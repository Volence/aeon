#!/usr/bin/env python3
"""fg_left_edge_capture — put the column-19 borrow's two halves on screen, side by side.

WHY THIS EXISTS AND WHAT IT IS NOT. `tools/fg_left_edge_gate.py` asserts the borrow
against the machine and is the thing that can go red. This tool asserts NOTHING about the
picture: it exists because the owner has to decide whether the borrow's PRICE is
acceptable, and a price is a thing you look at. It captures; a human rules.

WHAT IT CAPTURES, and why both edges rather than the one that was fixed:
  * the LEFT edge  (x 0..31)   — the defect, and what the borrow repairs
  * the RIGHT edge (x 288..319) — column-pair 19, which the borrow overwrites with the
                                  FOREGROUND's V-scroll. On all six per-column scenes
                                  plane B is vertically locked, so after the borrow those
                                  16 px show the background at the camera's height
                                  instead of its own. That is the price.

EVERY WAY IT CAN FAIL TO REACH ITS SUBJECT IS A REFUSAL, never a picture:
  * the served ROM not matching the file on disk        (a stale server is the classic)
  * the scene cursor not landing where it was driven
  * VDP reg $0B bit 2 clear at the sample point         (the DEBUG warp clears it)
  * `source != "raster"`                                (a post-hoc state render is NOT
                                                         what the raster drew, and every
                                                         mid-frame effect is absent from
                                                         it — which is the whole subject)
A capture that cannot prove it is the frame the raster drew is worse than none here,
because the reader cannot tell a wrong picture from a right one by looking.

Usage:
    python3 tools/fg_left_edge_capture.py --rom s4.debug.bin --lst s4.debug.lst \
        --scene 12 --label fix --out-dir /somewhere
"""

import argparse
import asyncio
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aether_instance import AetherInstance                      # noqa: E402
from aether import BusClient                                    # noqa: E402
import fg_left_edge_gate as G                                   # noqa: E402

ACTIVE_H = 224


def write_png(path, w, h, rows_rgb, scale=1):
    """rows_rgb: list of bytes, each 3*w. Pure stdlib; no decode path needed anywhere."""
    raw = bytearray()
    for row in rows_rgb:
        for _ in range(scale):
            raw.append(0)                                  # filter type 0
            if scale == 1:
                raw += row
            else:
                for x in range(w):
                    raw += row[x * 3:x * 3 + 3] * scale
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


async def grab(c, y0, y1, chunk=16):
    """Chunked deliberately: one 224-line response is ~430 KB on a single JSON line and
    the client's readline limit is 64 KB, so an unchunked grab dies in the transport with
    a ValueError that says nothing about scanlines. 16 lines is ~31 KB."""
    out, width = [], None
    y = y0
    while y <= y1:
        n = min(chunk, y1 - y + 1)
        r = await c.call("emulator/scanlines", {"startLine": y, "count": n})
        if r.get("source") != "raster":
            raise SystemExit(f"REFUSED: scanlines source is {r.get('source')!r}, not 'raster' — "
                             f"a post-hoc state render is not the frame the raster drew, and "
                             f"every mid-frame effect is missing from it")
        for row in r["rows"]:
            width = row["width"]
            out.append(bytes.fromhex(str(row["rgb"]).removeprefix("0x")))
        y += n
    if len(out) != y1 - y0 + 1:
        raise SystemExit(f"REFUSED: asked for {y1 - y0 + 1} lines, got {len(out)}")
    return width, out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--scene", type=int, default=12)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--travel", type=int, default=0)
    ap.add_argument("--scale", type=int, default=6)
    a = ap.parse_args()

    blob = open(a.rom, "rb").read()
    print(f"ROM {a.rom} {len(blob)} B crc32 {zlib.crc32(blob) & 0xFFFFFFFF:08x}")
    os.makedirs(a.out_dir, exist_ok=True)
    inst = AetherInstance(a.rom, symbols=a.lst)
    sock = inst.start()

    async def body():
        c = BusClient(sock)
        await c.connect()
        st = await c.call("emulator/status", {})
        if st["romBytes"] != len(blob):
            raise SystemExit(f"REFUSED: server serves {st['romBytes']} B, {a.rom} is {len(blob)}")
        syms = {n: await G.lookup(c, n) for n in ("Debug_Scene_Index", "Camera_Y")}
        await c.call("emulator/run_frames", {"frames": a.settle})
        if a.travel:
            await c.call("emulator/play_input",
                         {"rows": [{"start": 0, "end": a.travel, "buttons": ["right"]}],
                          "maxFrames": a.travel})
            await c.call("emulator/release_all", {})
            await c.call("emulator/run_frames", {"frames": 30})
        for _ in range(40):
            at = await G.read_bus(c, addr=syms["Debug_Scene_Index"], length=1)
            if at == a.scene:
                break
            await G.step_scene(c)
        else:
            raise SystemExit(f"REFUSED: could not drive the scene cursor to {a.scene}")
        at = await G.read_bus(c, addr=syms["Debug_Scene_Index"], length=1)
        if at != a.scene:
            raise SystemExit(f"REFUSED: cursor reads {at}, wanted {a.scene}")
        mode3 = await G.read_bus(c, symbol=None, addr=await G.lookup(c, "VDP_Shadow_Table") + G.VDP_MODE3_OFF, length=1)
        if not (mode3 & G.VDP_MODE3_PERCOL):
            raise SystemExit(f"REFUSED: VDP reg $0B = ${mode3:02X}, bit 2 clear — this scene is "
                             f"not in per-column V-scroll, so it is not the subject")
        cam = await G.read_bus(c, addr=syms["Camera_Y"], length=4)
        vs = await G.read_vsram(c, 0x4C, 4)
        a19, b19 = struct.unpack(">HH", vs)
        print(f"scene {a.scene}  reg$0B=${mode3:02X}  Camera_Y={cam >> 16}  "
              f"VSRAM $4C={a19:04X} $4E={b19:04X}  AND={(a19 & b19) & 0x7FF:03X}  "
              f"expected={(cam >> 16) & 0x7FF:03X}")
        w, rows = await grab(c, 0, ACTIVE_H - 1)
        full = os.path.join(a.out_dir, f"{a.label}-scene{a.scene}-full.png")
        write_png(full, w, len(rows), rows)
        for name, x0, x1 in (("left", 0, 32), ("right", w - 32, w)):
            crop = [r[x0 * 3:x1 * 3] for r in rows]
            p = os.path.join(a.out_dir, f"{a.label}-scene{a.scene}-{name}.png")
            write_png(p, x1 - x0, len(crop), crop, scale=a.scale)
            print(f"  wrote {p}  (x {x0}..{x1 - 1}, {a.scale}x)")
        print(f"  wrote {full}  ({w}x{len(rows)})")

    try:
        asyncio.run(body())
    finally:
        inst.reap()
    return 0


if __name__ == "__main__":
    sys.exit(main())
