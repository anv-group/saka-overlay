import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LOCAL_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.local.json")

DEFAULT_HOTKEYS = {
    "toggle_scan": "F1",
    "flag_error": "F2",
    "add_whitelist": "F3",
    "add_blocklist": "F4",
    "add_kamus": "F7",
    "add_tag": "F6",
    "cycle_mode": "",
}

DEFAULT_CONFIG = {
    "screen_area": {
        "top": 300,
        "left": 600,
        "width": 400,
        "height": 120
    },
    "scan_interval_sec": 0.08,
    "game_mode": "normal",  # "normal", "santai", atau "brutal"
    "mode_santai": False,  # True jika main di Mode Santai (tanpa X, Q, F) - backward compatibility
    "brutal_mode_tags": ["AMSI", "KSO", "RHU", "TL", "BD"],  # Tag kustom yang otomatis aktif saat Mode Brutal
    "saved_normal_tags": [],  # Snapshot tag aktif di Mode Normal untuk pemulihan saat keluar dari Mode Brutal
    "report_hotkey": "F2",  # Hotkey screenshot instan deteksi salah
    "hotkeys": DEFAULT_HOTKEYS.copy(),
    "ocr_engine": "winocr",  # "winocr" atau "tesseract"
    "tesseract_path": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "updater_mode": "prompt",  # "prompt", "auto", "disabled"
    "updater_branch": "main",  # "main", "dev", atau branch kustom lainnya
    "auto_check_update_on_startup": True,
    "use_kbbi": True,  # Aktifkan kamus resmi KBBI
    "use_contek": True,  # Aktifkan kamus Contek Sambung Kata (contek-sambungkata.web.id)
    "gameplay_indexing_enabled": True,  # Deteksi feedback gameplay (kata salah, kata sudah digunakan, kata benar)
    "gameplay_area": {  # Area monitoring kata & karakter di layar (1920x1200 default)
        "left": 740,
        "top": 250,
        "width": 440,
        "height": 400
    },
    "auto_blacklist_invalid": True,  # Otomatis blacklist kata yang ditolak game Roblox
    "auto_learn_valid": True,  # Otomatis simpan kata valid yang belum ada di kamus
    "tier0_sort_mode": "default",
    "two_tone_text": True,  # "default" (Panjang 4-7 & Abjad) atau "tag_order" (Sesuai Urutan Tag Kustom)
    "dev_mode": False,  # Mode Pengembang (Menampilkan tombol ⚡ Restart & fitur debug). Default OFF di git.
    "custom_trap_endings": [  # Kategori custom akhiran jebakan super (prioritas di atas X)
        {"suffix": "NS", "name": "Akhiran NS", "enabled": True, "color": "#cba6f7"},
        {"suffix": "NGK", "name": "Akhiran NGK", "enabled": True, "color": "#f5c2e7"}
    ]
}

def load_config():
    """
    Memuat konfigurasi aplikasi dengan sistem multi-layer:
    1. Nilai bawaan sistem (DEFAULT_CONFIG)
    2. File bersama (config.json)
    3. File override lokal pengguna (config.local.json) - Kebal git pull / update GitHub!
    """
    config = DEFAULT_CONFIG.copy()

    # Layer 1: config.json
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config.update(data)
        except Exception as e:
            print(f"[!] Error loading config: {e}, using default.")

    # Layer 2: config.local.json (Local Override - Tidak dilacak oleh git)
    if os.path.exists(LOCAL_CONFIG_FILE):
        try:
            with open(LOCAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
                config.update(local_data)
        except Exception as e:
            print(f"[!] Error loading local config override: {e}")

    # Pastikan semua kunci hotkey default tersedia
    merged_hotkeys = DEFAULT_HOTKEYS.copy()
    if isinstance(config.get("hotkeys"), dict):
        merged_hotkeys.update(config["hotkeys"])
    config["hotkeys"] = merged_hotkeys

    return config

def save_config(cfg):
    """
    Menyimpan konfigurasi:
    1. Menyimpan ke config.json (file konfigurasi umum)
    2. Menyimpan pengaturan lokal spesifik pengguna ke config.local.json (kebal git update/pull)
    """
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)

        # Simpan preferensi lokal pengguna ke config.local.json (kebal git pull / update GitHub / checkout)
        local_keys = [
            "dev_mode",
            "game_mode",
            "mode_santai",
            "brutal_mode_tags",
            "saved_normal_tags",
            "saved_default_tags",
            "santai_auto_disabled_tags",
            "tier0_sort_mode",
            "custom_trap_endings",
            "screen_area",
            "gameplay_area",
            "scan_interval_sec",
            "auto_copy_top_word",
            "use_kbbi",
            "use_contek",
            "window_geometry",
            "report_hotkey",
            "hotkeys"
        ]
        local_cfg = {}
        if os.path.exists(LOCAL_CONFIG_FILE):
            try:
                with open(LOCAL_CONFIG_FILE, "r", encoding="utf-8") as f:
                    local_cfg = json.load(f)
            except Exception:
                local_cfg = {}

        for k in local_keys:
            if k in cfg:
                local_cfg[k] = cfg[k]

        with open(LOCAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(local_cfg, f, indent=4)

        return True
    except Exception as e:
        print(f"[!] Gagal menyimpan config: {e}")
        return False
