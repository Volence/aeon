"""Unit cover for `tools/plane_role_swap_gate.py` — the pure halves, plus the source
reads, plus one exercise of the decode-and-pair-walk against a STATIC byte string.

WHY THIS FILE NEVER OPENS s4.debug.bin/s4.bin: build.sh's pytest lane runs BEFORE the
sigil build (band_drift_golden's sibling test files record this twice already — a unit
test opening the ROM here would grade a PREVIOUS build). What is covered is the four
facts the gate reads out of engine source, the pure pair-derivation over them, and the
decode/pair-walk logic exercised against a byte string captured from a real build
(2026-09-03, this parcel's own `Parallax_Set_Roles_Swapped` at aeon `s4.debug.lst`
$007BD6) rather than invented — so the parsing logic is proven against real capstone
output shapes, not against bytes this file's author guessed capstone would produce.
The gate's own ROM-reading arms (label lookup, `--built-after`) are proven red in the
parcel's DEFERRED_WORK entry, not here: they need a build, and a build is what this
lane runs before.

PROVEN RED, each mutation shown applied on disk (`git diff`) before the run and restored
from the COMMITTED baseline afterwards, `__pycache__` cleared between runs (the stale-
bytecode trap — a same-length, same-second edit can be served from a cached .pyc):

  * `engine/vdp.emp`'s `vdp_base_shift` `PlaneB => 13` -> `PlaneB => 10` — MEASURED
    2026-09-03: 1 failed, 9 passed. `test_the_two_planes_fold_to_different_reg04_bytes`
    stays GREEN (Plane A $C000 and Plane B $E000 still fold to two DIFFERENT bytes at
    shift 10 — $30 vs $38 — so that test's own claim, "the two normal/swapped bytes
    differ", still holds; it is not the test this mutation breaks, which is worth
    recording since the shift COLLIDING with PlaneA's own shift is the intuitive but
    wrong prediction). `test_expected_pairs_matches_the_real_build` fails instead: reg
    $04's pair becomes `(4, 0x30)` where the pin wants `(4, 0x06)` — the real regression
    this mutation causes is the STRUCTURAL PIN against the actually-shipped bytes, not
    the degenerate-fold guard.
  * `engine/system/constants.emp`'s `VRAM_PLANE_B = $E000` -> `$C000` — MEASURED
    2026-09-03: 3 failed, 7 passed. Both plane-fold guards fail
    (`test_the_two_planes_fold_to_different_reg02_bytes` AND `..._reg04_bytes` — with
    the two planes now identical, EVERY register's normal/swapped byte collapses, not
    only one), and `test_expected_pairs_matches_the_real_build` fails on the same
    `Unmeasurable` `expected_pairs` itself raises for the degenerate case.
    `test_two_identical_planes_are_UNMEASURABLE_on_both_regs` stays GREEN — it calls
    `expected_pairs` with hardcoded literals, not through `_facts()`, so a source
    mutation cannot reach it; it is proving the FUNCTION refuses the degenerate case,
    not that source currently avoids one.
  * `_imm`'s `if not op.startswith("#$")` -> `if not op.startswith("#%")` — MEASURED
    2026-09-03: 2 failed, 8 passed. `test_imm_parses_a_hex_immediate` fails (a real
    `#$38` operand no longer parses); `test_found_pairs_reads_the_real_build_bytes`
    fails too (zero pairs found in the fixture bytes, none of which use `#%`) —
    `test_found_pairs_ignores_the_flag_store_and_branches` stays green regardless,
    since it asserts an EMPTY list either way.
  * `found_pairs`'s `_reg_num(ops[1]) == 1` (the d1 destination check) -> `== 2` —
    MEASURED 2026-09-03: 1 failed, 9 passed. `test_found_pairs_reads_the_real_build_bytes`
    fails: the fixture's `move.b` destinations are all `d1`, so nothing matches and zero
    pairs are found.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import plane_role_swap_gate as G  # noqa: E402
from plane_base_swap_gate import Unmeasurable, emp_const, vdp_base_shift  # noqa: E402


# ---------------------------------------------------------------------------
# The two facts (plus the two shifts), read out of engine source. Not copies: the same
# calls the gate makes.
# ---------------------------------------------------------------------------

def _facts():
    return dict(
        plane_a=emp_const(G.CONSTANTS, "VRAM_PLANE_A"),
        plane_b=emp_const(G.CONSTANTS, "VRAM_PLANE_B"),
        shift_a=vdp_base_shift("PlaneA"),
        shift_b=vdp_base_shift("PlaneB"),
    )


def test_the_two_planes_fold_to_different_reg02_bytes():
    f = _facts()
    a_normal = f["plane_a"] >> f["shift_a"]
    a_swapped = f["plane_b"] >> f["shift_a"]
    assert a_normal != a_swapped, (
        f"VRAM_PLANE_A ${f['plane_a']:04X} and VRAM_PLANE_B ${f['plane_b']:04X} both "
        f"fold to reg $02 byte ${a_normal:02X} at vdp_base_shift(PlaneA) = "
        f"{f['shift_a']}. There is no role swap left to demonstrate on this register.")


def test_the_two_planes_fold_to_different_reg04_bytes():
    f = _facts()
    b_normal = f["plane_b"] >> f["shift_b"]
    b_swapped = f["plane_a"] >> f["shift_b"]
    assert b_normal != b_swapped, (
        f"VRAM_PLANE_A ${f['plane_a']:04X} and VRAM_PLANE_B ${f['plane_b']:04X} both "
        f"fold to reg $04 byte ${b_normal:02X} at vdp_base_shift(PlaneB) = "
        f"{f['shift_b']}. There is no role swap left to demonstrate on this register.")


def test_expected_pairs_matches_the_real_build():
    """A STRUCTURAL PIN against the four bytes this parcel's own landing measured
    (aeon s4.debug.lst, 2026-09-03): $38/$06 swapped, $30/$07 normal. If a future
    VRAM re-layout moves either plane, this pin is what should be re-derived — the
    point is that today's four bytes are not an accident of this test file's author
    typing them, they are what `expected_pairs` computes from source right now.
    """
    f = _facts()
    want = G.expected_pairs(f["plane_a"], f["plane_b"], f["shift_a"], f["shift_b"])
    assert want == [(2, 0x38), (4, 0x06), (2, 0x30), (4, 0x07)]


def test_two_identical_planes_are_UNMEASURABLE_on_both_regs():
    try:
        G.expected_pairs(0xC000, 0xC000, 10, 13)
    except Unmeasurable:
        return
    raise AssertionError(
        "expected_pairs accepted two identical plane bases and produced pairs; the "
        "gate would then pass on a swap that re-points a register at the base it "
        "already has")


# ---------------------------------------------------------------------------
# The operand parsers — pure string -> int/None, exercised directly.
# ---------------------------------------------------------------------------

def test_imm_parses_a_hex_immediate():
    assert G._imm("#$38") == 0x38
    assert G._imm("#$0") == 0


def test_imm_rejects_a_register_operand():
    assert G._imm("d1") is None
    assert G._imm("a0") is None


def test_reg_num_parses_a_data_register():
    assert G._reg_num("d1") == 1
    assert G._reg_num("d0") == 0
    assert G._reg_num("d7") == 7


def test_reg_num_rejects_an_address_register():
    assert G._reg_num("a1") is None
    assert G._reg_num("#$38") is None


# ---------------------------------------------------------------------------
# found_pairs, exercised against a STATIC byte string captured from a real build —
# aeon s4.debug.lst $007BD6..$007C0E, 2026-09-03 (Parallax_Set_Roles_Swapped's whole
# body), not invented. Proves the decode-and-pair-walk logic against real capstone
# output rather than against a shape this file's author assumed capstone produces.
# ---------------------------------------------------------------------------

_ROUTINE_HEX = (
    "11c08b48"      # move.b  d0, $8b48.w           (the flag store — ignored)
    "4a00"          # tst.b   d0                    (ignored)
    "6718"          # beq.b   $18                   (ignored)
    "303c0002"      # move.w  #$2, d0
    "123c0038"      # move.b  #$38, d1
    "6100a0c2"      # bsr.w   Set_VDP_Reg            (ignored — the two args cross it)
    "303c0004"      # move.w  #$4, d0
    "123c0006"      # move.b  #$6, d1
    "6000a0b6"      # bra.w   Set_VDP_Reg            (ignored)
    "303c0002"      # move.w  #$2, d0
    "123c0030"      # move.b  #$30, d1
    "6100a0aa"      # bsr.w   Set_VDP_Reg            (ignored)
    "303c0004"      # move.w  #$4, d0
    "123c0007"      # move.b  #$7, d1
)


def test_found_pairs_reads_the_real_build_bytes():
    rom = bytes.fromhex(_ROUTINE_HEX)
    got = G.found_pairs(rom, 0, len(rom))
    assert got == [(2, 0x38), (4, 0x06), (2, 0x30), (4, 0x07)]


def test_found_pairs_ignores_the_flag_store_and_branches():
    """The routine's FIRST three instructions (move.b to the flag, tst.b, beq) and its
    THREE control-flow instructions (bsr/bsr/bra) must contribute nothing — only the
    move.w-to-d0 / move.b-to-d1 pairs count. Cut the routine down to just those three
    non-pair instructions and confirm zero pairs are found (not a crash, not a partial
    pair)."""
    rom = bytes.fromhex("11c08b48" "4a00" "6718")
    assert G.found_pairs(rom, 0, len(rom)) == []


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
