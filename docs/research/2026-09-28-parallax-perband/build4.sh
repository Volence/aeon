#!/bin/bash
# build4.sh <tag> : FAST builds of THIS worktree's working tree, the four shapes the legs read:
# canonical plain/debug (cplain/cdebug) and S2 clip s2_ehz_cpz plain/debug (plain/debug).
# Outputs $HOME/pxperf/<tag>/{cplain,cdebug,plain,debug}.{bin,lst}, crc.txt, and done
# (the per-shape build rc and a finished=1 stamp). The tree diff at build time is kept beside
# them so a result can be tied to the source it came from.
export TMPDIR=/home/volence/.cache/aeon-tmp
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
W=$(cd "$(dirname "$0")/../../.." && pwd)
T=$HOME/pxperf/$1; rm -rf "$T"; mkdir -p "$T"
cd "$W" || exit 9
git rev-parse HEAD > "$T/head.txt"; git diff > "$T/tree.diff"
rm -f s4.bin s4.debug.bin s4.s2clip.bin s4.s2clip.debug.bin
FAST=1 ./build.sh > "$T/b_cplain.log" 2>&1; r1=$?; cp s4.bin "$T/cplain.bin"; cp s4.lst "$T/cplain.lst"
FAST=1 DEBUG=1 ./build.sh > "$T/b_cdebug.log" 2>&1; r2=$?; cp s4.debug.bin "$T/cdebug.bin"; cp s4.debug.lst "$T/cdebug.lst"
FAST=1 S2CLIP=s2_ehz_cpz ./build.sh > "$T/b_splain.log" 2>&1; r3=$?; cp s4.s2clip.bin "$T/plain.bin"; cp s4.s2clip.lst "$T/plain.lst"
FAST=1 DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh > "$T/b_sdebug.log" 2>&1; r4=$?; cp s4.s2clip.debug.bin "$T/debug.bin"; cp s4.s2clip.debug.lst "$T/debug.lst"
python3 -c "import zlib,glob,sys;[print(f.split('/')[-1], '%08x'%zlib.crc32(open(f,'rb').read()), len(open(f,'rb').read())) for f in sorted(glob.glob(sys.argv[1]+'/*.bin'))]" "$T" > "$T/crc.txt"
echo "rc cplain=$r1 cdebug=$r2 splain=$r3 sdebug=$r4 finished=1" > "$T/done"
cat "$T/done" "$T/crc.txt"
