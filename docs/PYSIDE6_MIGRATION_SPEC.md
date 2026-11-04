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
