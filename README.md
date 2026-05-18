# tesla-rack-control

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Status: bench-test](https://img.shields.io/badge/status-bench--test-orange.svg)](SAFETY.md)
[![Hardware: 2013 Tesla Model S pre-AP](https://img.shields.io/badge/hardware-2013_Tesla_Model_S_pre--AP-red.svg)](#hardware)

Laptop-side Python tooling for direct CAN-bus control of a 2013
Tesla Model S electric power-steering rack. Designed for racks
already flashed with
[gregjhogan's pre-AP EPAS firmware patch](https://github.com/gregjhogan/tesla-pre-ap-epas-patch).

The current program is `tesla_control.py` (v4.3.3). It needs only
a SYS TEC USB-CAN adapter and the patched rack. **No comma 3X is
required.**

**New in v5.0.0-rc1**: `tesla_control_rc.py` adds a Spektrum DX8 +
AR6200 + Arduino Nano RC bridge that drives the same rack from the
right-stick of the transmitter, with the AUX1 switch selecting R/N/D.
See [`docs/RC_SETUP.md`](docs/RC_SETUP.md) for binding and wiring.
The non-RC `tesla_control.py` is unchanged.

> **Read [SAFETY.md](SAFETY.md) before running anything.** This is
> hardware control code. Bugs have physical consequences.

---

## Contents

- [Quick start](#quick-start)
- [Repository layout](#repository-layout)
- [Hardware](#hardware)
- [Features](#features)
- [Documentation](#documentation)
- [Versions](#versions)
- [Authors](#authors)
- [License](#license)

---

## Quick start

### One-click install (Windows)

For Jordan / Charlie / anyone setting up a fresh laptop:

1. Install **32-bit Python 3.9+** from https://www.python.org/ — tick
   "Add Python to PATH" during install. 32-bit is required because
   the SYS TEC `USBCAN32.dll` is 32-bit.
2. Download
   [`Install_Tesla_Rack_Control.bat`](https://raw.githubusercontent.com/dnage76-beep/tesla-rack-control/main/Install_Tesla_Rack_Control.bat)
   (right-click → Save link as…) and **double-click it**. The script
   pulls the latest version of Tesla Rack Control into
   `%USERPROFILE%\TeslaRackControl`, pip-installs the dependencies,
   and drops a **"Tesla Rack Control"** shortcut on the desktop.
3. Install the **SYS TEC sysWORXX USB-CAN driver** from
   https://www.systec-electronic.com/en/services-support/downloads.
   Vendor-proprietary, so we can't auto-install it.

If Windows SmartScreen flags the .bat: click "More info" → "Run anyway".

#### Fallback if your network blocks the .bat

Some corporate machines block batch-file downloads or PowerShell
network calls. In that case:

1. Browse to https://github.com/dnage76-beep/tesla-rack-control.
2. Click **Code → Download ZIP**. (GitHub itself is rarely blocked.)
3. Extract the zip to `C:\Users\<you>\TeslaRackControl`.
4. Double-click `install.bat` inside that folder.

The launcher's auto-updater works the same either way — it only needs
`api.github.com` and `codeload.github.com`, both of which are reachable
from any network where GitHub itself works.

After install, double-click the **Tesla Rack Control** desktop icon
and you'll get the desktop suite — sidebar with Dashboard, Run
Steering Test, CAN Sniffer, Session Logs, CAN Captures, Documentation,
Updates, About. The Run Test screen launches `tesla_control.py` (the
real CAN-bus control program) in its own window.

### Manual install (developers)

```sh
git clone https://github.com/dnage76-beep/tesla-rack-control
cd tesla-rack-control
pip install -r requirements.txt
python app.py            # the desktop suite
# or directly:
python tesla_control.py  # just the control GUI
```

Developer checkouts (folders with a `.git/` subdirectory) skip the
launcher's auto-update prompt — manage versions with `git pull` directly.

For the full operating procedure, read [`docs/GUIDE.md`](docs/GUIDE.md).
For debugging, read [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

---

## Repository layout

```
.
├── README.md                  this file
├── SAFETY.md                  hard rules, defense in depth
├── CHANGELOG.md               version history
├── CONTRIBUTING.md            contribution guide
├── LICENSE                    MIT
├── requirements.txt           pip dependencies
│
├── tesla_control.py           the live CAN-bus control program (v4.3.3)
├── tesla_control_rc.py        v5.0.0-rc1 RC variant (DX8 + AR6200 + Arduino)
├── arduino/tesla_rc_bridge/   Arduino Nano firmware for the RC bridge
├── app.py                     desktop suite shell (sidebar, logs viewer, etc.)
├── launcher.py                update-checker (HTTP/zip), then loads app.py
├── launcher.bat               Windows double-click wrapper for launcher.py
├── Install_Tesla_Rack_Control.bat  one-click installer (download + extract + setup)
├── install.bat                local-folder setup (pip + shortcut, source already present)
├── make_shortcut.py           creates a desktop .lnk on Windows
├── can_sniffer.py             passive CAN bus listener
│
├── docs/
│   ├── GUIDE.md               operating guide
│   ├── TROUBLESHOOTING.md     symptom-driven debugging
│   ├── PROTOCOL.md            CAN protocol reference
│   └── RC_SETUP.md            v5: Spektrum + Arduino bridge wiring + binding
│
├── archive/
│   ├── legacy/                v1, v2, v3, v4 programs (see archive/legacy/README.md)
│   ├── pdfs/                  original Jordan-facing PDF documentation
│   └── notes/                 conversation snapshots, field-test plans
│
├── field_testing/             session photos and Charlie's field logs
└── logs/                      session .log + .csv files (gitignored)
```

Each subdirectory has its own README explaining what is in it.

---

## Hardware

| Component         | Tested with                                                |
|-------------------|------------------------------------------------------------|
| Vehicle           | 2013 Tesla Model S, post-May-31 build, pre-AP              |
| Steering rack     | EPAS rack flashed with gregjhogan's pre-AP firmware patch  |
| CAN adapter       | SYS TEC sysWORXX USB-CANmodul1 (model 3204001)             |
| Host OS           | Windows 10 / 11                                            |
| CAN tap point     | OBD-II pins 1/9, OR X437/TDC connector under center screen |
| Rack tap          | EPAS X119 connector (bench testing)                        |

What you do **not** need: comma 3X, comma 3, comma 2, comma red
panda, or any other comma device. A comma device on the bus while
`tesla_control.py` is running causes the EAC flicker bug from the
May 2026 field tests; v4 was specifically designed to remove the
dependency.

---

## Features

- **Single-program control**: GUI, CAN bus, safety, logging in one
  file. No external services, no internet.
- **Two input modes**: SLIDER for precise angle steps, KEYBOARD for
  fluid arrow-key driving with a steering-wheel canvas widget.
- **Live bus diagnostic panel**: per-ID frame rates with red
  flagging for contention bugs (`0x488` second transmitter,
  `0x155` ESP fight under 30 MPH MODE).
- **Optional 30 MPH MODE**: runtime toggle that synthesizes
  vehicle speed at 200 Hz to unlock the rack's at-speed envelope
  (more angle, more rate, more torque). Off at boot.
- **Per-session logging**: `./logs/session_*.log` (events) plus
  `./logs/session_*.csv` (per-frame state) for offline analysis.
- **Defense-in-depth safety**: hard angle clamp, rate limit, LPF,
  RX-timeout watchdog, divergence trip (opt-in), bus-error trip,
  loop-overrun trip, four E-STOP paths.

---

## Documentation

- [PROJECT_MEMORY.md](PROJECT_MEMORY.md) -- canonical reference of
  what's true, with sources cited. Read this first.
- [ROADMAP.md](ROADMAP.md) -- phased plan from current state to RC
  car to openpilot integration.
- [V5_PLAN.md](V5_PLAN.md) -- detailed plan for v5 (full vehicle
  control: throttle, brake, gear, steering). On
  `dev/v5-longitudinal` branch.
- [docs/build/ROADMAP.pdf](docs/build/ROADMAP.pdf) -- printable
  professional version of the roadmap with wiring diagrams and
  flowcharts. Regenerate with `python docs/build/build_pdf.py`.
- [docs/GUIDE.md](docs/GUIDE.md) -- setup, operating procedure,
  configuration, mode reference.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) -- symptom
  decision tree, EAC error code table, E-STOP reason table, log
  reading guide.
- [docs/PROTOCOL.md](docs/PROTOCOL.md) -- complete CAN protocol
  reference: message encodings, checksums, EAC enums, sign
  convention, standstill vs at-speed envelope.
- [SAFETY.md](SAFETY.md) -- hard rules and defense-in-depth.
- [CHANGELOG.md](CHANGELOG.md) -- full version history.

---

## Versions

| Version | Status        | File                                                | Headline                                       |
|---------|---------------|-----------------------------------------------------|------------------------------------------------|
| v5.0.0-rc1 | **rc**     | `tesla_control_rc.py` + `arduino/tesla_rc_bridge/`  | Spektrum DX8 + AR6200 + Arduino Nano RC bridge |
| v4.3.3  | **current**   | `tesla_control.py`                                  | Image wheel + PRND keys while steering         |
| v4.3.0  | superseded    | `tesla_control.py` @ tag v4.3.0                     | HARD_ANGLE_LIMIT_DEG raised to 360 (lock-to-lock) |
| v4.2.1  | superseded    | `tesla_control.py` @ tag v4.2.1                     | Non-blocking shift burst, fixes EPAS_d039_kfc_reset |
| v4.2.0  | superseded    | `tesla_control.py` @ tag v4.2.0                     | PRND shift, brake read, vitals strip, save-to-GitHub |
| v4.1.0  | superseded    | `tesla_control.py` @ tag v4.1.0                     | Adds runtime 30 MPH MODE toggle                |
| v4.0    | superseded    | `archive/legacy/tesla_control_v4.py`                | First no-3X version, unified GUI               |
| v3.0    | superseded    | `archive/legacy/steer.py`                           | Keyboard-only variant with wheel canvas        |
| v2.0    | superseded    | `archive/legacy/tesla_steering_test.py`             | First full GUI with safety architecture        |
| v1.0    | superseded    | `archive/legacy/move.py`                            | One-shot CLI angle command                     |

See [CHANGELOG.md](CHANGELOG.md) for full release notes and
[archive/legacy/README.md](archive/legacy/README.md) for the lineage
in narrative form.

The wire-level CAN protocol has not changed across versions. The
patched rack from gregjhogan's flash is compatible with all of them.

---

## Authors

- **Derek Nagel** -- project owner, software lead
  ([`@dnage76-beep`](https://github.com/dnage76-beep))
- **Jordan** -- hardware lead, EPAS firmware flash, harness work
- **Charlie Yonkura** -- field testing, session logs
  ([`@LinuxLover3000`](https://github.com/LinuxLover3000))
- **Claude** -- pair programmer

This project is a sub-component of Derek's broader Tesla Auto Repair
Business with Jordan.

---

## License

MIT. See [LICENSE](LICENSE).

The MIT license includes a standard "AS IS" disclaimer. This software
controls a real EPAS rack on a real car. Read [SAFETY.md](SAFETY.md)
and accept all risk before running anything.
