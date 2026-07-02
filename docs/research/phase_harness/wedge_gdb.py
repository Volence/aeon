#!/usr/bin/env python3
"""Boot, wedge, then gdb-dump VDP + M68000 + arbiter state from inside the wedge."""
import asyncio, subprocess, sys, time
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, "/home/volence/sonic_hacks/oracle/linux-port/harness")
from aether import BusClient
from launcher import headless_emulator

SCRATCH = "/tmp/claude-1000/-home-volence-sonic-hacks-aeon/4cd11b70-2dc2-41f1-a06f-2ac58573b8f9/scratchpad"
ROM = f"{SCRATCH}/s4_task5.bin"
GDB_SCRIPT = f"{SCRATCH}/wedge_dump.gdb"


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
    await b.call("emulator/run_frames", {"frames": 30})
    pcs = []
    for _ in range(5):
        await b.call("emulator/run_frames", {"frames": 1})
        pcs.append((await b.call("emulator/registers"))["pc"])
    print(f"wedge check pcs: {pcs}", flush=True)
    return all(p == pcs[0] for p in pcs)


async def drive_more(b, calls, frames):
    for _ in range(calls):
        try:
            await asyncio.wait_for(b.call("emulator/run_frames", {"frames": frames}), timeout=60)
        except Exception as e:
            print(f"drive err: {e}", flush=True)
            return


async def main_async(sock, pid):
    b = BusClient(socket_path=sock, client_id="wg", client_name="wg")
    await b.connect()
    if not await wedge(b):
        print("NOT WEDGED — abort", flush=True)
        return 2
    print(f"WEDGED. attaching gdb to {pid}", flush=True)
    gdb = subprocess.Popen(
        ["sudo", "-n", "gdb", "-p", str(pid), "-batch", "-x", GDB_SCRIPT],
        stdout=open(f"{SCRATCH}/wedge_dump.log", "w"), stderr=subprocess.STDOUT)
    await asyncio.sleep(5)
    await drive_more(b, 8, 10)
    try:
        gdb.wait(timeout=45)
    except subprocess.TimeoutExpired:
        print("gdb still waiting (a breakpoint never hit) — killing it", flush=True)
        subprocess.run(["sudo", "-n", "kill", str(gdb.pid)])
        time.sleep(2)
    await b.close()
    return 0


def main():
    with headless_emulator(ROM) as sock:
        out = subprocess.run(["fuser", sock], capture_output=True, text=True)
        pid = out.stdout.strip().split()[-1]
        print(f"sock={sock} pid={pid}", flush=True)
        return asyncio.run(main_async(sock, pid))


if __name__ == "__main__":
    sys.exit(main())
