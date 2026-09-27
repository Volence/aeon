#!/bin/bash
# fall_legs.sh <rom-stem> <outdir>: the OJZ act 1 FALL legs, with the fill's edges (--cache) and
#   the picture/coverage dump (--dump), on one DEBUG ROM. The legs are ojz-feel's (legs.sh):
#   fall_down     from the top of the act, no input: a straight fall to the act floor
#   fall_diag     the same fall holding right
#   spawn_right   run right from spawn off section 0's edge into the ~5,300 px diagonal fall
#   slab_spin     spindash right off section 0's lower slab (the worst lag leg before)
# One JSON + txt per leg, a line per leg in <outdir>/legs.meta (rc + loadavg), last line
# finished=<n>. Probe: docs/research/2026-09-27-ojz-feel/ojz_feel_probe.py (imported, not copied).
HERE=$(cd "$(dirname "$0")" && pwd)
PROBE="$HERE/../2026-09-27-ojz-feel/ojz_feel_probe.py"
R=$1; OUT=$2; shift 2; mkdir -p "$OUT"
export TMPDIR=/home/volence/.cache/aeon-tmp
n=0
leg() {
  local nm=$1 sc=$2; shift 2
  local la; la=$(cut -d' ' -f1 /proc/loadavg)
  timeout 1800 python3 "$PROBE" --rom "$R.bin" --lst "$R.lst" --script "$sc" --cache --dump \
      --out "$OUT/$nm.json" "$@" > "$OUT/$nm.txt" 2>&1
  echo "$nm rc=$? load=$la->$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT/legs.meta"
  n=$((n+1))
}
: > "$OUT/legs.meta"
leg fall_down   "warp:3000,100;hold::500" "$@"
leg fall_diag   "warp:1500,100;hold:right:500" "$@"
leg spawn_right "auto:right:2500" "$@"
leg slab_spin   "warp:900,830;spindash:right:150;hold:right:400" "$@"
echo "finished=$n" >> "$OUT/legs.meta"
