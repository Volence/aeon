#!/usr/bin/env python3
"""SCRATCH headless probe (no MCP): from a placed point, try scripted input patterns and report
the box the player's centre covered. Corroborates the flood model's cut claims on the real ROM.

    python3 escape_probe.py ROM LST MANIFEST NAME X Y [frames]
X, Y: the player's centre to place (use 'start' to begin at the act's own start after boot).
"""
import asyncio, sys
from pathlib import Path
WT = Path.cwd()
sys.path.insert(0, str(WT / "tools"))
from suite_paths import add_client_path  # noqa
add_client_path()
from aether import BusClient  # noqa
from aether_instance import aether_emulator  # noqa
import loop_step_over_witness as L  # noqa
import tunnel_run_witness as T  # noqa

POLICIES = {
    "right+jump":  [("right", 40)],
    "left+jump":   [("left", 40)],
    "right-run":   [("right", 0)],
    "left-run":    [("left", 0)],
    "zigzag":      [("right", 25), ("left", 25)],
    "spin-right":  [("spinR", 0)],
    "spin-left":   [("spinL", 0)],
}


async def run(sock, syms, equs, x, y, policy, frames):
    b = BusClient(socket_path=sock, client_id="esc", client_name="escape_probe")
    await b.connect()
    bus = L.Bus(b)
    T._EQUS.update(equs)
    P = syms["Player_1"]
    AX, AY = P + equs["SST_x_pos"], P + equs["SST_y_pos"]
    ADBG = P + L.PLAYERV_DEBUG_FLAG
    await bus.frames(240)
    if (await bus.read(ADBG, 1))[0]:
        await b.call("emulator/press", {"buttons": ["b"]})
        await bus.frames(4)
    if x is not None:
        await T.place(b, bus, syms, x, y)
    await bus.frames(30)
    xs, ys = [], []
    held = set()

    async def hold(btns):
        nonlocal held
        want = set(btns)
        for k in held - want:
            await b.call("emulator/hold", {"buttons": [k], "down": False})
        for k in want - held:
            await b.call("emulator/hold", {"buttons": [k], "down": True})
        held = want

    steps = POLICIES[policy]
    seg = frames // len(steps) if len(steps) > 1 else frames
    f = 0
    while f < frames:
        dirn, jump_every = steps[(f // 120) % len(steps)] if len(steps) > 1 else steps[0]
        if dirn in ("spinR", "spinL"):
            d = "right" if dirn == "spinR" else "left"
            # a spindash: crouch, rev 4x, release, then run 60 frames holding the direction
            await hold(["down"])
            await bus.frames(4)
            for _ in range(4):
                await b.call("emulator/press", {"buttons": ["c"]})
                await bus.frames(3)
            await hold([])
            await bus.frames(1)
            await hold([d])
            for _ in range(60):
                await bus.frames(1); f += 1
                xs.append(int.from_bytes(await bus.read(AX, 4), "big") >> 16)
                ys.append(int.from_bytes(await bus.read(AY, 4), "big") >> 16)
            f += 17
            continue
        await hold([dirn])
        if jump_every and f % jump_every == 0:
            await b.call("emulator/press", {"buttons": ["c"]})
        await bus.frames(1); f += 1
        xs.append(int.from_bytes(await bus.read(AX, 4), "big") >> 16)
        ys.append(int.from_bytes(await bus.read(AY, 4), "big") >> 16)
    await hold([])
    st = await bus.status()
    fault = "ErrorHandler" in (st.get("symbolAtPc") or "")
    await b.close() if hasattr(b, "close") else None
    return min(xs), max(xs), min(ys), max(ys), xs[-1], ys[-1], fault


def main():
    rom, lst, man, name = sys.argv[1:5]
    if sys.argv[5] == "start":
        x = y = None
    else:
        x, y = int(sys.argv[5]), int(sys.argv[6])
    frames = int(sys.argv[7]) if len(sys.argv) > 7 else 1200
    pols = sys.argv[8].split(",") if len(sys.argv) > 8 else list(POLICIES)
    syms, equs = L.parse_lst(lst)
    for pol in pols:
        with aether_emulator(rom, symbols=lst) as sock:
            r = asyncio.run(run(sock, syms, equs, x, y, pol, frames))
        print(f"PROBE {name} {pol:11s}: x {r[0]}..{r[1]}  y {r[2]}..{r[3]}  end ({r[4]}, {r[5]})"
              + ("  FAULTED" if r[6] else ""), flush=True)
    print("finished=0")


if __name__ == "__main__":
    main()
