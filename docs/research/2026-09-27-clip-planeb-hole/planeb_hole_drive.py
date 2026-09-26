#!/usr/bin/env python3
"""RESEARCH PROBE (not a gate, no runner): can the player reach the S2 clip act's plane-B hole
at x 1344..1407 (Emerald Hill's bridge pit seen from path B) and fall through it?

Same harness and placement as docs/research/2026-09-26-s2clip-loops-planes/loop_plane_probe.py
(headless tools/aether_instance; B press out of DEBUG free flight; the Debug_Warp_Consume
mailbox on a DEBUG ROM, a camera write on the plain ROM; pin, land, check grounded). Then it
optionally forces the layer byte, holds a direction, optionally injects a ground speed and
optionally presses A (jump) at given frames, and records per frame:

    x, y, layer (Sst.layer, read from the ROM), state, ground speed, y_vel, and FLOOR: the
    first landing surface at or below the player's feet in his current column ON HIS CURRENT
    LAYER, measured on the clip's own converted collision planes (clip_manifest.collision_grids,
    the grids the clip bake writes into the ROM), not on the donor.

A run ends when the player's y passes --fall-y (default 1100: the painted band ends at 1024 in
Emerald Hill, so a centre past 1100 is under the world) or the frame budget runs out.

    python3 docs/research/2026-09-27-clip-planeb-hole/planeb_hole_drive.py \\
        --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst \\
        --manifest games/sonic4/data/clips/s2_ehz_cpz/clips.json \\
        --x 4500 --y-from 600 --dir left --gsp top --frames 600 --json out.json
"""
import argparse
import asyncio
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
import loop_step_over_witness as L                         # noqa: E402
import tunnel_run_witness as T                             # noqa: E402
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402
import clip_manifest as CM                                 # noqa: E402
import collision_pipeline as CP                            # noqa: E402

HOLE = (1344, 1408)


class Floors:
    """First landing surface at or below y in column x, per plane, on the clip's own grids."""

    def __init__(self, act):
        self.planes = CM.collision_grids(act)
        self.hm, _ = CM._bank(CM.collision_banks(act))

    def floor(self, x, y, plane):
        g = self.planes[plane]
        act_h = g.shape[0] // 2 * 16
        cy = max(0, y) // 16 * 16
        while cy < act_h:
            h = CM._word_heights(int(g[cy // 16 * 2, x // 8]), self.hm)
            if h is not None:
                for yy in range(max(cy, y), cy + 16):
                    if CP.covers(h[x % 16], yy % 16):
                        return yy
            cy += 16
        return None


async def run(sock, syms, equs, act, a, floors):
    feet = T.ground_y(act, a.x, a.y_from)
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    client = BusClient(socket_path=sock, client_id="pbh", client_name="planeb-hole-drive")
    await client.connect()
    b = L.Bus(client)
    P = syms["Player_1"]
    A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    A_YVEL, A_LAYER = P + equs["SST_y_vel"], P + equs["SST_layer"]
    A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG
    A_STATE = P + T.PL_STATE_OFF
    grounded = {equs["PSTATE_GROUND"], equs["PSTATE_ROLL"]}

    await client.call("emulator/reset", {})
    await b.frames(240)
    await b.check_alive("boot")
    dbg_before = (await b.read(A_DBG, 1))[0]
    if dbg_before:
        await client.call("emulator/press", {"buttons": ["b"]})
        await b.frames(4)
    if (await b.read(A_DBG, 1))[0]:
        raise SystemExit("planeb_hole_drive: still in debug free-flight after the B press")
    if "Warp_Req_Flag" in syms:
        placement = "warp mailbox"
        await b.write(syms["Warp_Req_X"], a.x, 2)
        await b.write(syms["Warp_Req_Y"], feet - radius - 2, 2)
        await b.write(syms["Warp_Req_Flag"], 1, 1)
        for _ in range(240):
            await b.frames(1)
            if (await b.read(syms["Warp_Req_Flag"], 1))[0] == 0:
                break
        else:
            raise SystemExit("planeb_hole_drive: the warp mailbox never acked")
        await b.check_alive("warp")
    else:
        placement = "camera write"
        await b.write(syms["Camera_X"], (a.x - 160) << 16, 4)
        await b.write(syms["Camera_Y"], (feet - radius - 112) << 16, 4)
    for _ in range(T.PIN_FRAMES):
        await b.write(A_X, a.x << 16, 4)
        await b.write(A_Y, (feet - radius - 2) << 16, 4)
        await b.write(A_YVEL, 0, 2)
        await b.write(A_GSP, 0, 2)
        await b.frames(1)
    await b.frames(L.LAND_FRAMES * 4)
    await b.check_alive("placement")
    if (await b.read(A_STATE, 1))[0] not in grounded:
        raise SystemExit(f"planeb_hole_drive: the player never landed at x={a.x} (feet {feet})")
    landed_layer = (await b.read(A_LAYER, 1))[0]
    if a.force_layer is not None:
        await b.write(A_LAYER, a.force_layer, 1)
    landed = [int.from_bytes(await b.read(A_X, 4), "big") >> 16,
              int.from_bytes(await b.read(A_Y, 4), "big") >> 16]

    await client.call("emulator/hold", {"buttons": [a.dir], "down": True})
    if a.gsp != "none":
        v = equs["PHYS_TOP_SPEED"] if a.gsp == "top" else (
            equs["PHYS_GSP_CAP"] if a.gsp == "cap" else int(a.gsp, 0))
        await b.write(A_GSP, (v if a.dir == "right" else -v) & 0xFFFF, 2)
    jumps = set(a.jump_at or [])
    # A real spindash (no injected speed): let go of the direction, hold DOWN, tap A three
    # times, let go of DOWN (the release fires it), then hold the direction again.
    sd = {}
    for s0 in (a.spindash_at or []):
        sd[s0] = [("hold", a.dir, False), ("hold", "down", True)]
        for k in (4, 10, 16):
            sd.setdefault(s0 + k, []).append(("hold", "a", True))
            sd.setdefault(s0 + k + 3, []).append(("hold", "a", False))
        sd.setdefault(s0 + 24, []).append(("hold", "down", False))
        sd.setdefault(s0 + 26, []).append(("hold", a.dir, True))
        if a.idle_before_dash:              # let go of the direction first, so he settles
            sd.setdefault(s0 - a.idle_before_dash, []).append(("hold", a.dir, False))
        if a.jump_after_dash is not None and s0 == a.spindash_at[0]:   # the first dash only
            jumps.add(s0 + 24 + a.jump_after_dash)
    # Position/state-triggered actions (the plain and DEBUG shapes do not tick on the same
    # frames, so a frame-numbered input lands at different places in the two):
    #   --jump-x X      jump the first frame the player is at or past X in the held direction
    #   --spindash-when-stuck N   spindash once the player has been grounded at |gsp| < 64
    #                   without moving for N frames (the "walked into an uphill he cannot
    #                   climb from standstill" case), at most --spindash-max times
    jump_x = sorted(a.jump_x or [], reverse=(a.dir == "left"))
    stuck, dashes = 0, 0
    rows = []
    for f in range(a.frames):
        if rows and "x" in rows[-1]:
            r = rows[-1]
            past = (lambda X: r["x"] <= X) if a.dir == "left" else (lambda X: r["x"] >= X)
            if jump_x and past(jump_x[0]) and r["grounded"]:
                jump_x.pop(0)
                jumps.add(f)
            if a.spindash_when_stuck:
                moved = len(rows) > 1 and "x" in rows[-2] and rows[-2]["x"] != r["x"]
                stuck = stuck + 1 if (r["grounded"] and abs(r["gsp"]) < 64 and not moved) else 0
                if stuck >= a.spindash_when_stuck and dashes < a.spindash_max:
                    dashes += 1
                    stuck = -40
                    for k, v in list({0: [("hold", a.dir, False), ("hold", "down", True)],
                                      4: [("hold", "a", True)], 7: [("hold", "a", False)],
                                      10: [("hold", "a", True)], 13: [("hold", "a", False)],
                                      16: [("hold", "a", True)], 19: [("hold", "a", False)],
                                      24: [("hold", "down", False)],
                                      26: [("hold", a.dir, True)]}.items()):
                        sd.setdefault(f + k, []).extend(v)
                    if a.jump_after_dash is not None:       # D frames after DOWN is let go
                        jumps.add(f + 24 + a.jump_after_dash)
        for _, btn, down in sd.get(f, []):
            await client.call("emulator/hold", {"buttons": [btn], "down": down})
        if f in jumps:
            await client.call("emulator/hold", {"buttons": ["a"], "down": True})
        if f - 12 in jumps:
            await client.call("emulator/hold", {"buttons": ["a"], "down": False})
        await b.frames(1)
        sym = (await b.status()).get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            rows.append({"f": f, "fault": sym})
            break
        x = int.from_bytes(await b.read(A_X, 4), "big") >> 16
        y = int.from_bytes(await b.read(A_Y, 4), "big") >> 16
        g = int.from_bytes(await b.read(A_GSP, 2), "big")
        g = g - 0x10000 if g >= 0x8000 else g
        yv = int.from_bytes(await b.read(A_YVEL, 2), "big")
        yv = yv - 0x10000 if yv >= 0x8000 else yv
        st = (await b.read(A_STATE, 1))[0]
        layer = (await b.read(A_LAYER, 1))[0]
        fl = floors.floor(x, y + radius, layer & 1)
        rows.append({"f": f, "x": x, "y": y, "layer": layer, "state": st,
                     "grounded": st in grounded, "gsp": g, "yvel": yv, "floor": fl})
        if y >= a.fall_y or (a.stop_x is not None and
                             ((a.dir == "left" and x <= a.stop_x) or
                              (a.dir == "right" and x >= a.stop_x))):
            break
    await client.call("emulator/hold", {"buttons": [a.dir, "a"], "down": False})
    await client.close()
    return {"placement": placement, "debug_flag_at_boot": dbg_before,
            "start": [a.x, feet - radius], "landed": landed, "landed_layer": landed_layer,
            "rows": rows}


def summary(res, a):
    rows = [r for r in res["rows"] if "x" in r]
    if not rows:
        return "no rows"
    flips = [(q["f"], p["x"], q["x"], q["y"], p["layer"], q["layer"])
             for p, q in zip(rows, rows[1:]) if p["layer"] != q["layer"]]
    in_hole = [r for r in rows if HOLE[0] <= r["x"] < HOLE[1]]
    in_hole_b = [r for r in in_hole if r["layer"] & 1]
    no_floor = [r for r in rows if r["floor"] is None]
    last = rows[-1]
    out = [f"{a.label} [{res['placement']}; debug-fly at boot {res['debug_flag_at_boot']}] "
           f"start x {res['start'][0]} landed {res['landed']} landed layer {res['landed_layer']}"
           f" forced {a.force_layer} dir {a.dir} gsp {a.gsp} jump {a.jump_at}",
           f"  frames {len(rows)}  x {min(r['x'] for r in rows)}..{max(r['x'] for r in rows)}"
           f"  y {min(r['y'] for r in rows)}..{max(r['y'] for r in rows)}",
           f"  layer changes {len(flips)}: " + "; ".join(
               f"f{f} x {x0}->{x1} y {y} {l0}->{l1}" for f, x0, x1, y, l0, l1 in flips),
           f"  frames with x in {HOLE[0]}..{HOLE[1] - 1}: {len(in_hole)} (on layer B: "
           f"{len(in_hole_b)}); frames with NO floor below the feet on the current layer: "
           f"{len(no_floor)}",
           f"  end: x {last['x']} y {last['y']} layer {last['layer']} state {last['state']} "
           f"gsp {last['gsp']} yvel {last['yvel']} floor {last['floor']}  "
           f"FELL THROUGH: {'YES' if last['y'] >= a.fall_y else 'no'}"]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y-from", type=int, default=0)
    ap.add_argument("--dir", choices=("right", "left"), default="left")
    ap.add_argument("--gsp", default="none", help="none | top | cap | <int>")
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--fall-y", type=int, default=1100)
    ap.add_argument("--stop-x", type=int)
    ap.add_argument("--force-layer", type=int, choices=(0, 1))
    ap.add_argument("--jump-at", type=int, nargs="*")
    ap.add_argument("--spindash-at", type=int, nargs="*")
    ap.add_argument("--jump-x", type=int, nargs="*")
    ap.add_argument("--spindash-when-stuck", type=int, default=0)
    ap.add_argument("--spindash-max", type=int, default=3)
    ap.add_argument("--jump-after-dash", type=int)
    ap.add_argument("--idle-before-dash", type=int, default=0)
    ap.add_argument("--label", default="")
    ap.add_argument("--json")
    ap.add_argument("--every", type=int, default=0)
    a = ap.parse_args()
    syms, equs = L.parse_lst(a.lst)
    act = CM.load(a.manifest)
    floors = Floors(act)
    with aether_emulator(a.rom, symbols=a.lst) as sock:
        res = asyncio.run(run(sock, syms, equs, act, a, floors))
    print(summary(res, a))
    if a.every:
        for r in res["rows"][::a.every]:
            print("   ", r)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps({"args": vars(a), **res}))
    print("finished=1")


if __name__ == "__main__":
    main()
