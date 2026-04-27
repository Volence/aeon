# §2 Art & Compression Pipeline Phase 2 — Tile Pipeline End-to-End

**Date:** 2026-04-26
**Scope:** Five sequential layers that take tile art from per-section source data into VRAM correctly, with compile-time deduplication, multi-region packing, graph-coloring, Deferrable streaming, and per-section background art.
**Baseline:** ENGINE_ARCHITECTURE.md §2.1, §2.3, §2.4, §2.5; deferred items "OJZ Tile Art Loading — Full Terrain Visibility", "Build-time Graph Coloring", "Section-aware Streaming / Predictive Preloading", "Section Preload with S4LZ Deferrable DMA"
**Defers:** Dynamic VRAM allocator + refcounting (milestone B), S4LZ mid-decompress preemption (§9.7), velocity-adaptive thresholds (player physics), vertical section streaming (vertical level data), per-section parallax variation (§4.6)

---

## Overview

Phase 1 of §2 (2026-04-24) delivered the S4LZ format, the 68000 blocking decompressor, the DPLC pipeline, and 128KB DMA boundary safety. The runtime can decompress and DMA art correctly. What it can't do yet is assemble per-section tile art into VRAM without clobbering nametables, dedupe identical tiles, share VRAM across non-adjacent sections, or stream art ahead of section transitions. This phase delivers all of that.

The five layers stack: each one builds on the previous and adds a measurable capacity improvement. Each one is its own commit with a build-tool-printed measurement so we can see what it actually bought us. **No layer is skipped on the grounds that "the previous layer was probably enough" — the architecture commits to all five and future zones will need them.**

| Phase | Layer | What it does | Mandatory because |
|-------|-------|--------------|-------------------|
| A.0 | Per-layer research | Each phase opens with research → design refinement → build → verify | CLAUDE.md research checklist; per-component scope preference |
| A.1 | Dedupe + nametable remap | Flatten all section tiles globally, dedupe with hflip/vflip canonicalization, rewrite strips to reference compact indices | Stops nametable clobbering at indices ≥1536 |
| A.2 | Multi-region VRAM packing | Spill into Plane B's off-screen nametable rows when pool overflows | Ceiling raised beyond 1536 tiles |
| A.3 | Build-time graph coloring | Non-adjacent sections share VRAM tile slots | Effective capacity scales with adjacency, not zone size |
| A.4 | Per-section S4LZ Deferrable streaming | Section preload triggers double-buffered streaming via Deferrable DMA | No section transition stutter |
| A.5 | Per-section background art | Tiers 1/2/3 (zone-shared / per-section layout / per-section art+layout) | OJZ has BG today; future levels need per-section variation |

Each phase ends with the same kind of deliverable: a measurement printed by the build tool, a visual verification on the existing OJZ scroll test, and a synthetic stress test where OJZ's data doesn't naturally exercise the new code path.

---

## Phase A.0 — Per-layer research model

Per `CLAUDE.md`'s research checklist (mandatory for every design phase) and stored feedback ("interleave research+build per component"), each of the five layers opens with its own research phase that feeds into a refinement of that layer's design before any code is written. Research scope is implementation-focused, not design-relitigating: ENGINE_ARCHITECTURE.md is the baseline; research either confirms the documented approach or surfaces refinements that update the doc itself before the build proceeds.

Universal research targets per layer:
- All 7 reference disassemblies (S.C.E., Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force IV, sonic_hack)
- plutiedev, md.railgun.works, segaretro, SpritesMind, GitHub homebrew (Xeno Crisis, Tanglewood, Demons of Asteborg, Project MD)
- Modern engine literature where applicable (compiler reg-allocation for A.3, asset-streaming for A.4, etc.)

Per-layer-specific research targets are listed in each phase below.

If a research pass reveals something that contradicts the architecture doc, **update `docs/ENGINE_ARCHITECTURE.md` first**, then proceed to refine the spec/plan.

---

## Phase A.1 — Tile dedupe + nametable remap

### Goal
Stop nametable corruption from indices ≥1536 by globally deduping unique tiles and rewriting per-section strip data to reference the new compact index space. Foundation layer; every subsequent layer assumes it.

### Why this is the foundation (and why stock Sonic 2 didn't need it)
Stock Sonic 2 hand-packs level art to ~288 unique tiles per zone via chunks → blocks → tile indirection. The runtime never writes a high tile index because the chunk/block tables don't contain one. Our pipeline auto-extracts data and currently flattens tile-index space linearly, so tile #1700 in our strips lands at VRAM byte $C800 — inside Plane A's nametable. A.1 does automatically at build time what Sonic 2's artists did manually at authoring time.

### Research targets (specific to A.1)
- S.C.E.'s art tools and SGDK's `rescomp` image converter — battle-tested flip-aware tile dedup
- `programs/flex2` (sprite editor) — internal tile-canonicalization patterns
- Sonic Hacking Contest community tools (mtrmapper, etc.) — 20+ years of tile-dedup tricks
- Aseprite, TexturePacker — modern texture-atlas dedup and flip canonicalization

### Open implementation question (research-driven)
Canonical form for flip-aware dedupe: pick the lexicographically-smallest of the four orientations (none, H, V, HV), or hash-based with a stable tie-break. Both are correct; identify which is standard practice.

### Build tool — extends `tools/ojz_strip_gen.py` (or a new pass that runs after it)
- Walk every section's nametable strip data in OJZ act 1
- Extract every referenced 32-byte tile pattern
- Dedupe globally using hflip/vflip canonicalization (each tile has up to 4 orientations; canonical orientation chosen per the research-driven rule)
- Rewrite each section's strip data: `tile_index` field → new compact index; `H` and `V` flag bits set to recover the original orientation when canonicalization rotated the tile
- **Verify** the strip generator already preserves H/V flag bits in its output. If it doesn't, fix that first as part of A.1 — flip-aware dedupe is impossible without it.

### Build tool deliverables
- `data/generated/ojz/act1/ojz_tiles.bin` — deduped raw tile pool (replaces the current pre-dedupe blob)
- `data/generated/ojz/act1/ojz_tiles.s4lz` — S4LZ-compressed pool (with tile-delta), produced by piping `ojz_tiles.bin` through `tools/s4lz.py`
- Rewritten `secN_strips_a.bin` / `secN_strips_b.bin` referencing the new compact indices
- Build-time printed report:
  ```
  OJZ Act 1 — Phase A.1
  Raw tile references: <N>
  Deduped (no flip):   <M> (X% reduction)
  Deduped (with flip): <P> (Y% reduction)
  Pool fits in 1536:   yes / no
  S4LZ ratio:          <Z>
  ```

### Engine — `LoadArt_S4LZ` API
Replaces the test state's two `QueueDMA_Critical` calls with a real blocking S4LZ → DMA path.

- **Inputs:** `a0` = compressed source ROM ptr, `a1` = decompression work buffer in RAM, `d0` = VRAM tile-slot destination
- **Behavior:** call `S4LZ_Decompress` (already in `engine/s4lz_decompress.asm`), then queue DMA from work buffer → VRAM via `QueueDMATransfer`. For loads exceeding one VBlank's DMA budget, split into multiple queue entries (the queue already handles 128KB-boundary splitting; A.1 adds length-based splitting on top, or routes the load through display-off so multiple Critical-priority transfers run in one extended VBlank).
- **Work buffer size:** sized for the worst-case zone post-dedupe. OJZ post-dedupe is expected ~10-25KB. Reserve a 32KB transient buffer at boot, freed/reusable after `Section_Init` returns.
- **Call site:** new `Level_LoadArt` routine called from `Section_Init` (or before it) — becomes the canonical level-init flow that every future zone uses. The OJZ scroll test no longer hand-rolls DMA orchestration.

### Verification
1. Build-tool unit test: dedupe → re-expand → byte-compare against original concatenated tile data. Must round-trip losslessly.
2. Visual: scroll test renders OJZ section 0 with **all** terrain rows correct, no glitched bytes. This closes the "OJZ Tile Art Loading — Full Terrain Visibility" deferred item.
3. Exodus MCP: confirm VRAM $0000-$xxxx matches deduped pool; spot-check 5 nametable entries on Plane A point at sane tile indices < 1536.

### Out of scope for A.1
- Multi-region packing (A.2). All deduped tiles go in $0000-$BFFF; if the pool overflows, the build tool errors loudly.
- Graph coloring. Pool is one undifferentiated global blob.
- Streaming. One blocking load at level init.

---

## Phase A.2 — Multi-region VRAM packing

### Goal
When dedupe alone overflows the 1536-tile primary pool, spill into Plane B's off-screen nametable rows (~186 additional tile slots). Plane A's off-screen rows stay reserved for character DMA per the architecture doc.

### VRAM map after A.2
- `$0000-$BFFF` — primary art pool, 1536 tile slots
- `$C000-$DFFF` — Plane A nametable; off-screen rows reserved for character DMA (untouched by A.2)
- `$E000-$FFFF` — Plane B nametable; visible rows hold nametable entries; off-screen rows (~186 tile slots) become a second tile region

### Research targets (specific to A.2)
- S.C.E.'s exact off-screen embedding mechanics — VRAM addresses used, character-DMA routing
- Vectorman's 64×64 plane layout — only commercial game shipping this
- plutiedev / md.railgun on conflicts between static art and per-frame DMA in shared regions

### Open implementation question (research-driven)
Whether character DMA's target ever shares with static art via careful scheduling, or strict static/dynamic separation forever. Answer determines how many of Plane A's off-screen rows are usable for art (currently zero per the architecture doc) and whether A.5's character DMA work has 186 fewer tiles to play with.

### Build tool — extends A.1's deduper
- After dedupe, attempt to fit the pool in region 1 ($0000-$BFFF).
- On overflow, spill into region 2 (Plane B off-screen).
- Strip remap accounts for the discontinuity: tile in region 1 has VRAM byte = `tile_idx * 32`; tile in region 2 has VRAM byte = `region2_base + (tile_idx_within_r2) * 32`.
- Emits two pool blobs: `ojz_tiles_r1.s4lz` and `ojz_tiles_r2.s4lz` (the second is empty when no spill occurs — still emitted so the loader contract is uniform).
- Build-time printed report:
  ```
  OJZ Act 1 — Phase A.2
  Region 1 used: <M> / 1536 tiles
  Region 2 used: <K> / 186 tiles
  Effective pool capacity: <M+K> / 1722
  ```

### Engine — `LoadArt_S4LZ` extends to multi-region
- Two calls at level init (or one call accepting a region table).
- Region 2's destination address is computed from VDP register $04 (Plane B base) + visible-row byte offset.
- Build-tool-emitted constants `OJZ_TILES_R1_VRAM` and `OJZ_TILES_R2_VRAM` become destinations.

### Verification
1. Visual: same OJZ scroll test, no regression.
2. Synthetic stress: build-tool flag artificially shrinks region 1 (e.g. cap at 500 tiles) to force spill into region 2, exercising the runtime multi-region loader on data that wouldn't naturally spill.
3. Exodus MCP: confirm region 2 VRAM contains the spilled tile data and Plane B's visible nametable still renders correctly.

### Out of scope for A.2
- No graph coloring across sections — pool is still global, just spread across two regions.
- No per-frame region remapping — once art is loaded, the regions are fixed for the level.
- No use of Plane A's off-screen rows for art (reserved for character DMA in milestone B+).

---

## Phase A.3 — Build-time graph coloring

### Goal
Allow non-adjacent sections to share VRAM tile slots by constructing the section-adjacency graph and coloring it such that simultaneously-visible sections never share a VRAM range.

### The conceptual model
Two sections that can never be on screen at the same time can use the same VRAM slots: section X's art lives in slots 200-450 while X is active; when the camera crosses into a non-adjacent section Y, Y's art overwrites those same slots. The adjacency graph (which sections can co-exist on screen) becomes a constraint graph; coloring assigns each section a VRAM "phase" such that simultaneously-visible sections never share a phase.

### Research targets (specific to A.3)
- Compiler register-allocation literature: Chaitin-Briggs (graph coloring), linear scan, SSA-based — pick what fits our small graph size
- Modern bin-packing literature for the within-color tile arrangement: First-Fit-Decreasing, Best-Fit, optimal ILP for tiny instances
- Batman & Robin's VRAM allocation strategy — most ambitious commercial scheme on the platform
- S.C.E.'s art-loading pipeline — does anything analogous exist?

### Open implementation questions (research-driven)
- **Adjacency definition.** Strict 2D-grid neighbor adjacency, or visibility-based bounding-box overlap. The latter is more permissive (more reuse) but harder to compute and harder to verify.
- **Per-color packing strategy.** All sections in a color class share one VRAM range with their tiles interleaved, or each section in the class gets its own contiguous sub-range with the offset rotated by section.
- **Brute-force-optimal vs heuristic.** With ≤16 sections, brute force is fine for OJZ. Whether to also build the heuristic-fallback path now (for future zones with >100 sections) or defer until needed.

These three are explicitly **deferred to A.3's research phase** — the spec captures them as decisions, not pre-baked answers.

### Build tool
- Compute section adjacency from the act descriptor (`Act_section_grid` fields).
- For each section, compute its post-dedupe, post-flip-canon unique-tile set (carried over from A.1).
- Run graph coloring + bin-packing — each section gets a VRAM offset and a per-section tile order; non-adjacent sections may overlap.
- Emit per-section "art group" metadata: a list of `(section_id, vram_offset, tile_count, source_offset)` describing what to load when this section becomes active.
- The "global tile pool" emitted by A.1/A.2 splits into multiple per-color sub-pools; each sub-pool is its own S4LZ blob.
- Build-time printed report:
  ```
  OJZ Act 1 — Phase A.3
  Adjacency graph: <N> nodes, <E> edges
  Chromatic number: <K>
  Max simultaneously-resident: <M> tiles
  Effective compression: M / Σ unique = <X>%
  ```

### Engine — load the right group, not a global blob
- `Section_Init` loads art for the starting section + its immediately-adjacent set (the initial visibility clique).
- Section transitions trigger loading the new section's art group (still **blocking** in A.3 — A.4 makes it streaming).
- Currently-resident art from outgoing-only sections is overwritten in place, with no allocator (no refcount tracking — that's milestone B).

### Verification
1. Visual: normal scroll test — section transitions don't glitch.
2. Synthetic stress: artificially shrink the pool until graph coloring is forced to alias (otherwise A.3 might be a no-op for OJZ if it already fits). Build-tool flag, not runtime.
3. Build-tool invariant: for every edge in the adjacency graph, the two sections' VRAM ranges must be disjoint. Asserted at build time.

### Out of scope for A.3
- No streaming — A.4 layers on top.
- No runtime allocator / refcounting — milestone B.
- No vertical adjacency handling beyond what the act descriptor encodes (vertical section teleport is in §4 deferred work).

---

## Phase A.4 — Per-section S4LZ Deferrable streaming

### Goal
Replace A.3's "blocking S4LZ load on section transition" with "Deferrable DMA streaming queued ahead of the transition," so the player never sees a stutter when crossing section boundaries. Closes the §4 Phase 1 deferred item "Section Preload with S4LZ Deferrable DMA".

### The flow
1. Camera advances; `Section_Check` (already exists) detects camera approaching a boundary at threshold `SECTION_FWD/BWD_PRELOAD` (already a constant in §4).
2. Preload trigger fires: enqueue the incoming section's art-group decompression + DMA as **Deferrable** priority.
3. Decompressor runs in CPU time during gameplay frames (blocking-mode call from a per-frame system). Output lands in a streaming work buffer in RAM.
4. DMA transfers from buffer → VRAM run in subsequent VBlanks at Deferrable priority — gated by remaining VBlank budget after Critical/Important transfers.
5. By the time camera crosses the boundary, art is in VRAM. Section enter overwrites/aliases the outgoing section's slots per A.3's coloring layout.

### Engine pieces
- **Streaming work buffers — double-buffered.** Two ~4KB regions (8KB total) used in ping-pong, so a fast direction reversal can start decompressing the new section while the previous section's DMA finishes. RAM is plentiful (we eliminated chunk/block tables in §2.5), so robustness against the corner case is cheap.
- **`Section_StreamArtGroup(section_id)`** — new routine. Reads art-group metadata (built by A.3), kicks off S4LZ decompress + DMA queue. Idempotent: if the group is already resident or being streamed, no-op.
- **Per-section state** — small per-section state (e.g. `STREAMING_PENDING`, `STREAMING_BUFFER_A/B`, `RESIDENT`). Lives in existing per-section RAM, **not** the (deferred) allocator's loaded table.
- **Preload trigger hook** — extend `Section_Check` so the existing FWD/BWD threshold logic also calls `Section_StreamArtGroup` for the upcoming section.

### Research targets (specific to A.4)
- S3K dynamic art via PLCs — closest existing pattern for time-budgeted art streaming
- SGDK's `MAP` system — modern streaming reference
- Castlevania Bloodlines, Thunder Force IV — heavy DMA-scheduling commercial games
- S.C.E.'s art-loading flow if it has any streaming logic
- plutiedev / md.railgun on Deferrable-priority DMA scheduling patterns

### Open implementation questions (research-driven)
- Preload threshold value — fixed pixel distance from boundary. Educated guess: 64-128 px (a few frames at typical Sonic camera speed); research/profiling sets the number.
- Decompressor invocation pattern — call from a per-frame system every frame and let it consume a fixed CPU budget; or run to completion in one frame when triggered. Latter is simpler; former handles giant sections more gracefully.

### Compatibility with what's deferred
- **No** mid-decompress preemption. The decompressor runs to completion in one or more frames; if it overruns a frame's CPU budget, it just blocks until done. Cooperative-multitasking-style preemption stays in §9.7 deferred. Worst case A.4 stalls the main loop for one frame on a large section transition — acceptable trade-off for not building §9.7 yet.
- **No** velocity-adaptive thresholds — fixed preload distance per the §4 deferred item, which itself depends on player physics that don't exist.

### Verification
1. Visual: scroll OJZ continuously across all section boundaries, both directions — no stutter, no glitch, no missing tiles.
2. Synthetic stress: force-shrink pool (carried over from A.2/A.3 toggles) so streaming actually fires aggressively, then walk back and forth across one boundary repeatedly to exercise both buffers.
3. Exodus MCP: confirm Deferrable DMA queue depth stays reasonable; no overflow.
4. Profile via §4 frame instrumentation — confirm transitions produce no frame drop. If a regression appears on a big section, tune buffer sizing or threshold.

### Out of scope for A.4
- No interruptible/preemptable decompression (§9.7 deferred).
- No velocity-adaptive thresholds (player physics deferred).
- No vertical-axis section streaming (vertical level data is §4 deferred).
- No runtime VRAM allocator integration (milestone B).

---

## Phase A.5 — Per-section background art (§2.4)

### Goal
Implement all three BG tiers from ENGINE_ARCHITECTURE.md §2.4 end-to-end, validated on OJZ. No tier deferred; each one exists in the design.

### The three tiers
| Tier | Layout | Tiles | Engine cost |
|---|---|---|---|
| 1 — Zone-shared | Single zone-wide BG layout | Shared BG tile region (256-slot fixed VRAM) | Build-tool: emit zone BG nametable + zone BG tile blob. Runtime: load both once at level init via `BG_Init` |
| 2 — Per-section layout | Per-section BG arrangement | Shared BG tile region (same as T1) | Build-tool: emit per-section BG nametable using same shared region. Runtime: redraw nametable on transition |
| 3 — Per-section art + layout | Per-section BG arrangement + section-specific tiles | Section's A.3 art group | Build-tool: BG tiles fold into the section's tile group. Runtime: stream BG art alongside FG via A.4 |

**Shared BG tile region (T1/T2):** Fixed VRAM slots 1280-1535 ($A000-$BFFF), 256 tiles capacity, loaded once at level init and never overwritten by section transitions. Required because A.3's per-section graph-colored FG pool means slots 0-1279 are owned by whichever sections are currently loaded — the BG nametable can't reliably reference those slots. Reserving 1280-1535 gives BG a permanent home that all sections share. Build tool extracts BG-referenced tiles from `OJZ_1.bin`'s BG section (sonic_hack's reference data), dedupes, and emits a `bg_tiles.bin` blob loaded into the region by `BG_Init`.

### Research targets (specific to A.5)
- Thunder Force IV per-stage BG swapping
- Sonic CD per-act BG art and layout
- Castlevania Bloodlines — Plane B usage tricks
- S.C.E. — modern Sonic-style per-act backgrounds
- plutiedev on Plane B nametable swaps

### Implementation decisions (research-settled — see `docs/research/per-section-background.md`)
- **No pre-clear before redraw.** Layouts are full-coverage 64×32 nametables; pre-clear doubles cost for zero correctness benefit.
- **T3 BG tile art shares A.3 art group.** Per-section combined FG+BG art group, streamed via existing A.4 `Section_StreamArtGroup`. No parallel system. Validated by Thunder Force IV (unified stage DMA batch) and Alien Soldier (per-section section headers).
- **BG-tile dedupe runs in same per-section pass as FG.** A.1/A.3's per-section dedupe pass folds BG-referenced tiles in. Captures FG↔BG aliasing within the section.
- **BG layout storage = raw 64×32 nametable (4096 B per layout), uncompressed.** Compression deferrable; ROM cost (≤68 KB worst case for our OJZ scale) is negligible vs. 4 MB ROM budget. Column-strip approach explicitly rejected — would force unneeded Plane B column-streaming engine.

### Build tool — extends the strip generator
- Read `act_bg_layout` (Act, longword) and `sec_bg_layout` (Sec, longword) — added as fresh fields, replacing the unused `sec_strips_b` placeholder.
- Tier detection from sentinels:
  - `sec_bg_layout = NULL` → **tier 1** (uses `act_bg_layout` zone-wide BG)
  - `sec_bg_layout ≠ NULL`, BG tile refs subset of section's existing FG tile-set → **tier 2** (per-section BG layout, shared FG tiles)
  - `sec_bg_layout ≠ NULL`, BG tile refs include tiles not in FG set → **tier 3** (per-section BG layout + BG tiles folded into section's A.3 art group)
- Emit `zone_bg.bin` (4 KB raw nametable) once per act for T1.
- Emit per-section `secN_bg.bin` (4 KB raw nametable each) for T2/T3 sections under `--bg-fixture=t2` / `t3` flag.
- For T3, fold BG tile refs into the section's A.3 dedupe pass (`sec_tile_refs[sec_id] |= bg_tile_refs`); section's S4LZ blob then carries both FG and BG tiles unified.
- Build-time printed report: per section, `tier T; BG layout bytes 4096; BG-only tiles added to art group (T3 only) N`.

### Engine — Plane B redraw on section transition
- Section enter (tier 2): redraw Plane B nametable from the new section's BG strips. One-shot blit, similar to FG strip drawing already in `Section_Init` / `Section_QueueNewSlot1Cols`.
- Section enter (tier 3): same plus the BG tile art was already streamed via A.4 (no additional engine work — A.4's group concept covers FG and BG uniformly).
- Tier 1: no per-section redraw needed.

### Validation strategy on OJZ
OJZ act 1 ships with tier 1 (zone-wide BG via `Level_OJZ1_BG`). To validate tiers 2 and 3, **synthesize hand-authored variants** of one or two OJZ sections — these live in test fixture data, not in the production OJZ act. The shipped OJZ keeps its zone-wide BG; the synthesized variants exercise the new code paths.

### Verification
1. Visual: synthesized tier-2 OJZ section shows different BG arrangement than tier-1 sections, no glitch.
2. Visual: synthesized tier-3 OJZ section shows different BG layout AND unique BG tiles, no glitch.
3. Build tool round-trip on BG tile dedupe (FG round-trip already covered in A.1).

### Out of scope for A.5
- No per-section BG palette swaps (orthogonal — palette system, §7).
- No animated BG tiles (palette-cycling is §7).
- No per-section parallax variation — moved to §4.6 deferred work.

---

## Cross-cutting concerns

### RAM budget impact
- A.1: +32 KB **transient** (level-init S4LZ work buffer, freed/reusable after `Section_Init` returns)
- A.2: zero net RAM change (region 2 is VRAM, not RAM)
- A.3: small per-section art-group state, < 1 KB total
- A.4: +8 KB **persistent** (double-buffered streaming work, 4 KB × 2)
- A.5: negligible (small additional per-section state for tier flag + BG strip pointer)

**Total persistent additions across all five phases:** ~8 KB. Comfortably affordable in the work-RAM budget vacated by eliminating chunk/block tables (architecture doc §2.5).

### SST and §3 compatibility
`Load_Object`'s temporary `art_tile` field continues to work; nothing in §2 phase 2 changes the SST shape. Milestone B (the next milestone) replaces the temporary field with allocator-driven assignment.

### `Level_LoadArt` evolves across phases
The same routine name carries different scope at each layer. A.1 introduces `Level_LoadArt` as "decompress the whole deduped pool, blocking, at level init." A.3 narrows it to "load the initial visibility clique only" once art-group metadata exists. A.4 adds `Section_StreamArtGroup` for runtime streaming, leaving `Level_LoadArt` responsible only for the initial load. The internal `LoadArt_S4LZ` primitive (decompress + DMA) keeps the same signature throughout.

### Test fixtures
The synthetic stress toggles introduced across A.2, A.3, A.4 (force-shrink pool, force-coloring-aliasing, force-streaming) are build-tool flags, not runtime concepts. They emit fixture variants of OJZ that exercise specific code paths regardless of OJZ's natural data sizes. The shipped OJZ build never enables them.

### Architecture-doc updates expected
This phase plans for several research outputs to feed back into ENGINE_ARCHITECTURE.md:
- §2.3 — concrete adjacency-graph definition (A.3 research)
- §2.3 — concrete graph-coloring algorithm choice (A.3 research)
- §2.4 — concrete BG-tile-pool sharing decision (A.5 research)
- §2.5 — concrete preload threshold value (A.4 research)

The doc updates land alongside each layer's commit, not in a separate doc-only commit.

---

## Defer to milestone B (next milestone)
- Dynamic VRAM allocator: `AllocVRAM`, `FreeVRAM`, `Section_ResetVRAM`
- Refcount-based art caching / lazy reclaim
- Replacement of the temporary `art_tile` field in the SST

## Defer indefinitely (need other systems first)
- S4LZ mid-decompress preemption — needs §9.7 cooperative multitasking
- Velocity-adaptive preload threshold — needs §3 player physics ground_speed
- Vertical section streaming — needs vertical level data
- Per-section parallax variation — moved to §4.6 deferred work

---

## Asset workflow recap

Source per-section level data (chunk/block extracts from sonic_hack) is the input to `tools/ojz_strip_gen.py`. Phase A.1 makes that tool also dedupe + flip-canonicalize tiles and emit a deduped pool blob. Subsequent phases extend the same tool with multi-region packing (A.2), graph coloring (A.3), and per-section BG handling (A.5). The tool's output drives both the build-time S4LZ compression step (`tools/s4lz.py`) and the engine's runtime loader (`Level_LoadArt` / `Section_StreamArtGroup`). No data ever lives outside this build-tool pipeline.
