# comma 3X → rack steering bridge

Two small programs that let openpilot (the "brain", on the comma 3X)
steer the rack through our proven `tesla_control.py` CAN code (the
"actuator", on the laptop). See
[../V6_OPENPILOT_FORK_PLAN.md](../V6_OPENPILOT_FORK_PLAN.md) for the
architecture and why it is built this way.

```
comma 3X (openpilot)                         laptop (Windows)
controlsd                                    tesla_control_comma.py
  └ carControl.actuators.steeringAngleDeg      └ CommaLinkReader (TCP)
       └ comma_steer_forward.py  ── TCP ──►        └ ctrl.target_angle_deg
            (cereal SubMaster)                         └ CanWorker (unchanged)
                                                            └ 0x488 → SYS TEC → rack
```

| File | Runs on | Deps |
|---|---|---|
| `comma_steer_forward.py` | the comma 3X (openpilot env) | `cereal` (already on AGNOS) |
| `../../tesla_control_comma.py` | the laptop | same as `tesla_control.py` (no openpilot) |

## Run

1. **On the comma** (SSH in: `ssh comma@<ip>`), copy
   `comma_steer_forward.py` to `/data/`, then:
   ```
   cd /data/openpilot
   PYTHONPATH=. python /data/comma_steer_forward.py --port 7654
   ```
   You can watch the raw stream from any machine with
   `nc <comma_ip> 7654` — it is newline-delimited JSON.

2. **On the laptop:**
   ```
   python tesla_control_comma.py --comma-host <comma_ip> --comma-port 7654
   ```
   A wired USB-ethernet link to the 3X is strongly preferred over Wi-Fi
   for latency.

## Engagement

Pull the cruise stalk toward you → openpilot engages on the comma →
`carControl.latActive` goes true → the bridge mirrors it and starts
applying the angle (the **COMMA INPUT** panel shows `OP STEER:
STEERING`). Push the stalk away / cancel, or lose the link, and it
disengages. Uncheck **follow openpilot engage** to arm manually with
the ENGAGE button instead.

## Bench bring-up (do these in order; see plan §7)

- **M0 — link only, NO rack.** Run both. Confirm the panel shows
  `LINK: UP` and a steady `MSG/s` (~100). Hand-turn nothing; just prove
  the number flows. (openpilot can be faked with `FINGERPRINT=…`,
  `SKIP_FW_QUERY=1` if no car is connected.)
- **M1 — bench rack, sign check FIRST.** With the rack on a bench (no
  wheels loaded): get openpilot to command a small angle, engage, and
  **confirm the wheel turns the way openpilot intends.** If mirrored,
  restart with `--invert`. The angle-sign convention between openpilot
  and our code is **not yet verified** — this check is mandatory before
  trusting it.

## Hard rules

- **The comma panda must never transmit `0x488`.** This laptop is the
  sole transmitter of that id (Theory C, PROJECT_MEMORY.md §8). Two
  receivers on the bus is fine; two transmitters is the May-2026
  contention.
- **Bench/jacks only on this base.** `tesla_control.py` v4.3.3
  auto-disengages above ~1 mph and gates engage to Park — correct for
  bring-up, but it will drop openpilot the instant the car moves. Road
  use (M3+) requires building on the auto-disengage-removed base
  (v5.0.4, `claude/remove-eac-auto-disengage`).
