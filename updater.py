"""
updater.py
Modul pengecekan pembaruan otomatis untuk SAKA Overlay (Git CLI + HTTPS Archive ZIP Fallback).
Mendukung multi-branch (main, dev, dll) dan 3 mode:
- 'prompt': Menampilkan dialog konfirmasi dan daftar commit baru sebelum memperbarui.
- 'auto': Memperbarui secara otomatis di latar belakang saat aplikasi dibuka.
- 'disabled': Menonaktifkan pengecekan pembaruan otomatis saat startup.
"""

from datetime import datetime, timezone
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import requests

DEFAULT_GITHUB_REPO = "anv-group/saka-overlay"
UPDATER_STATE_FILE = "updater_state.json"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

PROTECTED_PREFIXES = (
    ".git",
    ".venv",
    "venv",
    "env",
    "sample",
    "deteksi-gameplay",
    "__pycache__",
)
PROTECTED_EXACT_FILES = {
    "config.json",
    "config.local.json",
    "updater_state.json",
    "kamus_custom.csv",
    "db_cache.json",
}
PRESERVE_IF_EXISTS_FILES = {
    "whitelist.csv",
    "blacklist.csv",
}


def _github_headers():
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SAKA-Overlay-Updater",
    }


def _format_github_api_error(resp, fallback_msg):
    if resp is None:
        return fallback_msg
    if resp.status_code in (403, 429) and resp.headers.get("X-RateLimit-Remaining") == "0":
        return "Batas akses GitHub API tercapai (rate limit), silakan coba beberapa saat lagi."
    return f"{fallback_msg} (HTTP {resp.status_code})"


def _format_api_commit(item):
    sha = str((item or {}).get("sha") or "")
    commit_obj = (item or {}).get("commit") or {}
    author_obj = commit_obj.get("author") or {}
    raw_msg = str(commit_obj.get("message") or "")
    first_line = raw_msg.splitlines()[0].strip() if raw_msg else ""
    raw_date = str(author_obj.get("date") or "")
    return {
        "hash": sha[:7] if sha else "unknown",
        "full_hash": sha,
        "author": str(author_obj.get("name") or "-"),
        "date": raw_date[:10] if raw_date else "-",
        "message": first_line,
    }


def _run_git_cmd(args, cwd=None, timeout=15):
    """Menjalankan perintah git dengan timeout dan encoding utf-8."""
    try:
        res = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=cwd,
            timeout=timeout,
            creationflags=_CREATE_NO_WINDOW,
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Waktu koneksi ke GitHub habis (Timeout)."
    except Exception as e:
        return -1, "", str(e)


class GitUpdater:
    def __init__(self, repo_dir=None, github_repo=DEFAULT_GITHUB_REPO):
        if repo_dir is None:
            repo_dir = os.path.dirname(os.path.abspath(__file__))
        self.repo_dir = repo_dir
        self.github_repo = github_repo
        self.state_path = os.path.join(self.repo_dir, UPDATER_STATE_FILE)

    def has_git_cli(self):
        """Memeriksa apakah executable git tersedia di PATH sistem."""
        return shutil.which("git") is not None

    def is_git_repo(self):
        """Memeriksa apakah folder ini adalah repositori Git yang valid."""
        git_dir = os.path.join(self.repo_dir, ".git")
        if not os.path.exists(git_dir) or not self.has_git_cli():
            return False
        code, out, _ = _run_git_cmd(["rev-parse", "--is-inside-work-tree"], cwd=self.repo_dir)
        return code == 0 and out == "true"

    def get_updater_mode(self):
        """Mengembalikan 'git' bila git CLI + .git tersedia, selain itu 'https'."""
        return "git" if (self.has_git_cli() and self.is_git_repo()) else "https"

    def _resolve_github_repo(self):
        """Membaca owner/repo dari .git/config bila tersedia, fallback ke DEFAULT_GITHUB_REPO."""
        git_cfg = os.path.join(self.repo_dir, ".git", "config")
        if os.path.isfile(git_cfg):
            try:
                with open(git_cfg, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                m = re.search(r"github\.com[:/]([^/\s]+/[^/\s.]+?)(?:\.git)?\s*$", content, re.M)
                if m:
                    return m.group(1)
            except OSError:
                pass
        return self.github_repo

    def _load_state(self):
        if not os.path.isfile(self.state_path):
            return {}
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_state(self, state):
        fd, tmp_path = tempfile.mkstemp(prefix=".upd_", suffix=".tmp", dir=self.repo_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=4)
            os.replace(tmp_path, self.state_path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def get_current_branch(self):
        """Mendapatkan nama branch lokal saat ini (misal: dev atau main)."""
        if self.get_updater_mode() == "git":
            code, out, _ = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_dir)
            return out if code == 0 and out else "main"

        state = self._load_state()
        if state.get("branch"):
            return str(state["branch"])
        cfg_path = os.path.join(self.repo_dir, "config.json")
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if isinstance(cfg, dict) and cfg.get("updater_branch"):
                    return str(cfg["updater_branch"])
            except Exception:
                pass
        return "main"

    @staticmethod
    def _sort_branches(branches):
        ordered = []
        if "main" in branches:
            ordered.append("main")
        if "dev" in branches:
            ordered.append("dev")
        for b in sorted(branches):
            if b not in ordered:
                ordered.append(b)
        return ordered

    def get_available_branches(self):
        """Mendapatkan daftar semua branch yang ada di remote origin."""
        branches = {"main", "dev"}
        if self.get_updater_mode() == "git":
            code, out, _ = _run_git_cmd(["ls-remote", "--heads", "origin"], cwd=self.repo_dir, timeout=8)
            if code == 0 and out:
                for line in out.splitlines():
                    if "refs/heads/" in line:
                        parts = line.split("refs/heads/")
                        if len(parts) > 1 and parts[1].strip():
                            branches.add(parts[1].strip())
            else:
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
            return self._sort_branches(branches)

        repo = self._resolve_github_repo()
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}/branches",
                params={"per_page": 100},
                headers=_github_headers(),
                timeout=8,
            )
            if resp.status_code == 200:
                payload = resp.json()
                if isinstance(payload, list):
                    for item in payload:
                        name = str((item or {}).get("name") or "").strip()
                        if name:
                            branches.add(name)
        except Exception:
            pass
        return self._sort_branches(branches)

    def get_current_commit(self):
        """Mendapatkan informasi commit lokal saat ini."""
        if self.get_updater_mode() == "git":
            code, out, _ = _run_git_cmd(
                ["log", "-1", "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"],
                cwd=self.repo_dir,
            )
            if code == 0 and out:
                parts = out.split("\t")
                if len(parts) >= 4:
                    return {
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                    }
                return {"hash": parts[0], "message": out, "author": "-", "date": "-"}
            return {"hash": "unknown", "message": "Tidak diketahui", "author": "-", "date": "-"}

        state = self._load_state()
        if state.get("hash"):
            return {
                "hash": str(state["hash"])[:7],
                "full_hash": str(state.get("full_hash") or state["hash"]),
                "author": str(state.get("author") or "-"),
                "date": str(state.get("date") or "-"),
                "message": str(state.get("message") or ""),
                "is_non_git": True,
            }
        return {
            "hash": "unknown",
            "message": "Versi ZIP belum terlacak (Mode Non-Git)",
            "author": "-",
            "date": "-",
            "is_non_git": True,
        }

    def check_for_updates(self, target_branch=None, timeout=12, is_auto_check=False):
        """
        Memeriksa pembaruan terhadap target_branch (Git CLI atau HTTPS GitHub API).
        """
        if self.get_updater_mode() != "git":
            return self._check_for_updates_https(
                target_branch=target_branch,
                timeout=timeout,
                is_auto_check=is_auto_check,
            )

        current_branch = self.get_current_branch()
        branch = target_branch if target_branch else current_branch
        current_commit = self.get_current_commit()

        # 1. Fetch dari remote origin untuk branch target
        code, _, err = _run_git_cmd(["fetch", "origin", branch], cwd=self.repo_dir, timeout=timeout)
        if code != 0:
            return {
                "success": False,
                "error": f"Gagal menghubungi GitHub untuk branch '{branch}': {err or 'Tidak ada koneksi internet'}",
                "has_update": False,
                "current_commit": current_commit,
                "branch": branch,
                "current_branch": current_branch,
                "commits": [],
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
            cwd=self.repo_dir,
        )
        behind_count = int(count_str) if (code_cnt == 0 and count_str.isdigit()) else 0

        if is_same_commit and not is_branch_switch:
            return {
                "success": True,
                "has_update": False,
                "behind_count": 0,
                "current_commit": current_commit,
                "branch": branch,
                "current_branch": current_branch,
                "is_branch_switch": False,
                "commits": [],
            }

        # 4. Ambil log commit
        commits = []
        if behind_count > 0:
            code_log, log_out, _ = _run_git_cmd(
                ["log", f"HEAD..{remote_ref}", "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"],
                cwd=self.repo_dir,
            )
        else:
            code_log, log_out, _ = _run_git_cmd(
                ["log", "-n", "5", remote_ref, "--pretty=format:%h%x09%an%x09%ad%x09%s", "--date=short"],
                cwd=self.repo_dir,
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
                        "message": parts[3],
                    })
                elif len(parts) >= 1:
                    commits.append({
                        "hash": parts[0],
                        "author": "-",
                        "date": "-",
                        "message": parts[-1],
                    })

        # 5. Periksa apakah requirements.txt berubah
        code_diff, diff_out, _ = _run_git_cmd(
            ["diff", "--name-only", f"HEAD..{remote_ref}"],
            cwd=self.repo_dir,
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
            "remote_hash": hash_rem[:7] if code_rev_rem == 0 and hash_rem else "",
            "current_commit": current_commit,
            "commits": commits,
            "changed_files": changed_files,
            "needs_pip": needs_pip,
        }

    def _fetch_latest_commits_https(self, repo, branch, per_page=5, timeout=12):
        resp = requests.get(
            f"https://api.github.com/repos/{repo}/commits",
            params={"sha": branch, "per_page": per_page},
            headers=_github_headers(),
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None, _format_github_api_error(resp, f"Gagal menghubungi GitHub untuk branch '{branch}'")
        payload = resp.json()
        if not isinstance(payload, list):
            return [], None
        return [_format_api_commit(c) for c in payload], None

    def _check_for_updates_https(self, target_branch=None, timeout=12, is_auto_check=False):
        repo = self._resolve_github_repo()
        state = self._load_state()
        local_hash = str(state.get("full_hash") or state.get("hash") or "").strip()
        current_branch = self.get_current_branch()
        branch = target_branch if target_branch else current_branch
        current_commit = self.get_current_commit()
        is_branch_switch = (current_branch != branch)

        # Fresh Download ZIP (hash lokal belum terlacak): jangan ganggu startup auto-check
        if not local_hash and is_auto_check:
            return {
                "success": True,
                "has_update": False,
                "behind_count": 0,
                "branch": branch,
                "current_branch": current_branch,
                "is_branch_switch": is_branch_switch,
                "current_commit": current_commit,
                "is_non_git": True,
                "is_version_untracked": True,
                "commits": [],
            }

        try:
            if not local_hash:
                commits, err_msg = self._fetch_latest_commits_https(repo, branch, per_page=5, timeout=timeout)
                if err_msg:
                    return {
                        "success": False,
                        "error": err_msg,
                        "has_update": False,
                        "current_commit": current_commit,
                        "branch": branch,
                        "current_branch": current_branch,
                        "is_non_git": True,
                        "commits": [],
                    }
                remote_hash = commits[0]["hash"] if commits else ""
                return {
                    "success": True,
                    "has_update": True,
                    "behind_count": len(commits),
                    "branch": branch,
                    "current_branch": current_branch,
                    "is_branch_switch": is_branch_switch,
                    "is_same_commit": False,
                    "remote_hash": remote_hash,
                    "current_commit": current_commit,
                    "is_non_git": True,
                    "is_version_untracked": True,
                    "commits": commits,
                    "changed_files": [],
                    "needs_pip": False,
                }

            resp = requests.get(
                f"https://api.github.com/repos/{repo}/compare/{local_hash}...{branch}",
                headers=_github_headers(),
                timeout=timeout,
            )
            if resp.status_code == 200:
                data = resp.json() if isinstance(resp.json(), dict) else {}
                ahead_by = int(data.get("ahead_by") or 0)
                raw_commits = list(reversed(data.get("commits") or []))
                commits = [_format_api_commit(c) for c in raw_commits]
                changed_files = [
                    str((f or {}).get("filename") or "")
                    for f in (data.get("files") or [])
                    if isinstance(f, dict)
                ]
                needs_pip = any("requirements.txt" in f for f in changed_files)
                remote_hash = commits[0]["hash"] if commits else local_hash[:7]
                is_same_commit = (ahead_by == 0 and data.get("status") == "identical")
                has_update = (ahead_by > 0 or is_branch_switch)
                return {
                    "success": True,
                    "has_update": has_update,
                    "behind_count": ahead_by,
                    "branch": branch,
                    "current_branch": current_branch,
                    "is_branch_switch": is_branch_switch,
                    "is_same_commit": is_same_commit,
                    "remote_hash": remote_hash,
                    "current_commit": current_commit,
                    "is_non_git": True,
                    "commits": commits,
                    "changed_files": changed_files,
                    "needs_pip": needs_pip,
                }

            if resp.status_code == 404:
                commits, err_msg = self._fetch_latest_commits_https(repo, branch, per_page=5, timeout=timeout)
                if err_msg:
                    return {
                        "success": False,
                        "error": err_msg,
                        "has_update": False,
                        "current_commit": current_commit,
                        "branch": branch,
                        "current_branch": current_branch,
                        "is_non_git": True,
                        "commits": [],
                    }
                remote_full = commits[0]["full_hash"] if commits else ""
                is_same = bool(
                    remote_full
                    and (remote_full.startswith(local_hash) or local_hash.startswith(remote_full))
                )
                has_update = (not is_same) or is_branch_switch
                return {
                    "success": True,
                    "has_update": has_update,
                    "behind_count": len(commits) if not is_same else 0,
                    "branch": branch,
                    "current_branch": current_branch,
                    "is_branch_switch": is_branch_switch,
                    "is_same_commit": is_same,
                    "remote_hash": commits[0]["hash"] if commits else "",
                    "current_commit": current_commit,
                    "is_non_git": True,
                    "commits": commits if has_update else [],
                    "changed_files": [],
                    "needs_pip": False,
                }

            return {
                "success": False,
                "error": _format_github_api_error(resp, f"Gagal memeriksa update di branch '{branch}'"),
                "has_update": False,
                "current_commit": current_commit,
                "branch": branch,
                "current_branch": current_branch,
                "is_non_git": True,
                "commits": [],
            }
        except requests.Timeout:
            return {
                "success": False,
                "error": "Waktu koneksi ke GitHub habis (Timeout).",
                "has_update": False,
                "current_commit": current_commit,
                "branch": branch,
                "current_branch": current_branch,
                "is_non_git": True,
                "commits": [],
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Gagal menghubungi GitHub untuk branch '{branch}': {e}",
                "has_update": False,
                "current_commit": current_commit,
                "branch": branch,
                "current_branch": current_branch,
                "is_non_git": True,
                "commits": [],
            }

    @staticmethod
    def _is_protected_rel_path(rel_posix, dst_path):
        parts = [p for p in rel_posix.split("/") if p]
        if not parts:
            return True
        if parts[0] in PROTECTED_PREFIXES:
            return True
        if rel_posix in PROTECTED_EXACT_FILES:
            return True
        if rel_posix in PRESERVE_IF_EXISTS_FILES and os.path.exists(dst_path):
            return True
        return False

    def _run_pip_install(self):
        req_path = os.path.join(self.repo_dir, "requirements.txt")
        if os.path.exists(req_path):
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
                    cwd=self.repo_dir,
                    timeout=60,
                    creationflags=_CREATE_NO_WINDOW,
                )
            except Exception:
                pass

    def _apply_update_https(self, target_branch=None):
        repo = self._resolve_github_repo()
        current_branch = self.get_current_branch()
        branch = target_branch if target_branch else current_branch
        zip_url = f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"

        staging_dir = tempfile.mkdtemp(prefix="saka_upd_")
        zip_path = os.path.join(staging_dir, "update.zip")
        extract_dir = os.path.join(staging_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)

        try:
            resp = requests.get(zip_url, headers={"User-Agent": "SAKA-Overlay-Updater"}, stream=True, timeout=60)
            if resp.status_code != 200:
                return False, f"Gagal mengunduh archive branch '{branch}' (HTTP {resp.status_code})."

            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)

            extract_root_real = os.path.realpath(extract_dir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zip_comment_sha = (zf.comment or b"").decode("utf-8", errors="ignore").strip()
                members = zf.infolist()
                for info in members:
                    norm_name = info.filename.replace("\\", "/")
                    if not norm_name or norm_name.startswith("/") or ".." in norm_name.split("/"):
                        return False, f"Archive berisi path tidak aman: {info.filename}"
                    dest_stage = os.path.realpath(os.path.join(extract_dir, norm_name))
                    if dest_stage != extract_root_real and not dest_stage.startswith(extract_root_real + os.sep):
                        return False, f"Archive berisi path traversal: {info.filename}"
                zf.extractall(extract_dir)

            top_entries = [os.path.join(extract_dir, name) for name in os.listdir(extract_dir)]
            if len(top_entries) == 1 and os.path.isdir(top_entries[0]):
                source_root = top_entries[0]
            else:
                source_root = extract_dir

            req_updated = False
            for root, dirs, files in os.walk(source_root):
                rel_dir = os.path.relpath(root, source_root)
                rel_dir_posix = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
                dirs[:] = [
                    d for d in dirs
                    if d not in PROTECTED_PREFIXES
                    and (f"{rel_dir_posix}/{d}" if rel_dir_posix else d).split("/")[0] not in PROTECTED_PREFIXES
                ]
                for fname in files:
                    rel_posix = f"{rel_dir_posix}/{fname}" if rel_dir_posix else fname
                    src_file = os.path.join(root, fname)
                    dst_file = os.path.join(self.repo_dir, *rel_posix.split("/"))
                    if self._is_protected_rel_path(rel_posix, dst_file):
                        continue
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                    if rel_posix == "requirements.txt":
                        req_updated = True

            commit_info = None
            try:
                commits, _ = self._fetch_latest_commits_https(repo, branch, per_page=1, timeout=8)
                if commits:
                    commit_info = commits[0]
            except Exception:
                commit_info = None

            full_sha = (commit_info or {}).get("full_hash") or zip_comment_sha
            state_payload = {
                "branch": branch,
                "hash": full_sha[:7] if full_sha else "unknown",
                "full_hash": full_sha,
                "author": (commit_info or {}).get("author", "-"),
                "date": (commit_info or {}).get("date", "-"),
                "message": (commit_info or {}).get("message", f"Diperbarui via Archive ZIP ({branch})"),
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
            self._save_state(state_payload)

            if req_updated:
                self._run_pip_install()

            action_msg = (
                f"Berhasil beralih ke branch '{branch}' dan diperbarui (Mode Non-Git)."
                if branch != current_branch
                else "Pembaruan berhasil diterapkan (Mode Non-Git)."
            )
            return True, action_msg
        except requests.Timeout:
            return False, f"Waktu unduh pembaruan untuk branch '{branch}' habis (Timeout)."
        except zipfile.BadZipFile:
            return False, "File pembaruan dari GitHub rusak atau tidak valid (BadZipFile)."
        except Exception as e:
            return False, f"Gagal menerapkan pembaruan Non-Git di branch '{branch}': {e}"
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    def apply_update(self, target_branch=None):
        """
        Memperbarui aplikasi (via git checkout + git pull, atau unduh Archive ZIP bila tanpa Git).
        """
        if self.get_updater_mode() != "git":
            return self._apply_update_https(target_branch=target_branch)

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
        self._run_pip_install()

        action_msg = (
            f"Berhasil beralih ke branch '{branch}' dan diperbarui."
            if branch != current_branch
            else "Pembaruan berhasil diterapkan."
        )
        return True, action_msg

    def restart_app(self):
        """Me-restart aplikasi saat ini."""
        try:
            subprocess.Popen([sys.executable] + sys.argv, cwd=self.repo_dir)
            os._exit(0)
        except Exception as e:
            print(f"[!] Gagal me-restart aplikasi: {e}")
