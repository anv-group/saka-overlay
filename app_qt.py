import sys
import os
import time
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QDialog, QLineEdit,
    QColorDialog, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap

from qt_theme import THEME, GLOBAL_QSS, get_qicon
from qt_components import QtTopTabStrip, QtMiniTickerBar
from tab_views_qt import QtLiveTabView, QtTagsTabView, QtDictionaryTabView, QtSystemTabView

from config import load_config, save_config
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SAKA Overlay")
        self.resize(440, 720)
        self.setMinimumSize(380, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        # Pasang Icon Window
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ico_path = os.path.join(base_dir, "assets", "logo.ico")
        if os.path.exists(ico_path):
            self.setWindowIcon(QIcon(ico_path))

        # 1. Load Backend Engines
        self.config = load_config()
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
        self.is_scanning = False
        self._save_timer = None
        self._dirty_live = False

        # 2. Setup Central Widget & Layout
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Top Navigation Strip
        self.top_strip = QtTopTabStrip()
        self.top_strip.tab_changed.connect(self._on_tab_changed)
        self.main_layout.addWidget(self.top_strip)

        # Mini Ticker Bar
        self.mini_ticker = QtMiniTickerBar()
        self.mini_ticker.clicked.connect(lambda: self.top_strip.select_tab("live"))
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

        # Toast Message Bar
        self.toast_frame = QFrame()
        self.toast_frame.setFixedHeight(28)
        self.toast_frame.setStyleSheet(f"background-color: {THEME['border_focus']}; border-top: 1px solid {THEME['primary']};")
        tf_layout = QHBoxLayout(self.toast_frame)
        tf_layout.setContentsMargins(10, 0, 10, 0)
        self.lbl_toast = QLabel("")
        self.lbl_toast.setStyleSheet(f"color: {THEME['text_primary']}; font-size: 11px; font-weight: 500;")
        tf_layout.addWidget(self.lbl_toast)
        self.toast_frame.hide()
        self.main_layout.addWidget(self.toast_frame)

        # 3. Connect Signals
        self.tab_live.start_stop_clicked.connect(self.toggle_scan)
        self.tab_live.mode_changed.connect(self.set_game_mode)
        self.tab_live.search_text_changed.connect(self.on_manual_search)
        self.tab_live.sort_mode_toggled.connect(self.toggle_tier0_sort)

        # Initial populate
        self.tab_live.refresh_quick_tags(self.config.get("custom_trap_endings", []))
        self.tab_live.mode_pills.set_mode(self.config.get("game_mode", "default"))

        # Setup Scan Worker
        self.scan_worker = ScanWorker(self.ocr, lambda: self.config.get("scan_interval_sec", 0.08))
        self.scan_worker.result_ready.connect(self._on_scan_result)

        # Global Hotkey F2 (manual flag detection)
        try:
            import keyboard
            keyboard.add_hotkey("F2", self._on_f2_hotkey)
        except Exception:
            pass

    # --- Scanning & Vision Control ---
    def toggle_scan(self):
        if not self.is_scanning:
            self.is_scanning = True
            self.tab_live.set_scanning_state(True)
            self.scan_worker.start()
            self.show_toast("Live OCR Scanner dimulai")
        else:
            self.is_scanning = False
            self.tab_live.set_scanning_state(False)
            self.scan_worker.stop()
            self.show_toast("Live OCR Scanner dihentikan")

    def _on_scan_result(self, res_data: dict):
        text = res_data.get("text", "").strip()
        conf = res_data.get("confidence", 1.0)
        if text and text != self.last_detected_word:
            self.last_detected_word = text
            self.update_results(text, int(conf * 100))

    def on_manual_search(self, query: str):
        q = "".join([c for c in query.upper() if c.isalpha()])
        if q:
            self.update_results(q, 100)
        elif self.last_detected_word:
            self.update_results(self.last_detected_word, 100)
        else:
            self.tab_live.update_results("", [], 100)

    def update_results(self, prefix: str, conf_pct: int = 100):
        if not prefix:
            self.tab_live.update_results("", [], 100)
            self.mini_ticker.update_ticker("", "")
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

        top_word = words[0]["kata"] if words else ""
        self.mini_ticker.update_ticker(prefix, top_word)

        if self.top_strip.active_tab == "live":
            self.tab_live.update_results(prefix, words, conf_pct)
        else:
            self._dirty_live = True

    # --- Navigation & Tabs ---
    def _on_tab_changed(self, tab_id: str):
        tab_map = {"live": 0, "tags": 1, "kamus": 2, "system": 3}
        idx = tab_map.get(tab_id, 0)
        self.stack.setCurrentIndex(idx)

        if tab_id == "live":
            self.mini_ticker.hide()
            if self._dirty_live:
                if self.last_detected_word:
                    self.update_results(self.last_detected_word, 100)
                self._dirty_live = False
        else:
            self.mini_ticker.show()

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
            self.save_config_debounced()
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
        if suffix in b_tags:
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

        self.tab_tags.refresh_brutal_list()

    def set_game_mode(self, mode: str):
        self.config["game_mode"] = mode
        self.save_config_debounced()

        cats = self.config.get("custom_trap_endings", [])
        if mode == "santai":
            disabled = []
            for c in cats:
                if any(ch in c.get("suffix", "").lower() for ch in ("x", "q", "f")):
                    if c.get("enabled", True):
                        c["enabled"] = False
                        disabled.append(c.get("suffix", "").upper())
            self.config["santai_auto_disabled_tags"] = disabled
        elif mode == "brutal":
            b_tags = set(self.config.get("brutal_mode_tags", ["AMSI", "KSO", "RHU", "TL", "BD"]))
            for c in cats:
                c["enabled"] = (c.get("suffix", "").upper() in b_tags)

        self.config["custom_trap_endings"] = cats
        self.solver.set_custom_endings(cats)
        self.tab_live.refresh_quick_tags(cats)
        if self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast(f"Mode permainan diubah ke {mode.upper()}")

    def toggle_tier0_sort(self):
        curr = self.config.get("tier0_sort_mode", "default")
        nxt = "tag_order" if curr == "default" else "default"
        self.config["tier0_sort_mode"] = nxt
        self.save_config_debounced()
        self.tab_live.btn_sort.setText(f" {nxt.upper()}")
        if self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast(f"Mode sortir Tier 0: {nxt.upper()}")

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

    def open_edit_tag_dialog(self, tag_data: dict = None):
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Tag Akhiran" if tag_data else "Tambah Tag Baru")
        dlg.setFixedSize(320, 200)
        d_layout = QVBoxLayout(dlg)
        d_layout.setContentsMargins(14, 14, 14, 14)
        d_layout.setSpacing(10)

        d_layout.addWidget(QLabel("Huruf Akhiran (Suffix):"))
        e_sfx = QLineEdit(tag_data.get("suffix", "") if tag_data else "")
        d_layout.addWidget(e_sfx)

        d_layout.addWidget(QLabel("Nama / Label Tag:"))
        e_name = QLineEdit(tag_data.get("name", "") if tag_data else "")
        d_layout.addWidget(e_name)

        btn_save = QPushButton("Simpan")
        btn_save.setStyleSheet(f"background-color: {THEME['primary']}; color: {THEME['text_dark']}; font-weight: bold;")

        def _do_save():
            sfx = e_sfx.text().strip().upper()
            name = e_name.text().strip() or f"Akhiran {sfx}"
            if not sfx:
                return
            cats = self.config.get("custom_trap_endings", [])
            if tag_data:
                tag_data["suffix"] = sfx
                tag_data["name"] = name
            else:
                cats.append({"suffix": sfx, "name": name, "enabled": True, "color": THEME["primary"]})
            self.config["custom_trap_endings"] = cats
            self.solver.set_custom_endings(cats)
            self.save_config_debounced()
            self.tab_tags.refresh_custom_list()
            self.tab_live.refresh_quick_tags(cats)
            dlg.accept()

        btn_save.clicked.connect(_do_save)
        d_layout.addWidget(btn_save)
        dlg.exec()

    def open_region_selector(self):
        from region_selector import RegionSelector
        def _on_selected(area):
            if area:
                self.config["screen_area"] = area
                self.ocr.set_screen_area(area)
                self.save_config_debounced()
                self.show_toast("Area ROI berhasil disimpan!")
        rs = RegionSelector(on_selected_callback=_on_selected)
        rs.start()

    def check_updates(self):
        self.show_toast("Sedang memeriksa pembaruan...")
        res = self.updater.check_for_updates()
        if res.get("has_update"):
            QMessageBox.information(self, "Pembaruan", f"Pembaruan tersedia! {res.get('behind_by', 1)} commit baru.")
        else:
            QMessageBox.information(self, "Pembaruan", "Aplikasi Anda sudah versi terbaru!")

    def _on_f2_hotkey(self):
        try:
            saved = self.ocr.save_false_detection(self.last_detected_word)
            if saved:
                self.show_toast(f"🚩 Sampel F2 tersimpan: {os.path.basename(saved)}")
        except Exception as e:
            pass

    # --- Sorting tags ---
    def on_sort_custom_categories_az(self):
        cats = self.config.get("custom_trap_endings", [])
        cats.sort(key=lambda c: c.get("suffix", "").upper())
        self._after_sort_tags(cats, "A-Z")

    def on_sort_custom_categories_count(self):
        cats = self.config.get("custom_trap_endings", [])
        cats.sort(key=lambda c: self.solver.count_words_by_suffix(c.get("suffix", "")), reverse=True)
        self._after_sort_tags(cats, "kata terbanyak")

    def on_sort_custom_categories_length(self, reverse=True):
        cats = self.config.get("custom_trap_endings", [])
        cats.sort(key=lambda c: (len(c.get("suffix", "")), c.get("suffix", "").upper()), reverse=reverse)
        txt = "terpanjang" if reverse else "tersedikit"
        self._after_sort_tags(cats, f"huruf {txt}")

    def _after_sort_tags(self, cats, desc):
        self.config["custom_trap_endings"] = cats
        self.solver.set_custom_endings(cats)
        self.save_config_debounced()
        self.tab_tags.refresh_custom_list()
        self.tab_live.refresh_quick_tags(cats)
        if self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast(f"Tag diurutkan berdasarkan {desc}")

    # --- Toast & Config Helpers ---
    def show_toast(self, message: str, duration_ms: int = 2500):
        self.lbl_toast.setText(message)
        self.toast_frame.show()
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
