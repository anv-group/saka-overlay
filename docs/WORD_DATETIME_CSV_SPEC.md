# Spesifikasi Desain: CSV Storage & Datetime Kata (Whitelist, Blocklist, Kamus Custom)

**Branch target:** `feature/word-datetime`  
**Status:** Disetujui (Validated via Brainstorming)

---

## 1. Understanding Summary

- **Apa yang dibangun:** Pencatatan metadata waktu (`datetime`) untuk setiap kata di **whitelist**, **blocklist**, dan **kata manual/custom** pada kedua mode penyimpanan (**CSV lokal** dan **Supabase**), disertai tampilan label/tooltip waktu lokal dan fitur **urutkan dari Terbaru (Sort by Newest)** di UI sub-tab **Whitelist**, **Blocklist**, dan **Eksplorer KAMUS**.
- **Mengapa fitur ini ada:** Memudahkan pemain dan tim melacak kapan kata terakhir ditambahkan atau diubah statusnya, memprioritaskan kata terbaru di daftar manajemen/eksplorasi, serta menjaga kamus sumber dasar (`kamus_kbbi.txt`, `kamus_contek.txt`, `kamus_lengkap.txt`) tetap murni (*read-only*).
- **Untuk siapa:** Pengguna SAKA Overlay di mode lokal (single-user) maupun mode sinkronisasi tim privat (Supabase).
- **Batasan & aturan inti:**
  1. Kurasi pengguna mode lokal dipindahkan dari `.txt` ke 3 file CSV terpisah: `whitelist.csv`, `blacklist.csv`, dan `kamus_custom.csv`.
  2. `kamus_kbbi.txt`, `kamus_contek.txt`, dan `kamus_lengkap.txt` diperlakukan **read-only** (tidak pernah ditulis ulang oleh `add_word` atau `whitelist_word`).
  3. Kata lama yang belum memiliki timestamp dibiarkan kosong (`""`, tampil tanpa tanggal/`—`) dan selalu berada di bagian bawah saat sort **Terbaru**.
  4. Penambahan ulang kata duplikat pada status yang sama **ditolak** (tidak menimpa timestamp lama); datetime hanya diperbarui saat kata baru ditambahkan atau statusnya berubah.
  5. File `.txt` lama (`whitelist.txt`, `blacklist.txt`) dimigrasi otomatis ke `.csv` saat startup pertama kali dan file `.txt` lama dihapus.
- **Explicit Non-Goals:**
  - Tidak mengubah format atau menulis ke `kamus_kbbi.txt`, `kamus_contek.txt`, dan `kamus_lengkap.txt`.
  - Tidak membuat backfill tanggal palsu untuk kata-kata lama.
  - Tidak memisahkan `created_at` dan `updated_at` (cukup 1 timestamp aktivitas terakhir).
  - Tidak menambahkan filter rentang tanggal (*date picker*).
  - Fitur *hapus kata dari kamus custom* tetap menjadi pekerjaan terpisah di `TODO.md`.

---

## 2. Assumptions & Non-Functional Requirements

- **Skala & Performa:** Data kurasi user (`whitelist`, `blacklist`, `kamus_custom`) berkisar ratusan hingga ribuan baris. Parsing/saving CSV dan pengurutan di memori berjalan dalam `< 5–10 ms`, tanpa memperlambat startup atau pencarian prefix $O(1)$ pada 148.000+ kata kamus dasar.
- **Zona Waktu & Format:** Timestamp disimpan sebagai string **ISO-8601 UTC** (`YYYY-MM-DDTHH:MM:SSZ`, selaras dengan `TIMESTAMPTZ` `updated_at` pada `saka_words` di Supabase) dan dikonversi ke zona waktu lokal perangkat saat dirender di UI.
- **Reliabilitas:** Penulisan CSV lokal menggunakan penulisan atomik (`*.tmp` → `os.replace`) dan parser toleran terhadap UTF-8 BOM, baris 1-kolom legacy, serta nilai waktu kosong/rusak.
- **Privasi & Keamanan:** Tidak ada data sensitif baru yang disimpan; kompatibel dengan kebijakan RLS privat `saka_words` yang ada.

---

## 3. Decision Log

| # | Keputusan | Alternatif yang Dipertimbangkan | Alasan Dipilih |
|---|---|---|---|
| 1 | Berlaku untuk **kedua mode** (Lokal & Supabase). | Hanya Supabase + UI; hanya TXT lokal + UI. | Memastikan pengalaman UI (tampil waktu & sort Terbaru) konsisten di kedua mode. |
| 2 | Kegunaan di UI: **Tampil waktu + Sortir Terbaru** di Whitelist, Blocklist, dan Eksplorer. | Tampil info saja; tampil + sort + filter tanggal; log file saja. | Sort Terbaru adalah kebutuhan praktis utama tanpa menambah kompleksitas date-range filter (YAGNI). |
| 3 | Kata lama dibiarkan **kosong** (tanpa backfill) & di urutan bawah saat sort Terbaru; duplikat pada status sama **ditolak**. | Backfill tanggal migrasi; pisah `created_at` & `updated_at`. | Akurat secara historis dan selaras dengan `updated_at` tunggal di `saka_words`. |
| 4 | Penyimpanan lokal memakai **3 CSV terpisah** (`whitelist.csv`, `blacklist.csv`, `kamus_custom.csv`), sedangkan `kamus_kbbi.txt`, `kamus_contek.txt`, `kamus_lengkap.txt` tetap *read-only*. | 1 file CSV gabungan (`saka_curation.csv`); JSON metadata sidecar; ubah `kamus_lengkap.txt` 148k baris jadi CSV. | Memisahkan data user dari basis data sumber eksternal, mudah dibaca/diedit manual per daftar, dan siap untuk fitur hapus kata custom di masa depan. |
| 5 | Migrasi **otomatis** `whitelist.txt` & `blacklist.txt` → `.csv` lalu **hapus `.txt` lama**. | Migrasi manual; menyimpan `.txt` lama sebagai cadangan. | Mencegah dua sumber kebenaran (*dual source of truth*) dan menjaga kebersihan direktori kerja. |
| 6 | **Opsi 1** (3 CSV `word,datetime` + unified metadata accessor di `solver.py` dengan optimistic `updated_at` di mode Supabase). | 1 CSV gabungan; mode Supabase tanpa optimistic timestamp. | UI tetap responsif saat offline/jeda Realtime dan kode UI seragam untuk kedua mode. |

---

## 4. Final Design

### 4.1 Skema File CSV (`whitelist.csv`, `blacklist.csv`, `kamus_custom.csv`)
- Header standar:
  ```csv
  word,datetime
  ```
- Setiap baris berisi kata lowercase (`word`) dan timestamp UTC ISO-8601 `YYYY-MM-DDTHH:MM:SSZ` (atau string kosong `""` untuk kata hasil migrasi `.txt` lama).
- Helper internal di `solver.py`:
  - `_utc_now_iso() -> str`: menghasilkan timestamp UTC saat ini berakhiran `Z`.
  - `_read_word_csv(path) -> dict[str, str]`: membaca CSV (UTF-8 / BOM-safe), mendukung fallback baris 1-kolom tanpa datetime, mengabaikan komentar `#` dan baris tidak valid.
  - `_write_word_csv(path, word_ts_map)`: mengurutkan/menulis ke `<path>.tmp` dengan `csv.writer` dan mengganti atomik lewat `os.replace()`.

### 4.2 Migrasi Otomatis & Kamus Dasar Read-Only
- Default path di `SambungKataSolver.__init__`: `blacklist_path="blacklist.csv"`, `whitelist_path="whitelist.csv"`, `custom_dict_path="kamus_custom.csv"`.
- Saat `storage_mode == "txt"` (atau sebelum load CSV) jika file `.csv` berada di lokasi default/berdampingan dengan `.txt` lama (`whitelist.txt`, `blacklist.txt`):
  - Baca kata valid dari `.txt` lama.
  - Gabungkan ke dict CSV (`word -> ""`) tanpa menimpa kata yang sudah ada di `.csv`.
  - Tulis `.csv` atomik, lalu hapus `.txt` lama via `os.remove`.
- `load_dictionary()` memuat `kamus_lengkap.txt` + `kamus_kbbi.txt` + `kamus_contek.txt` (*read-only*) + `kamus_custom.csv` (`base_custom_set` dan `custom_timestamps`).
- `add_word()` dan penambahan kata custom dari `whitelist_word()` hanya menulis ke `kamus_custom.csv`, **tidak lagi menulis** ke `kamus_lengkap.txt` maupun `kamus_contek.txt`.

### 4.3 Metadata Terpadu, Duplicate Guard & Sync Flow
- Di memori `SambungKataSolver`:
  - `self.whitelist_timestamps: dict[str, str]`
  - `self.blacklist_timestamps: dict[str, str]`
  - `self.custom_timestamps: dict[str, str]`
- Akses terpadu `get_word_datetime(word, scope="auto") -> str`:
  - Jika `storage_mode == "supabase"`, mengambil `db_records.get(w, {}).get("updated_at", "")`.
  - Jika mode lokal (`txt`/CSV), mengambil sesuai `scope` (`"whitelist"`, `"blacklist"`, `"custom"`, atau `"auto"` dengan urutan prioritas `whitelist` → `blacklist` → `custom`).
- **Duplicate Guard:**
  - `whitelist_word(w)`: jika `w` sudah di `whitelisted_words` (status sama), return `False` / no-op tanpa mengubah timestamp atau menulis ulang file/DB. *(Pastikan caller yang butuh idempoten seperti batch add membedakan duplikat vs gagal validasi).*
  - `blacklist_word(w)`: jika `w` sudah di `blacklisted_words` (status sama), no-op tanpa mengubah timestamp.
  - `add_word(w)`: sudah menolak jika `w in word_set`.
- **Supabase Sync (`solver.py`, `app_qt.py`):**
  - Mutasi lokal di mode `supabase` menyertakan `"updated_at": _utc_now_iso()` secara optimistik di `self.db_records[w]`, lalu disinkronkan saat event REST/Realtime datang.
  - `export_txt_records_for_import` menyertakan `updated_at` non-kosong dari CSV ke Supabase.
  - `apply_db_records_to_txt_files` menuliskan hasil download DB ke `whitelist.csv`, `blacklist.csv`, dan `kamus_custom.csv` dengan mempertahankan `updated_at`.
  - Label UI dialog import/download di `app_qt.py` diperbarui agar merujuk ke `.csv`.

### 4.4 UI Components & Sorting (`tab_views_qt.py`)
- Helper UI `format_word_datetime(iso_str) -> tuple[str, str]`: mem-parsing ISO-8601 (`...Z` / offset) ke waktu lokal dan mengembalikan `(short_label, full_tooltip)` seperti `("28/11 13:40", "Ditambahkan: 2026-11-28 13:40:00")`, atau `("", "")` jika kosong.
- Baris pada sub-tab **Whitelist**, **Blocklist**, dan **Eksplorer** menampilkan badge datetime ringkas di sebelah `added_by` (jika datetime ada) untuk kedua mode penyimpanan.
- Tombol toggle sortir **`A-Z` ↔ `Terbaru`** ditambahkan ke toolbar **Whitelist**, **Blocklist**, dan **Eksplorer** (di `search_dictionary` menerima `sort_by="default"|"newest"`):
  - Pada mode `Terbaru`, kata ber-datetime diurutkan descending berdasarkan waktu terbaru (tie-breaker `A-Z`), diikuti kata tanpa datetime (`""`) terurut `A-Z` di bagian bawah.

### 4.5 Testing Strategy
- Unit test baru & pembaruan test di [test_solver.py](file:///C:/Users/Alden/Documents/VSCode/saka-overlay/test_solver.py) dan [test_db_sync.py](file:///C:/Users/Alden/Documents/VSCode/saka-overlay/test_db_sync.py):
  - Verifikasi format CSV (`word,datetime`), atomic write, dan *read-only* guard terhadap `kamus_kbbi.txt`, `kamus_contek.txt`, `kamus_lengkap.txt`.
  - Verifikasi migrasi otomatis `whitelist.txt` / `blacklist.txt` → `.csv` dan penghapusan `.txt` lama.
  - Verifikasi duplicate guard tidak mengubah datetime, sedangkan perpindahan status memperbarui datetime.
  - Verifikasi `search_dictionary(..., sort_by="newest")` menempatkan kata terbaru di atas dan kata tanpa tanggal di bawah.
  - Verifikasi roundtrip export/download Supabase ↔ CSV mempertahankan `updated_at`.
