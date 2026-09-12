#!/bin/bash
# FIXTURE C (T1 seat): the LAST section has no editor tiles file. ojz_strip_gen.generate()
# skips a section without section_N.tiles.bin ("WARNING ... skipping", by design), and
# emit_section_local_maps() refuses a HOLE in the flat ids -- but a missing TAIL section is
# not a hole. Question: does the re-bake refuse, or does it ship a short OJZ_Sec_LocalMaps
# table (the engine indexes it by flat id = sec_y*grid_w + sec_x over the 3x3 grid) plus
# the previous bake's sec8_* files?
S=$(cat /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0f66baa9-0a26-4066-a435-9516186c96f8/scratchpad/t1_S_path)
F="$S/fx_tail"
rm -rf "$F"; cp -a "$S/pristine" "$F"
python3 - "$F/tools/regenerate-level.sh" <<'EOF'
import sys
p = sys.argv[1]; s = open(p).read()
old = 'cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"'
assert s.count(old) == 1
open(p, "w").write(s.replace(old, 'cd "$(dirname "${BASH_SOURCE[0]}")/.."'))
EOF
cd "$F"
rm -f games/sonic4/data/editor/ojz/act1/section_8.tiles.bin
G=games/sonic4/data/generated/ojz/act1
for f in sec8_strips_a.bin sec8_local_map.bin sec8_blocks.bin; do echo "before: $f mtime $(stat -c%Y $G/$f)"; done
export EMPYREAN_SUITE_ROOT=/home/volence/sonic_hacks
export AEON_SONIC_HACK_DIR=/home/volence/sonic_hacks/sonic_hack
export AEON_SKDISASM_DIR=/home/volence/sonic_hacks/skdisasm
PYC=$(mktemp -d "$S/pyc.XXXXXX"); export PYTHONPYCACHEPREFIX="$PYC"
sleep 1
echo "start_utc=$(date -u +%FT%TZ)"
bash tools/regenerate-level.sh > "$S/fx_tail.log" 2>&1
rc=$?
echo "regenerate-level.sh finished=$rc end_utc=$(date -u +%FT%TZ)"
grep -n "section_8\|WARNING: .*not found\|sec_local_maps:\|Section 8\|verify_level_bin\|ERROR\|Traceback\|Error\|Re-bake complete\|stamped" "$S/fx_tail.log"
for f in sec8_strips_a.bin sec8_local_map.bin sec8_blocks.bin; do echo "after:  $f mtime $(stat -c%Y $G/$f)"; done
grep -n "OJZ_Sec_LocalMaps" $G/sec_local_maps.emp
grep -n "OJZ_Sec8_Blocks" $G/sec_block_blobs.emp
