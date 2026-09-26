#!/usr/bin/env python3
"""ojz_feel_probe — play canonical OJZ act 1 the way a player does and record every frame.

2026-09-27, perf/ojz-feel. Research instrument, not a gate. Transport, symbol lookup and the
server wrapper are the EHZ-run-lag parcel's (ehz_run_probe.Server, which is the S2CLIP-LAG
study's with the socket under $HOME), imported, not copied.

A LEG is a script of steps, run in order after boot (+ B to leave DEBUG free flight):

  warp:X,Y            place the player through the DEBUG warp mailbox (never a bare Camera_X
                      poke), then settle 60 frames (not recorded)
  settle:N            run N frames unrecorded
  hold:DIRS:T         hold DIRS (e.g. right or right+c) for T logic ticks
  auto:DIR:T          hold DIR for T ticks; jump (C for 16 ticks) when x has not moved for 12
                      ticks on the ground (a wall), the way a player hops a step
  spindash:DIR        down, C x4, release, then hold DIR (38 ticks of charge)
  shuttle:T:N         N times: hold right T ticks, hold left T ticks (reversing direction)
  jumps:DIR:N:P       N jumps while holding DIR, one every P ticks (C for 16 ticks)

Every input is keyed to LOGIC TICKS since the step began, so the input on tick t is a function
of t alone and a lag frame cannot shift the path (the ehz_run_probe rule).

Per video frame the leg records: [i, dFrame_Counter, dLogic_Tick, dLag_Frame_Count, camX, camY,
px, py, x_vel, y_vel, player_state, step_index]. Lag over any window is sum(dFC) - sum(dLT).

--windows F,F,..  arm the profiler (callers lens) at each frame index and read it --win-len
frames later: attribution for a deterministic re-run of a leg whose lag frames are known.

--dump: on each frame that ends one on-time tick (dFC 1, dLT 1, no lag), keyed by step:tick, keep
[camX, camY, sha1(Hscroll_Buffer + Parallax_Vscroll_Column_Buf + Vscroll_Factor),
 sha1(VRAM Plane A over the camera window +1 cell each side), sha1(VRAM Plane B, all 8 KiB),
 coverage = visible columns/rows the plane streamer has NOT drawn (right, left, bottom, top;
 > 0 is a hole on screen; ehz_run_probe's --coverage rule)]
for before/after picture identity at matched ticks (picture_cmp.py).
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
sys.path.insert(0, str(HERE.parent / "2026-09-27-ehz-run-lag"))
sys.path.insert(0, str(HERE.parent / "2026-09-25-s4-lag"))
import ehz_run_probe as ERP  # noqa: E402
from lag_flythrough_probe import rd, syms  # noqa: E402
import lag_flythrough_probe as LFP  # noqa: E402

# OJZFEEL_ORACLE overrides the headless core binary (the transport resolves oracle's
# target/release/oracle-aether by default). Recorded in every leg's JSON.
if os.environ.get("OJZFEEL_ORACLE"):
    LFP.SERVER = os.environ["OJZFEEL_ORACLE"]

SST_X, SST_Y, SST_XVEL, SST_YVEL, SST_STATUS = 0x02, 0x06, 0x0A, 0x0C, 0x1E
ST_IN_AIR = 3


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def pl_state_off(lst):
    for line in open(lst, errors="replace"):
        if "EQU _pl_state" in line:
            return int(line.split("$")[-1], 16)
    raise SystemExit("_pl_state not in the listing")


def parse_script(s):
    return [tuple(p.split(":")) for p in s.split(";") if p]


class Driver:
    """Turns the current step + ticks-in-step + player state into a held set."""

    def __init__(self, step):
        self.step = step
        self.best, self.best_t, self.until = None, 0, -1

    def length(self):
        k = self.step[0]
        if k == "hold" or k == "auto":
            return int(self.step[2])
        if k == "spindash":
            return int(self.step[2]) if len(self.step) > 2 else 120
        if k == "shuttle":
            return 2 * int(self.step[1]) * int(self.step[2])
        if k == "jumps":
            return int(self.step[2]) * int(self.step[3])
        raise SystemExit(f"unknown step {self.step}")

    def want(self, t, px, air):
        k = self.step[0]
        if k == "hold":
            return set(x for x in self.step[1].split("+") if x)
        if k == "auto":
            d = self.step[1]
            if self.best is None or (px - self.best) * (1 if d == "right" else -1) > 0:
                self.best, self.best_t = px, t
            if t - self.best_t >= 12 and t >= self.until and not air:
                self.best_t = t
                self.until = t + 16
            return {d, "c"} if t < self.until else {d}
        if k == "spindash":
            d = self.step[1]
            if t < 4:
                return {"down"}
            if t < 28:
                return {"down", "c"} if ((t - 4) % 6) < 2 else {"down"}
            if t < 30:
                return {"down"}
            return {d}
        if k == "shuttle":
            T = int(self.step[1])
            return {"right"} if (t // T) % 2 == 0 else {"left"}
        if k == "jumps":
            P = int(self.step[3])
            return {self.step[1], "c"} if (t % P) < 16 else {self.step[1]}
        raise SystemExit(k)


CACHE = ["Cache_Left_Col", "Cache_Head_Col", "Cache_Top_Row", "Cache_Bottom_Row",
         "Cache_Fill_Resume_Col", "Cache_Fill_Budget", "Cache_Fill_RowResume_Row"]
PLANE_A, PLANE_B, PLANE_BYTES = 0xC000, 0xE000, 0x2000   # VRAM_PLANE_A/B, 64x64 cells


async def read_vram(c, addr, n):
    """nt_witness.py's reader (docs/research/2026-09-26-resident-plain-copy): 4 KiB per call."""
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


DUMP = [("Hscroll_Buffer", 896), ("Parallax_Vscroll_Column_Buf", 80), ("Vscroll_Factor", 4)]


async def main_async(a):
    rom, lst = str(Path(a.rom).resolve()), str(Path(a.lst).resolve())
    data = open(rom, "rb").read()
    plo = pl_state_off(lst)
    head = dict(rom=os.path.basename(rom), crc="%08x" % zlib.crc32(data), size=len(data),
                script=a.script, server=LFP.SERVER,
                server_md5=hashlib.md5(open(LFP.SERVER, "rb").read()).hexdigest(), loadavg_start=open("/proc/loadavg").read().split()[:3],
                date_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    rows, windows, dumps, notes, cache = [], [], {}, [], []
    async with ERP.Server(rom, lst, "feel", a.out + ".server.log") as c:
        s = await syms(c, ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y", "Camera_Target",
                           "Lag_Frame_Count", "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag"])
        debug = "Lag_Frame_Count" in s and "Warp_Req_Flag" in s
        if not debug and "warp:" in a.script:
            raise SystemExit("warp steps need the DEBUG shape (the warp mailbox)")
        ds = await syms(c, [n for n, _ in DUMP]) if a.dump else {}
        EDGES = ["Section_Right_Col_Written", "Section_Left_Col_Written",
                 "Section_Bottom_Row_Written", "Section_Top_Row_Written"]
        es = await syms(c, EDGES) if a.dump else {}
        if a.dump and (len(ds) != len(DUMP) or len(es) != len(EDGES)):
            raise SystemExit(f"--dump: not every buffer/edge word resolved: {sorted(ds)} {sorted(es)}")
        cs = await syms(c, CACHE) if a.cache else {}
        if a.cache and len(cs) != len(CACHE):
            raise SystemExit(f"--cache: not every fill word resolved: {sorted(cs)}")
        c._reader._limit = 64 * 1024 * 1024
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": a.boot})
        if debug:
            await c.call("emulator/press", {"buttons": ["b"]})
            await c.call("emulator/run_frames", {"frames": 8})
            notes.append("pressed B to leave free flight")
        else:
            await c.call("emulator/run_frames", {"frames": 8})
            notes.append("release shape: no free flight, no B")

        async def leader():
            tgt = await rd(c, s["Camera_Target"], 2)
            return 0xFF0000 | tgt if tgt & 0x8000 else tgt

        async def snap():
            L = await leader()
            r = await c.call("emulator/read_memory", {"addr": hex(L), "len": 0x40})
            hx = r["bytes"]
            b = bytes.fromhex(hx[2:] if hx.lower().startswith("0x") else hx)
            return dict(fc=await rd(c, s["Frame_Counter"], 2), lt=await rd(c, s["Logic_Tick"], 4),
                        lag=(await rd(c, s["Lag_Frame_Count"], 4)) if debug else 0,
                        cx=(await rd(c, s["Camera_X"], 4)) >> 16, cy=(await rd(c, s["Camera_Y"], 4)) >> 16,
                        px=int.from_bytes(b[SST_X:SST_X + 2], "big"),
                        py=s16(int.from_bytes(b[SST_Y:SST_Y + 2], "big")),
                        xv=s16(int.from_bytes(b[SST_XVEL:SST_XVEL + 2], "big")),
                        yv=s16(int.from_bytes(b[SST_YVEL:SST_YVEL + 2], "big")),
                        st=b[plo], air=(b[SST_STATUS] >> ST_IN_AIR) & 1)

        held = set()

        async def setheld(w):
            nonlocal held
            up, down = sorted(held - w), sorted(w - held)
            if up:
                await c.call("emulator/hold", {"buttons": up, "down": False})
            if down:
                await c.call("emulator/hold", {"buttons": down, "down": True})
            held = w

        wins = sorted(set(int(x) for x in a.windows.split(",") if x)) if a.windows else []
        win_open = None
        i = 0
        for si, step in enumerate(parse_script(a.script)):
            if step[0] == "warp":
                await setheld(set())
                wx, wy = (int(v) for v in step[1].split(","))
                await c.call("emulator/write_memory", {"addr": hex(s["Warp_Req_X"]), "bytes": "0x%04x" % (wx & 0xFFFF)})
                await c.call("emulator/write_memory", {"addr": hex(s["Warp_Req_Y"]), "bytes": "0x%04x" % (wy & 0xFFFF)})
                await c.call("emulator/write_memory", {"addr": hex(s["Warp_Req_Flag"]), "bytes": "0x01"})
                for _ in range(120):
                    await c.call("emulator/run_frames", {"frames": 1})
                    if await rd(c, s["Warp_Req_Flag"], 1) == 0:
                        break
                else:
                    raise SystemExit("warp mailbox never acknowledged")
                await c.call("emulator/run_frames", {"frames": 60})
                sp = await snap()
                notes.append(f"step {si} warp ({wx},{wy}) -> player ({sp['px']},{sp['py']}) cam ({sp['cx']},{sp['cy']})")
                continue
            if step[0] == "settle":
                await c.call("emulator/run_frames", {"frames": int(step[1])})
                continue
            drv = Driver(step)
            n = drv.length()
            prev = await snap()
            t0 = prev["lt"]
            while True:
                t = prev["lt"] - t0
                if t >= n:
                    break
                if wins and win_open is None and i in wins:
                    await c.call("emulator/set_profiler", {"enabled": True, "callers": True})
                    win_open = (i, prev)
                await setheld(drv.want(t, prev["px"], prev["air"]))
                await c.call("emulator/run_frames", {"frames": 1})
                cur = await snap()
                dfc = (cur["fc"] - prev["fc"]) & 0xFFFF
                dlt = cur["lt"] - prev["lt"]
                rows.append([i, dfc, dlt, cur["lag"] - prev["lag"], cur["cx"], cur["cy"], cur["px"],
                             cur["py"], cur["xv"], cur["yv"], cur["st"], si])
                if a.cache:
                    # the fill's edges: [left, head, top, bottom, resume_col, budget, rowresume_row]
                    cw = {}
                    for nm in CACHE:
                        cw[nm] = s16(await rd(c, cs[nm], 2))
                    cache.append([i] + [cw[nm] for nm in CACHE])
                if a.dump and dlt == 1 and dfc == 1 and cur["lag"] == prev["lag"]:
                    h = hashlib.sha1()
                    for nm, ln in DUMP:
                        r = await c.call("emulator/read_memory", {"addr": hex(ds[nm]), "len": ln})
                        hx = r["bytes"]
                        h.update(bytes.fromhex((hx[2:] if hx.lower().startswith("0x") else hx)[:2 * ln]))
                    # the picture VRAM shows: Plane A over the camera window (+1 cell each
                    # side for fine scroll; wrapped 64x64), and the whole of Plane B. The
                    # snapshot sits before this tick's Camera_Update, so VRAM holds the planes
                    # the previous VBlank drew for the camera (cx, cy) read here.
                    pa = await read_vram(c, PLANE_A, PLANE_BYTES)
                    pb = await read_vram(c, PLANE_B, PLANE_BYTES)
                    win = bytearray()
                    for ry in range((cur["cy"] >> 3) - 1, ((cur["cy"] + 223) >> 3) + 2):
                        for rx in range((cur["cx"] >> 3) - 1, ((cur["cx"] + 319) >> 3) + 2):
                            o = ((ry & 63) * 64 + (rx & 63)) * 2
                            win += pa[o:o + 2]
                    e = {k: s16(await rd(c, es[k], 2)) for k in es}
                    cov = [((cur["cx"] + 327) >> 3) - e["Section_Right_Col_Written"],
                           e["Section_Left_Col_Written"] - (cur["cx"] >> 3),
                           ((cur["cy"] + 231) >> 3) - e["Section_Bottom_Row_Written"],
                           e["Section_Top_Row_Written"] - (cur["cy"] >> 3)]
                    dumps[f"{si}:{cur['lt'] - t0}"] = [cur["cx"], cur["cy"], h.hexdigest(),
                                                       hashlib.sha1(bytes(win)).hexdigest(),
                                                       hashlib.sha1(pb).hexdigest(), cov]
                if win_open and i == win_open[0] + a.win_len - 1:
                    pf = await c.call("emulator/get_profiler_frames", {"top": a.top, "topCallers": 3})
                    await c.call("emulator/set_profiler", {"enabled": False})
                    w0 = win_open[1]
                    windows.append(dict(start=win_open[0], ticks=cur["lt"] - w0["lt"],
                                        frames=(cur["fc"] - w0["fc"]) & 0xFFFF, lfc=cur["lag"] - w0["lag"],
                                        cam=[cur["cx"], cur["cy"]], player=[cur["px"], cur["py"]],
                                        profile=ERP.prof_summary(pf, cur["lt"] - w0["lt"])))
                    win_open = None
                prev = cur
                i += 1
                if i >= a.max_frames:
                    notes.append("max_frames reached")
                    break
            await setheld(set())
    head.update(notes=notes, rows=rows, cache=cache, windows=windows, dumps=dumps,
                loadavg_end=open("/proc/loadavg").read().split()[:3])
    return head


def summary(h):
    rows = h["rows"]
    fc = sum(r[1] for r in rows)
    lt = sum(r[2] for r in rows)
    lfc = sum(r[3] for r in rows)
    return fc, lt, fc - lt, lfc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--max-frames", type=int, default=20000)
    ap.add_argument("--windows", default="")
    ap.add_argument("--win-len", type=int, default=3)
    ap.add_argument("--top", type=int, default=400)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--cache", action="store_true", help="per frame, read the tile cache's fill "
                    "edges, resume slots and this tick's decode budget (CACHE)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    h = asyncio.run(main_async(a))
    Path(a.out).write_text(json.dumps(h))
    fc, lt, lag, lfc = summary(h)
    print(f"{h['rom']} crc={h['crc']} frames={fc} ticks={lt} lag={lag} LFC={lfc} notes={h['notes']} "
          f"loadavg {h['loadavg_start']} -> {h['loadavg_end']}")
    print("finished=1")


if __name__ == "__main__":
    main()
