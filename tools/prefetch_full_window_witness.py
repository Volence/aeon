#!/usr/bin/env python3
"""Prefetch-at-full-window witness: fill the art window to PAGE_FRAMES of PAGE_FRAMES and prefetch.

WHY IT EXISTS (PREFETCH-THRASH-AT-FULL-WINDOW, 2026-09-27; ARCH §9.7). The bake admits a camera
window that needs exactly PAGE_FRAMES art pages, and the woven clip act `s2_mtz_cpz` has 2,792
of them (Chemical Plant's right half). At such a window every page frame is named by a tile-cache
word, so a PREFETCH of an ahead-strip page finds no free or evictable frame. The engine used to
treat that as the thrash bug: `PageCache_AllocFrame` raise_errored in DEBUG (release re-queued
the prefetch and paid a forced full liveness sweep on every retry). A prefetch is speculative;
the fix drops it (PageIn_Process .alloc_fail, counted in DEBUG by Dbg_PageIn_PfxNoFrame) and
keeps the halt for a DEMAND or BULK request, where no frame is a real error. This witness drives
both halves in the DEBUG clip ROM.

THE DRIVE IS DERIVED, NOT TYPED. The clip's own baked tree (games/sonic4/data/clips/s2_mtz_cpz/
baked, written by the S2CLIP build) is counted through fg_page_order's window count, the one the
bake's N1/N2 verdicts use: the windows needing exactly PAGE_FRAMES pages, the camera row
holding the most of them (the median such row on a tie), and the x span they cover. The drive
flies that row left to right from 256 px before the span to 64 px past it, in DEBUG free flight,
RIGHT held one frame in TAP (a slow flight: 16 px a tick every TAP-th frame). WHY SLOW, MEASURED
on the pre-fix DEBUG clip ROM (crc 18d1542b): flown at full speed (RIGHT held) at camera y 1088
the band was crossed with no halt (a prefetch was queued at 3 full-window frame boundaries but
never dequeued there); at one frame in three, camera y 1188 and 988 both halted, and this
derived drive (camera y 1104) halts at its frame 197. Physics does not matter here (the subject
is the camera), so the player stays in free flight; the placement is the WARP MAILBOX, never a
bare camera write.

TWO ARMS, each on a FRESH private headless `oracle-aether` (tools/aether_instance.py):
  A  prefetch at a full window. PASS: the leg flew without a halt, the residency invariant
     held on every frame (every tile-cache word names an assigned frame whose page maps back
     to it; frame 0 is the blank word and exempt), a FULL WINDOW was observed (every one of
     PAGE_FRAMES frames assigned and named by some cache word, read off the nametable itself,
     not the engine's masks), and Dbg_PageIn_PfxNoFrame advanced (the drop arm ran).
     FAIL (1): a halt (the old code: "PageCache_AllocFrame: no free/evictable frame (thrash
     bug)"), or an invariant violation (a drop that evicted a live frame would show here as
     corrupt art).
  B  a demand at a full window still halts. The same flight, stopped at the first frame the
     window is full; at PageIn_Process's entry (run_to, so nothing is mid-dequeue) a DEMAND
     request for a non-resident page is appended to the page-in FIFO with its claim bit set,
     exactly as PageIn_Enqueue writes one. No frame is free or evictable, so the engine must
     halt with the thrash message. FAIL (1): it did not halt within B_FRAMES, or halted with
     another message: the demand path lost its halt, which the fix must never do.
A leg that cannot fail is not a leg: every precondition above that is not met is UNMEASURABLE
(2), never a pass, and so is a ROM whose pool page count differs from the baked tree's.

Exit: 0 both arms held; 1 an arm FAILED; 2 UNMEASURABLE / COULD NOT RUN.
Usage (spawns its own emulators):
  DEBUG=1 S2CLIP=s2_mtz_cpz ./build.sh
  python3 tools/prefetch_full_window_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst
Wired: tools/keepalive_manifest.toml (tools/nightly_instrument_keepalive.sh builds DEBUG
S2CLIP=s2_mtz_cpz and keeps it as s4.s2clip_mtz.debug.bin/.lst). Not in tools/landing_build.sh,
which builds no clip shape.
"""
import argparse
import asyncio
import os
import re
import sys
import zlib
from pathlib import Path

import numpy as np

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance, SpawnError, run_to_addr  # noqa: E402
from cart_identity import CartMismatch  # noqa: E402
from stressart_legs_witness import (Unmeasurable, sym, rd, listing_labels,  # noqa: E402
                                    nearest_label, raise_message)
import clip_act_bake  # noqa: E402
import fg_page_order as fpo  # noqa: E402

BAKED = os.path.join(AEON, "games/sonic4/data/clips/s2_mtz_cpz/baked")
BOOT_FRAMES = 300
TAP = 3                 # RIGHT held on one frame in TAP
LEAD_PX, TAIL_PX = 256, 64
MAX_FRAMES = 900        # the derived span is ~1,100 px: ~210 frames at 16 px every 3rd frame
HALT_FRAMES = 60        # one second with no completed logic tick (a lag frame misses one)
B_FRAMES = 240          # arm B: frames allowed for the injected demand to reach AllocFrame
THRASH_TEXT = "no free/evictable frame"
EQUS = ("PAGE_FRAMES", "PAGE_FRAME_TILE_SHIFT", "PAGE_NOT_RESIDENT", "PGRQ_DEMAND",
        "PAGEIN_QUEUE_SLOTS", "TILE_CACHE_COLS", "TILE_CACHE_ROWS", "NT_TILE_MASK")
SYMS = ("Logic_Tick", "Camera_X", "Camera_Y", "Page_Table", "PageIn_Pool_Pages", "Page_Frames",
        "Tile_Cache_Nametable", "PageIn_Queue_Count", "PageIn_Queue", "Page_Queued_Bits",
        "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "PageIn_Process", "ErrorHandlerBlob")
COUNTER = "Dbg_PageIn_PfxNoFrame"


def listing_equs(lst):
    out = {}
    for m in re.finditer(r"^EQU (\w+) = \$([0-9A-F]+)$", Path(lst).read_text(errors="replace"), re.M):
        out.setdefault(m.group(1), int(m.group(2), 16))
    return out


def derive_drive(baked):
    """(camera y, camera x from, camera x to, windows at PAGE_FRAMES, pool pages) off the tree."""
    try:
        pg, pins, n_pages = clip_act_bake.page_grid_from_tree(baked)
    except (OSError, clip_act_bake.ClipBakeError) as e:
        raise Unmeasurable(f"the clip's baked tree at {baked} could not be read ({e}); build "
                           f"`DEBUG=1 S2CLIP=s2_mtz_cpz ./build.sh` first")
    c = fpo.load_budget_constants()
    H, W = pg.shape
    lefts, tops, _, _ = fpo.camera_windows(c, W, H)
    needed, _ = fpo.window_needed(pg, n_pages, pins, c, lefts, tops)
    F = c["PAGE_FRAMES"]
    ti, li = np.nonzero(needed == F)
    if len(ti) == 0:
        raise Unmeasurable(f"no camera window of this act needs {F} pages: the act cannot fill "
                           f"the window, so there is nothing to witness")
    per_row = np.bincount(ti, minlength=len(tops))
    best = np.flatnonzero(per_row == per_row.max())
    row = int(best[len(best) // 2])
    cols = li[ti == row]
    to_px = lambda left, margin: (left + margin) * 8  # noqa: E731 - budget_verdict's own map
    cam_y = to_px(int(tops[row]), c["TILE_CACHE_MARGIN_V"])
    x0 = to_px(int(lefts[cols.min()]), c["TILE_CACHE_MARGIN_H"])
    x1 = to_px(int(lefts[cols.max()]), c["TILE_CACHE_MARGIN_H"])
    return cam_y, x0, x1, int(len(ti)), n_pages, F


async def flight(b, s, e, drive, arm, image, labels):
    cam_y, x0, x1, _n, _pages, F = drive
    u = lambda bb: int.from_bytes(bb, "big")  # noqa: E731

    async def wr(addr, v, n):
        await b.call("emulator/write_memory", {"addr": hex(addr & 0xFFFFFF),
                                               "bytes": "0x" + v.to_bytes(n, "big").hex()})

    async def halted_report(f, what):
        st = await b.call("emulator/status", {})
        pc = int(str(st.get("pc", "0")), 16) & 0xFFFFFF
        msgs = await raise_message(b, image)
        print(f"  HALT ({what}), frame {f}: Logic_Tick unchanged for {HALT_FRAMES} frames, pc "
              f"${pc:06X} ({'in' if pc >= s['ErrorHandlerBlob'] else 'NOT in'} the fault island)")
        for site, m in msgs:
            print(f"    raise_error at ${site:06X} ({nearest_label(labels, site)}): {m!r}")
        if not msgs:
            print("    raise_error message: none recovered from RAM")
        return [m for _, m in msgs]

    await b.call("emulator/run_frames", {"frames": BOOT_FRAMES})
    pool = u(await rd(b, s["PageIn_Pool_Pages"], 2))
    if pool != drive[4]:
        raise Unmeasurable(f"the ROM's pool has {pool} pages, the baked tree {drive[4]}: the tree "
                           f"does not describe this ROM")
    px, py = x0 - LEAD_PX + 160, cam_y + 112
    await wr(s["Warp_Req_X"], px, 2)
    await wr(s["Warp_Req_Y"], py, 2)
    await wr(s["Warp_Req_Flag"], 1, 1)
    for _ in range(120):
        await b.call("emulator/run_frames", {"frames": 1})
        if (await rd(b, s["Warp_Req_Flag"], 1))[0] == 0:
            break
    else:
        raise Unmeasurable("the warp mailbox was never acknowledged (is this the DEBUG shape?)")
    await b.call("emulator/run_frames", {"frames": 30})
    c0 = u(await rd(b, s[COUNTER], 2)) if COUNTER in s else None
    prev, still, full, bad, cx = u(await rd(b, s["Logic_Tick"], 4)), 0, 0, 0, 0
    nt_bytes = e["TILE_CACHE_COLS"] * e["TILE_CACHE_ROWS"] * 2
    shift, tmask = e["PAGE_FRAME_TILE_SHIFT"], e["NT_TILE_MASK"]
    for f in range(1, MAX_FRAMES + 1):
        await b.call("emulator/hold", {"buttons": ["right"], "down": f % TAP == 1})
        await b.call("emulator/run_frames", {"frames": 1})
        t = u(await rd(b, s["Logic_Tick"], 4))
        still = still + 1 if t == prev else 0
        prev = t
        if still >= HALT_FRAMES:
            msgs = await halted_report(f - HALT_FRAMES, "arm A")
            return {"halt": msgs}
        cx = u(await rd(b, s["Camera_X"], 4)) >> 16
        frames_rec = await rd(b, s["Page_Frames"], F * 8)
        table = await rd(b, s["Page_Table"], pool)
        nt = b"".join([await rd(b, s["Tile_Cache_Nametable"] + o, min(3200, nt_bytes - o))
                       for o in range(0, nt_bytes, 3200)])
        named = {((nt[i] << 8 | nt[i + 1]) & tmask) >> shift for i in range(0, nt_bytes, 2)}
        assigned = [u(frames_rec[k * 8:k * 8 + 2]) for k in range(F)]
        for fr in named - {0}:
            pg = assigned[fr] if fr < F else 0xFFFF
            if pg == 0xFFFF or pg >= pool or table[pg] != fr:
                bad += 1
                if bad <= 5:
                    print(f"  INVARIANT: frame {f}, camera x {cx}: a cache word names frame {fr} "
                          f"(pf_page {pg:#06x}, Page_Table {table[pg] if pg < pool else '-'})")
        is_full = all(a != 0xFFFF for a in assigned) and named >= set(range(F))
        if is_full:
            full += 1
            if arm == "B":
                await b.call("emulator/hold", {"buttons": ["right"], "down": False})
                return await inject_demand(b, s, e, pool, f, cx, halted_report, u, wr)
        if cx >= x1 + TAIL_PX:
            break
    await b.call("emulator/hold", {"buttons": ["right"], "down": False})
    c1 = u(await rd(b, s[COUNTER], 2)) if COUNTER in s else None
    return {"halt": None, "frames": f, "cam_x": cx, "full": full, "bad": bad,
            "drops": None if c0 is None else (c1 - c0) & 0xFFFF}


async def inject_demand(b, s, e, pool, f, cx, halted_report, u, wr):
    table = await rd(b, s["Page_Table"], pool)
    cands = [p for p in range(pool) if table[p] == e["PAGE_NOT_RESIDENT"]]
    await run_to_addr(b, s["PageIn_Process"], "PageIn_Process", 60)
    n = (await rd(b, s["PageIn_Queue_Count"], 1))[0]
    bits = await rd(b, s["Page_Queued_Bits"], pool // 8 + 1)
    cands = [p for p in cands if not bits[p >> 3] & (1 << (p & 7))]
    if not cands or n >= e["PAGEIN_QUEUE_SLOTS"]:
        raise Unmeasurable(f"arm B: no unclaimed non-resident page ({len(cands)}) or a full FIFO "
                           f"({n}) at the full window (frame {f}, camera x {cx})")
    page = cands[0]
    await wr(s["PageIn_Queue"] + 4 * n, (page << 16) | (e["PGRQ_DEMAND"] << 8), 4)
    await wr(s["PageIn_Queue_Count"], n + 1, 1)
    await wr(s["Page_Queued_Bits"] + (page >> 3), bits[page >> 3] | (1 << (page & 7)), 1)
    print(f"  arm B: window full at frame {f} (camera x {cx}); DEMAND for page {page} appended "
          f"at FIFO slot {n}")
    prev, still = u(await rd(b, s["Logic_Tick"], 4)), 0
    for k in range(1, B_FRAMES + HALT_FRAMES + 1):
        await b.call("emulator/run_frames", {"frames": 1})
        t = u(await rd(b, s["Logic_Tick"], 4))
        still = still + 1 if t == prev else 0
        prev = t
        if still >= HALT_FRAMES:
            return {"halt": await halted_report(k - HALT_FRAMES, "arm B"), "full": 1}
    table = await rd(b, s["Page_Table"], pool)
    return {"halt": None, "full": 1, "b_page": page,
            "b_resident": table[page] != e["PAGE_NOT_RESIDENT"]}


def run_arm(rom, lst, image, labels, e, drive, arm):
    inst = AetherInstance(str(rom), symbols=str(lst))
    try:
        sock = inst.start()

        async def go():
            b = BusClient(socket_path=sock, client_id=f"pfw{arm}", client_name="prefetch-full-window")
            await b.connect()
            try:
                s = {n: await sym(b, n) for n in SYMS}
                try:
                    s[COUNTER] = await sym(b, COUNTER)
                except Unmeasurable:
                    pass  # a ROM before the fix: arm A still grades its halt
                return await flight(b, s, e, drive, arm, image, labels)
            finally:
                await b.close()
        return asyncio.run(go())
    finally:
        inst.reap()


def grade_a(r):
    if r["halt"] is not None:
        return 1, "FAIL: arm A HALTED on a prefetch at a full window" + (
            f" ({r['halt'][0]!r})" if r["halt"] else "")
    print(f"  arm A: {r['frames']} frames, camera x now {r['cam_x']}; {r['full']} frame(s) with "
          f"every frame named (full window); {r['drops']} prefetch(es) dropped for want of a frame; "
          f"{r['bad']} invariant violation(s)")
    if r["bad"]:
        return 1, "FAIL: arm A saw a cache word naming a frame whose page left (a live frame evicted)"
    if r["full"] == 0:
        return 2, "UNMEASURABLE: arm A never observed a full window; the drive did not reach the subject"
    if r["drops"] is None:
        return 2, f"UNMEASURABLE: arm A: no halt, but the ROM has no {COUNTER} to show the drop ran"
    if r["drops"] == 0:
        return 2, "UNMEASURABLE: arm A: no prefetch was dropped, so the arm under test never ran"
    return 0, "PASS: arm A"


def grade_b(r):
    if r["halt"] is None:
        return 1, (f"FAIL: arm B: a DEMAND at a full window did not halt in {B_FRAMES} frames "
                   f"(page {r.get('b_page')} resident afterwards: {r.get('b_resident')}); the "
                   f"demand path lost its thrash halt")
    if not any(THRASH_TEXT in m for m in r["halt"]):
        return 1, f"FAIL: arm B halted, but not on the thrash raise: {r['halt']!r}"
    return 0, "PASS: arm B (the demand halted on the thrash raise)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.s2clip.debug.bin"))
    ap.add_argument("--lst", default=os.path.join(AEON, "s4.s2clip.debug.lst"))
    ap.add_argument("--baked", default=BAKED)
    ap.add_argument("--arm", choices=("A", "B", "both"), default="both")
    a = ap.parse_args()
    rom, lst = Path(a.rom).resolve(), Path(a.lst).resolve()
    for label, q in (("ROM", rom), ("listing", lst)):
        if not q.is_file():
            print(f"UNMEASURABLE: no {label} at {q}. Build `DEBUG=1 S2CLIP=s2_mtz_cpz ./build.sh`.")
            print("finished=0")
            return 2
    image = rom.read_bytes()
    labels = listing_labels(lst)
    e = listing_equs(lst)
    missing = [n for n in EQUS if n not in e]
    if missing:
        print(f"UNMEASURABLE: the listing carries no EQU for {missing}")
        print("finished=0")
        return 2
    try:
        drive = derive_drive(a.baked)
    except Unmeasurable as ex:
        print(f"UNMEASURABLE: {ex}")
        print("finished=0")
        return 2
    if drive[5] != e["PAGE_FRAMES"]:
        print(f"UNMEASURABLE: engine source says PAGE_FRAMES {drive[5]}, the ROM {e['PAGE_FRAMES']}")
        print("finished=0")
        return 2
    cam_y, x0, x1, n, pages, F = drive
    print(f"prefetch_full_window_witness: {rom.name} crc32 {zlib.crc32(image):08x}; derived: {n} "
          f"camera windows need {F} of {F} frames ({pages}-page pool); flight at camera y {cam_y}, "
          f"x {x0 - LEAD_PX}..{x1 + TAIL_PX} (band {x0}..{x1}), RIGHT one frame in {TAP}")
    arms = ("A", "B") if a.arm == "both" else (a.arm,)
    rcs = []
    for arm in arms:
        try:
            r = run_arm(rom, lst, image, labels, e, drive, arm)
            rc, line = (grade_a if arm == "A" else grade_b)(r)
        except (Unmeasurable, SpawnError, CartMismatch, RuntimeError) as ex:
            rc, line = 2, f"UNMEASURABLE: arm {arm}: {ex}"
        print(f"  {line}")
        rcs.append(rc)
    worst = 1 if 1 in rcs else (2 if 2 in rcs else 0)
    print({0: "PASS: every arm held", 1: "FAIL: an arm failed",
           2: "UNMEASURABLE: an arm could not be measured"}[worst])
    print(f"finished={len(rcs)}")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
