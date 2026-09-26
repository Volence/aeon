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
# RULE B, second stage — only a gap a reachable standing player's ledge probe
# reports as a ledge is a violation (S2CLIP-CPZ-FURTHER, 2026-09-25).
#
# Four synthetic scenes, one per class the CPZ research found
# (docs/research/2026-09-25-cpz-floor-gaps.md). Every scene has the SAME one-row
# candidate: a 16 px gap in floor row 10, cols 20-21, floor on both sides. The
# one-row scan (`find_pinhole_violations`) flags all four; only the geometry
# around the gap differs, and each allowed scene is cleared by ONE named stage.
# Thresholds come from the source (`cc.ledge_params()`), never from this file.
# ---------------------------------------------------------------------------

B_ROWS, B_COLS, B_FLOOR_ROW, B_GAP_COLS = 16, 40, 10, (20, 21)
B_FULL, B_THIN = 1, 2       # attrs: full SOLID_ALL block; 1 px high SOLID_ALL shape


def _b_tables():
    heights, _angles, solidity = _tables({B_FULL: (FULL, 0xFF, SOLID_ALL),
                                          B_THIN: ([1] * 16, 0xFF, SOLID_ALL)})
    return heights, solidity


def _scene(kind):
    """One 40x16-cell scene holding the row-10 gap. Returns {(row, col): attr}."""
    cells = {}
    if kind == "reachable":
        # open floor with a 16 px hole: thick ground from row 10 down, air above
        for r in range(B_FLOOR_ROW, B_ROWS):
            for c in range(B_COLS):
                cells[(r, c)] = B_FULL
    elif kind == "sealed":
        # solid rock holding a 160 x 64 px room (rows 6-9, cols 10-29) whose
        # floor is row 10: a player fits in the room, but nothing leads into it
        for r in range(B_ROWS):
            for c in range(B_COLS):
                if not (6 <= r < B_FLOOR_ROW and 10 <= c < 30):
                    cells[(r, c)] = B_FULL
    elif kind == "notch":
        # a slab (rows 4-10) with a 16 px notch in its underside; open air below
        for r in range(4, B_FLOOR_ROW + 1):
            for c in range(B_COLS):
                cells[(r, c)] = B_FULL
    elif kind == "dip":
        # a 1 px high floor surface (row 10) over solid ground (rows 11+): the air
        # cell has solid ground 1 px under the probe point
        for c in range(B_COLS):
            cells[(B_FLOOR_ROW, c)] = B_THIN
        for r in range(B_FLOOR_ROW + 1, B_ROWS):
            for c in range(B_COLS):
                cells[(r, c)] = B_FULL
    else:
        raise ValueError(kind)
    for c in B_GAP_COLS:
        cells.pop((B_FLOOR_ROW, c), None)
    return cells


def _exposed(grid):
    heights, solidity = _b_tables()
    lp = cc.ledge_params()
    return cc.find_exposed_pinhole_violations(
        grid, heights, solidity, lp["SOLID_TOP"], lp["SOLID_LRB"],
        lp["PLAYER_X_RADIUS"], lp["PLAYER_Y_RADIUS"], lp["LEDGE_PROBE_REACH"],
        lp["LEDGE_NO_GROUND"], other_rows=grid)


def _stage(kind):
    heights, solidity = _b_tables()
    lp = cc.ledge_params()
    grid = _grid(B_ROWS, B_COLS, _scene(kind))
    cand, _ = cc.find_pinhole_violations(grid, heights, solidity, lp["SOLID_TOP"],
                                         2 * lp["PLAYER_X_RADIUS"])
    # The precondition every scene shares: the ONE-ROW scan flags exactly the
    # row-10 gap, so whatever clears it below is the second stage, not the scan.
    assert [(v["row"], v["x_start"], v["gap_px"]) for v in cand] == [
        (B_FLOOR_ROW, B_GAP_COLS[0] * 8, 16)], (kind, cand)
    plane = cc.CollisionPlane(grid, heights, solidity, grid)
    return cc.classify_pinhole(plane, cand[0], lp["SOLID_TOP"], lp["SOLID_LRB"],
                               lp["PLAYER_X_RADIUS"], lp["PLAYER_Y_RADIUS"],
                               lp["LEDGE_PROBE_REACH"], lp["LEDGE_NO_GROUND"])


def test_rule_b_refuses_a_reachable_pinhole():
    """RED-able: open floor, a player walks up to the hole and teeters."""
    stage, witness = _stage("reachable")
    assert stage == "exposed"
    x, foot_y, _facing = witness
    assert foot_y == B_FLOOR_ROW * 16          # standing on the floor's top
    v, stats = _exposed(_grid(B_ROWS, B_COLS, _scene("reachable")))
    assert len(v) == 1 and stats["candidates"] == 1


def test_rule_b_allows_a_sealed_pocket():
    """A room a player would fit in, sealed inside rock on both planes."""
    assert _stage("sealed")[0] == "sealed"
    assert _exposed(_grid(B_ROWS, B_COLS, _scene("sealed")))[0] == []


def test_rule_b_allows_an_under_slab_notch():
    """The gap is in the slab's underside: no one can stand beside it."""
    assert _stage("notch")[0] == "no_stand"
    assert _exposed(_grid(B_ROWS, B_COLS, _scene("notch")))[0] == []


def test_rule_b_allows_a_one_pixel_dip():
    """The probe finds ground 1 px down, within LEDGE_NO_GROUND: no teeter."""
    assert _stage("dip")[0] == "ground_within_limit"
    assert _exposed(_grid(B_ROWS, B_COLS, _scene("dip")))[0] == []


def test_rule_b_refuses_only_the_reachable_one_of_four_side_by_side():
    """All four scenes in one grid: four one-row candidates, one violation, at
    the reachable scene's gap."""
    order = ("sealed", "reachable", "notch", "dip")
    cells = {}
    for i, kind in enumerate(order):
        cells.update({(r, c + i * B_COLS): a for (r, c), a in _scene(kind).items()})
    v, stats = _exposed(_grid(B_ROWS, B_COLS * len(order), cells))
    assert stats["candidates"] == 4
    assert [(x["row"], x["x_start"]) for x in v] == [
        (B_FLOOR_ROW, (order.index("reachable") * B_COLS + B_GAP_COLS[0]) * 8)]
    assert (stats["cleared_sealed"], stats["cleared_no_stand"],
            stats["cleared_ground_within_limit"]) == (1, 1, 1)


def test_rule_b_ledge_thresholds_derive_from_the_source():
    """LEDGE_PROBE_REACH is `PLAYER_X_RADIUS+2` in player_sensors.emp: it must be
    EVALUATED from the source, and anything unreadable must be loud."""
    lp = cc.ledge_params()
    assert lp["LEDGE_PROBE_REACH"] == lp["PLAYER_X_RADIUS"] + 2 == 11
    assert lp["LEDGE_NO_GROUND"] == 8
    assert lp["SOLID_LRB"] == 2 and lp["PLAYER_Y_RADIUS"] == 19
    with pytest.raises(cc.GateError):
        cc.read_emp_const_expr(cc.player_sensors_emp_for(), "LEDGE_PROBE_REACH", {})
    with pytest.raises(cc.GateError):
        cc.read_emp_const_expr(cc.player_sensors_emp_for(), "NO_SUCH_CONSTANT", lp)


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
# Real in-repo data — the BAKED FILES ON DISK, which may be uncommitted
#
# "committed" in this module's names and prose means IN-REPO and donor-free, not
# "at HEAD": `cc.check()` reads games/sonic4/data/generated/... off disk, so a
# working-tree edit is graded exactly as build.sh grades it, which is correct for
# a build gate and misleading in a test name. A failure here therefore carries
# `cc.dirty_note()`, which says whether the graded bytes are uncommitted, because
# without it a reader's first move is to look at what landed. It cost a session
# that search on 2026-09-10.
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
    assert new == [], (f"{len(new)} collision violation(s) not in the baseline: "
                       f"{new}{cc.dirty_note()}")


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


# test_held_repaint_clears_every_violation_in_this_tree lived here until
# 2026-08-29. It asserted `va or vb` over the REAL editor tree — i.e. that the
# tree still violated — so it could only stay green while the defect was still
# unfixed, and it went red the moment the repaint landed (fde35b2f). It said so
# in its own assertion message and it was deleted per that instruction, together
# with the eight baseline entries the repaint cleared.
#
# What covers its two claims now:
#   OUTCOME  — superseded and STRENGTHENED by
#     test_committed_tree_has_no_violation_outside_the_baseline against an EMPTY
#     tools/collision_baseline.json: that measures the real GENERATED tree the
#     ROM actually consumes, and now demands zero violations rather than zero
#     new ones. The deleted test only simulated the fix in memory.
#   MECHANISM — rp.analyse's target selection and Section.set_word's write path
#     are covered by the synthetic tests on branch fix/repaint-preserve-crossover
#     (test_repaint_write_path_preserves_the_reserved_bits_on_a_synthetic_plane, named
#     ..._the_crossover_... until LINES-EVERYWHERE retired the mark, and
#     its _fake_root sibling). Those build their own dirty fixture, so unlike the
#     test deleted here they stay red-able forever. THAT BRANCH IS UNMERGED: until
#     it lands, rp.analyse has no direct test. See docs/DEFERRED_WORK.md.


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


def _write_plane(path, cells):
    """Write a synthetic 256x256 editor plane file at `path`.
    cells = {(col, cr): word}, addressed the way rp.Section does (cr = 16 px
    collision row = 2 tile rows). Every cell not named is air."""
    data = bytearray(rp.EDITOR_W * rp.EDITOR_W * 2)
    for (col, cr), w in cells.items():
        for tile_row in (cr * 2, cr * 2 + 1):
            o = 2 * (tile_row * rp.EDITOR_W + col)
            data[o] = (w >> 8) & 0xFF
            data[o + 1] = w & 0xFF
    path.write_bytes(bytes(data))
    return str(path)


def _plane_file(tmp_path, cells, name="section_0.collattr.bin"):
    """_write_plane into tmp_path/name. Returns the path."""
    return _write_plane(tmp_path / name, cells)


def test_repaint_word_preserves_the_reserved_bits():
    """Every rewriter of a per-plane cell word must PRESERVE bits 15:14, not rebuild the
    word without them. They are RESERVED (zero in every legal word) since the painted loop
    crossover mark they carried was retired on 2026-09-26 (LINES-EVERYWHERE), and the bake
    refuses a word with them set. A geometry repaint that quietly cleared a leftover mark
    would hide it from that refusal, so repaint_word carries them through.

    Converse control: repaint_word must still do its job on the same words — shape 255,
    flips cleared, solidity kept — so this cannot pass by turning repaint_word into the
    identity function. And a clear word must come back clear, so it cannot pass by setting
    the field unconditionally either.
    """
    import collision_pipeline as cp
    for reserved in range(1, cp.PLANE_RESERVED_MASK + 1):
        for sol in (SOLID_TOP, 2, SOLID_ALL):
            for flips in (0, cp.CHUNK_XFLIP_BIT, cp.CHUNK_YFLIP_BIT,
                          cp.CHUNK_XFLIP_BIT | cp.CHUNK_YFLIP_BIT):
                word = ((reserved << cp.PLANE_RESERVED_SHIFT) |
                        (sol << cp.PLANE_SOL_SHIFT) | flips | 114)
                out = rp.repaint_word(word)
                assert cp.plane_reserved_bits(out) == reserved, (
                    f"repaint_word dropped the reserved bits of ${word:04X}: got ${out:04X}")
                assert out & cp.BLOCK_ID_MASK == rp.SAFE_FULL_SHAPE
                assert not (out & (cp.CHUNK_XFLIP_BIT | cp.CHUNK_YFLIP_BIT))
                assert (out >> cp.PLANE_SOL_SHIFT) & 3 == sol

    clear = (SOLID_ALL << cp.PLANE_SOL_SHIFT) | 114
    out = rp.repaint_word(clear)
    assert cp.plane_reserved_bits(out) == 0
    assert out & cp.BLOCK_ID_MASK == rp.SAFE_FULL_SHAPE


def test_repaint_write_path_preserves_the_reserved_bits_on_a_synthetic_plane(tmp_path):
    """The reserved-bits rule through the tool's ACTUAL write path rather than one function.

    repaint_word is only half the rewriter: Section.set_word stamps the result into both
    tile rows of the 16 px cell. A synthetic plane with two shape-114 pinhole cells is run
    through rp.analyse + the repaint loop exactly as rp.run does.

    Positive: the marked cell keeps its reserved bits in BOTH tile rows. Converse control:
    the neighbouring cell, identical but clear, is repainted normally and stays clear — so
    the test cannot pass by the tool refusing to touch anything.
    """
    import collision_pipeline as cp
    hm, an = rp.base_bank_for()
    solid_top = cc.read_emp_const(cc.CONSTANTS_EMP, "SOLID_TOP")
    min_gap = 2 * cc.read_emp_const(cc.CONSTANTS_EMP, "PLAYER_X_RADIUS")

    base = (SOLID_ALL << cp.PLANE_SOL_SHIFT) | 114     # a pinhole floor cell
    marked = (2 << cp.PLANE_RESERVED_SHIFT) | base
    path = _plane_file(tmp_path, {(10, 20): marked, (12, 20): base})

    sec = rp.Section(path, hm, an)
    _resolved, targets, _va, _vb = rp.analyse(sec, solid_top, min_gap)
    assert (10, 20) in targets and (12, 20) in targets, (
        f"the fixture must be repaint TARGETS or it proves nothing: {targets}")

    for (col, cr) in targets:
        sec.set_word(col, cr, rp.repaint_word(sec.word(col, cr)))

    out_marked = sec.word(10, 20)
    out_plain = sec.word(12, 20)
    assert cp.plane_reserved_bits(out_marked) == 2, (
        f"the tool's write path erased the reserved bits: ${out_marked:04X}")
    assert out_marked & cp.BLOCK_ID_MASK == rp.SAFE_FULL_SHAPE
    assert cp.plane_reserved_bits(out_plain) == 0
    assert out_plain & cp.BLOCK_ID_MASK == rp.SAFE_FULL_SHAPE

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
    """A leftover retired crossover mark on a repaint target is REPORTED by the repaint tool
    (a NOTICE naming the cell), and the tool still exits 0: it repaints geometry, and the
    refusal of the mark is the bake's job. Converse control: the identical tree with the
    bits clear exits 0 with no NOTICE at all."""
    import collision_pipeline as cp
    import io

    base = (SOLID_ALL << cp.PLANE_SOL_SHIFT) | 114
    marked = (1 << cp.PLANE_RESERVED_SHIFT) | base

    buf = io.StringIO()
    rc = rp.run(root=_fake_root(tmp_path / "m", {(10, 20): marked}),
                apply_changes=False, out=buf)
    text = buf.getvalue()
    assert rc == 0, f"a marked cell must not change the exit code:\n{text}"
    assert "NOTICE" in text and "col 10 row 20" in text, text
    assert "RESERVED=1" in text and "RETIRED" in text, text
    assert "REFUSED" not in text, text

    buf2 = io.StringIO()
    rc2 = rp.run(root=_fake_root(tmp_path / "p", {(10, 20): base}),
                 apply_changes=False, out=buf2)
    text2 = buf2.getvalue()
    assert rc2 == 0, text2
    assert "NOTICE" not in text2, (
        f"the notice fired on a tree with no reserved bits anywhere:\n{text2}")
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


# ---------------------------------------------------------------------------
# THE RETIRED CROSSOVER MARK (LINES-EVERYWHERE, 2026-09-26).
#
# Bits 15:14 of the per-plane cell word carried the painted loop crossover mark until
# layer-switch LINES replaced it (tools/layer_lines.py). They are now RESERVED and must be
# zero, and a word with them set is REFUSED rather than dropped: a dropped mark is authoring
# intent that silently does nothing, the exact defect ("AN AUTHORED LOOP CROSSOVER REACHES
# THE FILE AND NEVER THE ROM") the field was built to close. Two refusals pin it: the bake
# (bake_plane_cell, through the real overlay path) and the preflight census
# (ojz_strip_gen.validate_editor_inputs), which also sees the odd editor rows the bake never
# reads. Every refusal below carries its converse control: the same tree, bits clear, bakes.
# ---------------------------------------------------------------------------

RESERVED_TEST_SHAPE = 114     # a real base-bank shape with geometry (see rule B)


def _overlay(tmp_path, monkeypatch, cells_a, cells_b):
    """Run the REAL bake path — ojz_strip_gen.apply_editor_collision_overlay — over a
    synthetic one-section editor tree, and emit the ROM tables from the attr-set it filled.
    Returns (grids, attrset, tables)."""
    import ojz_strip_gen as osg
    import collision_pipeline as cp

    edir = tmp_path / "editor"
    act = edir / "ojz" / "act1"
    act.mkdir(parents=True, exist_ok=True)
    _write_plane(act / "section_0.collattr.bin", cells_a)
    _write_plane(act / "section_0.collattrb.bin", cells_b)
    # EDITOR_ACT_DIR, not EDITOR_DIR — see the same note in test_baker_refusals.py.
    monkeypatch.setattr(osg, "EDITOR_ACT_DIR", str(act))

    profiles, angles = osg.load_base_bank()
    air = bytes(osg.COLLISION_ROWS_PER_STRIP)
    grids = ([air] * osg.STRIP_TILE_HEIGHT, [air] * osg.STRIP_TILE_HEIGHT)
    attrset = cp.AttrSet()
    out = osg.apply_editor_collision_overlay(grids, "0", profiles, angles, attrset)
    return out, attrset, cp.emit_tables(attrset)


@pytest.mark.parametrize("value", [1, 2, 3])
def test_the_bake_refuses_a_retired_mark_on_a_solid_and_on_an_air_cell(value):
    import collision_pipeline as cp
    profiles, angles = rp.base_bank_for()
    s = cp.AttrSet()
    base = (SOLID_ALL << cp.PLANE_SOL_SHIFT) | RESERVED_TEST_SHAPE
    for w in (base, 0x0000):
        with pytest.raises(ValueError) as exc:
            cp.bake_plane_cell(w | (value << cp.PLANE_RESERVED_SHIFT), profiles, angles, s)
        assert "RETIRED" in str(exc.value)
    assert len(s.entries) == 1, "a refused word interned nothing"
    # converse control: the same words, bits clear, bake (solid) and stay air
    assert cp.bake_plane_cell(base, profiles, angles, s) != 0
    assert cp.bake_plane_cell(0x0000, profiles, angles, s) == 0


def test_the_overlay_refuses_a_retired_mark_on_either_plane(tmp_path, monkeypatch):
    import collision_pipeline as cp
    base = (SOLID_ALL << cp.PLANE_SOL_SHIFT) | RESERVED_TEST_SHAPE
    marked = base | (2 << cp.PLANE_RESERVED_SHIFT)
    with pytest.raises(ValueError, match="RETIRED"):
        _overlay(tmp_path / "a", monkeypatch, {(10, 20): marked}, {(10, 20): base})
    with pytest.raises(ValueError, match="RETIRED"):
        _overlay(tmp_path / "b", monkeypatch, {(10, 20): base}, {(10, 20): marked})
    (ga, _gb), _s, tables = _overlay(tmp_path / "c", monkeypatch,
                                     {(10, 20): base}, {(10, 20): base})
    assert ga[10][20], "the converse control must bake to a solid cell"
    assert "crossover.bin" not in tables, "the crossover table is retired"


def test_the_preflight_names_every_retired_mark_including_an_odd_row(tmp_path):
    """The census the bake cannot do: the bake reads only the EVEN editor rows (the top
    tile row of each 16 px collision row), so a mark on an odd row would never reach
    bake_plane_cell. The preflight reads every word of both planes and names the cells."""
    import collision_pipeline as cp
    import ojz_strip_gen as osg
    base = (SOLID_ALL << cp.PLANE_SOL_SHIFT) | RESERVED_TEST_SHAPE
    d = tmp_path / "act"
    d.mkdir()
    words = [0] * (osg.STRIP_TILE_HEIGHT * osg.STRIP_TILE_HEIGHT)
    words[41 * osg.STRIP_TILE_HEIGHT + 10] = base | (1 << cp.PLANE_RESERVED_SHIFT)  # odd row
    (d / "section_0.collattr.bin").write_bytes(
        b"".join(w.to_bytes(2, "big") for w in words))
    problems = osg._collattr_problems(str(d), 0)
    assert len(problems) == 1 and "RETIRED" in problems[0] and "(10, 41)" in problems[0], problems
    # converse control: the same file with the bits clear raises nothing
    words[41 * osg.STRIP_TILE_HEIGHT + 10] = base
    (d / "section_0.collattr.bin").write_bytes(
        b"".join(w.to_bytes(2, "big") for w in words))
    assert osg._collattr_problems(str(d), 0) == []


def test_the_donor_baker_still_reads_bits_15_14_as_path_b_solidity():
    """Bits 15:14 are path-B SOLIDITY in the donor chunk-entry word (bake_cell) and RESERVED
    in the per-plane cell word (bake_plane_cell): the same value, two word spaces, never one
    name. Retiring the mark must not touch the donor's meaning.

    Converse control: the same value with 15:14 CLEAR must produce path-B air from
    bake_cell, so the test cannot pass by bake_cell returning a second byte unconditionally.
    """
    import collision_pipeline as cp
    index = bytes([0, 1])                                   # block 1 -> profile 1
    profiles = bytes(16) + bytes([16] * 16) + bytes(4096 - 32)
    angles = bytes(256)

    word = 0x0001 | (cp.SOL_ALL << cp.PATH_A_SOL_SHIFT) | (2 << cp.PATH_B_SOL_SHIFT)
    s_donor = cp.AttrSet()
    a, b = cp.bake_cell(word, index, index, profiles, angles, s_donor)
    assert a != 0 and b != 0, f"the donor baker lost path B: ({a}, {b})"
    assert s_donor.entries[b][2] == 2, "path B's SOLIDITY is the value bits 15:14 carried"

    with pytest.raises(ValueError, match="RETIRED"):
        cp.bake_plane_cell(word, profiles, angles, cp.AttrSet())

    clear = 0x0001 | (cp.SOL_ALL << cp.PATH_A_SOL_SHIFT)
    a2, b2 = cp.bake_cell(clear, index, index, profiles, angles, cp.AttrSet())
    assert a2 != 0 and b2 == 0, f"expected path-B air, got ({a2}, {b2})"
