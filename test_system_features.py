import os
import threading
import time
import unittest

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

import config as cfg_mod
from app_qt import SingleInstanceGuard, SambungKataQtApp
from qt_components import QtTopTabStrip
from tab_views_qt import QtSystemTabView


class TestSystemFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_single_instance_default_config_and_guard(self):
        self.assertFalse(cfg_mod.DEFAULT_CONFIG.get("allow_multiple_instances", True))

        activated = []
        guard1 = SingleInstanceGuard(server_name=f"test-saka-{os.getpid()}-{id(self)}")
        guard2 = SingleInstanceGuard(server_name=guard1.server_name)
        try:
            self.assertFalse(guard2.try_notify_existing(timeout_ms=100))
            self.assertTrue(guard1.start_listening(on_activate=lambda: activated.append(True)))

            notified = []
            t = threading.Thread(
                target=lambda: notified.append(guard2.try_notify_existing(timeout_ms=500)),
                daemon=True,
            )
            t.start()
            deadline = time.time() + 2.0
            while t.is_alive() or (not activated and time.time() < deadline):
                QCoreApplication.processEvents()
                time.sleep(0.01)
            t.join(timeout=1.0)

            self.assertEqual(notified, [True])
            self.assertTrue(len(activated) >= 1)
        finally:
            guard1.close()
            guard2.close()

    def test_top_tab_strip_badge_and_system_update_banner(self):
        strip = QtTopTabStrip()
        self.assertFalse(strip.badges.get("system", True))

        strip.set_tab_badge("system", True, "Update baru di main")
        self.assertTrue(strip.badges["system"])
        self.assertEqual(strip.buttons["system"].text(), " SYSTEM")
        self.assertNotIn("(!)", strip.buttons["system"].text())
        self.assertIn("Update baru", strip.buttons["system"].toolTip())
        self.assertFalse(strip.buttons["system"].icon().isNull())

        strip.set_tab_badge("system", False, "")
        self.assertFalse(strip.badges["system"])
        self.assertEqual(strip.buttons["system"].text(), " SYSTEM")

    def test_system_tab_view_update_banner_and_bg_notifier(self):
        class DummyUpdater:
            def get_current_branch(self):
                return "main"
            def get_available_branches(self):
                return ["main", "dev"]
            def get_current_commit(self):
                return {"hash": "abc1234", "message": "init"}

        class DummyApp:
            def __init__(self):
                self.config = {
                    "scan_interval_sec": 0.08,
                    "always_on_top": True,
                    "two_tone_text": True,
                    "dev_mode": False,
                    "allow_multiple_instances": False,
                    "auto_check_update_on_startup": True,
                    "storage_mode": "txt",
                    "hotkeys": dict(cfg_mod.DEFAULT_HOTKEYS),
                }
                self.updater = DummyUpdater()
                self.always_on_top = True
                self.top_strip = QtTopTabStrip()
                self.toasts = []
                self._last_notified_update_hash = ""
                self._update_check_in_progress = False
                self.tab_system = None
            def show_toast(self, m, duration_ms=2500):
                self.toasts.append(m)
            def set_allow_multiple_instances(self, v):
                self.config["allow_multiple_instances"] = bool(v)
            def set_auto_check_update(self, v):
                self.config["auto_check_update_on_startup"] = bool(v)
            def __getattr__(self, name):
                return lambda *a, **kw: None

        dummy = DummyApp()
        sys_view = QtSystemTabView(dummy)
        dummy.tab_system = sys_view
        dummy._get_selected_updater_branch = lambda: sys_view.combo_branch.currentText().strip() or "main"

        self.assertFalse(sys_view.chk_multi_instance.isChecked())
        self.assertTrue(sys_view.chk_auto_update_notif.isChecked())
        self.assertTrue(sys_view.update_banner.isHidden())

        # Result untuk branch lain harus diabaikan (hanya branch yang dipilih)
        other_res = {
            "success": True,
            "has_update": True,
            "behind_count": 3,
            "branch": "dev",
            "remote_hash": "999aaaa",
            "commits": [{"hash": "999aaaa", "message": "dev commit"}],
        }
        SambungKataQtApp._on_bg_update_checked(dummy, other_res)
        self.assertTrue(sys_view.update_banner.isHidden())
        self.assertFalse(dummy.top_strip.badges["system"])
        self.assertEqual(len(dummy.toasts), 0)

        res = {
            "success": True,
            "has_update": True,
            "behind_count": 2,
            "branch": "main",
            "remote_hash": "def5678",
            "commits": [{"hash": "def5678", "message": "fix something"}],
        }
        SambungKataQtApp._apply_update_badge(dummy, res)
        SambungKataQtApp._on_bg_update_checked(dummy, res)

        self.assertFalse(sys_view.update_banner.isHidden())
        self.assertIn("2 commit baru", sys_view.lbl_update_banner.text())
        self.assertTrue(dummy.top_strip.badges["system"])
        self.assertEqual(len(dummy.toasts), 1)

        # Dedup notification for same remote_hash
        SambungKataQtApp._on_bg_update_checked(dummy, res)
        self.assertEqual(len(dummy.toasts), 1)

        # Clear badge & banner when no update
        SambungKataQtApp._apply_update_badge(dummy, {"success": True, "has_update": False})
        self.assertTrue(sys_view.update_banner.isHidden())
        self.assertFalse(dummy.top_strip.badges["system"])

    def test_experimental_branch_warning_and_revert_on_cancel(self):
        class DummyUpdater:
            def get_current_branch(self): return "main"
            def get_available_branches(self): return ["main", "dev"]
            def get_current_commit(self): return {"hash": "abc1234", "message": "init"}

        class DummyApp:
            def __init__(self):
                self.config = {
                    "scan_interval_sec": 0.08,
                    "always_on_top": True,
                    "two_tone_text": True,
                    "dev_mode": False,
                    "allow_multiple_instances": False,
                    "auto_check_update_on_startup": True,
                    "storage_mode": "txt",
                    "updater_branch": "main",
                    "hotkeys": dict(cfg_mod.DEFAULT_HOTKEYS),
                }
                self.updater = DummyUpdater()
                self.always_on_top = True
                self.top_strip = QtTopTabStrip()
                self._confirmed_branch_selection = "main"
                self._last_notified_update_hash = ""
                self._update_check_in_progress = False
                self.tab_system = None
                self.bg_calls = 0
            def _confirm_experimental_branch(self, branch, action_label="memilih"):
                return branch == "main"
            def _apply_update_badge(self, res):
                pass
            def check_updates_background(self):
                self.bg_calls += 1
            def __getattr__(self, name):
                return lambda *a, **kw: None

        dummy = DummyApp()
        sys_view = QtSystemTabView(dummy)
        dummy.tab_system = sys_view

        # Default main -> warning hidden
        self.assertTrue(sys_view.lbl_branch_exp_warning.isHidden())

        # Selecting 'dev' and declining confirmation reverts back to 'main'
        sys_view.combo_branch.setCurrentText("dev")
        SambungKataQtApp.on_updater_branch_selection_changed(dummy, "dev")
        self.assertEqual(sys_view.combo_branch.currentText(), "main")
        self.assertEqual(dummy.config["updater_branch"], "main")
        self.assertTrue(sys_view.lbl_branch_exp_warning.isHidden())

        # Confirmed experimental branch shows warning banner
        sys_view.update_branch_warning("dev")
        self.assertFalse(sys_view.lbl_branch_exp_warning.isHidden())
        self.assertIn("dev", sys_view.lbl_branch_exp_warning.text())


if __name__ == "__main__":
    unittest.main()
