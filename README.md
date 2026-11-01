# 🎮 Roblox Sambung Kata Assistant & Auto Solver

Asisten cerdas pendamping bermain game **Roblox Sambung Kata** ([Mainkan di Roblox](https://www.roblox.com/games/130342654546662/Sambung-Kata)).

Aplikasi ini secara otomatis mendeteksi kotak awalan huruf giliran Anda di layar, memilihkan kata serangan terbaik dari kamus **147.870+ kata**, dan dapat langsung menyalinnya ke clipboard sehingga Anda tinggal menekan `Ctrl + V` lalu `Enter` di dalam game!

---

## ⚡ Panduan Kilat 1 Menit (Quick Start)

1. **Buka Roblox** dan masuk ke room permainan **Sambung Kata**.
2. **Jalankan Asisten:** Klik ganda file **`run.bat`** (atau jalankan `python main.py`).
3. **Tentukan Area Huruf:**
   - Klik tombol **`🎯 Set Area Layar`**.
   - Layar akan meredup. Tarik kotak seleksi menggunakan mouse tepat mengelilingi kotak putih tempat huruf giliran muncul di game Roblox.
4. **Mulai Main:**
   - Centang **`📋 Auto-copy sisa kata`** (atau ketik manual dengan melihat panduan sisa kata di layar).
   - Klik tombol **`▶️ Mulai Auto-Scan`**.
   - Saat giliran Anda tiba, sisa kata (tanpa awalan) langsung tersalin otomatis atau dapat diketik kilat. Jika menggunakan auto-copy, cukup tekan **`Ctrl + V`** di kolom input Roblox lalu tekan **`Enter`**!

---

## 🎯 Panduan Fitur & Tombol Aplikasi

| Tombol / Fitur | Fungsi & Cara Pakai |
| :--- | :--- |
| **`🎯 Set Area Layar`** | Menentukan posisi kotak putih tempat awalan kata muncul di Roblox. Hanya perlu diatur satu kali (otomatis tersimpan untuk pemakaian berikutnya). |
| **`👁️ Tes Area`** | Menampilkan cuplikan gambar area yang telah dipilih untuk memastikan kotak tidak terpotong. |
| **`▶️ Mulai Auto-Scan`** | Menjalankan pemindaian layar secara otomatis dan *real-time*. |
| **`⏹️ Stop Scan`** | Menghentikan pemindaian otomatis (misalnya saat sedang istirahat bermain). |
| **`⚡ Kecepatan Scan`** | Mengatur interval pengecekan layar: **100ms (Ekstrem)**, **150ms (Kilat)**, **250ms (Cepat)**, atau **500ms (Santai)**. Dilengkapi optimasi *Frame-Diff* sehingga scan super kilat tidak membebani CPU. |
| **`📋 Auto-copy sisa kata`** | Bila dicentang, **sisa huruf yang harus diketik** (tanpa awalan) langsung disalin otomatis ke clipboard. Di game Anda tinggal menekan `Ctrl + V` lalu `Enter`! |
| **`🌿 Mode Santai`** | **Aktifkan jika bermain di room Mode Santai!** Menyaring dan membuang kata yang mengandung/berakhiran huruf terlarang (**X, Q, dan F**). |
| **`🚩 Deteksi Salah (F2)`** | **Screenshot Seketika (1-Klik):** Jika saat bermain ada huruf yang salah terbaca, langsung tekan **`F2`**. Gambar langsung tersimpan seketika ke `sample/kurang_tepat/` tanpa popup dialog yang mengganggu tempo cepat permainan. |
| **`📝 Koreksi (N)`** | **Pendataan Koreksi:** Membuka antarmuka visual untuk mereview dan melabeli screenshot salah deteksi (baik dari manual `sample/kurang_tepat/` maupun auto-save `sample/tidak_dikenali/`), melihat gambar diperbesar, dan menginput awalan yang benar dengan menekan `Enter`. |
| **Tombol Alternatif Huruf** | Jika sistem membaca huruf yang memiliki kemiripan bentuk (seperti `G`, `C`, `D`, `O`), tombol pilihan alternatif akan muncul (contoh: `[G] [C]`). Klik huruf yang benar untuk beralih instan. |
| **`⚡ Cari Kata Cepat (Manual)`** | Kolom input manual di bagian bawah. Ketik 1–3 huruf awalan lalu tekan `Enter` jika ingin mencari kata tanpa menggunakan scanner layar. |
| **`➕ Kamus`** | Menambahkan kata baru ke `kamus_lengkap.txt` secara permanen. Dilengkapi validasi vokal otomatis, pengecekan duplikasi, dan pratinjau tipe prioritas (*Tier Jebakan*). |
| **`🚫 Blocklist`** | Membuka jendela **Kelola Blocklist Kata** untuk melihat semua kata yang diblokir, mencari/memfilter kata, menghapus kata dari daftar blokir, menambah kata blokir baru, atau membuka file `blacklist.txt` langsung. |
| **Tombol Blacklist `❌`** | Menghapus kata yang ditolak di Roblox dari rekomendasi tanpa mengubah file kamus utama. Kata otomatis tercatat ke `blacklist.txt` (bisa di-*undo* dengan tombol `↩️ Batalkan`). |
| **Tampilan Kartu & Klik Salin** | Menampilkan kata penuh (seperti `SEX`, `COMPLEX`, `BUKU`). Klik kartu mana saja untuk langsung menyalin sisa huruf tersebut ke clipboard. |

---

## 💥 Strategi Kata & Trik Menang

Aplikasi ini dirancang bukan sekadar untuk menjawab, melainkan untuk **memenangkan permainan** dengan taktik serangan:

### 1. 💥 Tier 1: JEBAKAN X (Serangan Mematikan)
Bot memprioritaskan kata-kata sah yang berakhiran huruf **`X`** (seperti `SEX`, `COMPLEX`, `PARADOX`, `DETOX`, `BOX`, `FAX`, `BODREX`, `LATEX`). Lawan berikutnya akan dipaksa mencari kata yang berawalan huruf **X** yang sangat terbatas di Roblox, sehingga lawan 95% akan kehabisan waktu dan tereliminasi.

### 2. ⚡ Tier 2: JEBAKAN SULIT
Jika tidak ada kata berakhiran X, bot akan menawarkan kata berakhiran konsonan langka: **`Z`**, **`Q`**, **`V`**, **`J`**, **`W`**, dan **`F`**.

### 3. 🛡️ Tier 3: NORMAL
Kata-kata bahasa Indonesia baku KBBI yang pendek (3–6 huruf) sehingga sangat cepat dan mudah diketik secara manual jika waktu giliran Anda menipis.

### 4. 🌿 Mode Santai (Tanpa X, Q, F)
Khusus di room *Mode Santai*, pemain dilarang menggunakan huruf **X**, **Q**, dan **F**. Saat toggle **`🌿 Mode Santai`** dinyalakan, bot secara otomatis:
- Menghapus semua kata yang mengandung atau berakhiran `X, Q, F`.
- Mengalihkan serangan ke akhiran sulit yang sah (**`Z, V, J, W`**).
- Menyediakan kata santai yang umum dan dijamin valid di Roblox.

---

## 📚 Kamus Lengkap & Terpercaya (147.870+ Kata)

Kamus bawaan aplikasi ini merupakan gabungan cerdas (*Hybrid Merge*):
- **KBBI Daring Edisi VI:** Kosakata baku bahasa Indonesia.
- **Basis Data Contek Sambung Kata:** Mencakup 108.344 kata yang sering lolos di server Roblox, termasuk kata populer dan gaul (seperti `aho`, `alo`, `wibu`, `noob`, `pro`, `roblox`).
- **Pembersihan Kata Asing:** Kata bahasa Inggris murni yang ditolak oleh sistem Roblox telah dibersihkan (misal: bot selalu menyarankan `klimaks`, bukan `climax`).
- **Validasi Struktur:** Setiap kata wajib memiliki minimal satu vokal untuk menghindari singkatan aneh yang tidak diterima game.

---

## 💡 Tips & Kenyamanan Bermain

- **Jendela Selalu di Atas (*Always on Top*):** Jendela asisten otomatis mengambang di atas jendela Roblox, sehingga Anda bisa meletakkannya di sudut kiri/kanan layar tanpa tertutup game.
- **Mendukung Segala Layar:** Kompatibel dengan semua resolusi monitor (termasuk 1920x1080, 1920x1200) dan pengaturan Windows Display Scaling (100%, 125%, 150%).
- **Intip Lebih Awal:** Biarkan tombol **`▶️ Mulai Auto-Scan`** menyala bahkan saat pemain lain sedang giliran. Saat huruf pemain lain muncul, Anda bisa melihat opsi kata lebih cepat sebelum giliran Anda tiba.

---

## ❓ Tanya Jawab & Kendala Umum (FAQ)

### Q: Apakah akun Roblox saya aman dari ban?
**A:** Sangat aman. Aplikasi ini bekerja 100% dari luar Roblox sebagai asisten visual. Aplikasi hanya membaca tangkapan layar (screenshot kotak putih) dan menyalin teks ke clipboard Windows Anda. Tidak ada injeksi memori, modifikasi file game, atau intervensi bot ke proses Roblox.

### Q: Teks awalan di game tidak terbaca atau akurasinya rendah?
1. Klik tombol **`👁️ Tes Area`** untuk melihat apakah kotak seleksi pas mengelilingi kotak putih huruf.
2. Jika posisi game bergeser atau resolusi Roblox berubah, klik kembali **`🎯 Set Area Layar`** dan buat kotak baru di sekeliling kotak putih.
3. Pastikan tidak ada jendela lain atau avatar pemain yang menutupi kotak putih di dalam game.

### Q: Saat bermain ada huruf yang salah terdeteksi?
Cukup tekan tombol **`F2`** pada keyboard! Sistem akan seketika mengambil screenshot dan menyimpannya langsung ke folder `sample/kurang_tepat/` tanpa memunculkan popup yang mengganggu fokus permainan. Setelah selesai bermain, buka menu **`📝 Koreksi`** untuk mendata huruf yang benar (tekan `Enter` untuk menyimpan, atau tekan `Del` untuk menghapus sampel langsung tanpa konfirmasi).

### Q: Aplikasi tidak mau terbuka saat klik `run.bat`?
Pastikan Anda sudah menginstal **Python** di komputer Anda (versi 3.10 ke atas) dan mencentang opsi *"Add Python to PATH"* saat proses instalasi Python.
