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
