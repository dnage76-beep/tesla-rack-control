# Charlie Handoff -- 17 May 2026

Hey Charlie, this is the full pickup-where-we-left-off doc for v5
(the RC bridge). Read this end-to-end before you flash or wire
anything. Everything that matters is linked or pathed below.

GitHub repo: <https://github.com/dnage76-beep/tesla-rack-control>

---

## TL;DR

We built a Spektrum RC bridge for the Tesla rack. v4.3.3 on `main`
still works exactly like it did (slider + keyboard, no radio).
There are now **two RC variants** that live on their own branches:

| Branch | Tag | Hardware | Operator ergonomic |
|---|---|---|---|
| `main` | v4.3.3 | none | Slider + keyboard |
| `dev/v5-rc` | v5.0.3 | DX8 + AR6200 | Plane sticks |
| `dev/v5-slt3` | v5.1.0 | SLT3 + SR315 | Wheel + trigger |

The Arduino firmware is identical between both v5 branches (just
the receiver-source comments differ). The Python program is also
nearly identical -- same expo curve, same calibration, same signal-
loss detection. Only the channel layout and the binding procedure
differ.

---

## The big picture

```
Spektrum TX  -->  Spektrum RX  -->  Arduino Nano  -->  Laptop  -->  SYS TEC  -->  Tesla rack
(DX8 or SLT3)   (AR6200 or SR315)   (PCINT reader,   (Python:           (USB-CAN)   (patched
                                     COBS + CRC8     tesla_control_                  EPAS)
                                     @ 100 Hz)        rc.py)
```

The Nano reads 3 PWM channels from the receiver, frames the values
with COBS + CRC8, and ships them to the laptop at 100 Hz over USB
serial. The laptop runs `tesla_control_rc.py` which subclasses the
v4.3.3 program and writes the decoded stick into `ctrl.target_angle_
deg`. The existing v4.3.3 worker produces `0x488 DAS_steeringControl`
frames on the CAN bus at 50 Hz. **No CAN protocol changes.** All
v4.3.3 safety guards (RX timeout, EAC bounce, real-motion auto-
disengage, park-to-engage, four E-STOP paths) still apply.

---

## File locations (everything in the repo)

All paths are relative to the repo root unless noted. Repo root is
`~/Code/Active/tesla-rack-control` on Derek's machine.

### Code

| File | Lives on | Purpose |
|---|---|---|
| `tesla_control.py` | all branches | v4.3.3 base program. Slider + keyboard. **Untouched by v5.** |
| `tesla_control_rc.py` | `dev/v5-rc`, `dev/v5-slt3` | v5 RC variant. Subclasses base.App, adds RC INPUT panel + serial reader thread. |
| `arduino/tesla_rc_bridge/tesla_rc_bridge.ino` | `dev/v5-rc`, `dev/v5-slt3` | Arduino Nano firmware. PCINT reader, COBS framing, CRC8. ~200 lines. |
| `can_sniffer.py` | all branches | Passive CAN listener. Unchanged. |
| `requirements.txt` | all branches | Python deps. v5 adds `pyserial>=3.5`. |

### Documentation (read these in this order)

| File | Purpose |
|---|---|
| `README.md` | High-level overview. Top of the README mentions v5. |
| `CHANGELOG.md` | Full version history. v5.0.3 and v5.1.0 entries explain what changed. |
| `PROJECT_MEMORY.md` | Canonical fact base for the whole project. Verified protocol facts, EAC enums, hardware identity. |
| `SAFETY.md` | Hard rules. Read before running anything. |
| `docs/RC_SETUP.md` | Plain-text RC setup notes. |
| `docs/build/RC_IMPLEMENTATION_GUIDE.pdf` | **DX8 + AR6200 variant** -- 9 pages, printable. Wiring, binding, expo curve, signal-loss. |
| `docs/build/RC_IMPLEMENTATION_GUIDE_SLT3.pdf` | **SLT3 + SR315 variant** -- 9 pages, printable. Same structure, different receiver. |
| `docs/build/build_rc_guide.py` | Python script that builds the AR6200 PDF. |
| `docs/build/build_rc_guide_slt3.py` | Python script that builds the SR315 PDF. |
| `docs/GUIDE.md`, `docs/PROTOCOL.md`, `docs/TROUBLESHOOTING.md` | v4.3.3 docs. Still apply. |

### Field test data (kept around for reference)

| Path | What's in it |
|---|---|
| `field_testing/sessions/` | Per-session save dirs from the GUI's SAVE TEST button (CSV + log + README). |
| `field_testing/captures/` | CAN sniffer captures. The 18,414-frame stalk capture from 2026-05-07 is here. |
| `logs/` | Local .log + .csv files from each program run. Gitignored. |
| `archive/notes/` | Old conversation snapshots from earlier rounds (Charlie's 04 May field test, etc.). |
| `archive/pdfs/` | v3-era PDFs from before the v4 reorganization. |
| `archive/legacy/` | v1/v2/v3 programs (move.py, steer.py, tesla_steering_test.py). |

### Direct GitHub links

| What | URL |
|---|---|
| Repo root | <https://github.com/dnage76-beep/tesla-rack-control> |
| main (v4.3.3) | <https://github.com/dnage76-beep/tesla-rack-control/tree/main> |
| dev/v5-rc (DX8 + AR6200) | <https://github.com/dnage76-beep/tesla-rack-control/tree/dev/v5-rc> |
| dev/v5-slt3 (SLT3 + SR315) | <https://github.com/dnage76-beep/tesla-rack-control/tree/dev/v5-slt3> |
| All tags | <https://github.com/dnage76-beep/tesla-rack-control/tags> |
| v5.0.3 release | <https://github.com/dnage76-beep/tesla-rack-control/releases/tag/v5.0.3> |
| v5.1.0 release | <https://github.com/dnage76-beep/tesla-rack-control/releases/tag/v5.1.0> |
| AR6200 PDF (raw) | <https://github.com/dnage76-beep/tesla-rack-control/blob/dev/v5-rc/docs/build/RC_IMPLEMENTATION_GUIDE.pdf> |
| SR315 PDF (raw) | <https://github.com/dnage76-beep/tesla-rack-control/blob/dev/v5-slt3/docs/build/RC_IMPLEMENTATION_GUIDE_SLT3.pdf> |

---

## What we did, in order

1. **Audited the project state.** Read main, CHANGELOG, PROJECT_
   MEMORY. v4.3.3 was already production: PRND shift, brake decode,
   30 MPH MODE toggle, image wheel, full 360° lock-to-lock clamp.
   Stalk shift CRC + byte format already fixed, gear shift code is
   bench-correct but not yet field-validated in-car.

2. **Researched the radio gear.** Derek mentioned SLT3, AR6200,
   SR515. Sourced primary documents from Spektrum / Horizon. Key
   findings:
   - SLT3 transmits **SLT FHSS** only.
   - AR6200 is a **DSM2 aircraft** receiver (binds to DX8).
   - SR515 is **DSMR-only** (does not bind to SLT3 OR to DX8).
   - SR315 is **dual-protocol DSMR + SLT** (binds to both SLT3 and DX8 in DSMR mode).
   - DX8 is **DSMX with DSM2 fallback** (binds to AR6200).

   This ruled out using the SLT3 + SR515 combo entirely. We needed
   either DX8 + AR6200 (plane sticks) or SLT3 + SR315 (wheel/trigger).
   Derek has both, so we shipped both.

3. **Built the Arduino firmware** (`arduino/tesla_rc_bridge/
   tesla_rc_bridge.ino`):
   - Reads PWM on pins D2, D3, D4 using pin-change interrupts on
     PORTD (PCINT2 group).
   - On each rising edge, snapshots `micros()`. On falling edge,
     computes pulse width = falling - rising. Stores to a `volatile`
     channel array.
   - Every 10 ms (100 Hz), sends a framed packet: `[seq:u8][ch_steer
     :u16 LE][ch_p:u16 LE][ch_rnd:u16 LE][flags:u8][crc8:u8]`. Total
     9 bytes raw, then COBS-encoded, then terminated by `0x00`.
   - CRC-8/ITU (poly 0x07, init 0x00). Verified against the Python
     decoder on the laptop side.
   - **Firmware is receiver-agnostic.** Same .ino works for both
     AR6200 and SR315; only the header comments mention which.

4. **Built the Python RC program** (`tesla_control_rc.py`):
   - Subclasses `base.App` from `tesla_control.py` v4.3.3. Inherits
     the entire CAN worker, safety architecture, GUI, session logger.
     **Zero changes to v4.3.3.**
   - Adds an `RcReader` daemon thread that opens the pyserial port,
     splits incoming bytes on `0x00`, COBS-decodes, validates CRC,
     and updates a shared `RcInput` object.
   - The reader thread calls `apply_rc_input(steer, p, rnd)` which:
     - Normalizes steering via a `StickCalibration` (running min/max
       envelope -- same as openpilot's `np.interp` approach).
     - Applies a 3% normalized deadband.
     - Applies the openpilot expo curve: `0.4 * x^3 + 0.6 * x`.
     - Scales to `HARD_ANGLE_LIMIT_DEG` (360°) and writes
       `ctrl.target_angle_deg`.
     - For PRND: edge-triggers `request_shift("R" / "N" / "D")` when
       the AUX1 PWM bucket changes.
     - For P button: debounces low-PWM for 200 ms, fires a P shift
       with a 1-second cooldown.

5. **Added signal-loss detection.** Spektrum receivers hold-last on
   TX power-off (SmartSafe). Without detection a dead TX looks like
   a stationary stick. Two indicators:
   - **NO SERIAL**: no COBS frame for > 200 ms.
   - **TX LOST**: aileron PWM unchanged > 2 us within 3 s.
   - **LIVE (green)**: both clear.
   A checkbox in the RC INPUT panel opts in to dropping
   `ctrl.engaged` when either condition fires. Off by default.

6. **Built two printable PDFs**, matching the visual style of
   ROADMAP.pdf:
   - `RC_IMPLEMENTATION_GUIDE.pdf` for the DX8 + AR6200 variant.
   - `RC_IMPLEMENTATION_GUIDE_SLT3.pdf` for the SLT3 + SR315
     variant.

   The pinout diagram on page 3 of each PDF was visually verified
   for no wire crossings and no false-connection artifacts.

7. **Tagged and pushed** five intermediate RC tags (`v5.0.0-rc1`,
   `rc2`, `rc3`) and two real releases (`v5.0.3` and `v5.1.0`).

---

## v5.0.3 -- DX8 + AR6200 (plane sticks)

Branch: `dev/v5-rc`. PDF:
`docs/build/RC_IMPLEMENTATION_GUIDE.pdf`.

### Hardware

| Item | Part number | Purpose |
|---|---|---|
| Spektrum DX8 transmitter | SPMR8000 (Gen 2) | Operator radio |
| Spektrum AR6200 receiver | SPMAR6200 | DSM2 aircraft, 6 PWM channels |
| Arduino Nano | ATmega328P, 16 MHz | PWM-to-USB bridge |
| Servo lead wires | --  | AR6200 to Nano signals |
| Mini-USB cable | --  | Nano to laptop |

### Channel map

| AR6200 channel | DX8 control | Nano pin | Function |
|---|---|---|---|
| ch2 AILE | right stick X | D2 (PCINT18) | Steering |
| ch5 GEAR | gear toggle | D3 (PCINT19) | P button (pulled to -100% / ~1000 us = pressed) |
| ch6 AUX1 | 3-pos switch | D4 (PCINT20) | R/N/D selector |

### AUX1 hysteresis

- < 1250 us = D
- 1250 - 1750 us = N
- > 1750 us = R

### Binding (AR6200 to DX8)

Aircraft-style with a bind plug:

1. Insert the bind plug into the AR6200's BIND/DATA port.
2. Power the AR6200 (any servo port: GND + 5V).
3. LED flashes rapidly.
4. Hold the DX8 trainer switch while powering it on.
5. LED goes solid = bound.
6. Power-cycle the AR6200, remove the bind plug.

---

## v5.1.0 -- SLT3 + SR315 (wheel/trigger)

Branch: `dev/v5-slt3`. PDF:
`docs/build/RC_IMPLEMENTATION_GUIDE_SLT3.pdf`.

### Hardware

| Item | Part number | Purpose |
|---|---|---|
| Spektrum SLT3 transmitter | SPMSLT300 (bundle SKU) | Operator radio (wheel/trigger) |
| Spektrum SR315 receiver | SPMSR315 | DSMR + SLT, 3 PWM channels |
| Arduino Nano | same | same |
| Servo lead wires | same | same |
| Mini-USB cable | same | same |

### Channel map

| SR315 channel | SLT3 control | Nano pin | Function |
|---|---|---|---|
| ch1 STR | wheel | D2 (PCINT18) | Steering |
| ch2 THR | trigger | D3 (PCINT19) | P button (pushed forward, ~1000 us = pressed) |
| ch3 AUX1 | rocker | D4 (PCINT20) | R/N/D selector |

### AUX1 hysteresis

Same thresholds as v5.0.3 (< 1250 = D, 1250 - 1750 = N, > 1750 = R)
but on the rocker switch instead of the toggle. **Direction may
need to be flipped if the SLT3's rocker reads inverted.** Check
visually in the RC INPUT panel when you first run it.

### Binding (SR315 to SLT3)

Surface-style with a bind button. **Failsafe positions are captured
at bind time** so set the wheel centered, trigger at rest, AUX1
center before powering on the SLT3.

1. Power the SR315.
2. Press the SR315 bind button THREE TIMES within 1.5 seconds.
3. Receiver LED flashes with a pause pattern.
4. Hold the SLT3 wheel CENTERED, trigger AT REST, AUX1 CENTER.
5. Power on the SLT3. Both LEDs go solid = bound.

Reference: SR315 SLT bind slip sheet and SLT3 user guide, both
linked in the PDF references section.

---

## Steering math (both variants)

This is the part Derek wanted aligned with how real RC pros do it.
It matches openpilot's `tools/joystick/joystickd.py` line-for-line.

Source: <https://github.com/commaai/openpilot/blob/master/tools/
joystick/joystickd.py>

```python
norm = StickCalibration.normalize(raw_us)   # running min/max envelope
if abs(norm) < 0.03:                         # 3% normalized deadband
    norm = 0.0
shaped = 0.4 * norm**3 + 0.6 * norm           # cubic-blend expo
angle_deg = shaped * HARD_ANGLE_LIMIT_DEG     # scale to ±360°
```

Result at representative stick positions:

| Stick | Wheel |
|---|---|
| 5% | 11° |
| 10% | 22° |
| 25% | 56° |
| 50% | 126° |
| 75% | 223° |
| 100% | 360° |

Linear feel near center for fine corrections; more aggressive at
the extremes for lock-to-lock parking maneuvers. The math is
unchanged between v5.0.3 and v5.1.0.

---

## Safety architecture (both variants)

Everything from v4.3.3 still applies, plus the RC-specific signal-
loss indicators. None of this is new code on v5 -- it's all the
v4.3.3 worker's existing watchdogs.

| Guard | Trigger | Action |
|---|---|---|
| Hard angle clamp | command exceeds ±360° | Truncate |
| Output rate limit | command rate exceeds 150°/s | Rate-limit at the worker |
| RX timeout | no `0x370` from rack for > 500 ms | E-STOP |
| EAC bounce | > 5 EAC transitions / second | E-STOP |
| Real-motion auto-disengage | `DI_vehicleSpeed` > 1 mph | Drop ctrl.engaged |
| Park-to-engage gate | gear ≠ P when ENGAGE is requested | Refuse |
| ESC / Q / E-STOP button / window close | user action | E-STOP |
| **NO SERIAL** (v5 new) | no Arduino frame for > 200 ms | UI indicator |
| **TX LOST** (v5 new) | aileron PWM frozen > 3 s | UI indicator |
| **Auto-disengage on signal loss** (v5, opt-in) | NO SERIAL or TX LOST + checkbox checked | Drop ctrl.engaged |

---

## Latency budget (calculated, not measured)

End-to-end stick-to-wheel:

| Stage | Typical | Worst |
|---|---|---|
| Spektrum 22 ms airframe | 11 ms | 22 ms |
| AR6200 / SR315 decode | 2 ms | 3 ms |
| Arduino PCINT measurement | 1 ms | 2 ms |
| Arduino tx tick (100 Hz) | 5 ms | 10 ms |
| USB CDC transit | 2 ms | 5 ms |
| Python decode + apply | 1 ms | 3 ms |
| Worker tick (50 Hz) | 10 ms | 20 ms |
| CAN frame TX | < 1 ms | 1 ms |
| Rack reaction | 10 ms | 20 ms |
| **Total** | **~40 ms** | **~85 ms** |

Below sim-racing thresholds for "feels real-time". The rate limit
(150°/s on the worker) is a separate concern -- a full lock command
from center takes 2.4 seconds to physically reach lock even with
zero latency, which is mechanical kindness on the rack, not latency.

---

## How to run, step by step

Same for both variants once the right branch is checked out.

```bash
# pick a branch
git checkout dev/v5-rc     # for DX8 + AR6200
# or
git checkout dev/v5-slt3   # for SLT3 + SR315

# flash the Nano (only needed if firmware changed)
cd arduino/tesla_rc_bridge
arduino-cli core install arduino:avr
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 .
arduino-cli upload  --fqbn arduino:avr:nano:cpu=atmega328 -p <PORT> .
# clone Nanos: use cpu=atmega328old instead

# back to the repo root
cd ../..

# install Python deps if first time
pip install -r requirements.txt

# bind the receiver to the TX per the PDF (procedure differs by variant)

# wire the receiver to the Nano per PDF section 4 / 5

# run
python tesla_control_rc.py --rc-port COM5
# macOS: --rc-port /dev/cu.usbserial-XXX
```

In the GUI:

1. CONNECT (opens CAN).
2. Verify bus diagnostic panel shows `0x370` at ~100 Hz and `0x488`
   RX at 0 Hz (we own that ID, nobody else should be transmitting).
3. Sweep the wheel / stick fully left and right once to seed
   calibration. STICK range should turn green.
4. Verify the RC INPUT panel shows STEER us tracking the stick.
5. ENGAGE. EAC transitions INHIBITED → AVAILABLE → ACTIVE.
6. Drive.
7. ESC / Q / E-STOP / close window = disengage.

---

## What v5 explicitly is NOT

- **Throttle.** Pre-AP 2013 Model S has no CAN-commandable
  throttle -- the Drive Unit reads two redundant 0-5V analog
  signals directly from the accelerator pedal. A hardware pedal
  interceptor (Tinkla, comma pedal, or DIY STM32) is required.
  See `V5_PLAN.md` for the full analysis.
- **Brake.** Vacuum-assisted brake system, no iBooster on 2013.
  No software-commanded service brake authority without an
  iBooster retrofit (significant invasive work).
- **In-car testing.** Both v5 branches are bench-only at this
  point. The first real in-car run should be on jacks per the
  standard procedure in SAFETY.md.

These are all v6+ scope.

---

## What I want you to do, Charlie

In priority order. Don't skip ahead.

### 1. Bench-validate the bridge (no rack)

Goal: verify the Arduino firmware reads PWM correctly and the
Python program decodes it.

1. Pick a variant. DX8 + AR6200 is the path of least resistance
   since it's the AR6200 we used in earlier rounds.
2. Bind the receiver to the TX per the PDF.
3. Wire the receiver to the Nano per PDF section 4 (only 3 SIG
   wires + 5V + GND, the diagram on page 3 is exact).
4. Flash the Nano.
5. Run `python tesla_control_rc.py --rc-port <PORT>`.
6. **Don't click CONNECT yet.** Just verify the RC INPUT panel
   populates:
   - PORT = OPEN (green)
   - FRAMES incrementing at ~100/sec
   - STEER us tracking the stick (~1000 - 2000 us)
   - RND us tracking the AUX1 switch
   - P us tracking the GEAR toggle
   - SIGNAL = LIVE (green) when the TX is on
7. Power off the DX8. SIGNAL should go to TX LOST within 3 seconds.
8. Unplug the Nano. SIGNAL should go to NO SERIAL within 200 ms.
9. Plug it back in, power the TX back on. SIGNAL goes back to LIVE.

If any of this fails, screenshot the panel and the field test log
(`logs/session_*.log`) and send to Derek.

### 2. Bench-validate steering (rack on, NOT in car)

Same setup, but now wire the SYS TEC USB-CAN to a bench rack with
no wheels touching anything.

1. CONNECT. Bus diagnostic should populate.
2. Sweep the stick once for calibration.
3. ENGAGE. EAC should reach ACTIVE.
4. Slowly move the stick to about ±10°. Wheel should track.
5. If it tracks cleanly, ramp up gradually. Don't slam to lock.
6. SAVE TEST (use the GUI button) at the end. The CSV + log goes
   into `field_testing/sessions/` and gets committed + pushed
   automatically.

### 3. Try the SLT3 + SR315 variant

Once the AR6200 variant is known-good, switch branches:

```bash
git checkout dev/v5-slt3
```

Re-bind, re-wire (the wiring diagram is on page 3 of the SLT3 PDF
and uses ch1 STR / ch2 THR / ch3 AUX1 instead of ch2 / ch5 / ch6),
re-flash if you want (firmware is byte-identical except for
comments). Run the same bench validation. The trigger gesture for
P is different from the GEAR toggle -- push the trigger fully
forward and hold for 200 ms.

### 4. Open question to test

Derek and I never bench-validated whether the SLT3's AUX1 rocker
reads HIGH = R or HIGH = D. The code assumes LOW = D and HIGH = R
(same as the DX8 variant's AUX1). When you have the SLT3 + SR315
binding working, flip the rocker and watch the RND us cell. If
it reads ~1000 us in the position you want for D, the polarity
is correct. If it reads ~2000 us in the D position, flip the
returns in `_rnd_pwm_to_gear` in `tesla_control_rc.py`.

---

## What you should NOT touch

- `tesla_control.py`. v4.3.3 is production. Don't change it.
- `0x488` CAN protocol. The wire format and rates are right.
- The expo curve coefficient (0.4). Openpilot uses this exact
  value in production; we're matching it on purpose.
- The safety constants in `tesla_control.py` (RX_TIMEOUT_MS,
  EAC_BOUNCE_LIMIT_PER_SEC, etc.). These came out of the May 2026
  field tests for a reason.

---

## Open items to think about (low priority)

- **No source-change ramp-in.** When you click ENGAGE with the
  stick off-center, the wheel snaps to that angle as fast as the
  rate limiter allows. v4.3.3's LPF softens this (tau = 0.15 s)
  but doesn't eliminate it. Worth adding a 500 ms ramp-in on the
  first valid RC frame. Not a v5 scope thing -- noted in the
  self-grade.
- **Single PDF for both variants?** Right now there are two near-
  identical PDFs. Could be one PDF with both variants documented
  side by side. Might be cleaner.
- **Single Python file for both variants?** Add a `--rx-type
  {ar6200, sr315}` flag that flips the channel mapping. ~30 line
  diff. Worth doing when you're confident both work.

---

## Self-grade summary

I graded our own code against openpilot's joystickd.py and what
the RC car community does. **Overall B**. The steering math is
professional-grade and matches commaai's production code line-by-
line. We lose points for:

- No source-change ramp-in (mechanical kindness, not safety).
- No bidirectional serial protocol (Arduino can't blink an LED
  when laptop is alive -- one-way only).

The signal-loss detection covers what would otherwise be the
biggest weakness (Spektrum hold-last semantics).

Full self-grade text is in the v5.0.0-rc2 commit message:
<https://github.com/dnage76-beep/tesla-rack-control/commit/a45720f>

---

## Where to ask questions

- Project owner: Derek Nagel (847-226-3311, dnage76@gmail.com)
- Repo: <https://github.com/dnage76-beep/tesla-rack-control>
- Earlier handoff notes from Derek to you (read these for
  historical context):
  - `archive/notes/NOTES_FOR_CHARLIE.md` (04 May 2026)
  - `archive/notes/NOTES_FOR_CHARLIE_05MAY.md` (Theory C diagnosis)
- The v4.x flicker / contention history is documented in
  `PROJECT_MEMORY.md` Section 8 (Theory C) and Section 9 (ESP
  contention). Don't re-derive it.

---

Good luck. The bench setup is the riskiest part. Once both
variants pass bench validation we move to wheels-on-jacks in-car,
then parking lot, then deciding whether to push toward v6
(throttle + brake).

-- Derek (notes drafted with Claude, 17 May 2026)
