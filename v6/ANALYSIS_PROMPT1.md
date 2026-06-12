# v6 Cost-Benefit Analysis — response to [prompt1.md](prompt1.md)

Requested by Charlie (commit `7a9d1dc`, 2026-06-10): compare the
possible paths for getting a comma 3X to operate on the 2013 pre-AP
Model S. Analysis below; facts verified 2026-06-10/12 against the
sources cited. Companion docs: [V6_PLAN.md](V6_PLAN.md) (fork
research detail) and [INSTALL_GUIDE.md](INSTALL_GUIDE.md).

Last updated: 2026-06-12.

---

## 0. Framing: v6 is a different species than v5

Before the comparison, one thing worth stating plainly, because it
drives every estimate below. v4/v5 and v6 are not versions of the
same thing:

| | v4/v5 (rack control family) | v6 (openpilot family) |
|---|---|---|
| Brain | Human operator (slider, keyboard, RC sticks) | Software (camera + neural net + planner) |
| Compute | Derek's laptop | comma 3X on the windshield |
| Our code's role | We ARE the control stack | We are integrators of someone else's stack |
| CAN role | We transmit `0x488` ourselves | The device transmits `0x488`; we must be OFF the bus |
| Hard problems | Protocol reverse-engineering (done) | Software/OS compatibility, fork maintenance |
| Failure mode | Bug in ~3,000 lines we wrote | Incompatibility somewhere in ~1M lines we didn't |

v5 was finishable by us alone because every line was ours. v6's
difficulty is almost entirely about **whose stack we ride on and
how alive it is** — which is exactly what the three options differ
on.

## 1. Corrections to the prompt's premises (important)

Three factual corrections before the options, because Option 1's
cost estimate changes with them:

1. **The "requires AGNOS 8" claim is unsupported.** The cited issue
   ([commaai/openpilot#28726](https://github.com/commaai/openpilot/issues/28726))
   is unrelated — it's a June 2023 "Process Not Running" bug report
   for a **Lexus NX300h**, with no mention of AGNOS versions, Tesla,
   Tinkla, or the 3X (fetched and read 2026-06-12). The primary
   source says otherwise: `launch_env.sh` on both
   `BogGyver/openpilot` C3 branches pins **`AGNOS_VERSION="9.1"`**
   (read directly from the branch, 2026-06-10).
2. **No manual AGNOS downgrade is needed — or possible via that
   URL.** Fork installers flash their own pinned AGNOS
   automatically on first boot. `installer.comma.ai/commaai/agnos8`
   points at a branch that does not exist on commaai/openpilot
   (verified via `git ls-remote`, 2026-06-10), which is why that
   attempt went nowhere. The correct legacy attempt is simply
   `installer.comma.ai/BogGyver/tesla_unity_releaseC3` — the
   installer itself handles the AGNOS 18.4 → 9.1 transition (or
   fails trying, see Option 1 risks).
3. **The harness problem has a current commercial answer.** Tinkla
   is gone, but the xnor shop sells a
   [pre-AP Model S OBD-C harness kit](https://xnor.shop/products/model-s-preap-kit)
   today, and the [commaai community wiki](https://github.com/commaai/openpilot/wiki/tesla)
   (updated 2026-05-21) lists pre-AP Model S as supported on
   **comma 3X** through the xnor ecosystem. This is effectively a
   fourth option the prompt didn't have — and it reshapes the whole
   comparison.

## 2. The options

### Option 0 (new): the xnor/Loetkolben continuation — *recommended*

The community successor to BogGyver: active fork
([xnor-tech/openpilot](https://github.com/xnor-tech/openpilot),
commits through April 2026, openpilot 0.10.1 base, AGNOS 12.8 —
3X-native), commercial harnesses in stock, a wiki, and a Discord.
This is "Option 1's goal achieved by someone else who is still
around."

- **Technical challenges**: almost none on our side — buy kit,
  install URL, plug in. The EPAS patch (their one prerequisite) is
  **already flashed on our rack**.
- **Effort**: days of our time + shipping from Germany.
- **Risks / unknowns**: the wiki links a `tesla-unity` branch on
  xnor-tech that is not publicly visible (verified missing via
  `git ls-remote`, 2026-06-10) — the actual pre-AP build/URL must
  be confirmed in the [xnor Discord](https://discord.xnor.shop/)
  before buying. The public `xnor-c3` branch covers HW1 (2014+)
  but has no pre-AP platform entry, so pre-AP support lives
  somewhere we haven't seen yet. Quality on pre-AP specifically is
  unverified by us. One hobbyist maintainer = bus factor of 1
  (but that was equally true of BogGyver in his prime).
- **Probability of success**: **high (~75-85%)** — this is the
  configuration the community wiki currently documents as the
  supported path for exactly our car and exactly our device.

### Option 1: restore the legacy BogGyver/Tinkla stack

- **Technical challenges**: getting AGNOS 9.1-era software to run
  on 2026-era 3X hardware. The 3X floor is openpilot 0.9.4
  ([docs.howtocomma.com](https://docs.howtocomma.com/docs/hw-three-3x));
  tesla_unity is 0.9.6, so it clears the floor *on paper* — but
  only for 3X hardware revisions that existed in Jan 2024. A 3X
  shipped recently (ours runs AGNOS 18.4, so it's recent) may have
  display/SOM/modem revisions that AGNOS 9.1 has no drivers for.
  AGNOS downgrades are also documented to strand devices
  (e.g. [commaai/openpilot#34365](https://github.com/commaai/openpilot/issues/34365),
  "stuck in registering device after downgrading AGNOS");
  recovery is a full reflash at flash.comma.ai — annoying, not
  fatal.
- **Effort to try**: **one afternoon** (the correct installer URL,
  not an AGNOS hunt). Effort to make it *work* if the afternoon
  fails: unbounded — we'd be patching a dead 0.9.6 codebase for a
  device it never targeted, alone.
- **Risks / unknowns**: codebase frozen Jan 2024, issues dormant
  since 2023, no upstream to ask. Every bug is ours forever. Even
  full success lands us on a 2.4-year-old openpilot with old
  driving models.
- **Probability of success**: **low-moderate (~25-40%)** for
  "boots and drives on our 3X," and the prize for winning is a
  dead-end stack.
- **Verdict**: worth the one-afternoon spike (it's nearly free and
  answers V6_PLAN open question 2), but never worth a second day.

### Option 2: port Model S support onto current openpilot ourselves

- **Technical challenges**: a car port is real software
  engineering across three repos: an opendbc platform definition
  (CarState/CarController/fingerprints for a car with no firmware
  query support), a panda safety mode (pre-AP legacy CRC + angle
  limits), and tuning (lateral control, vision-only longitudinal,
  no radar). We hold unusually good cards — PROJECT_MEMORY.md
  documents the exact `0x488` format, CRC algorithm, EAC state
  machine, and bus topology, all field-validated — but upstream
  comma will not accept a pre-AP port (their supported list starts
  at Model 3/Y HW3), so this is *maintaining our own fork forever*,
  the exact burden that killed BogGyver's and is carried by xnor
  today.
- **Effort**: months part-time (a working lateral-only port:
  ~2-4 months; polished daily-driver behavior: 6+), with the car
  needed regularly for validation.
- **Risks / unknowns**: openpilot internals churn fast (the car
  interface moved repos twice in two years); we'd chase a moving
  target solo.
- **Probability of success**: moderate for lateral-only
  (~50-70%) given our protocol knowledge; the real cost is the
  *permanent* maintenance tail.
- **Verdict**: only rational as a **contribution to xnor's fork**
  (if their pre-AP branch turns out to be missing/stale, our
  protocol documentation and a port PR make us collaborators
  instead of lone maintainers). As a solo project it re-fights a
  war someone else is already winning.

### Option 3: self-driving stack from scratch

- **Technical challenges**: all of them. Perception, planning,
  controls, calibration, a safety case, training data, and
  infrastructure — this is what comma.ai itself is, after ~10
  years and a large engineering team. Even "on an RC platform"
  (the prompt's framing) it's a multi-year research program, and
  an RC-platform stack does not transfer to a 4,700 lb car
  carrying humans without redoing the safety engineering entirely.
- **Effort**: years. **Probability of reaching "operates the
  Model S"**: effectively **~0%** at hobby scale.
- **Verdict**: reject for v6. If the actual appetite is *learning*
  perception/planning hands-on, do it as a separate educational
  RC-car project (donkeycar-style) that never touches the Tesla —
  but that's a different project with a different goal, not a path
  to this one.

## 3. Comparison table

| | Option 0: xnor | Option 1: legacy BogGyver | Option 2: own port | Option 3: from scratch |
|---|---|---|---|---|
| Major challenge | Confirm branch/URL, buy kit | Old OS on new hardware, alone | Full car port + forever-fork | Build comma.ai again |
| Difficulty | Low | Low to attempt, extreme to fix | High | Research-program |
| Time | Days (+ shipping) | 1 afternoon to try | Months → indefinite | Years |
| Out-of-pocket | Harness kit + shipping | $0 (have everything) | $0 hardware, all labor | RC platform + compute |
| Key risk | Pre-AP branch not public yet; bus factor 1 | Bricked-ish device (reflashable); dead-end even if it works | Maintenance tail forever | Doesn't terminate |
| P(success) | **~75-85%** | ~25-40% | ~50-70% lateral-only | ~0% |
| Stack freshness | openpilot 0.10.x, maintained | 0.9.6, frozen 2024 | current, self-maintained | n/a |

## 4. Recommendation

The prompt's stated objective is *minimum effort, maximum
probability of success*. That is **Option 0** by a wide margin,
with a cheap Option 1 spike in parallel since it costs nothing:

1. **Now**: join the [xnor Discord](https://discord.xnor.shop/),
   confirm the current pre-AP comma 3X build + installer URL, and
   order the [pre-AP harness kit](https://xnor.shop/products/model-s-preap-kit)
   once confirmed. (Also check our OBD2 port for pins 1/9 —
   V6_PLAN.md §3 — before ordering.)
2. **While waiting**: the one-afternoon Option 1 spike —
   `installer.comma.ai/BogGyver/tesla_unity_releaseC3` on the 3X
   (procedure in [INSTALL_GUIDE.md](INSTALL_GUIDE.md)). If it
   boots, we have an interim baseline; if it bootloops, factory
   reset / flash.comma.ai and we've answered the question for $0.
3. **Only if** xnor's pre-AP support turns out to be vapor:
   reconsider Option 2 *as a contribution to their fork*, leading
   with our PROJECT_MEMORY.md protocol work as the down payment.
4. **Option 3**: rejected for v6 in any form.
