#!/usr/bin/env bash
# bake_variant.sh MANIFEST LOG — copy a scratch manifest over the woven act's clips.json, bake it
# (no --keep: the generated tree is left as committed), print the lines the note quotes.
# The caller restores clips.json afterwards (git checkout -- games/sonic4/data/clips/s2_woven/clips.json).
man=$1
log=$2
cp "$man" games/sonic4/data/clips/s2_woven/clips.json
python3 tools/clip_rom_bake.py bake games/sonic4/data/clips/s2_woven/clips.json --allow-dirty > "$log" 2>&1
rc=$?
echo "bake rc=$rc ($man)"
grep -n "collision: \|N1 \|DONE\|SCREEN\|Z2 " "$log" | cut -c1-300
[ $rc -ne 0 ] && tail -1 "$log" | cut -c1-400
exit $rc
