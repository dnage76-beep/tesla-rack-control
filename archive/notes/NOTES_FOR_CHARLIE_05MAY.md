# Notes for Charlie -- 05 May 2026

Read your full 7752-line log and all 8 of your conclusions. Outstanding work, the structured logs and the periodic-flicker observation cracked this open. I think I know what's going on.

## Headline diagnosis

**The 3X is also broadcasting 0x488 on the bus.** We aren't the only source. The 3X is running BogGyver's openpilot fork, and BogGyver's `safety_tesla.h` synthesizes its own `DAS_steeringControl` frames as part of its DAS emulation code (it has `DAS_steeringControl_idx` as a counter, plus a `do_fake_DAS()` function).

When the 3X is connected:
- **We** send `0x488` with `controlType=1`, our angle, our counter
- **The 3X's panda** sends `0x488` with `controlType=0` (since openpilot isn't actually engaged for steering), some default angle, its own counter
- Both frames arrive at the rack with valid checksums
- The rack sees the same ID twice with conflicting controlType and angle
- It rapidly toggles: ACTIVE when our frame is most recent -> the angle suddenly "jumps" when the 3X's frame is most recent -> the differentiator inside the rack reads that as a rate spike -> fires HIGH_ANGLE_RATE_REQ -> drops to INHIBITED -> next ours arrives -> back to AVAILABLE -> repeat at the rate of the contention

**This explains every weird thing you saw:**

| Observation | Explained by |
|---|---|
| Flicker is periodic, time-based, not command-driven | Two streams of 0x488 racing on the bus |
| HIGH_ANGLE_RATE_REQ even with NO command sent | 3X is still sending 0x488 with angle = wherever, our LPF starts at 0, the rack sees jumps |
| 0x370 RX rate ~20 fps not 100 fps | CAN arbitration thrashing eats bandwidth when two TX'ers fight over the same ID |
| Unplug 3X -> stuck INHIBITED + OUT_OF_RANGE | 3X panda is also synthesizing the gateway / EPB messages the rack needs. Unplugging kills our gateway-alive heartbeat. Patch only bypasses the gating *content*; the rack still wants the messages present. |
| 3X boots -> stops being INHIBITED | The 3X's panda starts emitting GTW-emulation frames |
| Unplug rack -> bus goes silent | The rack was the only thing transmitting 0x370 |
| Theory A vs Theory B vs main: same flicker | Smoothing on our side can't beat a competing transmitter -- the rack reads the most recent frame regardless of how smooth ours was 20 ms ago |

So Theory A and Theory B were chasing the wrong cause. The smoothing was already fine. The rack is reacting to the OTHER stream of 0x488 hitting it.

## Quick way to confirm this is actually the issue

Run **can_sniffer.py only** -- no move.py, no GUI, no test program at all. With the 3X plugged in:

1. Watch the sniffer's table for ID `0x488`. Count its rate.

If 0x488 appears at ~50 Hz with NOTHING from our laptop sending: confirmed. The 3X is the source.

If 0x488 only appears when our program is running: my theory is wrong, look elsewhere.

You can also screenshot the sniffer's `0x488` line for evidence. If you see two competing counters (jumps backwards in counter values), that's a smoking gun.

## Three fixes, in order of effort

### Fix 1: Stop the 3X from sending 0x488 while we test

SSH into the 3X (you already have keys set up):
```
ssh comma@172.20.10.2
sudo systemctl stop comma
```
That kills openpilot. The panda will go quiet on 0x488 because there's nothing to feed it.

But: **it also kills the GTW emulation.** So you'd then need to handle that separately. This is the cleanest test of my theory but breaks the gateway side.

A safer variant -- BogGyver has a parameter to disable just the DAS emulation. SSH in and:
```
echo -n 0 > /data/params/d/TinklaUseTeslaRadar
echo -n 0 > /data/params/d/TinklaHasIcIntegration
```
or similar. There's likely a `enable_das_emulation = 0` config. I'll dig into the BogGyver config layer to find the exact param name -- want me to do that next?

### Fix 2: Just confirm and move on with the 3X's own steering control

The 3X already has steering control built in. Per BogGyver, you can connect a Tinkla Buddy (or similar) and use openpilot directly. Our `tesla_steering_test.py` is just a more controllable bench tool -- it isn't required for actual driving.

If the 3X's openpilot can drive the wheel without flicker, the problem is genuinely "two competing 0x488 sources" and the right move is to use one or the other, never both. For the eventual road system:
- **Production:** drive via the 3X (use openpilot or a tinkla-buddy-style integration)
- **Bench testing:** drive via our laptop tools, with the 3X **disconnected** from the bus but with its panda serving the gateway role somehow

### Fix 3 (Jordan's idea): Use the red panda instead

This is actually the most professional fix. The red panda flashed with comma's stock firmware does NOT broadcast 0x488 unless its host tells it to. If we put the red panda inline:

- Red panda physically replaces the 3X on the bus
- Red panda's stock firmware is passive on TX -- only forwards what we ask
- Our laptop talks to the red panda via USB instead of the SYS TEC
- We use comma's `panda` Python library (same pip install)
- Code is almost identical to current, just swap the can interface

The red panda comes with a flat OBD-C cable that goes into the 3X's slot. You can plug it in WITHOUT the 3X attached, with a small 5V USB power injector for the bus side.

**Trade-off:** we lose the 3X's gateway emulation. The rack might then complain about no GTW. We'd have to synthesize 0x101 and 0x214 ourselves (which we already have code for in IN_CAR_MODE=False).

## On your other 7 conclusions

**1. (centralized doc):** Yes. I'll send you a single `BENCH_TEST.md` next that you can write into directly. One file. You handwrite the section results. Done with multi-PDF chase.

**2. (flicker is independent of commands):** This was the key insight that pointed at "another transmitter is the cause." Spot on.

**3. (none of the branches fixed it):** Confirms cause is upstream of our smoother. Smoothing is fine; we're being overwritten by the 3X.

**4. (proof you ran the right branches):** Believed.

**5. (3X correlation):** This is the entire diagnosis. You had it.

**6. (think outside the box, hardware too):** Doing it. Software was a dead end on this one.

**7. (Jordan's red panda idea):** Better than I gave it credit for. See Fix 3.

**8. (X437 / TDC connection):** Good info. Doesn't change the diagnosis -- you're on the same chassis CAN segment as OBD-II pins 1/9, just a different physical tap. All 0x488 traffic from any source on chassis CAN reaches both your tap point and the rack equally.

## What I'd like you to do next session

Just one experiment, then we plan together based on what you find:

**Sniff alone with the 3X plugged in.** No laptop programs running except `can_sniffer.py`. Watch for `0x488` traffic. Tell me the rate and whether you see one or two distinct counter sequences. Take a screenshot. That's the entire test.

If 0x488 is ticking up while no laptop program is sending: theory confirmed, we plan the fix. If it's silent: my theory is wrong and I rethink.

After that one test, hold and we plan together rather than running another full validation cycle.

## Sources for this diagnosis

- `BogGyver/openpilot tesla_unity_releaseC3` `panda/board/safety/safety_tesla.h`: contains `do_fake_DAS()` function, `DAS_steeringControl_idx` counter, and the DAS emulation TX block
- The `enable_das_emulation = 1` flag visible in that same file
- gregjhogan README: confirms patched rack still reads 0x488 -- so two valid 0x488 sources do conflict, the rack does not arbitrate by sender

-- Derek
