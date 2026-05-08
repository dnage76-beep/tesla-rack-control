"""
Tesla Rack Control launcher.

Double-click entry point. On startup:

1. Quietly checks GitHub's REST API for the latest commit on `main`.
2. Compares to the SHA stored in `.version` next to this file.
3. If they differ, asks the user whether to update.
4. On accept: downloads the main-branch zip from codeload.github.com,
   extracts, copies the new files over the install folder (preserving
   logs/, field_testing/sessions/, field_testing/captures/), updates
   `.version`, and re-runs `pip install -r requirements.txt` in case
   dependencies changed.
5. Hands off to app.py (the Tesla Rack Control Suite shell, which
   in turn launches tesla_control.py from its Run Test screen).

Designed for the one-click install flow where Jordan's machine does
NOT have git. The HTTP/zip approach avoids any git dependency.

A developer checkout that has a `.git/` folder is detected and the
update prompt is skipped (the dev manages versions with git directly).

Failures (offline, GitHub down, pip failed) are non-fatal: the launcher
shows the error and offers to start the program anyway.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
import urllib.error
import urllib.request
import zipfile
from tkinter import messagebox, scrolledtext

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = "app.py"  # the desktop suite -- it spawns tesla_control.py from a button
VERSION_FILE = ".version"

OWNER = "dnage76-beep"
REPO = "tesla-rack-control"
BRANCH = "main"
USER_AGENT = "tesla-rack-control-launcher"

API_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 120

# Files/dirs that hold the user's local data and must NOT be
# overwritten by an update. Paths are relative to REPO_DIR.
PRESERVE_DIRS = {
    "logs",
    "field_testing/sessions",
    "field_testing/captures",
}


# ----------------------------------------------------------------------
# environment detection
# ----------------------------------------------------------------------

def _is_git_checkout():
    return os.path.isdir(os.path.join(REPO_DIR, ".git"))


def _local_sha():
    p = os.path.join(REPO_DIR, VERSION_FILE)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return f.read().strip() or None


def _write_local_sha(sha):
    with open(os.path.join(REPO_DIR, VERSION_FILE), "w") as f:
        f.write(sha)


# ----------------------------------------------------------------------
# GitHub API
# ----------------------------------------------------------------------

def _api_request(url, timeout=API_TIMEOUT):
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _latest_remote_sha():
    """Return (sha, error_or_none)."""
    try:
        data = _api_request(
            f"https://api.github.com/repos/{OWNER}/{REPO}/commits/{BRANCH}"
        )
        return data["sha"], None
    except urllib.error.URLError as e:
        return None, f"GitHub unreachable: {e.reason}"
    except (KeyError, json.JSONDecodeError) as e:
        return None, f"unexpected GitHub response: {e}"
    except Exception as e:
        return None, str(e)


def _commits_between(local_sha, remote_sha):
    """Best-effort list of commit messages between local and remote.
    Returns a string for display, or '' if the request fails."""
    if not local_sha:
        return ""
    try:
        data = _api_request(
            f"https://api.github.com/repos/{OWNER}/{REPO}/compare/"
            f"{local_sha}...{remote_sha}"
        )
        commits = data.get("commits", []) or []
        lines = []
        for c in commits[-10:]:
            sha7 = c.get("sha", "")[:7]
            msg = (c.get("commit", {}).get("message", "")
                   .splitlines()[0])
            lines.append(f"  {sha7}  {msg}")
        return "\n".join(lines)
    except Exception:
        return ""


# ----------------------------------------------------------------------
# zip-based update
# ----------------------------------------------------------------------

def _download_zip():
    """Download the branch zip and return its bytes."""
    url = (
        f"https://codeload.github.com/{OWNER}/{REPO}/zip/refs/heads/{BRANCH}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as r:
        return r.read()


def _is_preserved(rel_path):
    rp = rel_path.replace("\\", "/")
    for p in PRESERVE_DIRS:
        if rp == p or rp.startswith(p + "/"):
            return True
    return False


def _apply_zip(zip_bytes):
    """Extract zip to a temp dir and copy files over REPO_DIR."""
    tmp = tempfile.mkdtemp(prefix="trc_update_")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(tmp)
        # GitHub zips wrap everything in <repo>-<branch>/.
        roots = [
            n for n in os.listdir(tmp)
            if os.path.isdir(os.path.join(tmp, n)) and n != "__MACOSX"
        ]
        if not roots:
            raise RuntimeError("zip archive had no top-level directory")
        src = os.path.join(tmp, roots[0])

        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            if rel != "." and _is_preserved(rel):
                dirs[:] = []
                continue
            target_root = REPO_DIR if rel == "." else os.path.join(REPO_DIR, rel)
            os.makedirs(target_root, exist_ok=True)
            for f in files:
                rel_file = f if rel == "." else os.path.join(rel, f)
                if _is_preserved(rel_file):
                    continue
                shutil.copy2(
                    os.path.join(root, f), os.path.join(target_root, f)
                )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _pip_install():
    req = os.path.join(REPO_DIR, "requirements.txt")
    if not os.path.exists(req):
        return True, ""
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", req],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return r.returncode == 0, (r.stdout + r.stderr).strip()


# ----------------------------------------------------------------------
# UI helpers
# ----------------------------------------------------------------------

def _show_log(title, text):
    win = tk.Toplevel()
    win.title(title)
    win.geometry("700x300")
    box = scrolledtext.ScrolledText(win, wrap=tk.WORD)
    box.insert("1.0", text or "(no output)")
    box.configure(state="disabled")
    box.pack(fill="both", expand=True, padx=8, pady=8)
    tk.Button(win, text="Close", command=win.destroy).pack(pady=4)
    win.transient()
    win.grab_set()
    win.wait_window()


def _launch_target():
    target = os.path.join(REPO_DIR, TARGET)
    if not os.path.exists(target):
        messagebox.showerror(
            "Tesla Rack Control",
            f"Cannot find {TARGET} in {REPO_DIR}.",
        )
        sys.exit(1)
    os.chdir(REPO_DIR)
    os.execv(sys.executable, [sys.executable, target])


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    root = tk.Tk()
    root.withdraw()

    # Dev checkout: skip auto-update entirely.
    if _is_git_checkout():
        _launch_target()
        return

    local = _local_sha()
    remote, err = _latest_remote_sha()

    if err:
        if not messagebox.askyesno(
            "Tesla Rack Control",
            f"Could not check GitHub for updates "
            f"(running {(local or '?')[:7]}).\n\n{err}\n\n"
            "Launch anyway?",
        ):
            sys.exit(0)
        _launch_target()
        return

    # First run after install: write .version and proceed.
    if local is None:
        _write_local_sha(remote)
        _launch_target()
        return

    if local == remote:
        _launch_target()
        return

    notes = _commits_between(local, remote)
    msg = (
        f"A new version is available.\n\n"
        f"Current: {local[:7]}\nLatest:  {remote[:7]}\n"
    )
    if notes:
        msg += f"\nRecent changes:\n{notes}\n"
    msg += "\nUpdate now?"

    if not messagebox.askyesno("Update available", msg):
        _launch_target()
        return

    try:
        zip_bytes = _download_zip()
        _apply_zip(zip_bytes)
        _write_local_sha(remote)
    except Exception as e:
        _show_log("Update failed", str(e))
        if not messagebox.askyesno(
            "Update failed",
            "Update failed (see log). Launch the previous version?",
        ):
            sys.exit(1)
        _launch_target()
        return

    pip_ok, pip_log = _pip_install()
    if not pip_ok:
        _show_log("pip install failed", pip_log)
        if not messagebox.askyesno(
            "Dependency install failed",
            "Update applied but pip install failed.\n\nLaunch anyway?",
        ):
            sys.exit(1)

    messagebox.showinfo(
        "Updated",
        f"Updated to {remote[:7]}. Launching Tesla Rack Control.",
    )
    _launch_target()


if __name__ == "__main__":
    main()
