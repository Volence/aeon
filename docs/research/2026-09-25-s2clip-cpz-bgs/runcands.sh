#!/bin/bash
# Measure scratch candidate clip acts (written by mkcand.py, NEVER committed):
# FAST build in the plain and DEBUG shapes, the room gate run directly on each listing
# (FAST skips bganim_room), and a copy of the bake's clipact.json.
# Usage (from the repo root, with SIGIL_BUILD/SIGIL_EMIT exported):
#   OUT=<scratch dir> nohup docs/research/2026-09-25-s2clip-cpz-bgs/runcands.sh s2x_cpz4096 ... &
# then poll $OUT/runcands.status for `finished=<n>`. Delete the scratch manifests afterwards:
# the S2CLIP trap restores the generated tree, not games/sonic4/data/clips/.
W=$(git rev-parse --show-toplevel) || exit 3
S=${OUT:?set OUT to a scratch directory}
: "${SIGIL_BUILD:?export SIGIL_BUILD}" "${SIGIL_EMIT:?export SIGIL_EMIT}"
cd "$W" || exit 3
n=0
for id in "$@"; do
  for dbg in 0 1; do
    tag="${id}_d${dbg}"
    DEBUG=$dbg FAST=1 S2CLIP=$id ./build.sh > "$S/build_$tag.log" 2>&1
    echo "build $tag rc=$?" >> "$S/runcands.status"
    if [ "$dbg" = 1 ]; then rom=s4.s2clip.debug; else rom=s4.s2clip; fi
    python3 tools/bganim_room.py --lst "$rom.lst" --rom "$rom.bin" --gate > "$S/room_$tag.txt" 2>&1
    echo "room $tag rc=$?" >> "$S/runcands.status"
    python3 -c "import zlib,sys;b=open(sys.argv[1],'rb').read();print('crc %08x size %d'%(zlib.crc32(b),len(b)))" "$rom.bin" >> "$S/room_$tag.txt"
    n=$((n+1))
  done
  cp -f "games/sonic4/data/clips/$id/baked/clipact.json" "$S/clipact_$id.json" 2>/dev/null
done
echo "finished=$n" >> "$S/runcands.status"
