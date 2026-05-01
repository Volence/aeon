# 2D Section Grid — Vertical Transitions & 2D Sliding Window Cache

## Goal

Extend the horizontal-only section streaming system to a full 2D section grid. Sections can have neighbors above and below, enabling vertical level design (underground caves, canopy layers, multi-story structures). The strip cache becomes a 2D sliding window over both X and Y. The teleport system handles independent vertical transitions. Diagonal corners get seamless preview via a third preload slot.

## Background

### What exists (horizontal-only, §4.1–§4.7)

The engine has a working 1D horizontal section system:
- 2-slot bidirectional leapfrog (slots 0–1) with preload at midpoint and teleport at slot edge
- World-space strip cache: linear buffer, 80 columns × 48 rows (fixed height), batched memmove slide for eviction, checkpoint-seeking reinit for backward scrolling
- Collision embedded in strip data (24 bytes per column, 16px cells)
- Preview zones: 24-column nametable preview at section boundaries (§4.2)
- Camera-driven entity window with 3×3 rolling collected bitmask (§4.9)
- Strip format: 128-byte columns (96 nametable + 24 collision + 8 pad), power-of-2 stride

### What's stubbed but unused

- `Slot_Section_Map`: 4 slots × 2 bytes `[sec_x.b][sec_y.b]` — slots 2–3 unused
- `Slot_Origins`: 4 slots × 8 bytes `[origin_x.l][origin_y.l]` — slots 2–3 unused
- `SLOT_ORIGIN_U = $0200`, `SLOT_ORIGIN_D = $0A00` — defined but unreferenced
- `SECTION_UP/DOWN_THRESHOLD = $7FFF` — unreachable sentinel values
- `SECTION_UP/DOWN_PRELOAD = $7FFF` — unreachable
- `PREVIEW_ROWS = 24` — defined, never used
- `Act_grid_h` — defined, never checked (all code assumes single-row grid)

### Why the strip cache is linear, not a ring buffer

The original spec designed a circular buffer with modulo-80 wrap. During implementation, the ring buffer was replaced with a linear buffer + batched memmove slide because the 2-slot leapfrog teleport creates coordinate discontinuities that break modulo wrapping. When `SECTION_SHIFT` shifts all positions at teleport, a ring buffer's `Base_Col` adjustment creates ambiguity about which world column maps to which physical slot when the cache spans two sections across a teleport boundary. The linear buffer eliminates this: every position is `Left_Col + byte_offset / stride`, no wrapping, no ambiguity. The 2D extension must preserve this — linear in both axes.

### Supersedes

This design supersedes the "2D Grid Readiness" section of the world-space strip cache spec (`2026-04-30`). It also replaces the stubbed vertical constants and single-row assumptions throughout the section system.

---

## Architecture

### Section Grid

Sections remain **$800×$800 (2048×2048 pixels, 256×256 tiles)**. The grid is a flat array of section descriptors (72 bytes each, Sec struct) indexed by `(sec_y * grid_w + sec_x)`. Null entries represent missing positions — the camera clamps at any edge where the neighbor is null. Levels can be irregularly shaped:

```
       X=0    X=1    X=2
Y=0    null   SEC    null
Y=1    SEC    SEC    SEC
Y=2    SEC    null   null
```

`Act_grid_w` and `Act_grid_h` define the bounding rectangle. The grid array is `grid_w × grid_h` entries, with null pointers for empty cells.

### ROM Data Format — Block-Based

Each section's level data is stored as a **16×16 grid of blocks**. Each block covers **16×16 tiles (128×128 pixels)**.

```
Section ($800×$800 = 256×256 tiles)
├── 16×16 grid of blocks
│   ├── Block (0,0): 16×16 tiles, independently S4LZ-compressed
│   ├── Block (1,0): ...
│   ├── ...
│   └── Block (15,15): ...
├── Block index: 256 entries × 4 bytes = 1024 bytes (ROM)
│   └── Each entry: dc.l compressed_block_ptr (ROM pointer)
└── Block checkpoints: reuse S4LZ stream checkpoints for seek
```

Each block contains:
- **Nametable data:** 16×16 = 256 tile words = 512 bytes raw
- **Collision data:** 8×8 = 64 collision bytes (16px cells, so 16 tiles ÷ 2 = 8 collision rows per block)
- Total raw per block: 576 bytes, S4LZ-compressed independently

**Why 16×16 blocks:** Matches the 16px collision cell size. Each block compresses well individually (enough data for S4LZ patterns). When the cache edge needs one new column, it decompresses a 16-tile-wide block and gets 15 columns "free" for upcoming frames. Same vertically — one row request yields 15 bonus rows. 256 blocks per section is manageable for the ROM index.

**Block index:** Per-section ROM table of 256 longword pointers. Indexed by `(block_y * 16 + block_x)`. Null pointer = empty block (all air / all zero nametable).

### 2D Sliding Window Cache

A linear 2D tile buffer in lower RAM. Holds decompressed nametable and collision data for the region around the camera. Slides in whichever direction the camera moves.

**Dimensions:** ~80 columns × 60 rows of tiles.
- Horizontal: viewport 40 columns + 20 margin each side = 80 columns
- Vertical: viewport 28 rows + 16 margin each side = 60 rows (with SAT relocated, full 64-row plane available; 60 rows gives 16 rows margin = 128px each side at terminal velocity ~16px/frame = 8 frames buffer)

**RAM layout — separate arrays:**

```
; Nametable cache: 80 × 60 × 2 bytes = 9,600 bytes
Cache_Nametable:    ds.b 9600

; Collision cache: 80 × 30 × 1 byte = 2,400 bytes
; (30 collision rows = 60 tile rows ÷ 2, since collision cells are 16px = 2 tiles)
Cache_Collision:    ds.b 2400

; Total: 12,000 bytes (~11.7 KB)
```

Compare to current: 120 physical × 128 bytes = 15,360 bytes. The 2D cache is actually smaller because it eliminates the 128-byte padded stride.

**Tracking variables:**

```
Cache_Left_Col:     ds.w 1    ; world tile col of leftmost valid column
Cache_Head_Col:     ds.w 1    ; world tile col of rightmost valid column
Cache_Top_Row:      ds.w 1    ; world tile row of topmost valid row
Cache_Bottom_Row:   ds.w 1    ; world tile row of bottommost valid row
Cache_Stride:       = 80      ; compile-time constant (columns per row)
```

**Tile lookup** (replaces `Strip_Cache_GetColumn`):

```
; In:  d0.w = world tile col, d1.w = world tile row
; Out: d2.w = nametable word
Cache_GetTile:
    sub.w   (Cache_Left_Col).w, d0      ; col offset
    sub.w   (Cache_Top_Row).w, d1       ; row offset
    mulu.w  #Cache_Stride, d1           ; row offset × stride  — see note
    add.w   d0, d1                      ; linear index
    add.w   d1, d1                      ; × 2 (word-sized entries)
    lea     (Cache_Nametable).l, a0
    move.w  (a0, d1.w), d2
    rts
```

**Note on mulu:** The stride is 80 (not power-of-2). On 68000, `mulu` is 38-74 cycles. For the hot-path collision lookup (called multiple times per frame per object), this is acceptable because the alternative (power-of-2 stride with wasted RAM) trades RAM for speed. If profiling shows `mulu` is a bottleneck, bump stride to 128 and accept 15,360 bytes nametable + 3,840 bytes collision = 19,200 bytes total. Decision: start at 80, profile, widen if needed.

**Alternative:** `mulu` can be replaced with shift-add: `80 = 64 + 16`, so `d1 * 80 = (d1 << 6) + (d1 << 4)` = two shifts + one add = ~20 cycles. Use this in the hot path.

**Collision lookup** (replaces `Collision_GetType` strip-based lookup):

```
; In:  d0.w = world tile col, d1.w = world tile row
; Out: d0.b = collision type byte
Cache_GetCollision:
    sub.w   (Cache_Left_Col).w, d0      ; col offset in cache
    sub.w   (Cache_Top_Row).w, d1       ; row offset in cache (tile rows)
    lsr.w   #1, d1                      ; tile rows → collision rows (2 tiles per 16px cell)
    ; d1 * 80: shift-add (80 = 64 + 16)
    move.w  d1, d2
    lsl.w   #6, d1                      ; × 64
    lsl.w   #4, d2                      ; × 16
    add.w   d2, d1                      ; × 80
    add.w   d0, d1                      ; linear index
    lea     (Cache_Collision).l, a0
    move.b  (a0, d1.w), d0
    rts
```

Callers convert Y pixels → world tile row (`lsr #3`) before calling, same as the current `Collision_GetType` converts to tile columns. The collision array's row stride is half the nametable's because collision cells are 16px (2 tiles) tall.

### Horizontal Streaming (adapted from current)

When the camera moves right and the right edge of the cache needs new columns:

1. Check if new column's block is already decompressed in the block staging area
2. If not, decompress the block containing that column (16×16 tiles) into a temporary block buffer
3. Copy the relevant column from the block buffer into the cache at the rightmost position
4. Advance `Cache_Head_Col`

When the cache fills horizontally, **horizontal slide:** memmove all rows left by N columns to evict stale left-side data. Same batched approach as current `StripCache_Slide` but operates on 2D rows.

Leftward cache miss: checkpoint-seek reinit, same as current `StripCache_Reinit` but re-centers both axes.

### Vertical Streaming (new, symmetric to horizontal)

When the camera moves down and the bottom edge of the cache needs new rows:

1. Check if new row's block is already decompressed
2. If not, decompress the block containing that row
3. Copy the relevant row from the block buffer into the cache at the bottommost position
4. Advance `Cache_Bottom_Row`

When the cache fills vertically, **vertical slide:** memmove all data up by N rows to evict stale top-side data.

Upward cache miss: checkpoint-seek reinit (re-center both axes).

### Block Staging Buffer

When either axis needs data from a new block, the block is decompressed into a temporary staging buffer (576 bytes: 512 nametable + 64 collision). Subsequent column/row requests from the same block read directly from staging — no re-decompression.

```
Block_Stage_Nametable:  ds.b 512    ; 16×16 tile words
Block_Stage_Collision:  ds.b 64     ; 8×8 collision bytes
Block_Stage_ID:         ds.w 1      ; (block_y << 4) | block_x — current staged block
Block_Stage_Section:    ds.w 1      ; section_id of staged block (invalidate on teleport)
```

When the cache is scrolling steadily in one direction, most frames pull from the already-staged block. A new block decompression only happens every 16 columns or 16 rows of camera movement.

### VDP Plane — SAT Relocation

**Relocate SAT** out of the nametable plane to reclaim rows 48–63 for level rendering. The full 64×64 tile plane (512×512 pixels) is available for scrolling.

- **Vertical buffer:** 512 - 224 = 288 pixels = 36 tile rows. Split: 18 above, 18 below the viewport = 144px margin each direction.
- **Horizontal buffer:** 512 - 320 = 192 pixels = 24 tile columns. Split: 12 each side = 96px margin each direction.

SAT (640 bytes = 20 tiles) is relocated to a gap in the VRAM art pool. VDP register $05 updated accordingly. All sprite table writes updated to the new VRAM base address.

### VDP Plane Updates

**Column streaming** (existing, adapted): When horizontal scroll crosses an 8px tile boundary, write a column of tiles to the VDP plane. Source data comes from the 2D cache instead of the old strip format. Column writes set VDP auto-increment to 128 (row stride for 64-wide plane) and write sequentially.

**Row streaming** (new): When vertical scroll crosses an 8px tile boundary, write a row of tiles to the VDP plane. Row writes are naturally sequential in VRAM (adjacent addresses). Source data comes from the 2D cache row.

Both column and row writes go through the deferred Plane Buffer (existing infrastructure). `Section_UpdateColumns` becomes `Section_UpdatePlane` handling both axes.

---

## 2D Teleport System

### Independent Axis Teleport

Each axis teleports independently based on its own threshold pair:

**Horizontal (existing, unchanged in principle):**
- `SECTION_FWD_THRESHOLD` / `SECTION_BWD_THRESHOLD` — camera X triggers teleport
- `SECTION_FWD_PRELOAD` / `SECTION_BWD_PRELOAD` — camera X triggers art preload
- Slots 0–1 leapfrog: current section + horizontal neighbor
- `SECTION_SHIFT` shifts all X positions at teleport

**Vertical (new, symmetric):**
- `SECTION_UP_THRESHOLD` / `SECTION_DOWN_THRESHOLD` — camera Y triggers teleport
- `SECTION_UP_PRELOAD` / `SECTION_DOWN_PRELOAD` — camera Y triggers art preload
- Slots 2–3 leapfrog: current section + vertical neighbor
- `SECTION_SHIFT` shifts all Y positions at teleport (same magnitude as horizontal)

At teleport on either axis:
1. Check for valid neighbor in grid (null = clamp, no teleport)
2. Shift all positions (camera, player, objects) by `±SECTION_SHIFT` on the relevant axis
3. Swap slot roles on that axis
4. Update `Slot_Section_Map` entries
5. Strip cache remains valid (world-space coordinates adjust via `Engine_To_World_Col` / `Engine_To_World_Row`)
6. Mark plane dirty for the teleported axis

### Preload Triggers

Mirror horizontal pattern:
- Camera crosses midpoint on vertical axis → preload next section's art into the behind vertical slot (offscreen, safe to overwrite)
- Deferred cold-load: don't load the new pair's second slot inline — defer to mid-traversal of the new pair's first section (same pattern as `SECTION_DEFERRED_FWD/BWD_LOAD`)

### Vertical Preview Zones

Mirror horizontal `PREVIEW_COLS = 24`:
- `PREVIEW_ROWS = 24` — nametable rows at top/bottom edges showing neighbor section content
- Preview is streaming-integrated: the cache extends its range by `PREVIEW_ROWS` into neighbor section blocks at each vertical boundary
- Preview content only becomes visible when the camera reaches the boundary

---

## Diagonal Corner Preview

### The Problem

At a grid corner, up to 4 sections can be partially visible:
```
    ┌──────┬──────┐
    │ NW   │ NE   │
    │      │  ◉───┼── camera near corner
    ├──────┼──────┤
    │ SW   │ SE   │
    │      │      │
    └──────┴──────┘
```

The horizontal pair covers NW+NE (or SW+SE). The vertical pair covers NW+SW (or NE+SE). But the diagonal section (e.g., SE when camera is in NW) is in neither pair.

### Solution: Third Preload Slot

When the camera approaches a corner (both horizontal and vertical preload thresholds crossed simultaneously), queue the diagonal section's art as a **Deferrable DMA** — the lowest priority, streamed after horizontal and vertical neighbors are loaded.

- By the time the camera reaches a corner, the H and V neighbors should already be mostly/fully streamed (they preloaded earlier at their respective midpoints)
- The diagonal section gets the full streaming bandwidth
- After one axis teleports, the diagonal section becomes a normal neighbor on the other axis — the third preload slot is released

### VRAM Budget Impact

Build-time graph coloring must account for 4-section co-visibility at corners. At a 4-way corner, all 4 sections need distinct VRAM tile indices. With a 1536-tile art pool ($000–$5FF), that's ~384 tiles per section at a 4-way corner. The build tool should warn when a corner's combined tile budget exceeds the pool.

Most corners won't have 4 sections (irregular grids). Many corners will have 2–3 sections, giving more budget per section. The graph coloring already handles co-visibility constraints between horizontal neighbors; extending to include vertical and diagonal neighbors is a natural generalization.

---

## Entity & Ring Window

The current camera-driven entity window (§4.9) with 3×3 rolling collected bitmask extends to cover vertical neighbors:

- Window slides in both X and Y axes (mirrors cache behavior)
- Entity/ring loading triggers when new sections enter the 3×3 neighborhood around the camera
- Collected bitmask tracks which `(sec_x, sec_y)` cells have been loaded — same logic, now 2D
- `SLOT_TAG` system extends: `SLOT_TAG_LEFT/RIGHT` become `SLOT_TAG_LEFT/RIGHT/UP/DOWN` (4 tags for 4 slots)

---

## Coordinate Conversions

### Engine_To_World_Col (existing, unchanged)

Converts engine-space tile column to world-space tile column using horizontal slot mapping.

### Engine_To_World_Row (new)

Symmetric to `Engine_To_World_Col` for the vertical axis:

```asm
Engine_To_World_Row:
    subi.w  #SLOT_ORIGIN_U/8, d0       ; remove vertical slot origin
    moveq   #0, d1
    move.b  (Slot_Section_Map+1).w, d1  ; sec_y of slot 0
    lsl.w   #8, d1                      ; sec_y × 256 tile rows per section
    add.w   d1, d0
    rts
```

### World_To_Block (new)

Convert world tile position to block index and intra-block offset for decompression:

```asm
; In:  d0.w = world tile col, d1.w = world tile row
; Out: d0.w = sec_x, d1.w = sec_y, d2.w = block_index (0–255),
;      d3.w = intra-block col (0–15), d4.w = intra-block row (0–15)
World_To_Block:
    move.w  d0, d3
    move.w  d1, d4
    lsr.w   #8, d0              ; world col / 256 = sec_x
    lsr.w   #8, d1              ; world row / 256 = sec_y
    andi.w  #$FF, d3            ; intra-section col (0–255)
    andi.w  #$FF, d4            ; intra-section row (0–255)
    ; block_index = (intra_row & $F0) | (intra_col >> 4)
    move.w  d4, d2
    andi.w  #$F0, d2            ; block_y * 16
    move.w  d3, d5
    lsr.w   #4, d5
    or.w    d5, d2              ; d2 = block_index
    andi.w  #$F, d3             ; intra-block col
    andi.w  #$F, d4             ; intra-block row
    rts
```

---

## RAM Budget

| Component | Bytes | Notes |
|-----------|-------|-------|
| Cache_Nametable | 9,600 | 80 × 60 × 2 |
| Cache_Collision | 2,400 | 80 × 30 × 1 |
| Block_Stage | 580 | 512 + 64 + 4 metadata |
| Cache tracking vars | 16 | Left/Head/Top/Bottom + stride |
| S4LZ stream states | 40 | 4 streams × 10 bytes |
| **Total cache** | **~12,636** | |

Current strip cache: 15,360 bytes. The 2D cache is ~2,700 bytes smaller.

Other RAM (existing, unchanged): `Slot_Section_Map` (8 bytes), `Slot_Origins` (32 bytes), section streaming state (16 bytes), column/row tracking (8 bytes).

If stride is widened to 128 (power-of-2 for speed): nametable = 15,360 + collision = 3,840 = 19,200 bytes. Only do this if profiling shows the shift-add `×80` is a bottleneck.

---

## Build Pipeline Changes

### Current Pipeline

```
Editor stamps → flatten → deduplicate → graph-color → generate column strips + S4LZ compress
```

### New Pipeline

```
Editor stamps → flatten → deduplicate → graph-color (with 4-section co-visibility)
    → slice into 16×16 blocks → embed collision per block → S4LZ compress each block
    → generate block index table per section
```

Key changes:
1. **Graph coloring** accounts for diagonal co-visibility (4 sections at corners, not just 2)
2. **Block slicing** replaces column-strip generation — level data is organized into 16×16 tile blocks instead of full-height columns
3. **Per-block compression** replaces per-section stream — each block is independently accessible
4. **Block index** per section (256 × 4 bytes = 1 KB ROM per section)

---

## Migration Path

The 2D system replaces the 1D strip cache entirely. Key changes to existing code:

1. **`strip_cache.asm`** — rewrite as `tile_cache.asm`: 2D linear buffer with horizontal/vertical slide, block-based decompression, separate nametable/collision arrays
2. **`collision_lookup.asm`** — update `Collision_GetType` to use `Cache_GetCollision` instead of strip-column lookup
3. **`section.asm`** — add vertical teleport, vertical preload, diagonal preload, `Engine_To_World_Row`
4. **`Section_UpdateColumns`** → `Section_UpdatePlane` — handle both column and row streaming to VDP
5. **`Section_RedrawPlanes`** — adapt for 2D cache as data source
6. **`constants.asm`** — set real values for `SECTION_UP/DOWN_THRESHOLD` and `SECTION_UP/DOWN_PRELOAD`
7. **VDP init** — relocate SAT, update register $05
8. **Entity window** — extend sliding to Y axis
9. **Build pipeline** — new block-based data format, updated graph coloring

### Section descriptor field changes

- `sec_strips_s4lz` (+$00) → `sec_block_index` — pointer to 256-entry block index table (ROM)
- `sec_strip_checkpoints` (+$2C) → `sec_reserved_2C` — block-based format doesn't need stream checkpoints (each block is independently addressable)
- `sec_collision_s4lz` (+$34) — remains reserved (collision embedded in block data)

### What doesn't change

- Section descriptor struct (72 bytes, Sec) — size and layout preserved, only field semantics change
- `Slot_Section_Map` layout — already 4 slots × `[sec_x.b][sec_y.b]`
- `Slot_Origins` layout — already 4 slots × `[origin_x.l][origin_y.l]`
- S4LZ decompressor — blocks are just smaller payloads
- Plane Buffer infrastructure — column/row writes already supported
- World-space coordinate concept — extends naturally to Y axis
- Leapfrog teleport principle — same pattern, independent per axis
