#!/usr/bin/env bash
# Runs every leg of the 2026-09-25 lag measurement, sequentially (never two emulators at
# once, so legs do not load each other). Usage: run_legs.sh <romdir> <outdir> <tag>
# Writes <outdir>/<tag>.meta with each leg's exit code and a finished=<legs> stamp.
cd "$(dirname "$0")/../../.." || exit 2
PROBE=docs/research/2026-09-25-s4-lag/lag_flythrough_probe.py
R="$1"; O="$2"; T="$3"
M="$O/$T.meta"
{ date -u; cat /proc/loadavg; } > "$M"
N=0
leg() {  # name rom lst mode frames dirs
    python3 "$PROBE" --rom "$R/$2" --lst "$R/$3" --mode "$4" --frames "$5" --dirs "$6" \
        --stall-stop 60 --out "$O/${T}_$1.json" > "$O/${T}_$1.txt" 2>&1
    echo "$1 rc=$? loadavg=$(cat /proc/loadavg)" >> "$M"
    N=$((N + 1))
}
# physics (all four ROMs): hold right, tap C every 45 frames
leg clipdbg_run   s4.s2clip.debug.bin s4.s2clip.debug.lst run 3000 right
leg clip_run      s4.s2clip.bin       s4.s2clip.lst       run 3000 right
leg dbg_run       s4.debug.bin        s4.debug.lst        run 3000 right
leg rel_run       s4.bin              s4.lst              run 3000 right
# debug free flight (the two DEBUG ROMs): right, down, diagonal
leg clipdbg_fly   s4.s2clip.debug.bin s4.s2clip.debug.lst fly 2000 right
leg clipdbg_down  s4.s2clip.debug.bin s4.s2clip.debug.lst fly 2000 down
leg clipdbg_diag  s4.s2clip.debug.bin s4.s2clip.debug.lst fly 2000 right,down
leg dbg_fly       s4.debug.bin        s4.debug.lst        fly 2000 right
leg dbg_down      s4.debug.bin        s4.debug.lst        fly 2000 down
leg dbg_diag      s4.debug.bin        s4.debug.lst        fly 2000 right,down
{ date -u; echo "finished=$N"; } >> "$M"
