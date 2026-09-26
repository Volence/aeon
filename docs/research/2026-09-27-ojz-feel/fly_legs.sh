#!/bin/bash
# fly_legs.sh <romdir> <outdir> NAME...: the EHZ-run-lag parcel's canonical DEBUG fly legs
# (ehz_run_probe.py --mode fly, --coverage) over <romdir>/NAME.{bin,lst}: diagonal, right, down,
# 700 frames each. One line per leg in <outdir>/NAME/fly.meta.
HERE=$(cd "$(dirname "$0")" && pwd)
P="$HERE/../2026-09-27-ehz-run-lag/ehz_run_probe.py"
RD=$1; OUT=$2; shift 2
export TMPDIR=/home/volence/.cache/aeon-tmp
for v in "$@"; do
  mkdir -p "$OUT/$v"; : > "$OUT/$v/fly.meta"
  for leg in "diag right,down" "right right" "down down"; do
    set -- $leg
    nm=$1; dirs=$2
    timeout 900 python3 "$P" --rom "$RD/$v.bin" --lst "$RD/$v.lst" --mode fly --dirs "$dirs" \
        --stop-x 99999 --stall-stop 60 --frames 700 --coverage --out "$OUT/$v/fly_$nm.json" > "$OUT/$v/fly_$nm.txt" 2>&1
    echo "fly_$nm rc=$? $(grep -h 'IN MOTION' "$OUT/$v/fly_$nm.txt" | cut -c1-60) $(grep -h COVERAGE "$OUT/$v/fly_$nm.txt")" >> "$OUT/$v/fly.meta"
  done
  echo "finished=$v" >> "$OUT/$v/fly.meta"
done
