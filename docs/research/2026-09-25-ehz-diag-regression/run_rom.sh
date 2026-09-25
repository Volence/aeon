#!/usr/bin/env bash
# run_rom.sh <name> <tag> [extra leg_probe args...] : diag leg on runs/<name>.bin (+ .lst), no copy.
N=$1; T=$2; shift 2
SP=/tmp/claude-1000/-home-volence-sonic-hacks-aeon/49f49cb1-d570-40ef-a8a2-ffb2dc8e8dbc/scratchpad
R=$SP/runs
M=$R/${N}_${T}.meta
{ date -u; echo "rom=$N tag=$T args=$*"; cat /proc/loadavg; } > "$M"
find "$SP/probe" -name __pycache__ -type d -prune -exec rm -rf {} +
python3 "$SP/probe/perf/leg_probe.py" --rom "$R/${N}.bin" --lst "$R/${N}.lst" --mode fly --dirs right,down \
    --frames 2000 --out "$R/${N}_${T}.json" "$@" > "$R/${N}_${T}.txt" 2>&1
echo "leg rc=$? loadavg=$(cat /proc/loadavg)" >> "$M"
{ date -u; echo "finished=1"; } >> "$M"
