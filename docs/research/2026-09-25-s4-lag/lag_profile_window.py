#!/usr/bin/env python3
"""lag_profile_window — which routines own the cycles in one window of a flythrough.

Same boot and drive as lag_flythrough_probe (reset, BOOT frames, optional B to leave debug
free flight, hold the named d-pad buttons), then PRE unprofiled frames, then a WINDOW-frame
sample on the new oracle's exact per-invocation profiler (the tick_variance_probe method:
run_frames(W+1) so the sample holds exactly W complete frames; the server's completeness
identity is CHECKED, not trusted).

Prints, per routine, inclusive cycles and self cycles PER LOGIC TICK over the window
(Logic_Tick delta read from the engine), and the whole window's cycles per tick. 127,840 is
one NTSC video frame of 68000 cycles (7.67 MHz / 59.92 Hz); a tick above it is a lag frame.
"""
import argparse
import asyncio
import json
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lag_flythrough_probe import Server, rd, syms, snap  # noqa: E402

FRAME_CYC = 127840


async def go(a):
    rom, lst = str(Path(a.rom).resolve()), str(Path(a.lst).resolve())
    crc = "%08x" % zlib.crc32(open(rom, "rb").read())
    async with Server(rom, lst, "prof") as c:
        s = await syms(c, ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y",
                           "Camera_Target", "Lag_Frame_Count"])
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": a.boot})
        if a.press_b:
            await c.call("emulator/press", {"buttons": ["b"]})
            await c.call("emulator/run_frames", {"frames": 128})
        await c.call("emulator/hold", {"buttons": a.dirs.split(","), "down": True})
        if a.pre:
            await c.call("emulator/run_frames", {"frames": a.pre})
        s0 = await snap(c, s)
        await c.call("emulator/set_profiler", {"enabled": True, "perFrame": True})
        await c.call("emulator/run_frames", {"frames": a.window + 1})
        pf = await c.call("emulator/get_profiler_frames", {"frames": a.window + 8, "top": 512})
        await c.call("emulator/set_profiler", {"enabled": False})
        s1 = await snap(c, s)
    rows = pf["routines"]["items"]
    selfsum = sum(r["cyclesSelfTotal"] for r in rows) + sum(
        pf["interrupts"][k]["cyclesSelfTotal"] for k in ("hint", "vint"))
    ident = pf["sampleCycles"] - selfsum - pf["unattributedCycles"]
    ticks = s1["lt"] - s0["lt"]
    vfr = (s1["fc"] - s0["fc"]) & 0xFFFF
    print(f"{Path(rom).name} crc={crc} dirs={a.dirs} press_b={a.press_b} pre={a.pre} "
          f"window={a.window} frameCount={pf['frameCount']}")
    print(f"camera ({s0['cx']},{s0['cy']}) -> ({s1['cx']},{s1['cy']}); video frames {vfr}, "
          f"logic ticks {ticks}, lag {vfr - ticks}; Lag_Frame_Count "
          f"{(s1['lag'] - s0['lag']) if s0['lag'] is not None else 'n/a'}")
    print(f"identity remainder {ident} (must be 0); truncated={pf['routines']['truncated']} "
          f"abandoned={pf['abandonedFrames']} depthExceeded={pf['depthExceeded']}")
    vs = pf["interrupts"]["vint"]["cyclesSelfTotal"]
    hs = pf["interrupts"]["hint"]["cyclesSelfTotal"]
    print(f"sampleCycles {pf['sampleCycles']}  = {pf['sampleCycles'] / max(ticks, 1):.0f} per tick; "
          f"vint self {vs / max(ticks, 1):.0f}/tick, hint self {hs / max(ticks, 1):.0f}/tick")
    vsync = next((r for r in rows if r.get("name") == "VSync_Wait"), None)
    if vsync:
        work = pf["sampleCycles"] - vsync["cyclesTotal"]
        print(f"work (sample - VSync_Wait inclusive) {work / max(ticks, 1):.0f} cyc/tick "
              f"= {work / max(ticks, 1) / FRAME_CYC:.3f} frames/tick")
    print(f"{'routine':<34} {'incl/tick':>10} {'self/tick':>10} {'calls/tick':>10}")
    for r in sorted(rows, key=lambda r: -r["cyclesTotal"])[:a.top]:
        print(f"{(r.get('name') or r['addr'])[:34]:<34} {r['cyclesTotal'] / max(ticks, 1):>10.0f} "
              f"{r['cyclesSelfTotal'] / max(ticks, 1):>10.0f} {r['callsTotal'] / max(ticks, 1):>10.2f}")
    if a.out:
        Path(a.out).write_text(json.dumps(dict(rom=Path(rom).name, crc=crc, args=vars(a),
                                               s0=s0, s1=s1, pf=pf)))
    print("finished=1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--dirs", default="right")
    ap.add_argument("--press-b", action="store_true")
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--pre", type=int, default=0)
    ap.add_argument("--window", type=int, default=60)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--out")
    asyncio.run(go(ap.parse_args()))


if __name__ == "__main__":
    main()
