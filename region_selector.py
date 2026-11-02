import tkinter as tk
import ctypes

def enable_dpi_awareness():
    """Mengaktifkan DPI awareness agar Tkinter mengenali resolusi fisik monitor 1920x1200 1:1"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

class RegionSelector:
    """
    Overlay transparan full screen untuk memilih kotak area layar (ROI)
    secara interaktif dengan klik & drag mouse pada resolusi penuh (1920x1200).
    """
    def __init__(self, on_selected_callback, title=None):
        enable_dpi_awareness()
        self.on_selected_callback = on_selected_callback
        self.title = title
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.text_id = None

        # Dapatkan ukuran fisik layar penuh (termasuk multi-monitor / 1920x1200)
        user32 = ctypes.windll.user32
        self.screen_x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        self.screen_y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        self.screen_w = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        self.screen_h = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN

        if self.screen_w == 0 or self.screen_h == 0:
            self.screen_w = 1920
            self.screen_h = 1200
            self.screen_x = 0
            self.screen_y = 0

        self.root = tk.Toplevel()
        # Gunakan borderless window dengan ukuran virtual screen penuh
        self.root.overrideredirect(True)
        self.root.geometry(f"{self.screen_w}x{self.screen_h}+{self.screen_x}+{self.screen_y}")
        self.root.attributes("-alpha", 0.35)
        self.root.attributes("-topmost", True)
        self.root.config(cursor="cross")

        # Canvas untuk menggambar kotak seleksi
        self.canvas = tk.Canvas(
            self.root,
            cursor="cross",
            bg="black",
            highlightthickness=0,
            width=self.screen_w,
            height=self.screen_h
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Petunjuk di layar
        header_text = self.title or "KLIK & DRAG MOUSE UNTUK MEMILIH AREA AWALAN KATA ROBLOX"
        self.canvas.create_text(
            self.screen_w // 2,
            60,
            text=f"LAYAR PENUH ({self.screen_w}x{self.screen_h})\n{header_text}\n(Tekan ESC atau Klik Kanan untuk Batal)",
            fill="#00ffcc",
            font=("Segoe UI", 16, "bold"),
            justify=tk.CENTER
        )

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda e: self.close())
        self.root.bind("<Button-3>", lambda e: self.close())  # Klik kanan untuk batal

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)

        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#00ffcc", width=2, fill="#ffffff"
        )
        self.text_id = self.canvas.create_text(
            self.start_x + 10, self.start_y - 15,
            text="0 x 0",
            fill="#ffff00",
            font=("Segoe UI", 11, "bold"),
            anchor=tk.SW
        )

    def on_drag(self, event):
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

        w = abs(cur_x - self.start_x)
        h = abs(cur_y - self.start_y)
        min_x = min(self.start_x, cur_x)
        min_y = min(self.start_y, cur_y)

        self.canvas.coords(self.text_id, min_x + 10, max(20, min_y - 10))
        self.canvas.itemconfig(self.text_id, text=f"{w} x {h} px")

    def on_release(self, event):
        end_x, end_y = event.x, event.y
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        width = x2 - x1
        height = y2 - y1

        self.close()

        # Pastikan ukuran seleksi bukan klik tidak sengaja
        if width > 15 and height > 15:
            # Sesuaikan dengan offset monitor virtual
            actual_left = x1 + self.screen_x
            actual_top = y1 + self.screen_y

            selected_area = {
                "left": int(actual_left),
                "top": int(actual_top),
                "width": int(width),
                "height": int(height)
            }
            if self.on_selected_callback:
                self.on_selected_callback(selected_area)

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass
