"""The woven mega-act's 2-D bake (docs/research/2026-09-27-mega-act-woven.md §C).

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Rows that
need a donor convert their own into pytest's tmp tree and SKIP SAYING SO when the donor
checkout cannot be resolved (the tools/test_clip_two_zone.py pattern).

WHAT IS PINNED, per §C item:
  * item 2, SHAFTS (`clips.json` `shafts`, clip_manifest K7/K9/K10): walls, air lane and
    top-only ledges at the pitch, derived from the rect; every shaft pixel painted on line 0
    (no background shows), a cloud band's holes the sky; K7/K9/K10 refuse by their own tag
    with controls; the ledge pitch bound is the least jump rise, re-derived here in closed
    form from the same constants; the static bake counts shafts in the pool rows;
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
            "clips": [_clip("ehz", "EHZ", (4096, 0, 1024, 1024), (512, 256)),
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


# ---------------------------------------------------------------------------
# item 2 — shafts
# ---------------------------------------------------------------------------
#
# The fixture's seam: Emerald Hill (donor x 4096..5119) ends at act y 1280 and Chemical
# Plant starts at 1568, 288 px below (the report's same-blob vertical seam). Emerald Hill's
# last collision block row is open from the side and below at donor x 4288..4655 and CAPPED
# at 4256..4287 (MEASURED from the converted tree; `test_k10_*` re-reads it through K10
# itself, so a donor change fails loudly rather than moving the lane silently).
LANE_OPEN = 768             # act x of donor 4352: open
LANE_CAPPED = 672           # act x of donor 4256: capped


def _with_shaft(doc, **kw):
    doc = copy.deepcopy(doc)
    sh = {"id": "drop", "dst_rect": _rect(640, 1280, 256, 288),
          "lane": {"x": LANE_OPEN, "w": 64}}
    sh.update(kw)
    doc["shafts"] = [sh]
    return doc


def _cloud_art():
    """Emerald Hill art: wall_src has opaque pixels and holes (616 of 4096 transparent),
    back_src is sky with NO opaque pixel (MEASURED from the converted tree), so every
    open lane pixel is a hole and shows exactly which colour holes are painted."""
    return {"donor": "s2disasm", "zone": "EHZ", "wall_src": _rect(4096, 512, 64, 64),
            "back_src": _rect(4096, 0, 64, 64)}


def _pixels(sheet, word):
    t = sheet[(word & 0x7FF) * 32:(word & 0x7FF) * 32 + 32]
    return [(b >> 4, b & 15)[i] for b in t for i in (0, 1)]


def test_a_shaft_is_walls_an_air_lane_and_top_only_ledges(donors, tmp_path):
    _need(S.S2_FINAL)
    act = CM.load(_write(tmp_path, _with_shaft(_stacked_doc(), ledges={"pitch": 64, "w": 32})),
                  donor_root=donors)
    sh = act.shafts[0]
    assert (sh.axis, CM.connector_ends(act, sh)[1].id, CM.connector_ends(act, sh)[2].id) == \
        ("y", "ehz", "cpz")
    words, ledges = CM.shaft_collision(act, sh, donors)
    shape = CM.corridor_floor_shape(CM.collision_banks(act, donors))
    full = shape | (CP.SOL_ALL << CP.PLANE_SOL_SHIFT)
    top = shape | (CP.SOL_TOP << CP.PLANE_SOL_SHIFT)
    x0, y0, w, h = sh.dst
    l0 = (sh.lane[0] - x0) // 8
    l1 = l0 + sh.lane[1] // 8
    # walls: every column outside the lane, every row
    assert (words[:, :l0] == full).all() and (words[:, l1:] == full).all()
    # ledges DERIVED from the rect: bottom - k x pitch for every k that stays inside it,
    # alternately left and right, `w` wide, one block row each, top-solid only
    want = [(y0 + h - k * 64, "left" if k % 2 else "right")
            for k in range(1, h // 64 + 1) if y0 + h - k * 64 >= y0]
    assert [(e["y"], e["side"]) for e in ledges] == want and len(want) == 4
    lane = words[:, l0:l1].copy()
    for y, side in want:
        r = (y - y0) // 8
        cols = slice(0, 4) if side == "left" else slice(l1 - l0 - 4, l1 - l0)
        assert (lane[r:r + 2, cols] == top).all()
        lane[r:r + 2, cols] = 0
    assert (lane == 0).all()                     # the rest of the lane is air
    pa, pb = CM.collision_grids(act, donors)
    for p in (pa, pb):
        assert (p[y0 // 8:(y0 + h) // 8, x0 // 8:(x0 + w) // 8] == words).all()


@pytest.mark.parametrize("look,art", [("rock", None), ("rock", "art"), ("cloud", "art")])
def test_every_shaft_pixel_is_painted_on_line_0(donors, tmp_path, look, art):
    """No background shows through a shaft (the tunnel's rule on its side): every pixel of
    every tile its words name is opaque, and every word is on CRAM line 0."""
    _need(S.S2_FINAL)
    kw = {"look": look, "ledges": {"pitch": 64, "w": 32}}
    if art:
        kw["art"] = _cloud_art()
    act = CM.load(_write(tmp_path, _with_shaft(_stacked_doc(), **kw)), donor_root=donors)
    art_ = CM.connector_art(act, donors)
    sw = art_["shafts"][0][0]
    assert set((np.unique(sw) >> 13).tolist()) == {CM.CORRIDOR_PAL_LINE}
    for wd in np.unique(sw).tolist():
        assert 0 not in _pixels(art_["sheet"], wd), f"word ${wd:04X} has a transparent pixel"
    line0 = CM._palette_lines(open(CM.LINE0_PALETTE, "rb").read()[:32])[0]
    sky = CM._nearest_line0(CM._genesis_rgb(CM.CLOUD_SKY_WORD), line0)
    assert sky != CM.TUNNEL_HOLE_COLOUR
    # the OPEN lane cells (air in the shaft's own collision): back_src is all holes, so each
    # is painted wholly in the hole colour its look names — the sky for a cloud band, the
    # tunnel's dark hole for rock art, the mortar for plain rock
    cw, _l = CM.shaft_collision(act, act.shafts[0], donors)
    x0, _y0, _w, _h = act.shafts[0].dst
    lane = slice((act.shafts[0].lane[0] - x0) // 8,
                 (act.shafts[0].lane[0] + act.shafts[0].lane[1] - x0) // 8)
    open_words = set(sw[:, lane][cw[:, lane] == 0].tolist())
    want = (sky if look == "cloud" else CM.TUNNEL_HOLE_COLOUR if art
            else CM.CORRIDOR_COLOURS["mortar"])
    assert open_words and {px for wd in open_words for px in _pixels(art_["sheet"], wd)} == {want}
    words, zid = CM.cell_grids(act, donors)
    x0, y0, w, h = act.shafts[0].dst
    assert (zid[y0 // 8:(y0 + h) // 8, x0 // 8:(x0 + w) // 8] == act.corridor_key).all()


def test_the_ledge_pitch_bound_is_the_least_jump_rise():
    """Re-derived in CLOSED FORM from the constants (the tool steps frame by frame): the rise
    under a jump force F and gravity g is the sum of F - k g over the n + 1 frames the
    velocity is still upward, n = ceil(F / g) - 1."""
    from fg_working_set import ConstantSource
    src = ConstantSource()
    src.load_file(os.path.join(REPO, "engine", "system", "constants.emp"))
    src.load_file(os.path.join(REPO, "games", "sonic4", "player", "knuckles.emp"))
    g = int(src.get("PHYS_GRAVITY"))
    rises = []
    for name in ("PHYS_JUMP_FORCE", "KNUX_JUMP_FORCE"):
        f = int(src.get(name))
        n = -(-f // g) - 1
        rises.append(((n + 1) * f - g * n * (n + 1) // 2) // 256)
    assert CM.jump_reach_px() == min(rises) and min(rises) < max(rises)


@pytest.mark.parametrize("mutate,tag,needle", [
    (lambda s: s["dst_rect"].update(y=1296, h=272), "K7", "top edge"),
    (lambda s: s["dst_rect"].update(h=272), "K7", "bottom edge"),
    (lambda s: s["dst_rect"].update(x=648), "K9", "block grid"),
    (lambda s: s["lane"].update(x=512), "K9", "inside the rect"),
    (lambda s: s["lane"].update(w=16), "K9", "narrower than a standing player"),
    (lambda s: s.update(ledges={"pitch": 96, "w": 32}), "K9", "no more than 85"),
    (lambda s: s.update(ledges={"pitch": 72, "w": 32}), "K9", "whole number"),
    (lambda s: s.update(ledges={"pitch": 64, "w": 64}), "K9", "narrower than the lane"),
    (lambda s: s.update(look="fog"), "K9", "is not one of"),
    (lambda s: s.update(look="cloud"), "K9", "needs `art`"),
    (lambda s: s.update(art=dict(_cloud_art(), zone="OOZ")), "K5", "no clip of this act"),
])
def test_k7_k9_refuse_a_shaft_by_their_own_tag(donors, tmp_path, mutate, tag, needle):
    _need(S.S2_FINAL)
    doc = _with_shaft(_stacked_doc(), ledges={"pitch": 80, "w": 32})
    CM.load(_write(tmp_path, doc, "ok.json"), donor_root=donors)             # control
    mutate(doc["shafts"][0])
    with pytest.raises(CM.ClipManifestError) as exc:
        CM.load(_write(tmp_path, doc), donor_root=donors)
    assert str(exc.value).startswith(tag + " ") and needle in str(exc.value), str(exc.value)


def test_k10_refuses_a_capped_mouth_and_admits_an_open_one(donors, tmp_path):
    _need(S.S2_FINAL)
    ok = CM.load(_write(tmp_path, _with_shaft(_stacked_doc()), "ok.json"), donor_root=donors)
    CM.collision_grids(ok, donors)                                           # control
    capped = CM.load(_write(tmp_path, _with_shaft(
        _stacked_doc(), dst_rect=_rect(640, 1280, 256, 288), lane={"x": LANE_CAPPED, "w": 32})),
        donor_root=donors)
    with pytest.raises(CM.ClipManifestError) as exc:
        CM.collision_grids(capped, donors)
    assert str(exc.value).startswith("K10 ") and "top mouth is CAPPED" in str(exc.value)


def test_the_fill_goes_around_a_shaft_and_the_bake_counts_it(donors, tmp_path):
    _need(S.S2_FINAL)
    path = _write(tmp_path, _with_fill(_with_shaft(_stacked_doc(),
                                                   ledges={"pitch": 64, "w": 32})))
    act = CM.load(path, donor_root=donors)
    m = CM.fill_mask(act)
    x0, y0, w, h = act.shafts[0].dst
    assert not m[y0 // 8:(y0 + h) // 8, x0 // 8:(x0 + w) // 8].any()
    assert m[y0 // 8:(y0 + h) // 8, :x0 // 8].all()
    summary = CAB.bake(path, out_dir=str(tmp_path / "baked"), donor_root=donors, log=None)[2]
    pool = json.load(open(tmp_path / "baked" / "clipact.json"))["pool"]
    assert [r["id"] for r in pool["per_shaft"]] == ["drop"]
    added = sum(r["tiles_added"] for k in ("per_clip", "per_corridor", "per_shaft", "per_fill")
                for r in pool[k])
    assert added + 1 == pool["tiles"]
    # the ledges' top-only block costs at most ONE attr entry over the same act without
    # ledges (the report's §A.6 "+1 at most"; 0 when a clip already carries a top-only full
    # block, as these two do: MEASURED 88 both ways)
    bare = _write(tmp_path, _with_fill(_with_shaft(_stacked_doc())), "bare.json")
    bare_n = CAB.bake(bare, out_dir=str(tmp_path / "bare"), donor_root=donors,
                      log=None)[2]["collision"]["attr_entries"]
    assert 0 <= summary["collision"]["attr_entries"] - bare_n <= 1
