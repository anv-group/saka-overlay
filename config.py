import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "screen_area": {
        "top": 300,
        "left": 600,
        "width": 400,
        "height": 120
    },
    "scan_interval_sec": 0.15,
    "auto_copy_top_word": False,
    "mode_santai": False,  # True jika main di Mode Santai (tanpa X, Q, F)
    "report_hotkey": "F2",  # Hotkey screenshot instan deteksi salah
    "ocr_engine": "winocr",  # "winocr" atau "tesseract"
    "tesseract_path": r"C:\Program Files\Tesseract-OCR\tesseract.exe"
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception as e:
            print(f"[!] Error loading config: {e}, using default.")
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        return True
    except Exception as e:
        print(f"[!] Gagal menyimpan config: {e}")
        return False
