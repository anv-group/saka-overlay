# 🎨 DESIGN.md — SAKA Overlay Design System & Rules
> **Panduan Desain & Standar Antarmuka SAKA Overlay (Tactical Cyber Cheat Client)**  
> Versi: 2.0 (Tactical Cyber Bamboo Edition)

---

## 📌 1. Filosofi & Karakter Visual

SAKA Overlay mengusung tema **"Tactical Cyber Cheat Client"** yang terinspirasi oleh antarmuka cheat FiveM modern:
- 🌿 **Latar Belakang Sangat Gelap (Ultra Dark Ground):** Menggunakan basis `#0b0f0c` dan panel `#141c15` untuk integrasi visual minim silau di atas layar game.
- ⚡ **Aksen Neon Bamboo Cyber:** Aksen utama adalah hijau limau neon `#a2c73e` dan `#c0ee3e` yang memberikan hierarki visual instan dan kontras tinggi.
- 🎯 **Minimalis & Non-Bloated:** Tata letak ringkas (*compact*), tidak ada elemen dekoratif yang mubazir, setiap tombol memiliki tujuan fungsionalitas game.
- 🚫 **Bebas Bevel & 3D Windows Legacy:** Semua tombol menggunakan `relief=tk.FLAT`, `bd=0`, dan `highlightthickness=0`.

---

## 🎨 2. Palet Token Warna Resmi (`THEME`)

Semua komponen antarmuka **WAJIB** merujuk pada token warna `THEME` di `ui_theme.py`. **DILARANG KERAS** menggunakan kode hex hardcoded di luar token ini:

| Token Token | Hex Code | Peran & Penggunaan |
| :--- | :--- | :--- |
| `bg_root` | `#0b0f0c` | Background utama window, dialog frameless, canvas dasar |
| `bg_card` | `#141c15` | Kontainer kartu, header, popdown combobox, surface elevated |
| `bg_card_alt` | `#101611` | Sub-container sekunder, panel filter |
| `bg_input` | `#0e150f` | Kolom input teks (`Entry`), field tertutup `TCombobox` |
| `bg_hover` | `#1c271e` | Background tombol saat hover atau tombol sekunder |
| `bg_active` | `#223124` | Indikator tab aktif, selected row |
| `border` | `#223024` | Garis pembatas 1px standar antarmuka |
| `border_focus` | `#a2c73e` | Garis pembatas highlight / fokus input |
| `primary` | `#a2c73e` | Aksen tombol utama, teks badge aktif, indicator tab |
| `accent_neon` | `#c0ee3e` | Aksen neon terang untuk hash commit & hover glow |
| `text_primary` | `#f1f6ef` | Teks utama putih kehijauan (kontras tinggi) |
| `text_secondary`| `#8d9f8c` | Teks pendukung, label informasi, subtitle |
| `text_muted` | `#556454` | Teks nonaktif, counter nonaktif |
| `text_dark` | `#0b0f0c` | Warna teks di atas badge neon terang (`primary` / `santai` / `danger`) |
| `danger` | `#f38ba8` | Peringatan, tombol hapus, trap tag, indikator LIVE OCR |
| `danger_bg` | `#381d28` | Latar belakang notifikasi bahaya / baris tag brutal |
| `warning` | `#f9e2af` | Indikator whitelist, status sedang menunggu |
| `santai` | `#89dceb` | Mode Santai (cyan cerah) |

---

## 🚫 3. Aturan Kritis Ikonografi (STRICT RULES)

### ❌ Dilarang Menggunakan Emoji OS
- **TIDAK BOLEH** menggunakan native emoji Windows/Unicode seperti ⚔️, 🌿, 🔥, 🚀, 📂, 📁, 🚩, ⚠️, ✏️, 💾, 🗑️, ◀️, ▶️, ➕, ✕, ⚡, 📌 di dalam label teks tombol, title window, maupun card.
- Emoji OS membuat antarmuka tampak amatir, tidak konsisten antar-versi Windows, dan merusak tata letak font monospace/semi-bold.

### ✅ Wajib Menggunakan Official Material Design Icons (MDI)
- Semua icon **WAJIB** menggunakan file PNG resmi 48dp dari `assets/icons/` yang di-render melalui fungsi `render_vector_icon(name, size, color, bg)`.
- Menggunakan pewarnaan dinamis C-Level Pillow (*Alpha Masking*) dengan in-memory cache instan (< 1ms execution, 0% CPU overhead).
- **Kombinasi Icon + Teks:** Pasang icon pada button menggunakan opsi `image=ico, compound="left", text=" LABEL"` dengan padding seimbang.

Daftar icon MDI yang tersedia di `assets/icons/`:
- Navigasi & Aksi: `play`, `stop`, `refresh`, `cloud_download`, `search`, `settings`, `sort`
- File & Data: `folder`, `edit`, `check`, `cross`, `plus`, `trash`, `link`, `tag`
- Simbol & Arah: `star`, `star_filled`, `flag`, `zap`, `book`, `chevron_down`, `chevron_up`, `arrow_back`, `arrow_forward`

---

## 🪟 4. Aturan Window & Custom Frameless Titlebar

1. **Window Utama (`self.root`):**
   - Wajib frameless (`overrideredirect(True)`).
   - Di sisi atas terdapat custom titlebar dengan tinggi 30px (`bg=THEME["bg_root"]`).
   - Titlebar **HANYA** memuat gambar logo vektor horizontal (`assets/logo_horizontal.png`).
   - **DILARANG** menambahkan duplikasi teks judul di samping logo (teks OS title tetap diset via `root.title(...)` untuk taskbar Windows).
   - Tombol Close (`✕`) diposisikan di sudut kanan atas dengan `bg=THEME["bg_root"]`, `fg=THEME["text_secondary"]`, dan hover merah terang `bg=THEME["danger"]`, `fg="#ffffff"`.
   - Tombol Restart (`⚡`) hanya muncul jika Mode Development aktif, dengan warna `warning` dan hover `bg_card`.

2. **Modal / Dialog Tambahan (`_create_clean_toplevel`):**
   - Semua jendela toplevel (Koreksi Sampel, Update, Settings, dll.) wajib menggunakan `_create_clean_toplevel`.
   - Latar belakang jendela: `THEME["bg_root"]` dengan highlight 1px `THEME["border"]`.
   - Titlebar modal: `bg=THEME["bg_root"]` dengan teks judul bersih tanpa emoji, dan tombol close `✕`.
   - Tombol `Escape` wajib menutup jendela seketika.

---

## 🔽 5. Standar Dropdown & Combobox (Anti-White Policy)

1. **Global Theme Requirement:**
   - Tkinter `ttk` **WAJIB** disetel ke tema `"clam"` pada level root (`style.theme_use("clam")`).
   - Jangan pernah membiarkan tema bawaan Windows (`"vista"` / `"winnative"`), karena akan memaksa kontrol combobox dirender warna putih native oleh sistem operasi.
2. **Prioritas Database Opsi Tkinter (Level 100):**
   - Popdown listbox combobox **WAJIB** diatur menggunakan prioritas `100` pada root dan toplevel:
   ```python
   root.option_add('*Listbox.background', THEME["bg_card"], 100)
   root.option_add('*Listbox.foreground', THEME["text_primary"], 100)
   root.option_add('*Listbox.selectBackground', THEME["primary"], 100)
   root.option_add('*Listbox.selectForeground', THEME["text_dark"], 100)
   ```
3. **Field Combobox Tertutup:**
   - Field `TCombobox` disetel ke `fieldbackground=THEME["bg_input"]`, `background=THEME["bg_card"]`, `foreground=THEME["text_primary"]`, dan `arrowcolor=THEME["primary"]`.

---

## 🔴 6. Indikator LIVE OCR pada Tab Non-LIVE

- Ketika pemain berada di luar tab `LIVE` (misal di tab `TAGS`, `KAMUS`, `SYSTEM`), `MiniTickerBar` otomatis tampil di bawah tab bar.
- `MiniTickerBar` **WAJIB** menggunakan gaya merah mencolok (`bg="#1a1114"`, `highlightbackground=THEME["danger"]`, dan badge `LIVE` berwarna `#f38ba8`) agar pengguna segera menyadari perubahan prefix game tanpa harus kembali ke tab LIVE.

---

## 🖱️ 7. Scrolling & Interaktivitas

- **Universal Recursive MouseWheel:** Semua container yang memiliki scrollbar (`Canvas` / `Listbox` / `Treeview`) wajib menerapkan binding `<MouseWheel>`, `<Button-4>`, dan `<Button-5>` secara rekursif ke seluruh widget anaknya menggunakan helper `bind_mousewheel_recursive()`.
- **Keyboard Auto-Focus:** Dialog pencarian/tambah kata wajib secara otomatis mengarahkan fokus kursor ke kolom input utama (`after(50, lambda: entry.focus_set())`) dan mendukung eksekusi seketika via tombol `Enter`.
