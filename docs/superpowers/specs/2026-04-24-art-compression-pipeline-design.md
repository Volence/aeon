# §2 Art & Compression Pipeline — Compression Formats & Basic Art Loading

**Date:** 2026-04-24
**Scope:** S4LZ compression, random-access tile format, basic art loading API, DMA queue audit
**Baseline:** ENGINE_ARCHITECTURE.md §2.1-2.3
**Defers:** Dynamic VRAM allocator, refcount caching, graph coloring, section streaming, S4LZ streaming mode

---

## Overview

The VDP pipeline (§1) can drain DMA and push data to VRAM, but has nothing to feed it except raw uncompressed art. This phase delivers the compression formats and basic loading API that give the pipeline real data to work with.

Four phases, each self-contained with research → design → build → test:

| Phase | Deliverable | Test |
|-------|------------|------|
| 0 | DMA Queue Audit | Re-verify §1 DMA test if changes made |
| 1 | S4LZ compressor + 68000 decompressor | Title screen round-trip |
| 2 | Random-access tile format compressor + 68000 decompressor | Sprite frame loading |
| 3 | Basic art loading API | Robust multi-asset test |

---

## Phase 0: DMA Queue Audit

**Goal:** Verify our §1 Flamewing Ultra DMA queue implementation is best-in-class, or identify concrete improvements.

### Research Scope

**All 7 reference disassemblies:**
- **S.C.E.** — DMA queue design, how it compares to Flamewing's
- **Batman & Robin** — VDP shadow table approach (no queue) — tradeoffs vs queued DMA
- **Vectorman** — DMA handling for their 64×64 plane setup
- **Gunstar Heroes** — Treasure's approach to DMA scheduling with heavy sprite counts
- **Alien Soldier** — extreme optimization, any DMA-specific techniques
- **Thunder Force IV** — multi-layer scroll DMA bandwidth management
- **sonic_hack** — original S2-based implementation for comparison baseline

**Online & community sources:**
- Flamewing's repo — any updates/improvements since our implementation
- SGDK (Stephane-D) — alternative DMA queue design
- SpritesMind forum — community DMA discussions, forks, improvements
- plutiedev — DMA timing documentation
- GitHub homebrew (Xeno Crisis, Tanglewood, Demons of Asteborg, Project MD) — novel approaches

### Audit Targets

- Drain routines (jump-table Critical, budgeted Important/Deferrable)
- 128KB boundary safety (currently deferred — should §2's larger transfers force this now?)
- Queue slot count (32) — sized correctly for projected workloads?
- 3-priority sub-queue partitioning — better than single sorted queue?
- Static DMA pre-registration system

### Deliverable

Research findings document. Either "confirmed best-in-class" with evidence, or surgical code changes with re-verification against the existing §1 DMA test.

---

## Phase 1: S4LZ Compression Pipeline

**Goal:** Design, build, and verify an S4LZ compressor + 68000 decompressor meeting or exceeding the architecture doc's targets.

**Targets:** ≥700 KB/s decompression, ≤0.50 compression ratio on tile art.

### Research — Validate Architecture Doc §2.1 Baseline

The architecture doc specifies these design decisions. Research validates each:

| Decision | What to validate | Against what |
|----------|-----------------|--------------|
| Nibble-split token (hi=literal count, lo=match count) | Optimal vs separate literal/match tokens? | LZ4 token format, LZSA2, other 68000-targeted LZ |
| Word-aligned copies | Confirmed 68000 advantage (12 cycles/word = double throughput) — verify no edge cases | Byte-aligned formats for ratio comparison |
| 256-entry jump table dispatch | ROM cost (~2-5KB) worth the speed vs loop-based? | SGDK LZ4W loop, Comper's approach |
| 16-bit big-endian offsets (64KB window) | Window size vs ratio tradeoff | Smaller windows (LZ4 512B, LZSA 8KB) |
| Tile-delta XOR preprocessing | Verify 10-25% ratio improvement claim on real art | Compress with/without, measure on real Sonic tile art |
| Extension bytes for counts >15 | Mechanism design — single byte? Multi-byte chain? | LZ4's extension scheme |

**All 7 reference disassemblies:**
- How each game loads bulk art — format, speed, any tile-aware tricks
- Special attention to any game doing tile-aware preprocessing

**Online sources:**
- clownlzss — optimal parser library, usable or educational
- LZSA / LZSA2 (Emmanuel Marty) — designed for 8/16-bit CPUs
- LZ4W (SGDK) — closest existing comparison point
- Comper — simple and fast, where does S4LZ actually beat it?
- MEGAPACK (Codemasters) — tile-delta preprocessing prior art
- 68000 LZ benchmarks on SpritesMind, GitHub, retrodev communities

### S4LZ Build Tool

Single tool with three modes:
- **Compress:** raw tiles → S4LZ stream (with optional tile-delta preprocessing)
- **Decompress:** S4LZ stream → raw tiles (with optional tile-delta undo)
- **Verify:** compress → decompress → compare to original (automated round-trip)

Implementation:
- Optimal parsing (graph-based) — greedy parsing leaves ~5-15% ratio on the table
- Tile-delta XOR preprocessing pass before compression
- Language: decided during research (Python likely sufficient — compressor runs once at build time, not performance-critical; C only if optimal parsing on large art sets is too slow in Python)
- Input: raw binary tile data. Output: S4LZ compressed stream
- PC-side decompressor serves as reference implementation for validating the 68000 version

### S4LZ 68000 Decompressor

- Blocking mode only (streaming mode deferred to §9.7 cooperative multitasking)
- 256-entry jump table for token dispatch
- Word-aligned copies throughout
- Input: source ROM pointer, destination RAM buffer pointer
- Output: decompressed data in RAM buffer, ready for DMA to VRAM

### Tile-Delta XOR (68000 Runtime Undo)

- Post-decompression pass: XOR each 32-byte tile against previous to reconstruct originals
- Architecture doc estimates ~8.5 cycles/byte — verify acceptable overhead vs ratio gain

### Test — Title Screen Round-Trip

1. Take existing title screen art (from sonic_hack, currently uncompressed in §1 test)
2. Compress with S4LZ compressor (with tile-delta)
3. BINCLUDE compressed data in ROM
4. Runtime: S4LZ decompress → tile-delta undo → DMA to VRAM via §1 pipeline
5. Visual comparison: must look identical to §1's uncompressed test

### Success Criteria

- Decompression speed ≥700 KB/s on real tile data
- Compression ratio ≤0.50 on tile art with tile-delta
- Title screen displays identically to §1's uncompressed version
- Build tool verify mode confirms lossless round-trip

---

## Phase 2: Random-Access Tile Format

**Goal:** Deliver a format that decompresses individual tiles on demand without touching preceding tiles. UFTC is the baseline candidate; research determines whether it's the best option or if modifications/alternatives beat it.

**Why random access:** A character sprite frame uses 5-8 tiles. LZ would decompress an entire sprite sheet (~100+ tiles) to get those 5-8. Random access: give me tile #37 → get exactly tile #37's 32 bytes.

### Research — Validate UFTC Baseline

| Decision | What to validate |
|----------|-----------------|
| 4×4 block dictionary approach | Best ratio for sprite art specifically? |
| UFTC16 variant (16-bit offsets, 8192 max blocks) | Enough for projected sprite sheet sizes? |
| ~50% compression ratio | Verify on real Sonic sprite art |
| ~12.5 KB/frame decompression speed | Verify on 68000 |

**All 7 reference disassemblies:**
- How each game handles per-frame sprite art loading (DPLCs, pre-decompressed frames, other)
- S.C.E. specifically — likely has UFTC integration
- Any game using a non-UFTC random-access tile scheme

**Online sources:**
- Flamewing/Sik's UFTC repo — current state, known limitations, improvements
- SpritesMind discussions on UFTC — community experience
- Alternative random-access formats in homebrew (SGDK, Project MD, etc.)
- Simpler schemes: per-tile RLE, per-tile small-window LZ, dictionary of full tiles
- Amiga demoscene — random-access sprite decompression tricks

**Potential modifications to evaluate:**
- Different block sizes (2×4, 4×8, 2×2) — does 4×4 hit the sweet spot?
- Dictionary pruning — build-time analysis to reduce dictionary size
- Tile-delta between animation frames — adjacent frames differ by 1-2 tiles
- Hybrid: UFTC random access with secondary compression on the dictionary

### Build Tool

Same pattern as S4LZ — single tool with three modes:
- **Compress:** raw sprite sheet → random-access format
- **Decompress:** extract individual tiles or full sheet
- **Verify:** round-trip check

### 68000 Decompressor

- Single tile mode: given tile index, decompress one tile to RAM buffer
- Batch mode: decompress a list of tile indices (for a full sprite frame's DPLC entry)
- Output → RAM buffer → DMA to VRAM via §1 pipeline

### Test — Sprite Frame Loading

- Take a real Sonic sprite sheet from sonic_hack (walk cycle or similar)
- Compress with build tool
- Runtime: decompress specific frames by tile index → DMA to VRAM → display as sprites
- Verify visual correctness against original art

### Success Criteria

- Decompress 8 tiles (one sprite frame) within reasonable CPU budget (exact target set by research)
- Compression ratio ≤0.55 on real Sonic sprite art
- Individual tile access with zero wasted decompression work
- Build tool round-trip verified lossless

---

## Phase 3: Basic Art Loading API + Robust Test

**Goal:** Thin API layer connecting §2 decompressors to §1 DMA pipeline, then prove the full stack works with multiple art sets.

### API

**`LoadArt_S4LZ(source, vram_dest, compressed_size)`**
- Decompresses S4LZ data from ROM to RAM work buffer
- Runs tile-delta XOR undo pass
- Queues DMA transfer from RAM buffer to VRAM via `QueueDMATransfer`
- Blocking — returns when decompression complete, DMA queued (transfer at next VBlank)

**`LoadArt_Tiles(source, tile_index, tile_count, vram_dest)`**
- Decompresses `tile_count` tiles starting at `tile_index` from random-access sprite sheet
- Writes to RAM work buffer
- Queues DMA transfer to VRAM
- Used for sprite frame loading

### RAM Work Buffer

- Large enough for biggest single blocking art load
- Architecture doc mentions ~4KB for streaming — same buffer for blocking loads
- Exact size determined during implementation based on test art sizes

### What This Is NOT

- No art metadata tables (VRAM allocator, deferred to §3)
- No format auto-detection (caller specifies format)
- No streaming/interruptible decompression (deferred to §9.7)
- No error handling beyond debug assertions for buffer overflow

### Robust Test Suite

Art sourced from sonic_hack and/or S.C.E.:

| Test | Art Source | Format | Purpose |
|------|-----------|--------|---------|
| Title screen | Title screen tiles (~10KB) | S4LZ | Already proven uncompressed — now compressed |
| Level tiles | A zone's tile art (~20-30KB) | S4LZ | Larger data, stress decompressor + DMA |
| Sprite sheet | Sonic's sprites | Random-access | Load individual animation frames by tile index |
| Small art | Simple object (ring, monitor) | S4LZ | Verify small payloads |
| Combined | Level tiles + sprite frames same frame | Both | Prove both formats coexist through DMA pipeline |

Each test: compress at build time → BINCLUDE → decompress at runtime → DMA to VRAM → visual verification via Exodus MCP or on-screen display.

### Success Criteria

- All art loads display correctly through full pipeline (compress → decompress → DMA → VDP)
- No RAM buffer overflows
- DMA queue handles mixed S4LZ bulk loads and tile-format sprite loads in same frame
- Total decompression + DMA time for typical frame (level tiles + one sprite frame) fits within CPU budget

---

## Deferred Work (to add to DEFERRED_WORK.md)

**From §2 — Art & Compression Pipeline:**

- **Dynamic VRAM Allocator (§2.2)** — Blocked by: §3 Object System (`Load_Object` spawn/destroy lifecycle drives `AllocVRAM`/`FreeVRAM` calls). When ready: after §3 defines object RAM layout and the object loop exists.

- **Refcount-based Art Caching / Lazy Reclaim (§2.2)** — Blocked by: §3 Object System (refcount increments/decrements tied to object spawn/destroy). When ready: after §3 and the dynamic VRAM allocator exist.

- **Build-time Graph Coloring (§2.3)** — Blocked by: §4 Level/World (section adjacency graph defines which sections are "non-adjacent" and can share VRAM indices) + §8 Build Tools (tile deduplication pipeline). When ready: after §4 defines section grid and §8 has flatten/deduplicate pipeline.

- **Section-aware Streaming / Predictive Preloading (§2.1/§4.8)** — Blocked by: §4 Level/World (section transition triggers, camera position, leapfrog loading). When ready: after §4 implements section transitions and camera system.

- **S4LZ Streaming Mode (§2.1)** — Blocked by: §9.7 Cooperative Multitasking (interruptible decompression with VBlank bookmark/context switch). When ready: after §9.7 supervisor/user mode exists. Blocking mode (delivered in this phase) handles all current use cases.

---

## Asset Workflow

**Raw art in repo, compress at build time.** The source of truth is uncompressed tile data (`.bin` files). The build script runs the S4LZ/tile compressor to produce compressed versions that get BINCLUDE'd into the ROM.

- Raw art lives in `art/` subdirectories as uncompressed binary tile data
- Build step: raw `.bin` → compressor tool → compressed output → BINCLUDE in assembly
- If the compressor improves, just rebuild — everything benefits automatically
- The compressor is the single source of truth for the format

## Art Sources for Testing

All test art sourced from existing projects — no new art creation needed:
- **sonic_hack/** — title screen, zone tiles, Sonic sprites, object art (decompress from Nemesis/Kosinski using existing tools in `tools/`)
- **S.C.E./** — clean sprite sheets, may have UFTC-formatted art already
- Decompression tools available: `kosdec` (Kosinski), `nemdec` (Nemesis) in `sonic_hack/tools/`
