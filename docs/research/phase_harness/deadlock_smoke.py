#!/usr/bin/env python3
"""Smoke test: run the sound-driver-heavy ROM for many frames in deterministic mode
and confirm the machine never wedges (run_frames keeps returning, state keeps evolving,
and the VDP DMA-busy flag is not permanently stuck)."""
import asyncio, sys
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, "/home/volence/sonic_hacks/oracle/linux-port/harness")
from aether import BusClient
from launcher import headless_emulator

ROM = "/home/volence/sonic_hacks/aeon/.worktrees/sound-perf-budget/s4.bin"
FRAMES = 300  # 5 seconds of emulated time of Z80-banked-read + DMA interleave


async def run(sock: str) -> int:
    b = BusClient(socket_path=sock, client_id="smoke", client_name="smoke")
    await b.connect()
    await b.call("emulator/reset", {"wait": True, "run": False})
    hashes = []
    for i in range(FRAMES):
        # A wedged execution thread shows up as run_frames hanging; time it out hard.
        await asyncio.wait_for(b.call("emulator/run_frames", {"frames": 1}), timeout=60)
        hashes.append((await b.call("emulator/state_hash"))["combined"])
        if (i + 1) % 20 == 0:
            print(f"frame {i + 1}", flush=True)
    await b.close()
    # A deadlocked 68k spinning on dma_busy freezes machine state: consecutive identical
    # hashes over a long window. Look for any 120-frame window with zero change.
    longest_flat = flat = 0
    for i in range(1, len(hashes)):
        flat = flat + 1 if hashes[i] == hashes[i - 1] else 0
        longest_flat = max(longest_flat, flat)
    print(f"frames run: {len(hashes)}/{FRAMES}, longest flat-hash run: {longest_flat}")
    return 0 if (len(hashes) == FRAMES and longest_flat < 120) else 1


def main() -> int:
    with headless_emulator(ROM) as sock:
        return asyncio.run(run(sock))


if __name__ == "__main__":
    sys.exit(main())
