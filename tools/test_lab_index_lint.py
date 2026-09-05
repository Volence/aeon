"""Hold the effects lab's ONE list to the three things it dispatches into.

WHAT THIS GATE EXISTS FOR
=========================
`Debug_LabCycleHotkey` (games/sonic4/test/ojz_scroll_test.emp) is the whole selection
surface of the effects lab since 2026-09-05, when the owner's three chords
("why are there 3 ways to do things now? start + left/right, start + up/down,
start + a") collapsed into one list walked by START+LEFT/RIGHT. Every entry is a
six-byte row of `.lab_index`:

    dc.b    <kind>, <sub-index>, <four LTR_* name letters>

and the cursor reaches that row as a RAW multiply-by-LAB_ENTRY_SIZE offset, then the
sub-index reaches its own table as a raw scaled offset after that. NOT ONE of those
offsets is bounded by anything sigil can see:

  * a `dc.b` run carries no length in `.emp`, and the whole table lives inside an
    `if DEBUG == 1 {}` block where no `ensure` can size it;
  * the KIND byte decides which engine slot the row installs into
    (`Parallax_StartTransition` / `Raster_Install` / `Effects_InstallPreset`), so a
    row whose kind disagrees with its sub-index hands one table's index to another
    table;
  * a PRESET row's sub-index is a flat SECTION id resolved as
    `Act.sec_grid_ptr + sub * sizeof(Sec)`, so a row naming a section the act does not
    have resolves into whatever ROM follows the section grid;
  * the four name letters are `lsl.w #5` offsets into `Debug_TierTags_Update`'s
    26-tile `.alphabet`, so a letter index past 'Z' DMAs whatever follows the sheet
    into the tag.

Each of those, wrong, produces a plausible picture rather than a crash, and all of them
build GREEN. So the coupling is checked as TEXT, the way
tools/test_scene_cycle_table_lint.py, tools/test_raster_cycle_table_lint.py and
tools/test_tier_tag_tables.py are. The acknowledged limit is the same: this reads
SOURCE, not the ROM.

WHAT IT DOES **NOT** DUPLICATE, which is why it is short
========================================================
`.lab_index` is an INDEX over tables that already have gates. `.scene_table` is held to
the scene registry, row for row in emission order, by test_scene_cycle_table_lint.py;
`.raster_table` is held to the preset documents on disk, in both directions, by
test_raster_cycle_table_lint.py; the tier tags' name tables and the alphabet are held by
test_tier_tag_tables.py. This file checks only the JOIN: that every row of the one list
names a kind, a reachable sub-index of that kind's table, and a spellable name — plus
the one cross-table fact nothing else can see, that a raster row's SELECTION name and
that program's LIVE-STATE name are the same word.

EVERY EXPECTATION IS DERIVED. There is no 37, no 21, no 6, no 9 and no letter in this
file. Row widths come from LAB_ENTRY_SIZE and LAB_NAME_CELLS as those constants are
spelled; the scene bound from the `.scene_table` rows themselves and from
SCENE_CYCLE_COUNT in the registry; the raster bound from the `.raster_table` rows and
RASTER_CYCLE_COUNT; the section bound from the ACT's own `const GRID_W`/`GRID_H` and its
`pub data OJZ_Act1_Sections: [Sec; N]` arity; the alphabet size from ALPHABET_GLYPHS.

LOUD RATHER THAN GREEN WHEN IT CANNOT MEASURE. Every parse below raises with the file
and the pattern it could not find. A gate that quietly finds zero rows and passes is the
vacuity this tree keeps rediscovering.

PROVEN RED (2026-09-05), each mutation applied on disk, quoted back from disk before the
run and then REVERSED by hand, with __pycache__ cleared between runs — the transcript is
in this parcel's report. The arms and their mutations:
  * delete one `.lab_index` row            -> test_row_count_matches_the_cycle_count
  * flip a SCENE row's kind to RASTER       -> test_scene_rows_are_a_dense_run_over_the_scene_table
                                               (and the raster arm, which then sees a
                                               duplicate sub-index)
  * point a PRESET row at section 9         -> test_preset_rows_are_inside_the_acts_own_grid
  * misspell one name letter (LTR_Q -> Q)   -> test_every_name_is_four_defined_letters
  * copy one row's name onto another        -> test_no_two_entries_spell_the_same_word
  * change a raster row's name to a word
    the tier tag does not use               -> test_raster_names_match_the_live_state_tag
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LAB = REPO / "games/sonic4/test/ojz_scroll_test.emp"
REGISTRY = REPO / "games/sonic4/data/effects/scene_registry.emp"
ACT = REPO / "games/sonic4/data/levels/ojz/act1/act_descriptor.emp"

_PLAIN_CONST = re.compile(r"^\s*(?:pub\s+)?const\s+(\w+)\s*=\s*(\d+)\s*(?://.*)?$", re.M)
# `const LAB_RASTER_OFF = RASTER_CYCLE_COUNT` / `const RTAG_NONE = RASTER_CYCLE_COUNT + 1`
_SUM_CONST = re.compile(
    r"^\s*(?:pub\s+)?const\s+(\w+)\s*=\s*(\w+)\s*(?:\+\s*(\d+)\s*)?(?://.*)?$", re.M
)
# a labelled block: the label, up to the NEXT label or the close of its DEBUG block
_BLOCK_END = r"(?=^\s*(?:export\s+)?[.\w]+:\s*$|^\s*\}\s*$)"
_ROW = re.compile(r"^\s*dc\.b\s+([^/\n]+?)\s*(?://.*)?$", re.M)
_DC_L = re.compile(r"^\s*dc\.l\s+([^/\n]+?)\s*(?://.*)?$", re.M)
_ACT_SEC_ARITY = re.compile(r"^pub\s+data\s+\w+\s*:\s*\[\s*Sec\s*;\s*(\d+)\s*\]", re.M)


def _read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(
            f"{path} does not exist. This lint holds the effects lab's one list to the "
            "tables it dispatches into; with the file gone it cannot measure anything and "
            "must not pass. If the lab was deliberately removed, delete this lint in the "
            "same commit."
        )
    return path.read_text()


def _consts(path: Path) -> dict[str, int]:
    """Every `const NAME = <int>` and `const NAME = <other const> [+ <int>]` in a file."""
    src = _read(path)
    out: dict[str, int] = {n: int(v) for n, v in _PLAIN_CONST.findall(src)}
    # one resolution pass is enough: the sum forms here name plain constants
    for name, base, addend in _SUM_CONST.findall(src):
        if name in out or base not in out:
            continue
        out[name] = out[base] + (int(addend) if addend else 0)
    return out


def const(name: str, path: Path = LAB) -> int:
    values = _consts(path)
    if name not in values:
        raise AssertionError(
            f"{path.name}: could not resolve `const {name}`. This lint derives every "
            "expectation from the sources' own constants rather than restating numbers, "
            "so a renamed or restructured constant must FAIL here rather than let the "
            "check quietly measure nothing. Update this lint in the same commit as the "
            "rename."
        )
    return values[name]


def _block(label: str, path: Path = LAB) -> str:
    src = _read(path)
    m = re.search(rf"^\s*(?:export\s+)?\.{re.escape(label)}:\s*$", src, re.M)
    if m is None:
        raise AssertionError(
            f"{path.name}: could not find the `.{label}:` label. If it was renamed, "
            "update this lint; it must not silently pass, because every raw offset this "
            "file exists to bound is computed against that table."
        )
    rest = src[m.end():]
    stop = re.search(_BLOCK_END, rest, re.M)
    return rest[:stop.start()] if stop else rest


def lab_rows() -> list[list[str]]:
    """`.lab_index`, one list of operand tokens per row."""
    body = _block("lab_index")
    rows: list[list[str]] = []
    for line in _ROW.findall(body):
        rows.append([tok.strip() for tok in line.split(",") if tok.strip()])
    if not rows:
        raise AssertionError(
            f"{LAB.name}: `.lab_index:` was found but holds no `dc.b` rows. A zero-row "
            "list would make the cursor read a kind and a sub-index from whatever "
            "follows the label in ROM and dispatch on them."
        )
    return rows


def _dc_l_rows(label: str) -> list[str]:
    body = _block(label)
    items: list[str] = []
    for line in _DC_L.findall(body):
        items.extend(tok.strip() for tok in line.split(",") if tok.strip())
    if not items:
        raise AssertionError(
            f"{LAB.name}: `.{label}:` was found but holds no `dc.l` operands. Passing on "
            "an empty table would make every sub-index check that reads it vacuous."
        )
    return items


def letter_constants() -> dict[str, int]:
    values = _consts(LAB)
    letters = {n: v for n, v in values.items() if re.fullmatch(r"LTR_[A-Z]", n)}
    if not letters:
        raise AssertionError(
            f"{LAB.name}: found no `const LTR_<X> = <n>` lines. The list's names are "
            "written in those constants; with none resolved this lint would check the "
            "names against nothing."
        )
    return letters


def kind_constants() -> dict[str, int]:
    values = _consts(LAB)
    kinds = {n: v for n, v in values.items() if n.startswith("LAB_KIND_")}
    if not kinds:
        raise AssertionError(
            f"{LAB.name}: found no `const LAB_KIND_* = <n>` lines. The kind byte is what "
            "decides which engine slot a row installs into; with none resolved this lint "
            "could not tell a scene row from a preset row."
        )
    return kinds


def rows_of_kind(kind_name: str) -> list[list[str]]:
    return [r for r in lab_rows() if r and r[0] == kind_name]


def sub_indices(kind_name: str) -> list[int]:
    out = []
    for r in rows_of_kind(kind_name):
        assert len(r) >= 2, (
            f"{LAB.name}: a `{kind_name}` row of `.lab_index` has fewer than two "
            f"operands ({r!r}). Every row is <kind>, <sub-index>, then its name letters."
        )
        assert re.fullmatch(r"\d+", r[1]), (
            f"{LAB.name}: a `{kind_name}` row's sub-index is {r[1]!r}, not a plain "
            "decimal. It is used as a raw scaled table offset, so this lint has to be "
            "able to read it as a number."
        )
        out.append(int(r[1]))
    return out


def act_section_count() -> int:
    """grid_w x grid_h for OJZ act 1, cross-read against the Sec table's own arity."""
    values = _consts(ACT)
    for name in ("GRID_W", "GRID_H"):
        if name not in values:
            raise AssertionError(
                f"{ACT.name}: could not resolve `const {name}`. A preset row's sub-index "
                "is a flat section id into this act's grid; without the grid this lint "
                "cannot bound it and must not pass."
            )
    product = values["GRID_W"] * values["GRID_H"]
    m = _ACT_SEC_ARITY.search(_read(ACT))
    if m is None:
        raise AssertionError(
            f"{ACT.name}: could not find the `pub data <name>: [Sec; N]` section table. "
            "This lint cross-reads the grid product against that arity so a grid that "
            "drifted from its own table cannot silently widen the bound."
        )
    arity = int(m.group(1))
    assert product == arity, (
        f"{ACT.name}: grid_w x grid_h is {product} but the section table is declared "
        f"`[Sec; {arity}]`. The act's own `ensure` fails the build on this too; fix it "
        "there. Until then this lint cannot say how many sections the act has."
    )
    return product


# ---------------------------------------------------------------- the arms


def test_row_count_matches_the_cycle_count():
    """The wrap bound compiled into the cursor must be exactly the number of rows."""
    rows = lab_rows()
    n = const("LAB_CYCLE_COUNT")
    assert len(rows) == n, (
        f"{LAB.name}: `.lab_index` holds {len(rows)} row(s) but LAB_CYCLE_COUNT is {n}. "
        "The hotkey wraps its cursor at LAB_CYCLE_COUNT and then reads a row at a raw "
        f"multiply-by-LAB_ENTRY_SIZE offset, so a cursor of {len(rows)}..{n - 1} would "
        "read a kind and a sub-index from past the table's end and dispatch on them."
    )


def test_every_row_is_one_entry_wide_and_the_stride_is_even():
    """LAB_ENTRY_SIZE is the authored row width, and it has to be even."""
    size = const("LAB_ENTRY_SIZE")
    cells = const("LAB_NAME_CELLS")
    name_off = const("LAB_NAME_OFF")
    expected = name_off + cells
    assert size == expected, (
        f"{LAB.name}: LAB_ENTRY_SIZE is {size} but a row is LAB_NAME_OFF ({name_off}) "
        f"header bytes plus LAB_NAME_CELLS ({cells}) name bytes = {expected}. The cursor "
        "multiplies by LAB_ENTRY_SIZE to find a row and the tag painter adds "
        "LAB_NAME_OFF to find its letters; a stride that is not the row width slides "
        "every row after the first."
    )
    assert size % 2 == 0, (
        f"{LAB.name}: LAB_ENTRY_SIZE is {size} — ODD. `.scene_table` follows `.lab_index` "
        "and is `dc.l`; an odd stride times an odd row count leaves it on the wrong "
        "parity and every pointer it holds is fetched from an odd address. "
        "`align` is module-scope in `.emp` and sigil rejects it inside a proc body, so "
        "the parity is carried by the row width."
    )
    wrong = [(i, len(r)) for i, r in enumerate(lab_rows()) if len(r) != size]
    assert not wrong, (
        f"{LAB.name}: these `.lab_index` rows do not hold {size} operands "
        f"(index, operands): {wrong}. Every row is exactly one entry wide; a short row "
        "does not shorten the stride, it shifts every row after it."
    )


def test_the_scene_table_is_word_aligned_after_the_list():
    """The `dc.b` run before `.scene_table` must be an even number of bytes.

    RELATIVE parity only — `.lab_index`' own absolute address is a link-time fact this
    text lint cannot see — but relative parity is exactly what a row added to the list
    can break, which is the failure this exists for. `.lab_index` itself follows an
    `rts`, and every 68000 instruction is an even number of bytes.
    """
    src = _read(LAB)
    start = re.search(r"^\s*(?:export\s+)?\.lab_index:\s*$", src, re.M)
    end = re.search(r"^\s*(?:export\s+)?\.scene_table:\s*$", src, re.M)
    if start is None or end is None:
        raise AssertionError(
            f"{LAB.name}: could not find `.lab_index:` and `.scene_table:` — this lint "
            "cannot measure the byte run between them and must not pass without it."
        )
    assert start.end() < end.start(), (
        f"{LAB.name}: `.scene_table:` no longer follows `.lab_index:`. This lint measures "
        "the byte run between them; reordering them makes it measure nothing."
    )
    span = src[start.end():end.start()]
    counted = 0
    for line in _ROW.findall(span):
        counted += len([tok for tok in line.split(",") if tok.strip()])
    assert counted, (
        f"{LAB.name}: found no `dc.b` bytes between `.lab_index:` and `.scene_table:`. "
        "A zero count would make this parity check vacuous."
    )
    assert counted % 2 == 0, (
        f"{LAB.name}: the `dc.b` run from `.lab_index:` to `.scene_table:` is {counted} "
        "bytes — ODD — so `.scene_table` starts on the opposite parity and its `dc.l` "
        "pointers are fetched from odd addresses. Rows are LAB_ENTRY_SIZE bytes each; "
        "either the stride went odd or something else was emitted into that run."
    )


def test_every_row_names_a_defined_kind_and_the_kinds_are_dense():
    """A kind byte outside the set would fall through the dispatch's last compare."""
    kinds = kind_constants()
    values = sorted(kinds.values())
    assert values == list(range(len(values))), (
        f"{LAB.name}: the LAB_KIND_* constants are {kinds}, which is not a dense "
        "0..N-1 run. The dispatch asserts the kind is `ls` the LAST one and then "
        "branches; a gap lets a byte inside that range pass the assert and fall through "
        "to the first arm with a sub-index meant for another table."
    )
    unknown = sorted({r[0] for r in lab_rows() if r and r[0] not in kinds})
    assert not unknown, (
        f"{LAB.name}: these `.lab_index` rows name a kind that is not a LAB_KIND_* "
        f"constant: {unknown}. An unknown name in a `dc.b` operand does not error in "
        "`.emp` — it becomes a link extern resolving to some address's low byte — so "
        "this is the only place the misspelling can be caught."
    )


def test_scene_rows_are_a_dense_run_over_the_scene_table():
    """Scene sub-indices index `.scene_table`, and the whole registry must be reachable."""
    subs = sub_indices("LAB_KIND_SCENE")
    table = _dc_l_rows("scene_table")
    assert subs == list(range(len(table))), (
        f"{LAB.name}: the SCENE rows' sub-indices are {subs}, but `.scene_table` holds "
        f"{len(table)} rows, so they must be exactly 0..{len(table) - 1} in order. Out of "
        "order and a reviewer walking the list gets a different scene from the one the "
        "table's own numbering says; short and a shipped scene is unreachable from the "
        "lab; long and the cursor fetches a `parallax_config*` from past the table."
    )
    declared = const("SCENE_CYCLE_COUNT", REGISTRY)
    assert len(subs) == declared, (
        f"{LAB.name}: {len(subs)} SCENE row(s) in the one list, but SCENE_CYCLE_COUNT is "
        f"{declared} in {REGISTRY.name} (which sigil pins to `SCENES.len`). Every shipped "
        "scene has to have a row, or it ships in the ROM with nothing able to select it."
    )


def test_raster_rows_are_a_dense_run_with_one_off_row_last():
    """Raster sub-indices index `.raster_table`, plus ONE row past its end that means OFF."""
    subs = sub_indices("LAB_KIND_RASTER")
    table = _dc_l_rows("raster_table")
    off = const("LAB_RASTER_OFF")
    cycle = const("RASTER_CYCLE_COUNT")
    assert cycle == len(table), (
        f"{LAB.name}: RASTER_CYCLE_COUNT is {cycle} but `.raster_table` holds "
        f"{len(table)} rows. tools/test_raster_cycle_table_lint.py is the authority on "
        "that pairing; it is re-read here because LAB_RASTER_OFF is derived from it and "
        "this lint's own OFF check would otherwise inherit the drift."
    )
    assert off == len(table), (
        f"{LAB.name}: LAB_RASTER_OFF is {off} but `.raster_table` holds {len(table)} "
        "rows. OFF is the one sub-index that is NOT a table row — it means "
        "`Raster_Program_None` — so it has to be exactly one past the last row, or the "
        "hotkey's `beq` on it either misses (and reads past the table) or swallows a "
        "real row."
    )
    assert subs == list(range(len(table) + 1)), (
        f"{LAB.name}: the RASTER rows' sub-indices are {subs}, but `.raster_table` holds "
        f"{len(table)} rows plus the OFF row, so they must be exactly "
        f"0..{len(table)} in order with OFF last. A missing row makes a raster program "
        "unreachable from the lab; a duplicate makes two entries install the same thing "
        "under different names."
    )


def test_preset_rows_are_inside_the_acts_own_grid():
    """A preset sub-index is a flat SECTION id, resolved with no runtime table."""
    subs = sub_indices("LAB_KIND_PRESET")
    sections = act_section_count()
    assert subs == list(range(len(subs))), (
        f"{LAB.name}: the PRESET rows' sub-indices are {subs}, which is not a dense "
        "0..N-1 run in order. They are flat section ids; out of order the readout's "
        "section digit disagrees with the order a reviewer walks them in."
    )
    assert len(subs) <= sections, (
        f"{LAB.name}: the one list holds {len(subs)} PRESET row(s) but OJZ act 1 has "
        f"{sections} section(s) ({ACT.name}, grid_w x grid_h). A row naming a section the "
        "act does not have resolves `Act.sec_grid_ptr + sub * sizeof(Sec)` into whatever "
        "ROM follows the section grid and hands it to Effects_InstallPreset. The hotkey "
        "has a runtime bound too, and it would STAND DOWN — so the visible symptom is a "
        "row that does nothing, which is worse to debug than a build failure."
    )
    digit_max = const("PRESET_CYCLE_MAX")
    assert len(subs) <= digit_max, (
        f"{LAB.name}: {len(subs)} PRESET row(s), but the preset readout draws ONE decimal "
        f"digit and PRESET_CYCLE_MAX is {digit_max}. Section {digit_max} would show as "
        f"'{digit_max % 10}' and a reviewer would record his verdict against the wrong "
        "section. Give the readout a second cell (games/sonic4/vram.toml) first."
    )


def test_every_name_is_four_defined_letters():
    """The letters are raw `lsl.w #5` offsets into a 26-tile alphabet sheet."""
    letters = letter_constants()
    glyphs = const("ALPHABET_GLYPHS")
    cells = const("LAB_NAME_CELLS")
    off = const("LAB_NAME_OFF")
    bad = []
    for i, row in enumerate(lab_rows()):
        name = row[off:off + cells]
        if len(name) != cells:
            bad.append((i, f"{len(name)} letter(s), not {cells}"))
            continue
        for tok in name:
            if tok not in letters:
                bad.append((i, f"{tok} is not a defined LTR_* constant"))
            elif not 0 <= letters[tok] < glyphs:
                bad.append((i, f"{tok} = {letters[tok]} is outside the {glyphs}-glyph sheet"))
    assert not bad, (
        f"{LAB.name}: these `.lab_index` names are not {cells} defined letters "
        f"(row, problem): {bad}. Each letter reaches `.alphabet` as a raw `lsl.w #5` "
        "offset, so an undefined name becomes a link extern's low byte and an "
        "out-of-range index DMAs whatever follows the sheet into the tag — on the "
        "readout whose entire job is to be trusted."
    )


def test_no_two_entries_spell_the_same_word():
    """Two rows painting the same four letters cannot be told apart by the person holding
    the pad, which deletes the whole point of naming them."""
    off = const("LAB_NAME_OFF")
    cells = const("LAB_NAME_CELLS")
    seen: dict[tuple[str, ...], int] = {}
    dupes = []
    for i, row in enumerate(lab_rows()):
        key = tuple(row[off:off + cells])
        if key in seen:
            dupes.append((seen[key], i))
        else:
            seen[key] = i
    assert not dupes, (
        f"{LAB.name}: these `.lab_index` rows spell the same word: "
        + "; ".join(f"row {a} == row {b}" for a, b in dupes)
        + ". The whole reason this list is named rather than numbered is that the owner "
        "relays what he is looking at; two entries that read the same on screen cannot be "
        "relayed apart, and the readout would give the same answer for two different "
        "states, silently."
    )


def test_raster_names_match_the_live_state_tag():
    """One program, one word — whether you SELECTED it or the engine INSTALLED it.

    The lab shows two different subjects in two rows: the top tag names the entry the
    cursor is on (from `.lab_index`), the third names the raster program that is actually
    live (from `.rtag_names`, scanned back through `.raster_table` by
    Debug_TierTags_Update). They are deliberately different subjects — after a section
    crossing they disagree, and the disagreement is the answer. But for ONE program they
    must be the same WORD, or a reviewer stepping onto `SWAP` and reading `PSWP` below it
    has no way to tell whether he selected the wrong thing or the engine installed
    something else.

    This is the only fact here that no other lint can see: test_tier_tag_tables.py checks
    `.rtag_names` against `.raster_table`'s LENGTH, never against `.lab_index`'s words.
    """
    off = const("LAB_NAME_OFF")
    cells = const("LAB_NAME_CELLS")
    lab_names: dict[int, tuple[str, ...]] = {}
    for row in lab_rows():
        if row[0] != "LAB_KIND_RASTER":
            continue
        lab_names[int(row[1])] = tuple(row[off:off + cells])

    rtag_cells = const("RTAG_CELLS")
    body = _block("rtag_names")
    letters: list[str] = []
    for line in _ROW.findall(body):
        letters.extend(tok.strip() for tok in line.split(",") if tok.strip())
    if not letters:
        raise AssertionError(
            f"{LAB.name}: `.rtag_names:` was found but holds no `dc.b` operands. This "
            "arm compares the lab's raster names against it and must not pass on an "
            "empty table."
        )
    rtag_rows = [tuple(letters[i:i + rtag_cells])
                 for i in range(0, len(letters), rtag_cells)]

    assert rtag_cells == cells, (
        f"{LAB.name}: RTAG_CELLS is {rtag_cells} and LAB_NAME_CELLS is {cells}. Both tags "
        "are one 4x1 VDP sprite piece — four is the hardware maximum — so a difference "
        "means one of them can no longer spell the other's words and this comparison is "
        "not meaningful."
    )

    # The OFF row's live-state counterpart is RTAG_NONE ("no program installed"), which is
    # the first synthetic row, immediately after the cycle rows.
    none_row = const("RTAG_NONE")
    mismatches = []
    for sub, word in sorted(lab_names.items()):
        rtag_index = none_row if sub == const("LAB_RASTER_OFF") else sub
        if rtag_index >= len(rtag_rows):
            mismatches.append((sub, word, f"no `.rtag_names` row {rtag_index}"))
        elif rtag_rows[rtag_index] != word:
            mismatches.append((sub, word, f"`.rtag_names` row {rtag_index} spells "
                                          f"{rtag_rows[rtag_index]}"))
    assert not mismatches, (
        f"{LAB.name}: the one list's raster names disagree with the live-state raster "
        f"tag's (sub-index, list word, tag): {mismatches}. Selecting a program and seeing "
        "it installed must read as the SAME word in both rows; two words for one program "
        "makes the disagreement that IS meaningful — cursor vs. engine after a section "
        "crossing — impossible to read."
    )
