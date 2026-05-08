"""
Tesla Rack Control launcher.

Double-click entry point. On startup:

1. Quietly checks GitHub for new commits on the tracked branch.
2. If updates exist, asks the user whether to pull.
3. If pulled, re-runs `pip install -r requirements.txt` (in case
   requirements changed).
4. Hands off to tesla_control.py.

Failures are non-fatal: if GitHub is unreachable the launcher offers
to start the program anyway. If git or pip fail it shows the error
and offers to launch the previous version.

Run with the same Python interpreter that has python-can installed
(typically a 32-bit Python because USBCAN32.dll is 32-bit).
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, scrolledtext

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = "tesla_control.py"
REMOTE = "origin"
BRANCH = "main"
TIMEOUT_S = 10


def _run(cmd, timeout=TIMEOUT_S):
    return subprocess.run(
        cmd,
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _is_git_repo():
    try:
        r = _run(["git", "rev-parse", "--is-inside-work-tree"])
        return r.returncode == 0 and r.stdout.strip() == "true"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _local_sha():
    r = _run(["git", "rev-parse", "--short", "HEAD"])
    return r.stdout.strip() if r.returncode == 0 else "?"


def _check_remote():
    """Return (commits_behind, error_or_none)."""
    fetch = _run(["git", "fetch", REMOTE, BRANCH], timeout=20)
    if fetch.returncode != 0:
        return None, fetch.stderr.strip() or "git fetch failed"
    behind = _run(["git", "rev-list", f"HEAD..{REMOTE}/{BRANCH}", "--count"])
    if behind.returncode != 0:
        return None, behind.stderr.strip() or "git rev-list failed"
    try:
        return int(behind.stdout.strip() or 0), None
    except ValueError:
        return None, "could not parse rev-list output"


def _pending_release_notes(n):
    r = _run(
        ["git", "log", f"HEAD..{REMOTE}/{BRANCH}", "--oneline", f"-{n}"]
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def _has_local_changes():
    r = _run(["git", "status", "--porcelain"])
    return bool(r.stdout.strip())


def _pull():
    r = _run(["git", "pull", "--ff-only", REMOTE, BRANCH], timeout=30)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def _pip_install():
    req = os.path.join(REPO_DIR, "requirements.txt")
    if not os.path.exists(req):
        return True, ""
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", req],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def _show_log_dialog(title, text):
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


def main():
    root = tk.Tk()
    root.withdraw()

    if not _is_git_repo():
        messagebox.showwarning(
            "Tesla Rack Control",
            "This folder is not a git checkout, so update checking "
            "is disabled. Launching the program anyway.",
        )
        _launch_target()
        return

    sha = _local_sha()
    behind, err = _check_remote()

    if err:
        if not messagebox.askyesno(
            "Tesla Rack Control",
            f"Could not check GitHub for updates "
            f"(running {sha}).\n\n{err}\n\nLaunch anyway?",
        ):
            sys.exit(0)
        _launch_target()
        return

    if behind == 0:
        _launch_target()
        return

    notes = _pending_release_notes(behind)
    msg = (
        f"{behind} new commit(s) available on GitHub "
        f"(currently running {sha}).\n\n"
        f"{notes}\n\nUpdate now?"
    )
    if not messagebox.askyesno("Update available", msg):
        _launch_target()
        return

    if _has_local_changes():
        messagebox.showerror(
            "Cannot update",
            "You have local uncommitted changes. Commit or stash "
            "them, or ask Derek/Charlie for help. Launching the "
            "current version.",
        )
        _launch_target()
        return

    ok, log = _pull()
    if not ok:
        _show_log_dialog("git pull failed", log)
        if not messagebox.askyesno(
            "Update failed",
            "Pull failed (see log). Launch the previous version?",
        ):
            sys.exit(1)
        _launch_target()
        return

    pip_ok, pip_log = _pip_install()
    if not pip_ok:
        _show_log_dialog("pip install failed", pip_log)
        if not messagebox.askyesno(
            "Dependency install failed",
            "pip install failed (see log). Launch anyway?",
        ):
            sys.exit(1)

    new_sha = _local_sha()
    messagebox.showinfo(
        "Updated",
        f"Updated to {new_sha}. Launching Tesla Rack Control.",
    )
    _launch_target()


if __name__ == "__main__":
    main()
