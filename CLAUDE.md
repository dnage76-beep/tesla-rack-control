# tesla-rack-control

Pre-AP Tesla Model S EPAS rack control over CAN. Laptop-side Python tools for commanding a 2013 Model S steering rack flashed with [gregjhogan's pre-AP EPAS firmware patch](https://github.com/gregjhogan/tesla-pre-ap-epas-patch).

Evenings project with Charlie Yonkura (software) and Jordan Horwitz (hardware). Independent of the Tesla Auto Repair Business, which is parked.

---

## Hard rules for this repo

1. **`SAFETY.md` is authoritative and non-negotiable.** Front wheels off the ground, no passengers, no public roads, hands off during ENGAGE. Read it before touching any control code.
2. **Don't run any steering entry point unsupervised.** `tesla_control.py` (main) and `tesla_control_rc.py` (v5 branches) send torque commands to a real rack. Read-only inspection (`can_sniffer.py`) is fine.
3. **The rack must be flashed before any command will work.** If it stays at `INHIBITED`, see `archive/pdfs/FLASH_AND_TROUBLESHOOTING.pdf` (v3-era doc, procedure still applies).
4. **No em dashes in this repo's docs and comments** (Derek's preference). Use `--`. Style rule only; there is no enforcing hook.

---

## Current state: read pointers, don't trust snapshots

Hard-coded status in this file goes stale. For where the project actually is, read in order:
1. `charliereadthis.md` -- current Charlie handoff (v5 RC bridge)
2. `CHANGELOG.md` and `git log --oneline -10`
3. `PROJECT_MEMORY.md` -- accumulated decisions

Branch map:
- `main` -- v4.3.3 production (slider + keyboard control; PRND shift, brake decode, 30 MPH MODE, lock-to-lock clamp)
- `dev/v5-rc` -- v5 RC bridge, Spektrum DX8 + AR6200 (plane sticks)
- `dev/v5-slt3` -- v5 RC bridge, SLT3 + SR315 (wheel + trigger); usual working branch

The May 2026 EAC-flicker saga is resolved: Theory C was the confirmed cause (`PROJECT_MEMORY.md` section 8) and the EAC-bounce watchdog (v4.2+, documented in `SAFETY.md`) catches that pattern.

---

## Hardware

- 2013 Tesla Model S EPAS rack; OBD-II pins 1 (CH+) and 9 (CH-) for chassis CAN
- SYS TEC USB-CANmodul1 (model 3204001), Windows-only driver via `USBCAN32.dll`
- Arduino Nano RC bridge (`arduino/tesla_rc_bridge/tesla_rc_bridge.ino`): 3 PWM channels, COBS+CRC8 framing at 100 Hz into `tesla_control_rc.py`
- Comma 3X for re-flashing EPAS via BogGyver `tesla_unity_releaseC3` branch

## Software stack

Python 3.10+, `python-can` with `systec` interface, Tkinter GUIs. No build system, no tests; each script runs standalone. `tesla_control_rc.py` subclasses the v4.3.3 base program; no CAN protocol changes in v5.

## Files at a glance

- `tesla_control.py` -- v4.3.3 main control program (main branch)
- `tesla_control_rc.py` -- v5 RC-bridge control program
- `can_sniffer.py` -- passive listener, no torque output
- `docs/` -- GUIDE, PROTOCOL, TROUBLESHOOTING, RC_SETUP + `docs/build/RC_IMPLEMENTATION_GUIDE*.pdf`
- `SAFETY.md`, `PROJECT_MEMORY.md`, `CHANGELOG.md`, `charliereadthis.md`
- `archive/` -- v3-era legacy (old scripts, NOTES_FOR_CHARLIE, PDFs). Historical reference only; never run anything from here.

---

## Don't do

- Don't restructure into a package or add `setup.py`. Flat files are intentional; collaborators copy files individually.
- Don't add a CI pipeline. Tests live in the field, not on GitHub Actions.
- Don't add abstractions around the CAN protocol; it's the simplest part and wrapping it in a "Driver"/"Service" hurts readability.
- Don't push to main without Derek's review. Charlie has commit access; his PRs need Derek's approval before merge.
