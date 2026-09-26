#!/usr/bin/env python3
"""pc_trace — per-frame RAM trace of the page-residency cache on one flown leg.

STRESSART-HALTS parcel (2026-09-26). Evidence, not a gate. Boots the ROM in a headless
oracle-aether (socket off /tmp), holds the given d-pad directions in DEBUG free flight, and
after EVERY video frame reads:
  camera, Frame_Counter, Logic_Tick, Page_Free_Head, PageIn_Cur_{Page,Frame,Flags},
  PageIn_Queue_Count + the FIFO, Cache_Art_Stall, Page_Table[0..pool), and every
  Page_Frames record (page, refcount, stamp, flags);
and RECOUNTS each frame's references from Tile_Cache_Nametable (the audit's ground truth),
so a frame whose stored refcount is 0 but which the nametable still names, or one the
nametable does not name at all, is visible per frame.

It stops when Logic_Tick has not advanced for 60 frames (a raise_error halt) or at
--frames, and prints the last --tail frames of trace plus, for every frame, a one-line
classification: P pinned, E evictable, R referenced (stored rc>0), D demand-published
unflagged rc0 (awaiting its first ref), '.' unassigned, '!' assigned/rc0/unflagged and NOT
PageIn_Cur_Frame (what the orphan audit calls leaked).

  pc_trace.py --rom R --lst L --dirs right[,down] [--frames 600] [--tail 40] [--json OUT]
Prints finished=1 on completion.
"""
import argparse
import asyncio
import json
import os
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-09-25-s4-lag"))
import lag_flythrough_probe as LFP  # noqa: E402

SOCKDIR = os.environ.get("TMPDIR") or str(Path.home() / ".cache" / "aeon-tmp")
if SOCKDIR.startswith("/tmp"):
    raise SystemExit("pc_trace: REFUSED, socket dir is under /tmp")
_orig_init = LFP.Server.__init__


def _init(self, rom, lst, tag):
    _orig_init(self, rom, lst, tag)
    self.sock = os.path.join(SOCKDIR, f"pctrace_{os.getpid()}_{tag}.sock")


LFP.Server.__init__ = _init

PAGE_FRAMES = 12          # POOL_TILE_CEILING 768 / 64 (derived at start from the listing's symbol spacing check)
NT_BYTES = 9600
PF_PINNED, PF_EVICTABLE = 1, 2
NAMES = ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y", "Page_Free_Head",
         "PageIn_Cur_Page", "PageIn_Cur_Frame", "PageIn_Cur_Flags", "PageIn_Queue_Count",
         "PageIn_Queue", "Cache_Art_Stall", "Page_Table", "Page_Frames", "Tile_Cache_Nametable",
         "PageIn_Pool_Pages", "PageCache_Direct_Map", "PageIn_InFlight", "PageIn_Staging_Busy",
         "PageIn_Land_Pending", "PageIn_Suspended"]
OPTIONAL = {"PageCache_Direct_Map"}   # absent before the streaming fix F1; read as 0


async def rd(c, addr, n):
    out = b""
    while len(out) < n:
        k = min(1024, n - len(out))
        r = await c.call("emulator/read_memory", {"addr": hex((addr + len(out)) & 0xFFFFFF), "len": k})
        raw = r["bytes"]
        raw = raw[2:] if raw[:2].lower() == "0x" else raw
        out += bytes.fromhex(raw)[:k]
    return out


def u16(b, o=0):
    return int.from_bytes(b[o:o + 2], "big")


async def state(c, s, pool):
    g = {}
    g["fc"] = u16(await rd(c, s["Frame_Counter"], 2))
    g["lt"] = int.from_bytes(await rd(c, s["Logic_Tick"], 4), "big")
    g["cx"] = int.from_bytes(await rd(c, s["Camera_X"], 4), "big") >> 16
    g["cy"] = int.from_bytes(await rd(c, s["Camera_Y"], 4), "big") >> 16
    g["free"] = (await rd(c, s["Page_Free_Head"], 1))[0]
    g["cur_page"] = u16(await rd(c, s["PageIn_Cur_Page"], 2))
    g["cur_frame"] = (await rd(c, s["PageIn_Cur_Frame"], 1))[0]
    g["cur_flags"] = (await rd(c, s["PageIn_Cur_Flags"], 1))[0]
    qn = (await rd(c, s["PageIn_Queue_Count"], 1))[0]
    q = await rd(c, s["PageIn_Queue"], 32)
    g["queue"] = [(u16(q, 4 * i), q[4 * i + 2]) for i in range(min(qn, 8))]
    g["stall"] = u16(await rd(c, s["Cache_Art_Stall"], 2))
    g["dm"] = (await rd(c, s["PageCache_Direct_Map"], 1))[0] if "PageCache_Direct_Map" in s else 0
    g["busy"] = [(await rd(c, s[k], 1))[0] for k in
                 ("PageIn_InFlight", "PageIn_Staging_Busy", "PageIn_Land_Pending", "PageIn_Suspended")]
    pt = await rd(c, s["Page_Table"], pool)
    g["pt"] = {p: pt[p] for p in range(pool) if pt[p] != 0xFF}
    pf = await rd(c, s["Page_Frames"], 8 * PAGE_FRAMES)
    nt = await rd(c, s["Tile_Cache_Nametable"], NT_BYTES)
    recount = [0] * 32
    for i in range(0, NT_BYTES, 2):
        t = u16(nt, i) & 0x7FF
        if t:
            recount[t >> 6] += 1
    frames = []
    for f in range(PAGE_FRAMES):
        page, rc, stamp = u16(pf, 8 * f), u16(pf, 8 * f + 2), u16(pf, 8 * f + 4)
        flags = pf[8 * f + 7]
        frames.append(dict(f=f, page=page, rc=rc, re=recount[f], stamp=stamp, flags=flags))
    g["frames"] = frames
    g["recount_hi"] = {f: recount[f] for f in range(PAGE_FRAMES, 32) if recount[f]}
    return g


def classify(g):
    out = []
    for fr in g["frames"]:
        if fr["page"] == 0xFFFF:
            ch = "."
        elif fr["flags"] & PF_PINNED:
            ch = "P"
        elif fr["flags"] & PF_EVICTABLE:
            ch = "E"
        elif fr["rc"]:
            ch = "R"
        elif fr["f"] == g["cur_frame"]:
            ch = "D"
        else:
            ch = "!"
        out.append(ch)
    return "".join(out)


def line(g):
    fr = " ".join(f"{x['f']}:p{x['page'] if x['page'] != 0xFFFF else '--'}/rc{x['rc']}"
                  f"{'' if x['rc'] == x['re'] else '(nt' + str(x['re']) + ')'}"
                  f"/{'P' if x['flags'] & 1 else ''}{'E' if x['flags'] & 2 else ''}" for x in g["frames"])
    return (f"fc={g['fc']} lt={g['lt']} cam=({g['cx']},{g['cy']}) cls={classify(g)} free={g['free']:02X} "
            f"cur=p{g['cur_page']}/f{g['cur_frame']}/fl{g['cur_flags']} stall={g['stall']} dm={g['dm']} "
            f"busy={g['busy']} q={g['queue']}\n    {fr}"
            + (f"\n    nametable names frames >= PAGE_FRAMES: {g['recount_hi']}" if g["recount_hi"] else ""))


async def main_async(a):
    data = open(a.rom, "rb").read()
    print(f"{os.path.basename(a.rom)} crc={zlib.crc32(data):08x} dirs={a.dirs}")
    async with LFP.Server(str(Path(a.rom).resolve()), str(Path(a.lst).resolve()), f"t{os.getpid()}") as c:
        s = await LFP.syms(c, NAMES)
        missing = [n for n in NAMES if n not in s and n not in OPTIONAL]
        if missing:
            raise SystemExit(f"pc_trace: UNMEASURABLE, symbols missing from the listing: {missing}")
        pool = u16(await rd(c, s["PageIn_Pool_Pages"], 2)) or 64
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": a.boot})
        pool = u16(await rd(c, s["PageIn_Pool_Pages"], 2))
        print(f"pool_pages={pool}")
        await c.call("emulator/hold", {"buttons": a.dirs.split(","), "down": True})
        hist, still, prev_lt, halted = [], 0, None, False
        for i in range(a.frames):
            await c.call("emulator/run_frames", {"frames": 1})
            g = await state(c, s, pool)
            g["i"] = i
            hist.append(g)
            still = still + 1 if g["lt"] == prev_lt else 0
            prev_lt = g["lt"]
            if still >= 60:
                halted = True
                break
        # the first frame of the final still-run is where the halt landed
        end = len(hist) - (still if halted else 0)
        print(f"{'HALTED' if halted else 'ran'}: {len(hist)} frames stepped; last live frame index {end - 1}")
        for g in hist[max(0, end - a.tail):end + 1]:
            print(f"[{g['i']}] " + line(g))
        if a.json:
            with open(a.json, "w") as fh:
                json.dump(hist[:end + 1], fh)
    print("finished=1")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--dirs", default="right")
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--tail", type=int, default=40)
    ap.add_argument("--json", default="")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
