# Archived legacy programs

These are earlier iterations of the steering control program. They
are kept for reference and historical traceability. **Do not run
them on real hardware.** Use `tesla_control_v4_1.py` at the repo
root instead.

| File                      | What it was                                                                  | Superseded by                                |
|---------------------------|------------------------------------------------------------------------------|----------------------------------------------|
| `move.py`                 | One-shot CLI angle command, ~120 lines, every line commented                 | `tesla_control_v4_1.py` SLIDER mode          |
| `steer.py`                | Live keyboard steering GUI with steering-wheel canvas                        | `tesla_control_v4_1.py` KEYBOARD mode        |
| `tesla_steering_test.py`  | Full GUI with slider, status panel, event log, multiple watchdogs            | `tesla_control_v4_1.py` (architecture base)  |
| `tesla_control_v4.py`     | First no-3X version. v4.1 is v4 plus the 30 MPH MODE toggle.                 | `tesla_control_v4_1.py`                      |

The CAN protocol code (message builders, 0x370 decode) in v4.1 is
byte-identical to the versions in `tesla_steering_test.py` and the
older programs. The rack-side wire protocol has not changed.
