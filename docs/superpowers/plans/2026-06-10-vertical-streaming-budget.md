# Vertical Streaming Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax.

**Goal:** Vertical scroll streaming stops causing lag frames — measured: 512px descent currently costs +15 lag frames vs +6 horizontal (2.5×); target is parity or better.

**Architecture:** Port the proven column-fill discipline (budget-gated decompress + partial resume) to row fills, cap rows filled per frame, clamp camera Y velocity so the fill contract is structural (every reference engine bounds the CAMERA, not the fill — S2 16px/f, S3K 24px/f + 1-2 rows/frame), and spend leftover budget prefetching the next block-row in the scroll direction so block-boundary crossings stop spiking 6 decompresses at once.

**Research:** docs/research/vertical-streaming.md (all 8 references + online, 2026-06-10). Measured baseline: idle 0 lag, vertical +15, horizontal +6 (DEBUG build `Lag_Frame_Count`, 8×64px steps).

**Locked decisions:**
- Rows/frame cap **R=4** (terminal velocity = 2 rows/frame; cap 4 = catch-up headroom; cache margin 16 rows = 8 frames of TV buffer).
- Camera Y delta clamp **32px/frame** (= R×8; S2 uses 16, S3K 24 — we take 32 so the cap and clamp agree). `DEBUG_FLY_SPEED_FAST` drops 48→32 to match (debug-only knob). Bigger deltas only occur via teleports, which already run `TileCache_Reinit`.
- Row fills share `Cache_Fill_Budget` (6 decompresses/frame) with columns; row resume state is separate from column resume (`Cache_Fill_RowResume_Row/Col`, $FFFF = none).
- Prefetch uses NO new RAM: with 12 staging slots round-robin, ≤6 prefetched blocks + ≤6 column blocks coexist; prefetch ≤1 block/frame, only from leftover budget, only while Camera_Y is moving.
- **Out of scope:** Parallax_Fill_PerLine's 45.6k/frame idle cost (measured this session — bigger than streaming; separate task next). §4.9 X-only entity window (documented).

---

### Task 1: Budget + resume + cap for row fills

**Files:** engine/level/tile_cache.asm, ram.asm, constants.asm

- [ ] ram.asm: add `Cache_Fill_RowResume_Row: ds.w 1` + `Cache_Fill_RowResume_Col: ds.w 1` next to the column resume vars; init both to $FFFF in `Tile_Cache_Init`/`TileCache_Reinit` (alongside `Cache_Fill_Resume_Col`).
- [ ] constants.asm: `VFILL_ROWS_PER_FRAME = 4` next to BLOCK_DECOMP_BUDGET, with the terminal-velocity contract comment.
- [ ] `TileCache_FillRow` (~line 835): gate the `TileCache_DecompressBlock` call exactly like FillColumn's (~774-777): `tst.w (Cache_Fill_Budget).w` / `beq .fr_budget_out` / `subq.w #1, (Cache_Fill_Budget).w`. On budget-out: store `d5` (world row) → RowResume_Row and `d7` (current world col cursor) → RowResume_Col, set d0=1 (partial), restore stack (the routine has 2 words pushed — pop before exit), rts. Complete path returns d0=0 and sets RowResume_Row=$FFFF. Header updated (Out: d0).
- [ ] `TileCache_FillRow` resume entry: if `d5 == RowResume_Row` on entry, start the column walk from RowResume_Col instead of Cache_Left_Col (mirror FillColumn's `.fc_from_top` pattern).
- [ ] `Tile_Cache_Fill` vertical section (~655-730): before the v-loops, finish a pending row resume first (like the pending-column block at ~530): if RowResume_Row ≠ $FFFF and still within cache bounds, call FillRow on it; if partial again, skip ALL further vertical work this frame (budget gone). Stale resume (row evicted) → clear.
- [ ] `.v_bottom_fill` and `.v_top_fill`: add a rows-this-frame counter (register or RAM word reset each Fill call): each completed FillRow decrements; at 0 remaining OR a partial return, stop extending that edge this frame (do NOT update the edge tracker past what was actually filled — read the current code carefully: `.v_bottom_fill` writes `Cache_Bottom_Row` AFTER the fill; on partial, the row is INCOMPLETE — the edge must NOT advance past it; store resume and bail. CAREFUL with the up-fill pair loop: it fills 2 rows per iteration; on partial in the first of a pair, Top_Row was already decremented — verify the resume covers re-entry; simplest correct rule: the pair iteration only starts if rows-remaining ≥ 2 AND budget > 0).
- [ ] Build both flavors. Commit: `perf(§4.7): row fills get the column discipline — budget gate, partial resume, 4-rows/frame cap`

### Task 2: Camera Y velocity clamp

**Files:** engine/level/camera.asm, objects/test_player.asm (DEBUG_FLY_SPEED_FAST), constants.asm

- [ ] constants.asm: `CAM_MAX_Y_STEP = 32` (comment: must be ≥ VFILL_ROWS_PER_FRAME*8; the streaming contract rests on this clamp — every reference engine bounds camera velocity, S2=16 S3K=24).
- [ ] camera.asm `Camera_Update` Y tracking: after computing the overshoot delta (`.apply_y` path), clamp d3 to ±CAM_MAX_Y_STEP before applying. (X stays unclamped this task.)
- [ ] test_player.asm: `DEBUG_FLY_SPEED_FAST = 32` (was 48) with one-line why.
- [ ] Build, commit: `feat(camera): Y velocity clamp 32px/frame — the streaming fill contract is now structural`

### Task 3: Scroll-direction block prefetch from leftover budget

**Files:** engine/level/tile_cache.asm, ram.asm

- [ ] RAM: `Cache_Prev_Cam_Row: ds.w 1` (last frame's camera world row, for direction; init in Tile_Cache_Init).
- [ ] At the end of `Tile_Cache_Fill` (before `.fill_return`): if `Cache_Fill_Budget` ≥ 1 and camera row moved this frame (compare vs Cache_Prev_Cam_Row, update it), compute the NEXT block-row beyond the moving edge (down: (Cache_Bottom_Row+1) block row; up: (Cache_Top_Row-1)'s), and the block COLUMN under the camera center X; `TileCache_FindStagedBlock` — on miss, decrement budget and `TileCache_DecompressBlock` (≤1 per frame). Guard world bounds (row 0 / grid height).
- [ ] Build, commit: `perf(§4.7): leftover-budget prefetch of the next block-row — flattens block-boundary decompress spikes`

### Task 4: Measure, docs, close

- [ ] DEBUG build; reproduce the EXACT baseline protocol: boot, read Lag_Frame_Count (note boot value), idle 2s (must be unchanged), then 8 writes of +64px descent to player y_pos reading the counter after; then 8×+64px horizontal; record deltas. Targets: vertical delta ≤ 7 (from 15), horizontal not regressed (≤6). NOTE debug-build addresses: Player_1=$FF8996 (y_pos +6 = $FF899C, x_pos +2 = $FF8998), Lag_Frame_Count=$FF897E — RE-DERIVE from the fresh build's s4.lst, the debug profiler block shifts addresses.
- [ ] Visual check: descend and ascend through several hundred px — no black/stale rows visible (the cap must never outrun the 16-row margin at clamped camera speed: 32px/f camera = 4 rows/f = exactly the cap → margin holds; verify no pop-in at sustained max descent).
- [ ] Docs: ENGINE_ARCHITECTURE §4.7 fill section gains the row budget/resume/cap + camera clamp contract; DEFERRED_WORK: close/annotate the vertical-cost remainder, add "Parallax_Fill_PerLine measured at 45.6k cycles/frame idle (35.6%) — hoisting task is next" so it's not lost.
- [ ] Commit docs; merge branch to master after review.

**Branch:** `vertical-streaming` off master. The 5 uncommitted user files (editor rings JSONs + export entity_data.asm) must NEVER be staged — use explicit `git add <file>` lists, never `git add -A`.

---

## RESULTS (2026-06-10, measured via DEBUG Lag_Frame_Count, 8×64px protocol)

| Stage | Vertical | Horizontal |
|---|---|---|
| Baseline | +15 | +6 |
| T1 (budget/resume/cap=4) | +15 | +7 |
| T2+T3 (clamp 32 + prefetch) | +15 | +5 |
| + Parallax_Fill_PerLine hoist (45.6k→22.6k) | +15 | — |
| + S2 contract retune (clamp 16, cap 2) | **+4** | +6 |

**Root cause was twofold:** (1) no headroom — Parallax_Fill_PerLine ate 45.6k/frame
idle (fixed: per-band dispatch, −50.5%); (2) the VBlank handler, not the fill —
4 rows/frame of plane-buffer payload overflowed the VBlank window into active
display where VDP access throttles (caught by PC-sampling: CPU stalled in
Process_DMA_Critical's DMA trigger). S2's 16px-clamp/2-row contract exists for
exactly this reason. Scope additions vs the original plan: the parallax hoist
(was "out of scope", measured as the blocker) and the retune.

**Follow-ups (not blocking):** prefetch column cursor (the residual +4 vertical
= 4 block-row crossings; prefetch currently re-probes only the view-center
column — walking the 6 visible block columns between crossings should reach
~+1); horizontal's +6 is the same crossing class. Plane-buffer per-VBlank
drain budget is the deeper fix if row payloads ever grow again.
