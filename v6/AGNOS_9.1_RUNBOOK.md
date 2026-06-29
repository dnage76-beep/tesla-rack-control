# AGNOS 9.1 diagnostic + remediation runbook

Goal of the session: find out **why the comma 3X isn't ending up on
AGNOS 9.1** after a BogGyver/tesla-unity install, and get it there if
the hardware allows.

Read [INSTALL_GUIDE.md](INSTALL_GUIDE.md) and the AGNOS section of
[V6_PLAN.md](V6_PLAN.md) first. This runbook is command-first; paste
outputs back into a session log (`field_testing/sessions/<date>_agnos/`).

## What we already verified (so you trust the steps)

From BogGyver `tesla_unity_releaseC3` source (read 2026-06):
- `launch_env.sh` pins `AGNOS_VERSION="9.1"`.
- `launch_chffrplus.sh` → `agnos_init()`: if `/VERSION` (installed
  AGNOS) `!=` `AGNOS_VERSION`, it runs
  `system/hardware/tici/agnos.py --verify system/hardware/tici/agnos.json`
  (swaps to the inactive A/B slot if 9.x is already flashed there),
  otherwise runs the updater to download+flash the 9.x images listed
  in `agnos.json` (hosted on `commadist.azureedge.net`).
- `agnos.py` CLI (verified from `__main__`): `--swap` = flash-until-
  verified then swap; `--verify` = swap only if already flashed;
  no flag = flash to inactive slot. Uses A/B slots via `abctl`.
- So the fork tries to **downgrade** 18.x → 9.1. There is no code in
  the fork that installs AGNOS 18. xnor `tesla-unity` pins the same
  9.1, so this applies to both.

Flags marked **(verify on the day)** below are comma binaries/procedures
I could not fully confirm from source — check `--help` live.

## Phase 0 — prep (before you touch the car)

- [ ] 3X, USB-C cable, laptop, this runbook open.
- [ ] SSH enabled on the 3X: Settings → Network → Advanced → **Enable
      SSH**, enter your GitHub username (pulls your key).
- [ ] Bookmark **flash.comma.ai** — that is the always-works recovery
      (reflashes latest AGNOS + clean openpilot) if anything bricks.
- [ ] Connect: USB-C tether → device is at **192.168.43.1**
      (or read its Wi-Fi IP from Settings → Network → Advanced).

```bash
ssh comma@192.168.43.1
```

## Phase 1 — capture current state (READ-ONLY; record every output)

```bash
# THE key fact: what AGNOS is actually installed right now
cat /VERSION

# Confirm the fork's pin and that we're actually on the fork
grep AGNOS_VERSION /data/openpilot/launch_env.sh
cd /data/openpilot && git log -1 --oneline && git remote -v && git branch
cat /data/openpilot/common/version.h | grep -i version

# A/B slot state  (exact flags vary -- check help first)
sudo abctl --help
cat /proc/cmdline | tr ' ' '\n' | grep -i slot      # androidboot.slot_suffix = active slot
df -h ; lsblk 2>/dev/null

# what happened on recent boots
tail -200 /tmp/launch_log 2>/dev/null
sudo journalctl -b | grep -iE "agnos|updater|slot|abctl|reboot" | tail -120
```

**Decision:**
- `/VERSION` already `9.1` → you're on it. Skip to Phase 5 (verify
  openpilot actually runs). Done.
- `/VERSION` is `18.x` (or anything ≠ 9.1) → continue.

## Phase 2 — can a 9.1 flash even succeed? (prerequisites)

```bash
# Are the 9.x AGNOS images still on the CDN? (pick the 'boot' url from agnos.json)
grep -m1 '"url"' /data/openpilot/system/hardware/tici/agnos.json
curl -sI "<paste that url>" | head -5        # want HTTP 200, not 404

# General internet from the device
ping -c2 commadist.azureedge.net
```

**Decision:**
- 404 / unreachable → the 9.1 images are gone from the CDN; the
  automatic path cannot work. Jump to Phase 4 (archived image) and
  bring it to the Discord (Phase 6).
- 200 + internet OK → continue to Phase 3.

## Phase 3 — manually drive the 9.1 flash with visible output

This is the same thing `agnos_init` does, but in the foreground so you
see exactly where it fails.

```bash
cd /data/openpilot
sudo AGNOS_VERSION=9.1 ./system/hardware/tici/agnos.py --swap \
     system/hardware/tici/agnos.json 2>&1 | tee /tmp/agnos_flash.log
```

Watch for: per-partition `Installing <name>: 0..100`, no `hash
mismatch` / `RequestException`, ending in a successful `swap`. Then:

```bash
sudo reboot
# reconnect after it comes up:
ssh comma@192.168.43.1 'cat /VERSION'
```

**Decision (the real diagnosis):**
- **A — comes up on `9.1`** → SUCCESS. Go to Phase 5.
- **B — back on `18.x`** → the 9.1 slot was flashed but **won't boot**,
  so A/B rolled back. This is the hardware/anti-rollback wall. Capture:
  ```bash
  sudo journalctl -b -1 | tail -300        # the FAILED 9.1 boot
  sudo abctl --help   # then dump slot status with whatever flag it lists
  ```
  Go to Phase 4 / Phase 6.
- **C — flash errored mid-way** (hash/download) → save
  `/tmp/agnos_flash.log`, retry once; if it persists it's a CDN/network
  problem, not hardware → Phase 4 (archived image) or fix network.

## Phase 4 — if the automatic downgrade is blocked: low-level 9.1 flash

Heavier "force" path. Only do this if Phase 3 said the images are
gone (C) or won't boot needs a different image set. **(verify on the day)**

- Get an AGNOS **9.x** full image set: from the `commaai/agnos-builder`
  releases, or reassemble from the `agnos.json` partition images.
- Use comma's QDL/EDL flasher (the tech behind flash.comma.ai; the
  `qdl`/`flash` tooling in `system/hardware/tici/` or agnos-builder).
  flash.comma.ai itself serves the **latest** AGNOS, so it will NOT
  give you 9.1 — you need the 9.1 image + qdl directly.
- Put the 3X in QDL/EDL mode (button+power+cable combo — confirm the
  exact 3X procedure on howtocomma/comma docs that day), flash, then
  re-install the fork.
- Reality check: this only works if a 9.x image that supports your 3X
  hardware revision exists. Phase 3 outcome B is the signal that it may
  not.

## Phase 5 — once on 9.1: verify openpilot, do NOT reflash EPAS

```bash
cat /VERSION                       # 9.1
cd /data/openpilot && git log -1 --oneline
# let it boot to the UI; confirm the Tesla preAP settings screen exists.
```
- If the UI's EPAS screen asks to **flash EPAS — STOP.** The rack is
  already patched; investigate detection before any write
  (PROJECT_MEMORY.md, INSTALL_GUIDE Step 4).

## Phase 6 — escalate with data, not guesses

If blocked at Phase 3-B/4, you now have the exact facts to ask the
[xnor Discord](https://discord.xnor.shop/): paste `/VERSION`, the
`agnos_flash.log`, the failed-boot `journalctl`, and the slot status.
Because xnor's `tesla-unity` pins the **same 9.1**, they will know
whether 9.1 boots on a current 3X and the precise workaround. This is
the load-bearing question for the entire frozen-0.9.6 path.

## If it's a hard wall

If 9.1 genuinely won't boot this 3X, BogGyver and xnor-tesla-unity are
both out for this device. That is the trigger to commit to the bridge
we built (`v6/comma/`) — modern openpilot (modern AGNOS the 3X already
runs) as the brain, our laptop as the CAN actuator — which never needs
AGNOS 9.1 at all.

## Record for the session log
`/VERSION` before/after · CDN reachable? · `agnos_flash.log` ·
Phase-3 outcome A/B/C · slot status · any EPAS-flash prompt (and that
you did NOT act on it).
