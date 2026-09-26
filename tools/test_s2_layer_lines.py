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

REPO = os.path.dirname(TOOLS)
CLIPS = os.path.join(REPO, "games", "sonic4", "data", "clips")


def _donor_or_skip():
    try:
        root = s2_donor.donor_root(s2_donor.S2_FINAL)
    except SystemExit as exc:
        pytest.skip("the s2disasm donor checkout is not present: %s" % exc)
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


def test_s2_ehz_cpz_plan_matches_an_independent_reading_of_the_layouts():
    root = _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"))
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


def test_loop_one_is_an_apex_line_then_an_exit_line():
    """What the witness derives its drive expectations from: past x 3950 the first grounded-only
    row is the apex line at 4224 and the next row the exit line at 4368."""
    _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"))
    p = SLL.plan(act)
    import s2clip_layer_line_witness as W
    apex, exit_ = W.loop_lines(p, 3950, "right")
    assert (apex["key"], exit_["key"]) == (4224, 4368)
    apex_l, exit_l = W.loop_lines(p, 4500, "left")
    assert (apex_l["key"], exit_l["key"]) == (4224, 4368)


@pytest.mark.parametrize("clip", ["s2_ehz_cpz", "s2_ehz_boot", "s2_two_clip", "s2_two_clip_pins"])
def test_every_shipped_clip_manifest_bakes(clip):
    _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, clip, "clips.json"))
    p = SLL.plan(act)
    assert p["rows"], "%s has no plane switchers in its rectangles" % clip


def test_l2_refuses_a_line_whose_extent_leaves_the_clip():
    """A real line, a real layout: crop EHZ so the apex line's y extent (400..527) crosses the
    rectangle's bottom edge at 500."""
    _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"))
    cl = act.clips[0]
    cl.src = (4096, 0, 512, 500)
    cl.dst = (4096, 0, 512, 500)
    act.clips = [cl]
    with pytest.raises(SLL.LayerLineError, match=r"^L2 EHZ Obj03 at \(4224, 464\)"):
        SLL.plan(act)


def test_l1_refuses_a_prototype_donor():
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"))
    act.clips[0].donor = s2_donor.S2_PROTOTYPE
    with pytest.raises(SLL.LayerLineError, match=r"^L1 "):
        SLL.plan(act)


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


def test_rows_text_carries_both_sentinels_and_every_row():
    _donor_or_skip()
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"))
    p = SLL.plan(act)
    text = SLL.rows_text(p)
    assert text.count("LayerLine{") == len(p["rows"]) + 2
    assert text.startswith("LayerLine{ ll_key: $8000,")
    assert "ll_key: $7FFF," in text.splitlines()[-1]


def test_the_bake_reads_its_own_emission_back():
    """clip_rom_bake's LL1 over the text its own emitters write, and a one-row mutation of it."""
    _donor_or_skip()
    import clip_rom_bake as CRB
    act = CM.load(os.path.join(CLIPS, "s2_ehz_cpz", "clips.json"))
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
    assert "pub comptime fn ojz_clip_act_layer_lines(hand: int) -> int {\n    return hand\n}" in text
