#!/usr/bin/env python3
"""pic_witness — the RESOLVED picture at stop points of a two-phase fly leg, so two ROMs
whose page->frame assignment differs can still be compared cell for cell.

General-patch-loop parcel, 2026-09-27. The resident plain copy's nt_witness.py compares raw
nametable words. That is right when both ROMs place every page in the same frame; it is
wrong here, because a liveness lever changes WHICH frame an eviction frees, so the same
tile lands at a different physical index and the raw words differ while the picture is the
same. This witness resolves every word through the VRAM it names:

    cell = (word & $F800, the 32 pattern bytes at VRAM (word & $7FF) * 32)

and compares those. A cache word that names a frame whose page was evicted and replaced
resolves to the wrong pattern bytes, so the failure this parcel must not introduce is
visible to it. It drives the survey's transport (lag_flythrough_probe.Server with the socket
moved off /tmp, as gpl_probe.py does):

  1. boot `--boot` frames, hold `--dirs`; when the camera x reaches `--then-at-x`, switch to
     `--then-dirs` (the CPZ legs: right along the top, then down);
  2. at each stop point (ticks flown SINCE THE SWITCH >= t, for t in --ticks) release the
     input, run `--settle` frames, then dump VRAM $0000-$BFFF (every tile a nametable word
     can name), Plane A ($C000, 64x64 cells) and RAM Tile_Cache_Nametable (80x60);
  3. re-hold and continue.

  pic_witness.py dump --rom R --lst L --out X.json [--ticks 20,40,...]
  pic_witness.py compare A.json B.json
compare prints, per matched point (same camera), the visible Plane A window (41x29 cells)
and the whole tile cache, as RESOLVED cells that differ; exit 0 identical, 1 different,
2 unmatched. dump prints finished=1.
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

SOCKDIR = os.environ.get("TMPDIR") or str(Path.home() / ".cache" / "aeon-tmp")
if SOCKDIR.startswith("/tmp"):
    raise SystemExit("pic_witness: REFUSED, socket dir is under /tmp")
_orig_init = LFP.Server.__init__


def _init(self, rom, lst, tag):
    _orig_init(self, rom, lst, tag)
    self.sock = os.path.join(SOCKDIR, f"picw_{os.getpid()}_{tag}.sock")


LFP.Server.__init__ = _init

PLANE_A, PLANE_BYTES = 0xC000, 0x2000
TILES_BYTES = 0xC000          # every tile index an 11-bit word can name below the planes
NT_BYTES = 9600


async def read_vram(c, addr, n):
    got = b""
    while len(got) < n:
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
    if len(out) != n:
        raise RuntimeError(f"read_memory({addr:#x}, {n}) returned {len(out)} B")
    return out


def resolve(words, vram):
    """One short digest per cell: attribute bits + the 32 pattern bytes the index names."""
    out = []
    for i in range(0, len(words), 2):
        w = (words[i] << 8) | words[i + 1]
        t = w & 0x7FF
        pat = vram[t * 32:t * 32 + 32] if t * 32 + 32 <= len(vram) else b"OUT-OF-RANGE"
        out.append(hashlib.sha1(bytes([w >> 8 & 0xF8]) + pat).hexdigest()[:8])
    return out


async def halt_messages(c, rom_bytes):
    """RaiseError is `jsr <handler>` + the message: find stacked return addresses that point at
    text right after a `jsr abs.l` (4EB9) in ROM. Evidence for naming a halt, nothing more."""
    ram = await read_ram(c, 0xFF0000, 0x10000)
    out, seen = [], set()
    for off in range(0, len(ram) - 3, 2):
        v = int.from_bytes(ram[off:off + 4], "big")
        if 6 <= v < len(rom_bytes) - 4 and v not in seen and rom_bytes[v - 6:v - 4] == b"\x4e\xb9":
            txt = rom_bytes[v:v + 100].split(b"\0")[0]
            if len(txt) >= 8 and all(32 <= ch < 127 for ch in txt[:8]):
                seen.add(v)
                out.append(txt.decode("latin1"))
    return out


async def dump(a):
    rom, lst = str(Path(a.rom).resolve()), str(Path(a.lst).resolve())
    data = open(rom, "rb").read()
    head = dict(rom=os.path.basename(rom), crc="%08x" % zlib.crc32(data), size=len(data),
                dirs=a.dirs, then_dirs=a.then_dirs, then_at_x=a.then_at_x, ticks=a.ticks,
                boot=a.boot, settle=a.settle,
                loadavg_start=open("/proc/loadavg").read().split()[:3],
                date_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    ticks = [int(t) for t in a.ticks.split(",")]
    points = []
    async with LFP.Server(rom, lst, f"picw{os.getpid()}") as c:
        c._reader._limit = 64 * 1024 * 1024
        s = await syms(c, ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y", "Camera_Target",
                           "Lag_Frame_Count", "Tile_Cache_Nametable", "PageCache_Direct_Map",
                           "Page_Evict_Gen", "Page_Live_Forced", "Page_Live_Pad"])
        for need in ("Tile_Cache_Nametable", "PageCache_Direct_Map", "Logic_Tick"):
            if need not in s:
                raise SystemExit(f"symbol {need} not in {lst}: cannot witness")
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": a.boot})
        dirs = a.dirs.split(",")
        await c.call("emulator/hold", {"buttons": dirs, "down": True})
        guard = 0
        while True:                                   # phase 1: to the switch point
            cur = await snap(c, s)
            if cur["cx"] >= a.then_at_x:
                break
            await c.call("emulator/run_frames", {"frames": 1})
            guard += 1
            if guard > 5000:
                raise SystemExit("switch x never reached")
        await c.call("emulator/hold", {"buttons": dirs, "down": False})
        dirs = a.then_dirs.split(",")
        head["switch"] = dict(cam=[cur["cx"], cur["cy"]], lt=cur["lt"])
        await c.call("emulator/hold", {"buttons": dirs, "down": True})
        fly_base = (await snap(c, s))["lt"]
        flown = 0
        phases = [p.split(":") for p in a.phases.split(",")] if a.phases else []
        head["phases"] = a.phases
        if phases:
            dirs = phases[0][0].split("+")
            await c.call("emulator/hold", {"buttons": a.then_dirs.split(","), "down": False})
            await c.call("emulator/hold", {"buttons": dirs, "down": True})

        def reached(ph, cur):
            v = cur["cx"] if ph[1] == "x" else cur["cy"]
            return v >= int(ph[3]) if ph[2] == ">=" else v <= int(ph[3])

        async def advance_phase(cur):
            nonlocal dirs
            while phases and reached(phases[0], cur):
                phases.pop(0)
                await c.call("emulator/hold", {"buttons": dirs, "down": False})
                if phases:
                    dirs = phases[0][0].split("+")
                    await c.call("emulator/hold", {"buttons": dirs, "down": True})
                    print(f"  phase -> {phases[0]} at cam ({cur['cx']},{cur['cy']})", flush=True)
        head["halt"] = None
        for t in ticks:
            still, last_lt = 0, None
            while True:
                cur = await snap(c, s)
                await advance_phase(cur)
                if flown + cur["lt"] - fly_base >= t:
                    break
                still = still + 1 if cur["lt"] == last_lt else 0
                last_lt = cur["lt"]
                if still >= 120:                      # Logic_Tick stopped: a halt, name it
                    head["halt"] = dict(cam=[cur["cx"], cur["cy"]], lt=cur["lt"],
                                        messages=await halt_messages(c, data))
                    break
                await c.call("emulator/run_frames", {"frames": 1})
                guard += 1
                if guard > 40000:
                    raise SystemExit("tick target never reached")
            if head["halt"]:
                print(f"HALTED at cam {head['halt']['cam']}: {head['halt']['messages']}", flush=True)
                break
            await c.call("emulator/hold", {"buttons": dirs, "down": False})
            flown += cur["lt"] - fly_base
            await c.call("emulator/run_frames", {"frames": a.settle})
            st = await snap(c, s)
            vram = await read_vram(c, 0, TILES_BYTES)
            pa = await read_vram(c, PLANE_A, PLANE_BYTES)
            tc = await read_ram(c, s["Tile_Cache_Nametable"], NT_BYTES)
            dm = await rd(c, s["PageCache_Direct_Map"], 1)
            points.append(dict(target_tick=t, flown_at_stop=flown, settled=st, cam=[st["cx"], st["cy"]],
                               direct_map=dm, plane_a=resolve(pa, vram), tile_cache=resolve(tc, vram),
                               raw_tc_sha=hashlib.sha1(tc).hexdigest()[:12]))
            print(f"point t={t} cam=({st['cx']},{st['cy']}) lt={st['lt']} lag={st['lag']} DM={dm}", flush=True)
            await c.call("emulator/hold", {"buttons": dirs, "down": True})
            fly_base = (await snap(c, s))["lt"]
        # page evictions over the whole run (Page_Evict_Gen also counts the one PageCache_Init)
        head["evict_gen_end"] = await rd(c, s["Page_Evict_Gen"], 2) if "Page_Evict_Gen" in s else None
        head["live_forced_end"] = await rd(c, s["Page_Live_Forced"], 1) if "Page_Live_Forced" in s else None
        head["live_pad_end"] = await rd(c, s["Page_Live_Pad"], 1) if "Page_Live_Pad" in s else None
    head["loadavg_end"] = open("/proc/loadavg").read().split()[:3]
    head["points"] = points
    Path(a.out).write_text(json.dumps(head))
    print(f"{head['rom']} crc={head['crc']} switch={head['switch']} points={len(points)} "
          f"Page_Evict_Gen={head['evict_gen_end']} Page_Live_Forced={head["live_forced_end"]} Page_Live_Pad={head.get("live_pad_end")}")
    print("finished=1")


def compare(a):
    A, B = json.loads(Path(a.a).read_text()), json.loads(Path(a.b).read_text())
    print(f"A {A['rom']} crc={A['crc']}   B {B['rom']} crc={B['crc']}   "
          f"switch A {A['switch']['cam']} B {B['switch']['cam']}")
    if len(A["points"]) != len(B["points"]):
        print(f"POINT COUNTS DIFFER: {len(A['points'])} vs {len(B['points'])}; comparing the common prefix")
    rc = 0
    tot = [0, 0, 0]
    for pa, pb in zip(A["points"], B["points"]):
        if pa["cam"] != pb["cam"] or pa["target_tick"] != pb["target_tick"]:
            print(f"  t={pa['target_tick']} UNMATCHED cam {pa['cam']} vs {pb['cam']}")
            rc = max(rc, 2)
            continue
        cx, cy = pa["cam"]
        vis = [((cy // 8 + r) % 64) * 64 + (cx // 8 + c) % 64 for r in range(29) for c in range(41)]
        vd = sum(1 for i in vis if pa["plane_a"][i] != pb["plane_a"][i])
        td = sum(1 for x, y in zip(pa["tile_cache"], pb["tile_cache"]) if x != y)
        raw_same = pa["raw_tc_sha"] == pb["raw_tc_sha"]
        ok = vd == 0 and td == 0
        tot[0] += 1
        tot[1] += (vd == 0)
        tot[2] += (td == 0)
        print(f"  t={pa['target_tick']:>4} cam={tuple(pa['cam'])} DM {pa['direct_map']}/{pb['direct_map']} "
              f"lag {pa['settled']['lag']}/{pb['settled']['lag']} | visible planeA resolved diff {vd}/1189 | "
              f"tile cache resolved diff {td}/4800 | raw cache words {'same' if raw_same else 'differ'}  "
              f"{'IDENTICAL' if ok else 'DIFFERENT'}")
        if not ok:
            rc = max(rc, 1)
    if len(A["points"]) != len(B["points"]):
        rc = max(rc, 2)
    for nm, X in (("A", A), ("B", B)):
        if X.get("halt"):
            print(f"  {nm} HALTED at cam {X['halt']['cam']}: {X['halt']['messages']}")
            rc = max(rc, 1)
    print(f"points {tot[0]}: visible window identical at {tot[1]}, tile cache identical at {tot[2]}")
    print("verdict:", {0: "IDENTICAL resolved picture at every matched point", 1: "DIFFERENT",
                       2: "UNMATCHED points"}[rc])
    return rc


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("dump")
    d.add_argument("--rom", required=True)
    d.add_argument("--lst", required=True)
    d.add_argument("--dirs", default="right")
    d.add_argument("--then-dirs", default="down")
    d.add_argument("--then-at-x", type=int, default=int(os.environ.get("PICW_THEN_AT_X", "14400")))
    d.add_argument("--ticks", default="10,20,30,40,60,80,100,120,160,200,240,300,360,420")
    d.add_argument("--phases", default="", help="after the switch, a comma list of DIRS:AXIS:OP:VALUE "
                   "legs flown in order, e.g. 'down:y:>=:2000,left:x:<=:12400,up:y:<=:200'; stop points "
                   "then count ticks flown since the switch across all phases")
    d.add_argument("--boot", type=int, default=300)
    d.add_argument("--settle", type=int, default=30)
    d.add_argument("--out", required=True)
    c = sp.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    a = ap.parse_args()
    if a.cmd == "dump":
        asyncio.run(dump(a))
    else:
        sys.exit(compare(a))


if __name__ == "__main__":
    main()
