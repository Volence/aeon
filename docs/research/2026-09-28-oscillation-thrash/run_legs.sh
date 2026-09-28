#!/bin/bash
# run_legs.sh <romdir> <outdir> : the oscillation-thrash leg set on one build set, one headless
# emulator at a time. <romdir> holds cplain/cdebug (canonical OJZ) and plain/debug (S2 clip)
# .{bin,lst}, as .perf/build4.sh writes them. A line per leg in <outdir>/legs.meta (rc +
# loadavg); the last line is finished=<legs run>. A leg with no .json is DID NOT RUN.
HERE=$(cd "$(dirname "$0")" && pwd)
RD=$1; OUT=$2; mkdir -p "$OUT"
export TMPDIR=${TMPDIR:-/home/volence/.cache/aeon-tmp}
P="$HERE/thrash_probe.py"
: > "$OUT/legs.meta"
n=0
leg() {  # rom name [env=val ...] -- args...
  local rom=$1 nm=$2; shift 2
  # ONLY_LEGS (env, an ERE): run only the legs whose name matches it
  if [ -n "$ONLY_LEGS" ] && ! [[ $nm =~ $ONLY_LEGS ]]; then return; fi
  if [ ! -f "$RD/$rom.bin" ]; then echo "$nm DID NOT RUN (no $RD/$rom.bin)" >> "$OUT/legs.meta"; return; fi
  local envs=()
  while [ "$1" != "--" ]; do envs+=("$1"); shift; done; shift
  local la; la=$(cut -d' ' -f1 /proc/loadavg)
  env "${envs[@]}" timeout 1200 python3 "$P" --rom "$RD/$rom.bin" --lst "$RD/$rom.lst" --coverage \
      --out "$OUT/$nm.json" "$@" > "$OUT/$nm.txt" 2>&1
  echo "$nm rc=$? load=$la->$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT/legs.meta"
  n=$((n+1))
}
# --- canonical OJZ ---
# controls: straight flight (DEBUG) — the camera never reverses
leg cdebug c_fly_right -- --mode fly --dirs right --stop-x 99999 --stall-stop 60 --frames 700
leg cdebug c_fly_down  -- --mode fly --dirs down  --stop-x 99999 --stall-stop 60 --frames 700
# the survey's subject: physics run (jump every 45 ticks); on this tree it bounces at x ~1000
leg cplain c_run -- --mode run --stop-x 99999 --stall-stop 300 --frames 1800
leg cdebug c_run_dbg -- --mode run --stop-x 99999 --stall-stop 300 --frames 1800
# synthetic oscillation in free flight (camera path fixed by input): after 40 ticks right,
# alternate right/left every K ticks (16 px/tick: K=4 -> 64 px, K=8 -> 128 px swing)
leg cdebug c_osc_h4  THRASH_OSC_AFTER=right:40 THRASH_OSC=right/left:4 -- --mode fly --dirs right --stop-x 99999 --stall-stop 99999 --frames 700
leg cdebug c_osc_h8  THRASH_OSC_AFTER=right:40 THRASH_OSC=right/left:8 -- --mode fly --dirs right --stop-x 99999 --stall-stop 99999 --frames 700
leg cdebug c_osc_d4  THRASH_OSC_AFTER=right,down:40 THRASH_OSC=right,down/left,up:4 -- --mode fly --dirs right --stop-x 99999 --stall-stop 99999 --frames 700
# --- S2 clip (Emerald Hill) ---
leg debug e_fly_right -- --mode fly --dirs right --stop-x 99999 --frames 1100
leg plain e_run     -- --mode auto --triggers 1330,4620 --stop-x 5850 --frames 3000
leg debug e_run_dbg -- --mode auto --triggers 1330,4620 --stop-x 5850 --frames 3000
# the dead end: warp to (6300,690) (DEBUG only), then auto-run (jump when stuck) for 1500 frames
leg debug e_deadend_dbg -- --mode auto --triggers "" --warp 6300,690 --stop-x 99999 --stall-stop 99999 --frames 1500
# the pit under the missing bridge at x 6040: reachable in RELEASE (no warp); run past 5850
leg plain e_pit     -- --mode auto --triggers 1330,4620 --stop-x 99999 --stall-stop 99999 --frames 3000
leg debug e_pit_dbg -- --mode auto --triggers 1330,4620 --stop-x 99999 --stall-stop 99999 --frames 3000
leg debug e_osc_h4  THRASH_OSC_AFTER=right:200 THRASH_OSC=right/left:4 -- --mode fly --dirs right --stop-x 99999 --stall-stop 99999 --frames 900
leg debug e_osc_d4  THRASH_OSC_AFTER=right,down:40 THRASH_OSC=right,down/left,up:4 -- --mode fly --dirs right --stop-x 99999 --stall-stop 99999 --frames 900
echo "finished=$n" >> "$OUT/legs.meta"
