#!/bin/bash
# build_mutant3.sh <tag> <L|M|N|P|Q|R|S> : a deliberate MUTANT of HEAD's PPB-4 code (the split
# Step 4b keeps under Step 4a's key), built FAST in the canonical DEBUG shape (the anchored
# region is OJZ's; the S2 clip has no anchored config, so it cannot see any of these), then
# every mutated file restored FROM HEAD (`git show HEAD:path > path`). Refused if a file it
# mutates differs from HEAD on entry. The mutated files are kept beside the ROM (*.mutant)
# with their diff (mutant.diff), so the mutation is ON DISK.
#
# CODE MUTANTS (they build; the identity legs and/or the witness must go RED):
#   L  the kept check never compares L with the successor's top (`bhs .anchor_restart`
#      deleted): a line that moved DOWN into the next band keeps the old split.
#   M  the kept check never compares L with the parent's top (`blo .anchor_restart` deleted):
#      a line that moved UP into the previous band keeps the old split.
#   N  the kept tick never retops the split entry (`move.w d0, band_top_line(a5)` deleted
#      from the shared tail, so a FRESH split is not retopped either): the boundary stays
#      where the ROM copy put it.
#   P  Step 4a's rebuild does not clear the kept split (its `clr.w` deleted; the restart's
#      own clear stays, so this is a wrong picture, not a hang).
#   R  the no-split exit forgets a kept split (its `beq .bands_ready` becomes `jbra`): a line
#      that leaves the screen under an unchanged key leaves the old split on screen.
#   Q  the keep decision ignores the curve condition (`bne .anchor_drop` deleted). EXPECTED
#      GREEN, and recorded as a COVERAGE GAP, not a pass: no shipped config and no leg pairs
#      an anchored split with a curve layer (EHZ's curve config has no anchor channel, and
#      the fixture matrix's configs are RAM, never keyed, so never kept).
# ENSURE MUTANT (the build must FAIL, naming the new pin):
#   S  engine/ram.emp SHADOW_SPLIT_LONGS 0 under CAP_ANCHORS -> the Parallax_Shadow_Split pin
# Outputs $HOME/pxperf/<tag>/.
export TMPDIR=/home/volence/.cache/aeon-tmp
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$HERE/../../.." && pwd)
cd "$W" || exit 9
T=$HOME/pxperf/$1; rm -rf "$T"; mkdir -p "$T"
FILES="engine/level/parallax.emp engine/ram.emp"
for f in $FILES; do git diff --quiet HEAD -- "$f" || { echo "REFUSED: $f differs from HEAD"; exit 3; }; done
python3 - "$2" <<'EOF' || { for f in $FILES; do git show HEAD:$f > $f; done; exit 4; }
import sys
m = sys.argv[1]
P, R = "engine/level/parallax.emp", "engine/ram.emp"
cut = {
 "L": (P, "        bhs     .anchor_restart                     // at or below it: a later band holds L\n", ""),
 "M": (P, "        blo     .anchor_restart                     // above it: an earlier band holds L\n", ""),
 "N": (P, "        adda.w  d2, a5\n        move.w  d0, band_top_line(a5)\n        addq.w  #1, d7",
          "        adda.w  d2, a5\n        addq.w  #1, d7"),
 "P": (P, "    .cap_anchors_split_rebuild_begin:\n        clr.w   Parallax_Shadow_Split               // (Parallax_Shadow_Split).w\n",
          "    .cap_anchors_split_rebuild_begin:\n"),
 "R": (P, "        tst.w   Parallax_Shadow_Split               // (Parallax_Shadow_Split).w\n        beq     .bands_ready\n",
          "        tst.w   Parallax_Shadow_Split               // (Parallax_Shadow_Split).w\n        jbra    .bands_ready\n"),
 "Q": (P, "        bne     .anchor_drop                        // the hoist walks this view: never keep it\n", ""),
 "S": (R, "const SHADOW_SPLIT_LONGS    = if (GAME_SCANLINE_CAPS & $0008) != 0 { 1 } else { 0 }",
          "const SHADOW_SPLIT_LONGS    = if (GAME_SCANLINE_CAPS & $0008) != 0 { 0 } else { 0 }"),
}[m]
f, old, new = cut
s = open(f).read()
if s.count(old) != 1:
    raise SystemExit(f"mutant {m}: expected one site in {f}, found {s.count(old)}")
open(f, "w").write(s.replace(old, new))
print(f"mutant {m} applied to {f}")
EOF
git diff HEAD -- $FILES > "$T/mutant.diff"
for f in $FILES; do git diff --quiet HEAD -- "$f" || cp "$f" "$T/$(basename $f).mutant"; done
rm -f s4.debug.bin
FAST=1 DEBUG=1 ./build.sh > "$T/b_cdebug.log" 2>&1; r1=$?
cp s4.debug.bin "$T/cdebug.bin" 2>/dev/null; cp s4.debug.lst "$T/cdebug.lst" 2>/dev/null
for f in $FILES; do git show HEAD:$f > $f; done
ok=1; for f in $FILES; do git diff --quiet HEAD -- "$f" || ok=0; done
[ $ok = 1 ] && echo "restored $FILES from HEAD" || echo "RESTORE FAILED"
python3 -c "import zlib,glob,sys;[print(f.split('/')[-1], '%08x'%zlib.crc32(open(f,'rb').read()), len(open(f,'rb').read())) for f in sorted(glob.glob(sys.argv[1]+'/*.bin'))]" "$T" > "$T/crc.txt"
echo "rc cdebug=$r1 finished=1" > "$T/done"; cat "$T/done" "$T/crc.txt"
