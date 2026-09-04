#!/usr/bin/env python3
"""base_swap_witness — does EFFECTS-W1 item 11a's mid-frame base swap reach the SCREEN?

The claim is NOT "the program builds" and NOT "the emitted words are right" —
`tools/plane_base_swap_gate.py` proves both, statically, on every canonical build, and its
derivation was proven red four ways. It is that the machine EXECUTES `OP_SET_REG` mid-frame
and the picture INSIDE EACH BAND — and only inside it — changes as a result. The item-11a
booking tags this as owed: "No emulator was used. A green gate is not the picture."

THE CONTROL IS THE WHOLE DESIGN, and it is the one thing a screenshot cannot supply.
Installing ANY raster program REPLACES the act's own, so subject-vs-default and
subject-vs-None both differ on nearly every row for a reason that has nothing to do with
the base swap. `band_witness` measured exactly that (122 of 124 rows moved both ways) and
`ramp_authored_witness` answered it with a matched twin. This witness takes the same
instrument one step further, because item 11a admits a control the ramp could not:

    THE TWIN IS THE SUBJECT'S OWN 46 BYTES WITH TWO WORDS CHANGED — ONE PER BAND.

Words 8 and 16 are the two bands' ON-edge arguments. The subject carries $8406 (reg $04 <-
VRAM_PLANE_A: the FOREGROUND's map in the BACKGROUND layer) and $8238 (reg $02 <-
VRAM_PLANE_B: the BACKGROUND's map in the FOREGROUND layer). The twin substitutes each
register's OWN home base — the value it ALREADY has at frame top — so each op dispatches,
costs the same cycles, writes the same register and changes nothing; each band's OFF edge
then writes that same base a second time, equally inertly. Every confound the replacement
introduces is therefore present in BOTH arms and subtracts out: same program length, same
schedule, same arm words, same op count, same dispatch depth, same displaced act program.
The only surviving difference is the value in each register between that band's two edge
lines, which is precisely the subject.

⚠ THE PROGRAM GREW A SECOND EDGE ON 2026-09-04 (EFFECTS-W1 F2) AND A SECOND BAND ON A SECOND
REGISTER LATER THE SAME DAY (T3), and this witness's REGIONS changed with it — see the
five-region block in `compare` below. It was 11 words and two regions; then 15 and three;
it is now 23 words and FIVE. The new one is THE MIDDLE, between the two bands, and it is the
only assertion here that can tell TWO BOUNDED BANDS from ONE LONG SWAP running from the top
band's ON edge to the bottom band's OFF edge — a program that would satisfy every other
region in this file.

⚠ THE TWIN IS TWO WORDS NOW, AND ONE WOULD BE WORSE THAN NONE. Substituting only the top
band's word would leave the BOTTOM band live in the CONTROL, so the middle region's "must
not move" would be trivially true while the bottom band's "must move" compared the band
against itself. The control has to be inert on BOTH registers or the region it was extended
for measures nothing.

    (`ojz_effects.emp`'s own `ensure`s refuse those words in an AUTHORED program, by name —
    "the SAME word reg $0x already carries at frame top", one per band. That refusal is what
    makes them the right control here: the engine considers each a guaranteed no-op, so the
    twin is inert by the tree's own argument rather than by mine.)

WHY THE TWIN LIVES IN RAM. `ramp_authored_witness` measured that the Rust core refuses ROM
writes outright ("only the work-RAM window is writable"), so the twin is written to scratch
and `Raster_Pending` is pointed at it. `Raster_Install` only stores a pointer and the walker
reads the record through a1, so a record in RAM is walked identically. That also makes this
strictly better than a ROM patch would have been: the subject's bytes are never touched, so
the two arms are two installs of two records rather than one record mutated between runs.

EVERY EXPECTATION IS DERIVED FROM THE TREE AT THE MOMENT OF USE, none typed in:
  * the TOP band's two lines from `OJZ_BASE_SWAP_TOP_LINE` / `OJZ_BASE_SWAP_TOP_END_LINE` in
    games/sonic4/data/effects/ojz_effects.emp
  * the BOTTOM band's two lines from `OJZ_BASE_SWAP_BOT_LINE` / `..._BOT_END_LINE`, which are
    EXPRESSIONS there (`RASTER_MAX_FIRE_LINE - <the top band's>`, the reflection through the
    display's midline) and are resolved through `plane_base_swap_gate.emp_const_expr`
  * the program's address from the .lst passed on the command line
  * all four subject words from the built ROM
  * the two control words from VRAM_PLANE_A / VRAM_PLANE_B (engine/system/constants.emp)
    folded through vdp_base_shift's PlaneA **and PlaneB** arms (engine/vdp.emp) — the shifts
    are 10 and 13 and a witness that used one for both would build a control that is not inert
  * the two register selectors from engine/structs.emp's `VdpShadow` field comments, via
    `plane_base_swap_gate.vdp_shadow_reg` — the same struct that makes Flush_VDP_Shadow
    restore both registers at frame top
This matters more than usual here. `docs/DEFERRED_WORK.md`'s item-11a block still says the
swap fires at line 160 and pins the arm word $8A9D; the owner moved it to line 3 on
2026-09-03 ("I would like to see in the plane swap the fg go to the bg at the top"), F2 gave
it an OFF edge at 64 on 2026-09-04, and T3 added a second band at 159..220 on the OTHER
register the same day, so the ROM now reads $8A00 at word 1, $8A3C at word 3 and $8A5E at
word 5. A witness that had copied the booking's 160 would have predicted an edge that is not
there and reported a FAILURE on a correct ROM.

⚠ THE FIVE-REGION RESULT BELOW HAS NEVER BEEN OBSERVED — IT IS A PREDICTION. T3 changed
this instrument's shape (23 words, five regions, a TWO-word twin) and could not exercise it:
it boots an emulator, and the lane that made the change was a background agent, where
emulator tools deadlock. DO NOT quote a region count from here as evidence until someone
with an emulator runs it and pastes the counts.

    AND THE THREE-REGION TOTALS THAT EXIST DO NOT CARRY FORWARD. This file's own F2 note
    said the three-region shape had never been run; a separate report on 2026-09-04 says it
    WAS run that day and passed with "above 0 rows changed, inside 60/60, below 0". Those
    two statements disagree about whether the run happened, and this file is not the place
    to settle it — because either way those totals describe the ONE-BAND, three-region
    program, and the regions they name no longer exist. 60/60 was the single band's inside
    count; there are now two bands of 60 rows each and a 94-row MIDDLE between them that
    nothing has ever looked at. Carrying the number forward would be a measurement restated
    across the change that invalidated it.

    RUN IT AS:  python3 tools/base_swap_witness.py --rom s4.debug.bin --lst s4.debug.lst
    READ:       ARM 1 must be 224/224 identical, then in ARM 2 and ARM 3 —
                ABOVE 0 · TOP band all of its rows · MIDDLE 0 · BOTTOM band all of its rows ·
                BELOW 0. THE MIDDLE IS THE NEW ONE and it is the whole point: a nonzero
                middle means the two bands are really one long swap.

WHAT *HAS* BEEN EXERCISED HERE, so the distinction is not lost: `--dry-run` (everything up
to the first emulator call) was run against the built s4.debug.bin, exit 0, and its two
refusals were proven red against the COMMITTED baseline 84bb9e4a — each shown applied and
then reversed with `git diff --stat` empty:
  * `middle = list(range(top_end + 1, bot_line))` -> an empty range
        -> exit 1: "THE MIDDLE REGION IS EMPTY (lines 3/64/159/220), so its assertion below
           could not fail and a green would mean nothing." The vacuity guard fires BEFORE
           anything is compared, which is where it has to fire.
  * word 20 of a COPY of the ROM patched $8230 -> $8238 (the bottom band's OFF edge writing
    Plane B, i.e. the band losing its bottom — the exact single-edge failure F2 fixed)
        -> exit 1: "word 20 should be the BOTTOM band's OFF edge ... i.e. $8230, and it is
           $8238." The source was never touched; the subject ROM is not writable by this
           instrument and was not made so.
Clean re-run after both: exit 0. That is evidence about the INSTRUMENT, not about the
picture, and it is deliberately reported separately from the five-region prediction above.

WHAT THIS DOES NOT ESTABLISH, stated because the boundary is where a raster effect fails:
  * It does not pin either transition to an exact line. `raster.emp`'s row-119 note records
    that a bare OP_SET_REG switches its register partway across the fire+1 line (~45%
    across, measured), so each edge's own row is half one picture and half the other. The
    design's §8 Q2 asks exactly this and is open. Rows are compared as WHOLE-ROW hashes, so
    a partial row reads as changed; that is why BOTH edge rows are excluded from the
    assertions and merely printed, and why the two must-not-move regions stop strictly
    short of them.
  * It does not say either band is a RECOGNISABLE copy of the other plane's map. It says
    the picture between a band's two edges depends on the value written to that band's base
    register. Whether that value renders as the intended nametable is a separate claim; the
    gate's red-first mutations cover the words, and a human looking at it covers the taste.
  * It does not attribute the TOP band's change to the BACKGROUND layer. Both arms sample the
    composed frame, so "reg $04's value changes these rows" is what is measured; that the
    changed rows are Plane B's contribution is inference from which register was written.
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
# The BYTE gate's source readers, reused rather than re-implemented: `emp_const_expr` for the
# bottom band's two DERIVED lines and `vdp_shadow_reg` for the two register selectors. Reused
# on purpose — a second copy of either would be a second reader of the same source that can
# disagree with the first, and the disagreement would be invisible.
import plane_base_swap_gate as G  # noqa: E402

PROG_WORDS = 23          # the whole sparse program; asserted against the listing span
# The four edge arguments, in program order. Words 8/16 are the two bands' ON edges (what
# the twin makes inert) and 12/20 are their OFF edges (each band's own home base).
TOP_ON_WORD, TOP_OFF_WORD = 8, 12
BOT_ON_WORD, BOT_OFF_WORD = 16, 20
AUTHORED_SYM = "EditorRaster_OJZ_Act1_ojz_sec6_baseswap"


def read_const(path, name):
    """A named `const NAME = <int>` out of an .emp file. Refuses ambiguity rather than
    taking the first hit — two definitions of one name means the file is not what this
    reader thinks it is.

    ⚠ LITERALS ONLY, AND THAT IS NOW A LIMIT RATHER THAN A POSTURE. Since T3 the bottom
    band's two lines are EXPRESSIONS in the fixture (`RASTER_MAX_FIRE_LINE - ...`), because
    they are the top band's reflected through the display's midline. This reader cannot see
    them; `plane_base_swap_gate.emp_const_expr` can, and is what this file uses for those
    two. `read_const` keeps its shape because tools/role_swap_witness.py imports it.
    """
    src = Path(path).read_text()
    hits = re.findall(r"^\s*(?:pub\s+)?const\s+%s\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$" % name,
                      src, re.M)
    if len(hits) != 1:
        raise SystemExit("%s: expected exactly one `const %s = ...`, found %d. Refusing to "
                         "guess which one the ROM was built from." % (path, name, len(hits)))
    v = hits[0]
    return int(v[1:], 16) if v.startswith("$") else int(v)


def read_plane_shift(vdp_emp, variant):
    """vdp_base_shift's arm for one VdpBase variant. Read rather than assumed: the whole
    point of folding the word through the helper is that a shift change moves the op, and a
    witness that hardcoded 10 would be blind to exactly that.

    ⚠ BOTH PLANES SINCE T3, and they are NOT the same number — PlaneA shifts by 10 and
    PlaneB by 13. A witness that derived one shift and used it for both bands would build a
    control whose "inert" word was not inert.
    """
    src = Path(vdp_emp).read_text()
    m = re.search(r"fn\s+vdp_base_shift.*?\{(.*?)\n\}", src, re.S)
    if not m:
        raise SystemExit("%s: could not find vdp_base_shift" % vdp_emp)
    arm = re.search(r"%s\s*=>\s*(\d+)" % variant, m.group(1))
    if not arm:
        raise SystemExit("%s: vdp_base_shift has no %s arm" % (vdp_emp, variant))
    return int(arm.group(1))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    # --dry-run: everything up to the first emulator call, then stop. Added with T3 for a
    # reason worth stating: this instrument's SHAPE has now been changed twice by lanes that
    # could not boot an emulator, and both times the change shipped with nothing having
    # exercised even the parts that need no emulator — the four source reads, the four ROM
    # words, the two-word twin, and the five regions' arithmetic. Those are exactly where the
    # T3 change lives, and they are checkable in a second. A dry run is NOT the witness and
    # says NOTHING about the picture; it says the instrument is pointed at the program it
    # describes.
    ap.add_argument("--dry-run", action="store_true",
                    help="derive and print everything up to ARM 1, then stop. Proves the "
                         "instrument matches the ROM; proves NOTHING about the screen.")
    a = ap.parse_args()

    rom, lst, root = Path(a.rom), Path(a.lst), Path(a.root)
    for p in (rom, lst):
        if not p.is_file():
            raise SystemExit("missing %s — build the DEBUG shape first (DEBUG=1 ./build.sh)" % p)

    effects = root / "games/sonic4/data/effects/ojz_effects.emp"
    raster = root / "engine/effects/raster.emp"
    top_line = read_const(effects, "OJZ_BASE_SWAP_TOP_LINE")
    top_end = read_const(effects, "OJZ_BASE_SWAP_TOP_END_LINE")
    # The bottom band's lines are DERIVED in the fixture as the top band's reflected through
    # RASTER_MAX_FIRE_LINE, so they are read through the gate's expression reader rather than
    # forcing the fixture to freeze them as literals. One grammar, one spelling: this file
    # does not carry a second evaluator.
    max_fire = G.emp_const(str(raster), "RASTER_MAX_FIRE_LINE")
    env = {"RASTER_MAX_FIRE_LINE": max_fire,
           "OJZ_BASE_SWAP_TOP_LINE": top_line,
           "OJZ_BASE_SWAP_TOP_END_LINE": top_end}
    bot_line = G.emp_const_expr(str(effects), "OJZ_BASE_SWAP_BOT_LINE", env)
    bot_end = G.emp_const_expr(str(effects), "OJZ_BASE_SWAP_BOT_END_LINE", env)

    plane_a = read_const(root / "engine/system/constants.emp", "VRAM_PLANE_A")
    plane_b = read_const(root / "engine/system/constants.emp", "VRAM_PLANE_B")
    shift_a = read_plane_shift(root / "engine/vdp.emp", "PlaneA")
    shift_b = read_plane_shift(root / "engine/vdp.emp", "PlaneB")
    reg_a = G.vdp_shadow_reg("vdp_plane_a")
    reg_b = G.vdp_shadow_reg("vdp_plane_b")
    sel_a, sel_b = 0x8000 | (reg_a << 8), 0x8000 | (reg_b << 8)

    # THE FOUR WORDS. Each band's ON word borrows the OTHER plane's map; each band's HOME
    # word is the base that register already carries at frame top, i.e. what the twin
    # substitutes to make the band inert.
    top_away, top_home = sel_b | (plane_a >> shift_b), sel_b | (plane_b >> shift_b)
    bot_away, bot_home = sel_a | (plane_b >> shift_a), sel_a | (plane_a >> shift_a)

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
    print("  TOP band lines     %d..%d      reg $%02X (Plane B, the BACKGROUND layer)"
          % (top_line, top_end, reg_b))
    print("  BOTTOM band lines  %d..%d  reg $%02X (Plane A, the FOREGROUND layer)"
          % (bot_line, bot_end, reg_a))
    print("  VRAM_PLANE_A       $%04X       shift %d (vdp.emp PlaneA arm)" % (plane_a, shift_a))
    print("  VRAM_PLANE_B       $%04X       shift %d (vdp.emp PlaneB arm)" % (plane_b, shift_b))
    print("  TOP subject word   $%04X      reg $%02X <- $%02X  (the foreground's map)"
          % (top_away, reg_b, top_away & 0xFF))
    print("  TOP control word   $%04X      reg $%02X <- $%02X  (the base it already has)"
          % (top_home, reg_b, top_home & 0xFF))
    print("  BOT subject word   $%04X      reg $%02X <- $%02X  (the background's map)"
          % (bot_away, reg_a, bot_away & 0xFF))
    print("  BOT control word   $%04X      reg $%02X <- $%02X  (the base it already has)"
          % (bot_home, reg_a, bot_home & 0xFF))
    print("  OJZ_BaseSwap       $%06X in %s" % (addr, lst.name))
    print("  program words      %s" % " ".join("%04X" % w for w in words))
    print()

    # ---- THE ROM MUST BE THE SUBJECT THIS FILE DESCRIBES -----------------------------
    # All four edge words are checked, not just the two ON ones. A ROM whose OFF edges are
    # missing or wrong is a DIFFERENT effect — one or both bands running to the bottom of
    # the display — and the region assertions below would then be describing something the
    # program does not do.
    for idx, want, what in ((TOP_ON_WORD, top_away, "the TOP band's ON edge (reg $%02X <- the "
                                                    "foreground's map)" % reg_b),
                            (TOP_OFF_WORD, top_home, "the TOP band's OFF edge (reg $%02X back "
                                                     "to Plane B's own base)" % reg_b),
                            (BOT_ON_WORD, bot_away, "the BOTTOM band's ON edge (reg $%02X <- "
                                                    "the background's map)" % reg_a),
                            (BOT_OFF_WORD, bot_home, "the BOTTOM band's OFF edge (reg $%02X "
                                                     "back to Plane A's own base)" % reg_a)):
        if words[idx] != want:
            raise SystemExit(
                "THE ROM IS NOT THE SUBJECT THIS WITNESS DESCRIBES: word %d should be %s, "
                "i.e. $%04X, and it is $%04X. Either the ROM is stale against the source, or "
                "the program's shape moved. Refusing to measure a program whose words I "
                "cannot account for." % (idx, what, want, words[idx]))
    if top_away == top_home or bot_away == bot_home:
        raise SystemExit(
            "THERE IS NO CONTROL TO BUILD: a band's borrowed base and its own base fold to "
            "the same register word (Plane A $%04X, Plane B $%04X, shifts %d/%d), so the twin "
            "would be byte-identical to the subject and arm 2 would compare a thing with "
            "itself. This is the condition ojz_effects.emp's own ensures refuse at build "
            "time." % (plane_a, plane_b, shift_a, shift_b))

    # ---- THE TWIN: TWO WORDS, ONE PER BAND (T3) --------------------------------------
    # It was ONE word while there was one band. Substituting only the top band's ON word now
    # would leave the BOTTOM band live in the control — and the middle region, the assertion
    # this whole file was extended for, sits between them: a control that still paints the
    # bottom band would make the middle region's "must not move" trivially true while the
    # bottom band's "must move" became a comparison of the band against itself. So BOTH ON
    # edges are made inert, and every confound the replacement introduces is still present in
    # both arms: same program length, same schedule, same arm words, same op count, same
    # dispatch depth, same displaced act program. The only surviving difference is the value
    # in each register between that band's two edge lines.
    twin = bytearray(subject)
    twin[TOP_ON_WORD * 2:TOP_ON_WORD * 2 + 2] = top_home.to_bytes(2, "big")
    twin[BOT_ON_WORD * 2:BOT_ON_WORD * 2 + 2] = bot_home.to_bytes(2, "big")
    twin = bytes(twin)
    differing = [i for i in range(len(subject)) if subject[i] != twin[i]]
    print("THE TWIN: %d byte(s) differ from the subject, at offset(s) %s — words %d and %d "
          "only (the two ON edges)." % (len(differing), differing, TOP_ON_WORD, BOT_ON_WORD))
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

    # ---- THE FIVE REGIONS TWO BANDS HAVE (T3, 2026-09-04) ---------------------------
    # This was THREE regions while there was one band, and TWO before F2 gave that band a
    # bottom. Two bands have five, and the new one in the middle is the load-bearing one:
    #
    #     0 .. top_line-1          ABOVE   — must not move (no op has run yet)
    #     top_line                 the TOP band's ON edge row — PARTIAL, excluded
    #     top_line+1 .. top_end-1  TOP BAND    — must ALL move
    #     top_end                  the TOP band's OFF edge row — PARTIAL, excluded
    #     top_end+1 .. bot_line-1  MIDDLE  — must not move (both registers are home)
    #     bot_line                 the BOTTOM band's ON edge row — PARTIAL, excluded
    #     bot_line+1 .. bot_end-1  BOTTOM BAND — must ALL move
    #     bot_end                  the BOTTOM band's OFF edge row — PARTIAL, excluded
    #     bot_end+1 .. 223         BELOW   — must not move (both registers are home)
    #
    # WHY THE MIDDLE IS THE ONE THAT MATTERS. Every other region here has an analogue in the
    # one-band shape, and a program with a single long swap from line 3 to line 220 would
    # satisfy ABOVE, both BAND regions and BELOW. Only the MIDDLE distinguishes two bounded
    # bands from one long one — it is the assertion that says the top band CLOSED before the
    # bottom band OPENED, and nothing before T3 could make it.
    #
    # THE FOUR EDGE ROWS ARE EXCLUDED, NOT ASSERTED, and that is the honest reading of
    # engine/effects/raster.emp's row-119 measurement: a bare OP_SET_REG switches its
    # register ~45% ACROSS the fire+1 line, so each edge row is half one picture and half the
    # other. Asserting either way there would be asserting a timing this tree has not pinned.
    # They are PRINTED, because where each transition actually lands is the open question the
    # design's §8 Q2 asks.
    top_band = list(range(top_line + 1, top_end))
    middle = list(range(top_end + 1, bot_line))
    bot_band = list(range(bot_line + 1, bot_end))
    below = list(range(bot_end + 1, SCREEN_LINES))
    edges = (top_line, top_end, bot_line, bot_end)
    # A region that is EMPTY cannot fail, and a green on it would be a gate measuring
    # nothing (this tree has shipped that mistake). The fixture's own ensures make all four
    # non-empty; this is the arm that says so if they ever stop.
    for tag, region in (("TOP band", top_band), ("MIDDLE", middle),
                        ("BOTTOM band", bot_band), ("BELOW", below)):
        if not region:
            raise SystemExit(
                "THE %s REGION IS EMPTY (lines %d/%d/%d/%d), so its assertion below could "
                "not fail and a green would mean nothing. ojz_effects.emp's own ensures "
                "refuse this at build time; seeing it here means one of them is no longer "
                "running." % (tag, top_line, top_end, bot_line, bot_end))

    if a.dry_run:
        print("THE FIVE REGIONS, derived:")
        print("  ABOVE        lines 0..%d          %d row(s), must not move"
              % (top_line - 1, top_line))
        print("  TOP band     lines %d..%d        %d row(s), must ALL move"
              % (top_band[0], top_band[-1], len(top_band)))
        print("  MIDDLE       lines %d..%d      %d row(s), must not move  <- the assertion "
              "that tells two bands from one long swap" % (middle[0], middle[-1], len(middle)))
        print("  BOTTOM band  lines %d..%d    %d row(s), must ALL move"
              % (bot_band[0], bot_band[-1], len(bot_band)))
        print("  BELOW        lines %d..%d    %d row(s), must not move"
              % (below[0], below[-1], len(below)))
        print("  EDGE rows    %s — PARTIAL rows, excluded from every assertion"
              % ", ".join(str(e) for e in edges))
        print()
        print("DRY RUN — no emulator was started, so NOTHING here says the picture changes.")
        print("The instrument is pointed at the program it describes; run without --dry-run")
        print("to find out what the machine does with it.")
        return 0

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

    fails = []

    def compare(tag, subj_addr, note):
        s = arm(tag, subj_addr)
        diff = [i for i in range(SCREEN_LINES) if s[i] != c1[i]]
        above_rows = [i for i in diff if i < top_line]
        in_top = [i for i in diff if i in top_band]
        in_mid = [i for i in diff if i in middle]
        in_bot = [i for i in diff if i in bot_band]
        in_below = [i for i in diff if i in below]
        on_edges = [i for i in diff if i in edges]
        print()
        print("  %s" % note)
        print("  rows changed            %d of %d" % (len(diff), SCREEN_LINES))
        print("  ABOVE everything        %d  (lines 0..%d — must be 0)"
              % (len(above_rows), top_line - 1))
        print("  INSIDE the TOP band     %d of %d  (lines %d..%d — must be all)"
              % (len(in_top), len(top_band), top_band[0], top_band[-1]))
        print("  the MIDDLE              %d  (lines %d..%d — must be 0; THIS is what tells "
              "two bands from one long swap)" % (len(in_mid), middle[0], middle[-1]))
        print("  INSIDE the BOTTOM band  %d of %d  (lines %d..%d — must be all)"
              % (len(in_bot), len(bot_band), bot_band[0], bot_band[-1]))
        print("  BELOW everything        %d  (lines %d..%d — must be 0)"
              % (len(in_below), below[0], below[-1]))
        print("  the four EDGE rows      %s  (lines %s — partial rows, not asserted)"
              % (on_edges or "none", ", ".join(str(e) for e in edges)))
        if diff:
            print("  first changed row       %d   (TOP ON edge at %d; a switch partway across "
                  "the edge+1 row is expected)" % (diff[0], top_line))
            print("  last  changed row       %d   (BOTTOM OFF edge at %d)" % (diff[-1], bot_end))
        if above_rows:
            fails.append(
                "%s: %d row(s) ABOVE both bands changed (%s...). The twin differs from the "
                "subject in TWO WORDS — the arguments of two ops, neither of which has run "
                "yet at those lines — so nothing there may move. Something other than the "
                "base swaps is varying between the arms, and this result cannot be read as "
                "theirs." % (tag, len(above_rows), above_rows[:8]))
        for btag, got_rows, region, reg, borrowed in (
                ("TOP", in_top, top_band, reg_b, plane_a),
                ("BOTTOM", in_bot, bot_band, reg_a, plane_b)):
            if not got_rows:
                fails.append(
                    "%s: NO row inside the %s band changed. Either its OP_SET_REG never "
                    "executed, or the control is not inert on reg $%02X, or that register is "
                    "being restored before the beam reaches the band. This is the refutation "
                    "the arm exists to be able to produce: the picture does NOT depend on the "
                    "word, and the claim that reg $%02X borrows $%04X on screen is "
                    "unsupported." % (tag, btag, reg, reg, borrowed))
            elif len(got_rows) < len(region):
                missed = [i for i in region if i not in diff]
                fails.append(
                    "%s: only %d of %d rows inside the %s band changed (%s... unchanged). The "
                    "swap re-points the whole plane for every line between that band's two "
                    "edges, so a hole in it describes something narrower than the claimed "
                    "effect — report the shape rather than passing."
                    % (tag, len(got_rows), len(region), btag, missed[:8]))
        if in_mid:
            fails.append(
                "%s: %d row(s) in the MIDDLE changed (%s...). THIS IS THE ASSERTION THE "
                "FIVE-REGION SHAPE EXISTS FOR. Between line %d and line %d both base "
                "registers are home, so the two arms must be identical there. Rows moving in "
                "the middle mean the top band did not CLOSE before the bottom band OPENED — "
                "i.e. this is one long swap wearing two bands' clothes, which is the exact "
                "failure a three-region witness could not see."
                % (tag, len(in_mid), in_mid[:8], top_end, bot_line))
        if in_below:
            fails.append(
                "%s: %d row(s) BELOW everything changed (%s...). The bottom band's OFF edge "
                "writes Plane A's own base back at line %d, so everything under it must be "
                "identical in both arms. Rows moving there mean the bottom band has NO "
                "BOTTOM — which is exactly the single-edge program F2 replaced, the one that "
                "covers the rest of the screen and reads as no band at all."
                % (tag, len(in_below), in_below[:8], bot_end))
        return diff

    print("ARM 2  THE HAND FIXTURE AGAINST ITS MATCHED TWIN — two words apart")
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
    print("PASSED — the picture inside EACH band depends on the value in THAT band's base")
    print("register, and the picture above them, BETWEEN them, and below them does not. Two")
    print("bounded bands on two registers, each closed mid-frame rather than at the VBlank")
    print("shadow flush, measured against a control identical to the subject in every byte")
    print("but two — for the hand fixture AND for the program the generator lowered from a")
    print("document.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
