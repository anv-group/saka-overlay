import bisect
import csv
from datetime import datetime, timezone
import os
import re

class SambungKataSolver:
    def __init__(
        self,
        dictionary_path="kamus_lengkap.txt",
        blacklist_path="blacklist.csv",
        whitelist_path="whitelist.csv",
        kbbi_path="kamus_kbbi.txt",
        contek_path="kamus_contek.txt",
        custom_dict_path="kamus_custom.csv",
        use_kbbi=True,
        use_contek=True,
        storage_mode="txt",
        db_mutation_callback=None
    ):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.dictionary_path = os.path.join(base_dir, dictionary_path) if not os.path.isabs(dictionary_path) else dictionary_path
        self.blacklist_path = os.path.join(base_dir, blacklist_path) if not os.path.isabs(blacklist_path) else blacklist_path
        self.whitelist_path = os.path.join(base_dir, whitelist_path) if not os.path.isabs(whitelist_path) else whitelist_path
        self.kbbi_path = os.path.join(base_dir, kbbi_path) if not os.path.isabs(kbbi_path) else kbbi_path
        self.contek_path = os.path.join(base_dir, contek_path) if not os.path.isabs(contek_path) else contek_path
        self.custom_dict_path = os.path.join(base_dir, custom_dict_path) if not os.path.isabs(custom_dict_path) else custom_dict_path
        
        self.use_kbbi = use_kbbi
        self.use_contek = use_contek
        self.storage_mode = storage_mode if storage_mode in ("txt", "supabase") else "txt"
        self.db_mutation_callback = db_mutation_callback

        self.kbbi_set = set()
        self.contek_set = set()
        self.base_custom_set = set()
        self.legacy_custom_set = set()
        self.db_custom_set = set()
        self.custom_set = set()
        self.db_records = {}
        self.word_set = set()
        self.words = []
        self.blacklisted_words = set()
        self.whitelisted_words = set()
        self.whitelist_timestamps = {}
        self.blacklist_timestamps = {}
        self.custom_timestamps = {}
        self.words_by_initial = {}
        self.custom_endings = []
        self.tier0_sort_mode = "default"  # "default" atau "tag_order"

        if self.storage_mode == "txt":
            self._migrate_legacy_txt_to_csv()
            self.load_blacklist()
            self.load_whitelist()
        self.load_dictionary()

    @staticmethod
    def _utc_now_iso():
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _parse_iso_ts(ts_str):
        raw = str(ts_str or "").strip()
        if not raw:
            return None
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            return None

    def _read_word_csv(self, fpath, validate_vowels=False):
        """Membaca file CSV (word,datetime) atau baris kata tunggal legacy menjadi dict {word: datetime}."""
        items = {}
        if not fpath or not os.path.exists(fpath):
            return items
        vowels = set("aiueo")
        try:
            with open(fpath, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row:
                        continue
                    raw_w = str(row[0] or "").strip()
                    if not raw_w or raw_w.startswith("#"):
                        continue
                    w = raw_w.lower()
                    if w == "word" and len(row) >= 2 and str(row[1] or "").strip().lower() in ("datetime", "updated_at", "created_at"):
                        continue
                    if not w.isalpha() or len(w) < 2:
                        continue
                    if validate_vowels and not any(v in w for v in vowels):
                        continue
                    dt_str = str(row[1] or "").strip() if len(row) >= 2 else ""
                    if w not in items or (dt_str and not items[w]):
                        items[w] = dt_str
        except Exception as e:
            print(f"[!] Error membaca {fpath}: {e}")
        return items

    def _write_word_csv(self, fpath, word_ts_map):
        """Menulis {word: datetime} ke file CSV secara atomik."""
        folder = os.path.dirname(fpath)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        tmp_path = f"{fpath}.tmp"
        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["word", "datetime"])
            for w in sorted(word_ts_map.keys()):
                writer.writerow([w, word_ts_map.get(w, "") or ""])
        os.replace(tmp_path, fpath)

    def _migrate_pair_txt_to_csv(self, csv_path, validate_vowels=False):
        """Migrasi 1 file .txt saudara menjadi .csv (datetime='') lalu menghapus .txt lama."""
        if not csv_path or not csv_path.lower().endswith(".csv"):
            return
        legacy_txt = csv_path[:-4] + ".txt"
        if not os.path.exists(legacy_txt):
            return
        legacy_items = self._read_word_csv(legacy_txt, validate_vowels=validate_vowels)
        csv_items = self._read_word_csv(csv_path, validate_vowels=validate_vowels) if os.path.exists(csv_path) else {}
        merged = dict(csv_items)
        for w, dt_str in legacy_items.items():
            if w not in merged:
                merged[w] = dt_str
        self._write_word_csv(csv_path, merged)
        try:
            os.remove(legacy_txt)
        except Exception as e:
            print(f"[!] Gagal menghapus file lama {legacy_txt}: {e}")

    def _migrate_legacy_txt_to_csv(self):
        """Migrasi otomatis whitelist.txt & blacklist.txt ke .csv lalu hapus file .txt lama."""
        self._migrate_pair_txt_to_csv(self.whitelist_path, validate_vowels=False)
        self._migrate_pair_txt_to_csv(self.blacklist_path, validate_vowels=False)

    def load_blacklist(self):
        """Memuat daftar kata yang di-blacklist dari blacklist.csv"""
        items = self._read_word_csv(self.blacklist_path, validate_vowels=False)
        self.blacklisted_words = set(items.keys())
        self.blacklist_timestamps = dict(items)
        print(f"[*] Blacklist dimuat: {len(self.blacklisted_words)} kata diblokir.")

    def _emit_db_mutation(self, action, word, record=None):
        if self.storage_mode == "supabase" and callable(self.db_mutation_callback):
            self.db_mutation_callback(action, word, record)

    def _is_in_base_dictionary(self, w):
        return (w in self.legacy_custom_set) or (w in self.kbbi_set) or (w in self.contek_set)

    def get_word_datetime(self, word, scope="auto"):
        """Mengembalikan ISO-8601 timestamp aktivitas terakhir kata sesuai mode penyimpanan."""
        w = (word or "").strip().lower()
        if not w:
            return ""
        if self.storage_mode == "supabase":
            rec = self.db_records.get(w)
            if isinstance(rec, dict):
                return str(rec.get("updated_at") or "").strip()
            return ""
        if scope == "whitelist":
            return str(self.whitelist_timestamps.get(w, "") or "")
        if scope == "blacklist":
            return str(self.blacklist_timestamps.get(w, "") or "")
        if scope == "custom":
            return str(self.custom_timestamps.get(w, "") or "")
        return str(
            self.whitelist_timestamps.get(w)
            or self.blacklist_timestamps.get(w)
            or self.custom_timestamps.get(w)
            or ""
        )

    def _add_word_to_active_memory(self, w):
        if not w or w in self.word_set:
            return
        self.word_set.add(w)
        bisect.insort(self.words, w)
        init1 = w[0]
        if init1 not in self.words_by_initial:
            self.words_by_initial[init1] = [w]
        else:
            bisect.insort(self.words_by_initial[init1], w)

    def _should_stay_in_active_memory(self, w):
        if self.use_kbbi and w in self.kbbi_set:
            return True
        if self.use_contek and w in self.contek_set:
            return True
        if w in self.custom_set or w in self.whitelisted_words:
            return True
        return False

    def _remove_word_from_active_memory_if_unused(self, w):
        if w in self.word_set and not self._should_stay_in_active_memory(w):
            self.word_set.discard(w)
            idx = bisect.bisect_left(self.words, w)
            if idx < len(self.words) and self.words[idx] == w:
                self.words.pop(idx)
            init1 = w[0] if w else ""
            bucket = self.words_by_initial.get(init1)
            if bucket:
                bidx = bisect.bisect_left(bucket, w)
                if bidx < len(bucket) and bucket[bidx] == w:
                    bucket.pop(bidx)

    def blacklist_word(self, word):
        """Memasukkan kata ke blacklist dan menyimpannya (ke blacklist.csv atau Database). Duplikat ditolak."""
        w = word.strip().lower()
        if not w:
            return False

        if w in self.blacklisted_words:
            return False

        now_iso = self._utc_now_iso()

        if self.storage_mode == "supabase":
            self.whitelisted_words.discard(w)
            self.whitelist_timestamps.pop(w, None)
            is_custom = bool(self.db_records.get(w, {}).get("is_custom", False) or (w in self.db_custom_set))
            self.blacklisted_words.add(w)
            self.blacklist_timestamps[w] = now_iso
            rec = {"word": w, "status": "blocklist", "is_custom": is_custom, "updated_at": now_iso}
            self.db_records[w] = rec
            if not is_custom:
                self._remove_word_from_active_memory_if_unused(w)
            self._emit_db_mutation("upsert", w, rec)
            return True

        if w in self.whitelisted_words:
            self.unwhitelist_word(w)

        self.blacklisted_words.add(w)
        self.blacklist_timestamps[w] = now_iso
        try:
            self._write_word_csv(self.blacklist_path, self.blacklist_timestamps)
            return True
        except Exception as e:
            print(f"[!] Gagal menulis ke {self.blacklist_path}: {e}")
            return False

    def unblacklist_word(self, word):
        """Menghapus kata dari blacklist (Undo)"""
        w = word.strip().lower()
        if self.storage_mode == "supabase":
            self.blacklisted_words.discard(w)
            self.blacklist_timestamps.pop(w, None)
            prev = self.db_records.get(w, {})
            is_custom = bool(prev.get("is_custom", False) or (w in self.db_custom_set))
            if is_custom:
                now_iso = self._utc_now_iso()
                rec = {"word": w, "status": "custom", "is_custom": True, "updated_at": now_iso}
                self.db_records[w] = rec
                self.db_custom_set.add(w)
                self.custom_set.add(w)
                self.custom_timestamps[w] = now_iso
                self._add_word_to_active_memory(w)
                self._emit_db_mutation("upsert", w, rec)
            else:
                self.db_records.pop(w, None)
                self._remove_word_from_active_memory_if_unused(w)
                self._emit_db_mutation("delete", w, None)
            return True

        if w in self.blacklisted_words:
            self.blacklisted_words.remove(w)
        self.blacklist_timestamps.pop(w, None)
        try:
            self._write_word_csv(self.blacklist_path, self.blacklist_timestamps)
            return True
        except Exception as e:
            print(f"[!] Gagal memperbarui {self.blacklist_path}: {e}")
            return False

    def get_blacklisted_words(self):
        """Mengembalikan daftar kata yang di-blacklist terurut abjad"""
        return sorted(list(self.blacklisted_words))

    def load_whitelist(self):
        """Memuat daftar kata terverifikasi dari whitelist.csv"""
        items = self._read_word_csv(self.whitelist_path, validate_vowels=False)
        self.whitelisted_words = set(items.keys())
        self.whitelist_timestamps = dict(items)
        print(f"[*] Whitelist dimuat: {len(self.whitelisted_words)} kata terverifikasi.")

    def whitelist_word(self, word):
        """
        Memasukkan kata ke whitelist dan menyimpannya (ke whitelist.csv atau Database):
        - Jika sudah di whitelist, ditolak (return False) agar timestamp tidak tertimpa.
        - Jika kata ada di blacklist, otomatis dihapus dari blacklist.
        - Jika kata belum ada di kamus dasar, di mode lokal ditambahkan ke kamus_custom.csv;
          di mode Database ditandai is_custom=True di database privat.
        - Kata langsung aktif di memori pencarian solver O(1) dan menjadi prioritas teratas di kategorinya.
        """
        w = word.strip().lower()
        if not w or not w.isalpha() or len(w) < 2:
            return False

        if w in self.whitelisted_words:
            return False

        now_iso = self._utc_now_iso()

        if self.storage_mode == "supabase":
            self.blacklisted_words.discard(w)
            self.blacklist_timestamps.pop(w, None)
            self.whitelisted_words.add(w)
            self.whitelist_timestamps[w] = now_iso
            prev = self.db_records.get(w, {})
            is_custom = bool(prev.get("is_custom", False) or (w in self.db_custom_set) or not self._is_in_base_dictionary(w))
            if is_custom:
                self.db_custom_set.add(w)
                self.custom_set.add(w)
                self.custom_timestamps[w] = now_iso
            self._add_word_to_active_memory(w)
            rec = {"word": w, "status": "whitelist", "is_custom": is_custom, "updated_at": now_iso}
            self.db_records[w] = rec
            self._emit_db_mutation("upsert", w, rec)
            return True

        # Jika ada di blacklist, pulihkan
        if w in self.blacklisted_words:
            self.unblacklist_word(w)

        self.whitelisted_words.add(w)
        self.whitelist_timestamps[w] = now_iso
        try:
            self._write_word_csv(self.whitelist_path, self.whitelist_timestamps)
        except Exception as e:
            print(f"[!] Gagal menulis ke {self.whitelist_path}: {e}")
            return False

        # Jika belum ada di kamus (kamus_lengkap / KBBI / Contek / custom), tambahkan ke kamus_custom.csv
        if w not in self.custom_set and w not in self.kbbi_set and w not in self.contek_set:
            self.base_custom_set.add(w)
            self.custom_set.add(w)
            self.custom_timestamps[w] = now_iso
            if self.custom_dict_path:
                try:
                    self._write_word_csv(self.custom_dict_path, self.custom_timestamps)
                except Exception as e:
                    print(f"[!] Gagal menulis kata whitelist ke {self.custom_dict_path}: {e}")

        # Pastikan kata juga langsung hidup di memori aktif solver
        self._add_word_to_active_memory(w)

        return True

    def unwhitelist_word(self, word):
        """Menghapus kata dari whitelist"""
        w = word.strip().lower()
        if self.storage_mode == "supabase":
            self.whitelisted_words.discard(w)
            self.whitelist_timestamps.pop(w, None)
            prev = self.db_records.get(w, {})
            is_custom = bool(prev.get("is_custom", False) or (w in self.db_custom_set))
            if is_custom:
                now_iso = self._utc_now_iso()
                rec = {"word": w, "status": "custom", "is_custom": True, "updated_at": now_iso}
                self.db_records[w] = rec
                self.db_custom_set.add(w)
                self.custom_set.add(w)
                self.custom_timestamps[w] = now_iso
                self._emit_db_mutation("upsert", w, rec)
            else:
                self.db_records.pop(w, None)
                self._remove_word_from_active_memory_if_unused(w)
                self._emit_db_mutation("delete", w, None)
            return True

        if w in self.whitelisted_words:
            self.whitelisted_words.remove(w)
        self.whitelist_timestamps.pop(w, None)
        try:
            self._write_word_csv(self.whitelist_path, self.whitelist_timestamps)
            # Jika kata tidak ada di kamus asal (bukan bagian kbbi/contek/custom), hapus dari memori aktif
            self._remove_word_from_active_memory_if_unused(w)
            return True
        except Exception as e:
            print(f"[!] Gagal memperbarui {self.whitelist_path}: {e}")
            return False

    def is_whitelisted(self, word):
        """Mengecek apakah kata ada di whitelist"""
        return word.strip().lower() in self.whitelisted_words

    def get_whitelisted_words(self):
        """Mengembalikan daftar kata whitelist terurut abjad"""
        return sorted(list(self.whitelisted_words))

    def _read_word_file(self, fpath):
        """Membaca file kata dan menyaring kata yang valid (alpha, min 2 huruf, punya vokal)"""
        words = set()
        if not os.path.exists(fpath):
            return words
        vowels = set("aiueo")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    w = line.strip().lower()
                    if w.isalpha() and len(w) >= 2 and any(v in w for v in vowels):
                        words.add(w)
        except Exception as e:
            print(f"[!] Gagal membaca {fpath}: {e}")
        return words

    def load_dictionary(self):
        """Memuat kosakata dari KBBI dan Contek Sambung Kata ke memori"""
        # 1. Muat KBBI
        if os.path.exists(self.kbbi_path):
            self.kbbi_set = self._read_word_file(self.kbbi_path)
        else:
            # Fallback ke kata_kbbi.txt jika kamus_kbbi.txt belum dibuat
            alt_kbbi = os.path.join(os.path.dirname(self.kbbi_path), "kata_kbbi.txt")
            if os.path.exists(alt_kbbi):
                self.kbbi_set = self._read_word_file(alt_kbbi)

        # 2. Muat Contek Sambung Kata
        if os.path.exists(self.contek_path):
            self.contek_set = self._read_word_file(self.contek_path)

        # 3. Muat kata custom / warisan dari kamus_lengkap.txt (read-only) + kamus_custom.csv
        if os.path.exists(self.dictionary_path):
            lengkap_set = self._read_word_file(self.dictionary_path)
            # Kata yang ada di kamus_lengkap tapi tidak ada di kbbi/contek dianggap custom warisan
            self.legacy_custom_set = lengkap_set - (self.kbbi_set | self.contek_set)
        else:
            self.legacy_custom_set = set()

        custom_csv_items = self._read_word_csv(self.custom_dict_path, validate_vowels=True)
        self.custom_timestamps = dict(custom_csv_items)
        self.base_custom_set = self.legacy_custom_set | set(custom_csv_items.keys())

        self.custom_set = self.base_custom_set | self.db_custom_set
        self._rebuild_active_words()
        print(f"[*] Solver siap: KBBI={len(self.kbbi_set)}, Contek={len(self.contek_set)}, Total Aktif={len(self.words)} kata.")

    def _compute_active_word_set(self):
        active = set()
        if self.use_kbbi:
            active.update(self.kbbi_set)
        if self.use_contek:
            active.update(self.contek_set)
        active.update(self.custom_set)
        active.update(self.whitelisted_words)

        if not active:
            if self.kbbi_set:
                self.use_kbbi = True
                active.update(self.kbbi_set)
            elif self.contek_set:
                self.use_contek = True
                active.update(self.contek_set)
        return active

    def _rebuild_active_words(self):
        """Membangun ulang daftar kata aktif sesuai sumber kamus yang dipilih"""
        active = self._compute_active_word_set()
        self.word_set = active
        self.words = sorted(list(self.word_set))
        self._index_words()

    def switch_storage_mode(self, mode, db_records=None):
        """Berpindah secara instan antara Mode File Lokal (CSV) dan Mode Database tanpa restart."""
        target = mode if mode in ("txt", "supabase") else "txt"
        self.storage_mode = target
        if target == "txt":
            self.db_records = {}
            self.db_custom_set = set()
            self._migrate_legacy_txt_to_csv()
            self.load_blacklist()
            self.load_whitelist()
            custom_csv_items = self._read_word_csv(self.custom_dict_path, validate_vowels=True)
            self.custom_timestamps = dict(custom_csv_items)
            self.base_custom_set = self.legacy_custom_set | set(custom_csv_items.keys())
            self.custom_set = set(self.base_custom_set)
            if self._compute_active_word_set() != self.word_set:
                self._rebuild_active_words()
        else:
            self.apply_db_snapshot(db_records or {})

    def apply_db_snapshot(self, records_dict):
        """Menerapkan snapshot penuh dari database/cache ke memori solver secara efisien."""
        self.db_records = {}
        new_wl = set()
        new_bl = set()
        new_db_custom = set()
        new_wl_ts = {}
        new_bl_ts = {}
        new_custom_ts = {}

        for raw_w, rec in (records_dict or {}).items():
            if not isinstance(rec, dict):
                continue
            w = str(rec.get("word") or raw_w or "").strip().lower()
            if not w or not w.isalpha() or len(w) < 2:
                continue
            st = str(rec.get("status") or "custom").strip().lower()
            is_c = bool(rec.get("is_custom", False))
            upd = str(rec.get("updated_at") or "").strip()
            clean_rec = {
                "word": w,
                "status": st,
                "is_custom": is_c,
                "added_by": str(rec.get("added_by") or ""),
                "updated_at": upd,
            }
            self.db_records[w] = clean_rec
            if st == "whitelist":
                new_wl.add(w)
                new_wl_ts[w] = upd
                if is_c:
                    new_db_custom.add(w)
                    new_custom_ts[w] = upd
            elif st == "blocklist":
                new_bl.add(w)
                new_bl_ts[w] = upd
                if is_c:
                    new_db_custom.add(w)
                    new_custom_ts[w] = upd
            else:
                new_db_custom.add(w)
                new_custom_ts[w] = upd

        self.whitelisted_words = new_wl
        self.blacklisted_words = new_bl
        self.whitelist_timestamps = new_wl_ts
        self.blacklist_timestamps = new_bl_ts
        self.custom_timestamps = new_custom_ts
        self.db_custom_set = new_db_custom
        self.custom_set = self.base_custom_set | self.db_custom_set

        if self._compute_active_word_set() != self.word_set:
            self._rebuild_active_words()

    def apply_db_event(self, event_type, record=None, old_record=None):
        """Menerapkan event Realtime (INSERT/UPDATE/DELETE) ke memori solver dalam O(1)/O(log N)."""
        ev = str(event_type or "").upper()
        if ev in ("INSERT", "UPDATE") and isinstance(record, dict):
            w = str(record.get("word") or "").strip().lower()
            if not w or not w.isalpha() or len(w) < 2:
                return ""
            st = str(record.get("status") or "custom").strip().lower()
            is_c = bool(record.get("is_custom", False))
            upd = str(record.get("updated_at") or "").strip()
            self.db_records[w] = {
                "word": w,
                "status": st,
                "is_custom": is_c,
                "added_by": str(record.get("added_by") or ""),
                "updated_at": upd,
            }
            if is_c:
                self.db_custom_set.add(w)
                self.custom_set.add(w)
                self.custom_timestamps[w] = upd
            else:
                self.db_custom_set.discard(w)
                self.custom_timestamps.pop(w, None)
                if w not in self.base_custom_set:
                    self.custom_set.discard(w)

            if st == "whitelist":
                self.blacklisted_words.discard(w)
                self.blacklist_timestamps.pop(w, None)
                self.whitelisted_words.add(w)
                self.whitelist_timestamps[w] = upd
                self._add_word_to_active_memory(w)
            elif st == "blocklist":
                self.whitelisted_words.discard(w)
                self.whitelist_timestamps.pop(w, None)
                self.blacklisted_words.add(w)
                self.blacklist_timestamps[w] = upd
                if not is_c:
                    self._remove_word_from_active_memory_if_unused(w)
                else:
                    self._add_word_to_active_memory(w)
            else:
                self.whitelisted_words.discard(w)
                self.whitelist_timestamps.pop(w, None)
                self.blacklisted_words.discard(w)
                self.blacklist_timestamps.pop(w, None)
                self.db_custom_set.add(w)
                self.custom_set.add(w)
                self.custom_timestamps[w] = upd
                self._add_word_to_active_memory(w)
            return w

        if ev == "DELETE":
            src = old_record if isinstance(old_record, dict) and old_record.get("word") else record
            w = str((src or {}).get("word") or "").strip().lower()
            if not w:
                return ""
            self.db_records.pop(w, None)
            self.whitelisted_words.discard(w)
            self.whitelist_timestamps.pop(w, None)
            self.blacklisted_words.discard(w)
            self.blacklist_timestamps.pop(w, None)
            self.db_custom_set.discard(w)
            self.custom_timestamps.pop(w, None)
            if w not in self.base_custom_set:
                self.custom_set.discard(w)
            self._remove_word_from_active_memory_if_unused(w)
            return w
        return ""

    def export_txt_records_for_import(self, added_by=""):
        """Membaca whitelist.csv, blacklist.csv & kamus_custom.csv lokal menjadi daftar record siap import ke Supabase."""
        records_map = {}
        custom_items = self._read_word_csv(self.custom_dict_path, validate_vowels=True)
        for w, dt_str in custom_items.items():
            rec = {
                "word": w,
                "status": "custom",
                "is_custom": True,
                "added_by": added_by,
            }
            if dt_str:
                rec["updated_at"] = dt_str
            records_map[w] = rec

        bl_items = self._read_word_csv(self.blacklist_path, validate_vowels=False)
        for w, dt_str in bl_items.items():
            is_c = (w in custom_items) or (not self._is_in_base_dictionary(w))
            rec = {
                "word": w,
                "status": "blocklist",
                "is_custom": is_c,
                "added_by": added_by,
            }
            if dt_str:
                rec["updated_at"] = dt_str
            records_map[w] = rec

        wl_items = self._read_word_csv(self.whitelist_path, validate_vowels=False)
        for w, dt_str in wl_items.items():
            is_c = (w in custom_items) or (not self._is_in_base_dictionary(w))
            rec = {
                "word": w,
                "status": "whitelist",
                "is_custom": is_c,
                "added_by": added_by,
            }
            if dt_str:
                rec["updated_at"] = dt_str
            records_map[w] = rec

        return list(records_map.values())

    def apply_db_records_to_txt_files(self, records: dict, overwrite_lists: bool = False):
        """
        Menyimpan daftar kata dari Database Privat ke file CSV lokal:
        - whitelist.csv & blacklist.csv (gabung atau timpa penuh, mempertahankan updated_at)
        - kata tambahan (is_custom / status='custom') ke kamus_custom.csv jika belum ada di kamus dasar read-only.
        Mengembalikan (jumlah_wl, jumlah_bl, jumlah_kata_custom_baru).
        """
        wl_map = {} if overwrite_lists else self._read_word_csv(self.whitelist_path, validate_vowels=False)
        bl_map = {} if overwrite_lists else self._read_word_csv(self.blacklist_path, validate_vowels=False)
        custom_map = self._read_word_csv(self.custom_dict_path, validate_vowels=True)

        existing_base = set(self.kbbi_set) | set(self.contek_set) | set(self.legacy_custom_set)
        vowels = set("aiueo")
        new_custom_words = []

        for raw_w, rec in (records or {}).items():
            if not isinstance(rec, dict):
                continue
            w = str(rec.get("word") or raw_w or "").strip().lower()
            if not w or not w.isalpha() or len(w) < 2:
                continue
            st = str(rec.get("status") or "custom").strip().lower()
            is_c = bool(rec.get("is_custom", False))
            upd = str(rec.get("updated_at") or "").strip()

            if st == "whitelist":
                bl_map.pop(w, None)
                wl_map[w] = upd or wl_map.get(w, "")
            elif st == "blocklist":
                wl_map.pop(w, None)
                bl_map[w] = upd or bl_map.get(w, "")

            if (is_c or st == "custom") and w not in existing_base:
                if any(v in w for v in vowels):
                    if w not in custom_map:
                        custom_map[w] = upd
                        new_custom_words.append(w)
                    elif upd and not custom_map[w]:
                        custom_map[w] = upd

        self._write_word_csv(self.whitelist_path, wl_map)
        self._write_word_csv(self.blacklist_path, bl_map)
        if custom_map or os.path.exists(self.custom_dict_path):
            self._write_word_csv(self.custom_dict_path, custom_map)

        if self.storage_mode == "txt":
            self.load_blacklist()
            self.load_whitelist()
            self.load_dictionary()

        return len(wl_map), len(bl_map), len(new_custom_words)

    def set_dict_sources(self, use_kbbi=True, use_contek=True):
        """
        Mengubah sumber kamus yang aktif (KBBI, Contek, atau keduanya).
        Menghasilkan pembaruan indeks instan di memori.
        """
        if not use_kbbi and not use_contek:
            # Cegah kedua sumber nonaktif bersamaan
            return False, len(self.words), "Minimal satu sumber kamus harus dipilih!"
        
        self.use_kbbi = bool(use_kbbi)
        self.use_contek = bool(use_contek)
        self._rebuild_active_words()
        return True, len(self.words), f"Kamus aktif diperbarui ({len(self.words):,} kata)."

    def has_word(self, word):
        """Memeriksa apakah kata sudah terdaftar di kamus aktif"""
        return word.strip().lower() in self.word_set

    def add_word(self, word):
        """
        Menambahkan kata baru ke kamus custom (kamus_custom.csv atau Database) secara manual:
        - Validasi: huruf alfabet murni, panjang >= 2, wajib memiliki minimal 1 vokal.
        - Mengecek apakah kata sudah ada di kamus aktif (duplikat ditolak).
        - Jika ada di blacklist, otomatis dihapus dari blacklist.
        - Tidak mengubah file kamus dasar (kamus_lengkap.txt, kamus_kbbi.txt, kamus_contek.txt).
        - Mengindeks kata ke memori solver.
        """
        w = word.strip().lower()
        if not w.isalpha() or len(w) < 2:
            return False, "Kata harus berupa huruf alfabet murni (minimal 2 huruf)."
        
        vowels = set("aiueo")
        if not any(v in w for v in vowels):
            return False, "Kata harus memiliki minimal satu huruf vokal (A, I, U, E, O)."

        if w in self.word_set:
            return False, f"Kata '{w.upper()}' sudah terdaftar di dalam kamus."

        now_iso = self._utc_now_iso()

        # Jika sebelumnya ada di blacklist, pulihkan dari blacklist
        if w in self.blacklisted_words:
            if self.storage_mode == "supabase":
                self.blacklisted_words.discard(w)
                self.blacklist_timestamps.pop(w, None)
            else:
                self.unblacklist_word(w)

        if self.storage_mode == "supabase":
            self.db_custom_set.add(w)
            self.custom_set.add(w)
            self.custom_timestamps[w] = now_iso
            self._add_word_to_active_memory(w)
            rec = {"word": w, "status": "custom", "is_custom": True, "updated_at": now_iso}
            self.db_records[w] = rec
            self._emit_db_mutation("upsert", w, rec)
            return True, f"Kata '{w.upper()}' berhasil ditambahkan ke Database Kamus!"

        # Tambahkan ke memori (tanpa mengubah kamus_contek.txt / kamus_lengkap.txt)
        self.base_custom_set.add(w)
        self.custom_set.add(w)
        self.custom_timestamps[w] = now_iso
        self._add_word_to_active_memory(w)

        # Simpan persisten ke kamus_custom.csv
        try:
            self._write_word_csv(self.custom_dict_path, self.custom_timestamps)
            return True, f"Kata '{w.upper()}' berhasil ditambahkan ke kamus!"
        except Exception as e:
            return False, f"Gagal menulis ke file kamus custom: {e}"

    def is_deletable_custom_word(self, word):
        """Mengembalikan True hanya jika kata berasal dari kamus custom (bukan kamus dasar)."""
        w = (word or "").strip().lower()
        if not w or self._is_in_base_dictionary(w):
            return False
        if self.storage_mode == "supabase":
            return w in self.db_custom_set
        return w in self.custom_timestamps

    def delete_custom_word(self, word):
        """Menghapus kata custom dari kamus_custom.csv atau Database (tidak menyentuh KBBI/Contek)."""
        w = (word or "").strip().lower()
        if not w:
            return False, "Kata kosong."
        if not self.is_deletable_custom_word(w):
            return False, f"Kata '{w.upper()}' bukan bagian dari kamus custom."

        if self.storage_mode == "supabase":
            self.db_records.pop(w, None)
            self.db_custom_set.discard(w)
            self.custom_set.discard(w)
            self.custom_timestamps.pop(w, None)
            self.whitelisted_words.discard(w)
            self.whitelist_timestamps.pop(w, None)
            self.blacklisted_words.discard(w)
            self.blacklist_timestamps.pop(w, None)
            self._remove_word_from_active_memory_if_unused(w)
            self._emit_db_mutation("delete", w, None)
            return True, f"Kata '{w.upper()}' berhasil dihapus dari kamus custom."

        self.custom_timestamps.pop(w, None)
        self.base_custom_set.discard(w)
        self.custom_set.discard(w)
        try:
            self._write_word_csv(self.custom_dict_path, self.custom_timestamps)
        except Exception as e:
            return False, f"Gagal memperbarui file kamus custom: {e}"

        if w in self.whitelisted_words:
            self.whitelisted_words.discard(w)
            self.whitelist_timestamps.pop(w, None)
            try:
                self._write_word_csv(self.whitelist_path, self.whitelist_timestamps)
            except Exception as e:
                print(f"[!] Gagal memperbarui {self.whitelist_path}: {e}")

        if w in self.blacklisted_words:
            self.blacklisted_words.discard(w)
            self.blacklist_timestamps.pop(w, None)
            try:
                self._write_word_csv(self.blacklist_path, self.blacklist_timestamps)
            except Exception as e:
                print(f"[!] Gagal memperbarui {self.blacklist_path}: {e}")

        self._remove_word_from_active_memory_if_unused(w)
        return True, f"Kata '{w.upper()}' berhasil dihapus dari kamus custom."

    def _index_words(self):
        """Mengindeks kata berdasarkan 1 huruf pertama untuk pencarian instan O(1)"""
        self.words_by_initial = {}
        for w in self.words:
            init1 = w[0]
            if init1 not in self.words_by_initial:
                self.words_by_initial[init1] = []
            self.words_by_initial[init1].append(w)

    @staticmethod
    def _clean_tag_name(name, suffix):
        sfx = (suffix or "").strip().upper()
        cleaned = re.sub(r"(?i)^akhiran\s+", "", str(name or "")).strip()
        return cleaned or sfx

    def set_custom_endings(self, custom_endings):
        """
        Mengatur daftar akhiran kustom (Custom Traps) sebagai satu-satunya sistem tag prioritas.
        Format:
        [
            {"suffix": "NS", "name": "NS", "enabled": True, "color": "#cba6f7"},
            {"suffix": "NGK", "name": "NGK", "enabled": True, "color": "#f5c2e7"}
        ]
        atau list of string: ["NS", "NGK"]
        """
        self.custom_endings = []
        if not custom_endings:
            return
        seen_suffixes = set()
        for item in custom_endings:
            if isinstance(item, str):
                s = item.strip().lower()
                if s and s not in seen_suffixes:
                    seen_suffixes.add(s)
                    self.custom_endings.append({
                        "suffix": s,
                        "name": s.upper(),
                        "enabled": True,
                        "color": "#cba6f7"
                    })
            elif isinstance(item, dict):
                s = item.get("suffix", "").strip().lower()
                if s and s not in seen_suffixes:
                    seen_suffixes.add(s)
                    self.custom_endings.append({
                        "suffix": s,
                        "name": self._clean_tag_name(item.get("name"), s),
                        "enabled": bool(item.get("enabled", True)),
                        "color": item.get("color", "#cba6f7")
                    })

    def set_tier0_sort_mode(self, mode):
        """
        Mengatur mode pengurutan kata pada Tier 0 (Custom Traps):
        - 'default': Mengurutkan berdasarkan panjang ideal (4-7, 3, 8, >8) lalu urutan abjad kamus.
        - 'tag_order': Mengurutkan berdasarkan urutan daftar tag kustom (tag teratas lebih dulu).
        """
        if mode in ("default", "tag_order"):
            self.tier0_sort_mode = mode
            return True
        return False

    def count_words_by_suffix(self, suffix):
        """Menghitung berapa banyak kata di kamus aktif yang berakhiran suffix tertentu"""
        s = suffix.strip().lower()
        if not s:
            return 0
        return sum(1 for w in self.words if w.endswith(s) and w not in self.blacklisted_words)

    def cari_jawaban(self, awalan_prefix, limit=100, mode_santai=False, custom_endings=None, sort_mode=None, mode_brutal=False):
        """
        Mencari kata yang DIAWALI oleh `awalan_prefix`:
        Contoh:
        - Jika prefix 'BUK' -> mencari kata berawalan 'buk' (buka, bukan, bukti, bukit, dll)
        - Jika prefix 'M'   -> mencari kata berawalan 'm'
        - Jika prefix 'EX'  -> mencari kata berawalan 'ex' (exit, extra, expert, dll)
        - Jika prefix 'IX'  -> mencari kata berawalan 'ix' (ixora, ixodes, dll)
        
        Prioritas Jawaban (Pure Custom Tags):
        0. Kata berakhiran Kategori Custom / Custom Traps (misal NS, NGK, X, dll.)
        1. Kata normal/santai/brutal sesuai mode (BIASA)
        """
        prefix = "".join([c for c in awalan_prefix.lower() if c.isalpha()])
        if not prefix:
            return []

        # Ambil kandidat dari index 1 huruf pertama
        initial = prefix[0]
        pool = self.words_by_initial.get(initial, [])
        if not pool:
            return []

        # Filter kata yang diawali oleh prefix dan tidak ada di blacklist
        candidates = [w for w in pool if w.startswith(prefix) and w not in self.blacklisted_words]

        # Jika prefix lebih pendek dari 3 huruf, hindari kata yang sama persis dengan prefix
        if len(prefix) <= 2:
            candidates = [w for w in candidates if len(w) > len(prefix)]

        if not candidates:
            return []

        # Mode sortir Tier 0 (default atau tag_order)
        effective_sort_mode = sort_mode if sort_mode is not None else getattr(self, "tier0_sort_mode", "default")

        # Aturan akhiran kustom yang aktif
        custom_rules = custom_endings if custom_endings is not None else self.custom_endings
        active_custom = []
        if custom_rules:
            for idx, c in enumerate(custom_rules):
                if isinstance(c, dict) and c.get("enabled", True):
                    r = dict(c)
                    r["tag_index"] = idx
                    r["suffix"] = r.get("suffix", "").lower()
                    if r["suffix"]:
                        # Di Mode Santai: Abaikan custom tag yang mengandung huruf X, Q, atau F
                        if mode_santai and any(ch in r["suffix"] for ch in ("x", "q", "f")):
                            continue
                        active_custom.append(r)
                elif isinstance(c, str) and c.strip():
                    s = c.strip().lower()
                    if mode_santai and any(ch in s for ch in ("x", "q", "f")):
                        continue
                    active_custom.append({
                        "suffix": s,
                        "name": s.upper(),
                        "enabled": True,
                        "color": "#cba6f7",
                        "tag_index": idx
                    })

        # Urutan pencocokan aturan custom
        if effective_sort_mode == "default":
            # Pada mode default, utamakan suffix terpanjang (misal NGK sebelum GK)
            match_rules = sorted(active_custom, key=lambda c: len(c.get("suffix", "")), reverse=True)
        else:
            # Pada mode tag_order, utamakan tag dengan posisi teratas (tag_index lebih kecil)
            match_rules = sorted(active_custom, key=lambda c: (c.get("tag_index", 0), -len(c.get("suffix", ""))))

        vowels = set("aiueo")
        jebakan_custom = []
        kata_biasa = []

        if mode_santai:
            # Mode Santai: Kecualikan X, Q, dan F
            for w in candidates:
                if not any(v in w for v in vowels):
                    continue
                if w[-1] in ("x", "q", "f") or "x" in w or "q" in w:
                    continue

                matched_rule = None
                for rule in match_rules:
                    sfx = rule.get("suffix", "").lower()
                    if sfx and w.endswith(sfx):
                        matched_rule = rule
                        break

                if matched_rule:
                    jebakan_custom.append((w, matched_rule))
                else:
                    kata_biasa.append(w)
        else:
            # Mode Normal / Brutal (Pure Custom Tags)
            for w in candidates:
                if len(w) >= 4 and not any(v in w for v in vowels):
                    continue

                matched_rule = None
                for rule in match_rules:
                    sfx = rule.get("suffix", "").lower()
                    if sfx and w.endswith(sfx):
                        matched_rule = rule
                        break

                if matched_rule:
                    jebakan_custom.append((w, matched_rule))
                else:
                    kata_biasa.append(w)

        # Urutkan kata per tier
        def sort_key(w):
            is_wl = 0 if w in self.whitelisted_words else 1
            l = len(w)
            if 4 <= l <= 7:
                prio = 0
            elif l == 3:
                prio = 1
            elif l == 8:
                prio = 2
            else:
                prio = 3
            return (is_wl, prio, l)

        if effective_sort_mode == "tag_order":
            def sort_key_custom(item):
                w, rule = item
                is_wl = 0 if w in self.whitelisted_words else 1
                tag_prio = rule.get("tag_index", 0)
                l = len(w)
                if 4 <= l <= 7:
                    prio = 0
                elif l == 3:
                    prio = 1
                elif l == 8:
                    prio = 2
                else:
                    prio = 3
                return (tag_prio, is_wl, prio, l)
            jebakan_custom.sort(key=sort_key_custom)
        else:
            # Mode Default: Urutkan berdasarkan Whitelist -> Panjang 4-7, 3, 8, >8 -> Urutan Abjad Kamus (Stable Sort)
            def sort_key_custom(item):
                w, rule = item
                is_wl = 0 if w in self.whitelisted_words else 1
                l = len(w)
                if 4 <= l <= 7:
                    prio = 0
                elif l == 3:
                    prio = 1
                elif l == 8:
                    prio = 2
                else:
                    prio = 3
                return (is_wl, prio, l)
            jebakan_custom.sort(key=sort_key_custom)
        kata_biasa.sort(key=sort_key)

        hasil = []

        list_custom = []
        for w, rule in jebakan_custom:
            sfx = rule["suffix"].upper()
            b_name = self._clean_tag_name(rule.get("name"), sfx)
            list_custom.append({
                "kata": w,
                "tipe": "CUSTOM_TRAP",
                "suffix": sfx,
                "badge_name": b_name,
                "color": rule.get("color", "#cba6f7"),
                "deskripsi": b_name,
                "is_whitelisted": (w in self.whitelisted_words)
            })

        list_biasa = []
        for w in kata_biasa:
            if mode_brutal:
                desc = "Kata Brutal"
            elif mode_santai:
                desc = "Kata Santai"
            else:
                desc = "Kata Normal"
            list_biasa.append({
                "kata": w,
                "tipe": "BIASA",
                "deskripsi": desc,
                "is_whitelisted": (w in self.whitelisted_words)
            })

        # TIER 0: Pure Custom Traps
        hasil.extend(list_custom)

        # TIER 1: Kata Biasa (Normal / Santai / Brutal)
        hasil.extend(list_biasa)

        return hasil[:limit]


    def search_dictionary(
        self,
        query="",
        search_type="prefix",
        selected_tags=None,
        min_len=0,
        max_len=999,
        source_filter="all",
        limit=None,
        sort_by="default"
    ):
        """
        Mencari kata di seluruh kosakata aktif berdasarkan awalan/akhiran/mengandung,
        opsi filter sumber (all, kbbi_only, contek_only, both, custom), filter multi-tag,
        serta opsi urut ('default' abjad / 'newest' terbaru ditambahkan, kata tanpa tanggal di bawah).
        Mengembalikan tuple: (results, total_count)
        di mana results adalah list dict dengan detail kata terstruktur.
        """
        q = (query or "").strip().lower()
        search_type = (search_type or "prefix").strip().lower()
        if search_type not in ("prefix", "suffix", "contains"):
            search_type = "prefix"

        tag_set = set(t.strip().upper() for t in (selected_tags or []) if t.strip())
        suffix_tags = [t.lower() for t in tag_set if t not in ("WHITELIST", "⭐ WHITELIST", "BLACKLIST", "🚫 BLOCKLIST", "BLOCKLIST")]

        check_whitelist = any("WHITELIST" in t for t in tag_set)
        check_blacklist = any("BLOCKLIST" in t or "BLACKLIST" in t for t in tag_set)

        # Gabungkan seluruh basis data kamus (KBBI, Contek, Custom, Whitelist, Blacklist)
        all_pool = set(self.kbbi_set) | set(self.contek_set) | set(self.custom_set) | set(self.words) | self.whitelisted_words | self.blacklisted_words

        # Optimasi pemilihan kandidat kata awal jika ada awalan
        if q and search_type == "prefix":
            ch0 = q[0]
            cand = sorted([w for w in all_pool if w.startswith(ch0)])
        else:
            cand = sorted(list(all_pool))

        matches = []
        for w in cand:
            w_len = len(w)
            if w_len < min_len or w_len > max_len:
                continue

            # Filter Sumber (Semua, KBBI, Contek, KBBI Saja, Contek Saja, KBBI + Contek, Kamus+)
            if source_filter == "kbbi":
                if w not in self.kbbi_set:
                    continue
            elif source_filter == "contek":
                if w not in self.contek_set:
                    continue
            elif source_filter == "kbbi_only":
                if not (w in self.kbbi_set and w not in self.contek_set):
                    continue
            elif source_filter == "contek_only":
                if not (w in self.contek_set and w not in self.kbbi_set):
                    continue
            elif source_filter == "both":
                if not (w in self.kbbi_set and w in self.contek_set):
                    continue
            elif source_filter == "custom":
                custom_pool = self.db_custom_set if self.storage_mode == "supabase" else self.base_custom_set
                if w not in custom_pool:
                    continue

            # Filter Query Teks
            if q:
                if search_type == "prefix" and not w.startswith(q):
                    continue
                elif search_type == "suffix" and not w.endswith(q):
                    continue
                elif search_type == "contains" and q not in w:
                    continue

            # Filter Tag
            if tag_set:
                matched_tag = False
                if check_whitelist and w in self.whitelisted_words:
                    matched_tag = True
                elif check_blacklist and w in self.blacklisted_words:
                    matched_tag = True
                elif suffix_tags and any(w.endswith(st) for st in suffix_tags):
                    matched_tag = True
                if not matched_tag:
                    continue

            matches.append(w)

        dt_scope = "custom" if source_filter == "custom" else "auto"
        if sort_by == "newest":
            def _newest_key(word_item):
                ts_val = self._parse_iso_ts(self.get_word_datetime(word_item, scope=dt_scope))
                if ts_val is not None:
                    return (0, -ts_val, word_item)
                return (1, 0.0, word_item)
            matches.sort(key=_newest_key)

        total_count = len(matches)
        if limit is not None and limit > 0:
            trimmed = matches[:limit]
        else:
            trimmed = matches

        # Buat lookup custom endings
        custom_lookup = {}
        for c in self.custom_endings:
            if isinstance(c, dict):
                sfx = c.get("suffix", "").lower()
                if sfx:
                    custom_lookup[sfx] = self._clean_tag_name(c.get("name"), sfx)
            elif isinstance(c, str) and c.strip():
                sfx = c.strip().lower()
                custom_lookup[sfx] = sfx.upper()

        results = []
        for idx, w in enumerate(trimmed, 1):
            matched_custom = None
            for sfx in custom_lookup:
                if w.endswith(sfx):
                    matched_custom = custom_lookup[sfx]
                    break

            if matched_custom:
                tag_label = matched_custom
                tag_id = f"sfx_{matched_custom}"
            else:
                tag_label = "Normal"
                tag_id = "sfx_Normal"

            is_wl = w in self.whitelisted_words
            is_bl = w in self.blacklisted_words

            if is_bl:
                status_src = "🚫 Blocklist"
                tag_id = "sfx_BL"
            elif is_wl:
                status_src = "⭐ Whitelist"
                tag_id = "sfx_WL"
            elif w in self.kbbi_set and w not in self.contek_set:
                status_src = "KBBI"
            elif w in self.contek_set and w not in self.kbbi_set:
                status_src = "Contek"
            elif w in self.kbbi_set and w in self.contek_set:
                status_src = "KBBI + Contek"
            else:
                status_src = "Kamus"

            is_db_custom = (w in self.db_custom_set) or (self.storage_mode == "txt" and w in self.custom_timestamps)
            added_by = ""
            if self.storage_mode == "supabase" and w in self.db_records:
                added_by = str(self.db_records[w].get("added_by") or "")
            dt_str = self.get_word_datetime(w, scope=dt_scope)

            results.append({
                "original_index": idx,
                "word": w.upper(),
                "length": len(w),
                "tag": tag_label,
                "tag_id": tag_id,
                "status": status_src,
                "is_whitelisted": is_wl,
                "is_blacklisted": is_bl,
                "is_db_custom": is_db_custom,
                "can_delete": self.is_deletable_custom_word(w),
                "added_by": added_by,
                "datetime": dt_str,
            })

        return results, total_count
