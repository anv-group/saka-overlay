# Spesifikasi Desain: Non-Git HTTPS Archive Updater & Roadmap ke GitHub Releases

**Status:** Approved Design (Brainstorming Complete)  
**Tanggal:** 2026-11-28  
**Target:** Memungkinkan `GitUpdater` (`updater.py`) memeriksa pembaruan, daftar branch, log commit, ganti branch, dan menerapkan update lewat HTTPS GitHub API + Archive ZIP ketika `git` CLI tidak terinstal atau folder `.git` tidak ada.

---

## 1. Understanding Summary

- **Apa yang dibangun:** Dual-mode updater di `updater.py` (`Git CLI` sebagai jalur utama saat tersedia, dan fallback otomatis ke `HTTPS GitHub REST API + codeload Archive ZIP` saat `git` CLI tidak ada di PATH atau folder `.git` tidak tersedia).
- **Mengapa dibuat:** Pengguna Windows awam yang mengunduh aplikasi lewat *"Download ZIP"* GitHub atau tidak menginstal Git selalu gagal saat memeriksa dan memperbarui aplikasi.
- **Target pengguna:** Pengguna non-developer tanpa Git, sementara pengguna/developer yang memakai `git clone` + `git` CLI tetap menggunakan alur Git seperti biasa.
- **Batasan utama:**
  1. Tanpa dependency pihak ketiga baru: hanya memakai stdlib Python (`zipfile`, `shutil`, `tempfile`, `json`) dan `requests>=2.31.0` yang sudah tercantum di `requirements.txt`.
  2. File data personal (`config.json`, `updater_state.json`, `kamus_custom.csv`, `db_cache.json`, `sample/`, `deteksi-gameplay/`) **serta** `whitelist.csv` dan `blacklist.csv` yang sudah ada di disk user **tidak boleh ditimpa** saat ekstrak ZIP.
  3. Untuk instalasi *fresh Download ZIP* yang belum pernah mencatat hash commit lokal, pengecekan otomatis saat startup tidak langsung memunculkan notifikasi/prompt update; user tetap bisa sinkronisasi awal lewat tombol manual **Cek Update** atau **Ganti Branch**.
- **Di luar cakupan (*Non-Goals*):** Tidak menginstal Git otomatis (`winget`/installer) dan tidak mendukung autentikasi repository privat (repository diasumsikan publik: `anv-group/saka-overlay`).

---

## 2. Assumptions & Non-Functional Requirements

- **Performa:** Request GitHub REST API memakai timeout 8–12 detik; unduhan archive ZIP memakai `stream=True` dengan timeout 60 detik di background thread agar UI PySide6 tidak freeze.
- **Keamanan & Privasi:** Hanya mengakses host resmi GitHub (`api.github.com` & `codeload.github.com`) untuk repo `anv-group/saka-overlay`, dengan validasi path ekstraksi (`os.path.realpath`) untuk mencegah *Zip-Slip / path traversal*. Tidak menyimpan kredensial/token GitHub.
- **Keandalan (*Reliability*):** Ekstraksi dan persiapan salin dilakukan di direktori staging sementara (`tempfile`) yang selalu dibersihkan di blok `finally`; `updater_state.json` hanya ditulis setelah penyalinan file berhasil. Rate limit GitHub API unauthenticated (60 req/jam per IP) ditangani dengan pesan informatif dan fallback SHA dari `zipfile.ZipFile.comment`.
- **Kompatibilitas Kontrak:** Struktur return `GitUpdater` (`check_for_updates`, `apply_update`, `get_available_branches`, `get_current_branch`, `get_current_commit`) tetap kompatibel dengan `app_qt.py` dan `tab_views_qt.py`.

---

## 3. Decision Log

| Topik | Keputusan | Alternatif yang Dipertimbangkan | Alasan |
| :--- | :--- | :--- | :--- |
| Mekanisme update tanpa Git | **Opsi 1:** Dual-mode `Git CLI` + `GitHub REST API & Archive ZIP` fallback (+ roadmap ke Releases) | Instruksi install Git saja / GitHub Releases API saja / Pure `codeload` ETag tanpa REST API | Tetap mendukung branch (`main`, `dev`) dan preview log commit seperti mode Git tanpa menambah dependency atau memaksa pengguna awam install Git. |
| Pelacakan versi Non-Git | Simpan state lokal di `updater_state.json` (masuk `.gitignore`) | Simpan di `config.json` / tanpa state | Menjaga `config.json` tetap murni berisi preferensi user & kredensial Supabase. |
| Perlindungan `whitelist.csv` & `blacklist.csv` | **Preserve:** skip overwrite jika file sudah ada di disk user; seed hanya jika belum ada | Merge otomatis / Overwrite penuh dari ZIP | Mencegah daftar kata pribadi user hilang saat update ZIP, tanpa kerumitan konflik CSV. |
| Perilaku startup *fresh Download ZIP* (`local_hash` belum ada) | Jangan memunculkan prompt/toast saat `is_auto_check=True`; sync lewat cek manual | Tandai "Update Tersedia" di startup / tandai otomatis sebagai latest | Menghindari user yang baru saja ekstrak ZIP langsung diminta download ulang saat pembukaan pertama. |
| Ketahanan saat API limit / force-push | Fallback `/compare` 404 → `/commits`; fallback info SHA dari `ZipFile.comment` saat `apply_update` | Gagal keras jika API limit | Endpoint `codeload.github.com` tidak memakai kuota REST API sehingga update ZIP tetap bisa diterapkan. |

---

## 4. Final Design

### 4.1 Deteksi Mode & File State Lokal
1. **Deteksi Mode di `GitUpdater` (`updater.py`):**
   - `has_git_cli()` memeriksa `shutil.which("git") is not None`.
   - `get_updater_mode()` mengembalikan `"git"` hanya jika `has_git_cli()` dan `is_git_repo()` sama-sama `True`; selain itu `"https"`.
   - Konstanta target repository: `DEFAULT_GITHUB_REPO = "anv-group/saka-overlay"` (jika `.git/config` memiliki URL origin GitHub valid meski tanpa CLI `git`, boleh dipakai dengan fallback ke konstanta ini).
2. **`updater_state.json` (`.gitignore`):**
   - Disimpan di root aplikasi (sama dengan `repo_dir`), berformat:
     ```json
     {
       "branch": "main",
       "hash": "a01d38610058bfd537630413c7513833a4c86268",
       "author": "alden",
       "date": "2026-11-28",
       "message": "...",
       "updated_at": "2026-11-28T15:30:00Z"
     }
     ```
   - Jika `updater_state.json` belum ada:
     - `get_current_branch()` memakai `default_branch` / membaca `updater_branch` dari `config.json` bila tersedia (fallback `"main"`).
     - `get_current_commit()` mengembalikan `{"hash": "unknown", "message": "Versi ZIP belum terlacak (Mode Non-Git)", "author": "-", "date": "-", "is_non_git": True}`.

### 4.2 Alur Mode HTTPS (`updater.py`)
1. **`get_available_branches()`:**
   - `GET https://api.github.com/repos/{owner}/{repo}/branches?per_page=100` (timeout 8 detik).
   - Urutkan `main`, `dev`, lalu alfabetis; fallback `["main", "dev"]` bila jaringan gagal/rate-limited.
2. **`check_for_updates(target_branch=None, timeout=12, is_auto_check=False)`:**
   - Baca state dari `updater_state.json`.
   - **Bila `local_hash` kosong (*fresh Download ZIP*):**
     - Jika `is_auto_check=True`: kembalikan `{"success": True, "has_update": False, "behind_count": 0, "branch": branch, "current_branch": current_branch, "current_commit": current_commit, "is_non_git": True, "is_version_untracked": True, "commits": []}`.
     - Jika `is_auto_check=False`: ambil 5 commit terbaru dari `/commits?sha={branch}&per_page=5` dan kembalikan `has_update=True`, `commits=[...]` agar user dapat langsung menyinkronkan & mulai mencatat hash.
   - **Bila `local_hash` ada:**
     - Panggil `/compare/{local_hash}...{branch}`:
       - Jika `200 OK`: ekstrak `ahead_by`, `commits[]`, `behind_count`, dan cek `files[]` untuk `requirements.txt` (`needs_pip`). Jika `ahead_by == 0` dan `branch == local_branch`, `has_update=False`.
       - Jika `404 Not Found` (hash lama terhapus/rebase): fallback ke `/commits?sha={branch}&per_page=5`; bandingkan `latest_sha != local_hash` (atau branch berbeda).
3. **`apply_update(target_branch=None)`:**
   - Unduh ZIP: `GET https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}` ke temp dir (`timeout=60`).
   - Ekstrak ke staging temp dir sambil memvalidasi path agar berada di dalam staging dir (*anti Zip-Slip*).
   - Tentukan root folder tunggal hasil ekstrak GitHub (`{repo}-{branch}/`).
   - Salin ke `self.repo_dir` dengan aturan proteksi:
     - **Selalu skip** path dengan prefix: `.git/`, `.venv/`, `venv/`, `env/`, `sample/`, `deteksi-gameplay/`, `__pycache__/`.
     - **Selalu skip** file lokal spesifik: `config.json`, `config.local.json`, `updater_state.json`, `kamus_custom.csv`, `db_cache.json`.
     - **Skip jika sudah ada di disk (`os.path.exists(dst)`)**: `whitelist.csv`, `blacklist.csv` (jika belum ada di disk, salin dari ZIP).
     - File lain ditimpa dengan aman (tulis file sementara + `os.replace` atau `shutil.copy2` setelah staging lengkap).
   - Catat commit target ke `updater_state.json` (ambil detail commit dari `/commits?sha={branch}&per_page=1`; bila API limit/gagal, gunakan `zf.comment.decode("utf-8", errors="ignore").strip()` sebagai `hash` 40-char SHA).
   - Jalankan `pip install -r requirements.txt --quiet` bila `needs_pip` atau `requirements.txt` diperbarui, lalu kembalikan `(True, action_msg)`.

### 4.3 Error Handling & Penyesuaian UI
- **Rate limit (`403`/`429` dengan `X-RateLimit-Remaining: 0`):** Tampilkan pesan yang jelas ke pengguna agar menunggu beberapa menit atau memakai koneksi/jaringan berbeda.
- **`app_qt.py`:** `check_updates_background()` mengirim `is_auto_check=True` ke `self.updater.check_for_updates(target_branch=target_br, is_auto_check=True)`.
- **`tab_views_qt.py`:** Tampilkan label status mode ringkas (`Mode Non-Git (HTTPS ZIP)` bila `updater.get_updater_mode() == "https"`).
- **`.gitignore`:** Tambahkan `updater_state.json`.

### 4.4 Strategi Pengujian (`test_system_features.py`)
Tambahkan unit test memakai `tempfile.TemporaryDirectory`, in-memory `zipfile.ZipFile` (dengan `zf.comment = b"<40-char-sha>"`), dan mock `shutil.which` + `requests.get`:
1. `is_git_mode` / `get_updater_mode`: `git` hilang atau `.git` hilang → `"https"`.
2. Startup auto-check (`is_auto_check=True`) pada *fresh ZIP* (tanpa `updater_state.json`) → `has_update=False, is_version_untracked=True`; manual check (`is_auto_check=False`) → `has_update=True` + commits.
3. `apply_update` mode HTTPS:
   - Memperbarui file kode (`app_qt.py` dll.).
   - Melindungi `config.json`, `kamus_custom.csv`, `db_cache.json`, dan **tidak menimpa** `whitelist.csv` / `blacklist.csv` jika sudah ada; membuat keduanya jika belum ada.
   - Menulis `updater_state.json` dengan hash dari API atau fallback `zf.comment`.
   - Menolak/melewati entry Zip-Slip (`../../outside.txt`).
4. Rate-limit HTTP `403` mengembalikan error yang rapi tanpa crash.

---

## 5. Roadmap Migrasi ke Model GitHub Releases (Untuk Developer & AI Agent)

Bagian ini menjadi acuan ketika proyek siap beralih dari update berbasis branch/commit (`main`/`dev`) ke model **GitHub Releases** resmi (mis. saat mendistribusikan installer/zip `.exe` terkompilasi atau ingin terbebas dari batas commit branch mentah).

### Kapan Harus Pindah ke Model Releases
- Ketika SAKA Overlay mulai dirilis dengan *version tag* SemVer (`v1.0.0`, `v1.1.0`) atau mendistribusikan build terpaket (mis. PyInstaller `.exe` + aset siap pakai).
- Ketika jumlah pengguna meningkat sehingga pengecekan commit mentah antar-branch terlalu sering menyentuh batas GitHub REST API atau user tidak perlu melihat commit dev internal.

### Langkah Teknis Migrasi (Checklist untuk Developer & AI Agent)
1. **Tambahkan Penanda Versi Aplikasi & Asset Rilis:**
   - Buat konstanta `APP_VERSION` (mis. `"1.2.0"`) di file pusat (mis. `version.py` atau `updater.py`), dan gunakan Git tag berformat SemVer (`v1.2.0`) saat membuat Release di GitHub.
   - Jika mendistribusikan source ZIP custom atau binary ZIP, lampirkan sebagai **Release Asset** (`saka-overlay-vX.Y.Z.zip`) atau gunakan `zipball_url` milik tag rilis.
2. **Ubah Endpoints di `updater.py` (Mode HTTPS / Non-Git):**
   - Ganti pemanggilan `/branches` + `/commits` + `/compare` menjadi:
     - Stabil: `GET https://api.github.com/repos/{owner}/{repo}/releases/latest`
     - Beta/Eksperimental (jika masih ada jalur `dev`/prerelease): `GET https://api.github.com/repos/{owner}/{repo}/releases?per_page=10` lalu filter `prerelease == True/False` sesuai channel pilihan user (`"Stable"` vs `"Beta"`).
   - Bandingkan versi lokal vs remote berdasarkan **SemVer tuple** (`tuple(map(int, tag.lstrip("v").split(".")))`), bukan commit SHA mentah.
   - Ambil changelog dari field `body` (*Release Notes*) GitHub Release untuk ditampilkan pada dialog update.
   - Unduh file ZIP dari `assets[i].browser_download_url` (prioritas) atau `zipball_url` pada payload release.
   - (Opsional anti rate-limit penuh): Bisa mem-parse redirect `HEAD https://github.com/{owner}/{repo}/releases/latest` (tanpa kuota REST API) untuk membaca tag terbaru dari header `Location`, lalu unduh langsung `.../releases/download/{tag}/saka-overlay-{tag}.zip`.
3. **Skema `updater_state.json` di Model Releases:**
   - Tambahkan field `"version": "1.2.0"` / `"tag_name": "v1.2.0"` dan `"channel": "stable"` (menggantikan ketergantungan pada `"hash"` & `"branch"` untuk user non-Git).
   - Pertahankan **aturan proteksi file yang sama** saat ekstrak ZIP (`config.json`, `updater_state.json`, `kamus_custom.csv`, `db_cache.json`, `sample/`, serta `whitelist.csv` & `blacklist.csv` bila sudah ada).
4. **Penyesuaian UI (`tab_views_qt.py` & `app_qt.py`):**
   - Pada mode Non-Git berbasis Releases, ubah pemilih *Branch* menjadi pemilih *Release Channel* (`Stable` / `Prerelease`), dan tampilkan `vX.Y.Z` + *Release Notes* alih-alih daftar commit mentah.
