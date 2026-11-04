import sys
import os

# Pastikan direktori kerja berada di folder script
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app_qt import main

if __name__ == "__main__":
    main()
