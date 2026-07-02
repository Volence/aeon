#!/usr/bin/env python3
"""Reproduce the deterministic STOP wedge headless:
boot 300 frames -> hold UP 3 frames (HCZ2) -> 120 frames -> hold START 3 frames
(Sound_StopMusic) -> 60 frames watching 68k PC + VDP dma_busy/fifo_full.
Prints the socket + keeps the instance alive on wedge for gdb attach if KEEP=1."""
import asyncio, os, sys, time
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, "/home/volence/sonic_hacks/oracle/linux-port/harness")
from aether import BusClient
from launcher import headless_emulator

ROM = "/tmp/claude-1000/-home-volence-sonic-hacks-aeon/4cd11b70-2dc2-41f1-a06f-2ac58573b8f9/scratchpad/s4_task5.bin"
KEEP = os.environ.get("KEEP", "") == "1"


async def status(b):
    r = await b.call("emulator/registers")
    v = await b.call("emulator/read_vdp_registers")
    st = v.get("status", {})
    return r.get("pc"), st.get("dma_busy"), st.get("fifo_full")


async def drive(sock: str) -> int:
    b = BusClient(socket_path=sock, client_id="wedge", client_name="wedge")
    await b.connect()
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": 300})
    print("boot done", flush=True)
    await b.call("emulator/hold", {"buttons": ["up"], "down": True})
    await b.call("emulator/run_frames", {"frames": 3})
    await b.call("emulator/hold", {"buttons": ["up"], "down": False})
    await b.call("emulator/run_frames", {"frames": 120})
    print("UP done", flush=True)
    await b.call("emulator/hold", {"buttons": ["start"], "down": True})
    await b.call("emulator/run_frames", {"frames": 3})
    await b.call("emulator/hold", {"buttons": ["start"], "down": False})
    print("START done", flush=True)
    pcs = []
    for i in range(60):
        await asyncio.wait_for(b.call("emulator/run_frames", {"frames": 1}), timeout=60)
        pc, dma, fifo = await status(b)
        pcs.append((pc, dma, fifo))
        print(f"frame {i}: pc={pc} dma_busy={dma} fifo_full={fifo}", flush=True)
    # wedge = PC frozen over the last 30 frames AND dma_busy stuck true
    last = pcs[-30:]
    frozen = all(p[0] == last[0][0] for p in last)
    stuck = all(p[1] for p in last)
    print(f"VERDICT: frozen_pc={frozen} dma_busy_stuck={stuck} last_pc={last[-1][0]}", flush=True)
    await b.close()
    return 1 if (frozen and stuck) else 0


def main() -> int:
    with headless_emulator(ROM) as sock:
        print(f"SOCKET={sock}", flush=True)
        import subprocess
        out = subprocess.run(["pgrep", "-f", "oracle-harness.*oracle_gui|build/oracle_gui"],
                             capture_output=True, text=True)
        print(f"gui pids: {out.stdout.strip()}", flush=True)
        rc = asyncio.run(drive(sock))
        if rc and KEEP:
            print("WEDGED — keeping instance alive for gdb; sleeping 3600s", flush=True)
            time.sleep(3600)
        return rc


if __name__ == "__main__":
    sys.exit(main())
