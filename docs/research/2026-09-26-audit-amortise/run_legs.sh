#!/usr/bin/env bash
# Audit-amortise 2026-09-26: the perf survey's leg set on a DEBUG canonical + DEBUG clip
# ROM pair, one headless emulator at a time, reading Page_Audit_Late after every leg.
# Usage: run_legs.sh <romdir holding s4.debug.{bin,lst} + s4.s2clip.debug.{bin,lst}> <outdir> <tag>
# Same leg argv as ../2026-09-25-perf-survey/stub_legs.sh. Writes <outdir>/<tag>.meta with
# rc + loadavg per leg and a finished=<n> stamp. Summarise with
#   python3 ../2026-09-25-perf-survey/summarise_survey.py <outdir> <tag> canon_fly,...
# Put TMPDIR under $HOME: /tmp is over quota on this box (2026-09-26).
H="$(cd "$(dirname "$0")" && pwd)"
P="$H/lp_late.py"
R="$1"; O="$2"; T="$3"; mkdir -p "$O"
M="$O/$T.meta"
{ date -u; uptime; } > "$M"
N=0
run() {  # run <rom> <lst> <name> args...
    local rom=$1 lst=$2 name=$3; shift 3
    python3 "$P" --rom "$rom" --lst "$lst" "$@" --read-at-end Page_Audit_Late \
        --out "$O/${T}_$name.json" > "$O/${T}_$name.txt" 2>&1
    echo "$name rc=$? loadavg=$(cat /proc/loadavg)" >> "$M"
    N=$((N + 1))
}
C=$R/s4.debug.bin; CL=$R/s4.debug.lst
run $C $CL canon_fly  --mode fly --dirs right --frames 2000
run $C $CL canon_down --mode fly --dirs down --frames 2000
run $C $CL canon_diag --mode fly --dirs right,down --frames 2000
run $C $CL canon_run  --mode run --dirs right --frames 3000
C=$R/s4.s2clip.debug.bin; CL=$R/s4.s2clip.debug.lst
run $C $CL clip_fly  --mode fly --dirs right --frames 2000
run $C $CL clip_down --mode fly --dirs down --frames 2000
run $C $CL clip_diag --mode fly --dirs right,down --frames 2000
run $C $CL clip_cpzdown --mode fly --dirs right --then-dirs down --then-at-x 14400 --frames 2000
run $C $CL clip_cpzdiag --mode fly --dirs right --then-dirs right,down --then-at-x 14400 --frames 2000
{ date -u; uptime; echo "finished=$N"; } >> "$M"
