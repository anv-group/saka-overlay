import sys
import os
import time
import json
import hashlib
import threading
from collections import Counter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QDialog, QLineEdit,
    QColorDialog, QMessageBox, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QRect
from PySide6.QtGui import QIcon, QPixmap, QCursor, QKeySequence, QShortcut
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from ctypes import wintypes

from qt_theme import THEME, GLOBAL_QSS, get_qicon
from qt_components import QtTopTabStrip, QtMiniTickerBar, QtCustomTitleBar
from tab_views_qt import QtLiveTabView, QtTagsTabView, QtDictionaryTabView, QtSystemTabView, QtKoreksiDialog

from config import (
    load_config, save_config, DEFAULT_HOTKEYS,
    MODE_SYNC_KEYS, extract_mode_state, load_txt_mode_state, save_txt_mode_state
)
from solver import SambungKataSolver
from ocr_engine import OCREngine
from updater import GitUpdater
from db_sync import SupabaseSyncManager, SupabaseRestClient, SettingsTableUnavailableError


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


class SingleInstanceGuard:
    """Mengunci agar hanya 1 instance SAKA Overlay yang berjalan (kecuali allow_multiple_instances=True)."""

    def __init__(self, server_name: str = None, repo_dir: str = None):
        if server_name:
            self.server_name = server_name
        else:
            base = os.path.abspath(repo_dir or os.path.dirname(os.path.abspath(__file__))).lower()
            digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
            self.server_name = f"saka-overlay-{digest}"
        self.server = None
        self._on_activate = None

    def try_notify_existing(self, timeout_ms: int = 250) -> bool:
        """Jika instance aktif ditemukan, kirim sinyal ACTIVATE dan kembalikan True."""
        sock = QLocalSocket()
        sock.connectToServer(self.server_name)
        if sock.waitForConnected(timeout_ms):
            try:
                sock.write(b"ACTIVATE\n")
                sock.flush()
                sock.waitForBytesWritten(200)
            except Exception:
                pass
            sock.disconnectFromServer()
            return True
        QLocalServer.removeServer(self.server_name)
        return False

    def start_listening(self, on_activate=None) -> bool:
        """Membuka server IPC lokal untuk mendeteksi percobaan instance kedua."""
        self._on_activate = on_activate
        if self.server is not None:
            return True
        srv = QLocalServer()
        srv.newConnection.connect(self._handle_connection)
        if not srv.listen(self.server_name):
            QLocalServer.removeServer(self.server_name)
            if not srv.listen(self.server_name):
                return False
        self.server = srv
        return True

    def _handle_connection(self):
        if not self.server:
            return
        while self.server.hasPendingConnections():
            conn = self.server.nextPendingConnection()
            if not conn:
                continue
            if conn.bytesAvailable() <= 0:
                conn.waitForReadyRead(100)
            payload = bytes(conn.readAll()).decode("utf-8", errors="ignore").strip()
            conn.disconnectFromServer()
            conn.deleteLater()
            if (not payload or payload.startswith("ACTIVATE")) and callable(self._on_activate):
                self._on_activate()

    def close(self):
        if self.server is not None:
            try:
                self.server.close()
                self.server.deleteLater()
            except Exception:
                pass
            self.server = None
        try:
            QLocalServer.removeServer(self.server_name)
        except Exception:
            pass


class SambungKataQtApp(QMainWindow):
    """
    Aplikasi Utama SAKA Overlay berbasis PySide6 (Tactical Cyber Bamboo Theme).
    """
    hotkey_triggered = Signal(str)
    _db_test_done = Signal(bool, str, object)
    _db_import_done = Signal(bool, str, str, str, str)
    _db_download_done = Signal(bool, str, object)
    _bg_update_checked = Signal(dict)

    def __init__(self, instance_guard: SingleInstanceGuard = None):
        super().__init__()
        self._instance_guard = instance_guard
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

        storage_mode = self.config.get("storage_mode", "txt")
        self.sync_manager = SupabaseSyncManager(
            cache_path=os.path.join(base_dir, "db_cache.json"),
            parent=self
        )
        self.solver = SambungKataSolver(
            dictionary_path=os.path.join(base_dir, "kamus_lengkap.txt"),
            blacklist_path=os.path.join(base_dir, "blacklist.csv"),
            whitelist_path=os.path.join(base_dir, "whitelist.csv"),
            kbbi_path=os.path.join(base_dir, "kamus_kbbi.txt"),
            contek_path=os.path.join(base_dir, "kamus_contek.txt"),
            custom_dict_path=os.path.join(base_dir, "kamus_custom.csv"),
            use_kbbi=self.config.get("use_kbbi", False),
            use_contek=self.config.get("use_contek", True),
            storage_mode=storage_mode,
            db_mutation_callback=self._on_solver_db_mutation
        )
        if storage_mode == "supabase":
            self.solver.apply_db_snapshot(self.sync_manager.load_cached_records())
            cached_mode = self.sync_manager.load_cached_mode_state()
            if isinstance(cached_mode, dict):
                for mk in MODE_SYNC_KEYS:
                    if mk in cached_mode:
                        self.config[mk] = cached_mode[mk]
        self.solver.set_custom_endings(self.config.get("custom_trap_endings", []))
        self.solver.set_tier0_sort_mode(self.config.get("tier0_sort_mode", "default"))

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
        self.title_bar.db_status_clicked.connect(self._jump_to_db_settings)
        self.main_layout.addWidget(self.title_bar)

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

        self._last_db_sync_time = "-"
        self._last_db_event_note = ""
        self._online_users_count = 0
        self._online_users_names = []
        self._presence_initialized = False
        self._prev_online_names = []

        # Setup Database Sync Signals
        self._mode_sync_timer = QTimer(self)
        self._mode_sync_timer.setSingleShot(True)
        self._mode_sync_timer.timeout.connect(self._flush_local_mode_to_db)

        self._db_test_done.connect(lambda ok, msg, cb: cb(ok, msg))
        self._db_import_done.connect(self._on_import_finished)
        self._db_download_done.connect(self._on_download_finished)
        self.sync_manager.snapshot_loaded.connect(self._on_db_snapshot_loaded)
        self.sync_manager.remote_event_received.connect(self._on_db_remote_event)
        self.sync_manager.mode_state_loaded.connect(self._on_db_mode_state_loaded)
        self.sync_manager.remote_mode_event_received.connect(self._on_db_remote_mode_event)
        self.sync_manager.presence_updated.connect(self._on_db_presence_updated)
        self.sync_manager.settings_table_missing.connect(
            lambda _msg: self.show_toast("SQL lama: klik 'Salin SQL' & Run ulang di Supabase untuk sync Tab MODE", 4500)
        )
        self.sync_manager.status_changed.connect(self._on_db_status_changed)
        self.sync_manager.operation_failed.connect(lambda msg: self.show_toast(f"Sync DB: {msg}", 3500))

        if storage_mode == "supabase":
            sb_url = self.config.get("supabase_url", "").strip()
            sb_key = self.config.get("supabase_anon_key", "").strip()
            sb_nick = self.config.get("sync_nickname", "").strip()
            if sb_url and sb_key:
                self.sync_manager.start(sb_url, sb_key, sb_nick)
            else:
                self._on_db_status_changed("error", "Mode Database aktif, tetapi URL / Anon Key belum diisi.")
        else:
            self._on_db_status_changed("txt", "Mode File CSV (Default Lokal)")

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

        # Notifier update otomatis di latar belakang (startup + berkala tiap 30 menit)
        self._update_check_in_progress = False
        self._last_notified_update_hash = ""
        self._confirmed_branch_selection = self.updater.get_current_branch()
        self._bg_update_checked.connect(self._on_bg_update_checked)
        self._update_poll_timer = QTimer(self)
        self._update_poll_timer.timeout.connect(self.check_updates_background)
        self._update_poll_timer.start(30 * 60 * 1000)
        if self.config.get("auto_check_update_on_startup", True) and self.config.get("updater_mode", "prompt") != "disabled":
            QTimer.singleShot(1500, self.check_updates_background)

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
            self._on_local_mode_mutated()
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

            self._on_local_mode_mutated()

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
        self._on_local_mode_mutated()

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
        self._on_local_mode_mutated()

        self.tab_live.refresh_quick_tags(cats)
        self.tab_live.mode_pills.set_mode(mode)
        self.tab_tags.refresh_custom_list()
        self.tab_tags.refresh_brutal_list()

        if self.last_detected_word:
            self.update_results(self.last_detected_word)
        mode_label = "NORMAL" if mode == "default" else mode.upper()
        self.show_toast(f"Mode permainan diubah ke {mode_label}")

    def cycle_game_mode(self):
        order = ["default", "santai", "brutal"]
        cur = self.config.get("game_mode", "default")
        nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "default"
        self.set_game_mode(nxt)

    def toggle_tier0_sort(self):
        curr = self.config.get("tier0_sort_mode", "default")
        nxt = "tag_order" if curr == "default" else "default"
        self.config["tier0_sort_mode"] = nxt
        self.solver.set_tier0_sort_mode(nxt)
        self._on_local_mode_mutated()
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

    def _get_active_live_prefix(self) -> str:
        if getattr(self, "manual_override_active", False):
            manual_q = "".join([c for c in self.tab_live.edit_search.text().upper() if c.isalpha()])
            if manual_q:
                return manual_q
        return self.last_detected_word

    def _refresh_all_word_views(self):
        active_prefix = self._get_active_live_prefix()
        if active_prefix:
            conf = 100 if self.manual_override_active else self.last_detected_conf
            self.update_results(active_prefix, conf)
        if hasattr(self, "tab_kamus"):
            self.tab_kamus.refresh_whitelist()
            self.tab_kamus.refresh_blocklist()
            if getattr(self.tab_kamus.sub_strip, "active_sub", "") == "explorer":
                self.tab_kamus._search_dictionary()
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_db_stats"):
            self.tab_system.refresh_db_stats()

    # --- Database Sinkronisasi & Mode Handlers ---
    def _jump_to_db_settings(self):
        self.top_strip.select_tab("system")
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "db_box"):
            QTimer.singleShot(50, lambda: self.tab_system.scroll.ensureWidgetVisible(self.tab_system.db_box))

    def _on_solver_db_mutation(self, action: str, word: str, record: dict = None):
        if self.config.get("storage_mode", "txt") == "supabase":
            self.sync_manager.enqueue_mutation(action, word, record)
            self._last_db_sync_time = time.strftime("%H:%M:%S")
            st = str((record or {}).get("status") or ("hapus" if action == "delete" else "")).lower()
            self._last_db_event_note = f"Lokal: {word.upper()} ({st})"
            if hasattr(self, "title_bar"):
                self.title_bar.flash_db_activity("local")
            if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_db_stats"):
                self.tab_system.refresh_db_stats()

    def _on_db_status_changed(self, state_code: str, detail: str):
        self._last_db_state_code = state_code
        self._last_db_state_detail = detail
        if state_code in ("txt", "offline", "error"):
            self._online_users_count = 0
            self._online_users_names = []
            self._presence_initialized = False
            self._prev_online_names = []
        self._update_titlebar_db_tooltip()
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_db_status"):
            self.tab_system.refresh_db_status(state_code, detail)

    def _update_titlebar_db_tooltip(self):
        if not hasattr(self, "title_bar"):
            return
        state_code = getattr(self, "_last_db_state_code", "txt")
        detail = getattr(self, "_last_db_state_detail", "")
        if state_code == "live":
            if self._online_users_count > 0:
                names = ", ".join(self._online_users_names)
                tip_info = f"{self._online_users_count} online ({names})"
            else:
                tip_info = ""
        elif state_code == "error":
            tip_info = detail
        else:
            tip_info = ""
        self.title_bar.set_db_status(state_code, tip_info)

    def _on_db_presence_updated(self, count: int, names: list):
        new_names = list(names or [])
        if not self._presence_initialized:
            if count > 0:
                self._presence_initialized = True
                self._prev_online_names = list(new_names)
        else:
            prev_c = Counter(self._prev_online_names)
            curr_c = Counter(new_names)
            joined = list((curr_c - prev_c).elements())
            left = list((prev_c - curr_c).elements())
            if len(joined) == 1 and not left:
                self.show_toast(f"{joined[0]} terhubung ke database", 2000)
            elif len(left) == 1 and not joined:
                self.show_toast(f"{left[0]} keluar dari database", 2000)
            self._prev_online_names = list(new_names)

        self._online_users_count = int(count)
        self._online_users_names = new_names
        self._update_titlebar_db_tooltip()
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_db_stats"):
            self.tab_system.refresh_db_stats()

    def _on_db_snapshot_loaded(self, records: dict, is_delta: bool):
        if self.config.get("storage_mode", "txt") != "supabase":
            return
        self.solver.apply_db_snapshot(records)
        self._last_db_sync_time = time.strftime("%H:%M:%S")
        self._last_db_event_note = "Snapshot server"
        self._refresh_all_word_views()
        if is_delta and hasattr(self, "title_bar"):
            self.title_bar.flash_db_activity("remote")
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_db_stats"):
            self.tab_system.refresh_db_stats()

    def _on_db_remote_event(self, ev_type: str, record: dict, old_record: dict, is_self: bool):
        if self.config.get("storage_mode", "txt") != "supabase":
            return
        w = self.solver.apply_db_event(ev_type, record, old_record)
        self._refresh_all_word_views()
        if w:
            self._last_db_sync_time = time.strftime("%H:%M:%S")
            author = (record or {}).get("added_by", "").strip()
            by_str = f" ({author})" if author else ""
            if ev_type == "DELETE":
                self._last_db_event_note = f"{w.upper()} dihapus{by_str}"
                if not is_self:
                    self.show_toast(f"Sync{by_str}: '{w.upper()}' dihapus", 2200)
            else:
                st = str((record or {}).get("status") or "").upper()
                label_map = {"WHITELIST": "Whitelist", "BLOCKLIST": "Blocklist", "CUSTOM": "Kamus"}
                lbl = label_map.get(st, st)
                self._last_db_event_note = f"{w.upper()} -> {lbl}{by_str}"
                if not is_self:
                    self.show_toast(f"Sync{by_str}: '{w.upper()}' -> {lbl}", 2200)
            if not is_self and hasattr(self, "title_bar"):
                self.title_bar.flash_db_activity("remote")
            if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_db_stats"):
                self.tab_system.refresh_db_stats()

    def _on_local_mode_mutated(self):
        if self.config.get("storage_mode", "txt") == "supabase":
            self._mode_sync_timer.start(200)
        else:
            self.save_config_debounced()

    def _flush_local_mode_to_db(self):
        if self.config.get("storage_mode", "txt") != "supabase":
            return
        mode_state = extract_mode_state(self.config)
        self.sync_manager.enqueue_mode_state(mode_state)
        self._last_db_sync_time = time.strftime("%H:%M:%S")
        self._last_db_event_note = "Lokal: Mode/Tag"
        if hasattr(self, "title_bar"):
            self.title_bar.flash_db_activity("local")
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_db_stats"):
            self.tab_system.refresh_db_stats()

    def _apply_mode_state_to_runtime(self, mode_state: dict):
        if not isinstance(mode_state, dict):
            return
        for mk in MODE_SYNC_KEYS:
            if mk in mode_state:
                self.config[mk] = mode_state[mk]

        cats = self.config.get("custom_trap_endings", [])
        cur_mode = self.config.get("game_mode", "default")
        sort_m = self.config.get("tier0_sort_mode", "default")

        self.solver.set_custom_endings(cats)
        self.solver.set_tier0_sort_mode(sort_m)

        if hasattr(self, "tab_live"):
            self.tab_live.refresh_quick_tags(cats)
            self.tab_live.mode_pills.set_mode(cur_mode)
            self.tab_live.update_sort_button(sort_m)
        if hasattr(self, "tab_tags"):
            self.tab_tags.refresh_custom_list()
            self.tab_tags.refresh_brutal_list()
        self._refresh_all_word_views()

    def _on_db_mode_state_loaded(self, mode_state: dict, updated_by: str):
        if self.config.get("storage_mode", "txt") != "supabase":
            return
        if self._mode_sync_timer.isActive():
            return
        self._apply_mode_state_to_runtime(mode_state)
        self._last_db_sync_time = time.strftime("%H:%M:%S")
        by_str = f" ({updated_by})" if updated_by else ""
        self._last_db_event_note = f"Mode/Tag{by_str}"
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_db_stats"):
            self.tab_system.refresh_db_stats()

    def _on_db_remote_mode_event(self, mode_state: dict, updated_by: str, is_self: bool):
        if self.config.get("storage_mode", "txt") != "supabase":
            return
        if is_self or self._mode_sync_timer.isActive():
            return
        self._apply_mode_state_to_runtime(mode_state)
        self._last_db_sync_time = time.strftime("%H:%M:%S")
        by_str = f" ({updated_by})" if updated_by else ""
        self._last_db_event_note = f"Mode/Tag diperbarui{by_str}"
        self.show_toast(f"Sync{by_str}: Tag/Mode diperbarui", 2200)
        if hasattr(self, "title_bar"):
            self.title_bar.flash_db_activity("remote")
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "refresh_db_stats"):
            self.tab_system.refresh_db_stats()

    def update_sync_nickname(self, nickname: str):
        nick = (nickname or "").strip()
        if nick == self.config.get("sync_nickname", ""):
            return
        self.config["sync_nickname"] = nick
        self.save_config_debounced()
        self.sync_manager.update_nickname(nick)
        if self.config.get("storage_mode") == "supabase":
            self.show_toast(f"Nickname diperbarui: {nick or 'Anonim'}")

    def force_resync_database(self):
        if self.config.get("storage_mode", "txt") != "supabase":
            return
        url = self.config.get("supabase_url", "").strip()
        key = self.config.get("supabase_anon_key", "").strip()
        nick = self.config.get("sync_nickname", "").strip()
        if not url or not key:
            self.show_toast("URL atau Anon Key belum diisi.")
            return
        if self.sync_manager._running:
            self.sync_manager.request_resync()
        else:
            self.sync_manager.start(url, key, nick)
        self.show_toast("Menyinkronkan ulang data dari server...")

    def clear_database_cache(self):
        reply = QMessageBox.question(
            self,
            "Hapus Cache Lokal Database",
            "Hapus file cache lokal (db_cache.json)?\n\n"
            "Jika Mode Database sedang aktif, data akan diambil ulang dari server.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.sync_manager.clear_cache()
        if self.config.get("storage_mode", "txt") == "supabase":
            self.solver.apply_db_snapshot({})
            self._refresh_all_word_views()
            url = self.config.get("supabase_url", "").strip()
            key = self.config.get("supabase_anon_key", "").strip()
            nick = self.config.get("sync_nickname", "").strip()
            if url and key:
                self.sync_manager.start(url, key, nick)
        self.show_toast("Cache lokal database (db_cache.json) dihapus")

    def switch_to_txt_mode(self):
        if self._mode_sync_timer.isActive():
            self._mode_sync_timer.stop()
        self.sync_manager.stop()
        self.config["storage_mode"] = "txt"
        save_config(self.config)
        self.solver.switch_storage_mode("txt")
        self._apply_mode_state_to_runtime(load_txt_mode_state())
        self._on_db_status_changed("txt", "Mode File CSV aktif: membaca & menyimpan ke file .csv lokal.")
        self.show_toast("Beralih ke Mode File CSV (Default)")

    def activate_database_mode(self, url: str, anon_key: str, nickname: str = ""):
        if self.config.get("storage_mode", "txt") == "txt":
            save_config(self.config)
        self.config["storage_mode"] = "supabase"
        self.config["supabase_url"] = url
        self.config["supabase_anon_key"] = anon_key
        self.config["sync_nickname"] = nickname
        save_config(self.config)

        cached = self.sync_manager.load_cached_records()
        self.solver.switch_storage_mode("supabase", cached)
        cached_mode = self.sync_manager.load_cached_mode_state()
        if isinstance(cached_mode, dict):
            self._apply_mode_state_to_runtime(cached_mode)
        else:
            self._refresh_all_word_views()
        self.sync_manager.start(url, anon_key, nickname)

    def test_database_connection(self, url: str, anon_key: str, callback):
        def _worker():
            try:
                client = SupabaseRestClient(url, anon_key)
                ok, msg = client.test_connection()
            except Exception as exc:
                ok, msg = False, str(exc)
            self._db_test_done.emit(ok, msg, callback)

        threading.Thread(target=_worker, daemon=True).start()

    def import_txt_to_database(self, url: str, anon_key: str, nickname: str = ""):
        records = self.solver.export_txt_records_for_import(added_by=nickname)
        local_mode = load_txt_mode_state()

        dlg = QDialog(self)
        dlg.setWindowTitle("Upload Lokal -> Database")
        dlg.setFixedWidth(360)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            QLabel {{ color: {THEME['text_primary']}; border: none; background: transparent; }}
            QCheckBox {{ color: {THEME['text_primary']}; font-size: 11px; spacing: 8px; background: transparent; }}
            QCheckBox::indicator {{
                width: 15px; height: 15px;
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                background-color: {THEME['bg_root']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME['primary']};
                border-color: {THEME['primary']};
            }}
        """)
        dl = QVBoxLayout(dlg)
        dl.setContentsMargins(14, 12, 14, 12)
        dl.setSpacing(10)

        lbl_info = QLabel("Pilih data lokal yang ingin di-upload ke Database Privat:")
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        dl.addWidget(lbl_info)

        chk_words = QCheckBox(f"Daftar Kata (whitelist.csv, blacklist.csv & kamus_custom.csv: {len(records)} kata)")
        chk_words.setChecked(bool(records))
        chk_words.setEnabled(bool(records))
        dl.addWidget(chk_words)

        tag_cnt = len(local_mode.get("custom_trap_endings", []))
        chk_mode = QCheckBox(f"Pengaturan MODE ({tag_cnt} Tag, Urutan, On/Off, Brutal, Mode)")
        chk_mode.setChecked(True)
        dl.addWidget(chk_mode)

        lbl_note = QLabel("(File .csv dan pengaturan Mode Lokal tidak akan diubah.)")
        lbl_note.setStyleSheet(f"color: {THEME['text_muted']}; font-size: 10px;")
        dl.addWidget(lbl_note)

        brow = QHBoxLayout()
        brow.addStretch(1)
        btn_no = QPushButton("Batal")
        btn_no.setCursor(Qt.PointingHandCursor)
        btn_no.setStyleSheet(f"background-color: {THEME['bg_hover']}; color: {THEME['text_primary']}; border: 1px solid {THEME['border']}; border-radius: 4px; padding: 5px 12px; font-size: 11px;")
        btn_no.clicked.connect(dlg.reject)
        brow.addWidget(btn_no)

        btn_yes = QPushButton("Upload Sekarang")
        btn_yes.setCursor(Qt.PointingHandCursor)
        btn_yes.setStyleSheet(f"background-color: {THEME['primary']}; color: {THEME['text_dark']}; border: none; border-radius: 4px; padding: 5px 14px; font-size: 11px; font-weight: bold;")
        btn_yes.clicked.connect(dlg.accept)
        brow.addWidget(btn_yes)
        dl.addLayout(brow)

        if dlg.exec() != QDialog.Accepted:
            return

        do_words = chk_words.isChecked() and bool(records)
        do_mode = chk_mode.isChecked()
        if not do_words and not do_mode:
            self.show_toast("Tidak ada data yang dipilih untuk di-upload.")
            return

        self.show_toast("Mengupload data lokal ke database...")

        def _worker():
            try:
                client = SupabaseRestClient(url, anon_key)
                parts = []
                if do_words:
                    count = client.upsert_batch(records)
                    parts.append(f"{count} kata")
                if do_mode:
                    client.upsert_mode_state(local_mode, updated_by=nickname)
                    parts.append("pengaturan MODE")
                summary = " & ".join(parts)
                self._db_import_done.emit(True, summary, url, anon_key, nickname)
            except Exception as exc:
                self._db_import_done.emit(False, str(exc), url, anon_key, nickname)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_import_finished(self, ok: bool, summary: str, url: str, anon_key: str, nickname: str):
        if ok:
            self.show_toast(f"Berhasil mengupload {summary} ke database!")
            if self.config.get("storage_mode") == "supabase":
                self.sync_manager.start(url, anon_key, nickname)
            else:
                self.activate_database_mode(url, anon_key, nickname)
        else:
            QMessageBox.warning(self, "Upload Gagal", f"Gagal mengupload data lokal ke database:\n{summary}")

    def download_database_to_txt(self, url: str, anon_key: str):
        dlg = QDialog(self)
        dlg.setWindowTitle("Download Database -> Lokal")
        dlg.setFixedWidth(365)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            QLabel {{ color: {THEME['text_primary']}; border: none; background: transparent; }}
            QCheckBox {{ color: {THEME['text_primary']}; font-size: 11px; spacing: 8px; background: transparent; }}
            QCheckBox::indicator {{
                width: 15px; height: 15px;
                border: 1px solid {THEME['border']};
                border-radius: 3px;
                background-color: {THEME['bg_root']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME['primary']};
                border-color: {THEME['primary']};
            }}
        """)
        dl = QVBoxLayout(dlg)
        dl.setContentsMargins(14, 12, 14, 12)
        dl.setSpacing(10)

        lbl_info = QLabel("Pilih data dari Database Privat untuk disimpan ke file lokal:")
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 11px;")
        dl.addWidget(lbl_info)

        chk_words = QCheckBox("Daftar Kata (simpan ke whitelist.csv, blacklist.csv, & kamus_custom.csv)")
        chk_words.setChecked(True)
        dl.addWidget(chk_words)

        chk_overwrite = QCheckBox("Timpa penuh whitelist.csv & blacklist.csv (hapus yang tidak ada di DB)")
        chk_overwrite.setChecked(False)
        chk_overwrite.setStyleSheet(f"color: {THEME['text_secondary']}; font-size: 10px; padding-left: 18px; spacing: 6px; background: transparent;")
        chk_words.toggled.connect(chk_overwrite.setEnabled)
        dl.addWidget(chk_overwrite)

        chk_mode = QCheckBox("Pengaturan MODE (simpan Tag, Urutan, Brutal ke Mode CSV lokal)")
        chk_mode.setChecked(True)
        dl.addWidget(chk_mode)

        brow = QHBoxLayout()
        brow.addStretch(1)
        btn_no = QPushButton("Batal")
        btn_no.setCursor(Qt.PointingHandCursor)
        btn_no.setStyleSheet(f"background-color: {THEME['bg_hover']}; color: {THEME['text_primary']}; border: 1px solid {THEME['border']}; border-radius: 4px; padding: 5px 12px; font-size: 11px;")
        btn_no.clicked.connect(dlg.reject)
        brow.addWidget(btn_no)

        btn_yes = QPushButton("Download Sekarang")
        btn_yes.setCursor(Qt.PointingHandCursor)
        btn_yes.setStyleSheet(f"background-color: {THEME['primary']}; color: {THEME['text_dark']}; border: none; border-radius: 4px; padding: 5px 14px; font-size: 11px; font-weight: bold;")
        btn_yes.clicked.connect(dlg.accept)
        brow.addWidget(btn_yes)
        dl.addLayout(brow)

        if dlg.exec() != QDialog.Accepted:
            return

        do_words = chk_words.isChecked()
        do_overwrite = chk_overwrite.isChecked()
        do_mode = chk_mode.isChecked()
        if not do_words and not do_mode:
            self.show_toast("Tidak ada data yang dipilih untuk di-download.")
            return

        self.show_toast("Mengambil data dari database ke lokal...")

        def _worker():
            try:
                client = SupabaseRestClient(url, anon_key)
                payload = {
                    "do_words": do_words,
                    "do_overwrite": do_overwrite,
                    "do_mode": do_mode,
                    "records": None,
                    "mode_state": None,
                }
                if do_words:
                    payload["records"] = client.fetch_all_records()
                if do_mode:
                    try:
                        ms, _ = client.fetch_mode_state()
                        payload["mode_state"] = ms
                    except SettingsTableUnavailableError:
                        payload["mode_state"] = None
                self._db_download_done.emit(True, "", payload)
            except Exception as exc:
                self._db_download_done.emit(False, str(exc), None)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_download_finished(self, ok: bool, err: str, payload):
        if not ok:
            QMessageBox.warning(self, "Download Gagal", f"Gagal mendownload data dari database:\n{err}")
            return

        parts = []
        if payload.get("do_words") and isinstance(payload.get("records"), dict):
            wl_n, bl_n, cm_n = self.solver.apply_db_records_to_txt_files(
                payload["records"], overwrite_lists=bool(payload.get("do_overwrite"))
            )
            parts.append(f"WL:{wl_n}, BL:{bl_n}, Kamus+:{cm_n}")
        if payload.get("do_mode") and isinstance(payload.get("mode_state"), dict):
            save_txt_mode_state(payload["mode_state"])
            if self.config.get("storage_mode", "txt") == "txt":
                self._apply_mode_state_to_runtime(load_txt_mode_state())
            parts.append("MODE")

        if self.config.get("storage_mode", "txt") == "txt":
            self._refresh_all_word_views()

        if parts:
            self.show_toast(f"Download DB -> Lokal selesai ({' | '.join(parts)})", 3200)
        else:
            self.show_toast("Tidak ada data baru di database untuk disimpan ke lokal.")

    def on_add_word_quick(self, word: str):
        if not word:
            return False, "Kata kosong"
        ok, msg = self.solver.add_word(word)
        if ok:
            self.show_toast(f"'{word.upper()}' berhasil ditambahkan ke Kamus! ")
            self._refresh_all_word_views()
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
            if self.solver.whitelist_word(w):
                self.show_toast(f"'{word.upper()}' ditambahkan ke Whitelist")
            else:
                self.show_toast(f"'{word.upper()}' sudah ada di Whitelist")
        self._refresh_all_word_views()

    def on_block_word(self, word: str):
        if not word:
            return
        w = word.strip().lower()
        if self.solver.blacklist_word(w):
            self.show_toast(f"'{word.upper()}' diblokir ke Blocklist")
        else:
            self.show_toast(f"'{word.upper()}' sudah ada di Blocklist")
        self._refresh_all_word_views()

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
        self._on_local_mode_mutated()

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
                self._on_local_mode_mutated()
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
            self._on_local_mode_mutated()
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
        dlg.setFixedWidth(320)
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
        d_layout.setSpacing(8)

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

        lbl_err = QLabel("")
        lbl_err.setWordWrap(True)
        lbl_err.setStyleSheet(
            f"font-size: 11px; font-weight: bold; color: {THEME['danger']}; "
            f"background-color: rgba(239, 68, 68, 0.14); border: 1px solid {THEME['danger']}; "
            f"border-radius: 4px; padding: 4px 8px;"
        )
        lbl_err.hide()
        d_layout.addWidget(lbl_err)

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
            if any((c is not tag_data) and (str(c.get("suffix", "")).strip().upper() == sfx) for c in cats if isinstance(c, dict)):
                msg_dup = f"Tag '{sfx}' sudah ada!"
                lbl_err.setText(msg_dup)
                lbl_err.show()
                dlg.adjustSize()
                self.show_toast(msg_dup)
                e_sfx.selectAll()
                e_sfx.setFocus()
                return
            lbl_err.hide()
            dlg.adjustSize()
            if tag_data:
                tag_data["suffix"] = sfx
            else:
                palette = ["#cba6f7", "#f5c2e7", "#89dceb", "#a6e3a1", "#fab387", "#f38ba8"]
                chosen_color = palette[len(cats) % len(palette)]
                cats.append({"suffix": sfx, "enabled": True, "color": chosen_color})
            self.config["custom_trap_endings"] = cats
            self.solver.set_custom_endings(cats)
            self._on_local_mode_mutated()
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

    def check_region_scanner(self):
        """Menampilkan preview posisi Area Scanner di layar tanpa menjalankan OCR."""
        area = self.config.get("screen_area")
        if not area or area.get("width", 0) <= 0 or area.get("height", 0) <= 0:
            self.show_toast("Belum ada area layar yang diatur! Klik 'Atur Area Scanner' dulu.")
            return

        l = int(area.get("left", 0))
        t = int(area.get("top", 0))
        w = int(area.get("width", 0))
        h = int(area.get("height", 0))
        self.preview_selected_area(area, title=f"AREA SCANNER ({w}x{h})", bg_color=THEME["primary"])
        self.show_toast(f"Posisi Area Scanner: {w}x{h} px (X={l}, Y={t})")

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

    def bring_to_front(self):
        """Memunculkan jendela utama saat instance kedua mencoba dijalankan."""
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self.show_toast("SAKA Overlay sudah aktif (Single-Instance)")

    def set_allow_multiple_instances(self, enabled: bool):
        self.config["allow_multiple_instances"] = bool(enabled)
        self.save_config_debounced()
        if enabled:
            if self._instance_guard is not None:
                self._instance_guard.close()
            self.show_toast("Multi-Instance diaktifkan (bisa buka >1 jendela)")
        else:
            if self._instance_guard is None:
                self._instance_guard = SingleInstanceGuard()
            self._instance_guard.start_listening(on_activate=self.bring_to_front)
            self.show_toast("Single-Instance diaktifkan (maks 1 jendela)")

    def set_auto_check_update(self, enabled: bool):
        self.config["auto_check_update_on_startup"] = bool(enabled)
        self.save_config_debounced()
        if enabled:
            self.show_toast("Notifikasi update otomatis diaktifkan")
            self.check_updates_background()
        else:
            self.show_toast("Notifikasi update otomatis dinonaktifkan")

    def restart_app(self):
        self.show_toast("Memulai ulang aplikasi...")
        if self._instance_guard is not None:
            self._instance_guard.close()
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

    def _confirm_experimental_branch(self, branch: str, action_label: str = "memilih") -> bool:
        """Menampilkan peringatan + konfirmasi jika user memilih/beralih ke branch selain 'main'."""
        if (branch or "").strip() == "main":
            return True
        reply = QMessageBox.warning(
            self,
            "Peringatan Branch Eksperimental",
            f"Branch '{branch}' adalah branch EKSPERIMENTAL (bukan rilis stabil 'main').\n\n"
            f"Pengguna umum disarankan tetap berada di branch 'main'. "
            f"Fitur di branch selain 'main' dapat belum stabil atau berubah sewaktu-waktu.\n\n"
            f"Yakin ingin {action_label} branch '{branch}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    # --- Git Updater & Branch Switcher ---
    def switch_updater_branch(self, target_branch: str):
        curr = self.updater.get_current_branch()
        if target_branch == curr:
            self.show_toast(f"Sudah berada di branch '{curr}'")
            return

        if target_branch != "main":
            reply = QMessageBox.warning(
                self,
                "Peringatan Branch Eksperimental",
                f"Branch '{target_branch}' adalah branch EKSPERIMENTAL (bukan rilis stabil 'main').\n"
                f"Pengguna umum disarankan tetap berada di branch 'main'.\n\n"
                f"Beralih dari branch '{curr}' ke branch '{target_branch}' dan unduh pembaruannya?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                combo = getattr(getattr(self, "tab_system", None), "combo_branch", None)
                if combo is not None:
                    combo.blockSignals(True)
                    idx = combo.findText(curr)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    combo.blockSignals(False)
                    self._confirmed_branch_selection = curr
                    if hasattr(self.tab_system, "update_branch_warning"):
                        self.tab_system.update_branch_warning(curr)
                return
        else:
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
        up_res = self.updater.apply_update(target_branch=target_branch)
        ok, msg = up_res if isinstance(up_res, tuple) else (bool(up_res.get("success")), up_res.get("message", ""))
        if ok:
            self._confirmed_branch_selection = target_branch
            self.config["updater_branch"] = target_branch
            self.save_config_debounced()
            self._apply_update_badge({"has_update": False})
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
            QMessageBox.critical(self, "Gagal Ganti Branch", f"Error: {msg or 'Terjadi kesalahan'}")

    def _get_selected_updater_branch(self) -> str:
        combo = getattr(getattr(self, "tab_system", None), "combo_branch", None)
        if combo is not None:
            txt = combo.currentText().strip()
            if txt:
                return txt
        return self.updater.get_current_branch()

    def on_updater_branch_selection_changed(self, branch_name: str):
        branch = (branch_name or "").strip()
        if not branch:
            return
        prev_branch = getattr(self, "_confirmed_branch_selection", "") or self.updater.get_current_branch()
        if branch != "main" and branch != prev_branch:
            if not self._confirm_experimental_branch(branch, action_label="memilih"):
                combo = getattr(getattr(self, "tab_system", None), "combo_branch", None)
                if combo is not None:
                    combo.blockSignals(True)
                    idx = combo.findText(prev_branch)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    combo.blockSignals(False)
                if hasattr(self, "tab_system") and hasattr(self.tab_system, "update_branch_warning"):
                    self.tab_system.update_branch_warning(prev_branch)
                return

        self._confirmed_branch_selection = branch
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "update_branch_warning"):
            self.tab_system.update_branch_warning(branch)
        self.config["updater_branch"] = branch
        self._last_notified_update_hash = ""
        self._apply_update_badge({"has_update": False})
        self.save_config_debounced()
        self.check_updates_background()

    def _apply_update_badge(self, res: dict):
        has_upd = bool(res and res.get("has_update"))
        branch = (res or {}).get("branch") or self._get_selected_updater_branch()
        behind = int((res or {}).get("behind_count") or 0)
        tip = f"Update baru tersedia di '{branch}' ({behind} commit)" if has_upd else ""
        if hasattr(self, "top_strip"):
            self.top_strip.set_tab_badge("system", has_upd, tip)
        if hasattr(self, "tab_system") and hasattr(self.tab_system, "set_update_available"):
            self.tab_system.set_update_available(res if has_upd else None)

    def check_updates_background(self):
        """Memeriksa update git di background thread hanya untuk branch yang dipilih."""
        if self._update_check_in_progress:
            return
        if not self.config.get("auto_check_update_on_startup", True):
            return
        if self.config.get("updater_mode", "prompt") == "disabled":
            return
        self._update_check_in_progress = True
        target_br = self._get_selected_updater_branch()

        def _worker():
            try:
                res = self.updater.check_for_updates(target_branch=target_br, is_auto_check=True)
            except Exception as exc:
                res = {"success": False, "has_update": False, "error": str(exc)}
            self._bg_update_checked.emit(res if isinstance(res, dict) else {"success": False, "has_update": False})

        threading.Thread(target=_worker, daemon=True).start()

    def _on_bg_update_checked(self, res: dict):
        self._update_check_in_progress = False
        if not res or not res.get("success"):
            return
        res_branch = (res.get("branch") or "").strip()
        selected_branch = self._get_selected_updater_branch()
        if res_branch and res_branch != selected_branch:
            return
        self._apply_update_badge(res)
        if res.get("has_update"):
            rem_hash = str(res.get("remote_hash") or "")
            behind = int(res.get("behind_count") or 1)
            branch = res_branch or selected_branch
            if rem_hash != self._last_notified_update_hash:
                self._last_notified_update_hash = rem_hash
                self.show_toast(f"Update baru di '{branch}' ({behind} commit). Cek tab SYSTEM.", 4500)

    def apply_detected_update(self, target_branch: str):
        self.show_toast("Menerapkan pembaruan...")
        up_res = self.updater.apply_update(target_branch=target_branch)
        ok, msg = up_res if isinstance(up_res, tuple) else (bool(up_res.get("success")), up_res.get("message", ""))
        if ok:
            self._apply_update_badge({"has_update": False})
            self.tab_system.refresh_git_info()
            r_rep = QMessageBox.question(
                self,
                "Berhasil Diperbarui",
                f"{msg}\n\nRestart aplikasi sekarang?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if r_rep == QMessageBox.Yes:
                self.restart_app()
        else:
            QMessageBox.critical(self, "Gagal Update", msg or "Error")

    def check_updates(self):
        curr_branch = self.updater.get_current_branch()
        target_branch = getattr(self.tab_system, "combo_branch", None)
        tb = target_branch.currentText().strip() if target_branch else curr_branch

        btn_upd = getattr(self.tab_system, "btn_check_update", None)
        if btn_upd is not None:
            btn_upd.setEnabled(False)
            btn_upd.setText(f" Mengecek '{tb}'...")
        self.show_toast(f"Mengecek update di '{tb}'...")
        QApplication.processEvents()

        try:
            res = self.updater.check_for_updates(target_branch=tb)
        finally:
            if btn_upd is not None:
                btn_upd.setText(" Cek Update")
                btn_upd.setEnabled(True)
        if not res.get("success"):
            QMessageBox.warning(self, "Cek Update", f"Gagal: {res.get('error') or res.get('message', 'Tidak ada koneksi internet')}")
            return

        self._apply_update_badge(res)

        if res.get("has_update"):
            behind = res.get("behind_count", res.get("behind_by", 1))
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
                self.apply_detected_update(tb)
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
    def _confirm_sort_tags(self, desc: str) -> bool:
        reply = QMessageBox.question(
            self,
            "Konfirmasi Urutkan Semua",
            f"Urutkan ulang semua tag berdasarkan {desc}?\n\nSusunan manual Anda saat ini akan tertimpa.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes

    def on_sort_custom_categories_az(self):
        if not self._confirm_sort_tags("A-Z"):
            return
        cats = self.config.get("custom_trap_endings", [])
        cats.sort(key=lambda c: c.get("suffix", "").upper())
        self._after_sort_tags(cats, "A-Z")

    def on_sort_custom_categories_count(self, reverse=True):
        txt = "Kata Terbanyak" if reverse else "Kata Terdikit"
        if not self._confirm_sort_tags(txt):
            return
        cats = self.config.get("custom_trap_endings", [])
        cats.sort(key=lambda c: self.solver.count_words_by_suffix(c.get("suffix", "")), reverse=reverse)
        self._after_sort_tags(cats, txt)

    def on_sort_custom_categories_length(self, reverse=True):
        txt = "Huruf Terpanjang" if reverse else "Huruf Terpendek"
        if not self._confirm_sort_tags(txt):
            return
        cats = self.config.get("custom_trap_endings", [])
        cats.sort(key=lambda c: (len(c.get("suffix", "")), c.get("suffix", "").upper()), reverse=reverse)
        self._after_sort_tags(cats, txt)

    def _after_sort_tags(self, cats, desc):
        self.config["custom_trap_endings"] = cats
        self.solver.set_custom_endings(cats)
        self._on_local_mode_mutated()
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
        if hasattr(self, "_mode_sync_timer") and self._mode_sync_timer.isActive():
            self._mode_sync_timer.stop()
            self._flush_local_mode_to_db()
        if hasattr(self, "sync_manager"):
            self.sync_manager.stop()
        if getattr(self, "_instance_guard", None) is not None:
            self._instance_guard.close()
        save_config(self.config)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(GLOBAL_QSS)

    cfg = load_config()
    guard = None
    if not cfg.get("allow_multiple_instances", False):
        guard = SingleInstanceGuard()
        if guard.try_notify_existing():
            sys.exit(0)
        guard.start_listening()

    window = SambungKataQtApp(instance_guard=guard)
    if guard is not None:
        guard._on_activate = window.bring_to_front
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
