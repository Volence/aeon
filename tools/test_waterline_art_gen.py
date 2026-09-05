"""The waterline source-strip model, held against the engine's own spelling of it.

EFFECTS-W1 item 9d, and the twin of tools/test_row_remap_ladder_gen.py. There are two
expressions of one model in this tree — `waterline_strip_art16()` in
engine/level/parallax_dsl.emp (a `comptime fn` at one hard-coded height, because an `.emp`
comptime fn must return a concrete array type) and tools/waterline_art_gen.py (the
parameterised one). Two spellings of one model are two models unless something holds them
together, and this is that something.

WHAT IT DOES NOT DO: it does not read the ROM. Whether those bytes reached the linked image
at the address the 68000 indexes through is tools/waterline_art_gate.py's question, and it
is a different one — the generator being right and the right bytes shipping are two claims.
"""
import math
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import waterline_art_gen as gen                                          # noqa: E402

DSL = os.path.join(REPO, "engine/level/parallax_dsl.emp")


def _dsl_text() -> str:
    return open(DSL, encoding="utf-8").read()


def _dsl_const(name: str, _depth: int = 0) -> int:
    """A `pub const NAME = <expression>` out of the DSL, evaluated.

    THE FIRST VERSION OF THIS READ THE FIRST TOKEN ONLY, and it reported
    `WATERLINE_SRC_BYTES` (= `WATERLINE_STRIPS * 2 * WATERLINE_H * WATERLINE_ROW_BYTES`) as
    2 — the value of its first operand. It failed loudly here because the comparison was
    against 512, but a helper that returns a plausible small integer for an expression it
    cannot parse is one rename away from being the thing that passes silently.

    UNMEASURABLE rather than a default if it cannot be read: a test that silently invents
    the number it is checking is the vacuous shape this whole file exists against."""
    if _depth > 8:
        pytest.fail(f"UNMEASURABLE: `pub const {name}` recurses more than 8 deep in {DSL}")
    text = _dsl_text()
    m = re.search(r"^pub const " + name + r"\s*=\s*([^/\n]+)", text, re.M)
    if not m:
        pytest.fail(f"UNMEASURABLE: `pub const {name}` is not in {DSL}")
    expr = m.group(1).strip()
    if not re.fullmatch(r"[A-Za-z0-9_ ()*/+\-]+", expr):
        pytest.fail(f"UNMEASURABLE: `pub const {name} = {expr}` is not plain arithmetic")
    env = {ident: _dsl_const(ident, _depth + 1)
           for ident in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expr))}
    return int(eval(expr, {"__builtins__": {}}, env))     # noqa: S307 — arithmetic only


def shipped_H() -> int:
    return _dsl_const("WATERLINE_H")


def declared_src_len() -> int:
    """The DECLARED length of `waterline_strip_art16()`'s return array, off its signature.

    Since 2026-09-02 that annotation is a real length contract (docs/EMP_PITFALLS.md §13),
    so it is the one number in the engine that a wrong geometry cannot silently pass."""
    m = re.search(r"pub comptime fn waterline_strip_art16\(\)\s*->\s*\[u8;\s*(\d+)\]",
                  _dsl_text())
    if not m:
        pytest.fail("UNMEASURABLE: could not read the return type of "
                    "`waterline_strip_art16()` in " + DSL)
    return int(m.group(1))


# --------------------------------------------------------------------- the agreement


def test_the_engine_signature_matches_the_generator_at_the_shipped_height():
    """P1: `[u8; N]` on the engine's fn is 32*H for the H the engine declares.

    This is the pairing that a change to H breaks first, and it breaks LOUDLY — sigil
    refuses a comptime fn whose returned array is not its declared length. The value of
    checking it here is that it names WHICH number to move."""
    H = shipped_H()
    assert declared_src_len() == gen.src_bytes(H), (
        f"engine/level/parallax_dsl.emp declares WATERLINE_H = {H}, whose source image is "
        f"32*H = {gen.src_bytes(H)} bytes, but `waterline_strip_art16()` returns "
        f"[u8; {declared_src_len()}]. Both move together or the fn does not compile")


def test_the_geometry_constants_agree_with_the_generator():
    """P2: strips, row bytes, and the derived tile/DMA counts, both spellings."""
    H = shipped_H()
    assert _dsl_const("WATERLINE_STRIPS") == gen.STRIPS
    assert _dsl_const("WATERLINE_ROW_BYTES") == gen.ROW_BYTES
    assert _dsl_const("WATERLINE_SRC_BYTES") == gen.src_bytes(H)
    assert _dsl_const("WATERLINE_DST_BYTES") == gen.dst_bytes(H)


def test_the_engines_own_pins_are_this_models_bytes():
    """P3: the four `WlPin[...]` ensures in the DSL, re-derived from the generator.

    Those pins are the engine's only self-check on its pixels and they were written by
    hand — which is exactly the population this file exists to doubt. Each is parsed out of
    the source and evaluated against the generator's image at the same offset."""
    H = shipped_H()
    blob = gen.image(H)
    text = _dsl_text()
    pins = re.findall(r"ensure\(WlPin\[([^\]]+)\]\s*==\s*\$([0-9A-Fa-f]{2})", text)
    assert pins, ("UNMEASURABLE: no `ensure(WlPin[...] == $xx` pins found in " + DSL +
                  " — the engine's pixels have no self-check to agree with")
    env = {"WATERLINE_H": H, "WATERLINE_ROW_BYTES": gen.ROW_BYTES}
    for expr, want in pins:
        off = eval(expr, {"__builtins__": {}}, env)          # noqa: S307 — literals only
        assert blob[off] == int(want, 16), (
            f"engine/level/parallax_dsl.emp pins WlPin[{expr}] (= byte {off}) at ${want}, "
            f"the generator produces ${blob[off]:02X}. One of the two spellings of the "
            f"ripple has moved")


# --------------------------------------------------------------------- the model itself


@pytest.mark.parametrize("H", [8, 16, 32, 64, 128])
def test_every_expressible_height_produces_a_visible_image(H):
    """P4: at every height `brm_hshift` can name, no two source rows inside the ladder's
    own reach are identical and no nibble is 0.

    THE PARAMETERISATION IS WHAT MADE THIS TEST WORTH WRITING, and it refuted the first
    version of the model's own claim. That claim was GLOBAL distinctness — all 2H rows
    pairwise distinct — which holds at the shipped H = 16 and FAILS at 32, 64 and 128 (the
    ripple has 16 phases; a half of the image has H rows). Run only at the shipped height it
    would have been green, and the model would silently have been unraisable to the H = 64
    the 48-tile VRAM region was sized for. The property is now the local one the mechanism
    actually needs."""
    assert gen.check(H) == []


@pytest.mark.parametrize("H", [8, 16, 32, 64, 128])
def test_the_perspective_states_produce_different_pictures(H):
    """P4b: THE ON-SCREEN QUESTION, and neither distinctness property answers it.

    An image can satisfy every byte-level property and still gather to the same picture at
    every |p|. This runs the real transform over the real ladder and counts how many of the
    H+1 states differ. Measured: H of H+1 at every expressible height, the one collision
    being ladder rows H and H-1 — at |p| = 1 every `extra` term of the LADDER model floors
    to zero, so those two rows are byte-identical. That is the ladder's property, not the
    art's, which is why the expectation below is H and not H+1, and why it is derived here
    rather than pinned."""
    import row_remap_ladder_gen as ladder_gen
    seen, total = gen.distinct_gathers(H, ladder_gen.ladder(H))
    assert total == H + 1
    assert seen == H, (
        f"the {H + 1} ladder rows gather to {seen} distinct pictures, expected {H}. More "
        f"than {H} means the |p| = 0 / |p| = 1 identity collapse in the ladder model has "
        f"changed; fewer means perspective states the art cannot tell apart, which is this "
        f"effect being partly invisible")


def test_global_distinctness_is_reported_and_holds_only_at_the_shipped_height():
    """P4c: the stronger fact, measured where it holds and where it stops.

    Recorded as a test rather than as a comment because it is the boundary a future H raise
    walks into: at H = 16 the art distinguishes every source row; above it, it does not."""
    assert gen.globally_distinct(16) == (64, 64)
    d32, t32 = gen.globally_distinct(32)
    assert d32 < t32, ("global distinctness is expected to FAIL at H = 32 — if it now holds, "
                       "the model gained phases and the local-only claim above is too weak")


@pytest.mark.parametrize("H", [8, 16, 32, 64, 128])
def test_the_geometry_is_the_designs_own_arithmetic(H):
    """P5: tiles = H/2, DMA = 16H, source = 32H, at every expressible height."""
    assert gen.tiles_for_height(H) == H // 2
    assert gen.dst_bytes(H) == 16 * H
    assert gen.src_bytes(H) == 32 * H


def test_the_s3k_instance_reproduces_the_designs_published_figures():
    """P6: the item-9 design priced the art half at 3,072 B of ROM and 48 tiles, both at
    S3K's own H = 96. If this model is the same derivation it must hit both exactly.

    ⚠ 96 IS NOT AN EXPRESSIBLE HEIGHT — `brm_hshift` is consumed as `1 << shift`, so this
    is a check on the ARITHMETIC and not a configuration anything can ship. That is why the
    booking's 48 tiles and the shipped need of 8 differ, and it is measured here rather
    than argued."""
    assert gen.src_bytes(96) == 3072
    assert gen.tiles_for_height(96) == 48
    assert 96 & 95, "96 is a power of two?"                  # the premise, stated
    assert gen.tiles_for_height(64) == 32 and gen.tiles_for_height(128) == 64, (
        "the two expressible heights either side of 96 must bracket 48 — 32 and 64 — which "
        "is what makes 48 unreachable rather than merely unchosen")
    with pytest.raises(ValueError):
        gen.image(96)


def test_distinctness_needs_BOTH_halves_of_the_trick(monkeypatch):
    """P7: the negative control for the property everything else rests on.

    Distinctness comes from a coprime phase walk (rows within a half) AND an amplitude
    drop (the two halves against each other). A test that only asserted the property would
    keep passing if one of them became load-free — so each is removed in turn and the
    property must break."""
    H = 16
    assert gen.check(H) == []                                  # the control

    monkeypatch.setattr(gen, "AMP_DEEP", gen.AMP_SHALLOW)
    with pytest.raises(ValueError, match="row-for-row copy"):
        gen.image(H)
    monkeypatch.undo()

    monkeypatch.setattr(gen, "PHASE_STEP", 4)                  # gcd(4, 16) = 4
    with pytest.raises(ValueError, match="coprime"):
        gen.image(H)
    monkeypatch.undo()

    assert gen.check(H) == [], "the monkeypatches did not unwind"


def test_the_gather_is_the_transpose_and_the_ladder_bound_is_enforced():
    """P8: `gather()` reproduces the runtime's column-major destination, and refuses a
    ladder entry past the source image rather than reading off the end.

    The refusal is the point: `entry[i] <= 2i` is the ladder's own bound and it is what
    makes a 2H-row source sufficient. A gather that silently wrapped would make the bound
    look optional."""
    import row_remap_ladder_gen as ladder_gen
    H = shipped_H()
    blob = gen.image(H)
    tab = ladder_gen.ladder(H)
    row = tab[H * H: (H + 1) * H]                              # row H — the identity
    out = gen.gather(H, blob, row)
    assert len(out) == gen.dst_bytes(H)
    # Row H is the identity, so column 0 of strip 0 is source rows 0..H-1's first 4 bytes.
    for i in range(H):
        assert out[i * 4: i * 4 + 4] == blob[i * gen.ROW_BYTES: i * gen.ROW_BYTES + 4]
    # ...and column 1 is the SAME rows' second 4 bytes, which is what makes it a transpose.
    col1 = H * gen.BYTES_PER_COLUMN_ROW
    for i in range(H):
        assert out[col1 + i * 4: col1 + i * 4 + 4] == \
            blob[i * gen.ROW_BYTES + 4: i * gen.ROW_BYTES + 8]
    with pytest.raises(ValueError, match="walk off the end"):
        gen.gather(H, blob, bytes([2 * H] * H))


def test_every_ladder_row_stays_inside_the_source_image():
    """P9: the pairing that makes 2H rows the right size, checked over the WHOLE ladder.

    P8 exercises one row. The claim the source size rests on is about all H+1 of them, and
    a bound that holds for the identity row and not for row 0 is the one that matters."""
    import row_remap_ladder_gen as ladder_gen
    H = shipped_H()
    tab = ladder_gen.ladder(H)
    worst = max(tab)
    assert worst < 2 * H, (
        f"the ladder's largest entry at H = {H} is {worst}, and the source image has "
        f"{2 * H} rows — the gather would read past it. 2H is sized on the ladder's "
        f"`entry[i] <= 2i` bound; if that bound moved, this number must move with it")
    assert worst == 2 * (H - 1), (
        f"the ladder's largest entry is {worst}, not the saturating 2*(H-1) = {2 * (H - 1)} "
        f"— the source image is sized on that saturation being REACHED, so a smaller peak "
        f"means 2H rows is now more than the model can use and the check above is slack")


def test_the_ripple_amplitude_is_not_flat():
    """P10: a wave that folded to a constant satisfies distinctness nowhere and would be
    caught — but a wave with amplitude 1 satisfies it and is invisible on screen. The
    magnitude question, asked because item 9a shipped an effect that passed every boolean
    gate and the owner could not see it."""
    H = shipped_H()
    blob = gen.image(H)
    for strip in range(gen.STRIPS):
        rows = gen.source_rows(H, blob, strip)
        nibbles = [n for r in rows for b in r for n in (b >> 4, b & 15)]
        spread = max(nibbles) - min(nibbles)
        assert spread >= 4, (
            f"strip {strip}'s palette indices span only {spread} ({min(nibbles)}.."
            f"{max(nibbles)}). The gather would be running correctly over art nobody can "
            f"see change — 9a's own failure, one level down")
