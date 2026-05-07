# Troubleshooting -- `tesla_control_v4_1.py`

Symptom-driven troubleshooting for the current program. Find your
symptom, follow the steps, collect the artifacts that point at the
next move.

For first-time setup, see `GUIDE.md`. For the CAN protocol
reference, see `PROTOCOL.md`.

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
                             NO  -> done
                             YES -> jump to "unexpected disengage"

Was 30 MPH MODE involved?
  See "ESP contention" section.
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
keepalive plan: GTW=False EPB=True 30MPH=False
```

If instead you see `CAN open FAILED: ...`:

- The SYS TEC driver is not installed or not visible to python-can.
  Reinstall the sysWORXX driver. Reboot.
- Another program already has the SYS TEC open. Close any other CAN
  tool (PCAN-View, sniffers, etc.) and try again.
- USB cable is bad or unseated. Try a different port.

### Step 2: Confirm there is ANY traffic on the bus

Look at the bus diagnostic panel. If every row says 0 Hz:

- The car is off. Turn the key to ACC or ON.
- The SYS TEC is plugged into a wire that is not chassis CAN.
  - On the OBD port, you wired pins 1 and 9 backwards (CAN H/L
    swapped). Try swapping. There is no harm in trying both ways.
  - You are at the X437/TDC connector but on the wrong pin pair.
    See `archive/pdfs/PINOUT_VERIFICATION.pdf`.
- The SYS TEC's internal terminator is needed but not enabled.
  Connect a 120-ohm resistor between CAN H and CAN L at the SYS
  TEC end. Or use the cleaner X437/TDC tap which is in parallel
  with the bus's existing termination.

### Step 3: Confirm 0x370 specifically

If the bus has plenty of traffic but `0x370` stays at 0 Hz:

- The rack is off the bus. The relay between the rack and chassis
  CAN may be open (the rack only joins the bus at certain ignition
  states). Cycle the key.
- The rack is broken. Run `can_sniffer.py` for 60 seconds with the
  SYS TEC at the same tap. If you see `0x370` there but not in
  v4.1, file a bug.

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
| `MIN_SPEED`        | Vehicle speed below rack's gate, OR `0x155` not on the bus                | Click 30 MPH MODE ON. If on bench, the real ESP is silent so this is your fix.       |
| `EPB_INHIBIT`      | EPB module reporting inhibit, OR `0x214` missing/malformed                | Confirm `SYNTHESIZE_EPB = True` and 0x214 row in diagnostic shows ~10 Hz             |
| `HANDS_ON`         | Driver torque sensor reads non-zero                                       | Take hands off the wheel. Wait 2 seconds. Try ENGAGE again.                          |
| `BUS_FAULT`        | CAN bus errors                                                            | See "bus errors" below                                                               |
| `ECU_FAULT`        | Internal rack fault                                                       | Power-cycle the car. If persistent, the rack itself is the problem.                  |
| `INVALID_REQ`      | Our `0x488` is malformed                                                  | This should never happen with v4.1. File a bug with the session CSV.                 |
| `TIMEOUT`          | A required input has stopped arriving                                     | Same root cause as `OUT_OF_RANGE`                                                    |

### "missing keepalives" -- the OUT_OF_RANGE / TIMEOUT path

Look at the bus diagnostic panel and confirm each of these matches
expectation:

| ID    | In car (default flags)  | On bench (with `SYNTHESIZE_GTW = True`) |
|-------|-------------------------|------------------------------------------|
| 0x101 | ~10 Hz (real GTW)       | ~20 Hz (from us)                         |
| 0x214 | ~10 Hz (from us)        | ~10 Hz (from us)                         |
| 0x155 | ~50 Hz (real ESP)       | depends on 30 MPH MODE toggle            |

If a row is at 0 Hz when it should not be:

- **0x101 missing in car**: the real Tesla GTW is not on the bus.
  Did you tap into a different sub-bus (powertrain instead of
  chassis)? Run `can_sniffer.py` to confirm you see GTW messages.
- **0x214 missing**: confirm `SYNTHESIZE_EPB = True` at the top of
  `tesla_control_v4_1.py`. If True but the row is still 0 Hz, the
  worker thread crashed. Check the event log for `TX 0x214 failed:`
  lines.
- **0x155 missing in car**: the real ESP module is not on this bus,
  or the car is in a state where ESP does not transmit. Click 30
  MPH MODE ON to provide it ourselves (jacks only).

### What to send Claude

- Screenshot of bus diagnostic panel
- Screenshot of status panel showing the EAC error code
- Note whether 30 MPH MODE was ON or OFF
- The session .log file (the EAC transition history is gold)

---

## "EAC flicker" -- EAC bounces between INHIBITED, AVAILABLE, ACTIVE

### Symptom

After ENGAGE, the EAC status panel rapidly cycles through INHIBITED,
AVAILABLE, ACTIVE many times per second. Most common error is
`HIGH_ANGLE_RATE_REQ`. This is the bug from May 2026.

### Diagnosis: a second transmitter is on `0x488`

**Look at the bus diagnostic panel. Find the `0x488` row.**

- **`0x488` Hz is RED and non-zero**: confirmed. Some other device
  on the bus is also transmitting `0x488`, fighting your laptop for
  arbitration. Find and remove that device. The usual suspect is a
  comma 3X / 3 / red panda someone forgot to disconnect.
- **`0x488` Hz at 0.0**: Theory C is wrong. Take a screenshot, save
  the session log, and send to Claude for a fresh look.

### Fix path

Unplug the comma device from the chassis CAN bus entirely. Cycle
the SYS TEC's CONNECT to clear stats. The `0x488` row should now
stay at 0.0 Hz. Re-engage.

### What to send Claude

- Screenshot of bus diagnostic panel showing the `0x488` row
- Session CSV (the EAC bouncing pattern is visible row by row)
- Confirmation of whether or not a comma device was on the bus

---

## "ESP contention" -- 0x155 row red while 30 MPH MODE is ON

### Symptom

You enabled 30 MPH MODE. The bus diagnostic panel `0x155` row is
red. The keepalive panel shows
`! REAL ESP DETECTED ON BUS -- contention with our 0x155`.
EAC may be flickering between MIN_SPEED and ACTIVE.

### Diagnosis

The real Tesla ESP module is on the bus and transmitting `0x155` at
50 Hz. We are also transmitting `0x155` at 200 Hz. Two transmitters,
same arbitration ID, same situation as the `0x488` flicker bug --
just on speed instead of steering.

### Effects depending on car state

- **On jacks**: EAC will blip occasionally as real-ESP frames leak
  through (real ESP says 0 km/h, briefly triggers MIN_SPEED gating
  before our 30 km/h frame re-acquires). The rack mostly tracks
  fine. Acceptable for testing but not silent.
- **On wheels, car not actually moving**: dangerous. The rack's
  torque envelope opens for "30 km/h" and slams shut for "0 km/h"
  repeatedly. Stop.
- **On wheels, car actually moving**: never run this configuration.
  Two transmitters on speed = one is lying = the rack believes
  whichever frame won the last arbitration race. Don't.

### Fix paths in order of preference

1. **Don't use 30 MPH MODE on a live car.** If the rack is in the
   car with the real ESP alive, you don't need 30 MPH MODE for
   modest-angle steering at standstill (the rack accepts +/- 60
   degrees natively). Most testing fits within the standstill
   envelope.
2. **Physically disconnect the ESP module.** Invasive but eliminates
   contention. Suitable for serious bench work where you want the
   full at-speed envelope.
3. **Accept the brief blips on jacks.** The 4-to-1 transmission rate
   means our frames win most arbitration races. The rack
   re-acquires within a frame or two of any leak.

### What to send Claude

- Screenshot of bus diagnostic panel with the red 0x155 row
- Session CSV around the time of the flicker
- Description of what the car was doing (jacks / wheels / moving)

---

## "ACTIVE but no motion" -- EAC green ACTIVE but rack does not move

### Symptom

EAC status panel shows ACTIVE solidly. Last Error shows NONE. The
`Commanded` field changes when you move the slider, but the
`Measured` field stays at 0 (or stays at whatever it was when you
engaged).

### Step 1: Confirm 0x488 is actually being transmitted

The bus diagnostic panel does not show our own TX (only RX). To
confirm, run `can_sniffer.py` from a second laptop / another adapter
while v4.1 is running, and look for `0x488` at ~50 Hz with our
angle data. If you only have one adapter, look at the event log for
any `TX 0x488 failed:` line.

### Step 2: Confirm the rack has motor power

The patched rack still requires 12V on its power pin. If the rack
is on the bench and only the CAN harness is connected, the rack is
listening but cannot move. Confirm the power harness is plugged in.

### Step 3: Confirm wheels are free

If the wheels are on the ground at standstill, the rack will load
up but not move (it's pushing against the road). Jack up the front
of the car or disconnect the tie rods.

### Step 4: Are we exceeding the standstill ceiling?

With 30 MPH MODE OFF, the rack rejects commanded angles above ~60
degrees at 0 km/h with HIGH_ANGLE_REQ. Either reduce the target or
click 30 MPH MODE ON.

### What to send Claude

- Session CSV
- Confirmation of: 12V on rack, wheels free, target inside envelope

---

## "unexpected disengage" -- E-STOP fires during a run

### Symptom

Mid-run, the GUI flashes red, the header shows `E-STOP: <reason>`,
and the rack disengages on its own.

### Read the reason

The reason is in the header bar AND in the event log as
`E-STOP: <reason>`. Possible reasons:

| Reason                              | Meaning                                            | Action                                                                                               |
|-------------------------------------|----------------------------------------------------|------------------------------------------------------------------------------------------------------|
| `rack FAULT, EAC_ERROR=<x>`         | Rack moved itself into FAULT state                 | Look at the error code -- same table as "stuck in INHIBITED" above                                   |
| `no 0x370 for <ms> ms`              | Rack stopped responding for >500 ms                | Bus glitch, loose connector, or rack lost power. Reseat connectors and reconnect.                    |
| `angle divergence <deg> deg`        | Rack lagged commanded angle by >30 degrees         | Rack overloaded or you commanded too aggressively. Lower target or wait for catch-up.                |
| `bus error count <n>`               | More than 50 CAN error frames                      | Bad termination, wrong baud, or H/L swap intermittent                                                |
| `loop overrun <ms> ms`              | Worker thread missed its 50 Hz tick by >100 ms     | Laptop is starved. Close other apps. Plug into power, not battery.                                   |
| `TX 0x488 failed: ...`              | python-can refused to send                         | SYS TEC adapter dropped off USB or driver crashed. Reconnect.                                        |
| `RX exception: ...`                 | python-can blew up on receive                      | Same as above                                                                                        |
| `disconnect requested`              | You clicked DISCONNECT                             | Fine                                                                                                 |
| `window closed`                     | You closed the window                              | Fine                                                                                                 |
| `ESC key`, `Q key`, `button`        | You pressed an E-STOP                              | Fine                                                                                                 |

### What to send Claude

- The full event log line for the E-STOP plus the 30 lines before it
- The session CSV around the E-STOP timestamp

---

## Bus errors -- `bus_errors` count grows

### Symptom

The `Bus Errors` field in the status panel ticks upward. At >50 the
program E-STOPs.

### Diagnosis

CAN bus errors come from:

- **Wrong bitrate**: every device on a CAN bus must agree on the
  bitrate. v4.1 hardcodes 500 kbps. Tesla chassis CAN is 500 kbps.
  If you see errors, you may be on a different sub-bus.
- **Termination**: CAN buses need exactly two 120-ohm terminations
  total, one at each end. The Tesla bus already has its own. If
  you have added a 120-ohm at the SYS TEC on top, you have
  over-termination. Remove the extra.
- **H/L swap**: occasional intermittent if a connector is
  marginally crimped.
- **Stub length**: the wire from the chassis CAN bus to the SYS
  TEC should be short (under ~30 cm).

---

## Logs -- finding and reading them

Logs land in `./logs/` next to the script. Each session gets two
files:

```
logs/session_20260507_152314.log
logs/session_20260507_152314.csv
```

### .log file

One line per event. Plain text:

```
[2026-05-07 15:23:14.812] CAN open: SYS TEC dev=0 ch=0 500 kbps
[2026-05-07 15:23:14.815] keepalive plan: GTW=False EPB=True 30MPH=False
[2026-05-07 15:23:15.022] EAC: INHIBITED -> AVAILABLE (err=NONE)
[2026-05-07 15:23:15.044] EAC: AVAILABLE -> ACTIVE (err=NONE)
[2026-05-07 15:23:18.450] target set to +15.0 deg
[2026-05-07 15:23:25.110] 30 MPH MODE: ON (faking 30 km/h at 200 Hz; rack will open at-speed envelope)
[2026-05-07 15:23:35.200] DISENGAGED
[2026-05-07 15:23:35.205] EAC: ACTIVE -> AVAILABLE (err=NONE)
```

### .csv file

One row per ~100 ms (every 10th `0x370` frame), plus extra rows on
state changes. Columns:

```
wall_time, monotonic, event, mode, engaged, estop,
target_deg, commanded_deg, measured_deg,
eac_status, eac_error, rx_count_0x370, bus_errors
```

`monotonic` is seconds since session start. The `event` column is
empty for periodic samples and tagged for transitions
(`engage`, `disengage`, `30mph_on`, `30mph_off`,
`eac_transition:X`, `estop:reason`).

Always send both files together when asking for help.

---

## When all else fails

1. Save the session log
2. Run `can_sniffer.py` for 60 seconds and screenshot it
3. Take a clear photo of the wiring at the SYS TEC tap
4. Note 30 MPH MODE state at the time of failure
5. Post the artifacts plus a one-paragraph description
6. Sit on your hands. Do not start changing things until the
   root cause is identified.
