#!/usr/bin/env bash
# General-patch-loop parcel (2026-09-27): the survey's legs on one ROM, sequentially
# (one headless emulator at a time). Legs are the survey's own argv (stub_legs.sh /
# run_survey.sh), run through gpl_probe.py (socket off /tmp, nothing else changed).
# Usage: gpl_legs.sh <rom> <lst> <outdir> <tag> <legs, comma list>
#   legs: fly down diag run spin cpzdown cpzdiag cpzband   (+ "P" suffix = profiled, e.g. cpzdownP)
# Writes <outdir>/<tag>.meta with each leg's rc + loadavg and a finished=<n> stamp.
# A leg without a .json is DID NOT RUN, never a zero.
cd "$(dirname "$0")/../../.." || exit 2
P=docs/research/2026-09-27-general-patch-loop/gpl_probe.py
ROM="$1"; LST="$2"; O="$3"; T="$4"; LEGS="$5"
mkdir -p "$O"
M="$O/$T.meta"
{ date -u; echo "rom=$ROM"; uptime; } > "$M"
N=0
for L in ${LEGS//,/ }; do
    prof=()
    base=$L
    if [[ "$L" == *P ]]; then base=${L%P}; prof=(--profile); fi
    case "$base" in
        fly)  a=(--mode fly --dirs right --frames 2000 --read-at-end PageCache_Direct_Map${GPL_READ:+,$GPL_READ}) ;;
        down) a=(--mode fly --dirs down --frames 2000 --read-at-end PageCache_Direct_Map${GPL_READ:+,$GPL_READ}) ;;
        diag) a=(--mode fly --dirs right,down --frames 2000 --read-at-end PageCache_Direct_Map${GPL_READ:+,$GPL_READ}) ;;
        run)  a=(--mode run --dirs right --frames 3000 --read-at-end PageCache_Direct_Map${GPL_READ:+,$GPL_READ}) ;;
        spin) a=(--mode spin --dirs right --frames 3000 --read-at-end PageCache_Direct_Map${GPL_READ:+,$GPL_READ}) ;;
        cpzdown) a=(--mode fly --dirs right --then-dirs down --then-at-x 14400 --frames 2000
                    --read-at-end PageCache_Direct_Map${GPL_READ:+,$GPL_READ}) ;;
        cpzdiag) a=(--mode fly --dirs right --then-dirs right,down --then-at-x 14400 --frames 2000
                    --read-at-end PageCache_Direct_Map${GPL_READ:+,$GPL_READ}) ;;
        # the survey's "CPZ painted rows" window: profile 150 frames from 3 after the
        # switch (switch at frame 893 on this parcel's base; the .txt notes print it)
        cpzband) a=(--mode fly --dirs right --then-dirs down --then-at-x 14400 --frames 2000
                    --profile-window 896,1046 --read-at-end PageCache_Direct_Map${GPL_READ:+,$GPL_READ}) ;;
        *) echo "unknown leg $L" >> "$M"; continue ;;
    esac
    if [[ ${#prof[@]} -gt 0 && ( "$base" == cpzdown || "$base" == cpzdiag ) ]]; then
        prof+=(--profile-from-switch)
    fi
    python3 "$P" --rom "$ROM" --lst "$LST" "${a[@]}" "${prof[@]}" --out "$O/${T}_$L.json" > "$O/${T}_$L.txt" 2>&1
    echo "$L rc=$? loadavg=$(cat /proc/loadavg)" >> "$M"
    N=$((N + 1))
done
{ date -u; uptime; echo "finished=$N"; } >> "$M"
