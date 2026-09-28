#!/bin/bash
# redfirst_gate.sh <out> : tools/oscillation_thrash_gate.py must be RED on a rebuilt ROM whose
#   horizontal arming gate (the two instructions in Tile_Cache_Fill's col scan) is removed, and
#   GREEN again once engine/level/tile_cache.emp is restored from the COMMITTED file.
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
cd "$(dirname "$0")/../../.." || exit 2
OUT=$1; : > "$OUT"
F=engine/level/tile_cache.emp
crc() { python3 -c "import zlib,sys;print('%08x'%zlib.crc32(open(sys.argv[1],'rb').read()))" "$1"; }
git show HEAD:$F > $F
python3 - "$F" <<'EOF'
import sys
p = sys.argv[1]; s = open(p).read()
old = ("        cmpi.w  #H_PFX_ARM, Cache_H_Pfx_Run    // ARMING GATE (horizontal)\n"
       "        blt     .col_done\n")
assert s.count(old) == 1, "mutation site not found"
open(p, "w").write(s.replace(old, ""))
EOF
echo "== mutation (git diff of $F):" >> "$OUT"
git diff -- $F >> "$OUT"
FAST=1 DEBUG=1 ./build.sh > /dev/null 2>&1; echo "mutant build rc=$? s4.debug.bin crc=$(crc s4.debug.bin)" >> "$OUT"
python3 tools/oscillation_thrash_gate.py >> "$OUT" 2>&1; echo "gate on mutant rc=$? (want 1)" >> "$OUT"
git show HEAD:$F > $F
FAST=1 DEBUG=1 ./build.sh > /dev/null 2>&1; echo "restored build rc=$? s4.debug.bin crc=$(crc s4.debug.bin) diff-lines=$(git diff -- $F | wc -l)" >> "$OUT"
python3 tools/oscillation_thrash_gate.py >> "$OUT" 2>&1; echo "gate on restored rc=$? (want 0)" >> "$OUT"
echo "finished=1" >> "$OUT"
