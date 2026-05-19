"""
Tesla Rack Control  --  v5.0.4 (remove EAC auto-disengage)
==================================================================

Single-program steering control for the patched 2013 Tesla Model S EPAS
rack. Drives the rack from a SYS TEC USB-CANmodul1 (model 3204001) on
Windows, with NO comma 3X required.

WHAT IS NEW IN v5.0.4 (vs v4.3.3)
    - All EAC auto-disengage behaviours removed. The rack will no
      longer drop engagement automatically due to:
        * EAC-bounce watchdog (was: E-STOP if > 5 EAC transitions/s)
        * Real-motion auto-disengage (was: disengage if |DI speed| > 1 mph)
        * Gear-out-of-park auto-disengage (was: disengage if gear != P)
      The operator is now fully responsible for deciding when to
      disengage. Manual DISENGAGE, ESC, Q, and the window-close
      E-STOP paths remain in place.

WHAT IS NEW IN v4.3.3 (vs v4.3.0)
    - Steering wheel widget can now show a real photographed wheel
      that rotates with the commanded angle. Drop a transparent PNG
      into assets/wheel.png and the GUI uses it. Without the asset
      the original vector wheel is drawn instead. Helper script:
      `python tools/prepare_wheel.py path/to/photo.jpg` removes a
      mostly-white background and writes assets/wheel.png. Requires
      Pillow (added to requirements.txt).
    - Keyboard PRND: P / R / N / D keys now fire shifts directly.
      Works while LEFT / RIGHT arrows are held, so you can steer
      and shift simultaneously without taking your hands off the
      keyboard.
    - The "must disengage to shift" gate is removed. The non-
      blocking 200 Hz burst from v4.2.1 keeps 0x488 keepalives
      flowing during a shift, so the rack does not lose steering
      control mid-shift. The shift is logged as
      "SHIFT WHILE ENGAGED -> X" so it stands out in session logs.

WHAT IS NEW IN v4.3 (vs v4.2.1)
    - HARD_ANGLE_LIMIT_DEG raised from 180 to 360. Wheel can now
      command one full revolution in either direction (720° total
      range). Mechanical lock-to-lock on a 2013 Model S rack is
      ~±540°, so 360° leaves a comfortable safety margin to the
      end-stops.
    - Slider, keyboard input, and startup banner all auto-scale
      from the constant. No other knob changes: rate stays at 150
      deg/sec, divergence trip stays at 30 deg, all watchdogs
      unchanged. Bigger range with same rate just means you can
      drive there, not slam there.
    - First-test note: at standstill the rack accepts up to ~60°
      without 30 MPH MODE. Above that you need 30 MPH MODE ON. The
      software clamp doesn't change which physical region of the
      angle envelope is reachable -- it only stops being the
      bottleneck.

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
    - **EAC-bounce watchdog**, **real-motion auto-disengage**, and
      **gear-out-of-park auto-disengage** were introduced in v4.2 and
      removed in v5.0.4. See v5.0.4 release notes above.

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
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from tkinter import font
from typing import Optional

__version__ = "5.0.4"


# ============================================================================
# CONFIGURATION
# ============================================================================

# Hardware
CAN_BITRATE = 500_000           # Tesla chassis CAN
SYSTEC_DEVICE_NUMBER = 0        # First SYS TEC device on the system
SYSTEC_CHANNEL = 0              # CAN0 (USB-CANmodul1 has only one channel)

# Safety envelope (raised in v4.1 so 30 MPH MODE has somewhere to go;
# the rack itself enforces tighter caps when 30 MPH MODE is OFF).
HARD_ANGLE_LIMIT_DEG = 360.0    # Software clamp; rack will reject above ~60 if 30 MPH MODE off (v4.3: ±360°, one full turn each way)
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
ID_SBW_RQ_SCCM          = 0x6D   # gear shift request from steering column

# Gear shift -- 0x6D SBW_RQ_SCCM transmission parameters.
#
# v4.2.1 (2026-05-07 evening): non-blocking burst.
# Previously the burst blocked the worker for ~350 ms which caused
# the rack to fault EPAS_d039_kfc_reset because 0x488 stopped during
# the gap. Now the burst interleaves into the main 50 Hz loop --
# one 0x6D frame goes out every SBW_BURST_PERIOD_MS without blocking.
# The 0x488 keepalive stream continues uninterrupted.
#
# Also bumped the rate from 100 Hz to 200 Hz (5 ms period). At 100 Hz
# we were tied with the real stalk's IDLE-frame stream and lost ~50%
# of arbitration races. At 200 Hz our frames win 4 of every 5.
SBW_BURST_ACTIVE_FRAMES   = 30   # 30 active frames at 200 Hz = 150 ms of "request gear X"
SBW_BURST_IDLE_FRAMES     = 10   # 10 idle frames at 200 Hz = 50 ms of "stalk released"
SBW_BURST_PERIOD_MS       = 5    # 200 Hz, 4x the real stalk's rate
SBW_VERIFY_AFTER_MS       = 200  # log resulting gear this long after burst ends

# TSL_RND_Posn_StW values (verified from opendbc tesla_can.dbc, BO 109)
TSL_RND_IDLE   = 0
TSL_RND_R      = 1
TSL_RND_N_UP   = 2
TSL_RND_N_DOWN = 4
TSL_RND_D      = 8

# TSL_P_Psd_StW values
TSL_P_IDLE     = 0
TSL_P_PSD      = 1   # Park button pressed

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

# Speed threshold used by the shift gate to refuse R/D commands while
# the car is moving. Not an auto-disengage trigger (v5.0.4: all
# auto-disengage behaviours removed).
REAL_MOTION_AUTO_DISENGAGE_MPH = 1.0

# Bus diagnostic panel: which IDs we want to display rates for, and
# what we expect on a healthy bus.
DIAG_IDS = [
    (0x6D,  "SBW_RQ_SCCM (shift)",   "stalk gear request; bursts when we shift"),
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

# DI_brakePedalState enum (verified from opendbc tesla_can.dbc)
# 0=NotApplied, 1=ApplyingFault, 2=Released_Holding, 3=Applied
# Values 1 and 3 both indicate the brake is currently applied.
DI_BRAKE_STATE_NAMES = {
    0: "RELEASED",
    1: "FAULT",
    2: "HOLDING",
    3: "APPLIED",
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


def tesla_crc8(data: bytes) -> int:
    """Tesla CRC-8/SAE-J1850. Polynomial 0x1D, init 0xFF, XOR-out 0xFF.

    Verified against BogGyver/panda safety_tesla.h tesla_compute_crc:
    its lookup table starts 0x00, 0x1D, 0x3A, 0x27 ... which is the
    standard CRC-8/SAE-J1850 table for polynomial 0x1D, and the
    function's docstring states verbatim:
      "Calculate CRC8 using 1D poly, FF start, FF end"

    Used by 0x6D SBW_RQ_SCCM (gear shift) and 0x45 STW_ACTN_RQ
    (stalk) and other Tesla messages that use CRC8 instead of the
    simpler sum-checksum.

    NOTE: the original v4.2 implementation used polynomial 0x2F
    (AUTOSAR) and prepended the address byte to the CRC input.
    Both were wrong. Fixed after Charlie's 2026-05-07 field test
    showed shifts being silently ignored by the SCCM.
    """
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x1D) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc ^ 0xFF


def build_sbw_rq(rnd_posn: int, p_pressed: int, counter: int) -> bytes:
    """0x6D SBW_RQ_SCCM, 4 bytes. Gear shift request.

    Field layout (DBC + observed from real stalk capture
    field_testing/captures/20260507_011220_shift_diagnostic/):
      byte 0           : 0x40 (MsgTxmtId = 1, all other bits zero)
      byte 1 bits 0..3 : TSL_RND_Posn_StW          (gear position)
      byte 1 bits 4..5 : TSL_P_Psd_StW             (P button)
      byte 1 bits 6..7 : reserved, ALWAYS SET (= 0xC0 mask)
      byte 2 bits 4..7 : MC_SBW_RQ_SCCM            (counter, 0..15)
      byte 3 bits 0..7 : CRC_SBW_RQ_SCCM           (CRC-8/J1850)

    Byte 0 = 0x40 and byte-1 bits 6-7 = 0b11 are constant fixed bits
    that the SCCM checks. Initial v4.2 implementation set byte 0 = 0
    and ignored those byte-1 bits (the DBC doesn't define them).
    Charlie's 2026-05-07 capture proved the SCCM rejects frames
    without these bits, even with a valid CRC.

    CRC is computed over the 3 data bytes ONLY -- no address prefix.
    Verified against 6 captured stalk-shift frames (all CRC OK).
    """
    b0 = 0x40
    b1 = 0xC0 | ((p_pressed & 0x03) << 4) | (rnd_posn & 0x0F)
    b2 = (counter & 0x0F) << 4
    crc = tesla_crc8(bytes([b0, b1, b2]))
    return bytes([b0, b1, b2, crc])


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
    # Brake (from 0x118 also). brake_pedal: 0/1 boolean. brake_state: enum.
    brake_pedal: int = -1
    brake_state: int = -1



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
    # Gear shift request (set by GUI, consumed by worker). When set,
    # worker bursts SBW_BURST_ACTIVE_FRAMES of 0x6D with the requested
    # rnd/p values, then SBW_BURST_IDLE_FRAMES of IDLE, then clears
    # to None. While shift_target is set, the GUI's gear buttons stay
    # disabled to prevent overlapping shifts.
    shift_target: Optional[tuple] = None  # (rnd_posn, p_pressed, label) -- set by GUI, cleared by worker when burst done
    counter_sbw: int = 0
    # v4.2.1 non-blocking burst state machine. Phases:
    #   None       -> not shifting
    #   "active"   -> sending shift-request frames at 200 Hz
    #   "idle"     -> sending IDLE-stalk frames at 200 Hz (settling tail)
    #   "verify"   -> burst done, waiting for DI to update gear, then log result
    shift_phase: Optional[str] = None
    shift_frames_left: int = 0
    shift_verify_at: float = 0.0
    shift_label: str = ""
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
        # v4.2 PRND + brake columns
        "gear", "gear_request", "di_vehicle_speed_mph",
        "brake_pedal", "brake_state",
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
                    "brake_pedal": ("PRESSED" if status.brake_pedal == 1
                                    else ("released" if status.brake_pedal == 0 else "")),
                    "brake_state": (DI_BRAKE_STATE_NAMES.get(status.brake_state, "")
                                    if status.brake_state >= 0 else ""),
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

    def _clear_shift_state(self):
        """Reset the shift state machine. Called on E-STOP and disconnect
        so a new session starts clean."""
        self.ctrl.shift_target = None
        self.ctrl.shift_phase = None
        self.ctrl.shift_frames_left = 0
        self.ctrl.shift_label = ""

    def trigger_estop(self, reason: str):
        if not self.ctrl.estop:
            self.ctrl.estop = True
            self.ctrl.estop_reason = reason
            self.ctrl.engaged = False
            self._clear_shift_state()  # cancel any in-flight shift burst
            self.log(f"E-STOP: {reason}")
            if self.logger:
                self.logger.sample(self.ctrl, self.status, event=f"estop:{reason}")

    def stop(self):
        self._stop.set()

    def _decode_0x118(self, data: bytes):
        """0x118 DI_torque2, 6 bytes. Decode gear, gear request,
        vehicle speed, and brake state.

        Bit layout (verified from opendbc tesla_can.dbc, BO_ 280):
          DI_gear           : 12|3@1+   (byte 1, bits 6..4)
          DI_brakePedal     : 15|1@1+   (byte 1, bit 7)
          DI_vehicleSpeed   : 16|12@1+  factor 0.05, offset -25, MPH
          DI_gearRequest    : 28|3@1+   (byte 3, bits 6..4)
          DI_brakePedalState: 36|2@1+   (byte 4, bits 4..5)
        """
        if len(data) < 5:
            return
        gear = (data[1] >> 4) & 0x07
        brake_pedal = (data[1] >> 7) & 0x01
        gear_req = (data[3] >> 4) & 0x07
        speed_raw = data[2] | ((data[3] & 0x0F) << 8)
        speed_mph = speed_raw * 0.05 - 25.0
        brake_state = (data[4] >> 4) & 0x03

        prev_gear = self.status.gear
        prev_brake = self.status.brake_pedal
        self.status.gear = gear
        self.status.gear_request = gear_req
        self.status.di_vehicle_speed_mph = speed_mph
        self.status.brake_pedal = brake_pedal
        self.status.brake_state = brake_state
        self.status.di_torque2_rx_count += 1

        if prev_gear != gear and prev_gear != -1:
            self.log(f"gear: {DI_GEAR_NAMES.get(prev_gear,'?')} -> "
                     f"{DI_GEAR_NAMES.get(gear,'?')}")
            if self.logger:
                self.logger.sample(self.ctrl, self.status,
                                   event=f"gear_change:{DI_GEAR_NAMES.get(gear,'?')}")
        if prev_brake != brake_pedal and prev_brake != -1:
            self.log(f"brake: {'PRESSED' if brake_pedal else 'released'}")

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

    def _start_shift_burst(self):
        """Promote ctrl.shift_target (set by GUI) into the state-machine
        fields so the main loop can interleave the burst with the
        50 Hz steering keepalive. Non-blocking: returns immediately.
        """
        target = self.ctrl.shift_target
        if target is None:
            return
        rnd, p, label = target
        self.ctrl.shift_label = label
        self.ctrl.shift_phase = "active"
        self.ctrl.shift_frames_left = SBW_BURST_ACTIVE_FRAMES
        self.log(f"SHIFT: requesting {label} via 0x6D burst "
                 f"({SBW_BURST_ACTIVE_FRAMES} active + "
                 f"{SBW_BURST_IDLE_FRAMES} idle frames at "
                 f"{1000//SBW_BURST_PERIOD_MS} Hz)")

    def _send_one_sbw_frame(self):
        """Send one 0x6D frame matching the current shift phase, then
        advance the state machine. Called from the main loop whenever
        next_sbw deadline expires.
        """
        if self.ctrl.shift_phase == "active":
            target = self.ctrl.shift_target
            if target is None:
                # Defensive: GUI cleared shift_target; abort burst.
                self.ctrl.shift_phase = None
                return
            rnd, p, _label = target
        elif self.ctrl.shift_phase == "idle":
            rnd, p = TSL_RND_IDLE, TSL_P_IDLE
        else:
            return  # not bursting

        try:
            data = build_sbw_rq(rnd, p, self.ctrl.counter_sbw)
            self.bus.send(can.Message(
                arbitration_id=ID_SBW_RQ_SCCM,
                data=data, is_extended_id=False,
            ))
            self.ctrl.counter_sbw = (self.ctrl.counter_sbw + 1) & 0x0F
        except Exception as e:
            self.log(f"SHIFT FAILED: TX 0x6D error: {e}")
            self.ctrl.shift_phase = None
            self.ctrl.shift_target = None
            return

        self.ctrl.shift_frames_left -= 1
        if self.ctrl.shift_frames_left > 0:
            return

        # Phase complete -- advance.
        if self.ctrl.shift_phase == "active":
            self.ctrl.shift_phase = "idle"
            self.ctrl.shift_frames_left = SBW_BURST_IDLE_FRAMES
        elif self.ctrl.shift_phase == "idle":
            self.ctrl.shift_phase = "verify"
            self.ctrl.shift_verify_at = (time.monotonic()
                                         + SBW_VERIFY_AFTER_MS / 1000.0)
            self.ctrl.shift_target = None  # GUI button re-enables

    def _maybe_verify_shift(self, now: float):
        """If a burst recently ended, log the resulting gear once DI
        has had time to update."""
        if (self.ctrl.shift_phase == "verify"
                and now >= self.ctrl.shift_verify_at):
            gear_name = DI_GEAR_NAMES.get(self.status.gear, "?")
            self.log(f"SHIFT post-burst gear: {gear_name} "
                     f"(requested {self.ctrl.shift_label})")
            self.ctrl.shift_phase = None
            self.ctrl.shift_label = ""

    def run(self):
        if not self.connect():
            return
        next_das = time.monotonic()
        next_gtw = next_das
        next_epb = next_das
        next_esp = next_das
        next_sbw = next_das   # v4.2.1: non-blocking shift burst
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

            # ----- Shift burst state machine (non-blocking, v4.2.1) -----
            # GUI sets ctrl.shift_target via request_shift(). The state
            # machine takes it over and emits 0x6D frames at 200 Hz
            # alongside the normal 0x488 keepalive. Replaces the old
            # blocking _execute_shift_burst() which caused EPAS resets
            # by silencing 0x488 for 350 ms.
            if (self.ctrl.shift_target is not None
                    and self.ctrl.shift_phase is None
                    and not self.ctrl.estop):
                self._start_shift_burst()
                next_sbw = now   # send first frame this iteration
            if self.ctrl.shift_phase in ("active", "idle") and now >= next_sbw:
                self._send_one_sbw_frame()
                next_sbw = now + SBW_BURST_PERIOD_MS / 1000.0
            self._maybe_verify_shift(now)

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
            # v4.2.1: when bursting a gear shift, use the 5 ms SBW
            # deadline to drive the loop at 200 Hz so 0x6D frames go
            # out at the requested rate. 0x488/0x214 keep their own
            # cadence but the loop iterates faster.
            if self.ctrl.shift_phase in ("active", "idle"):
                deadlines.append(next_sbw)
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
    """Encapsulates the steering wheel widget. Drawn into a tk.Canvas.

    If assets/wheel.png exists relative to this file, the widget shows
    a rotating image of that wheel (use tools/prepare_wheel.py to make
    one with a transparent background). Otherwise it falls back to a
    minimal vector drawing.
    """

    _ASSET_REL = "assets/wheel.png"

    def __init__(self, parent, size=240, bg="#1c1c1f"):
        self.size = size
        self.bg = bg
        self.canvas = tk.Canvas(parent, width=size, height=size,
                                bg=bg, highlightthickness=0)
        self._pil_mod = None
        self._imagetk_mod = None
        self._image_pil = None
        self._image_tk = None
        self._tried_pil_load = False

    def _load_image(self):
        if self._tried_pil_load:
            return
        self._tried_pil_load = True
        try:
            from PIL import Image, ImageTk
        except ImportError:
            return
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, *self._ASSET_REL.split("/"))
        if not os.path.exists(path):
            return
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail((self.size, self.size), Image.LANCZOS)
        except Exception:
            return
        self._pil_mod = Image
        self._imagetk_mod = ImageTk
        self._image_pil = img

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)

    def draw(self, angle_deg: float, label_below: str = ""):
        self._load_image()
        if self._image_pil is not None:
            self._draw_image(angle_deg, label_below)
        else:
            self._draw_vector(angle_deg, label_below)

    def _draw_image(self, angle_deg: float, label_below: str):
        c = self.canvas
        c.delete("all")
        cx = cy = self.size // 2
        # PIL rotate is counter-clockwise; positive angle_deg = right
        # turn = clockwise on screen, so negate.
        rotated = self._image_pil.rotate(
            -angle_deg, resample=self._pil_mod.BICUBIC, expand=False
        )
        # Keep a reference on self so Tk doesn't garbage-collect it.
        self._image_tk = self._imagetk_mod.PhotoImage(rotated)
        c.create_image(cx, cy, image=self._image_tk)
        c.create_text(cx, cy + 6, text=f"{angle_deg:+.0f}",
                      fill="#e8e8e8", font=("Consolas", 14, "bold"))
        if label_below:
            c.create_text(cx, self.size - 14, text=label_below,
                          fill="#fbbf24", font=("Segoe UI", 10, "bold"))

    def _draw_vector(self, angle_deg: float, label_below: str = ""):
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
    # GitHub-dark-inspired palette. Tighter contrast, less harsh
    # than the original, more "instrumentation panel" than "demo".
    BG       = "#0d1117"   # window background
    PANEL    = "#161b22"   # primary panel background
    PANEL2   = "#1c2128"   # cell / stat background (one shade up)
    BORDER   = "#30363d"   # subtle border between panels
    SUNKEN   = "#010409"   # event log / sunken areas
    FG       = "#e6edf3"   # primary text
    DIM      = "#8b949e"   # labels, secondary text
    MUTE     = "#6e7681"   # disabled / placeholder
    ACCENT   = "#388bfd"   # blue (primary action)
    GREEN    = "#3fb950"   # success / nominal
    YELLOW   = "#d29922"   # warning
    ORANGE   = "#db6d28"   # engaged / on
    RED      = "#f85149"   # error / E-STOP

    def __init__(self):
        super().__init__()
        self.title(f"Tesla Rack Control  v{__version__}")
        self.geometry("1280x920")
        self.minsize(1180, 800)
        self.configure(bg=self.BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.ctrl = ControlState()
        self.status = RackStatus()
        self.stats = BusStats([cid for cid, _, _ in DIAG_IDS])
        self.log_q: queue.Queue = queue.Queue()
        self.logger: Optional[SessionLogger] = None
        self.worker: Optional[CanWorker] = None
        self.elapsed_start: Optional[float] = None  # set on CONNECT
        self.vitals: dict = {}                       # vitals strip widgets
        self.kp_lines: dict = {}                     # keepalive line dots

        self._build_styles()
        self._build_ui()
        self._bind_keys()
        self._tick()

    # ---------- Setup ----------

    def _build_styles(self):
        # New hierarchy (v4.2 polish, partial). f_h2 kept as an alias
        # for f_section so existing _build_ui calls still work; the
        # full UI rewrite to use f_section / f_label / f_pill directly
        # is in progress.
        self.f_h1     = font.Font(family="Segoe UI", size=16, weight="bold")
        self.f_section= font.Font(family="Segoe UI", size=9,  weight="bold")
        self.f_h2     = font.Font(family="Segoe UI", size=12, weight="bold")
        self.f_btn    = font.Font(family="Segoe UI", size=10, weight="bold")
        self.f_estop  = font.Font(family="Segoe UI", size=14, weight="bold")
        self.f_pill   = font.Font(family="Segoe UI", size=10, weight="bold")
        self.f_label  = font.Font(family="Segoe UI", size=8)
        self.f_help   = font.Font(family="Segoe UI", size=9)
        self.f_big    = font.Font(family="Consolas", size=20, weight="bold")
        self.f_mid    = font.Font(family="Consolas", size=11)
        self.f_mono   = font.Font(family="Consolas", size=10)

    def _bind_keys(self):
        self.bind("<Escape>",          lambda e: self.estop("ESC key"))
        self.bind("<KeyPress-q>",      lambda e: self.estop("Q key"))
        self.bind("<KeyPress-Q>",      lambda e: self.estop("Q key"))
        self.bind("<KeyPress-Left>",   self._key_left_down)
        self.bind("<KeyRelease-Left>", self._key_left_up)
        self.bind("<KeyPress-Right>",  self._key_right_down)
        self.bind("<KeyRelease-Right>",self._key_right_up)
        self.bind("<KeyPress-space>",  self._key_space)
        # v4.3.3: P/R/N/D fire shifts. Bound on KeyPress (not release)
        # so a single tap is enough; works while arrow keys are held.
        for letter, gear in (("p", "P"), ("r", "R"), ("n", "N"), ("d", "D")):
            self.bind(f"<KeyPress-{letter}>",
                      lambda e, g=gear: self.request_shift(g))
            self.bind(f"<KeyPress-{letter.upper()}>",
                      lambda e, g=gear: self.request_shift(g))

    def _build_ui(self):
        # ===================== HEADER =====================
        hdr = tk.Frame(self, bg=self.BG)
        hdr.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(hdr, text="Tesla Rack Control", font=self.f_h1,
                 fg=self.FG, bg=self.BG).pack(side="left")
        tk.Label(hdr, text=f"v{__version__}", font=self.f_help,
                 fg=self.DIM, bg=self.BG).pack(side="left", padx=(10, 0),
                                               anchor="s", pady=(0, 4))

        # ===================== VITALS STRIP =====================
        # At-a-glance pills for: LINK / EAC / GEAR / BRAKE / 30 MPH / SHIFT
        vital = tk.Frame(self, bg=self.PANEL,
                         highlightbackground=self.BORDER, highlightthickness=1)
        vital.pack(fill="x", padx=16, pady=(0, 8))
        for key, label in (("link",  "LINK"),
                           ("eac",   "EAC"),
                           ("gear",  "GEAR"),
                           ("brake", "BRAKE"),
                           ("mph30", "30 MPH"),
                           ("shift", "SHIFT")):
            cell = tk.Frame(vital, bg=self.PANEL)
            cell.pack(side="left", padx=14, pady=10)
            dot = tk.Label(cell, text="●", font=self.f_pill,
                           fg=self.MUTE, bg=self.PANEL)
            dot.pack(side="left")
            tk.Label(cell, text=label, font=self.f_label,
                     fg=self.DIM, bg=self.PANEL).pack(side="left", padx=(6, 6))
            val = tk.Label(cell, text="--", font=self.f_pill,
                           fg=self.FG, bg=self.PANEL)
            val.pack(side="left")
            self.vitals[key] = (dot, val)

        # ===================== ACTION BAR =====================
        bar_wrap = tk.Frame(self, bg=self.BG)
        bar_wrap.pack(fill="x", padx=16, pady=(0, 8))
        bar = tk.Frame(bar_wrap, bg=self.PANEL,
                       highlightbackground=self.BORDER, highlightthickness=1)
        bar.pack(fill="x")
        self.btn_conn = tk.Button(bar, text="CONNECT", font=self.f_btn,
                                  bg=self.ACCENT, fg="white", width=12,
                                  relief="flat", padx=4, pady=8,
                                  command=self.toggle_connect)
        self.btn_conn.pack(side="left", padx=(8, 4), pady=8)
        self.btn_engage = tk.Button(bar, text="ENGAGE", font=self.f_btn,
                                    bg=self.GREEN, fg="white", width=12,
                                    relief="flat", state="disabled",
                                    padx=4, pady=8,
                                    command=self.toggle_engage)
        self.btn_engage.pack(side="left", padx=4, pady=8)
        self.btn_30mph = tk.Button(bar, text="30 MPH MODE: OFF",
                                   font=self.f_btn, bg="#525252", fg="white",
                                   width=18, relief="flat", padx=4, pady=8,
                                   command=self.toggle_30mph)
        self.btn_30mph.pack(side="left", padx=4, pady=8)
        self.btn_save_test = tk.Button(bar, text="SAVE TEST", font=self.f_btn,
                                       bg="#525252", fg="white", width=14,
                                       relief="flat", state="disabled",
                                       padx=4, pady=8,
                                       command=self.open_save_test_dialog)
        self.btn_save_test.pack(side="left", padx=4, pady=8)
        self.btn_estop = tk.Button(bar, text="E - STOP   (ESC)",
                                   font=self.f_estop, bg=self.RED, fg="white",
                                   width=18, relief="flat", padx=4, pady=8,
                                   command=lambda: self.estop("button"))
        self.btn_estop.pack(side="right", padx=8, pady=8)

        # ===================== STATUS BAR (bottom; pack first so body fills above) =====================
        statusbar_wrap = tk.Frame(self, bg=self.BG)
        statusbar_wrap.pack(fill="x", side="bottom", padx=16, pady=(8, 12))
        statusbar = tk.Frame(statusbar_wrap, bg=self.PANEL,
                             highlightbackground=self.BORDER, highlightthickness=1)
        statusbar.pack(fill="x")
        self.lbl_statusbar = tk.Label(statusbar,
                                      text="session: not started · idle",
                                      font=self.f_help, fg=self.DIM,
                                      bg=self.PANEL, anchor="w",
                                      padx=12, pady=6)
        self.lbl_statusbar.pack(fill="x")

        # ===================== BODY (2 columns) =====================
        body = tk.Frame(self, bg=self.BG)
        body.pack(fill="both", expand=True, padx=16, pady=0)
        body.grid_columnconfigure(0, weight=3, minsize=720)
        body.grid_columnconfigure(1, weight=2, minsize=440)
        body.grid_rowconfigure(0, weight=1)
        left  = tk.Frame(body, bg=self.BG)
        right = tk.Frame(body, bg=self.BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 0))

        # ----- LEFT COLUMN -----
        # Keepalives moved here so the Event Log on the right gets
        # the full column height (was getting squeezed before).
        self._build_steering_command(left)
        self._build_rack_status(left)
        self._build_vehicle_status(left)
        self._build_shift_panel(left)
        self._build_keepalives(left)

        # ----- RIGHT COLUMN -----
        self._build_bus_diagnostic(right)
        self._build_event_log(right)   # expand=True; fills remainder

        self._log_local("ready. click CONNECT to open the SYS TEC adapter.")
        self._log_local(f"keepalives: GTW={SYNTHESIZE_GTW} EPB={SYNTHESIZE_EPB} "
                        f"30MPH=OFF (toggle button when ready)")

    # -------------------- panel builders --------------------

    def _section(self, parent, title, expand=False):
        """Section panel: small-caps heading above a bordered frame."""
        wrap = tk.Frame(parent, bg=self.BG)
        if expand:
            wrap.pack(fill="both", expand=True, pady=(0, 8))
        else:
            wrap.pack(fill="x", pady=(0, 8))
        tk.Label(wrap, text=title, font=self.f_section,
                 fg=self.DIM, bg=self.BG).pack(anchor="w", padx=2, pady=(0, 4))
        panel = tk.Frame(wrap, bg=self.PANEL,
                         highlightbackground=self.BORDER, highlightthickness=1)
        if expand:
            panel.pack(fill="both", expand=True)
        else:
            panel.pack(fill="x")
        return panel

    def _stat(self, parent, row, col, label, value):
        """Stat cell: small caps label above bigger value."""
        cell = tk.Frame(parent, bg=self.PANEL)
        cell.grid(row=row, column=col, sticky="nsew", padx=10, pady=(6, 8))
        tk.Label(cell, text=label, font=self.f_label, fg=self.DIM,
                 bg=self.PANEL, anchor="w").pack(anchor="w")
        v = tk.Label(cell, text=value, font=self.f_mid, fg=self.FG,
                     bg=self.PANEL, anchor="w")
        v.pack(anchor="w")
        return v

    def _build_steering_command(self, parent):
        panel = self._section(parent, "STEERING COMMAND")
        # Mode tabs row
        modebar = tk.Frame(panel, bg=self.PANEL)
        modebar.pack(fill="x", padx=12, pady=(10, 4))
        self.btn_mode_slider = tk.Button(
            modebar, text="SLIDER", font=self.f_btn, width=12,
            relief="flat", bg=self.ACCENT, fg="white", padx=4, pady=6,
            command=lambda: self.set_mode(MODE_SLIDER))
        self.btn_mode_slider.pack(side="left", padx=(0, 6))
        self.btn_mode_keyboard = tk.Button(
            modebar, text="KEYBOARD", font=self.f_btn, width=12,
            relief="flat", bg="#525252", fg="white", padx=4, pady=6,
            command=lambda: self.set_mode(MODE_KEYBOARD))
        self.btn_mode_keyboard.pack(side="left", padx=4)
        tk.Button(modebar, text="CENTER (0)", font=self.f_btn, width=12,
                  relief="flat", bg="#525252", fg="white", padx=4, pady=6,
                  command=self.on_center).pack(side="right", padx=4)

        # Slider frame (default visible)
        self.frame_slider = tk.Frame(panel, bg=self.PANEL)
        sl = tk.Frame(self.frame_slider, bg=self.PANEL)
        sl.pack(fill="x", padx=12, pady=(8, 4))
        tk.Label(sl, text=f"−{HARD_ANGLE_LIMIT_DEG:.0f}",
                 font=self.f_mono, fg=self.DIM, bg=self.PANEL).pack(side="left")
        self.var_slider = tk.DoubleVar(value=0.0)
        self.slider = tk.Scale(sl, from_=-HARD_ANGLE_LIMIT_DEG,
                               to=HARD_ANGLE_LIMIT_DEG, resolution=0.5,
                               orient="horizontal", variable=self.var_slider,
                               command=self.on_slider, length=520,
                               bg=self.PANEL, fg=self.FG,
                               troughcolor=self.PANEL2,
                               highlightthickness=0, sliderrelief="flat",
                               showvalue=0)
        self.slider.pack(side="left", padx=10, fill="x", expand=True)
        tk.Label(sl, text=f"+{HARD_ANGLE_LIMIT_DEG:.0f}", font=self.f_mono,
                 fg=self.DIM, bg=self.PANEL).pack(side="left")

        entry_row = tk.Frame(self.frame_slider, bg=self.PANEL)
        entry_row.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(entry_row, text="Type angle (deg):", font=self.f_mid,
                 fg=self.DIM, bg=self.PANEL).pack(side="left")
        self.var_entry = tk.StringVar(value="0.0")
        ent = tk.Entry(entry_row, textvariable=self.var_entry,
                       font=self.f_mono, width=10,
                       bg=self.PANEL2, fg=self.FG,
                       insertbackground=self.FG, relief="flat")
        ent.pack(side="left", padx=8, ipady=3)
        ent.bind("<Return>", lambda e: self.on_set_entry())
        tk.Button(entry_row, text="SET", font=self.f_btn, bg=self.ACCENT,
                  fg="white", relief="flat", width=8, padx=4, pady=4,
                  command=self.on_set_entry).pack(side="left", padx=4)

        # Keyboard frame (hidden until KEYBOARD mode)
        self.frame_kbd = tk.Frame(panel, bg=self.PANEL)
        kb_inner = tk.Frame(self.frame_kbd, bg=self.PANEL)
        kb_inner.pack(fill="x", padx=12, pady=(8, 12))
        self.wheel = WheelCanvas(kb_inner, size=210, bg=self.PANEL)
        self.wheel.pack(side="left", padx=8)
        kb_help = tk.Frame(kb_inner, bg=self.PANEL)
        kb_help.pack(side="left", padx=14, anchor="n", pady=8)
        for line in (
            "LEFT / RIGHT arrow .... hold to steer",
            f"steer rate ............ {KEYBOARD_STEER_RATE_DEG_PER_SEC:.0f} deg/s",
            "SPACE ................. snap target to 0",
            "P / R / N / D ......... shift gear",
            "Q or ESC .............. E-STOP",
            "",
            "Click in the window if",
            "keys do not register.",
        ):
            tk.Label(kb_help, text=line, font=self.f_help,
                     fg=self.DIM, bg=self.PANEL,
                     anchor="w").pack(anchor="w")

        # Show slider mode by default.
        self.frame_slider.pack(fill="x")

    def _build_rack_status(self, parent):
        panel = self._section(parent, "RACK STATUS")
        g = tk.Frame(panel, bg=self.PANEL)
        g.pack(fill="x", padx=4, pady=4)
        for c in range(4):
            g.grid_columnconfigure(c, weight=1, minsize=140)
        self.lbl_eac    = self._stat(g, 0, 0, "EAC STATUS",   "SNA")
        self.lbl_err    = self._stat(g, 0, 1, "LAST ERROR",   "NONE")
        self.lbl_meas   = self._stat(g, 0, 2, "MEASURED",     "-- deg")
        self.lbl_cmd    = self._stat(g, 0, 3, "COMMANDED",    "-- deg")
        self.lbl_target = self._stat(g, 1, 0, "TARGET",       "0.0 deg")
        self.lbl_diverg = self._stat(g, 1, 1, "DIVERGENCE",   "0.0 deg")
        self.lbl_rx     = self._stat(g, 1, 2, "RX (0x370)",   "0")
        self.lbl_buserr = self._stat(g, 1, 3, "BUS ERRORS",   "0")

    def _build_vehicle_status(self, parent):
        panel = self._section(parent, "VEHICLE STATUS")
        g = tk.Frame(panel, bg=self.PANEL)
        g.pack(fill="x", padx=4, pady=4)
        for c in range(4):
            g.grid_columnconfigure(c, weight=1, minsize=140)
        self.lbl_gear     = self._stat(g, 0, 0, "GEAR",        "--")
        self.lbl_gear_req = self._stat(g, 0, 1, "GEAR REQ",    "--")
        self.lbl_brake    = self._stat(g, 0, 2, "BRAKE",       "--")
        self.lbl_brake_st = self._stat(g, 0, 3, "BRAKE STATE", "--")
        self.lbl_di_speed = self._stat(g, 1, 0, "DI SPEED",    "-- mph")
        self.lbl_park_gate= self._stat(g, 1, 1, "PARK GATE",
                                       "armed" if REQUIRE_PARK_TO_ENGAGE else "off")

    def _build_shift_panel(self, parent):
        panel = self._section(parent, "SHIFT GEAR (EXPERIMENTAL)")
        bar = tk.Frame(panel, bg=self.PANEL)
        bar.pack(fill="x", padx=12, pady=(8, 4))
        for label in ("P", "R", "N", "D"):
            btn = tk.Button(bar, text=label, font=self.f_btn,
                            width=8, relief="flat",
                            bg="#525252", fg="white", padx=4, pady=8,
                            command=lambda l=label: self.request_shift(l))
            btn.pack(side="left", padx=(0, 6))
            setattr(self, f"btn_shift_{label.lower()}", btn)
        tk.Label(panel,
                 text="brake required · real speed < 1 mph · "
                      "rack disengaged · no shift in flight",
                 font=self.f_help, fg=self.DIM, bg=self.PANEL,
                 anchor="w").pack(fill="x", padx=12, pady=(0, 10))

    def _build_bus_diagnostic(self, parent):
        panel = self._section(parent, "BUS DIAGNOSTIC")
        tk.Label(panel,
                 text="frame rates per ID · 0x488 RX must stay 0.0",
                 font=self.f_help, fg=self.DIM, bg=self.PANEL,
                 anchor="w").pack(fill="x", padx=12, pady=(8, 4))
        g = tk.Frame(panel, bg=self.PANEL)
        g.pack(fill="x", padx=12, pady=(0, 10))
        # Column widths so nothing clips
        g.grid_columnconfigure(0, minsize=58)
        g.grid_columnconfigure(1, minsize=64)
        g.grid_columnconfigure(2, minsize=64)
        g.grid_columnconfigure(3, weight=1)
        # Header row
        for col, txt, anchor in ((0, "ID",    "w"),
                                 (1, "Hz",    "e"),
                                 (2, "count", "e"),
                                 (3, "name",  "w")):
            tk.Label(g, text=txt, font=self.f_label,
                     fg=self.DIM, bg=self.PANEL, anchor=anchor).grid(
                row=0, column=col, sticky="ew", padx=(0, 8), pady=(0, 4))
        self.diag_labels = {}
        for row, (cid, name, _note) in enumerate(DIAG_IDS, start=1):
            tk.Label(g, text=f"0x{cid:03X}", font=self.f_mono,
                     fg=self.FG, bg=self.PANEL).grid(
                row=row, column=0, sticky="w", padx=(0, 8))
            lbl_hz   = tk.Label(g, text=" 0.0", font=self.f_mono,
                                fg=self.MUTE, bg=self.PANEL, anchor="e")
            lbl_cnt  = tk.Label(g, text="0", font=self.f_mono,
                                fg=self.MUTE, bg=self.PANEL, anchor="e")
            lbl_name = tk.Label(g, text=name, font=self.f_mono,
                                fg=self.DIM, bg=self.PANEL, anchor="w")
            lbl_hz.grid  (row=row, column=1, sticky="ew", padx=(0, 8))
            lbl_cnt.grid (row=row, column=2, sticky="ew", padx=(0, 8))
            lbl_name.grid(row=row, column=3, sticky="w")
            self.diag_labels[cid] = (lbl_hz, lbl_cnt, lbl_name)

    def _build_keepalives(self, parent):
        panel = self._section(parent, "KEEPALIVES WE SEND")
        inner = tk.Frame(panel, bg=self.PANEL)
        inner.pack(fill="x", padx=12, pady=(10, 4))
        # 4 lines: 0x488 always, 0x214, 0x101, 0x155
        for kid, label, default_on, rate in (
            (0x488, "DAS_steeringControl", True,            "50 Hz"),
            (0x214, "EPB_epasControl",     SYNTHESIZE_EPB,  "10 Hz"),
            (0x101, "GTW_epasControl",     SYNTHESIZE_GTW,  "20 Hz"),
            (0x155, "ESP_B fake speed",    False,           "200 Hz"),
        ):
            line = tk.Frame(inner, bg=self.PANEL)
            line.pack(fill="x", pady=2)
            dot = tk.Label(line, text="●" if default_on else "○",
                           font=self.f_pill,
                           fg=self.GREEN if default_on else self.MUTE,
                           bg=self.PANEL)
            dot.pack(side="left")
            tk.Label(line, text=f"  0x{kid:03X}  {label}",
                     font=self.f_mono, fg=self.FG, bg=self.PANEL,
                     anchor="w").pack(side="left")
            rate_lbl = tk.Label(line,
                                text=f"{rate} · ON" if default_on else rate,
                                font=self.f_mono,
                                fg=self.GREEN if default_on else self.DIM,
                                bg=self.PANEL)
            rate_lbl.pack(side="right", padx=8)
            self.kp_lines[kid] = (dot, rate_lbl)
        self.lbl_esp_warn = tk.Label(panel, text="", font=self.f_mono,
                                     fg=self.RED, bg=self.PANEL, anchor="w")
        self.lbl_esp_warn.pack(fill="x", padx=12, pady=(0, 8))

    def _build_event_log(self, parent):
        panel = self._section(parent, "EVENT LOG", expand=True)
        # Vertical scrollbar so older lines don't get hidden when the
        # log fills up.
        wrap = tk.Frame(panel, bg=self.PANEL)
        wrap.pack(fill="both", expand=True, padx=12, pady=10)
        scroll = tk.Scrollbar(wrap, bg=self.PANEL, troughcolor=self.PANEL2,
                              activebackground=self.DIM, relief="flat",
                              borderwidth=0, highlightthickness=0)
        scroll.pack(side="right", fill="y")
        self.txt_log = tk.Text(wrap, font=self.f_mono, bg=self.SUNKEN,
                               fg=self.FG, relief="flat", wrap="word",
                               insertbackground=self.FG, padx=8, pady=6,
                               highlightthickness=0,
                               height=24,             # decent minimum
                               yscrollcommand=scroll.set)
        self.txt_log.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.txt_log.yview)

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
            self.elapsed_start = time.monotonic()
            self._log_local(f"session started -> {self.logger.log_path}")
            self.worker = CanWorker(self.ctrl, self.status, self.stats,
                                    self.log_q, self.logger)
            self.worker.start()
            self.btn_conn.config(text="DISCONNECT", bg="#525252")
            self.btn_engage.config(state="normal")
            self.btn_save_test.config(state="normal")
        else:
            self.estop("disconnect requested")
            self.worker.stop()
            self.worker.join(timeout=2.0)
            self.worker = None
            self.elapsed_start = None
            if self.logger:
                self.logger.event("disconnect; closing log")
                self.logger.close()
                self._log_local(f"log saved: {self.logger.log_path}")
                self._log_local(f"csv  saved: {self.logger.csv_path}")
                self.logger = None
            self.btn_conn.config(text="CONNECT", bg=self.ACCENT)
            self.btn_engage.config(state="disabled", text="ENGAGE",
                                   bg=self.GREEN)
            self.btn_save_test.config(state="disabled")

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

    # ---------- Save Test to GitHub ----------

    def open_save_test_dialog(self):
        """Modal dialog: name + description, then export to GitHub."""
        if not self.logger:
            self._log_local("REFUSED save test: no active session (CONNECT first)")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Save Test to GitHub")
        dlg.configure(bg=self.BG)
        dlg.geometry("560x340")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="SAVE TEST TO GITHUB", font=self.f_section,
                 fg=self.DIM, bg=self.BG).pack(anchor="w", padx=20, pady=(20, 4))

        panel = tk.Frame(dlg, bg=self.PANEL,
                         highlightbackground=self.BORDER, highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        tk.Label(panel, text="TEST NAME (short, no spaces)",
                 font=self.f_label, fg=self.DIM, bg=self.PANEL,
                 anchor="w").pack(fill="x", padx=14, pady=(14, 2))
        default_name = f"test_{datetime.now().strftime('%H%M%S')}"
        name_var = tk.StringVar(value=default_name)
        name_ent = tk.Entry(panel, textvariable=name_var, font=self.f_mono,
                            bg=self.PANEL2, fg=self.FG,
                            insertbackground=self.FG, relief="flat")
        name_ent.pack(fill="x", padx=14, pady=(0, 10), ipady=5)

        tk.Label(panel,
                 text="DESCRIPTION (what was being tested, what happened)",
                 font=self.f_label, fg=self.DIM, bg=self.PANEL,
                 anchor="w").pack(fill="x", padx=14, pady=(6, 2))
        desc_txt = tk.Text(panel, font=self.f_mono, bg=self.PANEL2,
                           fg=self.FG, insertbackground=self.FG,
                           relief="flat", height=5, wrap="word",
                           padx=8, pady=4, highlightthickness=0)
        desc_txt.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        btns = tk.Frame(dlg, bg=self.BG)
        btns.pack(fill="x", padx=20, pady=(0, 20))

        def do_save():
            name = name_var.get().strip()
            if not name:
                return
            desc = desc_txt.get("1.0", "end").strip()
            dlg.destroy()
            self._do_save_test(name, desc)

        tk.Button(btns, text="Cancel", font=self.f_btn,
                  bg="#525252", fg="white", relief="flat",
                  padx=12, pady=8, width=10,
                  command=dlg.destroy).pack(side="right", padx=(8, 0))
        tk.Button(btns, text="SAVE", font=self.f_btn,
                  bg=self.GREEN, fg="white", relief="flat",
                  padx=12, pady=8, width=12,
                  command=do_save).pack(side="right")

        name_ent.focus_set()
        name_ent.select_range(0, "end")

    def _do_save_test(self, name: str, description: str):
        """Spin off the export in a background thread so the UI stays
        responsive during git operations."""
        self._log_local(f"saving test '{name}'...")
        threading.Thread(
            target=self._run_git_export, args=(name, description),
            daemon=True
        ).start()

    def _run_git_export(self, name: str, description: str):
        """Background-thread worker. Copies session files into the repo,
        writes a README, and tries git add+commit+push. All output is
        streamed back to the event log via self.log_q."""
        def emit(msg):
            self.log_q.put(f"[{time.strftime('%H:%M:%S')}] {msg}")

        safe_name = re.sub(r'[^a-zA-Z0-9_-]+', '_', name).strip('_')[:64]
        if not safe_name:
            safe_name = "unnamed"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{ts}_{safe_name}"

        repo_root = os.path.dirname(os.path.abspath(__file__))
        dest = os.path.join(repo_root, "field_testing", "sessions", folder_name)

        # ---- Copy session files ----
        try:
            os.makedirs(dest, exist_ok=True)
            if self.logger:
                self.logger.event(f"snapshot: saving as '{name}'")
                log_src = self.logger.log_path
                csv_src = self.logger.csv_path
                if os.path.exists(log_src):
                    shutil.copy2(log_src, os.path.join(dest, "session.log"))
                if os.path.exists(csv_src):
                    shutil.copy2(csv_src, os.path.join(dest, "session.csv"))
            readme_path = os.path.join(dest, "README.md")
            with open(readme_path, "w") as f:
                f.write(self._build_test_readme(name, description, folder_name))
            emit(f"saved files to field_testing/sessions/{folder_name}/")
        except Exception as e:
            emit(f"ERROR copying files: {e}")
            return

        # ---- git add ----
        rel_path = os.path.relpath(dest, repo_root)
        commit_msg = (f"test: {name}\n\n{description}"
                      if description else f"test: {name}")
        try:
            subprocess.run(["git", "add", rel_path], cwd=repo_root,
                           check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            emit(f"git add failed: {(e.stderr or '').strip() or e}")
            return
        except FileNotFoundError:
            emit("git not found in PATH; files saved but not committed")
            return

        # ---- git commit ----
        try:
            subprocess.run(["git", "commit", "-m", commit_msg],
                           cwd=repo_root, check=True,
                           capture_output=True, text=True)
            emit(f"git commit OK: 'test: {name}'")
        except subprocess.CalledProcessError as e:
            err = (e.stderr or e.stdout or "").strip()
            if "nothing to commit" in err:
                emit("git commit: nothing changed (already saved?)")
                return
            emit(f"git commit failed: {err}")
            return

        # ---- git push ----
        try:
            br = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                cwd=repo_root, check=True,
                                capture_output=True, text=True)
            branch = br.stdout.strip()
            subprocess.run(["git", "push", "origin", branch],
                           cwd=repo_root, check=True,
                           capture_output=True, text=True)
            emit(f"git push OK to origin/{branch}")
            emit(f"saved on GitHub: field_testing/sessions/{folder_name}/")
        except subprocess.CalledProcessError as e:
            err = (e.stderr or "").strip()
            emit(f"git push failed: {err}")
            emit(f"files committed locally; push manually with:")
            emit(f"  git push origin {branch}")

    def _build_test_readme(self, name: str, description: str, folder: str) -> str:
        s = self.status
        c = self.ctrl
        elapsed = (time.monotonic() - (self.elapsed_start or time.monotonic()))
        lines = [
            f"# {name}",
            "",
            f"**Saved:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Folder:** `field_testing/sessions/{folder}/`",
            f"**Program version:** v{__version__}",
            "",
            "## Description",
            "",
            description if description else "_(no description provided)_",
            "",
            "## Snapshot at save time",
            "",
            f"- Elapsed session time: {elapsed:.1f} s",
            f"- EAC status: `{EAC_STATUS_NAMES.get(s.eac_status, '?')}`",
            f"- Last EAC error: `{EAC_ERROR_CODES.get(s.eac_error_code, '?')}`",
            f"- Measured angle: {s.measured_angle_deg:+.1f} deg",
            f"- Commanded angle: {c.commanded_angle_deg:+.1f} deg",
            f"- 0x370 RX count: {s.rx_count}",
            f"- Bus errors: {c.bus_errors}",
            f"- Engaged: {c.engaged}",
            f"- 30 MPH MODE: {'ON' if c.thirty_mph_mode else 'off'}",
            f"- Mode: {c.mode}",
            "",
        ]
        if s.di_torque2_rx_count > 0:
            lines += [
                "## Vehicle state",
                "",
                f"- Gear: `{DI_GEAR_NAMES.get(s.gear, '?')}`",
                f"- Gear request: `{DI_GEAR_NAMES.get(s.gear_request, '?')}`",
                f"- Brake: `{'PRESSED' if s.brake_pedal == 1 else 'released'}`",
                f"- Brake state: `{DI_BRAKE_STATE_NAMES.get(s.brake_state, '?')}`",
                f"- DI vehicle speed: {s.di_vehicle_speed_mph:+.2f} mph",
                "",
            ]
        lines += [
            "## Files",
            "",
            "- `session.log` -- human-readable event timeline",
            "- `session.csv` -- per-frame state samples (open in Excel/pandas)",
            "",
            "## How to read",
            "",
            "See [docs/TROUBLESHOOTING.md](../../../docs/TROUBLESHOOTING.md)",
            "under \"Logs -- finding and reading them\" for the .log and",
            ".csv format.",
        ]
        return "\n".join(lines) + "\n"

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

    def request_shift(self, gear_label: str):
        """User clicked P / R / N / D. Validate gates, then queue
        the shift for the worker to execute.

        EXPERIMENTAL: this is the first shipped version of the
        0x6D SBW_RQ_SCCM transmission. The CRC and bit layout are
        based on opendbc's tesla_can.dbc and the Tesla CRC-8/AUTOSAR
        spec, but have not yet been verified against a real shift
        capture from this car. If the first attempt is silently
        ignored, run can_sniffer.py while shifting physically and
        compare bytes. See PROTOCOL.md.
        """
        if self.worker is None:
            self._log_local("REFUSED shift: not connected")
            return
        if self.ctrl.estop:
            self._log_local("REFUSED shift: E-STOP active")
            return
        if self.ctrl.engaged:
            # v4.3.3: shift while engaged is allowed. The non-blocking
            # 200 Hz burst from v4.2.1 keeps 0x488 keepalives flowing
            # during the shift, so the rack does not lose steering
            # control. Log it loud so the .log makes the gear change
            # easy to spot when reading later.
            self._log_local(f"SHIFT WHILE ENGAGED -> {gear_label}")
        if (self.ctrl.shift_target is not None
                or self.ctrl.shift_phase is not None):
            self._log_local("REFUSED shift: another shift is in flight")
            return

        # Brake-pressed gate (skip if no DI module on bus -- bench mode)
        if self.status.di_torque2_rx_count > 0:
            if self.status.brake_pedal != 1:
                self._log_local("REFUSED shift: brake pedal not pressed "
                                "(real Tesla shifts require brake)")
                return
            # Speed gate: refuse R or D if real motion present
            if (gear_label in ("R", "D")
                    and abs(self.status.di_vehicle_speed_mph)
                        > REAL_MOTION_AUTO_DISENGAGE_MPH):
                self._log_local(f"REFUSED shift to {gear_label}: real speed "
                                f"{self.status.di_vehicle_speed_mph:+.1f} mph "
                                "(must be < 1 mph)")
                return
        else:
            # On bench without DI, the shift will happen but we have no
            # way to verify it took. Log loudly.
            self._log_local("WARN: no DI on bus, shift will be sent blind "
                            "(no brake / speed check possible)")

        # Map label to (rnd_posn, p_pressed)
        # P button is special: TSL_P_Psd_StW=1, TSL_RND_Posn_StW stays IDLE.
        # R/N/D use TSL_RND_Posn_StW with the corresponding code.
        spec_map = {
            "P": (TSL_RND_IDLE,   TSL_P_PSD,  "P"),
            "R": (TSL_RND_R,      TSL_P_IDLE, "R"),
            "N": (TSL_RND_N_DOWN, TSL_P_IDLE, "N"),
            "D": (TSL_RND_D,      TSL_P_IDLE, "D"),
        }
        if gear_label not in spec_map:
            self._log_local(f"REFUSED shift: unknown gear {gear_label}")
            return
        self.ctrl.shift_target = spec_map[gear_label]
        self._log_local(f"shift queued: {gear_label} (worker will burst 0x6D)")
        if self.logger:
            self.logger.event(f"shift requested: {gear_label}")
            self.logger.sample(self.ctrl, self.status,
                               event=f"shift_requested:{gear_label}")

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
        # Drain worker log queue into the event log text widget.
        try:
            while True:
                line = self.log_q.get_nowait()
                self.txt_log.insert("end", line + "\n")
                self.txt_log.see("end")
        except queue.Empty:
            pass

        # ===== Vitals strip =====
        # LINK
        if self.worker is None:
            self._set_vital("link", "DISCONNECTED", self.RED)
        elif self.ctrl.estop:
            self._set_vital("link", "E-STOP", self.RED)
        elif self.status.rx_count == 0:
            self._set_vital("link", "WAITING", self.YELLOW)
        else:
            self._set_vital("link", "OK", self.GREEN)
        # EAC
        eac = self.status.eac_status
        eac_name = EAC_STATUS_NAMES.get(eac, "?")
        eac_color = {0: self.MUTE, 1: self.YELLOW, 2: self.GREEN,
                     3: self.RED, 4: self.MUTE}.get(eac, self.FG)
        self._set_vital("eac", eac_name, eac_color)
        # GEAR
        gear = self.status.gear
        if gear < 0:
            self._set_vital("gear", "(no DI)", self.MUTE)
        else:
            self._set_vital("gear", DI_GEAR_NAMES.get(gear, "?"),
                            {1: self.GREEN, 2: self.RED, 3: self.YELLOW,
                             4: self.RED}.get(gear, self.MUTE))
        # BRAKE
        brake = self.status.brake_pedal
        if brake < 0:
            self._set_vital("brake", "(no DI)", self.MUTE)
        elif brake == 1:
            self._set_vital("brake", "PRESSED", self.GREEN)
        else:
            self._set_vital("brake", "released", self.MUTE)
        # 30 MPH
        if self.ctrl.thirty_mph_mode:
            self._set_vital("mph30", "ON", self.ORANGE)
        else:
            self._set_vital("mph30", "off", self.MUTE)
        # SHIFT
        if self.ctrl.shift_target:
            _r, _p, lbl = self.ctrl.shift_target
            self._set_vital("shift", f"-> {lbl}", self.YELLOW)
        else:
            self._set_vital("shift", "idle", self.MUTE)

        # ===== Rack Status =====
        self.lbl_eac.config(text=eac_name, fg=eac_color)
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

        # ===== Vehicle Status =====
        if gear < 0:
            self.lbl_gear.config(text="(no DI)", fg=self.MUTE)
            self.lbl_gear_req.config(text="--", fg=self.MUTE)
            self.lbl_brake.config(text="--", fg=self.MUTE)
            self.lbl_brake_st.config(text="--", fg=self.MUTE)
            self.lbl_di_speed.config(text="-- mph", fg=self.MUTE)
        else:
            self.lbl_gear.config(
                text=DI_GEAR_NAMES.get(gear, "?"),
                fg={1: self.GREEN, 2: self.RED, 3: self.YELLOW,
                    4: self.RED}.get(gear, self.MUTE))
            req_name = DI_GEAR_NAMES.get(self.status.gear_request, "?")
            req_color = self.FG if self.status.gear_request == gear else self.YELLOW
            self.lbl_gear_req.config(text=req_name, fg=req_color)
            if self.status.brake_pedal == 1:
                self.lbl_brake.config(text="PRESSED", fg=self.GREEN)
            else:
                self.lbl_brake.config(text="released", fg=self.MUTE)
            self.lbl_brake_st.config(
                text=DI_BRAKE_STATE_NAMES.get(self.status.brake_state, "?"),
                fg=(self.GREEN if self.status.brake_state in (1, 3)
                    else self.DIM))
            speed_color = (self.RED
                           if abs(self.status.di_vehicle_speed_mph) > 1
                           else self.FG)
            self.lbl_di_speed.config(
                text=f"{self.status.di_vehicle_speed_mph:+.1f} mph",
                fg=speed_color)
        # Park gate
        if not REQUIRE_PARK_TO_ENGAGE:
            self.lbl_park_gate.config(text="off", fg=self.MUTE)
        elif self.status.di_torque2_rx_count == 0:
            self.lbl_park_gate.config(text="bypass", fg=self.YELLOW)
        elif self.status.gear == DI_GEAR_PARK:
            self.lbl_park_gate.config(text="OK (P)", fg=self.GREEN)
        else:
            self.lbl_park_gate.config(text="BLOCKED", fg=self.RED)

        # ===== Bus Diagnostic =====
        esp_contention = False
        for cid, (lbl_hz, lbl_cnt, _lbl_name) in self.diag_labels.items():
            hz = self.stats.hz(cid)
            cnt = self.stats.count(cid)
            color = self.MUTE if hz < 0.1 else self.GREEN
            if cid == 0x488 and hz > 0.1:
                color = self.RED   # second transmitter on the bus
            if (cid == 0x155 and self.ctrl.thirty_mph_mode
                    and hz > ESP_CONTENTION_RX_THRESHOLD_HZ):
                color = self.RED
                esp_contention = True
            lbl_hz.config(text=f"{hz:5.1f}", fg=color)
            lbl_cnt.config(text=str(cnt),
                           fg=self.DIM if cnt == 0 else self.FG)

        # ===== Keepalives panel: 0x155 dot reflects 30 MPH MODE state =====
        dot_155, rate_155 = self.kp_lines.get(0x155, (None, None))
        if dot_155:
            if self.ctrl.thirty_mph_mode:
                dot_155.config(text="●", fg=self.ORANGE)
                rate_155.config(text="200 Hz · ON", fg=self.ORANGE)
            else:
                dot_155.config(text="○", fg=self.MUTE)
                rate_155.config(text="200 Hz", fg=self.DIM)
        if esp_contention:
            self.lbl_esp_warn.config(
                text="! REAL ESP DETECTED -- contention with our 0x155")
        else:
            self.lbl_esp_warn.config(text="")

        # ===== Wheel canvas (KEYBOARD mode only) =====
        if self.ctrl.mode == MODE_KEYBOARD:
            if self.ctrl.key_left and not self.ctrl.key_right:
                wlabel = "<<<  STEERING LEFT"
            elif self.ctrl.key_right and not self.ctrl.key_left:
                wlabel = "STEERING RIGHT  >>>"
            else:
                wlabel = "HOLDING"
            self.wheel.draw(self.ctrl.commanded_angle_deg, label_below=wlabel)

        # ===== Button label sync (worker can change these) =====
        if not self.ctrl.engaged and self.btn_engage["text"] != "ENGAGE":
            self.btn_engage.config(text="ENGAGE", bg=self.GREEN)
        if (not self.ctrl.thirty_mph_mode
                and self.btn_30mph["text"] != "30 MPH MODE: OFF"):
            self.btn_30mph.config(text="30 MPH MODE: OFF", bg="#525252")

        # ===== Status bar =====
        if self.elapsed_start is None or self.worker is None:
            elapsed_str = "idle"
        else:
            elapsed_s = time.monotonic() - self.elapsed_start
            elapsed_str = (f"{int(elapsed_s // 60):02d}:"
                           f"{int(elapsed_s % 60):02d} elapsed")
        if self.logger:
            session_str = ("session: logs/"
                           + os.path.basename(self.logger.log_path)
                                 .replace(".log", ""))
        else:
            session_str = "session: not started"
        rack_str = ""
        if self.worker:
            rack_str = (" · rack "
                        + EAC_STATUS_NAMES.get(self.status.eac_status, "?"))
        self.lbl_statusbar.config(
            text=f"{session_str}{rack_str} · {elapsed_str}")

        self.after(50, self._tick)

    def _set_vital(self, key: str, value: str, color: str):
        dot, val = self.vitals[key]
        dot.config(fg=color)
        val.config(text=value, fg=color)


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
    print(f" EAC auto-disengage       : DISABLED (v5.0.4)")
    print(f" Log dir                  : {LOG_DIR}")
    print("=" * 72)


if __name__ == "__main__":
    banner()
    try:
        App().mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
