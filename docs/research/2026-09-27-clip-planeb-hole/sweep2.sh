#!/usr/bin/env bash
# Finer sweep of "jump while inside loop 1, heading left" at speeds a player reaches without the
# engine's ground-speed cap: top running speed (0x600), and a spindash-range 0x900 and 0xC00
# (the S3K spindash maximum). One JSON per drive in out/; tabulate with sweep_table.py <tag>2.
#   usage: sweep2.sh <rom> <lst> <tag>
rom=$1; lst=$2; tag=$3
here=docs/research/2026-09-27-clip-planeb-hole
man=games/sonic4/data/clips/s2_ehz_cpz/clips.json
mkdir -p "$here/out"
bad=0
for g in 0x600 0x900 0xC00; do
  for j in $(seq 14 2 56); do
    name="${tag}2.sweep_g${g}_j${j}"
    timeout 900 python3 "$here/planeb_hole_drive.py" --rom "$rom" --lst "$lst" --manifest "$man" \
      --x 4500 --y-from 600 --dir left --gsp "$g" --frames 400 --stop-x 3990 \
      --jump-at "$j" --label "$name" --json "$here/out/$name.json"
    rc=$?
    echo "rc[$name]=$rc"
    [ $rc -ne 0 ] && bad=$((bad + 1))
  done
done
echo "finished=$bad"
