#!/usr/bin/env python3
"""One-question diagnostic: what does `Parallax_Current_Config` hold in an ORDINARY boot?

Not a gate. It installs nothing, drives no effects-lab cursor, and asserts nothing about
the value -- it REPORTS it, beside every `ParallaxConfig_*` / `EditorSceneBinding_*`
address derived from THIS build's own listing. Exit 0 measured, 2 could-not-measure.
"""
import argparse, asyncio, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from suite_paths import add_client_path
add_client_path()
from aether import BusClient
from aether_instance import AetherInstance

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def lst_syms(path):
    syms = {}
    for line in open(path, errors="replace"):
        m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([0-9A-Fa-f]+)\s+C\s*\|', line)
        if m:
            syms[m.group(1)] = int(m.group(2), 16)
    return syms

async def call(b, m, p): return await b.call(m, p)

async def rd(b, addr, n):
    r = await call(b, "emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    raw = r["bytes"].upper().removeprefix("0X")
    if len(raw) != n * 2:
        raise RuntimeError(f"read_memory gave {len(raw)//2} bytes, wanted {n}")
    return int(raw, 16)

async def main_async(a, inst, sock, syms, cfgs):
    try:
        b = BusClient(sock)
        await b.connect()
        if True:
            print(f"server pid {inst.pid}  rom {os.path.basename(a.rom)}")
            async def snap(tag):
                cur = await rd(b, syms["Parallax_Current_Config"], 4) & 0xFFFFFF
                tgt = await rd(b, syms["Parallax_Target_Config"], 4) & 0xFFFFFF
                fr  = await rd(b, syms["Parallax_Transition_Frames"], 1)
                cx  = await rd(b, syms["Camera_X"], 4); cy = await rd(b, syms["Camera_Y"], 4)
                reg = await rd(b, syms["Region_Current"], 4) & 0xFFFFFF
                lab = await rd(b, syms["Debug_Lab_Index"], 1)
                print(f"  [{tag:22s}] Current=${cur:06X} {cfgs.get(cur,'<NOT a config label>'):38s} "
                      f"Target=${tgt:06X} Frames={fr} Cam=({cx>>16},{cy>>16}) "
                      f"Region=${reg:06X} Lab={lab}")
                return cur
            seen = []
            await call(b, "emulator/run_frames", {"frames": a.boot})
            seen.append(await snap(f"boot +{a.boot}f"))
            if a.press_b:
                await call(b, "emulator/play_input",
                           {"rows": [{"start": 0, "end": 6, "buttons": ["b"]}], "maxFrames": 8})
                await call(b, "emulator/run_frames", {"frames": 10})
                seen.append(await snap("after B (leave freefly)"))
            for i in range(a.samples):
                await call(b, "emulator/run_frames", {"frames": a.step})
                seen.append(await snap(f"play +{(i+1)*a.step}f"))
            # ordinary play: hold RIGHT so the camera actually travels regions
            await call(b, "emulator/play_input",
                       {"rows": [{"start": 0, "end": a.travel, "buttons": ["right"]}],
                        "maxFrames": a.travel})
            seen.append(await snap(f"after RIGHT {a.travel}f"))
            await call(b, "emulator/run_frames", {"frames": 60})
            seen.append(await snap("settled +60f"))
            uniq = sorted(set(seen))
            print("\nDISTINCT VALUES OF Parallax_Current_Config OVER THE RUN:")
            for v in uniq:
                print(f"  ${v:06X}  {cfgs.get(v, '<NOT any ParallaxConfig_*/EditorSceneBinding_* label>')}")
            bad = [v for v in uniq if v not in cfgs and v != 0]
            print(f"\nVERDICT: {len(uniq)} distinct value(s); "
                  f"{'ALL resolve to a known config label' if not bad else f'{len(bad)} DO NOT resolve to any config label'}")
            return 0
    finally:
        inst.reap()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rom", default="s4.debug.bin"); p.add_argument("--lst", default="s4.debug.lst")
    p.add_argument("--boot", type=int, default=240); p.add_argument("--step", type=int, default=60)
    p.add_argument("--samples", type=int, default=3); p.add_argument("--travel", type=int, default=300)
    p.add_argument("--press-b", action="store_true", default=True)
    p.add_argument("--no-press-b", dest="press_b", action="store_false")
    a = p.parse_args()
    rom = os.path.join(REPO, a.rom); lst = os.path.join(REPO, a.lst)
    syms = lst_syms(lst)
    cfgs = {v & 0xFFFFFF: k for k, v in syms.items()
            if k.startswith("ParallaxConfig_") or k.startswith("EditorSceneBinding_")}
    need = ("Parallax_Current_Config", "Parallax_Target_Config",
            "Parallax_Transition_Frames", "Camera_X", "Camera_Y",
            "Region_Current", "Debug_Lab_Index")
    missing = [n for n in need if n not in syms]
    if missing:
        print(f"COULD NOT MEASURE: symbols absent from {a.lst}: {missing}"); return 2
    inst = AetherInstance(rom=rom, symbols=lst)
    sock = inst.start()          # SYNCHRONOUS -- it runs its own asyncio.run for the
                                 # handshake, so it must not be called from inside a loop
    return asyncio.run(main_async(a, inst, sock, syms, cfgs))

if __name__ == "__main__":
    sys.exit(main())
