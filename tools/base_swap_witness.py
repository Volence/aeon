#!/usr/bin/env python3
"""base_swap_witness — does EFFECTS-W1 item 11a's mid-frame base swap reach the SCREEN?

The claim is NOT "the program builds" and NOT "the emitted words are right" —
`tools/plane_base_swap_gate.py` proves both, statically, on every canonical build, and it
was proven red four ways. It is that the machine EXECUTES `OP_SET_REG` mid-frame and the
picture below the fire line changes as a result. The item-11a booking tags this as owed:
"No emulator was used. A green gate is not the picture."

THE CONTROL IS THE WHOLE DESIGN, and it is the one thing a screenshot cannot supply.
Installing ANY raster program REPLACES the act's own, so subject-vs-default and
subject-vs-None both differ on nearly every row for a reason that has nothing to do with
the base swap. `band_witness` measured exactly that (122 of 124 rows moved both ways) and
`ramp_authored_witness` answered it with a matched twin. This witness takes the same
instrument one step further, because item 11a admits a control the ramp could not:

    THE TWIN IS THE SUBJECT'S OWN 22 BYTES WITH ONE WORD CHANGED.

Word 8 is the op's argument. The subject carries $8238 — reg $02 <- VRAM_PLANE_B. The twin
carries $8200 | (VRAM_PLANE_A >> 10) — reg $02 <- the base Plane A ALREADY has at frame
top, so the op dispatches, costs the same cycles, writes the same register, and changes
nothing. Every confound the replacement introduces is therefore present in BOTH arms and
subtracts out: same program length, same schedule, same arm words, same op count, same
dispatch depth, same displaced act program. The only surviving difference is the value in
reg $02, which is precisely the subject.

    (`ojz_effects.emp`'s own `ensure` refuses that word in an AUTHORED program, by name —
    "the SAME word reg $02 already carries at frame top". That refusal is what makes it the
    right control here: the engine considers it a guaranteed no-op, so the twin is inert by
    the tree's own argument rather than by mine.)

WHY THE TWIN LIVES IN RAM. `ramp_authored_witness` measured that the Rust core refuses ROM
writes outright ("only the work-RAM window is writable"), so the twin is written to scratch
and `Raster_Pending` is pointed at it. `Raster_Install` only stores a pointer and the walker
reads the record through a1, so a record in RAM is walked identically. That also makes this
strictly better than a ROM patch would have been: the subject's bytes are never touched, so
the two arms are two installs of two records rather than one record mutated between runs.

EVERY EXPECTATION IS DERIVED FROM THE TREE AT THE MOMENT OF USE, none typed in:
  * the fire line from `OJZ_BASE_SWAP_LINE` in games/sonic4/data/effects/ojz_effects.emp
  * the program's address from the .lst passed on the command line
  * the subject word from the built ROM
  * the control word from VRAM_PLANE_A (engine/system/constants.emp) folded through
    vdp_base_shift's PlaneA arm (engine/vdp.emp)
This matters more than usual here. `docs/DEFERRED_WORK.md`'s item-11a block still says the
swap fires at line 160 and pins the arm word $8A9D; the owner moved it to line 3 on
2026-09-03 ("I would like to see in the plane swap the fg go to the bg at the top") and the
ROM reads $8A00. A witness that had copied the booking's 160 would have predicted an edge
that is not there and reported a FAILURE on a correct ROM.

WHAT THIS DOES NOT ESTABLISH, stated because the boundary is where a raster effect fails:
  * It does not pin the transition to an exact line. `raster.emp`'s row-119 note records
    that a bare OP_SET_REG switches its register partway across the fire+1 line (~45%
    across, measured), so the first changed row may be the fire line or the one after it.
    The design's §8 Q2 asks exactly this and is open. Rows are compared as WHOLE-ROW
    hashes, so a partial row reads as changed; that is why the control region is asserted
    over lines strictly ABOVE the fire line rather than up to it.
  * It does not say the bottom band is a RECOGNISABLE second copy of the background. It
    says the picture below the fire line depends on the value written to reg $02. Whether
    that value renders as the intended nametable is a separate claim; the gate's four
    red-first mutations cover the word, and a human looking at it covers the taste.
  * It samples the composed frame. It cannot attribute a changed row to a layer.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ramp_authored_witness import run, SCREEN_LINES  # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

PROG_WORDS = 11          # the whole sparse program; asserted against the listing span
ARG_WORD = 8             # OP_SET_REG's argument, per ojz_effects.emp's OJZ_BASE_SWAP_HAND
AUTHORED_SYM = "EditorRaster_OJZ_Act1_ojz_sec6_baseswap"


def read_const(path, name):
    """A named `const NAME = <int>` out of an .emp file. Refuses ambiguity rather than
    taking the first hit — two definitions of one name means the file is not what this
    reader thinks it is."""
    src = Path(path).read_text()
    hits = re.findall(r"^\s*(?:pub\s+)?const\s+%s\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$" % name,
                      src, re.M)
    if len(hits) != 1:
        raise SystemExit("%s: expected exactly one `const %s = ...`, found %d. Refusing to "
                         "guess which one the ROM was built from." % (path, name, len(hits)))
    v = hits[0]
    return int(v[1:], 16) if v.startswith("$") else int(v)


def read_plane_a_shift(vdp_emp):
    """vdp_base_shift's PlaneA arm. Read rather than assumed: the whole point of folding the
    word through the helper is that a shift change moves the op, and a witness that hardcoded
    10 would be blind to exactly that."""
    src = Path(vdp_emp).read_text()
    m = re.search(r"fn\s+vdp_base_shift.*?\{(.*?)\n\}", src, re.S)
    if not m:
        raise SystemExit("%s: could not find vdp_base_shift" % vdp_emp)
    arm = re.search(r"PlaneA\s*=>\s*(\d+)", m.group(1))
    if not arm:
        raise SystemExit("%s: vdp_base_shift has no PlaneA arm" % vdp_emp)
    return int(arm.group(1))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args()

    rom, lst, root = Path(a.rom), Path(a.lst), Path(a.root)
    for p in (rom, lst):
        if not p.is_file():
            raise SystemExit("missing %s — build the DEBUG shape first (DEBUG=1 ./build.sh)" % p)

    effects = root / "games/sonic4/data/effects/ojz_effects.emp"
    line = read_const(effects, "OJZ_BASE_SWAP_LINE")
    plane_a = read_const(root / "engine/system/constants.emp", "VRAM_PLANE_A")
    plane_b = read_const(root / "engine/system/constants.emp", "VRAM_PLANE_B")
    shift = read_plane_a_shift(root / "engine/vdp.emp")
    home_word = 0x8200 | (plane_a >> shift)
    away_word = 0x8200 | (plane_b >> shift)

    sym = parse_lst(str(lst))
    for n in ("OJZ_BaseSwap", "Raster_Pending", "Raster_Program", "Game_RAM_End"):
        if n not in sym:
            raise SystemExit("%s carries no symbol %s — wrong shape? item 11a's program is "
                             "DEBUG-gated and emits zero bytes in release." % (lst, n))
    addr = sym["OJZ_BaseSwap"]

    # THE SECOND SUBJECT, and it is a different DoD row. `OJZ_BaseSwap` is the hand-authored
    # DEBUG fixture; `EditorRaster_OJZ_Act1_ojz_sec6_baseswap` is what `effects_gen.py`
    # LOWERED from section 6's `base_swap` preset document, and it ships in both shapes. The
    # item-11a-authorable booking proves the two are byte-identical in the image; that is a
    # claim about BYTES. Installing the authored one is the only thing that says the
    # generator's output is a program the machine will actually run, and it is a second
    # address, so it is a second measurement rather than a restatement of the first.
    authored = sym.get(AUTHORED_SYM)

    img = rom.read_bytes()
    subject = img[addr:addr + PROG_WORDS * 2]
    words = [int.from_bytes(subject[i:i + 2], "big") for i in range(0, len(subject), 2)]

    print("DERIVED FROM THE TREE, not copied from any booking or design doc")
    print("  fire line          %d          (ojz_effects.emp OJZ_BASE_SWAP_LINE)" % line)
    print("  VRAM_PLANE_A       $%04X       shift %d (vdp.emp PlaneA arm)" % (plane_a, shift))
    print("  VRAM_PLANE_B       $%04X" % plane_b)
    print("  subject word       $%04X      reg $%02X <- $%02X" %
          (away_word, (away_word >> 8) & 0x1F, away_word & 0xFF))
    print("  control word       $%04X      reg $%02X <- $%02X  (the base it already has)" %
          (home_word, (home_word >> 8) & 0x1F, home_word & 0xFF))
    print("  OJZ_BaseSwap       $%06X in %s" % (addr, lst.name))
    print("  program words      %s" % " ".join("%04X" % w for w in words))
    print()

    if words[ARG_WORD] != away_word:
        raise SystemExit(
            "THE ROM IS NOT THE SUBJECT THIS WITNESS DESCRIBES: word %d of OJZ_BaseSwap is "
            "$%04X, but VRAM_PLANE_B folded through PlaneA's shift is $%04X. Either the ROM "
            "is stale against the source, or the op no longer targets Plane B. Refusing to "
            "measure a program whose argument I cannot account for."
            % (ARG_WORD, words[ARG_WORD], away_word))
    if home_word == away_word:
        raise SystemExit(
            "THERE IS NO CONTROL TO BUILD: VRAM_PLANE_A ($%04X) and VRAM_PLANE_B ($%04X) fold "
            "to the SAME reg $02 byte, so the twin would be byte-identical to the subject and "
            "arm 2 would compare a thing with itself. This is the condition ojz_effects.emp's "
            "own ensure refuses at build time." % (plane_a, plane_b))

    twin = bytearray(subject)
    twin[ARG_WORD * 2:ARG_WORD * 2 + 2] = home_word.to_bytes(2, "big")
    twin = bytes(twin)
    differing = [i for i in range(len(subject)) if subject[i] != twin[i]]
    print("THE TWIN: %d byte(s) differ from the subject, at offset(s) %s — word %d only."
          % (len(differing), differing, ARG_WORD))
    print("  subject %s" % subject.hex().upper())
    print("  twin    %s" % twin.hex().upper())
    print()

    # Scratch, derived the way ramp_authored_witness derives it: above the last claimed RAM
    # byte, far below the initial stack pointer, both margins asserted rather than argued.
    ram_end = sym["Game_RAM_End"]
    init_sp = int.from_bytes(img[0:4], "big")
    scratch = (ram_end + 0x1DA) & ~1
    if not (ram_end < scratch and scratch + len(twin) + 0x800 < init_sp):
        raise SystemExit("no safe scratch: Game_RAM_End $%08X, initial SP $%08X, candidate "
                         "$%08X" % (ram_end, init_sp, scratch))

    def arm(tag, install, patch=None):
        prog, mode3, px, track = run(rom, str(lst), sym, install=install, patch=patch)
        got = int(prog[2:] if prog.startswith("0x") else prog, 16)
        if got != install:
            raise SystemExit(
                "%s INSTALLED NOTHING: Raster_Program reads $%06X, not the $%06X we staged. "
                "Every row comparison below would be two runs of the SAME program, which "
                "reads as 'no change' — indistinguishable from a real negative."
                % (tag, got, install))
        print("  %-22s Raster_Program=$%06X  frames %s..%s  %d rows"
              % (tag, got, track[0][1], track[-1][1], len(px)))
        return [h for _, h in px]

    print("ARM 1  CONTROL AGAINST CONTROL — is anything here attributable at all?")
    c1 = arm("control", scratch, (scratch, twin))
    c2 = arm("control (again)", scratch, (scratch, twin))
    moved = [i for i in range(SCREEN_LINES) if c1[i] != c2[i]]
    if moved:
        raise SystemExit(
            "ARM 1 FAILED: %d of %d rows differ between two runs of the IDENTICAL control "
            "(first at line %d). The run is not reproducible, so a difference in arm 2 could "
            "not be attributed to the base swap. Nothing below this line means anything."
            % (len(moved), SCREEN_LINES, moved[0]))
    print("  -> %d of %d rows identical. Differences in arm 2 are attributable.\n"
          % (SCREEN_LINES, SCREEN_LINES))

    n_below_total = SCREEN_LINES - 1 - line
    fails = []

    def compare(tag, subj_addr, note):
        s = arm(tag, subj_addr)
        diff = [i for i in range(SCREEN_LINES) if s[i] != c1[i]]
        above = [i for i in diff if i < line]
        below = [i for i in diff if i > line]
        print()
        print("  %s" % note)
        print("  rows changed            %d of %d" % (len(diff), SCREEN_LINES))
        print("  ABOVE the fire line     %d  (lines 0..%d — must be 0)" % (len(above), line - 1))
        print("  BELOW the fire line     %d of %d  (lines %d..%d)"
              % (len(below), n_below_total, line + 1, SCREEN_LINES - 1))
        if diff:
            print("  first changed row       %d   (fire line %d; a switch partway across the "
                  "fire+1 line is expected)" % (diff[0], line))
        if above:
            fails.append(
                "%s: %d row(s) ABOVE the fire line changed (%s...). The twin differs from the "
                "subject in ONE WORD — the argument of an op that has not run yet at those "
                "lines — so nothing there may move. Something other than the base swap is "
                "varying between the arms, and this result cannot be read as the swap's."
                % (tag, len(above), above[:8]))
        if not below:
            fails.append(
                "%s: NO row below the fire line changed. Either OP_SET_REG never executed, or "
                "the control is not inert, or reg $02 is being restored before the beam "
                "reaches the band. This is the refutation the arm exists to be able to "
                "produce: the picture does NOT depend on the word, and item 11a's on-screen "
                "claim is unsupported." % tag)
        elif len(below) < n_below_total // 2:
            fails.append(
                "%s: only %d of %d rows below the fire line changed. The swap re-points the "
                "whole plane for the rest of the frame, so a minority of changed rows "
                "describes something narrower than the claimed effect — report the shape "
                "rather than passing." % (tag, len(below), n_below_total))
        return diff

    print("ARM 2  THE HAND FIXTURE AGAINST ITS MATCHED TWIN — one word apart")
    d_hand = compare("subject (hand)", addr,
                     "OJZ_BaseSwap $%06X — the DEBUG-gated fixture item 11a shipped." % addr)
    print()

    if authored is None:
        fails.append(
            "ARM 3 DID NOT RUN: %s is absent from %s, so the AUTHORED half of item 11a — the "
            "program effects_gen.py lowered from section 6's base_swap document — has still "
            "never been watched. An absent arm is not a passing one."
            % (AUTHORED_SYM, lst.name))
    else:
        print("ARM 3  THE AUTHORED PROGRAM AGAINST THE SAME TWIN — the generator's own output")
        d_auth = compare("subject (authored)", authored,
                         "%s $%06X — lowered from section 6's base_swap preset document."
                         % (AUTHORED_SYM, authored))
        if d_auth != d_hand:
            only_h = sorted(set(d_hand) - set(d_auth))
            only_a = sorted(set(d_auth) - set(d_hand))
            fails.append(
                "ARM 3 DISAGREES WITH ARM 2: the authored program and the hand fixture are "
                "byte-identical in the image, so they must move the SAME rows. %d row(s) "
                "moved only for the hand one (%s...), %d only for the authored one (%s...). "
                "Byte-identity is a claim about the image; this is the claim about the "
                "machine, and they have come apart."
                % (len(only_h), only_h[:6], len(only_a), only_a[:6]))
        else:
            print()
            print("  -> the authored program moves EXACTLY the rows the hand fixture moves "
                  "(%d of them)." % len(d_auth))
        print()

    if fails:
        print("FAILED")
        for f in fails:
            print("  * %s" % f)
        return 1
    print("PASSED — the picture below the fire line depends on reg $02's value, and nothing")
    print("above it does. The base swap executes mid-frame and its effect is bounded by its")
    print("own schedule, measured against a control identical to it in every byte but one —")
    print("for the hand fixture AND for the program the generator lowered from a document.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
