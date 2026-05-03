"""
move.py -- the simplest possible script that turns the steering wheel
=====================================================================

Run:    python move.py 15
Effect: wheels turn to +15 degrees.
Stop:   Ctrl-C (or close the terminal)

This script does ONE thing: it pumps a single CAN message (0x488
DAS_steeringControl) out the SYS TEC USB-CAN adapter at 50 Hz, with
the angle you typed on the command line, until you stop it.

REQUIREMENTS
    pip install python-can
    SYS TEC sysWORXX USB-CAN driver installed (Windows only)
    Front wheels OFF the ground (jacked up or tie rods disconnected)
    Tesla EPAS rack already firmware-patched per gregjhogan's tool
    Adapter wired: SYS TEC DB9 pin 7 -> OBD-II pin 1 (CH+)
                   SYS TEC DB9 pin 2 -> OBD-II pin 9 (CH-)
    Car ignition ON so chassis CAN has power.

WHAT IT DOES NOT DO (deliberately)
    - No GUI. No buttons.
    - No rate limit. If you type "90" the rack tries to slam there
      instantly. The rack itself rate-limits internally but a
      sudden full-lock command can fault it.
    - No watchdog on the rack's response. If 0x370 stops, this
      script doesn't care -- it keeps sending.
    - No driver-override detection. Touch the wheel and we keep
      fighting you.

For a more careful version with all the safety checks, use
tesla_steering_test.py (the GUI tool) in this same repo. This
file is just for "I want to see the wheel move with one command."

CAN PROTOCOL (verified against opendbc tesla_can.dbc)
    ID 0x488, DAS_steeringControl, 4 bytes, sent at 50 Hz on bus 0.
    Bytes 0-1 (big-endian): top bit reserved (haptic flag, leave 0),
                            remaining 15 bits = (degrees + 1638.35) * 10.
                            Center = 0x4000 = 16384.
    Byte 2:  upper 2 bits = controlType (1 = ANGLE_CONTROL = "engaged")
             lower 4 bits = counter, increments 0..15 each frame
    Byte 3:  checksum = (0x88 + 0x04 + b0 + b1 + b2) & 0xFF

The 0x88 + 0x04 in the checksum is the message ID's two bytes summed
(0x488 = 0x04, 0x88 in big-endian). That's how openpilot does it and
how the rack expects it.

Author: Derek Nagel (with Claude Sonnet 4.6)
"""

import can       # python-can library, talks to the SYS TEC adapter
import time      # for the 50 Hz timing loop
import sys       # to read the angle from the command line


# ============================================================================
# CONFIG -- edit these if you change hardware
# ============================================================================

CAN_BITRATE = 500_000        # Tesla chassis CAN bus runs at 500 kbps. Don't change.
SYSTEC_DEVICE = 0            # First SYS TEC device on the system. 0 is fine
                             # if you only have one plugged in.
SYSTEC_CHANNEL = 0           # USB-CANmodul1 only has one channel. Always 0.

SEND_RATE_HZ = 50            # How often to send 0x488. 50 matches what
                             # openpilot uses on Tesla. The rack expects
                             # at least ~20 Hz; below that it faults.
SEND_PERIOD_S = 1.0 / SEND_RATE_HZ   # = 0.02 s = 20 ms between frames

# Smoothing: low-pass filter the target angle so the rack ramps in smoothly
# instead of slamming to the commanded value. tau is the time-constant in
# seconds; 0.15 means it reaches ~63% of the target in 150ms, ~95% in 450ms.
RAMP_TAU_S = 0.15

# Bench mode: also inject a fake 0x155 ESP_B vehicle-speed message at 50 Hz.
# The rack scales its torque output by speed; at 0 km/h it intentionally
# limits torque (~30-40% of max) so it doesn't fight a stationary driver.
# Spoofing speed = 30 km/h unlocks the rack's full torque curve.
#
# WARNING: only enable when wheels are loaded and you accept the risk of
# tire scrub forces and rack motor stress at standstill. Stock ESP module
# is also broadcasting 0x155 saying 0 km/h, so our message contends with
# theirs on the bus.
BENCH_MODE = False           # Off for jacked-up testing (the right setup).
                             # Only set True for rack-on-bench (no stock ESP)
                             # or as an override on ground (unreliable due
                             # to contention with stock ESP module).
BENCH_FAKE_SPEED_KPH = 30.0  # Above MIN_SPEED gate, below alarm thresholds


# ============================================================================
# STEP 1: read the angle the user typed
# ============================================================================

# sys.argv is a list of command-line arguments. argv[0] is the script
# name itself, argv[1] is the first real argument.
# So `python move.py 15` gives sys.argv = ['move.py', '15'].
if len(sys.argv) != 2:
    print("Usage: python move.py <angle_in_degrees>")
    print("Example: python move.py 15      (turn wheels to +15 deg)")
    print("         python move.py -10     (turn wheels to -10 deg)")
    print("         python move.py 0       (center)")
    sys.exit(1)   # exit with error code 1 so shell knows it failed

try:
    target_angle_deg = float(sys.argv[1])
except ValueError:
    # User typed something that isn't a number, like "fifteen" or "abc"
    print(f"That's not a number: {sys.argv[1]}")
    sys.exit(1)

# Soft sanity clamp so a typo doesn't ruin our day. The patched rack
# probably accepts well beyond +/- 90 but we have no reason to test that.
if abs(target_angle_deg) > 90:
    print(f"Refusing to command {target_angle_deg} deg. Max is +/- 90.")
    print("If you really want more, edit this script. (Don't.)")
    sys.exit(1)


# ============================================================================
# STEP 2: open the CAN bus
# ============================================================================

# python-can's `Bus` is the abstraction for any CAN adapter. We tell it
# to use the "systec" backend (which calls into SYS TEC's USBCAN32.dll
# on Windows). The bitrate must match the bus speed -- chassis CAN is
# 500 kbps, so this had better be 500000.
print(f"Opening SYS TEC adapter at {CAN_BITRATE//1000} kbps...")
try:
    bus = can.Bus(
        interface="systec",
        channel=SYSTEC_CHANNEL,
        device_number=SYSTEC_DEVICE,
        bitrate=CAN_BITRATE,
        receive_own_messages=False,   # don't echo our own frames back to us
    )
except Exception as e:
    # The adapter isn't plugged in, the driver isn't installed, or the
    # bus has the wrong bitrate set somewhere else.
    print(f"Could not open CAN adapter: {e}")
    print("Check: USB cable, SYS TEC driver, and that no other program")
    print("       is currently using the adapter.")
    sys.exit(1)

print(f"Connected. Sending 0x488 at {SEND_RATE_HZ} Hz, target = {target_angle_deg:+.1f} deg.")
if BENCH_MODE:
    print(f"BENCH_MODE on: also sending fake 0x155 ESP_B at {BENCH_FAKE_SPEED_KPH:.0f} km/h.")
print("Press Ctrl-C to stop.")


# Build a fake 0x155 ESP_B (8 bytes) with vehicleSpeed signal set.
# Encoding from tesla_can.dbc ESP_B: vehicleSpeed at bits 24|13 LE,
# factor 0.04, offset -40 km/h. raw = (kph + 40) / 0.04, lives in
# bytes 3 (low 8) + byte 4 low-5 bits (high 5).
def build_fake_esp_speed(kph):
    raw = int(round((kph + 40.0) / 0.04)) & 0x1FFF
    data = bytearray(8)
    data[3] = raw & 0xFF
    data[4] = (raw >> 8) & 0x1F
    return bytes(data)

esp_data = build_fake_esp_speed(BENCH_FAKE_SPEED_KPH)
ID_ESP_B = 0x155


# ============================================================================
# STEP 3: the main send loop
# ============================================================================

counter = 0   # 4-bit counter, has to increment each frame mod 16. Anti-replay.
              # If we don't increment, the rack ignores us.

# We ramp the commanded angle from 0 to target with a low-pass filter,
# so the rack doesn't slam. current_angle starts at 0 and approaches
# target_angle_deg over RAMP_TAU_S seconds.
current_angle = 0.0

# Pre-compute the LPF coefficient. dt = SEND_PERIOD_S = 20 ms.
# alpha = dt / (tau + dt). At tau=0.15s: alpha ~= 0.118.
ALPHA = SEND_PERIOD_S / (RAMP_TAU_S + SEND_PERIOD_S)

try:
    next_send = time.monotonic()
    while True:
        # Stage 1: low-pass filter the target. Each iteration, current_angle
        # moves a small fraction (ALPHA) closer to target_angle_deg.
        current_angle += ALPHA * (target_angle_deg - current_angle)

        # Convert current_angle to the rack's raw 15-bit unsigned encoding.
        # raw = (degrees + 1638.35) * 10, center is 0x4000 = 16384.
        angle_raw = int(round((current_angle + 1638.35) * 10.0))
        angle_raw = max(0, min(0x7FFF, angle_raw))
        b0 = (angle_raw >> 8) & 0x7F   # high 7 bits, top bit reserved for haptic
        b1 = angle_raw & 0xFF          # low 8 bits

        # Build byte 2: upper 2 bits = controlType, lower 4 bits = counter.
        # controlType = 1 means "ANGLE_CONTROL active".
        b2 = (1 << 6) | (counter & 0x0F)

        # Build byte 3: checksum = sum of address bytes + data bytes, mod 256.
        # 0x488 = 0x04 0x88, so the ID contribution is 0x8C.
        b3 = (0x88 + 0x04 + b0 + b1 + b2) & 0xFF

        # Send the steering frame.
        bus.send(can.Message(
            arbitration_id=0x488,
            data=[b0, b1, b2, b3],
            is_extended_id=False,
        ))

        # In bench mode, also send a fake speed message so the rack
        # thinks the car is moving and unlocks full torque.
        if BENCH_MODE:
            bus.send(can.Message(
                arbitration_id=ID_ESP_B,
                data=esp_data,
                is_extended_id=False,
            ))

        counter = (counter + 1) & 0x0F

        # Hybrid sleep: sleep most of the way, busy-wait the last 2 ms for
        # accurate 50 Hz timing. Python's time.sleep on Windows has ~15 ms
        # granularity which makes plain sleep(0.02) jittery.
        next_send += SEND_PERIOD_S
        BUSY_WAIT_S = 0.002
        sleep_s = next_send - time.monotonic()
        if sleep_s > BUSY_WAIT_S:
            time.sleep(sleep_s - BUSY_WAIT_S)
        while time.monotonic() < next_send:
            pass

except KeyboardInterrupt:
    # Ctrl-C lands here. Send a few frames with controlType=0 to cleanly
    # disengage. Without this, the rack holds our last commanded angle
    # until its own watchdog times out (~200 ms).
    print("\nDisengaging...")
    angle_raw = int(round((current_angle + 1638.35) * 10.0))
    angle_raw = max(0, min(0x7FFF, angle_raw))
    b0 = (angle_raw >> 8) & 0x7F
    b1 = angle_raw & 0xFF
    b2 = (0 << 6) | (counter & 0x0F)   # controlType = 0 = disabled
    b3 = (0x88 + 0x04 + b0 + b1 + b2) & 0xFF
    try:
        # Send a few disengage frames in a row.
        for _ in range(5):
            bus.send(can.Message(
                arbitration_id=0x488,
                data=[b0, b1, b2, b3],
                is_extended_id=False,
            ))
            counter = (counter + 1) & 0x0F
            b2 = (0 << 6) | (counter & 0x0F)
            b3 = (0x88 + 0x04 + b0 + b1 + b2) & 0xFF
            time.sleep(0.02)
    except Exception:
        # If sending the disengage failed, oh well. The rack's own
        # watchdog kicks in within ~200 ms once it stops hearing us.
        pass

finally:
    # Always close the bus on the way out, even if something blew up.
    # This releases the USB device so the next run can open it.
    bus.shutdown()
    print("Bus closed.")
