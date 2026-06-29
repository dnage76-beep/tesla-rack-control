# v6 — openpilot on the car (comma 3X)

This directory is the home for the **v6 effort: getting a comma 3X
running an openpilot fork on Derek's 2013 pre-AP Model S**. This is
the project that the ROADMAP called "Phase 5: openpilot integration."

**v6 is NOT rack control.** It does not touch `tesla_control.py`,
the SYS TEC adapter, or the laptop control loop. It is a separate
track with its own hardware path (comma 3X on chassis CAN) and its
own software (an openpilot fork running on the device). This
directory exists so the two tracks don't get tangled.

Last updated: 2026-06-10.

---

## Documents

| File | What it is |
|---|---|
| [V6_PLAN.md](V6_PLAN.md) | The plan: software fork choice, hardware needed, phases, open questions. Read this first. |
| [INSTALL_GUIDE.md](INSTALL_GUIDE.md) | Step-by-step comma 3X setup: flashing, installer URL, harness, first power-on checks. |
| [prompt1.md](prompt1.md) | Charlie's request (2026-06-10): cost-benefit analysis of the possible v6 paths. |
| [ANALYSIS_PROMPT1.md](ANALYSIS_PROMPT1.md) | The requested analysis: four options compared, with premise corrections (the AGNOS 8 claim) and a recommendation. |
| [V6_OPENPILOT_FORK_PLAN.md](V6_OPENPILOT_FORK_PLAN.md) | Plan for forking modern openpilot as the *brain* while our laptop code transmits `0x488`, engaged on the cruise stalk. Verified seam (`steeringAngleDeg` ↔ `target_angle_deg`), three architectures, code-reuse map, staged milestones. |
| [comma/](comma/README.md) | **The bridge code (M0/M1).** `comma/comma_steer_forward.py` runs on the 3X and forwards `steeringAngleDeg` over TCP; `../tesla_control_comma.py` feeds it into `ctrl.target_angle_deg`. Engages by following openpilot's `latActive` (the cruise-stalk pull). |
| [AGNOS_9.1_RUNBOOK.md](AGNOS_9.1_RUNBOOK.md) | Field runbook: command-by-command diagnosis of why the 3X won't land on AGNOS 9.1 (the fork pins 9.1 and *downgrades* from 18.x — it never forces 18), with decision branches and how to force/verify 9.1. |
| [../docs/build/V6_OPENPILOT_PLAN.pdf](../docs/build/V6_OPENPILOT_PLAN.pdf) | Printable plan, filed next to ROADMAP.pdf: architecture + connection diagrams, install flowchart, gated test plan (T0-T4), commercial cost analysis, and a links page crediting the xnor/Loetkolben project. Regenerate with `python docs/build/build_v6_pdf.py` (needs `reportlab`). |

---

## The one rule that carries over from v4

**Never run `tesla_control.py` while the comma 3X is connected to
chassis CAN.** This is Theory C (PROJECT_MEMORY.md Section 8),
confirmed in May 2026: the comma device transmits `0x488`
(DAS_steeringControl) whenever it sees `0x115` from the car. Two
transmitters on the same arbitration ID caused the
HIGH_ANGLE_RATE_REQ flicker. The 3X was removed from the bus for
v4 for exactly this reason. v6 puts it back — so the two systems
are **mutually exclusive on the bus**:

- Doing rack-control work → unplug the 3X harness.
- Doing openpilot work → don't start `tesla_control.py`.
- The v4.2 bus diagnostic panel shows `0x488` RX rate; if it is
  >0 while the laptop is the only intended transmitter, a second
  transmitter (the 3X) is on the bus. Stop and unplug it.

---

## Status

- [x] EPAS firmware already patched (gregjhogan patch, flashed by
      Jordan via the BogGyver openpilot UI) — the hard prerequisite
      is **already done** on this car.
- [x] comma 3X in hand (removed from the bus since v4). Currently
      runs stock AGNOS 18.4 (per Charlie, prompt1.md).
- [x] Software fork identified (2026-06-13):
      `installer.comma.ai/xnor-tech/tesla-unity` — Tesla Unity
      0.9.6-Beta63 rehosted by Loetkolben with explicit
      `PREAP_MODELS` support (V6_PLAN.md §2b).
- [ ] Fork verified bootable on our 3X (AGNOS 9.1 vs recent
      hardware revision is the remaining risk).
- [ ] Harness path confirmed (OBD2 pins 1/9 populated? else X437
      tap) — see V6_PLAN.md Section 3.
- [ ] Device installs, boots, sees chassis CAN, fingerprints the car.
- [ ] First engage on a road at >18 mph.
