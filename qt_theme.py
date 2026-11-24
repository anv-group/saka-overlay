import os
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
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

def get_qicon(name: str, size: int = 18, color: str = None, angle: float = 0) -> QIcon:
    """
    Memuat icon PNG resmi Material Design dari assets/icons/, meresize dengan
    anti-aliasing halus, lalu mewarnainya (Dynamic Color Tinting) menggunakan
    QPainter CompositionMode_SourceIn. Mendukung rotasi opsional (angle).
    """
    if color is None:
        color = THEME["text_primary"]

    cache_key = (name, size, color, angle)
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

    if angle:
        rotated = QPixmap(tinted.size())
        rotated.fill(Qt.transparent)
        rp = QPainter(rotated)
        rp.setRenderHint(QPainter.Antialiasing)
        rp.setRenderHint(QPainter.SmoothPixmapTransform)
        cx, cy = tinted.width() / 2.0, tinted.height() / 2.0
        rp.translate(cx, cy)
        rp.rotate(angle)
        rp.translate(-cx, -cy)
        rp.drawPixmap(0, 0, tinted)
        rp.end()
        tinted = rotated

    ico = QIcon(tinted)
    _QICON_CACHE[cache_key] = ico
    return ico


def get_badge_qicon(base_icon, badge_name: str = "plus", size: int = 16, color: str = None, badge_color: str = None) -> QIcon:
    """Membuat ikon komposit (ikon utama dari nama aset atau QIcon + badge kecil di pojok kanan bawah) dengan cache."""
    if color is None:
        color = THEME["text_primary"]
    if badge_color is None:
        badge_color = color

    base_key = base_icon if isinstance(base_icon, str) else base_icon.cacheKey()
    cache_key = ("badge", base_key, badge_name, size, color, badge_color)
    if cache_key in _QICON_CACHE:
        return _QICON_CACHE[cache_key]

    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    base_sz = max(10, size - 3)
    src_icon = get_qicon(base_icon, size=base_sz, color=color) if isinstance(base_icon, str) else base_icon
    base_pix = src_icon.pixmap(base_sz, base_sz)
    painter.drawPixmap(0, 0, base_pix)

    badge_sz = max(7, size // 2)
    bx = size - badge_sz
    by = size - badge_sz
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(THEME["bg_card"]))
    painter.drawEllipse(bx - 1, by - 1, badge_sz + 2, badge_sz + 2)

    badge_pix = get_qicon(badge_name, size=badge_sz, color=badge_color).pixmap(badge_sz, badge_sz)
    painter.drawPixmap(bx, by, badge_pix)
    painter.end()

    ico = QIcon(pix)
    _QICON_CACHE[cache_key] = ico
    return ico


def get_ban_qicon(size: int = 15, color: str = None) -> QIcon:
    """Menggambar ikon vektor larangan (lingkaran + garis miring) untuk Blocklist."""
    if color is None:
        color = THEME["danger"]

    cache_key = ("ban", size, color)
    if cache_key in _QICON_CACHE:
        return _QICON_CACHE[cache_key]

    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)

    pen = QPen(QColor(color), max(1.6, size * 0.13), Qt.SolidLine, Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    pad = max(2, int(round(size * 0.14)))
    d = size - (pad * 2)
    painter.drawEllipse(pad, pad, d, d)
    offset = int(round(d * 0.16))
    painter.drawLine(pad + offset, pad + d - offset, pad + d - offset, pad + offset)
    painter.end()

    ico = QIcon(pix)
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

/* Typography & Labels - Strict Zero Border on text */
QLabel, QCheckBox, QRadioButton {{
    border: none;
    background: transparent;
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
