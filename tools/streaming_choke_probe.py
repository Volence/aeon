#!/usr/bin/env python3
"""streaming_choke_probe — decompose Tile_Cache_Fill's per-tick cost by CALLEE.

WHY THIS EXISTS. tools/engine_baseline_probe.py measured the top-level fact
(docs/benchmarks/scanline-p2/ENGINE-BASELINE.md): sustained max-diagonal runs at
2.067 video frames per logic tick, and `Tile_Cache_Fill` alone costs 106163 cyc/tick
(40.1% of a video frame). That row is INCLUSIVE and says nothing about WHERE inside
the fill the cycles go. This probe answers that, using the only decomposition the old
oracle profiler supports: every callee of the fill has its OWN per-routine row, so the
tree can be reconstructed by subtraction.

THE TREE (verified by grepping every `jbsr` in engine/ + games/, 2026-08-19):

    Tile_Cache_Fill
      +- TileCache_FillRow          (row fill; <=VFILL_ROWS_PER_FRAME per pass)
      |    +- TileCache_FindStagedBlock
      |    +- TileCache_DecompressBlock -> S4LZ_DecompressDict
      |    +- PageCache_PatchRun_Seq        (per nametable word)
      +- TileCache_FillColumn
      |    +- TileCache_FindStagedBlock
      |    +- TileCache_DecompressBlock -> S4LZ_DecompressDict
      |    +- TileCache_CopyBlockColumn
      |         +- PageCache_PatchRun_Col   (per nametable word)
      +- TileCache_HSlide / VSlide / VSlideUp
      +- (inline prefetch scans) -> FindStagedBlock / DecompressBlock

    PageCache_Audit is NO LONGER IN THAT TREE (fix F5, 2026-08-19). It was a child of
    Tile_Cache_Fill until the gate moved out to the level state's tick, where it is now
    a SIBLING of the fill under GameState_OJZScroll_Update. Its row is still printed —
    below the tree, at depth 0 — because the one-shot's cost is worth seeing; it just is
    not part of the fill's decomposition any more, and must never be subtracted from it.

SOLE-PARENT FACTS THAT MAKE THE SUBTRACTION HONEST. A per-routine row aggregates over
ALL parents, so a callee with two live parents cannot be attributed by row alone. On
this ROM, in this game state:
  * DecompressBlock, CopyBlockColumn, PatchRun_Seq, PatchRun_Col, S4LZ_DecompressDict
    and the three slides have exactly ONE live parent each (init-time callers do not
    run inside the sample).
  * FindStagedBlock has a SECOND caller, PageCache_Prefetch (page_cache.emp:677,708).
    That routine early-outs on `PageIn_Fully_Resident` and OJZ act 1 is fully resident
    (10 pages against PAGE_FRAMES=15), so the second parent contributes ZERO. This
    probe READS PageIn_Fully_Resident and prints it; if it is ever 0, the FindStagedBlock
    attribution below is not sole-parent and must not be split by parent.

INCLUSIVE-ROW CHECK, NOT ASSUMED. Whether oracle's rows are inclusive or exclusive
changes every derivation here, so it is TESTED rather than believed: the probe prints
sum(direct children) against the parent row and labels the arithmetic. Inclusive rows
give sum(children) <= parent with a positive "own" residue; exclusive rows would give a
residue near the parent row itself and children summing far past it.

STATES. `idle` and `maxdiag` are byte-identical in setup to engine_baseline_probe's
(same settle, same lead, same one poke) so the rows here are directly comparable with
ENGINE-BASELINE.md. Two new SINGLE-AXIS states pin the scaling axes:
  `right`  poke x only  -> horizontal fill (columns) alone
  `down`   poke y only  -> vertical fill (rows) alone
Their sum against maxdiag is what separates per-axis cost from a diagonal interaction.

Every figure is an IDEAL CYCLE count (INSTRUMENT-PARITY.md caveat 0): oracle's clock
adds only cyclesExecuted to _currentCycle; bus/VDP/DMA stall lands in _currentTime and
reaches no row here.

Usage:
    python3 tools/streaming_choke_probe.py --rom s4.debug.bin --lst s4.debug.lst --repeat 3
    python3 tools/streaming_choke_probe.py --state maxdiag --dump   # every profiler row
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

HARNESS = "/home/volence/sonic_hacks/oracle-old/linux-port/harness"
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, HARNESS)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient            # noqa: E402
from launcher import headless_emulator   # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402

# ---- the brackets, then the streaming tree ---------------------------------
BRACKETS = [
    "GameState_OJZScroll_Update",   # the MAIN LOOP bracket — one call per LOGIC TICK
    "VInt_Level",
    "VInt_Lag",
    "VSync_Wait",
    "Camera_Update",
    "EntityWindow_Scan",
    "Section_UpdateColumns",
    "Parallax_Update",
]
# depth 1..3 under Tile_Cache_Fill, in tree order
TREE = [
    ("Tile_Cache_Fill", 0),
    ("TileCache_FillColumn", 1),
    ("TileCache_CopyBlockColumn", 2),
    ("PageCache_PatchRun_Col", 3),
    ("TileCache_FillRow", 1),
    ("PageCache_PatchRun_Seq", 2),
    ("TileCache_DecompressBlock", 1),
    ("S4LZ_DecompressDict", 2),
    ("S4LZ_Decompress", 2),
    ("TileCache_FindStagedBlock", 1),
    ("TileCache_HSlide", 1),
    ("TileCache_VSlide", 1),
    ("TileCache_VSlideUp", 1),
    ("PageCache_Request", 1),
    ("PageCache_Prefetch", 1),
    # depth 0 = NOT a child of the fill. Since F5 the periodic residency audit is
    # gated by the level state's tick, one call after Tile_Cache_Fill returns, so its
    # one-shot cost belongs to GameState_OJZScroll_Update and never to the fill.
    ("PageCache_Audit", 0),
]
ROUTINES = BRACKETS + [n for n, _ in TREE]

# direct children of each parent, for the inclusive-row check
CHILDREN = {
    # PageCache_Audit is deliberately ABSENT — F5 moved it out of the fill (see the
    # module docstring). Re-adding it here would make the inclusive check fail loudly,
    # which is the point: the tree and this map must not drift apart again.
    "Tile_Cache_Fill": ["TileCache_FillColumn", "TileCache_FillRow",
                        "TileCache_HSlide", "TileCache_VSlide", "TileCache_VSlideUp"],
    "TileCache_FillColumn": ["TileCache_CopyBlockColumn"],
    "TileCache_CopyBlockColumn": ["PageCache_PatchRun_Col"],
    "TileCache_FillRow": ["PageCache_PatchRun_Seq"],
    "TileCache_DecompressBlock": ["S4LZ_DecompressDict"],
}

# ---- engine counters sampled either side of the profiled window ------------
# Deltas over the sample say what the fill actually DID, independent of any cycle row.
WORD_COUNTERS = [
    "Frame_Counter", "Cache_Fill_Budget", "Cache_Fill_Rows_Left",
    "Cache_Art_Stall", "Cache_Stall_Watchdog", "Block_Stage_Next", "Block_Stage_Gen",
    "Cache_Fill_Resume_Col", "Cache_Fill_Resume_Row", "Cache_Fill_RowResume_Row",
    "Cache_Left_Col", "Cache_Head_Col", "Cache_Top_Row", "Cache_Bottom_Row",
    "Cache_Pfx_Lag_Flag", "Cache_Pfx_Skip_Armed", "Page_Audit_Ticks",
    "Pfx_Memo_Gen", "Cs_Memo_Gen", "Cache_Pfx_Row_Target", "Cache_Pfx_Col_Target",
    "Dbg_PageCache_Demands", "Dbg_PageCache_Prefetches",
    "Dbg_PageIn_Preempts", "Dbg_PageIn_Resumes", "Dbg_PageIn_Flushes",
    "Dbg_PageIn_PfxSkips", "Dbg_PageIn_Deferred", "Dbg_Cam_Clamp_Frames",
]
# counters whose DELTA is the interesting quantity (monotone counters)
DELTA_COUNTERS = ["Block_Stage_Gen", "Dbg_PageCache_Demands", "Dbg_PageCache_Prefetches",
                  "Dbg_PageIn_Preempts", "Dbg_PageIn_Resumes", "Dbg_PageIn_Flushes",
                  "Dbg_PageIn_PfxSkips", "Dbg_PageIn_Deferred", "Dbg_Cam_Clamp_Frames"]

SST_X_POS = 0x02
SST_Y_POS = 0x06
DIAG_AHEAD_X = 2000
DIAG_AHEAD_Y = 1400
CAM_MAX_STEP = 16

# state -> (poke_x, poke_y)
STATES = {
    "idle":    (0, 0),
    "maxdiag": (DIAG_AHEAD_X, DIAG_AHEAD_Y),
    "right":   (DIAG_AHEAD_X, 0),
    "down":    (0, DIAG_AHEAD_Y),
}


async def _read(b, addr, n):
    r = await b.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": n})
    return int(r["bytes"][:n * 2], 16)


async def _counters(b, sym):
    out = {}
    for n in WORD_COUNTERS:
        if n in sym:
            out[n] = await _read(b, sym[n], 2)
    for n in ("Logic_Tick", "Lag_Frame_Count", "Camera_X", "Camera_Y"):
        if n in sym:
            out[n] = await _read(b, sym[n], 4)
    for n in ("PageIn_Fully_Resident", "Camera_Art_Hold", "PageIn_Bulk_Drain",
              "PageCache_Direct_Map"):
        if n in sym:
            out[n] = await _read(b, sym[n], 1)
    return out


async def _one(b, sym, state, settle, lead, sample):
    ax, ay = STATES[state]
    await b.call("emulator/reset", {"wait": True, "run": False})
    await b.call("emulator/run_frames", {"frames": settle})

    if ax or ay:
        tgt = await _read(b, sym["Camera_Target"], 2)
        leader = 0xFF0000 | tgt if tgt & 0x8000 else tgt
        cam_x = (await _read(b, sym["Camera_X"], 4)) >> 16
        cam_y = (await _read(b, sym["Camera_Y"], 4)) >> 16
        if ax:
            await b.call("emulator/write_memory",
                         {"addr": hex((leader + SST_X_POS) & 0xFFFFFF),
                          "value": (cam_x + ax) << 16, "width": 4})
        if ay:
            await b.call("emulator/write_memory",
                         {"addr": hex((leader + SST_Y_POS) & 0xFFFFFF),
                          "value": (cam_y + ay) << 16, "width": 4})
        await b.call("emulator/run_frames", {"frames": lead})

    c0 = await _counters(b, sym)
    # THE SLEEPS ARE LOAD-BEARING: set_profiler only flips a flag; the GUI main loop is
    # what starts the CPU recording and drains the event ring into frame snapshots.
    await b.call("emulator/set_profiler", {"enabled": True})
    await asyncio.sleep(0.4)
    await b.call("emulator/run_frames", {"frames": sample})
    await asyncio.sleep(0.4)
    st = await b.call("emulator/get_profiler", {})
    prof = await b.call("emulator/get_profiler_frames", {"frames": sample, "top": 400})
    prof["frames_recorded"] = st.get("frames_recorded")
    await b.call("emulator/set_profiler", {"enabled": False})
    c1 = await _counters(b, sym)

    d_frames = (c1["Frame_Counter"] - c0["Frame_Counter"]) & 0xFFFF
    d_ticks = c1["Logic_Tick"] - c0["Logic_Tick"]
    dx = (c1["Camera_X"] - c0["Camera_X"]) / 65536.0
    dy = (c1["Camera_Y"] - c0["Camera_Y"]) / 65536.0
    return {
        "prof": prof, "c0": c0, "c1": c1,
        "frames": d_frames, "ticks": d_ticks,
        "frames_per_tick": (d_frames / d_ticks) if d_ticks else float("nan"),
        "dx": dx, "dy": dy,
        "deltas": {n: (c1.get(n, 0) - c0.get(n, 0)) & 0xFFFF for n in DELTA_COUNTERS},
    }


def rows_by_addr(prof, sym, names):
    by = {}
    for r in prof.get("routines", []):
        try:
            a = int(str(r.get("addr", "$0")).lstrip("$"), 16) & 0xFFFFFF
        except ValueError:
            continue
        by[a] = r
    return {n: by.get(sym[n] & 0xFFFFFF) for n in names if n in sym}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--lead", type=int, default=24)
    ap.add_argument("--sample", type=int, default=31)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--state", default="idle,maxdiag,right,down")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    sym = parse_lst(args.lst)
    states = [s for s in args.state.split(",") if s]
    for s in states:
        if s not in STATES:
            print(f"unknown state {s}", file=sys.stderr)
            return 3
    missing = [n for n, _ in TREE if n not in sym]
    if missing:
        print(f"symbols missing from {args.lst}: {', '.join(missing)}", file=sys.stderr)
        return 3

    results = {s: [] for s in states}

    async def _sweep(sock):
        b = BusClient(socket_path=sock, client_id="chokeprobe",
                      client_name="streaming_choke_probe")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        for s in states:
            r = await _one(b, sym, s, args.settle, args.lead, args.sample)
            if args.dump:
                print(json.dumps(r["prof"], indent=2))
                print(json.dumps({"c1": r["c1"], "deltas": r["deltas"]}, indent=2))
                await b.close()
                return
            results[s].append(r)
        await b.close()

    for _ in range(args.repeat):
        with headless_emulator(args.rom) as sock:
            asyncio.run(_sweep(sock))
        if args.dump:
            return 0

    print(f"ROM {args.rom}   sample {args.sample} frames   repeats {args.repeat}")
    print("per-routine rows, matched on the low 24 bits of the entry address.")
    print("interrupts.hint is HBlank + VBlank in this ROM and is NEVER read here.\n")

    table = {}
    for s in states:
        runs = results[s]
        r0 = runs[0]
        fpt = r0["frames_per_tick"]
        fr = r0["c1"].get("PageIn_Fully_Resident")
        print(f"== state {s}   {r0['frames']} video frames / {r0['ticks']} logic ticks"
              f" = {fpt:.3f} frames/tick   dx {r0['dx']:.0f} dy {r0['dy']:.0f} px"
              f"   PageIn_Fully_Resident {fr}   Camera_Art_Hold {r0['c1'].get('Camera_Art_Hold')}"
              # Streaming fix F1: which of the two copy-site patch loops ran. A
              # PatchRun row is only comparable with another run's at the SAME
              # value, so it is printed beside the rows rather than left implicit.
              f"   PageCache_Direct_Map {r0['c1'].get('PageCache_Direct_Map', 'n/a')}")
        fpts = [x["frames_per_tick"] for x in runs]
        print(f"   frames/tick across {args.repeat} boots: {[round(x,3) for x in fpts]}"
              f"   spread {max(fpts)-min(fpts):.3f}")
        if fr == 0:
            print("   !! PageIn_Fully_Resident is 0 — PageCache_Prefetch is LIVE and"
                  " FindStagedBlock is NOT sole-parent. Do not split it by parent.")
        d = r0["deltas"]
        print("   engine counter deltas over the sample: "
              + "  ".join(f"{k.replace('Dbg_','')}={v}" for k, v in d.items() if v))
        # EXACT decompress count. Block_Stage_Gen is bumped in exactly two places
        # (tile_cache.emp:214 InvalidateStaging, :247 the DecompressBlock slot claim);
        # InvalidateStaging runs only at act init, never inside a sample. So the delta IS
        # the decompress count -- exact, unlike the profiler's integer-rounded per-frame
        # `calls` average. Cross-checked against calls(TileCache_DecompressBlock) below.
        dec = d.get("Block_Stage_Gen", 0)
        gens = [x["deltas"].get("Block_Stage_Gen", 0) for x in runs]
        print(f"   EXACT decompresses (Block_Stage_Gen delta): {dec} over {r0['ticks']} ticks"
              f" = {dec / r0['ticks'] if r0['ticks'] else 0:.2f}/tick"
              f"   (budget {6}/pass)   across boots {gens}")
        a0v, a1v = r0["c0"].get("Page_Audit_Ticks"), r0["c1"].get("Page_Audit_Ticks")
        fired = a1v is not None and a0v is not None and a1v < a0v
        print(f"   Page_Audit_Ticks {a0v} -> {a1v}: DEBUG residency audit"
              f" {'FIRED INSIDE THE WINDOW (PageCache_Audit row is a one-shot amortized over the sample)' if fired else 'did NOT fire in the window'}")
        print("   end-of-sample: "
              + "  ".join(f"{k}={r0['c1'].get(k)}" for k in
                          ("Cache_Fill_Budget", "Cache_Fill_Rows_Left", "Cache_Art_Stall",
                           "Cache_Stall_Watchdog", "Cache_Fill_Resume_Col",
                           "Cache_Fill_RowResume_Row", "Block_Stage_Next")))

        # WORK PER TICK, independent of any single row's attribution. The profiler's
        # `total_cycles` is the ideal cycles it accounted for in one video frame (budget_pct
        # against the 128000-cycle NTSC frame); VSync_Wait is the idle spin inside it. The
        # difference, scaled to the tick, is what a logic tick actually costs -- and
        # frames/tick tracks ceil(work / 128000), which is what makes the ratio integral.
        allrows = [rows_by_addr(x["prof"], sym, ROUTINES) for x in runs]
        tot = r0["prof"].get("total_cycles", 0)
        vs = next((int(a["VSync_Wait"]["cycles"]) for a in allrows if a.get("VSync_Wait")), 0)
        work = tot * fpt - vs * fpt
        print(f"   frame accounting: total_cycles {tot}/frame ({r0['prof'].get('budget_pct')}%"
              f" of 128000)   VSync_Wait {vs}/frame")
        print(f"   WORK PER TICK = ({tot} - {vs}) x {fpt:.3f} = {work:.0f}"
              f"   = {work/128000:.2f} video frames  ->  ceil = {-(-work//128000):.0f}"
              f"   (measured frames/tick {fpt:.3f})")

        hdr = (f"   {'ROUTINE':34} {'calls/f':>8} {'cyc/frame':>11} {'spread':>7}"
               f" {'cyc/tick':>10} {'calls/tick':>10} {'%fill':>7}")
        print(hdr)
        print("   " + "-" * (len(hdr) - 3))
        fill = allrows[0].get("Tile_Cache_Fill")
        fill_tick = (int(fill["cycles"]) * fpt) if fill else 0
        st = {}
        for name in BRACKETS:
            rr = [a.get(name) for a in allrows]
            if any(x is None for x in rr):
                print(f"   {name:34} {'--':>8} {'ABSENT':>11}")
                continue
            cyc = [int(x["cycles"]) for x in rr]
            cal = [int(x["calls"]) for x in rr]
            st[name] = {"cycles": cyc, "calls": cal, "cyc_per_tick": cyc[0] * fpt}
            print(f"   {name:34} {cal[0]:>8} {cyc[0]:>11} {max(cyc)-min(cyc):>7}"
                  f" {cyc[0]*fpt:>10.0f} {cal[0]*fpt:>10.1f}")
        print("   " + "-" * (len(hdr) - 3))
        for name, depth in TREE:
            rr = [a.get(name) for a in allrows]
            # depth 0 below Tile_Cache_Fill = a SIBLING of the fill, not a child: print
            # it flush-left and with no %fill, because a percentage of a routine it is
            # not inside is a category error (F5 — it read 411.6% at idle when the
            # audit was still tabled as a child after the gate had moved out).
            sib = depth == 0 and name != "Tile_Cache_Fill"
            label = ("   " if sib else "") + "  " * depth + ("+- " if depth else "") + name
            if any(x is None for x in rr):
                print(f"   {label:34} {'--':>8} {'ABSENT (0 calls)':>11}")
                st[name] = {"cycles": [0], "calls": [0], "cyc_per_tick": 0.0}
                continue
            cyc = [int(x["cycles"]) for x in rr]
            cal = [int(x["calls"]) for x in rr]
            st[name] = {"cycles": cyc, "calls": cal, "cyc_per_tick": cyc[0] * fpt}
            pct = (100.0 * cyc[0] / fill["cycles"]) if fill and fill["cycles"] else 0.0
            pcts = "  (not in fill)" if sib else f" {pct:>6.1f}%"
            print(f"   {label:34} {cal[0]:>8} {cyc[0]:>11} {max(cyc)-min(cyc):>7}"
                  f" {cyc[0]*fpt:>10.0f} {cal[0]*fpt:>10.1f}{pcts}")

        # ---- the inclusive-vs-exclusive test, and the OWN-cost residues ----
        print("   -- inclusive-row check + own (exclusive) cost --")
        for parent, kids in CHILDREN.items():
            p = st.get(parent)
            if not p:
                continue
            ksum = sum(st[k]["cycles"][0] for k in kids if k in st)
            own = p["cycles"][0] - ksum
            verdict = "inclusive OK" if 0 <= own <= p["cycles"][0] else "!! NOT INCLUSIVE"
            print(f"      {parent:30} row {p['cycles'][0]:>7}"
                  f"  children {ksum:>7}  own {own:>7}"
                  f"  ({own*fpt:>8.0f} /tick)  {verdict}")
        table[s] = {"frames": r0["frames"], "ticks": r0["ticks"], "frames_per_tick": fpt,
                    "frames_per_tick_all": fpts,
                    "dx": r0["dx"], "dy": r0["dy"], "deltas": d,
                    "end": r0["c1"], "routines": st}
        print()

    if args.out:
        Path(args.out).write_text(json.dumps(table, indent=2) + "\n")
        print(f"raw: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
