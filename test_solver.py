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


if __name__ == "__main__":
    unittest.main()
