"""
Tesla CAN bus sniffer / pinout verifier
=======================================

Passive-only tool. Listens to whatever wires you connect the SYS TEC adapter
to, reports what bus speed works (if any) and what message IDs are present.

PURPOSE
    Confirm you are tapped into the Tesla chassis CAN bus before connecting
    anything as a transmitter. This script never sends a single CAN frame.
    It is safe to leave running indefinitely.

USE
    python can_sniffer.py

WHAT YOU ARE LOOKING FOR
    A live Tesla chassis CAN bus produces hundreds of frames per second at
    500 kbps. The sniffer auto-tries 500 / 250 / 125 kbps and reports which
    one gets clean traffic (no error frames).

    Then it watches for these Tesla-specific IDs:
      0x370  EPAS_sysStatus         (steering rack status)
      0x101  GTW_epasControl        (gateway -> rack)
      0x488  DAS_steeringControl    (driver assist -> rack, only if AP)
      0x129  SteeringAngle          (steering wheel angle sensor)
      0x108  DI_torque1             (drive inverter)

    If you see >= 2 of these IDs ticking up, you are on chassis CAN. Done.
    If you see ZERO Tesla-pattern IDs but you ARE getting frames at some
    baud rate, you are on a different Tesla bus (powertrain, body, etc).
    If you see no frames at any baud rate, the wires are not connected to
    a CAN bus at all (or H/L are swapped).

OUTPUT
    Real-time table of every CAN ID seen, with hit count, rate, and last 8
    bytes of payload. Tesla IDs are highlighted in green.
"""

import can
import time
import sys
from collections import defaultdict

SYSTEC_DEVICE_NUMBER = 255      # ANY_MODULE auto-detect
SYSTEC_CHANNEL = 0
BITRATES_TO_TRY = [500_000, 250_000, 125_000]
SCAN_SECONDS = 4                # listen this long at each baud before deciding

TESLA_KNOWN_IDS = {
    0x101: "GTW_epasControl",
    0x108: "DI_torque1",
    0x129: "SteeringAngle",
    0x155: "ESP_B",
    0x214: "EPB_epasControl",
    0x224: "EPB_status",
    0x370: "EPAS_sysStatus",
    0x399: "EPAS_status",
    0x488: "DAS_steeringControl",
    0x4F0: "DAS_status",
    0x4F1: "DAS_bodyControls",
    0x562: "DI_state",
}

# ANSI colors (work in Windows 10+ cmd.exe with VT enabled)
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def enable_windows_vt():
    """Enable ANSI escape sequences on Windows 10+ cmd.exe."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def scan_bitrate(bitrate: int) -> tuple[int, int, set]:
    """Try a bitrate for SCAN_SECONDS. Return (frame_count, error_count, ids_seen)."""
    print(f"\n  trying {bitrate // 1000} kbps ...", end=" ", flush=True)
    bus = None
    try:
        bus = can.Bus(
            interface="systec",
            channel=SYSTEC_CHANNEL,
            device_number=SYSTEC_DEVICE_NUMBER,
            bitrate=bitrate,
            receive_own_messages=False,
        )
    except Exception as e:
        print(f"{RED}adapter open failed: {e}{RESET}")
        return 0, 0, set()

    frames = 0
    errors = 0
    ids = set()
    deadline = time.monotonic() + SCAN_SECONDS
    while time.monotonic() < deadline:
        msg = bus.recv(timeout=0.1)
        if msg is None:
            continue
        if msg.is_error_frame:
            errors += 1
        else:
            frames += 1
            ids.add(msg.arbitration_id)
    try:
        bus.shutdown()
    except Exception:
        pass

    if frames == 0:
        print(f"{DIM}no traffic{RESET}")
    elif errors > frames * 0.1:
        print(f"{RED}noisy ({frames} frames, {errors} errors) -- wrong baud{RESET}")
    else:
        print(f"{GREEN}{frames} frames, {errors} errors, {len(ids)} unique IDs{RESET}")
    return frames, errors, ids


def auto_detect_bitrate() -> int:
    print(f"{BOLD}auto-detecting CAN bitrate ({SCAN_SECONDS}s per try)...{RESET}")
    best = (0, 0, 500_000, set())   # frames, -errors, bitrate, ids
    for bps in BITRATES_TO_TRY:
        frames, errors, ids = scan_bitrate(bps)
        score = frames - errors * 10
        if score > best[0]:
            best = (score, errors, bps, ids)
    if best[0] < 5:
        print(f"\n{RED}NO valid CAN traffic found at any tested baud rate.{RESET}")
        print(f"{YELLOW}  Possible causes:{RESET}")
        print("    - CAN H and CAN L are swapped (try swapping pin 7 and pin 2)")
        print("    - Wires are not connected to a CAN bus at all")
        print("    - Bus is not powered (Tesla not in accessory or on)")
        print("    - Termination missing (try 120 ohm between H and L)")
        sys.exit(1)
    print(f"\n{GREEN}{BOLD}best match: {best[2] // 1000} kbps{RESET}")
    return best[2]


def live_view(bitrate: int):
    print(f"\n{BOLD}live capture at {bitrate // 1000} kbps. Ctrl-C to exit.{RESET}\n")
    bus = can.Bus(
        interface="systec",
        channel=SYSTEC_CHANNEL,
        device_number=SYSTEC_DEVICE_NUMBER,
        bitrate=bitrate,
    )

    counts = defaultdict(int)
    last_data = {}
    last_seen = {}
    rates = defaultdict(lambda: 0.0)
    rate_window = defaultdict(list)
    start = time.monotonic()
    last_print = 0.0
    tesla_hits = 0

    try:
        while True:
            msg = bus.recv(timeout=0.05)
            now = time.monotonic()
            if msg is not None and not msg.is_error_frame:
                counts[msg.arbitration_id] += 1
                last_data[msg.arbitration_id] = bytes(msg.data)
                last_seen[msg.arbitration_id] = now
                rate_window[msg.arbitration_id].append(now)
                # keep last 50 timestamps for rate calc
                if len(rate_window[msg.arbitration_id]) > 50:
                    rate_window[msg.arbitration_id].pop(0)

            # Update display 4x/sec
            if now - last_print < 0.25:
                continue
            last_print = now

            # Calculate rates
            for can_id, ts_list in rate_window.items():
                if len(ts_list) >= 2:
                    span = ts_list[-1] - ts_list[0]
                    rates[can_id] = (len(ts_list) - 1) / span if span > 0 else 0.0

            # Clear screen and reprint
            print("\033[H\033[2J", end="")
            elapsed = now - start
            tesla_hits = sum(1 for cid in counts if cid in TESLA_KNOWN_IDS)
            verdict = ""
            if tesla_hits >= 2:
                verdict = f"{GREEN}{BOLD}*** TESLA CHASSIS CAN CONFIRMED ***{RESET}"
            elif counts and tesla_hits == 0:
                verdict = f"{YELLOW}live CAN bus, but no known Tesla IDs -- wrong sub-bus?{RESET}"
            elif not counts:
                verdict = f"{RED}no traffic{RESET}"

            print(f"{BOLD}Tesla CAN sniffer  --  {bitrate // 1000} kbps  --  "
                  f"{elapsed:6.1f}s  --  {sum(counts.values())} frames total{RESET}")
            print(f"  Tesla-known IDs seen: {tesla_hits} / {len(TESLA_KNOWN_IDS)}    {verdict}")
            print()
            print(f"  {'ID':>6} {'Hz':>6} {'count':>8}  {'name':<22} {'last data (hex)':<25} age")
            print(f"  " + "-" * 80)

            sorted_ids = sorted(counts.keys())
            for can_id in sorted_ids:
                name = TESLA_KNOWN_IDS.get(can_id, "")
                color = GREEN if can_id in TESLA_KNOWN_IDS else ""
                hexdata = last_data[can_id].hex(" ")
                age_ms = (now - last_seen[can_id]) * 1000
                age_str = f"{age_ms:4.0f}ms" if age_ms < 1000 else f"{age_ms / 1000:4.1f}s"
                print(f"  {color}0x{can_id:03X} {rates[can_id]:6.1f} "
                      f"{counts[can_id]:>8}  {name:<22} {hexdata:<25} {age_str}{RESET}")

            # Tesla-specific decode for 0x370 if seen
            if 0x370 in last_data:
                d = last_data[0x370]
                if len(d) >= 8:
                    eac_status = (d[6] >> 5) & 0x07
                    eac_err = (d[2] >> 4) & 0x0F
                    raw = ((d[4] & 0x3F) << 8) | d[5]
                    angle = raw * 0.1 - 819.2
                    status_names = {0: "INHIBITED", 1: "AVAILABLE", 2: "ACTIVE",
                                    3: "FAULT", 4: "SNA"}
                    err_names = ["NONE", "MIN_SPEED", "MAX_SPEED", "HANDS_ON",
                                 "OUT_OF_RANGE", "OVER_TORQUE", "HIGH_ANGLE_REQ",
                                 "HIGH_ANGLE_RATE", "HIGH_TORQUE", "BLEND",
                                 "TIMEOUT", "ECU_FAULT", "BUS_FAULT",
                                 "INVALID_REQ", "EPB_INHIBIT", "SNA"]
                    print(f"\n  {BOLD}EPAS_sysStatus decode:{RESET}")
                    print(f"    eacStatus    = {status_names.get(eac_status, '?')}")
                    print(f"    eacErrorCode = {err_names[eac_err] if eac_err < 16 else '?'}")
                    print(f"    measured ang = {angle:+.1f} deg")
                    print(f"    {DIM}(turn the wheel by hand -- this number should change){RESET}")

    except KeyboardInterrupt:
        print(f"\n\n{BOLD}stopped.{RESET}")
        print(f"  {len(counts)} unique IDs seen")
        print(f"  {tesla_hits} matched known Tesla IDs")
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass


def main():
    enable_windows_vt()
    print(f"{BOLD}=== Tesla CAN Sniffer (passive only -- nothing transmitted) ==={RESET}")
    print()
    print("Make sure:")
    print("  1. SYS TEC USB-CANmodul1 is plugged into laptop")
    print("  2. CAN H/L wires are connected to the pins you want to test")
    print("  3. Tesla is on or in accessory mode (so the bus has power)")
    print()
    input("Press Enter to start auto-detect, or Ctrl-C to abort...")

    bitrate = auto_detect_bitrate()
    time.sleep(0.5)
    live_view(bitrate)


if __name__ == "__main__":
    main()
