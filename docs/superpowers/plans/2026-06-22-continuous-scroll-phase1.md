# Continuous-Scroll Traversal — Phase 1 (Horizontal) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 2-slot leapfrog with a continuous world camera and free horizontal scrolling — the OJZ level scrolls seamlessly through all sections with no teleport seam.

**Architecture:** Camera + player positions become continuous *world* coordinates. Because all world-coordinate mapping funnels through `Engine_To_World_Col/Row`, storing world coords collapses that mapping to identity — so the ~14 collision/tile-cache/streaming callers are untouched; the conversion fns become `rts` pass-throughs, the handful of live clamps/inline-derivations are migrated by hand, the per-frame teleport trigger stops firing, and the dead leapfrog subsystem is deleted. The 64×64 VDP plane wraps in hardware. Y stays on a conservative clamp this phase (full vertical = Phase 2).

**Tech Stack:** AS Macro Assembler (68000), `build.sh` (`SOUND_DRIVER_ENABLED=1 DEBUG=1`), oracle emulator (MCP) for runtime verification.

**Branch:** continue on `feat/act-art-streaming` (this builds on the resident art pool; art-pool + continuous-scroll merge together as the "free-flowing OJZ" deliverable). The spec is already committed there (`08830b0`).

**Out of Phase 1 scope:** full vertical continuous scroll (Phase 2 — resolves the render-safety/SAT concern), and the `Engine_To_World` inline-and-delete cleanup + `ENGINE_ARCHITECTURE.md` rewrite (Phase 3).

**Execution note — coordinated flip:** Tasks 1–8 are one coordinate-space flip. Each **assembles clean** (`./build.sh -pe`), but the level renders *correctly* only after Task 8 (the teleport trigger stops). Runtime correctness is verified at the **Task 9 gate**, not per-task. The deletions (Task 10) come last; their clean assembly *proves* every live reader was migrated. Reviewers: review Tasks 1–8 by **diff** against the before/after below, not by a correct render.

---

## File structure (Phase 1 touches)
- `engine/level/tile_cache.asm` — `Engine_To_World_Col/Row` → pass-through; `Tile_Cache_Init` seeds (already underflow-clamped).
- `engine/level/camera.asm` — `Camera_Init` world coords; `Camera_Update` X world-clamp + Y conservative clamp.
- `engine/player/player_common.asm` — `Player_LevelBound` world bounds.
- `engine/level/section.asm` — `Section_UpdateColumns` clamps migrated; `Section_RedrawPlanes`/`Section_FillInitial` world; **delete** teleports/Check/EdgeFlags/EngineToWorld/WorldToEngine/SlotFlatID/GetSlotDef + `Section_Init` slot-init.
- `engine/objects/entity_window.asm` — window derivation world-based.
- `engine/level/parallax.asm` — per-section snap on boundary crossing.
- `test/ojz_scroll_test.asm` — player spawn world coords; the per-frame `Section_Check` call removed.
- `constants.asm`, `ram.asm`, `data/levels/ojz/act1/act_descriptor.asm` — delete leapfrog constants/RAM; slim cam-bound fields.

---

## Task 1: `Engine_To_World_Col/Row` → pass-through

**Files:** Modify `engine/level/tile_cache.asm:11-31`

- [ ] **Step 1: Rewrite both functions to identity.** Replace the bodies:
```
Engine_To_World_Col:
        subi.w  #SLOT_ORIGIN_L/8, d0
        moveq   #0, d1
        move.b  (Slot_Section_Map).w, d1
        lsl.w   #8, d1
        add.w   d1, d0
        rts
```
with:
```
Engine_To_World_Col:
        rts                                 ; world == engine (continuous-scroll); pass-through
```
and the same for `Engine_To_World_Row` (drop the `SLOT_ORIGIN_U`/`Slot_Section_Map+1` body → bare `rts`). Keep the labels (the ~14 callers stay byte-identical; inline-delete is Phase 3).

- [ ] **Step 2: Assemble.** Run `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh -pe 2>&1 | tail -5`. Expected: assembles clean (still references `SLOT_ORIGIN_L` etc. elsewhere — they exist until Task 10). (Runtime is wrong until Task 8 — expected.)

- [ ] **Step 3: Commit.**
```bash
git add engine/level/tile_cache.asm
git commit -m "feat(traversal): Engine_To_World_Col/Row become identity pass-throughs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Camera → world coordinates

**Files:** Modify `engine/level/camera.asm` (`Camera_Init` 17-32; `Camera_Update` X clamp 114-161; Y clamp 232-262)

- [ ] **Step 1: `Camera_Init` X/Y store world coords.** Replace (17-25):
```
        move.w  Act_start_local_x(a0), d0
        addi.w  #SLOT_ORIGIN_L, d0
        subi.w  #CAM_SCREEN_HALF_W, d0
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_X).w
```
with (compute the section base from the descriptor; drop the `SLOT_ORIGIN_L` bias):
```
        moveq   #0, d0
        move.b  Act_start_sec_x(a0), d0           ; start section X
        lsl.w   #SECTION_SIZE_SHIFT, d0            ; × SECTION_SIZE = section world origin (px)
        add.w   Act_start_local_x(a0), d0          ; + local offset within section
        subi.w  #CAM_SCREEN_HALF_W, d0             ; camera left edge = centre − half-screen
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_X).w
```
Do the analogous rewrite for Y (27-32): `Act_start_sec_y × SECTION_SIZE + Act_start_local_y − CAM_SCREEN_HALF_H`.

- [ ] **Step 2: `Camera_Update` X clamp → world bounds.** Replace the `.no_move`/preview block (114-161) so the `Section_Edge_Flags`/`PREVIEW_PIXELS` branches are gone and the clamp is `[0, level_width − SCREEN_WIDTH]` with `level_width = grid_w × SECTION_SIZE`:
```
.no_move:
        movea.l (Current_Act_Ptr).w, a0
        move.l  (Camera_X).w, d0
        swap    d0                                 ; d0.w = camera X (world px)
        tst.w   d0
        bge.s   .min_ok
        moveq   #0, d0                             ; clamp left to world origin
.min_ok:
        move.w  Act_grid_w(a0), d1                 ; grid width in sections (word)
        lsl.w   #SECTION_SIZE_SHIFT, d1            ; level_width px
        subi.w  #SCREEN_WIDTH, d1                  ; rightmost camera-left edge
        cmp.w   d1, d0
        ble.s   .clamp_x
        move.w  d1, d0
.clamp_x:
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_X).w
```
(Confirm `Act_grid_w` is the word field; the existing code reads `Act_grid_w+1` as the low byte in places — use the full word here. If `SECTION_SIZE_SHIFT` × grid overflows a word for very large future grids it does not for OJZ; note for Phase-2.)

- [ ] **Step 3: `Camera_Update` Y clamp → conservative, no slot map.** Replace the Y clamp (232-262) `Slot_Section_Map+1` tests with a `sec_y` derived from the camera, keeping the **existing conservative bounds** (`Act_cam_min_y`/`Act_cam_max_y`) for Phase 1:
```
.clamp_y:
        movea.l (Current_Act_Ptr).w, a0
        move.l  (Camera_Y).w, d0
        swap    d0                                 ; d0.w = camera Y (world px)
        move.w  d0, d2
        lsr.w   #SECTION_SIZE_SHIFT, d2            ; d2 = current section row
        tst.w   d2
        bne.s   .check_max_y                       ; sec_y > 0 → not top row
        move.w  Act_cam_min_y(a0), d1
        cmp.w   d1, d0
        bge.s   .check_max_y
        move.w  d1, d0
        bra.s   .write_y
.check_max_y:
        addq.w  #1, d2
        cmp.w   Act_grid_h(a0), d2                 ; (full word grid_h)
        bcs.s   .y_done                            ; section below → no max clamp
        move.w  Act_cam_max_y(a0), d1
        cmp.w   d1, d0
        ble.s   .y_done
        move.w  d1, d0
.write_y:
        swap    d0
        clr.w   d0
        move.l  d0, (Camera_Y).w
.y_done:
        rts
```
Leave the deadzone follow (71-112) and spindash-freeze (48-70) UNCHANGED.

- [ ] **Step 4: Assemble.** `./build.sh -pe` → clean.
- [ ] **Step 5: Commit.** `git add engine/level/camera.asm` → `git commit -m "feat(traversal): camera stores world coords, clamps to level bounds (X) + conservative Y"` (+ trailer).

---

## Task 3: Player spawn → world coordinates

**Files:** Modify `test/ojz_scroll_test.asm` (the Player_1 spawn, ~55-67)

- [ ] **Step 1: Spawn in world coords.** The spawn currently sets `Player_1.x_pos = Camera_X + CAM_SCREEN_HALF_W` (reading the camera). Since Task 2 made `Camera_X` world-space, this *already* yields world coords with no change IF it derives from `Camera_X`. Verify the spawn reads `Camera_X`/`Camera_Y` (not `SLOT_ORIGIN`); if it adds any `SLOT_ORIGIN` bias, drop it. (Read the actual lines; if it's already `Camera_X + CAM_SCREEN_HALF_W`, this task is a no-op confirmation + a comment update.)
- [ ] **Step 2: Assemble.** `./build.sh -pe` → clean.
- [ ] **Step 3: Commit** (only if changed): `git add test/ojz_scroll_test.asm` → `git commit -m "feat(traversal): player spawns in world coords"` (+ trailer).

---

## Task 4: `Player_LevelBound` → world bounds

**Files:** Modify `engine/player/player_common.asm:646-688`

- [ ] **Step 1: Left bound → world.** Replace (646-652) the `SEF_BWD_BLOCKED`/`Act_cam_min_x` left bound with a world clamp to `PBOUND_LEFT_MARGIN` (world origin 0):
```
        ; --- left bound: world [0, level_width) ---
        move.w  #PBOUND_LEFT_MARGIN, d1
        cmp.w   d1, d0
        blt.s   .clamp_x
```
- [ ] **Step 2: Right bound → world.** Replace (654-665) the `SEF_FWD_VOID`/`SEF_FWD_BLOCKED` literals with `(grid_w × SECTION_SIZE) − PBOUND_RIGHT_MARGIN`:
```
        ; --- right bound: world level_width − margin ---
        move.w  Act_grid_w(a1), d1
        lsl.w   #SECTION_SIZE_SHIFT, d1            ; level_width px
        subi.w  #PBOUND_RIGHT_MARGIN, d1
        cmp.w   d1, d0
        ble.s   .x_done
.clamp_x:
        move.w  d1, SST_x_pos(a0)
.x_done:
```
- [ ] **Step 3: Bottom bound → world (conservative).** Replace (673-675) `Act_cam_max_y` with `(grid_h × SECTION_SIZE) − SCREEN_HEIGHT` (Phase 1 keeps the conservative bottom; full vertical is Phase 2). (Confirm `a1 = Current_Act_Ptr` in this routine; if it reads the act ptr differently, adapt.)
- [ ] **Step 4: Assemble.** `./build.sh -pe` → clean.
- [ ] **Step 5: Commit.** `git add engine/player/player_common.asm` → `git commit -m "feat(traversal): Player_LevelBound clamps to world level bounds"` (+ trailer).

---

## Task 5: `Section_UpdateColumns` clamps → world

**Files:** Modify `engine/level/section.asm` (6 regions: 956-963, 977-984, 1017-1026, 1040-1046, 1091-1098, 1138-1144)

- [ ] **Step 1: Right fill-window clamp (956-963)** → `Camera_X>>3 + 63`:
```
        move.l  (Camera_X).w, d0
        swap    d0
        lsr.w   #3, d0                             ; camera tile col (world)
        addi.w  #63, d0                            ; max right = visible_left + 63 VDP cells
```
- [ ] **Step 2: Right inline conversion (977-984)** → `world_col & 63`:
```
        move.w  d5, d0
        andi.w  #63, d0                            ; nametable col = world_col & 63
```
- [ ] **Step 3: Left fill-window clamp (1017-1026)** → `(Camera_X+327)>>3 − 63`:
```
        move.l  (Camera_X).w, d0
        swap    d0
        addi.w  #327, d0                           ; visible_right_px = Camera_X + screen−1
        lsr.w   #3, d0
        subi.w  #63, d0                            ; min left = visible_right − 63 VDP cells
```
- [ ] **Step 4: Left inline conversion (1040-1046)** → `move.w d5,d0` / `andi.w #63,d0`.
- [ ] **Step 5: Bottom row conversion (1091-1098)** → `move.w d5,d0` / `andi.w #63,d0` (`world_row & 63`).
- [ ] **Step 6: Top row conversion (1138-1144)** → `move.w d5,d0` / `andi.w #63,d0`.
- [ ] **Step 7: Assemble.** `./build.sh -pe` → clean.
- [ ] **Step 8: Commit.** `git add engine/level/section.asm` → `git commit -m "feat(traversal): Section_UpdateColumns fill clamps + nametable cols from world camera"` (+ trailer).

---

## Task 6: `Section_RedrawPlanes` + init seeds → world

**Files:** Modify `engine/level/section.asm` (`Section_RedrawPlanes` Slot_Section_Map reads ~721/754; `Section_FillInitial` 66-84), `engine/level/tile_cache.asm` (`Tile_Cache_Init` 386-420)

- [ ] **Step 1: `Section_RedrawPlanes` world derivation.** It re-derives nametable cols/rows via `Engine_To_World` + `Slot_Section_Map` for the init full-plane fill. With `Engine_To_World` now identity (Task 1), migrate its inline `Slot_Section_Map` reads (721/754) the same way as Task 5 (nametable cell = `world & 63`; visible bounds from `Camera_X/Y>>3`). Read the actual routine and apply the identical pattern.
- [ ] **Step 2: `Section_FillInitial` (66-84).** The `bsr.w Engine_To_World_Col/Row` calls are now identity — they can stay (no-op) for a minimal diff. Confirm the `Section_*_Col/Row_Written` trackers are seeded from `Camera_X/Y>>3` (world). No functional change needed beyond Task 1's no-op; verify by reading.
- [ ] **Step 3: `Tile_Cache_Init` (386-420).** The `bsr.w Engine_To_World_*` calls are now identity. The world-origin underflow clamps (`bpl.s / moveq #0`) **already exist** — confirm they remain so `Cache_Left_Col`/`Top_Row` clamp to 0 when the camera reaches world origin. No change beyond Task 1's no-op; verify.
- [ ] **Step 4: Assemble.** `./build.sh -pe` → clean.
- [ ] **Step 5: Commit.** `git add engine/level/section.asm engine/level/tile_cache.asm` → `git commit -m "feat(traversal): Section_RedrawPlanes + init seeds on world camera"` (+ trailer).

---

## Task 7: Entity window → world-derived

**Files:** Modify `engine/objects/entity_window.asm` (`EntityWindow_DeriveWindow` 566-578; `EntityWindow_BuildEntries` origin 600-608; `EntityWindow_Init` slot path 1595/1597)

- [ ] **Step 1: `DeriveWindow` from camera.** Replace the `Slot_Section_Map` reads (574/576) + `SLOT_ORIGIN` bias: derive `sec_x0 = (Camera_X − ENTITY_DESPAWN_BUFFER) >> SECTION_SIZE_SHIFT` (signed `asr` floor), `sec_y0` from `Camera_Y` likewise. Keep the 2×2 envelope + the floor logic identical.
- [ ] **Step 2: `BuildEntries` origins.** Replace the origin bases (600-608) `SLOT_ORIGIN + col0*SECTION_SIZE` with `origin_x = sec_x0 × SECTION_SIZE` (drop the `SLOT_ORIGIN` add). Leave the per-quadrant `+SECTION_SIZE` and the `Section_GetSecPtrXY` unsigned out-of-grid void check unchanged.
- [ ] **Step 3: `EntityWindow_Init` slot path (1595/1597).** Migrate its `Slot_Section_Map` reads to the same camera-world derivation as Step 1.
- [ ] **Step 4: Assemble.** `./build.sh -pe` → clean.
- [ ] **Step 5: Commit.** `git add engine/objects/entity_window.asm` → `git commit -m "feat(traversal): entity window derived from world camera, no slot map"` (+ trailer).

---

## Task 8: Stop the teleport trigger — activate continuous scroll

**Files:** Modify `test/ojz_scroll_test.asm` (remove the per-frame `jsr Section_Check`)

- [ ] **Step 1: Remove the `Section_Check` call.** Find the per-frame `jsr Section_Check` in the OJZ update loop and delete it. With no teleport trigger, the camera/player run continuously in world space (this is the moment continuous scroll goes live). (Leave `Section_Init` / `Section_FillInitial` / `Section_UpdateColumns` calls — only the teleport-trigger `Section_Check` goes.)
- [ ] **Step 2: Build the ROM.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -4` → `Build complete: s4.bin`, exit 0.
- [ ] **Step 3: Commit.** `git add test/ojz_scroll_test.asm` → `git commit -m "feat(traversal): drop per-frame teleport trigger — continuous scroll live"` (+ trailer).

---

## Task 9: GATE — verify horizontal continuous scroll (oracle)

**Files:** none (verification). This is the correctness gate for the Task 1–8 flip.

- [ ] **Step 1: Reload + boot.** oracle `emulator_reload_rom` (`/home/volence/sonic_hacks/s4_engine/s4.bin`) + `emulator_screenshot` → OJZ art renders at the start, no garbage.
- [ ] **Step 2: Drive horizontal scroll across the old sec1/sec2 seam.** Build with `SOUND_LOADTEST=1` (or drive `Player_1.x_pos` forward via `write_memory`); read `Camera_X` across frames — it must advance **continuously** (no rebase/jump) past 2048, 4096, to near `level_width` (6144). Screenshot mid-traverse: **no seam, no warp, brown→green transition is smooth**, the previous section's tail stays visible on the left (the original bug is gone because there is no teleport).
- [ ] **Step 3: Collision probe.** At a known section-2 ground position, confirm the player lands/collides correctly (read `Player_1` y on ground) — proves world-coord collision lookup is correct.
- [ ] **Step 4: VRAM no-tear check.** `emulator_read_vram` of Plane A nametable while scrolling across a boundary — no torn/duplicated columns (the fill-window clamp bounds ≤64 distinct cols).
- [ ] **Step 5:** If any check fails, STOP and debug (systematic-debugging) before Task 10 — do not delete the leapfrog while the flip is unverified.

---

## Task 10: Delete the leapfrog (clean teardown)

**Files:** `engine/level/section.asm`, `ram.asm`, `constants.asm`, `data/levels/ojz/act1/act_descriptor.asm`

- [ ] **Step 1: Delete dead `section.asm` routines.** Remove: `Section_GetSlotDef` (93-98), `Section_SlotFlatID` (108-124), `Section_UpdateEdgeFlags` (219-239), `Section_Check` (248-396), `Section_TeleportFwd` (403-494), `Section_TeleportBwd` (501-571), `Section_TeleportDown` (580-628), `Section_TeleportUp` (637-688), `Section_EngineToWorld` (1174-1184), `Section_WorldToEngine` (1194-1197), and the slot-init block in `Section_Init` (17-38: `Slot_Origins` + `Slot_Section_Map` setup). Keep `Section_Init` (minus slot-init), `Section_FillInitial`, `Section_UpdateColumns`, `Section_RedrawPlanes`, `Section_GetSecPtrXY`, `Section_FlatIDXY`. Fix any remaining callers of `Section_SlotFlatID` → `Section_FlatIDXY` (grep first).
- [ ] **Step 2: Delete dead RAM** (`ram.asm`): `Slot_Origins` (346), `Slot_Section_Map` (348), `Section_Preload_Flags` (351), `Section_Teleport_Guard` (352), `Section_Edge_Flags` (354), `Entity_Window_Anchor` (401), `Entity_Window_OriginX` (402), `Entity_Window_OriginY` (403).
- [ ] **Step 3: Delete dead constants** (`constants.asm`): `SECTION_SHIFT` (312), `SLOT_ORIGIN_L/R/U/D` (313-316), `SEF_*` (328-331), `PREVIEW_COLS/ROWS/PIXELS` (339-341), `SECTION_*_THRESHOLD`/`*_PRELOAD`/`DEFERRED_*_LOAD` (343-357), `SPF_*` (383-390). Keep `SECTION_SIZE`, `SECTION_SIZE_SHIFT`, `SECTION_TILE_WIDTH/HEIGHT`, `PLANE_*`, `TILE_CACHE_*`.
- [ ] **Step 4: Slim the act descriptor.** In `act_descriptor.asm`, the engine-space `cam_min/max_x` fields are now unused (camera clamps live-compute from grid). Remove them (and the struct fields) OR leave `cam_min/max_y` if still read by the conservative Y clamp (Task 2 Step 3 reads `Act_cam_min_y`/`Act_cam_max_y`) — keep only what Task 2/4 still read; delete the X ones.
- [ ] **Step 5: Build — clean assembly PROVES no live reader remains.** `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh 2>&1 | tail -4` → `Build complete`, exit 0. An "undefined symbol" here = a missed reader (grep it, migrate it, rebuild). Then `grep -rn "Slot_Section_Map\|SLOT_ORIGIN\|Section_Teleport\|SECTION_SHIFT\|Section_Check\|Section_Edge_Flags" engine constants.asm ram.asm` → no matches (except `__DEBUG__` self-check if still present — neutralize).
- [ ] **Step 6: Reload + screenshot** (oracle) → still renders + scrolls (deletion changed nothing live). Commit:
```bash
git add engine/level/section.asm ram.asm constants.asm data/levels/ojz/act1/act_descriptor.asm
git commit -m "refactor(traversal): delete the leapfrog (teleports, slot map, thresholds, preview-zone)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: Per-section parallax snap on boundary crossing

**Files:** Modify `engine/level/parallax.asm`

- [ ] **Step 1: Detect section-boundary crossing.** The old snap fired on teleport. Add a per-frame check: track the previous `(Camera_X >> SECTION_SIZE_SHIFT)` (and Y) in a RAM byte; when it changes, the camera crossed a section boundary — look up the new section's `sec_parallax_config` via `Section_GetSecPtrXY` and trigger the parallax snap (set `Parallax_Snap_Pending`) instead of lerp. Read the current `Parallax_Update` / `Parallax_Snap_Pending` usage and wire the trigger there. (If sections currently all share the act-default parallax config, this is a no-op visually now but preserves the per-section feature for when configs differ — keep it.)
- [ ] **Step 2: Build.** `./build.sh` → exit 0.
- [ ] **Step 3: Commit.** `git add engine/level/parallax.asm ram.asm` → `git commit -m "feat(traversal): per-section parallax snaps on section-boundary crossing"` (+ trailer).

---

## Task 12: Final verification + Phase-1 close (oracle)

**Files:** none (verification).

- [ ] **Step 1: Streaming budget under continuous scroll.** Drive max horizontal scroll across the full level; enable the profiler; watch `Lag_Frame_Count` (the profiler misses bursts) — confirm no lag/pop-in at the old section seams where a fresh block decompresses every frame.
- [ ] **Step 2: World-origin + edges.** Scroll to `Camera_X = 0` (left wall) and to the right wall; screenshot — no negative-coordinate garbage, clean clamp at both ends.
- [ ] **Step 3: Parallax.** Confirm parallax scrolls smoothly across boundaries (and snaps if a section has a distinct config).
- [ ] **Step 4: Confirm the seam bug is gone** — the original report (warp / missing brown preview at sec1→sec2) no longer reproduces: the transition is a continuous scroll.
- [ ] **Step 5: Commit verification note + (Phase 2/3 deferred).**
```bash
git commit --allow-empty -m "docs(traversal): Phase 1 verified — free-flowing horizontal continuous scroll, leapfrog removed"
```

---

## Self-review

- **Spec coverage:** §2 model (world coords, identity collapse, plane wrap)→Tasks 1-2,5; §3 four-system design→Tasks 2 (camera), 5-6 (tile-cache/plane), 7 (entity), 4 (Player_LevelBound), Task 8 (section-lookup via stopping the trigger); §4 parallax→Task 11; §5 removal scope→Task 10; §6 Phase 1→all; §7 verification→Tasks 9,12. Vertical (Phase 2) + inline-delete/arch-doc (Phase 3) correctly deferred. ✓
- **Placeholders:** every migration step has the real before/after from the source; ASM tasks give the exact code + assemble/Exodus verification (the engine's verification model). Tasks 3/6 are "confirm/verify" where Task 1's no-op already does the work — flagged as such, not hidden TODOs. ✓
- **Consistency:** `SECTION_SIZE_SHIFT` used for all world↔section shifts; `Act_grid_w/h` (full word) used consistently for level bounds; `Engine_To_World` no-op established in Task 1 and relied on in Tasks 5/6; the "flip then gate then delete" ordering is consistent (deletions Task 10 after the Task 9 gate). ✓
- **Risk:** Task 2's `Act_grid_w` word-vs-low-byte usage and Task 4's act-ptr register (`a1`) must be confirmed against the real code during implementation (flagged inline).
