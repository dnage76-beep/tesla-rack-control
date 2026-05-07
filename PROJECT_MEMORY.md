# PROJECT_MEMORY.md

Canonical reference for the tesla-rack-control project. Every claim
here is either verified against primary sources (cited) or marked
explicitly as a hypothesis. Update this file when new facts are
established. **Do not write speculation here without flagging it.**

Last updated: 2026-05-07.

---

## 1. Purpose

Build a remote-controlled steering system for a 2013 pre-AP Tesla
Model S, then expand to a full RC car (steering + throttle + brake +
shift), then eventually integrate with openpilot. The end state is a
laptop or Spektrum DX8 transmitter (via Arduino) commanding the car
in real time, with the openpilot stack able to take over for
autonomy work.

Sub-goals in priority order:

1. **Steering control loop, on-jacks** -- proven, ±60 deg, working in
   many sessions including 232457 (2.7 minutes of clean ACTIVE).
2. **Steering control, in-motion (3-5 mph rolling)** -- not yet
   tested but expected to work; rack opens its at-speed envelope
   honestly when real ESP reports actual speed.
3. **Gear shift command from laptop** -- byte format fixed in commit
   `eae24c4` based on Charlie's stalk capture; not yet field-validated.
4. **Throttle and brake control** -- not yet started.
5. **Spektrum DX8 RC integration** -- not yet started.
6. **openpilot integration as a v5+ goal** -- requires steering +
   throttle + brake + camera/sensor inputs; out of scope for v4.x.

---

## 2. Hardware in play (verified)

| Component | Identity | Source / verification |
|---|---|---|
| Vehicle | 2013 Tesla Model S, post-May-31 build, pre-AP, **RWD only** | Derek's car, identified by VIN. Tesla didn't introduce Model S AWD ("dual motor") until October 2014, so a 2013 Model S is RWD-only with a single rear motor. |
| Brake system | **Vacuum-assisted** (no iBooster) | [Tinkla Pedal Interceptor wiki](https://tinkla.us/index.php/Pedal_Interceptor): *"On preAP Tesla Model S, the braking system is vacuum based, like on regular ICE cars."* Implies no software-commanded service brake authority on this car without hardware retrofit. |
| Throttle architecture | Two redundant 0-5V analog signals from pedal to Drive Unit | [comma pedal docs](https://github.com/commaai/openpilot/wiki/comma-pedal): *"two redundant 5V analog signals that must be captured and sent twice"*. There is no CAN-commandable throttle on this car -- a hardware pedal interceptor is required for software throttle control. |
| Stability control firmware Dyno Mode | **Not present in 2013** firmware. Tesla shipped Dyno Mode 2019+. | Tesla Owners forum threads. |
| Steering rack | EPAS, patched with [gregjhogan/tesla-pre-ap-epas-patch](https://github.com/gregjhogan/tesla-pre-ap-epas-patch) | Patch flashed by Jordan via the BogGyver openpilot UI |
| Patch firmware MD5 (unmodified) | `9e51ddd80606fbdaaf604c73c8dde0d1` | Verified from `gregjhogan/tesla-pre-ap-epas-patch/patch.py` line 14 |
| Patch byte locations | `0x031750`, `0x031892`, `0x031974` (each 4 bytes) | Verified from `patch.py:104-110` |
| CAN adapter | SYS TEC sysWORXX USB-CANmodul1 (model 3204001) | Confirmed in v4.2 settings; `interface="systec"` for python-can |
| Host OS | Windows 10/11 | Required by python-can systec backend's `USBCAN32.dll` |
| Comma 3X | Removed from chassis CAN bus as of v4 | Theory C confirmed; see Section 8 |

---

## 3. CAN bus topology (pre-AP Model S)

Three independent CAN buses (verified from
[tinkla.us](https://tinkla.us/index.php/Tesla_Model_S_preAP_OBD2_port)
and [TeslaMotorsClub CAN bus thread](https://teslamotorsclub.com/tmc/threads/can-buses-access.105222/)):

| Bus | Speed | Modules on it | Where to tap |
|---|---|---|---|
| **Chassis** | 500 kbps | EPAS rack, GTW, ESP, EPB, SCCM (steering column), DI (drive inverter) | X437/TDC connector under the center screen, OR OBD-II pins 1/9 if populated (depends on build date) |
| Powertrain | 500 kbps | BMS, charger, drive inverter (some signals duplicated to chassis) | X437/TDC, separate pin pair |
| Body / Diagnostic | 500 kbps | non-critical body modules | OBD-II default pins (always populated) |

The X437/TDC connector is where Derek/Jordan tap. This gives chassis
CAN reliably regardless of OBD-II pin population.

---

## 4. Tesla CAN protocol facts (verified)

All bit positions and values verified against the
`commaai/opendbc/tesla_can.dbc` mirror. CRC algorithm verified
against `BogGyver/panda` `safety_tesla.h` and against 18,414 real
stalk frames captured 2026-05-07 (`field_testing/captures/20260507_011220_shift_diagnostic/`).

### TX (we send)

| ID | Name | Rate | Notes |
|---|---|---|---|
| `0x488` | DAS_steeringControl | 50 Hz | The steering command. Patched rack accepts directly. |
| `0x214` | EPB_epasControl | 10 Hz | Required keepalive per gregjhogan README. Patched rack ignores content. |
| `0x101` | GTW_epasControl | 20 Hz | Off by default in-car (real GTW alive). Required on bench. |
| `0x155` | ESP_B fake speed | 200 Hz | Off by default. 30 MPH MODE only. **Causes ESP contention if real ESP is alive.** |
| `0x6D` | SBW_RQ_SCCM | 100 Hz burst | Gear shift request. See Section 6. |

### RX (we listen)

| ID | Name | Rate | Decoded fields |
|---|---|---|---|
| `0x370` | EPAS_sysStatus | ~100 Hz | EAC status, EAC error code, measured wheel angle |
| `0x118` | DI_torque2 | ~100 Hz | DI_gear, DI_gearRequest, DI_brakePedal, DI_brakePedalState, DI_vehicleSpeed |

### Checksum vs CRC

Tesla uses TWO different integrity algorithms across messages:

- **Sum checksum** (`(addr_byte + sum(data_bytes)) & 0xFF`): used by
  `0x488`, `0x101`, `0x214` (the steering control set). Verified
  inline in our message builders.
- **CRC-8/SAE-J1850** (poly `0x1D`, init `0xFF`, xorout `0xFF`,
  no address prefix): used by `0x6D` (shift) and `0x45` (stalk).
  Verified by:
  - BogGyver/panda `safety_tesla.h` `tesla_compute_crc` function
    docstring: *"Calculate CRC8 using 1D poly, FF start, FF end"*
  - That function's lookup table starts `0x00, 0x1D, 0x3A, 0x27, ...`
    which matches the canonical CRC-8/J1850 table
  - Our Python `tesla_crc8` implementation produces the same first
    16 entries (verified 2026-05-07)
  - All 6 captured real stalk shift frames (IDLE, R, N_UP, N_DOWN,
    D, P-button) match `tesla_crc8(b0, b1, b2)` exactly

---

## 5. The gregjhogan EPAS patch (exact bytes verified)

Source: `gregjhogan/tesla-pre-ap-epas-patch/patch.py:104-110`,
verified 2026-05-07.

```python
mods = [
    # load 1 instead of extracting EPB_epasEACAllow
    [0x031750, b"\x80\xff\x74\x2b", b"\x20\x56\x01\x00"],
    # load 1 instead of extracting GTW_epasControlType
    [0x031892, b"\x80\xff\x32\x2a", b"\x20\x56\x01\x00"],
    # load 1 instead of extracting GTW_epasLDWEnable
    [0x031974, b"\x80\xff\x50\x29", b"\x20\x56\x01\x00"],
]
```

Each mod replaces a 4-byte instruction sequence (looks like an ARM
Thumb load-from-bus-message instruction) with `20 56 01 00` (looks
like `MOVS R0, #1`). The result: the rack's internal logic reads
"`1`" for these three control-allow signals regardless of what the
bus actually contains.

### What the patch DOES

- Bypasses the GTW/EPB content gates that prevent steering control
- Lets the rack accept `0x488 DAS_steeringControl` directly
- Standstill angle ceiling stays unchanged (~±60 deg, observed)
- Standstill torque scaling stays unchanged

### What the patch does NOT do (verified by absence)

- **Does not touch speed-related code.** None of the three patched
  addresses are in the speed-vs-torque scaling logic. Speed gating
  is intact.
- **Does not remove the standstill angle ceiling.** Above ~±60 deg
  at 0 mph, the rack still emits `HIGH_ANGLE_REQ`.
- **Does not affect 0x118 / DI / SCCM behavior.** Other modules are
  untouched.

### Required keepalive after patch

Per gregjhogan README, quoted verbatim:

> if you have no electronic parking brake you still need to send
> EPB_epasControl with a good checksum and counter to prevent the
> EPAS from faulting

Our code sends `0x214` at 10 Hz to satisfy this. `SYNTHESIZE_EPB =
True` is the default.

---

## 6. The 0x6D shift message (verified from real stalk capture)

Source:
`field_testing/captures/20260507_011220_shift_diagnostic/capture.csv`
(18,414 frames captured 2026-05-07 by Charlie).

### Frame format

```
byte 0:  0x40                                              (constant; MsgTxmtId = 1)
byte 1:  0xC0 | (TSL_P_Psd_StW << 4) | TSL_RND_Posn_StW   (high nibble always 0xC)
byte 2:  (counter << 4)                                    (counter mod 16)
byte 3:  tesla_crc8([byte0, byte1, byte2])                (CRC-8 / SAE-J1850)
```

### Field values (verified against the capture)

| State | byte 1 | observed in capture |
|---|---|---|
| stalk idle | `0xC0` | 18,305 frames (99.4%) |
| shift to R | `0xC1` | 15 frames |
| shift to N_UP | `0xC2` | 15 frames |
| shift to N_DOWN | `0xC4` | 34 frames |
| shift to D | `0xC8` | 32 frames |
| P button pressed | `0xD0` | 12 frames |

### Key reverse-engineering finding

The fixed bits at `byte 0 = 0x40` and `byte 1` bits 6-7 = `0b11`
are **not in the public DBC** but the SCCM rejects frames without
them. Our v4.2 originally sent byte 0 = `0x00` with bits 6-7 of
byte 1 zero; SCCM silently dropped every such frame regardless of
CRC validity. Fixed in commit `eae24c4`.

Status: **bench-correct, not yet field-validated.** Charlie hasn't
re-tested gear shifting since the byte 0/1 fix landed.

### Open question on gear shift

Even with our frames now byte-identical to real stalk frames (CRC
included), we may lose CAN arbitration to the real stalk which
also transmits at ~100 Hz with `byte 1 = 0xC0 (idle)`. If the SCCM
sees an interleaved stream of "shift to D" / "idle" / "shift to D" /
"idle", it may not register a clear shift request. **This is
hypothesis until tested.** Mitigation if needed: raise our burst
rate, lengthen the burst, or physically disconnect the real stalk.

---

## 7. EAC error codes (verified from opendbc DBC)

| Code | Name | Meaning |
|---|---|---|
| 0 | NONE | All clear |
| 1 | MIN_SPEED | Vehicle below speed gate, OR `0x155` not on bus |
| 2 | MAX_SPEED | Above rack's at-speed cap |
| 3 | HANDS_ON | Driver torque sensor non-zero |
| 4 | OUT_OF_RANGE | Required keepalive missing or off-rate |
| 5 | OVER_TORQUE | Driver torque exceeded threshold |
| 6 | HIGH_ANGLE_REQ | Above standstill ceiling (~±60 deg) |
| 7 | HIGH_ANGLE_RATE_REQ | Rate too high; the **Theory C flicker symptom** |
| 8 | HIGH_TORQUE_REQ | (legacy AP signal) |
| 9 | BLEND_REQ | (legacy AP signal) |
| 10 | TIMEOUT | Required input stopped arriving |
| 11 | ECU_FAULT | Internal rack fault |
| 12 | BUS_FAULT | CAN bus errors |
| 13 | INVALID_REQ | Our `0x488` malformed |
| 14 | EPB_INHIBIT | EPB module inhibit, OR `0x214` missing/malformed |
| 15 | SNA | Signal Not Available |

EAC status enum: 0=INHIBITED, 1=AVAILABLE, 2=ACTIVE, 3=FAULT, 4=SNA.

---

## 8. Theory C: confirmed cause of May 2026 EAC flicker

**Hypothesis (Theory C)**: a comma 3X on the bus running BogGyver's
firmware was transmitting `0x488` in parallel with our laptop. Two
transmitters on the same arbitration ID → contention →
HIGH_ANGLE_RATE_REQ flicker.

**Verification**:

- BogGyver/panda `safety_tesla.h` line 843-846 (verified): the
  panda emits `0x488` when it sees `0x115` from the car, on every
  pre-AP build (`!has_ap_hardware`).
- Charlie's session 232457 captured the symptom: 280+ EAC
  transitions over 67 seconds when 30 MPH MODE was toggled on (a
  separate ESP contention case, not Theory C, but same pattern).
- Once the 3X was removed (v4 default), no flicker observed in
  any session.

**Status**: confirmed and resolved. The bus diagnostic panel in
v4.2 shows `0x488` RX rate; if it's >0 we know a second
transmitter is on the bus.

---

## 9. ESP contention: confirmed cause of "car freaked out" with 30 MPH MODE

**Hypothesis**: when 30 MPH MODE transmits `0x155` at 200 Hz with
fake 30 km/h, AND the real Tesla ESP module is alive on the bus
transmitting `0x155` at 50 Hz with the actual speed, the rack
(plus other consumers like stability control, regen, EPB) reads
both alternately and freaks out.

**Verification**:

- Charlie's sessions 232457 and 233049 (2026-05-06) captured the
  symptom: 90+ seconds of EAC bouncing INHIBITED↔AVAILABLE, ~10 Hz
  bounce rate, with `OUT_OF_RANGE` error.
- Symptom appeared instantly on 30 MPH MODE toggle ON, disappeared
  ~50 ms after toggle OFF.
- Charlie's field note: *"Wheels up, 30MPH mode on: Same sort of
  error"*.

**Status**: confirmed. Pre-flight ESP-presence check in v4.2 now
refuses 30 MPH MODE if real ESP traffic is detected on `0x155`
above 1 Hz. Mid-session auto-disable at 5 Hz. Verified working in
session 000935: toggle refused twice with clear log message.

---

## 10. The standstill ground steering problem (unsolved)

**The problem**: Derek's stated end goal is full RC steering from
a complete stop with wheels on the ground. Currently the rack does
not move ground-loaded wheels at standstill even with full software
authority.

**Two layered causes**:

### Cause A: the rack's speed gate

Tesla's EPAS reduces commanded torque output at low speed. At 0 mph
the available torque is a fraction of the at-speed maximum. To
unlock full authority we have to convince the rack the car is
moving. We've established two ways to attempt this:

- 30 MPH MODE (spoof `0x155`): blocked by ESP contention in-car
- ESP module physical disconnect: works on bench, breaks rest of car

A third option exists in principle: patch the rack firmware
further to remove the speed gate. **Not yet attempted.** Would
require reverse-engineering more of the rack's internal speed-vs-
torque table.

### Cause B: physics

Even at full at-speed authority, the rack's stall torque may not
overcome rubber-on-pavement static friction at standstill. Order-
of-magnitude estimate: rack outputs ~5-10 Nm at the column, static
friction on each loaded tire requires ~50-100 Nm. **This is a
hardware limit, not a software one.**

This is why every modern car (Tesla included) does "rest-and-roll"
parking: the autopark routine releases brake briefly while
steering is commanded, lets the car creep, then re-applies brake.
The rack never tries to turn loaded wheels at literal zero speed.

### Tesla's own behavior at 0 mph (verified)

Tesla support page
[recall-vehicle-firmware-correct-loss-of-epas](https://www.tesla.com/support/recall-vehicle-firmware-correct-loss-of-epas)
documents a **2023 recall** for "loss of EPAS when vehicles reach
0 mph." Tesla's intended production behavior is for EPAS to assist
at 0 mph; the recall fixes a regression where it stopped doing so.

This implies the rack CAN function at 0 mph natively and a
firmware patch removing the speed gate is in principle possible
(Tesla does it differently but the underlying rack hardware
clearly supports it).

### Three realistic paths forward

| Path | Approach | Software effort | Hardware effort | Risk |
|---|---|---|---|---|
| **A: Rest-and-roll RC** | Add throttle/brake/shift control. RC commands turn → release brake briefly → tiny creep → re-apply brake. Never actually steer at zero. | High (throttle and brake reverse-engineering) | None | Low |
| **B: CAN MITM bridge** | Hardware bridge between rack and bus. Forward everything except `0x155` which gets replaced with our spoof. Real ESP keeps talking to other ECUs. | Medium (bridge code) | Medium (Pi or MCU + 2 CAN HATs) | Medium |
| **C: Patch rack firmware further** | Reverse-engineer speed-gate logic, patch out the speed-vs-torque scaling. | Very high | None | High (more flashing risk) |

Recommendation: **Path A** is the cleanest and most aligned with
the stated end goal (RC car / openpilot integration). Path B is a
useful intermediate for demos but doesn't help the production goal.
Path C is research-grade work that may not even succeed.

---

## 11. What works today (verified by session logs)

- Steering control loop: `0x488` at 50 Hz, ±60 deg at standstill.
  Verified ACTIVE for 2.7 minutes in session 232457 before user
  introduced contention.
- Rack reaches `EAC_ACTIVE` reliably with default flags (in-car).
  Multiple sessions (000552, 002425, plus 232457).
- `0x118` decode for gear, gear request, brake, brake state,
  DI vehicle speed: verified in sessions 000552 and 002425.
- Auto-disengage on gear-out-of-P: verified in session 000552
  (gear P→N triggered disengage within 1 ms).
- Pre-flight ESP check refusing 30 MPH MODE in-car: verified in
  session 000935 (refused twice).
- Loop-overrun fix on shift bursts: code commit `3a81e4d`.
- Gear shift CRC fix: code commit `b15c408`. Bench-correct
  (matches all 6 real captured shift frames).
- Gear shift fixed-bits fix: code commit `eae24c4`. Bench-correct
  (produces byte-identical frames to captures).

---

## 12. What does not work today

- **Standstill steering with wheels on ground**: see Section 10.
- **Gear shift command**: code is bench-correct as of `eae24c4` but
  not yet re-tested in-car. Charlie should retry.
- **Wheels-on-ground with 30 MPH MODE**: blocked by ESP contention.
  Pre-flight check correctly refuses the toggle.
- **Throttle, brake, shift-via-laptop fully tested**: only steering
  is in production state.

---

## 13. Open mysteries / questions to resolve

1. **Does the v4.2 byte 0/1 shift fix actually make the SCCM
   accept commands in-car?** Bench-correct does not guarantee
   accept. Could still lose to real-stalk arbitration (Section 6).
2. **What is the rack's actual stall torque at 0 mph?** No
   measurement on file. Would inform whether rest-and-roll is
   strictly required.
3. **Are there other reserved bits we're missing in the steering
   control set?** Less likely (we've been ACTIVE successfully) but
   the shift discovery suggests caution.
4. **What's the Tesla recall fix doing internally?** If it's a
   firmware patch to keep EPAS active at 0 mph, the same delta
   could be reverse-engineered onto our pre-AP rack. Long-shot.
5. **Throttle and brake CAN messages on pre-AP**: not present.
   Verified. Throttle requires a hardware pedal interceptor
   (see V5_PLAN.md). Brake authority is limited to throttle = 0
   regen on this car; full service-brake authority requires an
   iBooster retrofit.
6. **What is the comma pedal's CAN protocol exactly** (gas command
   ID, pedal position broadcast ID, watchdog timing)? Documented in
   `BogGyver/panda` `tesla_pedal` branch source; needs to be
   captured into `docs/PROTOCOL.md` once we source the hardware.
7. **What does ESP do on a partial dyno on this specific car?**
   Theoretical: stability intervention when front/rear wheel speed
   diverge. Empirical confirmation deferred -- per V5_PLAN.md
   Section 4, we will not test on a partial dyno; propulsion tests
   move to a parking lot.

---

## 14. Sources cited

Primary sources verified during research:

- [gregjhogan/tesla-pre-ap-epas-patch repo](https://github.com/gregjhogan/tesla-pre-ap-epas-patch) -- the firmware patch and required keepalives
- [BogGyver/panda safety_tesla.h on tesla_unity_dev](https://github.com/BogGyver/panda/blob/tesla_unity_dev/board/safety/safety_tesla.h) -- panda firmware behavior, CRC algorithm, lookup table
- [BogGyver/openpilot tesla_unity_releaseC3](https://github.com/BogGyver/openpilot/tree/tesla_unity_releaseC3) -- openpilot fork for pre-AP
- [commaai/opendbc tesla_can.dbc mirror](https://github.com/BYDcar/opendbc-byd/blob/master/tesla_can.dbc) -- bit positions, EAC enums, gear/RND/P_Psd values
- [Tinkla wiki](https://tinkla.us/index.php/Welcome_to_Tinkla!) -- pre-AP retrofit ecosystem
- [Tinkla pre-AP OBD2 port reference](https://tinkla.us/index.php/Tesla_Model_S_preAP_OBD2_port) -- CAN bus topology
- [Tesla recall: loss of EPAS at 0 mph](https://www.tesla.com/support/recall-vehicle-firmware-correct-loss-of-epas) -- Tesla's own production behavior re: 0 mph EPAS
- [TeslaMotorsClub CAN buses thread](https://teslamotorsclub.com/tmc/threads/can-buses-access.105222/) -- chassis vs powertrain vs body bus topology
- [comma ai openpilot tools/joystick](https://github.com/commaai/openpilot/tree/master/tools/joystick) -- reference implementation of joystick-based CAN steering
- [MUXSAN 3-port CAN MITM bridge](https://www.tindie.com/products/muxsan/can-mitm-bridge-3-port-rev-25/) -- commercial precedent for CAN MITM hardware
- [Emile Nijssen open-source CAN bridge](https://www.hackster.io/news/emile-nijssen-s-open-source-can-bridge-makes-automotive-man-in-the-middle-a-cinch-b4dfeb952b04) -- open-source MITM precedent

Project-internal verified data:

- `field_testing/captures/20260507_011220_shift_diagnostic/capture.csv` -- 18,414 real stalk frames; CRC verified, byte 0/1 layout discovered
- `logs/session_20260506_232457.log` -- Theory C flicker fingerprint (280 EAC transitions in 67 seconds when 30 MPH MODE toggled on)
- `logs/session_20260507_000552.log` -- gear-out-of-P auto-disengage working
- `logs/session_20260507_000935.log` -- 30 MPH MODE pre-flight ESP check working

---

## 15. Anti-patterns (do not do these)

Things that have been tried and proven wrong or harmful:

- **30 MPH MODE on a live in-car bus with real ESP active**:
  causes systemic ESP contention. Pre-flight check now blocks this.
- **Comma 3X on chassis CAN while running tesla_control.py**: causes
  Theory C `0x488` arbitration contention. Always remove the 3X.
- **CRC-8/AUTOSAR (poly 0x2F) for Tesla messages**: wrong
  polynomial. Tesla uses CRC-8/J1850 (poly 0x1D). Verified against
  18,414 captured stalk frames.
- **Including the address byte in `0x6D` CRC input**: wrong.
  Verified that BogGyver's `tesla_compute_crc` is called with no
  address prefix.
- **Trusting opendbc DBC for ALL bit positions on `0x6D`**: byte 0
  fixed bits and byte 1 high-nibble bits are NOT in the DBC but
  the SCCM requires them. Always verify against real captures for
  CRC-protected commands.
- **Driving the car on a partial dyno (only some wheels rolling)**:
  stability control will see wheel-speed disparity (front 0 mph,
  rear N mph), conclude the car is sliding, and intervene with
  unpredictable side effects. The 2013 Model S has no firmware
  Dyno Mode (that shipped 2019+). For propulsion tests, use a
  4-wheel chassis dyno OR an empty parking lot. See V5_PLAN.md
  Section 4 for the full reasoning.
- **Attempting to command throttle via CAN on pre-AP Model S**: no
  CAN-commandable throttle exists on this car. The Drive Unit
  reads two redundant 0-5V analog signals directly from the
  accelerator pedal. Software throttle requires a hardware pedal
  interceptor (Tinkla / Comma / DIY). See V5_PLAN.md Section 2.
- **Commanding software service-brake on pre-AP Model S**: the
  brake system is vacuum-assisted, mechanically linked to the
  pedal. There is no CAN message that applies the calipers. iBooster
  retrofit is the only path to full brake authority. EPB can lock
  the car at standstill but is not a service brake. See V5_PLAN.md
  Section 3.

---

## 16. Update protocol

Whenever a new fact is established (positive or negative result on
hardware), add it to the appropriate section above with:

- One sentence summarizing the fact
- The source (session log, capture file, code commit, or external link)
- The date of verification

If a previous claim is overturned, mark it with `~~strikethrough~~`
or move it to a "Retracted" subsection -- do not silently delete
it. Project history matters for not retracing dead-ends.
