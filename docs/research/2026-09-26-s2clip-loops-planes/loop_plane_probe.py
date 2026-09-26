#!/usr/bin/env python3
"""RESEARCH PROBE (not a gate, no runner): what does the player do at the S2 clip act's
loops and plane-switch spots, and what WOULD he do if Sonic 2's plane switchers existed?

Runs the real clip ROM headless (tools/aether_instance, the same harness and drive
preamble as docs/research/2026-09-25-cpz-traversal/cpz_traverse.py: leave debug-fly with a
real B press, set the camera, pin the player on the plane-A ground while streaming settles,
check he landed). Then holds a direction, optionally injects a ground speed once, and
records x / y / layer / angle / ground speed / player state / art_tile priority per frame.

--switchers:
  none   the ROM as built. Nothing in the clip writes Sst.layer (the S2 donor tree has
         no crossover marks, and the clip carries no objects), so this is the act as the
         owner plays it.
  s2     HOST-EMULATED Sonic 2 Obj03 (s2.asm:45132-45369) from the donor's own object
         layout (level/objects/<ZONE>_1.bin), shifted by the clip's dst-src offset. After
         each frame the probe applies Obj03's rule to the player's resolved position and
         writes Sst.layer (0 = S2 primary path, 1 = secondary) when a line fires. This is
         the same ordering as S2 (Obj03 runs after the player in the object loop, so its
         write takes effect for the next frame's collision). Priority (subtype bits 5/6)
         is NOT emulated: the engine derives priority from the layer only in
         Player_LoopCrossover, and this probe does not touch art_tile. It is a model of
         the missing object, used to test whether placing the switchers alone would make
         the act behave like Sonic 2; it is not the engine.

Usage:
    python3 docs/research/2026-09-26-s2clip-loops-planes/loop_plane_probe.py \\
        --rom s4.debug.bin --lst s4.debug.lst \\
        --manifest games/sonic4/data/clips/s2_ehz_cpz/clips.json \\
        --x 4000 --dir right --gsp top --frames 300 --switchers none [--json out.json]
"""
import argparse
import asyncio
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
import loop_step_over_witness as L                         # noqa: E402
import tunnel_run_witness as T                             # noqa: E402
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402
import clip_manifest as CM                                 # noqa: E402

S2_OBJECTS = pathlib.Path("/home/volence/sonic_hacks/s2disasm/level/objects")
OBJ03_SIZES = (0x20, 0x40, 0x80, 0x100)      # s2.asm word_1FD68
ART_TILE_PRIO = 0x8000


def s2_switchers(act):
    """Every Obj03 of every clip's donor zone, in ACT coordinates, inside its src rect."""
    out = []
    for cl in act.clips:
        zone = cl.zone
        data = (S2_OBJECTS / f"{zone}_1.bin").read_bytes()
        sx, sy, sw, sh = cl.src
        dx, dy = cl.dst[0] - sx, cl.dst[1] - sy
        for i in range(0, len(data) - 5, 6):
            x, yw, oid, st = struct.unpack(">HHBB", data[i:i + 6])
            if x == 0xFFFF:
                break
            y = yw & 0xFFF
            if oid != 3 or not (sx <= x < sx + sw and sy <= y < sy + sh):
                continue
            out.append({"zone": zone, "src": (x, y), "x": x + dx, "y": y + dy, "st": st,
                        "xflip": (yw >> 13) & 1, "horiz": bool(st & 4),
                        "half": OBJ03_SIZES[st & 3], "side": None})
    return out


def obj03_step(sw, px, py, in_air, layer):
    """One frame of Obj03_MainX / Obj03_MainY for one line. Returns the new layer."""
    along, across = (py, px) if sw["horiz"] else (px, py)
    line, centre = (sw["y"], sw["x"]) if sw["horiz"] else (sw["x"], sw["y"])
    if sw["side"] is None:                   # Obj03_Init: 1 iff player past the line
        sw["side"] = 1 if along > line else 0
        return layer
    if sw["side"] == 0:
        if along < line:
            return layer
        sw["side"], bit = 1, 3
    else:
        if along >= line:
            return layer
        sw["side"], bit = 0, 4
    if not (centre - sw["half"] <= across < centre + sw["half"]):
        return layer
    if sw["st"] & 0x80 and in_air:
        return layer
    if sw["xflip"]:
        return layer
    return 1 if sw["st"] & (1 << bit) else 0


async def run(sock, syms, equs, act, a):
    feet = T.ground_y(act, a.x, a.y_from)
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    client = BusClient(socket_path=sock, client_id="lpp", client_name="loop-plane-probe")
    await client.connect()
    b = L.Bus(client)
    P = syms["Player_1"]
    A_X, A_Y = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    A_YVEL, A_LAYER, A_ANGLE = P + equs["SST_y_vel"], P + equs["SST_layer"], P + equs["SST_angle"]
    A_ART = P + equs["SST_art_tile"]
    A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG
    A_STATE = P + T.PL_STATE_OFF
    grounded = {equs["PSTATE_GROUND"], equs["PSTATE_ROLL"]}

    await client.call("emulator/reset", {})
    await b.frames(240)
    await b.check_alive("boot")
    if (await b.read(A_DBG, 1))[0]:
        await client.call("emulator/press", {"buttons": ["b"]})
        await b.frames(4)
    if (await b.read(A_DBG, 1))[0]:
        raise SystemExit("loop_plane_probe: still in debug free-flight after the B press")
    await b.write(syms["Camera_X"], (a.x - 160) << 16, 4)
    await b.write(syms["Camera_Y"], (feet - radius - 112) << 16, 4)
    for _ in range(T.PIN_FRAMES):
        await b.write(A_X, a.x << 16, 4)
        await b.write(A_Y, (feet - radius - 2) << 16, 4)
        await b.write(A_YVEL, 0, 2)
        await b.write(A_GSP, 0, 2)          # a slope builds ground speed under a pin
        await b.frames(1)
    await b.frames(L.LAND_FRAMES * 4)
    await b.check_alive("placement")
    # grounded = the state machine says so (on a slope y_vel is the projected ground speed,
    # so y_vel == 0 is not the test here)
    if (await b.read(A_STATE, 1))[0] not in grounded:
        raise SystemExit(f"loop_plane_probe: the player never landed at x={a.x} (feet {feet})")
    start_layer = (await b.read(A_LAYER, 1))[0]
    landed = [int.from_bytes(await b.read(A_X, 4), "big") >> 16,
              int.from_bytes(await b.read(A_Y, 4), "big") >> 16]

    switchers = s2_switchers(act) if a.switchers == "s2" else []
    await client.call("emulator/hold", {"buttons": [a.dir], "down": True})
    if a.gsp != "none":
        v = equs["PHYS_TOP_SPEED"] if a.gsp == "top" else (
            equs["PHYS_GSP_CAP"] if a.gsp == "cap" else int(a.gsp, 0))
        await b.write(A_GSP, (v if a.dir == "right" else -v) & 0xFFFF, 2)
    rows, fired = [], []
    for f in range(a.frames):
        await b.frames(1)
        sym = (await b.status()).get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            rows.append({"f": f, "fault": sym})
            break
        x = int.from_bytes(await b.read(A_X, 4), "big") >> 16
        y = int.from_bytes(await b.read(A_Y, 4), "big") >> 16
        g = int.from_bytes(await b.read(A_GSP, 2), "big")
        g = g - 0x10000 if g >= 0x8000 else g
        st = (await b.read(A_STATE, 1))[0]
        layer = (await b.read(A_LAYER, 1))[0]
        ang = (await b.read(A_ANGLE, 1))[0]
        art = int.from_bytes(await b.read(A_ART, 2), "big")
        for sw in switchers:
            nl = obj03_step(sw, x, y, st not in grounded, layer)
            if nl != layer:
                fired.append({"f": f, "line": sw["src"], "zone": sw["zone"], "to": nl})
                layer = nl
                await b.write(A_LAYER, nl, 1)
        rows.append({"f": f, "x": x, "y": y, "gsp": g, "state": st, "layer": layer,
                     "angle": ang, "prio": int(bool(art & ART_TILE_PRIO))})
        if y >= a.fall_y:
            break
    await client.call("emulator/hold", {"buttons": [a.dir], "down": False})
    await client.close()
    return {"start": [a.x, feet - radius], "landed": landed, "start_layer": start_layer, "rows": rows,
            "fired": fired, "grounded_states": sorted(grounded)}


def summary(res, a):
    rows = [r for r in res["rows"] if "x" in r]
    if not rows:
        return "no rows"
    inv = [r for r in rows if 0x60 <= r["angle"] <= 0xA0 and r["state"] in res["grounded_states"]]
    air = [r for r in rows if r["state"] not in res["grounded_states"]]
    layers = sorted({r["layer"] for r in rows})
    flips = sum(1 for p, q in zip(rows, rows[1:]) if p["layer"] != q["layer"])
    last = rows[-1]
    return (f"{a.label or ''} start x {res['start'][0]} (landed at {res['landed']}) dir {a.dir} gsp {a.gsp} switchers "
            f"{a.switchers}: frames {len(rows)}, x {min(r['x'] for r in rows)}..{max(r['x'] for r in rows)}, "
            f"y {min(r['y'] for r in rows)}..{max(r['y'] for r in rows)}, layers seen {layers}, "
            f"layer changes {flips}, host-fired lines {len(res['fired'])}, grounded-inverted "
            f"frames (angle $60..$A0) {len(inv)}, airborne frames {len(air)}, end "
            f"(x {last['x']}, y {last['y']}, gsp {last['gsp']}, state {last['state']}, "
            f"layer {last['layer']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y-from", type=int, default=0, help="scan down for ground from here")
    ap.add_argument("--dir", choices=("right", "left"), default="right")
    ap.add_argument("--gsp", default="top", help="none | top | cap | <int>")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--fall-y", type=int, default=2400)
    ap.add_argument("--switchers", choices=("none", "s2"), default="none")
    ap.add_argument("--label", default="")
    ap.add_argument("--json")
    ap.add_argument("--every", type=int, default=0, help="print every Nth row")
    a = ap.parse_args()
    syms, equs = L.parse_lst(a.lst)
    for n in ("SST_art_tile", "PSTATE_GROUND", "PSTATE_ROLL", "SST_y_vel"):
        if n not in equs:
            raise SystemExit(f"loop_plane_probe: {a.lst} carries no {n}")
    act = CM.load(a.manifest)
    with aether_emulator(a.rom, symbols=a.lst) as sock:
        res = asyncio.run(run(sock, syms, equs, act, a))
    print(summary(res, a))
    for e in res["fired"]:
        print(f"    fired f{e['f']} {e['zone']} line {e['line']} -> layer {e['to']}")
    if a.every:
        for r in res["rows"][::a.every]:
            print("   ", r)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps({"args": vars(a), **res}, indent=0))
    print("finished=1")


if __name__ == "__main__":
    main()
