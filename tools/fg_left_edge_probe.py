#!/usr/bin/env python3
"""fg_left_edge_probe — measure plane-A ground occupancy across the LEFT EDGE of the screen.

WHY THIS EXISTS. The owner reported that the two leftmost columns of the foreground lose
their ground (a detached sliver of terrain at the far left). It was first measured from an
F2 save state through `emulator/pixel_attribution`, cell by cell, by hand. That route is
not repeatable from a script: the aether server has NO path from the bus to the filesystem
for machine state (a deliberate rule — `emulator/checkpoint` is in-memory only, and the
method table forbids a persist-to-disk variant), so the owner's `.state0` cannot be loaded
over the wire at all.

THE SAVE STATE IS NOT NEEDED, and that is a measured fact rather than a convenience. The
discriminator run booked in DEFERRED_WORK stepped the camera 195 -> 227 (four whole tile
columns) and found the affected band pinned to the VIEWPORT, not to the world: occupancy at
x >= 16 changes as world content scrolls through while x=0 and x=8 stay empty at every
position. A screen-pinned defect reproduces at ANY camera position where ground reaches the
left edge, so a plain boot plus some rightward travel reaches the same subject the owner's
state does.

WHAT IT MEASURES. For each sampled column it asks `pixel_attribution` for the plane-A
candidate's `opaque` flag - the same field the by-hand table tabulated - and prints one row
per screen row. `#` means plane A is opaque at that cell, `.` means transparent. The
signature of the defect is the two leftmost columns carrying NO ground band while every
column from x=16 rightwards carries one.

THIS IS A PROBE, NOT A GATE. It prints what it measured and exits 0 whether the band is
present or absent; deciding what the table means is the reader's job. It deliberately does
not encode a pass/fail expectation, because the expectation is exactly what is under
investigation - a probe that asserted "x=0 must be opaque" would be asserting the fix it
exists to evaluate.

USAGE
    python3 tools/fg_left_edge_probe.py                      # boot state, default grid
    python3 tools/fg_left_edge_probe.py --travel 240         # hold RIGHT for 240 frames first
    python3 tools/fg_left_edge_probe.py --travel 60,120,240  # one table per stop (screen-pin check)
    python3 tools/fg_left_edge_probe.py --rom s4.debug.bin --settle 240
"""
import argparse
import asyncio
import os
import sys
import zlib

sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Columns: the two under suspicion plus enough beyond them to show a healthy band.
DEFAULT_COLS = [0, 8, 16, 24, 32, 40, 48, 56]
# Rows: a window wide enough to catch the ground band wherever the camera puts it, rather
# than the y=168..184 the hand table used - that range was specific to Camera_Y=429.
DEFAULT_ROW_RANGE = (0, 216, 8)


async def sample(client, cols, rows):
    """Return {(x, y): bool_planeA_opaque}."""
    out = {}
    for y in rows:
        for x in cols:
            r = await client.call("emulator/pixel_attribution", {"x": x, "y": y})
            pa = next((c for c in r["candidates"] if c["layer"] == "planeA"), None)
            # A missing plane-A candidate is not the same fact as a transparent one, and
            # rendering it as "." would quietly turn "could not measure" into a reading.
            out[(x, y)] = None if pa is None else bool(pa["opaque"])
    return out


def render(grid, cols, rows, camera):
    print(f"\n  Camera_X={camera[0]}  Camera_Y={camera[1]}   (plane A: # opaque, . transparent, ? absent)")
    print("       " + "".join(f"x={x:<5}" for x in cols))
    for y in rows:
        cells = []
        for x in cols:
            v = grid[(x, y)]
            cells.append("#" if v is True else ("." if v is False else "?"))
        print(f"  y={y:<4} " + "".join(f"{c:<7}" for c in cells))
    # Per-column summary: how many sampled rows carry plane-A content at all.
    print("  count " + "".join(f"{sum(1 for y in rows if grid[(x, y)] is True):<7}" for x in cols))


async def warp(client, px, py):
    """Put the PLAYER at (px, py) through the DEBUG warp mailbox and wait for the ack.

    Why the mailbox and not a camera poke: a bare camera write TEARS — everything
    downstream of the camera (the column ring, the plane buffers, residency) is left
    describing the old position, which would manufacture exactly the kind of half-filled
    left edge this probe is investigating. The mailbox is consumed at a coherent point and
    rebuilds all of it; `tools/warp_mailbox_gate.py` is the gate that pins that property.
    The consumer CENTRES the camera on the player, so camera = player - (160, 144).
    """
    syms = {}
    for name in ("Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag"):
        r = await client.call("emulator/lookup_symbol", {"name": name})
        syms[name] = int(str(r["addr"]).removeprefix("0x"), 16)
    await client.call("emulator/write_memory", {"addr": hex(syms["Warp_Req_X"]), "value": px, "width": 2})
    await client.call("emulator/write_memory", {"addr": hex(syms["Warp_Req_Y"]), "value": py, "width": 2})
    await client.call("emulator/write_memory", {"addr": hex(syms["Warp_Req_Flag"]), "value": 1, "width": 1})
    for i in range(1, 121):
        await client.call("emulator/run_frames", {"frames": 1})
        r = await client.call("emulator/read_memory", {"addr": hex(syms["Warp_Req_Flag"]), "len": 1})
        if int(str(r["bytes"]).removeprefix("0x"), 16) == 0:
            # The engine publishes the CLAMPED destination back into the mailbox, so a
            # request outside the level reports where it actually landed rather than
            # letting the caller believe the requested position was honoured.
            bx = await client.call("emulator/read_memory", {"addr": hex(syms["Warp_Req_X"]), "len": 2})
            by = await client.call("emulator/read_memory", {"addr": hex(syms["Warp_Req_Y"]), "len": 2})
            print(f"      warp acked in {i} frames; clamped player = "
                  f"({int(str(bx['bytes']).removeprefix('0x'), 16)}, "
                  f"{int(str(by['bytes']).removeprefix('0x'), 16)})")
            await client.call("emulator/run_frames", {"frames": 30})
            return
    raise SystemExit("Warp_Req_Flag never cleared in 120 frames — the consumer did not run "
                     "(wrong ROM shape, or not in the level state)")


async def run(client, args, cols, rows, travel, button="right"):
    if travel:
        await client.call("emulator/play_input",
                          {"rows": [{"start": 0, "end": travel, "buttons": [button]}],
                           "maxFrames": travel})
    cam = []
    for sym in ("Camera_X", "Camera_Y"):
        r = await client.call("emulator/read", {"symbol": sym, "len": 4})
        raw = r["bytes"]
        raw = raw[2:] if raw[:2].lower() == "0x" else raw
        cam.append(int(raw[:4], 16))
    grid = await sample(client, cols, rows)
    render(grid, cols, rows, cam)
    return cam, grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--symbols", default=None)
    ap.add_argument("--settle", type=int, default=240,
                    help="frames to run before measuring (the engine boots into gameplay)")
    ap.add_argument("--warp", default="",
                    help="player position 'X,Y' to warp to before measuring "
                         "(camera lands at X-160, Y-144)")
    ap.add_argument("--travel", default="",
                    help="comma-separated frame counts to hold RIGHT for; one table per stop")
    ap.add_argument("--cols", default=",".join(str(c) for c in DEFAULT_COLS))
    args = ap.parse_args()

    rom = os.path.abspath(args.rom)
    symbols = args.symbols or (rom[:-4] + ".lst")
    cols = [int(c) for c in args.cols.split(",")]
    lo, hi, step = DEFAULT_ROW_RANGE
    rows = list(range(lo, hi + 1, step))
    # Each stop is "<frames>" (right) or "<frames>l" / "<frames>r" — a leg of travel in that
    # direction, measured from the previous stop. Leftward legs matter: the booked symptom is
    # at the edge the camera ADVANCES INTO, which is the left edge only when moving left.
    stops = []
    for t in args.travel.split(","):
        t = t.strip()
        if not t:
            continue
        btn = "right"
        if t[-1] in "lr":
            btn = "left" if t[-1] == "l" else "right"
            t = t[:-1]
        stops.append((int(t), btn))
    stops = stops or [(0, "right")]

    with open(rom, "rb") as fh:
        blob = fh.read()
    print(f"ROM   {rom}")
    print(f"      {len(blob)} bytes, crc32 {zlib.crc32(blob) & 0xFFFFFFFF:08x}")

    inst = AetherInstance(rom, symbols=symbols)
    sock = inst.start()

    async def body():
        c = BusClient(sock)
        await c.connect()
        st = await c.call("emulator/status", {})
        # The stale-shim hazard: a server can serve a PREVIOUS build while reporting a
        # correct-looking romPath. Byte count is the cheap independent witness.
        if st["romBytes"] != len(blob):
            raise SystemExit(f"ROM MISMATCH: server serves {st['romBytes']} bytes, "
                             f"{rom} is {len(blob)} - refusing to measure a different ROM")
        print(f"      server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")
        await c.call("emulator/run_frames", {"frames": args.settle})
        if args.warp:
            px, py = (int(v) for v in args.warp.split(","))
            await warp(c, px, py)
        for frames, btn in stops:
            # Each stop is a LEG: this many frames holding that direction, from wherever the
            # previous leg left the camera. Legs compose into one continuous run.
            await run(c, args, cols, rows, frames, btn)

    try:
        asyncio.run(body())
    finally:
        inst.reap()
    return 0


if __name__ == "__main__":
    sys.exit(main())
