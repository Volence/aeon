#!/bin/bash
# final_verify.sh : the brief's remaining final checks on THIS worktree, after landing_build:
# both full (non-FAST) S2CLIP=s2_ehz_cpz builds, then the effects-gates ritual on s4.debug.bin.
# Each step's rc is printed; the last line is finished=<steps run>. Log: $HOME/pxperf/r2_final.log
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
export TMPDIR=/home/volence/.cache/aeon-tmp
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$HERE/../../.." && pwd)
cd "$W" || exit 9
LOG=$HOME/pxperf/r2_final.log
: > "$LOG"
S2CLIP=s2_ehz_cpz ./build.sh >> "$LOG" 2>&1; echo "S2CLIP_PLAIN_RC=$?" >> "$LOG"
DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh >> "$LOG" 2>&1; echo "S2CLIP_DEBUG_RC=$?" >> "$LOG"
python3 -c "import zlib;[print(f, '%08x'%zlib.crc32(open(f,'rb').read()), len(open(f,'rb').read())) for f in ['s4.bin','s4.debug.bin','demo.debug.bin','s4.s2clip.bin','s4.s2clip.debug.bin']]" >> "$LOG"
find tools -name __pycache__ -type d -prune -exec rm -rf {} +
python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst >> "$LOG" 2>&1; echo "EFFECTS_GATES_RC=$?" >> "$LOG"
echo "finished=3" >> "$LOG"
