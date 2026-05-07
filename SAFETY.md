# Safety

This program commands a real Tesla Model S electric power steering
rack. The rack applies real torque to a real steering shaft. Misuse
can damage the rack, strain a tie rod, dent a fender from the inside,
or cause uncommanded steering.

Read this document before running anything.

---

## Hard rules

1. **Front wheels off the ground.** Jack stands or tie rods
   disconnected. No exceptions for "I'll just try a small angle."
2. **No passengers in or near the car** during testing. Anything
   running this software counts as a development tool, not a
   driver-assist system.
3. **No driving on a public road.** Ever. The rack patch removes
   safety gates that exist for good reasons.
4. **Driver hands off the wheel during ENGAGE.** The rack reads
   driver torque and will refuse to engage with hands on. Forcing
   it leads to HANDS_ON faults and unpredictable behavior.
5. **30 MPH MODE on jacks only.** Faking vehicle speed while the
   wheels are on the ground (whether the car is moving or not) is
   dangerous. See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
   under "ESP contention" for the full reasoning.

---

## Defense in depth (what the program does)

`tesla_control.py` enforces multiple independent safety layers.
Removing any one of them is acceptable; bypassing all of them is not.

- **Hard angle clamp** at +/- 180 degrees in software. The rack
  rejects beyond ~60 at standstill on its own.
- **Rate limit** at 150 deg/s. Rack rejects above ~250 at any speed.
- **Low-pass filter** (150 ms tau) on the user input target so a
  rapidly moved slider does not become a step input to the rack.
- **RX timeout watchdog**: lose `0x370` for >500 ms, E-STOP fires.
- **Bus error watchdog**: >50 CAN errors, E-STOP fires.
- **Loop overrun watchdog**: 50 Hz TX loop late by >100 ms,
  E-STOP fires.
- **Optional divergence watchdog**: commanded vs measured angle
  >30 deg, E-STOP fires. Off by default until the measured-angle
  decode is calibrated on bench.
- **Four E-STOP paths**: red button, ESC key, Q key, window close.
  Any one of them flips controlType=0 within 20 ms.
- **Refusal to engage blind**: ENGAGE refuses if `0x370` has never
  been received, so we never command a rack we can't hear back from.
- **Refusal to enable 30 MPH MODE while engaged**: prevents the
  rack's torque envelope from jumping mid-steer.

---

## What you must do before live testing

1. Read [docs/GUIDE.md](docs/GUIDE.md) end to end.
2. Read [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) at least
   for the "EAC flicker" and "ESP contention" sections.
3. Confirm the rack has the gregjhogan firmware patch applied.
4. Confirm front wheels are off the ground.
5. Confirm no comma device is on the chassis CAN bus.
6. Run `can_sniffer.py` first as a passive check that you are tapped
   into the right bus and the rack is responding.

---

## What to do when something goes wrong

E-STOP first, debug second. The program's E-STOP paths are designed
so that any one of them stops the rack within one CAN frame. If the
program is not responding, pull the SYS TEC's USB cable.

After E-STOP, save the session log files in `./logs/` and look at
the troubleshooting guide before you try anything else.

---

## What this software is NOT

- It is not a driver-assist system.
- It is not openpilot.
- It is not a substitute for the comma stack if you want autonomy.
- It is not validated for road use.

It is a bench-and-jacks test tool for commanding a patched EPAS rack
during development of an RC steering proof-of-concept. Treat it as
such.

---

## Disclaimer

By running this software you accept all risk of damage to your
vehicle, your rack, your fender, your tie rods, and yourself. The
authors provide no warranty (see [LICENSE](LICENSE) for the legal
text). If you are not comfortable with the safety rules above, stop
and find someone who is.
