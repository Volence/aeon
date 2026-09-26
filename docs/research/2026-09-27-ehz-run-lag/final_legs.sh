#!/bin/bash
# final_legs.sh <romdir> <outdir> : the parcel's whole before/after leg set on one build set.
#   <romdir> holds plain/debug.{bin,lst} (S2 clip) and cplain/cdebug.{bin,lst} (canonical OJZ),
#   as ~/ehzlag/build4.sh writes them. Every leg runs with --coverage and --dump.
#   Clip:      run + spin (plain, debug; spawn -> player x 5850, EHZ), fly diag/right/down (debug).
#   Canonical: fly diag/right/down (debug), run (plain, debug; jump every 45 ticks, 1800 frames).
#   A line per leg in <outdir>/legs.meta (rc + loadavg), last line finished=<n>.
HERE=$(cd "$(dirname "$0")" && pwd)
RD=$1; OUT=$2; mkdir -p "$OUT"
export TMPDIR=/home/volence/.cache/aeon-tmp
n=0
leg() {  # rom name args...
  local rom=$1 nm=$2; shift 2
  local la; la=$(cut -d' ' -f1 /proc/loadavg)
  timeout 900 python3 "$HERE/ehz_run_probe.py" --rom "$RD/$rom.bin" --lst "$RD/$rom.lst" --coverage --dump \
      --out "$OUT/$nm.json" "$@" > "$OUT/$nm.txt" 2>&1
  echo "$nm rc=$? load=$la->$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT/legs.meta"
  n=$((n+1))
}
for sh in plain debug; do
  leg $sh ${sh}_run  --mode auto --triggers 1330,4620 --stop-x 5850 --frames 3000
  leg $sh ${sh}_spin --mode auto --triggers 1330,4620 --spin-triggers 1700,3200 --stop-x 5850 --frames 3000
done
leg debug debug_diag  --mode fly --dirs right,down --stop-x 99999 --frames 1100
leg debug debug_right --mode fly --dirs right --stop-x 99999 --frames 1100
leg debug debug_down  --mode fly --dirs down --stop-x 99999 --frames 400
leg cdebug cdebug_diag  --mode fly --dirs right,down --stop-x 99999 --stall-stop 60 --frames 700
leg cdebug cdebug_right --mode fly --dirs right --stop-x 99999 --stall-stop 60 --frames 700
leg cdebug cdebug_down  --mode fly --dirs down --stop-x 99999 --stall-stop 60 --frames 700
leg cplain cplain_run --mode run --stop-x 99999 --stall-stop 300 --frames 1800
leg cdebug cdebug_run --mode run --stop-x 99999 --stall-stop 300 --frames 1800
echo "finished=$n" >> "$OUT/legs.meta"
