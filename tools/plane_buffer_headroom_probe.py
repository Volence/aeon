#!/usr/bin/env python3
"""Peak Plane_Buffer occupancy sampled BEFORE the drain.

CORRECTS pb2.py, which was vacuous: it sampled at frame boundaries, and
VInt_DrawLevel resets the write cursor to 0 after draining, so a
frame-boundary read returns 0 BY CONSTRUCTION. A green from that
instrument would have ruled out nothing.

This stops at VInt_DrawLevel -- the drain's own entry, before it runs --
so the value read is the frame's high-water mark.
"""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from aether_instance import aether_emulator, BusClient

LST = os.environ.get("PB_LST", "s4.debug.lst")
SETTLE = 240
PER_MODE = int(sys.argv[1]) if len(sys.argv) > 1 else 300

def sym(name):
    for line in open(LST, encoding="utf-8", errors="replace"):
        if f" {name} : " in line:
            return int(line.split(":")[1].split()[0], 16)
    raise SystemExit(f"BLOCKED: {name} not in {LST}")

async def go(sock):
    ptr, buf = sym("Plane_Buffer_Ptr"), sym("Plane_Buffer")
    size = ptr - buf
    addr = f"0x{ptr & 0xFFFFFF:06X}"
    b = BusClient(socket_path=sock, client_id="pb3", client_name="pb3")
    await b.connect()
    await b.call("emulator/run_frames", {"frames": SETTLE})
    print(f"buffer {size} B; a column is dropped SILENTLY once ptr > {size-2-136}")

    async def sample(buttons, n, tag):
        peak, hits, misses, hist = 0, 0, 0, {}
        for i in range(n):
            if buttons:
                await b.call("emulator/play_input",
                             {"rows": [{"start": 0, "end": 1, "buttons": buttons}], "maxFrames": 1})
            r = await b.call("emulator/run_to", {"symbol": "VInt_DrawLevel", "maxFrames": 3})
            if not r.get("reached"):
                misses += 1
                continue
            m = await b.call("emulator/read_memory", {"addr": addr, "len": 2})
            v = int(str(m["bytes"]).removeprefix("0x"), 16)
            if v > size:
                misses += 1
                continue
            hits += 1
            if v: hist[(v // 128) * 128] = hist.get((v // 128) * 128, 0) + 1
            peak = max(peak, v)
        await b.call("emulator/release_all", {})
        print(f"\n=== {tag} — {n} attempts ===")
        print(f"  stops reached           : {hits}   (unreached/invalid: {misses})")
        print(f"  PEAK before drain       : {peak} B of {size} B  ({100.0*peak/size:.1f}%)")
        print(f"  margin to silent drop   : {size-2-136-peak} B")
        for k in sorted(hist): print(f"    {k:5d}..{k+127:5d}  {hist[k]:4d}")
        return peak

    await sample([], PER_MODE, "at rest (control)")
    await sample(["right"], PER_MODE, "holding right")
    await sample(["left"], PER_MODE, "holding left (back over drawn ground)")
    await b.close()

with aether_emulator(os.environ.get("PB_ROM", "s4.debug.bin"), symbols=LST) as sock:
    asyncio.run(go(sock))
