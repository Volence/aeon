"""Hold the DEBUG effects-lab RASTER table to the preset documents on disk.

WHAT THIS GATE EXISTS FOR
=========================
`Debug_BandDemoHotkey` (games/sonic4/test/ojz_scroll_test.emp) steps the live raster
program by indexing a `dc.l` table with a cursor it wraps at `RASTER_CYCLE_COUNT`. Three
things have to agree, and NOTHING in sigil can see all three at once:

  1. the preset documents      games/sonic4/data/editor/effects/presets/*.json
  2. `RASTER_CYCLE_COUNT`      games/sonic4/test/ojz_scroll_test.emp
  3. the `.raster_table` rows  same file

sigil cannot see (3) at all: the table lives inside an `if DEBUG == 1 {}` block, its
length is not a comptime value anything can read back, and its rows are Labels. So a
preset document authored without a matching row would leave the program in the ROM with
nothing able to install it, and a `RASTER_CYCLE_COUNT` that drifted above the row count
would make the cursor fetch a pointer from past the table's end and hand it to
`Raster_Install` as a raster program. Both build GREEN.

IT CLOSES A SEAM THE CONTRACT NAMES AS OPEN. `tools/EFFECTS_CONSUMER_CONTRACT.md` §2.4,
"RULES WITH NO ENFORCING ASSERTION", opens with: *"Nothing checks that a preset document
is BOUND ... An authored but unbound preset therefore costs ROM and shows nothing, and no
assertion anywhere says so."* This says it for the DEBUG lab — the only place an
editor-authored program is reachable today. It does NOT close the general case: a preset
bound into a section `preset()` call is still unchecked, and a preset reachable ONLY from
this table is still not content. See docs/EDITOR_RASTER_PRESETS.md §C.

EVERY EXPECTATION IS DERIVED. There is no `2` in this file and no generated symbol name
spelled out. The editor rows are reconstructed by asking `tools/effects_gen.py` — the
generator that emits them — for `act_names(REPO).raster(pid)` over the preset ids it
itself discovers, which is the same call `render_module` makes. Row 0's identity is
derived too: it must be a `pub data` in the game's hand-authored effects library and must
NOT be one of the generated names, which is what "the hand-authored control" means.

LOUD RATHER THAN GREEN WHEN IT CANNOT MEASURE. Every parse below raises with the file and
the pattern it could not find. A gate that quietly finds zero rows and passes is the
vacuity this tree has been bitten by before.

PROVEN RED (2026-08-29), all four arms, by editing the sources and restoring:
  * delete the editor `dc.l` row        -> test_the_editor_rows_are_exactly_the_presets
  * swap the two `dc.l` rows            -> test_row_zero_is_a_hand_authored_program
                                           (and test_the_editor_rows_...)
  * set RASTER_CYCLE_COUNT to 3         -> test_cycle_count_matches_table_length
  * drop the editor name from `use`     -> test_every_table_row_is_imported
  * delete the preset .json             -> test_the_editor_rows_are_exactly_the_presets
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import effects_gen  # noqa: E402

HOTKEY = REPO / "games/sonic4/test/ojz_scroll_test.emp"
HAND_LIB = REPO / "games/sonic4/data/effects/ojz_effects.emp"

_CYCLE_COUNT = re.compile(r"^const\s+RASTER_CYCLE_COUNT\s*=\s*(\d+)\s*$", re.M)
# the table body: `.raster_table:` up to the closing of the DEBUG block
_TABLE_BODY = re.compile(r"^\s*\.raster_table:\s*$(.*?)^\s*\}", re.M | re.S)
_TABLE_ROW = re.compile(r"^\s*dc\.l\s+(\w+)\s*(?://.*)?$", re.M)
_HAND_DATA = re.compile(r"^pub\s+data\s+(\w+)\s*:", re.M)

# The prefix every generated raster label carries, asked of the generator rather than
# typed: `raster("")` is the empty-id spelling of the name it mints for a preset.
GENERATED_PREFIX = effects_gen.act_names(str(REPO)).raster("")


def _read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(
            f"{path} does not exist. This lint holds the DEBUG raster-cycle table to the "
            "preset documents; with either file gone it cannot measure anything and must "
            "not pass. If the hotkey was deliberately removed, delete this lint in the "
            "same commit."
        )
    return path.read_text()


def expected_editor_rows() -> list[str]:
    """The generated label for every preset document, in the generator's emission order.

    `render_module` walks `sorted(presets)` and emits one `pub data names.raster(pid)`
    each; this reconstructs that list through the same two calls, so the expectation
    cannot drift from the emission by being restated.
    """
    presets = effects_gen.load_all_presets(repo=str(REPO))
    names = effects_gen.act_names(str(REPO))
    return [names.raster(pid) for pid in sorted(presets)]


def hand_authored_programs() -> set[str]:
    """Every `pub data` label in the game's hand-authored effects library."""
    src = _read(HAND_LIB)
    found = set(_HAND_DATA.findall(src))
    if not found:
        raise AssertionError(
            f"{HAND_LIB}: found no `pub data <name>:` declarations. Either the file was "
            "reshaped (update the _HAND_DATA pattern here) or the hand-authored effects "
            "library stopped emitting records. Passing on zero would let row 0 of the "
            "raster table be anything at all."
        )
    return found


def table_rows() -> list[str]:
    src = _read(HOTKEY)
    body = _TABLE_BODY.search(src)
    if body is None:
        raise AssertionError(
            f"{HOTKEY}: could not find the `.raster_table:` pointer table inside "
            "Debug_BandDemoHotkey. If the hotkey was removed, delete this lint in the "
            "same commit; if the table was renamed, update this pattern. It must not "
            "silently pass."
        )
    rows = _TABLE_ROW.findall(body.group(1))
    if not rows:
        raise AssertionError(
            f"{HOTKEY}: `.raster_table:` was found but holds no `dc.l` rows. A zero-row "
            "table would make the hotkey index into whatever follows it in ROM and hand "
            "that to Raster_Install as a raster program."
        )
    return rows


def declared_cycle_count() -> int:
    src = _read(HOTKEY)
    m = _CYCLE_COUNT.search(src)
    if m is None:
        raise AssertionError(
            f"{HOTKEY}: could not find `const RASTER_CYCLE_COUNT = <n>`. That const is the "
            "wrap bound the hotkey compiles into its cursor; without it this gate cannot "
            "check the wrap against the table."
        )
    return int(m.group(1))


def test_row_zero_is_a_hand_authored_program():
    """Row 0 is the CONTROL, and it has to be hand-authored to be one.

    The whole value of the second row is the comparison: a band a programmer wrote in
    `.emp` beside a band an author wrote in JSON. If row 0 were itself editor-authored
    there would be no control, and a cold boot's first press — which lands on row 0
    because boot clears RAM — would show the editor's program while every document about
    this chord says it shows OJZ_BandDemo.
    """
    rows = table_rows()
    hand = hand_authored_programs()
    assert not rows[0].startswith(GENERATED_PREFIX), (
        f"row 0 of the raster table is {rows[0]!r}, which carries the generated prefix "
        f"{GENERATED_PREFIX!r} — it is editor-authored, so the table has no hand-authored "
        "control and the first press from a cold boot no longer shows what this chord is "
        "documented to show."
    )
    assert rows[0] in hand, (
        f"row 0 of the raster table is {rows[0]!r}, which is not a `pub data` in "
        f"{HAND_LIB.name}. Row 0 must be a hand-authored program that actually exists; an "
        "unresolved name in a Label position becomes a silent link extern in .emp, so "
        "this is the only place that misspelling can be caught."
    )


def test_the_editor_rows_are_exactly_the_presets():
    """Every preset document has a row, every editor row has a document, same order."""
    expected = expected_editor_rows()
    got = [r for r in table_rows() if r.startswith(GENERATED_PREFIX)]
    assert got == expected, (
        "the editor-authored rows of the DEBUG raster table do not match the preset "
        "documents in games/sonic4/data/editor/effects/presets/. Table has "
        f"{got}; the generator emits {expected} (sorted by preset id, which is "
        "`render_module`'s own emission order). A preset with no row costs ROM for a "
        "program nothing in either shape can install; a row with no preset is a name "
        "sigil resolves as a silent link extern."
    )


def test_cycle_count_matches_table_length():
    """The compiled wrap bound must be exactly the number of table rows."""
    n = declared_cycle_count()
    rows = len(table_rows())
    assert n == rows, (
        f"RASTER_CYCLE_COUNT is {n} but the DEBUG raster table holds {rows} rows. The "
        "hotkey wraps its cursor at RASTER_CYCLE_COUNT and then indexes this table, so a "
        f"cursor of {rows}..{n - 1} would fetch a pointer from past the table's end and "
        "hand it to Raster_Install as a raster program."
    )


def test_every_table_row_is_imported():
    """Each row must be a NAMED import, not a silent link extern.

    Same mechanism, same reason, as `test_scene_cycle_table_lint.test_every_table_row_is_imported`:
    an unknown name in a Label position does not error in `.emp`, it silently becomes an
    extern, so a misspelling would surface as a wrong picture rather than a build failure.
    """
    src = _read(HOTKEY)
    imported: set[str] = set()
    for m in re.finditer(r"use\s+games\.sonic4\.\w+\.\{([^}]*)\}", src, re.S):
        imported.update(n.strip() for n in m.group(1).split(",") if n.strip())
    if not imported:
        raise AssertionError(
            f"{HOTKEY}: found no `use games.sonic4.<module>.{{…}}` name lists at all. Every "
            "row in the raster table must be a named import or a misspelling becomes a "
            "silent extern."
        )
    missing = sorted(set(table_rows()) - imported)
    assert not missing, (
        f"{HOTKEY}: these raster-table rows are not in any `use games.sonic4.<module>.{{…}}` "
        f"list: {missing}. Unimported, a misspelled one would resolve as a link extern and "
        "the table would point at nothing the build ever complains about."
    )
