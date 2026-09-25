#!/usr/bin/env python3
"""leg_probe — one flythrough/physics leg, per-frame lag rows, PLUS a whole-leg profile.

Perf survey 2026-09-25 (owner: "fly through things and see if you can detect any lag").
Research instrument, not a gate. It REUSES the S2CLIP-LAG study's transport and counters
(docs/research/2026-09-25-s4-lag/lag_flythrough_probe.py: Server, rd, syms, snap and its
summarise(), imported, not copied) and adds two things that study did not have:

  1. mode "spin": the physics drive with repeated spindashes (release RIGHT, hold DOWN,
     tap C SPIN_TAPS times, release DOWN, hold RIGHT) every SPIN_PERIOD frames, so the
     player spends the leg rolling at spindash speed. New leg, not in the prior study.
  2. --profile: arms the oracle exact per-invocation profiler (callers lens on, per-frame
     ring off, so the aggregate covers the WHOLE leg, not the 120-frame ring) over the
     same frames the lag rows cover, and writes the top routines with their callers.
     The server's completeness identity is CHECKED and printed; a non-zero remainder is
     printed as such, never hidden.

Lag over a window = sum(dFrame_Counter) - sum(dLogic_Tick) (the prior study's rule,
exact over a window, not per row). Headless lag counts are deterministic; the host fps
phase of the prior probe is NOT run here (wall-clock numbers belong to that study).
"""
import argparse
import asyncio
import json
import os
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-09-25-s4-lag"))
import lag_flythrough_probe as LFP  # noqa: E402
from lag_flythrough_probe import rd, syms, snap, summarise  # noqa: E402


class Server(LFP.Server):
    """The prior study's Server, but the emulator's stderr goes to a log beside --out
    (the prior one discards it, which hid a server-side refusal/crash in testing)."""
    log = None

    async def __aenter__(self):
        import subprocess
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

JUMP_PERIOD = 45
SPIN_PERIOD = 150
SPIN_TAPS = 4
FRAME_CYC = 127840


async def btn(c, names, down):
    await c.call("emulator/hold", {"buttons": names, "down": down})


async def drive(c, mode, i, dirs):
    """Per-frame input schedule. Returns nothing; issues hold/release calls."""
    if mode == "run":
        if i % JUMP_PERIOD == 0:
            await btn(c, ["c"], True)
        if i % JUMP_PERIOD == 10:
            await btn(c, ["c"], False)
    elif mode == "spin":
        k = i % SPIN_PERIOD
        if k == 0:
            await btn(c, dirs, False)
            await btn(c, ["down"], True)
        elif 4 <= k < 4 + SPIN_TAPS * 6:
            j = (k - 4) % 6
            if j == 0:
                await btn(c, ["c"], True)
            elif j == 2:
                await btn(c, ["c"], False)
        elif k == 4 + SPIN_TAPS * 6 + 2:
            await btn(c, ["down"], False)
            await btn(c, dirs, True)


async def main_async(a):
    rom, lst = str(Path(a.rom).resolve()), str(Path(a.lst).resolve())
    data = open(rom, "rb").read()
    head = dict(rom=os.path.basename(rom), crc="%08x" % zlib.crc32(data), size=len(data),
                mode=a.mode, dirs=a.dirs, frames_cap=a.frames, boot=a.boot,
                loadavg_start=open("/proc/loadavg").read().split()[:3],
                date_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    dirs = a.dirs.split(",")
    Server.log = a.out + ".server.log"
    async with Server(rom, lst, f"leg{os.getpid()}") as c:
        s = await syms(c, ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y",
                           "Camera_Target", "Lag_Frame_Count"])
        head["syms"] = {k: hex(v) for k, v in s.items()}
        # The client reads replies with asyncio readline(), whose default 64 KiB line limit
        # a whole-leg profile reply with callers exceeds; the client then drops the
        # connection ("bus connection closed"). Measured 2026-09-25 on this probe. Raise it.
        c._reader._limit = 64 * 1024 * 1024
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": a.boot})
        s0 = await snap(c, s)
        notes = []
        if a.mode in ("run", "spin"):
            y0 = s0["py"]
            await c.call("emulator/run_frames", {"frames": 8})
            y1 = (await snap(c, s))["py"]
            if y1 == y0 and "Lag_Frame_Count" in s:   # DEBUG shape: leave free flight
                await c.call("emulator/press", {"buttons": ["b"]})
                await c.call("emulator/run_frames", {"frames": 8})
                notes.append(f"DEBUG free flight left with B (y {y0}->{y1})")
            else:
                notes.append(f"no free flight to leave (y {y0}->{y1}, release shape or physics)")
            await c.call("emulator/run_frames", {"frames": 120})
        head["notes"] = notes
        await btn(c, dirs, True)
        if a.profile and not a.profile_from_switch:
            await c.call("emulator/set_profiler", {"enabled": True, "callers": True})
        rows = []
        prev = await snap(c, s)
        first = prev
        stall = 0
        switched = False
        for i in range(a.frames):
            await drive(c, a.mode, i, dirs)
            await c.call("emulator/run_frames", {"frames": 1})
            cur = await snap(c, s)
            dfc = (cur["fc"] - prev["fc"]) & 0xFFFF
            dlt = cur["lt"] - prev["lt"]
            dlag = (cur["lag"] - prev["lag"]) if cur["lag"] is not None else None
            rows.append([i, dfc, dlt, dlag, cur["cx"], cur["cy"], cur["px"], cur["py"]])
            stall = stall + 1 if (cur["cx"], cur["cy"]) == (prev["cx"], prev["cy"]) else 0
            prev = cur
            if a.then_dirs and not switched and cur["cx"] >= a.then_at_x:
                # two-phase leg: e.g. fly right along the top to Chemical Plant, then down
                await btn(c, dirs, False)
                dirs = a.then_dirs.split(",")
                await btn(c, dirs, True)
                switched = True
                if a.profile and a.profile_from_switch:
                    await c.call("emulator/set_profiler", {"enabled": True, "callers": True})
                    first = cur
                    head["rows_before_switch"] = len(rows)
                notes.append(f"switched to {a.then_dirs} at frame {i} cam ({cur['cx']},{cur['cy']})")
                stall = 0
            if a.stop_x and cur["cx"] >= a.stop_x:
                notes.append(f"reached stop_x at ({cur['cx']},{cur['cy']})")
                break
            if stall >= a.stall_stop:
                notes.append(f"camera stalled at ({cur['cx']},{cur['cy']}) for {stall} frames; stopped")
                break
        prof = None
        if a.profile:
            pf = await c.call("emulator/get_profiler_frames", {"top": a.top, "topCallers": 4})
            await c.call("emulator/set_profiler", {"enabled": False})
            items = pf["routines"]["items"]
            selfsum = sum(r["cyclesSelfTotal"] for r in items) + sum(
                pf["interrupts"][k]["cyclesSelfTotal"] for k in ("hint", "vint"))
            ticks = prev["lt"] - first["lt"]
            prof = dict(ticks=ticks, sampleCycles=pf["sampleCycles"],
                        frameCount=pf["frameCount"],
                        unattributed=pf["unattributedCycles"],
                        identity_remainder=pf["sampleCycles"] - selfsum - pf["unattributedCycles"],
                        truncated=pf["routines"]["truncated"],
                        abandoned=pf.get("abandonedFrames"), depthExceeded=pf.get("depthExceeded"),
                        interrupts=pf["interrupts"], items=items)
    head["loadavg_end"] = open("/proc/loadavg").read().split()[:3]
    return head, rows, prof


def print_prof(prof, top):
    t = max(prof["ticks"], 1)
    print(f"PROFILE: ticks {prof['ticks']} sampleCycles {prof['sampleCycles']} "
          f"= {prof['sampleCycles'] / t:.0f}/tick; identity remainder {prof['identity_remainder']} "
          f"(0 means every cycle attributed within the returned rows); truncated={prof['truncated']} "
          f"abandoned={prof['abandoned']} depthExceeded={prof['depthExceeded']}")
    vs = next((r for r in prof["items"] if r.get("name") == "VSync_Wait"), None)
    if vs:
        w = prof["sampleCycles"] - vs["cyclesTotal"]
        print(f"work (sample - VSync_Wait incl) {w / t:.0f}/tick = {w / t / FRAME_CYC:.3f} frames/tick")
    for k in ("vint", "hint"):
        b = prof["interrupts"][k]
        print(f"  interrupt {k}: incl {b['cyclesTotal'] / t:.0f}/tick self {b['cyclesSelfTotal'] / t:.0f}/tick")
    print(f"{'routine':<36} {'incl/tick':>10} {'self/tick':>10} {'calls/tick':>10}  callers(incl/tick)")
    for r in sorted(prof["items"], key=lambda r: -r["cyclesTotal"])[:top]:
        cl = ", ".join(f"{(e.get('callerName') or e.get('callerAddr') or '?')}"
                       f"{'+' + str(e['callerDisp']) if e.get('callerDisp') else ''}:{e.get('cyclesTotal', 0) / t:.0f}"
                       for e in r.get("callers", []))
        print(f"{(r.get('name') or r['addr'])[:36]:<36} {r['cyclesTotal'] / t:>10.0f} "
              f"{r['cyclesSelfTotal'] / t:>10.0f} {r['callsTotal'] / t:>10.2f}  {cl}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--mode", choices=("fly", "run", "spin"), default="fly")
    ap.add_argument("--frames", type=int, default=2000)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--stop-x", type=int, default=0)
    ap.add_argument("--stall-stop", type=int, default=60)
    ap.add_argument("--dirs", default="right")
    ap.add_argument("--then-dirs", default="", help="second-phase held buttons")
    ap.add_argument("--then-at-x", type=int, default=0, help="switch when camera x >= this")
    ap.add_argument("--profile-from-switch", action="store_true",
                    help="(with --then-dirs) arm the profiler at the switch, not at leg start")
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--top", type=int, default=512)
    ap.add_argument("--print-top", type=int, default=30)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    head, rows, prof = asyncio.run(main_async(a))
    head["summary"] = summarise(head, rows)
    head["rows"] = rows
    head["profile"] = prof
    Path(a.out).write_text(json.dumps(head))
    sm = head["summary"]
    m = sm["motion"]
    print(f"{head['rom']} crc={head['crc']} size={head['size']} mode={a.mode} dirs={a.dirs} "
          f"notes={head['notes']}")
    print(f"IN MOTION: {m['video_frames']} video frames, {m['ticks']} ticks, lag {m['lag']} "
          f"({m['lag_pct']}%), {m['frames_per_tick']} frames/tick, cam end {m['cam_end']}")
    print(f"WHOLE: stepped={sm['frames_stepped']} lag={sm['lag_frames']} "
          f"LFC_delta={sm.get('Lag_Frame_Count_delta')} loadavg {head['loadavg_start']} -> "
          f"{head['loadavg_end']}")
    print("by cam_y/512: " + " ".join(f"{k}:{v['video_frames']}/{v['lag']}"
                                       for k, v in sm["by_camy512"].items()))
    print("by cam_x/512: " + " ".join(f"{k}:{v['video_frames']}/{v['lag']}"
                                       for k, v in sm["by_camx512"].items()))
    if prof:
        print_prof(prof, a.print_top)
    print("finished=1")


if __name__ == "__main__":
    main()
