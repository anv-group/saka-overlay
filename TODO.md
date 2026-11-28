# TODO — SAKA Overlay

## Kamus & Tag

- [ ] LIVE -> Sort kata terpanjang, pendek. Filter only whitelist, only NOT whitelisted
- [x] Hapus kata dari kamus (untuk kamus custom).
- [x] KAMUS → Eksplorer default ke Akhiran instead of Awalan.
- [x] Dilarang duplikat tag.
- [x] Pisahkan kata yang ditambah secara manual dari kamus kbbi dan kamus contek
- [x] Untuk whitelist, blocklist, dan kata yang ditambahkan secara manual, datetime ditambahkan.

## System & Updater

- [ ] Test updater.
- [ ] Add logging (info, debug)
- [ ] Updater jika repository privated?
- [x] statistik mode CSV tidak update realtime
- [x] Updater jika user tidak memiliki `git` ternistall pada systemnya?
- [x] Remove all legacy preserving systems (seperti migrasi dari config lama -> baru)
- [x] Change emoji in SAMPEL panel to something else to avoid using emojis
- [x] SYSTEM -> DATABASE SINKRONISASI, TXT sudah tidak lagi akurat karena sekarang mengguanakan CSV.
- [x] Notifier for new update.
- [x] One instance only by default unless enabled.
- [x] Tombol Cek Update kurang feedback: tambahkan feedback seperti `"Mengecek <branch>"` atau yang lain.

## UI & UX

- [ ] Bottom status bar for database status, replacing db status icon in title bar
- [ ] Web UI yang bisa dibuka di device lain di local network yang sama.
- [ ] More themes (like One Dark Pro, etc.)
- [ ] Transparency & acrylic material
- [x] Tab KAMUS -> Eksplorer untuk Opsi Semua, KBBI, Contek, KBBI + Contek, Kamus+ dibuat model klik untuk enable/disable seperti checkbox daripada opsi pilihan salah satu seperti radiobox
- [x] Jika ada perubahan DB, icon di title bar flashing atau indikasi lainnya.
- [x] Pada tab SETTINGS, tampilkan juga commit message, tidak hanya commit hash.
- [x] Pada UI pendataan koreksi:
    - [x] Terlalu banyak border.
    - [x] Angka pada Kurang Tepat dan Tidak Dikenali menunjukkan 0 kecuali saat aktif. Jika Kurang Tepat tidak diklik, maka akan tetap 0; saat diklik, baru muncul jumlahnya serta muncul di menu kalibrasi (foto, file, terdeteksi, akurasi, status, dan awalan yang seharusnya). Begitu juga dengan Tidak Dikenali dan Semua; jika diklik Semua, maka angka juga muncul untuk Kurang Tepat dan Tidak Dikenali.
    - [x] Tombol Sebelumnya dan Berikutnya icon-nya double.
- [x] Test Area Scanner ubah menjadi Cek Area Scanner, lalu tidak usah mengecek deteksi ke OCR.

## DX & Repository

- [x] Pindahkan file-file yang unrelated (seperti file untuk deteksi gameplay dll) ke branch tersendiri agar branch utama tetap bersih.
- [x] Fix github workflows test.
- [x] Add prettier.

# Bug

- [x] Klik Enter saat pendataan koreksi di "tidak dikenali" membuka folder
