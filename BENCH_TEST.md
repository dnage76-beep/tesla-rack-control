# Bench Test -- Single-Document Edition

> Write your results directly in this file. One document, one place.
> Per Charlie's request 05 May 2026: stop chasing across many PDFs.

## Session header

| Field | Value |
|---|---|
| Date / time | |
| Branch (main / theory-A / theory-B) | |
| Operator | |
| Spotter | |
| Wheels off ground? | |
| 3X plugged in? | |

---

## Test 0 -- THE NEW SINGLE TEST (do this first)

Goal: confirm or rule out that the 3X is broadcasting 0x488 alongside us.

**Setup:**
1. Tesla in Drive Ready
2. SYS TEC connected at X437/TDC
3. **3X plugged in** (whatever your normal setup is)
4. **No other program running.** Close move.py, GUI, steer.py.

**Run:**
```
python can_sniffer.py
```
Press Enter, let it run for 30 seconds.

**Observe the row for ID `0x488`:**

| Question | Answer |
|---|---|
| Is `0x488` showing up in the sniffer's table at all? | |
| What rate (Hz) does it report? | |
| What's in the data column? does it look frozen or changing? | |
| Counter value (lower nibble of byte 2): cycling 0..15? | |

**Then unplug the 3X** (no other change), wait 5 sec, observe again:

| Question | Answer |
|---|---|
| Does `0x488` still show in the sniffer? | |
| If yes, at what rate? | |
| If no, how long until it disappears? | |

**Verdict:**
- 3X plugged in and 0x488 ticking with no laptop program running: **theory confirmed, 3X is a competing transmitter.** Stop here, text Derek the screenshots.
- 3X plugged in and no 0x488 traffic: theory wrong, continue to Test 1.
- Either way, screenshot the sniffer.

---

## Test 1 -- Engage zero (only if Test 0 ruled out the 3X)

```
python tesla_steering_test.py
```
Click CONNECT, wait for green EPAS LINK OK, click ENGAGE at 0 deg.

| Result | |
|---|---|
| Did EAC reach ACTIVE? | |
| For how long before flickering? (sec) | |
| Most common error in event log | |
| Bus errors during 30 sec hold | |

---

## Test 2 -- Small angle ramps (only if Test 1 stayed mostly ACTIVE)

| Command | Reached angle? | Flicker pattern | Errors |
|---|---|---|---|
| 0 -> +5 | | | |
| +5 -> 0 | | | |
| 0 -> -5 | | | |
| -5 -> 0 | | | |

---

## Test 3 -- Big angle ramps (only if Test 2 mostly worked)

| Command | Reached angle? | Flicker pattern | Errors |
|---|---|---|---|
| 0 -> +30 | | | |
| +30 -> 0 | | | |
| 0 -> -30 | | | |
| -30 -> 0 | | | |

---

## Test 4 -- E-STOP test (always do this last)

Set slider to +20, ENGAGE, then mid-motion press ESC.

| Result | |
|---|---|
| Did wheel stop within 200 ms? | |
| Status read "E-STOP: ESC key"? | |
| Could you reconnect without restarting Python? | |

---

## Notes / observations during session

(write freely here)

---

## Open questions for Derek

(write here)

---

## Logs

Paste GUI event log lines here for each failure case. Truncate to ~20 lines per
incident to keep the file readable. Use timestamps to correlate.

```
[paste here]
```
