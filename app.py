"""
Tesla Rack Control Suite - desktop application.

A Tk-based shell that wraps the steering test program (tesla_control.py)
plus log browsing, capture browsing, update management, and reference
documentation. Designed so a non-developer can click around and
do the work without touching a terminal.

Architecture:
    +----------+----------------------------+
    | sidebar  |    content frame           |
    |   nav    |    (one of several views)  |
    |          |                            |
    +----------+----------------------------+
    |   status bar (version, github state)  |
    +---------------------------------------+

Each view is a `View` subclass that knows how to build itself and
how to refresh when navigated to. tesla_control.py is launched as a
subprocess so the app stays responsive and you can come back to look
at logs while the test runs.

This file does NOT do any CAN traffic itself - the steering test is
still owned entirely by tesla_control.py. Treat this app as a kiosk.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

# ----------------------------------------------------------------------
# paths and constants
# ----------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "logs"
SESSIONS_DIR = ROOT_DIR / "field_testing" / "sessions"
CAPTURES_DIR = ROOT_DIR / "field_testing" / "captures"
DOCS_DIR = ROOT_DIR / "docs"
VERSION_FILE = ROOT_DIR / ".version"
TARGET_SCRIPT = ROOT_DIR / "tesla_control.py"
SNIFFER_SCRIPT = ROOT_DIR / "can_sniffer.py"

OWNER = "dnage76-beep"
REPO = "tesla-rack-control"
BRANCH = "main"
GITHUB_URL = f"https://github.com/{OWNER}/{REPO}"
USER_AGENT = "tesla-rack-control-suite"

APP_TITLE = "Tesla Rack Control Suite"

# palette - dark, slightly tinted neutrals
BG = "#1b1d29"
PANEL_BG = "#252837"
SIDE_BG = "#13141d"
NAV_HOVER = "#272a3c"
NAV_ACTIVE = "#2f344e"
ACCENT = "#5b8def"
ACCENT_DIM = "#3c5fa3"
FG = "#e8eaf2"
FG_DIM = "#9ea1b3"
OK = "#4ec9b0"
WARN = "#e6a23c"
DANGER = "#f06b6b"

# read installed version & app version
def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""

def _installed_sha() -> str | None:
    return _read_text(VERSION_FILE) or None

def _read_app_version() -> str:
    """Pull the __version__ string out of tesla_control.py."""
    try:
        for line in TARGET_SCRIPT.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("__version__"):
                # __version__ = "4.2.1"
                _, _, val = line.partition("=")
                return val.strip().strip('"').strip("'")
    except OSError:
        pass
    return "?"


# ----------------------------------------------------------------------
# GitHub helpers
# ----------------------------------------------------------------------

def _gh_get_json(url: str, timeout: int = 12):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def gh_latest_sha() -> tuple[str | None, str]:
    try:
        data = _gh_get_json(
            f"https://api.github.com/repos/{OWNER}/{REPO}/commits/{BRANCH}"
        )
        return data["sha"], ""
    except urllib.error.URLError as e:
        return None, f"network: {e.reason}"
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def gh_compare(local_sha: str, remote_sha: str) -> list[dict]:
    if not local_sha or local_sha == remote_sha:
        return []
    try:
        data = _gh_get_json(
            f"https://api.github.com/repos/{OWNER}/{REPO}/compare/"
            f"{local_sha}...{remote_sha}"
        )
        return data.get("commits", []) or []
    except Exception:
        return []


# ----------------------------------------------------------------------
# styling helpers
# ----------------------------------------------------------------------

def configure_style(style: ttk.Style) -> None:
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=FG, fieldbackground=PANEL_BG,
                    bordercolor=PANEL_BG, lightcolor=PANEL_BG, darkcolor=PANEL_BG)
    style.configure("TFrame", background=BG)
    style.configure("Side.TFrame", background=SIDE_BG)
    style.configure("Panel.TFrame", background=PANEL_BG)

    style.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
    style.configure("Side.TLabel", background=SIDE_BG, foreground=FG)
    style.configure("Panel.TLabel", background=PANEL_BG, foreground=FG, font=("Segoe UI", 10))
    style.configure("PanelDim.TLabel", background=PANEL_BG, foreground=FG_DIM, font=("Segoe UI", 9))
    style.configure("Title.TLabel", background=BG, foreground=FG,
                    font=("Segoe UI Semibold", 18))
    style.configure("Subtitle.TLabel", background=BG, foreground=FG_DIM,
                    font=("Segoe UI", 10))
    style.configure("PanelTitle.TLabel", background=PANEL_BG, foreground=FG,
                    font=("Segoe UI Semibold", 12))
    style.configure("Brand.TLabel", background=SIDE_BG, foreground=FG,
                    font=("Segoe UI Semibold", 13))
    style.configure("Status.TLabel", background=SIDE_BG, foreground=FG_DIM,
                    font=("Segoe UI", 9))
    style.configure("OK.TLabel", background=PANEL_BG, foreground=OK,
                    font=("Segoe UI Semibold", 10))
    style.configure("Warn.TLabel", background=PANEL_BG, foreground=WARN,
                    font=("Segoe UI Semibold", 10))
    style.configure("Danger.TLabel", background=PANEL_BG, foreground=DANGER,
                    font=("Segoe UI Semibold", 10))

    style.configure("Accent.TButton",
                    background=ACCENT, foreground="#ffffff",
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                    font=("Segoe UI Semibold", 11), padding=(14, 8))
    style.map("Accent.TButton",
              background=[("active", ACCENT_DIM), ("disabled", "#3a3f55")],
              foreground=[("disabled", "#aab")])
    style.configure("TButton",
                    background=PANEL_BG, foreground=FG, padding=(10, 6),
                    bordercolor=PANEL_BG, lightcolor=PANEL_BG, darkcolor=PANEL_BG)
    style.map("TButton", background=[("active", NAV_HOVER)])
    style.configure("Danger.TButton",
                    background=DANGER, foreground="#ffffff",
                    bordercolor=DANGER, lightcolor=DANGER, darkcolor=DANGER,
                    padding=(10, 6))
    style.map("Danger.TButton", background=[("active", "#c64a4a")])

    style.configure("Treeview",
                    background=PANEL_BG, foreground=FG,
                    fieldbackground=PANEL_BG, rowheight=24,
                    font=("Segoe UI", 9))
    style.configure("Treeview.Heading",
                    background=SIDE_BG, foreground=FG,
                    font=("Segoe UI Semibold", 9), padding=(6, 4))
    style.map("Treeview", background=[("selected", ACCENT_DIM)],
              foreground=[("selected", "#ffffff")])

    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=PANEL_BG, foreground=FG_DIM,
                    padding=(14, 6))
    style.map("TNotebook.Tab",
              background=[("selected", BG)],
              foreground=[("selected", FG)])

    style.configure("TProgressbar", background=ACCENT, troughcolor=PANEL_BG,
                    bordercolor=PANEL_BG, lightcolor=ACCENT, darkcolor=ACCENT)


# ----------------------------------------------------------------------
# widget helpers
# ----------------------------------------------------------------------

def make_card(parent, title: str | None = None) -> ttk.Frame:
    """A panel with optional title, padded interior."""
    outer = ttk.Frame(parent, style="Panel.TFrame")
    if title:
        ttk.Label(outer, text=title, style="PanelTitle.TLabel").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
    body = ttk.Frame(outer, style="Panel.TFrame")
    body.pack(fill="both", expand=True, padx=14, pady=(0, 12))
    outer.body = body  # type: ignore[attr-defined]
    return outer


def make_kv_row(parent, label: str, value: str, value_style: str = "Panel.TLabel") -> ttk.Label:
    row = ttk.Frame(parent, style="Panel.TFrame")
    row.pack(fill="x", pady=2)
    ttk.Label(row, text=label, style="PanelDim.TLabel", width=18).pack(side="left")
    val = ttk.Label(row, text=value, style=value_style)
    val.pack(side="left")
    return val


def fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n //= 1024 if unit == "B" else 1
        n = n / 1024 if unit != "B" else n
    return f"{n:.1f} TB"


def fmt_age(ts: float) -> str:
    secs = max(0, time.time() - ts)
    if secs < 60:
        return f"{int(secs)}s ago"
    if secs < 3600:
        return f"{int(secs / 60)}m ago"
    if secs < 86400:
        return f"{int(secs / 3600)}h ago"
    return f"{int(secs / 86400)}d ago"


def open_in_explorer(path: Path) -> None:
    p = str(path.resolve())
    try:
        if platform.system() == "Windows":
            os.startfile(p)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("Open failed", str(e))


# ======================================================================
# main app
# ======================================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x740")
        self.minsize(960, 620)
        self.configure(bg=BG)

        self.style = ttk.Style(self)
        configure_style(self.style)

        self.test_proc: subprocess.Popen | None = None
        self.sniffer_proc: subprocess.Popen | None = None
        self.remote_sha: str | None = None
        self.remote_err: str = ""
        self.commits_ahead: list[dict] = []

        self._build()
        self._show("dashboard")
        self._poll_processes()
        self._kick_update_check()

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # sidebar
        self.sidebar = ttk.Frame(self, style="Side.TFrame", width=220)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        self.sidebar.grid_propagate(False)

        ttk.Label(self.sidebar, text="Tesla Rack",
                  style="Brand.TLabel").pack(anchor="w", padx=18, pady=(20, 0))
        ttk.Label(self.sidebar, text="Control Suite",
                  style="Brand.TLabel").pack(anchor="w", padx=18, pady=(0, 18))

        self.nav_buttons: dict[str, tk.Label] = {}
        for key, label in (
            ("dashboard", "Dashboard"),
            ("test", "Run Steering Test"),
            ("sniffer", "CAN Sniffer"),
            ("logs", "Session Logs"),
            ("captures", "CAN Captures"),
            ("docs", "Documentation"),
            ("updates", "Updates"),
            ("about", "About"),
        ):
            self._make_nav_item(key, label)

        # spacer + version label
        spacer = tk.Frame(self.sidebar, bg=SIDE_BG)
        spacer.pack(fill="both", expand=True)
        self.sidebar_status = ttk.Label(
            self.sidebar,
            text=f"v{_read_app_version()}\n{(_installed_sha() or '?')[:7]}",
            style="Status.TLabel",
            justify="left",
        )
        self.sidebar_status.pack(anchor="w", padx=18, pady=12)

        # content
        self.content = ttk.Frame(self, style="TFrame")
        self.content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # status bar
        self.status_bar = ttk.Frame(self, style="Side.TFrame")
        self.status_bar.grid(row=1, column=1, sticky="ew")
        self.status_left = ttk.Label(
            self.status_bar, text="Ready", style="Status.TLabel"
        )
        self.status_left.pack(side="left", padx=14, pady=4)
        self.status_right = ttk.Label(
            self.status_bar, text="checking GitHub...", style="Status.TLabel"
        )
        self.status_right.pack(side="right", padx=14, pady=4)

        # views
        self.views: dict[str, View] = {
            "dashboard": DashboardView(self.content, self),
            "test": TestView(self.content, self),
            "sniffer": SnifferView(self.content, self),
            "logs": LogsView(self.content, self),
            "captures": CapturesView(self.content, self),
            "docs": DocsView(self.content, self),
            "updates": UpdatesView(self.content, self),
            "about": AboutView(self.content, self),
        }
        for v in self.views.values():
            v.grid(row=0, column=0, sticky="nsew")
        self.active: str | None = None

        # window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _make_nav_item(self, key: str, label: str):
        # tk.Label gives us the freedom to style hover/active states
        item = tk.Label(
            self.sidebar, text="   " + label, anchor="w",
            bg=SIDE_BG, fg=FG_DIM,
            font=("Segoe UI", 10), padx=8, pady=8,
        )
        item.pack(fill="x", padx=8, pady=1)

        def on_enter(_e, k=key, w=item):
            if self.active != k:
                w.configure(bg=NAV_HOVER, fg=FG)

        def on_leave(_e, k=key, w=item):
            if self.active != k:
                w.configure(bg=SIDE_BG, fg=FG_DIM)

        def on_click(_e, k=key):
            self._show(k)

        item.bind("<Enter>", on_enter)
        item.bind("<Leave>", on_leave)
        item.bind("<Button-1>", on_click)
        self.nav_buttons[key] = item

    def _show(self, key: str):
        # update nav highlighting
        for k, w in self.nav_buttons.items():
            if k == key:
                w.configure(bg=NAV_ACTIVE, fg=FG, font=("Segoe UI Semibold", 10))
            else:
                w.configure(bg=SIDE_BG, fg=FG_DIM, font=("Segoe UI", 10))
        self.active = key
        view = self.views[key]
        view.tkraise()
        view.on_show()

    # ------------------------------------------------------------------
    # status bar / update banner
    # ------------------------------------------------------------------

    def set_status(self, text: str):
        self.status_left.configure(text=text)

    def set_remote_status(self, text: str, color: str = FG_DIM):
        self.status_right.configure(text=text, foreground=color)

    def _kick_update_check(self):
        """Check GitHub in a background thread."""
        def worker():
            sha, err = gh_latest_sha()
            commits = []
            if sha:
                local = _installed_sha()
                if local and local != sha:
                    commits = gh_compare(local, sha)
            self.after(0, self._on_update_check_done, sha, err, commits)
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.set_remote_status("checking GitHub for updates...", FG_DIM)

    def _on_update_check_done(self, sha: str | None, err: str, commits: list):
        self.remote_sha = sha
        self.remote_err = err
        self.commits_ahead = commits
        local = _installed_sha()
        if err:
            self.set_remote_status(f"GitHub: {err}", WARN)
        elif local and sha and local != sha:
            self.set_remote_status(
                f"update available: {len(commits) or '?'} new commit(s)", ACCENT
            )
        elif sha:
            self.set_remote_status(f"up to date • {sha[:7]}", OK)
        else:
            self.set_remote_status("status unknown", FG_DIM)
        # Let any visible view refresh.
        if self.active:
            self.views[self.active].on_remote_state_changed()

    # ------------------------------------------------------------------
    # subprocess management
    # ------------------------------------------------------------------

    def launch_test(self):
        if self.test_proc and self.test_proc.poll() is None:
            messagebox.showinfo(APP_TITLE,
                                "Steering test is already running.")
            return False
        if not TARGET_SCRIPT.exists():
            messagebox.showerror(APP_TITLE,
                                 f"{TARGET_SCRIPT.name} is missing.")
            return False
        try:
            self.test_proc = subprocess.Popen(
                [sys.executable, str(TARGET_SCRIPT)],
                cwd=str(ROOT_DIR),
            )
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Failed to launch:\n{e}")
            return False
        self.set_status(f"Steering test running (PID {self.test_proc.pid})")
        return True

    def stop_test(self):
        if self.test_proc and self.test_proc.poll() is None:
            try:
                self.test_proc.terminate()
            except Exception:  # noqa: BLE001
                pass

    def launch_sniffer(self, args: list[str] | None = None):
        if self.sniffer_proc and self.sniffer_proc.poll() is None:
            messagebox.showinfo(APP_TITLE, "CAN sniffer is already running.")
            return False
        if not SNIFFER_SCRIPT.exists():
            messagebox.showerror(APP_TITLE,
                                 f"{SNIFFER_SCRIPT.name} is missing.")
            return False
        cmd = [sys.executable, str(SNIFFER_SCRIPT)] + (args or [])
        try:
            # Open in a new console window on Windows so the user
            # can watch the live frame counts.
            kw = {}
            if platform.system() == "Windows":
                kw["creationflags"] = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
            self.sniffer_proc = subprocess.Popen(cmd, cwd=str(ROOT_DIR), **kw)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(APP_TITLE, f"Failed to launch sniffer:\n{e}")
            return False
        return True

    def _poll_processes(self):
        # update status bar based on whether a test is running
        if self.test_proc and self.test_proc.poll() is None:
            self.set_status(
                f"Steering test running (PID {self.test_proc.pid})"
            )
        elif self.test_proc and self.test_proc.poll() is not None:
            rc = self.test_proc.returncode
            self.set_status(f"Last test exited with code {rc}")
            self.test_proc = None
            # let TestView refresh
            if self.active == "test":
                self.views["test"].on_show()
        else:
            self.set_status("Ready")
        self.after(800, self._poll_processes)

    def _on_close(self):
        if self.test_proc and self.test_proc.poll() is None:
            if not messagebox.askyesno(
                APP_TITLE,
                "The steering test is still running. Quit anyway?",
            ):
                return
        self.destroy()


# ======================================================================
# views
# ======================================================================

class View(ttk.Frame):
    def __init__(self, master, app: App):
        super().__init__(master, style="TFrame")
        self.app = app
        self.build()

    def build(self): ...
    def on_show(self): ...
    def on_remote_state_changed(self): ...


# ----------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------

class DashboardView(View):
    def build(self):
        ttk.Label(self, text="Dashboard", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(self,
                  text="Pre-AP Tesla Model S EPAS bench/road test harness.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 16))

        top = ttk.Frame(self, style="TFrame")
        top.pack(fill="x", pady=(0, 12))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        # status card
        status_card = make_card(top, "Install")
        status_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.kv_version = make_kv_row(status_card.body, "Version",  # type: ignore[attr-defined]
                                       _read_app_version())
        self.kv_local = make_kv_row(status_card.body, "Installed commit",  # type: ignore[attr-defined]
                                     (_installed_sha() or "(no .version file)")[:12])
        self.kv_remote = make_kv_row(status_card.body, "Latest on GitHub",  # type: ignore[attr-defined]
                                      "checking...")
        self.kv_state = make_kv_row(status_card.body, "Status",  # type: ignore[attr-defined]
                                     "checking...")

        # quick actions card
        actions_card = make_card(top, "Quick actions")
        actions_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ttk.Button(
            actions_card.body, text="Launch Steering Test",  # type: ignore[attr-defined]
            style="Accent.TButton",
            command=self._launch_test,
        ).pack(fill="x", pady=4)
        ttk.Button(
            actions_card.body, text="Open CAN Sniffer",  # type: ignore[attr-defined]
            command=lambda: self.app._show("sniffer"),
        ).pack(fill="x", pady=4)
        ttk.Button(
            actions_card.body, text="Browse Session Logs",  # type: ignore[attr-defined]
            command=lambda: self.app._show("logs"),
        ).pack(fill="x", pady=4)
        ttk.Button(
            actions_card.body, text="Open repo on GitHub",  # type: ignore[attr-defined]
            command=lambda: webbrowser.open(GITHUB_URL),
        ).pack(fill="x", pady=4)

        # recent sessions card
        recent_card = make_card(self, "Recent test sessions")
        recent_card.pack(fill="both", expand=True)

        cols = ("when", "name", "size")
        self.recent_tree = ttk.Treeview(
            recent_card.body, columns=cols, show="headings", height=10  # type: ignore[attr-defined]
        )
        self.recent_tree.heading("when", text="When")
        self.recent_tree.heading("name", text="Session")
        self.recent_tree.heading("size", text="Size")
        self.recent_tree.column("when", width=180)
        self.recent_tree.column("name", width=420)
        self.recent_tree.column("size", width=80, anchor="e")
        self.recent_tree.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(recent_card.body, orient="vertical",  # type: ignore[attr-defined]
                           command=self.recent_tree.yview)
        sb.pack(side="right", fill="y")
        self.recent_tree.configure(yscrollcommand=sb.set)
        self.recent_tree.bind("<Double-1>", lambda _e: self.app._show("logs"))

    def _launch_test(self):
        if self.app.launch_test():
            self.app._show("test")

    def on_show(self):
        self.kv_version.configure(text=_read_app_version())
        self.kv_local.configure(
            text=(_installed_sha() or "(no .version file)")[:12]
        )
        self.on_remote_state_changed()
        self._refresh_recent()

    def on_remote_state_changed(self):
        if self.app.remote_err:
            self.kv_remote.configure(text=self.app.remote_err)
            self.kv_state.configure(text="cannot reach GitHub", style="Warn.TLabel")
            return
        if not self.app.remote_sha:
            self.kv_remote.configure(text="checking...")
            self.kv_state.configure(text="checking...")
            return
        self.kv_remote.configure(text=self.app.remote_sha[:12])
        local = _installed_sha()
        if local and local == self.app.remote_sha:
            self.kv_state.configure(text="up to date", style="OK.TLabel")
        elif local:
            self.kv_state.configure(
                text=f"{len(self.app.commits_ahead) or '?'} commit(s) behind",
                style="Warn.TLabel",
            )
        else:
            self.kv_state.configure(text="first run", style="OK.TLabel")

    def _refresh_recent(self):
        for i in self.recent_tree.get_children():
            self.recent_tree.delete(i)
        sessions = collect_sessions()
        for s in sessions[:30]:
            size = fmt_size(s["size"])
            self.recent_tree.insert(
                "", "end",
                values=(fmt_age(s["mtime"]), s["display"], size),
            )


# ----------------------------------------------------------------------
# Run Test
# ----------------------------------------------------------------------

class TestView(View):
    def build(self):
        ttk.Label(self, text="Run Steering Test",
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(self,
                  text="Launches tesla_control.py - the live CAN-bus "
                       "EPAS rack control program.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 16))

        preflight = make_card(self, "Pre-flight reminders")
        preflight.pack(fill="x", pady=(0, 12))
        for line in (
            "• Read SAFETY.md once if you haven't.",
            "• Confirm the SYS TEC USB-CAN adapter is plugged in.",
            "• Confirm the rack is on bench-test power and is the patched rack.",
            "• Have an E-STOP path ready: keyboard 'X', the GUI button, the rack power cut.",
            "• 30 MPH MODE off at boot. Only enable it deliberately.",
        ):
            ttk.Label(preflight.body, text=line,  # type: ignore[attr-defined]
                      style="Panel.TLabel", justify="left").pack(anchor="w", pady=1)

        action = make_card(self, "Launch")
        action.pack(fill="x")
        body = action.body  # type: ignore[attr-defined]
        self.state_label = ttk.Label(
            body, text="Status: not running", style="Panel.TLabel"
        )
        self.state_label.pack(anchor="w", pady=(0, 10))
        btn_row = ttk.Frame(body, style="Panel.TFrame")
        btn_row.pack(fill="x")
        self.launch_btn = ttk.Button(
            btn_row, text="Launch Steering Test",
            style="Accent.TButton",
            command=self._launch,
        )
        self.launch_btn.pack(side="left")
        self.stop_btn = ttk.Button(
            btn_row, text="Stop", style="Danger.TButton",
            command=self._stop,
        )
        self.stop_btn.pack(side="left", padx=(8, 0))

        ttk.Label(
            self,
            text="The control GUI opens in its own window. This page "
                 "stays here so you can come back and look at logs.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(16, 0))

    def _launch(self):
        self.app.launch_test()
        self._refresh_state()

    def _stop(self):
        if not self.app.test_proc or self.app.test_proc.poll() is not None:
            return
        if messagebox.askyesno(
            APP_TITLE,
            "Send a stop signal to the steering test? "
            "Use this only if its E-STOP isn't responding.",
        ):
            self.app.stop_test()

    def _refresh_state(self):
        running = (self.app.test_proc is not None
                   and self.app.test_proc.poll() is None)
        if running:
            self.state_label.configure(
                text=f"Status: running (PID {self.app.test_proc.pid})",
                style="OK.TLabel",
            )
            self.launch_btn.state(["disabled"])
            self.stop_btn.state(["!disabled"])
        else:
            self.state_label.configure(
                text="Status: not running",
                style="Panel.TLabel",
            )
            self.launch_btn.state(["!disabled"])
            self.stop_btn.state(["disabled"])

    def on_show(self):
        self._refresh_state()


# ----------------------------------------------------------------------
# Sniffer
# ----------------------------------------------------------------------

class SnifferView(View):
    def build(self):
        ttk.Label(self, text="CAN Sniffer", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text="Passive CAN bus listener for diagnostics. Opens in a "
                 "separate console window.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 16))

        card = make_card(self, "Launch sniffer")
        card.pack(fill="x")
        body = card.body  # type: ignore[attr-defined]

        # filter input
        row = ttk.Frame(body, style="Panel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Filter (CAN ID, hex):",
                  style="Panel.TLabel", width=22).pack(side="left")
        self.filter_var = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self.filter_var, width=20).pack(side="left")
        ttk.Label(row, text="(blank = all IDs, e.g. 0x488)",
                  style="PanelDim.TLabel").pack(side="left", padx=8)

        # save toggle
        row2 = ttk.Frame(body, style="Panel.TFrame")
        row2.pack(fill="x", pady=4)
        self.save_var = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(
            row2, text="Save capture to field_testing/captures/",
            variable=self.save_var,
            bg=PANEL_BG, fg=FG, selectcolor=PANEL_BG,
            activebackground=PANEL_BG, activeforeground=FG,
            font=("Segoe UI", 10),
        )
        chk.pack(anchor="w")

        ttk.Button(
            body, text="Start CAN Sniffer", style="Accent.TButton",
            command=self._launch,
        ).pack(anchor="w", pady=(10, 0))

        ttk.Label(
            self,
            text="The sniffer prints frames live. Close its console "
                 "window to stop. Captures save to field_testing/captures/.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(16, 0))

    def _launch(self):
        args: list[str] = []
        f = self.filter_var.get().strip()
        if f:
            args += ["--id", f]
        if self.save_var.get():
            args += ["--save"]
        self.app.launch_sniffer(args)


# ----------------------------------------------------------------------
# Logs / Captures shared helpers
# ----------------------------------------------------------------------

def collect_sessions() -> list[dict]:
    """Return a list of session dicts sorted by mtime desc."""
    out: list[dict] = []
    if LOGS_DIR.exists():
        # group by basename (session_xxx.log/.csv pairs)
        groups: dict[str, dict] = {}
        for p in LOGS_DIR.iterdir():
            if p.suffix not in (".log", ".csv"):
                continue
            stem = p.stem
            g = groups.setdefault(stem, {"name": stem, "files": []})
            g["files"].append(p)
        for stem, g in groups.items():
            files = g["files"]
            mtime = max(f.stat().st_mtime for f in files)
            size = sum(f.stat().st_size for f in files)
            out.append({
                "kind": "log",
                "name": stem,
                "display": stem,
                "path": LOGS_DIR,
                "files": files,
                "mtime": mtime,
                "size": size,
            })
    if SESSIONS_DIR.exists():
        for d in SESSIONS_DIR.iterdir():
            if not d.is_dir():
                continue
            files = list(d.iterdir())
            if not files:
                continue
            mtime = max(f.stat().st_mtime for f in files)
            size = sum(f.stat().st_size for f in files if f.is_file())
            out.append({
                "kind": "session",
                "name": d.name,
                "display": f"sessions/{d.name}",
                "path": d,
                "files": files,
                "mtime": mtime,
                "size": size,
            })
    out.sort(key=lambda s: s["mtime"], reverse=True)
    return out


def collect_captures() -> list[dict]:
    out: list[dict] = []
    if not CAPTURES_DIR.exists():
        return out
    for d in CAPTURES_DIR.iterdir():
        if not d.is_dir():
            continue
        files = [f for f in d.iterdir() if f.is_file()]
        if not files:
            continue
        mtime = max(f.stat().st_mtime for f in files)
        size = sum(f.stat().st_size for f in files)
        out.append({
            "name": d.name,
            "path": d,
            "files": files,
            "mtime": mtime,
            "size": size,
        })
    out.sort(key=lambda s: s["mtime"], reverse=True)
    return out


# ----------------------------------------------------------------------
# Logs view
# ----------------------------------------------------------------------

class LogsView(View):
    def build(self):
        ttk.Label(self, text="Session Logs", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text="Per-session .log + .csv pairs. Double-click an entry "
                 "to open the source folder.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 16))

        body = ttk.Frame(self, style="TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # left: list
        left = make_card(body, "Sessions")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        cols = ("when", "name", "size")
        self.tree = ttk.Treeview(
            left.body, columns=cols, show="headings"  # type: ignore[attr-defined]
        )
        for c, t, w in (
            ("when", "When", 140),
            ("name", "Name", 280),
            ("size", "Size", 80),
        ):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w" if c != "size" else "e")
        self.tree.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(left.body, orient="vertical",  # type: ignore[attr-defined]
                           command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_double)

        # right: preview
        right = ttk.Frame(body, style="TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        header = make_card(right, "Selected")
        header.grid(row=0, column=0, sticky="ew")
        self.kv_name = make_kv_row(header.body, "Name", "(none)")  # type: ignore[attr-defined]
        self.kv_when = make_kv_row(header.body, "Modified", "-")  # type: ignore[attr-defined]
        self.kv_size = make_kv_row(header.body, "Total size", "-")  # type: ignore[attr-defined]
        self.kv_csv = make_kv_row(header.body, "CSV rows", "-")  # type: ignore[attr-defined]

        btns = ttk.Frame(header.body, style="Panel.TFrame")  # type: ignore[attr-defined]
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Open in Explorer",
                   command=self._open_explorer).pack(side="left")
        ttk.Button(btns, text="Refresh", command=self._refresh).pack(
            side="left", padx=(8, 0)
        )

        preview_card = make_card(right, ".log preview (last 200 lines)")
        preview_card.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.preview = scrolledtext.ScrolledText(
            preview_card.body, wrap=tk.NONE,  # type: ignore[attr-defined]
            bg=PANEL_BG, fg=FG, font=("Consolas", 9), height=20,
            relief="flat", insertbackground=FG,
        )
        self.preview.pack(fill="both", expand=True)
        self.preview.configure(state="disabled")

        self.sessions: list[dict] = []

    def on_show(self):
        self._refresh()

    def _refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.sessions = collect_sessions()
        for s in self.sessions:
            self.tree.insert(
                "", "end",
                iid=str(id(s)),
                values=(
                    datetime.fromtimestamp(s["mtime"]).strftime("%Y-%m-%d %H:%M"),
                    s["display"],
                    fmt_size(s["size"]),
                ),
            )
        self._clear_preview()

    def _selected(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            return None
        for s in self.sessions:
            if str(id(s)) == sel[0]:
                return s
        return None

    def _on_select(self, _e=None):
        s = self._selected()
        if not s:
            return
        self.kv_name.configure(text=s["display"])
        self.kv_when.configure(
            text=datetime.fromtimestamp(s["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
        )
        self.kv_size.configure(text=fmt_size(s["size"]))
        # find log + csv
        log_files = [f for f in s["files"] if f.suffix == ".log"]
        csv_files = [f for f in s["files"] if f.suffix == ".csv"]
        if csv_files:
            try:
                with open(csv_files[0], "r", newline="", encoding="utf-8", errors="ignore") as f:
                    n = sum(1 for _ in f) - 1
                self.kv_csv.configure(text=f"{n}")
            except OSError:
                self.kv_csv.configure(text="?")
        else:
            self.kv_csv.configure(text="(no .csv)")

        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if log_files:
            try:
                with open(log_files[0], "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-200:]
                self.preview.insert("1.0", "".join(lines))
            except OSError as e:
                self.preview.insert("1.0", f"(could not read log: {e})")
        else:
            self.preview.insert("1.0", "(no .log file in this session)")
        self.preview.configure(state="disabled")

    def _on_double(self, _e=None):
        self._open_explorer()

    def _open_explorer(self):
        s = self._selected()
        if not s:
            return
        open_in_explorer(s["path"])

    def _clear_preview(self):
        self.kv_name.configure(text="(none)")
        self.kv_when.configure(text="-")
        self.kv_size.configure(text="-")
        self.kv_csv.configure(text="-")
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.configure(state="disabled")


# ----------------------------------------------------------------------
# Captures view
# ----------------------------------------------------------------------

class CapturesView(View):
    def build(self):
        ttk.Label(self, text="CAN Captures", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text="Saved CAN sniffer captures in field_testing/captures/.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 16))

        body = ttk.Frame(self, style="TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        left = make_card(body, "Captures")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        cols = ("when", "name", "size")
        self.tree = ttk.Treeview(
            left.body, columns=cols, show="headings"  # type: ignore[attr-defined]
        )
        for c, t, w in (
            ("when", "When", 140),
            ("name", "Name", 280),
            ("size", "Size", 80),
        ):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w" if c != "size" else "e")
        self.tree.pack(fill="both", expand=True, side="left")
        sb = ttk.Scrollbar(left.body, orient="vertical",  # type: ignore[attr-defined]
                           command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _e: self._open_explorer())

        right = ttk.Frame(body, style="TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        info = make_card(right, "Selected capture")
        info.grid(row=0, column=0, sticky="ew")
        self.kv_name = make_kv_row(info.body, "Name", "(none)")  # type: ignore[attr-defined]
        self.kv_when = make_kv_row(info.body, "Modified", "-")  # type: ignore[attr-defined]
        self.kv_size = make_kv_row(info.body, "Total size", "-")  # type: ignore[attr-defined]
        self.kv_files = make_kv_row(info.body, "Files", "-")  # type: ignore[attr-defined]
        ttk.Button(info.body, text="Open in Explorer",  # type: ignore[attr-defined]
                   command=self._open_explorer).pack(anchor="w", pady=(8, 0))

        readme = make_card(right, "README.md preview")
        readme.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.preview = scrolledtext.ScrolledText(
            readme.body, wrap=tk.WORD,  # type: ignore[attr-defined]
            bg=PANEL_BG, fg=FG, font=("Consolas", 9),
            relief="flat", insertbackground=FG,
        )
        self.preview.pack(fill="both", expand=True)
        self.preview.configure(state="disabled")
        self.captures: list[dict] = []

    def on_show(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.captures = collect_captures()
        for c in self.captures:
            self.tree.insert(
                "", "end", iid=str(id(c)),
                values=(
                    datetime.fromtimestamp(c["mtime"]).strftime("%Y-%m-%d %H:%M"),
                    c["name"],
                    fmt_size(c["size"]),
                ),
            )

    def _selected(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            return None
        for c in self.captures:
            if str(id(c)) == sel[0]:
                return c
        return None

    def _on_select(self, _e=None):
        c = self._selected()
        if not c:
            return
        self.kv_name.configure(text=c["name"])
        self.kv_when.configure(
            text=datetime.fromtimestamp(c["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
        )
        self.kv_size.configure(text=fmt_size(c["size"]))
        self.kv_files.configure(text=str(len(c["files"])))

        readme = c["path"] / "README.md"
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if readme.exists():
            try:
                self.preview.insert("1.0", readme.read_text(
                    encoding="utf-8", errors="ignore"))
            except OSError as e:
                self.preview.insert("1.0", f"(could not read: {e})")
        else:
            self.preview.insert("1.0", "(no README.md)")
        self.preview.configure(state="disabled")

    def _open_explorer(self):
        c = self._selected()
        if c:
            open_in_explorer(c["path"])


# ----------------------------------------------------------------------
# Docs view
# ----------------------------------------------------------------------

DOC_LIST = [
    ("README.md",                ROOT_DIR / "README.md"),
    ("SAFETY.md",                ROOT_DIR / "SAFETY.md"),
    ("docs/GUIDE.md",            DOCS_DIR / "GUIDE.md"),
    ("docs/PROTOCOL.md",         DOCS_DIR / "PROTOCOL.md"),
    ("docs/TROUBLESHOOTING.md",  DOCS_DIR / "TROUBLESHOOTING.md"),
    ("CHANGELOG.md",             ROOT_DIR / "CHANGELOG.md"),
    ("PROJECT_MEMORY.md",        ROOT_DIR / "PROJECT_MEMORY.md"),
    ("ROADMAP.md",               ROOT_DIR / "ROADMAP.md"),
    ("V5_PLAN.md",               ROOT_DIR / "V5_PLAN.md"),
]


class DocsView(View):
    def build(self):
        ttk.Label(self, text="Documentation", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text="Reference docs shipped with the program.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 16))

        body = ttk.Frame(self, style="TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        side = make_card(body, "Files")
        side.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        self.list = tk.Listbox(
            side.body, bg=PANEL_BG, fg=FG, selectbackground=ACCENT_DIM,  # type: ignore[attr-defined]
            selectforeground="#ffffff", font=("Segoe UI", 10),
            relief="flat", highlightthickness=0, activestyle="none", width=28,
        )
        self.list.pack(fill="both", expand=True)
        for label, _ in DOC_LIST:
            self.list.insert("end", "  " + label)
        self.list.bind("<<ListboxSelect>>", self._on_select)

        text_card = make_card(body, "Preview")
        text_card.grid(row=0, column=1, sticky="nsew")
        self.preview = scrolledtext.ScrolledText(
            text_card.body, wrap=tk.WORD,  # type: ignore[attr-defined]
            bg=PANEL_BG, fg=FG, font=("Consolas", 10),
            relief="flat", insertbackground=FG,
        )
        self.preview.pack(fill="both", expand=True)
        self.preview.configure(state="disabled")

    def _on_select(self, _e=None):
        sel = self.list.curselection()
        if not sel:
            return
        _, path = DOC_LIST[sel[0]]
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if path.exists():
            try:
                self.preview.insert("1.0", path.read_text(
                    encoding="utf-8", errors="ignore"))
            except OSError as e:
                self.preview.insert("1.0", f"(could not read: {e})")
        else:
            self.preview.insert("1.0", f"(file not found: {path})")
        self.preview.configure(state="disabled")


# ----------------------------------------------------------------------
# Updates view
# ----------------------------------------------------------------------

class UpdatesView(View):
    def build(self):
        ttk.Label(self, text="Updates", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text="Pulls the latest main from GitHub. Tesla Rack Control Suite "
                 "saves your logs and field-test data across updates.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 16))

        card = make_card(self, "Status")
        card.pack(fill="x", pady=(0, 12))
        self.kv_local = make_kv_row(card.body, "Installed",  # type: ignore[attr-defined]
                                     (_installed_sha() or "?")[:12])
        self.kv_remote = make_kv_row(card.body, "Latest on GitHub",  # type: ignore[attr-defined]
                                      "checking...")
        self.kv_state = make_kv_row(card.body, "State", "checking...")  # type: ignore[attr-defined]

        actions = ttk.Frame(card.body, style="Panel.TFrame")  # type: ignore[attr-defined]
        actions.pack(anchor="w", pady=(8, 0))
        ttk.Button(actions, text="Check now",
                   command=self._check_now).pack(side="left")
        self.update_btn = ttk.Button(
            actions, text="Update now",
            style="Accent.TButton", command=self._update_now,
        )
        self.update_btn.pack(side="left", padx=(8, 0))

        # commit list
        commits_card = make_card(self, "Pending commits")
        commits_card.pack(fill="both", expand=True)
        self.commits = scrolledtext.ScrolledText(
            commits_card.body, wrap=tk.WORD,  # type: ignore[attr-defined]
            bg=PANEL_BG, fg=FG, font=("Consolas", 10),
            relief="flat", insertbackground=FG, height=14,
        )
        self.commits.pack(fill="both", expand=True)
        self.commits.configure(state="disabled")

    def on_show(self):
        self.on_remote_state_changed()

    def on_remote_state_changed(self):
        self.kv_local.configure(text=(_installed_sha() or "?")[:12])
        if self.app.remote_err:
            self.kv_remote.configure(text=self.app.remote_err)
            self.kv_state.configure(text="cannot reach GitHub", style="Warn.TLabel")
            self.update_btn.state(["disabled"])
            self._set_commits("(no data)")
            return
        if not self.app.remote_sha:
            self.kv_remote.configure(text="checking...")
            self.kv_state.configure(text="checking...")
            self.update_btn.state(["disabled"])
            return
        self.kv_remote.configure(text=self.app.remote_sha[:12])
        local = _installed_sha()
        if local and local == self.app.remote_sha:
            self.kv_state.configure(text="up to date", style="OK.TLabel")
            self.update_btn.state(["disabled"])
            self._set_commits("(no pending commits)")
        elif local:
            self.kv_state.configure(
                text=f"{len(self.app.commits_ahead) or '?'} commit(s) behind",
                style="Warn.TLabel",
            )
            self.update_btn.state(["!disabled"])
            self._render_commits()
        else:
            self.kv_state.configure(text="first run (no .version)",
                                    style="OK.TLabel")
            self.update_btn.state(["!disabled"])
            self._set_commits("(no installed version recorded - "
                              "applying an update will write .version)")

    def _set_commits(self, text: str):
        self.commits.configure(state="normal")
        self.commits.delete("1.0", "end")
        self.commits.insert("1.0", text)
        self.commits.configure(state="disabled")

    def _render_commits(self):
        self.commits.configure(state="normal")
        self.commits.delete("1.0", "end")
        for c in self.app.commits_ahead:
            sha = c.get("sha", "")[:7]
            msg = c.get("commit", {}).get("message", "").splitlines()[0]
            author = c.get("commit", {}).get("author", {}).get("name", "")
            self.commits.insert("end", f"{sha}  {msg}\n         by {author}\n\n")
        self.commits.configure(state="disabled")

    def _check_now(self):
        self.app._kick_update_check()

    def _update_now(self):
        if not self.app.remote_sha:
            return
        if not messagebox.askyesno(
            APP_TITLE,
            "Download the latest version from GitHub and replace the "
            "installed files? Your logs and field-test data are preserved.",
        ):
            return
        ok, err = run_http_update(self.app.remote_sha)
        if not ok:
            messagebox.showerror(APP_TITLE, f"Update failed:\n{err}")
            return
        # run pip install in background
        rc, log = pip_install_silent()
        if rc != 0:
            messagebox.showwarning(
                APP_TITLE,
                "Update applied, but pip install reported errors. "
                "Check requirements.txt manually.",
            )
        if messagebox.askyesno(
            APP_TITLE,
            "Update applied. Restart Tesla Rack Control Suite now?",
        ):
            os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())])


# ----------------------------------------------------------------------
# About view
# ----------------------------------------------------------------------

class AboutView(View):
    def build(self):
        ttk.Label(self, text="About", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self,
                  text=APP_TITLE,
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 16))

        card = make_card(self, "Build info")
        card.pack(fill="x", pady=(0, 12))
        make_kv_row(card.body, "Program version",  # type: ignore[attr-defined]
                    _read_app_version())
        make_kv_row(card.body, "Installed commit",  # type: ignore[attr-defined]
                    (_installed_sha() or "?")[:12])
        make_kv_row(card.body, "Python",  # type: ignore[attr-defined]
                    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} "
                    f"({'32-bit' if sys.maxsize < 2**32 else '64-bit'})")
        make_kv_row(card.body, "Platform",  # type: ignore[attr-defined]
                    f"{platform.system()} {platform.release()}")
        make_kv_row(card.body, "Install path",  # type: ignore[attr-defined]
                    str(ROOT_DIR))

        team = make_card(self, "Team")
        team.pack(fill="x", pady=(0, 12))
        for line in (
            "Derek Nagel  -  project owner, software lead",
            "Jordan       -  hardware lead, EPAS firmware flash",
            "Charlie Yonkura - field testing, session logs",
            "Claude        - pair programmer",
        ):
            ttk.Label(team.body, text=line, style="Panel.TLabel").pack(  # type: ignore[attr-defined]
                anchor="w", pady=1)

        links = make_card(self, "Links")
        links.pack(fill="x")
        ttk.Button(links.body, text="GitHub repo",  # type: ignore[attr-defined]
                   command=lambda: webbrowser.open(GITHUB_URL)).pack(
            anchor="w", pady=2
        )
        ttk.Button(links.body, text="Open install folder",  # type: ignore[attr-defined]
                   command=lambda: open_in_explorer(ROOT_DIR)).pack(
            anchor="w", pady=2
        )
        ttk.Button(links.body, text="Open logs folder",  # type: ignore[attr-defined]
                   command=lambda: open_in_explorer(LOGS_DIR)).pack(
            anchor="w", pady=2
        )

        ttk.Label(
            self,
            text="MIT licensed. Read SAFETY.md before running anything. "
                 "This software controls a real EPAS rack on a real car.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(16, 0))


# ----------------------------------------------------------------------
# update helpers (HTTP/zip)
# ----------------------------------------------------------------------

def run_http_update(remote_sha: str) -> tuple[bool, str]:
    """Reuse launcher's HTTP zip update, then write .version."""
    try:
        from launcher import _download_zip, _apply_zip, _write_local_sha
    except Exception as e:  # noqa: BLE001
        return False, f"could not import launcher helpers: {e}"
    try:
        zip_bytes = _download_zip()
        _apply_zip(zip_bytes)
        _write_local_sha(remote_sha)
    except Exception as e:  # noqa: BLE001
        return False, str(e)
    return True, ""


def pip_install_silent() -> tuple[int, str]:
    req = ROOT_DIR / "requirements.txt"
    if not req.exists():
        return 0, ""
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
        cwd=str(ROOT_DIR),
        capture_output=True, text=True, timeout=180,
    )
    return r.returncode, (r.stdout + r.stderr).strip()


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
