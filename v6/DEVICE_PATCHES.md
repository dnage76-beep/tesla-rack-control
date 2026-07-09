# Device-side patches & fixes (comma 3X, tesla-unity)

Changes we make **directly on the comma 3X** (in `/data/openpilot`,
the xnor-tech `tesla-unity` checkout) — not in this repo. They live on
the device's `/data` partition, survive reboots, and are **lost if you
do a full reinstall/factory-reset**, so they're recorded here.

**Working baseline** (what a healthy device shows):
AGNOS **9.1**, slot `_b`, commit `5fc42b86` (`xnor-tech/openpilot @
tesla-unity`, openpilot 0.9.6-Beta63). Device IP over USB/hotspot
tether: `172.20.10.2` (yours may differ — check Settings → Network).

> **Golden rule:** never `flash.comma.ai` / factory-reset — that flashes
> AGNOS 18 and undoes the hard-won 9.1 state.

---

## Gotcha: two different params folders

The fork has **two** places for settings, and mixing them up wastes time:

| Path | What's in it |
|---|---|
| `/data/params/d/` | Standard openpilot params (dongle id, calibration, training) |
| `/data/params/` (parent) | **Tinkla/tesla-unity toggles** — e.g. `TinklaHasIBooster`, `TinklaAPForceFingerprint` |

A tesla-unity toggle you set in the UI ends up as a file in
`/data/params/` (e.g. `/data/params/TinklaHasIBooster`), **not** in
`/data/params/d/`. `1` = on, `0` = off; if the file is missing the code
uses its default. This is why the backup in `capture_comma_state.sh`
(which only tars `/data/params/d/`) does **not** capture the toggles —
back up `/data/params/Tinkla*` separately.

---

## Patch 1 — Turn OFF "Car has iBooster"

**In plain terms:** Someone flipped on the "Car has iBooster" switch.
Our car has old-style vacuum brakes, not an iBooster, so openpilot
starts looking for a brake computer that isn't there and errors out.
The UI wouldn't let us switch it back off, so we clear it from the
command line.

**Fix:** set the `TinklaHasIBooster` toggle to `0` and reboot.

```bash
ssh comma@172.20.10.2
echo -n "0" > /data/params/TinklaHasIBooster   # 0 = off
cat /data/params/TinklaHasIBooster              # confirm it prints 0
sudo reboot
```
Undo (re-enable, only if you ever add a real iBooster):
`echo -n "1" > /data/params/TinklaHasIBooster`.

---

## Patch 2 — Run driver-monitoring on the CPU instead of the DSP

**In plain terms:** The 3X has a special AI chip (the "DSP") that's
supposed to run the driver-watching camera model. On our old software +
newer 3X, that chip never turns on, so the driver-monitoring program
keeps crashing ("dmonitoringmodeld process not running"). The driving
model runs on the graphics chip (GPU), which works fine — only the
driver-monitoring piece needs the dead chip. The fix tells that one
program to use the regular CPU instead of the DSP so it stops crashing.

**Fix:** change one word in `dmonitoringmodeld.py` — `Runtime.DSP` →
`Runtime.CPU`.

```bash
ssh comma@172.20.10.2
cp /data/openpilot/selfdrive/modeld/dmonitoringmodeld.py /data/dmonitoringmodeld.py.bak
sed -i 's/self.output, Runtime.DSP, True, None/self.output, Runtime.CPU, True, None/' \
    /data/openpilot/selfdrive/modeld/dmonitoringmodeld.py
grep -n "ModelRunner(MODEL_PATHS" /data/openpilot/selfdrive/modeld/dmonitoringmodeld.py
```

Test before rebooting (should load and wait for the camera instead of
"Aborted"):
```bash
cd /data/openpilot
PYTHONPATH=/data/openpilot python -m selfdrive.modeld.dmonitoringmodeld
# Ctrl-C once it stops aborting, then:
sudo reboot
```

**If CPU still errors** (the DSP model file won't run on CPU), switch
that program to the ONNX model instead:
```bash
python -c "import onnxruntime; print('onnx ok')"   # must succeed first
# then edit /data/openpilot/selfdrive/modeld/dmonitoringmodeld.py:
#   delete the line   ModelRunner.SNPE: Path(__file__).parent / 'models/dmonitoring_model_q.dlc',
#   leaving only the  ModelRunner.ONNX: ... line in MODEL_PATHS
sudo reboot
```
Undo: `cp /data/dmonitoringmodeld.py.bak /data/openpilot/selfdrive/modeld/dmonitoringmodeld.py`.

**Note:** getting the process to *run* is step one. Driver-attention
*enforcement* is separate — on CPU it may lag, and openpilot will still
nag/disengage if it can't see an attentive driver. For an
operator-supervised research setup you'll likely also want to relax that
gating; handle that as a follow-up once the process is stable.

**Why this keeps happening:** a dead compute-DSP is one more thing that
works out of the box on the modern openpilot the 3X shipped with. These
patches keep the frozen-0.9.6 tesla-unity usable now; the durable path
is still the bridge (`v6/comma/`) — modern openpilot brain, our CAN
transmitter.

---

## Restore points

- Back up the toggles before changing them:
  `mkdir -p /data/settings_backup && cp /data/params/Tinkla* /data/settings_backup/`
- Record the exact code commit: `cd /data/openpilot && git rev-parse HEAD`
- Full snapshot: `v6/capture_comma_state.sh` (see `v6/README.md`).
