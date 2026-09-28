#!/bin/bash
# build_mutant2.sh <tag> <C|D|E|F|K|G|H|I|J> : a deliberate MUTANT of HEAD's round-2 parallax code,
# built FAST in the two DEBUG shapes the identity legs read (canonical cdebug, S2 clip debug),
# then every mutated file restored FROM HEAD (`git show HEAD:path > path`, never a checkout of
# a dirty tree). Refused if a file it mutates differs from HEAD on entry. The mutated files are
# kept beside the ROMs (*.mutant) with their diff (mutant.diff), so the mutation is ON DISK.
#
# CODE MUTANTS (they build; the identity legs and the witness must go RED):
#   C  PPB-3: the selection pass marks a BG-sampled slot flat (its `bne .sel_inline` after the
#      shift_b test is deleted), so the fill sends a deformed band down `.lp_flat`.
#   D  PPB-3: Step 4b's split sets the flag but does not mark the bytes (the
#      `fill_band_sel_longs` run is deleted), so a split view is read with the unsplit view's
#      selection.
#   K  PPB-3: Step 4a's rebuild does not drop the selection (its `clr.b` is deleted), so a
#      view re-rotated at a new vs keeps the old view's bytes.
#   E  PPB-5: the curve walk's slot count is one short (`addq.w #1, d2` deleted), so a view
#      with one curve layer (Emerald Hill's) never hoists it.
#   F  PPB-6: one of the two `movem.l` in a flat group is deleted, so half of every group of 8
#      lines keeps last frame's longwords.
# ENSURE MUTANTS (the build must FAIL, naming the new pin):
#   G  engine/ram.emp CURVE_WALK_WORDS one word short   -> the Parallax_Curve_Walk pin
#   H  engine/ram.emp BAND_SEL_BYTES four bytes short   -> the Parallax_Band_Sel pin
#   I  parallax.emp BAND_SEL_N folds the retired $0001 bit instead of CAP_DEFORM -> its pin
#   J  engine/system/constants.emp MAX_PARALLAX_BANDS 16 -> 18 -> the `% 4` pin
# Outputs $HOME/pxperf/<tag>/.
export TMPDIR=/home/volence/.cache/aeon-tmp
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$HERE/../../.." && pwd)
cd "$W" || exit 9
T=$HOME/pxperf/$1; rm -rf "$T"; mkdir -p "$T"
FILES="engine/level/parallax.emp engine/ram.emp engine/system/constants.emp"
for f in $FILES; do git diff --quiet HEAD -- "$f" || { echo "REFUSED: $f differs from HEAD"; exit 3; }; done
python3 - "$2" <<'EOF' || { for f in $FILES; do git show HEAD:$f > $f; done; exit 4; }
import sys
m = sys.argv[1]
P, R, C = "engine/level/parallax.emp", "engine/ram.emp", "engine/system/constants.emp"
cut = {
 "C": (P, "        cmpi.b  #15, band_entry.band_deform_shift_b(a4)\n        bne     .sel_inline\n    .sel_flat:\n",
          "        cmpi.b  #15, band_entry.band_deform_shift_b(a4)\n    .sel_flat:\n"),
 "D": (P, "        fill_band_sel_longs(a5, d3)\n", ""),
 "K": (P, "    .cap_deform_sel_rebuild_begin:\n        clr.b   Parallax_Band_Sel_Valid             // (Parallax_Band_Sel_Valid).w\n",
          "    .cap_deform_sel_rebuild_begin:\n"),
 "E": (P, "        addq.w  #1, d2                              // count = last - first + 1\n", ""),
 "F": (P, "    .fl_line:\n        movem.l d0/d3/d5-d6, -(a0)\n        movem.l d0/d3/d5-d6, -(a0)\n",
          "    .fl_line:\n        movem.l d0/d3/d5-d6, -(a0)\n"),
 "G": (R, "const CURVE_WALK_WORDS      = BAND_CURVE_BYTES / 5\n", "const CURVE_WALK_WORDS      = BAND_CURVE_BYTES / 10\n"),
 "H": (R, "{ MAX_PARALLAX_BANDS } else { 0 }   // CAP_DEFORM\n", "{ MAX_PARALLAX_BANDS - 4 } else { 0 }   // CAP_DEFORM\n"),
 "I": (P, "pub const BAND_SEL_N = if (GAME_SCANLINE_CAPS & $0004) != 0", "pub const BAND_SEL_N = if (GAME_SCANLINE_CAPS & $0001) != 0"),
 "J": (C, "pub const MAX_PARALLAX_BANDS    = 16\n", "pub const MAX_PARALLAX_BANDS    = 18\n"),
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
rm -f s4.debug.bin s4.s2clip.debug.bin
FAST=1 DEBUG=1 ./build.sh > "$T/b_cdebug.log" 2>&1; r1=$?; cp s4.debug.bin "$T/cdebug.bin" 2>/dev/null; cp s4.debug.lst "$T/cdebug.lst" 2>/dev/null
r2=skipped
case "$2" in C|D|K|E|F)
  FAST=1 DEBUG=1 S2CLIP=s2_ehz_cpz ./build.sh > "$T/b_sdebug.log" 2>&1; r2=$?
  cp s4.s2clip.debug.bin "$T/debug.bin"; cp s4.s2clip.debug.lst "$T/debug.lst";;
esac
for f in $FILES; do git show HEAD:$f > $f; done
ok=1; for f in $FILES; do git diff --quiet HEAD -- "$f" || ok=0; done
[ $ok = 1 ] && echo "restored $FILES from HEAD" || echo "RESTORE FAILED"
python3 -c "import zlib,glob,sys;[print(f.split('/')[-1], '%08x'%zlib.crc32(open(f,'rb').read()), len(open(f,'rb').read())) for f in sorted(glob.glob(sys.argv[1]+'/*.bin'))]" "$T" > "$T/crc.txt"
echo "rc cdebug=$r1 sdebug=$r2 finished=1" > "$T/done"; cat "$T/done" "$T/crc.txt"
