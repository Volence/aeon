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
2. **Phase 2 — Vertical continuous.** Extend to Y. **Resolve the vertical render-safety concern first:** the camera has never reached the bottom row (`cam_max_y` clamped to 2 sections) and `parallax.asm` notes the Y clamp doubles as a guard against "visible garbage beyond plane row 47." Phase 2 investigates + fixes the plane vertical-fill/SAT-adjacency so full-height scroll renders cleanly, then migrates the Y clamp + vertical entity/streaming. Verify the camera reaches the bottom row cleanly.
3. **Phase 3 — Cleanup.** Inline-and-delete the conversion pass-throughs; remove any remaining dead state; rewrite `ENGINE_ARCHITECTURE.md` to describe continuous-scroll as the traversal model.

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
