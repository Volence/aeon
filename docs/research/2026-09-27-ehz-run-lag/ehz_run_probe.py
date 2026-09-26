#!/usr/bin/env python3
"""ehz_run_probe — the owner's EHZ complaint as a leg: RUN (not fly) right from spawn to the tunnel.

2026-09-27, perf/ehz-run-lag. Research instrument, not a gate. Reuses the S2CLIP-LAG study's
transport and counters (docs/research/2026-09-25-s4-lag/lag_flythrough_probe.py: rd, syms,
snap, summarise), imported, not copied.

WHAT IS NEW HERE, AND WHY: the perf survey's physics legs scheduled inputs per VIDEO frame, so
a ROM with different lag took a different path and cross-ROM comparison was void. This probe
keys every input change to LOGIC TICKS since the leg started (read after each video frame), so
the input the game sees on tick t is a function of t alone. Holding one input for many ticks is
then independent of where the lag frames fall. The probe records (tick, player x/y, camera x/y)
per tick (the JSON's `path`) so two ROMs' paths can be compared tick by tick; a path that differs
is reported, never assumed away.

Modes (all hold RIGHT):
  hold   right only, no jumps.
  auto   right; C for --jump-hold ticks whenever the player's x first reaches a --triggers x
         (the clip carries no objects, so Emerald Hill's bridges are gaps to jump), or has not
         grown for --stuck ticks (a wall). The decision reads the player's x once per tick,
         so it is a function of the tick-indexed path; the path compare says whether it held.
  autospin  auto, but the stuck response is a spindash (down, C x4, release), and the leg
         opens with one.
  spinrun   auto (jumps), opening with one spindash from spawn.
  run    right, C held for ticks [0,10) of every JUMP ticks.
  spin   every SPIN ticks: release right, hold down, tap C x4, release down, hold right.

Segments: the profiler (callers lens) is re-armed every --seg px of CAMERA x (arming resets it),
so each segment gets its own per-tick routine table alongside its lag. Lag over any window is
sum(dFrame_Counter) - sum(dLogic_Tick), exact over a window (the prior study's rule).

The socket goes under $HOME, not /tmp (the /tmp quota rule of this parcel).
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-09-25-s4-lag"))
import lag_flythrough_probe as LFP  # noqa: E402
from lag_flythrough_probe import rd, syms, snap, summarise  # noqa: E402

FRAME_CYC = 127840
SOCK_DIR = Path(os.environ.get("RUNPROBE_SOCK_DIR", str(Path.home() / "ehzlag" / "sock")))


class Server(LFP.Server):
    def __init__(self, rom, lst, tag, log):
        super().__init__(rom, lst, tag)
        SOCK_DIR.mkdir(parents=True, exist_ok=True)
        self.sock = str(SOCK_DIR / f"rp{os.getpid()}_{tag}.sock")
        self.log = log

    async def __aenter__(self):
        real = subprocess.Popen
        logf = open(self.log, "w")

        def popen(argv, **kw):
            kw["stdout"] = logf
            kw["stderr"] = subprocess.STDOUT
            return real(argv, **kw)
        subprocess.Popen = popen
        try:
            return await super().__aenter__()
        finally:
            subprocess.Popen = real


class Auto:
    """State for the reactive modes; fed one (tick, px) per logic tick."""
    def __init__(self, a, spin):
        self.a, self.spin = a, spin
        self.trig = sorted(int(x) for x in a.triggers.split(",") if x)
        self.spin_trig = sorted(int(x) for x in a.spin_triggers.split(",") if x)
        self.fired = set()
        self.until = -1          # C held while t < until
        self.spin_at = 0 if (spin or a.mode == "spinrun") else None
        self.best, self.best_t = -1, 0
        self.last_t = -1

    def want(self, t, px, air=False):
        a = self.a
        if t != self.last_t:
            self.last_t = t
            if px > self.best:
                self.best, self.best_t = px, t
            for x in self.trig:
                if x not in self.fired and px >= x and not air:
                    self.fired.add(x)
                    if t >= self.until:
                        self.until = t + a.jump_hold
            for x in self.spin_trig:
                if x not in self.fired and px >= x and not air and t >= self.until:
                    self.fired.add(x)
                    self.spin_at = t
            if t - self.best_t >= a.stuck and t >= self.until and not air and (
                    self.spin_at is None or t - self.spin_at >= 40):
                self.best_t = t
                if self.spin:
                    self.spin_at = t
                else:
                    self.until = t + a.jump_hold
        if self.spin_at is not None:
            k = t - self.spin_at
            if k < 4:
                return {"down"}
            if k < 4 + 4 * 6:
                return {"down", "c"} if ((k - 4) % 6) < 2 else {"down"}
            if k < 4 + 4 * 6 + 2:
                return {"down"}
        return {"right", "c"} if t < self.until else {"right"}


def want(mode, t, a):
    """The held set for tick t since the leg started (a pure function of t)."""
    if mode == "hold":
        return {"right"}
    if mode == "fly":
        return set(a.dirs.split(","))
    if mode == "run":
        return {"right", "c"} if (t % a.jump) < 10 else {"right"}
    if mode == "spin":
        k = t % a.spin
        if k < 4:
            return {"down"}
        if k < 4 + 4 * 6:
            return {"down", "c"} if ((k - 4) % 6) < 2 else {"down"}
        if k < 4 + 4 * 6 + 2:
            return {"down"}
        return {"right"}
    raise SystemExit(mode)


# --dump: the parallax pass's whole output. Hscroll_Buffer is the per-line HScroll table the
# VBlank DMAs to VRAM (224 lines x FG/BG words); Parallax_Vscroll_Column_Buf is the per-column
# VSRAM image Vscroll_Write copies; Vscroll_Factor is the whole-plane VSRAM pair it writes when
# the scene has no column table (engine/ram.emp, engine/level/parallax.emp Vscroll_Write).
DUMP = [("Hscroll_Buffer", 896), ("Parallax_Vscroll_Column_Buf", 80), ("Vscroll_Factor", 4)]
SST_STATUS, ST_IN_AIR = 0x1E, 3   # engine/objects/sst.emp, engine/system/constants.emp


async def in_air(c, s):
    tgt = await rd(c, s["Camera_Target"], 2)
    leader = 0xFF0000 | tgt if tgt & 0x8000 else tgt
    return bool(leader) and bool((await rd(c, leader + SST_STATUS, 1)) >> ST_IN_AIR & 1)


def prof_summary(pf, ticks):
    items = pf["routines"]["items"]
    selfsum = sum(r["cyclesSelfTotal"] for r in items) + sum(
        pf["interrupts"][k]["cyclesSelfTotal"] for k in ("hint", "vint"))
    return dict(ticks=ticks, sampleCycles=pf["sampleCycles"], frameCount=pf["frameCount"],
                unattributed=pf["unattributedCycles"],
                identity_remainder=pf["sampleCycles"] - selfsum - pf["unattributedCycles"],
                truncated=pf["routines"]["truncated"], interrupts=pf["interrupts"], items=items)


async def main_async(a):
    rom, lst = str(Path(a.rom).resolve()), str(Path(a.lst).resolve())
    data = open(rom, "rb").read()
    head = dict(rom=os.path.basename(rom), crc="%08x" % zlib.crc32(data), size=len(data),
                mode=a.mode, frames_cap=a.frames, boot=a.boot, seg=a.seg,
                loadavg_start=open("/proc/loadavg").read().split()[:3],
                date_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    async with Server(rom, lst, a.mode, a.out + ".server.log") as c:
        s = await syms(c, ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y",
                           "Camera_Target", "Lag_Frame_Count"])
        c._reader._limit = 64 * 1024 * 1024   # whole-segment profile replies exceed 64 KiB
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": a.boot})
        notes = []
        s0 = await snap(c, s)
        await c.call("emulator/run_frames", {"frames": 8})
        s1 = await snap(c, s)
        if "Lag_Frame_Count" in s and a.mode != "fly":
            # DEBUG shape: it boots in free flight. B leaves it (the brief: press B first).
            await c.call("emulator/press", {"buttons": ["b"]})
            await c.call("emulator/run_frames", {"frames": 8})
            notes.append(f"DEBUG: pressed B to leave free flight (py {s0['py']}->{s1['py']})")
        if a.warp:
            # DEBUG shape only: the supported warp mailbox (Debug_Warp_Consume re-runs the boot
            # ladder; tools/clip_music_witness.py places the same way). A bare Camera_X poke
            # trips EntityWindow_Slide's step assert in DEBUG since 7c7ccf96.
            ws = await syms(c, ["Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag"])
            if len(ws) != 3:
                raise SystemExit("--warp needs the DEBUG shape's warp mailbox; this ROM has none")
            wx, wy = (int(v) for v in a.warp.split(","))
            await c.call("emulator/write_memory", {"addr": hex(ws["Warp_Req_X"]), "bytes": "0x%04x" % wx})
            await c.call("emulator/write_memory", {"addr": hex(ws["Warp_Req_Y"]), "bytes": "0x%04x" % wy})
            await c.call("emulator/write_memory", {"addr": hex(ws["Warp_Req_Flag"]), "bytes": "0x01"})
            for _ in range(120):
                await c.call("emulator/run_frames", {"frames": 1})
                if await rd(c, ws["Warp_Req_Flag"], 1) == 0:
                    break
            else:
                raise SystemExit("the warp mailbox was never acknowledged")
            notes.append(f"warped to ({wx},{wy})")
        await c.call("emulator/run_frames", {"frames": 120})
        s2 = await snap(c, s)
        await c.call("emulator/run_frames", {"frames": 8})
        s3 = await snap(c, s)
        notes.append(f"settle: player ({s2['px']},{s2['py']}) -> ({s3['px']},{s3['py']}) over 8 frames")
        cs = await syms(c, ["Section_Right_Col_Written", "Section_Left_Col_Written",
                            "Section_Bottom_Row_Written", "Section_Top_Row_Written"]) if a.coverage else {}
        if a.coverage and len(cs) != 4:
            raise SystemExit(f"--coverage: the streamer's edge words did not all resolve: {sorted(cs)}")
        cov = []
        ds = await syms(c, [nm for nm, _ in DUMP]) if a.dump else {}
        if a.dump and len(ds) != len(DUMP):
            raise SystemExit(f"--dump: not every buffer resolved: {sorted(ds)}")
        dumps = {}
        held = set()
        auto = Auto(a, a.mode == "autospin") if a.mode in ("auto", "autospin", "spinrun") else None
        prev = await snap(c, s)
        t0 = prev["lt"]
        rows, segs, path = [], [], {}
        seg_lo = (prev["cx"] // a.seg) * a.seg
        seg_first = prev
        if a.profile:
            await c.call("emulator/set_profiler", {"enabled": True, "callers": True})
        stall = 0
        wins = sorted(set(int(x) for x in a.windows.split(",") if x)) if a.windows else []
        win_open, windows = None, []
        for i in range(a.frames):
            if wins and win_open is None and i in wins:
                await c.call("emulator/set_profiler", {"enabled": True, "callers": True})
                win_open = (i, prev)
            t = prev["lt"] - t0
            w = auto.want(t, prev["px"], await in_air(c, s)) if auto else want(a.mode, t, a)
            up, down = sorted(held - w), sorted(w - held)
            if up:
                await c.call("emulator/hold", {"buttons": up, "down": False})
            if down:
                await c.call("emulator/hold", {"buttons": down, "down": True})
            held = w
            await c.call("emulator/run_frames", {"frames": 1})
            cur = await snap(c, s)
            dfc = (cur["fc"] - prev["fc"]) & 0xFFFF
            dlt = cur["lt"] - prev["lt"]
            dlag = (cur["lag"] - prev["lag"]) if cur["lag"] is not None else None
            rows.append([i, dfc, dlt, dlag, cur["cx"], cur["cy"], cur["px"], cur["py"]])
            if a.dump and dlt == 1 and dfc == 1 and (dlag in (None, 0)):
                # a frame that ended one on-time tick: the parallax pass for that tick has
                # finished (it runs inside the tick, before VSync_Wait), so the buffers are
                # whole. Keyed by the tick index since the leg started, which is the same
                # camera on both ROMs when the tick-indexed paths agree.
                blob = b""
                for nm, n in DUMP:
                    r = await c.call("emulator/read_memory", {"addr": hex(ds[nm]), "len": n})
                    hx = r["bytes"]
                    hx = hx[2:] if hx.lower().startswith("0x") else hx
                    blob += bytes.fromhex(hx[:2 * n])
                dumps[cur["lt"] - t0] = [cur["cx"], cur["cy"], blob.hex()]
            if a.coverage:
                e = {k: await rd(c, cs[k], 2) for k in cs}
                sgn = lambda v: v - 0x10000 if v & 0x8000 else v
                # deficits: visible cells the streamer has NOT drawn (> 0 is a hole on screen).
                # Visible cols camX>>3 .. (camX+SECTION_H_REACH_PX)>>3, rows camY>>3 .. (camY+
                # SECTION_V_REACH_PX)>>3 (engine/system/constants.emp, section.emp's own reach).
                cov.append([i,
                            ((cur["cx"] + 327) >> 3) - sgn(e["Section_Right_Col_Written"]),
                            sgn(e["Section_Left_Col_Written"]) - (cur["cx"] >> 3),
                            ((cur["cy"] + 231) >> 3) - sgn(e["Section_Bottom_Row_Written"]),
                            sgn(e["Section_Top_Row_Written"]) - (cur["cy"] >> 3)])
            if dlt:
                path[cur["lt"] - t0] = [cur["px"], cur["py"], cur["cx"], cur["cy"]]
            stall = stall + 1 if (cur["px"], cur["py"]) == (prev["px"], prev["py"]) else 0
            prev = cur
            seg_now = (cur["cx"] // a.seg) * a.seg
            end = cur["px"] >= a.stop_x or stall >= a.stall_stop or i == a.frames - 1
            if win_open and i == win_open[0] + a.win_len - 1:
                pf = await c.call("emulator/get_profiler_frames", {"top": a.top, "topCallers": 3})
                await c.call("emulator/set_profiler", {"enabled": False})
                w0 = win_open[1]
                wt = cur["lt"] - w0["lt"]
                windows.append(dict(start=win_open[0], ticks=wt,
                                    frames=(cur["fc"] - w0["fc"]) & 0xFFFF,
                                    lfc=(cur["lag"] - w0["lag"]) if cur["lag"] is not None else None,
                                    cam=[cur["cx"], cur["cy"]], player=[cur["px"], cur["py"]],
                                    profile=prof_summary(pf, wt)))
                win_open = None
            if seg_now != seg_lo or end:
                seg = dict(cx_lo=seg_lo, ticks=cur["lt"] - seg_first["lt"],
                           frames=(cur["fc"] - seg_first["fc"]) & 0xFFFF)
                seg["lag"] = seg["frames"] - seg["ticks"]
                if a.profile:
                    pf = await c.call("emulator/get_profiler_frames", {"top": a.top, "topCallers": 4})
                    seg["profile"] = prof_summary(pf, seg["ticks"])
                    await c.call("emulator/set_profiler", {"enabled": True, "callers": True})
                segs.append(seg)
                seg_lo, seg_first = seg_now, cur
            if cur["px"] >= a.stop_x:
                notes.append(f"reached stop_x: player ({cur['px']},{cur['py']}) at frame {i}")
                break
            if stall >= a.stall_stop:
                notes.append(f"player stalled at ({cur['px']},{cur['py']}) for {stall} frames; stopped")
                break
        if a.profile:
            await c.call("emulator/set_profiler", {"enabled": False})
    head["notes"] = notes
    head["loadavg_end"] = open("/proc/loadavg").read().split()[:3]
    head["windows"] = windows
    head["coverage"] = cov
    head["dumps"] = dumps
    return head, rows, segs, path


def top_table(prof, n):
    t = max(prof["ticks"], 1)
    out = []
    for r in sorted(prof["items"], key=lambda r: -r["cyclesTotal"])[:n]:
        cl = ", ".join(f"{(e.get('callerName') or e.get('callerAddr') or '?')}:"
                       f"{e.get('cyclesTotal', 0) / t:.0f}" for e in r.get("callers", []))
        out.append(f"  {(r.get('name') or r['addr'])[:36]:<36} {r['cyclesTotal'] / t:>9.0f} "
                   f"{r['cyclesSelfTotal'] / t:>9.0f} {r['callsTotal'] / t:>7.2f}  {cl}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--mode", choices=("hold", "run", "spin", "auto", "autospin", "spinrun", "fly"), default="run")
    ap.add_argument("--frames", type=int, default=4000)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--stop-x", type=int, default=10900, help="player x that ends the leg (EHZ's "
                    "region rows end at 10975, the tunnel starts there)")
    ap.add_argument("--stall-stop", type=int, default=240)
    ap.add_argument("--jump", type=int, default=45)
    ap.add_argument("--spin", type=int, default=150)
    ap.add_argument("--triggers", default="1290,4700,5900,8010,8330,9420",
                    help="player x values that fire one jump each (Emerald Hill act 1's bridge "
                    "gaps, from s2disasm level/objects/EHZ_1.bin object $11, less a run-up)")
    ap.add_argument("--spin-triggers", default="",
                    help="player x values that fire one spindash each (grounded), in auto modes")
    ap.add_argument("--warp", default="", help="X,Y (feet): DEBUG shape only, place the player "
                    "through the warp mailbox before the leg")
    ap.add_argument("--dirs", default="right", help="fly mode: held directions (DEBUG free flight)")
    ap.add_argument("--coverage", action="store_true", help="per frame, read the plane streamer's "
                    "four written edges and report how many VISIBLE tile columns/rows were not drawn")
    ap.add_argument("--dump", action="store_true", help="on every frame that ends one on-time "
                    "tick, record the parallax output buffers keyed by tick (see DUMP)")
    ap.add_argument("--jump-hold", type=int, default=16)
    ap.add_argument("--stuck", type=int, default=12)
    ap.add_argument("--seg", type=int, default=1024)
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--windows", default="", help="comma list of frame indices: arm the profiler "
                    "before each and read it --win-len frames later (lag-frame attribution; a "
                    "deterministic re-run of a leg whose lag rows are known). Not with --profile")
    ap.add_argument("--win-len", type=int, default=3)
    ap.add_argument("--top", type=int, default=400)
    ap.add_argument("--print-top", type=int, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.profile and a.windows:
        raise SystemExit("--profile and --windows both arm the one profiler; pick one")
    head, rows, segs, path = asyncio.run(main_async(a))
    head["summary"] = summarise(head, rows)
    head["rows"], head["segs"], head["path"] = rows, segs, path
    Path(a.out).write_text(json.dumps(head))
    sm = head["summary"]
    m = sm["motion"]
    print(f"{head['rom']} crc={head['crc']} size={head['size']} mode={a.mode} notes={head['notes']}")
    print(f"IN MOTION: {m['video_frames']} video frames, {m['ticks']} ticks, lag {m['lag']} "
          f"({m['lag_pct']}%), cam end {m['cam_end']}; WHOLE lag={sm['lag_frames']} "
          f"LFC_delta={sm.get('Lag_Frame_Count_delta')} loadavg {head['loadavg_start']} -> {head['loadavg_end']}")
    for g in segs:
        line = f"seg cx {g['cx_lo']:>6}: frames {g['frames']:>4} ticks {g['ticks']:>4} lag {g['lag']:>3}"
        if "profile" in g:
            p = g["profile"]
            t = max(p["ticks"], 1)
            vs = next((r for r in p["items"] if r.get("name") == "VSync_Wait"), None)
            work = (p["sampleCycles"] - (vs["cyclesTotal"] if vs else 0)) / t
            line += (f"  work {work:>7.0f}/tick ({work / FRAME_CYC:.3f} fr) idrem {p['identity_remainder']}"
                     f" trunc {p['truncated']}")
        print(line)
        if "profile" in g and a.print_top:
            print("\n".join(top_table(g["profile"], a.print_top)))
    if head.get("coverage"):
        cv = head["coverage"]
        mx = [max(r[k] for r in cv) for k in (1, 2, 3, 4)]
        bad = sum(1 for r in cv if max(r[1:]) > 0)
        print(f"COVERAGE over {len(cv)} frames: max undrawn visible right/left/bottom/top = {mx}; "
              f"frames with any undrawn visible cell: {bad}")
    print("finished=1")


if __name__ == "__main__":
    main()
