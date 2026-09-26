#!/usr/bin/env python3
"""evict_order_probe — how good are the eviction CHOICES under churn? (GPL-A3 build, 2026-09-27)

The design parcel flagged one change it could not measure: A3 orders eviction candidates by
"last known wanted" (publish time, refreshed when an eviction choice sees the frame live)
where the refcount design used "last released" (the 1->0 time). Both evict only unnamed
frames, so the difference is purely which dead page goes first; a worse order shows up as
pages evicted and then needed again. This probe flies a zigzag and counts, per video frame,
from Page_Table (the residency map every other number here derives from):

  evictions   a page resident in one frame and absent in the next
  loads       a page absent in one frame and resident in the next
  RE-LOADS    a load of a page that had been resident earlier in this run and was evicted:
              the cost of a choice that turned out wrong. The headline number.
and at the end Dbg_PageCache_Demands (DEBUG: demand requests enqueued, each a fill stall on a
non-resident page), Page_Evict_Gen, and the lag (dFrame_Counter - dLogic_Tick) in motion.

The drive is keyed to CAMERA thresholds, as pic_witness.py's zigzag is: hold RIGHT (and the
switch heading) until the camera passes --then-at-x, then each phase DIRS:AXIS:OP:VALUE in
turn. Two ROMs fly the same camera path unless an art hold stops one camera for a frame, so
the probe prints the camera at every phase change for the comparison to check. One private
headless oracle-aether per run (tools/aether_instance.py). Prints finished=1.

  evict_order_probe.py --rom R --lst L --then-at-x 14400 --phases 'down:y:>=:2400,...'
"""
import argparse
import asyncio
import json
import sys
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3] / "tools"
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance  # noqa: E402
from stressart_legs_witness import sym, rd  # noqa: E402

SYMS = ("Logic_Tick", "Frame_Counter", "Camera_X", "Camera_Y", "Page_Table", "PageIn_Pool_Pages",
        "Page_Evict_Gen", "Dbg_PageCache_Demands")


async def run(sock, a):
    b = BusClient(socket_path=sock, client_id="evord", client_name="evict-order-probe")
    await b.connect()
    s = {n: await sym(b, n) for n in SYMS}
    u16 = lambda bs: int.from_bytes(bs, "big")  # noqa: E731

    async def cam():
        return (u16(await rd(b, s["Camera_X"], 4)) >> 16, u16(await rd(b, s["Camera_Y"], 4)) >> 16)

    await b.call("emulator/run_frames", {"frames": a.boot})
    pool = u16(await rd(b, s["PageIn_Pool_Pages"], 2))
    phases = [p.split(":") for p in a.phases.split(",")] if a.phases else []
    dirs = a.dirs.split(",")
    await b.call("emulator/hold", {"buttons": dirs, "down": True})
    lt0, fc0 = u16(await rd(b, s["Logic_Tick"], 4)), u16(await rd(b, s["Frame_Counter"], 2))
    switched, log = False, []
    ever, prev = set(), None
    ev = loads = reloads = 0
    halt_still, last_lt = 0, None
    for f in range(a.frames):
        await b.call("emulator/run_frames", {"frames": 1})
        cx, cy = await cam()
        table = await rd(b, s["Page_Table"], pool)
        res = {p for p in range(pool) if table[p] != 0xFF}
        if prev is not None:
            ev += len(prev - res)
            new = res - prev
            loads += len(new)
            reloads += len(new & ever)
        ever |= res
        prev = res
        lt = u16(await rd(b, s["Logic_Tick"], 4))
        halt_still = halt_still + 1 if lt == last_lt else 0
        last_lt = lt
        if halt_still >= 60:
            log.append(f"HALT at frame {f} cam ({cx},{cy})")
            break
        if not switched and cx >= a.then_at_x:
            await b.call("emulator/hold", {"buttons": dirs, "down": False})
            dirs = (phases[0][0] if phases else a.then_dirs).replace("+", ",").split(",")
            await b.call("emulator/hold", {"buttons": dirs, "down": True})
            switched = True
            log.append(f"switch at frame {f} cam ({cx},{cy}) -> {dirs}")
            continue
        if switched and phases:
            ph = phases[0]
            v = cx if ph[1] == "x" else cy
            if (v >= int(ph[3])) if ph[2] == ">=" else (v <= int(ph[3])):
                phases.pop(0)
                await b.call("emulator/hold", {"buttons": dirs, "down": False})
                if not phases:
                    log.append(f"phases done at frame {f} cam ({cx},{cy})")
                    break
                dirs = phases[0][0].replace("+", ",").split(",")
                await b.call("emulator/hold", {"buttons": dirs, "down": True})
                log.append(f"phase at frame {f} cam ({cx},{cy}) -> {dirs}")
    lt1, fc1 = u16(await rd(b, s["Logic_Tick"], 4)), u16(await rd(b, s["Frame_Counter"], 2))
    out = dict(pool=pool, frames=f + 1, ticks=lt1 - lt0, video=(fc1 - fc0) & 0xFFFF,
               lag=((fc1 - fc0) & 0xFFFF) - (lt1 - lt0), evictions=ev, loads=loads, reloads=reloads,
               demands=u16(await rd(b, s["Dbg_PageCache_Demands"], 2)),
               evict_gen=u16(await rd(b, s["Page_Evict_Gen"], 2)), cam_end=list(await cam()), log=log)
    await b.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--dirs", default="right")
    ap.add_argument("--then-dirs", default="down")
    ap.add_argument("--then-at-x", type=int, default=14400)
    ap.add_argument("--phases", default="")
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--frames", type=int, default=6000)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rom = Path(a.rom).resolve()
    inst = AetherInstance(str(rom), symbols=str(Path(a.lst).resolve()))
    try:
        out = asyncio.run(run(inst.start(), a))
    finally:
        inst.reap()
    out.update(rom=rom.name, crc="%08x" % zlib.crc32(rom.read_bytes()), phases=a.phases)
    Path(a.out).write_text(json.dumps(out, indent=1))
    for line in out.pop("log"):
        print("  " + line)
    print(json.dumps(out))
    print("finished=1")


if __name__ == "__main__":
    main()
