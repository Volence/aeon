#!/usr/bin/env python3
"""thrash_probe — WHICH blocks the tile cache decodes, per tick, on a leg (2026-09-28).

Research instrument for perf/oscillation-thrash, not a gate. It runs the 2026-09-27 EHZ probe
(ehz_run_probe.py: tick-keyed inputs, same leg vocabulary, same JSON) and adds, after EVERY video
frame, a read of the block staging table and the page table:

  Block_Stage_Keys[16] (u32 key = sec_x<<24 | sec_y<<16 | block_index), Block_Stage_Gen (u16,
  +1 per staging claim), the cache window (Cache_Left_Col/Head_Col/Top_Row/Bottom_Row),
  Cache_Spec_Blocked, Page_Table[0..PAGES) and Page_Evict_Gen.

WHY A PER-FRAME DIFF IS EXACT. A staging claim is TileCache_DecompressBlock: it takes the next
round-robin slot and overwrites that slot's key. One tick claims at most BLOCK_DECOMP_BUDGET (6)
slots of 16, so no slot is claimed twice between two reads, and a claim never re-stages a live
key (the DEBUG assert in TileCache_DecompressBlock). So the slots whose key changed between two
reads ARE the decodes between them, in round-robin order. The probe cross-checks the count
against the Block_Stage_Gen delta on every frame and reports any disagreement (an
InvalidateStaging bumps Gen with no claim; those frames are counted, not hidden).

Page loads: a Page_Table cell going PAGE_NOT_RESIDENT ($FF) -> frame is one page load.

Extra leg: THRASH_OSC="dirsA/dirsB:K" (env) turns --mode fly into an oscillation: hold dirsA
for K ticks, then dirsB for K ticks, repeating (tick-keyed like every other input here).
THRASH_OSC_AFTER="dirs:T" holds dirs for the first T ticks before the oscillation starts.

Output: <out>.thrash.json with per-frame rows [frame, tick, camx, camy, gen_delta, [new keys],
[pages loaded], evict_gen_delta, left, head, top, bottom, spec_blocked].
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-09-27-ehz-run-lag"))
import ehz_run_probe as ERP  # noqa: E402

REC = []
STATE = {}
SYMS = ["Block_Stage_Keys", "Block_Stage_Gen", "Cache_Left_Col", "Cache_Head_Col",
        "Cache_Top_Row", "Cache_Bottom_Row", "Cache_Spec_Blocked", "Page_Table",
        "Page_Evict_Gen", "PageCache_Direct_Map"]
PAGES = int(os.environ.get("THRASH_PAGES", "32"))

_orig_snap = ERP.snap
_orig_want = ERP.want


async def _mem(c, addr, n):
    r = await c.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    h = r["bytes"]
    h = h[2:] if h.lower().startswith("0x") else h
    return bytes.fromhex(h[:2 * n])


async def snap(c, s):
    cur = await _orig_snap(c, s)
    if "ts" not in STATE:
        STATE["ts"] = await ERP.syms(c, SYMS)
        missing = [n for n in SYMS if n not in STATE["ts"]]
        if missing:
            raise SystemExit(f"thrash_probe: symbols did not resolve: {missing}")
    t = STATE["ts"]
    keys = await _mem(c, t["Block_Stage_Keys"], 64)
    keys = [int.from_bytes(keys[i:i + 4], "big") for i in range(0, 64, 4)]
    gen = int.from_bytes(await _mem(c, t["Block_Stage_Gen"], 2), "big")
    edges = [int.from_bytes(await _mem(c, t[n], 2), "big") for n in
             ("Cache_Left_Col", "Cache_Head_Col", "Cache_Top_Row", "Cache_Bottom_Row")]
    spec = int.from_bytes(await _mem(c, t["Cache_Spec_Blocked"], 2), "big")
    ptab = list(await _mem(c, t["Page_Table"], PAGES))
    egen = int.from_bytes(await _mem(c, t["Page_Evict_Gen"], 2), "big")
    dmap = (await _mem(c, t["PageCache_Direct_Map"], 1))[0]
    prev = STATE.get("prev")
    if prev is not None:
        pk, pg, pp, pe = prev
        new = [keys[i] for i in range(16) if keys[i] != pk[i]]
        loaded = [p for p in range(PAGES) if pp[p] == 0xFF and ptab[p] != 0xFF]
        REC.append([len(REC), cur["lt"], cur["cx"], cur["cy"], (gen - pg) & 0xFFFF, new, loaded,
                    (egen - pe) & 0xFFFF, *edges, spec, dmap, cur["px"], cur["py"]])
    STATE["prev"] = (keys, gen, ptab, egen)
    return cur


def want(mode, t, a):
    osc = os.environ.get("THRASH_OSC")
    if mode == "fly" and osc:
        pre = os.environ.get("THRASH_OSC_AFTER", "")
        if pre:
            pd, pt = pre.split(":")
            if t < int(pt):
                return set(pd.split(","))
            t -= int(pt)
        ab, k = osc.split(":")
        da, db = ab.split("/")
        return set((da if (t // int(k)) % 2 == 0 else db).split(","))
    return _orig_want(mode, t, a)


ERP.snap = snap
ERP.want = want


def main():
    out = sys.argv[sys.argv.index("--out") + 1]
    try:
        ERP.main()
    finally:
        Path(out + ".thrash.json").write_text(json.dumps(dict(
            osc=os.environ.get("THRASH_OSC"), osc_after=os.environ.get("THRASH_OSC_AFTER"),
            cols=["i", "lt", "cx", "cy", "gen_d", "new_keys", "pages_loaded", "evict_d",
                  "left", "head", "top", "bottom", "spec_blocked", "direct_map", "px", "py"],
            rows=REC)))


if __name__ == "__main__":
    main()
