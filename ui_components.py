"""
ui_components.py
Komponen Modular Antarmuka Tactical Cyber untuk SAKA Overlay.
Menyediakan:
1. TopTabStrip (Navigasi tab atas bergaya cheat injector dengan garis aksen neon lime)
2. MiniTickerBar (Status awalan & kata rekomendasi saat bernavigasi di luar tab LIVE)
3. SubTabStrip (Navigasi sub-tab horizontal anti-bloat di Tab TAGS dan KAMUS)
4. CyberSwitch (Modern toggle switch on/off bergaya sleek tactical)
"""

import tkinter as tk
from ui_theme import THEME, render_vector_icon

class TopTabStrip(tk.Frame):
    """
    Bilah tab horizontal atas dengan ikon vektor PIL tajam dan garis aksen neon bawah.
    """
    def __init__(self, parent, tabs, on_tab_changed=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_root"], **kwargs)
        self.tabs = tabs  # list of tuples: (tab_id, label_text, icon_name)
        self.on_tab_changed = on_tab_changed
        self.active_tab = tabs[0][0] if tabs else None
        self.tab_buttons = {}
        self.indicator_bars = {}

        self._build_tabs()

    def _build_tabs(self):
        self.columnconfigure(tuple(range(len(self.tabs))), weight=1)
        for idx, (tab_id, label, icon_name) in enumerate(self.tabs):
            tab_frame = tk.Frame(self, bg=THEME["bg_root"], cursor="hand2")
            tab_frame.grid(row=0, column=idx, sticky="nsew", padx=2, pady=(2, 0))

            icon_img = render_vector_icon(icon_name, size=15, color=THEME["text_secondary"])
            
            btn_inner = tk.Frame(tab_frame, bg=THEME["bg_root"])
            btn_inner.pack(fill=tk.BOTH, expand=True, pady=(5, 3))

            lbl_icon = tk.Label(btn_inner, image=icon_img, bg=THEME["bg_root"], cursor="hand2")
            lbl_icon.image = icon_img
            lbl_icon.pack(side=tk.LEFT, padx=(6, 4))

            lbl_text = tk.Label(
                btn_inner,
                text=label,
                font=("Segoe UI", 9, "bold"),
                fg=THEME["text_secondary"],
                bg=THEME["bg_root"],
                cursor="hand2"
            )
            lbl_text.pack(side=tk.LEFT, padx=(0, 6))

            # Garis indikator neon bawah
            indicator = tk.Frame(tab_frame, bg=THEME["bg_root"], height=2)
            indicator.pack(fill=tk.X, side=tk.BOTTOM)

            handler = lambda e, tid=tab_id: self.select_tab(tid)
            for widget in (tab_frame, btn_inner, lbl_icon, lbl_text, indicator):
                widget.bind("<Button-1>", handler)

            self.tab_buttons[tab_id] = {
                "frame": tab_frame,
                "inner": btn_inner,
                "icon": lbl_icon,
                "text": lbl_text,
                "indicator": indicator,
                "icon_name": icon_name,
                "label": label
            }

        # Separator bawah seluruh tab strip
        sep = tk.Frame(self, bg=THEME["border"], height=1)
        sep.grid(row=1, column=0, columnspan=len(self.tabs), sticky="ew")

        if self.active_tab:
            self._update_visuals()

    def select_tab(self, tab_id):
        if tab_id not in self.tab_buttons:
            return
        if self.active_tab != tab_id:
            self.active_tab = tab_id
            self._update_visuals()
            if callable(self.on_tab_changed):
                self.on_tab_changed(tab_id)

    def _update_visuals(self):
        for tid, comp in self.tab_buttons.items():
            is_active = (tid == self.active_tab)
            c_fg = THEME["accent_neon"] if is_active else THEME["text_secondary"]
            c_bg = THEME["bg_card"] if is_active else THEME["bg_root"]
            ind_color = THEME["accent_neon"] if is_active else THEME["bg_root"]

            comp["text"].config(fg=c_fg, bg=c_bg)
            comp["inner"].config(bg=c_bg)
            comp["frame"].config(bg=c_bg)

            new_icon = render_vector_icon(comp["icon_name"], size=15, color=c_fg)
            comp["icon"].config(image=new_icon, bg=c_bg)
            comp["icon"].image = new_icon

            comp["indicator"].config(bg=ind_color)


class SubTabStrip(tk.Frame):
    """
    Sub-tab navigasi horizontal ramping untuk Tab TAGS dan Tab KAMUS.
    """
    def __init__(self, parent, sub_tabs, on_tab_changed=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_card_alt"], **kwargs)
        self.sub_tabs = sub_tabs  # [(sub_id, label, icon_name)]
        self.on_tab_changed = on_tab_changed
        self.active_tab = sub_tabs[0][0] if sub_tabs else None
        self.buttons = {}

        self._build_sub_tabs()

    def _build_sub_tabs(self):
        for idx, (sub_id, label, icon_name) in enumerate(self.sub_tabs):
            btn_f = tk.Frame(self, bg=THEME["bg_card_alt"], cursor="hand2")
            btn_f.pack(side=tk.LEFT, fill=tk.Y, padx=1)

            inner = tk.Frame(btn_f, bg=THEME["bg_card_alt"])
            inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

            icon_img = render_vector_icon(icon_name, size=13, color=THEME["text_muted"]) if icon_name else None
            if icon_img:
                lbl_icon = tk.Label(inner, image=icon_img, bg=THEME["bg_card_alt"], cursor="hand2")
                lbl_icon.image = icon_img
                lbl_icon.pack(side=tk.LEFT, padx=(0, 4))
            else:
                lbl_icon = None

            lbl_txt = tk.Label(
                inner,
                text=label,
                font=("Segoe UI", 8, "bold"),
                fg=THEME["text_muted"],
                bg=THEME["bg_card_alt"],
                cursor="hand2"
            )
            lbl_txt.pack(side=tk.LEFT)

            ind = tk.Frame(btn_f, bg=THEME["bg_card_alt"], height=2)
            ind.pack(fill=tk.X, side=tk.BOTTOM)

            handler = lambda e, sid=sub_id: self.select_sub_tab(sid)
            for w in (btn_f, inner, lbl_icon, lbl_txt, ind):
                if w:
                    w.bind("<Button-1>", handler)

            self.buttons[sub_id] = {
                "frame": btn_f,
                "inner": inner,
                "text": lbl_txt,
                "icon": lbl_icon,
                "indicator": ind,
                "icon_name": icon_name
            }

        if self.active_tab:
            self._update_visuals()

    def select_sub_tab(self, sub_id):
        if sub_id not in self.buttons:
            return
        if self.active_tab != sub_id:
            self.active_tab = sub_id
            self._update_visuals()
            if callable(self.on_tab_changed):
                self.on_tab_changed(sub_id)

    def _update_visuals(self):
        for sid, comp in self.buttons.items():
            is_active = (sid == self.active_tab)
            c_fg = THEME["primary"] if is_active else THEME["text_secondary"]
            c_bg = THEME["bg_card"] if is_active else THEME["bg_card_alt"]
            ind_c = THEME["primary"] if is_active else THEME["bg_card_alt"]

            comp["text"].config(fg=c_fg, bg=c_bg)
            comp["inner"].config(bg=c_bg)
            comp["frame"].config(bg=c_bg)
            comp["indicator"].config(bg=ind_c)

            if comp["icon"] and comp["icon_name"]:
                ico = render_vector_icon(comp["icon_name"], size=13, color=c_fg)
                comp["icon"].config(image=ico, bg=c_bg)
                comp["icon"].image = ico


class MiniTickerBar(tk.Frame):
    """
    Mini status bar permanen ramping yang hanya muncul saat pengguna membuka tab
    selain LIVE (TAGS, KAMUS, SYSTEM) agar tetap dapat melihat deteksi awalan dan kata teratas.
    """
    def __init__(self, parent, on_click=None, **kwargs):
        super().__init__(parent, bg="#0e1710", highlightthickness=1, highlightbackground=THEME["border"], **kwargs)
        self.on_click = on_click

        # Badge Awalan Aktif
        self.lbl_prefix_badge = tk.Label(
            self,
            text="...",
            font=("Segoe UI", 9, "bold"),
            bg=THEME["primary"],
            fg=THEME["text_dark"],
            padx=6,
            pady=1
        )
        self.lbl_prefix_badge.pack(side=tk.LEFT, padx=(4, 6), pady=2)

        # Label Rekomendasi Teratas
        self.lbl_top_word = tk.Label(
            self,
            text="Menunggu OCR...",
            font=("Segoe UI", 9, "bold"),
            bg="#0e1710",
            fg=THEME["text_primary"],
            anchor="w"
        )
        self.lbl_top_word.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=2)

        # Mode Indicator Pill
        self.lbl_mode_pill = tk.Label(
            self,
            text="DEFAULT",
            font=("Segoe UI", 7, "bold"),
            bg=THEME["bg_active"],
            fg=THEME["primary"],
            padx=5,
            pady=1
        )
        self.lbl_mode_pill.pack(side=tk.RIGHT, padx=6, pady=2)

        if callable(self.on_click):
            for w in (self, self.lbl_prefix_badge, self.lbl_top_word, self.lbl_mode_pill):
                w.bind("<Button-1>", lambda e: self.on_click())

    def update_ticker(self, prefix, top_word="", mode_name="DEFAULT", mode_color=None):
        p_text = prefix.strip().upper() if prefix else "-"
        self.lbl_prefix_badge.config(text=p_text)
        w_text = top_word.strip().upper() if top_word else "Tidak ada saran"
        self.lbl_top_word.config(text=w_text)
        self.lbl_mode_pill.config(text=mode_name.upper())
        if mode_color:
            self.lbl_mode_pill.config(fg=mode_color)


class CyberSwitch(tk.Frame):
    """
    Saklar toggle on/off modern ala cheat client.
    """
    def __init__(self, parent, text, initial_value=False, on_toggle=None, **kwargs):
        super().__init__(parent, bg=THEME["bg_card"], **kwargs)
        self.value = bool(initial_value)
        self.on_toggle = on_toggle

        self.lbl_text = tk.Label(
            self,
            text=text,
            font=("Segoe UI", 9),
            fg=THEME["text_primary"],
            bg=THEME["bg_card"],
            anchor="w"
        )
        self.lbl_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_switch = tk.Canvas(
            self,
            width=36,
            height=18,
            bg=THEME["bg_card"],
            highlightthickness=0,
            cursor="hand2"
        )
        self.btn_switch.pack(side=tk.RIGHT, padx=4)

        self.btn_switch.bind("<Button-1>", self._click)
        self.lbl_text.bind("<Button-1>", self._click)
        self.bind("<Button-1>", self._click)

        self._render()

    def _click(self, event=None):
        self.value = not self.value
        self._render()
        if callable(self.on_toggle):
            self.on_toggle(self.value)

    def set_value(self, val):
        self.value = bool(val)
        self._render()

    def _render(self):
        self.btn_switch.delete("all")
        # Track capsule
        track_color = THEME["primary"] if self.value else "#2b382d"
        thumb_color = THEME["text_dark"] if self.value else THEME["text_muted"]

        # Gambar kapsul
        self.btn_switch.create_oval(1, 1, 17, 17, fill=track_color, outline="")
        self.btn_switch.create_oval(19, 1, 35, 17, fill=track_color, outline="")
        self.btn_switch.create_rectangle(9, 1, 27, 17, fill=track_color, outline="")

        # Thumb bulatan
        if self.value:
            self.btn_switch.create_oval(19, 2, 34, 16, fill="#f1f6ef", outline="")
        else:
            self.btn_switch.create_oval(2, 2, 17, 16, fill=thumb_color, outline="")
