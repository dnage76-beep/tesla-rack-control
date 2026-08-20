# Comma 4 Findings Report

Compiled 2026-07-24 from live GitHub state (commaai + xnor-tech repos), comma.ai release
history, and the team Milanote board. Action plan lives in `plan.md`; this is the
evidence behind it.

## 1. What "mici" is

"mici" is comma's internal codename for the **comma four** (FCC ID `2BFC6-MICI`, visible
in `selfdrive/assets/offroad/mici_fcc.html`). Device codenames used across the codebase:

| Codename | Device |
|---|---|
| tici | comma 3 |
| tizi | comma 3X |
| mici | comma four |

comma four launched Nov 9, 2025 at $999. Stock openpilot has fully supported it since
roughly v0.10.3; 0.11.x development is comma-4-first. Latest release: v0.11.1
(Jun 5, 2026); master is 0.11.2-dev.

## 2. Why release-mici and release-tizi look identical

Because they are identical. Verified via the GitHub API:

```
release-mici: 70e1574623  2026-06-05  "openpilot v0.11.1"
release-tizi: 70e1574623  2026-06-05  "openpilot v0.11.1"
compare release-tizi...release-mici: 0 ahead, 0 behind, 0 files changed
```

Both branches point to the **same commit**. Since 0.11.x, comma builds one unified
release image that runs on both the 3X and the 4; hardware is detected at runtime by the
hardware abstraction layer (`system/hardware/`, one `tici`-family module covers the
variants). The per-device branch names exist as **stable update channels** so each
device's updater/installer has a fixed branch to track, not because the code differs.

The device that did NOT get this treatment is the comma 3: `release-tici` froze at
v0.10.0 (Sep 2025). That is the actual EOL split; tizi/mici march forward together.

## 3. xnor-tech fork survey

Full verdict table in `plan.md`. Summary:

- **`xnor-dev`** (last commit 2026-07-16) is the active Tesla branch: v0.11.1 base,
  complete mici stack (159 mici paths), submodules pinned to `xnor-tech/opendbc` and
  `xnor-tech/panda`. **`xnor`** is its prebuilt install branch.
- Tesla support lives in **opendbc**, not openpilot: `opendbc/car/tesla/` incl.
  `teslacan_legacy.py`, safety `opendbc/safety/modes/tesla_legacy.h`, tests for
  HW1/HW2-3. Platforms defined: Model S/X HW1 (2014-16) through HW4, routed through the
  `teslaLegacy` safety model with per-hardware flags.
- Dead ends: `xnor-c3`/`xnor-c3-dev` (v0.10.1, comma 3 only, stale since Feb),
  `tesla-unity` (Jul 2025 Tinkla lineage), `rx*` (Rivian, very active but not ours).
- xnor-tech has no public GitHub Projects boards; branch commits are the activity signal.

## 4. The open risk

The fork's oldest tier is **HW1 = 2014-16 AP1**. Our 2013 Model S is pre-AP (no AP
hardware at all; EPAS CAN control only exists because of the gregjhogan firmware patch).
Whether a flashed pre-AP car fingerprints under the HW1-legacy path or falls through
entirely is unverified. That is plan steps 1-2: read
`opendbc/car/tesla/{values,fingerprints,interface}.py` end to end, then ask Robert
Cotran / the Discord (contacts on the Milanote Outreach board) before burning bench time.

## 5. What this means for the comma 4 goal

1. Install target: `xnor` prebuilt (installer URL pattern `installer.comma.ai/xnor-tech/xnor`)
   on the comma 4; it is built from a comma-4-capable base, so booting the mici UI is
   expected to work.
2. The comma 3X + BogGyver `tesla_unity_releaseC3` stays as the EPAS flash tool only.
3. The whole project's remaining unknown is pre-AP fingerprinting, not device support.
   Device-side work is already done upstream and in the fork.

## 6. Code read verdict (2026-07-24, xnor opendbc @ afb1e62)

The HW1-legacy path looks BUILT for flashed racks, not stock AP1 cars:
- openpilot itself emulates the whole DAS: sends DAS_steeringControl (0x488) and
  DAS_control (0x2b9), long control force-enabled for all legacy cars.
- For HW1 specifically it skips APS_eacMonitor, i.e. it assumes the EPAS does not
  need the eacAllow handshake: consistent with a gregjhogan-patched rack.
- carstate needs only chassis-CAN messages (ESP_B, EPAS_sysStatus, DI_state,
  DI_torque1/2, GTW_carState, BrakeMessage); airbag msg optional (NO_SDM1 -> RCM_status).

Two gates remain, both bench-testable in an hour:
1. FINGERPRINT: legacy cars match by EPS firmware only (UDS query to ECU 0x730,
   bus 0). HW1 accepts `1016704-00-HAA` (classic Model S EPAS part family) or
   `\x10\x00A`. No CAN-message fallback exists. Test: UDS-query our rack, see what
   it returns. If it differs, add the string to fingerprints.py (one line).
2. SAFETY RX CHECK: tesla_legacy.h FLAG_HW1 requires DAS_control at 25 Hz on BUS 2.
   openpilot transmits it on bus 0. Whether the harness/loopback satisfies bus 2 on
   a pre-AP car with an X437 tap is the open wiring question. If not, it's a small
   safety-config patch or the right harness bus assignment.

Bottom line: this fork very likely already supports our exact use case (the design
choices only make sense for patched pre-AP/legacy racks). Expected worst case is a
one-line fingerprint addition plus bus wiring, not a new port.
