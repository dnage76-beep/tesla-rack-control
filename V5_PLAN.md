# V5 Plan -- Full Vehicle Control

Implementation plan for v5: extend tesla_control.py from steering-only
into full RC control of throttle, brake (within limits), gear, and
steering on a 2013 Tesla Model S (pre-AP, post-May-31 build, RWD).

This is a planning document only. **No code changes yet.** Read this
end-to-end before any field work. Cross-reference
[PROJECT_MEMORY.md](PROJECT_MEMORY.md) for the canonical fact base.

Last updated: 2026-05-07.

---

## 1. The vehicle (verified)

| Fact | Value | Source |
|---|---|---|
| Year | 2013 | Derek's car |
| Model | **S** (not 3 -- Tesla didn't make Model 3 until 2017) | Derek's car |
| Build | post-May-31 | Project handoff doc |
| Drivetrain | **RWD only** -- single rear motor | [findmyelectric VIN decoder](https://www.findmyelectric.com/tesla-vin-decoder/); Tesla didn't introduce Model S AWD ("dual motor") until **October 2014** |
| Brake system | **Vacuum-assisted** (no iBooster) | [Tinkla Pedal Interceptor wiki](https://tinkla.us/index.php/Pedal_Interceptor): *"On preAP Tesla Model S, the braking system is vacuum based, like on regular ICE cars"* |
| Throttle architecture | Two redundant 0-5 V analog signals from pedal to Drive Unit | [comma pedal docs](https://github.com/commaai/openpilot/wiki/comma-pedal): *"two redundant 5V analog signals that must be captured and sent twice"* |
| Stability control | Standard ESP. **No firmware Dyno Mode in 2013.** That feature shipped 2019+. | Tesla service manual references |

**This means**:

- Throttle control is NOT achievable via CAN injection. The Drive Unit
  does not accept a "torque request" CAN message from a non-OEM source
  on this car. We must intercept the analog pedal signal.
- Brake control via software is **severely limited**. We can release
  brake (lift human's foot mechanically) but not apply brake unless we
  retrofit an iBooster (significant invasive work) or a separate
  electric brake actuator (complex). Phase 5 goal: scope-limit to
  controlled rolling, no full brake authority.
- Stability control on a single-axle dyno will fight us because front
  wheels (0 mph) won't match rear wheels (rolling). See Section 4.

---

## 2. Throttle: pedal interceptor architecture

There is no clean way to command throttle over CAN on a pre-AP Model
S. Every working solution in the Tinkla / openpilot ecosystem uses a
**hardware pedal interceptor**: a small board that physically sits
between the accelerator pedal and the Drive Unit, intercepting the
two redundant analog signals.

```
              [Accelerator pedal sensor (in-cabin)]
                          |
                (2x analog signals 0-5V)
                          |
                  ============== <-- Pedal Interceptor (NEW)
                  | Reads pedal |     Reads driver's foot input.
                  | Re-emits  →|     Either passes through OR
                  | new voltage|     emits a programmed voltage.
                  ==============     Emits "pedal position" on CAN.
                          |          Listens for "gas command" on CAN.
                (2x analog signals 0-5V)
                          |
              [Drive Unit (DU) accepts as if from real pedal]
```

### Three sourcing options

| Option | Cost | Effort | Notes |
|---|---|---|---|
| **Comma Pedal** | ~$800 | Low | Closed-form factor, well-documented, supported by openpilot mainline. BogGyver maintains a Tesla-specific firmware branch ([panda `tesla_pedal`](https://github.com/BogGyver/panda/tree/tesla_pedal)). |
| **Tinkla Pedal Interceptor** | unknown (no public price) | Low | Purpose-built for pre-AP Tesla. Sold via Tinkla shop. Ships ready to plug in. |
| **DIY (Arduino / STM32)** | ~$50 | High | Reference: [joeljacobs/Interceptor](https://github.com/joeljacobs/Interceptor), [jflorchi/micro_pedal](https://github.com/jflorchi/micro_pedal). Risk: 2 redundant analog channels with safety crosscheck logic; getting the DAC right matters. |

**My recommendation**: buy the Tinkla Pedal Interceptor if it's
available (purpose-built for our exact car) or the Comma Pedal
otherwise (well-trodden path). DIY is real engineering work and
delays Phase 5 by weeks. The pedal is a safety-critical component;
buy don't build unless you have the time.

### Wire-level facts (from comma pedal docs and openpilot wiki)

- Two 0-5 V analog signals from pedal sensor (redundant; one is
  ~half the voltage of the other for safety crosscheck)
- Interceptor uses a 12-bit DAC to write back analog output
- Interceptor speaks CAN to communicate with the host:
  - **Sends**: live pedal position (so openpilot knows what the
    human is doing)
  - **Receives**: gas command (0-100% requested throttle)
- Watchdog: if no CAN command received within ~100 ms, falls back
  to passing through the human pedal signal unchanged

---

## 3. Brake: what's actually achievable on 2013 Model S

Brake control on this car is hard. Three honest categories:

### 3a. What we CAN do (modest)

- **Regen-only deceleration via throttle = 0**: lifting the throttle
  command to 0 triggers regen braking. This is the "let off the gas"
  effect. Useful for gentle deceleration and matches how human
  drivers slow down most of the time.
- **Driver applies brake**: if a human is in the car, they can press
  the pedal. The pedal interceptor doesn't affect brakes directly.

### 3b. What we CANNOT do without hardware additions

- **Software-commanded service brake**: there is no CAN message on
  the chassis bus that commands the brake calipers to apply. The
  brake master cylinder is mechanically linked to the pedal via a
  vacuum booster.
- **Emergency brake intervention**: same reason. iBooster retrofit
  would solve this but is a significant project on its own.

### 3c. What we CAN do with hardware additions (out of scope for v5)

- **iBooster retrofit**: install the electronic brake booster from
  AP1+ Model S. The Tinkla wiki has documented this. Significant
  invasive work; new pedal mounting, new brake lines, programming.
- **Linear actuator on brake pedal**: a servo or linear actuator
  mechanically pushes the human-style brake pedal. Crude but
  functional. Not a serious engineering solution.
- **EPB (parking brake)**: the EPB module accepts an APPLY command
  via CAN. We already send `0x214 EPB_epasControl` keepalive; with
  different content we could request EPB engagement. **EPB is
  not a service brake** -- it's a parking brake that locks at
  standstill. Useful for "stop and hold" but not for stopping.

### Phase 5 brake plan

Accept the vacuum-brake limitation. Goal: control throttle for
controlled forward motion at low speed, accept regen for
deceleration, require a human in the seat for hard stops. The EPB
can be commanded to lock the car at standstill once the program
decides "we're done moving."

This is the realistic envelope. Anything more ambitious is a
hardware retrofit project beyond software.

---

## 4. Test stand / dyno: the real safety problem

Derek's note: *"Tesla does not like moving while on the stand."*
This is correct and important. The reason:

### Why a partial dyno breaks Tesla on this car

Stability control (ESP) and traction control (TC) on a 2013 Model S
read FOUR wheel speed sensors via the ABS module. They expect
all four to track each other. On a partial dyno (only some wheels
on rollers):

- Front wheels: 0 mph (held still on jacks or dyno frame)
- Rear wheels: 30 mph (spinning on rollers)
- ESP sees: car body not moving (yaw/lateral G sensors), rear
  wheels spinning fast, front wheels stationary -> **CONCLUSION:
  catastrophic slide event in progress**
- ESP intervenes: cuts torque, applies brakes individually, throws
  faults, may put car into reduced-power mode

This is not a Tesla quirk -- every modern stability-controlled car
does this. The fix in production is either:

- **4-wheel chassis dyno** (all 4 wheels on rollers, all spinning
  at the same speed) -- expensive, professional shops only
- **Tesla Dyno Mode** -- introduced 2019+, NOT in 2013 firmware
- **Wheel speed sensor spoofing** -- inject fake CAN signals to
  pretend front wheels are also moving. Risky, not well-documented
  on pre-AP

### Realistic Phase 5 test approach

| Test | How | Why |
|---|---|---|
| Pedal interceptor electrical bench-test | Bench, no car | Verify Arduino/comma pedal reads voltage and writes voltage correctly. Use a voltmeter and a function generator. |
| Pedal interceptor in-car static test | Wheels on jacks (off ground), brake pressed | Send 5% gas command, verify rear wheels start to turn (free-spinning). Confirm watchdog falls back to pass-through correctly. |
| Throttle response calibration | Same as above | Map gas command to motor torque output. Confirm 0% command = no torque. |
| **First propulsion test** | **Empty parking lot, real driving, 3-5 mph max** | The cleanest possible test. No dyno, no spoofing. Real ESP, real wheel speeds, real brakes (driver in seat). Issue gas commands, observe car move. |
| Steering + throttle integration | Same parking lot, low speed | Combine `0x488` steering with throttle command. Verify control loop. |
| Rest-and-roll primitive | Same parking lot | Shift to D, brief throttle, steer, brake (driver), shift to P. Validate the autopark-style maneuver. |

**Do not attempt to drive the car on a partial dyno.** The
stability control intervention will fight your throttle commands,
mask the real behavior, potentially throw codes that disable other
systems, and introduce unknown failure modes.

For tests that benefit from a stand (steering at large angles,
kinematics), keep wheels-off-the-ground on jacks. For propulsion
tests, go to a parking lot.

---

## 5. Phase 5 implementation plan

### Phase 5A: hardware sourcing and bench verification (week 1)

| Task | Owner | Deliverable |
|---|---|---|
| Choose pedal interceptor (Tinkla / Comma / DIY) | Derek | Decision documented in this file |
| Purchase / build | Derek + Jordan | Working interceptor on bench |
| Bench test: read pedal, write voltage, send/receive CAN | Charlie | Test log with screenshots of waveforms |
| Document CAN protocol used by chosen interceptor | Claude (after capture) | Update `docs/PROTOCOL.md` |

**Acceptance**: bench test shows voltage in -> CAN message out, CAN
message in -> voltage out, all within spec. No driving.

### Phase 5B: in-car installation, static verification (week 2)

| Task | Owner | Deliverable |
|---|---|---|
| Install interceptor in car | Jordan | Wired correctly, harness clean |
| Wheels on jacks, ignition on, brake pressed by driver | Charlie | Static test setup |
| Capture baseline: with interceptor in pass-through, drive cycle | Charlie | Session log |
| Send 5% gas command via tesla_control_v5.py | Derek | Rear wheels free-spin |
| Capture transitional: cancel gas, verify pass-through | Charlie | Session log |

**Acceptance**: software gas command makes rear wheels spin (off
ground), zero command stops, watchdog tested and works.

### Phase 5C: real-motion testing (week 3)

| Task | Owner | Deliverable |
|---|---|---|
| Empty parking lot identified | Derek | Location |
| Driver in seat (Jordan or Derek), foot ready over brake | Jordan | Safety driver |
| Charlie at laptop, sends 2% gas, observes | Charlie | Session log |
| Increase gas slowly to 5%, then 10% | Charlie | Logged transitions |
| Combine with steering: 30-degree turn while rolling | Charlie + Derek | Combined control session |

**Acceptance**: car rolls forward at 3-5 mph under software gas
control, steering tracks commanded angle, driver can intervene at
any time via the brake pedal.

### Phase 5D: integration into tesla_control.py (week 4)

Extend the existing program with:

- New "Throttle" panel in the GUI showing requested gas %, actual
  pedal voltage, watchdog status
- New CAN ID listening: pedal-position broadcast from interceptor
- New CAN ID transmitting: gas command at 50 Hz with sequence
  number and watchdog
- New auto-disengage: gas drops to 0 if any of the existing
  watchdogs fire
- New keybinding: W = gas up, S = gas down (matching openpilot's
  joystick mode convention)
- Save-test integration: throttle commands + actual pedal logged
  to the existing CSV format

### Phase 5E: rest-and-roll primitive (week 5)

Implement the autopark-style scripted maneuver:

```
1. Verify in P, brake pressed, EAC ACTIVE
2. Operator confirms "execute"
3. Software:
   a. Shift to D via 0x6D burst
   b. Verify gear changed via 0x118
   c. Apply 3% gas via interceptor
   d. Wait 0.3 s (creep)
   e. Command 15-degree steering via 0x488
   f. Wait 0.5 s
   g. Command 0% gas
   h. Wait 0.5 s for regen + driver brake
   i. Verify near-zero speed via 0x118 DI_vehicleSpeed
   j. Shift to P via 0x6D burst
   k. Verify gear back to P
4. Display "manuever complete"
```

**Acceptance**: scripted maneuver moves the car ~1 ft from a stop,
returns to stop with brake applied, no E-STOPs, full session
captured.

---

## 6. Safety: what gets added in v5

Existing v4.2 safety architecture (PROJECT_MEMORY.md Section 11)
extends with these new layers:

### Throttle-specific watchdogs

- **Hard cap at 10% gas**: never command more than 10% throttle
  during Phase 5. Plenty for parking-lot creep; safe ceiling.
- **Pedal-position vs gas-command divergence trip**: if the
  interceptor reports pedal voltage that doesn't match what we
  commanded (within tolerance), assume hardware failure. E-STOP.
- **Driver override**: if the human's pedal voltage > our gas
  command, the human wins (interceptor passes through). Standard
  comma pedal behavior.
- **Watchdog**: gas command must be re-sent at least every 100 ms
  or the interceptor falls back to pass-through (zero gas
  effectively, since human's foot is presumably off the pedal).
- **Estimated speed cap**: if `DI_vehicleSpeed > 8 mph` while
  software is commanding gas, automatic E-STOP (we should never
  exceed 5 mph in tests; 8 is a hard ceiling).

### Brake-specific (the hard category)

- **Driver in seat is mandatory**: software cannot apply brakes.
  The only authoritative brake source is the human's foot.
  Procedure: driver's foot stays hovering over the brake pedal at
  all times during throttle tests.
- **EPB latch on stop**: when commanded sequence ends, software
  fires `0x214 EPB_epasControl` with apply-request to lock the
  parking brake. Belt-and-suspenders against accidental rolling.

### Test stand specific

- **No driving on the stand**: Phase 5C explicitly forbids
  parking-lot-style throttle tests on a partial dyno. If a
  4-wheel dyno becomes available later, revisit.
- **Wheels-on-jacks throttle test**: only with rear wheels FREE
  (no rollers, no chocks blocking spin). Verify by hand spin
  before ignition on.

---

## 7. Open questions for Derek before Phase 5A starts

1. **Pedal interceptor sourcing**: comma vs Tinkla vs DIY? Budget
   and timeline preference?
2. **Brake retrofit appetite**: do we want to invest in iBooster
   for full brake authority later (Phase 6+), or accept rolling-
   only RC as the v5 endpoint?
3. **Test parking lot location**: where does the in-motion
   testing happen? Charlie + driver availability?
4. **Phase 0 still open**: gear shift in-car validation needs
   Charlie to retest. Do we wait for that result before moving on
   to v5, or run them in parallel?

---

## 8. What this branch will NOT contain

To be explicit about scope:

- **No new code in this branch yet.** Planning docs only.
- **No simulated throttle / brake control without hardware.** We
  don't fake having a pedal interceptor; v5 starts after the
  hardware is sourced and bench-verified.
- **No driving on a partial dyno.** Section 4 explicitly forbids it.
- **No iBooster retrofit work.** Out of scope for v5; potential
  v6 topic.
- **No openpilot integration.** Still v6+ per ROADMAP.md.

---

## 9. Sources

- [Tinkla wiki](https://tinkla.us/index.php/Welcome_to_Tinkla!) -- pre-AP retrofit ecosystem
- [Tinkla Pedal Interceptor article](https://tinkla.us/index.php/Pedal_Interceptor) -- vacuum brake confirmation
- [comma pedal documentation](https://github.com/commaai/openpilot/wiki/comma-pedal) -- pedal interceptor architecture
- [BogGyver/panda tesla_pedal branch](https://github.com/BogGyver/panda/tree/tesla_pedal) -- Tesla-specific pedal firmware
- [joeljacobs/Interceptor](https://github.com/joeljacobs/Interceptor) -- early DIY pedal source
- [jflorchi/micro_pedal](https://github.com/jflorchi/micro_pedal) -- modern STM32 DIY pedal
- [findmyelectric VIN decoder](https://www.findmyelectric.com/tesla-vin-decoder/) -- 2013 Model S RWD-only verification
- [Tesla Model S Service Manual](https://service.tesla.com/docs/ModelS/) -- ABS, stability control, wheel speed sensors
- Project-internal: PROJECT_MEMORY.md, ROADMAP.md, all session logs
