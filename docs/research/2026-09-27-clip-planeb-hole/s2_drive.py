#!/usr/bin/env python3
"""RESEARCH PROBE (not a gate, no runner): the same drives as planeb_hole_drive.py, in REAL
Sonic 2 (an s2disasm REV01 build, SHA-1 8bca5dcef1af3e00098666fd892dc1c2a76333f9) under Genesis
Plus GX, headless, through tools/s2_music_balance.py's ctypes libretro frontend.

PLACEMENT is Sonic 2's own starpost restart, so the camera, the object manager (and with it
every Obj03 line and the Obj11 bridge) and the player's path bits are initialised by the game
itself, not poked into a running level: boot to Emerald Hill act 1 (START pulsed until
Game_Mode reads $0C), then write the Saved_* block Obj79_SaveData writes (s2.asm:44261), set
Last_star_pole_hit and raise Level_Inactive_flag, which makes Level_MainLoop restart the level
(s2.asm:5092) and LevelSizeLoad call Obj79_LoadData (s2.asm:14754). Saved_Solid_bits is the
path: $0C0D = path A (primary), $0E0F = path B (secondary) (s2.asm:44269, 44316).

Per frame it records x, y, the path (top_solid_bit $0C -> A, $0E -> B), in-air, the routine
(6 = dead), ground speed, and FLOOR: the first landing surface at or below the feet in this
column on the current path, read from the donor's chunks + collision indices + height array
(s2_paths.py's reader). It also lists which objects are loaded near the player (Obj11 = bridge).

    python3 docs/research/2026-09-27-clip-planeb-hole/s2_drive.py --s2-rom PATH/s2built.bin \\
        --x 4500 --feet 655 --dir left --gsp 0x600 --frames 900
"""
import argparse
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "tools"))
import s2_music_balance as MB                              # noqa: E402
import s2_donor as D                                       # noqa: E402

GAME_MODE, LEVEL = 0xF600, 0x0C
LEVEL_INACTIVE = 0xFE02
LAST_STAR, SAVED_LAST_STAR = 0xFE30, 0xFE31
SAVED_X, SAVED_Y, SAVED_ART, SAVED_SOLID = 0xFE32, 0xFE34, 0xFE3C, 0xFE3E
SAVED_CAM_X, SAVED_CAM_Y, SAVED_CAM_MAXY = 0xFE40, 0xFE42, 0xFE56
SAVED_DYN = 0xFE58
CAM_MAXY, DYN = 0xEECE, 0xEEDF
ZONEACT = 0xFE10
SONIC = 0xB000
X, Y, YVEL, INERTIA, STATUS, ROUTINE, ART, TOPSOLID = 8, 0xC, 0x12, 0x14, 0x22, 0x24, 2, 0x3E
INVULN = 0x30
OBJ_RAM, OBJ_SLOTS, OBJ_SIZE = 0xB000, 0x80, 0x40
PATH = {0x0C: "A", 0x0E: "B"}
J_B, J_DOWN, J_LEFT, J_RIGHT = 0, 5, 6, 7   # libretro joypad ids (GPGX: RETRO_B -> Genesis B)

chunks, grid, ia, ib = D.collision_inputs("EHZ", "s2disasm")
prof, _ = D.collision_arrays("s2disasm")


def cell(x, y, path):
    if y < 0 or y // 128 >= grid.shape[0]:
        return 0, 0, 0
    ch = grid[y // 128][x // 128]
    w = chunks[ch][((y % 128) // 16) * 8 + (x % 128) // 16]
    blk, xf, yf = w & 0x3FF, (w >> 10) & 1, (w >> 11) & 1
    sol = (w >> (12 if path == "A" else 14)) & 3
    idx = (ia if path == "A" else ib)[blk]
    col = 15 - (x % 16) if xf else x % 16
    h = prof[idx * 16 + col]
    h = h - 256 if h > 127 else h
    return sol, idx, (-h if yf else h)


def floor_below(x, y, path):
    """First landing surface at or below y in column x (top-solid, positive height)."""
    for cy in range(max(0, y) // 16 * 16, grid.shape[0] * 128, 16):
        sol, idx, h = cell(x, cy, path)
        if sol & 1 and idx and h > 0 and cy + 16 - h >= y:
            return cy + 16 - h
    return None


class S2:
    def __init__(self, rom):
        self.c = MB.Core({})
        self.c.load(rom)

    def w8(self, a, v):
        self.c.wr(a, v)

    def w16(self, a, v):
        self.c.wr(a, (v >> 8) & 0xFF)
        self.c.wr(a + 1, v & 0xFF)

    def r8(self, a):
        return self.c.rd(a)

    def r16(self, a):
        return self.c.rd(a) << 8 | self.c.rd(a + 1)

    def s16(self, a):
        v = self.r16(a)
        return v - 0x10000 if v >= 0x8000 else v


def boot(s):
    f = 0
    while s.r8(GAME_MODE) != LEVEL:
        s.c.buttons = (1 << 3) if (f % 40) < 4 else 0
        s.c.run()
        f += 1
        if f > 2400:
            raise SystemExit("s2_drive: real S2 never reached a level")
    s.c.buttons = 0
    s.c.run(120)
    if s.r16(ZONEACT) != 0x0000:
        raise SystemExit(f"s2_drive: not Emerald Hill act 1 (zone/act ${s.r16(ZONEACT):04X})")


def place(s, x, feet, path):
    y = feet - 19
    s.w8(SAVED_LAST_STAR, 1)
    s.w8(LAST_STAR, 1)
    s.w16(SAVED_X, x)
    s.w16(SAVED_Y, y)
    s.w16(SAVED_ART, s.r16(SONIC + ART))
    s.w16(SAVED_SOLID, 0x0C0D if path == "A" else 0x0E0F)
    s.w16(SAVED_CAM_X, max(0, x - 160))
    s.w16(SAVED_CAM_Y, max(0, y - 96))
    s.w16(SAVED_CAM_MAXY, s.r16(CAM_MAXY))
    s.w8(SAVED_DYN, s.r8(DYN))
    s.w16(LEVEL_INACTIVE, 1)
    # Measured: the restart takes ~175 frames to Game_Mode $0C (title card flag clear).
    for _ in range(900):
        s.c.run()
        if s.r16(LEVEL_INACTIVE) == 0 and s.r8(GAME_MODE) == LEVEL:
            break
    else:
        raise SystemExit("s2_drive: the starpost restart never returned to the level")
    for _ in range(60):                 # settle, the player lands
        shield(s)
        s.c.run()
    return s.r16(SONIC + X), s.r16(SONIC + Y), PATH.get(s.r8(SONIC + TOPSOLID), "?")


def shield(s):
    """Keep the post-hit invulnerability timer up, so a badnik (Coconuts sits at (1831, 480),
    right over the first drive, and killed it with 0 rings) cannot end a drive. It only makes
    touch response ignore hurts; it does not change movement or collision."""
    s.w16(SONIC + INVULN, 0x78)


def objects_near(s, x0, x1):
    out = []
    for i in range(OBJ_SLOTS):
        a = OBJ_RAM + i * OBJ_SIZE
        oid = s.r8(a)
        if oid and x0 <= s.r16(a + X) < x1:
            out.append((f"${oid:02X}", s.r16(a + X), s.r16(a + Y)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--s2-rom", required=True)
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--feet", type=int, required=True, help="the ground's y under x")
    ap.add_argument("--path", choices=("A", "B"), default="A")
    ap.add_argument("--dir", choices=("left", "right"), default="left")
    ap.add_argument("--gsp", default="none", help="none | <int>, injected once (S2 inertia)")
    ap.add_argument("--jump-at", type=int, nargs="*")
    ap.add_argument("--jump-x", type=int, nargs="*")
    ap.add_argument("--spindash-when-stuck", type=int, default=0)
    ap.add_argument("--spindash-max", type=int, default=3)
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--stop-x", type=int)
    ap.add_argument("--label", default="")
    ap.add_argument("--json")
    a = ap.parse_args()

    s = S2(a.s2_rom)
    boot(s)
    lx, ly, lpath = place(s, a.x, a.feet, a.path)
    held = 1 << (J_LEFT if a.dir == "left" else J_RIGHT)
    s.c.buttons = held
    if a.gsp != "none":
        v = int(a.gsp, 0)
        s.w16(SONIC + INERTIA, (-v if a.dir == "left" else v) & 0xFFFF)
    jumps = set(a.jump_at or [])
    jump_x = sorted(a.jump_x or [], reverse=(a.dir == "left"))
    stuck, dashes, dash_from = 0, 0, None
    rows, bridge_seen = [], set()
    for f in range(a.frames):
        if rows:
            r = rows[-1]
            past = (lambda X: r["x"] <= X) if a.dir == "left" else (lambda X: r["x"] >= X)
            if jump_x and past(jump_x[0]) and not r["air"]:
                jump_x.pop(0)
                jumps.add(f)
            if a.spindash_when_stuck and dash_from is None:
                moved = len(rows) > 1 and rows[-2]["x"] != r["x"]
                stuck = stuck + 1 if (not r["air"] and abs(r["gsp"]) < 64 and not moved) else 0
                if stuck >= a.spindash_when_stuck and dashes < a.spindash_max:
                    dashes, stuck, dash_from = dashes + 1, 0, f
        btn = held | ((1 << J_B) if any(0 <= f - j < 12 for j in jumps) else 0)
        if dash_from is not None:           # the same spindash script as planeb_hole_drive
            k = f - dash_from
            btn = 1 << J_DOWN
            if k in range(4, 7) or k in range(10, 13) or k in range(16, 19):
                btn |= 1 << J_B
            if k >= 24:
                btn = held if k >= 26 else 0
            if k >= 26:
                dash_from = None
        s.c.buttons = btn
        shield(s)
        s.c.run()
        x, y = s.r16(SONIC + X), s.r16(SONIC + Y)
        path = PATH.get(s.r8(SONIC + TOPSOLID), f"?{s.r8(SONIC + TOPSOLID):02X}")
        air = bool(s.r8(SONIC + STATUS) & 2)
        rt = s.r8(SONIC + ROUTINE)
        fl = floor_below(x, y + 19, path) if path in ("A", "B") else None
        if 1300 <= x < 1600:
            for o in objects_near(s, 1300, 1600):
                if o[0] == "$11":
                    bridge_seen.add(o)
        rows.append({"f": f, "x": x, "y": y, "path": path, "air": air, "routine": rt,
                     "gsp": s.s16(SONIC + INERTIA), "yvel": s.s16(SONIC + YVEL), "floor": fl})
        if rt >= 6 or y >= 1100 or (a.stop_x is not None and (
                (a.dir == "left" and x <= a.stop_x) or (a.dir == "right" and x >= a.stop_x))):
            break
    flips = [(q["f"], p["x"], q["x"], q["y"], p["path"], q["path"])
             for p, q in zip(rows, rows[1:]) if p["path"] != q["path"]]
    hole = [r for r in rows if 1344 <= r["x"] < 1408]
    last = rows[-1]
    print(f"{a.label} S2 start x {a.x} feet {a.feet} path {a.path} -> placed ({lx}, {ly}) path "
          f"{lpath}; dir {a.dir} gsp {a.gsp} jump {a.jump_at}")
    print(f"  frames {len(rows)}  x {min(r['x'] for r in rows)}..{max(r['x'] for r in rows)}  "
          f"y {min(r['y'] for r in rows)}..{max(r['y'] for r in rows)}")
    print(f"  path changes {len(flips)}: " + "; ".join(
        f"f{f} x {x0}->{x1} y {y} {p0}->{p1}" for f, x0, x1, y, p0, p1 in flips))
    print(f"  frames with x in 1344..1407: {len(hole)} (path B: "
          f"{sum(1 for r in hole if r['path'] == 'B')}, airborne: "
          f"{sum(1 for r in hole if r['air'])}, no floor below on the current path: "
          f"{sum(1 for r in hole if r['floor'] is None)}); bridge objects seen: "
          f"{sorted(bridge_seen)}")
    print(f"  end: x {last['x']} y {last['y']} path {last['path']} air {last['air']} routine "
          f"{last['routine']} gsp {last['gsp']} floor {last['floor']}  DIED/FELL: "
          f"{'YES' if last['routine'] >= 6 or last['y'] >= 1100 else 'no'}")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps({"args": vars(a), "placed": [lx, ly, lpath],
                                                    "rows": rows}))
    print("finished=1")


if __name__ == "__main__":
    main()
