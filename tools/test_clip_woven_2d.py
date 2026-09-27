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
  * items 1, 3, 4 and 15, THE 2-D PLAN AND ITS CHECKS: a stacked act plans rectangles split
    at the shaft's balanced crossing (derived here from the frames and the camera constants),
    a 1-D act still plans its full-height strips (the committed acts: MEASURED identical row
    for row, and pinned below on s2_mtz_cpz), the crossing moves toward the cheaper side when
    the two sides' frames differ, Z2 and MUSIC walk a shaft on its own axis and every
    connector of a gap, and the SCREEN check (clip_camera) refuses MIXED, WRONG and short
    crossings — each proven able to fail on a mutated plan or layout;
  * item 14, BACKGROUND BLOB GROUPS (`crossing_overrides.background = blobs`, `bg_blobs`):
    BG0 refuses a group list the act cannot honour; the pair frames are the wipe inside a
    group and the group's overwrite across (derived from the lowered tiles); a group holding
    the start zone is the act default (its rows name tile blob 0), any other group is ONE
    blob every member's rows name, embedded once, and BG1 reads it all back;
  * THE END STATE: games/sonic4/data/clips/s2_woven_2d (s2_mtz_cpz's row with Oil Ocean under
    Chemical Plant, a shaft, fill, two blob groups) plans, emits and passes Z2, MUSIC, the
    SCREEN check and BG1 on both axes, its shaft at the slack the rule derives (0);
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
import clip_camera as CC                    # noqa: E402
import clip_manifest as CM                  # noqa: E402
import clip_rom_bake as CRB                 # noqa: E402
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
    """Emerald Hill over Chemical Plant, 320 px apart, one section wide: the smallest act
    with a vertical seam. Positions on the 16-px grid (K8). 320 = CAM_SCREEN_HALF_H x 2 +
    CAM_MAX_Y_STEP x (3 + 3): the bake's Z2 counts a same-blob crossing as the visible-row
    wipe, 3 frames (see test_the_same_blob_vertical_seam_is_320_not_the_reports_288)."""
    return {"schema": 1, "units": "world_px", "id": "t_stacked", "act": {"grid_w": 1, "grid_h": 2},
            "clips": [_clip("ehz", "EHZ", (4096, 0, 1024, 1024), (512, 256)),
                      _clip("cpz", "CPZ", (7168, 0, 1024, 1024), (512, 1600))]}


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
# Plant starts at 1600, 320 px below (the same-blob vertical seam, as the bake times it). The
# shaft's lane is under Emerald Hill act 1's own bottomless pit (donor x 4672..4863, the pit
# clip_reachability's parcel-8 note declares), so a player really falls into it; its last
# collision block row is open from the side and below there, and CAPPED at donor x
# 4960..5007 (MEASURED from the converted tree; the K10 rows re-read it through K10 itself,
# so a donor change fails loudly rather than moving the lane silently).
LANE_OPEN = 1088            # act x of donor 4672: the pit, open
LANE_CAPPED = 1376          # act x of donor 4960: capped
LANE_OPEN_2 = 768           # act x of donor 4352: open at the edge, but no pit above it


def _with_shaft(doc, **kw):
    doc = copy.deepcopy(doc)
    sh = {"id": "drop", "dst_rect": _rect(1024, 1280, 256, 320),
          "lane": {"x": LANE_OPEN, "w": 128}}
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
    assert [(e["y"], e["side"]) for e in ledges] == want and len(want) == 5
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
    (lambda s: s["dst_rect"].update(y=1296, h=304), "K7", "top edge"),
    (lambda s: s["dst_rect"].update(h=304), "K7", "bottom edge"),
    (lambda s: s["dst_rect"].update(x=1032), "K9", "block grid"),
    (lambda s: s["lane"].update(x=512), "K9", "inside the rect"),
    (lambda s: s["lane"].update(w=16), "K9", "narrower than a standing player"),
    (lambda s: s.update(ledges={"pitch": 96, "w": 32}), "K9", "no more than 85"),
    (lambda s: s.update(ledges={"pitch": 72, "w": 32}), "K9", "whole number"),
    (lambda s: s.update(ledges={"pitch": 64, "w": 128}), "K9", "narrower than the lane"),
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
        _stacked_doc(), dst_rect=_rect(1280, 1280, 256, 320), lane={"x": LANE_CAPPED, "w": 32})),
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


# ---------------------------------------------------------------------------
# items 1, 3, 4, 15 — the 2-D region plan and the checks that read it back
# ---------------------------------------------------------------------------

OVERRIDES = {"palette": "snap", "background": "co_resident", "zone_separation": "screen",
             "parallax": "snap", "why": WHY}


def _woven_small(music=False, **shaft):
    """The stacked fixture as a woven act: a drop shaft through the fill, s2_ehz_cpz's
    crossing overrides (EHZ + CPZ backgrounds are co-resident: 376 tiles)."""
    doc = _with_fill(_with_shaft(_stacked_doc(), **shaft))
    doc["crossing_overrides"] = dict(OVERRIDES)
    if music:
        doc["clips"][0]["music"] = "SONG_S2_EHZ"
        doc["clips"][1]["music"] = "SONG_S2_CPZ"
    return doc


def _texts(plan):
    return CRB.clip_module_text(plan), CRB.clip_data_block(plan)


def _need_c(frames, a, b, before, after, axis="y"):
    """The balanced crossing, re-derived from the camera constants and the pair frames."""
    c = CC.constants()
    half = c["CAM_SCREEN_HALF_H"] if axis == "y" else c["CAM_SCREEN_HALF_W"]
    step = c["CAM_MAX_Y_STEP"] if axis == "y" else c["CAM_MAX_X_STEP"]
    nb = half + step * frames["pair"][(after, before)]
    na = half + step * frames["pair"][(before, after)]
    return ((a + b + nb - na) // 2) // 16 * 16, nb, na


def _descriptor_rules(rows, W, H):
    """act_descriptor.emp's row rules (ojz_region_table_check), re-derived from the camera
    constants: every row at least REGION_MIN_SPAN (2 x CAM_MAX_Y_STEP) on both axes, every
    interior edge inside the camera centre's band, and the rows tiling the act exactly."""
    c = CC.constants()
    span = 2 * c["CAM_MAX_Y_STEP"]
    hw, hh = c["CAM_SCREEN_HALF_W"], c["CAM_SCREEN_HALF_H"]
    cover = np.zeros((H // 8, W // 8), dtype=np.int32)
    for r in rows:
        assert r["x1"] - r["x0"] + 1 >= span and r["y1"] - r["y0"] + 1 >= span, r
        assert r["x0"] == 0 or (r["x0"] - 1 >= hw and r["x0"] <= W - hw), r
        assert r["x1"] == W - 1 or (r["x1"] >= hw and r["x1"] + 1 <= W - hw), r
        assert r["y0"] == 0 or (r["y0"] - 1 >= hh and r["y0"] <= H - hh), r
        assert r["y1"] == H - 1 or (r["y1"] >= hh and r["y1"] + 1 <= H - hh), r
        cover[r["y0"] // 8:(r["y1"] + 1) // 8, r["x0"] // 8:(r["x1"] + 1) // 8] += 1
    assert (cover == 1).all()


def test_the_camera_models_components_are_a_bfs_s():
    """clip_camera.components (row runs + union-find) against a plain cell BFS."""
    from collections import deque
    rng = np.random.default_rng(7)
    for _ in range(20):
        m = rng.random((33, 47)) < rng.uniform(0.3, 0.7)
        lab, n = CC.components(m)
        ref, k = np.zeros(m.shape, dtype=np.int32), 0
        for y0, x0 in zip(*np.nonzero(m)):
            if ref[y0, x0]:
                continue
            k += 1
            ref[y0, x0] = k
            q = deque([(y0, x0)])
            while q:
                y, x = q.popleft()
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= yy < 33 and 0 <= xx < 47 and m[yy, xx] and not ref[yy, xx]:
                        ref[yy, xx] = k
                        q.append((yy, xx))
        assert n == k
        pairs = set(zip(lab[m].tolist(), ref[m].tolist()))
        assert len(pairs) == k                  # one-to-one: the same partition


def test_a_stacked_act_plans_two_rectangles_split_at_the_shafts_crossing(donors, tmp_path):
    _need(S.S2_FINAL)
    act = CM.load(_write(tmp_path, _woven_small()), donor_root=donors)
    plan = CRB.region_plan(act, donors)
    ehz, cpz = act.clips
    a, b = ehz.dst[1] + ehz.dst[3], cpz.dst[1]
    c, _nb, _na = _need_c(plan["frames"], a, b, ehz.zone_key, cpz.zone_key)
    W, H = act.grid_w * act.section_px, act.grid_h * act.section_px
    assert [(r["x0"], r["x1"], r["y0"], r["y1"], r["key"]) for r in plan["rows"]] == [
        (0, W - 1, 0, c - 1, ehz.zone_key), (0, W - 1, c, H - 1, cpz.zone_key)]
    _descriptor_rules(plan["rows"], W, H)
    assert plan["crossings"] == [{"connector": "drop", "axis": "y", "at": c, "y": c,
                                  "shaft": "drop", "from_key": 0, "to_key": 1, "gap": [a, b],
                                  "need": list(_need_c(plan["frames"], a, b, 0, 1)[1:])}]
    # Z2 walks the SHAFT in y, at every 16 px across its rectangle
    z2 = CRB.check_palette_crossings(act, *_texts(plan), frames=plan["frames"])
    assert len(z2) == 1 and z2[0]["axis"] == "y" and z2[0]["y"] == c
    assert z2[0]["xs_walked"] == act.shafts[0].dst[2] // 16
    assert z2[0]["margin_top"] >= z2[0]["margin_needed_top"]
    assert z2[0]["margin_bottom"] >= z2[0]["margin_needed_bottom"]
    # the screen check over the emitted rows: nothing mixed, nothing wrong, no short crossing
    model = CC.CameraModel.for_act(act, donors)
    scr = CRB.check_screen(act, model, *_texts(plan), plan["frames"])
    assert scr["mixed"] == scr["wrong"] == 0 and scr["void"] == 0
    assert scr["crossings"] and all(t["slack"] >= 0 for t in scr["crossings"])
    assert {t["axis"] for t in scr["crossings"]} == {"y"}


def test_the_same_blob_vertical_seam_is_320_not_the_reports_288(donors, tmp_path):
    """FINDING (2026-09-27): the report's woven layout cut its same-blob connectors with a
    2-frame background repaint (288 up/down, 384 across); the bake's Z2 counts the visible-row
    wipe as ceil(BG_SCREEN_ROWS / BG_WIPE_DMA_ROWS) frames, which is 3 (a slipped DMA allowed
    for, as s2_ehz_cpz's own why says). So a same-blob seam needs 2 x (HALF + 3 x STEP): 320
    in y and 416 in x. At 288 the bake refuses the shaft — derived here from the engine."""
    _need(S.S2_FINAL)
    chunk, rows_per_frame, screen_rows = CRB.background_constants()
    wipe = -(-screen_rows // rows_per_frame)
    c = CC.constants()
    assert wipe == 3
    assert 2 * (c["CAM_SCREEN_HALF_H"] + wipe * c["CAM_MAX_Y_STEP"]) == 320
    assert 2 * (c["CAM_SCREEN_HALF_W"] + wipe * c["CAM_MAX_X_STEP"]) == 416
    doc = _woven_small()
    for cl in doc["clips"][1:]:
        cl["dst_rect"]["y"] -= 32
    doc["shafts"][0]["dst_rect"]["h"] = 288
    doc["fill"]["rect"]["h"] = 4096
    act = CM.load(_write(tmp_path, doc), donor_root=donors)
    with pytest.raises(CRB.ClipRomError) as exc:
        plan = CRB.region_plan(act, donors)
        CRB.check_palette_crossings(act, *_texts(plan), frames=plan["frames"])
    assert "Z2" in str(exc.value) and "CAM_SCREEN_HALF_H" in str(exc.value)


def test_the_crossing_moves_toward_the_cheaper_side(donors, tmp_path):
    """The balanced rule: equal frames put it mid-connector (the old rule exactly); more
    frames into the TOP zone push it DOWN (more room above)."""
    _need(S.S2_FINAL)
    act = CM.load(_write(tmp_path, _woven_small()), donor_root=donors)
    base = CRB.crossing_frames(act)
    a, b = 1280, 1600
    assert CRB.region_plan(act, donors, frames=base)["crossings"][0]["at"] == \
        ((a + b) // 2) // 16 * 16
    skew = dict(base, pair={(1, 0): 6, (0, 1): 3})
    got = CRB.region_plan(act, donors, frames=skew)["crossings"][0]["at"]
    want, nb, na = _need_c(skew, a, b, 0, 1)
    assert got == want and got > (a + b) // 2 and nb > na


def test_a_one_row_act_still_plans_full_height_strips(donors, tmp_path):
    """The 2-D plan's special case: s2_mtz_cpz (MTZ | tunnel | CPZ | tunnel | MTZ) plans the
    five full-height strips the 1-D plan did, crossings at each tunnel's middle rounded down
    to 16, CPZ's strip split at the tunnel mouths for its song."""
    _need(S.S2_FINAL)
    path = os.path.join(REPO, "games", "sonic4", "data", "clips", "s2_mtz_cpz", "clips.json")
    act = CM.load(path, donor_root=donors)
    plan = CRB.region_plan(act, donors)
    mw, cpz, me = sorted(act.clips, key=lambda c: c.dst[0])
    c1 = ((mw.dst[0] + mw.dst[2] + cpz.dst[0]) // 2) // 16 * 16
    c2 = ((cpz.dst[0] + cpz.dst[2] + me.dst[0]) // 2) // 16 * 16
    W, H = act.grid_w * act.section_px, act.grid_h * act.section_px
    _descriptor_rules(plan["rows"], W, H)
    assert [(r["x0"], r["x1"], r["y0"], r["y1"], r["key"], r["song"]) for r in plan["rows"]] == [
        (0, c1 - 1, 0, H - 1, 0, None),
        (c1, cpz.dst[0] - 1, 0, H - 1, 1, None),
        (cpz.dst[0], cpz.dst[0] + cpz.dst[2] - 1, 0, H - 1, 1, "SONG_S2_CPZ"),
        (cpz.dst[0] + cpz.dst[2], c2 - 1, 0, H - 1, 1, None),
        (c2, W - 1, 0, H - 1, 0, None)]


def test_music_on_a_shaft_changes_at_its_mouths(donors, tmp_path):
    _need(S.S2_FINAL)
    act = CM.load(_write(tmp_path, _woven_small(music=True)), donor_root=donors)
    plan = CRB.region_plan(act, donors)
    ehz, cpz = act.clips
    a, b = ehz.dst[1] + ehz.dst[3], cpz.dst[1]
    c = plan["crossings"][0]["at"]
    H = act.grid_h * act.section_px
    assert [(r["y0"], r["y1"], r["key"], r["song"]) for r in plan["rows"]] == [
        (0, a - 1, 0, "SONG_S2_EHZ"), (a, c - 1, 0, None), (c, b - 1, 1, None),
        (b, H - 1, 1, "SONG_S2_CPZ")]
    out = CRB.check_music_crossings(act, *_texts(plan))
    assert out == [{"from": "ehz", "to": "cpz", "axis": "y", "connector": "drop",
                    "down_y": b, "up_y": a - 1, "dead_band_px": b - a,
                    "songs": ["SONG_S2_EHZ", "SONG_S2_CPZ"]}]
    # CAN IT FAIL: the unsplit rows (each zone's song on its whole region) change the song
    # at the crossing, not at the mouth
    merged = [dict(plan["rows"][0], y1=c - 1), dict(plan["rows"][3], y0=c)]
    with pytest.raises(CRB.ClipRomError, match=r"walking down the song changes at \[\(%d," % c):
        CRB.check_music_crossings(act, *_texts(dict(plan, rows=merged)))


def test_z2_walks_every_connector_of_a_gap_not_the_first(donors, tmp_path):
    """§C item 4: two shafts between the same two zones; a row plan that is right at the
    first and wrong at the second is refused (the old walk read `corr[0]` only)."""
    _need(S.S2_FINAL)
    doc = _woven_small()
    second = copy.deepcopy(doc["shafts"][0])
    second.update(id="drop_two", dst_rect=_rect(LANE_OPEN_2, 1280, 64, 320),
                  lane={"x": LANE_OPEN_2, "w": 64})
    doc["shafts"].append(second)
    act = CM.load(_write(tmp_path, doc), donor_root=donors)
    plan = CRB.region_plan(act, donors)
    z2 = CRB.check_palette_crossings(act, *_texts(plan), frames=plan["frames"])
    assert [r["connector"] for r in z2] == ["drop", "drop_two"]
    c = plan["crossings"][0]["at"]
    W, H = act.grid_w * act.section_px, act.grid_h * act.section_px
    # a hand plan: right at the first shaft (x >= 1024), 64 px too high at the second
    bad = [dict(plan["rows"][0], x0=0, x1=1023, y0=0, y1=c - 65),
           dict(plan["rows"][1], x0=0, x1=1023, y0=c - 64, y1=H - 1),
           dict(plan["rows"][0], x0=1024, x1=W - 1, y0=0, y1=c - 1),
           dict(plan["rows"][1], x0=1024, x1=W - 1, y0=c, y1=H - 1)]
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_palette_crossings(act, *_texts(dict(plan, rows=bad)), frames=plan["frames"])
    assert "Z2" in str(exc.value) and "drop_two" in str(exc.value)


def test_the_screen_check_refuses_wrong_and_short_rows(donors, tmp_path):
    _need(S.S2_FINAL)
    act = CM.load(_write(tmp_path, _woven_small()), donor_root=donors)
    plan = CRB.region_plan(act, donors)
    model = CC.CameraModel.for_act(act, donors)
    CRB.check_screen(act, model, *_texts(plan), plan["frames"])              # control
    c = plan["crossings"][0]["at"]
    ehz = act.clips[0]
    # the boundary 16 px up: the entered (top) zone is 16 px nearer than its frames need
    up = [dict(plan["rows"][0], y1=c - 17), dict(plan["rows"][1], y0=c - 16)]
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_screen(act, model, *_texts(dict(plan, rows=up)), plan["frames"])
    assert "Z2 (screen" in str(exc.value) and "slack -16 px" in str(exc.value)
    # the boundary INSIDE Emerald Hill: its bottom rows are shown under CPZ's region
    inside = [dict(plan["rows"][0], y1=ehz.dst[1] + ehz.dst[3] - 65),
              dict(plan["rows"][1], y0=ehz.dst[1] + ehz.dst[3] - 64)]
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_screen(act, model, *_texts(dict(plan, rows=inside)), plan["frames"])
    assert "Z2 (screen" in str(exc.value) and "ANOTHER zone's region" in str(exc.value)


def test_z1_on_the_screen_refuses_stacked_zones_a_camera_sees_together(donors, tmp_path):
    """Both axes: Chemical Plant 64 px under Emerald Hill with only fill between is a
    SEALED seam, and Emerald Hill's pit runs to its bottom edge: a player stands on the fill
    at the pit's foot and his camera sees both zones (MIXED), so Z1 refuses it. The control
    is the 320-px shaft act."""
    _need(S.S2_FINAL)
    ok = CM.load(_write(tmp_path, _woven_small(), "ok.json"), donor_root=donors)
    z = CRB.check_zone_separation(ok, {"zone_separation": {
        "mixed": 1, "windows": 1, "min_column_gap_cells": -128, "window_cells": [80, 60],
        "first_mixed": None}}, model=CC.CameraModel.for_act(ok, donors))
    assert z["axes"] == "both" and z["mixed_reachable"] == 0
    doc = _with_fill(_stacked_doc())
    doc["clips"][1]["dst_rect"]["y"] = 1280 + 64
    doc["crossing_overrides"] = dict(OVERRIDES)
    act = CM.load(_write(tmp_path, doc), donor_root=donors)
    model = CC.CameraModel.for_act(act, donors)
    assert int(model.mixed().sum()) > 0
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_zone_separation(act, {"zone_separation": {
            "mixed": 1, "windows": 1, "min_column_gap_cells": -128,
            "window_cells": [80, 60], "first_mixed": None}}, model=model)
    assert "Z1" in str(exc.value) and "both axes" in str(exc.value)


def test_zones_facing_across_void_are_refused_and_fill_seals_them(donors, tmp_path):
    _need(S.S2_FINAL)
    bare = CM.load(_write(tmp_path, _stacked_doc(), "bare.json"), donor_root=donors)
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_zone_faces(bare)
    assert "Z2" in str(exc.value) and "void in the 320 px" in str(exc.value)
    CRB.check_zone_faces(CM.load(_write(tmp_path, _with_fill(_stacked_doc()), "f.json"),
                                 donor_root=donors))                        # sealed: fine
    CRB.check_zone_faces(CM.load(_write(tmp_path, _with_shaft(_stacked_doc()), "s.json"),
                                 donor_root=donors))                        # joined: fine
    butted = _stacked_doc()
    butted["clips"][1]["dst_rect"]["y"] = 1280
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_zone_faces(CM.load(_write(tmp_path, butted), donor_root=donors))
    assert "butted" in str(exc.value) and "along y" in str(exc.value)


# ---------------------------------------------------------------------------
# item 14 — background blob groups, and the end state: s2_woven_2d
# ---------------------------------------------------------------------------

WOVEN = os.path.join(REPO, "games", "sonic4", "data", "clips", "s2_woven_2d", "clips.json")
DESCRIPTOR = os.path.join(REPO, "games", "sonic4", "data", "levels", "ojz", "act1",
                          "act_descriptor.emp")


def _woven_doc(**ov):
    doc = json.load(open(WOVEN))
    doc["crossing_overrides"].update(ov)
    return doc


@pytest.mark.parametrize("ov,needle", [
    ({"bg_blobs": [["CPZ", "MTZ"]]}, "leaves ['s2disasm/OOZ'] in no group"),
    ({"bg_blobs": [["CPZ", "MTZ"], ["OOZ", "CPZ"]]}, "a zone's tiles are in ONE blob"),
    ({"bg_blobs": [["CPZ", "MTZ"], ["HPZ", "OOZ"]]}, "no zone of this act"),
    ({"bg_blobs": [["CPZ", "MTZ"], []]}, "non-empty lists"),
])
def test_bg0_refuses_groups_the_act_cannot_honour(donors, tmp_path, ov, needle):
    _need(S.S2_FINAL)
    CRB.blob_groups(CM.load(WOVEN, donor_root=donors))                       # control
    act = CM.load(_write(tmp_path, _woven_doc(**ov)), donor_root=donors)
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.blob_groups(act)
    assert str(exc.value).startswith("BG0 ") and needle in str(exc.value), str(exc.value)


def test_blobs_and_bg_blobs_go_together(donors, tmp_path):
    _need(S.S2_FINAL)
    doc = _woven_doc()
    doc["crossing_overrides"].pop("bg_blobs")
    with pytest.raises(CRB.ClipRomError, match="go together"):
        CRB.crossing_overrides(CM.load(_write(tmp_path, doc, "a.json"), donor_root=donors))
    doc = _woven_doc(background="co_resident")
    with pytest.raises(CRB.ClipRomError, match="go together"):
        CRB.crossing_overrides(CM.load(_write(tmp_path, doc, "b.json"), donor_root=donors))


def test_pair_frames_are_the_wipe_inside_a_group_and_the_overwrite_across(donors):
    """Derived from the engine's constants and each zone's lowered tiles: into a zone of the
    SAME group only the wipe; into another group its blob's chunks + the wipe; never below
    the palette's frames."""
    _need(S.S2_FINAL)
    import clip_bg_lower as CBL
    act = CM.load(WOVEN, donor_root=donors)
    f = CRB.crossing_frames(act)
    chunk, rows_per_frame, screen_rows = CRB.background_constants()
    wipe = -(-screen_rows // rows_per_frame)
    tiles = {c.zone_key: CBL.lower(c.donor, c.zone)[1] for c in act.clips}
    mtz, cpz, ooz = 0, 1, 2
    m_union = len(set(tiles[mtz]) | set(tiles[cpz]))
    assert f["pair"][(mtz, cpz)] == f["pair"][(cpz, mtz)] == max(f["palette"], wipe)
    assert f["pair"][(ooz, cpz)] == -(-m_union * 32 // chunk) + wipe
    assert f["pair"][(cpz, ooz)] == -(-len(tiles[ooz]) * 32 // chunk) + wipe
    # the report's M-to-O shaft length, re-derived: HALF_H x 2 + STEP_Y x (both sides)
    c = CC.constants()
    assert 2 * c["CAM_SCREEN_HALF_H"] + c["CAM_MAX_Y_STEP"] * (
        f["pair"][(ooz, cpz)] + f["pair"][(cpz, ooz)]) == act.shafts[0].dst[3] == 464


def _woven_emitted(donors, tmp_path, doc=None):
    act = CM.load(WOVEN if doc is None else _write(tmp_path, doc), donor_root=donors)
    gen = tmp_path / "gen"
    gen.mkdir()
    data = tmp_path / "entity_data.emp"
    data.write_text(open(CRB.CLIP_DATA).read())
    z2, plan = CRB.emit_clip_module(act, donors, path=str(tmp_path / "clip_act.emp"),
                                    data_path=str(data), gen_dir=str(gen),
                                    baked_dir=str(tmp_path), log=None)
    return act, z2, plan, (tmp_path / "clip_act.emp").read_text(), data.read_text(), str(gen)


def test_the_woven_2d_act_passes_every_check_on_both_axes(donors, tmp_path):
    """THE END STATE this parcel ships: the committed 2-D woven manifest plans and emits,
    and Z2, MUSIC, the SCREEN check, BG1, SC1 and LL1 (all run by emit_clip_module over what
    it WROTE) pass. The shaft is at slack 0 — the length the rule derives, no longer."""
    _need(S.S2_FINAL)
    act, z2, plan, mod, data, gen = _woven_emitted(donors, tmp_path)
    assert {(r["connector"], r["axis"]) for r in z2} == {
        ("mtz_to_cpz", "x"), ("cpz_to_mtz", "x"), ("cpz_to_ooz", "y")}
    assert {(m["connector"], m["axis"]) for m in plan["music"]} == {
        ("mtz_to_cpz", "x"), ("cpz_to_mtz", "x"), ("cpz_to_ooz", "y")}
    scr = plan["screen"]
    assert scr["mixed"] == scr["wrong"] == scr["void"] == 0
    slack = {(t["from_key"], t["into_key"]): t["slack"] for t in scr["crossings"]}
    assert slack[(1, 2)] == slack[(2, 1)] == 0 and min(slack.values()) >= 0
    W = H = 3 * act.section_px
    _descriptor_rules(plan["rows"], W, H)
    # the blob groups, read out of the rows: MTZ (the start) and CPZ draw from the act
    # default's blob (tiles 0); OOZ names its own
    by_key = {}
    for r in plan["rows"]:
        by_key.setdefault(r["key"], set()).add((r.get("bg_layout"), r.get("bg_tiles")))
    assert by_key[0] == {(None, None)}
    assert by_key[1] == {("OJZ_Clip_BG_Layout_1", None)}
    assert by_key[2] == {("OJZ_Clip_BG_Layout_2", "OJZ_Clip_BG_Tiles_2")}
    assert plan["bg1"]["default"] == "MTZ"


def test_a_group_without_the_start_zone_is_one_blob_every_member_names(donors, tmp_path):
    """bg_blobs [[MTZ], [CPZ, OOZ]]: CPZ + OOZ share ONE blob (owned by the lower zone key,
    embedded once), both zones' rows name it, BG1 reads it back as their union."""
    _need(S.S2_FINAL)
    import clip_bg_lower as CBL
    act = CM.load(_write(tmp_path, _woven_doc(bg_blobs=[["MTZ"], ["CPZ", "OOZ"]])),
                  donor_root=donors)
    plan = CRB.region_plan(act, donors)
    gen = tmp_path / "gen"
    gen.mkdir()
    CRB.plan_backgrounds(plan, CRB.engine_spawn(DESCRIPTOR, start=CRB.act_start(act)),
                         str(gen), str(tmp_path), log=None)
    zones = {z["key"]: z for z in plan["zones"]}
    assert zones[1]["bg_tiles_label"] == zones[2]["bg_tiles_label"] == "OJZ_Clip_BG_Tiles_1"
    assert zones[1]["bg_tiles_owner"] and not zones[2]["bg_tiles_owner"]
    data = CRB.clip_data_block(plan)
    assert data.count("pub data OJZ_Clip_BG_Tiles_1 ") == 1
    assert "OJZ_Clip_BG_Tiles_2" not in data
    union = len(set(CBL.lower("s2disasm", "CPZ")[1]) | set(CBL.lower("s2disasm", "OOZ")[1]))
    assert zones[1]["bg_tile_bytes_effective"] == zones[2]["bg_tile_bytes_effective"] \
        == union * 32
    CRB.check_backgrounds(plan, CRB.clip_module_text(plan), data, str(gen))
    # CAN IT FAIL: the group blob on disk replaced by CPZ's own tiles alone
    (gen / CRB.CLIP_BG_TILES_BIN.format(key=1)).write_bytes(
        CBL.tiles_blob(CBL.lower("s2disasm", "CPZ")[1]))
    with pytest.raises(CRB.ClipRomError, match="BG1"):
        CRB.check_backgrounds(plan, CRB.clip_module_text(plan), data, str(gen))
