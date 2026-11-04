"""
ui_theme.py
Fondasi Tema "Tactical Cyber Bamboo" & Micro Vector Icon Generator untuk SAKA Overlay.
Dibuat dengan Native Python Tkinter + Pillow (Image, ImageDraw) tanpa dependensi tambahan.
Menghasilkan aset ikon vektor tajam monokrom anti-aliased bebas emoji OS.
"""

from PIL import Image, ImageDraw, ImageTk
import tkinter as tk

# ==========================================
# PALET WARNA TACTICAL CYBER BAMBOO
# ==========================================
THEME = {
    # Backgrounds & Surface
    "bg_root": "#0b0f0c",         # Obsidian pekat beraksen kehijauan gelap
    "bg_card": "#141c15",         # Permukaan modul kartu kontras
    "bg_card_alt": "#101611",     # Sub-card / table header
    "bg_input": "#0e150f",        # Kolom input teks
    "bg_hover": "#1c271e",        # Latar saat mouse hover
    "bg_active": "#223124",       # Latar tombol / item aktif

    # Border & Dividers
    "border": "#223024",          # Garis tepi kartu 1px halus
    "border_focus": "#a2c73e",    # Garis tepi saat fokus input
    "divider": "#1a241b",         # Garis pemisah internal

    # Brand & Accents
    "primary": "#a2c73e",         # Hijau bambu khas logo SAKA
    "accent_neon": "#c0ee3e",     # Hijau neon elektrik tajam (tab active & underline)
    "accent_glow": "#33451e",     # Bayangan glow lembut di sekeliling elemen aktif

    # Typography / Texts
    "text_primary": "#f1f6ef",    # Teks utama putih gading tajam
    "text_secondary": "#8d9f8c",  # Teks sub/keterangan abu-abu kehijauan lembut
    "text_muted": "#556454",      # Teks nonaktif / placeholder
    "text_dark": "#0b0f0c",       # Teks hitam pekat (di atas badge terang)

    # Status & Mode Alerts
    "danger": "#f38ba8",          # Crimson merah (Brutal mode & Blocklist)
    "danger_bg": "#381d28",       # Latar merah marun pekat untuk baris aktif Brutal
    "danger_border": "#5e2333",   # Border marun
    "warning": "#f9e2af",         # Kuning emas hangat (Whitelist & stars)
    "warning_bg": "#332a18",      # Latar kuning temaram
    "santai": "#89dceb",          # Cyan segar untuk Mode Santai
    "santai_bg": "#152d33",       # Latar cyan temaram
    "default_mode": "#a6e3a1",    # Hijau terang untuk Mode Default
    "default_bg": "#1d3320",      # Latar hijau temaram
}

# Cache global PhotoImage agar tidak di-garbage-collect oleh Tkinter
_ICON_CACHE = {}


def render_vector_icon(name, size=20, color="#f1f6ef", bg=None, scale=4):
    """
    Menghasilkan ImageTk.PhotoImage berbasis vektor beresolusi tajam menggunakan
    Supersampling Anti-Aliasing (SSAA 4x) murni PIL ImageDraw (Material Design Style).
    """
    cache_key = (name, size, color, bg)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0) if bg is None else bg)
    draw = ImageDraw.Draw(img)

    s = canvas_size

    def p(x_pct, y_pct):
        return (x_pct * s, y_pct * s)

    stroke_w = max(1, int(1.8 * scale))

    if name == "zap":
        poly = [
            p(0.55, 0.05),
            p(0.18, 0.52),
            p(0.48, 0.52),
            p(0.38, 0.95),
            p(0.82, 0.45),
            p(0.52, 0.45),
            p(0.62, 0.05),
        ]
        draw.polygon(poly, fill=color)

    elif name == "play":
        poly = [p(0.25, 0.15), p(0.85, 0.50), p(0.25, 0.85)]
        draw.polygon(poly, fill=color)

    elif name == "stop":
        draw.rectangle([p(0.20, 0.20), p(0.80, 0.80)], fill=color)

    elif name == "tag":
        poly = [
            p(0.15, 0.45),
            p(0.45, 0.15),
            p(0.85, 0.15),
            p(0.85, 0.55),
            p(0.55, 0.85),
            p(0.15, 0.45)
        ]
        draw.line(poly, fill=color, width=stroke_w, joint="round")
        r = int(0.08 * s)
        cx, cy = p(0.70, 0.30)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    elif name == "book":
        draw.arc([p(0.12, 0.25), p(0.50, 0.78)], start=180, end=0, fill=color, width=stroke_w)
        draw.line([p(0.12, 0.35), p(0.12, 0.82)], fill=color, width=stroke_w)
        draw.line([p(0.50, 0.45), p(0.50, 0.92)], fill=color, width=stroke_w)
        draw.line([p(0.12, 0.82), p(0.50, 0.92)], fill=color, width=stroke_w)
        draw.arc([p(0.50, 0.25), p(0.88, 0.78)], start=180, end=0, fill=color, width=stroke_w)
        draw.line([p(0.88, 0.35), p(0.88, 0.82)], fill=color, width=stroke_w)
        draw.line([p(0.50, 0.92), p(0.88, 0.82)], fill=color, width=stroke_w)

    elif name == "settings":
        draw.line([p(0.15, 0.30), p(0.85, 0.30)], fill=color, width=stroke_w)
        draw.ellipse([p(0.30, 0.20), p(0.50, 0.40)], fill=color)
        draw.line([p(0.15, 0.70), p(0.85, 0.70)], fill=color, width=stroke_w)
        draw.ellipse([p(0.50, 0.60), p(0.70, 0.80)], fill=color)

    elif name == "star":
        pts = [
            p(0.50, 0.10), p(0.61, 0.36), p(0.89, 0.38), p(0.67, 0.56),
            p(0.74, 0.84), p(0.50, 0.69), p(0.26, 0.84), p(0.33, 0.56),
            p(0.11, 0.38), p(0.39, 0.36)
        ]
        draw.polygon(pts, outline=color, width=stroke_w)

    elif name == "star_filled":
        pts = [
            p(0.50, 0.10), p(0.61, 0.36), p(0.89, 0.38), p(0.67, 0.56),
            p(0.74, 0.84), p(0.50, 0.69), p(0.26, 0.84), p(0.33, 0.56),
            p(0.11, 0.38), p(0.39, 0.36)
        ]
        draw.polygon(pts, fill=color)

    elif name == "cross":
        draw.line([p(0.22, 0.22), p(0.78, 0.78)], fill=color, width=int(stroke_w * 1.2))
        draw.line([p(0.22, 0.78), p(0.78, 0.22)], fill=color, width=int(stroke_w * 1.2))

    elif name == "check":
        draw.line([p(0.18, 0.52), p(0.42, 0.76)], fill=color, width=int(stroke_w * 1.3))
        draw.line([p(0.42, 0.76), p(0.84, 0.26)], fill=color, width=int(stroke_w * 1.3))

    elif name == "trash":
        draw.line([p(0.20, 0.28), p(0.80, 0.28)], fill=color, width=stroke_w)
        draw.line([p(0.40, 0.20), p(0.60, 0.20)], fill=color, width=stroke_w)
        poly = [p(0.28, 0.28), p(0.32, 0.82), p(0.68, 0.82), p(0.72, 0.28)]
        draw.line(poly, fill=color, width=stroke_w)
        draw.line([p(0.44, 0.40), p(0.44, 0.70)], fill=color, width=max(1, stroke_w - scale))
        draw.line([p(0.56, 0.40), p(0.56, 0.70)], fill=color, width=max(1, stroke_w - scale))

    elif name == "refresh":
        draw.arc([p(0.20, 0.20), p(0.80, 0.80)], start=30, end=300, fill=color, width=stroke_w)
        arrow = [p(0.80, 0.45), p(0.80, 0.20), p(0.55, 0.20)]
        draw.line(arrow, fill=color, width=stroke_w)

    elif name == "search":
        r_box = [p(0.20, 0.20), p(0.62, 0.62)]
        draw.ellipse(r_box, outline=color, width=stroke_w)
        draw.line([p(0.54, 0.54), p(0.82, 0.82)], fill=color, width=int(stroke_w * 1.3))

    elif name == "plus":
        draw.line([p(0.50, 0.20), p(0.50, 0.80)], fill=color, width=stroke_w)
        draw.line([p(0.20, 0.50), p(0.80, 0.50)], fill=color, width=stroke_w)

    elif name == "folder":
        poly = [
            p(0.15, 0.35), p(0.40, 0.35), p(0.50, 0.45),
            p(0.85, 0.45), p(0.85, 0.78), p(0.15, 0.78), p(0.15, 0.35)
        ]
        draw.line(poly, fill=color, width=stroke_w, joint="round")

    elif name == "chevron_down":
        draw.line([p(0.25, 0.38), p(0.50, 0.63)], fill=color, width=stroke_w)
        draw.line([p(0.50, 0.63), p(0.75, 0.38)], fill=color, width=stroke_w)

    elif name == "chevron_up":
        draw.line([p(0.25, 0.62), p(0.50, 0.37)], fill=color, width=stroke_w)
        draw.line([p(0.50, 0.37), p(0.75, 0.62)], fill=color, width=stroke_w)

    elif name == "flag":
        draw.line([p(0.25, 0.15), p(0.25, 0.85)], fill=color, width=stroke_w)
        poly = [p(0.25, 0.20), p(0.75, 0.35), p(0.25, 0.50)]
        draw.polygon(poly, fill=color)

    elif name == "edit":
        # Pensil Material Icon
        poly = [p(0.20, 0.80), p(0.20, 0.65), p(0.65, 0.20), p(0.80, 0.35), p(0.35, 0.80), p(0.20, 0.80)]
        draw.line(poly, fill=color, width=stroke_w)
        draw.line([p(0.20, 0.80), p(0.35, 0.80)], fill=color, width=stroke_w)

    elif name == "link":
        # Material Link icon
        draw.arc([p(0.15, 0.35), p(0.55, 0.75)], start=90, end=270, fill=color, width=stroke_w)
        draw.arc([p(0.45, 0.25), p(0.85, 0.65)], start=270, end=90, fill=color, width=stroke_w)
        draw.line([p(0.35, 0.55), p(0.65, 0.45)], fill=color, width=stroke_w)

    else:
        draw.rectangle([p(0.3, 0.3), p(0.7, 0.7)], fill=color)

    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(resized)
    _ICON_CACHE[cache_key] = photo
    return photo
