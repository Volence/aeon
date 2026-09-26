#!/usr/bin/env bash
# Without the ground-speed cap: a top-speed (0x600) leftward run into loop 1 with a jump at
# frame 30 leaves the player stuck on the loop's inner slope ON PLANE B (sweep2). From there a
# player lets go, settles, spindashes (real inputs, no injected speed: frame 260, direction
# released 60 frames earlier; measured: the rocking on the slope never reads as "stuck", so
# the first version of this sweep never fired a dash) and jumps D frames after the release.
# Does any D get him out of the loop to the LEFT on plane B?  Tabulate: sweep_table.py <tag>3
#   usage: sweep3.sh <rom> <lst> <tag>
rom=$1; lst=$2; tag=$3
here=docs/research/2026-09-27-clip-planeb-hole
man=games/sonic4/data/clips/s2_ehz_cpz/clips.json
mkdir -p "$here/out"
bad=0
for d in none $(seq 2 2 40); do
  darg=(); [ "$d" != none ] && darg=(--jump-after-dash "$d")
  name="${tag}3.sweep_dash_d${d}"
  timeout 900 python3 "$here/planeb_hole_drive.py" --rom "$rom" --lst "$lst" --manifest "$man" \
    --x 4500 --y-from 600 --dir left --gsp 0x600 --jump-at 30 --spindash-at 260 \
    --idle-before-dash 60 "${darg[@]}" --frames 600 --stop-x 3990 --label "$name" \
    --json "$here/out/$name.json"
  rc=$?
  echo "rc[$name]=$rc"
  [ $rc -ne 0 ] && bad=$((bad + 1))
done
echo "finished=$bad"
