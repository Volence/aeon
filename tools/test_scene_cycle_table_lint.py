"""Hold the DEBUG effects-lab hotkey's pointer table to the scene registry.

WHAT THIS GATE EXISTS FOR
=========================
`Debug_SceneCycleHotkey` (games/sonic4/test/ojz_scroll_test.emp) steps the live
background scene by indexing a twenty-entry `dc.l` table with a cursor it wraps at
`SCENE_CYCLE_COUNT`. Three things have to agree for that to be safe, and NOTHING in
sigil can see all three at once:

  1. `SCENES[]`                      games/sonic4/data/effects/scene_registry.emp
  2. `SCENE_CYCLE_COUNT`             same file (a mirror; sigil pins it to `SCENES.len`)
  3. the `dc.l` table                games/sonic4/test/ojz_scroll_test.emp

sigil covers 1<->2 with a build-fatal `ensure`. It CANNOT cover 3: the table lives
inside an `if DEBUG == 1 {}` block in a different module, its length is not a comptime
value anything can read back, and its rows are Labels — so a registry that grew a
twenty-first scene would leave the cursor wrapping at 21 while the table still held 20
entries, and index 20 would fetch whatever `dc.l` run follows it in ROM and hand that to
`Parallax_StartTransition` as a `parallax_config*`. That is a wrong picture at best and
a wild pointer at worst, and it would build GREEN.

So the coupling is checked as TEXT, the way the palette committer census is
(engine/system/buffers.emp + tools/test_palette_census_lint.py). Same species of pin,
same acknowledged limit: this reads source, not the ROM.

EVERY EXPECTATION IS DERIVED. There is no `20` in this file. The registry's own
emission block — `pub data ParallaxConfig_X: SceneCfgN = lowerN(SCENES[i])` — states
both the NAME and the INDEX of each record, so the expected table is reconstructed from
it and compared row for row. That makes this an ORDER check as well as a length check:
the hotkey's cycle order is documented as the registry order, and a table whose rows
were shuffled would be silently wrong to a reviewer who trusted the order.

LOUD RATHER THAN GREEN WHEN IT CANNOT MEASURE. Every parse below raises with the file
and the pattern it could not find. A gate that quietly finds zero rows and passes is the
vacuity this tree has been bitten by before.

PROVEN RED (2026-08-26), all four arms, by editing the sources and restoring:
  * delete one `dc.l` row              -> test_table_matches_registry_emission_order
  * swap two `dc.l` rows               -> test_table_matches_registry_emission_order
  * set SCENE_CYCLE_COUNT to 19        -> test_cycle_count_matches_table_length
                                          (and sigil's own ensure fails the build first)
  * drop a name from the `use` list    -> test_every_table_row_is_imported
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTRY = REPO / "games/sonic4/data/effects/scene_registry.emp"
HOTKEY = REPO / "games/sonic4/test/ojz_scroll_test.emp"

# `pub data ParallaxConfig_OJZ_Default:          SceneCfg4 = lower4(SCENES[0])`
_EMISSION = re.compile(
    r"^pub\s+data\s+(ParallaxConfig_\w+)\s*:\s*\w+\s*=\s*lower\d+\(\s*SCENES\[(\d+)\]\s*\)",
    re.M,
)
_CYCLE_COUNT = re.compile(r"^pub\s+const\s+SCENE_CYCLE_COUNT\s*=\s*(\d+)\s*$", re.M)
_SCENES_DECL = re.compile(r"^pub\s+const\s+SCENES\s*:\s*\[\s*Scene\s*;\s*(\d+)\s*\]", re.M)
# the table body: `.scene_table:` up to the closing of the DEBUG block
_TABLE_BODY = re.compile(r"^\s*\.scene_table:\s*$(.*?)^\s*\}", re.M | re.S)
_TABLE_ROW = re.compile(r"^\s*dc\.l\s+(ParallaxConfig_\w+)\s*(?://.*)?$", re.M)


def _read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(
            f"{path} does not exist. This lint holds the DEBUG scene-cycle table to the "
            "scene registry; with either file gone it cannot measure anything and must "
            "not pass. If the hotkey was deliberately removed, delete this lint in the "
            "same commit."
        )
    return path.read_text()


def registry_emission_order() -> list[str]:
    """[name] indexed by the SCENES[] index each `pub data` line lowers."""
    src = _read(REGISTRY)
    pairs = [(int(idx), name) for name, idx in _EMISSION.findall(src)]
    if not pairs:
        raise AssertionError(
            f"{REGISTRY}: found no `pub data ParallaxConfig_*: SceneCfgN = lowerN(SCENES[i])` "
            "emission lines. Either the emission block was reshaped (update the _EMISSION "
            "pattern in this file) or the registry stopped emitting the scene records. "
            "Passing on zero rows would make this gate vacuous."
        )
    seen = {}
    for idx, name in pairs:
        assert idx not in seen, (
            f"{REGISTRY}: SCENES[{idx}] is lowered twice — by {seen[idx]} and by {name}. "
            "Each registry index must emit exactly one record."
        )
        seen[idx] = name
    missing = sorted(set(range(len(pairs))) - set(seen))
    assert not missing, (
        f"{REGISTRY}: the emission block lowers {len(pairs)} records but leaves SCENES "
        f"indices {missing} unemitted — the indices are not a dense 0..N-1 run, so the "
        "hotkey's cursor cannot be an index into them."
    )
    return [seen[i] for i in range(len(pairs))]


def hotkey_table_rows() -> list[str]:
    src = _read(HOTKEY)
    body = _TABLE_BODY.search(src)
    if body is None:
        raise AssertionError(
            f"{HOTKEY}: could not find the `.scene_table:` pointer table inside "
            "Debug_SceneCycleHotkey. If the hotkey was removed, delete this lint in the "
            "same commit; if the table was renamed, update this pattern. It must not "
            "silently pass."
        )
    rows = _TABLE_ROW.findall(body.group(1))
    if not rows:
        raise AssertionError(
            f"{HOTKEY}: `.scene_table:` was found but holds no `dc.l ParallaxConfig_*` "
            "rows. A zero-row table would make the hotkey index into whatever follows it "
            "in ROM."
        )
    return rows


def declared_cycle_count() -> int:
    src = _read(REGISTRY)
    m = _CYCLE_COUNT.search(src)
    if m is None:
        raise AssertionError(
            f"{REGISTRY}: could not find `pub const SCENE_CYCLE_COUNT = <n>`. That const is "
            "the wrap bound the hotkey compiles into its cursor; without it this gate "
            "cannot check the wrap against the table."
        )
    return int(m.group(1))


def declared_scenes_len() -> int:
    src = _read(REGISTRY)
    m = _SCENES_DECL.search(src)
    if m is None:
        raise AssertionError(
            f"{REGISTRY}: could not find the `pub const SCENES: [Scene; N]` declaration."
        )
    return int(m.group(1))


def test_table_matches_registry_emission_order():
    """Row i of the table must be the record the registry lowers from SCENES[i]."""
    expected = registry_emission_order()
    got = hotkey_table_rows()
    assert len(got) == len(expected), (
        f"the DEBUG scene-cycle table in {HOTKEY.name} holds {len(got)} rows but the "
        f"registry emits {len(expected)} scene records. Add or remove the row(s) so the "
        "cursor cannot index past the table — the hotkey wraps at SCENE_CYCLE_COUNT, "
        "which is pinned to SCENES.len, not to this table's length."
    )
    mismatches = [
        (i, e, g) for i, (e, g) in enumerate(zip(expected, got)) if e != g
    ]
    assert not mismatches, (
        "the DEBUG scene-cycle table is not in registry emission order. Row i must be the "
        "record the registry lowers from SCENES[i], because the hotkey's documented cycle "
        "order IS the registry order and a reviewer reads the two side by side. "
        "Mismatches (index, expected, found): "
        + "; ".join(f"{i}: {e} != {g}" for i, e, g in mismatches)
    )


def test_cycle_count_matches_table_length():
    """The compiled wrap bound must be exactly the number of table rows."""
    n = declared_cycle_count()
    rows = len(hotkey_table_rows())
    assert n == rows, (
        f"SCENE_CYCLE_COUNT is {n} but the DEBUG scene-cycle table holds {rows} rows. The "
        "hotkey wraps its cursor at SCENE_CYCLE_COUNT and then indexes this table, so a "
        f"cursor of {rows}..{n - 1} would fetch a pointer from past the table's end and "
        "hand it to Parallax_StartTransition as a parallax_config*."
    )


def test_cycle_count_matches_scenes_declaration():
    """The mirror must equal the array it mirrors.

    sigil already fails the build on this (`ensure(SCENE_CYCLE_COUNT == SCENES.len)`),
    which is the authority. Re-checked here against the DECLARED `[Scene; N]` arity —
    a second, independent reading of the same fact — so this suite reports the whole
    coupling in one place instead of leaving a reader to correlate a build error with a
    test failure.
    """
    n = declared_cycle_count()
    decl = declared_scenes_len()
    assert n == decl, (
        f"SCENE_CYCLE_COUNT is {n} but SCENES is declared `[Scene; {decl}]` in "
        f"{REGISTRY.name}. sigil's own ensure fails the build on this too; fix the mirror."
    )


def test_scenes_declaration_matches_emission_count():
    """Every declared scene must be lowered to a record the table can point at."""
    decl = declared_scenes_len()
    emitted = len(registry_emission_order())
    assert decl == emitted, (
        f"SCENES is declared `[Scene; {decl}]` but the emission block lowers {emitted} "
        "records. A scene with no record cannot be installed by the hotkey (or by a "
        "section), and a record with no scene cannot exist — the emission block indexes "
        "SCENES directly."
    )


def test_every_table_row_is_imported():
    """Each row must be a NAMED import, not a silent link extern.

    An unknown name in a Label position does not error in .emp — it silently becomes an
    extern (games/sonic4/data/levels/ojz/act1/act_descriptor.emp:26). In a twenty-entry
    pointer table a misspelling would therefore surface as a runtime wrong picture, never
    as a build failure. The explicit `use` list is what turns it back into a build error,
    so the list is part of the mechanism and is checked here.
    """
    src = _read(HOTKEY)
    imported: set[str] = set()
    for m in re.finditer(r"use\s+games\.sonic4\.scene_registry\.\{([^}]*)\}", src, re.S):
        imported.update(n.strip() for n in m.group(1).split(",") if n.strip())
    if not imported:
        raise AssertionError(
            f"{HOTKEY}: found no `use games.sonic4.scene_registry.{{…}}` name list. Every "
            "ParallaxConfig_* row in the scene-cycle table must be a named import or a "
            "misspelling becomes a silent extern."
        )
    missing = sorted(set(hotkey_table_rows()) - imported)
    assert not missing, (
        f"{HOTKEY}: these scene-cycle table rows are not in any "
        f"`use games.sonic4.scene_registry.{{…}}` list: {missing}. Unimported, a "
        "misspelled one would resolve as a link extern and the table would point at "
        "nothing the build ever complains about."
    )
