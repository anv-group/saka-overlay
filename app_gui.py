import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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

class SambungKataApp:
    def __init__(self, root):
        self.root = root
        self.root.title("⚔️ Sambung Kata Assistant")

        self.config = load_config()

        # Posisi & ukuran window default: di sebelah kanan layar, minimal sesuai ui-size-min.png (438x1075)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        target_w = 440
        # Sesuaikan tinggi agar pas di layar pengguna mendekati 1075px dari ui-size-min.png
        target_h = max(720, min(1075, screen_h - 40))
        target_x = max(0, screen_w - target_w - 15)
        target_y = 15
        default_geom = f"{target_w}x{target_h}+{target_x}+{target_y}"

        saved_geom = self.config.get("window_geometry")
        if saved_geom:
            try:
                self.root.geometry(saved_geom)
            except Exception:
                self.root.geometry(default_geom)
        else:
            self.root.geometry(default_geom)

        # Lebar minimal 438px sesuai batas minimal visual ui-size-min.png
        self.root.minsize(438, 650)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e2e")

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

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_ui()

        # Pengecekan pembaruan otomatis di latar belakang saat startup
        if self.config.get("auto_check_update_on_startup", True) and self.config.get("updater_mode", "prompt") != "disabled":
            self.root.after(1200, lambda: threading.Thread(target=self._startup_update_check, daemon=True).start())

    def _build_ui(self):
        # 1. Baris Atas Compact: Tombol Aksi Utama (Mulai, Tambah Kata, Restart, Mode Santai, Settings ⚙️)
        top_bar = tk.Frame(self.root, bg="#181825", padx=8, pady=4)
        top_bar.pack(fill=tk.X)

        self.btn_toggle = tk.Button(
            top_bar,
            text="▶️ Mulai",
            font=("Segoe UI", 9, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground="#94e2d5",
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.toggle_scan
        )
        self.btn_toggle.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_add_word = tk.Button(
            top_bar,
            text="➕ Kamus",
            font=("Segoe UI", 9, "bold"),
            bg="#89b4fa",
            fg="#11111b",
            activebackground="#b4befe",
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self.open_add_word_dialog
        )
        self.btn_add_word.pack(side=tk.LEFT, padx=3)

        self.btn_restart = tk.Button(
            top_bar,
            text="⚡ Restart",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#fab387",
            activebackground="#45475a",
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._restart_app_cleanly
        )
        self.btn_restart.pack(side=tk.LEFT, padx=3)

        # Mode Santai Toggle
        self.mode_santai_var = tk.BooleanVar(value=self.config.get("mode_santai", False))
        self.chk_santai = tk.Checkbutton(
            top_bar,
            text="🌿 Santai",
            variable=self.mode_santai_var,
            command=self.on_toggle_mode_santai,
            font=("Segoe UI", 9, "bold"),
            fg="#a6e3a1",
            bg="#181825",
            selectcolor="#313244",
            activebackground="#181825",
            activeforeground="#a6e3a1"
        )
        self.chk_santai.pack(side=tk.LEFT, padx=(6, 2))

        # Status Dot & Settings Menu (⚙️) di ujung kanan
        self.status_lbl = tk.Label(
            top_bar,
            text="●",
            font=("Segoe UI", 10),
            fg="#6c7086",
            bg="#181825"
        )
        self.status_lbl.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_settings = tk.Button(
            top_bar,
            text="⚙️",
            font=("Segoe UI", 9),
            bg="#181825",
            fg="#a6adc8",
            activebackground="#313244",
            activeforeground="#cdd6f4",
            relief=tk.FLAT,
            padx=5,
            pady=2,
            cursor="hand2",
            command=self._open_settings_menu
        )
        self.btn_settings.pack(side=tk.RIGHT, padx=(0, 2))

        # 2. Baris Awalan OCR (Fixed Width di Kiri) & Pencarian Manual (Realtime + Clear Permanen di Kanan)
        search_prefix_row = tk.Frame(self.root, bg="#1e1e2e", padx=8, pady=3)
        search_prefix_row.pack(fill=tk.X)

        # Box Hasil Deteksi Awalan OCR (Teks Besar & Lebar Terkunci agar tidak menggeser elemen lain)
        self.prefix_badge_frame = tk.Frame(
            search_prefix_row,
            bg="#181825",
            width=70,
            height=32,
            relief=tk.FLAT
        )
        self.prefix_badge_frame.pack_propagate(False)
        self.prefix_badge_frame.pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_prefix_display = tk.Label(
            self.prefix_badge_frame,
            text="-",
            font=("Segoe UI", 15, "bold"),
            fg="#f9e2af",
            bg="#181825"
        )
        self.lbl_prefix_display.pack(fill=tk.BOTH, expand=True)

        self.lbl_conf = tk.Label(
            self.prefix_badge_frame,
            text="",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg="#181825"
        )

        # Alias kompatibilitas
        self.lbl_detected = self.lbl_prefix_display
        self.lbl_target = self.lbl_prefix_display

        # Kontainer Input Pencarian Manual (Mengisi sisa ruang ke kanan)
        search_box = tk.Frame(search_prefix_row, bg="#313244", padx=6, pady=2)
        search_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lbl_icon = tk.Label(search_box, text="🔍", font=("Segoe UI", 9), fg="#a6adc8", bg="#313244")
        lbl_icon.pack(side=tk.LEFT, padx=(0, 4))

        # Tombol Clear '✕' dipack ke RIGHT terlebih dahulu agar menempel permanen di sisi kanan
        self.btn_clear_search = tk.Button(
            search_box,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            bg="#313244",
            fg="#f38ba8",
            activebackground="#45475a",
            activeforeground="#f38ba8",
            relief=tk.FLAT,
            bd=0,
            padx=4,
            pady=0,
            cursor="hand2",
            command=self.clear_manual_search
        )
        self.btn_clear_search.pack(side=tk.RIGHT)

        self.search_var = tk.StringVar()
        self.entry_manual = tk.Entry(
            search_box,
            textvariable=self.search_var,
            font=("Segoe UI", 11, "bold"),
            bg="#313244",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            relief=tk.FLAT
        )
        self.entry_manual.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_var.trace_add("write", self._on_search_text_changed)

        # 3. Baris Horizontal Quick Toggle Kategori Custom
        self.custom_cats_bar = tk.Frame(self.root, bg="#1e1e2e")
        self.custom_cats_bar.pack(fill=tk.X, padx=8, pady=(1, 2))
        self._render_custom_category_quick_bar()

        # 4. Toast Frame & Warning Keyakinan Rendah
        self.warning_frame = tk.Frame(self.root, bg="#313244", padx=6, pady=2)
        self.lbl_warning_msg = tk.Label(
            self.warning_frame,
            text="⚠️ Keyakinan Rendah!",
            font=("Segoe UI", 8, "bold"),
            fg="#fab387",
            bg="#313244"
        )
        self.lbl_warning_msg.pack(side=tk.LEFT)
        self.alt_container = tk.Frame(self.warning_frame, bg="#313244")
        self.alt_container.pack(side=tk.LEFT, padx=4)

        self.toast_frame = tk.Frame(self.root, bg="#1e1e2e")
        self.toast_frame.pack(fill=tk.X, padx=8, pady=1)

        self.lbl_toast = tk.Label(
            self.toast_frame,
            text="",
            font=("Segoe UI", 8, "italic"),
            fg="#a6e3a1",
            bg="#1e1e2e"
        )
        self.lbl_toast.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_undo = tk.Button(
            self.toast_frame,
            text="↩️ Batalkan",
            font=("Segoe UI", 8, "bold"),
            bg="#fab387",
            fg="#11111b",
            activebackground="#f9e2af",
            activeforeground="#11111b",
            relief=tk.FLAT,
            padx=6,
            pady=0,
            cursor="hand2"
        )
        self._toast_timer = None

        # 5. Daftar Rekomendasi Jawaban (Memenuhi sisa seluruh window)
        is_santai_init = self.config.get("mode_santai", False)
        recom_title = " Rekomendasi Kata (🌿 Mode Santai) " if is_santai_init else " Rekomendasi Kata (Klik untuk Salin) "
        recom_fg = "#a6e3a1" if is_santai_init else "#f38ba8"
        self.recom_frame = tk.LabelFrame(
            self.root,
            text=recom_title,
            font=("Segoe UI", 9, "bold"),
            fg=recom_fg,
            bg="#1e1e2e",
            padx=4,
            pady=4
        )
        self.recom_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # Canvas & Scrollbar untuk daftar kata
        self.canvas = tk.Canvas(self.recom_frame, bg="#181825", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.recom_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#181825")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Aktifkan scroll roda mouse (MouseWheel) mulus di area rekomendasi kata
        self.recom_frame.bind("<Enter>", self._bind_mousewheel)
        self.recom_frame.bind("<Leave>", self._unbind_mousewheel)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
        self.scrollable_frame.bind("<Enter>", self._bind_mousewheel)
        self.scrollable_frame.bind("<Leave>", self._unbind_mousewheel)

        # Widget Pool untuk kartu kata
        self.word_card_pool = []
        self.lbl_empty_results = tk.Label(
            self.scrollable_frame,
            text="",
            font=("Segoe UI", 9, "italic"),
            fg="#f38ba8",
            bg="#181825",
            pady=10
        )

        # Objek pendukung & konfigurasi kompatibilitas
        self.auto_copy_var = tk.BooleanVar(value=self.config.get("auto_copy_top_word", False))
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

        # Global Hotkey menggunakan keyboard library
        try:
            import keyboard
            keyboard.add_hotkey(self.report_hotkey.lower(), lambda: self.root.after(0, self.on_report_kurang_tepat))
            keyboard.add_hotkey(self.gameplay_calib_hotkey.lower(), lambda: self.root.after(0, self.on_capture_gameplay_kalibrasi))
        except Exception as e:
            print(f"[!] Warning: Gagal mendaftarkan global hotkey: {e}")

        self._update_koreksi_badge()

    def _open_settings_menu(self):
        """Membuka dropdown menu pengaturan tambahan tanpa memenuhi layar game"""
        menu = tk.Menu(self.root, tearoff=0, bg="#181825", fg="#cdd6f4", activebackground="#313244", activeforeground="#f5e0dc")
        menu.add_command(label="🎯 Set Area ROI Awalan", command=self.open_region_selector)
        menu.add_command(label="👁️ Tes Tangkap Screenshot Area", command=self.preview_selected_area)
        menu.add_separator()
        menu.add_command(label="🚫 Buka Blocklist Kata", command=self.open_blacklist_window)
        menu.add_command(label="📝 Pendataan Koreksi (F2)", command=self.open_koreksi_window)
        menu.add_command(label="🏷️ Kelola Kategori Custom", command=self.open_custom_categories_window)
        menu.add_separator()
        menu.add_command(label="🎮 Set Area Gameplay (F3)", command=self.open_gameplay_region_selector)
        menu.add_command(label="📋 Log Gameplay", command=self.open_gameplay_history_window)
        menu.add_command(label="📸 Ambil Snapshot Kalibrasi (F3)", command=self.on_capture_gameplay_kalibrasi)
        menu.add_separator()
        menu.add_checkbutton(label="📋 Auto-copy sisa kata", variable=self.auto_copy_var, command=self.on_toggle_autocopy)
        menu.add_command(label="⚡ Kecepatan Scan...", command=self.cycle_scan_speed)
        menu.add_command(label="🔄 Cek Update Git...", command=lambda: self.check_for_updates(manual=True))

        try:
            x = self.btn_settings.winfo_rootx()
            y = self.btn_settings.winfo_rooty() + self.btn_settings.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

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
                    slot["frame"].pack_forget()

    def clear_manual_search(self):
        """Membersihkan kotak pencarian manual dan kembali ke OCR"""
        if hasattr(self, "search_var"):
            self.search_var.set("")
        if hasattr(self, "entry_manual") and self.entry_manual.winfo_exists():
            self.entry_manual.focus_set()

    def on_toggle_autocopy(self):
        val = self.auto_copy_var.get()
        self.config["auto_copy_top_word"] = val
        save_config(self.config)
        if val:
            self.show_toast("📋 Auto-copy sisa kata AKTIF (Tinggal Ctrl+V di Roblox)")
        else:
            self.show_toast("Auto-copy sisa kata dinonaktifkan")

    def on_toggle_mode_santai(self):
        is_santai = self.mode_santai_var.get()
        self.config["mode_santai"] = is_santai
        save_config(self.config)

        if is_santai:
            self.show_toast("🌿 Mode Santai AKTIF (Huruf X, Q, F dikecualikan)")
            self.recom_frame.config(text=" Rekomendasi Kata (🌿 Mode Santai) ", fg="#a6e3a1")
        else:
            self.show_toast("⚔️ Mode Normal AKTIF (Jebakan X/Z/Q/F aktif)")
            self.recom_frame.config(text=" Rekomendasi Kata (Klik untuk Salin) ", fg="#f38ba8")

        if self.last_detected_word:
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
            self.btn_toggle.config(text="⏹️ Stop", bg="#f38ba8")
            self.status_lbl.config(text="●", fg="#a6e3a1")
            self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
            self.scan_thread.start()
        else:
            self.is_scanning = False
            self.btn_toggle.config(text="▶️ Mulai", bg="#a6e3a1")
            self.status_lbl.config(text="●", fg="#6c7086")

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

        self.gameplay_history_win = tk.Toplevel(self.root)
        self.gameplay_history_win.title("🎮 Riwayat Auto-Index Gameplay")
        self.gameplay_history_win.geometry("560x490")
        self.gameplay_history_win.minsize(500, 400)
        self.gameplay_history_win.attributes("-topmost", True)
        self.gameplay_history_win.configure(bg="#1e1e2e")
        self.gameplay_history_win.bind("<Escape>", lambda e: self.gameplay_history_win.destroy())

        try:
            x = self.root.winfo_x() + 20
            y = self.root.winfo_y() + 20
            self.gameplay_history_win.geometry(f"560x490+{x}+{y}")
        except Exception:
            pass

        # Header Frame
        hdr = tk.Frame(self.gameplay_history_win, bg="#181825", padx=12, pady=10)
        hdr.pack(fill=tk.X)

        title_lbl = tk.Label(
            hdr,
            text="🎮 Riwayat Auto-Index Gameplay (File Terpisah)",
            font=("Segoe UI", 12, "bold"),
            fg="#a6e3a1",
            bg="#181825"
        )
        title_lbl.pack(side=tk.LEFT)

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
            fg="#a6adc8",
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
            fg="#cdd6f4",
            relief=tk.FLAT,
            command=self._clear_gameplay_history
        )
        btn_clear.pack(side=tk.LEFT)

        btn_close = tk.Button(
            bbar,
            text="Tutup",
            font=("Segoe UI", 9),
            bg="#313244",
            fg="#cdd6f4",
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

        self.classifier_win = tk.Toplevel(self.root)
        self.classifier_win.title("🎮 Klasifikasi Momen Gameplay")
        self.classifier_win.geometry("540x670")
        self.classifier_win.minsize(480, 580)
        self.classifier_win.attributes("-topmost", True)
        self.classifier_win.configure(bg="#1e1e2e")

        try:
            x = self.root.winfo_x() + 25
            y = self.root.winfo_y() + 15
            self.classifier_win.geometry(f"540x670+{x}+{y}")
        except Exception:
            pass

        self._classifier_unclassified_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "deteksi-gameplay", "unclassified"
        )
        os.makedirs(self._classifier_unclassified_dir, exist_ok=True)

        self._classifier_items = []
        self._classifier_current_idx = 0
        self._classifier_tk_img = None

        # Header Frame
        hdr = tk.Frame(self.classifier_win, bg="#181825", padx=12, pady=10)
        hdr.pack(fill=tk.X)

        title_lbl = tk.Label(
            hdr,
            text="🎮 Klasifikasi Momen Gameplay",
            font=("Segoe UI", 12, "bold"),
            fg="#89b4fa",
            bg="#181825"
        )
        title_lbl.pack(side=tk.LEFT)

        self.btn_classifier_extract = tk.Button(
            hdr,
            text="🎬 Ekstrak Video",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#a6e3a1",
            activebackground="#45475a",
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
            fg="#cdd6f4",
            activebackground="#45475a",
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
            activebackground="#45475a",
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._classifier_clear_all_unclassified
        )
        btn_clear_all.pack(side=tk.RIGHT)

        # Counter & Info bar
        bar_info = tk.Frame(self.classifier_win, bg="#24273a", padx=10, pady=6)
        bar_info.pack(fill=tk.X)

        self.lbl_class_counter = tk.Label(
            bar_info,
            text="Memuat sampel...",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#24273a"
        )
        self.lbl_class_counter.pack(side=tk.LEFT)

        self.lbl_class_trigger = tk.Label(
            bar_info,
            text="",
            font=("Segoe UI", 8, "italic"),
            fg="#fab387",
            bg="#24273a"
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
            fg="#cdd6f4",
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
            activebackground="#45475a",
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
            fg="#a6adc8",
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
            activebackground="#eba0ac",
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
            activebackground="#94e2d5",
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
            fg="#cdd6f4",
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
            fg="#cdd6f4",
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
            self.lbl_class_counter.config(text="Tidak ada sampel tersisa (0 / 0)", fg="#a6adc8")
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
            fg="#cdd6f4"
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
                        fg="#cdd6f4",
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
            self.lbl_prefix_display.config(text=prefix_clean, fg="#89dceb")
            self.lbl_conf.config(text="Manual", fg="#89dceb")
            self.warning_frame.pack_forget()

        if not prefix_clean:
            return

        is_santai = self.mode_santai_var.get()
        # Muat lebih banyak kata sekaligus (limit=30 kata)
        results = self.solver.cari_jawaban(prefix_clean, limit=30, mode_santai=is_santai)

        if not results:
            for slot in self.word_card_pool:
                slot["frame"].pack_forget()
            msg_not_found = f"Tidak ditemukan kata berawalan '{prefix_clean}' (Mode Santai: tanpa X/Q/F)." if is_santai else f"Tidak ditemukan kata di kamus berawalan '{prefix_clean}'."
            self.lbl_empty_results.config(text=msg_not_found)
            self.lbl_empty_results.pack(fill=tk.X)
            return

        self.lbl_empty_results.pack_forget()

        # Auto copy sisa kata pertama jika fitur aktif
        if self.auto_copy_var.get() and results:
            top_word = results[0]["kata"]
            top_upper = top_word.upper()
            sisa_top = top_upper[len(prefix_clean):] if top_upper.startswith(prefix_clean) else top_upper
            self.copy_to_clipboard(sisa_top, full_word=top_word, show_toast_flag=False)
            self.show_toast(f"Otomatis tersalin sisa kata: '{sisa_top}' (dari '{top_upper}')")

        # Tampilkan kata menggunakan widget pool berkinerja tinggi (tanpa create/destroy berulang)
        prefix_upper = prefix_clean.upper()
        for idx, item in enumerate(results):
            if idx >= len(self.word_card_pool):
                self._alloc_card_slot()
            self._update_card_slot(self.word_card_pool[idx], item, prefix_upper)

        # Sembunyikan slot kartu yang tidak terpakai
        for idx in range(len(results), len(self.word_card_pool)):
            self.word_card_pool[idx]["frame"].pack_forget()

    def _on_mousewheel(self, event):
        """Scroll daftar rekomendasi kata menggunakan roda mouse secara mulus"""
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists():
            return
        if event.delta:
            # Di Windows: event.delta positif = scroll up, negatif = scroll down
            step = int(-1 * (event.delta / 120))
            self.canvas.yview_scroll(step, "units")
        elif event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def _bind_mousewheel(self, event=None):
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def _alloc_card_slot(self):
        card = tk.Frame(self.scrollable_frame, bg="#1e1e2e", padx=6, pady=2, relief=tk.FLAT)
        lbl_kata = tk.Label(card, text="", font=("Segoe UI", 10, "bold"), fg="#cdd6f4", bg="#1e1e2e")
        lbl_kata.pack(side=tk.LEFT, padx=3)

        btn_del = tk.Button(
            card,
            text="❌",
            font=("Segoe UI", 8),
            bg="#1e1e2e",
            fg="#f38ba8",
            activebackground="#45475a",
            activeforeground="#f38ba8",
            relief=tk.FLAT,
            bd=0,
            padx=3,
            pady=0,
            cursor="hand2"
        )
        btn_del.pack(side=tk.RIGHT, padx=(2, 0))

        lbl_badge = tk.Label(
            card,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg="#11111b",
            bg="#a6e3a1",
            padx=5,
            pady=0
        )
        lbl_badge.pack(side=tk.RIGHT, padx=3)

        # Aktifkan scroll roda mouse saat kursor melayang di atas kartu kata
        card.bind("<Enter>", self._bind_mousewheel)
        card.bind("<Leave>", self._unbind_mousewheel)
        lbl_kata.bind("<Enter>", self._bind_mousewheel)
        lbl_kata.bind("<Leave>", self._unbind_mousewheel)
        lbl_badge.bind("<Enter>", self._bind_mousewheel)
        lbl_badge.bind("<Leave>", self._unbind_mousewheel)

        slot = {
            "frame": card,
            "lbl_kata": lbl_kata,
            "btn_del": btn_del,
            "lbl_badge": lbl_badge
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
            card_bg = "#313244"
            badge_bg = item.get("color", "#cba6f7")
            badge_fg = "#11111b"
            b_name = item.get("badge_name") or f"AKHIRAN {item.get('suffix', '')}"
            badge_text = f"🔥 {b_name}"
        elif tipe == "JEBAKAN_X":
            card_bg = "#45475a"
            badge_bg = "#f38ba8"
            badge_fg = "#11111b"
            badge_text = "💥 JEBAKAN X"
        elif tipe == "JEBAKAN_SULIT":
            card_bg = "#313244"
            badge_bg = "#fab387"
            badge_fg = "#11111b"
            badge_text = f"⚡ {deskripsi}"
        else:
            card_bg = "#1e1e2e"
            badge_bg = "#a6e3a1"
            badge_fg = "#11111b"
            badge_text = "🌿 SANTAI" if deskripsi == "Kata Santai" else "🛡️ NORMAL"

        card = slot["frame"]
        lbl_kata = slot["lbl_kata"]
        btn_del = slot["btn_del"]
        lbl_badge = slot["lbl_badge"]

        card.config(bg=card_bg)
        lbl_kata.config(text=kata_upper, bg=card_bg)
        lbl_badge.config(text=badge_text, bg=badge_bg, fg=badge_fg)
        btn_del.config(bg=card_bg, command=lambda k=kata: self.on_blacklist_word(k))

        handler = lambda e, s=sisa, w=kata: self.copy_to_clipboard(s, full_word=w)
        card.bind("<Button-1>", handler)
        lbl_kata.bind("<Button-1>", handler)
        lbl_badge.bind("<Button-1>", handler)

        card.pack(fill=tk.X, padx=3, pady=2)

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

        self.blacklist_win = tk.Toplevel(self.root)
        self.blacklist_win.title("🚫 Kelola Blocklist Kata")
        self.blacklist_win.geometry("400x520")
        self.blacklist_win.minsize(360, 440)
        self.blacklist_win.attributes("-topmost", True)
        self.blacklist_win.configure(bg="#1e1e2e")
        self.blacklist_win.bind("<Escape>", lambda e: self.blacklist_win.destroy())

        # Posisikan relatif terhadap window utama
        try:
            x = self.root.winfo_x() + 25
            y = self.root.winfo_y() + 25
            self.blacklist_win.geometry(f"400x520+{x}+{y}")
        except Exception:
            pass

        # Header Frame
        hdr = tk.Frame(self.blacklist_win, bg="#181825", padx=12, pady=10)
        hdr.pack(fill=tk.X)

        title_lbl = tk.Label(
            hdr,
            text="🚫 Daftar Blocklist Kata",
            font=("Segoe UI", 12, "bold"),
            fg="#f38ba8",
            bg="#181825"
        )
        title_lbl.pack(side=tk.LEFT)

        self.lbl_bl_count = tk.Label(
            hdr,
            text="0 kata",
            font=("Segoe UI", 10, "bold"),
            fg="#a6adc8",
            bg="#181825"
        )
        self.lbl_bl_count.pack(side=tk.RIGHT)

        sub_lbl = tk.Label(
            self.blacklist_win,
            text="Kata di bawah ditolak oleh Roblox dan tidak akan disarankan bot.",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#1e1e2e",
            padx=12,
            pady=4
        )
        sub_lbl.pack(anchor=tk.W)

        # Bar Tambah Kata Baru
        add_frame = tk.Frame(self.blacklist_win, bg="#1e1e2e", padx=12, pady=4)
        add_frame.pack(fill=tk.X)

        lbl_tambah = tk.Label(
            add_frame,
            text="Tambah Kata:",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e"
        )
        lbl_tambah.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_bl_add = tk.Entry(
            add_frame,
            font=("Segoe UI", 9),
            bg="#313244",
            fg="#cdd6f4",
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
            activebackground="#eba0ac",
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
            fg="#a6adc8",
            bg="#1e1e2e"
        )
        lbl_filter.pack(side=tk.LEFT, padx=(0, 4))

        self.entry_bl_filter = tk.Entry(
            search_frame,
            font=("Segoe UI", 9),
            bg="#313244",
            fg="#cdd6f4",
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
            fg="#cdd6f4",
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
            activebackground="#94e2d5",
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
            activebackground="#b4befe",
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
            fg="#cdd6f4",
            activebackground="#45475a",
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

    def open_custom_categories_window(self):
        """Membuka dialog popup untuk mengelola kategori & akhiran kustom (Custom Traps)"""
        if hasattr(self, "custom_cats_win") and self.custom_cats_win and self.custom_cats_win.winfo_exists():
            self.custom_cats_win.lift()
            self.custom_cats_win.focus_force()
            if hasattr(self, "entry_cat_sfx") and self.entry_cat_sfx.winfo_exists():
                self.entry_cat_sfx.focus_set()
                self.entry_cat_sfx.select_range(0, tk.END)
            return

        self.custom_cats_win = tk.Toplevel(self.root)
        self.custom_cats_win.title("🏷️ Kategori & Akhiran Kustom (Custom Traps)")
        self.custom_cats_win.geometry("460x580")
        self.custom_cats_win.minsize(420, 500)
        self.custom_cats_win.attributes("-topmost", True)
        self.custom_cats_win.configure(bg="#1e1e2e")
        self.custom_cats_win.bind("<Escape>", lambda e: self.custom_cats_win.destroy())

        # Header
        hdr = tk.Frame(self.custom_cats_win, bg="#181825", padx=14, pady=10)
        hdr.pack(fill=tk.X)

        title_lbl = tk.Label(
            hdr,
            text="🏷️ Kategori Akhiran Kustom",
            font=("Segoe UI", 12, "bold"),
            fg="#cba6f7",
            bg="#181825"
        )
        title_lbl.pack(side=tk.LEFT)

        subtitle_lbl = tk.Label(
            self.custom_cats_win,
            text="Kata berakhiran ini diprioritaskan paling atas (Super Jebakan, di atas X)\nuntuk menjebak lawan dengan awalan yang hampir mustahil disambung.",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg="#1e1e2e",
            justify=tk.LEFT,
            padx=14,
            pady=6
        )
        subtitle_lbl.pack(fill=tk.X)

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
        add_box.pack(fill=tk.X, padx=14, pady=6)

        row1 = tk.Frame(add_box, bg="#181825")
        row1.pack(fill=tk.X, pady=2)

        lbl_sfx = tk.Label(row1, text="Akhiran:", font=("Segoe UI", 9, "bold"), fg="#cdd6f4", bg="#181825", width=8, anchor="w")
        lbl_sfx.pack(side=tk.LEFT)

        self.entry_cat_sfx = tk.Entry(row1, font=("Segoe UI", 10, "bold"), bg="#313244", fg="#f5e0dc", insertbackground="white", width=9)
        self.entry_cat_sfx.pack(side=tk.LEFT, padx=4)
        self.entry_cat_sfx.focus_set()
        self.entry_cat_sfx.bind("<Return>", lambda e: self._on_add_custom_category())

        lbl_name = tk.Label(row1, text="Nama:", font=("Segoe UI", 9), fg="#cdd6f4", bg="#181825", width=6, anchor="w")
        lbl_name.pack(side=tk.LEFT, padx=(6, 0))

        self.entry_cat_name = tk.Entry(row1, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4", insertbackground="white")
        self.entry_cat_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_cat_name.bind("<Return>", lambda e: self._on_add_custom_category())

        btn_add = tk.Button(
            add_box,
            text="➕ Tambah Kategori Akhiran",
            font=("Segoe UI", 9, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground="#94e2d5",
            relief=tk.FLAT,
            command=self._on_add_custom_category,
            pady=3
        )
        btn_add.pack(fill=tk.X, pady=(6, 2))

        # List Area Container
        lbl_list_title = tk.Label(
            self.custom_cats_win,
            text="Daftar Kategori Akhiran:",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e",
            padx=14,
            anchor="w"
        )
        lbl_list_title.pack(fill=tk.X, pady=(6, 2))

        # Scrollable list container
        list_container = tk.Frame(self.custom_cats_win, bg="#181825")
        list_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        canvas = tk.Canvas(list_container, bg="#181825", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        self.custom_cats_inner = tk.Frame(canvas, bg="#181825")

        self.custom_cats_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.custom_cats_inner, anchor="nw", width=410)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Render item list
        self._render_custom_category_items()

        # Footer Actions
        footer = tk.Frame(self.custom_cats_win, bg="#1e1e2e", padx=14, pady=8)
        footer.pack(fill=tk.X)

        btn_reset = tk.Button(
            footer,
            text="↩️ Reset Default (NS & NGK)",
            font=("Segoe UI", 9),
            bg="#45475a",
            fg="#cdd6f4",
            activebackground="#585b70",
            relief=tk.FLAT,
            command=self._on_reset_custom_categories,
            padx=8,
            pady=4
        )
        btn_reset.pack(side=tk.LEFT)

        btn_close = tk.Button(
            footer,
            text="Tutup",
            font=("Segoe UI", 9),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            relief=tk.FLAT,
            command=self.custom_cats_win.destroy,
            padx=12,
            pady=4
        )
        btn_close.pack(side=tk.RIGHT)

    def _render_custom_category_quick_bar(self):
        """Merender tombol toggle horizontal untuk tiap kategori custom di atas Rekomendasi Kata"""
        if not hasattr(self, "custom_cats_bar") or not self.custom_cats_bar.winfo_exists():
            return

        for w in self.custom_cats_bar.winfo_children():
            w.destroy()

        categories = self.config.get("custom_trap_endings", [])

        # Label Header baris
        lbl_title = tk.Label(
            self.custom_cats_bar,
            text="🏷️ Custom:",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#1e1e2e"
        )
        lbl_title.pack(side=tk.LEFT, padx=(0, 6))

        # Tombol Kelola '⚙️' di ujung kanan horizontal
        btn_manage = tk.Button(
            self.custom_cats_bar,
            text="⚙️ Kelola",
            font=("Segoe UI", 8),
            bg="#181825",
            fg="#a6adc8",
            activebackground="#313244",
            activeforeground="#cdd6f4",
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self.open_custom_categories_window
        )
        btn_manage.pack(side=tk.RIGHT, padx=(4, 0))

        if not categories:
            lbl_none = tk.Label(
                self.custom_cats_bar,
                text="(Belum ada kategori)",
                font=("Segoe UI", 8, "italic"),
                fg="#6c7086",
                bg="#1e1e2e"
            )
            lbl_none.pack(side=tk.LEFT, padx=(0, 4))
            return

        for idx, cat in enumerate(categories):
            sfx = cat.get("suffix", "").upper()
            enabled = cat.get("enabled", True)
            col = cat.get("color", "#cba6f7")

            if enabled:
                btn_text = f"✓ {sfx}"
                btn_bg = col
                btn_fg = "#11111b"
                btn_abg = "#f5e0dc"
            else:
                btn_text = f"✕ {sfx}"
                btn_bg = "#313244"
                btn_fg = "#6c7086"
                btn_abg = "#45475a"

            btn = tk.Button(
                self.custom_cats_bar,
                text=btn_text,
                font=("Segoe UI", 8, "bold"),
                bg=btn_bg,
                fg=btn_fg,
                activebackground=btn_abg,
                activeforeground="#11111b" if enabled else "#cdd6f4",
                relief=tk.FLAT,
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda i=idx, cur=enabled: self._on_toggle_custom_category(i, not cur)
            )
            btn.pack(side=tk.LEFT, padx=3)

    def _render_custom_category_items(self):
        """Merender baris daftar kategori akhiran kustom di canvas"""
        if not hasattr(self, "custom_cats_inner") or not self.custom_cats_inner.winfo_exists():
            return

        for w in self.custom_cats_inner.winfo_children():
            w.destroy()

        categories = self.config.get("custom_trap_endings", [])
        if not categories:
            empty_lbl = tk.Label(
                self.custom_cats_inner,
                text="Belum ada kategori akhiran kustom.\nSilakan tambah di form atas (misal: NS atau NGK).",
                font=("Segoe UI", 9, "italic"),
                fg="#6c7086",
                bg="#181825",
                pady=20
            )
            empty_lbl.pack(fill=tk.X)
            return

        for idx, cat in enumerate(categories):
            sfx = cat.get("suffix", "").upper()
            name = cat.get("name") or f"Akhiran {sfx}"
            enabled = cat.get("enabled", True)
            color = cat.get("color", "#cba6f7")
            cnt = self.solver.count_words_by_suffix(sfx) if hasattr(self.solver, "count_words_by_suffix") else 0

            row = tk.Frame(self.custom_cats_inner, bg="#1e1e2e", padx=8, pady=6)
            row.pack(fill=tk.X, padx=4, pady=3)

            # Checkbox toggle
            var = tk.BooleanVar(value=enabled)
            cb = tk.Checkbutton(
                row,
                variable=var,
                bg="#1e1e2e",
                activebackground="#1e1e2e",
                selectcolor="#313244",
                command=lambda i=idx, v=var: self._on_toggle_custom_category(i, v.get())
            )
            cb.pack(side=tk.LEFT)

            # Badge Suffix
            badge = tk.Label(
                row,
                text=sfx,
                font=("Segoe UI", 9, "bold"),
                bg=color,
                fg="#11111b",
                padx=6,
                pady=1
            )
            badge.pack(side=tk.LEFT, padx=(2, 8))

            # Nama dan Info Kata
            info_frame = tk.Frame(row, bg="#1e1e2e")
            info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            lbl_name = tk.Label(
                info_frame,
                text=name,
                font=("Segoe UI", 9, "bold"),
                fg="#cdd6f4" if enabled else "#6c7086",
                bg="#1e1e2e",
                anchor="w"
            )
            lbl_name.pack(anchor="w")

            lbl_cnt = tk.Label(
                info_frame,
                text=f"{cnt} kata tersedia di kamus",
                font=("Segoe UI", 8),
                fg="#a6adc8" if enabled else "#585b70",
                bg="#1e1e2e",
                anchor="w"
            )
            lbl_cnt.pack(anchor="w")

            # Tombol Hapus
            btn_del = tk.Button(
                row,
                text="🗑️",
                font=("Segoe UI", 9),
                bg="#1e1e2e",
                fg="#f38ba8",
                activebackground="#313244",
                relief=tk.FLAT,
                cursor="hand2",
                command=lambda i=idx: self._on_delete_custom_category(i)
            )
            btn_del.pack(side=tk.RIGHT)

    def _on_add_custom_category(self):
        """Menambahkan kategori akhiran baru dari input"""
        if not hasattr(self, "entry_cat_sfx"):
            return
        raw_sfx = self.entry_cat_sfx.get().strip().upper()
        sfx = "".join(c for c in raw_sfx if c.isalpha())
        if not sfx:
            self.show_toast("Akhiran harus berupa huruf alfabet (misal: NS atau NGK)!")
            return

        raw_name = self.entry_cat_name.get().strip() if hasattr(self, "entry_cat_name") else ""
        name = raw_name if raw_name else f"Akhiran {sfx}"

        categories = self.config.get("custom_trap_endings", [])
        # Cek apakah sudah ada
        for c in categories:
            if c.get("suffix", "").upper() == sfx:
                self.show_toast(f"Kategori akhiran '{sfx}' sudah ada!")
                return

        palette = ["#cba6f7", "#f5c2e7", "#89dceb", "#f9e2af", "#a6e3a1", "#fab387", "#94e2d5"]
        chosen_color = palette[len(categories) % len(palette)]

        categories.append({
            "suffix": sfx,
            "name": name,
            "enabled": True,
            "color": chosen_color
        })

        self.config["custom_trap_endings"] = categories
        save_config(self.config)
        self.solver.set_custom_endings(categories)

        self.entry_cat_sfx.delete(0, tk.END)
        self.entry_cat_name.delete(0, tk.END)
        self.entry_cat_sfx.focus_set()

        self._render_custom_category_items()
        self._render_custom_category_quick_bar()
        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)

        cnt = self.solver.count_words_by_suffix(sfx)
        self.show_toast(f"✅ Kategori '{name}' ({sfx}) ditambahkan ({cnt} kata)!")

    def _on_toggle_custom_category(self, idx, new_val):
        """Toggle aktif/nonaktif kategori akhiran"""
        categories = self.config.get("custom_trap_endings", [])
        if 0 <= idx < len(categories):
            categories[idx]["enabled"] = bool(new_val)
            self.config["custom_trap_endings"] = categories
            save_config(self.config)
            self.solver.set_custom_endings(categories)
            self._render_custom_category_items()
            self._render_custom_category_quick_bar()
            if hasattr(self, "last_detected_word") and self.last_detected_word:
                self.update_results(self.last_detected_word)
            status_str = "diaktifkan" if new_val else "dinonaktifkan"
            self.show_toast(f"Kategori '{categories[idx].get('name')}' {status_str}")

    def _on_delete_custom_category(self, idx):
        """Menghapus kategori akhiran kustom"""
        categories = self.config.get("custom_trap_endings", [])
        if 0 <= idx < len(categories):
            removed = categories.pop(idx)
            self.config["custom_trap_endings"] = categories
            save_config(self.config)
            self.solver.set_custom_endings(categories)
            self._render_custom_category_items()
            self._render_custom_category_quick_bar()
            if hasattr(self, "last_detected_word") and self.last_detected_word:
                self.update_results(self.last_detected_word)
            self.show_toast(f"🗑️ Kategori '{removed.get('name')}' dihapus")

    def _on_reset_custom_categories(self):
        """Mereset daftar kategori akhiran ke default NS & NGK"""
        categories = [
            {"suffix": "NS", "name": "Akhiran NS", "enabled": True, "color": "#cba6f7"},
            {"suffix": "NGK", "name": "Akhiran NGK", "enabled": True, "color": "#f5c2e7"}
        ]
        self.config["custom_trap_endings"] = categories
        save_config(self.config)
        self.solver.set_custom_endings(categories)
        self._render_custom_category_items()
        self._render_custom_category_quick_bar()
        if hasattr(self, "last_detected_word") and self.last_detected_word:
            self.update_results(self.last_detected_word)
        self.show_toast("↩️ Kategori akhiran direset ke default (NS & NGK)")

    def copy_to_clipboard(self, sisa_text, full_word=None, show_toast_flag=True):
        self.root.clipboard_clear()
        self.root.clipboard_append(sisa_text.lower())
        self.root.update()
        if show_toast_flag:
            info = f" (dari '{full_word.upper()}')" if full_word else ""
            self.show_toast(f"Tersalin sisa kata: '{sisa_text.upper()}'{info} - Tinggal Ctrl+V di Roblox!")

    def show_toast(self, message, undo_callback=None):
        self.lbl_toast.config(text=message)
        if undo_callback:
            self.btn_undo.config(command=undo_callback)
            self.btn_undo.pack(side=tk.RIGHT, padx=4)
        else:
            self.btn_undo.pack_forget()

        if hasattr(self, "_toast_timer") and self._toast_timer:
            try:
                self.root.after_cancel(self._toast_timer)
            except Exception:
                pass

        self._toast_timer = self.root.after(4000, self._clear_toast)

    def _clear_toast(self):
        self.lbl_toast.config(text="")
        self.btn_undo.pack_forget()
        self._toast_timer = None

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
                    fg="#a6adc8",
                    activebackground="#45475a"
                )

    def open_koreksi_window(self):
        """Membuka jendela untuk mendata hasil deteksi yang tepat bagi sampel di kurang_tepat dan tidak_dikenali"""
        if hasattr(self, "koreksi_win") and self.koreksi_win and self.koreksi_win.winfo_exists():
            self.koreksi_win.lift()
            self.koreksi_win.focus_force()
            return

        self.koreksi_win = tk.Toplevel(self.root)
        self.koreksi_win.title("📝 Pendataan Koreksi Sampel")
        self.koreksi_win.geometry("480x620")
        self.koreksi_win.minsize(440, 540)
        self.koreksi_win.attributes("-topmost", True)
        self.koreksi_win.configure(bg="#1e1e2e")

        try:
            x = self.root.winfo_x() + 30
            y = self.root.winfo_y() + 20
            self.koreksi_win.geometry(f"480x620+{x}+{y}")
        except Exception:
            pass

        self._koreksi_items = []
        self._koreksi_current_idx = 0
        self._koreksi_only_uncorrected = tk.BooleanVar(value=True)
        self._koreksi_tk_img = None

        # Header Frame
        hdr = tk.Frame(self.koreksi_win, bg="#181825", padx=12, pady=10)
        hdr.pack(fill=tk.X)

        title_lbl = tk.Label(
            hdr,
            text="📝 Pendataan Koreksi Sampel",
            font=("Segoe UI", 12, "bold"),
            fg="#fab387",
            bg="#181825"
        )
        title_lbl.pack(side=tk.LEFT)

        btn_folder = tk.Button(
            hdr,
            text="📂 Buka Folder",
            font=("Segoe UI", 8),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            relief=tk.FLAT,
            padx=6,
            pady=2,
            command=self._koreksi_open_folder
        )
        btn_folder.pack(side=tk.RIGHT)

        # Sumber Selection Bar (Kurang Tepat vs Tidak Dikenali)
        source_frame = tk.Frame(self.koreksi_win, bg="#24273a", padx=10, pady=6)
        source_frame.pack(fill=tk.X)

        lbl_sumber = tk.Label(
            source_frame,
            text="📁 Sumber:",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#24273a"
        )
        lbl_sumber.pack(side=tk.LEFT, padx=(0, 4))

        count_kt, count_td = self._get_uncorrected_counts()
        initial_source = "tidak_dikenali" if (count_kt == 0 and count_td > 0) else "kurang_tepat"
        self._koreksi_source = tk.StringVar(value=initial_source)

        self.rb_kt = tk.Radiobutton(
            source_frame,
            text=f"🚩 Kurang Tepat ({count_kt})",
            variable=self._koreksi_source,
            value="kurang_tepat",
            font=("Segoe UI", 8, "bold"),
            fg="#eba0ac",
            bg="#24273a",
            selectcolor="#313244",
            activebackground="#24273a",
            activeforeground="#eba0ac",
            command=self._koreksi_reload_items
        )
        self.rb_kt.pack(side=tk.LEFT, padx=2)

        self.rb_td = tk.Radiobutton(
            source_frame,
            text=f"⚠️ Tidak Dikenali ({count_td})",
            variable=self._koreksi_source,
            value="tidak_dikenali",
            font=("Segoe UI", 8, "bold"),
            fg="#fab387",
            bg="#24273a",
            selectcolor="#313244",
            activebackground="#24273a",
            activeforeground="#fab387",
            command=self._koreksi_reload_items
        )
        self.rb_td.pack(side=tk.LEFT, padx=2)

        self.rb_all = tk.Radiobutton(
            source_frame,
            text="Semua",
            variable=self._koreksi_source,
            value="all",
            font=("Segoe UI", 8),
            fg="#89b4fa",
            bg="#24273a",
            selectcolor="#313244",
            activebackground="#24273a",
            activeforeground="#89b4fa",
            command=self._koreksi_reload_items
        )
        self.rb_all.pack(side=tk.LEFT, padx=2)

        # Bar filter / opsi
        filter_bar = tk.Frame(self.koreksi_win, bg="#1e1e2e", padx=12, pady=4)
        filter_bar.pack(fill=tk.X)

        chk_filter = tk.Checkbutton(
            filter_bar,
            text="Hanya tampilkan yang belum dikoreksi",
            variable=self._koreksi_only_uncorrected,
            font=("Segoe UI", 9),
            fg="#bac2de",
            bg="#1e1e2e",
            selectcolor="#313244",
            activebackground="#1e1e2e",
            activeforeground="#cdd6f4",
            command=self._koreksi_reload_items
        )
        chk_filter.pack(side=tk.LEFT)

        self.lbl_koreksi_progress = tk.Label(
            filter_bar,
            text="- / -",
            font=("Segoe UI", 9, "bold"),
            fg="#89b4fa",
            bg="#1e1e2e"
        )
        self.lbl_koreksi_progress.pack(side=tk.RIGHT)

        # Image Display Container
        img_container = tk.Frame(self.koreksi_win, bg="#11111b", padx=8, pady=8, bd=1, relief=tk.SOLID)
        img_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        self.lbl_koreksi_img = tk.Label(
            img_container,
            text="Tidak ada gambar",
            font=("Segoe UI", 10, "italic"),
            fg="#6c7086",
            bg="#11111b"
        )
        self.lbl_koreksi_img.pack(expand=True)

        # Info Frame
        self.info_box = tk.Frame(self.koreksi_win, bg="#181825", padx=12, pady=6)
        self.info_box.pack(fill=tk.X, padx=12, pady=4)

        self.lbl_koreksi_fname = tk.Label(
            self.info_box,
            text="File: -",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#181825",
            anchor=tk.W
        )
        self.lbl_koreksi_fname.pack(fill=tk.X)

        self.lbl_koreksi_detail = tk.Label(
            self.info_box,
            text="Terdeteksi: - | Akurasi: -",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#181825",
            anchor=tk.W
        )
        self.lbl_koreksi_detail.pack(fill=tk.X)

        self.lbl_koreksi_status = tk.Label(
            self.info_box,
            text="Status: -",
            font=("Segoe UI", 8),
            fg="#fab387",
            bg="#181825",
            anchor=tk.W
        )
        self.lbl_koreksi_status.pack(fill=tk.X)

        # Input Frame Koreksi
        input_frame = tk.Frame(self.koreksi_win, bg="#313244", padx=12, pady=8)
        input_frame.pack(fill=tk.X, padx=12, pady=6)

        lbl_input_prompt = tk.Label(
            input_frame,
            text="✏️ Awalan yang Seharusnya (Benar):",
            font=("Segoe UI", 10, "bold"),
            fg="#fab387",
            bg="#313244"
        )
        lbl_input_prompt.pack(anchor=tk.W)

        action_row = tk.Frame(input_frame, bg="#313244")
        action_row.pack(fill=tk.X, pady=(4, 0))

        self.entry_koreksi_text = tk.Entry(
            action_row,
            font=("Segoe UI", 12, "bold"),
            bg="#181825",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            relief=tk.FLAT,
            justify=tk.CENTER
        )
        self.entry_koreksi_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=3)
        self.entry_koreksi_text.bind("<Return>", lambda e: self._koreksi_save_current())

        btn_save = tk.Button(
            action_row,
            text="💾 Simpan (Enter)",
            font=("Segoe UI", 9, "bold"),
            bg="#a6e3a1",
            fg="#11111b",
            activebackground="#94e2d5",
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._koreksi_save_current
        )
        btn_save.pack(side=tk.RIGHT)

        # Navigation & Bottom Bar
        nav_frame = tk.Frame(self.koreksi_win, bg="#1e1e2e", padx=12, pady=6)
        nav_frame.pack(fill=tk.X, side=tk.BOTTOM)

        btn_prev = tk.Button(
            nav_frame,
            text="◀️ Sebelumnya",
            font=("Segoe UI", 8),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            command=self._koreksi_prev
        )
        btn_prev.pack(side=tk.LEFT)

        btn_next = tk.Button(
            nav_frame,
            text="Berikutnya ▶️",
            font=("Segoe UI", 8),
            bg="#313244",
            fg="#cdd6f4",
            activebackground="#45475a",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            command=self._koreksi_next
        )
        btn_next.pack(side=tk.LEFT, padx=4)

        btn_delete = tk.Button(
            nav_frame,
            text="🗑️ Hapus Sampel (Del)",
            font=("Segoe UI", 8),
            bg="#f38ba8",
            fg="#11111b",
            activebackground="#eba0ac",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            command=self._koreksi_delete_current
        )
        btn_delete.pack(side=tk.RIGHT)

        # Shortcut Del / Delete untuk hapus sampel seketika tanpa konfirmasi
        self.koreksi_win.bind("<Delete>", lambda e: (self._koreksi_delete_current(), "break")[1])
        self.entry_koreksi_text.bind("<Delete>", lambda e: (self._koreksi_delete_current(), "break")[1])

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
            self.rb_kt.config(text=f"🚩 Kurang Tepat ({count_kt})")
            self.rb_td.config(text=f"⚠️ Tidak Dikenali ({count_td})")

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

        src_badge = "🚩 [F2 Kurang Tepat]" if item["source"] == "kurang_tepat" else "⚠️ [Auto Tidak Dikenali]"
        self.lbl_koreksi_fname.config(text=f"{src_badge} {item['filename']}")
        self.lbl_koreksi_detail.config(text=f"Terdeteksi: '{item['label']}' | Keyakinan: {item['conf']}")

        if item["is_corrected"]:
            self.lbl_koreksi_status.config(text=f"✅ Sudah Dikoreksi: '{item['seh']}'", fg="#a6e3a1")
        else:
            self.lbl_koreksi_status.config(text="⚠️ Belum Dikoreksi", fg="#fab387")

        total = len(self._koreksi_items)
        self.lbl_koreksi_progress.config(text=f"Sampel {self._koreksi_current_idx + 1} dari {total}")

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

        self.add_word_win = tk.Toplevel(self.root)
        self.add_word_win.title("➕ Tambah Kata ke Kamus")
        self.add_word_win.geometry("420x440")
        self.add_word_win.minsize(380, 400)
        self.add_word_win.attributes("-topmost", True)
        self.add_word_win.configure(bg="#1e1e2e")
        self.add_word_win.bind("<Escape>", lambda e: self.add_word_win.destroy())

        try:
            x = self.root.winfo_x() + 30
            y = self.root.winfo_y() + 40
            self.add_word_win.geometry(f"420x440+{x}+{y}")
        except Exception:
            pass

        # Header Frame
        hdr = tk.Frame(self.add_word_win, bg="#181825", padx=14, pady=10)
        hdr.pack(fill=tk.X)

        title_lbl = tk.Label(
            hdr,
            text="📚 Tambah Kata Baru ke Kamus",
            font=("Segoe UI", 12, "bold"),
            fg="#a6e3a1",
            bg="#181825"
        )
        title_lbl.pack(side=tk.LEFT)

        self.lbl_dict_total = tk.Label(
            hdr,
            text=f"{len(self.solver.words):,} kata",
            font=("Segoe UI", 9, "bold"),
            fg="#a6adc8",
            bg="#181825"
        )
        self.lbl_dict_total.pack(side=tk.RIGHT)

        sub_lbl = tk.Label(
            self.add_word_win,
            text="Kosakata yang ditambahkan akan tersimpan ke kamus_lengkap.txt\ndan langsung siap digunakan oleh bot saat bermain.",
            font=("Segoe UI", 8),
            fg="#a6adc8",
            bg="#1e1e2e",
            padx=14,
            pady=6,
            justify=tk.LEFT
        )
        sub_lbl.pack(anchor=tk.W)

        # Input Card Frame
        input_card = tk.Frame(self.add_word_win, bg="#313244", padx=12, pady=10)
        input_card.pack(fill=tk.X, padx=14, pady=6)

        lbl_input_title = tk.Label(
            input_card,
            text="Ketik Kata Baru:",
            font=("Segoe UI", 10, "bold"),
            fg="#cdd6f4",
            bg="#313244"
        )
        lbl_input_title.pack(anchor=tk.W)

        self.entry_new_word = tk.Entry(
            input_card,
            font=("Segoe UI", 13, "bold"),
            bg="#181825",
            fg="#cdd6f4",
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
            fg="#a6adc8",
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
            activebackground="#94e2d5",
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
            fg="#89b4fa",
            activebackground="#45475a",
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
            fg="#cdd6f4",
            activebackground="#45475a",
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
            self.lbl_live_tier.config(text="Tipe: -", fg="#a6adc8")
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
                            fg="#89b4fa"
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

        self.update_win = tk.Toplevel(self.root)
        self.update_win.title("🚀 Pembaruan Aplikasi — Sambung Kata" if has_update else "⚙️ Pengaturan & Info Pembaruan")
        self.update_win.geometry("480x620")
        self.update_win.minsize(440, 520)
        self.update_win.attributes("-topmost", True)
        self.update_win.configure(bg="#1e1e2e")
        self.update_win.bind("<Escape>", lambda e: self.update_win.destroy())

        try:
            x = self.root.winfo_x() + 20
            y = self.root.winfo_y() + 20
            self.update_win.geometry(f"480x620+{x}+{y}")
        except Exception:
            pass

        # 1. Header Frame
        hdr = tk.Frame(self.update_win, bg="#181825", padx=14, pady=10)
        hdr.pack(fill=tk.X)

        if has_update:
            lbl_title = tk.Label(
                hdr,
                text="🔀 Beralih Branch" if is_branch_switch else "🚀 Pembaruan Tersedia!",
                font=("Segoe UI", 12, "bold"),
                fg="#f9e2af",
                bg="#181825"
            )
            lbl_title.pack(side=tk.LEFT)

            status_text = f"Target: {branch}" if is_branch_switch else f"{behind_count} commit baru"
            lbl_count = tk.Label(
                hdr,
                text=status_text,
                font=("Segoe UI", 9, "bold"),
                fg="#a6e3a1",
                bg="#181825"
            )
            lbl_count.pack(side=tk.RIGHT)
        else:
            lbl_title = tk.Label(
                hdr,
                text="✅ Versi Terbaru",
                font=("Segoe UI", 12, "bold"),
                fg="#a6e3a1",
                bg="#181825"
            )
            lbl_title.pack(side=tk.LEFT)

            lbl_cur = tk.Label(
                hdr,
                text=f"Commit #{curr_commit.get('hash', 'latest')}",
                font=("Segoe UI", 9, "bold"),
                fg="#89b4fa",
                bg="#181825"
            )
            lbl_cur.pack(side=tk.RIGHT)

        # 2. Branch Selector Bar
        branch_box = tk.Frame(self.update_win, bg="#24273a", padx=12, pady=6, bd=1, relief=tk.FLAT)
        branch_box.pack(fill=tk.X, padx=14, pady=(6, 2))

        lbl_br = tk.Label(
            branch_box,
            text="🌿 Branch:",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#24273a"
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
            fg="#a6adc8",
            bg="#24273a"
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

        btn_chk_br = tk.Button(
            branch_box,
            text="Ganti Branch",
            font=("Segoe UI", 8, "bold"),
            bg="#89b4fa",
            fg="#11111b",
            activebackground="#b4befe",
            relief=tk.FLAT,
            padx=6,
            pady=1,
            cursor="hand2",
            command=_on_branch_change_action
        )
        btn_chk_br.pack(side=tk.RIGHT)

        # 3. Status / Info Subtitle
        sub_frame = tk.Frame(self.update_win, bg="#1e1e2e", padx=14, pady=4)
        sub_frame.pack(fill=tk.X)

        if is_branch_switch:
            msg_sub = f"Anda sedang di branch '{current_branch}'. Memilih branch '{branch}' akan beralih ke branch tersebut."
            fg_sub = "#f9e2af"
        elif has_update:
            msg_sub = f"Branch '{branch}' di GitHub memiliki {behind_count} commit baru:"
            fg_sub = "#cdd6f4"
        else:
            msg_sub = f"Aplikasi Anda sudah sinkron dengan branch '{branch}' di GitHub.\nCommit aktif: {curr_commit.get('message', '-')}"
            fg_sub = "#a6adc8"

        lbl_sub = tk.Label(
            sub_frame,
            text=msg_sub,
            font=("Segoe UI", 9),
            fg=fg_sub,
            bg="#1e1e2e",
            wraplength=450,
            justify=tk.LEFT
        )
        lbl_sub.pack(anchor=tk.W)

        # 4. Commit List Container (Canvas + Scrollbar)
        if commits:
            list_container = tk.Frame(self.update_win, bg="#181825", bd=1, relief=tk.SOLID)
            list_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

            canvas = tk.Canvas(list_container, bg="#181825", highlightthickness=0)
            scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
            commit_scroll_frame = tk.Frame(canvas, bg="#181825")

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
            current_box = tk.Frame(self.update_win, bg="#181825", padx=12, pady=10, bd=1, relief=tk.SOLID)
            current_box.pack(fill=tk.X, padx=14, pady=8)

            tk.Label(
                current_box,
                text="📌 INFORMASI COMMIT AKTIF",
                font=("Segoe UI", 8, "bold"),
                fg="#89b4fa",
                bg="#181825"
            ).pack(anchor=tk.W)

            tk.Label(
                current_box,
                text=f"Hash: {curr_commit.get('hash', '-')}",
                font=("Segoe UI", 9, "bold"),
                fg="#f9e2af",
                bg="#181825"
            ).pack(anchor=tk.W, pady=(2, 0))

            tk.Label(
                current_box,
                text=f"Pesan: {curr_commit.get('message', '-')}",
                font=("Segoe UI", 9),
                fg="#cdd6f4",
                bg="#181825",
                wraplength=420,
                justify=tk.LEFT
            ).pack(anchor=tk.W, pady=(2, 0))

            tk.Label(
                current_box,
                text=f"Tanggal: {curr_commit.get('date', '-')} | Oleh: {curr_commit.get('author', '-')}",
                font=("Segoe UI", 8),
                fg="#6c7086",
                bg="#181825"
            ).pack(anchor=tk.W, pady=(4, 0))

        # 5. Mode Selection Frame (Radio buttons for: prompt, auto, disabled)
        mode_box = tk.Frame(self.update_win, bg="#24273a", padx=12, pady=6, bd=1, relief=tk.FLAT)
        mode_box.pack(fill=tk.X, padx=14, pady=4)

        lbl_mode_title = tk.Label(
            mode_box,
            text="⚙️ Mode Pemeriksaan Update:",
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#24273a"
        )
        lbl_mode_title.pack(anchor=tk.W, pady=(0, 2))

        curr_mode = self.config.get("updater_mode", "prompt")
        var_updater_mode = tk.StringVar(value=curr_mode)

        def _on_mode_change():
            new_mode = var_updater_mode.get()
            self.config["updater_mode"] = new_mode
            save_config(self.config)
            mode_labels = {
                "prompt": "Tanya Setiap Ada Update",
                "auto": "Otomatis Update di Latar Belakang",
                "disabled": "Pengecekan Otomatis Dinonaktifkan"
            }
            self.show_toast(f"Mode updater: {mode_labels.get(new_mode, new_mode)}")

        modes = [
            ("prompt", "🔔 Tanya Setiap Ada Update (Prompt)", "#cdd6f4"),
            ("auto", "⚡ Otomatis Update Tanpa Tanya (Auto)", "#a6e3a1"),
            ("disabled", "🚫 Nonaktifkan Cek Otomatis (Disabled)", "#f38ba8")
        ]
        for val, text, color in modes:
            rb = tk.Radiobutton(
                mode_box,
                text=text,
                variable=var_updater_mode,
                value=val,
                font=("Segoe UI", 8, "bold" if val == curr_mode else "normal"),
                fg=color,
                bg="#24273a",
                selectcolor="#181825",
                activebackground="#24273a",
                activeforeground=color,
                command=_on_mode_change
            )
            rb.pack(anchor=tk.W, pady=1)

        # 6. Action Buttons Frame
        btn_frame = tk.Frame(self.update_win, bg="#1e1e2e", padx=14, pady=8)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        lbl_update_status = tk.Label(
            btn_frame,
            text="",
            font=("Segoe UI", 8),
            fg="#fab387",
            bg="#1e1e2e"
        )
        lbl_update_status.pack(fill=tk.X, pady=(0, 4))

        if has_update:
            btn_text = f"🔀 Beralih ke '{branch}' & Update" if is_branch_switch else "🚀 Perbarui Sekarang"
            btn_apply = tk.Button(
                btn_frame,
                text=btn_text,
                font=("Segoe UI", 10, "bold"),
                bg="#a6e3a1",
                fg="#11111b",
                activebackground="#94e2d5",
                relief=tk.FLAT,
                padx=14,
                pady=5,
                cursor="hand2"
            )
            btn_apply.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

            def _apply_click():
                btn_apply.config(state=tk.DISABLED, text="⏳ Memproses Pembaruan...")
                lbl_update_status.config(text=f"Sedang mengunduh / beralih ke '{branch}'...")

                def _apply_worker():
                    success, msg = self.updater.apply_update(target_branch=branch)

                    def _apply_done():
                        if success:
                            self.config["updater_branch"] = branch
                            save_config(self.config)
                            lbl_update_status.config(text=f"✅ {msg}", fg="#a6e3a1")
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
                            btn_apply.config(state=tk.NORMAL, text="🔄 Coba Lagi")
                            lbl_update_status.config(text=f"❌ Gagal: {msg}", fg="#f38ba8")

                    self.root.after(0, _apply_done)

                threading.Thread(target=_apply_worker, daemon=True).start()

            btn_apply.config(command=_apply_click)

            btn_dismiss = tk.Button(
                btn_frame,
                text="Nanti Saja",
                font=("Segoe UI", 9),
                bg="#313244",
                fg="#cdd6f4",
                activebackground="#45475a",
                relief=tk.FLAT,
                padx=12,
                pady=5,
                command=self.update_win.destroy
            )
            btn_dismiss.pack(side=tk.RIGHT)
        else:
            btn_recheck = tk.Button(
                btn_frame,
                text="🔄 Periksa Lagi",
                font=("Segoe UI", 9, "bold"),
                bg="#89b4fa",
                fg="#11111b",
                activebackground="#b4befe",
                relief=tk.FLAT,
                padx=12,
                pady=4,
                cursor="hand2",
                command=lambda: [self.update_win.destroy(), self.check_for_updates(target_branch=branch, manual=True)]
            )
            btn_recheck.pack(side=tk.LEFT)

            btn_close = tk.Button(
                btn_frame,
                text="Tutup",
                font=("Segoe UI", 9),
                bg="#313244",
                fg="#cdd6f4",
                activebackground="#45475a",
                relief=tk.FLAT,
                padx=14,
                pady=4,
                command=self.update_win.destroy
            )
            btn_close.pack(side=tk.RIGHT)
            btn_recheck.pack(side=tk.LEFT)

            btn_close = tk.Button(
                btn_frame,
                text="Tutup",
                font=("Segoe UI", 9),
                bg="#313244",
                fg="#cdd6f4",
                activebackground="#45475a",
                relief=tk.FLAT,
                padx=14,
                pady=4,
                command=self.update_win.destroy
            )
            btn_close.pack(side=tk.RIGHT)

    def _create_commit_card(self, parent, commit_info):
        """Membuat tampilan kartu per-commit di daftar pembaruan"""
        card = tk.Frame(parent, bg="#11111b", padx=10, pady=8, bd=1, relief=tk.SOLID)
        card.pack(fill=tk.X, padx=6, pady=4)

        hdr = tk.Frame(card, bg="#11111b")
        hdr.pack(fill=tk.X)

        h_badge = tk.Label(
            hdr,
            text=f"📌 #{commit_info['hash']}",
            font=("Segoe UI", 8, "bold"),
            bg="#313244",
            fg="#89b4fa",
            padx=4,
            pady=1
        )
        h_badge.pack(side=tk.LEFT)

        info_lbl = tk.Label(
            hdr,
            text=f"{commit_info['date']} • {commit_info['author']}",
            font=("Segoe UI", 8),
            fg="#6c7086",
            bg="#11111b"
        )
        info_lbl.pack(side=tk.LEFT, padx=6)

        msg_lbl = tk.Label(
            card,
            text=commit_info['message'],
            font=("Segoe UI", 9, "bold"),
            fg="#cdd6f4",
            bg="#11111b",
            wraplength=380,
            justify=tk.LEFT,
            anchor=tk.W
        )
        msg_lbl.pack(fill=tk.X, pady=(4, 0))

    def _restart_app_cleanly(self):
        """Menutup aplikasi secara bersih lalu memulai ulang"""
        try:
            self.on_close()
        except Exception:
            pass
        self.updater.restart_app()

    def on_close(self):
        try:
            self.config["window_geometry"] = self.root.geometry()
            save_config(self.config)
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
