from datetime import datetime, timezone
import os
import webbrowser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QFrame, QComboBox, QSizePolicy, QMessageBox, QCheckBox, QDialog, QMenu,
    QButtonGroup, QRadioButton, QApplication, QInputDialog
)
from PySide6.QtGui import QDrag, QPixmap, QKeySequence, QShortcut
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QMimeData, QEvent
from qt_theme import THEME, get_qicon, get_badge_qicon, get_ban_qicon
from qt_components import QtSubTabStrip, QtSegmentedPills


def format_word_datetime(iso_str: str) -> tuple[str, str]:
    """Mengonversi ISO-8601 UTC string menjadi (label_ringkas_lokal, tooltip_lengkap)."""
    raw = str(iso_str or "").strip()
    if not raw:
        return "", ""
    try:
        norm = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone()
        return local_dt.strftime("%d/%m %H:%M"), f"Ditambahkan: {local_dt.strftime('%Y-%m-%d %H:%M:%S')}"
    except Exception:
        return "", ""


def make_meta_pill(text: str, tooltip: str = "") -> QLabel:
    """Membuat badge metadata ringkas untuk added_by / datetime."""
    lbl = QLabel(text)
    lbl.setFixedHeight(18)
    if tooltip:
        lbl.setToolTip(tooltip)
    lbl.setStyleSheet(
        f"background-color: {THEME['bg_root']}; color: {THEME['text_secondary']}; "
        f"border: 1px solid {THEME['border']}; font-size: 9px; font-weight: 600; "
        f"padding: 1px 5px; border-radius: 3px;"
    )
    return lbl

# --- Word Card Widget ---
class QtWordCardWidget(QFrame):
    """
    Kartu Rekomendasi Kata yang Ringan dan Cepat (High-Performance Word Card).
    Bebas border pada teks huruf dan bebas glitch pewarisan QFrame.
    """
    toggle_whitelist = Signal(str)
    block_word = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.word = ""
        self.setObjectName("WordCard")
        self.setFixedHeight(34)
        self.setCursor(Qt.ArrowCursor)
        self.setStyleSheet(f"""
            #WordCard {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
            }}
            #WordCard:hover {{
                background-color: {THEME["bg_hover"]};
                border-color: {THEME["border_focus"]};
            }}
            #WordCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 8, 0)
        layout.setSpacing(8)

        # Tombol Bintang Whitelist (Hitbox diperluas 26x26)
        self.btn_star = QPushButton()
        self.btn_star.setObjectName("btn_star")
        self.btn_star.setFixedSize(26, 26)
        self.btn_star.setCursor(Qt.PointingHandCursor)
        self.btn_star.setStyleSheet(f"""
            #btn_star {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }}
            #btn_star:hover {{
                background-color: rgba(245, 158, 11, 0.18);
            }}
        """)
        self.btn_star.clicked.connect(lambda: self.toggle_whitelist.emit(self.word))
        layout.addWidget(self.btn_star)

        # Kata Utama (Mendukung Two-Tone Text HTML)
        self.lbl_word = QLabel()
        self.lbl_word.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {THEME['text_primary']}; border: none; background: transparent;")
        layout.addWidget(self.lbl_word)

        layout.addStretch(1)

        # Badge Tier / Tag (Flat pill tanpa border individual)
        self.badge_tier = QLabel()
        self.badge_tier.setFixedHeight(20)
        self.badge_tier.setStyleSheet("border: none;")
        layout.addWidget(self.badge_tier)

        # Tombol Silang Blocklist (Hitbox diperluas 26x26)
        self.btn_del = QPushButton()
        self.btn_del.setObjectName("btn_del")
        self.btn_del.setFixedSize(26, 26)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.setIcon(get_qicon("cross", size=13, color=THEME["text_muted"]))
        self.btn_del.setStyleSheet(f"""
            #btn_del {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }}
            #btn_del:hover {{
                background-color: rgba(239, 68, 68, 0.18);
            }}
        """)
        self.btn_del.clicked.connect(lambda: self.block_word.emit(self.word))
        layout.addWidget(self.btn_del)

    def update_data(self, item: dict, prefix_upper: str = "", two_tone: bool = True):
        self.word = item.get("kata", "").upper()
        tipe = item.get("tipe", "NORMAL")
        deskripsi = item.get("deskripsi", "")
        is_wl = item.get("is_whitelisted", False)

        # Format Two-Tone Text jika diaktifkan: redupkan awalan, terangkan sisa huruf
        if two_tone and prefix_upper and self.word.startswith(prefix_upper):
            p_len = len(prefix_upper)
            p_part = self.word[:p_len]
            rest_part = self.word[p_len:]
            self.lbl_word.setText(
                f"<span style='color: {THEME['text_muted']}; font-weight: 500;'>{p_part}</span>"
                f"<span style='color: {THEME['text_primary']}; font-weight: bold;'>{rest_part}</span>"
            )
        else:
            self.lbl_word.setText(self.word)

        if is_wl:
            self.btn_star.setIcon(get_qicon("star_filled", size=14, color=THEME["warning"]))
            self.btn_star.setToolTip("Terdaftar di Whitelist (Klik untuk hapus)")
        else:
            self.btn_star.setIcon(get_qicon("star", size=14, color=THEME["text_muted"]))
            self.btn_star.setToolTip("Tambah ke Whitelist")

        if tipe == "CUSTOM_TRAP":
            b_name = item.get("badge_name") or item.get("suffix", "").upper()
            if b_name.lower().startswith("akhiran "):
                b_name = b_name[8:].strip()
            bg = item.get("color", THEME["primary"])
            self.badge_tier.setText(b_name)
            self.badge_tier.setStyleSheet(f"background-color: {bg}; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; padding: 2px 7px; border-radius: 3px; border: none;")
        else:
            self.badge_tier.setText("Santai" if deskripsi == "Kata Santai" else "Normal")
            bg = "#a6e3a1" if deskripsi == "Kata Santai" else THEME["border_focus"]
            self.badge_tier.setStyleSheet(f"background-color: {bg}; color: {THEME['text_primary']}; font-size: 10px; font-weight: 500; padding: 2px 7px; border-radius: 3px; border: none;")


# --- Tab 1: LIVE Tab View ---
class QtLiveTabView(QWidget):
    start_stop_clicked = Signal()
    mode_changed = Signal(str)
    search_text_changed = Signal(str)
    sort_mode_toggled = Signal()
    flag_clicked = Signal()
    add_word_clicked = Signal()
    add_whitelist_clicked = Signal()
    add_blocklist_clicked = Signal()

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.word_card_widgets = []
        self.tag_chip_buttons = []
        self.two_tone_enabled = self.app.config.get("two_tone_text", True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(6)

        # 1. Action Bar (Top Toolbar - Clean Icon-Only Actions)
        act_bar = QWidget()
        act_layout = QHBoxLayout(act_bar)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(5)

        # Tombol Mulai / Stop
        self.btn_toggle = QPushButton(" MULAI")
        self.btn_toggle.setIcon(get_qicon("play", size=14, color=THEME["text_dark"]))
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setFixedHeight(30)
        self.btn_toggle.setToolTip("Mulai / Hentikan Live OCR Scanner (Hotkey: F5)")
        self.btn_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["primary"]};
                color: {THEME["text_dark"]};
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {THEME["accent_neon"]};
            }}
        """)
        self.btn_toggle.clicked.connect(self.start_stop_clicked.emit)
        act_layout.addWidget(self.btn_toggle)

        # 1. Tombol Flag Salah (F2) - Icon Only
        self.btn_flag = QPushButton()
        self.btn_flag.setIcon(get_qicon("flag", size=14, color=THEME["danger"]))
        self.btn_flag.setCursor(Qt.PointingHandCursor)
        self.btn_flag.setFixedSize(30, 30)
        self.btn_flag.setToolTip("Laporkan / Simpan Sampel Deteksi Salah (Hotkey: F2)")
        self.btn_flag.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(239, 68, 68, 0.18);
                border-color: {THEME["danger"]};
            }}
        """)
        self.btn_flag.clicked.connect(self.flag_clicked.emit)
        act_layout.addWidget(self.btn_flag)

        # 2. Tombol Tambah Kata Baru ke Kamus (Buku +) - Icon Only
        self.btn_add_word = QPushButton()
        self.btn_add_word.setIcon(get_badge_qicon("book", "plus", size=16, color=THEME["primary"]))
        self.btn_add_word.setCursor(Qt.PointingHandCursor)
        self.btn_add_word.setFixedSize(30, 30)
        self.btn_add_word.setToolTip("Tambah Kata Baru ke Kamus Lengkap")
        self.btn_add_word.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(56, 217, 118, 0.18);
                border-color: {THEME["primary"]};
            }}
        """)
        self.btn_add_word.clicked.connect(self.add_word_clicked.emit)
        act_layout.addWidget(self.btn_add_word)

        # 3. Tombol Tambah ke Whitelist (Bintang +) - Icon Only
        self.btn_add_wl = QPushButton()
        self.btn_add_wl.setIcon(get_badge_qicon("star_filled", "plus", size=16, color=THEME["warning"]))
        self.btn_add_wl.setCursor(Qt.PointingHandCursor)
        self.btn_add_wl.setFixedSize(30, 30)
        self.btn_add_wl.setToolTip("Tambah Kata ke Whitelist (Prioritas Teratas #1) (Hotkey: F3)")
        self.btn_add_wl.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(245, 158, 11, 0.18);
                border-color: {THEME["warning"]};
            }}
        """)
        self.btn_add_wl.clicked.connect(self.add_whitelist_clicked.emit)
        act_layout.addWidget(self.btn_add_wl)

        # 4. Tombol Tambah ke Blocklist (Larangan +) - Icon Only
        self.btn_add_bl = QPushButton()
        self.btn_add_bl.setIcon(get_badge_qicon(get_ban_qicon(size=13, color=THEME["danger"]), "plus", size=16, color=THEME["danger"]))
        self.btn_add_bl.setCursor(Qt.PointingHandCursor)
        self.btn_add_bl.setFixedSize(30, 30)
        self.btn_add_bl.setToolTip("Blokir Kata ke Blocklist (Kata Ditolak) (Hotkey: F4)")
        self.btn_add_bl.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(239, 68, 68, 0.18);
                border-color: {THEME["danger"]};
            }}
        """)
        self.btn_add_bl.clicked.connect(self.add_blocklist_clicked.emit)
        act_layout.addWidget(self.btn_add_bl)

        act_layout.addStretch(1)

        # Tombol Sortir yang Jelas (Bukan Mode Permainan)
        cur_sort = self.app.config.get("tier0_sort_mode", "default")
        sort_txt = "SORT: TAG" if cur_sort == "tag_order" else "SORT: DEFAULT"
        self.btn_sort = QPushButton(f" {sort_txt}")
        self.btn_sort.setIcon(get_qicon("sort", size=13, color=THEME["text_secondary"]))
        self.btn_sort.setCursor(Qt.PointingHandCursor)
        self.btn_sort.setFixedHeight(30)
        self.btn_sort.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["bg_card"]};
                color: {THEME["text_secondary"]};
                font-size: 11px;
                font-weight: 600;
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                background-color: {THEME["bg_hover"]};
                color: {THEME["text_primary"]};
                border-color: {THEME["border_focus"]};
            }}
        """)
        self.btn_sort.clicked.connect(self.sort_mode_toggled.emit)
        act_layout.addWidget(self.btn_sort)

        layout.addWidget(act_bar)

        # 2. Mode Game Switcher (DEFAULT, SANTAI, BRUTAL)
        self.mode_pills = QtSegmentedPills()
        self.mode_pills.mode_changed.connect(self.mode_changed.emit)
        layout.addWidget(self.mode_pills)

        # 3. HUD Box (OCR Prefix Box + Search Bar Overpower OCR)
        hud_box = QFrame()
        hud_box.setObjectName("HudBox")
        hud_box.setStyleSheet(f"""
            #HudBox {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border"]};
                border-radius: 6px;
            }}
            #HudBox QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        hud_layout = QHBoxLayout(hud_box)
        hud_layout.setContentsMargins(8, 6, 8, 6)
        hud_layout.setSpacing(10)

        # Kotak Besar Huruf OCR
        prefix_frame = QFrame()
        prefix_frame.setObjectName("PrefixFrame")
        prefix_frame.setFixedSize(62, 48)
        prefix_frame.setStyleSheet(f"""
            #PrefixFrame {{
                background-color: {THEME["bg_root"]};
                border: 1px solid {THEME["border_focus"]};
                border-radius: 4px;
            }}
            #PrefixFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        pf_layout = QVBoxLayout(prefix_frame)
        pf_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_prefix = QLabel("-")
        self.lbl_prefix.setAlignment(Qt.AlignCenter)
        self.lbl_prefix.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {THEME['text_primary']}; border: none;")
        pf_layout.addWidget(self.lbl_prefix)
        hud_layout.addWidget(prefix_frame)

        # Sisi Kanan: Status, Speed 40ms di Kanan, & Input Search Bar Manual (Overpower OCR)
        right_box = QVBoxLayout()
        right_box.setSpacing(3)

        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        self.lbl_conf = QLabel("OCR Standby")
        self.lbl_conf.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; border: none;")
        info_row.addWidget(self.lbl_conf)

        self.lbl_manual_badge = QLabel("[MANUAL OVERRIDE]")
        self.lbl_manual_badge.setStyleSheet(f"color: {THEME['accent_cyan']}; font-size: 10px; font-weight: bold; border: none;")
        self.lbl_manual_badge.hide()
        info_row.addWidget(self.lbl_manual_badge)

        info_row.addStretch(1)

        # Angka Kecepatan (Speed 40ms) mentok kanan di samping OCR Standby
        init_spd = int(self.app.config.get("scan_interval_sec", 0.04) * 1000)
        self.lbl_speed = QLabel(f"{init_spd}ms")
        self.lbl_speed.setToolTip("Kecepatan Interval Scan OCR Layar")
        self.lbl_speed.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 11px; font-weight: 600; border: none;")
        info_row.addWidget(self.lbl_speed)

        right_box.addLayout(info_row)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Ketik manual")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.setFixedHeight(26)
        self.edit_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME["bg_root"]};
                color: {THEME["text_primary"]};
                font-size: 12px;
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
                padding: 2px 6px;
            }}
            QLineEdit:focus {{
                border-color: {THEME["primary"]};
            }}
        """)
        self.edit_search.textChanged.connect(self.search_text_changed.emit)
        right_box.addWidget(self.edit_search)

        hud_layout.addLayout(right_box, 1)
        layout.addWidget(hud_box)

        # 4. Quick Tag Chips Flow Container (Glitch-free horizontal scrollbar)
        self.tag_scroll = QScrollArea()
        self.tag_scroll.setFixedHeight(30)
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setFrameShape(QFrame.NoFrame)
        self.tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tag_scroll.setStyleSheet("background: transparent; border: none;")

        # Enable horizontal wheel scroll
        self.tag_scroll.wheelEvent = self._on_tag_scroll_wheel

        self.tag_bar = QWidget()
        self.tag_bar_layout = QHBoxLayout(self.tag_bar)
        self.tag_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_bar_layout.setSpacing(4)
        self.tag_scroll.setWidget(self.tag_bar)
        layout.addWidget(self.tag_scroll)

        # 5. Cards Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 4, 0)
        self.cards_layout.setSpacing(4)
        self.cards_layout.setAlignment(Qt.AlignTop)

        self.lbl_empty = QLabel("Belum ada kata terdeteksi.\nTekan MULAI untuk memindai otomatis.")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px; font-style: italic; padding: 20px; border: none;")
        self.cards_layout.addWidget(self.lbl_empty)

        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area, 1)

        self.update_hotkey_tooltips(self.app.config.get("hotkeys", {}))

    def update_hotkey_tooltips(self, hotkeys: dict):
        def _fmt(aid, desc):
            k = (hotkeys.get(aid) or "").strip()
            return f"{desc} ({k})" if k else desc

        self.btn_toggle.setToolTip(_fmt("toggle_scan", "Mulai / Hentikan"))
        self.btn_flag.setToolTip(_fmt("flag_error", "Flag Kesalahan"))
        self.btn_add_word.setToolTip(_fmt("add_kamus", "Kata Baru"))
        self.btn_add_wl.setToolTip(_fmt("add_whitelist", "Whitelist Kata"))
        self.btn_add_bl.setToolTip(_fmt("add_blocklist", "Blacklist Kata"))
        if hasattr(self, "_btn_add_tag") and self._btn_add_tag is not None:
            self._btn_add_tag.setToolTip(_fmt("add_tag", "Akhiran Baru"))

    def _on_tag_scroll_wheel(self, event):
        delta = event.angleDelta().y() or event.angleDelta().x()
        sb = self.tag_scroll.horizontalScrollBar()
        sb.setValue(sb.value() - delta)
        event.accept()

    def set_scanning_state(self, is_scanning: bool):
        if is_scanning:
            self.btn_toggle.setText(" STOP")
            self.btn_toggle.setIcon(get_qicon("stop", size=14, color="#ffffff"))
            self.btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME["danger"]};
                    color: #ffffff;
                    font-size: 11px;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                }}
            """)
        else:
            self.btn_toggle.setText(" MULAI")
            self.btn_toggle.setIcon(get_qicon("play", size=14, color=THEME["text_dark"]))
            self.btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME["primary"]};
                    color: {THEME["text_dark"]};
                    font-size: 11px;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 10px;
                }}
                QPushButton:hover {{
                    background-color: {THEME["accent_neon"]};
                }}
            """)

    def set_two_tone_enabled(self, enabled: bool):
        self.two_tone_enabled = enabled

    def update_ocr_display(self, prefix: str, conf_pct: int):
        self.lbl_prefix.setText(prefix if prefix else "-")
        if prefix:
            self.lbl_conf.setText(f"Akurasi: {conf_pct}%")
            self.lbl_conf.setStyleSheet(f"color: {THEME['primary']}; font-size: 11px; font-weight: bold; border: none;")
        else:
            self.lbl_conf.setText("OCR Standby")
            self.lbl_conf.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; border: none;")

    def set_manual_override_active(self, active: bool):
        if active:
            self.lbl_manual_badge.show()
            self.edit_search.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {THEME["bg_card_alt"]};
                    color: {THEME["primary"]};
                    font-weight: bold;
                    font-size: 12px;
                    border: 1px solid {THEME["primary"]};
                    border-radius: 4px;
                    padding: 2px 6px;
                }}
            """)
        else:
            self.lbl_manual_badge.hide()
            self.edit_search.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {THEME["bg_root"]};
                    color: {THEME["text_primary"]};
                    font-size: 12px;
                    border: 1px solid {THEME["border"]};
                    border-radius: 4px;
                    padding: 2px 6px;
                }}
                QLineEdit:focus {{
                    border-color: {THEME["primary"]};
                }}
            """)

    def update_sort_button(self, mode: str):
        sort_txt = "SORT: TAG" if mode == "tag_order" else "SORT: DEFAULT"
        self.btn_sort.setText(f" {sort_txt}")

    def refresh_quick_tags(self, categories: list):
        while self.tag_bar_layout.count():
            item = self.tag_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        btn_ico = QPushButton()
        btn_ico.setIcon(get_badge_qicon("tag", "plus", size=15, color=THEME["text_secondary"]))
        btn_ico.setFixedSize(26, 26)
        btn_ico.setCursor(Qt.PointingHandCursor)
        hk_tag = (self.app.config.get("hotkeys", {}).get("add_tag") or "").strip()
        btn_ico.setToolTip(f"Akhiran Baru ({hk_tag})" if hk_tag else "Akhiran Baru")
        btn_ico.setStyleSheet(f"background: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 4px;")
        btn_ico.clicked.connect(self.app.open_add_tag_dialog)
        self._btn_add_tag = btn_ico
        self.tag_bar_layout.addWidget(btn_ico)

        for cat in categories:
            sfx = cat.get("suffix", "").upper()
            is_enabled = cat.get("enabled", True)
            btn = QPushButton(sfx)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.PointingHandCursor)
            if is_enabled:
                bg = cat.get("color", THEME["primary"])
                btn.setStyleSheet(f"background-color: {bg}; color: {THEME['text_dark']}; font-weight: bold; font-size: 11px; border: none; border-radius: 4px; padding: 2px 8px;")
            else:
                btn.setStyleSheet(f"background-color: {THEME['bg_card']}; color: {THEME['text_muted']}; font-weight: 500; font-size: 11px; border: 1px solid {THEME['border']}; border-radius: 4px; padding: 2px 8px;")
            btn.clicked.connect(lambda ch=False, s=sfx: self.app.toggle_quick_tag(s))
            self.tag_bar_layout.addWidget(btn)

        self.tag_bar_layout.addStretch(1)

    def update_results(self, prefix: str, words: list, conf_pct: int = 100):
        if not words:
            self.lbl_empty.setText(f"Tidak ada rekomendasi kata berawalan '{prefix}'.")
            self.lbl_empty.show()
            for c in self.word_card_widgets:
                c.hide()
            return

        self.lbl_empty.hide()

        while len(self.word_card_widgets) < len(words):
            card = QtWordCardWidget()
            card.toggle_whitelist.connect(self.app.on_toggle_whitelist)
            card.block_word.connect(self.app.on_block_word)
            self.cards_layout.addWidget(card)
            self.word_card_widgets.append(card)

        for i, card in enumerate(self.word_card_widgets):
            if i < len(words):
                card.update_data(words[i], prefix_upper=prefix.upper(), two_tone=self.two_tone_enabled)
                card.show()
            else:
                card.hide()


# --- Quick 1-Input Add Dialog (Fast Whitelist / Blocklist / Kamus) ---
class QtQuickAddDialog(QDialog):
    """
    Dialog Cepat 1-Input untuk Tambah Kata / Whitelist / Blocklist
    """
    def __init__(self, app, mode="whitelist", parent=None):
        super().__init__(parent)
        self.app = app
        self.mode = mode  # "whitelist", "blocklist", "kamus"

        titles = {
            "whitelist": ("Tambah ke Whitelist", "star_filled", THEME["warning"], "Kata ini akan selalu diprioritaskan di posisi #1 rekomendasi"),
            "blocklist": ("Blokir ke Blocklist", "ban", THEME["danger"], "Kata ini tidak akan pernah direkomendasikan lagi oleh bot"),
            "kamus": ("Tambah Kata ke Kamus", "plus", THEME["primary"], "Daftarkan kata baru ke kamus lengkap")
        }
        title, icon_name, color, hint = titles.get(mode, titles["whitelist"])

        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setFixedSize(350, 160)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME["bg_root"]};
                border: 1px solid {THEME["border_focus"]};
                border-radius: 8px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        ico = QLabel()
        ico.setPixmap(get_qicon(icon_name, size=18, color=color).pixmap(18, 18))
        hdr.addWidget(ico)
        lbl_t = QLabel(title.upper())
        lbl_t.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")
        hdr.addWidget(lbl_t)
        hdr.addStretch(1)
        layout.addLayout(hdr)

        lbl_desc = QLabel(hint)
        lbl_desc.setStyleSheet(f"font-size: 11px; color: {THEME['text_secondary']};")
        layout.addWidget(lbl_desc)

        self.edit_word = QLineEdit()
        self.edit_word.setPlaceholderText("Ketik kata lalu tekan Enter...")
        self.edit_word.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME["bg_card"]};
                color: {THEME["text_primary"]};
                font-size: 14px;
                font-weight: bold;
                border: 1px solid {THEME["border_focus"]};
                border-radius: 5px;
                padding: 6px 10px;
            }}
            QLineEdit:focus {{
                border: 1px solid {color};
            }}
        """)
        self.edit_word.returnPressed.connect(self._do_submit)
        layout.addWidget(self.edit_word)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)

        btn_cancel = QPushButton("Batal")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(28)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["bg_card"]};
                color: {THEME["text_secondary"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
                padding: 2px 12px;
            }}
            QPushButton:hover {{
                background-color: {THEME["bg_hover"]};
                color: {THEME["text_primary"]};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_ok = QPushButton("Simpan")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setFixedHeight(28)
        btn_ok.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {THEME["text_dark"]};
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 2px 14px;
            }}
            QPushButton:hover {{
                background-color: {THEME["accent_neon"] if mode == "kamus" else color};
            }}
        """)
        btn_ok.clicked.connect(self._do_submit)
        btn_box.addWidget(btn_ok)

        layout.addLayout(btn_box)

    def _do_submit(self):
        w = self.edit_word.text().strip().lower()
        if not w:
            return
        if self.mode == "whitelist":
            if not self.app.solver.is_whitelisted(w):
                self.app.solver.whitelist_word(w)
                self.app.show_toast(f"'{w.upper()}' ditambahkan ke Whitelist")
                self.app.tab_kamus.refresh_whitelist()
                if self.app.last_detected_word:
                    self.app.update_results(self.app.last_detected_word)
            else:
                self.app.show_toast(f"'{w.upper()}' sudah ada di Whitelist")
        elif self.mode == "blocklist":
            self.app.solver.blacklist_word(w)
            self.app.show_toast(f"'{w.upper()}' diblokir ke Blocklist")
            self.app.tab_kamus.refresh_blocklist()
            if self.app.last_detected_word:
                self.app.update_results(self.app.last_detected_word)
        elif self.mode == "kamus":
            self.app.on_add_word_quick(w)
        self.accept()


# --- Tab 2: TAGS Tab View ---

class QtBrutalRowWidget(QFrame):
    """
    Baris Tag Mode Brutal dengan Model Card Active/Inactive:
    - Seluruh kartu bertindak sebagai switch visual.
    - Huruf akhiran menggunakan badge berwarna persis dengan Kelola Semua Tag.
    - Mendukung Shift + Click untuk multi-toggle range.
    """
    row_clicked = Signal(int, bool)  # idx, is_shift

    def __init__(self, idx: int, cat_or_sfx, is_active: bool, word_count: int, parent=None):
        super().__init__(parent)
        self.idx = idx
        if isinstance(cat_or_sfx, dict):
            self.cat = cat_or_sfx
            self.sfx = self.cat.get("suffix", "").upper()
            self.color = self.cat.get("color", THEME["primary"])
        else:
            self.cat = {}
            self.sfx = str(cat_or_sfx).upper()
            self.color = THEME["primary"]

        self.is_active = is_active
        self.setFixedHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("BrutalCard")

        self._apply_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        # 1. Badge Akhiran Berwarna (Persis dengan di Kelola Semua Tag)
        bg = self.color
        self.badge_sfx = QLabel(self.sfx)
        self.badge_sfx.setFixedHeight(22)
        if self.is_active:
            self.badge_sfx.setStyleSheet(f"""
                background-color: {bg};
                color: {THEME['text_dark']};
                font-size: 11px;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 3px;
                border: none;
            """)
        else:
            self.badge_sfx.setStyleSheet(f"""
                background-color: {THEME['bg_root']};
                color: {THEME['text_muted']};
                font-size: 11px;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 3px;
                border: 1px solid {THEME['border']};
            """)
        layout.addWidget(self.badge_sfx)
        self.lbl_sfx = self.badge_sfx  # Alias for backward compatibility

        # 2. Counter Jumlah Kata di Kamus
        self.lbl_count = QLabel(f"({word_count} kata)")
        self.lbl_count.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 500;
            color: {THEME['primary'] if self.is_active else THEME['text_muted']};
            border: none;
            background: transparent;
        """)
        layout.addWidget(self.lbl_count)

        layout.addStretch(1)

    def set_active_state(self, is_active: bool):
        self.is_active = is_active
        self._apply_style()
        bg = self.color
        if self.is_active:
            self.badge_sfx.setStyleSheet(f"""
                background-color: {bg};
                color: {THEME['text_dark']};
                font-size: 11px;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 3px;
                border: none;
            """)
            self.lbl_count.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {THEME['primary']}; border: none; background: transparent;")
        else:
            self.badge_sfx.setStyleSheet(f"""
                background-color: {THEME['bg_root']};
                color: {THEME['text_muted']};
                font-size: 11px;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 3px;
                border: 1px solid {THEME['border']};
            """)
            self.lbl_count.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {THEME['text_muted']}; border: none; background: transparent;")

    def _apply_style(self):
        if self.is_active:
            self.setStyleSheet(f"""
                #BrutalCard {{
                    background-color: #162418;
                    border: 1px solid {THEME['primary']};
                    border-radius: 5px;
                }}
                #BrutalCard:hover {{
                    background-color: #1c3020;
                    border-color: {THEME['accent_neon']};
                }}
                #BrutalCard QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                #BrutalCard {{
                    background-color: {THEME['bg_card']};
                    border: 1px solid {THEME['border']};
                    border-radius: 5px;
                }}
                #BrutalCard:hover {{
                    background-color: {THEME['bg_hover']};
                    border-color: {THEME['border_focus']};
                }}
                #BrutalCard QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            is_shift = bool(event.modifiers() & Qt.ShiftModifier)
            self.row_clicked.emit(self.idx, is_shift)
        super().mousePressEvent(event)


class QtCustomTagRowWidget(QFrame):
    """
    Baris Kelola Tag Kustom dengan Drag Handle (≡) untuk reordering instan.
    """
    def __init__(self, idx: int, cat: dict, word_count: int, parent_view, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.cat = cat
        self.parent_view = parent_view
        self.sfx = cat.get("suffix", "").upper()
        self.is_enabled = cat.get("enabled", True)
        self.setFixedHeight(36)
        self.setObjectName("CustomTagCard")
        self.setAcceptDrops(True)

        self._apply_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 8, 0)
        layout.setSpacing(8)

        # 1. Drag Handle (≡)
        self.btn_handle = QLabel("≡")
        self.btn_handle.setFixedSize(20, 24)
        self.btn_handle.setAlignment(Qt.AlignCenter)
        self.btn_handle.setCursor(Qt.SizeVerCursor)
        self.btn_handle.setToolTip("Tahan dan geser untuk memindahkan urutan prioritas tag")
        self.btn_handle.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {THEME['text_secondary']}; border: none; background: transparent;")
        self.btn_handle.mouseMoveEvent = self._start_drag
        layout.addWidget(self.btn_handle)

        # 2. Badge Akhiran Bersih
        bg = cat.get("color", THEME["primary"])
        self.badge_sfx = QLabel(self.sfx)
        self.badge_sfx.setFixedHeight(22)
        self.badge_sfx.setStyleSheet(f"""
            background-color: {bg if self.is_enabled else THEME['bg_root']};
            color: {THEME['text_dark'] if self.is_enabled else THEME['text_muted']};
            font-size: 11px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 3px;
            border: 1px solid {THEME['border'] if not self.is_enabled else 'transparent'};
        """)
        layout.addWidget(self.badge_sfx)
        self.lbl_sfx = self.badge_sfx  # Alias for backward compatibility

        # 3. Counter Jumlah Kata
        lbl_count = QLabel(f"({word_count} kata)")
        lbl_count.setStyleSheet(f"font-size: 11px; color: {THEME['text_secondary']}; border: none; background: transparent;")
        layout.addWidget(lbl_count)

        layout.addStretch(1)

        # 4. Toggle On/Off Switch Button (Icon-based)
        self.btn_toggle = QPushButton()
        self.btn_toggle.setFixedSize(28, 22)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        if self.is_enabled:
            self.btn_toggle.setIcon(get_qicon("toggle_on", size=22, color=THEME["primary"]))
            self.btn_toggle.setToolTip("Tag Aktif (Klik untuk nonaktifkan)")
        else:
            self.btn_toggle.setIcon(get_qicon("toggle_off", size=22, color=THEME["text_muted"]))
            self.btn_toggle.setToolTip("Tag Nonaktif (Klik untuk aktifkan)")
        self.btn_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 3px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {THEME['bg_hover']};
            }}
        """)
        self.btn_toggle.clicked.connect(lambda: self.parent_view.app.on_toggle_tag(self.idx))
        layout.addWidget(self.btn_toggle)

        # 5. Tombol Edit
        self.btn_edit = QPushButton()
        self.btn_edit.setIcon(get_qicon("edit", size=13, color=THEME["text_secondary"]))
        self.btn_edit.setFixedSize(24, 24)
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.setToolTip("Edit Huruf Akhiran")
        self.btn_edit.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {THEME['bg_hover']};
            }}
        """)
        self.btn_edit.clicked.connect(lambda: self.parent_view.app.open_edit_tag_dialog(self.cat))
        layout.addWidget(self.btn_edit)

        # 6. Tombol Hapus
        self.btn_del = QPushButton()
        self.btn_del.setIcon(get_qicon("trash", size=13, color=THEME["text_muted"]))
        self.btn_del.setFixedSize(24, 24)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.setToolTip("Hapus Tag")
        self.btn_del.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: rgba(239, 68, 68, 0.18);
            }}
        """)
        self.btn_del.clicked.connect(lambda: self.parent_view.app.on_delete_tag(self.idx))
        layout.addWidget(self.btn_del)

    def set_enabled_state(self, is_enabled: bool):
        self.is_enabled = is_enabled
        if self.is_enabled:
            self.btn_toggle.setIcon(get_qicon("toggle_on", size=22, color=THEME["primary"]))
            self.btn_toggle.setToolTip("Tag Aktif (Klik untuk nonaktifkan)")
        else:
            self.btn_toggle.setIcon(get_qicon("toggle_off", size=22, color=THEME["text_muted"]))
            self.btn_toggle.setToolTip("Tag Nonaktif (Klik untuk aktifkan)")
        bg = self.cat.get("color", THEME["primary"])
        self.badge_sfx.setStyleSheet(f"""
            background-color: {bg if self.is_enabled else THEME['bg_root']};
            color: {THEME['text_dark'] if self.is_enabled else THEME['text_muted']};
            font-size: 11px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 3px;
            border: 1px solid {THEME['border'] if not self.is_enabled else 'transparent'};
        """)

    def _apply_style(self):
        self.setStyleSheet(f"""
            #CustomTagCard {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 5px;
            }}
            #CustomTagCard:hover {{
                background-color: {THEME['bg_hover']};
                border-color: {THEME['border_focus']};
            }}
            #CustomTagCard QLabel {{
                border: none;
                background: transparent;
            }}
        """)

    def _start_drag(self, event):
        if event.buttons() & Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(self.idx))
            drag.setMimeData(mime)
            drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet(f"""
                #CustomTagCard {{
                    background-color: {THEME['bg_selected']};
                    border: 1px solid {THEME['primary']};
                    border-radius: 5px;
                }}
                #CustomTagCard QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)

    def dragLeaveEvent(self, event):
        self._apply_style()

    def dropEvent(self, event):
        self._apply_style()
        src_text = event.mimeData().text()
        if src_text.isdigit():
            src_idx = int(src_text)
            target_idx = self.idx
            if src_idx != target_idx:
                self.parent_view.app.on_reorder_tag(src_idx, target_idx)
        event.acceptProposedAction()


class QtTagsTabView(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.last_brutal_idx = None
        self.sub_strip = QtSubTabStrip([
            ("custom", "Kelola (0)", "tag"),
            ("brutal", "Brutal", "zap")
        ])
        self.sub_strip.sub_tab_changed.connect(self._on_sub_tab_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(6)
        layout.addWidget(self.sub_strip)

        self.stack_brutal = QWidget()
        self.stack_custom = QWidget()

        layout.addWidget(self.stack_custom, 1)
        layout.addWidget(self.stack_brutal, 1)

        self._build_custom_view()
        self._build_brutal_view()
        self._on_sub_tab_changed("custom")

    def _on_sub_tab_changed(self, sub_id):
        if sub_id == "brutal":
            self.stack_brutal.show()
            self.stack_custom.hide()
            self.refresh_brutal_list()
        else:
            self.stack_brutal.hide()
            self.stack_custom.show()
            self.refresh_custom_list()

    def _build_brutal_view(self):
        layout = QVBoxLayout(self.stack_brutal)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        hdr = QWidget()
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        lbl = QLabel("PRESET MODE BRUTAL")
        lbl.setStyleSheet(f"color: {THEME['primary']}; font-weight: bold; font-size: 11px;")
        h_layout.addWidget(lbl)

        self.lbl_brutal_count = QLabel("(0 Aktif)")
        self.lbl_brutal_count.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        h_layout.addWidget(self.lbl_brutal_count)

        h_layout.addStretch(1)

        # Options Menu Button (...)
        self.btn_brutal_opts = QPushButton()
        self.btn_brutal_opts.setIcon(get_qicon("settings", size=13, color=THEME["text_secondary"]))
        self.btn_brutal_opts.setFixedSize(26, 26)
        self.btn_brutal_opts.setCursor(Qt.PointingHandCursor)
        self.btn_brutal_opts.setToolTip("Aksi Massal Preset Brutal")
        self.btn_brutal_opts.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border"]};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {THEME["bg_hover"]};
                border-color: {THEME["border_focus"]};
            }}
        """)
        self.btn_brutal_opts.clicked.connect(self._show_brutal_options_menu)
        h_layout.addWidget(self.btn_brutal_opts)

        layout.addWidget(hdr)

        self.scroll_brutal = QScrollArea()
        self.scroll_brutal.setWidgetResizable(True)
        self.scroll_brutal.setFrameShape(QFrame.NoFrame)
        self.container_brutal = QWidget()
        self.layout_brutal_items = QVBoxLayout(self.container_brutal)
        self.layout_brutal_items.setContentsMargins(0, 0, 4, 16)
        self.layout_brutal_items.setSpacing(4)
        self.scroll_brutal.setWidget(self.container_brutal)
        layout.addWidget(self.scroll_brutal, 1)

    def _show_brutal_options_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {THEME["bg_card"]};
                color: {THEME["text_primary"]};
                border: 1px solid {THEME["border_focus"]};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 3px;
            }}
            QMenu::item:selected {{
                background-color: {THEME["bg_hover"]};
                color: {THEME["primary"]};
            }}
        """)
        act_all = menu.addAction("Aktifkan Semua Tag (Timpa Preset)")
        act_none = menu.addAction("Matikan Semua Tag (Timpa Preset)")

        action = menu.exec(self.btn_brutal_opts.mapToGlobal(QPoint(0, self.btn_brutal_opts.height() + 2)))
        if action == act_all:
            self._select_all_brutal()
        elif action == act_none:
            self._deselect_all_brutal()

    def _select_all_brutal(self):
        cats = self.app.config.get("custom_trap_endings", [])
        reply = QMessageBox.question(
            self,
            "Konfirmasi Aksi Massal",
            f"Aktifkan semua {len(cats)} tag untuk preset Brutal?\n\nSeleksi preset Brutal Anda saat ini akan tertimpa.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        all_sfx = [c.get("suffix", "").upper() for c in cats]
        self.app.set_brutal_tags_batch(all_sfx)
        self.app.show_toast(f"Semua {len(all_sfx)} tag Brutal diaktifkan")

    def _deselect_all_brutal(self):
        reply = QMessageBox.question(
            self,
            "Konfirmasi Aksi Massal",
            "Matikan seluruh tag di preset Brutal?\n\nSeleksi preset Brutal Anda saat ini akan tertimpa.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.app.set_brutal_tags_batch([])
        self.app.show_toast("Semua tag Brutal dinonaktifkan")

    def refresh_brutal_list(self):
        sb = self.scroll_brutal.verticalScrollBar()
        saved_scroll = sb.value()

        while self.layout_brutal_items.count():
            item = self.layout_brutal_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        brutal_tags = set(self.app.config.get("brutal_mode_tags", ["AMSI", "KSO", "RHU", "TL", "BD"]))
        cats = self.app.config.get("custom_trap_endings", [])

        active_count = sum(1 for c in cats if c.get("suffix", "").upper() in brutal_tags)
        self.lbl_brutal_count.setText(f"({active_count} / {len(cats)} Aktif)")

        for idx, cat in enumerate(cats):
            sfx = cat.get("suffix", "").upper()
            is_active = (sfx in brutal_tags)
            word_count = self.app.solver.count_words_by_suffix(sfx)

            card = QtBrutalRowWidget(idx, cat, is_active, word_count)
            card.row_clicked.connect(self._on_brutal_card_clicked)
            self.layout_brutal_items.addWidget(card)

        self.layout_brutal_items.addStretch(1)
        QTimer.singleShot(0, lambda: sb.setValue(saved_scroll))

    def _on_brutal_card_clicked(self, idx: int, is_shift: bool):
        cats = self.app.config.get("custom_trap_endings", [])
        b_tags = set(self.app.config.get("brutal_mode_tags", []))

        if is_shift and self.last_brutal_idx is not None and 0 <= self.last_brutal_idx < len(cats):
            start = min(self.last_brutal_idx, idx)
            end = max(self.last_brutal_idx, idx)
            clicked_sfx = cats[idx].get("suffix", "").upper()
            target_state = (clicked_sfx not in b_tags)

            for i in range(start, end + 1):
                s = cats[i].get("suffix", "").upper()
                if target_state:
                    b_tags.add(s)
                else:
                    b_tags.discard(s)

            self.app.set_brutal_tags_batch(list(b_tags))
            st = "diaktifkan" if target_state else "dinonaktifkan"
            self.app.show_toast(f"Rentang #{start+1}-#{end+1} {st}")
        else:
            self.last_brutal_idx = idx
            sfx = cats[idx].get("suffix", "").upper()
            self.app.toggle_brutal_tag(sfx)

    def _build_custom_view(self):
        layout = QVBoxLayout(self.stack_custom)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        act_bar = QWidget()
        a_layout = QHBoxLayout(act_bar)
        a_layout.setContentsMargins(0, 0, 0, 0)
        a_layout.setSpacing(6)

        # Dropdown button: Urutkan Semua Tag
        self.btn_sort_menu = QPushButton(" Urutkan Semua")
        self.btn_sort_menu.setIcon(get_qicon("sort", size=13, color=THEME["text_secondary"]))
        self.btn_sort_menu.setFixedHeight(26)
        self.btn_sort_menu.setCursor(Qt.PointingHandCursor)
        self.btn_sort_menu.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_primary']};
                font-size: 11px;
                font-weight: 500;
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 2px 10px;
            }}
            QPushButton:hover {{
                background-color: {THEME['bg_hover']};
                border-color: {THEME['border_focus']};
            }}
        """)

        # Build Sort Menu
        sort_menu = QMenu(self.btn_sort_menu)
        sort_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_primary']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 11px;
            }}
            QMenu::item:selected {{
                background-color: {THEME['primary']};
                color: {THEME['text_dark']};
            }}
        """)

        act_az = sort_menu.addAction("A - Z (Abjad)")
        act_az.triggered.connect(self.app.on_sort_custom_categories_az)

        sort_menu.addSeparator()

        act_most_words = sort_menu.addAction("Kata Terbanyak (Banyak ke Sedikit)")
        act_most_words.triggered.connect(lambda: self.app.on_sort_custom_categories_count(reverse=True))

        act_least_words = sort_menu.addAction("Kata Terdikit (Sedikit ke Banyak)")
        act_least_words.triggered.connect(lambda: self.app.on_sort_custom_categories_count(reverse=False))

        sort_menu.addSeparator()

        act_longest = sort_menu.addAction("Terpanjang (Huruf Akhiran Terpanjang)")
        act_longest.triggered.connect(lambda: self.app.on_sort_custom_categories_length(reverse=True))

        act_shortest = sort_menu.addAction("Terpendek (Huruf Akhiran Terpendek)")
        act_shortest.triggered.connect(lambda: self.app.on_sort_custom_categories_length(reverse=False))

        self.btn_sort_menu.setMenu(sort_menu)
        a_layout.addWidget(self.btn_sort_menu)

        a_layout.addStretch(1)

        btn_add = QPushButton("Tag Baru")
        btn_add.setIcon(get_qicon("plus", size=12, color=THEME["text_dark"]))
        btn_add.setFixedHeight(26)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['primary']};
                color: {THEME['text_dark']};
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-radius: 4px;
                padding: 2px 10px;
            }}
            QPushButton:hover {{
                background-color: {THEME['accent_neon']};
            }}
        """)
        btn_add.clicked.connect(self.app.open_add_tag_dialog)
        a_layout.addWidget(btn_add)

        layout.addWidget(act_bar)

        # Helper info notice
        lbl_hint = QLabel("Toggle aktif di sini dipakai untuk mode Normal (mode Santai otomatis menyaring X, Q, F).")
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 10px; font-style: italic; border: none; background: transparent; padding: 0 2px;")
        layout.addWidget(lbl_hint)

        self.scroll_custom = QScrollArea()
        self.scroll_custom.setWidgetResizable(True)
        self.scroll_custom.setFrameShape(QFrame.NoFrame)
        self.container_custom = QWidget()
        self.layout_custom_items = QVBoxLayout(self.container_custom)
        self.layout_custom_items.setContentsMargins(0, 0, 4, 16)
        self.layout_custom_items.setSpacing(4)
        self.scroll_custom.setWidget(self.container_custom)
        layout.addWidget(self.scroll_custom, 1)

    def refresh_custom_list(self):
        sb = self.scroll_custom.verticalScrollBar()
        saved_scroll = sb.value()

        while self.layout_custom_items.count():
            item = self.layout_custom_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cats = self.app.config.get("custom_trap_endings", [])
        self.sub_strip.update_tab_label("custom", f"Kelola ({len(cats)})")

        for idx, cat in enumerate(cats):
            sfx = cat.get("suffix", "").upper()
            word_count = self.app.solver.count_words_by_suffix(sfx)

            row = QtCustomTagRowWidget(idx, cat, word_count, self)
            self.layout_custom_items.addWidget(row)

        self.layout_custom_items.addStretch(1)
        QTimer.singleShot(0, lambda: sb.setValue(saved_scroll))


# --- Tab 3: KAMUS Tab View ---
class QtBatchAddDialog(QDialog):
    """
    Dialog penambahan kata beruntun (tidak auto-close saat Enter).
    Mendukung penambahan berulang kali ke Whitelist, Blocklist, atau Kamus
    tanpa crash dan dengan input focus otomatis.
    """
    def __init__(self, target_type: str, app, on_added_callback=None, parent=None):
        top_window = parent.window() if parent else None
        super().__init__(top_window)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.target_type = target_type  # "whitelist", "blocklist", "kamus"
        self.app = app
        self.on_added_callback = on_added_callback
        self.added_session_words = []

        self.setWindowTitle({
            "whitelist": "Tambah Kata ke Whitelist",
            "blocklist": "Tambah Kata ke Blocklist",
            "kamus": "Tambah Kata Baru ke Kamus"
        }.get(target_type, "Tambah Kata"))

        self.setFixedSize(390, 290)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border_focus"]};
                border-radius: 8px;
            }}
            QLabel {{
                color: {THEME["text_primary"]};
                border: none;
                background: transparent;
            }}
            QLineEdit {{
                background-color: {THEME["bg_root"]};
                color: {THEME["text_primary"]};
                font-size: 13px;
                font-weight: bold;
                border: 1px solid {THEME["border"]};
                border-radius: 5px;
                padding: 6px 10px;
            }}
            QLineEdit:focus {{
                border-color: {THEME["primary"]};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Header Title
        title_colors = {"whitelist": THEME["warning"], "blocklist": THEME["danger"], "kamus": THEME["primary"]}
        lbl_title = QLabel(self.windowTitle().upper())
        lbl_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {title_colors.get(target_type, THEME['primary'])};")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel({
            "whitelist": "Kata di Whitelist selalu diprioritaskan di posisi #1 rekomendasi.",
            "blocklist": "Kata di Blocklist tidak akan pernah direkomendasikan lagi oleh bot.",
            "kamus": "Kata baru akan divalidasi dan disimpan permanen ke kamus lengkap."
        }.get(target_type, ""))
        lbl_desc.setStyleSheet(f"font-size: 11px; color: {THEME['text_secondary']};")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        # Input row with Submit button
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.edit_input = QLineEdit()
        self.edit_input.setPlaceholderText("Ketik kata lalu tekan Enter...")
        self.edit_input.returnPressed.connect(self._submit_word)
        input_row.addWidget(self.edit_input, 1)

        btn_add = QPushButton(" Tambah")
        btn_add.setIcon(get_qicon("plus", size=11, color=THEME["text_dark"]))
        btn_add.setFixedHeight(30)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {title_colors.get(target_type, THEME['primary'])};
                color: {THEME['text_dark']};
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-radius: 4px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background-color: {THEME['accent_neon']};
            }}
        """)
        btn_add.clicked.connect(self._submit_word)
        input_row.addWidget(btn_add)
        layout.addLayout(input_row)

        # Inline Feedback Message
        self.lbl_feedback = QLabel("Tekan Enter atau klik Tambah untuk memasukkan beruntun.")
        self.lbl_feedback.setStyleSheet(f"font-size: 10px; font-style: italic; color: {THEME['text_muted']};")
        layout.addWidget(self.lbl_feedback)

        # Session history label
        self.lbl_session = QLabel("Ditambahkan sesi ini (0): -")
        self.lbl_session.setStyleSheet(f"font-size: 10px; color: {THEME['text_secondary']};")
        self.lbl_session.setWordWrap(True)
        layout.addWidget(self.lbl_session)

        layout.addStretch(1)

        # Bottom Button: Selesai
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)

        btn_done = QPushButton("Selesai")
        btn_done.setCursor(Qt.PointingHandCursor)
        btn_done.setFixedSize(80, 28)
        btn_done.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_hover']};
                color: {THEME['text_primary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {THEME['border_focus']};
            }}
        """)
        btn_done.clicked.connect(self.accept)
        btn_layout.addWidget(btn_done)
        layout.addLayout(btn_layout)

        # Auto-focus input on open
        QTimer.singleShot(50, self.edit_input.setFocus)

    def _submit_word(self):
        try:
            raw = self.edit_input.text().strip()
            word = "".join([c for c in raw.upper() if c.isalpha()])
            if not word:
                return

            w_lower = word.lower()
            if self.target_type == "whitelist":
                if not self.app.solver.whitelist_word(w_lower):
                    self.lbl_feedback.setText(f"✕ '{word}' sudah terdaftar di Whitelist!")
                    self.lbl_feedback.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {THEME['danger']};")
                    return
                self.lbl_feedback.setText(f"✓ '{word}' berhasil ditambahkan ke Whitelist!")
                self.lbl_feedback.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {THEME['primary']};")
                self.added_session_words.append(word)
            elif self.target_type == "blocklist":
                if not self.app.solver.blacklist_word(w_lower):
                    self.lbl_feedback.setText(f"✕ '{word}' sudah terdaftar di Blocklist!")
                    self.lbl_feedback.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {THEME['danger']};")
                    return
                self.lbl_feedback.setText(f"✓ '{word}' berhasil diblokir!")
                self.lbl_feedback.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {THEME['danger']};")
                self.added_session_words.append(word)
            elif self.target_type == "kamus":
                success, msg = self.app.solver.add_word(w_lower)
                if success:
                    self.lbl_feedback.setText(f"✓ '{word}' berhasil ditambahkan ke Kamus!")
                    self.lbl_feedback.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {THEME['primary']};")
                    self.added_session_words.append(word)
                else:
                    self.lbl_feedback.setText(f"✕ {msg}")
                    self.lbl_feedback.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {THEME['danger']};")
                    return

            # Update session label
            recents = ", ".join(self.added_session_words[-5:])
            self.lbl_session.setText(f"Ditambahkan sesi ini ({len(self.added_session_words)}): {recents}")

            self.edit_input.clear()
            self.edit_input.setFocus()

            if self.on_added_callback:
                self.on_added_callback()
        except Exception as e:
            self.lbl_feedback.setText(f"Error: {e}")
            self.lbl_feedback.setStyleSheet(f"font-size: 11px; color: {THEME['danger']};")


class QtDictionaryTabView(QWidget):
    """
    Tab KAMUS (Manajemen Whitelist, Blocklist, dan Eksplorer Kosakata 147.000+).
    Dilengkapi pencarian filter real-time, indikator badge akhiran di sisi kanan,
    vertical source bars (Ijo KBBI, Biru Contek, Ungu Keduanya), dan auto-focus cursor.
    """
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._search_dictionary)

        self.sub_strip = QtSubTabStrip([
            ("whitelist", "Whitelist", "star_filled"),
            ("blocklist", "Blocklist", "ban"),
            ("explorer", "Eksplorer", "search")
        ])
        self.sub_strip.sub_tab_changed.connect(self._on_sub_tab_changed)

        self.show_word_datetime = bool(self.app.config.get("show_word_datetime", False))
        self.show_word_author = bool(self.app.config.get("show_word_author", False))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(6)
        layout.addWidget(self.sub_strip)

        self.stack_wl = QWidget()
        self.stack_bl = QWidget()
        self.stack_exp = QWidget()

        layout.addWidget(self.stack_wl, 1)
        layout.addWidget(self.stack_bl, 1)
        layout.addWidget(self.stack_exp, 1)

        self._build_whitelist_view()
        self._build_blocklist_view()
        self._build_explorer_view()
        self._on_sub_tab_changed("whitelist")

    def _create_meta_gear_button(self, height: int = 26) -> QPushButton:
        btn = QPushButton()
        btn.setIcon(get_qicon("settings", size=12, color=THEME["text_secondary"]))
        btn.setFixedSize(height, height)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Opsi tampilan metadata (Waktu & Author)")
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {THEME['bg_hover']}; border-color: {THEME['border_focus']}; }}"
        )
        btn.clicked.connect(lambda ch=False, b=btn: self._open_meta_menu(b))
        return btn

    def _open_meta_menu(self, anchor_btn: QPushButton):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_primary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 4px;
                font-size: 11px;
            }}
            QMenu::item {{
                padding: 5px 14px 5px 10px;
                border-radius: 3px;
            }}
            QMenu::item:selected {{
                background-color: {THEME['bg_hover']};
                color: {THEME['primary']};
            }}
        """)
        act_dt = menu.addAction("Tampilkan Waktu")
        act_dt.setCheckable(True)
        act_dt.setChecked(self.show_word_datetime)
        act_dt.triggered.connect(self._toggle_show_datetime)

        act_author = menu.addAction("Tampilkan Author")
        act_author.setCheckable(True)
        act_author.setChecked(self.show_word_author)
        act_author.triggered.connect(self._toggle_show_author)

        menu.exec(anchor_btn.mapToGlobal(QPoint(0, anchor_btn.height() + 2)))

    def _refresh_active_subtab(self):
        curr_sub = getattr(self.sub_strip, "active_sub", "whitelist")
        if curr_sub == "whitelist":
            self.refresh_whitelist()
        elif curr_sub == "blocklist":
            self.refresh_blocklist()
        elif self.edit_exp_search.text().strip() or self.src_filter == "custom":
            self._search_dictionary()

    def _toggle_show_datetime(self):
        self.show_word_datetime = not self.show_word_datetime
        self.app.config["show_word_datetime"] = self.show_word_datetime
        self.app.save_config_debounced()
        self._refresh_active_subtab()

    def _toggle_show_author(self):
        self.show_word_author = not self.show_word_author
        self.app.config["show_word_author"] = self.show_word_author
        self.app.save_config_debounced()
        self._refresh_active_subtab()

    def _append_word_meta_pills(self, row_layout, word: str, scope: str = "auto", added_by: str = "", dt_str: str = ""):
        if self.show_word_datetime:
            raw_dt = dt_str or self.app.solver.get_word_datetime(word, scope=scope)
            dt_short, dt_tip = format_word_datetime(raw_dt)
            if dt_short:
                row_layout.addWidget(make_meta_pill(dt_short, dt_tip))
        if self.show_word_author:
            author = (added_by or "").strip()
            if not author and self.app.config.get("storage_mode", "txt") == "supabase":
                rec = self.app.solver.db_records.get(word.lower(), {})
                author = (rec.get("added_by") or "").strip()
            if author:
                row_layout.addWidget(make_meta_pill(author, f"Ditambahkan oleh {author}"))

    def focus_active_search(self):
        curr_sub = getattr(self.sub_strip, "active_sub", "whitelist")
        if curr_sub == "whitelist":
            self.edit_filter_wl.setFocus()
        elif curr_sub == "blocklist":
            self.edit_filter_bl.setFocus()
        else:
            self.edit_exp_search.setFocus()

    def _on_sub_tab_changed(self, sub_id):
        self.stack_wl.hide()
        self.stack_bl.hide()
        self.stack_exp.hide()
        if sub_id == "whitelist":
            self.stack_wl.show()
            self.refresh_whitelist()
            QTimer.singleShot(50, self.edit_filter_wl.setFocus)
        elif sub_id == "blocklist":
            self.stack_bl.show()
            self.refresh_blocklist()
            QTimer.singleShot(50, self.edit_filter_bl.setFocus)
        else:
            self.stack_exp.show()
            if not self.edit_exp_search.text().strip():
                self._show_explorer_welcome()
            QTimer.singleShot(50, self.edit_exp_search.setFocus)

    # -------------------------------------------------------------
    # 1. SUB-TAB WHITELIST
    # -------------------------------------------------------------
    def _build_whitelist_view(self):
        layout = QVBoxLayout(self.stack_wl)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header toolbar
        hdr = QWidget()
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        self.lbl_wl_count = QLabel("WHITELIST (0)")
        self.lbl_wl_count.setStyleSheet(f"color: {THEME['warning']}; font-weight: bold; font-size: 11px;")
        h_layout.addWidget(self.lbl_wl_count)
        h_layout.addStretch(1)

        self.wl_sort_mode = "default"
        self.btn_wl_sort = QPushButton("A-Z")
        self.btn_wl_sort.setFixedHeight(26)
        self.btn_wl_sort.setCursor(Qt.PointingHandCursor)
        self.btn_wl_sort.setToolTip("Urutan daftar: A-Z / Terbaru ditambahkan")
        self.btn_wl_sort.clicked.connect(self._toggle_wl_sort)
        self._update_sort_button_style(self.btn_wl_sort, self.wl_sort_mode)
        h_layout.addWidget(self.btn_wl_sort)
        self.btn_wl_gear = self._create_meta_gear_button(26)
        h_layout.addWidget(self.btn_wl_gear)

        # Tombol Tambah (tanpa '+')
        btn_add = QPushButton(" Tambah")
        btn_add.setIcon(get_qicon("plus", size=12, color=THEME["text_dark"]))
        btn_add.setFixedHeight(26)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['warning']};
                color: {THEME['text_dark']};
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-radius: 4px;
                padding: 2px 10px;
            }}
            QPushButton:hover {{
                background-color: #fbbf24;
            }}
        """)
        btn_add.clicked.connect(self._open_add_whitelist_dialog)
        h_layout.addWidget(btn_add)
        layout.addWidget(hdr)

        # Real-time search filter input
        self.edit_filter_wl = QLineEdit()
        self.edit_filter_wl.setPlaceholderText("Filter kata whitelist...")
        self.edit_filter_wl.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_primary']};
                font-size: 11px;
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QLineEdit:focus {{
                border-color: {THEME['warning']};
            }}
        """)
        self.edit_filter_wl.textChanged.connect(self._filter_whitelist_items)
        layout.addWidget(self.edit_filter_wl)

        # Scroll area for items
        self.scroll_wl = QScrollArea()
        self.scroll_wl.setWidgetResizable(True)
        self.scroll_wl.setFrameShape(QFrame.NoFrame)
        self.scroll_wl.setStyleSheet("background: transparent; border: none;")
        self.container_wl = QWidget()
        self.layout_wl_items = QVBoxLayout(self.container_wl)
        self.layout_wl_items.setContentsMargins(0, 0, 4, 16)
        self.layout_wl_items.setSpacing(4)
        self.scroll_wl.setWidget(self.container_wl)
        layout.addWidget(self.scroll_wl, 1)

    def _open_add_whitelist_dialog(self):
        dlg = QtBatchAddDialog("whitelist", self.app, on_added_callback=self.refresh_whitelist, parent=self.window())
        dlg.exec()

    def _update_sort_button_style(self, btn: QPushButton, sort_mode: str):
        is_newest = (sort_mode == "newest")
        btn.setText("Terbaru" if is_newest else "A-Z")
        if is_newest:
            btn.setStyleSheet(
                f"background-color: rgba(56, 217, 118, 0.18); color: {THEME['primary']}; "
                f"font-size: 10px; font-weight: bold; border: 1px solid {THEME['primary']}; "
                f"border-radius: 4px; padding: 2px 8px;"
            )
        else:
            btn.setStyleSheet(
                f"background-color: {THEME['bg_card']}; color: {THEME['text_secondary']}; "
                f"font-size: 10px; font-weight: 500; border: 1px solid {THEME['border']}; "
                f"border-radius: 4px; padding: 2px 8px;"
            )

    def _sort_words_by_mode(self, words: list, scope: str, sort_mode: str) -> list:
        if sort_mode != "newest":
            return sorted(words)
        solver = self.app.solver
        def _key(w):
            ts_val = solver._parse_iso_ts(solver.get_word_datetime(w, scope=scope))
            if ts_val is not None:
                return (0, -ts_val, w)
            return (1, 0.0, w)
        return sorted(words, key=_key)

    def _toggle_wl_sort(self):
        self.wl_sort_mode = "newest" if self.wl_sort_mode == "default" else "default"
        self._update_sort_button_style(self.btn_wl_sort, self.wl_sort_mode)
        self.refresh_whitelist()

    def refresh_whitelist(self):
        v_scroll = self.scroll_wl.verticalScrollBar().value() if hasattr(self, "scroll_wl") else 0
        wl_words = self._sort_words_by_mode(list(self.app.solver.whitelisted_words), "whitelist", getattr(self, "wl_sort_mode", "default"))
        self.lbl_wl_count.setText(f"WHITELIST ({len(wl_words)})")
        self.sub_strip.update_tab_label("whitelist", f"Whitelist ({len(wl_words)})")
        query = self.edit_filter_wl.text().strip().lower() if hasattr(self, "edit_filter_wl") else ""
        if query:
            filtered = [w for w in wl_words if query in w.lower()]
            self._render_whitelist_rows(filtered)
        else:
            self._render_whitelist_rows(wl_words)
        if hasattr(self, "scroll_wl"):
            QTimer.singleShot(10, lambda: self.scroll_wl.verticalScrollBar().setValue(v_scroll))

    def _filter_whitelist_items(self, text):
        query = text.strip().lower()
        all_words = self._sort_words_by_mode(list(self.app.solver.whitelisted_words), "whitelist", getattr(self, "wl_sort_mode", "default"))
        if query:
            filtered = [w for w in all_words if query in w.lower()]
        else:
            filtered = all_words
        self._render_whitelist_rows(filtered)

    def _render_whitelist_rows(self, words: list):
        while self.layout_wl_items.count():
            item = self.layout_wl_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not words:
            lbl_empty = QLabel("Belum ada kata di Whitelist.\nKata di Whitelist selalu diprioritaskan di posisi #1 rekomendasi.")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 11px; font-style: italic; padding: 30px 10px; border: none;")
            self.layout_wl_items.addWidget(lbl_empty)
            return

        cats = self.app.config.get("custom_trap_endings", [])

        for w in words:
            row = QFrame()
            row.setFixedHeight(34)
            row.setObjectName("WlRow")
            row.setStyleSheet(f"""
                #WlRow {{
                    background-color: {THEME['bg_card']};
                    border: 1px solid {THEME['border']};
                    border-radius: 4px;
                }}
                #WlRow:hover {{
                    background-color: {THEME['bg_hover']};
                    border-color: {THEME['border_focus']};
                }}
                #WlRow QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            r_l = QHBoxLayout(row)
            r_l.setContentsMargins(10, 0, 8, 0)
            r_l.setSpacing(8)

            lbl = QLabel(w.upper())
            lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['text_primary']};")
            r_l.addWidget(lbl)

            r_l.addStretch(1)

            # Indikator Whitelist row datetime + added_by (sesuai toggle)
            self._append_word_meta_pills(r_l, w, scope="whitelist")

            # Indikator akhiran persis di paling kanan (seperti LIVE)
            for c in cats:
                sfx = c.get("suffix", "").upper()
                if sfx and w.upper().endswith(sfx):
                    bg = c.get("color", THEME["primary"])
                    b_lbl = QLabel(sfx)
                    b_lbl.setFixedHeight(20)
                    b_lbl.setStyleSheet(f"background-color: {bg}; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; padding: 1px 6px; border-radius: 3px;")
                    r_l.addWidget(b_lbl)
                    break

            # Tombol trash persis disamaratakan
            btn_del = QPushButton()
            btn_del.setFixedSize(24, 24)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setIcon(get_qicon("trash", size=13, color=THEME["danger"]))
            btn_del.setToolTip("Hapus dari Whitelist")
            btn_del.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    background-color: rgba(239, 68, 68, 0.18);
                }}
            """)
            btn_del.clicked.connect(lambda ch=False, word=w: self._remove_wl_word(word))
            r_l.addWidget(btn_del)

            self.layout_wl_items.addWidget(row)

        self.layout_wl_items.addStretch(1)

    def _remove_wl_word(self, word):
        self.app.solver.unwhitelist_word(word)
        if self.app.last_detected_word:
            self.app.update_results(self.app.last_detected_word)
        self.refresh_whitelist()
        self.app.show_toast(f"'{word.upper()}' dihapus dari Whitelist")

    # -------------------------------------------------------------
    # 2. SUB-TAB BLOCKLIST
    # -------------------------------------------------------------
    def _build_blocklist_view(self):
        layout = QVBoxLayout(self.stack_bl)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header toolbar
        hdr = QWidget()
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        self.lbl_bl_count = QLabel("BLOCKLIST (0)")
        self.lbl_bl_count.setStyleSheet(f"color: {THEME['danger']}; font-weight: bold; font-size: 11px;")
        h_layout.addWidget(self.lbl_bl_count)
        h_layout.addStretch(1)

        self.bl_sort_mode = "default"
        self.btn_bl_sort = QPushButton("A-Z")
        self.btn_bl_sort.setFixedHeight(26)
        self.btn_bl_sort.setCursor(Qt.PointingHandCursor)
        self.btn_bl_sort.setToolTip("Urutan daftar: A-Z / Terbaru ditambahkan")
        self.btn_bl_sort.clicked.connect(self._toggle_bl_sort)
        self._update_sort_button_style(self.btn_bl_sort, self.bl_sort_mode)
        h_layout.addWidget(self.btn_bl_sort)
        self.btn_bl_gear = self._create_meta_gear_button(26)
        h_layout.addWidget(self.btn_bl_gear)

        # Tombol Blokir Kata (tanpa '+')
        btn_add = QPushButton(" Tambah")
        btn_add.setIcon(get_qicon("plus", size=12, color="#ffffff"))
        btn_add.setFixedHeight(26)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['danger']};
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-radius: 4px;
                padding: 2px 10px;
            }}
            QPushButton:hover {{
                background-color: #dc2626;
            }}
        """)
        btn_add.clicked.connect(self._open_add_blocklist_dialog)
        h_layout.addWidget(btn_add)
        layout.addWidget(hdr)

        # Real-time search filter input
        self.edit_filter_bl = QLineEdit()
        self.edit_filter_bl.setPlaceholderText("Filter kata diblokir...")
        self.edit_filter_bl.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_primary']};
                font-size: 11px;
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QLineEdit:focus {{
                border-color: {THEME['danger']};
            }}
        """)
        self.edit_filter_bl.textChanged.connect(self._filter_blocklist_items)
        layout.addWidget(self.edit_filter_bl)

        # Scroll area for items
        self.scroll_bl = QScrollArea()
        self.scroll_bl.setWidgetResizable(True)
        self.scroll_bl.setFrameShape(QFrame.NoFrame)
        self.scroll_bl.setStyleSheet("background: transparent; border: none;")
        self.container_bl = QWidget()
        self.layout_bl_items = QVBoxLayout(self.container_bl)
        self.layout_bl_items.setContentsMargins(0, 0, 4, 16)
        self.layout_bl_items.setSpacing(4)
        self.scroll_bl.setWidget(self.container_bl)
        layout.addWidget(self.scroll_bl, 1)

    def _open_add_blocklist_dialog(self):
        dlg = QtBatchAddDialog("blocklist", self.app, on_added_callback=self.refresh_blocklist, parent=self.window())
        dlg.exec()

    def _toggle_bl_sort(self):
        self.bl_sort_mode = "newest" if self.bl_sort_mode == "default" else "default"
        self._update_sort_button_style(self.btn_bl_sort, self.bl_sort_mode)
        self.refresh_blocklist()

    def refresh_blocklist(self):
        v_scroll = self.scroll_bl.verticalScrollBar().value() if hasattr(self, "scroll_bl") else 0
        bl_words = self._sort_words_by_mode(list(self.app.solver.blacklisted_words), "blacklist", getattr(self, "bl_sort_mode", "default"))
        self.lbl_bl_count.setText(f"BLOCKLIST ({len(bl_words)})")
        self.sub_strip.update_tab_label("blocklist", f"Blocklist ({len(bl_words)})")
        query = self.edit_filter_bl.text().strip().lower() if hasattr(self, "edit_filter_bl") else ""
        if query:
            filtered = [w for w in bl_words if query in w.lower()]
            self._render_blocklist_rows(filtered)
        else:
            self._render_blocklist_rows(bl_words)
        if hasattr(self, "scroll_bl"):
            QTimer.singleShot(10, lambda: self.scroll_bl.verticalScrollBar().setValue(v_scroll))

    def _filter_blocklist_items(self, text):
        query = text.strip().lower()
        all_words = self._sort_words_by_mode(list(self.app.solver.blacklisted_words), "blacklist", getattr(self, "bl_sort_mode", "default"))
        if query:
            filtered = [w for w in all_words if query in w.lower()]
        else:
            filtered = all_words
        self._render_blocklist_rows(filtered)

    def _render_blocklist_rows(self, words: list):
        while self.layout_bl_items.count():
            item = self.layout_bl_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not words:
            lbl_empty = QLabel("Belum ada kata di Blocklist.\nKata yang diblokir tidak akan pernah direkomendasikan bot.")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 11px; font-style: italic; padding: 30px 10px; border: none;")
            self.layout_bl_items.addWidget(lbl_empty)
            return

        cats = self.app.config.get("custom_trap_endings", [])

        for w in words:
            row = QFrame()
            row.setFixedHeight(34)
            row.setObjectName("BlRow")
            row.setStyleSheet(f"""
                #BlRow {{
                    background-color: {THEME['bg_card']};
                    border: 1px solid {THEME['border']};
                    border-radius: 4px;
                }}
                #BlRow:hover {{
                    background-color: {THEME['bg_hover']};
                    border-color: {THEME['border_focus']};
                }}
                #BlRow QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            r_l = QHBoxLayout(row)
            r_l.setContentsMargins(10, 0, 8, 0)
            r_l.setSpacing(8)

            lbl = QLabel(w.upper())
            lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['text_primary']};")
            r_l.addWidget(lbl)

            r_l.addStretch(1)

            # Indikator Blocklist row datetime + added_by (sesuai toggle)
            self._append_word_meta_pills(r_l, w, scope="blacklist")

            # Indikator akhiran persis di paling kanan (seperti LIVE)
            for c in cats:
                sfx = c.get("suffix", "").upper()
                if sfx and w.upper().endswith(sfx):
                    bg = c.get("color", THEME["primary"])
                    b_lbl = QLabel(sfx)
                    b_lbl.setFixedHeight(20)
                    b_lbl.setStyleSheet(f"background-color: {bg}; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; padding: 1px 6px; border-radius: 3px;")
                    r_l.addWidget(b_lbl)
                    break

            # Tombol trash persis disamaratakan
            btn_del = QPushButton()
            btn_del.setFixedSize(24, 24)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setIcon(get_qicon("trash", size=13, color=THEME["danger"]))
            btn_del.setToolTip("Hapus dari Blocklist (Pulihkan)")
            btn_del.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    background-color: rgba(239, 68, 68, 0.18);
                }}
            """)
            btn_del.clicked.connect(lambda ch=False, word=w: self._remove_bl_word(word))
            r_l.addWidget(btn_del)

            self.layout_bl_items.addWidget(row)

        self.layout_bl_items.addStretch(1)

    def _remove_bl_word(self, word):
        self.app.solver.unblacklist_word(word)
        if self.app.last_detected_word:
            self.app.update_results(self.app.last_detected_word)
        self.refresh_blocklist()
        self.app.show_toast(f"'{word.upper()}' dipulihkan dari Blocklist")

    # -------------------------------------------------------------
    # 3. SUB-TAB EKSPLORER
    # -------------------------------------------------------------
    def _build_explorer_view(self):
        layout = QVBoxLayout(self.stack_exp)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Toolbar Row 1: Search mode + Search input + Add new word button (tanpa '+')
        tb1 = QWidget()
        tb1_layout = QHBoxLayout(tb1)
        tb1_layout.setContentsMargins(0, 0, 0, 0)
        tb1_layout.setSpacing(4)

        self.combo_search_mode = QComboBox()
        self.combo_search_mode.addItems(["Awalan", "Akhiran", "Mengandung"])
        self.combo_search_mode.setCurrentIndex(1)
        self.combo_search_mode.setFixedHeight(26)
        self.combo_search_mode.setFixedWidth(90)
        self.combo_search_mode.setStyleSheet(f"""
            QComboBox {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_primary']};
                font-size: 11px;
                font-weight: 500;
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding-left: 6px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_primary']};
                selection-background-color: {THEME['primary']};
                selection-color: {THEME['text_dark']};
                border: 1px solid {THEME['border']};
            }}
        """)
        self.combo_search_mode.currentIndexChanged.connect(self._on_search_params_changed)
        tb1_layout.addWidget(self.combo_search_mode)

        self.edit_exp_search = QLineEdit()
        self.edit_exp_search.setPlaceholderText("Cari kosakata...")
        self.edit_exp_search.setFixedHeight(26)
        self.edit_exp_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_primary']};
                font-size: 11px;
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 2px 8px;
            }}
            QLineEdit:focus {{
                border-color: {THEME['primary']};
            }}
        """)
        self.edit_exp_search.textChanged.connect(self._on_search_text_changed)
        self.edit_exp_search.returnPressed.connect(self._search_dictionary)
        tb1_layout.addWidget(self.edit_exp_search, 1)

        btn_add = QPushButton(" Kata Baru")
        btn_add.setIcon(get_qicon("plus", size=11, color=THEME["text_dark"]))
        btn_add.setFixedHeight(26)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setToolTip("Tambah kata baru ke kamus lengkap")
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['primary']};
                color: {THEME['text_dark']};
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-radius: 4px;
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                background-color: {THEME['accent_neon']};
            }}
        """)
        btn_add.clicked.connect(self._open_add_kamus_dialog)
        tb1_layout.addWidget(btn_add)
        layout.addWidget(tb1)

        # Toolbar Row 2: Source filter buttons with MATCHING COLORS!
        # KBBI = Ijo (#38d976), Contek = Biru (#38bdf8), Semua & Irisan = Ungu (#c084fc)
        tb2 = QWidget()
        tb2_layout = QHBoxLayout(tb2)
        tb2_layout.setContentsMargins(0, 0, 0, 0)
        tb2_layout.setSpacing(4)

        self.src_filter = "all"  # "all", "kbbi", "contek", "both"
        self.is_exclusive_source = self.app.config.get("dict_filter_exclusive", False)

        self.btn_src_all = QPushButton("Semua")
        self.btn_src_kbbi = QPushButton("KBBI")
        self.btn_src_contek = QPushButton("Contek")
        self.btn_src_both = QPushButton("KBBI + Contek")
        self.btn_src_custom = QPushButton("Kamus+")

        for b, sf in [
            (self.btn_src_all, "all"),
            (self.btn_src_kbbi, "kbbi"),
            (self.btn_src_contek, "contek"),
            (self.btn_src_both, "both"),
            (self.btn_src_custom, "custom"),
        ]:
            b.setFixedHeight(22)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda ch=False, s=sf: self._set_source_filter(s))
            tb2_layout.addWidget(b)

        # Mode Filter Switch: Inklusif vs Murni Saja (Eksklusif)
        self.btn_mode_toggle = QPushButton("Inklusif" if not self.is_exclusive_source else "Murni Saja")
        self.btn_mode_toggle.setFixedHeight(22)
        self.btn_mode_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_mode_toggle.setToolTip(
            "Mode Filter Sumber: Inklusif (Menampilkan semua kata di basis data ini termasuk yang beririsan) / "
            "Murni Saja (Hanya kata yang khusus ada di kamus ini tanpa irisan). Klik untuk beralih."
        )
        self.btn_mode_toggle.clicked.connect(self._toggle_source_mode)
        tb2_layout.addWidget(self.btn_mode_toggle)

        self.exp_sort_mode = "default"
        self.btn_exp_sort = QPushButton("A-Z")
        self.btn_exp_sort.setFixedHeight(22)
        self.btn_exp_sort.setCursor(Qt.PointingHandCursor)
        self.btn_exp_sort.setToolTip("Urutan hasil: A-Z / Terbaru ditambahkan")
        self.btn_exp_sort.clicked.connect(self._toggle_exp_sort)
        self._update_sort_button_style(self.btn_exp_sort, self.exp_sort_mode)
        tb2_layout.addWidget(self.btn_exp_sort)
        self.btn_exp_gear = self._create_meta_gear_button(22)
        tb2_layout.addWidget(self.btn_exp_gear)

        self._update_src_buttons()

        tb2_layout.addStretch(1)

        self.lbl_exp_status = QLabel("")
        self.lbl_exp_status.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 10px; font-style: italic; border: none; background: transparent;")
        tb2_layout.addWidget(self.lbl_exp_status)
        layout.addWidget(tb2)

        # Results scroll area
        self.scroll_exp = QScrollArea()
        self.scroll_exp.setWidgetResizable(True)
        self.scroll_exp.setFrameShape(QFrame.NoFrame)
        self.scroll_exp.setStyleSheet("background: transparent; border: none;")
        self.container_exp = QWidget()
        self.layout_exp_items = QVBoxLayout(self.container_exp)
        self.layout_exp_items.setContentsMargins(0, 0, 4, 16)
        self.layout_exp_items.setSpacing(4)
        self.scroll_exp.setWidget(self.container_exp)
        layout.addWidget(self.scroll_exp, 1)

    def _open_add_kamus_dialog(self):
        dlg = QtBatchAddDialog("kamus", self.app, on_added_callback=self._search_dictionary, parent=self.window())
        dlg.exec()

    def _set_source_filter(self, sf: str):
        self.src_filter = sf
        self._update_src_buttons()
        self._search_dictionary()

    def _toggle_source_mode(self):
        self.is_exclusive_source = not self.is_exclusive_source
        self.app.config["dict_filter_exclusive"] = self.is_exclusive_source
        self.app.save_config_debounced()
        self.btn_mode_toggle.setText("Inklusif" if not self.is_exclusive_source else "Murni Saja")
        self._update_src_buttons()
        self._search_dictionary()
        mode_str = "Murni Saja (Eksklusif)" if self.is_exclusive_source else "Inklusif (Gabungan)"
        self.app.show_toast(f"Mode Sumber: {mode_str}")

    def _update_src_buttons(self):
        # Matching Colors:
        # Semua: Ungu (#c084fc)
        # KBBI: Ijo (#38d976)
        # Contek: Biru (#38bdf8)
        # KBBI + Contek: Ungu (#c084fc)
        if self.src_filter == "all":
            self.btn_src_all.setStyleSheet("background-color: rgba(192, 132, 252, 0.25); color: #c084fc; font-size: 10px; font-weight: bold; border: 1px solid #c084fc; border-radius: 3px; padding: 1px 8px;")
        else:
            self.btn_src_all.setStyleSheet(f"background-color: {THEME['bg_card']}; color: {THEME['text_muted']}; font-size: 10px; border: 1px solid {THEME['border']}; border-radius: 3px; padding: 1px 8px;")

        if self.src_filter == "kbbi":
            self.btn_src_kbbi.setStyleSheet("background-color: rgba(56, 217, 118, 0.25); color: #38d976; font-size: 10px; font-weight: bold; border: 1px solid #38d976; border-radius: 3px; padding: 1px 8px;")
        else:
            self.btn_src_kbbi.setStyleSheet(f"background-color: {THEME['bg_card']}; color: #556b58; font-size: 10px; border: 1px solid {THEME['border']}; border-radius: 3px; padding: 1px 8px;")

        if self.src_filter == "contek":
            self.btn_src_contek.setStyleSheet("background-color: rgba(56, 189, 248, 0.25); color: #38bdf8; font-size: 10px; font-weight: bold; border: 1px solid #38bdf8; border-radius: 3px; padding: 1px 8px;")
        else:
            self.btn_src_contek.setStyleSheet(f"background-color: {THEME['bg_card']}; color: #556b58; font-size: 10px; border: 1px solid {THEME['border']}; border-radius: 3px; padding: 1px 8px;")

        if self.src_filter == "both":
            self.btn_src_both.setStyleSheet("background-color: rgba(192, 132, 252, 0.25); color: #c084fc; font-size: 10px; font-weight: bold; border: 1px solid #c084fc; border-radius: 3px; padding: 1px 8px;")
        else:
            self.btn_src_both.setStyleSheet(f"background-color: {THEME['bg_card']}; color: #556b58; font-size: 10px; border: 1px solid {THEME['border']}; border-radius: 3px; padding: 1px 8px;")

        if hasattr(self, "btn_src_custom"):
            if self.src_filter == "custom":
                self.btn_src_custom.setStyleSheet(f"background-color: rgba(245, 158, 11, 0.22); color: {THEME['warning']}; font-size: 10px; font-weight: bold; border: 1px solid {THEME['warning']}; border-radius: 3px; padding: 1px 8px;")
            else:
                self.btn_src_custom.setStyleSheet(f"background-color: {THEME['bg_card']}; color: #556b58; font-size: 10px; border: 1px solid {THEME['border']}; border-radius: 3px; padding: 1px 8px;")

        if hasattr(self, "btn_mode_toggle"):
            if self.is_exclusive_source:
                self.btn_mode_toggle.setStyleSheet("background-color: rgba(243, 139, 168, 0.18); color: #f38ba8; font-size: 10px; font-weight: bold; border: 1px solid #f38ba8; border-radius: 3px; padding: 1px 6px;")
            else:
                self.btn_mode_toggle.setStyleSheet(f"background-color: {THEME['bg_card']}; color: {THEME['text_secondary']}; font-size: 10px; font-weight: 500; border: 1px dashed {THEME['border']}; border-radius: 3px; padding: 1px 6px;")

    def _toggle_exp_sort(self):
        self.exp_sort_mode = "newest" if self.exp_sort_mode == "default" else "default"
        self._update_sort_button_style(self.btn_exp_sort, self.exp_sort_mode)
        self._search_dictionary()

    def _on_search_params_changed(self):
        self._search_dictionary()

    def _on_search_text_changed(self, text):
        self._search_timer.start(250)

    def _show_explorer_welcome(self):
        while self.layout_exp_items.count():
            item = self.layout_exp_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.lbl_exp_status.setText("")

        # Overview Stats Card
        stats_box = QFrame()
        stats_box.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 6px; padding: 12px;")
        sb_layout = QVBoxLayout(stats_box)
        sb_layout.setSpacing(8)

        lbl_head = QLabel("EKSPLORASI KOSAKATA LENGKAP")
        lbl_head.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {THEME['primary']}; border: none;")
        sb_layout.addWidget(lbl_head)

        total_cnt = len(getattr(self.app.solver, "words", []))
        kbbi_cnt = len(getattr(self.app.solver, "kbbi_set", []))
        contek_cnt = len(getattr(self.app.solver, "contek_set", []))

        lbl_info = QLabel(
            f"• Total Kosakata Aktif: {total_cnt:,} kata\n"
            f"• Basis KBBI VI Baku: {kbbi_cnt:,} kata\n"
            f"• Basis Game & Slang: {contek_cnt:,} kata"
        )
        lbl_info.setStyleSheet(f"font-size: 11px; color: {THEME['text_secondary']}; line-height: 1.4; border: none;")
        sb_layout.addWidget(lbl_info)

        lbl_tips = QLabel("Ketik huruf di kolom pencarian untuk menemukan kata berdasarkan Awalan, Akhiran, atau Mengandung.\n"
                          "Indikator warna bar: Ijo = KBBI, Biru = Contek, Ungu = KBBI + Contek.")
        lbl_tips.setStyleSheet(f"font-size: 10px; font-style: italic; color: {THEME['text_muted']}; border: none;")
        lbl_tips.setWordWrap(True)
        sb_layout.addWidget(lbl_tips)

        self.layout_exp_items.addWidget(stats_box)
        self.layout_exp_items.addStretch(1)

    def _search_dictionary(self):
        query = self.edit_exp_search.text().strip().lower()
        if not query and self.src_filter != "custom":
            self._show_explorer_welcome()
            return

        mode_map = {0: "prefix", 1: "suffix", 2: "contains"}
        st = mode_map.get(self.combo_search_mode.currentIndex(), "prefix")

        if self.src_filter == "kbbi":
            sf = "kbbi_only" if self.is_exclusive_source else "kbbi"
        elif self.src_filter == "contek":
            sf = "contek_only" if self.is_exclusive_source else "contek"
        else:
            sf = self.src_filter

        results, total_count = self.app.solver.search_dictionary(
            query=query,
            search_type=st,
            source_filter=sf,
            limit=40,
            sort_by=getattr(self, "exp_sort_mode", "default")
        )

        while self.layout_exp_items.count():
            item = self.layout_exp_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.lbl_exp_status.setText(f"{min(len(results), 40)} dari {total_count} kata")

        if not results:
            lbl_empty = QLabel(f"Tidak ada kata yang cocok dengan '{query}'.")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 11px; font-style: italic; padding: 30px; border: none;")
            self.layout_exp_items.addWidget(lbl_empty)
            return

        cats = self.app.config.get("custom_trap_endings", [])
        wl_set = self.app.solver.whitelisted_words
        bl_set = self.app.solver.blacklisted_words

        for r in results:
            w = r["word"]
            w_lower = w.lower()
            is_wl = (w_lower in wl_set)
            is_bl = (w_lower in bl_set)
            status_text = r.get("status", "")

            # Tentukan warna bar vertikal:
            # Ijo untuk KBBI, Biru untuk Contek, Ungu untuk KBBI + Contek
            if "KBBI" in status_text and "Contek" in status_text:
                bar_color = "#c084fc"  # Ungu
                bar_tip = "Sumber: KBBI + Contek (Keduanya)"
            elif r.get("is_db_custom"):
                bar_color = THEME["warning"]
                bar_tip = "Sumber: Database Kamus+ (Tambahan Grup)"
            elif "KBBI" in status_text:
                bar_color = "#38d976"  # Ijo
                bar_tip = "Sumber: Kamus Besar Bahasa Indonesia (KBBI VI)"
            elif "Contek" in status_text:
                bar_color = "#38bdf8"  # Biru
                bar_tip = "Sumber: Basis Data Sambung Kata Roblox"
            else:
                bar_color = THEME["text_muted"]
                bar_tip = f"Sumber: {status_text}"

            card = QFrame()
            card.setFixedHeight(34)
            card.setObjectName("ExpCard")
            card.setStyleSheet(f"""
                #ExpCard {{
                    background-color: {THEME['bg_card']};
                    border: 1px solid {THEME['border']};
                    border-radius: 4px;
                }}
                #ExpCard:hover {{
                    background-color: {THEME['bg_hover']};
                    border-color: {THEME['border_focus']};
                }}
                #ExpCard QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            c_l = QHBoxLayout(card)
            c_l.setContentsMargins(8, 0, 8, 0)
            c_l.setSpacing(6)

            # Bar vertikal kecil berwarna (Ijo KBBI, Biru Contek, Ungu Keduanya)
            src_bar = QFrame()
            src_bar.setFixedSize(3, 16)
            src_bar.setStyleSheet(f"background-color: {bar_color}; border-radius: 1px;")
            src_bar.setToolTip(bar_tip)
            c_l.addWidget(src_bar)

            # Word text
            lbl_w = QLabel(w.upper())
            lbl_w.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['text_primary']};")
            lbl_w.setToolTip(bar_tip)
            c_l.addWidget(lbl_w)

            c_l.addStretch(1)

            self._append_word_meta_pills(
                c_l,
                w_lower,
                scope="custom" if self.src_filter == "custom" else "auto",
                added_by=r.get("added_by", ""),
                dt_str=r.get("datetime", ""),
            )

            # Tag Suffix Badge (pentok kanan persis LIVE)
            for c in cats:
                sfx = c.get("suffix", "").upper()
                if sfx and w.upper().endswith(sfx):
                    bg = c.get("color", THEME["primary"])
                    lbl_tag = QLabel(sfx)
                    lbl_tag.setFixedHeight(20)
                    lbl_tag.setStyleSheet(f"background-color: {bg}; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; border-radius: 3px; padding: 1px 6px;")
                    c_l.addWidget(lbl_tag)
                    break

            # Action 1: Toggle Whitelist ⭐
            btn_star = QPushButton()
            btn_star.setFixedSize(24, 24)
            btn_star.setCursor(Qt.PointingHandCursor)
            btn_star.setIcon(get_qicon("star_filled" if is_wl else "star", size=13, color=THEME["warning"] if is_wl else THEME["text_muted"]))
            btn_star.setToolTip("Hapus dari Whitelist" if is_wl else "Tambahkan ke Whitelist")
            btn_star.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    background-color: rgba(245, 158, 11, 0.18);
                }}
            """)
            btn_star.clicked.connect(lambda ch=False, word=w: self._toggle_exp_whitelist(word))
            c_l.addWidget(btn_star)

            # Action 2: Toggle Blocklist ✕
            btn_cross = QPushButton()
            btn_cross.setFixedSize(24, 24)
            btn_cross.setCursor(Qt.PointingHandCursor)
            btn_cross.setIcon(get_qicon("ban", size=12, color=THEME["danger"] if is_bl else THEME["text_muted"]))
            btn_cross.setToolTip("Pulihkan dari Blocklist" if is_bl else "Blokir kata ini")
            btn_cross.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    background-color: rgba(239, 68, 68, 0.18);
                }}
            """)
            btn_cross.clicked.connect(lambda ch=False, word=w: self._toggle_exp_blocklist(word))
            c_l.addWidget(btn_cross)

            # Action 3: Hapus kata custom (hanya jika dari kamus custom)
            if r.get("can_delete"):
                btn_del_custom = QPushButton()
                btn_del_custom.setFixedSize(24, 24)
                btn_del_custom.setCursor(Qt.PointingHandCursor)
                btn_del_custom.setIcon(get_qicon("trash", size=12, color=THEME["danger"]))
                btn_del_custom.setToolTip("Hapus kata dari kamus custom")
                btn_del_custom.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        border: none;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{
                        background-color: rgba(239, 68, 68, 0.18);
                    }}
                """)
                btn_del_custom.clicked.connect(lambda ch=False, word=w: self._delete_exp_custom_word(word))
                c_l.addWidget(btn_del_custom)

            self.layout_exp_items.addWidget(card)

        self.layout_exp_items.addStretch(1)

    def _toggle_exp_whitelist(self, word: str):
        w_lower = word.lower()
        if w_lower in self.app.solver.whitelisted_words:
            self.app.solver.unwhitelist_word(w_lower)
            self.app.show_toast(f"'{word.upper()}' dihapus dari Whitelist")
        else:
            self.app.solver.whitelist_word(w_lower)
            self.app.show_toast(f"'{word.upper()}' ditambahkan ke Whitelist")
        if self.app.last_detected_word:
            self.app.update_results(self.app.last_detected_word)
        self._search_dictionary()

    def _toggle_exp_blocklist(self, word: str):
        w_lower = word.lower()
        if w_lower in self.app.solver.blacklisted_words:
            self.app.solver.unblacklist_word(w_lower)
            self.app.show_toast(f"'{word.upper()}' dipulihkan dari Blocklist")
        else:
            self.app.solver.blacklist_word(w_lower)
            self.app.show_toast(f"'{word.upper()}' ditambahkan ke Blocklist")
        if self.app.last_detected_word:
            self.app.update_results(self.app.last_detected_word)
        self._search_dictionary()

    def _delete_exp_custom_word(self, word: str):
        ok, msg = self.app.solver.delete_custom_word(word.lower())
        self.app.show_toast(msg)
        if ok:
            if self.app.last_detected_word:
                self.app.update_results(self.app.last_detected_word)
            self.refresh_whitelist()
            self.refresh_blocklist()
            self._search_dictionary()


# --- Dialog Pendataan Koreksi Sampel OCR ---
class QtKoreksiDialog(QDialog):
    """
    Dialog Pendataan dan Koreksi Sampel Deteksi OCR (sample/kurang_tepat & sample/tidak_dikenali)
    Mendukung penamaan file otomatis _seharusnya_<BENAR>, shortcut Enter untuk simpan & lanjut,
    shortcut Del untuk hapus instan, dan panah navigasi.
    """
    def __init__(self, app, parent=None):
        super().__init__(parent or (app.window() if app else None))
        self.app = app
        self.setWindowTitle("Pendataan Koreksi Sampel")
        self.resize(500, 640)
        self.setMinimumSize(440, 520)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME["bg_root"]};
                color: {THEME["text_primary"]};
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.kurang_tepat_dir = os.path.join(base_dir, "sample", "kurang_tepat")
        self.unknown_dir = os.path.join(base_dir, "sample", "tidak_dikenali")

        self.source_mode = "kurang_tepat"
        self.only_uncorrected = True
        self.items = []
        self.current_idx = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header bar
        hdr = QHBoxLayout()
        lbl_h = QLabel("Koreksi visual sampel pembacaan OCR")
        lbl_h.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        hdr.addWidget(lbl_h)
        hdr.addStretch(1)

        btn_folder = QPushButton(" Buka Folder")
        btn_folder.setIcon(get_qicon("folder", size=12, color=THEME["text_primary"]))
        btn_folder.setCursor(Qt.PointingHandCursor)
        btn_folder.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_card']};
                color: {THEME['text_primary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {THEME['bg_hover']};
            }}
        """)
        btn_folder.clicked.connect(self._open_folder)
        hdr.addWidget(btn_folder)
        layout.addLayout(hdr)

        # Source Selection Bar (Segmented Pills)
        src_bar = QFrame()
        src_bar.setObjectName("KorSrcBar")
        src_bar.setStyleSheet(f"""
            #KorSrcBar {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
        """)
        sb_layout = QHBoxLayout(src_bar)
        sb_layout.setContentsMargins(6, 5, 6, 5)
        sb_layout.setSpacing(6)

        self.btn_grp = QButtonGroup(self)
        self.btn_grp.setExclusive(True)
        self.rb_kt = QPushButton("Kurang Tepat")
        self.rb_td = QPushButton("Tidak Dikenali")
        self.rb_all = QPushButton("Semua")

        pill_qss = f"""
            QPushButton {{
                background: transparent;
                color: {THEME['text_secondary']};
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {THEME['bg_hover']};
                color: {THEME['text_primary']};
            }}
            QPushButton:checked {{
                background-color: {THEME['bg_selected']};
                color: {THEME['primary']};
                border: 1px solid {THEME['primary']};
                font-weight: 600;
            }}
        """
        for i, rb in enumerate([self.rb_kt, self.rb_td, self.rb_all]):
            rb.setCheckable(True)
            rb.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            rb.setCursor(Qt.PointingHandCursor)
            rb.setStyleSheet(pill_qss)
            self.btn_grp.addButton(rb, i)
            sb_layout.addWidget(rb)
        self.rb_kt.setChecked(True)

        self.btn_grp.idClicked.connect(self._on_source_changed)
        sb_layout.addStretch(1)
        layout.addWidget(src_bar)

        # Filter bar
        flt_bar = QHBoxLayout()
        self.chk_uncorrected = QCheckBox("Hanya tampilkan yang belum dikoreksi")
        self.chk_uncorrected.setChecked(True)
        self.chk_uncorrected.setCursor(Qt.PointingHandCursor)
        self.chk_uncorrected.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        self.chk_uncorrected.toggled.connect(self._on_filter_toggled)
        flt_bar.addWidget(self.chk_uncorrected)
        flt_bar.addStretch(1)

        self.lbl_progress = QLabel("- / -")
        self.lbl_progress.setStyleSheet(f"color: {THEME['primary']}; font-size: 12px; font-weight: bold;")
        flt_bar.addWidget(self.lbl_progress)
        layout.addLayout(flt_bar)

        # Image preview container
        self.img_box = QFrame()
        self.img_box.setObjectName("KorImgBox")
        self.img_box.setStyleSheet(f"""
            #KorImgBox {{
                background-color: {THEME['bg_root']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            #KorImgBox QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        ib_layout = QVBoxLayout(self.img_box)
        ib_layout.setContentsMargins(12, 12, 12, 12)
        self.lbl_img = QLabel("Tidak ada gambar")
        self.lbl_img.setAlignment(Qt.AlignCenter)
        self.lbl_img.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px; font-style: italic;")
        ib_layout.addWidget(self.lbl_img)
        layout.addWidget(self.img_box, 1)

        # Info Box
        info_box = QFrame()
        info_box.setObjectName("KorInfoBox")
        info_box.setStyleSheet(f"""
            #KorInfoBox {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            #KorInfoBox QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        inf_l = QVBoxLayout(info_box)
        inf_l.setContentsMargins(10, 8, 10, 8)
        inf_l.setSpacing(4)

        self.lbl_fname = QLabel("File: -")
        self.lbl_fname.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 10px;")
        inf_l.addWidget(self.lbl_fname)

        self.lbl_detail = QLabel("Terdeteksi: - | Akurasi: -")
        self.lbl_detail.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 12px; font-weight: bold;")
        inf_l.addWidget(self.lbl_detail)

        self.lbl_status = QLabel("Status: -")
        self.lbl_status.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        inf_l.addWidget(self.lbl_status)
        layout.addWidget(info_box)

        # Input Frame
        in_frame = QFrame()
        in_frame.setObjectName("KorInFrame")
        in_frame.setStyleSheet(f"""
            #KorInFrame {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            #KorInFrame QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        in_l = QVBoxLayout(in_frame)
        in_l.setContentsMargins(10, 8, 10, 8)
        in_l.setSpacing(6)

        lbl_p = QLabel("Awalan yang Seharusnya (Benar):")
        lbl_p.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 11px; font-weight: bold;")
        in_l.addWidget(lbl_p)

        act_r = QHBoxLayout()
        self.edit_text = QLineEdit()
        self.edit_text.setPlaceholderText("Ketik awalan yang benar lalu tekan Enter...")
        self.edit_text.setAlignment(Qt.AlignCenter)
        self.edit_text.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME['bg_root']};
                color: {THEME['text_primary']};
                font-size: 14px;
                font-weight: bold;
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 4px;
            }}
            QLineEdit:focus {{
                border-color: {THEME['primary']};
            }}
        """)
        self.edit_text.textChanged.connect(lambda t: self.edit_text.setText(t.upper()) if t != t.upper() else None)
        self.edit_text.returnPressed.connect(self._save_current)
        act_r.addWidget(self.edit_text, 1)

        btn_save = QPushButton(" Simpan (Enter)")
        btn_save.setIcon(get_qicon("check", size=13, color=THEME["text_dark"]))
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setFixedHeight(30)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['primary']};
                color: {THEME['text_dark']};
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background-color: {THEME['accent_neon']};
            }}
        """)
        btn_save.clicked.connect(self._save_current)
        act_r.addWidget(btn_save)
        in_l.addLayout(act_r)
        layout.addWidget(in_frame)

        # Navigation & Delete Bar
        nav_r = QHBoxLayout()
        self.btn_prev = QPushButton(" Sebelumnya")
        self.btn_prev.setIcon(get_qicon("arrow_back", size=12, color=THEME["text_primary"]))
        self.btn_prev.setToolTip("Sebelumnya (←)")
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.setStyleSheet(f"background-color: {THEME['bg_card']}; color: {THEME['text_primary']}; border: 1px solid {THEME['border']}; border-radius: 4px; padding: 4px 10px; font-size: 11px;")
        self.btn_prev.clicked.connect(self._prev)
        nav_r.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Berikutnya ")
        self.btn_next.setIcon(get_qicon("arrow_forward", size=12, color=THEME["text_primary"]))
        self.btn_next.setLayoutDirection(Qt.RightToLeft)
        self.btn_next.setToolTip("Berikutnya (→)")
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setStyleSheet(f"background-color: {THEME['bg_card']}; color: {THEME['text_primary']}; border: 1px solid {THEME['border']}; border-radius: 4px; padding: 4px 10px; font-size: 11px;")
        self.btn_next.clicked.connect(self._next)
        nav_r.addWidget(self.btn_next)

        nav_r.addStretch(1)

        self.btn_del = QPushButton(" Hapus (Del)")
        self.btn_del.setIcon(get_qicon("trash", size=12, color=THEME["danger"]))
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.setToolTip("Hapus sampel ini secara instan (Shortcut: Del)")
        self.btn_del.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['danger_bg']};
                color: {THEME['danger']};
                font-size: 11px;
                font-weight: bold;
                border: 1px solid {THEME['danger']};
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {THEME['danger']};
                color: #ffffff;
            }}
        """)
        self.btn_del.clicked.connect(self._delete_current)
        nav_r.addWidget(self.btn_del)
        layout.addLayout(nav_r)

        # Install event filter pada QLineEdit agar Del, Panah Kiri/Kanan langsung bernavigasi
        self.edit_text.installEventFilter(self)

        # Global Window Shortcuts untuk Navigasi & Hapus
        self.sc_del = QShortcut(QKeySequence(Qt.Key_Delete), self)
        self.sc_del.activated.connect(self._delete_current)

        self.sc_left = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.sc_left.activated.connect(self._prev)

        self.sc_right = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.sc_right.activated.connect(self._next)

        self.sc_up = QShortcut(QKeySequence(Qt.Key_Up), self)
        self.sc_up.activated.connect(self._prev)

        self.sc_down = QShortcut(QKeySequence(Qt.Key_Down), self)
        self.sc_down.activated.connect(self._next)

        # Load initial
        self._reload_items()
        QTimer.singleShot(60, self.edit_text.setFocus)

    def _open_folder(self):
        target = self.kurang_tepat_dir if self.source_mode == "kurang_tepat" else self.unknown_dir
        if not os.path.exists(target):
            os.makedirs(target, exist_ok=True)
        try:
            os.startfile(target)
        except Exception:
            pass

    def _on_source_changed(self, idx):
        modes = ["kurang_tepat", "tidak_dikenali", "all"]
        self.source_mode = modes[idx] if idx < len(modes) else "kurang_tepat"
        self._reload_items()

    def _on_filter_toggled(self, checked):
        self.only_uncorrected = checked
        self._reload_items()

    def _parse_file(self, fpath, src):
        fname = os.path.basename(fpath)
        parts = fname.replace(".png", "").split("_")
        if len(parts) >= 4:
            ts = f"{parts[0]}_{parts[1]}"
            conf = parts[-1]
            if "seharusnya" in parts:
                idx = parts.index("seharusnya")
                label = "_".join(parts[2:idx])
                seh = "_".join(parts[idx+1:-1])
                is_corrected = True
            else:
                label = "_".join(parts[2:-1])
                seh = ""
                is_corrected = False
            return {
                "ts": ts,
                "label": label,
                "seh": seh,
                "conf": conf,
                "is_corrected": is_corrected,
                "filename": fname,
                "fpath": fpath,
                "source": src
            }
        return None

    def _reload_items(self):
        all_kt = []
        if os.path.exists(self.kurang_tepat_dir):
            for f in sorted(os.listdir(self.kurang_tepat_dir)):
                if f.endswith(".png"):
                    p = self._parse_file(os.path.join(self.kurang_tepat_dir, f), "kurang_tepat")
                    if p:
                        all_kt.append(p)

        all_td = []
        if os.path.exists(self.unknown_dir):
            for f in sorted(os.listdir(self.unknown_dir)):
                fpath = os.path.join(self.unknown_dir, f)
                if f.endswith(".png") and os.path.isfile(fpath):
                    p = self._parse_file(fpath, "tidak_dikenali")
                    if p:
                        all_td.append(p)

        filt_kt = [p for p in all_kt if not p["is_corrected"]] if self.only_uncorrected else all_kt
        filt_td = [p for p in all_td if not p["is_corrected"]] if self.only_uncorrected else all_td

        self.rb_kt.setText(f"Kurang Tepat ({len(filt_kt)})")
        self.rb_td.setText(f"Tidak Dikenali ({len(filt_td)})")
        self.rb_all.setText(f"Semua ({len(filt_kt) + len(filt_td)})")
        for rb in (self.rb_kt, self.rb_td, self.rb_all):
            rb.adjustSize()
            rb.updateGeometry()

        if self.source_mode == "kurang_tepat":
            self.items = filt_kt
        elif self.source_mode == "tidak_dikenali":
            self.items = filt_td
        else:
            self.items = filt_kt + filt_td

        self.current_idx = min(self.current_idx, max(0, len(self.items) - 1))
        self._display_current()

    def _display_current(self):
        if not self.items:
            self.lbl_progress.setText("0 / 0")
            self.lbl_img.setPixmap(QPixmap())
            self.lbl_img.setText("Tidak ada sampel yang perlu dikoreksi.")
            self.lbl_fname.setText("File: -")
            self.lbl_detail.setText("Terdeteksi: - | Akurasi: -")
            self.lbl_status.setText("Status: -")
            self.edit_text.clear()
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.btn_del.setEnabled(False)
            return

        item = self.items[self.current_idx]
        self.lbl_progress.setText(f"{self.current_idx + 1} / {len(self.items)}")
        self.lbl_fname.setText(f"File: {item['filename']}")
        self.lbl_detail.setText(f"Terdeteksi: '{item['label']}' | Keyakinan: {item['conf']}")

        if item["is_corrected"]:
            self.lbl_status.setText(f"✅ Sudah dikoreksi: '{item['seh']}'")
            self.lbl_status.setStyleSheet(f"color: {THEME['primary']}; font-size: 11px;")
            self.edit_text.setText(item["seh"])
            self.edit_text.selectAll()
        else:
            self.lbl_status.setText("Belum dikoreksi")
            self.lbl_status.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
            self.edit_text.clear()

        pix = QPixmap(item["fpath"])
        if not pix.isNull():
            target_w = min(400, max(240, pix.width() * 3))
            self.lbl_img.setPixmap(pix.scaledToWidth(target_w, Qt.SmoothTransformation))
            self.lbl_img.setText("")
        else:
            self.lbl_img.setText("Gagal memuat gambar")

        self.btn_prev.setEnabled(self.current_idx > 0)
        self.btn_next.setEnabled(self.current_idx < len(self.items) - 1)
        self.btn_del.setEnabled(True)
        self.edit_text.setFocus()

    def _save_current(self):
        if not self.items or self.current_idx >= len(self.items):
            return
        correct_text = self.edit_text.text().strip().upper()
        if not correct_text:
            return

        item = self.items[self.current_idx]
        old_path = item["fpath"]
        folder = os.path.dirname(old_path)
        new_fname = f"{item['ts']}_{item['label']}_seharusnya_{correct_text}_{item['conf']}.png"
        new_path = os.path.join(folder, new_fname)

        try:
            if old_path != new_path:
                os.rename(old_path, new_path)
            if self.app:
                self.app.show_toast(f"Tersimpan: '{correct_text}'")
            if hasattr(self.app, "tab_system") and hasattr(self.app.tab_system, "refresh_counts"):
                self.app.tab_system.refresh_counts()
            self._reload_items()
            if self.current_idx < len(self.items):
                self._display_current()
        except Exception as e:
            QMessageBox.warning(self, "Gagal Menyimpan", f"Gagal mengubah nama file: {e}")

    def _delete_current(self):
        if not self.items or self.current_idx >= len(self.items):
            return
        item = self.items[self.current_idx]
        try:
            if os.path.exists(item["fpath"]):
                os.remove(item["fpath"])
            if self.app:
                self.app.show_toast("Sampel dihapus")
            if hasattr(self.app, "tab_system") and hasattr(self.app.tab_system, "refresh_counts"):
                self.app.tab_system.refresh_counts()
            self._reload_items()
        except Exception as e:
            QMessageBox.warning(self, "Gagal Menghapus", f"Gagal menghapus file: {e}")

    def _prev(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._display_current()

    def _next(self):
        if self.current_idx < len(self.items) - 1:
            self.current_idx += 1
            self._display_current()

    def eventFilter(self, obj, event):
        if obj == self.edit_text and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Delete:
                self._delete_current()
                return True
            elif key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp):
                self._prev()
                return True
            elif key in (Qt.Key_Right, Qt.Key_Down, Qt.Key_PageDown):
                self._next()
                return True
            elif key == Qt.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Delete:
            self._delete_current()
            event.accept()
        elif key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp):
            self._prev()
            event.accept()
        elif key in (Qt.Key_Right, Qt.Key_Down, Qt.Key_PageDown):
            self._next()
            event.accept()
        elif key == Qt.Key_Escape:
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)


class QtHotkeyButton(QPushButton):
    """Tombol interaktif untuk merekam kombinasi tombol keyboard sebagai hotkey kustom."""
    hotkey_changed = Signal(str, str)  # (action_id, new_key)

    def __init__(self, action_id: str, key_str: str = "", parent=None):
        super().__init__(parent)
        self.action_id = action_id
        self._key_str = (key_str or "").strip()
        self._capturing = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(26)
        self.setMinimumWidth(96)
        self.setToolTip("Klik lalu tekan tombol baru (Backspace/Del untuk hapus, Esc untuk batal)")
        self.clicked.connect(self._start_capture)
        self._refresh_visual()

    def set_hotkey(self, key_str: str):
        self._key_str = (key_str or "").strip()
        self._capturing = False
        self._refresh_visual()

    def _refresh_visual(self):
        if self._capturing:
            self.setText("Tekan tombol...")
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(56, 217, 118, 0.16);
                    color: {THEME['primary']};
                    border: 1px solid {THEME['primary']};
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }}
            """)
        else:
            label = self._key_str if self._key_str else "Kosong"
            fg = THEME["text_primary"] if self._key_str else THEME["text_muted"]
            self.setText(label)
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME['bg_root']};
                    color: {fg};
                    border: 1px solid {THEME['border']};
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border-color: {THEME['primary']};
                }}
            """)

    def _start_capture(self):
        self._capturing = True
        self._refresh_visual()
        self.setFocus()

    def focusOutEvent(self, event):
        if self._capturing:
            self._capturing = False
            self._refresh_visual()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if not self._capturing:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        if key == Qt.Key_Escape:
            self._capturing = False
            self._refresh_visual()
            return

        if key in (Qt.Key_Backspace, Qt.Key_Delete):
            self._capturing = False
            self._key_str = ""
            self._refresh_visual()
            self.hotkey_changed.emit(self.action_id, "")
            return

        mods = []
        m = event.modifiers()
        if m & Qt.ControlModifier:
            mods.append("Ctrl")
        if m & Qt.AltModifier:
            mods.append("Alt")
        if m & Qt.ShiftModifier:
            mods.append("Shift")

        key_name = QKeySequence(key).toString().strip()
        if not key_name:
            return
        combo = "+".join(mods + [key_name])
        self._capturing = False
        self._refresh_visual()
        self.hotkey_changed.emit(self.action_id, combo)


# --- Tab 4: SYSTEM Tab View ---
class QtSystemTabView(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app

        # Scroll Area for System Tab to ensure all settings fit smoothly
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.viewport().installEventFilter(self)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {THEME['bg_root']};
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {THEME['border']};
                border-radius: 3px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {THEME['primary']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.container = QWidget()
        self.container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(10, 8, 10, 16)
        layout.setSpacing(10)

        # 1. Scanner Settings Frame (Vision & OCR)
        sc_box = QFrame()
        sc_box.setObjectName("ScBox")
        sc_box.setStyleSheet(f"""
            #ScBox {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            #ScBox QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        sc_layout = QVBoxLayout(sc_box)
        sc_layout.setContentsMargins(12, 10, 12, 10)
        sc_layout.setSpacing(8)

        lbl_sc = QLabel("SCANNER")
        lbl_sc.setStyleSheet(f"color: {THEME['primary']}; font-weight: bold; font-size: 11px;")
        sc_layout.addWidget(lbl_sc)

        sp_row = QHBoxLayout()
        lbl_sp_title = QLabel("Kecepatan:")
        lbl_sp_title.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 12px;")
        sp_row.addWidget(lbl_sp_title)

        self.combo_speed = QComboBox()
        self.combo_speed.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_speed.setMinimumWidth(0)
        self.combo_speed.addItems([
            "Agresif (40ms)",
            "Cepat (80ms)",
            "Sedang (120ms)",
            "Santai (200ms)"
        ])
        current_spd = self.app.config.get("scan_interval_sec", 0.08)
        speeds = [0.04, 0.08, 0.12, 0.20]
        if current_spd in speeds:
            self.combo_speed.setCurrentIndex(speeds.index(current_spd))
        else:
            self.combo_speed.setCurrentIndex(1)
        self.combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        sp_row.addWidget(self.combo_speed, 1)
        sc_layout.addLayout(sp_row)

        roi_row = QHBoxLayout()
        roi_row.setSpacing(6)

        btn_roi = QPushButton(" Atur Area Scanner")
        btn_roi.setIcon(get_qicon("settings", size=13, color=THEME["text_primary"]))
        btn_roi.setCursor(Qt.PointingHandCursor)
        btn_roi.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_hover']};
                color: {THEME['text_primary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 6px 8px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {THEME['primary']};
            }}
        """)
        btn_roi.clicked.connect(self.app.open_region_selector)
        roi_row.addWidget(btn_roi, 1)

        btn_test_roi = QPushButton(" Cek Area Scanner")
        btn_test_roi.setIcon(get_qicon("search", size=13, color=THEME["primary"]))
        btn_test_roi.setCursor(Qt.PointingHandCursor)
        btn_test_roi.setToolTip("Tampilkan posisi Area Scanner di layar")
        btn_test_roi.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_hover']};
                color: {THEME['primary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 6px 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {THEME['primary']};
                background-color: {THEME['bg_card']};
            }}
        """)
        btn_test_roi.clicked.connect(self.app.check_region_scanner)
        roi_row.addWidget(btn_test_roi)

        sc_layout.addLayout(roi_row)

        layout.addWidget(sc_box)

        # 2. Tampilan, Ergonomi & Mode Dev Frame
        ui_box = QFrame()
        ui_box.setObjectName("UiBox")
        ui_box.setStyleSheet(f"""
            #UiBox {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            #UiBox QLabel, #UiBox QCheckBox {{
                border: none;
                background: transparent;
            }}
        """)
        ui_layout = QVBoxLayout(ui_box)
        ui_layout.setContentsMargins(12, 10, 12, 10)
        ui_layout.setSpacing(8)

        lbl_ui = QLabel("TAMPILAN")
        lbl_ui.setStyleSheet(f"color: {THEME['primary']}; font-weight: bold; font-size: 11px;")
        ui_layout.addWidget(lbl_ui)

        # Checkbox Always-on-Top (Pin Window)
        self.chk_ontop = QCheckBox("Selalu di Atas (Always on Top)")
        self.chk_ontop.setChecked(getattr(self.app, "always_on_top", True))
        self.chk_ontop.setCursor(Qt.PointingHandCursor)
        self.chk_ontop.setStyleSheet(f"""
            QCheckBox {{
                background: transparent;
                color: {THEME['text_primary']};
                font-size: 12px;
                font-weight: 600;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                background-color: {THEME['bg_root']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME['primary']};
                border-color: {THEME['primary']};
            }}
        """)
        self.chk_ontop.toggled.connect(self.app.set_always_on_top)
        ui_layout.addWidget(self.chk_ontop)

        lbl_ontop_hint = QLabel("Pertahankan jendela overlay selalu melayang di atas Roblox dan aplikasi lainnya.")
        lbl_ontop_hint.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        lbl_ontop_hint.setWordWrap(True)
        ui_layout.addWidget(lbl_ontop_hint)

        self.chk_twotone = QCheckBox("Pewarnaan Dua Nada")
        self.chk_twotone.setChecked(self.app.config.get("two_tone_text", True))
        self.chk_twotone.setCursor(Qt.PointingHandCursor)
        self.chk_twotone.setStyleSheet(f"""
            QCheckBox {{
                background: transparent;
                color: {THEME['text_primary']};
                font-size: 12px;
                font-weight: 600;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                background-color: {THEME['bg_root']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME['primary']};
                border-color: {THEME['primary']};
            }}
        """)
        self.chk_twotone.toggled.connect(self.app.set_two_tone_text)
        ui_layout.addWidget(self.chk_twotone)

        lbl_hint = QLabel("Redupkan huruf awalan yang sudah ada di game, terangkan sisa huruf yang harus diketik.")
        lbl_hint.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        lbl_hint.setWordWrap(True)
        ui_layout.addWidget(lbl_hint)

        # Checkbox Mode Development
        self.chk_dev_mode = QCheckBox("Mode Pengembang")
        self.chk_dev_mode.setChecked(self.app.config.get("dev_mode", False))
        self.chk_dev_mode.setCursor(Qt.PointingHandCursor)
        self.chk_dev_mode.setStyleSheet(f"""
            QCheckBox {{
                background: transparent;
                color: {THEME['primary']};
                font-size: 12px;
                font-weight: 600;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                background-color: {THEME['bg_root']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME['primary']};
                border-color: {THEME['primary']};
            }}
        """)
        self.chk_dev_mode.toggled.connect(self.app.set_dev_mode)
        ui_layout.addWidget(self.chk_dev_mode)

        lbl_dev_hint = QLabel("Menampilkan tombol ⚡ Restart di titlebar untuk memulai ulang aplikasi secara instan. Shortcut: Ctrl+Shift+D.")
        lbl_dev_hint.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        lbl_dev_hint.setWordWrap(True)
        ui_layout.addWidget(lbl_dev_hint)

        # Checkbox Izinkan Multi-Instance
        self.chk_multi_instance = QCheckBox("Izinkan Multi-Instance")
        self.chk_multi_instance.setChecked(self.app.config.get("allow_multiple_instances", False))
        self.chk_multi_instance.setCursor(Qt.PointingHandCursor)
        self.chk_multi_instance.setStyleSheet(f"""
            QCheckBox {{
                background: transparent;
                color: {THEME['text_primary']};
                font-size: 12px;
                font-weight: 600;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                background-color: {THEME['bg_root']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME['primary']};
                border-color: {THEME['primary']};
            }}
        """)
        self.chk_multi_instance.toggled.connect(self.app.set_allow_multiple_instances)
        ui_layout.addWidget(self.chk_multi_instance)

        lbl_multi_hint = QLabel("Aktif jika ingin membuka lebih dari satu jendela SAKA Overlay bersamaan (default: hanya 1 instance aktif).")
        lbl_multi_hint.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        lbl_multi_hint.setWordWrap(True)
        ui_layout.addWidget(lbl_multi_hint)

        layout.addWidget(ui_box)

        # 2b. Sinkronisasi Database Privat (Mode TXT vs Supabase)
        self.db_box = QFrame()
        self.db_box.setObjectName("DbBox")
        self.db_box.setStyleSheet(f"""
            #DbBox {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            #DbBox QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        db_layout = QVBoxLayout(self.db_box)
        db_layout.setContentsMargins(12, 10, 12, 10)
        db_layout.setSpacing(8)

        db_hdr = QHBoxLayout()
        lbl_db = QLabel("DATABASE SINKRONISASI")
        lbl_db.setStyleSheet(f"color: {THEME['primary']}; font-weight: bold; font-size: 11px;")
        db_hdr.addWidget(lbl_db)
        db_hdr.addStretch(1)

        self.lbl_db_badge = QLabel("MODE TXT")
        self.lbl_db_badge.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 10px; font-weight: bold;")
        db_hdr.addWidget(self.lbl_db_badge)

        self.btn_db_resync = QPushButton()
        self.btn_db_resync.setIcon(get_qicon("refresh", size=11, color=THEME["text_secondary"]))
        self.btn_db_resync.setFixedSize(22, 22)
        self.btn_db_resync.setCursor(Qt.PointingHandCursor)
        self.btn_db_resync.setToolTip("Sync ulang data terbaru dari database")
        self.btn_db_resync.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_root']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 0px;
            }}
            QPushButton:hover {{
                border-color: {THEME['primary']};
                background-color: {THEME['bg_hover']};
            }}
        """)
        self.btn_db_resync.clicked.connect(self.app.force_resync_database)
        self.btn_db_resync.setVisible(self.app.config.get("storage_mode", "txt") == "supabase")
        db_hdr.addWidget(self.btn_db_resync)

        self.btn_db_clear_cache = QPushButton()
        self.btn_db_clear_cache.setIcon(get_qicon("trash", size=11, color=THEME["text_muted"]))
        self.btn_db_clear_cache.setFixedSize(22, 22)
        self.btn_db_clear_cache.setCursor(Qt.PointingHandCursor)
        self.btn_db_clear_cache.setToolTip("Hapus cache lokal database (db_cache.json)")
        self.btn_db_clear_cache.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_root']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 0px;
            }}
            QPushButton:hover {{
                border-color: {THEME['danger']};
                background-color: {THEME['danger_bg']};
            }}
        """)
        self.btn_db_clear_cache.clicked.connect(self.app.clear_database_cache)
        db_hdr.addWidget(self.btn_db_clear_cache)
        db_layout.addLayout(db_hdr)

        # Toggle Mode Penyimpanan
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.btn_mode_txt = QPushButton(" Lokal (File TXT)")
        self.btn_mode_txt.setIcon(get_qicon("book", size=12, color=THEME["text_primary"]))
        self.btn_mode_txt.setCursor(Qt.PointingHandCursor)
        self.btn_mode_txt.setFixedHeight(28)
        self.btn_mode_txt.clicked.connect(self._on_select_txt_mode)
        mode_row.addWidget(self.btn_mode_txt, 1)

        self.btn_mode_db = QPushButton(" Database (Self-hosted)")
        self.btn_mode_db.setIcon(get_qicon("supabase", size=12, color=THEME["text_primary"]))
        self.btn_mode_db.setCursor(Qt.PointingHandCursor)
        self.btn_mode_db.setFixedHeight(28)
        self.btn_mode_db.clicked.connect(self._on_select_db_mode)
        mode_row.addWidget(self.btn_mode_db, 1)
        db_layout.addLayout(mode_row)

        self.lbl_db_status = QLabel("Mode File TXT aktif: membaca & menyimpan ke file .txt lokal/publik.")
        self.lbl_db_status.setWordWrap(True)
        self.lbl_db_status.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        db_layout.addWidget(self.lbl_db_status)

        # Indikator Panel Terpisah: 3 Panel Horizontal (WL/BL/Kamus+), Panel Sync Terakhir, Panel Aktivitas Terakhir
        self.db_stats_panel = QWidget()
        self.db_stats_panel.setObjectName("DbStatsPanel")
        self.db_stats_panel.setStyleSheet("#DbStatsPanel { background: transparent; border: none; }")
        stats_root = QVBoxLayout(self.db_stats_panel)
        stats_root.setContentsMargins(0, 2, 0, 2)
        stats_root.setSpacing(5)

        stat_box_qss = f"""
            QFrame {{
                background-color: {THEME['bg_root']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """

        def _make_metric_panel(title: str, val_color: str):
            box = QFrame()
            box.setStyleSheet(stat_box_qss)
            bl = QVBoxLayout(box)
            bl.setContentsMargins(6, 5, 6, 5)
            bl.setSpacing(1)
            lbl_t = QLabel(title)
            lbl_t.setAlignment(Qt.AlignCenter)
            lbl_t.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 9px; font-weight: bold;")
            lbl_v = QLabel("0")
            lbl_v.setAlignment(Qt.AlignCenter)
            lbl_v.setStyleSheet(f"color: {val_color}; font-size: 13px; font-weight: bold;")
            bl.addWidget(lbl_t)
            bl.addWidget(lbl_v)
            return box, lbl_v

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(6)
        p_wl, self.lbl_stat_wl_val = _make_metric_panel("WHITELIST", THEME["warning"])
        p_bl, self.lbl_stat_bl_val = _make_metric_panel("BLOCKLIST", THEME["danger"])
        p_cm, self.lbl_stat_cm_val = _make_metric_panel("KAMUS+", THEME["primary"])
        metrics_row.addWidget(p_wl, 1)
        metrics_row.addWidget(p_bl, 1)
        metrics_row.addWidget(p_cm, 1)
        stats_root.addLayout(metrics_row)

        # Panel User Online (Presence)
        online_box = QFrame()
        online_box.setStyleSheet(stat_box_qss)
        online_l = QHBoxLayout(online_box)
        online_l.setContentsMargins(8, 5, 8, 5)
        lbl_on_title = QLabel("User Online")
        lbl_on_title.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 10px; font-weight: 600;")
        self.lbl_stat_online = QLabel("0 Online")
        self.lbl_stat_online.setWordWrap(True)
        self.lbl_stat_online.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_stat_online.setStyleSheet(f"color: {THEME['primary']}; font-size: 10px; font-weight: bold;")
        online_l.addWidget(lbl_on_title)
        online_l.addWidget(self.lbl_stat_online, 1)
        stats_root.addWidget(online_box)

        # Panel Sync Terakhir
        sync_box = QFrame()
        sync_box.setStyleSheet(stat_box_qss)
        sync_l = QHBoxLayout(sync_box)
        sync_l.setContentsMargins(8, 5, 8, 5)
        lbl_st_title = QLabel("Sync Terakhir")
        lbl_st_title.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 10px; font-weight: 600;")
        self.lbl_stat_sync_time = QLabel("-")
        self.lbl_stat_sync_time.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 10px; font-weight: bold;")
        sync_l.addWidget(lbl_st_title)
        sync_l.addStretch(1)
        sync_l.addWidget(self.lbl_stat_sync_time)
        stats_root.addWidget(sync_box)

        # Panel Aktivitas Terakhir
        act_box = QFrame()
        act_box.setStyleSheet(stat_box_qss)
        act_l = QHBoxLayout(act_box)
        act_l.setContentsMargins(8, 5, 8, 5)
        lbl_act_title = QLabel("Aktivitas")
        lbl_act_title.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 10px; font-weight: 600;")
        self.lbl_stat_last_act = QLabel("-")
        self.lbl_stat_last_act.setWordWrap(True)
        self.lbl_stat_last_act.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_stat_last_act.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 10px; font-weight: 600;")
        act_l.addWidget(lbl_act_title)
        act_l.addWidget(self.lbl_stat_last_act, 1)
        stats_root.addWidget(act_box)

        self.db_stats_panel.setVisible(False)
        db_layout.addWidget(self.db_stats_panel)

        # Panel Konfigurasi Supabase (tampil saat Database (Self-hosted) dipilih)
        self.db_config_panel = QWidget()
        self.db_config_panel.setObjectName("DbConfigPanel")
        self.db_config_panel.setStyleSheet("#DbConfigPanel { background: transparent; border: none; }")
        cfg_l = QVBoxLayout(self.db_config_panel)
        cfg_l.setContentsMargins(0, 4, 0, 0)
        cfg_l.setSpacing(6)

        input_qss = f"""
            QLineEdit {{
                background-color: {THEME['bg_root']};
                color: {THEME['text_primary']};
                font-size: 11px;
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 5px 8px;
            }}
            QLineEdit:focus {{
                border-color: {THEME['primary']};
            }}
        """
        sec_btn_qss = f"""
            QPushButton {{
                background-color: {THEME['bg_hover']};
                color: {THEME['text_primary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {THEME['primary']};
            }}
        """

        self.edit_sb_url = QLineEdit(self.app.config.get("supabase_url", ""))
        self.edit_sb_url.setPlaceholderText("Project URL (misal: https://xyz.supabase.co)")
        self.edit_sb_url.setStyleSheet(input_qss)
        cfg_l.addWidget(self.edit_sb_url)

        key_row = QHBoxLayout()
        key_row.setSpacing(4)
        self.edit_sb_key = QLineEdit(self.app.config.get("supabase_anon_key", ""))
        self.edit_sb_key.setPlaceholderText("Supabase Anon Key (simpan privat untuk grup Anda)")
        self.edit_sb_key.setEchoMode(QLineEdit.Password)
        self.edit_sb_key.setStyleSheet(input_qss)
        key_row.addWidget(self.edit_sb_key, 1)

        self.btn_toggle_key = QPushButton()
        self.btn_toggle_key.setIcon(get_qicon("eye", size=14, color=THEME["text_secondary"]))
        self.btn_toggle_key.setToolTip("Tampilkan Anon Key")
        self.btn_toggle_key.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_key.setFixedSize(28, 26)
        self.btn_toggle_key.setStyleSheet(sec_btn_qss)
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self.btn_toggle_key)
        cfg_l.addLayout(key_row)

        self.edit_sb_nick = QLineEdit(self.app.config.get("sync_nickname", ""))
        self.edit_sb_nick.setPlaceholderText("Nickname Anda (opsional, untuk label kontributor)")
        self.edit_sb_nick.setStyleSheet(input_qss)
        self.edit_sb_nick.editingFinished.connect(lambda: self.app.update_sync_nickname(self.edit_sb_nick.text()))
        cfg_l.addWidget(self.edit_sb_nick)

        # Row Tombol Setup & Invite
        helper_row = QHBoxLayout()
        helper_row.setSpacing(4)

        btn_sql = QPushButton(" Salin SQL")
        btn_sql.setIcon(get_qicon("edit", size=11, color=THEME["text_primary"]))
        btn_sql.setCursor(Qt.PointingHandCursor)
        btn_sql.setToolTip("Salin skrip SQL pembuatan tabel saka_words untuk Supabase SQL Editor")
        btn_sql.setStyleSheet(sec_btn_qss)
        btn_sql.clicked.connect(self._copy_sql_setup)
        helper_row.addWidget(btn_sql, 1)

        btn_paste_inv = QPushButton(" Tempel Invite")
        btn_paste_inv.setIcon(get_qicon("clipboard", size=12, color=THEME["text_primary"]))
        btn_paste_inv.setCursor(Qt.PointingHandCursor)
        btn_paste_inv.setToolTip("Mengambil kode invite (saka-db://...) dari clipboard untuk mengisi URL & Key secara otomatis")
        btn_paste_inv.setStyleSheet(sec_btn_qss)
        btn_paste_inv.clicked.connect(self._paste_invite_config)
        helper_row.addWidget(btn_paste_inv, 1)

        btn_copy_inv = QPushButton(" Salin Invite")
        btn_copy_inv.setIcon(get_qicon("link", size=11, color=THEME["text_primary"]))
        btn_copy_inv.setCursor(Qt.PointingHandCursor)
        btn_copy_inv.setToolTip("Salin paket Invite Config untuk dibagikan ke teman grup")
        btn_copy_inv.setStyleSheet(sec_btn_qss)
        btn_copy_inv.clicked.connect(self._copy_invite_config)
        helper_row.addWidget(btn_copy_inv, 1)
        cfg_l.addLayout(helper_row)

        # Tombol Utama: Tes & Hubungkan
        self.btn_db_connect = QPushButton(" Tes & Hubungkan")
        self.btn_db_connect.setIcon(get_qicon("check", size=12, color=THEME["text_dark"]))
        self.btn_db_connect.setCursor(Qt.PointingHandCursor)
        self.btn_db_connect.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['primary']};
                color: {THEME['text_dark']};
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-radius: 4px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background-color: {THEME['accent_neon']};
            }}
        """)
        self.btn_db_connect.clicked.connect(self._on_connect_clicked)
        cfg_l.addWidget(self.btn_db_connect)

        # Row Tombol Transfer Lokal <-> DB (dengan ikon panah MDI)
        transfer_row = QHBoxLayout()
        transfer_row.setSpacing(6)

        def _make_transfer_btn(left_icon: str, icon_color: str, left_txt: str, right_txt: str, tooltip: str):
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(sec_btn_qss)
            bl = QHBoxLayout(btn)
            bl.setContentsMargins(8, 0, 8, 0)
            bl.setSpacing(4)
            bl.addStretch(1)

            ico_l = QLabel()
            ico_l.setPixmap(get_qicon(left_icon, size=12, color=icon_color).pixmap(12, 12))
            ico_l.setAttribute(Qt.WA_TransparentForMouseEvents)
            ico_l.setStyleSheet("border: none; background: transparent;")
            bl.addWidget(ico_l)

            lbl_l = QLabel(left_txt)
            lbl_l.setAttribute(Qt.WA_TransparentForMouseEvents)
            lbl_l.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 10px; font-weight: 600; border: none; background: transparent;")
            bl.addWidget(lbl_l)

            ico_arr = QLabel()
            ico_arr.setPixmap(get_qicon("arrow_forward", size=10, color=THEME["text_secondary"]).pixmap(10, 10))
            ico_arr.setAttribute(Qt.WA_TransparentForMouseEvents)
            ico_arr.setStyleSheet("border: none; background: transparent;")
            bl.addWidget(ico_arr)

            lbl_r = QLabel(right_txt)
            lbl_r.setAttribute(Qt.WA_TransparentForMouseEvents)
            lbl_r.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 10px; font-weight: 600; border: none; background: transparent;")
            bl.addWidget(lbl_r)

            bl.addStretch(1)
            return btn

        self.btn_db_import = _make_transfer_btn(
            "cloud_upload", THEME["warning"], "Upload Lokal", "DB",
            "Upload daftar kata (.txt) & pengaturan MODE lokal ke Database Privat",
        )
        self.btn_db_import.clicked.connect(self._on_import_txt_clicked)
        transfer_row.addWidget(self.btn_db_import, 1)

        self.btn_db_download = _make_transfer_btn(
            "cloud_download", THEME["info"], "Download DB", "Lokal",
            "Download daftar kata & pengaturan MODE dari Database Privat ke file lokal (.txt & config.local.json)",
        )
        self.btn_db_download.clicked.connect(self._on_download_db_clicked)
        transfer_row.addWidget(self.btn_db_download, 1)
        cfg_l.addLayout(transfer_row)

        lbl_priv_note = QLabel("Kredensial tersimpan hanya di config.local.json. Jangan bagikan Anon Key privat ke publik.")
        lbl_priv_note.setWordWrap(True)
        lbl_priv_note.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 10px;")
        cfg_l.addWidget(lbl_priv_note)

        db_layout.addWidget(self.db_config_panel)
        layout.addWidget(self.db_box)
        self._refresh_db_mode_ui(expand_panel=(self.app.config.get("storage_mode", "txt") == "supabase"))

        # 3. Pendataan Koreksi Sampel Frame (F2)
        kor_box = QFrame()
        kor_box.setObjectName("KorBox")
        kor_box.setStyleSheet(f"""
            #KorBox {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            #KorBox QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        kor_layout = QVBoxLayout(kor_box)
        kor_layout.setContentsMargins(12, 10, 12, 10)
        kor_layout.setSpacing(8)

        lbl_kor = QLabel("SAMPEL")
        lbl_kor.setStyleSheet(f"color: {THEME['primary']}; font-weight: bold; font-size: 11px;")
        kor_layout.addWidget(lbl_kor)

        self.lbl_koreksi_counts = QLabel("Memuat data sampel...")
        self.lbl_koreksi_counts.setWordWrap(True)
        self.lbl_koreksi_counts.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; font-weight: 500;")
        kor_layout.addWidget(self.lbl_koreksi_counts)

        self.btn_open_kor = QPushButton(" Buka Pendataan Koreksi")
        self.btn_open_kor.setIcon(get_qicon("edit", size=13, color=THEME["text_dark"]))
        self.btn_open_kor.setCursor(Qt.PointingHandCursor)
        self.btn_open_kor.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['primary']};
                color: {THEME['text_dark']};
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {THEME['accent_neon']};
            }}
        """)
        self.btn_open_kor.clicked.connect(self.app.open_koreksi_dialog)
        kor_layout.addWidget(self.btn_open_kor)

        self.btn_open_fld = QPushButton(" Buka Folder Sampel")
        self.btn_open_fld.setIcon(get_qicon("folder", size=13, color=THEME["text_primary"]))
        self.btn_open_fld.setCursor(Qt.PointingHandCursor)
        self.btn_open_fld.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_hover']};
                color: {THEME['text_primary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                border-color: {THEME['primary']};
            }}
        """)
        self.btn_open_fld.clicked.connect(self.app.open_sample_folder)
        kor_layout.addWidget(self.btn_open_fld)

        layout.addWidget(kor_box)

        # 4. Hotkey Kustom Frame
        hk_box = QFrame()
        hk_box.setObjectName("HkBox")
        hk_box.setStyleSheet(f"""
            #HkBox {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            #HkBox QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        hk_layout = QVBoxLayout(hk_box)
        hk_layout.setContentsMargins(12, 10, 12, 10)
        hk_layout.setSpacing(6)

        hk_hdr = QHBoxLayout()
        lbl_hk = QLabel("HOTKEY")
        lbl_hk.setStyleSheet(f"color: {THEME['primary']}; font-weight: bold; font-size: 11px;")
        hk_hdr.addWidget(lbl_hk)
        hk_hdr.addStretch(1)

        btn_hk_reset = QPushButton("Reset Default")
        btn_hk_reset.setCursor(Qt.PointingHandCursor)
        btn_hk_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {THEME['text_secondary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {THEME['primary']};
                border-color: {THEME['primary']};
            }}
        """)
        btn_hk_reset.clicked.connect(self.app.reset_hotkeys)
        hk_hdr.addWidget(btn_hk_reset)
        hk_layout.addLayout(hk_hdr)

        self._hotkey_specs = [
            ("toggle_scan", "Start / Stop Scanner"),
            ("flag_error", "Flag Deteksi Salah"),
            ("add_whitelist", "Tambah Whitelist"),
            ("add_blocklist", "Tambah Blocklist"),
            ("add_kamus", "Tambah Kata ke Kamus"),
            ("add_tag", "Tambah Tag Akhiran"),
            ("cycle_mode", "Ganti Mode Permainan"),
        ]
        self._hotkey_buttons = {}
        cur_hotkeys = self.app.config.get("hotkeys", {})
        for aid, label_txt in self._hotkey_specs:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label_txt)
            lbl.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 11px;")
            row.addWidget(lbl, 1)

            btn_hk = QtHotkeyButton(aid, cur_hotkeys.get(aid, ""))
            btn_hk.hotkey_changed.connect(self._on_hotkey_changed)
            self._hotkey_buttons[aid] = btn_hk
            row.addWidget(btn_hk)
            hk_layout.addLayout(row)

        layout.addWidget(hk_box)

        # 5. Git & Version Info Frame with Branch Switcher!
        git_box = QFrame()
        git_box.setObjectName("GitBox")
        git_box.setStyleSheet(f"""
            #GitBox {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            #GitBox QLabel, #GitBox QCheckBox {{
                border: none;
                background: transparent;
            }}
        """)
        git_layout = QVBoxLayout(git_box)
        git_layout.setContentsMargins(12, 10, 12, 10)
        git_layout.setSpacing(8)

        lbl_git = QLabel("VERSI")
        lbl_git.setStyleSheet(f"color: {THEME['primary']}; font-weight: bold; font-size: 11px;")
        git_layout.addWidget(lbl_git)

        # 1. Baris Informasi Branch Aktif
        curr_b = self.app.updater.get_current_branch()
        b_info_row = QHBoxLayout()
        lbl_b_title = QLabel("Branch Aktif:")
        lbl_b_title.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        b_info_row.addWidget(lbl_b_title)

        self.lbl_branch_status = QLabel(curr_b)
        self.lbl_branch_status.setStyleSheet(f"color: {THEME['primary']}; font-size: 12px; font-weight: bold;")
        b_info_row.addWidget(self.lbl_branch_status)
        b_info_row.addStretch(1)
        git_layout.addLayout(b_info_row)

        # 2. Baris Pengganti Branch Terpisah
        br_row = QHBoxLayout()
        lbl_sw = QLabel("Ganti:")
        lbl_sw.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        br_row.addWidget(lbl_sw)

        self.combo_branch = QComboBox()
        self.combo_branch.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.combo_branch.setMinimumWidth(0)
        avail_branches = self.app.updater.get_available_branches()
        if curr_b not in avail_branches:
            avail_branches.append(curr_b)
        self.combo_branch.addItems(avail_branches)
        if curr_b in avail_branches:
            self.combo_branch.setCurrentIndex(avail_branches.index(curr_b))
        self.combo_branch.currentTextChanged.connect(self.app.on_updater_branch_selection_changed)
        self.combo_branch.setStyleSheet(f"""
            QComboBox {{
                background-color: {THEME['bg_root']};
                color: {THEME['text_primary']};
                font-size: 11px;
                font-weight: 500;
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 2px 8px;
            }}
        """)
        br_row.addWidget(self.combo_branch, 1)

        btn_switch_br = QPushButton("Ganti")
        btn_switch_br.setCursor(Qt.PointingHandCursor)
        btn_switch_br.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_hover']};
                color: {THEME['text_primary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                padding: 3px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {THEME['primary']};
            }}
        """)
        btn_switch_br.clicked.connect(lambda: self.app.switch_updater_branch(self.combo_branch.currentText()))
        br_row.addWidget(btn_switch_br)
        git_layout.addLayout(br_row)

        self.lbl_branch_exp_warning = QLabel(
            "Peringatan: Branch non-'main' bersifat eksperimental, disarankan tetap di 'main' untuk penggunaan stabil."
        )
        self.lbl_branch_exp_warning.setWordWrap(True)
        self.lbl_branch_exp_warning.setStyleSheet(
            f"color: {THEME['warning']}; font-size: 10px; font-weight: 600; "
            f"background-color: rgba(245, 158, 11, 0.10); border: 1px solid {THEME['warning']}; "
            f"border-radius: 4px; padding: 4px 8px;"
        )
        git_layout.addWidget(self.lbl_branch_exp_warning)
        self.update_branch_warning(self.combo_branch.currentText().strip() or curr_b)

        curr_commit = self.app.updater.get_current_commit()
        self.commit_hash = curr_commit.get("hash", "Unknown")
        c_row = QHBoxLayout()
        c_row.addWidget(QLabel("Commit:"))
        self.lbl_commit = QLabel(f"#{self.commit_hash}")
        self.lbl_commit.setCursor(Qt.PointingHandCursor)
        self.lbl_commit.setStyleSheet(f"color: {THEME['primary']}; text-decoration: underline; font-weight: bold;")
        self.lbl_commit.setToolTip("Klik untuk membuka commit di GitHub")
        self.lbl_commit.mousePressEvent = lambda e: self._open_commit_link()
        c_row.addWidget(self.lbl_commit)
        c_row.addStretch(1)
        git_layout.addLayout(c_row)

        self.lbl_commit_msg = QLabel(curr_commit.get("message", ""))
        self.lbl_commit_msg.setWordWrap(True)
        self.lbl_commit_msg.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        git_layout.addWidget(self.lbl_commit_msg)

        # Checkbox Notifikasi Update Otomatis
        self.chk_auto_update_notif = QCheckBox("Notifikasi Update Otomatis")
        self.chk_auto_update_notif.setChecked(self.app.config.get("auto_check_update_on_startup", True))
        self.chk_auto_update_notif.setCursor(Qt.PointingHandCursor)
        self.chk_auto_update_notif.setStyleSheet(f"""
            QCheckBox {{
                background: transparent;
                color: {THEME['text_primary']};
                font-size: 11px;
                font-weight: 600;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                background-color: {THEME['bg_root']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME['primary']};
                border-color: {THEME['primary']};
            }}
        """)
        self.chk_auto_update_notif.toggled.connect(self.app.set_auto_check_update)
        git_layout.addWidget(self.chk_auto_update_notif)

        # Banner Notifikasi Update Baru (tersembunyi saat sudah versi terbaru)
        self._pending_update_branch = curr_b
        self.update_banner = QFrame()
        self.update_banner.setObjectName("UpdateBanner")
        self.update_banner.setStyleSheet(f"""
            #UpdateBanner {{
                background-color: rgba(245, 158, 11, 0.14);
                border: 1px solid {THEME['warning']};
                border-radius: 5px;
            }}
            #UpdateBanner QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        ub_layout = QVBoxLayout(self.update_banner)
        ub_layout.setContentsMargins(8, 6, 8, 6)
        ub_layout.setSpacing(6)

        self.lbl_update_banner = QLabel("")
        self.lbl_update_banner.setWordWrap(True)
        self.lbl_update_banner.setStyleSheet(f"color: {THEME['warning']}; font-size: 11px; font-weight: 600;")
        ub_layout.addWidget(self.lbl_update_banner)

        self.btn_apply_update = QPushButton("Terapkan Update Sekarang")
        self.btn_apply_update.setCursor(Qt.PointingHandCursor)
        self.btn_apply_update.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['warning']};
                color: {THEME['text_dark']};
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: #fbbf24;
            }}
        """)
        self.btn_apply_update.clicked.connect(lambda: self.app.apply_detected_update(self._pending_update_branch))
        ub_layout.addWidget(self.btn_apply_update)
        self.update_banner.hide()
        git_layout.addWidget(self.update_banner)

        self.btn_check_update = QPushButton(" Cek Update")
        self.btn_check_update.setIcon(get_qicon("refresh", size=13, color=THEME["text_dark"]))
        self.btn_check_update.setCursor(Qt.PointingHandCursor)
        self.btn_check_update.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["primary"]};
                color: {THEME["text_dark"]};
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {THEME["accent_neon"]};
            }}
        """)
        self.btn_check_update.clicked.connect(self.app.check_updates)
        git_layout.addWidget(self.btn_check_update)

        layout.addWidget(git_box)
        layout.addStretch(1)

        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        self.refresh_counts()

    def eventFilter(self, obj, event):
        if hasattr(self, "scroll") and obj == self.scroll.viewport() and event.type() == QEvent.Resize:
            if hasattr(self, "container"):
                self.container.setFixedWidth(event.size().width())
        return super().eventFilter(obj, event)

    def _on_hotkey_changed(self, action_id: str, new_key: str):
        if new_key:
            cur_hotkeys = self.app.config.get("hotkeys", {})
            spec_map = dict(self._hotkey_specs)
            for other_id, other_key in cur_hotkeys.items():
                if other_id != action_id and (other_key or "").strip().lower() == new_key.lower():
                    self._hotkey_buttons[action_id].set_hotkey(cur_hotkeys.get(action_id, ""))
                    self.app.show_toast(f"Hotkey '{new_key}' sudah dipakai oleh '{spec_map.get(other_id, other_id)}'!")
                    return
        self.app.set_hotkey(action_id, new_key)
        self._hotkey_buttons[action_id].set_hotkey(new_key)
        spec_map = dict(self._hotkey_specs)
        if new_key:
            self.app.show_toast(f"Hotkey '{spec_map.get(action_id, action_id)}' diubah ke {new_key}")
        else:
            self.app.show_toast(f"Hotkey '{spec_map.get(action_id, action_id)}' dinonaktifkan")

    def refresh_hotkeys(self):
        cur_hotkeys = self.app.config.get("hotkeys", {})
        for aid, btn in self._hotkey_buttons.items():
            btn.set_hotkey(cur_hotkeys.get(aid, ""))

    def refresh_counts(self):
        folder_kt = os.path.abspath("sample/kurang_tepat")
        folder_td = os.path.abspath("sample/tidak_dikenali")
        cnt_kt = len([f for f in os.listdir(folder_kt) if f.endswith(".png") and "seharusnya" not in f]) if os.path.exists(folder_kt) else 0
        cnt_td = len([f for f in os.listdir(folder_td) if f.endswith(".png") and "seharusnya" not in f and os.path.isfile(os.path.join(folder_td, f))]) if os.path.exists(folder_td) else 0
        if hasattr(self, "lbl_koreksi_counts"):
            self.lbl_koreksi_counts.setText(f"🚩 Kurang Tepat: {cnt_kt} belum dikoreksi\n⚠️ Tidak Dikenali: {cnt_td} belum dikoreksi")

    def refresh_git_info(self):
        curr_b = self.app.updater.get_current_branch()
        if hasattr(self, "lbl_branch_status"):
            self.lbl_branch_status.setText(curr_b)
        if hasattr(self, "combo_branch"):
            self.combo_branch.blockSignals(True)
            avail = self.app.updater.get_available_branches()
            if curr_b not in avail:
                avail.append(curr_b)
            self.combo_branch.clear()
            self.combo_branch.addItems(avail)
            self.combo_branch.setCurrentIndex(avail.index(curr_b))
            self.combo_branch.blockSignals(False)
            self.update_branch_warning(curr_b)
        curr_commit = self.app.updater.get_current_commit()
        self.commit_hash = curr_commit.get("hash", "Unknown")
        if hasattr(self, "lbl_commit"):
            self.lbl_commit.setText(f"#{self.commit_hash}")
        if hasattr(self, "lbl_commit_msg"):
            self.lbl_commit_msg.setText(curr_commit.get("message", ""))

    def _open_commit_link(self):
        url = f"https://github.com/anv-group/sambung-kata-overlay/commit/{self.commit_hash}"
        webbrowser.open(url)

    def update_branch_warning(self, branch_name: str):
        """Tampilkan peringatan eksperimental jika branch terpilih bukan 'main'."""
        if not hasattr(self, "lbl_branch_exp_warning"):
            return
        br = (branch_name or "").strip()
        if br and br != "main":
            self.lbl_branch_exp_warning.setText(
                f"Peringatan: Branch '{br}' bersifat eksperimental (hanya untuk pengujian). "
                f"Pengguna umum disarankan tetap menggunakan 'main'."
            )
            self.lbl_branch_exp_warning.show()
        else:
            self.lbl_branch_exp_warning.hide()

    def set_update_available(self, res: dict = None):
        """Menampilkan atau menyembunyikan banner notifikasi update baru di tab SYSTEM."""
        if not hasattr(self, "update_banner"):
            return
        if res and res.get("has_update"):
            branch = res.get("branch") or self.app.updater.get_current_branch()
            behind = int(res.get("behind_count") or 1)
            commits = res.get("commits") or []
            self._pending_update_branch = branch
            preview = ""
            if commits:
                c0 = commits[0]
                preview = f"\n• #{str(c0.get('hash', ''))[:7]}: {c0.get('message', '')}"
            self.lbl_update_banner.setText(f"Update tersedia di '{branch}' ({behind} commit baru){preview}")
            self.update_banner.show()
        else:
            self.update_banner.hide()

    def _on_speed_changed(self, idx):
        speeds = [0.04, 0.08, 0.12, 0.20]
        if 0 <= idx < len(speeds):
            self.app.config["scan_interval_sec"] = speeds[idx]
            self.app.save_config_debounced()
            spd_ms = speeds[idx] * 1000
            self.app.tab_live.lbl_speed.setText(f"{spd_ms:.0f}ms")
            self.app.show_toast(f"Kecepatan scan: {spd_ms:.0f}ms")

    # --- Database Sinkronisasi Handlers ---
    def _refresh_db_mode_ui(self, expand_panel: bool = None, selected_db: bool = None):
        is_db_active = (self.app.config.get("storage_mode", "txt") == "supabase")
        show_panel = is_db_active if expand_panel is None else expand_panel
        is_db_selected = show_panel if selected_db is None else selected_db
        self.db_config_panel.setVisible(show_panel)

        active_qss = f"""
            QPushButton {{
                background-color: {THEME['bg_active'] if 'bg_active' in THEME else THEME['bg_selected']};
                color: {THEME['primary']};
                border: 1px solid {THEME['primary']};
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
            }}
        """
        idle_qss = f"""
            QPushButton {{
                background-color: {THEME['bg_root']};
                color: {THEME['text_secondary']};
                border: 1px solid {THEME['border']};
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                border-color: {THEME['border_focus']};
                color: {THEME['text_primary']};
            }}
        """
        self.btn_mode_txt.setStyleSheet(idle_qss if is_db_selected else active_qss)
        self.btn_mode_db.setStyleSheet(active_qss if is_db_selected else idle_qss)
        self.btn_mode_txt.setIcon(get_qicon("book", size=12, color=THEME["text_secondary"] if is_db_selected else THEME["primary"]))
        self.btn_mode_db.setIcon(get_qicon("supabase", size=12, color=THEME["primary"] if is_db_selected else THEME["text_secondary"]))

    def refresh_db_status(self, state_code: str, detail: str = ""):
        badge_map = {
            "txt": ("MODE TXT", THEME["text_secondary"]),
            "connecting": ("MENYAMBUNG", THEME["warning"]),
            "syncing": ("SINKRONISASI", THEME["warning"]),
            "live": ("Terhubung", THEME["primary"]),
            "offline": ("OFFLINE", THEME["warning"]),
            "error": ("ERROR", THEME["danger"]),
        }
        txt, col = badge_map.get(state_code, ("MODE TXT", THEME["text_secondary"]))
        self.lbl_db_badge.setText(txt)
        self.lbl_db_badge.setStyleSheet(f"color: {col}; font-size: 10px; font-weight: bold;")
        if detail:
            self.lbl_db_status.setText(detail)
            self.lbl_db_status.setStyleSheet(
                f"color: {THEME['danger'] if state_code == 'error' else THEME['text_secondary']}; font-size: 11px;"
            )
        self._refresh_db_mode_ui(expand_panel=True if state_code != "txt" or self.db_config_panel.isVisible() else False)
        self.refresh_db_stats()

    def refresh_db_stats(self, last_sync_str: str = None, last_event_note: str = None):
        is_db = (self.app.config.get("storage_mode", "txt") == "supabase")
        self.db_stats_panel.setVisible(is_db)
        if hasattr(self, "btn_db_resync"):
            self.btn_db_resync.setVisible(is_db)
        if not is_db:
            return
        wl_cnt = len(self.app.solver.whitelisted_words)
        bl_cnt = len(self.app.solver.blacklisted_words)
        cm_cnt = len(self.app.solver.db_custom_set)
        sync_t = last_sync_str if last_sync_str is not None else getattr(self.app, "_last_db_sync_time", "-")
        ev_note = last_event_note if last_event_note is not None else getattr(self.app, "_last_db_event_note", "")
        on_cnt = getattr(self.app, "_online_users_count", 0)
        on_names = getattr(self.app, "_online_users_names", []) or []
        if on_cnt > 0:
            names_str = ", ".join(on_names)
            self.lbl_stat_online.setText(f"{on_cnt} Online ({names_str})" if names_str else f"{on_cnt} Online")
            self.lbl_stat_online.setStyleSheet(f"color: {THEME['primary']}; font-size: 10px; font-weight: bold;")
        else:
            self.lbl_stat_online.setText("0 Online")
            self.lbl_stat_online.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 10px; font-weight: 600;")

        self.lbl_stat_wl_val.setText(str(wl_cnt))
        self.lbl_stat_bl_val.setText(str(bl_cnt))
        self.lbl_stat_cm_val.setText(str(cm_cnt))
        self.lbl_stat_sync_time.setText(sync_t or "-")
        self.lbl_stat_last_act.setText(ev_note or "-")

    def _on_select_txt_mode(self):
        if self.app.config.get("storage_mode", "txt") != "txt":
            self.app.switch_to_txt_mode()
        self._refresh_db_mode_ui(expand_panel=False, selected_db=False)

    def _on_select_db_mode(self):
        self._refresh_db_mode_ui(expand_panel=True, selected_db=True)
        url = self.edit_sb_url.text().strip()
        key = self.edit_sb_key.text().strip()
        if url and key and self.app.config.get("storage_mode", "txt") != "supabase":
            self._on_connect_clicked()
        elif not url or not key:
            self.lbl_db_status.setText("Isi Project URL & Anon Key (atau Tempel Invite Config), lalu klik Tes & Hubungkan.")
            self.lbl_db_status.setStyleSheet(f"color: {THEME['warning']}; font-size: 11px;")

    def _toggle_key_visibility(self):
        if self.edit_sb_key.echoMode() == QLineEdit.Password:
            self.edit_sb_key.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key.setIcon(get_qicon("eye_off", size=14, color=THEME["primary"]))
            self.btn_toggle_key.setToolTip("Sembunyikan Anon Key")
        else:
            self.edit_sb_key.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key.setIcon(get_qicon("eye", size=14, color=THEME["text_secondary"]))
            self.btn_toggle_key.setToolTip("Tampilkan Anon Key")

    def _copy_sql_setup(self):
        from db_sync import SQL_SETUP_SCRIPT
        QApplication.clipboard().setText(SQL_SETUP_SCRIPT)
        self.app.show_toast("SQL Setup disalin! Tempel & Run di Supabase SQL Editor.")

    def _copy_invite_config(self):
        from db_sync import encode_invite_config
        try:
            token = encode_invite_config(self.edit_sb_url.text(), self.edit_sb_key.text())
            QApplication.clipboard().setText(token)
            self.app.show_toast("Invite Config disalin ke clipboard! Kirim ke teman grup Anda.")
        except ValueError as exc:
            self.app.show_toast(str(exc))

    def _paste_invite_config(self):
        from db_sync import decode_invite_config
        clip_txt = (QApplication.clipboard().text() or "").strip()
        raw = ""
        if clip_txt.startswith("saka-db://") or (clip_txt.startswith("{") and "url" in clip_txt):
            raw = clip_txt
        else:
            val, ok = QInputDialog.getText(
                self.window(),
                "Tempel Invite Config",
                "Clipboard belum berisi kode invite.\nTempel teks Invite Config dari teman (saka-db://...) untuk isi otomatis:",
            )
            if not ok or not val.strip():
                return
            raw = val.strip()
        try:
            url, key = decode_invite_config(raw)
            self.edit_sb_url.setText(url)
            self.edit_sb_key.setText(key)
            self.app.show_toast("Invite Config diterapkan! Klik Tes & Hubungkan.")
        except ValueError as exc:
            QMessageBox.warning(self.window(), "Invite Config Tidak Valid", str(exc))

    def _on_connect_clicked(self):
        from db_sync import normalize_supabase_url
        try:
            url = normalize_supabase_url(self.edit_sb_url.text())
        except ValueError as exc:
            QMessageBox.warning(self.window(), "URL Tidak Valid", str(exc))
            return
        key = self.edit_sb_key.text().strip()
        nick = self.edit_sb_nick.text().strip()
        if not url or not key:
            QMessageBox.warning(self.window(), "Data Belum Lengkap", "Project URL dan Anon Key wajib diisi.")
            return

        self.edit_sb_url.setText(url)
        self.btn_db_connect.setEnabled(False)
        self.btn_db_connect.setText(" Menguji...")
        self.lbl_db_status.setText("Menguji koneksi ke Supabase...")
        self.lbl_db_status.setStyleSheet(f"color: {THEME['warning']}; font-size: 11px;")

        def _done(ok: bool, msg: str):
            self.btn_db_connect.setEnabled(True)
            self.btn_db_connect.setText(" Tes & Hubungkan")
            if ok:
                self.app.activate_database_mode(url, key, nick)
                self._refresh_db_mode_ui(expand_panel=True)
                self.app.show_toast("Terhubung ke Database Privat (Real-Time)!")
            else:
                self.lbl_db_status.setText(msg)
                self.lbl_db_status.setStyleSheet(f"color: {THEME['danger']}; font-size: 11px;")
                QMessageBox.warning(self.window(), "Koneksi Database Gagal", msg)

        self.app.test_database_connection(url, key, _done)

    def _on_import_txt_clicked(self):
        from db_sync import normalize_supabase_url
        try:
            url = normalize_supabase_url(self.edit_sb_url.text())
        except ValueError as exc:
            QMessageBox.warning(self.window(), "URL Tidak Valid", str(exc))
            return
        key = self.edit_sb_key.text().strip()
        nick = self.edit_sb_nick.text().strip()
        if not url or not key:
            QMessageBox.warning(self.window(), "Data Belum Lengkap", "Isi URL & Anon Key terlebih dahulu.")
            return
        self.app.import_txt_to_database(url, key, nick)

    def _on_download_db_clicked(self):
        from db_sync import normalize_supabase_url
        try:
            url = normalize_supabase_url(self.edit_sb_url.text())
        except ValueError as exc:
            QMessageBox.warning(self.window(), "URL Tidak Valid", str(exc))
            return
        key = self.edit_sb_key.text().strip()
        if not url or not key:
            QMessageBox.warning(self.window(), "Data Belum Lengkap", "Isi URL & Anon Key terlebih dahulu.")
            return
        self.app.download_database_to_txt(url, key)
