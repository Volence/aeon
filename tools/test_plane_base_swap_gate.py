"""Unit cover for `tools/plane_base_swap_gate.py` — the pure halves, plus the source reads.

WHY THIS FILE IS PURE-FUNCTION AND SOURCE-READING ONLY, and never opens a ROM:
build.sh's pytest lane runs BEFORE the sigil build (build.sh:61-72 — a unit test opening
`s4.debug.bin` would grade a PREVIOUS build, which has bitten this tree twice). The gate's
ROM half therefore runs post-sigil, in build.sh, with `--built-after`. What is covered here
is the two pieces of judgement the gate adds — the word derivation and the gap
classification — plus the four facts it reads out of engine source, which are exactly the
facts a source-level regression would break before any ROM existed.

PROVEN RED, all four arms, by editing and restoring (2026-09-03):
  * `PlaneA => 10` -> `=> 13` in engine/vdp.emp
        -> test_the_two_planes_fold_to_different_reg02_bytes  (both fold to $8238)
  * `VRAM_PLANE_B = $E000` -> `$C000` in engine/system/constants.emp
        -> test_the_two_planes_fold_to_different_reg02_bytes
  * `OJZ_BASE_SWAP_LINE = 160` -> `2`
        -> test_the_fixtures_line_is_a_schedulable_screen_line
  * `classify_gap` returning `"absent"` for any unrecognised gap
        -> test_an_unrecognised_gap_is_not_classified
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
    )


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


def test_op_set_reg_is_the_opcode_the_gate_expects():
    """OP_SET_REG's VALUE is load-bearing in the handler, and it is the gate's word 7."""
    f = _facts()
    want = G.expected_words(f["line"], f["plane_b"], f["plane_a"], f["shift"],
                            f["op_set_reg"], f["park"], f["ops_end"])
    assert want[7] == f["op_set_reg"]
    assert want[8] == 0x8200 | (f["plane_b"] >> f["shift"])


def test_the_program_is_the_documented_sparse_framing():
    """One header word, two priming records, one event record, one terminator."""
    f = _facts()
    want = G.expected_words(f["line"], f["plane_b"], f["plane_a"], f["shift"],
                            f["op_set_reg"], f["park"], f["ops_end"])
    assert len(want) == 11, f"the derived image is {len(want)} words, not 11"
    assert want[0] == 0, "a program whose only op is a register write dirties no palette line"
    assert want[1] == 0x8A00 | (f["line"] - 3), "record 0's arm schedules the event's fire line"
    assert want[2] == 0 and want[4] == 0, "both priming records carry zero ops"
    assert want[3] == f["park"] and want[5] == f["park"]
    assert want[6] == 1, "the event record carries exactly one op"
    assert want[-2] == f["park"] and want[-1] == f["ops_end"]


def test_the_fixtures_line_is_a_schedulable_screen_line():
    """The authored line must produce a legal reg $0A reload for the priming gap."""
    f = _facts()
    G.expected_words(f["line"], f["plane_b"], f["plane_a"], f["shift"],
                     f["op_set_reg"], f["park"], f["ops_end"])


def test_two_identical_plane_bases_are_UNMEASURABLE_not_a_pass():
    """The derivation refuses the degenerate case rather than emitting a no-op image."""
    try:
        G.expected_words(160, 0xC000, 0xC000, 10, 0, 0x8AFF, 0xFFFF)
    except G.Unmeasurable:
        return
    raise AssertionError(
        "expected_words accepted two identical plane bases and produced an image; the "
        "gate would then pass on a program that re-points Plane A at its own base")


# ---------------------------------------------------------------------------
# The gap classifier — the two-sided shape assertion, in all three states.
# ---------------------------------------------------------------------------

def test_a_full_image_gap_is_emitted():
    assert G.classify_gap(22, 22) == "emitted"


def test_a_zero_gap_is_absent():
    assert G.classify_gap(0, 22) == "absent"


def test_an_unrecognised_gap_is_not_classified():
    """Neither the image nor zero must be reported as UNMEASURABLE, never chosen for.

    If this ever returns a string, the gate has started guessing which shape it is
    looking at from a length it does not recognise — and the release arm's whole value
    is that it can tell "correctly absent" from "silently truncated"."""
    assert G.classify_gap(10, 22) is None
    assert G.classify_gap(24, 22) is None
