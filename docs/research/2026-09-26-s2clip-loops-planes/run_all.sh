#!/usr/bin/env bash
# Every drive the 2026-09-26 loops/planes research reports, each run with the switchers
# absent (the ROM as built) and host-emulated (S2 Obj03). Writes one JSON per drive into
# out/ beside this script and prints each summary. Run from the aeon worktree root after
# `DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh`.
#   name  x  y_from  dir  gsp  frames
here=docs/research/2026-09-26-s2clip-loops-planes
mkdir -p "$here/out"
drives=(
  "ehz_loop1_R 3950 0 right top 240"
  "ehz_loop1_R_walk 3950 0 right none 600"
  "ehz_loop2_R 6600 0 right top 240"
  "ehz_loop3_R 7040 780 right top 240"
  "ehz_loop4_R 8500 0 right top 240"
  "ehz_loop1_L 4500 600 left top 240"
  "cpz_braid_R 12160 0 right top 300"
  "cpz_wall3591_R 14700 700 right top 400"
  "cpz_upper_R 13700 0 right top 900"
  "cpz_dfloor_R 14310 1106 right top 400"
  "cpz_from_braid_long_R 12160 0 right top 1500"
)
if [ -n "$ONLY" ]; then
  keep=(); for d in "${drives[@]}"; do case " $ONLY " in *" ${d%% *} "*) keep+=("$d");; esac; done
  drives=("${keep[@]}")
fi
for d in "${drives[@]}"; do
  set -- $d
  for sw in none s2; do
    timeout 900 python3 "$here/loop_plane_probe.py" --rom s4.s2clip.debug.bin \
      --lst s4.s2clip.debug.lst --manifest games/sonic4/data/clips/s2_ehz_cpz/clips.json \
      --x "$2" --y-from "$3" --dir "$4" --gsp "$5" --frames "$6" --switchers "$sw" \
      --label "$1" --json "$here/out/$1.$sw.json" 2>&1 | grep -v "^finished="
    echo "rc[$1.$sw]=${PIPESTATUS[0]}"
  done
done
echo "finished=0"
