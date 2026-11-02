import cv2
import os
import unittest
from gameplay_indexer import GameplayIndexer
from solver import SambungKataSolver

class TestGameplayIndexer(unittest.TestCase):
    def setUp(self):
        self.events = []
        def on_event(state, word, action, entry):
            self.events.append((state, word, action))

        self.tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_tmp_staging')
        os.makedirs(self.tmp_dir, exist_ok=True)

        self.solver = SambungKataSolver()
        self.indexer = GameplayIndexer(
            config={
                "auto_blacklist_invalid": True,
                "auto_learn_valid": True,
                "gameplay_area": {
                    "left": 740,
                    "top": 250,
                    "width": 440,
                    "height": 400
                }
            },
            solver=self.solver,
            on_event_callback=on_event,
            base_dir=self.tmp_dir
        )

    def tearDown(self):
        # Bersihkan folder staging pengujian
        if os.path.exists(self.tmp_dir):
            for f in os.listdir(self.tmp_dir):
                fp = os.path.join(self.tmp_dir, f)
                try:
                    if os.path.isfile(fp): os.remove(fp)
                except Exception:
                    pass
            try:
                os.rmdir(self.tmp_dir)
            except Exception:
                pass

    def test_default_typing(self):
        img = cv2.imread('deteksi-gameplay/default/full.png')
        state, word, act = self.indexer.process_frame(img, is_full_frame=True)
        self.assertEqual(state, "SEDANG_KETIK")
        self.assertEqual(word, "IMBAS")

    def test_kata_salah_sequence(self):
        # Catat total baris blacklist.txt asli sebelum test
        with open('blacklist.txt', 'r', encoding='utf-8') as f:
            orig_bl_lines = f.readlines()

        detected_states = []
        for i in range(16):
            img = cv2.imread(f'deteksi-gameplay/kata-tidak-ada/{i}.png')
            st, wd, act = self.indexer.process_frame(img, is_full_frame=True)
            detected_states.append(st)

        # Harus ada state KATA_SALAH yang terdeteksi
        self.assertIn("KATA_SALAH", detected_states)
        states_in_events = [e[0] for e in self.events]
        words_in_events = [e[1] for e in self.events]
        self.assertIn("KATA_SALAH", states_in_events)
        self.assertIn("ATF", words_in_events)

        # PASTIKAN blacklist.txt asli TIDAK BERUBAH SAMA SEKALI
        with open('blacklist.txt', 'r', encoding='utf-8') as f:
            curr_bl_lines = f.readlines()
        self.assertEqual(orig_bl_lines, curr_bl_lines, "blacklist.txt asli tidak boleh tersentuh!")

        # Pastikan masuk ke auto_blacklist.txt terisolasi
        auto_bl_file = os.path.join(self.tmp_dir, "auto_blacklist.txt")
        self.assertTrue(os.path.exists(auto_bl_file), "auto_blacklist.txt harus terbuat")
        with open(auto_bl_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("atf", content)

    def test_sudah_dipakai_sequence(self):
        self.events.clear()
        detected_states = []
        for i in range(16):
            img = cv2.imread(f'deteksi-gameplay/sudah-dipakai/{i}.png')
            st, wd, act = self.indexer.process_frame(img, is_full_frame=True)
            detected_states.append(st)

        self.assertIn("SUDAH_DIGUNAKAN", detected_states)
        words_in_events = [e[1] for e in self.events]
        self.assertIn("UPAN", words_in_events)

        # Pastikan kamus resmi tidak berubah, tapi tercatat di auto_kata_baru.txt jika belum ada
        auto_baru_file = os.path.join(self.tmp_dir, "auto_kata_baru.txt")
        # Jika UPAN belum ada di kamus, harus tercatat
        if not self.solver.has_word("upan"):
            self.assertTrue(os.path.exists(auto_baru_file))
            with open(auto_baru_file, 'r', encoding='utf-8') as f:
                self.assertIn("upan", f.read())

    def test_benar_sequence(self):
        self.events.clear()
        # Frame 0: sedang mengetik IMBAS
        img0 = cv2.imread('deteksi-gameplay/benar/0.png')
        st0, wd0, act0 = self.indexer.process_frame(img0, is_full_frame=True)
        self.assertEqual(st0, "SEDANG_KETIK")
        self.assertEqual(wd0, "IMBAS")

        # Frame 1: benar (kotak hilang + tubuh hijau)
        img1 = cv2.imread('deteksi-gameplay/benar/1.png')
        st1, wd1, act1 = self.indexer.process_frame(img1, is_full_frame=True)
        self.assertEqual(st1, "KATA_BENAR")
        self.assertEqual(wd1, "IMBAS")
        self.assertIn(("KATA_BENAR", "IMBAS"), [(e[0], e[1]) for e in self.events])

    def test_kata_disensor_detection(self):
        self.events.clear()
        # Simulasikan kata yang sedang diketik
        self.indexer.last_typing_word = "KATA_KASAR"

        # Simulasikan frame kotak teks dengan teks sensor "######"
        # Buat crop sintetis dengan kotak putih berisi teks '######'
        import numpy as np
        crop = np.ones((400, 440, 3), dtype=np.uint8) * 50
        # Kotak putih di tengah
        crop[10:110, 150:290] = 250
        cv2.putText(crop, "######", (155, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

        st, wd, act = self.indexer.process_frame(crop, is_full_frame=False)
        self.assertEqual(st, "KATA_DISENSOR")
        self.assertEqual(wd, "KATA_KASAR")
        self.assertEqual(act, "AUTO_BLACKLISTED_CENSORED")


if __name__ == '__main__':
    unittest.main()
