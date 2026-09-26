#!/usr/bin/env bash
# Leftward exits from Emerald Hill loop 1 (act x ~4100..4400) at a sweep of ground speeds, with
# and without a jump, on one clip ROM. The question each drive answers: on which LAYER is the
# player when he is first left of x 3990 (i.e. out of the loop, heading for x 1704 and the
# bridge pit)? Writes one JSON per drive into out/ and a summary log.
#   usage: sweep.sh <rom> <lst> <tag>
# Run from the aeon worktree root. Ends with finished=<number of nonzero drive exits>.
rom=$1; lst=$2; tag=$3
here=docs/research/2026-09-27-clip-planeb-hole
man=games/sonic4/data/clips/s2_ehz_cpz/clips.json
mkdir -p "$here/out"
bad=0
for g in 0x300 0x400 0x500 0x600 0x700 0x800 0x900 0xA00 0xB00 0xC00 cap; do
  for j in none 10 30 60; do
    jarg=(); [ "$j" != none ] && jarg=(--jump-at "$j")
    name="$tag.sweep_g${g}_j${j}"
    timeout 900 python3 "$here/planeb_hole_drive.py" --rom "$rom" --lst "$lst" --manifest "$man" \
      --x 4500 --y-from 600 --dir left --gsp "$g" --frames 500 --stop-x 3990 \
      "${jarg[@]}" --label "$name" --json "$here/out/$name.json"
    rc=$?
    echo "rc[$name]=$rc"
    [ $rc -ne 0 ] && bad=$((bad + 1))
  done
done
echo "finished=$bad"
