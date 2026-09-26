#!/bin/bash
# release_legs.sh <rom-stem> <outdir>: the spawn legs of legs.sh on a RELEASE build (no warp
# mailbox, no free flight, no B press). A settle:120 prefix puts both shapes on the spawn floor
# (the DEBUG player leaves free flight in the air at y 256 and lands), so DEBUG and release run
# the same path from the same state: pass a DEBUG stem too and it runs the identical scripts.
HERE=$(cd "$(dirname "$0")" && pwd)
R=$1; OUT=$2; mkdir -p "$OUT"; : > "$OUT/legs.meta"
export TMPDIR=/home/volence/.cache/aeon-tmp
n=0
leg() {
  timeout 900 python3 "$HERE/ojz_feel_probe.py" --rom "$R.bin" --lst "$R.lst" --script "$2" \
      --out "$OUT/$1.json" > "$OUT/$1.txt" 2>&1
  echo "$1 rc=$?" >> "$OUT/legs.meta"; n=$((n+1))
}
leg spawn_right   "settle:120;auto:right:2500"
leg spawn_spin    "settle:120;spindash:right:150;auto:right:1500"
leg spawn_jumprun "settle:120;jumps:right:45:45"
leg sec0_left     "settle:120;hold:left:900"
echo "finished=$n" >> "$OUT/legs.meta"
