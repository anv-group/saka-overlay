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
    Mini Ticker Bar di tab non-LIVE.
    Menampilkan status realtime OCR dan awalan aktif dengan satu klik kembali ke LIVE.
    """
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME["bg_card"]};
                border-bottom: 1px solid {THEME["border"]};
                padding: 2px 8px;
            }}
            QFrame:hover {{
                background-color: {THEME["bg_hover"]};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        self.dot_lbl = QLabel("●")
        self.dot_lbl.setStyleSheet(f"color: {THEME['primary']}; font-size: 10px;")
        layout.addWidget(self.dot_lbl)

        self.lbl_text = QLabel("LIVE OCR AKTIF: Menunggu deteksi awalan kata...")
        self.lbl_text.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.lbl_text, 1)

        btn_go = QLabel("➔ BUKA LIVE")
        btn_go.setStyleSheet(f"color: {THEME['primary']}; font-size: 10px; font-weight: bold;")
        layout.addWidget(btn_go)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def update_ticker(self, prefix: str, top_word: str = ""):
        if prefix:
            if top_word:
                self.lbl_text.setText(f"LIVE: Awalan [{prefix}] ➔ Rekomendasi: {top_word}")
            else:
                self.lbl_text.setText(f"LIVE: Awalan [{prefix}] terdeteksi")
            self.lbl_text.setStyleSheet(f"color: {THEME['primary']}; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_text.setText("LIVE OCR AKTIF: Menunggu deteksi awalan kata...")
            self.lbl_text.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; font-weight: 500;")


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

