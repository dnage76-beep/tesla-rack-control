# RC Setup Guide  --  v5.0.0-rc1

How to set up the Spektrum DX8 + AR6200 + Arduino Nano + laptop
chain that drives `tesla_control_rc.py`.

> **Read [../SAFETY.md](../SAFETY.md) before doing any of this.**
> RC steering moves the rack at full software authority. Wheels off
> the ground, tie rods disconnected, or an empty private lot only.

---

## Hardware list

| Item | Purpose | Source |
|---|---|---|
| Spektrum DX8 transmitter (any gen) | Operator radio | already owned |
| Spektrum AR6200 receiver (SPMAR6200) | Receives radio, outputs 6 PWM channels | already owned |
| Arduino Nano (ATmega328P, 16 MHz) | PWM-to-USB bridge | any of the bench supply |
| 3x servo lead wires or jumper wires | Receiver to Nano | bench supply |
| Mini-USB cable for the Nano | Bridge to laptop | bench supply |
| SYS TEC USB-CANmodul1 + harness | Laptop to car CAN | unchanged from v4 |

The Nano runs on 5 V over USB. The AR6200 is happy on 5 V from the
Nano's regulated rail. Do NOT power the AR6200 from a separate battery
unless you also tie both grounds together.

---

## Step 1 -- Bind the AR6200 to the DX8

The AR6200 is a DSM2 aircraft receiver. The DX8 transmits DSMX with
DSM2 fallback, so it binds. Procedure from
[Spektrum AR6200 manual](https://www.spektrumrc.com/ProdInfo/Files/SPMAR6200.pdf):

1. Push the bind plug into the AR6200's BIND/DATA port.
2. Power the AR6200 (any servo port: GND-V+-signal lead from a battery
   or the Nano's 5 V rail will work; just GND + 5 V on any servo port).
3. The AR6200's LED flashes rapidly while in bind mode.
4. On the DX8, hold the trainer/bind switch while powering the radio
   on. The DX8 enters bind mode.
5. Within a few seconds the AR6200's LED goes solid -- bound.
6. Power-cycle the AR6200, remove the bind plug. The bind is now saved
   in the receiver's flash; future power-ups auto-link to the DX8.

If the LED stays flashing for >30 s, the DX8 isn't in bind mode or
the receiver isn't seeing it. Move them closer, check antenna, retry.

---

## Step 2 -- Wire the AR6200 to the Arduino Nano

The Nano firmware reads PWM on three pins (PORTD pins 2, 3, 4, all
PCINT-capable). Channel assignments are CHOSEN to put steering on the
right-stick X (aileron, channel 2 on the AR6200) and the gear + Aux1
switches on channels 5 and 6.

### Channel-to-pin map

| AR6200 port | DX8 control | Arduino pin | Purpose |
|---|---|---|---|
| 1 (THRO) | throttle stick (left, vertical) | unused | future throttle interceptor |
| 2 (AILE) | right stick, horizontal | D2 (PCINT18) | **STEERING ANGLE** |
| 3 (ELEV) | right stick, vertical | unused | reserved |
| 4 (RUDD) | left stick, horizontal | unused | reserved |
| 5 (GEAR) | gear toggle switch | D3 (PCINT19) | **P latch** (long press) |
| 6 (AUX1) | aux1 3-position switch | D4 (PCINT20) | **R / N / D** select |

### Wiring per channel

Each AR6200 channel port is a standard 3-pin servo header in JR
orientation:

```
AR6200 channel port (looking at the receiver)
+--------+
|        |  <- top edge
|   ()()  |    pin 1 (signal, white/orange) - innermost
|   ()()()|    pin 2 (positive, red)
|   ()()|     pin 3 (ground, black/brown)  - outermost
|        |
+--------+
```

Power and ground only need to be connected ONCE, on any single
channel. The Nano supplies them:

```
Channel 2 (AILE) signal (white)   -> Nano D2
Channel 2 (AILE) positive (red)   -> Nano 5V  (powers Rx)
Channel 2 (AILE) ground (black)   -> Nano GND
Channel 5 (GEAR) signal (white)   -> Nano D3
Channel 6 (AUX1) signal (white)   -> Nano D4
```

The other two channels (5 and 6) only need their signal wires;
they share power and ground through the AR6200's internal rails
once channel 2 is energized.

If you prefer separate power for cleanliness, tie all grounds
together (Nano GND + AR6200 GND + any external supply GND) and
power the AR6200 from any 4.8-9.6 V source.

---

## Step 3 -- Flash the Arduino Nano

```sh
cd arduino/tesla_rc_bridge
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 .
arduino-cli upload  --fqbn arduino:avr:nano:cpu=atmega328 -p <PORT> .
```

If your Nano has the "old bootloader" (most Chinese clones do):

```sh
arduino-cli upload --fqbn arduino:avr:nano:cpu=atmega328old -p <PORT> .
```

Find your port:

- Windows: Device Manager -> Ports (COM & LPT). Should be a "USB
  Serial Device (COMx)" or "CH340" entry. Note the COM number.
- macOS: `ls /dev/cu.usbserial-* /dev/cu.usbmodem*`
- Linux: `dmesg | tail -20` after plugging the Nano in. Usually
  `/dev/ttyUSB0` or `/dev/ttyACM0`.

Verify framing with `screen` or `python -m serial.tools.miniterm`:

```sh
python -m serial.tools.miniterm <PORT> 115200
```

You will see binary garbage -- that's normal. COBS-framed data isn't
ASCII. To verify the framing is healthy, run the Python program; it
parses and displays the values.

---

## Step 4 -- Verify channel values

With the AR6200 powered (and bound to DX8 that's also on), run the
Python program. The RC INPUT panel shows live values:

```
PORT   FRAMES  STEER us  RND us  P us   GEAR  ARMED  CRC/GAP
OPEN     342      1502    1500   1000    N     NO      0 / 0
```

Move the right stick left and right; STEER us should sweep ~1000
to ~2000. Flick the AUX1 3-pos switch; RND us should jump to ~1000
at one end, ~1500 in the middle, ~2000 at the other end. Toggle the
GEAR switch; P us should flip between ~1000 and ~2000.

If a value reads 0 or stays at 1500 with no response, that channel
isn't wired correctly. Confirm the white-wire-on-D2/D3/D4 assignment.

---

## Step 5 -- Arm the watchdog

The Python program will NOT command the rack until it sees the
aileron stick travel at least 50 us. Wiggle the right stick left
and right a couple times; the ARMED cell goes from `NO` (yellow)
to `YES` (green). This is the layer that prevents a stale value
left over from a power cycle from snapping the wheel on connect.

---

## Step 6 -- Launch the program

```sh
python tesla_control_rc.py --rc-port COM5
```

(use the actual port from Step 3.)

The GUI is identical to the v4.3.3 program plus the RC INPUT panel.
Click CONNECT to open CAN. Confirm the bus diagnostic panel shows
expected RX (0x370 ~100 Hz, 0x118 ~100 Hz if you're in-car).
Click ENGAGE.

From here on the rack follows the right stick. Aux1 changes between
R / N / D. Holding the gear switch in its high position for 200 ms
fires a P shift.

---

## Channel calibration (optional)

If your DX8 endpoints are trimmed away from the default 100% travel,
the steering may not reach the full +/- HARD_ANGLE_LIMIT_DEG. To
calibrate:

1. Move the right stick all the way left and read STEER us. Call it
   `RC_STEER_MIN_US`.
2. Center it and read. Call it `RC_STEER_CENTER_US`.
3. All the way right. Call it `RC_STEER_MAX_US`.
4. Edit `tesla_control_rc.py` and replace the three constants near
   the top of the file.

For the AUX1 switch you usually don't need to recalibrate -- the
hysteresis bands at 1250 and 1750 us cover any sane endpoint.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| RC port FAILED to open | Wrong port number, Arduino not plugged in, driver missing | Re-check Device Manager / dmesg. On Windows install CH340 driver if using a clone Nano. |
| STEER us stays at 0 | White wire not on D2, or AR6200 not bound | Re-bind, re-check wiring |
| STEER us frozen at 1500 with no response | Stick has no signal, but PWM still emitting | DX8 powered off, signal lost. Power DX8, re-arm |
| ARMED stays NO no matter what | Aileron wire on wrong pin, or stick at center the whole time | Move stick left AND right >50 us total |
| CRC counter climbing | USB cable noise, or Arduino flash corrupt | Re-flash, swap cable |
| GAP counter climbing | Arduino is restarting, or laptop USB hub is dropping packets | Plug Nano directly into laptop, not through a hub |
| RND switch wobbles between R and N | Switch is near a hysteresis edge | Adjust DX8 EPA on Aux1 to push endpoints further out |
| Shifts spam the log | RND switch picking up noise | Increase the hysteresis bands in `_rnd_pwm_to_gear` |

---

## Future work (NOT in v5.0.0-rc1)

- Pedal interceptor for throttle (see V5_PLAN.md from the longitudinal branch)
- Direct SRXL2 from a Spektrum AR637T (eliminates Arduino, one wire instead of three)
- Failsafe via panel-level signal-loss detection (currently the PWM held-last behavior means we cannot detect TX-off on the Arduino side)
- Bind-time stick check (verify aileron is centered before launching the program)
