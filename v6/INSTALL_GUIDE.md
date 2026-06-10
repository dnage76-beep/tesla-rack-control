# v6 Install Guide — comma 3X setup for the pre-AP Model S

Step-by-step commissioning guide. Read
[V6_PLAN.md](V6_PLAN.md) first for the why; this is the how.

**Safety**: same rules as [SAFETY.md](../SAFETY.md). And the v6
golden rule: **the comma 3X and `tesla_control.py` are never on
chassis CAN at the same time** (Theory C, PROJECT_MEMORY.md §8).

Last updated: 2026-06-10.

---

## Step 0 — Pick the software (do this before touching the car)

Two candidate installer URLs. The custom-software URL is entered
on the comma setup screen; the pattern is
`installer.comma.ai/<github-owner>/<branch>`.

| Option | URL | AGNOS it flashes | Status |
|---|---|---|---|
| xnor pre-AP build | **ask the [xnor Discord](https://discord.xnor.shop/)** — the public repo has no `tesla-unity` branch yet; do not guess | 12.8 (xnor-c3) | Actively maintained, advertises 3X + pre-AP |
| BogGyver fallback | `installer.comma.ai/BogGyver/tesla_unity_releaseC3` | 9.1 (pinned in the branch) | Frozen Jan 2024; 3X compatibility **unverified** |

> **Do not use `installer.comma.ai/commaai/agnos8`.** That branch
> does not exist on commaai/openpilot (verified 2026-06-10), and
> installing stock comma software wouldn't support this car anyway.
> You also never need a separate AGNOS install: every fork pins its
> AGNOS version in `launch_env.sh` and flashes it automatically on
> first boot of the installer.

## Step 1 — Factory-reset the comma 3X

1. Power the 3X from a USB-C wall supply (bench, not car).
2. Factory reset: power on while holding the touchscreen
   (or Settings → Software → Uninstall if it still boots an old
   install). Follow comma's on-screen reset flow.
3. Walk the setup wizard: language → Wi-Fi (join the shop/home
   network — the installer download and AGNOS flash need internet).

## Step 2 — Install the fork

1. At "Choose Software", pick **Custom Software**.
2. Enter the installer URL chosen in Step 0. Double-check
   spelling — a typo gives a generic "installation failed".
3. Let it download, flash AGNOS (one or more reboots, progress
   bar; can take 15–30 min on the AGNOS step), and boot to the
   fork's UI.
4. Confirm in Settings that the fork's Tesla/preAP options screen
   exists. On tesla_unity this is the menu Jordan used to flash
   the EPAS patch. **The rack is already patched — do not run the
   EPAS flash again.** The screen should report the patched state;
   if it instead demands a flash, stop and note it (V6_PLAN.md
   open question 4).
5. If the BogGyver branch fails to boot or bootloops on the 3X,
   that answers open question 2 — factory reset and wait on the
   xnor URL. Nothing on the car has changed.

## Step 3 — Harness

1. **Check the OBD2 port** (driver footwell area): are pins 1 and
   9 populated? Photograph it for the log.
2. Pins present → use the
   [xnor preAP OBD-C kit](https://xnor.shop/products/model-s-preap-kit):
   adapter into OBD2 port, OBD-C cable up the A-pillar to the 3X
   mount on the windshield.
3. Pins absent → chassis CAN must come from the diagnostic
   connector under the center screen (X437/TDC — the same place
   the laptop taps). Tinkla's retrofit harness did exactly this;
   we can also build the equivalent since we know the pinout from
   v4 work.
4. Mount the 3X high-center on the windshield, camera unobstructed,
   per comma's standard mount instructions.

**Before plugging in**: confirm the SYS TEC laptop adapter is
physically disconnected from the bus. One transmitter at a time.

## Step 4 — First power-on in the car (passive)

1. Plug the harness in. The 3X should power from the port and boot.
2. Car in P, ignition on. Watch the fork UI: it should detect CAN
   traffic and identify (or let you manually select) the pre-AP
   Model S.
3. Sanity-check live values against reality: speed = 0, steering
   angle tracks hand-turns of the wheel.
4. Drive a normal route **without engaging**. Afterwards check:
   no new DTCs, no EAC errors, route recorded on comma connect /
   fork equivalent.

If the rack throws EAC flicker or the cluster complains during
passive driving, pull the harness and capture a log — that's a
bus-contention smell and needs diagnosis before going further.

## Step 5 — First engage

1. Open, straight road; >18 mph (pre-AP engagement floor —
   vision-based ACC only, no radar).
2. Engage via cruise stalk per the fork's docs. Hands on wheel.
3. Verify: smooth lateral hold; instant disengage on steering
   override; instant disengage on brake.
4. Short sessions, build up. Log everything to
   `field_testing/sessions/` with the same note discipline as the
   v4 work.

## Known limits on this car (don't chase these as bugs)

- **No ACC below ~18 mph** without a pedal interceptor (no radar;
  no CAN throttle on pre-AP).
- **No stop-and-go / hard braking authority** — vacuum brakes, no
  iBooster. openpilot can only cut throttle and regen.
- **No standstill steering** — the rack's speed gate applies to
  openpilot exactly as it does to `tesla_control.py`.

## Troubleshooting quick table

| Symptom | First check |
|---|---|
| "Installation failed" at setup | URL typo; Wi-Fi captive portal; branch name wrong (e.g. the nonexistent `commaai/agnos8`) |
| Bootloop after install on 3X | Fork/AGNOS too old for 3X hardware — likely BogGyver-on-3X incompatibility (plan §2a) |
| Fork boots, no CAN data in car | Harness pins 1/9 not actually populated; adapter seated; check with the laptop sniffer (`can_sniffer.py`) on X437 that the bus is alive |
| EAC flicker while 3X connected | Second transmitter on `0x488` — is the laptop also connected? (Theory C) |
| Fork wants to flash EPAS | Stop. Rack is already patched. Investigate detection before any re-flash. |
