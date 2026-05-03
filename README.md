# tesla-rack-control

Laptop-side Python tools for commanding a 2013 Tesla Model S EPAS rack over CAN.

The rack must already be flashed with [gregjhogan's pre-AP EPAS firmware patch](https://github.com/gregjhogan/tesla-pre-ap-epas-patch). With the patch in place, the rack accepts `0x488 DAS_steeringControl` messages directly without the GTW/EPB gating.

## Files

### Code

- `move.py` — **Simplest possible.** ~120 lines. Run `python move.py 15` and the wheel goes to +15°. Ctrl-C to disengage. No GUI, no rate limit, no watchdog. Heavily commented so you can read and understand the entire CAN protocol.
- `tesla_steering_test.py` — Full Tkinter GUI. Slider sets target angle, sends `0x488` at 50 Hz with valid checksum and counter, listens for `0x370 EPAS_sysStatus`. Hard angle clamp ±90°, rate limit 50°/sec, big red E-STOP, ESC key, multiple watchdog failsafes.
- `can_sniffer.py` — Passive CAN bus listener. Auto-detects baud rate (500/250/125 kbps), highlights known Tesla IDs, decodes `0x370` so you can verify wiring before sending anything.

### Documentation (read these before running anything)

- `READ_ME_FIRST.txt` — Plain-English overview of the project status and the order to do things in.
- `WIRING_DIAGRAM.pdf` — One-page printable. SYS TEC DB9 ↔ Tesla OBD-II pin-by-pin with safety notes.
- `PINOUT_VERIFICATION.pdf` — Two-page procedure for confirming chassis CAN is on OBD-II pins 1/9 (multimeter checks + sniffer test).
- `INSTRUCTION_MANUAL.pdf` — Two-page Windows install + first-run guide.
- `SETUP.md` — Longer text reference for installing the SYS TEC driver and python-can.

## Hardware tested with

- SYS TEC USB-CANmodul1 (model 3204001) on Windows. python-can `systec` interface.
- Connects to chassis CAN at OBD-II pin 1 (CH+) and pin 9 (CH-) per [Tinkla wiki](https://web.archive.org/web/20221201213432/https://tinkla.us/index.php/Tesla_Model_S_preAP_OBD2_port).

## Install

```
pip install python-can
```

Plus SYS TEC's Windows driver (USBCAN32.dll) from systec-electronic.com.

## Run

```
python tesla_steering_test.py
```

## Configuration (top of `tesla_steering_test.py`)

| Flag | Default | Meaning |
|---|---|---|
| `IN_CAR_MODE` | `True` | True: rack is in car, stock GTW/EPB still on bus, we don't send `0x101`/`0x214`. False: bench, we synthesize them. |
| `BENCH_MODE` | `False` | Inject fake `0x155 ESP_B` vehicle speed so rack doesn't fault on `MIN_SPEED`. Bench only. |
| `HARD_ANGLE_LIMIT_DEG` | 90 | Refuses commands beyond this. |
| `MAX_RATE_DEG_PER_SEC` | 50 | Rate-limits commanded angle. Rack faults > 250°/s; 50 is well clear. |
| `DIVERGENCE_TRIP_ENABLED` | False | E-STOP if commanded vs measured angle differs by > 15°. Off until measured-angle decode is calibrated on bench. |

## Failsafes

All trigger immediate E-STOP (sets `controlType=0`, freezes commanded angle):

- No `0x370` received in 500 ms
- Rack reports `eacStatus = FAULT`
- Loop overrun > 100 ms
- Any TX/RX exception
- CAN bus error count > 50
- ESC key, E-STOP button, or window close
- Refuses ENGAGE before any `0x370` has been received
- Hard ±90° clamp on commands
- 50°/sec rate limit on commanded angle

## CAN protocol references

Verified against [opendbc tesla_can.dbc](https://github.com/commaai/opendbc/blob/master/opendbc/dbc/tesla_can.dbc) and [BogGyver pre-AP safety](https://github.com/BogGyver/openpilot/blob/tesla_0.7.10/panda/board/safety/safety_tesla.h).

- `0x488 DAS_steeringControl` (4 bytes, TX 50 Hz): angle = (degrees + 1638.35) × 10. Big-endian. Includes 4-bit counter and 8-bit checksum.
- `0x101 GTW_epasControl` (3 bytes): bench-mode TX only. Patched rack ignores content.
- `0x214 EPB_epasControl` (3 bytes): bench-mode TX only. Patched rack ignores content but requires presence on bus.
- `0x370 EPAS_sysStatus` (8 bytes, RX): `eacStatus` byte 6 bits 7-5; measured angle bytes 4-5 big-endian factor 0.1 offset -819.2.

Checksum algorithm for all: `(addr_low + addr_high + sum_data_bytes_except_checksum) & 0xFF`.

## Safety

This commands a 2013 Tesla EPAS rack. Misuse can damage the rack or cause uncommanded steering. Front wheels off the ground or tie rods disconnected before any active testing. Read the failsafe list above before running.
