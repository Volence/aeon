#!/usr/bin/env python3
"""clip_camera.py — the 2-D camera model of a clip act: where the player can be, where the
camera CENTRE can be, and what each centre's screen shows.

The woven mega-act (docs/research/2026-09-27-mega-act-woven.md, §A.4 and §C items 1 and 15)
stacks zones in both axes, so "which screen can show which zone" is no longer a question
about x alone. `docs/research/2026-09-27-mega-act-woven/woven.py check` answered it for the
proposal; this is that model PROMOTED INTO THE BAKE, built on the act's own composed
collision (clips, corridors, shafts and fill, `clip_manifest.collision_grids`) rather than
on the donor trees and a layout file, with every constant READ from the engine.

It serves two consumers in `tools/clip_rom_bake.py`:
  * the 2-D REGION PLAN (§C item 1): the reachable centres that see a zone are what the
    plan's rectangles must agree with;
  * the SCREEN CHECK (§C item 15, "Z1 counted on the screen, both axes"): over every
    reachable centre, no screen shows two zones, no screen shows a zone its region does not
    install, and every region boundary a player can cross has the frames the crossing needs.

THE MODEL (each term the engine's, named where it is read):

* WHERE THE PLAYER CAN BE. A cell is AIR when its plane-A collision word is not solid (shape
  0 or solidity 0: `collision_pipeline.bake_plane_cell`'s rule). Air is REACHABLE when it is
  within REACH px above a solid cell in its column (standing, or the top of a jump), or
  directly below reachable air in the same column (falling). REACH is the HIGHEST standing
  jump over every character (`clip_manifest.jump_reach_px`'s stepping, the max rather than
  the min) plus the standing body (2 x PLAYER_Y_RADIUS): the top of the body at the apex.
  A column alone cannot see a player RUN OR JUMP OFF AN EDGE into a pit (no floor in the
  pit's columns, so none of its air is near one): so reachable air also spreads ACROSS
  every air run of a row that holds a reachable cell, then falls again, until nothing new
  is reached. (The report's woven.py had only the column rule and declared its connector
  lanes reachable; the bake reaches them through their own collision, which this needs.)
  The row spread is unbounded, a further OVER-reach.
  Reachable air is then intersected with where the rolling ball fits (2 x BALL_X/Y_RADIUS + 1,
  floored to whole cells) and only the 4-connected pieces at least KEEP_FRAC of the largest
  are kept: an air pocket sealed inside the ground, which Sonic 2 leaves non-solid because
  nothing reaches it, is dropped. A COLUMN model: it ignores walls and so OVER-reaches, which
  makes every count below conservative (a centre that cannot really be reached can only add
  a refusal, never hide one). Plane A only, as the report's model: plane B is the same
  terrain with loops opened, and the column model already ignores what a loop blocks.
* WHERE THE CAMERA CENTRE CAN BE. Within the deadzone of a reachable player cell:
  CAM_X_DEADZONE_INIT px across and CAM_Y_DEADZONE px up and down (engine/level/camera.emp),
  then clamped to the act ([HALF_W, W - HALF_W] x [HALF_H, H - HALF_H]).
* WHAT A SCREEN SHOWS. The CAM_SCREEN_HALF_W x CAM_SCREEN_HALF_H box around the centre
  (engine/system/constants.emp). A zone is ON SCREEN when that box meets one of its clip
  RECTANGLES — not only its painted cells: a transparent cell shows the zone's background.
  `gap(key)` is the Chebyshev distance, in px, from the screen to the zone's nearest clip
  rectangle; negative means on screen.

The grid is the 8-px cell: a centre cell (r, c) stands for the centre (c * 8 + 4, r * 8 + 4).
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import clip_manifest            # noqa: E402
import collision_pipeline       # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELL = clip_manifest.TILE_PX
#: an air component smaller than this fraction of the largest is a sealed pocket (the
#: report's woven.py rule, kept as it was measured there)
KEEP_FRAC = 0.01


def constants():
    """Every engine term the model uses, READ from source (never typed)."""
    from fg_working_set import ConstantSource
    src = ConstantSource()
    for rel in ("engine/system/constants.emp", "engine/level/camera.emp",
                "games/sonic4/player/knuckles.emp"):
        src.load_file(os.path.join(REPO, rel))
    g = int(src.get("PHYS_GRAVITY"))
    rise = 0
    for name in ("PHYS_JUMP_FORCE", "KNUX_JUMP_FORCE"):
        v, r = -int(src.get(name)), 0
        while v < 0:
            r -= v
            v += g
        rise = max(rise, r // 256)
    c = {k: int(src.get(k)) for k in (
        "CAM_SCREEN_HALF_W", "CAM_SCREEN_HALF_H", "CAM_X_DEADZONE_INIT", "CAM_Y_DEADZONE",
        "CAM_MAX_X_STEP", "CAM_MAX_Y_STEP", "PLAYER_Y_RADIUS", "BALL_X_RADIUS",
        "BALL_Y_RADIUS")}
    c["JUMP_RISE_MAX"] = rise
    c["REACH"] = rise + 2 * c["PLAYER_Y_RADIUS"]
    return c


def _fits(air, bw, bh):
    """Cells where a bw x bh-cell body anchored there (top-left) is all air."""
    h, w = air.shape
    out = air.copy()
    for dx in range(bw):
        for dy in range(bh):
            sh = np.zeros_like(air)
            sh[:h - dy, :w - dx] = air[dy:, dx:]
            out &= sh
    return out


def components(mask):
    """4-connected components of a bool grid, labelled 1..n; (labels, n). Row RUNS joined by
    a union-find over the runs that touch vertically (a cell BFS over a whole act was the
    model's whole cost)."""
    h, w = mask.shape
    flat = mask.ravel()
    start = flat & ~np.concatenate([[False], flat[:-1]])
    start[np.arange(h) * w] = flat[np.arange(h) * w]
    run = (np.cumsum(start) * flat).reshape(h, w)
    nruns = int(run.max())
    parent = list(range(nruns + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    both = mask[:-1] & mask[1:]
    if both.any():
        pairs = np.unique(np.stack([run[:-1][both], run[1:][both]], axis=1), axis=0)
        for u, v in pairs.tolist():
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[max(ru, rv)] = min(ru, rv)
    roots = np.array([find(x) for x in range(nruns + 1)], dtype=np.int64)
    uniq, lab_of_root = np.unique(roots[1:], return_inverse=True)
    relabel = np.zeros(nruns + 1, dtype=np.int32)
    relabel[1:] = lab_of_root + 1
    return relabel[run], len(uniq)


def _fall(reach, air):
    """Everything directly below reachable air, down to the first non-air cell."""
    for r in range(1, reach.shape[0]):
        reach[r] |= reach[r - 1] & air[r]
    return reach


def _across(reach, air):
    """Every air run along a row (between two non-air cells) that holds a reachable cell."""
    h, w = air.shape
    flat = air.ravel()
    start = flat & ~np.concatenate([[False], flat[:-1]])
    start[np.arange(h) * w] = flat[np.arange(h) * w]      # a row edge starts a run too
    run = np.cumsum(start) * flat                          # run id per air cell, 0 = not air
    hit = np.bincount(run[reach.ravel() & flat], minlength=run.max() + 1) > 0
    hit[0] = False
    return reach | hit[run].reshape(h, w)


def reachable_air(solid, c):
    """solid: (rows, cols) bool -> reachable air, by the module docstring's model."""
    n = -(-c["REACH"] // CELL)
    near_floor = np.zeros_like(solid)
    for k in range(1, n + 1):
        near_floor[:-k] |= solid[k:]
    air = ~solid
    reach = _fall(near_floor & air, air)
    while True:                                    # across, then down, until nothing new
        nxt = _fall(_across(reach, air), air)
        if (nxt == reach).all():
            break
        reach = nxt
    bw = (2 * c["BALL_X_RADIUS"] + 1) // CELL
    bh = (2 * c["BALL_Y_RADIUS"] + 1) // CELL
    reach &= _fits(~solid, max(1, bw), max(1, bh))
    lab, cnt = components(reach)
    if cnt == 0:
        return reach
    sizes = np.bincount(lab.ravel())[1:]
    keep = np.flatnonzero(sizes >= KEEP_FRAC * sizes.max()) + 1
    return np.isin(lab, keep)


def dilate(m, rx, ry):
    out = m.copy()
    for k in range(1, rx + 1):
        out[:, k:] |= m[:, :-k]
        out[:, :-k] |= m[:, k:]
    m2 = out.copy()
    for k in range(1, ry + 1):
        out[k:] |= m2[:-k]
        out[:-k] |= m2[k:]
    return out


class CameraModel:
    """The act's reachable player cells, reachable camera centres and per-zone screen gaps.

    Built once per bake (`for_act` memoises it on the act) — every consumer reads the same
    numbers."""

    def __init__(self, act, donor_root=None, consts=None):
        donor_root = clip_manifest._root(donor_root)
        self.act = act
        self.c = consts or constants()
        self.W = act.cols * CELL
        self.H = act.rows * CELL
        pa, _pb = clip_manifest.collision_grids(act, donor_root)
        sol = (pa.astype(np.int64) >> collision_pipeline.PLANE_SOL_SHIFT) & 3
        self.solid = ((pa & collision_pipeline.BLOCK_ID_MASK) != 0) & (sol != 0)
        self.player = reachable_air(self.solid, self.c)
        self.centres = self._centres(self.player)
        self.keys = sorted({cl.zone_key for cl in act.clips})
        self.rects = {k: [cl.dst for cl in act.clips if cl.zone_key == k] for k in self.keys}
        painted = np.zeros((act.rows, act.cols), dtype=bool)
        for p in list(act.clips) + list(act.corridors) + list(getattr(act, "shafts", [])):
            x, y, w, h = (v // CELL for v in p.dst)
            painted[y:y + h, x:x + w] = True
        painted |= clip_manifest.fill_mask(act)
        #: act cells a screen may show that are not VOID (a clip, a connector or the fill)
        self.painted = painted
        self._gaps = {}

    @classmethod
    def for_act(cls, act, donor_root=None):
        key = (clip_manifest._root(donor_root), "camera_model")
        if key not in act._memo:
            act._memo[key] = cls(act, donor_root)
        return act._memo[key]

    def _centres(self, player):
        c = self.c
        d = dilate(player, c["CAM_X_DEADZONE_INIT"] // CELL, c["CAM_Y_DEADZONE"] // CELL)
        ys, xs = np.nonzero(d)
        xs = np.clip(xs, c["CAM_SCREEN_HALF_W"] // CELL,
                     (self.W - c["CAM_SCREEN_HALF_W"]) // CELL - 1)
        ys = np.clip(ys, c["CAM_SCREEN_HALF_H"] // CELL,
                     (self.H - c["CAM_SCREEN_HALF_H"]) // CELL - 1)
        out = np.zeros_like(d)
        out[ys, xs] = True
        return out

    def centre_px(self):
        """(cy, cx) broadcastable px grids of every cell's centre."""
        rows, cols = self.centres.shape
        return ((np.arange(rows) * CELL + CELL // 2)[:, None],
                (np.arange(cols) * CELL + CELL // 2)[None, :])

    def gap(self, key):
        """(rows, cols) int: Chebyshev px from each centre's screen to zone `key`'s nearest
        clip rectangle; negative = on screen."""
        if key not in self._gaps:
            cy, cx = self.centre_px()
            hw, hh = self.c["CAM_SCREEN_HALF_W"], self.c["CAM_SCREEN_HALF_H"]
            best = None
            for x0, y0, w, h in self.rects[key]:
                gx = np.maximum(x0 - (cx + hw), (cx - hw) - (x0 + w))
                gy = np.maximum(y0 - (cy + hh), (cy - hh) - (y0 + h))
                g = np.maximum(gx, gy)
                best = g if best is None else np.minimum(best, g)
            self._gaps[key] = best
        return self._gaps[key]

    def visible(self):
        """(Z, rows, cols) bool, zone keys in `self.keys` order."""
        return np.stack([self.gap(k) < 0 for k in self.keys])

    def mixed(self, everywhere=False):
        """Centres whose screen shows two zones — REACHABLE ones, or every centre with
        `everywhere` (the latter is reported, never enforced: a sealed seam is legitimately
        closer than a screen, and nobody's camera is there)."""
        m = self.visible().sum(axis=0) > 1
        return m if everywhere else m & self.centres
