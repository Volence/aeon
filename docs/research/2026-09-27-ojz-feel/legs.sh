#!/bin/bash
# legs.sh <rom-stem> <outdir> [extra probe args]: the OJZ feel leg set on one DEBUG ROM.
#   <rom-stem>.bin/.lst is a canonical OJZ DEBUG build. One JSON + txt per leg, a line per leg
#   in <outdir>/legs.meta (rc + loadavg), last line finished=<n>.
# The legs are the ways a player covers act 1 (docs/research/2026-09-27-ojz-feel.md, "Legs"):
#   spawn_right   run right from spawn with stuck-hops: section 0, the drop off its end, the
#                 ~5,300 px diagonal fall to the act floor, then the floor run to the right edge
#   floor_left    from the floor's right end, run left along the act floor to the left edge
#   floor_shuttle on the act floor mid-act: right 90 ticks / left 90 ticks, x10 (reversing)
#   floor_spin    spindash right then left along the act floor
#   floor_jumps   jumps at speed along the act floor (one every 40 ticks)
#   fall_down     from the top of the act, no input: a straight 5,700 px fall
#   fall_diag     the same fall holding right
#   sec0_left     from spawn, hold left into section 0's springs (vertical bouncing)
#   sec0_loop     spindash right into section 0's loop from its run-up
#   sec0_shuttle  reversing on section 0's floor
#   spawn_spin    spindash from spawn, then run right with stuck-hops
#   spawn_jumprun hold right, jump every 45 ticks (the canonical run leg's rhythm)
#   fall_diag_l   the top-of-act fall holding LEFT from the right side
#   fall_diag_mid the top-of-act fall holding right from mid-act
#   fall_diag_rev the top-of-act fall, reversing right/left/right mid-air
#   slab_spin     spindash right off section 0's lower slab (x ~10 px/tick into the fall)
HERE=$(cd "$(dirname "$0")" && pwd)
R=$1; OUT=$2; shift 2; mkdir -p "$OUT"
export TMPDIR=/home/volence/.cache/aeon-tmp
n=0
leg() {
  local nm=$1 sc=$2; shift 2
  local la; la=$(cut -d' ' -f1 /proc/loadavg)
  timeout 900 python3 "$HERE/ojz_feel_probe.py" --rom "$R.bin" --lst "$R.lst" --script "$sc" \
      --out "$OUT/$nm.json" "$@" > "$OUT/$nm.txt" 2>&1
  echo "$nm rc=$? load=$la->$(cut -d' ' -f1 /proc/loadavg)" >> "$OUT/legs.meta"
  n=$((n+1))
}
: > "$OUT/legs.meta"
leg spawn_right   "auto:right:2500" "$@"
leg floor_left    "warp:6000,5900;auto:left:1400" "$@"
leg floor_shuttle "warp:3000,5900;shuttle:90:10" "$@"
leg floor_spin    "warp:500,5900;spindash:right:200;hold:right:300;spindash:left:200;hold:left:300" "$@"
leg floor_jumps   "warp:500,5900;jumps:right:30:40" "$@"
leg fall_down     "warp:3000,100;hold::500" "$@"
leg fall_diag     "warp:1500,100;hold:right:500" "$@"
leg sec0_left     "hold:left:900" "$@"
leg sec0_loop     "warp:700,560;spindash:right:150;hold:right:400" "$@"
leg sec0_shuttle  "warp:700,560;shuttle:60:10" "$@"
leg spawn_spin    "spindash:right:150;auto:right:1500" "$@"
leg spawn_jumprun "jumps:right:45:45" "$@"
leg fall_diag_l   "warp:5500,100;hold:left:500" "$@"
leg fall_diag_mid "warp:2500,100;hold:right:500" "$@"
leg fall_diag_rev "warp:3000,100;hold:right:150;hold:left:150;hold:right:200" "$@"
leg slab_spin     "warp:900,830;spindash:right:150;hold:right:400" "$@"
echo "finished=$n" >> "$OUT/legs.meta"
