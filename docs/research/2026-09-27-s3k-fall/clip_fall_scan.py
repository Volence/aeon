#!/usr/bin/env python3
"""clip_fall_scan — find the longest falls a DEBUG ROM's act offers, by dropping the player from
the top edge at a sweep of X and recording where he lands.

usage: clip_fall_scan.py ROM LST [--x0 N --x1 N --dx N --y N]

Placement through the DEBUG warp mailbox (after a B press leaves free flight), then no input
until he is grounded or 600 frames pass. Per X: landing y, fall distance, peak y_vel, frames.
Used to pick the S2 clip's fall legs (docs/research/2026-09-27-s3k-fall.md); the clip carries
Sonic 2's collision everywhere, unlike OJZ act 1 whose sections 1-8 are empty.
"""
import argparse
import asyncio
import pathlib
import re
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[3] / "tools"
sys.path.insert(0, str(TOOLS))
from suite_paths import add_client_path          # noqa: E402
add_client_path()
from aether_instance import aether_emulator      # noqa: E402
from aether import BusClient                     # noqa: E402


def lst(path):
    syms, equs = {}, {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = re.match(r"^ ([A-Za-z_$][\w$.]*) : ([0-9A-Fa-f]+) [A-Z] \|", line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
        m = re.match(r"^EQU ([A-Za-z_]\w*) = \$([0-9A-Fa-f]+)\s*$", line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    return syms, equs


async def run(sock, syms, equs, xs, y0):
    c = BusClient(socket_path=sock, client_id="cfs", client_name="clip-fall-scan")
    await c.connect()

    async def rd(a, n):
        r = await c.call("emulator/read_memory", {"addr": hex(a & 0xFFFFFF), "len": n})
        s = r["bytes"]
        return bytes.fromhex(s[2:] if s[:2].lower() == "0x" else s)

    async def wr(a, h):
        await c.call("emulator/write_memory", {"addr": hex(a & 0xFFFFFF), "bytes": "0x" + h})

    await c.call("emulator/reset", {})
    await c.call("emulator/run_frames", {"frames": 300})
    await c.call("emulator/press", {"buttons": ["b"]})
    await c.call("emulator/run_frames", {"frames": 8})
    P = syms["Player_1"]
    out = []
    for x in xs:
        await wr(syms["Warp_Req_X"], "%04x%04x01" % (x, y0))
        for _ in range(120):
            await c.call("emulator/run_frames", {"frames": 1})
            if not (await rd(syms["Warp_Req_Flag"], 1))[0]:
                break
        s = await rd(P, 0x40)
        ys = int.from_bytes(s[equs["SST_y_pos"]:equs["SST_y_pos"] + 2], "big")
        peak, f = 0, 0
        while f < 600:
            await c.call("emulator/run_frames", {"frames": 1})
            f += 1
            s = await rd(P, 0x40)
            yv = int.from_bytes(s[equs["SST_y_vel"]:equs["SST_y_vel"] + 2], "big", signed=True)
            peak = max(peak, yv)
            if s[equs["_pl_state"]] in (equs["PSTATE_GROUND"], equs["PSTATE_ROLL"]) and f > 2:
                break
        y = int.from_bytes(s[equs["SST_y_pos"]:equs["SST_y_pos"] + 2], "big")
        out.append((x, ys, y, y - ys, peak, f))
        print("x %5d start %5d land %5d fall %5d peak y_vel %5.1f frames %3d" % (
            x, ys, y, y - ys, peak / 256, f), flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("lst")
    ap.add_argument("--x0", type=int, default=160)
    ap.add_argument("--x1", type=int, default=15900)
    ap.add_argument("--dx", type=int, default=128)
    ap.add_argument("--y", type=int, default=64)
    a = ap.parse_args()
    syms, equs = lst(a.lst)
    with aether_emulator(a.rom, symbols=a.lst) as sock:
        res = asyncio.run(run(sock, syms, equs, range(a.x0, a.x1, a.dx), a.y))
    res.sort(key=lambda r: -r[3])
    print("longest:", res[:8])
    print("finished=1")


if __name__ == "__main__":
    main()
