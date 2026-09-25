"""The shorter-connector parcel (2026-09-25): Z2's background term and the per-clip crossing
overrides. Research: docs/research/2026-09-25-shorter-connector.md.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Rows that
need a donor convert their own into pytest's tmp tree and SKIP SAYING SO when the donor
checkout cannot be resolved (the tools/test_clip_two_zone.py pattern).

WHAT IS PINNED:
  * Z2's BACKGROUND TERM applies to every clip act: a crossing the fade alone would pass is
    refused when the background switch into a side's zone takes longer than the fade.
    `background_switch_frames` is derived from engine constants (read here, never typed).
  * `crossing_overrides` is a NAMED, PER-CLIP key: unknown keys and a missing `why` are
    refused; without it a snapping preset is still refused (test_clip_two_zone's row); with
    `palette: snap` a FADING preset is refused, and the snap's margin is HALF_W + STEP x
    max(SNAP_FRAMES, background frames).
  * `co_resident` backgrounds: every zone's cells draw, through the shared blob, exactly
    the tile a fresh lowering of its own zone draws; a union past the arena is refused.
  * the feasibility clip `s2_ehz_cpz_short` is the SHORTEST corridor on the 16-px grid that
    Z1 and the re-derived Z2 admit, and the landed `s2_ehz_cpz` is untouched by the new
    term (its margins are what they were).

What these rows CANNOT see is the screen: whether the swap and the repaint really happen
unseen is tools/crossing_witness.py's job (a witness, run by hand on a clip ROM).
"""

import json
import os
import sys

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_manifest as CM                  # noqa: E402
import clip_rom_bake as CRB                 # noqa: E402
import s2_donor as S                        # noqa: E402
import s2_zone_convert as C                 # noqa: E402
from suite_paths import SuitePathError      # noqa: E402

REPO = os.path.dirname(TOOLS)
CLIPS = os.path.join(REPO, "games", "sonic4", "data", "clips")
SHORT = os.path.join(CLIPS, "s2_ehz_cpz_short", "clips.json")
LANDED = os.path.join(CLIPS, "s2_ehz_cpz", "clips.json")
DESCRIPTOR = os.path.join(REPO, "games", "sonic4", "data", "levels", "ojz", "act1",
                          "act_descriptor.emp")


def _need(donor):
    try:
        return S.donor_root(donor)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {donor} donor could not be resolved, so NOTHING in this row "
                    f"is checked: {e}")


@pytest.fixture(autouse=True, scope="module")
def no_working_tree_donors():
    real = CM.DEFAULT_DONOR_ROOT
    CM.DEFAULT_DONOR_ROOT = os.path.join(
        REPO, "tools", "__no_donor_root_for_tests__", "this-path-must-not-exist")
    assert not os.path.exists(CM.DEFAULT_DONOR_ROOT)
    yield
    CM.DEFAULT_DONOR_ROOT = real


@pytest.fixture(scope="module")
def donors(tmp_path_factory):
    root = str(tmp_path_factory.mktemp("s2crossingdonors"))
    for zone in ("EHZ", "CPZ"):
        try:
            S.donor_root(S.S2_FINAL)
        except (SystemExit, SuitePathError):
            continue
        C.convert_zone(zone, S.S2_FINAL, os.path.join(root, S.S2_FINAL, zone), quiet=True)
    return root


# ---------------------------------------------------------------------------
# synthetic acts (test_clip_two_zone's shapes, with an override-carrying `raw`)
# ---------------------------------------------------------------------------

class _C:
    def __init__(self, cid, key, x, w):
        self.id, self.zone_key, self.dst = cid, key, (x, 0, w, 1024)
        self.tree_key = ("d", f"Z{key}")


class _K:
    def __init__(self, x, w):
        self.id, self.dst, self.floor_y = "k", (x, 0, w, 1024), 512


class _A:
    def __init__(self, clips, corridors, raw=None):
        self.id = "t"
        self.clips, self.corridors, self.raw = clips, corridors, raw or {}


def _plan(rows, overrides=None):
    zones = [{"key": k, "donor": "d", "zone": f"Z{k}", "palette_file": "p",
              "palette_sha256": "0", "palette_words": [k] * 48,
              "palette_label": f"OJZ_Clip_Palette_{k}",
              "preset_label": f"OJZ_Clip_Preset_{k}"} for k in (0, 1)]
    return {"act": "t", "zones": zones, "overrides": overrides,
            "rows": [{"x0": a, "x1": b, "y0": 0, "y1": 6143, "key": k,
                      "preset_label": f"OJZ_Clip_Preset_{k}", "why": "t"} for a, b, k in rows]}


SNAP = {"crossing_overrides": {"palette": "snap", "why": "test"}}


def _z2(act, plan, bg_frames=None, data_plan=None):
    return CRB.check_palette_crossings(act, CRB.clip_module_text(plan),
                                       CRB.clip_data_block(data_plan or plan),
                                       consts=(16, 16, 160), log=None, bg_frames=bg_frames)


def _act(gap_w, raw=None):
    return _A([_C("a", 0, 0, 2048), _C("b", 1, 2048 + gap_w, 2048)],
              [_K(2048, gap_w)], raw)


# ---------------------------------------------------------------------------
# Z2's background term — every act
# ---------------------------------------------------------------------------

def test_z2_background_term_refuses_a_crossing_only_the_fade_fits():
    """Crossing at 2464, 416 px from zone a: the fade (160 + 16 x 16) fits exactly. A
    background that takes 17 frames into zone a needs 160 + 16 x 17 = 432 on that side."""
    act = _act(2048)
    plan = _plan([(0, 2463, 0), (2464, 6143, 1)])
    _z2(act, plan, bg_frames={0: 16, 1: 16})                       # control: passes
    with pytest.raises(CRB.ClipRomError) as exc:
        _z2(act, plan, bg_frames={0: 17, 1: 0})
    assert "Z2" in str(exc.value) and "432" in str(exc.value)


def test_z2_background_term_leaves_the_default_rule_unchanged_below_the_fade():
    """background <= PAL_FADE_FRAMES: the margin is the old HALF_W + FADE x STEP."""
    out = _z2(_act(2048), _plan([(0, 3071, 0), (3072, 6143, 1)]), bg_frames={0: 11, 1: 13})
    assert out[0]["margin_needed_left"] == out[0]["margin_needed_right"] == 160 + 16 * 16


def test_background_switch_frames_is_chunks_plus_the_visible_wipe():
    """Derived from engine/level/bg.emp's constants, read — the CPZ blob of the landed act
    (237 tiles) and a co-resident zone."""
    chunk, per_frame, screen_rows = CRB.background_constants()
    wipe = -(-screen_rows // per_frame)
    plan = {"bg_default_key": 0, "zones": [
        {"key": 0, "zone": "A", "bg_tile_bytes_effective": 141 * 32},
        {"key": 1, "zone": "B", "bg_tiles_label": "L1", "bg_tile_bytes_effective": 237 * 32}]}
    got = CRB.background_switch_frames(plan)
    assert got == {0: -(-141 * 32 // chunk) + wipe, 1: -(-237 * 32 // chunk) + wipe}
    shared = {"bg_default_key": 0, "zones": [
        {"key": 0, "zone": "A", "bg_tile_bytes_effective": 376 * 32},
        {"key": 1, "zone": "B", "bg_tile_bytes_effective": 376 * 32}]}
    assert CRB.background_switch_frames(shared) == {0: wipe, 1: wipe}


# ---------------------------------------------------------------------------
# crossing_overrides — named, per clip
# ---------------------------------------------------------------------------

def test_overrides_absent_are_the_default_rule():
    ov = CRB.crossing_overrides(_act(2048))
    assert (ov["palette"], ov["background"], ov["declared"]) == ("fade", "overwrite", False)


@pytest.mark.parametrize("raw,needle", [
    ({"palette": "snap"}, "why"),
    ({"palette": "instant", "why": "x"}, "palette"),
    ({"palette": "snap", "fade_frames": 4, "why": "x"}, "fade_frames"),
])
def test_overrides_refuse_what_they_do_not_name(raw, needle):
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.crossing_overrides(_act(2048, {"crossing_overrides": raw}))
    assert needle in str(exc.value)


def test_snap_override_emits_transition_0_and_holds_the_snap_margin():
    """160 + 16 x max(SNAP_FRAMES, background frames) each side."""
    act = _act(640, SNAP)
    mid = 2048 + 320
    plan = _plan([(0, mid - 1, 0), (mid, 6143, 1)], overrides=CRB.crossing_overrides(act))
    assert "transition: 0)" in CRB.clip_data_block(plan)
    out = _z2(act, plan, bg_frames={0: 8, 1: 8})
    assert out[0]["palette"] == "snap"
    assert out[0]["margin_needed_left"] == 160 + 16 * 8
    with pytest.raises(CRB.ClipRomError) as exc:                  # 10 frames need 320: 1 px over
        _z2(act, _plan([(0, mid - 2, 0), (mid - 1, 6143, 1)],
                       overrides=CRB.crossing_overrides(act)), bg_frames={0: 10, 1: 8})
    assert "SNAP" in str(exc.value)


def test_snap_override_refuses_a_preset_that_still_fades():
    act = _act(640, SNAP)
    mid = 2048 + 320
    plan = _plan([(0, mid - 1, 0), (mid, 6143, 1)], overrides=CRB.crossing_overrides(act))
    fading = _plan([(0, mid - 1, 0), (mid, 6143, 1)])              # no override: transition 1
    with pytest.raises(CRB.ClipRomError) as exc:
        _z2(act, plan, data_plan=fading)
    assert "snap" in str(exc.value)


# ---------------------------------------------------------------------------
# co_resident backgrounds (real donors)
# ---------------------------------------------------------------------------

def _short_plan(donors, tmp_path):
    act = CM.load(SHORT, donor_root=donors)
    plan = CRB.region_plan(act, donors)
    gen = tmp_path / "gen"
    gen.mkdir()
    CRB.plan_backgrounds(plan, CRB.engine_spawn(DESCRIPTOR), str(gen), str(tmp_path), log=None)
    return act, plan, str(gen)


def test_co_resident_blob_draws_every_zones_own_tiles(donors, tmp_path):
    _need(S.S2_FINAL)
    import clip_bg_lower as CBL
    from vram_map import BG_TILE_CAPACITY
    act, plan, gen = _short_plan(donors, tmp_path)
    union = None
    for z in plan["zones"]:
        words, tiles = plan["_bg_lowered"][z["key"]]
        union = tiles if union is None else union
        assert tiles == union, "every zone must name the ONE shared blob"
        fw, ft, _ = CBL.lower(z["donor"], z["zone"])
        drawn = [(w & ~0x7FF, ft[w & 0x7FF]) if w else None for w in fw]
        assert [(w & ~0x7FF, union[w & 0x7FF]) if w else None for w in words] == drawn
        if z["key"] != plan["bg_default_key"]:
            assert not z.get("bg_tiles_label")
            assert not os.path.exists(os.path.join(gen, CRB.CLIP_BG_TILES_BIN.format(key=z["key"])))
    assert len(union) <= BG_TILE_CAPACITY
    assert open(os.path.join(gen, "bg_tiles.bin"), "rb").read() == CBL.tiles_blob(union)
    mod, data = CRB.clip_module_text(plan), CRB.clip_data_block(plan)
    CRB.check_backgrounds(plan, mod, data, gen)
    assert CRB.background_switch_frames(plan) == {
        z["key"]: -(-CRB.background_constants()[2] // CRB.background_constants()[1])
        for z in plan["zones"]}


def test_bg1_refuses_a_co_resident_cell_that_draws_another_tile(donors, tmp_path):
    """The re-indexed layout is written from the plan, so comparing the file to the plan
    proves nothing: BG1 must re-lower the zone and compare what each cell DRAWS. Corrupt one
    cell in the plan AND on disk; only that comparison can see it."""
    _need(S.S2_FINAL)
    import clip_bg_lower as CBL
    act, plan, gen = _short_plan(donors, tmp_path)
    mod, data = CRB.clip_module_text(plan), CRB.clip_data_block(plan)
    CRB.check_backgrounds(plan, mod, data, gen)                          # control
    key = next(k for k in plan["_bg_lowered"] if k != plan["bg_default_key"])
    words, tiles = plan["_bg_lowered"][key]
    i = next(i for i, w in enumerate(words) if w and (w & 0x7FF) + 1 < len(tiles)
             and tiles[(w & 0x7FF) + 1] != tiles[w & 0x7FF])
    words = list(words)
    words[i] += 1
    plan["_bg_lowered"][key] = (words, tiles)
    with open(os.path.join(gen, CRB.CLIP_BG_LAYOUT_BIN.format(key=key)), "wb") as fh:
        fh.write(CBL.layout_blob(words))
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_backgrounds(plan, mod, data, gen)
    assert "BG1" in str(exc.value) and f"cell {i}" in str(exc.value)


def test_co_resident_refuses_a_union_past_the_arena(donors, tmp_path, monkeypatch):
    _need(S.S2_FINAL)
    import vram_map
    monkeypatch.setattr(vram_map, "BG_TILE_CAPACITY", 300)
    with pytest.raises(CRB.ClipRomError) as exc:
        _short_plan(donors, tmp_path)
    assert "BG_TILE_CAPACITY" in str(exc.value)


# ---------------------------------------------------------------------------
# the feasibility clip and the landed act
# ---------------------------------------------------------------------------

def _shortest(act, z2_side_frames, z1_cells):
    fade, step, half_w = CRB.crossing_constants()
    co = act.corridors[0]
    left = co.dst[0]

    def fits(w):
        mid = ((left + left + w) // 2) & ~15
        fl, fr = z2_side_frames
        return (mid - left >= half_w + fl * step and left + w - mid >= half_w + fr * step
                and w >= z1_cells * CM.TILE_PX)
    return next(w for w in range(16, 1 << 14, 16) if fits(w))


def test_the_short_clip_is_the_shortest_its_overrides_allow(donors, tmp_path):
    """Z1 (TILE_CACHE_COLS - 1 cells) and Z2 re-derived (HALF_W + STEP x max(SNAP_FRAMES,
    the co-resident background's visible wipe)), both read from source."""
    _need(S.S2_FINAL)
    import fg_page_order as FPO
    act, plan, gen = _short_plan(donors, tmp_path)
    ov = CRB.crossing_overrides(act)
    assert ov["declared"] and (ov["palette"], ov["background"]) == ("snap", "co_resident")
    bgf = CRB.background_switch_frames(plan)
    frames = [max(CRB.SNAP_FRAMES, bgf[k]) for k in (0, 1)]
    z1 = FPO.load_budget_constants()["TILE_CACHE_COLS"] - 1
    assert act.corridors[0].dst[2] == _shortest(act, frames, z1)
    out = CRB.check_palette_crossings(act, CRB.clip_module_text(plan),
                                      CRB.clip_data_block(plan), bg_frames=bgf)
    assert out[0]["palette"] == "snap"


def test_the_landed_act_is_held_to_what_it_was(donors, tmp_path):
    """s2_ehz_cpz carries no override: fade, overwrite, and the background term does not
    move its margin (its backgrounds switch in fewer frames than PAL_FADE_FRAMES)."""
    _need(S.S2_FINAL)
    act = CM.load(LANDED, donor_root=donors)
    assert not CRB.crossing_overrides(act)["declared"]
    plan = CRB.region_plan(act, donors)
    gen = tmp_path / "gen"
    gen.mkdir()
    CRB.plan_backgrounds(plan, CRB.engine_spawn(DESCRIPTOR), str(gen), str(tmp_path), log=None)
    fade, step, half_w = CRB.crossing_constants()
    bgf = CRB.background_switch_frames(plan)
    assert max(bgf.values()) <= fade
    out = CRB.check_palette_crossings(act, CRB.clip_module_text(plan),
                                      CRB.clip_data_block(plan), bg_frames=bgf)
    assert out[0]["palette"] == "fade"
    assert out[0]["margin_needed_left"] == out[0]["margin_needed_right"] == half_w + fade * step
    assert "transition: 1)" in CRB.clip_data_block(plan)
    assert json.load(open(LANDED)).get("crossing_overrides") is None
