# Tesla Rack Control v4 -- Setup and Operating Guide

This is the guide for `tesla_control_v4.py`. It replaces every prior
program in this repo for steering control. The headline change: **no
comma 3X is required**. All keepalive messages the rack needs come
directly from the SYS TEC adapter.

If something goes wrong, see `TROUBLESHOOTING_V4.md`.

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

- A comma 3X
- A comma 3
- A comma red panda
- A comma 2
- Any other comma device

The 3X was historically in the loop because BogGyver's openpilot fork
shipped with a panda firmware that synthesized the rack keepalives for
free. We now do that ourselves, surgically, from the SYS TEC adapter.

If a comma device is plugged into the chassis CAN bus when you run v4,
it will fight you for the `0x488` arbitration ID and you will see the
EAC flicker bug from the May 2026 field tests. **Pull the comma device
off the bus before running v4.**

---

## What v4 sends and listens for

### TX from the laptop

| ID    | Name                | Rate   | When                             |
|-------|---------------------|--------|----------------------------------|
| 0x488 | DAS_steeringControl | 50 Hz  | always                           |
| 0x214 | EPB_epasControl     | 10 Hz  | always (default)                 |
| 0x101 | GTW_epasControl     | 20 Hz  | only if `SYNTHESIZE_GTW = True`  |
| 0x155 | ESP_B fake speed    | 50 Hz  | only if `SYNTHESIZE_SPEED = True`|

The defaults are tuned for **rack in the car, real Tesla GTW and ESP
alive on the bus**. In that configuration, only `0x488` and `0x214`
come from us. Everything else is the real car.

### RX

| ID    | Name           | What we do                                      |
|-------|----------------|-------------------------------------------------|
| 0x370 | EPAS_sysStatus | Decode EAC state, error code, measured angle    |
| (any) | other          | Count for the bus diagnostic panel              |

---

## First-time setup

### Step 1: Confirm the patched rack is in place

If you are not 100% certain the rack has already been patched with
gregjhogan/tesla-pre-ap-epas-patch, **stop and confirm with Jordan**.
v4 assumes a patched rack. Sending `0x488` to an unpatched rack does
nothing and is harmless, but you would also be debugging a problem
that has nothing to do with this code.

### Step 2: Wire up

Plug the SYS TEC into:

- **In car**: the X437 / TDC connector under the center screen, OR
  the OBD-II port (pins 1 and 9 reach the same chassis CAN bus).
- **Bench**: the EPAS X119 connector via the custom adapter harness
  Jordan built.

### Step 3: Disconnect any comma device

Physically unplug the comma 3X (or any other panda) from the chassis
CAN bus. It does not matter if the device is powered, only that it is
not on the bus.

### Step 4: Front wheels off the ground

Jack up the front of the car or disconnect the tie rods. The rack can
apply real force at standstill. Skipping this step is the single
fastest way to dent the inside of your fender or strain a tie rod
boot.

### Step 5: Run the program

```
python tesla_control_v4.py
```

A 1080x820 window opens with status, mode, and diagnostic panels.

---

## Operating procedure

### 1. CONNECT

Click the blue **CONNECT** button. You should see:

- The header light goes from `DISCONNECTED` (red) to `WAITING FOR
  0x370...` (yellow) to `EPAS LINK OK` (green) within ~2 seconds.
- The **Bus Diagnostic** panel populates. You should see at minimum:
  - `0x370` rate near 100 Hz (rack to us)
  - `0x101` rate near 10 Hz (real car GTW; absent on the bench)
  - `0x108` rate near 100 Hz (drive inverter; absent on the bench)
  - `0x155` rate near 50 Hz (real car ESP; absent on the bench)
- The row for `0x488` should show **0.0 Hz** in the diagnostic. If it
  shows anything above 0.1 Hz, **stop**. Some other device is also
  transmitting `0x488`. Find it and remove it before continuing.

### 2. Pick a mode

The default is **SLIDER**. Click **KEYBOARD** to switch.

- **SLIDER mode** is for precise commanded-angle entry. Drag the
  slider, type a value and press SET, or press CENTER (0). The
  slider mode is what you want for repeatable angle-step tests.
- **KEYBOARD mode** is for fluid driving. Hold LEFT or RIGHT arrow
  to steer continuously at 30 deg/s. SPACE snaps the target back to
  0. The wheel canvas in this mode mirrors the commanded angle.

You can switch modes at any time. Engagement state is preserved
across mode switches.

### 3. ENGAGE

Click the green **ENGAGE** button.

What should happen:

- Event log shows `ENGAGED at <angle> deg`.
- EAC Status panel transitions from `INHIBITED` (gray) to `AVAILABLE`
  (yellow) within a few hundred milliseconds.
- Within another few hundred milliseconds, EAC transitions to
  `ACTIVE` (green).
- The rack does not move yet because commanded angle equals
  measured angle.

If EAC bounces between INHIBITED and AVAILABLE many times per
second without ever reaching ACTIVE, see `TROUBLESHOOTING_V4.md`
under "EAC flicker".

### 4. Steer

Move the slider, type an angle, or hold an arrow key. The rack ramps
to the commanded angle at 50 deg/s with a 150 ms LPF on the user
target. Both limits are configurable in the constants at the top of
`tesla_control_v4.py`.

### 5. DISENGAGE

Click the orange **DISENGAGE** button. The rack stays at its current
position; only the controlType bit drops to 0. EAC goes back to
`AVAILABLE`. You can ENGAGE again immediately.

### 6. SAVE LOG and finish

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

Four ways to trigger an E-STOP. Use any of them at any time:

- Click the big red **E - STOP** button
- Press **ESC** anywhere in the window
- Press **Q**
- Close the window

E-STOP does:

1. Sets controlType=0 immediately. Rack will receive a disengage
   command on the next 50 Hz tick (worst case 20 ms).
2. Holds the last commanded angle in software so an accidental
   re-engage does not snap to 0.
3. Logs the trigger reason to the event log and the session .log file.

To clear E-STOP:

- Click DISCONNECT then CONNECT. This re-creates a fresh worker
  thread with cleared state. You will start a new session log file.

This is intentional. There is no "clear E-STOP and continue" because
E-STOP only fires when something genuinely went wrong, and continuing
without a fresh look at the bus state is dangerous.

---

## What the bus diagnostic panel is telling you

| Row     | Healthy in-car        | Healthy on bench (with self-synth) | Bad sign                        |
|---------|-----------------------|------------------------------------|---------------------------------|
| 0x101   | ~10 Hz (real GTW)     | ~20 Hz (we send)                   | 0 Hz in car -> GTW dead         |
| 0x108   | ~100 Hz (real DI)     | 0 Hz                               | irrelevant on bench             |
| 0x129   | ~100 Hz (SAS)         | 0 Hz                               | --                              |
| 0x155   | ~50 Hz (real ESP)     | ~50 Hz (we send)                   | 0 Hz in car -> ESP not on bus   |
| 0x214   | ~10 Hz (we send)      | ~10 Hz (we send)                   | 0 Hz -> we are not transmitting |
| 0x370   | ~100 Hz (rack)        | ~100 Hz (rack)                     | 0 Hz -> rack not powered        |
| **0x488**| **0.0 Hz (RX)**     | **0.0 Hz (RX)**                    | **>0 -> SECOND TRANSMITTER**    |

The 0x488 row going red is the single most important thing the panel
can tell you. We are the only allowed transmitter on that ID. If
something else shows up, it WILL cause the EAC flicker.

---

## Configuration cheat sheet

Edit the constants at the top of `tesla_control_v4.py`. Common
overrides:

### Rack on the bench (no real car around)

```python
SYNTHESIZE_GTW   = True    # we have to provide 0x101
SYNTHESIZE_EPB   = True    # always on
SYNTHESIZE_SPEED = True    # provide fake 0x155
```

### Rack in the car, real GTW alive (default)

```python
SYNTHESIZE_GTW   = False   # car GTW is doing it
SYNTHESIZE_EPB   = True    # car EPB does NOT do this on pre-AP
SYNTHESIZE_SPEED = False   # car ESP is doing it
```

### Tighter safety envelope

```python
HARD_ANGLE_LIMIT_DEG    = 30.0   # smaller travel
MAX_RATE_DEG_PER_SEC    = 25.0   # slower ramp
DIVERGENCE_TRIP_ENABLED = True   # E-STOP if rack lags command by >15 deg
```

---

## What to send Claude when something goes wrong

1. The session `.log` file from `./logs/`
2. The session `.csv` file from `./logs/`
3. A screenshot of the bus diagnostic panel during the failure
4. One sentence: what mode you were in and what you were trying to do
   when it failed

That's enough context for a remote diagnosis without a follow-up
round. The CSV in particular is gold: it lets us replay the EAC state
machine offline.
