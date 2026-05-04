"""
steer.py -- live keyboard-controlled steering with GUI
=======================================================

Run:    python steer.py
Effect: A small dark window opens. Click anywhere in the window to give
        it focus, then:
          LEFT arrow  -- steer left  (target decreases)
          RIGHT arrow -- steer right (target increases)
          SPACE       -- snap target to 0
          Q or ESC    -- disengage and exit
        Hold the arrow keys to steer continuously, release to hold.

What this is:
    Like move.py (one-shot CLI angle command) and tesla_steering_test.py
    (the full GUI with sliders, status panel, failsafes), but designed
    for live keyboard driving. A simple GUI shows you a steering-wheel
    icon that rotates with the commanded angle, plus a numeric readout.

REQUIREMENTS
    pip install python-can
    SYS TEC sysWORXX USB-CAN driver installed (Windows only)
    Front wheels OFF the ground (jack stands or tie rods disconnected)
    EPAS rack already firmware-patched
    Adapter wired:
       SYS TEC pin 7 -> OBD-II pin 1 (CH+)
       SYS TEC pin 2 -> OBD-II pin 9 (CH-)
       SYS TEC pin 3 -> OBD-II pin 4 (GND)
    Tesla in Drive Ready (key in, brake pressed)

NO admin / keyboard package needed. We use Tkinter's <KeyPress>/<KeyRelease>
events, which work in-window without any extra libraries.

CAN PROTOCOL
    See move.py header for the full DAS_steeringControl byte layout and
    checksum derivation. We send 0x488 at 50 Hz with a 4-bit incrementing
    counter and the standard Tesla checksum.

Author: Derek Nagel (with Claude Sonnet 4.6)
Date: 2026-05-04
"""

import can
import time
import threading
import math
import tkinter as tk
from tkinter import font


# ============================================================================
# CONFIG
# ============================================================================

CAN_BITRATE = 500_000
SYSTEC_DEVICE = 0
SYSTEC_CHANNEL = 0
SEND_RATE_HZ = 50
SEND_PERIOD_S = 1.0 / SEND_RATE_HZ

TURN_RATE_DEG_PER_SEC = 30.0     # how fast target moves while arrow held
HARD_ANGLE_LIMIT_DEG = 60.0      # standstill-safe envelope
RAMP_TAU_S = 0.20                # LPF time-constant for smoothness


# ============================================================================
# SHARED STATE
# ============================================================================

class State:
    target = 0.0          # degrees, moves with arrow keys
    filtered = 0.0        # LPF-smoothed angle (what we actually command)
    measured = 0.0        # last decoded measured angle from 0x370
    eac_status = 4        # 0..4
    eac_error = 0         # 0..15
    rx_count = 0
    bus_errors = 0
    going_left = False
    going_right = False
    estop = False
    estop_reason = ""
    counter = 0
    counter_ok = False    # True once first 0x370 received

    # commanded_angle is what we just sent (for the steering-wheel display)
    @classmethod
    def commanded(cls):
        return cls.filtered


EAC_STATUS_NAMES = {0: "INHIBITED", 1: "AVAILABLE", 2: "ACTIVE",
                    3: "FAULT", 4: "SNA"}
EAC_ERROR_NAMES = ["NONE", "MIN_SPEED", "MAX_SPEED", "HANDS_ON",
                   "OUT_OF_RANGE", "OVER_TORQUE", "HIGH_ANGLE_REQ",
                   "HIGH_ANGLE_RATE_REQ", "HIGH_TORQUE_REQ", "BLEND_REQ",
                   "TIMEOUT", "ECU_FAULT", "BUS_FAULT", "INVALID_REQ",
                   "EPB_INHIBIT", "SNA"]


# ============================================================================
# CAN FRAME BUILDER
# ============================================================================

def build_488(angle_deg, ctype, ctr):
    raw = int(round((angle_deg + 1638.35) * 10.0))
    raw = max(0, min(0x7FFF, raw))
    b0 = (raw >> 8) & 0x7F
    b1 = raw & 0xFF
    b2 = ((ctype & 0x03) << 6) | (ctr & 0x0F)
    b3 = (0x88 + 0x04 + b0 + b1 + b2) & 0xFF
    return [b0, b1, b2, b3]


def decode_370(data):
    """Return (eac_status, eac_error, measured_angle) from an 8-byte 0x370."""
    if len(data) < 8:
        return None
    eac_status = (data[6] >> 5) & 0x07
    eac_err = (data[2] >> 4) & 0x0F
    raw = ((data[4] & 0x3F) << 8) | data[5]
    angle = raw * 0.1 - 819.2
    return eac_status, eac_err, angle


# ============================================================================
# CAN WORKER THREAD
# ============================================================================

class Worker(threading.Thread):
    """Owns the bus. Runs the 50 Hz LPF + TX loop and drains 0x370 RX.
    Reads input flags from State.going_left/going_right (set by the GUI's
    key handlers). Writes State.filtered, State.measured, etc.
    """

    def __init__(self, log_callback):
        super().__init__(daemon=True)
        self.log = log_callback
        self._stop = threading.Event()
        self.bus = None

    def open(self):
        try:
            self.bus = can.Bus(
                interface="systec",
                channel=SYSTEC_CHANNEL,
                device_number=SYSTEC_DEVICE,
                bitrate=CAN_BITRATE,
                receive_own_messages=False,
            )
            self.log(f"CAN open at {CAN_BITRATE//1000} kbps")
            return True
        except Exception as e:
            self.log(f"CAN open FAILED: {e}")
            State.estop = True
            State.estop_reason = "bus open failed"
            return False

    def close(self):
        if self.bus is not None:
            try:
                self.bus.shutdown()
            except Exception:
                pass

    def stop(self):
        self._stop.set()

    def run(self):
        if not self.open():
            return

        ALPHA = SEND_PERIOD_S / (RAMP_TAU_S + SEND_PERIOD_S)
        next_send = time.monotonic()
        last_loop = next_send
        BUSY_WAIT_S = 0.002

        while not self._stop.is_set():
            now = time.monotonic()
            dt = now - last_loop
            last_loop = now

            # ---- RX drain ----
            try:
                while True:
                    msg = self.bus.recv(timeout=0)
                    if msg is None:
                        break
                    if msg.is_error_frame:
                        State.bus_errors += 1
                        continue
                    if msg.arbitration_id == 0x370:
                        decoded = decode_370(msg.data)
                        if decoded:
                            State.eac_status, State.eac_error, State.measured = decoded
                            State.rx_count += 1
            except Exception as e:
                self.log(f"RX exception: {e}")

            # ---- E-STOP check ----
            if State.estop:
                # Send a few disengage frames before giving up.
                try:
                    data = build_488(State.filtered, ctype=0, ctr=State.counter)
                    self.bus.send(can.Message(arbitration_id=0x488,
                                              data=data,
                                              is_extended_id=False))
                    State.counter = (State.counter + 1) & 0x0F
                except Exception:
                    pass
                time.sleep(0.02)
                continue

            # ---- INPUT (set by GUI key handlers) ----
            if State.going_left and not State.going_right:
                State.target -= TURN_RATE_DEG_PER_SEC * dt
            elif State.going_right and not State.going_left:
                State.target += TURN_RATE_DEG_PER_SEC * dt
            State.target = max(-HARD_ANGLE_LIMIT_DEG,
                               min(HARD_ANGLE_LIMIT_DEG, State.target))

            # ---- LPF ----
            State.filtered += ALPHA * (State.target - State.filtered)

            # ---- TX 0x488 ----
            try:
                data = build_488(State.filtered, ctype=1, ctr=State.counter)
                self.bus.send(can.Message(arbitration_id=0x488,
                                          data=data,
                                          is_extended_id=False))
                State.counter = (State.counter + 1) & 0x0F
            except Exception as e:
                self.log(f"TX 0x488 failed: {e}")
                State.estop = True
                State.estop_reason = "TX failed"
                continue

            # ---- 50 Hz hybrid sleep ----
            next_send += SEND_PERIOD_S
            sleep_s = next_send - time.monotonic()
            if sleep_s > BUSY_WAIT_S:
                time.sleep(sleep_s - BUSY_WAIT_S)
            while time.monotonic() < next_send:
                pass

        self.close()


# ============================================================================
# GUI
# ============================================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("steer.py -- live keyboard control")
        self.geometry("520x620")
        self.configure(bg="#0f0f10")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Fonts
        self.f_h1 = font.Font(family="Segoe UI", size=18, weight="bold")
        self.f_h2 = font.Font(family="Segoe UI", size=11, weight="bold")
        self.f_big = font.Font(family="Consolas", size=28, weight="bold")
        self.f_mid = font.Font(family="Consolas", size=12)
        self.f_small = font.Font(family="Consolas", size=9)
        self.f_help = font.Font(family="Segoe UI", size=10)

        self._build_ui()

        # Key handlers. Bound to the window so they fire as long as the
        # window has focus (no admin needed).
        self.bind("<KeyPress-Left>", self._key_left_down)
        self.bind("<KeyRelease-Left>", self._key_left_up)
        self.bind("<KeyPress-Right>", self._key_right_down)
        self.bind("<KeyRelease-Right>", self._key_right_up)
        self.bind("<KeyPress-space>", self._key_space)
        self.bind("<KeyPress-Escape>", lambda e: self.estop("ESC"))
        self.bind("<KeyPress-q>", lambda e: self.estop("Q"))

        # Force focus so keys register without clicking
        self.focus_force()

        # Start worker
        self.worker = Worker(self._log)
        self.worker.start()

        # Schedule UI tick
        self.after(40, self._tick)

    # ---------- UI ----------

    def _build_ui(self):
        BG = "#0f0f10"
        PANEL = "#1c1c1f"
        FG = "#e8e8e8"
        DIM = "#7a7a7a"
        ACCENT = "#3b82f6"

        # --- Title bar ---
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(hdr, text="LIVE KEYBOARD STEERING",
                 font=self.f_h1, fg=FG, bg=BG).pack(side="left")
        self.lbl_status = tk.Label(hdr, text="OPENING...",
                                   font=self.f_h2, fg="#eab308", bg=BG)
        self.lbl_status.pack(side="right")

        # --- Steering wheel canvas ---
        wheel_frame = tk.Frame(self, bg=PANEL)
        wheel_frame.pack(fill="x", padx=14, pady=8)
        self.canvas = tk.Canvas(wheel_frame, width=300, height=300,
                                bg=PANEL, highlightthickness=0)
        self.canvas.pack(pady=12)

        # The steering wheel itself (rim, hub, spokes, indicator) drawn by tick

        # --- Numeric readouts ---
        nums = tk.Frame(self, bg=PANEL)
        nums.pack(fill="x", padx=14, pady=(0, 8))
        self.lbl_cmd = self._readout(nums, "COMMANDED", "+0.0 deg", row=0, col=0, big=True)
        self.lbl_meas = self._readout(nums, "MEASURED", "+0.0 deg", row=0, col=1)
        self.lbl_eac = self._readout(nums, "EAC", "SNA", row=1, col=0)
        self.lbl_err = self._readout(nums, "ERROR", "NONE", row=1, col=1)
        for c in (0, 1):
            nums.grid_columnconfigure(c, weight=1)

        # --- Help text ---
        help_frame = tk.Frame(self, bg=BG)
        help_frame.pack(fill="x", padx=14, pady=(4, 4))
        help_lines = [
            "  LEFT / RIGHT arrow ........ steer (hold for continuous)",
            "  SPACE ..................... snap target to 0 (center)",
            "  Q or ESC .................. disengage and exit",
            "  Click in the window if keys don't respond",
        ]
        for line in help_lines:
            tk.Label(help_frame, text=line, font=self.f_small,
                     fg=DIM, bg=BG, anchor="w").pack(fill="x")

        # --- Log line (compact) ---
        log_frame = tk.Frame(self, bg=PANEL)
        log_frame.pack(fill="x", padx=14, pady=(8, 12))
        self.lbl_log = tk.Label(log_frame, text="opening adapter...",
                                font=self.f_small, fg="#9ca3af", bg=PANEL,
                                anchor="w", padx=10, pady=8)
        self.lbl_log.pack(fill="x")

    def _readout(self, parent, label, value, row, col, big=False):
        cell = tk.Frame(parent, bg="#1c1c1f")
        cell.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        tk.Label(cell, text=label, font=self.f_small, fg="#7a7a7a",
                 bg="#1c1c1f").pack(anchor="w", padx=10, pady=(8, 0))
        v = tk.Label(cell, text=value,
                     font=self.f_big if big else self.f_mid,
                     fg="#e8e8e8", bg="#1c1c1f")
        v.pack(anchor="w", padx=10, pady=(0, 8))
        return v

    # ---------- Wheel drawing ----------

    def _draw_wheel(self, angle_deg):
        """Draw a stylized steering wheel rotated by angle_deg.
        Positive = right (per Jordan's confirmed sign convention)."""
        c = self.canvas
        c.delete("all")
        cx, cy, r = 150, 150, 110

        # Outer rim
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      outline="#475569", width=8)

        # Inner rim shading
        c.create_oval(cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8,
                      outline="#334155", width=2)

        # Spokes (rotated by the angle). 3 spokes at 90, 210, 330 (T config).
        ang_rad = math.radians(angle_deg)
        for spoke_deg in (90, 210, 330):
            rad = math.radians(spoke_deg) + ang_rad
            x2 = cx + (r - 12) * math.cos(rad)
            y2 = cy - (r - 12) * math.sin(rad)
            c.create_line(cx, cy, x2, y2, fill="#64748b", width=6,
                          capstyle=tk.ROUND)

        # Center hub
        c.create_oval(cx - 22, cy - 22, cx + 22, cy + 22,
                      fill="#1f2937", outline="#475569", width=2)

        # Top indicator (so you can see the rotation clearly)
        rad_top = math.radians(90) + ang_rad
        x_top = cx + (r - 12) * math.cos(rad_top)
        y_top = cy - (r - 12) * math.sin(rad_top)
        c.create_oval(x_top - 8, y_top - 8, x_top + 8, y_top + 8,
                      fill="#3b82f6", outline="")

        # Angle text in the hub
        c.create_text(cx, cy, text=f"{angle_deg:+.0f}",
                      fill="#e8e8e8",
                      font=("Consolas", 14, "bold"))

        # Direction arrow at the bottom of the canvas
        arrow_y = 280
        if State.going_left and not State.going_right:
            c.create_text(cx, arrow_y, text="< < <  STEERING LEFT",
                          fill="#fbbf24", font=("Segoe UI", 11, "bold"))
        elif State.going_right and not State.going_left:
            c.create_text(cx, arrow_y, text="STEERING RIGHT  > > >",
                          fill="#fbbf24", font=("Segoe UI", 11, "bold"))
        else:
            c.create_text(cx, arrow_y, text="HOLDING",
                          fill="#7a7a7a", font=("Segoe UI", 10))

    # ---------- Key handlers ----------

    def _key_left_down(self, _):  State.going_left = True
    def _key_left_up(self, _):    State.going_left = False
    def _key_right_down(self, _): State.going_right = True
    def _key_right_up(self, _):   State.going_right = False

    def _key_space(self, _):
        State.target = 0.0

    def estop(self, reason):
        if not State.estop:
            State.estop = True
            State.estop_reason = reason
            self._log(f"E-STOP: {reason}")
        # Schedule clean exit
        self.after(300, self.on_close)

    # ---------- UI tick ----------

    def _log(self, msg):
        # Called from worker thread -- safe with single Tk widget update via after()
        ts = time.strftime("%H:%M:%S")
        self.after(0, lambda: self.lbl_log.config(text=f"[{ts}] {msg}"))

    def _tick(self):
        # Wheel
        self._draw_wheel(State.commanded())

        # Numeric panels
        self.lbl_cmd.config(text=f"{State.commanded():+5.1f} deg")
        self.lbl_meas.config(text=f"{State.measured:+5.1f} deg")
        eac_name = EAC_STATUS_NAMES.get(State.eac_status, "?")
        eac_color = {0: "#9ca3af", 1: "#eab308", 2: "#22c55e",
                     3: "#ef4444", 4: "#9ca3af"}.get(State.eac_status, "#e8e8e8")
        self.lbl_eac.config(text=eac_name, fg=eac_color)
        err_name = EAC_ERROR_NAMES[State.eac_error] if 0 <= State.eac_error < 16 else "?"
        err_color = "#ef4444" if State.eac_error else "#22c55e"
        self.lbl_err.config(text=err_name, fg=err_color)

        # Top status badge
        if State.estop:
            self.lbl_status.config(text=f"E-STOP: {State.estop_reason}", fg="#ef4444")
        elif State.rx_count == 0:
            self.lbl_status.config(text="WAITING FOR 0x370...", fg="#eab308")
        elif State.eac_status == 2:
            self.lbl_status.config(text="ACTIVE", fg="#22c55e")
        elif State.eac_status == 1:
            self.lbl_status.config(text="AVAILABLE", fg="#eab308")
        elif State.eac_status == 0:
            self.lbl_status.config(text="INHIBITED", fg="#9ca3af")
        else:
            self.lbl_status.config(text=eac_name, fg=eac_color)

        self.after(40, self._tick)

    # ---------- Shutdown ----------

    def on_close(self):
        State.estop = True
        if hasattr(self, "worker") and self.worker:
            self.worker.stop()
            self.worker.join(timeout=1.5)
        self.destroy()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("steer.py launching... GUI window will open.")
    print("Click in the window to give it focus, then use arrow keys.")
    App().mainloop()
    print("Bye.")
