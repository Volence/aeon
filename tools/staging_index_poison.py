#!/usr/bin/env python3
"""Poison test for the staging probe index's machine check (streaming fix F4).

F4 replaced TileCache_FindStagedBlock's 16-key linear scan with a hashed lookup
over Block_Stage_Bucket / Block_Stage_Chain. That is only value-identical to the
scan while the index is a FAITHFUL view of Block_Stage_Keys, so
TileCache_DecompressBlock's claim raises if its unlink ever walks off the chain
of the key it is evicting — the signal that the two have diverged.

A check that cannot fail is not a check. Each arm below breaks the invariant at
runtime and the engine must STOP (raise_error -> error handler; Logic_Tick
freezes). The control pokes nothing and must keep running.

The camera is poked into sustained motion first, because the check lives on the
CLAIM path: a stationary camera stages nothing and would let a broken index sit
undetected, which would make every arm here pass for the wrong reason.

NOT COVERED HERE, deliberately. The claim's other DEBUG arm — "this claim
re-stages a key that is already live" — guards a CALLER precondition (every call
site probes before it claims), not an index state. It has no RAM poison: any poke
that puts a duplicate key in the table also makes the probe HIT it, so the caller
never reaches the claim. Its liveness was shown instead by a throwaway source
mutation that drops one call site's already-staged guard; see the F4 entry in
docs/benchmarks/streaming/CHOKE-DIAGNOSIS.md.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path, harness_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
HARNESS = str(harness_path())  # legacy oracle_gui launcher; loud if absent
sys.path.insert(0, HARNESS)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient              # noqa: E402
from launcher import headless_emulator     # noqa: E402
from raster_cost_probe import parse_lst    # noqa: E402

SST_X_POS = 0x02
BLOCK_STAGE_SLOTS = 16
BLOCK_STAGE_BUCKETS = 256
EMPTY_KEY = 0xFFFFFFFF


async def rd(b, addr, n=2):
    r = await b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    return int(r["bytes"][:n * 2], 16)


async def wr(b, addr, val, width):
    await b.call("emulator/write_memory",
                 {"addr": hex(addr & 0xFFFFFF), "value": val, "width": width})


async def start_motion(b, sym):
    """Poke the leader far to the right so the fill claims blocks continuously."""
    tgt = await rd(b, sym["Camera_Target"], 2)
    leader = 0xFF0000 | tgt if tgt & 0x8000 else tgt
    cam_x = (await rd(b, sym["Camera_X"], 4)) >> 16
    await wr(b, leader + SST_X_POS, (cam_x + 4000) << 16, 4)
    await b.call("emulator/run_frames", {"frames": 8})


async def case(b, sym, name, poke):
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": 180})
    await start_motion(b, sym)
    t0 = await rd(b, sym["Logic_Tick"], 4)
    if poke:
        await poke(b, sym)
    await b.call("emulator/run_frames", {"frames": 90})
    mid = await rd(b, sym["Logic_Tick"], 4)
    await b.call("emulator/run_frames", {"frames": 60})
    end = await rd(b, sym["Logic_Tick"], 4)
    halted = (end == mid)
    print(f"  {name:44s} ticks {t0} -> {mid} -> {end}   "
          f"{'HALTED (claim raised)' if halted else 'still running'}")
    return halted


async def sweep(sock, lst, sym):
    b = BusClient(socket_path=sock, client_id="stgidxpoison",
                  client_name="staging_index_poison")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})

    async def p_wipe(bb, s):
        """(a) Every bucket emptied — every live key becomes unreachable at once."""
        for i in range(BLOCK_STAGE_BUCKETS):
            await wr(bb, s["Block_Stage_Bucket"] + i, 0xFF, 1)

    async def p_one_bucket(bb, s):
        """(b) ONE bucket emptied — the bucket of the key the NEXT claim evicts.

        The subtle version: 255 buckets stay correct, so this fails only if the
        check actually follows the evicted key's own chain rather than noticing
        some coarser breakage.
        """
        slot = await rd(bb, s["Block_Stage_Next"], 2)
        key = await rd(bb, s["Block_Stage_Keys"] + slot * 4, 4)
        if key == EMPTY_KEY:
            print("      (slot about to be evicted is virgin — poison would be a no-op)")
            return
        await wr(bb, s["Block_Stage_Bucket"] + (key & 0xFF), 0xFF, 1)

    async def p_mislink(bb, s):
        """(c) The evicted key's bucket MIS-LINKED to another slot.

        The bucket is populated and the walk finds a real slot there — just not
        the one being evicted — so this fails only if the unlink compares the slot
        it lands on against the slot it is actually retiring. An "is the bucket
        non-empty" check would sail through it.
        """
        slot = await rd(bb, s["Block_Stage_Next"], 2)
        key = await rd(bb, s["Block_Stage_Keys"] + slot * 4, 4)
        if key == EMPTY_KEY:
            print("      (slot about to be evicted is virgin — poison would be a no-op)")
            return
        other = (slot + 1) % BLOCK_STAGE_SLOTS
        await wr(bb, s["Block_Stage_Bucket"] + (key & 0xFF), other * 4, 1)
        await wr(bb, s["Block_Stage_Chain"] + other * 4, 0xFF, 1)

    ok = True
    ok &= not await case(b, sym, "CONTROL (no poke)", None)
    ok &= await case(b, sym, "(a) every bucket emptied", p_wipe)
    ok &= await case(b, sym, "(b) the evicted key's bucket emptied", p_one_bucket)
    ok &= await case(b, sym, "(c) the evicted key's bucket mis-linked", p_mislink)

    # OBSERVATION, not an arm. Truncating every chain link is a MEASURED no-op on
    # this content — which is the collision argument in engine/ram.emp confirmed
    # from the other side: every link already reads $FF, i.e. every bucket holds at
    # most one slot and no probe ever walks past the head. The chain is carried for
    # exactness, not because it is exercised. It is reported rather than asserted
    # because a future act with a wider staging spread may legitimately chain.
    live = [await rd(b, sym["Block_Stage_Chain"] + i * 4, 1)
            for i in range(BLOCK_STAGE_SLOTS)]
    chained = [i for i, v in enumerate(live) if v != 0xFF]
    print(f"  observation: chain links in use after the run: "
          f"{len(chained)}/{BLOCK_STAGE_SLOTS}"
          f"{'' if not chained else f' (slots {chained})'}"
          f"  -> max chain length {1 if not chained else '>1'}")
    await b.close()
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    lst = str(Path(a.lst).resolve())
    sym = parse_lst(lst)
    for n in ("Block_Stage_Bucket", "Block_Stage_Chain", "Block_Stage_Keys",
              "Block_Stage_Next", "Logic_Tick", "Camera_Target", "Camera_X"):
        if n not in sym:
            print(f"symbol {n} missing from {lst}", file=sys.stderr)
            return 3
    with headless_emulator(str(Path(a.rom).resolve())) as sock:
        ok = asyncio.run(sweep(sock, lst, sym))
    print("RESULT:", "the index check is LIVE (control kept running)"
          if ok else "AT LEAST ONE ARM IS VACUOUS")
    return 0 if ok else 1


sys.exit(main())
