# Comma 4 Port Plan -- xnor-tech/openpilot Branch Survey

Goal: get pre-AP Tesla openpilot (xnor-tech fork lineage) running on the comma four.
Surveyed 2026-07-24 against live GitHub state. Companion boards: Milanote "Tesla Innovation"
(Old Fork Integration Team / New Fork Bridge Team).

## Key facts first

- **"mici" is comma's codename for the comma four** (FCC ID 2BFC6-MICI, in-repo).
  comma four launched Nov 9, 2025 at $999. Stock openpilot has had full comma 4
  support since ~v0.10.3, and 0.11.x is comma-4-first.
- **Upstream releases:** v0.11.1 (Jun 5, 2026) is the latest release; master is 0.11.2-dev.
  v0.11.1 already contains the full mici (comma 4) stack.
- **Where the Tesla code actually lives:** NOT in the openpilot repo. Car ports moved to
  opendbc. The pre-AP/legacy Tesla support is in `xnor-tech/opendbc`
  (`opendbc/car/tesla/teslacan_legacy.py`, `opendbc/safety/modes/tesla_legacy.h`,
  safety tests `test_tesla_hw1.py` / `test_tesla_hw23.py`) plus `xnor-tech/panda`.

## Branch verdicts -- xnor-tech/openpilot

| Branch | Last commit | Base | comma 4 (mici) | Verdict |
|---|---|---|---|---|
| `xnor-dev` | 2026-07-16 ("bump opendbc") | v0.11.1 | YES (159 mici paths) | **USE THIS. Active dev branch, comma-4-capable.** |
| `xnor` | 2026-04-16 ("openpilot xnor prebuilt") | 0.11.x | YES | **Prebuilt/install branch of xnor-dev. Use for device installs.** |
| `master` | 2026-07-22 | 0.11.2-dev | YES | Clean upstream tracker, no Tesla changes on top. Reference only. |
| `xnor-c3` | 2026-02-21 | v0.10.1 | no | comma 3 only. Dead end for comma 4. |
| `xnor-c3-dev` | 2026-02-17 | 0.10.x | no | comma 3 dev. Dead end for comma 4. |
| `tesla-unity` | 2025-07-16 ("replace tinkla logo") | old | no | Legacy BogGyver/Tinkla lineage. A year stale. Historical reference only (we still use BogGyver `tesla_unity_releaseC3` on the 3X for EPAS flashing; that stays on the 3X). |
| `rx`, `rx-dev`, `rx-dev-src`, `rx-src`, `rx-test`, `rx-master` | very active (thru 2026-07-24) | 0.11.x | -- | **Rivian work. Not our project. Ignore.** |

Companion repos:

| Repo | Branches | Notes |
|---|---|---|
| `xnor-tech/opendbc` | `master`, `master-c3`, `master-xnor` | `master-xnor` = the Tesla legacy port. `xnor-dev` pins commit `afb1e62` which HAS the legacy Tesla files. `master-c3` pairs with the dead c3 branches. |
| `xnor-tech/panda` | (updated 2026-06-15) | Safety firmware side of the same port. |

Bottom line: **the fork maintainers already did the heavy lifting.** `xnor-dev` is based
on v0.11.1 which fully supports comma 4, and its pinned opendbc carries the legacy Tesla
port. The c3/tesla-unity branches are the "old fork"; `xnor`/`xnor-dev` are the "new fork."

## The real gap: is a true pre-AP car covered?

The xnor opendbc `values.py` tiers are: HW4, HW3, HW2, **HW1 (2014-16 AP1)**, for both
Model S and X. `LEGACY_CARS = (S_HW1, S_HW2, S_HW3, X_HW1, X_HW2)`, all routed through
the `teslaLegacy` safety model with per-HW flags.

Our car is a **2013 Model S: pre-AP, older than HW1**. No AP hardware, EPAS only
CAN-controllable because of the gregjhogan firmware patch. Whether the fork treats a
flashed pre-AP car as "HW1 minus camera" or doesn't fingerprint it at all is the single
question that decides how much work this port is.

## Plan

1. **Read the port before touching hardware.** Clone `xnor-tech/openpilot@xnor-dev` with
   submodules. Read `opendbc/car/tesla/{values,interface,carstate,fingerprints}.py` and
   `teslacan_legacy.py` end to end. Answer: is there a pre-AP fingerprint/flag, or does
   HW1 assume an AP1 harness + Mobileye messages we do not have?
2. **Ask the people who know.** Robert Cotran replied technically before (X164/X437);
   Andrew Sidhu's Discord invite is open (Derek's Discord: nagelbagel3507). Ask directly:
   "does xnor-dev support a gregjhogan-flashed pre-AP 2013 Model S, and on comma 4?"
   Cheapest possible step; could save weeks.
3. **Bench-install on the comma 4.** Custom-fork installer URL pattern:
   `installer.comma.ai/xnor-tech/xnor` (prebuilt branch). Verify it boots the mici UI
   and reaches the car-selection/fingerprint stage on the bench rack, wheels off.
4. **Fingerprint test on the rack.** Chassis CAN on OBD-II pins 1/9 as usual (SAFETY.md
   rules apply). See what the fork fingerprints the flashed rack as. If it lands on
   HW1-legacy and EPAS accepts torque frames, the port may be nearly free.
5. **Gap-fill if needed.** If pre-AP is not fingerprinted: smallest viable change is a
   pre-AP platform entry in `xnor-tech/opendbc` values/fingerprints + a `teslaLegacy`
   safety flag, modeled on HW1 minus the camera-side messages. That work goes in a fork
   of `master-xnor`, not in openpilot itself.
6. **Keep the 3X flashing path untouched.** BogGyver `tesla_unity_releaseC3` on the
   comma 3X remains the EPAS flash tool. The comma 4 is the runtime target only.

## Waste of time (do not sink evenings here)

- `xnor-c3`, `xnor-c3-dev`: superseded, no comma 4 support, 5 months stale.
- `tesla-unity`: a year stale, pre-move-to-opendbc architecture. Reference only.
- All `rx*` branches: Rivian, unrelated.
- Rebasing tesla code onto `master` (0.11.2-dev) ourselves: xnor-dev already tracks
  releases; ride their work instead.
- GitHub Projects boards on xnor-tech/openpilot: none visible (org has no public
  projects we can read). The activity signal is branch commits, not project boards.

## Open questions

- [ ] Pre-AP fingerprint present in `master-xnor` opendbc? (Plan step 1)
- [ ] Does `xnor` prebuilt actually boot on comma 4, or is it c3-tested only? (Step 3)
- [ ] Which AGNOS ships on the comma 4 vs the "unable to put AGNOS 8 on it" June issue
      -- was that attempt on the 3X or the 4?
- [ ] Panda safety: does `tesla_legacy.h` FLAG_HW1 path tolerate missing AP1 ECUs?
