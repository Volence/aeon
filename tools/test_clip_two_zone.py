"""S2-COMPRESSED-ACT row 7: two zones in one act, joined by a corridor, each in its own colours.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Rows
that need a donor convert their own into pytest's tmp tree (the `donors` fixture, the
test_clip_manifest pattern) and SKIP SAYING SO when the donor checkout cannot be resolved.

WHAT IS PINNED HERE, and where the rest of the row's evidence lives:
  * the corridor's three structural promises — its art is on the one CRAM line no region
    install writes (DERIVED from Palette_LoadPal's own `Pal_Compose_Lines` write, not from a
    comment), its floor is the bank's full solid block with the odd-angle flag (FOUND, not
    typed), and K1-K3 refuse a corridor the bake could not honour;
  * Z2, the palette-crossing check, on synthetic modules: both arms of every refusal;
  * region_plan's refusals (butted zones, a stacked layout);
  * the COMMITTED neutral clip module is byte-for-byte what the emitter writes, so the
    canonical shapes cannot silently compile a stale or hand-edited one.
  Z1 (zone separation) and the deleted R20 live in tools/test_clip_rom_bake.py. K4 (the ROM
  pool is the composed pool) and the keyed verify_level_bin lane are END-TO-END checks that
  run on every `S2CLIP=... ./build.sh`; their red-first proofs are the on-disk mutations in
  docs/research/s2-compressed-act/2026-09-25-two-zone-act.md §5.
"""

import json
import os
import re
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
MANIFEST = os.path.join(REPO, "games", "sonic4", "data", "clips", "s2_ehz_cpz", "clips.json")
CASES = [(S.S2_FINAL, "EHZ"), (S.S2_FINAL, "CPZ")]


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
def donors(tmp_path_factory):
    root = str(tmp_path_factory.mktemp("s2twozonedonors"))
    for donor, zone in CASES:
        try:
            S.donor_root(donor)
        except (SystemExit, SuitePathError):
            continue
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    return root


def _doc():
    with open(MANIFEST) as fh:
        return json.load(fh)


def _write(tmp_path, doc):
    p = tmp_path / "clips.json"
    p.write_text(json.dumps(doc))
    return str(p)


# ---------------------------------------------------------------------------
# The corridor
# ---------------------------------------------------------------------------

def test_corridor_art_is_on_the_one_cram_line_no_install_writes():
    """DERIVED, not asserted from a comment: Palette_LoadPal (every region install reaches
    it) marks the lines its 96-byte base touched in Pal_Compose_Lines, and that literal is
    read out of engine/effects/palette.emp here. The corridor's line must be CLEAR in it —
    then no palette install, snap or fade, can recolour the corridor."""
    src = open(os.path.join(REPO, "engine", "effects", "palette.emp")).read()
    body = src[src.index("pub proc Palette_LoadPal"):]
    body = body[:body.index("\n}\n")]
    m = re.search(r"move\.b\s+#%([01]{4}),\s*Pal_Compose_Lines", body)
    assert m, "Palette_LoadPal no longer writes a Pal_Compose_Lines literal — re-derive"
    touched = int(m.group(1), 2)
    assert touched, "an install that touches no line proves nothing"
    assert not (touched >> CM.CORRIDOR_PAL_LINE) & 1, (
        f"the corridor is drawn on CRAM line {CM.CORRIDOR_PAL_LINE}, which a region install "
        f"writes (Pal_Compose_Lines %{m.group(1)}) — the fade would recolour it")
    co = CM.Corridor({"id": "k", "dst_rect": {"x": 0, "y": 0, "w": 64, "h": 64},
                      "floor_y": 32}, 0)
    words, _ = CM.corridor_cells(co)
    painted = words[(words & 0x7FF) != 0]
    assert painted.size and all(((int(w) >> 13) & 3) == CM.CORRIDOR_PAL_LINE for w in painted)


def test_corridor_cells_put_the_edge_on_the_floor_row_and_fill_below():
    co = CM.Corridor({"id": "k", "dst_rect": {"x": 0, "y": 64, "w": 32, "h": 64},
                      "floor_y": 96}, 0)
    words, _ = CM.corridor_cells(co)
    floor_row = (96 - 64) // 8
    assert set((words[:floor_row] & 0x7FF).ravel().tolist()) == {CM.CORRIDOR_TILE_BLANK}
    assert set((words[floor_row] & 0x7FF).tolist()) == {CM.CORRIDOR_TILE_EDGE}
    assert set((words[floor_row + 1:] & 0x7FF).ravel().tolist()) == {CM.CORRIDOR_TILE_FILL}
    sheet = CM.corridor_sheet()
    assert len(sheet) == 3 * 32 and sheet[:32] == bytes(32)
    assert sheet[32:64] != sheet[64:96] and sheet[32:64] != bytes(32)


def test_corridor_floor_is_the_banks_full_solid_odd_angle_block():
    """FOUND in the bank, not typed: every one of its 16 heights is a full cell and its
    angle carries the odd ("no usable angle") flag probe_core substitutes a cardinal for."""
    bank = os.path.join(REPO, "games", "sonic4", "data", "collision", "base_s2")
    s = CM.corridor_floor_shape(bank)
    hm = open(os.path.join(bank, "heightmaps.bin"), "rb").read()
    an = open(os.path.join(bank, "angles.bin"), "rb").read()
    assert list(hm[s * 16:(s + 1) * 16]) == [16] * 16 and an[s] & 1


@pytest.mark.parametrize("tag,mutate", [
    ("K3", lambda d: d["corridors"][0].__setitem__("floor_y", 770)),
    ("K3", lambda d: d["corridors"][0].__setitem__("floor_y", 1024)),
    ("K1", lambda d: d["corridors"][0].__setitem__("id", "Corridor")),
    ("K1", lambda d: d["corridors"][0].__setitem__("id", "ehz_act1")),
    ("K2", lambda d: d["corridors"][0]["dst_rect"].__setitem__("w", 1300)),
    ("R10", lambda d: d["corridors"][0]["dst_rect"].__setitem__("x", 10960)),
])
def test_the_corridor_rules_refuse_by_their_own_tag(donors, tmp_path, tag, mutate):
    _need(S.S2_FINAL)
    doc = _doc()
    CM.load(_write(tmp_path, doc), donor_root=donors)            # control: the real one loads
    mutate(doc)
    with pytest.raises(CM.ClipManifestError) as exc:
        CM.load(_write(tmp_path, doc), donor_root=donors)
    assert str(exc.value).split()[0] == tag, str(exc.value)[:200]


# ---------------------------------------------------------------------------
# region_plan and Z2 on the real manifest
# ---------------------------------------------------------------------------

def test_the_real_act_plans_two_regions_crossing_mid_corridor(donors):
    _need(S.S2_FINAL)
    act = CM.load(MANIFEST, donor_root=donors)
    plan = CRB.region_plan(act, donors)
    assert [(r["x0"], r["x1"], r["key"]) for r in plan["rows"]] == [
        (0, 11631, 0), (11632, act.grid_w * act.section_px - 1, 1)]
    mod, data = CRB.clip_module_text(plan), CRB.clip_data_block(plan)
    z2 = CRB.check_palette_crossings(act, mod, data, log=None)
    fade, step, half_w = CRB.crossing_constants()
    assert z2 and z2[0]["x"] == 11632
    assert min(z2[0]["margin_left"], z2[0]["margin_right"]) >= half_w + fade * step


def test_region_plan_refuses_two_zones_with_no_corridor(donors, tmp_path):
    _need(S.S2_FINAL)
    doc = _doc()
    doc.pop("corridors")
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.region_plan(CM.load(_write(tmp_path, doc), donor_root=donors), donors)
    assert "Z2" in str(exc.value) and "corridor" in str(exc.value)


# ---------------------------------------------------------------------------
# Z2 on synthetic modules — both arms of every refusal
# ---------------------------------------------------------------------------

class _C:
    def __init__(self, cid, key, x, w):
        self.id, self.zone_key, self.dst = cid, key, (x, 0, w, 1024)
        self.tree_key = ("d", f"Z{key}")


class _K:
    def __init__(self, x, w):
        self.id, self.dst, self.floor_y = "k", (x, 0, w, 1024), 512


class _A:
    def __init__(self, clips, corridors):
        self.clips, self.corridors = clips, corridors


def _plan(rows, transitions=(1, 1)):
    zones = [{"key": k, "donor": "d", "zone": f"Z{k}", "palette_file": "p",
              "palette_sha256": "0", "palette_words": [k] * 48,
              "palette_label": f"OJZ_Clip_Palette_{k}",
              "preset_label": f"OJZ_Clip_Preset_{k}"} for k in (0, 1)]
    return {"act": "t", "zones": zones,
            "rows": [{"x0": a, "x1": b, "y0": 0, "y1": 6143, "key": k,
                      "preset_label": f"OJZ_Clip_Preset_{k}", "why": "t"} for a, b, k in rows]}


def _z2(act, plan, transitions=(1, 1), data_rows=None):
    data = CRB.clip_data_block(plan if data_rows is None else _plan(data_rows))
    for k, t in enumerate(transitions):
        data = data.replace(f"pub data OJZ_Clip_Preset_{k}: EffectsPreset = preset(pal: "
                            f"OJZ_Clip_Palette_{k}, raster: Raster_Program_None, cycle: "
                            f"Pal_Cycle_None, transition: 1)",
                            f"pub data OJZ_Clip_Preset_{k}: EffectsPreset = preset(pal: "
                            f"OJZ_Clip_Palette_{k}, raster: Raster_Program_None, cycle: "
                            f"Pal_Cycle_None, transition: {t})")
    return CRB.check_palette_crossings(act, CRB.clip_module_text(plan), data,
                                       consts=(16, 16, 160), log=None)


ACT = _A([_C("a", 0, 0, 2048), _C("b", 1, 4096, 2048)], [_K(2048, 2048)])


def test_z2_passes_a_mid_corridor_crossing():
    out = _z2(ACT, _plan([(0, 3071, 0), (3072, 6143, 1)]))
    assert out[0]["x"] == 3072 and out[0]["margin_left"] == 1024


def test_z2_refuses_a_crossing_the_fade_can_see_a_zone_from():
    """160 + 16 x 16 = 416 px each side, from the engine's own terms (passed in here so the
    row pins the RULE; the real constants are read in the row above)."""
    _z2(ACT, _plan([(0, 2463, 0), (2464, 6143, 1)]))                 # 416 left: passes
    with pytest.raises(CRB.ClipRomError) as exc:
        _z2(ACT, _plan([(0, 2462, 0), (2463, 6143, 1)]))             # 415 left
    assert "Z2" in str(exc.value) and "416" in str(exc.value)


def test_z2_refuses_a_crossing_that_snaps():
    with pytest.raises(CRB.ClipRomError) as exc:
        _z2(ACT, _plan([(0, 3071, 0), (3072, 6143, 1)]), transitions=(1, 0))
    assert "Z2" in str(exc.value) and "SNAP" in str(exc.value)


def test_z2_refuses_more_than_one_install_between_two_zones():
    plan = _plan([(0, 2800, 0), (2801, 3200, 1), (3201, 3600, 0), (3601, 6143, 1)])
    with pytest.raises(CRB.ClipRomError) as exc:
        _z2(ACT, plan)
    assert "exactly once" in str(exc.value)


def test_z2_refuses_a_zone_drawn_under_the_other_zones_palette():
    with pytest.raises(CRB.ClipRomError) as exc:
        _z2(ACT, _plan([(0, 1999, 0), (2000, 6143, 1)]))
    assert "Z2" in str(exc.value) and "colours" in str(exc.value)


def test_z2_refuses_when_the_checked_rows_are_not_the_emitted_table():
    with pytest.raises(CRB.ClipRomError) as exc:
        _z2(ACT, _plan([(0, 3071, 0), (3072, 6143, 1)]),
            data_rows=[(0, 3087, 0), (3088, 6143, 1)])
    assert "not the rows the Act names" in str(exc.value)


# ---------------------------------------------------------------------------
# The committed neutral module
# ---------------------------------------------------------------------------

def test_the_committed_clip_module_is_the_neutral_one_byte_for_byte():
    """Every canonical shape compiles this file. It must be exactly what the emitter's
    neutral form writes — OJZ_CLIP_ACT = 0, no rows, a chooser that returns `hand`, no data
    and no label — or a stale clip bake (or a hand edit) is in the canonical ROM."""
    with open(CRB.CLIP_MODULE) as fh:
        assert fh.read() == CRB.clip_module_text(None), (
            "games/sonic4/data/generated/ojz/act1/clip_act.emp is not the neutral module; "
            "restore it with `python3 tools/clip_rom_bake.py emit-neutral`")
    with open(CRB.CLIP_DATA) as fh:
        assert CRB.CLIP_DATA_BEGIN not in fh.read(), (
            "the committed entity_data.emp carries a CLIP ACT DATA block — a clip bake's "
            "throwaway was committed")


# ---------------------------------------------------------------------------
# Each zone's own Sonic 2 background (research 2026-09-25 (B), parcel B-1)
# ---------------------------------------------------------------------------

DESCRIPTOR = os.path.join(REPO, "games", "sonic4", "data", "levels", "ojz", "act1",
                          "act_descriptor.emp")


def _planned(donors, tmp_path):
    """The real act's region plan with its backgrounds planned into a tmp generated dir,
    and the two module texts emitted from it."""
    act = CM.load(MANIFEST, donor_root=donors)
    plan = CRB.region_plan(act, donors)
    gen = tmp_path / "gen"
    gen.mkdir()
    spawn = CRB.engine_spawn(DESCRIPTOR)
    CRB.plan_backgrounds(plan, spawn, str(gen), str(tmp_path), log=None)
    return act, plan, str(gen), spawn


def test_the_act_default_background_is_the_start_zones_own(donors, tmp_path):
    """The act default is the zone the act STARTS in (BG_Init blits it before the camera
    exists), derived here from the descriptor's spawn and the manifest's own rectangles —
    the clip whose destination holds the spawn — never typed as 'EHZ'. Its rows name no
    background of their own; every other zone's rows name that zone's own pair."""
    _need(S.S2_FINAL)
    act, plan, gen, spawn = _planned(donors, tmp_path)
    holder = [c for c in act.clips
              if c.dst[0] <= spawn[0] < c.dst[0] + c.dst[2]
              and c.dst[1] <= spawn[1] < c.dst[1] + c.dst[3]]
    assert len(holder) == 1, f"the spawn {spawn} is in {len(holder)} clips"
    assert plan["bg_default_key"] == holder[0].zone_key
    zones = {z["key"]: z for z in plan["zones"]}
    assert zones[plan["bg_default_key"]]["zone"] == holder[0].zone
    for r in plan["rows"]:
        if r["key"] == plan["bg_default_key"]:
            assert (r["bg_layout"], r["bg_tiles"]) == (None, None)
        else:
            assert (r["bg_layout"], r["bg_tiles"]) == (
                f"OJZ_Clip_BG_Layout_{r['key']}", f"OJZ_Clip_BG_Tiles_{r['key']}")
    # the injector really wrote the start zone's lowering as the act default
    import clip_bg_lower as CBL
    words, tiles, _ = CBL.lower(holder[0].donor, holder[0].zone)
    assert open(os.path.join(gen, "zone_bg.bin"), "rb").read() == CBL.layout_blob(words)
    assert open(os.path.join(gen, "bg_tiles.bin"), "rb").read() == CBL.tiles_blob(tiles)
    # ...and with no animation band: the shipped OJZ bank does not ride along
    bganim = open(os.path.join(gen, "bg_anim.emp")).read()
    assert "BgAnim_Table: u16 = 0" in bganim and "bg_anim_banks.bin" not in bganim


def test_every_other_zone_carries_its_own_background_on_its_region_rows(donors, tmp_path):
    """Chemical Plant (every zone but the start one) is named in BOTH emitted tables — the
    rows the descriptor checks and the rows the Act binds — and its blobs are embedded in
    the data block, typed, and on disk as its own lowering. BG1 reads all of that back."""
    _need(S.S2_FINAL)
    act, plan, gen, _ = _planned(donors, tmp_path)
    others = [z for z in plan["zones"] if z["key"] != plan["bg_default_key"]]
    assert others, "a two-zone act has a zone that is not the start zone"
    mod, data = CRB.clip_module_text(plan), CRB.clip_data_block(plan)
    for z in others:
        for text in (mod, data):
            assert f"rg_bg_layout: {z['bg_layout_label']}, rg_bg_span: 0, " \
                   f"rg_bg_tiles: {z['bg_tiles_label']}" in text
        assert f"pub data {z['bg_layout_label']} (align: 2): [u8; BG_LAYOUT_SIZE]" in data
        assert f"pub data {z['bg_tiles_label']} (align: 2): [u8; {z['bg_tiles_bytes']}]" in data
    out = CRB.check_backgrounds(plan, mod, data, gen)
    assert out["regions"] == [z["zone"] for z in others]


def test_bg1_refuses_the_shipped_background_left_as_the_act_default(donors, tmp_path):
    _need(S.S2_FINAL)
    act, plan, gen, _ = _planned(donors, tmp_path)
    mod, data = CRB.clip_module_text(plan), CRB.clip_data_block(plan)
    CRB.check_backgrounds(plan, mod, data, gen)                          # control
    shipped = os.path.join(CRB.GEN_DIR, "zone_bg.bin")
    with open(os.path.join(gen, "zone_bg.bin"), "wb") as fh:
        fh.write(open(shipped, "rb").read())
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_backgrounds(plan, mod, data, gen)
    assert "BG1" in str(exc.value) and "zone_bg.bin" in str(exc.value)


def test_bg1_refuses_a_row_under_another_zones_background(donors, tmp_path):
    _need(S.S2_FINAL)
    act, plan, gen, _ = _planned(donors, tmp_path)
    other = next(z for z in plan["zones"] if z["key"] != plan["bg_default_key"])
    data = CRB.clip_data_block(plan)
    mod = CRB.clip_module_text(plan)
    CRB.check_backgrounds(plan, mod, data, gen)                          # control
    bad = mod.replace(f"rg_bg_layout: {other['bg_layout_label']}", "rg_bg_layout: 0", 1)
    with pytest.raises(CRB.ClipRomError) as exc:
        CRB.check_backgrounds(plan, bad, data, gen)
    assert "BG1" in str(exc.value)


def test_the_backdrop_is_the_donors_own_register_7_byte_and_neutral_is_zero(donors, tmp_path):
    """The clip module carries Sonic 2's own `Level:` backdrop byte; the neutral module a 0
    that nothing reads (ojz_scroll_test.emp stores it only under OJZ_CLIP_ACT == 1)."""
    _need(S.S2_FINAL)
    import re as _re
    act, plan, gen, _ = _planned(donors, tmp_path)
    s2asm = open(os.path.join(S.donor_root(S.S2_FINAL), "s2.asm"), errors="replace").read()
    level = s2asm[s2asm.index("\nLevel:"):s2asm.index("\nLevel_LoadPal:")]
    want = int(_re.findall(r"move\.w\s+#\$87([0-9A-Fa-f]{2}),\(a6\)", level)[0], 16)
    assert f"pub const OJZ_CLIP_BACKDROP = ${want:02X}\n" in CRB.clip_module_text(plan)
    assert "pub const OJZ_CLIP_BACKDROP = 0\n" in CRB.clip_module_text(None)
    src = open(os.path.join(REPO, "games", "sonic4", "test", "ojz_scroll_test.emp")).read()
    body = src[src.index("pub proc GameState_OJZScroll_Init"):]
    body = body[:body.index("\n}\n")]
    m = _re.search(r"if OJZ_CLIP_ACT == 1 \{\s*move\.b\s+#OJZ_CLIP_BACKDROP,\s*VDP_Shadow_Table"
                   r" \+ offsetof\(VdpShadow, vdp_bgcolor\)\s*\}", body)
    assert m, ("GameState_OJZScroll_Init no longer stores OJZ_CLIP_BACKDROP into the shadow "
               "register 7 under `if OJZ_CLIP_ACT == 1` — the clip sky would be black, or "
               "the store would reach a canonical shape")


def test_the_debug_test_backgrounds_are_not_in_a_clip_build(donors, tmp_path):
    """The canonical act's DEBUG-only test backgrounds (the tall map, the showcase layout and
    tiles) are emitted ONLY when a region table that names them is live — never in a clip
    act, whose own table replaces it. DERIVED, not listed: the labels are whatever the
    shipped descriptor's rows name as a background (`bg_layout:` / `bg_tiles:`); the clip
    act's emitted rows must name none of them; and each one's `pub data` and its SIZE const
    must be gated on a predicate that is false when OJZ_CLIP_ACT == 1. The bytes' absence
    from the built clip DEBUG ROM is the build's evidence (listing spans), not this row's."""
    _need(S.S2_FINAL)
    desc = open(DESCRIPTOR).read()
    labels = sorted(set(re.findall(r"\bbg_(?:layout|tiles):\s*(OJZ_Act1_\w+)", desc)))
    assert labels, "the shipped descriptor names no background blob on any row — re-derive"
    act, plan, gen, _ = _planned(donors, tmp_path)
    emitted = CRB.clip_module_text(plan) + CRB.clip_data_block(plan)
    assert not [lab for lab in labels if lab in emitted]
    assets = open(os.path.join(REPO, "games", "sonic4", "data", "levels", "ojz", "act1",
                               "act_assets.emp")).read()
    for lab in labels:
        m = re.search(rf"^pub data {lab}:\s*\[u8;\s*(\w+)\]\s*=\s*if (\w+) == 1 \{{\s*embed\("
                      rf"[^)]*\)\s*\}} else \{{ \[\] \}}", assets, re.M)
        assert m, f"{lab} is not a gated `if <GATE> == 1 {{ embed }} else {{ [] }}` in act_assets.emp"
        size, gate = m.groups()
        assert re.search(rf"^pub const {size}\s*=\s*if {gate} == 1 \{{", assets, re.M), (
            f"{lab}'s length {size} is not gated on the same predicate {gate}")
        g = re.search(rf"^const {gate}\s*=\s*if (.+?) \{{ 1 \}} else \{{ 0 \}}", assets, re.M)
        assert g, f"the gate {gate} is not a `if <predicate> {{ 1 }} else {{ 0 }}` const"
        terms = [t.strip() for t in g.group(1).split("&&")]
        assert "OJZ_CLIP_ACT == 0" in terms and "DEBUG == 1" in terms, (
            f"{lab} is gated on `{g.group(1)}`, which does not exclude a clip act — the "
            f"clip DEBUG ROM would carry test data its region table cannot reach")
