#!/usr/bin/bash
#
# capture_comma_state.sh -- snapshot the working state of the comma 3X
# =====================================================================
#
# Run this ON the comma 3X (over SSH) to record exactly what AGNOS /
# openpilot / params / panda state the device is in -- e.g. after an
# unexplained reboot where "it just started working" and we need a
# reproducible record + a restore point.
#
# It does two things:
#   1. BACKS UP the params dir and the exact openpilot commit (the
#      config that "makes it work"), so this state can be restored.
#   2. CAPTURES a full read-only state dump to a text file you can scp
#      off the device and commit to this repo for analysis.
#
# Everything here is read-only except the backup tarball it writes to
# /data. It never flashes, swaps slots, or factory-resets.
#
# USAGE (on the comma, over SSH):
#   scp v6/capture_comma_state.sh comma@<ip>:/data/
#   ssh comma@<ip>
#   bash /data/capture_comma_state.sh                 # writes /data/comma_state.txt
#   bash /data/capture_comma_state.sh mylabel         # writes /data/comma_state_mylabel.txt
# Then, from your laptop:
#   scp comma@<ip>:/data/comma_state*.txt .
#   scp comma@<ip>:/data/params_backup_working.tar.gz .
# and commit the .txt under v6/ for analysis.

set -u

LABEL="${1:-}"
if [ -n "$LABEL" ]; then
  OUT="/data/comma_state_${LABEL}.txt"
else
  OUT="/data/comma_state.txt"
fi

OP_DIR="/data/openpilot"
PARAMS_DIR="/data/params/d"

# -------- 1. BACKUP (restore point) --------
echo "=== backing up working state ==="
tar czf /data/params_backup_working.tar.gz -C "$PARAMS_DIR" . 2>/dev/null \
  && echo "params  -> /data/params_backup_working.tar.gz" \
  || echo "WARN: params backup failed"
( cd "$OP_DIR" && git rev-parse HEAD ) > /data/working_commit.txt 2>/dev/null \
  && echo "commit  -> /data/working_commit.txt ($(cat /data/working_commit.txt))" \
  || echo "WARN: could not record commit"
echo

# -------- 2. CAPTURE (state dump) --------
{
echo "######## A. AGNOS / SLOT / UPTIME ########"
echo "VERSION: $(cat /VERSION 2>/dev/null)"
cat /proc/cmdline 2>/dev/null | tr ' ' '\n' | grep -i slot
sudo abctl --boot_slot 2>/dev/null
uname -a
uptime

echo; echo "######## B. OPENPILOT VERSION / GIT ########"
cd "$OP_DIR" 2>/dev/null || echo "WARN: $OP_DIR missing"
git log -1 --format='%H%n%ci%n%s' 2>/dev/null
echo "--- status ---"; git status -s 2>/dev/null
echo "--- branch -vv ---"; git branch -vv 2>/dev/null
echo "--- remote ---"; git remote -v 2>/dev/null
echo "--- versions ---"; grep -i version common/version.h 2>/dev/null
cat common/tinkla_version.h 2>/dev/null
grep AGNOS_VERSION launch_env.sh 2>/dev/null

echo; echo "######## C. WHY IT REBOOTED / WHAT CHANGED ########"
echo "--- tinkla splash flag (one-time fork self-reboot marker) ---"
ls -la /usr/comma/.tinkla_splash 2>/dev/null || echo "NO .tinkla_splash (splash reboot not yet done)"
echo "--- boot history (count + timing of reboots) ---"
sudo journalctl --list-boots 2>/dev/null | tail -12
echo "--- updater staging ---"
ls -la /data/safe_staging/ 2>/dev/null
ls -la /data/safe_staging/finalized/.overlay_consistent 2>/dev/null || echo "no finalized overlay"
echo "--- agnos/updater/swap/reboot this boot ---"
sudo journalctl -b 0 2>/dev/null | grep -iE 'agnos|updater|swap|abctl|finaliz|overlay|reboot|panic|watchdog' | tail -60
echo "--- end of PREVIOUS boot (right before the reboot) ---"
sudo journalctl -b -1 -n 80 2>/dev/null

echo; echo "######## D. PARAMS (the working config) ########"
for f in TinklaAPForceFingerprint GitBranch GitCommit GitRemote Version \
         UpdaterState LastUpdateTime UpdateAvailable UpdateFailedCount \
         DongleId IsOnroad OpenpilotEnabledToggle CompletedTrainingVersion; do
  echo "$f = $(cat "$PARAMS_DIR/$f" 2>/dev/null)"
done
echo "--- all Tinkla* params ---"
for f in $(ls "$PARAMS_DIR" 2>/dev/null | grep -i tinkla); do
  echo "$f = $(cat "$PARAMS_DIR/$f" 2>/dev/null)"
done

echo; echo "######## E. RUNNING / PANDA / CAR / FINGERPRINT ########"
ps aux 2>/dev/null | grep -iE 'manager|controlsd|card|pandad|boardd|selfdrived|ui' | grep -v grep
echo "--- panda/car/fingerprint from this boot's log ---"
sudo journalctl -b 0 2>/dev/null | grep -iE 'panda|fingerprint|EPAS|tesla|controlsAllowed|safetyModel|recognized' | tail -40
echo "--- launch_log tail ---"
tail -80 /tmp/launch_log 2>/dev/null
} 2>&1 | tee "$OUT"

echo; echo "DONE -> $OUT"
echo "Backups: /data/params_backup_working.tar.gz  /data/working_commit.txt"
echo "Pull them off:  scp comma@<ip>:$OUT .   then commit under v6/"
