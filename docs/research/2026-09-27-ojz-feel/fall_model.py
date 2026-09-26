#!/usr/bin/env python3
"""fall_model — a straight fall from rest under four rule sets, frame by frame.

usage: fall_model.py [HEIGHT ...]   (default 1024 2048 5400)

Each rule set is its source's own arithmetic, cited, not a fit:
  aeon   y_vel 8.8, ObjectMove THEN gravity $38 THEN clamp to PHYS_FALL_CAP $F00
         (games/sonic4/player/player_air.emp PState_AirShared step 4; engine/system/constants.emp
         PHYS_FALL_CAP). Camera after objects (ojz_scroll_test.emp: RunObjects, then
         Camera_Update): focal = camY + CAM_SCREEN_HALF_H 112, deadzone +-CAM_Y_DEADZONE 32,
         step capped at CAM_MAX_Y_STEP 16 (engine/level/camera.emp .y_track .. .apply_y).
  s3k    MoveSprite: move by old y_vel, then y_vel += $38, no clamp (sonic3k.asm:36035, reached
         from Sonic_MdAir:22354 via MoveSprite_TestGravity:36071). MoveCameraY (sonic3k.asm:38438)
         airborne: bias Distance_from_top $60 (sonic3k.asm:38088), window +-$20 (:38460, :38463),
         step capped at $1800 = 24 px (:38511). Camera after objects.
  s2     ObjectMoveAndFall (s2.asm:29942), no clamp (Obj01_MdAir s2.asm:36163). ScrollVerti
         (s2.asm:18112): bias (224/2)-16 = 96 (s2.asm:14688), window +-$20 (:18141, :18144),
         cap 16<<8 (:18190).
  sce    S.C.E.: as s3k but y_vel clamped to $1000 after gravity (Objects/Players/Sonic/
         Sonic.asm:435-437); S.C.E.'s camera is S3K's (24 px), not modelled separately.
Prints per height: frames to fall it, landing speed (px/frame), the player's lowest on-screen
sprite-centre line while falling, and frames spent at a clamp (fall cap or camera cap).
"""
import sys


def run(rule, H):
    y = 0 << 16          # 16.16 player y
    v = 0                # 8.8 y_vel
    cam = (0 - {"aeon": 112, "s3k": 96, "s2": 96, "sce": 96}[rule]) << 16
    f, low, capped, camcap = 0, 0, 0, 0
    while (y >> 16) < H:
        y += v << 8
        v += 0x38
        if rule == "aeon" and v > 0xF00:
            v, capped = 0xF00, capped + 1
        if rule == "sce" and v > 0x1000:
            v, capped = 0x1000, capped + 1
        py, cy = y >> 16, cam >> 16
        if rule == "aeon":
            d = py - (cy + 112)
            if d > 32:
                st = d - 32
                if st > 16:
                    st, camcap = 16, camcap + 1
                cam += st << 16
        else:
            capv = 16 if rule == "s2" else 24
            d = py - cy - 96 + 32
            if d >= 0:
                d -= 64
                if d >= 0:
                    st = d
                    if st > capv:
                        st, camcap = capv, camcap + 1
                    cam += st << 16
        low = max(low, py - (cam >> 16))
        f += 1
    return f, v / 256, low, capped, camcap


hs = [int(x) for x in sys.argv[1:]] or [1024, 2048, 5400]
print(f"{'height':>6} {'rule':<5} {'frames':>6} {'seconds':>7} {'land px/f':>9} {'lowest scr y':>12} "
      f"{'frames at fall cap':>18} {'frames camera capped':>20}")
for H in hs:
    for rule in ("aeon", "sce", "s2", "s3k"):
        f, vl, low, cap, cc = run(rule, H)
        print(f"{H:>6} {rule:<5} {f:>6} {f / 60:>7.2f} {vl:>9.2f} {low:>12} {cap:>18} {cc:>20}")
