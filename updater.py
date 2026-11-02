"""
updater.py
Modul pengecekan pembaruan otomatis (Git Updater) untuk Roblox Sambung Kata Assistant.
Mendukung 3 mode:
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
        """Mendapatkan nama branch saat ini (misal: main)"""
        code, out, _ = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_dir)
        return out if code == 0 and out else "main"

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

    def check_for_updates(self, timeout=12):
        """
        Melakukan git fetch dan membandingkan commit lokal vs remote.
        Mengembalikan dict hasil pemeriksaan.
        """
        if not self.is_git_repo():
            return {
                "success": False,
                "error": "Bukan repositori Git yang terhubung.",
                "has_update": False,
                "commits": []
            }

        branch = self.get_current_branch()
        current_commit = self.get_current_commit()

        # 1. Fetch dari remote origin
        code, out, err = _run_git_cmd(["fetch", "origin", branch], cwd=self.repo_dir, timeout=timeout)
        if code != 0:
            return {
                "success": False,
                "error": f"Gagal menghubungi GitHub: {err or 'Tidak ada koneksi internet'}",
                "has_update": False,
                "current_commit": current_commit,
                "commits": []
            }

        # 2. Hitung jumlah commit tertinggal (behind)
        remote_ref = f"origin/{branch}"
        code_cnt, count_str, _ = _run_git_cmd(
            ["rev-list", "--count", f"HEAD..{remote_ref}"],
            cwd=self.repo_dir
        )
        behind_count = int(count_str) if (code_cnt == 0 and count_str.isdigit()) else 0

        if behind_count == 0:
            return {
                "success": True,
                "has_update": False,
                "behind_count": 0,
                "current_commit": current_commit,
                "branch": branch,
                "commits": []
            }

        # 3. Dapatkan daftar commit baru
        code_log, log_out, _ = _run_git_cmd(
            ["log", f"HEAD..{remote_ref}", "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"],
            cwd=self.repo_dir
        )
        commits = []
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

        # 4. Periksa apakah requirements.txt berubah
        code_diff, diff_out, _ = _run_git_cmd(
            ["diff", "--name-only", f"HEAD..{remote_ref}"],
            cwd=self.repo_dir
        )
        changed_files = diff_out.splitlines() if code_diff == 0 else []
        needs_pip = any("requirements.txt" in f for f in changed_files)

        return {
            "success": True,
            "has_update": True,
            "behind_count": behind_count,
            "branch": branch,
            "current_commit": current_commit,
            "commits": commits,
            "changed_files": changed_files,
            "needs_pip": needs_pip
        }

    def apply_update(self):
        """
        Menjalankan git pull untuk memperbarui repositori lokal.
        """
        if not self.is_git_repo():
            return False, "Bukan repositori Git yang terhubung."

        branch = self.get_current_branch()
        code, out, err = _run_git_cmd(["pull", "--autostash", "origin", branch], cwd=self.repo_dir, timeout=30)
        if code != 0:
            return False, f"Gagal melakukan git pull: {err or out}"

        # Jalankan pip install jika requirements berubah
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

        return True, "Pembaruan berhasil diterapkan."

    def restart_app(self):
        """Me-restart aplikasi saat ini"""
        try:
            subprocess.Popen([sys.executable] + sys.argv, cwd=self.repo_dir)
            os._exit(0)
        except Exception as e:
            print(f"[!] Gagal me-restart aplikasi: {e}")
