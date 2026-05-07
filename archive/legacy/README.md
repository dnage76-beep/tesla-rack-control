# Archived legacy programs

These are earlier iterations of the steering control program. They
are kept for reference and historical traceability. **Do not run
them on real hardware.** Use `tesla_control.py` at the repo root.

For a fuller release history, see [CHANGELOG.md](../../CHANGELOG.md).

---

## Lineage

```
v1  move.py                  one-shot CLI
v2  tesla_steering_test.py   first full GUI with safety architecture
v3  steer.py                 keyboard-only variant of v2
v4  tesla_control_v4.py      first unified program; no comma 3X required
v4.1 tesla_control.py        adds the runtime 30 MPH MODE toggle (CURRENT)
```

---

## v1.0 -- `move.py` (March 2026)

The first working steering command from a laptop. ~120 lines, every
line commented. CLI only: `python move.py 15` commands the wheel to
+15 degrees, Ctrl-C disengages.

Used to verify the CAN protocol byte-for-byte against
`opendbc/tesla_can.dbc`. The protocol code in v4.1 is a direct
descendant.

**Status**: superseded by v4.1 SLIDER mode and the `tesla_control.py`
CLI banner. Kept for the inline protocol comments.

## v2.0 -- `tesla_steering_test.py` (April 2026)

The first full GUI. Tkinter window with a slider for target angle, a
status panel showing EAC state, an event log, and a big red E-STOP
button. Established the safety architecture that v4 still inherits
verbatim:

- Hard angle clamp (90 deg in v2; 180 in v4.1)
- Rate limit (50 deg/s in v2; 150 in v4.1)
- LPF on user target (150 ms tau)
- RX-timeout watchdog (500 ms)
- Divergence trip (opt-in)
- Bus-error trip (>50)
- Loop-overrun trip (>100 ms)
- Four E-STOP paths (button, ESC, Q, window close)

This is the stable workhorse Charlie used during the May 2026 field
tests. The E-STOP-cannot-be-cleared bug was found and fixed in this
file before v4 inherited the fix.

**Status**: superseded by `tesla_control.py`. The architecture lives
on in v4.1 essentially unchanged.

## v3.0 -- `steer.py` (April 2026)

Parallel artifact to v2, not a strict successor. Built for ergonomic
"feel" testing rather than precision angle commands. Hold LEFT or
RIGHT arrow to steer continuously, SPACE to recenter, Q or ESC to
disengage. Soft +/- 60 degree clamp. Steering wheel canvas widget
that rotates with the commanded angle.

**Status**: superseded by v4.1 KEYBOARD mode. The wheel canvas was
lifted into v4 unchanged. Kept here as the original keyboard-driving
reference.

## v4.0 -- `tesla_control_v4.py` (May 2026)

First unified program. Combined the safety architecture from v2 with
the keyboard mode + wheel canvas from v3, and added:

- Synthesis of `0x214 EPB_epasControl` from the SYS TEC adapter,
  removing the comma 3X dependency
- Bus diagnostic panel with live per-ID frame rates
- Per-session logs to `./logs/` (`.log` + `.csv`)

**Status**: superseded by v4.1. v4.1 with the 30 MPH MODE toggle in
the OFF position is functionally identical to v4. v4 is kept here so
the diff between v4 and v4.1 is easy to inspect.

---

## What did NOT change across versions

The wire-level CAN protocol. Every program in this folder speaks the
same `0x488 / 0x101 / 0x214 / 0x370` bytes that v4.1 speaks, with
the same checksums and counter logic. The patched rack from
gregjhogan's flash is compatible with all of them.
