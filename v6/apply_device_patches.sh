#!/usr/bin/bash
#
# apply_device_patches.sh -- recreate our working "driving" condition on a
# fresh comma 3X running the tesla-unity fork.
# =====================================================================
#
# Run ON the target 3X over SSH, AFTER it is already installed with
# tesla-unity (installer.comma.ai/xnor-tech/tesla-unity -> AGNOS 9.1,
# openpilot 0.9.6-Beta63, commit 5fc42b86) and the car's EPAS rack is
# patched. It edits /data/openpilot and /data/params in place, backing up
# every file it touches to /data/*.bak. Idempotent -- safe to re-run.
#
#   scp v6/apply_device_patches.sh comma@<ip>:/data/
#   ssh comma@<ip> 'bash /data/apply_device_patches.sh' ; ssh comma@<ip> sudo reboot
#
# IMPORTANT -- two classes of change:
#   * Section 1 (iBooster) is config hygiene: this car has vacuum brakes,
#     so the toggle must be OFF. Default is off; we just enforce it.
#   * Section 2 (DSP workarounds) exist ONLY because THIS 3X's compute-DSP
#     never comes up on AGNOS 9.1. If the target 3X's DSP works (test:
#     `PYTHONPATH=/data/openpilot python -m selfdrive.modeld.dmonitoringmodeld`
#     runs WITHOUT an "isRuntimeAvailable" abort), you do NOT need Section 2
#     -- DM/nav will run on the DSP with full safety checks. Only apply
#     Section 2 if that test aborts on the DSP like ours did.
# See v6/DEVICE_PATCHES.md for the full explanation of each change.

set -u
OP=/data/openpilot
PARAMS=/data/params

echo "=== preflight ==="
echo "AGNOS:  $(cat /VERSION 2>/dev/null)"
( cd "$OP" && echo "commit: $(git rev-parse --short HEAD)  branch: $(git rev-parse --abbrev-ref HEAD)" )
echo

bk() { cp -n "$1" "/data/$(basename "$1").bak" 2>/dev/null && echo "  backed up $(basename "$1")"; }

echo "=== Section 1: iBooster OFF (car has vacuum brakes) ==="
echo -n "0" > "$PARAMS/TinklaHasIBooster"
echo "  TinklaHasIBooster = $(cat "$PARAMS/TinklaHasIBooster")"
echo

echo "=== Section 2: DSP workarounds (only needed if this 3X's DSP is dead) ==="

echo "-- 2a. DM + nav models: Runtime.DSP -> Runtime.CPU"
for f in dmonitoringmodeld navmodeld; do
  bk "$OP/selfdrive/modeld/$f.py"
  sed -i 's/self.output, Runtime.DSP, True, None/self.output, Runtime.CPU, True, None/' \
      "$OP/selfdrive/modeld/$f.py"
  grep -q "Runtime.CPU, True, None" "$OP/selfdrive/modeld/$f.py" \
    && echo "  $f.py -> CPU OK" || echo "  $f.py: line not found (check manually)"
done

echo "-- 2b. disable unused nav stack (frees CPU)"
bk "$OP/selfdrive/manager/process_config.py"
sed -i 's/PythonProcess("navmodeld", "selfdrive.modeld.navmodeld", only_onroad)/PythonProcess("navmodeld", "selfdrive.modeld.navmodeld", only_onroad, enabled=False)/' "$OP/selfdrive/manager/process_config.py"
sed -i 's|NativeProcess("mapsd", "selfdrive/navd", \["\./mapsd"\], only_onroad)|NativeProcess("mapsd", "selfdrive/navd", ["./mapsd"], only_onroad, enabled=False)|' "$OP/selfdrive/manager/process_config.py"
sed -i 's/PythonProcess("navd", "selfdrive.navd.navd", only_onroad)/PythonProcess("navd", "selfdrive.navd.navd", only_onroad, enabled=False)/' "$OP/selfdrive/manager/process_config.py"
grep -nE '"(navmodeld|mapsd|navd)"' "$OP/selfdrive/manager/process_config.py" | sed 's/^/  /'

echo "-- 2c. exempt navModel + driverMonitoringState from controlsd comm checks"
bk "$OP/selfdrive/controls/controlsd.py"
sed -i "s/ignore = self.sensor_packets + \['testJoystick'\]/ignore = self.sensor_packets + ['testJoystick', 'navModel', 'driverMonitoringState']/" "$OP/selfdrive/controls/controlsd.py"
sed -i "s/ignore_avg_freq=\['radarState', 'testJoystick'\]/ignore_avg_freq=['radarState', 'testJoystick', 'driverMonitoringState']/" "$OP/selfdrive/controls/controlsd.py"
sed -i "s/ignore_valid=\['testJoystick','navModel'\]/ignore_valid=['testJoystick','navModel','driverMonitoringState']/" "$OP/selfdrive/controls/controlsd.py"
grep -nE "ignore = self.sensor_packets|ignore_alive=ignore" "$OP/selfdrive/controls/controlsd.py" | sed 's/^/  /'

echo
echo "=== done -- REBOOT to apply:  sudo reboot ==="
echo "Backups in /data/*.bak . Undo a file with: cp /data/<name>.bak $OP/<path>/<name>"
