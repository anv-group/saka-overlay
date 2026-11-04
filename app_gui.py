import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
from PIL import Image, ImageTk
import threading
import time
import os
import re
import ctypes
import cv2
import numpy as np

def enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

enable_dpi_awareness()

from solver import SambungKataSolver
from ocr_engine import OCREngine
from config import load_config, save_config
from region_selector import RegionSelector
from updater import GitUpdater
from gameplay_indexer import GameplayIndexer
from extract_gameplay_recording import extract_gameplay_events
from ui_theme import THEME, render_vector_icon
from ui_components import TopTabStrip, MiniTickerBar
from tab_views import TagsTabView, DictionaryTabView, SystemTabView

class SambungKataApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SAKA Overlay")

        # Pasang icon aplikasi (ico & png)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_ico = os.path.join(base_dir, "assets", "logo.ico")
        if not os.path.exists(icon_ico):
            icon_ico = os.path.join(base_dir, "assets", "icon.ico")
        icon_png = os.path.join(base_dir, "assets", "logo.png")
        if not os.path.exists(icon_png):
            icon_png = os.path.join(base_dir, "assets", "logo_cropped.png")
        if os.path.exists(icon_ico):
            try:
                self.root.iconbitmap(icon_ico)
            except Exception:
                pass
        if os.path.exists(icon_png):
            try:
                from PIL import Image, ImageTk
                self._app_icon_img = ImageTk.PhotoImage(Image.open(icon_png))
                self.root.iconphoto(True, self._app_icon_img)
            except Exception:
                pass

        self.config = load_config()
        if self.config.get("game_mode") == "normal":
            self.config["game_mode"] = "default"

        # Posisi & ukuran window default: di sebelah kanan layar, minimal sesuai ui-size-min.png (438x1075)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        target_w = 440
        # Sesuaikan tinggi agar muat di layar pengguna (misal 1536x960 pada scaling 125%)
        target_h = max(600, min(880, screen_h - 60))
        target_x = max(10, screen_w - target_w - 20)
        target_y = 15
        default_geom = f"{target_w}x{target_h}+{target_x}+{target_y}"

        saved_geom = self.config.get("window_geometry")
        if saved_geom:
            try:
                import re
                m = re.match(r"^(\d+)x(\d+)\+([+-]?\d+)\+([+-]?\d+)$", saved_geom.strip())
                if m:
                    gw, gh, gx, gy = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                    # Clamp agar selalu aman dan tidak off-screen
                    gw = max(438, min(gw, screen_w - 20))
                    gh = max(550, min(gh, screen_h - 50))
                    if gx + gw > screen_w - 15:
                        gx = screen_w - gw - 25
                    if gx < 0:
                        gx = 10
                    if gy + gh > screen_h - 20:
                        gy = max(10, screen_h - gh - 50)
                    if gy < 0:
                        gy = 10
                    self.root.geometry(f"{gw}x{gh}+{gx}+{gy}")
                else:
                    self.root.geometry(default_geom)
            except Exception:
                self.root.geometry(default_geom)
        else:
            self.root.geometry(default_geom)

        # Lebar minimal 438px sesuai batas minimal visual ui-size-min.png
        self.root.minsize(438, 650)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=THEME["bg_root"], highlightthickness=1, highlightbackground=THEME["border"], highlightcolor=THEME["border"])

        # Setup global ttk style using 'clam' to override Windows Vista native white dropdowns
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure(
            "TCombobox",
            fieldbackground=THEME["bg_input"],
            background=THEME["bg_card"],
            foreground=THEME["text_primary"],
            arrowcolor=THEME["primary"],
            bordercolor=THEME["border"],
            darkcolor=THEME["bg_root"],
            lightcolor=THEME["bg_card"],
            insertcolor=THEME["primary"]
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", THEME["bg_input"]), ("focus", THEME["bg_input"])],
            foreground=[("readonly", THEME["text_primary"]), ("focus", THEME["text_primary"])],
            background=[("readonly", THEME["bg_card"])],
            arrowcolor=[("readonly", THEME["primary"])],
            bordercolor=[("focus", THEME["primary"])]
        )
        self.style.configure(
            "Vertical.TScrollbar",
            background=THEME["bg_card"],
            troughcolor=THEME["bg_root"],
            bordercolor=THEME["bg_root"],
            arrowcolor=THEME["text_muted"]
        )

        # Global Dark Option styling with priority 100 for Listbox & Menu popdowns
        self.root.option_add('*Listbox.background', THEME["bg_card"], 100)
        self.root.option_add('*Listbox.foreground', THEME["text_primary"], 100)
        self.root.option_add('*Listbox.selectBackground', THEME["primary"], 100)
        self.root.option_add('*Listbox.selectForeground', THEME["text_dark"], 100)
        self.root.option_add('*Combobox*Listbox.background', THEME["bg_card"], 100)
        self.root.option_add('*Combobox*Listbox.foreground', THEME["text_primary"], 100)
        self.root.option_add('*Combobox*Listbox.selectBackground', THEME["primary"], 100)
        self.root.option_add('*Combobox*Listbox.selectForeground', THEME["text_dark"], 100)
        self.root.option_add('*TCombobox*Listbox.background', THEME["bg_card"], 100)
        self.root.option_add('*TCombobox*Listbox.foreground', THEME["text_primary"], 100)
        self.root.option_add('*TCombobox*Listbox.selectBackground', THEME["primary"], 100)
        self.root.option_add('*TCombobox*Listbox.selectForeground', THEME["text_dark"], 100)
        self.root.option_add('*TCombobox*Listbox.font', ('Segoe UI', 9), 100)
        self.root.option_add('*Menu.background', THEME["bg_card"], 100)
        self.root.option_add('*Menu.foreground', THEME["text_primary"], 100)
        self.root.option_add('*Menu.activeBackground', THEME["primary"], 100)
        self.root.option_add('*Menu.activeForeground', THEME["text_dark"], 100)
        self.root.option_add('*Menu.borderWidth', 1, 100)
        self.root.option_add('*Menu.relief', 'flat', 100)
        self.root.option_add('*Menu.font', ('Segoe UI', 9), 100)
        self._setup_taskbar_presence()

        use_kbbi = self.config.get("use_kbbi", True)
        use_contek = self.config.get("use_contek", True)
        self.solver = SambungKataSolver(
            dictionary_path="kamus_lengkap.txt",
            kbbi_path="kamus_kbbi.txt",
            contek_path="kamus_contek.txt",
            use_kbbi=use_kbbi,
            use_contek=use_contek
        )
        self.solver.set_custom_endings(self.config.get("custom_trap_endings", []))
        self.solver.set_tier0_sort_mode(self.config.get("tier0_sort_mode", "default"))
        self.ocr = OCREngine(self.config)
        self.updater = GitUpdater()
        self.gameplay_indexer = GameplayIndexer(
            config=self.config,
            solver=self.solver,
            on_event_callback=self._on_gameplay_event
        )

        self.is_scanning = False
        self.scan_thread = None
        self.last_detected_word = ""

        self._save_config_timer = None
        self._dirty_quick_bar = False
        self._dirty_live_results = False

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_ui()

        # Pengecekan pembaruan otomatis di latar belakang saat startup
        if self.config.get("auto_check_update_on_startup", True) and self.config.get("updater_mode", "prompt") != "disabled":
            self.root.after(1200, lambda: threading.Thread(target=self._startup_update_check, daemon=True).start())

    def _setup_taskbar_presence(self):
        """Memastikan window frameless tetap tampil di Windows Taskbar dan Alt-Tab"""
        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd == 0:
                hwnd = self.root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def _create_clean_toplevel(self, title, width, height, min_w=None, min_h=None, resizable=True, on_close=None, parent=None):
        """
        Membuat jendela Toplevel dengan custom titlebar frameless yang konsisten dengan UI utama:
        - Frameless (overrideredirect) dengan border luar Catppuccin 1px (#313244).
        - Titlebar gelap (#11111b) dengan teks judul Segoe UI 8/9 Bold (#cdd6f4).
        - Tombol Close '✕' di sudut kanan dengan hover merah (#f38ba8).
        - Drag-to-move pada titlebar dan label judul.
        - Resize grip ⋰ di sudut kanan bawah jika resizable.
        - Tombol Escape untuk menutup.
        - Posisi otomatis di samping window utama agar tidak menutupi overlay game.
        """
        parent_win = parent if parent else self.root
        win = tk.Toplevel(parent_win)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=THEME["bg_root"], highlightthickness=1, highlightbackground=THEME["border"])
        win.option_add('*Listbox.background', THEME["bg_card"], 100)
        win.option_add('*Listbox.foreground', THEME["text_primary"], 100)
        win.option_add('*Listbox.selectBackground', THEME["primary"], 100)
        win.option_add('*Listbox.selectForeground', THEME["text_dark"], 100)
        win.option_add('*Combobox*Listbox.background', THEME["bg_card"], 100)
        win.option_add('*Combobox*Listbox.foreground', THEME["text_primary"], 100)
        win.option_add('*Combobox*Listbox.selectBackground', THEME["primary"], 100)
        win.option_add('*Combobox*Listbox.selectForeground', THEME["text_dark"], 100)

        min_w = min_w or max(340, width - 60)
        min_h = min_h or max(300, height - 80)

        try:
            rx = self.root.winfo_x()
            ry = self.root.winfo_y()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            target_x = max(20, rx - width - 12) if rx > 500 else rx + self.root.winfo_width() + 12
            if target_x + width > sw - 20:
                target_x = max(20, sw - width - 20)
            target_y = max(30, ry)
            if target_y + height > sh - 50:
                target_y = max(30, sh - height - 60)
            win.geometry(f"{width}x{height}+{target_x}+{target_y}")
        except Exception:
            win.geometry(f"{width}x{height}")

        close_fn = on_close if on_close else win.destroy

        # 0. Custom Frameless Titlebar
        tbar = tk.Frame(win, bg=THEME["bg_root"], height=30)
        tbar.pack(fill=tk.X, side=tk.TOP)

        btn_close = tk.Button(
            tbar,
            text="✕",
            font=("Segoe UI", 10, "bold"),
            fg=THEME["text_secondary"],
            bg=THEME["bg_root"],
            activebackground=THEME["danger"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=3,
            cursor="hand2",
            command=close_fn
        )
        btn_close.pack(side=tk.RIGHT, padx=(0, 4), pady=2)
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg=THEME["danger"], fg="#ffffff"))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg=THEME["bg_root"], fg=THEME["text_secondary"]))

        lbl_title = tk.Label(
            tbar,
            text=title,
            font=("Segoe UI", 8, "bold"),
            fg=THEME["text_primary"],
            bg=THEME["bg_root"],
            anchor="w"
        )
        lbl_title.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 4), pady=4)

        drag_data = {"x": 0, "y": 0}
        def _start_drag(event):
            drag_data["x"] = event.x_root - win.winfo_x()
            drag_data["y"] = event.y_root - win.winfo_y()

        def _on_drag(event):
            win.geometry(f"+{event.x_root - drag_data['x']}+{event.y_root - drag_data['y']}")

        tbar.bind("<ButtonPress-1>", _start_drag)
        tbar.bind("<B1-Motion>", _on_drag)
        lbl_title.bind("<ButtonPress-1>", _start_drag)
        lbl_title.bind("<B1-Motion>", _on_drag)

        sep_title = tk.Frame(win, bg=THEME["border"], height=1)
        sep_title.pack(fill=tk.X, side=tk.TOP)

        if resizable:
            grip_bar = tk.Frame(win, bg=THEME["bg_root"], height=16, cursor="size_ns")
            grip_bar.pack(fill=tk.X, side=tk.BOTTOM)
            lbl_grip = tk.Label(
                grip_bar,
                text="⋰",
                font=("Segoe UI", 9, "bold"),
                fg=THEME["text_muted"],
                bg=THEME["bg_root"],
                cursor="size_nw_se"
            )
            lbl_grip.pack(side=tk.RIGHT, padx=6)

            popup_resize_data = {"is_resizing": False, "timer": None, "pending": None}

            def _apply_popup_resize():
                popup_resize_data["timer"] = None
                if not popup_resize_data["is_resizing"] or not popup_resize_data["pending"]:
                    return
                try:
                    win.geometry(popup_resize_data["pending"])
                except Exception:
                    pass

            def _start_resize(event):
                popup_resize_data["is_resizing"] = True
                popup_resize_data["x"] = event.x_root
                popup_resize_data["y"] = event.y_root
                popup_resize_data["w"] = win.winfo_width()
                popup_resize_data["h"] = win.winfo_height()

            def _on_resize(event):
                if not popup_resize_data["is_resizing"]:
                    return
                dw = event.x_root - popup_resize_data["x"]
                dh = event.y_root - popup_resize_data["y"]
                nw = max(min_w, popup_resize_data["w"] + dw)
                nh = max(min_h, popup_resize_data["h"] + dh)
                popup_resize_data["pending"] = f"{nw}x{nh}"
                if popup_resize_data["timer"] is None:
                    popup_resize_data["timer"] = win.after(16, _apply_popup_resize)

            def _stop_resize(event=None):
                if not popup_resize_data["is_resizing"]:
                    return
                popup_resize_data["is_resizing"] = False
                if popup_resize_data["timer"]:
                    win.after_cancel(popup_resize_data["timer"])
                    popup_resize_data["timer"] = None
                if popup_resize_data["pending"]:
                    try:
                        win.geometry(popup_resize_data["pending"])
                    except Exception:
                        pass
                    popup_resize_data["pending"] = None

            lbl_grip.bind("<ButtonPress-1>", _start_resize)
            lbl_grip.bind("<B1-Motion>", _on_resize)
            lbl_grip.bind("<ButtonRelease-1>", _stop_resize)
            grip_bar.bind("<ButtonPress-1>", _start_resize)
            grip_bar.bind("<B1-Motion>", _on_resize)
            grip_bar.bind("<ButtonRelease-1>", _stop_resize)
            win.bind("<ButtonRelease-1>", _stop_resize)

        win.bind("<Escape>", lambda e: close_fn())
        return win, lbl_title

    def _build_ui(self):
        # 0. Custom Frameless Titlebar (Dark Theme, Judul Penuh & Hanya Tombol Close ✕)
        self.custom_title_bar = tk.Frame(self.root, bg=THEME["bg_root"], height=30)
        self.custom_title_bar.pack(fill=tk.X, side=tk.TOP)

        # Tombol Close '✕' dipack PERTAMA di sisi kanan agar selalu terjamin di dalam window dan mudah diklik
        self.btn_title_close = tk.Button(
            self.custom_title_bar,
            text="✕",
            font=("Segoe UI", 10, "bold"),
            fg=THEME["text_secondary"],
            bg=THEME["bg_root"],
            activebackground=THEME["danger"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=3,
            cursor="hand2",
            command=self.on_close
        )
        self.btn_title_close.pack(side=tk.RIGHT, padx=(0, 4), pady=2)
        self.btn_title_close.bind("<Enter>", lambda e: self.btn_title_close.config(bg=THEME["danger"], fg="#ffffff"))
        self.btn_title_close.bind("<Leave>", lambda e: self.btn_title_close.config(bg=THEME["bg_root"], fg=THEME["text_secondary"]))

        # Tombol Restart (Mode Development) diposisikan tepat di samping tombol close di titlebar
        self.btn_restart = tk.Button(
            self.custom_title_bar,
            text="⚡",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["bg_root"],
            fg=THEME["warning"],
            activebackground=THEME["bg_card"],
            activeforeground=THEME["warning"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._restart_app_cleanly
        )
        self.btn_restart.bind("<Enter>", lambda e: self.btn_restart.config(bg=THEME["bg_card"], fg=THEME["warning"]))
        self.btn_restart.bind("<Leave>", lambda e: self.btn_restart.config(bg=THEME["bg_root"], fg=THEME["warning"]))

        # Mode Development: Tombol Restart disembunyikan by default kecuali dev_mode aktif
        self.dev_mode_var = tk.BooleanVar(value=self.config.get("dev_mode", False))
        if self.dev_mode_var.get():
            self.btn_restart.pack(side=tk.RIGHT, padx=(0, 2), pady=2)

        # Logo SAKA Overlay di titlebar menggunakan assets/logo_horizontal.png murni
        logo_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo_horizontal.png")
        if not os.path.exists(logo_file):
            logo_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
        if os.path.exists(logo_file):
            try:
                from PIL import Image, ImageTk
                im_logo = Image.open(logo_file)
                h_target = 22
                w_target = int(im_logo.width * (h_target / im_logo.height))
                logo_resized = im_logo.resize((w_target, h_target), Image.Resampling.LANCZOS)
                self._titlebar_logo_img = ImageTk.PhotoImage(logo_resized)
                self.lbl_logo = tk.Label(
                    self.custom_title_bar,
                    image=self._titlebar_logo_img,
                    bg=THEME["bg_root"],
                    cursor="arrow"
                )
                self.lbl_logo.pack(side=tk.LEFT, padx=(8, 4), pady=2)
            except Exception:
                self.lbl_logo = None
        else:
            self.lbl_logo = None

        self.lbl_title_bar = tk.Label(
            self.custom_title_bar,
            text="",
            bg=THEME["bg_root"]
        )
        self.lbl_title_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

# Close button hover bound above

        # Dragging logic untuk memindahkan window
        self._drag_data = {"x": 0, "y": 0}
        def _start_title_drag(event):
            self._drag_data["x"] = event.x_root - self.root.winfo_x()
            self._drag_data["y"] = event.y_root - self.root.winfo_y()

        def _on_title_drag(event):
            nx = event.x_root - self._drag_data["x"]
            ny = event.y_root - self._drag_data["y"]
            self.root.geometry(f"+{nx}+{ny}")

        self.custom_title_bar.bind("<ButtonPress-1>", _start_title_drag)
        self.custom_title_bar.bind("<B1-Motion>", _on_title_drag)
        self.lbl_title_bar.bind("<ButtonPress-1>", _start_title_drag)
        self.lbl_title_bar.bind("<B1-Motion>", _on_title_drag)
        if getattr(self, "lbl_logo", None) and self.lbl_logo.winfo_exists():
            self.lbl_logo.bind("<ButtonPress-1>", _start_title_drag)
            self.lbl_logo.bind("<B1-Motion>", _on_title_drag)

        # Garis pemisah 1px di bawah titlebar
        sep_title = tk.Frame(self.root, bg=THEME["border"], height=1)
        sep_title.pack(fill=tk.X, side=tk.TOP)

        # Resize grip di sisi kiri (karena window di kanan layar, resize paling nyaman dari sisi kiri)
        self.left_grip = tk.Frame(self.root, bg=THEME["border"], width=4, cursor="size_we")
        self.left_grip.place(x=0, y=0, relheight=1.0, width=4)

        # Unified Smooth Resize State & 60fps Throttling
        self._is_resizing = False
        self._resize_timer = None
        self._pending_geometry = None
        self._resize_mode = None
        self._lg_data = {}
        self._resize_data = {}

        def _apply_pending_resize():
            self._resize_timer = None
            if not self._is_resizing or not self._pending_geometry:
                return
            try:
                self.root.geometry(self._pending_geometry)
            except Exception:
                pass

        def _start_left_grip(event):
            self._is_resizing = True
            self._resize_mode = "left"
            self._lg_data["x_root"] = event.x_root
            self._lg_data["win_x"] = self.root.winfo_x()
            self._lg_data["win_w"] = self.root.winfo_width()
            self._lg_data["win_h"] = self.root.winfo_height()
            self._lg_data["win_y"] = self.root.winfo_y()

        def _on_left_grip(event):
            if not self._is_resizing or self._resize_mode != "left":
                return
            dx = event.x_root - self._lg_data.get("x_root", event.x_root)
            new_w = max(438, self._lg_data.get("win_w", 534) - dx)
            new_x = self._lg_data.get("win_x", 0) + (self._lg_data.get("win_w", 534) - new_w)
            win_h = self._lg_data.get("win_h", self.root.winfo_height())
            win_y = self._lg_data.get("win_y", self.root.winfo_y())
            self._pending_geometry = f"{new_w}x{win_h}+{new_x}+{win_y}"
            if self._resize_timer is None:
                self._resize_timer = self.root.after(16, _apply_pending_resize)

        def _start_bottom_resize(event):
            self._is_resizing = True
            self._resize_mode = "bottom_right"
            self._resize_data["x"] = event.x_root
            self._resize_data["y"] = event.y_root
            self._resize_data["w"] = self.root.winfo_width()
            self._resize_data["h"] = self.root.winfo_height()

        def _on_bottom_resize(event):
            if not self._is_resizing or self._resize_mode != "bottom_right":
                return
            dw = event.x_root - self._resize_data.get("x", event.x_root)
            dh = event.y_root - self._resize_data.get("y", event.y_root)
            nw = max(438, self._resize_data.get("w", 534) + dw)
            nh = max(600, self._resize_data.get("h", 800) + dh)
            self._pending_geometry = f"{nw}x{nh}"
            if self._resize_timer is None:
                self._resize_timer = self.root.after(16, _apply_pending_resize)

        def _stop_resize(event=None):
            if not self._is_resizing:
                return
            self._is_resizing = False
            self._resize_mode = None
            if self._resize_timer is not None:
                self.root.after_cancel(self._resize_timer)
                self._resize_timer = None
            if self._pending_geometry:
                try:
                    self.root.geometry(self._pending_geometry)
                except Exception:
                    pass
                self._pending_geometry = None

            # Auto-reflow tag bar & refresh canvas scrollregion sekali setelah resize tuntas
            self.root.after(20, self._render_custom_category_quick_bar)
            if hasattr(self, "canvas") and self.canvas.winfo_exists():
                try:
                    self.canvas.itemconfig(self.canvas_window, width=self.canvas.winfo_width())
                    self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                except Exception:
                    pass

            try:
                self.config["window_geometry"] = self.root.geometry()
                save_config(self.config)
            except Exception:
                pass

        self.left_grip.bind("<ButtonPress-1>", _start_left_grip)
        self.left_grip.bind("<B1-Motion>", _on_left_grip)
        self.left_grip.bind("<ButtonRelease-1>", _stop_resize)

        # 1. TOP TAB STRIP (LIVE, TAGS, KAMUS, SYSTEM) & MINI TICKER BAR
        tab_defs = [
            ("live", "LIVE", "zap"),
            ("tags", "TAGS", "tag"),
            ("kamus", "KAMUS", "book"),
            ("system", "SYSTEM", "settings")
        ]
        self.top_tab_strip = TopTabStrip(self.root, tab_defs, on_tab_changed=self._on_main_tab_changed)
        self.top_tab_strip.pack(fill=tk.X, side=tk.TOP)

        # Mini Ticker Bar (Hanya tampil di tab non-LIVE)
        self.mini_ticker = MiniTickerBar(self.root, on_click=lambda: self.top_tab_strip.select_tab("live"))

        # Main Tab Host Containers
        self.tab_live_container = tk.Frame(self.root, bg=THEME["bg_root"])
        self.tab_tags_container = TagsTabView(self.root, self)
        self.tab_kamus_container = DictionaryTabView(self.root, self)
        self.tab_system_container = SystemTabView(self.root, self)

        self.tab_live_container.pack(fill=tk.BOTH, expand=True)

        # 2. TAB LIVE: Action Bar & Scan Indicator
        action_bar = tk.Frame(self.tab_live_container, bg=THEME["bg_card"], padx=8, pady=4, highlightthickness=1, highlightbackground=THEME["border"])
        action_bar.pack(fill=tk.X, padx=8, pady=(4, 2))

        self.btn_toggle = tk.Button(
            action_bar,
            text="▶ MULAI",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["primary"],
            fg=THEME["text_dark"],
            activebackground=THEME["accent_neon"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.toggle_scan
        )
        self.btn_toggle.pack(side=tk.LEFT, padx=(0, 4))

        curr_sec_init = self.config.get("scan_interval_sec", 0.08)
        self.lbl_scan_speed_indicator = tk.Label(
            action_bar,
            text=f"Speed: {int(curr_sec_init*1000)}ms",
            font=("Segoe UI", 8, "bold"),
            fg=THEME["text_secondary"],
            bg=THEME["bg_card"]
        )
        self.lbl_scan_speed_indicator.pack(side=tk.RIGHT, padx=4)

        # Mode Sortir Button dengan Icon Sortir
        sort_ico = render_vector_icon("sort", size=13, color=THEME["primary"])
        self.btn_sort_mode = tk.Button(
            action_bar,
            text=" DEFAULT",
            image=sort_ico,
            compound="left",
            font=("Segoe UI", 7, "bold"),
            bg=THEME["bg_hover"],
            fg=THEME["primary"],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.toggle_sort_mode
        )
        self.btn_sort_mode.image = sort_ico
        self.btn_sort_mode.pack(side=tk.RIGHT, padx=4)
        self._update_sort_mode_button()

        # Dummy button references for compatibility
        self.btn_add_word = tk.Button(self.root)
        self.btn_settings = tk.Button(self.root)
        self.status_lbl = tk.Label(self.root)

        # 3. TAB LIVE: Segmented Cyber Pill Mode Switcher (DEFAULT | SANTAI | BRUTAL)
        cur_mode_val = self.config.get("game_mode", "santai" if self.config.get("mode_santai", False) else "default")
        if cur_mode_val == "normal":
            cur_mode_val = "default"
        self.game_mode_var = tk.StringVar(value=cur_mode_val)
        self.mode_santai_var = tk.BooleanVar(value=(cur_mode_val == "santai"))

        pill_frame = tk.Frame(self.tab_live_container, bg=THEME["bg_card"], padx=4, pady=3, highlightthickness=1, highlightbackground=THEME["border"])
        pill_frame.pack(fill=tk.X, padx=8, pady=2)
        pill_frame.columnconfigure((0, 1, 2), weight=1)

        self.btn_pill_default = tk.Button(pill_frame, text="DEFAULT", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, highlightthickness=0, cursor="hand2", command=lambda: self.set_game_mode("default"))
        self.btn_pill_default.grid(row=0, column=0, sticky="nsew", padx=2, pady=1)

        self.btn_pill_santai = tk.Button(pill_frame, text="SANTAI", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, highlightthickness=0, cursor="hand2", command=lambda: self.set_game_mode("santai"))
        self.btn_pill_santai.grid(row=0, column=1, sticky="nsew", padx=2, pady=1)

        self.btn_pill_brutal = tk.Button(pill_frame, text="BRUTAL", font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, highlightthickness=0, cursor="hand2", command=lambda: self.set_game_mode("brutal"))
        self.btn_pill_brutal.grid(row=0, column=2, sticky="nsew", padx=2, pady=1)

        self.btn_game_mode = self.btn_pill_default
        self.btn_mode_santai = self.btn_pill_default
        self.chk_santai = self.btn_pill_default

        self._update_mode_santai_button()

        # 4. TAB LIVE: AWALAN TERDETEKSI & Realtime Search Box
        search_prefix_row = tk.Frame(self.tab_live_container, bg=THEME["bg_root"], padx=8, pady=2)
        search_prefix_row.pack(fill=tk.X)

        self.prefix_badge_frame = tk.Frame(
            search_prefix_row,
            bg=THEME["bg_card"],
            highlightthickness=1,
            highlightbackground=THEME["border_focus"],
            width=76,
            height=34,
            relief=tk.FLAT
        )
        self.prefix_badge_frame.pack_propagate(False)
        self.prefix_badge_frame.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_prefix_display = tk.Label(
            self.prefix_badge_frame,
            text="-",
            font=("Segoe UI", 15, "bold"),
            fg=THEME["accent_neon"],
            bg=THEME["bg_card"]
        )
        self.lbl_prefix_display.pack(fill=tk.BOTH, expand=True)

        self.lbl_conf = tk.Label(
            self.prefix_badge_frame,
            text="",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg=THEME["bg_card"]
        )

        self.lbl_detected = self.lbl_prefix_display
        self.lbl_target = self.lbl_prefix_display

        search_box = tk.Frame(search_prefix_row, bg=THEME["bg_card"], highlightthickness=1, highlightbackground=THEME["border"], padx=6, pady=2)
        search_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        search_ico = render_vector_icon("search", size=14, color=THEME["text_muted"])
        lbl_icon = tk.Label(search_box, image=search_ico, bg=THEME["bg_card"])
        lbl_icon.image = search_ico
        lbl_icon.pack(side=tk.LEFT, padx=(0, 4))

        cross_ico = render_vector_icon("cross", size=12, color=THEME["danger"])
        self.btn_clear_search = tk.Button(
            search_box,
            image=cross_ico,
            bg=THEME["bg_card"],
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self.clear_manual_search
        )
        self.btn_clear_search.image = cross_ico
        self.btn_clear_search.pack(side=tk.RIGHT)

        self.search_var = tk.StringVar()
        self.entry_manual = tk.Entry(
            search_box,
            textvariable=self.search_var,
            font=("Segoe UI", 10, "bold"),
            bg=THEME["bg_card"],
            fg=THEME["text_primary"],
            insertbackground=THEME["primary"],
            relief=tk.FLAT
        )
        self.entry_manual.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_var.trace_add("write", self._on_search_text_changed)

        # 5. TAB LIVE: Baris Horizontal Quick Toggle Kategori Custom
        self.custom_cats_bar = tk.Frame(self.tab_live_container, bg=THEME["bg_root"])
        self.custom_cats_bar.pack(fill=tk.X, padx=8, pady=(1, 2))

        self._cats_bar_last_w = 0
        self._cats_bar_timer = None
        def _on_cats_bar_resize(event):
            if getattr(self, "_is_resizing", False):
                return
            if abs(event.width - self._cats_bar_last_w) > 6:
                self._cats_bar_last_w = event.width
                if self._cats_bar_timer:
                    self.root.after_cancel(self._cats_bar_timer)
                self._cats_bar_timer = self.root.after(40, self._render_custom_category_quick_bar)

        self.custom_cats_bar.bind("<Configure>", _on_cats_bar_resize)
        self._render_custom_category_quick_bar()

        # 5. TAB LIVE: Warning & Toast Frame
        self.warning_frame = tk.Frame(self.tab_live_container, bg=THEME["bg_card"], padx=6, pady=2)
        self.lbl_warning_msg = tk.Label(
            self.warning_frame,
            text="⚠️ Keyakinan Rendah!",
            font=("Segoe UI", 8, "bold"),
            fg=THEME["warning"],
            bg=THEME["bg_card"]
        )
        self.lbl_warning_msg.pack(side=tk.LEFT)
        self.alt_container = tk.Frame(self.warning_frame, bg=THEME["bg_card"])
        self.alt_container.pack(side=tk.LEFT, padx=4)

        self.toast_frame = tk.Frame(self.tab_live_container, bg=THEME["bg_root"])
        self.toast_frame.pack(fill=tk.X, padx=8, pady=1)

        self.lbl_toast = tk.Label(
            self.toast_frame,
            text="",
            font=("Segoe UI", 8, "italic"),
            fg=THEME["primary"],
            bg=THEME["bg_root"]
        )
        self.lbl_toast.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_undo = tk.Button(
            self.toast_frame,
            text="↩️ Batalkan",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["bg_card"],
            fg=THEME["warning"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["warning"],
            relief=tk.FLAT,
            padx=6,
            pady=0,
            cursor="hand2"
        )
        self._toast_timer = None

        # 6. TAB LIVE: Daftar Rekomendasi Jawaban
        is_santai_init = self.config.get("mode_santai", False)
        cur_mode_init = self.config.get("game_mode", "santai" if is_santai_init else "default")
        if cur_mode_init == "normal":
            cur_mode_init = "default"
        recom_title = f" Rekomendasi Kata ({cur_mode_init.upper()}) "
        recom_fg = THEME["danger"] if cur_mode_init == "brutal" else THEME["primary"]

        self.recom_frame = tk.LabelFrame(
            self.tab_live_container,
            text=recom_title,
            font=("Segoe UI", 9, "bold"),
            fg=recom_fg,
            bg=THEME["bg_root"],
            padx=4,
            pady=4,
            highlightthickness=1,
            highlightbackground=THEME["border"]
        )
        self.recom_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 0))

        # Canvas & Scrollbar untuk daftar kata
        self.canvas = tk.Canvas(self.recom_frame, bg=THEME["bg_root"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.recom_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=THEME["bg_root"])

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self._canvas_cfg_timer = None
        def _on_canvas_configure(e):
            try:
                self.canvas.itemconfig(self.canvas_window, width=e.width)
            except Exception:
                pass

        def _on_scrollable_configure(e):
            if getattr(self, "_is_resizing", False):
                return
            if self._canvas_cfg_timer:
                self.root.after_cancel(self._canvas_cfg_timer)
            self._canvas_cfg_timer = self.root.after(
                30,
                lambda: self.canvas.configure(scrollregion=self.canvas.bbox("all")) if hasattr(self, "canvas") and self.canvas.winfo_exists() else None
            )

        self.canvas.bind("<Configure>", _on_canvas_configure)
        self.scrollable_frame.bind("<Configure>", _on_scrollable_configure)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Aktifkan scroll roda mouse (MouseWheel) mulus terpusat di root window (tanpa spam enter/leave per card)
        self.root.bind("<MouseWheel>", self._on_mousewheel)
        self.root.bind("<Button-4>", self._on_mousewheel)
        self.root.bind("<Button-5>", self._on_mousewheel)

        # Widget Pool untuk kartu kata
        self.word_card_pool = []
        self.lbl_empty_results = tk.Label(
            self.scrollable_frame,
            text="",
            font=("Segoe UI", 9, "italic"),
            fg=THEME["danger"],
            bg=THEME["bg_root"],
            pady=10
        )

        # Objek pendukung & konfigurasi kompatibilitas
        self.use_kbbi_var = tk.BooleanVar(value=self.config.get("use_kbbi", True))
        self.use_contek_var = tk.BooleanVar(value=self.config.get("use_contek", True))
        self.gameplay_indexing_var = tk.BooleanVar(value=self.config.get("gameplay_indexing_enabled", True))
        self.speed_options = [
            (0.04, "🔥 40ms (Ultra Instan)"),
            (0.08, "⚡ 80ms (Kilat Turbo)"),
            (0.15, "🚀 150ms (Cepat)"),
            (0.30, "🐢 300ms (Santai)")
        ]

        # Dummy widgets untuk kompatibilitas fungsi eksisting
        self.lbl_coords = tk.Label(self.root)
        self.btn_speed = tk.Button(self.root)
        self.chk_kbbi = tk.Checkbutton(self.root)
        self.chk_contek = tk.Checkbutton(self.root)
        self.lbl_dict_count = tk.Label(self.root)
        self.chk_gameplay = tk.Checkbutton(self.root)
        self.btn_kurang_tepat = tk.Button(self.root)
        self.btn_koreksi = tk.Button(self.root)
        self.btn_roi = tk.Button(self.root)
        self.btn_preview = tk.Button(self.root)
        self.btn_blocklist = tk.Button(self.root)
        self.btn_custom_cats = tk.Button(self.root)

        # Shortcut lokal Tkinter (F2 untuk awalan, F3 untuk gameplay)
        self.report_hotkey = self.config.get("report_hotkey", "F2").upper()
        self.root.bind(f"<{self.report_hotkey}>", lambda e: self.on_report_kurang_tepat())
        self.gameplay_calib_hotkey = "F3"
        self.root.bind(f"<{self.gameplay_calib_hotkey}>", lambda e: self.on_capture_gameplay_kalibrasi())
        # Shortcut Ctrl+Shift+D untuk toggle mode development (Restart)
        self.root.bind("<Control-Shift-D>", lambda e: self._toggle_dev_mode_shortcut())
        self.root.bind("<Control-Shift-d>", lambda e: self._toggle_dev_mode_shortcut())

        # Global Hotkey menggunakan keyboard library
        try:
            import keyboard
            keyboard.add_hotkey(self.report_hotkey.lower(), lambda: self.root.after(0, self.on_report_kurang_tepat))
            keyboard.add_hotkey(self.gameplay_calib_hotkey.lower(), lambda: self.root.after(0, self.on_capture_gameplay_kalibrasi))
        except Exception as e:
            print(f"[!] Warning: Gagal mendaftarkan global hotkey: {e}")

        self._update_mode_santai_button()
        self._update_koreksi_badge()
        self._update_window_title()

    def _open_settings_menu(self):
        """Membuka dropdown menu pengaturan tambahan tanpa memenuhi layar game"""
        menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#181825",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            activeforeground="#f5e0dc",
            selectcolor="#a6e3a1"
        )
        # Kelompok 1: Area Deteksi Awalan Huruf
        menu.add_command(label="🎯 Set Area Deteksi", command=self.open_region_selector)
        menu.add_command(label="👁️ Test Area Deteksi", command=self.preview_selected_area)
        menu.add_command(label="📸 Screenshot Area Deteksi (F2)", command=self.on_report_kurang_tepat)
        menu.add_separator()

        # Kelompok 2: Fitur Kamus, Koreksi & Kategori
        menu.add_command(label="📖 Cari di Kamus (Eksplorasi)", command=self.open_dictionary_browser_window)
        menu.add_command(label="⭐ Buka Whitelist Kata", command=self.open_whitelist_window)
        menu.add_command(label="🚫 Buka Blocklist Kata", command=self.open_blacklist_window)
        menu.add_command(label="Pendataan Koreksi Sampel", command=self.open_koreksi_window)
        menu.add_command(label="🏷️ Kelola Kategori Custom", command=self.open_custom_categories_window)
        menu.add_command(label="🔥 Pengaturan Mode Brutal", command=self.open_brutal_settings_window)

        # Submenu Mode Permainan (Default, Santai, Brutal)
        cur_gm = self.config.get("game_mode", "santai" if self.mode_santai_var.get() else "default")
        if cur_gm == "normal":
            cur_gm = "default"
        game_mode_menu = tk.Menu(menu, tearoff=0, bg="#181825", fg=THEME["text_primary"], activebackground=THEME["bg_hover"], activeforeground="#f5e0dc", selectcolor="#a6e3a1")
        game_mode_menu.add_command(
            label=f"{'✓ ' if cur_gm in ('default', 'normal') else '   '}⚔️ Mode Default",
            command=lambda: self.set_game_mode("default")
        )
        game_mode_menu.add_command(
            label=f"{'✓ ' if cur_gm == 'santai' else '   '}🌿 Mode Santai (Tanpa X, Q, F)",
            command=lambda: self.set_game_mode("santai")
        )
        game_mode_menu.add_command(
            label=f"{'✓ ' if cur_gm == 'brutal' else '   '}🔥 Mode Brutal",
            command=lambda: self.set_game_mode("brutal")
        )
        game_mode_menu.add_separator()
        game_mode_menu.add_command(label="🔥 Pengaturan Mode Brutal...", command=self.open_brutal_settings_window)
        menu.add_cascade(label=f"🎮 Mode Permainan: {cur_gm.upper()}", menu=game_mode_menu)

        # Submenu Mode Sortir Tier 0 (Custom Traps)
        cur_t0 = self.config.get("tier0_sort_mode", "default")
        tier0_menu = tk.Menu(menu, tearoff=0, bg="#181825", fg=THEME["text_primary"], activebackground=THEME["bg_hover"], activeforeground="#f5e0dc", selectcolor="#a6e3a1")
        tier0_menu.add_command(
            label=f"{'✓ ' if cur_t0 == 'default' else '   '}Default (Panjang 4-7 & Abjad A-Z)",
            command=lambda: self._set_tier0_sort_mode("default")
        )
        tier0_menu.add_command(
            label=f"{'✓ ' if cur_t0 == 'tag_order' else '   '}Sesuai Urutan Tag Kustom",
            command=lambda: self._set_tier0_sort_mode("tag_order")
        )
        menu.add_cascade(label=f"📊 Mode Sortir Tier 0: {'Default' if cur_t0 == 'default' else 'Urutan Tag'}", menu=tier0_menu)
        menu.add_separator()

        # Kelompok 3: Area Gameplay & Kalibrasi
        menu.add_command(label="🎮 Set Area Gameplay", command=self.open_gameplay_region_selector)
        menu.add_command(label="📸 Screenshot Area Gameplay (F3)", command=self.on_capture_gameplay_kalibrasi)
        menu.add_command(label="📋 Log Gameplay", command=self.open_gameplay_history_window)
        menu.add_separator()

        # Submenu Pilihan Kecepatan Scan (Pilih langsung sekali klik tanpa ganti-ganti mode)
        speed_menu = tk.Menu(
            menu,
            tearoff=0,
            bg="#181825",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            activeforeground="#f5e0dc",
            selectcolor="#a6e3a1"
        )
        curr_speed = self.config.get("scan_interval_sec", 0.08)
        self.scan_speed_var = tk.DoubleVar(value=curr_speed)
        for sec, label in self.speed_options:
            speed_menu.add_radiobutton(
                label=label,
                variable=self.scan_speed_var,
                value=sec,
                command=lambda s=sec, l=label: self._set_scan_speed(s, l),
                selectcolor="#a6e3a1"
            )
        menu.add_cascade(label="⚡ Kecepatan Scan", menu=speed_menu)

        dev_status = "✅ AKTIF" if self.dev_mode_var.get() else "⚪ NONAKTIF"
        menu.add_checkbutton(
            label=f"🛠️ Mode Development (Restart) [{dev_status}]",
            variable=self.dev_mode_var,
            command=self.on_toggle_dev_mode,
            selectcolor="#a6e3a1"
        )
        menu.add_command(label="🔄 Cek Update Git...", command=lambda: self.check_for_updates(manual=True))

        try:
            x = self.btn_settings.winfo_rootx()
            y = self.btn_settings.winfo_rooty() + self.btn_settings.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _set_scan_speed(self, sec, label):
        """Mengatur interval scan langsung ke nilai yang dipilih"""
        self.config["scan_interval_sec"] = sec
        save_config(self.config)
        if hasattr(self, "lbl_scan_speed_indicator") and self.lbl_scan_speed_indicator.winfo_exists():
            self.lbl_scan_speed_indicator.config(text=f"Speed: {int(sec*1000)}ms")
        self._update_window_title()
        self.show_toast(f"⚡ Kecepatan scan diatur ke: {label}")

    def _on_search_text_changed(self, *args):
        """Pencarian manual realtime saat pengguna mengetik (Auto-search & overwrite OCR)"""
        raw_text = self.search_var.get()
        clean_text = "".join([c for c in raw_text.upper() if c.isalpha()])
        if clean_text:
            self.update_results(clean_text)
        else:
            if hasattr(self, "last_detected_word") and self.last_detected_word:
                self.update_results(self.last_res_data or self.last_detected_word)
            else:
                self.lbl_prefix_display.config(text="-", fg="#6c7086")
                self.lbl_conf.config(text="")
                for slot in self.word_card_pool:
                    if slot.get("packed", False):
                        slot["frame"].pack_forget()
                        slot["packed"] = False

    def _on_main_tab_changed(self, tab_id):
        """Handler perpindahan 4 Tab Utama: LIVE, TAGS, KAMUS, SYSTEM"""
        # Sembunyikan semua kontainer tab
        self.tab_live_container.pack_forget()
        self.tab_tags_container.pack_forget()
        self.tab_kamus_container.pack_forget()
        self.tab_system_container.pack_forget()

        if tab_id == "live":
            # Di tab LIVE, mini ticker bar disembunyikan agar ruang kartu rekomendasi maksimal
            if hasattr(self, "mini_ticker") and self.mini_ticker.winfo_exists():
                self.mini_ticker.pack_forget()
            self.tab_live_container.pack(fill=tk.BOTH, expand=True)
            if getattr(self, "_dirty_quick_bar", False) or not self.custom_cats_bar.winfo_children():
                self._render_custom_category_quick_bar()
                self._dirty_quick_bar = False
            if getattr(self, "_dirty_live_results", False):
                if hasattr(self, "last_detected_word") and self.last_detected_word:
                    self.update_results(self.last_detected_word)
                self._dirty_live_results = False
        else:
            # Di tab non-LIVE (TAGS, KAMUS, SYSTEM), mini ticker tampil ramping di atas
            if hasattr(self, "mini_ticker") and self.mini_ticker.winfo_exists():
                self.mini_ticker.pack(fill=tk.X, padx=8, pady=(2, 0), after=self.top_tab_strip)
            
            if tab_id == "tags":
                self.tab_tags_container.pack(fill=tk.BOTH, expand=True)
            elif tab_id == "kamus":
                self.tab_kamus_container.pack(fill=tk.BOTH, expand=True)
                # Auto-focus ke input tab kamus
                sub = self.tab_kamus_container.sub_strip.active_tab
                self.tab_kamus_container._on_sub_tab_changed(sub)
            elif tab_id == "system":
                self.tab_system_container.pack(fill=tk.BOTH, expand=True)

    def clear_manual_search(self):
        """Membersihkan kotak pencarian manual dan kembali ke OCR"""
        if hasattr(self, "search_var"):
            self.search_var.set("")
        if hasattr(self, "entry_manual") and self.entry_manual.winfo_exists():
            self.entry_manual.focus_set()

    def _update_window_title(self):
        """Memperbarui judul window: SAKA Overlay (<branch jika bukan main> <commit>) [<kecepatan scan>]"""
        try:
            branch = self.updater.get_current_branch()
            commit_info = self.updater.get_current_commit()
            commit_hash = commit_info.get("hash", "")
            if branch and branch != "main":
                git_str = f"({branch} {commit_hash})".strip()
            elif commit_hash and commit_hash != "unknown":
                git_str = f"({commit_hash})"
            else:
                git_str = ""
        except Exception:
            git_str = ""

        curr_sec = self.config.get("scan_interval_sec", 0.08)
        speed_label = None
        for sec, lbl in getattr(self, "speed_options", []):
            if abs(sec - curr_sec) < 0.005:
                speed_label = lbl
                break
        if not speed_label:
            speed_label = f"⚡ {int(curr_sec * 1000)}ms"

        parts = ["SAKA Overlay"]
        if git_str:
            parts.append(git_str)
        parts.append(f"[{speed_label}]")

        full_title = " ".join(parts)
        self.root.title(full_title)
        # Sesuai permintaan user, title bar hanya menampilkan logo image tanpa duplikasi teks apapun

    def _update_mode_santai_button(self):
        """Memperbarui visual segmented cyber pills: DEFAULT, SANTAI, BRUTAL"""
        if not hasattr(self, "btn_pill_default"):
            return
        cur_mode = self.config.get("game_mode", "santai" if getattr(self, "mode_santai_var", tk.BooleanVar()).get() else "default")
        if cur_mode == "normal":
            cur_mode = "default"

        # Reset semua pill ke gaya nonaktif
        self.btn_pill_default.config(bg=THEME["bg_card"], fg=THEME["text_secondary"], activebackground=THEME["bg_hover"], activeforeground=THEME["text_primary"])
        self.btn_pill_santai.config(bg=THEME["bg_card"], fg=THEME["text_secondary"], activebackground=THEME["bg_hover"], activeforeground=THEME["text_primary"])
        self.btn_pill_brutal.config(bg=THEME["bg_card"], fg=THEME["text_secondary"], activebackground=THEME["bg_hover"], activeforeground=THEME["text_primary"])

        if cur_mode == "santai":
            self.btn_pill_santai.config(bg=THEME["santai"], fg=THEME["text_dark"], activebackground=THEME["santai"], activeforeground=THEME["text_dark"])
        elif cur_mode == "brutal":
            self.btn_pill_brutal.config(bg=THEME["danger"], fg=THEME["text_dark"], activebackground=THEME["danger"], activeforeground=THEME["text_dark"])
        else:
            self.btn_pill_default.config(bg=THEME["primary"], fg=THEME["text_dark"], activebackground=THEME["primary"], activeforeground=THEME["text_dark"])

    def _show_game_mode_menu(self, event=None):
        """Menampilkan menu pilihan mode permainan saat tombol mode diklik kanan"""
        menu = tk.Menu(self.root, tearoff=0, bg="#181825", fg=THEME["text_primary"], activebackground=THEME["bg_hover"], activeforeground="#f5e0dc", selectcolor="#a6e3a1")
        cur_gm = self.config.get("game_mode", "santai" if self.mode_santai_var.get() else "default")
        if cur_gm == "normal":
            cur_gm = "default"
        
        prefix_d = "✓ " if cur_gm in ("default", "normal") else "   "
        prefix_s = "✓ " if cur_gm == "santai" else "   "
        prefix_b = "✓ " if cur_gm == "brutal" else "   "
        
        menu.add_command(label=f"{prefix_d}⚔️ Mode Default", command=lambda: self.set_game_mode("default"))
        menu.add_command(label=f"{prefix_s}🌿 Mode Santai (Tanpa X, Q, F)", command=lambda: self.set_game_mode("santai"))
        menu.add_command(label=f"{prefix_b}🔥 Mode Brutal", command=lambda: self.set_game_mode("brutal"))
        menu.add_separator()
        menu.add_command(label="🔥 Pengaturan Mode Brutal...", command=self.open_brutal_settings_window)
        menu.add_command(label="🏷️ Kelola Kategori Custom...", command=self.open_custom_categories_window)
        
        btn = getattr(self, "btn_game_mode", getattr(self, "btn_mode_santai", None))
        if event:
            menu.tk_popup(event.x_root, event.y_root)
        elif btn and btn.winfo_exists():
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height()
            menu.tk_popup(x, y)

    def _update_sort_mode_button(self):
        """Memperbarui teks, icon, dan warna tombol toggle Mode Sortir di Top Bar"""
        if not hasattr(self, "btn_sort_mode") or not self.btn_sort_mode.winfo_exists():
            return
        cur_mode = self.config.get("tier0_sort_mode", "default")
        if cur_mode == "tag_order":
            sort_ico = render_vector_icon("sort", size=13, color=THEME["text_dark"])
            self.btn_sort_mode.config(
                text=" URUT TAG",
                image=sort_ico,
                compound="left",
                bg=THEME["primary"],
                fg=THEME["text_dark"]
            )
            self.btn_sort_mode.image = sort_ico
        else:
            sort_ico = render_vector_icon("sort", size=13, color=THEME["primary"])
            self.btn_sort_mode.config(
                text=" DEFAULT",
                image=sort_ico,
                compound="left",
                bg=THEME["bg_hover"],
                fg=THEME["primary"]
            )
            self.btn_sort_mode.image = sort_ico

    def toggle_sort_mode(self):
        """Toggle mode sortir tier 0 antara 'default' dan 'tag_order' langsung dari UI utama"""
        cur = self.config.get("tier0_sort_mode", "default")
        new_mode = "tag_order" if cur == "default" else "default"
        self._set_tier0_sort_mode(new_mode)

    def cycle_game_mode(self):
        """Beralih mode permainan berurutan: DEFAULT -> SANTAI -> BRUTAL -> DEFAULT"""
        cur = self.config.get("game_mode", "santai" if self.mode_santai_var.get() else "default")
        if cur in ("default", "normal"):
            self.set_game_mode("santai")
        elif cur == "santai":
            self.set_game_mode("brutal")
        else:
            self.set_game_mode("default")

    def toggle_mode_santai(self):
        """Kompatibilitas lama toggle mode"""
        self.cycle_game_mode()

    def on_toggle_mode_santai(self):
        """Kompatibilitas lama"""
        pass

    def set_game_mode(self, new_mode, show_toast=True):
        """
        Mengatur mode permainan (default, santai, atau brutal) dan menyelaraskan status tag kustom.
        - Default: Mengembalikan tag profil default yang disimpan.
        - Santai: Menonaktifkan tag berhuruf X, Q, F dan memfilter kata dengan X/Q/F.
        - Brutal: Mengaktifkan tag kustom yang dikonfigurasi untuk Mode Brutal (AMSI, KSO, RHU, TL, BD, dll).
        """
        if new_mode == "normal":
            new_mode = "default"
        cur_mode = self.config.get("game_mode", "santai" if self.mode_santai_var.get() else "default")
        if cur_mode == "normal":
            cur_mode = "default"
            self.config["game_mode"] = "default"
        if new_mode == cur_mode and self.config.get("game_mode") == new_mode:
            return

        categories = self.config.get("custom_trap_endings", [])

        # 1. Simpan state tag dari mode yang ditinggalkan
        if cur_mode in ("default", "normal"):
            saved_tags = [c.get("suffix", "").upper() for c in categories if c.get("enabled", True)]
            self.config["saved_default_tags"] = saved_tags
            self.config["saved_normal_tags"] = saved_tags
        elif cur_mode == "brutal":
            self.config["brutal_mode_tags"] = [c.get("suffix", "").upper() for c in categories if c.get("enabled", True)]

        # 2. Terapkan konfigurasi mode baru
        if new_mode == "brutal":
            self.config["santai_auto_disabled_tags"] = []
            brutal_tags = set(self.config.get("brutal_mode_tags", ["AMSI", "KSO", "RHU", "TL", "BD"]))
            for cat in categories:
                sfx = cat.get("suffix", "").upper()
                cat["enabled"] = (sfx in brutal_tags)

            self.config["game_mode"] = "brutal"
            self.config["mode_santai"] = False
            self.mode_santai_var.set(False)
            if hasattr(self, "game_mode_var"):
                self.game_mode_var.set("brutal")

            if hasattr(self, "recom_frame") and self.recom_frame.winfo_exists():
                self.recom_frame.config(text=" Rekomendasi Kata (🔥 BRUTAL) ", fg="#f38ba8")
            if show_toast:
                active_cnt = sum(1 for c in categories if c.get("enabled", True))
                self.show_toast(f"🔥 Mode Brutal aktif ({active_cnt} tag brutal dinyalakan)")

        elif new_mode == "santai":
            # Jika sebelumnya dari brutal, pulihkan dulu tag default sebelum menerapkan santai
            if cur_mode == "brutal":
                saved_default = set(self.config.get("saved_default_tags", self.config.get("saved_normal_tags", [])))
                if saved_default:
                    for cat in categories:
                        cat["enabled"] = (cat.get("suffix", "").upper() in saved_default)

            # Matikan tag yang mengandung X, Q, F
            auto_disabled = set()
            for cat in categories:
                sfx = cat.get("suffix", "").upper()
                if any(ch in sfx.lower() for ch in ("x", "q", "f")):
                    if cat.get("enabled", True):
                        cat["enabled"] = False
                        auto_disabled.add(sfx)
            self.config["santai_auto_disabled_tags"] = list(auto_disabled)

            self.config["game_mode"] = "santai"
            self.config["mode_santai"] = True
            self.mode_santai_var.set(True)
            if hasattr(self, "game_mode_var"):
                self.game_mode_var.set("santai")

            if hasattr(self, "recom_frame") and self.recom_frame.winfo_exists():
                self.recom_frame.config(text=" Rekomendasi Kata (tanpa X, Q, F) ", fg="#a6e3a1")
            if show_toast:
                if auto_disabled:
                    tag_str = ", ".join(f"[{t}]" for t in sorted(auto_disabled))
                    self.show_toast(f"🌿 Mode Santai aktif (tanpa X, Q, F) - Tag {tag_str} dinonaktifkan")
                else:
                    self.show_toast("🌿 Mode Santai aktif (tanpa X, Q, F)")

        else:  # "default"
            if cur_mode == "santai":
                auto_disabled = set(self.config.get("santai_auto_disabled_tags", []))
                for cat in categories:
                    if cat.get("suffix", "").upper() in auto_disabled:
                        cat["enabled"] = True
                self.config["santai_auto_disabled_tags"] = []
            elif cur_mode == "brutal":
                saved_default = set(self.config.get("saved_default_tags", self.config.get("saved_normal_tags", [])))
                if saved_default:
                    for cat in categories:
                        cat["enabled"] = (cat.get("suffix", "").upper() in saved_default)

            self.config["game_mode"] = "default"
            self.config["mode_santai"] = False
            self.mode_santai_var.set(False)
            if hasattr(self, "game_mode_var"):
                self.game_mode_var.set("default")

            if hasattr(self, "recom_frame") and self.recom_frame.winfo_exists():
                self.recom_frame.config(text=" Rekomendasi Kata (DEFAULT) ", fg="#f38ba8")
            if show_toast:
                self.show_toast("⚔️ Mode Default aktif (Jebakan X/Z/Q/F aktif)")

        self.config["custom_trap_endings"] = categories
        save_config(self.config)
        self.solver.set_custom_endings(categories)

        self._update_mode_santai_button()
        self._render_custom_category_items()
        self._render_custom_category_quick_bar()

        manual_text = "".join([c for c in self.search_var.get().strip().upper() if c.isalpha()]) if hasattr(self, "search_var") else ""
        if manual_text:
            self.update_results(manual_text)
        elif hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)

    def on_toggle_dict_source(self):
        """Menangani pemilihan sumber kamus (KBBI dan/atau Contek Sambung Kata)"""
        use_kbbi = self.use_kbbi_var.get()
        use_contek = self.use_contek_var.get()

        # Cegah kedua kamus dimatikan sekaligus
        if not use_kbbi and not use_contek:
            self.show_toast("⚠️ Minimal satu sumber kamus harus aktif!")
            self.use_kbbi_var.set(True)
            use_kbbi = True

        self.config["use_kbbi"] = use_kbbi
        self.config["use_contek"] = use_contek
        save_config(self.config)

        success, total_words, msg = self.solver.set_dict_sources(
            use_kbbi=use_kbbi,
            use_contek=use_contek
        )

        if hasattr(self, "lbl_dict_count") and self.lbl_dict_count.winfo_exists():
            self.lbl_dict_count.config(text=f"({total_words:,} kata)")

        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)

        if use_kbbi and use_contek:
            sumber_str = "KBBI + Contek Sambung Kata"
        elif use_kbbi:
            sumber_str = "KBBI Saja"
        else:
            sumber_str = "Contek Sambung Kata Saja"

        self.show_toast(f"📚 Sumber: {sumber_str} ({total_words:,} kata)")

    def open_region_selector(self):
        RegionSelector(self.on_region_selected, title="KLIK & DRAG MOUSE UNTUK MEMILIH AREA AWALAN KATA (PREFIX)")

    def on_region_selected(self, area):
        self.config["screen_area"] = area
        save_config(self.config)
        self.ocr.update_config(self.config)
        self.lbl_coords.config(
            text=f"Area: X={area.get('left',0)} Y={area.get('top',0)} | {area.get('width',0)}x{area.get('height',0)} px"
        )
        self.show_toast(f"Area awalan disimpan: {area['width']}x{area['height']} px")
        self.preview_selected_area()

    def open_gameplay_region_selector(self):
        RegionSelector(
            self.on_gameplay_region_selected,
            title="KLIK & DRAG MOUSE UNTUK MEMILIH AREA GAMEPLAY (KOTAK KATA & KARAKTER)"
        )

    def on_gameplay_region_selected(self, area):
        self.config["gameplay_area"] = area
        save_config(self.config)
        self.gameplay_indexer.update_config(self.config)
        self.show_toast(f"Area gameplay disimpan: {area['width']}x{area['height']} px")
        self.preview_selected_area(
            area=area,
            title=f"AREA GAMEPLAY ({area['width']}x{area['height']})",
            bg_color="#a6e3a1"
        )

    def on_toggle_gameplay_indexing(self):
        val = self.gameplay_indexing_var.get()
        self.config["gameplay_indexing_enabled"] = val
        save_config(self.config)
        if val:
            self.show_toast("🎮 Auto-Index Gameplay AKTIF (Auto Blacklist salah & Auto Learn benar)")
        else:
            self.show_toast("Auto-Index Gameplay dinonaktifkan")

    def preview_selected_area(self, area=None, title=None, bg_color=None):
        """Menampilkan kotak transparan sekejap di layar untuk mengonfirmasi area deteksi"""
        target_area = area or self.config.get("screen_area", {})
        l, t = target_area.get("left", 0), target_area.get("top", 0)
        w, h = target_area.get("width", 100), target_area.get("height", 50)
        bg = bg_color or "#f38ba8"
        t_text = title or f"AREA AWALAN ({w}x{h})"

        preview_win = tk.Toplevel()
        preview_win.overrideredirect(True)
        preview_win.geometry(f"{w}x{h}+{l}+{t}")
        preview_win.attributes("-topmost", True)
        preview_win.attributes("-alpha", 0.45)
        preview_win.configure(bg=bg)

        lbl = tk.Label(
            preview_win,
            text=t_text,
            font=("Segoe UI", 9, "bold"),
            fg="#11111b",
            bg=bg
        )
        lbl.pack(expand=True)

        # Tutup otomatis setelah 1.2 detik
        preview_win.after(1200, preview_win.destroy)

    def toggle_scan(self):
        if not self.is_scanning:
            self.is_scanning = True
            self.btn_toggle.config(text="■ STOP", bg=THEME["danger"], fg=THEME["text_dark"])
            self.status_lbl.config(text="●", fg=THEME["primary"])
            self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
            self.scan_thread.start()
        else:
            self.is_scanning = False
            self.btn_toggle.config(text="▶ MULAI", bg=THEME["primary"], fg=THEME["text_dark"])
            self.status_lbl.config(text="●", fg=THEME["text_muted"])

    def cycle_scan_speed(self):
        curr = self.config.get("scan_interval_sec", 0.08)
        curr_idx = 1
        for i, (sec, _) in enumerate(self.speed_options):
            if abs(sec - curr) < 0.03:
                curr_idx = i
                break
        next_idx = (curr_idx + 1) % len(self.speed_options)
        next_sec, next_label = self.speed_options[next_idx]
        self.config["scan_interval_sec"] = next_sec
        save_config(self.config)
        self.btn_speed.config(text=next_label)
        self._update_window_title()
        self.show_toast(f"Kecepatan scan: {next_label}")

    def _scan_loop(self):
        last_gameplay_scan = 0
        while self.is_scanning:
            interval = self.config.get("scan_interval_sec", 0.08)
            now = time.time()
            try:
                # 1. Scan Awalan Huruf (Prefix Kotak Bawah)
                res_data = self.ocr.scan_once()
                if res_data.get("saved_path"):
                    self.root.after(0, self._update_koreksi_badge)
                detected_text = res_data.get("text", "")
                if detected_text and detected_text != self.last_detected_word:
                    self.last_detected_word = detected_text
                    self.root.after(0, self.update_results, res_data)

                # 2. Scan Feedback Gameplay (setiap ~150ms)
                if self.config.get("gameplay_indexing_enabled", True) and (now - last_gameplay_scan >= 0.15):
                    last_gameplay_scan = now
                    self.gameplay_indexer.scan_once()

            except Exception as e:
                pass
            time.sleep(interval)

    def on_capture_gameplay_kalibrasi(self):
        """Mengambil snapshot area gameplay dan metadata ke deteksi-gameplay/sample_kalibrasi (Hotkey F3)"""
        saved_img = self.gameplay_indexer.capture_kalibrasi_sample(label="kalibrasi_f3")
        if saved_img:
            fn = os.path.basename(saved_img)
            self.show_toast(f"📸 Sampel kalibrasi tersimpan: '{fn}'")
        else:
            self.show_toast("⚠️ Gagal mengambil sampel (pastikan area gameplay sudah diatur)")

    def _on_gameplay_event(self, state, word, action, log_entry):
        """Callback dari background thread saat ada event gameplay"""
        self.root.after(0, self._handle_gameplay_event_ui, state, word, action, log_entry)

    def _handle_gameplay_event_ui(self, state, word, action, log_entry):
        if action == "AUTO_BLACKLISTED_CENSORED":
            self.show_toast(f"⚠️ [Safe Chat] '{word}' disensor Roblox (######) -> Otomatis diblokir!")
        elif action == "AUTO_BLACKLISTED":
            self.show_toast(f"🚫 [Auto-Detect] '{word}' ditolak game -> Dicatat di auto_blacklist.txt")
        elif action == "AUTO_LEARNED":
            self.show_toast(f"✨ [Auto-Detect] '{word}' valid di game -> Dicatat di auto_kata_baru.txt")

        if hasattr(self, "gameplay_history_win") and self.gameplay_history_win and self.gameplay_history_win.winfo_exists():
            self._refresh_gameplay_history_table()

    def open_gameplay_history_window(self):
        """Membuka dialog popup riwayat aktivitas indexing gameplay"""
        if hasattr(self, "gameplay_history_win") and self.gameplay_history_win and self.gameplay_history_win.winfo_exists():
            self.gameplay_history_win.lift()
            self.gameplay_history_win.focus_force()
            return

        self.gameplay_history_win, _ = self._create_clean_toplevel(
            "🎮 Riwayat Auto-Index Gameplay", 560, 490, min_w=500, min_h=400
        )

        sub_hdr = tk.Frame(self.gameplay_history_win, bg="#181825", padx=12, pady=6)
        sub_hdr.pack(fill=tk.X)
        tk.Label(
            sub_hdr,
            text="Log pemantauan frame status game (auto_blacklist & auto_kata_baru)",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg="#181825"
        ).pack(side=tk.LEFT)

        # Options Frame
        opts_box = tk.Frame(self.gameplay_history_win, bg="#1e1e2e", padx=12, pady=6)
        opts_box.pack(fill=tk.X)

        self.bl_inv_var = tk.BooleanVar(value=self.config.get("auto_blacklist_invalid", True))
        def on_toggle_bl_inv():
            self.config["auto_blacklist_invalid"] = self.bl_inv_var.get()
            save_config(self.config)
            self.gameplay_indexer.update_config(self.config)

        chk_bl = tk.Checkbutton(
            opts_box,
            text="Catat kata ditolak ke auto_blacklist.txt",
            variable=self.bl_inv_var,
            command=on_toggle_bl_inv,
            font=("Segoe UI", 8),
            fg="#f38ba8",
            bg="#1e1e2e",
            selectcolor="#313244",
            activebackground="#1e1e2e"
        )
        chk_bl.pack(side=tk.LEFT, padx=(0, 10))

        self.lrn_val_var = tk.BooleanVar(value=self.config.get("auto_learn_valid", True))
        def on_toggle_lrn_val():
            self.config["auto_learn_valid"] = self.lrn_val_var.get()
            save_config(self.config)
            self.gameplay_indexer.update_config(self.config)

        chk_lrn = tk.Checkbutton(
            opts_box,
            text="Catat kata valid baru ke auto_kata_baru.txt",
            variable=self.lrn_val_var,
            command=on_toggle_lrn_val,
            font=("Segoe UI", 8),
            fg="#a6e3a1",
            bg="#1e1e2e",
            selectcolor="#313244",
            activebackground="#1e1e2e"
        )
        chk_lrn.pack(side=tk.LEFT)

        # Info Box
        sub_info = tk.Label(
            self.gameplay_history_win,
            text="🛡️ Kamus & blacklist resmi Anda 100% aman (kata di bawah hanya disimpan ke file staging terpisah)",
            font=("Segoe UI", 8, "italic"),
            fg=THEME["text_secondary"],
            bg="#1e1e2e",
            padx=12
        )
        sub_info.pack(anchor=tk.W)

        # Treeview Tabel Riwayat
        tree_frame = tk.Frame(self.gameplay_history_win, bg="#1e1e2e", padx=12, pady=4)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("Waktu", "Status", "Kata", "Tindakan", "Keterangan")
        self.tree_history = ttk.Treeview(tree_frame, columns=cols, show="headings", height=9)
        self.tree_history.heading("Waktu", text="Waktu")
        self.tree_history.heading("Status", text="Status")
        self.tree_history.heading("Kata", text="Kata")
        self.tree_history.heading("Tindakan", text="Tindakan")
        self.tree_history.heading("Keterangan", text="Keterangan")

        self.tree_history.column("Waktu", width=65, anchor=tk.CENTER)
        self.tree_history.column("Status", width=110, anchor=tk.CENTER)
        self.tree_history.column("Kata", width=80, anchor=tk.CENTER)
        self.tree_history.column("Tindakan", width=140, anchor=tk.W)
        self.tree_history.column("Keterangan", width=140, anchor=tk.W)

        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_history.yview)
        self.tree_history.configure(yscrollcommand=tree_scroll.set)

        self.tree_history.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bar Buka File Terpisah
        file_bar = tk.Frame(self.gameplay_history_win, bg="#1e1e2e", padx=12, pady=4)
        file_bar.pack(fill=tk.X)

        def _open_file(filepath):
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("# Daftar kata auto-detect\n")
            try:
                os.startfile(filepath)
            except Exception as e:
                self.show_toast(f"Gagal membuka file: {e}")

        def _open_dir(dirpath):
            os.makedirs(dirpath, exist_ok=True)
            try:
                os.startfile(dirpath)
            except Exception as e:
                self.show_toast(f"Gagal membuka folder: {e}")

        btn_open_bl = tk.Button(
            file_bar,
            text="📂 Buka auto_blacklist.txt",
            font=("Segoe UI", 8),
            bg="#313244",
            fg="#f38ba8",
            relief=tk.FLAT,
            command=lambda: _open_file(self.gameplay_indexer.auto_blacklist_path)
        )
        btn_open_bl.pack(side=tk.LEFT, padx=(0, 4))

        btn_open_baru = tk.Button(
            file_bar,
            text="📂 Buka auto_kata_baru.txt",
            font=("Segoe UI", 8),
            bg="#313244",
            fg="#a6e3a1",
            relief=tk.FLAT,
            command=lambda: _open_file(self.gameplay_indexer.auto_kata_baru_path)
        )
        btn_open_baru.pack(side=tk.LEFT, padx=4)

        btn_open_samples = tk.Button(
            file_bar,
            text="📁 Sampel F3",
            font=("Segoe UI", 8),
            bg="#313244",
            fg="#f9e2af",
            relief=tk.FLAT,
            command=lambda: _open_dir(self.gameplay_indexer.kalibrasi_dir)
        )
        btn_open_samples.pack(side=tk.LEFT, padx=4)

        # Bottom Bar
        bbar = tk.Frame(self.gameplay_history_win, bg="#181825", padx=12, pady=8)
        bbar.pack(fill=tk.X)

        btn_clear = tk.Button(
            bbar,
            text="🗑️ Bersihkan Riwayat Sesi",
            font=("Segoe UI", 9),
            bg="#45475a",
            fg=THEME["text_primary"],
            relief=tk.FLAT,
            command=self._clear_gameplay_history
        )
        btn_clear.pack(side=tk.LEFT)

        btn_close = tk.Button(
            bbar,
            text="Tutup",
            font=("Segoe UI", 9),
            bg="#313244",
            fg=THEME["text_primary"],
            relief=tk.FLAT,
            command=self.gameplay_history_win.destroy
        )
        btn_close.pack(side=tk.RIGHT)

        self._refresh_gameplay_history_table()

    def _refresh_gameplay_history_table(self):
        if not hasattr(self, "tree_history") or not self.tree_history.winfo_exists():
            return
        for row in self.tree_history.get_children():
            self.tree_history.delete(row)

        for entry in reversed(self.gameplay_indexer.history):
            st_text = entry.get("state", "")
            if st_text == "KATA_SALAH":
                st_display = "❌ Ditolak Game"
            elif st_text == "SUDAH_DIGUNAKAN":
                st_display = "⚠️ Sudah Dipakai"
            elif st_text == "KATA_BENAR":
                st_display = "✅ Jawaban Benar"
            else:
                st_display = st_text

            act_text = entry.get("action", "")
            if act_text == "AUTO_BLACKLISTED":
                act_display = "🚫 auto_blacklist.txt"
            elif act_text == "AUTO_LEARNED":
                act_display = "✨ auto_kata_baru.txt"
            elif act_text == "ALREADY_IN_AUTO_BLACKLIST":
                act_display = "Sudah di auto_blacklist"
            elif act_text == "ALREADY_IN_AUTO_NEW":
                act_display = "Sudah di auto_kata_baru"
            elif act_text == "KNOWN_IN_OFFICIAL_DICT":
                act_display = "Sudah di Kamus Resmi"
            elif act_text == "DETECTED_WRONG":
                act_display = "Terdeteksi Salah"
            else:
                act_display = act_text or "-"

            self.tree_history.insert(
                "",
                tk.END,
                values=(
                    entry.get("time", ""),
                    st_display,
                    entry.get("word", ""),
                    act_display,
                    entry.get("detail", "")
                )
            )

    def _clear_gameplay_history(self):
        self.gameplay_indexer.history.clear()
        self._refresh_gameplay_history_table()
        self.show_toast("Riwayat auto-index dibersihkan")

    def open_gameplay_classifier_window(self):
        """Membuka dialog visual untuk mengklasifikasikan kandidat momen gameplay (hasil video extractor atau auto-capture)"""
        if hasattr(self, "classifier_win") and self.classifier_win and self.classifier_win.winfo_exists():
            self.classifier_win.lift()
            self.classifier_win.focus_force()
            return

        self.classifier_win, _ = self._create_clean_toplevel(
            "🎮 Klasifikasi Momen Gameplay", 540, 670, min_w=480, min_h=580
        )

        self._classifier_unclassified_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "deteksi-gameplay", "unclassified"
        )
        os.makedirs(self._classifier_unclassified_dir, exist_ok=True)

        self._classifier_items = []
        self._classifier_current_idx = 0
        self._classifier_tk_img = None

        hdr = tk.Frame(self.classifier_win, bg="#181825", padx=12, pady=6)
        hdr.pack(fill=tk.X)

        tk.Label(
            hdr,
            text="Klasifikasi visual momen gameplay unclassified",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg="#181825"
        ).pack(side=tk.LEFT)

        self.btn_classifier_extract = tk.Button(
            hdr,
            text="🎬 Ekstrak Video",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#a6e3a1",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._classifier_pick_and_extract_video
        )
        self.btn_classifier_extract.pack(side=tk.RIGHT, padx=(4, 0))

        btn_folder = tk.Button(
            hdr,
            text="📂 Buka Folder",
            font=("Segoe UI", 8),
            bg="#313244",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=lambda: os.startfile(os.path.dirname(self._classifier_unclassified_dir))
        )
        btn_folder.pack(side=tk.RIGHT, padx=(4, 0))

        btn_clear_all = tk.Button(
            hdr,
            text="🧹 Kosongkan",
            font=("Segoe UI", 8),
            bg="#313244",
            fg="#f38ba8",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._classifier_clear_all_unclassified
        )
        btn_clear_all.pack(side=tk.RIGHT)

        # Counter & Info bar
        bar_info = tk.Frame(self.classifier_win, bg=THEME["bg_card"], padx=10, pady=6)
        bar_info.pack(fill=tk.X)

        self.lbl_class_counter = tk.Label(
            bar_info,
            text="Memuat sampel...",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_primary"],
            bg=THEME["bg_card"]
        )
        self.lbl_class_counter.pack(side=tk.LEFT)

        self.lbl_class_trigger = tk.Label(
            bar_info,
            text="",
            font=("Segoe UI", 8, "italic"),
            fg="#fab387",
            bg=THEME["bg_card"]
        )
        self.lbl_class_trigger.pack(side=tk.RIGHT)

        # Preview Container
        preview_container = tk.Frame(self.classifier_win, bg="#181825", padx=6, pady=6)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        self.lbl_class_img = tk.Label(
            preview_container,
            text="Tidak ada sampel untuk diklasifikasi\nKlik '🎬 Ekstrak Video' atau taruh file rekaman.",
            font=("Segoe UI", 10),
            fg="#6c7086",
            bg="#181825"
        )
        self.lbl_class_img.pack(fill=tk.BOTH, expand=True)

        # Input Kata Field
        input_box = tk.Frame(self.classifier_win, bg="#1e1e2e", padx=12, pady=4)
        input_box.pack(fill=tk.X)

        lbl_w = tk.Label(
            input_box,
            text="Kata Terbaca:",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_primary"],
            bg="#1e1e2e"
        )
        lbl_w.pack(side=tk.LEFT, padx=(0, 6))

        self._classifier_word_var = tk.StringVar()
        def _on_word_var_change(*args):
            val = self._classifier_word_var.get()
            # Hapus angka jika sempat masuk dan ubah otomatis ke uppercase
            cleaned = "".join(c for c in val if not c.isdigit()).upper()
            if val != cleaned:
                self._classifier_word_var.set(cleaned)
        self._classifier_word_var.trace_add("write", _on_word_var_change)

        self.entry_class_word = tk.Entry(
            input_box,
            textvariable=self._classifier_word_var,
            font=("Segoe UI", 11, "bold"),
            bg="#313244",
            fg="#f9e2af",
            insertbackground="#f9e2af",
            relief=tk.FLAT
        )
        self.entry_class_word.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_clr_entry = tk.Button(
            input_box,
            text="❌ Kosongkan",
            font=("Segoe UI", 8),
            bg="#313244",
            fg="#f38ba8",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=lambda: self.entry_class_word.delete(0, tk.END)
        )
        btn_clr_entry.pack(side=tk.LEFT, padx=(4, 0))

        lbl_hint = tk.Label(
            self.classifier_win,
            text="💡 Tip: Kosongkan kolom jika tidak tahu kata aslinya. Gambar tetap tersimpan rapi.",
            font=("Segoe UI", 8, "italic"),
            fg="#6c7086",
            bg="#1e1e2e"
        )
        lbl_hint.pack(anchor="w", padx=16, pady=(0, 2))

        # Action Buttons Frame
        btn_box = tk.LabelFrame(
            self.classifier_win,
            text=" Pilih Klasifikasi (Tekan 1 / 2 / 3 / 0 / Del) ",
            font=("Segoe UI", 8, "bold"),
            fg=THEME["text_secondary"],
            bg="#1e1e2e",
            padx=8,
            pady=8
        )
        btn_box.pack(fill=tk.X, padx=12, pady=6)

        # Baris 1: Kategori klasifikasi
        row1 = tk.Frame(btn_box, bg="#1e1e2e")
        row1.pack(fill=tk.X, pady=(0, 6))

        btn_salah = tk.Button(
            row1,
            text="[1] ❌ Kata Salah",
            font=("Segoe UI", 9, "bold"),
            bg="#f38ba8",
            fg="#11111b",
            activebackground=THEME["danger_bg"],
            relief=tk.FLAT,
            padx=6,
            pady=6,
            cursor="hand2",
            command=lambda: self._classifier_classify_action("kata-tidak-ada")
        )
        btn_salah.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        btn_used = tk.Button(
            row1,
            text="[2] ⚠️ Sudah Dipakai",
            font=("Segoe UI", 9, "bold"),
            bg="#f9e2af",
            fg="#11111b",
            activebackground="#f5e0dc",
            relief=tk.FLAT,
            padx=6,
            pady=6,
            cursor="hand2",
            command=lambda: self._classifier_classify_action("sudah-dipakai")
        )
        btn_used.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        btn_benar = tk.Button(
            row1,
            text="[3] ✅ Kata Benar",
            font=("Segoe UI", 9, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground=THEME["accent_neon"],
            relief=tk.FLAT,
            padx=6,
            pady=6,
            cursor="hand2",
            command=lambda: self._classifier_classify_action("benar")
        )
        btn_benar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        btn_default = tk.Button(
            row1,
            text="[0] ⬜ Sedang Ngetik",
            font=("Segoe UI", 9, "bold"),
            bg="#89dceb",
            fg="#11111b",
            activebackground="#74c7ec",
            relief=tk.FLAT,
            padx=6,
            pady=6,
            cursor="hand2",
            command=lambda: self._classifier_classify_action("default")
        )
        btn_default.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Baris 2: Navigasi & Hapus
        row2 = tk.Frame(btn_box, bg="#1e1e2e")
        row2.pack(fill=tk.X)

        btn_prev = tk.Button(
            row2,
            text="◀ Sebelumnya",
            font=("Segoe UI", 8),
            bg="#313244",
            fg=THEME["text_primary"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._classifier_prev
        )
        btn_prev.pack(side=tk.LEFT, padx=2)

        btn_next = tk.Button(
            row2,
            text="Selanjutnya ▶",
            font=("Segoe UI", 8),
            bg="#313244",
            fg=THEME["text_primary"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._classifier_next
        )
        btn_next.pack(side=tk.LEFT, padx=2)

        btn_del = tk.Button(
            row2,
            text="🗑️ Abaikan / Hapus [Del]",
            font=("Segoe UI", 8, "bold"),
            bg="#45475a",
            fg="#f38ba8",
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._classifier_delete_current
        )
        btn_del.pack(side=tk.RIGHT, padx=2)

        # Keyboard shortcuts cerdas: 0, 1, 2, 3 selalu bertindak sebagai tombol aksi klasifikasi
        def _on_classifier_keypress(e):
            # Cek penekanan angka (baik baris angka keyboard maupun Numpad)
            if e.keysym in ("0", "KP_0") or e.char == "0":
                self._classifier_classify_action("default")
                return "break"
            elif e.keysym in ("1", "KP_1") or e.char == "1":
                self._classifier_classify_action("kata-tidak-ada")
                return "break"
            elif e.keysym in ("2", "KP_2") or e.char == "2":
                self._classifier_classify_action("sudah-dipakai")
                return "break"
            elif e.keysym in ("3", "KP_3") or e.char == "3":
                self._classifier_classify_action("benar")
                return "break"

            # Navigasi panah
            elif e.keysym == "Left":
                if e.widget != self.entry_class_word or self.entry_class_word.index(tk.INSERT) == 0:
                    self._classifier_prev()
                    return "break"
            elif e.keysym == "Right":
                if e.widget != self.entry_class_word or self.entry_class_word.index(tk.INSERT) == len(self.entry_class_word.get()):
                    self._classifier_next()
                    return "break"

            # Tombol Delete: abaikan/hapus sampel
            elif e.keysym == "Delete":
                if e.widget != self.entry_class_word or not self.entry_class_word.select_present():
                    self._classifier_delete_current()
                    return "break"

            # Tombol Escape: kosongkan input atau tutup jendela
            elif e.keysym == "Escape":
                if self.entry_class_word.get():
                    self.entry_class_word.delete(0, tk.END)
                else:
                    self.classifier_win.destroy()
                return "break"

            # Jika mengetik huruf alfabet (a-z / A-Z) dan fokus berada di luar entry,
            # otomatis pindahkan fokus ke entry dan masukkan hurufnya
            elif len(e.char) == 1 and e.char.isalpha() and e.widget != self.entry_class_word:
                self.entry_class_word.focus_set()
                self.entry_class_word.delete(0, tk.END)
                self.entry_class_word.insert(tk.END, e.char.upper())
                return "break"

        self.classifier_win.bind("<KeyPress>", _on_classifier_keypress)
        self.entry_class_word.bind("<KeyPress>", _on_classifier_keypress)

        self._classifier_load_items()

    def _classifier_load_items(self):
        """Memuat daftar gambar PNG yang belum diklasifikasi di folder unclassified"""
        self._classifier_items = []
        if os.path.exists(self._classifier_unclassified_dir):
            for f in sorted(os.listdir(self._classifier_unclassified_dir)):
                if f.lower().endswith(".png"):
                    self._classifier_items.append(os.path.join(self._classifier_unclassified_dir, f))

        self._classifier_current_idx = 0
        self._classifier_show_current()

    def _classifier_show_current(self):
        """Menampilkan gambar dan info kandidat momen saat ini"""
        total = len(self._classifier_items)
        if total == 0:
            self.lbl_class_counter.config(text="Tidak ada sampel tersisa (0 / 0)", fg=THEME["text_secondary"])
            self.lbl_class_trigger.config(text="")
            self.lbl_class_img.config(
                image="",
                text="Semua momen sudah diklasifikasikan! 🎉\nKlik '🎬 Ekstrak Video' untuk memproses video rekaman baru."
            )
            self.entry_class_word.delete(0, tk.END)
            self._classifier_tk_img = None
            return

        if self._classifier_current_idx >= total:
            self._classifier_current_idx = total - 1
        elif self._classifier_current_idx < 0:
            self._classifier_current_idx = 0

        img_path = self._classifier_items[self._classifier_current_idx]
        fn = os.path.basename(img_path)

        # Baca metadata JSON jika ada
        meta_path = os.path.splitext(img_path)[0] + ".json"
        trigger_str = ""
        meta_dict = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta_dict = json.load(f)
                tt = meta_dict.get("trigger_type", "")
                ts = meta_dict.get("timestamp_sec", "")
                trigger_str = f"{tt} (detik {ts}s)"
            except Exception:
                pass

        self.lbl_class_counter.config(
            text=f"Momen {self._classifier_current_idx + 1} / {total}: {fn[:30]}",
            fg=THEME["text_primary"]
        )
        self.lbl_class_trigger.config(text=trigger_str)

        # Muat gambar dan resize proporsional untuk ditampilkan (maks 500x320)
        try:
            with Image.open(img_path) as raw_img:
                pil_img = raw_img.copy()
            orig_w, orig_h = pil_img.size

            # Jika full screenshot 1920x1200, lakukan crop fokus gameplay tengah agar teks terlihat jelas
            if orig_w >= 1200 and orig_h >= 700:
                # Crop area gameplay (y: 18%..55%, x: 32%..68%)
                cy1, cy2 = int(orig_h * 0.18), int(orig_h * 0.55)
                cx1, cx2 = int(orig_w * 0.32), int(orig_w * 0.68)
                crop_pil = pil_img.crop((cx1, cy1, cx2, cy2))
            else:
                crop_pil = pil_img

            cw, ch = crop_pil.size
            max_w, max_h = 500, 310
            scale = min(max_w / cw, max_h / ch)
            new_w, new_h = max(1, int(cw * scale)), max(1, int(ch * scale))
            resized = crop_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)

            self._classifier_tk_img = ImageTk.PhotoImage(resized)
            self.lbl_class_img.config(image=self._classifier_tk_img, text="")

            # Coba jalankan OCR cerdas: Cari kontur kotak kata (putih / merah) terlebih dahulu agar tidak membaca username Roblox
            detected_clean = ""
            try:
                cv_img = cv2.cvtColor(np.array(crop_pil), cv2.COLOR_RGB2BGR)
                H_c, W_c = cv_img.shape[:2]
                
                # Deteksi kotak input (putih atau merah) di tengah layar
                gray_c = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                _, thresh_white = cv2.threshold(gray_c, 210, 255, cv2.THRESH_BINARY)
                
                # Mask merah pekat
                br_b, br_g, br_r = cv2.split(cv_img.astype(np.int16))
                pure_red = (br_r > 140) & (br_g < 95) & (br_b < 95)
                mask_red = pure_red.astype(np.uint8) * 255
                
                combined_box = cv2.bitwise_or(thresh_white, mask_red)
                cnts, _ = cv2.findContours(combined_box, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                target_crop = None
                for c in cnts:
                    x, y, w, h = cv2.boundingRect(c)
                    # Kotak kata di Roblox biasanya rasio 1.0 s/d 4.0 dan ukuran w > 50, h > 30
                    if w >= 50 and h >= 28 and 0.8 <= (w / h) <= 4.5 and y < int(H_c * 0.6):
                        target_crop = cv_img[max(0, y-4):min(H_c, y+h+4), max(0, x-4):min(W_c, x+w+4)]
                        break
                
                # Jika kotak ditemukan, OCR tepat di kotak tersebut.
                # JANGAN OCR jika kotak tidak ditemukan (misal momen GREEN_FLASH di mana kotak sudah hilang),
                # untuk mencegah OCR membaca spanduk/background arena (seperti "Buy & Gift to your friends").
                if target_crop is not None:
                    raw_lines = self.gameplay_indexer.ocr_crop(target_crop)
                    for line in raw_lines:
                        clean = "".join(c for c in line if c.isalpha()).upper()
                        has_vowel = any(v in clean for v in 'AIUEO')
                        is_subtext = any(k in clean.lower() for k in ['sudah', 'guna', 'pakai', 'sud'])
                        if 2 <= len(clean) <= 12 and has_vowel and not is_subtext:
                            detected_clean = clean
                            break
            except Exception:
                pass

            self.entry_class_word.delete(0, tk.END)
            if detected_clean:
                self.entry_class_word.insert(0, detected_clean)

            # Otomatis fokuskan ke kolom entry kata dan seleksi semua teks
            # sehingga jika user langsung mengetik huruf, teks auto-detect lama langsung tertimpa
            self.entry_class_word.focus_set()
            self.entry_class_word.select_range(0, tk.END)
            self.entry_class_word.icursor(tk.END)

        except Exception as e:
            self.lbl_class_img.config(image="", text=f"Gagal memuat gambar: {e}")

    def _classifier_classify_action(self, target_category):
        """Memindahkan sampel ke folder kategori yang dipilih dan mencatat ke file terisolasi"""
        if not self._classifier_items or self._classifier_current_idx >= len(self._classifier_items):
            return

        img_path = self._classifier_items[self._classifier_current_idx]

        # Validasi eksistensi file: jika file sudah tidak ada di disk, pop dan tampilkan berikutnya
        if not os.path.exists(img_path):
            self._classifier_items.pop(self._classifier_current_idx)
            self._classifier_show_current()
            return

        fn = os.path.basename(img_path)
        word = self.entry_class_word.get().strip().upper()

        dest_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "deteksi-gameplay", target_category
        )
        os.makedirs(dest_dir, exist_ok=True)

        dest_img_path = os.path.join(dest_dir, fn)
        meta_path = os.path.splitext(img_path)[0] + ".json"
        dest_meta_path = os.path.join(dest_dir, os.path.basename(meta_path))

        try:
            import shutil
            # Gunakan copy2 + remove untuk kehandalan penuh di Windows
            shutil.copy2(img_path, dest_img_path)
            try:
                os.remove(img_path)
            except Exception:
                pass

            # Update / Simpan metadata JSON di folder tujuan
            meta_dict = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta_dict = json.load(f)
                except Exception:
                    pass

            meta_dict["category"] = target_category
            meta_dict["labeled_text"] = word
            try:
                with open(dest_meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_dict, f, indent=4)
                if os.path.exists(meta_path) and meta_path != dest_meta_path:
                    try: os.remove(meta_path)
                    except Exception: pass
            except Exception:
                pass

        except Exception as e:
            self.show_toast(f"Gagal memindahkan sampel: {e}")
            if not os.path.exists(img_path):
                self._classifier_items.pop(self._classifier_current_idx)
                self._classifier_show_current()
            return

        # Catat kata ke file teks klasifikasi tersendiri di folder deteksi-gameplay/ (Terpisah dari auto_<>.txt)
        if target_category == "default":
            if word:
                self._save_klasifikasi_text("klasifikasi_sedang_ngetik.txt", word, fn, "Teks sedang diketik")
                self.show_toast(f"⬜ '{word}' dicatat ke deteksi-gameplay/klasifikasi_sedang_ngetik.txt")
            else:
                self.show_toast("⬜ Sampel baseline disimpan ke deteksi-gameplay/default/")
        elif word and len(word) >= 2:
            if target_category == "kata-tidak-ada":
                self._save_klasifikasi_text("klasifikasi_blacklist.txt", word, fn, "Ditolak Roblox (Kata Salah)")
                self.show_toast(f"❌ '{word}' disimpan ke deteksi-gameplay/klasifikasi_blacklist.txt")
            elif target_category == "sudah-dipakai":
                self._save_klasifikasi_text("klasifikasi_kata_baru.txt", word, fn, "Sudah digunakan ronde ini")
                self.show_toast(f"⚠️ '{word}' disimpan ke deteksi-gameplay/klasifikasi_kata_baru.txt")
            elif target_category == "benar":
                self._save_klasifikasi_text("klasifikasi_kata_baru.txt", word, fn, "Jawaban benar diterima")
                self.show_toast(f"✅ '{word}' disimpan ke deteksi-gameplay/klasifikasi_kata_baru.txt")

        # Hapus item dari list dan tampilkan berikutnya
        self._classifier_items.pop(self._classifier_current_idx)
        self._classifier_show_current()

    def _save_klasifikasi_text(self, filename, word, sample_name, reason=""):
        """Menyimpan kata hasil klasifikasi ke file tersendiri di folder deteksi-gameplay"""
        w = word.strip().lower()
        if not w:
            return
        base_dir = os.path.dirname(os.path.abspath(__file__))
        target_path = os.path.join(base_dir, "deteksi-gameplay", filename)

        existing = set()
        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    for line in f:
                        item = line.strip().split("#")[0].strip().lower()
                        if item:
                            existing.add(item)
            except Exception:
                pass

        if w in existing:
            return

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(f"{w}  # [{now_str}] {reason} (Sampel: {sample_name})\n")
        except Exception:
            pass

    def _classifier_clear_all_unclassified(self):
        """Mengosongkan semua gambar di antrean unclassified"""
        if not self._classifier_items:
            self.show_toast("Antrean unclassified sudah kosong")
            return
        if not messagebox.askyesno("Kosongkan Antrean", f"Hapus semua {len(self._classifier_items)} gambar di antrean unclassified?"):
            return
        try:
            for item in self._classifier_items:
                if os.path.exists(item): os.remove(item)
                meta = os.path.splitext(item)[0] + ".json"
                if os.path.exists(meta): os.remove(meta)
        except Exception as e:
            self.show_toast(f"Sebagian file gagal dihapus: {e}")

        self.show_toast("🧹 Antrean unclassified berhasil dikosongkan")
        self._classifier_load_items()

    def _classifier_delete_current(self):
        """Menghapus sampel yang tidak relevan (shortcut Del) tanpa popup konfirmasi"""
        if not self._classifier_items or self._classifier_current_idx >= len(self._classifier_items):
            return

        img_path = self._classifier_items[self._classifier_current_idx]
        meta_path = os.path.splitext(img_path)[0] + ".json"

        try:
            if os.path.exists(img_path): os.remove(img_path)
            if os.path.exists(meta_path): os.remove(meta_path)
        except Exception:
            pass

        self.show_toast("🗑️ Sampel dihapus")
        self._classifier_items.pop(self._classifier_current_idx)
        self._classifier_show_current()

    def _classifier_prev(self):
        if self._classifier_current_idx > 0:
            self._classifier_current_idx -= 1
            self._classifier_show_current()

    def _classifier_next(self):
        if self._classifier_current_idx < len(self._classifier_items) - 1:
            self._classifier_current_idx += 1
            self._classifier_show_current()

    def _classifier_pick_and_extract_video(self):
        """Membuka dialog file untuk memilih file video recording dan mengekstrak momennya di background thread"""
        rec_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "deteksi-gameplay", "recordings"
        )
        os.makedirs(rec_dir, exist_ok=True)

        vid_path = filedialog.askopenfilename(
            parent=self.classifier_win if hasattr(self, "classifier_win") and self.classifier_win else self.root,
            title="Pilih File Video Rekaman Roblox Sambung Kata",
            initialdir=rec_dir,
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm"),
                ("Semua File", "*.*")
            ]
        )
        if not vid_path:
            return

        vname = os.path.basename(vid_path)
        self.show_toast(f"⏳ Memulai ekstraksi: '{vname}'...")
        if hasattr(self, "btn_classifier_extract") and self.btn_classifier_extract:
            self.btn_classifier_extract.config(text="⏳ Memproses...", state=tk.DISABLED)

        def _on_prog(pct, saved, sec):
            if hasattr(self, "classifier_win") and self.classifier_win and self.classifier_win.winfo_exists():
                self.lbl_class_counter.config(
                    text=f"⏳ Ekstraksi: {pct}% | Tertangkap: {saved} momen | Video: {sec:.1f}s",
                    fg="#fab387"
                )

        def _on_event(saved, sec, tr_type, img_p):
            # Notifikasi info seketika momen berhasil di-capture ke unclassified
            self.show_toast(f"📸 Momen #{saved} tertangkap: {tr_type} ({sec:.1f}s)")
            if hasattr(self, "classifier_win") and self.classifier_win and self.classifier_win.winfo_exists():
                self.lbl_class_trigger.config(text=f"📸 Baru: {tr_type} ({sec:.1f}s)")

        def _worker():
            try:
                count, out_dir = extract_gameplay_events(
                    video_path=vid_path,
                    output_dir=self._classifier_unclassified_dir,
                    progress_callback=lambda p, s, sec: self.root.after(0, lambda: _on_prog(p, s, sec)),
                    event_callback=lambda s, sec, tr, p: self.root.after(0, lambda: _on_event(s, sec, tr, p))
                )
                self.root.after(0, lambda: self._on_video_extract_done(count, vid_path))
            except Exception as err:
                self.root.after(0, lambda: self._on_video_extract_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_video_extract_done(self, count, vid_path):
        if hasattr(self, "btn_classifier_extract") and self.btn_classifier_extract:
            self.btn_classifier_extract.config(text="🎬 Ekstrak Video", state=tk.NORMAL)
        self.show_toast(f"✅ Ekstraksi selesai! {count} momen siap diklasifikasikan.")
        if hasattr(self, "classifier_win") and self.classifier_win and self.classifier_win.winfo_exists():
            self._classifier_load_items()
        else:
            self.open_gameplay_classifier_window()

    def _on_video_extract_error(self, err):
        if hasattr(self, "btn_classifier_extract") and self.btn_classifier_extract:
            self.btn_classifier_extract.config(text="🎬 Ekstrak Video", state=tk.NORMAL)
        self.show_toast(f"⚠️ Gagal ekstraksi video: {err}")

    def on_report_kurang_tepat(self):
        """
        Langsung mengambil screenshot seketika dan menyimpannya ke folder sample/kurang_tepat
        tanpa dialog popup agar pemain tidak terganggu saat bermain cepat.
        """
        current_detected = self.last_detected_word
        current_conf = 1.0
        if isinstance(getattr(self, "last_res_data", None), dict):
            current_conf = self.last_res_data.get("confidence", 1.0)
        elif self.ocr.last_detection_result:
            current_conf = self.ocr.last_detection_result.get("confidence", 1.0)

        # Jika belum ada screenshot aktif di engine, ambil langsung dari screen_area
        if self.ocr.last_captured_image is None:
            area = self.config.get("screen_area")
            if area:
                self.ocr.last_captured_image = self.ocr.capture_screen_area(area)

        if self.ocr.last_captured_image is None:
            self.show_toast("⚠️ Belum ada area layar yang diatur! Set area dulu lewat '🎯 Set Area'")
            return

        saved_path = self.ocr.save_to_kurang_tepat(
            detected_text=current_detected,
            confidence=current_conf,
            correct_text=None
        )

        if saved_path:
            fn = os.path.basename(saved_path)
            self._update_koreksi_badge()
            self.show_toast(f"📸 Tersimpan ke kurang_tepat: '{fn}'")
        else:
            self.show_toast("⚠️ Gagal menyimpan screenshot deteksi salah")

    def on_manual_submit(self, event=None):
        raw_text = self.search_var.get().strip() if hasattr(self, "search_var") else ""
        if raw_text:
            self.update_results(raw_text)

    def update_results(self, res_data):
        self.last_res_data = res_data
        # res_data bisa berupa string (manual) atau dict (dari ocr)
        is_manual = isinstance(res_data, str)
        if is_manual:
            prefix = res_data
            conf = 1.0
            is_low = False
            alts = []
            saved_path = None
        else:
            prefix = res_data.get("text", "")
            conf = res_data.get("confidence", 1.0)
            is_low = res_data.get("is_low_confidence", False)
            alts = res_data.get("alternatives", [])
            saved_path = res_data.get("saved_path", None)

        prefix_clean = "".join([c for c in prefix.upper() if c.isalpha()])

        # Cek apakah pengguna sedang memiliki input di kotak pencarian manual
        manual_active = ""
        if hasattr(self, "search_var"):
            manual_active = "".join([c for c in self.search_var.get().strip().upper() if c.isalpha()])

        if not is_manual:
            if prefix_clean:
                self.last_detected_word = prefix_clean
                self.lbl_prefix_display.config(text=prefix_clean, fg="#f9e2af")
            else:
                self.lbl_prefix_display.config(text="-", fg="#6c7086")

            pct = int(conf * 100)
            if is_low:
                self.lbl_conf.config(text=f"⚠️ {pct}%", fg="#fab387")
                # Bersihkan dan buat tombol alternatif
                for widget in self.alt_container.winfo_children():
                    widget.destroy()

                if alts:
                    lbl_alt_title = tk.Label(
                        self.alt_container,
                        text="Alt:",
                        font=("Segoe UI", 8),
                        fg=THEME["text_primary"],
                        bg="#313244"
                    )
                    lbl_alt_title.pack(side=tk.LEFT, padx=2)

                    for alt_char in alts:
                        btn_alt = tk.Button(
                            self.alt_container,
                            text=alt_char,
                            font=("Segoe UI", 8, "bold"),
                            bg="#f9e2af",
                            fg="#11111b",
                            relief=tk.FLAT,
                            padx=4,
                            pady=0,
                            command=lambda ch=alt_char: self.update_results(ch)
                        )
                        btn_alt.pack(side=tk.LEFT, padx=1)
                    self.warning_frame.pack(fill=tk.X, padx=8, pady=1)
                else:
                    self.warning_frame.pack_forget()
            else:
                self.lbl_conf.config(text="" if pct >= 90 else f"{pct}%", fg="#a6e3a1")
                self.warning_frame.pack_forget()

            # PENTING: MANUAL SEARCH MENG-OVERWRITE OCR!
            # Jika user sedang mengetik di search bar, rekomendasi kata TETAP mengikuti search bar
            if manual_active:
                return
        else:
            self.lbl_prefix_display.config(text=prefix_clean, fg=THEME["primary"])
            self.lbl_conf.config(text="Manual", fg=THEME["primary"])
            self.warning_frame.pack_forget()

        if not prefix_clean:
            return

        cur_mode = self.config.get("game_mode", "santai" if self.mode_santai_var.get() else "default")
        is_santai = (cur_mode == "santai")
        is_brutal = (cur_mode == "brutal")
        # Muat 50 kata rekomendasi terbaik (Prioritas Tier 0 -> Tier 1 (X) -> Tier 2 (Sulit) -> Tier 3)
        results = self.solver.cari_jawaban(
            prefix_clean,
            limit=50,
            mode_santai=is_santai,
            mode_brutal=is_brutal,
            sort_mode=self.config.get("tier0_sort_mode", "default")
        )

        if not results:
            for slot in self.word_card_pool:
                if slot.get("packed", False):
                    slot["frame"].pack_forget()
                    slot["packed"] = False
            msg_not_found = f"Tidak ditemukan kata berawalan '{prefix_clean}' (Mode Santai: tanpa X/Q/F)." if is_santai else f"Tidak ditemukan kata di kamus berawalan '{prefix_clean}'."
            self.lbl_empty_results.config(text=msg_not_found)
            self.lbl_empty_results.pack(fill=tk.X)
            return

        self.lbl_empty_results.pack_forget()

        # Update mini ticker bar untuk tab non-LIVE
        if hasattr(self, "mini_ticker") and self.mini_ticker.winfo_exists():
            top_w = results[0]["kata"] if results else ""
            cur_gm = self.config.get("game_mode", "default")
            m_col = THEME["danger"] if cur_gm == "brutal" else (THEME["santai"] if cur_gm == "santai" else THEME["primary"])
            self.mini_ticker.update_ticker(prefix_clean, top_w, cur_gm, m_col)

        # Tampilkan kata menggunakan widget pool berkinerja tinggi dengan dirty-checking
        prefix_upper = prefix_clean.upper()
        for idx, item in enumerate(results):
            if idx >= len(self.word_card_pool):
                self._alloc_card_slot()
            self._update_card_slot(self.word_card_pool[idx], item, prefix_upper)

        # Sembunyikan slot kartu yang tidak terpakai
        for idx in range(len(results), len(self.word_card_pool)):
            slot = self.word_card_pool[idx]
            if slot.get("packed", False):
                slot["frame"].pack_forget()
                slot["packed"] = False

        # Reset scroll ke posisi teratas setiap kali kata berganti agar user langsung melihat rekomendasi terbaik
        if hasattr(self, "canvas") and self.canvas.winfo_exists():
            self.canvas.yview_moveto(0)

    def _on_mousewheel(self, event):
        """Scroll daftar rekomendasi kata atau tab aktif manapun secara cerdas"""
        if event.delta:
            step = int(-1 * (event.delta / 120))
        elif event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            return

        w_str = str(event.widget)

        # 1. Jendela Toplevel terpisah jika ada
        if hasattr(self, "brutal_canvas") and self.brutal_canvas and self.brutal_canvas.winfo_exists():
            if w_str.startswith(str(self.brutal_canvas)):
                self.brutal_canvas.yview_scroll(step, "units")
                return

        # 2. Tab TAGS (Brutal Preset atau Kelola Tag)
        if hasattr(self, "top_tab_strip") and self.top_tab_strip.active_tab == "tags":
            if hasattr(self, "tab_tags_container") and self.tab_tags_container.winfo_exists():
                active_sub = self.tab_tags_container.sub_strip.active_tab
                if active_sub == "brutal" and hasattr(self.tab_tags_container, "brutal_canvas"):
                    self.tab_tags_container.brutal_canvas.yview_scroll(step, "units")
                    return
                elif active_sub == "custom" and hasattr(self.tab_tags_container, "custom_canvas"):
                    self.tab_tags_container.custom_canvas.yview_scroll(step, "units")
                    return

        # 3. Tab KAMUS (Whitelist, Blocklist, Eksplorer)
        if hasattr(self, "top_tab_strip") and self.top_tab_strip.active_tab == "kamus":
            if hasattr(self, "tab_kamus_container") and self.tab_kamus_container.winfo_exists():
                active_sub = self.tab_kamus_container.sub_strip.active_tab
                if active_sub == "whitelist" and hasattr(self.tab_kamus_container, "wl_canvas"):
                    self.tab_kamus_container.wl_canvas.yview_scroll(step, "units")
                    return
                elif active_sub == "blocklist" and hasattr(self.tab_kamus_container, "bl_canvas"):
                    self.tab_kamus_container.bl_canvas.yview_scroll(step, "units")
                    return
                elif active_sub == "eksplorer" and hasattr(self.tab_kamus_container, "ex_canvas"):
                    self.tab_kamus_container.ex_canvas.yview_scroll(step, "units")
                    return

        # 4. Tab LIVE: Canvas Rekomendasi Kata Utama
        if hasattr(self, "canvas") and self.canvas and self.canvas.winfo_exists():
            self.canvas.yview_scroll(step, "units")

    def _bind_mousewheel(self, event=None):
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        # Jangan unbind jika jendela custom categories atau mode brutal sedang aktif / terbuka
        if hasattr(self, "custom_cats_win") and self.custom_cats_win and self.custom_cats_win.winfo_exists():
            return
        if hasattr(self, "brutal_win") and self.brutal_win and self.brutal_win.winfo_exists():
            return
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def _alloc_card_slot(self):
        card = tk.Frame(self.scrollable_frame, bg=THEME["bg_card"], padx=6, pady=2, relief=tk.FLAT, highlightthickness=1, highlightbackground=THEME["border"])
        
        # Bintang Whitelist di sebelah KIRI kartu
        btn_star = tk.Button(
            card,
            text="☆",
            font=("Segoe UI", 9),
            bg=THEME["bg_card"],
            fg=THEME["text_muted"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["warning"],
            relief=tk.FLAT,
            bd=0,
            padx=3,
            pady=0,
            cursor="hand2"
        )
        btn_star.pack(side=tk.LEFT, padx=(0, 4))

        lbl_kata = tk.Label(card, text="", font=("Segoe UI", 10, "bold"), fg=THEME["text_primary"], bg=THEME["bg_card"])
        lbl_kata.pack(side=tk.LEFT, padx=2)

        # Tombol Silang / Blocklist di sebelah KANAN kartu
        btn_del = tk.Button(
            card,
            text="✕",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["bg_card"],
            fg=THEME["text_muted"],
            activebackground=THEME["danger_bg"],
            activeforeground=THEME["danger"],
            relief=tk.FLAT,
            bd=0,
            padx=4,
            pady=0,
            cursor="hand2"
        )
        btn_del.pack(side=tk.RIGHT, padx=(2, 0))

        # Badge Kategori (Akhiran TI, Jebakan X, dll) di sebelah kiri tombol Blocklist
        lbl_badge = tk.Label(
            card,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg=THEME["text_dark"],
            bg=THEME["primary"],
            padx=6,
            pady=0
        )
        lbl_badge.pack(side=tk.RIGHT, padx=3)

        slot = {
            "frame": card,
            "lbl_kata": lbl_kata,
            "btn_del": btn_del,
            "btn_star": btn_star,
            "lbl_badge": lbl_badge,
            "packed": False,
            "kata": None,
            "bg": None,
            "badge_text": None,
            "badge_bg": None,
            "badge_fg": None,
            "is_wl": None
        }
        self.word_card_pool.append(slot)
        return slot

    def _update_card_slot(self, slot, item, prefix_upper):
        kata = item["kata"]
        tipe = item["tipe"]
        deskripsi = item["deskripsi"]

        kata_upper = kata.upper()
        if prefix_upper and kata_upper.startswith(prefix_upper):
            sisa = kata_upper[len(prefix_upper):]
        else:
            sisa = kata_upper

        if tipe == "CUSTOM_TRAP":
            card_bg = THEME["bg_card"]
            badge_bg = item.get("color", THEME["primary"])
            badge_fg = THEME["text_dark"]
            b_name = item.get("badge_name") or f"Akhiran {item.get('suffix', '').upper()}"
            badge_text = b_name
        elif tipe == "JEBAKAN_X":
            card_bg = THEME["bg_card"]
            badge_bg = THEME["danger"]
            badge_fg = THEME["text_dark"]
            badge_text = "Jebakan X"
        elif tipe == "JEBAKAN_SULIT":
            card_bg = THEME["bg_card"]
            badge_bg = "#fab387"
            badge_fg = THEME["text_dark"]
            clean_desc = deskripsi.replace(" (Sulit)", "").replace("(Sulit)", "").strip()
            badge_text = clean_desc.title()
        else:
            card_bg = THEME["bg_card"]
            badge_bg = THEME["santai"] if deskripsi == "Kata Santai" else THEME["primary"]
            badge_fg = THEME["text_dark"]
            badge_text = "Santai" if deskripsi == "Kata Santai" else "Normal"

        is_wl = item.get("is_whitelisted", False) or self.solver.is_whitelisted(kata)

        card = slot["frame"]
        lbl_kata = slot["lbl_kata"]
        btn_del = slot["btn_del"]
        btn_star = slot.get("btn_star")
        lbl_badge = slot["lbl_badge"]

        # 1. Update background kartu jika berbeda
        if slot.get("bg") != card_bg:
            card.config(bg=card_bg)
            lbl_kata.config(bg=card_bg)
            if btn_del:
                btn_del.config(bg=card_bg)
            if btn_star:
                btn_star.config(bg=card_bg)
            slot["bg"] = card_bg

        # 2. Update teks kata, command blacklist & handler klik jika kata berbeda
        if slot.get("kata") != kata_upper:
            lbl_kata.config(text=kata_upper)
            slot["kata"] = kata_upper
            btn_del.config(command=lambda k=kata: self.on_blacklist_word(k))

            handler = lambda e, s=sisa, w=kata: self.copy_to_clipboard(s, full_word=w)
            card.bind("<Button-1>", handler)
            lbl_kata.bind("<Button-1>", handler)
            lbl_badge.bind("<Button-1>", handler)

        # 3. Update badge teks & warna
        if (slot.get("badge_text") != badge_text or
            slot.get("badge_bg") != badge_bg or
            slot.get("badge_fg") != badge_fg):
            lbl_badge.config(text=badge_text, bg=badge_bg, fg=badge_fg)
            slot["badge_text"] = badge_text
            slot["badge_bg"] = badge_bg
            slot["badge_fg"] = badge_fg

        # 4. Update status whitelist bintang di kiri
        if btn_star and slot.get("is_wl") != is_wl:
            if is_wl:
                btn_star.config(
                    text="★",
                    fg=THEME["warning"],
                    command=lambda k=kata: self.on_toggle_whitelist(k, False)
                )
            else:
                btn_star.config(
                    text="☆",
                    fg=THEME["text_muted"],
                    command=lambda k=kata: self.on_toggle_whitelist(k, True)
                )
            slot["is_wl"] = is_wl

        # 5. Pack hanya jika belum ter-pack
        if not slot.get("packed", False):
            card.pack(fill=tk.X, padx=2, pady=1)
            slot["packed"] = True

    def on_toggle_whitelist(self, kata, enable=True):
        """Memasukkan atau menghapus kata dari whitelist (Terbukti valid & Prioritas Utama)"""
        if enable:
            self.solver.whitelist_word(kata)
            if hasattr(self, "last_detected_word") and self.last_detected_word:
                self.update_results(self.last_detected_word)
            self._wl_refresh_list()
            self._bl_refresh_list()
            self.show_toast(
                f"⭐ '{kata.upper()}' masuk whitelist (Prioritas Utama)",
                undo_callback=lambda: self.on_toggle_whitelist(kata, False)
            )
        else:
            self.solver.unwhitelist_word(kata)
            if hasattr(self, "last_detected_word") and self.last_detected_word:
                self.update_results(self.last_detected_word)
            self._wl_refresh_list()
            self.show_toast(f"Dihapus dari whitelist: '{kata.upper()}'")

    def on_blacklist_word(self, kata):
        """Memasukkan kata ke blacklist dan merefresh rekomendasi"""
        self.solver.blacklist_word(kata)
        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)
        self._bl_refresh_list()
        self.show_toast(
            f"🚫 '{kata.upper()}' masuk blacklist",
            undo_callback=lambda k=kata: self.on_undo_blacklist(k)
        )

    def on_undo_blacklist(self, kata):
        """Membatalkan blacklist kata (Undo)"""
        self.solver.unblacklist_word(kata)
        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)
        self._bl_refresh_list()
        self.show_toast(f"✅ '{kata.upper()}' dipulihkan ke kamus")

    def open_blacklist_window(self):
        """Membuka dialog popup untuk memeriksa dan mengelola daftar kata di blocklist"""
        if hasattr(self, "blacklist_win") and self.blacklist_win and self.blacklist_win.winfo_exists():
            self.blacklist_win.lift()
            self.blacklist_win.focus_force()
            if hasattr(self, "entry_bl_add") and self.entry_bl_add.winfo_exists():
                self.entry_bl_add.focus_set()
                self.entry_bl_add.select_range(0, tk.END)
            return

        self.blacklist_win, _ = self._create_clean_toplevel(
            "🚫 Kelola Blocklist Kata", 400, 520, min_w=360, min_h=440
        )

        sub_hdr = tk.Frame(self.blacklist_win, bg="#181825", padx=12, pady=6)
        sub_hdr.pack(fill=tk.X)
        tk.Label(
            sub_hdr,
            text="Kata ditolak Roblox & tidak disarankan bot",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg="#181825"
        ).pack(side=tk.LEFT)

        self.lbl_bl_count = tk.Label(
            sub_hdr,
            text="0 kata",
            font=("Segoe UI", 8, "bold"),
            fg="#f38ba8",
            bg="#181825"
        )
        self.lbl_bl_count.pack(side=tk.RIGHT)

        # Bar Tambah Kata Baru
        add_frame = tk.Frame(self.blacklist_win, bg="#1e1e2e", padx=12, pady=4)
        add_frame.pack(fill=tk.X)

        lbl_tambah = tk.Label(
            add_frame,
            text="Tambah Kata:",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_primary"],
            bg="#1e1e2e"
        )
        lbl_tambah.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_bl_add = tk.Entry(
            add_frame,
            font=("Segoe UI", 9),
            bg="#313244",
            fg=THEME["text_primary"],
            insertbackground="#cdd6f4",
            relief=tk.FLAT
        )
        self.entry_bl_add.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        btn_add = tk.Button(
            add_frame,
            text="➕ Blokir",
            font=("Segoe UI", 9, "bold"),
            bg="#f38ba8",
            fg="#11111b",
            activebackground=THEME["danger_bg"],
            relief=tk.FLAT,
            padx=8,
            pady=2,
            command=self._bl_add_word
        )
        btn_add.pack(side=tk.RIGHT)
        self.entry_bl_add.bind("<Return>", lambda e: self._bl_add_word())

        # Search / Filter Bar
        search_frame = tk.Frame(self.blacklist_win, bg="#1e1e2e", padx=12, pady=4)
        search_frame.pack(fill=tk.X)

        lbl_filter = tk.Label(
            search_frame,
            text="🔍 Filter:",
            font=("Segoe UI", 9),
            fg=THEME["text_secondary"],
            bg="#1e1e2e"
        )
        lbl_filter.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_bl_filter = tk.Entry(
            search_frame,
            font=("Segoe UI", 9),
            bg="#313244",
            fg=THEME["text_primary"],
            insertbackground="#cdd6f4",
            relief=tk.FLAT
        )
        self.entry_bl_filter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_bl_filter.bind("<KeyRelease>", lambda e: self._bl_refresh_list())

        # Listbox Frame dengan Scrollbar
        list_frame = tk.Frame(self.blacklist_win, bg="#1e1e2e", padx=12, pady=4)
        list_frame.pack(fill=tk.BOTH, expand=True)

        bl_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.bl_listbox = tk.Listbox(
            list_frame,
            font=("Segoe UI", 10),
            bg="#181825",
            fg=THEME["text_primary"],
            selectbackground="#f38ba8",
            selectforeground="#11111b",
            activestyle="none",
            relief=tk.FLAT,
            highlightthickness=0,
            yscrollcommand=bl_scroll.set,
            selectmode=tk.EXTENDED
        )
        bl_scroll.config(command=self.bl_listbox.yview)

        self.bl_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        bl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.bl_listbox.bind("<Double-Button-1>", lambda e: self._bl_remove_selected())

        # Bottom Action Bar
        act_frame = tk.Frame(self.blacklist_win, bg="#181825", padx=12, pady=8)
        act_frame.pack(fill=tk.X, side=tk.BOTTOM)

        btn_remove = tk.Button(
            act_frame,
            text="🗑️ Hapus dari Blocklist",
            font=("Segoe UI", 9, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground=THEME["accent_neon"],
            relief=tk.FLAT,
            padx=10,
            pady=3,
            command=self._bl_remove_selected
        )
        btn_remove.pack(side=tk.LEFT, padx=2)

        btn_open_file = tk.Button(
            act_frame,
            text="📂 Buka File (.txt)",
            font=("Segoe UI", 9),
            bg="#89b4fa",
            fg="#11111b",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            command=self._bl_open_txt
        )
        btn_open_file.pack(side=tk.LEFT, padx=4)

        btn_reload = tk.Button(
            act_frame,
            text="🔄 Muat Ulang",
            font=("Segoe UI", 9),
            bg="#313244",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            command=self._bl_reload
        )
        btn_reload.pack(side=tk.RIGHT, padx=2)

        self._bl_refresh_list()

        # Pre-fill jika di manual entry ada kata yang diketik
        if hasattr(self, "entry_manual"):
            manual_text = self.entry_manual.get().strip().upper()
            if manual_text:
                self.entry_bl_add.insert(0, manual_text)

        # Langsung fokus ke input teks tambah kata
        self.entry_bl_add.focus_set()
        self.entry_bl_add.select_range(0, tk.END)

    def _bl_refresh_list(self):
        """Memperbarui isi Listbox di jendela Blocklist"""
        if not hasattr(self, "bl_listbox") or not self.bl_listbox.winfo_exists():
            return
        
        filter_query = self.entry_bl_filter.get().strip().lower() if hasattr(self, "entry_bl_filter") else ""
        all_words = self.solver.get_blacklisted_words()
        
        self.bl_listbox.delete(0, tk.END)
        count = 0
        for w in all_words:
            if not filter_query or filter_query in w:
                self.bl_listbox.insert(tk.END, w.upper())
                count += 1
                
        total = len(all_words)
        if hasattr(self, "lbl_bl_count"):
            if filter_query:
                self.lbl_bl_count.config(text=f"{count}/{total} kata")
            else:
                self.lbl_bl_count.config(text=f"{total} kata")

    def _bl_add_word(self):
        """Menambahkan kata baru ke blocklist via dialog dan langsung menutup popup"""
        if not hasattr(self, "entry_bl_add"):
            return
        raw = self.entry_bl_add.get().strip().lower()
        word = "".join([c for c in raw if c.isalpha()])
        if not word:
            return
        
        self.solver.blacklist_word(word)
        self.entry_bl_add.delete(0, tk.END)
        self._bl_refresh_list()
        
        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast(f"🚫 '{word.upper()}' ditambahkan ke blocklist")

        # Tutup popup seketika setelah menambahkan kata
        if hasattr(self, "blacklist_win") and self.blacklist_win and self.blacklist_win.winfo_exists():
            self.blacklist_win.destroy()

    def _bl_remove_selected(self):
        """Menghapus kata-kata yang dipilih dari blocklist"""
        if not hasattr(self, "bl_listbox"):
            return
        selected_indices = self.bl_listbox.curselection()
        if not selected_indices:
            self.show_toast("Pilih kata yang ingin dihapus terlebih dahulu")
            return
            
        selected_words = [self.bl_listbox.get(i).lower() for i in selected_indices]
        for w in selected_words:
            self.solver.unblacklist_word(w)
            
        self._bl_refresh_list()
        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)
            
        removed_str = ", ".join([w.upper() for w in selected_words])
        self.show_toast(f"✅ Dipulihkan ke kamus: {removed_str}")

    def _bl_open_txt(self):
        """Membuka file blacklist.txt dengan text editor default sistem"""
        bl_path = os.path.abspath(self.solver.blacklist_path)
        try:
            os.startfile(bl_path)
        except Exception as e:
            self.show_toast(f"Gagal membuka file: {e}")

    def _bl_reload(self):
        """Memuat ulang blacklist dari file disk"""
        self.solver.load_blacklist()
        self._bl_refresh_list()
        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast("🔄 Blocklist dimuat ulang dari disk")

    def open_whitelist_window(self):
        """Membuka dialog popup untuk memeriksa dan mengelola daftar kata di whitelist (Terverifikasi & Prioritas)"""
        if hasattr(self, "whitelist_win") and self.whitelist_win and self.whitelist_win.winfo_exists():
            self.whitelist_win.lift()
            self.whitelist_win.focus_force()
            if hasattr(self, "entry_wl_add") and self.entry_wl_add.winfo_exists():
                self.entry_wl_add.focus_set()
                self.entry_wl_add.select_range(0, tk.END)
            return

        self.whitelist_win, _ = self._create_clean_toplevel(
            "⭐ Kelola Whitelist Kata", 400, 520, min_w=360, min_h=440
        )

        sub_hdr = tk.Frame(self.whitelist_win, bg="#181825", padx=12, pady=6)
        sub_hdr.pack(fill=tk.X)
        tk.Label(
            sub_hdr,
            text="Kata terbukti 100% valid & prioritas teratas",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg="#181825"
        ).pack(side=tk.LEFT)

        self.lbl_wl_count = tk.Label(
            sub_hdr,
            text="0 kata",
            font=("Segoe UI", 8, "bold"),
            fg="#f9e2af",
            bg="#181825"
        )
        self.lbl_wl_count.pack(side=tk.RIGHT)

        # Bar Tambah Kata Baru
        add_frame = tk.Frame(self.whitelist_win, bg="#1e1e2e", padx=12, pady=4)
        add_frame.pack(fill=tk.X)

        lbl_tambah = tk.Label(
            add_frame,
            text="Tambah Kata:",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_primary"],
            bg="#1e1e2e"
        )
        lbl_tambah.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_wl_add = tk.Entry(
            add_frame,
            font=("Segoe UI", 9),
            bg="#313244",
            fg=THEME["text_primary"],
            insertbackground="#cdd6f4",
            relief=tk.FLAT
        )
        self.entry_wl_add.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        btn_add = tk.Button(
            add_frame,
            text="➕ Whitelist",
            font=("Segoe UI", 9, "bold"),
            bg="#f9e2af",
            fg="#11111b",
            activebackground="#f5e0dc",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            command=self._wl_add_word
        )
        btn_add.pack(side=tk.RIGHT)
        self.entry_wl_add.bind("<Return>", lambda e: self._wl_add_word())

        # Search / Filter Bar
        search_frame = tk.Frame(self.whitelist_win, bg="#1e1e2e", padx=12, pady=4)
        search_frame.pack(fill=tk.X)

        lbl_filter = tk.Label(
            search_frame,
            text="🔍 Filter:",
            font=("Segoe UI", 9),
            fg=THEME["text_secondary"],
            bg="#1e1e2e"
        )
        lbl_filter.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_wl_filter = tk.Entry(
            search_frame,
            font=("Segoe UI", 9),
            bg="#313244",
            fg=THEME["text_primary"],
            insertbackground="#cdd6f4",
            relief=tk.FLAT
        )
        self.entry_wl_filter.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_wl_filter.bind("<KeyRelease>", lambda e: self._wl_refresh_list())

        # Listbox Frame dengan Scrollbar
        list_frame = tk.Frame(self.whitelist_win, bg="#1e1e2e", padx=12, pady=4)
        list_frame.pack(fill=tk.BOTH, expand=True)

        wl_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.wl_listbox = tk.Listbox(
            list_frame,
            font=("Segoe UI", 10),
            bg="#181825",
            fg=THEME["text_primary"],
            selectbackground="#f9e2af",
            selectforeground="#11111b",
            activestyle="none",
            relief=tk.FLAT,
            highlightthickness=0,
            yscrollcommand=wl_scroll.set,
            selectmode=tk.EXTENDED
        )
        wl_scroll.config(command=self.wl_listbox.yview)

        self.wl_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        wl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.wl_listbox.bind("<Double-Button-1>", lambda e: self._wl_remove_selected())

        # Bottom Action Bar
        act_frame = tk.Frame(self.whitelist_win, bg="#181825", padx=12, pady=8)
        act_frame.pack(fill=tk.X, side=tk.BOTTOM)

        btn_remove = tk.Button(
            act_frame,
            text="🗑️ Hapus dari Whitelist",
            font=("Segoe UI", 9, "bold"),
            bg="#f38ba8",
            fg="#11111b",
            activebackground=THEME["danger_bg"],
            relief=tk.FLAT,
            padx=10,
            pady=3,
            command=self._wl_remove_selected
        )
        btn_remove.pack(side=tk.LEFT, padx=2)

        btn_open_file = tk.Button(
            act_frame,
            text="📂 Buka File (.txt)",
            font=("Segoe UI", 9),
            bg="#89b4fa",
            fg="#11111b",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            command=self._wl_open_txt
        )
        btn_open_file.pack(side=tk.LEFT, padx=4)

        btn_reload = tk.Button(
            act_frame,
            text="🔄 Muat Ulang",
            font=("Segoe UI", 9),
            bg="#313244",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            command=self._wl_reload
        )
        btn_reload.pack(side=tk.RIGHT, padx=2)

        self._wl_refresh_list()

        # Pre-fill jika di manual entry ada kata yang diketik
        if hasattr(self, "entry_manual"):
            manual_text = self.entry_manual.get().strip().upper()
            if manual_text:
                self.entry_wl_add.insert(0, manual_text)

        # Langsung fokus ke input teks tambah kata
        self.entry_wl_add.focus_set()
        self.entry_wl_add.select_range(0, tk.END)

    def _wl_refresh_list(self):
        """Memperbarui isi Listbox di jendela Whitelist"""
        if not hasattr(self, "wl_listbox") or not self.wl_listbox.winfo_exists():
            return

        filter_query = self.entry_wl_filter.get().strip().lower() if hasattr(self, "entry_wl_filter") else ""
        all_words = self.solver.get_whitelisted_words()

        self.wl_listbox.delete(0, tk.END)
        count = 0
        for w in all_words:
            if not filter_query or filter_query in w:
                self.wl_listbox.insert(tk.END, w.upper())
                count += 1

        total = len(all_words)
        if hasattr(self, "lbl_wl_count"):
            if filter_query:
                self.lbl_wl_count.config(text=f"{count}/{total} kata")
            else:
                self.lbl_wl_count.config(text=f"{total} kata")

    def _wl_add_word(self):
        """Menambahkan kata baru ke whitelist via dialog dan langsung menutup popup"""
        if not hasattr(self, "entry_wl_add"):
            return
        raw = self.entry_wl_add.get().strip().lower()
        word = "".join([c for c in raw if c.isalpha()])
        if not word or len(word) < 2:
            self.show_toast("⚠️ Kata minimal 2 huruf alfabet")
            return

        self.solver.whitelist_word(word)
        self.entry_wl_add.delete(0, tk.END)
        self._wl_refresh_list()

        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast(f"⭐ '{word.upper()}' masuk whitelist (Prioritas)")

        if hasattr(self, "whitelist_win") and self.whitelist_win and self.whitelist_win.winfo_exists():
            self.whitelist_win.destroy()

    def _wl_remove_selected(self):
        """Menghapus kata-kata yang dipilih dari whitelist"""
        if not hasattr(self, "wl_listbox"):
            return
        selected_indices = self.wl_listbox.curselection()
        if not selected_indices:
            self.show_toast("Pilih kata yang ingin dihapus terlebih dahulu")
            return

        selected_words = [self.wl_listbox.get(i).lower() for i in selected_indices]
        for w in selected_words:
            self.solver.unwhitelist_word(w)

        self._wl_refresh_list()
        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)

        removed_str = ", ".join([w.upper() for w in selected_words])
        self.show_toast(f"Dihapus dari whitelist: {removed_str}")

    def _wl_open_txt(self):
        """Membuka file whitelist.txt dengan text editor default sistem"""
        wl_path = os.path.abspath(self.solver.whitelist_path)
        try:
            os.startfile(wl_path)
        except Exception as e:
            self.show_toast(f"Gagal membuka file: {e}")

    def _wl_reload(self):
        """Memuat ulang whitelist dari file disk"""
        self.solver.load_whitelist()
        self._wl_refresh_list()
        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast("🔄 Whitelist dimuat ulang dari disk")

    def _set_tier0_sort_mode(self, mode):
        """Mengatur mode sortir rekomendasi kata untuk Tier 0 (Custom Traps)"""
        if mode not in ("default", "tag_order"):
            return
        self.config["tier0_sort_mode"] = mode
        save_config(self.config)
        self.solver.set_tier0_sort_mode(mode)
        if hasattr(self, "var_tier0_mode") and self.var_tier0_mode:
            self.var_tier0_mode.set(mode)
        self._update_sort_mode_button()
        manual_text = "".join([c for c in self.search_var.get().strip().upper() if c.isalpha()]) if hasattr(self, "search_var") else ""
        if manual_text:
            self.update_results(manual_text)
        elif hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)
        if mode == "default":
            self.show_toast("📊 Mode Tier 0: Default (Panjang 4-7 & Abjad A-Z)")
        else:
            self.show_toast("🏷️ Mode Tier 0: Sesuai Urutan Tag Kustom")

    def open_custom_categories_window(self):
        """Membuka dialog popup untuk mengelola kategori & akhiran kustom (Custom Traps)"""
        if hasattr(self, "custom_cats_win") and self.custom_cats_win and self.custom_cats_win.winfo_exists():
            self.custom_cats_win.lift()
            self.custom_cats_win.focus_force()
            if hasattr(self, "entry_cat_sfx") and self.entry_cat_sfx.winfo_exists():
                self.entry_cat_sfx.focus_set()
                self.entry_cat_sfx.select_range(0, tk.END)
            return

        def _on_custom_cats_close():
            self.custom_cats_canvas = None
            if hasattr(self, "custom_cats_win") and self.custom_cats_win and self.custom_cats_win.winfo_exists():
                self.custom_cats_win.destroy()
            self._unbind_mousewheel()

        self.custom_cats_win, _ = self._create_clean_toplevel(
            "🏷️ Kategori & Akhiran Kustom", 500, 660, min_w=460, min_h=520, on_close=_on_custom_cats_close
        )

        sub_hdr = tk.Frame(self.custom_cats_win, bg="#181825", padx=14, pady=6)
        sub_hdr.pack(fill=tk.X)
        tk.Label(
            sub_hdr,
            text="Kata berakhiran ini diprioritaskan super jebakan (di atas X)",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg="#181825"
        ).pack(side=tk.LEFT)

        btn_brutal_cfg = tk.Button(
            sub_hdr,
            text="🔥 Mode Brutal...",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#fab387",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.open_brutal_settings_window
        )
        btn_brutal_cfg.pack(side=tk.RIGHT)

        # Mode Sortir Tier 0 Control Frame
        sort_box = tk.LabelFrame(
            self.custom_cats_win,
            text=" 📊 Mode Urutan Rekomendasi Kata (Tier 0) ",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["primary"],
            bg="#181825",
            padx=10,
            pady=6
        )
        sort_box.pack(fill=tk.X, padx=14, pady=(2, 6))

        self.var_tier0_mode = tk.StringVar(value=self.config.get("tier0_sort_mode", "default"))

        rb_def = tk.Radiobutton(
            sort_box,
            text="Default (Panjang 4-7 & Abjad A-Z)",
            variable=self.var_tier0_mode,
            value="default",
            font=("Segoe UI", 9),
            fg=THEME["text_primary"],
            bg="#181825",
            activebackground="#181825",
            activeforeground="#f5e0dc",
            selectcolor="#313244",
            command=lambda: self._set_tier0_sort_mode("default")
        )
        rb_def.pack(anchor="w", pady=1)

        rb_tag = tk.Radiobutton(
            sort_box,
            text="Sesuai Urutan Tag Kustom",
            variable=self.var_tier0_mode,
            value="tag_order",
            font=("Segoe UI", 9),
            fg=THEME["text_primary"],
            bg="#181825",
            activebackground="#181825",
            activeforeground="#f5e0dc",
            selectcolor="#313244",
            command=lambda: self._set_tier0_sort_mode("tag_order")
        )
        rb_tag.pack(anchor="w", pady=1)

        # Form Tambah Akhiran Baru
        add_box = tk.LabelFrame(
            self.custom_cats_win,
            text=" Tambah Akhiran / Kategori Baru ",
            font=("Segoe UI", 9, "bold"),
            fg="#cba6f7",
            bg="#181825",
            padx=10,
            pady=8
        )
        add_box.pack(fill=tk.X, padx=14, pady=(0, 6))

        row1 = tk.Frame(add_box, bg="#181825")
        row1.pack(fill=tk.X, pady=2)

        lbl_sfx = tk.Label(row1, text="Akhiran:", font=("Segoe UI", 9, "bold"), fg=THEME["text_primary"], bg="#181825", width=8, anchor="w")
        lbl_sfx.pack(side=tk.LEFT)

        self.entry_cat_sfx = tk.Entry(row1, font=("Segoe UI", 10, "bold"), bg="#313244", fg=THEME["text_primary"], insertbackground="white", width=9)
        self.entry_cat_sfx.pack(side=tk.LEFT, padx=4)
        self.entry_cat_sfx.focus_set()
        self.entry_cat_sfx.bind("<Return>", lambda e: self._on_add_custom_category())

        lbl_name = tk.Label(row1, text="Nama:", font=("Segoe UI", 9), fg=THEME["text_primary"], bg="#181825", width=6, anchor="w")
        lbl_name.pack(side=tk.LEFT, padx=(6, 0))

        self.entry_cat_name = tk.Entry(row1, font=("Segoe UI", 9), bg="#313244", fg=THEME["text_primary"], insertbackground="white")
        self.entry_cat_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_cat_name.bind("<Return>", lambda e: self._on_add_custom_category())

        btn_add = tk.Button(
            add_box,
            text="➕ Tambah Kategori Akhiran",
            font=("Segoe UI", 9, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground=THEME["accent_neon"],
            relief=tk.FLAT,
            command=self._on_add_custom_category,
            pady=3
        )
        btn_add.pack(fill=tk.X, pady=(6, 2))

        # List Area Toolbar (Header + Quick Sort)
        list_toolbar = tk.Frame(self.custom_cats_win, bg="#1e1e2e", padx=14)
        list_toolbar.pack(fill=tk.X, pady=(4, 2))

        self.lbl_cat_list_title = tk.Label(
            list_toolbar,
            text="Daftar Kategori Akhiran:",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_primary"],
            bg="#1e1e2e",
            anchor="w"
        )
        self.lbl_cat_list_title.pack(side=tk.LEFT)

        btn_sort_len_asc = tk.Button(
            list_toolbar,
            text="📏 Tersedikit",
            font=("Segoe UI", 8),
            bg="#313244",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=lambda: self._on_sort_custom_categories_length(reverse=False)
        )
        btn_sort_len_asc.pack(side=tk.RIGHT, padx=(2, 0))

        btn_sort_len_desc = tk.Button(
            list_toolbar,
            text="📏 Terpanjang",
            font=("Segoe UI", 8),
            bg="#313244",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=lambda: self._on_sort_custom_categories_length(reverse=True)
        )
        btn_sort_len_desc.pack(side=tk.RIGHT, padx=2)

        btn_sort_cnt = tk.Button(
            list_toolbar,
            text="📊 Terbanyak",
            font=("Segoe UI", 8),
            bg="#313244",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=self._on_sort_custom_categories_count
        )
        btn_sort_cnt.pack(side=tk.RIGHT, padx=2)

        btn_sort_az = tk.Button(
            list_toolbar,
            text="🔤 A-Z",
            font=("Segoe UI", 8),
            bg="#313244",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=5,
            pady=1,
            cursor="hand2",
            command=self._on_sort_custom_categories_az
        )
        btn_sort_az.pack(side=tk.RIGHT, padx=2)

        lbl_sort_txt = tk.Label(
            list_toolbar,
            text="Urutkan:",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#1e1e2e"
        )
        lbl_sort_txt.pack(side=tk.RIGHT, padx=(0, 2))

        # Scrollable list container
        list_container = tk.Frame(self.custom_cats_win, bg="#181825")
        list_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        canvas = tk.Canvas(list_container, bg="#181825", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        self.custom_cats_canvas = canvas
        self.custom_cats_inner = tk.Frame(canvas, bg="#181825")

        canvas_win_id = canvas.create_window((0, 0), window=self.custom_cats_inner, anchor="nw", width=450)
        canvas.configure(yscrollcommand=scrollbar.set)

        self.custom_cats_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win_id, width=e.width))

        # Mousewheel binding langsung untuk jendela Kategori Kustom
        self._bind_mousewheel()
        self.custom_cats_win.bind("<Enter>", lambda e: self._bind_mousewheel())
        list_container.bind("<Enter>", lambda e: self._bind_mousewheel())
        canvas.bind("<Enter>", lambda e: self._bind_mousewheel())
        self.custom_cats_inner.bind("<Enter>", lambda e: self._bind_mousewheel())

        # Cleanup handler configured in _create_clean_toplevel

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Render item list
        self._render_custom_category_items()

        # Footer padding
        pad_bottom = tk.Frame(self.custom_cats_win, bg="#1e1e2e", height=8)
        pad_bottom.pack(fill=tk.X)

    def open_brutal_settings_window(self):
        """Membuka dialog popup pengaturan Mode Brutal untuk memilih tag kustom yang otomatis aktif"""
        if hasattr(self, "brutal_win") and self.brutal_win and self.brutal_win.winfo_exists():
            self.brutal_win.lift()
            self.brutal_win.focus_force()
            return

        selected_brutal_tags = set(self.config.get("brutal_mode_tags", ["AMSI", "KSO", "RHU", "TL", "BD"]))
        initial_brutal_tags = set(selected_brutal_tags)

        def _save_and_apply(show_toast_msg=True):
            self.config["brutal_mode_tags"] = list(selected_brutal_tags)
            save_config(self.config)

            if self.config.get("game_mode") == "brutal":
                categories = self.config.get("custom_trap_endings", [])
                for cat in categories:
                    sfx = cat.get("suffix", "").upper()
                    cat["enabled"] = (sfx in selected_brutal_tags)
                self.config["custom_trap_endings"] = categories
                save_config(self.config)
                self.solver.set_custom_endings(categories)
                self._render_custom_category_items()
                self._render_custom_category_quick_bar()
                if hasattr(self, "last_detected_word") and self.last_detected_word:
                    self.update_results(self.last_detected_word)

            if show_toast_msg:
                self.show_toast(f"✅ Pengaturan Mode Brutal disimpan ({len(selected_brutal_tags)} tag aktif)!")

        def _on_brutal_close():
            # Otomatis simpan jika ada perubahan tag saat user menutup jendela langsung (agar tidak hilang)
            if selected_brutal_tags != initial_brutal_tags:
                _save_and_apply(show_toast_msg=True)
            self.brutal_canvas = None
            self.brutal_inner = None
            if hasattr(self, "brutal_win") and self.brutal_win and self.brutal_win.winfo_exists():
                self.brutal_win.destroy()
            self._unbind_mousewheel()

        # Window lebih besar dan lega (580x720) dengan batas minimum 500x520
        self.brutal_win, _ = self._create_clean_toplevel(
            "🔥 Pengaturan Mode Brutal", 580, 720, min_w=500, min_h=520, on_close=_on_brutal_close
        )
        self.brutal_win.bind("<Destroy>", lambda e: (setattr(self, "brutal_canvas", None), setattr(self, "brutal_inner", None)) if e.widget == self.brutal_win else None, add="+")

        # 1. Pinned Bottom Action Bar (Dipack terlebih dahulu dengan side=tk.BOTTOM agar SELALU tampak di dasar window)
        bottom_bar = tk.Frame(self.brutal_win, bg="#1e1e2e", padx=16, pady=10)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        def _on_save_button_click():
            _save_and_apply(show_toast_msg=True)
            initial_brutal_tags.clear()
            initial_brutal_tags.update(selected_brutal_tags)
            _on_brutal_close()

        btn_save = tk.Button(
            bottom_bar,
            text="💾 Simpan & Terapkan",
            font=("Segoe UI", 9, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground=THEME["accent_neon"],
            relief=tk.FLAT,
            padx=16,
            pady=5,
            cursor="hand2",
            command=_on_save_button_click
        )
        btn_save.pack(side=tk.RIGHT, padx=(8, 0))

        btn_cancel = tk.Button(
            bottom_bar,
            text="Tutup",
            font=("Segoe UI", 9),
            bg="#313244",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=14,
            pady=5,
            cursor="hand2",
            command=_on_brutal_close
        )
        btn_cancel.pack(side=tk.RIGHT)

        # 2. Header & Toolbar (Dipack di bagian atas)
        sub_hdr = tk.Frame(self.brutal_win, bg="#181825", padx=14, pady=8)
        sub_hdr.pack(fill=tk.X, side=tk.TOP)
        tk.Label(
            sub_hdr,
            text="Pilih tag akhiran kustom yang otomatis dinyalakan saat Mode BRUTAL aktif.\nTag ini akan diprioritaskan di baris teratas rekomendasi (Tier 0).",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg="#181825",
            justify=tk.LEFT
        ).pack(anchor="w")

        # Status & Toggle Mode Saat Ini
        status_frame = tk.Frame(self.brutal_win, bg="#1e1e2e", padx=14, pady=6)
        status_frame.pack(fill=tk.X, side=tk.TOP, pady=(0, 4))

        cur_gm = self.config.get("game_mode", "default")
        if cur_gm == "normal":
            cur_gm = "default"
        lbl_status_txt = "🔥 Mode Brutal Saat Ini: AKTIF" if cur_gm == "brutal" else f"⚪ Mode Saat Ini: {cur_gm.upper()}"
        lbl_status_col = "#f38ba8" if cur_gm == "brutal" else "#89dceb"

        lbl_mode_cur = tk.Label(
            status_frame,
            text=lbl_status_txt,
            font=("Segoe UI", 9, "bold"),
            fg=lbl_status_col,
            bg="#1e1e2e"
        )
        lbl_mode_cur.pack(side=tk.LEFT)

        btn_toggle_mode = tk.Button(
            status_frame,
            text="Matikan Mode Brutal" if cur_gm == "brutal" else "🔥 Aktifkan Mode Brutal Sekarang",
            font=("Segoe UI", 8, "bold"),
            bg="#313244" if cur_gm == "brutal" else "#f38ba8",
            fg=THEME["text_primary"] if cur_gm == "brutal" else "#11111b",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2"
        )
        btn_toggle_mode.pack(side=tk.RIGHT)

        # Form Tambah Suffix Baru ke Brutal
        add_frame = tk.LabelFrame(
            self.brutal_win,
            text=" Tambah Akhiran Baru ke Daftar Brutal ",
            font=("Segoe UI", 9, "bold"),
            fg="#fab387",
            bg="#181825",
            padx=10,
            pady=6
        )
        add_frame.pack(fill=tk.X, side=tk.TOP, padx=14, pady=(2, 6))

        row_add = tk.Frame(add_frame, bg="#181825")
        row_add.pack(fill=tk.X, pady=2)

        tk.Label(row_add, text="Akhiran:", font=("Segoe UI", 9, "bold"), fg=THEME["text_primary"], bg="#181825").pack(side=tk.LEFT, padx=(0, 4))
        entry_sfx = tk.Entry(row_add, font=("Segoe UI", 10, "bold"), bg="#313244", fg=THEME["text_primary"], insertbackground="white", width=9)
        entry_sfx.pack(side=tk.LEFT, padx=(0, 8))
        entry_sfx.focus_set()

        # Toolbar Aksi Cepat (Pilih Semua, Default, Hapus Semua)
        tb = tk.Frame(self.brutal_win, bg="#1e1e2e", padx=14, pady=4)
        tb.pack(fill=tk.X, side=tk.TOP)

        lbl_tb_title = tk.Label(
            tb,
            text="Daftar Tag Brutal:",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_primary"],
            bg="#1e1e2e"
        )
        lbl_tb_title.pack(side=tk.LEFT)

        # 3. List Area Container with Canvas (Memenuhi sisa seluruh ruang window secara dinamis)
        list_container = tk.Frame(self.brutal_win, bg="#181825")
        list_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=(4, 6))

        canvas = tk.Canvas(list_container, bg="#181825", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg="#181825")

        self.brutal_canvas = canvas
        self.brutal_inner = inner

        canvas_win_id = canvas.create_window((0, 0), window=inner, anchor="nw", width=520)
        canvas.configure(yscrollcommand=scrollbar.set)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win_id, width=e.width))

        # Mousewheel scroll handler khusus untuk jendela Brutal
        def _scroll_brutal(e):
            if getattr(e, "delta", 0):
                step = int(-1 * (e.delta / 120))
            elif getattr(e, "num", None) == 4:
                step = -1
            elif getattr(e, "num", None) == 5:
                step = 1
            else:
                return
            canvas.yview_scroll(step, "units")

        def _bind_scroll_recursive(w):
            w.bind("<MouseWheel>", _scroll_brutal, add="+")
            w.bind("<Button-4>", _scroll_brutal, add="+")
            w.bind("<Button-5>", _scroll_brutal, add="+")

        # Global mousewheel binding
        self._bind_mousewheel()
        _bind_scroll_recursive(self.brutal_win)
        _bind_scroll_recursive(list_container)
        _bind_scroll_recursive(canvas)
        _bind_scroll_recursive(inner)
        _bind_scroll_recursive(sub_hdr)
        _bind_scroll_recursive(status_frame)
        _bind_scroll_recursive(add_frame)
        _bind_scroll_recursive(tb)
        _bind_scroll_recursive(bottom_bar)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _create_row_item(cat, idx, cats):
            sfx = cat.get("suffix", "").upper()
            name = cat.get("name") or f"Akhiran {sfx}"
            col = cat.get("color", "#cba6f7")
            is_checked = (sfx in selected_brutal_tags)
            cnt = self.solver.count_words_by_suffix(sfx) if hasattr(self.solver, "count_words_by_suffix") else 0

            # Container baris dengan kontras tinggi (merah marun jika aktif, gelap jika tidak)
            row_bg = "#381d28" if is_checked else "#1e1e2e"
            row_border = "#f38ba8" if is_checked else "#313244"
            row = tk.Frame(
                inner,
                bg=row_bg,
                highlightbackground=row_border,
                highlightcolor=row_border,
                highlightthickness=1,
                padx=8,
                pady=5,
                cursor="hand2"
            )
            row.pack(fill=tk.X, padx=4, pady=2)

            var = tk.BooleanVar(value=is_checked)

            # Checkbox dengan warna seleksi kontras
            cb = tk.Checkbutton(
                row,
                variable=var,
                bg=row_bg,
                activebackground=row_bg,
                selectcolor="#f38ba8" if is_checked else "#313244",
                cursor="hand2"
            )
            cb.pack(side=tk.LEFT, padx=(0, 4))

            # Badge Suffix
            badge = tk.Label(
                row,
                text=sfx,
                font=("Segoe UI", 9, "bold"),
                bg=col,
                fg="#11111b",
                padx=6,
                pady=1,
                cursor="hand2"
            )
            badge.pack(side=tk.LEFT, padx=(0, 6))

            # Info Frame (Nama dan Jumlah Kata)
            info_frame = tk.Frame(row, bg=row_bg, cursor="hand2")
            info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            lbl_name = tk.Label(
                info_frame,
                text=name,
                font=("Segoe UI", 9, "bold" if is_checked else "normal"),
                fg=THEME["text_primary"] if is_checked else "#6c7086",
                bg=row_bg,
                anchor="w",
                cursor="hand2"
            )
            lbl_name.pack(anchor="w")

            lbl_cnt = tk.Label(
                info_frame,
                text=f"{cnt} kata di kamus",
                font=("Segoe UI", 8),
                fg="#fab387" if is_checked else "#585b70",
                bg=row_bg,
                anchor="w",
                cursor="hand2"
            )
            lbl_cnt.pack(anchor="w")

            # Pill badge status kanan: Kontras tinggi (Pill merah mencolok saat BRUTAL vs Pill abu-abu saat NONAKTIF)
            lbl_flag = tk.Label(
                row,
                text=" 🔥 BRUTAL " if is_checked else " ⚪ NONAKTIF ",
                font=("Segoe UI", 8, "bold"),
                bg="#f38ba8" if is_checked else "#313244",
                fg="#11111b" if is_checked else "#6c7086",
                padx=8,
                pady=3,
                cursor="hand2"
            )
            lbl_flag.pack(side=tk.RIGHT, padx=4)

            def _apply_row_visual(active):
                if active:
                    r_bg = "#381d28"
                    row.configure(bg=r_bg, highlightbackground="#f38ba8", highlightcolor="#f38ba8")
                    cb.configure(bg=r_bg, activebackground=r_bg, selectcolor="#f38ba8")
                    info_frame.configure(bg=r_bg)
                    lbl_name.configure(bg=r_bg, fg=THEME["text_primary"], font=("Segoe UI", 9, "bold"))
                    lbl_cnt.configure(bg=r_bg, fg="#fab387")
                    lbl_flag.configure(text=" 🔥 BRUTAL ", bg="#f38ba8", fg="#11111b", font=("Segoe UI", 8, "bold"))
                else:
                    r_bg = "#1e1e2e"
                    row.configure(bg=r_bg, highlightbackground="#313244", highlightcolor="#313244")
                    cb.configure(bg=r_bg, activebackground=r_bg, selectcolor="#313244")
                    info_frame.configure(bg=r_bg)
                    lbl_name.configure(bg=r_bg, fg="#6c7086", font=("Segoe UI", 9, "normal"))
                    lbl_cnt.configure(bg=r_bg, fg="#585b70")
                    lbl_flag.configure(text=" ⚪ NONAKTIF ", bg="#313244", fg="#6c7086", font=("Segoe UI", 8, "bold"))

            # Toggle handler saat klik se-baris (di mana saja pada baris)
            def _toggle_from_row(event=None):
                is_now = not var.get()
                var.set(is_now)
                if is_now:
                    selected_brutal_tags.add(sfx)
                else:
                    selected_brutal_tags.discard(sfx)
                _apply_row_visual(is_now)
                lbl_tb_title.config(text=f"Daftar Tag Brutal ({len(selected_brutal_tags)} dari {len(cats)} aktif):")

            # Toggle handler saat klik checkbutton langsung
            def _toggle_from_cb():
                is_now = var.get()
                if is_now:
                    selected_brutal_tags.add(sfx)
                else:
                    selected_brutal_tags.discard(sfx)
                _apply_row_visual(is_now)
                lbl_tb_title.config(text=f"Daftar Tag Brutal ({len(selected_brutal_tags)} dari {len(cats)} aktif):")

            cb.configure(command=_toggle_from_cb)

            # Klik di mana saja pada baris (frame, badge, teks, status) langsung toggle!
            for clickable in (row, badge, info_frame, lbl_name, lbl_cnt, lbl_flag):
                clickable.bind("<Button-1>", _toggle_from_row)

            # Hover feedback halus
            def _on_hover(e):
                row.configure(highlightthickness=1, highlightbackground="#f38ba8" if var.get() else "#585b70")
            def _on_leave(e):
                row.configure(highlightthickness=1, highlightbackground="#f38ba8" if var.get() else "#313244")
            row.bind("<Enter>", _on_hover, add="+")
            row.bind("<Leave>", _on_leave, add="+")

            # Bind mousewheel ke seluruh komponen baris
            for w in (row, cb, badge, info_frame, lbl_name, lbl_cnt, lbl_flag):
                _bind_scroll_recursive(w)

        def _render_list():
            for w in inner.winfo_children():
                w.destroy()

            cats = self.config.get("custom_trap_endings", [])
            lbl_tb_title.config(text=f"Daftar Tag Brutal ({len(selected_brutal_tags)} dari {len(cats)} aktif):")

            if not cats:
                tk.Label(inner, text="Belum ada kategori akhiran kustom.", font=("Segoe UI", 9, "italic"), fg="#6c7086", bg="#181825", pady=20).pack(fill=tk.X)
                return

            for idx, cat in enumerate(cats):
                _create_row_item(cat, idx, cats)

            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_toggle_current_mode():
            c_mode = self.config.get("game_mode", "default")
            if c_mode == "brutal":
                self.set_game_mode("default")
                lbl_mode_cur.config(text="⚪ Mode Saat Ini: DEFAULT", fg=THEME["primary"])
                btn_toggle_mode.config(text="🔥 Aktifkan Mode Brutal Sekarang", bg="#f38ba8", fg="#11111b")
            else:
                self.set_game_mode("brutal")
                lbl_mode_cur.config(text="🔥 Mode Brutal Saat Ini: AKTIF", fg="#f38ba8")
                btn_toggle_mode.config(text="Matikan Mode Brutal", bg="#313244", fg=THEME["text_primary"])
            _render_list()

        btn_toggle_mode.config(command=_on_toggle_current_mode)

        def _on_quick_add_brutal():
            sfx = "".join(c for c in entry_sfx.get().strip().upper() if c.isalpha())
            if not sfx:
                self.show_toast("⚠️ Masukkan huruf akhiran terlebih dahulu!")
                return
            
            categories = self.config.get("custom_trap_endings", [])
            found = False
            for cat in categories:
                if cat.get("suffix", "").upper() == sfx:
                    found = True
                    break
            
            if not found:
                swatches = ["#cba6f7", "#f5c2e7", "#89dceb", "#94e2d5", "#f9e2af", "#fab387", "#a6e3a1"]
                col = swatches[len(categories) % len(swatches)]
                new_cat = {
                    "suffix": sfx,
                    "name": f"Akhiran {sfx}",
                    "enabled": (self.config.get("game_mode") == "brutal"),
                    "color": col
                }
                categories.append(new_cat)
                self.config["custom_trap_endings"] = categories
                save_config(self.config)
                self.solver.set_custom_endings(categories)
                self._render_custom_category_quick_bar()

            selected_brutal_tags.add(sfx)
            entry_sfx.delete(0, tk.END)
            _render_list()
            self.show_toast(f"✅ Akhiran [{sfx}] ditambahkan ke Mode Brutal!")

        entry_sfx.bind("<Return>", lambda e: _on_quick_add_brutal())

        btn_add_brutal = tk.Button(
            row_add,
            text="➕ Tambah ke Brutal",
            font=("Segoe UI", 8, "bold"),
            bg="#fab387",
            fg="#11111b",
            activebackground="#f9e2af",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=_on_quick_add_brutal
        )
        btn_add_brutal.pack(side=tk.LEFT)

        def _select_all():
            for c in self.config.get("custom_trap_endings", []):
                selected_brutal_tags.add(c.get("suffix", "").upper())
            _render_list()

        def _reset_default():
            selected_brutal_tags.clear()
            for t in ["AMSI", "KSO", "RHU", "TL", "BD"]:
                selected_brutal_tags.add(t)
            _render_list()

        def _clear_all():
            selected_brutal_tags.clear()
            _render_list()

        btn_clr = tk.Button(tb, text="❌ Hapus Semua", font=("Segoe UI", 8), bg="#313244", fg="#f38ba8", activebackground=THEME["bg_hover"], relief=tk.FLAT, padx=6, pady=1, cursor="hand2", command=_clear_all)
        btn_clr.pack(side=tk.RIGHT, padx=(2, 0))

        btn_def = tk.Button(tb, text="🔄 Reset Default (AMSI, KSO, ...)", font=("Segoe UI", 8), bg="#313244", fg="#fab387", activebackground=THEME["bg_hover"], relief=tk.FLAT, padx=6, pady=1, cursor="hand2", command=_reset_default)
        btn_def.pack(side=tk.RIGHT, padx=2)

        btn_all = tk.Button(tb, text="⚡ Pilih Semua", font=("Segoe UI", 8), bg="#313244", fg=THEME["primary"], activebackground=THEME["bg_hover"], relief=tk.FLAT, padx=6, pady=1, cursor="hand2", command=_select_all)
        btn_all.pack(side=tk.RIGHT, padx=2)

        _render_list()

    def _render_custom_category_items(self):
        """Merender baris daftar kategori akhiran kustom di canvas jika jendela terpisah dibuka"""
        if hasattr(self, "tab_tags_container") and hasattr(self.tab_tags_container, "_refresh_custom_list"):
            self.tab_tags_container._refresh_custom_list()

    def _render_custom_category_quick_bar(self):
        """Merender tombol toggle untuk tiap kategori custom bergaya Tactical Cyber Chips"""
        if not hasattr(self, "custom_cats_bar") or not self.custom_cats_bar.winfo_exists():
            return

        for w in self.custom_cats_bar.winfo_children():
            w.destroy()

        categories = self.config.get("custom_trap_endings", [])

        current_row = tk.Frame(self.custom_cats_bar, bg=THEME["bg_root"])
        current_row.pack(fill=tk.X, pady=(0, 2))

        tag_ico = render_vector_icon("tag", size=13, color=THEME["text_secondary"])
        btn_tag_icon = tk.Button(
            current_row,
            image=tag_ico,
            bg=THEME["bg_root"],
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self.open_custom_categories_window
        )
        btn_tag_icon.image = tag_ico
        btn_tag_icon.pack(side=tk.LEFT, padx=(0, 4))

        if not categories:
            lbl_none = tk.Label(
                current_row,
                text="(Belum ada tag)",
                font=("Segoe UI", 8, "italic"),
                fg=THEME["text_muted"],
                bg=THEME["bg_root"]
            )
            lbl_none.pack(side=tk.LEFT, padx=(0, 4))
            return

        avail_w = self.custom_cats_bar.winfo_width()
        if avail_w < 150:
            try:
                avail_w = self.root.winfo_width() - 20
            except Exception:
                avail_w = 420
        if avail_w < 150:
            avail_w = 420

        max_row_w = avail_w - 14

        import tkinter.font as tkfont
        tag_font = tkfont.Font(family="Segoe UI", size=8, weight="bold")
        cur_row_w = 26

        for idx, cat in enumerate(categories):
            sfx = cat.get("suffix", "").upper()
            enabled = cat.get("enabled", True)
            col = cat.get("color", THEME["primary"])

            if enabled:
                btn_bg = col
                btn_fg = THEME["text_dark"]
                btn_abg = THEME["accent_neon"]
            else:
                btn_bg = THEME["bg_card"]
                btn_fg = THEME["text_muted"]
                btn_abg = THEME["bg_hover"]

            btn_w = tag_font.measure(sfx) + 18

            if cur_row_w + btn_w > max_row_w and cur_row_w > 30:
                current_row = tk.Frame(self.custom_cats_bar, bg=THEME["bg_root"])
                current_row.pack(fill=tk.X, pady=(0, 2))
                cur_row_w = 0

            btn = tk.Button(
                current_row,
                text=sfx,
                font=tag_font,
                bg=btn_bg,
                fg=btn_fg,
                activebackground=btn_abg,
                activeforeground=THEME["text_dark"] if enabled else THEME["text_primary"],
                relief=tk.FLAT,
                bd=0,
                padx=5,
                pady=1,
                cursor="hand2",
                command=lambda i=idx, cur=enabled: self._on_toggle_custom_category(i, not cur)
            )
            btn.pack(side=tk.LEFT, padx=2)
            cur_row_w += btn_w

    def show_toast(self, message, undo_callback=None):
        """Menampilkan notifikasi toast non-intrusif di bagian bawah tab LIVE"""
        if not hasattr(self, "lbl_toast") or not self.lbl_toast.winfo_exists():
            return
        self.lbl_toast.config(text=message)
        if undo_callback and hasattr(self, "btn_undo"):
            self.btn_undo.config(command=undo_callback)
            self.btn_undo.pack(side=tk.RIGHT, padx=4)
        elif hasattr(self, "btn_undo"):
            self.btn_undo.pack_forget()

        if hasattr(self, "_toast_timer") and self._toast_timer:
            try:
                self.root.after_cancel(self._toast_timer)
            except Exception:
                pass

        self._toast_timer = self.root.after(4000, self._clear_toast)

    def _clear_toast(self):
        """Membersihkan teks notifikasi toast"""
        if hasattr(self, "lbl_toast") and self.lbl_toast.winfo_exists():
            self.lbl_toast.config(text="")
        if hasattr(self, "btn_undo") and self.btn_undo.winfo_exists():
            self.btn_undo.pack_forget()
        self._toast_timer = None

    def copy_to_clipboard(self, sisa_text, full_word=None, show_toast_flag=True):
        """Menyalin sisa teks kata ke clipboard sistem Windows"""
        self.root.clipboard_clear()
        self.root.clipboard_append(sisa_text.lower())
        self.root.update()
        if show_toast_flag:
            info = f" (dari '{full_word.upper()}')" if full_word else ""
            self.show_toast(f"Tersalin sisa kata: '{sisa_text.upper()}'{info} - Tinggal Ctrl+V di Roblox!")

    def _on_toggle_custom_category(self, idx, new_val=None, skip_ui_rebuild=False):
        """Toggle aktif/nonaktif kategori akhiran kustom (mendukung 1 atau 2 argumen)"""
        categories = self.config.get("custom_trap_endings", [])
        if 0 <= idx < len(categories):
            sfx = categories[idx].get("suffix", "").upper()
            if new_val is None:
                new_val = not categories[idx].get("enabled", True)

            # Jika sedang di Mode Santai dan pengguna mencoba mengaktifkan tag yang dilarang (mengandung X, Q, F)
            if getattr(self, "mode_santai_var", tk.BooleanVar()).get() and new_val and any(ch in sfx.lower() for ch in ("x", "q", "f")):
                self.show_toast(f"⚠️ Tag [{sfx}] dilarang di Mode Santai (mengandung X, Q, atau F)!")
                self._render_custom_category_items()
                self._render_custom_category_quick_bar()
                return

            categories[idx]["enabled"] = bool(new_val)

            cur_mode = self.config.get("game_mode", "santai" if getattr(self, "mode_santai_var", tk.BooleanVar()).get() else "default")
            if cur_mode == "brutal":
                brutal_tags = set(self.config.get("brutal_mode_tags", []))
                if new_val:
                    brutal_tags.add(sfx)
                else:
                    brutal_tags.discard(sfx)
                self.config["brutal_mode_tags"] = list(brutal_tags)
            elif cur_mode in ("default", "normal"):
                default_tags = set(self.config.get("saved_default_tags", self.config.get("saved_normal_tags", [])))
                if not default_tags:
                    default_tags = {c.get("suffix", "").upper() for c in categories if c.get("enabled", True)}
                if new_val:
                    default_tags.add(sfx)
                else:
                    default_tags.discard(sfx)
                self.config["saved_default_tags"] = list(default_tags)
                self.config["saved_normal_tags"] = list(default_tags)

            # Jika pengguna sengaja menonaktifkan tag saat di Mode Santai, hapus dari daftar auto-restore
            auto_disabled = set(self.config.get("santai_auto_disabled_tags", []))
            if not new_val and sfx in auto_disabled:
                auto_disabled.remove(sfx)
                self.config["santai_auto_disabled_tags"] = list(auto_disabled)

            self.config["custom_trap_endings"] = categories
            self._sync_tags_and_solver(skip_ui_rebuild=skip_ui_rebuild)
            status_str = "diaktifkan" if new_val else "dinonaktifkan"
            self.show_toast(f"Tag [{sfx}] {status_str}")

    def _on_move_custom_category(self, idx, direction, skip_ui_rebuild=False):
        """Memindahkan posisi kategori ke atas (-1) atau ke bawah (+1)"""
        categories = self.config.get("custom_trap_endings", [])
        new_idx = idx + direction
        if 0 <= idx < len(categories) and 0 <= new_idx < len(categories):
            categories[idx], categories[new_idx] = categories[new_idx], categories[idx]
            self.config["custom_trap_endings"] = categories
            self._sync_tags_and_solver(skip_ui_rebuild=skip_ui_rebuild)
            sfx = categories[new_idx].get("suffix", "")
            self.show_toast(f"Tag '{sfx}' dipindahkan ke urutan #{new_idx + 1}")

    def _on_sort_custom_categories_az(self):
        """Mengurutkan kategori kustom secara abjad A-Z"""
        categories = self.config.get("custom_trap_endings", [])
        if not categories:
            return
        categories.sort(key=lambda c: c.get("suffix", "").upper())
        self.config["custom_trap_endings"] = categories
        self._sync_tags_and_solver(skip_ui_rebuild=False)
        self.show_toast("🔤 Kategori akhiran diurutkan A-Z")

    def _on_sort_custom_categories_count(self):
        """Mengurutkan kategori kustom berdasarkan jumlah kata di kamus terbanyak"""
        categories = self.config.get("custom_trap_endings", [])
        if not categories:
            return
        categories.sort(key=lambda c: self.solver.count_words_by_suffix(c.get("suffix", "")), reverse=True)
        self.config["custom_trap_endings"] = categories
        self._sync_tags_and_solver(skip_ui_rebuild=False)
        self.show_toast("📊 Kategori akhiran diurutkan berdasarkan kata terbanyak")

    def _on_sort_custom_categories_length(self, reverse=True):
        """Mengurutkan kategori kustom berdasarkan panjang huruf akhiran"""
        categories = self.config.get("custom_trap_endings", [])
        if not categories:
            return

        if reverse:
            categories.sort(key=lambda c: (-len(c.get("suffix", "")), c.get("suffix", "").upper()))
        else:
            categories.sort(key=lambda c: (len(c.get("suffix", "")), c.get("suffix", "").upper()))

        self.config["custom_trap_endings"] = categories
        self._sync_tags_and_solver(skip_ui_rebuild=False)

        mode_txt = "terpanjang" if reverse else "paling sedikit"
        self.show_toast(f"📏 Kategori akhiran diurutkan huruf {mode_txt}")

    def _on_delete_custom_category(self, idx):
        """Menghapus kategori akhiran kustom"""
        categories = self.config.get("custom_trap_endings", [])
        if 0 <= idx < len(categories):
            removed = categories.pop(idx)
            sfx = removed.get("suffix", "").upper()
            brutal_tags = set(self.config.get("brutal_mode_tags", []))
            brutal_tags.discard(sfx)
            self.config["brutal_mode_tags"] = list(brutal_tags)

            normal_tags = set(self.config.get("saved_normal_tags", []))
            normal_tags.discard(sfx)
            self.config["saved_normal_tags"] = list(normal_tags)

            default_tags = set(self.config.get("saved_default_tags", []))
            default_tags.discard(sfx)
            self.config["saved_default_tags"] = list(default_tags)

            self.config["custom_trap_endings"] = categories
            save_config(self.config)
            self.solver.set_custom_endings(categories)
            self._render_custom_category_items()
            self._render_custom_category_quick_bar()
            if hasattr(self, "last_detected_word") and self.last_detected_word:
                self.update_results(self.last_detected_word)
            self.show_toast(f"🗑️ Kategori [{sfx}] dihapus")

    def _on_reset_custom_categories(self):
        """Mereset daftar kategori akhiran ke default NS & NGK"""
        categories = [
            {"suffix": "NS", "name": "Akhiran NS", "enabled": True, "color": "#cba6f7"},
            {"suffix": "NGK", "name": "Akhiran NGK", "enabled": True, "color": "#f5c2e7"}
        ]
        self.config["custom_trap_endings"] = categories
        self._sync_tags_and_solver(skip_ui_rebuild=False)
        self.show_toast("↩️ Kategori akhiran direset ke default (NS & NGK)")

    def open_edit_custom_category_dialog(self, idx_or_cat):
        """Membuka dialog popup modal untuk mengedit akhiran, nama, dan warna kategori"""
        from tkinter import colorchooser
        categories = self.config.get("custom_trap_endings", [])
        if isinstance(idx_or_cat, int):
            if not (0 <= idx_or_cat < len(categories)):
                return
            idx = idx_or_cat
            cat = categories[idx]
        else:
            cat = idx_or_cat
            try:
                idx = categories.index(cat)
            except ValueError:
                idx = -1
                return

        cur_sfx = cat.get("suffix", "").upper()
        cur_name = cat.get("name") or f"Akhiran {cur_sfx}"
        cur_color = cat.get("color", THEME["primary"])

        edit_win, _ = self._create_clean_toplevel(
            f"✏️ Edit Tag: [{cur_sfx}]", 420, 440, min_w=380, min_h=400, resizable=False
        )
        edit_win.grab_set()

        body = tk.Frame(edit_win, bg=THEME["bg_card"], padx=16, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text="Akhiran (Huruf):", font=("Segoe UI", 9, "bold"), fg=THEME["text_primary"], bg=THEME["bg_card"], anchor="w").pack(fill=tk.X, pady=(2, 2))
        entry_sfx = tk.Entry(body, font=("Segoe UI", 10, "bold"), bg=THEME["bg_input"], fg=THEME["text_primary"], insertbackground=THEME["primary"], relief=tk.FLAT)
        entry_sfx.insert(0, cur_sfx)
        entry_sfx.pack(fill=tk.X, pady=(0, 8))

        tk.Label(body, text="Nama Kategori:", font=("Segoe UI", 9, "bold"), fg=THEME["text_primary"], bg=THEME["bg_card"], anchor="w").pack(fill=tk.X, pady=(2, 2))
        entry_name = tk.Entry(body, font=("Segoe UI", 9), bg=THEME["bg_input"], fg=THEME["text_primary"], insertbackground=THEME["primary"], relief=tk.FLAT)
        entry_name.insert(0, cur_name)
        entry_name.pack(fill=tk.X, pady=(0, 8))

        # Preview
        preview_frame = tk.Frame(body, bg=THEME["bg_root"], padx=10, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        preview_frame.pack(fill=tk.X, pady=(0, 8))
        tk.Label(preview_frame, text="Preview Tag:", font=("Segoe UI", 8), fg=THEME["text_secondary"], bg=THEME["bg_root"]).pack(side=tk.LEFT, padx=(0, 10))

        lbl_preview = tk.Label(
            preview_frame,
            text=cur_sfx,
            font=("Segoe UI", 9, "bold"),
            bg=cur_color,
            fg=THEME["text_dark"],
            padx=10,
            pady=2
        )
        lbl_preview.pack(side=tk.LEFT)

        selected_color = [cur_color]

        def update_preview(*args):
            s = entry_sfx.get().strip().upper() or "TAG"
            lbl_preview.config(text=s, bg=selected_color[0])

        entry_sfx.bind("<KeyRelease>", update_preview)

        def pick_custom_color():
            res = colorchooser.askcolor(initialcolor=selected_color[0], parent=edit_win, title="Pilih Warna Kustom")
            if res and res[1]:
                selected_color[0] = res[1]
                update_preview()

        btn_pick_color = tk.Button(
            body,
            text="🎨 Pilih Warna Tag...",
            font=("Segoe UI", 8),
            bg=THEME["bg_hover"],
            fg=THEME["primary"],
            relief=tk.FLAT,
            padx=6,
            pady=3,
            cursor="hand2",
            command=pick_custom_color
        )
        btn_pick_color.pack(anchor="w", pady=(0, 10))

        btn_box = tk.Frame(body, bg=THEME["bg_card"])
        btn_box.pack(fill=tk.X, pady=(10, 0))

        def on_save_edit():
            raw_sfx = entry_sfx.get().strip().upper()
            clean_sfx = "".join(c for c in raw_sfx if c.isalpha())
            if not clean_sfx:
                self.show_toast("Akhiran harus berupa huruf alfabet!")
                return
            cat["suffix"] = clean_sfx
            cat["name"] = entry_name.get().strip() or f"Akhiran {clean_sfx}"
            cat["color"] = selected_color[0]
            self.config["custom_trap_endings"] = categories
            save_config(self.config)
            self.solver.set_custom_endings(categories)
            self._render_custom_category_items()
            self._render_custom_category_quick_bar()
            edit_win.destroy()
            self.show_toast(f"✅ Tag [{clean_sfx}] diperbarui")

        btn_save = tk.Button(btn_box, text="Simpan", font=("Segoe UI", 9, "bold"), bg=THEME["primary"], fg=THEME["text_dark"], relief=tk.FLAT, padx=12, pady=4, cursor="hand2", command=on_save_edit)
        btn_save.pack(side=tk.LEFT, padx=(0, 8))
        btn_cancel = tk.Button(btn_box, text="Batal", font=("Segoe UI", 9), bg=THEME["bg_hover"], fg=THEME["text_secondary"], relief=tk.FLAT, padx=12, pady=4, cursor="hand2", command=edit_win.destroy)
        btn_cancel.pack(side=tk.LEFT)


    def _get_uncorrected_counts(self):
        """Menghitung jumlah sampel belum dikoreksi di kurang_tepat dan tidak_dikenali"""
        p_kt = self.ocr.kurang_tepat_dir
        count_kt = 0
        if os.path.exists(p_kt):
            try:
                count_kt = len([f for f in os.listdir(p_kt) if f.endswith(".png") and "_seharusnya_" not in f])
            except Exception:
                pass

        p_td = self.ocr.unknown_dir
        count_td = 0
        if os.path.exists(p_td):
            try:
                count_td = len([f for f in os.listdir(p_td) if f.endswith(".png") and "_seharusnya_" not in f and not os.path.isdir(os.path.join(p_td, f))])
            except Exception:
                pass
        return count_kt, count_td

    def _update_koreksi_badge(self):
        """Memperbarui teks dan warna tombol koreksi berdasarkan jumlah sampel belum dikoreksi"""
        count_kt, count_td = self._get_uncorrected_counts()
        total = count_kt + count_td

        if hasattr(self, "btn_koreksi") and self.btn_koreksi.winfo_exists():
            if total > 0:
                self.btn_koreksi.config(
                    text=f"📝 Koreksi ({total})",
                    bg="#fab387",
                    fg="#11111b",
                    activebackground="#f9e2af"
                )
            else:
                self.btn_koreksi.config(
                    text="📝 Koreksi (0)",
                    bg="#313244",
                    fg=THEME["text_secondary"],
                    activebackground=THEME["bg_hover"]
                )

    def open_koreksi_window(self):
        """Membuka jendela untuk mendata hasil deteksi yang tepat bagi sampel di kurang_tepat dan tidak_dikenali"""
        if hasattr(self, "koreksi_win") and self.koreksi_win and self.koreksi_win.winfo_exists():
            self.koreksi_win.lift()
            self.koreksi_win.focus_force()
            return

        self.koreksi_win, _ = self._create_clean_toplevel(
            "Pendataan Koreksi Sampel", 480, 620, min_w=440, min_h=540
        )

        self._koreksi_items = []
        self._koreksi_current_idx = 0
        self._koreksi_tk_img = None

        sub_hdr = tk.Frame(self.koreksi_win, bg=THEME["bg_card"], padx=12, pady=6)
        sub_hdr.pack(fill=tk.X)

        tk.Label(
            sub_hdr,
            text="Koreksi visual sampel pembacaan OCR",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg=THEME["bg_card"]
        ).pack(side=tk.LEFT)

        ico_folder = render_vector_icon("folder", size=13, color=THEME["text_primary"])
        btn_folder = tk.Button(
            sub_hdr,
            text=" Buka Folder",
            image=ico_folder,
            compound="left",
            font=("Segoe UI", 8),
            bg=THEME["border"],
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._koreksi_open_folder
        )
        btn_folder.image = ico_folder
        btn_folder.pack(side=tk.RIGHT)

        # Sumber Selection Bar (Kurang Tepat vs Tidak Dikenali)
        source_frame = tk.Frame(self.koreksi_win, bg=THEME["bg_card_alt"], padx=10, pady=6)
        source_frame.pack(fill=tk.X)

        ico_src = render_vector_icon("tag", size=13, color=THEME["text_secondary"])
        lbl_sumber = tk.Label(
            source_frame,
            text=" Sumber:",
            image=ico_src,
            compound="left",
            font=("Segoe UI", 8, "bold"),
            fg=THEME["text_secondary"],
            bg=THEME["bg_card_alt"]
        )
        lbl_sumber.image = ico_src
        lbl_sumber.pack(side=tk.LEFT, padx=(0, 4))

        count_kt, count_td = self._get_uncorrected_counts()
        initial_source = "tidak_dikenali" if (count_kt == 0 and count_td > 0) else "kurang_tepat"
        self._koreksi_source = tk.StringVar(value=initial_source)

        # Jika tidak ada sampel yang belum dikoreksi sama sekali di kedua folder,
        # otomatis jangan centang filter 'hanya belum dikoreksi' agar sampel yang ada tetap tampil
        has_uncorrected = (count_kt > 0 or count_td > 0)
        self._koreksi_only_uncorrected = tk.BooleanVar(value=has_uncorrected)

        ico_flag = render_vector_icon("flag", size=12, color=THEME["danger"])
        self.rb_kt = tk.Radiobutton(
            source_frame,
            text=f" Kurang Tepat ({count_kt})",
            image=ico_flag,
            compound="left",
            variable=self._koreksi_source,
            value="kurang_tepat",
            font=("Segoe UI", 8, "bold"),
            fg=THEME["danger"],
            bg=THEME["bg_card_alt"],
            selectcolor=THEME["border"],
            activebackground=THEME["bg_card_alt"],
            activeforeground=THEME["danger"],
            command=self._koreksi_reload_items
        )
        self.rb_kt.image = ico_flag
        self.rb_kt.pack(side=tk.LEFT, padx=2)

        ico_zap = render_vector_icon("zap", size=12, color=THEME["warning"])
        self.rb_td = tk.Radiobutton(
            source_frame,
            text=f" Tidak Dikenali ({count_td})",
            image=ico_zap,
            compound="left",
            variable=self._koreksi_source,
            value="tidak_dikenali",
            font=("Segoe UI", 8, "bold"),
            fg=THEME["warning"],
            bg=THEME["bg_card_alt"],
            selectcolor=THEME["border"],
            activebackground=THEME["bg_card_alt"],
            activeforeground=THEME["warning"],
            command=self._koreksi_reload_items
        )
        self.rb_td.image = ico_zap
        self.rb_td.pack(side=tk.LEFT, padx=2)

        self.rb_all = tk.Radiobutton(
            source_frame,
            text="Semua",
            variable=self._koreksi_source,
            value="all",
            font=("Segoe UI", 8),
            fg=THEME["primary"],
            bg=THEME["bg_card_alt"],
            selectcolor=THEME["border"],
            activebackground=THEME["bg_card_alt"],
            activeforeground=THEME["primary"],
            command=self._koreksi_reload_items
        )
        self.rb_all.pack(side=tk.LEFT, padx=2)

        # Bar filter / opsi
        filter_bar = tk.Frame(self.koreksi_win, bg=THEME["bg_card"], padx=12, pady=4)
        filter_bar.pack(fill=tk.X)

        chk_filter = tk.Checkbutton(
            filter_bar,
            text="Hanya tampilkan yang belum dikoreksi",
            variable=self._koreksi_only_uncorrected,
            font=("Segoe UI", 9),
            fg=THEME["text_secondary"],
            bg=THEME["bg_card"],
            selectcolor=THEME["border"],
            activebackground=THEME["bg_card"],
            activeforeground=THEME["text_primary"],
            command=self._koreksi_reload_items
        )
        chk_filter.pack(side=tk.LEFT)

        self.lbl_koreksi_progress = tk.Label(
            filter_bar,
            text="- / -",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["primary"],
            bg=THEME["bg_card"]
        )
        self.lbl_koreksi_progress.pack(side=tk.RIGHT)

        # Image Display Container
        img_container = tk.Frame(self.koreksi_win, bg=THEME["bg_root"], padx=8, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        img_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        self.lbl_koreksi_img = tk.Label(
            img_container,
            text="Tidak ada gambar",
            font=("Segoe UI", 10, "italic"),
            fg=THEME["text_muted"],
            bg=THEME["bg_root"]
        )
        self.lbl_koreksi_img.pack(expand=True)

        # Info Frame
        self.info_box = tk.Frame(self.koreksi_win, bg=THEME["bg_card"], padx=12, pady=6)
        self.info_box.pack(fill=tk.X, padx=12, pady=4)

        self.lbl_koreksi_fname = tk.Label(
            self.info_box,
            text="File: -",
            font=("Segoe UI", 8),
            fg=THEME["text_muted"],
            bg=THEME["bg_card"],
            anchor=tk.W
        )
        self.lbl_koreksi_fname.pack(fill=tk.X)

        self.lbl_koreksi_detail = tk.Label(
            self.info_box,
            text="Terdeteksi: - | Akurasi: -",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_primary"],
            bg=THEME["bg_card"],
            anchor=tk.W
        )
        self.lbl_koreksi_detail.pack(fill=tk.X)

        self.lbl_koreksi_status = tk.Label(
            self.info_box,
            text="Status: -",
            font=("Segoe UI", 8),
            fg=THEME["warning"],
            bg=THEME["bg_card"],
            anchor=tk.W
        )
        self.lbl_koreksi_status.pack(fill=tk.X)

        # Input Frame Koreksi
        input_frame = tk.Frame(self.koreksi_win, bg=THEME["border"], padx=12, pady=8)
        input_frame.pack(fill=tk.X, padx=12, pady=6)

        ico_edit = render_vector_icon("edit", size=13, color=THEME["warning"])
        lbl_input_prompt = tk.Label(
            input_frame,
            text=" Awalan yang Seharusnya (Benar):",
            image=ico_edit,
            compound="left",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["warning"],
            bg=THEME["border"]
        )
        lbl_input_prompt.image = ico_edit
        lbl_input_prompt.pack(anchor=tk.W)

        action_row = tk.Frame(input_frame, bg=THEME["border"])
        action_row.pack(fill=tk.X, pady=(4, 0))

        self.entry_koreksi_text = tk.Entry(
            action_row,
            font=("Segoe UI", 12, "bold"),
            bg=THEME["bg_card"],
            fg=THEME["text_primary"],
            insertbackground=THEME["text_primary"],
            relief=tk.FLAT,
            justify=tk.CENTER
        )
        self.entry_koreksi_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=3)
        self.entry_koreksi_text.bind("<Return>", lambda e: self._koreksi_save_current())

        ico_check = render_vector_icon("check", size=13, color=THEME["bg_root"])
        btn_save = tk.Button(
            action_row,
            text=" Simpan (Enter)",
            image=ico_check,
            compound="left",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["primary"],
            fg=THEME["bg_root"],
            activebackground=THEME["accent_neon"],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._koreksi_save_current
        )
        btn_save.image = ico_check
        btn_save.pack(side=tk.RIGHT)

        # Navigation & Bottom Bar
        nav_frame = tk.Frame(self.koreksi_win, bg=THEME["bg_card"], padx=12, pady=6)
        nav_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ico_prev = render_vector_icon("arrow_back", size=12, color=THEME["text_primary"])
        self.btn_koreksi_prev = tk.Button(
            nav_frame,
            text=" Sebelumnya (←)",
            image=ico_prev,
            compound="left",
            font=("Segoe UI", 8),
            bg=THEME["border"],
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=2,
            command=self._koreksi_prev
        )
        self.btn_koreksi_prev.image = ico_prev
        self.btn_koreksi_prev.pack(side=tk.LEFT)

        ico_next = render_vector_icon("arrow_forward", size=12, color=THEME["text_primary"])
        self.btn_koreksi_next = tk.Button(
            nav_frame,
            text=" Berikutnya (→)",
            image=ico_next,
            compound="left",
            font=("Segoe UI", 8),
            bg=THEME["border"],
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=2,
            command=self._koreksi_next
        )
        self.btn_koreksi_next.image = ico_next
        self.btn_koreksi_next.pack(side=tk.LEFT, padx=4)

        ico_trash = render_vector_icon("trash", size=13, color=THEME["bg_root"])
        btn_delete = tk.Button(
            nav_frame,
            text=" Hapus Sampel (Del)",
            image=ico_trash,
            compound="left",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["danger"],
            fg=THEME["bg_root"],
            activebackground=THEME["danger_bg"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=2,
            command=self._koreksi_delete_current
        )
        btn_delete.image = ico_trash
        btn_delete.pack(side=tk.RIGHT)

        # Shortcut Del / Delete untuk hapus sampel seketika tanpa konfirmasi
        self.koreksi_win.bind("<Delete>", lambda e: (self._koreksi_delete_current(), "break")[1])
        self.entry_koreksi_text.bind("<Delete>", lambda e: (self._koreksi_delete_current(), "break")[1])

        # Shortcut Panah Kiri, Kanan, Atas, Bawah, PgUp, PgDn untuk navigasi sampel / halaman
        self.koreksi_win.bind("<Left>", lambda e: (self._koreksi_prev(), "break")[1])
        self.koreksi_win.bind("<Right>", lambda e: (self._koreksi_next(), "break")[1])
        self.koreksi_win.bind("<Up>", lambda e: (self._koreksi_prev(), "break")[1])
        self.koreksi_win.bind("<Down>", lambda e: (self._koreksi_next(), "break")[1])
        self.koreksi_win.bind("<Prior>", lambda e: (self._koreksi_prev(), "break")[1])
        self.koreksi_win.bind("<Next>", lambda e: (self._koreksi_next(), "break")[1])

        self.entry_koreksi_text.bind("<Left>", lambda e: (self._koreksi_prev(), "break")[1])
        self.entry_koreksi_text.bind("<Right>", lambda e: (self._koreksi_next(), "break")[1])
        self.entry_koreksi_text.bind("<Up>", lambda e: (self._koreksi_prev(), "break")[1])
        self.entry_koreksi_text.bind("<Down>", lambda e: (self._koreksi_next(), "break")[1])
        self.entry_koreksi_text.bind("<Prior>", lambda e: (self._koreksi_prev(), "break")[1])
        self.entry_koreksi_text.bind("<Next>", lambda e: (self._koreksi_next(), "break")[1])

        self._koreksi_reload_items()

    def _parse_file_info(self, fpath, source_type):
        fname = os.path.basename(fpath)
        name, _ = os.path.splitext(fname)
        parts = name.split("_")

        parent_dir = os.path.basename(os.path.dirname(fpath))
        is_in_subfolder = (parent_dir not in ("kurang_tepat", "tidak_dikenali"))

        if len(parts) >= 4:
            ts = f"{parts[0]}_{parts[1]}"
            conf = parts[-1]
            if "seharusnya" in parts:
                idx = parts.index("seharusnya")
                label = "_".join(parts[2:idx])
                seh = "_".join(parts[idx+1:-1])
                corr = True
            elif is_in_subfolder:
                label = "_".join(parts[2:-1])
                seh = parent_dir.upper()
                corr = True
            else:
                label = "_".join(parts[2:-1])
                seh = ""
                corr = False
            return {
                "ts": ts,
                "label": label,
                "seh": seh,
                "conf": conf,
                "is_corrected": corr,
                "filename": fname,
                "fpath": fpath,
                "source": source_type
            }
        elif is_in_subfolder and len(parts) >= 3:
            return {
                "ts": f"{parts[0]}_{parts[1]}",
                "label": parts[2],
                "seh": parent_dir.upper(),
                "conf": parts[-1] if len(parts) > 3 else "auto",
                "is_corrected": True,
                "filename": fname,
                "fpath": fpath,
                "source": source_type
            }
        return None

    def _koreksi_reload_items(self):
        count_kt, count_td = self._get_uncorrected_counts()
        if hasattr(self, "rb_kt") and self.rb_kt.winfo_exists():
            self.rb_kt.config(text=f" Kurang Tepat ({count_kt})")
            self.rb_td.config(text=f" Tidak Dikenali ({count_td})")

        source = getattr(self, "_koreksi_source", None)
        src_val = source.get() if source else "kurang_tepat"

        parsed = []

        # 1. Muat dari sample/kurang_tepat
        if src_val in ("kurang_tepat", "all"):
            folder_kt = self.ocr.kurang_tepat_dir
            if os.path.exists(folder_kt):
                for f in sorted(os.listdir(folder_kt)):
                    if f.endswith(".png"):
                        fpath = os.path.join(folder_kt, f)
                        p = self._parse_file_info(fpath, source_type="kurang_tepat")
                        if p:
                            parsed.append(p)

        # 2. Muat dari sample/tidak_dikenali
        if src_val in ("tidak_dikenali", "all"):
            folder_td = self.ocr.unknown_dir
            if os.path.exists(folder_td):
                for f in sorted(os.listdir(folder_td)):
                    fpath = os.path.join(folder_td, f)
                    if f.endswith(".png") and not os.path.isdir(fpath):
                        p = self._parse_file_info(fpath, source_type="tidak_dikenali")
                        if p:
                            parsed.append(p)
                if not self._koreksi_only_uncorrected.get():
                    for d in sorted(os.listdir(folder_td)):
                        sub = os.path.join(folder_td, d)
                        if os.path.isdir(sub):
                            for f in sorted(os.listdir(sub)):
                                if f.endswith(".png"):
                                    fpath = os.path.join(sub, f)
                                    p = self._parse_file_info(fpath, source_type="tidak_dikenali")
                                    if p:
                                        parsed.append(p)

        if self._koreksi_only_uncorrected.get():
            self._koreksi_items = [p for p in parsed if not p["is_corrected"]]
        else:
            self._koreksi_items = parsed

        if self._koreksi_current_idx >= len(self._koreksi_items):
            self._koreksi_current_idx = max(0, len(self._koreksi_items) - 1)
        self._koreksi_display_current()

    def _koreksi_display_current(self):
        if not hasattr(self, "lbl_koreksi_img") or not self.lbl_koreksi_img.winfo_exists():
            return

        if not self._koreksi_items:
            src_name = "sumber ini"
            if hasattr(self, "_koreksi_source"):
                s = self._koreksi_source.get()
                if s == "kurang_tepat":
                    src_name = "Kurang Tepat (F2)"
                elif s == "tidak_dikenali":
                    src_name = "Tidak Dikenali (Auto)"
                else:
                    src_name = "semua folder"

            self.lbl_koreksi_img.config(image="", text=f"🎉 Semua sampel di {src_name} sudah dikoreksi!\nTidak ada data yang perlu dikoreksi.", fg="#a6e3a1")
            self._koreksi_tk_img = None
            self.lbl_koreksi_fname.config(text="File: -")
            self.lbl_koreksi_detail.config(text="Semua sampel telah memiliki label yang tepat.")
            self.lbl_koreksi_status.config(text="Status: Selesai", fg="#a6e3a1")
            self.lbl_koreksi_progress.config(text="0 / 0")
            self.entry_koreksi_text.delete(0, tk.END)
            self.entry_koreksi_text.config(state=tk.DISABLED)
            if hasattr(self, "btn_koreksi_prev") and self.btn_koreksi_prev.winfo_exists():
                self.btn_koreksi_prev.config(state=tk.DISABLED)
            if hasattr(self, "btn_koreksi_next") and self.btn_koreksi_next.winfo_exists():
                self.btn_koreksi_next.config(state=tk.DISABLED)
            return

        self.entry_koreksi_text.config(state=tk.NORMAL)
        item = self._koreksi_items[self._koreksi_current_idx]
        fpath = item["fpath"]

        # Muat dan tampilkan gambar diperbesar
        try:
            im = Image.open(fpath)
            max_w, max_h = 360, 180
            scale = min(max_w / im.width, max_h / im.height, 2.0)
            target_w = max(1, int(im.width * scale))
            target_h = max(1, int(im.height * scale))
            im_resized = im.resize((target_w, target_h), Image.NEAREST)
            self._koreksi_tk_img = ImageTk.PhotoImage(im_resized)
            self.lbl_koreksi_img.config(image=self._koreksi_tk_img, text="")
        except Exception as e:
            self.lbl_koreksi_img.config(image="", text=f"Gagal memuat gambar: {e}", fg="#f38ba8")

        src_badge = "[Kurang Tepat]" if item["source"] == "kurang_tepat" else "[Tidak Dikenali]"
        self.lbl_koreksi_fname.config(text=f"{src_badge} {item['filename']}")
        self.lbl_koreksi_detail.config(text=f"Terdeteksi: '{item['label']}' | Keyakinan: {item['conf']}")

        if item["is_corrected"]:
            self.lbl_koreksi_status.config(text=f"Sudah Dikoreksi: '{item['seh']}'", fg=THEME["primary"])
        else:
            self.lbl_koreksi_status.config(text="Belum Dikoreksi", fg=THEME["warning"])

        total = len(self._koreksi_items)
        if total > 1:
            nav_state = tk.NORMAL
            self.lbl_koreksi_progress.config(text=f"Sampel {self._koreksi_current_idx + 1} dari {total}")
        else:
            nav_state = tk.DISABLED
            self.lbl_koreksi_progress.config(text=f"Sampel 1 dari 1 (Hanya 1 sampel)")

        if hasattr(self, "btn_koreksi_prev") and self.btn_koreksi_prev.winfo_exists():
            self.btn_koreksi_prev.config(state=nav_state)
        if hasattr(self, "btn_koreksi_next") and self.btn_koreksi_next.winfo_exists():
            self.btn_koreksi_next.config(state=nav_state)

        self.entry_koreksi_text.delete(0, tk.END)
        if item["seh"]:
            self.entry_koreksi_text.insert(0, item["seh"])
        self.entry_koreksi_text.focus_set()
        self.entry_koreksi_text.select_range(0, tk.END)

    def _koreksi_save_current(self):
        if not self._koreksi_items:
            return
        raw = self.entry_koreksi_text.get().strip().upper()
        corr = "".join([c for c in raw if c.isalpha()])
        if not corr:
            self.show_toast("⚠️ Ketik awalan kata yang seharusnya terlebih dahulu")
            return

        item = self._koreksi_items[self._koreksi_current_idx]
        old_path = item["fpath"]
        folder = os.path.dirname(old_path)
        new_filename = f"{item['ts']}_{item['label']}_seharusnya_{corr}_{item['conf']}.png"
        new_path = os.path.join(folder, new_filename)

        try:
            if old_path != new_path:
                if os.path.exists(new_path):
                    os.remove(new_path)
                os.rename(old_path, new_path)
            self.show_toast(f"✅ Tersimpan: '{item['label']}' seharusnya '{corr}'")
            self._update_koreksi_badge()
            self._koreksi_reload_items()
        except Exception as e:
            self.show_toast(f"⚠️ Gagal menyimpan koreksi: {e}")

    def _koreksi_delete_current(self):
        if not self._koreksi_items:
            return
        item = self._koreksi_items[self._koreksi_current_idx]
        fpath = item["fpath"]
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
            self.show_toast(f"🗑️ File '{item['filename']}' dihapus")
            self._update_koreksi_badge()
            self._koreksi_reload_items()
        except Exception as e:
            self.show_toast(f"⚠️ Gagal menghapus file: {e}")

    def _koreksi_prev(self):
        if not self._koreksi_items:
            return
        self._koreksi_current_idx = (self._koreksi_current_idx - 1) % len(self._koreksi_items)
        self._koreksi_display_current()

    def _koreksi_next(self):
        if not self._koreksi_items:
            return
        self._koreksi_current_idx = (self._koreksi_current_idx + 1) % len(self._koreksi_items)
        self._koreksi_display_current()

    def _koreksi_open_folder(self):
        src = getattr(self, "_koreksi_source", None)
        src_val = src.get() if src else "kurang_tepat"
        folder = self.ocr.unknown_dir if src_val == "tidak_dikenali" else self.ocr.kurang_tepat_dir
        try:
            os.startfile(folder)
        except Exception as e:
            self.show_toast(f"Gagal membuka folder: {e}")

    def open_add_word_dialog(self):
        """Membuka dialog popup untuk menambahkan kata baru ke kamus secara manual"""
        if hasattr(self, "add_word_win") and self.add_word_win and self.add_word_win.winfo_exists():
            self.add_word_win.lift()
            self.add_word_win.focus_force()
            if hasattr(self, "entry_new_word") and self.entry_new_word.winfo_exists():
                self.entry_new_word.focus_set()
                self.entry_new_word.select_range(0, tk.END)
            return

        self.add_word_win, _ = self._create_clean_toplevel(
            "➕ Tambah Kata ke Kamus", 420, 440, min_w=380, min_h=400
        )

        sub_hdr = tk.Frame(self.add_word_win, bg="#181825", padx=14, pady=6)
        sub_hdr.pack(fill=tk.X)

        tk.Label(
            sub_hdr,
            text="Tambahkan kata resmi baru ke kamus aktif",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg="#181825"
        ).pack(side=tk.LEFT)

        self.lbl_dict_total = tk.Label(
            sub_hdr,
            text=f"{len(self.solver.words):,} kata",
            font=("Segoe UI", 8, "bold"),
            fg="#a6e3a1",
            bg="#181825"
        )
        self.lbl_dict_total.pack(side=tk.RIGHT)

        # Input Card Frame
        input_card = tk.Frame(self.add_word_win, bg="#313244", padx=12, pady=10)
        input_card.pack(fill=tk.X, padx=14, pady=6)

        lbl_input_title = tk.Label(
            input_card,
            text="Ketik Kata Baru:",
            font=("Segoe UI", 10, "bold"),
            fg=THEME["text_primary"],
            bg="#313244"
        )
        lbl_input_title.pack(anchor=tk.W)

        self.entry_new_word = tk.Entry(
            input_card,
            font=("Segoe UI", 13, "bold"),
            bg="#181825",
            fg=THEME["text_primary"],
            insertbackground="#cdd6f4",
            relief=tk.FLAT,
            justify=tk.CENTER
        )
        self.entry_new_word.pack(fill=tk.X, pady=(6, 8), ipady=4)
        self.entry_new_word.bind("<KeyRelease>", self._on_new_word_keyrelease)
        self.entry_new_word.bind("<Return>", lambda e: self._do_add_word())

        # Live Info Box
        self.live_info_frame = tk.Frame(input_card, bg="#1e1e2e", padx=8, pady=6)
        self.live_info_frame.pack(fill=tk.X)

        self.lbl_live_tier = tk.Label(
            self.live_info_frame,
            text="Tipe: -",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_secondary"],
            bg="#1e1e2e",
            anchor=tk.W
        )
        self.lbl_live_tier.pack(fill=tk.X)

        self.lbl_live_status = tk.Label(
            self.live_info_frame,
            text="Status: Masukkan kata minimal 2 huruf",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#1e1e2e",
            anchor=tk.W
        )
        self.lbl_live_status.pack(fill=tk.X)

        # Tombol Tambah
        btn_add = tk.Button(
            self.add_word_win,
            text="➕ Tambahkan ke Kamus (Enter)",
            font=("Segoe UI", 10, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground=THEME["accent_neon"],
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._do_add_word
        )
        btn_add.pack(fill=tk.X, padx=14, pady=8)

        # Status Hasil
        self.lbl_add_feedback = tk.Label(
            self.add_word_win,
            text="",
            font=("Segoe UI", 9),
            fg="#a6e3a1",
            bg="#1e1e2e",
            wraplength=380
        )
        self.lbl_add_feedback.pack(fill=tk.X, padx=14, pady=2)

        # Bottom Frame
        bottom_frame = tk.Frame(self.add_word_win, bg="#181825", padx=14, pady=8)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        btn_open_dict = tk.Button(
            bottom_frame,
            text="📂 Buka kamus_lengkap.txt",
            font=("Segoe UI", 8),
            bg="#313244",
            fg=THEME["accent_neon"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=3,
            command=self._open_dict_file
        )
        btn_open_dict.pack(side=tk.LEFT)

        btn_close = tk.Button(
            bottom_frame,
            text="Tutup",
            font=("Segoe UI", 8),
            bg="#313244",
            fg=THEME["text_primary"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=10,
            pady=3,
            command=self.add_word_win.destroy
        )
        btn_close.pack(side=tk.RIGHT)

        # Pre-fill jika di manual entry ada kata yang diketik
        if hasattr(self, "entry_manual"):
            manual_text = self.entry_manual.get().strip().upper()
            if manual_text:
                self.entry_new_word.insert(0, manual_text)

        self._on_new_word_keyrelease()
        self.entry_new_word.focus_set()
        self.entry_new_word.select_range(0, tk.END)

    def _on_new_word_keyrelease(self, event=None):
        if not hasattr(self, "entry_new_word") or not self.entry_new_word.winfo_exists():
            return
        raw = self.entry_new_word.get().strip().lower()
        word = "".join([c for c in raw if c.isalpha()])

        if not word:
            self.lbl_live_tier.config(text="Tipe: -", fg=THEME["text_secondary"])
            self.lbl_live_status.config(text="Status: Masukkan kata minimal 2 huruf", fg="#6c7086")
            return

        last = word[-1]
        vowels = set("aiueo")
        has_vowel = any(v in word for v in vowels)

        if last == "x":
            tier_text = "💥 Tipe: JEBAKAN X (Akhiran X)"
            tier_fg = "#f38ba8"
        elif last in ("z", "q", "v", "j", "w", "f"):
            tier_text = f"⚡ Tipe: JEBAKAN SULIT (Akhiran {last.upper()})"
            tier_fg = "#fab387"
        else:
            tier_text = f"🛡️ Tipe: NORMAL / BERTAHAN (Akhiran {last.upper()})"
            tier_fg = "#a6e3a1"

        self.lbl_live_tier.config(text=tier_text, fg=tier_fg)

        if len(word) < 2:
            self.lbl_live_status.config(text="⚠️ Minimal 2 huruf", fg="#fab387")
        elif not has_vowel:
            self.lbl_live_status.config(text="⚠️ Wajib memiliki vokal (A, I, U, E, O)", fg="#f38ba8")
        elif self.solver.has_word(word):
            self.lbl_live_status.config(text=f"⚠️ Kata '{word.upper()}' sudah ada di kamus", fg="#fab387")
        else:
            self.lbl_live_status.config(text=f"✅ Siap ditambahkan ({len(word)} huruf, awalan '{word[:2].upper()}')", fg="#a6e3a1")

    def _do_add_word(self):
        if not hasattr(self, "entry_new_word"):
            return
        raw = self.entry_new_word.get().strip()
        success, msg = self.solver.add_word(raw)

        if success:
            word_clean = "".join([c for c in raw if c.isalpha()]).upper()
            self.lbl_add_feedback.config(text=f"✅ {msg}", fg="#a6e3a1")
            self.lbl_dict_total.config(text=f"{len(self.solver.words):,} kata")
            if hasattr(self, "lbl_dict_count") and self.lbl_dict_count.winfo_exists():
                self.lbl_dict_count.config(text=f"({len(self.solver.words):,} kata)")
            self.entry_new_word.delete(0, tk.END)
            self._on_new_word_keyrelease()
            self.show_toast(f"📚 Kata '{word_clean}' berhasil ditambahkan ke kamus!")
            if hasattr(self, "last_detected_word") and self.last_detected_word:
                self.update_results(self.last_detected_word)
            # Tutup popup seketika setelah berhasil menambahkan kata
            if hasattr(self, "add_word_win") and self.add_word_win and self.add_word_win.winfo_exists():
                self.add_word_win.destroy()
        else:
            self.lbl_add_feedback.config(text=f"❌ {msg}", fg="#f38ba8")

    def _open_dict_file(self):
        dict_path = os.path.abspath(self.solver.dictionary_path)
        try:
            os.startfile(dict_path)
        except Exception as e:
            self.show_toast(f"Gagal membuka file: {e}")

    # =========================================================================
    # FITUR PEMBARUAN OTOMATIS (UPDATER)
    # =========================================================================

    def _startup_update_check(self):
        """Memeriksa update di latar belakang saat aplikasi pertama kali dibuka"""
        try:
            target_br = self.config.get("updater_branch", "main")
            res = self.updater.check_for_updates(target_branch=target_br, timeout=10)
            if res.get("has_update"):
                self.root.after(0, self._on_update_found_badge, res)
                mode = self.config.get("updater_mode", "prompt")
                if mode == "auto":
                    self.root.after(0, lambda: self._execute_auto_update(res))
                elif mode == "prompt":
                    self.root.after(0, lambda: self.show_update_dialog(res))
        except Exception as e:
            print(f"[!] Update check error: {e}")

    def _on_update_found_badge(self, res):
        """Memperbarui tampilan tombol update di header jika ditemukan commit baru"""
        if hasattr(self, "btn_update") and self.btn_update.winfo_exists():
            cnt = res.get("behind_count", len(res.get("commits", [])))
            txt = f"🔀 Branch ({res.get('branch')})" if res.get("is_branch_switch") else f"🚀 Update ({cnt})"
            self.btn_update.config(
                text=txt,
                bg="#f9e2af",
                fg="#11111b",
                activebackground="#fab387"
            )

    def _execute_auto_update(self, res):
        """Menjalankan update secara otomatis di latar belakang dan memberi opsi restart"""
        target_br = res.get("branch", self.config.get("updater_branch", "main"))
        cnt = res.get("behind_count", len(res.get("commits", [])))
        self.show_toast(f"⏳ Sedang mengunduh update branch '{target_br}' otomatis...")

        def _worker():
            success, msg = self.updater.apply_update(target_branch=target_br)
            if success:
                self.root.after(0, lambda: self._on_auto_update_complete(cnt, target_br))
            else:
                self.root.after(0, lambda: self.show_toast(f"⚠️ Gagal auto-update: {msg}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_auto_update_complete(self, count, branch="main"):
        """Callback ketika auto-update selesai terpasang"""
        if hasattr(self, "btn_update") and self.btn_update.winfo_exists():
            self.btn_update.config(
                text="🔄 Restart",
                bg="#a6e3a1",
                fg="#11111b",
                command=self._restart_app_cleanly
            )
        self.show_toast(
            f"✅ Update '{branch}' terpasang! Klik 'Restart' di header.",
            undo_callback=self._restart_app_cleanly
        )

    def check_for_updates(self, target_branch=None, manual=False):
        """Memicu pengecekan pembaruan secara manual atau terjadwal"""
        branch_to_check = target_branch or self.config.get("updater_branch", "main")
        if manual:
            self.show_toast(f"🔄 Memeriksa branch '{branch_to_check}' di GitHub...")
            if hasattr(self, "btn_update") and self.btn_update.winfo_exists():
                self.btn_update.config(state=tk.DISABLED, text="⏳ Cek...")

        def _worker():
            try:
                res = self.updater.check_for_updates(target_branch=branch_to_check, timeout=12)
            except Exception as e:
                res = {
                    "success": False,
                    "error": str(e),
                    "has_update": False,
                    "branch": branch_to_check,
                    "commits": []
                }

            def _done():
                if hasattr(self, "btn_update") and self.btn_update.winfo_exists():
                    self.btn_update.config(state=tk.NORMAL)
                    if res.get("has_update"):
                        self._on_update_found_badge(res)
                    else:
                        self.btn_update.config(
                            text="🔄 Update",
                            bg="#313244",
                            fg=THEME["accent_neon"]
                        )

                if res.get("has_update") or manual:
                    self.show_update_dialog(res)

            self.root.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def show_update_dialog(self, res):
        """Membuka popup dialog pembaruan dengan daftar commit dan pengaturan mode"""
        if hasattr(self, "update_win") and self.update_win and self.update_win.winfo_exists():
            self.update_win.lift()
            self.update_win.focus_force()
            return

        has_update = res.get("has_update", False)
        commits = res.get("commits", [])
        behind_count = res.get("behind_count", len(commits))
        curr_commit = res.get("current_commit", self.updater.get_current_commit())
        branch = res.get("branch", self.config.get("updater_branch", "main"))
        current_branch = res.get("current_branch", self.updater.get_current_branch())
        is_branch_switch = res.get("is_branch_switch", (current_branch != branch))

        upd_title = "Beralih Branch" if (has_update and is_branch_switch) else ("Pembaruan Tersedia" if has_update else "Pengaturan & Info Pembaruan")
        self.update_win, _ = self._create_clean_toplevel(
            upd_title, 480, 620, min_w=440, min_h=520
        )

        sub_hdr = tk.Frame(self.update_win, bg=THEME["bg_card"], padx=14, pady=6)
        sub_hdr.pack(fill=tk.X)

        if has_update:
            status_text = f"Target: {branch}" if is_branch_switch else f"{behind_count} commit baru"
            tk.Label(
                sub_hdr,
                text="Pembaruan baru terdeteksi dari GitHub",
                font=("Segoe UI", 8),
                fg=THEME["text_secondary"],
                bg=THEME["bg_card"]
            ).pack(side=tk.LEFT)
            lbl_count = tk.Label(
                sub_hdr,
                text=status_text,
                font=("Segoe UI", 8, "bold"),
                fg=THEME["warning"],
                bg=THEME["bg_card"]
            )
            lbl_count.pack(side=tk.RIGHT)
        else:
            tk.Label(
                sub_hdr,
                text="Aplikasi sudah versi terbaru",
                font=("Segoe UI", 8),
                fg=THEME["text_secondary"],
                bg=THEME["bg_card"]
            ).pack(side=tk.LEFT)
            lbl_cur = tk.Label(
                sub_hdr,
                text=f"Commit #{curr_commit.get('hash', 'latest')}",
                font=("Segoe UI", 8, "bold"),
                fg=THEME["accent_neon"],
                bg=THEME["bg_card"]
            )
            lbl_cur.pack(side=tk.RIGHT)

        # 2. Branch Selector Bar
        branch_box = tk.Frame(self.update_win, bg=THEME["bg_card"], padx=12, pady=6, highlightthickness=1, highlightbackground=THEME["border"])
        branch_box.pack(fill=tk.X, padx=14, pady=(6, 2))

        lbl_br = tk.Label(
            branch_box,
            text="Branch:",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_primary"],
            bg=THEME["bg_card"]
        )
        lbl_br.pack(side=tk.LEFT, padx=(0, 4))

        available_branches = self.updater.get_available_branches()
        if branch not in available_branches:
            available_branches.append(branch)

        combo_branch = ttk.Combobox(
            branch_box,
            values=available_branches,
            state="readonly",
            width=12,
            font=("Segoe UI", 9)
        )
        combo_branch.set(branch)
        combo_branch.pack(side=tk.LEFT, padx=4)

        lbl_curr_local = tk.Label(
            branch_box,
            text=f"(Aktif: {current_branch})",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg=THEME["bg_card"]
        )
        lbl_curr_local.pack(side=tk.LEFT, padx=2)

        def _on_branch_change_action(event=None):
            selected_b = combo_branch.get().strip()
            if selected_b:
                self.config["updater_branch"] = selected_b
                save_config(self.config)
                self.update_win.destroy()
                self.check_for_updates(target_branch=selected_b, manual=True)

        combo_branch.bind("<<ComboboxSelected>>", _on_branch_change_action)

        ico_branch = render_vector_icon("refresh", size=12, color=THEME["bg_root"])
        btn_chk_br = tk.Button(
            branch_box,
            text=" Ganti Branch",
            image=ico_branch,
            compound="left",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["accent_neon"],
            fg=THEME["bg_root"],
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=2,
            cursor="hand2",
            command=_on_branch_change_action
        )
        btn_chk_br.image = ico_branch
        btn_chk_br.pack(side=tk.RIGHT)

        # 3. Status / Info Subtitle
        sub_frame = tk.Frame(self.update_win, bg=THEME["bg_card"], padx=14, pady=4)
        sub_frame.pack(fill=tk.X)

        if is_branch_switch:
            msg_sub = f"Anda sedang di branch '{current_branch}'. Memilih branch '{branch}' akan beralih ke branch tersebut."
            fg_sub = THEME["warning"]
        elif has_update:
            msg_sub = f"Branch '{branch}' di GitHub memiliki {behind_count} commit baru:"
            fg_sub = THEME["text_primary"]
        else:
            msg_sub = f"Aplikasi Anda sudah sinkron dengan branch '{branch}' di GitHub.\nCommit aktif: {curr_commit.get('message', '-')}"
            fg_sub = THEME["text_secondary"]

        lbl_sub = tk.Label(
            sub_frame,
            text=msg_sub,
            font=("Segoe UI", 9),
            fg=fg_sub,
            bg=THEME["bg_card"],
            wraplength=450,
            justify=tk.LEFT
        )
        lbl_sub.pack(anchor=tk.W)

        # 4. Commit List Container (Canvas + Scrollbar)
        if commits:
            list_container = tk.Frame(self.update_win, bg=THEME["bg_card"], bd=1, relief=tk.SOLID)
            list_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

            canvas = tk.Canvas(list_container, bg=THEME["bg_card"], highlightthickness=0)
            scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
            commit_scroll_frame = tk.Frame(canvas, bg=THEME["bg_card"])

            commit_scroll_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas_frame_id = canvas.create_window((0, 0), window=commit_scroll_frame, anchor="nw")

            def _on_canvas_configure(event):
                canvas.itemconfig(canvas_frame_id, width=event.width)
            canvas.bind("<Configure>", _on_canvas_configure)

            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            for c in commits:
                self._create_commit_card(commit_scroll_frame, c)

        elif not has_update:
            current_box = tk.Frame(self.update_win, bg=THEME["bg_card"], padx=12, pady=10, bd=1, relief=tk.SOLID)
            current_box.pack(fill=tk.X, padx=14, pady=8)

            tk.Label(
                current_box,
                text="INFORMASI COMMIT AKTIF",
                font=("Segoe UI", 8, "bold"),
                fg=THEME["accent_neon"],
                bg=THEME["bg_card"]
            ).pack(anchor=tk.W)

            tk.Label(
                current_box,
                text=f"Hash: {curr_commit.get('hash', '-')}",
                font=("Segoe UI", 9, "bold"),
                fg=THEME["warning"],
                bg=THEME["bg_card"]
            ).pack(anchor=tk.W, pady=(2, 0))

            tk.Label(
                current_box,
                text=f"Pesan: {curr_commit.get('message', '-')}",
                font=("Segoe UI", 9),
                fg=THEME["text_primary"],
                bg=THEME["bg_card"],
                wraplength=420,
                justify=tk.LEFT
            ).pack(anchor=tk.W, pady=(2, 0))

            tk.Label(
                current_box,
                text=f"Tanggal: {curr_commit.get('date', '-')} | Oleh: {curr_commit.get('author', '-')}",
                font=("Segoe UI", 8),
                fg=THEME["text_muted"],
                bg=THEME["bg_card"]
            ).pack(anchor=tk.W, pady=(4, 0))

        # 5. Mode Selection Frame (Dropdown Combobox)
        mode_box = tk.Frame(self.update_win, bg=THEME["bg_card"], padx=12, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        mode_box.pack(fill=tk.X, padx=14, pady=4)

        lbl_mode_title = tk.Label(
            mode_box,
            text="Mode Pemeriksaan Update:",
            font=("Segoe UI", 8, "bold"),
            fg=THEME["text_secondary"],
            bg=THEME["bg_card"]
        )
        lbl_mode_title.pack(side=tk.LEFT, padx=(0, 8))

        curr_mode = self.config.get("updater_mode", "prompt")
        mode_labels = {
            "prompt": "Tanya Setiap Ada Update (Prompt)",
            "auto": "Otomatis Update di Background (Auto)",
            "disabled": "Nonaktifkan Cek Otomatis (Disabled)"
        }
        reverse_mode_labels = {v: k for k, v in mode_labels.items()}

        combo_upd_mode = ttk.Combobox(
            mode_box,
            values=list(mode_labels.values()),
            state="readonly",
            font=("Segoe UI", 9)
        )
        combo_upd_mode.set(mode_labels.get(curr_mode, mode_labels["prompt"]))
        combo_upd_mode.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _on_mode_combo_change(event=None):
            chosen = combo_upd_mode.get()
            new_mode = reverse_mode_labels.get(chosen, "prompt")
            self.config["updater_mode"] = new_mode
            save_config(self.config)
            self.show_toast(f"Mode updater: {chosen}")

        combo_upd_mode.bind("<<ComboboxSelected>>", _on_mode_combo_change)

        # 6. Action Buttons Frame
        btn_frame = tk.Frame(self.update_win, bg=THEME["bg_card"], padx=14, pady=8)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        lbl_update_status = tk.Label(
            btn_frame,
            text="",
            font=("Segoe UI", 8),
            fg="#fab387",
            bg=THEME["bg_card"]
        )
        lbl_update_status.pack(fill=tk.X, pady=(0, 4))

        if has_update:
            btn_text = f" Beralih ke '{branch}' & Update" if is_branch_switch else " Perbarui Sekarang"
            ico_dl = render_vector_icon("cloud_download", size=14, color=THEME["bg_root"])
            btn_apply = tk.Button(
                btn_frame,
                text=btn_text,
                image=ico_dl,
                compound="left",
                font=("Segoe UI", 10, "bold"),
                bg=THEME["primary"],
                fg=THEME["bg_root"],
                activebackground=THEME["accent_neon"],
                relief=tk.FLAT,
                bd=0,
                padx=14,
                pady=5,
                cursor="hand2"
            )
            btn_apply.image = ico_dl
            btn_apply.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

            def _apply_click():
                btn_apply.config(state=tk.DISABLED, text="Memproses Pembaruan...")
                lbl_update_status.config(text=f"Sedang mengunduh / beralih ke '{branch}'...")

                def _apply_worker():
                    success, msg = self.updater.apply_update(target_branch=branch)

                    def _apply_done():
                        if success:
                            self.config["updater_branch"] = branch
                            save_config(self.config)
                            lbl_update_status.config(text=f"{msg}", fg=THEME["primary"])
                            restart = messagebox.askyesno(
                                "Pembaruan Berhasil",
                                f"{msg}\n\nApakah Anda ingin me-restart aplikasi sekarang agar perubahan aktif?",
                                parent=self.update_win
                            )
                            if restart:
                                self.update_win.destroy()
                                self._restart_app_cleanly()
                            else:
                                self.show_toast("✅ Pembaruan selesai. Silakan restart aplikasi nanti.")
                                self.update_win.destroy()
                        else:
                            btn_apply.config(state=tk.NORMAL, text="Coba Lagi")
                            lbl_update_status.config(text=f"Gagal: {msg}", fg=THEME["danger"])

                    self.root.after(0, _apply_done)

                threading.Thread(target=_apply_worker, daemon=True).start()

            btn_apply.config(command=_apply_click)

            btn_dismiss = tk.Button(
                btn_frame,
                text="Nanti Saja",
                font=("Segoe UI", 9),
                bg=THEME["border"],
                fg=THEME["text_primary"],
                activebackground=THEME["bg_hover"],
                relief=tk.FLAT,
                padx=12,
                pady=5,
                command=self.update_win.destroy
            )
            btn_dismiss.pack(side=tk.RIGHT)
        else:
            ico_ref = render_vector_icon("refresh", size=13, color=THEME["bg_root"])
            btn_recheck = tk.Button(
                btn_frame,
                text=" Periksa Lagi",
                image=ico_ref,
                compound="left",
                font=("Segoe UI", 9, "bold"),
                bg=THEME["primary"],
                fg=THEME["bg_root"],
                activebackground=THEME["accent_neon"],
                relief=tk.FLAT,
                bd=0,
                padx=12,
                pady=4,
                cursor="hand2",
                command=lambda: [self.update_win.destroy(), self.check_for_updates(target_branch=branch, manual=True)]
            )
            btn_recheck.image = ico_ref
            btn_recheck.pack(side=tk.LEFT)

            btn_close = tk.Button(
                btn_frame,
                text="Tutup",
                font=("Segoe UI", 9),
                bg=THEME["border"],
                fg=THEME["text_primary"],
                activebackground=THEME["bg_hover"],
                relief=tk.FLAT,
                bd=0,
                padx=14,
                pady=4,
                cursor="hand2",
                command=self.update_win.destroy
            )
            btn_close.pack(side=tk.RIGHT)

    def _create_commit_card(self, parent, commit_info):
        """Membuat tampilan kartu per-commit di daftar pembaruan"""
        card = tk.Frame(parent, bg=THEME["bg_card"], padx=10, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill=tk.X, padx=6, pady=4)

        hdr = tk.Frame(card, bg=THEME["bg_card"])
        hdr.pack(fill=tk.X)

        h_badge = tk.Label(
            hdr,
            text=f"#{commit_info['hash']}",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["bg_hover"],
            fg=THEME["accent_neon"],
            padx=5,
            pady=1
        )
        h_badge.pack(side=tk.LEFT)

        info_lbl = tk.Label(
            hdr,
            text=f"{commit_info['date']} • {commit_info['author']}",
            font=("Segoe UI", 8),
            fg=THEME["text_muted"],
            bg=THEME["bg_card"]
        )
        info_lbl.pack(side=tk.LEFT, padx=6)

        msg_lbl = tk.Label(
            card,
            text=commit_info['message'],
            font=("Segoe UI", 9, "bold"),
            fg=THEME["text_primary"],
            bg=THEME["bg_card"],
            wraplength=380,
            justify=tk.LEFT,
            anchor=tk.W
        )
        msg_lbl.pack(fill=tk.X, pady=(4, 0))

    def on_toggle_dev_mode(self):
        """Toggle mode pengembangan: menampilkan/menyembunyikan tombol ⚡ Restart di titlebar samping close"""
        new_val = self.dev_mode_var.get()
        self.config["dev_mode"] = new_val
        save_config(self.config)
        if new_val:
            # Tampilkan tombol restart di samping tombol close di titlebar
            if hasattr(self, "btn_title_close") and self.btn_title_close.winfo_exists():
                self.btn_restart.pack(side=tk.RIGHT, padx=(0, 2), pady=2, after=self.btn_title_close)
            else:
                self.btn_restart.pack(side=tk.RIGHT, padx=(0, 2), pady=2)
            self.show_toast("🛠️ Mode Development DIAKTIFKAN (Tombol ⚡ muncul di titlebar)")
        else:
            self.btn_restart.pack_forget()
            self.show_toast("🛠️ Mode Development DINONAKTIFKAN (Tombol ⚡ disembunyikan)")

    def _toggle_dev_mode_shortcut(self):
        """Toggle cepat mode development via keyboard Ctrl+Shift+D"""
        self.dev_mode_var.set(not self.dev_mode_var.get())
        self.on_toggle_dev_mode()

    def _restart_app_cleanly(self):
        """Menutup aplikasi secara bersih lalu memulai ulang"""
        try:
            self.on_close()
        except Exception:
            pass
        self.updater.restart_app()


    def open_dictionary_browser_window(self):
        """Membuka dialog popup UI Eksplorasi Kamus dengan manajemen Whitelist & Blocklist terintegrasi,
        filter sumber (KBBI, Contek, Keduanya), filter awalan/akhiran/mengandung, tag warna, kolom sortir,
        dan infinite scroll tanpa batasan entry."""
        if hasattr(self, "dict_win") and self.dict_win and self.dict_win.winfo_exists():
            self.dict_win.lift()
            self.dict_win.focus_force()
            if hasattr(self, "entry_dict_search") and self.entry_dict_search.winfo_exists():
                self.entry_dict_search.focus_set()
                self.entry_dict_search.select_range(0, tk.END)
            return

        self.dict_win, _ = self._create_clean_toplevel(
            "📖 Eksplorasi Kamus & Whitelist/Blocklist", 680, 740, min_w=560, min_h=600
        )

        # State management pencarian & sortir
        self._dict_all_results = []
        self._dict_loaded_count = 0
        self._dict_batch_size = 500
        self._dict_sort_col = "no"
        self._dict_sort_desc = False

        # Sub-Header
        sub_hdr = tk.Frame(self.dict_win, bg="#181825", padx=14, pady=6)
        sub_hdr.pack(fill=tk.X)

        tk.Label(
            sub_hdr,
            text="Pencarian kosakata aktif, filter sumber, tag, serta kelola Whitelist & Blocklist",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg="#181825"
        ).pack(side=tk.LEFT)

        self.btn_dict_load_all = tk.Button(
            sub_hdr,
            text="⚡ Muat Semua",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#f9e2af",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=6,
            pady=1,
            cursor="hand2",
            command=self._dict_load_all
        )

        self.lbl_dict_stats = tk.Label(
            sub_hdr,
            text=f"Total: {len(self.solver.words):,} kata",
            font=("Segoe UI", 8, "bold"),
            fg=THEME["accent_neon"],
            bg="#181825"
        )
        self.lbl_dict_stats.pack(side=tk.RIGHT)

        # Control Box (Mode, Sumber, & Search Entry)
        ctrl_box = tk.Frame(self.dict_win, bg="#1e1e2e", padx=14, pady=2)
        ctrl_box.pack(fill=tk.X)

        # Baris 1: Mode Pencarian
        mode_row = tk.Frame(ctrl_box, bg="#1e1e2e")
        mode_row.pack(fill=tk.X, pady=(0, 2))

        lbl_mode = tk.Label(mode_row, text="Mode Cari:", font=("Segoe UI", 8, "bold"), fg=THEME["text_primary"], bg="#1e1e2e")
        lbl_mode.pack(side=tk.LEFT, padx=(0, 6))

        self.dict_search_mode_var = tk.StringVar(value="prefix")

        for m_val, m_lbl in [("prefix", "🔤 Awalan (Prefix)"), ("suffix", "🎯 Akhiran (Suffix)"), ("contains", "🔍 Mengandung")]:
            rb = tk.Radiobutton(
                mode_row,
                text=m_lbl,
                variable=self.dict_search_mode_var,
                value=m_val,
                font=("Segoe UI", 8),
                fg=THEME["text_primary"],
                bg="#1e1e2e",
                activebackground="#1e1e2e",
                activeforeground="#f5e0dc",
                selectcolor="#313244",
                command=self._dict_refresh_search
            )
            rb.pack(side=tk.LEFT, padx=4)

        # Baris 2: Filter Sumber Kamus (Semua, KBBI Saja, Contek Saja, KBBI + Contek)
        source_row = tk.Frame(ctrl_box, bg="#1e1e2e")
        source_row.pack(fill=tk.X, pady=(0, 3))

        lbl_src = tk.Label(source_row, text="Sumber:", font=("Segoe UI", 8, "bold"), fg=THEME["text_primary"], bg="#1e1e2e")
        lbl_src.pack(side=tk.LEFT, padx=(0, 16))

        self.dict_source_filter_var = tk.StringVar(value="all")

        for s_val, s_lbl in [
            ("all", "🌐 Semua"),
            ("kbbi_only", "📚 KBBI Saja"),
            ("contek_only", "🎮 Contek Saja"),
            ("both", "✨ KBBI + Contek (Dua-duanya)")
        ]:
            rb = tk.Radiobutton(
                source_row,
                text=s_lbl,
                variable=self.dict_source_filter_var,
                value=s_val,
                font=("Segoe UI", 8),
                fg=THEME["text_primary"],
                bg="#1e1e2e",
                activebackground="#1e1e2e",
                activeforeground="#f5e0dc",
                selectcolor="#313244",
                command=self._dict_refresh_search
            )
            rb.pack(side=tk.LEFT, padx=4)

        # Baris 3: Input Pencarian
        search_box = tk.Frame(ctrl_box, bg="#313244", padx=6, pady=2)
        search_box.pack(fill=tk.X, pady=(2, 4))

        lbl_s_icon = tk.Label(search_box, text="🔍", font=("Segoe UI", 10), fg=THEME["text_secondary"], bg="#313244")
        lbl_s_icon.pack(side=tk.LEFT, padx=(2, 6))

        btn_clear = tk.Button(
            search_box,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#f38ba8",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            bd=0,
            padx=4,
            cursor="hand2",
            command=lambda: [self.dict_search_var.set(""), self._dict_refresh_search()]
        )
        btn_clear.pack(side=tk.RIGHT)

        self.dict_search_var = tk.StringVar()
        self.entry_dict_search = tk.Entry(
            search_box,
            textvariable=self.dict_search_var,
            font=("Segoe UI", 11, "bold"),
            bg="#313244",
            fg=THEME["text_primary"],
            insertbackground="white",
            relief=tk.FLAT
        )
        self.entry_dict_search.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_dict_search.focus_set()
        self.dict_search_var.trace_add("write", lambda *args: self._dict_refresh_search())
        self.entry_dict_search.bind("<Return>", lambda e: self._dict_refresh_search())

        # Baris 4: Tag Multi-Select Filter Box
        self.dict_selected_tags = set()
        self.dict_tag_buttons = {}

        tag_box = tk.LabelFrame(
            ctrl_box,
            text=" 🏷️ Filter Tag & Status (Klik untuk memilih/menggabungkan filter) ",
            font=("Segoe UI", 8, "bold"),
            fg="#cba6f7",
            bg="#181825",
            padx=8,
            pady=4
        )
        tag_box.pack(fill=tk.X, pady=(2, 2))

        self.dict_tag_container = tk.Frame(tag_box, bg="#181825")
        self.dict_tag_container.pack(fill=tk.X)
        self._dict_render_tag_chips()

        # Treeview Hasil Pencarian
        list_frame = tk.Frame(self.dict_win, bg="#1e1e2e", padx=14, pady=4)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Style Treeview bertema Dark Catppuccin dengan dukungan background warna baris
        style = ttk.Style(self.dict_win)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "Dict.Treeview",
            background="#1e1e2e",
            foreground="#cdd6f4",
            fieldbackground="#1e1e2e",
            borderwidth=0,
            font=("Segoe UI", 9)
        )
        style.configure(
            "Dict.Treeview.Heading",
            background="#313244",
            foreground="#cdd6f4",
            relief="flat",
            font=("Segoe UI", 9, "bold")
        )
        style.map(
            "Dict.Treeview.Heading",
            background=[("active", "#45475a")],
            foreground=[("active", "#f5e0dc")]
        )
        style.map(
            "Dict.Treeview",
            background=[("selected", "#45475a")],
            foreground=[("selected", "#ffffff")]
        )

        self.dict_tree_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.dict_tree = ttk.Treeview(
            list_frame,
            columns=("no", "word", "len", "tags", "source"),
            show="headings",
            style="Dict.Treeview",
            yscrollcommand=self._on_dict_tree_scroll,
            selectmode="extended"
        )
        self.dict_tree_scroll.config(command=self.dict_tree.yview)

        # Header kolom dengan fitur sortir saat diklik
        self.dict_tree.heading("no", text="#", command=lambda: self._dict_sort_by("no"))
        self.dict_tree.heading("word", text="Kata", command=lambda: self._dict_sort_by("word"))
        self.dict_tree.heading("len", text="Panjang", command=lambda: self._dict_sort_by("len"))
        self.dict_tree.heading("tags", text="Tag / Akhiran", command=lambda: self._dict_sort_by("tags"))
        self.dict_tree.heading("source", text="Sumber", command=lambda: self._dict_sort_by("source"))

        self.dict_tree.column("no", width=45, anchor="center")
        self.dict_tree.column("word", width=175, anchor="w")
        self.dict_tree.column("len", width=70, anchor="center")
        self.dict_tree.column("tags", width=125, anchor="center")
        self.dict_tree.column("source", width=135, anchor="center")

        # Konfigurasi pewarnaan baris: FONT TETAP PUTIH/TERANG BERSIH (#cdd6f4), warna HANYA pada background baris status
        self.dict_tree.tag_configure("status_whitelist", background="#2a3824", foreground="#cdd6f4")
        self.dict_tree.tag_configure("status_blocklist", background="#3d2028", foreground="#cdd6f4")
        self.dict_tree.tag_configure("row_even", background="#1e1e2e", foreground="#cdd6f4")
        self.dict_tree.tag_configure("row_odd", background="#181825", foreground="#cdd6f4")

        self.dict_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.dict_tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.dict_tree.bind("<Double-Button-1>", lambda e: self._dict_copy_selected())
        self.dict_tree.bind("<Button-3>", self._dict_show_context_menu)
        self.dict_tree.bind("<MouseWheel>", self._on_dict_mousewheel)

        # Footer Action Bar (Integrasi Whitelist, Blocklist, & Operasi Kamus)
        footer = tk.Frame(self.dict_win, bg="#181825", padx=12, pady=6)
        footer.pack(fill=tk.X)

        btn_cp = tk.Button(
            footer,
            text="📋 Salin",
            font=("Segoe UI", 8, "bold"),
            bg="#89b4fa",
            fg="#11111b",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._dict_copy_selected
        )
        btn_cp.pack(side=tk.LEFT, padx=(0, 4))

        btn_wl = tk.Button(
            footer,
            text="⭐ Whitelist",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#f9e2af",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._dict_toggle_whitelist
        )
        btn_wl.pack(side=tk.LEFT, padx=3)

        btn_bl = tk.Button(
            footer,
            text="🚫 Blocklist",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#f38ba8",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._dict_toggle_blacklist
        )
        btn_bl.pack(side=tk.LEFT, padx=3)

        btn_add = tk.Button(
            footer,
            text="➕ Tambah",
            font=("Segoe UI", 8),
            bg="#313244",
            fg="#a6e3a1",
            activebackground=THEME["bg_hover"],
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.open_add_word_dialog
        )
        btn_add.pack(side=tk.LEFT, padx=3)

        btn_open_bl = tk.Button(
            footer,
            text="📂 blacklist.txt",
            font=("Segoe UI", 8),
            bg="#181825",
            fg="#6c7086",
            activeforeground="#f38ba8",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: os.startfile(self.solver.blacklist_path)
        )
        btn_open_bl.pack(side=tk.RIGHT, padx=4)

        btn_open_wl = tk.Button(
            footer,
            text="📂 whitelist.txt",
            font=("Segoe UI", 8),
            bg="#181825",
            fg="#6c7086",
            activeforeground="#f9e2af",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: os.startfile(self.solver.whitelist_path)
        )
        btn_open_wl.pack(side=tk.RIGHT, padx=4)

        # Trigger search awal
        self._dict_refresh_search()

    def _dict_render_tag_chips(self):
        """Merender tombol tag chip filter dengan wrapping baris adaptif dan counter Whitelist/Blocklist"""
        if not hasattr(self, "dict_tag_container") or not self.dict_tag_container.winfo_exists():
            return

        for w in self.dict_tag_container.winfo_children():
            w.destroy()

        self.dict_tag_buttons.clear()

        tag_items = []
        seen = set()

        # Custom endings
        for cat in self.config.get("custom_trap_endings", []):
            sfx = cat.get("suffix", "").upper()
            if sfx and sfx not in seen:
                seen.add(sfx)
                tag_items.append((sfx, cat.get("color", "#cba6f7")))

        # Built-in trap letters
        for ch in ["X", "Z", "Q", "V", "J", "W", "F"]:
            if ch not in seen:
                seen.add(ch)
                tag_items.append((ch, "#fab387" if ch == "X" else "#f9e2af"))

        # Special Whitelist & Blocklist dengan jumlah kata
        wl_cnt = len(self.solver.whitelisted_words)
        bl_cnt = len(self.solver.blacklisted_words)
        tag_items.append((f"⭐ WHITELIST ({wl_cnt})", "#f9e2af"))
        tag_items.append((f"🚫 BLOCKLIST ({bl_cnt})", "#f38ba8"))

        current_row = tk.Frame(self.dict_tag_container, bg="#181825")
        current_row.pack(fill=tk.X, pady=(0, 2))

        btn_all = tk.Button(
            current_row,
            text="Semua Tag",
            font=("Segoe UI", 8, "bold"),
            bg="#45475a",
            fg=THEME["text_primary"],
            activebackground="#585b70",
            relief=tk.FLAT,
            padx=6,
            pady=1,
            cursor="hand2",
            command=self._dict_clear_tags
        )
        btn_all.pack(side=tk.LEFT, padx=(0, 4), pady=1)

        avail_w = 620
        cur_row_w = 75

        for tag_display, color in tag_items:
            # Identifikasi tag canonical
            if "WHITELIST" in tag_display:
                canon_tag = "WHITELIST"
            elif "BLOCKLIST" in tag_display:
                canon_tag = "BLOCKLIST"
            else:
                canon_tag = tag_display

            approx_w = max(24, len(tag_display) * 7 + 12) + 4
            if cur_row_w + approx_w > avail_w and cur_row_w > 80:
                current_row = tk.Frame(self.dict_tag_container, bg="#181825")
                current_row.pack(fill=tk.X, pady=(0, 2))
                cur_row_w = 0

            is_sel = canon_tag in self.dict_selected_tags
            btn = tk.Button(
                current_row,
                text=tag_display,
                font=("Segoe UI", 8, "bold"),
                bg=color if is_sel else "#313244",
                fg="#11111b" if is_sel else "#a6adc8",
                activebackground="#f5e0dc" if is_sel else "#45475a",
                relief=tk.FLAT,
                bd=0,
                padx=5,
                pady=1,
                cursor="hand2",
                command=lambda t=canon_tag: self._dict_toggle_tag(t)
            )
            btn.pack(side=tk.LEFT, padx=2, pady=1)
            self.dict_tag_buttons[canon_tag] = (btn, color)
            cur_row_w += approx_w

    def _dict_toggle_tag(self, tag_name):
        """Toggle status terpilih dari chip tag filter (multi-select)"""
        if tag_name in self.dict_selected_tags:
            self.dict_selected_tags.remove(tag_name)
        else:
            self.dict_selected_tags.add(tag_name)

        for tn, (btn, col) in self.dict_tag_buttons.items():
            if tn in self.dict_selected_tags:
                btn.config(bg=col, fg="#11111b", activebackground="#f5e0dc", activeforeground="#11111b")
            else:
                btn.config(bg="#313244", fg=THEME["text_secondary"], activebackground=THEME["bg_hover"], activeforeground="#cdd6f4")

        self._dict_refresh_search()

    def _dict_clear_tags(self):
        """Mereset seluruh filter tag (menampilkan semua kata)"""
        self.dict_selected_tags.clear()
        for tn, (btn, col) in self.dict_tag_buttons.items():
            btn.config(bg="#313244", fg=THEME["text_secondary"], activebackground=THEME["bg_hover"], activeforeground="#cdd6f4")
        self._dict_refresh_search()

    def _dict_refresh_search(self):
        """Menjalankan query pencarian kata ke solver dan merender batch awal"""
        if not hasattr(self, "dict_tree") or not self.dict_tree.winfo_exists():
            return

        query = self.dict_search_var.get().strip() if hasattr(self, "dict_search_var") else ""
        sm = self.dict_search_mode_var.get() if hasattr(self, "dict_search_mode_var") else "prefix"
        sf = self.dict_source_filter_var.get() if hasattr(self, "dict_source_filter_var") else "all"
        tags = list(self.dict_selected_tags) if hasattr(self, "dict_selected_tags") else []

        results, total = self.solver.search_dictionary(
            query=query,
            search_type=sm,
            selected_tags=tags,
            source_filter=sf,
            limit=None
        )

        self._dict_all_results = results
        self._dict_apply_sort_to_results()
        self._dict_render_initial_batch()

    def _dict_apply_sort_to_results(self):
        """Mengurutkan _dict_all_results berdasarkan kolom dan arah sortir aktif"""
        col = self._dict_sort_col
        desc = self._dict_sort_desc

        if col == "no":
            self._dict_all_results.sort(key=lambda r: r.get("original_index", 0), reverse=desc)
        elif col == "word":
            self._dict_all_results.sort(key=lambda r: r.get("word", ""), reverse=desc)
        elif col == "len":
            self._dict_all_results.sort(key=lambda r: (r.get("length", 0), r.get("word", "")), reverse=desc)
        elif col == "tags":
            self._dict_all_results.sort(key=lambda r: (r.get("tag", ""), r.get("word", "")), reverse=desc)
        elif col == "source":
            self._dict_all_results.sort(key=lambda r: (r.get("status", ""), r.get("word", "")), reverse=desc)

    def _dict_sort_by(self, col):
        """Mengubah kolom sortir atau membalik arah urutan (Ascending / Descending)"""
        if self._dict_sort_col == col:
            self._dict_sort_desc = not self._dict_sort_desc
        else:
            self._dict_sort_col = col
            self._dict_sort_desc = False

        cols = {
            "no": "#",
            "word": "Kata",
            "len": "Panjang",
            "tags": "Tag / Akhiran",
            "source": "Sumber"
        }
        for c_id, c_title in cols.items():
            if c_id == col:
                arrow = " ▼" if self._dict_sort_desc else " ▲"
                self.dict_tree.heading(c_id, text=f"{c_title}{arrow}")
            else:
                self.dict_tree.heading(c_id, text=c_title)

        self._dict_apply_sort_to_results()
        self._dict_render_initial_batch()

    def _dict_render_initial_batch(self):
        """Merender batch pertama (500 item) ke Treeview dan mereset posisi scroll"""
        if not hasattr(self, "dict_tree") or not self.dict_tree.winfo_exists():
            return
        for item in self.dict_tree.get_children():
            self.dict_tree.delete(item)

        self._dict_loaded_count = 0
        self._dict_load_next_batch(count=self._dict_batch_size)
        try:
            self.dict_tree.yview_moveto(0.0)
        except Exception:
            pass

    def _dict_load_next_batch(self, count=None):
        """Memuat batch item berikutnya ke Treeview secara halus tanpa freeze"""
        if not hasattr(self, "dict_tree") or not self.dict_tree.winfo_exists():
            return
        batch = count or self._dict_batch_size
        start = self._dict_loaded_count
        end = min(start + batch, len(self._dict_all_results))
        if start >= end:
            self._dict_update_stats_label()
            return

        chunk = self._dict_all_results[start:end]
        for idx_row, r in enumerate(chunk, start=start):
            # Warna HANYA diterapkan pada background status (bukan font agar tetap bersih dan jelas dibaca)
            if r.get("is_blacklisted"):
                row_tag = "status_blocklist"
            elif r.get("is_whitelisted"):
                row_tag = "status_whitelist"
            else:
                row_tag = "row_even" if idx_row % 2 == 0 else "row_odd"

            self.dict_tree.insert(
                "",
                "end",
                values=(
                    r.get("original_index", 0),
                    r.get("word", ""),
                    r.get("length", 0),
                    r.get("tag", ""),
                    r.get("status", "")
                ),
                tags=(row_tag,)
            )
        self._dict_loaded_count = end
        self._dict_update_stats_label()

    def _dict_load_all(self):
        """Memuat seluruh sisa entri ke Treeview secara langsung"""
        if not hasattr(self, "dict_tree") or not self.dict_tree.winfo_exists():
            return
        remaining = len(self._dict_all_results) - self._dict_loaded_count
        if remaining > 0:
            self._dict_load_next_batch(count=remaining)
            self.show_toast(f"⚡ Seluruh {len(self._dict_all_results):,} kata telah dimuat!")

    def _on_dict_tree_scroll(self, first, last):
        """Callback scrollbar untuk memicu infinite scroll saat mendekati bawah"""
        if hasattr(self, "dict_tree_scroll") and self.dict_tree_scroll.winfo_exists():
            self.dict_tree_scroll.set(first, last)
        if float(last) >= 0.85 and self._dict_loaded_count < len(self._dict_all_results):
            self.root.after_idle(self._dict_load_next_batch)

    def _on_dict_mousewheel(self, event):
        """Deteksi mousewheel ke bawah untuk memuat batch berikutnya jika di ujung"""
        if event.delta < 0 and self._dict_loaded_count < len(self._dict_all_results):
            try:
                _, last = self.dict_tree.yview()
                if last >= 0.85:
                    self.root.after_idle(self._dict_load_next_batch)
            except Exception:
                pass

    def _dict_update_stats_label(self):
        """Memperbarui teks statistik dan menampilkan tombol 'Muat Semua' jika relevan"""
        if not hasattr(self, "lbl_dict_stats") or not self.lbl_dict_stats.winfo_exists():
            return
        total = len(self._dict_all_results)
        loaded = self._dict_loaded_count
        if total == 0:
            self.lbl_dict_stats.config(text="Tidak ada kata cocok")
            if hasattr(self, "btn_dict_load_all") and self.btn_dict_load_all.winfo_exists():
                self.btn_dict_load_all.pack_forget()
        elif loaded < total:
            self.lbl_dict_stats.config(text=f"Menampilkan {loaded:,} dari {total:,} kata (Scroll ke bawah)")
            if hasattr(self, "btn_dict_load_all") and self.btn_dict_load_all.winfo_exists():
                self.btn_dict_load_all.config(text=f"⚡ Muat Semua ({total:,})")
                self.btn_dict_load_all.pack(side=tk.RIGHT, padx=4)
        else:
            self.lbl_dict_stats.config(text=f"Menampilkan seluruh {total:,} kata")
            if hasattr(self, "btn_dict_load_all") and self.btn_dict_load_all.winfo_exists():
                self.btn_dict_load_all.pack_forget()

    def _dict_get_target_words(self):
        """Mengambil daftar kata yang ditargetkan: dari seleksi Treeview atau kolom pencarian"""
        words = []
        if hasattr(self, "dict_tree") and self.dict_tree.winfo_exists():
            selected = self.dict_tree.selection()
            for s in selected:
                item = self.dict_tree.item(s)
                val = item.get("values", [])
                if len(val) >= 2:
                    words.append(str(val[1]).strip().lower())
        if not words:
            q = self.dict_search_var.get().strip().lower() if hasattr(self, "dict_search_var") else ""
            if q and q.isalpha() and len(q) >= 2:
                words.append(q)
        return words

    def _dict_copy_selected(self):
        """Menyalin kata yang sedang dipilih di Treeview ke clipboard"""
        words = self._dict_get_target_words()
        if not words:
            self.show_toast("⚠️ Pilih kata terlebih dahulu untuk disalin")
            return
        clip_text = "\n".join(words)
        self.root.clipboard_clear()
        self.root.clipboard_append(clip_text)
        if len(words) == 1:
            self.show_toast(f"📋 '{words[0].upper()}' disalin ke clipboard!")
        else:
            self.show_toast(f"📋 {len(words)} kata disalin ke clipboard!")

    def _dict_toggle_whitelist(self):
        """Menambah atau membatalkan status Whitelist pada kata terpilih atau input search"""
        words = self._dict_get_target_words()
        if not words:
            self.show_toast("⚠️ Pilih kata dari tabel atau ketik di kolom cari")
            return

        added = []
        removed = []
        for w in words:
            if self.solver.is_whitelisted(w):
                self.solver.unwhitelist_word(w)
                removed.append(w.upper())
            else:
                self.solver.whitelist_word(w)
                added.append(w.upper())

        if added and not removed:
            self.show_toast(f"⭐ {', '.join(added)} ditambahkan ke Whitelist!")
        elif removed and not added:
            self.show_toast(f"↩️ {', '.join(removed)} dihapus dari Whitelist!")
        else:
            self.show_toast(f"⭐ Whitelist diperbarui ({len(added)} ditambah, {len(removed)} dihapus)")

        self._dict_render_tag_chips()
        self._dict_refresh_search()

    def _dict_toggle_blacklist(self):
        """Menambah atau memulihkan status Blocklist pada kata terpilih atau input search"""
        words = self._dict_get_target_words()
        if not words:
            self.show_toast("⚠️ Pilih kata dari tabel atau ketik di kolom cari")
            return

        added = []
        restored = []
        for w in words:
            if w in self.solver.blacklisted_words:
                self.solver.unblacklist_word(w)
                restored.append(w.upper())
            else:
                self.solver.blacklist_word(w)
                added.append(w.upper())

        if added and not restored:
            self.show_toast(f"🚫 {', '.join(added)} dimasukkan ke Blocklist!")
        elif restored and not added:
            self.show_toast(f"✅ {', '.join(restored)} dipulihkan dari Blocklist!")
        else:
            self.show_toast(f"🚫 Blocklist diperbarui ({len(added)} diblokir, {len(restored)} dipulihkan)")

        self._dict_render_tag_chips()
        self._dict_refresh_search()

    def _dict_show_context_menu(self, event):
        """Menampilkan menu popup klik kanan dengan opsi dinamis Whitelist & Blocklist"""
        if not hasattr(self, "dict_tree") or not self.dict_tree.winfo_exists():
            return
        row_id = self.dict_tree.identify_row(event.y)
        if row_id:
            if row_id not in self.dict_tree.selection():
                self.dict_tree.selection_set(row_id)

            words = self._dict_get_target_words()
            menu = tk.Menu(self.dict_win, tearoff=0, bg="#181825", fg=THEME["text_primary"], activebackground=THEME["bg_hover"], activeforeground="#f5e0dc")
            menu.add_command(label="📋 Salin Kata", command=self._dict_copy_selected)
            menu.add_separator()

            if words:
                w0 = words[0]
                is_wl = self.solver.is_whitelisted(w0)
                is_bl = w0 in self.solver.blacklisted_words

                lbl_wl = f"⭐ Hapus '{w0.upper()}' dari Whitelist" if is_wl else f"⭐ Tambah '{w0.upper()}' ke Whitelist"
                lbl_bl = f"✅ Pulihkan '{w0.upper()}' dari Blocklist" if is_bl else f"🚫 Masukkan '{w0.upper()}' ke Blocklist"

                menu.add_command(label=lbl_wl, command=self._dict_toggle_whitelist)
                menu.add_command(label=lbl_bl, command=self._dict_toggle_blacklist)
                menu.add_separator()

            menu.add_command(label="➕ Tambah Kata Baru ke Kamus...", command=self.open_add_word_dialog)
            menu.add_separator()
            menu.add_command(label="📂 Buka whitelist.txt", command=lambda: os.startfile(self.solver.whitelist_path))
            menu.add_command(label="📂 Buka blacklist.txt", command=lambda: os.startfile(self.solver.blacklist_path))

            menu.tk_popup(event.x_root, event.y_root)

    def save_config_debounced(self, delay_ms=400):
        """Menjadwalkan penyimpanan konfigurasi ke disk dengan debounce untuk menghindari disk I/O lag"""
        if hasattr(self, "_save_config_timer") and self._save_config_timer:
            try:
                self.root.after_cancel(self._save_config_timer)
            except Exception:
                pass
        self._save_config_timer = self.root.after(delay_ms, self.flush_config_save)

    def flush_config_save(self):
        """Menyimpan konfigurasi secara langsung ke disk dan mereset timer"""
        self._save_config_timer = None
        save_config(self.config)

    def _sync_tags_and_solver(self, skip_ui_rebuild=False):
        """Menyinkronkan konfigurasi tag ke solver dan menandai dirty flag / render UI secara efisien"""
        categories = self.config.get("custom_trap_endings", [])
        self.save_config_debounced()
        self.solver.set_custom_endings(categories)

        is_live_active = hasattr(self, "top_tab_strip") and getattr(self.top_tab_strip, "active_tab", "") == "live"
        if is_live_active:
            self._render_custom_category_quick_bar()
            if hasattr(self, "last_detected_word") and self.last_detected_word:
                self.update_results(self.last_detected_word)
        else:
            self._dirty_quick_bar = True
            self._dirty_live_results = True

        if not skip_ui_rebuild:
            self._render_custom_category_items()

    def on_close(self):
        try:
            self.config["window_geometry"] = self.root.geometry()
            self.flush_config_save()
        except Exception:
            pass
        try:
            import keyboard
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self.is_scanning = False
        self.root.destroy()

def main():
    root = tk.Tk()
    app = SambungKataApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
