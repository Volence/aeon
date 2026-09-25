#!/usr/bin/env bash
# Perf survey: the four DEBUG legs (fly right/down/diag, physics run) on one ROM, no profile.
# Usage: stub_legs.sh <rom> <lst> <outdir> <tag> [legs: fly,down,diag,run,spin]
# Meta + finished=<n> stamp as run_survey.sh.
cd "$(dirname "$0")/../../.." || exit 2
P=docs/research/2026-09-25-perf-survey/leg_probe.py
ROM="$1"; LST="$2"; O="$3"; T="$4"; LEGS="${5:-fly,down,diag,run}"
M="$O/$T.meta"
{ date -u; echo "rom=$ROM"; cat /proc/loadavg; } > "$M"
N=0
for L in ${LEGS//,/ }; do
    case "$L" in
        fly)  a=(--mode fly --dirs right --frames 2000) ;;
        down) a=(--mode fly --dirs down --frames 2000) ;;
        diag) a=(--mode fly --dirs right,down --frames 2000) ;;
        run)  a=(--mode run --dirs right --frames 3000) ;;
        spin) a=(--mode spin --dirs right --frames 3000) ;;
        cpzdown) a=(--mode fly --dirs right --then-dirs down --then-at-x 14400 --frames 2000) ;;
        cpzdiag) a=(--mode fly --dirs right --then-dirs right,down --then-at-x 14400 --frames 2000) ;;
        *) echo "unknown leg $L" >> "$M"; continue ;;
    esac
    python3 "$P" --rom "$ROM" --lst "$LST" "${a[@]}" --out "$O/${T}_$L.json" > "$O/${T}_$L.txt" 2>&1
    echo "$L rc=$? loadavg=$(cat /proc/loadavg)" >> "$M"
    N=$((N + 1))
done
{ date -u; echo "finished=$N"; } >> "$M"
