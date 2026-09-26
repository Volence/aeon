#!/usr/bin/env python3
"""Poison test for PageCache_Audit: its latched (DIRECT-MAP) arm, its general-regime
liveness-mask check, its demand-hold checks, and its per-tick amortised schedule.

A check that cannot fail is not a check, so each invariant is violated in turn and the
engine must STOP (raise_error -> error handler; Frame_Counter and Logic_Tick freeze).
Each control pokes nothing wrong and must keep running.

LATCHED ARMS (the booted canonical act is latched). (a)/(a2) every row / column liveness
mask keeps its reset value under the latch (GPL-A3, 2026-09-27; it was "every refcount
is zero" before the masks replaced the refcounts; checked per audit slice, so its bound
is the per-word one), (b) no cache word names an unassigned frame, (c) Page_Table is the
identity.

AMORTISED SINCE 2026-09-26. The nametable half of the audit is audited in paced slices
by VSync_Wait's idle slot. So (b1)/(b2) plant ONE dangling word at the first and at the
last nametable word, and every arm measures its DETECTION LATENCY in logic ticks, poke
to halt. The bounds are derived from source, not copied: every frame-level check runs
once per PAGECACHE_AUDIT_INTERVAL ticks (engine/system/constants.emp), and a nametable
word is audited once per interval at its slice's phase give or take
PAGE_AUDIT_SLACK_TICKS (engine/level/page_cache.emp), so a corruption that stays put is
caught within INTERVAL, resp. INTERVAL + SLACK, ticks. A halt later than that, or no
halt, FAILS.

GENERAL-REGIME ARMS (g*), GPL-A3. They force PageCache_Direct_Map to 0 on the booted
act. The latched runs kept no liveness, so the tool first does what
PageCache_EndBoundedRegime does at the real flip: it makes the masks a valid superset
(every row mask = every frame, every column mask empty). Without that, every non-blank
word would fail the mask check and the arms would prove nothing about the planted word
(that was the old arm (g)'s trap once the refcount sum left). Then:
  (g0)  CONTROL: nothing else. Must keep running (the idle liveness sweep shrinks the
        masks to exact meanwhile, so this also runs the sweep against the audit).
  (g1)  one word naming an UNASSIGNED frame. Must halt with the "UNASSIGNED" message.
  (g2)  one word naming an ASSIGNED frame that its row mask omits (column mask empty):
        a barrier that missed a write. Must halt with the "masks both omit" message.
  (g3)  CONTROL for the column half: the same word and the same row omission, but
        every COLUMN mask carries the frame. Must keep running (an audit that ignored
        the column masks would halt here).
The idle sweep re-derives masks exactly, so it would HEAL (g2)'s omission within a few
frames (that is what it is for). (g2)/(g3) therefore plant in the NEXT slice the audit
will read (Page_Audit_Slice), and poke at a frame boundary: the next frame's audit
reads that slice in the idle slot BEFORE the sweep runs (VSync_Wait's order). Each
halting arm also recovers the raise_error message from RAM and requires the expected
one, so the two general messages are proven distinct, not just "something halted".

DEMAND-HOLD ARMS (stressart-halts GPL-2). (h) a hold with the gate disarmed halts; (hr)
an armed hold does NOT halt and PageCache_DemandHoldTick releases it: flag clear, gate
0, and (no liveness mask names the frame on a latched act) its stamp moved to the
release time. The old orphan arm (o) is RETIRED with the refcounts: it planted an
assigned, unpinned frame with no candidate flag, which under the masks is simply an
ordinary frame (a candidate the moment no mask names it); the only unreachable frame
left is a held one whose hold nothing ends, which is (h).

Exit: 0 every arm behaved within the bound; 1 otherwise; 2 COULD NOT RUN (a precondition
the arms need is not met — e.g. no unassigned frame to aim a dangling word at).
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


def message(fragment, src=PAGE_CACHE):
    """The one raise_error message in page_cache.emp containing `fragment`. Loud if it is
    not exactly one: an arm must name the message it proves, from source."""
    hits = re.findall(r'raise_error "([^"]*)"', src.read_text())
    hits = [h for h in hits if fragment in h]
    if len(hits) != 1:
        print(f"COULD NOT RUN: {len(hits)} raise_error messages contain {fragment!r} in {src}")
        raise SystemExit(2)
    return hits[0]


INTERVAL = const("PAGECACHE_AUDIT_INTERVAL")
# a nametable word is audited once per interval at its slice's phase, give or take the
# pacing slack, so its bound is INTERVAL + SLACK (page_cache.emp, PageCache_Audit LATENCY)
WORD_BOUND = INTERVAL + const("PAGE_AUDIT_SLACK_TICKS", PAGE_CACHE)
COLS, ROWS = const("TILE_CACHE_COLS"), const("TILE_CACHE_ROWS")
NT_WORDS = COLS * ROWS
SLICE_WORDS = const("PAGE_AUDIT_SLICE_WORDS", PAGE_CACHE)
SLICES = NT_WORDS // SLICE_WORDS
PF_SIZE = 8          # sizeof(PageFrame); page_cache.emp ensures it is 8 (`lsl #3` stride)
PF_STAMP_OFF = 4     # offsetof(PageFrame, pf_stamp): engine/structs.emp
PF_FLAGS_OFF = 7     # offsetof(PageFrame, pf_flags): engine/structs.emp, the last byte of 8
PF_PINNED = 1 << const("PF_PINNED_BIT")
PF_DEMAND_HELD = 1 << const("PF_DEMAND_HELD_BIT")
PAGE_HELD_NEW = const("PAGE_HELD_NEW", PAGE_CACHE)
TILE_SHIFT = 6       # PAGE_FRAME_TILE_SHIFT; constants.emp ensures 1 << 6 == ART_POOL_PAGE_TILES
MSG_LATCH_MASK = message("liveness mask left its reset value")
MSG_UNASSIGNED = message("general regime: a cache word names an UNASSIGNED frame")
MSG_UNMASKED = message("masks both omit")


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


async def raised_messages(b, rom):
    """Every raise_error message a long in work RAM points at (the `jsr <handler>` return
    address sits just past the jsr, and the message bytes follow it), as halt_probe.py and
    stressart_legs_witness.py recover it. Other stacked candidates can be stale; an arm
    requires ITS message among them."""
    ram = b""
    for off in range(0, 0x10000, 1024):
        r = await b.call("emulator/read_memory", {"addr": hex(0xFF0000 + off), "len": 1024})
        ram += bytes.fromhex(r["bytes"][:2048])
    found = []
    for off in range(0, len(ram) - 3, 2):
        v = int.from_bytes(ram[off:off + 4], "big")
        if 6 <= v < len(rom) - 4 and rom[v - 6:v - 4] == b"\x4e\xb9":
            txt = rom[v:v + 140].split(b"\0")[0]
            if len(txt) >= 12 and all(32 <= c < 127 for c in txt[:12]):
                t = txt.decode("latin1")
                if t not in found:
                    found.append(t)
    return found


async def case(b, sym, rom, name, poke, expect_halt=True, bound=INTERVAL, expect_msg=None):
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
    msg_note = ""
    if expect_halt:
        ok = halted and latency <= bound
        if halted and expect_msg is not None:
            got = await raised_messages(b, rom)
            named = expect_msg in got
            ok = ok and named
            msg_note = f"   message {'named' if named else 'NOT FOUND'} (candidates: {got})"
    else:
        ok = not halted
        if halted:
            msg_note = f"   (raised: {await raised_messages(b, rom)})"
    verdict = ("HALTED (audit raised)" if halted else "still running")
    lat = f" after {latency} ticks (bound {bound})" if halted else f" ({last - t0} ticks run)"
    print(f"  {name:48s} {verdict}{lat}   {'ok' if ok else 'FAIL'}{msg_note}")
    return ok, latency


async def sweep(sock, lst, sym, rom):
    b = BusClient(socket_path=sock, client_id="auditpoison", client_name="audit_poison")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    ok = True

    # Preconditions, read off the booted state rather than assumed: an UNASSIGNED frame to
    # aim a dangling word at, and an ASSIGNED, UNPINNED frame for the hold arms.
    await boot(b)
    direct = await rdw(b, sym["PageCache_Direct_Map"], 1)
    free = None
    assigned = []
    for f in range(16):
        if await rdw(b, sym["Page_Frames"] + PF_SIZE * f, 2) == 0xFFFF:
            free = f if free is None else free
        else:
            assigned.append(f)
    unpinned = None
    for f in assigned:
        flags = await rdw(b, sym["Page_Frames"] + PF_SIZE * f + PF_FLAGS_OFF, 1)
        if not flags & PF_PINNED:
            unpinned = f
            break
    named = [f for f in assigned if f != 0]
    print(f"  booted: PageCache_Direct_Map=${direct:02X}, first unassigned frame = {free}, "
          f"assigned frames = {assigned}, first assigned unpinned frame = {unpinned}, "
          f"nametable {NT_WORDS} words in {SLICES} slices, interval {INTERVAL} ticks")
    if direct == 0 or free is None or unpinned is None or not named:
        print("COULD NOT RUN: the arms need a latched regime, an unassigned frame, an "
              "assigned unpinned frame and an assigned frame other than 0")
        await b.close()
        return 2
    f_named = named[0]                  # an assigned frame the (g2)/(g3) word names
    masks = sym["Page_Live_Masks"]
    col_masks = masks + 2 * ROWS         # PAGE_LIVE_COL_OFFSET: the rows, then the columns

    async def p_mask(bb, s):        # (a) a ROW liveness mask moved under the latch
        await wr(bb, masks + 2 * 5, 0x0003, 2)            # row 5 now also names frame 1

    async def p_colmask(bb, s):     # (a2) a COLUMN liveness mask moved under the latch
        await wr(bb, col_masks + 2 * (COLS - 1), 0x0002, 2)   # the last column now names frame 1

    async def p_ident(bb, s):       # (c) Page_Table must still be the identity
        await wr(bb, s["Page_Table"] + 3, 5, 1)           # page 3 -> frame 5

    async def p_dangle(bb, s):      # (b) no cache word may name an unassigned frame
        await wr(bb, s["Page_Frames"] + 8 * 1, 0xFFFF, 2)  # frame 1 pf_page = UNASSIGNED
        # frame 1 is heavily named, so the nametable certainly holds words that land in it

    def p_word(index, frame=None):  # ONE word: the slice walk's own subject
        async def poke(bb, s):
            addr = s["Tile_Cache_Nametable"] + 2 * index
            word = ((free if frame is None else frame) << TILE_SHIFT) | 1   # tile 1 of that frame
            await wr(bb, addr, word, 2)
            back = await rdw(bb, addr, 2)
            if back != word:
                print(f"COULD NOT RUN: nametable word {index} read back ${back:04X}")
                raise SystemExit(2)
        return poke

    flags_at = sym["Page_Frames"] + PF_SIZE * unpinned + PF_FLAGS_OFF
    stamp_at = sym["Page_Frames"] + PF_SIZE * unpinned + PF_STAMP_OFF

    async def p_held_disarmed(bb, s):   # a demand hold nothing will ever end
        await wr(bb, flags_at, PF_DEMAND_HELD, 1)         # held, while Page_Demand_Held stays 0

    async def p_held_armed(bb, s):  # a demand hold the fill must END (control + behaviour)
        await wr(bb, flags_at, PF_DEMAND_HELD, 1)
        await wr(bb, stamp_at, 0, 2)                      # so a release's stamp is visible
        await wr(bb, s["Page_Demand_Held"], PAGE_HELD_NEW, 1)   # as PageCache_Publish leaves it

    async def force_general(bb, s):
        """What PageCache_EndBoundedRegime establishes at the real flip: the general loop
        and masks that are a superset of every cell (all frames in every row)."""
        await wr(bb, s["PageCache_Direct_Map"], 0, 1)
        for r in range(ROWS):
            await wr(bb, masks + 2 * r, 0xFFFF, 2)
        for c in range(COLS):
            await wr(bb, col_masks + 2 * c, 0x0000, 2)

    async def next_slice(bb, s):
        """The slice the audit reads next, stepping frames until one is left this interval."""
        for _ in range(64):
            sl = await rdw(bb, s["Page_Audit_Slice"], 2)
            if sl < SLICES:
                return sl
            await bb.call("emulator/run_frames", {"frames": 1})
        print("COULD NOT RUN: Page_Audit_Slice never came back below the slice count")
        raise SystemExit(2)

    async def p_general(bb, s):     # (g0) the valid general state
        await force_general(bb, s)

    async def p_general_dangle(bb, s):  # (g1)
        await force_general(bb, s)
        sl = await next_slice(bb, s)
        await p_word(sl * SLICE_WORDS)(bb, s)

    def p_general_unmasked(col_carries):  # (g2) / (g3)
        async def poke(bb, s):
            await force_general(bb, s)
            sl = await next_slice(bb, s)
            row = sl // 2                                # a slice is half a row (ensure'd)
            await p_word(sl * SLICE_WORDS, f_named)(bb, s)
            await wr(bb, masks + 2 * row, 0xFFFF & ~(1 << f_named), 2)
            if col_carries:
                # EVERY column carries the frame, so every cell of that row naming it (the
                # planted one and any the act drew there) is covered by its column alone
                for c in range(COLS):
                    await wr(bb, col_masks + 2 * c, 1 << f_named, 2)
        return poke

    ok &= (await case(b, sym, rom, "CONTROL (no poke)", None, expect_halt=False))[0]
    ok &= (await case(b, sym, rom, "(a) row liveness mask moved under the latch", p_mask,
                      bound=WORD_BOUND, expect_msg=MSG_LATCH_MASK))[0]
    ok &= (await case(b, sym, rom, "(a2) column liveness mask moved under the latch", p_colmask,
                      bound=WORD_BOUND, expect_msg=MSG_LATCH_MASK))[0]
    ok &= (await case(b, sym, rom, "(b) unassigned frame referenced", p_dangle))[0]
    ok &= (await case(b, sym, rom, "(c) Page_Table not the identity", p_ident))[0]
    ok &= (await case(b, sym, rom, "(b1) one dangling word, first slice", p_word(0), bound=WORD_BOUND))[0]
    ok &= (await case(b, sym, rom, "(b2) one dangling word, last slice", p_word(NT_WORDS - 1), bound=WORD_BOUND))[0]
    ok &= (await case(b, sym, rom, "(g0) general regime forced, valid masks: CONTROL", p_general,
                      expect_halt=False))[0]
    ok &= (await case(b, sym, rom, "(g1) general: word names an unassigned frame", p_general_dangle,
                      bound=WORD_BOUND, expect_msg=MSG_UNASSIGNED))[0]
    ok &= (await case(b, sym, rom, "(g2) general: frame in neither mask", p_general_unmasked(False),
                      bound=WORD_BOUND, expect_msg=MSG_UNMASKED))[0]
    ok &= (await case(b, sym, rom, "(g3) general: row omits, column carries: CONTROL",
                      p_general_unmasked(True), expect_halt=False))[0]
    # Demand-hold arms (STRESSART-HALTS GPL-2 fix). (h) must halt. (hr) must NOT: an armed
    # hold is legitimate, and PageCache_DemandHoldTick must RELEASE it (the idle fill never
    # stalls): after the run the frame is no longer held, the gate is 0, and — no mask
    # names the frame under the latch — its stamp moved off the 0 planted with the hold.
    ok &= (await case(b, sym, rom, "(h) demand hold with the gate disarmed", p_held_disarmed))[0]
    rel_ok, _ = await case(b, sym, rom, "(hr) armed demand hold, must be released", p_held_armed,
                           expect_halt=False)
    fl = await rdw(b, flags_at, 1)
    gate = await rdw(b, sym["Page_Demand_Held"], 1)
    stamp = await rdw(b, stamp_at, 2)
    released = rel_ok and not fl & PF_DEMAND_HELD and gate == 0 and stamp != 0
    print(f"  {'   (hr) after the run: flags $%02X, gate %d, stamp $%04X' % (fl, gate, stamp):48s} "
          f"{'released' if released else 'NOT released'}   {'ok' if released else 'FAIL'}")
    ok &= bool(released)
    await b.close()
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin"); ap.add_argument("--lst", default="s4.debug.lst")
    a = ap.parse_args()
    lst = str(Path(a.lst).resolve()); sym = parse_lst(lst)
    rom = Path(a.rom).read_bytes()
    with headless_emulator(str(Path(a.rom).resolve())) as sock:
        rc = asyncio.run(sweep(sock, lst, sym, rom))
    print("RESULT:", {0: "every arm is LIVE within the latency bound (controls kept running)",
                      1: "AT LEAST ONE ARM IS VACUOUS OR LATE",
                      2: "COULD NOT RUN"}[rc])
    return rc


sys.exit(main())
