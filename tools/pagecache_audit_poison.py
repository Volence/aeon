#!/usr/bin/env python3
"""Poison test for PageCache_Audit's DIRECT-MAP arm (streaming fix F1) and its
per-tick amortised schedule (audit-amortise, 2026-09-26).

The arm replaces the refcount-vs-nametable comparison under the latch. A check
that cannot fail is not a check, so each of its three invariants is violated in
turn and the engine must STOP (raise_error -> error handler; Frame_Counter and
Logic_Tick freeze). The control run pokes nothing and must keep running.

AMORTISED SINCE 2026-09-26. In the latched regimes the nametable half of the audit
((b): no cache word names an unassigned frame) is no longer one whole walk on the
interval tick: VSync_Wait's idle slot audits it in paced slices. So two new arms
plant ONE dangling word — the corruption the sliced walk exists to catch — at the
first and at the last nametable word (the first and the last slice), and every arm
now also measures its DETECTION LATENCY in logic ticks, poke to halt. The bounds are
derived from source, not copied: every frame-level check runs once per
PAGECACHE_AUDIT_INTERVAL ticks (engine/system/constants.emp), and a nametable word is
audited once per interval at its slice's phase give or take PAGE_AUDIT_SLACK_TICKS
(engine/level/page_cache.emp), so a corruption that stays put is caught within
INTERVAL, resp. INTERVAL + SLACK, ticks. A halt later than that, or no halt, FAILS.
A general-regime arm forces PageCache_Direct_Map to 0 so the interval tick must take
the whole-walk refcount comparison (the arm the amortised schedule leaves atomic) and
prove it still fires through the new path. At idle the fill writes nothing, so the
audit is the only thing that can raise on that poke.

Exit: 0 every arm fired within the bound and the control kept running; 1 otherwise;
2 COULD NOT RUN (a precondition the arms need is not met — e.g. no unassigned frame
to aim a dangling word at).
"""
import argparse, asyncio, re, sys
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

REPO = Path(__file__).resolve().parent.parent
CONSTS = REPO / "engine" / "system" / "constants.emp"
PAGE_CACHE = REPO / "engine" / "level" / "page_cache.emp"
STEP = 4            # frames between Logic_Tick reads while waiting for the halt


def const(name, src=CONSTS):
    """A plain integer `[pub ]const NAME = <int>` from engine source. Loud if the
    spelling changed: a guessed number here would make the latency bound a copy."""
    m = re.search(rf"^(?:pub )?const {name}\s*=\s*(\d+)\b", src.read_text(), re.M)
    if not m:
        print(f"COULD NOT RUN: `const {name} = <int>` not found in {src}")
        raise SystemExit(2)
    return int(m.group(1))


INTERVAL = const("PAGECACHE_AUDIT_INTERVAL")
# a nametable word is audited once per interval at its slice's phase, give or take the
# pacing slack, so its bound is INTERVAL + SLACK (page_cache.emp, PageCache_Audit LATENCY)
WORD_BOUND = INTERVAL + const("PAGE_AUDIT_SLACK_TICKS", PAGE_CACHE)
NT_WORDS = const("TILE_CACHE_COLS") * const("TILE_CACHE_ROWS")
PF_SIZE = 8          # sizeof(PageFrame); page_cache.emp ensures it is 8 (`lsl #3` stride)
TILE_SHIFT = 6       # PAGE_FRAME_TILE_SHIFT; constants.emp ensures 1 << 6 == ART_POOL_PAGE_TILES


async def rdw(b, addr, n=2):
    r = await b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    return int(r["bytes"][:n * 2], 16)


async def wr(b, addr, val, width):
    await b.call("emulator/write_memory", {"addr": hex(addr & 0xFFFFFF), "value": val, "width": width})


async def boot(b):
    """Reset and settle into play. The ONE reset site (tools/test_legacy_seam_keys.py
    pins the count of legacy `reset.wait` senders)."""
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": 180})


async def case(b, sym, name, poke, expect_halt=True, bound=INTERVAL):
    """Boot, settle, poke, then step until Logic_Tick stops. Returns (ok, latency)."""
    await boot(b)
    t0 = await rdw(b, sym["Logic_Tick"], 4)
    if poke:
        await poke(b, sym)
    # up to 3 intervals of frames (1 frame/tick at idle), then a final stillness check
    last, halted_at = t0, None
    for _ in range((3 * WORD_BOUND) // STEP + 1):
        await b.call("emulator/run_frames", {"frames": STEP})
        now = await rdw(b, sym["Logic_Tick"], 4)
        if now == last:
            await b.call("emulator/run_frames", {"frames": 30})
            if await rdw(b, sym["Logic_Tick"], 4) == now:
                halted_at = now
                break
        last = now
    halted = halted_at is not None
    latency = (halted_at - t0) if halted else None
    if expect_halt:
        ok = halted and latency <= bound
    else:
        ok = not halted
    verdict = ("HALTED (audit raised)" if halted else "still running")
    lat = f" after {latency} ticks (bound {bound})" if halted else f" ({last - t0} ticks run)"
    print(f"  {name:44s} {verdict}{lat}   {'ok' if ok else 'FAIL'}")
    return ok, latency


async def sweep(sock, lst, sym):
    b = BusClient(socket_path=sock, client_id="auditpoison", client_name="audit_poison")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    ok = True

    # Precondition for the single-word arms: an UNASSIGNED frame to aim a word at. Read
    # it off the booted state rather than assuming the act's page count.
    await boot(b)
    direct = await rdw(b, sym["PageCache_Direct_Map"], 1)
    free = None
    for f in range(16):
        if await rdw(b, sym["Page_Frames"] + PF_SIZE * f, 2) == 0xFFFF:
            free = f
            break
    print(f"  booted: PageCache_Direct_Map=${direct:02X}, first unassigned frame = {free}, "
          f"nametable {NT_WORDS} words, interval {INTERVAL} ticks")
    if direct == 0 or free is None:
        print("COULD NOT RUN: the arms need a latched regime and an unassigned frame")
        await b.close()
        return 2

    async def p_rc(bb, s):          # (a) refcounts must all be zero under the latch
        await wr(bb, s["Page_Frames"] + 2, 1, 2)          # frame 0 pf_refcount = 1

    async def p_ident(bb, s):       # (c) Page_Table must still be the identity
        await wr(bb, s["Page_Table"] + 3, 5, 1)           # page 3 -> frame 5

    async def p_dangle(bb, s):      # (b) no cache word may name an unassigned frame
        await wr(bb, s["Page_Frames"] + 8 * 1, 0xFFFF, 2)  # frame 1 pf_page = UNASSIGNED
        # frame 1 is the heavily referenced one (rc 168 in the general regime), so the
        # nametable certainly holds words whose physical index lands in it

    def p_word(index):              # (b), ONE word: the slice walk's own subject
        async def poke(bb, s):
            addr = s["Tile_Cache_Nametable"] + 2 * index
            word = (free << TILE_SHIFT) | 1                   # tile 1 of the unassigned frame
            await wr(bb, addr, word, 2)
            back = await rdw(bb, addr, 2)
            if back != word:
                print(f"COULD NOT RUN: nametable word {index} read back ${back:04X}")
                raise SystemExit(2)
        return poke

    async def p_general(bb, s):     # the general regime's interval-tick whole walk
        await wr(bb, s["PageCache_Direct_Map"], 0, 1)
        # the latched copy loops wrote no refcounts, so every referenced frame now
        # disagrees with its count: only the general arm's comparison can raise

    ok &= (await case(b, sym, "CONTROL (no poke)", None, expect_halt=False))[0]
    ok &= (await case(b, sym, "(a) nonzero pf_refcount", p_rc))[0]
    ok &= (await case(b, sym, "(b) unassigned frame referenced", p_dangle))[0]
    ok &= (await case(b, sym, "(c) Page_Table not the identity", p_ident))[0]
    ok &= (await case(b, sym, "(b1) one dangling word, first slice", p_word(0), bound=WORD_BOUND))[0]
    ok &= (await case(b, sym, "(b2) one dangling word, last slice", p_word(NT_WORDS - 1), bound=WORD_BOUND))[0]
    ok &= (await case(b, sym, "(g) general regime forced: refcount sum", p_general))[0]
    await b.close()
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin"); ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    lst = str(Path(a.lst).resolve()); sym = parse_lst(lst)
    with headless_emulator(str(Path(a.rom).resolve())) as sock:
        rc = asyncio.run(sweep(sock, lst, sym))
    print("RESULT:", {0: "every arm is LIVE within the latency bound (control kept running)",
                      1: "AT LEAST ONE ARM IS VACUOUS OR LATE",
                      2: "COULD NOT RUN"}[rc])
    return rc


sys.exit(main())
