# ROADMAP.md

The plan from where we are (v4.2 dev) to where we want to go
(full RC car → openpilot integration). Read
[PROJECT_MEMORY.md](PROJECT_MEMORY.md) first; that's the
"what's true" reference. This document is "what's next."

Last updated: 2026-05-07.

---

## North Star

A 2013 Tesla Model S that:

1. Can be steered, accelerated, braked, and shifted from a Spektrum
   DX8 transmitter via an Arduino bridge (RC car phase)
2. Can be driven by openpilot using the same control surfaces
   (autonomy phase)

The destination has three control axes (steering, longitudinal,
gear) and one input source (DX8 → Arduino → CAN). openpilot is
swappable for the DX8 once the control surfaces are stable.

---

## Where we are right now

**Steering, on jacks**: works reliably. Production-ready in
`tesla_control.py` v4.2.0-dev. Multiple sessions confirm it.

**Steering, in-motion**: never tested but expected to work
(real ESP unlocks at-speed envelope honestly).

**Standstill ground steering**: blocked by physics + speed gate.
See PROJECT_MEMORY.md Section 10 for analysis.

**Gear shift command**: code is bench-correct as of `eae24c4`
(byte 0 / byte 1 fix landed). Not yet field-validated.

**Throttle, brake**: zero progress. Not started.

**Spektrum DX8 integration**: zero progress. Not started.

**openpilot integration**: out of scope for v4.x.

---

## Phased plan

### Phase 0: close the loop on what's already in flight (~this week)

Single objective: get gear shift working in-car, then call v4.2
done. Everything in v4.2 is then production for "steering on jacks
+ gear shift + brake/gear/speed read."

| Task | Status | Owner |
|---|---|---|
| Field-test gear shift fix `eae24c4` | not done | Charlie |
| If shift fails: capture more `0x6D` frames during attempted shift, diff against real stalk capture | conditional | Charlie + Claude |
| If shift wins arbitration but SCCM still ignores: try longer burst (20-40 frames) or higher burst rate | conditional | Claude code change |
| Tag `v4.2.0` and merge `dev/v4.2-prnd` to `main` | gated on shift working | Derek |

**Phase 0 acceptance**: clicking N/D/R in the GUI causes the Gear
cell to update within 300 ms.

### Phase 1: in-motion steering test (~next week)

Single objective: prove the steering control loop works while the
car is actually rolling at 3-5 mph, with real ESP doing its job.

This is the cleanest validation of the core loop because it
removes every spoofing-related question. The real ESP reports
real speed. The rack opens its at-speed envelope honestly. The
EPAS has full authority. We just send `0x488` like we already do.

| Task | Owner |
|---|---|
| Find a safe parking lot for low-speed testing | Derek + Jordan |
| Pre-flight checklist: steering wheel free hands, jack down, all guards in place | Charlie |
| Driver in seat (pedal control), Charlie/Derek with laptop | Charlie / Derek |
| Test sequence: roll at 3 mph, command 5° → 10° → 20° → 30° → recenter | Driver |
| Capture session log + CSV; SAVE TEST | Derek |

**Phase 1 acceptance**: rack tracks commanded angles within 2°
divergence at 3-5 mph, no E-STOPs, no EAC flicker, full session
saved to repo.

This is the milestone that turns the project from "interesting bench
demo" to "real RC steering." It's also the single most informative
test we can run without new hardware.

### Phase 2: throttle and brake reverse engineering (~weeks 2-4)

Single objective: identify and command the CAN messages for go-
pedal and brake-pedal on this specific 2013 Model S.

This is the hard one. Throttle and brake are typically harder to
reverse-engineer than steering because the production cars don't
have an external "torque request" interface the way they have
`0x488` for steering.

| Sub-task | Approach |
|---|---|
| Identify which message contains driver pedal request | Sniff during pedal press; diff vs idle |
| Identify which message contains regen / torque request | Same sniff approach |
| Determine if pedal request is read-only or writable | Send synthesized version, see if car responds |
| If writable: define safe command envelope, watchdogs, timeout behavior | Dedicated design doc |
| If not writable: investigate brake-pump / regen approaches BogGyver / Tinkla used | Literature review |

**Phase 2 acceptance**: laptop can command 0-10% throttle and
0-30% brake from a stationary rolled position, with auto-disengage
on any anomaly. This is the most dangerous phase; do not rush it.

**Risk note**: pre-AP Model S has vacuum-based braking (per
Tinkla wiki). Unlike AP cars with iBooster, full software brake
control may not be possible without hardware additions.

### Phase 3: shift integration via existing v4.2 + new states (~week 4)

Single objective: combine steering + gear control such that the
laptop can hold the car in P, command a shift to D, command a
small forward roll, command a steering angle, return to P. This
is the primitive for rest-and-roll RC.

Most of this is already in v4.2 (gear shift code is in place;
steering is working). Phase 3 is integration testing, not new code.

| Task |
|---|
| Document the rest-and-roll primitive sequence in `docs/REST_AND_ROLL.md` |
| Implement a "scripted maneuver" mode in `tesla_control.py` (shift to D → throttle 5% for 0.5s → steer 10° → throttle 0% → brake 20% → shift to P) |
| Test the scripted maneuver on jacks (no actual movement) to validate the timing and sequencing |
| Test on the ground in a parking lot |

**Phase 3 acceptance**: scripted maneuver completes from stop,
moves the car ~1 ft, returns to stop with brake applied.

### Phase 4: Spektrum DX8 + Arduino bridge (~week 5-6)

Single objective: replace the laptop GUI with a DX8 transmitter as
the primary control interface.

| Sub-task | Approach |
|---|---|
| Pick the Spektrum receiver (probably a satellite Rx with the SRXL2 or DSMX serial output) | Hardware sourcing |
| Wire the Spektrum Rx to an Arduino Nano | Standard SBUS-on-UART pattern |
| Arduino reads channel data, formats CAN frames, writes to a small CAN module (MCP2515) | Reference: Arduino_SBUS, mcp_can libraries |
| Arduino plugs into the chassis CAN bus at the X437/TDC tap (parallel with SYS TEC for now) | Use the same harness Jordan built |
| Add a "DX8 mode" to `tesla_control.py` that disables our `0x488` TX and lets the Arduino take over | One software flag |
| Document the channel mapping (left stick X = steering, right stick Y = throttle, switch = gear, etc.) | New doc |

**Phase 4 acceptance**: DX8 transmitter steers, accelerates, brakes,
shifts the car. Laptop is optional for the run (can still log).

### Phase 5: openpilot integration (long-term, no concrete date)

Out of scope for v4.x. The principle: once steering + throttle +
brake + shift are all CAN-commandable, openpilot's `controlsd` can
emit those commands instead of the DX8. This requires:

- A car port in openpilot for our patched 2013 Model S (the
  BogGyver fork is the closest precedent)
- Camera, IMU, and GPS hardware (we'd want a comma 3X for this,
  contradicting the "no comma" v4 design — but Phase 5 needs it)
- A new safety model in panda firmware to gate the commands openpilot
  emits

This is genuinely the BogGyver/Tinkla problem, which already has a
working starting point. Phase 5 may end up being "fork BogGyver
and integrate our improvements" rather than "build from scratch."

---

## Decision points along the way

**After Phase 1**: do we accept that ground-loaded standstill
steering is not in scope? If yes, skip ahead to phases 2 and 3 for
the rest-and-roll approach. If no, allocate time for either
hardware MITM (Path B) or rack firmware patch reverse engineering
(Path C). I recommend the former.

**After Phase 2**: is throttle/brake control feasible on this
specific 2013 Model S? If pre-AP's vacuum brake system is too
limiting, the project pivots: rolling-only RC (no full brake
control), or hardware additions (electric brake assist retrofit).

**After Phase 4**: is openpilot integration a goal worth pursuing,
or has the project achieved enough as-is? The DX8 RC car is itself
a complete deliverable.

---

## Risks to watch

1. **The 2013 rack's stall torque is genuinely insufficient.** Even
   with the speed gate removed, the hardware may not turn ground-
   loaded wheels. Empirical only. Mitigation: rest-and-roll.
2. **Vacuum brake system on pre-AP** prevents full brake authority.
   Mitigation: scope-limit Phase 2, accept rolling-only RC.
3. **Reverse engineering throttle takes longer than expected.**
   Drive inverter messages are typically more validated than EPAS.
   Mitigation: budget 2-3 weeks for Phase 2, not 1.
4. **Real stalk wins arbitration on `0x6D`** even with our fixed
   bytes. Mitigation: longer burst, faster burst, or physical
   stalk disconnect for testing.
5. **Repeated rack reflashing risk.** Each flash has a small
   chance of bricking the rack. Don't reflash unless we have a
   strong reason and a tested rollback. The current patch works;
   leave it alone unless we move to Path C.

---

## What NOT to do (from prior anti-patterns)

See PROJECT_MEMORY.md Section 15. Don't:

- Toggle 30 MPH MODE on a live in-car bus
- Run with the comma 3X on chassis CAN
- Trust the DBC blindly for CRC-protected commands
- Patch firmware without backup + test rollback path
- Skip the session-log save after a meaningful field test

---

## Cadence

- **Daily**: Charlie or Derek field-tests the latest dev branch,
  saves the session via SAVE TEST, pushes the log
- **Weekly**: Claude reviews logs, cuts a v4.x.y release if
  warranted, updates PROJECT_MEMORY.md with new facts
- **Per-phase**: written acceptance criteria checked off, ROADMAP.md
  updated with status

---

## Acceptance for "v4.2 done"

- [ ] Gear shift works in-car (Phase 0)
- [ ] In-motion steering verified at 3-5 mph (Phase 1)
- [ ] All session logs from those tests saved to GitHub
- [ ] CHANGELOG.md updated, `__version__` bumped to "4.2.0"
- [ ] dev/v4.2-prnd merged to main
- [ ] release/v4.2 branch created at the merge point
- [ ] v4.2.0 git tag created
- [ ] PROJECT_MEMORY.md updated with verified Phase 0/1 results
