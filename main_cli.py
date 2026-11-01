import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from solver import SambungKataSolver
from ocr_engine import OCREngine
from config import load_config

def main():
    print("=" * 60)
    print("      ⚔️ ROBLOX SAMBUNG KATA BOT - TERMINAL MODE ⚔️")
    print("=" * 60)

    config = load_config()
    solver = SambungKataSolver("kamus_lengkap.txt")
    ocr = OCREngine(config)

    area = config["screen_area"]
    print(f"[*] Area Layar: Left={area['left']}, Top={area['top']}, Width={area['width']}, Height={area['height']}")
    print(f"[*] Interval Scan: {config.get('scan_interval_sec', 1.2)} detik")
    print("[*] Mulai memantau layar Roblox... (Tekan Ctrl + C untuk berhenti)\n")

    last_detected = ""

    try:
        while True:
            res_data = ocr.scan_once()
            detected_prefix = res_data.get("text", "")
            conf = res_data.get("confidence", 0.0)
            is_low = res_data.get("is_low_confidence", False)
            alts = res_data.get("alternatives", [])
            saved_path = res_data.get("saved_path", None)

            if detected_prefix and detected_prefix != last_detected:
                last_detected = detected_prefix

                status_tag = f"Akurasi: {conf*100:.0f}% [✅ Tinggi]" if not is_low else f"Akurasi: {conf*100:.0f}% [⚠️ Rendah]"
                print(f"\n[!] Awalan Terdeteksi: '{detected_prefix.upper()}' | {status_tag}")
                if is_low and saved_path:
                    print(f"    [📷] Cuplikan disimpan ke: {saved_path}")
                if alts:
                    print(f"    [?] Alternatif kemungkinan: {alts}")
                print("-" * 50)

                recoms = solver.cari_jawaban(detected_prefix, limit=10)
                if recoms:
                    for idx, item in enumerate(recoms, 1):
                        tag = ""
                        if item["tipe"] == "JEBAKAN_X":
                            tag = " [💥 JEBAKAN AKHIRAN X]"
                        elif item["tipe"] == "JEBAKAN_SULIT":
                            tag = f" [⚡ {item['deskripsi']}]"

                        print(f"  {idx}. {item['kata'].upper()}{tag}")
                else:
                    print(f"  [X] Tidak ada kata di kamus yang berawalan '{detected_prefix.upper()}'!")

                print("-" * 50)

            time.sleep(config.get("scan_interval_sec", 1.2))

    except KeyboardInterrupt:
        print("\n[*] Bot dihentikan.")

if __name__ == "__main__":
    main()
