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

## Patch 2 — Run the DSP models (driver-monitoring + navigation) on the CPU

**In plain terms:** The 3X has a special AI chip (the "DSP") that's
supposed to run two of the smaller AI models — the driver-watching
camera model and the navigation model. On our old software + newer 3X,
that chip never turns on, so those programs keep crashing
("dmonitoringmodeld process not running", then "navmodeld process not
running" when you engage). The main driving model runs on the graphics
chip (GPU), which works fine — only these two need the dead chip. The
fix tells them to use the regular CPU instead. **These are the only two
DSP models**, so patching both ends the crashing.

- `dmonitoringmodeld` runs all the time → its error shows immediately.
- `navmodeld` runs only when engaged (`only_onroad`) → its error shows
  when you engage.

**Fix:** change `Runtime.DSP` → `Runtime.CPU` in both files (one word each):

```bash
ssh comma@172.20.10.2
for f in dmonitoringmodeld navmodeld; do
  cp /data/openpilot/selfdrive/modeld/$f.py /data/$f.py.bak
  sed -i 's/self.output, Runtime.DSP, True, None/self.output, Runtime.CPU, True, None/' \
      /data/openpilot/selfdrive/modeld/$f.py
  grep -n "ModelRunner(MODEL_PATHS" /data/openpilot/selfdrive/modeld/$f.py
done
```

Test before rebooting — the key is that neither **"Aborted (core
dumped)" / `isRuntimeAvailable` assert** appears:
```bash
cd /data/openpilot
PYTHONPATH=/data/openpilot python -m selfdrive.modeld.dmonitoringmodeld   # loads, waits for camera
PYTHONPATH=/data/openpilot python -m selfdrive.modeld.navmodeld           # reaches "models loaded, navmodeld starting"
# Ctrl-C each once it's past the assert, then:
sudo reboot
```
(`navmodeld` will hang waiting for the map video stream when run by hand
— that's fine; success = it got past the DSP assert to "models loaded".)

**If CPU still errors** (a quantized `.dlc` won't run on CPU), switch
that program to the ONNX model instead (same idea for either file):
```bash
python -c "import onnxruntime; print('onnx ok')"   # must succeed first
# then in the offending file's MODEL_PATHS dict, delete the
#   ModelRunner.SNPE: ...'models/<name>_q.dlc',   line,
# leaving only the ModelRunner.ONNX: ...'.onnx' line, then reboot.
sudo reboot
```
Undo either patch: `cp /data/<name>.py.bak /data/openpilot/selfdrive/modeld/<name>.py`.

**Optional (later):** since we don't use navigation, `navmodeld` (and
`mapsd`/`navd`) could instead be disabled to save CPU rather than run on
CPU. That's a `process_config.py` change — do it only after the CPU
patch has the system stable.

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

## Patch 3 — Stop "Communication Issue Between Processes" from blocking engagement

**In plain terms:** Now that the driver-monitoring and navigation models
run on the slow CPU (and nav has no map to look at), they don't send
their status messages fast enough. openpilot has a watchdog that expects
every message on time; when `driverMonitoringState` and `navModel` show
up late/never, it throws *"Communication Issue Between Processes"* — which
is a blocking error, so you can't engage. The fix tells that watchdog not
to require those two messages.

**Why (verified):** `controlsd.py` builds a SubMaster and each cycle calls
`all_alive()`; a missing service → `commIssue` event, which is
`NO_ENTRY`+`SOFT_DISABLE` (blocks/disengages). `navModel` and
`driverMonitoringState` aren't in the `ignore_alive` list, so their
CPU-induced lateness trips it.

**Fix:** add both to `controlsd`'s ignore list (line ~79, the `ignore`
that feeds `ignore_alive`):

```bash
ssh comma@172.20.10.2
cd /data/openpilot
cp selfdrive/controls/controlsd.py /data/controlsd.py.bak
sed -i "s/ignore = self.sensor_packets + \['testJoystick'\]/ignore = self.sensor_packets + ['testJoystick', 'navModel', 'driverMonitoringState']/" \
    selfdrive/controls/controlsd.py
grep -n "ignore = self.sensor_packets" selfdrive/controls/controlsd.py
sudo reboot
```
Undo: `cp /data/controlsd.py.bak selfdrive/controls/controlsd.py`.

**Safety note:** ignoring `navModel` is harmless (nav unused). Ignoring
`driverMonitoringState` **relaxes openpilot's check that driver-monitoring
is communicating** — DM still runs and its attention events still apply,
but a slow/stalled DM is no longer treated as a fault. Acceptable for an
operator-supervised research vehicle; make it a conscious choice.

**Cleaner alternative (frees CPU):** since nav is unused and `navmodeld`
on CPU steals cycles from DM, disable the nav stack instead — add
`, enabled=False` to the `navmodeld`, `navd`, and `mapsd` entries in
`selfdrive/manager/process_config.py`. You still need `navModel` in
`ignore_alive` (controlsd subscribes to it regardless), but the freed CPU
may let `driverMonitoringState` keep up so you don't have to ignore it.
Try `ignore` with only `'navModel'` first, then disable the nav stack,
and see if DM stays green.

**Pattern:** each of Patches 2–3 is another symptom of running frozen
0.9.6 on a 3X whose compute-DSP is dead. They keep tesla-unity usable now;
the durable path remains the `v6/comma/` bridge (modern openpilot brain,
our CAN transmitter).

## Restore points

- Back up the toggles before changing them:
  `mkdir -p /data/settings_backup && cp /data/params/Tinkla* /data/settings_backup/`
- Record the exact code commit: `cd /data/openpilot && git rev-parse HEAD`
- Full snapshot: `v6/capture_comma_state.sh` (see `v6/README.md`).
