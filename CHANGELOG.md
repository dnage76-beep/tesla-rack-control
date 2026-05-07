# Changelog

All notable changes to this project. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project follows a loose semantic-versioning scheme (see
[CONTRIBUTING.md](CONTRIBUTING.md)).

## [Unreleased]

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
