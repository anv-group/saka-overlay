import os

# Huruf akhiran yang sangat sulit untuk lawan sambung
HURUF_SULIT_AKHIRAN = ["x", "z", "q", "v", "j", "w", "f"]

class SambungKataSolver:
    def __init__(
        self,
        dictionary_path="kamus_lengkap.txt",
        blacklist_path="blacklist.txt",
        whitelist_path="whitelist.txt",
        kbbi_path="kamus_kbbi.txt",
        contek_path="kamus_contek.txt",
        use_kbbi=True,
        use_contek=True
    ):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.dictionary_path = os.path.join(base_dir, dictionary_path) if not os.path.isabs(dictionary_path) else dictionary_path
        self.blacklist_path = os.path.join(base_dir, blacklist_path) if not os.path.isabs(blacklist_path) else blacklist_path
        self.whitelist_path = os.path.join(base_dir, whitelist_path) if not os.path.isabs(whitelist_path) else whitelist_path
        self.kbbi_path = os.path.join(base_dir, kbbi_path) if not os.path.isabs(kbbi_path) else kbbi_path
        self.contek_path = os.path.join(base_dir, contek_path) if not os.path.isabs(contek_path) else contek_path
        
        self.use_kbbi = use_kbbi
        self.use_contek = use_contek

        self.kbbi_set = set()
        self.contek_set = set()
        self.custom_set = set()
        self.word_set = set()
        self.words = []
        self.blacklisted_words = set()
        self.whitelisted_words = set()
        self.words_by_initial = {}
        self.custom_endings = []
        self.tier0_sort_mode = "default"  # "default" atau "tag_order"

        self.load_blacklist()
        self.load_whitelist()
        self.load_dictionary()

    def load_blacklist(self):
        """Memuat daftar kata yang di-blacklist dari blacklist.txt"""
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

    def load_whitelist(self):
        """Memuat daftar kata terverifikasi dari whitelist.txt"""
        self.whitelisted_words = set()
        if os.path.exists(self.whitelist_path):
            try:
                with open(self.whitelist_path, "r", encoding="utf-8") as f:
                    for line in f:
                        w = line.strip().lower()
                        if w and not w.startswith("#") and w.isalpha() and len(w) >= 2:
                            self.whitelisted_words.add(w)
                print(f"[*] Whitelist dimuat: {len(self.whitelisted_words)} kata terverifikasi.")
            except Exception as e:
                print(f"[!] Error membaca whitelist: {e}")

    def whitelist_word(self, word):
        """
        Memasukkan kata ke whitelist dan menyimpannya ke whitelist.txt:
        - Jika kata ada di blacklist, otomatis dihapus dari blacklist.
        - Kata langsung aktif di memori pencarian solver O(1) tanpa perlu menambah file kamus.
        - Menjadi prioritas teratas di kategorinya saat dicari.
        """
        w = word.strip().lower()
        if not w or not w.isalpha() or len(w) < 2:
            return False

        # Jika ada di blacklist, pulihkan
        if w in self.blacklisted_words:
            self.unblacklist_word(w)

        if w in self.whitelisted_words:
            return True

        self.whitelisted_words.add(w)
        try:
            folder = os.path.dirname(self.whitelist_path)
            if folder and not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            with open(self.whitelist_path, "a", encoding="utf-8") as f:
                f.write(f"{w}\n")
        except Exception as e:
            print(f"[!] Gagal menulis ke whitelist.txt: {e}")
            return False

        # Pastikan kata juga langsung hidup di memori aktif solver
        if w not in self.word_set:
            self.word_set.add(w)
            self.words.append(w)
            self.words.sort()
            init1 = w[0]
            if init1 not in self.words_by_initial:
                self.words_by_initial[init1] = []
            self.words_by_initial[init1].append(w)
            self.words_by_initial[init1].sort()

        return True

    def unwhitelist_word(self, word):
        """Menghapus kata dari whitelist"""
        w = word.strip().lower()
        if w in self.whitelisted_words:
            self.whitelisted_words.remove(w)
        try:
            folder = os.path.dirname(self.whitelist_path)
            if folder and not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            with open(self.whitelist_path, "w", encoding="utf-8") as f:
                f.write("# Daftar kata yang di-whitelist (Terbukti valid di game Roblox & Prioritas Utama di kategorinya)\n")
                for ww in sorted(self.whitelisted_words):
                    f.write(f"{ww}\n")
            # Jika kata tidak ada di kamus asal (bukan bagian kbbi/contek/custom), rebuild memori aktif
            if w not in self.kbbi_set and w not in self.contek_set and w not in self.custom_set:
                self._rebuild_active_words()
            return True
        except Exception as e:
            print(f"[!] Gagal memperbarui whitelist.txt: {e}")
            return False

    def is_whitelisted(self, word):
        """Mengecek apakah kata ada di whitelist"""
        return word.strip().lower() in self.whitelisted_words

    def get_whitelisted_words(self):
        """Mengembalikan daftar kata whitelist terurut abjad"""
        return sorted(list(self.whitelisted_words))

    def _read_word_file(self, fpath):
        """Membaca file kata dan menyaring kata yang valid (alpha, min 2 huruf, punya vokal)"""
        words = set()
        if not os.path.exists(fpath):
            return words
        vowels = set("aiueo")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    w = line.strip().lower()
                    if w.isalpha() and len(w) >= 2 and any(v in w for v in vowels):
                        words.add(w)
        except Exception as e:
            print(f"[!] Gagal membaca {fpath}: {e}")
        return words

    def load_dictionary(self):
        """Memuat kosakata dari KBBI dan Contek Sambung Kata ke memori"""
        # 1. Muat KBBI
        if os.path.exists(self.kbbi_path):
            self.kbbi_set = self._read_word_file(self.kbbi_path)
        else:
            # Fallback ke kata_kbbi.txt jika kamus_kbbi.txt belum dibuat
            alt_kbbi = os.path.join(os.path.dirname(self.kbbi_path), "kata_kbbi.txt")
            if os.path.exists(alt_kbbi):
                self.kbbi_set = self._read_word_file(alt_kbbi)

        # 2. Muat Contek Sambung Kata
        if os.path.exists(self.contek_path):
            self.contek_set = self._read_word_file(self.contek_path)

        # 3. Muat kata custom / warisan dari kamus_lengkap.txt
        if os.path.exists(self.dictionary_path):
            lengkap_set = self._read_word_file(self.dictionary_path)
            # Kata yang ada di kamus_lengkap tapi tidak ada di kbbi/contek dianggap custom
            self.custom_set = lengkap_set - (self.kbbi_set | self.contek_set)
        else:
            self.custom_set = set()

        self._rebuild_active_words()
        print(f"[*] Solver siap: KBBI={len(self.kbbi_set)}, Contek={len(self.contek_set)}, Total Aktif={len(self.words)} kata.")

    def _rebuild_active_words(self):
        """Membangun ulang daftar kata aktif sesuai sumber kamus yang dipilih"""
        active = set()
        if self.use_kbbi:
            active.update(self.kbbi_set)
        if self.use_contek:
            active.update(self.contek_set)
        
        # Kata custom dan kata whitelist selalu aktif
        active.update(self.custom_set)
        active.update(self.whitelisted_words)

        # Keamanan: Jika kedua sumber dimatikan oleh user, aktifkan setidaknya satu
        if not active:
            if self.kbbi_set:
                self.use_kbbi = True
                active.update(self.kbbi_set)
            elif self.contek_set:
                self.use_contek = True
                active.update(self.contek_set)

        self.word_set = active
        self.words = sorted(list(self.word_set))
        self._index_words()

    def set_dict_sources(self, use_kbbi=True, use_contek=True):
        """
        Mengubah sumber kamus yang aktif (KBBI, Contek, atau keduanya).
        Menghasilkan pembaruan indeks instan di memori.
        """
        if not use_kbbi and not use_contek:
            # Cegah kedua sumber nonaktif bersamaan
            return False, len(self.words), "Minimal satu sumber kamus harus dipilih!"
        
        self.use_kbbi = bool(use_kbbi)
        self.use_contek = bool(use_contek)
        self._rebuild_active_words()
        return True, len(self.words), f"Kamus aktif diperbarui ({len(self.words):,} kata)."

    def has_word(self, word):
        """Memeriksa apakah kata sudah terdaftar di kamus aktif"""
        return word.strip().lower() in self.word_set

    def add_word(self, word):
        """
        Menambahkan kata baru ke kamus (kamus_lengkap.txt & kamus_contek.txt) secara manual:
        - Validasi: huruf alfabet murni, panjang >= 2, wajib memiliki minimal 1 vokal.
        - Mengecek apakah kata sudah ada di kamus aktif.
        - Jika ada di blacklist, otomatis dihapus dari blacklist.
        - Menyimpan ke file kamus lokal.
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
        self.custom_set.add(w)
        self.contek_set.add(w)
        self.word_set.add(w)
        self.words.append(w)
        self.words.sort()
        
        # Tambahkan ke index
        init1 = w[0]
        if init1 not in self.words_by_initial:
            self.words_by_initial[init1] = []
        self.words_by_initial[init1].append(w)
        self.words_by_initial[init1].sort()

        # Simpan persisten ke kamus_lengkap.txt dan kamus_contek.txt
        try:
            with open(self.dictionary_path, "a", encoding="utf-8") as f:
                f.write(f"{w}\n")
            if os.path.exists(self.contek_path):
                with open(self.contek_path, "a", encoding="utf-8") as f:
                    f.write(f"{w}\n")
            return True, f"Kata '{w.upper()}' berhasil ditambahkan ke kamus!"
        except Exception as e:
            return False, f"Gagal menulis ke file kamus: {e}"

    def _index_words(self):
        """Mengindeks kata berdasarkan 1 huruf pertama untuk pencarian instan O(1)"""
        self.words_by_initial = {}
        for w in self.words:
            init1 = w[0]
            if init1 not in self.words_by_initial:
                self.words_by_initial[init1] = []
            self.words_by_initial[init1].append(w)

    def set_custom_endings(self, custom_endings):
        """
        Mengatur daftar akhiran kustom (Custom Traps) dengan prioritas super (di atas X).
        Format:
        [
            {"suffix": "NS", "name": "Akhiran NS", "enabled": True, "color": "#cba6f7"},
            {"suffix": "NGK", "name": "Akhiran NGK", "enabled": True, "color": "#f5c2e7"}
        ]
        atau list of string: ["NS", "NGK"]
        """
        self.custom_endings = []
        if not custom_endings:
            return
        for item in custom_endings:
            if isinstance(item, str):
                s = item.strip().lower()
                if s:
                    self.custom_endings.append({
                        "suffix": s,
                        "name": f"Akhiran {s.upper()}",
                        "enabled": True,
                        "color": "#cba6f7"
                    })
            elif isinstance(item, dict):
                s = item.get("suffix", "").strip().lower()
                if s:
                    self.custom_endings.append({
                        "suffix": s,
                        "name": item.get("name") or f"Akhiran {s.upper()}",
                        "enabled": bool(item.get("enabled", True)),
                        "color": item.get("color", "#cba6f7")
                    })

    def set_tier0_sort_mode(self, mode):
        """
        Mengatur mode pengurutan kata pada Tier 0 (Custom Traps):
        - 'default': Mengurutkan berdasarkan panjang ideal (4-7, 3, 8, >8) lalu urutan abjad kamus.
        - 'tag_order': Mengurutkan berdasarkan urutan daftar tag kustom (tag teratas lebih dulu).
        """
        if mode in ("default", "tag_order"):
            self.tier0_sort_mode = mode
            return True
        return False

    def count_words_by_suffix(self, suffix):
        """Menghitung berapa banyak kata di kamus aktif yang berakhiran suffix tertentu"""
        s = suffix.strip().lower()
        if not s:
            return 0
        return sum(1 for w in self.words if w.endswith(s) and w not in self.blacklisted_words)

    def cari_jawaban(self, awalan_prefix, limit=12, mode_santai=False, custom_endings=None, sort_mode=None):
        """
        Mencari kata yang DIAWALI oleh `awalan_prefix`:
        Contoh:
        - Jika prefix 'BUK' -> mencari kata berawalan 'buk' (buka, bukan, bukti, bukit, dll)
        - Jika prefix 'M'   -> mencari kata berawalan 'm'
        - Jika prefix 'EX'  -> mencari kata berawalan 'ex' (exit, extra, expert, dll)
        - Jika prefix 'IX'  -> mencari kata berawalan 'ix' (ixora, ixodes, dll)
        
        Prioritas Jawaban (Mode Normal):
        0. Kata berakhiran Kategori Custom / Custom Traps (🔥 Super Jebakan, misal NS, NGK)
        1. Kata berakhiran 'X' (💥 Jebakan Mematikan)
        2. Kata berakhiran huruf sulit 'Z', 'Q', 'V', 'J', 'W', 'F' (⚡ Jebakan Sulit)
        3. Kata normal/seadanya (🛡️ Bertahan)

        Prioritas Jawaban (Mode Santai - tanpa X, Q, F):
        0. Kata berakhiran Kategori Custom yang tidak mengandung X, Q, F
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

        # Mode sortir Tier 0 (default atau tag_order)
        effective_sort_mode = sort_mode if sort_mode is not None else getattr(self, "tier0_sort_mode", "default")

        # Aturan akhiran kustom yang aktif
        custom_rules = custom_endings if custom_endings is not None else self.custom_endings
        active_custom = []
        if custom_rules:
            for idx, c in enumerate(custom_rules):
                if isinstance(c, dict) and c.get("enabled", True):
                    r = dict(c)
                    r["tag_index"] = idx
                    r["suffix"] = r.get("suffix", "").lower()
                    if r["suffix"]:
                        # Di Mode Santai: Abaikan custom tag yang mengandung huruf X, Q, atau F
                        if mode_santai and any(ch in r["suffix"] for ch in ("x", "q", "f")):
                            continue
                        active_custom.append(r)
                elif isinstance(c, str) and c.strip():
                    s = c.strip().lower()
                    if mode_santai and any(ch in s for ch in ("x", "q", "f")):
                        continue
                    active_custom.append({
                        "suffix": s,
                        "name": f"Akhiran {s.upper()}",
                        "enabled": True,
                        "color": "#cba6f7",
                        "tag_index": idx
                    })

        # Urutan pencocokan aturan custom
        if effective_sort_mode == "default":
            # Pada mode default, utamakan suffix terpanjang (misal NGK sebelum GK)
            match_rules = sorted(active_custom, key=lambda c: len(c.get("suffix", "")), reverse=True)
        else:
            # Pada mode tag_order, utamakan tag dengan posisi teratas (tag_index lebih kecil)
            match_rules = sorted(active_custom, key=lambda c: (c.get("tag_index", 0), -len(c.get("suffix", ""))))

        vowels = set("aiueo")
        jebakan_custom = []
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
                
                # Cek akhiran custom
                matched_rule = None
                for rule in match_rules:
                    sfx = rule.get("suffix", "").lower()
                    if sfx and w.endswith(sfx):
                        matched_rule = rule
                        break

                if matched_rule:
                    jebakan_custom.append((w, matched_rule))
                elif w[-1] in ("z", "v", "j", "w"):
                    jebakan_sulit.append(w)
                else:
                    kata_biasa.append(w)
        else:
            # Mode Normal / Push Index / Brutal
            for w in candidates:
                # Saring kata singkatan aneh (harus memiliki setidaknya 1 huruf vokal jika > 3 huruf)
                if len(w) >= 4 and not any(v in w for v in vowels):
                    continue

                # Cek akhiran custom (Prioritas Super / Paling Atas)
                matched_rule = None
                for rule in match_rules:
                    sfx = rule.get("suffix", "").lower()
                    if sfx and w.endswith(sfx):
                        matched_rule = rule
                        break

                if matched_rule:
                    jebakan_custom.append((w, matched_rule))
                elif w[-1] == "x":
                    jebakan_x.append(w)
                elif w[-1] in HURUF_SULIT_AKHIRAN:
                    jebakan_sulit.append(w)
                else:
                    kata_biasa.append(w)

        # Urutkan kata per tier
        def sort_key(w):
            is_wl = 0 if w in self.whitelisted_words else 1
            l = len(w)
            if 4 <= l <= 7:
                prio = 0
            elif l == 3:
                prio = 1
            elif l == 8:
                prio = 2
            else:
                prio = 3
            return (is_wl, prio, l)

        if effective_sort_mode == "tag_order":
            def sort_key_custom(item):
                w, rule = item
                is_wl = 0 if w in self.whitelisted_words else 1
                tag_prio = rule.get("tag_index", 0)
                l = len(w)
                if 4 <= l <= 7:
                    prio = 0
                elif l == 3:
                    prio = 1
                elif l == 8:
                    prio = 2
                else:
                    prio = 3
                return (is_wl, tag_prio, prio, l)
            jebakan_custom.sort(key=sort_key_custom)
        else:
            # Mode Default: Urutkan berdasarkan Whitelist -> Panjang 4-7, 3, 8, >8 -> Urutan Abjad Kamus (Stable Sort)
            def sort_key_custom(item):
                w, rule = item
                is_wl = 0 if w in self.whitelisted_words else 1
                l = len(w)
                if 4 <= l <= 7:
                    prio = 0
                elif l == 3:
                    prio = 1
                elif l == 8:
                    prio = 2
                else:
                    prio = 3
                return (is_wl, prio, l)
            jebakan_custom.sort(key=sort_key_custom)
        jebakan_x.sort(key=sort_key)
        jebakan_sulit.sort(key=sort_key)
        kata_biasa.sort(key=sort_key)

        hasil = []
        # TIER 0: Custom Traps (Prioritas Super)
        for w, rule in jebakan_custom:
            sfx = rule["suffix"].upper()
            hasil.append({
                "kata": w,
                "tipe": "CUSTOM_TRAP",
                "suffix": sfx,
                "badge_name": rule.get("name") or f"AKHIRAN {sfx}",
                "color": rule.get("color", "#cba6f7"),
                "deskripsi": f"Akhiran {sfx} (Super Jebakan)",
                "is_whitelisted": (w in self.whitelisted_words)
            })

        # TIER 1: Jebakan X
        for w in jebakan_x:
            hasil.append({
                "kata": w,
                "tipe": "JEBAKAN_X",
                "deskripsi": "Akhiran X (Mematikan)",
                "is_whitelisted": (w in self.whitelisted_words)
            })

        # TIER 2: Jebakan Sulit
        for w in jebakan_sulit:
            hasil.append({
                "kata": w,
                "tipe": "JEBAKAN_SULIT",
                "deskripsi": f"Akhiran {w[-1].upper()}",
                "is_whitelisted": (w in self.whitelisted_words)
            })

        # TIER 3: Kata Biasa
        for w in kata_biasa:
            desc = "Kata Santai" if mode_santai else "Kata Normal"
            hasil.append({
                "kata": w,
                "tipe": "BIASA",
                "deskripsi": desc,
                "is_whitelisted": (w in self.whitelisted_words)
            })

        return hasil[:limit]


    def search_dictionary(
        self,
        query="",
        search_type="prefix",
        selected_tags=None,
        min_len=0,
        max_len=999,
        limit=2000
    ):
        """
        Mencari kata di seluruh kosakata aktif berdasarkan awalan/akhiran/mengandung
        dan opsi filter multi-tag (bisa memilih satu atau beberapa tag).
        Mengembalikan tuple: (results, total_count)
        di mana results adalah list dict dengan detail kata terstruktur.
        """
        q = (query or "").strip().lower()
        search_type = (search_type or "prefix").strip().lower()
        if search_type not in ("prefix", "suffix", "contains"):
            search_type = "prefix"

        tag_set = set(t.strip().upper() for t in (selected_tags or []) if t.strip())
        suffix_tags = [t.lower() for t in tag_set if t not in ("WHITELIST", "⭐ WHITELIST", "BLACKLIST", "🚫 BLOCKLIST", "BLOCKLIST")]

        check_whitelist = any("WHITELIST" in t for t in tag_set)
        check_blacklist = any("BLOCKLIST" in t or "BLACKLIST" in t for t in tag_set)

        # Optimasi pemilihan kandidat kata awal
        if q and search_type == "prefix" and q[0] in self.words_by_initial:
            cand = self.words_by_initial[q[0]]
        else:
            cand = self.words

        matches = []
        for w in cand:
            w_len = len(w)
            if w_len < min_len or w_len > max_len:
                continue

            if q:
                if search_type == "prefix" and not w.startswith(q):
                    continue
                elif search_type == "suffix" and not w.endswith(q):
                    continue
                elif search_type == "contains" and q not in w:
                    continue

            if tag_set:
                matched_tag = False
                if check_whitelist and w in self.whitelisted_words:
                    matched_tag = True
                elif check_blacklist and w in self.blacklisted_words:
                    matched_tag = True
                elif suffix_tags and any(w.endswith(st) for st in suffix_tags):
                    matched_tag = True
                if not matched_tag:
                    continue

            matches.append(w)

        total_count = len(matches)
        trimmed = matches[:limit]

        # Buat lookup custom endings
        custom_lookup = {}
        for c in self.custom_endings:
            if isinstance(c, dict):
                sfx = c.get("suffix", "").lower()
                if sfx:
                    custom_lookup[sfx] = c.get("name") or f"Akhiran {sfx.upper()}"
            elif isinstance(c, str) and c.strip():
                sfx = c.strip().lower()
                custom_lookup[sfx] = f"Akhiran {sfx.upper()}"

        results = []
        for w in trimmed:
            tag_label = ""
            matched_custom = None
            for sfx in custom_lookup:
                if w.endswith(sfx):
                    matched_custom = sfx.upper()
                    break

            if matched_custom:
                tag_label = f"[{matched_custom}]"
            elif w.endswith("x"):
                tag_label = "[💥 X]"
            elif any(w.endswith(ch) for ch in ("z", "q", "v", "j", "w", "f")):
                tag_label = f"[⚡ {w[-1].upper()}]"
            else:
                tag_label = "[🛡️ Normal]"

            is_wl = w in self.whitelisted_words
            is_bl = w in self.blacklisted_words

            if is_bl:
                status_src = "🚫 Blocklist"
            elif is_wl:
                status_src = "⭐ Whitelist"
            elif w in self.kbbi_set and w not in self.contek_set:
                status_src = "KBBI"
            elif w in self.contek_set and w not in self.kbbi_set:
                status_src = "Contek"
            elif w in self.kbbi_set and w in self.contek_set:
                status_src = "KBBI + Contek"
            else:
                status_src = "Kamus"

            results.append({
                "word": w.upper(),
                "length": len(w),
                "tag": tag_label,
                "status": status_src,
                "is_whitelisted": is_wl,
                "is_blacklisted": is_bl
            })

        return results, total_count
