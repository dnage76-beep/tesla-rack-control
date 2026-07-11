# V6 — Forking openpilot to drive the rack through our own CAN code

How to use a modern openpilot's steering brain on the comma 3X while
**our** proven laptop code (`tesla_control.py` + SYS TEC) does the
actual `0x488` transmission, engaged by a pull of the cruise stalk.

Every claim here is cited to a file and line in a real tree. Two
trees were inspected on 2026-06-16:

- **tesla-unity** (the pre-AP fork) — `xnor-tech/openpilot @ tesla-unity`,
  `COMMA_VERSION` 0.9.6-Beta63. Paths below: `tu:<path>`.
- **modern openpilot** — `commaai/openpilot @ master`, commit
  `f3b1f97`, `COMMA_VERSION` **0.11.2** (not 0.10.x — that guess was
  stale); car ports now live in `opendbc/car/`. Paths: `op:<path>`.
- **our code** — this repo, `tesla_control.py` v4.3.3 and the v5 RC
  bridge on `dev/v5-rc`. Paths: `ours:<path>`.

Last updated: 2026-06-16.

---

## 1. The one fact that makes this whole idea work

openpilot's lateral controller outputs a **desired steering angle in
degrees**, in `carControl.actuators.steeringAngleDeg`, and the Tesla
port uses **angle control** (not torque):

- `op:opendbc/car/tesla/interface.py:24` — `ret.steerControlType = SteerControlType.angle`
- `op:selfdrive/controls/controlsd.py:137` — `actuators.steeringAngleDeg = float(lateral_output)`
- `op:opendbc/car/car.capnp` `struct Actuators` — `steeringAngleDeg @3 :Float32`

Our code's input is **the same quantity**: a target angle in degrees.

- `ours:tesla_control.py:517` — `ControlState.target_angle_deg`
- `ours:tesla_control.py:911` — `_apply_rate_limit()` turns it into the rate-limited command
- `ours:tesla_control.py` builds `0x488 DAS_steeringControl` at 50 Hz (PROJECT_MEMORY §4)

And the pre-AP fork builds the **identical wire format** we already send:

- `tu:selfdrive/car/tesla/teslacan.py:126` — `create_steering_control(angle, ...)` packs
  `DAS_steeringAngleRequest: -angle`, `DAS_steeringControlType: 1` (ANGLE) into `DAS_steeringControl` (= `0x488`)
- `tu:selfdrive/car/tesla/carcontroller.py:142` — reads `actuators.steeringAngleDeg`, applies
  `apply_std_steer_angle_limits`, then `create_steering_control(...)` at `:152`

**So openpilot's job ends exactly where our code's job begins: a
number of degrees.** We do not need openpilot's CAN/panda layer at
all if we can read that number off the device. We can (see §3).

This is the same seam the **v5 RC bridge** already plugged into:
`ours(dev/v5-rc):tesla_control_rc.py:348` `RcApp(base.App)` runs a
reader thread that calls `apply_rc_input()` (`:371`), which writes
`ctrl.target_angle_deg` (`:385`) and lets the existing worker
transmit. A "comma bridge" is the **same class with a different
reader**.

---

## 2. Reading the angle off the comma (verified, in-tree, ~no new infra)

openpilot ships a message bridge we can reuse as-is:

- `op:cereal/messaging/bridge.cc` — run `./cereal/messaging/bridge`
  on the comma with no args → it re-publishes all msgq services over
  ZMQ/TCP for a remote machine. (Documented in
  `op:tools/plotjuggler/README.md` and `op:tools/joystick/README.md`.)
- On the laptop: `export ZMQ=1`, then
  `sm = cereal.messaging.SubMaster(['carControl'], addr=<comma_ip>)`
  and read `sm['carControl'].actuators.steeringAngleDeg`
  (`op:cereal/messaging/__init__.py:150,153` — `SubMaster` takes `addr`).
- `carControl` is a real logged pub/sub service at 100 Hz
  (`op:cereal/services.py:46`). `tools/joystick/joystickd.py` is a
  working in-tree example of a standalone process reading/writing
  these same messages.

Transport is **TCP/ZMQ over the network** (Wi-Fi or USB-ethernet to
the 3X). There is **no USB cereal transport** in the tree — flagged.
A USB link would be an SSH/USB-ethernet tunnel layered under ZMQ.

So the "get the steering out of the comma" half is a **tiny
forwarder** (subscribe `carControl` → push `steeringAngleDeg` + an
engage flag to the laptop). Tens of lines, built on shipped infra.

---

## 3. Engagement on the cruise stalk (verified)

Pulling the stalk **toward you** is, on this car,
`STW_ACTN_RQ.SpdCtrlLvr_Stat == 2` ("RWD" / resume):

- `tu:selfdrive/car/tesla/values.py:225` — `VAL_ 69 SpdCtrlLvr_Stat … 2 "RWD" 1 "FWD" 0 "IDLE"`
  (CAN id 69 = `0x45`)
- `tu:values.py:205` — `resumeCruise` ← `SpdCtrlLvr_Stat [2]`; `cancel` ← `[1]` (push away)
- `tu:selfdrive/car/tesla/carstate.py:289` — `self.cruise_buttons = cp.vl["STW_ACTN_RQ"]["SpdCtrlLvr_Stat"]`

We already decode this message — it is the same `STW_ACTN_RQ` /
`0x45` stalk in our 18,414-frame capture (PROJECT_MEMORY §6,
`field_testing/captures/20260507_011220_shift_diagnostic/`).

**Important divergence:** the *pre-AP* fork engages off this stalk,
but the **modern** Tesla port (Model 3/Y) does **not** parse a cruise
stalk at all — it ties engagement to the car's own
`DI_state.DI_cruiseState` (`op:opendbc/car/tesla/carstate.py:71-88`;
`op:selfdrive/car/car_specific.py:43-46` → `pcmEnable`). Modern
Model 3/Y have no such stalk. So "engage on lever pull" is **native
to the pre-AP world, absent from the modern port.**

**Design decision that falls out of this:** let the **laptop own
engagement.** Our code already sees `0x45`; gate `ctrl.engaged` on
`SpdCtrlLvr_Stat == 2`, drop it on `== 1` (push-away) or brake. This
gives us a hard, local engage authority independent of whatever the
comma's brain thinks, and it's the behavior you asked for. It also
means the comma brain can run "always trying to steer" and the
laptop decides when that steering reaches the rack.

---

## 4. The honest catch: modern openpilot can't see this car

Everything above assumes openpilot is producing a sane
`steeringAngleDeg`. For that, openpilot must read **CarState**
(vEgo, steering angle) and reach an engaged/active state
(`op:selfdrive/controls/controlsd.py:99-112` — no `latActive` →
lateral output resets to zero; §6 of the research). And here is the
problem:

**The pre-AP car port exists ONLY in the 0.9.6 tesla-unity tree.**
Modern openpilot's Tesla port is Model 3/Y on the *party* CAN bus
with DBC `tesla_model3_party` — a different bus and different
messages than our pre-AP **chassis-bus** car (`0x370 EPAS_sysStatus`,
`DI_state`, `STW_ACTN_RQ`, `0x488` on DBC `tesla_can`). You cannot
configure the modern port for pre-AP; the pre-AP CAN definitions and
`CarState` are not in it. xnor themselves have **not** ported pre-AP
to the modern base — their pre-AP build is still the frozen 0.9.6
tesla-unity. That is the strongest evidence that the port is real
work, not a config flag.

What the "transmit with our code" idea **does** save: because the
laptop sends `0x488`, you do **not** have to port the pre-AP
**CarController / teslacan / panda TX-safety** to 0.11.2. That's
roughly half the port avoided. What it does **not** save: you still
need a pre-AP **CarState + fingerprint + engagement** on whatever
openpilot you run, so the brain can read speed/angle and reach
`active`.

---

## 5. Three coherent architectures (pick one)

| | A. Proper modern port | **B. Modern brain → our actuator (recommended)** | C. Old brain → our actuator |
|---|---|---|---|
| openpilot on comma | fork 0.11.2 + full pre-AP port incl. panda safety | fork 0.11.2 + pre-AP **CarState/fingerprint/engage** only | run existing tesla-unity 0.9.6 as-is |
| Who sends `0x488` | comma panda | **our laptop** (`tesla_control.py`) | our laptop |
| Comma on bus | TX+RX | RX only (no `0x488` from comma) | RX only |
| Uses our TX code | no | **yes** | yes |
| Engage on stalk pull | must add to modern port | **laptop owns it** (§3) | native + laptop can own it |
| New code | most (full port + safety) | bridge + CommaApp + pre-AP CarState port | **bridge + CommaApp only** |
| Brain quality | modern | **modern** | frozen 0.9.6 |
| Theory C risk | one node, fine | avoided (laptop sole TX) | avoided |

**Recommendation: build B, but stage it through C first.**

- C requires *almost no new code* — tesla-unity already produces
  `steeringAngleDeg` and already engages on the stalk. Standing up
  the forwarder + `CommaApp` against the 0.9.6 brain **proves the
  entire laptop-actuator path with zero porting.** Working system
  early.
- Then B becomes an *isolated upgrade*: swap the brain to forked
  0.11.2, doing only the pre-AP CarState/fingerprint/engagement port,
  with the bridge + laptop side already validated. The modern brain
  is the prize; this gets it without betting everything on the port
  up front.

This honors all three of your constraints — most-current openpilot
(B end state), reuse our transmit code (both), write as little as
possible (C first, then one contained port).

---

## 6. Code-reuse map (write as little as possible)

**Reused unchanged:**
- All of openpilot perception / planning / lateral control (the brain).
- `op:cereal/messaging/bridge` + `SubMaster` (the off-board link).
- `ours:tesla_control.py` worker, rate limiter (`:911`), `0x488` TX,
  `0x370` RX-timeout E-STOP (`:231` `RX_TIMEOUT_MS`), 360° clamp
  (`:228`), session logging, GUI.
- The v5 `RcApp` pattern as the literal template
  (`ours(dev/v5-rc):tesla_control_rc.py:348`).

**Lifted from tesla-unity (adapt, don't rewrite):**
- For B: `tu:selfdrive/car/tesla/carstate.py` pre-AP CarState (read
  `DI_state`, `0x370`, `STW_ACTN_RQ`), `values.py` `PREAP_MODELS`
  fingerprint + `CruiseButtons`, and the `tesla_can` DBC — adapted to
  the 0.11.2 `opendbc/car` interface.

**New code (small):**
1. `bridge/comma_steer_forward.py` (runs on comma): `SubMaster(['carControl'])`
   → emit `{angle_deg, op_active, ts}` to laptop. ~50 lines.
2. `ours:tesla_control_comma.py`: `CommaApp(base.App)` mirroring
   `RcApp` — reader thread for the bridged angle → `apply_comma_input()`
   writes `ctrl.target_angle_deg`; engage gated on the `0x45` stalk
   (§3); reuse the RC signal-loss/auto-disengage logic
   (`ours(dev/v5-rc):tesla_control_rc.py:534`). ~150–200 lines.

---

## 7. Staged milestones (each bench-testable before the next)

- **M0 — bridge proof, no rack.** Comma running *any* fingerprinted
  openpilot (even faked via `FINGERPRINT=`/`SKIP_FW_QUERY=1`,
  `op:opendbc/car/car_helpers.py:86`). Forwarder + a laptop stub that
  just prints the received angle. Gate: laptop prints openpilot's
  `steeringAngleDeg` at a steady rate over the link.
- **M1 — Architecture C end to end, bench rack.** tesla-unity brain →
  forwarder → `CommaApp` → existing worker → `0x488` to a bench rack
  (no wheels loaded). Engage by stalk pull. Gate: rack tracks
  openpilot's commanded angle; stalk push-away / brake disengages;
  `0x370` timeout still E-STOPs.
- **M2 — pre-AP CarState port onto 0.11.2 (the contained hard part).**
  Lift CarState/fingerprint/engagement; verify modern openpilot
  reaches `latActive` and emits real angles on this car's bus.
- **M3 — Architecture B end to end, bench then on-jacks**, then the
  v6 on-car test plan (T2–T4 in `docs/build/V6_OPENPILOT_PLAN.pdf`).

**Theory C rule still absolute:** the comma panda must never transmit
`0x488` — the laptop is the sole transmitter of that ID. Two
transmitters is the May-2026 contention (PROJECT_MEMORY §8). Two
*receivers* on the bus is fine.

---

## 8. Open risks / unknowns (flagged, not yet verified)

1. **Can openpilot reach `active` with the panda RX-only?** Engagement
   normally needs panda `controlsAllowed`
   (`op:selfdrive/selfdrived/selfdrived.py:473`). We must confirm a
   config (e.g. our own pre-AP panda safety that grants
   `controlsAllowed` on the stalk but sends nothing, or
   `JoystickDebugMode`/`SIMULATION` relaxations,
   `op:tools/joystick/README.md`) that lets the brain produce angles
   while never sending `0x488`. **This is the load-bearing unknown for B/C.**
2. **Latency.** Bridge over Wi-Fi adds a hop our v5 budget didn't
   have. `0x370` RX-timeout E-STOP (500 ms) bounds the danger, but a
   wired USB-ethernet link to the 3X is strongly preferred.
3. **Angle sign / units.** tesla-unity sends `-angle`
   (`tu:teslacan.py:128`); confirm our `target_angle_deg` sign
   convention matches openpilot's before the rack moves.
4. **Two devices on chassis bus.** Electrically fine (CAN is
   multi-drop); reconfirm only one sources `0x488`.

---

## 9. Sources

All paths above are file:line in the inspected trees. Trees:
- `commaai/openpilot @ master` (`f3b1f97`, v0.11.2) and `opendbc @ 0635488`
- `xnor-tech/openpilot @ tesla-unity` (v0.9.6-Beta63)
- this repo `tesla_control.py` v4.3.3; `dev/v5-rc:tesla_control_rc.py`
- PROJECT_MEMORY.md §4 (`0x488`/`0x370`), §6 (stalk/`0x45`), §8 (Theory C)
