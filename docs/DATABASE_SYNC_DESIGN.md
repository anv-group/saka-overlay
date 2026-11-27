# ☁️ DATABASE_SYNC_DESIGN.md — Sinkronisasi Database Privat Real-Time (SAKA Overlay)

> **Status:** Validated Design Specification  
> **Tanggal:** 2026-11-27  
> **Target:** Dual-Mode Storage (`Mode File TXT` default vs. `Mode Database Privat` Supabase)

---

## 1. Understanding Summary

- **Apa yang dibangun:** Sistem sinkronisasi **real-time** untuk **Whitelist, Blocklist, dan Kata Tambahan (Custom Kamus)** berbasis dua mode di SAKA Overlay: **Mode File `.txt` (Default)** dan **Mode Database Privat (Setting Sendiri)**.
- **Mengapa dibuat:** Agar kelompok teman dalam satu room/grup privat dapat menambah atau menghapus kata secara bersama-sama dan melihat perubahannya **secara langsung** di aplikasi masing-masing tanpa sinkronisasi file manual, tanpa restart aplikasi, dan tanpa refresh manual.
- **Untuk siapa:**
  - Pengguna umum/publik: tetap menggunakan file `.txt` bawaan repository (`whitelist.txt`, `blacklist.txt`, `kamus_lengkap.txt`).
  - Pengguna/grup privat: membuat dan mengelola database cloud gratis sendiri untuk dipakai bersama teman-teman.
- **Batasan Utama (Constraints):**
  - Kamus dasar (~148.000 kata dari `kamus_kbbi.txt`, `kamus_contek.txt`, `kamus_lengkap.txt`) tetap dibaca secara lokal dari file `.txt`.
  - Di Mode Database, data privat **terpisah penuh** dari `whitelist.txt` & `blacklist.txt` publik (plus tersedia tombol opsional *Import dari `.txt`* sekali klik).
  - User mengelola database privat sendiri via Cloud BaaS gratis (Supabase) tanpa perlu menyewa VPS atau menyalakan PC host 24 jam.
  - Berbagi akses antar teman memakai *Shared Project Key / Invite Config* (tanpa login akun individual; opsional *Nickname* lokal untuk label kontributor).
- **Explicit Non-Goals:**
  - Tidak membangun sistem akun user/login dengan manajemen role (Admin/Read-only).
  - Tidak memindahkan/menyinkronkan ~148.000 kata kamus dasar ke database cloud.
  - Tidak mengubah perilaku bawaan `Mode File TXT` saat tidak menggunakan database.
  - Tidak menghapus fitur `whitelist.txt`, `blacklist.txt`, maupun mekanisme `config.local.json`.

---

## 2. Non-Functional Requirements & Explicit Assumptions

1. **Performa & Responsivitas *(Asumsi)*:**
   - Perubahan kata dari satu pengguna muncul di aplikasi teman dalam **< 1–2 detik** melalui push WebSocket (bukan polling rutin atau fetch per OCR).
   - Saat OCR mendeteksi huruf (interval `80 ms`), `SambungKataSolver.cari_jawaban()` tetap bekerja **100% di RAM lokal (< 1 ms, $O(1)$)** tanpa request jaringan.
   - Seluruh operasi jaringan (REST & WebSocket) dijalankan di background thread agar GUI PySide6 dan OCR tidak pernah freeze.
2. **Skala Data & Trafik *(Asumsi)*:**
   - **2–20 pengguna bersamaan** per database privat.
   - Ratusan hingga **~10.000 entri kata** tersinkronisasi (whitelist + blocklist + custom words), aman di dalam batas Free Tier Supabase.
3. **Keamanan & Privasi *(Asumsi)*:**
   - Kredensial (`storage_mode`, `supabase_url`, `supabase_anon_key`, `sync_nickname`) disimpan di `config.local.json` (gitignored, kebal `git pull`).
   - Cache lokal Mode Database disimpan di `db_cache.json` (harus ditambahkan ke `.gitignore`).
   - Keamanan grup privat bergantung pada kerahasiaan *Invite Config / Anon Key* yang hanya dibagikan ke teman terpercaya.
4. **Reliabilitas & Ketersediaan *(Asumsi)*:**
   - Startup instan dengan memuat `db_cache.json` lebih dulu sebelum initial sync REST selesai.
   - Auto-reconnect WebSocket dengan *exponential backoff* + *catch-up sync* saat koneksi pulih.
5. **Pemeliharaan & Kepemilikan *(Asumsi)*:**
   - Pemilik grup membuat dan memantau project Supabase gratisnya sendiri dengan panduan setup 1x (salin SQL setup langsung dari UI Tab `SYSTEM`).

---

## 3. Decision Log

| ID | Keputusan | Alternatif yang Dipertimbangkan | Alasan Dipilih |
|---|---|---|---|
| **D1** | Data yang disinkronkan: **Whitelist, Blocklist, dan Custom Kamus** (kamus dasar ~148k tetap lokal) | Hanya WL+BL; atau seluruh 148k kamus ikut di DB | Ringan untuk free tier, startup cepat, fokus ke data dinamis temuan pemain |
| **D2** | Model hosting: **Cloud BaaS Gratis** (user daftar & kelola sendiri) | Self-hosted VPS/PC; Direct SQL host/port | Nol biaya server, teman bisa konek kapan saja tanpa PC host menyala 24 jam |
| **D3** | Relasi dengan `.txt` publik: **Terpisah penuh + opsi Import 1-klik** | Merge `.txt` + DB; Mirror dua arah | File `.txt` publik tetap bersih & aman saat `git pull`, DB privat tidak tercampur |
| **D4** | Kontrol akses: **Shared Project Key / Invite Config** (+ opsional Nickname lokal) | Login akun + Role Admin/Read-only | Sesuai prinsip YAGNI untuk grup teman dekat yang saling percaya |
| **D5** | Platform & protokol: **Supabase (PostgreSQL + Lightweight REST & Realtime WebSocket)** | Firebase RTDB + SSE; Generic HTTP Delta Polling | Setup SQL lebih jelas tanpa jebakan test-mode expired 30 hari, tabel terstruktur, realtime push hemat kuota |
| **D6** | Cakupan sinkronisasi MODE: **Tag Kustom (`Kelola`: urutan, warna, on/off), Preset `Brutal`, Game Mode aktif, & Mode Sortir** | Hanya `Kelola`; atau `Kelola` + Preset `Brutal` | Semua pemain satu grup bermain dengan strategi & kondisi mode yang 100% seragam |
| **D7** | Isolasi MODE: **Terpisah penuh dari `config.local.json` Mode TXT + opsi Upload Lokal -> DB** | Langsung timpa `config.local.json` | Konsisten dengan isolasi Whitelist/Blocklist; pengaturan lokal Mode TXT tidak pernah tertimpa |
| **D8** | Inisialisasi DB MODE kosong: **Fallback lokal sementara sampai ada yang mengubah/upload ke DB** | Mulai dari 0 tag kosong; atau auto-upload paksa saat konek | Mencegah quick-tag bar mendadak kosong saat baru konek ke DB baru |
| **D9** | Penyimpanan MODE di Supabase: **Tabel `saka_settings` (`key TEXT PRIMARY KEY, value JSONB`) dengan 1 baris `'mode_state'`** | Tabel relasional per tag (`position INT`); atau sentinel row di `saka_words` | Pengurutan list & ganti game mode bersifat atomik tanpa konflik posisi/race condition |
| **D10** | Pemicu & warna indikasi title bar: **Remote (`accent_cyan`) dan Lokal (`warning`)** | Hanya Remote; atau satu warna sama | Membedakan secara instan antara update masuk dari teman vs pengiriman lokal |
| **D11** | Gaya & durasi indikasi: **Pulse/kedip cepat 2–3x (~1.1–1.3 detik) lalu kembali ke `DB LIVE`** | Solid highlight tanpa kedip; atau dot menetap | Menarik perhatian seketika tanpa mengganggu fokus saat bermain |
| **D12** | Mekanisme render animasi: **State-machine `QTimer` + QSS + Cached MDI Icon** | `QPropertyAnimation` + `QGraphicsEffect`; atau ubah warna ikon saja | Tajam, bebas artefak DPI scaling di Windows, zero layout shift |

---

## 4. Final Design

### 4.1 Arsitektur & Komponen

Memisahkan **mesin pencarian memori (`SambungKataSolver` di `solver.py`)** dari **lapisan persistensi & sinkronisasi**:

- **`SambungKataSolver` (`solver.py`):**
  - Tetap mempertahankan `kbbi_set`, `contek_set` (selalu dimuat dari `.txt` lokal), `custom_set`, `whitelisted_words`, `blacklisted_words`, `word_set`, dan `words_by_initial`.
  - Menerima `storage_mode` (`"txt"` atau `"supabase"`) beserta backend/sync adapter.
  - Mendukung *hot-swap* mode langsung di RAM (`switch_storage_mode(...)`) tanpa restart aplikasi.
- **`TxtStorageBackend` (Default):**
  - Perilaku identik dengan implementasi saat ini (`whitelist.txt`, `blacklist.txt`, penambahan ke `kamus_lengkap.txt`/`kamus_contek.txt`).
- **`SupabaseSyncManager` (`db_sync.py`):**
  - Berjalan di background worker thread (memakai `requests`/`httpx` + `websockets`).
  - Memuat & memperbarui `db_cache.json` sebagai cache lokal privat (terpisah total dari file `.txt`).
  - Memancarkan **Qt Signals** (`words_synced`, `word_event_received`, `status_changed`, `sync_error`) ke main thread `app_qt.py` sehingga `solver` dan widget PySide6 (`LIVE`, `KAMUS`, badge status) langsung diperbarui otomatis.
- **Konfigurasi (`config.py`):**
  - Menambahkan kunci lokal baru ke `DEFAULT_CONFIG` & `local_keys` (`config.local.json`):
    - `storage_mode`: `"txt"` (default) | `"supabase"`
    - `supabase_url`: `""`
    - `supabase_anon_key`: `""`
    - `sync_nickname`: `""`

### 4.2 Skema Database Supabase (`saka_words`)

Satu tabel terpadu untuk mencegah konflik state ganda (misal satu kata tidak bisa berada di whitelist dan blocklist sekaligus):

```sql
CREATE TABLE IF NOT EXISTS public.saka_words (
    word TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('whitelist', 'blocklist', 'custom')),
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    added_by TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Wajib agar event DELETE Realtime membawa nama kata (old_record)
ALTER TABLE public.saka_words REPLICA IDENTITY FULL;

-- Aktifkan Realtime untuk tabel ini
ALTER PUBLICATION supabase_realtime ADD TABLE public.saka_words;

-- RLS sederhana untuk akses bersama via Anon Key privat
ALTER TABLE public.saka_words ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow shared read/write"
ON public.saka_words
FOR ALL
USING (true)
WITH CHECK (true);
```

**Aturan Transisi State:**
- **Whitelist kata (`F3` / klik bintang):** `UPSERT` dengan `status = 'whitelist'`. Jika kata tidak ada di `kbbi_set | contek_set` lokal (atau sudah `is_custom = true`), pertahankan `is_custom = true`.
- **Unwhitelist kata:**
  - Jika `is_custom = true`, `UPDATE` menjadi `status = 'custom'` (kata tetap ada di kamus tambahan, hanya keluar dari prioritas #1 whitelist).
  - Jika `is_custom = false`, `DELETE` baris dari `saka_words`.
- **Blocklist kata (`F4` / klik silang):** `UPSERT` dengan `status = 'blocklist'` (otomatis menggantikan status whitelist/custom sebelumnya).
- **Unblocklist kata:**
  - Jika `is_custom = true`, `UPDATE` menjadi `status = 'custom'`.
  - Jika `is_custom = false`, `DELETE` baris dari `saka_words`.
- **Tambah Kata Kamus (`F7` / `add_word`):** `UPSERT` dengan `status = 'custom'`, `is_custom = true`.

### 4.3 Alur Data Real-Time (Data Flow)

1. **Startup / Switch ke Mode Database:**
   - Memuat `kbbi_set` & `contek_set` dari `.txt` lokal.
   - Memuat `db_cache.json` langsung ke `whitelisted_words`, `blacklisted_words`, `custom_set` → `_rebuild_active_words()`.
   - Worker melakukan `GET /rest/v1/saka_words?select=*` → menyamakan RAM & `db_cache.json` → menghubungkan WebSocket ke `wss://<project>.supabase.co/realtime/v1/websocket` (subscribe `postgres_changes` pada `public:saka_words`).
2. **Aksi Lokal:**
   - RAM solver & UI diperbarui instan (*optimistic update*).
   - Worker mengirim `POST/PATCH/DELETE` REST API di background.
3. **Aksi dari Teman (Remote Event):**
   - WebSocket menerima event `INSERT` / `UPDATE` / `DELETE` → memancarkan Qt Signal ke main thread.
   - Main thread menerapkan perubahan secara idempoten ke `solver` RAM (`_rebuild_active_words()` jika `custom_set` berubah) dan menulis ulang `db_cache.json`.
   - UI aktif langsung refresh otomatis (rekomendasi kata pada Tab `LIVE` jika ada prefix aktif, serta daftar kata di Tab `KAMUS`).

### 4.4 Antarmuka Pengguna (UI & Setup)

Seluruh komponen UI mengikuti aturan `DESIGN.md` (menggunakan palet `THEME` di `qt_theme.py` dan ikon vektor MDI dari `assets/icons/`, **tanpa emoji OS** pada label/tombol Qt):

1. **Tab `SYSTEM` — Bagian Sinkronisasi Database:**
   - **Mode Penyimpanan:** Pilihan `File TXT (Default)` vs `Database Privat (Supabase)`.
   - **Kredensial:** Field `Project URL`, `Anon Key` (opsi tampil/sembunyikan), dan `Nickname (Opsional)`.
   - **Aksi Setup & Berbagi:**
     - `Salin SQL Setup`: menyalin skrip SQL tabel `saka_words` ke clipboard.
     - `Tes & Hubungkan`: validasi koneksi & keberadaan tabel sebelum menyimpan/mengaktifkan.
     - `Salin Invite Config` & `Tempel Invite Config`: encode/decode JSON `{url, key}` dengan prefix ringkas (misal `saka-db://<base64>`) untuk dibagikan ke teman.
     - `Import .txt ke Database`: menyalin `whitelist.txt` & `blacklist.txt` lokal ke `saka_words` dengan konfirmasi.
2. **Indikator Status Global:**
   - Badge status ringkas pada header/toolbar (`TXT` netral, `DB LIVE` aksen `primary`, `DB SYNC` aksen `warning`, `DB OFFLINE/ERR` aksen `danger`) dengan tooltip detail error atau timestamp sinkronisasi terakhir.

### 4.5 Error Handling, Edge Cases & Keamanan

- **Putus Koneksi & Catch-up:** Heartbeat WebSocket (~25s); jika putus, *exponential backoff reconnect* (2s → 4s → 8s → maks 30s). Setelah tersambung ulang, lakukan *catch-up sync* (`updated_at > last_synced_at` atau full snapshot ringkas) agar tidak ada kata yang terlewat.
- **Offline Saat Startup / Saat Main:** Aplikasi tetap berjalan memakai `db_cache.json` (`DB OFFLINE`). Aksi tulis yang gagal karena timeout/jaringan masuk ke antrean retry ringan hingga koneksi pulih; error permanen (`401/403/404` tabel belum dibuat atau project ter-pause) memunculkan pesan jelas di status + toast tanpa crash.
- **Deduplikasi Optimistic Echo:** Penerapan event WebSocket bersifat idempoten terhadap state RAM sehingga pantulan event milik sendiri tidak memicu duplikasi atau toast berulang.
- **Git Hygiene:** `db_cache.json` dan `config.local.json` berada di `.gitignore`.

### 4.6 Strategi Pengujian (Testing Strategy)

1. **Regresi Mode TXT:** Menjalankan `test_solver.py` untuk memastikan Mode File TXT tetap 100% lulus tanpa perubahan perilaku.
2. **Unit Test Sinkronisasi (`test_db_sync.py`):** Menggunakan mock HTTP & mock WebSocket payload (tanpa koneksi internet nyata) untuk menguji:
   - Event `INSERT`, `UPDATE`, `DELETE` memperbarui `whitelisted_words`, `blacklisted_words`, dan `custom_set` di `SambungKataSolver`.
   - Aturan transisi `is_custom` saat unwhitelist/unblocklist.
   - Encode/decode `saka-db://` Invite Config dan validasi error input.
   - Fallback baca `db_cache.json` saat offline dan *hot-swap* `txt` ↔ `supabase`.

---

## 5. Ekstensi Desain: Sinkronisasi Tab MODE (`saka_settings`)

### 5.1 Skema SQL Tambahan (`public.saka_settings`)
Skrip SQL setup bersifat idempoten (aman dijalankan ulang oleh user lama tanpa menghapus `saka_words`):
```sql
CREATE TABLE IF NOT EXISTS public.saka_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_by TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.saka_settings REPLICA IDENTITY FULL;
-- Tambahkan ke publikasi supabase_realtime jika belum terdaftar
-- GRANT USAGE & SELECT/INSERT/UPDATE/DELETE ke anon, authenticated + RLS "Allow shared read/write"
```

### 5.2 Payload `mode_state` & Isolasi Config Lokal
- **Payload JSONB (`key = 'mode_state'`):** memuat `custom_trap_endings` (termasuk urutan, warna, state `enabled`), `brutal_mode_tags`, `saved_default_tags`, `santai_auto_disabled_tags`, `game_mode`, dan `tier0_sort_mode`.
- **Isolasi Penuh:** Selama `storage_mode == "supabase"`, perubahan MODE hanya memperbarui state runtime, `db_cache.json` (`mode_state`, `pending_mode_state`), dan server `saka_settings` — **tidak** menimpa field MODE di `config.local.json`. Kembali ke Mode File TXT akan memuat ulang state MODE lokal asli dari `config.local.json`.
- **Fallback DB Baru:** Jika `saka_settings` belum memiliki baris `'mode_state'`, aplikasi memakai fallback lokal sementara di runtime sampai ada user yang mengubah tag/mode atau menekan **Upload Lokal -> DB**.

### 5.3 Alur Real-Time, Debouncing & Upload Lokal -> DB
- **1 Koneksi WebSocket:** `phx_join` mendaftarkan `postgres_changes` untuk `saka_words` dan `saka_settings` sekaligus.
- **Debouncing (~200 ms):** Mutasi MODE lokal langsung memperbarui RAM/UI (0 ms), lalu di-*debounce* ~200 ms sebelum di-`UPSERT` ke `saka_settings`.
- **Penerapan Remote Event:** Update dari teman memperbarui runtime config, `solver.set_custom_endings(...)`, `tab_live` (quick tags, mode pills, sort button, hasil), `tab_tags`, dan `tab_kamus` tanpa loop balik; self-echo ditekan saat ada debounce/pending aktif.
- **Upload Lokal -> DB:** Dialog konfirmasi menyediakan pilihan centang untuk meng-upload **Daftar Kata** (`whitelist.txt`/`blacklist.txt`) dan/atau **Pengaturan MODE** lokal ke database privat.
- **Degradasi Aman SQL Lama:** Jika `saka_settings` belum ada (`404`/`42501`), sinkronisasi kata `saka_words` tetap berjalan normal dan aplikasi mengingatkan user untuk menjalankan ulang **Salin SQL** terbaru.
- **Pengujian Tambahan (`test_db_sync.py`):** Mock test parsing event `saka_settings`, cache `mode_state`/`pending_mode_state`, fallback `404` pada `saka_settings`, serta isolasi state MODE `txt` ↔ `supabase`.

---

## 6. Ekstensi Desain: Indikasi Flash Aktivitas DB di Title Bar

### 6.1 State-Machine Visual (`QtCustomTitleBar` di `qt_components.py`)
- Tombol `btn_db_status` (`24x22 px`) menyimpan status dasar (`_db_state_code`, `_db_detail`).
- `flash_db_activity(kind: str)` hanya aktif saat `_db_state_code in ("live", "syncing", "connecting")`:
  - **`"remote"` (Update masuk dari teman):** `THEME["accent_cyan"]` (`#00f0ff`), bingkai `#00f0ff`, latar tint `#0b2830`.
  - **`"local"` (Perubahan kita sendiri):** `THEME["warning"]` (`#f59e0b`), bingkai `#f59e0b`, latar tint `#2b2009`.
- Menggunakan 1 `QTimer` (220 ms × 5 transisi): langkah `0, 2, 4` nyala terang; `1, 3` redup (`bg_card` / `border`); langkah `5` berhenti dan memanggil `_apply_db_status_visual()` untuk memulihkan tampilan dasar `DB LIVE`.

### 6.2 Pemicu Trigger & Prioritas Edge Cases (`app_qt.py`)
- **Trigger `"remote"`:** `_on_db_remote_event` (`not is_self`), `_on_db_remote_mode_event` (`not is_self`), dan `_on_db_snapshot_loaded` ketika `is_delta=True` (reconnect catch-up; tidak berkedip pada initial startup).
- **Trigger `"local"`:** `_on_solver_db_mutation` dan `_flush_local_mode_to_db`.
- **Edge Cases:** `set_db_status` untuk `"txt"`, `"offline"`, atau `"error"` langsung menghentikan timer flash; event beruntun me-reset step ke `0` pada timer tunggal tanpa menumpuk timer.
- **Pengujian (`test_db_sync.py`):** Uji *offscreen* pada `QtCustomTitleBar` untuk memastikan transisi flash `remote`/`local`, pemulihan status dasar, dan pembatalan flash saat `error`/`txt`.
