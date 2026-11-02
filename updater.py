"""
updater.py
Modul pengecekan pembaruan otomatis (Git Updater) untuk Roblox Sambung Kata Assistant.
Mendukung multi-branch (main, dev, dll) dan 3 mode:
- 'prompt': Menampilkan dialog konfirmasi dan daftar commit baru sebelum memperbarui.
- 'auto': Memperbarui secara otomatis di latar belakang saat aplikasi dibuka.
- 'disabled': Menonaktifkan pengecekan pembaruan otomatis saat startup.
"""

import subprocess
import os
import sys
import threading

def _run_git_cmd(args, cwd=None, timeout=15):
    """Menjalankan perintah git dengan timeout dan encoding utf-8"""
    try:
        res = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            timeout=timeout
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Waktu koneksi ke GitHub habis (Timeout)."
    except Exception as e:
        return -1, "", str(e)

class GitUpdater:
    def __init__(self, repo_dir=None):
        if repo_dir is None:
            repo_dir = os.path.dirname(os.path.abspath(__file__))
        self.repo_dir = repo_dir

    def is_git_repo(self):
        """Memeriksa apakah folder ini adalah repositori Git yang valid"""
        git_dir = os.path.join(self.repo_dir, ".git")
        if not os.path.exists(git_dir):
            return False
        code, out, _ = _run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=self.repo_dir)
        return code == 0 and out == "true"

    def get_current_branch(self):
        """Mendapatkan nama branch lokal saat ini (misal: dev atau main)"""
        code, out, _ = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_dir)
        return out if code == 0 and out else "main"

    def get_available_branches(self):
        """Mendapatkan daftar semua branch yang ada di remote origin"""
        branches = set(["main", "dev"])
        # Coba ambil remote branch via ls-remote
        code, out, _ = _run_git_cmd(["ls-remote", "--heads", "origin"], cwd=self.repo_dir, timeout=8)
        if code == 0 and out:
            for line in out.splitlines():
                if "refs/heads/" in line:
                    parts = line.split("refs/heads/")
                    if len(parts) > 1:
                        b = parts[1].strip()
                        if b:
                            branches.add(b)
        else:
            # Fallback ke git branch -a
            code_loc, out_loc, _ = _run_git_cmd(["branch", "-a"], cwd=self.repo_dir)
            if code_loc == 0 and out_loc:
                for line in out_loc.splitlines():
                    line = line.replace("*", "").strip()
                    if "remotes/origin/" in line:
                        b = line.split("remotes/origin/")[1].strip()
                        if b and "HEAD" not in b:
                            branches.add(b)
                    elif line and not line.startswith("("):
                        branches.add(line)

        # Urutkan: main, dev, lalu sisanya alfabetis
        ordered = []
        if "main" in branches:
            ordered.append("main")
        if "dev" in branches:
            ordered.append("dev")
        for b in sorted(branches):
            if b not in ordered:
                ordered.append(b)
        return ordered

    def get_current_commit(self):
        """Mendapatkan informasi commit lokal saat ini"""
        code, out, _ = _run_git_cmd(
            ["log", "-1", "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"],
            cwd=self.repo_dir
        )
        if code == 0 and out:
            parts = out.split("\t")
            if len(parts) >= 4:
                return {
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3]
                }
            return {"hash": parts[0], "message": out, "author": "-", "date": "-"}
        return {"hash": "unknown", "message": "Tidak diketahui", "author": "-", "date": "-"}

    def check_for_updates(self, target_branch=None, timeout=12):
        """
        Melakukan git fetch terhadap target_branch dan membandingkan commit lokal vs remote.
        Mengembalikan dict hasil pemeriksaan.
        """
        if not self.is_git_repo():
            return {
                "success": False,
                "error": "Bukan repositori Git yang terhubung.",
                "has_update": False,
                "commits": []
            }

        current_branch = self.get_current_branch()
        branch = target_branch if target_branch else current_branch
        current_commit = self.get_current_commit()

        # 1. Fetch dari remote origin untuk branch target
        code, out, err = _run_git_cmd(["fetch", "origin", branch], cwd=self.repo_dir, timeout=timeout)
        if code != 0:
            return {
                "success": False,
                "error": f"Gagal menghubungi GitHub untuk branch '{branch}': {err or 'Tidak ada koneksi internet'}",
                "has_update": False,
                "current_commit": current_commit,
                "branch": branch,
                "current_branch": current_branch,
                "commits": []
            }

        remote_ref = f"origin/{branch}"

        # 2. Cek apakah local HEAD sama persis dengan remote_ref
        code_rev_head, hash_head, _ = _run_git_cmd(["rev-parse", "HEAD"], cwd=self.repo_dir)
        code_rev_rem, hash_rem, _ = _run_git_cmd(["rev-parse", remote_ref], cwd=self.repo_dir)

        is_same_commit = (code_rev_head == 0 and code_rev_rem == 0 and hash_head == hash_rem)
        is_branch_switch = (current_branch != branch)

        # 3. Hitung jumlah commit tertinggal (behind)
        code_cnt, count_str, _ = _run_git_cmd(
            ["rev-list", "--count", f"HEAD..{remote_ref}"],
            cwd=self.repo_dir
        )
        behind_count = int(count_str) if (code_cnt == 0 and count_str.isdigit()) else 0

        # Jika sama persis commit-nya dan berada di branch yang sama
        if is_same_commit and not is_branch_switch:
            return {
                "success": True,
                "has_update": False,
                "behind_count": 0,
                "current_commit": current_commit,
                "branch": branch,
                "current_branch": current_branch,
                "is_branch_switch": False,
                "commits": []
            }

        # 4. Ambil log commit
        commits = []
        if behind_count > 0:
            code_log, log_out, _ = _run_git_cmd(
                ["log", f"HEAD..{remote_ref}", "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"],
                cwd=self.repo_dir
            )
        else:
            code_log, log_out, _ = _run_git_cmd(
                ["log", "-n", "5", remote_ref, "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"],
                cwd=self.repo_dir
            )

        if code_log == 0 and log_out:
            for line in log_out.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3]
                    })
                elif len(parts) >= 1:
                    commits.append({
                        "hash": parts[0],
                        "author": "-",
                        "date": "-",
                        "message": parts[-1]
                    })

        # 5. Periksa apakah requirements.txt berubah
        code_diff, diff_out, _ = _run_git_cmd(
            ["diff", "--name-only", f"HEAD..{remote_ref}"],
            cwd=self.repo_dir
        )
        changed_files = diff_out.splitlines() if code_diff == 0 else []
        needs_pip = any("requirements.txt" in f for f in changed_files)

        has_update = (behind_count > 0 or is_branch_switch)

        return {
            "success": True,
            "has_update": has_update,
            "behind_count": behind_count,
            "branch": branch,
            "current_branch": current_branch,
            "is_branch_switch": is_branch_switch,
            "is_same_commit": is_same_commit,
            "current_commit": current_commit,
            "commits": commits,
            "changed_files": changed_files,
            "needs_pip": needs_pip
        }

    def apply_update(self, target_branch=None):
        """
        Menjalankan checkout (jika beralih branch) dan git pull untuk memperbarui repositori lokal.
        """
        if not self.is_git_repo():
            return False, "Bukan repositori Git yang terhubung."

        current_branch = self.get_current_branch()
        branch = target_branch if target_branch else current_branch

        # 1. Jika berpindah branch
        if branch != current_branch:
            code_check, _, _ = _run_git_cmd(["show-ref", "--verify", f"refs/heads/{branch}"], cwd=self.repo_dir)
            if code_check == 0:
                code_co, out_co, err_co = _run_git_cmd(["checkout", branch], cwd=self.repo_dir)
            else:
                code_co, out_co, err_co = _run_git_cmd(["checkout", "-b", branch, f"origin/{branch}"], cwd=self.repo_dir)

            if code_co != 0:
                return False, f"Gagal beralih ke branch '{branch}': {err_co or out_co}"

        # 2. Pull branch terbaru
        code, out, err = _run_git_cmd(["pull", "--autostash", "origin", branch], cwd=self.repo_dir, timeout=30)
        if code != 0:
            return False, f"Gagal melakukan git pull di branch '{branch}': {err or out}"

        # 3. Jalankan pip install jika requirements berubah
        req_path = os.path.join(self.repo_dir, "requirements.txt")
        if os.path.exists(req_path):
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
                    cwd=self.repo_dir,
                    timeout=60
                )
            except Exception:
                pass

        action_msg = f"Berhasil beralih ke branch '{branch}' dan diperbarui." if branch != current_branch else "Pembaruan berhasil diterapkan."
        return True, action_msg

    def restart_app(self):
        """Me-restart aplikasi saat ini"""
        try:
            subprocess.Popen([sys.executable] + sys.argv, cwd=self.repo_dir)
            os._exit(0)
        except Exception as e:
            print(f"[!] Gagal me-restart aplikasi: {e}")
