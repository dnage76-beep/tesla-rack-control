"""
Tesla Rack Control - one-click installer.

Downloads the main branch as a zip, extracts to ~/TeslaRackControl,
runs `pip install -r requirements.txt`, and creates a "Tesla Rack
Control" shortcut on the user's desktop.

Run by double-clicking `Install Tesla Rack Control.bat`, which fetches
this script from raw.githubusercontent.com and runs it.

Idempotent: re-running upgrades to the latest main and refreshes
the shortcut. Existing logs/ and field_testing/sessions/ are
preserved (the launcher itself preserves them on subsequent updates).
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

OWNER = "dnage76-beep"
REPO = "tesla-rack-control"
BRANCH = "main"
USER_AGENT = "tesla-rack-control-installer"

DEST = os.path.join(os.path.expanduser("~"), "TeslaRackControl")
PRESERVE = {"logs", "field_testing/sessions", "field_testing/captures"}


def step(msg):
    print()
    print(f"=== {msg} ===")


def get_latest_sha():
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/commits/{BRANCH}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["sha"]


def is_preserved(rel):
    rp = rel.replace("\\", "/")
    return any(rp == p or rp.startswith(p + "/") for p in PRESERVE)


def download_and_extract(dest):
    url = (
        f"https://codeload.github.com/{OWNER}/{REPO}/zip/refs/heads/{BRANCH}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    print("Downloading repository archive from GitHub...")
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    print(f"Downloaded {len(data) // 1024} KB.")

    print(f"Extracting to {dest}...")
    tmp = tempfile.mkdtemp(prefix="trc_install_")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(tmp)
        roots = [
            n for n in os.listdir(tmp)
            if os.path.isdir(os.path.join(tmp, n)) and n != "__MACOSX"
        ]
        if not roots:
            raise RuntimeError("zip archive had no top-level directory")
        src = os.path.join(tmp, roots[0])

        os.makedirs(dest, exist_ok=True)
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            if rel != "." and is_preserved(rel):
                dirs[:] = []
                continue
            target_root = dest if rel == "." else os.path.join(dest, rel)
            os.makedirs(target_root, exist_ok=True)
            for f in files:
                rel_file = f if rel == "." else os.path.join(rel, f)
                if is_preserved(rel_file):
                    continue
                shutil.copy2(
                    os.path.join(root, f),
                    os.path.join(target_root, f),
                )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def write_version(dest, sha):
    with open(os.path.join(dest, ".version"), "w") as f:
        f.write(sha)


def pip_install(dest):
    req = os.path.join(dest, "requirements.txt")
    if not os.path.exists(req):
        print("(no requirements.txt found, skipping)")
        return True
    rc = subprocess.call(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"]
    )
    if rc != 0:
        print("WARNING: pip self-upgrade failed, continuing.")
    rc = subprocess.call(
        [sys.executable, "-m", "pip", "install", "-r", req]
    )
    return rc == 0


def make_shortcut(dest):
    script = os.path.join(dest, "make_shortcut.py")
    if not os.path.exists(script):
        print("(make_shortcut.py not found, skipping)")
        return False
    return subprocess.call([sys.executable, script]) == 0


def main():
    print("=" * 50)
    print(" Tesla Rack Control - One-Click Installer")
    print("=" * 50)
    print(f"Install location: {DEST}")

    step("Checking GitHub for the latest version")
    try:
        sha = get_latest_sha()
    except Exception as e:
        print(f"ERROR: could not reach GitHub: {e}")
        input("\nPress Enter to close...")
        sys.exit(1)
    print(f"Latest commit: {sha[:7]}")

    step("Installing program files")
    try:
        download_and_extract(DEST)
        write_version(DEST, sha)
    except Exception as e:
        print(f"ERROR: install failed: {e}")
        input("\nPress Enter to close...")
        sys.exit(1)

    step("Installing Python dependencies")
    if not pip_install(DEST):
        print("WARNING: pip install reported errors. The program may "
              "still run, but check the messages above.")

    step("Creating desktop shortcut")
    if not make_shortcut(DEST):
        print("WARNING: shortcut creation failed. You can still launch")
        print(f"the program by double-clicking launcher.bat in {DEST}")

    step("Done")
    print("Look for 'Tesla Rack Control' on your desktop.")
    print()
    print("If you haven't already, install the SYS TEC USB-CAN driver")
    print("from:")
    print("  https://www.systec-electronic.com/en/services-support/downloads")
    print()
    try:
        input("Press Enter to close...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
