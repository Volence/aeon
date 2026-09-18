#!/usr/bin/env python3
"""Companion to pcc_identity_probe: the SAME three cells, read under fg_left_edge_gate's
own lab install, using that gate's own drive_cursor. Discriminates "staged into Target and
not yet promoted" from "never staged at all". Reports; asserts nothing."""
import asyncio, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from suite_paths import add_client_path
add_client_path()
from aether import BusClient
from aether_instance import AetherInstance
import fg_left_edge_gate as G

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def lst_syms(path):
    s = {}
    for line in open(path, errors="replace"):
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([0-9A-Fa-f]+)\s+C\s*\|', line)
        if m: s[m.group(1)] = int(m.group(2), 16)
    return s

async def rd(b, addr, n):
    r = await b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    return int(r["bytes"].upper().removeprefix("0X"), 16)

async def body(sock, syms, cfgs, scenes):
    b = BusClient(sock); await b.connect()
    async def snap(tag):
        cur = await rd(b, syms["Parallax_Current_Config"], 4) & 0xFFFFFF
        tgt = await rd(b, syms["Parallax_Target_Config"], 4) & 0xFFFFFF
        fr  = await rd(b, syms["Parallax_Transition_Frames"], 1)
        lab = await rd(b, syms["Debug_Lab_Index"], 1)
        cy  = await rd(b, syms["Camera_Y"], 4) >> 16
        print(f"  [{tag:26s}] Lab={lab:3d} Current=${cur:06X} {cfgs.get(cur,'<unknown>'):36s} "
              f"Target=${tgt:06X} {cfgs.get(tgt,'-' if tgt==0 else '<unknown>'):36s} Frames={fr} CamY={cy}")
    await b.call("emulator/run_frames", {"frames": 240})
    await snap("boot +240f (settle)")
    for idx in scenes:
        await G.drive_cursor(b, syms["Debug_Lab_Index"] & 0xFFFFFF, idx)
        await snap(f"cursor -> {idx}, +0f")
        await b.call("emulator/run_frames", {"frames": 4})
        await snap(f"cursor -> {idx}, +4f")
        await b.call("emulator/run_frames", {"frames": 60})
        await snap(f"cursor -> {idx}, +64f")
    return 0

def main():
    rom = os.path.join(REPO, "s4.debug.bin"); lst = os.path.join(REPO, "s4.debug.lst")
    syms = lst_syms(lst)
    cfgs = {v & 0xFFFFFF: k for k, v in syms.items()
            if k.startswith("ParallaxConfig_") or k.startswith("EditorSceneBinding_")}
    inst = AetherInstance(rom=rom, symbols=lst)
    sock = inst.start()
    try:
        return asyncio.run(body(sock, syms, cfgs, [13, 14]))
    finally:
        inst.reap()

if __name__ == "__main__":
    sys.exit(main())
