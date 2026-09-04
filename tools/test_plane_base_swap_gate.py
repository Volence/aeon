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
`git checkout HEAD -- <path>` afterwards. Every count below is the whole run, not a tail:

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
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import plane_base_swap_gate as G  # noqa: E402


# ---------------------------------------------------------------------------
# The four facts, read out of engine source. Not copies: the same calls the gate makes.
# ---------------------------------------------------------------------------

def _facts():
    return dict(
        plane_a=G.emp_const(G.CONSTANTS, "VRAM_PLANE_A"),
        plane_b=G.emp_const(G.CONSTANTS, "VRAM_PLANE_B"),
        shift=G.vdp_base_shift("PlaneA"),
        op_set_reg=G.emp_const(G.RASTER, "OP_SET_REG"),
        park=G.emp_const(G.RASTER, "RASTER_ARM_PARK"),
        ops_end=G.emp_const(G.RASTER, "RASTER_OPS_END"),
        line=G.emp_const(G.FIXTURE, "OJZ_BASE_SWAP_LINE"),
        end_line=G.emp_const(G.FIXTURE, "OJZ_BASE_SWAP_END_LINE"),
    )


def _want(f):
    """The derived image, from the facts dict — ONE spelling of the call, so a signature
    change lands in one place instead of in every test."""
    return G.expected_words(f["line"], f["end_line"], f["plane_b"], f["plane_a"],
                            f["shift"], f["op_set_reg"], f["park"], f["ops_end"])


def test_the_two_planes_fold_to_different_reg02_bytes():
    """Item 11a is only demonstrable while Plane A and Plane B fold to different bytes.

    If a re-layout ever put them on one base — or if `vdp_base_shift`'s PlaneA arm moved
    far enough to drop the difference — the op would re-point Plane A at the base it
    already has: a no-op on screen that every byte-level check would still call correct.
    The `.emp` fixture refuses it too; this is the arm that fires in the pytest lane,
    before a ROM exists.
    """
    f = _facts()
    a = 0x8200 | (f["plane_a"] >> f["shift"])
    b = 0x8200 | (f["plane_b"] >> f["shift"])
    assert a != b, (
        f"VRAM_PLANE_A ${f['plane_a']:04X} and VRAM_PLANE_B ${f['plane_b']:04X} both fold "
        f"to reg $02 word ${a:04X} at vdp_base_shift(PlaneA) = {f['shift']}. There is no "
        f"mid-frame swap left to demonstrate.")


def test_op_set_reg_is_still_zero():
    """OP_SET_REG's VALUE is load-bearing, and this reads it out of the engine.

    Not a restatement of the gate: `expected_words` puts whatever it is handed at word 7,
    so nothing downstream would notice a renumbering. `engine/effects/raster.emp` says why
    zero matters — `Raster_HInt`'s `.op_loop` dispatches a register write on the Z flag
    that `move.w (a1)+, d1` sets while FETCHING the op, which is only the OP_SET_REG test
    while the opcode is zero — and item 11a is entirely that path.
    """
    assert G.emp_const(G.RASTER, "OP_SET_REG") == 0


def test_the_program_is_the_documented_sparse_framing():
    """One header word, two priming records, one event record, one terminator.

    A STRUCTURAL PIN on `expected_words`, not an independent measurement of the ROM: it
    holds the derivation to the schedule engine/effects/raster.emp documents, so a
    refactor that moved the opcode or dropped a priming record fails here rather than in
    a byte diff nobody can read.
    """
    f = _facts()
    want = _want(f)
    assert len(want) == 15, f"the derived image is {len(want)} words, not 15"
    assert want[0] == 0, "a program of register writes only dirties no palette line"
    assert want[1] == 0x8A00 | (f["line"] - 3), "record 0's arm schedules the ON edge's fire line"
    assert want[3] == 0x8A00 | (f["end_line"] - f["line"] - 1), \
        "record 1's arm schedules the gap from the ON fire line to the OFF one"
    assert want[2] == 0 and want[4] == 0, "both priming records carry zero ops"
    assert want[5] == f["park"] and want[9] == f["park"], \
        "nothing follows the OFF edge, so both event records park"
    assert want[6] == 1 and want[10] == 1, "each edge record carries exactly one op"
    assert want[7] == f["op_set_reg"] and want[11] == f["op_set_reg"], \
        "both edges are OP_SET_REG"
    assert want[-2] == f["park"] and want[-1] == f["ops_end"]


def test_the_fixtures_lines_are_schedulable_screen_lines():
    """Both authored lines must produce legal reg $0A reloads for their gaps."""
    _want(_facts())


def test_the_two_edges_carry_DIFFERENT_register_words():
    """THE BAND'S WHOLE CLAIM, and the one F2 exists for.

    Words 8 and 12 are the two edges' arguments. If they were equal there would be no
    band: the second op would cost its dispatch, write the base the first one already
    wrote, and the swap would run to the bottom of the display exactly as the single-fire
    program did. Every other assertion in this file — the framing, the arm chain, the
    opcodes — holds just as well for that program, which is why this one is stated
    separately and by name.
    """
    f = _facts()
    want = _want(f)
    assert want[8] != want[12], (
        f"both edges carry reg $02 word ${want[8]:04X}. The ON edge must borrow Plane B's "
        f"nametable (${f['plane_b']:04X}) and the OFF edge must return Plane A's own "
        f"(${f['plane_a']:04X}).")
    assert want[8] == 0x8200 | (f["plane_b"] >> f["shift"])
    assert want[12] == 0x8200 | (f["plane_a"] >> f["shift"])


def test_an_OFF_edge_at_or_above_the_ON_edge_is_UNMEASURABLE_not_a_pass():
    """A non-ascending pair is a source fault, never a byte mismatch.

    `fire_lines` refuses it at build time, so a ROM carrying it cannot exist — and a gate
    that answered such a pair with a word-by-word diff would blame the ROM for a fixture
    that never assembled. Both the equal and the inverted case are refused.
    """
    for end_line in (3, 2):
        try:
            G.expected_words(3, end_line, 0xE000, 0xC000, 10, 0, 0x8AFF, 0xFFFF)
        except G.Unmeasurable:
            continue
        raise AssertionError(
            f"expected_words accepted an OFF edge at screen line {end_line} against an ON "
            f"edge at 3 and produced an image")


def test_a_band_wider_than_one_reload_is_UNMEASURABLE_not_a_pass():
    """The ON->OFF gap is ONE reg $0A reload byte, so it cannot exceed 255 lines.

    Unreachable from `fire()`'s own 3..223 bound today — which is precisely why it is
    asserted on the DERIVATION rather than left implicit: this function is the pure half
    other lanes call with values the fixture never carries, and a gap byte that wrapped
    would encode a schedule nothing on screen matches.
    """
    try:
        G.expected_words(3, 3 + 257, 0xE000, 0xC000, 10, 0, 0x8AFF, 0xFFFF)
    except G.Unmeasurable:
        return
    raise AssertionError("expected_words accepted a 257-line band and produced an image")


def test_two_identical_plane_bases_are_UNMEASURABLE_not_a_pass():
    """The derivation refuses the degenerate case rather than emitting a no-op image."""
    try:
        G.expected_words(3, 64, 0xC000, 0xC000, 10, 0, 0x8AFF, 0xFFFF)
    except G.Unmeasurable:
        return
    raise AssertionError(
        "expected_words accepted two identical plane bases and produced an image; the "
        "gate would then pass on a program that re-points Plane A at its own base")


# ---------------------------------------------------------------------------
# The gap classifier — the two-sided shape assertion, in all three states.
# ---------------------------------------------------------------------------

def test_a_full_image_gap_is_emitted():
    assert G.classify_gap(30, 30) == "emitted"


def test_a_zero_gap_is_absent():
    assert G.classify_gap(0, 30) == "absent"


def test_an_unrecognised_gap_is_not_classified():
    """Neither the image nor zero must be reported as UNMEASURABLE, never chosen for.

    If this ever returns a string, the gate has started guessing which shape it is
    looking at from a length it does not recognise — and the release arm's whole value
    is that it can tell "correctly absent" from "silently truncated"."""
    assert G.classify_gap(10, 30) is None
    assert G.classify_gap(32, 30) is None
    # THE SINGLE-FIRE IMAGE IS THE LENGTH THAT MATTERS HERE. 22 bytes is exactly what this
    # program emitted before F2 gave it its OFF edge, so a tree half-reverted to the
    # one-op fixture lands on that length — and it must read as UNMEASURABLE, never as
    # "absent" (which the release arm treats as CORRECT) and never as "emitted".
    assert G.classify_gap(22, 30) is None
