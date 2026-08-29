#!/usr/bin/env python3
"""Tests for the collision height/angle consistency gate.

Run by `python3 -m pytest tools -q` — which build.sh runs BUILD-FATALLY (see the
pytest lane around build.sh:463). That, plus build.sh's direct invocation of
tools/collision_consistency.py, are the two named runners for this gate.

NEVER write into the repo from here (tools/test_import_sk_collision.py:14 records
the incident that rule exists for): every test either works on synthetic grids in
memory or reads committed files read-only.

The synthetic tests are the RED-FIRST evidence for the two rules in a form that
stays red-able after the real data is repainted. The two real-data tests pin the
gate to the actual tree.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import collision_consistency as cc
import repaint_ojz_collision as rp

FULL = [16] * 16
AIR_PROFILE = [0] * 16
SOLID_TOP = 1
SOLID_ALL = 3


def _tables(spec):
    """spec = {attr: (profile, angle, solidity)} -> the three parallel tables."""
    heights = [[0] * 16 for _ in range(cc.MAX_ATTRS)]
    angles = [0] * cc.MAX_ATTRS
    solidity = [0] * cc.MAX_ATTRS
    for idx, (prof, ang, sol) in spec.items():
        heights[idx] = list(prof)
        angles[idx] = ang
        solidity[idx] = sol
    return heights, angles, solidity


def _grid(rows, cols, cells):
    """cells = {(row, col): attr}."""
    g = [[0] * cols for _ in range(rows)]
    for (r, c), a in cells.items():
        g[r][c] = a
    return g


# ---------------------------------------------------------------------------
# Pure predicates
# ---------------------------------------------------------------------------

def test_is_full_block():
    assert cc.is_full_block(FULL)
    assert not cc.is_full_block(AIR_PROFILE)
    assert not cc.is_full_block([16] * 15 + [0])       # shape 114 X-flipped
    assert not cc.is_full_block([16] * 15)             # wrong length


def test_is_flat_angle_permits_zero_and_the_odd_sentinel():
    assert cc.is_flat_angle(0x00)
    # Odd bytes are the "no usable angle" sentinel: Player_SensorFloor does
    # `btst #0 / bne .substitute` before the value is ever used as a direction.
    # S&K's own full block is shape 255, angle $FF, used 11,493 times.
    assert cc.is_flat_angle(0xFF)
    assert cc.is_flat_angle(0x01)
    # Even non-zero is a positive claim of slope.
    assert not cc.is_flat_angle(0xE0)
    assert not cc.is_flat_angle(0x20)
    assert not cc.is_flat_angle(0x40)


# ---------------------------------------------------------------------------
# RULE A — flat run cannot be a slope
# ---------------------------------------------------------------------------

def test_rule_a_fires_on_a_flat_run_claiming_45_degrees():
    """RED: 6 columns (48 px) of floor-exposed full block carrying angle $E0."""
    heights, angles, solidity = _tables({1: (FULL, 0xE0, SOLID_ALL)})
    grid = _grid(4, 10, {(2, c): 1 for c in range(6)})
    v, stats = cc.find_flat_run_violations(grid, heights, angles, solidity,
                                           SOLID_TOP)
    assert len(v) == 1
    assert v[0]["columns"] == 6
    assert v[0]["width_px"] == 48
    assert v[0]["angles"] == {0xE0: 6}
    assert stats["exposed_full_cells"] == 6


@pytest.mark.parametrize("angle", [0x00, 0xFF, 0x01, 0x7F])
def test_rule_a_permits_flat_and_odd_angles(angle):
    """GREEN: the same long run is fine at angle $00 or any odd sentinel."""
    heights, angles, solidity = _tables({1: (FULL, angle, SOLID_ALL)})
    grid = _grid(4, 10, {(2, c): 1 for c in range(8)})
    v, _ = cc.find_flat_run_violations(grid, heights, angles, solidity, SOLID_TOP)
    assert v == []


def test_rule_a_permits_an_isolated_45_degree_corner_block():
    """The over-strictness guard, and the reason RUN_MIN_COLUMNS exists.

    S&K ships four full-block shapes with even 45-degree angles (251 $E0,
    252 $20, 253 $A0, 254 $60) and uses them 184 times across its 28 zones as
    isolated corner/loop fillers. A single 16 px placement is 2 collision
    columns, below the 4-column threshold, so it must NOT be refused.
    """
    heights, angles, solidity = _tables({1: (FULL, 0xE0, SOLID_ALL)})
    for width in (1, 2, 3):
        grid = _grid(4, 10, {(2, c): 1 for c in range(width)})
        v, _ = cc.find_flat_run_violations(grid, heights, angles, solidity,
                                           SOLID_TOP)
        assert v == [], f"a {width}-column corner block must be permitted"
    # ...but two adjacent shape placements (4 columns) are provably horizontal.
    grid = _grid(4, 10, {(2, c): 1 for c in range(4)})
    v, _ = cc.find_flat_run_violations(grid, heights, angles, solidity, SOLID_TOP)
    assert len(v) == 1


def test_rule_a_exempts_buried_blocks():
    """probe_core's `.full_back` only keeps the PRIMARY cell's angle when the
    cell above is air for the floor class. A buried full block never supplies
    its angle to a floor probe, so its angle is not this gate's business."""
    heights, angles, solidity = _tables({1: (FULL, 0xE0, SOLID_ALL)})
    cells = {}
    for c in range(8):
        cells[(1, c)] = 1        # roof
        cells[(2, c)] = 1        # buried underneath it
    grid = _grid(4, 10, cells)
    v, _ = cc.find_flat_run_violations(grid, heights, angles, solidity, SOLID_TOP)
    # Only the exposed roof row is judged; it is the one that violates.
    assert len(v) == 1
    assert v[0]["row"] == 1


def test_rule_a_ignores_cells_that_fail_the_floor_class():
    """SOLID_LRB-only cells never pass the floor sensor's class mask."""
    heights, angles, solidity = _tables({1: (FULL, 0xE0, 2)})   # SOLID_LRB
    grid = _grid(4, 10, {(2, c): 1 for c in range(8)})
    v, stats = cc.find_flat_run_violations(grid, heights, angles, solidity,
                                           SOLID_TOP)
    assert v == []
    assert stats["exposed_full_cells"] == 0


# ---------------------------------------------------------------------------
# RULE B — pinholes
# ---------------------------------------------------------------------------

def test_rule_b_fires_on_the_shape_114_one_pixel_hole():
    """RED: S&K shape 114 X-flipped is [16 x15, 0] — a floor with a 1 px hole
    at every world X = 15 (mod 16)."""
    holed = [16] * 15 + [0]
    heights, angles, solidity = _tables({1: (holed, 0x01, SOLID_TOP)})
    grid = _grid(2, 8, {(1, c): 1 for c in range(8)})       # 64 px of floor
    v, stats = cc.find_pinhole_violations(grid, heights, solidity, SOLID_TOP, 18)
    assert v, "a 1 px hole in the middle of a floor must be reported"
    assert all(x["gap_px"] == 1 for x in v)
    # Holes sit at world X = 15 (mod 16); the run's final hole is at the very
    # edge of the span and is an edge, not an enclosed hole.
    assert all(x["x_start"] % 16 == 15 for x in v)
    assert stats["floor_pixels"] > 0


def test_rule_b_permits_a_real_ledge():
    """GREEN: a gap at or beyond the sensor pair separation is a real ledge."""
    heights, angles, solidity = _tables({1: (FULL, 0x00, SOLID_TOP)})
    # floor, 24 px gap (3 columns), floor
    cells = {(0, c): 1 for c in list(range(4)) + list(range(7, 12))}
    grid = _grid(1, 12, cells)
    v, _ = cc.find_pinhole_violations(grid, heights, solidity, SOLID_TOP, 18)
    assert v == []


def test_rule_b_threshold_is_the_sensor_pair_separation():
    """A 17 px gap is invisible to the 18 px pair; an 18 px gap is not."""
    heights, angles, solidity = _tables({
        1: (FULL, 0x00, SOLID_TOP),
        2: ([0] * 15 + [16], 0x00, SOLID_TOP),   # solid only at x&15 == 15
    })
    for gap_cols, expect in ((2, True), (3, False)):
        cells = {(0, c): 1 for c in range(4)}
        cells.update({(0, c): 1 for c in range(4 + gap_cols, 4 + gap_cols + 4)})
        grid = _grid(1, 16, cells)
        v, _ = cc.find_pinhole_violations(grid, heights, solidity, SOLID_TOP, 18)
        assert bool(v) is expect, f"{gap_cols * 8} px gap: expected fires={expect}"


def test_rule_b_ignores_gaps_running_off_the_section_edge():
    heights, angles, solidity = _tables({1: (FULL, 0x00, SOLID_TOP)})
    grid = _grid(1, 12, {(0, c): 1 for c in range(4, 8)})
    v, _ = cc.find_pinhole_violations(grid, heights, solidity, SOLID_TOP, 18)
    assert v == []


# ---------------------------------------------------------------------------
# Loud-on-unmeasurable
# ---------------------------------------------------------------------------

def test_read_emp_const_derives_from_the_engine_source():
    assert cc.read_emp_const(cc.CONSTANTS_EMP, "PLAYER_X_RADIUS") == 9
    assert cc.read_emp_const(cc.CONSTANTS_EMP, "SOLID_TOP") == 1


def test_read_emp_const_refuses_to_fall_back():
    with pytest.raises(cc.GateError):
        cc.read_emp_const(cc.CONSTANTS_EMP, "NO_SUCH_CONSTANT_EXISTS")
    with pytest.raises(cc.GateError):
        cc.read_emp_const("/nonexistent/constants.emp", "PLAYER_X_RADIUS")


def test_gate_refuses_an_empty_population(tmp_path):
    """GATE-VACUITY: 'passed because there was nothing there' must be impossible
    to mistake for 'passed because the content is correct'."""
    empty = tmp_path / "gen"
    empty.mkdir()
    with pytest.raises(cc.GateError) as exc:
        cc.check(gen_dir=str(empty))
    assert "ZERO" in str(exc.value)

    with pytest.raises(cc.GateError):
        cc.enumerate_sections(str(tmp_path / "does_not_exist"))


def test_baseline_rejects_a_malformed_file(tmp_path):
    bad = tmp_path / "b.json"
    bad.write_text("{}")
    with pytest.raises(cc.GateError):
        cc.load_baseline(str(bad))
    bad.write_text("not json")
    with pytest.raises(cc.GateError):
        cc.load_baseline(str(bad))


def test_violation_key_excludes_the_attr_index():
    """The attr-set is content-addressed and renumbers on every bake (the same
    bad cell is $02 in the owner's tree and $0E in this one), so an attr in the
    key would let a re-bake silently un-exempt entries."""
    v = {"section": 0, "plane": "A", "row": 16, "col_start": 112, "col_end": 127,
         "columns": 16, "angles": {0xE0: 16}, "attrs": [0x0E]}
    k = cc.violation_key(v, "A")
    assert 0x0E not in k
    v2 = dict(v, attrs=[0x02])
    assert cc.violation_key(v2, "A") == k


# ---------------------------------------------------------------------------
# Real committed data
# ---------------------------------------------------------------------------

def test_committed_tree_has_no_violation_outside_the_baseline():
    """The same assertion build.sh makes. Fails the moment new bad collision
    data lands, whatever attr index the bake gives it."""
    baseline = cc.load_baseline(os.path.join(cc.ROOT, "tools",
                                             "collision_baseline.json"))
    va, vb, pop = cc.check()
    assert pop["nonair_cells"] > 0
    new = [v for v in va
           if tuple(map(cc._hashable, cc.violation_key(v, "A"))) not in baseline]
    new += [v for v in vb
            if tuple(map(cc._hashable, cc.violation_key(v, "B"))) not in baseline]
    assert new == [], f"{len(new)} collision violation(s) not in the baseline: {new}"


def test_baseline_has_no_stale_entries():
    """The ratchet only tightens if cleared entries are removed. When this fails
    after a repaint, DELETE the listed entries from tools/collision_baseline.json.
    """
    path = os.path.join(cc.ROOT, "tools", "collision_baseline.json")
    baseline = cc.load_baseline(path)
    va, vb, _ = cc.check()
    seen = {tuple(map(cc._hashable, cc.violation_key(v, "A"))) for v in va}
    seen |= {tuple(map(cc._hashable, cc.violation_key(v, "B"))) for v in vb}
    stale = baseline - seen
    assert stale == set(), (
        f"{len(stale)} baseline entr(ies) no longer match anything — delete them "
        f"from {path}: {sorted(map(list, stale), key=str)}")


def test_held_repaint_clears_every_violation_in_this_tree():
    """The green-after-fix half of the red-first evidence, locked in.

    Runs tools/repaint_ojz_collision.py's analysis in memory over the committed
    editor tree and asserts both rules reach zero. Writes nothing.
    """
    hm, an = rp.base_bank_for()
    solid_top = cc.read_emp_const(cc.CONSTANTS_EMP, "SOLID_TOP")
    min_gap = 2 * cc.read_emp_const(cc.CONSTANTS_EMP, "PLAYER_X_RADIUS")
    edir = rp.editor_dir_for()
    path = os.path.join(edir, "section_0.collattr.bin")
    if not os.path.isfile(path):
        pytest.skip(f"no editor collision tree at {edir}")

    sec = rp.Section(path, hm, an)
    resolved, targets, va, vb = rp.analyse(sec, solid_top, min_gap)
    assert resolved, "section 0 plane A has no solid cells — nothing was measured"
    assert va or vb, (
        "section 0 plane A is already clean, so this test proves nothing. If the "
        "repaint has landed, delete this test along with the baseline.")

    for (col, cr) in targets:
        sec.set_word(col, cr, rp.repaint_word(sec.word(col, cr)))
    _r2, _t2, va2, vb2 = rp.analyse(sec, solid_top, min_gap)
    assert va2 == [] and vb2 == [], (
        f"repaint left {len(va2)} rule-A and {len(vb2)} rule-B violations")


def test_repaint_word_preserves_solidity_and_clears_flips():
    """Solidity is the owner's gameplay ruling (Defect 2), not this tool's."""
    import collision_pipeline as cp
    for sol in (1, 2, 3):
        for flips in (0, cp.CHUNK_XFLIP_BIT, cp.CHUNK_YFLIP_BIT,
                      cp.CHUNK_XFLIP_BIT | cp.CHUNK_YFLIP_BIT):
            word = (sol << cp.PATH_A_SOL_SHIFT) | flips | 114
            out = rp.repaint_word(word)
            assert out & cp.BLOCK_ID_MASK == rp.SAFE_FULL_SHAPE
            assert not (out & (cp.CHUNK_XFLIP_BIT | cp.CHUNK_YFLIP_BIT))
            assert (out >> cp.PATH_A_SOL_SHIFT) & 3 == sol


def _plane_file(tmp_path, cells, name="section_0.collattr.bin"):
    """Write a synthetic 256x256 editor plane file. cells = {(col, cr): word},
    addressed the way rp.Section does (cr = 16 px collision row = 2 tile rows).
    Every cell not named is air. Returns the path."""
    data = bytearray(rp.EDITOR_W * rp.EDITOR_W * 2)
    for (col, cr), w in cells.items():
        for tile_row in (cr * 2, cr * 2 + 1):
            o = 2 * (tile_row * rp.EDITOR_W + col)
            data[o] = (w >> 8) & 0xFF
            data[o + 1] = w & 0xFF
    path = tmp_path / name
    path.write_bytes(bytes(data))
    return str(path)


def test_repaint_word_preserves_the_loop_crossover_mark():
    """R4 of docs/LOOP_CROSSOVER_ENCODING.md §7: every rewriter of a per-plane
    cell word must PRESERVE bits 15:14, not rebuild the word without them.

    Non-vacuity, which is the whole difficulty here (anchor §8.1): bits 15:14
    are zero in all 18 shipped plane files, so no test over real content can
    fail. The mark is therefore AUTHORED DELIBERATELY below.

    Converse control, per anchor §8.1's R4 entry: repaint_word must still do its
    job on the same words — shape 255, flips cleared, solidity kept — so this
    cannot pass by turning repaint_word into the identity function. And a cell
    whose mark is XOVER_NONE must come back XOVER_NONE, so it cannot pass by
    setting the field unconditionally either.

    Bit positions come from cp.XOVER_SHIFT / cp.XOVER_MASK, never from a typed
    literal: the last sweep of this field missed a live use because it searched
    for the literal and the pipeline only ever spells the name.
    """
    import collision_pipeline as cp
    for xover in (cp.XOVER_TO_A, cp.XOVER_TO_B):
        for sol in (SOLID_TOP, 2, SOLID_ALL):
            for flips in (0, cp.CHUNK_XFLIP_BIT, cp.CHUNK_YFLIP_BIT,
                          cp.CHUNK_XFLIP_BIT | cp.CHUNK_YFLIP_BIT):
                word = ((xover << cp.XOVER_SHIFT) |
                        (sol << cp.PATH_A_SOL_SHIFT) | flips | 114)
                out = rp.repaint_word(word)
                # positive: the deliberately-authored mark survives
                assert (out >> cp.XOVER_SHIFT) & cp.XOVER_MASK == xover, (
                    f"repaint_word dropped the crossover mark of "
                    f"${word:04X}: got ${out:04X}")
                # converse: it is still the repaint, not the identity
                assert out & cp.BLOCK_ID_MASK == rp.SAFE_FULL_SHAPE
                assert not (out & (cp.CHUNK_XFLIP_BIT | cp.CHUNK_YFLIP_BIT))
                assert (out >> cp.PATH_A_SOL_SHIFT) & 3 == sol

    # converse: an unmarked cell must not acquire a mark
    unmarked = (SOLID_ALL << cp.PATH_A_SOL_SHIFT) | 114
    out = rp.repaint_word(unmarked)
    assert (out >> cp.XOVER_SHIFT) & cp.XOVER_MASK == cp.XOVER_NONE
    assert out & cp.BLOCK_ID_MASK == rp.SAFE_FULL_SHAPE


def test_repaint_write_path_preserves_the_crossover_on_a_synthetic_plane(tmp_path):
    """R4 again, through the tool's ACTUAL write path rather than one function.

    repaint_word is only half the rewriter: Section.set_word stamps the result
    into both tile rows of the 16 px cell. A synthetic plane with two shape-114
    pinhole cells is run through rp.analyse + the repaint loop exactly as
    rp.run does.

    Positive: the marked cell keeps XOVER_TO_B in BOTH tile rows.
    Converse control: the neighbouring cell, identical but for XOVER_NONE,
    is repainted normally and stays unmarked — so the test cannot pass by the
    tool refusing to touch anything.
    """
    import collision_pipeline as cp
    hm, an = rp.base_bank_for()
    solid_top = cc.read_emp_const(cc.CONSTANTS_EMP, "SOLID_TOP")
    min_gap = 2 * cc.read_emp_const(cc.CONSTANTS_EMP, "PLAYER_X_RADIUS")

    base = (SOLID_ALL << cp.PATH_A_SOL_SHIFT) | 114     # a pinhole floor cell
    marked = (cp.XOVER_TO_B << cp.XOVER_SHIFT) | base
    path = _plane_file(tmp_path, {(10, 20): marked, (12, 20): base})

    sec = rp.Section(path, hm, an)
    _resolved, targets, _va, _vb = rp.analyse(sec, solid_top, min_gap)
    assert (10, 20) in targets and (12, 20) in targets, (
        f"the fixture must be repaint TARGETS or it proves nothing: {targets}")

    for (col, cr) in targets:
        sec.set_word(col, cr, rp.repaint_word(sec.word(col, cr)))

    out_marked = sec.word(10, 20)
    out_plain = sec.word(12, 20)
    assert (out_marked >> cp.XOVER_SHIFT) & cp.XOVER_MASK == cp.XOVER_TO_B, (
        f"the tool's write path erased the crossover: ${out_marked:04X}")
    assert out_marked & cp.BLOCK_ID_MASK == rp.SAFE_FULL_SHAPE
    assert (out_plain >> cp.XOVER_SHIFT) & cp.XOVER_MASK == cp.XOVER_NONE
    assert out_plain & cp.BLOCK_ID_MASK == rp.SAFE_FULL_SHAPE

    # both tile rows of the marked cell, since set_word stamps two
    for tile_row in (40, 41):
        o = 2 * (tile_row * rp.EDITOR_W + 10)
        w = (sec.data[o] << 8) | sec.data[o + 1]
        assert w == out_marked, f"tile row {tile_row} disagrees: ${w:04X}"


def _fake_root(tmp_path, cells):
    """A minimal tree rp.run() can be pointed at with --root: the committed S&K
    base bank and constants.emp linked in read-only, plus ONE synthetic editor
    plane file built from `cells`. Nothing is written into the repo."""
    root = tmp_path / "root"
    coll = root / "games" / "sonic4" / "data" / "collision" / "base"
    edir = root / "games" / "sonic4" / "data" / "editor" / "ojz" / "act1"
    sysd = root / "engine" / "system"
    for d in (coll, edir, sysd):
        d.mkdir(parents=True, exist_ok=True)
    real_base = os.path.join(cc.coll_dir_for(), "base")
    for name in ("heightmaps.bin", "angles.bin"):
        (coll / name).symlink_to(os.path.join(real_base, name))
    (sysd / "constants.emp").symlink_to(cc.CONSTANTS_EMP)
    _plane_file(edir, cells)
    return str(root)


def test_run_reports_a_marked_target_as_a_notice_and_still_succeeds(tmp_path):
    """The preserve-not-refuse ruling, at the level of the tool's OUTPUT.

    docs/LOOP_CROSSOVER_ENCODING.md §3.4: a crossover mark on a cell whose
    geometry is being repainted is reported, not refused — §4 Q4 rules the two
    independent axes. So rp.run() must name the cell AND still exit 0.

    Positive: a deliberately marked pinhole cell produces the NOTICE and
    exit 0. Converse control: the identical tree with the mark cleared exits 0
    with no NOTICE at all — otherwise the test would pass on a tool that
    printed the notice unconditionally.
    """
    import collision_pipeline as cp
    import io

    base = (SOLID_ALL << cp.PATH_A_SOL_SHIFT) | 114
    marked = (cp.XOVER_TO_A << cp.XOVER_SHIFT) | base

    buf = io.StringIO()
    rc = rp.run(root=_fake_root(tmp_path / "m", {(10, 20): marked}),
                apply_changes=False, out=buf)
    text = buf.getvalue()
    assert rc == 0, f"a marked cell must not change the exit code:\n{text}"
    assert "NOTICE" in text and "col 10 row 20" in text, text
    assert f"XOVER={cp.XOVER_TO_A}" in text, text
    assert "REFUSED" not in text, text

    buf2 = io.StringIO()
    rc2 = rp.run(root=_fake_root(tmp_path / "p", {(10, 20): base}),
                 apply_changes=False, out=buf2)
    text2 = buf2.getvalue()
    assert rc2 == 0, text2
    assert "NOTICE" not in text2, (
        f"the notice fired on a tree with no crossover anywhere:\n{text2}")
    assert "WOULD REPAINT 1 cells" in text2, (
        f"the converse control must still be a real repaint target:\n{text2}")


def test_the_safe_full_shape_really_is_safe():
    """Shape 255 must be all-16 AND carry a flat/odd angle. Shape 251 is all-16
    but carries $E0 — the shape-114 diagnosis recommends '255 or 251' and that
    'or 251' would install the glide bug. Pin the distinction."""
    hm, an = rp.base_bank_for()
    prof255 = list(hm[255 * 16:256 * 16])
    assert cc.is_full_block(prof255)
    assert cc.is_flat_angle(an[255]), "shape 255 must not claim a slope"
    prof251 = list(hm[251 * 16:252 * 16])
    assert cc.is_full_block(prof251)
    assert not cc.is_flat_angle(an[251]), (
        "shape 251 is expected to be the UNSAFE all-16 block (angle $E0); if this "
        "fails the base bank changed and the repaint advice needs re-deriving")


def test_pinhole_profile_predicate():
    assert rp.is_pinhole_profile([16] * 15 + [0])          # shape 114 X-flipped
    assert rp.is_pinhole_profile([0] + [16] * 15)          # shape 114 itself
    assert not rp.is_pinhole_profile([16] * 16)            # no hole
    assert not rp.is_pinhole_profile([0] * 16)             # air, not a hole
    assert not rp.is_pinhole_profile([0] * 6 + [16] * 10)  # a real ledge


def test_baseline_file_is_wellformed_json_with_a_provenance_comment():
    path = os.path.join(cc.ROOT, "tools", "collision_baseline.json")
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    assert isinstance(doc.get("known_violations"), list)
    assert doc.get("_comment"), "the baseline must say why each exemption exists"
