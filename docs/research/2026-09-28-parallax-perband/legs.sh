#!/bin/bash
# legs.sh <romdir> <outdir> [leg ...] : the PERF-EHZ-RUN-LAG leg set (docs/research/2026-09-27-
#   ehz-run-lag/final_legs.sh, the same drives and flags) on one build4.sh output dir, with the
#   profiler ARMED (--profile, callers lens, re-armed per 1024 px of camera x) so every leg also
#   yields Parallax_* cycles per tick. Every leg runs with --coverage and --dump (the parallax
#   output bytes per on-time tick, for dumpcmp's identity check).
#   <romdir> holds plain/debug.{bin,lst} (S2 clip) and cplain/cdebug.{bin,lst} (canonical OJZ).
#   With leg names given, runs only those. One line per leg in <outdir>/legs.meta (rc +
#   loadavg); the last line is finished=<n>.
HERE=$(cd "$(dirname "$0")" && pwd)
PROBE="$HERE/../2026-09-27-ehz-run-lag/ehz_run_probe.py"
RD=$1; OUT=$2; shift 2; mkdir -p "$OUT"
WANT=" $* "
export TMPDIR=/home/volence/.cache/aeon-tmp
export RUNPROBE_SOCK_DIR=$HOME/pxperf/sock
n=0
leg() {  # rom name args...
  local rom=$1 nm=$2; shift 2
  if [ "$WANT" != "  " ] && [ "${WANT#* $nm }" = "$WANT" ]; then return; fi
  local la; la=$(cut -d' ' -f1 /proc/loadavg)
  timeout 1800 python3 "$PROBE" --rom "$RD/$rom.bin" --lst "$RD/$rom.lst" --coverage --dump --profile \
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
