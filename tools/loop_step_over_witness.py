#!/usr/bin/env python3
"""loop_step_over_witness.py — drive a player through the section-0 loop at a chosen
ground speed and record what the collision LAYER did, frame by frame.

WHY IT EXISTS. `tools/loop_crossover_gate.py` executes `Player_LoopCrossover`'s bytes
against a synthetic world; it proves the routine asks about every cell it crossed. It
cannot show a player riding a real loop, because it never runs the engine. This does the
other half: a real ROM, the shipped act, the shipped crossover marks, and the shipped
physics, with one value injected.

WHAT IS INJECTED, and nothing else. `PlayerV.ground_speed`, ONCE, on the frame after the
player is placed at the ramp foot. Everything downstream — where the sensors land, which
plane they read, whether the loop is completed — is the engine's. The three speeds that
matter are derived from the build's own constants, not chosen:

    PHYS_TOP_SPEED  $600  =  6 px/frame   under COLL_CELL_W: cannot step over a mark
    (the boundary)  $900  =  9 px/frame   just over it — the case whose symptom is
                                          displaced (he rides the loop and falls through
                                          a floor a screen later)
    PHYS_GSP_CAP   $1000  = 16 px/frame   two whole cells a frame

SAMPLE SPACING IS DERIVED, and it is one frame. A mark is COLL_CELL_W = 8 px wide, so a
player at v px/frame occupies the marked column for ceil(8/v) frames: 2 at 6 px/frame,
1 at 9, 1 at 16. Any interval above ONE frame therefore cannot resolve a transition at
the two speeds this witness exists to compare, even in principle — that error is already
in this tree's record (a 4-frame interval reported "0 flips" for a run that had them).
So the machine is stepped one frame at a time and `Sst.layer` is read every frame.

WHAT ONE-FRAME SAMPLING STILL CANNOT SEE, said out loud: `layer` is a state, not an
event. A frame in which the sweep crosses two marked cells writes it twice and this
witness sees the net. It counts OBSERVED TRANSITIONS between consecutive frames, which
is a lower bound on writes and is exactly the quantity the pre/post comparison needs.

THE DRIVE ORDER IS LOAD-BEARING (each of these cost an evening):
  * leave debug-fly with a real B PRESS, never by writing debug_flag — the write skips
    Player_DebugExit, leaves `mappings` on Map_TestObj, and crashes in
    RefreshSpritePieceCount;
  * set the CAMERA first and let streaming settle, THEN place the player. The reverse
    order drops him through ground the collision cache does not cover yet;
  * let the camera FOLLOW afterwards. A pinned camera lets the player outrun the
    streamed window and fall through the level, which looks exactly like the defect.

Usage:
    loop_step_over_witness.py --rom s4.debug.bin --lst s4.debug.lst --gsp 0x900
    loop_step_over_witness.py --rom A.bin --lst A.lst --compare B.bin B.lst   (A/B at all
                                                                              three speeds)
Exit 0 always for a bare run — this is a WITNESS, it reports. `--require-flips N` turns
it into an assertion.
"""

import argparse
import asyncio
import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path, harness_path      # noqa: E402
sys.path.insert(0, str(harness_path()))
add_client_path()
from aether_instance import aether_emulator                # noqa: E402
from aether import BusClient                               # noqa: E402

# The SST field offsets and the player slot come from the LISTING, never from here.
NEED_SYMS = ("Player_1", "Camera_X", "Camera_Y")
NEED_EQUS = ("SST_x_pos", "SST_y_pos", "SST_layer", "SST_angle",
             "PHYS_TOP_SPEED", "PHYS_GSP_CAP", "COLL_CELL_W")
# PlayerV overlays Sst.sst_custom = $30; ground_speed is the first field of the overlay
# and debug_flag is at +$C from it. Both are `.emp` struct fields rather than EQU lines,
# so they are the two numbers this file states — and it says so rather than pretending
# they came out of the build.
PLAYERV_GROUND_SPEED = 0x30
PLAYERV_DEBUG_FLAG = 0x3C

START_X, START_Y = 1097, 553          # the ramp foot of the section-0 loop
CAM_X, CAM_Y = 1097, 445
SETTLE_FRAMES = 40                    # camera set -> streaming covers the player
LAND_FRAMES = 8                       # placed -> feet on the ground, before injection


def parse_lst(path):
    import re
    sym_re = re.compile(r"^ ([A-Za-z_$][\w$.]*) : ([0-9A-Fa-f]+) [A-Z] \|")
    equ_re = re.compile(r"^EQU ([A-Za-z_][\w]*) = \$([0-9A-Fa-f]+)\s*$")
    syms, equs = {}, {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = sym_re.match(line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
            continue
        m = equ_re.match(line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    missing = [n for n in NEED_SYMS if n not in syms] + [n for n in NEED_EQUS if n not in equs]
    if missing:
        raise SystemExit("loop_step_over_witness: %s carries no %s" % (path, ", ".join(missing)))
    return syms, equs


class Bus:
    """Thin wrapper: 24-bit addresses, and every step checks for a fault handler."""

    def __init__(self, client):
        self.b = client

    async def read(self, addr, n):
        r = await self.b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
        s = r["bytes"]
        s = s[2:] if s[:2].lower() == "0x" else s
        return bytes.fromhex(s)

    async def write(self, addr, value, width):
        return await self.b.call("emulator/write_memory",
                                 {"addr": hex(addr & 0xFFFFFF), "value": value, "width": width})

    async def frames(self, n):
        return await self.b.call("emulator/run_frames", {"frames": n})

    async def status(self):
        return await self.b.call("emulator/status", {})

    async def check_alive(self, where):
        st = await self.status()
        sym = st.get("symbolAtPc") or ""
        if "ErrorHandler" in sym or "ErrorHandlerBlob" in sym:
            raise SystemExit("loop_step_over_witness: the ROM FAULTED during %s — "
                             "symbolAtPc=%r pc=%s. Every number after this point would "
                             "be from a halted machine." % (where, sym, st.get("pc")))
        return st


async def drive(sock, syms, equs, gsp, frames, verbose, start_dx=0):
    client = BusClient(socket_path=sock, client_id="lsow", client_name="loop-step-over")
    await client.connect()
    b = Bus(client)

    P = syms["Player_1"]
    A_X = P + equs["SST_x_pos"]
    A_Y = P + equs["SST_y_pos"]
    A_LAYER = P + equs["SST_layer"]
    A_ANGLE = P + equs["SST_angle"]
    A_GSP = P + PLAYERV_GROUND_SPEED
    A_DBG = P + PLAYERV_DEBUG_FLAG

    await client.call("emulator/reset", {})
    await b.frames(240)
    await b.check_alive("boot")

    # 1. leave debug-fly with a REAL press (never by writing debug_flag)
    dbg = (await b.read(A_DBG, 1))[0]
    if dbg:
        await client.call("emulator/press", {"buttons": ["b"]})
        await b.frames(4)
        dbg = (await b.read(A_DBG, 1))[0]
    await b.check_alive("debug-fly exit")

    # 2. camera FIRST, then let streaming settle
    await b.write(syms["Camera_X"], CAM_X << 16, 4)
    await b.write(syms["Camera_Y"], CAM_Y << 16, 4)
    await b.frames(SETTLE_FRAMES)
    await b.check_alive("streaming settle")

    # 3. now place the player, and only now — then let him LAND before anything is
    #    injected. Measured 2026-09-04: placing at START_Y leaves him ~10 px above the
    #    ground, and the landing frame resets ground_speed. An injection before the
    #    landing is simply erased, and the run then reports the physics' own
    #    acceleration curve instead of the speed under test — which looks like a
    #    result rather than like a broken drive.
    await b.write(A_X, (START_X + start_dx) << 16, 4)
    await b.write(A_Y, START_Y << 16, 4)
    await b.frames(LAND_FRAMES)
    await b.check_alive("placement")

    # 4. hold RIGHT and inject the ground speed ONCE
    await client.call("emulator/hold", {"buttons": ["right"], "down": True})
    await b.write(A_GSP, gsp, 2)

    # 5. one frame at a time — the spacing derivation is in this file's docstring
    rows = []
    for f in range(frames):
        await b.frames(1)
        st = await b.status()
        sym = st.get("symbolAtPc") or ""
        if "ErrorHandler" in sym:
            rows.append({"frame": f, "fault": sym, "pc": st.get("pc")})
            break
        x = int.from_bytes(await b.read(A_X, 4), "big") >> 16
        y = int.from_bytes(await b.read(A_Y, 4), "big") >> 16
        layer = (await b.read(A_LAYER, 1))[0]
        angle = (await b.read(A_ANGLE, 1))[0]
        g = int.from_bytes(await b.read(A_GSP, 2), "big")
        rows.append({"frame": f, "x": x, "y": y, "layer": layer, "angle": angle,
                     "gsp": g if g < 0x8000 else g - 0x10000})
    await client.call("emulator/hold", {"buttons": ["right"], "down": False})
    await client.close()
    return rows


def summarise(rows, gsp, equs, label, verbose):
    live = [r for r in rows if "layer" in r]
    faulted = [r for r in rows if "fault" in r]
    flips = sum(1 for a, c in zip(live, live[1:]) if a["layer"] != c["layer"])
    ys = [r["y"] for r in live]
    xs = [r["x"] for r in live]
    px = gsp / 256.0
    residency = -(-equs["COLL_CELL_W"] // max(1, int(px)))   # ceil(cell / px per frame)
    print("  gsp $%04X = %.0f px/frame · a %d px mark is occupied for %d frame(s) at this "
          "speed, so the sample interval is 1 frame (derived, see the docstring)"
          % (gsp, px, equs["COLL_CELL_W"], residency))
    print("  %-10s frames=%d  layer flips=%d  layer sequence=%s"
          % (label, len(live), flips,
             "".join(str(r["layer"]) for r in live)[:80]))
    if live:
        print("             x %d..%d (%+d)   y %d..%d (climb %+d, max drop %+d)"
              % (xs[0], xs[-1], xs[-1] - xs[0], ys[0], ys[-1],
                 ys[0] - min(ys), max(ys) - ys[0]))
    if faulted:
        print("             FAULTED at frame %d: %s" % (faulted[0]["frame"], faulted[0]["fault"]))
    if verbose:
        for r in live:
            print("               f%-3d x=%-5d y=%-5d layer=%d angle=$%02X gsp=%d"
                  % (r["frame"], r["x"], r["y"], r["layer"], r["angle"], r["gsp"]))
    return {"flips": flips, "frames": len(live), "faulted": bool(faulted),
            "x0": xs[0] if xs else None, "x1": xs[-1] if xs else None,
            "y0": ys[0] if ys else None, "y1": ys[-1] if ys else None,
            "climb": (ys[0] - min(ys)) if ys else None,
            "drop": (max(ys) - ys[0]) if ys else None,
            "layers": "".join(str(r["layer"]) for r in live)}


def run_one(rom, lst, gsp, frames, verbose, label, start_dx=0, quiet=False):
    syms, equs = parse_lst(lst)
    with aether_emulator(rom, symbols=lst) as sock:
        rows = asyncio.run(drive(sock, syms, equs, gsp, frames, verbose, start_dx))
    if quiet:
        live = [r for r in rows if "layer" in r]
        flips = sum(1 for a, c in zip(live, live[1:]) if a["layer"] != c["layer"])
        return {"flips": flips, "layers": "".join(str(r["layer"]) for r in live),
                "cols": [r["x"] // equs["COLL_CELL_W"] for r in live]}, equs
    return summarise(rows, gsp, equs, label, verbose), equs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--gsp", default=None,
                    help="ground speed to inject (hex ok). Default: the three derived "
                         "speeds PHYS_TOP_SPEED, the boundary, PHYS_GSP_CAP")
    ap.add_argument("--compare", nargs=2, metavar=("ROM", "LST"),
                    help="a second build to run the identical drive against — the control")
    ap.add_argument("--frames", type=int, default=90)
    ap.add_argument("--start-dx", type=int, default=0,
                    help="shift the start X by this many pixels")
    ap.add_argument("--phase-sweep", action="store_true",
                    help="sweep start-dx over one whole COLL_CELL_W stride. The PHASE is "
                         "the free variable that decides a step-over: a 16 px/frame "
                         "stride against an 8 px cell visits every OTHER column, and "
                         "which half it visits is set by where the run started.")
    ap.add_argument("--json", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    syms, equs = parse_lst(args.lst)
    if args.gsp:
        speeds = [int(args.gsp, 0)]
    else:
        # DERIVED, not chosen: the cap, the top speed, and the value that first exceeds
        # one collision cell a frame (the boundary the defect lives at).
        speeds = [equs["PHYS_TOP_SPEED"],
                  (equs["COLL_CELL_W"] + 1) << 8,
                  equs["PHYS_GSP_CAP"]]

    if args.phase_sweep:
        cw = equs["COLL_CELL_W"]
        gsp = speeds[-1] if not args.gsp else speeds[0]
        print("PHASE SWEEP at gsp $%04X — start X shifted 0..%d px." % (gsp, cw - 1))
        print("  A %d px/frame step against a %d px cell leaves %s. WHICH columns get "
              "skipped is set by the sub-cell phase the run starts on, and that phase is "
              "the ONLY thing varied below — same ROMs, same drive, same injection."
              % (gsp >> 8, cw,
                 "no gap: every column is occupied on some frame"
                 if (gsp >> 8) <= cw else
                 "%d column(s) unoccupied between consecutive frames"
                 % ((gsp >> 8) // cw)))
        rows = []
        for dx in range(cw):
            r, _ = run_one(args.rom, args.lst, gsp, args.frames, False,
                           "subject", dx, quiet=True)
            c = None
            if args.compare:
                c, _ = run_one(args.compare[0], args.compare[1], gsp, args.frames,
                               False, "control", dx, quiet=True)
            print("  dx=%+d  subject flips=%d %s   control flips=%s %s"
                  % (dx, r["flips"], r["layers"][:28],
                     c["flips"] if c else "-", (c["layers"][:28] if c else "")))
            rows.append((dx, r, c))
        differing = [d for d, r, c in rows if c and r["flips"] != c["flips"]]
        print("  phases where the sweep changed the outcome: %s of %d"
              % (differing if differing else "NONE", cw))
        return 0

    out = {}
    for gsp in speeds:
        print("=" * 78)
        r, _ = run_one(args.rom, args.lst, gsp, args.frames, args.verbose,
                       pathlib.Path(args.rom).name, args.start_dx)
        out.setdefault("%04X" % gsp, {})["subject"] = r
        if args.compare:
            c, _ = run_one(args.compare[0], args.compare[1], gsp, args.frames,
                           args.verbose, pathlib.Path(args.compare[0]).name,
                           args.start_dx)
            out["%04X" % gsp]["control"] = c
            print("  DELTA: flips %d -> %d   final y %s -> %s"
                  % (c["flips"], r["flips"], c["y1"], r["y1"]))
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(out, indent=2) + "\n")
        print("wrote %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
