#!/usr/bin/env bash
# Perf survey 2026-09-25: run a set of leg_probe legs sequentially (one emulator at a time).
# Usage: run_survey.sh <romdir> <outdir> <tag> <set>
#   set = canon | clip   (which ROMs/legs; see below)
# Writes <outdir>/<tag>.meta: start date + loadavg, one line per leg with rc + loadavg,
# and a finished=<legs run> stamp. A leg without a .json is DID NOT RUN, never a zero.
cd "$(dirname "$0")/../../.." || exit 2
P=docs/research/2026-09-25-perf-survey/leg_probe.py
R="$1"; O="$2"; T="$3"; SET="$4"
M="$O/$T.meta"
{ date -u; echo "set=$SET"; cat /proc/loadavg; } > "$M"
N=0
leg() {  # name rom lst mode dirs [extra args...]
    local name=$1 rom=$2 lst=$3 mode=$4 dirs=$5; shift 5
    python3 "$P" --rom "$R/$rom" --lst "$R/$lst" --mode "$mode" --dirs "$dirs" --profile \
        --out "$O/${T}_${name}.json" "$@" > "$O/${T}_${name}.txt" 2>&1
    echo "$name rc=$? loadavg=$(cat /proc/loadavg)" >> "$M"
    N=$((N + 1))
}
case "$SET" in
canon)
    leg dbg_fly   s4.debug.bin s4.debug.lst fly  right      --frames 2000
    leg dbg_down  s4.debug.bin s4.debug.lst fly  down       --frames 2000
    leg dbg_diag  s4.debug.bin s4.debug.lst fly  right,down --frames 2000
    leg dbg_run   s4.debug.bin s4.debug.lst run  right      --frames 3000
    leg dbg_spin  s4.debug.bin s4.debug.lst spin right      --frames 3000
    leg rel_run   s4.bin       s4.lst       run  right      --frames 3000
    leg rel_spin  s4.bin       s4.lst       spin right      --frames 3000
    ;;
clip)
    C=s4.s2clip.debug.bin; CL=s4.s2clip.debug.lst
    leg clipdbg_fly   $C $CL fly  right      --frames 2000
    leg clipdbg_down  $C $CL fly  down       --frames 2000
    leg clipdbg_diag  $C $CL fly  right,down --frames 2000
    leg clipdbg_run   $C $CL run  right      --frames 3000
    leg clipdbg_spin  $C $CL spin right      --frames 3000
    # NEW: fly right along the top into Chemical Plant, then straight down through its
    # painted rows (the prior study never moved vertically inside CPZ).
    leg clipdbg_cpzdown $C $CL fly right --then-dirs down --then-at-x 14400 \
        --profile-from-switch --frames 2000
    leg clipdbg_cpzdiag $C $CL fly right --then-dirs right,down --then-at-x 14400 \
        --profile-from-switch --frames 2000
    leg clip_run   s4.s2clip.bin s4.s2clip.lst run  right --frames 3000
    leg clip_spin  s4.s2clip.bin s4.s2clip.lst spin right --frames 3000
    ;;
*) echo "unknown set $SET" >> "$M"; exit 2 ;;
esac
{ date -u; echo "finished=$N"; } >> "$M"
