import os
import time
import json
import cv2
import numpy as np
import mss
from PIL import Image

try:
    import winocr
    HAS_WINOCR = True
except ImportError:
    HAS_WINOCR = False

try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False


class GameplayIndexer:
    """
    Modul pengamat gameplay (Gameplay Watcher & Auto-Indexer) untuk game Roblox Sambung Kata:
    1. Mendeteksi status kata yang diinput:
       - SEDANG_KETIK: Kotak input berwarna putih/terang dengan teks huruf kapital.
       - KATA_SALAH: Kotak berubah merah, tidak ada pesan 'sudah digunakan' (kata invalid/ditolak game).
       - SUDAH_DIGUNAKAN: Kotak berubah merah, terdapat teks '"<KATA>" sudah digunakan!' (kata valid tapi sudah terpakai).
       - KATA_BENAR: Kotak kata lenyap seketika DAN tubuh karakter pemain di bawahnya berubah hijau terang.
    2. Isolasi Data (Keamanan Kamus):
       - Data auto-detect disimpan ke file terpisah: auto_blacklist.txt dan auto_kata_baru.txt.
       - TIDAK menyentuh atau merubah kamus resmi (kamus_kbbi.txt, kamus_contek.txt, kamus_lengkap.txt, blacklist.txt)
         agar data kurasi yang ada tetap aman dan murni dari kesalahan deteksi visual.
    """
    def __init__(self, config=None, solver=None, on_event_callback=None, base_dir=None):
        self.config = config or {}
        self.solver = solver
        self.on_event_callback = on_event_callback
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.sct = getattr(mss, "MSS", mss.mss)()

        # File terisolasi khusus auto-detect
        self.auto_blacklist_path = os.path.join(self.base_dir, "auto_blacklist.txt")
        self.auto_kata_baru_path = os.path.join(self.base_dir, "auto_kata_baru.txt")
        self.kalibrasi_dir = os.path.join(self.base_dir, "deteksi-gameplay", "sample_kalibrasi")
        os.makedirs(self.kalibrasi_dir, exist_ok=True)

        # RapidOCR engine fallback jika WinOCR tidak tersedia
        self.rapid_engine = RapidOCR(params={'Global': {'use_angle_cls': False}}) if HAS_RAPIDOCR else None

        # State tracking
        self.last_typing_word = None
        self.last_typing_time = 0
        self.last_processed_word = None
        self.last_processed_state = None
        self.last_processed_time = 0

        # Riwayat aktivitas indexing dalam sesi
        self.history = []

    def update_config(self, config):
        self.config = config

    def capture_gameplay_area(self):
        """Mengambil screenshot crop area gameplay langsung via mss (cepat < 1ms)"""
        area = self.config.get("gameplay_area")
        if not area:
            return None
        try:
            monitor = {
                "top": int(area.get("top", 250)),
                "left": int(area.get("left", 740)),
                "width": int(area.get("width", 440)),
                "height": int(area.get("height", 400))
            }
            sct_img = self.sct.grab(monitor)
            img = np.array(sct_img)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception:
            return None

    def scan_once(self):
        """Melakukan 1 siklus scan area gameplay dan memproses hasilnya"""
        crop = self.capture_gameplay_area()
        if crop is None:
            return "IDLE", "", None
        return self.process_frame(crop, is_full_frame=False)

    def ocr_crop(self, img_bgr):
        """Menjalankan OCR cepat pada potongan kotak kata (menggunakan WinOCR atau fallback RapidOCR)"""
        lines = []
        if HAS_WINOCR:
            try:
                pil_img = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
                res = winocr.recognize_pil_sync(pil_img, lang='en')
                for line in res.get('lines', []):
                    t = line.get('text', '').strip()
                    if t:
                        lines.append(t)
                return lines
            except Exception:
                pass

        if self.rapid_engine:
            try:
                res, _ = self.rapid_engine(img_bgr)
                if res:
                    for item in res:
                        t = item[1].strip()
                        if t:
                            lines.append(t)
            except Exception:
                pass

        return lines

    def process_crop(self, crop):
        """
        Menganalisis satu frame crop area gameplay (lebar ~440, tinggi ~400):
        Bagian atas (y: 0..180): Kotak kata dan subtext
        Bagian bawah (y: 70..400): Karakter pemain
        """
        if crop is None or crop.shape[0] < 100 or crop.shape[1] < 100:
            return "IDLE", "", {}

        H, W = crop.shape[:2]

        # 1. Analisis Tubuh Karakter Pemain (Piksel Hijau)
        char_roi = crop[int(H * 0.18):H, int(W * 0.12):int(W * 0.88)]
        char_hsv = cv2.cvtColor(char_roi, cv2.COLOR_BGR2HSV)
        green_mask = cv2.inRange(char_hsv, np.array([35, 80, 80]), np.array([85, 255, 255]))
        green_count = np.count_nonzero(green_mask)
        is_char_green = (green_count > 10000)

        # 2. Analisis Kotak Kata & Subtext di bagian atas
        word_h = min(H, 180)
        word_roi = crop[0:word_h, :]
        raw_lines = self.ocr_crop(word_roi)

        # Deteksi warna kotak kata di area tengah (y: 20..90, x: 25%..75% W)
        box_y1, box_y2 = int(word_h * 0.15), int(word_h * 0.55)
        box_x1, box_x2 = int(W * 0.22), int(W * 0.78)
        box_sample = word_roi[box_y1:box_y2, box_x1:box_x2]

        b, g, r = box_sample.mean(axis=(0, 1))
        b_int, g_int, r_int = cv2.split(box_sample.astype(np.int16))
        redness = r_int - np.maximum(b_int, g_int)
        red_count = np.count_nonzero(redness > 35)

        is_box_red = (red_count > 1000 and r > 100 and r > g * 1.3)
        is_box_white = (r > 150 and g > 150 and b > 150 and abs(r - g) < 30)

        full_text_lower = " ".join(raw_lines).lower()
        has_sudah_digunakan = (
            'sud' in full_text_lower or
            'guna' in full_text_lower or
            'pakai' in full_text_lower or
            len(raw_lines) >= 2
        )

        main_word = ""
        for line in raw_lines:
            clean = "".join(c for c in line if c.isalpha()).upper()
            if len(clean) >= 2 and not any(k in clean.lower() for k in ['sudah', 'guna', 'pakai', 'sud']):
                main_word = clean
                break

        # Tentukan status
        state = "IDLE"
        if is_box_red:
            if has_sudah_digunakan:
                state = "SUDAH_DIGUNAKAN"
            else:
                state = "KATA_SALAH"
        elif is_box_white and main_word:
            state = "SEDANG_KETIK"
        elif not main_word and is_char_green and self.last_typing_word:
            state = "KATA_BENAR"
            main_word = self.last_typing_word

        details = {
            'is_box_red': is_box_red,
            'is_box_white': is_box_white,
            'green_count': green_count,
            'red_count': red_count,
            'raw_lines': raw_lines
        }

        return state, main_word, details

    def save_to_auto_blacklist(self, word):
        """Menyimpan kata salah ke auto_blacklist.txt terisolasi"""
        w = word.strip().lower()
        if not w or len(w) < 2:
            return False
        existing = set()
        if os.path.exists(self.auto_blacklist_path):
            try:
                with open(self.auto_blacklist_path, "r", encoding="utf-8") as f:
                    for line in f:
                        item = line.strip().split("#")[0].strip().lower()
                        if item:
                            existing.add(item)
            except Exception:
                pass
        if w in existing:
            return False

        try:
            with open(self.auto_blacklist_path, "a", encoding="utf-8") as f:
                f.write(f"{w}  # Ditolak Roblox {datetime_now_str()}\n")
            return True
        except Exception:
            return False

    def save_to_auto_kata_baru(self, word, reason="Valid di Roblox"):
        """Menyimpan kata baru ke auto_kata_baru.txt terisolasi"""
        w = word.strip().lower()
        if not w or len(w) < 2:
            return False
        existing = set()
        if os.path.exists(self.auto_kata_baru_path):
            try:
                with open(self.auto_kata_baru_path, "r", encoding="utf-8") as f:
                    for line in f:
                        item = line.strip().split("#")[0].strip().lower()
                        if item:
                            existing.add(item)
            except Exception:
                pass
        if w in existing:
            return False

        try:
            with open(self.auto_kata_baru_path, "a", encoding="utf-8") as f:
                f.write(f"{w}  # {reason} {datetime_now_str()}\n")
            return True
        except Exception:
            return False

    def capture_kalibrasi_sample(self, label="manual", note=""):
        """
        Menyimpan snapshot visual gameplay saat ini beserta metadata lengkap
        ke folder deteksi-gameplay/sample_kalibrasi/ untuk bahan kalibrasi akurasi lanjutan.
        """
        crop = self.capture_gameplay_area()
        if crop is None:
            return None
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        state, word, details = self.process_crop(crop)
        fn_base = f"{timestamp}_{label}_{state}_{word or 'EMPTY'}"
        img_path = os.path.join(self.kalibrasi_dir, f"{fn_base}.png")
        meta_path = os.path.join(self.kalibrasi_dir, f"{fn_base}.json")

        cv2.imwrite(img_path, crop)
        meta = {
            "timestamp": timestamp,
            "label": label,
            "state_detected": state,
            "word_detected": word,
            "details": {
                "is_box_red": bool(details.get("is_box_red", False)),
                "is_box_white": bool(details.get("is_box_white", False)),
                "green_count": int(details.get("green_count", 0)),
                "red_count": int(details.get("red_count", 0)),
                "raw_lines": details.get("raw_lines", [])
            },
            "note": note
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=4)
        except Exception:
            pass
        return img_path

    def process_frame(self, frame_or_crop, is_full_frame=False):
        """
        Memproses frame/crop dan melakukan tindakan auto-blacklist atau auto-learn jika memenuhi syarat.
        Hasil disimpan ke file terisolasi (auto_blacklist.txt / auto_kata_baru.txt).
        """
        now = time.time()
        
        if is_full_frame and frame_or_crop is not None:
            area = self.config.get("gameplay_area")
            if not area:
                H, W = frame_or_crop.shape[:2]
                area = {
                    "left": int(W * 0.385),
                    "top": int(H * 0.208),
                    "width": int(W * 0.230),
                    "height": int(H * 0.333)
                }
            x = max(0, int(area.get("left", 740)))
            y = max(0, int(area.get("top", 250)))
            w = int(area.get("width", 440))
            h = int(area.get("height", 400))
            crop = frame_or_crop[y:y+h, x:x+w]
        else:
            crop = frame_or_crop

        state, word, details = self.process_crop(crop)

        # 1. Update state SEDANG_KETIK
        if state == "SEDANG_KETIK" and word:
            self.last_typing_word = word
            self.last_typing_time = now
            return state, word, None

        # Debounce: Jangan proses kata yang sama dalam jeda waktu < 2.5 detik
        is_same_recent_event = (
            word == self.last_processed_word and
            state == self.last_processed_state and
            (now - self.last_processed_time) < 2.5
        )

        action_taken = None

        # 2. Aksi KATA_SALAH (Catat ke auto_blacklist.txt)
        if state == "KATA_SALAH" and word and len(word) >= 2 and not is_same_recent_event:
            self.last_processed_word = word
            self.last_processed_state = state
            self.last_processed_time = now

            auto_bl = self.config.get("auto_blacklist_invalid", True)
            if auto_bl:
                success = self.save_to_auto_blacklist(word)
                action_taken = "AUTO_BLACKLISTED" if success else "ALREADY_IN_AUTO_BLACKLIST"
            else:
                action_taken = "DETECTED_WRONG"

            log_entry = {
                "time": datetime_now_str(),
                "state": "KATA_SALAH",
                "word": word,
                "action": action_taken,
                "detail": "Ditolak game Roblox -> dicatat ke auto_blacklist.txt"
            }
            self.history.append(log_entry)

            if self.on_event_callback:
                self.on_event_callback("KATA_SALAH", word, action_taken, log_entry)

        # 3. Aksi SUDAH_DIGUNAKAN (Catat ke auto_kata_baru.txt jika belum ada di kamus)
        elif state == "SUDAH_DIGUNAKAN" and word and len(word) >= 2 and not is_same_recent_event:
            self.last_processed_word = word
            self.last_processed_state = state
            self.last_processed_time = now

            auto_learn = self.config.get("auto_learn_valid", True)
            already_has = self.solver.has_word(word) if self.solver else False
            
            if not already_has and auto_learn:
                success = self.save_to_auto_kata_baru(word, reason="Sudah digunakan di Roblox")
                action_taken = "AUTO_LEARNED" if success else "ALREADY_IN_AUTO_NEW"
            else:
                action_taken = "KNOWN_IN_OFFICIAL_DICT"

            log_entry = {
                "time": datetime_now_str(),
                "state": "SUDAH_DIGUNAKAN",
                "word": word,
                "action": action_taken,
                "detail": "Kata valid Roblox (sudah dipakai putaran ini)"
            }
            self.history.append(log_entry)

            if self.on_event_callback:
                self.on_event_callback("SUDAH_DIGUNAKAN", word, action_taken, log_entry)

        # 4. Aksi KATA_BENAR (Catat ke auto_kata_baru.txt jika belum ada di kamus)
        elif state == "KATA_BENAR" and word and len(word) >= 2 and not is_same_recent_event:
            self.last_processed_word = word
            self.last_processed_state = state
            self.last_processed_time = now
            self.last_typing_word = None

            auto_learn = self.config.get("auto_learn_valid", True)
            already_has = self.solver.has_word(word) if self.solver else False

            if not already_has and auto_learn:
                success = self.save_to_auto_kata_baru(word, reason="Jawaban benar Roblox")
                action_taken = "AUTO_LEARNED" if success else "ALREADY_IN_AUTO_NEW"
            else:
                action_taken = "KNOWN_IN_OFFICIAL_DICT"

            log_entry = {
                "time": datetime_now_str(),
                "state": "KATA_BENAR",
                "word": word,
                "action": action_taken,
                "detail": "Jawaban diterima Roblox (karakter flash hijau)"
            }
            self.history.append(log_entry)

            if self.on_event_callback:
                self.on_event_callback("KATA_BENAR", word, action_taken, log_entry)

        return state, word, action_taken


def datetime_now_str():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")
