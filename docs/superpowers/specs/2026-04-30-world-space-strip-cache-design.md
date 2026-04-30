# World-Space Strip Cache with Streaming Collision

## Goal

Replace uncompressed ROM-resident nametable strips and the planned §4.7 flat collision maps with S4LZ-compressed strips, a streaming decompressor with pause/resume, a world-space circular strip cache in RAM, and build-time-authored collision maps derived from tile→collision assignments. This reduces per-act ROM cost from ~360 KB to ~24 KB (15× reduction), enabling 14+ zones in a 4 MB ROM. Introduces the "world space" vs "slot space" coordinate distinction — the strip cache operates as a continuous window over the visible world, seamless across section boundaries and teleports.

## Background

### ROM Budget Problem

Uncompressed nametable strips consume 24 KB per section (256 columns × 96 bytes each). The originally planned §4.7 flat collision maps add 16 KB per section (128×128×1 byte). For a 9-section act, that's 360 KB — limiting a 4 MB ROM to ~4 zones. Measured S4LZ compression of actual OJZ strip data achieves 3–10% ratios, bringing strips to ~2 KB per section. Collision maps (3 KB raw at the revised 128×24 resolution) compress to ~300–900 bytes. Combined per-act cost drops to ~24 KB.

### World Space vs Slot Space

**Slot space:** The engine's internal coordinate system. Two horizontal slots at fixed positions (`SLOT_ORIGIN_L = $0200`, `SLOT_ORIGIN_R = $0A00`). Camera_X, player positions, and object coordinates live here. Teleport shifts everything by `±SECTION_SHIFT`.

**World space:** The continuous coordinate system the player experiences. Section 0 occupies world columns 0–255, section 1 occupies 256–511, etc. The strip cache and decompression streams operate in world space — a teleport doesn't invalidate the cache, it just adjusts the coordinate mapping.

### Supersedes

This design replaces the §4.7 "Per-Section Collision Map + Dual Sensors" section of ENGINE_ARCHITECTURE.md. The dual-sensor system, height maps, and angle arrays survive. The collision storage mechanism (flat 16 KB maps read from ROM) is replaced by compressed build-time-authored maps decompressed into RAM.

## Architecture

### 2D Grid Readiness

All data structures are sized for a 2×2 section grid (4 slots). The initial implementation only uses the horizontal pair (slots 0–1). Vertical slot support is deferred until the 2D section grid ships. Vertical threshold constants are defined but set to unreachable values. The RAM layout reserves 2D-sized regions; the 1D implementation only touches the first half.

When vertical sections ship, the full 2D reservation (strip cache + collision maps + streams = ~27.7 KB) plus existing streaming buffers (8 KB) will exceed 32 KB lower RAM by ~3.7 KB. Resolution deferred — likely by sharing streaming buffers with the strip cache (they're used for tile art preload, not simultaneously with strip decompression).

### Components

1. **Streaming S4LZ Decompressor** — pause/resume at token boundaries, 10-byte bookmark
2. **Strip Cache** — world-space circular buffer, 80 columns × 2 vertical slots
3. **Collision Maps** — build-time-authored flat arrays, S4LZ compressed, preloaded into RAM
4. **Height Maps + Angle Array** — shared ROM tables, global to entire game
5. **Build Pipeline** — strip compression with checkpoints, collision map generation, collision-aware tile deduplication

---

## 1. Streaming S4LZ Decompressor

The existing `S4LZ_Decompress` runs to completion. The streaming variant adds pause/resume capability at token boundaries.

### Bookmark Struct (10 bytes)

```
StreamState_src:      ds.l 1    ; current position in compressed stream (ROM)
StreamState_dst:      ds.l 1    ; current position in output buffer (RAM)
StreamState_xor_prev: ds.w 1    ; previous tile word for tile-delta XOR undo
```

S4LZ tokens are self-contained: literal count + literal words + match offset + match count. No partial state carries across tokens. Every token boundary is a safe pause point. The decompressor processes one token, checks if it has produced enough output bytes, and either continues or saves the bookmark and returns.

### Interface

```asm
; S4LZ_Stream_Init — start a new stream
;   d0.b = slot index (0-3)
;   a0 = compressed source (ROM)
; Parses S4LZ header, initializes bookmark in StreamState[slot]

; S4LZ_Stream_Decompress — decompress N bytes from a stream
;   d0.b = slot index (0-3)
;   a2 = output destination (RAM, within strip cache)
;   d1.w = byte count to produce
; Processes tokens until N bytes emitted or stream ends
; Updates bookmark in StreamState[slot] in-place
```

### Checkpoint Table

Stored in ROM per section, emitted by the compressor. Four entries per section, one every 64 strips (6,144 bytes of output). Each entry is a word — the byte offset into the compressed stream at that output position.

```
; 4 checkpoints × 2 bytes = 8 bytes per section
dc.w  checkpoint_0    ; always 0 (stream start)
dc.w  checkpoint_1    ; compressed offset at strip 64
dc.w  checkpoint_2    ; compressed offset at strip 128
dc.w  checkpoint_3    ; compressed offset at strip 192
```

For backward seeking: find nearest checkpoint before target strip, reset `StreamState_src` to `ROM_base + checkpoint_offset`, set `StreamState_dst` to the corresponding output position, decompress forward. Worst case re-decompresses ~6 KB (~6–9 ms at S4LZ's 700–1100 KB/s throughput on 68000).

### Slot Array

```
S4LZ_Stream_States:  ds.b 10 * 4    ; 4 slots × 10 bytes = 40 bytes
```

Initial implementation uses slots 0–1 only (horizontal pair). Slots 2–3 reserved for vertical sections.

---

## 2. Strip Cache

A circular buffer in RAM holding decompressed strips for the region around the camera. Operates in world space — section boundaries and teleports are invisible to the cache.

### Size and Layout

80 columns × 2 vertical slots × 96 bytes = 15,360 bytes (2D-reserved). Initial 1D implementation uses one vertical slot: 80 × 96 = 7,680 bytes.

80 columns covers the 40-column viewport plus 20 columns of margin on each side for collision sensor range and speculative lookahead (~640 pixels total, roughly two screen widths).

### Metadata (upper RAM, .w addressable)

```
Strip_Cache_Base_Col:    ds.w 1    ; world tile column of ring buffer slot 0
Strip_Cache_Base_Row:    ds.w 1    ; world tile row of vertical slot 0 (0 in 1D)
Strip_Cache_Head:        ds.w 1    ; rightmost valid world column in cache
Strip_Cache_Tail:        ds.w 1    ; leftmost valid world column in cache
Active_Stream_ID:        ds.b 2    ; section IDs currently feeding each vertical slot
```

### Addressing

To read strip data for a given world tile column:

```asm
; d0.w = world tile column
    sub.w   (Strip_Cache_Base_Col).w, d0   ; offset from cache start
    ; modulo 80 for ring wrap
    cmp.w   #80, d0
    blt.s   .no_wrap
    sub.w   #80, d0
.no_wrap:
    ; ×96 via shift+add (no mulu per CLAUDE.md convention)
    lsl.w   #5, d0         ; ×32
    move.w  d0, d1
    add.w   d0, d0         ; ×64
    add.w   d1, d0         ; ×96
    lea     (Strip_Cache).l, a0
    add.w   d0, a0         ; a0 = strip base in cache
    ; index by row: move.w (row*2)(a0), d2 → nametable word
```

### Fill Policy

Each frame, after `Camera_Update`:

1. Calculate rightmost and leftmost world columns needed (viewport + collision margin)
2. If right edge exceeds `Strip_Cache_Head`: call `S4LZ_Stream_Decompress` to produce next strip(s) into the ring buffer at the head position, advance head
3. If left edge is before `Strip_Cache_Tail`: seek to nearest checkpoint, decompress forward to fill leftward, retreat tail
4. On teleport: cache contents remain valid. `Strip_Cache_Base_Col` adjusts by `±SECTION_SHIFT / 8` to stay in sync with the camera coordinate shift. No data is invalidated or re-decompressed.

### Section Stream Transitions

When the streaming decompressor reaches the end of one section's compressed data, it initializes the next section's stream (from the Sec struct's `sec_strips_s4lz` pointer) and continues filling the cache. The cache doesn't distinguish between sections — it's a continuous world-space window.

---

## 3. Collision System

### Flat Collision Map (per-section, compressed)

Each section has a flat byte array — one collision type per 16×16-pixel cell. For a 2048px × 384px section:

- 128 columns × 24 rows = 3,072 bytes raw
- S4LZ compressed: ~300–900 bytes per section

Fully decompressed into RAM at section preload time (same trigger as tile art preloading via `Section_StreamArtGroup`). Four RAM slots for the 2×2 grid; initial implementation populates slots 0–1 only.

### Collision Map Generation (Build-Time)

The collision map is authored, not auto-detected from tile pixels. Auto-detection from pixel content fails for common Sonic art patterns (loop tubes, decorative walls) where tiles are fully opaque but collision should be a slope or air.

The level designer assigns collision types to tiles via the editor. The build tool:

1. Reads the tile→collision LUT (per-zone, authored by designer)
2. For each 16×16 cell (2×2 tiles), selects the dominant non-air collision type (priority: slope > solid > air; if all four tiles differ, bottom-left wins as the floor contact tile)
3. Emits a flat 128×24 byte array
4. S4LZ compresses it

The tile→collision LUT exists only in the build tool — runtime never sees it.

### Collision-Aware Tile Deduplication

The tile deduplication step must treat collision assignments as part of tile identity. Two tiles with identical pixels but different collision types (e.g., walkable ground vs decorative background) get separate VRAM indices. This costs a VRAM slot per variant but ensures the LUT mapping is unambiguous. Typical cost: 5–15 extra tiles per section out of 1536 available.

### Runtime Collision Lookup

```asm
; a0 = Collision_Map_SlotN base (determined by X/Y quadrant routing)
; d0.w = section-local X position, d1.w = section-local Y position
    lsr.w   #4, d0              ; X / 16 → column index
    lsr.w   #4, d1              ; Y / 16 → row index
    lsl.w   #7, d1              ; row × 128 (shift, not mulu)
    add.w   d0, d1              ; flat array offset
    move.b  (a0, d1.w), d0      ; collision type byte
```

~40 cycles per query. Slot routing determines which of the 4 collision map slots to use based on the query position's quadrant in the 2×2 grid. In 1D implementation, Y routing always selects the top row (slots 0–1).

### Height Maps (shared ROM, global)

256 collision profiles × 16 bytes each = 4,096 bytes for vertical floor/ceiling sensors. A second rotated copy for wall sensors = 4,096 bytes. Total: 8,192 bytes, shared across all zones in the entire game.

```asm
; d0.b = collision type (from flat map lookup)
; d2.w = x_pixel & $F (pixel position within 16px block)
    andi.w  #$FF, d0
    lsl.w   #4, d0              ; type × 16
    add.w   d2, d0              ; + pixel column offset
    move.b  HeightMaps(pc, d0.w), d1   ; signed floor height
```

Most profiles are trivial: type 0 = all zeros (air), type 1 = all $10 (flat solid). Real slope profiles only needed for angled terrain. A typical game uses 20–50 distinct slope shapes out of 256 available.

### Angle Array (shared ROM, global)

256 bytes — one surface angle per collision type. Used for slope physics (running speed, character tilt). 8-bit angle where $00 = flat, $40 = 90° clockwise, $80 = ceiling, $C0 = 90° counter-clockwise.

### Dual Floor Sensors

Two sensors per player positioned at `x_pos ± width_pixels/2, y_pos + height_pixels/2`. Each queries the collision map → height map independently. The sensor with the higher floor (lower height value = closer to surface) determines the character's ground contact point. Wall sensors use `HeightMapsRot` with X and Y roles swapped.

### ROM Cost

| Data | Scope | Size |
|---|---|---|
| Height maps (vertical) | Entire game | 4,096 bytes |
| Height maps (rotated) | Entire game | 4,096 bytes |
| Angle array | Entire game | 256 bytes |
| Collision map per section | Per section (compressed) | ~300–900 bytes |
| **Shared total** | | **8,448 bytes** |
| **Per-act (9 sections)** | | **~3–8 KB** |

---

## 4. RAM Layout

All new allocations in lower RAM ($FFFF0000+), which is the 32 KB Decomp_Buffer region — idle after level init.

```
$FFFF0000 ┌────────────────────────────────────┐
           │ Strip Cache (vertical slot 0)      │
           │ 80 strips × 96 bytes               │  7,680 bytes
$FFFF1E00 ├────────────────────────────────────┤
           │ Strip Cache (vertical slot 1)      │
           │ [RESERVED — zeroed in 1D impl]     │  7,680 bytes
$FFFF3C00 ├────────────────────────────────────┤
           │ Collision Map Slot 0               │  3,072 bytes
$FFFF4800 ├────────────────────────────────────┤
           │ Collision Map Slot 1               │  3,072 bytes
$FFFF5400 ├────────────────────────────────────┤
           │ Collision Map Slot 2               │
           │ [RESERVED — zeroed in 1D impl]     │  3,072 bytes
$FFFF6000 ├────────────────────────────────────┤
           │ Collision Map Slot 3               │
           │ [RESERVED — zeroed in 1D impl]     │  3,072 bytes
$FFFF6C00 ├────────────────────────────────────┤
           │ Stream States (4 × 10 bytes)       │
           │ Checkpoint ptrs (4 × 4 bytes)      │  56 bytes (padded to 64)
$FFFF6C40 ├────────────────────────────────────┤
           │ Free                               │  ~5.0 KB
$FFFF7FFF └────────────────────────────────────┘
```

**1D active footprint:** ~13.8 KB (strip cache slot 0 + collision slots 0–1 + stream metadata).
**2D reserved footprint:** ~27.6 KB. Exceeds 32 KB when combined with the existing 8 KB streaming buffers. The 2D overflow (~3.7 KB) is a known issue to resolve when vertical sections ship — likely by sharing streaming buffer space with the strip cache during non-preload frames.

Cache metadata variables (Strip_Cache_Base_Col, Head, Tail, etc.) live in upper RAM for .w addressing — they're accessed every frame. Stream states and checkpoint pointers live in lower RAM — they're only accessed during decompression.

**Note:** The existing `STREAMING_BUFFER_A` ($FFFF0000) and `STREAMING_BUFFER_B` ($FFFF1000) from §2 A.4 are relocated. They previously occupied the start of Decomp_Buffer. With the strip cache now occupying that space, streaming buffers move into the free region at $FFFF6C50+ or share space with the reserved vertical slot 1 region (which is unused in 1D).

### Upper RAM Additions (.w addressable)

```
Strip_Cache_Base_Col:    ds.w 1
Strip_Cache_Base_Row:    ds.w 1    ; 0 in 1D implementation
Strip_Cache_Head:        ds.w 1
Strip_Cache_Tail:        ds.w 1
Active_Stream_ID:        ds.b 2    ; section IDs feeding each vertical slot
                         ds.b 2    ; pad
```

These are added to the existing RAM layout in `ram.asm`, in the level system section.

---

## 5. Build Pipeline

### Per-Section Outputs

**Compressed strips** — `secN_strips.s4lz`:
`ojz_strip_gen.py` currently emits raw 24 KB strip binaries. New step: pipe through `s4lz.py compress` with checkpoint emission. The compressor tracks output bytes and records the compressed stream offset every 64 strips.

**Checkpoint table** — `secN_strip_checkpoints.bin`:
4 entries × 2 bytes = 8 bytes. Emitted by the compressor alongside the compressed stream.

**Compressed collision map** — `secN_collision.s4lz`:
New build step. The strip gen tool reads the tile→collision LUT, samples each 16×16 cell's representative collision type, emits a 128×24 flat array, and S4LZ compresses it.

### Per-Zone Shared Outputs

**Tile→collision LUT** — build tool config only, not shipped in ROM:
Maps tile index → collision type byte. Authored by the level designer. The build tool consumes this to generate collision maps. Each zone has its own LUT.

**Height maps** — `heightmaps.bin` (4,096 bytes), `heightmaps_rot.bin` (4,096 bytes):
16 bytes per collision profile × 256 profiles. Hand-authored from slope geometry. Global to the entire game.

**Angle array** — `angles.bin` (256 bytes):
One angle byte per collision type. Global to the entire game.

### Collision-Aware Tile Deduplication

The existing tile deduplication step in `ojz_strip_gen.py` merges tiles with identical pixels. This must be extended to also compare collision assignments: two tiles with identical pixels but different collision types (e.g., walkable ground tile vs same tile used as background decoration) are NOT merged. They receive separate VRAM indices.

### Sec Struct Changes

```
sec_strips_s4lz:       ds.l 1    ; ROM pointer to S4LZ compressed strip stream
sec_collision_s4lz:    ds.l 1    ; ROM pointer to S4LZ compressed collision map
sec_strip_checkpoints: ds.l 1    ; ROM pointer to 8-byte checkpoint table
```

`sec_strips_a` (raw ROM strip pointer) is removed. `sec_collision` ($34) changes from planned "flat 16 KB map pointer" to "compressed collision map pointer." One reserved field is consumed for the checkpoint pointer.

### Modified Build Flow

```
stamps → flatten → tile dedupe (collision-aware) → graph-color
  → emit strips → S4LZ compress + checkpoint emit → secN_strips.s4lz
  → apply collision LUT → emit flat map → S4LZ compress → secN_collision.s4lz
```

---

## 6. Integration with Existing Systems

### Section_UpdateColumns

Currently reads strip data directly from ROM via `Sec_sec_strips_a` pointers with routing logic (slot 0 / slot 1 / preview neighbor). Changes to read from the strip cache:

```asm
; Current: route world column → Sec_sec_strips_a → ROM read
; New: route world column → Strip_Cache circular buffer → RAM read
    sub.w   (Strip_Cache_Base_Col).w, d0   ; offset from cache start
    cmp.w   #80, d0
    blt.s   .no_wrap
    sub.w   #80, d0
.no_wrap:
    lsl.w   #5, d0
    move.w  d0, d1
    add.w   d0, d0
    add.w   d1, d0
    lea     (Strip_Cache).l, a3
    add.w   d0, a3
    ; read 48 rows from (a3) — same downstream path, RAM instead of ROM
```

The routing logic (which section, which slot, preview neighbor?) is eliminated from `Section_UpdateColumns`. The cache is world-space — every column is just an offset from `Strip_Cache_Base_Col`, regardless of which section it belongs to.

### Section Teleport

Cache contents survive teleport. Adjustments:

- `Strip_Cache_Base_Col` shifts by `±SECTION_SHIFT / 8` to stay in sync with Camera_X shift
- The streaming decompressor state for the departing section is preserved (its data is still in the cache for backtracking)
- A new stream is initialized for the incoming section if not already started via preload
- Collision map slots rotate (same as existing tile art slot rotation)

For 2D: vertical teleport adjusts `Strip_Cache_Base_Row` similarly. Slot rotation becomes 2D (column rotation for horizontal teleport, row rotation for vertical).

### Section Preload

Collision maps decompress at preload time, using the same trigger as `Section_StreamArtGroup` (camera crosses `SECTION_FWD_PRELOAD` / `SECTION_BWD_PRELOAD`). The decompression is fast — 300–900 bytes of S4LZ at ~700 KB/s = under 2 ms. Writes directly to the destination collision map slot.

### Level Init (Cold Start)

At `Level_LoadArt` time (display off, before gameplay):

1. Decompress collision maps for both starting sections into slots 0–1
2. Initialize two `StreamState` bookmarks for the starting sections' strip streams
3. Fill the strip cache with strips covering the starting viewport + margin
4. Set `Strip_Cache_Base_Col` to starting camera position minus half cache width
5. Set `Strip_Cache_Head` / `Strip_Cache_Tail` to reflect filled range

### Per-Frame Update Order

```
Camera_Update
  → Strip_Cache_Fill (decompress new strips if camera advanced past cache edge)
  → Section_Check (teleport thresholds, preload triggers, collision map preload)
  → Section_UpdateColumns (reads from strip cache → plane buffer → VDP)
  → Collision queries (flat map lookup → height maps → angle array)
```

### Vertical Thresholds (2D-Ready, Unused in 1D)

```
SECTION_UP_THRESHOLD   = $7FFF    ; unreachable until 2D grid ships
SECTION_DOWN_THRESHOLD = $7FFF
SECTION_UP_PRELOAD     = $7FFF
SECTION_DOWN_PRELOAD   = $7FFF
```

Defined in `constants.asm` as placeholders. Teleport and preload checks test against these but never trigger.

---

## 7. World-Space Coordinate Convention

### Naming in Code

- **`world_col` / `world_row`** — world-space tile coordinates. Used in strip cache addressing and decompression stream management. Continuous across section boundaries.
- **`slot_x` / `slot_y`** — slot-space pixel coordinates. What most engine code uses (Camera_X, SST positions, object coordinates).
- **`section_local_col` / `section_local_row`** — column/row within a single section (0–255 horizontal, 0–47 vertical). Used in collision map indexing.

### Conversions

```
world_col = slot_col - SLOT_ORIGIN_L/8 + (section_x × SECTION_TILE_WIDTH)
slot_col  = world_col - (section_x × SECTION_TILE_WIDTH) + SLOT_ORIGIN_L/8

world_row = slot_row - SLOT_ORIGIN_U/8 + (section_y × SECTION_TILE_HEIGHT)
slot_row  = world_row - (section_y × SECTION_TILE_HEIGHT) + SLOT_ORIGIN_U/8
```

In 1D implementation: `section_y = 0`, `SLOT_ORIGIN_U/8 = 0`, so `world_row == slot_row`.

### Slot Index Mapping (2×2 Grid)

```
flat_slot = sy * 2 + sx

  sy=0: [slot 0 (left)]  [slot 1 (right)]
  sy=1: [slot 2 (left)]  [slot 3 (right)]
```

Collision map routing, stream state indexing, and collision map preload all use this flat index. In 1D, `sy = 0` always, so `flat_slot = sx` (0 or 1).

---

## Research Findings (Informing Design Decisions)

### Streaming Decompression on 68000

- **Ristar** validates interruptible decompression: Star decompressor yields to VBlank via busy flag + state save to RAM.
- **KosM** (S.C.E./sonic_hack) uses fixed 4 KB modules — zero inter-module state but 5–15% compression ratio penalty from resetting the dictionary per chunk.
- **S4LZ token boundaries** are natural pause points with no bit-stream state. Bookmark is 10 bytes vs Kosinski's 14+ bytes (must also save descriptor word + bit count). Every token is self-contained.
- **Cooperative multitasking** (plutiedev.com) documents the foreground/background decompression pattern on 68000. Applicable for speculative ahead-of-camera decompression in leftover main loop time.

### Tile→Collision Derivation

- **NES/Game Boy games** extensively derive collision from tile indices via LUT (Balloon Fight, Ice Climber, Bubble Bobble, etc.). Well-proven on constrained hardware.
- **No Genesis game found** using this pattern — all use chunk→block→collision indirection. Our approach is novel for the platform.
- **Auto-detection from pixel content** was investigated and rejected: fails for common Sonic art patterns (loop tubes, decorative walls where tiles are fully opaque but collision should be a slope or air). Collision types are authored by the designer, not derived from pixels.

### Compression Format

- **S4LZ** confirmed as correct choice. Comper is faster (800–1200 KB/s vs 700–1100 KB/s) but dramatically worse ratio (0.65–0.75 vs 0.40–0.55). The speed gap is ~100 KB/s; the ratio gap saves hundreds of KB across a full game.
- **Checkpoints for backward seeking** follow the ZSTD seekable format pattern: store compressed stream offsets at regular intervals, seek to nearest checkpoint, decompress forward. S4LZ's 64 KB match window exceeds total section strip size (~24 KB), so checkpoint restart requires no dictionary preservation.

### Height Map Resolution

- **16×16 height profiles** (classic Sonic, Option B) chosen over 8×8. Battle-tested, smoother slopes (16 height samples per block), physics designed around 16px width. 8×8 gives finer granularity but increases profile count and risks stutter at fast speeds from abrupt height transitions between adjacent tiles.
- Height maps and angle array are **global to the entire game** (same as Sonic 2/3). Slope shapes are geometric, not zone-specific. 8.5 KB total, once.
