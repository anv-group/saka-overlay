<div align="center">

<img src="assets/logo_horizontal.png" alt="SAKA Overlay" width="420" />

</div>

SAKA Overlay is a Windows overlay assistant for the Roblox game [Sambung Kata](https://www.roblox.com/games/130342654546662/Sambung-Kata). It reads the starting letters on your screen and suggests the best words to play.

SAKA Overlay adalah aplikasi overlay untuk game Roblox Sambung Kata. Aplikasi ini membaca awalan huruf giliran Anda langsung dari layar, lalu menampilkan daftar kata yang bisa dipakai. Rekomendasi diprioritaskan pada kata yang menyulitkan lawan, dan Anda tetap mengetik sendiri di game.

## Fitur Utama

- **Deteksi otomatis:** membaca awalan huruf giliran Anda langsung dari layar.
- **Rekomendasi kata:** menampilkan daftar kata berawalan tersebut, dengan prioritas pada kata yang sulit dilanjutkan lawan.
- **Tiga mode:** Normal, Santai (menyaring kata berhuruf X, Q, dan F), serta Brutal (preset akhiran khusus).
- **Akhiran kustom:** tambah, urutkan, dan aktifkan akhiran pilihan Anda sendiri.
- **Kamus pribadi:** whitelist untuk kata yang pasti diterima, blocklist untuk kata yang ditolak game, dan eksplorer untuk mencari kata.

## Tampilan

**LIVE:** awalan yang terbaca dan daftar rekomendasi kata.

<img src="docs/screenshots/live_running.png" alt="Tab LIVE" width="320" />

**MODE:** mengelola akhiran dan memilih mode permainan.

<img src="docs/screenshots/mode_kelola.png" alt="Tab MODE" width="320" />

**KAMUS:** whitelist, blocklist, dan eksplorer kata.

<img src="docs/screenshots/kamus_whitelist.png" alt="Tab KAMUS" width="320" />

**SYSTEM:** area scanner, tampilan, dan hotkey.

<img src="docs/screenshots/system.png" alt="Tab SYSTEM" width="320" />

## Instalasi

Prasyarat:

- Windows 10 atau 11
- [Python](https://www.python.org/downloads/) 3.10 atau lebih baru (centang "Add Python to PATH" saat instalasi)

Langkah:

1. Unduh repositori ini (Code, lalu Download ZIP) dan ekstrak, atau clone:
    ```
    git clone https://github.com/anv-group/saka-overlay.git
    ```
2. Double click `run.bat`. Dependensi akan diinstall otomatis jika belum ada.

Alternatif lewat terminal:

```
pip install -r requirements.txt
python main.py
```

## Cara Penggunaan

1. Buka Roblox Sambung Kata, lalu jalankan SAKA Overlay.
2. Buka tab **SYSTEM**, klik **Atur Area Scanner**, lalu tarik kotak di sekitar kotak putih berisi awalan huruf.
3. Klik **Cek Area Scanner** untuk memastikan posisinya tepat.
4. Kembali ke tab **LIVE**, pilih mode (Normal, Santai, atau Brutal), lalu tekan **Mulai** atau `F1`.
5. Saat giliran Anda, lihat daftar rekomendasi kata berawalan huruf yang terbaca, lalu ketik kata pilihan Anda secara manual di game.
6. Gunakan **Whitelist** (`F3`) untuk menyimpan kata bagus yang Anda sukai dan sudah pasti bisa dipakai, misalnya kata berakhiran sulit. Kata tersebut akan muncul di urutan teratas.
7. Gunakan **Blocklist** (`F4`) untuk memblokir kata yang masih muncul di rekomendasi tetapi tidak bisa dipakai di game.

## Hotkey

Semua hotkey dapat diubah di tab **SYSTEM**.

| Aksi             | Tombol |
| :--------------- | :----: |
| Mulai / Hentikan |  `F1`  |
| Flag Kesalahan   |  `F2`  |
| Whitelist Kata   |  `F3`  |
| Blacklist Kata   |  `F4`  |
| Akhiran Baru     |  `F6`  |
| Kata Baru        |  `F7`  |

Ganti Mode kosong secara bawaan dan dapat diisi sendiri. Saat kotak input (F3, F4, F6, F7) terbuka, kursor langsung aktif, dan setelah `Enter` fokus kembali ke game.

## Catatan

- Hanya untuk Windows 10 dan 11.
- Aplikasi hanya membaca layar dan menampilkan rekomendasi. Aplikasi tidak mengirim input ke game, jadi Anda tetap mengetik sendiri.
- Pengaturan pribadi (area, akhiran, mode, hotkey) disimpan lokal dan tidak hilang saat aplikasi diperbarui.
- Flag Kesalahan (`F2`) menyimpan tangkapan layar saat deteksi salah baca, untuk membantu perbaikan.
