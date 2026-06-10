# Dual-Layer Collision Research — Loop Path A/B

## Task 7, objects-v2 plan

---

## 1. OJZ collision index source data

**Files in `/home/volence/sonic_hacks/sonic_hack/collision/`:**
- `OJZ primary 16x16 collision index.bin` — 140 bytes
- `OJZ secondary 16x16 collision index.bin` — 138 bytes
- `Collision array 1.bin` / `Collision array 2.bin` — 4096 bytes each

The collision index files provide per-block collision type identifiers.
Each byte is an index into the global collision array (which holds height
map profiles and angle data). "Primary" = path A (the default floor
surface); "secondary" = path B (the inner loop surface, toggled by path
swap objects).

**Key finding:** The secondary collision index file IS available for OJZ in
sonic_hack. It is 138 bytes (vs 140 for primary); 122 of those bytes
differ from the primary index, confirming it is genuinely different data
and not a copy.

**Implication for the strip generator:** `ojz_strip_gen.py`'s
`generate_collision_bytes` currently reads only nametable words and uses
the VDP priority bit (bit 15) as a proxy for solidity. It does NOT read
either collision index file at all — the index files are not even loaded.
The primary/secondary collision files live in `sonic_hack/collision/`; the
strip generator reads only `mappings/16x16/OJZ.bin` (block tile art) and
`mappings/128x128/OJZ.bin` (chunk layout).

**Reading the index data:** The primary and secondary collision index files
are NOT Kosinski-compressed — they are raw bytes, one byte per block
entry, up to the block count of the level. They index into the
global `Collision array 1.bin` (4096 bytes = 256 entries × 16 height
profile bytes).

Wiring the strip generator to decode block IDs from the chunk → block
chain and then index into the collision index files is a non-trivial
pipeline extension (requires matching the block order in `OJZ.bin` to
their entries in the index file). This is a material increase in scope
for this task.

---

## 2. Fallback rule applied: copy layer B = layer A

Per the pre-authorized fallback rule: **layer B is emitted as a COPY of
layer A**. Both planes carry the same priority-bit-derived collision data.
The format ships correctly with dual-plane layout now; real path-B content
(using the secondary collision index) is a build-pipeline task for later.

**Rationale for fallback:**
- The secondary index file exists but the current pipeline doesn't decode
  block IDs to index file positions — that's a separate task.
- The format change (doubling the collision area in blocks and the tile
  cache) is the blocking dependency for path-B support; content comes later.
- With layer B = copy of layer A, the player can switch layers without
  any visual or physics change — correct behavior for a loop that hasn't
  had real path-B data authored yet.

---

## 3. S.C.E. layer-bit convention

S.C.E. uses a global `Collision_addr` RAM pointer that is switched between
`Primary_collision_addr` and `Secondary_collision_addr` by path-swap
objects and by the `Find Floor` routines themselves when the player's
`top_solid_bit` flips (values `$0C`/`$0E` for path A/B). The two
addresses point to the full zone-wide primary or secondary collision index
maps respectively.

**Convention alignment:** S.C.E.'s path A = primary = default; path B =
secondary = the inner loop surface. This matches our SST `layer` byte:
`0 = path A` (primary), `1 = path B` (secondary). The s4_engine
per-object layer select avoids S.C.E.'s global pointer switch; instead
each sensor query carries the layer from the querying object's SST,
which is correct for multi-player or player + carried object scenarios.

---

## 4. Format summary (as implemented)

### Block raw format (768 bytes)
| Component | Offset | Size |
|---|---|---|
| Nametable | 0 | 512 B (16×16 × 2B) |
| Collision plane A | 512 | 128 B (16 cols × 8 rows × 1B) |
| Collision plane B | 640 | 128 B (copy of plane A in OJZ) |

### Tile cache collision (4800 bytes total)
| Region | Symbol | Size |
|---|---|---|
| Plane A | `Tile_Cache_Collision` | 2400 B (80×30) |
| Plane B | `Tile_Cache_Collision + TILE_CACHE_COLL_SIZE` | 2400 B (80×30) |

### Layer select
- `SST_layer(a0)` = 0 → reads plane A (no extra cost)
- `SST_layer(a0)` = 1 → adds `TILE_CACHE_COLL_SIZE` to byte offset before read

---

## 5. RAM budget check

Previous lower RAM end: computed from:
- `Tile_Cache_Nametable`: 9600 B
- `Tile_Cache_Collision`: 2400 B (single plane, pre-change)
- `Block_Stage_Buffers`: `12 × 640 = 7680 B`
- `STREAMING_BUFFER_A/B`: `2 × 4096 = 8192 B`
- `S4LZ_Stream_States`: 48 B
- **Total pre-change**: ~28,020 B

Post-change:
- `Tile_Cache_Collision`: `2 × 2400 = 4800 B` (+2400)
- `Block_Stage_Buffers`: `12 × 768 = 9216 B` (+1536)
- **Added**: +3936 B

New total: ~31,956 B starting from $FFFF0000 → ends at ~$FFFF7CE4.
Guard limit is $FFFF8000 → ~$31C bytes slack. Verified by build guard.
