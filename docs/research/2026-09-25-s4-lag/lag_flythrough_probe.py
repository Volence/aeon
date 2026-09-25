#!/usr/bin/env python3
"""lag_flythrough_probe — per-frame GAME-SIDE lag and HOST-SIDE speed for one ROM, in motion.

Research parcel 2026-09-25 (owner: "s4 is now super laggy"). Not a gate; a measurement.

GAME-SIDE. The engine counts two things in every shape:
  Frame_Counter (u16)  +1 per VBlank, on BOTH the VInt_Level and the VInt_Lag path
  Logic_Tick    (u32)  +1 per completed game-loop tick (post-VSync)
So over one video frame dLT is 1 on a made frame and 0 on a lag frame (VInt_Lag ran
because the main loop had not reached VSync_Wait). The DEBUG shape also keeps
Lag_Frame_Count (+1 in VInt_Lag), read here as an independent second witness.
The probe steps ONE video frame per run_frames(1) and reads all counters after each, so
every lag frame is attributed to the camera position at which it happened.

HOST-SIDE. A separate phase times run_frames(N) in one call on the headless core with
--no-pace (so it runs as fast as the host allows), in motion, and prints frames/s. The
GUI player does more per frame than this (render + present + bus), so headless fps is an
UPPER bound on what the player can do on this box.

Modes:
  fly     DEBUG shapes: stay in debug free flight (16 px/tick) and hold RIGHT.
  run     leave free flight with B if present (DEBUG), then hold RIGHT and tap C every
          JUMP_PERIOD frames (physics play).
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

TOOLS = Path(__file__).resolve().parents[3] / "tools"
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path, suite_path  # noqa: E402
add_client_path()
from aether import BusClient  # noqa: E402

SERVER = str(suite_path("oracle", "target", "release", "oracle-aether"))
SST_X_POS, SST_Y_POS = 0x02, 0x06
JUMP_PERIOD = 45


class Server:
    def __init__(self, rom, lst, tag):
        self.rom, self.lst = rom, lst
        self.sock = f"/tmp/aeon_lagprobe_{os.getpid()}_{tag}.sock"
        self.proc = self.client = None

    async def __aenter__(self):
        if os.path.exists(self.sock):
            os.unlink(self.sock)
        argv = [SERVER, self.rom, "--socket", self.sock, "--no-pace", "--symbols", self.lst]
        self.proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(400):
            if os.path.exists(self.sock):
                break
            time.sleep(0.05)
        else:
            raise SystemExit(f"oracle-aether never created {self.sock}")
        self.client = BusClient(self.sock, client_id="lagprobe", client_name="lag_flythrough_probe")
        await self.client.connect()
        return self.client

    async def __aexit__(self, *exc):
        try:
            if self.client:
                await self.client.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
            if os.path.exists(self.sock):
                os.unlink(self.sock)


async def rd(c, addr, n):
    r = await c.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    b = r["bytes"]
    b = b[2:] if b.lower().startswith("0x") else b
    return int(b[:n * 2], 16)


async def syms(c, names):
    out = {}
    for n in names:
        try:
            r = await c.call("emulator/lookup_symbol", {"name": n})
            out[n] = int(r["addr"], 16) & 0xFFFFFF
        except Exception:
            pass
    return out


async def snap(c, s):
    fc = await rd(c, s["Frame_Counter"], 2)
    lt = await rd(c, s["Logic_Tick"], 4)
    cx = (await rd(c, s["Camera_X"], 4)) >> 16
    cy = (await rd(c, s["Camera_Y"], 4)) >> 16
    lag = await rd(c, s["Lag_Frame_Count"], 4) if "Lag_Frame_Count" in s else None
    tgt = await rd(c, s["Camera_Target"], 2)
    leader = 0xFF0000 | tgt if tgt & 0x8000 else tgt
    px = (await rd(c, leader + SST_X_POS, 4)) >> 16 if leader else 0
    py = (await rd(c, leader + SST_Y_POS, 4)) >> 16 if leader else 0
    return dict(fc=fc, lt=lt, cx=cx, cy=cy, lag=lag, px=px, py=py)


def uptime():
    return open("/proc/loadavg").read().split()[:3]


async def main_async(a):
    rom, lst = str(Path(a.rom).resolve()), str(Path(a.lst).resolve())
    data = open(rom, "rb").read()
    head = dict(rom=os.path.basename(rom), crc="%08x" % zlib.crc32(data), size=len(data),
                mode=a.mode, dirs=a.dirs, frames_cap=a.frames, boot=a.boot, server=SERVER)
    async with Server(rom, lst, a.mode) as c:
        s = await syms(c, ["Frame_Counter", "Logic_Tick", "Camera_X", "Camera_Y",
                           "Camera_Target", "Lag_Frame_Count"])
        head["syms"] = {k: hex(v) for k, v in s.items()}
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": a.boot})
        s0 = await snap(c, s)
        head["after_boot"] = s0
        notes = []
        if a.mode == "run":
            # leave free flight if we are in it: a frozen y over 8 frames = debug-fly
            y0 = s0["py"]
            await c.call("emulator/run_frames", {"frames": 8})
            y1 = (await snap(c, s))["py"]
            if y1 == y0:
                await c.call("emulator/press", {"buttons": ["b"]})
                await c.call("emulator/run_frames", {"frames": 8})
                y2 = (await snap(c, s))["py"]
                notes.append(f"free flight detected (y {y0}->{y1}); pressed B; y -> {y2}")
            else:
                notes.append(f"already physics (y {y0}->{y1})")
            await c.call("emulator/run_frames", {"frames": 120})
        head["notes"] = notes
        await c.call("emulator/hold", {"buttons": a.dirs.split(","), "down": True})
        rows = []
        prev = await snap(c, s)
        t0 = time.monotonic()
        stall = 0
        for i in range(a.frames):
            if a.mode == "run" and i % JUMP_PERIOD == 0:
                await c.call("emulator/hold", {"buttons": ["c"], "down": True})
            if a.mode == "run" and i % JUMP_PERIOD == 10:
                await c.call("emulator/hold", {"buttons": ["c"], "down": False})
            await c.call("emulator/run_frames", {"frames": 1})
            cur = await snap(c, s)
            dfc = (cur["fc"] - prev["fc"]) & 0xFFFF
            dlt = cur["lt"] - prev["lt"]
            dlag = (cur["lag"] - prev["lag"]) if cur["lag"] is not None else None
            rows.append([i, dfc, dlt, dlag, cur["cx"], cur["cy"], cur["px"], cur["py"]])
            stall = stall + 1 if (cur["cx"], cur["cy"]) == (prev["cx"], prev["cy"]) else 0
            prev = cur
            if a.stop_x and cur["cx"] >= a.stop_x:
                break
            if stall >= a.stall_stop:
                notes.append(f"camera stalled at ({cur['cx']},{cur['cy']}) for {stall} frames; stopped")
                break
        head["stepped_wall_s"] = round(time.monotonic() - t0, 3)
        # ---- host-side: one bulk run in motion, no per-frame reads ----
        la0 = uptime()
        await c.call("emulator/reset", {})
        await c.call("emulator/run_frames", {"frames": a.boot})
        await c.call("emulator/hold", {"buttons": a.dirs.split(","), "down": True})
        t1 = time.monotonic()
        await c.call("emulator/run_frames", {"frames": a.host_frames})
        dt = time.monotonic() - t1
        la1 = uptime()
        endsnap = await snap(c, s)
        head["host"] = dict(frames=a.host_frames, wall_s=round(dt, 3),
                            fps=round(a.host_frames / dt, 1), loadavg_before=la0,
                            loadavg_after=la1, cam_end=(endsnap["cx"], endsnap["cy"]),
                            date_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return head, rows


def summarise(head, rows):
    """Lag frames over a window = sum(dFrame_Counter) - sum(dLogic_Tick): exact over any
    window. A single row's dLogic_Tick is NOT (run_frames stops at a fixed cycle, not at
    VBlank, so a late tick shows as 0 then 2 across two rows); buckets therefore sum."""
    n = len(rows)
    sfc = sum(r[1] for r in rows)
    slt = sum(r[2] for r in rows)
    out = dict(frames_stepped=n, sum_dFrame_Counter=sfc, sum_dLogic_Tick=slt,
               lag_frames=sfc - slt,
               lag_pct=round(100.0 * (sfc - slt) / sfc, 2) if sfc else None,
               cam_x_start=rows[0][4] if rows else None, cam_x_end=rows[-1][4] if rows else None,
               cam_x_max=max(r[4] for r in rows) if rows else None)
    if rows and rows[0][3] is not None:
        out["Lag_Frame_Count_delta"] = sum(r[3] for r in rows)
    buckets = {}
    for r in rows:
        b = (r[4] // 512) * 512
        e = buckets.setdefault(b, [0, 0, 0])
        e[0] += r[1]
        e[1] += r[2]
        e[2] += r[3] or 0
    out["by_camx512"] = {str(k): {"video_frames": v[0], "lag": v[0] - v[1], "LFC": v[2]}
                         for k, v in sorted(buckets.items())}
    ybk = {}
    for r in rows:
        b = (r[5] // 512) * 512
        e = ybk.setdefault(b, [0, 0])
        e[0] += r[1]
        e[1] += r[2]
    out["by_camy512"] = {str(k): {"video_frames": v[0], "lag": v[0] - v[1]}
                         for k, v in sorted(ybk.items())}
    # IN MOTION: rows up to and including the last frame the camera moved (drops the
    # trailing at-rest stall the stop rule waits through).
    last = max((i for i in range(1, n) if rows[i][4:6] != rows[i - 1][4:6]), default=n - 1)
    mv = rows[:last + 1]
    mfc = sum(r[1] for r in mv)
    mlt = sum(r[2] for r in mv)
    out["motion"] = dict(video_frames=mfc, ticks=mlt, lag=mfc - mlt,
                         lag_pct=round(100.0 * (mfc - mlt) / mfc, 2) if mfc else None,
                         frames_per_tick=round(mfc / mlt, 3) if mlt else None,
                         cam_end=rows[last][4:6])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--mode", choices=("fly", "run"), default="fly")
    ap.add_argument("--frames", type=int, default=1500)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--stop-x", type=int, default=0)
    ap.add_argument("--stall-stop", type=int, default=240)
    ap.add_argument("--host-frames", type=int, default=1800)
    ap.add_argument("--dirs", default="right", help="comma list of held d-pad buttons")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    head, rows = asyncio.run(main_async(a))
    head["summary"] = summarise(head, rows)
    head["rows_cols"] = ["i", "dFrame_Counter", "dLogic_Tick", "dLag_Frame_Count",
                         "cam_x", "cam_y", "player_x", "player_y"]
    head["rows"] = rows
    Path(a.out).write_text(json.dumps(head))
    print(json.dumps({k: v for k, v in head.items() if k != "rows"}, indent=1))
    print("finished=1")


if __name__ == "__main__":
    main()
