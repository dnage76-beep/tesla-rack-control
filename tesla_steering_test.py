"""
Tesla Model S (2013) steering rack test bench
=============================================

Direct-control GUI for commanding steering angles to a 2013 Tesla Model S
EPAS rack via a SYS TEC USB-CANmodul1 (model 3204001) on Windows.

PURPOSE
    Send DAS_steeringControl (0x488) and GTW_epasControl (0x101) on Tesla
    chassis CAN at 500 kbps. Listen for EPAS_sysStatus (0x370) feedback.
    Wrap everything in a tkinter GUI with rate limits, hard angle clamps,
    multiple independent failsafes, and a single big red E-STOP.

REQUIREMENTS
    pip install python-can

    SYS TEC driver: install the "sysWORXX USB-CAN Driver" from
    https://www.systec-electronic.com/en/services-support/downloads
    This installs USBCAN32.dll which python-can's `systec` backend uses.

USAGE
    python tesla_steering_test.py

    1. Click CONNECT. The status panel shows "EPAS link OK" once 0x370 is
       received. If you do not see 0x370 within ~2 seconds, you are on the
       wrong bus, wrong baud rate, or wrong pinout.
    2. Click ENGAGE. The rack should transition to ACTIVE.
    3. Move the slider OR type a number and press SET. The rack ramps to
       the target at the configured rate limit.
    4. E-STOP at any time: button, ESC key, or close the window.

SAFETY NOTES
    * First power-up: jack the front of the car off the ground OR disconnect
      tie rods. The rack can apply real force.
    * On the bench (engine off, no real ESP), the rack faults with
      EAC_ERROR_MIN_SPEED. Enable BENCH_MODE below to inject a fake speed
      message. In the car with ignition on, leave it off.
    * The hard angle limit defaults to +/- 90 degrees. Do not raise it
      until you have confirmed the rack tracks correctly.
    * The rate limit defaults to 50 deg/sec. The rack faults above ~250
      deg/sec at standstill, so 50 is well inside the safe envelope.

CAN PROTOCOL (from openpilot opendbc tesla_can.dbc, classic Model S fork)
    0x488 DAS_steeringControl  TX 100 Hz, 4 bytes
        b0 = (angle_raw >> 8) & 0x7F      angle_raw = (deg + 1638.35) * 10
        b1 = angle_raw & 0xFF
        b2 = (controlType << 6) | counter   controlType: 1=engage, 0=disable
        b3 = (0x88 + 0x04 + b0 + b1 + b2) & 0xFF
    0x101 GTW_epasControl  TX 10 Hz, 3 bytes
        b0 = (emergencyOn<<7) | (powerMode<<3) | tuneRequest   0x0A typical
        b1 = (controlType<<6) | (LDWenabled<<4) | counter      0x50 | ctr
        b2 = (0x01 + 0x01 + b0 + b1) & 0xFF
    0x370 EPAS_sysStatus  RX
        eacStatus at byte 6 bits 7..5: 0=INHIBITED 1=AVAILABLE 2=ACTIVE
                                       3=FAULT 4=SNA
        eacErrorCode at byte 2 bits 7..4

Author: Derek Nagel (with Claude)
Date: 2026-05-02
"""

import can
import time
import threading
import queue
import tkinter as tk
from tkinter import ttk, font
from dataclasses import dataclass, field
from typing import Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

# Hardware
CAN_BITRATE = 500_000           # Tesla chassis CAN
SYSTEC_DEVICE_NUMBER = 0        # First SYS TEC device on the system
SYSTEC_CHANNEL = 0              # CAN0 (USB-CANmodul1 has only one channel)

# Safety envelope (start conservative; do not raise until verified)
HARD_ANGLE_LIMIT_DEG = 90.0     # Refuses commands beyond this
MAX_RATE_DEG_PER_SEC = 50.0     # Ramp rate cap; rack faults > 250 deg/s
ANGLE_DIVERGENCE_LIMIT_DEG = 15.0  # commanded vs measured before E-STOP
RX_TIMEOUT_MS = 500             # Lose 0x370 for this long -> E-STOP
LOOP_OVERRUN_LIMIT_MS = 100     # 100 Hz loop overrun before E-STOP

# The 0x370 measured-angle decode is now verified against the DBC, but until
# you confirm on the bench that the GUI's "Measured Angle" tracks the real
# wheel position when turned by hand, leave the divergence trip OFF. After
# the passive-listen step shows correct angle tracking, flip to True.
DIVERGENCE_TRIP_ENABLED = False

# Bench mode: inject fake vehicle speed (0x155 ESP_B) so the rack runs its
# full-torque curve instead of the standstill curve. The rack scales torque
# output by speed; at 0 km/h it outputs ~30-40% to avoid fighting drivers.
#
# Per Derek's 2026-05-03 decision: enabled on Jordan's rig with wheels
# LOADED on ground (no jack stands). Risks acknowledged:
#   - tire scrub forces at standstill can stress tie rods and rack motor
#   - stock ESP module is also sending 0x155 -- our message contends with it
#   - instrument cluster may show a ghost speed
# Set BENCH_MODE = False after testing if you ever want to drive normally.
BENCH_MODE = True
BENCH_FAKE_SPEED_KPH = 30.0     # Above MIN_SPEED gate, below alarm thresholds

# IN_CAR_MODE: True if the rack is in the car with stock GTW and EPB modules on
# the bus (they will keep sending 0x101 and 0x214). False if the rack is on the
# bench with no GTW/EPB present.
#
# When True: this script does NOT send 0x101 or 0x214 -- the stock modules are
# already sending them, and after Greg Hogan's firmware patch the rack ignores
# their content anyway. Sending duplicates would create CAN bus contention.
#
# When False (bench): this script sends 0x101 and 0x214 itself with valid
# checksum and counter so the rack does not fault. Patched rack ignores values.
IN_CAR_MODE = True

# CAN IDs
ID_DAS_STEERING_CONTROL = 0x488   # TX 50 Hz (always)
ID_GTW_EPAS_CONTROL     = 0x101   # TX 20 Hz (only when IN_CAR_MODE=False)
ID_EPB_EPAS_CONTROL     = 0x214   # TX 10 Hz (only when IN_CAR_MODE=False)
ID_EPAS_SYS_STATUS      = 0x370   # RX
ID_ESP_B_FAKE_SPEED     = 0x155   # TX bench-mode only (ESP_B at ~50 Hz)

# Tx cycle periods
# DAS_steeringControl: matches BogGyver pre-AP fork (production reference)
#   at 50 Hz. Earlier draft had 100 Hz; that was incorrect.
# GTW_epasControl: stock Tesla GTW sends ~10 Hz with controlType=0. We send
#   at 20 Hz so our "WITH_ANGLE" frames outnumber the GTW's. If you fully
#   disconnect the GTW from the bus, 10 Hz is enough.
PERIOD_DAS_MS = 20              # 50 Hz (always)
PERIOD_GTW_MS = 50              # 20 Hz (only if IN_CAR_MODE=False)
PERIOD_EPB_MS = 100             # 10 Hz (only if IN_CAR_MODE=False)
PERIOD_ESP_MS = 20              # 50 Hz (only if BENCH_MODE)

# EAC error code lookup (from tesla_can.dbc)
EAC_ERROR_CODES = {
    0: "NONE",
    1: "MIN_SPEED",
    2: "MAX_SPEED",
    3: "HANDS_ON",
    4: "OUT_OF_RANGE",
    5: "OVER_TORQUE",
    6: "HIGH_ANGLE_REQ",
    7: "HIGH_ANGLE_RATE_REQ",
    8: "HIGH_TORQUE_REQ",
    9: "BLEND_REQ",
    10: "TIMEOUT",
    11: "ECU_FAULT",
    12: "BUS_FAULT",
    13: "INVALID_REQ",
    14: "EPB_INHIBIT",
    15: "SNA",
}

EAC_STATUS_NAMES = {
    0: "INHIBITED",
    1: "AVAILABLE",
    2: "ACTIVE",
    3: "FAULT",
    4: "SNA",
}


# ============================================================================
# CAN MESSAGE BUILDERS
# ============================================================================

def build_das_steering_control(angle_deg: float, control_type: int, counter: int) -> bytes:
    """0x488 DAS_steeringControl, 4 bytes.

    angle_deg: target wheel angle. Positive = left? right? depends on rack
        orientation. Confirm sign on first run with small commanded values.
    control_type: 1 = ANGLE_CONTROL (engaged), 0 = NONE (disengaged)
    counter: 0..15, must increment each frame
    """
    angle_raw = int(round((angle_deg + 1638.35) * 10.0))
    angle_raw = max(0, min(0x7FFF, angle_raw))   # 15-bit clamp
    b0 = (angle_raw >> 8) & 0x7F                 # MSB bit reserved for haptic
    b1 = angle_raw & 0xFF
    b2 = ((control_type & 0x03) << 6) | (counter & 0x0F)
    b3 = (0x88 + 0x04 + b0 + b1 + b2) & 0xFF
    return bytes([b0, b1, b2, b3])


def build_gtw_epas_control(counter: int, engaged: bool) -> bytes:
    """0x101 GTW_epasControl, 3 bytes.

    Sent at 20 Hz to keep the rack believing the gateway is alive and
    granting permission to steer. Stock GTW also sends 0x101 at ~10 Hz
    with controlType=0; we send faster so our WITH_ANGLE frames win.

    GTW_epasControlType values per tesla_can.dbc line 750:
      0 = WITHOUT, 1 = WITH_ANGLE, 2 = WITH_TORQUE, 3 = WITH_BOTH
    """
    emergency_on = 0
    power_mode = 1                 # DRIVE_ON
    tune_request = 2               # DM_STANDARD
    b0 = (emergency_on << 7) | (power_mode << 3) | (tune_request & 0x07)
    control_type = 1 if engaged else 0     # 1 = WITH_ANGLE
    ldw_enabled = 1 if engaged else 0
    b1 = ((control_type & 0x03) << 6) | ((ldw_enabled & 0x01) << 4) | (counter & 0x0F)
    b2 = (0x01 + 0x01 + b0 + b1) & 0xFF
    return bytes([b0, b1, b2])


def build_epb_epas_control(counter: int) -> bytes:
    """0x214 EPB_epasControl, 3 bytes.

    Per gregjhogan/tesla-pre-ap-epas-patch README: rack still requires this
    message on the bus with valid checksum and counter, even after firmware
    patch. Content (EPB_epasEACAllow) is ignored on patched rack.

    DBC layout (verified from tesla_can.dbc):
      EPB_epasEACAllow at byte 0 bits 7..5 (3 bits)
      EPB_epasControlCounter at byte 1 bits 3..0
      EPB_epasControlChecksum at byte 2

    Address contribution to checksum: 0x14 + 0x02 = 0x16.
    """
    eac_allow = 1   # ENABLE (ignored by patched rack but harmless)
    b0 = (eac_allow & 0x07) << 5
    b1 = counter & 0x0F
    b2 = (0x14 + 0x02 + b0 + b1) & 0xFF
    return bytes([b0, b1, b2])


def build_fake_esp_speed(speed_kph: float, counter: int) -> bytes:
    """0x155 ESP_B (bench-mode only). 8 bytes.

    Encoding from openpilot opendbc tesla_can.dbc ESP_B:
      ESP_vehicleSpeed at bits 24|13 LE, factor 0.04, offset -40 km/h.
    The rack uses this to gate min-speed-active behavior. NOT FULLY
    OEM-ACCURATE: counter / checksum / other signals are zeroed. Real
    Tesla bench tools do this and the rack accepts it for clearing
    EAC_ERROR_MIN_SPEED. If your rack rejects it, sniff the real bus
    and replicate exactly.
    """
    raw = int(round((speed_kph + 40.0) / 0.04))
    raw &= 0x1FFF
    data = bytearray(8)
    # bits 24..36 little-endian = bytes[3] low..bytes[4] high portion
    data[3] = raw & 0xFF
    data[4] = (raw >> 8) & 0x1F
    return bytes(data)


# ============================================================================
# STATE
# ============================================================================

@dataclass
class RackStatus:
    """Latest decoded EPAS_sysStatus (0x370) from the rack."""
    last_rx_monotonic: float = 0.0
    eac_status: int = 4            # SNA until proven otherwise
    eac_error_code: int = 0
    measured_angle_deg: float = 0.0
    rx_count: int = 0


@dataclass
class ControlState:
    target_angle_deg: float = 0.0   # what user typed / set on slider
    commanded_angle_deg: float = 0.0  # rate-limited actual command
    engaged: bool = False
    estop: bool = False
    estop_reason: str = ""
    counter_488: int = 0
    counter_101: int = 0
    counter_214: int = 0
    bus_errors: int = 0
    log_lines: list = field(default_factory=list)


# ============================================================================
# CAN WORKER THREAD
# ============================================================================

class CanWorker(threading.Thread):
    """Owns the CAN bus, runs the 100 Hz / 10 Hz / 50 Hz TX loops,
    and the RX decode of 0x370. Failsafes that need fast reaction
    (rx timeout, divergence, loop overrun) are checked here."""

    def __init__(self, ctrl: ControlState, status: RackStatus, log_q: queue.Queue):
        super().__init__(daemon=True)
        self.ctrl = ctrl
        self.status = status
        self.log_q = log_q
        self.bus: Optional[can.BusABC] = None
        self._stop = threading.Event()
        self._connected = threading.Event()

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_q.put(f"[{ts}] {msg}")

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
            self.log(f"CAN open: SYS TEC dev={SYSTEC_DEVICE_NUMBER} ch={SYSTEC_CHANNEL} {CAN_BITRATE//1000} kbps")
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

    def stop(self):
        self._stop.set()

    def _decode_0x370(self, data: bytes):
        """Decode EPAS_sysStatus.

        Bit positions verified against commaai/opendbc tesla_can.dbc lines
        121-126:
          eacStatus     : 55|3@0+   = byte 6 bits 7..5
          eacErrorCode  : 23|4@0+   = byte 2 bits 7..4 (upper nibble)
          internalSAS   : 37|14@0+  = big-endian, byte 4 bit 5 .. byte 5 bit 0
                          factor 0.1, offset -819.2, units deg
        """
        if len(data) < 8:
            return
        eac_status = (data[6] >> 5) & 0x07
        eac_err = (data[2] >> 4) & 0x0F
        # Big-endian (Motorola) 14-bit field starting at byte 4 bit 5.
        # That's bits 5..0 of byte 4 (top 6 bits) plus all of byte 5 (low 8 bits).
        raw = ((data[4] & 0x3F) << 8) | data[5]
        angle = raw * 0.1 - 819.2

        self.status.last_rx_monotonic = time.monotonic()
        self.status.eac_status = eac_status
        self.status.eac_error_code = eac_err
        self.status.measured_angle_deg = angle
        self.status.rx_count += 1

        if eac_status == 3:
            self.trigger_estop(f"rack FAULT, EAC_ERROR={EAC_ERROR_CODES.get(eac_err, '?')}")

    def _check_failsafes(self, now: float, last_loop: float):
        if self.ctrl.estop:
            return
        # RX timeout
        if self.status.rx_count > 0:
            since_rx_ms = (now - self.status.last_rx_monotonic) * 1000.0
            if since_rx_ms > RX_TIMEOUT_MS:
                self.trigger_estop(f"no 0x370 for {since_rx_ms:.0f} ms")
                return
        # Divergence (only when engaged, calibrated, and we have at least one rx)
        if (DIVERGENCE_TRIP_ENABLED and self.ctrl.engaged
                and self.status.rx_count > 5):
            err = abs(self.ctrl.commanded_angle_deg - self.status.measured_angle_deg)
            if err > ANGLE_DIVERGENCE_LIMIT_DEG:
                self.trigger_estop(
                    f"angle divergence {err:.1f} deg "
                    f"(cmd {self.ctrl.commanded_angle_deg:+.1f} vs meas {self.status.measured_angle_deg:+.1f})"
                )
                return
        # Loop overrun
        if last_loop > 0:
            dt_ms = (now - last_loop) * 1000.0
            if dt_ms > (PERIOD_DAS_MS + LOOP_OVERRUN_LIMIT_MS):
                self.trigger_estop(f"loop overrun {dt_ms:.0f} ms")
                return

    def _apply_rate_limit(self, dt_s: float):
        """Move commanded_angle toward target_angle, no faster than rate cap."""
        max_delta = MAX_RATE_DEG_PER_SEC * dt_s
        target = self.ctrl.target_angle_deg
        # Hard clamp the target as well
        target = max(-HARD_ANGLE_LIMIT_DEG, min(HARD_ANGLE_LIMIT_DEG, target))
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

            # RX drain (non-blocking)
            try:
                while True:
                    msg = self.bus.recv(timeout=0)
                    if msg is None:
                        break
                    if msg.is_error_frame:
                        self.ctrl.bus_errors += 1
                        if self.ctrl.bus_errors > 50:
                            self.trigger_estop(f"bus error count {self.ctrl.bus_errors}")
                        continue
                    if msg.arbitration_id == ID_EPAS_SYS_STATUS:
                        self._decode_0x370(msg.data)
            except Exception as e:
                self.trigger_estop(f"RX exception: {e}")

            self._check_failsafes(now, last_loop)
            last_loop = now

            # E-STOP path: send a few disengage frames then idle
            if self.ctrl.estop:
                # Hold the last commanded angle (do NOT snap to measured, which
                # may be a stale 0 if RX never came up). Rack ignores angle
                # when controlType=0 anyway; this just avoids a confusing jump
                # if the user re-engages.
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

            # Apply rate limit
            dt = PERIOD_DAS_MS / 1000.0
            self._apply_rate_limit(dt)

            # 100 Hz: 0x488
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

            # 0x101 GTW_epasControl -- ONLY in bench mode (rack out of car)
            # In car: stock GTW is sending this, do not contend.
            if not IN_CAR_MODE and now >= next_gtw:
                try:
                    data = build_gtw_epas_control(self.ctrl.counter_101, self.ctrl.engaged)
                    self.bus.send(can.Message(
                        arbitration_id=ID_GTW_EPAS_CONTROL,
                        data=data, is_extended_id=False,
                    ))
                    self.ctrl.counter_101 = (self.ctrl.counter_101 + 1) & 0x0F
                except Exception as e:
                    self.trigger_estop(f"TX 0x101 failed: {e}")
                next_gtw = now + PERIOD_GTW_MS / 1000.0

            # 0x214 EPB_epasControl -- ONLY in bench mode (rack out of car)
            # In car: stock EPB module is sending this. Patched rack ignores
            # the EAC_Allow value but requires the message present on the bus.
            if not IN_CAR_MODE and now >= next_epb:
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

            # 50 Hz: bench-mode fake speed
            if BENCH_MODE and now >= next_esp:
                try:
                    data = build_fake_esp_speed(BENCH_FAKE_SPEED_KPH, 0)
                    self.bus.send(can.Message(
                        arbitration_id=ID_ESP_B_FAKE_SPEED,
                        data=data, is_extended_id=False,
                    ))
                except Exception:
                    pass
                next_esp = now + PERIOD_ESP_MS / 1000.0

            # Sleep until next deadline
            deadlines = [next_das]
            if not IN_CAR_MODE:
                deadlines.extend([next_gtw, next_epb])
            if BENCH_MODE:
                deadlines.append(next_esp)
            sleep_until = min(deadlines)
            sleep_s = max(0.0, sleep_until - time.monotonic())
            if sleep_s > 0:
                time.sleep(min(sleep_s, 0.005))

        self.disconnect()


# ============================================================================
# GUI
# ============================================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tesla Model S Rack Test  --  v1.0")
        self.geometry("780x720")
        self.configure(bg="#1e1e1e")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Escape>", lambda e: self.estop("ESC key"))

        self.ctrl = ControlState()
        self.status = RackStatus()
        self.log_q: queue.Queue = queue.Queue()
        self.worker: Optional[CanWorker] = None

        self._build_styles()
        self._build_ui()
        self.after(50, self._tick)

    def _build_styles(self):
        self.f_h1 = font.Font(family="Segoe UI", size=18, weight="bold")
        self.f_h2 = font.Font(family="Segoe UI", size=12, weight="bold")
        self.f_mono_big = font.Font(family="Consolas", size=28, weight="bold")
        self.f_mono = font.Font(family="Consolas", size=10)
        self.f_btn = font.Font(family="Segoe UI", size=11, weight="bold")
        self.f_estop = font.Font(family="Segoe UI", size=18, weight="bold")

    def _build_ui(self):
        BG = "#1e1e1e"
        FG = "#e0e0e0"
        PANEL = "#2a2a2a"
        ACCENT = "#3b82f6"

        # ---------- Header ----------
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(hdr, text="Tesla Model S Steering Rack Test",
                 font=self.f_h1, fg=FG, bg=BG).pack(side="left")

        self.lbl_conn = tk.Label(hdr, text="DISCONNECTED",
                                 font=self.f_h2, fg="#ef4444", bg=BG)
        self.lbl_conn.pack(side="right")

        # ---------- Connection bar ----------
        bar = tk.Frame(self, bg=PANEL)
        bar.pack(fill="x", padx=16, pady=4)
        self.btn_conn = tk.Button(bar, text="CONNECT", font=self.f_btn,
                                  bg=ACCENT, fg="white", width=14,
                                  relief="flat", command=self.toggle_connect)
        self.btn_conn.pack(side="left", padx=8, pady=8)

        self.btn_engage = tk.Button(bar, text="ENGAGE", font=self.f_btn,
                                    bg="#16a34a", fg="white", width=14,
                                    relief="flat", state="disabled",
                                    command=self.toggle_engage)
        self.btn_engage.pack(side="left", padx=8, pady=8)

        self.btn_estop = tk.Button(bar, text="E - STOP   (ESC)", font=self.f_estop,
                                   bg="#dc2626", fg="white", width=18,
                                   relief="flat", command=lambda: self.estop("button"))
        self.btn_estop.pack(side="right", padx=8, pady=8)

        # ---------- Status panel ----------
        sp = tk.LabelFrame(self, text=" Rack Status ", font=self.f_h2,
                           fg=FG, bg=PANEL, bd=1, relief="solid")
        sp.pack(fill="x", padx=16, pady=8)

        grid = tk.Frame(sp, bg=PANEL)
        grid.pack(fill="x", padx=12, pady=10)
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1)

        self.lbl_eac = self._stat(grid, 0, 0, "EAC Status", "SNA")
        self.lbl_err = self._stat(grid, 0, 1, "Last Error", "NONE")
        self.lbl_meas = self._stat(grid, 0, 2, "Measured Angle", "-- deg")
        self.lbl_cmd = self._stat(grid, 0, 3, "Commanded", "-- deg")
        self.lbl_rx = self._stat(grid, 1, 0, "0x370 RX", "0")
        self.lbl_target = self._stat(grid, 1, 1, "Target", "0.0 deg")
        self.lbl_diverg = self._stat(grid, 1, 2, "Divergence", "0.0 deg")
        self.lbl_buserr = self._stat(grid, 1, 3, "Bus Errors", "0")

        # ---------- Control panel ----------
        cp = tk.LabelFrame(self, text=" Steering Command ", font=self.f_h2,
                           fg=FG, bg=PANEL, bd=1, relief="solid")
        cp.pack(fill="x", padx=16, pady=8)

        sl = tk.Frame(cp, bg=PANEL)
        sl.pack(fill="x", padx=12, pady=10)

        tk.Label(sl, text=f"-{HARD_ANGLE_LIMIT_DEG:.0f}",
                 font=self.f_mono, fg=FG, bg=PANEL).pack(side="left")
        self.var_slider = tk.DoubleVar(value=0.0)
        self.slider = tk.Scale(sl, from_=-HARD_ANGLE_LIMIT_DEG,
                               to=HARD_ANGLE_LIMIT_DEG, resolution=0.5,
                               orient="horizontal", variable=self.var_slider,
                               command=self.on_slider, length=560,
                               bg=PANEL, fg=FG, troughcolor="#404040",
                               highlightthickness=0, sliderrelief="flat",
                               showvalue=0)
        self.slider.pack(side="left", padx=10, fill="x", expand=True)
        tk.Label(sl, text=f"+{HARD_ANGLE_LIMIT_DEG:.0f}",
                 font=self.f_mono, fg=FG, bg=PANEL).pack(side="left")

        entry_row = tk.Frame(cp, bg=PANEL)
        entry_row.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(entry_row, text="Type angle (deg):",
                 font=self.f_h2, fg=FG, bg=PANEL).pack(side="left")
        self.var_entry = tk.StringVar(value="0.0")
        ent = tk.Entry(entry_row, textvariable=self.var_entry,
                       font=self.f_mono, width=10, bg="#1a1a1a", fg=FG,
                       insertbackground=FG, relief="flat")
        ent.pack(side="left", padx=8)
        ent.bind("<Return>", lambda e: self.on_set_entry())
        tk.Button(entry_row, text="SET", font=self.f_btn, bg=ACCENT, fg="white",
                  relief="flat", width=8,
                  command=self.on_set_entry).pack(side="left", padx=4)
        tk.Button(entry_row, text="CENTER (0)", font=self.f_btn,
                  bg="#525252", fg="white", relief="flat", width=12,
                  command=self.on_center).pack(side="left", padx=4)

        info = (f"Limits: +/- {HARD_ANGLE_LIMIT_DEG:.0f} deg, "
                f"max rate {MAX_RATE_DEG_PER_SEC:.0f} deg/s, "
                f"divergence trip {ANGLE_DIVERGENCE_LIMIT_DEG:.0f} deg")
        tk.Label(cp, text=info, font=self.f_mono,
                 fg="#9ca3af", bg=PANEL).pack(anchor="w", padx=14, pady=(0, 8))

        # ---------- Log ----------
        lp = tk.LabelFrame(self, text=" Event Log ", font=self.f_h2,
                           fg=FG, bg=PANEL, bd=1, relief="solid")
        lp.pack(fill="both", expand=True, padx=16, pady=(8, 14))
        self.txt_log = tk.Text(lp, font=self.f_mono, bg="#0f0f0f", fg=FG,
                               relief="flat", wrap="word", height=10)
        self.txt_log.pack(fill="both", expand=True, padx=8, pady=8)
        self._log_local("ready. click CONNECT to open the SYS TEC adapter.")

    def _stat(self, parent, row, col, label, value):
        cell = tk.Frame(parent, bg="#2a2a2a")
        cell.grid(row=row, column=col, sticky="nsew", padx=6, pady=4)
        tk.Label(cell, text=label, font=self.f_mono, fg="#9ca3af",
                 bg="#2a2a2a").pack(anchor="w")
        v = tk.Label(cell, text=value, font=self.f_mono_big, fg="#e0e0e0",
                     bg="#2a2a2a")
        v.pack(anchor="w")
        return v

    # ---------- Actions ----------

    def toggle_connect(self):
        if self.worker is None:
            self.worker = CanWorker(self.ctrl, self.status, self.log_q)
            self.worker.start()
            self.btn_conn.config(text="DISCONNECT", bg="#525252")
            self.btn_engage.config(state="normal")
            self.lbl_conn.config(text="CONNECTING...", fg="#eab308")
        else:
            self.estop("disconnect requested")
            self.worker.stop()
            self.worker.join(timeout=2.0)
            self.worker = None
            self.btn_conn.config(text="CONNECT", bg="#3b82f6")
            self.btn_engage.config(state="disabled", text="ENGAGE", bg="#16a34a")
            self.lbl_conn.config(text="DISCONNECTED", fg="#ef4444")

    def toggle_engage(self):
        if self.ctrl.estop:
            self._log_local("clear E-STOP first (reconnect to reset)")
            return
        if not self.ctrl.engaged:
            if self.status.rx_count == 0:
                self._log_local("REFUSED: no 0x370 yet, cannot engage blind")
                return
            self.ctrl.commanded_angle_deg = self.status.measured_angle_deg
            self.ctrl.target_angle_deg = self.status.measured_angle_deg
            self.var_slider.set(self.status.measured_angle_deg)
            self.ctrl.engaged = True
            self.btn_engage.config(text="DISENGAGE", bg="#ea580c")
            self._log_local(f"ENGAGED at {self.status.measured_angle_deg:+.1f} deg")
        else:
            self.ctrl.engaged = False
            self.btn_engage.config(text="ENGAGE", bg="#16a34a")
            self._log_local("DISENGAGED")

    def on_slider(self, val):
        if self.ctrl.estop:
            return
        try:
            v = float(val)
            self.ctrl.target_angle_deg = max(-HARD_ANGLE_LIMIT_DEG,
                                             min(HARD_ANGLE_LIMIT_DEG, v))
            self.var_entry.set(f"{self.ctrl.target_angle_deg:.1f}")
        except ValueError:
            pass

    def on_set_entry(self):
        if self.ctrl.estop:
            return
        try:
            v = float(self.var_entry.get())
        except ValueError:
            self._log_local("bad number")
            return
        if abs(v) > HARD_ANGLE_LIMIT_DEG:
            self._log_local(f"REFUSED: {v:.1f} exceeds +/- {HARD_ANGLE_LIMIT_DEG:.0f}")
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

    def estop(self, reason: str):
        if self.worker:
            self.worker.trigger_estop(reason)
        else:
            self.ctrl.estop = True
            self.ctrl.estop_reason = reason

    def on_close(self):
        self.estop("window closed")
        if self.worker:
            self.worker.stop()
            self.worker.join(timeout=2.0)
        self.destroy()

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
            self.lbl_conn.config(text="DISCONNECTED", fg="#ef4444")
        elif self.ctrl.estop:
            self.lbl_conn.config(text=f"E-STOP: {self.ctrl.estop_reason}",
                                 fg="#ef4444")
        elif self.status.rx_count == 0:
            self.lbl_conn.config(text="WAITING FOR 0x370...", fg="#eab308")
        else:
            self.lbl_conn.config(text="EPAS LINK OK", fg="#22c55e")

        # Status readouts
        eac = self.status.eac_status
        eac_name = EAC_STATUS_NAMES.get(eac, "?")
        eac_color = {0: "#9ca3af", 1: "#eab308", 2: "#22c55e",
                     3: "#ef4444", 4: "#9ca3af"}.get(eac, "#e0e0e0")
        self.lbl_eac.config(text=eac_name, fg=eac_color)

        err_name = EAC_ERROR_CODES.get(self.status.eac_error_code, "?")
        self.lbl_err.config(text=err_name,
                            fg="#ef4444" if self.status.eac_error_code else "#22c55e")

        self.lbl_meas.config(text=f"{self.status.measured_angle_deg:+.1f} deg")
        self.lbl_cmd.config(text=f"{self.ctrl.commanded_angle_deg:+.1f} deg")
        self.lbl_target.config(text=f"{self.ctrl.target_angle_deg:+.1f} deg")
        self.lbl_rx.config(text=str(self.status.rx_count))
        diverg = abs(self.ctrl.commanded_angle_deg - self.status.measured_angle_deg)
        d_color = "#ef4444" if diverg > ANGLE_DIVERGENCE_LIMIT_DEG * 0.6 else "#e0e0e0"
        self.lbl_diverg.config(text=f"{diverg:.1f} deg", fg=d_color)
        self.lbl_buserr.config(text=str(self.ctrl.bus_errors),
                               fg="#ef4444" if self.ctrl.bus_errors else "#e0e0e0")

        if self.ctrl.estop and self.btn_engage["text"] != "ENGAGE":
            self.btn_engage.config(text="ENGAGE", bg="#16a34a")

        self.after(50, self._tick)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print(" Tesla Model S rack test bench")
    print(" SYS TEC USB-CANmodul1 (3204001) on Windows")
    print("=" * 70)
    print(f" Bitrate: {CAN_BITRATE} bps")
    print(f" Hard angle limit:    +/- {HARD_ANGLE_LIMIT_DEG:.0f} deg")
    print(f" Max rate:            {MAX_RATE_DEG_PER_SEC:.0f} deg/sec")
    print(f" Divergence trip:     {ANGLE_DIVERGENCE_LIMIT_DEG:.0f} deg")
    print(f" RX timeout trip:     {RX_TIMEOUT_MS} ms")
    print(f" Bench mode:          {BENCH_MODE}")
    print("=" * 70)
    App().mainloop()
