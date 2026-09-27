#!/usr/bin/env python3
"""fall_model_s3k — a straight fall from rest, frame by frame, under the rule sets FALL-FEEL weighs.

usage: fall_model_s3k.py [--trace RULE HEIGHT] [HEIGHT ...]   (default 512 1024 2048 5400)

2026-09-27, feel/s3k-fall. Extends docs/research/2026-09-27-ojz-feel/fall_model.py (same
integration order, same camera arithmetic) with the rules this parcel builds. Every constant is
the source's own, cited:

  before  y_vel 8.8: ObjectMove, then gravity $38, then clamp to PHYS_FALL_CAP $F00
          (games/sonic4/player/player_air.emp PState_AirShared step 4). Camera after objects
          (ojz_scroll_test.emp: RunObjects, Camera_Update, Tile_Cache_Fill): focal camY + 112
          (CAM_SCREEN_HALF_H), deadzone +-32 (CAM_Y_DEADZONE), step cap 16 (CAM_MAX_Y_STEP).
  s3k     MoveSprite (sonic3k.asm:36035): move by the old y_vel, y_vel += $38, no clamp.
          MoveCameraY airborne (sonic3k.asm:38458-38463, :38511): bias $60 (:38088), window
          +-$20, step cap $1800 = 24 px.
  free    this parcel with no residency guard: s3k physics, OUR focal 112 and deadzone 32, the
          airborne step cap 24. Shows where the player would leave the collision ring.
  ring    free + the residency guard: the move may not put the floor probe's lowest read
          (feet + 16, the probe core's one forward cell) at or past the FILLED collision
          frontier. Frontier = the ring the PREVIOUS tick's fill left (order above): bottom row
          B = ((camY_prev + SECTION_V_REACH_PX 231) >> 3) + TILE_CACHE_MARGIN_V 16, collision
          complete through cell floor((B+1)/2) - 1 (collision is copied on the odd, cell-
          completing row only: tile_cache.emp TileCache_FillRow), so frontier_px =
          ((B+1) & ~1) * 8. When held, the POSITION waits and y_vel is left alone (gravity
          keeps adding, as S3K's would): the landing speed is S3K's, the arrival is later.
          Assumes the fill keeps the ring AT the camera (VFILL_ROWS_PER_FRAME*8 >= 24).
  screen  ring + a visibility hold: the sprite's bottom (centre + y_radius) may not pass the
          bottom of the screen the previous camera showed (camY_prev + 224).

Feet = centre + 19 (PLAYER_Y_RADIUS, the uncurled AIR box a walk-off falls in).
Prints per height: frames, seconds, landing speed, the lowest sprite-centre screen line, frames
the player's centre was below the screen (line >= 224 + 19: sprite wholly off), frames held,
and the largest per-frame Y step (the layer lines' step bound reads this).
"""
import sys

G, CAP = 0x38, 0xF00
YR = 19
FOCAL = {"before": 112, "s3k": 96, "free": 112, "ring": 112, "screen": 112}


def frontier(cam_prev):
    b = ((cam_prev + 231) >> 3) + 16
    return ((b + 1) & ~1) * 8


def run(rule, H, trace=None):
    y, v = 0, 0                      # 16.16 player centre, 8.8 y_vel
    cam = -FOCAL[rule] << 16
    f = low = off = held = maxstep = 0
    while (y >> 16) < H:
        cy_prev = cam >> 16
        y_old = y
        ny = y + (v << 8)
        v += G
        if rule == "before" and v > CAP:
            v = CAP
        if rule in ("ring", "screen"):
            lim = frontier(cy_prev) - 17 - YR          # centre max: feet + 16 <= frontier - 1
            if rule == "screen":
                lim = min(lim, cy_prev + 224 - YR)
            if (ny >> 16) > lim:
                ny = lim << 16                        # position waits; y_vel is left alone
                held += 1
        y = ny
        maxstep = max(maxstep, (y - y_old) >> 16)
        py, cy = y >> 16, cam >> 16
        if rule == "before":
            d = py - (cy + 112)
            if d > 32:
                cam += min(d - 32, 16) << 16
        elif rule == "s3k":
            d = py - cy - 96 + 32
            if d >= 0:
                d -= 64
                if d >= 0:
                    cam += min(d, 24) << 16
        else:
            d = py - (cy + 112)
            if d > 32:
                cam += min(d - 32, 24) << 16
        line = py - (cam >> 16)
        low = max(low, line)
        off += line >= 224 + YR
        f += 1
        if trace == (rule, H):
            fr = frontier(cam >> 16)
            print(f"{f:4d} y={py:5d} yv={v:5d}({v / 256:5.1f}) cam={cam >> 16:5d} line={line:4d} "
                  f"probe_low={py + YR + 16:5d} frontier_next={fr:5d}")
    return f, v / 256, low, off, held, maxstep


def main():
    a = sys.argv[1:]
    if a[:1] == ["--trace"]:
        run(a[1], int(a[2]), trace=(a[1], int(a[2])))
        return
    hs = [int(x) for x in a] or [512, 1024, 2048, 5400]
    print(f"{'height':>6} {'rule':<6} {'frames':>6} {'sec':>5} {'land px/f':>9} {'lowest line':>11} "
          f"{'frames off-screen':>17} {'frames held':>11} {'max step':>8}")
    for H in hs:
        for rule in ("before", "s3k", "free", "ring", "screen"):
            f, vl, low, off, held, ms = run(rule, H)
            print(f"{H:>6} {rule:<6} {f:>6} {f / 60:>5.2f} {vl:>9.2f} {low:>11} {off:>17} {held:>11} {ms:>8}")


if __name__ == "__main__":
    main()
