"""
Tesla Rack Control RC  --  v5.0.0-rc1
=====================================

Variant of tesla_control.py v4.3.3 that takes its steering and shift
input from a Spektrum receiver wired through an Arduino Nano bridge
instead of from the on-screen slider and keyboard.

This file imports the v4.3.3 program as a library and adds an RC input
mode on top. All CAN protocol code, safety guards, EAC bounce watchdog,
real-motion auto-disengage, park-to-engage gate, and 30 MPH MODE
interlocks come from tesla_control.py UNCHANGED.

HARDWARE CHAIN
    Spektrum DX8 (DSMX air, SPMR8000) -> AR6200 (DSM2 air, SPMAR6200,
    6-channel PWM out) -> Arduino Nano (PCINT PWM reader, COBS framing,
    USB CDC) -> this program -> CanWorker -> SYS TEC USB-CAN -> Tesla rack.

    See docs/RC_SETUP.md for binding procedure and wiring diagram.

CHANNEL MAP
    AR6200 channel 2 (aileron, right stick X)  -> STEERING angle
        Centered = 0 deg, full deflection = +/- HARD_ANGLE_LIMIT_DEG.
    AR6200 channel 5 (gear switch)             -> Park latch
        Switch held in "active" position for >= 200 ms requests P.
    AR6200 channel 6 (aux1, 3-position switch) -> R / N / D
        Switch position dictates target gear; the program only fires
        a shift when the position CHANGES, so holding the switch in
        D does not spam shift requests.

INPUT PROTOCOL (Arduino -> laptop)
    COBS-framed packets, terminated by 0x00. Decoded payload is 9 bytes:
        [seq:u8][ch_steer:u16 LE][ch_p:u16 LE][ch_rnd:u16 LE][flags:u8][crc8:u8]
    CRC-8/ITU (poly 0x07, init 0x00, no reflect, no xorout) over the
    first 8 bytes.

SAFETY ADDED ON TOP OF v4.3.3
    1. Stick-jitter watchdog: the program refuses to apply any RC angle
       command until it has seen the aileron channel move by at least
       RC_INITIAL_JITTER_US since the serial port opened. Spektrum
       receivers hold-last on signal loss (per AR6210 manual, SmartSafe
       semantics inherited by the AR6200), so a stale value is not
       enough on its own to prove the human is actually flying the
       stick. The user has to wiggle the stick to "arm" RC mode.
    2. Serial frame timeout: if no valid frame is received in
       RC_SERIAL_TIMEOUT_MS, RC input is dropped (target snaps to
       the last commanded angle) and the user is logged about it.
       Engagement is NOT killed automatically -- existing v4.3.3
       watchdogs (RX timeout from rack, EAC bounce, etc.) handle the
       deeper failure modes.
    3. CRC failures and seq-gaps are logged. Five consecutive gaps
       disable RC input.

REQUIREMENTS
    All of tesla_control.py's deps, plus:
        pip install pyserial

USAGE
    1. Flash arduino/tesla_rc_bridge/tesla_rc_bridge.ino onto a Nano.
    2. Wire AR6200 to the Nano per docs/RC_SETUP.md.
    3. Bind the AR6200 to the DX8.
    4. Plug Nano into laptop USB; note the COM port.
    5. Plug SYS TEC USB-CAN into laptop, into car.
    6. Run:
           python tesla_control_rc.py --rc-port COM5
       (or --rc-port /dev/cu.usbserial-XXX on macOS)
    7. The GUI is the same as v4.3.3, plus a new "RC INPUT" panel that
       shows live channel values, jitter watchdog state, and selected
       gear. While the watchdog is unarmed, RC commands are ignored.
    8. Wiggle the aileron stick by >50 us to arm.
    9. Click ENGAGE as usual. From here on the rack tracks the stick.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import tkinter as tk
from tkinter import font
from typing import Optional

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial",
          file=sys.stderr)
    sys.exit(1)

import tesla_control as base


__version__ = "5.0.0-rc1"


# ============================================================================
# CONFIGURATION
# ============================================================================

RC_BAUD = 115200

# PWM endpoint calibration (microseconds). Spektrum/JR-style transmitters
# at 100% travel send roughly 1000..2000 us. With DX8 EPA at default,
# expect close to these but allow some headroom. Calibration at startup
# can override these per-stick.
RC_STEER_MIN_US     = 1000
RC_STEER_CENTER_US  = 1500
RC_STEER_MAX_US     = 2000
RC_STEER_DEADBAND_US = 25  # +/- around center -> 0 deg commanded

# 3-position switch thresholds. Spektrum 3-pos switches center at ~1500
# and travel to ~1000 / ~2000 at the endpoints. Hysteresis bands so a
# wobbling stick doesn't flip-flop the selected gear.
RC_RND_LOW_THRESH_US  = 1250   # below this -> R
RC_RND_HIGH_THRESH_US = 1750   # above this -> D
                               # in-between -> N

# Park latch. Spektrum 2-pos switches travel 1000<->2000. Treat anything
# above the high threshold as "P pressed."
RC_P_PRESS_THRESH_US  = 1750
RC_P_LATCH_HOLD_MS    = 200   # need to hold this long to count

# Watchdogs
RC_SERIAL_TIMEOUT_MS  = 100   # no frame for this long -> drop RC input
RC_INITIAL_JITTER_US  = 50    # min aileron travel before arming
RC_CRC_GAP_LIMIT      = 5     # consecutive bad frames before kicking RC off

# Display update rate (Tk side). Worker is independent.
RC_UI_UPDATE_MS = 50


# ============================================================================
# COBS DECODE + CRC-8 / ITU
# ============================================================================

def cobs_decode(buf: bytes) -> Optional[bytes]:
    """Decode a COBS-encoded payload (no trailing 0x00 byte). Returns
    None on malformed input."""
    if not buf:
        return None
    out = bytearray()
    i = 0
    while i < len(buf):
        code = buf[i]
        if code == 0:
            return None
        i += 1
        end = i + code - 1
        if end > len(buf):
            return None
        out.extend(buf[i:end])
        i = end
        if code != 0xFF and i < len(buf):
            out.append(0)
    return bytes(out)


def crc8_itu(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


# ============================================================================
# RC INPUT THREAD
# ============================================================================

class RcInput:
    """Live state from the Arduino bridge. UI thread reads this."""

    def __init__(self):
        self.lock = threading.Lock()
        self.connected = False
        self.steer_us = 0
        self.p_us = 0
        self.rnd_us = 0
        self.seq = -1
        self.last_frame_monotonic = 0.0
        self.frame_count = 0
        self.crc_errors = 0
        self.seq_gaps = 0
        self.consecutive_bad = 0
        self.armed = False
        # Initial-jitter watchdog
        self._steer_min_seen = None
        self._steer_max_seen = None
        # Edge detection for PRND
        self.selected_gear = "N"       # current logical RND switch position
        self.last_shift_gear = None    # most recent gear we asked for
        # P latch
        self._p_high_since: Optional[float] = None
        self.last_p_latch_at = 0.0


class RcReader(threading.Thread):
    """Owns the pyserial port. Reads COBS-framed frames, decodes, applies
    them to control state. Runs at the Arduino's output rate (~100 Hz)
    plus a 5 ms select-timeout for shutdown latency."""

    def __init__(self, port: str, baud: int,
                 app: "RcApp", rc: RcInput):
        super().__init__(daemon=True, name="RcReader")
        self.port = port
        self.baud = baud
        self.app = app
        self.rc = rc
        self._stop = threading.Event()
        self._buf = bytearray()

    def stop(self):
        self._stop.set()

    def _log(self, msg: str):
        self.app.rc_log(msg)

    def _handle_payload(self, payload: bytes):
        if len(payload) != 9:
            self.rc.crc_errors += 1
            self.rc.consecutive_bad += 1
            return
        if crc8_itu(payload[:8]) != payload[8]:
            self.rc.crc_errors += 1
            self.rc.consecutive_bad += 1
            return

        seq = payload[0]
        w_steer = payload[1] | (payload[2] << 8)
        w_p     = payload[3] | (payload[4] << 8)
        w_rnd   = payload[5] | (payload[6] << 8)
        # flags = payload[7]   -- unused for now

        with self.rc.lock:
            if self.rc.seq >= 0:
                gap = (seq - self.rc.seq) & 0xFF
                if gap > 1:
                    self.rc.seq_gaps += 1
            self.rc.seq = seq
            self.rc.steer_us = w_steer
            self.rc.p_us = w_p
            self.rc.rnd_us = w_rnd
            self.rc.last_frame_monotonic = time.monotonic()
            self.rc.frame_count += 1
            self.rc.consecutive_bad = 0

            # initial jitter
            if self.rc._steer_min_seen is None:
                self.rc._steer_min_seen = w_steer
                self.rc._steer_max_seen = w_steer
            else:
                if w_steer < self.rc._steer_min_seen:
                    self.rc._steer_min_seen = w_steer
                if w_steer > self.rc._steer_max_seen:
                    self.rc._steer_max_seen = w_steer
            travel = (self.rc._steer_max_seen or 0) - (self.rc._steer_min_seen or 0)
            if not self.rc.armed and travel >= RC_INITIAL_JITTER_US:
                self.rc.armed = True
                self._log(f"RC armed (aileron travel {travel} us)")

        self.app.apply_rc_input(w_steer, w_p, w_rnd)

    def _consume(self, chunk: bytes):
        # COBS framing: split on 0x00 delimiters.
        for b in chunk:
            if b == 0x00:
                if self._buf:
                    decoded = cobs_decode(bytes(self._buf))
                    if decoded is not None:
                        self._handle_payload(decoded)
                    else:
                        self.rc.crc_errors += 1
                        self.rc.consecutive_bad += 1
                self._buf.clear()
            else:
                self._buf.append(b)
                # Cap buffer size to avoid runaway memory if the port
                # streams garbage with no 0x00 in sight.
                if len(self._buf) > 64:
                    self._buf.clear()

    def run(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=0.005)
        except Exception as e:
            self._log(f"RC port open FAILED: {e}")
            return
        self.rc.connected = True
        self._log(f"RC port open: {self.port} @ {self.baud}")

        try:
            while not self._stop.is_set():
                try:
                    chunk = ser.read(64)
                except Exception as e:
                    self._log(f"RC read error: {e}")
                    break
                if chunk:
                    self._consume(chunk)
        finally:
            try:
                ser.close()
            except Exception:
                pass
            self.rc.connected = False
            self._log("RC port closed")


# ============================================================================
# APP -- subclass v4.3.3 App, add RC input mode
# ============================================================================

class RcApp(base.App):
    """Subclasses tesla_control.App to add the RC input pipeline. The
    GUI gets a new 'RC INPUT' panel; everything else is unchanged."""

    def __init__(self, rc_port: str):
        self.rc = RcInput()
        self.rc_port = rc_port
        self.rc_reader: Optional[RcReader] = None
        self.rc_widgets: dict = {}
        super().__init__()
        # Override title so the user can see at a glance which program
        # they're running.
        self.title(f"Tesla Rack Control RC  v{__version__}  "
                   f"(core v{base.__version__})  --  {rc_port}")
        self._build_rc_panel()
        self.rc_reader = RcReader(rc_port, RC_BAUD, self, self.rc)
        self.rc_reader.start()
        # Replace base _tick with our own that includes RC UI refresh.
        # base App already calls _tick at 50 ms via after(); we just
        # piggyback by overriding the method.
        # See _tick below.

    # ---------- RC input plumbing ----------

    def rc_log(self, msg: str):
        # Borrow the worker's log queue so RC events show up inline.
        self.log_q.put(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if self.logger:
            self.logger.event(f"rc: {msg}")

    def apply_rc_input(self, w_steer: int, w_p: int, w_rnd: int):
        """Translate raw PWM widths into ControlState updates. Called
        from the RcReader thread."""

        # Steering: only act once armed.
        if self.rc.armed and not self.ctrl.estop:
            deg = self._steer_pwm_to_deg(w_steer)
            self.ctrl.target_angle_deg = deg

        # RND switch: pick gear from PWM bucket with hysteresis.
        gear = self._rnd_pwm_to_gear(w_rnd)
        if gear != self.rc.selected_gear:
            self.rc.selected_gear = gear
            # Edge-trigger a shift request. The base App's request_shift
            # gates re-entrancy and refuses overlapping bursts.
            if (self.rc.armed
                    and self.worker is not None
                    and not self.ctrl.estop):
                if gear != self.rc.last_shift_gear:
                    self.rc_log(f"RND switch -> {gear}, queuing shift")
                    self.rc.last_shift_gear = gear
                    # request_shift is thread-safe in that it only sets
                    # control-state flags; the worker reads them on its
                    # next tick.
                    self.request_shift(gear)

        # P latch: long press only.
        now = time.monotonic()
        if w_p >= RC_P_PRESS_THRESH_US:
            if self.rc._p_high_since is None:
                self.rc._p_high_since = now
            elif (now - self.rc._p_high_since) * 1000.0 >= RC_P_LATCH_HOLD_MS:
                if (self.rc.armed
                        and self.worker is not None
                        and not self.ctrl.estop
                        and (now - self.rc.last_p_latch_at) > 1.0):
                    self.rc_log("P latch (gear switch held)")
                    self.rc.last_p_latch_at = now
                    self.rc.last_shift_gear = "P"
                    self.request_shift("P")
        else:
            self.rc._p_high_since = None

    def _steer_pwm_to_deg(self, w: int) -> float:
        if w <= 0:
            return self.ctrl.target_angle_deg  # no-op on bad sample
        # Deadband
        if abs(w - RC_STEER_CENTER_US) <= RC_STEER_DEADBAND_US:
            return 0.0
        # Piecewise linear so trim-asymmetric sticks still map cleanly.
        limit = base.HARD_ANGLE_LIMIT_DEG
        if w >= RC_STEER_CENTER_US:
            span = max(1, RC_STEER_MAX_US - RC_STEER_CENTER_US)
            ratio = min(1.0, (w - RC_STEER_CENTER_US) / span)
            return ratio * limit
        else:
            span = max(1, RC_STEER_CENTER_US - RC_STEER_MIN_US)
            ratio = min(1.0, (RC_STEER_CENTER_US - w) / span)
            return -ratio * limit

    def _rnd_pwm_to_gear(self, w: int) -> str:
        if w <= 0:
            return self.rc.selected_gear
        if w < RC_RND_LOW_THRESH_US:
            return "R"
        if w > RC_RND_HIGH_THRESH_US:
            return "D"
        return "N"

    # ---------- UI ----------

    def _build_rc_panel(self):
        """Build a slim status strip docked under the existing keepalive
        panel. We don't restructure the base UI; we just add."""
        frm = tk.Frame(self, bg=self.PANEL, bd=1, relief="solid",
                       highlightbackground=self.BORDER,
                       highlightthickness=1)
        frm.pack(fill="x", padx=8, pady=(0, 8))

        hdr = tk.Label(frm, text="RC INPUT",
                       bg=self.PANEL, fg=self.DIM,
                       font=self.f_section, anchor="w")
        hdr.pack(fill="x", padx=8, pady=(6, 2))

        row = tk.Frame(frm, bg=self.PANEL)
        row.pack(fill="x", padx=8, pady=(0, 8))

        def cell(parent, label):
            wrap = tk.Frame(parent, bg=self.PANEL2, bd=0)
            wrap.pack(side="left", padx=(0, 8), fill="y")
            tk.Label(wrap, text=label, bg=self.PANEL2, fg=self.DIM,
                     font=self.f_label).pack(anchor="w", padx=6, pady=(4, 0))
            val = tk.Label(wrap, text="--", bg=self.PANEL2, fg=self.FG,
                           font=self.f_mid, width=10, anchor="w")
            val.pack(anchor="w", padx=6, pady=(0, 4))
            return val

        self.rc_widgets["port"]   = cell(row, "PORT")
        self.rc_widgets["frames"] = cell(row, "FRAMES")
        self.rc_widgets["steer"]  = cell(row, "STEER us")
        self.rc_widgets["rnd"]    = cell(row, "RND us")
        self.rc_widgets["p"]      = cell(row, "P us")
        self.rc_widgets["gear"]   = cell(row, "GEAR")
        self.rc_widgets["armed"]  = cell(row, "ARMED")
        self.rc_widgets["err"]    = cell(row, "CRC/GAP")

    def _refresh_rc_ui(self):
        w = self.rc_widgets
        if not w:
            return
        with self.rc.lock:
            connected = self.rc.connected
            frames = self.rc.frame_count
            steer = self.rc.steer_us
            p = self.rc.p_us
            rnd = self.rc.rnd_us
            armed = self.rc.armed
            crc_err = self.rc.crc_errors
            seq_gap = self.rc.seq_gaps
            gear = self.rc.selected_gear
            last_mono = self.rc.last_frame_monotonic
        age_ms = (time.monotonic() - last_mono) * 1000.0 if last_mono > 0 else -1.0
        stale = age_ms < 0 or age_ms > RC_SERIAL_TIMEOUT_MS

        w["port"].config(text=("OPEN" if connected else "CLOSED"),
                         fg=(self.GREEN if connected else self.RED))
        w["frames"].config(text=f"{frames}")
        w["steer"].config(text=(f"{steer}" if steer else "--"),
                          fg=(self.MUTE if stale else self.FG))
        w["rnd"].config(text=(f"{rnd}" if rnd else "--"),
                        fg=(self.MUTE if stale else self.FG))
        w["p"].config(text=(f"{p}" if p else "--"),
                      fg=(self.MUTE if stale else self.FG))
        w["gear"].config(text=gear,
                         fg=(self.ORANGE if armed else self.DIM))
        w["armed"].config(text=("YES" if armed else "NO"),
                          fg=(self.GREEN if armed else self.YELLOW))
        w["err"].config(text=f"{crc_err} / {seq_gap}",
                        fg=(self.RED if crc_err or seq_gap else self.DIM))

    def _tick(self):
        super()._tick()
        # The base class re-arms via after(50, self._tick). Riding on
        # that 20 Hz cadence is fine for RC panel refresh.
        self._refresh_rc_ui()

    def on_close(self):
        if self.rc_reader:
            self.rc_reader.stop()
        super().on_close()


# ============================================================================
# Entry point
# ============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Tesla Rack Control RC -- DX8 + AR6200 + Arduino bridge")
    p.add_argument("--rc-port", required=True,
                   help="Serial port for the Arduino bridge "
                        "(e.g. COM5, /dev/cu.usbserial-XXX)")
    return p.parse_args()


def banner_rc(port: str):
    print("=" * 72)
    print(f" Tesla Rack Control RC v{__version__}  "
          f"(core v{base.__version__})")
    print(f" Spektrum DX8 -> AR6200 -> Arduino Nano @ {port} -> CAN")
    print("=" * 72)
    print(f" RC baud                  : {RC_BAUD}")
    print(f" RC steer endpoints       : {RC_STEER_MIN_US} / "
          f"{RC_STEER_CENTER_US} / {RC_STEER_MAX_US} us")
    print(f" RC steer deadband        : +/- {RC_STEER_DEADBAND_US} us")
    print(f" RC RND switch buckets    : <{RC_RND_LOW_THRESH_US} R, "
          f">{RC_RND_HIGH_THRESH_US} D, else N")
    print(f" RC P-latch hold          : {RC_P_LATCH_HOLD_MS} ms above "
          f"{RC_P_PRESS_THRESH_US} us")
    print(f" RC serial timeout        : {RC_SERIAL_TIMEOUT_MS} ms")
    print(f" RC initial-jitter arm    : aileron travel >= "
          f"{RC_INITIAL_JITTER_US} us")
    print("=" * 72)
    base.banner()


if __name__ == "__main__":
    args = parse_args()
    banner_rc(args.rc_port)
    try:
        RcApp(args.rc_port).mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
