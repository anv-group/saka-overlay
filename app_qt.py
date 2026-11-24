import sys
import os
import time
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QDialog, QLineEdit,
    QColorDialog, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QRect
from PySide6.QtGui import QIcon, QPixmap, QCursor, QKeySequence, QShortcut
from ctypes import wintypes

from qt_theme import THEME, GLOBAL_QSS, get_qicon
from qt_components import QtTopTabStrip, QtMiniTickerBar, QtCustomTitleBar
from tab_views_qt import QtLiveTabView, QtTagsTabView, QtDictionaryTabView, QtSystemTabView, QtKoreksiDialog

from config import load_config, save_config, DEFAULT_HOTKEYS
from solver import SambungKataSolver
from ocr_engine import OCREngine
from updater import GitUpdater


class ScanWorker(QThread):
    """
    Background Thread untuk Vision & OCR Engine murni Qt QThread.
    Memancarkan hasil scan ke GUI thread secara aman via Signal.
    """
    result_ready = Signal(dict)

    def __init__(self, ocr_engine, get_interval_func, parent=None):
        super().__init__(parent)
        self.ocr = ocr_engine
        self.get_interval_func = get_interval_func
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            interval = self.get_interval_func()
            try:
                data = self.ocr.scan_once()
                self.result_ready.emit(data)
            except Exception as e:
                pass
            time.sleep(interval)

    def stop(self):
        self.running = False
        self.wait(1000)


class SambungKataQtApp(QMainWindow):
    """
    Aplikasi Utama SAKA Overlay berbasis PySide6 (Tactical Cyber Bamboo Theme).
    """
    hotkey_triggered = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAKA Overlay")
        self.setMinimumSize(380, 500)

        # 1. Load Backend Engines & Configuration
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config = load_config()
        self.always_on_top = self.config.get("always_on_top", True)

        flags = Qt.FramelessWindowHint
        if self.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        # Pasang Icon Window
        ico_path = os.path.join(base_dir, "assets", "logo.ico")
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))

        if "saved_default_tags" not in self.config:
            cats = self.config.get("custom_trap_endings", [])
            self.config["saved_default_tags"] = [c.get("suffix", "").upper() for c in cats if c.get("enabled", True)]
        self.solver = SambungKataSolver(
            dictionary_path=os.path.join(base_dir, "kamus_lengkap.txt"),
            blacklist_path=os.path.join(base_dir, "blacklist.txt"),
            whitelist_path=os.path.join(base_dir, "whitelist.txt"),
            kbbi_path=os.path.join(base_dir, "kamus_kbbi.txt"),
            contek_path=os.path.join(base_dir, "kamus_contek.txt"),
            use_kbbi=self.config.get("use_kbbi", False),
            use_contek=self.config.get("use_contek", True)
        )
        self.solver.set_custom_endings(self.config.get("custom_trap_endings", []))

        self.ocr = OCREngine(config=self.config)
        self.updater = GitUpdater(repo_dir=base_dir)

        # State Variables
        self.last_detected_word = ""
        self.last_detected_conf = 100
        self.is_scanning = False
        self.manual_override_active = False
        self._save_timer = None
        self._dirty_live = False

        # 2. Setup Central Widget & Layout
        central = QWidget()
        central.setMouseTracking(True)
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Custom Frameless Titlebar dengan Logo Horizontal
        self.dev_mode = self.config.get("dev_mode", False)
        logo_path = os.path.join(base_dir, "assets", "logo_horizontal.png")
        self.title_bar = QtCustomTitleBar(self, logo_path, on_restart_func=self.restart_app)
        self.title_bar.set_dev_mode(self.dev_mode)
        self.title_bar.set_pinned(self.always_on_top)
        self.main_layout.addWidget(self.title_bar)

        # Shortcut Ctrl+Shift+D untuk Mode Dev
        self.sc_dev = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        self.sc_dev.activated.connect(self.toggle_dev_mode)

        # Top Navigation Strip
        self.top_strip = QtTopTabStrip()
        self.top_strip.tab_changed.connect(self._on_tab_changed)
        self.main_layout.addWidget(self.top_strip)

        # Mini Ticker Bar
        self.mini_ticker = QtMiniTickerBar()
        self.mini_ticker.clicked.connect(lambda: self.top_strip.select_tab("live"))
        self.mini_ticker.update_ticker("", None, is_manual=False)
        self.mini_ticker.hide()
        self.main_layout.addWidget(self.mini_ticker)

        # Stacked Tabs Container
        self.stack = QStackedWidget()
        self.tab_live = QtLiveTabView(self)
        self.tab_tags = QtTagsTabView(self)
        self.tab_kamus = QtDictionaryTabView(self)
        self.tab_system = QtSystemTabView(self)

        self.stack.addWidget(self.tab_live)
        self.stack.addWidget(self.tab_tags)
        self.stack.addWidget(self.tab_kamus)
        self.stack.addWidget(self.tab_system)

        self.main_layout.addWidget(self.stack, 1)

        # Toast Message Bar (Floating Overlay HUD - Zero layout shift!)
        self.toast_frame = QFrame(self)
        self.toast_frame.setFixedHeight(30)
        self.toast_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(20, 28, 21, 0.95);
                border: 1px solid {THEME['primary']};
                border-radius: 15px;
            }}
        """)
        tf_layout = QHBoxLayout(self.toast_frame)
        tf_layout.setContentsMargins(14, 0, 14, 0)
        self.lbl_toast = QLabel("")
        self.lbl_toast.setAlignment(Qt.AlignCenter)
        self.lbl_toast.setStyleSheet(f"color: {THEME['primary']}; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        tf_layout.addWidget(self.lbl_toast)
        self.toast_frame.hide()

        # 3. Connect Signals
        self.tab_live.start_stop_clicked.connect(self.toggle_scan)
        self.tab_live.mode_changed.connect(self.set_game_mode)
        self.tab_live.search_text_changed.connect(self.on_manual_search)
        self.tab_live.sort_mode_toggled.connect(self.toggle_tier0_sort)
        self.tab_live.flag_clicked.connect(self._on_f2_hotkey)
        self.tab_live.add_word_clicked.connect(lambda: self.open_quick_add_dialog("kamus"))
        self.tab_live.add_whitelist_clicked.connect(lambda: self.open_quick_add_dialog("whitelist"))
        self.tab_live.add_blocklist_clicked.connect(lambda: self.open_quick_add_dialog("blocklist"))

        # Initial populate
        self.tab_live.refresh_quick_tags(self.config.get("custom_trap_endings", []))
        self.tab_live.mode_pills.set_mode(self.config.get("game_mode", "default"))

        # Setup Scan Worker
        self.scan_worker = ScanWorker(self.ocr, lambda: self.config.get("scan_interval_sec", 0.08))
        self.scan_worker.result_ready.connect(self._on_scan_result)

        # Global Hotkeys (Customizables) - marshal ke Qt main thread via Signal(str)
        self._kb_hooks = []
        self._qt_shortcuts = []
        self.hotkey_triggered.connect(self._on_hotkey_action)
        self.register_hotkeys()

        # Posisikan window di sisi kanan layar (Default Right-Docked) & Muat Geometri Tersimpan
        self._init_window_geometry()

    # --- Scanning & Vision Control ---
    def update_ticker_visibility(self):
        if self.top_strip.active_tab == "live":
            self.mini_ticker.hide()
        else:
            # Tampilkan hanya jika scanner sedang MULAI atau saat MANUAL OVERRIDE aktif
            if self.is_scanning or self.manual_override_active:
                self.mini_ticker.show()
            else:
                self.mini_ticker.hide()

    def toggle_scan(self):
        if not self.is_scanning:
            self.is_scanning = True
            self.tab_live.set_scanning_state(True)
            self.scan_worker.start()
            self.update_ticker_visibility()
            self.show_toast("Live OCR Scanner dimulai")
        else:
            self.is_scanning = False
            self.tab_live.set_scanning_state(False)
            self.scan_worker.stop()
            self.update_ticker_visibility()
            self.show_toast("Live OCR Scanner dihentikan")

    def _on_scan_result(self, res_data: dict):
        text = res_data.get("text", "").strip()
        conf = res_data.get("confidence", 1.0)
        conf_pct = int(conf * 100)
        self.last_detected_word = text
        self.last_detected_conf = conf_pct

        # Update tampilan OCR di HUD Live
        self.tab_live.update_ocr_display(text, conf_pct)

        # Cek apakah pemain sedang melakukan manual search
        manual_q = self.tab_live.edit_search.text().strip()
        if manual_q:
            # Manual query selalu OVERPOWER OCR! Jangan timpa hasil rekomendasi.
            return

        if text:
            self.update_results(text, conf_pct)
        else:
            self.update_results("", conf_pct)

    def on_manual_search(self, query: str):
        q = "".join([c for c in query.upper() if c.isalpha()])
        if q:
            # Input manual aktif: Overpower OCR seketika!
            self.manual_override_active = True
            self.tab_live.set_manual_override_active(True)
            self.update_results(q, 100)
            self.update_ticker_visibility()
        else:
            self.manual_override_active = False
            self.tab_live.set_manual_override_active(False)
            if self.last_detected_word:
                self.update_results(self.last_detected_word, self.last_detected_conf)
            else:
                self.tab_live.update_results("", [], 100)
                self.mini_ticker.update_ticker("", None, is_manual=False)
            self.update_ticker_visibility()

    def update_results(self, prefix: str, conf_pct: int = 100):
        if not prefix:
            self.tab_live.update_results("", [], 100)
            self.mini_ticker.update_ticker("", None, is_manual=self.manual_override_active)
            return

        cur_mode = self.config.get("game_mode", "default")
        is_santai = (cur_mode == "santai")
        is_brutal = (cur_mode == "brutal")
        sort_m = self.config.get("tier0_sort_mode", "default")

        words = self.solver.cari_jawaban(
            prefix, limit=40,
            mode_santai=is_santai,
            mode_brutal=is_brutal,
            sort_mode=sort_m
        )

        top_item = words[0] if words else None
        two_tone = self.config.get("two_tone_text", True)
        self.mini_ticker.update_ticker(prefix, top_item, is_manual=self.manual_override_active, two_tone=two_tone)

        if self.top_strip.active_tab == "live":
            self.tab_live.update_results(prefix, words, conf_pct)
        else:
            self._dirty_live = True

    # --- Navigation & Tabs ---
    def _on_tab_changed(self, tab_id: str):
        tab_map = {"live": 0, "tags": 1, "kamus": 2, "system": 3}
        idx = tab_map.get(tab_id, 0)
        self.stack.setCurrentIndex(idx)

        self.update_ticker_visibility()

        if tab_id == "live":
            if self._dirty_live:
                if self.last_detected_word:
                    self.update_results(self.last_detected_word, 100)
                self._dirty_live = False

        if tab_id == "kamus":
            QTimer.singleShot(60, self.tab_kamus.focus_active_search)

    def open_tags_tab(self):
        self.top_strip.select_tab("tags")

    # --- Tag & Solver Management ---
    def on_move_tag(self, idx: int, direction: int):
        cats = self.config.get("custom_trap_endings", [])
        new_idx = idx + direction
        if 0 <= idx < len(cats) and 0 <= new_idx < len(cats):
            cats[idx], cats[new_idx] = cats[new_idx], cats[idx]
            self.config["custom_trap_endings"] = cats
            self.solver.set_custom_endings(cats)
            self.save_config_debounced()
            self.tab_tags.refresh_custom_list()
            self.tab_live.refresh_quick_tags(cats)
            if self.last_detected_word:
                self.update_results(self.last_detected_word)
            sfx = cats[new_idx].get("suffix", "")
            self.show_toast(f"Tag '{sfx}' dipindahkan ke #{new_idx + 1}")

    def on_toggle_tag(self, idx: int):
        cats = self.config.get("custom_trap_endings", [])
        if 0 <= idx < len(cats):
            cat = cats[idx]
            new_val = not cat.get("enabled", True)
            sfx = cat.get("suffix", "").upper()

            # Mode Santai check
            if self.config.get("game_mode") == "santai" and new_val and any(c in sfx.lower() for c in ("x", "q", "f")):
                self.show_toast(f"Tag [{sfx}] dilarang di Mode Santai (ada X/Q/F)!")
                return

            cat["enabled"] = new_val
            self.config["custom_trap_endings"] = cats
            self.solver.set_custom_endings(cats)

            # Sync active profile
            cur_m = self.config.get("game_mode", "default")
            if cur_m == "default":
                self.config["saved_default_tags"] = [c.get("suffix", "").upper() for c in cats if c.get("enabled", True)]
            elif cur_m == "brutal":
                self.config["brutal_mode_tags"] = [c.get("suffix", "").upper() for c in cats if c.get("enabled", True)]

            self.save_config_debounced()

            # In-place row update (Preserve exact scroll position without jumps!)
            if idx < self.tab_tags.layout_custom_items.count():
                row_w = self.tab_tags.layout_custom_items.itemAt(idx).widget()
                if row_w and hasattr(row_w, "set_enabled_state"):
                    row_w.set_enabled_state(new_val)
                else:
                    self.tab_tags.refresh_custom_list()
            else:
                self.tab_tags.refresh_custom_list()

            self.tab_live.refresh_quick_tags(cats)
            if self.last_detected_word:
                self.update_results(self.last_detected_word)
            st = "diaktifkan" if new_val else "dinonaktifkan"
            self.show_toast(f"Tag [{sfx}] {st}")

    def toggle_quick_tag(self, suffix: str):
        cats = self.config.get("custom_trap_endings", [])
        for i, c in enumerate(cats):
            if c.get("suffix", "").upper() == suffix.upper():
                self.on_toggle_tag(i)
                break

    def toggle_brutal_tag(self, suffix: str):
        b_tags = set(self.config.get("brutal_mode_tags", []))
        is_active = (suffix in b_tags)
        if is_active:
            b_tags.remove(suffix)
        else:
            b_tags.add(suffix)
        self.config["brutal_mode_tags"] = list(b_tags)
        self.save_config_debounced()

        if self.config.get("game_mode") == "brutal":
            cats = self.config.get("custom_trap_endings", [])
            for c in cats:
                c["enabled"] = (c.get("suffix", "").upper() in b_tags)
            self.config["custom_trap_endings"] = cats
            self.solver.set_custom_endings(cats)
            self.tab_live.refresh_quick_tags(cats)
            if self.last_detected_word:
                self.update_results(self.last_detected_word)

        # In-place card update (Zero scroll jump!)
        cats = self.config.get("custom_trap_endings", [])
        for i in range(self.tab_tags.layout_brutal_items.count()):
            card_w = self.tab_tags.layout_brutal_items.itemAt(i).widget()
            if card_w and getattr(card_w, "sfx", "") == suffix:
                card_w.set_active_state(not is_active)
                break
        active_count = sum(1 for c in cats if c.get("suffix", "").upper() in b_tags)
        self.tab_tags.lbl_brutal_count.setText(f"({active_count} / {len(cats)} Aktif)")

    def set_game_mode(self, mode: str):
        cur_mode = self.config.get("game_mode", "default")
        if mode == cur_mode:
            return

        cats = self.config.get("custom_trap_endings", [])

        # 1. Simpan snapshot tag aktif dari mode saat ini SEBELUM berpindah
        if cur_mode == "default":
            self.config["saved_default_tags"] = [c.get("suffix", "").upper() for c in cats if c.get("enabled", True)]
        elif cur_mode == "brutal":
            self.config["brutal_mode_tags"] = [c.get("suffix", "").upper() for c in cats if c.get("enabled", True)]

        # 2. Terapkan konfigurasi tag untuk mode baru
        if mode == "brutal":
            self.config["santai_auto_disabled_tags"] = []
            b_tags = set(self.config.get("brutal_mode_tags", ["AMSI", "KSO", "RHU", "TL", "BD"]))
            for c in cats:
                c["enabled"] = (c.get("suffix", "").upper() in b_tags)

        elif mode == "santai":
            # Jika sebelumnya dari brutal, pulihkan tag default terlebih dahulu
            if cur_mode == "brutal":
                saved_def = set(self.config.get("saved_default_tags", []))
                if saved_def:
                    for c in cats:
                        c["enabled"] = (c.get("suffix", "").upper() in saved_def)

            disabled = []
            for c in cats:
                sfx = c.get("suffix", "").upper()
                if any(ch in sfx.lower() for ch in ("x", "q", "f")):
                    if c.get("enabled", True):
                        c["enabled"] = False
                        disabled.append(sfx)
            self.config["santai_auto_disabled_tags"] = disabled

        else:  # mode == "default"
            if cur_mode == "santai":
                auto_disabled = set(self.config.get("santai_auto_disabled_tags", []))
                for c in cats:
                    if c.get("suffix", "").upper() in auto_disabled:
                        c["enabled"] = True
                self.config["santai_auto_disabled_tags"] = []
            elif cur_mode == "brutal":
                saved_def = set(self.config.get("saved_default_tags", []))
                if saved_def:
                    for c in cats:
                        c["enabled"] = (c.get("suffix", "").upper() in saved_def)

        self.config["game_mode"] = mode
        self.config["custom_trap_endings"] = cats
        self.solver.set_custom_endings(cats)
        self.save_config_debounced()

        self.tab_live.refresh_quick_tags(cats)
        self.tab_live.mode_pills.set_mode(mode)
        self.tab_tags.refresh_custom_list()
        self.tab_tags.refresh_brutal_list()

        if self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast(f"Mode permainan diubah ke {mode.upper()}")

    def cycle_game_mode(self):
        order = ["default", "santai", "brutal"]
        cur = self.config.get("game_mode", "default")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "default"
        self.set_game_mode(nxt)

    def toggle_tier0_sort(self):
        curr = self.config.get("tier0_sort_mode", "default")
        nxt = "tag_order" if curr == "default" else "default"
        self.config["tier0_sort_mode"] = nxt
        self.save_config_debounced()
        self.tab_live.update_sort_button(nxt)
        if self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast(f"Metode sortir: {nxt.upper()}")

    def set_two_tone_text(self, enabled: bool):
        self.config["two_tone_text"] = enabled
        self.save_config_debounced()
        self.tab_live.set_two_tone_enabled(enabled)
        # Refresh tampilan
        if self.last_detected_word:
            self.update_results(self.last_detected_word, self.last_detected_conf)
        st = "diaktifkan" if enabled else "dinonaktifkan"
        self.show_toast(f"Two-Tone Text {st}")

    def _exec_dialog_with_focus(self, dlg: QDialog, focus_widget):
        """Menjalankan dialog modal dengan auto-focus ke input dan mengembalikan fokus ke window sebelumnya (misal Roblox)."""
        prev_hwnd = 0
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                fg = user32.GetForegroundWindow()
                if fg and fg != int(self.winId()):
                    prev_hwnd = fg
            except Exception:
                prev_hwnd = 0

        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)

        def _force_focus_dialog():
            if sys.platform == "win32":
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    kernel32 = ctypes.windll.kernel32
                    fg = user32.GetForegroundWindow()
                    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
                    cur_tid = kernel32.GetCurrentThreadId()
                    attached = False
                    if fg_tid and fg_tid != cur_tid:
                        attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
                    dlg.raise_()
                    dlg.activateWindow()
                    user32.SetForegroundWindow(int(dlg.winId()))
                    if attached:
                        user32.AttachThreadInput(cur_tid, fg_tid, False)
                except Exception:
                    pass
            dlg.raise_()
            dlg.activateWindow()
            if focus_widget is not None:
                focus_widget.setFocus()

        QTimer.singleShot(20, _force_focus_dialog)
        dlg.exec()

        if prev_hwnd and sys.platform == "win32":
            def _restore_prev_window():
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    kernel32 = ctypes.windll.kernel32
                    if not user32.IsWindow(prev_hwnd):
                        return
                    fg = user32.GetForegroundWindow()
                    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
                    target_tid = user32.GetWindowThreadProcessId(prev_hwnd, None)
                    cur_tid = kernel32.GetCurrentThreadId()
                    att_fg = bool(fg_tid and fg_tid != cur_tid and user32.AttachThreadInput(cur_tid, fg_tid, True))
                    att_tgt = bool(target_tid and target_tid != cur_tid and user32.AttachThreadInput(cur_tid, target_tid, True))
                    user32.SetForegroundWindow(prev_hwnd)
                    if att_tgt:
                        user32.AttachThreadInput(cur_tid, target_tid, False)
                    if att_fg:
                        user32.AttachThreadInput(cur_tid, fg_tid, False)
                except Exception:
                    pass
            QTimer.singleShot(30, _restore_prev_window)

    def open_quick_add_dialog(self, mode: str = "whitelist"):
        if getattr(self, "_active_quick_add", None) is not None:
            try:
                self._active_quick_add.raise_()
                self._active_quick_add.activateWindow()
                self._active_quick_add.edit_word.setFocus()
                return
            except Exception:
                self._active_quick_add = None

        from tab_views_qt import QtQuickAddDialog
        dlg = QtQuickAddDialog(self, mode=mode, parent=self)
        self._active_quick_add = dlg
        self._exec_dialog_with_focus(dlg, dlg.edit_word)
        self._active_quick_add = None

    def on_add_word_quick(self, word: str):
        if not word:
            return False, "Kata kosong"
        ok, msg = self.solver.add_word(word)
        if ok:
            self.show_toast(f"'{word.upper()}' berhasil ditambahkan ke Kamus! ")
            if self.last_detected_word:
                self.update_results(self.last_detected_word)
            self.tab_kamus.refresh_whitelist()
        else:
            self.show_toast(f"Gagal: {msg}")
        return ok, msg

    # --- Whitelist & Blocklist Action Handlers ---
    def on_toggle_whitelist(self, word: str):
        if not word:
            return
        w = word.strip().lower()
        if self.solver.is_whitelisted(w):
            self.solver.unwhitelist_word(w)
            self.show_toast(f"'{word.upper()}' dihapus dari Whitelist")
        else:
            self.solver.whitelist_word(w)
            self.show_toast(f"'{word.upper()}' ditambahkan ke Whitelist")
        if self.last_detected_word:
            self.update_results(self.last_detected_word)

    def on_block_word(self, word: str):
        if not word:
            return
        w = word.strip().lower()
        self.solver.blacklist_word(w)
        self.show_toast(f"'{word.upper()}' diblokir ke Blocklist")
        if self.last_detected_word:
            self.update_results(self.last_detected_word)

    def on_copy_word(self, word: str):
        if not word:
            return
        QApplication.clipboard().setText(word.upper())
        self.show_toast(f"Disalin ke clipboard: {word.upper()}")

    # --- Dialogs ---
    def open_add_tag_dialog(self):
        self.open_edit_tag_dialog(None)

    def set_brutal_tags_batch(self, b_tags: list):
        b_set = set(b_tags)
        self.config["brutal_mode_tags"] = b_tags
        self.save_config_debounced()

        if self.config.get("game_mode") == "brutal":
            cats = self.config.get("custom_trap_endings", [])
            for c in cats:
                c["enabled"] = (c.get("suffix", "").upper() in b_set)
            self.config["custom_trap_endings"] = cats
            self.solver.set_custom_endings(cats)
            self.tab_live.refresh_quick_tags(cats)
            if self.last_detected_word:
                self.update_results(self.last_detected_word)

        # In-place batch update
        cats = self.config.get("custom_trap_endings", [])
        for i in range(self.tab_tags.layout_brutal_items.count()):
            card_w = self.tab_tags.layout_brutal_items.itemAt(i).widget()
            if card_w and hasattr(card_w, "sfx"):
                card_w.set_active_state(card_w.sfx in b_set)
        active_count = sum(1 for c in cats if c.get("suffix", "").upper() in b_set)
        self.tab_tags.lbl_brutal_count.setText(f"({active_count} / {len(cats)} Aktif)")

    def on_delete_tag(self, idx: int):
        cats = self.config.get("custom_trap_endings", [])
        if 0 <= idx < len(cats):
            sfx = cats[idx].get("suffix", "").upper()
            reply = QMessageBox.question(
                self, "Hapus Tag",
                f"Apakah Anda yakin ingin menghapus tag akhiran '{sfx}'?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                cats.pop(idx)
                self.config["custom_trap_endings"] = cats
                self.solver.set_custom_endings(cats)
                self.save_config_debounced()
                self.tab_tags.refresh_custom_list()
                self.tab_live.refresh_quick_tags(cats)
                if self.last_detected_word:
                    self.update_results(self.last_detected_word)
                self.show_toast(f"Tag '{sfx}' berhasil dihapus")

    def on_reorder_tag(self, src_idx: int, target_idx: int):
        cats = self.config.get("custom_trap_endings", [])
        if 0 <= src_idx < len(cats) and 0 <= target_idx < len(cats):
            item = cats.pop(src_idx)
            cats.insert(target_idx, item)
            self.config["custom_trap_endings"] = cats
            self.solver.set_custom_endings(cats)
            self.save_config_debounced()
            self.tab_tags.refresh_custom_list()
            self.tab_live.refresh_quick_tags(cats)
            if self.last_detected_word:
                self.update_results(self.last_detected_word)
            self.show_toast(f"Tag '{item.get('suffix')}' dipindahkan ke #{target_idx + 1}")

    def open_edit_tag_dialog(self, tag_data: dict = None):
        if tag_data is None and getattr(self, "_active_tag_dialog", None) is not None:
            try:
                self._active_tag_dialog.raise_()
                self._active_tag_dialog.activateWindow()
                self._active_tag_edit.setFocus()
                return
            except Exception:
                self._active_tag_dialog = None

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Tag Akhiran" if tag_data else "Tambah Tag Baru")
        dlg.setFixedSize(300, 140)
        dlg.setStyleSheet(f"""
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
        d_layout = QVBoxLayout(dlg)
        d_layout.setContentsMargins(16, 14, 16, 14)
        d_layout.setSpacing(10)

        lbl = QLabel("Huruf Akhiran (Suffix):")
        lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['text_primary']};")
        d_layout.addWidget(lbl)

        e_sfx = QLineEdit(tag_data.get("suffix", "") if tag_data else "")
        e_sfx.setPlaceholderText("Misal: AMSI, KSO, NS...")
        e_sfx.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME["bg_card"]};
                color: {THEME["text_primary"]};
                font-size: 13px;
                font-weight: bold;
                border: 1px solid {THEME["border_focus"]};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QLineEdit:focus {{
                border-color: {THEME["primary"]};
            }}
        """)
        d_layout.addWidget(e_sfx)

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
        """)
        btn_cancel.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Simpan")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setFixedHeight(28)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME["primary"]};
                color: {THEME["text_dark"]};
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 2px 14px;
            }}
        """)

        def _do_save():
            sfx = e_sfx.text().strip().upper()
            if not sfx:
                return
            cats = self.config.get("custom_trap_endings", [])
            if tag_data:
                tag_data["suffix"] = sfx
            else:
                palette = ["#cba6f7", "#f5c2e7", "#89dceb", "#a6e3a1", "#fab387", "#f38ba8"]
                chosen_color = palette[len(cats) % len(palette)]
                cats.append({"suffix": sfx, "enabled": True, "color": chosen_color})
            self.config["custom_trap_endings"] = cats
            self.solver.set_custom_endings(cats)
            self.save_config_debounced()
            self.tab_tags.refresh_custom_list()
            self.tab_live.refresh_quick_tags(cats)
            dlg.accept()
            self.show_toast(f"Tag '{sfx}' berhasil disimpan!")

        btn_save.clicked.connect(_do_save)
        e_sfx.returnPressed.connect(_do_save)
        btn_box.addWidget(btn_save)
        d_layout.addLayout(btn_box)

        if tag_data is None:
            self._active_tag_dialog = dlg
            self._active_tag_edit = e_sfx
        self._exec_dialog_with_focus(dlg, e_sfx)
        if tag_data is None:
            self._active_tag_dialog = None
            self._active_tag_edit = None

    def open_region_selector(self):
        from region_selector_qt import QtRegionSelector
        def _on_selected(area):
            if area:
                self.config["screen_area"] = area
                self.ocr.last_captured_image = None
                self.ocr.last_detection_result = None
                self.ocr.update_config(self.config)
                self.save_config_debounced()
                self.show_toast(f"Area Scanner disimpan: {area['width']}x{area['height']} px")
                self.preview_selected_area(area)
        self._region_selector = QtRegionSelector(on_selected_callback=_on_selected, title="KLIK & DRAG MOUSE UNTUK MEMILIH AREA SCANNER")
        self._region_selector.show()

    def preview_selected_area(self, area=None, title=None, bg_color=None):
        """Menampilkan kotak transparan sekejap di layar untuk mengonfirmasi area deteksi."""
        target_area = area or self.config.get("screen_area")
        if not target_area or target_area.get("width", 0) <= 0 or target_area.get("height", 0) <= 0:
            return
        l, t = int(target_area.get("left", 0)), int(target_area.get("top", 0))
        w, h = int(target_area.get("width", 100)), int(target_area.get("height", 50))
        bg = bg_color or "#f38ba8"
        t_text = title or f"AREA SCANNER ({w}x{h})"

        # Konversi piksel fisik (MSS) -> piksel logis Qt agar posisi overlay presisi di layar DPI scaling
        screen = QApplication.primaryScreen()
        for s in QApplication.screens():
            sdpr = s.devicePixelRatio() or 1.0
            sg = s.geometry()
            if (sg.x() * sdpr <= l < (sg.x() + sg.width()) * sdpr and
                    sg.y() * sdpr <= t < (sg.y() + sg.height()) * sdpr):
                screen = s
                break
        dpr = screen.devicePixelRatio() if screen else 1.0
        l_qt = int(round(l / dpr))
        t_qt = int(round(t / dpr))
        w_qt = max(1, int(round(w / dpr)))
        h_qt = max(1, int(round(h / dpr)))

        if getattr(self, "_area_preview_win", None) is not None:
            try:
                self._area_preview_win.close()
            except Exception:
                pass

        preview = QLabel(t_text)
        preview.setAlignment(Qt.AlignCenter)
        preview.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput
        )
        preview.setAttribute(Qt.WA_ShowWithoutActivating, True)
        preview.setWindowOpacity(0.45)
        preview.setStyleSheet(
            f"background-color: {bg}; color: #11111b; font-weight: bold; font-size: 10px; border: 2px solid #ffffff;"
        )
        preview.setGeometry(l_qt, t_qt, w_qt, h_qt)
        preview.show()
        self._area_preview_win = preview
        QTimer.singleShot(1200, preview.close)

    def test_region_scanner(self):
        """Menguji Area Scanner dengan menampilkan preview area dan menjalankan 1x scan OCR."""
        area = self.config.get("screen_area")
        if not area or area.get("width", 0) <= 0 or area.get("height", 0) <= 0:
            self.show_toast("Belum ada area layar yang diatur! Klik 'Atur Area Scanner' dulu.")
            return

        w = int(area.get("width", 0))
        h = int(area.get("height", 0))

        try:
            self.ocr.update_config(self.config)
            res = self.ocr.scan_once() or {}
            text = res.get("text", "").strip()
            conf_pct = int(res.get("confidence", 0.0) * 100)
            self.preview_selected_area(area, title=f"TEST AREA ({w}x{h})", bg_color=THEME["primary"])
            if text:
                self._on_scan_result(res)
                self.show_toast(f"Test Area ({w}x{h}): Terdeteksi '{text}' ({conf_pct}%)")
            else:
                self.show_toast(f"Test Area ({w}x{h}): Tidak ada teks terdeteksi")
        except Exception as e:
            self.preview_selected_area(area, title=f"TEST AREA ({w}x{h})", bg_color=THEME["primary"])
            self.show_toast(f"Gagal test Area Scanner: {e}")

    # --- Mode Dev & Window Management ---
    def set_always_on_top(self, enabled: bool):
        self.always_on_top = enabled
        self.config["always_on_top"] = enabled
        self.save_config_debounced()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, enabled)
        self.show()
        if hasattr(self, "title_bar"):
            self.title_bar.set_pinned(enabled)
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "chk_ontop"):
            if self.tab_system.chk_ontop.isChecked() != enabled:
                self.tab_system.chk_ontop.setChecked(enabled)
        status_str = "AKTIF" if enabled else "NONAKTIF"
        self.show_toast(f"Always-on-Top: {status_str}")

    def toggle_always_on_top(self):
        self.set_always_on_top(not self.always_on_top)

    def set_dev_mode(self, enabled: bool):
        self.dev_mode = enabled
        self.config["dev_mode"] = enabled
        self.save_config_debounced()
        if hasattr(self, "title_bar"):
            self.title_bar.set_dev_mode(enabled)
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "chk_dev_mode"):
            if self.tab_system.chk_dev_mode.isChecked() != enabled:
                self.tab_system.chk_dev_mode.setChecked(enabled)
        status_str = "AKTIF" if enabled else "NONAKTIF"
        self.show_toast(f"Mode Development: {status_str}")

    def toggle_dev_mode(self):
        self.set_dev_mode(not self.dev_mode)

    def restart_app(self):
        self.show_toast("Memulai ulang aplikasi...")
        self.updater.restart_app()

    # --- Pendataan Koreksi Sampel (F2) ---
    def open_koreksi_dialog(self):
        dlg = QtKoreksiDialog(self, parent=self)
        dlg.exec()

    def open_sample_folder(self):
        folder = os.path.abspath("sample")
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except Exception:
            pass

    # --- Git Updater & Branch Switcher ---
    def switch_updater_branch(self, target_branch: str):
        curr = self.updater.get_current_branch()
        if target_branch == curr:
            self.show_toast(f"Sudah berada di branch '{curr}'")
            return

        reply = QMessageBox.question(
            self,
            "Ganti Branch Git",
            f"Beralih dari branch '{curr}' ke branch '{target_branch}'?\n\n"
            f"Aplikasi akan melakukan checkout dan mengunduh pembaruan terbaru dari branch '{target_branch}'.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self.show_toast(f"Beralih ke branch '{target_branch}'...")
        res = self.updater.apply_update(target_branch=target_branch)
        if res.get("success"):
            self.config["updater_branch"] = target_branch
            self.save_config_debounced()
            msg = res.get("message", "Branch berhasil diganti.")
            restart_reply = QMessageBox.question(
                self,
                "Pembaruan Berhasil",
                f"{msg}\n\nIngin me-restart aplikasi sekarang agar perubahan aktif?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if restart_reply == QMessageBox.Yes:
                self.restart_app()
            else:
                self.tab_system.refresh_git_info()
        else:
            QMessageBox.critical(self, "Gagal Ganti Branch", f"Error: {res.get('message', 'Terjadi kesalahan')}")

    def check_updates(self):
        curr_branch = self.updater.get_current_branch()
        target_branch = getattr(self.tab_system, "combo_branch", None)
        tb = target_branch.currentText().strip() if target_branch else curr_branch

        self.show_toast(f"Memeriksa update di branch '{tb}'...")
        res = self.updater.check_for_updates(target_branch=tb)
        if not res.get("success"):
            QMessageBox.warning(self, "Cek Update", f"Gagal: {res.get('message', 'Tidak ada koneksi internet')}")
            return

        if res.get("has_update"):
            behind = res.get("behind_by", 1)
            commits = res.get("commits", [])
            commit_text = "\n".join([f"• {c['hash'][:7]}: {c['message']}" for c in commits[:5]])
            if len(commits) > 5:
                commit_text += f"\n... dan {len(commits) - 5} commit lainnya."

            reply = QMessageBox.question(
                self,
                "Pembaruan Tersedia",
                f"Tersedia {behind} pembaruan commit baru di branch '{tb}':\n\n{commit_text}\n\nUnduh dan terapkan sekarang?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.show_toast("Menerapkan pembaruan...")
                up_res = self.updater.apply_update(target_branch=tb)
                if up_res.get("success"):
                    r_rep = QMessageBox.question(
                        self,
                        "Berhasil Diperbarui",
                        f"{up_res.get('message')}\n\nRestart aplikasi sekarang?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if r_rep == QMessageBox.Yes:
                        self.restart_app()
                else:
                    QMessageBox.critical(self, "Gagal Update", up_res.get("message", "Error"))
        else:
            QMessageBox.information(self, "Pembaruan", f"Aplikasi Anda sudah versi terbaru di branch '{tb}'!")

    # --- Native Windows Frameless Resizing (WM_NCHITTEST) ---
    def nativeEvent(self, event_type, message):
        """
        Menangani resize window frameless di Windows via kernel WM_NCHITTEST.
        Bekerja di level window manager OS sebelum child widget, menjamin kursor
        tidak pernah 'nyangkut' dan resize berjalan sangat mulus (60 FPS).
        """
        if sys.platform == "win32" and event_type == "windows_generic_MSG":
            msg = wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x0084:  # WM_NCHITTEST
                pos = self.mapFromGlobal(QCursor.pos())
                lx = pos.x()
                ly = pos.y()
                w = self.width()
                h = self.height()
                b = 8  # Area deteksi tepi 8 piksel

                # Sudut bawah
                if ly >= h - b:
                    if lx <= b:
                        return True, 16  # HTBOTTOMLEFT
                    elif lx >= w - b:
                        return True, 17  # HTBOTTOMRIGHT
                    else:
                        return True, 15  # HTBOTTOM
                # Tepi samping kiri & kanan
                elif lx <= b:
                    return True, 10  # HTLEFT
                elif lx >= w - b:
                    return True, 11  # HTRIGHT

        return super().nativeEvent(event_type, message)

    def register_hotkeys(self):
        """Mendaftarkan ulang seluruh hotkey kustom dari config."""
        for hk in getattr(self, "_kb_hooks", []):
            try:
                import keyboard
                keyboard.remove_hotkey(hk)
            except Exception:
                pass
        self._kb_hooks = []

        for sc in getattr(self, "_qt_shortcuts", []):
            try:
                sc.setEnabled(False)
                sc.deleteLater()
            except Exception:
                pass
        self._qt_shortcuts = []

        hotkeys = self.config.get("hotkeys", DEFAULT_HOTKEYS)
        try:
            import keyboard
            has_kb = True
        except Exception:
            has_kb = False

        for action_id, key_str in hotkeys.items():
            key_clean = (key_str or "").strip()
            if not key_clean:
                continue
            if has_kb:
                try:
                    hk = keyboard.add_hotkey(key_clean.lower(), lambda a=action_id: self.hotkey_triggered.emit(a))
                    self._kb_hooks.append(hk)
                    continue
                except Exception:
                    pass
            try:
                sc = QShortcut(QKeySequence(key_clean), self)
                sc.activated.connect(lambda a=action_id: self._on_hotkey_action(a))
                self._qt_shortcuts.append(sc)
            except Exception:
                pass

        if hasattr(self, "tab_live") and hasattr(self.tab_live, "update_hotkey_tooltips"):
            self.tab_live.update_hotkey_tooltips(hotkeys)

    def set_hotkey(self, action_id: str, key_str: str):
        hotkeys = dict(self.config.get("hotkeys", DEFAULT_HOTKEYS))
        hotkeys[action_id] = (key_str or "").strip()
        self.config["hotkeys"] = hotkeys
        self.save_config_debounced()
        self.register_hotkeys()

    def reset_hotkeys(self):
        self.config["hotkeys"] = DEFAULT_HOTKEYS.copy()
        self.save_config_debounced()
        self.register_hotkeys()
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_hotkeys"):
            self.tab_system.refresh_hotkeys()
        self.show_toast("Semua hotkey dikembalikan ke pengaturan default!")

    def _on_hotkey_action(self, action_id: str):
        if action_id == "toggle_scan":
            self.toggle_scan()
        elif action_id == "flag_error":
            self._on_f2_hotkey()
        elif action_id == "add_whitelist":
            self.open_quick_add_dialog("whitelist")
        elif action_id == "add_blocklist":
            self.open_quick_add_dialog("blocklist")
        elif action_id == "add_kamus":
            self.open_quick_add_dialog("kamus")
        elif action_id == "add_tag":
            self.open_edit_tag_dialog(None)
        elif action_id == "cycle_mode":
            self.cycle_game_mode()

    def _on_f2_hotkey(self):
        try:
            conf = (self.last_detected_conf / 100.0) if self.last_detected_conf is not None else None
            if self.ocr.last_detection_result:
                conf = self.ocr.last_detection_result.get("confidence", conf)

            saved = self.ocr.save_to_kurang_tepat(
                detected_text=self.last_detected_word,
                confidence=conf,
                correct_text=None
            )
            if saved:
                self.show_toast(f"Sampel F2 tersimpan: {os.path.basename(saved)}")
                if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_counts"):
                    self.tab_system.refresh_counts()
            else:
                self.show_toast("Belum ada area layar yang diatur! Atur lewat System -> Atur Area Scanner")
        except Exception as e:
            self.show_toast(f"Gagal simpan sampel F2: {e}")

    # --- Sorting tags ---
    def on_sort_custom_categories_az(self):
        cats = self.config.get("custom_trap_endings", [])
        cats.sort(key=lambda c: c.get("suffix", "").upper())
        self._after_sort_tags(cats, "A-Z")

    def on_sort_custom_categories_count(self, reverse=True):
        cats = self.config.get("custom_trap_endings", [])
        cats.sort(key=lambda c: self.solver.count_words_by_suffix(c.get("suffix", "")), reverse=reverse)
        txt = "Kata Terbanyak" if reverse else "Kata Terdikit"
        self._after_sort_tags(cats, txt)

    def on_sort_custom_categories_length(self, reverse=True):
        cats = self.config.get("custom_trap_endings", [])
        cats.sort(key=lambda c: (len(c.get("suffix", "")), c.get("suffix", "").upper()), reverse=reverse)
        txt = "Huruf Terpanjang" if reverse else "Huruf Terpendek"
        self._after_sort_tags(cats, txt)

    def _after_sort_tags(self, cats, desc):
        self.config["custom_trap_endings"] = cats
        self.solver.set_custom_endings(cats)
        self.save_config_debounced()
        self.tab_tags.refresh_custom_list()
        self.tab_live.refresh_quick_tags(cats)
        if self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast(f"Tag diurutkan berdasarkan {desc}")

    # --- Window Geometry & Persistence ---
    def _init_window_geometry(self):
        target_w = 476
        target_h = 953
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            target_h = min(target_h, max(500, avail.height() - 40))
            # Posisikan default di sebelah kanan layar (20px dari tepi kanan)
            target_x = max(10, avail.right() - target_w - 20 + 1)
            target_y = avail.top() + max(10, (avail.height() - target_h) // 2)

            saved_geom = self.config.get("window_geometry")
            if saved_geom and isinstance(saved_geom, dict):
                gx = saved_geom.get("x", target_x)
                gy = saved_geom.get("y", target_y)
                gw = saved_geom.get("width", target_w)
                gh = saved_geom.get("height", target_h)

                gw = max(380, min(gw, avail.width() - 20))
                gh = max(500, min(gh, avail.height() - 20))
                if gx + gw > avail.right() + 10 or gx < avail.left() - 10:
                    gx = max(10, avail.right() - gw - 20 + 1)
                if gy + gh > avail.bottom() + 10 or gy < avail.top() - 10:
                    gy = max(10, avail.top() + 15)

                self.setGeometry(gx, gy, gw, gh)
            else:
                self.setGeometry(target_x, target_y, target_w, target_h)
        else:
            self.resize(target_w, target_h)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._save_window_geom()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toast_frame") and self.toast_frame.isVisible():
            w = self.toast_frame.width()
            h = self.toast_frame.height()
            x = (self.width() - w) // 2
            y = self.height() - h - 16
            self.toast_frame.setGeometry(x, y, w, h)
        self._save_window_geom()

    def _save_window_geom(self):
        geom = self.geometry()
        if self.isMinimized() or geom.width() < 100 or geom.height() < 100:
            return
        self.config["window_geometry"] = {
            "x": geom.x(),
            "y": geom.y(),
            "width": geom.width(),
            "height": geom.height()
        }
        self.save_config_debounced(delay_ms=800)

    # --- Toast & Config Helpers ---
    def show_toast(self, message: str, duration_ms: int = 2500):
        self.lbl_toast.setText(message)
        self.lbl_toast.adjustSize()
        w = max(180, self.lbl_toast.sizeHint().width() + 36)
        h = 30
        x = (self.width() - w) // 2
        y = self.height() - h - 16
        self.toast_frame.setGeometry(x, y, w, h)
        self.toast_frame.show()
        self.toast_frame.raise_()
        QTimer.singleShot(duration_ms, self.toast_frame.hide)

    def save_config_debounced(self, delay_ms: int = 400):
        if self._save_timer:
            self._save_timer.stop()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(lambda: save_config(self.config))
        self._save_timer.start(delay_ms)

    def closeEvent(self, event):
        if self.is_scanning:
            self.scan_worker.stop()
        save_config(self.config)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(GLOBAL_QSS)
    window = SambungKataQtApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
