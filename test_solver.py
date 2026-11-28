"""
Suite Pengujian Unit SambungKataSolver
Memverifikasi:
1. Pemuatan kamus (KBBI, Contek, Gabungan)
2. Struktur prioritas (Tier 0 Custom Traps, Tier 1 Jebakan X, Tier 2 Jebakan Sulit, Tier 3 Normal)
3. Kategori kustom (Custom Traps, e.g. NS, NGK)
4. Mode Santai (Pengecualian X, Q, F)
5. Sistem Blacklist (Blokir dan Pemulihan)
"""

import os
import unittest
from solver import SambungKataSolver


class TestSambungKataSolver(unittest.TestCase):
    def setUp(self):
        self.solver = SambungKataSolver()

    def test_dictionary_loading(self):
        """Memastikan kamus memuat lebih dari 100.000 kata unik"""
        self.assertGreater(len(self.solver.words), 100000)
        self.assertGreater(len(self.solver.kbbi_set), 50000)
        self.assertGreater(len(self.solver.contek_set), 50000)

    def test_prefix_search_basic(self):
        """Memastikan pencarian prefix mengembalikan kata yang sesuai awalan"""
        hasil = self.solver.cari_jawaban("BU", limit=10)
        self.assertTrue(len(hasil) > 0)
        for item in hasil:
            self.assertTrue(item["kata"].upper().startswith("BU"))

    def test_pure_custom_tags_no_builtin_traps(self):
        """Memastikan tidak ada tag bawaan JEBAKAN_X / JEBAKAN_SULIT (pure custom tags)"""
        for mode_kw in ({}, {"mode_santai": True}, {"mode_brutal": True}):
            hasil = self.solver.cari_jawaban("S", limit=40, custom_endings=[], **mode_kw)
            self.assertTrue(len(hasil) > 0)
            self.assertFalse(any(x["tipe"] in ("JEBAKAN_X", "JEBAKAN_SULIT") for x in hasil))

    def test_custom_ending_traps(self):
        """Memastikan custom ending categories (seperti NS, NGK) berprioritas super tanpa prefix 'Akhiran '"""
        custom_rules = [
            {"suffix": "NS", "name": "Akhiran NS", "color": "#cba6f7", "enabled": True}
        ]
        hasil = self.solver.cari_jawaban("LE", limit=10, custom_endings=custom_rules)

        custom_traps = [x for x in hasil if x["tipe"] == "CUSTOM_TRAP"]
        self.assertTrue(len(custom_traps) > 0)
        self.assertTrue(custom_traps[0]["kata"].upper().endswith("NS"))
        self.assertEqual(custom_traps[0]["badge_name"], "NS")

        # Uji jika dinonaktifkan (enabled=False)
        custom_disabled = [
            {"suffix": "NS", "name": "NS", "color": "#cba6f7", "enabled": False}
        ]
        hasil_dis = self.solver.cari_jawaban("LE", limit=10, custom_endings=custom_disabled)
        custom_dis_traps = [x for x in hasil_dis if x["tipe"] == "CUSTOM_TRAP"]
        self.assertEqual(len(custom_dis_traps), 0)

    def test_mode_santai_filtering(self):
        """Memastikan mode santai menyaring seluruh kata yang mengandung atau berakhiran X, Q, F"""
        hasil = self.solver.cari_jawaban("A", limit=30, mode_santai=True)
        self.assertTrue(len(hasil) > 0)
        for item in hasil:
            k = item["kata"].upper()
            self.assertFalse(k.endswith("X"))
            self.assertFalse(k.endswith("Q"))
            self.assertFalse(k.endswith("F"))
            self.assertNotIn("X", k)
            self.assertNotIn("Q", k)

        # Pastikan custom endings dengan huruf terlarang (X, Q, F seperti IF) otomatis diabaikan di Mode Santai
        custom_rules = [
            {"suffix": "IF", "name": "Akhiran IF", "enabled": True, "color": "#89dceb"},
            {"suffix": "NS", "name": "Akhiran NS", "enabled": True, "color": "#cba6f7"}
        ]
        hasil_custom = self.solver.cari_jawaban("A", limit=20, mode_santai=True, custom_endings=custom_rules)
        if_traps = [x for x in hasil_custom if x.get("suffix") == "IF"]
        self.assertEqual(len(if_traps), 0)

    def test_mode_brutal(self):
        """Memastikan Mode Brutal memprioritaskan tag jebakan brutal (AMSI, KSO, RHU, TL, BD) di Tier 0"""
        brutal_rules = [
            {"suffix": "AMSI", "name": "Akhiran AMSI", "enabled": True, "color": "#f9e2af"},
            {"suffix": "KSO", "name": "Akhiran KSO", "enabled": True, "color": "#a6e3a1"},
            {"suffix": "RHU", "name": "Akhiran RHU", "enabled": True, "color": "#fab387"},
            {"suffix": "TL", "name": "Akhiran TL", "enabled": True, "color": "#94e2d5"},
            {"suffix": "BD", "name": "Akhiran BD", "enabled": True, "color": "#cba6f7"},
        ]
        hasil = self.solver.cari_jawaban("AK", limit=20, mode_brutal=True, custom_endings=brutal_rules)
        self.assertTrue(len(hasil) > 0)
        # Kata 'akamsi' berakhiran AMSI harus berada di posisi #1 (Tier 0)
        top = hasil[0]
        self.assertEqual(top["tipe"], "CUSTOM_TRAP")
        self.assertEqual(top["suffix"], "AMSI")
        self.assertEqual(top["kata"].lower(), "akamsi")

        # Cek kata berakhiran KSO (seperti bakso)
        hasil_b = self.solver.cari_jawaban("BA", limit=20, mode_brutal=True, custom_endings=brutal_rules)
        kso_items = [x for x in hasil_b if x.get("suffix") == "KSO"]
        self.assertTrue(len(kso_items) > 0)
        self.assertTrue(kso_items[0]["kata"].lower().endswith("kso"))

        # Pastikan tidak ada tambahan jebakan bawaan (JEBAKAN_X / JEBAKAN_SULIT) di Mode Brutal
        hasil_s = self.solver.cari_jawaban("S", limit=40, mode_brutal=True, custom_endings=brutal_rules)
        self.assertFalse(any(x["tipe"] in ("JEBAKAN_X", "JEBAKAN_SULIT") for x in hasil_s))

    def test_blacklist_mechanism(self):
        """Memastikan kata yang diblacklist tidak muncul dan dapat dipulihkan"""
        kata_uji = "buku"
        self.solver.blacklist_word(kata_uji)
        self.assertTrue(kata_uji in self.solver.get_blacklisted_words())

        hasil = self.solver.cari_jawaban("BU", limit=20)
        kata_hasil = [x["kata"].lower() for x in hasil]
        self.assertNotIn(kata_uji, kata_hasil)

        # Pulihkan (unblacklist)
        self.solver.unblacklist_word(kata_uji)
        self.assertFalse(kata_uji in self.solver.get_blacklisted_words())

    def test_whitelist_mechanism_and_category_priority(self):
        """Memastikan kata di whitelist menjadi prioritas teratas di kategorinya dan aktif di memori"""
        custom_x = [{"suffix": "X", "name": "X", "enabled": True, "color": "#f38ba8"}]
        kata_baru = "zzwhitelistx"
        self.assertFalse(self.solver.has_word(kata_baru))
        self.solver.whitelist_word(kata_baru)
        self.assertTrue(self.solver.is_whitelisted(kata_baru))
        self.assertTrue(self.solver.has_word(kata_baru))

        hasil = self.solver.cari_jawaban("ZZ", limit=15, custom_endings=custom_x)
        trap_items = [x for x in hasil if x["tipe"] == "CUSTOM_TRAP"]
        self.assertTrue(len(trap_items) > 0)
        self.assertEqual(trap_items[0]["kata"].lower(), kata_baru)
        self.assertTrue(trap_items[0]["is_whitelisted"])

        # Bersihkan setelah pengujian
        self.solver.unwhitelist_word(kata_baru)
        self.assertFalse(self.solver.is_whitelisted(kata_baru))
        self.assertTrue(self.solver.has_word(kata_baru))

        # Hapus kata uji dari kamus_lengkap.txt agar file kamus tetap bersih
        if os.path.exists(self.solver.dictionary_path):
            with open(self.solver.dictionary_path, "r", encoding="utf-8") as f:
                lines = [ln for ln in f if ln.strip().lower() != kata_baru]
            with open(self.solver.dictionary_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

    def test_tier0_sort_modes_default_and_tag_order(self):
        """Memastikan mode sortir Tier 0 (default: panjang & abjad vs tag_order: urutan tag kustom) bekerja akurat"""
        custom_rules = [
            {"suffix": "NS", "name": "Akhiran NS", "enabled": True, "color": "#cba6f7"},
            {"suffix": "MP", "name": "Akhiran MP", "enabled": True, "color": "#89dceb"}
        ]

        # 1. Mode Default: Mengutamakan panjang 4-7 dan urutan abjad antar tag
        res_def = self.solver.cari_jawaban("S", limit=30, custom_endings=custom_rules, sort_mode="default")
        custom_def = [f"{x['kata']}[{x['suffix']}]" for x in res_def if x["tipe"] == "CUSTOM_TRAP"]
        # 'samp[MP]' (4 huruf) harus mendahului 'sains[NS]' (5 huruf)
        self.assertIn("samp[MP]", custom_def)
        self.assertIn("sains[NS]", custom_def)
        self.assertLess(custom_def.index("samp[MP]"), custom_def.index("sains[NS]"))

        # 2. Mode Tag Order: Tag 0 (NS) harus muncul SEMUA sebelum Tag 1 (MP)
        res_tag = self.solver.cari_jawaban("S", limit=100, custom_endings=custom_rules, sort_mode="tag_order")
        custom_tag = [f"{x['kata']}[{x['suffix']}]" for x in res_tag if x["tipe"] == "CUSTOM_TRAP"]
        first_mp = next(i for i, w in enumerate(custom_tag) if "[MP]" in w)
        last_ns = max(i for i, w in enumerate(custom_tag) if "[NS]" in w)
        self.assertGreater(first_mp, last_ns)

        # 3. Mode Tag Order Dibalik: Tag 0 (MP) harus muncul SEMUA sebelum Tag 1 (NS)
        custom_rules_rev = [
            {"suffix": "MP", "name": "Akhiran MP", "enabled": True, "color": "#89dceb"},
            {"suffix": "NS", "name": "Akhiran NS", "enabled": True, "color": "#cba6f7"}
        ]
        res_rev = self.solver.cari_jawaban("S", limit=100, custom_endings=custom_rules_rev, sort_mode="tag_order")
        custom_rev = [f"{x['kata']}[{x['suffix']}]" for x in res_rev if x["tipe"] == "CUSTOM_TRAP"]
        first_ns = next(i for i, w in enumerate(custom_rev) if "[NS]" in w)
        last_mp = max(i for i, w in enumerate(custom_rev) if "[MP]" in w)
        self.assertGreater(first_ns, last_mp)



    def test_search_dictionary_prefix_suffix_and_tags(self):
        """Memastikan fitur pencarian kamus (prefix, suffix, contains, dan multi-tag) bekerja akurat"""
        custom_rules = [
            {"suffix": "NS", "name": "Akhiran NS"},
            {"suffix": "MP", "name": "Akhiran MP"}
        ]
        self.solver.set_custom_endings(custom_rules)

        # 1. Pencarian Awalan (Prefix)
        res_pre, tot_pre = self.solver.search_dictionary(query="BUK", search_type="prefix", limit=10)
        self.assertGreater(tot_pre, 0)
        for r in res_pre:
            self.assertTrue(r["word"].startswith("BUK"))

        # 2. Pencarian Akhiran (Suffix)
        res_suf, tot_suf = self.solver.search_dictionary(query="X", search_type="suffix", limit=10)
        self.assertGreater(tot_suf, 0)
        for r in res_suf:
            self.assertTrue(r["word"].endswith("X"))

        # 3. Pencarian Mengandung (Contains)
        res_con, tot_con = self.solver.search_dictionary(query="OBX", search_type="contains", limit=10)
        for r in res_con:
            self.assertIn("OBX", r["word"])

        # 4. Filter Multi-Tag (NS dan MP)
        res_tag, tot_tag = self.solver.search_dictionary(query="", selected_tags=["NS", "MP"], limit=50)
        self.assertGreater(tot_tag, 0)
        for r in res_tag:
            self.assertTrue(r["word"].endswith("NS") or r["word"].endswith("MP"))

if __name__ == "__main__":
    unittest.main()
