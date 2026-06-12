# Visibility-Derived Entity Window — Preview Entities (§4.9.5) + Teleport Continuity

**Date:** 2026-06-11
**Status:** Approved
**Closes:** DEFERRED_WORK "§4.9.5 Warp-Based Teleport Preview", "Teleport keep-range tests
pre-shift coords against the post-rebase camera", "No survivor continuity across teleports"
(the latter two close as *dissolved by design*, not patched).

## Problem

1. **No entity preview at seams.** Terrain streams across teleport boundaries (the tile
   cache is world-coordinate driven), but the entity window scans only the slot-pair 2×2,
   so the sections past a seam have no scan entry. Rings/objects pop in only after the
   teleport rebuild. User-visible since rings became visible (2026-06-11).
2. **Keep-range coordinate bug (pre-existing).** `EntityWindow_TeleportShift/ShiftY`
   compare pre-shift entity coords against the already-rebased camera; intended seam
   survivors are reaped instead of kept.
3. Fixing (2) alone re-introduces duplicate spawns on quick reversals (no loaded-mask
   slot exists for just-departed sections) — the two were deferred as a coupled pair.

## Decision

Replace the window's *derivation*, not its machinery: track **the sections the camera's
despawn envelope actually overlaps** instead of "the slot pair × its rows". The preview
problem, the keep-range bug, and the survivor-continuity problem all dissolve under this
rule. Rejected alternatives:

- **Transient preview entries** (4 + 5 zone-gated entries, warped origins, teleport
  migration matrix, populate-time dedupe): works but is correct only by case enumeration
  (FWD/DOWN/corner; proof that BWD/UP need nothing), grows state, and re-opens the
  case analysis on every future threshold change.
- **One-shot warp populate** (original April sketch): broken — the despawn exemption
  only protects tracked-entry sections, so preview entities would be reaped next frame.

## Design

### 1. Window derivation

Tracked set = the 2×2 of sections overlapping the **despawn envelope**:

```
X: [camX − ENTITY_DESPAWN_BUFFER,   camX + SCREEN_WIDTH  + ENTITY_DESPAWN_BUFFER]   (1344 px)
Y: [camY − ENTITY_DESPAWN_BUFFER_Y, camY + SCREEN_HEIGHT + ENTITY_DESPAWN_BUFFER_Y] ( 976 px)
```

Both spans < SECTION_SIZE (2048), so the envelope overlaps **at most 2 columns × 2 rows
— the entry count stays 4**. Derivation:

```
col0 = floor((camX − SLOT_ORIGIN_L − ENTITY_DESPAWN_BUFFER)   / SECTION_SIZE)   ; shift, no div
row0 = floor((camY − SLOT_ORIGIN_U − ENTITY_DESPAWN_BUFFER_Y) / SECTION_SIZE)
window = sections (slot0_x + col0 + {0,1}, slot0_y + row0 + {0,1})
entry origins: x = SLOT_ORIGIN_L + (col0+{0,1})·SECTION_SIZE   (may be $A00, $1200, …)
               y = SLOT_ORIGIN_U + (row0+{0,1})·SECTION_SIZE
```

col0/row0 may be negative or beyond the grid near edges; `Section_GetSecPtrXY`'s range
check voids those entries exactly as today (SEC_VOID stamp + validity mask). The slot
map remains the **anchor** that says which world section engine ($200,$200) is — its
maintenance by the teleport system is unchanged.

Using the *despawn* envelope (the widest band) establishes the core invariant:
**any live windowed entity's section is always tracked.** Entities can no longer outlive
their section's entry (the active-section X-despawn exemption keeps entities alive
arbitrarily far left/right *within* a tracked section — that exemption now applies to
exactly the envelope's sections, which is the correct scope).

### 2. Slides (replaces teleport-driven rebuilds)

A per-frame check in `EntityWindow_Scan` (same shape/cost as the coarse-Y re-scan
trigger) compares (col0,row0) against the stored previous value. On change — a **slide**,
at most once per ~2048 px of travel, and by ±1 in one axis per frame at the 16 px/f
camera clamp (DEBUG-assert both-axes slides don't happen; handle them generically
anyway):

1. **Mask migration by section identity:** for each new entry, search the old 4 entries
   for the same section_id; copy its 32-byte loaded mask. Generic 4×4 match — no
   direction-specific copy tables.
2. Re-init entries (`EntityWindow_BuildEntries` reworked to take the derived window);
   compare-clear wipes masks only for genuinely new sections.
3. `Collected_UpdateCenter` recenters the 3×3 collected/killed window (call moves from
   the teleport path to the slide path; center = the envelope's dominant section, e.g.
   the section containing the camera center).
4. **Band-aware populate** for newly-tracked sections only (existing
   `PopulateSectionRings` + the object X-scan ratchet handles the rest).

Slide-out is despawn-free at the moment of the slide: the departed section's entities
are by definition outside the despawn envelope (or in its hysteresis margin) and the
existing per-frame despawners reap them with their normal rules; the untracked-section
rule provides the backstop.

### 3. Teleports become coordinate re-expressions

A teleport rebase does not change what is visible, so the visibility-derived window
tracks **the same sections** before and after — only their origins re-express
(e.g. FWD: the previewed column at origin $1200 becomes origin $200).
`EntityWindow_TeleportShift/ShiftY` reduce to:

1. Shift ALL slot-tagged entities' coords by the rebase delta (no keep-window — the
   keep-range bug is deleted, not fixed).
2. Re-derive the window (slide check with rebased camera + advanced slot map) — which
   must resolve to the identical section set with new origins. **DEBUG assert** this
   invariance (section ids before == after, modulo entry reordering; reuse the mask
   migration to follow them).
3. No populate at teleport (sections unchanged → nothing new to spawn) → no duplicate
   vector → no runtime dedupe. A DEBUG-build assert in `PopulateSectionRings` (candidate
   (section_id, list_index) already present in the live ring buffer → fail loud) guards
   the invariant instead of runtime code.
4. `Camera_Y_Coarse_Prev` rebases by the delta (Y teleports) so the vertical re-scan
   trigger doesn't false-fire.

### 4. User-visible behavior (the §4.9.5 promise)

- Approaching any seam in any direction: next sections' entities are simply present,
  spawned at warped origins as the envelope reaches them (subject to normal X ratchet +
  Y band rules — same pop-in distance as everywhere else in the world).
- Crossing a seam: **Ring_Count and live object identity are unchanged across the
  teleport frame.** The preview objects ARE the real objects, re-addressed.
- BWD/UP get the same correctness for free (their envelopes never reach unseen sections
  before the threshold — but nothing in the code asserts or depends on that).

### 5. Interactions

- **§4.9.4 respawn memory** (next plan): unchanged — layers over the collected/killed
  window, which keeps its 3×3-by-section-id structure; only the recenter call site moved.
- **Vertical re-scan / Y band / loaded bitmasks / OEF_ANY_Y:** unchanged semantics; the
  re-scan walks whatever entries the derivation provides.
- **Entity exporter / pressure analysis:** the 736px-band 2×2 analysis in
  `ojz_entity_gen.py` already models a camera-centered window — it remains valid
  (conservative) for the new derivation.
- **Section streaming/terrain:** untouched. The slot map, teleport thresholds, preload
  triggers, and tile cache are not modified by this design.

### 6. Edge cases

- Grid edges: negative/overflow cols/rows → void entries (existing SEC_VOID machinery).
  The X void camera clamp ($8C0) and Y guards bound the envelope sanely.
- SEC_VOID slot-map states ((2,VOID) at the grid edge): column derivation runs off
  slot0_x and grid checks — voids fall out; BWD heal re-derives normally.
- Both-axes slide in one frame: impossible at the camera clamp (16 px/f), but the
  generic identity-match migration handles it anyway; DEBUG assert documents the
  expectation.
- Boot: `EntityWindow_Init` derives the window from the boot camera (replaces the
  hardcoded slot-pair init); start positions near seams work without special cases.
- **Negative-origin entries (post-teleport kept column/row):** after a FWD teleport the
  kept left column re-expresses to origin −$600 (engine X of its entities spans
  [−$600, $1FF]). Its surviving entities shifted correctly and stay tracked (despawn
  exemption + mask ownership), but the X scan's unsigned edge compare makes the entry
  inert for NEW spawns — intended: nothing in a negative-origin section can reach the
  screen without a BWD teleport re-expressing it to a positive origin first. Document
  at the scan site; DEBUG assert that a negative-origin entry's ratchet stays 0.
- **Ratchet reset on persisting sections:** `EntityWindow_InitSection` clears scan
  indices unconditionally, so a teleport's re-derivation re-walks persisting sections'
  lists from index 0. Loaded/collected/killed bits gate every re-offer — correct,
  mildly wasteful, teleport-only. Acceptable; do not add same-section index preservation
  without measuring first.

### 7. Performance

- Per frame: derivation + compare ≈ 40 cycles (2 sub, 2 shift, cmp) — replaces nothing
  (new), negligible.
- Slides: ≈ current rebuild cost, once per ~2048 px of travel (cold).
- Teleports: cheaper than today (shift-all loop minus the despawn/keep logic).
- Scan loop, despawners, re-scan: unchanged cost shapes.

### 8. Verification matrix

1. **Seam preview, all three directions** (FWD column, DOWN row, corner diagonal):
   approach slowly — entities appear before the seam at correct world positions.
2. **Teleport continuity:** Ring_Count identical on the frames straddling each teleport
   (FWD/BWD/DOWN/UP); a tracked test object's SST survives the seam (same slot, shifted
   coords).
3. **Quick reversals** across a slide boundary and across a teleport: counts stable,
   no duplicates (DEBUG asserts silent).
4. **Grid edges:** envelope clipped at all four world edges; void entries correct.
5. **Regression:** re-run the §4.9-phase-2 matrix (band culling, vertical re-scan
   idempotency, 10× oscillation, ANY_Y, bottom-edge voids, Ring_Add_Dropped = 0).
6. **DEBUG invariance asserts** active throughout (teleport same-section, populate
   no-dup, single-axis slide).

## Non-goals

- §4.9.4 respawn memory (next plan, layers on top).
- Terrain/parallax preview behavior (already correct; untouched).
- Production entity art; loss rings; magnet shield (player-gated).
