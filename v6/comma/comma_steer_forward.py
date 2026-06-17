"""
comma_steer_forward.py  --  runs ON the comma 3X (in the openpilot env)
=======================================================================

Reads openpilot's live steering command and forwards it over a plain
TCP socket to the laptop running tesla_control_comma.py, which turns it
into 0x488 DAS_steeringControl on the chassis bus.

WHY THIS LIVES ON THE COMMA
    openpilot's actuator command is published on the cereal message
    `carControl`, field `actuators.steeringAngleDeg` (degrees). The
    Tesla port is an ANGLE-control car (opendbc/car/tesla/interface.py:
    `steerControlType = angle`), so steeringAngleDeg is the meaningful
    command. cereal/msgq only run cleanly inside the openpilot
    environment (Linux/AGNOS), so we subscribe here and emit a tiny,
    dependency-free message the Windows laptop can read with nothing
    but a socket.

VERIFIED SOURCE BASIS (inspected 2026-06-16)
    - carControl.actuators.steeringAngleDeg  -- opendbc/car/car.capnp
      struct Actuators @3; set by controlsd.py:137
    - carControl.latActive / .enabled        -- car.capnp struct CarControl
    - messaging.SubMaster(['carControl', ...]).update / ['carControl']
      -- cereal/messaging/__init__.py
    Tesla pre-AP engagement is via the cruise stalk (STW_ACTN_RQ /
    SpdCtrlLvr_Stat == 2 "RWD"/pull-toward); when the stalk engages
    openpilot, latActive goes true and we forward that flag.

WIRE FORMAT  (newline-delimited JSON, one object per CAN- ish tick)
    {"seq": int, "t": float (comma monotonic s),
     "angle_deg": float, "lat_active": bool, "enabled": bool,
     "alive": bool, "valid": bool, "vego": float}
    Reliable, ordered TCP stream; '\n' is the frame delimiter. JSON is
    deliberately human-readable so you can `nc <comma_ip> 7654` and watch
    it during bring-up.

SAFETY / TOPOLOGY
    The comma's panda must NOT transmit 0x488 -- the laptop is the sole
    transmitter of that arbitration id (Theory C, PROJECT_MEMORY.md
    Section 8). This script only READS cereal; it never touches CAN.

USAGE  (on the comma, over SSH)
    cd /data/openpilot
    PYTHONPATH=. python /data/comma_steer_forward.py --port 7654
    # then on the laptop:  python tesla_control_comma.py --comma-host <ip>
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time

try:
    import cereal.messaging as messaging
except Exception as e:  # pragma: no cover - only importable on the comma
    print("ERROR: cereal not importable. Run this ON the comma 3X from "
          "inside /data/openpilot with PYTHONPATH=.  (%s)" % e,
          file=sys.stderr)
    sys.exit(1)


SEND_HZ = 100.0           # forward rate; carControl publishes at 100 Hz
SEND_PERIOD = 1.0 / SEND_HZ


def serve(host: str, port: int) -> None:
    sm = messaging.SubMaster(["carControl", "carState"])

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(1)
    print(f"comma_steer_forward: listening on {host}:{port} (Ctrl-C to quit)")

    seq = 0
    while True:
        print("comma_steer_forward: waiting for laptop to connect ...")
        conn, peer = srv.accept()
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print(f"comma_steer_forward: laptop connected from {peer}")
        try:
            next_send = time.monotonic()
            while True:
                # Block up to one period waiting for fresh cereal, then
                # send the latest snapshot regardless so the laptop gets
                # a steady heartbeat it can use for link-loss detection.
                sm.update(int(SEND_PERIOD * 1000))
                cc = sm["carControl"]
                cs = sm["carState"]
                msg = {
                    "seq": seq,
                    "t": round(time.monotonic(), 4),
                    "angle_deg": float(cc.actuators.steeringAngleDeg),
                    "lat_active": bool(cc.latActive),
                    "enabled": bool(cc.enabled),
                    "alive": bool(sm.alive["carControl"]),
                    "valid": bool(sm.valid["carControl"]),
                    "vego": round(float(cs.vEgo), 3),
                }
                seq += 1
                line = (json.dumps(msg, separators=(",", ":")) + "\n").encode()
                try:
                    conn.sendall(line)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    print("comma_steer_forward: laptop disconnected")
                    break

                # Pace to SEND_HZ even if cereal returned early.
                next_send += SEND_PERIOD
                slack = next_send - time.monotonic()
                if slack > 0:
                    time.sleep(slack)
                else:
                    next_send = time.monotonic()
        finally:
            try:
                conn.close()
            except OSError:
                pass


def parse_args():
    p = argparse.ArgumentParser(
        description="Forward openpilot steeringAngleDeg to the rack laptop")
    p.add_argument("--host", default="0.0.0.0",
                   help="bind address (default 0.0.0.0 = all interfaces)")
    p.add_argument("--port", type=int, default=7654,
                   help="TCP port to listen on (default 7654)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        serve(args.host, args.port)
    except KeyboardInterrupt:
        sys.exit(0)
