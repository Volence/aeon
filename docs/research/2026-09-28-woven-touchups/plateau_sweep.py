#!/usr/bin/env python3
"""SCRATCH: can the player get from the woven act's START onto Emerald Hill's east plateau (the
C5 tunnel's mouth, x 1344..2559, standing y ~2400..2480)? From the start: hold RIGHT, inject a
ground speed once, press jump (C) at frame k, keep holding right. One boot per (speed, k)."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "tools"))
from suite_paths import add_client_path  # noqa
add_client_path()
from aether import BusClient  # noqa
from aether_instance import aether_emulator  # noqa
import loop_step_over_witness as L  # noqa


async def run(sock, syms, equs, gsp, k, frames=420):
    b = BusClient(socket_path=sock, client_id="pl", client_name="plateau_sweep")
    await b.connect()
    bus = L.Bus(b)
    P = syms["Player_1"]
    AX, AY = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    AG = P + L.PLAYERV_GROUND_SPEED
    await bus.frames(240)
    if (await bus.read(P + L.PLAYERV_DEBUG_FLAG, 1))[0]:
        await b.call("emulator/press", {"buttons": ["b"]})
        await bus.frames(4)
    await bus.frames(20)
    await b.call("emulator/hold", {"buttons": ["right"], "down": True})
    if gsp:
        await bus.write(AG, gsp & 0xFFFF, 2)
    best = None
    for f in range(frames):
        if f == k:
            await b.call("emulator/press", {"buttons": ["c"]})
        await bus.frames(1)
        x = int.from_bytes(await bus.read(AX, 4), "big") >> 16
        y = int.from_bytes(await bus.read(AY, 4), "big") >> 16
        if x >= 1344 and (best is None or y < best[1]):
            best = (x, y, f)
        if x > 2560:
            break
    return best, x, y


def main():
    rom, lst = sys.argv[1:3]
    syms, equs = L.parse_lst(lst)
    hits = 0
    for gsp in (0, equs["PHYS_TOP_SPEED"], 0x0C00):
        for k in range(0, 400, 8):
            with aether_emulator(rom, symbols=lst) as sock:
                best, x, y = asyncio.run(run(sock, syms, equs, gsp, k))
            on = best is not None and best[1] <= 2470 and 1360 <= best[0] < 2560
            hits += on
            print(f"SWEEP gsp={gsp:#x} jump@{k:3d}: highest point east of x 1344 = {best}; "
                  f"end ({x}, {y}){'  PLATEAU' if on else ''}", flush=True)
    print(f"plateau hits: {hits}")
    print("finished=0")


if __name__ == "__main__":
    main()
