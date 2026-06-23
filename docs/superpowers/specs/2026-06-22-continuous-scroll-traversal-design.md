# Continuous-Scroll Traversal — design spec

**Date:** 2026-06-22
**Status:** Draft — pending user review
**Supersedes:** the 2-slot leapfrog / teleport-rebase traversal model (§4.2 preview-zone, §4.9 slide, the `Slot_Section_Map` slot system) and the corresponding `ENGINE_ARCHITECTURE.md` prose (to be rewritten when this lands).

---

## 1. Goal & non-goals

**Goal.** Replace the 2-slot leapfrog/teleport traversal with **continuous scrolling**: a single world-space camera that moves freely across the whole act, with the VDP plane wrapping for free and the tile-cache/collision/entity systems keyed directly to the world position. This is the classic Genesis model (S2/S3K/S.C.E. — continuous camera over a wrapping plane, layout streamed at the edge, **no rebase/teleport**; confirmed in `docs/research/teleport-rebase.md`). It eliminates the section-boundary seam entirely (there is no teleport to create one) and removes a large, assistant-authored subsystem the resident art pool made unnecessary.

**Why it's possible now.** The act's whole tile ART is resident in VRAM (the act art pool, Phase 1). The leapfrog existed to (a) swap per-section art and (b) keep engine coordinates bounded. (a) is gone (art resident); (b) is unnecessary (the 64×64 VDP plane wraps modulo its size in hardware, and 16.16 world positions fit the act with huge headroom).

**Non-goals.** No change to player physics, animation, the art pool, sound, or the BG-tile model. No change to the tile-cache *internals* (block staging, decompression, the 6-block/2-row budget) — only the *coordinates* feeding it.

---

## 2. The model

**Continuous world camera.** `Camera_X/Y` and `Player_1.x/y` are stored as **world** coordinates (0 … level extent), not the old bounded engine space (`$0200`–`$1200`). Level extent = `grid_w × SECTION_SIZE` × `grid_h × SECTION_SIZE` (OJZ 3×3 = `$1800` = 6144 px). They are 16.16 longwords; `$1800` uses 13 bits of the upper word — fits unsigned with room to an 8×8 grid (`$4000`) before the sign bit. **No overflow at any plausible act size.**

**The identity-collapse (the key simplification).** Every world-coordinate mapping flows through `Engine_To_World_Col/Row` (`tile_cache.asm:11-31`), which today compute `world = (engine − SLOT_ORIGIN) + sec_x*256` from the slot map. With camera+player stored as world coords, **this collapses to identity (`world == engine`)**. So the ~14 collision/tile-cache/streaming callers that go through these functions need **zero changes** — the functions become pass-throughs, and the leapfrog is deleted out from under them.

**VDP plane wrap (free).** Plane A/B are 64×64 (`boot.asm`, reg `$10=$11`) = 512×512 px. The VDP masks the HScroll/VScroll values to the plane dimension, so a continuous world scroll position wraps in hardware. `Camera_X` already feeds `Parallax_Update`'s HScroll buffer with no slot offset; nametable cell writes are already `& 63`. (Verified: the inline nametable cell math `(world_col − sec_x*256 + SLOT_ORIGIN_L/8) & 63` already equals `world_col & 63` today, since `sec_x*256 ≡ 0` and `SLOT_ORIGIN_L/8 = 64 ≡ 0` mod 64 — so the *cell* math is already correct; only the *fill-window clamp* below changes.)

**World → section lookup.** `sec_x = world_px >> SECTION_SIZE_SHIFT`, `sec_y` likewise; `flat_id = sec_y*grid_w + sec_x` via the existing grid-agnostic `Section_FlatIDXY` / `Section_GetSecPtrXY` (unchanged). Only the *source* of `sec_x/sec_y` changes — from `Slot_Section_Map` bytes to a 2-shift derive from the world camera.

---

## 3. Four-system design

1. **Camera (`camera.asm`).** `Camera_Init` stores world coords (`start_sec_x*SECTION_SIZE + start_local_x − CAM_SCREEN_HALF_W`; drop the `+SLOT_ORIGIN_L` bias). `Camera_Update` keeps the deadzone follow and the spindash freeze unchanged, but the clamp block drops all `Section_Edge_Flags`/`PREVIEW_PIXELS` logic and clamps to `[0, level_width − SCREEN_W]` / `[0, level_height − SCREEN_H]` (computed live from grid dims). The vertical clamp reads `(Camera_Y >> SECTION_SIZE_SHIFT)` vs `0`/`grid_h` instead of `Slot_Section_Map`.

2. **Tile-cache / plane (`tile_cache.asm`, `section.asm`).** `Engine_To_World_Col/Row` → pass-throughs (covers the ~14 callers untouched). `Section_UpdateColumns`'s 6 inline plane-wrap **clamps** (`956-963, 977-984, 1017-1025, 1040-1046, 1091-1098, 1138-1144`) migrate from slot-derived visible-left to `Camera_X>>3`-based bounds (the clamp that bounds the per-frame fill to ≤64 distinct columns is load-bearing — it must stay correct, just sourced from the world camera). `Tile_Cache_Init` / `Section_FillInitial` / `Section_RedrawPlanes` migrate their cache-origin seeds + handle **world-origin underflow** (`Cache_Left_Col`/`Top_Row` `bpl/moveq #0` clamps when the camera reaches 0 — a state the leapfrog never allowed). Tile-cache internals (window, block staging, 6-block/2-row budget) unchanged.

3. **Entity / collision (`entity_window.asm`, `collision_lookup.asm`, `player_common.asm`).** `EntityWindow_DeriveWindow` derives the 2×2 envelope from `(Camera − despawn_buffer) >> SECTION_SIZE_SHIFT` (drop `Slot_Section_Map` reads + `SLOT_ORIGIN` bias); the floor/void logic and the 3×3 collected/killed bitmask are unchanged. Collision is world-native already. **`Player_LevelBound` (`player_common.asm:640`) — a live per-frame hard clamp to engine-space literals — must migrate to world bounds `[0, level)` (this was missed in the first pass; unmigrated it pins the player in section 0/1).**

4. **Section-lookup helper.** A tiny 2-shift "camera → (sec_x, sec_y)" for the entity-window anchor and the debug flat-id derive; the actual grid fetch reuses `Section_GetSecPtrXY`/`Section_FlatIDXY` unchanged.

---

## 4. Per-section parallax (kept as a feature)

Sections retain distinct parallax configs. The old per-section parallax snap fired on teleport; the continuous-mode replacement fires on **section-boundary crossing**: detect a change in `(Camera_X >> SECTION_SIZE_SHIFT)` (or Y) frame-to-frame, look up the new section's `sec_parallax_config`, and snap (vs lerp) the parallax bands. `Parallax_Snap_Pending` is repurposed from teleport-triggered to boundary-crossing-triggered.

---

## 5. Removal scope (delete; clean, no vestigial code)

- **RAM (`ram.asm`):** `Slot_Origins`, `Slot_Section_Map`, `Section_Preload_Flags`, `Section_Teleport_Guard`, `Section_Edge_Flags`, `Entity_Window_Anchor/OriginX/OriginY`. Keep `Section_Plane_Dirty` for the level-start full-plane fill only.
- **`section.asm`:** `Section_TeleportFwd/Bwd/Down/Up`, `Section_Check` threshold/guard/preload logic, `Section_UpdateEdgeFlags`, `Section_EngineToWorld`/`WorldToEngine`, `Section_SlotFlatID` (→ use `Section_FlatIDXY`), `Section_GetSlotDef`. Keep `Section_Init`, `Section_UpdateColumns` (migrated), `Section_RedrawPlanes` (init-only, migrated), `Section_GetSecPtrXY`/`Section_FlatIDXY`.
- **`constants.asm`:** `SECTION_SHIFT`, `SLOT_ORIGIN_L/R/U/D`, `SEF_*`, all `SECTION_*_THRESHOLD`/`*_PRELOAD`/`DEFERRED_*_LOAD`, `PREVIEW_COLS/ROWS/PIXELS`, `SPF_*`. Keep `SECTION_SIZE`, `SECTION_SIZE_SHIFT`, `SECTION_TILE_WIDTH/HEIGHT`, `PLANE_*`, `TILE_CACHE_*`, parallax constants.
- **`Engine_To_World_Col/Row`:** pass-through first (verify minimal diff), then **inline-and-delete** so no vestigial call+rts remains in the hot collision/streaming paths (clean end-state).
- **Descriptor:** the engine-space `cam_min/max_x/y` fields are replaced by live computation from grid dims (or slimmed to nothing).
- **Non-issue:** the `player_sensors.asm` `PlayerSensors_SelfCheck` engine→world hand-composition is `__DEBUG__`-only and already off the boot path — no live migration needed (neutralize/remove with the rest).

---

## 6. Phasing

1. **Phase 1 — Horizontal continuous.** Store world coords (X), no-op the conversion fns, migrate the camera X clamp + `Player_LevelBound` X + `Section_UpdateColumns` X clamps + init seeds + world-origin underflow, delete the horizontal teleport/slot machinery, wire per-section parallax snap on X-boundary crossing. **Verify free-flowing horizontal traversal + no seam.** (Y stays clamped as-is this phase.)
2. **Phase 2 — Vertical continuous + edge modes.** Extend to Y. **Render-safety concern RESOLVED by research (2026-06-22): no rework needed** — the "garbage beyond plane row 47" was a *stale comment*, not a real constraint (plane is already 64×64; the SAT was relocated `$D800→$B800` to free rows 48-63; the render path already wraps `world_row & 63`). The garbage on lifting the clamp "as-is" is pure cache under-fill of rows never driven; the streaming is already world-row-based + unbounded. So Phase 2 is unlock + verify: lift the Y clamp to grid-derived full-height, add a configurable per-act vertical **edge_mode**, and run a diagonal/sustained-down on-device verification pass. See §10.
3. **Phase 3 — Cleanup.** Inline-and-delete the conversion pass-throughs; remove any remaining dead state; rewrite `ENGINE_ARCHITECTURE.md` to describe continuous-scroll as the traversal model.
4. **Phase 4 — Floating-origin rebase (future; only when a level needs >16 sections per axis).** The unbounded-level path. Not built until a level actually exceeds the 16-bit coordinate ceiling. Designed up front (§9) so the coordinate layer doesn't preclude it.

---

## 7. Risks & verification (Exodus / oracle MCP)

- **Coordinate migration correctness:** read `Player_1.x/y` + probe a known section-2 ground tile's collision byte; confirm world coords yield the right tile.
- **Plane-wrap alignment:** scroll fully across a section boundary; VRAM viewer shows no torn/duplicated columns (the fill-window clamp bounds ≤64 distinct cols).
- **Streaming budget (the new continuous cost):** the leapfrog never streamed during a teleport (pure rebase, zero columns); continuous scroll streams every moving frame, and diagonal motion demands columns *and* rows against the shared 6-block budget. Run at max scroll across the sec0/1/3/4 corner; watch `Lag_Frame_Count` (the profiler misses bursts — per memory) for pop-in.
- **World-origin/edge underflow:** scroll to camera 0,0 and to the far edges; no negative-coordinate garbage.
- **Vertical (Phase 2):** camera reaches the bottom section row without the old clamp pinning it; no plane-row garbage.

---

## 8. Provenance note

This completes the teardown of the **leapfrog** — an assistant-authored, never-user-decided bet (see `leapfrog-provenance-audit`) — in favor of the classic continuous-scroll model the reference research validated. It is the user-reviewed replacement of the traversal/coordinate model. The art pool (Phase 1) and this traversal change together deliver the free-flowing level that is the completion bar for the OJZ work; the same continuous-scroll model is the foundation the future >VRAM art-streaming end-state builds on.

---

## 9. Floating-origin rebase (future — the unbounded-level path)

**Status:** user-approved as a later phase (Phase 4); built only when a level exceeds the coordinate ceiling. Documented now so the coordinate layer is designed not to preclude it.

**The ceiling it removes.** World positions are 16.16 (pixel value in the 16-bit upper word). Several coordinate ops are signed (deadzone follow, `asr` section-derive, the despawn/load compares), so the practical ceiling is the sign bit at `$8000` = **~16 sections per axis** (`16 × SECTION_SIZE`). Past that, the signed despawn/load comparisons wrap and produce false despawn / missed load *before* any visual glitch — so the rebase trigger fires on the camera approaching `$8000`, not on a render symptom. (Unsigned-hardening the coordinate ops first would raise the ceiling to ~32 sections; floating-origin is what makes it effectively unbounded.)

**The model — floating-point for world space.** Split the absolute position into a coarse base + a fine live coordinate, and renormalize periodically so the fine part never overflows:
```
absolute position = World_Section_Base × SECTION_SIZE  +  Camera_X (live 16-bit)
```
The whole engine keeps running in the fine coordinate exactly as today. `World_Section_Base` (a new RAM counter, the one piece of state this adds) records how many sections we have renormalized past.

**The rebase (atomic, one frame, rendering quiesced).** Trigger when `Camera_X` crosses a threshold below the ceiling (e.g. `REBASE_THRESHOLD = $6000`). Choose `REBASE_DELTA` as a whole number of sections (e.g. `8 × SECTION_SIZE = $4000`; a multiple of `SECTION_SIZE` is automatically a multiple of the 512px plane width, so the wrapped nametable lines up and **no plane redraw** is needed). Then, in one step, subtract `REBASE_DELTA` from every piece of **live world-space state** (the audit's shift-list) and add `REBASE_DELTA / SECTION_SIZE` to `World_Section_Base`:
- `Camera_X`, `Player_1.x_pos`
- every active object `x_pos` (walk Object_RAM / Dynamic_Slots)
- every active ring `engine_X` (walk Ring_Buffer)
- the tile-cache world cursors (`Cache_Left_Col`/`Cache_Head_Col`/streaming cursors), shifted by `REBASE_DELTA/8` tiles (keep the cache even-row/circular invariants — `REBASE_DELTA` is a multiple of the section size, so parity is preserved)
- the entity-window origins/scan-state: easiest to **re-run `BuildEntries`** after shifting the camera so they recompute from the shifted camera rather than being bumped by hand.

It is invisible because everything moves by the same delta in one frame — every relative relationship (camera↔player↔entities↔plane) is unchanged; the screen is pixel-for-pixel identical. It is a pure coordinate renumber, not a content transition, so there is **no preview zone and no per-section object/ring preload-or-handoff** (those leapfrog mechanisms stay deleted — continuous streaming + the entity window already cover "see ahead" and "spawn ahead").

**What it does NOT touch (verified by the section-local entity audit, 2026-06-22).** The static per-section `sec_objects`/`sec_rings` ROM data is section-local (positions relative to the section, `0..SECTION_SIZE-1`, build-enforced) — never shifted, never overflows at any level size. Respawn/collected/killed memory is keyed by absolute `section_id` (`sec_y*grid_w + sec_x`) + list-index — coordinate-invariant, so it survives a rebase untouched. The **only** data-lookup change is adding `World_Section_Base` where a (local) coordinate is mapped to an absolute section for ROM lookup: `absolute_section = World_Section_Base + (Camera_X >> SECTION_SIZE_SHIFT)`.

**vs. the leapfrog.** Same good idea (keep the working coordinate bounded), done coarsely (every ~8 sections, not every boundary), uniformly (one shift of the live set, no slots, no per-section art swap), and invisibly (atomic, plane-aligned — no seam). Bookkeeping is one counter + `+World_Section_Base` at the section-lookup sites, vs. the leapfrog's slot map + thresholds + edge flags + preview zone.

**Companion limit to lift at the same time.** `section_id` is currently one byte (`sec_y*grid_w+sec_x`) → max 256 sections total (independent of the coordinate ceiling, and above today's `MAX_ACT_SECTIONS=48`). Widen `section_id` to a word when a level approaches 256 sections; if section_ids are ever allowed to repeat across rebase epochs, fold an epoch into the respawn key.

**Cost:** one RAM counter, a per-frame threshold compare, a rare entity-walk (tens of entities, a few hundred cycles, once per ~8 sections of travel), and `+World_Section_Base` at the handful of section-lookup sites.

---

## 10. Phase 2 — vertical continuous scroll + edge modes

**Status:** user-approved 2026-06-22; the next phase after the Phase-1 horizontal merge.

### Render-safety: resolved (no structural rework)
Research (2026-06-22) root-caused the "garbage beyond plane row 47" guard as a **stale comment**, not a hardware/layout constraint:
- Plane A is **already 64×64** (`boot.asm` reg `$10=$11`; `PLANE_V_CELLS=64`) — all 64 rows valid.
- **No VRAM overlap:** the SAT was relocated `$D800→$B800` *"specifically to free plane rows 48-63"* (`constants.asm:53`); `constants.asm:327` — *"Region 2 removed — full 64-row plane uses all nametable rows."* SAT/HScroll sit below `$C000`; Plane A `$C000-$DFFF` owns all 64 rows.
- The render path **already wraps `world_row & 63`** (`section.asm`, `plane_buffer.asm`) — identical to the verified horizontal `world_col & 63`.

The garbage on lifting `cam_max_y` "as-is" is **cache under-fill**: the world-row-based vertical fill (already unbounded by section count) has simply never been *driven* below ~2 sections, so unstreamed rows hold boot/sprite leftovers. Lifting the clamp lets it stream those rows on demand, exactly like horizontal.

### The change (unlock + verify)
Phase 1 already did the hard parts (continuous `Camera_Y`, world-row cache fill with up/down eviction + cross-frame resume, ring-wrap plane writes, world-derived entity window, `Player_LevelBound` already computing `grid_h*SECTION_SIZE − SCREEN_HEIGHT`). Phase 2:
1. **Lift the Y clamp, grid-derived** (symmetric with the X clamp): the camera Y clamp computes `[0, grid_h*SECTION_SIZE − SCREEN_HEIGHT]` from `grid_h` at runtime, and the descriptor's `cam_min_y`/`cam_max_y` fields are **deleted** (fully symmetric — no act-supplied camera bounds). Default behavior at the bottom = clamp.
2. **Remove the stale render-safety comment** (`parallax.asm:488-492`) and sync the `ENGINE_ARCHITECTURE.md` VRAM diagram (rows 48-63 are normal nametable rows; SAT at `$B800`).
3. **Verify** on-device (the real work): full-height + diagonal + sustained-down scroll renders clean (VRAM dump of rows 48-63 = valid data, not zeros); the **zero-slack streaming contract holds** (`CAM_MAX_Y_STEP=16 ≤ VFILL_ROWS_PER_FRAME×8=16`) under diagonal motion where H column-fill and V row-fill share `BLOCK_DECOMP_BUDGET=6` — watch `Lag_Frame_Count` (the profiler hides bursts); bottom-boundary prefetch honors `SEC_VOID`; collision-cell parity (`Cache_Top_Row` even) holds across boundary crossings.

### Vertical edge modes (per-act `edge_mode`, extensible to per-section)
The vertical edge behavior is configurable, not a fixed clamp:
- **`EDGE_CLAMP`** (default) — camera + player stop at `grid_h*SECTION_SIZE − SCREEN_HEIGHT`. OJZ Act 1 ships this (so verification is the clean full-height scroll).
- **`EDGE_WRAP_V`** (the fall-forever trick) — crossing the bottom wraps `Y` by `level_height` (preserving X); the top wraps to the bottom. `level_height = grid_h*SECTION_SIZE` is an exact multiple of the 512px plane height, so the wrap is **plane-aligned** (visible cells identical across the wrap → no redraw, seamless). **Deferred hook** (no level needs it yet; OJZ ships CLAMP) — the `edge_mode` dispatch is in place and stubbed to clamp; the `.edge_wrap` comment in `player_common.asm` records the design. **Implementation note (from the 2026-06-23 Phase-2 audit — the plan's "shift the live set from `Player_LevelBound`" alone is NOT sufficient):**
  - The wrap is an atomic one-frame "shift the live set" — the same machinery as the floating-origin rebase (§9), applied modulo at the level edge: shift `Camera_Y` + `Player_1.y_pos` + every active object `y_pos` (walk `Dynamic_Slots`/`System_Slots`/`Effect_Slots`, stride `SST_len`, skip `code_addr==0`) + every active ring `engine_Y` (walk `Ring_Buffer`, stride 6, +2 offset, count `Ring_Count`) + the cache world-row cursors (`Cache_Top_Row`/`Cache_Bottom_Row`/`Cache_Prev_Cam_Row`/`Cache_Fill_RowResume_Row`) by `±level_height/8` tile rows (even, so the `Cache_Top_Row`/`Cache_Origin_Row` even-parity invariant holds), then call `EntityWindow_BuildEntries` to re-derive the window.
  - **The camera Y clamp (`camera.asm` `.clamp_y`) must become edge-mode-aware** — otherwise it re-clamps the shifted `Camera_Y` (a `−level_height` shift → ~`−224` → clamp to 0 → ~240px visible jump). Frame order is `Player_LevelBound` → `Camera_Update`, so the clamp runs *after* a player-side shift.
  - **Trigger on `Camera_Y >= level_height`, NOT the player.** A player-triggered wrap drives `Camera_Y` negative, and the signed section derive (`sec_y = Camera_Y asr 11`) then yields `−1` (void) → wrong/blank content. Triggering when the (unclamped, in WRAP_V) camera reaches `level_height` keeps every world coord `≥ 0`, so the section lookup needs no `mod`. (Entities just above the camera at the wrap instant can go slightly negative and want either a small mod-safe window or are accepted as a documented edge limit.) `sec_y = (Y mod level_height) >> SECTION_SIZE_SHIFT` is the fallback if a player-trigger is ever required.
- **`EDGE_KILL`** (death pit) — bottom kills the player. **Deferred stub** (no death system yet): the `edge_mode` dispatch + a death-pending hook are in place now (falls through to clamp meanwhile), wired to the real death system when it exists. Architected from the start, not faked.

Phase 2 implements `EDGE_CLAMP` (the production path); `EDGE_WRAP_V` and `EDGE_KILL` are deferred hooks (enum + dispatch in place, stubbed to clamp, full design captured for when a level needs them).

### Deferred (tracked — revisit after the Phase 2 stress test)
`CAM_MAX_Y_STEP` is currently 16 px/frame (zero-slack against the 2-rows/frame fill). S3K allows ~24. After the on-device stress test shows the diagonal VBlank-budget headroom, revisit raising `CAM_MAX_Y_STEP` + `VFILL_ROWS_PER_FRAME` together (e.g. 24/3) for a snappier vertical camera. **Do not forget this step.**
