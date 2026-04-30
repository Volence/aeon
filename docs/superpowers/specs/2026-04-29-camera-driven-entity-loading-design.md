# Camera-Driven Entity Loading System

## Overview

Replace the current teleport-triggered bulk entity loading with a camera-driven sliding window. Entities (rings and objects) load as they scroll into camera range and despawn when they leave. This eliminates preview zone pop-in, boundary respawn issues, and the coordinate-shifting complexity of the teleport-triggered approach.

**Replaces:** §4.9 teleport-triggered entity lifecycle (Section_LoadSlotEntities, ExpandRings, save/restore bitmasks, entity blocks in Section_TeleportFwd/Bwd).

**Motivation:** The teleport-triggered system caused three problems:
1. Rings/objects respawned instantly when crossing the teleport boundary and returning (1-pixel round-trip)
2. Entities in the preview zone popped in only after teleport fired
3. Coordinate shifting by ±SECTION_SHIFT caused 16-bit unsigned wrapping for entities far from camera

The camera-driven sliding window solves all three: entities appear as they scroll into view, disappear when they scroll out, and the sliding window naturally preserves state for nearby entities without any persistence bitmask.

## Data Format Changes

### Ring Layouts — Build-Time Flat Expansion

Ring layouts switch from runtime pattern-encoded format (H-line/V-line/individual with count and spacing fields) to **pre-expanded, X-sorted flat lists** generated at build time by `ojz_strip_gen.py`.

**ROM format per ring (4 bytes):**
```
dc.w  X    ; bits 9-0 = section-local X (0-$3FF), bits 15-10 = reserved (0)
dc.w  Y    ; bits 9-0 = section-local Y (0-$3FF), bits 15-10 = reserved (0)
```
Terminated by `dc.l 0`.

Entries must be sorted ascending by X. The build tool handles expansion and sorting from the authoring format (which can still use H-line/V-line definitions).

The reserved high bits (6 per coordinate, 12 total) are available for future use (ring value variants, art variants, behavior flags). Not used in this design.

**ROM size tradeoff:** An H-line of 5 rings goes from 4 bytes (one pattern entry) to 20 bytes (5 × 4-byte entries). At current ROM usage (11.5% of 4MB), this is negligible.

### Object Layouts — X-Sorted, Same Format

Object entries remain 4 bytes: `[2-bit reserved][10-bit X][10-bit Y][5-bit type][5-bit subtype]`. Must be X-sorted ascending in ROM. The build tool enforces sort order.

### Type Tables — ROM-Only, No RAM Copy

Per-section type tables stay as count-prefixed ObjDef pointer arrays in ROM. The Object_Type_Table RAM copy (128 bytes) is removed. At spawn time, the sliding window reads the section's ROM type table directly to resolve the ObjDef pointer, then passes it to Load_Object. After spawning, the object doesn't need the type table.

## Unified Ring Buffer

One ring buffer replaces the two slot buffers. 128 entries max.

**RAM format per entry (6 bytes):**
```
dc.w  engine_X     ; world-space X (section-local + section origin)
dc.w  engine_Y     ; world-space Y
dc.b  section_id   ; which section this ring belongs to
dc.b  list_index   ; index in section's ROM ring list (for removal tracking)
```

6 bytes × 128 entries = 768 bytes.

**Buffer management:**
- **Add:** append to end, increment count
- **Remove** (on collection or off-screen): swap with last entry, decrement count. O(1). Buffer order doesn't matter — sorted scanning uses the ROM list, not the RAM buffer.

**Single count byte:** `Ring_Count` replaces `Ring_Count_0`/`Ring_Count_1`.

### 3×3 Rolling Collected Bitmask

A 3×3 sliding window of per-section bitmasks tracks which rings have been collected. The player's current section is the center; the 8 surrounding sections also retain collected state. When the player enters a new section, the box shifts and sections that fall outside get their slots cleared (rings there will respawn on next visit).

**RAM format per slot (18 bytes):**
```
dc.b  section_id_tag    ; which section owns this slot ($FF = empty)
dc.b  pad
ds.b  16                ; 128-bit collected bitmask (1 bit per ring)
```

9 slots × 18 bytes = 162 bytes.

**At spawn time:** scanner looks up `section_id` in the 9 tags. If found, check `bitmask[list_index]`. If bit set, skip (already collected). If not found, ring is uncollected.

**At collect time:** find the slot matching the ring's `section_id` (guaranteed to exist since the ring's section is within the scanner's range, which is always inside the 3×3 box). Set the bit.

**On center section change:** when the player enters a new section, any slot whose `section_id` falls outside the new 3×3 range gets cleared (`section_id_tag = $FF`). The freed slot is available for newly-entered sections.

**Why 3×3:** a section must exit the box before its rings can respawn. That requires 2+ sections of travel (~$1000 pixels, ~3 screen widths). Large enough that respawn feels natural. The entity scanner's 4 tracked sections (2 active + 2 preview neighbors) are always a subset of the 3×3 box. Works for any grid size — infinite levels supported. 2D-native with no modulo collision issues.

## Sliding Window Mechanism

### Per-Frame Entity Scan (EntityWindow_Scan)

Called once per frame after Camera_Update, before RunObjects and DrawRings.

For each tracked section (the two active sections in Slot_Section_Map, plus the BWD and FWD neighbor sections for preview zone coverage — 4 sections total):

**Right edge — spawn ahead:**
Scan the section's X-sorted ROM list forward from `right_load_index`. For each entry where `section_local_X + section_origin` falls within `Camera_X + screen_width + buffer` (~$180px ahead of camera right edge): add to the ring buffer (rings) or call Load_Object (objects). Advance `right_load_index`.

**Left edge — spawn behind (when scrolling left):**
Scan backward from `left_load_index`. Same range check against `Camera_X - buffer` (~$180px behind camera left edge). Advance `left_load_index` backward.

**Despawn — remove out-of-range:**
Iterate the ring buffer. Any ring whose `engine_X` is outside `Camera_X - buffer` to `Camera_X + screen_width + buffer`: remove via swap-with-last.

For objects: any dynamic object whose `SST_x_pos` is outside the range and carries a slot tag: DeleteObject.

**Amortized cost:** Typically 0-2 entities cross the boundary per frame. The sorted ROM list means scanning stops as soon as an out-of-range entry is hit.

### Per-Section Scan State (RAM)

Each tracked section needs a small scan state block:

```
dc.w  right_load_index   ; next unloaded entry index (scanning right)
dc.w  left_load_index    ; next unloaded entry index (scanning left)
dc.l  rom_ring_list_ptr  ; pointer to section's ROM ring list
dc.l  rom_obj_list_ptr   ; pointer to section's ROM object list
dc.l  rom_type_table_ptr ; pointer to section's ROM type table
dc.w  origin_x           ; section's engine-space X origin
```

~16 bytes per section, 4 sections tracked (2 active + 2 preview neighbors) = 64 bytes.

### Bidirectional Operation

The window works symmetrically:

```
Moving right:  right edge advances (spawn ahead)
               left edge advances  (despawn behind)

Moving left:   left edge retreats  (spawn behind)
               right edge retreats (despawn ahead)

Standing still: neither edge moves, zero work
```

### Y Range Gate

At spawn time, check vertical distance: `abs(entity_Y - Camera_Y)`. If beyond ~$180px, skip spawning. Prevents loading entities from vertically distant parts of a section. Same pattern as sonic_hack's ChkLoadObj Y gate.

## Teleport Integration

On camera teleport (Section_TeleportFwd / Section_TeleportBwd), the entity system does minimal work:

1. **Shift on-screen entities** — iterate the ring buffer and dynamic object slots. Anything within `Camera_X ± $180` (screen + preview buffer) gets its position shifted by ±SECTION_SHIFT. These entities are guaranteed to have valid 16-bit results since they're near the camera. Rings: adjust `engine_X` in the buffer entry. Objects: adjust `SST_x_pos`.

2. **Despawn the rest** — rings outside that range: remove from buffer (swap-with-last). Objects outside that range: DeleteObject.

3. **Reset scan state** — the new sections get fresh left/right scan indices. The per-frame scan picks up from the new camera position on the next frame.

No type table reload, no ring expansion, no bitmask save/restore. The sliding window handles everything else naturally.

## Level Init Integration

`Section_Init` (or the game state init) sets up the section map and calls `EntityWindow_Init`, which:

1. Populates scan state for both initial sections (ROM pointers, origins)
2. Runs one full scan pass to load all entities in initial camera range
3. Sets load indices to reflect what was loaded

Alternatively, let the first game frame's `EntityWindow_Scan` handle it — functionally equivalent, but explicit init avoids a 1-frame empty screen.

## Code Changes Summary

### New Code

| Component | File | Purpose |
|-----------|------|---------|
| `EntityWindow_Init` | engine/objects/entity_window.asm | Initial scan at level start |
| `EntityWindow_Scan` | engine/objects/entity_window.asm | Per-frame camera-range scan |
| `EntityWindow_TeleportShift` | engine/objects/entity_window.asm | Shift on-screen entities at teleport |
| `RingBuffer_Add` | engine/objects/rings.asm | Add entry to unified buffer |
| `RingBuffer_Remove` | engine/objects/rings.asm | Swap-with-last removal |
| `DrawRings` (rewrite) | engine/objects/rings.asm | Single-pass, no bitmask |
| `RingCollision` (rewrite) | engine/objects/rings.asm | Single-pass, no bitmask |
| `CollectRing` (rewrite) | engine/objects/rings.asm | Remove from buffer, increment counter |
| Build tool update | tools/ojz_strip_gen.py | Flat X-sorted ring list output |

### Removed Code

| Component | File | Reason |
|-----------|------|--------|
| `ExpandRings` | engine/objects/rings.asm | Replaced by build-time expansion |
| `RingSpacingTable` | engine/objects/rings.asm | No longer needed |
| `Section_LoadSlotEntities` | engine/objects/entity_loader.asm | Replaced by sliding window |
| `LoadTypeTable` | engine/objects/entity_loader.asm | Type tables read from ROM directly |
| `SaveRingBitmask_0/1` | engine/objects/entity_loader.asm | No persistence bitmask |
| `RestoreRingBitmask_0/1` | engine/objects/entity_loader.asm | No persistence bitmask |
| `SpawnSectionObjects` | engine/objects/entity_loader.asm | Replaced by per-entity window spawning |
| Entity lifecycle blocks | engine/level/section.asm | ~120 lines in TeleportFwd/Bwd |
| Pattern-encoding constants | constants.asm | RING_TYPE_HLINE, RING_X_SHIFT, etc. |

### Modified Code

| Component | File | Change |
|-----------|------|--------|
| `DespawnSlotObjects` | engine/objects/entity_loader.asm | Keep, used by teleport shift |
| `Section_TeleportFwd` | engine/level/section.asm | Replace entity block with TeleportShift call |
| `Section_TeleportBwd` | engine/level/section.asm | Same |
| `Section_Init` | engine/level/section.asm | Call EntityWindow_Init instead of LoadSlotEntities |
| `ojz_scroll_test.asm` | test/ | Update init sequence, call EntityWindow_Scan in update loop |
| `entity_data.asm` | data/levels/ojz/act1/ | Flat X-sorted ring lists |
| `act_descriptor.asm` | data/levels/ojz/act1/ | Type table pointers stay in section defs (read from ROM directly at spawn time) |

### RAM Changes

| Removed | Bytes | Added | Bytes |
|---------|-------|-------|-------|
| Ring_Buffer_1 | 512 | Ring buffer (unified, 6-byte entries) | 768 |
| Ring_Bitmask_0 | 16 | Ring_Count (single byte) | 1 |
| Ring_Bitmask_1 | 16 | Section scan state (4 × 16) | 64 |
| Ring_Count_1 | 1 | 3×3 rolling collected bitmask (9 × 18) | 162 |
| Object_Type_Table | 128 | | |
| Ring_Persist_Bitmask | 256 | | |

**Net change:** 929 bytes removed, 995 bytes added = **~66 bytes added** (worth it for infinite-level persistence).

## Constants

```
ENTITY_LOAD_BUFFER      = $180   ; pixels ahead/behind camera to load entities
ENTITY_DESPAWN_BUFFER   = $200   ; pixels beyond load buffer to despawn (hysteresis)
MAX_RING_BUFFER         = 128    ; max rings in unified buffer
RING_BUFFER_ENTRY_SIZE  = 6      ; bytes per ring buffer entry
MAX_TRACKED_SECTIONS    = 4      ; 2 active + 2 preview neighbors
COLLECTED_WINDOW_SLOTS  = 9      ; 3×3 rolling bitmask window
COLLECTED_SLOT_SIZE     = 18     ; 1 tag + 1 pad + 16 bitmask bytes
COLLECTED_EMPTY_TAG     = $FF    ; slot not owned by any section
```

The despawn buffer is slightly larger than the load buffer to prevent oscillation (entity at boundary constantly loading/unloading).
