#!/usr/bin/env python3
"""RESEARCH PROBE (not a gate, no runner): drive the player headless through one scripted
scene and print a per-frame row (x, y, x_vel, y_vel, gsp, angle, state, status, layer).

Built for SONIC-SLOPE-COLLISION (owner report 2026-09-26: "I can stand on random things
or don't just start rolling when I try to"). Same harness and drive preamble as
tools/tunnel_run_witness.py / cpz_traverse.py: boot, leave debug free-flight with a REAL
B press (DEBUG shape only; the plain shape boots grounded), write the camera and the
player together, pin the player while streaming settles, then run the scene.

A SCENE is: a placement (x, feet-y from the collision under x or --y), an optional state
poke (--gsp ground speed written after landing), and an input schedule of
`frame:buttons[:frames]` items (buttons '+'-joined, e.g. 30:down:60 = hold DOWN from
frame 30 for 60 frames; '-' = nothing).

    python3 docs/research/2026-09-26-sonic-slope-collision/slope_probe.py \
        --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst --x 13700 --gsp 0x600 \
        --inputs 0:down:4 --frames 120
"""
import argparse
import asyncio
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
import loop_step_over_witness as L                         # noqa: E402
import tunnel_run_witness as T                             # noqa: E402
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402
import clip_manifest as CM                                 # noqa: E402

STATE_NAMES = {0: "GRND", 2: "ROLL", 4: "SPIN", 6: "AIR", 8: "JUMP", 0xA: "RJMP",
               0xC: "ABAL", 0xE: "FLY", 0x10: "GLID", 0x12: "GLFL", 0x14: "SLID"}


def s16(v):
    return v - 0x10000 if v >= 0x8000 else v


def parse_inputs(spec):
    out = []
    for item in spec or []:
        parts = item.split(":")
        f = int(parts[0])
        btns = [] if parts[1] in ("-", "") else parts[1].split("+")
        n = int(parts[2]) if len(parts) > 2 else 1
        out.append((f, btns, n))
    return out


async def scene(sock, syms, equs, args, feet):
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    client = BusClient(socket_path=sock, client_id="slp", client_name="slope-probe")
    await client.connect()
    b = L.Bus(client)
    P = syms["Player_1"]
    A = {k: P + equs["SST_" + k] for k in ("x_pos", "y_pos", "x_vel", "y_vel", "angle",
                                          "status", "layer")}
    A_GSP, A_DBG = P + L.PLAYERV_GROUND_SPEED, P + L.PLAYERV_DEBUG_FLAG
    A_STATE = P + T.PL_STATE_OFF

    await client.call("emulator/reset", {})
    await b.frames(240)
    await b.check_alive("boot")
    if (await b.read(A_DBG, 1))[0]:
        await client.call("emulator/press", {"buttons": ["b"]})
        await b.frames(4)
    if (await b.read(A_DBG, 1))[0]:
        raise SystemExit("slope_probe: still in debug free-flight after the B press")
    await b.write(syms["Camera_X"], (args.x - 160) << 16, 4)
    await b.write(syms["Camera_Y"], (feet - radius - 112) << 16, 4)
    for _ in range(args.pin):
        await b.write(A["x_pos"], args.x << 16, 4)
        await b.write(A["y_pos"], (feet - radius - 2) << 16, 4)
        await b.write(A["y_vel"], 0, 2)
        await b.write(A["x_vel"], 0, 2)
        await b.frames(1)
    if args.settle:
        await b.frames(args.settle)
    await b.check_alive("placement")
    st0 = (await b.read(A_STATE, 1))[0]
    if args.gsp is not None:
        await b.write(A_GSP, args.gsp & 0xFFFF, 2)
    if args.xvel is not None:
        await b.write(A["x_vel"], args.xvel & 0xFFFF, 2)
    if args.yvel is not None:
        await b.write(A["y_vel"], args.yvel & 0xFFFF, 2)
    if args.y_after is not None:
        await b.write(A["y_pos"], args.y_after << 16, 4)
    sched = parse_inputs(args.inputs)
    held = set()
    rows = []
    for f in range(args.frames):
        want = set()
        for (f0, btns, n) in sched:
            if f0 <= f < f0 + n:
                want |= set(btns)
        for btn in held - want:
            await client.call("emulator/hold", {"buttons": [btn], "down": False})
        for btn in want - held:
            await client.call("emulator/hold", {"buttons": [btn], "down": True})
        held = want
        await b.frames(1)
        sym = (await b.status()).get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            rows.append((f, "FAULT " + sym))
            break
        x = int.from_bytes(await b.read(A["x_pos"], 4), "big")
        y = int.from_bytes(await b.read(A["y_pos"], 4), "big")
        xv = s16(int.from_bytes(await b.read(A["x_vel"], 2), "big"))
        yv = s16(int.from_bytes(await b.read(A["y_vel"], 2), "big"))
        g = s16(int.from_bytes(await b.read(A_GSP, 2), "big"))
        ang = (await b.read(A["angle"], 1))[0]
        stat = (await b.read(A["status"], 1))[0]
        lay = (await b.read(A["layer"], 1))[0]
        pst = (await b.read(A_STATE, 1))[0]
        rows.append((f, x, y, xv, yv, g, ang, stat, lay, pst, "+".join(sorted(want)) or "-"))
    for btn in held:
        await client.call("emulator/hold", {"buttons": [btn], "down": False})
    await client.close()
    return st0, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--manifest", default="games/sonic4/data/clips/s2_ehz_cpz/clips.json",
                    help="clip manifest for the ground lookup; 'none' needs --y")
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y", type=int, default=None, help="feet y (default: first top-solid "
                    "pixel under --x from --y-from, plane A)")
    ap.add_argument("--y-from", type=int, default=0)
    ap.add_argument("--gsp", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--xvel", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--yvel", type=lambda s: int(s, 0), default=None)
    ap.add_argument("--y-after", type=int, default=None,
                    help="write y_pos after landing (drop the player from here)")
    ap.add_argument("--inputs", nargs="*", default=[])
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--pin", type=int, default=120)
    ap.add_argument("--settle", type=int, default=L.LAND_FRAMES * 4,
                    help="frames run after the pin, before the scene (0 = log the fall)")
    args = ap.parse_args()
    syms, equs = L.parse_lst(args.lst)
    if args.y is not None:
        feet = args.y
    else:
        act = CM.load(args.manifest)
        feet = T.ground_y(act, args.x, args.y_from)
    with aether_emulator(args.rom, symbols=args.lst) as sock:
        st0, rows = asyncio.run(scene(sock, syms, equs, args, feet))
    print(f"# placed x={args.x} feet={feet}; state after landing={STATE_NAMES.get(st0, st0)}")
    print("#  f     x.sub        y.sub     xvel  yvel   gsp  ang stat L state input")
    for r in rows:
        if isinstance(r[1], str):
            print(f"{r[0]:4d} {r[1]}")
            continue
        f, x, y, xv, yv, g, ang, stat, lay, pst, inp = r
        print(f"{f:4d} {x >> 16:6d}.{(x >> 8) & 0xFF:02X} {y >> 16:6d}.{(y >> 8) & 0xFF:02X} "
              f"{xv:6d} {yv:5d} {g:5d}  ${ang:02X}  ${stat:02X}  {lay} {STATE_NAMES.get(pst, pst):5s} {inp}")


if __name__ == "__main__":
    main()
