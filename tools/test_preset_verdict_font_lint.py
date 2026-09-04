"""Hold the effects lab's verdict-glyph SHEET to its verdict CONSTANTS.

WHAT THIS GATE EXISTS FOR
=========================
`Debug_PresetReadout_Show` (games/sonic4/test/ojz_scroll_test.emp) paints the preset
tier's verdict by taking a `PRESET_VERDICT_*` value in a data register, shifting it left
by 5 (x 32 bytes, one 8x8 4bpp tile) and using the result as a RAW OFFSET into the
`.verdict_font` sheet that follows in the same DEBUG block:

    lsl.w   #5, d0                          // verdict x 32
    lea     .verdict_font(pc), a0
    lea     (a0,d0.w), a1                   // -> the DMA source

Nothing bounds that offset. A `PRESET_VERDICT_*` constant with no row in the sheet
therefore DMAs the 32 bytes that FOLLOW the sheet into the glyph cell — whatever `dc.l`
run or instruction stream sits there — and paints it as a verdict, on the one readout in
this tree whose entire job is to be trusted about what an effect is doing. It would build
green: the sheet's length is not a comptime value anything in `.emp` can read back (a
Label carries no length, which is the vacuous-guard generator this tree has already been
bitten by — see engine/effects/preset.emp's `ensure` banner), and the sheet lives inside
an `if DEBUG == 1 {}` block, so no `ensure` can size it.

So the coupling is checked as TEXT, the same species of pin as
tools/test_scene_cycle_table_lint.py's (the DEBUG scene table vs. the scene registry) and
with the same acknowledged limit: this reads source, not the ROM. The ROM-side half is
tools/preset_lab_witness.py, which reads the sheet back out of a running machine and
compares the painted tile against it byte for byte.

EVERY EXPECTATION IS DERIVED. There is no `4` in this file, and no glyph is named. Both
sides are counted out of the source: the constants from their `const PRESET_VERDICT_* =`
lines, the rows from the `dc.l` longs between `.verdict_font:` and the end of its block.
A fifth verdict state needs no edit here; a fifth verdict state with no glyph fails.

WHAT IT CHECKS
  1. one glyph row per verdict constant, and no spare rows;
  2. the constants are a dense 0..N-1 run, because the value is used as the row INDEX
     (a gap would index a row belonging to a different state, which is worse than
     indexing past the end: it paints a plausible wrong answer);
  3. every row is exactly 8 longs — an 8x8 4bpp tile is 8 rows of 8 nibbles, and a short
     row would slide every glyph after it by a scanline;
  4. no two glyphs have the same bytes. Two verdicts that paint the same tile are
     indistinguishable on screen, which deletes the readout's value SILENTLY — the exact
     failure mode the whole lab exists to remove, one level down.

LOUD RATHER THAN GREEN WHEN IT CANNOT MEASURE. Every parse raises with the file and the
pattern it could not find. A gate that quietly finds zero rows and passes is the vacuity
this tree keeps rediscovering.

PROVEN RED (2026-09-04), each mutation applied on disk against a COMMITTED baseline and
then restored, with `__pycache__` cleared between runs:
  * delete the arrow's two `dc.l` lines        -> test_one_glyph_row_per_verdict_constant
  * add `const PRESET_VERDICT_SPARE = 4`       -> test_one_glyph_row_per_verdict_constant
  * renumber PARALLAX from 3 to 4              -> test_verdict_constants_are_a_dense_run
  * drop one long from the arrow's first line  -> test_every_glyph_row_is_eight_longs
  * make the arrow a byte-copy of the diamond  -> test_no_two_glyphs_are_identical
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
READOUT = REPO / "games/sonic4/test/ojz_scroll_test.emp"

LONGS_PER_TILE = 8      # an 8x8 4bpp tile: 8 rows of 8 nibbles = 8 longs = 32 bytes

# `const PRESET_VERDICT_LIVE     = 2       // diamond — ...`
_VERDICT_CONST = re.compile(
    r"^\s*const\s+PRESET_VERDICT_(\w+)\s*=\s*(\d+)\s*(?://.*)?$", re.M
)
# the sheet body: `.verdict_font:` up to the close of the enclosing DEBUG block
_FONT_BODY = re.compile(r"^\s*\.verdict_font:\s*$(.*?)^\s*\}", re.M | re.S)
# one emission line: `dc.l  $00000000, $0000C000, ...` (comment tail allowed)
_FONT_LINE = re.compile(r"^\s*dc\.l\s+([^/\n]+?)\s*(?://.*)?$", re.M)


def _read() -> str:
    if not READOUT.is_file():
        raise AssertionError(
            f"{READOUT} does not exist. This lint holds the effects lab's verdict glyph "
            "sheet to its verdict constants; with the file gone it cannot measure "
            "anything and must not pass. If the readout was deliberately removed, delete "
            "this lint in the same commit."
        )
    return READOUT.read_text()


def verdict_constants() -> dict[str, int]:
    src = _read()
    rows = _VERDICT_CONST.findall(src)
    if not rows:
        raise AssertionError(
            f"{READOUT}: found no `const PRESET_VERDICT_* = <n>` lines. Either the verdict "
            "constants were renamed (update the _VERDICT_CONST pattern here) or the "
            "readout stopped having states. Passing on zero constants would make every "
            "check below vacuous."
        )
    out: dict[str, int] = {}
    for name, value in rows:
        assert name not in out, (
            f"{READOUT}: PRESET_VERDICT_{name} is declared twice. One name, one value, "
            "one glyph row."
        )
        out[name] = int(value)
    return out


def glyph_rows() -> list[list[str]]:
    """The sheet, split into one list of long literals per 8x8 tile."""
    src = _read()
    body = _FONT_BODY.search(src)
    if body is None:
        raise AssertionError(
            f"{READOUT}: could not find the `.verdict_font:` glyph sheet inside "
            "Debug_PresetReadout_Show. If the readout was removed, delete this lint in "
            "the same commit; if the sheet was renamed, update this pattern. It must not "
            "silently pass."
        )
    longs: list[str] = []
    for line in _FONT_LINE.findall(body.group(1)):
        longs.extend(tok.strip() for tok in line.split(",") if tok.strip())
    if not longs:
        raise AssertionError(
            f"{READOUT}: `.verdict_font:` was found but holds no `dc.l` longs. An empty "
            "sheet would have every verdict DMA whatever follows the label into the glyph "
            "cell."
        )
    return [longs[i:i + LONGS_PER_TILE] for i in range(0, len(longs), LONGS_PER_TILE)]


def test_one_glyph_row_per_verdict_constant():
    """Exactly one 8x8 tile per PRESET_VERDICT_* state — no missing row, no spare."""
    consts = verdict_constants()
    rows = glyph_rows()
    assert len(rows) == len(consts), (
        f"{READOUT.name}: `.verdict_font` holds {len(rows)} glyph row(s) but there are "
        f"{len(consts)} PRESET_VERDICT_* constants "
        f"({', '.join(f'{k}={v}' for k, v in sorted(consts.items(), key=lambda kv: kv[1]))}). "
        "The verdict value is used as a RAW `lsl.w #5` offset into this sheet, so a state "
        "with no row DMAs the 32 bytes that follow the sheet into the glyph cell and "
        "paints them as a verdict. Add the missing 8-long row, or delete the spare "
        "constant."
    )


def test_verdict_constants_are_a_dense_run():
    """The values must be 0..N-1 — they ARE the row indices."""
    consts = verdict_constants()
    values = sorted(consts.values())
    expected = list(range(len(consts)))
    assert values == expected, (
        f"{READOUT.name}: the PRESET_VERDICT_* values are {values}, not a dense "
        f"{expected}. Each value indexes `.verdict_font` directly, so a gap paints the row "
        "belonging to some other state — a plausible WRONG answer, which is worse than "
        "indexing off the end. Renumber so the constants and the sheet's row order are "
        "the same sequence."
    )


def test_every_glyph_row_is_eight_longs():
    """Each tile is 8 rows of 8 nibbles; a short one slides every glyph after it."""
    rows = glyph_rows()
    short = [(i, len(r)) for i, r in enumerate(rows) if len(r) != LONGS_PER_TILE]
    assert not short, (
        f"{READOUT.name}: these `.verdict_font` glyph rows are not {LONGS_PER_TILE} longs "
        f"(index, longs): {short}. An 8x8 4bpp tile is exactly {LONGS_PER_TILE} longs = 32 "
        "bytes, and the readout's DMA length is a literal 32 — a short row does not "
        "shorten the DMA, it shifts every glyph after it by a scanline and leaves the last "
        "one reading past the sheet."
    )


def test_no_two_glyphs_are_identical():
    """Two states that paint the same tile are indistinguishable on screen."""
    rows = glyph_rows()
    consts = {v: k for k, v in verdict_constants().items()}
    seen: dict[tuple[str, ...], int] = {}
    dupes = []
    for i, row in enumerate(rows):
        key = tuple(row)
        if key in seen:
            dupes.append((seen[key], i))
        else:
            seen[key] = i
    assert not dupes, (
        f"{READOUT.name}: these `.verdict_font` rows have identical bytes: "
        + "; ".join(
            f"row {a} ({consts.get(a, '?')}) == row {b} ({consts.get(b, '?')})"
            for a, b in dupes
        )
        + ". Two verdicts that paint the same tile cannot be told apart by the person "
        "holding the pad, so the readout would give a confident answer that carries no "
        "information — and it would do it silently. tools/preset_lab_witness.py REFUSES "
        "on the same condition for the same reason."
    )
