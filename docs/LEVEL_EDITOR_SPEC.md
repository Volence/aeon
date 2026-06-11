# S4 Engine — Level Data Format Specification

This document describes every data format a level editor must read and write for the Sonic 4 Engine. All data is Motorola 68000 big-endian. All pointer fields are 32-bit ROM addresses. All sizes and offsets are in bytes unless stated otherwise. The assembler is ASL (Macro Assembler AS).

The editor's primary output is **assembly source files** (`.asm`) containing `dc.b`/`dc.w`/`dc.l` directives and label definitions. Some outputs are **binary files** (`.bin`, `.s4lz`) included via `BINCLUDE`.

---

## 1. Act Descriptor (`Act` struct) — 34 bytes ($22)

The Act descriptor is the top-level entry point for a level. The engine stores a pointer to the active one in `Current_Act_Ptr` (RAM).

**Struct definition:** `structs.asm` lines 202–221

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| $00 | long | `sec_grid_ptr` | ROM pointer to flat array of `Sec` structs (section grid) |
| $04 | word | `grid_w` | Sections wide (columns) |
| $06 | word | `grid_h` | Sections tall (rows) |
| $08 | word | `start_local_x` | Player start X within starting section (0–$7FF) |
| $0A | word | `start_local_y` | Player start Y within starting section (0–$7FF) |
| $0C | byte | `start_sec_x` | Starting section grid X index |
| $0D | byte | `start_sec_y` | Starting section grid Y index |
| $0E | word | `cam_min_x` | Camera X lower bound (engine pixels) |
| $10 | word | `cam_max_x` | Camera X upper bound (engine pixels) |
| $12 | word | `cam_min_y` | Camera Y lower bound (engine pixels) |
| $14 | word | `cam_max_y` | Camera Y upper bound (engine pixels) |
| $16 | long | `act_bg_layout` | ROM pointer to zone-wide Plane B nametable (4096 bytes raw) |
| $1A | long | `act_bg_tiles` | ROM pointer to zone-wide Plane B tile blob (2-byte length header + raw tile data) |
| $1E | long | `act_parallax_config` | ROM pointer to default parallax config (fallback when section's is NULL) |

### Camera bounds behavior

Camera bounds are **dynamic at runtime**: the engine extends them by `PREVIEW_PIXELS` (192 px) into neighboring sections when a neighbor exists. At the first/last grid column, `cam_min_x`/`cam_max_x` apply directly. Same for Y at top/bottom rows.

Typical values:
- `cam_min_x = SLOT_ORIGIN_L` ($200)
- `cam_max_x = SLOT_ORIGIN_L + (grid_w * SECTION_SIZE) - SCREEN_WIDTH` (minus 320)
- `cam_min_y = SLOT_ORIGIN_U` ($200)
- `cam_max_y = SLOT_ORIGIN_U + SECTION_SHIFT - 224` ($1120 for a single vertical pair)

### Example (OJZ Act 1, 3×3 grid)

```asm
OJZ_Act1_Descriptor:
    dc.l    OJZ_Act1_Sections       ; sec_grid_ptr
    dc.w    3                       ; grid_w
    dc.w    3                       ; grid_h
    dc.w    $0100                   ; start_local_x
    dc.w    $0100                   ; start_local_y
    dc.b    0                       ; start_sec_x
    dc.b    0                       ; start_sec_y
    dc.w    SLOT_ORIGIN_L           ; cam_min_x
    dc.w    SLOT_ORIGIN_L + $1680   ; cam_max_x
    dc.w    SLOT_ORIGIN_U           ; cam_min_y
    dc.w    SLOT_ORIGIN_U+SECTION_SHIFT-224  ; cam_max_y
    dc.l    OJZ_Act1_BG_Layout      ; act_bg_layout
    dc.l    OJZ_Act1_BG_Tiles       ; act_bg_tiles
    dc.l    ParallaxConfig_OJZ_Default ; act_parallax_config
```

---

## 2. Section Definition (`Sec` struct) — 72 bytes ($48)

Sections are stored as a **contiguous flat array** pointed to by `Act.sec_grid_ptr`. A section at grid position `(sec_x, sec_y)` has flat index `flat_id = sec_y * grid_w + sec_x`. ROM offset: `sec_grid_ptr + flat_id * 72`.

**Struct definition:** `structs.asm` lines 120–148

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| $00 | long | `sec_block_index` | ROM pointer to 256-entry block index table. NULL = empty section. |
| $04 | long | `sec_objects` | ROM pointer to compact 4-byte object entries (X-sorted, `dc.l 0` terminated) |
| $08 | long | `sec_rings` | ROM pointer to ring list (`dc.w X, Y` pairs, `dc.l 0` terminated) |
| $0C | long | `sec_plc` | S4LZ art PLC list pointer (0 = none) |
| $10 | long | `sec_pal` | 128-byte palette pointer (4 CRAM lines × 32 bytes) |
| $14 | long | `sec_parallax_config` | Parallax config pointer (0 = inherit `Act.act_parallax_config`) |
| $18 | long | `sec_raster_table` | Raster command table pointer (0 = none) |
| $1C | long | `sec_bg_layout` | Plane B layout pointer (NULL = use `Act.act_bg_layout`) |
| $20 | long | `sec_type_table` | Type table pointer: `dc.b count, pad; dc.l ObjDef * N` |
| $24 | long | `sec_pal_cycle` | Palette cycling script (reserved, Phase 4) |
| $28 | long | `sec_sound_bank` | DAC sample bank pointer (0 = none) |
| $2C | long | `sec_reserved_2C` | Reserved |
| $30 | long | `sec_anim_blocks` | Animated tile script (reserved, Phase 4) |
| $34 | long | `sec_collision_s4lz` | Reserved (collision embedded in block data) |
| $38 | word | `sec_flags` | `SF_*` bitmask |
| $3A | word | `sec_music` | Music track ID (0 = keep current) |
| $3C | byte | reserved | (was `sec_layer_mask`) |
| $3D | byte | `sec_camera_lookahead` | Lookahead pixels (0 = zone default) |
| $3E | byte | reserved | |
| $3F | byte | reserved | |
| $40 | long | `sec_tile_art_s4lz` | Per-section S4LZ tile art blob pointer |
| $44 | word | `sec_tile_art_vram` | VRAM byte destination (`color_base * 32`) |
| $46 | word | (pad) | |

### Null/zero convention

- `sec_parallax_config = 0`: inherit `Act.act_parallax_config`
- `sec_bg_layout = 0`: use `Act.act_bg_layout`
- `sec_music = 0`: keep current music
- `sec_block_index = 0`: empty section (no geometry)

### Section flags

```
SF_HAS_WATER      = 1<<0    ; Section has a water line
SF_UNDERGROUND    = 1<<1    ; Underground (affects lighting)
SF_NO_Y_WRAP      = 1<<2    ; Disable Y wrapping
SF_PRESERVE_STATE = 1<<3    ; Preserve object state on revisit
```

### Example (section table for 3×3 grid)

```asm
OJZ_Act1_Sections:
; --- Section 0 (0,0) — flat_id 0 ---
OJZ_Sec0:
    dc.l    OJZ_Sec0_Blocks           ; sec_block_index
    dc.l    OJZ_Sec0_Objects          ; sec_objects
    dc.l    OJZ_Sec0_Rings            ; sec_rings
    dc.l    0                         ; sec_plc
    dc.l    OJZ_Palette               ; sec_pal
    dc.l    0                         ; sec_parallax_config (inherit act default)
    dc.l    0                         ; sec_raster_table
    dc.l    0                         ; sec_bg_layout (use act default)
    dc.l    OJZ_Sec0_TypeTable        ; sec_type_table
    dc.l    0                         ; sec_pal_cycle
    dc.l    0                         ; sec_sound_bank
    dc.l    0                         ; sec_reserved_2C
    dc.l    0                         ; sec_anim_blocks
    dc.l    0                         ; sec_collision_s4lz
    dc.w    0                         ; sec_flags
    dc.w    0                         ; sec_music
    dc.b    0, 0, 0, 0               ; reserved bytes
    dc.l    OJZ_Sec0_Tiles_S4LZ       ; sec_tile_art_s4lz
    dc.w    OJZ_SEC0_VRAM             ; sec_tile_art_vram
    dc.w    0                         ; pad
; --- Section 1 (1,0) — flat_id 1 ---
OJZ_Sec1:
    ; ... same 72-byte layout ...
```

---

## 3. Block Data Format

Each section is a **16×16 grid of blocks**. Each block covers **16×16 tiles = 128×128 pixels**.

### Block index table

- Pointed to by `Sec.sec_block_index`
- 256 entries × 4 bytes = 1024 bytes
- Each entry is a longword byte offset from the table start to the S4LZ-compressed block
- Entry value 0 = empty/air block
- Index formula: `entry_index = block_y * 16 + block_x`

### Raw block data (768 bytes per block)

| Component | Byte offset | Size | Layout |
|-----------|-------------|------|--------|
| Nametable | 0 | 512 bytes | 16 rows × 16 cols × 2 bytes/word. Row-major. |
| Collision plane A | 512 | 128 bytes | 8 rows × 16 cols × 1 byte/cell. Half vertical resolution (16px cells). Row-major. Path A (default surface). |
| Collision plane B | 640 | 128 bytes | 8 rows × 16 cols × 1 byte/cell. Same layout as plane A. Path B (inner loop surface). OJZ ships B = copy of A until real secondary data is authored. |

### Nametable word format (standard Genesis VDP)

```
Bit 15:    Priority
Bit 14-13: Palette line (0-3)
Bit 12:    V-flip
Bit 11:    H-flip
Bit 10-0:  Tile index (0-2047, ABSOLUTE VRAM slot)
```

**Critical:** Tile indices are **absolute VRAM indices**. They embed the section's VRAM base. Cloned sections sharing block data MUST use the same `sec_tile_art_vram` value.

### Block binary file layout

Each `sec{N}_blocks.bin` file:
```
Bytes 0–1023:    256 × dc.l offset (block index table)
Bytes 1024+:     S4LZ-compressed blocks concatenated
```

Each compressed block is S4LZ encoding of 768 raw bytes (512 nametable + 128 collision plane A + 128 collision plane B).

### Constants

```
BLOCK_TILE_SIZE          = 16       ; tiles per block side
BLOCK_NT_SIZE            = 512      ; nametable bytes per block
BLOCK_COLL_ROWS          = 8        ; collision rows per block (per plane)
BLOCK_COLL_PLANE_SIZE    = 128      ; collision bytes per plane
BLOCK_COLL_SIZE          = 256      ; total collision bytes per block (2 planes)
BLOCK_RAW_SIZE           = 768      ; 512 + 128 + 128
TILE_CACHE_COLL_PLANES   = 2        ; path A + path B
BLOCKS_PER_SECTION_AXIS  = 16
BLOCK_INDEX_ENTRIES      = 256      ; 16 × 16
BLOCK_INDEX_SIZE         = 1024     ; 256 × 4
```

---

## 4. Tile Art and Compression

### S4LZ compression format

Custom word-aligned LZ compression.

**Header (4 bytes):**

| Offset | Size | Description |
|--------|------|-------------|
| $00 | word | Uncompressed size in bytes |
| $02 | byte | Flags: bit 0 = tile-delta XOR preprocessing |
| $03 | byte | Reserved (0) |

**Body:** Token-based sequences. Each token has a high nibble (literal word count) and low nibble (match word count). Token byte $00 = end of stream. 15 in either nibble triggers an extended count word. See `engine/s4lz_decompress.asm` for full decode logic.

**Tile-delta preprocessing** (flag bit 0): After decompression, each 32-byte tile is XOR'd against the previous tile. Used for tile art blobs where adjacent tiles share patterns.

### Per-section tile art

Each section has:
- `sec_tile_art_s4lz`: S4LZ-compressed tile art blob (with tile-delta)
- `sec_tile_art_vram`: VRAM byte destination = `first_tile_index * 32`

### VRAM graph-coloring

Adjacent sections in the grid (which can be co-visible during teleport transitions) must have **different VRAM base addresses** so their tile art doesn't overlap. The build pipeline assigns VRAM bases using graph coloring.

Auto-generated file `data/generated/ojz/act1/sec_vram_bases.asm`:
```asm
OJZ_SEC0_VRAM = 113 * 32   ; = $0E20
OJZ_SEC1_VRAM = 0 * 32     ; = $0000
OJZ_SEC2_VRAM = 113 * 32   ; non-adjacent to sec1, can reuse sec0's color
```

### Shared BG tiles

Zone-wide background tiles occupy a separate VRAM region:
```
BG_TILE_BASE_VRAM = $8000   ; byte address (tile slot 1024)
BG_TILE_CAPACITY  = 512     ; tiles
```

`act_bg_tiles` blob: 2-byte big-endian length header + raw (uncompressed) tile data. Loaded once at level init.

### BG nametable layout

`act_bg_layout` points to a raw 64×32 nametable = 4096 bytes (2 bytes/cell, 64 cols × 32 rows, row-major). Written directly to VDP Plane B nametable at $E000.

---

## 5. Section Grid and Coordinate Model

### 2D grid

`grid_w × grid_h` sections stored flat: `flat_id = sec_y * grid_w + sec_x`. ROM offset: `sec_grid_ptr + flat_id * Sec_len`.

Each section is **$800 × $800 pixels (2048 × 2048)** = **256 × 256 tiles**.

### Engine-space coordinates

The engine uses a fixed coordinate space with slot origins:

```
SLOT_ORIGIN_L = $0200    ; left slot X origin (512 px)
SLOT_ORIGIN_R = $0A00    ; right slot X origin (2560 px)
SLOT_ORIGIN_U = $0200    ; upper slot Y origin (512 px)
SLOT_ORIGIN_D = $0A00    ; lower slot Y origin (2560 px)
SECTION_SIZE  = $0800    ; section side in engine pixels (2048 px)
SECTION_SHIFT = $1000    ; teleport shift amount (4096 px)
```

### Slot model

The engine maintains 4 slots in RAM:
- `Slot_Section_Map` (4 × 2 bytes): `[sec_x.b][sec_y.b]` per slot
- `Slot_Origins` (4 × 8 bytes): `[origin_x.l][origin_y.l]` per slot
- Slot 0 = left/upper section, Slot 1 = right/lower section

### Teleport thresholds

When the player crosses a threshold, Camera_X/Y and Player positions shift by `SECTION_SHIFT`, and the slot map advances:

```
; Horizontal (keyed off Player_1.x_pos in engine space)
SECTION_FWD_THRESHOLD   = $1200
SECTION_BWD_THRESHOLD   = $0200
SECTION_FWD_PRELOAD     = $0E00
SECTION_BWD_PRELOAD     = $0400

; Vertical
SECTION_DOWN_THRESHOLD  = $1200
SECTION_UP_THRESHOLD    = $0200
SECTION_DOWN_PRELOAD    = $0E00
SECTION_UP_PRELOAD      = $0400

SECTION_SHIFT           = $1000   ; shift amount for both axes
```

### Preview zones

```
PREVIEW_COLS   = 24       ; nametable columns at FWD/BWD edges
PREVIEW_ROWS   = 24       ; nametable rows at UP/DN edges
PREVIEW_PIXELS = 192      ; = 24 × 8
```

---

## 6. 2D Tile Cache

A sliding window in lower RAM holding decompressed nametable + collision data around the camera.

```
TILE_CACHE_COLS      = 80    ; viewport 40 + margin 20×2
TILE_CACHE_ROWS      = 60    ; viewport 28 + margin 16×2
TILE_CACHE_NT_SIZE   = 9600  ; 80×60×2 bytes
TILE_CACHE_COLL_SIZE = 2400  ; 80×30 bytes (half vertical resolution)
TILE_CACHE_MARGIN_H  = 20
TILE_CACHE_MARGIN_V  = 16
```

Uses circular horizontal indexing. Slides at most 1 column/row per frame to amortize decompression cost.

---

## 7. Parallax Config Format

### parallax_config header — 28 bytes

**Struct definition:** `structs.asm` lines 174–196

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| $00 | byte | `pcfg_band_count` | Number of bands (1–8) |
| $01 | byte | `pcfg_v_factor_bg` | Plane B VScroll shift (15 = locked/no scroll) |
| $02 | byte | `pcfg_v_factor_fg` | Reserved (FG always = camY) |
| $03 | byte | `pcfg_layer_mask` | Bitmask: bit per band, 1 = active |
| $04 | word | `pcfg_v_center_y` | Reference camera Y for VScroll computation |
| $06 | word | `pcfg_v_offset` | VScroll BG value at center_y |
| $08 | byte | `pcfg_transition` | 0 = smooth lerp, 1 = instant snap on section change |
| $09 | byte | `pcfg_deform_speed_fg` | FG H-deform phase increment/frame |
| $0A | byte | `pcfg_deform_speed_bg` | BG H-deform phase increment/frame |
| $0B | byte | pad | |
| $0C | long | `pcfg_deform_table_fg` | 256-byte signed FG H-deform table (0 = none) |
| $10 | long | `pcfg_deform_table_bg` | 256-byte signed BG H-deform table (0 = none) |
| $14 | long | `pcfg_v_deform_table_bg` | 256-byte signed BG V-column deform (0 = whole-plane) |
| $18 | byte | `pcfg_v_deform_speed_bg` | 0 = static, >0 = animated |
| $19 | byte | `pcfg_v_deform_shift_bg` | Amplitude shift on V-column samples |
| $1A | 2 bytes | pad | |

### band_entry — 10 bytes per band (immediately after header)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| $00 | byte | `band_top_cell` | First cell row (0–27). Must be strictly ascending. |
| $01 | byte | `band_factor_a_s1` | Plane A shift1 (0–14; 15 = locked) |
| $02 | byte | `band_factor_a_s2` | Plane A shift2 (0–14; 15 = single-term) |
| $03 | byte | `band_factor_a_op` | 0 = ADD, 1 = SUB |
| $04 | byte | `band_factor_b_s1` | Plane B shift1 |
| $05 | byte | `band_factor_b_s2` | Plane B shift2 |
| $06 | byte | `band_factor_b_op` | 0 = ADD, 1 = SUB |
| $07 | byte | `band_deform_shift_a` | FG deform amplitude shift (15 = no deform) |
| $08 | byte | `band_deform_shift_b` | BG deform amplitude shift |
| $09 | byte | `band_phase_offset` | Phase desync (0–255) |

**Total parallax_config size:** `28 + (band_count × 10)` bytes.

### Factor encoding

Scroll speed = `(camX >> shift1) OP (camX >> shift2)`, then negated for HScroll.

Pre-defined factors:

| Name | Value | Computation | Scroll speed |
|------|-------|-------------|--------------|
| `FACTOR_0` / `FACTOR_LOCKED` | `$0FF` | 0 (locked) | 0% |
| `FACTOR_1` | `$0F0` | `camX >> 0` | 100% |
| `FACTOR_1_2` | `$1F0` | `camX >> 1` | 50% |
| `FACTOR_1_4` | `$2F0` | `camX >> 2` | 25% |
| `FACTOR_1_8` | `$3F0` | `camX >> 3` | 12.5% |
| `FACTOR_1_16` | `$4F0` | `camX >> 4` | 6.25% |
| `FACTOR_3_4` | `$021` | `camX - camX>>2` | 75% |
| `FACTOR_3_8` | `$230` | `camX>>2 + camX>>3` | 37.5% |
| `FACTOR_7_8` | `$031` | `camX - camX>>3` | 87.5% |

### Deform tables

256 signed bytes each. Sampled at `(frame * speed + scanline + phase) & $FF`. Generated by macros in `engine/parallax_macros.inc`:
- `deform_table_sine AMPLITUDE, PERIOD`
- `deform_table_triangle AMPLITUDE, PERIOD`
- `v_column_perspective FOCAL, maxOffset`
- `v_column_floor CENTER, maxOffset`

### Assembly authoring syntax

```asm
ParallaxConfig_MyScene:
    parallax_section layerMask=$1F, vFactorBg=3, vCenter=128, vOffset=0
        band 0,  FACTOR_1, FACTOR_1_8    ; rows 0–3: clouds
        band 4,  FACTOR_1, FACTOR_1_4    ; rows 4–9: far mountains
        band 10, FACTOR_1, FACTOR_3_8    ; rows 10–13: mid mountains
        band 14, FACTOR_1, FACTOR_1_2    ; rows 14–19: hills
        band 20, FACTOR_1, FACTOR_1      ; rows 20–27: ground
    parallax_section_end
```

---

## 8. Entity Data Formats

### 8.1 Object placement (ROM)

Each entry is **6 bytes**, X-sorted ascending, terminated by `dc.w -1` (section-local X is always ≥ 0, so a negative first word is unambiguous as the sentinel):

```
+0  dc.w x          ; section-local X (15-bit usable; bit 15 reserved as list terminator. 0–$7FF for 2048px section)
+2  dc.w y          ; section-local Y (15-bit usable; 0–$7FF)
+4  dc.w flags|type|subtype
      bit 15    = OEF_ANY_Y   (spawn regardless of camera Y — §4.9 phase 2; ignored by engine until implemented)
      bit 14    = OEF_YFLIP   (Y-flip; rol.w #4 in Load_Object maps to RF_YFLIP)
      bit 13    = OEF_XFLIP   (X-flip; rol.w #4 in Load_Object maps to RF_XFLIP)
      bits 12-8 = type index into section's type table (0–31)
      bits 7-0  = subtype (0–255)
```

```asm
OJZ_Sec0_Objects:
    dc.w $200, $0B0, (1<<OEF_TYPE_SHIFT)|0   ; X=$200, Y=$0B0, type 1, subtype 0
    dc.w -1                                   ; terminator
```

**Exporter hard-fail requirements:**
- x and y must be within section bounds (0–$7FF); error if outside.
- type index must be < 32 (5 bits); error if outside.
- subtype must be < 256 (8 bits); error if outside.
- Lists must be emitted X-sorted ascending.

### 8.2 Type table (ROM)

```
+0: dc.b count       ; number of types
+1: dc.b 0           ; pad
+2: dc.l ObjDef_0    ; pointer to ObjDef for type 0
+6: dc.l ObjDef_1    ; pointer to ObjDef for type 1
    ...
```

### 8.3 Object definition (ObjDef, ROM) — v2 archetype template

A 26-byte verbatim ROM image of the SST spawn template (code_addr word +
SST $0A-$21), emitted by the `objdef` macro (macros.asm). No format byte,
no conditional fields — Load_Object burst-copies it with movem:

```
+0:  dc.w objroutine(Code)            ; SST $00 code_addr
+2:  dc.w x_vel, y_vel                ; SST $0A, $0C
+6:  dc.b render_flags|(pri<<5)       ; SST $0E (priority in bits 5-7)
+7:  dc.b collision_resp              ; SST $0F
+8:  dc.l mappings                    ; SST $10
+12: dc.w art_tile                    ; SST $14
+14: dc.b width, height               ; SST $16, $17
+16: dc.b anim, subtype_default       ; SST $18, $19
+18: dc.l anim_table                  ; SST $1A
+22: dc.b status, 0                   ; SST $1E, $1F (angle always 0)
+24: dc.w 0                           ; SST $20-$21 pad (re-inited at spawn)
```

Authored via named parameters (all optional except code/map; the macro
validates pri <= 7 and its own 26-byte emission size):

```asm
ObjDef_Enemy:
        objdef code=TestEnemy_Init, map=Map_TestObj, art=vram_art(...), \
               zpri=4, xvel=ENEMY_PATROL_SPEED, wdth=16, hght=16, col=COLLISION_HURT
```

Per-placement subtype and flip flags come from the entity entry (§8.1)
and are patched after the copy — the template's subtype is only a default.

### 8.4 Ring layout (ROM)

Flat X-sorted list. Each ring: `dc.w X, dc.w Y` (section-local coordinates). Terminated by `dc.l 0`.

```asm
OJZ_Sec0_Rings:
    dc.w $080, $060
    dc.w $090, $060
    dc.w $0A0, $060
    dc.l 0               ; terminator
```

---

## 9. Palette Format

128 bytes = 4 CRAM lines × 32 bytes × 1 = 64 colors. Each color is a Genesis CRAM word: `0000 BBB0 GGG0 RRR0` (9-bit color, only even values per channel: 0, 2, 4, 6, 8, A, C, E).

---

## 10. Collision Data

### Embedded in blocks

Each block has 128 collision bytes (16 cols × 8 rows). Resolution: 16×16 px per cell (half the tile grid's vertical resolution).

### Global height maps and angle table

```
NUM_COLLISION_PROFILES = 256
HEIGHT_PROFILE_SIZE    = 16      ; bytes per profile
HEIGHT_MAP_SIZE        = 4096    ; 256 × 16
ANGLE_TABLE_SIZE       = 256     ; 1 byte per collision type
```

Files:
- `data/collision/heightmaps.bin` — 4096 bytes, floor sensor profiles
- `data/collision/heightmaps_rot.bin` — 4096 bytes, wall sensor profiles
- `data/collision/angles.bin` — 256 bytes, surface angle per type

Generated by `tools/gen_collision_data.py`.

---

## 11. File Organization

```
data/levels/ojz/act1/
    act_descriptor.asm           ← Act descriptor + section table (EDITOR WRITES THIS)
    entity_data.asm              ← Ring lists, object lists, type tables (EDITOR WRITES THIS)

data/generated/ojz/act1/        ← Build-generated (gitignored)
    sec{N}_blocks.bin            ← Block index + S4LZ blocks (EDITOR GENERATES)
    sec{N}_tiles.bin             ← Raw tile art per section
    sec{N}_tiles.s4lz            ← S4LZ compressed tile art (EDITOR GENERATES)
    sec_vram_bases.asm           ← VRAM base assignments (EDITOR GENERATES)
    zone_bg.bin                  ← Plane B nametable (4096 bytes)
    bg_tiles.bin                 ← Shared BG tile blob
    ojz_palette.bin              ← 128-byte palette

data/parallax/
    ojz_default.asm              ← Default parallax config
    scenes/                      ← Per-section parallax configs
    effects/                     ← Deform table library

data/collision/
    heightmaps.bin, heightmaps_rot.bin, angles.bin

data/objdefs/
    test_objects.asm             ← Object definitions
```

### How files are included

`main.asm` includes everything via `include` (assembly) and `BINCLUDE` (binary). The data section includes:
- Parallax configs and deform effects
- Object definitions
- Entity data (ring/object lists per section)
- Act descriptors and section tables
- Block data (`BINCLUDE "data/generated/ojz/act1/sec{N}_blocks.bin"`)
- Tile art (`BINCLUDE "data/generated/ojz/act1/sec{N}_tiles.s4lz"`)
- Collision data, palettes, BG layouts

---

## 12. Build Pipeline

```
1. python3 tools/gen_collision_data.py data/collision
2. python3 tools/ojz_strip_gen.py generate      → per-section tiles, BG, palette
3. python3 tools/ojz_block_gen.py                → sec{N}_blocks.bin
4. python3 tools/s4lz.py compress --tile-delta   → sec{N}_tiles.s4lz
5. python3 tools/s4lint.py main.asm              → lint
6. tools/asl main.asm                            → assemble
7. tools/p2bin                                   → ROM binary
8. tools/fixheader                               → checksum
```

### Key tools

| Tool | Input | Output |
|------|-------|--------|
| `tools/ojz_strip_gen.py` | Reference project data | Tiles, BG, palette, VRAM bases |
| `tools/ojz_block_gen.py` | Strip data | `sec{N}_blocks.bin` |
| `tools/s4lz.py` | Raw binary | S4LZ compressed binary |
| `tools/tile_dedupe.py` | Tile art | Deduplicated tiles with flip detection |
| `tools/gen_collision_data.py` | Height definitions | Binary height maps + angle table |

---

## 13. What the Editor Must Generate

When the user creates or modifies a level, the editor should output:

### Assembly source files

1. **`act_descriptor.asm`** — Complete act descriptor with:
   - Grid dimensions, start position, camera bounds
   - Full section table (all `grid_w × grid_h` entries, each 72 bytes)
   - All label references to data (block pointers, tile art, rings, objects, etc.)

2. **`entity_data.asm`** — Per-section:
   - Ring lists (X-sorted, `dc.l 0` terminated)
   - Object placement lists (X-sorted, `dc.l 0` terminated)
   - Type tables (count + ObjDef pointers)

3. **`sec_vram_bases.asm`** — VRAM base equates per section (graph-colored)

### Binary files

4. **`sec{N}_blocks.bin`** — Per-section block index + S4LZ compressed blocks
5. **`sec{N}_tiles.s4lz`** — Per-section S4LZ compressed tile art (with tile-delta)

### Constraints the editor must enforce

- Section flat array must be contiguous, `grid_w × grid_h` entries of exactly 72 bytes each
- Ring/object lists must be X-sorted ascending
- Object type indices must be valid for the section's type table
- Adjacent sections in the grid must have different VRAM base assignments
- Block nametable tile indices must be absolute and match the section's VRAM base
- All binary data is big-endian

---

## 14. SST (Sprite Status Table) — Object RAM Layout

Each object occupies $50 (80) bytes. Key fields for the editor:

| Offset | Size | Field | Editor-relevant? |
|--------|------|-------|------------------|
| $02 | long | `x_pos` | 16.16 fixed-point X |
| $06 | long | `y_pos` | 16.16 fixed-point Y |
| $24 | byte | `subtype` | Maps to object placement subtype |
| $16 | word | `priority` | Sprite priority band (0–7) |

Object pools: 2 players, 40 dynamic, 16 effects, 8 system = 66 total slots.

---

## 15. VDP Constants

```
VRAM_PLANE_A       = $C000
VRAM_PLANE_B       = $E000
VRAM_SPRITE_TABLE  = $B800
VRAM_HSCROLL_TABLE = $BC00
PLANE_H_CELLS      = 64
PLANE_V_CELLS      = 64
TILE_SIZE          = 32        ; bytes per 8×8 4bpp tile
SCREEN_WIDTH       = 320
SCREEN_HEIGHT      = 224
```

VRAM art pool: tiles $000–$5BF (1472 tiles). BG region: tiles $400–$5FF (512 tiles).
