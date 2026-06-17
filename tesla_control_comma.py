"""
Tesla Rack Control COMMA  --  v6.0.0-dev
========================================

Variant of tesla_control.py that takes its steering target from a comma
3X running openpilot, instead of from the slider/keyboard (slider build)
or the Spektrum RC bridge (v5). openpilot is the "brain"; this program
is the unchanged, proven actuator: it rate-limits the angle and emits
0x488 DAS_steeringControl on the chassis bus through the SYS TEC adapter.

DATA PATH
    comma 3X: openpilot controlsd -> carControl.actuators.steeringAngleDeg
      -> comma_steer_forward.py (cereal SubMaster) -> TCP socket
    laptop:   this program (CommaLinkReader) -> ctrl.target_angle_deg
      -> tesla_control.CanWorker (rate limit + LPF + clamp) -> 0x488 -> rack

    All CAN protocol code, the 360 deg clamp, the rate limiter, the
    0x370 RX-timeout E-STOP, divergence/bus/loop watchdogs, the session
    logger and the GUI come from tesla_control.py UNCHANGED. This file
    only adds a socket reader and a COMMA INPUT panel -- the exact shape
    of the v5 RC bridge (tesla_control_rc.py), with TCP in place of
    pyserial.

ENGAGEMENT  ("pull of the cruise control lever")
    On the pre-AP car the cruise stalk pulled toward you
    (STW_ACTN_RQ.SpdCtrlLvr_Stat == 2, "RWD"/resume) engages openpilot
    ON THE COMMA; openpilot then asserts carControl.latActive. The
    forwarder ships that flag, and by default this program mirrors it:
    latActive rising -> engage (through the guarded toggle_engage, so the
    park-to-engage gate still applies); latActive falling or link lost ->
    disengage. Uncheck "follow openpilot engage" to arm/disarm manually
    with the ENGAGE button instead; the comma angle is still only applied
    while openpilot is actively steering (latActive).

SAFETY NOTES
    - The comma's panda must NOT transmit 0x488. This laptop is the sole
      transmitter of that id (Theory C, PROJECT_MEMORY.md Section 8). Two
      receivers on the bus is fine; two transmitters is the May-2026
      contention.
    - Link-loss ALWAYS disengages (the worker's 0x370 watchdog only
      covers the rack link, not the comma link).
    - ANGLE SIGN IS UNVERIFIED until bench test. openpilot's
      steeringAngleDeg sign convention vs. our target_angle_deg has not
      been confirmed against hardware. FIRST bench run: command a few
      degrees and confirm the wheel turns the SAME way openpilot intends.
      If mirrored, pass --invert.
    - Base is tesla_control.py v4.3.3, whose worker auto-disengages above
      ~1 mph (real-motion guard) and gates engage to Park. That is
      CORRECT for bench / wheels-off-ground bring-up (M0-M2). Driving the
      car on a road (M3+) requires building on a base with that
      auto-disengage removed (the v5.0.4 change on
      claude/remove-eac-auto-disengage). Do not skip that step for road use.

USAGE
    python tesla_control_comma.py --comma-host 192.168.43.1 [--comma-port 7654]
    (find the 3X IP from its network settings; a wired USB-ethernet link
    is strongly preferred over Wi-Fi for latency.)
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
import tkinter as tk
from typing import Optional

import tesla_control as base


__version__ = "6.0.0-dev"


# ============================================================================
# CONFIGURATION
# ============================================================================

COMMA_DEFAULT_PORT = 7654

# Link-loss detection. If no message arrives for this long, the link is
# considered dead and engagement is dropped.
COMMA_LINK_TIMEOUT_MS = 200

# Reconnect backoff when the socket drops or refuses.
COMMA_RECONNECT_S = 1.0

# Sanity ceiling on a single received angle. The worker clamps to
# HARD_ANGLE_LIMIT_DEG anyway; this just rejects obviously-garbage frames
# (e.g. a NaN or a parse that produced a huge number) before they reach
# ControlState.
COMMA_MAX_ABS_ANGLE_DEG = base.HARD_ANGLE_LIMIT_DEG + 5.0


# ============================================================================
# COMMA INPUT STATE
# ============================================================================

class CommaInput:
    """Live state from the comma forwarder. UI thread reads this."""

    def __init__(self):
        self.lock = threading.Lock()
        self.connected = False
        self.angle_deg = 0.0
        self.lat_active = False
        self.op_enabled = False
        self.cc_alive = False
        self.cc_valid = False
        self.vego = 0.0
        self.seq = -1
        self.frame_count = 0
        self.last_frame_monotonic = 0.0
        # Default ON for this bridge: engagement follows openpilot, which
        # is what the cruise-stalk pull drives on the comma.
        self.follow_engage = True


class CommaLinkReader(threading.Thread):
    """Owns the TCP connection to comma_steer_forward.py. Reads
    newline-delimited JSON, updates CommaInput, and calls
    CommaApp.apply_comma_input on every valid message."""

    def __init__(self, host: str, port: int,
                 app: "CommaApp", ci: CommaInput, invert: bool):
        super().__init__(daemon=True, name="CommaLinkReader")
        self.host = host
        self.port = port
        self.app = app
        self.ci = ci
        self.invert = invert
        self._stop = threading.Event()
        self._buf = bytearray()

    def stop(self):
        self._stop.set()

    def _log(self, msg: str):
        self.app.comma_log(msg)

    def _handle_line(self, line: bytes):
        try:
            m = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            return  # drop malformed; next good frame arrives in ~10 ms
        try:
            angle = float(m["angle_deg"])
            lat_active = bool(m.get("lat_active", False))
            op_enabled = bool(m.get("enabled", False))
            alive = bool(m.get("alive", False))
            valid = bool(m.get("valid", False))
            vego = float(m.get("vego", 0.0))
            seq = int(m.get("seq", -1))
        except (KeyError, TypeError, ValueError):
            return
        if angle != angle or abs(angle) > COMMA_MAX_ABS_ANGLE_DEG:  # NaN/garbage
            return
        if self.invert:
            angle = -angle

        now = time.monotonic()
        with self.ci.lock:
            self.ci.angle_deg = angle
            self.ci.lat_active = lat_active
            self.ci.op_enabled = op_enabled
            self.ci.cc_alive = alive
            self.ci.cc_valid = valid
            self.ci.vego = vego
            self.ci.seq = seq
            self.ci.frame_count += 1
            self.ci.last_frame_monotonic = now

        self.app.apply_comma_input(angle, lat_active, alive and valid)

    def _consume(self, chunk: bytes):
        self._buf.extend(chunk)
        while True:
            nl = self._buf.find(b"\n")
            if nl < 0:
                if len(self._buf) > 4096:        # runaway line -> resync
                    self._buf.clear()
                break
            line = bytes(self._buf[:nl])
            del self._buf[:nl + 1]
            if line:
                self._handle_line(line)

    def run(self):
        while not self._stop.is_set():
            try:
                sock = socket.create_connection((self.host, self.port),
                                                timeout=3.0)
            except OSError as e:
                self._log(f"connect to {self.host}:{self.port} failed: {e}")
                if self._stop.wait(COMMA_RECONNECT_S):
                    return
                continue

            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(0.5)
            self._buf.clear()
            with self.ci.lock:
                self.ci.connected = True
            self._log(f"link up: {self.host}:{self.port}")

            try:
                while not self._stop.is_set():
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        continue
                    except OSError as e:
                        self._log(f"link read error: {e}")
                        break
                    if not chunk:
                        self._log("link closed by comma")
                        break
                    self._consume(chunk)
            finally:
                try:
                    sock.close()
                except OSError:
                    pass
                with self.ci.lock:
                    self.ci.connected = False
                self._log("link down")
                if not self._stop.is_set():
                    self._stop.wait(COMMA_RECONNECT_S)


# ============================================================================
# APP -- subclass v4.3.3 App, add comma input mode
# ============================================================================

class CommaApp(base.App):
    """Subclasses tesla_control.App. Adds a COMMA INPUT panel and a TCP
    reader; everything else is unchanged."""

    def __init__(self, comma_host: str, comma_port: int, invert: bool):
        self.ci = CommaInput()
        self.comma_host = comma_host
        self.comma_port = comma_port
        self.comma_invert = invert
        self.comma_reader: Optional[CommaLinkReader] = None
        self.comma_widgets: dict = {}
        super().__init__()
        self.title(f"Tesla Rack Control COMMA  v{__version__}  "
                   f"(core v{base.__version__})  --  {comma_host}:{comma_port}")
        self._build_comma_panel()
        self.comma_reader = CommaLinkReader(
            comma_host, comma_port, self, self.ci, invert)
        self.comma_reader.start()

    # ---------- input plumbing ----------

    def comma_log(self, msg: str):
        self.log_q.put(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if self.logger:
            self.logger.event(f"comma: {msg}")

    def apply_comma_input(self, angle_deg: float, lat_active: bool,
                          link_ok: bool):
        """Called from the reader thread on every valid message. Writes
        the target angle ONLY while openpilot is actively steering and
        the link is healthy; the existing worker rate-limits, LPFs,
        clamps and transmits it. Engagement transitions are handled on
        the UI thread in _refresh_comma_ui (Tk-safe)."""
        if self.ctrl.estop:
            return
        if lat_active and link_ok:
            self.ctrl.target_angle_deg = max(
                -base.HARD_ANGLE_LIMIT_DEG,
                min(base.HARD_ANGLE_LIMIT_DEG, angle_deg))

    # ---------- UI ----------

    def _build_comma_panel(self):
        frm = tk.Frame(self, bg=self.PANEL, bd=1, relief="solid",
                       highlightbackground=self.BORDER,
                       highlightthickness=1)
        frm.pack(fill="x", padx=8, pady=(0, 8))

        tk.Label(frm, text="COMMA INPUT (openpilot)", bg=self.PANEL,
                 fg=self.DIM, font=self.f_section, anchor="w"
                 ).pack(fill="x", padx=8, pady=(6, 2))

        row = tk.Frame(frm, bg=self.PANEL)
        row.pack(fill="x", padx=8, pady=(0, 8))

        def cell(parent, label):
            wrap = tk.Frame(parent, bg=self.PANEL2, bd=0)
            wrap.pack(side="left", padx=(0, 8), fill="y")
            tk.Label(wrap, text=label, bg=self.PANEL2, fg=self.DIM,
                     font=self.f_label).pack(anchor="w", padx=6, pady=(4, 0))
            val = tk.Label(wrap, text="--", bg=self.PANEL2, fg=self.FG,
                           font=self.f_mid, width=11, anchor="w")
            val.pack(anchor="w", padx=6, pady=(0, 4))
            return val

        self.comma_widgets["link"]   = cell(row, "LINK")
        self.comma_widgets["op"]     = cell(row, "OP STEER")
        self.comma_widgets["angle"]  = cell(row, "ANGLE deg")
        self.comma_widgets["rate"]   = cell(row, "MSG/s")
        self.comma_widgets["vego"]   = cell(row, "OP vEgo")
        self.comma_widgets["engsrc"] = cell(row, "ENGAGE SRC")

        chk_var = tk.BooleanVar(value=True)
        chk = tk.Checkbutton(
            row, text="follow openpilot engage (latActive)",
            variable=chk_var,
            bg=self.PANEL, fg=self.DIM, selectcolor=self.PANEL2,
            activebackground=self.PANEL, activeforeground=self.FG,
            font=self.f_help, bd=0, highlightthickness=0,
            command=lambda: self._set_follow(bool(chk_var.get())),
        )
        chk.pack(side="left", padx=(8, 0))
        self.comma_widgets["_follow_var"] = chk_var

        # rate calc state
        self._comma_rate_last_n = 0
        self._comma_rate_last_t = time.monotonic()
        self._comma_rate_hz = 0.0

    def _set_follow(self, val: bool):
        with self.ci.lock:
            self.ci.follow_engage = val
        self.comma_log(f"follow openpilot engage = {val}")

    def _refresh_comma_ui(self):
        w = self.comma_widgets
        if not w:
            return
        now = time.monotonic()
        with self.ci.lock:
            connected = self.ci.connected
            angle = self.ci.angle_deg
            lat_active = self.ci.lat_active
            cc_alive = self.ci.cc_alive
            cc_valid = self.ci.cc_valid
            vego = self.ci.vego
            frames = self.ci.frame_count
            last_frame = self.ci.last_frame_monotonic
            follow = self.ci.follow_engage

        age_ms = ((now - last_frame) * 1000.0
                  if last_frame > 0 else float("inf"))
        link_ok = connected and age_ms <= COMMA_LINK_TIMEOUT_MS
        op_steering = link_ok and lat_active and cc_alive and cc_valid

        # message rate (over ~1 s windows)
        if now - self._comma_rate_last_t >= 1.0:
            self._comma_rate_hz = ((frames - self._comma_rate_last_n)
                                   / (now - self._comma_rate_last_t))
            self._comma_rate_last_n = frames
            self._comma_rate_last_t = now

        # ---- engagement management (UI thread, Tk-safe) ----
        # Link loss always disengages.
        if self.ctrl.engaged and not link_ok and self.worker is not None:
            self.comma_log("AUTO-DISENGAGE: comma link lost")
            self.ctrl.engaged = False
        elif follow and self.worker is not None and not self.ctrl.estop:
            if op_steering and not self.ctrl.engaged:
                # Engage through the guarded path (park-to-engage gate,
                # logging) -- mirrors pressing ENGAGE.
                self.toggle_engage()
            elif self.ctrl.engaged and not op_steering:
                self.comma_log("AUTO-DISENGAGE: openpilot no longer steering")
                self.ctrl.engaged = False

        # ---- widgets ----
        w["link"].config(
            text=("UP" if link_ok else ("STALE" if connected else "DOWN")),
            fg=(self.GREEN if link_ok else self.RED))
        w["op"].config(
            text=("STEERING" if op_steering else "idle"),
            fg=(self.GREEN if op_steering else self.DIM))
        w["angle"].config(text=f"{angle:+.1f}")
        w["rate"].config(text=f"{self._comma_rate_hz:.0f}")
        w["vego"].config(text=f"{vego:.1f}")
        w["engsrc"].config(
            text=("openpilot" if follow else "manual"),
            fg=(self.ORANGE if follow else self.DIM))

    def _tick(self):
        super()._tick()
        self._refresh_comma_ui()

    def on_close(self):
        if self.comma_reader:
            self.comma_reader.stop()
        super().on_close()


# ============================================================================
# Entry point
# ============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Tesla Rack Control -- steering from a comma 3X "
                    "running openpilot")
    p.add_argument("--comma-host", required=True,
                   help="IP of the comma 3X running comma_steer_forward.py")
    p.add_argument("--comma-port", type=int, default=COMMA_DEFAULT_PORT,
                   help=f"TCP port (default {COMMA_DEFAULT_PORT})")
    p.add_argument("--invert", action="store_true",
                   help="negate the angle (use ONLY if the bench sign "
                        "check shows the wheel turns the wrong way)")
    return p.parse_args()


def banner_comma(host: str, port: int, invert: bool):
    print("=" * 72)
    print(f" Tesla Rack Control COMMA v{__version__}  "
          f"(core v{base.__version__})")
    print(f" comma 3X openpilot -> {host}:{port} -> CAN 0x488")
    print("=" * 72)
    print(f" comma host:port          : {host}:{port}")
    print(f" link timeout             : {COMMA_LINK_TIMEOUT_MS} ms -> disengage")
    print(f" angle invert             : {invert}")
    print(f" engage source            : openpilot latActive (default) "
          f"/ manual via checkbox")
    print(" SIGN UNVERIFIED: confirm wheel direction at small angles "
          "before trusting.")
    print("=" * 72)
    base.banner()


if __name__ == "__main__":
    args = parse_args()
    banner_comma(args.comma_host, args.comma_port, args.invert)
    try:
        CommaApp(args.comma_host, args.comma_port, args.invert).mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
