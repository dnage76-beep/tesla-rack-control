# Changelog

All notable changes to this project. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows a loose semantic-versioning scheme (see
[CONTRIBUTING.md](CONTRIBUTING.md)).

## [Unreleased]

## [4.2.0-dev] -- in progress on `dev/v4.2-prnd`

### Added (UI overhaul)
Complete restructure of the GUI for a more professional look. All
prior features preserved.

- **Vitals strip** across the top: at-a-glance colored pills for
  LINK / EAC / GEAR / BRAKE / 30 MPH / SHIFT. Each pill is a
  colored dot + label + value, readable from across the room.
- **Sectioned panels** with consistent small-caps headings, a
  subtle border, and proper padding. New helper `_section()` and
  `_stat()` keep styling uniform.
- **Brake cell** in the new Vehicle Status panel. Brake state was
  decoded earlier; v4.2 finally surfaces it in the GUI.
- **Vehicle Status panel** groups gear / gear-req / brake /
  brake-state / DI-speed / park-gate together (separate from
  Rack Status which now holds only EPAS-specific values).
- **Status bar** at the bottom: shows active session path, current
  rack EAC state, and elapsed session time (mm:ss).
- **Window grew** from 1080x920 to 1280x920; minsize 1180x800.
- **GitHub-dark color palette**: tighter contrast, more
  "instrumentation panel" than original flat dark theme.
- **No clipped text**: bus diagnostic and stat cells now use
  explicit minsize widths so values are never cut off.

### Added (save test to GitHub)
- New **SAVE TEST** button in the action bar (replaces the old
  SAVE LOG button).
- Modal dialog asks for a short test name and an optional
  description.
- Background thread copies the active session's `.log` and `.csv`
  into `field_testing/sessions/<timestamp>_<name>/`, generates a
  `README.md` with metadata (elapsed time, EAC state, gear,
  brake, errors, etc.), then runs `git add` + `git commit -m
  "test: <name>"` + `git push origin <current-branch>`.
- All git output streams to the event log. If push fails (no
  auth, no network), files are committed locally and the user is
  shown the manual command to push.
- Session export keeps the live session running -- the dialog
  doesn't disconnect.

### Added (gear shift -- EXPERIMENTAL)
- Four shift buttons in the GUI: **P / R / N / D**.
- New CAN message: `0x6D SBW_RQ_SCCM` (Shift By Wire Request from
  Steering Column Module). 4 bytes. Carries `TSL_RND_Posn_StW`
  (R/N/D position) and `TSL_P_Psd_StW` (Park button), counter at
  bit 20, CRC at bit 24.
- New helper `tesla_crc8()` implementing CRC-8/AUTOSAR (poly 0x2F,
  init 0xFF, XOR-out 0xFF) for any future Tesla messages that need
  it. **Untested in-car**: if the first shift attempt is silently
  ignored, the CRC is the most likely culprit. Capture a real
  stalk frame on the bus and verify byte 3.
- New helper `build_sbw_rq(rnd, p, counter)` produces a complete
  4-byte 0x6D frame with valid CRC.
- Worker thread method `_execute_shift_burst()`: when GUI queues a
  shift, sends 10 active frames at 100 Hz with the requested gear
  encoded, then 5 IDLE frames as a settling tail, then logs the
  resulting `DI_gear` for verification.
- Bus diagnostic adds `0x6D` row.

### Added (gear shift safety gates)
- Shift request refused unless: not in E-STOP, not engaged, no
  shift already in flight, brake pedal pressed (when DI is on the
  bus), real speed < 1 mph for R/D shifts.
- Brake-not-pressed message logged loudly so the user knows what
  to do.
- "Shift in flight" lock prevents overlapping shift bursts from
  rapid clicks.

### Added (PRND awareness)
- Listens to `0x118 DI_torque2` and decodes `DI_gear`,
  `DI_gearRequest`, and `DI_vehicleSpeed` (DI's own speed estimate,
  useful for verifying the 30 MPH MODE spoof is not propagating
  somewhere it shouldn't).
- Status panel grows to 3 rows: adds Gear, Gear Request, DI Speed,
  Park Gate cells.
- Bus diagnostic panel adds `0x118 DI_torque2 (gear)`.
- Session CSV adds `gear`, `gear_request`, `di_vehicle_speed_mph`
  columns.
- Gear transition events written to the `.log` file.

### Added (safety guards)
Derek's first 30 MPH MODE in-car test "freaked out" the car
(ESP contention cascaded into other ECUs). These guards prevent
that exact failure mode and several adjacent ones:

- **Park-to-engage gate**. When `0x118` is being received and the
  gear is not P, ENGAGE is refused with a clear log message.
  Bypassed automatically when `0x118` has never been received
  (bench mode). Configurable via `REQUIRE_PARK_TO_ENGAGE` (default
  `True`).
- **30 MPH MODE pre-flight ESP check**. If real ESP traffic is
  detected on `0x155` above `ESP_PREFLIGHT_REFUSE_HZ` (1 Hz), the
  toggle refuses to enable. The original test would have been
  prevented by this guard.
- **30 MPH MODE mid-session auto-disable**. If real ESP traffic
  appears (or returns) while 30 MPH MODE is on, the toggle flips
  itself off within one tick.
- **Auto-disengage on gear-out-of-P**. If engaged and the gear
  leaves Park, the worker disengages on the next 50 Hz tick.
- **Auto-disengage on real motion**. If `DI_vehicleSpeed` (the
  car's own estimate, NOT our spoof) goes above 1 mph, the worker
  disengages.
- **EAC-bounce watchdog**. If we see more than 5 EAC status
  transitions in any 1-second window, auto-E-STOP. Catches the
  May 2026 flicker pattern automatically.
- GUI buttons (`ENGAGE`, `30 MPH MODE`) now resync their labels
  when the worker thread auto-disables them.

### Changed
- Window height increased from 860 to 920 px to fit the new row.
- `__version__` bumped to `4.2.0-dev`.

### Notes
- Wire-level CAN protocol unchanged. Patched rack remains compatible.
- All v4.2 watchdogs are configurable via the constants at the top
  of `tesla_control.py`. Default values err on the side of safety.
- The 30 MPH MODE toggle is intentionally still available, but the
  pre-flight check makes it impossible to enable in-car (where
  real ESP is alive). It can be enabled on a bench setup with the
  ESP module disconnected, which is the only configuration where
  it was ever safe to use.

## [4.1.0] -- 2026-05-07

### Added
- **Runtime 30 MPH MODE toggle** in the GUI action bar. Off at boot.
  When enabled, transmits `0x155 ESP_B` at 200 Hz claiming 30 km/h
  to convince the patched rack the car is moving and unlock the
  at-speed envelope (more angle, more rate, more torque).
- ESP contention detection. When 30 MPH MODE is on and the real
  Tesla ESP module is also transmitting `0x155`, the bus diagnostic
  `0x155` row turns red and a warning line appears in the keepalive
  panel.
- `__version__` constant in `tesla_control.py`.

### Changed
- Hard angle clamp raised from 60 to 180 degrees.
- Rate limit raised from 50 to 150 deg/sec.
- Keyboard mode steer rate raised from 30 to 90 deg/sec.
- Angle divergence trip threshold raised from 15 to 30 degrees.
- Toggling 30 MPH MODE while engaged is refused (you must disengage
  first to prevent the rack's torque envelope from jumping).

### Notes
- The wire-level CAN protocol has not changed. The rack flashed
  with gregjhogan's pre-AP EPAS patch is fully compatible.
- With 30 MPH MODE OFF, behavior is functionally identical to v4.

---

## [4.0.0] -- 2026-05-06

### Added
- `tesla_control_v4.py`: single-program steering control that does
  not require a comma 3X. Synthesizes `0x214 EPB_epasControl`
  directly from the SYS TEC adapter at 10 Hz.
- Switchable SLIDER and KEYBOARD input modes in one window.
- Steering wheel canvas in keyboard mode (lifted from v3 / steer.py).
- Bus diagnostic panel with live per-ID frame rates. The `0x488` row
  turns red on any non-zero RX, surfacing the EAC flicker bug from
  the May 2026 field tests.
- Per-session logging to `./logs/`: human-readable `.log` plus
  per-frame `.csv`.
- `GUIDE_V4.md` and `TROUBLESHOOTING_V4.md` (later moved to `docs/`).

### Changed
- Default workflow no longer assumes a comma 3X is on the bus. The
  3X had been providing keepalive messages that we now provide
  ourselves.

### Diagnostic
- Theory C diagnosis written: the EAC flicker observed in May 2026
  is caused by the BogGyver panda firmware on the 3X transmitting
  `0x488` in parallel with our laptop, causing CAN arbitration
  contention. With the 3X removed, the contention disappears.

---

## [3.0.0] -- 2026-04 (`steer.py`, archived)

### Added
- `steer.py`: live keyboard-control GUI. Hold LEFT or RIGHT arrows
  to steer continuously, SPACE to recenter, Q or ESC to disengage.
- Steering wheel canvas widget that rotates with the commanded angle.
- Soft +/- 60 degree clamp, smoother output, on-screen state.

### Notes
- Originally a parallel artifact to v2 rather than a strict
  successor. Used for ergonomic feel testing. v4 absorbed its
  keyboard mode and canvas widget.
- Now lives at `archive/legacy/steer.py`.

---

## [2.0.0] -- 2026-04 (`tesla_steering_test.py`, archived)

### Added
- `tesla_steering_test.py`: full Tkinter GUI with slider input,
  status panel, event log, big red E-STOP, and the safety
  architecture that v4 still inherits verbatim.
- Hard angle clamp at +/- 90 degrees, rate limit 50 deg/sec.
- RX-timeout watchdog, divergence trip (opt-in), bus-error trip,
  loop-overrun trip.
- EAC transition logging.
- `IN_CAR_MODE` flag for in-car vs bench-with-no-GTW operation.
- E-STOP-cannot-be-cleared bug fix (after Charlie's 2026-05-04
  field test).
- LPF on slider target + deterministic 50 Hz timing
  (after the same field test).

### Notes
- The stable workhorse that survived May 2026 testing intact.
- Now lives at `archive/legacy/tesla_steering_test.py`.

---

## [1.0.0] -- 2026-03 (`move.py`, archived)

### Added
- `move.py`: ~120-line one-shot CLI. `python move.py 15` commands
  the wheel to +15 degrees. Ctrl-C disengages.
- Hard +/- 90 degree clamp, LPF smoothing (tau=0.15s), 50 Hz hybrid
  sleep.
- Heavily commented as a learning reference for the CAN protocol.

### Notes
- The first working steering command from a laptop. Used to verify
  the protocol byte-for-byte against `opendbc/tesla_can.dbc`.
- Now lives at `archive/legacy/move.py`.
