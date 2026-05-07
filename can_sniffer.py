"""
Tesla CAN bus sniffer / pinout verifier
=======================================

Passive-only tool. Listens to whatever wires you connect the SYS TEC
adapter to, reports what bus speed works (if any) and what message
IDs are present. NEVER transmits.

USAGE
    python can_sniffer.py
        Default. Auto-detect bitrate, then show the wide live table
        with all CAN IDs.

    python can_sniffer.py 0x6D
        Filter to a single ID. Switches the display to the "frame
        history" pane: shows the last 15 frames of 0x6D with their
        bytes, decoded fields, and (for known CRC-bearing IDs)
        whether our tesla_crc8 matches the wire byte.

    python can_sniffer.py 0x6D 0x118
        Filter to multiple IDs. Each gets its own history pane.

    python can_sniffer.py 0x6D --capture
        Filter to 0x6D AND append every matching frame to
        field_testing/captures/capture_<timestamp>.csv. Useful for
        recording a stalk-shift event for offline CRC analysis.

    python can_sniffer.py 0x6D --git-save shift_capture
        Same as --capture, AND on exit copy the file to a named
        folder, git add + commit + push so Claude / Derek can
        pull it down. Equivalent to the SAVE TEST button in
        tesla_control.py.

    python can_sniffer.py --bitrate 500000 --no-detect
        Skip the auto-detect step and use a fixed bitrate.

ON EXIT (Ctrl-C)
    Prints a paste-friendly summary block with the last few captured
    frames in a format you can copy directly into a chat message.

WHAT YOU ARE LOOKING FOR
    A live Tesla chassis CAN bus produces hundreds of frames per
    second at 500 kbps. The sniffer auto-tries 500 / 250 / 125 kbps
    and reports which one gets clean traffic.

    Then it watches for these Tesla-specific IDs:
      0x06D  SBW_RQ_SCCM           (gear shift request, CRC-protected)
      0x045  STW_ACTN_RQ           (stalk action, CRC-protected)
      0x101  GTW_epasControl       (gateway -> rack)
      0x108  DI_torque1
      0x118  DI_torque2            (carries DI_gear)
      0x129  SteeringAngle
      0x155  ESP_B vehicleSpeed
      0x214  EPB_epasControl
      0x370  EPAS_sysStatus        (rack -> us, decoded inline)
      0x488  DAS_steeringControl

    If you see >= 2 of these IDs ticking up, you are on chassis CAN.
"""

import argparse
import can
import csv
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict, deque
from datetime import datetime

SYSTEC_DEVICE_NUMBER = 255      # ANY_MODULE auto-detect
SYSTEC_CHANNEL = 0
BITRATES_TO_TRY = [500_000, 250_000, 125_000]
SCAN_SECONDS = 4
HISTORY_PER_ID = 15

TESLA_KNOWN_IDS = {
    0x045: "STW_ACTN_RQ (stalk)",
    0x06D: "SBW_RQ_SCCM (shift)",
    0x101: "GTW_epasControl",
    0x108: "DI_torque1",
    0x118: "DI_torque2 (gear)",
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

# IDs whose last byte is a CRC-8/J1850 over the preceding bytes.
# We auto-verify these in the history pane.
CRC_PROTECTED_IDS = {
    0x06D: 3,   # SBW_RQ_SCCM: CRC at byte 3, over bytes 0..2
    # 0x045 STW_ACTN_RQ: CRC at byte 7 over bytes 0..6 (stalk message,
    # not currently sent by us; verify if you start using it)
}

# ANSI colors (work in Windows 10+ cmd.exe with VT enabled)
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def enable_windows_vt():
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


# ============================================================================
# Tesla CRC-8/SAE-J1850
# ============================================================================
# Verbatim from tesla_control.py. Polynomial 0x1D, init 0xFF, XOR-out 0xFF.
# Verified against BogGyver/panda safety_tesla.h tesla_compute_crc.

def tesla_crc8(data: bytes) -> int:
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x1D) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc ^ 0xFF


# ============================================================================
# Bitrate detection
# ============================================================================

def scan_bitrate(bitrate: int):
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
        print(f"{RED}noisy ({frames} frames, {errors} errors){RESET}")
    else:
        print(f"{GREEN}{frames} frames, {errors} errors, "
              f"{len(ids)} unique IDs{RESET}")
    return frames, errors, ids


def auto_detect_bitrate():
    print(f"{BOLD}auto-detecting CAN bitrate "
          f"({SCAN_SECONDS}s per try)...{RESET}")
    best = (0, 0, 500_000, set())
    for bps in BITRATES_TO_TRY:
        frames, errors, ids = scan_bitrate(bps)
        score = frames - errors * 10
        if score > best[0]:
            best = (score, errors, bps, ids)
    if best[0] < 5:
        print(f"\n{RED}NO valid CAN traffic found at any tested baud.{RESET}")
        print(f"{YELLOW}  Possible causes:{RESET}")
        print("    - CAN H and CAN L are swapped (try swapping pins)")
        print("    - Wires not connected to a CAN bus")
        print("    - Bus not powered (Tesla not in accessory or on)")
        print("    - Termination missing (try 120 ohm between H and L)")
        sys.exit(1)
    print(f"\n{GREEN}{BOLD}best match: {best[2] // 1000} kbps{RESET}")
    return best[2]


# ============================================================================
# Inline decoders (informational; doesn't affect what is captured)
# ============================================================================

def decode_0x370(data: bytes) -> str:
    if len(data) < 8:
        return "(short frame)"
    eac_status = (data[6] >> 5) & 0x07
    eac_err = (data[2] >> 4) & 0x0F
    raw = ((data[4] & 0x3F) << 8) | data[5]
    angle = raw * 0.1 - 819.2
    status_names = {0: "INHIBITED", 1: "AVAILABLE", 2: "ACTIVE",
                    3: "FAULT", 4: "SNA"}
    err_names = ["NONE", "MIN_SPEED", "MAX_SPEED", "HANDS_ON",
                 "OUT_OF_RANGE", "OVER_TORQUE", "HIGH_ANGLE_REQ",
                 "HIGH_ANGLE_RATE", "HIGH_TORQUE", "BLEND", "TIMEOUT",
                 "ECU_FAULT", "BUS_FAULT", "INVALID_REQ",
                 "EPB_INHIBIT", "SNA"]
    return (f"eac={status_names.get(eac_status, '?')} "
            f"err={err_names[eac_err] if eac_err < 16 else '?'} "
            f"ang={angle:+.1f}deg")


def decode_0x118(data: bytes) -> str:
    if len(data) < 5:
        return "(short frame)"
    gear = (data[1] >> 4) & 0x07
    brake = (data[1] >> 7) & 0x01
    gear_req = (data[3] >> 4) & 0x07
    speed_raw = data[2] | ((data[3] & 0x0F) << 8)
    speed_mph = speed_raw * 0.05 - 25.0
    gear_names = {0: "INV", 1: "P", 2: "R", 3: "N", 4: "D", 7: "SNA"}
    return (f"gear={gear_names.get(gear, '?')} "
            f"req={gear_names.get(gear_req, '?')} "
            f"brake={'1' if brake else '0'} spd={speed_mph:+.1f}mph")


def decode_0x6D(data: bytes) -> str:
    if len(data) < 4:
        return "(short frame)"
    rnd = data[1] & 0x0F
    p = (data[1] >> 4) & 0x03
    counter = (data[2] >> 4) & 0x0F
    crc_byte = data[3]
    rnd_names = {0: "IDLE", 1: "R", 2: "N_UP", 4: "N_DOWN",
                 6: "INI", 8: "D", 15: "SNA"}
    p_names = {0: "IDLE", 1: "PSD", 2: "INI", 3: "SNA"}
    # Show the fixed bits for diagnosis (real stalk: b0=0x40, b1 bit 6-7 set)
    b0_mark = "" if data[0] == 0x40 else f" b0=0x{data[0]:02X}"
    b1_top  = "" if (data[1] & 0xC0) == 0xC0 else " b1!c0"
    # CRC verification
    our_crc = tesla_crc8(bytes(data[:3]))
    crc_mark = f"{GREEN}OK{RESET}" if our_crc == crc_byte else f"{RED}MISS{RESET}"
    return (f"rnd={rnd_names.get(rnd, f'?({rnd})')} "
            f"P={p_names.get(p, f'?({p})')} "
            f"ctr={counter}{b0_mark}{b1_top} "
            f"crc=0x{crc_byte:02X} ours=0x{our_crc:02X} {crc_mark}")


def decode_0x45(data: bytes) -> str:
    if len(data) < 8:
        return "(short frame)"
    crc_byte = data[7]
    our_crc = tesla_crc8(bytes(data[:7]))
    crc_mark = f"{GREEN}OK{RESET}" if our_crc == crc_byte else f"{RED}MISS{RESET}"
    counter = (data[6] >> 4) & 0x0F
    return (f"ctr={counter} crc=0x{crc_byte:02X} "
            f"ours=0x{our_crc:02X} {crc_mark}")


DECODERS = {
    0x06D: decode_0x6D,
    0x118: decode_0x118,
    0x370: decode_0x370,
    0x045: decode_0x45,
}


# ============================================================================
# Live view -- default (wide table)
# ============================================================================

def live_view_wide(bitrate: int, capture_writer=None):
    print(f"\n{BOLD}live capture at {bitrate // 1000} kbps. "
          f"Ctrl-C to exit.{RESET}\n")
    bus = can.Bus(interface="systec", channel=SYSTEC_CHANNEL,
                  device_number=SYSTEC_DEVICE_NUMBER, bitrate=bitrate)

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
                cid = msg.arbitration_id
                counts[cid] += 1
                last_data[cid] = bytes(msg.data)
                last_seen[cid] = now
                rate_window[cid].append(now)
                if len(rate_window[cid]) > 50:
                    rate_window[cid].pop(0)
                if capture_writer:
                    capture_writer(now, cid, msg.data)

            if now - last_print < 0.25:
                continue
            last_print = now

            for can_id, ts_list in rate_window.items():
                if len(ts_list) >= 2:
                    span = ts_list[-1] - ts_list[0]
                    rates[can_id] = (len(ts_list) - 1) / span if span > 0 else 0.0

            print("\033[H\033[2J", end="")
            elapsed = now - start
            tesla_hits = sum(1 for cid in counts if cid in TESLA_KNOWN_IDS)
            verdict = ""
            if tesla_hits >= 2:
                verdict = f"{GREEN}{BOLD}*** TESLA CHASSIS CAN CONFIRMED ***{RESET}"
            elif counts and tesla_hits == 0:
                verdict = f"{YELLOW}live bus, no known Tesla IDs -- wrong sub-bus?{RESET}"
            elif not counts:
                verdict = f"{RED}no traffic{RESET}"

            print(f"{BOLD}Tesla CAN sniffer  --  {bitrate // 1000} kbps  --  "
                  f"{elapsed:6.1f}s  --  {sum(counts.values())} frames total{RESET}")
            print(f"  Tesla-known IDs seen: {tesla_hits} / "
                  f"{len(TESLA_KNOWN_IDS)}    {verdict}")
            print()
            print(f"  {'ID':>6} {'Hz':>6} {'count':>8}  "
                  f"{'name':<24} {'last data (hex)':<25} age")
            print(f"  " + "-" * 84)

            for can_id in sorted(counts.keys()):
                name = TESLA_KNOWN_IDS.get(can_id, "")
                color = GREEN if can_id in TESLA_KNOWN_IDS else ""
                hexdata = last_data[can_id].hex(" ")
                age_ms = (now - last_seen[can_id]) * 1000
                age_str = f"{age_ms:4.0f}ms" if age_ms < 1000 else f"{age_ms / 1000:4.1f}s"
                print(f"  {color}0x{can_id:03X} {rates[can_id]:6.1f} "
                      f"{counts[can_id]:>8}  {name:<24} "
                      f"{hexdata:<25} {age_str}{RESET}")

            if 0x370 in last_data:
                print(f"\n  {BOLD}EPAS_sysStatus decode:{RESET}")
                print(f"    {decode_0x370(last_data[0x370])}")

    except KeyboardInterrupt:
        print(f"\n\n{BOLD}stopped.{RESET}")
        print(f"  {len(counts)} unique IDs seen")
        print(f"  {tesla_hits} matched known Tesla IDs")
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass


# ============================================================================
# Live view -- filtered (frame history pane per ID)
# ============================================================================

def live_view_filtered(bitrate: int, watch_ids: list, capture_writer=None):
    print(f"\n{BOLD}filtered capture at {bitrate // 1000} kbps. "
          f"Ctrl-C to exit.{RESET}")
    print(f"watching: {' '.join(f'0x{cid:03X}' for cid in watch_ids)}")
    print()

    bus = can.Bus(interface="systec", channel=SYSTEC_CHANNEL,
                  device_number=SYSTEC_DEVICE_NUMBER, bitrate=bitrate)
    watch_set = set(watch_ids)
    counts = defaultdict(int)
    history = {cid: deque(maxlen=HISTORY_PER_ID) for cid in watch_ids}
    rate_window = defaultdict(list)
    rates = defaultdict(float)
    other_count = 0
    start = time.monotonic()
    last_print = 0.0

    try:
        while True:
            msg = bus.recv(timeout=0.05)
            now = time.monotonic()
            if msg is not None and not msg.is_error_frame:
                cid = msg.arbitration_id
                if cid in watch_set:
                    counts[cid] += 1
                    history[cid].append((now, bytes(msg.data)))
                    rate_window[cid].append(now)
                    if len(rate_window[cid]) > 50:
                        rate_window[cid].pop(0)
                    if capture_writer:
                        capture_writer(now, cid, msg.data)
                else:
                    other_count += 1

            if now - last_print < 0.25:
                continue
            last_print = now

            for cid, ts_list in rate_window.items():
                if len(ts_list) >= 2:
                    span = ts_list[-1] - ts_list[0]
                    rates[cid] = (len(ts_list) - 1) / span if span > 0 else 0.0

            print("\033[H\033[2J", end="")
            elapsed = now - start
            print(f"{BOLD}Tesla CAN sniffer (FILTERED)  --  "
                  f"{bitrate // 1000} kbps  --  {elapsed:6.1f}s{RESET}")
            print(f"  watched IDs: {' '.join(f'0x{cid:03X}' for cid in watch_ids)}"
                  f"   ·   other traffic ignored: {other_count} frames")
            print()

            # Summary row per watched ID
            print(f"  {'ID':>6} {'Hz':>6} {'count':>8}  {'name':<28}")
            print(f"  " + "-" * 50)
            for cid in watch_ids:
                name = TESLA_KNOWN_IDS.get(cid, "")
                color = GREEN if counts[cid] > 0 else DIM
                print(f"  {color}0x{cid:03X} {rates[cid]:6.1f} "
                      f"{counts[cid]:>8}  {name:<28}{RESET}")

            # History pane per ID
            for cid in watch_ids:
                if not history[cid]:
                    print(f"\n  {DIM}0x{cid:03X}: no frames yet{RESET}")
                    continue
                name = TESLA_KNOWN_IDS.get(cid, "")
                print(f"\n  {BOLD}0x{cid:03X}  {name}  "
                      f"(last {len(history[cid])} frames):{RESET}")
                print(f"    {'time':<12} {'bytes':<26} decode")
                for (ts, data) in history[cid]:
                    wall = datetime.fromtimestamp(time.time() - (now - ts))
                    tstr = wall.strftime("%H:%M:%S.") + f"{wall.microsecond//1000:03d}"
                    hexdata = data.hex(" ")
                    decoder = DECODERS.get(cid)
                    decode_str = decoder(data) if decoder else ""
                    print(f"    {tstr:<12} {hexdata:<26} {decode_str}")

    except KeyboardInterrupt:
        print(f"\n\n{BOLD}stopped.{RESET}")
        for cid in watch_ids:
            print(f"  0x{cid:03X}: {counts[cid]} frames")
    finally:
        try:
            bus.shutdown()
        except Exception:
            pass


# ============================================================================
# Capture writer
# ============================================================================

def make_capture_writer(path: str):
    """Returns a function (timestamp, can_id, data) -> None that
    appends a CSV row, AND keeps a small in-memory tail buffer per
    ID for the paste-friendly exit summary.
    """
    f = open(path, "w", newline="", buffering=1)
    w = csv.writer(f)
    w.writerow(["wall_time", "monotonic", "id_hex", "dlc",
                "data_hex", "data_decimal_bytes"])
    start = time.monotonic()
    tail = defaultdict(lambda: deque(maxlen=20))   # last 20 per ID
    counts = defaultdict(int)

    def write(ts: float, can_id: int, data):
        wall = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        rel = ts - start
        b = bytes(data)
        w.writerow([wall, f"{rel:.4f}", f"0x{can_id:03X}", len(b),
                    b.hex(" "), " ".join(str(x) for x in b)])
        tail[can_id].append((wall, b))
        counts[can_id] += 1

    write._file = f
    write._tail = tail
    write._counts = counts
    write._start = start
    return write


def close_capture_writer(writer):
    try:
        writer._file.close()
    except Exception:
        pass


def print_paste_summary(writer, capture_path: str, watch_ids: list):
    """Print a clean ANSI-free summary of the captured frames that
    Charlie can copy/paste directly into a chat message."""
    if writer is None or not writer._counts:
        return
    duration = time.monotonic() - writer._start
    print()
    print("=" * 72)
    print(" PASTE-FRIENDLY SUMMARY -- copy everything below into a message")
    print("=" * 72)
    print(f" file: {capture_path}")
    print(f" duration: {duration:.1f}s")
    if watch_ids:
        print(f" watched: {' '.join(f'0x{cid:03X}' for cid in watch_ids)}")
    print()
    for cid, frames in writer._tail.items():
        name = TESLA_KNOWN_IDS.get(cid, "")
        print(f" 0x{cid:03X}  {name}  ({writer._counts[cid]} frames captured)")
        decoder = DECODERS.get(cid)
        for wall, data in list(frames)[-10:]:   # last 10 per ID
            hexdata = data.hex(" ")
            line = f"   {wall[11:]}  {hexdata}"
            if decoder:
                # Strip ANSI from decode output for clean copy
                decode_str = re.sub(r"\033\[[0-9;]*m", "", decoder(data))
                line += f"   {decode_str}"
            print(line)
        print()
    print("=" * 72)


def git_save_capture(local_path: str, name: str) -> int:
    """Move/copy the capture into a named folder under
    field_testing/captures/, write a small README, then git add +
    commit + push. Returns 0 on success, nonzero on git failure
    (file is still saved in the repo either way).
    """
    repo_root = os.path.dirname(os.path.abspath(__file__))
    safe = re.sub(r'[^a-zA-Z0-9_-]+', '_', name).strip('_')[:64] or "unnamed"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = os.path.join(repo_root, "field_testing", "captures",
                            f"{ts}_{safe}")
    try:
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(local_path, os.path.join(dest_dir, "capture.csv"))
        with open(os.path.join(dest_dir, "README.md"), "w") as f:
            f.write(f"# {name}\n\n")
            f.write(f"**Saved:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Source:** `{os.path.basename(local_path)}`\n\n")
            f.write("## File\n\n- `capture.csv` -- raw CAN frames\n\n")
            f.write("## How to read\n\n")
            f.write("Columns: wall_time, monotonic, id_hex, dlc, "
                    "data_hex, data_decimal_bytes\n")
        rel = os.path.relpath(dest_dir, repo_root)
        print(f"\n{GREEN}saved to {rel}/{RESET}")
    except Exception as e:
        print(f"\n{RED}save failed: {e}{RESET}")
        return 1

    try:
        subprocess.run(["git", "add", rel], cwd=repo_root,
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", f"capture: {name}"],
                       cwd=repo_root, check=True,
                       capture_output=True, text=True)
        print(f"{GREEN}git commit OK{RESET}")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()
        if "nothing to commit" in err:
            print(f"{YELLOW}git: nothing to commit{RESET}")
            return 0
        print(f"{RED}git commit failed: {err}{RESET}")
        return 1
    except FileNotFoundError:
        print(f"{YELLOW}git not in PATH; saved locally only{RESET}")
        return 1

    try:
        br = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                            cwd=repo_root, check=True,
                            capture_output=True, text=True)
        branch = br.stdout.strip()
        subprocess.run(["git", "push", "origin", branch], cwd=repo_root,
                       check=True, capture_output=True, text=True)
        print(f"{GREEN}git push OK to origin/{branch}{RESET}")
        print(f"{GREEN}saved on GitHub: {rel}/{RESET}")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"{RED}git push failed: "
              f"{(e.stderr or '').strip()}{RESET}")
        print(f"  push manually with:  git push origin {branch}")
        return 1


# ============================================================================
# Main
# ============================================================================

def parse_can_id(s: str) -> int:
    s = s.strip().lower()
    if s.startswith("0x"):
        return int(s, 16)
    # accept bare hex like "6d" too
    try:
        return int(s, 16)
    except ValueError:
        pass
    return int(s)


def main():
    enable_windows_vt()
    parser = argparse.ArgumentParser(
        description="Tesla CAN sniffer (passive only).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*",
                        help="optional CAN IDs to filter to (hex like 0x6D). "
                             "If omitted, shows the wide table of all IDs.")
    parser.add_argument("--capture", nargs="?", const="auto",
                        help="append matching frames to a CSV "
                             "(default path: logs/sniffer_capture_"
                             "<timestamp>.csv)")
    parser.add_argument("--git-save", metavar="NAME",
                        help="on exit, copy capture into "
                             "field_testing/captures/<timestamp>_<NAME>/ "
                             "and git add+commit+push (implies --capture)")
    parser.add_argument("--bitrate", type=int, default=None,
                        help="skip auto-detect and use this bitrate (e.g. 500000)")
    parser.add_argument("--no-detect", action="store_true",
                        help="skip auto-detect; assume --bitrate or 500000")
    args = parser.parse_args()

    print(f"{BOLD}=== Tesla CAN Sniffer (passive only -- "
          f"nothing transmitted) ==={RESET}")
    print()

    watch_ids = []
    for s in args.ids:
        try:
            watch_ids.append(parse_can_id(s))
        except ValueError:
            print(f"{RED}bad CAN ID: {s}{RESET}")
            sys.exit(1)

    # --git-save implies --capture
    if args.git_save and args.capture is None:
        args.capture = "auto"

    # Capture file setup -- writes go to ./logs/ alongside session logs
    capture_writer = None
    capture_path = None
    if args.capture is not None:
        if args.capture == "auto":
            here = os.path.dirname(os.path.abspath(__file__))
            cap_dir = os.path.join(here, "logs")
            os.makedirs(cap_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            capture_path = os.path.join(cap_dir, f"sniffer_capture_{ts}.csv")
        else:
            capture_path = args.capture
            os.makedirs(os.path.dirname(os.path.abspath(capture_path)) or ".",
                        exist_ok=True)
        capture_writer = make_capture_writer(capture_path)
        print(f"{YELLOW}capture mode: writing to "
              f"{capture_path}{RESET}")
        if args.git_save:
            print(f"{YELLOW}  on exit: will git-save as "
                  f"'{args.git_save}'{RESET}")
        print()

    print("Make sure:")
    print("  1. SYS TEC USB-CANmodul1 is plugged into laptop")
    print("  2. CAN H/L wires are connected to the pins you want to test")
    print("  3. Tesla is on or in accessory mode (so the bus has power)")
    print()

    if args.no_detect or args.bitrate is not None:
        bitrate = args.bitrate or 500_000
        print(f"{BOLD}using fixed bitrate {bitrate // 1000} kbps "
              f"(skipping auto-detect){RESET}")
    else:
        input("Press Enter to start auto-detect, or Ctrl-C to abort...")
        bitrate = auto_detect_bitrate()
        time.sleep(0.5)

    try:
        if watch_ids:
            live_view_filtered(bitrate, watch_ids, capture_writer)
        else:
            live_view_wide(bitrate, capture_writer)
    finally:
        if capture_writer:
            print_paste_summary(capture_writer, capture_path, watch_ids)
            close_capture_writer(capture_writer)
            print(f"\n{BOLD}capture file: {capture_path}{RESET}")
            if args.git_save:
                git_save_capture(capture_path, args.git_save)


if __name__ == "__main__":
    main()
