# Art Streaming Phase 2 — Residency Cache & Resumable Decode — design spec

**Date:** 2026-07-02
**Status:** Approved by user (design dialogue 2026-07-02); pending spec review
**Extends:** `2026-06-22-act-art-streaming-design.md` (Phase 1 shipped; this designs its Phase 2)
**Supersedes:** ARCH §9.7 (user-mode cooperative multitasking — REJECTED, see §3);
audit amendment #1 "small S4LZ pages mandatory" (superseded by measurement, see §4)

---

## 1. Goal

Level size unbounded, fresh art anywhere, no cap. VRAM is a windowed cache over an
act art pool whose size is limited only by ROM. No component may assume "the act's
art fits in VRAM." This is the virtual-texture model (id Tech 5 page cache: free /
LRU / locked lists) adapted to the 68000 — and its CPU-slicing mechanism is the one
three shipped Genesis codebases independently converged on (S3K, Ristar, S.C.E.).

**Non-goals:** BG art unification (Phase 3 of the parent spec, unchanged); object/DPLC
art streaming (§2.2 dynamic VRAM allocator, separate); layout/collision/entity
streaming (already works, untouched).

**Constraint from the user (2026-07-02): art ROM footprint stays controlled.**
Uncapped capability ≠ unbounded footprint — see the ROM budget gate in §7.

---

## 2. Decisions made in this design (all user-ratified 2026-07-02)

1. **Resumable decode = supervisor-mode preemptive bookmark** (S3K/Ristar/S.C.E.
   pattern). User-mode §9.7 rejected.
2. **Page format = ZX0 + raw-direct hybrid**, per-page election by ratio at build
   time. The S4LZ page tier is dead (amendment #1 superseded — evidence in §4).
3. **Nametable words carry logical indices until cache entry**, patched to physical
   VRAM slots as blocks enter the 80×60 tile cache.
4. **Unbounded pool indices** via per-section local→global translation tables
   (the 11-bit nametable field ceases to be a pool-size ceiling).
5. **Page-granular residency**: refcount-pinned + LRU-over-unpinned page frames.
6. **Budgets**: B&R per-act art-budget descriptor word + Vectorman dual-cap
   (entries AND bytes) on the DMA queue.
7. **Degradation**: camera soft-clamp on demand-miss (audit amendment #3, stands).

---

## 3. Mechanism: supervisor-mode preemptive bookmark (§9.7 replacement)

**How it works.** The page decoder runs as a straight-line loop in main-loop idle
time (the `VSync_Wait` spin, `engine/system/vblank.asm:167-184`). If VBlank fires
mid-decode, `VBlank_Handler` checks whether the interrupted PC (read symbolically
from the known stack frame layout — NOT an S3K-style magic `$42(sp)` offset; we own
the handler) lies inside `[ZX0_Resume_Start, ZX0_Resume_End)`. If so: save the
decoder's registers + SR + interrupted PC to RAM, rewrite the `rte` return address
to a small "bank registers and return to main loop" stub. Next frame the page-in
dispatcher sees the in-progress flag and `rte`s straight back into the loop
(registers + SR + PC restored). Cost ≈250–300 cycles per preempted frame (~0.2%).

**The decoder contract (assert-guarded, greppable):**
- **Stack-flat**: no `bsr`/`push` anywhere in the resumable PC range. The shipped
  `ZX0_Decompress` uses `bsr.s` for elias reads and a stack prologue — the resumable
  variant inlines the elias reader (also a speedup: kills ~34 cyc of bsr/rts per
  length read) and takes caller-managed registers (no stack save/restore).
- **All state in registers at every instruction** (a0 src, a1 dest, d0/d1/d2/a2 +
  CCR; SR save covers the live carry/X flags — `move sr,<ea>` is unprivileged on
  the 68000).
- **No VDP, no Z80, no shared-RAM writes** from inside the resumable range — decode
  targets the staging buffer only.
- PC range exported as symbols; the handler check compiles from them.

**Why not user mode (ARCH §9.7 as previously written):** zero shipped adopters in
~15 years (plutiedev pattern is educational/prospective); TAS is broken as a lock
primitive on MD1/MD2 (bus arbiter ignores TAS's write phase — hardware-revision-
dependent); critical sections require `trap` syscalls; a permanent debugging tax
(two register contexts, preemption at any instruction) in an engine whose worst
historical bugs were preemption-window bugs (VInt_Lag Plane_Buffer race, banked-Z80
code corruption). The bookmark delivers user-mode's two real advantages — straight-
line decoder, all idle time consumed — with none of this. **ARCH §9.7 is rewritten
to the bookmark design; the user-mode variant is documented there as rejected with
this rationale.** Precedent: S3K `Set_Kos_Bookmark`/`Backup_Kos_Registers`/
`Restore_Kos_Bookmark` (sonic3k.asm:2818-2966); Ristar's `$FFE5BC` yield path
(disasm.asm:5443-5474, 9098-9109); S.C.E. `Set_KosPlus_Bookmark`.

---

## 4. Page format: ZX0 + raw-direct (amendment #1 superseded)

**Measurement (2026-07-02, real OJZ act pool, 612 tiles / 19,584 B):**

| Form | Size | Ratio |
|---|---|---|
| ZX0 (shipped 256-tile pages, incl. wrappers) | 11,312 B | **57.8%** |
| S4LZ 64-tile pages | 16,854 B | 86.1% |
| S4LZ 64-tile pages + tile-delta | 19,062 B | 97.3% |
| Raw | 19,584 B | 100% |

The globally-deduped pool is deliberately redundancy-free; S4LZ (word-aligned, no
entropy coding) barely compresses it and tile-delta actively hurts. The audit's
"S4LZ pages mandatory" amendment was premised on decode fitting a per-frame budget
slice; the bookmark (§3) dissolves that premise — decode speed is a *latency*
concern (frames until a prefetched page lands), not a correctness one. A 64-tile
ZX0 page ≈ 2 KB ≈ ~45K cycles ≈ under one frame of measured idle (~62% at max
scroll; ~2.4 frames at worst-case diagonal ~24% idle). The cache-window lookahead
(§5) absorbs that.

**Design:** one page abstraction, two storage forms, elected per page by the build
tool: **ZX0** (density) or **raw-direct** (zero CPU — DMA straight from ROM,
skipping staging; precedent: the block tier's RAW-DIRECT form, Sonic 3D/SGDK
uncompressed streaming). Election rule: raw only when ZX0 gains < RAW_ELECT_MIN
(tunable, default ~10%). Manifest v2 per page: ROM address, form bit, tile count,
pinned flag. Page size default **64 tiles / 2 KB** (build-time tunable; sweep on
the Phase-2 stress level). S4LZ keeps its block-stream role unchanged.

**Init unification:** level init = the same streaming path with display off
(prefetch the starting window). The separate 256-tile ZX0 init loader path and
`ART_POOL_PAGE_TILES=256` constants are deleted, not kept beside (clean-not-
bolted-on).

---

## 5. Data model & residency

**Pool.** Globally-deduped, spatially-ordered, unbounded. Split into pages (§4).

**Unbounded indices.** Blocks keep compact local tile indices (fit the 11-bit
nametable field); each section dictionary carries a **local→global translation
table**. Pool size has no format ceiling.

**Residency cache.** The FG VRAM region becomes N **page frames** (~11–13 × 64
tiles inside the ~700–850-tile effective budget). Structures (lower-RAM slack is
9,150 B as of `s4.lst` @ c2e5ae8 — the old "910 B" figure is stale):
- page table: global page id → frame (or NOT_RESIDENT),
- per-frame: refcount, LRU link, pinned bit.
**Pinned roots** (build-marked act-common pages) never evict.

**The safety invariant.** A page's refcount counts tiles referenced by blocks
currently inside the 80×60 tile cache. Blocks are patched logical→physical at
cache entry (`TileCache_CopyBlockColumn` / `TileCache_FillRow` — the words the
generator bakes today become logical); everything downstream (Plane_Buffer, VDP)
sees ordinary physical words. Eviction only of zero-refcount unpinned frames ⇒ a
physical index in the cache can never dangle.

**Demand & latency.** A block entering the window whose page is not resident
stalls that cell via the existing partial-fill/keyed-resume machinery until the
page lands. The cache window's ~10-column lookahead beyond the screen is the
latency budget hiding 1–3-frame page-in at 16 px/frame max scroll.

**Floating-origin compatibility (design #2):** page identity is position-
independent; residency keys off cache content, not coordinates. Rebases don't
touch this system.

---

## 6. Page-in pipeline, budgets, degradation

**Request queue.** Small FIFO, two priorities: **demand** (a fill is stalled)
ahead of **prefetch** (leading-edge lookahead, direction-sensed the same way the
existing `Cache_Prev_Cam_Row` prefetch works). Completed ZX0 pages decode to a
2 KB staging buffer, then enqueue DMA at Important priority; raw-direct pages
enqueue DMA from ROM directly.

**Budget adoptions:**
- **DMA queue dual cap** (Vectorman `$E806`/`$AABE` pattern: max entries AND max
  bytes per frame, atomic rollback + retry-next-frame on overflow) added to the
  Important/Deferrable drain — extends, not replaces, the existing
  `DMA_Budget_Remaining` byte budget.
- **Per-act art budget word** (B&R `$FF9914`→`$FF9916` pattern): the per-frame
  art-streaming byte allowance lives in the Act descriptor and is reloaded each
  frame — per-act tuning, no global constant.

**Degradation (amendment #3).** If a demand page-in would let unfetched art reach
the visible edge, the camera soft-clamps until it lands (the S3K gate). DEBUG
counts clamp events; the acceptance gate is sustained-max-diagonal stress showing
zero visible pop-in and bounded clamp frequency.

---

## 7. Build pipeline & the ROM budget gate

`tools/ojz_strip_gen.py` is **daemon-watched — coordinate with the user; never
edit autonomously.** Changes: emit local→global tables; split the pool into pages
(spatial order preserved); per-page ZX0-vs-raw election; pinned-root marking
(act-common frequency heuristic, validated by measurement); manifest v2. Pool-size
asserts become residency asserts (working-set/frames), not pool ceilings.

**ROM budget gate (user requirement 2026-07-02):** the build prints a per-act art
ROM report (raw vs stored, per form, page count) and enforces a per-act art ROM
budget: **warn** above a soft threshold, **fail** above a hard one (both
configurable per act; defaults set when the first real second act exists). The
ZX0-first election is the density lever; the report is the visibility lever. No
silent growth.

---

## 8. Phasing (implementation plan will detail; each phase oracle-verified)

- **P2a — Resumable decoder + bookmark.** Stack-flat inlined resumable ZX0
  variant + `VBlank_Handler` bookmark + dispatcher. Proven standalone by running
  the *existing* pool load through it (self-test: decode with forced mid-stream
  preemptions == blocking decode, byte-identical).
- **P2b — Residency cache.** Page frames, page table, refcount/LRU/pin, logical
  words + patch-at-entry, demand stall. Eviction exercised deliberately.
- **P2c — Budgets, degradation, stress.** Dual-cap DMA, per-act budget word,
  camera gate, synthetic oversized stress level (generated fixture, >2,048 distinct
  tiles to prove the unbounded index path), sustained-max-diagonal acceptance.

Everything in this spec is **engine** (design-#5 tagging); only the Act-descriptor
budget word and the generated data are game-side.

---

## 9. Verification

- P2a self-test at DEBUG boot (like the compression golden test): resumable ==
  blocking output under forced preemption.
- P2b: oracle screenshots + VRAM reads across eviction cycles; refcount audit
  assert (DEBUG walk: every cache-referenced page resident).
- P2c: stress level at sustained max scroll all axes — zero visible pop-in,
  `Lag_Frame_Count` regression-free vs master, clamp events bounded and logged;
  ROM report matches budget.
- Feasibility numbers to hold: S4LZ block tier unchanged (~6-9K cyc/block);
  ZX0 page ≈ 45K cyc idle-time; bookmark ≤ ~300 cyc/preempted frame.

## 10. Risks & open parameters

- **Page size 64** — sweep 32/64/128 on the stress level (frame count vs
  granularity vs manifest size).
- **Pinned-root heuristic** — frequency threshold; measure eviction churn.
- **Demand-stall interaction with fill budget** — a stalled cell must not
  deadlock the fill's keyed resume; P2b test includes a forced-miss soak.
- **Prefetch depth** — enough to hide worst-case diagonal latency (~2.4 frames);
  validated under P2c stress.
- **Staging buffer RAM** — 2 KB steady-state (vs today's 8 KB init-only alias);
  placed in the 9,150 B lower slack; `Art_Staging_Buffer` alias deleted.

## 11. Research provenance

Four-agent pass, 2026-07-02: S3K KosM mechanism (skdisasm cites in §3); aeon
integration facts (facts sheet — hooks, budgets, RAM, decoder analysis); web
(plutiedev multitasking, SpritesMind t=597/t=703/t=3245, Tanglewood, SGDK, van
Waveren SVT 2012, MD TAS quirk); reference engines (B&R dual budget
`main_loop.asm:22-25,194-206,3604`; Vectorman dual cap `disasm.asm:6288-6341`;
Ristar resumable decode; Gunstar/AS/TF4 negative results; S.C.E. KosPlusM).
Page-format measurement: §4 table (scratchpad `pagesweep.py`, reproducible).
