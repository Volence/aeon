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
#     (test_repaint_write_path_preserves_the_crossover_on_a_synthetic_plane and
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
