"""A ONE-PATH zone in a clip act (woven first screen, s2_mtz_cpz, 2026-09-27; the rule re-keyed
by WOVEN-WFZ-PLANE-B, 2026-09-27).

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Rows
that need a donor convert their own into pytest's tmp tree and SKIP SAYING SO when the donor
checkout cannot be resolved (the tools/test_clip_two_zone.py pattern).

WHAT A ONE-PATH ZONE IS. A zone in which Sonic 2 never puts the player on collision path B:
its act-1 object layout carries no plane switcher (Obj03) that can select path B, and every
act starts on path A. MEASURED 2026-09-27 on the final game's layouts (B-selecting Obj03 /
all Obj03): EHZ 17/19, CPZ 34/60, ARZ 16/30, CNZ 6/6, HTZ 17/18, SCZ 1/1; MCZ, OOZ, MTZ, WFZ
0/0; the prototype's Hidden Palace 0 Obj03 of 43 records.

WHY IT MATTERS HERE. In a clip act the player can ARRIVE in a one-path zone on plane B:
Chemical Plant's and Emerald Hill's own Obj03 lines put him there, and nothing in the one-path
zone puts him back. Metropolis's donor plane B carries no solidity at all (MEASURED: 0
plane-B solid words), so there he fell forever: 384 floorless plane-B columns on the first
bake of s2_mtz_cpz. Wing Fortress's donor plane B DOES carry solidity, but not Sonic 2's decks
(the owner's sighting, woven (5133, 1389) on layer 1: plane A has floors at y 320, 512, 640,
1152 and 1280 there, plane B only 512), so a plane-B player fell through the ship.

THE RULE (`clip_manifest.zone_path_b_switchers`, `_clip_collision`): a clip whose ZONE's
Sonic 2 object layout has no plane switcher that can select path B is pasted with its plane A
on BOTH planes. A player on either path then stands on the one path Sonic 2 gives him there.
It used to be keyed on "the converted tree has plane-B solidity anywhere", which is not
Sonic 2's criterion: it gave the right answer for Metropolis and the wrong one for Wing
Fortress. The test is the ZONE's layout, not the clip's crop: a zone that selects path B
anywhere keeps its own plane B, even where its crop is empty on B, and K6 then holds its
seams to both planes exactly as before.

WHAT IS PINNED:
  * zone_path_b_switchers agrees with a direct count of the donor's own object layout, and
    the per-zone measurement above holds;
  * the act's collision carries each one-path clip's plane A on plane B, cell for cell, and
    Chemical Plant's own plane B untouched;
  * Wing Fortress (s2_wfz_solo and the woven act): plane B is plane A under every WFZ clip,
    and the owner's sighting column carries the 1152 and 1280 decks on plane B (RED before
    the re-key: plane B had only 512 in the ship);
  * the real act's two tunnels bake at Metropolis's edges on both planes;
  * THE CONTROL THAT NOTHING WAS LOOSENED: Metropolis with ONE B-selecting plane switcher
    added to its layout (far from the seam) is a two-path zone, so it is NOT mirrored and K6
    refuses the seam with "disagree"; and a plane-B solid word planted in Metropolis's tree
    no longer changes anything (the retired criterion);
  * Chemical Plant, which selects path B, is still read on both planes at its own seams.
"""

import json
import os
import shutil
import sys

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_manifest as CM                  # noqa: E402
import collision_pipeline as CP             # noqa: E402
import s2_donor as S                        # noqa: E402
import s2_zone_convert as C                 # noqa: E402
from suite_paths import SuitePathError      # noqa: E402

REPO = os.path.dirname(TOOLS)
MANIFEST = os.path.join(REPO, "games", "sonic4", "data", "clips", "s2_mtz_cpz", "clips.json")
CLIPS = os.path.join(REPO, "games", "sonic4", "data", "clips")
WFZ_SOLO = os.path.join(CLIPS, "s2_wfz_solo", "clips.json")
WOVEN = os.path.join(CLIPS, "s2_woven", "clips.json")
CASES = [(S.S2_FINAL, "MTZ"), (S.S2_FINAL, "CPZ"), (S.S2_FINAL, "EHZ"), (S.S2_FINAL, "OOZ"),
         (S.S2_FINAL, "WFZ"), (S.S2_PROTOTYPE, "HPZ")]
#: (donor, zone) -> (B-selecting Obj03, all Obj03) in the act-1 object layout, MEASURED
#: 2026-09-27 (module header). The rule's input, pinned so a donor change is seen.
LAYOUT_SWITCHERS = {(S.S2_FINAL, "EHZ"): (17, 19), (S.S2_FINAL, "CPZ"): (34, 60),
                    (S.S2_FINAL, "MTZ"): (0, 0), (S.S2_FINAL, "OOZ"): (0, 0),
                    (S.S2_FINAL, "WFZ"): (0, 0), (S.S2_PROTOTYPE, "HPZ"): (0, 0)}


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
    root = str(tmp_path_factory.mktemp("s2onepath"))
    for donor, zone in CASES:
        try:
            S.donor_root(donor)
        except (SystemExit, SuitePathError):
            continue
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    return root


def _plane_b_solid_words(tree):
    """Plane-B words with any solidity bit, counted straight off the files (the retired
    criterion's input: it no longer decides anything, the rows below show why)."""
    n = 0
    for f in sorted(os.listdir(tree)):
        if f.endswith(".collattrb.bin"):
            data = open(os.path.join(tree, f), "rb").read()
            for i in range(0, len(data), 2):
                w = (data[i] << 8) | data[i + 1]
                n += bool((w >> CP.PLANE_SOL_SHIFT) & CP.SOL_ALL)
    return n


def _tree_planes(cl, root, act):
    zm = json.load(open(os.path.join(cl.tree_dir(root), "zone.json")))
    return [CM.section_plane_grid(cl.tree_dir(root), zm, act.section_tiles, s)
            for s in ("collattr", "collattrb")]


def _layout_obj03(donor, zone):
    """(B-selecting, all) Obj03 records in the zone's act-1 object layout, counted straight off
    the donor's files with s2_layer_lines' readers (the reference the rule is held to). A
    final-game record selects path B when it is not x-flipped (LL_KEEP_PATH) and its subtype
    has bit 3 or 4; the prototype's subtype is not read, so every Obj03 counts there."""
    import s2_layer_lines as SLL
    asm = SLL._s2_asm(donor)
    oid = SLL.obj03_id(asm, donor)
    recs = [r for r in SLL.read_layout(SLL.object_layout_path(asm, donor, zone), donor)
            if r[3] == oid]
    if donor != S.S2_FINAL:
        return len(recs), len(recs)
    return sum(1 for r in recs if not r[2] and r[4] & 0x18), len(recs)


def test_zone_path_b_switchers_is_the_layouts_own_count(donors):
    _need(S.S2_FINAL)
    _need(S.S2_PROTOTYPE)
    act = CM.load(WOVEN, donor_root=donors)
    by_zone = {(cl.donor, cl.zone): cl for cl in act.clips}
    assert set(by_zone) == set(LAYOUT_SWITCHERS)
    for key, want in LAYOUT_SWITCHERS.items():
        assert _layout_obj03(*key) == want, key
        assert CM.zone_path_b_switchers(by_zone[key]) == want[0], key
    # the premise the old criterion rested on, and why it was the wrong question for WFZ:
    # Metropolis has no plane-B solidity, Wing Fortress DOES, and neither selects path B
    assert _plane_b_solid_words(os.path.join(donors, S.S2_FINAL, "MTZ")) == 0
    assert _plane_b_solid_words(os.path.join(donors, S.S2_FINAL, "WFZ")) > 0
    assert _plane_b_solid_words(os.path.join(donors, S.S2_FINAL, "CPZ")) > 0


def test_a_one_path_zone_is_pasted_with_its_plane_a_on_both_planes(donors):
    """Red before the rule: the act's plane B under every Metropolis clip was the donor's
    solidity-free plane B, so a plane-B player fell through all of Metropolis."""
    _need(S.S2_FINAL)
    act = CM.load(MANIFEST, donor_root=donors)
    pa, pb = CM._clip_collision(act, donors)
    seen = set()
    for cl in act.clips:
        ta, tb = _tree_planes(cl, donors, act)
        sx, sy, sw, sh = (v // CM.TILE_PX for v in cl.src)
        dx, dy = cl.dst[0] // CM.TILE_PX, cl.dst[1] // CM.TILE_PX
        got_a = pa[dy:dy + sh, dx:dx + sw]
        got_b = pb[dy:dy + sh, dx:dx + sw]
        assert (got_a == ta[sy:sy + sh, sx:sx + sw]).all(), cl.id
        want_b = ta if CM.zone_path_b_switchers(cl) == 0 else tb
        assert (got_b == want_b[sy:sy + sh, sx:sx + sw]).all(), cl.id
        seen.add(cl.zone)
    assert seen == {"MTZ", "CPZ"}
    # and the mirror is not vacuous: CPZ's own planes differ inside its crop
    cpz = next(cl for cl in act.clips if cl.zone == "CPZ")
    ta, tb = _tree_planes(cpz, donors, act)
    sx, sy, sw, sh = (v // CM.TILE_PX for v in cpz.src)
    assert (ta[sy:sy + sh, sx:sx + sw] != tb[sy:sy + sh, sx:sx + sw]).any()


def test_the_real_acts_tunnels_meet_metropolis_on_both_planes(donors):
    """Before either fix this raised `K6 ... two collision planes disagree at x=1535 ...
    (heights 16 and 0)` on the draft geometry. Each corridor's Metropolis end is now measured
    on both planes, and both carry plane A's floor there."""
    _need(S.S2_FINAL)
    act = CM.load(MANIFEST, donor_root=donors)
    CM.collision_grids(act, donors)
    planes = CM._clip_collision(act, donors)
    hm, _an = CM._bank(CM.collision_banks(act, donors))
    n = CP.PROFILE_LEN
    seen_mtz = 0
    for co in act.corridors:
        _words, ramps = CM.corridor_collision(act, co, donors)
        for side, x in (("left", co.dst[0] - 1), ("right", co.dst[0] + co.dst[2])):
            cl = CM._clip_at(act, x, co.floor_y)
            assert cl is not None, (co.id, side)
            hs = []
            for p in planes:
                h = CM._word_heights(int(p[co.floor_y // 8, x // 8]), hm)
                hs.append(h[x % n] if h is not None else 0)
            assert hs[0] == hs[1], (co.id, side, hs)
            if ramps[side] is None:
                assert hs[0] == n, (co.id, side, hs)
            else:
                assert ramps[side]["neighbour_surface_y"] == co.floor_y + n - hs[0], (co.id, side)
            seen_mtz += cl.zone == "MTZ"
    assert seen_mtz == 2, "both tunnels have a Metropolis end"


def _with_extra_obj03(monkeypatch, donor, zone, rec):
    """Make s2_layer_lines.read_layout return `rec` (x, y, xflip, subtype) as one more Obj03
    record appended to `zone`'s act-1 layout, and nothing else changed."""
    import s2_layer_lines as SLL
    asm = SLL._s2_asm(donor)
    path = SLL.object_layout_path(asm, donor, zone)
    oid = SLL.obj03_id(asm, donor)
    real = SLL.read_layout

    def fake(p, d=S.S2_FINAL):
        out = real(p, d)
        return out + [(*rec[:3], oid, rec[3])] if p == path else out
    monkeypatch.setattr(SLL, "read_layout", fake)


def test_a_zone_that_selects_path_b_is_not_mirrored(donors, monkeypatch):
    """THE CONTROL. The same act with ONE path-B-selecting Obj03 added to Metropolis's layout,
    far from either seam (subtype $08: crossing right selects B). That zone is two-path, so it
    keeps its own (solidity-free) plane B at the seam and K6 refuses it exactly as before the
    one-path rule."""
    _need(S.S2_FINAL)
    _with_extra_obj03(monkeypatch, S.S2_FINAL, "MTZ", (16, 16, 0, 0x08))
    act = CM.load(MANIFEST, donor_root=donors)
    assert all(CM.zone_path_b_switchers(cl) == 1 for cl in act.clips if cl.zone == "MTZ")
    with pytest.raises(CM.ClipManifestError) as exc:
        CM.collision_grids(act, donors)
    msg = str(exc.value)
    assert msg.split()[0] == "K6" and "disagree" in msg, msg[:200]


def test_a_keep_path_switcher_does_not_make_a_zone_two_path(donors, monkeypatch):
    """An x-flipped Obj03 (LL_KEEP_PATH: priority only) never selects path B, so it leaves
    Metropolis one-path and the act bakes."""
    _need(S.S2_FINAL)
    _with_extra_obj03(monkeypatch, S.S2_FINAL, "MTZ", (16, 16, 1, 0x18))
    act = CM.load(MANIFEST, donor_root=donors)
    assert all(CM.zone_path_b_switchers(cl) == 0 for cl in act.clips if cl.zone == "MTZ")
    CM.collision_grids(act, donors)


def test_plane_b_solidity_alone_no_longer_decides(donors, tmp_path):
    """The RETIRED criterion. Metropolis's tree with ONE plane-B solid word planted in its last
    section (nowhere near either seam) used to make it a two-path zone and K6 refused the seam.
    Its layout still selects no path B, so it is still mirrored and the act bakes."""
    _need(S.S2_FINAL)
    root = str(tmp_path / "donors")
    shutil.copytree(donors, root)
    tree = os.path.join(root, S.S2_FINAL, "MTZ")
    zm = json.load(open(os.path.join(tree, "zone.json")))
    last = zm["grid"]["w"] * zm["grid"]["h"] - 1
    p = os.path.join(tree, f"section_{last}.collattrb.bin")
    data = bytearray(open(p, "rb").read())
    w = (data[-2] << 8) | data[-1]
    w |= CP.SOL_TOP << CP.PLANE_SOL_SHIFT
    data[-2:] = bytes(((w >> 8) & 0xFF, w & 0xFF))
    open(p, "wb").write(bytes(data))
    assert _plane_b_solid_words(tree) == 1
    act = CM.load(MANIFEST, donor_root=root)
    CM.collision_grids(act, root)
    pa, pb = CM._clip_collision(act, root)
    for cl in act.clips:
        if cl.zone == "MTZ":
            dx, dy, dw, dh = (v // CM.TILE_PX for v in cl.dst)
            assert (pb[dy:dy + dh, dx:dx + dw] == pa[dy:dy + dh, dx:dx + dw]).all(), cl.id


def _top_rows(plane, col, rows):
    """Rows (8-px) of column `col` inside `rows` whose cell is TOP-solid."""
    return [r for r in rows
            if int(plane[r, col]) & CP.BLOCK_ID_MASK
            and (int(plane[r, col]) >> CP.PLANE_SOL_SHIFT) & CP.SOL_TOP]


@pytest.mark.parametrize("manifest", [WFZ_SOLO, WOVEN], ids=["s2_wfz_solo", "s2_woven"])
def test_wing_fortress_is_pasted_with_its_plane_a_on_both_planes(donors, manifest):
    """WOVEN-WFZ-PLANE-B. Red before the re-key: Wing Fortress's plane-B solidity made it a
    'two-path' zone, so its donor plane B (none of the ship's decks but one) was kept, and a
    plane-B player fell through the ship."""
    _need(S.S2_FINAL)
    if manifest == WOVEN:
        _need(S.S2_PROTOTYPE)
    act = CM.load(manifest, donor_root=donors)
    pa, pb = CM._clip_collision(act, donors)
    wfz = [cl for cl in act.clips if cl.zone == "WFZ"]
    assert wfz, "the act has no Wing Fortress clip"
    for cl in wfz:
        dx, dy, dw, dh = (v // CM.TILE_PX for v in cl.dst)
        # not vacuous: the donor's own plane B differs from plane A inside this crop
        ta, tb = _tree_planes(cl, donors, act)
        sx, sy = cl.src[0] // CM.TILE_PX, cl.src[1] // CM.TILE_PX
        assert (ta[sy:sy + dh, sx:sx + dw] != tb[sy:sy + dh, sx:sx + dw]).any(), cl.id
        assert (pb[dy:dy + dh, dx:dx + dw] == pa[dy:dy + dh, dx:dx + dw]).all(), cl.id
        assert CM.zone_path_b_switchers(cl) == 0


def test_the_owners_wing_fortress_sighting_has_its_decks_on_plane_b(donors):
    """The sighting: woven (5133, 1389), grounded on layer 1 on the act's fill floor, under the
    ship. Plane A carries decks at y 1152 and 1280 in that column (MEASURED 2026-09-27, the
    booking); plane B must carry the same ones, and every other plane-A surface there."""
    _need(S.S2_FINAL)
    _need(S.S2_PROTOTYPE)
    act = CM.load(WOVEN, donor_root=donors)
    cl = CM._clip_at(act, 5133, 1389)
    assert cl is not None and cl.zone == "WFZ", cl
    pa, pb = CM._clip_collision(act, donors)
    col = 5133 // CM.TILE_PX
    rows = range(cl.dst[1] // CM.TILE_PX, (cl.dst[1] + cl.dst[3]) // CM.TILE_PX)
    a_rows, b_rows = _top_rows(pa, col, rows), _top_rows(pb, col, rows)
    for deck in (1152, 1280):
        assert deck // CM.TILE_PX in a_rows, f"plane A has no deck at y {deck} (premise)"
        assert deck // CM.TILE_PX in b_rows, f"plane B has no deck at y {deck}: he falls"
    assert a_rows == b_rows


def test_chemical_plant_seams_are_still_read_on_both_planes(donors, tmp_path):
    """CPZ has plane B, so a seam on CPZ where the planes disagree is still refused.
    Mutation: in a copy of Chemical Plant's tree, the ONE plane-B word under the
    CPZ-to-MTZ tunnel's floor at CPZ's last column loses its solidity (plane A keeps its
    flush floor). CPZ still has plane B everywhere else, so K6 must read both planes there
    and refuse. Control: the unmutated act bakes (test_the_real_acts_tunnels_...)."""
    _need(S.S2_FINAL)
    act = CM.load(MANIFEST, donor_root=donors)
    idx = next(i for i, co in enumerate(act.corridors)
               if CM._clip_at(act, co.dst[0] - 1, co.floor_y).zone == "CPZ")
    co = act.corridors[idx]
    xl = co.dst[0] - 1
    cl = CM._clip_at(act, xl, co.floor_y)
    # the seam cell in the DONOR's coordinates, then its section file and offset
    sx = xl - cl.dst[0] + cl.src[0]
    sy = co.floor_y - cl.dst[1] + cl.src[1]
    root = str(tmp_path / "donors")
    shutil.copytree(donors, root)
    tree = os.path.join(root, S.S2_FINAL, "CPZ")
    zm = json.load(open(os.path.join(tree, "zone.json")))
    st = act.section_tiles
    col, row = sx // 8, sy // 8
    sec = (row // st) * zm["grid"]["w"] + col // st
    off = 2 * ((row % st) * st + col % st)
    p = os.path.join(tree, f"section_{sec}.collattrb.bin")
    data = bytearray(open(p, "rb").read())
    w = (data[off] << 8) | data[off + 1]
    mask = CP.SOL_ALL << CP.PLANE_SOL_SHIFT
    assert w & mask, "the seam cell was expected to be solid on plane B before the mutation"
    w &= ~mask & 0xFFFF
    data[off:off + 2] = bytes(((w >> 8) & 0xFF, w & 0xFF))
    open(p, "wb").write(bytes(data))
    assert _plane_b_solid_words(tree) > 0, "CPZ must still be a two-path zone"
    act2 = CM.load(MANIFEST, donor_root=root)
    with pytest.raises(CM.ClipManifestError) as exc:
        CM.collision_grids(act2, root)
    msg = str(exc.value)
    assert msg.split()[0] == "K6" and "left neighbour's two collision planes disagree" in msg, \
        msg[:200]
