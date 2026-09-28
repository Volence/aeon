"""tools/s2_layer_lines.py — Sonic 2's Obj03 lines baked into a clip act's layer-line table.

Every expectation below is DERIVED: the Obj03 id, the four half-lengths and the object layouts
come from the donor disassembly itself (s2disasm), and the LL_* bits from
engine/system/constants.emp. The counts pinned against the research
(docs/research/2026-09-26-s2clip-loops-planes.md: 19 EHZ lines, 25 CPZ) are re-derived here
from the layout files by a second, independent reader, not copied.
"""
import os
import struct
import sys

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_manifest as CM          # noqa: E402
import s2_donor                     # noqa: E402
import s2_layer_lines as SLL        # noqa: E402
import s2_zone_convert as C         # noqa: E402
from suite_paths import SuitePathError  # noqa: E402

REPO = os.path.dirname(TOOLS)
CLIPS = os.path.join(REPO, "games", "sonic4", "data", "clips")


#: The converted zone trees the shipped manifests clip (every clips.json under CLIPS names
#: s2disasm EHZ and/or CPZ). A manifest that starts naming another zone fails loudly with
#: clip_manifest's R4 ("no converted tree at ..."), it cannot pass by skipping.
CASES = [(s2_donor.S2_FINAL, "EHZ"), (s2_donor.S2_FINAL, "CPZ")]


def _donor_or_skip():
    try:
        root = s2_donor.donor_root(s2_donor.S2_FINAL)
    except (SystemExit, SuitePathError) as exc:
        pytest.skip("the s2disasm donor checkout could not be resolved, so NOTHING in this "
                    "row is checked: %s" % exc)
    return root


@pytest.fixture(autouse=True, scope="module")
def no_working_tree_donors():
    """No row may read the repo's own (gitignored) converted donor trees.

    The same guard test_clip_manifest carries, for the same incident class: this file shipped
    (332cc1ba) with seven `CM.load(p)` calls and no `donor_root=`, green in the worktree that
    had run s2_zone_convert and 10 FAILED rows in every fresh landing worktree. Pointing the
    default at a path that cannot exist makes that mistake fail on EVERY machine.
    """
    real = CM.DEFAULT_DONOR_ROOT
    CM.DEFAULT_DONOR_ROOT = os.path.join(
        REPO, "tools", "__no_donor_root_for_tests__", "this-path-must-not-exist")
    assert not os.path.exists(CM.DEFAULT_DONOR_ROOT)
    yield
    CM.DEFAULT_DONOR_ROOT = real


@pytest.fixture(scope="module")
def donors(tmp_path_factory):
    """A converted donor root in pytest's own tmp tree, MADE here from the read-only s2disasm
    checkout (the converter is deterministic), so the rows run on a fresh checkout instead
    of requiring the caller to have run s2_zone_convert first."""
    _donor_or_skip()
    root = str(tmp_path_factory.mktemp("s2layerlinedonors"))
    for donor, zone in CASES:
        C.convert_zone(zone, donor, os.path.join(root, donor, zone), quiet=True)
    return root


def _independent_obj03(root, layout, rect):
    """A second reader of the layout: every record with id 3 inside `rect`."""
    data = open(os.path.join(root, "level", "objects", layout + ".bin"), "rb").read()
    sx, sy, sw, sh = rect
    out = []
    for i in range(0, len(data), 6):
        x, yw, oid, st = struct.unpack(">HHBB", data[i:i + 6])
        if oid == 3 and sx <= x < sx + sw and sy <= (yw & 0xFFF) < sy + sh:
            out.append((x, yw & 0xFFF, st, (yw >> 13) & 1))
    return out


def test_engine_constants_are_seven_distinct_bits_and_the_sentinels():
    c = SLL.engine_constants()
    bits = [c[n] for n in ("LL_KEEP_PATH", "LL_GROUNDED", "LL_HORIZONTAL", "LL_FWD_B",
                           "LL_BACK_B", "LL_FWD_HI", "LL_BACK_HI")]
    assert sorted(bits) == list(range(7))
    assert c["LL_KEY_BEFORE"] == 0x8000 and c["LL_KEY_AFTER"] == 0x7FFF
    assert 0 < c["LL_SEG_W"] < 0x8000


def test_obj03_id_and_lengths_come_from_s2_asm():
    _donor_or_skip()
    asm = SLL._s2_asm(s2_donor.S2_FINAL)
    # Obj_Index starts at id 1 with Sonic, Tails, then the plane switcher.
    assert SLL.obj03_id(asm) == 3
    assert SLL.obj03_half_lengths(asm) == (0x20, 0x40, 0x80, 0x100)


def test_flags_repack_obj03_subtypes():
    c = SLL.engine_constants()
    b = {n: 1 << c[n] for n in c if n.startswith("LL_") and c[n] < 8}
    # EHZ's apex line: grounded-only, crossing left -> B, right -> A.
    assert SLL.flags_of(0x91, 0, c) == b["LL_GROUNDED"] | b["LL_BACK_B"]
    # EHZ's exit line: the same without the grounded bit.
    assert SLL.flags_of(0x11, 0, c) == b["LL_BACK_B"]
    # CPZ's vertical loop entry: right -> B + high priority, left -> A + high priority.
    assert SLL.flags_of(0x6A, 0, c) == b["LL_FWD_B"] | b["LL_FWD_HI"] | b["LL_BACK_HI"]
    # An x-flipped (priority-only) line keeps its priority bits and drops its path bits.
    assert SLL.flags_of(0x39, 1, c) == b["LL_KEEP_PATH"] | b["LL_FWD_HI"]
    # A horizontal line.
    assert SLL.flags_of(0x0D, 0, c) == b["LL_HORIZONTAL"] | b["LL_FWD_B"]


def test_s2_ehz_cpz_plan_matches_an_independent_reading_of_the_layouts(donors):
    root = _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"), donor_root=donors)
    p = SLL.plan(act)
    per_zone = {}
    for ln in p["lines"]:
        per_zone[ln["zone"]] = per_zone.get(ln["zone"], 0) + 1
    want = {cl.zone: len(_independent_obj03(root, s2_donor.zone_row(cl.zone, cl.donor)["layout"],
                                            cl.src)) for cl in act.clips}
    assert per_zone == want
    # the research's census, re-derived above rather than trusted
    assert want == {"EHZ": 19, "CPZ": 25}
    c = p["consts"]
    h = 1 << c["LL_HORIZONTAL"]
    keys = [r["key"] for r in p["rows"]]
    assert keys == sorted(keys)
    for r in p["rows"]:
        if r["flags"] & h:
            assert 0 < r["b"] - r["key"] <= c["LL_SEG_W"]
        else:
            assert r["a"] < r["b"]
    # every horizontal line's segments partition its extent exactly
    for ln in p["lines"]:
        if ln["horizontal"]:
            segs = sorted((r["key"], r["b"]) for r in p["rows"]
                          if r["flags"] & h and r["a"] == ln["y"] and r["order"] == ln["order"])
            assert segs[0][0] == ln["lo"] and segs[-1][1] == ln["hi"]
            assert all(a[1] == b[0] for a, b in zip(segs, segs[1:]))
    # CPZ is pasted at (+11360, +256): its lines are moved with it
    cpz = [ln for ln in p["lines"] if ln["zone"] == "CPZ"]
    assert all(ln["x"] == ln["src"][0] + 11360 and ln["y"] == ln["src"][1] + 256 for ln in cpz)


def test_loop_one_is_an_apex_line_then_an_exit_line(donors):
    """What the witness derives its drive expectations from: past x 3950 the first grounded-only
    row is the apex line at 4224 and the next row the exit line at 4368."""
    _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"), donor_root=donors)
    p = SLL.plan(act)
    import s2clip_layer_line_witness as W
    apex, exit_ = W.loop_lines(p, 3950, "right")
    assert (apex["key"], exit_["key"]) == (4224, 4368)
    apex_l, exit_l = W.loop_lines(p, 4500, "left")
    assert (apex_l["key"], exit_l["key"]) == (4224, 4368)


@pytest.mark.parametrize("clip", ["s2_ehz_cpz", "s2_ehz_boot", "s2_two_clip", "s2_two_clip_pins"])
def test_every_shipped_clip_manifest_bakes(clip, donors):
    _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, clip, "clips.json"), donor_root=donors)
    p = SLL.plan(act)
    assert p["rows"], "%s has no plane switchers in its rectangles" % clip


def test_l2_refuses_a_line_whose_extent_leaves_the_clip(donors):
    """A real line, a real layout: crop EHZ so the apex line's y extent (400..527) crosses the
    rectangle's bottom edge at 500."""
    _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"), donor_root=donors)
    cl = act.clips[0]
    cl.src = (4096, 0, 512, 500)
    cl.dst = (4096, 0, 512, 500)
    act.clips = [cl]
    with pytest.raises(SLL.LayerLineError, match=r"^L2 EHZ Obj03 at \(4224, 464\)"):
        SLL.plan(act)


def test_l1_refuses_an_unregistered_donor(donors):
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"), donor_root=donors)
    act.clips[0].donor = "skdisasm"
    with pytest.raises(SLL.LayerLineError, match=r"^L1 "):
        SLL.plan(act)


# ---------------------------------------------------------------------------
# Woven HPZ / WFZ / OOZ prep (2026-09-27): the object layout comes from the donor's own
# pointer table, revisions resolved; the prototype's records decoded; its Obj03 refused.
# ---------------------------------------------------------------------------

def _fake_act(donor, zone, src, dst=None, section=2048):
    from types import SimpleNamespace as NS
    dst = dst or src
    clip = NS(id=f"{zone.lower()}_probe", donor=donor, zone=zone, src=tuple(src), dst=tuple(dst))
    gw = -(-(dst[0] + dst[2]) // section)
    gh = -(-(dst[1] + dst[3]) // section)
    return NS(clips=[clip], section_px=section, grid_w=gw, grid_h=gh)


def _proto_or_skip():
    try:
        return s2_donor.donor_root(s2_donor.S2_PROTOTYPE)
    except (SystemExit, SuitePathError) as exc:
        pytest.skip("the s2-simonwai-disasm donor checkout could not be resolved, so NOTHING "
                    "in this row is checked: %s" % exc)


def _independent_ids(path, final):
    """A second reader: (x, y, id) of every record, the id masked the way each loader masks it."""
    data = open(path, "rb").read()
    out = []
    for i in range(0, len(data) - len(data) % 6, 6):
        x, yw, oid, _st = struct.unpack(">HHBB", data[i:i + 6])
        if x == 0xFFFF:
            break
        out.append((x, yw & 0xFFF, oid if final else oid & 0x7F))
    return out


def test_wfz_object_layout_is_off_objects_act1_at_the_donors_revision():
    """WFZ's level layout is `WFZ.kos`, its object layout `Objects_WFZ_1`, BINCLUDEd once per
    revision. The one picked is the one s2.asm's own `gameRevision` assembles."""
    root = _donor_or_skip()
    asm = SLL._s2_asm(s2_donor.S2_FINAL)
    rev = SLL._game_revision(asm)
    path = SLL.object_layout_path(asm, s2_donor.S2_FINAL, "WFZ")
    want = "WFZ_1 (REV00).bin" if rev == 0 else "WFZ_1.bin"
    assert path == os.path.join(root, "level", "objects", want)
    # both revisions resolve, to different files, from the same walk
    start = asm.index("\nOff_Objects:")
    r0 = SLL._active_binclude(asm, "Objects_WFZ_1", start, 0)
    r1 = SLL._active_binclude(asm, "Objects_WFZ_1", start, 1)
    assert (r0, r1) == ("level/objects/WFZ_1 (REV00).bin", "level/objects/WFZ_1.bin")
    # the zones the shipped clips already use still resolve to the same files
    for z in ("EHZ", "CPZ"):
        assert SLL.object_layout_path(asm, s2_donor.S2_FINAL, z) == \
            os.path.join(root, "level", "objects", z + "_1.bin")


def test_hpz_prototype_layout_is_objects_layout_row_zone_id_times_two():
    root = _proto_or_skip()
    asm = SLL._s2_asm(s2_donor.S2_PROTOTYPE)
    assert SLL.obj03_id(asm, s2_donor.S2_PROTOTYPE) == 3
    path = SLL.object_layout_path(asm, s2_donor.S2_PROTOTYPE, "HPZ")
    assert path == os.path.join(root, "level", "objects", "HPZ_1.bin")


@pytest.mark.parametrize("donor,zone", [(s2_donor.S2_FINAL, "WFZ"), (s2_donor.S2_FINAL, "OOZ"),
                                        (s2_donor.S2_PROTOTYPE, "HPZ")])
def test_the_new_woven_zones_bake_with_the_lines_their_layouts_carry(donor, zone):
    """Every one of WFZ, OOZ and HPZ accepted over its whole painted width; the line count is
    what an independent reader of the same file finds (MEASURED 2026-09-27: 0 for all three)."""
    (_proto_or_skip if donor == s2_donor.S2_PROTOTYPE else _donor_or_skip)()
    asm = SLL._s2_asm(donor)
    path = SLL.object_layout_path(asm, donor, zone)
    want = sum(1 for _x, _y, i in _independent_ids(path, donor == s2_donor.S2_FINAL) if i == 3)
    p = SLL.plan(_fake_act(donor, zone, (0, 0, 16384 - 2048, 2048)))
    assert len(p["lines"]) == want
    assert want == 0


def test_l6_refuses_a_prototype_obj03_inside_a_clip():
    """The prototype's Green Hill carries EHZ's apex line at (4224, 464) subtype $91; its Obj03
    fires on leaving a band, which the engine does not run."""
    _proto_or_skip()
    act = _fake_act(s2_donor.S2_PROTOTYPE, "GHZ", (4096, 0, 512, 1024))
    with pytest.raises(SLL.LayerLineError, match=r"^L6 GHZ .*Obj03 at \(4224, 464\) subtype \$91"):
        SLL.plan(act)
    # a rectangle clear of every Obj03 is accepted, with no lines
    asm = SLL._s2_asm(s2_donor.S2_PROTOTYPE)
    recs = _independent_ids(SLL.object_layout_path(asm, s2_donor.S2_PROTOTYPE, "GHZ"), False)
    xs = sorted(x for x, _y, i in recs if i == 3)
    gap = next(a for a, b in zip(xs, xs[1:]) if b - a > 600)
    ok = _fake_act(s2_donor.S2_PROTOTYPE, "GHZ", (gap + 16, 0, 512, 1024))
    assert SLL.plan(ok)["lines"] == []


def test_prototype_records_take_xflip_from_bit_14_and_mask_the_remember_bit(tmp_path):
    p = tmp_path / "proto.bin"
    # record 1: bit 14 only (the prototype's x-flip); record 2: bit 13 only (the final game's
    # x-flip, which the prototype's loader does not read as one). id $83 = remember + Obj03.
    p.write_bytes(struct.pack(">HHBB", 100, 0x4000 | 200, 0x83, 0x11)
                  + struct.pack(">HHBB", 300, 0x2000 | 400, 0x03, 0x22))
    assert SLL.read_layout(str(p), s2_donor.S2_PROTOTYPE) == [(100, 200, 1, 3, 0x11),
                                                             (300, 400, 0, 3, 0x22)]
    assert SLL.read_layout(str(p), s2_donor.S2_FINAL) == [(100, 200, 0, 0x83, 0x11),
                                                         (300, 400, 1, 3, 0x22)]


def test_l4_refuses_a_row_outside_the_act():
    c = SLL.engine_constants()
    line = {"order": 0, "zone": "EHZ", "horizontal": False, "x": 9000, "y": 500, "lo": 436,
            "hi": 564, "flags": 0, "xflip": 0, "where": "a line"}
    with pytest.raises(SLL.LayerLineError, match=r"^L4 "):
        SLL.rows([line], 8192, 2048, c)


def test_l5_refuses_a_layout_that_is_not_whole_records(tmp_path):
    p = tmp_path / "bad.bin"
    p.write_bytes(b"\x00" * 7)
    with pytest.raises(SLL.LayerLineError, match=r"^L5 "):
        SLL.read_layout(str(p))


def test_rows_text_carries_both_sentinels_and_every_row(donors):
    _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"), donor_root=donors)
    p = SLL.plan(act)
    text = SLL.rows_text(p)
    assert text.count("LayerLine{") == len(p["rows"]) + 2
    assert text.startswith("LayerLine{ ll_key: $8000,")
    assert "ll_key: $7FFF," in text.splitlines()[-1]


def test_the_bake_reads_its_own_emission_back(donors):
    """clip_rom_bake's LL1 over the text its own emitters write, and a one-row mutation of it."""
    _donor_or_skip()
    import clip_rom_bake as CRB
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"), donor_root=donors)
    plan = {"layer_lines": SLL.plan(act), "zones": [], "rows": []}
    mod = CRB._layer_lines_module_text(plan)
    data = CRB._layer_lines_data_text(plan["layer_lines"])
    assert CRB.check_layer_lines(plan, mod, data) == len(plan["layer_lines"]["rows"])
    bad = data.replace("ll_key: 4224,", "ll_key: 4225,", 1)
    assert bad != data
    with pytest.raises(CRB.ClipRomError, match=r"^LL1 the data block"):
        CRB.check_layer_lines(plan, mod, bad)


def test_the_neutral_module_binds_no_table():
    import clip_rom_bake as CRB
    text = CRB.clip_module_text(None)
    assert "pub const OJZ_CLIP_LAYER_LINE_ROWS: array = []" in text
    # LINES-EVERYWHERE: the neutral chooser hands back `hand`, which is now the canonical
    # act's own authored table (a Label), not 0.
    assert "pub comptime fn ojz_clip_act_layer_lines(hand: Label) -> Label {\n    return hand\n}" in text


# ---- corridor path lines (clip_manifest PATH LINES, WOVEN-CROSSING-PATH 2026-09-27) ----------
#
# The shipped woven manifest's ONE declaration, read out of its raw JSON (the geometry and the
# declaration), placed on a stand-in act so no converted donor tree is needed. Every
# expectation is derived: the subtype from the donor layout, the bits from constants.emp, the
# placement from PATH_LINE_INSET_PX and the corridor's own rect.

WOVEN_JSON = os.path.join(CLIPS, "s2_woven", "clips.json")


def _woven_stand_in(**change):
    """(act, corridor) for the woven act's Metropolis-west | mtz_to_cpz | Chemical Plant row,
    from the shipped clips.json. `change` overrides fields: cpz_src (the crop), path_lines."""
    import json
    from types import SimpleNamespace as NS
    raw = json.load(open(WOVEN_JSON))
    clips = []
    for c in raw["clips"]:
        if c["id"] not in ("mtz_west", "cpz_loop_cluster"):
            continue
        r = lambda k: tuple(c[k][f] for f in ("x", "y", "w", "h"))  # noqa: E731
        src = change.get("cpz_src", r("src_rect")) if c["zone"] == "CPZ" else r("src_rect")
        dst = r("dst_rect")
        clips.append(NS(id=c["id"], donor=c["donor"], zone=c["zone"], src=src,
                        dst=(dst[0], dst[1], src[2], src[3])))
    k = next(k for k in raw["corridors"] if k["id"] == "mtz_to_cpz")
    pls = change.get("path_lines", [{"mouth": p["mouth"], "why": p["why"],
                                     "donor_obj03": (p["donor_obj03"]["x"],
                                                     p["donor_obj03"]["y"])}
                                    for p in k.get("path_lines", [])])
    co = NS(id=k["id"], axis="x", dst=tuple(k["dst_rect"][f] for f in ("x", "y", "w", "h")),
            floor_y=k["floor_y"], tunnel=NS(ceiling_y=k["tunnel"]["ceiling_y"]),
            path_lines=pls)
    act = NS(clips=clips, corridors=[co], section_px=2048,
             grid_w=raw["act"]["grid_w"], grid_h=raw["act"]["grid_h"])
    return act, co


def _decl(x, y, mouth="east"):
    return [{"mouth": mouth, "donor_obj03": (x, y), "why": "test"}]


def test_the_woven_declaration_bakes_to_a_path_a_line_before_chemical_plants_west_mouth():
    _donor_or_skip()
    act, co = _woven_stand_in()
    assert [p["donor_obj03"] for p in co.path_lines] == [(6536, 1152)]
    asm = SLL._s2_asm(s2_donor.S2_FINAL)
    recs = SLL.read_layout(SLL.object_layout_path(asm, s2_donor.S2_FINAL, "CPZ"))
    st = next(r[4] for r in recs if (r[0], r[1]) == (6536, 1152) and r[3] == SLL.obj03_id(asm))
    ls = SLL.connector_lines(act)
    assert len(ls) == 1
    ln = ls[0]
    c = SLL.engine_constants()
    assert ln["subtype"] == st
    assert ln["flags"] == SLL.flags_of(st, 0, c)
    # Sonic 2's path on a rightward crossing is A (subtype bit 3 clear), and that is what the
    # row carries: no FWD_B, no keep bit
    assert not st & 0x08
    assert not ln["flags"] & ((1 << c["LL_FWD_B"]) | (1 << c["LL_KEEP_PATH"]))
    # placed inside the corridor, PATH_LINE_INSET_PX before the east mouth, over its open height
    assert ln["x"] == co.dst[0] + co.dst[2] - SLL.PATH_LINE_INSET_PX
    assert co.dst[0] <= ln["x"] < co.dst[0] + co.dst[2]
    assert (ln["lo"], ln["hi"]) == (co.tunnel.ceiling_y, co.floor_y)
    # and it reaches the rows through the one bake path, after every clip line
    p = SLL.plan(act)
    assert p["lines"][-1]["connector"] == "mtz_to_cpz"
    assert any(r["key"] == ln["x"] and r["flags"] == ln["flags"] for r in p["rows"])


@pytest.mark.parametrize("decl,cpz_src,match", [
    # no Obj03 at that point
    (_decl(6536, 1153), None, r"^L7 .*0 Obj03 record\(s\) there"),
    # an x-flipped (keep-path) Obj03 sets no path
    (_decl(6400, 864), None, r"^L7 .*subtype \$39 is x-flipped"),
    # inside the crop: already baked by lines()
    (_decl(7272, 832), None, r"^L7 .*is not west of clip 'cpz_loop_cluster'"),
    # extent y 768..895 misses the corridor's standing body (donor 1050..1087)
    (_decl(6048, 832), None, r"^L7 .*does not cover the standing body"),
    # crop moved to x 7500: (7408, 1088) $79 now lies between the line and the edge
    (_decl(6536, 1152), (7500, 128, 1716, 1920), r"^L7 .*\(7408, 1088\) subtype \$79 lies between"),
])
def test_l7_refuses_a_declaration_whose_donor_premise_fails(decl, cpz_src, match):
    _donor_or_skip()
    change = {"path_lines": decl}
    if cpz_src:
        change["cpz_src"] = cpz_src
    act, _co = _woven_stand_in(**change)
    with pytest.raises(SLL.LayerLineError, match=match):
        SLL.connector_lines(act)


def test_l7_the_premise_is_necessary_not_sufficient():
    """Why a path line is DECLARED per mouth and never inferred: over every Obj03 of the zone,
    the premise admits the declared Chemical Plant line and nothing else at that mouth, but the
    same premise at Emerald Hill's east edge admits (8968, 576) $11, which WOVEN-CROSSING-PATH
    measured to disagree with the route Sonic 2 actually leaves on. Pinned so an 'infer it for
    every connector' change has to face that row."""
    _donor_or_skip()
    act, co = _woven_stand_in()
    asm = SLL._s2_asm(s2_donor.S2_FINAL)
    recs = [r for r in SLL.read_layout(SLL.object_layout_path(asm, s2_donor.S2_FINAL, "CPZ"))
            if r[3] == SLL.obj03_id(asm)]
    admitted = []
    for r in recs:
        co.path_lines = _decl(r[0], r[1])
        try:
            SLL.connector_lines(act)
        except SLL.LayerLineError:
            continue
        admitted.append((r[0], r[1]))
    assert admitted == [(6536, 1152)]


def test_the_witness_grades_the_declared_arrival_off_the_raw_subtype():
    """path_b_floor_witness --connectors: the declared mtz_to_cpz east line is graded as a
    RIGHTWARD arrival that must be on path A (subtype bit 3 clear), read off the donor subtype,
    not the baked flags; a subtype with bit 3 set would expect B."""
    _donor_or_skip()
    import path_b_floor_witness as W
    act, _co = _woven_stand_in()
    got = W.declared_arrivals(act)
    assert set(got) == {("mtz_to_cpz", "right")}
    assert got[("mtz_to_cpz", "right")][0] == 0
    # a declaration the bake refuses makes the witness COULD NOT RUN, never silently ungraded
    bad, _ = _woven_stand_in(path_lines=_decl(6536, 1153))
    with pytest.raises(W.CouldNotRun):
        W.declared_arrivals(bad)


@pytest.mark.parametrize("raw,match", [
    ([], r"non-empty list"),
    ([{"mouth": "east", "donor_obj03": {"x": 1, "y": 2}}], r"exactly \{mouth, donor_obj03, why\}"),
    ([{"mouth": "north", "donor_obj03": {"x": 1, "y": 2}, "why": "w"}], r"not 'east' or 'west'"),
    ([{"mouth": "east", "donor_obj03": {"x": 1, "y": True}, "why": "w"}], r"\{x, y\} integers"),
    ([{"mouth": "east", "donor_obj03": {"x": 1, "y": 2}, "why": " "}], r"say what admitted"),
    ([{"mouth": "east", "donor_obj03": {"x": 1, "y": 2}, "why": "w"}] * 2, r"a second line"),
])
def test_k11_refuses_a_malformed_path_lines_block(raw, match):
    act, co = _woven_stand_in()
    with pytest.raises(CM.ClipManifestError, match=r"^K11 .*" + match):
        CM._load_path_lines(co.id, raw, co, act.clips, [])


def test_k11_refuses_a_mouth_no_clip_meets():
    act, co = _woven_stand_in()
    clips = [c for c in act.clips if c.zone != "CPZ"]
    with pytest.raises(CM.ClipManifestError, match=r"^K11 .*no clip meets the corridor's east"):
        CM._load_path_lines(co.id, [{"mouth": "east", "donor_obj03": {"x": 1, "y": 2},
                                     "why": "w"}], co, clips, [])
