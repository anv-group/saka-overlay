import webbrowser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QFrame, QComboBox, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from qt_theme import THEME, get_qicon
from qt_components import QtSubTabStrip, QtSegmentedPills

# --- Word Card Widget ---
class QtWordCardWidget(QFrame):
    """
    Kartu Rekomendasi Kata yang Ringan dan Cepat (High-Performance Word Card)
    """
    toggle_whitelist = Signal(str)
    block_word = Signal(str)
    card_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.word = ""
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border"]};
                border-radius: 5px;
            }}
            QFrame:hover {{
                background-color: {THEME["bg_card_alt"]};
                border-color: {THEME["border_focus"]};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        # Tombol Bintang Whitelist
        self.btn_star = QPushButton()
        self.btn_star.setFixedSize(20, 20)
        self.btn_star.setCursor(Qt.PointingHandCursor)
        self.btn_star.setStyleSheet("background: transparent; border: none; padding: 0px;")
        self.btn_star.clicked.connect(lambda: self.toggle_whitelist.emit(self.word))
        layout.addWidget(self.btn_star)

        # Kata Utama
        self.lbl_word = QLabel()
        self.lbl_word.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {THEME['text_primary']}; background: transparent;")
        layout.addWidget(self.lbl_word)

        # Akhiran Kata
        self.lbl_suffix = QLabel()
        self.lbl_suffix.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {THEME['accent_cyan']}; background: transparent;")
        layout.addWidget(self.lbl_suffix)

        layout.addStretch(1)

        # Badge Tier / Tag
        self.badge_tier = QLabel()
        self.badge_tier.setFixedHeight(18)
        layout.addWidget(self.badge_tier)

        # Tombol Silang Blocklist
        self.btn_del = QPushButton()
        self.btn_del.setFixedSize(20, 20)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.setIcon(get_qicon("cross", size=12, color=THEME["text_muted"]))
        self.btn_del.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {THEME["danger_bg"]};
                border-radius: 3px;
            }}
        """)
        self.btn_del.clicked.connect(lambda: self.block_word.emit(self.word))
        layout.addWidget(self.btn_del)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.card_clicked.emit(self.word)
        super().mousePressEvent(event)

    def update_data(self, item: dict, prefix_upper: str = ""):
        self.word = item.get("kata", "").upper()
        tipe = item.get("tipe", "NORMAL")
        deskripsi = item.get("deskripsi", "")
        is_wl = item.get("is_whitelisted", False)

        # Hitung suffix
        if prefix_upper and self.word.startswith(prefix_upper):
            sisa = self.word[len(prefix_upper):]
        else:
            sisa = self.word

        self.lbl_word.setText(self.word)
        self.lbl_suffix.setText(f"-{sisa}" if sisa else "")

        if is_wl:
            self.btn_star.setIcon(get_qicon("star_filled", size=14, color=THEME["warning"]))
            self.btn_star.setToolTip("Terdaftar di Whitelist (Klik untuk hapus)")
        else:
            self.btn_star.setIcon(get_qicon("star", size=14, color=THEME["text_muted"]))
            self.btn_star.setToolTip("Tambah ke Whitelist")

        if tipe == "CUSTOM_TRAP":
            b_name = item.get("badge_name") or f"Akhiran {item.get('suffix', '').upper()}"
            bg = item.get("color", THEME["primary"])
            self.badge_tier.setText(b_name)
            self.badge_tier.setStyleSheet(f"background-color: {bg}; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; padding: 1px 6px; border-radius: 3px;")
        elif tipe == "JEBAKAN_X":
            self.badge_tier.setText("Jebakan X")
            self.badge_tier.setStyleSheet(f"background-color: {THEME['danger']}; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; padding: 1px 6px; border-radius: 3px;")
        elif tipe == "JEBAKAN_SULIT":
            clean_desc = deskripsi.replace(" (Sulit)", "").replace("(Sulit)", "").strip()
            self.badge_tier.setText(clean_desc.title())
            self.badge_tier.setStyleSheet(f"background-color: #fab387; color: {THEME['text_dark']}; font-size: 10px; font-weight: bold; padding: 1px 6px; border-radius: 3px;")
        else:
            self.badge_tier.setText("Santai" if deskripsi == "Kata Santai" else "Normal")
            bg = "#a6e3a1" if deskripsi == "Kata Santai" else THEME["border_focus"]
            self.badge_tier.setStyleSheet(f"background-color: {bg}; color: {THEME['text_primary']}; font-size: 10px; font-weight: 500; padding: 1px 6px; border-radius: 3px;")


# --- Tab 1: LIVE Tab View ---
class QtLiveTabView(QWidget):
    start_stop_clicked = Signal()
    mode_changed = Signal(str)
    search_text_changed = Signal(str)
    sort_mode_toggled = Signal()

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.word_card_widgets = []
        self.tag_chip_buttons = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(8)

        # Action Bar
        act_bar = QWidget()
        act_layout = QHBoxLayout(act_bar)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(8)

        self.btn_toggle = QPushButton(" MULAI")
        self.btn_toggle.setIcon(get_qicon("play", size=14, color=THEME["text_dark"]))
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setFixedHeight(32)
        self.btn_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["primary"]};
                color: {THEME["text_dark"]};
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 4px 14px;
            }}
            QPushButton:hover {{
                background-color: {THEME["accent_neon"]};
            }}
        """)
        self.btn_toggle.clicked.connect(self.start_stop_clicked.emit)
        act_layout.addWidget(self.btn_toggle)

        act_layout.addStretch(1)

        self.btn_sort = QPushButton(" DEFAULT")
        self.btn_sort.setIcon(get_qicon("sort", size=13, color=THEME["text_secondary"]))
        self.btn_sort.setCursor(Qt.PointingHandCursor)
        self.btn_sort.setFixedHeight(28)
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
            }}
        """)
        self.btn_sort.clicked.connect(self.sort_mode_toggled.emit)
        act_layout.addWidget(self.btn_sort)

        self.lbl_speed = QLabel("Speed: 40ms [Ultra Instan]")
        self.lbl_speed.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; font-weight: 500;")
        act_layout.addWidget(self.lbl_speed)

        layout.addWidget(act_bar)

        # Mode Pills
        self.mode_pills = QtSegmentedPills()
        self.mode_pills.mode_changed.connect(self.mode_changed.emit)
        layout.addWidget(self.mode_pills)

        # HUD Box
        hud_box = QFrame()
        hud_box.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME["bg_card"]};
                border: 1px solid {THEME["border"]};
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        hud_layout = QHBoxLayout(hud_box)
        hud_layout.setContentsMargins(10, 8, 10, 8)
        hud_layout.setSpacing(12)

        prefix_frame = QFrame()
        prefix_frame.setFixedSize(70, 52)
        prefix_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME["bg_root"]};
                border: 1px solid {THEME["border_focus"]};
                border-radius: 5px;
            }}
        """)
        pf_layout = QVBoxLayout(prefix_frame)
        pf_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_prefix = QLabel("-")
        self.lbl_prefix.setAlignment(Qt.AlignCenter)
        self.lbl_prefix.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {THEME['text_primary']};")
        pf_layout.addWidget(self.lbl_prefix)
        hud_layout.addWidget(prefix_frame)

        right_box = QVBoxLayout()
        right_box.setSpacing(4)

        info_row = QHBoxLayout()
        info_row.addWidget(QLabel("AWALAN TERDETEKSI"))
        self.lbl_conf = QLabel("Menunggu...")
        self.lbl_conf.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px; font-weight: bold;")
        info_row.addStretch(1)
        info_row.addWidget(self.lbl_conf)
        right_box.addLayout(info_row)

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Ketik awalan kata manual...")
        self.edit_search.textChanged.connect(self.search_text_changed.emit)
        right_box.addWidget(self.edit_search)

        hud_layout.addLayout(right_box, 1)
        layout.addWidget(hud_box)

        # Quick Tag Chips Flow Container
        self.tag_scroll = QScrollArea()
        self.tag_scroll.setFixedHeight(34)
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setFrameShape(QFrame.NoFrame)
        self.tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.tag_bar = QWidget()
        self.tag_bar_layout = QHBoxLayout(self.tag_bar)
        self.tag_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_bar_layout.setSpacing(4)
        self.tag_scroll.setWidget(self.tag_bar)
        layout.addWidget(self.tag_scroll)

        # Cards Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 4, 0)
        self.cards_layout.setSpacing(4)

        self.lbl_empty = QLabel("Belum ada kata terdeteksi.\nTekan MULAI untuk memindai otomatis.")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        self.lbl_empty.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 12px; font-style: italic; padding: 20px;")
        self.cards_layout.addWidget(self.lbl_empty)

        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area, 1)

    def set_scanning_state(self, is_scanning: bool):
        if is_scanning:
            self.btn_toggle.setText(" STOP")
            self.btn_toggle.setIcon(get_qicon("stop", size=14, color="#ffffff"))
            self.btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME["danger"]};
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: bold;
                    border: none;
                    border-radius: 5px;
                    padding: 4px 14px;
                }}
            """)
        else:
            self.btn_toggle.setText(" MULAI")
            self.btn_toggle.setIcon(get_qicon("play", size=14, color=THEME["text_dark"]))
            self.btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME["primary"]};
                    color: {THEME["text_dark"]};
                    font-size: 12px;
                    font-weight: bold;
                    border: none;
                    border-radius: 5px;
                    padding: 4px 14px;
                }}
                QPushButton:hover {{
                    background-color: {THEME["accent_neon"]};
                }}
            """)

    def refresh_quick_tags(self, categories: list):
        # Clear existing
        while self.tag_bar_layout.count():
            item = self.tag_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        btn_ico = QPushButton()
        btn_ico.setIcon(get_qicon("tag", size=13, color=THEME["text_secondary"]))
        btn_ico.setFixedSize(26, 26)
        btn_ico.setCursor(Qt.PointingHandCursor)
        btn_ico.setStyleSheet(f"background: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 4px;")
        btn_ico.clicked.connect(self.app.open_tags_tab)
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
        self.lbl_prefix.setText(prefix if prefix else "-")
        if prefix:
            self.lbl_conf.setText(f"Akurasi: {conf_pct}%")
            self.lbl_conf.setStyleSheet(f"color: {THEME['primary']}; font-size: 11px; font-weight: bold;")
        else:
            self.lbl_conf.setText("Menunggu...")
            self.lbl_conf.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")

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
            card.card_clicked.connect(self.app.on_copy_word)
            self.cards_layout.addWidget(card)
            self.word_card_widgets.append(card)

        for i, card in enumerate(self.word_card_widgets):
            if i < len(words):
                card.update_data(words[i], prefix_upper=prefix.upper())
                card.show()
            else:
                card.hide()


# --- Tab 2: TAGS Tab View ---
class QtTagsTabView(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.sub_strip = QtSubTabStrip([
            ("brutal", "BRUTAL PRESET", "zap"),
            ("custom", "KELOLA SEMUA TAG", "tag")
        ])
        self.sub_strip.sub_tab_changed.connect(self._on_sub_tab_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(6)
        layout.addWidget(self.sub_strip)

        self.stack_brutal = QWidget()
        self.stack_custom = QWidget()

        layout.addWidget(self.stack_brutal, 1)
        layout.addWidget(self.stack_custom, 1)

        self._build_brutal_view()
        self._build_custom_view()
        self._on_sub_tab_changed("brutal")

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

        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 5px;")
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(8, 6, 8, 6)

        lbl = QLabel("PRESET TAG MODE BRUTAL")
        lbl.setStyleSheet(f"color: {THEME['danger']}; font-weight: bold; font-size: 11px;")
        h_layout.addWidget(lbl)
        h_layout.addStretch(1)

        btn_all = QPushButton("Pilih Semua")
        btn_all.setFixedHeight(24)
        btn_all.setCursor(Qt.PointingHandCursor)
        btn_all.setStyleSheet(f"color: {THEME['primary']}; font-size: 11px; font-weight: bold;")
        btn_all.clicked.connect(self._brutal_select_all)
        h_layout.addWidget(btn_all)

        btn_rst = QPushButton("Reset Default")
        btn_rst.setFixedHeight(24)
        btn_rst.setCursor(Qt.PointingHandCursor)
        btn_rst.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        btn_rst.clicked.connect(self._brutal_reset_default)
        h_layout.addWidget(btn_rst)

        layout.addWidget(hdr)

        self.scroll_brutal = QScrollArea()
        self.scroll_brutal.setWidgetResizable(True)
        self.scroll_brutal.setFrameShape(QFrame.NoFrame)
        self.container_brutal = QWidget()
        self.layout_brutal_items = QVBoxLayout(self.container_brutal)
        self.layout_brutal_items.setContentsMargins(0, 0, 4, 0)
        self.layout_brutal_items.setSpacing(4)
        self.scroll_brutal.setWidget(self.container_brutal)
        layout.addWidget(self.scroll_brutal, 1)

    def _build_custom_view(self):
        layout = QVBoxLayout(self.stack_custom)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        act_bar = QWidget()
        a_layout = QHBoxLayout(act_bar)
        a_layout.setContentsMargins(0, 0, 0, 0)
        a_layout.setSpacing(4)

        sort_btns = [
            ("A-Z", self.app.on_sort_custom_categories_az),
            ("Terbanyak", self.app.on_sort_custom_categories_count),
            ("Terpanjang", lambda: self.app.on_sort_custom_categories_length(reverse=True)),
            ("Tersedikit", lambda: self.app.on_sort_custom_categories_length(reverse=False))
        ]
        for name, cmd in sort_btns:
            b = QPushButton(name)
            b.setFixedHeight(24)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"font-size: 10px; padding: 2px 6px; background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 4px;")
            b.clicked.connect(cmd)
            a_layout.addWidget(b)

        a_layout.addStretch(1)

        btn_add = QPushButton("+ Tag Baru")
        btn_add.setFixedHeight(24)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"background-color: {THEME['primary']}; color: {THEME['text_dark']}; font-weight: bold; font-size: 11px; border: none; border-radius: 4px; padding: 2px 10px;")
        btn_add.clicked.connect(self.app.open_add_tag_dialog)
        a_layout.addWidget(btn_add)

        layout.addWidget(act_bar)

        self.scroll_custom = QScrollArea()
        self.scroll_custom.setWidgetResizable(True)
        self.scroll_custom.setFrameShape(QFrame.NoFrame)
        self.container_custom = QWidget()
        self.layout_custom_items = QVBoxLayout(self.container_custom)
        self.layout_custom_items.setContentsMargins(0, 0, 4, 0)
        self.layout_custom_items.setSpacing(4)
        self.scroll_custom.setWidget(self.container_custom)
        layout.addWidget(self.scroll_custom, 1)

    def refresh_custom_list(self):
        # In-place clean and populate
        while self.layout_custom_items.count():
            item = self.layout_custom_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cats = self.app.config.get("custom_trap_endings", [])
        self.sub_strip.update_tab_label("custom", f"KELOLA SEMUA TAG ({len(cats)})")

        self.custom_row_widgets = []
        for idx, cat in enumerate(cats):
            sfx = cat.get("suffix", "").upper()
            is_enabled = cat.get("enabled", True)

            row = QFrame()
            row.setFixedHeight(34)
            bg = THEME["bg_card"] if is_enabled else THEME["bg_root"]
            bd = THEME["border_focus"] if is_enabled else THEME["border"]
            row.setStyleSheet(f"background-color: {bg}; border: 1px solid {bd}; border-radius: 5px;")

            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(6, 0, 8, 0)
            r_layout.setSpacing(6)

            btn_up = QPushButton("▲")
            btn_up.setFixedSize(18, 20)
            btn_up.setCursor(Qt.PointingHandCursor)
            btn_up.setStyleSheet("border: none; font-size: 9px; color: #8fa892;")
            btn_up.clicked.connect(lambda ch=False, i=idx: self.app.on_move_tag(i, -1))
            r_layout.addWidget(btn_up)

            btn_down = QPushButton("▼")
            btn_down.setFixedSize(18, 20)
            btn_down.setCursor(Qt.PointingHandCursor)
            btn_down.setStyleSheet("border: none; font-size: 9px; color: #8fa892;")
            btn_down.clicked.connect(lambda ch=False, i=idx: self.app.on_move_tag(i, 1))
            r_layout.addWidget(btn_down)

            badge = QLabel(sfx)
            badge.setFixedHeight(18)
            badge.setStyleSheet(f"background-color: {cat.get('color', THEME['primary'])}; color: {THEME['text_dark']}; font-weight: bold; font-size: 10px; padding: 1px 6px; border-radius: 3px;")
            r_layout.addWidget(badge)

            lbl_name = QLabel(cat.get("name", sfx))
            lbl_name.setStyleSheet("font-size: 12px; font-weight: bold;")
            r_layout.addWidget(lbl_name, 1)

            btn_edit = QPushButton()
            btn_edit.setFixedSize(22, 22)
            btn_edit.setCursor(Qt.PointingHandCursor)
            btn_edit.setIcon(get_qicon("edit", size=13, color=THEME["text_secondary"]))
            btn_edit.setStyleSheet("border: none; background: transparent;")
            btn_edit.clicked.connect(lambda ch=False, c=cat: self.app.open_edit_tag_dialog(c))
            r_layout.addWidget(btn_edit)

            switch_txt = "ON" if is_enabled else "OFF"
            switch_fg = THEME["primary"] if is_enabled else THEME["text_muted"]
            btn_sw = QPushButton(switch_txt)
            btn_sw.setFixedSize(36, 22)
            btn_sw.setCursor(Qt.PointingHandCursor)
            btn_sw.setStyleSheet(f"background-color: {THEME['bg_hover']}; color: {switch_fg}; font-weight: bold; font-size: 10px; border-radius: 3px;")
            btn_sw.clicked.connect(lambda ch=False, i=idx: self.app.on_toggle_tag(i))
            r_layout.addWidget(btn_sw)

            self.layout_custom_items.addWidget(row)
            self.custom_row_widgets.append(row)

        self.layout_custom_items.addStretch(1)

    def refresh_brutal_list(self):
        while self.layout_brutal_items.count():
            item = self.layout_brutal_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        brutal_tags = set(self.app.config.get("brutal_mode_tags", ["AMSI", "KSO", "RHU", "TL", "BD"]))
        cats = self.app.config.get("custom_trap_endings", [])

        for cat in cats:
            sfx = cat.get("suffix", "").upper()
            is_active = (sfx in brutal_tags)

            row = QFrame()
            row.setFixedHeight(34)
            row.setCursor(Qt.PointingHandCursor)
            bg = THEME["danger_bg"] if is_active else THEME["bg_card"]
            bd = THEME["danger"] if is_active else THEME["border"]
            row.setStyleSheet(f"background-color: {bg}; border: 1px solid {bd}; border-radius: 5px;")

            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(10, 0, 10, 0)
            r_layout.setSpacing(8)

            chk_txt = "☑" if is_active else "☐"
            chk_fg = THEME["danger"] if is_active else THEME["text_muted"]
            lbl_chk = QLabel(chk_txt)
            lbl_chk.setStyleSheet(f"color: {chk_fg}; font-size: 14px; font-weight: bold;")
            r_layout.addWidget(lbl_chk)

            badge = QLabel(sfx)
            badge.setFixedHeight(18)
            badge.setStyleSheet(f"background-color: {cat.get('color', THEME['primary'])}; color: {THEME['text_dark']}; font-weight: bold; font-size: 10px; padding: 1px 6px; border-radius: 3px;")
            r_layout.addWidget(badge)

            lbl_name = QLabel(cat.get("name", sfx))
            lbl_name.setStyleSheet(f"font-size: 12px; font-weight: {'bold' if is_active else 'normal'}; color: {THEME['text_primary'] if is_active else THEME['text_secondary']};")
            r_layout.addWidget(lbl_name, 1)

            st_txt = "BRUTAL" if is_active else "NONAKTIF"
            st_fg = THEME["danger"] if is_active else THEME["text_muted"]
            lbl_st = QLabel(st_txt)
            lbl_st.setStyleSheet(f"color: {st_fg}; font-weight: bold; font-size: 10px;")
            r_layout.addWidget(lbl_st)

            row.mousePressEvent = lambda e, s=sfx: self.app.toggle_brutal_tag(s)
            self.layout_brutal_items.addWidget(row)

        self.layout_brutal_items.addStretch(1)

    def _brutal_select_all(self):
        cats = self.app.config.get("custom_trap_endings", [])
        self.app.config["brutal_mode_tags"] = [c.get("suffix", "").upper() for c in cats]
        self.app.save_config_debounced()
        self.refresh_brutal_list()

    def _brutal_reset_default(self):
        self.app.config["brutal_mode_tags"] = ["AMSI", "KSO", "RHU", "TL", "BD"]
        self.app.save_config_debounced()
        self.refresh_brutal_list()


# --- Tab 3: KAMUS Tab View ---
class QtDictionaryTabView(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.sub_strip = QtSubTabStrip([
            ("whitelist", "WHITELIST", "star_filled"),
            ("blocklist", "BLOCKLIST", "cross"),
            ("explorer", "EKSPLORER", "search")
        ])
        self.sub_strip.sub_tab_changed.connect(self._on_sub_tab_changed)

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

    def _on_sub_tab_changed(self, sub_id):
        self.stack_wl.hide()
        self.stack_bl.hide()
        self.stack_exp.hide()
        if sub_id == "whitelist":
            self.stack_wl.show()
            self.refresh_whitelist()
        elif sub_id == "blocklist":
            self.stack_bl.show()
            self.refresh_blocklist()
        else:
            self.stack_exp.show()

    def _build_whitelist_view(self):
        layout = QVBoxLayout(self.stack_wl)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 5px;")
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(8, 6, 8, 6)
        self.lbl_wl_count = QLabel("Daftar Kata Whitelist (0)")
        self.lbl_wl_count.setStyleSheet(f"color: {THEME['warning']}; font-weight: bold; font-size: 11px;")
        h_layout.addWidget(self.lbl_wl_count)
        h_layout.addStretch(1)

        self.edit_wl_input = QLineEdit()
        self.edit_wl_input.setPlaceholderText("+ Tambah kata...")
        self.edit_wl_input.setFixedWidth(130)
        self.edit_wl_input.returnPressed.connect(self._add_wl_word)
        h_layout.addWidget(self.edit_wl_input)

        layout.addWidget(hdr)

        self.scroll_wl = QScrollArea()
        self.scroll_wl.setWidgetResizable(True)
        self.scroll_wl.setFrameShape(QFrame.NoFrame)
        self.container_wl = QWidget()
        self.layout_wl_items = QVBoxLayout(self.container_wl)
        self.layout_wl_items.setContentsMargins(0, 0, 4, 0)
        self.layout_wl_items.setSpacing(4)
        self.scroll_wl.setWidget(self.container_wl)
        layout.addWidget(self.scroll_wl, 1)

    def _build_blocklist_view(self):
        layout = QVBoxLayout(self.stack_bl)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        hdr = QFrame()
        hdr.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 5px;")
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(8, 6, 8, 6)
        self.lbl_bl_count = QLabel("Daftar Kata Diblokir (0)")
        self.lbl_bl_count.setStyleSheet(f"color: {THEME['danger']}; font-weight: bold; font-size: 11px;")
        h_layout.addWidget(self.lbl_bl_count)
        h_layout.addStretch(1)

        self.edit_bl_input = QLineEdit()
        self.edit_bl_input.setPlaceholderText("+ Blokir kata...")
        self.edit_bl_input.setFixedWidth(130)
        self.edit_bl_input.returnPressed.connect(self._add_bl_word)
        h_layout.addWidget(self.edit_bl_input)

        layout.addWidget(hdr)

        self.scroll_bl = QScrollArea()
        self.scroll_bl.setWidgetResizable(True)
        self.scroll_bl.setFrameShape(QFrame.NoFrame)
        self.container_bl = QWidget()
        self.layout_bl_items = QVBoxLayout(self.container_bl)
        self.layout_bl_items.setContentsMargins(0, 0, 4, 0)
        self.layout_bl_items.setSpacing(4)
        self.scroll_bl.setWidget(self.container_bl)
        layout.addWidget(self.scroll_bl, 1)

    def _build_explorer_view(self):
        layout = QVBoxLayout(self.stack_exp)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 1. Baris Tambah Kata Baru (Dipisah dari Search)
        add_box = QFrame()
        add_box.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 5px;")
        ab_layout = QHBoxLayout(add_box)
        ab_layout.setContentsMargins(8, 6, 8, 6)

        lbl_add = QLabel("+ Kata Baru:")
        lbl_add.setStyleSheet("font-weight: bold; font-size: 11px;")
        ab_layout.addWidget(lbl_add)

        self.edit_new_word = QLineEdit()
        self.edit_new_word.setPlaceholderText("Ketik kata KBBI baru...")
        self.edit_new_word.returnPressed.connect(self._on_add_dictionary_word)
        ab_layout.addWidget(self.edit_new_word, 1)

        btn_add = QPushButton("Tambah")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setFixedHeight(26)
        btn_add.setStyleSheet(f"background-color: {THEME['primary']}; color: {THEME['text_dark']}; font-weight: bold; font-size: 11px; border: none; border-radius: 4px; padding: 2px 10px;")
        btn_add.clicked.connect(self._on_add_dictionary_word)
        ab_layout.addWidget(btn_add)
        layout.addWidget(add_box)

        # 2. Baris Pencarian
        search_box = QFrame()
        search_box.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 5px;")
        s_layout = QHBoxLayout(search_box)
        s_layout.setContentsMargins(8, 6, 8, 6)

        self.edit_exp_search = QLineEdit()
        self.edit_exp_search.setPlaceholderText("Cari kata dalam kamus...")
        self.edit_exp_search.returnPressed.connect(self._search_dictionary)
        s_layout.addWidget(self.edit_exp_search, 1)

        btn_srch = QPushButton("Cari")
        btn_srch.setCursor(Qt.PointingHandCursor)
        btn_srch.setFixedHeight(26)
        btn_srch.setStyleSheet(f"background-color: {THEME['bg_hover']}; color: {THEME['text_primary']}; font-weight: bold; font-size: 11px; border: 1px solid {THEME['border']}; border-radius: 4px; padding: 2px 12px;")
        btn_srch.clicked.connect(self._search_dictionary)
        s_layout.addWidget(btn_srch)
        layout.addWidget(search_box)

        # 3. Hasil Pencarian List
        self.scroll_exp = QScrollArea()
        self.scroll_exp.setWidgetResizable(True)
        self.scroll_exp.setFrameShape(QFrame.NoFrame)
        self.container_exp = QWidget()
        self.layout_exp_items = QVBoxLayout(self.container_exp)
        self.layout_exp_items.setContentsMargins(0, 0, 4, 0)
        self.layout_exp_items.setSpacing(4)
        self.scroll_exp.setWidget(self.container_exp)
        layout.addWidget(self.scroll_exp, 1)

    def refresh_whitelist(self):
        while self.layout_wl_items.count():
            item = self.layout_wl_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        wl_words = sorted(list(self.app.solver.whitelisted_words))
        self.lbl_wl_count.setText(f"Daftar Kata Whitelist ({len(wl_words)})")

        for w in wl_words:
            row = QFrame()
            row.setFixedHeight(32)
            row.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 4px;")
            r_l = QHBoxLayout(row)
            r_l.setContentsMargins(8, 0, 8, 0)

            lbl = QLabel(w.upper())
            lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['text_primary']};")
            r_l.addWidget(lbl, 1)

            btn_del = QPushButton()
            btn_del.setFixedSize(22, 22)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setIcon(get_qicon("trash", size=13, color=THEME["danger"]))
            btn_del.setStyleSheet("border: none; background: transparent;")
            btn_del.clicked.connect(lambda ch=False, word=w: self._remove_wl_word(word))
            r_l.addWidget(btn_del)

            self.layout_wl_items.addWidget(row)

        self.layout_wl_items.addStretch(1)

    def refresh_blocklist(self):
        while self.layout_bl_items.count():
            item = self.layout_bl_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        bl_words = sorted(list(self.app.solver.blacklisted_words))
        self.lbl_bl_count.setText(f"Daftar Kata Diblokir ({len(bl_words)})")

        for w in bl_words:
            row = QFrame()
            row.setFixedHeight(32)
            row.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 4px;")
            r_l = QHBoxLayout(row)
            r_l.setContentsMargins(8, 0, 8, 0)

            lbl = QLabel(w.upper())
            lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['text_primary']};")
            r_l.addWidget(lbl, 1)

            btn_del = QPushButton()
            btn_del.setFixedSize(22, 22)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setIcon(get_qicon("trash", size=13, color=THEME["primary"]))
            btn_del.setToolTip("Pulihkan kata dari blocklist")
            btn_del.setStyleSheet("border: none; background: transparent;")
            btn_del.clicked.connect(lambda ch=False, word=w: self._remove_bl_word(word))
            r_l.addWidget(btn_del)

            self.layout_bl_items.addWidget(row)

        self.layout_bl_items.addStretch(1)

    def _add_wl_word(self):
        word = self.edit_wl_input.text().strip().lower()
        if word:
            self.app.solver.whitelist_word(word)
            self.edit_wl_input.clear()
            self.refresh_whitelist()

    def _remove_wl_word(self, word):
        self.app.solver.unwhitelist_word(word)
        self.refresh_whitelist()

    def _add_bl_word(self):
        word = self.edit_bl_input.text().strip().lower()
        if word:
            self.app.solver.blacklist_word(word)
            self.edit_bl_input.clear()
            self.refresh_blocklist()

    def _remove_bl_word(self, word):
        self.app.solver.unblacklist_word(word)
        self.refresh_blocklist()

    def _on_add_dictionary_word(self):
        word = self.edit_new_word.text().strip().lower()
        if not word:
            return
        success, msg = self.app.solver.add_word(word)
        if success:
            self.app.show_toast(f"Berhasil: {msg}")
            self.edit_new_word.clear()
        else:
            QMessageBox.warning(self, "Peringatan", msg)

    def _search_dictionary(self):
        query = self.edit_exp_search.text().strip().lower()
        while self.layout_exp_items.count():
            item = self.layout_exp_items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not query:
            return

        matches = self.app.solver.search_dictionary(query, limit=40)
        for w in matches:
            row = QFrame()
            row.setFixedHeight(30)
            row.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 4px;")
            r_l = QHBoxLayout(row)
            r_l.setContentsMargins(8, 0, 8, 0)
            lbl = QLabel(w.upper())
            lbl.setStyleSheet(f"font-size: 12px; color: {THEME['text_primary']};")
            r_l.addWidget(lbl, 1)
            self.layout_exp_items.addWidget(row)

        self.layout_exp_items.addStretch(1)


# --- Tab 4: SYSTEM Tab View ---
class QtSystemTabView(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # 1. Scanner Settings Frame
        sc_box = QFrame()
        sc_box.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 6px;")
        sc_layout = QVBoxLayout(sc_box)
        sc_layout.setContentsMargins(12, 10, 12, 10)
        sc_layout.setSpacing(8)

        lbl_sc = QLabel("PENGATURAN SCANNER OCR")
        lbl_sc.setStyleSheet(f"color: {THEME['primary']}; font-weight: bold; font-size: 11px;")
        sc_layout.addWidget(lbl_sc)

        sp_row = QHBoxLayout()
        sp_row.addWidget(QLabel("Kecepatan Scan:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems([
            "40ms (Ultra Instan)",
            "80ms (Cepat / Rekomendasi)",
            "120ms (Standar)",
            "200ms (Santai / Hemat CPU)"
        ])
        self.combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        sp_row.addWidget(self.combo_speed, 1)
        sc_layout.addLayout(sp_row)

        btn_roi = QPushButton("📐 Atur Area Layar (Region Selector)")
        btn_roi.setCursor(Qt.PointingHandCursor)
        btn_roi.setStyleSheet(f"background-color: {THEME['bg_hover']}; color: {THEME['text_primary']}; border: 1px solid {THEME['border']}; border-radius: 4px; padding: 6px;")
        btn_roi.clicked.connect(self.app.open_region_selector)
        sc_layout.addWidget(btn_roi)

        layout.addWidget(sc_box)

        # 2. Git & Version Info Frame
        git_box = QFrame()
        git_box.setStyleSheet(f"background-color: {THEME['bg_card']}; border: 1px solid {THEME['border']}; border-radius: 6px;")
        git_layout = QVBoxLayout(git_box)
        git_layout.setContentsMargins(12, 10, 12, 10)
        git_layout.setSpacing(8)

        lbl_git = QLabel("INFORMASI VERSI & PEMBARUAN")
        lbl_git.setStyleSheet(f"color: {THEME['accent_cyan']}; font-weight: bold; font-size: 11px;")
        git_layout.addWidget(lbl_git)

        br_row = QHBoxLayout()
        br_row.addWidget(QLabel("Branch:"))
        self.lbl_branch = QLabel(self.app.updater.get_current_branch())
        self.lbl_branch.setStyleSheet(f"color: {THEME['primary']}; font-weight: bold;")
        br_row.addWidget(self.lbl_branch)
        br_row.addStretch(1)
        git_layout.addLayout(br_row)

        curr_commit = self.app.updater.get_current_commit()
        self.commit_hash = curr_commit.get("hash", "Unknown")
        c_row = QHBoxLayout()
        c_row.addWidget(QLabel("Commit:"))
        self.lbl_commit = QLabel(f"#{self.commit_hash}")
        self.lbl_commit.setCursor(Qt.PointingHandCursor)
        self.lbl_commit.setStyleSheet(f"color: {THEME['primary']}; text-decoration: underline; font-weight: bold;")
        self.lbl_commit.mousePressEvent = lambda e: self._open_commit_link()
        c_row.addWidget(self.lbl_commit)
        c_row.addStretch(1)
        git_layout.addLayout(c_row)

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
        """)
        self.btn_check_update.clicked.connect(self.app.check_updates)
        git_layout.addWidget(self.btn_check_update)

        layout.addWidget(git_box)
        layout.addStretch(1)

    def _open_commit_link(self):
        url = f"https://github.com/anv-group/sambung-kata-overlay/commit/{self.commit_hash}"
        webbrowser.open(url)

    def _on_speed_changed(self, idx):
        speeds = [0.04, 0.08, 0.12, 0.20]
        if 0 <= idx < len(speeds):
            self.app.config["scan_interval_sec"] = speeds[idx]
            self.app.save_config_debounced()
            self.app.show_toast(f"Kecepatan scan: {speeds[idx]*1000:.0f}ms")
