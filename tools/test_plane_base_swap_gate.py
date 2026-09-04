"""Unit cover for `tools/plane_base_swap_gate.py` — the pure halves, plus the source reads.

WHY THIS FILE IS PURE-FUNCTION AND SOURCE-READING ONLY, and never opens a ROM:
build.sh's pytest lane runs BEFORE the sigil build (build.sh:61-72 — a unit test opening
`s4.debug.bin` would grade a PREVIOUS build, which has bitten this tree twice). The gate's
ROM half therefore runs post-sigil, in build.sh, with `--built-after`. What is covered here
is the two pieces of judgement the gate adds — the word derivation and the gap
classification — plus the four facts it reads out of engine source, which are exactly the
facts a source-level regression would break before any ROM existed.

PROVEN RED, by editing a COMMITTED baseline and restoring it, 2026-09-03. Four mutations,
each shown applied on disk (`git diff -U0`) before the run, each restored with
`git checkout HEAD -- <path>` afterwards. Every count below is the whole run, not a tail.

⚠ THE 2026-09-03 AND F2 LEDGERS BELOW ARE HISTORY, NOT STANDING CLAIMS. T3 (2026-09-04)
changed `expected_words`' signature and word layout and renamed three of the tests these
rows name, so their counts describe a file that no longer exists and none of them was
re-run. They are kept because the REASONING in them still holds (what the mutation was
reaching for, and the two documented traps: a shift change that does not collide, and an
assertion on the exception type that a different guard satisfies). The standing red-first
evidence for this file is T3's LEDGER at the bottom:

  * `PlaneA => 10` -> `=> 16` in engine/vdp.emp's `vdp_base_shift`
        -> 3 failed, 5 passed. test_the_two_planes_fold_to_different_reg02_bytes fires
           first ("both fold to reg $02 word $8200"); the two derivation tests then fail
           through `expected_words`' own degenerate-case refusal.
        NOTE the mutation that does NOT work, so nobody wastes a run reproducing it:
           `=> 13` leaves $C000 and $E000 folding to 6 and 7 — still different — so it is
           green here. The arm is about the two bases COLLIDING, not about the shift's
           value, and only a shift wide enough to erase the difference reaches it.
  * `OJZ_BASE_SWAP_LINE = 160` -> `2` in the fixture
        -> 2 failed, 6 passed (test_the_fixtures_line_is_a_schedulable_screen_line and
           the framing pin; fire line 1 gives a priming gap of -1, not a legal reload).
           `-> 3` is green: 3 is the lowest line `fire()` itself admits.
  * `pub const OP_SET_REG = 0` -> `= 1` in engine/effects/raster.emp
        -> 1 failed, 7 passed (test_op_set_reg_is_still_zero).
  * `classify_gap`'s `return None` -> `return "absent"`
        -> 1 failed, 7 passed (test_an_unrecognised_gap_is_not_classified).
  * `expected_words`' degenerate-case `if word == home:` -> `if 0:`
        -> 1 failed, 7 passed (test_two_identical_plane_bases_are_UNMEASURABLE_not_a_pass).

The gate's own ROM arms are proven red in the parcel's DEFERRED_WORK entry, not here:
they need a build, and a build is what this lane runs before.

---- F2's LEDGER (2026-09-04), the two-edge arms ----------------------------------------
The mutations above predate the OFF edge; every one of them still applies (the derivation
they poke is the same one) and the counts move only because this file now carries 11 tests
instead of 8. Three NEW mutations, each shown applied on disk (`git diff -U0`) before its
run, each reversed afterwards — reversed rather than `git checkout`ed, because the parcel's
own work was uncommitted for part of this and a checkout would have deleted it. Whole-run
totals, never a tail:

  * `expected_words`' OFF-edge argument, `op_set_reg, home` -> `op_set_reg, word`
        -> 1 failed, 10 passed (test_the_two_edges_carry_DIFFERENT_register_words).
           This is the mutation that turns the band back into the program that shipped:
           two ops, both writing Plane B, no bottom edge. Nothing else in this file
           notices — the framing, the arm chain and both opcodes are unchanged by it,
           which is why that test exists separately.
  * `expected_words`' ordering guard, `if end_fire_line <= fire_line:` -> `if False:`
        -> 1 failed, 10 passed (test_an_OFF_edge_at_or_above_the_ON_edge_is_DIAGNOSED_as_ordering).
           ⚠ AND IT WAS GREEN ON THE FIRST ATTEMPT — 11 passed, 0 failed — with the guard
           deleted. The test asserted only "raises Unmeasurable", and an inverted pair
           makes the ON->OFF gap negative, so the WIDTH guard below caught it and raised
           the same exception with a sentence about a band "wider than one reload": the
           opposite diagnosis, reported as a pass. The test now asserts the MESSAGE, and
           the mutation above is its re-run after that tightening. The earlier claim in
           this ledger (the `home` -> `word` row) was re-established against the tightened
           file and is the count printed there.
  * `expected_words`' width guard, `if not 0 <= (end_fire_line - fire_line - 1) <= 255:`
        -> `if False:`
        -> 1 failed, 10 passed (test_a_band_wider_than_one_reload_is_UNMEASURABLE_not_a_pass).

The GATE's own two-edge ROM arms were proven red on the built `s4.debug.bin` (word 12
patched $8230 -> $8238 in a COPY: exit 1, naming the OFF edge's register word AND the
both-edges-identical arm; word 11 patched $0000 -> $0001: exit 1, naming the missing OFF
opcode) and by mutating `OJZ_BASE_SWAP_END_LINE` 64 -> 96 in the fixture and re-running
against the unmodified ROM (exit 1 at word 3, the arm that carries the ON->OFF gap).

---- T3's LEDGER (2026-09-04), the two-BAND, two-REGISTER arms --------------------------
The subject moved again the same day: 15 words on one register became 23 on two. The F2
mutations above are NOT re-run and are NOT re-claimed — every one of them poked a call
signature and a word layout that no longer exist, so quoting their counts here would be a
result restated across a change that invalidated it. What replaces them, each shown applied
on disk (`git diff -U0`) before its run and REVERSED afterwards (reversed, not
`git checkout`ed: this parcel's own work was uncommitted while the runs happened):

  * `expected_words`' top-band word, `sel_b | (plane_a >> shift_b)` -> `sel_b | (plane_b
    >> shift_b)` — the top band borrowing its OWN map, i.e. a silent no-op on screen
        -> 5 failed, 12 passed. `test_the_two_bands_borrow_from_EACH_OTHER` is the arm
           aimed at it; the other four fail through the degenerate-case refusal inside
           `expected_words`, which raises on EVERY call once the two words collide.
        ⚠ THE SPREAD IS THE POINT AND ALSO THE LIMIT. A mutation that makes the
           derivation raise takes out every test that calls it, so a wide red here is NOT
           evidence that four independent checks noticed four things — three of those
           four are the same refusal reported four times. The narrow mutation below is
           the one that measures whether a single arm is load-bearing.
  * `expected_words`' bottom-band selector, `sel_a | (plane_b >> shift_a)` -> `sel_b |
    (plane_b >> shift_a)` — BOTH bands on reg $04, the failure T3 exists to rule out
        -> 2 failed, 15 passed (test_the_two_bands_write_DIFFERENT_registers and
           test_the_two_bands_borrow_from_EACH_OTHER). NOTHING ELSE NOTICES: the framing,
           the arm chain, all four opcodes, the band widths and the reflection are
           unchanged by it, and the image is still 23 well-formed words. That is exactly
           why those two tests are stated separately from the framing pin.
  * `vdp_shadow_reg`'s regex, `reg\\s+\\$` -> `reg\\s+#`
        -> 7 failed, 10 passed. Every arm that needs a register number reports
           UNMEASURABLE naming the VdpShadow field it could not parse — never a wrong
           number, which is the property being checked.
  * `emp_const_expr`'s sign handling, `sign * v` -> `v`
        -> 5 failed, 12 passed. `test_the_bottom_band_is_the_top_band_REFLECTED` names the
           reflection; the bottom band reads 287/226 instead of 159/220, which is
           non-ascending against nothing and pushes the rest through the ordering refusal.
           The failure is reported as a reflection/ordering fault, never as a byte
           mismatch — which is the diagnosis this reader exists to keep honest.

Each of the four was shown applied with `git diff -U0` before its run and reversed
afterwards; `git diff --stat` was empty after each reversal, and the file was re-run green
(17 passed) after the last one. `__pycache__` was cleared before every one of the five runs.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import plane_base_swap_gate as G  # noqa: E402


# ---------------------------------------------------------------------------
# The facts, read out of engine source. Not copies: the same calls the gate makes.
# ---------------------------------------------------------------------------

def _facts():
    max_fire = G.emp_const(G.RASTER, "RASTER_MAX_FIRE_LINE")
    top_line = G.emp_const(G.FIXTURE, "OJZ_BASE_SWAP_TOP_LINE")
    top_end = G.emp_const(G.FIXTURE, "OJZ_BASE_SWAP_TOP_END_LINE")
    env = {"RASTER_MAX_FIRE_LINE": max_fire,
           "OJZ_BASE_SWAP_TOP_LINE": top_line,
           "OJZ_BASE_SWAP_TOP_END_LINE": top_end}
    return dict(
        plane_a=G.emp_const(G.CONSTANTS, "VRAM_PLANE_A"),
        plane_b=G.emp_const(G.CONSTANTS, "VRAM_PLANE_B"),
        shift_a=G.vdp_base_shift("PlaneA"),
        shift_b=G.vdp_base_shift("PlaneB"),
        reg_a=G.vdp_shadow_reg("vdp_plane_a"),
        reg_b=G.vdp_shadow_reg("vdp_plane_b"),
        op_set_reg=G.emp_const(G.RASTER, "OP_SET_REG"),
        park=G.emp_const(G.RASTER, "RASTER_ARM_PARK"),
        ops_end=G.emp_const(G.RASTER, "RASTER_OPS_END"),
        max_fire=max_fire,
        top_line=top_line,
        top_end=top_end,
        bot_line=G.emp_const_expr(G.FIXTURE, "OJZ_BASE_SWAP_BOT_LINE", env),
        bot_end=G.emp_const_expr(G.FIXTURE, "OJZ_BASE_SWAP_BOT_END_LINE", env),
    )


def _want(f):
    """The derived image, from the facts dict — ONE spelling of the call, so a signature
    change lands in one place instead of in every test."""
    return G.expected_words(f["top_line"], f["top_end"], f["bot_line"], f["bot_end"],
                            f["plane_a"], f["plane_b"], f["shift_a"], f["shift_b"],
                            f["reg_a"], f["reg_b"],
                            f["op_set_reg"], f["park"], f["ops_end"])


# A legal two-band, two-register argument set that does NOT read the tree, for the arms
# that poke the derivation with values the fixture never carries. Kept beside the real
# facts on purpose: a test that mutated `_facts()` to make its point would be measuring
# the reader, not the derivation.
_SYNTH = dict(plane_a=0xC000, plane_b=0xE000, shift_a=10, shift_b=13, reg_a=2, reg_b=4,
              op_set_reg=0, park=0x8AFF, ops_end=0xFFFF)


def _synth(top_line=3, top_end=64, bot_line=159, bot_end=220, **over):
    a = dict(_SYNTH)
    a.update(over)
    return G.expected_words(top_line, top_end, bot_line, bot_end,
                            a["plane_a"], a["plane_b"], a["shift_a"], a["shift_b"],
                            a["reg_a"], a["reg_b"],
                            a["op_set_reg"], a["park"], a["ops_end"])


def test_the_two_planes_fold_to_different_bytes_on_BOTH_registers():
    """The effect is only demonstrable while each plane's own base and the base it borrows
    fold to different bytes ON THE REGISTER THAT BAND WRITES.

    ⚠ IT IS TWO CHECKS, NOT ONE, AND THAT IS T3's WHOLE POINT. The two bands write reg $02
    and reg $04, whose shifts are 10 and 13 — a re-layout or a shift change can collapse
    one band's difference while leaving the other's intact, and a single check over reg $02
    would call that program correct. The `.emp` fixture carries the same pair of ensures;
    this is the arm that fires in the pytest lane, before a ROM exists.
    """
    f = _facts()
    for tag, sel, shift in (("TOP (background layer)", 0x8000 | (f["reg_b"] << 8), f["shift_b"]),
                            ("BOTTOM (foreground layer)", 0x8000 | (f["reg_a"] << 8), f["shift_a"])):
        a = sel | (f["plane_a"] >> shift)
        b = sel | (f["plane_b"] >> shift)
        assert a != b, (
            f"the {tag} band: VRAM_PLANE_A ${f['plane_a']:04X} and VRAM_PLANE_B "
            f"${f['plane_b']:04X} both fold to ${a:04X} under selector ${sel:04X} at shift "
            f"{shift}. That band re-points a register at the base it already has — no "
            f"mid-frame swap left to demonstrate.")


def test_the_two_bands_write_DIFFERENT_registers():
    """THE T3 INVERSION, stated on the derivation rather than on the prose.

    Plane A's nametable base is one VDP register and Plane B's is another; the owner's ask
    names two LAYERS ("the foreground in the background layer at the top and the background
    in the foreground layer at the bottom"), so the two bands must land on two registers. A
    program with both bands on one register is ordered, assembles, emits two visible bands,
    and is two copies of the same borrow. Every other assertion in this file holds for it,
    which is why this one is separate.
    """
    f = _facts()
    assert f["reg_a"] != f["reg_b"], (
        f"VdpShadow's vdp_plane_a and vdp_plane_b both name reg ${f['reg_a']:02X}")
    want = _want(f)
    assert (want[8] & 0xFF00) != (want[16] & 0xFF00), (
        f"the top band's ON word ${want[8]:04X} and the bottom band's ${want[16]:04X} carry "
        f"the same register selector — that is two of one effect, not an inversion")


def test_the_two_bands_borrow_from_EACH_OTHER():
    """Direction, not just difference. The top band's ON word must point the BACKGROUND
    layer's register at the FOREGROUND's nametable, and the bottom band's the other way.

    A program where both bands borrowed in the same direction (say both pointing at Plane
    B) would still write two registers, still show two bands, and still pass the selector
    test above.
    """
    f = _facts()
    want = _want(f)
    sel_a, sel_b = 0x8000 | (f["reg_a"] << 8), 0x8000 | (f["reg_b"] << 8)
    assert want[8] == sel_b | (f["plane_a"] >> f["shift_b"]), \
        "the TOP band's ON edge must point reg $04 at VRAM_PLANE_A (the foreground's map)"
    assert want[12] == sel_b | (f["plane_b"] >> f["shift_b"]), \
        "the TOP band's OFF edge must return reg $04 to VRAM_PLANE_B"
    assert want[16] == sel_a | (f["plane_b"] >> f["shift_a"]), \
        "the BOTTOM band's ON edge must point reg $02 at VRAM_PLANE_B (the background's map)"
    assert want[20] == sel_a | (f["plane_a"] >> f["shift_a"]), \
        "the BOTTOM band's OFF edge must return reg $02 to VRAM_PLANE_A"


def test_the_register_numbers_come_from_the_struct_that_makes_them_SHADOWED():
    """reg $02 and reg $04, read out of engine/structs.emp's VdpShadow field comments.

    NOT a formatting preference. The whole reason neither band needs a frame-top reset word
    is that both registers are in VdpShadow and Flush_VDP_Shadow walks the table with no
    filter. A register number typed into this gate would go on being right about the
    SELECTOR after the register left the struct — i.e. after the band started leaking into
    the next frame — so the number is read from the fact it depends on.
    """
    assert G.vdp_shadow_reg("vdp_plane_a") == 2
    assert G.vdp_shadow_reg("vdp_plane_b") == 4
    try:
        G.vdp_shadow_reg("vdp_plane_c")
    except G.Unmeasurable:
        return
    raise AssertionError("vdp_shadow_reg invented a register for a field that is not there")


def test_op_set_reg_is_still_zero():
    """OP_SET_REG's VALUE is load-bearing, and this reads it out of the engine.

    Not a restatement of the gate: `expected_words` puts whatever it is handed at the four
    opcode words, so nothing downstream would notice a renumbering.
    `engine/effects/raster.emp` says why zero matters — `Raster_HInt`'s `.op_loop`
    dispatches a register write on the Z flag that `move.w (a1)+, d1` sets while FETCHING
    the op, which is only the OP_SET_REG test while the opcode is zero — and item 11a is
    entirely that path.
    """
    assert G.emp_const(G.RASTER, "OP_SET_REG") == 0


def test_the_bottom_band_is_the_top_band_REFLECTED():
    """The fixture DERIVES the bottom band's lines; this re-derives them independently.

    `OJZ_BASE_SWAP_BOT_LINE` is `RASTER_MAX_FIRE_LINE - OJZ_BASE_SWAP_TOP_END_LINE` in the
    source, not a literal, and `emp_const_expr` is what lets this gate read that without
    forcing the fixture to freeze 159 and 220 into itself. The identity below is what the
    reflection MEANS, so it is asserted rather than the two numbers: equal widths, equal
    margins at top and bottom, and a middle region centred on the display.
    """
    f = _facts()
    assert f["bot_line"] == f["max_fire"] - f["top_end"]
    assert f["bot_end"] == f["max_fire"] - f["top_line"]
    assert f["top_end"] - f["top_line"] == f["bot_end"] - f["bot_line"], \
        "the reflection makes the two bands the same width"
    assert f["top_line"] == f["max_fire"] - f["bot_end"], \
        "the margin above the top band equals the margin below the bottom one"
    assert f["top_end"] + 1 <= f["bot_line"] - 1, \
        "the two bands must leave at least one whole row between them, or the witness's " \
        "middle-region assertion measures an empty range"


def test_the_program_is_the_documented_sparse_framing():
    """One header word, two priming records, FOUR event records, one terminator.

    A STRUCTURAL PIN on `expected_words`, not an independent measurement of the ROM: it
    holds the derivation to the schedule engine/effects/raster.emp documents, so a refactor
    that moved an opcode or dropped a priming record fails here rather than in a byte diff
    nobody can read.
    """
    f = _facts()
    want = _want(f)
    assert len(want) == 23, f"the derived image is {len(want)} words, not 23"
    assert want[0] == 0, "a program of register writes only dirties no palette line"
    assert want[1] == 0x8A00 | (f["top_line"] - 3), \
        "record 0's arm schedules the top band's ON edge"
    assert want[3] == 0x8A00 | (f["top_end"] - f["top_line"] - 1), \
        "record 1's arm is the TOP band's width"
    assert want[5] == 0x8A00 | (f["bot_line"] - f["top_end"] - 1), \
        "record 2's arm is the MIDDLE — the gap between the two bands"
    assert want[9] == 0x8A00 | (f["bot_end"] - f["bot_line"] - 1), \
        "record 3's arm is the BOTTOM band's width"
    assert want[3] == want[9], \
        "the reflection makes the two bands equal, so their two arm words are the same word"
    assert want[2] == 0 and want[4] == 0, "both priming records carry zero ops"
    assert want[13] == f["park"] and want[17] == f["park"], \
        "nothing follows the bottom band, so its two records park"
    assert all(want[i] == 1 for i in (6, 10, 14, 18)), \
        "each edge record carries exactly one op"
    assert all(want[i] == f["op_set_reg"] for i in (7, 11, 15, 19)), \
        "all four edges are OP_SET_REG"
    assert want[-2] == f["park"] and want[-1] == f["ops_end"]


def test_the_fixtures_lines_are_schedulable_screen_lines():
    """All four authored lines must produce legal reg $0A reloads for their gaps."""
    _want(_facts())


def test_a_non_ascending_program_is_DIAGNOSED_as_ordering():
    """A non-ascending fire-line list is a source fault, never a byte mismatch.

    `fire_lines` refuses it at build time, so a ROM carrying it cannot exist — and a gate
    that answered such a program with a word-by-word diff would blame the ROM for a fixture
    that never assembled.

    ⚠ THE ASSERTION IS ON THE MESSAGE, NOT ON THE EXCEPTION, and that is the whole test.
    Written the obvious way — "it raises Unmeasurable" — the F2 version of this passed with
    the ordering guard DELETED (measured 2026-09-04: 11 passed, 0 failed), because an
    inverted pair also makes a gap negative and the WIDTH guard caught it with the opposite
    diagnosis. The guard earns its place by DIAGNOSING, so the diagnosis is asserted. All
    THREE joints are exercised — inside the top band, between the bands, inside the bottom
    one — because T3 added two more places for the list to stop ascending.
    """
    for kw in (dict(top_end=3), dict(top_end=2), dict(bot_line=64), dict(bot_end=159)):
        try:
            _synth(**kw)
        except G.Unmeasurable as e:
            assert "does not follow" in str(e), (
                f"{kw} was refused, but not as an ORDERING fault: {e}")
            continue
        raise AssertionError(f"expected_words accepted {kw} and produced an image")


def test_a_gap_wider_than_one_reload_is_UNMEASURABLE_not_a_pass():
    """Every gap is ONE reg $0A reload byte, so none can exceed 255 lines.

    Unreachable from `fire()`'s own 3..223 bound today — which is precisely why it is
    asserted on the DERIVATION rather than left implicit: this function is the pure half
    other lanes call with values the fixture never carries, and a gap byte that wrapped
    would encode a schedule nothing on screen matches.
    """
    try:
        _synth(top_end=3 + 257, bot_line=3 + 258, bot_end=3 + 259)
    except G.Unmeasurable:
        return
    raise AssertionError("expected_words accepted a 257-line band and produced an image")


def test_two_identical_plane_bases_are_UNMEASURABLE_not_a_pass():
    """The derivation refuses the degenerate case rather than emitting a no-op image."""
    try:
        _synth(plane_b=0xC000)
    except G.Unmeasurable as e:
        assert "band" in str(e), f"refused, but without naming which band: {e}"
        return
    raise AssertionError(
        "expected_words accepted two identical plane bases and produced an image; the "
        "gate would then pass on a program that re-points a plane at its own base")


def test_two_bands_on_ONE_register_are_UNMEASURABLE_not_a_pass():
    """The other degenerate case, and the one T3 introduced. If both bands wrote the same
    register the image would still be 23 well-formed words."""
    try:
        _synth(reg_b=2)
    except G.Unmeasurable as e:
        assert "selector" in str(e), f"refused, but not as a register collision: {e}"
        return
    raise AssertionError("expected_words accepted two bands on one register")


# ---------------------------------------------------------------------------
# emp_const_expr — the reader that lets the fixture keep its derivation.
# ---------------------------------------------------------------------------

def test_emp_const_expr_refuses_a_name_it_has_not_derived():
    """Never a guess and never a zero: an unresolved name is UNMEASURABLE, naming both the
    missing name and what the reader does know."""
    try:
        G.emp_const_expr(G.FIXTURE, "OJZ_BASE_SWAP_BOT_LINE", {})
    except G.Unmeasurable as e:
        assert "RASTER_MAX_FIRE_LINE" in str(e)
        return
    raise AssertionError("emp_const_expr resolved a name it was never given")


def test_emp_const_expr_refuses_anything_outside_its_tiny_grammar():
    """Names and integers joined by + and -, and nothing else. A reader that could evaluate
    more would be a second, weaker evaluator whose disagreements with sigil are invisible —
    so the grammar is small and everything outside it is refused by name."""
    try:
        G.emp_const_expr(G.RASTER, "RASTER_STATE_SIZE", {})
    except G.Unmeasurable as e:
        assert "grammar" in str(e) or "names" in str(e), e
        return
    raise AssertionError("emp_const_expr evaluated an expression outside its grammar")


# ---------------------------------------------------------------------------
# The gap classifier — the two-sided shape assertion, in all three states.
# ---------------------------------------------------------------------------

def test_a_full_image_gap_is_emitted():
    assert G.classify_gap(46, 46) == "emitted"


def test_a_zero_gap_is_absent():
    assert G.classify_gap(0, 46) == "absent"


def test_an_unrecognised_gap_is_not_classified():
    """Neither the image nor zero must be reported as UNMEASURABLE, never chosen for.

    If this ever returns a string, the gate has started guessing which shape it is
    looking at from a length it does not recognise — and the release arm's whole value
    is that it can tell "correctly absent" from "silently truncated"."""
    assert G.classify_gap(10, 46) is None
    assert G.classify_gap(48, 46) is None
    # THE TWO EARLIER IMAGES ARE THE LENGTHS THAT MATTER HERE. 22 bytes is what this program
    # emitted before F2 gave it an OFF edge; 30 is what it emitted between F2 and T3, with
    # one band on one register. A tree half-reverted to either lands on that length, and it
    # must read as UNMEASURABLE — never as "absent" (which the release arm treats as
    # CORRECT) and never as "emitted".
    assert G.classify_gap(22, 46) is None
    assert G.classify_gap(30, 46) is None
