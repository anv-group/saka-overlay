import sys
import os
import ctypes

# Aktifkan DPI awareness agar skala resolusi Windows (1920x1200) terbaca 1:1 tanpa downscaling
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Pastikan direktori script masuk dalam python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app_gui import main

if __name__ == "__main__":
    main()
