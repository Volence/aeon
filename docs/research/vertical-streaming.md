# Vertical Level Streaming / Row Filling Under a Cycle Budget

**Date:** 2026-06-10
**Driver:** The tile cache (80×60, circular both axes) budget-gates HORIZONTAL fill
(`BLOCK_DECOMP_BUDGET = 6` decompresses/frame, partial-column resume via
`Cache_Fill_Resume_Col/Row`) but VERTICAL fill is unbounded: the `.v_bottom_fill` /
`.v_top_fill` loops in `Tile_Cache_Fill` run as many rows as the camera moved, and
`TileCache_FillRow` calls `TileCache_DecompressBlock` with **no budget check**
(`engine/level/tile_cache.asm:892-896` vs the guarded column path at `:774-777`).
Fast falls lag. Planned fix: port budget+resume to rows, cap rows/frame, prefetch in
scroll direction. This doc surveys prior art to confirm/improve/replace that plan.

## Current engine facts (baseline for the math)

- Cache 80 cols × 60 rows of 8px tiles; viewport 40×28; `TILE_CACHE_MARGIN_V = 16`
  rows requested above AND below, but 28+1+32 = 61 > 60, so the bottom edge is
  clamped (`tile_cache.asm:666-672`) — effective margin ≈ 16 top / 15 bottom.
- Blocks are 16×16 tiles (128×128 px). A full-width row fill touches
  ceil(80/16) = 5 blocks, 6 worst case when unaligned/section-straddling.
- Staging cache: 12 slots, 768 bytes/block (512 NT + 256 collision). S4LZ decompress
  ≈ 10–15 cycles/output byte (lz-compression-survey.md) → **~8–12k cycles per block**;
  6 blocks ≈ 50–70k cycles ≈ half an NTSC frame. The budget is a real bound.
- Player terminal velocity `$1000` = **16 px/frame = 2 tile rows/frame**
  (`objects/test_player.asm:33`). The camera has **no per-frame speed clamp**
  (`engine/level/camera.asm` applies full deadzone overshoot) — in normal play it
  inherits the player's 16px cap, but debug-fly turbo exceeds it (the §4.7 lag was
  observed at "up to 3 memmoves/frame" = 6 rows/frame).

## Per-source notes

### 1. S.C.E. (`Engine/Core/Draw Level.asm`) — strongest prior art

- **Delta-based row count, not flags.** `Draw_TileRow`/`Draw_TileRow2` compare the
  16px-rounded camera Y against a stored rounded copy (`Camera_Y_pos_rounded`),
  compute the signed delta, and draw rows for the boundary crossings that actually
  happened ("Draw Level.asm":310-343).
- **`Plane_double_update_flag`** — `andi.w #$30,d2; cmpi.w #block_height,d2; sne` —
  if the camera moved **more than 16px this frame (up to 32)**, a SECOND row is drawn
  immediately after the first. This exists because S3K raises the vertical camera cap
  to 24px/frame. **Speed-based row count with a hard upper bound of 2 — exactly the
  "cap rows/frame" idea, sized to the engine's camera speed contract.**
- Work is emitted into a RAM **plane command buffer** (VRAM addr + length + words),
  flushed by `VInt_DrawLevel` during VBlank ("Draw Level.asm":7-50). Decoupling
  generation (main loop) from VRAM writes (VBlank) — same shape as our plane buffer.
- No decompression in the row path: S3K block/chunk tables are already in RAM, so a
  row's cost is fixed and small. Rows always complete in-frame; **no resume needed
  because the worst case is bounded by design.**

### 2. sonic_hack / Sonic 2 (`code/engines/scroll_camera.asm`)

- **The real guarantee is the camera clamp, not the draw routine.** `ScrollVerti`
  caps camera Y movement at `$200`/`$600`/`$1000` (2/6/16 px per frame) depending on
  state (`scroll_camera.asm:73-137`). The player may fall at 16px/frame; the camera
  never exceeds it. Drawing therefore never needs more than 1 row per direction per
  frame.
- Scroll flags: a 16px-boundary toggle (`Verti_block_crossed_flag`, eor with `$10`)
  sets one bit per crossing (`scroll_camera.asm:296-332`); VBlank-side code draws one
  block row per flag. **This toggle mechanism silently drops crossings beyond one per
  frame** — it only works because the camera clamp makes >16px impossible. Porting a
  flag system without the clamp reproduces our bug.
- **Width-limiting confirmed:** `DrawBlockRow1` draws `moveq #$15,d6` + 1 = **22
  blocks = 352 px** (screen 320 + one block margin each side), NOT the full 512px
  plane width (`scroll_camera.asm:639-700`). Corner cells are covered because
  vertical plane movement also triggers the column draws. Crucially, Sonic's
  **collision reads level layout directly** (ROM/RAM chunk tables per query) — the
  drawn nametable strip does not back collision, so partial coverage is safe for it.
  Our cache backs collision for the whole entity window; this difference limits how
  directly the width-limiting trick transfers.

### 3. Batman & Robin (`disasm/ART_AND_COMPRESSION.md:80-99`)

- Level maps are stored in ROM as **raw VDP nametable words** — "no conversion
  needed — just DMA the data to the scroll plane." Streaming cost per row is a fixed,
  small DMA with **zero decompress** — they bought bounded per-frame cost with ROM
  (892 KB of level nametables). Per earlier research (section-streaming.md:24) there
  is no in-gameplay art streaming at all.
- Lesson: the spike we fight is entirely the decompress. Any scheme that moves
  decompress out of the row-fill critical path (prefetch, staging) approximates
  Batman's "data already VDP-ready" property without the ROM cost.

### 4-6. Vectorman, Gunstar Heroes, Alien Soldier

- Prior survey (section-streaming.md:26-34) found **no streaming symbols** in any of
  them; static per-scene art loads. Vectorman's relevant trick is **64×64-tile planes
  (512×512 px)**: 288 px of vertical slack beyond the 224px screen means nametable
  updates can lag many frames before the seam is visible — **margin as the
  amortization mechanism**. Gunstar/Alien Soldier arenas are small/horizontal;
  nothing applicable to fast vertical streaming.

### 7. Thunder Force IV (`thunderforce4_disasm/ANALYSIS.md`)

- Analysis covers the 20-slot parallax layer system only; no row-streaming
  documentation. TF4's free-scrolling sections use looping/repeating BG bands driven
  by per-layer scroll factors — plane content is largely prefilled and wrapped, not
  streamed against a large unique map. No budget machinery to borrow.

### 8. Ristar (`docs/research/ristar-techniques.md`)

- Confirmed Sonic 1 engine fork — inherits S1's scroll-flag + block-row drawing,
  i.e., the same camera-clamp-backed, 1-row-per-frame model as sonic_hack above
  (raw capstone disasm not re-read; lineage per ristar-techniques.md:63).

### Online

- **SGDK MAP** (`MAP_scrollTo`, [map.h docs](http://www.retropc.net/mm/md/doc/html/map_8h.html),
  [SpritesMind t=3245](https://gendev.spritesmind.net/forum/viewtopic.php?t=3245)):
  incremental row/column updates through the DMA queue; 16×16 metatiles mean **two
  tile rows/columns are updated at a time** via a temp buffer + two DMA transfers.
  First call does a full-plane update (~4KB, explicitly flagged as "you can't init 2
  MAPs in one frame — 7.2KB/frame DMA limit"). For true tile-art streaming the
  community answer is blunt: "**this limits the scroll speed since you can't stream
  too many tiles per frame**" — i.e., the contract is a scroll-speed cap, same as
  classic Sonic. No partial-row resume anywhere in SGDK.
- **SpritesMind "Tile streaming engines"**
  ([t=2122](http://gendev.spritesmind.net/forum/viewtopic.php?t=2122)): Sonic 3D
  Blast streams **rows of tiles (art!) with every movement**, up to 4096 unique
  tiles/level — made viable only by keeping art **uncompressed in ROM** (Batman's
  trade again) and by D-pad-speed scrolling. No frame-budget engineering documented.
- **MDDC "streaming planes" thread**
  ([board.mddc.dev](https://board.mddc.dev/threads/streaming-planes-new-thread.78/)):
  standard column/row VRAM write technique (auto-increment = plane stride for
  columns); generation in main loop into buffers, VRAM writes in VBlank. *"The
  discussion notably lacks mention of per-frame budgets, prefetch margins, or scroll
  speed caps."*
- **Tanglewood** ([gamedeveloper.com interview](https://www.gamedeveloper.com/design/new-game-classic-hardware-developing-i-tanglewood-i-on-a-sega-devkit),
  [repo](https://github.com/BigEvilCorporation/TANGLEWOOD)): 16×16-tile chunked map,
  SLZ (LZ-family) compression, **streams and decompresses one map column at a time as
  the player moves** — the closest homebrew analog to our design. Work is sized to
  complete per movement step; gameplay (puzzle platformer) keeps speeds low. No
  evidence of partial-unit resume.
- **plutiedev / md.railgun.works**: no streaming-budget articles (consistent with
  section-streaming.md findings #9-10).

## Answers to the four questions

**Q1 — How do references bound per-frame work during fast vertical movement?**
They don't bound the *fill*; they bound the *camera*. S2 clamps camera Y to
16px/frame (`ScrollVerti`), S3K to 24px/frame and sizes its drawing for exactly 2
rows (`Plane_double_update_flag`). SGDK and homebrew state the same contract as a
design rule ("can't stream too many tiles per frame ⇒ limit scroll speed"). Batman
and Sonic 3D instead eliminate the variable cost (raw VDP-ready / uncompressed data).
**Nobody decompresses LZ data inside an unbounded per-row loop — our current
vertical path has no precedent because it's a bug by every reference's standard.**

**Q2 — Partial-row resume, or rows sized to always complete?**
Universally the latter: every reference sizes the row unit (22 blocks in S2, one
plane row in S.C.E./SGDK, one column in Tanglewood) so it always completes in-frame,
and relies on the camera cap to bound units/frame. Partial-unit resume appears in no
reference — but none of them pay a variable decompress cost per row. Our own
budget+resume column fill is the only existing implementation of the pattern, and it
is proven (shipped in the §4.7/§4.8 rewrite). Porting it to rows is novel-but-safe.

**Q3 — Width-limiting: fill only the camera band?**
Yes — classic Sonic draws 352px-wide row strips (22 blocks), not the full 512px
plane, and lets the column-draw path cover the corners. BUT its collision doesn't
read the drawn strip; ours reads the cache. Consumers of cache width:
- Plane column/row draws source up to the 64-tile plane width (512 px) around the
  camera — needs ~64 of the 80 cols valid near the seam.
- Collision lookups serve the §4.9 entity window (objects beyond the viewport).
- The 20-col side margins exist as horizontal *prefetch*, not as data anyone needs
  the same frame the row is filled.
So a row fill that covers only the **camera-centered ~64-col plane window** (4–5
blocks instead of 5–6) is safe *if* per-row fill extents are tracked and the
horizontal fill path backfills the outer margins. Saving: ~1–2 decompresses and ~20%
copy per row — real but modest, at the cost of new extent-tracking state and a new
class of "corner hole" bugs (we just fixed one: wrap-twin columns, §4.7).

**Q4 — Terminal-velocity contract (what cap + margin guarantees fill stays ahead)?**
At TV = 16px/frame = 2 rows/frame:
- **Steady-state demand:** a new block row is entered every 128px = every 8 frames;
  it needs ≤ 6 decompresses (≈ 50–70k cycles), then 7 frames of pure staging hits
  (12 slots ≥ 6-block row + in-flight column blocks). Average demand 0.75
  decompresses/frame — far under budget 6. **The problem is the spike frame, not
  throughput.**
- **Margin headroom:** 15 rows below viewport = 7.5 frames at TV.
- **Contract:** rows/frame cap **R = 4** (2 to keep pace + 2 catch-up) with the
  shared budget of 6 guarantees: a fill that falls D rows behind (budget-starved
  spike frames) recovers at +2 rows/frame and can absorb D ≤ 15 before the viewport
  reaches unfilled rows — i.e., up to ~7 consecutive fully-starved frames, which
  cannot occur since a spike frame consumes 6 budget but *completes* the block row.
  Worst realistic case is diagonal max-speed travel (fall at TV + run at X cap)
  where horizontal and vertical fills split the 6-budget in the same frame —
  R = 4 + resume still recovers within the margin. A debug/turbo camera that exceeds
  16px/frame must either (a) be clamped, or (b) route through the existing teleport
  snap path (full refill + `EntityWindow_TeleportShiftY`), as classic Sonic does
  implicitly via its clamp.

## Recommendation

**(a) Planned budget+resume+cap port — CONFIRMED, with two upgrades.** It is the
correct synthesis: S3K proves bounded speed-based row counts, our column fill proves
budget+resume under decompression, and the math above closes the contract. Concrete
shape:
1. `TileCache_FillRow` checks `Cache_Fill_Budget` before `TileCache_DecompressBlock`
   (mirror `:774-777`); on exhaustion store `Cache_Fill_Resume_Row` + column cursor
   and return partial, exactly like the column path.
2. Cap the `.v_bottom_fill`/`.v_top_fill` loops at **4 rows/frame total** (2 pace +
   2 catch-up; keep the 2-row pairing for collision-cell parity). Resume pending rows
   first next frame, re-anchored if columns slid (mirror `:539-543`).
3. **Upgrade 1 — spike smoothing via direction prefetch (improves the plan).** During
   the ~7 quiet frames between block-row crossings, when `Cache_Fill_Budget` is still
   ≥ N after all fill work, pre-decompress 1 block/frame of the NEXT block row in the
   scroll direction into staging (it's keyed by section/block index — no cache commit
   needed). The crossing frame then finds 5–6 staging hits and decompresses ~0–1
   blocks. This converts the 6-block spike into ≤ 1/frame amortized — the closest
   68000 equivalent of Batman's "data already ready" property. Requires bumping
   staging from 12 → 16 slots (one extra block row) or accepting round-robin evict
   pressure; 16 × 768 = 12 KB RAM, check against the RAM budget.
4. **Upgrade 2 — make the camera contract explicit.** Add a camera Y per-frame clamp
   (16px, raise to 24 later with R sized accordingly, à la S3K) OR assert (debug
   build) that camera delta ≤ R×8 px and route larger deltas through the teleport
   refill path. Every reference engine's correctness rests on this clamp; ours should
   state it rather than inherit it accidentally from player physics.

**(b) Width-limited row fills — DEFER.** Genuine prior art (S2's 22-block rows), but
the saving is 1–2 decompresses per spike frame, which Upgrade 1 already removes more
cleanly, and it adds per-row extent state plus corner-hole risk to every cache
consumer (collision, plane draws, §4.9 window). Revisit only if profiling after (a)
still shows row-fill copy cost (not decompress) dominating — then limit rows to the
64-col plane window, never narrower.

**(c) Superior replacements found — none.** The only fundamentally different
techniques are Batman/Sonic 3D's "store it uncompressed/VDP-ready" (rejected: S4LZ
ROM savings are a core engine decision) and Vectorman's "bigger margin" (we already
hold 15–16 rows; growing the cache trades RAM for nothing once the fill is bounded).
The budget+resume+cap+prefetch combination exceeds every surveyed engine's
machinery because none of them ever paid LZ decompress costs mid-scroll.

Sources: [SGDK map.h](http://www.retropc.net/mm/md/doc/html/map_8h.html) ·
[SpritesMind t=3245](https://gendev.spritesmind.net/forum/viewtopic.php?t=3245) ·
[SpritesMind t=2122](http://gendev.spritesmind.net/forum/viewtopic.php?t=2122) ·
[MDDC streaming planes](https://board.mddc.dev/threads/streaming-planes-new-thread.78/) ·
[Tanglewood @ gamedeveloper.com](https://www.gamedeveloper.com/design/new-game-classic-hardware-developing-i-tanglewood-i-on-a-sega-devkit) ·
[Tanglewood repo](https://github.com/BigEvilCorporation/TANGLEWOOD) ·
[plutiedev](https://plutiedev.com/)
