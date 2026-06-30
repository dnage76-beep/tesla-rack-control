# AGNOS 9.1 runbook — results (session 2026-06-29)

Raw terminal output:
[AGNOS_9.1_RUNBOOK_terminal_output.txt](AGNOS_9.1_RUNBOOK_terminal_output.txt)
(run by Jordan over an iPhone hotspot, `ssh comma@172.20.10.2`).

## Headline: the device is ALREADY on AGNOS 9.1. The premise was wrong.

```
cat /VERSION                       -> 9.1
git log -1 / remote                -> xnor-tech/openpilot @ tesla-unity (5fc42b86)
common/version.h                   -> COMMA_VERSION "0.9.6-Beta63"
/proc/cmdline                      -> androidboot.slot_suffix=_b
/tmp/launch_log                    -> "weston ready", overlay-update skipped
journalctl | grep agnos/updater    -> no AGNOS flash activity at all
```

The comma 3X is sitting stably on **AGNOS 9.1**, running the
**xnor-tech tesla-unity** pre-AP fork (openpilot 0.9.6-Beta63), and it
boots (weston/UI up). Because `/VERSION` (9.1) `==` `AGNOS_VERSION`
(9.1), `agnos_init` never triggers a flash — there is no "force to
AGNOS 18." Empirically confirmed: the earlier worry is resolved (or was
never the current state). **The AGNOS 9.1 goal is achieved.**

## Two non-issues, do not chase

- `ping commadist.azureedge.net` → 100% packet loss, BUT `curl -sI` the
  same host returned `HTTP/2 200`. Azure's CDN blocks ICMP and serves
  HTTPS fine; reachability is good.
- The first `curl` looked broken — that was a paste error (URL
  duplicated, SSH reset); the retry succeeded.
- Bonus: the AGNOS 9.x `boot` image still returns `200`
  (`last-modified: 2023-12-06`), so the 9.1 images remain archived on
  the CDN if a reflash is ever needed.

## Decision: drive the rack directly from tesla-unity (no new fork, no bridge)

They are already on the maintained pre-AP fork, which natively has
PREAP_MODELS, the 0x488 CarController, and cruise-stalk engagement. The
shortest "get it running without a new fork" path is to let tesla-unity
drive the rack itself; the laptop bridge in `v6/comma/` is now an
*optional* safety-wrapper, not a requirement.

### Next steps
1. **Bench, now** — confirm openpilot health: on the device,
   `tmux a` (prefix = backtick) to watch manager/cloudlog; confirm the
   UI and the **Tesla preAP** settings screen come up.
2. **Bench, now** — force the pre-AP car: set
   `/data/params/TinklaAPForceFingerprint` to `TESLA PREAP MODEL S`
   (via the preAP settings screen, or echo the param). The launch
   script then exports `FINGERPRINT` + `SKIP_FW_QUERY=1` (verified in
   launch_chffrplus.sh).
3. **Bench, now** — confirm the EPAS screen reports the rack **patched**.
   If it asks to flash EPAS, STOP (rack is already patched).
4. **Car** — the gating hardware step: get the comma onto **chassis
   CAN** (xnor preAP OBD-C harness → OBD2 pins 1/9, or an X437 tap).
   Needed for openpilot to see CarState (speed/angle/stalk) regardless
   of direct-vs-bridge.
5. **Car** — engage by pulling the cruise stalk; verify openpilot
   sends 0x488 and the rack tracks. On jacks first, then road
   (>18 mph, vision ACC).

If the comma cannot/should not transmit on the bus, fall back to the
`v6/comma/` bridge (tesla-unity brain → laptop transmits) — but the
comma still needs to be on the bus to RX CarState either way.
