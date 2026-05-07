# tesla-rack-control

Laptop-side Python tools for commanding a 2013 Tesla Model S EPAS
rack over CAN. Designed for the rack already flashed with
[gregjhogan's pre-AP EPAS firmware patch](https://github.com/gregjhogan/tesla-pre-ap-epas-patch).

The current program is `tesla_control_v4_1.py`. It needs only a
SYS TEC USB-CANmodul1 and the patched rack. **No comma 3X required.**

---

## Repository layout

```
.
├── README.md                  this file
├── tesla_control_v4_1.py      the program -- run this
├── can_sniffer.py             passive CAN bus listener
├── docs/
│   ├── GUIDE.md               operating guide for v4.1
│   ├── TROUBLESHOOTING.md     symptom-driven debugging
│   └── PROTOCOL.md            CAN protocol reference
├── archive/
│   ├── legacy/                older programs (move.py, steer.py, ...)
│   ├── pdfs/                  original Jordan-facing PDFs
│   └── notes/                 conversation snapshots, field-test plans
├── field_testing/             session photos and Charlie's field logs
└── logs/                      session .log + .csv files (gitignored)
```

Each subdirectory has its own README explaining what is in it.

---

## Quick start

```
pip install python-can
```

Plus the SYS TEC sysWORXX USB-CAN driver from
https://www.systec-electronic.com/en/services-support/downloads.

Then:

```
python tesla_control_v4_1.py
```

For the operating procedure, see [`docs/GUIDE.md`](docs/GUIDE.md).
For debugging, see [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

---

## Hardware

- 2013 Tesla Model S, post-May-31 build, pre-AP. EPAS rack flashed
  with gregjhogan's patch.
- SYS TEC sysWORXX USB-CANmodul1 (model 3204001), Windows 10+.
- The custom OBD-to-X119 (or X437/TDC) harness Jordan built.

What you do **not** need: comma 3X, comma 3, comma 2, red panda,
any other comma device. A comma device on the bus while v4.1 is
running causes the EAC flicker bug from the May 2026 field tests.

---

## Safety

This commands a real EPAS rack that applies real force. Misuse can
damage the rack, strain a tie rod, dent a fender, or cause
uncommanded steering. Front wheels off the ground or tie rods
disconnected before any active testing.

The program enforces a hard angle clamp, rate limit, and multiple
watchdog failsafes. Full failsafe list is in
[`docs/GUIDE.md`](docs/GUIDE.md). All E-STOP paths are documented in
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

---

## Versions

| Version | Status                | Notes                                                           |
|---------|-----------------------|------------------------------------------------------------------|
| v4.1    | **current**           | Adds runtime 30 MPH MODE toggle. Default behavior matches v4.    |
| v4      | superseded            | First no-3X version. Lives at `archive/legacy/tesla_control_v4.py`. |
| pre-v4  | superseded, archived  | `move.py`, `steer.py`, `tesla_steering_test.py`. See `archive/legacy/README.md`. |

The wire-level CAN protocol has not changed across versions. The
patched rack from gregjhogan's flash is compatible with all of them.

---

## Authors

- Derek Nagel (project owner, software lead)
- Jordan (hardware lead, EPAS firmware flash)
- Charlie Yonkura (field testing, session logs)
- Claude (pair programmer)
