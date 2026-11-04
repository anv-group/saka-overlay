import os
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtCore import Qt

# Palet Warna Resmi Tactical Cyber Bamboo (sesuai DESIGN.md)
THEME = {
    # Surfaces
    "bg_root": "#0f1710",        # Hitam kehijauan taktis (Main Window & Canvas)
    "bg_card": "#141c15",        # Hijau gelap pekat (Card & Item Row)
    "bg_card_alt": "#1a241b",    # Sedikit lebih terang (Input & Active Row)
    "bg_hover": "#223024",       # Hover state tombol & baris
    "bg_selected": "#28392b",    # Active / Selected state

    # Borders
    "border": "#223024",         # Border standar antar elemen
    "border_focus": "#2f4432",   # Border saat widget aktif/fokus
    "border_highlight": "#38d976", # Neon green accent border

    # Primary & Accents
    "primary": "#38d976",        # Neon Cyber Bamboo Green
    "accent_neon": "#4ade80",    # Bright cyber green
    "accent_cyan": "#00f0ff",    # Tactical Cyan
    "accent_mint": "#22c55e",    # Deep bamboo mint

    # Status Colors
    "danger": "#ef4444",         # Merah tajam untuk status offline/hapus/brutal
    "danger_bg": "#2a1518",      # Latar belakang indikator bahaya
    "warning": "#f59e0b",        # Kuning amber untuk peringatan/akurasi sedang
    "info": "#06b6d4",           # Cyan untuk informasi/link

    # Text Colors
    "text_primary": "#f1f6ef",   # Putih kehijauan terang (Kontras tinggi)
    "text_secondary": "#8fa892", # Hijau keabuan untuk label sekunder
    "text_muted": "#556b58",     # Hijau redup untuk placeholder/shortcut
    "text_dark": "#0a100b",      # Hitam pekat untuk teks di atas background neon
}

ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")
_QICON_CACHE = {}

def get_qicon(name: str, size: int = 18, color: str = None) -> QIcon:
    """
    Memuat icon PNG resmi Material Design dari assets/icons/, meresize dengan
    anti-aliasing halus, lalu mewarnainya (Dynamic Color Tinting) menggunakan
    QPainter CompositionMode_SourceIn. Hasilnya di-cache permanen di memori.
    """
    if color is None:
        color = THEME["text_primary"]

    cache_key = (name, size, color)
    if cache_key in _QICON_CACHE:
        return _QICON_CACHE[cache_key]

    filename = f"{name}.png" if not name.endswith(".png") else name
    file_path = os.path.join(ICONS_DIR, filename)

    if not os.path.exists(file_path):
        # Fallback empty transparent icon
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        ico = QIcon(pix)
        _QICON_CACHE[cache_key] = ico
        return ico

    # Load source pixmap
    src = QPixmap(file_path)
    scaled = src.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    # Dynamic Color Tinting
    tinted = QPixmap(scaled.size())
    tinted.fill(Qt.transparent)

    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, scaled)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()

    ico = QIcon(tinted)
    _QICON_CACHE[cache_key] = ico
    return ico

GLOBAL_QSS = f"""
/* Global Reset & Base */
QWidget {{
    background-color: {THEME["bg_root"]};
    color: {THEME["text_primary"]};
    font-family: "Segoe UI", -apple-system, sans-serif;
    font-size: 13px;
    outline: none;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {THEME["bg_root"]};
    width: 6px;
    margin: 0px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {THEME["border"]};
    min-height: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {THEME["primary"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

/* Inputs (QLineEdit) */
QLineEdit {{
    background-color: {THEME["bg_card"]};
    color: {THEME["text_primary"]};
    border: 1px solid {THEME["border"]};
    border-radius: 5px;
    padding: 6px 10px;
    selection-background-color: {THEME["bg_selected"]};
    selection-color: {THEME["primary"]};
}}
QLineEdit:focus {{
    border: 1px solid {THEME["primary"]};
    background-color: {THEME["bg_card_alt"]};
}}

/* Dark Dropdown Combobox */
QComboBox {{
    background-color: {THEME["bg_card"]};
    color: {THEME["text_primary"]};
    border: 1px solid {THEME["border"]};
    border-radius: 5px;
    padding: 5px 10px;
    min-height: 20px;
}}
QComboBox:hover {{
    border: 1px solid {THEME["border_focus"]};
}}
QComboBox:on {{
    border: 1px solid {THEME["primary"]};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: none;
}}
QComboBox QAbstractItemView {{
    background-color: {THEME["bg_card"]};
    color: {THEME["text_primary"]};
    border: 1px solid {THEME["border_focus"]};
    selection-background-color: {THEME["bg_selected"]};
    selection-color: {THEME["primary"]};
    padding: 4px;
    outline: none;
}}

/* Standard Buttons */
QPushButton {{
    background-color: {THEME["bg_card"]};
    color: {THEME["text_primary"]};
    border: 1px solid {THEME["border"]};
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {THEME["bg_hover"]};
    border-color: {THEME["border_focus"]};
}}
QPushButton:pressed {{
    background-color: {THEME["bg_selected"]};
}}
QPushButton:disabled {{
    color: {THEME["text_muted"]};
    border-color: {THEME["border"]};
}}

/* Tooltips */
QToolTip {{
    background-color: {THEME["bg_card_alt"]};
    color: {THEME["text_primary"]};
    border: 1px solid {THEME["border_focus"]};
    padding: 4px 8px;
    border-radius: 4px;
}}
"""
