#!/usr/bin/env bash
# run_leg.sh <label> <tag> [extra leg_probe args...]
# Copies the built clip DEBUG ROM+lst of point <label> to runs/, then runs the survey's
# diagonal leg (fly right,down, --frames 2000) with the survey's probe (run-unique copy).
L=$1; T=$2; shift 2
SP=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/49f49cb1-d570-40ef-a8a2-ffb2dc8e8dbc/scratchpad
W=/home/volence/sonic_hacks/.aeon-ehzbis-$L
R=$SP/runs
M=$R/${L}_${T}.meta
{ date -u; echo "label=$L tag=$T args=$*"; cat /proc/loadavg; } > "$M"
cp "$W/s4.s2clip.debug.bin" "$R/${L}.bin" && cp "$W/s4.s2clip.debug.lst" "$R/${L}.lst" || { echo "copy failed" >> "$M"; echo "finished=0" >> "$M"; exit 2; }
find "$SP/probe" -name __pycache__ -type d -prune -exec rm -rf {} +
python3 "$SP/probe/perf/leg_probe.py" --rom "$R/${L}.bin" --lst "$R/${L}.lst" --mode fly --dirs right,down \
    --frames 2000 --out "$R/${L}_${T}.json" "$@" > "$R/${L}_${T}.txt" 2>&1
echo "leg rc=$? loadavg=$(cat /proc/loadavg)" >> "$M"
{ date -u; echo "finished=1"; } >> "$M"
