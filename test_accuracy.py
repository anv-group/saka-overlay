"""
Benchmark & Regression Test Suite untuk Sambung Kata OCR Engine
Digunakan oleh developer / AI agent untuk memverifikasi akurasi OCR setelah perubahan kode.
"""

import os
import sys
import cv2

# Pastikan output UTF-8 di Windows Console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from ocr_engine import OCREngine

def run_tests():
    engine = OCREngine()
    
    test_suites = [
        ("sample/1", "1 Huruf (Template Matcher)"),
        ("sample/2", "2 Huruf (Template Matcher)"),
        ("sample/3", "3 Huruf (RapidOCR)"),
        ("sample/tidak_dikenali_corrected", "Challenge Set (tidak_dikenali_corrected)"),
    ]

    total = 0
    passed = 0
    failures = []

    print("=" * 65)
    print(">>> MEMULAI PENGUJIAN REGRESI OCR SAMBUNG KATA")
    print("=" * 65)

    for rel_path, suite_name in test_suites:
        folder = os.path.join(base_dir, rel_path.replace("/", os.sep))
        if not os.path.exists(folder):
            continue
        
        files = [f for f in sorted(os.listdir(folder)) if f.endswith(".png")]
        suite_pass = 0
        print(f"\n[*] Menguji {suite_name} ({len(files)} sampel)...")
        
        for f in files:
            total += 1
            expected = os.path.splitext(f)[0].upper()
            p = os.path.join(folder, f)
            img = cv2.imread(p)
            res = engine.recognize_game_prompt(img, auto_save=False)
            ok = (res["text"] == expected)
            
            if ok and not res["is_low_confidence"]:
                suite_pass += 1
                passed += 1
            else:
                failures.append({
                    "suite": suite_name,
                    "file": f,
                    "expected": expected,
                    "got": res["text"],
                    "conf": res["confidence"],
                    "low": res["is_low_confidence"]
                })
        print(f"    Hasil: {suite_pass}/{len(files)} lolos ({suite_pass/len(files)*100:.1f}%)")

    # Uji subfolder sample/tidak_dikenali jika ada
    unknown_parent = os.path.join(base_dir, "sample", "tidak_dikenali")
    if os.path.exists(unknown_parent):
        subdirs = [d for d in sorted(os.listdir(unknown_parent)) if os.path.isdir(os.path.join(unknown_parent, d))]
        if subdirs:
            print(f"\n[*] Menguji Subfolder sample/tidak_dikenali ({len(subdirs)} subfolder)...")
            sub_total = 0
            sub_pass = 0
            for sub in subdirs:
                sub_path = os.path.join(unknown_parent, sub)
                expected = sub.upper()
                for f in sorted(os.listdir(sub_path)):
                    if f.endswith(".png"):
                        total += 1
                        sub_total += 1
                        p = os.path.join(sub_path, f)
                        img = cv2.imread(p)
                        res = engine.recognize_game_prompt(img, auto_save=False)
                        ok = (res["text"] == expected)
                        if ok and not res["is_low_confidence"]:
                            passed += 1
                            sub_pass += 1
                        else:
                            failures.append({
                                "suite": f"tidak_dikenali/{sub}",
                                "file": f,
                                "expected": expected,
                                "got": res["text"],
                                "conf": res["confidence"],
                                "low": res["is_low_confidence"]
                            })
            print(f"    Hasil: {sub_pass}/{sub_total} lolos ({sub_pass/sub_total*100:.1f}%)")

    # Laporkan sampel mentah/belum diklasifikasi yang dilewati
    unclassified_count = 0
    for rel_folder in ["sample/kurang_tepat", "sample/tidak_dikenali"]:
        folder = os.path.join(base_dir, rel_folder.replace("/", os.sep))
        if os.path.exists(folder):
            for f in os.listdir(folder):
                if f.endswith(".png") and os.path.isfile(os.path.join(folder, f)) and "_seharusnya_" not in f:
                    unclassified_count += 1
    if unclassified_count > 0:
        print(f"\n[*] Catatan: {unclassified_count} sampel mentah/belum dikoreksi dilewati (hanya menguji dataset benchmark terverifikasi).")

    print("\n" + "=" * 65)
    print(f"[STATUS] TOTAL HASIL AKHIR: {passed}/{total} Lolos Bersih ({passed/total*100:.1f}%)")
    print("=" * 65)

    if failures:
        print("\n[!] DAFTAR KEGAGALAN / PERINGATAN RENDAH:")
        for item in failures:
            print(f"   [{item['suite']}] {item['file']} -> Diharapkan: '{item['expected']}' | Hasil: '{item['got']}' (Conf: {item['conf']:.2f}, Low: {item['low']})")
        return False
    else:
        print("\n[OK] SEMUA PENGUJIAN LOLOS DENGAN SEMPURNA (100% ACCURACY)!\n")
        return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
