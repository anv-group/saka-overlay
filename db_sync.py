import asyncio
import base64
import json
import os
import queue
import threading
import time
import uuid
from urllib.parse import quote, urlparse

import requests
from PySide6.QtCore import QObject, Signal

SQL_SETUP_SCRIPT = """-- Jalankan skrip ini 1x di Supabase Dashboard -> SQL Editor -> New Query
CREATE TABLE IF NOT EXISTS public.saka_words (
    word TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('whitelist', 'blocklist', 'custom')),
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    added_by TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Wajib agar event DELETE Realtime mengirim kata yang dihapus
ALTER TABLE public.saka_words REPLICA IDENTITY FULL;

-- Aktifkan Realtime untuk tabel saka_words
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_publication_tables
        WHERE pubname = 'supabase_realtime'
          AND schemaname = 'public'
          AND tablename = 'saka_words'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.saka_words;
    END IF;
END $$;

-- Kebijakan akses bersama untuk grup privat (menggunakan Anon / Publishable Key privat)
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.saka_words TO anon, authenticated;

ALTER TABLE public.saka_words ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow shared read/write" ON public.saka_words;
CREATE POLICY "Allow shared read/write"
ON public.saka_words
FOR ALL
USING (true)
WITH CHECK (true);

-- Tabel sinkronisasi pengaturan Tab MODE (Tag, Urutan, On/Off, Preset Brutal, Game Mode)
CREATE TABLE IF NOT EXISTS public.saka_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_by TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.saka_settings REPLICA IDENTITY FULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_publication_tables
        WHERE pubname = 'supabase_realtime'
          AND schemaname = 'public'
          AND tablename = 'saka_settings'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.saka_settings;
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.saka_settings TO anon, authenticated;

ALTER TABLE public.saka_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow shared read/write settings" ON public.saka_settings;
CREATE POLICY "Allow shared read/write settings"
ON public.saka_settings
FOR ALL
USING (true)
WITH CHECK (true);
"""

INVITE_PREFIX = "saka-db://"


def normalize_supabase_url(url: str) -> str:
    """Menormalkan Project URL Supabase (hapus spasi dan slash akhir)."""
    clean = (url or "").strip().rstrip("/")
    if not clean:
        return ""
    parsed = urlparse(clean)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL Supabase tidak valid (harus diawali https://).")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def build_realtime_ws_url(supabase_url: str, anon_key: str) -> str:
    """Mengonversi Project URL Supabase ke endpoint WebSocket Realtime Phoenix."""
    base = normalize_supabase_url(supabase_url)
    parsed = urlparse(base)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    key_q = quote((anon_key or "").strip(), safe="")
    base_path = parsed.path.rstrip("/")
    return f"{ws_scheme}://{parsed.netloc}{base_path}/realtime/v1/websocket?apikey={key_q}&vsn=1.0.0"


def encode_invite_config(url: str, anon_key: str) -> str:
    """Mengemas URL dan Anon Key menjadi string invite ringkas saka-db://..."""
    clean_url = normalize_supabase_url(url)
    clean_key = (anon_key or "").strip()
    if not clean_url or not clean_key:
        raise ValueError("Project URL dan Anon Key wajib diisi sebelum membuat Invite Config.")
    payload = json.dumps({"url": clean_url, "key": clean_key}, separators=(",", ":")).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{INVITE_PREFIX}{token}"


def decode_invite_config(raw_text: str) -> tuple[str, str]:
    """Mem-parsing string invite saka-db://... (atau JSON mentah) menjadi (url, anon_key)."""
    txt = (raw_text or "").strip()
    if not txt:
        raise ValueError("Invite Config kosong.")

    if txt.startswith(INVITE_PREFIX):
        token = txt[len(INVITE_PREFIX):].strip()
        padding = "=" * (-len(token) % 4)
        try:
            raw_json = base64.urlsafe_b64decode(token + padding).decode("utf-8")
            data = json.loads(raw_json)
        except Exception as exc:
            raise ValueError(f"Format Invite Config rusak: {exc}") from exc
    elif txt.startswith("{"):
        try:
            data = json.loads(txt)
        except Exception as exc:
            raise ValueError(f"JSON config tidak valid: {exc}") from exc
    else:
        raise ValueError("Format harus diawali 'saka-db://'.")

    if not isinstance(data, dict):
        raise ValueError("Struktur Invite Config tidak valid.")

    url = normalize_supabase_url(data.get("url", ""))
    key = (data.get("key") or data.get("anon_key") or "").strip()
    if not url or not key:
        raise ValueError("Invite Config tidak memuat URL dan Anon Key yang lengkap.")
    return url, key


def parse_realtime_table_change(msg: dict):
    """
    Mengekstrak (table, event_type, record, old_record) dari pesan WebSocket Supabase Realtime
    untuk tabel saka_words maupun saka_settings.
    """
    if not isinstance(msg, dict):
        return None
    if msg.get("event") != "postgres_changes":
        return None

    payload = msg.get("payload") or {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        return None

    table = data.get("table") or "saka_words"
    if table not in ("saka_words", "saka_settings"):
        return None

    ev_type = str(data.get("type") or data.get("eventType") or "").upper()
    if ev_type not in ("INSERT", "UPDATE", "DELETE"):
        return None

    record = data.get("record") or data.get("new") or {}
    old_record = data.get("old_record") or data.get("old") or {}
    return table, ev_type, record, old_record


def apply_presence_event(presence_map: dict, event_name: str, payload: dict) -> tuple[int, list]:
    """
    Memperbarui state presence lokal dari event Supabase Realtime (`presence_state` / `presence_diff`)
    lalu mengembalikan `(online_count, list_of_nicknames)`.
    """
    if not isinstance(payload, dict):
        return summarize_presence(presence_map)

    if event_name == "presence_state":
        presence_map.clear()
        for key, obj in payload.items():
            metas = (obj or {}).get("metas") if isinstance(obj, dict) else None
            if isinstance(metas, list) and metas:
                presence_map[str(key)] = list(metas)
    elif event_name == "presence_diff":
        joins = payload.get("joins") or {}
        leaves = payload.get("leaves") or {}
        if isinstance(joins, dict):
            for key, obj in joins.items():
                k = str(key)
                metas = (obj or {}).get("metas") if isinstance(obj, dict) else None
                if not isinstance(metas, list) or not metas:
                    continue
                existing = presence_map.setdefault(k, [])
                existing_refs = {m.get("phx_ref") for m in existing if isinstance(m, dict) and m.get("phx_ref")}
                for m in metas:
                    if isinstance(m, dict):
                        ref = m.get("phx_ref")
                        if ref and ref in existing_refs:
                            continue
                        existing.append(m)
                        if ref:
                            existing_refs.add(ref)
        if isinstance(leaves, dict):
            for key, obj in leaves.items():
                k = str(key)
                metas = (obj or {}).get("metas") if isinstance(obj, dict) else None
                if not isinstance(metas, list) or k not in presence_map:
                    continue
                leave_refs = {m.get("phx_ref") for m in metas if isinstance(m, dict) and m.get("phx_ref")}
                if leave_refs:
                    remaining = [
                        m for m in presence_map[k]
                        if not (isinstance(m, dict) and m.get("phx_ref") in leave_refs)
                    ]
                    if remaining:
                        presence_map[k] = remaining
                    else:
                        presence_map.pop(k, None)
                else:
                    presence_map.pop(k, None)
    return summarize_presence(presence_map)


def summarize_presence(presence_map: dict) -> tuple[int, list]:
    """Menghitung jumlah koneksi aktif dan daftar nickname dari presence_map."""
    names = []
    count = 0
    for key in sorted(presence_map.keys()):
        metas = presence_map.get(key) or []
        if not metas:
            continue
        count += 1
        last_meta = metas[-1] if isinstance(metas[-1], dict) else {}
        nick = str(last_meta.get("nickname") or "").strip()
        names.append(nick if nick else "Anonim")
    return count, names


def parse_realtime_postgres_change(msg: dict):
    """
    Mengekstrak (event_type, record, old_record) dari pesan WebSocket Supabase Realtime.
    Mengembalikan None jika pesan bukan event perubahan tabel saka_words.
    """
    parsed = parse_realtime_table_change(msg)
    if not parsed:
        return None
    table, ev_type, record, old_record = parsed
    if table != "saka_words":
        return None
    return ev_type, record, old_record


class DbCacheStore:
    """Menyimpan snapshot kata privat, state MODE, dan antrean tulis tertunda di db_cache.json."""

    def __init__(self, cache_path: str):
        self.cache_path = cache_path

    def load(self) -> dict:
        default_data = {
            "records": {},
            "last_synced_at": "",
            "pending_ops": [],
            "mode_state": None,
            "pending_mode_state": None,
            "mode_updated_by": "",
        }
        if not os.path.exists(self.cache_path):
            return default_data
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                return default_data
            records = raw.get("records") if isinstance(raw.get("records"), dict) else {}
            pending = raw.get("pending_ops") if isinstance(raw.get("pending_ops"), list) else []
            mode_state = raw.get("mode_state") if isinstance(raw.get("mode_state"), dict) else None
            pending_mode = raw.get("pending_mode_state") if isinstance(raw.get("pending_mode_state"), dict) else None
            return {
                "records": records,
                "last_synced_at": str(raw.get("last_synced_at") or ""),
                "pending_ops": pending,
                "mode_state": mode_state,
                "pending_mode_state": pending_mode,
                "mode_updated_by": str(raw.get("mode_updated_by") or ""),
            }
        except Exception:
            return default_data

    def save(
        self,
        records: dict,
        last_synced_at: str = "",
        pending_ops: list = None,
        mode_state: dict = None,
        pending_mode_state: dict = None,
        mode_updated_by: str = "",
    ) -> bool:
        data = {
            "records": records or {},
            "last_synced_at": last_synced_at or "",
            "pending_ops": list(pending_ops or []),
            "mode_state": mode_state if isinstance(mode_state, dict) else None,
            "pending_mode_state": pending_mode_state if isinstance(pending_mode_state, dict) else None,
            "mode_updated_by": str(mode_updated_by or ""),
        }
        try:
            folder = os.path.dirname(self.cache_path)
            if folder and not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            tmp_path = f"{self.cache_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.cache_path)
            return True
        except Exception:
            return False

    def clear(self) -> bool:
        try:
            if os.path.exists(self.cache_path):
                os.remove(self.cache_path)
            return True
        except Exception:
            return False


class PermanentSyncError(Exception):
    """Error non-transient (kredensial salah, tabel belum ada, RLS menolak)."""


class SettingsTableUnavailableError(Exception):
    """Tabel saka_settings belum dibuat/di-grant (user masih memakai SQL setup lama)."""


class SupabaseRestClient:
    """Client HTTP REST ringan untuk tabel public.saka_words & public.saka_settings di Supabase."""

    def __init__(self, url: str, anon_key: str, session=None, timeout: float = 8.0):
        self.base_url = normalize_supabase_url(url)
        self.anon_key = (anon_key or "").strip()
        if not self.anon_key:
            raise ValueError("Anon Key Supabase wajib diisi.")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.endpoint = f"{self.base_url}/rest/v1/saka_words"
        self.settings_endpoint = f"{self.base_url}/rest/v1/saka_settings"

    def _is_jwt_key(self) -> bool:
        return (not self.anon_key.startswith("sb_")) and (self.anon_key.count(".") == 2)

    def _headers(self, extra=None) -> dict:
        hdrs = {
            "apikey": self.anon_key,
            "Content-Type": "application/json",
        }
        if self._is_jwt_key():
            hdrs["Authorization"] = f"Bearer {self.anon_key}"
        if extra:
            hdrs.update(extra)
        return hdrs

    def _interpret_http_error(self, resp) -> str:
        code = getattr(resp, "status_code", 0)
        body = ""
        try:
            body = resp.text or ""
        except Exception:
            body = ""
        if code in (401, 403):
            if "42501" in body or "permission denied for table saka_words" in body.lower():
                return "Izin tabel 'saka_words' belum diberikan ke role anon. Klik 'Salin SQL' terbaru lalu Run ulang di Supabase SQL Editor."
            return "Anon / Publishable Key tidak valid atau ditolak oleh Policy (RLS)."
        if code == 404 or "PGRST205" in body or "saka_words" in body and "does not exist" in body.lower():
            return "Tabel 'saka_words' belum dibuat. Jalankan SQL Setup di Supabase terlebih dahulu."
        return f"HTTP {code}: {body[:160]}"

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = self.session.get(
                f"{self.endpoint}?select=word&limit=1",
                headers=self._headers(),
                timeout=self.timeout,
            )
            if 200 <= resp.status_code < 300:
                return True, "Terhubung! Tabel saka_words siap digunakan."
            return False, self._interpret_http_error(resp)
        except requests.Timeout:
            return False, "Koneksi timeout. Periksa internet atau cek apakah project Supabase sedang paused."
        except requests.RequestException as exc:
            return False, f"Gagal terhubung ke server: {exc}"

    def fetch_all_records(self, page_size: int = 1000) -> dict:
        records = {}
        offset = 0
        while True:
            headers = self._headers({"Range": f"{offset}-{offset + page_size - 1}"})
            resp = self.session.get(
                f"{self.endpoint}?select=word,status,is_custom,added_by,updated_at&order=word.asc",
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code in (401, 403, 404):
                raise PermanentSyncError(self._interpret_http_error(resp))
            if not (200 <= resp.status_code < 300):
                raise RuntimeError(self._interpret_http_error(resp))

            rows = resp.json() or []
            for row in rows:
                w = str(row.get("word") or "").strip().lower()
                if w:
                    records[w] = {
                        "word": w,
                        "status": str(row.get("status") or "custom").lower(),
                        "is_custom": bool(row.get("is_custom", False)),
                        "added_by": str(row.get("added_by") or ""),
                        "updated_at": str(row.get("updated_at") or ""),
                    }
            if len(rows) < page_size:
                break
            offset += page_size
        return records

    def upsert_record(self, record: dict) -> dict:
        payload = {
            "word": str(record["word"]).strip().lower(),
            "status": str(record["status"]).strip().lower(),
            "is_custom": bool(record.get("is_custom", False)),
            "added_by": str(record.get("added_by") or ""),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        headers = self._headers({"Prefer": "resolution=merge-duplicates,return=representation"})
        resp = self.session.post(
            f"{self.endpoint}?on_conflict=word",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        if resp.status_code in (401, 403, 404):
            raise PermanentSyncError(self._interpret_http_error(resp))
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(self._interpret_http_error(resp))
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return payload

    def upsert_batch(self, records: list, chunk_size: int = 200) -> int:
        if not records:
            return 0
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        headers = self._headers({"Prefer": "resolution=merge-duplicates,return=minimal"})
        total = 0
        for i in range(0, len(records), chunk_size):
            chunk = []
            for rec in records[i:i + chunk_size]:
                chunk.append({
                    "word": str(rec["word"]).strip().lower(),
                    "status": str(rec["status"]).strip().lower(),
                    "is_custom": bool(rec.get("is_custom", False)),
                    "added_by": str(rec.get("added_by") or ""),
                    "updated_at": now_iso,
                })
            resp = self.session.post(
                f"{self.endpoint}?on_conflict=word",
                headers=headers,
                json=chunk,
                timeout=max(self.timeout, 15.0),
            )
            if resp.status_code in (401, 403, 404):
                raise PermanentSyncError(self._interpret_http_error(resp))
            if not (200 <= resp.status_code < 300):
                raise RuntimeError(self._interpret_http_error(resp))
            total += len(chunk)
        return total

    def delete_word(self, word: str) -> None:
        w = quote(str(word).strip().lower(), safe="")
        resp = self.session.delete(
            f"{self.endpoint}?word=eq.{w}",
            headers=self._headers(),
            timeout=self.timeout,
        )
        if resp.status_code in (401, 403, 404):
            raise PermanentSyncError(self._interpret_http_error(resp))
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(self._interpret_http_error(resp))

    def _is_settings_missing_response(self, resp) -> bool:
        code = getattr(resp, "status_code", 0)
        body = (getattr(resp, "text", "") or "").lower()
        if code == 404 or "pgrst205" in body or "42p01" in body:
            return True
        if code in (401, 403) and ("42501" in body or "permission denied for table saka_settings" in body):
            return True
        return False

    def fetch_mode_state(self) -> tuple[dict | None, str]:
        resp = self.session.get(
            f"{self.settings_endpoint}?key=eq.mode_state&select=key,value,updated_by,updated_at",
            headers=self._headers(),
            timeout=self.timeout,
        )
        if self._is_settings_missing_response(resp):
            raise SettingsTableUnavailableError(
                "Tabel 'saka_settings' belum ada. Klik 'Salin SQL' lalu jalankan di Supabase SQL Editor untuk sinkronisasi Tab MODE."
            )
        if resp.status_code in (401, 403):
            raise PermanentSyncError(self._interpret_http_error(resp))
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(self._interpret_http_error(resp))
        rows = resp.json() or []
        if not rows:
            return None, ""
        row = rows[0]
        val = row.get("value")
        if not isinstance(val, dict):
            return None, ""
        return val, str(row.get("updated_by") or "")

    def upsert_mode_state(self, mode_state: dict, updated_by: str = "") -> dict:
        payload = {
            "key": "mode_state",
            "value": mode_state or {},
            "updated_by": str(updated_by or ""),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        headers = self._headers({"Prefer": "resolution=merge-duplicates,return=representation"})
        resp = self.session.post(
            f"{self.settings_endpoint}?on_conflict=key",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        if self._is_settings_missing_response(resp):
            raise SettingsTableUnavailableError(
                "Tabel 'saka_settings' belum ada. Klik 'Salin SQL' lalu jalankan di Supabase SQL Editor untuk sinkronisasi Tab MODE."
            )
        if resp.status_code in (401, 403):
            raise PermanentSyncError(self._interpret_http_error(resp))
        if not (200 <= resp.status_code < 300):
            raise RuntimeError(self._interpret_http_error(resp))
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return payload


class SupabaseSyncManager(QObject):
    """
    Pengelola sinkronisasi real-time latar belakang (REST + WebSocket Realtime).
    Memancarkan Qt Signals ke GUI thread tanpa memblokir OCR maupun tampilan.
    """

    snapshot_loaded = Signal(dict, bool)
    remote_event_received = Signal(str, dict, dict, bool)
    mode_state_loaded = Signal(dict, str)
    remote_mode_event_received = Signal(dict, str, bool)
    settings_table_missing = Signal(str)
    presence_updated = Signal(int, list)
    status_changed = Signal(str, str)
    operation_failed = Signal(str)

    def __init__(self, cache_path: str, parent=None):
        super().__init__(parent)
        self.cache_store = DbCacheStore(cache_path)
        self._lock = threading.Lock()
        self._records = {}
        self._pending_ops = []
        self._last_synced_at = ""
        self._recently_pushed = {}  # word -> monotonic timestamp

        self._mode_state = None
        self._pending_mode_state = None
        self._mode_updated_by = ""
        self._last_mode_pushed_at = 0.0
        self._last_mode_pushed_hash = ""
        self._notified_settings_missing = False
        self._presence_key = uuid.uuid4().hex[:12]
        self._presence_map = {}

        self._url = ""
        self._anon_key = ""
        self._nickname = ""
        self._running = False
        self._thread = None
        self._op_queue = queue.Queue()
        self._wake_event = threading.Event()

    def load_cached_records(self) -> dict:
        cached = self.cache_store.load()
        with self._lock:
            self._records = dict(cached.get("records", {}))
            self._pending_ops = list(cached.get("pending_ops", []))
            self._last_synced_at = cached.get("last_synced_at", "")
            self._mode_state = cached.get("mode_state")
            self._pending_mode_state = cached.get("pending_mode_state")
            self._mode_updated_by = cached.get("mode_updated_by", "")
            return dict(self._records)

    def load_cached_mode_state(self):
        with self._lock:
            if isinstance(self._mode_state, dict):
                return dict(self._mode_state)
        cached = self.cache_store.load()
        ms = cached.get("mode_state")
        return dict(ms) if isinstance(ms, dict) else None

    def get_cached_records_snapshot(self) -> dict:
        with self._lock:
            return dict(self._records)

    def _save_cache_locked(self):
        self.cache_store.save(
            self._records,
            last_synced_at=self._last_synced_at,
            pending_ops=self._pending_ops,
            mode_state=self._mode_state,
            pending_mode_state=self._pending_mode_state,
            mode_updated_by=self._mode_updated_by,
        )

    def start(self, url: str, anon_key: str, nickname: str = ""):
        self.stop()
        self._url = normalize_supabase_url(url)
        self._anon_key = (anon_key or "").strip()
        self._nickname = (nickname or "").strip()
        self._notified_settings_missing = False
        if not self._url or not self._anon_key:
            self.status_changed.emit("error", "URL atau Anon Key Supabase belum diatur.")
            return

        self.load_cached_records()
        # Bersihkan antrean memori sisa sebelumnya tanpa menghapus pending_ops persisten
        while not self._op_queue.empty():
            try:
                self._op_queue.get_nowait()
            except queue.Empty:
                break

        self._running = True
        self._wake_event.clear()
        self.status_changed.emit("connecting", "Menyambungkan ke database...")
        self._thread = threading.Thread(target=self._run_worker_thread, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._presence_map = {}
        self.presence_updated.emit(0, [])

    def update_nickname(self, nickname: str):
        self._nickname = (nickname or "").strip()
        if self._running:
            self._op_queue.put({"action": "presence_track"})
            self._wake_event.set()

    def request_resync(self):
        """Memicu fetch ulang snapshot kata & MODE dari server tanpa memutus WebSocket."""
        if self._running:
            self._op_queue.put({"action": "resync"})
            self._wake_event.set()

    def clear_cache(self) -> bool:
        """Menghapus cache lokal (db_cache.json) dan mereset state cache di memori."""
        with self._lock:
            self._records = {}
            self._pending_ops = []
            self._last_synced_at = ""
            self._mode_state = None
            self._pending_mode_state = None
            self._mode_updated_by = ""
            return self.cache_store.clear()

    def enqueue_mode_state(self, mode_state: dict):
        """Menyimpan state Tab MODE ke cache lokal dan mengantrekan upsert ke saka_settings."""
        if not isinstance(mode_state, dict):
            return
        clean = dict(mode_state)
        payload_hash = json.dumps(clean, sort_keys=True, ensure_ascii=False)
        with self._lock:
            self._mode_state = clean
            self._pending_mode_state = clean
            self._mode_updated_by = self._nickname
            self._last_mode_pushed_at = time.monotonic()
            self._last_mode_pushed_hash = payload_hash
            self._save_cache_locked()
        self._op_queue.put({"action": "mode_upsert"})
        self._wake_event.set()

    def _consume_mode_self_echo(self, val: dict) -> bool:
        payload_hash = json.dumps(val or {}, sort_keys=True, ensure_ascii=False)
        now = time.monotonic()
        with self._lock:
            if self._pending_mode_state is not None:
                return True
            if self._last_mode_pushed_hash and (now - self._last_mode_pushed_at) < 8.0:
                if payload_hash == self._last_mode_pushed_hash:
                    return True
        return False

    def enqueue_mutation(self, action: str, word: str, record: dict = None):
        """
        Mencatat perubahan lokal secara optimistik di cache dan mengantrekan
        pengiriman ke server Supabase di background.
        """
        w = (word or "").strip().lower()
        if not w:
            return
        with self._lock:
            self._recently_pushed[w] = time.monotonic()
            if action == "upsert" and record:
                rec = dict(record)
                rec["word"] = w
                if not rec.get("added_by") and self._nickname:
                    rec["added_by"] = self._nickname
                self._records[w] = rec
                op = {"action": "upsert", "word": w, "record": rec}
            else:
                self._records.pop(w, None)
                op = {"action": "delete", "word": w, "record": None}

            # Deduplikasi antrean untuk kata yang sama (ambil aksi terbaru)
            self._pending_ops = [p for p in self._pending_ops if p.get("word") != w]
            self._pending_ops.append(op)
            self._save_cache_locked()

        self._op_queue.put(op)
        self._wake_event.set()

    def _consume_self_echo(self, word: str) -> bool:
        w = (word or "").strip().lower()
        now = time.monotonic()
        with self._lock:
            # Bersihkan penanda kedaluwarsa (> 8 detik)
            expired = [k for k, ts in self._recently_pushed.items() if now - ts > 8.0]
            for k in expired:
                self._recently_pushed.pop(k, None)
            if w in self._recently_pushed:
                self._recently_pushed.pop(w, None)
                return True
        return False

    def _run_worker_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main_loop())
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def _async_main_loop(self):
        client = SupabaseRestClient(self._url, self._anon_key)
        backoff = 2.0
        first_sync = True

        while self._running:
            try:
                self.status_changed.emit("syncing", "Menyinkronkan data...")
                # 1. Flush pending ops terlebih dulu agar edit offline tidak tertimpa fetch
                await asyncio.to_thread(self._flush_pending_ops, client)
                await asyncio.to_thread(self._flush_pending_mode_state, client)

                # 2. Fetch snapshot terbaru dari server
                server_records = await asyncio.to_thread(client.fetch_all_records)
                now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

                with self._lock:
                    # Jangan timpa kata yang masih punya pending_ops aktif di memori
                    pending_words = {p.get("word") for p in self._pending_ops}
                    merged = dict(server_records)
                    for pw in pending_words:
                        if pw in self._records:
                            merged[pw] = self._records[pw]
                        else:
                            merged.pop(pw, None)
                    self._records = merged
                    self._last_synced_at = now_iso
                    self._save_cache_locked()
                    snapshot_copy = dict(self._records)

                self.snapshot_loaded.emit(snapshot_copy, not first_sync)

                # 2b. Fetch mode_state dari saka_settings (tidak memblokir sync kata jika tabel belum dibuat)
                try:
                    srv_mode, srv_by = await asyncio.to_thread(client.fetch_mode_state)
                    if isinstance(srv_mode, dict):
                        should_emit_mode = False
                        with self._lock:
                            if self._pending_mode_state is None:
                                self._mode_state = srv_mode
                                self._mode_updated_by = srv_by
                                self._save_cache_locked()
                                should_emit_mode = True
                        if should_emit_mode:
                            self.mode_state_loaded.emit(dict(srv_mode), srv_by)
                except SettingsTableUnavailableError as exc:
                    if not self._notified_settings_missing:
                        self._notified_settings_missing = True
                        self.settings_table_missing.emit(str(exc))

                first_sync = False
                backoff = 2.0

                # 3. Buka WebSocket Realtime + task pengirim mutasi
                await self._listen_realtime(client)

            except PermanentSyncError as exc:
                self.status_changed.emit("error", str(exc))
                self.operation_failed.emit(str(exc))
                # Tunggu lebih lama sebelum mencoba lagi atau sampai user perbaiki config
                for _ in range(15):
                    if not self._running:
                        return
                    await asyncio.sleep(1.0)
            except Exception as exc:
                if not self._running:
                    break
                self.status_changed.emit("offline", f"Koneksi terputus ({type(exc).__name__}), menyambung ulang...")
                waited = 0.0
                while self._running and waited < backoff:
                    await asyncio.sleep(0.5)
                    waited += 0.5
                backoff = min(30.0, backoff * 2.0)

    def _flush_pending_ops(self, client: SupabaseRestClient):
        while self._running:
            with self._lock:
                if not self._pending_ops:
                    return
                op = dict(self._pending_ops[0])

            try:
                if op["action"] == "upsert" and op.get("record"):
                    client.upsert_record(op["record"])
                elif op["action"] == "delete":
                    client.delete_word(op["word"])
            except PermanentSyncError as exc:
                # Hapus op permanen yang ditolak agar tidak menyumbat antrean
                with self._lock:
                    if self._pending_ops and self._pending_ops[0].get("word") == op["word"]:
                        self._pending_ops.pop(0)
                        self._save_cache_locked()
                raise exc

            with self._lock:
                if self._pending_ops and self._pending_ops[0].get("word") == op["word"]:
                    self._pending_ops.pop(0)
                    self._save_cache_locked()

    def _flush_pending_mode_state(self, client: SupabaseRestClient):
        with self._lock:
            pending = dict(self._pending_mode_state) if isinstance(self._pending_mode_state, dict) else None
            nick = self._nickname
        if not pending:
            return
        try:
            client.upsert_mode_state(pending, updated_by=nick)
            with self._lock:
                if self._pending_mode_state == pending:
                    self._pending_mode_state = None
                    self._save_cache_locked()
        except SettingsTableUnavailableError as exc:
            with self._lock:
                self._pending_mode_state = None
                self._save_cache_locked()
            if not self._notified_settings_missing:
                self._notified_settings_missing = True
                self.settings_table_missing.emit(str(exc))

    async def _listen_realtime(self, client: SupabaseRestClient):
        import websockets

        ws_url = build_realtime_ws_url(self._url, self._anon_key)
        is_jwt = (not self._anon_key.startswith("sb_")) and (self._anon_key.count(".") == 2)
        headers = {"apikey": self._anon_key}
        if is_jwt:
            headers["Authorization"] = f"Bearer {self._anon_key}"

        async with websockets.connect(
            ws_url,
            additional_headers=headers,
            ping_interval=None,
            open_timeout=10,
            close_timeout=5,
        ) as ws:
            ref_counter = 1
            join_ref = str(ref_counter)
            self._presence_map = {}
            join_payload = {
                "config": {
                    "broadcast": {"self": False},
                    "presence": {"key": self._presence_key},
                    "postgres_changes": [
                        {"event": "*", "schema": "public", "table": "saka_words"},
                        {"event": "*", "schema": "public", "table": "saka_settings"},
                    ],
                },
            }
            if is_jwt:
                join_payload["access_token"] = self._anon_key

            join_msg = {
                "topic": "realtime:saka_sync",
                "event": "phx_join",
                "payload": join_payload,
                "ref": join_ref,
                "join_ref": join_ref,
            }
            await ws.send(json.dumps(join_msg))
            self.status_changed.emit("live", "Terhubung Real-Time (Supabase)")

            async def _send_presence_track():
                nonlocal ref_counter
                ref_counter += 1
                track_msg = {
                    "topic": "realtime:saka_sync",
                    "event": "presence",
                    "payload": {
                        "type": "presence",
                        "event": "track",
                        "payload": {
                            "nickname": self._nickname,
                            "online_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        },
                    },
                    "ref": str(ref_counter),
                    "join_ref": join_ref,
                }
                await ws.send(json.dumps(track_msg))

            async def _heartbeat_and_writer():
                nonlocal ref_counter
                last_hb = time.monotonic()
                while self._running:
                    # Kirim mutasi lokal jika ada
                    if not self._op_queue.empty():
                        need_retrack = False
                        need_resync = False
                        while not self._op_queue.empty():
                            try:
                                item = self._op_queue.get_nowait()
                                if isinstance(item, dict):
                                    if item.get("action") == "presence_track":
                                        need_retrack = True
                                    elif item.get("action") == "resync":
                                        need_resync = True
                            except queue.Empty:
                                break
                        if need_retrack:
                            try:
                                await _send_presence_track()
                            except Exception:
                                pass
                        try:
                            await asyncio.to_thread(self._flush_pending_ops, client)
                            await asyncio.to_thread(self._flush_pending_mode_state, client)
                            if need_resync:
                                server_records = await asyncio.to_thread(client.fetch_all_records)
                                now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                                with self._lock:
                                    pending_words = {p.get("word") for p in self._pending_ops}
                                    merged = dict(server_records)
                                    for pw in pending_words:
                                        if pw in self._records:
                                            merged[pw] = self._records[pw]
                                        else:
                                            merged.pop(pw, None)
                                    self._records = merged
                                    self._last_synced_at = now_iso
                                    self._save_cache_locked()
                                    snap_copy = dict(self._records)
                                self.snapshot_loaded.emit(snap_copy, True)
                                try:
                                    srv_mode, srv_by = await asyncio.to_thread(client.fetch_mode_state)
                                    if isinstance(srv_mode, dict):
                                        with self._lock:
                                            if self._pending_mode_state is None:
                                                self._mode_state = srv_mode
                                                self._mode_updated_by = srv_by
                                                self._save_cache_locked()
                                                emit_mode = True
                                            else:
                                                emit_mode = False
                                        if emit_mode:
                                            self.mode_state_loaded.emit(dict(srv_mode), srv_by)
                                except SettingsTableUnavailableError:
                                    pass
                        except PermanentSyncError as exc:
                            self.operation_failed.emit(str(exc))
                            self.status_changed.emit("error", str(exc))
                        except Exception:
                            self.status_changed.emit("offline", "Gagal kirim perubahan, masuk antrean retry...")

                    # Kirim Phoenix heartbeat tiap 25 detik
                    now = time.monotonic()
                    if now - last_hb >= 25.0:
                        ref_counter += 1
                        hb = {
                            "topic": "phoenix",
                            "event": "heartbeat",
                            "payload": {},
                            "ref": str(ref_counter),
                        }
                        await ws.send(json.dumps(hb))
                        last_hb = now

                    await asyncio.sleep(0.15)

            writer_task = asyncio.create_task(_heartbeat_and_writer())
            try:
                while self._running:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue

                    ev_name = msg.get("event")
                    if ev_name == "phx_reply" and str(msg.get("ref")) == join_ref:
                        if isinstance(msg.get("payload"), dict) and msg["payload"].get("status") == "ok":
                            await _send_presence_track()
                        continue

                    if ev_name in ("presence_state", "presence_diff"):
                        cnt, names = apply_presence_event(self._presence_map, ev_name, msg.get("payload") or {})
                        self.presence_updated.emit(cnt, names)
                        continue

                    parsed = parse_realtime_table_change(msg)
                    if not parsed:
                        continue
                    table, ev_type, record, old_record = parsed

                    if table == "saka_settings":
                        key_name = str((record if ev_type != "DELETE" else old_record).get("key") or "").strip()
                        if key_name != "mode_state" or ev_type == "DELETE":
                            continue
                        val = record.get("value")
                        if not isinstance(val, dict):
                            continue
                        is_self = self._consume_mode_self_echo(val)
                        upd_by = str(record.get("updated_by") or "")
                        if not is_self:
                            with self._lock:
                                self._mode_state = dict(val)
                                self._mode_updated_by = upd_by
                                self._save_cache_locked()
                        self.remote_mode_event_received.emit(dict(val), upd_by, is_self)
                        continue

                    word = str((record if ev_type != "DELETE" else old_record).get("word") or "").strip().lower()
                    if not word:
                        continue

                    is_self = self._consume_self_echo(word)
                    with self._lock:
                        if ev_type in ("INSERT", "UPDATE"):
                            self._records[word] = {
                                "word": word,
                                "status": str(record.get("status") or "custom").lower(),
                                "is_custom": bool(record.get("is_custom", False)),
                                "added_by": str(record.get("added_by") or ""),
                                "updated_at": str(record.get("updated_at") or ""),
                            }
                        elif ev_type == "DELETE":
                            self._records.pop(word, None)
                        self._save_cache_locked()

                    self.remote_event_received.emit(ev_type, record, old_record, is_self)
            finally:
                writer_task.cancel()
                try:
                    await writer_task
                except BaseException:
                    pass
