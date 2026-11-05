# 🚀 Spesifikasi Teknis Migrasi UI SAKA Overlay ke PySide6 (Qt)

## 📌 Ringkasan Keputusan (Decision Log)

| Aspek | Status Quo (Tkinter) | Solusi Baru (PySide6 / Qt) | Alasan Keputusan |
| :--- | :--- | :--- | :--- |
| **Framework GUI** | Tkinter (`app_gui.py`) | PySide6 (`app_qt.py`) | Mengeliminasi lag rendering, memory overhead widget destroy, dan limitasi styling Windows UxTheme. |
| **Strategi Migrasi** | Single File Monolith | Side-by-Side Paralel | `app_gui.py` tetap berjalan sampai `app_qt.py` diverifikasi 100% fungsional dan stabil. |
| **Threading Model** | `threading.Thread` + `root.after()` | `QThread` + `Signal & Slot` | Komunikasi OCR ➔ UI aman dari thread collision, zero UI freeze, 60fps mulus. |
| **Styling & Tema** | Tkinter manual widgets config | Qt Style Sheets (QSS) | Tampilan konsisten, dark dropdown 100% andal, rounded corners hardware-accelerated. |
| **Desain & Aset** | Zero-Emoji Tactical Bamboo | Zero-Emoji Tactical Bamboo | Mematuhi penuh aturan [DESIGN.md](../DESIGN.md). |

---

## 🏗️ Struktur Modul Baru

```
sambung-kata-overlay/
├── qt_theme.py           # Palet warna Tactical Bamboo, QSS Global, QIcon loader
├── qt_components.py      # TopTabStrip, SubTabStrip, MiniTickerBar, SegmentedPill, WordCard
├── tab_views_qt.py       # LiveView, TagsView, DictionaryView, SystemView
├── app_qt.py             # Main Application Window, ScanWorker QThread, Hotkey F2
└── main_qt.py            # Entry point alternatif untuk menguji PySide6
```


---

## 📋 Catatan Pengembangan Mendatang (Backlog & Roadmap)

### ⚙️ Pengaturan Lanjutan Brutal Preset di Tab SYSTEM (TODO)
- **Konsep:** Menyediakan panel kontrol terpusat di Tab **SYSTEM** untuk konfigurasi lanjutan Mode Brutal:
  - Opsi *Quick Toggle All / Disable All* dengan tombol konfirmasi aman (agar tidak sengaja terpencet saat bermain).
  - Snapshot otomatis preferensi tag aktif saat berpindah antara Mode Default dan Mode Brutal.


### 📚 Spesifikasi UX Tab KAMUS (Final)
- **Filter Pencarian Sumber Inklusif & Eksklusif:**
  - Inklusif (Default): Pencarian Contek atau KBBI menyertakan kata yang juga ada di kamus lain (irisan).
  - Murni Saja: Hanya menampilkan kata yang khusus ada di basis data sumber tersebut tanpa irisan.
  - Tombol filter: Semua (Ungu #c084fc), KBBI (Hijau #38d976), Contek (Biru #38bdf8), KBBI + Contek (Ungu #c084fc).
- **Preservasi Query & Scroll saat Hapus di Whitelist/Blocklist:**
  - Saat kata dihapus saat filter aktif, query pencarian tetap terjaga dan daftar hanya menampilkan hasil filter yang tersisa, tanpa reset ke awal. Scroll position juga dipertahankan.
- **Standarisasi Visual Kartu:**
  - Bar vertikal indikator sumber: Hijau (KBBI), Biru (Contek), Ungu (KBBI + Contek).
  - Suffix tag indicator diposisikan di paling kanan (pentok kanan) mendahului tombol aksi.
