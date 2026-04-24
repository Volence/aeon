# Random-Access Tile Format Survey

Research for §2 Art & Compression Pipeline — validating UFTC as baseline candidate for per-frame sprite art.

## Key Finding: UFTC Disappoints on Our Data

**UFTC achieves 0.82–0.86 ratio on Sonic/Tails sprite art, not the projected ~0.50.** The 4×4 block dictionary approach has limited reuse because detailed Sonic sprite art produces mostly unique pixel patterns per block. Only blank (transparent) blocks see meaningful reuse (21% of total).

SpritesMind benchmarks show 0.75 on a single sprite BMP and Sik claims ~0.50 on character sheets with "many poses" — but on OUR real Sonic 2 sprite data, the ratio is 0.82–0.86.

**Recommendation: Drop UFTC. Use uncompressed sprite art + DPLC/DMA** — the same approach every commercial Genesis game uses. Total sprite art ROM cost (~463 KB) fits comfortably in a 4 MB ROM (11.3%). UFTC saves only ~55 KB (1.3% of ROM) at the cost of added complexity and per-frame CPU work.

---

## UFTC Compression Ratio Measurements

Tested on real sprite art from sonic_hack using UFTC16 format (4×4 block dictionary, 16-bit indices).

Multiple block-splitting methods tested; results consistent:

| Asset | Raw (bytes) | UFTC16 | Ratio | Unique Blocks | Reuse Factor |
|-------|------------|--------|-------|---------------|-------------|
| Sonic sprites | 109,600 | 94,340 | 0.861 | 8,367 | 1.64× |
| Tails sprites | 95,904 | 78,244 | 0.816 | 6,783 | 1.64× |
| Fire Shield | 8,608 | 6,316 | 0.734 | 520 | 1.66× |
| Lightning Shield | 4,320 | 3,708 | 0.858 | 328 | 1.32× |
| Insta-Shield | 1,664 | 1,660 | 0.998 | 155 | 1.07× |
| Invincibility Stars | 1,088 | 660 | 0.607 | 48 | 2.27× |
| DEZ level tiles | 6,688 | 4,948 | 0.740 | 409 | 2.04× |

**Why UFTC fails on sprites:** Sonic has 13,700 total 4×4 blocks with 8,367 unique — only 1.64× reuse. The dictionary (66,936 bytes) dominates the compressed output. The only significant block reuse is blank/transparent blocks (21.1% of total). Non-transparent blocks are almost all unique.

Tested four different block-splitting strategies (spatial 4×4 quadrants, row pairs, single rows, bytewise pairs). All give 0.86–0.94 ratio on character sprites. No splitting method recovers the claimed ~50%.

## Reference Game Survey: How Do They Handle Per-Frame Sprite Art?

### Uncompressed + DPLC (all Sonic engines)

**sonic_hack (Sonic 2 base):** Sprite art stored uncompressed in ROM (`ArtUnc_Sonic`, 110 KB). DPLC tables map each animation frame to tile ranges. On frame change, `LoadSonicDynPLC` queues DMA transfers from ROM directly to VRAM. Zero CPU decompression cost.

**S.C.E. (S3K base):** Same DPLC approach via `Perform_DPLC`. Per-object `ros_prev_frame` tracking prevents redundant DMA on unchanged frames. Art stored uncompressed, DMA from ROM.

**Key insight:** DPLC is not a compression format — it's a tile selection system. Art stays uncompressed in ROM; DPLC just tells the DMA which tiles to load each frame. This is effectively free (VDP DMA runs on its own clock).

### Raw Uncompressed (Batman & Robin, Vectorman)

**Batman & Robin:** All art stored raw/uncompressed. No decompression at all. DMA and CPU writes directly from ROM. Compensates with procedural raster effects instead of more art.

**Vectorman:** Pre-computed DMA command lists. Objects provide `(length, source_addr)` pairs. Double-buffered 54-entry queue with 2,880-byte per-frame budget. Art stored uncompressed.

### No Per-Frame Decompression (all references)

**None of the 7 reference projects decompress art per animation frame.** Every one stores sprite art uncompressed and uses DMA from ROM. The CPU cycle cost of any decompression scheme — even UFTC — is overhead that commercial games avoid entirely.

| Project | Sprite Art Format | Per-Frame Loading |
|---------|-------------------|-------------------|
| sonic_hack | Uncompressed + DPLC | DMA from ROM |
| S.C.E. | Uncompressed + DPLC | DMA from ROM |
| Batman & Robin | Uncompressed | DMA/CPU from ROM |
| Vectorman | Uncompressed | DMA from ROM |
| Gunstar Heroes | Uncompressed | DMA from ROM |
| Alien Soldier | Uncompressed | DMA from ROM |
| Thunder Force IV | Uncompressed | DMA from ROM |

## Online Format Survey

Comprehensive search of Genesis homebrew community, SpritesMind, plutiedev, SGDK, Amiga demoscene.

**No alternative random-access tile format exists in the Genesis ecosystem.** UFTC is the only option for per-tile random access with compression. The alternatives are:

| Format | Random Access | Ratio (sprites) | Speed | Notes |
|--------|:---:|:---:|:---:|------|
| **UFTC** (Sik) | Per-tile | 0.75–0.91 | ~821 KB/s | Only random-access format available |
| **LZ4W** (SGDK) | Per-frame-block | 0.45–0.53 | 600–950 KB/s | SGDK stores each frame as separate LZ4W block |
| **Comper** | No | 0.55–0.75 | 800–1200 KB/s | Tiny decompressor, weak ratio |
| **MEGAPACK** (Codemasters) | No | 0.35–0.55 | Slow | Tile-aware, too complex for real-time |
| **PB53/Oracle** (NES) | Per-block | 0.75–0.87 | Fast | Weak ratio, NES-oriented |
| **Raw + DPLC** | Per-tile | 1.00 | Bus speed | Zero CPU, proven |

**SGDK approach (LZ4W per-frame):** Each animation frame's tiles stored as a separate compressed block. Better ratio than UFTC, but decompresses entire frame — can't pick individual tiles. Needs ~1 KB RAM buffer per active character.

**Tanglewood** uses uncompressed + DPLC (traditional Sonic approach).
**Project MD** (Sik's own game) uses UFTC.
**Xeno Crisis** (SGDK) uses LZ4W per-frame.

Sources: plutiedev.com/format-uftc, SpritesMind LZ4W benchmark thread, github.com/sikthehedgehog/mdtools, NESdev Wiki, github.com/lab313ru/megapack-megadrive

## Alternative Approaches Considered

### S4LZ on Full Sprite Sheets
S4LZ achieves ~0.35–0.50 on tile data — much better than UFTC. But S4LZ is sequential-access only. Can't decompress tile #37 without decompressing tiles 0–36 first. Full Sonic sprite sheet is 110 KB — can't decompress to RAM (exceeds 64 KB).

### S4LZ Per Animation Frame Group
Group each frame's tiles (5-8 tiles = 160-256 bytes), compress individually. But S4LZ has 4+ bytes of format overhead per block, and 256 bytes isn't enough data for LZ to find meaningful matches. Ratio would be near 1.0 or worse.

### Tile-Level Dictionary (Full 32-Byte Tiles)
Sonic has 3,068 unique tiles out of 3,425 total — only 10% dedup. Dictionary overhead (indices + unique tile storage) makes this worse than uncompressed.

### Block Size Variants (2×2, 4×8)
Smaller blocks increase dictionary index overhead. Larger blocks reduce sharing. 4×4 is theoretically optimal for the tradeoff, but the absolute reuse is too low on sprite data regardless of block size.

## ROM Budget Analysis

| Category | Estimated Size | % of 4 MB |
|----------|---------------|-----------|
| Character sprites (uncompressed) | ~308 KB | 7.5% |
| Object/enemy sprites (uncompressed) | ~155 KB | 3.8% |
| Level tiles (S4LZ @ 0.50) | ~150 KB | 3.7% |
| Music/SFX/DAC | ~400 KB | 9.8% |
| Code | ~150 KB | 3.7% |
| Other data | ~150 KB | 3.7% |
| **Total** | **~1,313 KB** | **32%** |

Uncompressed sprite art at ~463 KB leaves 2,783 KB free in a 4 MB ROM. This is more than enough headroom for 10+ zones, multiple bosses, and additional content.

## Architecture Decision

**Drop UFTC. Use two-format system:**

| Format | Use Case | Access Pattern |
|--------|----------|----------------|
| **S4LZ** | Level tiles, BG art, large one-time loads | Sequential (decompress full set) |
| **Uncompressed + DPLC** | Character sprites, animated objects | Random-access via DPLC tables (DMA from ROM) |

**Why this is better than UFTC:**
- Zero CPU overhead for per-frame sprite loading (DMA only)
- Simpler codebase (no UFTC encoder/decompressor/format handling)
- Proven by every commercial Genesis game
- ROM cost acceptable (32% of 4 MB total)
- DPLC tables from sonic_hack can be migrated directly

**What changes in ENGINE_ARCHITECTURE.md:**
- §2.1: Remove UFTC from two-tier compression. Replace with "uncompressed + DPLC" for sprites.
- §3 (Object System): DPLC pipeline stays (not "replaced by UFTC" as previously planned)
- §2.2 (Dynamic VRAM Allocator): Still works — AllocVRAM returns VRAM address, DPLC DMAs from ROM to that address. No decompression step needed.
