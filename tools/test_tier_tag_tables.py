"""Hold the effects lab's TIER NAME TAGS to the tables and the VRAM they index.

WHAT THIS GATE EXISTS FOR
=========================
`Debug_TierTags_Update` (games/sonic4/test/ojz_scroll_test.emp) spells the live raster
program's and BG-animation table's names into two multi-cell sprite tags. Three separate
raw offsets carry it, and NOT ONE of them is bounded by anything at runtime:

  * a row index (from scanning `.raster_table` / `.view_table`) times the tag's CELL
    COUNT, used as a raw offset into `.rtag_names` / `.btag_names`;
  * a letter index out of those name tables, `lsl.w #5` (x 32 bytes, one 8x8 4bpp tile),
    used as a raw offset into `.alphabet`;
  * a cell count that must equal the tag's VRAM region width in games/sonic4/vram.toml,
    because a multi-cell VDP sprite piece reads CONSECUTIVE tiles from its base.

Each of those, wrong, produces a plausible picture rather than a crash: a name row short
and the tag DMAs whatever follows the table; a letter index past 'Z' and it DMAs whatever
follows the alphabet; a cell count wider than the region and the tag draws the first tiles
of `plane_a` as letters. All three build green — a Label carries no length in `.emp`, and
all of this lives inside an `if DEBUG == 1 {}` block where no `ensure` can size it (the
same reason tools/test_preset_verdict_font_lint.py exists one readout over).

So the coupling is checked as TEXT, like that lint and like
tools/test_raster_cycle_table_lint.py. The acknowledged limit is the same: this reads
SOURCE, not the ROM.

EVERY EXPECTATION IS DERIVED. There is no `4`, no `3`, no `26` and no letter in this file.
The row counts come from `RTAG_ROWS`/`BTAG_ROWS` as those constants are SPELLED
(`RASTER_CYCLE_COUNT + 3`), the cell counts from `RTAG_CELLS`/`BTAG_CELLS`, the alphabet
size from `ALPHABET_GLYPHS`, the tile widths from vram.toml's own `tiles` fields, and the
VDP size nibble is recomputed from the cell count with the packing rule
engine/objects/mapping_dsl.emp pins with its own non-square `ensure`.

WHAT IT CHECKS
  1. one name row per table row, and no spare — for BOTH tiers, counting the cycle
     tables' own `dc.l` rows as the authority for the non-synthetic half;
  2. the synthetic rows (RTAG_NONE/PTCH/PSET, BTAG_OTHER) are a dense run starting at the
     cycle count, because those values index the name table directly;
  3. every name row is exactly its tier's cell count of letters;
  4. every letter is a defined `LTR_*` inside the alphabet;
  5. the `LTR_*` constants are a dense 0..N-1 run in alphabetical order — they index a
     sheet that is authored A to Z, so one out of place renames every word using it;
  6. the alphabet holds exactly `ALPHABET_GLYPHS` rows of 8 longs, all distinct;
  7. no two names within a tier are the same word (two rows that paint the same letters
     cannot be told apart, which deletes the tag's value silently);
  8. each tag's cell count equals its VRAM region's declared `tiles`, and the VDP piece
     size byte in `.tag_frame_*` packs exactly that width at one cell tall;
  9. the `dc.b` run from the first name table to `.alphabet` is an EVEN number of bytes,
     so `.alphabet`'s `dc.l` tiles keep the parity their DMA source needs (added
     2026-09-04, when a seventh `.btag_names` row made that run odd for the first time
     and the two prose "bytes — even" comments went stale without failing anything).

LOUD RATHER THAN GREEN WHEN IT CANNOT MEASURE. Every parse raises with the file and the
pattern it could not find; a gate that quietly finds zero rows and passes is the vacuity
this tree keeps rediscovering.

PROVEN RED (2026-09-04), each mutation applied on disk and quoted back from disk before
the run, then reversed, with `__pycache__` cleared between runs — see the parcel's report
for the transcript.
"""

import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
READOUT = REPO / "games/sonic4/test/ojz_scroll_test.emp"
VRAM_TOML = REPO / "games/sonic4/vram.toml"

LONGS_PER_TILE = 8      # an 8x8 4bpp tile: 8 rows of 8 nibbles = 8 longs = 32 bytes

# The two tiers, named once. Everything else in this file is derived from these rows.
#   name          the tier, for messages
#   cells_const   the constant holding its tag width in cells
#   rows_const    the constant holding its name-table row count
#   cycle_const   the constant holding its CYCLE row count (the non-synthetic half)
#   cycle_label   the `.emp` local label of the cycle's pointer table
#   names_label   the `.emp` local label of the name table
#   frame_label   the `.emp` local label of the sprite frame record
#   synth_prefix  the prefix of the synthetic row constants
#   region        the vram.toml region the tag's cells live in
TIERS = [
    dict(name="raster", cells_const="RTAG_CELLS", rows_const="RTAG_ROWS",
         cycle_const="RASTER_CYCLE_COUNT", cycle_label="raster_table",
         names_label="rtag_names", frame_label="tag_frame_4",
         synth_prefix="RTAG_", region="debug_raster_tag"),
    dict(name="bganim", cells_const="BTAG_CELLS", rows_const="BTAG_ROWS",
         cycle_const="BGANIM_VIEW_CYCLE_COUNT", cycle_label="view_table",
         names_label="btag_names", frame_label="tag_frame_3",
         synth_prefix="BTAG_", region="debug_bganim_tag"),
]

_PLAIN_CONST = re.compile(r"^\s*const\s+(\w+)\s*=\s*(\d+)\s*(?://.*)?$", re.M)
# `const RTAG_ROWS  = RASTER_CYCLE_COUNT + 3` / `const RTAG_NONE = RASTER_CYCLE_COUNT`
_SUM_CONST = re.compile(
    r"^\s*const\s+(\w+)\s*=\s*(\w+)\s*(?:\+\s*(\d+)\s*)?(?://.*)?$", re.M
)


def _read() -> str:
    if not READOUT.is_file():
        raise AssertionError(
            f"{READOUT} does not exist. This lint holds the effects lab's tier name tags "
            "to the tables and the VRAM they index; with the file gone it cannot measure "
            "anything and must not pass. If the tags were deliberately removed, delete "
            "this lint in the same commit."
        )
    return READOUT.read_text()


def _consts() -> dict[str, int]:
    """Every `const NAME = <int>` and `const NAME = <other const> [+ <int>]` in the file."""
    src = _read()
    out: dict[str, int] = {n: int(v) for n, v in _PLAIN_CONST.findall(src)}
    # one resolution pass is enough: the sum forms here name plain constants
    for name, base, addend in _SUM_CONST.findall(src):
        if name in out or base not in out:
            continue
        out[name] = out[base] + (int(addend) if addend else 0)
    return out


def const(name: str) -> int:
    values = _consts()
    if name not in values:
        raise AssertionError(
            f"{READOUT.name}: could not resolve `const {name}`. This lint derives every "
            "expectation from the source's own constants rather than restating numbers, "
            "so a renamed or restructured constant must FAIL here rather than let the "
            "check quietly measure nothing. Update this lint in the same commit as the "
            "rename."
        )
    return values[name]


def _block(label: str) -> str:
    """The source between a local label and the next label or block close."""
    src = _read()
    m = re.search(rf"^\s*(?:export\s+)?\.{re.escape(label)}:\s*$", src, re.M)
    if m is None:
        raise AssertionError(
            f"{READOUT.name}: could not find the `.{label}:` label. If it was renamed, "
            "update this lint; it must not silently pass, because every raw offset this "
            "file exists to bound is computed against that table."
        )
    rest = src[m.end():]
    stop = re.search(r"^\s*(?:export\s+)?[.\w]+:\s*$|^\s*\}\s*$", rest, re.M)
    return rest[:stop.start()] if stop else rest


def _dc_items(label: str, width: str) -> list[str]:
    """Every `dc.<width>` operand under a label, in order."""
    body = _block(label)
    items: list[str] = []
    for line in re.findall(rf"^\s*dc\.{width}\s+([^/\n]+?)\s*(?://.*)?$", body, re.M):
        items.extend(tok.strip() for tok in line.split(",") if tok.strip())
    if not items:
        raise AssertionError(
            f"{READOUT.name}: `.{label}:` was found but holds no `dc.{width}` operands. "
            "Passing on an empty table would make every check that reads it vacuous."
        )
    return items


def letter_constants() -> dict[str, int]:
    values = _consts()
    letters = {n: v for n, v in values.items() if re.fullmatch(r"LTR_[A-Z]", n)}
    if not letters:
        raise AssertionError(
            f"{READOUT.name}: found no `const LTR_<X> = <n>` lines. The name tables are "
            "written in those constants; with none resolved this lint would check the "
            "names against nothing."
        )
    return letters


def name_rows(tier: dict) -> list[list[str]]:
    """A tier's name table, split into one list of LTR_* names per row."""
    letters = _dc_items(tier["names_label"], "b")
    cells = const(tier["cells_const"])
    return [letters[i:i + cells] for i in range(0, len(letters), cells)]


def alphabet_rows() -> list[list[str]]:
    longs = _dc_items("alphabet", "l")
    return [longs[i:i + LONGS_PER_TILE]
            for i in range(0, len(longs), LONGS_PER_TILE)]


def vram_regions() -> dict[str, dict]:
    if not VRAM_TOML.is_file():
        raise AssertionError(
            f"{VRAM_TOML} does not exist — this lint cannot check a tag's cell count "
            "against the VRAM run it draws from, and must not pass without doing so."
        )
    with VRAM_TOML.open("rb") as fh:
        doc = tomllib.load(fh)
    return {r["name"]: r for r in doc.get("region", [])}


def test_one_name_row_per_table_row():
    """Exactly one name per cycle row plus one per synthetic row — no gap, no spare."""
    for tier in TIERS:
        expected = const(tier["rows_const"])
        cycle_rows = len(_dc_items(tier["cycle_label"], "l"))
        synth = expected - cycle_rows
        rows = name_rows(tier)
        assert len(rows) == expected, (
            f"{READOUT.name}: `.{tier['names_label']}` holds {len(rows)} name row(s) but "
            f"{tier['rows_const']} is {expected} "
            f"({cycle_rows} `.{tier['cycle_label']}` row(s) + {synth} synthetic). The row "
            "index reaches this table as a raw multiply-by-cell-count offset, so a row "
            "short makes the tag DMA whatever follows the table and spell it as a name. "
            f"Add the missing row, or correct {tier['rows_const']}."
        )
        assert cycle_rows == const(tier["cycle_const"]), (
            f"{READOUT.name}: `.{tier['cycle_label']}` holds {cycle_rows} pointer(s) but "
            f"{tier['cycle_const']} is {const(tier['cycle_const'])}. The scan in "
            "Debug_TierTags_Update walks the table for exactly that many entries, so a "
            "disagreement either skips a real row (which then reads as the synthetic "
            "fallback) or reads a pointer from past the table's end."
        )


def test_synthetic_rows_are_a_dense_run_after_the_cycle():
    """The synthetic constants ARE row indices — a gap names some other row."""
    for tier in TIERS:
        values = _consts()
        cycle = const(tier["cycle_const"])
        total = const(tier["rows_const"])
        synth = {n: v for n, v in values.items()
                 if n.startswith(tier["synth_prefix"])
                 and n not in (tier["rows_const"], tier["cells_const"])
                 and cycle <= v}
        assert sorted(synth.values()) == list(range(cycle, total)), (
            f"{READOUT.name}: the synthetic {tier['name']} rows are "
            f"{sorted((v, n) for n, v in synth.items())}, not a dense "
            f"{list(range(cycle, total))}. Each value indexes "
            f"`.{tier['names_label']}` directly, so a gap spells the name belonging to "
            "another state — a plausible WRONG answer, which is worse than reading past "
            "the end."
        )


def test_every_name_row_is_one_cell_per_tile():
    """A short name row slides every name after it, and the last reads past the table."""
    for tier in TIERS:
        cells = const(tier["cells_const"])
        letters = _dc_items(tier["names_label"], "b")
        assert len(letters) % cells == 0, (
            f"{READOUT.name}: `.{tier['names_label']}` holds {len(letters)} letter "
            f"byte(s), which is not a whole number of {cells}-cell names "
            f"({tier['cells_const']}). Every row is indexed as row x {cells}, so a row of "
            "the wrong length shifts every name after it."
        )


def test_every_letter_is_a_defined_glyph():
    """A letter index past the alphabet DMAs whatever follows the sheet into a cell."""
    letters = letter_constants()
    glyphs = len(alphabet_rows())
    for tier in TIERS:
        for row_i, row in enumerate(name_rows(tier)):
            for cell_i, tok in enumerate(row):
                assert tok in letters, (
                    f"{READOUT.name}: `.{tier['names_label']}` row {row_i} cell {cell_i} "
                    f"is `{tok}`, which is not one of the `LTR_*` constants. The name "
                    "tables are written in those on purpose — so the source SPELLS the "
                    "word — and a raw number here is both unreadable and unchecked."
                )
                assert letters[tok] < glyphs, (
                    f"{READOUT.name}: `.{tier['names_label']}` row {row_i} cell {cell_i} "
                    f"is {tok} = {letters[tok]}, but `.alphabet` holds only {glyphs} "
                    "glyph(s). The letter reaches the sheet as a raw `lsl.w #5` offset, "
                    "so this cell would DMA the 32 bytes that follow the sheet and paint "
                    "them as a letter."
                )


def test_letter_constants_are_a_dense_alphabetical_run():
    """The sheet is authored A to Z; the constants must be the same sequence."""
    letters = letter_constants()
    expected = {f"LTR_{chr(ord('A') + i)}": i for i in range(len(letters))}
    assert letters == expected, (
        f"{READOUT.name}: the `LTR_*` constants are "
        f"{sorted((v, n) for n, v in letters.items())}, which is not a dense run in "
        "alphabetical order. Each value indexes `.alphabet`, whose rows are authored A "
        "to Z, so one constant out of place silently re-spells every name that uses it."
    )


def test_alphabet_is_complete_and_well_formed():
    """One 8-long tile per declared glyph, no short rows, no duplicates."""
    rows = alphabet_rows()
    declared = const("ALPHABET_GLYPHS")
    longs = len(_dc_items("alphabet", "l"))
    assert longs == declared * LONGS_PER_TILE, (
        f"{READOUT.name}: `.alphabet` holds {longs} long(s), which is not "
        f"{declared} (ALPHABET_GLYPHS) x {LONGS_PER_TILE}. An 8x8 4bpp tile is exactly "
        f"{LONGS_PER_TILE} longs = 32 bytes and the tag's DMA length is a literal 32, so "
        "a short row does not shorten the DMA — it shifts every glyph after it by a "
        "scanline and leaves the last one reading past the sheet."
    )
    seen: dict[tuple[str, ...], int] = {}
    dupes = []
    for i, row in enumerate(rows):
        key = tuple(row)
        if key in seen:
            dupes.append((seen[key], i))
        else:
            seen[key] = i
    assert not dupes, (
        f"{READOUT.name}: these `.alphabet` glyph rows have identical bytes: "
        + "; ".join(f"{chr(ord('A') + a)} == {chr(ord('A') + b)}" for a, b in dupes)
        + ". Two letters that paint the same tile make every name containing either of "
        "them ambiguous on screen — a confident answer carrying less information than it "
        "appears to, which is the failure the whole lab exists to remove."
    )


def test_name_tables_leave_the_alphabet_word_aligned():
    """`.alphabet` must sit at the same parity as the first name table.

    WHY THIS IS A GATE AND NOT A COMMENT. `.alphabet` is `dc.l` tile art that
    `.paint_cells` hands to the DMA queue at a `lsl.w #5` offset from its own label. A
    VDP DMA source is a WORD address, so an odd `.alphabet` base does not fail loudly —
    it paints shifted garbage on the readout whose entire job is to be trusted. Nothing
    in `.emp` aligns a `dc.b` run for you, and `align` is a module-scope directive that
    sigil rejects inside a proc body, so the parity is carried by hand-placed pad bytes.

    Until 2026-09-04 it was carried by two PROSE comments ("36 bytes — even", "18 bytes
    — even") that a new name row silently invalidated: `.btag_names` went to seven rows
    of three, 21 bytes, and the comments still said 18.

    WHAT IT MEASURES, AND WHAT IT DOES NOT. It counts every `dc.b` byte from the first
    name table's label up to `.alphabet` and requires the total to be EVEN, i.e. that
    `.alphabet` has the same parity as `.rtag_names`. It cannot see `.rtag_names`' own
    absolute address (that is a link-time fact this text lint has no access to), so it
    proves RELATIVE parity only — but relative parity is exactly what a name row added
    to a table can break, which is the failure this exists for.
    """
    src = _read()
    first = TIERS[0]["names_label"]
    start = re.search(rf"^\s*(?:export\s+)?\.{re.escape(first)}:\s*$", src, re.M)
    end = re.search(r"^\s*(?:export\s+)?\.alphabet:\s*$", src, re.M)
    if start is None or end is None:
        raise AssertionError(
            f"{READOUT.name}: could not find `.{first}:` and `.alphabet:` — this lint "
            "cannot measure the run between them and must not pass without doing so."
        )
    assert start.end() < end.start(), (
        f"{READOUT.name}: `.alphabet:` no longer follows `.{first}:`. This lint measures "
        "the byte run between them; reordering them makes it measure nothing."
    )
    span = src[start.end():end.start()]
    counted = 0
    for line in re.findall(r"^\s*dc\.b\s+([^/\n]+?)\s*(?://.*)?$", span, re.M):
        counted += len([tok for tok in line.split(",") if tok.strip()])
    assert counted, (
        f"{READOUT.name}: found no `dc.b` bytes between `.{first}:` and `.alphabet:`. "
        "A zero count would make this parity check vacuous."
    )
    # The names' own contribution, derived from the same constants every other check
    # here reads. Anything above this is padding, which is what the parity needs.
    names_bytes = sum(const(t["rows_const"]) * const(t["cells_const"]) for t in TIERS)
    padding = counted - names_bytes
    assert padding >= 0, (
        f"{READOUT.name}: the run from `.{first}:` to `.alphabet:` holds {counted} "
        f"`dc.b` bytes but the name tables alone need {names_bytes} "
        "(sum of rows x cells). One of the tables is short, or this lint is reading "
        "the wrong span."
    )
    assert counted % 2 == 0, (
        f"{READOUT.name}: the `dc.b` run from `.{first}:` to `.alphabet:` is {counted} "
        f"bytes — ODD — so `.alphabet` starts on the opposite parity from `.{first}` and "
        "its `dc.l` tiles are a misaligned DMA source. The name tables account for "
        f"{names_bytes} of that ({', '.join(t['name'] + ': ' + str(const(t['rows_const'])) + 'x' + str(const(t['cells_const'])) for t in TIERS)}) "
        f"and {padding} byte(s) of padding follow them. Add or remove one pad byte "
        "(`.btag_pad` in that file is the existing one); `align` is module-scope in "
        "`.emp` and sigil rejects it inside a proc body."
    )


def test_no_two_names_in_a_tier_are_the_same_word():
    """Two rows spelling the same word cannot be told apart by the person holding the pad."""
    for tier in TIERS:
        seen: dict[tuple[str, ...], int] = {}
        dupes = []
        for i, row in enumerate(name_rows(tier)):
            key = tuple(row)
            if key in seen:
                dupes.append((seen[key], i))
            else:
                seen[key] = i
        assert not dupes, (
            f"{READOUT.name}: these `.{tier['names_label']}` rows spell the same word: "
            + "; ".join(f"row {a} == row {b}" for a, b in dupes)
            + ". The tag would give the same answer for two different states, silently."
        )


def test_tag_width_matches_its_vram_region_and_its_sprite_piece():
    """The cell count, the VRAM run and the VDP size nibble must be one number."""
    regions = vram_regions()
    for tier in TIERS:
        cells = const(tier["cells_const"])
        region = regions.get(tier["region"])
        assert region is not None, (
            f"{VRAM_TOML.name}: no region named `{tier['region']}`. The {tier['name']} "
            "tag draws its cells from that run; without it declared, the tag's tiles "
            "belong to nobody and the next region to need space will take them."
        )
        assert region["tiles"] == cells, (
            f"{VRAM_TOML.name}: region `{tier['region']}` declares {region['tiles']} "
            f"tile(s) but {tier['cells_const']} is {cells}. A multi-cell VDP sprite piece "
            "reads CONSECUTIVE tiles from its base, so a tag wider than its run draws the "
            f"first tiles of whatever follows tile {region['base'] + region['tiles']} as "
            "letters."
        )
        # mapping_dsl.emp's packing, pinned there by its own non-square `ensure`:
        # (w-1) in bits 3:2, (h-1) in bits 1:0. These tags are one cell tall.
        expected = (cells - 1) << 2
        frame = _block(tier["frame_label"])
        size_bytes = re.findall(r"^\s*dc\.b\s+\$([0-9A-Fa-f]{2})\s*,", frame, re.M)
        assert len(size_bytes) == 1, (
            f"{READOUT.name}: expected exactly one `dc.b $XX, <link>` size line in "
            f"`.{tier['frame_label']}`, found {len(size_bytes)}. This lint cannot check "
            "the piece width it cannot find, and must not pass without checking it."
        )
        assert int(size_bytes[0], 16) == expected, (
            f"{READOUT.name}: `.{tier['frame_label']}` packs size byte "
            f"${size_bytes[0].upper()}, but {cells} cells wide x 1 tall is "
            f"${expected:02X} under the VDP packing engine/objects/mapping_dsl.emp pins "
            "((w-1) in bits 3:2, (h-1) in bits 1:0). A size byte that disagrees with the "
            "name width draws the wrong number of tiles — too few and the last letters "
            "vanish, too many and it reads into the next VRAM region."
        )
