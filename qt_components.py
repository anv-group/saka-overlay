import os
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from qt_theme import THEME, get_qicon

class QtTopTabStrip(QWidget):
    """
    Bilah navigasi 4 Tab Utama: LIVE, TAGS, KAMUS, SYSTEM
    Bergaya Cyber Tabs dengan indikator border aktif neon.
    """
    tab_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_tab = "live"
        self.buttons = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 0)
        layout.setSpacing(4)

        tabs = [
            ("live", "LIVE", "zap"),
            ("tags", "TAGS", "tag"),
            ("kamus", "KAMUS", "book"),
            ("system", "SYSTEM", "settings")
        ]

        for tab_id, label, icon_name in tabs:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(get_qicon(icon_name, size=14, color=THEME["text_secondary"]))
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda checked=False, tid=tab_id: self.select_tab(tid))
            layout.addWidget(btn)
            self.buttons[tab_id] = btn

        self._update_styles()

    def select_tab(self, tab_id: str):
        if self.active_tab == tab_id:
            return
        self.active_tab = tab_id
        self._update_styles()
        self.tab_changed.emit(tab_id)

    def _update_styles(self):
        for tid, btn in self.buttons.items():
            is_active = (tid == self.active_tab)
            if is_active:
                btn.setIcon(get_qicon(
                    "zap" if tid=="live" else "tag" if tid=="tags" else "book" if tid=="kamus" else "settings",
                    size=14, color=THEME["primary"]
                ))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {THEME["bg_card"]};
                        color: {THEME["primary"]};
                        font-weight: bold;
                        border: 1px solid {THEME["border_focus"]};
                        border-bottom: 2px solid {THEME["primary"]};
                        border-top-left-radius: 6px;
                        border-top-right-radius: 6px;
                        border-bottom-left-radius: 0px;
                        border-bottom-right-radius: 0px;
                        padding: 4px 10px;
                    }}
                """)
            else:
                btn.setIcon(get_qicon(
                    "zap" if tid=="live" else "tag" if tid=="tags" else "book" if tid=="kamus" else "settings",
                    size=14, color=THEME["text_secondary"]
                ))
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {THEME["text_secondary"]};
                        font-weight: 500;
                        border: 1px solid transparent;
                        border-bottom: 1px solid {THEME["border"]};
                        border-top-left-radius: 6px;
                        border-top-right-radius: 6px;
                        border-bottom-left-radius: 0px;
                        border-bottom-right-radius: 0px;
                        padding: 4px 10px;
                    }}
                    QPushButton:hover {{
                        background-color: {THEME["bg_hover"]};
                        color: {THEME["text_primary"]};
                    }}
                """)


class QtSubTabStrip(QWidget):
    """
    Sub-Tab Navigasi Ramping untuk sub-view di tab TAGS dan KAMUS.
    """
    sub_tab_changed = Signal(str)

    def __init__(self, tabs_def, parent=None):
        super().__init__(parent)
        self.active_sub = tabs_def[0][0] if tabs_def else ""
        self.buttons = {}
        self.tabs_def = tabs_def

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 4)
        layout.setSpacing(4)

        for sub_id, label, icon_name in tabs_def:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            if icon_name:
                btn.setIcon(get_qicon(icon_name, size=12, color=THEME["text_secondary"]))
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda checked=False, sid=sub_id: self.select_sub_tab(sid))
            layout.addWidget(btn)
            self.buttons[sub_id] = btn

        self._update_styles()

    def select_sub_tab(self, sub_id: str):
        if self.active_sub == sub_id:
            return
        self.active_sub = sub_id
        self._update_styles()
        self.sub_tab_changed.emit(sub_id)

    def update_tab_label(self, sub_id: str, new_label: str):
        if sub_id in self.buttons:
            self.buttons[sub_id].setText(new_label)

    def _update_styles(self):
        for sid, btn in self.buttons.items():
            is_active = (sid == self.active_sub)
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {THEME["border_focus"]};
                        color: {THEME["primary"]};
                        font-size: 11px;
                        font-weight: bold;
                        border: 1px solid {THEME["border_highlight"]};
                        border-radius: 4px;
                        padding: 2px 8px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {THEME["bg_card"]};
                        color: {THEME["text_muted"]};
                        font-size: 11px;
                        border: 1px solid {THEME["border"]};
                        border-radius: 4px;
                        padding: 2px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {THEME["bg_hover"]};
                        color: {THEME["text_primary"]};
                    }}
                """)


class QtMiniTickerBar(QFrame):
    """
    Mini Ticker Bar di tab non-LIVE (Tactical Cyber Live OCR & Manual Status Bar).
    - Mode Live OCR: Tema Merah (Danger).
    - Mode Manual Override: Tema Biru (Accent Cyan).
    - State Menunggu: [LIVE] / [MANUAL] solid badge (inverted dark text) + "Menunggu OCR...".
    - State Terdeteksi: [<PREFIX>] solid badge + <KATA> rekomendasi + mentok kanan <TAG BADGE>.
    - Klik di mana saja untuk kembali ke Tab LIVE.
    """
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MiniTickerBar")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        self.setToolTip("Klik untuk kembali ke Tab LIVE")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        # 1. Badge Kiri (Kotak Solid [LIVE], [MANUAL], atau [AWALAN])
        self.badge_status = QLabel("LIVE")
        self.badge_status.setFixedHeight(20)
        self.badge_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.badge_status)

        # 2. Teks Utama (Status Menunggu atau Kata Rekomendasi)
        self.lbl_text = QLabel("Menunggu OCR...")
        self.lbl_text.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        layout.addWidget(self.lbl_text)

        # 3. Spacer agar tag mentok di kanan
        layout.addStretch(1)

        # 4. Badge Tag Kata Rekomendasi (Mentok Paling Kanan)
        self.badge_tag = QLabel("")
        self.badge_tag.setFixedHeight(20)
        self.badge_tag.setAlignment(Qt.AlignCenter)
        self.badge_tag.hide()
        layout.addWidget(self.badge_tag)

        self._is_manual = False
        self._apply_theme(is_manual=False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def _apply_theme(self, is_manual: bool):
        self._is_manual = is_manual
        if is_manual:
            # Tema Biru / Tactical Cyan (Manual Override)
            bg_bar = "#0b1520"
            border_bar = "#162f46"
            hover_bar = "#13273a"
        else:
            # Tema Merah (Live OCR)
            bg_bar = "#180e10"
            border_bar = "#351519"
            hover_bar = "#261317"

        self.setStyleSheet(f"""
            #MiniTickerBar {{
                background-color: {bg_bar};
                border-bottom: 1px solid {border_bar};
            }}
            #MiniTickerBar:hover {{
                background-color: {hover_bar};
            }}
            #MiniTickerBar QLabel {{
                border: none;
                background: transparent;
            }}
        """)

    def update_ticker(self, prefix: str, top_item: dict = None, is_manual: bool = False, two_tone: bool = True):
        self._apply_theme(is_manual)

        # Background warna inverted untuk text di dalam badge
        bg_inverted = "#0b1520" if is_manual else "#180e10"
        badge_bg = THEME["accent_cyan"] if is_manual else THEME["danger"]
        badge_text_color = bg_inverted

        if not prefix:
            # State Menunggu
            badge_label = "MANUAL" if is_manual else "LIVE"
            self.badge_status.setText(badge_label)
            self.badge_status.setStyleSheet(f"""
                background-color: {badge_bg};
                color: {badge_text_color};
                font-weight: bold;
                font-size: 10px;
                padding: 2px 7px;
                border-radius: 3px;
                border: none;
            """)

            waiting_text = "Menunggu input manual..." if is_manual else "Menunggu OCR..."
            text_color = "#7dd3fc" if is_manual else "#fca5a5"
            self.lbl_text.setText(waiting_text)
            self.lbl_text.setStyleSheet(f"color: {text_color}; font-size: 11px; font-weight: 500; border: none; background: transparent;")

            self.badge_tag.hide()
            return

        # State Terdeteksi: [AWALAN] KATA
        self.badge_status.setText(prefix.upper())
        self.badge_status.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {badge_text_color};
            font-weight: bold;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 3px;
            border: none;
        """)

        if top_item:
            kata = top_item.get("kata", "").upper()
            tipe = top_item.get("tipe", "NORMAL")
            deskripsi = top_item.get("deskripsi", "")

            # Two-Tone atau Bold
            p_upper = prefix.upper()
            if two_tone and p_upper and kata.startswith(p_upper):
                p_len = len(p_upper)
                p_part = kata[:p_len]
                rest_part = kata[p_len:]
                self.lbl_text.setText(
                    f"<span style='color: {THEME['text_muted']}; font-weight: 500;'>{p_part}</span>"
                    f"<span style='color: {THEME['text_primary']}; font-weight: bold; font-size: 12px;'>{rest_part}</span>"
                )
            else:
                self.lbl_text.setText(f"<span style='color: {THEME['text_primary']}; font-weight: bold; font-size: 12px;'>{kata}</span>")

            self.lbl_text.setStyleSheet("border: none; background: transparent;")

            # Tag Badge di Ujung Kanan
            if tipe == "CUSTOM_TRAP":
                b_name = top_item.get("badge_name") or f"Akhiran {top_item.get('suffix', '').upper()}"
                bg = top_item.get("color", THEME["primary"])
                self.badge_tag.setText(b_name)
                self.badge_tag.setStyleSheet(f"background-color: {bg}; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; padding: 2px 7px; border-radius: 3px; border: none;")
                self.badge_tag.show()
            elif tipe == "JEBAKAN_X":
                self.badge_tag.setText("Jebakan X")
                self.badge_tag.setStyleSheet(f"background-color: {THEME['danger']}; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; padding: 2px 7px; border-radius: 3px; border: none;")
                self.badge_tag.show()
            elif tipe == "JEBAKAN_SULIT":
                clean_desc = deskripsi.replace(" (Sulit)", "").replace("(Sulit)", "").strip()
                self.badge_tag.setText(clean_desc.title())
                self.badge_tag.setStyleSheet(f"background-color: #fab387; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; padding: 2px 7px; border-radius: 3px; border: none;")
                self.badge_tag.show()
            else:
                is_santai = (deskripsi == "Kata Santai")
                self.badge_tag.setText("Santai" if is_santai else "Normal")
                bg = "#a6e3a1" if is_santai else THEME["border_focus"]
                color = THEME['text_dark'] if is_santai else THEME['text_primary']
                self.badge_tag.setStyleSheet(f"background-color: {bg}; color: {color}; font-size: 10px; font-weight: 500; padding: 2px 7px; border-radius: 3px; border: none;")
                self.badge_tag.show()
        else:
            self.lbl_text.setText("<span style='color: #6c7086; font-style: italic; font-size: 11px;'>(Tidak ada rekomendasi)</span>")
            self.lbl_text.setStyleSheet("border: none; background: transparent;")
            self.badge_tag.hide()


class QtSegmentedPills(QWidget):
    """
    Segmented Cyber Pill Mode Switch (DEFAULT, SANTAI, BRUTAL)
    """
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_mode = "default"
        self.buttons = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        modes = [
            ("default", "DEFAULT", "zap"),
            ("santai", "SANTAI", "book"),
            ("brutal", "BRUTAL", "danger")
        ]

        for mid, label, _ in modes:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked=False, m=mid: self.set_mode(m))
            layout.addWidget(btn)
            self.buttons[mid] = btn

        self._update_styles()

    def set_mode(self, mode: str):
        if self.active_mode == mode:
            return
        self.active_mode = mode
        self._update_styles()
        self.mode_changed.emit(mode)

    def _update_styles(self):
        for mid, btn in self.buttons.items():
            is_active = (mid == self.active_mode)
            if is_active:
                if mid == "brutal":
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {THEME["danger_bg"]};
                            color: {THEME["danger"]};
                            border: 1px solid {THEME["danger"]};
                            border-radius: 4px;
                            font-weight: bold;
                            font-size: 11px;
                        }}
                    """)
                else:
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {THEME["bg_selected"]};
                            color: {THEME["primary"]};
                            border: 1px solid {THEME["primary"]};
                            border-radius: 4px;
                            font-weight: bold;
                            font-size: 11px;
                        }}
                    """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {THEME["bg_card"]};
                        color: {THEME["text_muted"]};
                        border: 1px solid {THEME["border"]};
                        border-radius: 4px;
                        font-weight: 500;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        background-color: {THEME["bg_hover"]};
                        color: {THEME["text_primary"]};
                    }}
                """)

class QtCustomTitleBar(QWidget):
    """
    Custom Frameless Window Titlebar dengan Logo Horizontal SAKA Overlay,
    Tombol Restart (Mode Dev), Minimize, dan Close.
    """
    def __init__(self, parent_window, logo_path, on_restart_func=None):
        super().__init__(parent_window)
        self.win = parent_window
        self.on_restart = on_restart_func
        self.setFixedHeight(32)
        self.setObjectName("CustomTitleBar")
        self.setStyleSheet(f"""
            #CustomTitleBar {{
                background-color: {THEME["bg_root"]};
                border-bottom: 1px solid {THEME["border"]};
            }}
            #CustomTitleBar QLabel {{
                border: none;
                background: transparent;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(6)

        # Logo horizontal (177x28 -> scaled to height 20)
        self.lbl_logo = QLabel()
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            if not pix.isNull():
                self.lbl_logo.setPixmap(pix.scaledToHeight(20, Qt.SmoothTransformation))
        layout.addWidget(self.lbl_logo)

        layout.addStretch(1)

        # Restart Button (Dev Mode)
        self.btn_restart = QPushButton("⚡")
        self.btn_restart.setFixedSize(30, 32)
        self.btn_restart.setCursor(Qt.PointingHandCursor)
        self.btn_restart.setToolTip("Restart Aplikasi (Mode Dev)")
        self.btn_restart.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {THEME["warning"]};
                font-size: 13px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME["bg_card"]};
                color: #fab387;
            }}
        """)
        if on_restart_func:
            self.btn_restart.clicked.connect(on_restart_func)
        self.btn_restart.hide()  # Hidden by default until dev_mode enabled
        layout.addWidget(self.btn_restart)

        # Pin Button (Always-on-Top)
        self.btn_pin = QPushButton()
        self.btn_pin.setFixedSize(30, 32)
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME["bg_hover"]};
            }}
        """)
        self.btn_pin.clicked.connect(self.win.toggle_always_on_top)
        layout.addWidget(self.btn_pin)
        self.set_pinned(True)

        # Minimize Button
        self.btn_min = QPushButton()
        self.btn_min.setIcon(get_qicon("minus", size=13, color=THEME["text_secondary"]))
        self.btn_min.setFixedSize(32, 32)
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.setToolTip("Minimize Window")
        self.btn_min.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME["bg_hover"]};
            }}
        """)
        self.btn_min.clicked.connect(self.win.showMinimized)
        layout.addWidget(self.btn_min)

        # Close Button
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(38, 32)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("Tutup Aplikasi")
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {THEME["text_secondary"]};
                font-size: 12px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {THEME["danger"]};
                color: #ffffff;
            }}
        """)
        self.btn_close.clicked.connect(self.win.close)
        layout.addWidget(self.btn_close)

        self._drag_pos = None

    def set_dev_mode(self, enabled: bool):
        self.btn_restart.setVisible(enabled)

    def set_pinned(self, pinned: bool):
        self.is_pinned = pinned
        if pinned:
            self.btn_pin.setIcon(get_qicon("pin", size=14, color=THEME["primary"]))
            self.btn_pin.setToolTip("Lepas Pin (Always-on-Top Aktif)")
        else:
            self.btn_pin.setIcon(get_qicon("pin", size=14, color=THEME["text_muted"]))
            self.btn_pin.setToolTip("Sematkan di Atas (Always-on-Top Nonaktif)")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.win.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.win.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

