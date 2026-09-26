#!/usr/bin/env python3
"""s2clip_layer_line_witness.py — do Sonic 2's plane-switcher lines work in the clip ROM?

THE CLAIM (S2CLIP-PLANE-SWITCH, option A). The clip act (`S2CLIP=s2_ehz_cpz`) carries Sonic 2's
Obj03 lines as a layer-line table (tools/s2_layer_lines.py bakes it; Player_LayerLines in
games/sonic4/player/player_common.emp runs it), and with them a player can complete Emerald
Hill's loops, which on plane A alone he cannot (docs/research/2026-09-26-s2clip-loops-planes.md:
without the lines, 0 layer changes and a max x at the loop's right arc in every drive).

WHAT IT RUNS. The real clip ROM, headless (tools/aether_instance, the same harness and drive
preamble as the research probe): leave debug free-flight with a real B press when the shape
starts in it (the DEBUG shape does, and free flight skips the whole player preamble, so it would
mask exactly the code under test), pin the player on plane-A ground, hold a direction, inject a
ground speed once, and record x / y / layer per frame. NOTHING is written to the layer byte:
the ROM's own routine is the only thing that can move it.

WHAT EACH DRIVE REQUIRES, and where the numbers come from. The lines a drive must cross are
DERIVED from the donor, not typed: tools/s2_layer_lines.plan() over the clip manifest, i.e.
Sonic 2's own object layout moved into act coordinates. For a loop:
  * the APEX line is the first grounded-only row past the start in the travel direction and the
    EXIT line the next row past it (Sonic 2 places them that way: s2.asm Obj03 subtype $91 at
    the apex, $11 past the right foot);
  * rightward, the run must go onto plane B (the apex line crossed upside down, moving left),
    come back to plane A, finish past the exit line, and end on plane A;
  * leftward, the run must go onto plane B at the exit line, back to A at the apex line, finish
    left of the apex line, and end on plane A.
A drive that fails any of these is FAILED (exit 1). The loop cannot be completed on plane A
(research, measured), so a ROM whose lines do nothing fails the first requirement and the
second.

EXIT STATUS: 0 every drive passed; 1 a drive FAILED; 2 COULD NOT RUN (the ROM is not a clip ROM,
the listing lacks a symbol, the player never landed, the emulator faulted, the donor plan has
no loop where the drive expects one). A run that cannot say anything about the lines must not
look like one that said "fine".

Usage:
    python3 tools/s2clip_layer_line_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst
    python3 tools/s2clip_layer_line_witness.py ... --drive ehz_loop1_R   (repeatable)
"""
import argparse
import asyncio
import os
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import clip_manifest as CM                                 # noqa: E402
import loop_step_over_witness as L                         # noqa: E402
import s2_layer_lines as SLL                               # noqa: E402
import tunnel_run_witness as T                             # noqa: E402

DEFAULT_MANIFEST = REPO / "games" / "sonic4" / "data" / "clips" / "s2_ehz_cpz" / "clips.json"

#: The drives. The start points are the research's (run_all.sh), each left (or right) of the
#: loop it is aimed at; which LINES that loop has is derived, see the header. `gsp` "top" is
#: PHYS_TOP_SPEED read from the listing, injected once after landing.
DRIVES = {
    "ehz_loop1_R": {"x": 3950, "y_from": 0, "dir": "right", "gsp": "top", "frames": 240},
    "ehz_loop1_L": {"x": 4500, "y_from": 600, "dir": "left", "gsp": "top", "frames": 240},
}
DEFAULT_DRIVES = ("ehz_loop1_R", "ehz_loop1_L")

#: A symbol only a clip ROM's listing carries (the clip data block's region table,
#: tools/clip_rom_bake.py). Its absence means this is not a clip ROM: COULD NOT RUN.
CLIP_SYMBOL = "OJZ_Clip_Regions"


class CouldNotRun(Exception):
    pass


def loop_lines(plan, x, direction):
    """(apex, exit) rows of the loop a drive starting at `x` runs into, from the donor plan."""
    c = plan["consts"]
    grounded = 1 << c["LL_GROUNDED"]
    horiz = 1 << c["LL_HORIZONTAL"]
    rows = [r for r in plan["rows"] if not r["flags"] & horiz]
    if direction == "right":
        ahead = sorted((r for r in rows if r["key"] > x), key=lambda r: r["key"])
        apex = next((r for r in ahead if r["flags"] & grounded), None)
        if apex is None:
            raise CouldNotRun(f"the donor plan has no grounded-only line right of x {x}")
        exit_ = next((r for r in ahead if r["key"] > apex["key"]), None)
    else:
        ahead = sorted((r for r in rows if r["key"] < x), key=lambda r: -r["key"])
        exit_ = next((r for r in ahead if not r["flags"] & grounded), None)
        apex = next((r for r in ahead if exit_ and r["key"] < exit_["key"]
                     and r["flags"] & grounded), None)
    if apex is None or exit_ is None:
        raise CouldNotRun(f"the donor plan has no apex + exit line pair {direction} of x {x}")
    return apex, exit_


def verdict(rows, apex, exit_, direction):
    """[] when the drive did what the loop needs, else the requirements it broke."""
    xs = [r["x"] for r in rows]
    layers = [r["layer"] for r in rows]
    runs = [layers[0]] + [b for a, b in zip(layers, layers[1:]) if a != b]
    bad = []
    if 1 not in layers:
        bad.append("the layer never left plane A (0 on every frame)")
    elif runs[:3] != [0, 1, 0]:
        bad.append(f"the layer went {runs}, not A -> B -> A")
    if direction == "right":
        if max(xs) <= exit_["key"]:
            bad.append(f"max x {max(xs)} never passed the exit line at x {exit_['key']}")
        if xs[-1] <= exit_["key"]:
            bad.append(f"ended at x {xs[-1]}, not past the exit line at x {exit_['key']}")
    else:
        if min(xs) >= apex["key"]:
            bad.append(f"min x {min(xs)} never passed the apex line at x {apex['key']}")
        if xs[-1] >= apex["key"]:
            bad.append(f"ended at x {xs[-1]}, not left of the apex line at x {apex['key']}")
    if layers[-1] != 0:
        bad.append(f"ended on layer {layers[-1]}, not plane A")
    return bad


async def drive(sock, syms, equs, act, d):
    from aether import BusClient
    feet = T.ground_y(act, d["x"], d["y_from"])
    radius = int(equs.get("PLAYER_Y_RADIUS", 19))
    client = BusClient(socket_path=sock, client_id="s2clip-ll", client_name="s2clip-layer-line")
    await client.connect()
    try:
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
        # THE DEBUG SHAPE STARTS IN FREE FLIGHT, and free flight skips Player_Main's whole
        # preamble (Player_DebugMove is its escape hatch), so the routine under test would never
        # run. A real B press leaves it.
        if (await b.read(A_DBG, 1))[0]:
            await client.call("emulator/press", {"buttons": ["b"]})
            await b.frames(4)
        if (await b.read(A_DBG, 1))[0]:
            raise CouldNotRun("still in debug free-flight after the B press")
        await b.write(syms["Camera_X"], (d["x"] - 160) << 16, 4)
        await b.write(syms["Camera_Y"], (feet - radius - 112) << 16, 4)
        for _ in range(T.PIN_FRAMES):
            await b.write(A_X, d["x"] << 16, 4)
            await b.write(A_Y, (feet - radius - 2) << 16, 4)
            await b.write(A_YVEL, 0, 2)
            await b.write(A_GSP, 0, 2)
            await b.frames(1)
        await b.frames(L.LAND_FRAMES * 4)
        await b.check_alive("placement")
        if (await b.read(A_STATE, 1))[0] not in grounded:
            raise CouldNotRun(f"the player never landed at x={d['x']} (feet {feet})")
        if (await b.read(A_LAYER, 1))[0] != 0:
            raise CouldNotRun("the player is not on plane A after placement; the drive assumes "
                              "it starts there")
        await client.call("emulator/hold", {"buttons": [d["dir"]], "down": True})
        v = equs["PHYS_TOP_SPEED"]
        await b.write(A_GSP, (v if d["dir"] == "right" else -v) & 0xFFFF, 2)
        rows = []
        for f in range(d["frames"]):
            await b.frames(1)
            sym = (await b.status()).get("symbolAtPc") or ""
            if "ErrorHandler" in sym:
                raise CouldNotRun(f"the emulator faulted at frame {f} ({sym})")
            x = int.from_bytes(await b.read(A_X, 4), "big") >> 16
            y = int.from_bytes(await b.read(A_Y, 4), "big") >> 16
            rows.append({"f": f, "x": x, "y": y, "layer": (await b.read(A_LAYER, 1))[0]})
        await client.call("emulator/hold", {"buttons": [d["dir"]], "down": False})
        return rows
    finally:
        await client.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--drive", action="append", choices=sorted(DRIVES), default=None)
    a = ap.parse_args(argv)
    for p in (a.rom, a.lst, a.manifest):
        if not os.path.isfile(p):
            print(f"COULD NOT RUN: no file at {p}")
            print("finished=2")
            return 2
    syms, equs = L.parse_lst(a.lst)
    missing = [n for n in ("Player_1", "Camera_X", "Camera_Y", CLIP_SYMBOL) if n not in syms]
    missing += [n for n in ("SST_x_pos", "SST_y_pos", "SST_y_vel", "SST_layer", "PSTATE_GROUND",
                            "PSTATE_ROLL", "PHYS_TOP_SPEED") if n not in equs]
    if missing:
        print(f"COULD NOT RUN: {a.lst} lacks {', '.join(missing)}"
              + (" (not a clip ROM: build it with S2CLIP=s2_ehz_cpz)"
                 if CLIP_SYMBOL in missing else ""))
        print("finished=2")
        return 2
    act = CM.load(a.manifest)
    plan = SLL.plan(act)
    from aether_instance import aether_emulator
    failed = unrun = 0
    for name in a.drive or DEFAULT_DRIVES:
        d = DRIVES[name]
        try:
            apex, exit_ = loop_lines(plan, d["x"], d["dir"])
            with aether_emulator(a.rom, symbols=a.lst) as sock:
                rows = asyncio.run(drive(sock, syms, equs, act, d))
        except CouldNotRun as exc:
            print(f"{name}: COULD NOT RUN: {exc}")
            unrun += 1
            continue
        bad = verdict(rows, apex, exit_, d["dir"])
        layers = [r["layer"] for r in rows]
        changes = [(r["f"], r["x"], r["layer"]) for p, r in zip(rows, rows[1:])
                   if p["layer"] != r["layer"]]
        print(f"{name}: {'PASSED' if not bad else 'FAILED'} — start x {d['x']} {d['dir']}, "
              f"apex line x {apex['key']} ({apex['why']}), exit line x {exit_['key']}; "
              f"{len(rows)} frames, x {min(r['x'] for r in rows)}..{max(r['x'] for r in rows)}, "
              f"end x {rows[-1]['x']} layer {layers[-1]}, layer changes (frame, x, to) {changes}")
        for why in bad:
            print(f"    FAILED: {why}")
        failed += bool(bad)
    rc = 2 if unrun else (1 if failed else 0)
    print(f"finished={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
