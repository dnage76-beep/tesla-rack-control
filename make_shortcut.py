"""
Create a "Tesla Rack Control" shortcut on the user's Windows desktop
pointing at launcher.bat. Idempotent: overwrites any existing shortcut
with the same name.

No-op on non-Windows hosts.
"""

import os
import subprocess
import sys


def main():
    if sys.platform != "win32":
        print("Not Windows, skipping shortcut.")
        return 0

    repo = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(repo, "launcher.bat")
    if not os.path.exists(target):
        print(f"ERROR: {target} not found.")
        return 1

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(desktop):
        # OneDrive-redirected desktop
        alt = os.path.join(
            os.path.expanduser("~"), "OneDrive", "Desktop"
        )
        if os.path.isdir(alt):
            desktop = alt
        else:
            print(f"ERROR: desktop folder not found at {desktop}")
            return 1

    shortcut = os.path.join(desktop, "Tesla Rack Control.lnk")

    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{shortcut}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.WorkingDirectory = '{repo}'; "
        "$s.WindowStyle = 1; "
        "$s.Description = 'Tesla Rack Control launcher'; "
        "$s.Save()"
    )
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("PowerShell error:", r.stderr)
        return r.returncode
    print(f"Created shortcut: {shortcut}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
