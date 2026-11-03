"""
Suite Pengujian Unit SambungKataSolver
Memverifikasi:
1. Pemuatan kamus (KBBI, Contek, Gabungan)
2. Struktur prioritas (Tier 0 Custom Traps, Tier 1 Jebakan X, Tier 2 Jebakan Sulit, Tier 3 Normal)
3. Kategori kustom (Custom Traps, e.g. NS, NGK)
4. Mode Santai (Pengecualian X, Q, F)
5. Sistem Blacklist (Blokir dan Pemulihan)
"""

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

    def test_jebakan_x_priority(self):
        """Memastikan kata berakhiran X berada di tier prioritas atas"""
        hasil = self.solver.cari_jawaban("BO", limit=10)
        jebakan_x = [x for x in hasil if x["tipe"] == "JEBAKAN_X"]
        self.assertTrue(len(jebakan_x) > 0)
        self.assertTrue(jebakan_x[0]["kata"].endswith("x"))
        self.assertEqual(jebakan_x[0]["tipe"], "JEBAKAN_X")

    def test_jebakan_sulit_priority(self):
        """Memastikan kata berakhiran konsonan sulit (Z, Q, V, J, W, F) ditandai benar tanpa suffix '(Sulit)'"""
        hasil = self.solver.cari_jawaban("A", limit=20)
        jebakan_sulit = [x for x in hasil if x["tipe"] == "JEBAKAN_SULIT"]
        self.assertTrue(len(jebakan_sulit) > 0)
        for item in jebakan_sulit:
            self.assertIn(item["kata"][-1].upper(), ["Z", "Q", "V", "J", "W", "F"])
            self.assertNotIn("(Sulit)", item["deskripsi"])

    def test_custom_ending_traps(self):
        """Memastikan custom ending categories (seperti NS, NGK) berprioritas super (Tier 0)"""
        custom_rules = [
            {"suffix": "NS", "name": "Akhiran NS", "color": "#cba6f7", "enabled": True}
        ]
        hasil = self.solver.cari_jawaban("LE", limit=10, custom_endings=custom_rules)

        custom_traps = [x for x in hasil if x["tipe"] == "CUSTOM_TRAP"]
        self.assertTrue(len(custom_traps) > 0)
        self.assertTrue(custom_traps[0]["kata"].upper().endswith("NS"))
        self.assertEqual(custom_traps[0]["badge_name"], "Akhiran NS")

        # Uji jika dinonaktifkan (enabled=False)
        custom_disabled = [
            {"suffix": "NS", "name": "Akhiran NS", "color": "#cba6f7", "enabled": False}
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
        kata_x = "sex"
        # Whitelist kata 'sex'
        self.solver.whitelist_word(kata_x)
        self.assertTrue(self.solver.is_whitelisted(kata_x))

        hasil = self.solver.cari_jawaban("S", limit=15)
        x_items = [x for x in hasil if x["tipe"] == "JEBAKAN_X"]
        self.assertTrue(len(x_items) > 0)
        # Kata yang di-whitelist harus berada di urutan teratas pada kategori X
        self.assertEqual(x_items[0]["kata"].lower(), kata_x)
        self.assertTrue(x_items[0]["is_whitelisted"])

        # Uji kata baru yang belum ada di kamus
        kata_baru = "zzwhitelisttest"
        self.assertFalse(self.solver.has_word(kata_baru))
        self.solver.whitelist_word(kata_baru)
        self.assertTrue(self.solver.has_word(kata_baru))
        
        hasil_baru = self.solver.cari_jawaban("ZZ", limit=5)
        self.assertTrue(any(x["kata"] == kata_baru for x in hasil_baru))

        # Bersihkan setelah pengujian
        self.solver.unwhitelist_word(kata_x)
        self.solver.unwhitelist_word(kata_baru)
        self.assertFalse(self.solver.is_whitelisted(kata_x))
        self.assertFalse(self.solver.has_word(kata_baru))

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
