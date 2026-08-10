# FillColumn/Draw_TileColumn Hoist Implementation Plan (Diagonal-Scroll Parcel)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover ~5.5–8k cycles/frame at sustained max diagonal from the tile-cache copy/draw chain — `FillColumn`→`CopyBlockColumn` per-block overhead, `FindStagedBlock` repeat resolves, `FillRow` phase-2 re-derivation, and `Draw_TileColumn`'s gather loop — with **byte-identical per-word/per-cell SEMANTICS; cycle-shape changes only**.

**Branch:** `perf/fillcol-hoist` (off master, after any pending merges — same isolation pattern as `perf/patchrun-batch`).

## Plan-time code-read surprises (they re-scoped the briefed levers)

1. **Lever 1 was half-done already.** The "hoist invariant loads" half of the precedent already shipped as the H6 hoist: `FillColumn`/`FillRow` already carry `Tile_Cache_Nametable`/`Tile_Cache_Collision` in a5/a6 per column/row, and `PatchRun_Seq/_Col` already hoist `Cache_Cur_LocalMap`/`Page_Table`/`Page_Frames` per run. What remains per `CopyBlockColumn` call is call bracket + wrap re-derivation + dest-address recompute + stack traffic ≈ ~260 cycles/block, not thousands.
2. **`CopyBlockColumn`'s self cost is dominated by the strided two-plane collision byte loop** (~58 cycles/row × up to 8 rows ≈ 460–520 of its ~900/call self), not by re-derivable address math — unrolling that loop is worth as much as the hoist.
3. **`Draw_TileColumn`'s per-cell address is ALREADY incremental** (`lea TILE_CACHE_STRIDE*2(a0)` walk with a precomputed wrap-split). The real remaining win is a 4× unroll of the 30-cycle/cell gather. `Draw_TileRow_FromCache` is already move.l-paired and incremental — left alone.
4. **A 1-entry "last-block cache" in `FindStagedBlock` would catch almost nothing.** Repeat hits are not consecutive-call repeats: sibling walks repeat the same block *sequence in order* (col N+1 re-walks col N's 4-5 blocks; row N+1 re-walks row N's 6 blocks). Correct memo shape = per-walk, generation-guarded resolve trace. The prefetch scans' memos (`Pfx_Memo_*`/`Cs_Memo_*`) structurally miss every frame at max diagonal because the cache bounds advance.
5. **Register saturation is real.** `FillRow` uses every register except d6; `DecompressBlock` clobbers d0-d7/a0/a2-a4 — cursors cannot be carried across a demand decompress in registers; the cold path must recompute.
6. **`CopyBlockColumn` preserves a1 (staged base) via stack for `FillAll`'s 16-column reuse** — a documented past regression (P2b Task 6). The inlined hot path re-probes per block so it doesn't need the contract, but the proc must survive unchanged for `FillAll`.
7. **Budget honesty:** the "~50k copy chain" includes the off-limits PatchRuns (32.3k). Addressable non-PatchRun cost ≈ 17-18k; realistic scoped extraction ≈ 5.5–8k/frame (~4.5–6%) — converts zero headroom into real headroom but will not eliminate lag on the worst dense strips.

**Architecture:** Second wave of the patch-run batching precedent (`eb37f5a`, merged `01d9d059` — study its diff before Task 3). That parcel banked registers once per RUN inside `page_cache.emp`; this parcel banks once per COLUMN/WALK in the callers. Baseline (2026-08-09, oracle profiler, 60-frame avg, max diagonal from spawn, canonical DEBUG): frame 127,962/128,000. Decomposition: `Tile_Cache_Fill` 72.8k incl = `FillRow` 35.9k + `FillColumn` 28.9k; `CopyBlockColumn` 20.9k incl (8 calls) of which `PatchRun_Col` 13.7k; `PatchRun_Seq` 18.6k; `FindStagedBlock` 9.3k (24 calls, ~387/call); `DecompressBlock` 3.4k; `Draw_TileColumn` 5.1k; `Draw_TileRow_FromCache` 3.3k.

**HARD RULES (verbatim gate list — the DEBUG per-frame refcount audit is the checker):**
- `PageCache_PatchRun_Seq`/`_Col` and `pc_patch_run_loop` (`engine/level/page_cache.emp:418-584`) are **OFF-LIMITS** — already batched, M-1-endorsed. Do not touch `page_cache.emp` at all.
- Per-word/per-cell semantics IDENTICAL: **capture-old-before-write**, **ref-new-then-unref-old**, **blank early-outs preserved**, **miss = demand-Request + stall + skip + continue**. All four live inside the PatchRun loop we don't touch; every task must preserve the *inputs* to that loop (same src ptr, same dest ptr, same run lengths, same `Cache_Cur_LocalMap` published before every run).
- The final cache/collision/plane-buffer BYTES per frame must be identical to baseline. Only the cycle count changes.
- No `mulu`/`divu` in any touched path (§2.1). New-style `.emp` branch conventions apply.
- Every changed proc's `clobbers(...)`/`preserves(...)` re-derived from the actual write set — the sigil clobber verification is error-tier and is used as an expected-failure checkpoint.

**Tech Stack:** sigil native build (`SIGIL_BUILD`/`SIGIL_EMIT` env vars required). Shapes per commit, delete-first: `./build.sh`, `DEBUG=1 ./build.sh`, `./build.sh demo`, `DEBUG=1 ./build.sh demo`.

**Verification ground rules:**
- The implementer builds all four shapes per commit and never leaves the branch red. The implementer does **NOT** run emulators.
- **The controller runs every emulator gate** — oracle profiler decomposition re-measure, lag-counter traverses, replay net, DEBUG refcount audit soak — foreground only, ONE oracle instance, ROM hash-verified before any measurement. The controller also runs the **sigil byte-parcel ritual** (repin → hand-ledger narration → refreeze → workspace suite → merge both repos; precedent: sigil `7559a6e8` for code-shift parcels).
- **Replay regression net expectation, stated explicitly:** this is a PURE perf parcel — visible state per logic tick must be bit-identical, so **both fixtures must NOT desync**. A desync here is a gate FAILURE meaning a semantic change leaked (do NOT re-record; find the leak). This inverts the behavior-parcel rule on purpose.
- **DEBUG refcount audit gate** after every behavior-touching task (3, 4, 5): DEBUG shape, full-map churn drive — zero raises.
- Lag counter is ground truth for the win; the profiler decomposition is the attribution tool.

**Baseline capture (controller, before Task 1):** re-run the 2026-08-09 oracle decomposition (60-frame avg, max diagonal from spawn, canonical DEBUG) and the position-matched dense-region diagonal traverse (**baseline 29 lag/90 frames post-batching**) against the branch-point build, archived under `docs/superpowers/notes/`, so the Task 6 A/B is same-session, same-method.

---

### Task 1: `Draw_TileColumn` — 4× gather unroll + per-call invariant hoist

**Files:**
- Modify: `engine/level/plane_buffer.emp:183-206` (`.copy_col_run`) and `:64-88` (per-call setup)

- [ ] **Step 1: Unroll the two column-gather runs 4×.** `.ccr_run1`/`.ccr_run2` currently cost 30 cycles/cell (`move.w (a0),(a2)+` 12 + `lea TILE_CACHE_STRIDE*2(a0),a0` 8 + `dbf` 10). Replace each run body with a 4-cell unrolled loop using 16-bit source displacements + one `lea` + `dbf`, and a 0–3-cell remainder loop (existing body) fed from `count & 3`:

  ```asm
  // 4 cells: 12 + 16 + 16 + 16 + 8 (lea) + 10 (dbf) = 78 -> 19.5/cell (was 30)
  move.w  (a0), (a2)+
  move.w  TILE_CACHE_STRIDE*2(a0), (a2)+
  move.w  TILE_CACHE_STRIDE*4(a0), (a2)+
  move.w  TILE_CACHE_STRIDE*6(a0), (a2)+
  lea     TILE_CACHE_STRIDE*8(a0), a0
  ```

  The wrap-split arithmetic (`d2` rows-before-wrap, the `TILE_CACHE_NT_SIZE` rewind) is untouched — only the straight-run drains change. Both runs get the same treatment. The helper's register contract must hold; if the remainder split needs one more scratch, re-derive the proc's `clobbers(...)` and header comment together.
- [ ] **Step 2: Hoist the per-call `mul_const.w d1, #160` origin-row product** only if it falls out naturally from Step 1's register shuffle; it is ~44 cycles × 2 calls/frame — do not spend structure on it.
- [ ] **Step 3: Leave `Draw_TileRow_FromCache` untouched** — already move.l-paired with incremental cursors; note in the commit body why lever 3's second half is a no-op.
- [ ] **Step 4: Build all four shapes delete-first — green.**
- [ ] **Step 5: Commit:** `perf(level): Draw_TileColumn gather unroll — 4-cell displaced reads, ~10.5 cyc/cell off the column strip copy`

**Expected win:** ~10.5 cycles × 60 cells × 2 calls ≈ **~1.2k/frame** (HIGH confidence). CONTROLLER gate: none beyond build (byte-identity re-proven by the Task 6 replay net; optional screenshot-during-motion sanity pass).

### Task 2: `FillRow` — reuse the phase-1 valid-run bounds in phase 2

**Files:**
- Modify: `engine/level/tile_cache.emp:1724-1755` (phase-2 re-derivation) and `:1633-1659` (phase-1 derivation)

- [ ] **Step 1: Stack `ic_lo`/`ic_hi`/`B` once.** Phase 1 derives `[ic_lo, ic_hi)` + block base `B`; phase 2 re-derives the identical values (~140 cycles/block, odd rows only). Push `d3`/`d4`/`d2` immediately after `.fr_ichi_done` (before the emit clobbers them), pop at the phase-2 head, delete the re-derivation. Values identical by construction — same inputs, same math, computed once.
- [ ] **Step 2: Rewrite the phase-2 block comment.** The isolation-of-blame property ("a fault in this block can only touch collision") is being traded for cycles; the new comment must say so and state the invariant instead: *phase 2 consumes the exact phase-1 bounds; any bounds bug now hits NT and collision identically (the §5 parity-safe `coll_src_row_base` guard still stands alone).*
- [ ] **Step 3: Mind the budget-out stack discipline.** `.fr_budget_out`/`.fr_done` pop exactly two words today; the empty-run and even-row paths must not leave the three new words stacked. Push/pop strictly within the per-block span, discharged on every path reaching `.fr_next_block` (including `.fr_nt_empty` with an empty phase-2).
- [ ] **Step 4: Build all four shapes — green. Commit:** `perf(level): FillRow phase-2 reuses phase-1 run bounds — re-derivation folded (~140 cyc/block on cell-completing rows)`

**Expected win:** ~100 net/block × ~6 blocks × 1 odd row/frame ≈ **~0.6k/frame** (MEDIUM). CONTROLLER gate: DEBUG refcount audit soak + the §5 loop-arc wall probe drive (the audit is blind to collision corruption).

### Task 3: `FillColumn` — inline the hot copy body, bank once per column

The core of the parcel. `TileCache_CopyBlockColumn` (`tile_cache.emp:391-531`) stays byte-identical for its cold caller (`FillAll`, init-only). `FillColumn` (`:1418-1508`) gets a private inlined copy body with per-column invariants hoisted and cursors carried block-to-block.

**Files:**
- Modify: `engine/level/tile_cache.emp:1418-1508` (`TileCache_FillColumn`)
- Read-only reference: `:391-531`, `git show eb37f5a` (precedent for comment style + per-word-semantics narration)

- [ ] **Step 1: Hoist per-column invariants above `.fc_block_loop`.** Compute once per call: physical cache column (the `Cache_Origin_Col` wrap, ~34 cycles/block today), the column's NT dest byte offset component, the collision dest column component. `Cache_Origin_Col`/`Cache_Origin_Row` cannot change inside one `FillColumn` call (only `HSlide`/`VSlide`/`VSlideUp` move them, all outside) — say so in a comment.
- [ ] **Step 2: Inline the copy body and carry cursors across blocks.** Replace the `jbsr TileCache_CopyBlockColumn` + `movem` bracket with an inlined body that:
  - keeps the staged base from the probe in a register (no stack round-trip — the `FillAll` a1-preserve contract is NOT needed here because every block re-probes; cite the P2b Task 6 regression comment at `:522-528` and state why the inline path is exempt);
  - computes NT + collision dest cursors from the hoisted invariants **for the first block only**, then carries them (PatchRun_Col returns a0/a1 advanced one stride past the run; the collision loop advances its own cursor) with rows-until-wrap counters exactly as `Draw_TileColumn`'s `d2` scheme (wrap-split preserved: subtract `TILE_CACHE_NT_SIZE`/`TILE_CACHE_COLL_SIZE` at the row-59→0 / 29→0 boundary, at most once per column);
  - keeps the source-address calc per block (src row genuinely varies);
  - keeps run lengths, run splits, and the `PatchRun_Col` call sequence **bit-identical** (same d0 per run, same wrap subtraction) — the PatchRun inputs are the semantic surface.
- [ ] **Step 3: Cold path = recompute.** `DecompressBlock` clobbers d0-d7/a0/a2-a4 — carried cursors die on a demand decompress. On that path (and the resume-entry first block), derive cursors from `(d5, d7)` exactly as `CopyBlockColumn` does today. Do NOT preserve cursors across `DecompressBlock` in registers (only a5/a6 survive and they hold the H6 bases). RAM stash permitted only if recompute proves harder to sequence; prefer recompute.
- [ ] **Step 4: Expected-failure checkpoint — clobber verification.** Build DEBUG after restructuring but before re-deriving `TileCache_FillColumn`'s `clobbers(...)`: expect the sigil clobber verification to fail on the changed write set. Fix attribute + header comment; rebuild green. (If it does NOT fail, diff the write set by hand.)
- [ ] **Step 5: Verify `Cache_Art_Stall` and budget-out topology unchanged.** The stall test after the copy, the `.fc_budget_out` resume store, and the `art_hold_edge_check` camera-hold arm sit at the same decision points with the same `d5`/`d7` meanings. Miss semantics untouched by construction (PatchRun inputs identical).
- [ ] **Step 6: Build all four shapes — green. Commit:** `perf(level): FillColumn banks per column — CopyBlockColumn body inlined for the hot path, wraps/dest cursors hoisted & carried across blocks; CopyBlockColumn proc retained byte-identical for FillAll. PatchRun inputs bit-identical (per-word semantics: capture-old-before-write, ref-new-then-unref-old, blank early-outs, miss=Request+stall+skip+continue — all inside the untouched patch runs)`

**Expected win:** ~260/block × 8 ≈ **~2.1k/frame** (MEDIUM; register fit = SOFT until it assembles). ROM +~150-250 B (body duplicated for FillAll; patch-run parcel banked −230 B, pair ~net-flat). CONTROLLER gate: DEBUG refcount audit soak through full-map churn + a diagonal drive past the dense strips; screenshots during motion at the column seam.

### Task 4: collision inner-loop unroll (inside the Task 3 body)

**Files:**
- Modify: `engine/level/tile_cache.emp` (the new inline body's collision runs; optionally `TileCache_CopyBlockColumn` — Step 2)

- [ ] **Step 1: Full-unroll the count-8 case.** The collision run body costs ~58/row. A full block (16 tile rows → count 8, the common mid-column case) unrolls to displaced pairs — row k: `move.b k*16(a0), k*80(a2)` + `move.b (k*16+BLOCK_COLL_PLANE_SIZE)(a0), (k*80+TILE_CACHE_COLL_SIZE)(a2)` — ≈ 312 total vs 464, with one trailing cursor advance to keep the Task 3 carried-cursor contract. Dispatch: `cmpi #8` → unrolled, else the existing `dbf` loop (wrap-split and clipped blocks). Guard displacement reach with comptime `ensure`s, not comments.
- [ ] **Step 2: Decide `CopyBlockColumn` parity.** Default: leave the proc's loops alone (init-only, cold). A shared `comptime fn` body is acceptable only if it costs no hot-path cycles.
- [ ] **Step 3: Build all four shapes — green. Commit:** `perf(level): FillColumn collision copy — count-8 full unroll with displaced two-plane pairs (~150 cyc/full block)`

**Expected win:** ~152 × ~6 full blocks/frame ≈ **~0.9k/frame** (MEDIUM). CONTROLLER gate: collision drive re-run (audit is blind to collision).

### Task 5: `FindStagedBlock` walk-trace memo (the resolve hoist)

Behavior-adjacent — sequenced last on purpose. `TileCache_FindStagedBlock` itself stays untouched; the memo lives in the two fill walks.

**Files:**
- Modify: `engine/ram.emp` (~:605-640, beside the existing memo block): `Fill_ColTrace`/`Fill_RowTrace` (12-byte entries: key.l, ptr.l, map.l; capacities from comptime math — `TILE_CACHE_COLS/BLOCK_TILE_SIZE + 1 = 6` row entries, `TILE_CACHE_ROWS/BLOCK_TILE_SIZE + 2 = 5` col entries, `ensure`-guarded), `Fill_ColTrace_Gen`/`Fill_RowTrace_Gen` (u16, `$FFFF` = dead), cursors. ~150 bytes; the phase-block overflow `ensure` is the budget check.
- Modify: `engine/level/tile_cache.emp` `.fc_block_loop` (`:1431-1449`) and `.fr_block_loop` (`:1581-1597`) probe sites; `TileCache_InvalidateStaging` (`:195-218`) gets the trace-gen kill alongside the existing memo kills.

- [ ] **Step 1: Emit the trace check/record as one `comptime fn`** (mirroring `decompose_block`'s pattern) parameterized on trace base + cursor location, so both walks share one audited body. Scheme:
  - **Walk start:** if `Block_Stage_Gen != trace_gen` → trace invalid for reads this walk; set `trace_gen = Block_Stage_Gen` and record-as-you-go. Reset cursor either way.
  - **Per block (trace live):** build the 32-bit key (same `sec_x<<8|sec_y : block_index` pack the probe uses), `cmp.l` against the cursor entry. **Match** → take ptr into a1 AND store the entry's map to `Cache_Cur_LocalMap` (the republish is part of `FindStagedBlock`'s hit contract — the PatchRuns read it per run; missing this is the one way this task can corrupt state, say so in the comment). **Mismatch** → normal `jbsr TileCache_FindStagedBlock` (+ decompress path), then record key/ptr/`Cache_Cur_LocalMap` at the cursor.
  - **Mid-walk decompress:** `DecompressBlock` bumps `Block_Stage_Gen`; a round-robin claim may overwrite a slot an earlier-recorded entry points at → on the decompress path, set this walk's `trace_gen = $FFFF` (dead), stop reading AND recording for the rest of the walk. Conservative by design.
  - **Cursor homes:** `FillRow` — d6 currently unused in its body (verify, then claim it in the clobber attr). `FillColumn` — d6 is a transient there; use a RAM cursor.
  - `TileCache_InvalidateStaging` sets both trace gens to `$FFFF` (it already bumps `Block_Stage_Gen`; the explicit kill makes the invariant local and greppable).
- [ ] **Step 2: DEBUG capacity assert** against trace capacity before each record; capacities derived from the same constants as the walk spans, `ensure`-tied.
- [ ] **Step 3: Expected-failure checkpoint.** Deliberately mis-size one trace `ensure` (capacity − 1) to prove the comptime guard fires, then restore. (Validates the guard protecting against future `TILE_CACHE_*` geometry drift.)
- [ ] **Step 4: Build all four shapes — green. Commit:** `perf(level): fill-walk resolve trace — gen-guarded per-walk memo of FindStagedBlock resolves; sibling column/row walks skip the 16-slot probe (~250 cyc/repeat hit). Hit path republishes Cache_Cur_LocalMap identically; any staging claim/invalidate kills the trace via generation`

**Expected win (SOFT — hit-rate dependent):** hit ≈ ~84-100 cycles vs jbsr+probe ≈ ~365 → ~265/hit; at max diagonal ~10 repeat hits/frame minus ~14 misses × ~60-120 record/check overhead ≈ **~1.5-2.5k/frame net**. Frames with a mid-walk demand decompress drop to zero benefit (by design). CONTROLLER gate: FULL battery — DEBUG refcount audit soak through full-map churn (this is the task that can serve a stale slot pointer if the gen rules are wrong; the audit + the DEBUG pool-bound raise are the tripwires), stall/watchdog spot-check, replay net.

### Task 6: A/B gate, docs sync, ritual handoff

**Files:**
- Modify: `docs/DEFERRED_WORK.md` (diagonal-budget entry: new measured block + status update)
- Create: `docs/superpowers/notes/2026-08-10-fillcol-hoist-ab.md` (A/B note)

- [ ] **Step 1 (CONTROLLER): oracle profiler decomposition re-measure** — same method as baseline, ROM hash-verified. Per-symbol deltas for: `Tile_Cache_Fill`, `FillRow`, `FillColumn`, `CopyBlockColumn` (should collapse — hot caller no longer calls it), the inline body's span, `FindStagedBlock` (call count AND cycles — count is the memo's direct witness, expect ~24 → ~14), `PatchRun_Seq`/`_Col` (**must be unchanged within noise** — a delta = the run inputs changed = semantic leak), `Draw_TileColumn`, `Draw_TileRow_FromCache` (unchanged).
- [ ] **Step 2 (CONTROLLER): lag counter on the position-matched dense-region diagonal traverse.** Baseline **29 lag/90 frames**. Do NOT promise zero lag; record the honest number.
- [ ] **Step 3 (CONTROLLER): replay regression net — both fixtures MUST NOT desync** (a desync = leaked semantic change = gate FAILURE; bisect the task commits, do not re-record). Runbook: `notes/2026-08-09-replay-net-rerecord-ab.md`.
- [ ] **Step 4 (CONTROLLER): DEBUG refcount audit final soak** + all four shapes delete-first at the merge candidate.
- [ ] **Step 5: docs sync commit** — DEFERRED_WORK diagonal entry A/B block, the A/B note, and name the NEXT lever explicitly (candidates surfaced: sibling-row paired walks — rejected here for resume-topology risk; the flat HScroll/HInt taxes — previously ruled). Commit: `docs(level): fillcol-hoist A/B — diagonal-budget entry updated, parcel measured`
- [ ] **Step 6 (CONTROLLER): sigil byte-parcel ritual** — repin → hand-ledger narration → `refreeze --freeze <name> --ab <evidence>` → full workspace suite green → merge BOTH repos (precedent: sigil `7559a6e8`).

**Merge commit message (controller):** `Merge perf/fillcol-hoist: fill/draw copy-chain hoist — per-column banking, walk-trace resolve memo, gather/collision unrolls; per-word semantics untouched (PatchRuns unmodified, refcount audit green, replay fixtures hold)`

---

## Commit sequencing summary (never red)

T1 (draw unroll) → T2 (phase-2 reuse) → T3 (column banking) → T4 (collision unroll) → T5 (resolve trace) → T6 (docs). Risk ascends monotonically; any task can be the stopping point and the branch still merges as a smaller parcel. Expected-failure checkpoints (T3 Step 4 clobber lint, T5 Step 3 `ensure`) are transient within a task and never committed red.

## Cycle-estimate ledger (from instruction-timing arithmetic over the code as read)

| Task | Mechanism | Est./frame | Confidence |
|---|---|---|---|
| 1 | 30→19.5 cyc/cell × 60 × 2 calls | ~1.2k | HIGH |
| 2 | ~100 net/block × 6 × 1 odd row | ~0.6k | MEDIUM |
| 3 | ~260/block × 8 (bracket+wraps+dest recompute+stack) | ~2.1k | MEDIUM (register fit = SOFT) |
| 4 | ~152/full block × ~6 | ~0.9k | MEDIUM |
| 5 | ~265/hit × ~10 − record/check overhead | ~1.5-2.5k | SOFT (hit-rate) |
| **Total** | | **~5.5-8k (~4.5-6%)** | |

Against a 127,962/128,000 baseline this converts zero headroom into a real margin on the measured window; the dense-strip worst crossings will still lag — the lag counter, not this table, is the verdict.

## Self-review notes (scope coverage)

- Lever 1 (copy chain bank-per-column + hoist) → Tasks 3+4, re-scoped after finding the H6 hoist already shipped (surprise 1) and the collision loop dominating self cost (surprise 2).
- Lever 2 (`FindStagedBlock` memo) → Task 5, re-shaped from "last-block cache" to a per-walk gen-guarded trace (surprise 4).
- Lever 3 (draw recompute fold) → Task 1; the incremental-per-cell half already exists (surprise 3), `Draw_TileRow_FromCache` deliberately untouched with rationale recorded.
- Semantics gate list → enforced structurally (PatchRuns and their inputs untouched; `Cache_Cur_LocalMap` republish contract called out at its one risk point, T5 Step 1).
- Rejected in-scope alternative recorded for the next parcel: sibling-row paired walks (bigger win, resume-topology risk).
