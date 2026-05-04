# Notes for Charlie -- 04 May 2026

Hey Charlie, thanks for the field test notes and screenshots. Reading back through your test log gave me everything I needed.

## What I fixed on `main`

Already pushed. You can pull and these are live.

**1. E-STOP cannot clear bug.** You called this out and you were right -- it was real. When you click DISCONNECT, the code sets `ctrl.estop = True` to stop the worker. But the flag never got reset on the next CONNECT, so ENGAGE refused with "clear E-STOP first". Now CONNECT explicitly clears `estop`, `engaged`, `bus_errors`, and `rx_count` before spawning a new worker. Reconnect should now work without restarting Python.

**2. EAC transition logging.** You wanted to see Last Error in the log. Now every time `eacStatus` changes, the GUI logs the transition with the previous and new state plus the current error code. Same for any non-zero error code change. You should see lines like:

```
[23:48:01] EAC: ACTIVE -> AVAILABLE (err=HIGH_ANGLE_RATE_REQ)
[23:48:01] err -> HIGH_ANGLE_RATE_REQ
[23:48:02] EAC: AVAILABLE -> ACTIVE (err=NONE)
```

That should give you a real-time picture of the flicker pattern without needing screenshots.

## The HIGH_ANGLE_RATE_REQ + flicker problem

Your screenshots showed the rack throwing `HIGH_ANGLE_RATE_REQ` repeatedly even when motion looked smooth. I have two competing theories about why and **I built two branches so we can A/B test them.**

Don't merge either to main. Run them as branches:

```
git fetch origin
git checkout theory-A-conservative-rate
# test
git checkout theory-B-pure-filter
# test
git checkout main   # back to current
```

### Theory A: `theory-A-conservative-rate`

**Hypothesis:** the rack scales its rate-of-change tolerance by speed. At 0 km/h it expects very slow angle changes. Our 50°/sec rate limit is too aggressive for standstill, so the rack throws HIGH_ANGLE_RATE_REQ.

**Changes:**
- `MAX_RATE_DEG_PER_SEC`: 50 -> 20
- `TARGET_FILTER_TAU_S`: 0.15 -> 0.30

**Trade-off:** big-angle commands (0 -> 30°) take ~1.5 sec instead of ~0.6 sec. Slower but should keep the rack happy.

**What to watch for if it works:** HIGH_ANGLE_RATE_REQ disappears, rack stays in ACTIVE more reliably. Motion is slower but consistent.

### Theory B: `theory-B-pure-filter`

**Different hypothesis:** the two-stage smoother (LPF then rate-limit) creates a velocity discontinuity. When the gap is bigger than `max_delta`, output velocity is constant; when the gap shrinks below `max_delta`, velocity instantly drops to zero. That step in velocity is an acceleration impulse. The rack differentiates angle to check rate-of-change, which makes that impulse visible as a brief rate spike.

**Changes:**
- Removed the rate limiter entirely
- Commanded angle = LPF output directly
- `TARGET_FILTER_TAU_S`: 0.15 -> 0.40

**Trade-off:** motion has organic ease-in/ease-out (exponential approach) instead of constant-velocity sweep. Looks more like real human steering. Peak velocity for a 30° step is `30 / 0.40 = 75 deg/s` -- still well under the rack's hardware limit but might be enough headroom over the standstill threshold.

**What to watch for if it works:** HIGH_ANGLE_RATE_REQ disappears AND motion has natural ease-in/ease-out. Looks "alive" instead of "robotic".

**Safety:** the `MAX_RATE_DEG_PER_SEC` is still defined and used as an OUTER bound. If the LPF output's actual velocity ever exceeds 75 deg/s (50% headroom over the 50 cap), the loop E-STOPs. Belt and suspenders.

## How to A/B test

For both branches, run the same sequence and write down which one performs better:

1. Connect, engage at 0 deg
2. Slide to +5, watch event log for any `EAC` or `err ->` lines
3. Slide back to 0
4. Slide to +30, again watch the log
5. Slide back to 0

Note for each branch:
- How often did EAC flicker? Steady ACTIVE, occasional flicker, or constant flicker?
- What error codes appeared in the log? HIGH_ANGLE_RATE_REQ? HIGH_ANGLE_REQ? Other?
- Did the wheel motion feel smoother, the same, or worse than current main?

If neither works perfectly, I have a Theory C in my back pocket that I haven't built yet -- it'd combine both ideas plus add a feedback term that watches measured-vs-commanded divergence and slows down the LPF when the rack is struggling. Save it for if A and B both flop.

## Other things I noticed in your screenshots

**Photo 4** (00:25, +90° test) showed `HIGH_ANGLE_REQ` (not `HIGH_ANGLE_RATE_REQ`). That's a different error -- the rack's standstill angle limit, not its rate limit. Tesla scales the maximum allowed angle by speed too. At 0 km/h the rack probably caps at something like ±60°, not ±90°. **Recommendation:** keep test angles to ±60° max while at standstill. The hard ±90° clamp in our code is fine, you just don't want to drive it that high.

**Photo 1** (23:37, OUT_OF_RANGE at -10°) is weird. -10° should not be out of range. I think what happened is the rack was already in a fault state from the previous attempt and the error code was stale. Once you rebooted everything (per your test notes), it cleared. If you see OUT_OF_RANGE again at any small angle, screenshot it and we'll dig deeper.

## Action items

1. Pull main, retest: confirm E-STOP clears properly now and the event log shows EAC transitions
2. A/B test theory-A vs theory-B against the same script
3. Tell me which one (if any) made HIGH_ANGLE_RATE_REQ go away
4. Stay below ±60° at standstill for now

You're doing great work. The rack moving smoothly from 5 to 10 deg consistently is a real win -- means the protocol is solid, we just need to tune the smoother. We'll get the flicker handled.

-- Derek
