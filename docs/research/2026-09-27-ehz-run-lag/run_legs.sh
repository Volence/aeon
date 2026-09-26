#!/bin/bash
# run_legs.sh <romdir> <outdir> [debug|plain|both]
#   <romdir> holds plain.bin/plain.lst and/or debug.bin/debug.lst (clip shapes).
#   Runs the EHZ leg set on each shape, one headless emulator at a time, foreground-safe.
#   Legs: run (auto, grounded jumps at EHZ's missing bridges, spawn -> player x 5850),
#         spin (the same, plus spindashes at x 1700 and 3200),
#         diag (DEBUG only: the perf survey's fly right+down leg, EHZ band = cam y < 1024).
#   Every leg's stdout goes to <outdir>/<shape>_<leg>.txt, its JSON beside it; a .meta line
#   per leg carries rc and loadavg; the last line of <outdir>/legs.meta is finished=<n>.
HERE=$(cd "$(dirname "$0")" && pwd)
RD=$1; OUT=$2; WHICH=${3:-both}
mkdir -p "$OUT"
export TMPDIR=/home/volence/.cache/aeon-tmp
n=0
leg() {  # shape name args...
  local sh=$1 nm=$2; shift 2
  local la; la=$(cut -d' ' -f1 /proc/loadavg)
  timeout 900 python3 "$HERE/ehz_run_probe.py" --rom "$RD/$sh.bin" --lst "$RD/$sh.lst" \
      --out "$OUT/${sh}_$nm.json" "$@" > "$OUT/${sh}_$nm.txt" 2>&1
  local rc=$?
  echo "$sh $nm rc=$rc load=$la->$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT/legs.meta"
  n=$((n+1))
}
for sh in plain debug; do
  [ "$WHICH" = both ] || [ "$WHICH" = "$sh" ] || continue
  [ -f "$RD/$sh.bin" ] || { echo "$sh MISSING $RD/$sh.bin" >> "$OUT/legs.meta"; continue; }
  leg $sh run  --mode auto --triggers 1330,4620 --stop-x 5850 --frames 3000
  leg $sh spin --mode auto --triggers 1330,4620 --spin-triggers 1700,3200 --stop-x 5850 --frames 3000
  if [ $sh = debug ]; then
    la=$(cut -d' ' -f1 /proc/loadavg)
    timeout 900 python3 "$HERE/../2026-09-25-perf-survey/leg_probe.py" --rom "$RD/debug.bin" \
        --lst "$RD/debug.lst" --mode fly --dirs right,down --frames 2000 \
        --out "$OUT/debug_diag.json" > "$OUT/debug_diag.txt" 2>&1
    echo "debug diag rc=$? load=$la->$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT/legs.meta"
    n=$((n+1))
  fi
done
echo "finished=$n" >> "$OUT/legs.meta"
