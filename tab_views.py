"""
tab_views.py
Implementasi Tampilan Konten untuk 4 Tab SAKA Overlay:
- Tab TAGS (Sub-Tab: Brutal Preset & Kelola Semua Tag Kustom)
- Tab KAMUS (Sub-Tab: Whitelist, Blocklist, & Eksplorer Terpisah Search & Add)
- Tab SYSTEM (Kartu Modular: Scanner dengan Dropdown Speed, Hotkey, Preferensi, dan Info Branch/Commit)
Dilengkapi dukungan MouseWheel universal terintegrasi dan tema Tactical Cyber murni (tanpa emoji OS).
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import webbrowser
from ui_theme import THEME, render_vector_icon
from ui_components import SubTabStrip, CyberSwitch
from config import save_config

def bind_mousewheel_recursive(widget, on_scroll):
    """
    Mengikat event scroll roda mouse ke sebuah widget dan seluruh turunan (children)-nya
    secara rekursif agar scrolling tidak terputus saat mouse berada di atas teks/kartu.
    """
    for event_name in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        widget.bind(event_name, on_scroll)
    for child in widget.winfo_children():
        bind_mousewheel_recursive(child, on_scroll)


class TagsTabView(tk.Frame):
    """
    Tampilan Tab 2: TAGS (Bebas bloat via Sub-Tab Navigasi)
    - Sub-Tab 1: BRUTAL PRESET
    - Sub-Tab 2: KELOLA SEMUA TAG
    """
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=THEME["bg_root"], **kwargs)
        self.app = app

        # Sub-Tab Navigasi Ramping
        sub_tabs = [
            ("brutal", "BRUTAL PRESET", "zap"),
            ("custom", f"KELOLA SEMUA TAG ({len(app.config.get('custom_trap_endings', []))})", "tag")
        ]
        self.sub_strip = SubTabStrip(self, sub_tabs, on_tab_changed=self._on_sub_tab_changed)
        self.sub_strip.pack(fill=tk.X, side=tk.TOP)

        self.container = tk.Frame(self, bg=THEME["bg_root"])
        self.container.pack(fill=tk.BOTH, expand=True)

        self.sub_brutal_frame = tk.Frame(self.container, bg=THEME["bg_root"])
        self.sub_custom_frame = tk.Frame(self.container, bg=THEME["bg_root"])

        self._build_brutal_view()
        self._build_custom_view()

        self._on_sub_tab_changed("brutal")

    def _on_sub_tab_changed(self, sub_id):
        self.sub_brutal_frame.pack_forget()
        self.sub_custom_frame.pack_forget()

        if sub_id == "brutal":
            self.sub_brutal_frame.pack(fill=tk.BOTH, expand=True)
            self._refresh_brutal_list()
        else:
            self.sub_custom_frame.pack(fill=tk.BOTH, expand=True)
            self._refresh_custom_list()

    def _scroll_canvas(self, canvas, event):
        if event.delta:
            step = int(-1 * (event.delta / 120))
        elif event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            return
        canvas.yview_scroll(step, "units")

    def _build_brutal_view(self):
        hdr = tk.Frame(self.sub_brutal_frame, bg=THEME["bg_card"], padx=10, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        hdr.pack(fill=tk.X, padx=8, pady=6)

        lbl = tk.Label(
            hdr,
            text="PRESET TAG MODE BRUTAL",
            font=("Segoe UI", 9, "bold"),
            fg=THEME["danger"],
            bg=THEME["bg_card"]
        )
        lbl.pack(side=tk.LEFT)

        btn_all = tk.Button(
            hdr,
            text="Pilih Semua",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["bg_hover"],
            fg=THEME["primary"],
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._brutal_select_all
        )
        btn_all.pack(side=tk.RIGHT, padx=2)

        btn_rst = tk.Button(
            hdr,
            text="Reset Default",
            font=("Segoe UI", 8),
            bg=THEME["bg_hover"],
            fg=THEME["text_secondary"],
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._brutal_reset_default
        )
        btn_rst.pack(side=tk.RIGHT, padx=2)

        canvas_f = tk.Frame(self.sub_brutal_frame, bg=THEME["bg_root"])
        canvas_f.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        self.brutal_canvas = tk.Canvas(canvas_f, bg=THEME["bg_root"], highlightthickness=0)
        self.brutal_scroll = ttk.Scrollbar(canvas_f, orient=tk.VERTICAL, command=self.brutal_canvas.yview)
        self.brutal_inner = tk.Frame(self.brutal_canvas, bg=THEME["bg_root"])

        self.brutal_win_id = self.brutal_canvas.create_window((0, 0), window=self.brutal_inner, anchor="nw")
        self.brutal_canvas.configure(yscrollcommand=self.brutal_scroll.set)

        self.brutal_canvas.bind("<Configure>", lambda e: self.brutal_canvas.itemconfig(self.brutal_win_id, width=e.width))
        self.brutal_inner.bind("<Configure>", lambda e: self.brutal_canvas.configure(scrollregion=self.brutal_canvas.bbox("all")))

        # Bind scroll
        scroll_cb = lambda e: self._scroll_canvas(self.brutal_canvas, e)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.brutal_canvas.bind(ev, scroll_cb)
            self.brutal_inner.bind(ev, scroll_cb)

        self.brutal_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.brutal_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _refresh_brutal_list(self):
        for w in self.brutal_inner.winfo_children():
            w.destroy()

        brutal_tags = set(self.app.config.get("brutal_mode_tags", ["AMSI", "KSO", "RHU", "TL", "BD"]))
        cats = self.app.config.get("custom_trap_endings", [])

        scroll_cb = lambda e: self._scroll_canvas(self.brutal_canvas, e)

        for cat in cats:
            sfx = cat.get("suffix", "").upper()
            is_active = (sfx in brutal_tags)

            bg_c = THEME["danger_bg"] if is_active else THEME["bg_card"]
            bd_c = THEME["danger"] if is_active else THEME["border"]

            row = tk.Frame(self.brutal_inner, bg=bg_c, highlightthickness=1, highlightbackground=bd_c, padx=8, pady=6, cursor="hand2")
            row.pack(fill=tk.X, pady=2)

            chk_txt = "☑" if is_active else "☐"
            chk_fg = THEME["danger"] if is_active else THEME["text_muted"]
            lbl_chk = tk.Label(row, text=chk_txt, font=("Segoe UI", 11, "bold"), fg=chk_fg, bg=bg_c, cursor="hand2")
            lbl_chk.pack(side=tk.LEFT, padx=(2, 6))

            badge = tk.Label(
                row,
                text=sfx,
                font=("Segoe UI", 8, "bold"),
                bg=cat.get("color", THEME["primary"]),
                fg=THEME["text_dark"],
                padx=6,
                pady=1
            )
            badge.pack(side=tk.LEFT, padx=(0, 6))

            name_txt = cat.get("name", sfx)
            lbl_name = tk.Label(row, text=name_txt, font=("Segoe UI", 9, "bold" if is_active else "normal"), fg=THEME["text_primary"] if is_active else THEME["text_secondary"], bg=bg_c, cursor="hand2")
            lbl_name.pack(side=tk.LEFT, fill=tk.X, expand=True)

            status_txt = "BRUTAL" if is_active else "NONAKTIF"
            status_fg = THEME["danger"] if is_active else THEME["text_muted"]
            lbl_st = tk.Label(row, text=status_txt, font=("Segoe UI", 7, "bold"), fg=status_fg, bg=bg_c)
            lbl_st.pack(side=tk.RIGHT)

            handler = lambda e, s=sfx: self._toggle_brutal_tag(s)
            for w in (row, lbl_chk, badge, lbl_name, lbl_st):
                w.bind("<Button-1>", handler)

            # Bind scroll to every item
            bind_mousewheel_recursive(row, scroll_cb)

    def _toggle_brutal_tag(self, suffix):
        b_tags = set(self.app.config.get("brutal_mode_tags", []))
        if suffix in b_tags:
            b_tags.remove(suffix)
        else:
            b_tags.add(suffix)
        self.app.config["brutal_mode_tags"] = list(b_tags)
        save_config(self.app.config)

        if self.app.config.get("game_mode") == "brutal":
            cats = self.app.config.get("custom_trap_endings", [])
            for cat in cats:
                cat["enabled"] = (cat.get("suffix", "").upper() in b_tags)
            self.app.config["custom_trap_endings"] = cats
            save_config(self.app.config)
            self.app.solver.set_custom_endings(cats)
            self.app._render_custom_category_quick_bar()
            if hasattr(self.app, "last_detected_word") and self.app.last_detected_word:
                self.app.update_results(self.app.last_detected_word)

        self._refresh_brutal_list()

    def _brutal_select_all(self):
        cats = self.app.config.get("custom_trap_endings", [])
        all_tags = [c.get("suffix", "").upper() for c in cats if c.get("suffix")]
        self.app.config["brutal_mode_tags"] = all_tags
        save_config(self.app.config)
        self._refresh_brutal_list()

    def _brutal_reset_default(self):
        self.app.config["brutal_mode_tags"] = ["AMSI", "KSO", "RHU", "TL", "BD"]
        save_config(self.app.config)
        self._refresh_brutal_list()

    def _build_custom_view(self):
        act_bar = tk.Frame(self.sub_custom_frame, bg=THEME["bg_card"], padx=8, pady=6, highlightthickness=1, highlightbackground=THEME["border"])
        act_bar.pack(fill=tk.X, padx=8, pady=6)

        lbl = tk.Label(act_bar, text="Sortir:", font=("Segoe UI", 8, "bold"), fg=THEME["text_secondary"], bg=THEME["bg_card"])
        lbl.pack(side=tk.LEFT, padx=(2, 4))

        for text_btn, cmd in [
            ("A-Z", lambda: (self.app._on_sort_custom_categories_az(), self._refresh_custom_list())),
            ("Banyak", lambda: (self.app._on_sort_custom_categories_count(), self._refresh_custom_list())),
            ("Panjang", lambda: (self.app._on_sort_custom_categories_length(reverse=True), self._refresh_custom_list())),
            ("Pendek", lambda: (self.app._on_sort_custom_categories_length(reverse=False), self._refresh_custom_list()))
        ]:
            b = tk.Button(
                act_bar,
                text=text_btn,
                font=("Segoe UI", 7, "bold"),
                bg=THEME["bg_hover"],
                fg=THEME["text_primary"],
                relief=tk.FLAT,
                padx=5,
                pady=1,
                cursor="hand2",
                command=cmd
            )
            b.pack(side=tk.LEFT, padx=2)

        btn_tambah = tk.Button(
            act_bar,
            text="+ Tag Baru",
            font=("Segoe UI", 8, "bold"),
            bg=THEME["primary"],
            fg=THEME["text_dark"],
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._open_add_dialog
        )
        btn_tambah.pack(side=tk.RIGHT)

        canvas_f = tk.Frame(self.sub_custom_frame, bg=THEME["bg_root"])
        canvas_f.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        self.custom_canvas = tk.Canvas(canvas_f, bg=THEME["bg_root"], highlightthickness=0)
        self.custom_scroll = ttk.Scrollbar(canvas_f, orient=tk.VERTICAL, command=self.custom_canvas.yview)
        self.custom_inner = tk.Frame(self.custom_canvas, bg=THEME["bg_root"])

        self.custom_win_id = self.custom_canvas.create_window((0, 0), window=self.custom_inner, anchor="nw")
        self.custom_canvas.configure(yscrollcommand=self.custom_scroll.set)

        self.custom_canvas.bind("<Configure>", lambda e: self.custom_canvas.itemconfig(self.custom_win_id, width=e.width))
        self.custom_inner.bind("<Configure>", lambda e: self.custom_canvas.configure(scrollregion=self.custom_canvas.bbox("all")))

        scroll_cb = lambda e: self._scroll_canvas(self.custom_canvas, e)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.custom_canvas.bind(ev, scroll_cb)
            self.custom_inner.bind(ev, scroll_cb)

        self.custom_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.custom_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _refresh_custom_list(self):
        for w in self.custom_inner.winfo_children():
            w.destroy()

        cats = self.app.config.get("custom_trap_endings", [])
        self.sub_strip.buttons["custom"]["text"].config(text=f"KELOLA SEMUA TAG ({len(cats)})")

        scroll_cb = lambda e: self._scroll_canvas(self.custom_canvas, e)

        for idx, cat in enumerate(cats):
            sfx = cat.get("suffix", "").upper()
            is_enabled = cat.get("enabled", True)

            bg_c = THEME["bg_card"] if is_enabled else THEME["bg_root"]
            bd_c = THEME["border_focus"] if is_enabled else THEME["border"]

            row = tk.Frame(self.custom_inner, bg=bg_c, highlightthickness=1, highlightbackground=bd_c, padx=8, pady=4)
            row.pack(fill=tk.X, pady=2)

            btn_up = tk.Button(row, text="▲", font=("Segoe UI", 6), bg=bg_c, fg=THEME["text_muted"], relief=tk.FLAT, bd=0, cursor="hand2", command=lambda i=idx: (self.app._on_move_custom_category(i, -1), self._refresh_custom_list()))
            btn_up.pack(side=tk.LEFT, padx=(0, 2))
            btn_down = tk.Button(row, text="▼", font=("Segoe UI", 6), bg=bg_c, fg=THEME["text_muted"], relief=tk.FLAT, bd=0, cursor="hand2", command=lambda i=idx: (self.app._on_move_custom_category(i, 1), self._refresh_custom_list()))
            btn_down.pack(side=tk.LEFT, padx=(0, 4))

            badge = tk.Label(
                row,
                text=sfx,
                font=("Segoe UI", 8, "bold"),
                bg=cat.get("color", THEME["primary"]),
                fg=THEME["text_dark"],
                padx=6,
                pady=1
            )
            badge.pack(side=tk.LEFT, padx=(0, 6))

            lbl_name = tk.Label(row, text=cat.get("name", sfx), font=("Segoe UI", 9, "bold"), fg=THEME["text_primary"], bg=bg_c)
            lbl_name.pack(side=tk.LEFT, fill=tk.X, expand=True)

            edit_ico = render_vector_icon("edit", size=14, color=THEME["text_secondary"])
            btn_edit = tk.Button(row, image=edit_ico, bg=bg_c, relief=tk.FLAT, bd=0, cursor="hand2", command=lambda c=cat: (self.app.open_edit_custom_category_dialog(c), self._refresh_custom_list()))
            btn_edit.image = edit_ico
            btn_edit.pack(side=tk.RIGHT, padx=4)

            switch_txt = "ON" if is_enabled else "OFF"
            switch_fg = THEME["primary"] if is_enabled else THEME["text_muted"]
            btn_sw = tk.Button(
                row,
                text=switch_txt,
                font=("Segoe UI", 7, "bold"),
                bg=THEME["bg_hover"],
                fg=switch_fg,
                relief=tk.FLAT,
                padx=6,
                pady=1,
                cursor="hand2",
                command=lambda i=idx: (self.app._on_toggle_custom_category(i), self._refresh_custom_list())
            )
            btn_sw.pack(side=tk.RIGHT, padx=2)

            bind_mousewheel_recursive(row, scroll_cb)

    def _open_add_dialog(self):
        self.app.open_edit_custom_category_dialog(None)
        self._refresh_custom_list()


class DictionaryTabView(tk.Frame):
    """
    Tampilan Tab 3: KAMUS (Whitelist, Blocklist, Eksplorer)
    Mendukung State Persistence sub-tab terakhir, pemisahan tombol Search & Simpan, dan auto-focus.
    """
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=THEME["bg_root"], **kwargs)
        self.app = app

        self.last_sub = self.app.config.get("last_dict_sub_tab", "whitelist")

        sub_tabs = [
            ("whitelist", "WHITELIST", "star"),
            ("blocklist", "BLOCKLIST", "cross"),
            ("eksplorer", "EKSPLORER", "search")
        ]
        self.sub_strip = SubTabStrip(self, sub_tabs, on_tab_changed=self._on_sub_tab_changed)
        self.sub_strip.pack(fill=tk.X, side=tk.TOP)

        self.container = tk.Frame(self, bg=THEME["bg_root"])
        self.container.pack(fill=tk.BOTH, expand=True)

        self.sub_wl_frame = tk.Frame(self.container, bg=THEME["bg_root"])
        self.sub_bl_frame = tk.Frame(self.container, bg=THEME["bg_root"])
        self.sub_ex_frame = tk.Frame(self.container, bg=THEME["bg_root"])

        self._build_whitelist_view()
        self._build_blocklist_view()
        self._build_eksplorer_view()

        self.sub_strip.select_sub_tab(self.last_sub)

    def _scroll_canvas(self, canvas, event):
        if event.delta:
            step = int(-1 * (event.delta / 120))
        elif event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            return
        canvas.yview_scroll(step, "units")

    def _on_sub_tab_changed(self, sub_id):
        self.app.config["last_dict_sub_tab"] = sub_id
        save_config(self.app.config)

        self.sub_wl_frame.pack_forget()
        self.sub_bl_frame.pack_forget()
        self.sub_ex_frame.pack_forget()

        if sub_id == "whitelist":
            self.sub_wl_frame.pack(fill=tk.BOTH, expand=True)
            self._refresh_whitelist()
            self.after(50, lambda: (self.entry_wl_add.focus_set(), self.entry_wl_add.select_range(0, tk.END)))
        elif sub_id == "blocklist":
            self.sub_bl_frame.pack(fill=tk.BOTH, expand=True)
            self._refresh_blocklist()
            self.after(50, lambda: (self.entry_bl_add.focus_set(), self.entry_bl_add.select_range(0, tk.END)))
        else:
            self.sub_ex_frame.pack(fill=tk.BOTH, expand=True)
            self.after(50, lambda: (self.entry_ex_new.focus_set(), self.entry_ex_new.select_range(0, tk.END)))

    # 1. WHITELIST VIEW
    def _build_whitelist_view(self):
        top_box = tk.Frame(self.sub_wl_frame, bg=THEME["bg_card"], padx=8, pady=6, highlightthickness=1, highlightbackground=THEME["border"])
        top_box.pack(fill=tk.X, padx=8, pady=6)

        lbl = tk.Label(top_box, text="+ Whitelist Cepat:", font=("Segoe UI", 8, "bold"), fg=THEME["warning"], bg=THEME["bg_card"])
        lbl.pack(side=tk.LEFT, padx=(2, 6))

        self.wl_add_var = tk.StringVar()
        self.entry_wl_add = tk.Entry(top_box, textvariable=self.wl_add_var, font=("Segoe UI", 9, "bold"), bg=THEME["bg_input"], fg=THEME["text_primary"], insertbackground=THEME["primary"], relief=tk.FLAT)
        self.entry_wl_add.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_wl_add.bind("<Return>", self._submit_add_whitelist)

        btn_add = tk.Button(top_box, text="+ Tambah", font=("Segoe UI", 8, "bold"), bg=THEME["warning"], fg=THEME["text_dark"], relief=tk.FLAT, padx=8, pady=2, cursor="hand2", command=self._submit_add_whitelist)
        btn_add.pack(side=tk.RIGHT)

        search_f = tk.Frame(self.sub_wl_frame, bg=THEME["bg_card_alt"], padx=8, pady=4)
        search_f.pack(fill=tk.X, padx=8, pady=(0, 4))
        self.wl_search_var = tk.StringVar()
        entry_s = tk.Entry(search_f, textvariable=self.wl_search_var, font=("Segoe UI", 8), bg=THEME["bg_input"], fg=THEME["text_secondary"], relief=tk.FLAT)
        entry_s.pack(fill=tk.X)
        self.wl_search_var.trace_add("write", lambda *a: self._refresh_whitelist())

        canvas_f = tk.Frame(self.sub_wl_frame, bg=THEME["bg_root"])
        canvas_f.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        self.wl_canvas = tk.Canvas(canvas_f, bg=THEME["bg_root"], highlightthickness=0)
        self.wl_scroll = ttk.Scrollbar(canvas_f, orient=tk.VERTICAL, command=self.wl_canvas.yview)
        self.wl_inner = tk.Frame(self.wl_canvas, bg=THEME["bg_root"])
        self.wl_win_id = self.wl_canvas.create_window((0, 0), window=self.wl_inner, anchor="nw")
        self.wl_canvas.configure(yscrollcommand=self.wl_scroll.set)
        self.wl_canvas.bind("<Configure>", lambda e: self.wl_canvas.itemconfig(self.wl_win_id, width=e.width))
        self.wl_inner.bind("<Configure>", lambda e: self.wl_canvas.configure(scrollregion=self.wl_canvas.bbox("all")))

        scroll_cb = lambda e: self._scroll_canvas(self.wl_canvas, e)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.wl_canvas.bind(ev, scroll_cb)
            self.wl_inner.bind(ev, scroll_cb)

        self.wl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.wl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _submit_add_whitelist(self, event=None):
        w = self.wl_add_var.get().strip().lower()
        if not w:
            return
        if self.app.solver.whitelist_word(w):
            self.app.show_toast(f"'{w.upper()}' masuk Whitelist!")
            self.wl_add_var.set("")
            self._refresh_whitelist()
            if hasattr(self.app, "last_detected_word") and self.app.last_detected_word:
                self.app.update_results(self.app.last_detected_word)
        else:
            self.app.show_toast(f"Kata '{w}' sudah ada di whitelist")

    def _refresh_whitelist(self):
        for w in self.wl_inner.winfo_children():
            w.destroy()

        query = self.wl_search_var.get().strip().lower()
        wl_words = sorted(list(self.app.solver.get_whitelisted_words()))

        scroll_cb = lambda e: self._scroll_canvas(self.wl_canvas, e)

        for word in wl_words:
            if query and query not in word:
                continue
            row = tk.Frame(self.wl_inner, bg=THEME["bg_card"], highlightthickness=1, highlightbackground=THEME["border"], padx=8, pady=4)
            row.pack(fill=tk.X, pady=1)

            star_ico = render_vector_icon("star_filled", size=14, color=THEME["warning"])
            lbl_star = tk.Label(row, image=star_ico, bg=THEME["bg_card"])
            lbl_star.image = star_ico
            lbl_star.pack(side=tk.LEFT, padx=(0, 6))

            lbl_w = tk.Label(row, text=word.upper(), font=("Segoe UI", 9, "bold"), fg=THEME["text_primary"], bg=THEME["bg_card"])
            lbl_w.pack(side=tk.LEFT)

            trash_ico = render_vector_icon("trash", size=14, color=THEME["danger"])
            btn_del = tk.Button(row, image=trash_ico, bg=THEME["bg_card"], relief=tk.FLAT, bd=0, cursor="hand2", command=lambda kw=word: self._remove_whitelist(kw))
            btn_del.image = trash_ico
            btn_del.pack(side=tk.RIGHT)

            bind_mousewheel_recursive(row, scroll_cb)

    def _remove_whitelist(self, kata):
        self.app.solver.unwhitelist_word(kata)
        self.app.show_toast(f"Dicabut dari Whitelist: {kata.upper()}")
        self._refresh_whitelist()
        if hasattr(self.app, "last_detected_word") and self.app.last_detected_word:
            self.app.update_results(self.app.last_detected_word)

    # 2. BLOCKLIST VIEW
    def _build_blocklist_view(self):
        top_box = tk.Frame(self.sub_bl_frame, bg=THEME["bg_card"], padx=8, pady=6, highlightthickness=1, highlightbackground=THEME["border"])
        top_box.pack(fill=tk.X, padx=8, pady=6)

        lbl = tk.Label(top_box, text="+ Blokir Kata:", font=("Segoe UI", 8, "bold"), fg=THEME["danger"], bg=THEME["bg_card"])
        lbl.pack(side=tk.LEFT, padx=(2, 6))

        self.bl_add_var = tk.StringVar()
        self.entry_bl_add = tk.Entry(top_box, textvariable=self.bl_add_var, font=("Segoe UI", 9, "bold"), bg=THEME["bg_input"], fg=THEME["danger"], insertbackground=THEME["danger"], relief=tk.FLAT)
        self.entry_bl_add.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_bl_add.bind("<Return>", self._submit_add_blocklist)

        btn_add = tk.Button(top_box, text="Blokir", font=("Segoe UI", 8, "bold"), bg=THEME["danger"], fg=THEME["text_dark"], relief=tk.FLAT, padx=8, pady=2, cursor="hand2", command=self._submit_add_blocklist)
        btn_add.pack(side=tk.RIGHT)

        search_f = tk.Frame(self.sub_bl_frame, bg=THEME["bg_card_alt"], padx=8, pady=4)
        search_f.pack(fill=tk.X, padx=8, pady=(0, 4))
        self.bl_search_var = tk.StringVar()
        entry_s = tk.Entry(search_f, textvariable=self.bl_search_var, font=("Segoe UI", 8), bg=THEME["bg_input"], fg=THEME["text_secondary"], relief=tk.FLAT)
        entry_s.pack(fill=tk.X)
        self.bl_search_var.trace_add("write", lambda *a: self._refresh_blocklist())

        canvas_f = tk.Frame(self.sub_bl_frame, bg=THEME["bg_root"])
        canvas_f.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        self.bl_canvas = tk.Canvas(canvas_f, bg=THEME["bg_root"], highlightthickness=0)
        self.bl_scroll = ttk.Scrollbar(canvas_f, orient=tk.VERTICAL, command=self.bl_canvas.yview)
        self.bl_inner = tk.Frame(self.bl_canvas, bg=THEME["bg_root"])
        self.bl_win_id = self.bl_canvas.create_window((0, 0), window=self.bl_inner, anchor="nw")
        self.bl_canvas.configure(yscrollcommand=self.bl_scroll.set)
        self.bl_canvas.bind("<Configure>", lambda e: self.bl_canvas.itemconfig(self.bl_win_id, width=e.width))
        self.bl_inner.bind("<Configure>", lambda e: self.bl_canvas.configure(scrollregion=self.bl_canvas.bbox("all")))

        scroll_cb = lambda e: self._scroll_canvas(self.bl_canvas, e)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bl_canvas.bind(ev, scroll_cb)
            self.bl_inner.bind(ev, scroll_cb)

        self.bl_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.bl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _submit_add_blocklist(self, event=None):
        w = self.bl_add_var.get().strip().lower()
        if not w:
            return
        if self.app.solver.blacklist_word(w):
            self.app.show_toast(f"'{w.upper()}' masuk Blocklist!")
            self.bl_add_var.set("")
            self._refresh_blocklist()
            if hasattr(self.app, "last_detected_word") and self.app.last_detected_word:
                self.app.update_results(self.app.last_detected_word)
        else:
            self.app.show_toast(f"Kata '{w}' sudah diblokir")

    def _refresh_blocklist(self):
        for w in self.bl_inner.winfo_children():
            w.destroy()

        query = self.bl_search_var.get().strip().lower()
        bl_words = sorted(list(self.app.solver.get_blacklisted_words()))

        scroll_cb = lambda e: self._scroll_canvas(self.bl_canvas, e)

        for word in bl_words:
            if query and query not in word:
                continue
            row = tk.Frame(self.bl_inner, bg=THEME["danger_bg"], highlightthickness=1, highlightbackground=THEME["danger_border"], padx=8, pady=4)
            row.pack(fill=tk.X, pady=1)

            cross_ico = render_vector_icon("cross", size=12, color=THEME["danger"])
            lbl_ico = tk.Label(row, image=cross_ico, bg=THEME["danger_bg"])
            lbl_ico.image = cross_ico
            lbl_ico.pack(side=tk.LEFT, padx=(0, 6))

            lbl_w = tk.Label(row, text=word.upper(), font=("Segoe UI", 9, "bold"), fg=THEME["danger"], bg=THEME["danger_bg"])
            lbl_w.pack(side=tk.LEFT)

            trash_ico = render_vector_icon("trash", size=14, color=THEME["danger"])
            btn_unbl = tk.Button(row, image=trash_ico, bg=THEME["bg_card"], relief=tk.FLAT, bd=0, cursor="hand2", command=lambda kw=word: self._unblock_word(kw))
            btn_unbl.image = trash_ico
            btn_unbl.pack(side=tk.RIGHT)

            bind_mousewheel_recursive(row, scroll_cb)

    def _unblock_word(self, kata):
        self.app.solver.unblacklist_word(kata)
        self.app.show_toast(f"Dipulihkan dari Blocklist: {kata.upper()}")
        self._refresh_blocklist()
        if hasattr(self.app, "last_detected_word") and self.app.last_detected_word:
            self.app.update_results(self.app.last_detected_word)

    # 3. EKSPLORER VIEW (Terpisah Fungsi Search dan Tambah)
    def _build_eksplorer_view(self):
        # 1. Baris Pencarian Kosakata (Search)
        search_box = tk.Frame(self.sub_ex_frame, bg=THEME["bg_card"], padx=8, pady=6, highlightthickness=1, highlightbackground=THEME["border"])
        search_box.pack(fill=tk.X, padx=8, pady=(6, 2))

        lbl_s = tk.Label(search_box, text="Cari:", font=("Segoe UI", 8, "bold"), fg=THEME["primary"], bg=THEME["bg_card"])
        lbl_s.pack(side=tk.LEFT, padx=(2, 4))

        # Mode Selector (Prefix, Suffix, Contains)
        self.ex_mode_var = tk.StringVar(value="prefix")
        self.ex_mode_combo = ttk.Combobox(search_box, textvariable=self.ex_mode_var, values=["prefix", "suffix", "contains"], state="readonly", width=8)
        self.ex_mode_combo.pack(side=tk.LEFT, padx=(0, 4))
        self.ex_mode_combo.bind("<<ComboboxSelected>>", lambda e: self._do_search())

        self.ex_search_var = tk.StringVar()
        self.entry_ex_search = tk.Entry(search_box, textvariable=self.ex_search_var, font=("Segoe UI", 9, "bold"), bg=THEME["bg_input"], fg=THEME["text_primary"], insertbackground=THEME["primary"], relief=tk.FLAT)
        self.entry_ex_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_ex_search.bind("<Return>", lambda e: self._do_search())

        btn_find = tk.Button(search_box, text="Cari", font=("Segoe UI", 8, "bold"), bg=THEME["primary"], fg=THEME["text_dark"], relief=tk.FLAT, padx=8, pady=2, cursor="hand2", command=self._do_search)
        btn_find.pack(side=tk.RIGHT)

        # 2. Baris Simpan Kata Baru Manual ke Kamus (Terpisah & Aman dari lag search)
        add_box = tk.Frame(self.sub_ex_frame, bg=THEME["bg_card_alt"], padx=8, pady=4, highlightthickness=1, highlightbackground=THEME["border"])
        add_box.pack(fill=tk.X, padx=8, pady=(0, 4))

        lbl_a = tk.Label(add_box, text="+ Kata Baru:", font=("Segoe UI", 8), fg=THEME["text_secondary"], bg=THEME["bg_card_alt"])
        lbl_a.pack(side=tk.LEFT, padx=(2, 4))

        self.ex_new_word_var = tk.StringVar()
        self.entry_ex_new = tk.Entry(add_box, textvariable=self.ex_new_word_var, font=("Segoe UI", 9), bg=THEME["bg_input"], fg=THEME["text_primary"], insertbackground=THEME["primary"], relief=tk.FLAT)
        self.entry_ex_new.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_ex_new.bind("<Return>", self._submit_add_new_word)

        btn_save = tk.Button(add_box, text="Tambah", font=("Segoe UI", 8, "bold"), bg=THEME["bg_hover"], fg=THEME["primary"], relief=tk.FLAT, padx=6, pady=1, cursor="hand2", command=self._submit_add_new_word)
        btn_save.pack(side=tk.RIGHT)

        # Canvas Hasil Pencarian
        canvas_f = tk.Frame(self.sub_ex_frame, bg=THEME["bg_root"])
        canvas_f.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        self.ex_canvas = tk.Canvas(canvas_f, bg=THEME["bg_root"], highlightthickness=0)
        self.ex_scroll = ttk.Scrollbar(canvas_f, orient=tk.VERTICAL, command=self.ex_canvas.yview)
        self.ex_inner = tk.Frame(self.ex_canvas, bg=THEME["bg_root"])
        self.ex_win_id = self.ex_canvas.create_window((0, 0), window=self.ex_inner, anchor="nw")
        self.ex_canvas.configure(yscrollcommand=self.ex_scroll.set)
        self.ex_canvas.bind("<Configure>", lambda e: self.ex_canvas.itemconfig(self.ex_win_id, width=e.width))
        self.ex_inner.bind("<Configure>", lambda e: self.ex_canvas.configure(scrollregion=self.ex_canvas.bbox("all")))

        scroll_cb = lambda e: self._scroll_canvas(self.ex_canvas, e)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.ex_canvas.bind(ev, scroll_cb)
            self.ex_inner.bind(ev, scroll_cb)

        self.ex_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.ex_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _do_search(self):
        query = self.ex_search_var.get().strip().lower()
        mode = self.ex_mode_var.get().strip()

        for w in self.ex_inner.winfo_children():
            w.destroy()

        if not query:
            lbl_empty = tk.Label(self.ex_inner, text="Masukkan teks lalu klik Cari...", font=("Segoe UI", 9, "italic"), fg=THEME["text_muted"], bg=THEME["bg_root"], pady=20)
            lbl_empty.pack(fill=tk.X)
            return

        # Panggil solver.search_dictionary
        results, total_count = self.app.solver.search_dictionary(query=query, search_type=mode, limit=60)

        if not results:
            lbl_nf = tk.Label(self.ex_inner, text=f"Tidak ditemukan kata untuk '{query}' ({mode}). Gunakan form di atas untuk menambahkan kata baru.", font=("Segoe UI", 8, "italic"), fg=THEME["danger"], bg=THEME["bg_root"], pady=20)
            lbl_nf.pack(fill=tk.X)
            return

        scroll_cb = lambda e: self._scroll_canvas(self.ex_canvas, e)

        for item in results:
            word = item["word"]
            tag_name = item.get("tag", "Normal")
            is_wl = item.get("is_whitelisted", False)
            is_bl = item.get("is_blacklisted", False)

            row = tk.Frame(self.ex_inner, bg=THEME["bg_card"], highlightthickness=1, highlightbackground=THEME["border"], padx=8, pady=4)
            row.pack(fill=tk.X, pady=1)

            lbl_w = tk.Label(row, text=word.upper(), font=("Segoe UI", 9, "bold"), fg=THEME["text_primary"], bg=THEME["bg_card"])
            lbl_w.pack(side=tk.LEFT)

            # Badge Kategori
            lbl_tag = tk.Label(row, text=tag_name, font=("Segoe UI", 7, "bold"), fg=THEME["text_dark"], bg=THEME["primary"] if tag_name == "Normal" else THEME["danger"], padx=4, pady=0)
            lbl_tag.pack(side=tk.LEFT, padx=6)

            # Aksi Blocklist
            cross_ico = render_vector_icon("cross", size=12, color=THEME["danger"])
            btn_bl = tk.Button(row, image=cross_ico, bg=THEME["bg_card"], relief=tk.FLAT, bd=0, cursor="hand2", command=lambda kw=word: (self.app.on_blacklist_word(kw), self._do_search()))
            btn_bl.image = cross_ico
            btn_bl.pack(side=tk.RIGHT, padx=2)

            # Aksi Whitelist
            star_ico = render_vector_icon("star_filled" if is_wl else "star", size=13, color=THEME["warning"] if is_wl else THEME["text_muted"])
            btn_wl = tk.Button(row, image=star_ico, bg=THEME["bg_card"], relief=tk.FLAT, bd=0, cursor="hand2", command=lambda kw=word, curr=is_wl: (self.app.on_toggle_whitelist(kw, not curr), self._do_search()))
            btn_wl.image = star_ico
            btn_wl.pack(side=tk.RIGHT, padx=4)

            bind_mousewheel_recursive(row, scroll_cb)

    def _submit_add_new_word(self, event=None):
        w = self.ex_new_word_var.get().strip().lower()
        if not w:
            return
        success, msg = self.app.solver.add_word(w)
        if success:
            self.app.show_toast(f"'{w.upper()}' berhasil ditambahkan ke Kamus!")
            self.ex_new_word_var.set("")
            if hasattr(self.app, "last_detected_word") and self.app.last_detected_word:
                self.app.update_results(self.app.last_detected_word)
        else:
            self.app.show_toast(f"{msg}")


class SystemTabView(tk.Frame):
    """
    Tampilan Tab 4: SYSTEM (Scanner dengan Dropdown Speed, Hotkey, Preferensi, dan Info Branch/Commit)
    """
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=THEME["bg_root"], **kwargs)
        self.app = app

        canvas = tk.Canvas(self, bg=THEME["bg_root"], highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        self.inner = tk.Frame(canvas, bg=THEME["bg_root"])

        win_id = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        scroll_cb = lambda e: self._scroll_canvas(canvas, e)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind(ev, scroll_cb)
            self.inner.bind(ev, scroll_cb)

        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_card_scanner()
        self._build_card_hotkeys()
        self._build_card_preferences()
        self._build_card_system_info()

        bind_mousewheel_recursive(self.inner, scroll_cb)

    def _scroll_canvas(self, canvas, event):
        if event.delta:
            step = int(-1 * (event.delta / 120))
        elif event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            return
        canvas.yview_scroll(step, "units")

    def _build_card_scanner(self):
        card = tk.LabelFrame(self.inner, text=" SCANNER & AREA LAYAR ", font=("Segoe UI", 8, "bold"), fg=THEME["primary"], bg=THEME["bg_card"], padx=10, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill=tk.X, padx=8, pady=4)

        roi = self.app.config.get("detection_region", {})
        roi_txt = f"X: {roi.get('left', 0)}, Y: {roi.get('top', 0)} | {roi.get('width', 0)} x {roi.get('height', 0)} px"
        lbl_roi = tk.Label(card, text=f"Area ROI: [ {roi_txt} ]", font=("Segoe UI", 8), fg=THEME["text_secondary"], bg=THEME["bg_card"], anchor="w")
        lbl_roi.pack(fill=tk.X, pady=(0, 6))

        btn_row = tk.Frame(card, bg=THEME["bg_card"])
        btn_row.pack(fill=tk.X, pady=(0, 6))

        btn_set = tk.Button(btn_row, text="Atur Area Layar", font=("Segoe UI", 8, "bold"), bg=THEME["primary"], fg=THEME["text_dark"], relief=tk.FLAT, padx=8, pady=2, cursor="hand2", command=self.app.open_region_selector)
        btn_set.pack(side=tk.LEFT, padx=(0, 4))

        btn_test = tk.Button(btn_row, text="Preview Area", font=("Segoe UI", 8), bg=THEME["bg_hover"], fg=THEME["text_primary"], relief=tk.FLAT, padx=8, pady=2, cursor="hand2", command=self.app.preview_selected_area)
        btn_test.pack(side=tk.LEFT)

        # Kecepatan scan: Dropdown
        spd_row = tk.Frame(card, bg=THEME["bg_card"])
        spd_row.pack(fill=tk.X, pady=(4, 2))

        lbl_spd = tk.Label(spd_row, text="Kecepatan Scan:", font=("Segoe UI", 8, "bold"), fg=THEME["text_secondary"], bg=THEME["bg_card"])
        lbl_spd.pack(side=tk.LEFT, padx=(0, 6))

        self.speed_map = {
            "40ms (Ultra Instan)": 0.04,
            "80ms (Kilat Turbo)": 0.08,
            "150ms (Cepat)": 0.15,
            "300ms (Santai)": 0.30
        }
        self.rev_speed_map = {v: k for k, v in self.speed_map.items()}

        cur_spd = self.app.config.get("scan_interval_sec", 0.08)
        cur_spd_text = self.rev_speed_map.get(cur_spd, "80ms (Kilat Turbo)")

        self.spd_var = tk.StringVar(value=cur_spd_text)
        self.combo_speed = ttk.Combobox(spd_row, textvariable=self.spd_var, values=list(self.speed_map.keys()), state="readonly", width=18)
        self.combo_speed.pack(side=tk.LEFT)
        self.combo_speed.bind("<<ComboboxSelected>>", self._on_speed_selected)

    def _on_speed_selected(self, event=None):
        selected_text = self.spd_var.get()
        sec = self.speed_map.get(selected_text, 0.08)
        self.app._set_scan_speed(sec, selected_text)
        if hasattr(self.app, "lbl_scan_speed_indicator"):
            self.app.lbl_scan_speed_indicator.config(text=f"Status: {int(sec*1000)}ms")

    def _build_card_hotkeys(self):
        card = tk.LabelFrame(self.inner, text=" SHORTCUT & HOTKEY GLOBAL ", font=("Segoe UI", 8, "bold"), fg=THEME["primary"], bg=THEME["bg_card"], padx=10, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill=tk.X, padx=8, pady=4)

        row1 = tk.Frame(card, bg=THEME["bg_card"])
        row1.pack(fill=tk.X, pady=2)
        lbl1 = tk.Label(row1, text="Tandai OCR Salah:", font=("Segoe UI", 8), fg=THEME["text_secondary"], bg=THEME["bg_card"])
        lbl1.pack(side=tk.LEFT)
        lbl_key = tk.Label(row1, text="[ F2 ]", font=("Segoe UI", 8, "bold"), fg=THEME["accent_neon"], bg=THEME["bg_card"])
        lbl_key.pack(side=tk.RIGHT)

        btn_koreksi = tk.Button(card, text="Buka Jendela Koreksi Sampel", font=("Segoe UI", 8), bg=THEME["bg_hover"], fg=THEME["text_primary"], relief=tk.FLAT, padx=8, pady=3, cursor="hand2", command=self.app.open_koreksi_window)
        btn_koreksi.pack(fill=tk.X, pady=(6, 0))

    def _build_card_preferences(self):
        card = tk.LabelFrame(self.inner, text=" PREFERENSI & DEV MODE ", font=("Segoe UI", 8, "bold"), fg=THEME["primary"], bg=THEME["bg_card"], padx=10, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill=tk.X, padx=8, pady=4)

        is_aot = self.app.config.get("always_on_top", True)
        sw_aot = CyberSwitch(card, text="Always on Top (Di atas game)", initial_value=is_aot, on_toggle=self._toggle_aot)
        sw_aot.pack(fill=tk.X, pady=3)

        is_dev = self.app.config.get("dev_mode", False)
        sw_dev = CyberSwitch(card, text="Mode Development (Tombol Restart)", initial_value=is_dev, on_toggle=self._toggle_dev_mode)
        sw_dev.pack(fill=tk.X, pady=3)

    def _toggle_aot(self, val):
        self.app.config["always_on_top"] = val
        save_config(self.app.config)
        self.app.root.attributes("-topmost", val)
        self.app.show_toast(f"Always on Top: {'ON' if val else 'OFF'}")

    def _toggle_dev_mode(self, val):
        self.app.config["dev_mode"] = val
        save_config(self.app.config)
        if hasattr(self.app, "btn_restart") and self.app.btn_restart.winfo_exists():
            if val:
                self.app.btn_restart.pack(side=tk.RIGHT, padx=(0, 2), pady=2)
            else:
                self.app.btn_restart.pack_forget()
        self.app.show_toast(f"Mode Dev: {'ON' if val else 'OFF'}")

    def _build_card_system_info(self):
        card = tk.LabelFrame(self.inner, text=" INFORMASI SISTEM & PEMBARUAN ", font=("Segoe UI", 8, "bold"), fg=THEME["primary"], bg=THEME["bg_card"], padx=10, pady=8, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill=tk.X, padx=8, pady=4)

        # Baris Branch Selector (Dapat diubah dan auto fetch branch)
        branch_row = tk.Frame(card, bg=THEME["bg_card"])
        branch_row.pack(fill=tk.X, pady=(0, 4))

        lbl_br = tk.Label(branch_row, text="Branch:", font=("Segoe UI", 8, "bold"), fg=THEME["text_secondary"], bg=THEME["bg_card"])
        lbl_br.pack(side=tk.LEFT, padx=(0, 6))

        cur_branch = getattr(self.app.updater, "get_current_branch", lambda: "redesign-ui")()
        avail_branches = getattr(self.app.updater, "get_available_branches", lambda: ["main", "dev", cur_branch])()
        if cur_branch not in avail_branches:
            avail_branches.append(cur_branch)

        self.branch_var = tk.StringVar(value=cur_branch)
        self.combo_branch = ttk.Combobox(branch_row, textvariable=self.branch_var, values=avail_branches, state="readonly", width=14)
        self.combo_branch.pack(side=tk.LEFT)
        self.combo_branch.bind("<<ComboboxSelected>>", self._on_branch_selected)

        # Baris Clickable Commit Hash
        commit_row = tk.Frame(card, bg=THEME["bg_card"])
        commit_row.pack(fill=tk.X, pady=(0, 4))

        lbl_cm = tk.Label(commit_row, text="Commit:", font=("Segoe UI", 8, "bold"), fg=THEME["text_secondary"], bg=THEME["bg_card"])
        lbl_cm.pack(side=tk.LEFT, padx=(0, 6))

        cur_commit = getattr(self.app.updater, "get_current_commit", lambda: {"hash": "8c469b7"})()
        h_hash = cur_commit.get("hash", "unknown")

        self.lbl_commit_click = tk.Label(
            commit_row,
            text=f"#{h_hash}",
            font=("Segoe UI", 8, "underline"),
            fg=THEME["accent_neon"],
            bg=THEME["bg_card"],
            cursor="hand2"
        )
        self.lbl_commit_click.pack(side=tk.LEFT)
        self.lbl_commit_click.bind("<Button-1>", lambda e, h=h_hash: self._open_commit_url(h))

        # Statistik kosakata nyata
        total_k = len(getattr(self.app.solver, "words", []))
        total_wl = len(self.app.solver.get_whitelisted_words())
        total_bl = len(self.app.solver.get_blacklisted_words())
        total_tag = len(self.app.config.get("custom_trap_endings", []))

        lbl_stat = tk.Label(
            card,
            text=f"Kosakata: {total_k:,} | Whitelist: {total_wl} | Block: {total_bl} | Tags: {total_tag}",
            font=("Segoe UI", 8),
            fg=THEME["text_secondary"],
            bg=THEME["bg_card"],
            anchor="w"
        )
        lbl_stat.pack(fill=tk.X, pady=(0, 6))

        # Mode Auto-Updater Dropdown
        upd_row = tk.Frame(card, bg=THEME["bg_card"])
        upd_row.pack(fill=tk.X, pady=(0, 6))

        lbl_um = tk.Label(upd_row, text="Mode Update:", font=("Segoe UI", 8), fg=THEME["text_secondary"], bg=THEME["bg_card"])
        lbl_um.pack(side=tk.LEFT, padx=(0, 6))

        upd_mode_val = self.app.config.get("auto_update_mode", "prompt")
        self.upd_mode_var = tk.StringVar(value=upd_mode_val)

        mode_options = [("Tanya Dulu (Prompt)", "prompt"), ("Otomatis (Auto)", "auto"), ("Nonaktif (Disabled)", "disabled")]
        
        opt_menu = ttk.Combobox(upd_row, textvariable=self.upd_mode_var, values=[m[0] for m in mode_options], state="readonly", width=18)
        for d, v in mode_options:
            if v == upd_mode_val:
                opt_menu.set(d)
                break
        opt_menu.pack(side=tk.LEFT)
        opt_menu.bind("<<ComboboxSelected>>", self._on_update_mode_selected)

        # Tombol Update & Buka Folder
        btn_row = tk.Frame(card, bg=THEME["bg_card"])
        btn_row.pack(fill=tk.X, pady=(2, 0))

        btn_chk = tk.Button(btn_row, text="Cek Update", font=("Segoe UI", 8, "bold"), bg=THEME["bg_hover"], fg=THEME["primary"], relief=tk.FLAT, padx=8, pady=3, cursor="hand2", command=self._check_updates_now)
        btn_chk.pack(side=tk.LEFT, padx=(0, 4))

        btn_fld = tk.Button(btn_row, text="Buka Folder", font=("Segoe UI", 8), bg=THEME["bg_hover"], fg=THEME["text_primary"], relief=tk.FLAT, padx=8, pady=3, cursor="hand2", command=self._open_app_folder)
        btn_fld.pack(side=tk.RIGHT)

    def _on_branch_selected(self, event=None):
        target = self.branch_var.get()
        self.app.config["updater_branch"] = target
        save_config(self.app.config)
        self.app.show_toast(f"Branch target diatur ke: {target}")

    def _open_commit_url(self, commit_hash):
        if commit_hash and commit_hash != "unknown":
            url = f"https://github.com/anv-group/sambung-kata-overlay/commit/{commit_hash}"
            webbrowser.open(url)

    def _on_update_mode_selected(self, event=None):
        val_str = self.upd_mode_var.get()
        mapping = {"Tanya Dulu (Prompt)": "prompt", "Otomatis (Auto)": "auto", "Nonaktif (Disabled)": "disabled"}
        real_val = mapping.get(val_str, "prompt")
        self.app.config["auto_update_mode"] = real_val
        save_config(self.app.config)
        self.app.show_toast(f"Mode Auto-Update disetel ke: {real_val}")

    def _check_updates_now(self):
        target_b = self.branch_var.get()
        self.app.show_toast(f"Sedang memeriksa pembaruan branch '{target_b}' di GitHub...")
        self.app.check_for_updates(target_branch=target_b, manual=True)

    def _open_app_folder(self):
        try:
            os.startfile(os.path.dirname(os.path.abspath(__file__)))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka folder: {e}")
