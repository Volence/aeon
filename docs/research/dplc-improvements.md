# DPLC System Research & Improvements

Research for §2 Art & Compression Pipeline — designing an improved DPLC system to replace UFTC for per-frame sprite art loading.

## Decision: Uncompressed Art + Improved DPLC

UFTC compression achieves only 0.82–0.86 ratio on real Sonic sprite art (see `tile-format-survey.md`). Every reference game stores sprite art uncompressed and uses DMA from ROM. We follow suit, with several improvements over the standard S2/S3K DPLC system.

## Reference Implementation Survey

### Sonic 2 (sonic_hack) — LoadSonicDynPLC
- Frame change detection via global `Player_Prev_DynPLC_Frame` byte
- DPLC entry format: word with 4-bit tile count (1-16 tiles) + 12-bit tile start index (0-4095)
- Fixed VRAM regions per character (Sonic=$F000, Tails=$E400)
- Multiple DMA entries per frame (average 3.1, max 16 for Sonic)
- No VRAM sharing between objects

### S.C.E. (S3K base) — Perform_DPLC
- Generic routine (works for any object, not per-character)
- Per-object `ros_prev_frame` field for frame change detection
- **Slot system**: `Slotted_object_bits` tracks VRAM region allocation
- Multiple instances of same enemy type share VRAM slot
- Nearly identical algorithm to S2 otherwise

### All Other References (Batman & Robin, Vectorman, Gunstar, Alien Soldier, Thunder Force IV)
- None use DPLC — sprite art loaded via direct DMA from uncompressed ROM
- Vectorman: 54-slot DMA queue with 5,760 byte/frame budget cap
- Gunstar: fixed DMA slots for subsystems + general queue

### Universal Pattern
- **No reference game decompresses art per animation frame** — all DMA from ROM
- **Frame-level dedup is universal** — skip DMA when frame unchanged
- **No tile-level dedup exists** in any reference — impractical overhead

## DMA Bandwidth Analysis

| Metric | Value |
|--------|-------|
| Average tiles per frame change | 17.1 |
| Average DMA per frame change | 547 bytes |
| VBlank DMA budget (NTSC) | ~7,000 bytes |
| Single frame change = % of budget | 7.8% |
| Worst case (3 chars + 8 objects) | 4,202 bytes (60%) |
| Amortized (frame changes every ~7 frames) | 1.1% of budget |

DPLC is not a DMA bandwidth bottleneck.

## S4 Engine DPLC Improvements

### Tier 1: Implement (high value, low complexity)

**1. DPLC Lookahead (NOVEL — §1.6)**
No Genesis game does predictive DPLC loading. When `anim_timer <= 1` (one frame before animation changes), peek at the next frame's DPLC requirements. If different from current, queue as Important-priority DMA. Art arrives before the frame changes — zero-latency animation transitions.

**2. Priority Queue Integration**
Character DPLCs → Important priority (guaranteed delivery in VBlank). Object DPLCs → Deferrable priority (budget-gated, can slip to next frame). This prevents VBlank overflow when many objects change frame simultaneously.

**3. Generic Perform_DPLC (S.C.E. approach)**
Single routine works for all objects. Per-object `ros_prev_frame` field. No hardcoded addresses. Object spawn sets up art source pointer + DPLC table pointer.

**4. VRAM Allocator Integration**
Object spawn → `AllocVRAM(type_id)` → returns VRAM address + bumps refcount. Multiple instances of same enemy type share VRAM (one set of tiles, many sprites). DPLC writes to allocated region. Already designed in §2.2.

### Tier 2: Build tools (moderate value)

**5. Build-time DPLC Entry Merging**
Scan DPLC tables at build time. Merge adjacent entries (tiles N..N+M → single entry). Reduces average DMA entries from 3.1 to 1.2 per frame change for Sonic. Fewer DMA queue slots consumed.

**6. Build-time Tile Deduplication**
Store only unique tile contents, remap DPLC indices. Saves ~11% ROM on character art. Requires a build tool to analyze pixel content and remap tables.

**7. Build-time Contiguous Art Layout**
Rearrange tiles so each animation frame's tiles are contiguous in ROM. Guarantees 1 DMA entry per frame change. 12% ROM overhead from tile duplication. Conflicts with tile dedup (#6) — choose one or the other.

### Tier 3: Not recommended

**8. Frame-Delta DPLC** — Only load tiles that pixel-differ from current frame. 8% DMA savings on an already-tiny load. Complex tracking logic. Not worth it.

**9. Tile-Level Caching** — Track individual tiles in VRAM, skip redundant loads. No reference game does this. Per-tile tracking overhead exceeds DMA savings.

## DPLC Data Format

Keep the S2/S3K format — it's compact and efficient:

```
Per animation frame:
  word: entry_count
  word × entry_count:
    bits 15-12: tile_count - 1 (1-16 tiles per entry)
    bits 11-0:  tile_start_index (×32 = byte offset in art)
```

Per-object fields needed in SST:
- `art_source` (long): ROM pointer to uncompressed art
- `dplc_script` (long): ROM pointer to DPLC table  
- `ros_prev_frame` (byte): last DPLC'd frame (for change detection)

## 128KB DMA Boundary Safety

**Gap identified**: DMA transfers crossing a 128KB ROM boundary ($20000, $40000, etc.) cause the source address to wrap, loading garbage tiles. The current `QueueDMATransfer` does not split these.

**Must add before production**: Check if `source + length` crosses a 128KB boundary. If so, split into two DMA entries. S.C.E. has a proven implementation (~20 lines, ~16 cycles common case, ~154 for split transfers).

## Architecture Impact

Changes to ENGINE_ARCHITECTURE.md:
- §2.1: Remove UFTC. Sprite art = uncompressed + DPLC/DMA.
- §3.9: Update per-frame art loading to reference DPLC (not UFTC).
- §2.2 (VRAM Allocator): Remove UFTC dictionary registration path. AllocVRAM returns VRAM address, DPLC handles per-frame loading.
- §1.1: Add 128KB boundary splitting to QueueDMATransfer.
