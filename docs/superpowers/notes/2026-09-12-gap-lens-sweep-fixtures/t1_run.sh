#!/bin/bash
# usage: t1_run.sh <copy-name> <label> [--no-cache]
# Runs the copy's regenerate-level.sh with per-run pycache prefix, stamps finished=<rc>,
# then snapshots the outputs under $S/snap_<label>.
S=$(cat /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0f66baa9-0a26-4066-a435-9516186c96f8/scratchpad/t1_S_path)
COPY="$1"; LABEL="$2"; shift 2
cd "$S/$COPY" || exit 9
export EMPYREAN_SUITE_ROOT=/home/volence/sonic_hacks
export AEON_SONIC_HACK_DIR=/home/volence/sonic_hacks/sonic_hack
export AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm
PYC=$(mktemp -d "$S/pyc.XXXXXX")
export PYTHONPYCACHEPREFIX="$PYC"
LOG="$S/run_$LABEL.log"
{ echo "start_utc=$(date -u +%FT%TZ)"; TZ=UTC uptime; } > "$LOG"
T0=$(date +%s.%N)
bash tools/regenerate-level.sh "$@" >> "$LOG" 2>&1
rc=$?
T1=$(date +%s.%N)
echo "finished=$rc elapsed=$(python3 -c "print(round($T1-$T0,2))")s end_utc=$(date -u +%FT%TZ)" >> "$LOG"
TZ=UTC uptime >> "$LOG"
mkdir -p "$S/snap_$LABEL"
cp -a games/sonic4/data/generated "$S/snap_$LABEL/generated"
cp -a games/sonic4/data/collision "$S/snap_$LABEL/collision"
cp -a games/sonic4/data/editor_sources.stamp.json "$S/snap_$LABEL/"
cp -a games/sonic4/data/editor "$S/snap_$LABEL/editor"
echo "pyc_files_written=$(find "$PYC" -name '*.pyc' | wc -l)" >> "$LOG"
tail -4 "$LOG"
