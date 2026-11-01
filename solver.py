import os

# Huruf akhiran yang sangat sulit untuk lawan sambung
HURUF_SULIT_AKHIRAN = ["x", "z", "q", "v", "j", "w", "f"]

class SambungKataSolver:
    def __init__(self, dictionary_path="kamus_lengkap.txt", blacklist_path="blacklist.txt"):
        self.dictionary_path = dictionary_path
        self.blacklist_path = blacklist_path
        self.words = []
        self.word_set = set()
        self.blacklisted_words = set()
        self.words_by_initial = {}
        self.load_blacklist()
        self.load_dictionary()

    def load_blacklist(self):
        """Memuat daftar kata yang di-blacklist dari blacklist.txt"""
        if not os.path.exists(self.blacklist_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            alt_path = os.path.join(base_dir, self.blacklist_path)
            if os.path.exists(alt_path):
                self.blacklist_path = alt_path

        self.blacklisted_words = set()
        if os.path.exists(self.blacklist_path):
            try:
                with open(self.blacklist_path, "r", encoding="utf-8") as f:
                    for line in f:
                        w = line.strip().lower()
                        if w and not w.startswith("#"):
                            self.blacklisted_words.add(w)
                print(f"[*] Blacklist dimuat: {len(self.blacklisted_words)} kata diblokir.")
            except Exception as e:
                print(f"[!] Error membaca blacklist: {e}")

    def blacklist_word(self, word):
        """Memasukkan kata ke blacklist dan menyimpannya ke blacklist.txt"""
        w = word.strip().lower()
        if not w:
            return False
        if w in self.blacklisted_words:
            return True
        self.blacklisted_words.add(w)
        try:
            with open(self.blacklist_path, "a", encoding="utf-8") as f:
                f.write(f"{w}\n")
            return True
        except Exception as e:
            print(f"[!] Gagal menulis ke blacklist.txt: {e}")
            return False

    def unblacklist_word(self, word):
        """Menghapus kata dari blacklist (Undo)"""
        w = word.strip().lower()
        if w in self.blacklisted_words:
            self.blacklisted_words.remove(w)
        try:
            with open(self.blacklist_path, "w", encoding="utf-8") as f:
                for bw in sorted(self.blacklisted_words):
                    f.write(f"{bw}\n")
            return True
        except Exception as e:
            print(f"[!] Gagal memperbarui blacklist.txt: {e}")
            return False

    def get_blacklisted_words(self):
        """Mengembalikan daftar kata yang di-blacklist terurut abjad"""
        return sorted(list(self.blacklisted_words))

    def load_dictionary(self):
        if not os.path.exists(self.dictionary_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            alt_path = os.path.join(base_dir, self.dictionary_path)
            if os.path.exists(alt_path):
                self.dictionary_path = alt_path

        word_set = set()
        if os.path.exists(self.dictionary_path):
            with open(self.dictionary_path, "r", encoding="utf-8") as f:
                for line in f:
                    w = line.strip().lower()
                    if w.isalpha() and len(w) >= 2:
                        word_set.add(w)
        else:
            print(f"[!] Warning: Kamus {self.dictionary_path} tidak ditemukan!")

        # Simpan dalam list terurut
        self.word_set = word_set
        self.words = sorted(list(word_set))
        self._index_words()
        print(f"[*] Solver siap dengan {len(self.words)} kata.")

    def has_word(self, word):
        """Memeriksa apakah kata sudah terdaftar di kamus"""
        return word.strip().lower() in self.word_set

    def add_word(self, word):
        """
        Menambahkan kata baru ke kamus (kamus_lengkap.txt) secara manual:
        - Validasi: huruf alfabet murni, panjang >= 2, wajib memiliki minimal 1 vokal.
        - Mengecek apakah kata sudah ada di kamus.
        - Jika ada di blacklist, otomatis dihapus dari blacklist.
        - Menyimpan ke kamus_lengkap.txt.
        - Mengindeks kata ke memori solver.
        """
        w = word.strip().lower()
        if not w.isalpha() or len(w) < 2:
            return False, "Kata harus berupa huruf alfabet murni (minimal 2 huruf)."
        
        vowels = set("aiueo")
        if not any(v in w for v in vowels):
            return False, "Kata harus memiliki minimal satu huruf vokal (A, I, U, E, O)."

        if w in self.word_set:
            return False, f"Kata '{w.upper()}' sudah terdaftar di dalam kamus."

        # Jika sebelumnya ada di blacklist, pulihkan dari blacklist
        if w in self.blacklisted_words:
            self.unblacklist_word(w)

        # Tambahkan ke memori
        self.word_set.add(w)
        self.words.append(w)
        self.words.sort()
        
        # Tambahkan ke index
        init1 = w[0]
        if init1 not in self.words_by_initial:
            self.words_by_initial[init1] = []
        self.words_by_initial[init1].append(w)
        self.words_by_initial[init1].sort()

        # Simpan ke file kamus_lengkap.txt
        try:
            with open(self.dictionary_path, "a", encoding="utf-8") as f:
                f.write(f"{w}\n")
            return True, f"Kata '{w.upper()}' berhasil ditambahkan ke kamus!"
        except Exception as e:
            return False, f"Gagal menulis ke file kamus: {e}"

    def _index_words(self):
        """Mengindeks kata berdasarkan 1 dan 2 huruf pertama untuk pencarian instan"""
        self.words_by_initial = {}
        for w in self.words:
            init1 = w[0]
            if init1 not in self.words_by_initial:
                self.words_by_initial[init1] = []
            self.words_by_initial[init1].append(w)

    def cari_jawaban(self, awalan_prefix, limit=12, mode_santai=False):
        """
        Mencari kata yang DIAWALI oleh `awalan_prefix`:
        Contoh:
        - Jika prefix 'BUK' -> mencari kata berawalan 'buk' (buka, bukan, bukti, bukit, dll)
        - Jika prefix 'M'   -> mencari kata berawalan 'm'
        - Jika prefix 'EX'  -> mencari kata berawalan 'ex' (exit, extra, expert, dll)
        - Jika prefix 'IX'  -> mencari kata berawalan 'ix' (ixora, ixodes, dll)
        
        Prioritas Jawaban (Mode Normal):
        1. Kata berakhiran 'X' (💥 Jebakan Mematikan)
        2. Kata berakhiran huruf sulit 'Z', 'Q', 'V', 'J', 'W', 'F' (⚡ Jebakan Sulit)
        3. Kata normal/seadanya (🛡️ Bertahan)

        Prioritas Jawaban (Mode Santai - tanpa X, Q, F):
        1. Kata berakhiran 'Z', 'V', 'J', 'W' (⚡ Jebakan Sulit Alternatif)
        2. Kata santai/normal yang nyaman diketik
        (Semua kata berakhiran X, Q, F atau mengandung X, Q dihilangkan)
        """
        prefix = "".join([c for c in awalan_prefix.lower() if c.isalpha()])
        if not prefix:
            return []

        # Ambil kandidat dari index 1 huruf pertama
        initial = prefix[0]
        pool = self.words_by_initial.get(initial, [])
        if not pool:
            return []

        # Filter kata yang diawali oleh prefix dan tidak ada di blacklist
        candidates = [w for w in pool if w.startswith(prefix) and w not in self.blacklisted_words]

        # Jika prefix lebih pendek dari 3 huruf, hindari kata yang sama persis dengan prefix
        if len(prefix) <= 2:
            candidates = [w for w in candidates if len(w) > len(prefix)]

        if not candidates:
            return []

        vowels = set("aiueo")
        jebakan_x = []
        jebakan_sulit = []
        kata_biasa = []

        if mode_santai:
            # Mode Santai: Kecualikan X, Q, dan F
            for w in candidates:
                # Wajib memiliki vokal
                if not any(v in w for v in vowels):
                    continue
                # Jangan gunakan kata yang berakhiran X, Q, F atau mengandung X, Q
                if w[-1] in ("x", "q", "f") or "x" in w or "q" in w:
                    continue
                
                last = w[-1]
                if last in ("z", "v", "j", "w"):
                    jebakan_sulit.append(w)
                else:
                    kata_biasa.append(w)
        else:
            # Mode Normal / Push Index / Brutal
            for w in candidates:
                # Saring kata singkatan aneh (harus memiliki setidaknya 1 huruf vokal jika > 3 huruf)
                if len(w) >= 4 and not any(v in w for v in vowels):
                    continue

                last = w[-1]
                if last == "x":
                    jebakan_x.append(w)
                elif last in HURUF_SULIT_AKHIRAN:
                    jebakan_sulit.append(w)
                else:
                    kata_biasa.append(w)

        # Urutkan berdasarkan panjang yang nyaman diketik (panjang 4-7 huruf paling prioritas)
        def sort_key(w):
            l = len(w)
            if 4 <= l <= 7:
                prio = 0
            elif l == 3:
                prio = 1
            elif l == 8:
                prio = 2
            else:
                prio = 3
            return (prio, l)

        jebakan_x.sort(key=sort_key)
        jebakan_sulit.sort(key=sort_key)
        kata_biasa.sort(key=sort_key)

        hasil = []
        for w in jebakan_x:
            hasil.append({"kata": w, "tipe": "JEBAKAN_X", "deskripsi": "Akhiran X (Mematikan)"})

        for w in jebakan_sulit:
            hasil.append({"kata": w, "tipe": "JEBAKAN_SULIT", "deskripsi": f"Akhiran {w[-1].upper()} (Sulit)"})

        for w in kata_biasa:
            desc = "Kata Santai" if mode_santai else "Kata Normal"
            hasil.append({"kata": w, "tipe": "BIASA", "deskripsi": desc})

        return hasil[:limit]
