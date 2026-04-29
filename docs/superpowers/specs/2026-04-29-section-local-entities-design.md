# §4.9 Section-Local Entity Management — Design Spec

## Goal

Make objects and rings appear in levels by tying entity spawning/despawning to the section streaming lifecycle. When a section loads into a slot, its rings and objects load with it. When it unloads, they unload.

## Scope

**In scope (components 1-3 of §4.9):**
- Ring layout format + pattern expansion into slot ring buffers
- Object layout format + per-section type tables
- Spawn/despawn lifecycle hooks in section streaming
- Ring rendering (dedicated DrawRings, no SST slots)
- Ring collection via player overlap
- Shared AABB overlap macro (used by both TouchResponse and RingCollision)
- Test data: hand-authored rings and objects in OJZ Sec0/Sec1

**Deferred (components 4-5, logged in DEFERRED_WORK.md):**
- §4.9.4 Rolling 4-slot state tracking (respawn memory — collected rings/destroyed objects persist across revisits)
- §4.9.5 Warp-based teleport preview (entities spawn at warped coordinates in preview zone)
- Bouncing "loss rings" (scattered SST ring objects when player takes damage)
- Ring attraction (magnet shield pull behavior)

## Architecture

### Ring System

**ROM format:** Pattern-encoded, 4 bytes per entry, 3 types selected by high 2 bits of first word:
- `%00` = individual ring (X, Y)
- `%01` = horizontal line (X, Y, count, spacing)
- `%10` = vertical line (X, Y, count, spacing)

```
; 32-bit entry layout (big-endian):
;   Bits 31-30: type (%00=individual, %01=h-line, %10=v-line)
;   Bits 29-20: X position (10 bits, $000-$3FF, section-local)
;   Bits 19-10: Y position (10 bits, $000-$3FF, section-local)
;   Bits  9- 5: count (5 bits, 0-31 → 1-32 rings) — lines only; reserved for individual
;   Bits  4- 2: spacing index (3 bits) — lines only; reserved for individual
;   Bits  1- 0: reserved
;
; Spacing index: 0=$10, 1=$14, 2=$18, 3=$1C, 4=$20, 5=$24, 6=$28, 7=$30
; Terminated by dc.l 0
```

X/Y are section-local coordinates ($000-$7FF, 10 bits each). Pattern encoding achieves ~58% ROM savings on typical ring layouts vs individual entries.

**Expanded buffer format:** Flat `dc.w x, y` pairs in engine-space coordinates (section-local + slot origin). 128 rings max per slot × 4 bytes = 512 bytes per slot buffer.

**Bitmask:** 16 bytes per slot (128 bits). Bit N = 1 means ring N collected. Checked during rendering and collision to skip collected rings.

**ExpandRings:** One-time at section load. Reads pattern entries from ROM, expands lines into individual positions, converts section-local coords to engine-space by adding slot origin. Stores expanded count for iteration bounds. ~50 cycles per pattern entry.

**DrawRings:** Per frame. Iterates ring buffer for both active slots, skips collected rings via bitmask, writes sprite entries directly to Sprite_Table_Buffer. Uses shared ring animation frame (global counter, 4 frames). No SST slots consumed. ~15 cycles per collected ring (bitmask skip), ~40 cycles per visible ring (sprite write).

**RingCollision:** Per frame. Tests player position against each uncollected ring in both active slots using the shared AABB overlap macro. On hit: sets bitmask bit, increments ring counter, queues sparkle effect via AllocEffect. Ring dimensions fixed at 16×16 for all rings (no per-ring size variation). ~20 cycles per ring for overlap test.

### Object Layout + Type Tables

**ROM layout format:** Compact 4-byte entries with section-local coordinates and local type index:

```
; 32-bit entry: [2-bit reserved][10-bit X][10-bit Y][5-bit type][5-bit subtype]
;   X, Y:     section-local ($000-$7FF, 10 bits each)
;   type:     index into section's type table (5 bits, 0-31)
;   subtype:  object-specific parameter (5 bits, 0-31)
; Terminated by dc.l 0
```

**Per-section type table:** ROM array of ObjDef longword pointers. Each section independently maps up to 32 local type indices to object definitions. A section using 3 types has a 12-byte table.

```asm
OJZ_Sec0_Types:
    dc.l    ObjDef_TestStatic     ; type 0
    dc.l    ObjDef_TestEnemy      ; type 1
    dc.l    ObjDef_TestSolid      ; type 2
```

**RAM type table:** 128 bytes (32 entries × 4 bytes). Copied from ROM at section load. Object spawning reads the 5-bit type index from the layout entry, does one indexed `move.l` from the RAM lookup to get the ObjDef pointer.

**LoadTypeTable:** Copies ROM type table to RAM lookup. Called at section load. Needs the type table pointer and entry count (stored as a byte before the table, or derived from section data).

**SpawnSectionObjects:** Iterates section's object layout entries. For each: extracts type/subtype/position, converts section-local to engine-space (add slot origin), looks up ObjDef pointer via RAM type table, calls `Load_Object`. Tags each spawned object with a slot ID byte in `SST_sst_custom` area.

**DespawnSlotObjects:** Scans Object_RAM for objects matching a given slot tag. Calls `DeleteObject` on each. Runs at section unload (teleport).

### Slot Tag

Each section-spawned object carries a slot tag byte at a fixed SST custom offset. Values:
- 0 = slot L (slot 0)
- 1 = slot R (slot 1)
- $FF = untagged (player, system objects, effects — never despawned by slot cleanup)

Stored as a full byte to support future 2D grid expansion (values 0-3 for LU/RU/LD/RD). Objects not spawned by the entity loader (player, manually spawned test objects) default to $FF.

Offset: `SST_sst_custom+$1D` (last byte of custom area). Chosen to minimize collision with per-object custom data which typically starts at the beginning of the custom area.

### Shared AABB Overlap Macro

Assembler macro `aabb_overlap` expands the AABB overlap test inline. Used by both `TouchResponse` and `RingCollision` — single source of truth for the overlap math, zero runtime call overhead.

```asm
; aabb_overlap — inline AABB overlap test (assembler macro)
; Parameterized by register names so callers use their own allocation.
; Branches to \miss label on no overlap.
; On overlap: \dx = signed delta_x, \dy = signed delta_y available.
```

Optimized for 68000: early-out on X axis before computing Y, all register operations (no memory access in the hot path), branch ordering for the common case (miss).

### Section Streaming Integration

Entity spawn/despawn hooks at four points in the section streaming lifecycle:

**1. Section_Init (level boot):**
After `Section_FillInitial`, for each initial slot:
- LoadTypeTable from section's type table
- SpawnSectionObjects from section's object layout
- ExpandRings from section's ring layout

**2. Preload trigger (.preload_fwd / .preload_bwd):**
After tile art streaming, for the upcoming section:
- LoadTypeTable
- SpawnSectionObjects (objects spawn at engine-space coords in upcoming slot territory)
- ExpandRings

**3. Teleport (Section_TeleportFwd / Section_TeleportBwd):**
- DespawnSlotObjects for outgoing slot tag
- SECTION_SHIFT adjustment: iterate Object_RAM, add/subtract $1000 from every active tagged object's x_pos (same shift applied to Player_1 and Camera_X)
- Shift surviving ring buffer positions by SECTION_SHIFT
- Clear outgoing slot's ring buffer and bitmask

**4. Deferred cold-load (.deferred_fwd_load / .deferred_bwd_load):**
After tile art loading for the new trailing slot:
- LoadTypeTable
- SpawnSectionObjects
- ExpandRings

### Per-Frame Update Order

1. `RunObjects` (existing) — dispatches all SST objects including section-spawned ones
2. `TouchResponse` (existing) — player-vs-object AABB collision, uses shared macro
3. `RingCollision` (new) — player-vs-ring-buffer AABB, uses shared macro
4. `DrawRings` (new) — ring buffer → sprite table entries

### RAM Layout

| Component | Size | Notes |
|---|---|---|
| Ring buffer slot 0 | 512 B | 128 rings × 4 bytes (dc.w x, y) |
| Ring buffer slot 1 | 512 B | 128 rings × 4 bytes (dc.w x, y) |
| Ring bitmask slot 0 | 16 B | 128 bits, 1 = collected |
| Ring bitmask slot 1 | 16 B | 128 bits, 1 = collected |
| Ring count slot 0 | 1 B | number of expanded rings in buffer |
| Ring count slot 1 | 1 B | number of expanded rings in buffer |
| Object type table | 128 B | 32 entries × 4 bytes (RAM copy) |
| Slot origins | 8 B | 2 × (dc.w origin_x, origin_y) |
| Ring counter (HUD) | 2 B | total collected rings (player state) |
| Ring anim frame | 1 B | global ring animation counter |
| **Total** | **~1,198 B** |

### New Engine Files

- `engine/objects/rings.asm` — ExpandRings, DrawRings, RingCollision, CollectRing
- `engine/objects/entity_loader.asm` — SpawnSectionObjects, DespawnSlotObjects, LoadTypeTable
- `engine/objects/aabb.inc` — shared AABB overlap macro (included by collision.asm and rings.asm)

### Test Data

Hand-authored fixtures in OJZ Act 1:
- **Sec0:** 1 horizontal ring line (5 rings), 2 individual rings, type table with TestStatic + TestEnemy (2 object placements)
- **Sec1:** 1 vertical ring line (3 rings), 3 individual rings, type table with TestSolid (1 object placement)
- **Sec2-8:** Empty (`sec_objects = 0, sec_rings = 0`) — entity loader skips NULL pointers

### Testing Strategy

All testing in `ojz_scroll_test.asm` (the section-streaming level test):
- Rings visible on screen in Sec0/Sec1, disappear in Sec2+ (no data)
- Ring collection works (player marker overlaps ring → ring disappears, counter increments)
- Objects spawn when entering a section, despawn when leaving
- Objects survive teleport with correct position (SECTION_SHIFT applied)
- Scrolling back to a section re-spawns fresh entities (no respawn memory yet — deferred)
- Ring animation cycles (4-frame global counter)
- No SST slot leaks (despawn cleans up all tagged objects)

### Constraints

- Max 128 rings per section (bitmask size). Real Sonic levels peak around 50.
- Max 64 objects per section (future bitmask size for rolling state). Real levels peak around 30.
- Max 32 object types per section (5-bit index). Generous — most sections use 5-10.
- Ring dimensions fixed at 16×16 pixels for AABB (standard Sonic ring size).
- Slot tag at `SST_sst_custom+$1D` — object code must not use this offset for custom data.
