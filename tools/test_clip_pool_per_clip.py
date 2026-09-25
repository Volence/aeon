"""Gate: clipact.json's per-clip pool rows (`pool.per_clip`, `pool.per_corridor`) agree with
the act-level pool figures, AND with the tree the bake emitted.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Rows
convert their own donors into pytest's tmp tree (the test_clip_manifest pattern) and SKIP
SAYING SO when the donor checkout cannot be resolved.

WHY THIS EXISTS. Aurora's Sonic 2 donor page asked for per-clip unique-tile and page counts
(design §8, RULED 2026-09-25 block, accepted as row-8 work). `clip_act_bake.pool_contributions`
derives them from the placement dict the act-level `pool.tiles` / `pool.pages` come from.

WHAT MAKES THIS MORE THAN A RESTATEMENT. The rows are produced from the IN-MEMORY placement
(`canon`, `page_grid`). This gate recomputes every row from the EMITTED tree instead —
`section_N.local.bin` through `secN_local_map.bin` to a global pool slot per cell, exactly
the decode `clip_act_bake.page_grid_from_tree` does for the window recount — so a row that
disagrees with it is a row that does not describe the bytes. Then it holds the rows to the
act-level figures by identities that are DERIVED from the field definitions, not copied:

  * the union of every row's tile set, plus the blank at slot 0, IS the set of occupied pool
    slots (pool.page_lengths) — and has pool.tiles members;
  * sum(tiles_added) + 1 == pool.tiles (the "+1" is the blank, excluded from every row);
  * the union of every row's pages is range(pool.pages);
  * pages_exclusive <= pages_touched per row, and sum(pages_exclusive) <= pool.pages.

The fixtures are all four committed clip acts, chosen because between them they reach both
placement rungs (s2_two_clip is `searched`, i.e. zone-split canonicals; the others `shipped`),
a corridor row (s2_ehz_cpz) and a single-clip act (s2_ehz_boot). A row asserts the fixture
really reaches the rung/corridor it is here for, so the coverage cannot quietly lapse.
"""

import json
import os
import struct
import sys

import numpy as np
import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_act_bake as BAKE                # noqa: E402
import clip_manifest as CM                  # noqa: E402
import fg_page_order as fpo                 # noqa: E402
import s2_donor as S                        # noqa: E402
import s2_zone_convert as C                 # noqa: E402
from suite_paths import SuitePathError      # noqa: E402

REPO = os.path.dirname(TOOLS)
FIXTURE_DIR = os.path.join(REPO, "games", "sonic4", "data", "clips")
CASES = [(S.S2_FINAL, "EHZ"), (S.S2_FINAL, "CPZ")]
#: fixture -> (the rung it is here to cover, does it carry a corridor)
FIXTURES = {
    "s2_two_clip": ("searched", False),
    "s2_two_clip_pins": ("shipped", False),
    "s2_ehz_cpz": ("shipped", True),
    "s2_ehz_boot": ("shipped", False),
}
ROW_KEYS = {"id", "index", "tiles", "tiles_added", "pages_touched", "pages_exclusive"}


def _need(donor):
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this row "
                    f"is checked: {e}")


@pytest.fixture(autouse=True, scope="module")
def no_working_tree_donors():
    """No row may read the repo's own (gitignored) converted donor trees — see
    test_clip_manifest's fixture of the same name for the incident it prevents."""
    real = CM.DEFAULT_DONOR_ROOT
    CM.DEFAULT_DONOR_ROOT = os.path.join(
        REPO, "tools", "__no_donor_root_for_tests__", "this-path-must-not-exist")
    assert not os.path.exists(CM.DEFAULT_DONOR_ROOT)
    yield
    CM.DEFAULT_DONOR_ROOT = real


@pytest.fixture(scope="module")
def baked(tmp_path_factory):
    for donor, _zone in CASES:
        _need(donor)
    root = str(tmp_path_factory.mktemp("perclipdonors"))
    for donor, zone in CASES:
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    out_root = tmp_path_factory.mktemp("perclipbake")
    out = {}
    for name in FIXTURES:
        src = os.path.join(FIXTURE_DIR, name, "clips.json")
        d = str(out_root / name)
        act, _st, _m, _v1, _v2 = BAKE.bake(src, out_dir=d, donor_root=root, log=None)
        with open(os.path.join(d, "clipact.json")) as fh:
            out[name] = (act, json.load(fh), d)       # the file ON DISK, not the dict
    return out


def _global_slots(act, out_dir):
    """(rows, cols) global pool slot per cell, decoded off the emitted tree."""
    sect = act.section_tiles
    g = np.zeros((act.rows, act.cols), dtype=np.int64)
    for s_idx in range(act.grid_w * act.grid_h):
        sy, sx = divmod(s_idx, act.grid_w)
        with open(os.path.join(out_dir, f"section_{s_idx}.local.bin"), "rb") as fh:
            nt = np.frombuffer(fh.read(), dtype=">u2").reshape(sect, sect).astype(np.int64)
        with open(os.path.join(out_dir, f"sec{s_idx}_local_map.bin"), "rb") as fh:
            raw = fh.read()
        lmap = np.array(struct.unpack(f">{len(raw) // 2}H", raw), dtype=np.int64)
        g[sy * sect:(sy + 1) * sect, sx * sect:(sx + 1) * sect] = \
            lmap[nt & BAKE.TILE_MASK]
    return g


def _disk_sets(act, out_dir):
    """[(kind, rect, tile-slot set, page set)] per clip then corridor, from disk."""
    shift = fpo.load_budget_constants()["PAGE_FRAME_TILE_SHIFT"]
    g = _global_slots(act, out_dir)
    out = []
    for kind, r in [("clip", c) for c in act.clips] + [("corridor", c) for c in act.corridors]:
        dx, dy, w, h = (v // CM.TILE_PX for v in r.dst)
        slots = {int(s) for s in np.unique(g[dy:dy + h, dx:dx + w])} - {0}
        out.append((kind, r, slots, {s >> shift for s in slots}))
    return out


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_reaches_what_it_is_here_for(baked, name):
    act, m, _d = baked[name]
    rung, has_corridor = FIXTURES[name]
    assert m["placement"]["rung"] == rung, (name, m["placement"]["rung"])
    assert bool(act.corridors) == has_corridor
    assert len(m["pool"]["per_clip"]) == len(m["clips"])
    assert len(m["pool"]["per_corridor"]) == len(m["corridors"])
    assert set(m["pool"]["per_clip_fields"]) == ROW_KEYS
    for row in m["pool"]["per_clip"] + m["pool"]["per_corridor"]:
        assert set(row) == ROW_KEYS, row


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_rows_match_the_emitted_tree(baked, name):
    """Every row, recomputed off disk, equals what clipact.json says."""
    act, m, d = baked[name]
    rows = m["pool"]["per_clip"] + m["pool"]["per_corridor"]
    sets = _disk_sets(act, d)
    touch = {}
    for _k, _r, _s, pages in sets:
        for p in pages:
            touch[p] = touch.get(p, 0) + 1
    seen = set()
    for row, (_kind, r, slots, pages) in zip(rows, sets):
        want = {"id": r.id, "index": r.index, "tiles": len(slots),
                "tiles_added": len(slots - seen), "pages_touched": len(pages),
                "pages_exclusive": sum(1 for p in pages if touch[p] == 1)}
        seen |= slots
        assert row == want, (name, row, want)


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_rows_add_up_to_the_act(baked, name):
    """The per-rectangle figures and the act-level pool figures describe one pool."""
    act, m, d = baked[name]
    pool = m["pool"]
    rows = pool["per_clip"] + pool["per_corridor"]
    sets = _disk_sets(act, d)
    page_tiles = pool["page_tiles"]
    occupied = {p * page_tiles + i
                for p, n in enumerate(pool["page_lengths"]) for i in range(n)}
    union = set().union(*(s for _k, _r, s, _p in sets)) | {0}
    assert union == occupied, (name, len(union), len(occupied))
    assert len(union) == pool["tiles"]
    assert sum(r["tiles_added"] for r in rows) + 1 == pool["tiles"], (name, rows, pool["tiles"])
    assert set().union(*(p for _k, _r, _s, p in sets)) == set(range(pool["pages"]))
    assert all(r["pages_exclusive"] <= r["pages_touched"] for r in rows), rows
    assert sum(r["pages_exclusive"] for r in rows) <= pool["pages"]
    assert all(r["tiles"] > 0 for r in rows), rows      # no vacuous empty row
