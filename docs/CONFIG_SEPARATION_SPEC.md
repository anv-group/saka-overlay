# Spesifikasi Desain: Pemisahan Konfigurasi Default & Lokal (`config.default.json` + `config.json`)

**Status:** Approved Design (Brainstorming Complete)  
**Tanggal:** 2026-11-28  
**Target:** Memisahkan template konfigurasi GitHub (`config.default.json`) dari konfigurasi personal lokal (`config.json`), serta memensiunkan `config.local.json`.

---

## 1. Understanding Summary

- **Tujuan:** Memisahkan konfigurasi bawaan repository (seperti `hotkeys` default dan `screen_area` default) dari konfigurasi personal user (termasuk `supabase_url`, `supabase_anon_key`, `sync_nickname`, `hotkeys` kustom, dan `custom_trap_endings`) agar kredensial pribadi tidak masuk ke GitHub dan perubahan lokal tidak tertimpa saat menarik update.
- **Pemetaan File:**
  - `config.default.json` → **tracked di GitHub**, template default tanpa kredensial (read-only terhadap penyimpanan aplikasi).
  - `config.json` → **untracked & masuk `.gitignore`**, satu-satunya file konfigurasi personal lokal yang dibaca/ditulis oleh `config.py`.
  - `config.local.json` → **dipensiunkan** (tidak lagi dipakai oleh aplikasi).
- **Target Pengguna:** Developer dan pengguna SAKA Overlay.
- **Batasan Utama:** Konfigurasi lokal developer saat ini (di `config.json` / `config.local.json`) harus tetap utuh saat transisi repository dilakukan.
- **Di Luar Cakupan:** Tidak mengubah struktur data tag/hotkey, skema Supabase, maupun mekanisme update di `updater.py`.

---

## 2. Assumptions & Non-Functional Requirements

- **Privasi & Keamanan:** `config.json` wajib keluar dari pelacakan Git (`git rm --cached config.json`) dan terdaftar di `.gitignore` agar kredensial Supabase dan data personal tidak pernah ikut ter-commit/ter-push ke GitHub.
- **Fallback Default Berkelanjutan:** Ketika update GitHub di masa depan menambah key atau action hotkey baru di `config.default.json`, aplikasi otomatis mengisi key yang belum ada tanpa menimpa pengaturan user yang sudah ada di `config.json`.
- **Kesederhanaan (YAGNI):** Tidak ada mekanisme migrasi otomatis maupun pre-pull safety guard di `updater.py`. Jika user lama menarik commit transisi ini dari GitHub dan konfigurasi lamanya ter-reset, user lama cukup mengatur ulang `config.json` dari template `config.default.json`.
- **Isolasi Mode (`CSV/TXT` vs `Supabase`):** Isolasi `MODE_SYNC_KEYS` milik mode lokal saat `storage_mode == "supabase"` tetap dijaga langsung di dalam `config.json`.

---

## 3. Decision Log

| Topik | Keputusan | Alternatif yang Dipertimbangkan | Alasan |
| :--- | :--- | :--- | :--- |
| Penamaan & peran file Git vs Lokal | `config.default.json` (GitHub) + `config.json` lokal (`.gitignore`) | Mempertahankan `config.json` (GitHub) + `config.local.json` (lokal) | `config.json` lokal adalah pola paling intuitif dan sudah umum digunakan untuk menyimpan semua setting runtime & kredensial pribadi dalam 1 file. |
| Nasib `config.local.json` | Pensiunkan total (`2-file architecture`), merge & hapus file lokal developer saat implementasi | Menyimpan `config.local.json` khusus mode TXT | Menghindari duplikasi dua file konfigurasi lokal; isolasi `MODE_SYNC_KEYS` dapat ditangani di dalam `config.json`. |
| Sumber defaults saat runtime | Opsi 1: `DEFAULT_CONFIG` Python + overlay `config.default.json` saat `load_config()` | Static copy saat fresh install saja / Sparse delta override | Memastikan key/hotkey baru dari update GitHub otomatis tersedia sebagai fallback tanpa membuat format file delta yang rumit. |
| Migrasi otomatis & Pre-pull guard | Tidak dibuat di runtime maupun di `updater.py` | Auto-migrate `config.local.json` saat startup + backup/restore `config.json` di `updater.py` | Atas arahan user: menghindari kerumitan kode migrasi legacy/guard; cukup jaga config milik developer saat eksekusi transisi lokal (`git rm --cached`). |
| Penulisan file | Atomic write (`tempfile`/temp file + `os.replace`) ke `config.json` | Direct `open(..., "w")` | Mencegah file `config.json` rusak/kosong jika aplikasi crash saat menyimpan. |

---

## 4. Final Design

### 4.1 Arsitektur File
1. **`.gitignore`**
   - Tambahkan `config.json` (pertahankan `config.local.json` dan `*.local.json` sebagai jaring pengaman).
2. **`config.default.json` (Git-tracked)**
   - Template JSON bersih berisi seluruh default standar (termasuk `hotkeys`, `screen_area`, opsi UI/OCR, `custom_trap_endings` default, `supabase_url: ""`, `supabase_anon_key: ""`, `sync_nickname: ""`).
3. **`config.json` (Untracked / Local User Config)**
   - Menampung seluruh konfigurasi runtime user, termasuk kredensial Supabase dan preferensi pribadi.
   - Tidak pernah ditimpa aplikasi oleh `config.default.json` kecuali pada *fresh install* (saat `config.json` belum ada di disk).

### 4.2 Alur Data di `config.py`
- Tambah konstanta `DEFAULT_CONFIG_FILE` mengarah ke `config.default.json`; hapus penggunaan `LOCAL_CONFIG_FILE` (`config.local.json`).
- **`load_config()`:**
  1. Mulai dari `copy.deepcopy(DEFAULT_CONFIG)`.
  2. Jika `DEFAULT_CONFIG_FILE` (`config.default.json`) ada dan valid JSON, merge ke `config` (termasuk merge key `hotkeys`).
  3. Jika `CONFIG_FILE` (`config.json`) **belum ada**, buat file `config.json` awal dari hasil gabungan langkah 1–2 (memakai atomic write).
  4. Jika `CONFIG_FILE` (`config.json`) **ada** dan valid JSON, overlay seluruh key-nya ke `config`, serta pastikan action di `config["hotkeys"]` tetap menerima action default baru dari `config.default.json` yang belum ada di `config.json` user.
- **Isolasi `MODE_SYNC_KEYS` & Atomic Write:**
  - `load_txt_mode_state()` membaca `MODE_SYNC_KEYS` dari `CONFIG_FILE` (`config.json`).
  - `save_txt_mode_state(mode_state)` mem-patch `MODE_SYNC_KEYS` di `CONFIG_FILE` (`config.json`) secara atomic (`os.replace`).
  - `save_config(cfg)` membaca `CONFIG_FILE` yang ada (jika `storage_mode == "supabase"`), mempertahankan `MODE_SYNC_KEYS` lokal milik `CSV/TXT` mode yang tersimpan di `CONFIG_FILE`, lalu menulis penuh ke `CONFIG_FILE` secara atomic (`os.replace`).

### 4.3 Transisi Aman untuk Konfigurasi Lokal Developer
Saat implementasi dilakukan pada workspace developer:
1. Pastikan isi [`config.local.json`](../config.local.json) yang relevan sudah ter-merge ke [`config.json`](../config.json) di disk, lalu hapus `config.local.json`.
2. Tambahkan `config.json` ke `.gitignore`.
3. Jalankan `git rm --cached config.json` agar `config.json` keluar dari Git index **tanpa menghapus** file `config.json` milik developer di disk.

### 4.4 Pembaruan UI, Dokumentasi, & Pengujian
- **`tab_views_qt.py`:** Perbarui referensi teks/tooltip yang masih menyebut `config.local.json` (sekitar baris 3961–3970) agar merujuk ke `config.json`.
- **`AGENTS.md`:** Perbarui deskripsi arsitektur file konfigurasi dari model `config.json` + `config.local.json` menjadi model 2-file `config.default.json` + `config.json`.
- **`test_db_sync.py` & Test Konfigurasi:**
  - Perbarui `test_config_mode_isolation_between_txt_and_supabase` dan `test_download_db_to_txt_files_and_mode` di `test_db_sync.py` agar menguji isolasi `MODE_SYNC_KEYS` langsung pada `CONFIG_FILE` (`config.json`) tanpa `LOCAL_CONFIG_FILE`.
  - Tambah unit test untuk `config.py`: overlay `config.default.json`, penggabungan `hotkeys` baru tanpa menimpa bind user, dan pembuatan otomatis `config.json` saat *fresh install*.
