"""K6 at a zone with NO plane-B collision (woven first screen, s2_mtz_cpz, 2026-09-27).

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Rows
that need a donor convert their own into pytest's tmp tree and SKIP SAYING SO when the donor
checkout cannot be resolved (the tools/test_clip_two_zone.py pattern).

THE BLOCKER THIS CLOSES (docs/research/2026-09-27-mega-act-woven.md §C item 9, MEASURED).
K6 read the neighbour's floor row on BOTH collision planes and refused when they disagreed.
Sonic 2's Metropolis has one collision path: s2.asm names `ColP_MTZ` as both its primary and
secondary index, and its chunk words carry no path-B solidity at all, so the converted tree's
plane B has a shape in every cell and solidity in NONE (0 of 221,276 words, MEASURED by the
converter's tree). Every flush floor at Metropolis's edge therefore read "heights 16 and 0" and
was refused, though there is no plane-B seam there to match.

THE RULE NOW (`clip_manifest.zone_has_plane_b`, `_seam_ramps`): a neighbour whose ZONE has no
plane-B solidity anywhere in its whole converted tree is matched on plane A alone. The test is
the ZONE, not the clip's crop and not the seam column: a zone that uses plane B anywhere is
held to both planes exactly as before, even where its crop happens to be empty on B.

WHAT IS PINNED:
  * the real act's two tunnels bake at Metropolis's edges, and what K6 measured there;
  * zone_has_plane_b agrees with a direct count of the tree's plane-B solidity bits;
  * THE CONTROL THAT IT IS NOT LOOSENED: Metropolis's own tree with ONE plane-B solid word
    planted far from the seam (a different section) is a zone that has plane B, and K6
    refuses the same seam again with "disagree" — the exemption is keyed to the zone's
    measurement and nothing else;
  * Chemical Plant, which has plane B, is still read on both planes at its own seams.
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
CASES = [(S.S2_FINAL, "MTZ"), (S.S2_FINAL, "CPZ")]


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
    root = str(tmp_path_factory.mktemp("s2k6planeb"))
    for donor, zone in CASES:
        try:
            S.donor_root(donor)
        except (SystemExit, SuitePathError):
            continue
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    return root


def _plane_b_solid_words(tree):
    """Plane-B words with any solidity bit, counted straight off the files (the reference
    zone_has_plane_b is held to)."""
    n = 0
    for f in sorted(os.listdir(tree)):
        if f.endswith(".collattrb.bin"):
            data = open(os.path.join(tree, f), "rb").read()
            for i in range(0, len(data), 2):
                w = (data[i] << 8) | data[i + 1]
                n += bool((w >> CP.PLANE_SOL_SHIFT) & CP.SOL_ALL)
    return n


def test_zone_has_plane_b_is_the_trees_own_count(donors):
    _need(S.S2_FINAL)
    act = CM.load(MANIFEST, donor_root=donors)
    by_zone = {cl.zone: cl for cl in act.clips}
    for zone in ("MTZ", "CPZ"):
        tree = os.path.join(donors, S.S2_FINAL, zone)
        count = _plane_b_solid_words(tree)
        assert CM.zone_has_plane_b(by_zone[zone], donors) == (count > 0), (zone, count)
    # The premise the exemption rests on, measured rather than assumed:
    assert _plane_b_solid_words(os.path.join(donors, S.S2_FINAL, "MTZ")) == 0
    assert _plane_b_solid_words(os.path.join(donors, S.S2_FINAL, "CPZ")) > 0


def test_the_real_acts_tunnels_meet_metropolis_on_plane_a(donors):
    """Before the fix this raised `K6 ... two collision planes disagree at x=1535 ...
    (heights 16 and 0)` (the report's MEASURED blocker, reproduced 2026-09-27 on this
    manifest). Each corridor's Metropolis end must now be measured on plane A: flush, or a
    ramp from plane A's own height."""
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
            ha = CM._word_heights(int(planes[0][co.floor_y // 8, x // 8]), hm)
            ha = ha[x % n] if ha is not None else 0
            if ramps[side] is None:
                assert ha == n, (co.id, side, ha)
            else:
                assert ramps[side]["neighbour_surface_y"] == co.floor_y + n - ha, (co.id, side)
            if cl.zone == "MTZ":
                seen_mtz += 1
                hb = CM._word_heights(int(planes[1][co.floor_y // 8, x // 8]), hm)
                assert hb is None, "Metropolis's plane B was expected to carry no floor here"
    assert seen_mtz == 2, "both tunnels have a Metropolis end"


def test_a_zone_with_plane_b_anywhere_is_still_held_to_both_planes(donors, tmp_path):
    """THE CONTROL. The same act over a Metropolis tree carrying ONE plane-B solid word, in
    its last section (x 8192.., nowhere near either seam). That zone HAS plane B, so the
    seam at x=1535 must be refused exactly as before the fix."""
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
    with pytest.raises(CM.ClipManifestError) as exc:
        CM.collision_grids(act, root)
    msg = str(exc.value)
    assert msg.split()[0] == "K6" and "disagree" in msg, msg[:200]


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
