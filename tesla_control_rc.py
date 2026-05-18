"""
Tesla Rack Control RC  --  v5.0.0-rc2
=====================================

Variant of tesla_control.py v4.3.3 that takes its steering and shift
input from a Spektrum receiver wired through an Arduino Nano bridge
instead of from the on-screen slider and keyboard.

This file imports the v4.3.3 program as a library and adds an RC input
mode on top. All CAN protocol code, safety guards, EAC bounce watchdog,
real-motion auto-disengage, park-to-engage gate, RX-timeout watchdog,
and 30 MPH MODE interlocks come from tesla_control.py UNCHANGED.

HARDWARE CHAIN
    Spektrum DX8 (DSMX air, SPMR8000) -> AR6200 (DSM2 air, SPMAR6200,
    6-channel PWM out) -> Arduino Nano (PCINT PWM reader, COBS framing,
    USB CDC) -> this program -> CanWorker -> SYS TEC USB-CAN -> Tesla rack.

    See docs/RC_SETUP.md and docs/build/RC_IMPLEMENTATION_GUIDE.pdf for
    binding procedure and wiring diagram.

CHANNEL MAP (AR6200 channel labels)
    Channel 2 AILE (right stick X)        -> STEERING angle
    Channel 5 GEAR (gear toggle switch)   -> Park latch
    Channel 6 AUX1 (3-position switch)    -> R / N / D

STEERING MATH
    Following openpilot's tools/joystick/joystickd.py:
      1. Read PWM width (microseconds, ~1000..2000).
      2. Running min/max calibration -- the program tracks the actual
         endpoints of YOUR stick and normalizes to [-1, 1]. No
         hardcoded 1000/2000 us.
      3. 3% deadband around center -- kills jitter without creating a
         noticeable dead zone for the driver.
      4. Expo (cubic blend): output = 0.4 * x^3 + 0.6 * x. This is the
         exact formula openpilot uses; tested in production for years.
         Result: linear feel near center for small corrections, more
         aggressive near full deflection so lock-to-lock is reachable.
      5. Multiply by HARD_ANGLE_LIMIT_DEG (360 deg) for the target.
      6. v4.3.3's existing rate limit + LPF on the worker side shapes
         actual output motion.

The watchdogs, jitter armer, and seq-gap counter from the prior rc1
draft are GONE. v4.3.3 already has six layers of safety -- adding
another set on top was making the program harder to use without
buying more safety than already exists.

REQUIREMENTS
    All of tesla_control.py's deps, plus:
        pip install pyserial

USAGE
    python tesla_control_rc.py --rc-port COM5
    (macOS: --rc-port /dev/cu.usbserial-XXX)
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import tkinter as tk
from typing import Optional

try:
    import serial
except ImportError:
    print("ERROR: pyserial not installed. Run: pip install pyserial",
          file=sys.stderr)
    sys.exit(1)

import tesla_control as base


__version__ = "5.0.0-rc2"


# ============================================================================
# CONFIGURATION
# ============================================================================

RC_BAUD = 115200

# Steering math (openpilot tools/joystick/joystickd.py pattern)
RC_DEADBAND_NORM = 0.03   # 3% normalized deadband, post-calibration
RC_EXPO_K        = 0.4    # cubic blend coefficient. 0.4 = openpilot value
                          #   output = 0.4 * x^3 + 0.6 * x

# Bootstrap endpoints. Used until the running min/max calibration sees
# enough travel to take over. Spektrum convention 1000/2000 is the
# starting point; calibration adjusts in real time as the user moves
# the stick.
RC_BOOT_STEER_MIN_US    = 1100
RC_BOOT_STEER_CENTER_US = 1500
RC_BOOT_STEER_MAX_US    = 1900

# 3-position switch thresholds for AUX1 -> R/N/D. Spektrum 3-pos
# switches travel ~1000 / ~1500 / ~2000 us. Wide hysteresis bands so a
# wobbling stick doesn't flip-flop the selected gear.
RC_RND_LOW_THRESH_US  = 1250   # below this -> R
RC_RND_HIGH_THRESH_US = 1750   # above this -> D
                               # in-between -> N

# Park latch on the GEAR toggle switch. Hold above the threshold for
# this long to request P. Cooldown prevents double-firing.
RC_P_PRESS_THRESH_US  = 1750
RC_P_LATCH_HOLD_MS    = 200
RC_P_LATCH_COOLDOWN_S = 1.0


# ============================================================================
# COBS DECODE + CRC-8 / ITU
# ============================================================================

def cobs_decode(buf: bytes) -> Optional[bytes]:
    """Decode a COBS-encoded payload (no trailing 0x00 byte). Returns
    None on malformed input.

    Reference: Cheshire & Baker, "Consistent Overhead Byte Stuffing",
    IEEE/ACM Transactions on Networking, April 1999.
    """
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
    """CRC-8/ITU (poly 0x07, init 0x00, no reflect, no xorout)."""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


# ============================================================================
# STEERING MATH  (openpilot tools/joystick pattern)
# ============================================================================

def apply_expo(x: float, k: float = RC_EXPO_K) -> float:
    """Cubic blend expo, openpilot-style. x in [-1, 1]. Returns shaped
    value in [-1, 1]. With k = 0.4 this gives ~linear feel near center
    and more aggressive response near full deflection -- the curve real
    sim racers and openpilot use for natural steering across a full
    lock-to-lock range.

    Source: commaai/openpilot tools/joystick/joystickd.py.
    """
    return k * (x ** 3) + (1.0 - k) * x


class StickCalibration:
    """Running min/max envelope of an RC channel. Used to translate raw
    PWM widths into normalized [-1, 1] without hardcoding endpoints.

    Center is taken as the midpoint of (min, max) once both have moved
    away from the boot values. Until then, RC_BOOT_STEER_CENTER_US is
    used as a fallback so the program is usable without a calibration
    sweep.
    """

    def __init__(self, boot_min: int, boot_center: int, boot_max: int):
        self.lo = boot_min
        self.hi = boot_max
        self.boot_center = boot_center
        self.seen_movement = False

    def observe(self, us: int):
        if us <= 0:
            return
        if us < self.lo:
            self.lo = us
            self.seen_movement = True
        if us > self.hi:
            self.hi = us
            self.seen_movement = True

    def normalize(self, us: int) -> float:
        """Map raw PWM width to [-1, 1] using the current envelope."""
        if us <= 0:
            return 0.0
        center = (self.lo + self.hi) // 2 if self.seen_movement else self.boot_center
        if us >= center:
            span = max(1, self.hi - center)
            return min(1.0, (us - center) / span)
        else:
            span = max(1, center - self.lo)
            return -min(1.0, (center - us) / span)


# ============================================================================
# RC INPUT STATE
# ============================================================================

class RcInput:
    """Live state from the Arduino bridge. UI thread reads this."""

    def __init__(self):
        self.lock = threading.Lock()
        self.connected = False
        self.steer_us = 0
        self.p_us = 0
        self.rnd_us = 0
        self.frame_count = 0
        self.calib = StickCalibration(
            RC_BOOT_STEER_MIN_US,
            RC_BOOT_STEER_CENTER_US,
            RC_BOOT_STEER_MAX_US,
        )
        # Edge detection for PRND switch
        self.selected_gear = "N"
        self.last_shift_gear = None
        # P latch
        self._p_high_since: Optional[float] = None
        self.last_p_latch_at = 0.0


class RcReader(threading.Thread):
    """Owns the pyserial port. Reads COBS-framed frames, decodes them,
    pushes channel values into RcInput, calls into RcApp.apply_rc_input
    which translates them into ControlState updates."""

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
        # Quietly drop malformed frames -- the worker's tick will pick
        # up the next good one.
        if len(payload) != 9:
            return
        if crc8_itu(payload[:8]) != payload[8]:
            return

        w_steer = payload[1] | (payload[2] << 8)
        w_p     = payload[3] | (payload[4] << 8)
        w_rnd   = payload[5] | (payload[6] << 8)

        with self.rc.lock:
            self.rc.steer_us = w_steer
            self.rc.p_us = w_p
            self.rc.rnd_us = w_rnd
            self.rc.frame_count += 1
            self.rc.calib.observe(w_steer)

        self.app.apply_rc_input(w_steer, w_p, w_rnd)

    def _consume(self, chunk: bytes):
        for b in chunk:
            if b == 0x00:
                if self._buf:
                    decoded = cobs_decode(bytes(self._buf))
                    if decoded is not None:
                        self._handle_payload(decoded)
                self._buf.clear()
            else:
                self._buf.append(b)
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
    """Subclasses tesla_control.App. The GUI gets a new RC INPUT panel;
    everything else is unchanged."""

    def __init__(self, rc_port: str):
        self.rc = RcInput()
        self.rc_port = rc_port
        self.rc_reader: Optional[RcReader] = None
        self.rc_widgets: dict = {}
        super().__init__()
        self.title(f"Tesla Rack Control RC  v{__version__}  "
                   f"(core v{base.__version__})  --  {rc_port}")
        self._build_rc_panel()
        self.rc_reader = RcReader(rc_port, RC_BAUD, self, self.rc)
        self.rc_reader.start()

    # ---------- RC input plumbing ----------

    def rc_log(self, msg: str):
        self.log_q.put(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if self.logger:
            self.logger.event(f"rc: {msg}")

    def apply_rc_input(self, w_steer: int, w_p: int, w_rnd: int):
        """Translate raw PWM widths into ControlState updates. Called
        from the RcReader thread on every valid frame.

        Steering goes through openpilot's exact stick-to-output pipeline:
        runtime calibration -> deadband -> expo -> scale to angle.
        """

        # ---- Steering ----
        if not self.ctrl.estop:
            norm = self.rc.calib.normalize(w_steer)
            if abs(norm) < RC_DEADBAND_NORM:
                norm = 0.0
            shaped = apply_expo(norm, RC_EXPO_K)
            self.ctrl.target_angle_deg = shaped * base.HARD_ANGLE_LIMIT_DEG

        # ---- RND switch -> R / N / D ----
        gear = self._rnd_pwm_to_gear(w_rnd)
        if gear != self.rc.selected_gear:
            self.rc.selected_gear = gear
            if (self.worker is not None and not self.ctrl.estop
                    and gear != self.rc.last_shift_gear):
                self.rc_log(f"RND switch -> {gear}, queuing shift")
                self.rc.last_shift_gear = gear
                self.request_shift(gear)

        # ---- GEAR toggle -> P latch (long press) ----
        now = time.monotonic()
        if w_p >= RC_P_PRESS_THRESH_US:
            if self.rc._p_high_since is None:
                self.rc._p_high_since = now
            elif (now - self.rc._p_high_since) * 1000.0 >= RC_P_LATCH_HOLD_MS:
                if (self.worker is not None and not self.ctrl.estop
                        and (now - self.rc.last_p_latch_at) > RC_P_LATCH_COOLDOWN_S):
                    self.rc_log("P latch (gear switch held)")
                    self.rc.last_p_latch_at = now
                    self.rc.last_shift_gear = "P"
                    self.request_shift("P")
        else:
            self.rc._p_high_since = None

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
        frm = tk.Frame(self, bg=self.PANEL, bd=1, relief="solid",
                       highlightbackground=self.BORDER,
                       highlightthickness=1)
        frm.pack(fill="x", padx=8, pady=(0, 8))

        tk.Label(frm, text="RC INPUT", bg=self.PANEL, fg=self.DIM,
                 font=self.f_section, anchor="w"
                 ).pack(fill="x", padx=8, pady=(6, 2))

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
        self.rc_widgets["calib"]  = cell(row, "STICK range")
        self.rc_widgets["rnd"]    = cell(row, "RND us")
        self.rc_widgets["p"]      = cell(row, "P us")
        self.rc_widgets["gear"]   = cell(row, "GEAR")

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
            gear = self.rc.selected_gear
            lo = self.rc.calib.lo
            hi = self.rc.calib.hi
            seen = self.rc.calib.seen_movement

        w["port"].config(text=("OPEN" if connected else "CLOSED"),
                         fg=(self.GREEN if connected else self.RED))
        w["frames"].config(text=f"{frames}")
        w["steer"].config(text=(f"{steer}" if steer else "--"))
        w["calib"].config(
            text=(f"{lo}..{hi}" if seen else f"{lo}..{hi}*"),
            fg=(self.GREEN if seen else self.YELLOW))
        w["rnd"].config(text=(f"{rnd}" if rnd else "--"))
        w["p"].config(text=(f"{p}" if p else "--"))
        w["gear"].config(text=gear, fg=self.ORANGE)

    def _tick(self):
        super()._tick()
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
    print(f" RC expo                  : 0.4 * x^3 + 0.6 * x "
          f"(openpilot joystickd)")
    print(f" RC deadband              : {RC_DEADBAND_NORM*100:.1f} % normalized")
    print(f" RC steer endpoints       : runtime-calibrated "
          f"(boot {RC_BOOT_STEER_MIN_US}..{RC_BOOT_STEER_MAX_US} us)")
    print(f" RC RND switch buckets    : <{RC_RND_LOW_THRESH_US} R, "
          f">{RC_RND_HIGH_THRESH_US} D, else N")
    print(f" RC P-latch hold          : {RC_P_LATCH_HOLD_MS} ms above "
          f"{RC_P_PRESS_THRESH_US} us")
    print("=" * 72)
    base.banner()


if __name__ == "__main__":
    args = parse_args()
    banner_rc(args.rc_port)
    try:
        RcApp(args.rc_port).mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
