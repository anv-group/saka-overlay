import os
import re
import time
from datetime import datetime
import cv2
import numpy as np
import mss
from PIL import Image, ImageDraw, ImageFont

# Coba import rapidocr
try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False

# Coba import winocr sebagai fallback
try:
    import winocr
    HAS_WINOCR = True
except ImportError:
    HAS_WINOCR = False


class OCREngine:
    def __init__(self, config=None):
        self.config = config or {}
        self.sct = mss.mss()
        self.engine = RapidOCR(params={'Global': {'use_angle_cls': False}}) if HAS_RAPIDOCR else None
        self.templates = {}
        self.last_saved_time = 0
        self.last_saved_hash = None

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.unknown_dir = os.path.join(base_dir, "sample", "tidak_dikenali")
        os.makedirs(self.unknown_dir, exist_ok=True)
        self.kurang_tepat_dir = os.path.join(base_dir, "sample", "kurang_tepat")
        os.makedirs(self.kurang_tepat_dir, exist_ok=True)

        self.last_captured_image = None
        self.last_detection_result = None

        self._init_templates()

    def update_config(self, config):
        self.config = config
        self.last_frame_gray = None

    def _init_templates(self):
        """Membangun template huruf dari folder sample/1 dan sample/2 serta font sistem"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        sample_dir = os.path.join(base_dir, "sample")

        # 1. Muat dari sample/1 (A, F, G, I, K, L, M, N, O, P, Q, R, S, T, Y)
        p1 = os.path.join(sample_dir, "1")
        if os.path.exists(p1):
            for f in os.listdir(p1):
                if not f.endswith(".png"):
                    continue
                ch = os.path.splitext(f)[0].upper()
                im = cv2.imread(os.path.join(p1, f), cv2.IMREAD_GRAYSCALE)
                if im is None:
                    continue
                g = self._extract_glyph_from_single(im)
                if g is not None:
                    self.templates[ch] = g

        # 2. Muat C, D, E, J, U, X, H dari sample/2
        p2 = os.path.join(sample_dir, "2")
        if os.path.exists(p2):
            self._add_from_split(p2, "CI.png", ("C", "I"))
            self._add_from_split(p2, "DA.png", ("D", "A"))
            self._add_from_split(p2, "EX.png", ("E", "X"))
            self._add_from_split(p2, "JI.png", ("J", "I"))
            self._add_from_split(p2, "UH.png", ("U", "H"))
            self._add_from_split(p2, "NG.png", ("N", "G"))

        # 3. Buat template huruf yang belum ada (B, C, V, W, Z) menggunakan font sistem
        all_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        missing = [c for c in all_letters if c not in self.templates]
        if missing:
            self._generate_synthetic_templates(missing)

    def _extract_glyph_from_single(self, img_gray):
        _, thresh = cv2.threshold(img_gray, 180, 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        c = max(cnts, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)
        wb = img_gray[y+6:y+h-6, x+6:x+w-6]
        if wb.size == 0:
            return None
        _, bin_w = cv2.threshold(wb, 130, 255, cv2.THRESH_BINARY_INV)
        ty, tx = np.where(bin_w > 0)
        if len(ty) == 0:
            return None
        crop = bin_w[ty.min():ty.max()+1, tx.min():tx.max()+1]
        return cv2.resize(crop, (28, 28), interpolation=cv2.INTER_AREA)

    def _add_from_split(self, p2, f_name, chs):
        fpath = os.path.join(p2, f_name)
        if not os.path.exists(fpath):
            return
        im = cv2.imread(fpath, cv2.IMREAD_GRAYSCALE)
        if im is None:
            return
        _, th = cv2.threshold(im, 180, 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return
        c = max(cnts, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)
        wb = im[y+6:y+h-6, x+6:x+w-6]
        if wb.size == 0:
            return
        _, bin_w = cv2.threshold(wb, 130, 255, cv2.THRESH_BINARY_INV)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(bin_w)
        comps = [(stats[i, 0], i) for i in range(1, n) if stats[i, 4] > 30 and stats[i, 3] > 10]
        comps.sort()
        if len(comps) == 2:
            for idx, (_, comp_idx) in enumerate(comps):
                ch = chs[idx]
                if ch not in self.templates:
                    mask = (lab == comp_idx).astype(np.uint8) * 255
                    ty, tx = np.where(mask > 0)
                    if len(ty) > 0:
                        crop = mask[ty.min():ty.max()+1, tx.min():tx.max()+1]
                        self.templates[ch] = cv2.resize(crop, (28, 28), interpolation=cv2.INTER_AREA)

    def _generate_synthetic_templates(self, letters):
        """Merender huruf yang belum ada sampelnya menggunakan font Windows"""
        font_path = r"C:\Windows\Fonts\arialbd.ttf"
        if not os.path.exists(font_path):
            font_path = r"C:\Windows\Fonts\segoeuib.ttf"
        if not os.path.exists(font_path):
            return

        font = ImageFont.truetype(font_path, 34)
        for ch in letters:
            canvas = Image.new("L", (50, 50), color=0)
            d = ImageDraw.Draw(canvas)
            bbox = d.textbbox((0, 0), ch, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            ox = (50 - tw) // 2 - bbox[0]
            oy = (50 - th) // 2 - bbox[1]
            d.text((ox, oy), ch, fill=255, font=font)
            arr = np.array(canvas)
            ty, tx = np.where(arr > 0)
            if len(ty) > 0:
                crop = arr[ty.min():ty.max()+1, tx.min():tx.max()+1]
                self.templates[ch] = cv2.resize(crop, (28, 28), interpolation=cv2.INTER_AREA)

    def _match_single_crop(self, crop, orig_w):
        """
        Mencocokkan satu potongan huruf dengan template dan mengembalikan:
        (best_char, confidence_score, alternatives_list)
        """
        # Huruf 'I' di font Roblox adalah garis lurus tipis (lebar <= 12px)
        if orig_w <= 12:
            return "I", 0.99, []

        norm = cv2.resize(crop, (28, 28), interpolation=cv2.INTER_AREA)
        scores = {}
        for ch, tmpl in self.templates.items():
            if ch == "I":
                continue
            score = cv2.matchTemplate(norm, tmpl, cv2.TM_CCOEFF_NORMED)[0][0]
            scores[ch] = float(score)

        sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_ch, best_score = sorted_scores[0]
        alternatives = [ch for ch, s in sorted_scores[1:4] if s > 0.52 and ch != best_ch]

        # ----------------- Aturan Disambiguasi Fitur Struktur -----------------
        # 1. Pembeda D vs O vs U:
        # Huruf D memiliki garis vertikal tebal lurus di 4 kolom kiri DAN bagian atas tengah tertutup
        if best_ch in ["O", "D"] or "D" in alternatives:
            left_mean = crop[:, :4].mean()
            top_center = crop[:6, int(crop.shape[1]*0.3):int(crop.shape[1]*0.7)].mean()
            if left_mean > 190 and top_center > 120:
                best_ch = "D"
                best_score = max(best_score, 0.92)

        # Jika sebelumnya salah terprediksi D tapi bagian atasnya terbuka (seperti U)
        if best_ch == "D":
            top_center = crop[:6, int(crop.shape[1]*0.3):int(crop.shape[1]*0.7)].mean()
            if top_center < 80:
                best_ch = "U"

        # 2. Pembeda G vs C vs O:
        # Huruf G dan C keduanya terbuka di kanan atas (ur_mean < 110)
        # Huruf G memiliki tiang/stem vertikal tebal di kanan bawah (x > 70%, y: 45%-75%) dengan densitas tinggi (> 90)
        # Huruf C TIDAK memiliki tiang di kanan (densitas < 60)
        if best_ch in ["O", "G", "C"] or "G" in alternatives or "C" in alternatives:
            h, w = crop.shape
            ur_mean = crop[int(h*0.15):int(h*0.45), int(w*0.75):].mean()
            r_stem = crop[int(h*0.45):int(h*0.75), int(w*0.70):].mean()
            if ur_mean < 110:  # Kanan atas terbuka
                if r_stem < 60:
                    best_ch = "C"
                    best_score = max(best_score, 0.94)
                elif r_stem > 90:
                    best_ch = "G"
                    best_score = max(best_score, 0.94)

        # 3. Pembeda Q vs O: Huruf Q memiliki ekor di kanan bawah (tinggi > 39px atau tail density tinggi)
        if best_ch in ["O", "Q"] or "Q" in alternatives:
            h, w = crop.shape
            tail = crop[int(h*0.80):, int(w*0.70):]
            if h >= 41 or tail.mean() > 115:
                best_ch = "Q"
                best_score = max(best_score, 0.92)

        # 4. Pembeda W vs U: Huruf W jauh lebih lebar (lebar >= 32px) dibanding U (lebar <= 27px)
        if best_ch in ["U", "W"] or "W" in alternatives:
            if orig_w >= 32:
                best_ch = "W"
                best_score = max(best_score, 0.92)

        return best_ch, best_score, alternatives

    def capture_screen_area(self, area):
        """Mengambil screenshot dari area layar ROI"""
        bbox = {
            "top": int(area["top"]),
            "left": int(area["left"]),
            "width": int(area["width"]),
            "height": int(area["height"])
        }
        sct_img = self.sct.grab(bbox)
        img_np = np.array(sct_img)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
        return img_bgr

    def auto_save_unknown(self, img_bgr, detected_text, confidence):
        """Menyimpan screenshot ke folder sample/tidak_dikenali jika keyakinan rendah"""
        now = time.time()
        # Batasi penyimpanan maksimal 1 gambar per 1.5 detik
        if now - self.last_saved_time < 1.5:
            return None

        # Cek apakah gambar berbeda dari sebelumnya untuk menghindari duplikasi
        curr_hash = hash(img_bgr.tobytes()[::100])
        if curr_hash == self.last_saved_hash:
            return None

        self.last_saved_time = now
        self.last_saved_hash = curr_hash

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = detected_text if detected_text else "UNKNOWN"
        filename = f"{ts}_{label}_{int(confidence*100)}pct.png"
        save_path = os.path.join(self.unknown_dir, filename)

        try:
            cv2.imwrite(save_path, img_bgr)
            print(f"[!] Simpan gambar tidak yakin: {save_path}")
            return save_path
        except Exception as e:
            print(f"[!] Gagal menyimpan gambar: {e}")
            return None

    def _run_rapidocr_robust(self, box):
        """
        Menjalankan RapidOCR dengan multi-padding adaptif:
        - pad 8: Optimal untuk font Roblox (mencegah pemotongan huruf tepi seperti GOH, GAL)
        - pad 0: Direct crop (terbaik jika padding mengaburkan batas teks seperti OXO)
        - pad 15: Margin sedang untuk variasi skala
        - pad 20: Margin lebar untuk kata kompak seperti DIH
        """
        best_res = None
        for pad in [8, 0, 15, 20]:
            if pad == 0:
                target = box
            else:
                target = cv2.copyMakeBorder(box, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=[255, 255, 255])
            res, _ = self.engine(target)
            if res:
                raw = "".join([item[1] for item in res])
                scores = [float(item[2]) for item in res]
                conf = float(np.mean(scores)) if scores else 0.8
                repl = {'0': 'O', '1': 'I', '5': 'S', '8': 'B', '|': 'I', 'l': 'I'}
                clean = "".join([repl.get(c, c) for c in raw.upper()])
                clean = re.sub(r'[^A-Z]', '', clean)
                # Early exit jika kata 3 huruf atau kata valid panjang dengan confidence tinggi
                if (len(clean) == 3 and conf >= 0.50) or (len(clean) >= 2 and conf >= 0.70):
                    return clean, conf
                if best_res is None or len(clean) > len(best_res[0]) or (len(clean) == len(best_res[0]) and conf > best_res[1]):
                    best_res = (clean, conf)
        return best_res if best_res else ("", 0.0)

    def recognize_game_prompt(self, img_bgr, auto_save=True):
        """
        Mendeteksi teks awalan dengan mengembalikan:
        dict: {
            'text': str,
            'confidence': float,
            'is_low_confidence': bool,
            'alternatives': list,
            'saved_path': str or None
        }
        """
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        # Cari kontur kotak putih di dalam gambar
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_c = max(cnts, key=cv2.contourArea) if cnts else None
        # Jika kotak terpotong (bh < 44) karena gradient/shading atas tombol Roblox
        if best_c is not None:
            bx, by, bw, bh = cv2.boundingRect(best_c)
            if bh < 44:
                _, thresh_low = cv2.threshold(gray, 145, 255, cv2.THRESH_BINARY)
                cnts_low, _ = cv2.findContours(thresh_low, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if cnts_low:
                    best_low = max(cnts_low, key=cv2.contourArea)
                    lx, ly, lw, lh = cv2.boundingRect(best_low)
                    if lh > bh:
                        best_c = best_low

        box = img_bgr
        if best_c is not None:
            area = cv2.contourArea(best_c)
            if area > 300:
                x, y, w, h = cv2.boundingRect(best_c)
                box = img_bgr[max(0, y+1):min(img_bgr.shape[0], y+h-1), max(0, x):min(img_bgr.shape[1], x+w)]

        box_gray = cv2.cvtColor(box, cv2.COLOR_BGR2GRAY)
        bh, bw = box_gray.shape

        if bh > 12 and bw > 12:
            wb = box_gray[max(1, int(bh*0.1)):bh-max(1, int(bh*0.1)), max(1, int(bw*0.06)):bw-max(1, int(bw*0.06))]
            _, bin_w = cv2.threshold(wb, 130, 255, cv2.THRESH_BINARY_INV)
            n, lab, stats, _ = cv2.connectedComponentsWithStats(bin_w)
            comps = [(stats[i, 0], stats[i, 2], i) for i in range(1, n) if stats[i, 4] > 25 and stats[i, 3] > 10]
            comps.sort()

            # Jika comps pendek (terpotong vertikal karena shading lokal), coba Otsu di dalam wb
            if len(comps) == 0 or all(stats[c[2], 3] < 18 for c in comps):
                _, bin_w = cv2.threshold(wb, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                n, lab, stats, _ = cv2.connectedComponentsWithStats(bin_w)
                comps = [(stats[i, 0], stats[i, 2], i) for i in range(1, n) if stats[i, 4] > 25 and stats[i, 3] > 10]
                comps.sort()

            # Slicing cerdas untuk huruf yang bersentuhan (misal 'KA' di 'KAR' atau 'AKAN')
            if len(comps) < 4 and any(48 <= c[1] <= 68 for c in comps):
                split_comps = []
                for c in comps:
                    cx, cw, idx = c[0], c[1], c[2]
                    if 48 <= cw <= 68:
                        mask = (lab == idx).astype(np.uint8)
                        ty, tx = np.where(mask > 0)
                        x_min, x_max = tx.min(), tx.max()
                        proj = np.sum(mask > 0, axis=0)
                        search_start = x_min + int(cw * 0.3)
                        search_end = x_min + int(cw * 0.7)
                        dip_idx = search_start + int(np.argmin(proj[search_start:search_end]))
                        split_comps.append((x_min, dip_idx - x_min, idx, (x_min, dip_idx)))
                        split_comps.append((dip_idx, x_max - dip_idx, idx, (dip_idx, x_max)))
                    else:
                        split_comps.append((cx, cw, idx, None))
                comps = split_comps

            # Tentukan apakah 1, 2, atau 3-4 huruf terpisah bersih
            # Catatan: Huruf 'W' memiliki lebar hingga 43px, 'M' hingga 38px.
            is_separated = False
            if len(comps) in [1, 2] and all(c[1] < 48 for c in comps):
                is_separated = True
            elif len(comps) in [3, 4] and all(c[1] < 44 for c in comps):
                is_separated = True

            if is_separated:
                chars = []
                scores = []
                alts = []
                for c in comps:
                    idx = c[2]
                    mask = (lab == idx).astype(np.uint8) * 255
                    if len(c) >= 4 and c[3] is not None:
                        x0, x1 = c[3]
                        crop = mask[:, x0:x1]
                    else:
                        crop = mask
                    ty, tx = np.where(crop > 0)
                    if len(ty) > 0:
                        crop = crop[ty.min():ty.max()+1, tx.min():tx.max()+1]
                        ch, score, alt = self._match_single_crop(crop, crop.shape[1])
                        chars.append(ch)
                        scores.append(score)
                        alts.extend(alt)
                
                text = "".join(chars)
                conf = float(np.mean(scores)) if scores else 0.5
                # Jika 3 atau 4 huruf, pastikan rata-rata confidence template matching tinggi (>= 0.75)
                # agar jika ambigu tetap dapat beralih ke RapidOCR
                if len(text) in [1, 2] or (len(text) >= 3 and conf >= 0.75):
                    is_low = conf < 0.65
                    saved_path = self.auto_save_unknown(img_bgr, text, conf) if (auto_save and is_low) else None
                    return {
                        "text": text,
                        "confidence": conf,
                        "is_low_confidence": is_low,
                        "alternatives": list(set(alts)),
                        "saved_path": saved_path
                    }

        # Kasus 3 huruf atau huruf menempel / kotak lebar: Gunakan RapidOCR multi-padding
        if self.engine:
            text, conf = self._run_rapidocr_robust(box)
            if text:
                is_low = conf < 0.48
                saved_path = self.auto_save_unknown(img_bgr, text, conf) if (auto_save and is_low) else None
                return {
                    "text": text,
                    "confidence": conf,
                    "is_low_confidence": is_low,
                    "alternatives": [],
                    "saved_path": saved_path
                }

        # Fallback jika OCR kosong
        saved_path = self.auto_save_unknown(img_bgr, "EMPTY", 0.0) if auto_save else None
        return {
            "text": "",
            "confidence": 0.0,
            "is_low_confidence": True,
            "alternatives": [],
            "saved_path": saved_path
        }

    def save_to_kurang_tepat(self, img_bgr=None, detected_text=None, confidence=None, correct_text=None):
        """
        Menyimpan screenshot ROI/kotak ke folder sample/kurang_tepat secara manual.
        Bisa dipanggil saat spectate/main ketika deteksi salah meskipun confidence tinggi.
        """
        target_img = img_bgr if img_bgr is not None else self.last_captured_image
        if target_img is None:
            area = self.config.get("screen_area")
            if area:
                target_img = self.capture_screen_area(area)
                self.last_captured_image = target_img

        if target_img is None:
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = (detected_text or (self.last_detection_result.get("text") if self.last_detection_result else "") or "UNKNOWN").upper()
        
        if confidence is None and self.last_detection_result:
            confidence = self.last_detection_result.get("confidence", 1.0)
            
        conf_str = f"{int(confidence*100)}pct" if confidence is not None else "manual"
        
        if correct_text and correct_text.strip():
            corr_clean = re.sub(r'[^A-Z]', '', correct_text.upper().strip())
            filename = f"{ts}_{label}_seharusnya_{corr_clean}_{conf_str}.png"
        else:
            filename = f"{ts}_{label}_{conf_str}.png"

        save_path = os.path.join(self.kurang_tepat_dir, filename)
        try:
            cv2.imwrite(save_path, target_img)
            print(f"[!] Simpan manual ke kurang_tepat: {save_path}")
            return save_path
        except Exception as e:
            print(f"[!] Gagal menyimpan ke kurang_tepat: {e}")
            return None

    def scan_once(self):
        """Mengambil screenshot 1x dan mengembalikan info deteksi lengkap"""
        area = self.config.get("screen_area")
        if not area:
            return {"text": "", "confidence": 0.0, "is_low_confidence": False, "alternatives": []}
        img_bgr = self.capture_screen_area(area)
        self.last_captured_image = img_bgr

        # Fast frame-diff check: jika ROI tidak berubah sama sekali (< 1.0 diff)
        # langsung kembalikan hasil sebelumnya (hanya butuh 0.02ms, hemat CPU)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        if getattr(self, "last_frame_gray", None) is not None and self.last_frame_gray.shape == gray.shape:
            diff = cv2.absdiff(gray, self.last_frame_gray)
            if np.mean(diff) < 1.0 and self.last_detection_result is not None:
                return self.last_detection_result
        self.last_frame_gray = gray

        res = self.recognize_game_prompt(img_bgr)
        self.last_detection_result = res
        return res
