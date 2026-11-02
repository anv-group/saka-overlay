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

        # Gunakan path file sementara untuk pengujian
        self.tmp_bl_path = 'test_tmp_blacklist.txt'
        with open(self.tmp_bl_path, 'w', encoding='utf-8') as f:
            f.write("remix\n")

        self.solver = SambungKataSolver(blacklist_path=self.tmp_bl_path)
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
            on_event_callback=on_event
        )

    def tearDown(self):
        if hasattr(self, 'tmp_bl_path') and os.path.exists(self.tmp_bl_path):
            try:
                os.remove(self.tmp_bl_path)
            except Exception:
                pass

    def test_default_typing(self):
        img = cv2.imread('deteksi-gameplay/default/full.png')
        state, word, act = self.indexer.process_frame(img, is_full_frame=True)
        self.assertEqual(state, "SEDANG_KETIK")
        self.assertEqual(word, "IMBAS")

    def test_kata_salah_sequence(self):
        # Jalankan pada sequence kata tidak ada (0..15)
        detected_states = []
        for i in range(16):
            img = cv2.imread(f'deteksi-gameplay/kata-tidak-ada/{i}.png')
            st, wd, act = self.indexer.process_frame(img, is_full_frame=True)
            detected_states.append(st)

        # Harus ada state KATA_SALAH yang terdeteksi
        self.assertIn("KATA_SALAH", detected_states)
        # Event callback harus dipanggil dengan KATA_SALAH dan word ATF
        states_in_events = [e[0] for e in self.events]
        words_in_events = [e[1] for e in self.events]
        self.assertIn("KATA_SALAH", states_in_events)
        self.assertIn("ATF", words_in_events)

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


if __name__ == '__main__':
    unittest.main()
