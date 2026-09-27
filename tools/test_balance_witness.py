#!/usr/bin/env python3
"""tools/balance_witness.py's population and grading, without a machine.

WOVEN-FALSE-BALANCE (2026-09-27). The scene is the owner's, in miniature: a floor with a solid
step on it whose column under the step carries NO collision (Sonic 2's Emerald Hill at donor
(7712..7743, 896..927)), and a real ledge at the floor's far end. The step's foot must classify
WALL (the retired x -/+ 11 probe read a ledge there; S3K's rule is supported), the far end LEDGE
(S3K's rule balances), and nothing else on flat floor may be either.
"""
import balance_witness as W
import collision_consistency as cc

FULL = [16] * 16
SOLID_ALL = 3


def _scene():
    # 8-px columns x 16-px rows. Floor: row 10 (y 160), cols 12..59 (x 96..479).
    # Step: rows 8-9 (y 128..159), cols 8..11 (x 64..95), NOTHING under it in row 10.
    # Upper platform: rows 8-9 cols 0..7 top-only, like Emerald Hill's.
    rows, cols = 16, 64
    grid = [[0] * cols for _ in range(rows)]
    for c in range(12, 60):
        grid[10][c] = 1
    for r in (8, 9):
        for c in range(0, 12):
            grid[r][c] = 1
    heights = [[0] * 16, FULL]
    solidity = [0, SOLID_ALL]
    return cc.CollisionPlane(grid, heights, solidity), (cols * 8, rows * 16)


def test_the_steps_foot_is_wall_and_the_far_end_is_ledge():
    lp = cc.ledge_params()
    plane, size = _scene()
    pop = W.classify(plane, size, lp)
    walls = {(x, f, face) for x, f, face in pop["WALL"]}
    ledges = {(x, f, side) for x, f, side in pop["LEDGE"]}
    xr = lp["PLAYER_X_RADIUS"]
    # standing on the lower floor (feet y 160), just right of the step (its face at x 96),
    # facing it: the old probe at x - 11 lands in x < 96, under the step, where row 10 is air
    assert (96 + xr, 160, "left") in walls
    assert all(f == 160 and face == "left" and x - (xr + 2) < 96 for x, f, face in walls)
    # two real ledges, both facing right: the top of the step (x 95, feet 128) and the lower
    # floor's end (x 479, feet 160); the centre is over air and the right sensor finds nothing
    step_top = {r for r in ledges if r[1] == 128}
    floor_end = {r for r in ledges if r[1] == 160}
    assert step_top and floor_end and step_top | floor_end == ledges
    assert all(side == "right" and 96 <= x < 96 + xr for x, _f, side in step_top)
    assert all(side == "right" and 480 <= x < 480 + xr for x, _f, side in floor_end)


def test_spots_takes_one_per_cluster():
    picked, n = W.spots([(10, 160, "left"), (11, 160, "left"), (12, 160, "left"),
                         (40, 160, "left"), (41, 160, "right")], per_class=8)
    assert n == 3 and picked == [(11, 160, "left"), (40, 160, "left"), (41, 160, "right")]


def test_grade():
    e = {"PLAYER_Y_RADIUS": 19, "ANIM_BALANCE": 6}
    base = {"x": 105, "foot": 160, "px": 105, "py": 141, "layer": 0}
    assert W.grade(dict(base, cls="WALL", face="left", anim=5, facing="left"), e) is None
    assert W.grade(dict(base, cls="WALL", face="left", anim=6, facing="left"), e).startswith(
        "TEETERED")
    assert W.grade(dict(base, cls="LEDGE", face="right", anim=6, facing="right"), e) is None
    assert "facing left" in W.grade(dict(base, cls="LEDGE", face="right", anim=6,
                                         facing="left"), e)
    assert W.grade(dict(base, cls="LEDGE", face="right", anim=5, facing="right"),
                   e).startswith("did NOT")
    assert W.grade(dict(base, px=100, cls="WALL", face="left", anim=5, facing="left"),
                   e).startswith("UNMEASURED")
