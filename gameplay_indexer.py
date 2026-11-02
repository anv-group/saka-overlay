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

        # Fallback solver jika tidak diinjeksi
        if self.solver is None:
            try:
                from solver import SambungKataSolver
                self.solver = SambungKataSolver()
            except Exception:
                self.solver = None

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

    def clean_gameplay_word(self, word):
        """
        Membersihkan dan mengoreksi kata hasil OCR gameplay menggunakan kamus solver.
        Mengatasi kebingungan font Roblox: C vs G (contoh: AANCIN -> ANGIN, NENCOK -> NENGOK).
        """
        w = "".join(c for c in word if c.isalpha()).upper()
        if not w or len(w) < 2:
            return ""

        if not self.solver:
            return w

        # 1. Jika sudah ada di kamus persis seperti ini
        if self.solver.has_word(w):
            return w

        # 2. Coba ganti "NC" -> "NG" (karena C sering keliru dibaca dari G)
        if "NC" in w:
            cand_ng = w.replace("NC", "NG")
            if self.solver.has_word(cand_ng):
                return cand_ng
            # Cek jika ada double vocal awal berlebih, misal AANCIN -> AANGIN -> ANGIN
            if cand_ng.startswith("AA") and self.solver.has_word(cand_ng[1:]):
                return cand_ng[1:]

        # 3. Coba ganti semua 'C' menjadi 'G'
        if "C" in w:
            cand_g = w.replace("C", "G")
            if self.solver.has_word(cand_g):
                return cand_g
            # Coba ganti per karakter C -> G
            for i, char in enumerate(w):
                if char == 'C':
                    cand = w[:i] + 'G' + w[i+1:]
                    if self.solver.has_word(cand):
                        return cand

        # 4. Coba sebaliknya 'G' -> 'C' jika w tidak ada di kamus
        if "G" in w:
            cand_c = w.replace("G", "C")
            if self.solver.has_word(cand_c):
                return cand_c
            for i, char in enumerate(w):
                if char == 'G':
                    cand = w[:i] + 'C' + w[i+1:]
                    if self.solver.has_word(cand):
                        return cand

        # 5. Cek double vokal awal berlebih akibat border font (misal AANGIN -> ANGIN)
        if len(w) >= 3 and w[0] == w[1] and self.solver.has_word(w[1:]):
            return w[1:]

        return w

    def find_gameplay_box(self, crop):
        """
        Mendeteksi posisi kotak kata (putih atau merah) secara presisi.
        Mengembalikan: (box_crop, box_type, box_rect)
        - box_type: 'WHITE' (sedang mengetik), 'RED' (salah/sudah dipakai), atau None
        Mencegah OCR membaca spanduk/background arena Roblox.
        """
        if crop is None or crop.shape[0] < 80 or crop.shape[1] < 80:
            return None, None, None

        H, W = crop.shape[:2]
        word_h = min(H, int(H * 0.60))
        upper_roi = crop[:word_h, :]
        gray = cv2.cvtColor(upper_roi, cv2.COLOR_BGR2GRAY)

        # 1. Cek Kotak Putih (Sedang Mengetik)
        _, thresh_w = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        cnts_w, _ = cv2.findContours(thresh_w, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in cnts_w:
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            norm_cx = (x + w / 2.0) / W
            # Wajib berada di area tengah horizontal karakter (mengabaikan banner samping)
            if not (0.35 <= norm_cx <= 0.65):
                continue
            if w >= 55 and 30 <= h <= 140 and 0.9 <= (w / h) <= 5.5 and area >= 2000:
                box_sample = upper_roi[y:y+h, x:x+w]
                b, g, r = box_sample.mean(axis=(0, 1))
                if r > 175 and g > 175 and b > 175 and abs(r - g) < 25 and abs(g - b) < 25:
                    return box_sample, 'WHITE', (x, y, w, h)

        # 2. Cek Kotak Merah (Kata Salah / Sudah Dipakai)
        br_b, br_g, br_r = cv2.split(upper_roi.astype(np.int16))
        pure_red = (br_r > 135) & (br_g < 100) & (br_b < 100)
        cnts_r, _ = cv2.findContours(pure_red.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for c in cnts_r:
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            norm_cx = (x + w / 2.0) / W
            # Wajib berada di area tengah horizontal karakter (mengabaikan timer & 'X' samping)
            if not (0.35 <= norm_cx <= 0.65):
                continue
            if w >= 55 and 30 <= h <= 140 and 0.9 <= (w / h) <= 5.5 and area >= 2000:
                box_sample = upper_roi[y:y+h, x:x+w]
                return box_sample, 'RED', (x, y, w, h)

        return None, None, None

    def process_crop(self, crop):
        """
        Menganalisis satu frame area gameplay secara cerdas:
        1. Kotak kata dipotong secara presisi (HANYA membaca isi dalam kotak, isolasi dari background arena).
        2. Karakter pemain dianalisis kilatan flash hijaunya saat kata benar.
        """
        if crop is None or crop.shape[0] < 100 or crop.shape[1] < 100:
            return "IDLE", "", {}

        H, W = crop.shape[:2]

        # 1. Analisis Tubuh Karakter Pemain (Piksel Hijau saat flash jawaban benar)
        char_roi = crop[int(H * 0.22):H, int(W * 0.15):int(W * 0.85)]
        char_hsv = cv2.cvtColor(char_roi, cv2.COLOR_BGR2HSV)
        green_mask = cv2.inRange(char_hsv, np.array([35, 70, 70]), np.array([85, 255, 255]))
        green_count = int(np.count_nonzero(green_mask))
        is_char_green = (green_count > 5000)

        # 2. Deteksi Kotak Kata (Putih / Merah)
        box_crop, box_type, box_rect = self.find_gameplay_box(crop)

        raw_lines = []
        main_word = ""
        has_sudah_digunakan = False

        if box_crop is not None:
            # Jalankan OCR HANYA di dalam potongan kotak kata yang ditemukan (100% bebas dari background)
            raw_lines = self.ocr_crop(box_crop)
            for line in raw_lines:
                clean = "".join(c for c in line if c.isalpha()).upper()
                if 2 <= len(clean) <= 12 and not any(k in clean.lower() for k in ['sudah', 'guna', 'pakai', 'sud', 'buy', 'gift', 'cift']):
                    main_word = self.clean_gameplay_word(clean)
                    break

            # Jika kotak merah, periksa teks subtext di bawah kotak merah (y+h sampai y+h+80)
            if box_type == 'RED':
                x, y, w, h = box_rect
                sub_y1, sub_y2 = y + h, min(H, y + h + 80)
                sub_roi = crop[sub_y1:sub_y2, max(0, x - 40):min(W, x + w + 40)]
                if sub_roi.shape[0] >= 15 and sub_roi.shape[1] >= 40:
                    sub_lines = self.ocr_crop(sub_roi)
                    sub_text = " ".join(sub_lines).lower()
                    has_sudah_digunakan = any(k in sub_text for k in ['sud', 'guna', 'pakai', 'diguna', 'sudah', 'sudan', 'igun', 'iguy', 'vour'])

        # 3. Tentukan status
        state = "IDLE"

        # PRIORITAS 1: KATA_BENAR (Tubuh karakter flash hijau saat kata diterima game)
        # Karakter Roblox HANYA menyala hijau jika kata benar, mengabaikan segala sisa warna merah di arena
        if is_char_green and self.last_typing_word:
            state = "KATA_BENAR"
            main_word = self.last_typing_word
            self.last_typing_word = None
        elif box_type == 'RED':
            # Jika teks di dalam kotak merah sedang pudar/animasi, gunakan kata yang baru saja diketik
            if not main_word and self.last_typing_word:
                main_word = self.last_typing_word
            if has_sudah_digunakan:
                state = "SUDAH_DIGUNAKAN"
            else:
                state = "KATA_SALAH"
            self.last_typing_word = None
        elif box_type == 'WHITE' and main_word:
            state = "SEDANG_KETIK"
            self.last_typing_word = main_word

        details = {
            'box_type': box_type,
            'is_char_green': is_char_green,
            'green_count': green_count,
            'main_word': main_word,
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
