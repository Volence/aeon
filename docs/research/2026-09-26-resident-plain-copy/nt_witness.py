#!/usr/bin/env python3
"""nt_witness — dump the Plane A / Plane B VRAM nametables (and the tile cache) at stop
points along a fly leg, so two ROMs can be compared at MATCHED points.

Resident plain copy parcel, 2026-09-26. The survey's stand-in plain copy put the wrong art on
screen with every lag number looking better, so the picture needs its own witness, and a
screenshot is not one. This drives the same headless transport the perf survey uses
(docs/research/2026-09-25-s4-lag/lag_flythrough_probe.py: Server, rd, syms, snap) and:

  1. boots `--boot` frames, then HOLDS `--dirs` (debug free flight: the camera path is a pure
     function of the input, one step per logic tick);
  2. at each stop point (Logic_Tick - tick_at_press >= t, for t in --ticks) RELEASES the input
     and runs `--settle` frames so every queued plane draw has drained and the camera is still;
  3. records the camera, Logic_Tick, Frame_Counter and Lag_Frame_Count, and dumps
     VRAM Plane A ($C000, 8 KiB), Plane B ($E000, 8 KiB) and RAM Tile_Cache_Nametable;
  4. re-holds `--dirs` and continues to the next point.

A point is MATCHED between two ROMs when its camera (x, y) agrees; `compare` refuses to call an
unmatched point identical. Lag changes WHEN a tick happens, not what it computes, so matched
points are the fair comparison; video-frame-matched points would compare different places.

  nt_witness.py dump --rom R --lst L --dirs right,down --ticks 60,120 --out X.json
  nt_witness.py compare A.json B.json
Prints finished=1 on a completed dump; compare exits 0 identical, 1 different, 2 unmatched.
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-09-25-s4-lag"))
import lag_flythrough_probe as LFP  # noqa: E402
from lag_flythrough_probe import rd, syms, snap  # noqa: E402

PLANE_A, PLANE_B, PLANE_BYTES = 0xC000, 0xE000, 0x2000   # engine/system/constants.emp VRAM_PLANE_A/B, 64x64 cells


async def read_vram(c, addr, n):
    got = b""
    while len(got) < n:                      # the server caps one read at 4096 bytes
        k = min(4096, n - len(got))
        r = await c.call("emulator/read_vram", {"addr": hex(addr + len(got)), "len": k})
        raw = r["bytes"]
        raw = raw[2:] if raw[:2].lower() == "0x" else raw
        got += bytes.fromhex(raw)[:k]
    if len(got) != n:
        raise RuntimeError(f"read_vram({addr:#x}, {n}) returned {len(got)} B")
    return got


async def read_ram(c, addr, n):
    out = b""
    while len(out) < n:
        k = min(1024, n - len(out))
        r = await c.call("emulator/read_memory", {"addr": hex((addr + len(out)) & 0xFFFFFF), "len": k})
        raw = r["bytes"]
        raw = raw[2:] if raw[:2].lower() == "0x" else raw
        out += bytes.fromhex(raw)[:k]
    return out


async def dump(a):
    rom, lst = str(Path(a.rom).resolve()), str(Path(a.lst).resolve())
    data = open(rom, "rb").read()
    head = dict(rom=os.path.basename(rom), crc="%08x" % zlib.crc32(data), size=len(data),
                dirs=a.dirs, ticks=a.ticks, boot=a.boot, settle=a.settle,
                loadavg_start=open("/proc/loadavg").read().split()[:3],
                date_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    dirs = a.dirs.split(",")
    ticks = [int(t) for t in a.ticks.split(",")]
    points = []
    async with LFP.Server(rom, lst, f"ntw{os.getpid()}") as c:
        c._reader._limit = 64 * 1024 * 1024
        s = await syms(c, ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y",
                           "Camera_Target", "Lag_Frame_Count", "Tile_Cache_Nametable",
                           "PageCache_Direct_Map"])
        for need in ("Tile_Cache_Nametable", "PageCache_Direct_Map", "Logic_Tick"):
            if need not in s:
                raise SystemExit(f"symbol {need} not in {lst}: cannot witness")
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": a.boot})
        head["direct_map"] = await rd(c, s["PageCache_Direct_Map"], 1)
        s0 = await snap(c, s)
        head["after_boot"] = s0
        await c.call("emulator/hold", {"buttons": dirs, "down": True})
        # Stop points count FLOWN ticks only: the settle at each point runs ticks too (with
        # the input released), and counting those made every later point land at once on
        # the first point's camera (measured: 15 points, one camera, per leg).
        fly_base = s0["lt"]
        flown = 0
        guard = 0
        for t in ticks:
            while True:
                cur = await snap(c, s)
                if flown + cur["lt"] - fly_base >= t:
                    break
                await c.call("emulator/run_frames", {"frames": 1})
                guard += 1
                if guard > 20000:
                    raise SystemExit("tick target never reached")
            await c.call("emulator/hold", {"buttons": dirs, "down": False})
            flown += cur["lt"] - fly_base
            await c.call("emulator/run_frames", {"frames": a.settle})
            st = await snap(c, s)
            pa = await read_vram(c, PLANE_A, PLANE_BYTES)
            pb = await read_vram(c, PLANE_B, PLANE_BYTES)
            tc = await read_ram(c, s["Tile_Cache_Nametable"], 9600)
            points.append(dict(target_tick=t, flown_at_stop=flown, settled=st,
                               cam=[st["cx"], st["cy"]],
                               plane_a=pa.hex(), plane_b=pb.hex(), tile_cache=tc.hex(),
                               sha_a=hashlib.sha1(pa).hexdigest()[:12],
                               sha_b=hashlib.sha1(pb).hexdigest()[:12],
                               sha_tc=hashlib.sha1(tc).hexdigest()[:12]))
            print(f"point t={t} cam=({st['cx']},{st['cy']}) lt={st['lt']} lag={st['lag']} "
                  f"A={points[-1]['sha_a']} B={points[-1]['sha_b']} TC={points[-1]['sha_tc']}",
                  flush=True)
            await c.call("emulator/hold", {"buttons": dirs, "down": True})
            fly_base = (await snap(c, s))["lt"]
        head["direct_map_end"] = await rd(c, s["PageCache_Direct_Map"], 1)
    head["loadavg_end"] = open("/proc/loadavg").read().split()[:3]
    head["points"] = points
    Path(a.out).write_text(json.dumps(head))
    print(f"{head['rom']} crc={head['crc']} direct_map boot=${head['direct_map']:02X} "
          f"end=${head['direct_map_end']:02X} points={len(points)}")
    print("finished=1")


def diff_count(x, y):
    bx, by = bytes.fromhex(x), bytes.fromhex(y)
    return sum(1 for i in range(0, len(bx), 2) if bx[i:i + 2] != by[i:i + 2])


def compare(a):
    A, B = json.loads(Path(a.a).read_text()), json.loads(Path(a.b).read_text())
    print(f"A {A['rom']} crc={A['crc']} direct_map=${A['direct_map']:02X}   "
          f"B {B['rom']} crc={B['crc']} direct_map=${B['direct_map']:02X}   dirs={A['dirs']}")
    if len(A["points"]) != len(B["points"]):
        print(f"UNMATCHED: {len(A['points'])} vs {len(B['points'])} points")
        return 2
    rc = 0
    for pa, pb in zip(A["points"], B["points"]):
        if pa["cam"] != pb["cam"] or pa["target_tick"] != pb["target_tick"]:
            print(f"  t={pa['target_tick']} UNMATCHED cam {pa['cam']} vs {pb['cam']}")
            rc = max(rc, 2)
            continue
        d = {k: diff_count(pa[k], pb[k]) for k in ("plane_a", "plane_b", "tile_cache")}
        # Plane A split: the VISIBLE window (41 x 29 cells from the camera, wrapped on the
        # 64 x 64 plane) against the OFF-SCREEN rest. Off-screen cells hold whatever was
        # drawn there on the way, and which strips got drawn when depends on lag timing,
        # so they can differ between two ROMs whose copy is identical (a timing-only
        # control shows this). The visible window and the tile cache (the copy's own
        # output) cannot.
        cx, cy = pa["cam"]
        vis = {(((cy // 8 + r) % 64) * 64 + (cx // 8 + c) % 64) for r in range(29) for c in range(41)}
        ax, bx = bytes.fromhex(pa["plane_a"]), bytes.fromhex(pb["plane_a"])
        diff_cells = [i // 2 for i in range(0, len(ax), 2) if ax[i:i + 2] != bx[i:i + 2]]
        vis_diff = sum(1 for c in diff_cells if c in vis)
        off_diff = len(diff_cells) - vis_diff
        vis_nz = sum(1 for c in vis if ax[2 * c:2 * c + 2] != b"\0\0")
        tc_nz = sum(1 for i in range(0, 9600, 2) if bytes.fromhex(pa["tile_cache"])[i:i + 2] != b"\0\0")
        ok = vis_diff == 0 and d["plane_b"] == 0 and d["tile_cache"] == 0
        print(f"  t={pa['target_tick']:>4} cam={tuple(pa['cam'])} lagA={pa['settled']['lag']} "
              f"lagB={pb['settled']['lag']} | planeA visible diff {vis_diff} (content {vis_nz}/1189) "
              f"off-screen diff {off_diff} | planeB diff {d['plane_b']} | tilecache diff "
              f"{d['tile_cache']} (content {tc_nz}/4800)  {'IDENTICAL' if ok else 'DIFFERENT'}")
        if not ok:
            rc = max(rc, 1)
    print("verdict:", {0: "IDENTICAL (visible plane A, plane B, tile cache) at every matched point",
                       1: "DIFFERENT", 2: "UNMATCHED points"}[rc])
    return rc


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump")
    d.add_argument("--rom", required=True)
    d.add_argument("--lst", required=True)
    d.add_argument("--dirs", default="right")
    d.add_argument("--ticks", default="60,120,180,240,300,360")
    d.add_argument("--boot", type=int, default=300)
    d.add_argument("--settle", type=int, default=30)
    d.add_argument("--out", required=True)
    c = sub.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    a = ap.parse_args()
    if a.cmd == "dump":
        asyncio.run(dump(a))
        return 0
    return compare(a)


if __name__ == "__main__":
    sys.exit(main())
