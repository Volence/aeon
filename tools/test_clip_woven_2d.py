"""The woven mega-act's 2-D bake (docs/research/2026-09-27-mega-act-woven.md §C).

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Rows that
need a donor convert their own into pytest's tmp tree and SKIP SAYING SO when the donor
checkout cannot be resolved (the tools/test_clip_two_zone.py pattern).

WHAT IS PINNED, per §C item:
  * item 6, NEUTRAL FILL (`clips.json` `fill`, clip_manifest K8): every fill cell is the
    stone word on the corridor sheet's zone key and the full solid block on both planes, no
    clip cell changes, an act without a fill has the sheet it always had, K8 refuses by its
    own tag, and the bake's pool rows still add up with the fill counted.
"""

import copy
import json
import os
import sys

import numpy as np
import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_act_bake as CAB                 # noqa: E402
import clip_manifest as CM                  # noqa: E402
import collision_pipeline as CP             # noqa: E402
import s2_donor as S                        # noqa: E402
import s2_zone_convert as C                 # noqa: E402
from suite_paths import SuitePathError      # noqa: E402

REPO = os.path.dirname(TOOLS)
CASES = [(S.S2_FINAL, "EHZ"), (S.S2_FINAL, "CPZ"), (S.S2_FINAL, "MTZ"), (S.S2_FINAL, "OOZ")]
WHY = "test fixture: the woven report's 2-D bake (docs/research/2026-09-27-mega-act-woven.md)"


def _need(donor):
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this row "
                    f"is checked: {e}")


@pytest.fixture(autouse=True, scope="module")
def no_working_tree_donors():
    """No row may read the repo's own (gitignored) converted donor trees (see
    test_clip_manifest's fixture of the same name)."""
    real = CM.DEFAULT_DONOR_ROOT
    CM.DEFAULT_DONOR_ROOT = os.path.join(
        REPO, "tools", "__no_donor_root_for_tests__", "this-path-must-not-exist")
    assert not os.path.exists(CM.DEFAULT_DONOR_ROOT)
    yield
    CM.DEFAULT_DONOR_ROOT = real


@pytest.fixture(scope="module")
def donors(tmp_path_factory):
    root = str(tmp_path_factory.mktemp("s2woven2d"))
    for donor, zone in CASES:
        try:
            S.donor_root(donor)
        except (SystemExit, SuitePathError):
            continue
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    return root


def _rect(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def _clip(cid, zone, src, dst):
    return {"id": cid, "donor": "s2disasm", "zone": zone, "src_rect": _rect(*src),
            "dst_rect": _rect(*dst, src[2], src[3]), "unaligned_dst_reason": WHY}


def _stacked_doc():
    """Emerald Hill over Chemical Plant, 288 px apart, one section wide: the smallest act
    with a vertical seam. Positions on the 16-px grid (K8)."""
    return {"schema": 1, "units": "world_px", "id": "t_stacked", "act": {"grid_w": 1, "grid_h": 2},
            "clips": [_clip("ehz", "EHZ", (6144, 0, 1024, 1024), (512, 256)),
                      _clip("cpz", "CPZ", (7168, 0, 1024, 1024), (512, 1568))]}


def _write(tmp_path, doc, name="clips.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    return str(p)


# ---------------------------------------------------------------------------
# item 6 — the neutral fill
# ---------------------------------------------------------------------------

def _with_fill(doc, rect=(0, 0, 2048, 4096)):
    doc = copy.deepcopy(doc)
    doc["fill"] = {"rect": _rect(*rect), "why": WHY}
    return doc


def test_fill_paints_every_uncovered_cell_solid_stone_and_leaves_the_clips(donors, tmp_path):
    _need(S.S2_FINAL)
    bare = CM.load(_write(tmp_path, _stacked_doc(), "bare.json"), donor_root=donors)
    act = CM.load(_write(tmp_path, _with_fill(_stacked_doc())), donor_root=donors)
    words, zid = CM.cell_grids(act, donors)
    bw, bz = CM.cell_grids(bare, donors)
    m = CM.fill_mask(act)
    # the mask is the fill rect less the clips, DERIVED here from the rects themselves
    want = np.ones((act.rows, act.cols), dtype=bool)
    for c in act.clips:
        x, y, w, h = (v // 8 for v in c.dst)
        want[y:y + h, x:x + w] = False
    assert (m == want).all() and m.sum() == 256 * 512 - 2 * 128 * 128
    # every fill cell: the ONE stone word on CRAM line 0, keyed to the corridor sheet
    art = CM.connector_art(act, donors)
    assert art["fill_word"] >> 13 == CM.CORRIDOR_PAL_LINE == 0
    assert set(np.unique(words[m]).tolist()) == {art["fill_word"]}
    assert act.corridor_key == len(act.zone_table) and (zid[m] == act.corridor_key).all()
    assert act.sheet_table[-1] == CM.CORRIDOR_SHEET
    # every clip cell exactly what it is without the fill
    assert (words[~m] == bw[~m]).all() and (zid[~m] == bz[~m]).all()
    # collision: the corridor floor's full solid block, solid on every side, BOTH planes
    pa, pb = CM.collision_grids(act, donors)
    ba, bb = CM.collision_grids(bare, donors)
    full = CM.corridor_floor_shape(CM.collision_banks(act, donors)) | (
        CP.SOL_ALL << CP.PLANE_SOL_SHIFT)
    for p, b in ((pa, ba), (pb, bb)):
        assert set(np.unique(p[m]).tolist()) == {full}
        assert (p[~m] == b[~m]).all()


def test_an_act_without_a_fill_has_no_sheet_and_no_fill_cells(donors, tmp_path):
    _need(S.S2_FINAL)
    act = CM.load(_write(tmp_path, _stacked_doc()), donor_root=donors)
    assert act.fill is None and not act.has_sheet and act.corridor_key is None
    assert not CM.fill_mask(act).any()
    assert act.sheet_table == act.zone_table


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d["fill"].pop("why"), "no `why`"),
    (lambda d: d["fill"].update(why="  "), "no `why`"),
    (lambda d: d["fill"]["rect"].update(x=8), "collision block grid"),
    (lambda d: d["fill"]["rect"].update(h=4112), "runs past the act"),
    (lambda d: d["clips"][1]["dst_rect"].update(x=520) or
     d["clips"][1]["src_rect"].update(x=7176), "meets the fill with its edge"),
    (lambda d: d.update(fill=[1]), "must be an object"),
])
def test_k8_refuses_a_fill_the_bake_could_not_honour(donors, tmp_path, mutate, needle):
    _need(S.S2_FINAL)
    doc = _with_fill(_stacked_doc())
    CM.load(_write(tmp_path, doc, "ok.json"), donor_root=donors)            # control
    mutate(doc)
    with pytest.raises(CM.ClipManifestError) as exc:
        CM.load(_write(tmp_path, doc), donor_root=donors)
    assert str(exc.value).startswith("K8 ") and needle in str(exc.value), str(exc.value)


def test_the_static_bake_counts_the_fill_in_the_pool_rows(donors, tmp_path):
    _need(S.S2_FINAL)
    path = _write(tmp_path, _with_fill(_stacked_doc()))
    CAB.bake(path, out_dir=str(tmp_path / "baked"), donor_root=donors, log=None)
    m = json.load(open(tmp_path / "baked" / "clipact.json"))
    pool = m["pool"]
    assert m["fill"]["cells"] == int(CM.fill_mask(CM.load(path, donor_root=donors)).sum())
    assert [r["id"] for r in pool["per_fill"]] == ["fill"]
    added = sum(r["tiles_added"] for k in ("per_clip", "per_corridor", "per_fill")
                for r in pool[k])
    assert added + 1 == pool["tiles"], (added, pool["tiles"])
    assert "per_fill" in pool["per_clip_fields"]["tiles_added"]
