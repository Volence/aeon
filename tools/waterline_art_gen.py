#!/usr/bin/env python3
"""waterline_art_gen — THE waterline source-strip model (EFFECTS-W1 item 9d).

The row remap has two halves and they are the same permutation applied to two different
things. `tools/row_remap_ladder_gen.py` is the model for the half that permutes plane-B
SCROLL words; this is the model for the half that permutes PIXEL ROWS — S3K's `loc_278C6`
(sonic3k.asm:53981), a ROM source image gathered row by row through the SAME ladder row into
a fixed VRAM run.

WHAT THIS FILE IS FOR, and it is the same job the ladder generator does: the bytes ship from
`engine/level/parallax_dsl.emp`'s `waterline_strip_art16()`, which must return a CONCRETE
array type and so cannot take H as an argument. This module is the parameterised spelling —
one place the model is written down, callable at every band height the runtime can express,
and the thing `tools/test_waterline_art_gen.py` and `tools/waterline_art_gate.py` both check
against. Two spellings of one model are two models unless something holds them together.

GEOMETRY, DERIVED FROM H AND NOTHING ELSE
=========================================
A strip is 16 px wide (2 tile columns; the band repeats horizontally on the plane and the
16 px period is what makes the repeat invisible) and H px tall (H/8 tiles per column). There
are two strips, above the water surface and below it — S3K's `ArtUnc_AniHCZ1_WaterlineAbove`
and `_Below`.

    VRAM tiles          = 2 strips * 2 columns * H/8            = H/2
    per-frame DMA bytes = 2 strips * 2 columns * H rows * 4 B   = 16*H
    ROM source bytes    = 2 strips * 2 columns * 2H rows * 4 B  = 32*H

⚠ THE SOURCE IS 2H ROWS, AND THAT IS DERIVED — IT IS NOT S3K'S 192. S3K's source image is
192 rows because S3K's ladder entries are unbounded above (parcel 9b measured 5,871 of 9,312
HCZ entries violating `entry[i] <= 2i`). Aeon's ladder guarantees that bound, so the furthest
row any gather can reach is `2*(H-1)` and `2H` rows covers it with one to spare. The same
expression evaluated at S3K's own H = 96 gives 32*96 = 3,072 bytes, which is the figure the
item-9 design priced the art half at — the check that says this is the same derivation and
not a coincidence that happens to fit.

⚠ AND 48 TILES IS S3K's H, NOT A HEIGHT THIS ENGINE CAN NAME. `tiles = H/2` reaches 48 only
at H = 96, and `band_remap.brm_hshift` is consumed as `1 << shift`, so 96 has no spelling.
The booking's "48 tiles (two 16x96 strips)" is S3K's instance of the shape; at the shipped
H = 16 the derived need is 8 tiles, and the largest expressible height inside the declared
48-tile region is H = 64 at 32 tiles. `tiles_for_height()` below is the arithmetic.

THE PIXELS ARE A PLACEHOLDER, AND WHAT IS LOAD-BEARING IS NOT THEM
=================================================================
The OJZ background carries no water surface to promote (item-9 design section 6.2), so this
generates a ripple rather than importing art. Replacing these pixels with authored water is a
content edit that touches nothing else. What the mechanism actually depends on, and what
every consumer of this module checks, is two properties:

  * **no two source rows within RIPPLE_PERIOD of each other are identical.** A row-uniform
    image makes the gather byte-for-byte invisible, which is the failure mode this whole
    effect fails by — not a subtle one, an absent one. It is the pixel-side twin of the
    ladder's all-identity refusal.
  * **every nibble is in 1..14.** Index 0 is the plane's backdrop colour and would punch a
    hole through the band; 15 is left out on the same principle, one index of margin at the
    top of the line.

⚠ THE PROPERTY IS LOCAL AND THAT IS DELIBERATE — the first spelling of it was GLOBAL ("all
2H rows pairwise distinct") and the parameterised test refuted it at H = 32, 64 and 128. The
ripple has 16 phases; a half of the image has H rows; so global distinctness is only
reachable while H <= 16, and asserting it would have shipped a model that silently could not
be raised to the H = 64 the VRAM region was sized for. The LOCAL form is what the mechanism
actually needs and it holds at every expressible height (measured: 0 duplicates inside a
16-row window at H = 8, 16, 32, 64, 128): the ladder advances the source row by 1 or 2 per
output line, so what makes the compression visible — and what makes a wrong index detectable
— is that NEARBY rows differ. `globally_distinct()` reports the stronger fact where it
happens to hold; nothing requires it.

HOW LOCAL DISTINCTNESS IS OBTAINED. The ripple is a triangle wave in x whose phase advances
3 px per source row, and `gcd(3, 16) = 1`, so any 16 consecutive rows take all 16 phases and
none of them repeat. The deep half's 6 -> 4 amplitude drop is what additionally separates the
two halves row for row, which is what buys global distinctness at H = 16. Remove either and
`check()` fails.

AND THE PROPERTY THAT ACTUALLY MATTERS ON SCREEN, which is neither of those: how many of the
H+1 perspective states produce a DIFFERENT picture. `distinct_gathers()` answers it by
running the real transform over the real ladder, and the answer is **H of H+1 at every
expressible height** — the single collision is ladder rows H and H-1, which this model makes
byte-identical (at |p| = 1 every `extra` term floors to zero), and is the ladder's property
rather than the art's.
"""
from __future__ import annotations

import argparse
import math
import sys

#: 4bpp: two pixels per byte, 8 px per tile column, so 4 bytes per column row.
BYTES_PER_COLUMN_ROW = 4
#: A strip is 16 px wide = 2 tile columns, so a whole source row is 8 bytes.
COLUMNS_PER_STRIP = 2
ROW_BYTES = COLUMNS_PER_STRIP * BYTES_PER_COLUMN_ROW
#: Above the water surface, and below it.
STRIPS = 2
#: The ripple's horizontal period, in pixels — and the strip's own width.
RIPPLE_PERIOD = 16
#: Pixels the ripple's phase advances per source row. Coprime with RIPPLE_PERIOD is the
#: whole point (see the module docstring); `_validate_model` re-derives that rather than
#: trusting this comment.
PHASE_STEP = 3
#: The shallow half's ripple amplitude, and the deep half's. Their INEQUALITY is what makes
#: the two halves' rows distinct; `check()` fails if they are made equal.
AMP_SHALLOW, AMP_DEEP = 6, 4
#: The palette nibble each strip's ripple starts from. Two disjoint bands of one line, so the
#: strips are told apart on screen by colour and not only by position. Neither is 0.
BASE_ABOVE, BASE_BELOW = 1, 8
#: The triangle wave's own range, before it is scaled into a strip's band.
TRI_MAX = 7


def _validate_model() -> None:
    """The two model properties distinctness rests on, re-derived rather than asserted.

    Called from `image()`, so no caller can get bytes out of a model that cannot be
    distinct. This is cheap and it is not decoration: both constants above are the kind
    somebody tunes for looks, and either one tuned wrong turns 2H distinct rows into H."""
    if math.gcd(PHASE_STEP, RIPPLE_PERIOD) != 1:
        raise ValueError(
            f"PHASE_STEP {PHASE_STEP} is not coprime with RIPPLE_PERIOD {RIPPLE_PERIOD}, so "
            f"the ripple's phase cycles through only {RIPPLE_PERIOD // math.gcd(PHASE_STEP, RIPPLE_PERIOD)} "
            f"of its {RIPPLE_PERIOD} positions and rows repeat inside each half of the image")
    if AMP_SHALLOW == AMP_DEEP:
        raise ValueError(
            "AMP_SHALLOW == AMP_DEEP, so the deep half of the source image is a row-for-row "
            "copy of the shallow half. The phase walk alone only distinguishes rows WITHIN a "
            "half; the amplitude drop is what distinguishes the halves")
    for base in (BASE_ABOVE, BASE_BELOW):
        top = base + max(AMP_SHALLOW, AMP_DEEP)
        if base < 1 or top > 14:
            raise ValueError(
                f"a strip's index band {base}..{top} leaves 1..14: index 0 is the plane's "
                f"backdrop and would punch a hole through the band")


def tiles_for_height(H: int) -> int:
    """VRAM tiles the two strips occupy at band height H. See the module docstring."""
    return STRIPS * COLUMNS_PER_STRIP * (H // 8)


def dst_bytes(H: int) -> int:
    """Bytes of one frame's DMA — the gathered image, H rows per column."""
    return STRIPS * COLUMNS_PER_STRIP * H * BYTES_PER_COLUMN_ROW


def src_bytes(H: int) -> int:
    """Bytes of the ROM source image — 2H rows per column, the ladder's own read bound."""
    return STRIPS * COLUMNS_PER_STRIP * 2 * H * BYTES_PER_COLUMN_ROW


def _validate_height(H: int) -> None:
    if not isinstance(H, int) or isinstance(H, bool):
        raise TypeError(f"band height must be an int, got {H!r}")
    if H & (H - 1) or H < 8:
        raise ValueError(
            f"band height {H} is not a power of two >= 8. `band_remap.brm_hshift` is "
            f"consumed as `H = 1 << brm_hshift`, and below 8 a strip is not a whole tile "
            f"column — a source image at such an H is bytes no band record can name and no "
            f"DMA can transfer as tiles.")


def triangle(t: int) -> int:
    """A 0..TRI_MAX triangle over a 0..RIPPLE_PERIOD-1 input.

    Spelled as the engine spells it (`t + (t/8)*(15 - 2t)`) would be spelling the engine's
    workaround rather than the model: the `.emp` avoids a branch because an `if` in
    block-tail position folds to `()` silently. Python has no such trap, so this says what
    the wave IS and the agreement test is what holds the two spellings together."""
    half = RIPPLE_PERIOD // 2
    return t if t < half else (RIPPLE_PERIOD - 1 - t)


def pixel(H: int, strip: int, row: int, x: int) -> int:
    """One 4bpp palette index. `row` is a SOURCE row, 0 .. 2H-1; `x` is 0 .. 15."""
    phase = (x + PHASE_STEP * row) % RIPPLE_PERIOD
    amp = AMP_SHALLOW if row < H else AMP_DEEP
    base = BASE_ABOVE if strip == 0 else BASE_BELOW
    return base + (triangle(phase) * amp) // TRI_MAX


def image(H: int) -> bytes:
    """The whole ROM source image, flat and row-major: 2 strips x 2H rows x 8 bytes."""
    _validate_height(H)
    _validate_model()
    out = bytearray()
    for strip in range(STRIPS):
        for row in range(2 * H):
            for b in range(ROW_BYTES):
                out.append(pixel(H, strip, row, 2 * b) * 16 + pixel(H, strip, row, 2 * b + 1))
    assert len(out) == src_bytes(H)
    return bytes(out)


def source_rows(H: int, blob: bytes, strip: int) -> list[bytes]:
    """The 2H rows of one strip, as they sit in the image. Shared with the gate so both
    read the layout the same way."""
    base = strip * 2 * H * ROW_BYTES
    return [blob[base + r * ROW_BYTES: base + (r + 1) * ROW_BYTES] for r in range(2 * H)]


def gather(H: int, blob: bytes, ladder_row: bytes) -> bytes:
    """The runtime's own transform, in Python: what Waterline_Art_Update DMAs.

    `ladder_row` is the H entries of the selected row. The destination is COLUMN-major —
    each tile column's H rows contiguous — because that is what a vertical run of 8x8 tiles
    is in VRAM, while the source is row-major. The gather is exactly that transpose, and
    having it here is what lets tools/waterline_art_witness.py predict a VRAM read word for
    word instead of asserting that something changed."""
    if len(ladder_row) != H:
        raise ValueError(f"a ladder row is {H} entries, got {len(ladder_row)}")
    out = bytearray()
    for strip in range(STRIPS):
        rows = source_rows(H, blob, strip)
        for col in range(COLUMNS_PER_STRIP):
            for i in range(H):
                k = ladder_row[i]
                if k >= 2 * H:
                    raise ValueError(
                        f"ladder entry {k} at line {i} reads source row {k} of {2 * H} — "
                        f"the gather would walk off the end of the image. The ladder's "
                        f"`entry[i] <= 2i` bound is what forbids this")
                r = rows[k]
                out.append(r[col * BYTES_PER_COLUMN_ROW + 0])
                out.append(r[col * BYTES_PER_COLUMN_ROW + 1])
                out.append(r[col * BYTES_PER_COLUMN_ROW + 2])
                out.append(r[col * BYTES_PER_COLUMN_ROW + 3])
    assert len(out) == dst_bytes(H)
    return bytes(out)


# ------------------------------------------------------------------ self-check (the model)


def local_duplicates(H: int, blob: bytes) -> list[str]:
    """Source rows within RIPPLE_PERIOD of each other that are byte-identical.

    THE WINDOW IS THE LADDER'S OWN REACH, not a tuning knob: `entry[i]` advances by 1 or 2
    per output line, so what a gather can confuse is rows NEAR each other. Shared with
    tools/waterline_art_gate.py so the model and the ROM are judged by one rule."""
    bad = []
    for strip in range(STRIPS):
        rows = source_rows(H, blob, strip)
        for i in range(len(rows)):
            for j in range(i + 1, min(i + RIPPLE_PERIOD, len(rows))):
                if rows[i] == rows[j]:
                    bad.append(
                        f"strip {strip}: source rows {i} and {j} are byte-identical and "
                        f"{j - i} apart — inside the ladder's own reach, so a gather that "
                        f"selects one instead of the other is INVISIBLE")
    return bad


def globally_distinct(H: int) -> tuple[int, int]:
    """(distinct rows, total rows) over both strips. REPORTED, never required — see the
    module docstring: global distinctness is unreachable above H = 16 with 16 phases."""
    blob = image(H)
    total = STRIPS * 2 * H
    distinct = sum(len({bytes(r) for r in source_rows(H, blob, s)}) for s in range(STRIPS))
    return distinct, total


def distinct_gathers(H: int, ladder: bytes) -> tuple[int, int]:
    """(distinct gathered images, ladder rows) — the on-screen visibility question.

    How many of the H+1 perspective states produce a DIFFERENT picture, measured by running
    the real transform over the real ladder rather than by arguing about the source image.
    `ladder` is the whole (H+1)xH table; the caller supplies it so this module does not
    depend on the ladder generator."""
    blob = image(H)
    seen = {gather(H, blob, ladder[r * H:(r + 1) * H]) for r in range(H + 1)}
    return len(seen), H + 1


def check(H: int) -> list[str]:
    """Re-derive every property a consumer depends on, on the produced bytes.

    Duplicates tools/test_waterline_art_gen.py on purpose, for that file's reason: the
    pytest lane is what a build runs, and this is what somebody typing `--height 64` at a
    prompt gets told before they paste anything into an engine source."""
    blob = image(H)
    if len(blob) != src_bytes(H):
        return [f"H={H}: produced {len(blob)} bytes, not 32*H = {src_bytes(H)}"]
    bad = [f"H={H} " + b for b in local_duplicates(H, blob)]
    for off, byte in enumerate(blob):
        if (byte >> 4) == 0 or (byte & 15) == 0:
            bad.append(f"H={H}: byte {off} carries palette index 0, the plane backdrop")
            break
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--height", type=int, default=16, help="band height H (power of two)")
    ap.add_argument("--out", help="write the raw image here")
    ap.add_argument("--check", action="store_true", help="self-check and report")
    a = ap.parse_args()
    blob = image(a.height)
    H = a.height
    print(f"waterline source image: H = {H}, {len(blob)} B "
          f"({STRIPS} strips x {2 * H} rows x {ROW_BYTES} B)")
    print(f"  per-frame DMA {dst_bytes(H)} B into {tiles_for_height(H)} VRAM tiles")
    if a.out:
        open(a.out, "wb").write(blob)
        print(f"  wrote {a.out}")
    if a.check:
        d, t = globally_distinct(H)
        print(f"  globally distinct source rows {d} of {t} "
              f"(REPORTED, not required — see the module docstring)")
        bad = check(H)
        for b in bad:
            print("  FAIL " + b)
        print(f"  {'OK' if not bad else 'FAILED'} — {len(bad)} problem(s)")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
