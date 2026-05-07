# Operating Guide -- `tesla_control_v4_1.py`

This is the operating guide for the current program. For the CAN
protocol reference, see `PROTOCOL.md`. For symptom-driven debugging,
see `TROUBLESHOOTING.md`.

Headline of v4.1: **no comma 3X required**, plus a runtime **30 MPH
MODE toggle** that opens the rack's at-speed envelope (more angle
travel, more rate, more torque) when you flip it on.

---

## What you need

### Hardware

- 2013 Tesla Model S, post-May-31 build, pre-AP. EPAS rack already
  patched with gregjhogan/tesla-pre-ap-epas-patch.
- SYS TEC sysWORXX USB-CANmodul1 (model 3204001).
- A laptop running Windows 10 or newer.
- The custom OBD-to-X119 (or X437/TDC) harness that taps chassis CAN.

### Software

```
pip install python-can
```

SYS TEC USB-CAN driver from
https://www.systec-electronic.com/en/services-support/downloads
This installs `USBCAN32.dll`, which python-can's `systec` backend
loads automatically.

### What you do NOT need

No comma device of any kind: not a 3X, not a 3, not a red panda, not
a 2. The 3X was historically in the loop because BogGyver's openpilot
fork shipped a panda firmware that synthesized the rack keepalives
for free. v4.1 does that ourselves, surgically, from the SYS TEC
adapter.

If a comma device is plugged into the chassis CAN bus when you run
v4.1, it will fight you for the `0x488` arbitration ID and you will
see the EAC flicker bug from the May 2026 field tests. **Pull the
comma device off the bus before running v4.1.**

---

## What v4.1 sends and listens for

### TX from the laptop

| ID    | Name                 | Rate    | When                                |
|-------|----------------------|---------|-------------------------------------|
| 0x488 | DAS_steeringControl  | 50 Hz   | always                              |
| 0x214 | EPB_epasControl      | 10 Hz   | always (default)                    |
| 0x101 | GTW_epasControl      | 20 Hz   | only if `SYNTHESIZE_GTW = True`     |
| 0x155 | ESP_B fake speed     | 200 Hz  | only when **30 MPH MODE** is ON     |

The defaults are tuned for **rack in the car, real Tesla GTW and ESP
alive on the bus**. In that configuration, only `0x488` and `0x214`
come from us at boot. The 30 MPH MODE toggle adds `0x155` when the
user opts in.

### RX

| ID    | Name           | What we do                                      |
|-------|----------------|-------------------------------------------------|
| 0x370 | EPAS_sysStatus | Decode EAC state, error code, measured angle    |
| (any) | other          | Count for the bus diagnostic panel              |

---

## First-time setup

### Step 1: Confirm the patched rack is in place

If you are not 100% certain the rack has been patched with
gregjhogan/tesla-pre-ap-epas-patch, **stop and confirm with Jordan**.
v4.1 assumes a patched rack.

### Step 2: Wire up

Plug the SYS TEC into:

- **In car**: the X437 / TDC connector under the center screen, OR
  the OBD-II port (pins 1 and 9 reach the same chassis CAN bus).
- **Bench**: the EPAS X119 connector via the custom adapter harness
  Jordan built.

### Step 3: Disconnect any comma device

Physically unplug any comma device from the chassis CAN bus. It
does not matter if the device is powered, only that it is not on
the bus.

### Step 4: Front wheels off the ground

Jack up the front of the car or disconnect the tie rods. The rack
can apply real force at standstill. With **30 MPH MODE** ON the rack
applies even more force. Skipping this step is the fastest way to
dent the inside of a fender or strain a tie rod boot.

### Step 5: Run the program

```
python tesla_control_v4_1.py
```

A 1080x860 window opens with status, mode, diagnostic, and keepalive
panels.

---

## Operating procedure

### 1. CONNECT

Click the blue **CONNECT** button. Expected:

- Header light goes from `DISCONNECTED` (red) to `WAITING FOR
  0x370...` (yellow) to `EPAS LINK OK` (green) within ~2 seconds.
- The **Bus Diagnostic** panel populates. You should see:
  - `0x370` rate near 100 Hz (rack to us)
  - `0x101` rate near 10 Hz (real car GTW; absent on the bench)
  - `0x108` rate near 100 Hz (drive inverter; absent on the bench)
  - `0x155` rate near 50 Hz (real car ESP; absent on the bench)
- The row for `0x488` should show **0.0 Hz**. If it shows above 0.1
  Hz, **stop**. Some other device is also transmitting `0x488`.
  Find it and remove it before continuing.

### 2. Pick a mode

Default is **SLIDER**. Click **KEYBOARD** to switch.

- **SLIDER mode** -- precise commanded-angle entry. Drag the slider,
  type and SET, or click CENTER (0). Best for repeatable angle-step
  tests.
- **KEYBOARD mode** -- fluid driving. Hold LEFT or RIGHT arrow to
  steer continuously at 90 deg/s. SPACE snaps target to 0. The
  wheel canvas mirrors the commanded angle.

You can switch modes at any time. Engagement state is preserved
across mode switches.

### 3. ENGAGE

Click the green **ENGAGE** button.

Expected:

- Event log shows `ENGAGED at <angle> deg`.
- EAC Status panel transitions from `INHIBITED` to `AVAILABLE` to
  `ACTIVE` within a few hundred milliseconds.
- The rack does not move yet because commanded equals measured.

If EAC bounces between INHIBITED, AVAILABLE, and ACTIVE many times
per second without ever reaching ACTIVE, see
`TROUBLESHOOTING.md` under "EAC flicker".

### 4. (Optional) 30 MPH MODE

By default the rack is in its standstill envelope: ~+/- 60 degrees,
~250 deg/s rate ceiling, modest torque. Plenty for tabletop and
slow-speed tests.

To unlock the at-speed envelope (full angle travel, higher rate
ceiling, more torque output), click **30 MPH MODE: OFF**. The button
turns orange and reads **30 MPH MODE: ON**, the keepalive panel
shows `0x155 ESP_B fake speed ON`, and the worker starts sending
`0x155` at 200 Hz claiming 30 km/h. The rack reads this as a moving
car and opens its envelope.

Rules:

- The button refuses to enable while you are engaged. Disengage
  first. (Reason: the rack's torque output jumps when its speed
  envelope opens. You do not want that mid-steer.)
- The button can be flipped OFF at any time. Doing so while engaged
  is allowed but the rack will snap back to standstill envelope and
  may briefly flicker EAC.
- Watch the bus diagnostic panel after enabling. The `0x155` row
  should show >0 frames/sec from us, but no second source. If the
  row turns RED, the real Tesla ESP is also transmitting (the
  contention case). See `TROUBLESHOOTING.md` under "ESP contention".

### 5. Steer

Move the slider, type an angle, or hold an arrow key. The rack
ramps to the commanded angle at up to 150 deg/s, with a 150 ms LPF
on the user target.

The software hard-clamps at +/- 180 degrees. With 30 MPH MODE OFF,
the rack itself rejects anything beyond ~60 degrees -- you'll see
HIGH_ANGLE_REQ in the error field. With 30 MPH MODE ON, the full
180 is available.

### 6. DISENGAGE

Click the orange **DISENGAGE** button. The rack stays at its current
position; only the controlType bit drops to 0. EAC goes back to
`AVAILABLE`. Re-ENGAGE at any time.

### 7. SAVE LOG and finish

Click **SAVE LOG** to flush the in-progress log to disk without
disconnecting (useful for snapshotting mid-session). Or just
**DISCONNECT** or close the window. The session log files are
finalized automatically.

Logs land in `./logs/` next to the script:

- `session_YYYYMMDD_HHMMSS.log` -- one line per event, human-readable
- `session_YYYYMMDD_HHMMSS.csv` -- one row per ~100 ms with cmd
  angle, measured angle, EAC state, error code, etc. Open in Excel,
  pandas, or hand it to Claude.

---

## E-STOP

Four ways to trigger an E-STOP:

- Click the big red **E - STOP** button
- Press **ESC**
- Press **Q**
- Close the window

E-STOP does:

1. Sets controlType=0 immediately. Rack receives a disengage on the
   next 50 Hz tick (worst case 20 ms).
2. Holds the last commanded angle so an accidental re-engage does
   not snap to 0.
3. Logs the trigger reason.

To clear E-STOP: click DISCONNECT then CONNECT. Fresh worker
thread, fresh state, fresh session log file.

---

## What the bus diagnostic panel is telling you

| Row     | Healthy in-car (default flags)            | Healthy on bench (with all-synth flags) | Bad sign                                     |
|---------|-------------------------------------------|------------------------------------------|----------------------------------------------|
| 0x101   | ~10 Hz (real GTW)                         | ~20 Hz (we send)                         | 0 Hz in car -> GTW dead                      |
| 0x108   | ~100 Hz (real DI)                         | 0 Hz                                     | irrelevant on bench                          |
| 0x129   | ~100 Hz (SAS)                             | 0 Hz                                     | --                                           |
| 0x155   | depends on 30 MPH MODE (see below)        | 0 Hz off / ~50 Hz our leak on (see TS)   | RED row -> contention                        |
| 0x214   | ~10 Hz (we send)                          | ~10 Hz (we send)                         | 0 Hz -> we are not transmitting              |
| 0x370   | ~100 Hz (rack)                            | ~100 Hz (rack)                           | 0 Hz -> rack not powered                     |
| **0x488**| **0.0 Hz**                              | **0.0 Hz**                               | **>0 -> SECOND TRANSMITTER**                 |

About 0x155 in car:

- **30 MPH MODE OFF**: the row shows the real Tesla ESP at ~50 Hz.
  This is normal. We are not transmitting.
- **30 MPH MODE ON, no real ESP**: the row shows 0 Hz (we don't
  receive our own frames; the diagnostic only counts RX traffic).
- **30 MPH MODE ON, real ESP present**: the row shows ~10-50 Hz of
  RX traffic and turns RED. This is the contention case.

The 0x488 row going red is the single most important thing the panel
can tell you. We are the only allowed transmitter on that ID.

---

## Configuration cheat sheet

Edit the constants at the top of `tesla_control_v4_1.py`. Common
overrides:

### Rack on the bench (no real car around)

```python
SYNTHESIZE_GTW   = True    # we have to provide 0x101
SYNTHESIZE_EPB   = True    # always on
# 30 MPH MODE: still toggled in the GUI, no constant to change
```

### Rack in the car, real GTW alive (default)

```python
SYNTHESIZE_GTW   = False   # car GTW is doing it
SYNTHESIZE_EPB   = True    # car EPB does NOT do this on pre-AP
```

### Tighter envelope (back to v4 defaults)

```python
HARD_ANGLE_LIMIT_DEG       = 60.0
MAX_RATE_DEG_PER_SEC       = 50.0
KEYBOARD_STEER_RATE_DEG_PER_SEC = 30.0
```

### Tighter divergence trip

```python
DIVERGENCE_TRIP_ENABLED = True
ANGLE_DIVERGENCE_LIMIT_DEG = 15.0
```

---

## What to send Claude when something goes wrong

1. The session `.log` file from `./logs/`
2. The session `.csv` file from `./logs/`
3. A screenshot of the bus diagnostic panel during the failure
4. One sentence: what mode you were in, whether 30 MPH MODE was
   ON or OFF, and what you were trying to do when it failed

That's enough context for a remote diagnosis without a follow-up
round. The CSV in particular lets us replay the EAC state machine
offline.
