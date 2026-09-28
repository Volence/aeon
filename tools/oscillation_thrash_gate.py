#!/usr/bin/env python3
"""oscillation_thrash_gate — a camera swinging back and forth by one block decodes NOTHING.

WHAT IT GATES (perf/oscillation-thrash, 2026-09-28; docs/research/2026-09-28-oscillation-thrash.md).
The tile cache's speculative scans stage the block one past the cache edge in the direction of
motion, and every staging claim evicts one of BLOCK_STAGE_SLOTS round-robin slots. Before the
arming run (H_PFX_ARM / V_PFX_ARM in engine/system/constants.emp), a camera oscillating by one
block re-aimed the scans at every reversal: measured on OJZ, 450 decodes in the 600 ticks after
warm-up, every one of them a block decoded before, and each wasted claim evicted an edge block
the demand fill then decoded again.

THE ASSERTION. In DEBUG free flight: fly right to leave the act edge, then alternate
right/left, each half-period H_PFX_ARM px long (the swing is ONE BLOCK). After two whole
periods of warm-up, count staging claims (`Block_Stage_Gen`, +1 per claim) over the measure
window. Expected: **0**.

WHY 0 IS DERIVED, NOT OBSERVED. With a one-block swing each cache edge crosses at most one
block-column boundary, so the demand working set is at most two block columns of
((TILE_CACHE_ROWS - 1) / BLOCK_TILE_SIZE + 2) blocks each at the worst alignment. The gate checks that this is <=
BLOCK_STAGE_SLOTS (it is 10 <= 16 today) and refuses to measure (exit 2) if it is not. With the
working set resident, a claim can only come from speculation; the arming run is what stops the
scans staging on a swing no longer than H_PFX_ARM, and the vertical scan has no motion to see.
Nothing else in the fill claims.

LOUD ON UNMEASURABLE (exit 2): missing symbols, a ROM with no free flight, a camera that did
not actually swing by the derived amount at least 4 times inside the window, or the premise
above failing. Exit 1 = claims happened. Exit 0 = none.

RED-FIRST (docs/research/2026-09-28-oscillation-thrash/results/redfirst_gate.txt): with the
horizontal arming gate's two instructions removed from engine/level/tile_cache.emp's col scan,
the rebuilt DEBUG ROM is RED here.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import zlib

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from suite_paths import add_client_path  # noqa: E402
add_client_path()

from aether import BusClient                     # noqa: E402
from aether_instance import AetherInstance, read_bytes  # noqa: E402
from raster_cost_probe import parse_lst           # noqa: E402

BOOT_FRAMES = 300
SST_X_POS = 0x02


class Unmeasurable(Exception):
    pass


def parse_equ(path: str) -> dict[str, int]:
    out = {}
    for m in re.finditer(r"^EQU (\w+) = \$([0-9A-Fa-f]+)$", open(path, errors="replace").read(), re.M):
        out[m.group(1)] = int(m.group(2), 16)
    return out


async def rd(b, addr: int, n: int) -> int:
    return int((await read_bytes(b, addr, n))[:2 * n], 16)


async def body(sock: str, sym: dict, k: dict, args) -> int:
    b = BusClient(sock, client_id="oscthrash", client_name="oscillation_thrash_gate")
    await b.connect()
    try:
        async def tick():
            return await rd(b, sym["Logic_Tick"], 4)

        async def camx():
            return await rd(b, sym["Camera_X"], 4) >> 16

        await b.call("emulator/reset", {})
        await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})
        # the DEBUG shape boots in free flight: holding RIGHT moves the camera at a fixed step
        held = None

        async def hold(btn):
            nonlocal held
            if held == btn:
                return
            if held:
                await b.call("emulator/hold", {"buttons": [held], "down": False})
            await b.call("emulator/hold", {"buttons": [btn], "down": True})
            held = btn

        await hold("right")
        t0 = await tick()
        # lead-in: 40 ticks right (clear of the act's left edge, where the camera starts
        # clamped); the flight step is measured over its last 10 ticks
        while await tick() - t0 < 30:
            await b.call("emulator/run_frames", {"frames": 1})
        t1 = await tick()
        x0 = await camx()
        while await tick() - t0 < 40:
            await b.call("emulator/run_frames", {"frames": 1})
        x1 = await camx()
        dt = await tick() - t1
        step = (x1 - x0) // max(dt, 1)
        if step <= 0 or (x1 - x0) % max(dt, 1):
            raise Unmeasurable(f"no steady free flight: camera {x0}->{x1} over {dt} ticks "
                               "(not a DEBUG shape, or the flight was blocked)")
        half = k["H_PFX_ARM"] // step
        if half * step != k["H_PFX_ARM"]:
            raise Unmeasurable(f"H_PFX_ARM {k['H_PFX_ARM']} px is not a whole number of "
                               f"{step}-px flight ticks")
        warm, meas = 4 * half, args.ticks
        gen0 = None
        xs = []
        ts = await tick()
        while True:
            t = await tick() - ts
            if t >= warm + meas:
                break
            await hold("left" if (t // half) % 2 else "right")
            if t >= warm and gen0 is None:
                gen0 = await rd(b, sym["Block_Stage_Gen"], 2)
            await b.call("emulator/run_frames", {"frames": 1})
            if gen0 is not None:
                xs.append(await camx())
        gen1 = await rd(b, sym["Block_Stage_Gen"], 2)
        claims = (gen1 - gen0) & 0xFFFF
        swing = max(xs) - min(xs)
        moves = [d for d in (xs[i + 1] - xs[i] for i in range(len(xs) - 1)) if d]
        rev = sum(1 for i in range(len(moves) - 1) if moves[i] * moves[i + 1] < 0)
        print(f"flight step {step} px/tick; half-period {half} ticks (H_PFX_ARM {k['H_PFX_ARM']} px); "
              f"warm-up {warm} ticks; measured {meas} ticks: camera x {min(xs)}..{max(xs)} "
              f"(swing {swing}), {rev} reversals; staging claims {claims}")
        if abs(swing - k["H_PFX_ARM"]) > step or rev < 4:
            raise Unmeasurable(f"the camera did not swing by H_PFX_ARM ({swing} px, {rev} reversals)")
        return claims
    finally:
        await b.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.debug.bin"))
    ap.add_argument("--lst", default=os.path.join(AEON, "s4.debug.lst"))
    ap.add_argument("--ticks", type=int, default=600, help="measure window, logic ticks")
    args = ap.parse_args()
    for p in (args.rom, args.lst):
        if not os.path.exists(p):
            print(f"oscillation_thrash_gate: UNMEASURABLE — {p} does not exist", file=sys.stderr)
            return 2
    k = parse_equ(args.lst)
    sym = parse_lst(args.lst)
    need_k = ["H_PFX_ARM", "BLOCK_STAGE_SLOTS", "TILE_CACHE_ROWS", "BLOCK_TILE_SIZE"]
    need_s = ["Logic_Tick", "Camera_X", "Block_Stage_Gen"]
    miss = [n for n in need_k if n not in k] + [n for n in need_s if n not in sym]
    if miss:
        print(f"oscillation_thrash_gate: UNMEASURABLE — the listing lacks {miss}", file=sys.stderr)
        return 2
    # blocks a TILE_CACHE_ROWS-row column touches at the worst alignment, per block column
    ws = 2 * ((k["TILE_CACHE_ROWS"] - 1) // k["BLOCK_TILE_SIZE"] + 2)
    if ws > k["BLOCK_STAGE_SLOTS"]:
        print(f"oscillation_thrash_gate: UNMEASURABLE — the premise fails: a one-block swing's "
              f"working set is {ws} blocks > BLOCK_STAGE_SLOTS {k['BLOCK_STAGE_SLOTS']}, so a "
              f"nonzero count would not be speculation's", file=sys.stderr)
        return 2
    crc = zlib.crc32(open(args.rom, "rb").read())
    print(f"rom {os.path.basename(args.rom)} crc32 {crc:08x}; working set <= {ws} blocks of "
          f"{k['BLOCK_STAGE_SLOTS']} slots; expected claims 0")
    inst = AetherInstance(args.rom, symbols=args.lst)
    try:
        sock = inst.start()
        claims = asyncio.run(asyncio.wait_for(body(sock, sym, k, args), 600))
    except Unmeasurable as e:
        print(f"oscillation_thrash_gate: UNMEASURABLE — {e}", file=sys.stderr)
        return 2
    except Exception as e:                       # noqa: BLE001 — spawn/transport = setup
        print(f"oscillation_thrash_gate: UNMEASURABLE — {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    finally:
        inst.reap()
    if claims:
        print(f"RED   {claims} staging claim(s) while the camera swung by one block: the "
              f"speculative scans are re-aiming at every reversal and evicting edge blocks")
        return 1
    print("GREEN a one-block oscillation claimed no staging slot")
    return 0


if __name__ == "__main__":
    sys.exit(main())
