# .emp Port Optimization Review — 2026-07-16

Static optimization review of ALL `.emp` ports, in two waves.
**Wave 1** (hot per-frame paths): `plane_buffer`, `tile_cache`, `entity_window`, `sprites`,
`core`, `collision` + `collision_lookup`, `animate` + `rings`.
**Wave 2** (everything else): `section`, `sound_api`, `dplc`/`load_object`/`frames`/
`objdef`/`sst`, `hblank`/`game_loop`/`controllers`/`math`/`vdp_init`/`types`, `aabb` +
test objects, and the data/definition files (`structs`/`constants` twins + game data).
Thirteen independent deep reviews, synthesized here. **Notes only — nothing has been
applied.** All cycle figures are estimates from standard 68000 timing tables; no emulator
profiling was run. Wave-2 sections start at "WAVE 2" below; the cross-file priority list
and bug roll-up immediately following this paragraph cover BOTH waves.

## Global constraints for whoever applies any of this

- **Twin lockstep:** every `.emp` file here is a byte-identical port of its `.asm` twin.
  Any change lands on BOTH sides together, and moves the shape-length byte gates. Check the
  tranche porting rules first.
- **Measure with the lag-frame counter** during max-speed diagonal scroll (the historical
  worst case). Producer-side costs eat the main-loop frame budget; VBlank-side costs eat the
  ~18,500-cycle NTSC VBlank window. Attribute wins to the right budget. A
  `Prof_TouchResponse` harness already exists at `games/sonic4/test/object_test_state.asm:109-116`.
- **Preserve the VInt_Lag race fix** (b96c861): terminator semantics and Plane_Buffer_Ptr
  reset ordering are load-bearing.
- Cycle numbers below are **estimates** — verify against real timings before claiming savings.

## Cross-file priority order (by expected value)

1. **tile_cache #1** — FillRow per-tile loop → precomputed contiguous segments.
   ~10–25k cycles per vertical-scroll frame (est.). The single biggest item; directly the
   historical lag path.
2. **tile_cache #2** — per-slot staging data pointer: empty blocks point at a shared zero
   ROM block (~5.8k/block), raw blocks point straight at ROM (~4.0k/block), up to 6/frame.
3. **plane_buffer #1/#4** — row-fill and column-fill segment restructures (same pattern as
   tile_cache #1); plus **#2/#3** drain-side wins (move.l column drain, producer-precomputed
   VDP command words).
4. **collision_lookup #1–3 fused rewrite** — span-check fusion + cached biases + ×80 row
   table: ~30% off every terrain sensor lookup (~600–2,000/frame). Plus **collision #1**
   fixed-sweep skip counter (~1.5–1.9k/frame).
5. **sprites H1 + H2** — cached frame offset in SST (~1.5–2k/frame) + emit-loop stream-order
   restructure with size+link word merge (~1–1.9k/frame in the hottest loop). **H3** patches
   the sprite-table DMA length to `Sprites_Rendered*8` (up to ~480 B of Critical VBlank DMA
   budget back).
6. **rings R2 + R3** — cull-side camera-bias fold (~2.5k/frame at full buffer) + hoisted
   player dims in RingCollision (~3k/frame). **animate A2+A3** — dirty-check + tail-call
   around RefreshSpritePieceCount (~60/expiry, big for static looped objects).
7. **entity_window High #1** — per-section next-entity-X trigger cache (reusing the two
   *dead* `ess_*_left_idx` fields), ~500–650/frame; **High #3/#4** despawn-loop invariant
   hoists (~1.3–2k/frame with many live entities).
8. **core #1** — register-cached camera + branchless window cull (~200–350/frame, scales
   with object count); **#2** O(1) delete backpointer (only if delete storms show on the
   lagometer).
9. **section H1/H2/H3** — idle early-out for `Section_UpdateColumns` (~500–600/frame on the
   majority of frames), delete the contract-contradicting `movem` pair (~180/frame, every
   frame incl. lag frames), build-time act boundary constant (~50/frame + kills a drift
   trap). **H4** — hoist the per-cell wrap compare out of the redraw loop (~57k cycles off
   the init/recovery stall).
10. **hblank H1** — replace the dispatch wrapper with a RAM `jmp` trampoline BEFORE any real
    raster handler is written: ~116 cycles/line of pure wrapper ≈ ~26k cycles/frame once
    per-line HInt is active (OJZ parallax end-state). Zero handlers exist yet — this is the
    cheap moment.
11. **aabb #1** — split the template into three composable comptime pieces (byte-neutral
    today); unblocks the rings pre-combined-dims variant (~24+ cycles/ring) and the
    collision coarse-reject variant as pure recompositions.
12. **dplc D1 + load_object L1** — both `movem` pairs save registers their callees
    contractually preserve (~575 cycles per Sonic frame change; ~76/spawn, matters in
    entity-window spawn storms). **dplc D3** — hoist the frame-unchanged check into callers
    (~65 cycles/frame/DPLC character).
13. **vdp_init M1** — `Flush_VDP_Shadow` is per-VBlank, NOT init-only: early-exit shift walk
    saves ~600 VBlank cycles on register-dirty frames.
14. **section M1** — build-time per-act row-pointer table for `GetSecPtrXY`/`FlatIDXY`
    (~50–200/frame, grows with mega-act grid heights). **M2** — drop the double
    caller/callee checks between section and plane_buffer producers (~100–250 on max-scroll
    frames; keep the CALLER's check — the tracker desyncs if the callee's is kept instead).
15. Everything filed Medium/Micro in the per-file sections, opportunistically.

## Correctness findings surfaced by the review (not optimizations — triage these)

- **sprites PB1 (real bug):** `InitSpriteSystem` zeroes `Sprites_Rendered` every frame, so
  `Render_Sprites`' `.empty_table` had-sprites→none trigger is dead — the hidden terminator
  is never written and the previous frame's SAT persists in VRAM (**frozen ghost sprites**).
  Same in the `.asm` twin.
- **sprites PB2 (real bug):** scanline-budget band index is computed from *biased* Y
  (screenY+128) but treated as raw screen Y — bands shifted by +4, budget heuristic
  effectively non-functional over most of the screen. Comment stale post camera-bias fold.
- **sprites PB3:** `sprSize` w/h swap in `engine/macros.asm:21` **confirmed still present**
  (matches the standing stray-fixes memory). `sprites.emp` itself does NOT inherit it
  (hand-coded constants are correct); latent until the first non-square `sprSize` use.
- **entity_window bug #1:** `ess_ring_left_idx`/`ess_obj_left_idx` are dead state — cleared,
  never read/written anywhere (grep-verified). Delete or repurpose as the trigger cache.
- **entity_window bug #2:** mixed signed/unsigned X comparisons pin a silent world-X < $8000
  assumption — flag against the mega-act/floating-origin work.
- **entity_window bug #3:** `Collected_ClaimSlot` failure silently ignored at
  `BuildEntries:772` — wants a DEBUG assert on Z.
- **tile_cache bug #1:** first-fill lag-skip contradicts its own comment (spurious
  `Cache_Pfx_Lag_Flag` on frame 1 if init took frames). **#3:** `Tile_Cache_GetTile` has
  zero call sites (dead export). **#2:** no DEBUG guard on out-of-window hot lookups.
- **core #11:** `clobbers` on `RunObjects`/`RunObjects_Frozen` omit d7 (both write it).
  **#12:** `AllocDynamic` `.latch_full` rollback leaves a stamped `slot_tag` byte in a freed
  slot. **#14:** full-count check uses `bne` where `blo` fails closed.
- **collision #11:** `touch_test_target` header understates clobbers (d5 written on overlap
  path). **#13:** `Touch_Solid` exact-center tie resolves as "player below".
  **lookup #8:** d3 clobber contract disagreement between `Collision_GetType` and
  `Tile_Cache_GetCollision`.
- **animate:** RF_* comment expressions misuse bit numbers as masks (`$06` ≠
  `RF_XFLIP|RF_YFLIP` as literally written); `.cc_back` has no over-rewind DEBUG rail;
  `Sound_PlaySFX` clobbers-only-d0 license needs re-verification post-SFX-Stage-B/C.
- **rings:** `EntityWindow_EntryForSection` clobber list omits d0 (its own output).

Wave-2 additions (details in the per-file sections):

- **sound_api H-1 (real race, cross-file):** `Sound_PlayMusic` has no "previous request
  consumed" gate — a repost landing while the Z80 is mid-`Snd_LoadSong` tears the 6-byte
  param block AND loses the new request (the Z80 clears `SND_REQ_MUSIC` at load END). The
  SFX slot's drain gate is the correct pattern; music + ping/fade/tempo/sample slots lack
  it (PB-2: latest-wins claim is violated by the read→handle→clear poll shape). Needs a
  cross-file design pass, not a drive-by.
- **game_loop B1 (corruption-class, rare):** `VSync_Wait`'s clear-flag/set-Ready window
  (`vblank.asm:174-176`) lets an unluckily-timed IRQ6 run a full game tick with
  `VBlank_Ready=1` → next VBlank runs full `VInt_Level` incl. the plane drain against a
  possibly mid-fill buffer — the exact torn-drain hazard VInt_Lag exists to prevent. Fix ≈
  mask interrupts around the pair (~34 cycles/frame), which also makes Lag_Frame_Count exact.
- **controllers B1 (hardware-only, unfalsifiable in oracle):** single TH-settle `nop` where
  every reference (S1/S2/S3K, SGDK, plutiedev) uses two. Add the second nop (16 cycles/frame
  total); no emulator models settling, so this can never be caught by testing here.
- **dplc D4 (build tool, live hole):** the 2026-06-17 stray-fix overflow guard was NEVER
  re-applied to `tools/dplc_layout.py` — `write_dplc` silently masks counts, and the
  `--merge-only` path merges runs past 16 tiles with no split → silent art corruption.
  Runtime entry-splitting on the main path IS in place.
- **section B4:** `adda.w` sign-extension caps flat×66 at 32767 → **≤496 sections per act**,
  unguarded — directly relevant to the mega-act goal. **B1:** `RedrawPlanes` right-edge
  tracker unclamped (latent if cache margins grow). **B3:** hardcoded `lsl.w #8` encodes
  SECTION_SIZE_SHIFT−3 with no guard.
- **math B1:** `Sine_Table` declared `[u8]` but word-read — evenness is accidental, not
  enforced; latent address-error.
- **aabb #3/#4:** missing `ensure(cdim != delt)` and read-only guards on `apos` — same
  miscompile class the two shipped `stmp` ensures were added for. **#7:** the "two branch
  widths pinned" comment contradicts the code (only one is pinned).
- **structs/constants twins:** drift-guard coverage verified 100%; `act_descriptor.emp`
  still carries a duplicate local `SECTION_SIZE_SHIFT` mirror that should import the shared
  twin; `test_objects.emp`'s four unguarded mirrors lose all protection when the .asm twin
  dies (Spec-5 pattern).
- **objdef O1:** `vram_art` tile refinement `0..$1FFF` silently permits flip-bit bleed
  ($800..$1FFF); tighten to `0..$7FF` or document.
- **hblank:** ENGINE_ARCHITECTURE.md:1136 understates the no-effect HInt cost ~8×.
- **frames F1 / dplc D5:** offset-table words sign-extend — mappings/DPLC files ≥ 32KB
  index backwards; belongs as fatal checks in the build tools.

---

# Per-file reports (verbatim from the review agents)

## 1. engine/level/plane_buffer.emp

### Process constraints (read first)

- Twin parity: this `.emp` is a byte-isolated port of `plane_buffer.asm`. Any optimization
  must be applied to both twins together (or deferred until the `.emp` is authoritative).
- Preserve the VInt_Lag race fix (b96c861): terminator-word semantics and the order of
  `Plane_Buffer_Ptr` reset vs. drain are load-bearing against mid-fill drain corruption.
- Measure with the lag-frame counter during max-speed diagonal scroll. Producer cost eats
  the main-loop frame budget; `VInt_DrawLevel` cost eats the VBlank window.

### High-impact, conceptual

**1. `Draw_TileRow_FromCache` inner loop — restructure from per-column checks to precomputed
segments.** The current loop does clamp-check, physical-col wrap check, W-cursor wrap check,
and an indexed load *per plane column* (~60+ cycles × 64 ≈ ~3,800 cycles/row). But the
W-walk is fully deterministic up front: W runs `A..R` then `R−63..A−1`, both monotonic, and
the `< Cache_Left_Col` zero region is a prefix of the second run. So the whole row
decomposes into **at most ~5 contiguous segments** (each W-run splits ≤2 ways at the
`TILE_CACHE_COLS` physical wrap, plus one zero-fill segment), computable before the loop.
Each segment becomes a straight `move.w (a0)+,(a2)+` (or `move.l`/unrolled) copy. Estimated
~3,800 → ~1,000 cycles per row. Rows fire during vertical scroll, exactly where lag lived.
**Top candidate for this file.**

**2. Column drain in `VInt_DrawLevel` can use `move.l`.** With autoinc `$80`, a `move.l` to
the data port is two word writes, each autoincremented — two column cells per instruction.
`.drain_col` currently does `move.w`+`dbf` (~18 cycles/word); longword pairs + one trailing
word for odd counts roughly halves the iteration count. Caution: an accidental extra word
past row 63 lands at `$E000` (Plane B), so odd-count handling must be exact.

**3. Precompute the VDP command longword in the producers.** The `lsl.l #2 / addq.w #1 /
ror.w #2 / swap` shuffle runs per entry inside VBlank, twice-duplicated. If producers stored
the ready-made command longword in the entry header (4 bytes instead of a 2-byte VRAM addr),
the drain heads become a single `move.l (a0)+, (a5)` — moving ~26 cycles/entry out of the
VBlank window. Buffer grows 2 bytes/entry (negligible vs. 1536). Also lets the count word be
stored bare (drops the `andi.w #$7FFF`). Interacts with the noted `vdp_comm_reg`
shared-module consolidation.

**4. `Draw_TileColumn` copy loops — hoist the circular-wrap check out.**
`.pA_data`/`.pB_data` do `cmpa.l`+branch **every** iteration (~16 cycles/iter of pure
wrap-checking, up to 64 iterations ≈ ~1,000 cycles/column). Rows-until-physical-wrap is
computable up front from the starting physical row: split into two check-free runs, each a
tight `move.w (a0),(a2)+ / lea 160(a0),a0 / dbf`. Combine with 2–4× unrolling.

**5. Consider DMA drain instead of CPU drain — Aeon-specific opening.** Classic Sonic
engines drain plane buffers with the CPU because VBlank DMA bandwidth is consumed by art
streaming. Aeon's art pool is **fully resident at init**, so runtime DMA budget is
comparatively idle. A 128-byte column via DMA ≈ ~100 cycles setup + ~300 cycles of
bus-frozen transfer, vs. ~700–1,150 cycles of CPU drain. The engine already has a DMA queue.
Trade-offs to verify: queue-slot pressure, per-entry setup dominating for small entries, and
whether total VBlank *time* actually improves. An option to measure, not a directive.

### Medium

**6. `Draw_BG_TileColumn` — build-time transpose of the BG layout.** The strip copy reads
column-major from a row-major 64×32 array (~30 cycles/word × 32). Stored column-major at
build time, the strip is a sequential 64-byte copy — roughly 3× cheaper. Verifier must check
all other consumers of `sec_bg_layout`/`act_bg_layout` (e.g. the initial Plane B fill in
`bg.asm`) before flipping the layout. Short of that: `adda.w #128,a1` → `lea 128(a1),a1`
saves 4 cycles/iter for free.

**7. Zero-fill rows in `Draw_TileColumn` — are they necessary?** When the cache's 60 rows
don't cover the 64-row plane, zero words are buffered AND drained to VRAM every column. If
those cells are truly never visible, clamping the entry count to the cached rows shrinks
buffer usage and VBlank drain. But if the zeros do stale-tile clearing during vertical
transitions, they're load-bearing. Determine empirically (sentinel-overwrite test).

**8. `clr.w (a2)+` in the zero-fill loops is a read-modify-write (12 cycles).** `move.w`
from a pre-zeroed data register is 8 cycles, and `move.l` pairs halve iterations.

### Micro

- `move.w #64,d5`, `move.w #TILE_CACHE_ROWS,dN`, `move.w #PLANE_H_CELLS-1,d2` → `moveq`.
- `Draw_TileColumn`'s `move.w d0,-(sp)` / `(sp)+` pair: d3–d5 are free — use a register.
- `.done: move.w #$8F02,(a5)` restore is only needed after a col entry; row entries rewrite
  `$8F02` even when autoinc is already 2. Marginal; fold into note 3 if done.
- All drain/copy loops are unroll candidates (dbf ≈ 10 cycles/iter overhead).

### Checked and already fine

`lea 160(a0),a0` stride advance optimal; ×160 and ×80 shift-add decompositions correct;
row drain already `move.l`; buffer-full checks reserve terminator space; VDP FIFO won't
stall these writes during VBlank; worst-case buffer occupancy (~11 columns at 136 B) fits
1536 comfortably.

---

## 2. engine/level/tile_cache.emp

### High-impact conceptual

#### 1. `TileCache_FillRow` per-tile loop should be restructured into precomputed contiguous segments
`tile_cache.emp:1415-1464`. The inner `.fr_col_loop` runs **per tile** and re-does, every
iteration: world-col reconstruction (~16c), Head check vs memory (~20c), Left/width clip
(~32c), circular column wrap (~30c), indexed source read (14c), stack-relative row-offset
reload (~36c even on rows with no collision), and double-indexed writes (~14-22c each).
Estimated **~180-250 cycles per tile**; a full 80-tile row ≈ 14-20k cycles, and with
`VFILL_ROWS_PER_FRAME = 2` a vertical-scroll frame spends roughly **30-40k cycles** here
before any decompression — the dominant per-frame cost in the file.

Everything the loop checks is deterministic once the block is known: the intra-col range
that survives Left/Head clipping is computable at block entry, and the circular wrap splits
the destination into **at most 2 contiguous runs**. Source tiles within a block row are
contiguous (`a0 + 2*col`), and so is each dest run. Restructure per block into: compute
`[col_start, col_end)` + wrap split → tight `move.w (a0)+,(a2)+ / dbf` (~22c/tile), with
`move.l` pairing (~13c/tile) when both cursors are long-aligned, and two loop *variants*
selected once per row (collision vs no-collision) instead of the per-tile `2(sp)` test.
Collision bytes are likewise contiguous both sides → `move.b (a0)+,(aX)+` runs.

**Estimated saving: ~5-8× on the copy portion — order 10-25k cycles per vertical-scroll
frame.** Budget-out only happens at `.fr_block_loop` head, so the resume contract
(`Cache_Fill_RowResume_Col` = block-start world col) is unaffected by segmenting within a
block. Verifier must check: wrap split arithmetic vs `Cache_Origin_Col` (off-by-one at the
seam), the transient case where `Head − Left < COLS − 1` during left-fill, odd/even dest
alignment before using `move.l`, and that the collision odd-row gate (`btst #0` at 1329)
still selects the right variant after resume mid-row.

#### 2. Empty blocks pay a ~5,800-cycle zero-fill that a pointer indirection makes free
`tile_cache.emp:343-350`. `.empty_block` writes 768 bytes with `clr.l (a0)+` × 192 (~30c/iter
≈ **5.8k cycles per empty block**). Empty blocks recur at world edges and blank regions —
exactly where max-speed scroll runs.

Because consumers only ever *read* staged data through the slot base returned in `a1`, the
staging system can hold a **per-slot data pointer in RAM** (16 × 4 bytes) written at claim
time instead of always resolving through the ROM `BlockStage_PtrTable` (`:189`). Then:
- **empty block** → point the slot at a single shared 768-byte all-zero ROM block: ~0 cost;
- **raw-direct block** (`:321-341`) → point the slot straight at the uncompressed ROM block,
  deleting the 24-burst movem copy (**~4.0k cycles per raw block**);
- compressed blocks still decompress into the RAM slot as today.

**Estimated saving: ~5.8k/empty, ~4.0k/raw** — up to `BLOCK_DECOMP_BUDGET`(6) × per frame
worst case. Verifier must check: nothing writes through a staged-block pointer
(`CopyBlockColumn` and `FillRow` only read); `FindStagedBlock:213-214` must switch from the
ROM table to the RAM pointer array; slot reuse must overwrite the pointer unconditionally;
ROM block must be `even`. Fallback if indirection is rejected: pre-zeroed `movem.l` bursts
(~3.5k saved per empty block), which also clears the conventions §2.5 `clr.l (a0)` violation.

#### 3. `TileCache_FindStagedBlock` linear probe + per-frame prefetch re-probing
`tile_cache.emp:198-220` and scan sites `1073-1089`, `1165-1183`. Probe ≈ ~250c average hit,
~390c miss. The steady-state prefetch scans re-probe every block col/row of the target line
**every frame even when fully staged** (`:1133-1136` confirms intentional): ~1.5-2.5k
cycles/frame of pure probing in steady scroll, plus the same again from demand probes.

Options, in order of preference:
- **Memoize completed scan targets** (behavior-preserving): when a scan walks the whole
  target row/col with all hits, record (target, Left/Head or Top/Bottom,
  staging-generation). Skip while the memo matches. Invalidate by bumping a generation word
  in `DecompressBlock`'s claim path. Saves nearly the whole steady-state probe cost for ~30
  cycles of check. Verifier: generation must bump on *every* claim including empty/raw; memo
  must die on `InvalidateStaging` and on Left/Head/Top/Bottom movement.
- **Direct-mapped staging** (hash low bits → slot): O(1) probe (~40c) but conflict-eviction
  thrash risk; needs the lag-counter A/B.

#### 4. No DMA opportunity in this file — stated for the record
Every copy targets **68K work RAM**; VDP DMA can only write VRAM/CRAM/VSRAM. The DMA
leverage point is downstream (plane buffer → VRAM).

### Medium

#### 5. `TileCache_CopyBlockColumn` — per-iteration wrap check on a wrap that happens at most once
`:407-414` (NT loop) and `:445-454` (collision loop). Each iteration pays `cmpa.l a3,a2` (6)
+ `blo` (10, common case is the **taken** branch — inverted fall-through per §2.2). The wrap
row is fully deterministic: split into ≤2 tight `dbf` segments — saves ~16c × (≤16 NT rows +
≤8 coll rows) ≈ up to ~380c per call, ~1.5-2k per newly-filled column, plus opens 2×/4×
unroll (rows are even by contract, `:365-368`). Verifier: segment-length math at the seam
row (59→0 NT, 29→0 collision); the plane-B displacement trick (`:440-444`) holds inside each
segment (it does — displacement is position-independent).

#### 6. Hot-lookup arithmetic in `Tile_Cache_GetCollision` (tail-called per collision sensor)
`:156-182`; hot via `collision_lookup.emp` tail call. Whole routine ≈ **200 cycles**. Two cuts:
- **`mul_cache_stride` uses the 40-cycle form when a 32-cycle form exists** (`:111-119`).
  `((x<<2)+x)<<4` (the file's own form (b), `:396-397`) = 32c with the same one-scratch
  requirement. The macro should just BE form (b). Even better: a build-time row-offset table
  (`add.w d1,d1; move.w RowTab(pc,d1.w),d1` ≈ 18c, 30/60 words of ROM) — saves ~22c/lookup.
  Verifier: `ensure(TILE_CACHE_STRIDE==80)` guard moves accordingly.
- **Fold `Left/Origin` and `Top/Origin` into cached biases.** `Cache_Col_Bias = Origin_Col −
  Left_Col` collapses two RAM reads to one. The row side folds too: both `Cache_Top_Row` and
  `Cache_Origin_Row` are kept even, so `((row−Top)>>1) + (Origin>>1) = (row +
  (Origin−Top))>>1` exactly — one bias read + one shift replaces sub/lsr/move/lsr/add (~46c
  → ~22c). Combined ≈ **45-50c/GetCollision (~25%)**. Verifier: bias updated at *every*
  mutation site — `HSlide`, `VSlide`, `VSlideUp`, left-fill origin retreat (`:874-879`),
  `Init`, `Reinit`; recommend a DEBUG assert recomputing from primaries.

#### 7. Prefetch/warmup scans reload loop-invariant act fields every iteration
`.pfx_scan` (`:1077-1080`), `.cs_scan` (`:1170-1172`), `WarmupBelowRow .scan` (`:691-693`):
`movea.l Current_Act_Ptr,a0` + grid loads re-executed per block (~30c/iter). Hoist into a
register that survives `FindStagedBlock` (clobbers only d3-d4/a1). ~180c/frame; trivial.

#### 8. `TileCache_DecompressBlock` sec-id add-loop and ×66 stride
`:283-298`. The `grid_w × sec_y` add-loop is ~14c × sec_y, up to 6×/frame. A build-time
per-act row-pointer table removes the loop; padding `Sec` to a power of two is the stronger
fix (62 bytes ROM per section). Low urgency. Verifier: `section.emp` shares the struct.

### Micro

- **`cmpi.w #$FFFF` after a flag-setting `move.w` → `bmi`** — sites `:749-751`, `:780-782`,
  `:1192-1197`, `:1455-1456` (last one per-tile until finding #1 deletes it). ~8c each.
- **`TileCache_InvalidateStaging` `:230-231`**: `move.l #-1,(a0)+` × 16 → `moveq #-1,d1` +
  `move.l d1,(a0)+`: ~128c, cold. Requires widening `clobbers`.
- **`TileCache_FillAll` zero loops `:527-536`**: `clr.l (a0)+` × 3,600 ≈ 108k cycles at init;
  `movem.l` bursts cut ~3×. Init-only (display off) — conventions-compliance more than lag.
- **Round-robin wrap `:257-261`**: → `addq.w #1,d5; andi.w #BLOCK_STAGE_SLOTS-1,d5` (~10c per
  decompress). Add `ensure` power-of-two.
- **`Tile_Cache_Fill` recomputes Camera swap+shift twice each axis** (`:802-804` vs
  `:813-815`; `:890-892` vs `:903-905`): ~24c/frame each. Trivial.
- **Wrap checks branch-taken on the common case** in `GetTile`/`GetCollision`: 2-4c/lookup;
  only while editing per finding #6.
- **`FillRow` redundant width check `:1429-1430`**: unreachable if `Head − Left ≤ COLS−1`
  invariant holds — verify with a DEBUG assert first, then remove (~16c/tile).

### Possible bugs / comment mismatches

1. **First-fill false lag-skip contradicts its own comment.** `Tile_Cache_Init:496` claims
   "no false skip on frame 1", but `Tile_Cache_Fill:721-735` recomputes from
   `Frame_Counter − Cache_Fill_Last_Frame − 1` with the `$FFFF` sentinel: on first fill the
   flag is set spuriously if any frames elapsed during init (~10 frames documented, `:658`).
   Harmless (one lost prefetch frame), but comment or gate is wrong.
2. **No out-of-window guard on the hot lookups.** GetTile/GetCollision silently read
   adjacent RAM for out-of-window inputs. Conventions §7.7 wants a DEBUG assert/CHK.
3. **Dead export: `Tile_Cache_GetTile` has zero call sites** (grepped whole repo).
   Deletion candidate under "clean, not bolted-on".
4. Header/attribute contracts spot-checked — consistent. The raw-copy cycle comment
   (`:335-337`) checks out.
5. **Load-bearing invisible dependency, self-flagged:** the a5/a6-survive-`DecompressBlock`
   hoist (`:1345-1354`) is one decompressor swap away from silent corruption; endorse the
   checked-clobbers lint the file itself asks for.

### Checked and already fine

Stack balance in `Tile_Cache_Fill` (all paths traced); circular-wrap single-subtract
correctness; `FindStagedBlock` low-word slot arithmetic under 16-bit wraparound;
`.fr_budget_out` resume granularity; `dbeq` probe semantics; sec-id add-loop trip count;
×66 shift pair vs `sizeof(Sec)` ensure; screen+rounding constants; movem burst register
choice; VSlide/VSlideUp/HSlide already O(1) origin-move; frame-budget accounting overhead
(~30c per block-unit) not worth register-threading.

**Priority:** #1 first (measure with lag counter during diagonal scroll); #2 biggest
per-decompress; #3/#6 steady-state trims; rest polish.

---

## 3. engine/objects/entity_window.emp

### High-impact conceptual

#### 1. Per-frame X-scan calls have no cheap "nothing entering" gate
`:901-911` (section loop) + `:1030-1062` / `:1237-1271` (walkers). Every frame, per valid
entry (≤4), the code jsr's into `ScanRingsRight` **and** `ScanObjectsRight`; each call loads
the ROM ptr, ratchet, re-derives the entry cursor, reads the first entry, compares against
the edge, exits. ~150-200c per section per frame (~600-800c/frame) doing nothing most
frames.
**Proposed:** cache "next entity engine-X" per section per list — walker writes the engine-X
of the entry at the ratchet (or `$FFFF` at terminator) into the scan state on exit; the
section loop does `cmp.w cached,d7 / bcs` and skips the call when the edge hasn't reached
it. The two **dead** `ess_ring_left_idx`/`ess_obj_left_idx` fields (see bugs #1) are
perfectly placed storage. `InitSection` clearing them to 0 naturally forces the first scan.
**Est. ~500-650c/frame steady-state.**
Verifier: cache written on *every* walker exit path (`update_idx` and ptr==0 early-out) and
by `PopulateSectionRings` (`:1104` sets the ratchet without running the walker); `RescanY`
doesn't move ratchets; ratchet semantics unchanged; unsigned-compare wrap identical to
today's `bhi`.

#### 2. `Collected_UpdateCenter` re-divides an id its callers just multiplied
`:456-473`, callers `:831-841` and `:1625-1638`. Both callers hold `sec_x`/`sec_y`, call
`Section_FlatIDXY`, and `Collected_UpdateCenter` then reconstructs center x/y from the flat
id by repeated subtraction (up to `grid_h` × ~22c). Widen the contract to take center x/y;
delete the `.div_center` loop. Cold path but free (~350c/slide) and less code.

#### 3. `DespawnRings` recomputes loop invariants per live ring — up to 128 iterations/frame
`:1383-1418`. Per iteration: `lea Ring_Buffer,a0` **inside** the loop (~8c/iter); rebuilds
`index×6` (~16c/iter) + indexed field reads (+6c/access); rebuilds the Y despawn band from
scratch (`:1411-1415`, ~28c/iter).
**Proposed:** walk `a0` backward with `subq.l #6,a0` (keep d5 for `RingBuffer_Remove`);
hoist the two Y band bounds into free registers. **Est. ~50-70c per live ring per frame →
~1,000-1,400c/frame at 20 rings; several thousand worst case.**
Verifier: swap-with-last removal + backward iteration with a walking pointer (swapped-in
entry comes from a higher, already-visited index — pointer must NOT advance past it; walking
backward this holds); `RingBuffer_Remove` clobbers vs hoisted regs.

#### 4. `DespawnObjects`: Y band rebuilt per live object
`:1499-1506`. Same pattern: hoist both band bounds before `.loop` (d6/d7 free). **Est.
~28-36c per live object per frame (~300-700c/frame).** Verifier: the `.despawn` movem window
(`:1510`) — hoisted regs inside a preserved set or re-derived after `DeleteObject`.

### Medium

1. **`Collected_CheckRing`/`Killed_CheckObject` save d0 needlessly around `FindSlot`** —
   `:192-194`, `:239-241`: `movem.l d0-d1` (~52c round trip) but `Collected_FindSlot`
   clobbers d1 only. Save just d1.w (~20c). ~30c per spawn attempt. Verify: d0-preservation
   becomes a contract — document it on FindSlot.
2. **Cache the claimed collected/killed slot pointer per window entry** — every candidate
   funnels through `Collected_FindSlot`'s 9×34-byte linear scan (worst ~300c incl. call).
   Slots are claimed once in `BuildEntries` (`:768-773`) and never move — store the slot ptr
   (or 0) in `EntityScanState`. ~200-300c per spawn attempt. Verify: eviction can't touch a
   window section (2×2 ⊆ 3×3, currently *unchecked* — bugs #3); ClaimSlot failure → cached 0
   → same semantics; `Collected_MarkRing`/`Killed_MarkObject` still FindSlot unless also
   routed through the cache.
3. **`clear_slot_bitmasks` uses `clr.l d16(An)` — conventions §2.5 violation** — `:119-131`
   (expanded `:146`, `:315`, `:515`). ~40-70c per slot clear; cold-ish but codified rule.
4. **`EntityWindow_InitSection` `.clear_mask` uses `clr.l (a2)+`** — `:643-644`, 8 iters.
   Same rule; ~8c/iter. Clobbers widen — check callers' live regs.
5. **`EntityWindow_Init` clears scan state byte-at-a-time** — `:814-818`: 104 × `clr.b
   (a0)+` ≈ 2,300c → 26 long stores ≈ 570c. Init-only. `:815` also fits moveq. Verify:
   word alignment of `Entity_Scan_State`.
6. **`Collected_UpdateCenter` per-slot division loop** — `:487-493`: up to 9 × 16 × ~22c ≈
   3,000+c on a slide frame (the lag-risk frames). Option: stash grid (x,y) in the slot's
   existing pad byte at claim time (x:4|y:4 works for grids ≤ 16×16); compare directly.
   Verify: grid ≤ 16 assert; pad byte unclaimed; park/unpark copies start at offset 2 so the
   byte isn't preserved across park — re-stamped at claim, which is when it's derived.
7. **`EntityWindow_MigrateMasks` re-derives entry×26 per iteration** — `:1550-1561`: d3
   iterates 0-3 sequentially — a stepped pointer deletes the decomposition and is *also*
   clearer. Cold; low priority.
8. **`EntityWindow_Scan` slide gate calls `DeriveWindow` every frame** — `:886`. ~130-150c/
   frame to conclude "unchanged" on ~99% of frames. Store the anchor cell's raw pixel
   trigger bounds at slide/build time; gate on 2-4 raw `cmp.w Camera_X/Y`. ~100c/frame.
   Verify: world-origin clamp (`:688-696`) baked into stored thresholds; recomputed on every
   anchor change (BuildEntries).

### Micro

1. `:877-879` movem of d5/d7 around `RescanY` — d5 save is dead (DeriveWindow clobbers d5
   anyway). Save only d7. ~24c on rescan frames.
2. `:145`, `:154` (`:514` evict path): `move.b #$FF,(a0)` (12c) in loops → hoisted `moveq
   #-1,d0` + `move.b d0,(a0)` (8c).
3. `DespawnObjects` reads `Sst.slot_tag` twice (`:1482`, `:1497`). Load once; tests must
   stay ordered ($FF has bit 7 set). ~8-12c per live tagged object. Verify d1 liveness.
4. `Collected_ParkSlot` `:358-365`: pointer step vs ×33 decomposition is near-wash — the
   *comment's rationale* is wrong, not the code (see mismatches #4).
5. `EntityLoaded_Test/Set/Clear` `:544-586`: ~36c call overhead on ~60c bodies, jbsr'd from
   every spawn attempt and despawn-clear. Inline as comptime fn at ~6 sites; ~100 bytes ROM.
   Only bundled with a broader spawn-path pass.

### Possible bugs / comment mismatches

1. **`ess_ring_left_idx` / `ess_obj_left_idx` are dead state** — declared `:59`/`:61`,
   cleared `:656`/`:658`, **never read or written anywhere else** (grep-verified across
   .asm+.emp; `structs.asm:246,248` matches). No left-edge walker exists. Delete (struct
   shrink — coordinate twins + drift guards `:98,:100`) or repurpose as the trigger cache
   (High #1).
2. **Mixed signed/unsigned X comparisons — latent 16-bit world-extent constraint** — walkers
   use unsigned `bhi` (`:1050`, `:1260`, `:1099`); `DespawnRings` uses signed `blt/ble`
   (`:1393-1395`). Both fine today; `d7 = Camera_X + $4A0` wraps unsigned past `Camera_X ≈
   $FB60`, signed despawn breaks past X = $7FFF. Assumes world X well below $8000 — assert
   or pin to the floating-origin dependency.
3. **`Collected_ClaimSlot` failure silently ignored** — `BuildEntries:772` never tests Z; on
   failure the section runs with no collected/killed tracking. Should be impossible
   (2×2 ⊆ 3×3) but that invariant lives only in a comment (`:447-449`). DEBUG assert wanted.
4. **`Collected_ParkSlot` comment overstates the multiply cost** — `:357`: ×33 is a 2-op
   decomposition; comment gives a wrong rationale.
5. **`TrySpawnRing` buffer-full drop window** — `:1006`: on `RingBuffer_Add` carry, the
   ratchet has passed the ring; retry only on the next 128px coarse-Y crossing or slide. A
   ring can stay missing indefinitely on a flat run with a full buffer. Interacts with any
   despawn-staggering change.

### Checked and already fine

Despawn tail call (`:914-915`); X-sorted early exit in walkers (O(entering), not O(list));
ratchet/loaded-bit idempotency sound; `DespawnObjects` walks the live list (empty slots
zero); movem frame offsets verified; static-camera despawn skip considered and rejected
(objects move themselves out of the band; a ring/object despawn *stagger* is the only
variant worth escalating — needs user sign-off); asr flooring / world-origin clamp /
SEC_VOID / single-axis slide assert all match code; index-register hygiene clean; ×6/×26
decompositions fine.

**Priority:** High #1 (trigger cache, reusing dead fields) → High #3/#4 (despawn hoists) →
Medium #1/#2 (spawn path) → High #2 + Medium #6 (slide frames) → rest opportunistically.

---

## 4. engine/objects/sprites.emp

### High-impact conceptual

#### H1. Frame-data resolution done twice per object per frame — cache the frame offset (and bbox) in the SST
`:77-81` (Draw_Sprite) and `:273-277` (Render_Sprites) — identical resolve chains (~46c
each, ~92/object/frame combined); third copy in the sibling walk (`:361-365`). The caching
infrastructure already exists (`Sst.sprite_piece_count` cached at spawn, refreshed on frame
change via `RefreshSpritePieceCount`). Extending that refresh to also cache the resolved
**frame-data word offset** (2 bytes in SST) makes both hot paths one `move.w
cached_off(a0),d0` + `adda.w d0,a3` (~20c). Caching the 4 bbox bytes too removes
Draw_Sprite's mapping deref entirely on the cull path.
**Est. ~50-70c/object/frame (~1,500-2,000c/frame at 30 objects).**
Verify: SST free bytes near `$25`; every `mapping_frame`/`mappings` mutation goes through
the refresh; stale-cache behavior on mid-frame changes.

#### H2. Emit loop: restructure to stream order; merge size+link into one word write
`emit_piece_loop` `:590-607` + term helpers `:485-581`. Unflipped piece ≈ 136c. The copy
can't be `move.l`-batched (3 of 4 SAT words need per-piece arithmetic), but:
1. **Stream-order processing** — stop front-loading all 4 reads and parking tile/X in a6/a1;
   process each field as read. Flip variants still work (yflip reads Y then size before
   computing; xflip's width re-read via `-6(a3)` still lands on size). **−8-12c/piece**, and
   frees **a1 and a6** (see M2).
2. **size+link word merge** — the mapping's pad byte occupies exactly the link position:
   `move.w (a3)+,d1` / `addq.b #1,d5` / `move.b d5,d1` / `move.w d1,(a4)+` (~24c) replaces
   the ~36c byte sequence. **−12c/piece** for unflipped/xflip (yflip keeps its form).
**Est. combined ~20-24c/piece → ~1,000-1,900c/frame at 50-80 pieces. Hottest loop in file.**
Verify: byte-identical SAT for all four flip variants; pad byte genuinely don't-care;
a1/a6 not live across `Emit_ObjectPieces` (contract `:627-629` says clobbered — they are).

#### H3. Sprite-table DMA is a fixed 640 bytes every dirty frame — patch length to `Sprites_Rendered * 8`
Consumer: `engine/system/buffers.asm:69-72` (`dmaLength(640)`), enqueued on
`Sprite_Table_Dirty` (`buffers.asm:150-153`), set by `Render_Sprites` (`:433`). 640 B of
Critical VBlank DMA (~8.5% of budget) even at 20 live sprites (160 B). Partial DMA is safe —
the link chain terminates at the last written entry. `Render_Sprites.done` patches the
length to `d5<<3` (~20 CPU cycles; saves up to ~480 B critical DMA).
Verify: `Static_Sprite_DMA` layout tolerates runtime length rewrite; had-sprites→none frame
still DMAs the 8-byte terminator (**fix PB1 first**); halved-word-count semantics.

#### H4. Dirty-tracking / static-frame skip is foreclosed by the every-frame link-order flip
`:230-241` — the B2 fairness choice (reverse intra-band order every frame) means the SAT
differs every frame; `Render_Sprites` + full DMA can never be skipped even on static frames.
Design tension only: gating flicker-cycling on "band count > 1" would let static frames
reuse the previous SAT (~10-20k cycles + DMA). **Needs Volence's call — B2 was signed.**

### Medium

- **M1. Drop the per-piece SAT-cap compare by pre-clamping the loop count** — `:603-604`
  (~8c/piece). Pre-clamp `d4 = min(d4, MAX-d5)` (~20c once), plain `dbf`. Strictly safe
  (doesn't trust the cached count). ~200-400c/frame. Verify dbeq→dbf per variant; d5 still
  incremented per piece.
- **M2. Step direction lives on the stack — move to a register freed by H2** — `:236,241`
  push, `:250` `adda.w (sp),a2` (~12c/object), `:408`/`:458` pops. Hold in a6: ~4c/object +
  ~160c/frame, and `.band_limit_pop`'s stack-balancing hazard disappears. Verify a6 across
  `Emit_ObjectPieces` (post-refactor), `InsertSpriteMasks`, `DrawRings` (a6 safe).
- **M3. Fuse `move.w (aN,d0.w),d0` + `lea (aN,d0.w),aN` → `adda.w (aN,d0.w),aN`** — three
  sites (`:80-81`, `:276-277`, `:364-365`), ~8c each; ~16c/object/frame. Subsumed by H1.
- **M4. Draw_Sprite: reorder band-count increment to kill a redundant `lea`** — `:150-155`;
  a1 already holds Counts at `:123`. ~8c/registered object. Verify cascade path (a1 =
  Counts — it is).
- **M5. `lea CellOffsets_XFlip(pc),a0` loaded for all four variants, used by two** — `:632`,
  ~8c/object wasted for unflipped/yflip. Move into xflip instantiations; or drop the table:
  width = `andi.w #%1100,d1` + `add.w d1,d1` + `addq.w #8,d1` (~16c vs ~30c) — faster AND
  frees a0 + 16 bytes ROM.

### Micro

- `:333-337` + `:286` — `render_flags` read 3× per rendered object; one load + `btst #n,Dn`
  saves ~12-20c but register pressure — bundle with a bigger refactor only.
- `:233` — `btst` of cycle-counter parity per band; acceptable, note only.
- `:684-685` (`InsertSpriteMasks`) — `move.w #0,(a4)+` ×2 → zeroed reg; `addi/subi` →
  moveq'd reg. Masks rare — cosmetic.
- x_term X=0 fixup (`:566-570,576-579`) — branchless `seq/sub.b` saves ~2c/piece; fold into
  H2 only.
- `:431` — fine as-is (correctly avoids `clr.b` RMW).

### Possible bugs / comment mismatches

- **PB1. `.empty_table` edge trigger is dead — `InitSpriteSystem` zeroes `Sprites_Rendered`
  every frame** (`:39` vs `:441-442`). Init runs at top of every frame (confirmed in all
  three states), so the had-sprites→none transition never writes the hidden terminator and
  never sets dirty: **previous frame's SAT persists in VRAM — frozen ghost sprites**, the
  exact failure the comment claims to prevent. No other reader of `Sprites_Rendered` exists.
  Same in the twin. Fix direction: remove the init clear (Render_Sprites writes it on every
  path) or a dedicated prev-frame flag. Verify first-frame-ever (both 0 → `.still_empty`,
  fine — VRAM SAT starts cleared).
- **PB2. Scanline-budget band index computed from *biased* Y — bands shifted +4, budget dead
  for the lower 128 screen lines** (`:318-323`). `d3 = screenY + 128` but treated as raw
  screen Y; `lsr.w #5` yields band+4. Sprites at screenY ≥ 96 are never budget-checked;
  0-95 charge the wrong counters; hang-in-from-above sprites escape the `bmi` guard. Soft
  heuristic (B1) effectively non-functional. Twin identical. Looks like a regression from
  retrofitting the camera-bias fold; `subi.w #VDP_SPRITE_Y_OFFSET,d0` or fold −128 into the
  band compare bounds restores it.
- **PB3. `sprSize` w/h swap — still present in `engine/macros.asm:21`, but this file does
  NOT inherit it.** `SPRITE_MASK_SIZE` (`:16`) and `CellOffsets_XFlip` (`:469-474`) use the
  correct hardware interpretation. Current `sprSize` users are all square — latent until the
  first non-square use.
- **PB4.** Minor: `:27` pad wording; `:319` "screen-relative Y" factually wrong post-fold
  (see PB2); `.band_limit_pop` note names DrawRings but mask insertion is also skipped
  (currently harmless).

### Checked and already fine

Index-register hygiene clean throughout; emit dispatch fall-through ordering optimal
(unflipped first); per-piece loop fully unrolled per flip variant, zero JSR per piece —
architecture right, H2 is refinement; camera bias fold good (modulo PB2); d5 byte
increments word-clean; stack balance on empty-band path verified all routes; word-stored
SST addresses correct; SAT overflow impossible (d5 capped at 80 across pieces+masks+rings);
scanline counter 8-byte clear over 7-byte array is explicit pad; a5 as band counter is the
right trade; register contracts hold (Draw_Sprite preserves a0/d7; attributes match bodies).

**Top 3 by expected value: PB1 (correctness), H2, H1. Fix or re-document PB2 before anyone
tunes budget constants.**

---

## 5. engine/objects/core.emp

### High-impact conceptual

**1. `.run_culled` reloads `Camera_X`/`Camera_Y` from absolute RAM for every live entry, and
the abs-value cull is branchy — `:497-511`.** ~50c/axis × 2 × every live dynamic entry.
Fixes: (a) cache camera in d5/d6 at entry, reload only after each `jsr (a1)` — culled
entries (the majority) pay `sub.w d5,d0` (4c) vs 12c; (b) branchless window check: `sub.w
d5,d0` / `addi.w #CULL_DISTANCE_X,d0` / `cmpi.w #2*CULL_DISTANCE_X,d0` / `bhi` — kills the
`bpl/neg` pair. **~10-12c/axis per live entry → ~200-350c/frame at 20-25 objects, scaling
with count.** Verify: camera only moves via dispatched object code (reload-after-jsr
preserves semantics); window math at 16-bit wraparound (same trick as S3K
`Check_Object_Range`); `Sst.x_pos` word read at +2 unchanged.

**2. `DeleteObject` zeroes the live-list entry by linear scan — `:241-273`.** Up to 40
words (~18c/entry → ~720c worst) + 8 pending. "Deletes are rare" per frame on average, but a
delete storm (boss, despawn sweep, multi-badnik explosion) is O(n·m): 20 deletes ≈ 7,000+c
in one frame. Alternative: store the slot's live-list index (tag bit for pending) in a spare
SST byte at append time → O(1) delete. Compact/Drain rewrite the backpointer as they move
entries (~8c/kept entry). Verify: backpointer correct across the latch path
(pending→live), LIFO same-frame realloc, and the §6 "exactly once" invariant (the DEBUG
sweep at `:374-396` rails exactly this). Only if delete storms show on the lagometer.

### Medium

**3. `.run_always` builds the bank word before testing for an empty slot — `:458-462`.**
44c/empty slot; reorder to test-first saves 8/empty at +8/occupied. At ~18 empty / ~8
occupied ≈ ~80c/frame net. Verify flag dependence (beq must test the loaded word).

**4. `RunObjects` sweeps System and Effect pools as two `.run_always` calls (`:429-437`)
while `RunObjects_Frozen` already merges them (`:596-598`), adjacency link-enforced by the
ensure at `:22`.** Merge in RunObjects too: ~54c/frame, and consistency. Verify: only
address-order dependency (preserved); update the ensure message (`:17-22`) which scopes
adjacency to Frozen only.

**5. Missed tail calls (conventions §2.8):** `:451-454` — second `jbsr` + rts → `jbra
DrainDynamicPending` (~24c on reconcile frames; keep the `.no_reconcile` rts); `:598-599` —
`jbsr .frozen_fixed / rts` → `jbra` (~24c per frozen frame).

**6. `ObjectMove`/`ObjectMoveX/Y` as jsr targets — `:619-657`.** ~100-130c bodies behind a
34c jsr/rts — ~25-30% call overhead per moving object per frame. An `.emp` inline macro for
hot object code removes it. Caller-side change; noted for the record.

**7. `DrainDynamicPending` append loop uses indexed addressing + per-entry abs RMW counter —
`:359-365`.** Cursor + register count + one `add.w` after the loop saves ~20+c/entry.
Latch ≤8 entries, drains only on saturated frames — low absolute value, but it's the
conventions' own §2.7 BAD pattern. Verify: count not read mid-loop (it isn't); DEBUG block
sees final count.

### Micro

**8. `move.w #imm,dN` → `moveq`:** `:421` (=1), `:431` (=7), `:436` (=15) per-frame ×3 ≈
12c/frame; `:570`, `:597` frozen; `:58,68,377` init/debug. If pools merge (finding 4), 23
also fits. d7 upper word never read.
**9. `clr.w` RMW on memory — `:253, 271, 368`.** d0 dead at the hit sites — `moveq #0,d0` +
`move.w d0,-(a1)`. Rare paths; consistency.
**10. `DeleteObject` pool-detection branch order — `:206-217`.** Dynamic deletes pay 3
cmpa+branch (~34c) before `.dynamic_pool`. If profiling shows dynamic dominating, reorder
(test System_Slots first, `bhs .upper_half`). ~12c per dynamic delete. Not blind.

### Possible bugs / comment mismatches

**11. `clobbers` omit d7 on both dispatch procs** (`:412`, `:567`) — both write d7
(`:421,431,436`; `:570,597`). Should be `d0-d7/a0-a6` or documented; per conventions §10 the
attribute is compiler-verified from the write set — either the verifier has a gap or these
were grandfathered.
**12. `AllocDynamic` `.latch_full` rollback leaves a stamped `slot_tag` byte in a freed
slot** (`:107` vs `:143-146`) — breaks the "freed slot is all-zeros" state on this rare
path. Harmless today; move the `slot_tag` write after the full-count checks.
**13. `Debug_AssertObjLoop` comment overstates the check** (`:532-534, 550-553`) — rail only
verifies a0 ∈ Object_RAM and d7 < NUM_DYNAMIC, not "a0 = own SST"; a repointed a0 skews the
sweep silently. Fix comment or strengthen rail (DEBUG-only saved-copy compare).
**14. `:120` full-count check uses `bne`, not `blo`** — `blo` is same cost and fails closed
into the latch if the count is ever corrupted past NUM_DYNAMIC.
**15. Header byte counts (`:6`, plain 0x1C4 / debug 0x2EC)** unverifiable in a no-build
review — re-check against the gates when touching the file.

### Checked and already fine

Dynamic walk via spawn-order live list (empty slots cost zero; mid-walk hazards correctly
reasoned + DEBUG-railed); O(1) LIFO free-slot stacks with correct rollback (modulo #12
cosmetic byte); a2 save/restore around dispatch is the cheapest shape given the contract;
`moveq #0` + move for Spawn_Count; `ObjectMove` 16.16 apply is canonical minimum
(fraction-word carry chain forbids the split); `movea.w` sign-extension build-guarded
(`ram.asm:486-487`); `InitObjectRAM` fine (init-only); `clear_longs` comptime unroll
near-optimal within its clobber contract; quiet-frame reconcile gate O(1); frozen pass
already merged-sweep + preserve-contract-exploiting.

---

## 6. engine/objects/collision.emp + engine/level/collision_lookup.emp

(Terrain lookup reviewed together with its tail target `Tile_Cache_GetCollision`.)

### collision.emp — High-impact conceptual

**1. The system+effect fixed sweep scans 24 slots per player even when zero are
collidable.** `:166-172`. ~40c/empty slot × 24 × 2 players ≈ **~1,900c/frame** in the common
case. Maintain a `Fixed_Collidable_Count` word (inc/dec at spawn/delete of system/effect
slots with nonzero `collision_resp` — cold paths in core), skip the segment with
`tst.w`+`beq` when zero. Or a second small live-list. **~1.5-1.9k/frame.** Verify: every
spawn/delete/`collision_resp`-mutation path updates the counter (incl. `Object_ClearAll`style resets); no object clears `collision_resp` in place without bookkeeping.

**2. The `tst.w Sst.code_addr(a3)` gate in the dynamic segment is likely redundant.**
`:40-41` spliced at `:159`. Delete's dynamic path zeroes both the list entry and the SST,
and the walk already null-guards the entry — but `CompactDynamicLive` defends against
"dead-code_addr entries", implying a path that clears code_addr without list-zeroing.
**If handlers may delete OTHER objects mid-walk, the gate protects exactly that case and
must stay — verify before touching.** If removable: ~20c × live candidates × players ≈
~480c/frame at 12 objects. Needs a comptime segment flag on `touch_test_target` (keep gate
for fixed, where it IS the empty-slot filter).

**3. Not-a-finding: the scan is O(players × candidates), not O(N²).** No object-vs-object
pairing; bucketing infrastructure would cost more than it saves at ≤64 candidates ×2
players. No change.

### collision.emp — Medium

**4. Player width/height reloaded from RAM per candidate** (`:47`, `:57`) — loop-invariant
per player, 16c/dimension/candidate. Load once per player into a5/a6 (handlers already must
preserve them). ~300-400c/frame at ~25 candidates, minus one movem save/restore (~60c).
Verify: loads go through a data reg (`moveq #0`+`move.b`+`movea.w`) so 0-255 widths are
safe; update clobbers + twin lockstep.

**5. Coarse delta-first rejection before width loads** (`:46-51`) — reject far candidates in
~48c instead of ~80c, +24c for near ones. Win only if most candidates are far — **measure
first** (§8.2). Template is shared with `rings.asm` — must not silently change ring
behavior.

**6. Segment-shared template prevents per-segment gate tuning** — fixed sweep's discriminant
is `code_addr==0`; dynamic's is `collision_resp`. Comptime segment flag; ~20c per
non-collidable live object. Fallback if finding 2 is void.

### collision.emp — Micro

**7.** `:126` `move.w #NUM_PLAYERS-1,d7` and `:167` (=23) → moveq.
**8.** `:142` `clr.w interact_off()(a2)` RMW → hoisted zero reg (conventions consistency).
**9.** `:40`/etc. `tst.w Sst.code_addr(a3)` — offset 0: check the .lst whether the zero
displacement folds to `(a3)` (8c vs 12c); if both twins already emit `(An)`, non-finding.
**10.** Dispatch double-jump (`:82-85` + bra.w table `:191-205`) costs +10c/overlap — the
stride is declared load-bearing ABI; **not worth changing**, noted for completeness.

### collision.emp — Possible bugs / mismatches

**11.** `touch_test_target` header (`:34`) says "clobbers d0-d4, a0-a1" — overlap path also
writes **d5** (`:92`, the Y-cache reload, by design). Comment fix.
**12.** Unused import: `NUM_DYNAMIC` (`:7`). Lint-level.
**13.** `Touch_Solid` exact-center tie (`:271-273`): `delta_y == 0` resolves as "player
below" (snap under, y_vel untouched). Stub-era; decide the `beq` tiebreak when Touch_Solid
becomes real. Flag only.
**14.** Documented `delta == -32768` `neg.w` hazard inherited from aabb template
(`aabb.emp:63-66`) — unreachable via current callers; re-check for any future unbounded
caller.
**15.** a4 saved via single move.l pair, invisible to the movem-based S2-D6b preserves
check. Correct as declared; noted.

### collision.emp — Checked and already fine

Live-list dynamic walk (empty slots zero; entity window is the spatial prune — right
design); d4/d5 player-position caching with fresh-cache fast path; `movea.w` stashes of
combined_w/delta_x; jump-table dispatch; AABB math shift-based, no mulu/divu; movem fires
only on overlap; dbf loops + correct fall-through senses on the hot rejection path;
unrolling the 24-slot sweep considered and rejected (finding 1 removes the loop instead);
Touch_Solid integer-word writes into 16.16 coords correct.

### collision_lookup.emp (+ Tile_Cache_GetCollision) — High-impact

Current per-lookup ≈ **~322c** (~114 in `Collision_GetType`, ~208 in the tail). At 6-20
calls/frame ≈ 2-6.5k cycles/frame.

**1. Fuse `Collision_GetType` with `Tile_Cache_GetCollision`** — the four-compare bounds
check (`:23-36`, ~80c) re-reads what the tail re-derives (`tile_cache.emp:157-167` re-reads
`Cache_Left_Col`/`Cache_Top_Row`), plus the `jbra` (10c). Replace with the unsigned-span
trick producing the window-relative coordinate as a side effect:

```
lsr.w #3, d0
sub.w Cache_Left_Col, d0
cmp.w Cache_Col_Span, d0        ; span = Head-Left+1, maintained at fill/slide
bhs .cgt_air                    ; negative → huge unsigned → rejected too
```

then continue straight into wrap+index with d0/d1 already relative. Eliminates ~40c of
compares/branches + ~24c duplicate subs + 10c jbra. Combined with #2-3: **~80-100c/call
(~30%) → ~600-2,000c/frame.** Cost: `Cache_Col_Span`/`Cache_Row_Span` RAM words written at
every edge-var commit site (`Tile_Cache_Init`, per-column/row commits at
`tile_cache.emp:844,873,944,985`, H/VSlides). Verify: ALL writers found (fill commits
mid-frame); `Tile_Cache_GetCollision` has no other callers (grep found none — re-verify);
`Tile_Cache_GetTile` same treatment or consciously left; twins + byte gates; DEBUG-boot
self-tests.

**2. Precompute the halved collision-row origin** — `tile_cache.emp:165-167` does
`move/lsr/add` (24c) per call on a value that changes only at V-slides/init: store
`Cache_Origin_Coll_Row` (= origin>>1). **~12c/call**, frees d2. Verify: every
`Cache_Origin_Row` writer updates it (`Init:479`, VSlide, VSlideUp).

**3. Replace ×80 shift-add with a build-time row-offset table** — `mul_cache_stride` (40c) →
`add.w d1,d1; move.w Row80Tbl(pc,d1.w),d1` (18c; 120 bytes ROM shared with GetTile).
**~22c/call**, and removes the scratch-register requirement (the reason layer rides in d3).
Conventions §1.8/§2.1. Verify PC-relative reach; CopyBlockColumn's inline ×80 is loop-setup —
leave it.

**4. Caller-side caching: the extension probe repeats the entire lookup for a cell one step
away** — `player_sensors.asm:83-121`: up to 2 calls/probe at exactly ±16px, ~330c each.
Options (API change, game-side file): (a) pointer-return variant — `out(a0)` = resolved cell
byte address; extension cell is ±TILE_CACHE_STRIDE or ±2 bytes away (~14c) **when no
wrap/window seam is crossed** — the seam fallback is the hard part and the thing to prove
(naive offset walks off the circular buffer); (b) cheaper/safer: pass the already-shifted
tile col/row between the two calls. **~300c per extension call — the biggest number in the
pair if the seam handling is right; also the riskiest.**

### collision_lookup — Medium/Micro

**5.** Layer plane-select branch (`tile_cache.emp:175-178`): carry the layer as a pre-scaled
word (0 / TILE_CACHE_COLL_SIZE) via a 2-entry table at probe setup → single `add.w d3,d1`
(~10-16c/call). Touches the register convention + every d3 producer — only bundled with #1.
**6.** `lea Tile_Cache_Collision,a0` is absolute-long because the buffer lives in the
`$FFFF0000` phase — unavoidable; noted so nobody "fixes" it to `.w` and crashes.
**7.** Wrap-branch sense: current shape already cheapest for an 80-column buffer. No change.

### collision_lookup — Possible bugs / mismatches

**8.** `Collision_GetType` declares `clobbers(d1-d3/a0)` but neither it nor the tail writes
d3 (deliberate contract reservation, but the callee's attribute disagrees — make them
consistent; conventions §10 sources attributes from the write set).
**9.** Evenness invariant (`Cache_Top_Row`/`Cache_Origin_Row` even) is load-bearing and
enforced only by convention — DEBUG asserts at the write sites recommended.
**10.** Signed `blt/bgt` on world tile coords — fine while world pixel X < $8000; re-check
in the mega-act/floating-origin work.

### collision_lookup — Checked and already fine

Shift-based, no multiply; `jbra` tail call; air-reject ordering (all four compares fall
through in-window); single conditional subtract for circular wrap (verified against
constants: max 158 < 160, max 58 < 60); indexed final fetch at the leaf is the right trade;
`moveq #CTYPE_AIR`; layer-in-d3 rationale matches code.

### Suggested priority (both files)

1. Fixed-sweep skip counter (collision #1) — biggest guaranteed win, smallest risk.
2. Lookup fusion + span vars + row table + halved origin (lookup #1-3) — one coordinated
   rewrite of the hot leaf, ~30%/call.
3. Player dim caching in a5/a6 (collision #4).
4. Extension-probe pointer caching (lookup #4) — largest potential, needs careful seam
   design; after #2 settles the leaf's shape.
5. Rest micro or conditional on verification (code_addr gate, delta-first reorder — measure
   first).

---

## 7. engine/objects/animate.emp + engine/objects/rings.emp

### rings.emp — High-impact conceptual

**R1. The priority-1 question — layout scan is already incremental. No finding.** Spawning
is the entity window's ratchet; collected rings are removed immediately (swap-with-last) so
they cost zero afterward. This is the sorted-layout + persistent-cursor O(delta) design.
Worst case at the 128 cap ≈ ~10k (DrawRings) + ~10k (RingCollision, 1 player) ≈ 17% of frame
(est.) — acceptable; R2/R3 cut a meaningful slice.

**R2. `DrawRings` — the camera-bias fold is on the wrong side: fold for the CULL, not the
SAT write.** `:177-217`. The fold (comment `:171-176`) makes `sub.w d6,d2` yield final SAT
X — then `:206-207`/`:214-215` spend `move.w d2,d0` + `addi.w` **per ring per axis** to undo
it for the cull, which runs for EVERY scanned ring; the SAT write only for visible ones.
Invert: bias d6/d7 by `Camera − RING_WIDTH/2` so d2 is directly the cull value (cmpi
constants unchanged), convert to SAT only on the emit path. Strictly non-negative;
**~12-24c/ring, up to ~2.5k/frame at a full buffer.** Verify: (a) cmpi bounds literally the
same; (b) the X=0 sprite-masking test (`:226`) must move AFTER the SAT conversion; (c)
update the fold comment, which currently argues the opposite tradeoff.

**R3. `RingCollision` — loop-invariant player dimensions reloaded per ring.** `:283-295`.
~20c of setup per iteration + template `add.w`s — player width/height and the ring's 16px
are constant across the whole loop. Precompute combined dims once per player, pass as
pre-combined `cdim`. **~24c/ring/player on X, ~24 more on X-passers; ~3k/frame at 128
rings.** Needs an `aabb_axis_test` variant taking `cdim` preloaded (current template
consumes adim/bdim, `aabb.emp:15-17`). Register plan: d3/d0 combined dims, d1 delt, d2 stmp;
collect path clobbers d0-d3 → re-derive after collect (rare, ~30c), reload section/list from
`4(a3)/5(a3)`. Verify: aabb alias ensures (`aabb.emp:52-53`); collect path reloads
everything; twin lockstep.

### rings.emp — Medium

**R4.** Sprite-cap check at loop top for every ring incl. culled (`:196-197`, ~16c/ring) —
move to just before the SAT write. Behavior change: at cap, remaining buffer is
scanned-and-culled instead of abandoned (already an overflow frame). Verify against
`sprites.emp:451-457` (B2): the invariant is "no EMIT at cap", not "no scan at cap" —
preserved.
**R5.** Pack size+link into one word write via a biased d5 (`:222-224`): d5 carries
`$0500|count`; pair becomes `addq.b #1,d5` + `move.w d5,(a4)+`. ~12c/emitted ring −16 fixed;
wins from 2 visible rings. Verify: d5 is in-out shared with `Render_Sprites` (`-5(a4)`
fixup + `Sprites_Rendered` at `sprites.emp:428-432`) — unbias on EVERY exit path incl. early
`.done`; link semantics unchanged.
**R6.** `RingBuffer_Add` `andi.b #$FE,ccr` (20c) → `moveq #0,d4` (4c) clears C too; must sit
after the branch join exactly where the andi is (the `.not_record` path arrives with C
possibly set from `cmp.b/bls`). `.full`'s `ori.b #1,ccr` (20c) → `moveq #-1,d4; add.b d4,d4`
(8c), cosmetic. Spawn-time.

### rings.emp — Micro

- `:68-69` count RMW + reload → d4 still holds old count: `addq.b #1,d4; move.b d4,Ring_Count`
  (~8-12c). Spawn-time.
- `:56-58` ×6 via stack (24c) vs RingCollision's register chain (16c) — needs one more
  scratch (widens `clobbers(d4,a0)` — both entity_window call sites tolerate it).
- **Entry stride 6 → 8**: every ×6 chain becomes shift+add and entries long-align — but the
  per-frame loops walk by pointer (`addq #6` = `addq #8`), so this buys ~40c per
  spawn/collect, not per frame. +256 B RAM; the `ensure` pair at `:33` makes the change
  loud. Only if RAM is free — check `ram.asm` end margin.
- `:109-123` `RingBuffer_Remove`: compute `(last − remove) × 6` once, derive `a1 = a0 +
  delta` (~20c). Collect-time.
- `:160` timer reset → moveq; `:186` `lsl.w #2,d4` → `add.w d4,d4` ×2; `:259` player count →
  moveq. Once/frame each.
- `:204,212,233` buffer reads → post-increment with split skip paths (~4c/ring reaching Y
  test); only if touching the loop for R2.

### rings.emp — Possible bugs / mismatches

- `:249` header cites `EntityWindow_EntryForSection` as "d1/a0" — it also writes **d0** (its
  output, `entity_window.emp:605,608`), and its own `clobbers(d1,a0)` omits d0 despite the
  tranche-3 rule. Harmless here (d0 dead); fix both the citation and the contract.
- `RingBuffer_Remove` leaves the vacated last slot stale (`:125-126`) — all consumers bound
  by `Ring_Count` (verified incl. the DEBUG nodup scan); noting for future whole-buffer
  debug tools.
- Cull boundary inclusive-by-one (`bhi` at `:209,217`): one sprite of slack at the exact
  edge — standard classic-engine behavior, documented not bugged.

### rings.emp — Checked and already fine

Buffer-only design + immediate collect removal (the R1 concern); global spin timer + attr
computed once per frame; rolling a3 + backward iteration vs swap-with-last removal verified
(removal only rewrites an index ≥ cursor, already visited; both-players case re-derives
count); `tst.w code_addr(a2)` correct (word field at Sst+$00); x_pos integer-word extraction
correct; aabb $8000 note bounded by the window; dbf/moveq/pointer-walk/X=0 guard per
convention.

### animate.emp — High-impact

**A1. No script re-parsing per frame — steady state lean (~100c/object); pointer re-derived
only on expiry (~34c).** Caching a script pointer in SST would buy little. **However:** the
common *static looped object* (single-frame script) pays ~150+c per expiry to change
nothing. A2/A3 = the cheap 80% fix; the 100% fix (static-art objects don't call
AnimateSprite, or a "held" sentinel parks the timer) is a game-side authoring pattern —
docs note, not engine change.

**A2. Dirty-check `mapping_frame` before `RefreshSpritePieceCount`.** `:100-102`.
`.set_frame` unconditionally writes + calls Refresh (~60-70c) even when the frame is
unchanged — every expiry of a single-frame loop, every same-frame `AF_BACK`. `cmp.b
Sst.mapping_frame(a0),d0; beq.s <rts>` costs ~14 when changed, saves ~60 when not. Verify:
`prev_frame` ($24) is the DPLC field, NOT what Refresh keys on; confirm nothing relies on
`sprite_piece_count` being rewritten when the frame value is unchanged (an object poking
`mappings` mid-anim would now miss a refresh; check `player_common.asm:718`).

### animate.emp — Medium

**A3. Tail-call `RefreshSpritePieceCount` from `.set_frame`** (`:100-104`) — textbook §2.8
tail call; split labels (timer path's `bpl .done` keeps its own rts). ~24c per
frame-advance. Combine with A2.
**A4. Event handlers RMW `anim_frame` in memory, then `.after_event` reloads it**
(`:213,226,232,249 → :252-254`) — d1 already holds the pre-event frame: `addq.w #N,d1` per
handler, one write-back in `.after_event`. ~16c/event. **Exception:** `.evt_callback` (the
callback may clobber d0-d2) keeps the memory form. Verify: scripts < 256 bytes so word addq
can't diverge from byte semantics; every handler exits through the write-back.

### animate.emp — Micro

- `:85-86` timer check: `bmi .expired` + inline rts makes the common not-expired path
  not-taken (2c/object/frame); only with the A3 restructure.
- `:123-124` `neg.b` → `not.b` maps $FF→0, drops the `-4` displacement; cycle-neutral,
  2 bytes smaller. Cosmetic.
- `:270-271` null check idiom is correct as-is (movea doesn't set flags).
- The five duplicated fetch-and-dispatch blocks are deliberate speed-over-size — do not
  common up.

### animate.emp — Possible bugs / mismatches

- **RF_* comment expressions misuse bit numbers as masks** (`:74`, `:77`, header `:73-75`):
  `RF_XFLIP|RF_YFLIP` = 3 as literally written (bit numbers 1,2), not $06. Code correct;
  comments should read `(1<<RF_XFLIP)|(1<<RF_YFLIP)`. Better: derive the masks via
  `function`/const from the bit numbers (both twins).
- **`.cc_back` has no over-rewind rail** (`:161-166`) — N > anim_frame+1 wraps toward $FF
  and the next fetch reads up to 255 bytes past the script. DEBUG-rail backlog / typed-script
  DSL item. Do not fix in this pass.
- Known documented hangs (frameless `.cc_end` loop `:145-150`; AF_CHANGE-to-self `:176-182`)
  already ledgered in-file.
- **`.evt_sound` exhaustive-license comment** (`:220-223`) claims `Sound_PlaySFX` clobbers
  ONLY d0 — NOT independently verified; the 2026-07-03 SFX work resized SfxChannel and moved
  contracts. Re-confirm before applying anything here.

### animate.emp — Checked and already fine

Control-code dispatch already a pc-relative jump table with pinned 4-byte `bra.w` slots;
index-register hygiene clean at all five fetch sites + `.evt_set_field` railed;
`reload_anim_timer` template correct with lockstep note; `.evt_callback` bank-address build
and `$xx00` tst.w comment correct; flip propagation unconditional-copy is cycle-neutral vs
all alternatives costed; `AnimateSprite` clobber declaration matches the write set.

### Suggested priority (both files)

1. **R2** (cull-side fold) — per-frame, strictly non-negative, one routine.
2. **R3** (hoist player dims) — largest per-frame save; aabb variant + twin care.
3. **A2+A3** (dirty-check + tail-call) — big for static looped objects.
4. **R4, A4** — small trims.
5. Comment fixes (RF_* masks, clobber lists) — zero-risk.
6. Micro, opportunistically.

---
---

# WAVE 2 — per-file reports (verbatim from the review agents)

## 8. engine/level/section.emp

### High-impact conceptual

**H1. `Section_UpdateColumns` has no idle early-out — full four-edge pass every frame**
(`section.emp:474-693`). On a frame where the camera didn't cross a tile boundary and no
streaming is pending, the routine still executes the 10-register movem save/restore (~180c,
see H2), camera loads, the act-boundary clamp, three clamp chains per horizontal edge, two
per vertical edge, four loop-entry checks, and four cross-clamp blocks — **~500-600c/frame
doing nothing**. Conventions §7.6 applies. *Proposed:* a convergence gate — after a pass
where all four `Section_*_Written` trackers equal their needed values, set
`Section_Stream_Converged`; clear it when (a) camera tile coords change (~30c compare),
(b) tile_cache commits a new Head/Left/Top/Bottom (one `sf` at each commit site —
cross-file hook), or (c) `Section_Plane_Dirty` fires. Gate check sits AFTER the dirty
check. ~450-550c on every idle/sub-tile-scroll frame (majority of gameplay); zero on
max-scroll frames — buys headroom, doesn't move the lag counter. *Verifier:* a
camera-tile-only compare is INSUFFICIENT — a pass that exits early on the buffer-full
checks (`:531`, `:583`, `:626`, `:666`) with the camera then stopping would stall streaming
forever under a naive gate; convergence must be trackers==needed. Teleport/rebase paths
must dirty the gate.

**H2. The `.not_dirty` `movem.l d2-d7/a0-a3` contradicts the declared contract and burns
~180c/frame** (`:490`, `:691`; twin `section.asm:357/558`). The proc declares
`clobbers(d0-d7/a0-a3/a5-a6)` — every caller already treats those regs as dead — yet the
common path pays save+restore ≈ 180c/frame preserving registers nobody is entitled to. a3
is saved but never used anywhere in the routine. *Proposed:* delete the movem pair.
*Verifier:* every call site for register liveness (the only per-frame caller,
`ojz_scroll_test.asm:187`, has none); consistent register state between dirty/not-dirty
paths.

**H3. Act-boundary clamp recomputed per frame from the Act struct** (`:501-508`) —
~60c/frame for a per-act constant. *Proposed:* build-time `Act.max_tile_col` word in the
descriptor (or cache to RAM at `Section_Init`). ~45-55c/frame and kills the hardcoded-shift
drift trap (B3). *Verifier:* Act struct layout consumers (structs.emp wall, generators);
teleport/act-switch re-read.

**H4. `Section_RedrawPlanes` inner loop pays a per-cell wrap compare that is loop-invariant
per redraw** (`:345-353`, `:382-389`). ~14c × 4096 Plane-A cell writes ≈ **57k cycles
(~0.45 frame)** off the ~3-frame synchronous stall; the wrap point is fully determined by
`Cache_Origin_Row`, constant across all 64 columns. Hoist segmentation out: (seg1, seg2)
counts once per redraw, two straight `move.w (a1),(a6) / lea stride(a1),a1 / dbf` loops per
part with a single `suba.w` between segments; optional 2× unroll adds ~20-30k more. Fires
at level init and cache recovery — user-visible hitch. *Verifier:* segment math for every
start_nt_row/origin_row combination incl. origin_row=0 (seg2 empty); Part A→B pointer
continuation across the seam; `.pla_next` skip paths; verify by redraw-triggered screenshot
diff, not lag counter.

### Medium

**M1. `Section_GetSecPtrXY` / `Section_FlatIDXY` — repeated-add multiply + ×66 chain
replaceable by build-time row table** (`:180-243`). GetSecPtrXY: sec_y × 14c + stack pair
(20c) + ×66 decomposition (~30c); called per frame from `entity_window.emp:747` and
`parallax.asm:79`. FlatIDXY keeps the memory operand INSIDE the loop
(`add.w Act.grid_w(a2),d0` ≈ 22c/iter, `:187-188`); called ≥2×/frame from entity_window.
Tiered: (cheap) hoist grid_w to a register in FlatIDXY (~8c/iter); (better) build-time
`Act.row_pitch = grid_w*66`; (best) per-act row-pointer table → fully O(1). ~50-200c/frame,
grows with mega-act grid heights. *Verifier:* `sizeof(Sec)==66` ensure moves with stride
changes; FlatIDXY's d2/d3/a2-preserved contract (entity_window relies on it); out-of-grid
Z protocol unchanged (entity_window void-cell logic depends on it).

**M2. Redundant double-checking between `Section_UpdateColumns` and the plane_buffer
producers (cross-file).** Per streamed column the caller checks buffer headroom (`:531`)
and clamps to cache bounds (`:511-515`, `:562-566`); `Draw_TileColumn` then re-checks BOTH
(`plane_buffer.emp:79-87`). ~50-60c/column of re-verification; ~200+c/frame at max diagonal
scroll on exactly the lag-measured frames. Same for `Draw_TileRow_FromCache`. *Proposed:*
a trusted entry point (checked public wrapper falling into an unchecked body). *Verifier:*
every other producer call site; **keep the CALLER's check and drop the CALLEE's** — the
tracker (d5) desyncs past a dropped column the other way round.

**M3. Duplicate camera-derived values inside one pass** (`:497-498` vs `:568-570`; `:517-518`
vs `:558`) — `(Camera_X+327)>>3` and `Camera_X>>3` each computed twice; d4 (never used) and
others free. ~40-50c/frame, pure CSE. *Verifier:* register lifetimes across
`jbsr Draw_TileColumn` clobbers.

**M4. Plane B blit loop unrolling** (`:438-440`) — `move.l (a1)+,(a6) / dbf` ×1024 ≈ 31k;
unroll ×8 saves ~9k off the redraw stall. Cold; bundle with H4. *Verifier:* 4096 % 32 == 0;
autoinc $02 at that point (`:435`).

**M5. `RedrawPlanes` per-column stack traffic + VDP-command rebuild** (`:304`, `:326-332`,
`:365-370`, `:407`) — column offset pushed/re-read/popped (~30c/col) though a3/a4 are
declared clobbered and unused; the `vdp_comm_reg` splice (~40c) up to twice per column
could be a swap+`move.w #const` build (~15c). ~2-3k, cold; only inside H4's rewrite.
*Verifier:* moving to a register removes the `.pla_next` stack-balance trap entirely.

### Micro

- **µ1.** `:502` dead `moveq #0,d0` before word-sized uses. −4c/frame (subsumed by H3).
- **µ2.** `:187` memory operand in the `.fxy_mul` dbf loop — hoist (part of M1 cheap tier).
- **µ3.** `:539-542` (+3 siblings) per-column push/pop pair ~24c/col — disappears if
  `Draw_TileColumn` preserved the world col; cross-file API change, bundle with M2.
- **µ4.** `:478` `clr.b Section_Plane_Dirty` → `sf` (house idiom). Cosmetic.
- **µ5.** `:337-340` `moveq #TILE_CACHE_ROWS` silently breaks past 127 rows; add
  `ensure(TILE_CACHE_ROWS <= 127)`. Robustness, zero cycles.

### Possible bugs / comment mismatches

**B1. `RedrawPlanes` Out-doc vs actual d7** (`:262-263` vs `:456`): header says
"start_world_col + 63"; code sets `move.w Cache_Head_Col,d7` unconditionally — no clamp,
asymmetric with d5's left clamp. Safe today only by 80-col cache geometry; if margins grow,
`Section_Right_Col_Written` claims aliased columns as written. Fix header at minimum,
ideally add the min-clamp.
**B2.** Stale comment `:561` "clamp to cache and act bounds" — no act clamp exists there.
**B3.** Hardcoded `lsl.w #8` (`:504`) encodes SECTION_SIZE_SHIFT−3 with no derivation or
guard (file imports the constant and uses it properly elsewhere, `:421`). Derive or
`ensure(SECTION_SIZE_SHIFT - 3 == 8)`; H3 removes the site. Twin shares the trap.
**B4. `adda.w d0,a0` caps flat×66 at 32767 → ≤496 sections per act, unguarded** (`:232`).
`adda.w` sign-extends. No build-time grid-area ensure exists. Mega-act makes large grids
plausible — add a data-gen/`ensure` guard.
**B5.** Contract-vs-body: `UpdateColumns` declares clobbers yet movem-preserves on the
common path (H2 resolves); `RedrawPlanes` declares a3/a4 clobbered but never writes either.
**B6.** `Section_FillInitial` seeding comment (`:148-150`) implies a symmetry that isn't
literal; coverage is correct and gapless. Cosmetic.

### Checked and already fine

No mulu/divu; zero-fill correctly avoids `clr.w` on the VDP port and says so; buffer
reservation math exactly matches Draw_TileColumn's documented worst case; cache-miss
columns skipped before the VDP address is set (stale content survives instead of flashing —
deliberate); dbf everywhere; lea-stride in hot cell loops; Part A/B stack discipline
balanced on all paths; Plane B `vdp_comm` comptime; `cmpa.w #0` null checks correct;
interrupt masking + autoinc restore in redraw matches the VInt cleanup contract.

### Cross-file notes
M2 + µ3 need `Draw_TileColumn`/`Draw_TileRow_FromCache` API decisions — coordinate with the
plane_buffer findings. H1's gate needs one-line `sf` hooks at tile_cache's edge-commit
sites. `Draw_TileColumn` recomputes the full cache-origin pointer per call
(`plane_buffer.emp:91-103`) — identical math to `RedrawPlanes:306-322`; a shared helper or
batched multi-column entry would amortize teleport-refill bursts.

---

## 9. engine/sound/sound_api.emp

### High-impact conceptual

**H-1. `Sound_PlayMusic` has no "previous request consumed" gate — a repost landing
mid-`Snd_LoadSong` both tears the param block and silently loses the new request.**
`sound_api.emp:205-221` writes the 6-byte param block + trigger under one bus hold; the
comment (`:171-173`) claims the Z80 can't read a half-updated block — but that only covers
a Z80 that hasn't STARTED reading. The Z80 handler reads the param block throughout the
load (`z80_sound_driver.asm:1125`, `:1166`, `:1169-1171`, `:1183`) and clears
`SND_REQ_MUSIC` only at the very END (`:1373-1374`). A `PlayMusic(B)` while the Z80 is
mid-`Snd_LoadSong(A)` (a window of order-of-ms) → mixed A/B block (garbage stream) AND the
end-of-load clear wipes B's trigger — the new song never plays. Reachable with two calls
~1 frame apart with unlucky phase. The file already contains the correct pattern for SFX:
`Sound_DrainSfxRing`'s `tst.b SFX_SLOT / bne .dr_done` gate (`:320-321`) is immune.
*Proposed (cross-file, flag for design sign-off):* (a) Z80 side — `Snd_LoadSong` snapshots
the 6-byte block into driver-local RAM and clears `SND_REQ_MUSIC` immediately at entry;
(b) 68k side — `Sound_PlayMusic` spins (bus-held probe, Sound_Init pattern) until
`MUSIC_SLOT == 0` before writing. With (a), (b)'s spin is bounded by the ~20-instruction
snapshot. Either half alone shrinks but does not close the window.
*Verifier:* every `SND_MUSIC_PARAM_*` read moves to the snapshot; the mid-drum
`SND_ROM_BANK` guard (`:1125-1135`) reads the snapshot bank; the 68k spin releases the bus
between probes; latest-wins preserved for posted-not-started.

### Medium

**M-1. `Sound_Init` probe loop starves the Z80 during the boot handshake** (`:132-142`) —
~22 cycles between release and next stop-request gives the Z80 a handful of instructions
per probe; boot handshake stretched ~1-2 orders of magnitude (~0.1s scale, boot-only,
forward progress guaranteed). Insert a short delay (~500c spin) after `start_z80`. Cost:
one clobbered register (currently `clobbers()`). *Verifier:* nothing times boot against a
prompt return; keep the release-between-probes anti-deadlock shape.

### Micro (cold/lukewarm; mirror in the twin)

- **µ-1.** `z80_bank` (`:89-96`): ~66c → `move.l/add.l/swap` ≈ 16c (consumer reads only .b;
  ROM ≤ 4MB). ~50c, cold.
- **µ-2.** `z80_window` (`:97-103`): `(x & $7FFF) | $8000` ≡ `x | $8000` on low 16 bits and
  both consumers use only .b/.w → `move.w/ori.w` ≈ 12c vs ~36. Document dirty high word.
- **µ-3.** `Sound_PlayRing` toggle (`:344-346`): move/eori/move (~32c) → `bchg #0,mem`
  (~20c) with branch flipped to `bne .left` (bchg Z = OLD bit; old=1 ⇒ new=0 ⇒ LEFT —
  matches `ram.asm:411`). Warmest path in the file (ring bursts).
- **µ-4.** `Sound_StopMusic` (`:363`): `move.b #SND_MUSIC_STOP,d0` → `moveq #-1,d0`
  (PostByte writes only d0.b). Also fixes the misleading comment (CM-3).

### Possible bugs / comment mismatches

- **PB-1.** The mid-load repost race — see H-1. Latent; needs the cross-file design pass.
- **PB-2. Lost-command race on all `Sound_PostByte`-class slots (ping/fade/tempo/sample).**
  Z80 poll is read → call handler → clear: a 68k post landing between read and clear is
  wiped — contradicts the stated latest-wins model (`:9`). Cheap Z80-side fix: clear the
  slot immediately after the read (handler works from the copy in `a`). SFX immune; music
  is PB-1.
- **PB-3.** Unstated single-producer/main-loop-only invariant on the SFX ring — verified
  all current callers are main-loop; a future ISR caller would race. One header line wanted.
- **CM-1.** "once/VBlank consume" (`:229`, `:296`) is stale — poll also runs from the
  Timer-A tick during DAC streaming. Conclusions hold; wording should say "once per driver
  frame".
- **CM-2.** `engine/sound_constants.asm:23` still annotates `SND_REQ_SFX` "reserved
  (Phase 1C)" — live SFX mailbox since Phase 5a. Adjacent file, load-bearing slot map.
- **CM-3.** "`$FF` (out of moveq's signed range)" (`:24`, `:363`) — misleading;
  `moveq #-1` puts $FF in d0.b, which is all PostByte consumes.
- **Recency check:** no stale claims found from the SfxChannel-68/7-bit-priority work; the
  "3-deep priority queue" claim matches current `sound_sfx.asm`; `$33/$34` mirrors are
  ensure-guarded.

### Checked and already fine

Z80 stop/start pairing on EVERY path (no early-out leaks a held bus); interrupt masking
around every hold, and the vblank stopZ80 pairs can't nest; grant spin hardware-bounded;
stop-duration already minimized (all derivation before the hold; hold covers 7 byte
writes); param-first/trigger-last matches the Z80's LE reads; byte-only Z80 RAM access;
`Sound_PlaySFX` index hygiene exemplary + data-before-pointer commit + DEBUG flag-threading
correct; drain gate closes SFX races; ring plumbing matches RAM layout; `andi.l #$FF`
sanitizer needed; all ensure guards cover the mirrors; no banked in-frame 68k code.

---

## 10. engine/objects/dplc.emp + load_object.emp + frames.emp + objdef.emp + sst.emp

### dplc.emp

**D1 (high).** Per-entry `movem.l d2-d4/a2-a3` save/restore ≈ ~100c/entry — but
`QueueDMA_Important/Deferrable` clobber only d0-d4/a1-a2, so loop state can live in
preserved regs (cursor a2→a4, dest d2→d5, count d4→d6) and the movem disappears: **~96c/
entry, ~575c per 6-entry Sonic frame change**. Widens the clobber contract to d5-d6/a4 —
legal under the object contract (everything but a0/d7); verify player-path callers
(`sonic.asm:28`, `test_animated.asm:46`, `test_player.asm:259`), update headers + attrs +
twins, confirm carry reaches `bcs` untouched, oracle-soak ObjectTest + Sonic cycling.
*Zero-risk fallback:* drop a3 from the movem set (QueueDMA preserves it) — ~16c/entry, no
contract change.

**D2 (medium).** Entry decode: count extraction + later `lsl.w #5` ≈ 60c → direct byte
length via `andi.w #$F000 / lsr.w #7 / addi.w #$20` ≈ 40c (bits 15-12 = count−1 →
(entry&$F000)>>7 = (count−1)×32; +32 = count×32). ~20c/entry. Boundary-test count 1 and 16.

**D3 (medium, caller-side).** `Sonic_LoadArt` pays full pointer setup + call every frame;
the frame-unchanged early-out fires inside the callee (~100c/frame/character on the
no-change path). Hoist the `mapping_frame != prev_frame` compare into callers via a
comptime template (~65c/frame/DPLC character); the in-callee check stays (drop-retry
semantics depend on it and survive — stale prev_frame keeps the caller's check true).

**D4 (BUG, build tool — the standing overflow-guard question ANSWERED).** The historical
entry-splitting fix IS present (`tools/dplc_layout.py:29-33`, applied at `:205`). The
2026-06-17 stray-fix guard (build-fatal on count>16 / start>4095) is ABSENT: `write_dplc`
(`:146`) silently masks. Worse: `merge_adjacent_entries` (`:120-122`) merges past 16 tiles
with no cap, and the `--merge-only` CLI path (`:190-198`) writes that straight through with
NO split — a 20-tile merged entry wraps to 4 tiles → silent art corruption. Re-add the
raise in `write_dplc` AND cap the merge or split its output.

**D5.** `adda.w (a2,d0.w),a2` (`:43`) sign-extends — DPLC file ≥ 32KB rebases backwards.
Make it a fatal check in the emitting tools.
**D6.** Partial-enqueue commit via the 128KB-split edge (inherited, documented in
dma_queue): a split with one free slot enqueues half and returns carry clear → prev_frame
commits with half the art stale for one frame. Documented out-of-scope; on the record. The
retry design re-enqueues already-delivered entries (idempotent, bounded, doubles that
frame's DMA bytes).

*Fine:* prev_frame committed only after all entries enqueue with per-entry carry checks
(the historical stale-art bug correctly fixed); comptime single-sourcing of the two
priority variants; clobber attr matches body; `andi.l`+`lsl.l` source math optimal.

### load_object.emp

**L1 (high).** The `movem.l d0-d2/a1` around AllocDynamic ≈ ~84c/spawn — but AllocDynamic
is `clobbers(d0) out(a1)`: d1/d2 SURVIVE. Two register stashes (`movea.l a1,a2` +
`move.w d0,d3`) replace it: **~76c/spawn**, ~300-450c in an entity-window spawn-storm
frame. Fail-path note: today `.alloc_fail` restores a1=template; header promises nothing
and no consumer reads a1 on fail — MUST re-verify before dropping the restore. Also verify:
AllocDynamic's write set after any core.emp change; entity_window's documented
"Load_Object preserves d4-d7/a0" survives (restructure touches d0-d3/a1-a3 only); twins;
oracle-verify list spawn + edge-crossing storm + pool-exhaustion fail.

**L2 (micro).** `Load_ObjectList` loop rotation removes an unconditional 10c branch per
entry. Init-time; opportunistic.
**L3.** List-data bits 13-15 trusted by comment only — a DEBUG assert on
`d2 & $E000 == 0` for the list path would check it. Low severity.

*Fine:* 6×`move.l` burst copy optimal (movem alternative ~equal + 6 regs);
swap/clr/move.l position seeding minimal; `rol.w #4` flip fold ensure-guarded; inline
piece-count init deliberately cheaper than calling Refresh (frame always 0 at spawn);
fall-through success paths.

### frames.emp

**F1.** The `{off}.w` index sign-extends — mappings ≥ 32KB indexes backwards. Fatal check
belongs in the mappings build tool. Otherwise fine (3 lines, comptime single-source of the
+4 offset, spawn/frame-change only).

### objdef.emp

**O1.** `vram_art` tile refinement `0..$1FFF` (`:35`) already permits $800..$1FFF silently
setting the H/V flip bits (tile index is bits 0-10; comment only claims palette-bit bleed
above $1FFF). Tighten to `0..$7FF` (engine has 2048 tiles) or document baked-flip intent.
Stricter than the AS twin either way. Otherwise fine: pure comptime emitter; priority
refinement reproduces the macro's fatal; 26-byte ObjDef non-power-of-two irrelevant
(direct pointers, never index math).

### sst.emp

**S1 (micro).** `ObjDef.pad` = 2 dead ROM bytes per archetype buying the clean 6×move.l
copy — correct tradeoff; leave it.
*Fine (verified in detail):* every word/long field at even offset, byte fields packing the
odd slots, `sst_custom` starts even ($2E) with even size; `code_addr` at offset 0 makes the
hottest read in the engine (`tst.w (a0)` per slot per frame) zero-displacement; size $50
non-power-of-two harmless (no runtime index×sizeof anywhere); the 30-entry extern
drift-guard chain + burst-copy ensures are the right build-fatal posture; comments verified
against consumers (dispatch bank build, RF bit map, TEMPLATE_COPY_SHIFT math).

---

## 11. engine/system/ — hblank, game_loop, controllers, math, vdp_init, types

### hblank.emp

**H1 (high).** Dispatch wrapper costs ~116c/line on top of irreducible interrupt cost
(`:18-22`: movem push 3 regs + movea.l abs.w + jsr (a0) + handler rts + movem pop). Null-
handler line ≈ 180c; at per-line HInt (the stated OJZ end-state) ≈ **40k cycles/frame ≈ 33%
of budget with the handler doing nothing**; the wrapper alone ≈ 26k/frame. *Proposed:* ROM
vector → fixed 6-byte RAM `jmp <handler>.l` trampoline patched at install (S3K pattern);
handlers become rte-terminated and save exactly what they use; `HBlank_Null` becomes a bare
rte (180 → 76c/line; a 2-reg handler saves ~56c/line ≈ 12.5k/frame). Also dissolves the
rigid d0-d1/a0 contract. **Zero handlers exist yet (only HBlank_Null at boot) — now is the
cheap moment.** *Verifier:* vector table emits trampoline address; patch atomic w.r.t. IRQ
(single move.l or IE1 off); demo+s4 boot; raster-bar profile once a real effect exists.

**H2.** Future install API must gate IE1 + reg $0A with the pointer swap — 224 null
interrupts/frame ≈ 40k cycles if a null handler is left enabled.

*Bugs/mismatches:* ENGINE_ARCHITECTURE.md:1136 claims ~20c no-effect return — understated
~8× (dispatch ≈ 160c more). No enforcement of the survive-contract on handlers (acceptable;
moot under H1). *Fine:* preserves() matches the movem pair; restore order; rte; pointer
initialized before interrupts enabled.

### game_loop.emp

**B1 (corruption-class, rare).** `VSync_Wait` (`vblank.asm:174-176`) clears `VBlank_Flag`
BEFORE setting `VBlank_Ready`. IRQ6 in that ~16c window: VInt_Lag runs (+1 lag count), sets
the flag; VSync_Wait sees it set and returns immediately → a full game tick runs with
Ready=1 → next VBlank dispatches full VInt_Level including the plane drain against a
possibly mid-fill Plane_Buffer — the exact torn-drain hazard documented at
`vblank.asm:126-136`. Fix direction: mask interrupts around the clear/set pair
(~34c/frame), which also makes the lag count exact. Desk-check all three IRQ landing
positions.
**B2.** `Lag_Frame_Count` exists only in DEBUG builds (`vblank.asm:156-158`) — confirm
deliberate; it's the engine's stated ground-truth metric.
**B3.** The .emp hard-mirrors sonic4's `gameDebugTick` expansion while the .asm twin
expands whichever game's macro is in scope (demo's is empty) — silent divergence if a
game's macro body changes; wants a kill-list assertion tied to the macro body.
*Fine:* lag accounting otherwise sound (Ready cleared on every IRQ → VBlanks landing in the
game-tick span correctly take VInt_Lag); honest clobbers; ~60c/frame loop overhead.

### controllers.emp

**B1.** Single TH-settle `nop` where S1/S2/S3K, SGDK, and plutiedev all use two (`:39,42`).
~1.0µs vs ~1.5µs settle; marginal on worn/third-party/6-button pads. **Emulators don't
model settling — oracle can never falsify this**; the project has no hardware loop. Add the
second nop per transition (16c/frame total). This is a missing-delay flag, not an
optimization target.
**B2 (observation).** TH left low between frames — harmless now; comment the idle-state
assumption when 6-button lands.
*Fine:* edge derivation correct and matches the vblank accumulate/latch protocol; port
control initialized; undriven bits masked; no stopZ80 needed around joypad reads (the
classic pattern is cargo cult — omitting is correct); L+R/U+D guard not worth touching.

### math.emp

**B1.** `Sine_Table: [u8; $280]` (`:37`) is word-read by `GetSineCosine` (`:25,27`) — even
today only by accident of preceding code length; an odd-length blob added earlier in the
section → address error. Retype `[i16; $140]` (also documents signedness) or ensure
evenness. Size check vs sine.bin (640 bytes) correct.
*Fine:* GetSineCosine is the canonical best idiom (S2 CalcSine shape); andi index hygiene;
add.w d0,d0; pc-relative reads; the addi/subi #$80 pair is required (d8 reach + clobbers()
contract both preclude the alternatives). Overlap math verified to the last word ($27E).

### vdp_init.emp

**Scope correction:** NOT init-only — `Flush_VDP_Shadow` (`:44-64`) runs every VBlank
(`vblank.asm:58`, `:124`) inside the ~4,300c VBlank budget.
**M1.** Dirty path walks all 19 slots even for one dirty bit (~38c/clean iteration →
~700+c ≈ 16% of the VBlank budget on any register-touching frame; clean fast path ~20c is
the common case — hence Medium). *Proposed:* shift-walk with early exit (`lsr.l #1,d1` /
`bcs` write / loop while d1≠0) — a lone reg-1 change goes 19 → 2 iterations (~600c). Write
order stays ascending; the btst-mod-32 ensure stays valid. Conceptual alternative if ever
critical: pending ring of ready `$8rvv` words → O(dirty) flush. *Verifier:* ascending write
order unchanged; mask cleared once; demo+s4 boot; lagometer under register churn.
*Micro:* indexed read in the loop is a wash vs (a0)+ with skip-path addq — M1 is the fix.
*Fine:* `clr.l VDP_Dirty_Mask` race-free (Flush is ISR-context; setVDPReg's ori.l is one
RMW instruction); the ≤32 ensure is the right guard; mask comment matches.

### types.emp

Pure-type module, zero bytes emitted — no alignment hazards possible here. Newtype claims
cross-check against consumers; sizes consistent. One unverified doc claim: the HitboxDim
full-dimension rationale (`:43-46`) cites aabb semantics not independently re-derived —
unverified comment, not a suspected error.

### System-cluster priority
1. hblank H1 (decide before any raster handler is written), 2. game_loop B1,
3. controllers B1, 4. vdp_init M1, 5. math B1.

---

## 12. engine/objects/aabb.emp + games/sonic4/objects/test_solid.emp, test_particle.emp

### aabb.emp

**1 (high).** Split the template into three composable comptime pieces (`combine_dims`,
`delta_abs2`, `dim_compare`) with `aabb_axis_test` becoming their byte-identical
composition (byte gates stay green; zero change at today's call sites). This cleanly serves
BOTH wave-1 consumer requests: (a) pre-combined `cdim` variant = delta_abs2 + dim_compare —
rings hoists ~24c/ring/frame on the X test alone (~35% of the reject path), ~24 more per
X-passer; collision X can't use it (target width varies) — exactly why it's a variant.
(b) coarse delta-first variant = delta_abs2 + `cmpi #bound` — collision moves the ~32c dim
setup behind the coarse gate (84 → 52 per coarse-rejected candidate, +4c for passers).
*Verifier:* default composition byte-identical (re-pin gates); variant adoption diverges
from the gate-off AS twins — mirror variant macros into aabb.inc in lockstep or defer
adoption to the Spec-5 twin kill (the split itself is safe now); the stmp-carries-2|delta|
contract between coarse and fine documented + ensure'd.

**2 (option, ABI-breaking).** Branchless interval form `unsigned(2d + c) < 2c`
(add/add/add/cmp/bhs): saves ~6-8c/test, kills the bpl, and ELIMINATES stmp (frees a
register at every splice site, deletes both ensure hazards). Costs: boundary shifts by one
at 2d = −c (not byte-lockable), destroys cdim/delt (breaking the handler ABI — though
Touch_Solid immediately halves them, so a 2×-native ABI is not absurd). Deliberate
decision, not a drop-in.

**3 (medium, correctness).** Missing `ensure(cdim != delt)` — that alias assembles clean
and compares garbage; same failure class as the two shipped stmp guards.
**4 (medium, correctness).** Missing read-only guards on `apos` (`stmp != apos`,
`delt != apos`) — `delt == apos` silently destroys the caller's cached player coordinate
IN the cache register.
**5.** The documented `$8000` edge can become a one-flag variant: `bvs.s {mlab}` after the
double (`:68`) rejects ALL |delta| ≥ $4000 including −32768, 8c not-taken, as a
`guard: bool = false` comptime param. Verify the add's V covers every case; no current
caller enables it (bytes unchanged).
**6 (micro).** Register-`bpos` variant hook — no caller exists; folds into the item-1 split.
**7 (mismatch).** `:24-28` says "the TWO branch widths stay PINNED .s" — `:62` `bpl .aov`
is unsized (only `:70` bhs.s is pinned); the .inc twin spells `bpl.s`. Bytes identical
today (reach forces .s). Amend the comment to "the mlab branch" or re-pin — the file
currently contradicts itself.
*Fine:* reject-as-taken-branch is the floor for an inline template (§2.2 can't apply);
abs shape optimal when delt must survive; lead_move conditional emission correct; boff-0
collapse is a real 4c save rings already gets; instruction ordering cycle-neutral inline.

### test_solid.emp

**1 (micro).** `TestSolid_Main` is a pure per-frame trampoline (~10c/instance/frame to
reach Draw_Sprite). If the dispatcher offset can encode an engine-side target, Init could
store it directly and Main disappears — verify dispatcher signedness + reach + any
"code_addr targets inside the object bank" invariant. Defensible as a teaching template;
add a comment so cloners don't cargo-cult trampolines into heavier objects (that's this
file's real job).
*Fine:* falls_into Init→Main (frame 1 draws without redispatch); clobber declarations
verified against Draw_Sprite; mem-to-mem subtype copy init-only; bare-label-difference .w
dispatch store is the house pattern.

### test_particle.emp

**1 (medium).** Two RMWs on the same byte in Init (`:29,32`) — RF_COORDMODE is bit 3,
priority bits 5-7, no overlap: one
`ori.b #(6<<RF_PRIORITY_SHIFT)|(1<<RF_COORDMODE), render_flags(a0)` replaces both (~20c +
6 bytes per spawn; particles spawn in bursts). More importantly this is the template new
effects clone — split RMWs on one byte is the pattern not to propagate. Verify constant
($C8) and final value in oracle.
**2 (medium, engine gap).** No `ObjectMoveAndFall`: `:47` `addi.w #GRAVITY,y_vel(a0)` RMW
then ObjectMove immediately re-reads y_vel (~15-20c/particle/frame). The file's pattern is
the best available today; every falling effect will repeat it — log the combined routine
(classic S3K shape) as engine work.
**3-5 (micro).** width/height adjacent at $16/$17 → one move.w; x_vel/y_vel adjacent at
$0A/$0C → one move.l; prev_anim($20)/prev_frame($24) NOT adjacent — the two #$FF stores
can't merge (worth knowing so cloners don't assume).
*Fine:* clobber union claim verified exact against all three callees (including the note
that the old set over-declared); jbsr/jbsr/jbra tail; clr.b on RAM fine; anim/subtype
correctly not merged.

---

## 13. Data/definition files (structs.emp, constants.emp, game data)

### engine/structs.emp — CLEAN
All Act/Sec offsets verified 1:1 against the .asm twins; drift wall complete (every named
field guarded; anonymous pad covered by the sizeof guard); no alignment hazards; grid_*_lo
placement correct per the BOUNDARY rule with the <256 claim holding transitively via
act_descriptor's ensure. Struct layout quality moot on 68000 (d16 displacement flat).

### engine/system/constants.emp
- **Consolidation claim vs reality:** `:88-91` says SECTION_SIZE_SHIFT consolidated on its
  3rd consumer — but `act_descriptor.emp:21` still carries its own local mirror + duplicate
  guard (`:26`) instead of `use engine.constants`. Migrate it or fix the claim.
- Stale line reference `:80` (ring constants now at constants.asm:446-448).
- Guard coverage 100% (all ~53 pub consts audited name-by-name); no dead definitions
  (19 sampled, all consumed); spot-checked values all match.

### act_descriptor.emp
- Duplicate SECTION_SIZE_SHIFT mirror (above).
- `:34-35` comment overstates the $8000 failure boundary — the CHECK (`<= $8000`) is
  correct (camera clamp math verified); reword so nobody "fixes" the ensure to `<`.
- The nine `ojz_sec` calls spell each blocks-symbol twice (blocks: + dict: extern) — a
  copy-paste mismatch compiles clean and fails at runtime; the Tier-3 computed-name
  extern() deferral would kill the class. The one convention-held invariant with no ensure.
- Grid-area/section-count ensure verified present (`GRID_W*GRID_H == 9`).

### test_objects.emp
Four local mirrors (VRAM_TEST_OBJ, COLLISION_SOLID/HURT, ENEMY_PATROL_SPEED) carry NO
extern drift guards — rationale is the objdef_port byte gate, which dies with the .asm
twin (Spec-5 pattern). All four values verified correct today. Add four one-line ensures
or document the guard's lifetime.

### Animation data — CLEAN
All 11 sonic script lengths hand-counted correct; AF_BACK rewind matches; ordinal drift
wall complete vs ANIM_*; even-total claims verified; particle single script + terminator +
align verified. One over-specific adjacency comment (sonic_anims `:59-60`) — each file
self-terminates with align 2, so the claim is moot regardless of link order.

### Sound data — CLEAN with two notes
- dac_samples blip bank: 2880-byte placeholder alone in a pinned 32KB window ≈ ~29.7KB ROM
  slack — known-temporary; cleanup candidate when it retires.
- mt_bank SONG_DRUMTEST/SONG_HCZ2 unguarded mirrors have a documented sound rationale
  (ifdef-gated equs); the SongTable order invariant (entry[id-1]) is comment-only — the one
  place a future computed-index ensure would pay.
- Every byte-count claim in all three files verified exact against on-disk blobs (drum-bank
  sum 30908; MT_PITCHTAB_OFFSET equals the actual blob length — the detune guard is armed;
  odd/even blob claims all check out; SFX key range/row count/zero-length banks confirmed).
