#!/usr/bin/env python3
"""staging_lifetime_timeline — the settling experiment for TICK-VARIANCE §3's flagged
inference: WHY do the block-ROW crossings cost nothing while the block-COLUMN
crossings burst 25.7-48.9k cycles of S4LZ_DecompressDict?

THE QUESTION, as booked. TICK-VARIANCE.md §3 measured the burst, its frames, the
block-edge coincidence, and the budget exhaustion — and flagged the *coverage* of the
row side as an INFERENCE, with the leading hypothesis "the column crossing decompresses
blocks that the row crossing three ticks later re-uses out of the staging slots". This
instrument answers, per block claim:
    (a) which staging slot served each crossing's claims, and WHO filled that slot
        (which frame, which code path);
    (b) whether the column burst's output is what covers the later row crossing, or
        something else does;
    (c) why the column crossing itself finds NOTHING staged — and what early staging
        would have to do, and by when, to cover it.

THE INSTRUMENT. The staging cache is fully observable from RAM at frame boundaries:
    Block_Stage_Keys[BLOCK_STAGE_SLOTS]  — u32 key (sec_x<<24 | sec_y<<16 | block_index)
                                            per slot, $FFFFFFFF = empty
    Block_Stage_Ptrs[BLOCK_STAGE_SLOTS]  — the staged-data pointer per slot, which
                                            CLASSIFIES the claim's decode form:
                                              == Block_Stage_Buffers + slot*BLOCK_RAW_SIZE
                                                       -> COMPRESSED (S4LZ v3 decode ran)
                                              == Block_Stage_ZeroPage -> EMPTY (zero page)
                                              else (ROM address)      -> RAW-DIRECT (zero-copy)
    Block_Stage_Next / Block_Stage_Gen   — round-robin cursor / claim counter
Eviction is strict round-robin over BLOCK_STAGE_SLOTS slots, and every claim bumps
Block_Stage_Gen (engine/level/tile_cache.emp, TileCache_DecompressBlock), so diffing
the key array across one frame is an EXACT per-frame claim ledger: a slot cannot be
claimed twice inside one frame unless the frame carries more than BLOCK_STAGE_SLOTS
claims (round-robin needs SLOTS further claims to come back), and that case is
detected by gen_delta > changed_slots and BLOCKED loudly.

RITUAL — byte-identical to tools/tick_variance_probe.py, which this probe imports
rather than re-implements: maxdiag state via the leader poke, settle 180 / lead 24 /
31-frame window, fresh oracle-aether server per boot, prefix-differenced per-frame
routine rows on the cyclesSelf basis with the completeness identity checked at every
rung, and the corpus A/B PHASE-0 REFERENCE ROW control re-run before any new number.

IDENTITIES this probe adds, each cross-checking the ledger against an independent
witness (and each with a --poison lane that must exit 1):
    * CLAIMS: per frame, gen_delta == #slots whose key changed
                       == TileCache_DecompressBlock calls (profiler row, prefix-diffed)
    * FORM:   per frame, #claims classified COMPRESSED == S4LZ_DecompressDict calls
              (the profiler row again — a misclassified pointer cannot hide)
    * COVERAGE: every block a crossing NEEDS (derived from the engine's own geometry
              constants, parsed from engine/system/constants.emp at run time) is
              accounted for: either present in staging BEFORE the crossing frame, or
              claimed during the crossing tick. An unaccounted block means the
              needed-set derivation is wrong, and no serving verdict may be printed.

CONFOUND LANES. §3's row-coverage could be a STAGING property (the hypothesis) or a
CONTENT property (the row-side blocks decode as empty/raw-direct forms, which cost no
S4LZ regardless of staging). The form classification separates the two; the extra
`right` and `down` states vary what maxdiag holds fixed (heading, hence content path,
hence which crossings occur with speculation unsuppressed) — `right` in particular
shows what a column crossing looks like when the F2a latch is UP and the col-scan
prefetch is allowed to pre-stage.

Usage:
    python3 tools/staging_lifetime_timeline.py --rom s4.debug.bin --lst s4.debug.lst
    python3 tools/staging_lifetime_timeline.py --poison claims     # must exit 1
    python3 tools/staging_lifetime_timeline.py --poison form       # must exit 1
    python3 tools/staging_lifetime_timeline.py --poison coverage   # must exit 1
Exit: 0 measured · 1 a control/assertion failed (BLOCKED) · 3 setup problem
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tick_variance_probe as tvp                      # noqa: E402  (the ritual)
from tick_variance_probe import Blocked, Setup, Server, rd, identity, by_name  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# Extra states: vary the heading maxdiag holds fixed. Same leader-poke mechanism.
tvp.STATES["right"] = (tvp.DIAG_AHEAD_X, 0)
tvp.STATES["down"] = (0, tvp.DIAG_AHEAD_Y)

# Slot-array symbols on top of tick_variance_probe's counter set.
SLOT_SYMS = ("Block_Stage_Keys", "Block_Stage_Ptrs", "Block_Stage_Next",
             "Block_Stage_Buffers", "Block_Stage_ZeroPage")
EXTRA_WORD_SYMS = ("Cache_Pfx_Row_Target", "Cache_Pfx_Col_Target", "Cache_Spec_Window",
                   "Cache_Spec_Blocked", "Cache_H_Pfx_Dir", "Block_Stage_Next",
                   "Cache_Fill_Resume_Col", "Cache_Fill_RowResume_Row")

EMPTY_KEY = 0xFFFFFFFF


# ---- constants DERIVED from engine source, never pinned -----------------------------

def engine_constants():
    """Parse `pub const NAME = expr` from engine/system/constants.emp and evaluate the
    dependency chain (exprs reference earlier consts; `$` is hex). Every geometry
    number this probe uses comes from here or from the listing — nothing is copied
    from TICK-VARIANCE.md or from this file's own comments."""
    src = (ROOT / "engine" / "system" / "constants.emp").read_text()
    raw = {}
    for line in src.splitlines():
        m = re.match(r"\s*pub const (\w+)\s*=\s*(.+)$", line)
        if m:
            raw[m.group(1)] = m.group(2).split("//")[0].strip()
    vals, progress = {}, True
    while raw and progress:
        progress = False
        for name, expr in list(raw.items()):
            py = re.sub(r"\$([0-9A-Fa-f]+)", r"0x\1", expr)
            try:
                v = eval(py, {"__builtins__": {}}, vals)      # noqa: S307 (build const chain)
            except Exception:
                continue
            if isinstance(v, (int, float)):
                vals[name] = int(v)
                del raw[name]
                progress = True
    need = ("BLOCK_TILE_SIZE", "BLOCK_STAGE_SLOTS", "BLOCK_RAW_SIZE",
            "BLOCK_DECOMP_BUDGET", "BLOCK_SPEC_LEAD_TICKS", "BLOCK_SPEC_REARM",
            "TILE_CACHE_COLS", "TILE_CACHE_ROWS", "TILE_CACHE_MARGIN_H",
            "TILE_CACHE_MARGIN_V", "VFILL_ROWS_PER_FRAME", "CAM_MAX_STEP"
            if "CAM_MAX_STEP" in vals else "BLOCK_TILE_SIZE")
    missing = [n for n in need if n not in vals]
    if missing:
        raise Setup(f"constants not derivable from engine/system/constants.emp: {missing}")
    return vals


async def read_block(c, addr, nbytes):
    r = await c.call("emulator/read_memory", {"addr": hex(addr & 0xFFFFFF), "len": nbytes})
    b = r["bytes"]
    b = b[2:] if b.lower().startswith("0x") else b
    return bytes.fromhex(b[:nbytes * 2])


async def slot_snapshot(c, sym, K):
    slots = K["BLOCK_STAGE_SLOTS"]
    keys_raw = await read_block(c, sym["Block_Stage_Keys"], slots * 4)
    ptrs_raw = await read_block(c, sym["Block_Stage_Ptrs"], slots * 4)
    keys = [int.from_bytes(keys_raw[i * 4:i * 4 + 4], "big") for i in range(slots)]
    ptrs = [int.from_bytes(ptrs_raw[i * 4:i * 4 + 4], "big") for i in range(slots)]
    return {"keys": keys, "ptrs": ptrs}


async def counters_ext(c, sym):
    out = await tvp.counters(c, sym)
    for n in EXTRA_WORD_SYMS:
        if n in sym:
            out[n] = await rd(c, sym[n], 2)
    return out


def classify_ptr(ptr, slot, sym, K, poison_form=False):
    base = sym["Block_Stage_Buffers"] + (K["BLOCK_RAW_SIZE"] // 2 if poison_form else 0)
    if ptr & 0xFFFFFF == (base + slot * K["BLOCK_RAW_SIZE"]) & 0xFFFFFF:
        return "compressed"
    if ptr & 0xFFFFFF == sym["Block_Stage_ZeroPage"] & 0xFFFFFF:
        return "empty"
    return "raw"


def key_fields(key, K):
    """key = sec_x<<24 | sec_y<<16 | block_index  ->  world block (col, row)."""
    sec_x, sec_y, bi = key >> 24, (key >> 16) & 0xFF, key & 0xFFFF
    bts = K["BLOCK_TILE_SIZE"]
    return (sec_x * bts + (bi & 0xF), sec_y * bts + (bi >> 4))


def make_key(bcol, brow, K):
    bts = K["BLOCK_TILE_SIZE"]
    sec_x, sec_y = bcol // bts, brow // bts
    bi = (brow % bts) * 16 + (bcol % bts)
    return (sec_x << 24) | (sec_y << 16) | bi


# ---- the boot -----------------------------------------------------------------------

async def measure_boot(c, sym, K, state, window):
    """Direct sample + prefix ladder (tick_variance_probe's own), each rung extended
    with a staging-slot snapshot at the frame boundary.

    THE BASE-BOUNDARY PASS, load-bearing: sample() arms the profiler and the frame
    the arm lands in is uncounted (run_frames(N) -> frameCount N-1,
    tick_variance_probe's own note). So a rung's counted window starts one frame
    AFTER any state that can be read before its sample() — reading c0 at reach()'s
    end makes the FIRST ledger interval span two physical frames (the arm frame +
    the first counted one) while the profiler row spans one. The `right` state
    caught this live: gen delta 2 vs TileCache_DecompressBlock calls 1 at rung 1 —
    a claim inside the arm frame, invisible to the profiler by construction.

    The machine is deterministic (the spread gate proves it per boot), so the
    counted window's true START boundary is readable in a DEDICATED pass: reach()
    + run 1 frame (the arm-equivalent) + read. That state — c0/s0 — is the ledger's
    base; every rung k then reads its end boundary after sample(k), and interval k
    spans exactly the profiler's frame k, first rung included."""
    # base boundary pass — read the counted window's start state
    await tvp.reach(c, sym, state)
    await c.call("emulator/run_frames", {"frames": 1})   # the arm-equivalent frame
    c0 = await counters_ext(c, sym)
    s0 = await slot_snapshot(c, sym, K)
    # same-boot reproducibility witness: the base pass repeated must land on the
    # same state, or the ledger would difference two different runs
    await tvp.reach(c, sym, state)
    await c.call("emulator/run_frames", {"frames": 1})
    cb = await counters_ext(c, sym)
    sb = await slot_snapshot(c, sym, K)
    if sb != s0 or cb != c0:
        raise Blocked("base boundary pass does not reproduce within one boot — the "
                      "machine is not deterministic here and no ledger interval is "
                      "a measurement")

    # direct pass — its own reach, NO pre-run: sample()'s uncounted arm frame is
    # the same physical frame the base pass ran, so the counted window starts at
    # exactly the c0/s0 boundary
    await tvp.reach(c, sym, state)
    direct = await tvp.sample(c, window)
    c1 = await counters_ext(c, sym)
    identity(direct)
    if direct["frameCount"] != window:
        raise Blocked(f"direct sample frameCount {direct['frameCount']} != {window}")

    cums, snaps, cnts = [], [], []
    for k in range(1, window + 1):
        await tvp.reach(c, sym, state)
        pf = await tvp.sample(c, k)
        ck = await counters_ext(c, sym)
        sk = await slot_snapshot(c, sym, K)
        identity(pf)
        if pf["frameCount"] != k:
            raise Blocked(f"prefix {k}: frameCount {pf['frameCount']}")
        cums.append((k, pf, None, ck))
        snaps.append(sk)
        cnts.append(ck)
    tvp.check_ladder(cums, direct, window)
    return {"direct": direct, "c0": c0, "s0": s0, "c1": c1, "cums": cums,
            "snaps": snaps, "cnts": cnts,
            "ticks": c1["Logic_Tick"] - c0["Logic_Tick"]}


# ---- the ledger ---------------------------------------------------------------------

def build_ledger(boot, sym, K, poison=None):
    """Per-frame claim ledger from adjacent slot snapshots, cross-checked against
    Block_Stage_Gen and the profiler's own per-frame call counts."""
    window = len(boot["snaps"])
    frames = tvp.diff_series(boot["cums"])
    idx = {}
    for f in frames:
        for kk in f:
            idx.setdefault(kk[1], kk)

    def series(name, q):
        kk = idx.get(name)
        return [f.get(kk, {}).get(q, 0) if kk else 0 for f in frames]

    dec_calls = series("TileCache_DecompressBlock", "callsTotal")
    s4lz_calls = series("S4LZ_DecompressDict", "callsTotal")
    s4lz_self = series("S4LZ_DecompressDict", "cyclesSelfTotal")
    fr_calls = series("TileCache_FillRow", "callsTotal")
    fc_calls = series("TileCache_FillColumn", "callsTotal")

    ledger = []
    prev_s, prev_c = boot["s0"], boot["c0"]
    for i in range(window):
        cur_s, cur_c = boot["snaps"][i], boot["cnts"][i]
        gen_d = (cur_c["Block_Stage_Gen"] - prev_c["Block_Stage_Gen"]) & 0xFFFF
        if poison == "claims":
            gen_d += 1
        changed = [s for s in range(K["BLOCK_STAGE_SLOTS"])
                   if cur_s["keys"][s] != prev_s["keys"][s]]
        if gen_d != len(changed):
            raise Blocked(
                f"CLAIMS identity: frame +{i + 1}: Block_Stage_Gen advanced {gen_d} but "
                f"{len(changed)} slot keys changed — the ledger does not see every claim "
                f"(a slot turned over twice inside one frame, or the gen witness moved "
                f"without a key write)")
        if gen_d != dec_calls[i]:
            raise Blocked(
                f"CLAIMS identity: frame +{i + 1}: gen delta {gen_d} != "
                f"TileCache_DecompressBlock calls {dec_calls[i]} (profiler row) — a claim "
                f"path outside DecompressBlock exists, or the ledger is mis-diffed")
        claims = []
        for s in changed:
            form = classify_ptr(cur_s["ptrs"][s], s, sym, K,
                                poison_form=(poison == "form"))
            bc, br = key_fields(cur_s["keys"][s], K)
            claims.append({"slot": s, "key": cur_s["keys"][s], "bcol": bc, "brow": br,
                           "form": form,
                           "evicted_key": None if prev_s["keys"][s] == EMPTY_KEY
                           else prev_s["keys"][s]})
        n_comp = sum(1 for cl in claims if cl["form"] == "compressed")
        if n_comp != s4lz_calls[i]:
            raise Blocked(
                f"FORM identity: frame +{i + 1}: {n_comp} claims classified COMPRESSED "
                f"(staged ptr == Block_Stage_Buffers slot base) but S4LZ_DecompressDict "
                f"ran {s4lz_calls[i]} times (profiler row) — the pointer classification "
                f"does not describe the decode paths taken")
        ledger.append({"frame": i + 1, "claims": claims, "gen_d": gen_d,
                       "s4lz_calls": s4lz_calls[i], "s4lz_self": s4lz_self[i],
                       "fillrow_calls": fr_calls[i], "fillcol_calls": fc_calls[i],
                       "counters": cur_c})
        prev_s, prev_c = cur_s, cur_c
    return ledger


def attribute_claim(cl, cnt, prev_cnt, K):
    """Code-path attribution by block geometry + which claim sites were LIVE in the
    interval. tile_cache.emp claim sites: FillColumn/FillRow (demand), pfx row scan,
    cs col scan, corner (speculation — structurally impossible while the F2a latch
    `Cache_Spec_Blocked` is down at both interval boundaries, so those candidates are
    dropped then). Preference-ordered: a crossing's own demand walk first; ambiguity
    is printed as a candidate list, never silently resolved."""
    bts = K["BLOCK_TILE_SIZE"]
    head_b = cnt["Cache_Head_Col"] // bts
    left_b = cnt["Cache_Left_Col"] // bts
    top_b = cnt["Cache_Top_Row"] // bts
    bot_b = cnt["Cache_Bottom_Row"] // bts
    crossed_c = head_b != prev_cnt["Cache_Head_Col"] // bts
    crossed_r = bot_b != prev_cnt["Cache_Bottom_Row"] // bts
    moved_up = cnt["Cache_Top_Row"] < prev_cnt["Cache_Top_Row"]
    spec_live = not (cnt.get("Cache_Spec_Blocked", 0)
                     and prev_cnt.get("Cache_Spec_Blocked", 0))
    rt, ct = cnt.get("Cache_Pfx_Row_Target", 0xFFFF), cnt.get("Cache_Pfx_Col_Target", 0xFFFF)
    paths = []
    in_window = left_b <= cl["bcol"] <= head_b and top_b <= cl["brow"] <= bot_b
    if in_window:
        if crossed_c and cl["bcol"] == head_b:
            paths.append("demand-col(FillColumn@head)")
        if crossed_r and cl["brow"] == bot_b:
            paths.append("demand-row(FillRow@bottom)")
        if moved_up and cl["brow"] == top_b:
            paths.append("demand-row(FillRow@top)")
    if spec_live:
        if rt != 0xFFFF and cl["brow"] == rt // bts:
            paths.append("spec-row(pfx scan)")
        if ct != 0xFFFF and cl["bcol"] == ct // bts:
            paths.append("spec-col(cs scan)")
        if (rt != 0xFFFF and ct != 0xFFFF and cl["brow"] == rt // bts
                and cl["bcol"] == ct // bts):
            paths.append("spec-corner")
    if not paths and in_window:
        paths.append("demand-interior(resume/slide refill)")
    return paths or ["UNATTRIBUTED"]


def crossings(boot, K):
    """Block-grid crossings, exactly tick_variance_probe's derivation."""
    bts = K["BLOCK_TILE_SIZE"]
    out = []
    prev = boot["c0"]
    for i, cnt in enumerate(boot["cnts"]):
        mark = ""
        if cnt["Cache_Head_Col"] // bts != prev["Cache_Head_Col"] // bts:
            mark += "C"
        if cnt["Cache_Bottom_Row"] // bts != prev["Cache_Bottom_Row"] // bts:
            mark += "R"
        if mark:
            out.append({"frame": i + 1, "mark": mark, "cnt": cnt, "prev": prev})
        prev = cnt
    return out


def needed_blocks(x, K, poison=False):
    """The block set a crossing's demand fill must supply, from the engine's own
    walk geometry: a NEW column at Head touches block col Head//16 x block rows
    [Top//16 .. Bottom//16]; a NEW bottom row touches block row Bottom//16 x block
    cols [Left//16 .. Head//16] (tile_cache.emp FillColumn/FillRow loops)."""
    bts = K["BLOCK_TILE_SIZE"]
    cnt = x["cnt"]
    off = 1 if poison else 0
    need = []
    if "C" in x["mark"]:
        hb = cnt["Cache_Head_Col"] // bts + off
        for br in range(cnt["Cache_Top_Row"] // bts, cnt["Cache_Bottom_Row"] // bts + 1):
            need.append(("C", hb, br))
    if "R" in x["mark"]:
        rb = cnt["Cache_Bottom_Row"] // bts + off
        for bc in range(cnt["Cache_Left_Col"] // bts, cnt["Cache_Head_Col"] // bts + 1):
            need.append(("R", bc, rb))
    return need


def serve_analysis(boot, ledger, sym, K, poison=None):
    """For each crossing: each needed block is either PRE-STAGED (present in the slot
    table at the boundary before the crossing frame — then find who filled it) or
    CLAIMED during the crossing tick (frame f or f+1: FillRow can resume across the
    boundary on a budget-out). Anything else BLOCKS: the needed-set derivation would
    be wrong and no verdict may rest on it."""
    xs = crossings(boot, K)
    slots = K["BLOCK_STAGE_SLOTS"]
    # fill history: key -> list of (frame, slot, form, paths)
    fills = {}
    prev_cnt = boot["c0"]
    for e in ledger:
        for cl in e["claims"]:
            fills.setdefault(cl["key"], []).append(
                (e["frame"], cl["slot"], cl["form"],
                 attribute_claim(cl, e["counters"], prev_cnt, K)))
        prev_cnt = e["counters"]
    results = []
    edge_excluded = []
    for x in xs:
        f = x["frame"]
        # A crossing's claims land in frames f..f+1 (the fill pass can straddle the
        # boundary, and a budget-out resumes next frame). A crossing at the window's
        # last frame therefore has claims the ladder cannot observe — EXCLUDED with a
        # printed note, never adjudicated on a truncated view.
        if f + 1 > len(boot["snaps"]):
            edge_excluded.append(x)
            continue
        before = boot["snaps"][f - 2]["keys"] if f >= 2 else boot["s0"]["keys"]
        rows = []
        for kind, bc, br in needed_blocks(x, K, poison=(poison == "coverage")):
            key = make_key(bc, br, K)
            if key in before:
                slot = before.index(key)
                hist = [h for h in fills.get(key, []) if h[0] < f]
                if hist:
                    ff, fs, form, paths = hist[-1]
                    who = f"filled frame +{ff} slot {fs} form {form} via {'/'.join(paths)}"
                else:
                    ff = None
                    form = classify_ptr(
                        (boot["snaps"][f - 2] if f >= 2 else boot["s0"])["ptrs"][slot],
                        slot, sym, K)
                    who = f"filled BEFORE the window (form {form})"
                rows.append({"kind": kind, "bcol": bc, "brow": br, "served": "PRE-STAGED",
                             "slot": slot, "who": who})
                continue
            claimed = [h for h in fills.get(key, []) if f <= h[0] <= f + 1]
            if claimed:
                ff, fs, form, paths = claimed[0]
                rows.append({"kind": kind, "bcol": bc, "brow": br,
                             "served": f"CLAIMED frame +{ff}", "slot": fs,
                             "who": f"form {form} via {'/'.join(paths)}"})
                continue
            raise Blocked(
                f"COVERAGE: crossing {x['mark']} at frame +{f}: needed block "
                f"({bc},{br}) [key {key:08x}] is neither pre-staged at the prior "
                f"boundary nor claimed in frames +{f}..+{f + 1} — the needed-set "
                f"derivation does not describe the fill's real walk; no serving "
                f"verdict may be printed from it")
        results.append({"x": x, "rows": rows})
    # slot lifetimes: claim -> eviction (same slot re-claimed)
    lifetimes = []
    slot_last = {}
    for e in ledger:
        for cl in e["claims"]:
            s = cl["slot"]
            if s in slot_last:
                lifetimes.append({"slot": s, "filled": slot_last[s][0],
                                  "evicted": e["frame"],
                                  "life_frames": e["frame"] - slot_last[s][0],
                                  "key": slot_last[s][1], "form": slot_last[s][2]})
            slot_last[s] = (e["frame"], cl["key"], cl["form"])
    return results, lifetimes, edge_excluded


# ---- report -------------------------------------------------------------------------

def report(state, boots, sym, K, poison=None, out=sys.stdout):
    p = lambda *a: print(*a, file=out)                                  # noqa: E731
    b0 = boots[0]
    ledger = build_ledger(b0, sym, K, poison=poison)
    # cross-boot determinism: the whole ledger must be byte-identical
    led_reprs = []
    for b in boots:
        led_reprs.append(json.dumps(build_ledger(b, sym, K), sort_keys=True,
                                    default=str))
    spread = len(set(led_reprs)) - 1
    serve, lifetimes, edge_excluded = serve_analysis(b0, ledger, sym, K, poison=poison)

    n = len(b0["snaps"])
    ticks = [b["ticks"] for b in boots]
    p(f"== state {state}: {n} frames / ticks {ticks} (spread {max(ticks) - min(ticks)})"
      f"   claim-ledger spread across {len(boots)} boots: {spread} "
      f"({'IDENTICAL' if spread == 0 else 'DIVERGENT — machine not deterministic'})")
    if spread:
        raise Blocked("claim ledger differs across boots — no figure below is a "
                      "measurement")
    total_claims = sum(e["gen_d"] for e in ledger)
    forms = {}
    for e in ledger:
        for cl in e["claims"]:
            forms[cl["form"]] = forms.get(cl["form"], 0) + 1
    p(f"   claims over the window: {total_claims}  by form: {forms}   "
      f"claims/tick {total_claims / max(1, b0['ticks']):.2f}")
    p(f"   BLOCK_STAGE_SLOTS {K['BLOCK_STAGE_SLOTS']}  BLOCK_DECOMP_BUDGET "
      f"{K['BLOCK_DECOMP_BUDGET']}  BLOCK_SPEC_LEAD_TICKS {K['BLOCK_SPEC_LEAD_TICKS']} "
      f"(all parsed from engine/system/constants.emp)")

    p("\n   -- per-frame claim ledger (slot -> key(block col,row) form path) --")
    prev_cnt = b0["c0"]
    for e in ledger:
        if not e["claims"]:
            prev_cnt = e["counters"]
            continue
        cnt = e["counters"]
        bts = K["BLOCK_TILE_SIZE"]
        mark = ("C" if cnt["Cache_Head_Col"] // bts != prev_cnt["Cache_Head_Col"] // bts
                else "") + \
               ("R" if cnt["Cache_Bottom_Row"] // bts != prev_cnt["Cache_Bottom_Row"] // bts
                else "")
        p(f"   frame +{e['frame']:>2} {mark or '.':>2}  gen+{e['gen_d']}  "
          f"S4LZ {e['s4lz_self']:>6} cyc/{e['s4lz_calls']} calls  "
          f"spec_blocked {cnt.get('Cache_Spec_Blocked')}  "
          f"budget@boundary {cnt.get('Cache_Fill_Budget')} (a boundary SAMPLE — the "
          f"fill pass can straddle the frame boundary, so this is not 'budget after "
          f"these claims')")
        for cl in e["claims"]:
            paths = attribute_claim(cl, cnt, prev_cnt, K)
            p(f"        slot {cl['slot']:>2} <- block ({cl['bcol']},{cl['brow']}) "
              f"{cl['form']:<10} via {'/'.join(paths)}"
              + (f"  [evicted ({key_fields(cl['evicted_key'], K)[0]},"
                 f"{key_fields(cl['evicted_key'], K)[1]})]" if cl["evicted_key"] else ""))
        prev_cnt = e["counters"]

    p("\n   -- (a) each crossing's claims: which slot served, who filled it --")
    for x in edge_excluded:
        p(f"   crossing {x['mark']} at frame +{x['frame']}: WINDOW-EDGE EXCLUDED — its "
          f"claims land in frames +{x['frame']}..+{x['frame'] + 1}, past the ladder; "
          f"not evidence either way")
    for r in serve:
        x = r["x"]
        pre = sum(1 for row in r["rows"] if row["served"] == "PRE-STAGED")
        p(f"   crossing {x['mark']} at frame +{x['frame']}: "
          f"{len(r['rows'])} needed blocks, {pre} pre-staged, "
          f"{len(r['rows']) - pre} claimed at the crossing")
        for row in r["rows"]:
            p(f"        [{row['kind']}] block ({row['bcol']},{row['brow']}) "
              f"{row['served']:<18} slot {row['slot']:>2}  {row['who']}")

    if lifetimes:
        lf = [x["life_frames"] for x in lifetimes]
        p(f"\n   -- slot lifetimes (claim -> same-slot eviction), n={len(lf)}: "
          f"min {min(lf)} / mean {sum(lf) / len(lf):.1f} / max {max(lf)} frames --")
    return {"ledger": ledger, "serve": serve, "lifetimes": lifetimes, "forms": forms,
            "edge_excluded": edge_excluded, "total_claims": total_claims,
            "ticks": b0["ticks"]}


# ---- CR-28 addendum: the caller lens on the fill/S4LZ rows --------------------------

CALLER_ROWS = ("S4LZ_DecompressDict", "TileCache_DecompressBlock",
               "TileCache_FindStagedBlock", "Tile_Cache_Fill",
               "TileCache_FillRow", "TileCache_FillColumn")


async def callers_addendum(rom, lst, sym, K, state, window, out=sys.stdout):
    """One boot, whole-window sample with the CR-28 caller lens armed
    (set_profiler{callers:true} + get_profiler_frames{topCallers}) — direct
    call-graph evidence for the ledger's geometry-attributed 'who filled' answer.
    Consumption verdict for the oracle team rides on this output."""
    p = lambda *a: print(*a, file=out)                                  # noqa: E731
    async with Server(rom, lst) as c:
        r = await c.call("emulator/set_profiler",
                         {"enabled": True, "perFrame": True, "callers": True})
        if r.get("callers") is not True:
            raise Setup(f"server did not arm the caller lens: {r} — rebuild "
                        "oracle-aether at/after CR-28 (oracle main a621e4c)")
        await c.call("emulator/set_profiler", {"enabled": False})
        await tvp.reach(c, sym, state)
        await c.call("emulator/set_profiler",
                     {"enabled": True, "perFrame": True, "callers": True})
        await c.call("emulator/run_frames", {"frames": window + 1})
        pf = await c.call("emulator/get_profiler_frames",
                          {"frames": window + 8, "top": 512, "topCallers": 8})
        await c.call("emulator/set_profiler", {"enabled": False})
        identity(pf)
        addr2name = {int(r2["addr"], 16) & 0xFFFFFF: r2.get("name")
                     for r2 in pf["routines"]["items"]}
        p(f"\n== CR-28 caller lens, state {state}, {pf['frameCount']} frames "
          f"(whole-window rows; one boot — the ledger above carries the spread) ==")
        rows = by_name(pf)
        for nme in CALLER_ROWS:
            r2 = rows.get(nme)
            if r2 is None:
                p(f"   {nme}: no row in this window")
                continue
            p(f"   {nme}  calls {r2['callsTotal']}  self {r2['cyclesSelfTotal']}"
              f"  callers {r2.get('callersReturned')}/{r2.get('callersTotal')}"
              f"{'  TRUNCATED' if r2.get('callersTruncated') else ''}")
            for e in r2.get("callers", []):
                who = e.get("callerAddr")
                if who is not None:
                    a = int(who, 16) & 0xFFFFFF
                    who = addr2name.get(a) or who
                else:
                    who = f"<{e.get('entryKind')}>"
                extra = {k2: v for k2, v in e.items()
                         if k2 not in ("callerAddr", "entryKind")}
                p(f"        <- {who:38} {json.dumps(extra, sort_keys=True)}")
    return pf


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--states", default="maxdiag,right,down")
    ap.add_argument("--window", type=int, default=tvp.WINDOW)
    ap.add_argument("--boots", type=int, default=3)
    ap.add_argument("--no-control", action="store_true")
    ap.add_argument("--poison", choices=("claims", "form", "coverage"), default=None)
    ap.add_argument("--callers", action="store_true",
                    help="CR-28 addendum: whole-window caller lens on the fill/S4LZ "
                         "rows, one boot per state (requires oracle-aether at/after "
                         "CR-28)")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    rom, lst = str(Path(args.rom).resolve()), str(Path(args.lst).resolve())
    if not Path(rom).exists() or not Path(lst).exists():
        print(f"missing {rom} or {lst}", file=sys.stderr)
        return 3
    d = Path(rom).read_bytes()
    t0 = time.time()
    print(f"ROM {rom}\n    crc32 {zlib.crc32(d) & 0xFFFFFFFF:08x}  len {len(d)}")
    print(f"instrument: {tvp.SERVER}")
    if args.poison:
        print(f"!! POISONED RUN (--poison {args.poison}) — this MUST exit 1\n")
    K = engine_constants()

    async def resolve():
        need = (list(tvp.LONG_SYMS) + list(tvp.WORD_SYMS) + list(tvp.BYTE_SYMS)
                + list(tvp.SETUP_SYMS) + list(SLOT_SYMS) + list(EXTRA_WORD_SYMS))
        out, missing = {}, []
        async with Server(rom, lst) as c:
            for nme in dict.fromkeys(need):
                try:
                    r = await c.call("emulator/lookup_symbol", {"name": nme})
                    out[nme] = int(r["addr"], 16) & 0xFFFFFF
                except Exception:
                    missing.append(nme)
        hard = [m for m in missing if m in SLOT_SYMS or m in tvp.LONG_SYMS
                or m in tvp.SETUP_SYMS]
        if hard:
            raise Setup(f"symbols missing from {lst}: {', '.join(hard)}")
        if missing:
            print(f"   note: optional counters absent: {', '.join(missing)}")
        return out

    try:
        sym = asyncio.run(resolve())
        if not args.no_control:
            scratch = Path(os.environ.get("TMPDIR", "/tmp")) / "s4.corpus.d22dda85.bin"
            corpus = tvp.recover_corpus_rom(scratch)
            print(f"-- CONTROL: the A/B's pinned reference row on the A/B's own ROM "
                  f"(tick_variance_probe's §0, reused verbatim) --")
            log = asyncio.run(tvp.control(corpus, sym))
            print("\n".join(log))
            print(f"   control took {time.time() - t0:.1f}s\n")

        if args.callers:
            for state in args.states.split(","):
                asyncio.run(callers_addendum(rom, lst, sym, K, state, args.window))
            print(f"total wall {time.time() - t0:.1f}s")
            return 0

        results = {}
        for state in args.states.split(","):
            boots = []
            for i in range(args.boots):
                tb = time.time()

                async def one():
                    async with Server(rom, lst) as c:
                        return await measure_boot(c, sym, K, state, args.window)
                boots.append(asyncio.run(one()))
                print(f"   [{state}] boot {i + 1}/{args.boots}: direct + "
                      f"{args.window}-rung ladder + slot snapshots in "
                      f"{time.time() - tb:.1f}s")
            print()
            results[state] = report(state, boots, sym, K, poison=args.poison)
            print()
        if args.json:
            Path(args.json).write_text(
                json.dumps({s: {k2: v for k2, v in r.items() if k2 != "ledger"}
                            | {"ledger": r["ledger"]} for s, r in results.items()},
                           indent=1, default=str) + "\n")
            print(f"raw: {args.json}")
    except Blocked as e:
        print(f"\nBLOCKED: {e}", file=sys.stderr)
        return 1
    except Setup as e:
        print(f"\nSETUP: {e}", file=sys.stderr)
        return 3
    print(f"total wall {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
