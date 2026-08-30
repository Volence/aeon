#!/usr/bin/env python3
"""Poison test for PageCache_Audit's DIRECT-MAP arm (streaming fix F1).

The arm replaces the refcount-vs-nametable comparison under the latch. A check
that cannot fail is not a check, so each of its three invariants is violated in
turn and the engine must STOP (raise_error -> error handler; Frame_Counter and
Logic_Tick freeze). The control run pokes nothing and must keep running.
"""
import argparse, asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path, harness_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
HARNESS = str(harness_path())  # legacy oracle_gui launcher; loud if absent
sys.path.insert(0, HARNESS)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient
from launcher import headless_emulator
from raster_cost_probe import parse_lst


async def rdw(b, addr, n=2):
    r = await b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    return int(r["bytes"][:n * 2], 16)


async def wr(b, addr, val, width):
    await b.call("emulator/write_memory", {"addr": hex(addr & 0xFFFFFF), "value": val, "width": width})


async def case(b, sym, name, poke):
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": 180})
    live_before = await rdw(b, sym["Logic_Tick"], 4)
    if poke:
        await poke(b, sym)
    # the periodic audit fires every PAGECACHE_AUDIT_INTERVAL logic ticks; 400 frames
    # is >3 intervals at 1 frame/tick, so it cannot be missed
    await b.call("emulator/run_frames", {"frames": 400})
    mid = await rdw(b, sym["Logic_Tick"], 4)
    await b.call("emulator/run_frames", {"frames": 60})
    end = await rdw(b, sym["Logic_Tick"], 4)
    halted = (end == mid)
    print(f"  {name:38s} ticks {live_before} -> {mid} -> {end}   "
          f"{'HALTED (audit raised)' if halted else 'still running'}")
    return halted


async def sweep(sock, lst, sym):
    b = BusClient(socket_path=sock, client_id="auditpoison", client_name="audit_poison")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    ok = True

    async def p_rc(bb, s):          # (a) refcounts must all be zero under the latch
        await wr(bb, s["Page_Frames"] + 2, 1, 2)          # frame 0 pf_refcount = 1

    async def p_ident(bb, s):       # (c) Page_Table must still be the identity
        await wr(bb, s["Page_Table"] + 3, 5, 1)           # page 3 -> frame 5

    async def p_dangle(bb, s):      # (b) no cache word may name an unassigned frame
        await wr(bb, s["Page_Frames"] + 8 * 1, 0xFFFF, 2)  # frame 1 pf_page = UNASSIGNED
        # frame 1 is the heavily referenced one (rc 168 in the general regime), so the
        # nametable certainly holds words whose physical index lands in it

    ok &= not await case(b, sym, "CONTROL (no poke)", None)
    ok &= await case(b, sym, "(a) nonzero pf_refcount", p_rc)
    ok &= await case(b, sym, "(b) unassigned frame referenced", p_dangle)
    ok &= await case(b, sym, "(c) Page_Table not the identity", p_ident)
    await b.close()
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin"); ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    lst = str(Path(a.lst).resolve()); sym = parse_lst(lst)
    with headless_emulator(str(Path(a.rom).resolve())) as sock:
        ok = asyncio.run(sweep(sock, lst, sym))
    print("RESULT:", "all three arms are LIVE (control kept running)" if ok else "AT LEAST ONE ARM IS VACUOUS")
    return 0 if ok else 1


sys.exit(main())
