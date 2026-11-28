import copy
import json
import os
import tempfile

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DEFAULT_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.default.json")

MODE_SYNC_KEYS = (
    "game_mode",
    "mode_santai",
    "brutal_mode_tags",
    "saved_normal_tags",
    "saved_default_tags",
    "santai_auto_disabled_tags",
    "tier0_sort_mode",
    "custom_trap_endings",
)

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
    "allow_multiple_instances": False,  # Default hanya 1 instance aktif kecuali diaktifkan
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
    "show_word_datetime": False,  # Tampilkan badge datetime di tab KAMUS (default tersembunyi)
    "show_word_author": False,    # Tampilkan badge author di tab KAMUS (default tersembunyi)
    "two_tone_text": True,  # "default" (Panjang 4-7 & Abjad) atau "tag_order" (Sesuai Urutan Tag Kustom)
    "dev_mode": False,  # Mode Pengembang (Menampilkan tombol ⚡ Restart & fitur debug). Default OFF di git.
    "storage_mode": "txt",  # "txt" (Default lokal/publik) atau "supabase" (Database privat real-time)
    "supabase_url": "",
    "supabase_anon_key": "",
    "sync_nickname": "",
    "custom_trap_endings": [  # Kategori custom akhiran jebakan super
        {"suffix": "NS", "enabled": True, "color": "#cba6f7"},
        {"suffix": "NGK", "enabled": True, "color": "#f5c2e7"}
    ]
}

def _read_json_dict(path: str) -> dict:
    """Membaca file JSON menjadi dict secara aman; mengembalikan {} jika gagal."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _atomic_write_json(path: str, data: dict) -> None:
    """Menulis JSON secara atomic memakai file sementara di direktori yang sama."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".cfg_", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def load_config():
    """
    Memuat konfigurasi aplikasi dengan sistem 2-file:
    1. Nilai bawaan sistem (DEFAULT_CONFIG) + template GitHub (config.default.json)
    2. Konfigurasi personal lokal pengguna (config.json - untracked / .gitignore)
    Jika config.json belum ada (fresh install), file dibuat otomatis dari layer default.
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    base_hotkeys = copy.deepcopy(DEFAULT_HOTKEYS)

    # Layer 1: config.default.json (Template resmi di GitHub)
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            default_data = _read_json_dict(DEFAULT_CONFIG_FILE)
            if isinstance(default_data.get("hotkeys"), dict):
                base_hotkeys.update(default_data["hotkeys"])
            config.update(default_data)
        except Exception as e:
            print(f"[!] Error loading default config: {e}, using built-in default.")

    config["hotkeys"] = copy.deepcopy(base_hotkeys)

    # Fresh install: buat config.json lokal dari template default bila belum ada
    if not os.path.exists(CONFIG_FILE):
        try:
            _atomic_write_json(CONFIG_FILE, config)
        except Exception as e:
            print(f"[!] Gagal membuat config.json awal: {e}")
        return config

    # Layer 2: config.json (Konfigurasi personal lokal pengguna)
    try:
        user_data = _read_json_dict(CONFIG_FILE)
        config.update(user_data)
        merged_hotkeys = copy.deepcopy(base_hotkeys)
        if isinstance(user_data.get("hotkeys"), dict):
            merged_hotkeys.update(user_data["hotkeys"])
        config["hotkeys"] = merged_hotkeys
    except Exception as e:
        print(f"[!] Error loading config: {e}, using default.")

    return config


def extract_mode_state(cfg: dict) -> dict:
    """Mengambil salinan field pengaturan Tab MODE dari dict konfigurasi."""
    state = {}
    for k in MODE_SYNC_KEYS:
        if k in cfg:
            state[k] = copy.deepcopy(cfg[k])
        elif k in DEFAULT_CONFIG:
            state[k] = copy.deepcopy(DEFAULT_CONFIG[k])
    return state


def load_txt_mode_state() -> dict:
    """Memuat pengaturan MODE lokal khusus Mode File CSV/TXT dari config.json."""
    return extract_mode_state(load_config())


def save_txt_mode_state(mode_state: dict) -> bool:
    """Menyimpan pengaturan MODE (misal hasil Download DB -> Lokal) ke config.json untuk Mode File CSV/TXT."""
    if not isinstance(mode_state, dict):
        return False
    try:
        try:
            local_cfg = _read_json_dict(CONFIG_FILE)
        except Exception:
            local_cfg = {}
        for k in MODE_SYNC_KEYS:
            if k in mode_state:
                local_cfg[k] = copy.deepcopy(mode_state[k])
        _atomic_write_json(CONFIG_FILE, local_cfg)
        return True
    except Exception as e:
        print(f"[!] Gagal menyimpan mode TXT lokal: {e}")
        return False


def save_config(cfg):
    """
    Menyimpan konfigurasi ke config.json lokal secara atomic.
    Saat storage_mode == 'supabase', kunci MODE_SYNC_KEYS di config.json tetap
    dipertahankan untuk Mode File CSV/TXT agar tidak tertimpa oleh profil database privat.
    """
    try:
        is_db_mode = (cfg.get("storage_mode", "txt") == "supabase")

        existing_cfg = {}
        try:
            existing_cfg = _read_json_dict(CONFIG_FILE)
        except Exception:
            existing_cfg = {}

        cfg_to_save = copy.deepcopy(cfg)
        if is_db_mode:
            for mk in MODE_SYNC_KEYS:
                if mk in existing_cfg:
                    cfg_to_save[mk] = copy.deepcopy(existing_cfg[mk])

        _atomic_write_json(CONFIG_FILE, cfg_to_save)
        return True
    except Exception as e:
        print(f"[!] Gagal menyimpan config: {e}")
        return False
