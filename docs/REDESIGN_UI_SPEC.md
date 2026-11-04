# 🎮 SPESIFIKASI DESAIN: SAKA OVERLAY - TACTICAL CYBER UI (BRANCH: redesign-ui)

Dokumen ini merangkum keputusan desain lengkap hasil sesi brainstorming untuk perombakan antarmuka SAKA Overlay menjadi UI bergaya modern *cheat client* (terinspirasi dari antarmuka FiveM TZX Cheat) yang elegan, responsif, dan berperforma tinggi.

---

## 🎨 1. Fondasi Visual & Tema Warna ("Tactical Cyber Bamboo")

Warna diturunkan secara harmonis dari identitas logo resmi di `assets/logo.svg` dan `assets/logo_saka.png`:

| Elemen UI | Nilai Hex | Keterangan & Filosofi |
| :--- | :--- | :--- |
| **Main Background** | `#0b0f0c` | Obsidian gelap pekat dengan sentuhan tint hijau sangat gelap |
| **Card / Surface** | `#141c15` | Latar kartu modul dengan kontras seimbang |
| **Border / Divider** | `#223024` | Garis tepi kartu 1px halus bergaya tactical |
| **Primary (Brand)** | `#a2c73e` | Warna hijau bambu ikonik dari logo SAKA |
| **Accent / Neon Glow**| `#c0ee3e` | Hijau neon tajam untuk tab aktif, underline neon, & focus outline |
| **Text Primary** | `#f1f6ef` | Teks utama putih gading bersih dan kontras tinggi |
| **Text Muted / Sub** | `#8d9f8c` | Teks pendukung abu-abu kehijauan lembut |
| **Danger / Brutal** | `#f38ba8` | Merah aksen untuk Mode Brutal, Blocklist, dan tombol tutup |
| **Warning / Whitelist**| `#f9e2af` | Kuning emas untuk bintang Whitelist |

---

## 🧭 2. Arsitektur Navigasi Utama (Top Icon Tab Strip)

Navigasi atas mengadopsi gaya horizontal ikonik *cheat injector* dengan 4 tab utama:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ [LOGO SAKA] SAKA OVERLAY     [⚡]                               [—][✕] │  <-- Title Bar Custom
├────────────────────────────────────────────────────────────────────────┤
│   [ ⚡ LIVE ]        [ 🏷️ TAGS ]        [ 📖 KAMUS ]       [ ⚙️ SYSTEM ] │  <-- 4 Tab Utama
│   ▔▔▔▔▔▔▔▔▔                                                            │  (Neon Lime Underline)
└────────────────────────────────────────────────────────────────────────┘
```

1. **Aset Ikon:** Ikon vektor outline monokrom tajam (Material 3 / SVGRepo), **bebas emoji OS bawaan**.
2. **Mini Status Bar Otomatis:**
   - **Tab LIVE:** Mini status bar **disembunyikan** (agar ruang kartu rekomendasi maksimal).
   - **Tab TAGS, KAMUS, SYSTEM:** Mini status bar **tampil ramping di bagian atas** berisi ticker prefix aktif, rekomendasi kata teratas, dan status mode game saat ini.

---

## 🕹️ 3. Rincian Desain Per Tab

### A. Tab 1: [ ⚡ LIVE ] (Ruang Kendali Saat Bermain)
Fokus 100% pada kecepatan baca OCR dan kenyamanan mengetik:

1. **Mode Switcher (Segmented Cyber Pill Bar):**
   - Terpasang tepat di atas prefix: `[ 🌿 SANTAI ] | [ ⚔️ DEFAULT ] | [ 🔥 BRUTAL ]`.
   - 1-klik untuk beralih mode secara instan.
2. **Kartu Awalan (Prefix Screen):**
   - Menampilkan awalan huruf deteksi OCR ukuran besar (`A`, `BU`, `EX`, dll.).
   - Dilengkapi kolom input *manual override* dengan fokus otomatis.
   - Tombol tangkap sampel salah `[ 🚩 Deteksi Salah (F2) ]`.
3. **Quick Bar Tag Kustom (Dynamic Multi-Row Wrap):**
   - Deretan tombol toggle tag kustom aktif dengan perhitungan lebar presisi (`Font.measure + padding`) agar tidak pernah terpotong keluar layar.
4. **Daftar Kartu Kata (Word Cards 60 FPS Pool):**
   - **Bintang Whitelist Cepat di Kiri:** `[ ☆ ]` / `[ ★ ]` (1-klik langsung masuk/keluar whitelist).
   - **Teks Kata:** Huruf besar putih tebal, diurutkan berdasarkan tier prioritas.
   - **Badge Kategori Berwarna:** Contoh `[Akhiran TI]`, `[Jebakan X]`, `[Konsonan Sulit]` dengan warna latar sesuai tag.
   - **Tombol Blocklist Cepat di Kanan:** `[ ✕ ]` (1-klik langsung memasukkan kata ke `blacklist.txt`).

---

### B. Tab 2: [ 🏷️ TAGS ] (Manajemen Mode Brutal & Tag Kustom)
Menggunakan **Sub-Tab Navigasi Ramping** untuk mencegah tampilan berjejal (*anti-bloated*):

```text
  [ 🔥 BRUTAL PRESET ]      [ 🏷️ KELOLA SEMUA TAG (44 Tag) ]
  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
```

1. **Sub-Tab [ 🔥 BRUTAL PRESET ]:**
   - Membuka daftar checklist tag mode brutal (misal `AMSI`, `KSO`, `RHU`, `TL`, `BD`).
   - Fitur *Click Anywhere* pada baris untuk toggle on/off.
   - Kontras tinggi: baris aktif marun pekat `#381d28` dengan badge `🔥 BRUTAL`.
2. **Sub-Tab [ 🏷️ KELOLA SEMUA TAG ]:**
   - Formulir pendaftaran akhiran kustom baru + pemilih warna Catppuccin.
   - Tombol sortir cepat (`🔤 A-Z`, `📊 Terbanyak`, `📏 Terpanjang`, `📏 Tersedikit`).
   - Seluruh 44+ tag kustom tertata rapi dalam kontainer scroll mulus terisolasi.
   - Semua preferensi disimpan ke `config.local.json` (kebal pembaruan git).

---

### C. Tab 3: [ 📖 KAMUS ] (Whitelist, Blocklist, & Eksplorer)
Dilengkapi **State Persistence** (mengingat sub-tab terakhir) dan **Auto-Focus Kursor**:

```text
  [ ⭐ WHITELIST ]    [ 🚫 BLOCKLIST ]    [ 🔍 EKSPLORER ]
  ▔▔▔▔▔▔▔▔▔▔▔▔
```

1. **Sub-Tab [ ⭐ WHITELIST ]:**
   - Menampilkan kata yang terbukti 100% valid di Roblox.
   - Input teks langsung fokus kursor saat tab dibuka ➔ Tekan `Enter` langsung menambahkan ke `whitelist.txt`.
   - Tombol aksi `[ 🗑️ Hapus ]` untuk mencabut whitelist.
2. **Sub-Tab [ 🚫 BLOCKLIST ]:**
   - Menampilkan daftar kata yang diblacklist dari rekomendasi bot.
   - Input teks fokus kursor ➔ Tekan `Enter` langsung menambahkan ke `blacklist.txt`.
   - Tombol aksi `[ ↩️ Pulihkan ]` untuk mengizinkan kembali kata tersebut.
3. **Sub-Tab [ 🔍 EKSPLORER ]:**
   - Penjelajah 147.000+ kosakata dengan filter:
     * Mode: `[ Awalan ]` | `[ Akhiran ]` | `[ Mengandung ]`
     * Sumber: `[ Semua ]` | `[ KBBI ]` | `[ Contek ]` | `[ Irisan Keduanya ]`
   - Input teks fokus kursor ➔ Tekan `Enter` langsung menambahkan kata baru ke `kamus_lengkap.txt`.
   - Tombol aksi instan 1-klik per baris: `[ ⭐ Whitelist ]` dan `[ 🚫 Blokir ]`.

---

### D. Tab 4: [ ⚙️ SYSTEM ] (Pengaturan Teknis & Informasi Status)
Disusun dalam 4 kartu modular *cyber dashboard*:

1. **Kartu Scanner & Area Layar:**
   - Koordinat ROI layar aktif + tombol `[ 🎯 Atur Area Layar ]` dan `[ 🔄 Reset Default ]`.
   - Selektor kecepatan pemindaian OCR (`100ms`, `250ms`, `500ms`).
2. **Kartu Shortcut & Hotkey Global:**
   - Status Hotkey `F2` (tangkap sampel kurang tepat non-blocking).
   - Tombol `[ 📝 Jendela Koreksi Sampel ]`.
3. **Kartu Preferensi & Dev Mode:**
   - Saklar toggle modern untuk `Always-on-Top` dan `Mode Development` (Tombol `⚡` restart).
4. **Kartu Informasi Sistem & Pembaruan:**
   - Data Git Aktual: Nama Branch (`redesign-ui`) & Short Hash Commit (`8c469b7`).
   - Mode Auto-Update: Pilihan interaktif `[ ● Tanya Dulu (Prompt) | ○ Otomatis | ○ Nonaktif ]`.
   - Branch Selector: Pilihan branch target GitHub (`dev`, `main`, dll.).
   - Statistik Kosakata Nyata: Total kosakata aktif (147,870+), jumlah whitelist terdaftar, jumlah blocklist, dan total tag kustom.
   - Tombol `[ 🔄 Periksa Pembaruan Sekarang ]` dan `[ 📁 Buka Folder App ]`.
   - Dialog Pembaruan Cyber Modal: Menampilkan jumlah commit baru dan ringkasan changelog sebelum eksekusi pull.
   - Proteksi Total Data: Konfigurasi lokal di `config.local.json` dijamin tidak tertimpa saat git pull berjalan.

---

## 🛠️ 4. Fondasi Teknis & Performa

- **Teknologi:** Murni **Native Python Tkinter + Pillow (PIL)**.
- **Nol Dependensi Baru:** Tidak memerlukan instalasi pip tambahan.
- **Performa 60 FPS:** Menggunakan *Widget Pooling* (daur ulang widget baris yang ada) sehingga memori hemat (< 60MB RAM) dan CPU tetap dingin (< 1% saat idle).
- **Integritas Penyimpanan:** Seluruh perubahan pengaturan dan tag disimpan secara persisten ke `config.local.json` sehingga kebal dari benturan Git pull atau branch checkout.
