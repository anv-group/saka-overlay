import json
import os
import tempfile
import unittest

from db_sync import (
    DbCacheStore,
    PermanentSyncError,
    SettingsTableUnavailableError,
    SupabaseRestClient,
    SupabaseSyncManager,
    apply_presence_event,
    build_realtime_ws_url,
    decode_invite_config,
    encode_invite_config,
    normalize_supabase_url,
    parse_realtime_postgres_change,
    parse_realtime_table_change,
)
import config as cfg_mod
from solver import SambungKataSolver


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text or (json.dumps(json_data) if json_data is not None else "")

    def json(self):
        return self._json


class _FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url, headers, None))
        return self.handler("GET", url, headers, None)

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("POST", url, headers, json))
        return self.handler("POST", url, headers, json)

    def delete(self, url, headers=None, timeout=None):
        self.calls.append(("DELETE", url, headers, None))
        return self.handler("DELETE", url, headers, None)


class TestDbSyncHelpers(unittest.TestCase):
    def test_url_and_ws_builders(self):
        self.assertEqual(normalize_supabase_url(" https://abc.supabase.co/ "), "https://abc.supabase.co")
        ws = build_realtime_ws_url("https://abc.supabase.co/", "my-key")
        self.assertEqual(ws, "wss://abc.supabase.co/realtime/v1/websocket?apikey=my-key&vsn=1.0.0")
        with self.assertRaises(ValueError):
            normalize_supabase_url("ftp://invalid.example.com")

    def test_invite_config_roundtrip_and_errors(self):
        token = encode_invite_config("https://proj.supabase.co/", "anon-secret-123")
        self.assertTrue(token.startswith("saka-db://"))
        url, key = decode_invite_config(token)
        self.assertEqual(url, "https://proj.supabase.co")
        self.assertEqual(key, "anon-secret-123")

        # Raw JSON fallback
        url2, key2 = decode_invite_config('{"url": "https://proj2.supabase.co", "key": "k2"}')
        self.assertEqual(url2, "https://proj2.supabase.co")
        self.assertEqual(key2, "k2")

        with self.assertRaises(ValueError):
            decode_invite_config("not-a-valid-token")
        with self.assertRaises(ValueError):
            decode_invite_config("")

    def test_parse_realtime_postgres_change(self):
        msg_insert = {
            "topic": "realtime:public:saka_words",
            "event": "postgres_changes",
            "payload": {
                "data": {
                    "table": "saka_words",
                    "type": "INSERT",
                    "record": {"word": "faks", "status": "whitelist", "is_custom": True},
                    "old_record": {},
                }
            },
        }
        parsed = parse_realtime_postgres_change(msg_insert)
        self.assertIsNotNone(parsed)
        ev, rec, old = parsed
        self.assertEqual(ev, "INSERT")
        self.assertEqual(rec["word"], "faks")
        self.assertEqual(old, {})

        msg_delete = {
            "event": "postgres_changes",
            "payload": {
                "data": {
                    "table": "saka_words",
                    "type": "DELETE",
                    "record": {},
                    "old_record": {"word": "hoax"},
                }
            },
        }
        ev2, _, old2 = parse_realtime_postgres_change(msg_delete)
        self.assertEqual(ev2, "DELETE")
        self.assertEqual(old2["word"], "hoax")

        self.assertIsNone(parse_realtime_postgres_change({"event": "phx_reply", "payload": {}}))

    def test_cache_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "db_cache.json")
            store = DbCacheStore(p)
            records = {"faks": {"word": "faks", "status": "whitelist", "is_custom": True}}
            pending = [{"action": "upsert", "word": "faks", "record": records["faks"]}]
            self.assertTrue(store.save(records, last_synced_at="2026-11-27T00:00:00Z", pending_ops=pending))
            loaded = store.load()
            self.assertEqual(loaded["records"]["faks"]["status"], "whitelist")
            self.assertEqual(loaded["last_synced_at"], "2026-11-27T00:00:00Z")
            self.assertEqual(len(loaded["pending_ops"]), 1)

    def test_rest_client_mocked(self):
        def handler(method, url, headers, body):
            if method == "GET" and "limit=1" in url:
                return _FakeResponse(200, [{"word": "test"}])
            if method == "GET":
                rng = headers.get("Range", "0-999")
                if rng.startswith("0-"):
                    return _FakeResponse(200, [
                        {"word": "alpha", "status": "whitelist", "is_custom": False, "added_by": "a", "updated_at": "t1"}
                    ])
                return _FakeResponse(200, [])
            if method == "POST":
                return _FakeResponse(201, [body] if isinstance(body, dict) else [])
            if method == "DELETE":
                return _FakeResponse(204, None)
            return _FakeResponse(500)

        client = SupabaseRestClient("https://demo.supabase.co", "key123", session=_FakeSession(handler))
        ok, _ = client.test_connection()
        self.assertTrue(ok)
        recs = client.fetch_all_records(page_size=1000)
        self.assertIn("alpha", recs)
        up = client.upsert_record({"word": "beta", "status": "custom", "is_custom": True})
        self.assertEqual(up["word"], "beta")
        cnt = client.upsert_batch([{"word": "gamma", "status": "blocklist", "is_custom": False}])
        self.assertEqual(cnt, 1)
        client.delete_word("alpha")

        # 404 table missing test
        client_404 = SupabaseRestClient(
            "https://demo.supabase.co",
            "key123",
            session=_FakeSession(lambda *_: _FakeResponse(404, text="PGRST205")),
        )
        ok404, msg404 = client_404.test_connection()
        self.assertFalse(ok404)
        self.assertIn("saka_words", msg404)
        with self.assertRaises(PermanentSyncError):
            client_404.fetch_all_records()


class TestSolverDualMode(unittest.TestCase):
    def _make_temp_solver(self, td, storage_mode="txt", callback=None, use_csv=True):
        kamus = os.path.join(td, "kamus_lengkap.txt")
        kbbi = os.path.join(td, "kamus_kbbi.txt")
        contek = os.path.join(td, "kamus_contek.txt")
        custom_csv = os.path.join(td, "kamus_custom.csv")
        wl = os.path.join(td, "whitelist.csv" if use_csv else "whitelist.txt")
        bl = os.path.join(td, "blacklist.csv" if use_csv else "blacklist.txt")

        with open(kbbi, "w", encoding="utf-8") as f:
            f.write("buku\nbukit\nbox\n")
        with open(contek, "w", encoding="utf-8") as f:
            f.write("buka\nparadox\n")
        with open(kamus, "w", encoding="utf-8") as f:
            f.write("buku\nbukit\nbuka\nbox\nparadox\n")
        if use_csv:
            with open(wl, "w", encoding="utf-8") as f:
                f.write("word,datetime\nbuka,\n")
            with open(bl, "w", encoding="utf-8") as f:
                f.write("word,datetime\nbox,\n")
        else:
            with open(wl, "w", encoding="utf-8") as f:
                f.write("buka\n")
            with open(bl, "w", encoding="utf-8") as f:
                f.write("box\n")

        return SambungKataSolver(
            dictionary_path=kamus,
            blacklist_path=bl,
            whitelist_path=wl,
            kbbi_path=kbbi,
            contek_path=contek,
            custom_dict_path=custom_csv,
            use_kbbi=True,
            use_contek=True,
            storage_mode=storage_mode,
            db_mutation_callback=callback,
        )

    def test_txt_mode_and_switch_isolation(self):
        with tempfile.TemporaryDirectory() as td:
            mutations = []
            solver = self._make_temp_solver(td, storage_mode="txt", callback=lambda a, w, r: mutations.append((a, w, r)))
            self.assertIn("buka", solver.whitelisted_words)
            self.assertIn("box", solver.blacklisted_words)
            self.assertEqual(mutations, [])

            # Export csv records
            exported = solver.export_txt_records_for_import(added_by="host")
            exp_map = {r["word"]: r for r in exported}
            self.assertEqual(exp_map["buka"]["status"], "whitelist")
            self.assertEqual(exp_map["box"]["status"], "blocklist")

            # Switch ke supabase dengan snapshot kosong -> tidak tercampur whitelist.csv / blacklist.csv
            solver.switch_storage_mode("supabase", {})
            self.assertEqual(len(solver.whitelisted_words), 0)
            self.assertEqual(len(solver.blacklisted_words), 0)

            # Mutasi di mode supabase tidak menyentuh file CSV lokal!
            self.assertTrue(solver.whitelist_word("buku"))
            self.assertTrue(solver.blacklist_word("bukit"))
            ok_add, _ = solver.add_word("zztestkata")
            self.assertTrue(ok_add)
            self.assertTrue(solver.has_word("zztestkata"))
            self.assertTrue(bool(solver.get_word_datetime("buku", scope="whitelist")))
            self.assertTrue(bool(solver.get_word_datetime("bukit", scope="blacklist")))
            self.assertTrue(bool(solver.get_word_datetime("zztestkata", scope="custom")))
            # Duplikat di mode supabase ditolak
            self.assertFalse(solver.whitelist_word("buku"))
            self.assertFalse(solver.blacklist_word("bukit"))

            wl_after = solver._read_word_csv(os.path.join(td, "whitelist.csv"))
            bl_after = solver._read_word_csv(os.path.join(td, "blacklist.csv"))
            self.assertEqual(set(wl_after.keys()), {"buka"})
            self.assertEqual(set(bl_after.keys()), {"box"})

            # Transisi is_custom: whitelist custom word -> unwhitelist tetap mempertahankan kata di kamus!
            self.assertTrue(solver.whitelist_word("zztestkata"))
            self.assertTrue(solver.is_whitelisted("zztestkata"))
            solver.unwhitelist_word("zztestkata")
            self.assertFalse(solver.is_whitelisted("zztestkata"))
            self.assertTrue(solver.has_word("zztestkata"))
            self.assertEqual(mutations[-1][0], "upsert")
            self.assertEqual(mutations[-1][2]["status"], "custom")

            # Unwhitelist kata dasar -> delete dari DB, tetap ada di kamus dasar
            solver.unwhitelist_word("buku")
            self.assertEqual(mutations[-1][0], "delete")
            self.assertTrue(solver.has_word("buku"))

            # Remote event INSERT/UPDATE/DELETE dari teman
            solver.apply_db_event("INSERT", {"word": "temanbaru", "status": "whitelist", "is_custom": True, "updated_at": "2026-11-28T06:00:00Z"})
            self.assertTrue(solver.is_whitelisted("temanbaru"))
            self.assertTrue(solver.has_word("temanbaru"))
            self.assertEqual(solver.get_word_datetime("temanbaru", scope="whitelist"), "2026-11-28T06:00:00Z")
            res = solver.cari_jawaban("TE", limit=5)
            self.assertEqual(res[0]["kata"], "temanbaru")

            solver.apply_db_event("UPDATE", {"word": "temanbaru", "status": "blocklist", "is_custom": True, "updated_at": "2026-11-28T06:05:00Z"})
            self.assertFalse(solver.is_whitelisted("temanbaru"))
            self.assertIn("temanbaru", solver.blacklisted_words)
            res2 = solver.cari_jawaban("TE", limit=5)
            self.assertFalse(any(x["kata"] == "temanbaru" for x in res2))

            solver.apply_db_event("DELETE", old_record={"word": "temanbaru"})
            self.assertNotIn("temanbaru", solver.blacklisted_words)
            self.assertFalse(solver.has_word("temanbaru"))

            # Switch balik ke txt -> state txt kembali bersih seperti awal
            solver.switch_storage_mode("txt")
            self.assertIn("buka", solver.whitelisted_words)
            self.assertIn("box", solver.blacklisted_words)
            self.assertFalse(solver.has_word("zztestkata"))

    def test_sync_manager_cache_and_echo_dedup(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SupabaseSyncManager(cache_path=os.path.join(td, "db_cache.json"))
            mgr.update_nickname("alden")
            mgr.enqueue_mutation("upsert", "faks", {"word": "faks", "status": "whitelist", "is_custom": True})
            loaded = mgr.load_cached_records()
            self.assertIn("faks", loaded)
            self.assertEqual(loaded["faks"]["added_by"], "alden")
            self.assertTrue(mgr._consume_self_echo("faks"))
            self.assertFalse(mgr._consume_self_echo("faks"))

    def test_saka_settings_realtime_parse_cache_and_rest(self):
        msg_settings = {
            "event": "postgres_changes",
            "payload": {
                "data": {
                    "table": "saka_settings",
                    "type": "UPDATE",
                    "record": {
                        "key": "mode_state",
                        "value": {
                            "game_mode": "brutal",
                            "tier0_sort_mode": "tag_order",
                            "custom_trap_endings": [{"suffix": "AMSI", "enabled": True, "color": "#fff"}],
                        },
                        "updated_by": "teman",
                    },
                    "old_record": {},
                }
            },
        }
        parsed = parse_realtime_table_change(msg_settings)
        self.assertIsNotNone(parsed)
        table, ev, rec, _ = parsed
        self.assertEqual(table, "saka_settings")
        self.assertEqual(ev, "UPDATE")
        self.assertEqual(rec["value"]["game_mode"], "brutal")
        # Backwards-compat helper ignores saka_settings
        self.assertIsNone(parse_realtime_postgres_change(msg_settings))

        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "db_cache.json")
            store = DbCacheStore(p)
            ms = {"game_mode": "santai", "custom_trap_endings": [{"suffix": "NS", "enabled": True}]}
            self.assertTrue(store.save({}, mode_state=ms, pending_mode_state=ms, mode_updated_by="alden"))
            loaded = store.load()
            self.assertEqual(loaded["mode_state"]["game_mode"], "santai")
            self.assertEqual(loaded["pending_mode_state"]["game_mode"], "santai")
            self.assertEqual(loaded["mode_updated_by"], "alden")

            mgr = SupabaseSyncManager(cache_path=p)
            mgr.update_nickname("alden")
            mgr.enqueue_mode_state({"game_mode": "brutal", "custom_trap_endings": []})
            mgr.load_cached_records()
            cm = mgr.load_cached_mode_state()
            self.assertEqual(cm["game_mode"], "brutal")
            self.assertTrue(mgr._consume_mode_self_echo({"game_mode": "brutal", "custom_trap_endings": []}))

        def handler(method, url, headers, body):
            if "saka_settings" in url and method == "GET":
                return _FakeResponse(200, [{"key": "mode_state", "value": {"game_mode": "brutal"}, "updated_by": "budi"}])
            if "saka_settings" in url and method == "POST":
                return _FakeResponse(201, [body])
            return _FakeResponse(404)

        client = SupabaseRestClient("https://demo.supabase.co", "sb_publishable_demo", session=_FakeSession(handler))
        val, who = client.fetch_mode_state()
        self.assertEqual(val["game_mode"], "brutal")
        self.assertEqual(who, "budi")
        up = client.upsert_mode_state({"game_mode": "default"}, updated_by="alden")
        self.assertEqual(up["key"], "mode_state")

        client_missing = SupabaseRestClient(
            "https://demo.supabase.co",
            "sb_publishable_demo",
            session=_FakeSession(lambda *_: _FakeResponse(404, text="PGRST205")),
        )
        with self.assertRaises(SettingsTableUnavailableError):
            client_missing.fetch_mode_state()
        with self.assertRaises(SettingsTableUnavailableError):
            client_missing.upsert_mode_state({"game_mode": "default"})

    def test_config_mode_isolation_between_txt_and_supabase(self):
        with tempfile.TemporaryDirectory() as td:
            orig_main = cfg_mod.CONFIG_FILE
            orig_default = cfg_mod.DEFAULT_CONFIG_FILE
            try:
                cfg_mod.CONFIG_FILE = os.path.join(td, "config.json")
                cfg_mod.DEFAULT_CONFIG_FILE = os.path.join(td, "config.default.json")

                txt_cfg = dict(cfg_mod.DEFAULT_CONFIG)
                txt_cfg["storage_mode"] = "txt"
                txt_cfg["game_mode"] = "default"
                txt_cfg["custom_trap_endings"] = [{"suffix": "NS", "enabled": True, "color": "#cba6f7"}]
                self.assertTrue(cfg_mod.save_config(txt_cfg))

                # Simulasi masuk Mode Database dan mengubah MODE dari teman
                db_cfg = dict(txt_cfg)
                db_cfg["storage_mode"] = "supabase"
                db_cfg["game_mode"] = "brutal"
                db_cfg["custom_trap_endings"] = [{"suffix": "AMSI", "enabled": False, "color": "#fff"}]
                self.assertTrue(cfg_mod.save_config(db_cfg))

                # Saat kembali ke Mode TXT, load_txt_mode_state() harus memulihkan tag/mode TXT asli!
                restored_txt = cfg_mod.load_txt_mode_state()
                self.assertEqual(restored_txt["game_mode"], "default")
                self.assertEqual(restored_txt["custom_trap_endings"][0]["suffix"], "NS")
            finally:
                cfg_mod.CONFIG_FILE = orig_main
                cfg_mod.DEFAULT_CONFIG_FILE = orig_default

    def test_load_config_seeds_from_default_and_merges_new_hotkeys(self):
        with tempfile.TemporaryDirectory() as td:
            orig_main = cfg_mod.CONFIG_FILE
            orig_default = cfg_mod.DEFAULT_CONFIG_FILE
            try:
                cfg_mod.CONFIG_FILE = os.path.join(td, "config.json")
                cfg_mod.DEFAULT_CONFIG_FILE = os.path.join(td, "config.default.json")

                default_payload = dict(cfg_mod.DEFAULT_CONFIG)
                default_payload["updater_branch"] = "main"
                default_payload["hotkeys"] = {
                    **cfg_mod.DEFAULT_HOTKEYS,
                    "quick_ping": "F9",
                }
                with open(cfg_mod.DEFAULT_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_payload, f)

                # Fresh install: otomatis membuat config.json dari config.default.json
                seeded = cfg_mod.load_config()
                self.assertTrue(os.path.exists(cfg_mod.CONFIG_FILE))
                self.assertEqual(seeded["hotkeys"]["quick_ping"], "F9")

                # User mengubah bind + mengisi kredensial, lalu default menambah hotkey baru
                user_cfg = dict(seeded)
                user_cfg["supabase_url"] = "https://example.supabase.co"
                user_cfg["hotkeys"] = {"toggle_scan": "F10"}
                self.assertTrue(cfg_mod.save_config(user_cfg))

                default_payload["hotkeys"]["extra_bind"] = "F11"
                with open(cfg_mod.DEFAULT_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(default_payload, f)

                loaded = cfg_mod.load_config()
                self.assertEqual(loaded["supabase_url"], "https://example.supabase.co")
                self.assertEqual(loaded["hotkeys"]["toggle_scan"], "F10")
                self.assertEqual(loaded["hotkeys"]["extra_bind"], "F11")
            finally:
                cfg_mod.CONFIG_FILE = orig_main
                cfg_mod.DEFAULT_CONFIG_FILE = orig_default

    def test_presence_state_and_diff_tracking(self):
        pmap = {}
        cnt, names = apply_presence_event(
            pmap,
            "presence_state",
            {
                "k1": {"metas": [{"phx_ref": "r1", "nickname": "alden"}]},
                "k2": {"metas": [{"phx_ref": "r2", "nickname": ""}]},
            },
        )
        self.assertEqual(cnt, 2)
        self.assertEqual(names, ["alden", "Anonim"])

        cnt2, names2 = apply_presence_event(
            pmap,
            "presence_diff",
            {
                "joins": {"k3": {"metas": [{"phx_ref": "r3", "nickname": "budi"}]}},
                "leaves": {"k2": {"metas": [{"phx_ref": "r2", "nickname": ""}]}},
            },
        )
        self.assertEqual(cnt2, 2)
        self.assertEqual(names2, ["alden", "budi"])

    def test_titlebar_db_activity_flash_state_machine(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication, QWidget
        from qt_components import QtCustomTitleBar
        from qt_theme import THEME

        app = QApplication.instance() or QApplication([])

        class _DummyWin(QWidget):
            def toggle_always_on_top(self):
                pass

        win = _DummyWin()
        bar = QtCustomTitleBar(win, logo_path="")

        # Di Mode TXT tidak boleh flash
        bar.set_db_status("txt", "Mode TXT")
        bar.flash_db_activity("remote")
        self.assertFalse(bar._db_flash_timer.isActive())

        # Di Mode LIVE, flash remote pakai accent_cyan dan pulih setelah 5 tick
        bar.set_db_status("live", "Terhubung")
        bar.flash_db_activity("remote")
        self.assertTrue(bar._db_flash_timer.isActive())
        self.assertIn(THEME["accent_cyan"], bar.btn_db_status.styleSheet())

        bar._on_db_flash_tick()  # step 1 (dim)
        self.assertIn(THEME["border"], bar.btn_db_status.styleSheet())
        bar._on_db_flash_tick()  # step 2 (on)
        self.assertIn(THEME["accent_cyan"], bar.btn_db_status.styleSheet())
        bar._on_db_flash_tick()  # step 3 (dim)
        bar._on_db_flash_tick()  # step 4 (on)
        bar._on_db_flash_tick()  # step 5 -> selesai & pulih ke live primary
        self.assertFalse(bar._db_flash_timer.isActive())
        self.assertIn(THEME["primary"], bar.btn_db_status.styleSheet())

        # Flash local pakai warning, dan dibatalkan seketika saat status error
        bar.flash_db_activity("local")
        self.assertTrue(bar._db_flash_timer.isActive())
        self.assertIn(THEME["warning"], bar.btn_db_status.styleSheet())
        bar.set_db_status("error", "Gagal")
        self.assertFalse(bar._db_flash_timer.isActive())
        self.assertIn(THEME["danger"], bar.btn_db_status.styleSheet())

    def test_download_db_to_txt_files_and_mode(self):
        with tempfile.TemporaryDirectory() as td:
            solver = self._make_temp_solver(td, storage_mode="supabase")
            db_records = {
                "faks": {"word": "faks", "status": "whitelist", "is_custom": True, "updated_at": "2026-11-28T05:00:00Z"},
                "buka": {"word": "buka", "status": "blocklist", "is_custom": False, "updated_at": "2026-11-28T05:01:00Z"},
                "zzunik": {"word": "zzunik", "status": "custom", "is_custom": True, "updated_at": "2026-11-28T05:02:00Z"},
            }
            # 1. Merge mode: mempertahankan whitelist/blacklist lokal yang tidak bentrok + timestamp DB
            wl_n, bl_n, cm_n = solver.apply_db_records_to_txt_files(db_records, overwrite_lists=False)
            self.assertEqual(wl_n, 1)  # faks (buka dipindah ke blocklist)
            self.assertEqual(bl_n, 2)  # box + buka
            self.assertEqual(cm_n, 2)  # faks + zzunik ditambahkan ke kamus_custom.csv
            wl_csv = solver._read_word_csv(os.path.join(td, "whitelist.csv"))
            bl_csv = solver._read_word_csv(os.path.join(td, "blacklist.csv"))
            cm_csv = solver._read_word_csv(os.path.join(td, "kamus_custom.csv"))
            self.assertEqual(wl_csv.get("faks"), "2026-11-28T05:00:00Z")
            self.assertEqual(bl_csv.get("buka"), "2026-11-28T05:01:00Z")
            self.assertEqual(cm_csv.get("zzunik"), "2026-11-28T05:02:00Z")

            # 2. Overwrite mode: box (yang tidak ada di DB) ikut dihapus dari blacklist.csv
            wl_n2, bl_n2, cm_n2 = solver.apply_db_records_to_txt_files(db_records, overwrite_lists=True)
            self.assertEqual(wl_n2, 1)
            self.assertEqual(bl_n2, 1)  # hanya buka
            self.assertEqual(cm_n2, 0)  # sudah masuk sebelumnya

            # 3. save_txt_mode_state menulis ke config.json
            orig_main = cfg_mod.CONFIG_FILE
            orig_default = cfg_mod.DEFAULT_CONFIG_FILE
            try:
                cfg_mod.CONFIG_FILE = os.path.join(td, "config.json")
                cfg_mod.DEFAULT_CONFIG_FILE = os.path.join(td, "config.default.json")
                self.assertTrue(cfg_mod.save_txt_mode_state({"game_mode": "santai", "tier0_sort_mode": "tag_order"}))
                loaded = cfg_mod.load_txt_mode_state()
                self.assertEqual(loaded["game_mode"], "santai")
                self.assertEqual(loaded["tier0_sort_mode"], "tag_order")
            finally:
                cfg_mod.CONFIG_FILE = orig_main
                cfg_mod.DEFAULT_CONFIG_FILE = orig_default

    def test_csv_migration_readonly_dicts_duplicate_guard_and_newest_sort(self):
        with tempfile.TemporaryDirectory() as td:
            kamus = os.path.join(td, "kamus_lengkap.txt")
            kbbi = os.path.join(td, "kamus_kbbi.txt")
            contek = os.path.join(td, "kamus_contek.txt")
            custom_csv = os.path.join(td, "kamus_custom.csv")
            wl_txt = os.path.join(td, "whitelist.txt")
            bl_txt = os.path.join(td, "blacklist.txt")
            wl_csv = os.path.join(td, "whitelist.csv")
            bl_csv = os.path.join(td, "blacklist.csv")

            with open(kbbi, "w", encoding="utf-8") as f:
                f.write("buku\nbukit\n")
            with open(contek, "w", encoding="utf-8") as f:
                f.write("buka\nparadox\n")
            with open(kamus, "w", encoding="utf-8") as f:
                f.write("buku\nbukit\nbuka\nparadox\n")
            with open(wl_txt, "w", encoding="utf-8") as f:
                f.write("# header\nbuka\n")
            with open(bl_txt, "w", encoding="utf-8") as f:
                f.write("bukit\n")

            def _read_txt(p):
                with open(p, encoding="utf-8") as f:
                    return f.read()

            kbbi_before = _read_txt(kbbi)
            contek_before = _read_txt(contek)
            kamus_before = _read_txt(kamus)

            solver = SambungKataSolver(
                dictionary_path=kamus,
                blacklist_path=bl_csv,
                whitelist_path=wl_csv,
                kbbi_path=kbbi,
                contek_path=contek,
                custom_dict_path=custom_csv,
                use_kbbi=True,
                use_contek=True,
                storage_mode="txt",
            )

            # Migrasi otomatis: .txt lama dihapus, .csv terbuat dengan datetime kosong ""
            self.assertFalse(os.path.exists(wl_txt))
            self.assertFalse(os.path.exists(bl_txt))
            self.assertTrue(os.path.exists(wl_csv))
            self.assertTrue(os.path.exists(bl_csv))
            self.assertEqual(solver.get_word_datetime("buka", scope="whitelist"), "")
            self.assertEqual(solver.get_word_datetime("bukit", scope="blacklist"), "")

            # Tambah manual & whitelist kata baru -> masuk kamus_custom.csv, kamus dasar read-only!
            ok_add, _ = solver.add_word("buxa")
            self.assertTrue(ok_add)
            self.assertTrue(os.path.exists(custom_csv))
            self.assertEqual(_read_txt(kbbi), kbbi_before)
            self.assertEqual(_read_txt(contek), contek_before)
            self.assertEqual(_read_txt(kamus), kamus_before)

            ts_buxa = solver.get_word_datetime("buxa", scope="custom")
            self.assertTrue(bool(ts_buxa))

            # Duplicate guard: re-add ke whitelist / blocklist / kamus ditolak & tidak menimpa timestamp
            self.assertFalse(solver.whitelist_word("buka"))
            self.assertEqual(solver.get_word_datetime("buka", scope="whitelist"), "")
            self.assertFalse(solver.blacklist_word("bukit"))
            self.assertEqual(solver.get_word_datetime("bukit", scope="blacklist"), "")
            ok_dup, _ = solver.add_word("buxa")
            self.assertFalse(ok_dup)
            self.assertEqual(solver.get_word_datetime("buxa", scope="custom"), ts_buxa)

            # Transisi status (bukit: blocklist -> whitelist) memperbarui datetime
            self.assertTrue(solver.whitelist_word("bukit"))
            self.assertNotIn("bukit", solver.blacklisted_words)
            self.assertIn("bukit", solver.whitelisted_words)
            self.assertTrue(bool(solver.get_word_datetime("bukit", scope="whitelist")))

            # Sortir Terbaru di search_dictionary: ber-datetime di atas (newest first), tanpa tanggal di bawah
            solver.custom_timestamps["buold"] = "2026-01-01T00:00:00Z"
            solver.base_custom_set.add("buold")
            solver.custom_set.add("buold")
            solver._add_word_to_active_memory("buold")
            res_new, _ = solver.search_dictionary(query="bu", search_type="prefix", limit=20, sort_by="newest")
            words_new = [r["word"] for r in res_new]
            self.assertLess(words_new.index("BUXA"), words_new.index("BUOLD"))
            self.assertLess(words_new.index("BUOLD"), words_new.index("BUKU"))

            # Hapus kata kamus custom (tidak bisa hapus kata dasar KBBI/Contek)
            ok_del_base, _ = solver.delete_custom_word("buku")
            self.assertFalse(ok_del_base)
            self.assertTrue(solver.has_word("buku"))

            ok_del_custom, _ = solver.delete_custom_word("buxa")
            self.assertTrue(ok_del_custom)
            self.assertFalse(solver.has_word("buxa"))
            self.assertNotIn("buxa", solver._read_word_csv(custom_csv))

            # Deduplikasi tag custom di set_custom_endings
            solver.set_custom_endings([
                {"suffix": "NS", "name": "NS", "enabled": True},
                {"suffix": "ns", "name": "NS2", "enabled": False},
                {"suffix": "MP", "name": "MP", "enabled": True},
            ])
            self.assertEqual([c["suffix"] for c in solver.custom_endings], ["ns", "mp"])

    def test_explorer_custom_filter_added_by_and_cache_clear(self):
        with tempfile.TemporaryDirectory() as td:
            solver = self._make_temp_solver(td, storage_mode="supabase")
            solver.apply_db_snapshot({
                "zzcustom": {"word": "zzcustom", "status": "custom", "is_custom": True, "added_by": "budi"},
                "buka": {"word": "buka", "status": "whitelist", "is_custom": False, "added_by": "alden"},
            })
            res_c, tot_c = solver.search_dictionary(query="", source_filter="custom", limit=20)
            self.assertEqual(tot_c, 1)
            self.assertEqual(res_c[0]["word"], "ZZCUSTOM")
            self.assertEqual(res_c[0]["added_by"], "budi")
            self.assertTrue(res_c[0]["is_db_custom"])

            cache_p = os.path.join(td, "db_cache.json")
            mgr = SupabaseSyncManager(cache_path=cache_p)
            mgr.enqueue_mutation("upsert", "zzcustom", {"word": "zzcustom", "status": "custom", "is_custom": True})
            self.assertTrue(os.path.exists(cache_p))
            self.assertTrue(mgr.clear_cache())
            self.assertFalse(os.path.exists(cache_p))
            self.assertEqual(mgr.get_cached_records_snapshot(), {})


if __name__ == "__main__":
    unittest.main()
