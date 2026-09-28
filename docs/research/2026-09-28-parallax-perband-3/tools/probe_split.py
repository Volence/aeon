import asyncio
import sys
sys.path.insert(0, "/home/volence/sonic_hacks/aeon/.claude/worktrees/agent-a0dca5666d176ac8f/tools")
import parallax_shadow_key_witness as W
from aether import BusClient
from aether_bytes import write_bytes
from aether_instance import aether_emulator
from pathlib import Path

rom, lst = sys.argv[1], sys.argv[2]
legs = eval(sys.argv[3])  # [(name, dirs, dy, tap, frames)]
s, equs = W.parse_lst(lst)
romb = Path(rom).read_bytes()


async def rd16(b, a):
    return int.from_bytes(await W.rd(b, a, 2), "big")


async def main(sock):
    b = BusClient(socket_path=sock, client_id="pxp", client_name="probe")
    await b.connect()
    await b.call("emulator/run_frames", {"frames": 420})
    act = int.from_bytes(await W.rd(b, s["Current_Act_Ptr"], 4), "big") & 0xFFFFFF
    reg, wy = W.anchored_region(romb, act, equs)
    for name, dirs, dy, tap, frames in legs:
        await write_bytes(b, s["Warp_Req_X"], f"{reg['x0'] + 104:04X}")
        await write_bytes(b, s["Warp_Req_Y"], f"{wy + dy:04X}")
        await write_bytes(b, s["Warp_Req_Flag"], "01")
        for _ in range(120):
            await b.call("emulator/run_frames", {"frames": 1})
            if (await W.rd(b, s["Warp_Req_Flag"], 1))[0] == 0:
                break
        await b.call("emulator/run_frames", {"frames": 30})
        print("==", name)
        for i in range(frames):
            if dirs and (i == 0 or tap):
                await b.call("emulator/hold", {"buttons": dirs, "down": not tap or i % tap == 0})
            vs = await rd16(b, s["Parallax_Current_Vscroll_BG"]) & 511
            sp = await rd16(b, s["Parallax_Shadow_Split"])
            L = await rd16(b, s["Effects_Screen_L"])
            cy = await rd16(b, s["Camera_Y"])
            await b.call("emulator/run_frames", {"frames": 1})
            vs1 = await rd16(b, s["Parallax_Current_Vscroll_BG"]) & 511
            sp1 = await rd16(b, s["Parallax_Shadow_Split"])
            tops = await W.rd(b, s["Parallax_Shadow_Bands"], 32 * 6)
            t = [int.from_bytes(tops[32 * j:32 * j + 2], "big") for j in range(6)]
            print(i, "camY", cy, "L", L if L < 32768 else L - 65536, "vs", vs, "->", vs1, "split", sp, "->", sp1, "tops", t)
        if dirs:
            await b.call("emulator/hold", {"buttons": dirs, "down": False})
    await b.close()

with aether_emulator(rom, symbols=lst) as sock:
    asyncio.run(main(sock))
