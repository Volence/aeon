#!/bin/bash
# clip_fall_legs.sh <rom-stem> <outdir>: the S2 clip's (S2CLIP=s2_ehz_cpz, DEBUG) longest falls,
#   found by clip_fall_scan.py on the base clip ROM (drops from y 64 every 256 px of X):
#   clip_pit      x 4768: an Emerald Hill pit, ~5,900 px to the act's bottom bound
#   clip_pit_diag the same pit holding right
#   clip_cpz      x 15264: Chemical Plant's longest landing fall, ~1,070 px
# With --cache and --dump, as fall_legs.sh. A line per leg in <outdir>/legs.meta, finished=<n>.
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
leg clip_pit      "warp:4768,64;hold::500" "$@"
leg clip_pit_diag "warp:4768,64;hold:right:500" "$@"
leg clip_cpz      "warp:15264,64;hold::200" "$@"
echo "finished=$n" >> "$OUT/legs.meta"
