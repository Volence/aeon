# Vertical Entity Window (§4.9 Phase 2) — Design

**Date:** 2026-06-11
**Status:** Approved
**Closes:** DEFERRED_WORK "§4.9 entity window is X-only — no vertical dimension"

## Problem

The §4.9 entity window is one-dimensional. `EntityScanState` has `ess_origin_x` but no
Y origin; spawn Y is computed as `ROM Y + SLOT_ORIGIN_U` (assumes section row 0); only
the two slot-mapped sections of row r are scanned. Consequences:

1. Entities placed in lower section rows (sec_y ≥ 1) **never load**, even though the
   camera can see those rows (camY window $200–$1200 spans rows r and r+1).
2. After a Y teleport advances the rows, spawn Y for the new rows is wrong (constant
   origin).
3. `OEF_ANY_Y` (entity flag bit 15) is accepted at build time and discarded at runtime.

## Research basis

Full fan-out 2026-06-11 (skdisasm, s2disasm, sonic_hack, S.C.E., Batman&Robin-family
disassemblies, SGDK/homebrew + modern engine patterns):

- **S1/S2 objects: X-only** (s2.asm `ObjectsManager` ~32810, no Y anywhere).
- **S3K objects: X + Y.** X two-pointer scan unchanged; Y band filter at spawn
  (camY−$80..camY+$200, 128px-coarse, sonic3k.asm ~37742); on a coarse camY crossing,
  re-walks only the span between the X pointers; respawn-table bit 7 = "loaded" flag
  makes the re-scan idempotent; **high bit of Y = skip the Y check** (tall objects).
- **S.C.E. kept S3K's Y check** (`Load Objects.asm` 281–286). **sonic_hack added a Y
  gate to S2's ChkLoadObj** (±$180).
- **Rings are X-only in every Sonic engine** — but only because their ring state is
  whole-level resident (S2 `Ring_Positions`, S3K per-level status table); the X window
  bounds per-frame scan cost, not a scarce pool. **Our engine streams rings through a
  shared 128-slot buffer**, so slots ARE scarce: X-only spawning across a 2-row-tall
  window risks silent `RingBuffer_Add` drops. The classics' ring asymmetry does not
  transfer; rings get the same Y band here.
- Modern alternatives rejected: spatial hashing (wins only at 100s of entities per
  query region), room-activation (cannot guarantee 64-slot fit for a 2048×2048
  section), load-everything (RAM scales with level size).

Decision: **S3K-style Y banding for objects AND rings, on a 2×2 quadrant section
window, with loaded-bitmask idempotency and the OEF_ANY_Y opt-out honored.**

## Design

### 1. Quadrant window

`Entity_Scan_State` grows 2 → 4 entries:

| Entry | Slot | Section row |
|---|---|---|
| 0 | left (L) | r |
| 1 | right (R) | r |
| 2 | left (L) | r+1 |
| 3 | right (R) | r+1 |

Entries 0/1 keep today's semantics (existing consumers extend, not change). The
quadrant set derives purely from `Slot_Section_Map` (sec_x per slot) + slot sec_y —
Y teleports pin camY to $200–$1200, so rows r/r+1 are always the only visible rows.
No per-frame geometry.

Void quadrants (sec_x = SEC_VOID, or row ≥ grid_h, or row < 0): entry stamped
SEC_VOID, skipped by all scans. `Entity_Window_Active` becomes a **4-bit validity
mask** (was a count). Despawn exemption reads all 4 entry ids; SEC_VOID stamps keep
stale ids from exempting dead sections (mirrors the existing X void pattern).

### 2. Data structures

- `EntityScanState` += `ess_origin_y` (word). Struct $18 → $1A. `SLOT_ORIGIN_U`
  constant removed from the spawn path.
- **Loaded bitmasks**: per entry index (0–3), 128 bits rings + 128 bits objects
  = 32 bytes × 4 = 128 bytes RAM. Indexed by entry index (no FindSlot search).
  Transient: cleared whenever the entry's section changes; moved (copied) when an
  entry's section migrates between entry slots on Y teleport.
- `Camera_Y_Coarse_Prev` (word): 128px-coarse camY for the re-scan trigger.
- New constants: `ENTITY_LOAD_BUFFER_Y` (≈$100) and `ENTITY_DESPAWN_BUFFER_Y`
  (> load, hysteresis). Tunable at one site.
- Net new RAM ≈ +190 bytes.

### 3. Spawn path (shared shape for rings + objects)

X-sorted scans (`ScanRingsRight/Left`, `ScanObjectsRight/Left`, populate paths) gain:

1. engine-Y = ROM Y + `ess_origin_y` (replaces SLOT_ORIGIN_U).
2. Y band check: spawn iff engine-Y within
   `[camY − ENTITY_LOAD_BUFFER_Y, camY + 224 + ENTITY_LOAD_BUFFER_Y]` (128px-coarse).
   - Objects with `OEF_ANY_Y` (bit 15) skip the band check.
   - Rings have no flags word and never need ANY_Y (16px tall).
3. Loaded-bit check before spawn; set on spawn. Both the X scan and the Y re-scan
   honor it — no path can double-spawn.

X index advance is unchanged: an entity skipped for Y still advances the X index
(S3K behavior); the Y re-scan is what catches it later.

### 4. Vertical re-scan

When coarse camY (128px) changes (≤1 boundary/frame at the 16px/f camera clamp):
for each valid entry, re-walk its ROM ring + object lists **only between its
left/right X indices**, applying the same band + loaded-bit + collected/killed
checks. No newly-exposed-strip math — the loaded bitmask makes a full-band walk
idempotent at the same cost magnitude (tens of entries × 2 compares). Fires for
both up and down motion.

### 5. Despawn

`EntityWindow_DespawnRings` / `DespawnObjects` gain the Y dimension: an entity
outside `[camY − despawnY, camY + 224 + despawnY]` despawns (ring buffer remove /
SST delete) and its loaded bit clears. ANY_Y objects are exempt from Y despawn
(X rules still apply). Untracked-section despawn checks all 4 entry ids.

### 6. Teleport integration

- **X teleports** (`EntityWindow_TeleportShift`): origin shift covers all 4
  entries; rebuild populates the full quadrant set with void stamping.
- **Y teleports** (`TeleportShiftY` + rebuild): on Down, entries [2,3]'s sections
  become entries [0,1]; **their loaded bitmasks move with them** so the
  post-teleport populate doesn't double-spawn survivors; the newly exposed row
  populates fresh; old-row entities exit via the Y despawn band naturally after
  the camY rebase. Up mirrors. The existing TeleportShiftY/RebuildScanState
  mechanics get a dedicated research pass before this task (subtlest part).
- Y teleports recenter the 3×3 collected/killed window via
  `Collected_UpdateCenter` (already 2D-capable — no changes to bitmask windowing).

### 7. Edge cases

- Bottom grid row: r+1 ≥ grid_h → entries 2/3 void. Top: r−1 never tracked (camY
  window can't see above row r by construction).
- X grid edge: SEC_VOID right column composes — minimum 1 valid entry.
- Section-boundary entities: owned by exactly one section in editor data; origins
  make spawn math exact, no overlap or double-ownership.
- Teleport during re-scan frame: teleport handlers run before the per-frame scan;
  rebuild resets `Camera_Y_Coarse_Prev` so the next re-scan is consistent.

### 8. Instrumentation & verification

- DEBUG: ring-buffer high-water-mark counter; assert (or at minimum a counter) on
  `RingBuffer_Add` overflow — silent drops become visible.
- Exodus test plan:
  1. Author test rings/objects in row-1 sections of OJZ act1 (editor
     `section_N.rings.json` / `.objects.json` for sections 3–8).
  2. Descend → row-1 entities spawn at correct world positions.
  3. Band culling: entities far below camera stay unspawned until approached.
  4. Vertical re-scan: approach from above/below spawns them; ring count stable
     across repeated up/down passes (idempotency).
  5. Y teleport down/up: survivors persist (no double-spawn, no state reset).
  6. Bottom-edge: void quadrants, no asserts.
  7. ANY_Y test object spawns regardless of camY.

## Non-goals

- §4.9.4 respawn memory (rolling 4-slot save/restore) — separate follow-up; this
  design keeps its interface points (bitmask save/restore wraps populate/unload).
- §4.9.5 warp-based preview entities — reshaped by teleport-rebase; not touched.
- Ring/object production art — separate deferred item.
