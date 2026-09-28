import asyncio
import sys
sys.path.insert(0, "/home/volence/sonic_hacks/aeon/.claude/worktrees/agent-a0dca5666d176ac8f/tools")
import parallax_shadow_key_witness as W
from aether import BusClient
from aether_instance import aether_emulator

rom, lst = sys.argv[1], sys.argv[2]
s, equs = W.parse_lst(lst)


async def main(sock):
    b = BusClient(socket_path=sock, client_id="pxs", client_name="probe")
    await b.connect()
    for fr in (420, 200, 200, 200):
        await b.call("emulator/run_frames", {"frames": fr})
        cfg = int.from_bytes(await W.rd(b, s["Parallax_Current_Config"], 4), "big")
        sel = (await W.rd(b, s["Parallax_Band_Sel"], 16)).hex()
        val = (await W.rd(b, s["Parallax_Band_Sel_Valid"], 1)).hex()
        n = (await W.rd(b, cfg & 0xFFFFFF, 64))
        tops = await W.rd(b, s["Parallax_Shadow_Bands"], 32 * 9)
        t = [int.from_bytes(tops[32 * j:32 * j + 2], "big") for j in range(9)]
        sh = [(tops[32 * j + 7], tops[32 * j + 8]) for j in range(9)]
        print(hex(cfg), "sel", sel, "valid", val, "tops", t, "shifts", sh)
    await b.close()

with aether_emulator(rom, symbols=lst) as sock:
    asyncio.run(main(sock))
