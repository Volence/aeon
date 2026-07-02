#!/usr/bin/env python3
"""Call run_frames N on a given oracle socket (used to trigger gdb breakpoints)."""
import asyncio, sys
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
from aether import BusClient


async def go(sock, n):
    b = BusClient(socket_path=sock, client_id="drv", client_name="drv")
    await b.connect()
    try:
        r = await asyncio.wait_for(b.call("emulator/run_frames", {"frames": n}), timeout=120)
        print("run_frames ok", r)
    except Exception as e:
        print("run_frames err:", e)
    await b.close()

asyncio.run(go(sys.argv[1], int(sys.argv[2])))
