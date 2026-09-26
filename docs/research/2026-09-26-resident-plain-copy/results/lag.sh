#!/bin/bash
# usage: lag.sh <romdir> <outdir> <set: canon|clip>
# The perf survey's legs (run_survey.sh), same drives and frame caps, WITHOUT --profile
# (the profiler is emulator-side and does not change lag counts; it only slows the run).
export TMPDIR=/home/volence/.cache/aeon_rpc_tmp
W=/home/volence/sonic_hacks/aeon/.claude/worktrees/agent-a3972eb4efa965fff
cd "$W" || exit 9
P=docs/research/2026-09-25-perf-survey/leg_probe.py
R="$1"; O="$2"; SET="$3"; mkdir -p "$O"
M="$O/$SET.meta"
{ date -u; echo "set=$SET romdir=$R"; cat /proc/loadavg; } > "$M"
N=0
leg() {
    local name=$1 rom=$2 lst=$3 mode=$4 dirs=$5; shift 5
    python3 "$P" --rom "$R/$rom" --lst "$R/$lst" --mode "$mode" --dirs "$dirs" \
        --out "$O/${name}.json" "$@" > "$O/${name}.txt" 2>&1
    echo "$name rc=$? loadavg=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$M"
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
    leg clipdbg_cpzdown $C $CL fly right --then-dirs down --then-at-x 14400 --frames 2000
    leg clipdbg_cpzdiag $C $CL fly right --then-dirs right,down --then-at-x 14400 --frames 2000
    leg clipdbg_run   $C $CL run  right      --frames 3000
    leg clip_run   s4.s2clip.bin s4.s2clip.lst run  right --frames 3000
    ;;
esac
{ date -u; echo "finished=$N"; } >> "$M"
