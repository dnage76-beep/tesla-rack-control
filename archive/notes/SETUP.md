# Tesla Rack Test -- Setup (Windows)

## 1. Install the SYS TEC driver

The USB-CANmodul1 (model 3204001) needs SYS TEC's Windows driver, which provides `USBCAN32.dll`.

1. Go to https://www.systec-electronic.com/en/services-support/downloads
2. Search for "USB-CANmodul1" or "USBCAN32"
3. Download "sysWORXX USB-CAN Driver" for Windows (current version, x64)
4. Run the installer as Administrator
5. Plug in the USB-CANmodul. Device Manager should show it under "USB-CAN Devices"
6. Reboot if Windows asks

To verify the driver is alive: open SYS TEC's "USB-CAN Coupling Tool" (installed alongside the driver) and confirm it sees the device. You don't have to use this tool, just confirm the box enumerates.

## 2. Install Python and python-can

Python 3.10 or newer:

```
py -m pip install --upgrade pip
py -m pip install python-can
```

python-can has a built-in `systec` interface that calls into `USBCAN32.dll`. No extra packages needed.

## 3. Wire up the CAN bus

Tesla 2013 Model S MCU connector pins 4 and 11 (verify with a sniff first):
- Pin 4 -> CAN High -> SYS TEC DB9 pin 7
- Pin 11 -> CAN Low -> SYS TEC DB9 pin 2
- Common ground recommended -> SYS TEC DB9 pin 3 to chassis ground

If your bus segment is not already terminated, add a 120 ohm resistor between CAN H and CAN L at the SYS TEC end. The Tesla bus segment between MCU and rack should already have proper termination at both ends, so adding a third 120 ohm in parallel is wrong. When in doubt, measure with a multimeter: a properly terminated bus reads ~60 ohms between H and L with no power.

## 4. First run -- passive listen

Before letting the script send anything, just confirm you can hear the bus:

1. Put the car in "Accessory" or fully on (key fob in, brake pressed for "Drive Ready" but parking brake set, or just power-on diagnostic mode)
2. Run:

```
py tesla_steering_test.py
```

3. Click CONNECT
4. Do NOT click ENGAGE yet
5. Within 2 seconds the status panel should show "EPAS LINK OK" and the RX count should start climbing
6. The "Measured Angle" should reflect actual steering wheel position. Turn the wheel by hand and confirm it tracks.

If you see nothing on RX:
- Wrong bus (try other pin pairs, sniff with the SYS TEC tool to confirm 500 kbps and check for 0x370 frames)
- Wrong baud (rare on Tesla but possible)
- Reversed CAN H/L (script will likely show bus errors)
- No power to the bus (rack ECU not awake)

## 5. First active test

Front of car on jack stands, wheels free OR tie rods disconnected. Engine off, ignition on (Drive Ready not required and probably shouldn't be).

1. Connected, EPAS LINK OK, RX count climbing.
2. Click ENGAGE. Watch "EAC Status":
   - INHIBITED -> rack hears you but isn't ready (handshake or speed gate failing)
   - AVAILABLE -> rack ready, engaging
   - ACTIVE -> rack is following commands. You can now move the slider.
   - FAULT -> read the "Last Error" field. Common bench faults:
     - MIN_SPEED -> set BENCH_MODE = True at top of script and rerun
     - HANDS_ON -> someone is touching the wheel, let go
     - HIGH_ANGLE_RATE_REQ -> lower MAX_RATE_DEG_PER_SEC
3. Once ACTIVE, move the slider to +5 deg. Confirm the rack moves the right direction. Note: positive could be left or right depending on rack orientation; identify the sign on first run before pushing further.
4. Try +/- 30 deg.
5. E-STOP test: hit ESC. Rack should immediately stop and disengage.

## 6. If the rack faults with MIN_SPEED on the bench

Edit `tesla_steering_test.py`, set:

```python
BENCH_MODE = True
```

This injects a fake `0x155 ESP_B` at 50 Hz with `vehicleSpeed` set to 30 km/h. The encoding is best-effort; if your rack still rejects it, sniff the real ESP_B on a moving car and replicate exactly (counter, checksum, neighboring signals). I left a note at the build function to that effect.

## 7. Failsafes already in the script

All trigger immediate disengage and stop the 0x488 stream:

- **No 0x370 for 500 ms** -- bus dropped, abort
- **Rack reports FAULT** -- abort and print error code
- **Commanded vs measured angle differs > 15 deg** -- rack not tracking, abort
- **Loop overrun > 50 ms** -- timing problem, abort
- **CAN TX exception** -- driver/bus problem, abort
- **Bus error counter > 50** -- electrical issue, abort
- **ESC key, E-STOP button, or window close** -- user abort
- **Refuses to engage if no 0x370 has ever been received** -- blind operation blocked
- **Hard angle clamp at +/- 90 deg** -- typed values beyond are refused
- **Rate clamp at 50 deg/sec** -- ramps in to target, no instant snaps

To clear E-STOP: click DISCONNECT, then CONNECT again.

## Files

- `tesla_steering_test.py` -- the GUI app
- `SETUP.md` -- this file
