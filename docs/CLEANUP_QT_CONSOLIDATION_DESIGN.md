# Desain Pembersihan Proyek & Konsolidasi Entry Point Qt (SAKA Overlay)

**Tanggal:** 2026-11-26  
**Branch Target:** `dev`  
**Titik Arsip:** Git tag `archive/tkinter-v1`

---

## 1. Understanding Summary
- **Apa yang dilakukan:** Menghapus UI Tkinter lama (`app_gui.py`, `tab_views.py`, `ui_components.py`, `ui_theme.py`, `region_selector.py`), entry point duplikat (`main_qt.py`, `run_qt.bat`), serta artefak bloat di root (`repomix-output.xml`, screenshot PNG di root, `test_tmp_staging/`, `scratch/`).
- **Tujuan:** Menyederhanakan struktur repository menjadi satu UI stack (**PySide6 / Qt**) dengan satu entry point standar (`main.py` dan `run.bat`).
- **Target pengguna:** Maintainer/developer proyek dan pengguna akhir yang menjalankan aplikasi lewat `run.bat` atau `python main.py`.
- **Batasan utama:** Membuat Git tag `archive/tkinter-v1` sebelum penghapusan; tidak mengganggu `config.local.json`.
- **Explicit Non-Goals:** Tidak mengubah logika inti OCR, Solver, Hotkey, atau fitur gameplay; mempertahankan `main_cli.py`, `gameplay_indexer.py`, `sample/`, `deteksi-gameplay/`, dan test inti.

## 2. Assumptions
- `requirements.txt` sudah mencakup `PySide6>=6.5.0` dan semua dependensi OCR/hotkey yang dibutuhkan.
- File seperti `DESIGN.md`, `TODO.md`, `extract_gameplay_recording.py`, dan `kata_kbbi.txt` tetap dipertahankan.
- Dataset `sample/` dan `deteksi-gameplay/` tetap dipertahankan untuk `test_accuracy.py` dan `test_gameplay_indexer.py`.

## 3. Non-Functional Requirements
- **Keandalan & Kompatibilitas:** `⚡ Restart`, `updater.py`, dan `run.bat` tetap berfungsi mulus setelah `main.py` menjalankan `app_qt.main`; `config.local.json` tetap tidak terlacak Git.
- **Keamanan & Privasi:** Tidak ada kredensial atau konfigurasi lokal pengguna yang ikut ter-commit.
- **Pemeliharaan:** `README.md` dan `AGENTS.md` diperbarui agar konsisten merujuk ke PySide6 + `main.py` + `run.bat`.

## 4. Decision Log
| Keputusan | Alternatif yang Dipertimbangkan | Alasan Dipilih |
| :--- | :--- | :--- |
| Ruang lingkup: Hapus UI Tkinter + artefak root | Hanya Tkinter / Bersih total hapus CLI | Menghilangkan bloat nyata tanpa membuang `main_cli.py` & `gameplay_indexer.py` |
| Entry point tunggal `main.py` & `run.bat` | Pertahankan `main_qt.py` sebagai alias atau entry point utama | Lebih bersih dan standar untuk pengguna (`run.bat` / `python main.py`) |
| Buat tag Git `archive/tkinter-v1` sebelum hapus | Hapus langsung / folder arsip lokal | Aman untuk rollback cepat tanpa mengotori working tree |
| Konsolidasi in-place tanpa rename `*_qt.py` | Staged 2 fase / Rename `app_qt.py` → `app_gui.py` | Risiko rendah, langsung bersih, menghindari churn import/git history |

## 5. Final Design

### A. Titik Arsip
1. Pastikan state sebelum pembersihan di-tag dengan `git tag archive/tkinter-v1`.

### B. Penghapusan File & Artefak
- **UI Tkinter Lama:** `app_gui.py`, `tab_views.py`, `ui_components.py`, `ui_theme.py`, `region_selector.py`.
- **Entry Point Duplikat:** `main_qt.py`, `run_qt.bat`.
- **Artefak Root:** `repomix-output.xml`, `Screenshot 2026-11-08 102010.png`, `FiveM Tzx Cheat Remake By MinikAyicuhV5 (Community).png`, `test_tmp_staging/`, `scratch/`.

### C. Konsolidasi Entry Point & Dokumentasi
- **`main.py`:** Diperbarui agar mengimpor dan menjalankan `from app_qt import main`.
- **`run.bat`:** Tetap mempertahankan pengecekan Python + auto-install `requirements.txt` dan menjalankan `python main.py`.
- **`README.md` & `AGENTS.md`:** Diperbarui agar merujuk ke `main.py`, `run.bat`, dan modul PySide6 (`app_qt.py`, `tab_views_qt.py`, `qt_components.py`, `qt_theme.py`, `region_selector_qt.py`).

### D. Strategi Verifikasi
1. Compile check seluruh modul Python aktif (`py_compile`).
2. Verifikasi `import main` tanpa referensi modul Tkinter.
3. Jalankan `test_solver.py`, `test_gameplay_indexer.py`, dan `test_accuracy.py`.
