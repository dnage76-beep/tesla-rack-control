# Tesla Rack Control v4 -- Troubleshooting Guide

Symptom-driven troubleshooting. Find your symptom, follow the steps,
collect the artifacts that point at the next move.

For first-time setup, see `GUIDE_V4.md`.

---

## Quick decision tree

```
Did you click CONNECT and see "EPAS LINK OK" within 3 seconds?
  NO  -> jump to "no link"
  YES -> Did EAC reach ACTIVE after ENGAGE?
           NO  -> jump to "stuck in INHIBITED" or "EAC flicker"
                  (depends on whether EAC is steady or bouncing)
           YES -> Did the rack actually move?
                    NO  -> jump to "ACTIVE but no motion"
                    YES -> Did motion stop unexpectedly?
                             NO  -> you are done. pat self on back.
                             YES -> jump to "unexpected disengage"
```

---

## "no link" -- CONNECT does not show EPAS LINK OK

### Symptom

After CONNECT, the header light stays at `WAITING FOR 0x370...`
(yellow) for more than 3 seconds. Bus diagnostic panel shows no
traffic at all OR shows traffic but the `0x370` row is at 0 Hz.

### Step 1: Confirm the SYS TEC opened the bus

Look at the event log immediately after CONNECT. You should see:

```
CAN open: SYS TEC dev=0 ch=0 500 kbps
```

If instead you see `CAN open FAILED: ...`:

- The SYS TEC driver is not installed or not visible to python-can.
  Reinstall the sysWORXX driver from the SYS TEC website. Reboot.
- Another program already has the SYS TEC open. Close any other CAN
  tool (PCAN-View, sniffers, etc.) and try again.
- USB cable is bad or unseated. Try a different port.

### Step 2: Confirm there is ANY traffic on the bus

Look at the bus diagnostic panel. If every row says 0 Hz:

- The car is off. Turn the key to ACC or ON.
- The SYS TEC is plugged into a wire that is not chassis CAN.
  Possible causes:
  - On the OBD port, you wired pins 1 and 9 backwards (CAN H/L
    swapped). Try swapping. There is no harm in trying both ways.
  - You are at the X437/TDC connector but on the wrong pin pair
    (Tesla has multiple CAN buses there). See
    `PINOUT_VERIFICATION.pdf` for the correct pair.
- The SYS TEC's internal terminator is needed but not enabled.
  Connect a 120-ohm resistor between CAN H and CAN L at the SYS
  TEC end. Or use the cleaner X437/TDC tap which is in parallel
  with the bus's existing termination.

### Step 3: Confirm 0x370 specifically

If the bus has plenty of traffic but `0x370` stays at 0 Hz:

- The rack is off the bus. The relay between the rack and chassis
  CAN may be open (the rack only joins the bus at certain ignition
  states). Cycle the key.
- The rack is broken. (Unlikely but not impossible.) Run
  `can_sniffer.py` for 60 seconds with the SYS TEC at the same
  tap. If you see `0x370` there but not in v4, file a bug.

### What to send Claude

The first 30 lines of the event log, plus a screenshot of the bus
diagnostic panel.

---

## "stuck in INHIBITED" -- EAC does not leave INHIBITED after ENGAGE

### Symptom

CONNECT works, EPAS LINK OK shows green, but after ENGAGE the EAC
status panel stays solidly at `INHIBITED` and the Last Error column
shows something specific. EAC is not bouncing -- it is stuck.

### Read the error code

Look at the **Last Error** field. The rack is telling you exactly
what is missing:

| Error              | What the rack is complaining about                                        | Fix                                                                                  |
|--------------------|---------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| `OUT_OF_RANGE`     | A required keepalive message is missing OR off-rate                       | See "missing keepalives" below                                                       |
| `MIN_SPEED`        | Vehicle speed is below the rack's gate, or `0x155` is not on the bus      | If on bench, set `SYNTHESIZE_SPEED = True`. If in car, real ESP is silent.           |
| `EPB_INHIBIT`      | EPB module is reporting inhibit, OR `0x214` is missing/malformed          | Confirm `SYNTHESIZE_EPB = True` and 0x214 row in diagnostic shows ~10 Hz             |
| `HANDS_ON`         | Driver torque sensor reads non-zero                                       | Take hands off the wheel. Wait 2 seconds. Try ENGAGE again.                          |
| `BUS_FAULT`        | CAN bus errors                                                            | See "bus errors" below                                                               |
| `ECU_FAULT`        | Internal rack fault                                                       | Power-cycle the car. If persistent, the rack itself is the problem.                  |
| `INVALID_REQ`      | Our `0x488` is malformed                                                  | This should never happen with v4. File a bug with the session CSV.                   |
| `TIMEOUT`          | A required input has stopped arriving                                     | Same root cause as `OUT_OF_RANGE`                                                    |

### "missing keepalives" -- the OUT_OF_RANGE / TIMEOUT path

Look at the bus diagnostic panel and confirm each of these matches
expectation:

| ID    | In car (default flags) | On bench (all synth flags True) |
|-------|------------------------|---------------------------------|
| 0x101 | ~10 Hz (from real GTW) | ~20 Hz (from us)                |
| 0x214 | ~10 Hz (from us)       | ~10 Hz (from us)                |
| 0x155 | ~50 Hz (from real ESP) | ~50 Hz (from us)                |

If a row is at 0 Hz when it should not be:

- **0x101 missing in car**: the real Tesla GTW is not on the bus.
  Did you tap into a different sub-bus (powertrain instead of
  chassis)? Run `can_sniffer.py` to confirm you see GTW messages.
- **0x214 missing**: confirm `SYNTHESIZE_EPB = True` at the top of
  `tesla_control_v4.py`. If the constant is True but the row is
  still 0 Hz, the worker thread crashed. Check the event log for
  `TX 0x214 failed:` lines.
- **0x155 missing in car**: the real ESP module is not on this bus,
  or the car is in a state where ESP does not transmit. Either set
  `SYNTHESIZE_SPEED = True` (with the rack jacked up so contention
  with the real ESP later is not an issue) or fix the wiring to
  hit the right sub-bus.

### What to send Claude

- Screenshot of bus diagnostic panel
- Screenshot of status panel showing the EAC error code
- The session .log file (the EAC transition history is gold)

---

## "EAC flicker" -- EAC bounces between INHIBITED, AVAILABLE, ACTIVE

### Symptom

After ENGAGE, the EAC status panel rapidly cycles through INHIBITED,
AVAILABLE, ACTIVE many times per second. Most common error is
`HIGH_ANGLE_RATE_REQ`. This is the bug from May 2026.

### Diagnosis: a second transmitter is on `0x488`

**Look at the bus diagnostic panel. Find the `0x488` row.**

- **If `0x488` Hz is RED and non-zero**: confirmed. Some other
  device on the bus is also transmitting `0x488`, fighting your
  laptop for arbitration. Find and remove that device. The usual
  suspect is a comma 3X, comma 3, or comma red panda someone
  forgot to disconnect.
- **If `0x488` Hz is at 0.0**: my Theory C diagnosis was wrong.
  Take a screenshot, save the session log, and send to Claude for
  a fresh look. Possible alternatives: a real internal-counter
  bug in v4's `0x488` builder, or the patched rack has a check we
  do not know about.

### Fix path 1: physically remove the other transmitter

Unplug the comma device from the chassis CAN bus entirely. Cycle
the SYS TEC's CONNECT button to clear stats. The `0x488` row
should now stay at 0.0 Hz. Re-engage.

### Fix path 2: if the other transmitter cannot be removed

- If for some reason the comma 3X must stay powered (e.g. it is
  providing display visualization you want to keep), then v4
  cannot work on the same bus. Use one or the other.
- The "patch the panda firmware to skip 0x488 generation" path
  is a real option, but it is a firmware change and a re-flash.
  See the May 2026 conversation transcript for the file and line
  to patch.

### What to send Claude

- Screenshot of bus diagnostic panel showing the `0x488` row
- Session CSV (the EAC bouncing pattern is visible row by row)
- Confirmation of whether or not a comma device was on the bus

---

## "ACTIVE but no motion" -- EAC is green ACTIVE but rack does not move

### Symptom

EAC status panel shows ACTIVE solidly. Last Error shows NONE. The
`Commanded` field changes when you move the slider, but the
`Measured` field stays at 0 (or stays at whatever it was when you
engaged).

### Step 1: Confirm 0x488 is actually being transmitted

Look at the bus diagnostic panel. The `0x488` row should be at 0.0
Hz **for RX** (we never receive our own frames) but you have no
direct confirmation that we are sending. To confirm, run
`can_sniffer.py` from a second laptop / another adapter while v4 is
running, and look for `0x488` at ~50 Hz with our angle data.

If you only have one adapter, look at the event log for any
`TX 0x488 failed:` line. If the worker is failing to send, every
attempt would log.

### Step 2: Confirm the rack has motor power

The patched rack still requires 12V on its power pin. If the rack
is on the bench and only the CAN harness is connected, the rack is
listening but cannot move. Confirm the power harness is plugged in.

### Step 3: Confirm wheels are free

If the wheels are on the ground at standstill, the rack will load
up but not move (it's pushing against the road). Jack up the front
of the car or disconnect the tie rods.

### Step 4: Are we exceeding the standstill ceiling?

The rack rejects commanded angles above ~60 degrees at 0 km/h.
v4's hard clamp is 60 by default, so this should not be a factor,
but if you have raised the clamp, you can hit this. Check the
target value -- if it is at clamp, lower the clamp.

### What to send Claude

- Session CSV
- Confirmation of: 12V on rack, wheels free, target inside clamp

---

## "unexpected disengage" -- E-STOP fires during a run

### Symptom

Mid-run, the GUI flashes red, the header shows `E-STOP: <reason>`,
and the rack disengages on its own.

### Read the reason

The reason is shown in the header bar AND written to the event log
in the format `E-STOP: <reason>`. Possible reasons:

| Reason                              | Meaning                                            | Action                                                                                               |
|-------------------------------------|----------------------------------------------------|------------------------------------------------------------------------------------------------------|
| `rack FAULT, EAC_ERROR=<x>`         | Rack moved itself into FAULT state                 | Look at the error code -- same table as "stuck in INHIBITED" above                                   |
| `no 0x370 for <ms> ms`              | Rack stopped responding for >500 ms                | Bus glitch, loose connector, or rack lost power. Reseat connectors and reconnect.                    |
| `angle divergence <deg> deg`        | Rack lagged commanded angle by >15 degrees         | Rack is overloaded or you commanded too aggressively. Lower target or wait for catch-up before next. |
| `bus error count <n>`               | More than 50 CAN error frames                      | Bad termination, wrong baud, or H/L swap intermittent                                                |
| `loop overrun <ms> ms`              | Worker thread missed its 50 Hz tick by >100 ms     | Laptop is starved. Close other apps. Plug into power, not battery.                                   |
| `TX 0x488 failed: ...`              | python-can refused to send                         | SYS TEC adapter dropped off USB or driver crashed. Reconnect.                                        |
| `RX exception: ...`                 | python-can blew up on receive                      | Same as above                                                                                        |
| `disconnect requested`              | You clicked DISCONNECT                             | This is fine                                                                                         |
| `window closed`                     | You closed the window                              | This is fine                                                                                         |
| `ESC key`, `Q key`, `button`        | You pressed an E-STOP                              | This is fine                                                                                         |

### What to send Claude

- The full event log line for the E-STOP plus the 30 lines before
  it
- The session CSV around the E-STOP timestamp (the rows just before
  show what the rack was doing)

---

## Bus errors -- `bus_errors` count grows

### Symptom

The `Bus Errors` field in the status panel ticks upward. At >50 the
program E-STOPs.

### Diagnosis

CAN bus errors come from:

- **Wrong bitrate**: every device on a CAN bus must agree on the
  bitrate. v4 hardcodes 500 kbps. Tesla chassis CAN is 500 kbps.
  If you see errors, you may be on a different sub-bus.
- **Termination**: CAN buses need exactly two 120-ohm terminations
  total, one at each end. The Tesla bus already has its own
  terminations. If you have added a 120-ohm at the SYS TEC end on
  top, you have over-termination. Remove the extra.
- **H/L swap**: occasional intermittent if a connector is
  marginally crimped.
- **Stub length**: the wire from the chassis CAN bus to the SYS
  TEC should be short (under ~30 cm).

### What to send Claude

The bus error count, and a description of your wiring (length of
stubs, where you tapped, whether you added a terminator).

---

## Logs -- finding and reading them

Logs land in `./logs/` next to `tesla_control_v4.py`. Each session
gets two files:

```
logs/session_20260506_152314.log
logs/session_20260506_152314.csv
```

### .log file

One line per event. Plain text. Open in any text editor. Format:

```
[2026-05-06 15:23:14.812] CAN open: SYS TEC dev=0 ch=0 500 kbps
[2026-05-06 15:23:14.815] keepalive plan: GTW=False EPB=True SPEED=False
[2026-05-06 15:23:15.022] EAC: INHIBITED -> AVAILABLE (err=NONE)
[2026-05-06 15:23:15.044] EAC: AVAILABLE -> ACTIVE (err=NONE)
[2026-05-06 15:23:18.450] target set to +15.0 deg
[2026-05-06 15:23:21.200] DISENGAGED
[2026-05-06 15:23:21.205] EAC: ACTIVE -> AVAILABLE (err=NONE)
```

### .csv file

One row per ~100 ms (every 10th `0x370` frame), plus extra rows on
state changes. Columns:

```
wall_time, monotonic, event, mode, engaged, estop,
target_deg, commanded_deg, measured_deg,
eac_status, eac_error, rx_count_0x370, bus_errors
```

Open in Excel, pandas, anything. The `monotonic` column is seconds
since session start, which is useful for plotting. The `event`
column is empty for periodic samples and tagged for transitions.

### What Claude can do with these

- Reconstruct the EAC state machine timeline
- Plot commanded vs measured to see lag, divergence, oscillation
- Verify keepalive timing
- Spot patterns invisible in real time

Always send both files together.

---

## When all else fails

1. Save the session log
2. Run `can_sniffer.py` for 60 seconds and screenshot it
3. Take a clear photo of the wiring at the SYS TEC tap
4. Post the three artifacts plus a one-paragraph description of
   what you were doing and what went wrong
5. Sit on your hands. Do not start changing things until the
   root cause is identified, otherwise you risk masking the
   problem.
