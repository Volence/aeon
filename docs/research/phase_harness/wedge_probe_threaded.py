#!/usr/bin/env python3
"""Probe the wedged guest: 68k single-steps, Z80 state, and the spin-loop code bytes."""
import asyncio, sys
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, "/home/volence/sonic_hacks/oracle/linux-port/harness")
from aether import BusClient
from launcher_threaded import headless_emulator

SCRATCH = "/tmp/claude-1000/-home-volence-sonic-hacks-aeon/4cd11b70-2dc2-41f1-a06f-2ac58573b8f9/scratchpad"
ROM = f"{SCRATCH}/s4_task5.bin"


async def wedge(b):
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": 300})
    await b.call("emulator/hold", {"buttons": ["up"], "down": True})
    await b.call("emulator/run_frames", {"frames": 3})
    await b.call("emulator/hold", {"buttons": ["up"], "down": False})
    await b.call("emulator/run_frames", {"frames": 120})
    await b.call("emulator/hold", {"buttons": ["start"], "down": True})
    await b.call("emulator/run_frames", {"frames": 3})
    await b.call("emulator/hold", {"buttons": ["start"], "down": False})
    await b.call("emulator/run_frames", {"frames": 35})


async def main_async(sock):
    b = BusClient(socket_path=sock, client_id="pr", client_name="pr")
    await b.connect()
    await wedge(b)
    # per-frame 68k + z80 pc
    for i in range(3):
        await b.call("emulator/run_frames", {"frames": 1})
        r = await b.call("emulator/registers")
        z = await b.call("emulator/z80_registers")
        print(f"frame {i}: 68k pc={r['pc']} a1={r['a1']} | z80 pc={z.get('pc')} sp={z.get('sp')} halted={z.get('halted')}", flush=True)
    # single-steps
    for i in range(8):
        s = await b.call("emulator/step", {})
        r = await b.call("emulator/registers")
        print(f"step {i}: pc={r['pc']} step_reply={s}", flush=True)
    # code bytes around the loop
    m = await b.call("emulator/read", {"addr": 0x1C90, "len": 0x50})
    print("code @1C90:", m, flush=True)
    # 68k call stack if available
    try:
        cs = await b.call("emulator/call_stack")
        print("call_stack:", cs, flush=True)
    except Exception as e:
        print("call_stack err:", e, flush=True)
    await b.close()
    return 0


def main():
    with headless_emulator(ROM) as sock:
        print(f"sock={sock}", flush=True)
        return asyncio.run(main_async(sock))


if __name__ == "__main__":
    sys.exit(main())
