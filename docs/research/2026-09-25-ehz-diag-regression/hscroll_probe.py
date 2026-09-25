#!/usr/bin/env python3
"""hscroll_probe.py <romA> <romB> [frames]: fly the diag leg on each ROM, and on every frame whose
logic tick advanced with no lag frame, read the whole Hscroll_Buffer (224 lines x FG/BG words)
keyed by camera (x, y). Then compare the two ROMs at every camera position both saw.
Research instrument for the curve-loop prototype: is its output identical to the shipped loop?"""
import asyncio, sys, zlib
sys.path.insert(0, "/tmp/claude-1000/-home-volence-sonic-hacks-aeon/49f49cb1-d570-40ef-a8a2-ffb2dc8e8dbc/scratchpad/probe/2026-09-25-s4-lag")
import lag_flythrough_probe as LFP
RUN = "--run" in sys.argv
if RUN: sys.argv.remove("--run")
from lag_flythrough_probe import rd, syms, snap

async def one(rom, frames):
    lst = rom[:-4] + ".lst"
    out = {}
    async with LFP.Server(rom, lst, "hs") as c:
        s = await syms(c, ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y", "Camera_Target",
                           "Lag_Frame_Count", "Hscroll_Buffer"])
        c._reader._limit = 64 * 1024 * 1024
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": 300})
        if RUN:   # physics: leave DEBUG free flight with B, run right, jump every 45 frames
            await c.call("emulator/press", {"buttons": ["b"]})
            await c.call("emulator/run_frames", {"frames": 8})
            await c.call("emulator/hold", {"buttons": ["right"], "down": True})
        else:
            await c.call("emulator/hold", {"buttons": ["right", "down"], "down": True})
        prev = await snap(c, s)
        for i in range(frames):
            if RUN and i % 45 == 0:
                await c.call("emulator/hold", {"buttons": ["c"], "down": True})
            if RUN and i % 45 == 10:
                await c.call("emulator/hold", {"buttons": ["c"], "down": False})
            await c.call("emulator/run_frames", {"frames": 1})
            cur = await snap(c, s)
            if cur["lt"] > prev["lt"] and cur["lag"] == prev["lag"]:
                r = await c.call("emulator/read_memory", {"addr": hex(s["Hscroll_Buffer"]), "len": 896})
                b = r["bytes"]; b = b[2:] if b.lower().startswith("0x") else b
                out.setdefault((cur["cx"], cur["cy"]), bytes.fromhex(b[:1792]))
            prev = cur
    return out

async def main():
    a, b = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 1100
    A = await one(a, n); B = await one(b, n)
    common = sorted(set(A) & set(B))
    diff = [k for k in common if A[k] != B[k]]
    band = [k for k in common if k[1] < 1024]
    print(f"A {a.split('/')[-1]} crc={zlib.crc32(open(a,'rb').read()):08x} samples={len(A)}")
    print(f"B {b.split('/')[-1]} crc={zlib.crc32(open(b,'rb').read()):08x} samples={len(B)}")
    print(f"common camera positions {len(common)} (EHZ band y<1024: {len(band)}); differing {len(diff)}")
    for k in diff[:10]:
        x, y = A[k], B[k]
        lines = [i for i in range(224) if x[i*4:i*4+4] != y[i*4:i*4+4]]
        print(f"  cam {k}: {len(lines)} lines differ, first {lines[:8]}")
    print("finished=1")

asyncio.run(main())
