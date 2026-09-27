#!/usr/bin/env python3
"""fall_axis_b — read fall_legs.sh output (ojz_feel_probe JSONs with --cache and --dump) and
report, per leg: the fall (peak y_vel, frames airborne), the camera (peak step, lowest sprite
line), COLLISION RESIDENCY and the picture.

usage: fall_axis_b.py <legdir> [<legdir> ...]  [--trace LEG]

RESIDENCY, per recorded frame. The probe's snapshot sits after RunObjects and before
Camera_Update and Tile_Cache_Fill (ojz-feel.md, method notes), so the cache words it reads are
the ring the player's own move saw, and the position is where that move put him. The floor
probe's lowest read is one collision cell under the feet (player_sensors.emp probe_core, the
forward cell); it must fall inside the collision the ring has WRITTEN:
    B = Cache_Bottom_Row, or Cache_Fill_RowResume_Row - 1 when a partial row pending below the
        player cuts it (engine/level/collision_lookup.emp Collision_ResidentBottom's rule)
    frontier = ((B + 1) & ~1) * 8        (collision is copied on a cell's odd row only)
    margin   = frontier - (py + yr + 16) - 1   (>= 0: every probe read is resident)
yr is the state's radius: 19 uncurled (PSTATE_AIR/GROUND = 6/0), 14 curled (every other air
state here, and ROLL). A frame with margin < 0 is a BLACKOUT: a probe there reads a row the
ring has not written (AIR past the window, or a stale slot inside it).

THE PICTURE: --dump's coverage per on-time tick = visible columns/rows the plane streamer has
NOT drawn [right, left, bottom, top]; any > 0 is a hole on screen (ehz_run_probe's rule).
LAG: sum(dFrame_Counter) - sum(dLogic_Tick) over the leg.

SCREEN LINE: the snapshot's camera is one tick behind its player (method notes), so the line
printed is py - cy of the SAME snapshot, i.e. against the previous tick's camera — the line
Player_FallLimit's screen hold tests (camY_prev + 224 - yr). The drawn line is that minus the
camera's step that tick.
"""
import json
import sys
from pathlib import Path

CURLED_STATES = {2, 8, 10, 12}      # ROLL, JUMP, ROLLJUMP, AIRBALL (games/sonic4/config/constants.emp)
YR_STAND, YR_CURL = 19, 14


def frontier(bottom, resume, py):
    b = bottom
    if resume not in (-1, 0xFFFF) and resume <= bottom and resume > (py >> 3):
        b = resume - 1
    return ((b + 1) & ~1) * 8


def leg_report(path, trace=False):
    h = json.loads(Path(path).read_text())
    rows, cache = h["rows"], {c[0]: c for c in h.get("cache", [])}
    fc = sum(r[1] for r in rows)
    lt = sum(r[2] for r in rows)
    peak_v, air_frames, low_line, peak_step, prev_cy = 0, 0, -999, 0, None
    worst, blackout = None, 0
    for r in rows:
        i, dfc, dlt, dlag, cx, cy, px, py, xv, yv, st, si = r
        peak_v = max(peak_v, yv)
        if prev_cy is not None:
            peak_step = max(peak_step, abs(cy - prev_cy))
        prev_cy = cy
        low_line = max(low_line, py - cy)
        c = cache.get(i)
        if c:
            _, left, head, top, bottom, rcol, budget, rrow = c
            yr = YR_CURL if st in CURLED_STATES else YR_STAND
            m = frontier(bottom & 0xFFFF, rrow & 0xFFFF, py) - (py + yr + 16) - 1
            if worst is None or m < worst[0]:
                worst = (m, i, py, cy, yv, bottom, rrow)
            blackout += m < 0
            if trace:
                print(f"  {i:5d} cy {cy:5d} py {py:5d} line {py - cy:4d} yv {yv:6d} ({yv / 256:5.1f}) "
                      f"st {st:2d} bottom {bottom} rrow {rrow} margin {m}")
    holes = [(k, v) for k, v in h.get("dumps", {}).items() if max(v[5]) > 0]
    hole_rows = sum(max(0, v[5][2]) + max(0, v[5][3]) for _, v in holes)
    hole_cols = sum(max(0, v[5][0]) + max(0, v[5][1]) for _, v in holes)
    return dict(leg=Path(path).stem, crc=h["crc"], frames=fc, ticks=lt, lag=fc - lt,
                peak_yvel=peak_v, peak_cam_step=peak_step, lowest_line=low_line,
                resid_min_margin=None if worst is None else worst[0],
                resid_worst=worst, blackout_frames=blackout,
                dumped_ticks=len(h.get("dumps", {})), hole_ticks=len(holes),
                undrawn_rows=hole_rows, undrawn_cols=hole_cols)


def main():
    a = sys.argv[1:]
    trace = None
    if "--trace" in a:
        k = a.index("--trace")
        trace = a[k + 1]
        del a[k:k + 2]
    print(f"{'dir':<22} {'leg':<12} {'crc':<9} {'frames':>6} {'lag':>4} {'peak yv':>8} "
          f"{'cam step':>8} {'low line':>8} {'min margin':>10} {'blackout':>8} {'hole ticks':>10} "
          f"{'undrawn rows':>12} {'undrawn cols':>12}")
    for d in a:
        for p in sorted(Path(d).glob("*.json")):
            if p.name.endswith(".server.log"):
                continue
            r = leg_report(p, trace == p.stem)
            print(f"{Path(d).name:<22} {r['leg']:<12} {r['crc']:<9} {r['frames']:>6} {r['lag']:>4} "
                  f"{r['peak_yvel'] / 256:>8.1f} {r['peak_cam_step']:>8} {r['lowest_line']:>8} "
                  f"{str(r['resid_min_margin']):>10} {r['blackout_frames']:>8} {r['hole_ticks']:>10} "
                  f"{r['undrawn_rows']:>12} {r['undrawn_cols']:>12}")


if __name__ == "__main__":
    main()
