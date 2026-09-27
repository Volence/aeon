#!/usr/bin/env python3
"""The woven mega-act proposal: seam timing check, clip edge survey, picture, and draft manifest.

A MEASUREMENT AND DRAWING TOOL for docs/research/2026-09-27-mega-act-woven.md. Not a bake and
not a gate. It reads the converted donor trees (gitignored, written by
`tools/s2_zone_convert.py`) and a layout file (`layout.json` beside it). It never writes into
the repo except where told (`--out`).

    python3 woven.py edges  s2disasm/EHZ 6144,0,2560,1024      # how far a camera sees past each edge
    python3 woven.py check  layout.json                          # the seam rule over every camera
    python3 woven.py render layout.json --out woven.png          # the to-scale picture
    python3 woven.py manifest layout.json --out draft_clips.json # clips-only manifest for the bake

THE MODEL (every constant is the engine's, named where it is used):

* WHERE THE PLAYER CAN BE. A clip cell is "air" when its plane-A collision word is not solid
  (`collision_pipeline.bake_plane_cell`'s rule: solidity 0 or shape 0). Air is REACHABLE when
  it is within JUMP_REACH px above a solid cell in its column (standing, or the top of a
  jump), or directly below reachable air in the same column (falling). That is a column model:
  it ignores walls, so it over-reaches (enclosed air under a floor counts), which makes every
  number below conservative. Connector lanes (the tunnel walkway, the shaft's climb column) are
  reachable by declaration.
* WHERE THE CAMERA CAN BE. Its centre is within the deadzone of the player:
  CAM_X_DEADZONE_INIT 16 px across and CAM_Y_DEADZONE 32 px up and down (engine/level/
  camera.emp), then clamped to the act ([160, W-160] x [112, H-112]). No look-up / look-down
  pan exists today (`PlayerV.look_offset` "stays 0 this pass"); when it lands it widens the
  vertical view, and the report says by how much.
* WHAT THE SCREEN SHOWS. 320 x 224 around the centre (CAM_SCREEN_HALF_W 160,
  CAM_SCREEN_HALF_H 112). A zone is ON SCREEN when that window meets its clip RECTANGLE (not
  only its painted cells: a transparent cell shows the zone's background and backdrop).
* THE REGION. Every reachable centre is in one zone's region. The plan puts the boundary
  where the two sides' slack is balanced: region = argmin over zones of
  (distance-to-on-screen - 16 x T_into), which is what "the crossing in the middle, shifted
  toward the cheaper side" means on both axes at once. The engine needs rectangles; turning
  this into rectangles is the 2-D region plan item (§C), and the check below is what those
  rectangles must satisfy.
* THE TIMING. On a crossing into zone Z, the palette snaps in the crossing frame and the
  background needs T frames (docs/research/2026-09-25-shorter-connector.md §8): T = 2 when Z's
  background tiles are already in the BG arena (the two zones share a BG blob), otherwise
  ceil(blob bytes / 1824) overwrite chunks + 3 (DMA wipe 2 + one slipped-DMA frame). The
  camera moves at most 16 px a frame on each axis (CAM_MAX_X_STEP, CAM_MAX_Y_STEP), so a
  centre whose screen is s px (Chebyshev) from zone Z's rectangle cannot show Z for
  floor(s/16)+1 frames. The rule: at every centre where the region is Z and a neighbouring
  reachable centre is in another region R, s >= 16 x T(R -> Z).

Output of `check`: MIXED (screens showing two zones: must be 0), WRONG (a zone on screen
while the centre is in another zone's region: must be 0), per-crossing SLACK in px (must be
>= 0), and VOID seen from a connector lane (unpainted act cells a crossing could show while
the background is being replaced: must be 0).
"""
import argparse
import json
import math
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "docs/research/2026-09-27-mega-act-layout"))

CELL = 8
SEC = 2048
HALF_W, HALF_H = 160, 112          # CAM_SCREEN_HALF_W / _H
DZ_X, DZ_Y = 16, 32                # CAM_X_DEADZONE_INIT / CAM_Y_DEADZONE
STEP = 16                          # CAM_MAX_X_STEP = CAM_MAX_Y_STEP
JUMP_REACH = 128                   # INFERRED: S2 jump apex ~97 px (6.5^2 / (2 x 0.21875)) + ball radius
CHUNK_BYTES = 1824                 # BG_OVERWRITE_CHUNK_BYTES
WIPE_T = 2                         # DMA wipe, frames (MEASURED 09-25 §8.2)
SLIP = 1                           # Z2's slipped-DMA allowance
PLANE_SOL_SHIFT = 12
DONORS = REPO / "games/sonic4/data/donors"


# ---------------------------------------------------------------------------- trees

class Tree:
    def __init__(self, rel):
        d = DONORS / rel
        self.zm = json.loads((d / "zone.json").read_text())
        gw, gh = self.zm["grid"]["w"], self.zm["grid"]["h"]
        ca = np.zeros((gh * 256, gw * 256), dtype=np.uint16)
        for s in self.zm["sections"]:
            raw = (d / f"section_{s['n']}.collattr.bin").read_bytes()
            ca[s["sy"] * 256:(s["sy"] + 1) * 256, s["sx"] * 256:(s["sx"] + 1) * 256] = \
                np.frombuffer(raw, dtype=">u2").reshape(256, 256)
        self.ca = ca

    def solid(self, x, y, w, h):
        c = self.ca[y // CELL:(y + h) // CELL, x // CELL:(x + w) // CELL]
        return ((c & 0x3FF) != 0) & (((c >> PLANE_SOL_SHIFT) & 3) != 0)


_trees = {}


def tree(rel):
    if rel not in _trees:
        _trees[rel] = Tree(rel)
    return _trees[rel]


def _fits(air, bw, bh):
    """Cells where a bw x bh-cell body anchored there is all air (the rolling ball, 14 x 28 px
    radii, rounds to 2 x 4 cells)."""
    h, w = air.shape
    out = air.copy()
    for dx in range(bw):
        for dy in range(bh):
            sh = np.zeros_like(air)
            sh[:h - dy, :w - dx] = air[dy:, dx:]
            out &= sh
    return out


def _components(mask):
    """4-connected components, labelled 1..n (pure Python BFS: no scipy here)."""
    from collections import deque
    lab = np.zeros(mask.shape, dtype=np.int32)
    h, w = mask.shape
    n = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if lab[y0, x0]:
            continue
        n += 1
        lab[y0, x0] = n
        q = deque([(y0, x0)])
        while q:
            y, x = q.popleft()
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    q.append((yy, xx))
    return lab, n


def reachable_air(solid, keep_frac=0.01):
    """solid: (h, w) bool -> reachable air bool. Column model (see the module docstring),
    intersected with where the rolling ball fits, then only the connected pieces of it that
    are at least `keep_frac` of the largest: an air pocket sealed inside the ground, which
    Sonic 2 leaves non-solid because nothing can reach it, is dropped."""
    h, w = solid.shape
    n = JUMP_REACH // CELL
    near_floor = np.zeros_like(solid)
    for k in range(1, n + 1):
        near_floor[:-k] |= solid[k:]
    reach = near_floor & ~solid
    for r in range(1, h):                     # falling
        reach[r] |= reach[r - 1] & ~solid[r]
    reach &= _fits(~solid, 2, 3)
    lab, cnt = _components(reach)
    if cnt == 0:
        return reach
    sizes = np.bincount(lab.ravel())[1:]
    keep = np.flatnonzero(sizes >= keep_frac * sizes.max()) + 1
    return np.isin(lab, keep)


# ---------------------------------------------------------------------------- layout

def load(path):
    return load_spec_dict(json.loads(pathlib.Path(path).read_text()))


def load_spec_dict(spec):
    gw, gh = spec["grid"]
    spec["W"], spec["H"] = gw * SEC, gh * SEC
    bg = spec["bg_tiles"]
    blob_of = {}
    for name, zones in spec["blobs"].items():
        for z in zones:
            blob_of[z] = name
    spec["blob_of"] = blob_of
    spec["blob_tiles"] = {b: sum(bg[z] for z in zs) for b, zs in spec["blobs"].items()}
    return spec


def t_into(spec, frm, to):
    if spec["blob_of"][frm] == spec["blob_of"][to]:
        return WIPE_T
    chunks = math.ceil(spec["blob_tiles"][spec["blob_of"][to]] * 32 / CHUNK_BYTES)
    return chunks + WIPE_T + SLIP


def grids(spec):
    W, H = spec["W"] // CELL, spec["H"] // CELL
    player = np.zeros((H, W), dtype=bool)
    painted = np.zeros((H, W), dtype=bool)          # clip or connector cell (not void)
    for c in spec["clips"]:
        sx, sy, w, h = c["src"]
        dx, dy = c["dst"]
        sol = tree(c["tree"]).solid(sx, sy, w, h)
        r = reachable_air(sol)
        player[dy // CELL:(dy + h) // CELL, dx // CELL:(dx + w) // CELL] |= r
        painted[dy // CELL:(dy + h) // CELL, dx // CELL:(dx + w) // CELL] = True
    # NEUTRAL FILL: every act cell inside the clips' bounding box that no clip covers is
    # painted with the connector sheet (line 0, solid unless a lane crosses it). Outside
    # that box the act is void.
    bx = max(c["dst"][0] + c["src"][2] for c in spec["clips"]) // CELL
    by = max(c["dst"][1] + c["src"][3] for c in spec["clips"]) // CELL
    painted[:by, :bx] = True
    lanes = np.zeros((H, W), dtype=bool)
    for k in spec["connectors"]:
        x, y, w, h = k["rect"]
        painted[y // CELL:(y + h) // CELL, x // CELL:(x + w) // CELL] = True
        for lx, ly, lw, lh in k["lanes"]:
            player[ly // CELL:(ly + lh) // CELL, lx // CELL:(lx + lw) // CELL] = True
            lanes[ly // CELL:(ly + lh) // CELL, lx // CELL:(lx + lw) // CELL] = True
    return player, painted, lanes


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


def centres(spec, player):
    """Reachable camera centres, as an (H, W) bool on the cell grid (cell = centre px // 8)."""
    c = dilate(player, DZ_X // CELL, DZ_Y // CELL)
    H, W = c.shape
    ys, xs = np.nonzero(c)
    xs = np.clip(xs, HALF_W // CELL, (spec["W"] - HALF_W) // CELL - 1)
    ys = np.clip(ys, HALF_H // CELL, (spec["H"] - HALF_H) // CELL - 1)
    out = np.zeros_like(c)
    out[ys, xs] = True
    return out


def screen_gap(spec, zone, H, W):
    """(H, W) int: Chebyshev px from each centre's 320x224 screen to the zone's nearest clip
    rectangle; negative = on screen."""
    cx = (np.arange(W) * CELL + CELL // 2)[None, :]
    cy = (np.arange(H) * CELL + CELL // 2)[:, None]
    best = None
    for c in spec["clips"]:
        if c["zone"] != zone:
            continue
        x0, y0 = c["dst"]
        x1, y1 = x0 + c["src"][2], y0 + c["src"][3]
        gx = np.maximum(x0 - (cx + HALF_W), (cx - HALF_W) - x1)
        gy = np.maximum(y0 - (cy + HALF_H), (cy - HALF_H) - y1)
        g = np.maximum(gx, gy)
        best = g if best is None else np.minimum(best, g)
    return best


def region_all(spec):
    """(zones, gaps, vis, region) over EVERY act cell (reachable or not): the planned region
    of a camera centre there, by the rule in the module docstring."""
    H, W = spec["H"] // CELL, spec["W"] // CELL
    zones = sorted({c["zone"] for c in spec["clips"]})
    gaps = {z: screen_gap(spec, z, H, W) for z in zones}
    tmax = {z: max(t_into(spec, r, z) for r in zones if r != z) for z in zones}
    vis = np.stack([gaps[z] for z in zones]) < 0                 # (Z, H, W)
    nvis = vis.sum(axis=0)
    adj = np.stack([gaps[z] - STEP * tmax[z] for z in zones])
    region = np.argmin(adj, axis=0)
    # a visible zone always wins its region (a screen showing one zone IS in that zone)
    region = np.where(nvis == 1, np.argmax(vis, axis=0), region)
    return zones, gaps, vis, region


def mode_check(a):
    spec = load(a.layout)
    player, painted, lanes = grids(spec)
    cen = centres(spec, player)
    H, W = cen.shape
    zones, gaps, vis, region = region_all(spec)
    nvis = vis.sum(axis=0)
    mixed = cen & (nvis > 1)
    wrong = cen & (nvis >= 1) & ~vis[region, np.arange(H)[:, None], np.arange(W)[None, :]]
    print(f"act {spec['W']} x {spec['H']} px, {len(zones)} zones, "
          f"{int(cen.sum())} reachable camera centres (8-px grid)")
    print(f"MIXED  screens showing two zones: {int(mixed.sum())}")
    if mixed.any():
        ys, xs = np.nonzero(mixed)
        for i in range(0, len(ys), max(1, len(ys) // 6))[:6]:
            zs = [zones[k] for k in range(len(zones)) if vis[k, ys[i], xs[i]]]
            print(f"   e.g. centre ({xs[i] * CELL}, {ys[i] * CELL}) sees {zs}")
    print(f"WRONG  a zone on screen outside its region: {int(wrong.sum())}")
    # crossings: centre P in region Z with a reachable neighbour (within one 16-px step)
    # in region R != Z
    rows = {}
    # ENTRY PAIRS: P in region Z, its 8-px 4-neighbour Q in region R. The region boundary
    # lies between their centres, so s at the boundary is s(P) + CELL/2. CALIBRATION: with
    # that reading a connector cut to the rule (screen + 16 x (T_a + T_b)) reads slack 0 on
    # both sides, which is what the 12-run witness MEASURED at 384 px with T = 2 a side
    # (docs/research/2026-09-25-shorter-connector.md §8.4: 0 glitch frames, 0 frames of slack
    # at the camera cap). A negative slack here is therefore a connector shorter than the one
    # measured glitch-free, not a modelling margin.
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        if True:
            sh = np.roll(np.roll(region, dy, axis=0), dx, axis=1)
            shc = np.roll(np.roll(cen, dy, axis=0), dx, axis=1)
            edge = cen & shc & (sh != region)
            for zi, z in enumerate(zones):
                for ri, r in enumerate(zones):
                    if zi == ri:
                        continue
                    m = edge & (region == zi) & (sh == ri)
                    if not m.any():
                        continue
                    s = gaps[z][m] + CELL // 2
                    t = t_into(spec, r, z)
                    k = (r, z)
                    worst = int(s.min()) - STEP * t
                    if k not in rows or worst < rows[k][0]:
                        rows[k] = (worst, int(s.min()), t, int(m.sum()))
    print("CROSSINGS  (from -> into: T frames, screen distance at the crossing, slack)")
    bad = 0
    for (r, z), (slack, s, t, n) in sorted(rows.items()):
        flag = "ok" if slack >= 0 else "SHORT"
        bad += slack < 0
        print(f"   {r:4s} -> {z:4s}  T={t:2d}  s_min={s:5d} px  need {STEP * t:4d}  "
              f"slack {slack:+5d} px  {flag}")
    void_seen = 0
    lane_c = centres(spec, lanes) & cen
    if lane_c.any():
        ys, xs = np.nonzero(lane_c)
        vx0 = np.clip(xs - HALF_W // CELL, 0, W)
        vy0 = np.clip(ys - HALF_H // CELL, 0, H)
        unp = (~painted).astype(np.int64)
        ii = np.zeros((H + 1, W + 1), dtype=np.int64)
        np.cumsum(np.cumsum(unp, axis=0), axis=1, out=ii[1:, 1:])
        vx1 = np.clip(xs + HALF_W // CELL, 0, W)
        vy1 = np.clip(ys + HALF_H // CELL, 0, H)
        cnt = ii[vy1, vx1] - ii[vy0, vx1] - ii[vy1, vx0] + ii[vy0, vx0]
        void_seen = int((cnt > 0).sum())
    print(f"VOID   connector-lane centres whose screen shows unpainted act cells: {void_seen}")
    blobs = ", ".join(f"{b} {{{'+'.join(zs)}}} {spec['blob_tiles'][b]} tiles"
                      for b, zs in spec["blobs"].items())
    print(f"BG blobs: {blobs}")
    ok = not mixed.any() and not wrong.any() and bad == 0 and void_seen == 0
    print("VERDICT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def mode_edges(a):
    """For one candidate rect: how far past each edge a camera reachable INSIDE it sees, in px.
    Negative = the screen never reaches the edge (that much solid margin to spare)."""
    x, y, w, h = (int(v) for v in a.rect.split(","))
    sol = tree(a.tree).solid(x, y, w, h)
    r = reachable_air(sol)
    rc = dilate(r, DZ_X // CELL, DZ_Y // CELL)
    ys, xs = np.nonzero(rc)
    px = xs * CELL + CELL // 2
    py = ys * CELL + CELL // 2
    print(f"{a.tree} {a.rect}: reachable air {int(r.sum())} cells of {r.size}")
    print(f"  left   screen reaches {HALF_W - int(px.min()):5d} px past x=0")
    print(f"  right  screen reaches {int(px.max()) + HALF_W - w:5d} px past x={w}")
    print(f"  top    screen reaches {HALF_H - int(py.min()):5d} px past y=0")
    print(f"  bottom screen reaches {int(py.max()) + HALF_H - h:5d} px past y={h}")
    # per 256-px span along the bottom and top edges: deepest / highest reach
    for name, sel, fn in (("bottom", None, max), ("top", None, min)):
        prof = []
        for x0 in range(0, w, 256):
            m = (px >= x0) & (px < x0 + 256)
            if not m.any():
                prof.append("  -  ")
                continue
            v = int(py[m].max()) + HALF_H - h if name == "bottom" else HALF_H - int(py[m].min())
            prof.append(f"{v:+5d}")
        print(f"  {name} per 256 px: " + " ".join(prof))
    for name in ("left", "right"):
        prof = []
        for y0 in range(0, h, 256):
            m = (py >= y0) & (py < y0 + 256)
            if not m.any():
                prof.append("  -  ")
                continue
            v = HALF_W - int(px[m].min()) if name == "left" else int(px[m].max()) + HALF_W - w
            prof.append(f"{v:+5d}")
        print(f"  {name} per 256 px: " + " ".join(prof))


def _mixed_count(spec):
    player, painted, lanes = grids(spec)
    cen = centres(spec, player)
    H, W = cen.shape
    zones = sorted({c["zone"] for c in spec["clips"]})
    vis = np.stack([screen_gap(spec, z, H, W) < 0 for z in zones])
    return int((cen & (vis.sum(axis=0) > 1)).sum())


def mode_seal(a):
    """The shortest SEALED separation (no crossing, so no background time) between two clips:
    the smallest gap, in 16-px steps, at which no reachable camera in either clip shows both.
    `--below`: B is under A, left edges aligned plus --offset; default B is right of A, tops
    aligned plus --offset."""
    ta, ra = a.a.split(":")
    tb, rb = a.b.split(":")
    ra = [int(v) for v in ra.split(",")]
    rb = [int(v) for v in rb.split(",")]
    for gap in range(0, 1025, 16):
        if a.below:
            db = (a.offset, ra[3] + gap)
        else:
            db = (ra[2] + gap, a.offset)
        x0 = min(0, db[0])
        y0 = min(0, db[1])
        clips = [{"zone": "A", "tree": ta, "src": ra, "dst": [-x0, -y0]},
                 {"zone": "B", "tree": tb, "src": rb, "dst": [db[0] - x0, db[1] - y0]}]
        Wp = max(c["dst"][0] + c["src"][2] for c in clips) + 512
        Hp = max(c["dst"][1] + c["src"][3] for c in clips) + 512
        spec = {"W": (Wp + 7) // 8 * 8, "H": (Hp + 7) // 8 * 8, "clips": clips,
                "connectors": []}
        n = _mixed_count(spec)
        if n == 0:
            print(f"{a.a} {'over' if a.below else 'beside'} {a.b} (offset {a.offset}): "
                  f"sealed separation {gap} px (0 mixed screens); {gap - 16} px -> "
                  f"{prev} mixed" if gap else f"{a.a} / {a.b}: 0 px, they can touch")
            return 0
        prev = n
    print("no separation up to 1024 px")
    return 1


def mode_manifest(a):
    spec = load(a.layout)
    doc = {"schema": 1, "units": "world_px", "id": "s2_mega_act_woven_draft",
           "name": "WOVEN MEGA-ACT PROPOSAL (2026-09-27), clips only, a DRAFT for measurement",
           "note": "NOT AN ACT. The woven proposal's clip rectangles at their act positions, "
                   "with NO connectors: the manifest has no vertical shaft or cloud-band kind, "
                   "and a connector's art is one corridor sheet (see the report). Written by "
                   "docs/research/2026-09-27-mega-act-woven/woven.py manifest.",
           "act": {"grid_w": a.grid[0] if a.grid else spec["grid"][0],
                   "grid_h": a.grid[1] if a.grid else spec["grid"][1]}, "clips": []}
    for c in spec["clips"]:
        sx, sy, w, h = c["src"]
        dx, dy = c["dst"]
        donor, zone = c["tree"].split("/")
        doc["clips"].append({
            "id": c["id"], "donor": donor, "zone": zone,
            "src_rect": {"x": sx, "y": sy, "w": w, "h": h},
            "dst_rect": {"x": dx, "y": dy, "w": w, "h": h},
            "unaligned_dst_reason": "woven proposal placement (docs/research/"
                                    "2026-09-27-mega-act-woven.md)"})
    if a.tunnels:
        # ART STAND-INS for the horizontal tunnel lanes, so the bake places the tunnel sheet
        # (today's s2_ehz_cpz tunnel art) and N1 counts it. Each is inset 16 px from both
        # clips: K6 (seam ramp) refuses any corridor that TOUCHES Metropolis, Hidden Palace
        # or Oil Ocean (no plane-B floor, the v1 report's item 9), and it skips a void
        # neighbour column. Only the art matters here; the collision of a stand-in is not
        # the proposal's.
        doc["note"] += (" With --tunnels: the horizontal tunnels are ART STAND-INS inset "
                        "16 px from both clips (K6 refuses a tunnel touching MTZ/HPZ/OOZ).")
        doc["corridors"] = []
        for k in spec["connectors"]:
            if k["kind"] != "tunnel":
                continue
            x, y, w, h = k["lanes"][0]
            x0 = x + 64 + 16
            x1 = x + w - 64 - 16
            floor = (y + 96) // 16 * 16
            doc["corridors"].append({
                "id": f"standin_{k['id'].lower()}",
                "dst_rect": {"x": x0, "y": floor - 256, "w": x1 - x0, "h": 512},
                "floor_y": floor,
                "tunnel": {"ceiling_y": floor - 96, "art": {
                    "donor": "s2disasm", "zone": "CPZ",
                    "wall_src": {"x": 768, "y": 784, "w": 32, "h": 32},
                    "back_src": {"x": 512, "y": 896, "w": 32, "h": 32}}}})
    pathlib.Path(a.out).write_text(json.dumps(doc, indent=2) + "\n")
    print(a.out)


def mode_render(a):
    import render_woven
    render_woven.render(load(a.layout), a.out)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("check")
    p.add_argument("layout")
    p = sub.add_parser("edges")
    p.add_argument("tree")
    p.add_argument("rect")
    p = sub.add_parser("seal")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--below", action="store_true")
    p.add_argument("--offset", type=int, default=0)
    p = sub.add_parser("manifest")
    p.add_argument("layout")
    p.add_argument("--out", required=True)
    p.add_argument("--tunnels", action="store_true")
    p.add_argument("--grid", type=int, nargs=2, help="override the section grid (the bake's "
                   "inherited OJZ entity pass refuses a section count not a multiple of 3)")
    p = sub.add_parser("render")
    p.add_argument("layout")
    p.add_argument("--out", required=True)
    a = ap.parse_args()
    return {"check": mode_check, "edges": mode_edges, "manifest": mode_manifest,
            "render": mode_render, "seal": mode_seal}[a.mode](a)


if __name__ == "__main__":
    sys.exit(main() or 0)
