"""
Tesla Rack Control  --  v4.2.0-dev (PRND features)
==================================================

Single-program steering control for the patched 2013 Tesla Model S EPAS
rack. Drives the rack from a SYS TEC USB-CANmodul1 (model 3204001) on
Windows, with NO comma 3X required.

WHAT IS NEW IN v4.2 (vs v4.1)
    PRND awareness:
    - Listens to 0x118 DI_torque2 and decodes DI_gear,
      DI_gearRequest, and DI_vehicleSpeed (DI's own speed estimate,
      useful for verifying the 30 MPH MODE spoof is not propagating
      somewhere it shouldn't).
    - Status panel grows to 3 rows of 4 to show Gear, Gear Request,
      DI Speed, and Park Gate state.
    - Bus diagnostic adds 0x118.
    - CSV log adds gear, gear_request, di_vehicle_speed_mph columns.
    - Gear transitions are logged to the .log file.

    Safety guards (added after Derek's 30 MPH MODE in-car test
    "freaked out" the car):
    - **Park-to-engage gate.** When 0x118 is being received and the
      gear is not P, ENGAGE is refused. Bypassed automatically when
      0x118 has never been received (bench mode without DI on bus).
      Configurable via REQUIRE_PARK_TO_ENGAGE.
    - **30 MPH MODE pre-flight check**. If real ESP is transmitting
      0x155 above ESP_PREFLIGHT_REFUSE_HZ (1 Hz), the toggle refuses
      to enable. Prevents the contention case that caused the test
      failure.
    - **30 MPH MODE mid-session auto-disable**. If real ESP traffic
      appears while 30 MPH MODE is on, it disables itself within one
      tick.
    - **Auto-disengage on gear-out-of-P**. If engaged and the gear
      leaves Park, the worker disengages on the next tick.
    - **Auto-disengage on real motion**. If DI_vehicleSpeed (the
      car's own estimate, NOT our spoof) goes above 1 mph, the worker
      disengages. Any real motion of the car means we should not be
      commanding the rack.
    - **EAC-bounce watchdog**. If we see more than 5 EAC status
      transitions in 1 second, auto-E-STOP. Catches the May 2026
      flicker pattern automatically.

WHAT IS NEW IN v4.1 (vs v4)
    - **30 MPH MODE toggle button in the GUI.** Starts OFF. When the
      user clicks it, the program starts synthesizing 0x155 ESP_B at
      200 Hz claiming 30 km/h. The patched rack reads this as "the car
      is moving" and opens its at-speed envelope: more angle travel,
      more rate, more torque output.
    - HARD_ANGLE_LIMIT_DEG raised from 60 to 180. The clamp itself is
      always 180 in v4.1, but with 30 MPH MODE OFF the rack will only
      track up to its standstill ceiling (~60 deg). Past that the rack
      throws HIGH_ANGLE_REQ. With 30 MPH MODE ON, the rack will track
      to the full software clamp.
    - MAX_RATE_DEG_PER_SEC raised from 50 to 150. Same idea: the rack
      enforces its own rate ceiling depending on speed; we just stop
      capping it ourselves.
    - KEYBOARD_STEER_RATE_DEG_PER_SEC raised from 30 to 90 for snappy
      keyboard driving.
    - 0x155 transmitted at 200 Hz when the toggle is ON, vs the real
      Tesla ESP module's 50 Hz. At 4-to-1 our frames win arbitration
      most of the time. NOT bulletproof; see ESP CONTENTION below.
    - Bus diagnostic panel detects ESP contention: when 30 MPH MODE
      is ON and the 0x155 RX rate exceeds expectations, the row turns
      red. (Our own TX does not appear in RX -- we only see other
      transmitters.)

WHAT IS CARRIED OVER FROM v4
    - The SYS TEC adapter is the only device on our side. No comma 3X.
    - Slider + keyboard modes, steering wheel canvas, bus diagnostic
      panel, session logs (.log + .csv) in ./logs/.
    - Safety architecture: hard angle clamp, rate limit + LPF,
      RX-timeout watchdog, divergence trip (opt-in), bus-error trip,
      loop-overrun trip, four E-STOP paths (button, ESC, Q, window).

ESP CONTENTION (read this before clicking 30 MPH MODE on a live car)
    With 30 MPH MODE ON AND the real Tesla ESP module alive on the
    chassis CAN bus (which it is whenever the car is ON), there are
    two transmitters on 0x155. Same general failure mode as the May
    2026 EAC flicker bug, just on a different ID. v4.1 mitigates by
    transmitting at 200 Hz vs the real ESP's 50 Hz, but real-ESP
    frames do leak through.
      - On jacks (the only safe configuration for 30 MPH MODE in-car):
        the rack may briefly drop into MIN_SPEED gating and you'll
        see EAC blip. Mostly harmless; the rack re-acquires within a
        frame or two.
      - On wheels with the car not actually moving: dangerous --
        the rack's torque envelope momentarily opens for "30 km/h"
        then snaps shut for "0 km/h" repeatedly.
      - On wheels with the car ACTUALLY moving: do not run this code.
        Two transmitters on speed = one of them is lying = you do not
        want to be the lie.
    If the 0x155 RX row in the bus diagnostic panel goes RED while
    30 MPH MODE is ON, the real ESP is on the bus. Decide whether you
    want to continue.

REQUIREMENTS
    pip install python-can

    SYS TEC driver: install "sysWORXX USB-CAN Driver" from
    https://www.systec-electronic.com/en/services-support/downloads
    This installs USBCAN32.dll which python-can's `systec` backend uses.

USAGE
    python tesla_control.py

    1. Click CONNECT. Bus diagnostic panel populates within ~2 seconds.
    2. Confirm "0x488 (RX)" stays at 0.0 Hz. If it shows non-zero, you
       have a second transmitter on the bus (a comma device, a panda,
       another tool) and you must remove it.
    3. Click ENGAGE. Rack should transition INHIBITED -> AVAILABLE -> ACTIVE.
    4. Pick a mode (SLIDER default, KEYBOARD optional). Try modest
       angles first (10-20 deg) with 30 MPH MODE OFF to verify
       baseline.
    5. To unlock the at-speed envelope: click 30 MPH MODE. The button
       turns orange and a warning appears in the status bar. The rack
       will now accept full angle travel and faster rates.
    6. Press SAVE LOG (or just close the window) to flush the session
       log and CSV to ./logs/.

SAFETY
    * Front wheels OFF the ground or tie rods disconnected before ANY
      live testing. With 30 MPH MODE on, the rack applies even more
      force than it would at standstill.
    * 30 MPH MODE on a moving car is dangerous. Real ESP says one
      thing, our fake ESP says another, the rack blends. Don't.
    * Driver hands OFF the wheel during ENGAGE or the rack throws
      HANDS_ON.
    * E-STOP at any time: button, ESC, Q, or close the window.

NO-COMMA-3X SETUP CHEAT SHEET
    Defaults assume:
      - rack is in the car
      - real Tesla GTW is alive on chassis CAN (sends 0x101 at 10 Hz)
      - 3X is REMOVED from the bus
    Only 0x214 is synthesized at boot. 30 MPH MODE adds 0x155.

    On bench (rack off the car, no real GTW or ESP on the bus):
      flip SYNTHESIZE_GTW = True (you have to provide 0x101)
      30 MPH MODE toggle still works the same way

CAN PROTOCOL (verified against opendbc tesla_can.dbc)
    0x488 DAS_steeringControl  TX 50 Hz, 4 bytes
        b0 = (angle_raw >> 8) & 0x7F      angle_raw = (deg + 1638.35) * 10
        b1 = angle_raw & 0xFF
        b2 = (controlType << 6) | counter   controlType: 1=engage, 0=disable
        b3 = (0x88 + 0x04 + b0 + b1 + b2) & 0xFF
    0x101 GTW_epasControl  TX 20 Hz, 3 bytes (only if SYNTHESIZE_GTW)
    0x214 EPB_epasControl  TX 10 Hz, 3 bytes (always)
    0x155 ESP_B fake speed TX 200 Hz, 8 bytes (only if 30 MPH MODE on)
    0x370 EPAS_sysStatus   RX
        eacStatus    : byte 6 bits 7..5  (0=INHIBITED 1=AVAILABLE 2=ACTIVE
                                          3=FAULT 4=SNA)
        eacErrorCode : byte 2 bits 7..4
        SAS angle    : big-endian 14-bit at byte 4 bit 5, factor 0.1, off -819.2

Author: Derek Nagel (with Claude)
Date: 2026-05-07
"""

import can
import csv
import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from tkinter import font
from typing import Optional

__version__ = "4.2.0-dev"


# ============================================================================
# CONFIGURATION
# ============================================================================

# Hardware
CAN_BITRATE = 500_000           # Tesla chassis CAN
SYSTEC_DEVICE_NUMBER = 0        # First SYS TEC device on the system
SYSTEC_CHANNEL = 0              # CAN0 (USB-CANmodul1 has only one channel)

# Safety envelope (raised in v4.1 so 30 MPH MODE has somewhere to go;
# the rack itself enforces tighter caps when 30 MPH MODE is OFF).
HARD_ANGLE_LIMIT_DEG = 180.0    # Software clamp; rack will reject above ~60 if 30 MPH MODE off
MAX_RATE_DEG_PER_SEC = 150.0    # Software cap; rack at-speed allows ~250 deg/s
ANGLE_DIVERGENCE_LIMIT_DEG = 30.0  # commanded vs measured before E-STOP (raised for bigger commands)
RX_TIMEOUT_MS = 500             # Lose 0x370 for this long -> E-STOP
LOOP_OVERRUN_LIMIT_MS = 100     # 50 Hz loop overrun before E-STOP
TARGET_FILTER_TAU_S = 0.15      # Slider/keyboard target LPF time constant

# Divergence is OFF by default until you have confirmed on-bench that
# the GUI's measured angle tracks the wheel when turned by hand.
DIVERGENCE_TRIP_ENABLED = False

# Keepalive synthesis flags. Defaults assume IN-CAR with the real GTW
# and ESP modules alive on the bus, and the 3X REMOVED.
# Note: 0x155 is no longer a static flag in v4.1. It's a runtime
# toggle on ControlState.thirty_mph_mode, controlled by a button.
SYNTHESIZE_GTW = False          # 0x101 -- real car GTW handles this
SYNTHESIZE_EPB = True           # 0x214 -- THIS is what the 3X used to do
BENCH_FAKE_SPEED_KPH = 30.0     # Speed claimed when 30 MPH MODE is ON

# Keyboard-mode steering rate (degrees per second of held key).
# Independent of MAX_RATE_DEG_PER_SEC, which is the rack-protection cap.
KEYBOARD_STEER_RATE_DEG_PER_SEC = 90.0

# CAN IDs
ID_DAS_STEERING_CONTROL = 0x488
ID_GTW_EPAS_CONTROL     = 0x101
ID_EPB_EPAS_CONTROL     = 0x214
ID_EPAS_SYS_STATUS      = 0x370
ID_ESP_B_FAKE_SPEED     = 0x155
ID_DI_TORQUE2           = 0x118  # carries DI_gear, DI_gearRequest, DI_vehicleSpeed

# TX cycle periods (ms)
PERIOD_DAS_MS = 20              # 50 Hz
PERIOD_GTW_MS = 50              # 20 Hz
PERIOD_EPB_MS = 100             # 10 Hz
PERIOD_ESP_MS = 5               # 200 Hz when 30 MPH MODE on (drown out real 50 Hz ESP)

# When 30 MPH MODE is ON, expect roughly 50 Hz of "leakage" from the
# real ESP module (since we transmit at 200 Hz, our frames win 4 of 5
# arbitration races, so the rack mostly reads us). If the 0x155 RX rate
# exceeds this threshold while 30 MPH MODE is ON, the real ESP is
# present and contention is in play.
ESP_CONTENTION_RX_THRESHOLD_HZ = 5.0

# v4.2 safety guards added after Derek's 30 MPH MODE field test
# (the car "freaked out" -- ESP contention cascaded into other ECUs).

# Pre-flight: refuse to enable 30 MPH MODE if real ESP is transmitting
# 0x155 above this rate. Set to a low value because even occasional
# real-ESP frames are enough to cause cascading faults in other modules
# downstream of 0x155 (stability control, regen, EPB).
ESP_PREFLIGHT_REFUSE_HZ = 1.0

# Mid-session: if 30 MPH MODE is enabled and 0x155 RX rate climbs
# above this threshold (real ESP came alive), auto-disable.
ESP_AUTO_DISABLE_HZ = 5.0

# EAC-bounce watchdog. If we observe more than this many EAC status
# transitions in one second, auto-E-STOP. Catches the May 2026 flicker
# pattern automatically.
EAC_BOUNCE_LIMIT_PER_SEC = 5

# Real-motion watchdog. If DI_vehicleSpeed (the car's own estimate,
# unaffected by our 0x155 spoof) goes above this, auto-disengage. Any
# real motion of the car means the rack should not be under remote
# control -- we are bench-and-jacks-only.
REAL_MOTION_AUTO_DISENGAGE_MPH = 1.0

# Bus diagnostic panel: which IDs we want to display rates for, and
# what we expect on a healthy bus.
DIAG_IDS = [
    (0x101, "GTW_epasControl",       "real car GTW; ~10 Hz expected"),
    (0x108, "DI_torque1",            "drive inverter; ~100 Hz expected"),
    (0x118, "DI_torque2 (gear)",     "carries PRND; ~100 Hz expected"),
    (0x129, "SteeringAngle (SAS)",   "steering angle sensor; ~100 Hz"),
    (0x155, "ESP_B vehicleSpeed",    "real car ESP; ~50 Hz expected"),
    (0x214, "EPB_epasControl",       "we send this; ~10 Hz when synth"),
    (0x370, "EPAS_sysStatus (RX)",   "rack -> us; ~100 Hz expected"),
    (0x488, "DAS_steeringControl",   "WE OWN THIS ID. Should be 0 Hz RX!"),
]

# Logs
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# EAC enums (verified from opendbc tesla_can.dbc)
EAC_ERROR_CODES = {
    0: "NONE",  1: "MIN_SPEED",  2: "MAX_SPEED",  3: "HANDS_ON",
    4: "OUT_OF_RANGE",  5: "OVER_TORQUE",  6: "HIGH_ANGLE_REQ",
    7: "HIGH_ANGLE_RATE_REQ",  8: "HIGH_TORQUE_REQ",  9: "BLEND_REQ",
    10: "TIMEOUT", 11: "ECU_FAULT", 12: "BUS_FAULT",
    13: "INVALID_REQ", 14: "EPB_INHIBIT", 15: "SNA",
}

EAC_STATUS_NAMES = {
    0: "INHIBITED", 1: "AVAILABLE", 2: "ACTIVE", 3: "FAULT", 4: "SNA",
}

# DI_gear enum (verified from opendbc tesla_can.dbc, message 280 / 0x118)
DI_GEAR_NAMES = {
    0: "INVALID", 1: "P", 2: "R", 3: "N", 4: "D", 7: "SNA",
}
DI_GEAR_PARK = 1

# Refuse to engage unless gear is P. Bypassed when 0x118 has never
# been received (bench mode, no DI module on the bus). When 0x118 IS
# arriving and gear is not P, ENGAGE is refused.
REQUIRE_PARK_TO_ENGAGE = True

MODE_SLIDER = "slider"
MODE_KEYBOARD = "keyboard"


# ============================================================================
# CAN MESSAGE BUILDERS  (verified against opendbc tesla_can.dbc)
# ============================================================================

def build_das_steering_control(angle_deg: float, control_type: int,
                                counter: int) -> bytes:
    """0x488 DAS_steeringControl, 4 bytes."""
    angle_raw = int(round((angle_deg + 1638.35) * 10.0))
    angle_raw = max(0, min(0x7FFF, angle_raw))
    b0 = (angle_raw >> 8) & 0x7F            # MSB bit reserved for haptic flag
    b1 = angle_raw & 0xFF
    b2 = ((control_type & 0x03) << 6) | (counter & 0x0F)
    b3 = (0x88 + 0x04 + b0 + b1 + b2) & 0xFF
    return bytes([b0, b1, b2, b3])


def build_gtw_epas_control(counter: int, engaged: bool) -> bytes:
    """0x101 GTW_epasControl, 3 bytes. Patched rack ignores content, but
    the message must be present with valid checksum."""
    emergency_on = 0
    power_mode = 1                          # DRIVE_ON
    tune_request = 2                        # DM_STANDARD
    b0 = (emergency_on << 7) | (power_mode << 3) | (tune_request & 0x07)
    control_type = 1 if engaged else 0      # 1 = WITH_ANGLE
    ldw_enabled = 1 if engaged else 0
    b1 = ((control_type & 0x03) << 6) | ((ldw_enabled & 0x01) << 4) | (counter & 0x0F)
    b2 = (0x01 + 0x01 + b0 + b1) & 0xFF
    return bytes([b0, b1, b2])


def build_epb_epas_control(counter: int) -> bytes:
    """0x214 EPB_epasControl, 3 bytes. Required by the patched rack per
    gregjhogan/tesla-pre-ap-epas-patch README. Content ignored, but
    counter and checksum must be valid."""
    eac_allow = 1                           # ENABLE (ignored after patch)
    b0 = (eac_allow & 0x07) << 5
    b1 = counter & 0x0F
    b2 = (0x14 + 0x02 + b0 + b1) & 0xFF
    return bytes([b0, b1, b2])


def build_fake_esp_speed(speed_kph: float) -> bytes:
    """0x155 ESP_B (bench mode only). Not OEM-accurate but enough to
    clear EAC_ERROR_MIN_SPEED in lab tests."""
    raw = int(round((speed_kph + 40.0) / 0.04))
    raw &= 0x1FFF
    data = bytearray(8)
    data[3] = raw & 0xFF
    data[4] = (raw >> 8) & 0x1F
    return bytes(data)


# ============================================================================
# STATE
# ============================================================================

@dataclass
class RackStatus:
    last_rx_monotonic: float = 0.0
    eac_status: int = 4                     # SNA until proven otherwise
    eac_error_code: int = 0
    measured_angle_deg: float = 0.0
    rx_count: int = 0
    # 0x118 DI_torque2 decoded fields. -1 means "no 0x118 received yet"
    # (bench mode without the real DI module on the bus).
    gear: int = -1
    gear_request: int = -1
    di_vehicle_speed_mph: float = 0.0
    di_torque2_rx_count: int = 0
    # EAC transition timestamps for the bounce watchdog. Worker
    # appends; the bounce check reads. Bounded to keep memory finite.
    eac_transition_times: deque = field(default_factory=lambda: deque(maxlen=64))


@dataclass
class ControlState:
    mode: str = MODE_SLIDER
    target_angle_deg: float = 0.0           # raw user input
    filtered_target_deg: float = 0.0        # LPF smoothed
    commanded_angle_deg: float = 0.0        # rate-limited actual command
    engaged: bool = False
    estop: bool = False
    estop_reason: str = ""
    counter_488: int = 0
    counter_101: int = 0
    counter_214: int = 0
    bus_errors: int = 0
    # keyboard input flags (set by GUI, read by worker)
    key_left: bool = False
    key_right: bool = False
    # runtime 30 MPH MODE toggle (off by default). When True, worker
    # transmits 0x155 at 200 Hz to drown out the real ESP module and
    # convince the rack the car is moving.
    thirty_mph_mode: bool = False


class BusStats:
    """Per-ID rolling rate tracker. Lock-free for the read side: the
    worker thread appends timestamps, the UI thread computes Hz."""

    def __init__(self, ids):
        self._windows = {can_id: deque(maxlen=200) for can_id in ids}
        self._counts = defaultdict(int)
        self._last_seen = {}

    def note(self, can_id: int, ts: float):
        if can_id in self._windows:
            self._windows[can_id].append(ts)
            self._counts[can_id] += 1
            self._last_seen[can_id] = ts

    def hz(self, can_id: int) -> float:
        w = self._windows.get(can_id)
        if not w or len(w) < 2:
            return 0.0
        span = w[-1] - w[0]
        if span <= 0:
            return 0.0
        return (len(w) - 1) / span

    def count(self, can_id: int) -> int:
        return self._counts[can_id]

    def age_ms(self, can_id: int, now: float) -> float:
        last = self._last_seen.get(can_id)
        if last is None:
            return -1.0
        return (now - last) * 1000.0


# ============================================================================
# SESSION LOGGER
# ============================================================================

class SessionLogger:
    """Writes a human-readable .log and a per-frame .csv for one session.
    Safe to call from any thread (uses an internal lock).

    Files land in ./logs/session_<YYYYMMDD_HHMMSS>.{log,csv}.
    """

    CSV_COLUMNS = [
        "wall_time", "monotonic", "event",
        "mode", "engaged", "estop",
        "target_deg", "commanded_deg", "measured_deg",
        "eac_status", "eac_error",
        "rx_count_0x370", "bus_errors",
        # v4.2 PRND columns
        "gear", "gear_request", "di_vehicle_speed_mph",
    ]

    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(LOG_DIR, f"session_{ts}.log")
        self.csv_path = os.path.join(LOG_DIR, f"session_{ts}.csv")
        self._lock = threading.Lock()
        self._log_f = open(self.log_path, "a", buffering=1)   # line buffered
        self._csv_f = open(self.csv_path, "a", newline="", buffering=1)
        self._csv = csv.DictWriter(self._csv_f, fieldnames=self.CSV_COLUMNS)
        self._csv.writeheader()
        self._start_mono = time.monotonic()
        self.event(f"session start ({ts})")

    def event(self, text: str):
        wall = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"[{wall}] {text}"
        with self._lock:
            try:
                self._log_f.write(line + "\n")
            except Exception:
                pass

    def sample(self, ctrl: ControlState, status: RackStatus, event: str = ""):
        """Append one CSV row capturing the current control + rack state."""
        wall = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        mono = time.monotonic() - self._start_mono
        with self._lock:
            try:
                self._csv.writerow({
                    "wall_time": wall,
                    "monotonic": f"{mono:.4f}",
                    "event": event,
                    "mode": ctrl.mode,
                    "engaged": int(ctrl.engaged),
                    "estop": int(ctrl.estop),
                    "target_deg": f"{ctrl.target_angle_deg:.2f}",
                    "commanded_deg": f"{ctrl.commanded_angle_deg:.2f}",
                    "measured_deg": f"{status.measured_angle_deg:.2f}",
                    "eac_status": EAC_STATUS_NAMES.get(status.eac_status, "?"),
                    "eac_error": EAC_ERROR_CODES.get(status.eac_error_code, "?"),
                    "rx_count_0x370": status.rx_count,
                    "bus_errors": ctrl.bus_errors,
                    "gear": DI_GEAR_NAMES.get(status.gear, "") if status.gear >= 0 else "",
                    "gear_request": DI_GEAR_NAMES.get(status.gear_request, "") if status.gear_request >= 0 else "",
                    "di_vehicle_speed_mph": (f"{status.di_vehicle_speed_mph:.2f}"
                                             if status.di_torque2_rx_count > 0 else ""),
                })
            except Exception:
                pass

    def close(self):
        with self._lock:
            try:
                self._log_f.close()
            except Exception:
                pass
            try:
                self._csv_f.close()
            except Exception:
                pass


# ============================================================================
# CAN WORKER THREAD
# ============================================================================

class CanWorker(threading.Thread):
    """Owns the CAN bus, runs the TX loops, decodes 0x370, tracks bus
    stats, and runs the fast-path failsafes."""

    def __init__(self, ctrl: ControlState, status: RackStatus,
                 stats: BusStats, log_q: queue.Queue,
                 logger: Optional[SessionLogger]):
        super().__init__(daemon=True)
        self.ctrl = ctrl
        self.status = status
        self.stats = stats
        self.log_q = log_q
        self.logger = logger
        self.bus: Optional[can.BusABC] = None
        self._stop = threading.Event()
        self._connected = threading.Event()

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_q.put(f"[{ts}] {msg}")
        if self.logger:
            self.logger.event(msg)

    def connect(self) -> bool:
        try:
            self.bus = can.Bus(
                interface="systec",
                channel=SYSTEC_CHANNEL,
                device_number=SYSTEC_DEVICE_NUMBER,
                bitrate=CAN_BITRATE,
                receive_own_messages=False,
            )
            self._connected.set()
            self.log(f"CAN open: SYS TEC dev={SYSTEC_DEVICE_NUMBER} "
                     f"ch={SYSTEC_CHANNEL} {CAN_BITRATE//1000} kbps")
            self.log(f"keepalive plan: GTW={SYNTHESIZE_GTW} "
                     f"EPB={SYNTHESIZE_EPB} 30MPH={self.ctrl.thirty_mph_mode}")
            return True
        except Exception as e:
            self.log(f"CAN open FAILED: {e}")
            return False

    def disconnect(self):
        self._connected.clear()
        if self.bus is not None:
            try:
                self.bus.shutdown()
            except Exception:
                pass
            self.bus = None
            self.log("CAN closed")

    def trigger_estop(self, reason: str):
        if not self.ctrl.estop:
            self.ctrl.estop = True
            self.ctrl.estop_reason = reason
            self.ctrl.engaged = False
            self.log(f"E-STOP: {reason}")
            if self.logger:
                self.logger.sample(self.ctrl, self.status, event=f"estop:{reason}")

    def stop(self):
        self._stop.set()

    def _decode_0x118(self, data: bytes):
        """0x118 DI_torque2, 6 bytes. Decode gear, gear request, DI's
        own vehicle speed estimate.

        Bit layout (verified from opendbc tesla_can.dbc, BO_ 280):
          DI_gear          : 12|3@1+   (byte 1, bits 6..4)
          DI_vehicleSpeed  : 16|12@1+  factor 0.05, offset -25, MPH
                             (byte 2 bits 7..0, byte 3 bits 3..0)
          DI_gearRequest   : 28|3@1+   (byte 3, bits 6..4)
        """
        if len(data) < 4:
            return
        gear = (data[1] >> 4) & 0x07
        gear_req = (data[3] >> 4) & 0x07
        speed_raw = data[2] | ((data[3] & 0x0F) << 8)
        speed_mph = speed_raw * 0.05 - 25.0

        prev_gear = self.status.gear
        self.status.gear = gear
        self.status.gear_request = gear_req
        self.status.di_vehicle_speed_mph = speed_mph
        self.status.di_torque2_rx_count += 1

        if prev_gear != gear and prev_gear != -1:
            self.log(f"gear: {DI_GEAR_NAMES.get(prev_gear,'?')} -> "
                     f"{DI_GEAR_NAMES.get(gear,'?')}")
            if self.logger:
                self.logger.sample(self.ctrl, self.status,
                                   event=f"gear_change:{DI_GEAR_NAMES.get(gear,'?')}")

    def _decode_0x370(self, data: bytes):
        if len(data) < 8:
            return
        eac_status = (data[6] >> 5) & 0x07
        eac_err = (data[2] >> 4) & 0x0F
        # Big-endian 14-bit field at byte 4 bit 5 .. byte 5 bit 0.
        raw = ((data[4] & 0x3F) << 8) | data[5]
        angle = raw * 0.1 - 819.2

        prev_status = self.status.eac_status
        prev_err = self.status.eac_error_code

        self.status.last_rx_monotonic = time.monotonic()
        self.status.eac_status = eac_status
        self.status.eac_error_code = eac_err
        self.status.measured_angle_deg = angle
        self.status.rx_count += 1

        # Log every status transition (skip the boot-time SNA -> X first edge).
        if prev_status != eac_status and prev_status != 4:
            self.log(f"EAC: {EAC_STATUS_NAMES.get(prev_status,'?')} -> "
                     f"{EAC_STATUS_NAMES.get(eac_status,'?')} "
                     f"(err={EAC_ERROR_CODES.get(eac_err,'?')})")
            self.status.eac_transition_times.append(time.monotonic())
            if self.logger:
                self.logger.sample(self.ctrl, self.status,
                                   event=f"eac_transition:{EAC_STATUS_NAMES.get(eac_status,'?')}")
        if prev_err != eac_err and eac_err != 0:
            self.log(f"err -> {EAC_ERROR_CODES.get(eac_err,'?')}")

        if eac_status == 3:
            self.trigger_estop(f"rack FAULT, EAC_ERROR={EAC_ERROR_CODES.get(eac_err, '?')}")

        # Periodic CSV sample so the timeline has at least one row per
        # ~100 ms even when nothing transitions.
        if self.logger and self.status.rx_count % 10 == 0:
            self.logger.sample(self.ctrl, self.status)

    def _check_failsafes(self, now: float, last_loop: float):
        if self.ctrl.estop:
            return
        if self.status.rx_count > 0:
            since_rx_ms = (now - self.status.last_rx_monotonic) * 1000.0
            if since_rx_ms > RX_TIMEOUT_MS:
                self.trigger_estop(f"no 0x370 for {since_rx_ms:.0f} ms")
                return
        if (DIVERGENCE_TRIP_ENABLED and self.ctrl.engaged
                and self.status.rx_count > 5):
            err = abs(self.ctrl.commanded_angle_deg - self.status.measured_angle_deg)
            if err > ANGLE_DIVERGENCE_LIMIT_DEG:
                self.trigger_estop(
                    f"angle divergence {err:.1f} deg "
                    f"(cmd {self.ctrl.commanded_angle_deg:+.1f} "
                    f"vs meas {self.status.measured_angle_deg:+.1f})"
                )
                return
        if last_loop > 0:
            dt_ms = (now - last_loop) * 1000.0
            if dt_ms > (PERIOD_DAS_MS + LOOP_OVERRUN_LIMIT_MS):
                self.trigger_estop(f"loop overrun {dt_ms:.0f} ms")
                return

        # v4.2 -- EAC bounce watchdog. Count transitions in the last
        # second; if too many, the rack is flickering and we E-STOP
        # rather than letting the user keep commanding into the chaos.
        recent = sum(1 for t in self.status.eac_transition_times
                     if now - t < 1.0)
        if recent > EAC_BOUNCE_LIMIT_PER_SEC:
            self.trigger_estop(
                f"EAC bounce: {recent} transitions in last second")
            return

        # v4.2 -- real-motion auto-disengage. DI_vehicleSpeed is the
        # car's own estimate, unaffected by our 0x155 spoof. Any real
        # motion means we should not be commanding the rack.
        if (self.ctrl.engaged
                and self.status.di_torque2_rx_count > 0
                and abs(self.status.di_vehicle_speed_mph) > REAL_MOTION_AUTO_DISENGAGE_MPH):
            self.log(f"AUTO-DISENGAGE: real motion detected "
                     f"({self.status.di_vehicle_speed_mph:+.1f} mph)")
            self.ctrl.engaged = False
            return

        # v4.2 -- gear-out-of-park auto-disengage. If we engaged in P
        # and the gear changes to anything else, drop engagement.
        if (self.ctrl.engaged
                and self.status.di_torque2_rx_count > 0
                and self.status.gear != DI_GEAR_PARK
                and self.status.gear >= 0):
            gear_name = DI_GEAR_NAMES.get(self.status.gear, "?")
            self.log(f"AUTO-DISENGAGE: gear left Park (now {gear_name})")
            self.ctrl.engaged = False
            return

        # v4.2 -- mid-session ESP contention auto-disable for 30 MPH MODE.
        # If the real ESP comes alive (or comes back) while we're in
        # 30 MPH MODE, kill the spoof immediately.
        if self.ctrl.thirty_mph_mode:
            esp_rx_hz = self.stats.hz(ID_ESP_B_FAKE_SPEED)
            if esp_rx_hz > ESP_AUTO_DISABLE_HZ:
                self.ctrl.thirty_mph_mode = False
                self.log(f"AUTO-DISABLE 30 MPH MODE: real ESP detected "
                         f"({esp_rx_hz:.1f} Hz on 0x155)")
                if self.logger:
                    self.logger.sample(self.ctrl, self.status,
                                       event="30mph_auto_disabled")
                return

    def _apply_keyboard_input(self, dt_s: float):
        if self.ctrl.mode != MODE_KEYBOARD:
            return
        delta = 0.0
        if self.ctrl.key_left and not self.ctrl.key_right:
            delta = -KEYBOARD_STEER_RATE_DEG_PER_SEC * dt_s
        elif self.ctrl.key_right and not self.ctrl.key_left:
            delta = +KEYBOARD_STEER_RATE_DEG_PER_SEC * dt_s
        if delta != 0.0:
            new_target = self.ctrl.target_angle_deg + delta
            new_target = max(-HARD_ANGLE_LIMIT_DEG,
                             min(HARD_ANGLE_LIMIT_DEG, new_target))
            self.ctrl.target_angle_deg = new_target

    def _apply_rate_limit(self, dt_s: float):
        """LPF the user target, then rate-limit toward it."""
        raw = max(-HARD_ANGLE_LIMIT_DEG,
                  min(HARD_ANGLE_LIMIT_DEG, self.ctrl.target_angle_deg))
        alpha = dt_s / (TARGET_FILTER_TAU_S + dt_s)
        self.ctrl.filtered_target_deg += alpha * (raw - self.ctrl.filtered_target_deg)

        max_delta = MAX_RATE_DEG_PER_SEC * dt_s
        target = self.ctrl.filtered_target_deg
        cur = self.ctrl.commanded_angle_deg
        if target > cur + max_delta:
            cur += max_delta
        elif target < cur - max_delta:
            cur -= max_delta
        else:
            cur = target
        self.ctrl.commanded_angle_deg = cur

    def run(self):
        if not self.connect():
            return
        next_das = time.monotonic()
        next_gtw = next_das
        next_epb = next_das
        next_esp = next_das
        last_loop = 0.0

        while not self._stop.is_set():
            now = time.monotonic()

            # ----- RX drain -----
            try:
                while True:
                    msg = self.bus.recv(timeout=0)
                    if msg is None:
                        break
                    if msg.is_error_frame:
                        self.ctrl.bus_errors += 1
                        if self.ctrl.bus_errors > 50:
                            self.trigger_estop(
                                f"bus error count {self.ctrl.bus_errors}")
                        continue
                    # Log every observed ID for the diagnostic panel
                    self.stats.note(msg.arbitration_id, now)
                    if msg.arbitration_id == ID_EPAS_SYS_STATUS:
                        self._decode_0x370(msg.data)
                    elif msg.arbitration_id == ID_DI_TORQUE2:
                        self._decode_0x118(msg.data)
            except Exception as e:
                self.trigger_estop(f"RX exception: {e}")

            self._check_failsafes(now, last_loop)
            last_loop = now

            # ----- E-STOP path: send disengaged 0x488 frames and idle -----
            if self.ctrl.estop:
                if now >= next_das:
                    try:
                        data = build_das_steering_control(
                            self.ctrl.commanded_angle_deg, control_type=0,
                            counter=self.ctrl.counter_488,
                        )
                        self.bus.send(can.Message(
                            arbitration_id=ID_DAS_STEERING_CONTROL,
                            data=data, is_extended_id=False,
                        ))
                        self.ctrl.counter_488 = (self.ctrl.counter_488 + 1) & 0x0F
                    except Exception:
                        pass
                    next_das = now + PERIOD_DAS_MS / 1000.0
                time.sleep(0.005)
                continue

            # ----- Input shaping -----
            dt = PERIOD_DAS_MS / 1000.0
            self._apply_keyboard_input(dt)
            self._apply_rate_limit(dt)

            # ----- 0x488 DAS_steeringControl @ 50 Hz (always) -----
            if now >= next_das:
                try:
                    ctype = 1 if self.ctrl.engaged else 0
                    data = build_das_steering_control(
                        self.ctrl.commanded_angle_deg, ctype, self.ctrl.counter_488,
                    )
                    self.bus.send(can.Message(
                        arbitration_id=ID_DAS_STEERING_CONTROL,
                        data=data, is_extended_id=False,
                    ))
                    self.ctrl.counter_488 = (self.ctrl.counter_488 + 1) & 0x0F
                except Exception as e:
                    self.trigger_estop(f"TX 0x488 failed: {e}")
                next_das = now + PERIOD_DAS_MS / 1000.0

            # ----- 0x101 GTW_epasControl @ 20 Hz (optional) -----
            if SYNTHESIZE_GTW and now >= next_gtw:
                try:
                    data = build_gtw_epas_control(self.ctrl.counter_101,
                                                  self.ctrl.engaged)
                    self.bus.send(can.Message(
                        arbitration_id=ID_GTW_EPAS_CONTROL,
                        data=data, is_extended_id=False,
                    ))
                    self.ctrl.counter_101 = (self.ctrl.counter_101 + 1) & 0x0F
                except Exception as e:
                    self.trigger_estop(f"TX 0x101 failed: {e}")
                next_gtw = now + PERIOD_GTW_MS / 1000.0

            # ----- 0x214 EPB_epasControl @ 10 Hz (THE main 3X replacement) -----
            if SYNTHESIZE_EPB and now >= next_epb:
                try:
                    data = build_epb_epas_control(self.ctrl.counter_214)
                    self.bus.send(can.Message(
                        arbitration_id=ID_EPB_EPAS_CONTROL,
                        data=data, is_extended_id=False,
                    ))
                    self.ctrl.counter_214 = (self.ctrl.counter_214 + 1) & 0x0F
                except Exception as e:
                    self.trigger_estop(f"TX 0x214 failed: {e}")
                next_epb = now + PERIOD_EPB_MS / 1000.0

            # ----- 0x155 fake speed @ 200 Hz (when 30 MPH MODE is ON) -----
            if self.ctrl.thirty_mph_mode and now >= next_esp:
                try:
                    data = build_fake_esp_speed(BENCH_FAKE_SPEED_KPH)
                    self.bus.send(can.Message(
                        arbitration_id=ID_ESP_B_FAKE_SPEED,
                        data=data, is_extended_id=False,
                    ))
                except Exception:
                    pass
                next_esp = now + PERIOD_ESP_MS / 1000.0

            # ----- Hybrid sleep -----
            deadlines = [next_das]
            if SYNTHESIZE_GTW:            deadlines.append(next_gtw)
            if SYNTHESIZE_EPB:            deadlines.append(next_epb)
            if self.ctrl.thirty_mph_mode: deadlines.append(next_esp)
            sleep_until = min(deadlines)
            BUSY_WAIT_S = 0.002
            sleep_s = sleep_until - time.monotonic()
            if sleep_s > BUSY_WAIT_S:
                time.sleep(sleep_s - BUSY_WAIT_S)
            while time.monotonic() < sleep_until:
                pass

        self.disconnect()


# ============================================================================
# WHEEL CANVAS
# ============================================================================

class WheelCanvas:
    """Encapsulates the steering wheel widget. Drawn into a tk.Canvas."""

    def __init__(self, parent, size=240, bg="#1c1c1f"):
        self.size = size
        self.bg = bg
        self.canvas = tk.Canvas(parent, width=size, height=size,
                                bg=bg, highlightthickness=0)

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)

    def draw(self, angle_deg: float, label_below: str = ""):
        c = self.canvas
        c.delete("all")
        cx = cy = self.size // 2
        r = int(self.size * 0.42)
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      outline="#475569", width=8)
        c.create_oval(cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8,
                      outline="#334155", width=2)
        ang_rad = math.radians(angle_deg)
        for spoke_deg in (90, 210, 330):
            rad = math.radians(spoke_deg) + ang_rad
            x2 = cx + (r - 12) * math.cos(rad)
            y2 = cy - (r - 12) * math.sin(rad)
            c.create_line(cx, cy, x2, y2, fill="#64748b", width=6,
                          capstyle=tk.ROUND)
        c.create_oval(cx - 22, cy - 22, cx + 22, cy + 22,
                      fill="#1f2937", outline="#475569", width=2)
        rad_top = math.radians(90) + ang_rad
        x_top = cx + (r - 12) * math.cos(rad_top)
        y_top = cy - (r - 12) * math.sin(rad_top)
        c.create_oval(x_top - 8, y_top - 8, x_top + 8, y_top + 8,
                      fill="#3b82f6", outline="")
        c.create_text(cx, cy, text=f"{angle_deg:+.0f}",
                      fill="#e8e8e8", font=("Consolas", 14, "bold"))
        if label_below:
            c.create_text(cx, self.size - 14, text=label_below,
                          fill="#fbbf24", font=("Segoe UI", 10, "bold"))


# ============================================================================
# GUI
# ============================================================================

class App(tk.Tk):
    BG     = "#1e1e1e"
    FG     = "#e0e0e0"
    PANEL  = "#2a2a2a"
    SUNKEN = "#0f0f0f"
    ACCENT = "#3b82f6"
    GREEN  = "#22c55e"
    YELLOW = "#eab308"
    RED    = "#ef4444"
    DIM    = "#9ca3af"

    def __init__(self):
        super().__init__()
        self.title(f"Tesla Rack Control  --  v{__version__}  --  30 MPH MODE toggle")
        self.geometry("1080x920")
        self.configure(bg=self.BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.ctrl = ControlState()
        self.status = RackStatus()
        self.stats = BusStats([cid for cid, _, _ in DIAG_IDS])
        self.log_q: queue.Queue = queue.Queue()
        self.logger: Optional[SessionLogger] = None
        self.worker: Optional[CanWorker] = None

        self._build_styles()
        self._build_ui()
        self._bind_keys()
        self._tick()

    # ---------- Setup ----------

    def _build_styles(self):
        self.f_h1   = font.Font(family="Segoe UI", size=18, weight="bold")
        self.f_h2   = font.Font(family="Segoe UI", size=12, weight="bold")
        self.f_btn  = font.Font(family="Segoe UI", size=11, weight="bold")
        self.f_estop= font.Font(family="Segoe UI", size=16, weight="bold")
        self.f_big  = font.Font(family="Consolas", size=22, weight="bold")
        self.f_mid  = font.Font(family="Consolas", size=12)
        self.f_mono = font.Font(family="Consolas", size=10)
        self.f_help = font.Font(family="Segoe UI", size=9)

    def _bind_keys(self):
        self.bind("<Escape>",          lambda e: self.estop("ESC key"))
        self.bind("<KeyPress-q>",      lambda e: self.estop("Q key"))
        self.bind("<KeyPress-Q>",      lambda e: self.estop("Q key"))
        self.bind("<KeyPress-Left>",   self._key_left_down)
        self.bind("<KeyRelease-Left>", self._key_left_up)
        self.bind("<KeyPress-Right>",  self._key_right_down)
        self.bind("<KeyRelease-Right>",self._key_right_up)
        self.bind("<KeyPress-space>",  self._key_space)

    def _build_ui(self):
        # ---------- Header bar ----------
        hdr = tk.Frame(self, bg=self.BG)
        hdr.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(hdr, text=f"Tesla Rack Control  v{__version__}",
                 font=self.f_h1, fg=self.FG, bg=self.BG).pack(side="left")
        self.lbl_conn = tk.Label(hdr, text="DISCONNECTED",
                                 font=self.f_h2, fg=self.RED, bg=self.BG)
        self.lbl_conn.pack(side="right")

        # ---------- Action bar ----------
        bar = tk.Frame(self, bg=self.PANEL)
        bar.pack(fill="x", padx=14, pady=4)
        self.btn_conn = tk.Button(bar, text="CONNECT", font=self.f_btn,
                                  bg=self.ACCENT, fg="white", width=12,
                                  relief="flat", command=self.toggle_connect)
        self.btn_conn.pack(side="left", padx=6, pady=6)

        self.btn_engage = tk.Button(bar, text="ENGAGE", font=self.f_btn,
                                    bg=self.GREEN, fg="white", width=12,
                                    relief="flat", state="disabled",
                                    command=self.toggle_engage)
        self.btn_engage.pack(side="left", padx=6, pady=6)

        self.btn_save = tk.Button(bar, text="SAVE LOG", font=self.f_btn,
                                  bg="#525252", fg="white", width=12,
                                  relief="flat", state="disabled",
                                  command=self.save_log)
        self.btn_save.pack(side="left", padx=6, pady=6)

        # 30 MPH MODE toggle. Starts OFF. When ON, the worker thread
        # synthesizes 0x155 ESP_B at 200 Hz to spoof speed.
        self.btn_30mph = tk.Button(bar, text="30 MPH MODE: OFF",
                                   font=self.f_btn, bg="#525252", fg="white",
                                   width=18, relief="flat",
                                   command=self.toggle_30mph)
        self.btn_30mph.pack(side="left", padx=6, pady=6)

        self.btn_estop = tk.Button(bar, text="E - STOP   (ESC)",
                                   font=self.f_estop, bg=self.RED, fg="white",
                                   width=18, relief="flat",
                                   command=lambda: self.estop("button"))
        self.btn_estop.pack(side="right", padx=6, pady=6)

        # ---------- Two-column body ----------
        body = tk.Frame(self, bg=self.BG)
        body.pack(fill="both", expand=True, padx=14, pady=4)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)
        left  = tk.Frame(body, bg=self.BG)
        right = tk.Frame(body, bg=self.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # ---------- Status panel (LEFT TOP) ----------
        sp = tk.LabelFrame(left, text=" Rack Status ", font=self.f_h2,
                           fg=self.FG, bg=self.PANEL, bd=1, relief="solid")
        sp.pack(fill="x", pady=(0, 6))
        grid = tk.Frame(sp, bg=self.PANEL)
        grid.pack(fill="x", padx=10, pady=8)
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1)
        self.lbl_eac    = self._stat(grid, 0, 0, "EAC Status",     "SNA")
        self.lbl_err    = self._stat(grid, 0, 1, "Last Error",     "NONE")
        self.lbl_meas   = self._stat(grid, 0, 2, "Measured",       "-- deg")
        self.lbl_cmd    = self._stat(grid, 0, 3, "Commanded",      "-- deg")
        self.lbl_target = self._stat(grid, 1, 0, "Target",         "0.0 deg")
        self.lbl_diverg = self._stat(grid, 1, 1, "Divergence",     "0.0 deg")
        self.lbl_rx     = self._stat(grid, 1, 2, "0x370 RX count", "0")
        self.lbl_buserr = self._stat(grid, 1, 3, "Bus Errors",     "0")
        # v4.2 -- PRND row
        self.lbl_gear     = self._stat(grid, 2, 0, "Gear",         "--")
        self.lbl_gear_req = self._stat(grid, 2, 1, "Gear Request", "--")
        self.lbl_di_speed = self._stat(grid, 2, 2, "DI Speed",     "-- mph")
        self.lbl_park_gate= self._stat(grid, 2, 3, "Park Gate",    "armed" if REQUIRE_PARK_TO_ENGAGE else "off")

        # ---------- Mode tabs (LEFT MIDDLE) ----------
        modef = tk.Frame(left, bg=self.PANEL, bd=1, relief="solid")
        modef.pack(fill="x", pady=6)
        tk.Label(modef, text=" Input Mode ", font=self.f_h2,
                 fg=self.FG, bg=self.PANEL).pack(anchor="w", padx=10, pady=(6, 0))
        modebar = tk.Frame(modef, bg=self.PANEL)
        modebar.pack(fill="x", padx=10, pady=8)
        self.btn_mode_slider = tk.Button(
            modebar, text="SLIDER", font=self.f_btn, width=14, relief="flat",
            bg=self.ACCENT, fg="white",
            command=lambda: self.set_mode(MODE_SLIDER))
        self.btn_mode_slider.pack(side="left", padx=4)
        self.btn_mode_keyboard = tk.Button(
            modebar, text="KEYBOARD", font=self.f_btn, width=14, relief="flat",
            bg="#525252", fg="white",
            command=lambda: self.set_mode(MODE_KEYBOARD))
        self.btn_mode_keyboard.pack(side="left", padx=4)
        tk.Button(modebar, text="CENTER (0)", font=self.f_btn, width=12,
                  relief="flat", bg="#525252", fg="white",
                  command=self.on_center).pack(side="right", padx=4)

        # ---------- Slider controls ----------
        self.frame_slider = tk.Frame(left, bg=self.PANEL, bd=1, relief="solid")
        sl = tk.Frame(self.frame_slider, bg=self.PANEL)
        sl.pack(fill="x", padx=10, pady=10)
        tk.Label(sl, text=f"-{HARD_ANGLE_LIMIT_DEG:.0f}", font=self.f_mono,
                 fg=self.FG, bg=self.PANEL).pack(side="left")
        self.var_slider = tk.DoubleVar(value=0.0)
        self.slider = tk.Scale(sl, from_=-HARD_ANGLE_LIMIT_DEG,
                               to=HARD_ANGLE_LIMIT_DEG, resolution=0.5,
                               orient="horizontal", variable=self.var_slider,
                               command=self.on_slider, length=420,
                               bg=self.PANEL, fg=self.FG, troughcolor="#404040",
                               highlightthickness=0, sliderrelief="flat",
                               showvalue=0)
        self.slider.pack(side="left", padx=10, fill="x", expand=True)
        tk.Label(sl, text=f"+{HARD_ANGLE_LIMIT_DEG:.0f}", font=self.f_mono,
                 fg=self.FG, bg=self.PANEL).pack(side="left")
        entry_row = tk.Frame(self.frame_slider, bg=self.PANEL)
        entry_row.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(entry_row, text="Type angle (deg):", font=self.f_mid,
                 fg=self.FG, bg=self.PANEL).pack(side="left")
        self.var_entry = tk.StringVar(value="0.0")
        ent = tk.Entry(entry_row, textvariable=self.var_entry,
                       font=self.f_mono, width=10, bg="#1a1a1a", fg=self.FG,
                       insertbackground=self.FG, relief="flat")
        ent.pack(side="left", padx=8)
        ent.bind("<Return>", lambda e: self.on_set_entry())
        tk.Button(entry_row, text="SET", font=self.f_btn, bg=self.ACCENT,
                  fg="white", relief="flat", width=8,
                  command=self.on_set_entry).pack(side="left", padx=4)

        # ---------- Keyboard controls ----------
        self.frame_kbd = tk.Frame(left, bg=self.PANEL, bd=1, relief="solid")
        kb_inner = tk.Frame(self.frame_kbd, bg=self.PANEL)
        kb_inner.pack(fill="x", padx=10, pady=10)
        self.wheel = WheelCanvas(kb_inner, size=220, bg=self.PANEL)
        self.wheel.pack(side="left", padx=8)
        kb_help = tk.Frame(kb_inner, bg=self.PANEL)
        kb_help.pack(side="left", padx=14, anchor="n", pady=10)
        for line in (
            "LEFT / RIGHT arrow .... hold to steer",
            f"steer rate ............ {KEYBOARD_STEER_RATE_DEG_PER_SEC:.0f} deg/s",
            "SPACE ................. snap target to 0",
            "Q or ESC .............. E-STOP",
            "",
            "Click in the window if",
            "keys do not register.",
        ):
            tk.Label(kb_help, text=line, font=self.f_help,
                     fg=self.DIM, bg=self.PANEL,
                     anchor="w").pack(anchor="w")

        # Show slider mode by default.
        self.frame_slider.pack(fill="x", pady=6)

        # ---------- Bus Diagnostic Panel (RIGHT TOP) ----------
        dp = tk.LabelFrame(right, text=" Bus Diagnostic ",
                           font=self.f_h2, fg=self.FG, bg=self.PANEL,
                           bd=1, relief="solid")
        dp.pack(fill="x", pady=(0, 6))
        tk.Label(dp, text="frame rates per ID -- watch 0x488 stays at 0.0",
                 font=self.f_help, fg=self.DIM,
                 bg=self.PANEL).pack(anchor="w", padx=10, pady=(4, 0))
        diag_grid = tk.Frame(dp, bg=self.PANEL)
        diag_grid.pack(fill="x", padx=10, pady=8)
        self.diag_labels = {}
        # Header
        for col, txt in enumerate(("ID", "Hz", "count", "name")):
            tk.Label(diag_grid, text=txt, font=self.f_mono,
                     fg=self.DIM, bg=self.PANEL, anchor="w"
                     ).grid(row=0, column=col, sticky="w", padx=4)
        for row, (cid, name, _note) in enumerate(DIAG_IDS, start=1):
            tk.Label(diag_grid, text=f"0x{cid:03X}", font=self.f_mono,
                     fg=self.FG, bg=self.PANEL).grid(row=row, column=0,
                                                     sticky="w", padx=4)
            lbl_hz  = tk.Label(diag_grid, text=" 0.0", font=self.f_mono,
                               fg=self.DIM, bg=self.PANEL, width=8, anchor="e")
            lbl_cnt = tk.Label(diag_grid, text="0", font=self.f_mono,
                               fg=self.DIM, bg=self.PANEL, width=8, anchor="e")
            lbl_name= tk.Label(diag_grid, text=name, font=self.f_mono,
                               fg=self.FG, bg=self.PANEL, anchor="w")
            lbl_hz.grid (row=row, column=1, sticky="e", padx=4)
            lbl_cnt.grid(row=row, column=2, sticky="e", padx=4)
            lbl_name.grid(row=row, column=3, sticky="w", padx=4)
            self.diag_labels[cid] = (lbl_hz, lbl_cnt, lbl_name)

        # ---------- Keepalive plan readout (RIGHT) ----------
        kp = tk.LabelFrame(right, text=" Keepalives We Send ",
                           font=self.f_h2, fg=self.FG, bg=self.PANEL,
                           bd=1, relief="solid")
        kp.pack(fill="x", pady=6)
        kp_inner = tk.Frame(kp, bg=self.PANEL)
        kp_inner.pack(fill="x", padx=10, pady=8)
        # Static lines (don't change at runtime)
        tk.Label(kp_inner, text="  0x488 DAS_steeringControl   ALWAYS  @ 50 Hz",
                 font=self.f_mono, fg=self.FG, bg=self.PANEL,
                 anchor="w").pack(fill="x")
        tk.Label(kp_inner,
                 text=f"  0x101 GTW_epasControl       {'ON ' if SYNTHESIZE_GTW else 'off'}     @ 20 Hz",
                 font=self.f_mono, fg=self.FG, bg=self.PANEL,
                 anchor="w").pack(fill="x")
        tk.Label(kp_inner,
                 text=f"  0x214 EPB_epasControl       {'ON ' if SYNTHESIZE_EPB else 'off'}     @ 10 Hz",
                 font=self.f_mono, fg=self.FG, bg=self.PANEL,
                 anchor="w").pack(fill="x")
        # Dynamic line (updated by _tick to reflect 30 MPH MODE state)
        self.lbl_kp_speed = tk.Label(kp_inner,
                 text="  0x155 ESP_B fake speed      off     @ 200 Hz",
                 font=self.f_mono, fg=self.FG, bg=self.PANEL, anchor="w")
        self.lbl_kp_speed.pack(fill="x")
        # ESP contention warning line (hidden until 30 MPH MODE is on
        # AND we detect real ESP traffic on the bus).
        self.lbl_esp_warn = tk.Label(kp_inner, text="", font=self.f_mono,
                                     fg=self.RED, bg=self.PANEL, anchor="w")
        self.lbl_esp_warn.pack(fill="x")

        # ---------- Event log (RIGHT bottom, takes remaining space) ----------
        lp = tk.LabelFrame(right, text=" Event Log ", font=self.f_h2,
                           fg=self.FG, bg=self.PANEL, bd=1, relief="solid")
        lp.pack(fill="both", expand=True, pady=(6, 0))
        self.txt_log = tk.Text(lp, font=self.f_mono, bg=self.SUNKEN,
                               fg=self.FG, relief="flat", wrap="word")
        self.txt_log.pack(fill="both", expand=True, padx=6, pady=6)
        self._log_local("ready. click CONNECT to open the SYS TEC adapter.")
        self._log_local(f"keepalives: GTW={SYNTHESIZE_GTW} EPB={SYNTHESIZE_EPB} "
                        f"30MPH=OFF (toggle button when ready)")

    def _stat(self, parent, row, col, label, value):
        cell = tk.Frame(parent, bg=self.PANEL)
        cell.grid(row=row, column=col, sticky="nsew", padx=6, pady=4)
        tk.Label(cell, text=label, font=self.f_mono, fg=self.DIM,
                 bg=self.PANEL).pack(anchor="w")
        v = tk.Label(cell, text=value, font=self.f_big, fg=self.FG,
                     bg=self.PANEL)
        v.pack(anchor="w")
        return v

    # ---------- Actions ----------

    def toggle_connect(self):
        if self.worker is None:
            self.ctrl.estop = False
            self.ctrl.estop_reason = ""
            self.ctrl.engaged = False
            self.ctrl.bus_errors = 0
            self.status.rx_count = 0
            self.status.last_rx_monotonic = 0.0
            self.logger = SessionLogger()
            self._log_local(f"session started -> {self.logger.log_path}")
            self.worker = CanWorker(self.ctrl, self.status, self.stats,
                                    self.log_q, self.logger)
            self.worker.start()
            self.btn_conn.config(text="DISCONNECT", bg="#525252")
            self.btn_engage.config(state="normal")
            self.btn_save.config(state="normal")
            self.lbl_conn.config(text="CONNECTING...", fg=self.YELLOW)
        else:
            self.estop("disconnect requested")
            self.worker.stop()
            self.worker.join(timeout=2.0)
            self.worker = None
            if self.logger:
                self.logger.event("disconnect; closing log")
                self.logger.close()
                self._log_local(f"log saved: {self.logger.log_path}")
                self._log_local(f"csv  saved: {self.logger.csv_path}")
                self.logger = None
            self.btn_conn.config(text="CONNECT", bg=self.ACCENT)
            self.btn_engage.config(state="disabled", text="ENGAGE",
                                   bg=self.GREEN)
            self.btn_save.config(state="disabled")
            self.lbl_conn.config(text="DISCONNECTED", fg=self.RED)

    def toggle_engage(self):
        if self.ctrl.estop:
            self._log_local("clear E-STOP first (reconnect to reset)")
            return
        if not self.ctrl.engaged:
            if self.status.rx_count == 0:
                self._log_local("REFUSED: no 0x370 yet, cannot engage blind")
                return
            # v4.2 park-to-engage gate. Only enforced when 0x118 has
            # actually been observed (so bench mode without a real DI
            # module on the bus is not blocked).
            if (REQUIRE_PARK_TO_ENGAGE
                    and self.status.di_torque2_rx_count > 0
                    and self.status.gear != DI_GEAR_PARK):
                gear_name = DI_GEAR_NAMES.get(self.status.gear, "?")
                self._log_local(f"REFUSED: gear is {gear_name}, must be P "
                                "to engage. Shift to Park first.")
                return
            cur = self.status.measured_angle_deg
            self.ctrl.commanded_angle_deg = cur
            self.ctrl.filtered_target_deg = cur
            self.ctrl.target_angle_deg = cur
            self.var_slider.set(cur)
            self.ctrl.engaged = True
            self.btn_engage.config(text="DISENGAGE", bg="#ea580c")
            self._log_local(f"ENGAGED at {self.status.measured_angle_deg:+.1f} deg")
            if self.logger:
                self.logger.sample(self.ctrl, self.status, event="engage")
        else:
            self.ctrl.engaged = False
            self.btn_engage.config(text="ENGAGE", bg=self.GREEN)
            self._log_local("DISENGAGED")
            if self.logger:
                self.logger.sample(self.ctrl, self.status, event="disengage")

    def set_mode(self, mode: str):
        if mode == self.ctrl.mode:
            return
        self.ctrl.mode = mode
        self.ctrl.key_left = False
        self.ctrl.key_right = False
        if mode == MODE_SLIDER:
            self.frame_kbd.pack_forget()
            self.frame_slider.pack(fill="x", pady=6)
            self.btn_mode_slider.config(bg=self.ACCENT)
            self.btn_mode_keyboard.config(bg="#525252")
        else:
            self.frame_slider.pack_forget()
            self.frame_kbd.pack(fill="x", pady=6)
            self.btn_mode_slider.config(bg="#525252")
            self.btn_mode_keyboard.config(bg=self.ACCENT)
            self.focus_force()
        self._log_local(f"mode -> {mode}")
        if self.logger:
            self.logger.event(f"mode change: {mode}")

    def on_slider(self, val):
        if self.ctrl.estop or self.ctrl.mode != MODE_SLIDER:
            return
        try:
            v = float(val)
            self.ctrl.target_angle_deg = max(-HARD_ANGLE_LIMIT_DEG,
                                             min(HARD_ANGLE_LIMIT_DEG, v))
            self.var_entry.set(f"{self.ctrl.target_angle_deg:.1f}")
        except ValueError:
            pass

    def on_set_entry(self):
        if self.ctrl.estop or self.ctrl.mode != MODE_SLIDER:
            return
        try:
            v = float(self.var_entry.get())
        except ValueError:
            self._log_local("bad number")
            return
        if abs(v) > HARD_ANGLE_LIMIT_DEG:
            self._log_local(f"REFUSED: {v:.1f} exceeds +/- "
                            f"{HARD_ANGLE_LIMIT_DEG:.0f}")
            return
        self.ctrl.target_angle_deg = v
        self.var_slider.set(v)
        self._log_local(f"target set to {v:+.1f} deg")

    def on_center(self):
        if self.ctrl.estop:
            return
        self.ctrl.target_angle_deg = 0.0
        self.var_slider.set(0.0)
        self.var_entry.set("0.0")
        self._log_local("centering")

    def save_log(self):
        """Flush the current session log to disk without disconnecting."""
        if not self.logger:
            self._log_local("no active session log to save")
            return
        self.logger.event("manual flush requested")
        self._log_local(f"log path: {self.logger.log_path}")
        self._log_local(f"csv path: {self.logger.csv_path}")

    def toggle_30mph(self):
        """Flip the 30 MPH MODE runtime toggle. When ON, the worker
        sends 0x155 ESP_B at 200 Hz claiming 30 km/h. The patched rack
        opens its at-speed envelope: more angle, more rate, more torque.

        Cannot be enabled while engaged -- you should not change the
        rack's speed envelope while it is actively steering, because
        the rack's torque output will jump. Disengage first."""
        if self.ctrl.thirty_mph_mode:
            # Turning OFF
            self.ctrl.thirty_mph_mode = False
            self.btn_30mph.config(text="30 MPH MODE: OFF", bg="#525252")
            self._log_local("30 MPH MODE: OFF (rack reverts to standstill envelope)")
            if self.logger:
                self.logger.event("30 MPH MODE off")
                self.logger.sample(self.ctrl, self.status, event="30mph_off")
        else:
            # Turning ON
            if self.ctrl.engaged:
                self._log_local("REFUSED: disengage before enabling 30 MPH MODE")
                return
            # v4.2 PRE-FLIGHT: refuse if real ESP is on the bus.
            # The May 2026 in-car test "freaked out" the car because two
            # transmitters on 0x155 cascaded into stability/regen/EPB
            # faults. If we see real ESP traffic here, we must not enable.
            esp_rx_hz = self.stats.hz(ID_ESP_B_FAKE_SPEED)
            if esp_rx_hz > ESP_PREFLIGHT_REFUSE_HZ:
                self._log_local(
                    f"REFUSED 30 MPH MODE: real ESP detected on bus "
                    f"({esp_rx_hz:.1f} Hz on 0x155). Disconnect the ESP "
                    "module or move to a bench setup before enabling.")
                if self.logger:
                    self.logger.event(
                        f"30 MPH MODE refused: real ESP at {esp_rx_hz:.1f} Hz")
                return
            self.ctrl.thirty_mph_mode = True
            self.btn_30mph.config(text="30 MPH MODE: ON", bg="#ea580c")
            self._log_local(f"30 MPH MODE: ON (faking {BENCH_FAKE_SPEED_KPH:.0f} km/h "
                            "at 200 Hz; rack will open at-speed envelope)")
            self._log_local("WARNING: front wheels MUST be off the ground")
            if self.logger:
                self.logger.event("30 MPH MODE on")
                self.logger.sample(self.ctrl, self.status, event="30mph_on")

    def estop(self, reason: str):
        if self.worker:
            self.worker.trigger_estop(reason)
        else:
            self.ctrl.estop = True
            self.ctrl.estop_reason = reason
            self._log_local(f"E-STOP: {reason}")

    def on_close(self):
        self.estop("window closed")
        if self.worker:
            self.worker.stop()
            self.worker.join(timeout=2.0)
        if self.logger:
            self.logger.event("window closed; closing log")
            self.logger.close()
        self.destroy()

    # ---------- Key handlers ----------

    def _key_left_down(self, _):
        if self.ctrl.mode == MODE_KEYBOARD and not self.ctrl.estop:
            self.ctrl.key_left = True
    def _key_left_up(self, _):
        self.ctrl.key_left = False
    def _key_right_down(self, _):
        if self.ctrl.mode == MODE_KEYBOARD and not self.ctrl.estop:
            self.ctrl.key_right = True
    def _key_right_up(self, _):
        self.ctrl.key_right = False
    def _key_space(self, _):
        if not self.ctrl.estop:
            self.on_center()

    # ---------- UI tick ----------

    def _log_local(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{ts}] {msg}\n")
        self.txt_log.see("end")

    def _tick(self):
        # Drain log queue
        try:
            while True:
                line = self.log_q.get_nowait()
                self.txt_log.insert("end", line + "\n")
                self.txt_log.see("end")
        except queue.Empty:
            pass

        # Connection light
        if self.worker is None:
            self.lbl_conn.config(text="DISCONNECTED", fg=self.RED)
        elif self.ctrl.estop:
            self.lbl_conn.config(text=f"E-STOP: {self.ctrl.estop_reason}",
                                 fg=self.RED)
        elif self.status.rx_count == 0:
            self.lbl_conn.config(text="WAITING FOR 0x370...", fg=self.YELLOW)
        else:
            self.lbl_conn.config(text="EPAS LINK OK", fg=self.GREEN)

        # Status readouts
        eac = self.status.eac_status
        eac_color = {0: self.DIM, 1: self.YELLOW, 2: self.GREEN,
                     3: self.RED, 4: self.DIM}.get(eac, self.FG)
        self.lbl_eac.config(text=EAC_STATUS_NAMES.get(eac, "?"), fg=eac_color)
        err_name = EAC_ERROR_CODES.get(self.status.eac_error_code, "?")
        self.lbl_err.config(
            text=err_name,
            fg=self.RED if self.status.eac_error_code else self.GREEN)
        self.lbl_meas.config(text=f"{self.status.measured_angle_deg:+.1f} deg")
        self.lbl_cmd.config (text=f"{self.ctrl.commanded_angle_deg:+.1f} deg")
        self.lbl_target.config(text=f"{self.ctrl.target_angle_deg:+.1f} deg")
        self.lbl_rx.config(text=str(self.status.rx_count))
        diverg = abs(self.ctrl.commanded_angle_deg
                     - self.status.measured_angle_deg)
        d_color = self.RED if diverg > ANGLE_DIVERGENCE_LIMIT_DEG * 0.6 else self.FG
        self.lbl_diverg.config(text=f"{diverg:.1f} deg", fg=d_color)
        self.lbl_buserr.config(
            text=str(self.ctrl.bus_errors),
            fg=self.RED if self.ctrl.bus_errors else self.FG)

        # PRND row
        gear = self.status.gear
        if gear < 0:
            self.lbl_gear.config(text="-- (no DI)", fg=self.DIM)
            self.lbl_gear_req.config(text="--", fg=self.DIM)
            self.lbl_di_speed.config(text="-- mph", fg=self.DIM)
        else:
            gear_name = DI_GEAR_NAMES.get(gear, "?")
            gear_color = {1: self.GREEN, 2: self.RED, 3: self.YELLOW,
                          4: self.RED}.get(gear, self.DIM)
            self.lbl_gear.config(text=gear_name, fg=gear_color)
            req_name = DI_GEAR_NAMES.get(self.status.gear_request, "?")
            req_color = self.FG if self.status.gear_request == gear else self.YELLOW
            self.lbl_gear_req.config(text=req_name, fg=req_color)
            self.lbl_di_speed.config(
                text=f"{self.status.di_vehicle_speed_mph:+.1f} mph",
                fg=self.FG)
        # Park gate state
        if not REQUIRE_PARK_TO_ENGAGE:
            self.lbl_park_gate.config(text="off", fg=self.DIM)
        elif self.status.di_torque2_rx_count == 0:
            self.lbl_park_gate.config(text="bypass (no DI)", fg=self.YELLOW)
        elif self.status.gear == DI_GEAR_PARK:
            self.lbl_park_gate.config(text="OK (P)", fg=self.GREEN)
        else:
            self.lbl_park_gate.config(text="BLOCKED", fg=self.RED)

        # Bus diagnostic panel
        now = time.monotonic()
        esp_contention = False
        for cid, (lbl_hz, lbl_cnt, _lbl_name) in self.diag_labels.items():
            hz = self.stats.hz(cid)
            cnt = self.stats.count(cid)
            color = self.DIM if hz < 0.1 else self.GREEN
            # Special case: any RX of 0x488 means a second transmitter
            # exists on the bus. That is the contention bug we just fled.
            if cid == 0x488 and hz > 0.1:
                color = self.RED
            # Special case for 0x155: when 30 MPH MODE is ON, our own
            # frames don't echo back, so any 0x155 RX traffic above the
            # threshold is the real ESP module fighting us.
            if (cid == 0x155 and self.ctrl.thirty_mph_mode
                    and hz > ESP_CONTENTION_RX_THRESHOLD_HZ):
                color = self.RED
                esp_contention = True
            lbl_hz.config(text=f"{hz:6.1f}", fg=color)
            lbl_cnt.config(text=str(cnt),
                           fg=self.DIM if cnt == 0 else self.FG)

        # Keepalive plan dynamic line + ESP contention warning
        if self.ctrl.thirty_mph_mode:
            self.lbl_kp_speed.config(
                text=f"  0x155 ESP_B fake speed      ON     @ 200 Hz "
                     f"({BENCH_FAKE_SPEED_KPH:.0f} km/h)", fg=self.YELLOW)
        else:
            self.lbl_kp_speed.config(
                text="  0x155 ESP_B fake speed      off     @ 200 Hz", fg=self.FG)
        if esp_contention:
            self.lbl_esp_warn.config(
                text="  ! REAL ESP DETECTED ON BUS -- contention "
                     "with our 0x155 (see docstring)")
        else:
            self.lbl_esp_warn.config(text="")

        # Wheel canvas (always render -- shows commanded angle even in slider mode)
        if self.ctrl.mode == MODE_KEYBOARD:
            label = ""
            if self.ctrl.key_left and not self.ctrl.key_right:
                label = "<<<  STEERING LEFT"
            elif self.ctrl.key_right and not self.ctrl.key_left:
                label = "STEERING RIGHT  >>>"
            else:
                label = "HOLDING"
            self.wheel.draw(self.ctrl.commanded_angle_deg, label_below=label)

        # Sync ENGAGE button label to actual engaged state. The worker
        # thread can auto-disengage from a watchdog (real motion, gear
        # leaving P, ESP contention), so we must reflect that in the UI.
        if not self.ctrl.engaged and self.btn_engage["text"] != "ENGAGE":
            self.btn_engage.config(text="ENGAGE", bg=self.GREEN)
        # Sync 30 MPH MODE button to its actual state (auto-disable
        # in worker can flip it).
        if (not self.ctrl.thirty_mph_mode
                and self.btn_30mph["text"] != "30 MPH MODE: OFF"):
            self.btn_30mph.config(text="30 MPH MODE: OFF", bg="#525252")

        self.after(50, self._tick)


# ============================================================================
# ENTRY POINT
# ============================================================================

def banner():
    print("=" * 72)
    print(f" Tesla Rack Control v{__version__}  --  30 MPH MODE toggle (off at boot)")
    print(" SYS TEC USB-CANmodul1 (3204001) on Windows")
    print("=" * 72)
    print(f" CAN bitrate              : {CAN_BITRATE} bps")
    print(f" Hard angle limit         : +/- {HARD_ANGLE_LIMIT_DEG:.0f} deg")
    print(f" Max rate                 : {MAX_RATE_DEG_PER_SEC:.0f} deg/sec")
    print(f" Keyboard rate            : {KEYBOARD_STEER_RATE_DEG_PER_SEC:.0f} deg/sec")
    print(f" Divergence trip          : {ANGLE_DIVERGENCE_LIMIT_DEG:.0f} deg "
          f"({'enabled' if DIVERGENCE_TRIP_ENABLED else 'disabled'})")
    print(f" Synthesize 0x101 (GTW)   : {SYNTHESIZE_GTW}")
    print(f" Synthesize 0x214 (EPB)   : {SYNTHESIZE_EPB}")
    print(f" 30 MPH MODE 0x155 fake   : runtime toggle, default OFF")
    print(f"   when ON               : {BENCH_FAKE_SPEED_KPH:.0f} km/h "
          f"@ {1000//PERIOD_ESP_MS} Hz")
    print(f" Park-to-engage gate      : {'armed' if REQUIRE_PARK_TO_ENGAGE else 'off'}")
    print(f"   (bypassed when 0x118 DI_torque2 has not been observed)")
    print(f" 30 MPH MODE pre-flight   : refuse if 0x155 RX > "
          f"{ESP_PREFLIGHT_REFUSE_HZ:.0f} Hz")
    print(f" 30 MPH MODE auto-disable : if 0x155 RX > "
          f"{ESP_AUTO_DISABLE_HZ:.0f} Hz mid-session")
    print(f" EAC bounce watchdog      : E-STOP if > "
          f"{EAC_BOUNCE_LIMIT_PER_SEC} EAC transitions / second")
    print(f" Real-motion auto-disengage: if |DI speed| > "
          f"{REAL_MOTION_AUTO_DISENGAGE_MPH:.1f} mph")
    print(f" Log dir                  : {LOG_DIR}")
    print("=" * 72)


if __name__ == "__main__":
    banner()
    try:
        App().mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
