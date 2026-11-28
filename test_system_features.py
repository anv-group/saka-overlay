import io
import json
import os
import tempfile
import threading
import time
import unittest
from unittest import mock
import zipfile

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

import config as cfg_mod
from app_qt import SingleInstanceGuard, SambungKataQtApp
from qt_components import QtTopTabStrip
from tab_views_qt import (
    QtBrutalRowWidget,
    QtCustomTagRowWidget,
    QtDictionaryTabView,
    QtSystemTabView,
    QtTagsTabView,
    _format_tag_count_text,
)
from updater import GitUpdater


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

    def test_explorer_source_filters_checkbox_behavior(self):
        class DummySolver:
            def __init__(self):
                self.whitelisted_words = set()
                self.blacklisted_words = set()
                self.storage_mode = "txt"
                self.last_source_filter = None
            def search_dictionary(self, query="", search_type="prefix", source_filter="all", limit=40, sort_by="default"):
                self.last_source_filter = source_filter
                return [{"word": "baja", "status": "KBBI", "datetime": "", "added_by": ""}], 1
            def get_word_datetime(self, word, scope="auto"):
                return ""

        class DummyApp:
            def __init__(self):
                self.config = {
                    "dict_filter_exclusive": False,
                    "custom_trap_endings": [],
                    "last_dict_sub_tab": "explorer",
                }
                self.solver = DummySolver()
            def __getattr__(self, name):
                return lambda *a, **kw: None

        dummy = DummyApp()
        dict_view = QtDictionaryTabView(dummy)

        # Default: semua aktif
        self.assertTrue(dict_view.btn_src_all.isChecked())
        self.assertTrue(dict_view.btn_src_kbbi.isChecked())
        self.assertTrue(dict_view.btn_src_contek.isChecked())
        self.assertTrue(dict_view.btn_src_custom.isChecked())
        self.assertFalse(hasattr(dict_view, "btn_src_both"))

        # Matikan KBBI -> Semua ikut mati, sisanya tetap aktif
        dict_view.edit_exp_search.setText("ba")
        dict_view.btn_src_kbbi.click()
        self.assertFalse(dict_view.btn_src_all.isChecked())
        self.assertFalse(dict_view.btn_src_kbbi.isChecked())
        self.assertTrue(dict_view.btn_src_contek.isChecked())
        self.assertTrue(dict_view.btn_src_custom.isChecked())
        self.assertEqual(set(dummy.solver.last_source_filter), {"contek", "custom"})

        # Nyalakan KBBI, matikan Kamus+ -> KBBI + Contek Inklusif = ["kbbi", "contek"]
        dict_view.btn_src_kbbi.click()
        dict_view.btn_src_custom.click()
        self.assertEqual(set(dummy.solver.last_source_filter), {"kbbi", "contek"})

        # Aktifkan Eksklusif saat KBBI + Contek sama-sama aktif -> hanya irisan ["both"]
        dict_view.btn_mode_toggle.click()
        self.assertEqual(dummy.solver.last_source_filter, ["both"])

        # Kembali ke Inklusif lalu klik Semua saat tidak penuh -> aktifkan semua kembali
        dict_view.btn_mode_toggle.click()
        dict_view.btn_src_all.click()
        self.assertTrue(dict_view.btn_src_all.isChecked())
        self.assertEqual(dummy.solver.last_source_filter, "all")

        # Klik Semua saat semua aktif -> nonaktifkan semua
        dict_view.btn_src_all.click()
        self.assertFalse(dict_view.btn_src_all.isChecked())
        self.assertEqual(dict_view.selected_sources, set())
        self.assertEqual(dict_view.lbl_exp_status.text(), "0 kata")

    def test_tag_count_formatting_and_prefix_suffix_sort(self):
        self.assertEqual(_format_tag_count_text(12, 5, True, False), "(12 akhiran)")
        self.assertEqual(_format_tag_count_text(12, 5, False, True), "(5 awalan)")
        self.assertEqual(_format_tag_count_text(12, 5, True, True), "(12 akhiran · 5 awalan)")
        self.assertEqual(_format_tag_count_text(12, 5, False, False), "")

        class DummySolver:
            def count_words_by_suffix(self, s):
                return {"NS": 10, "MP": 30}.get(s, 0)
            def count_words_by_prefix(self, p):
                return {"NS": 2, "MP": 1}.get(p, 0)
            def set_custom_endings(self, cats):
                pass

        class DummyApp:
            def __init__(self):
                self.config = {
                    "custom_trap_endings": [
                        {"suffix": "NS", "enabled": True, "color": "#cba6f7"},
                        {"suffix": "MP", "enabled": True, "color": "#89dceb"},
                    ]
                }
                self.solver = DummySolver()
                self.last_detected_word = ""
                self.tab_tags = mock.MagicMock()
                self.tab_live = mock.MagicMock()
            def _confirm_sort_tags(self, txt):
                return True
            def _on_local_mode_mutated(self):
                pass
            def _after_sort_tags(self, cats, desc):
                return SambungKataQtApp._after_sort_tags(self, cats, desc)
            def show_toast(self, msg, duration_ms=2500):
                pass

        d_app = DummyApp()
        SambungKataQtApp.on_sort_custom_categories_count(d_app, reverse=True, count_type="suffix")
        self.assertEqual([c["suffix"] for c in d_app.config["custom_trap_endings"]], ["MP", "NS"])

        SambungKataQtApp.on_sort_custom_categories_count(d_app, reverse=True, count_type="prefix")
        self.assertEqual([c["suffix"] for c in d_app.config["custom_trap_endings"]], ["NS", "MP"])

    def test_mode_tab_tag_search_filters_kelola_and_brutal(self):
        class DummySolver:
            def count_words_by_suffix(self, s): return 5
            def count_words_by_prefix(self, p): return 2

        class DummyApp:
            def __init__(self):
                self.config = {
                    "custom_trap_endings": [
                        {"suffix": "NS", "enabled": True, "color": "#cba6f7"},
                        {"suffix": "AMSI", "enabled": True, "color": "#f9e2af"},
                        {"suffix": "KSO", "enabled": False, "color": "#a6e3a1"},
                    ],
                    "brutal_mode_tags": ["AMSI", "KSO"],
                    "show_tag_suffix_count": True,
                    "show_tag_prefix_count": False,
                }
                self.solver = DummySolver()
            def __getattr__(self, name):
                return lambda *a, **kw: None

        tags_view = QtTagsTabView(DummyApp())
        tags_view.edit_tag_search.setText("am")

        custom_rows = [
            tags_view.layout_custom_items.itemAt(i).widget()
            for i in range(tags_view.layout_custom_items.count())
            if isinstance(tags_view.layout_custom_items.itemAt(i).widget(), QtCustomTagRowWidget)
        ]
        self.assertEqual([r.sfx for r in custom_rows], ["AMSI"])
        self.assertEqual(custom_rows[0].idx, 1)

        tags_view.sub_strip.select_sub_tab("brutal")
        brutal_rows = [
            tags_view.layout_brutal_items.itemAt(i).widget()
            for i in range(tags_view.layout_brutal_items.count())
            if isinstance(tags_view.layout_brutal_items.itemAt(i).widget(), QtBrutalRowWidget)
        ]
        self.assertEqual([r.sfx for r in brutal_rows], ["AMSI"])
        self.assertEqual(brutal_rows[0].idx, 1)

    def test_csv_local_stats_refresh_on_dictionary_mutations(self):
        class DummySolver:
            def __init__(self):
                self.whitelisted_words = {"awal"}
                self.blacklisted_words = {"blok"}
                self.base_custom_set = {"kustom"}
                self.db_custom_set = set()
                self.storage_mode = "txt"
            def unwhitelist_word(self, w):
                self.whitelisted_words.discard(w)
            def blacklist_word(self, w):
                self.blacklisted_words.add(w)
                return True
            def search_dictionary(self, **kw):
                return [], 0

        class DummyUpdater:
            def get_current_branch(self): return "main"
            def get_available_branches(self): return ["main"]
            def get_current_commit(self): return {"hash": "abc1234", "message": "init"}

        class DummyApp:
            def __init__(self):
                self.config = {"storage_mode": "txt", "hotkeys": dict(cfg_mod.DEFAULT_HOTKEYS), "custom_trap_endings": []}
                self.solver = DummySolver()
                self.updater = DummyUpdater()
                self.always_on_top = True
                self.last_detected_word = ""
                self.tab_system = None
            def __getattr__(self, name):
                return lambda *a, **kw: None

        d_app = DummyApp()
        sys_view = QtSystemTabView(d_app)
        d_app.tab_system = sys_view
        dict_view = QtDictionaryTabView(d_app)

        sys_view.refresh_db_stats()
        self.assertEqual(sys_view.lbl_stat_wl_val.text(), "1")
        self.assertEqual(sys_view.lbl_stat_bl_val.text(), "1")
        self.assertEqual(sys_view.lbl_stat_cm_val.text(), "1")

        dict_view._remove_wl_word("awal")
        dict_view._toggle_exp_blocklist("baru")
        self.assertEqual(sys_view.lbl_stat_wl_val.text(), "0")
        self.assertEqual(sys_view.lbl_stat_bl_val.text(), "2")


class _FakeResp:
    def __init__(self, status_code=200, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_data
        self._content = content
        self.headers = headers or {}

    def json(self):
        return self._json

    def iter_content(self, chunk_size=65536):
        if self._content:
            yield self._content


class TestNonGitHttpsUpdater(unittest.TestCase):
    @staticmethod
    def _build_zip_bytes(files_map, comment_sha="1111222233334444555566667777888899990000"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for rel, content in files_map.items():
                zf.writestr(rel, content)
            zf.comment = comment_sha.encode("utf-8")
        return buf.getvalue()

    def test_mode_detection_and_untracked_auto_vs_manual_check(self):
        with tempfile.TemporaryDirectory() as td:
            upd = GitUpdater(repo_dir=td, github_repo="anv-group/sambung-kata-overlay")
            with mock.patch("updater.shutil.which", return_value=None):
                self.assertEqual(upd.get_updater_mode(), "https")
                self.assertEqual(upd.get_current_commit()["hash"], "unknown")

                # Auto-check startup pada fresh Download ZIP tidak boleh memicu update
                auto_res = upd.check_for_updates(target_branch="main", is_auto_check=True)
                self.assertTrue(auto_res["success"])
                self.assertFalse(auto_res["has_update"])
                self.assertTrue(auto_res["is_version_untracked"])

                # Manual check mengambil commit terbaru dari GitHub API
                commits_payload = [
                    {
                        "sha": "abcdef1234567890",
                        "commit": {
                            "author": {"name": "alden", "date": "2026-11-28T10:00:00Z"},
                            "message": "feat: non-git updater\n\ndetails",
                        },
                    }
                ]
                with mock.patch("updater.requests.get", return_value=_FakeResp(200, commits_payload)):
                    manual_res = upd.check_for_updates(target_branch="main", is_auto_check=False)
                self.assertTrue(manual_res["success"])
                self.assertTrue(manual_res["has_update"])
                self.assertEqual(manual_res["remote_hash"], "abcdef1")
                self.assertEqual(manual_res["commits"][0]["message"], "feat: non-git updater")

    def test_apply_update_preserves_user_files_and_seeds_missing_lists(self):
        with tempfile.TemporaryDirectory() as td:
            # Siapkan file lokal user yang wajib dilindungi
            with open(os.path.join(td, "config.json"), "w", encoding="utf-8") as f:
                json.dump({"supabase_url": "https://secret.supabase.co"}, f)
            with open(os.path.join(td, "whitelist.csv"), "w", encoding="utf-8") as f:
                f.write("word,datetime\nkatapribadi,\n")
            with open(os.path.join(td, "kamus_custom.csv"), "w", encoding="utf-8") as f:
                f.write("word,datetime\nkatacustom,\n")

            zip_bytes = self._build_zip_bytes(
                {
                    "sambung-kata-overlay-main/app_qt.py": "# updated\n",
                    "sambung-kata-overlay-main/config.json": '{"supabase_url": ""}',
                    "sambung-kata-overlay-main/whitelist.csv": "word,datetime\ngithubword,\n",
                    "sambung-kata-overlay-main/blacklist.csv": "word,datetime\nbadword,\n",
                    "sambung-kata-overlay-main/kamus_custom.csv": "word,datetime\noverwrite,\n",
                },
                comment_sha="deadbeef1234567890abcdef1234567890abcdef",
            )

            def _fake_get(url, **kwargs):
                if "codeload.github.com" in url:
                    return _FakeResp(200, content=zip_bytes)
                # Simulasikan API commits gagal/rate-limit -> fallback ke ZipFile.comment SHA!
                return _FakeResp(403, headers={"X-RateLimit-Remaining": "0"})

            upd = GitUpdater(repo_dir=td, github_repo="anv-group/sambung-kata-overlay")
            with mock.patch("updater.shutil.which", return_value=None), mock.patch("updater.requests.get", side_effect=_fake_get):
                ok, msg = upd.apply_update(target_branch="main")

            self.assertTrue(ok, msg)
            self.assertIn("Non-Git", msg)
            with open(os.path.join(td, "app_qt.py"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "# updated\n")
            with open(os.path.join(td, "config.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["supabase_url"], "https://secret.supabase.co")
            with open(os.path.join(td, "whitelist.csv"), encoding="utf-8") as f:
                self.assertIn("katapribadi", f.read())
            # blacklist.csv belum ada sebelumnya -> harus dibuat dari ZIP
            with open(os.path.join(td, "blacklist.csv"), encoding="utf-8") as f:
                self.assertIn("badword", f.read())
            with open(os.path.join(td, "kamus_custom.csv"), encoding="utf-8") as f:
                self.assertIn("katacustom", f.read())

            curr = upd.get_current_commit()
            self.assertEqual(curr["hash"], "deadbee")
            self.assertTrue(curr["is_non_git"])

    def test_apply_update_rejects_zip_slip_and_reports_rate_limit(self):
        with tempfile.TemporaryDirectory() as td:
            bad_zip = self._build_zip_bytes({"../../evil.txt": "pwned"})
            upd = GitUpdater(repo_dir=td, github_repo="anv-group/sambung-kata-overlay")

            with mock.patch("updater.shutil.which", return_value=None):
                with mock.patch("updater.requests.get", return_value=_FakeResp(200, content=bad_zip)):
                    ok, msg = upd.apply_update(target_branch="main")
                self.assertFalse(ok)
                self.assertIn("tidak aman", msg.lower())

                upd._save_state({"branch": "main", "hash": "abc1234", "full_hash": "abc1234"})
                rate_resp = _FakeResp(403, headers={"X-RateLimit-Remaining": "0"})
                with mock.patch("updater.requests.get", return_value=rate_resp):
                    res = upd.check_for_updates(target_branch="main")
                self.assertFalse(res["success"])
                self.assertIn("rate limit", res["error"].lower())


if __name__ == "__main__":
    unittest.main()
