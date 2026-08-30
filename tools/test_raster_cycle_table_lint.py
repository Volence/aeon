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
assertion anywhere says so."* It now says it for BOTH installers.

RELAXED 2026-08-30, AND THE RELAXATION IS THE DANGEROUS DIRECTION SO READ WHY.
The reachability arm used to be a HARD EQUALITY: the table's editor rows were exactly the
preset documents on disk. That was correct while the DEBUG chord was the ONLY installer —
a document with no row was ROM nobody could reach. The `rasterRef` arm (EFFECTS-W1 item 1)
adds a SECOND installer: a section sidecar names a document and the generated chooser
threads its program into that section's `preset()` call. Under the old equality, authoring
a band through Aurora would STILL have required a hand-typed `dc.l` here plus a
`RASTER_CYCLE_COUNT` bump — a programmer's edit, which is the exact thing item 1 exists to
remove. The gate would have falsified its own feature's headline claim.

So the arm is now a DISJUNCTION and nothing weaker: every preset document must be reachable
by (a) a `.raster_table` row, or (b) a `rasterRef` binding in some section sidecar. A
document reachable by NEITHER is still ROM nobody can install, and that is still red. The
converse direction did NOT relax — a row naming no document is still a silent link extern
and is still red, in its own test now that the equality is gone.

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

RE-PROVEN RED (2026-08-30) after the relaxation, every arm firing ALONE — because a gate
that was loosened has to be shown to still catch what it caught, not merely to permit the
new case:
  * delete the editor `dc.l` row        -> test_every_preset_document_is_REACHABLE
  * add a row naming no document        -> test_every_editor_row_has_a_preset_document
  * two docs, rows in the wrong order   -> test_the_editor_rows_are_in_emission_order
  * swap row 0 for the editor row       -> test_row_zero_is_a_hand_authored_program
  * set RASTER_CYCLE_COUNT to 3         -> test_cycle_count_matches_table_length
  * drop the editor name from `use`     -> test_every_table_row_is_imported

THE DISJUNCTION ITSELF is proven twice, at two levels.

  * `unreachable_presets()` is a PURE FUNCTION over three sets, unit-tested below in all
    four combinations of (row, binding). It is a pure function so that the arm can be
    exercised without a sidecar at all — which mattered when it was written, because
    `rasterRef` was then forbidden in any sidecar until aurora's `SectionMeta` extension
    landed, and a relaxed arm exercisable only by violating the precondition it waits on
    would never be exercised.
  * ON THE REAL TREE, 2026-08-30, once that precondition was DISCHARGED (aurora master
    `7b1d15a0`, "sidecar: rasterRef, the per-section raster-preset binding"): the editor
    `dc.l` row was deleted and `authored_probe` bound instead through a real
    `section_5.meta.json` — **11 passed**. Removing only that sidecar, leaving everything
    else identical, turns `test_every_preset_document_is_REACHABLE` **red**. The single
    file is the whole difference between the two runs, which is what makes the (b) arm a
    measurement rather than a unit-test analogy. Both states were reverted; no sidecar in
    this tree carries the key, which is what step 3's four-CRC byte-identity rests on.
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


def bound_preset_ids() -> set[str]:
    """Every preset id a section sidecar binds through `rasterRef`.

    Read through `effects_gen`'s own loader, so this gate and the generator cannot
    disagree about what a binding is, and NOTHING here spells the wire key — it lives
    once, as `effects_gen.ACT_RASTER_REF_KEY`.
    """
    return set(effects_gen.load_section_raster_refs(repo=str(REPO)).values())


def unreachable_presets(preset_ids, row_ids, bound_ids) -> list[str]:
    """The documents no installer can reach: NOT in a table row and NOT bound.

    A PURE FUNCTION taking three sets, and that is deliberate. The disjunction is the
    part of this gate that was loosened, so it is the part that has to be tested in
    every combination — including "reachable only by a binding", which cannot be staged
    on the real tree because no `rasterRef` may be written into a sidecar until aurora's
    SectionMeta extension lands. Passing the three sets in makes that arm testable
    without violating the precondition it is waiting on.

    `row_ids` and `bound_ids` are PRESET IDS, not labels — the caller converts, so this
    function has no opinion about symbol spelling.
    """
    return sorted(set(preset_ids) - set(row_ids) - set(bound_ids))


def row_preset_ids(rows) -> list[str]:
    """The preset id behind each editor-authored table row, in table order.

    Derived by stripping the generator's own prefix rather than by re-deriving the name,
    so a row that is NOT a generated label simply is not an editor row.
    """
    return [r[len(GENERATED_PREFIX):] for r in rows if r.startswith(GENERATED_PREFIX)]


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


def test_every_preset_document_is_REACHABLE():
    """A row OR a `rasterRef` binding. Neither alone, and NEITHER IS STILL RED.

    This is the relaxed arm. It is not "reachability is now optional": a document that
    no `.raster_table` row names and that no section sidecar binds is a raster program
    in the ROM that nothing in either shape can install, which is precisely the waste
    this gate was built to catch. What changed is that a SECOND installer now counts.
    """
    presets = effects_gen.load_all_presets(repo=str(REPO))
    rows = row_preset_ids(table_rows())
    bound = bound_preset_ids()
    orphans = unreachable_presets(presets, rows, bound)
    assert not orphans, (
        f"these preset documents in games/sonic4/data/editor/effects/presets/ are "
        f"reachable by NOTHING: {orphans}. A preset document reaches the running game "
        f"through one of exactly two installers — a `dc.l` row in "
        f"{HOTKEY.name}'s `.raster_table` (the DEBUG lab chord), or a "
        f"`{effects_gen.ACT_RASTER_REF_KEY}` in a section sidecar, which the generated "
        f"chooser threads into that section's `preset()` call. With neither, the "
        f"program's bytes are in the ROM and no code path can ever point the raster "
        f"engine at them. Table rows name {sorted(rows)}; sidecar bindings name "
        f"{sorted(bound)}."
    )


def test_every_editor_row_has_a_preset_document():
    """The converse direction, and it did NOT relax.

    Split out of the old equality rather than dropped with it: a row naming a document
    that does not exist is a name `.emp` resolves as a SILENT LINK EXTERN, so the table
    would point at nothing the build ever complains about. Adding a second installer
    changes nothing about that — it is still one-directional and still hard.
    """
    presets = effects_gen.load_all_presets(repo=str(REPO))
    ghosts = sorted(set(row_preset_ids(table_rows())) - set(presets))
    assert not ghosts, (
        f"these editor-authored rows of the DEBUG raster table name preset documents "
        f"that do not exist: {ghosts}. An unresolved name in a Label position does not "
        f"error in `.emp` — it becomes a link extern — so the row would point at "
        f"whatever the linker resolves it to, or at nothing. Known documents: "
        f"{sorted(presets)}."
    )


def test_the_editor_rows_are_in_emission_order():
    """The rows that DO exist stay in `render_module`'s own order (sorted preset id).

    Kept from the equality it was folded into. The value is small and real: the table is
    read by a human stepping a cursor through it, and rows in a different order from the
    generator's emission make the listing and the chord disagree about which band is
    which.
    """
    rows = row_preset_ids(table_rows())
    assert rows == sorted(rows), (
        f"the editor-authored rows of the DEBUG raster table are in the order {rows}, "
        f"which is not the generator's emission order ({sorted(rows)} — "
        f"`render_module` walks `sorted(presets)`)."
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


# ---------------------------------------------------------------------------
# THE DISJUNCTION, IN ALL FOUR COMBINATIONS.
#
# `unreachable_presets` is the one piece of judgement the relaxation added, so it is the
# one piece that gets exhaustive coverage. These are unit tests over sets and touch no
# file: the "reachable only by a binding" case cannot be staged on the real tree, because
# writing a `rasterRef` into a sidecar is forbidden until aurora's SectionMeta extension
# is on their master (empyrean §3.1). A relaxed arm that could not be exercised at all
# would be the vacuity this file's header warns about, arriving through the new door.
# ---------------------------------------------------------------------------

def test_a_document_reachable_by_a_ROW_ONLY_is_reachable():
    assert unreachable_presets({"a"}, ["a"], set()) == []


def test_a_document_reachable_by_a_BINDING_ONLY_is_reachable():
    assert unreachable_presets({"a"}, [], {"a"}) == []


def test_a_document_reachable_by_BOTH_is_reachable():
    assert unreachable_presets({"a"}, ["a"], {"a"}) == []


def test_a_document_reachable_by_NEITHER_is_REPORTED():
    """The whole point of keeping a gate here. If this ever passes, the relaxation
    turned the arm off instead of widening it."""
    assert unreachable_presets({"a"}, [], set()) == ["a"]


def test_only_the_unreachable_ones_are_reported():
    assert unreachable_presets({"a", "b", "c"}, ["a"], {"b"}) == ["c"]
