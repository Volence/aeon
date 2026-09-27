"""S2CLIP-ORIGINAL-BGS B-2: each zone's background scrolls the way Sonic 2 scrolls it.

RUNNER: build.sh's PRE-build tool-suite lane (`pytest tools -m "not needs_build"`), which
`tools/landing_build.sh` runs once per landing. Nothing here reads a build artifact. Every row
reads the donor's own s2.asm and SKIPS SAYING SO when the donor checkout cannot be resolved.
The end-to-end half (the BUILT clip ROM's Hscroll_Buffer against the same model) is
`tools/clip_bg_scroll_witness.py`, a headless run, manual.

WHAT IS HELD HERE, every expectation derived — from s2.asm, by running it, or from the band
table the derivation produced — and none copied from a pin:
  * THE MODEL REPRODUCES SONIC 2. `clip_bg_scroll.engine_bg_words` (the engine's fill, modelled)
    is compared with `run_swscrl_ehz` (s2.asm SwScrl_EHZ, executed) on every line S2 writes:
      - EXACT at camera X = every multiple of the LCM of every band denominator (there no
        shift floors anything, so any difference is a wrong band, factor, ripple phase or
        slope — not rounding);
      - elsewhere within the floor bound the factor ENCODING implies (one pixel per shift
        term, plus the curve's one-pixel Bresenham floor), and on the ramp's HELD lines the
        whole difference is exactly the hold (j lines into a group, j steps of the slope).
  * The ripple is the donor's cycle, at S2's frame-0 phase, on the lines S2 ripples.
  * CPZ's reader refuses by name when the source stops saying what it reads, and when
    InitCam_CPZ and SwScrl_CPZ disagree about a rate.
  * The emitted scene text maps every layer back to the plane line it was derived for
    (scene_plane_line's formula, the one Parallax_Step5_Vscroll applies to the camera).
  * The bake's SC1 check refuses a preset that does not bind its zone's parallax record.
"""

import os
import re
import sys
from fractions import Fraction
from math import ceil, lcm

import pytest

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import clip_bg_scroll as CBS                # noqa: E402
import s2_donor as S                        # noqa: E402
from suite_paths import SuitePathError      # noqa: E402


@pytest.fixture(scope="module")
def s2asm():
    try:
        root = S.donor_root(S.S2_FINAL)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {S.S2_FINAL} donor could not be resolved, so NOTHING in this row is "
                    f"checked: {e}")
    with open(os.path.join(root, "s2.asm"), errors="replace") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def ehz(s2asm):
    return CBS.derive_ehz(s2asm)


def _terms(f):
    return 0 if f[0] == CBS.LOCKED else (1 if f[1] == CBS.LOCKED else 2)


def _exact_period(spec):
    dens = [b["ratio"].denominator for b in spec["bands"]]
    dens += [b["slope"].denominator for b in spec["bands"] if b["kind"] == "ramp"]
    dens += [b["to_ratio"].denominator for b in spec["bands"] if b["kind"] == "ramp"]
    return lcm(*dens)


def _sweep(spec, extra=()):
    """Camera X values across Emerald Hill's clip width (the manifest's), not a round number."""
    return sorted(set(list(range(0, 10976, 61)) + [10975] + list(extra)))


def test_ehz_every_band_is_one_sonic2_store_loop_group(ehz):
    """Structure, read back: bands cover the screen from line 0 in order, each band records the
    s2.asm dbf loop(s) that wrote it, and the engine's last band reaches the screen bottom."""
    bands = ehz["bands"]
    assert bands[0]["top"] == 0
    assert all(a["top"] < b["top"] for a, b in zip(bands, bands[1:]))
    assert all(b["loops"] and all(isinstance(x, int) for x in b["loops"]) for b in bands)
    assert bands[-1]["engine_end"] == CBS.SCREEN_LINES
    assert len(bands) <= CBS.MAX_BANDS
    # every band's factor decodes back to its ratio exactly (encode_factor's contract)
    for b in bands:
        assert CBS.factor_value(*b["factor"]) == b["ratio"]
        if b["kind"] == "ramp":
            assert CBS.factor_value(*b["to_factor"]) == b["to_ratio"]


def test_ehz_model_is_exact_where_no_shift_rounds(s2asm, ehz):
    period = _exact_period(ehz)
    xs = [k * period for k in range(0, 10976 // period + 1)]
    assert len(xs) >= 8, f"the exact-period sweep has {len(xs)} points; it proves little"
    for c in xs:
        rows, _ = CBS.run_swscrl_ehz(s2asm, c)
        eng = CBS.engine_bg_words(ehz, c)
        for k, b in enumerate(ehz["bands"]):
            starts = set(CBS.group_starts(b)) if b["kind"] == "ramp" else None
            for line in range(b["top"], b["engine_end"]):
                if rows[line] is None:
                    continue
                s2 = CBS._sx(rows[line][1], 16)
                if starts is None:
                    assert eng[line] == s2, (f"camX {c} line {line} ({b['kind']} band {k}): "
                                             f"engine {eng[line]} vs Sonic 2 {s2}")
                else:
                    g = max(s for s in starts if s <= line)
                    held = (line - g) * b["slope"] * c
                    assert held.denominator == 1
                    assert eng[line] == s2 - int(held), (
                        f"camX {c} line {line}: engine {eng[line]} vs Sonic 2 {s2}; the only "
                        f"allowed difference on a held line is the hold, {line - g} step(s)")


def test_ehz_model_is_within_the_encoding_floor_bound_everywhere(s2asm, ehz):
    worst, unwritten = CBS.compare(s2asm, ehz, _sweep(ehz))
    for k, b in enumerate(ehz["bands"]):
        bound = _terms(b["factor"]) + (_terms(b["to_factor"]) + 1 if b["kind"] == "ramp" else 0)
        assert worst[k][0] <= bound, (f"band {k} ({b['kind']}, top {b['top']}): worst "
                                      f"{worst[k][0]} px on new-value lines, bound {bound}")
        if b["kind"] != "ramp":
            assert worst[k][1] == 0
        else:
            hold = max(b["holds"]) - 1
            assert worst[k][1] <= hold * ceil(10975 * b["slope"]) + bound
    # the lines S2 never writes are exactly the tail below its last loop, inside the last band
    assert unwritten == list(range(ehz["written_lines"], CBS.SCREEN_LINES))
    assert all(line >= ehz["bands"][-1]["top"] for line in unwritten)


def test_ehz_ripple_is_the_donor_cycle_at_frame_zero_phase(s2asm, ehz):
    """Run S2 at camera X 0 (every other term vanishes) with and without its ripple table:
    the difference is the ripple S2 adds on each line. The engine's table sample on that
    line must equal it, and the engine must add nothing on any other line."""
    rows, _ = CBS.run_swscrl_ehz(s2asm, 0)
    n = len(CBS._dc_bytes(s2asm.split("\n"), "SwScrl_RippleData"))
    zero, _ = CBS.run_swscrl_ehz(s2asm, 0, ripple_override=[0] * n)
    eng = CBS.engine_bg_words(ehz, 0)
    rippled = 0
    for line in range(CBS.SCREEN_LINES):
        if rows[line] is None:
            continue
        s2 = CBS._sx(rows[line][1], 16) - CBS._sx(zero[line][1], 16)
        assert eng[line] == s2, f"line {line}: engine ripple {eng[line]}, Sonic 2 {s2}"
        rippled += s2 != 0
    assert rippled, "no line rippled at camera X 0 — the check cannot fail"


def test_ripple_table_is_the_cycle_repeated(s2asm):
    table, cycle = CBS.ripple_table(s2asm)
    lines = s2asm.split("\n")
    raw = CBS._dc_bytes(lines, "SwScrl_RippleData")
    assert len(table) == 256 and 256 % cycle == 0
    assert [CBS._sx(v, 8) for v in raw[:cycle]] == table[:cycle]
    assert all(table[i] == table[i % cycle] for i in range(256))


@pytest.mark.parametrize("dy", [0, 256, 512])
def test_cpz_layers_map_back_to_the_rows_sonic2_keys_on(s2asm, dy):
    spec = CBS.derive_cpz(s2asm, dy)
    block, special = spec["block"], spec["special_block"]
    assert [b["plane_top"] for b in spec["bands"]] == [0, special * block, (special + 1) * block]
    assert [b["kind"] for b in spec["bands"]] == ["flat", "ripple", "flat"]
    for b in spec["bands"]:
        wy = CBS.layer_world_y(spec, b["plane_top"])
        # scene_plane_line(): ((world_y - v_center) >> v_factor) + v_offset
        assert ((wy - spec["v_center"]) >> spec["v_factor"]) + spec["v_offset"] == b["plane_top"]
    # the ripple band's first ROW reads cycle entry 0: index = phase + vscroll + line = phase + row
    rb = spec["bands"][1]
    assert (rb["phase"] + rb["plane_top"]) % spec["ripple_cycle"] == 0
    # the vertical rate is InitCam_CPZ's
    assert spec["v_factor"] == int(re.search(r"InitCam_CPZ:\s*\n\s*lsr\.w\s+#(\d+),d0",
                                             s2asm).group(1))


def _mutate_cpz(text, needle, repl):
    """Replace EVERY occurrence of `needle` inside SwScrl_CPZ only (s2.asm has other zones'
    routines with the same instructions)."""
    start = text.index("\nSwScrl_CPZ:")
    end = text.index("\nSwScrl_DEZ:", start)
    body = text[start:end]
    assert needle in body, f"the mutation's target {needle!r} is gone from SwScrl_CPZ — re-derive"
    return text[:start] + body.replace(needle, repl) + text[end:]


@pytest.mark.parametrize("needle,repl,why", [
    ("cmpi.b\t#18,d4", "cmpi.b\t#18,d5", "special-block"),
    ("\tasl.l\t#6,d5", "\tasl.l\t#5,d5", "disagree"),
    ("\tlsr.w\t#4,d0\n\tlea\t(a0,d0.w),a0", "\tlsr.w\t#3,d0\n\tlea\t(a0,d0.w),a0", None),
])
def test_cpz_reader_refuses_a_source_that_stops_saying_what_it_reads(s2asm, needle, repl, why):
    CBS.derive_cpz(s2asm, 256)                                     # control
    mutated = _mutate_cpz(s2asm, needle, repl)
    if why is None:
        # a different block height is not an error — it must MOVE the bands, not be ignored
        spec = CBS.derive_cpz(mutated, 256)
        assert spec["block"] == 8 and spec["bands"][1]["plane_top"] == 18 * 8
        return
    with pytest.raises(CBS.ClipScrollError, match=why):
        CBS.derive_cpz(mutated, 256)


# ---- METROPOLIS (woven first screen s2_mtz_cpz, 2026-09-27) --------------------------------
# Red before derive_mtz: derive("MTZ") returned None, the act kept the act-default scroll, and
# crossing_witness counted 13-16 "mid-lerp" glitch ticks per arrival in Metropolis.

@pytest.mark.parametrize("dy", [0, 448])
def test_mtz_is_one_flat_band_at_initcam_stds_rates(s2asm, dy):
    spec = CBS.derive("s2disasm", "MTZ", dy)
    assert spec is not None and spec["routine"] == "SwScrl_MTZ"
    m = re.search(r"InitCam_Std:\s*\n\s*asr\.w\s+#(\d+),d0\s*\n\s*move\.w\s+d0,\(Camera_BG_Y_pos\)"
                  r"\.w\s*\n\s*asr\.w\s+#(\d+),d1", s2asm)
    v_shift, x_shift = int(m.group(1)), int(m.group(2))
    assert (spec["v_factor"], spec["v_center"]) == (v_shift, dy)
    assert [(b["kind"], b["plane_top"], b["ratio"]) for b in spec["bands"]] == \
        [("flat", 0, Fraction(1, 1 << x_shift))]
    assert CBS.factor_value(*spec["bands"][0]["factor"]) == Fraction(1, 1 << x_shift)


def _mutate_mtz(text, needle, repl):
    start = text.index("\nSwScrl_MTZ:")
    end = text.index("\nSwScrl_WFZ:", start)
    body = text[start:end]
    assert needle in body, f"the mutation's target {needle!r} is gone from SwScrl_MTZ — re-derive"
    return text[:start] + body.replace(needle, repl) + text[end:]


@pytest.mark.parametrize("needle,repl,why", [
    ("\tasl.l\t#5,d4", "\tasl.l\t#4,d4", "disagree"),
    ("\tmove.w\t#224-1,d1", "\tmove.w\t#112-1,d1", "one-value store"),
])
def test_mtz_reader_refuses_a_source_that_stops_saying_what_it_reads(s2asm, needle, repl, why):
    CBS.derive_mtz(s2asm, 448)                                     # control
    with pytest.raises(CBS.ClipScrollError, match=why):
        CBS.derive_mtz(_mutate_mtz(s2asm, needle, repl), 448)


def test_scene_text_carries_every_derived_layer(s2asm, ehz):
    cpz = CBS.derive_cpz(s2asm, 256)
    for spec in (ehz, cpz):
        txt = CBS.scene_text(spec, "X", CBS.TABLE_LABEL)
        layers = re.findall(r"layer\(world_y: (\d+), fa: packed\(s1: 0, s2: 15, op: 0\), "
                            r"fb: packed\(s1: (\d+), s2: (\d+), op: (\d)\)([^)]*\)?)", txt)
        assert len(layers) == len(spec["bands"])
        for (wy, s1, s2, op, rest), b in zip(layers, spec["bands"]):
            assert int(wy) == CBS.layer_world_y(spec, b["plane_top"])
            assert (int(s1), int(s2), int(op)) == b["factor"]
            assert ("dsb: 0" in rest) == (b["kind"] == "ripple")
        assert txt.count("no_layer()") == CBS.MAX_BANDS - len(spec["bands"])
        assert f"count: {len(spec['bands'])}," in txt


def test_encode_factor_refuses_what_the_engine_cannot_decode():
    assert CBS.encode_factor(Fraction(3, 32)) == (4, 5, 0)
    assert CBS.factor_value(*CBS.encode_factor(Fraction(3, 4))) == Fraction(3, 4)
    with pytest.raises(CBS.ClipScrollError):
        CBS.encode_factor(Fraction(1, 3))
    with pytest.raises(CBS.ClipScrollError):
        CBS.encode_factor(Fraction(11, 32))


# ---------------------------------------------------------------------------
# SC1 — the bake's read-back of the presets it emitted
# ---------------------------------------------------------------------------

def _sc1_plan(s2asm, ehz):
    zones = []
    for key, (zone, spec) in enumerate((("EHZ", ehz), ("CPZ", CBS.derive_cpz(s2asm, 256)))):
        zones.append({"key": key, "donor": S.S2_FINAL, "zone": zone, "scroll": spec,
                      "preset_label": f"OJZ_Clip_Preset_{key}",
                      "palette_label": f"OJZ_Clip_Palette_{key}",
                      "parallax_label": CBS.PARALLAX_LABEL.format(key=key)})
    return {"act_span": 6144, "zones": zones}


def _sc1_text(plan, bind=None):
    import clip_rom_bake as CRB
    out = [CBS.data_block_text(CRB._scroll_zones(plan), plan["act_span"])]
    for z in plan["zones"]:
        lab = z["parallax_label"] if bind is None else bind.get(z["key"], z["parallax_label"])
        out.append(f"pub data {z['preset_label']}: EffectsPreset = preset(pal: "
                   f"{z['palette_label']}, " + (f"parallax: {lab}, " if lab else "")
                   + "raster: Raster_Program_None, cycle: Pal_Cycle_None, transition: 1)\n")
    return "".join(out)


def test_sc1_accepts_each_preset_binding_its_own_record(s2asm, ehz):
    import clip_rom_bake as CRB
    plan = _sc1_plan(s2asm, ehz)
    assert CRB.check_scroll(plan, _sc1_text(plan)) == {
        "EHZ": len(ehz["bands"]), "CPZ": len(plan["zones"][1]["scroll"]["bands"])}


@pytest.mark.parametrize("bind,frag", [
    ({1: None}, "binds parallax none"),
    ({0: "OJZ_Clip_Parallax_1", 1: "OJZ_Clip_Parallax_0"}, "its zone's own record"),
])
def test_sc1_refuses_a_preset_bound_to_the_wrong_record(s2asm, ehz, bind, frag):
    import clip_rom_bake as CRB
    plan = _sc1_plan(s2asm, ehz)
    with pytest.raises(CRB.ClipRomError, match=frag):
        CRB.check_scroll(plan, _sc1_text(plan, bind))


def test_sc1_refuses_a_scroll_block_that_is_not_a_fresh_derivation(s2asm, ehz):
    import clip_rom_bake as CRB
    plan = _sc1_plan(s2asm, ehz)
    text = _sc1_text(plan)
    wrong = text.replace("fb: packed(s1: 6, s2: 15, op: 0)", "fb: packed(s1: 5, s2: 15, op: 0)", 1)
    assert wrong != text, "the mutation found nothing to change — re-derive its target"
    with pytest.raises(CRB.ClipRomError, match="fresh derivation"):
        CRB.check_scroll(plan, wrong)


# ---- OIL OCEAN, HIDDEN PALACE, WING FORTRESS (woven prep, 2026-09-27) -----------------------
# Before this, derive() returned None for all three (the act default's scroll) and
# clip_bg_lower refused WFZ and HPZ outright.

@pytest.fixture(scope="module")
def protoasm():
    try:
        root = S.donor_root(S.S2_PROTOTYPE)
    except (SystemExit, SuitePathError) as e:
        pytest.skip(f"the {S.S2_PROTOTYPE} donor could not be resolved, so NOTHING in this row "
                    f"is checked: {e}")
    with open(os.path.join(root, "main.asm"), errors="replace") as fh:
        return fh.read()


def _ooz_prog(s2asm):
    lines = CBS._lines(s2asm)
    s, e = CBS._span(lines, "SwScrl_OOZ", "")
    return CBS._assemble(lines, s, e, CBS._fixbugs(lines)), CBS._dc_bytes(lines, "SwScrl_RippleData")


def test_ooz_model_reproduces_swscrl_ooz_on_every_line(s2asm):
    """SwScrl_OOZ RUN at every 16th BG Y it can reach inside the plane and a sweep of camera X,
    against the engine model of the derived scene: the ripple (sun) lines EXACT, the flat
    lines within the one pixel of floor the shift order implies (S2 shifts -BG_X, the engine
    shifts +camX), and exact at camera X multiples of 128 (no shift floors anything there)."""
    spec = CBS.derive("s2disasm", "OOZ", 0)
    assert spec["window_top"] == 0 and spec["table_label"] == CBS.TABLE_LABEL + "_Rev"
    prog, ripple = _ooz_prog(s2asm)
    tab = {"SwScrl_RippleData": [v & 0xFF for v in ripple]}
    lo = spec["v_offset"]
    for bgy in list(range(lo, CBS.PLANE_LINES - CBS.SCREEN_LINES + 1, 16)) + [CBS.PLANE_LINES - CBS.SCREEN_LINES]:
        for camx in list(range(0, 12288, 331)) + [128 * 37, 128 * 81]:
            s2 = CBS._ooz_run(prog, tab, camx, camx >> 3, bgy)
            eng = CBS.engine_bg_words(spec, camx, vscroll=bgy - spec["window_top"])
            for line in range(CBS.SCREEN_LINES):
                row = bgy + line
                b = [x for x in spec["bands"] if x["plane_top"] <= row][-1]
                d = abs(eng[line] - s2[row])
                if b["kind"] == "ripple" or camx % 128 == 0:
                    assert d == 0, (bgy, camx, line, eng[line], s2[row])
                else:
                    assert d <= 1, (bgy, camx, line, eng[line], s2[row])


def test_ooz_bands_are_its_cloud_rows_and_sun(s2asm):
    spec = CBS.derive("s2disasm", "OOZ", 0)
    rows = [(b["plane_top"], b["kind"], b["ratio"]) for b in spec["bands"]]
    assert rows[0] == (spec["v_offset"], "flat", Fraction(1, 8))       # empty sky, camX/8
    assert rows[-1][1:] == ("flat", Fraction(1, 8))                     # the factory
    assert [r for r in rows if r[1] == "ripple"] == [(192, "ripple", 0)]  # the sun, 33 rows
    assert {r[2] for r in rows if r[1] == "flat"} == {Fraction(1, n) for n in (8, 32, 64, 128)}
    assert spec["approximations"] == []
    # the first band's top maps back to world Y v_center: the lowest reachable plane line
    assert CBS.layer_world_y(spec, spec["bands"][0]["plane_top"]) == spec["v_center"]


def test_hpz_table_half_and_writer_cover_its_background(protoasm):
    """The run table has one entry per 16-line block, and those blocks are the prototype
    background's painted height exactly (HPZ_BG.bin, via Off_Level)."""
    raw = CBS.derive_hpz_raw(protoasm)
    grid = S.load_bg_grid("HPZ", S.S2_PROTOTYPE)
    assert raw["blocks"] * raw["block"] == grid.shape[0] * 128
    assert raw["v_factor"] == 1 and raw["x_shift"] == 2


def test_hpz_bands_are_its_table_and_the_approximations_are_named(protoasm):
    raw = CBS.derive_hpz_raw(protoasm)
    spec = CBS.derive("s2-simonwai-disasm", "HPZ", 0)
    for b in spec["bands"]:
        s2 = raw["kinds"][b["plane_top"]][1]
        got = CBS.factor_value(*b["factor"])
        if b.get("s2_ratio") is None:
            assert got == s2
        else:
            assert b["s2_ratio"] == s2 and got != s2
            # nothing the engine can decode is nearer: an independent brute force over every
            # (s1, s2, op) the decoder accepts
            everything = {CBS.factor_value(a, c, o) for a in range(15)
                          for c in [CBS.LOCKED] + list(range(a + 1, 15))
                          for o in ((0,) if c == CBS.LOCKED else (0, 1))}
            assert abs(got - s2) == min(abs(v - s2) for v in everything)
    approx = {a["s2_ratio"] for a in spec["approximations"]}
    for r in {k[1] for k in raw["kinds"].values()}:
        try:
            CBS.encode_factor(r)
            assert r not in approx
        except CBS.ClipScrollError:
            if any(b.get("s2_ratio") == r for b in spec["bands"]):
                assert r in approx
    assert {Fraction(57, 128), Fraction(50, 128), Fraction(43, 128)} == approx


def test_wfz_bands_are_the_segment_array_as_drift_rows(s2asm):
    raw = CBS.derive_wfz_raw(s2asm)
    r0 = __import__("clip_bg_lower").window_top("s2disasm", "WFZ")
    spec = CBS.derive("s2disasm", "WFZ", -256)
    assert spec["window_top"] == r0 == 896
    assert (spec["v_factor"], spec["v_offset"], spec["v_center"]) == (0, -r0, -256)
    # an independent reading: the three addi.l longs in order are TempArray +8, +$C, +$10,
    # each 16.16 px/frame, i.e. value / 256 in the engine's 1/256 px unit
    adds = [int(v, 16) for v in re.findall(
        r"addi\.l\t#\$([0-9A-F]+),\(a2\)\+", s2asm[s2asm.index("\nSwScrl_WFZ:"):
                                                 s2asm.index("\nSwScrl_WFZ_Transition_Array:")])]
    rate_of = {8: adds[0] // 256, 12: adds[1] // 256, 16: adds[2] // 256}
    assert sorted(rate_of.values()) == [32, 64, 128]
    # and the segment array, read again here: (count, index) pairs from BG row 0
    arr = s2asm[s2asm.index("\nSwScrl_WFZ_Normal_Array:"):]
    arr = arr[:arr.index("\n; ====")]
    idx_of, row = {}, 0
    for n, i in re.findall(r"dc\.b\s+\$?([0-9A-F]+),\s*\$?([0-9A-F]+)", arr.split("if fixBugs")[0]):
        for r in range(row, row + int(n, 16)):
            idx_of[r] = int(i, 16)
        row += int(n, 16)
    for pl in range(CBS.PLANE_LINES):
        b = [x for x in spec["bands"] if x["plane_top"] <= pl][-1]
        i = idx_of[pl + r0]
        if i in rate_of:
            assert (b["factor"], b["drift"]) == ((CBS.LOCKED, CBS.LOCKED, 0), rate_of[i])
        else:
            assert CBS.factor_value(*b["factor"]) == 1 and not b.get("drift")
    assert raw["arrays"]["Normal"][r0] == ("drift", rate_of[idx_of[r0]])
    txt = CBS.scene_text(spec, "X", CBS.TABLE_LABEL)
    assert txt.count("drift: SceneDrift.Rate(") == len(spec["bands"])


@pytest.mark.parametrize("zone,needle,repl,why", [
    ("OOZ", "\tlsr.w\t#3,d0\n\taddi.w\t#$50,d0", "\tlsr.w\t#2,d0\n\taddi.w\t#$50,d0", "disagrees"),
    ("WFZ", "\taddi.l\t#$8000,(a2)+", "\taddi.l\t#$8001,(a2)+", "whole"),
    ("WFZ", "\tmove.l\t(Camera_X_pos).w,(Camera_BG_X_pos).w", "\tclr.l\t(Camera_BG_X_pos).w",
     "copy the camera"),
])
def test_new_readers_refuse_a_source_that_stops_saying_what_they_read(s2asm, zone, needle,
                                                                       repl, why):
    fn = {"OOZ": CBS.derive_ooz_raw, "WFZ": CBS.derive_wfz_raw}[zone]
    fn(s2asm)                                                       # control
    assert needle in s2asm, f"the mutation's target {needle!r} is gone — re-derive"
    with pytest.raises(CBS.ClipScrollError, match=why):
        fn(s2asm.replace(needle, repl, 1))


def test_hpz_reader_refuses_a_writer_it_does_not_recognise(protoasm):
    CBS.derive_hpz_raw(protoasm)                                    # control
    needle = "\t\tandi.w\t#$F,d2\n\t\tadd.w\td2,d2"
    assert needle in protoasm
    with pytest.raises(CBS.ClipScrollError, match="loc_6AA8"):
        CBS.derive_hpz_raw(protoasm.replace(needle, "\t\tandi.w\t#$7,d2\n\t\tadd.w\td2,d2", 1))


def test_every_windowed_zone_keeps_its_start_view_inside_the_plane():
    import clip_bg_lower as L
    for donor, zone in (("s2disasm", "OOZ"), ("s2disasm", "WFZ"), ("s2-simonwai-disasm", "HPZ")):
        try:
            S.donor_root(donor)
        except (SystemExit, SuitePathError):
            pytest.skip(f"{donor} unresolved")
        raw = CBS.derive(donor, zone, 0, r0=0)
        _x, y = S.start_position(zone, donor)
        top = CBS.bg_row_at(raw, max(0, y - 0x60))
        r0 = L.window_top(donor, zone)
        assert r0 <= top and top + CBS.SCREEN_LINES <= r0 + CBS.PLANE_LINES, (zone, top, r0)
    for zone in ("EHZ", "CPZ", "MTZ", "OOZ"):
        assert L.window_top("s2disasm", zone) == 0


def test_data_block_emits_one_table_per_direction(s2asm, ehz):
    ooz = CBS.derive("s2disasm", "OOZ", 0)
    txt = CBS.data_block_text([(0, ehz), (1, ooz)], 4096)
    assert f"pub data {CBS.TABLE_LABEL}: [i8; 256]" in txt
    assert f"pub data {CBS.TABLE_LABEL}_Rev: [i8; 256]" in txt
    fwd = [int(v) for v in re.search(rf"pub data {CBS.TABLE_LABEL}: \[i8; 256\] = \[(.*?)\]",
                                     txt, re.S).group(1).replace("\n", "").split(",")]
    rev = [int(v) for v in re.search(rf"pub data {CBS.TABLE_LABEL}_Rev: \[i8; 256\] = \[(.*?)\]",
                                     txt, re.S).group(1).replace("\n", "").split(",")]
    assert all(rev[k] == fwd[(-k) % 256] for k in range(256))
    assert f"deform_bg: SceneDeform.Shared({CBS.TABLE_LABEL}_Rev, 0)" in txt
