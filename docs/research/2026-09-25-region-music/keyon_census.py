#!/usr/bin/env python3
"""THROWAWAY (docs/research/2026-09-25-region-music-design.md, Q1 witness): does the Z80 actually SEQUENCE a song? Census of YM key-ons per channel
and DAC-sample activity, headless (oracle-aether subprocess), off the Z80's YM writes.

Leg A: boot, run BOOT frames (the config-A boot hook autoplays), then census W frames.
Leg B (optional --press BUTTON): hold BUTTON 2 frames (a config-A hotkey = another song),
       settle 30 frames, census W frames again.
Prints counts only. Says nothing about how anything SOUNDS.
"""
import argparse, asyncio, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
from suite_paths import add_client_path
add_client_path()
from aether import BusClient
from aether_instance import aether_emulator
from cart_identity import assert_cart_matches_disk
from song_load_mid_drum_witness import YmTap

CH = {0: "FM1", 1: "FM2", 2: "FM3", 4: "FM4", 5: "FM5", 6: "FM6"}

async def census(b, tap, frames):
    tap.events.clear(); d0 = tap.dropped
    for _ in range(frames):
        await b.call("emulator/run_frames", {"frames": 1})
        await tap.poll()
    keyons = collections.Counter(); dac_w = 0; dac_en = []
    for _, _, part, reg, val in tap.events:
        if val is None:
            continue
        if part == 0 and reg == 0x28 and (val & 0xF0):
            keyons[CH.get(val & 7, "?%d" % (val & 7))] += 1
        elif part == 0 and reg == 0x2A:
            dac_w += 1
        elif part == 0 and reg == 0x2B:
            dac_en.append(val)
    print('  [window dropped hits: %d]' % (tap.dropped - d0))
    return keyons, dac_w, dac_en

async def main_async(sock, a):
    b = BusClient(socket_path=sock, client_id="keyon", client_name="keyon_census")
    await b.connect()
    out = []
    await assert_cart_matches_disk(b, a.rom, out)
    tap = YmTap(b); await tap.arm()
    await b.call("emulator/run_frames", {"frames": a.boot})
    await tap.poll()
    k, d, e = await census(b, tap, a.window)
    print("leg A (boot autoplay): z80 YM hits=%d  keyons=%s  total=%d  $2A writes=%d  $2B writes=%s"
          % (tap.z80, dict(sorted(k.items())), sum(k.values()), d, sorted(set(e))))
    fault = tap.liveness_fault()
    print("  liveness:", fault or "live")
    if a.press:
        await b.call("emulator/hold", {"buttons": [a.press], "down": True})
        await b.call("emulator/run_frames", {"frames": 2})
        await b.call("emulator/release_all", {})
        await b.call("emulator/run_frames", {"frames": 30})
        await tap.poll()
        k, d, e = await census(b, tap, a.window)
        print("leg B (after %r): keyons=%s  total=%d  $2A writes=%d  $2B writes=%s"
              % (a.press, dict(sorted(k.items())), sum(k.values()), d, sorted(set(e))))
    print("dropped=%s holes=%s" % (tap.dropped, "n/a"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True); ap.add_argument("--lst", required=True)
    ap.add_argument("--boot", type=int, default=120); ap.add_argument("--window", type=int, default=600)
    ap.add_argument("--press")
    a = ap.parse_args()
    with aether_emulator(a.rom, symbols=a.lst) as sock:
        asyncio.run(main_async(sock, a))
    print("finished=1")

if __name__ == "__main__":
    main()
