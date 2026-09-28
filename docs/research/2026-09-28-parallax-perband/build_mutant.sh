#!/bin/bash
# build_mutant.sh <tag> <A|B> : a deliberate MUTANT of HEAD's engine/level/parallax.emp, built in the
# two DEBUG shapes the identity legs read (canonical cdebug, S2 clip debug), then the file restored
# FROM HEAD (the committed file, never `git checkout --` on a dirty tree). Refused if parallax.emp
# differs from HEAD on entry.
#   A  Step 4a's key ignores vs: the `cmp.w Parallax_Shadow_Key_VS, d0 / bne .shadow_rebuild` pair
#      is deleted, so a view built at one Vscroll_BG is reused at another (stale band tops).
#   B  Step 4b's split does not drop the key: its `clr.l Parallax_Shadow_Key_Config` is deleted, so
#      the tick after a split reuses (and re-splits) the rewritten view.
# The mutated file is kept beside the ROMs as parallax.emp.mutant, and its diff against HEAD as
# mutant.diff, so the mutation is ON DISK for the record. Outputs $HOME/pxperf/<tag>/.
export TMPDIR=/home/volence/.cache/aeon-tmp
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$HERE/../../.." && pwd)
cd "$W" || exit 9
F=engine/level/parallax.emp
T=$HOME/pxperf/$1; rm -rf "$T"; mkdir -p "$T"
git diff --quiet HEAD -- $F || { echo "REFUSED: $F differs from HEAD"; exit 3; }
python3 - "$F" "$2" <<'EOF' || { git show HEAD:$F > $F; exit 4; }
import sys
p, m = sys.argv[1], sys.argv[2]
s = open(p).read()
cut = {"A": "        cmp.w   Parallax_Shadow_Key_VS, d0          // (Parallax_Shadow_Key_VS).w\n"
            "        bne     .shadow_rebuild\n",
       "B": "    .anchor_have_k:\n" + "".join(
            l + "\n" for l in s.split(".anchor_have_k:\n", 1)[1].split("\n")[:4]) +
            "        clr.l   Parallax_Shadow_Key_Config          // (Parallax_Shadow_Key_Config).w\n"}[m]
if s.count(cut) != 1:
    raise SystemExit(f"mutant {m}: expected one site, found {s.count(cut)}")
keep = "    .anchor_have_k:\n" if m == "B" else ""
open(p, "w").write(s.replace(cut, keep))
print(f"mutant {m} applied")
EOF
cp $F "$T/parallax.emp.mutant"; git diff HEAD -- $F > "$T/mutant.diff"
rm -f s4.debug.bin s4.s2clip.debug.bin
FAST=1 DEBUG=1 ./build.sh > "$T/b_cdebug.log" 2>&1; r1=$?; cp s4.debug.bin "$T/cdebug.bin"; cp s4.debug.lst "$T/cdebug.lst"
FAST=1 DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh > "$T/b_sdebug.log" 2>&1; r2=$?; cp s4.s2clip.debug.bin "$T/debug.bin"; cp s4.s2clip.debug.lst "$T/debug.lst"
git show HEAD:$F > $F
git diff --quiet HEAD -- $F && echo "restored $F from HEAD" || echo "RESTORE FAILED"
python3 -c "import zlib,glob,sys;[print(f.split('/')[-1], '%08x'%zlib.crc32(open(f,'rb').read()), len(open(f,'rb').read())) for f in sorted(glob.glob(sys.argv[1]+'/*.bin'))]" "$T" > "$T/crc.txt"
echo "rc cdebug=$r1 sdebug=$r2 finished=1" > "$T/done"; cat "$T/done" "$T/crc.txt"
