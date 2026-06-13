# V6 Plan — comma 3X + openpilot on the 2013 pre-AP Model S

Goal: a comma 3X mounted in the car, connected to chassis CAN,
running an openpilot fork that supports pre-AP Tesla, able to
steer the (already-patched) EPAS rack and provide vision-based
adaptive cruise.

This is a planning document. Cross-reference
[PROJECT_MEMORY.md](../PROJECT_MEMORY.md) for the canonical fact
base on the car. Facts below were verified 2026-06-10 against the
primary sources cited; anything not verified is flagged.

Last updated: 2026-06-10.

---

## 1. What we start with (verified)

| Fact | Value | Source |
|---|---|---|
| Car | 2013 Model S, pre-AP, post-May-31 build, RWD, vacuum brakes | PROJECT_MEMORY.md §2 |
| EPAS | **Already patched** with [gregjhogan/tesla-pre-ap-epas-patch](https://github.com/gregjhogan/tesla-pre-ap-epas-patch); accepts `0x488` steering commands directly | Flashed by Jordan via the BogGyver openpilot UI; proven by every v4 steering session |
| Device | comma 3X, currently off the bus (removed in v4, Theory C) | PROJECT_MEMORY.md §8 |
| Bus needed | Chassis CAN (500 kbps): EPAS, GTW, ESP, SCCM, DI | PROJECT_MEMORY.md §3 |
| Known tap points | X437/TDC under the center screen (what Derek/Jordan use); OBD-II pins 1/9 **if populated** (build-date dependent) | PROJECT_MEMORY.md §3 |

The big-ticket prerequisite — the EPAS firmware patch — is already
done. v6 is mostly a software-selection, harness, and
commissioning problem, not a reverse-engineering problem.

---

## 2. Software: which fork

### 2a. BogGyver / Tinkla "tesla_unity" — the original, now frozen

Verified directly against `github.com/BogGyver/openpilot` (git,
2026-06-10):

- Relevant branches: `tesla_unity_releaseC3` (last commit
  **2024-01-21**) and `tesla_unity_betaC3` (last commit
  **2024-01-23**, "Tesla Unity v0.9.6-Beta63" — the newest commit
  in the entire repo).
- Frozen at openpilot ~0.9.6. **No commits in ~2.4 years.** Issue
  tracker dormant since July 2023.
- Both C3 branches pin `AGNOS_VERSION="9.1"` in `launch_env.sh`
  (verified by reading the file on both branches). The installer
  flashes that AGNOS automatically — no separate AGNOS step needed.
- The [commaai community wiki Tesla page](https://github.com/commaai/openpilot/wiki/tesla)
  (last edited 2026-05-21) describes Tinkla/Unity as
  **"unmaintained since 2023."**
- **comma 3X compatibility is unverified.** The `…C3` branches
  were built for the comma *three*; the 3X shipped late 2023 with
  different internals. No primary source confirms tesla_unity
  boots and drives on 3X hardware. Tinkla's own pages list "comma
  two / comma three dev kits" only. Treat "it runs on the 3X" as
  a hypothesis to be tested, not a fact.

### 2b. xnor-tech / Loetkolben — the active successor

Verified directly against `github.com/xnor-tech/openpilot` (git,
2026-06-10):

- Actively maintained: `xnor-c3` last commit 2026-02-21 (openpilot
  v0.10.1 base), `xnor-dev` 2026-04-25. `xnor-c3` pins
  `AGNOS_VERSION="12.8"` — current-generation, 3X-native.
- The commaai wiki (2026-05-21) lists pre-AP Model S as supported
  with device = "**comma 3X (NOT comma four)**", via the xnor
  ecosystem, using the [xnor preAP OBD-C harness kit](https://xnor.shop/products/model-s-preap-kit),
  "requires one-time EPAS patch, vision-based ACC 18+ MPH."
- **The pre-AP branch (resolved 2026-06-13)**: the wiki's
  `tesla-unity` link was a dead end on 2026-06-10 but the branch
  **now exists**:
  [xnor-tech/openpilot @ tesla-unity](https://github.com/xnor-tech/openpilot/tree/tesla-unity).
  Verified by shallow clone: `selfdrive/car/tesla/values.py`
  defines `PREAP_MODELS = 'TESLA PREAP MODEL S'`; version is
  **0.9.6-Beta63** (i.e. BogGyver's final Tesla Unity beta,
  rehosted and continued by Loetkolben — last commit 2025-07-16,
  author lukasloetkolben); `launch_env.sh` pins **AGNOS 9.1**.
  Install URL: `installer.comma.ai/xnor-tech/tesla-unity`.
  Note this is the frozen 0.9.6-era codebase under an active
  maintainer, NOT a port to the modern 0.10.x `xnor-c3` base —
  `xnor-c3`'s own Tesla port starts at HW1 (2014-16) with no
  pre-AP entry. Remaining question for the Discord: does AGNOS
  9.1 boot recent 3X hardware revisions.

### 2c. Decision

Recommended order of attack:

1. **Install `installer.comma.ai/xnor-tech/tesla-unity`** (found
   and verified 2026-06-13, see §2b). This is the wiki-documented
   pre-AP path under the active maintainer. Cost is one
   install/factory-reset cycle; if it bootloops on our 3X
   (AGNOS 9.1 vs recent hardware revisions is the open risk),
   recover via flash.comma.ai and take the question to the
   Discord with the exact failure documented.
2. **Use the xnor Discord for confirmation and support**, not
   discovery: confirm `tesla-unity` is still current for a 3X and
   ask about AGNOS 9.1 on recent hardware. The original BogGyver
   branch is now historical-reference only — same codebase, dead
   repo.

Not viable: upstream commaai/openpilot (supports Model 3/Y
HW3/HW4 only) and SunnyPilot-TeslaHW1 (AP1 cars, not pre-AP).

### 2d. About `installer.comma.ai/commaai/agnos8`

This URL was floated as the install method. **It points at a
branch that does not exist** — `git ls-remote` of
`commaai/openpilot` shows no `agnos8` branch (or any `agnos*`
ref), and `installer.comma.ai/<owner>/<branch>` only builds
installers from real branches of `<owner>`'s openpilot fork. It
is also not needed: fork installers flash their own pinned AGNOS
(BogGyver C3 → AGNOS 9.1; xnor-c3 → AGNOS 12.8) on first boot.
The correct URLs are in INSTALL_GUIDE.md. If "agnos8" came from a
guide or Discord post, re-read the source — it may have been an
AGNOS-downgrade trick for a different fork/era, and it is stale
either way.

---

## 3. Hardware: harness and bus connection

No comma car harness exists for pre-AP — the community solution is
an **OBD2-port adapter**, not a windshield giraffe:

- [xnor "Model S (preAP) Harness" kit](https://xnor.shop/products/model-s-preap-kit):
  plugs into the OBD2 port, OBD-C cable to the 3X, ~2 m extension
  included. Compatible "Tesla Model S preAP (2012 – Oct. 2014)".
  **Requires OBD2 pins 1 & 9 populated** (that's chassis CAN on
  this platform). Ships from Germany.
- If pins 1/9 are NOT populated on our build: Tinkla sold a
  [Chassis CAN Retrofit Harness](https://shop.tinkla.us/Tinkla-Chassis-CAN-Retrofit-Harness-p455366003)
  that taps chassis CAN at the diagnostic connector under the
  center console — the same X437/TDC area we already tap for the
  laptop. Worst case we build the equivalent ourselves; we know
  the pinout from the v4 work.

**First physical task of v6**: pull the OBD2 port cover and check
whether pins 1 and 9 are populated on this car. That decides the
harness order. (PROJECT_MEMORY.md §3 already flags this as
build-date dependent.)

Optional / later:

- **Pedal interceptor** (comma pedal): extends longitudinal
  control below the vision-ACC floor (~18 mph) down to ~1–5 mph.
  Connects via the adapter's CAN expansion port. This overlaps
  with V5_PLAN.md §2 — one interceptor serves both tracks.
- **Tinkla Buddy**: instrument-cluster integration, MCU1 cars
  only. Cosmetic; skip for now. Unverified whether it works with
  the current xnor stack.
- No external GPS or speed-signal hack is required in the
  OBD-C-era setup (the old EPAS-harness-era hacks are obsolete).

---

## 4. What openpilot gives us on this car (and what it can't)

| Capability | Status | Why |
|---|---|---|
| Lateral (steering) | Yes — the whole point | Patched EPAS accepts `0x488`; same mechanism our v4 laptop control uses |
| Adaptive cruise | Vision-based, **18+ mph** | No radar on a pre-AP car; vision ACC floor per commaai wiki |
| Low-speed longitudinal | Only with pedal interceptor | No CAN-commandable throttle on pre-AP (PROJECT_MEMORY.md §2) |
| Stop-and-go / full brake authority | **No** | Vacuum-assisted brakes, no iBooster (PROJECT_MEMORY.md §2) |
| Standstill steering | No | Same rack speed-gate as v4 (PROJECT_MEMORY.md §10) — openpilot doesn't change rack physics |

---

## 5. Phases

### Phase 0 — decisions and parts (no car time)
- Check OBD2 pins 1/9. Order xnor preAP kit (or plan X437 tap).
- Ask xnor Discord: current pre-AP branch + installer URL for 3X.
- Factory-reset the 3X; confirm it boots stock AGNOS.

**Acceptance**: harness on order, install URL confirmed.

### Phase 1 — bench install (device only, car not involved)
- Install the chosen fork via custom software URL (INSTALL_GUIDE.md).
- Confirm boot, UI loads, fork settings menu (Tesla preAP section)
  is present.

**Acceptance**: device boots the fork reliably.

### Phase 2 — on-car, passive
- Connect harness. Device powered from the port, sees chassis CAN.
- Confirm car fingerprint / manual pre-AP selection in fork settings.
- **Do NOT engage.** Drive normally; confirm device records a route,
  shows speed/steering angle matching reality.
- Confirm `tesla_control.py` is NOT in the picture (laptop
  disconnected) — Theory C discipline.

**Acceptance**: clean passive drive, plausible CAN data, no DTCs,
no EAC complaints from the rack.

### Phase 3 — first engage
- Open road, >18 mph (it's pre-AP: engagement floor), driver ready
  to override.
- Engage; verify smooth lateral, clean disengage on steering
  override and brake.

**Acceptance**: repeatable engage/disengage, no flicker, no faults.

### Phase 4 — daily-driver hardening + pedal interceptor (joint with v5)
- Tune, log, iterate. Add pedal interceptor for low-speed ACC if
  wanted. Revisit ROADMAP Phase 5 goals.

---

## 6. Open questions (ranked)

1. ~~What branch/URL is the current xnor pre-AP build?~~
   **Resolved 2026-06-13**: `xnor-tech/openpilot @ tesla-unity` →
   `installer.comma.ai/xnor-tech/tesla-unity` (§2b).
2. **Does the tesla-unity build (AGNOS 9.1) boot on a recent
   comma 3X hardware revision?** Cheap to test; also ask the
   Discord.
3. **Are OBD2 pins 1/9 populated on this post-May-31 2013 build?**
   → physical check, decides harness.
4. **Does the fork's EPAS-patch detection accept our
   already-patched rack** (patched outside its UI flow)? Expected
   yes — it's the same gregjhogan patch the BogGyver UI applies —
   but verify the settings screen shows "patched" rather than
   prompting to re-flash. Do NOT re-flash without a reason; we
   have a working rack.
5. **MCU1 vs MCU2 on this car** — only matters if we ever want
   Tinkla Buddy. Low priority.

---

## 7. Sources

- [BogGyver/openpilot](https://github.com/BogGyver/openpilot) — branches/dates verified via git 2026-06-10
- [xnor-tech/openpilot](https://github.com/xnor-tech/openpilot) — branches/dates and `xnor-c3` Tesla port contents verified via git 2026-06-10
- [commaai wiki — Tesla page](https://github.com/commaai/openpilot/wiki/tesla) — last edited 2026-05-21; most current overview
- [xnor shop — Model S preAP kit](https://xnor.shop/products/model-s-preap-kit); [xnor wiki](https://wiki.xnor.shop/); [xnor Discord](https://discord.xnor.shop/)
- [tinkla.us](https://tinkla.us) — OBD-C adapter, pedal interceptor, Buddy (2022-era pages; partially stale, snippet-verified only — these sites block automated fetching)
- [gregjhogan/tesla-pre-ap-epas-patch](https://github.com/gregjhogan/tesla-pre-ap-epas-patch) — last commit 2022-04-28
