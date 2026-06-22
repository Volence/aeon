# Act Art Streaming — design spec

**Date:** 2026-06-22
**Status:** Draft — pending user review
**Supersedes:** the parity-union / DSATUR-graph-color-union art model and the
`ENGINE_ARCHITECTURE.md` §2.3 "build-time tile graph coloring / 2 color regions /
zero-DMA-transition" prose (to be rewritten when this lands).

---

## 1. Goal & non-goals

**Goal.** Give the engine its intended best-of-class capability: **levels of
effectively unlimited size with unique per-section foreground *and* background
art**, streamed smoothly (no pop-in), with **section identity living in the data
layer, not in VRAM**. Unblock the currently-failing OJZ build as the first
concrete increment of this system.

**Non-goals.** This does not change the layout/collision/entity streaming (the
80×60 tile-cache window already streams those in 2D and works). It does not touch
parallax, sound, or player systems. It does not introduce a new windowing system —
it adds an art-residency layer to the window that already exists.

**Why now.** The build dies because the build tool emits, per section, the *union*
of its DSATUR color group's tiles (sec0/2/4/6/8 are byte-identical 603-tile blobs),
decompressed in one shot into a 9,600-byte buffer. That model duplicates art, caps
total art at VRAM, and never actually streamed (the runtime reload hooks are empty
stubs). It is replaced wholesale here.

---

## 2. The model — three decoupled layers

The core idea is to separate **how art is stored**, **how the level references it**,
and **what is resident in VRAM** — the virtual-texture model adapted to the 68000.

### 2.1 Storage — one globally-deduplicated *act art pool*
- Every act has **one art pool**: all of its unique tiles, **deduplicated globally
  and stored exactly once**. No per-section, no per-color-group duplication.
- The pool is **ordered by spatial locality** (tiles that appear near each other in
  the level get adjacent pool indices) so a screenful of tiles clusters into a few
  adjacent pages.
- The pool is stored as **independently-decodable pages** (a *page* = a contiguous
  run of N pool indices, compressed on its own). A single monolithic LZ stream can't
  be random-accessed; pages can. Page size (e.g. 64–256 tiles) is a tunable.

### 2.2 Reference — sections index the pool
- A *section* is a level region (its layout/collision/entity data). Its nametables
  reference tiles **by global pool index**. (The engine already remaps nametable
  indices internally — today to per-color-group slots; here to the single pool.)
- Section identity is entirely in this data. The art pool is shared substrate.

### 2.3 Residency — a windowed VRAM cache over the pool
- VRAM holds a **unified residency pool** (~1,472 art tiles; both planes index the
  same tile space, so there is no hard FG/BG split — *soft* budgets + pinned roots
  instead). Foreground migrates into this pool first (Phases 1–2); background joins
  it in Phase 3 — until then BG keeps its existing load-once region.
- A **page table** maps pool-tile-index → physical VRAM slot. A **refcount/LRU
  free-list** governs occupancy.
- Residency rides the **existing 80×60 tile-cache window fill** (which already
  streams nametable columns/rows in 2D). As a block enters the window, the residency
  layer ensures the pages holding that block's referenced tiles are resident
  (decode + DMA on miss), and patches the block's nametable cells to the chosen
  physical slots. Tiles leaving the window decrement refcount; zero-refcount slots
  are freed.
- **Pinned roots:** tiles common across the act (shared ground/foliage/sky) are
  loaded once and never evicted, so adjacent sections stream only their *delta*.
- Bounded by a **per-frame art budget cap** (analogous to `BLOCK_DECOMP_BUDGET`),
  prefetched ahead of the seam via the existing camera/section predictor.

### 2.4 Vocabulary (used identically in code, comments, docs)
- **Act art pool** — the one globally-deduped tile set for an act.
- **Page** — an independently-decodable compressed chunk of the pool; the art
  streaming unit.
- **Block** — the existing 16×16 layout/collision unit; references pool indices.
- **Section** — a level region; layout/collision/entities referencing the pool.
- **Residency cache** — the VRAM working set (page table + refcount/LRU).

---

## 3. Build pipeline (`tools/ojz_strip_gen.py` — daemon-watched; coordinate edits)

- **Remove** the DSATUR color-grouping and the per-color-group **union blob**
  emission entirely.
- Emit **one act art pool**: global dedup (keep the existing flip-canonical dedup —
  it now serves ROM size + window density, not VRAM-fit), spatially-ordered, written
  as independently-decodable pages + a small page/slot manifest.
- Remap all section nametables to **global pool indices**.
- Reconcile the capacity constant (`REGION1_TILE_CAPACITY` 1536 → 1472) and replace
  the `> 9600` single-blob guard with a per-page `≤ staging-buffer` guard; close the
  silent-overflow window (build fails if pool > pool-VRAM ceiling).

## 4. Engine runtime

- A purpose-named **art staging buffer** sized to the page/DMA budget (replacing the
  `Decomp_Buffer = Tile_Cache_Nametable` alias and the orphaned
  `DECOMP_BUFFER_SIZE`).
- **Page loader**: decode a page → DMA to its residency slot(s). Iterates pages, not
  one monolithic blob.
- **Residency cache**: page table (pool index → slot), refcount/LRU free-list,
  pinned roots, integrated into `Tile_Cache_Fill`; nametable patch to physical slots.
- **Prefetch** driven by the existing camera/section window predictor; per-frame art
  budget cap.

## 5. Phasing — real abstractions from the start

Each phase lands as clean, coherent code. The residency cache *abstraction* exists
in Phase 1; later phases complete its policy — they do not rewrite or wrap it.

- **Phase 1 — Act art pool + paged residency (unblocks the build).**
  Build emits the globally-deduped, spatially-ordered, paged act art pool; nametables
  reference global indices; the residency cache + page loader are the real ones, run
  with eviction disabled (working set fits VRAM, so all pages stay resident). Result:
  **build unblocks, level is scrollable, zero art duplication.** Verify by screenshot
  + scroll profile.
- **Phase 2 — Eviction policy (streams past VRAM).**
  Enable refcount/LRU eviction + pinned roots + budget-capped prefetch on the *same*
  residency cache. Validate on a deliberately oversized/art-varied level (the
  decode-under-load envelope we could not measure on the current 1×3 OJZ row).
- **Phase 3 — Background into the unified pool.**
  Bring per-section BG art into the same act art pool + residency cache.

## 6. Cleanliness / legacy removal (hard requirement)

This replaces a load-bearing system; the old one is excised, not left beside the new.
On completion, **none of the following remain**: the parity-union/graph-color-union
build path; the `Decomp_Buffer`/`Decomp_Buffer_End` aliases and
`DECOMP_BUFFER_SIZE=32768`; the empty preload/deferred-load stubs (replaced by the
real prefetch); the two temp scaffolds (`build.sh` guard widening,
`ojz_scroll_test.asm` scroll-rate edit). `ENGINE_ARCHITECTURE.md` §2.3 is rewritten to
describe this model as the design. Names reflect the new roles. No dormant
parallel codepaths or `if old else new` branches.

## 7. Coupling & staging

`Slot_Section_Map` and the world↔engine coordinate helpers are read across the section,
camera, load_art, tile_cache, entity_window, and player_sensors modules. The residency
cache is introduced **behind those interfaces** and the section model refactored to fit
it — cleanly, so the result reads as one coherent system (not a wrapper around the old
leapfrog).

## 8. Risks & open parameters

- **ZX0 can't be chunked mid-stream** → pages are independently-decodable (resolved).
- **Page size & spatial ordering** — tunables; pick a default, measure over-fetch and
  decode cost on an art-varied level in Phase 2.
- **Art budget cap** — set from the measured leading-edge block rate (~0.5–1 block/frame
  at max scroll) × per-block decode (~6–9K cyc measured); validate under real scroll.
- **Pinned-root selection** — which tiles count as act-common; build-time heuristic +
  measurement.

## 9. Verification

- Phase 1: `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh` completes; ROM boots; OJZ art
  renders correctly (oracle screenshot); sustained-scroll profile shows no regression
  (parallax-dominant, streaming small, ~60% idle); zero tile duplication (pool size ==
  distinct count).
- Phase 2: on an oversized/varied test level, eviction keeps the working set ≤ pool,
  no pop-in at max scroll, `Lag_Frame_Count` stable; budget cap honored.
- Throughout: feasibility numbers from `streaming_feasibility_2026_06_22` hold.

## 10. Provenance note

The model being replaced (2-slot leapfrog + graph-color union) was assistant-authored
in the engine's first commit, never an explicit user decision (see
`leapfrog_provenance_audit`). This spec is the deliberate, user-reviewed replacement of
the art-storage/residency portion. The leapfrog *coordinate/section* model is retained
(ratified) and the residency cache is built behind its interface.
