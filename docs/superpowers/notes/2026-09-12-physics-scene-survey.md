# Physics-scene survey: can the boot scene reach the still-owed runtime checks? (2026-09-12)

Read-only worktree survey for the aeon controller. No emulator was run; everything below is from
source, the build listings and one ROM read. Anything that needs a running machine is tagged
**RUNTIME-TAG**.

- **Tree:** `9fe9ee91fcec3d7a1c587b65f7aab938ce895208` (= `origin/master` when the survey started;
  `git rev-parse HEAD` checked at start and again before the commit, working tree clean). Every
  file:symbol below is at this SHA.
- **Listing used for names/addresses:** `/home/volence/sonic_hacks/.aeon-ls8-land/s4.debug.lst`
  (mtime 2026-09-12 11:59Z) and `s4.lst` beside it, read only. **Its tree was not determined.** It
  is NOT `c5dd8c20` as the s7 note describes: its `Draw_Sprite` already has `.offscreen` ($36B2)
  below `.no_parent` ($36BA), which is the post-fix short-entry layout. `c5dd8c20` is an ancestor of
  HEAD, and `c5dd8c20..9fe9ee91` touches code only in `engine/level/collision_lookup.emp`,
  `engine/objects/sprites.emp`, `engine/level/tile_cache.emp` (comment), `engine/system/constants.emp`
  and `games/sonic4/map.toml`. **Addresses quoted here are examples. Resolve every symbol against
  the ROM actually loaded.**

## Headline: the boot scene HAS player physics, one B press away

The brief's premise ("no player physics, so nothing collides, collects rings or kills anything")
and the same sentence in the s7 witness note and in DEFERRED_WORK's runtime-TAG status line are
**wrong about the scene**. They describe the debug-fly cheat's boot state, not the scene.

By call site, at HEAD:

1. `GameState_OJZScroll_Init` (`games/sonic4/test/ojz_scroll_test.emp`) arms the cheat in the
   DEBUG shape only: `if DEBUG == 1 { move.b #CHEAT_DEBUG_FLY, Cheat_Flags }`. It then runs
   `jbsr Player_Init` on `Player_1`, under the comment "Player_Init boots in debug-fly (yellow
   square) so the streaming-test workflow is unchanged — B drops into physics."
2. `Player_Init` (`games/sonic4/player/player_common.emp`) writes
   `move.w #Player_Main - ObjCodeBase, code_addr(a0)`, then
   `moveq #CHEAT_DEBUG_FLY,d0 / and.b Cheat_Flags,d0 / bne Player_DebugEnter`. Its comment for the
   clear case reads "normal player (PSTATE_AIR, lands frame 1)".
3. `GameState_OJZScroll_Update` calls `jbsr RunObjects` every tick (comment: "Player_Main handles
   its own movement"), then `Camera_Update`, `EntityWindow_Scan`, `Section_UpdateColumns`,
   `TouchResponse`, then `RingCollision` gated on `tst.b PlayerV.debug_flag(Player_1)`, then
   `Render_Sprites`.
4. `RunObjects` (`engine/objects/core.emp`) walks the player slots first
   (`lea Player_1, a0 / move.w #NUM_PLAYERS-1, d7`).
5. `Player_Main` reads `Ctrl_1_Press`. A B press with the cheat armed calls `Player_DebugExit` when
   `debug_flag` is set, or `Player_DebugEnter` when it is clear. While `debug_flag` is set it does
   `bne Player_DebugMove`: `PLAYER_DEBUG_FLY_SPEED` = 16 px/frame, draw only. With `debug_flag`
   clear it runs `Player_LoopCrossover`, the jump buffer, the `Player_States` dispatch
   (`jsr (a1,d1.w) as PlayerState`), `Player_LevelBound`, and falls into `Player_Display`.
6. `Player_DebugExit` does `sf debug_flag`, `Player_InitAssets`, the standing size, and
   `jbra Player_SetState` with `PSTATE_AIR`.

So the "16 px/frame free scroll" is the player being moved by `Player_DebugMove`, with
`Camera_Update` following him. It is not a camera scroll. **One B press hands `Player_1` to the
real state machine, in this scene, on this ROM.**

Four existing tools already rely on this, and their headers record it as measured. I cite them; I
did not re-run them:
- `tools/dma_straddle_exercise.py`, header: "the canonical DEBUG shape boots ALREADY IN DEBUG FLY
  … One B press (edge-triggered) hands the player to real physics". It also sets
  `JUMP_BUTTON = "a"`.
- `tools/spring_launch_witness.py`, `boot_and_settle`.
- `tools/spring_clip_ab.py`, `boot`.
- `tools/tile_cache_fill_gate.py`, which arms `Cheat_Flags` for its fly drive.

Button facts while the cheat is armed:
- **B** is the fly toggle. It is excluded from the jump mask (`BUTTON_JUMP_MASK_NO_B` in
  `Player_Main`).
- **A** and **C** jump.
- **A inside fly** is the character cycle (`Debug_CharacterHotkey`).
- **C** is the lab's anchor/flood modifier.

The release shape never arms the cheat, so there the player is in physics from frame 1.

## 1. How a game state is chosen

- **Boot** (`engine/system/boot.emp`, the tail of the boot proc) runs
  `move.l #Game.entry, (Game_State).w`, `move.b #Game.ENTRY_ID, (Game_State_ID).w`,
  `clr.b Game_State_Init`, then `jbra GameLoop`.
- **sonic4** binds `proc entry = GameState_OJZScroll_Init` and
  `const ENTRY_ID = GS_OJZ_SCROLL_TEST` (`games/sonic4/config/game.emp`, `implement Game`). **demo**
  binds `GameState_Demo_Init` / `GS_DEMO` (`games/demo/config/game.emp`). demo is a separate ROM
  (`demo.bin`); it cannot be selected inside `s4*.bin`.
- **Dispatch** is `GameLoop` (`engine/system/game_loop.emp`): `movea.l Game_State, a0 /
  jsr (a0) as GameState`, once per logic tick. Each init installs its own update proc:
  - `GameState_OJZScroll_Init` installs `GameState_OJZScroll_Update`.
  - `GameState_ObjectTest_Init` installs `GameState_ObjectTest`.
  - `GameState_ObjectTestChurn_Init` installs `GameState_ObjectTestChurn`.
- **`Game_State_ID` and `Game_State_Init` have no reader.** `git grep` over `engine/` and `games/`
  finds only their RAM declarations and the two boot stores. Selection is the `Game_State` long and
  nothing else.
- **No hotkey or build define selects another state.** Neither ObjectTest init has a call site.
  `GameState_ObjectTest_Init` appears only in `games/sonic4/map.toml`'s tail placement list, and
  `object_test_state.emp`'s own header for Churn says "Entered at runtime by writing
  GameState_ObjectTestChurn_Init to Game_State".
- **Both ObjectTest states are debug-ROM only.** `s4.lst` (release) has none of
  `GameState_ObjectTest_Init`, `ObjDef_Parent` or `TestParent`, while `GameState_OJZScroll_Update`
  is present. That was checked by name; the exclusion mechanism was not checked.

What the controller does for each state:

| state | how to enter it in the emulator |
|---|---|
| OJZ scroll test | boot (the default). For physics, press **B** once after boot, in the DEBUG shape. |
| ObjectTest | write the 32-bit address of `GameState_ObjectTest_Init` to `Game_State` (u32; `$FFFF8008` in the reference listing). It runs on the next tick. s4.debug only. |
| ObjectTestChurn | the same, with `GameState_ObjectTestChurn_Init`. s4.debug only. |
| Demo | load `demo.bin`/`demo.debug.bin`. It is a different ROM. |

**RUNTIME-TAG:** entering ObjectTest mid-run is untested here. Its init re-runs `InitObjectRAM`,
the palette, the test-art DMA and camera 0, but it does NOT tear down the OJZ level, effects,
raster or parallax state that the VBlank path keeps using. The consequences were not checked, and
nothing in this survey needs that state.

## 2. Which states run player physics (by call site)

| update proc | per-frame calls | `Player_1.code_addr` | real player physics? |
|---|---|---|---|
| `GameState_OJZScroll_Update` | the warp and objreq mailboxes (DEBUG), the lab hotkeys (DEBUG), `InitSpriteSystem`, `RunObjects`, `Camera_Update`, `Effects_LatchWorldLines`, `Tile_Cache_Fill`, `EntityWindow_Scan`, `Section_UpdateColumns`, `TouchResponse`, `RingCollision` (when `debug_flag` = 0), `Render_Sprites`, `Parallax_*`, `BgAnim_Update`, `Waterline_Art_Update` | `Player_Main` (`Player_Init`) | **YES**, whenever `PlayerV.debug_flag` = 0: after one B press in DEBUG, and always in release |
| `GameState_ObjectTest` | `InitSpriteSystem`, `RunObjects`, `TouchResponse`, `Render_Sprites` | `TestPlayer` (`games/sonic4/objects/test_player.emp`) | no. `TestPlayer_Main` is a separate test player (its own gravity/jump constants, `ObjectMove`, one `Player_SensorFloor` probe), not `Player_Main`. No camera follow, entity window, ring pass or level load |
| `GameState_ObjectTestChurn` | the same plus `EntityWindow_Scan` (window left inactive) | `TestPlayer` | no, same as above |
| `GameState_Demo` (demo ROM) | not checked | not checked | not checked |
| `GameState_Idle` | `rts` | none | no |

With physics on, `Collision_GetType` runs every frame. Its call sites are
`games/sonic4/player/player_common.emp` inside `Player_LoopCrossover`, which `Player_Main` calls
before the state dispatch, and `games/sonic4/player/player_sensors.emp` (the enclosing proc was not
checked).

## 3. Per-check table

Symbols are link names. Take their addresses from the loaded ROM's own listing. Struct offsets are
from `engine/objects/sst.emp` (`Sst`, `$50` bytes).

| check | reachable in the scroll test? | needs physics? | recipe, or blocker |
|---|---|---|---|
| **C4a-3** DespawnRings at a FULL ring buffer | **Only by RAM seed; no state can fill it from content** | no | See 3a. OJZ act 1 has 60 rings in total and at most 41 in any 2x2 window, against `MAX_RING_BUFFER` = 128. |
| **C2a-6** piece count `$FF` + wrong cached offset | yes (s4.debug) | no | See 3b. The target is `Player_1` in fly, whose cache is never refreshed while it flies. |
| **B2a-2** (optional) | **no, in every state** | no | `CreateChild_Complex` and `CreateChild_FlipAware` have zero call sites, and no mailbox can call a proc. A caller is missing (§4a). |
| **EFX-4b** longer→shorter static re-install | yes | no | See 3c. Lab raster row 21 (`OJZ_BandDemo`, 110 B) then row 22 (`OJZ_BaseSwap`, 46 B), or a section crossing 5→2 / 4→1. **Not in section 0 or 7**: those are patched. |
| **C3b-2** lag-frame residue | yes, but probabilistic | no | See 3d. Section 0 at boot already has two patchable channels with motion. It needs a `VInt_Lag` that lands between two channels' stores in `Effects_LatchWorldLines`. |
| **C4a-2** collected half | **yes** | **yes, one B press** | See 3e. Fly onto a section-0 ring, press B (it is collected that same frame), fly away and back. The cycle counts need the pre-C4a-2 ROM. |
| **Draw_Sprite** multisprite parent | yes (s4.debug only) | no | See 3f. Spawn `ObjDef_Parent` through the live-object mailbox. |
| **Draw_Sprite** null-mappings object | yes | yes for the natural path, no for the poke | See 3g. A ring sparkle's AF_DELETE frame, or a `mappings = 0` poke on a debug-spawned `ObjDef_Static`. |
| **Killed_MarkObject** | **no: unreachable by construction, CONFIRMED** | — | See 3h. It is stronger than booked: no archetype in the tree uses `COLLISION_ENEMY`. |

### 3a. C4a-3: full ring buffer (RAM seed)

The content cannot fill the buffer:
- `MAX_RING_BUFFER` is a build define. The C4a parcel note reads it as `cmpi.b #$80` in the built
  `RingBuffer_Add` (`engine/objects/rings.emp`).
- Rings per section, 0..8 (`games/sonic4/data/editor/ojz/act1/section_N.rings.json`, counted
  here): 7, 9, 12, 0, 12, 8, 0, 8, 4, which is 60 in total.
- The 2x2 window's maximum is sections 1+2+4+5 = 41.
- s7 measured `Ring_HighWater` 21.

A full buffer therefore cannot happen in OJZ act 1 in any state. The recipe:
1. Make sure `Debug_Scene_Freeze` is 0 (non-zero skips `EntityWindow_Scan` entirely).
2. Set a breakpoint at `EntityWindow_DespawnRings` entry. Its header says its one caller is
   `EntityWindow_Scan`'s tail, after the spawn walkers.
3. On the hit, write `Ring_Count` = `$80` and 128 six-byte entries at `Ring_Buffer`:
   `x.w @0`, `y.w @2`, `section_id.b @4` (`RING_ENTRY_SECTION_ID_OFFSET`), `list_index.b @5`.
4. Step to the proc's `rts` and take the cycle count, from the profiler or the step-out delta.

Seed one of two variants, read from the proc body:
- **keep-all:** `x` in `[Camera_X − ENTITY_DESPAWN_BUFFER ($200), Camera_X + 320 + $200]`, and `y`
  in `[Camera_Y − ENTITY_DESPAWN_BUFFER_Y ($180), Camera_Y + 224 + $180]`. `Ring_Count` stays 128.
- **remove-all:** `x` outside that X window, and `section_id` equal to none of the four
  `Entity_Scan_State[k].ess_section_id` bytes. `Ring_Count` ends at 0.

Hazards:
- `RingBuffer_Add` has a DEBUG-fatal assert on a full buffer (`.full`). After the keep-all variant,
  restore a checkpoint before the next frame's spawn walk runs.
- The remove path calls `EntityLoaded_Clear` for tracked section ids. Use the checkpoint for that
  variant as well.

"Before/after", as the TAG words it, needs the ROM built from the parent of merge `f64f26b3`.
That ROM was not built here. The parcel note predicts a net change of about 36 − 24N cycles for N
kept rings. **RUNTIME-TAG.**

### 3b. C2a-6: staleness net ahead of the overflow pre-check

The fix is on HEAD: `Render_Sprites` has `assert.w d1, eq, d0` and then `.stale_net_done`
(`engine/objects/sprites.emp`; merge `60e26266`, land `8c5e6d35`).

The target is `Player_1` in the boot fly state:
- `Player_DebugMove` tail-calls `Draw_Sprite` every frame.
- `Player_Main`'s hatch skips `Player_Display`, so no animate or refresh rewrites the cache.
- s7 measured its `render_flags` at `$81` (on screen).

Steps:
1. At boot plus about 400 frames, read `Player_1+$2E` (`frame_off`).
2. Write `Player_1+$25` (`sprite_piece_count`) = `$FF`.
3. Write `Player_1+$2E` = any even value different from the one read.
4. Run one frame. **Witnessed:** the MD Debugger assert screen, raised from `Render_Sprites`.

Controls, from the parcel TAG:
- Poke the piece count only (`frame_off` untouched): no assert, and the marker is skipped for that
  frame.
- "Zero mappings on a slot still in a band": break at `Render_Sprites` entry (after `Draw_Sprite`
  has registered the player), write `Player_1+$10` (`mappings`) = 0, and expect no assert.

**RUNTIME-TAG.**

### 3c. EFX-4b: longer→shorter static re-install

A static install reaches `Raster_VBlank`'s `.copy_program`, which copies a fixed `RASTER_BUF_SIZE`
into `Raster_Buf_A` (`engine/effects/raster.emp`).

Unpadded program lengths were measured from the reference ROM
(`.aeon-ls8-land/s4.debug.bin`, as the last non-zero word, which is `$FFFF` in every case, plus
two). Every 128-byte image had an all-zero tail. The effects data did not change in
`c5dd8c20..HEAD`.

| program | bytes |
|---|---|
| `OJZ_BandDemo` (lab row 21) | 110 |
| `EditorRaster_OJZ_Act1_ojz_sec5_showcase` (section 5 preset) | 110 |
| `EditorRaster_OJZ_Act1_authored_probe` (lab row 24) | 78 |
| `OJZ_TwoChannel` (section 0, **patched**) | 50 |
| `OJZ_BaseSwap` (lab row 22) · `OJZ_DepthVSplit` (section 4) · `EditorRaster_OJZ_Act1_ojz_sec6_baseswap` (section 6) · `EditorRaster_OJZ_Act1_ojz_sec3_shimmer` (lab row 25) · `OJZ_WorldWater` (section 7, **patched**) | 46 |
| `OJZ_TestRaster` (section 1) · `EditorRaster_OJZ_Act1_aurora_ramp_witness` (row 23) · `EditorRaster_OJZ_Act1_ramp_probe` (row 26) · `OJZ_WaterRaster` · `OJZ_TestRamp` | 34 |
| `OJZ_TestGradient` (section 2) · `OJZ_TestVsram` | 30 |

**Route A, the lab hotkey (DEBUG):**
1. Write `Debug_Lab_Index` = 20. (The boot value was not checked. Otherwise step to it.)
2. Hold START and press RIGHT once. This lands on row 21 (`OJZ_BandDemo`), installed by
   `Raster_Install` into `Raster_Pending`.
3. After the next VBlank, START+RIGHT again for row 22 (`OJZ_BaseSwap`).

LEFT and RIGHT still steer the fly while START is held (`Debug_LabCycleHotkey`'s header). An
equivalent that tools already use is to write `Raster_Pending` with the program's ROM address.

**Witnessed** after the second install's VBlank when all of these hold:
- `Raster_Program` is the ROM address of `OJZ_BaseSwap` (a static install stores the ROM pointer).
- `Raster_Patch_Tab` = 0.
- `Raster_Active_Buf` = `Raster_Buf_A`.
- `Raster_Buf_A[0..46)` equals the ROM image.
- `Raster_Buf_A[46..128)` is all zero.

**Route B, a natural crossing (any shape):** fly from section 5 (110 B) up into section 2 (30 B),
or from section 4 (46 B) up into section 1 (34 B). The grid is 3 wide with 2048-px sections, so
section 5 is x 4096–6143, y 2048–4095, and section 2 is the same x at y 0–2047.
`Parallax_CheckBoundary` decides the crossing from the camera centre.

**Do NOT use sections 0 or 7.** They bind PATCHED programs. `Raster_InstallPatched` plus
`Raster_BuildSchedule` re-record into whichever of Buf_A/Buf_B is not live, swap them every VBlank,
and write only up to their own emitted terminator. Words past it can legitimately be stale, so a
Buf_A read there is not this check (see §5, item 2).

**RUNTIME-TAG.**

### 3d. C3b-2: lag-frame residue

The ingredients are all present in section 0 at boot:
- `OJZ_Preset_Sec0` binds `patched: OJZ_TwoChannel`, which has two `patchable()` records
  (`games/sonic4/data/effects/ojz_effects.emp`).
- Channel 0 carries `anchor_sweep` motion, so `Effects_LatchWorldLines` takes its `.mch` loop. That
  loop does one `move.w d2, 6(a0)` per channel for `RASTER_MAX_PATCH` = 4 channels.
- `VInt_Lag` (a VBlank taken with `VBlank_Ready` = 0) calls `Raster_VBlank`
  (`engine/system/vblank.emp`), whose `Raster_BuildSchedule` reads `Effects_Screen_L`.

**A tear is a `VInt_Lag` whose interrupted PC lies inside the `.mch` loop after channel 0's store
and before channel 1's.**

Recipe:
1. Fly diagonally at full speed in section 0 to produce lag frames. `Lag_Frame_Count` (DEBUG) goes
   up once per `VInt_Lag`, and the page-audit comment in `GameState_OJZScroll_Update` notes that
   "the streaming path lags at 2 frames/tick".
2. Break on `VInt_Lag`, read the stacked return PC, and compare it against
   `$engine.effects.raster$Effects_LatchWorldLines$mch` .. `$cap_anchor_motion_latch_end`.

The hit rate was not derived. The latch loop is a small fraction of a frame, so many lag frames
may be needed.

This was not checked either: whether channel 1's record is live or `.suppress`ed (dropped past its
band) at the camera used. A visible disagreement needs both records live.

**RUNTIME-TAG.** No physics is needed.

### 3e. C4a-2: collected half

The section-0 rings, per s7, are list indices 0–6 at (128,96) (144,96) (160,96) (176,96)
(192,96) (308,157) (324,157). The boot camera is (96,144), and the fly marker is at the camera
centre, about (256,256).

1. Fly the marker onto list index 0 at world (128,96) (left 8 frames, up 10 frames, at 16 px/frame).
2. Press **B** once. Within that frame, `Player_Main` → `Player_DebugExit` clears `debug_flag`,
   the physics runs, and then the level state's `RingCollision` (its gate now open) tests
   `Player_1`'s box against the ring. `Player_DebugExit` keeps the position.
3. **Collected when** all of these hold:
   - `Ring_Count` drops by 1 (7 to 6 at the boot population).
   - `Ring_Counter` rises by 1.
   - Section 0's collected bit for list index 0 is set in `Ring_Collected_Window`.
   - The ring sparkle spawns (`Game.ring_collected` is bound to `RingSparkle_Spawn`).
4. Press **B** again (back to fly). Hold RIGHT 200 frames, then LEFT 200 frames (s7's
   spawn-half route).
5. **Witnessed when** section 0 is back in the buffer with list indices 1–6 only, index 0 is
   absent, and its collected bit is still set.

Whether 200 frames takes section 0 out of the 3x3 collected-window neighbourhood, and so exercises
the respawn park (`Collected_ClaimSlot`, §4.9.4) rather than a retained slot, was not derived.
Slide further (to sec_x 2) to be sure of the park path.

The `PopulateSectionRings`/`RescanY` "before/after" cycle counts need the ROM built from the
parent of merge `62fb300f`. That ROM was not built here.

If the landing box does not overlap the ring, lower the marker a few pixels and repeat.

**RUNTIME-TAG.**

### 3f. Draw_Sprite: multisprite parent

This goes through the live-object mailbox (`objreq_consume` in `ojz_scroll_test.emp`, spliced at
`GameState_OJZScroll_Update`'s frame top, DEBUG only):
1. Write `Obj_Req_Def` = the address of `ObjDef_Parent`. It is a DEBUG-only record in
   `games/sonic4/test/object_test_state.emp`: code `TestParent`, map `Map_TestObj`, art
   `VRAM_TEST_OBJ`. The OJZ init DMAs `TestArt` there.
2. Write `Obj_Req_X` = 160, `Obj_Req_Y` = 112, `Obj_Req_Place` = 0, `Obj_Req_Op` = 1.
3. Write `Obj_Req_Flag` = 1, **last**.
4. On the next tick expect `Obj_Req_Status` = 0 and `Obj_Req_Slot` = the handle.

What `TestParent` does (`games/sonic4/objects/test_parent.emp`):
- It sets `RF_COORDMODE` (screen coordinates) and `RF_MULTISPRITE`.
- It spawns three `TestChildPart` children through `CreateChild_Normal`.
- It lives `PARENT_LIFETIME` = 180 frames, then `DeleteObject` cascades the children.

**Witnessed** when:
- each child's `Draw_Sprite` takes the batching-parent exit (parent_ptr ≠ 0 and the parent has
  RF_MULTISPRITE, so it lands at `$engine.objects.sprites$Draw_Sprite$offscreen` and the child's
  RF_ONSCREEN stays clear), and
- `Render_Sprites` takes `$…Render_Sprites$multi_sprite` for the parent.

**Keep the camera still for the whole 180 frames.** `RunObjects`' dynamic cull compares `x_pos` and
`y_pos` against the WORLD camera (`CULL_DISTANCE_X` $300, `_Y` $200). The screen coordinates
(160,112) pass that test at the boot camera (96,144) and may fail it elsewhere.

This route does not exist in release: `ObjDef_Parent` is absent from `s4.lst`. **RUNTIME-TAG.**

### 3g. Draw_Sprite: null-mappings object

**Natural path (needs physics):**
- `RingSparkle_Main` is `jbsr AnimateSprite / jbra Draw_Sprite`
  (`games/sonic4/objects/ring_sparkle.emp`).
- Its script ends in `AF_DELETE` (`RING_SPARKLE_SCRIPT`), and `AnimateSprite`'s delete arm does
  `jbra DeleteObject` (`engine/objects/animate.emp`).
- `DeleteObject`'s header says it zeroes the SST. Its `.clear_slot` body was not read.
- `InstaShield_Main`'s header (`games/sonic4/player/player_instashield.emp`) states this path in so
  many words: "Draw_Sprite guards null mappings — the same animate-then-draw-a-dead-slot path
  dust_puff and ring_sparkle already run".

So on a sparkle's last frame, `Draw_Sprite` runs on a zeroed slot: parent_ptr 0 → `.no_parent`,
then mappings 0 → `.offscreen`.

Recipe: collect a ring (3e). Then break at `$…Draw_Sprite$no_parent` with `a0` = the sparkle's
slot, on the frame its `mappings` reads 0. **Witnessed** when the next branch goes to
`$…Draw_Sprite$offscreen`.

**Poke path (no physics):** spawn `ObjDef_Static` through the mailbox (as in 3f, with
`Obj_Req_Def` = `ObjDef_Static`). `TestStatic_Main` is a bare `jbra Draw_Sprite`. Write its
`Sst.mappings` (+$10) = 0 and watch its next `Draw_Sprite`. Prefer this over poking a spring: what
`AnimateSprite` does with null mappings on an animated object was not checked.

**RUNTIME-TAG.**

### 3h. Killed_MarkObject: unreachable, confirmed

- `git grep -w Killed_MarkObject -- engine games` finds its definition
  (`engine/objects/entity_window.emp`), comments and one ensure message. There is no call site.
- `Touch_Enemy` is part of the empty `falls_into` stub chain in `engine/objects/collision.emp`,
  which ends at `Touch_Touch`'s `rts`.
- **Stronger than the booking:** `COLLISION_ENEMY` is referenced only by its constant
  (`engine/system/constants.emp`) and the handler-table comment. **No archetype uses it.** The one
  enemy archetype, `ObjDef_Enemy` (DEBUG-only, in `object_test_state.emp`), is `COLLISION_HURT`,
  which routes to `Touch_Hurt`, also an `rts` stub. So even `GameState_ObjectTest`, which spawns 10
  enemies, cannot kill one.
- OJZ act 1's objects, counted by `typeId`: section 0 has 1 solid and 7 springs; section 1 has 1
  solid; section 2 has 1 solid and 1 static; sections 3–8 have none. This matches the booking.

The re-booking stands: the call belongs in the parcel that gives `Touch_Enemy` a defeat.

## 4. Smallest honest additions (PROPOSED ONLY, nothing built)

**No new game state is needed for physics:** the boot scene already has it (the headline). What is
actually missing is narrower.

**a. B2a-2: a caller for `CreateChild_Complex` / `CreateChild_FlipAware`.** The smallest honest
form is a DEBUG-only harness archetype placed beside `ObjDef_Parent` in
`games/sonic4/test/object_test_state.emp`. That module is absent from `s4.lst`, so release is not
touched; the mechanism was not checked, so verify it at build.
- Its init calls `CreateChild_Complex`, or `CreateChild_FlipAware` when its subtype is 1, with its
  own `a0` and a small `SpawnDesc` table.
- The controller spawns it through the objreq mailbox. For the positive case, the controller
  breaks at the init and pokes `parent_ptr` non-zero, so the B2a-2 assert has a child calling it.
  The control is `parent_ptr` = 0.
- Rough size, my estimate and not measured: about 40–60 B of code, a 3-row descriptor table, and
  one `ObjDef` template.
- It moves bytes in **s4.debug only** (demo does not link this module), and moves the debug object
  bank's sigil pins (the routine repin ritual).
- It deliberately gives the two procs their first caller. That is the premise the B2a-2 note
  argued from, so it is the owner's call.

**b. Killed_MarkObject:** not a scene problem. It needs a `COLLISION_ENEMY` archetype, a
`Touch_Enemy` defeat body and the `Killed_MarkObject` call, which together are the badnik parcel.
Nothing to propose here.

**c. C4a-3:** the RAM seed in 3a is honest for a profile. A content route would need at least 128
rings inside one 2x2 window, which is a content decision. Not proposed.

## 5. Stale or wrong in the bookings

1. **"the boot scene (the OJZ scroll test) has no player physics"** is WRONG about the scene; it
   is the debug-fly boot state (headline). It appears in:
   - `docs/DEFERRED_WORK.md`, the C4a runtime-TAG status line;
   - `docs/superpowers/notes/2026-09-12-runtime-witnesses-s7.md`: the header line, the C4a-2
     "Collected half" line, the C1b-3 LIMIT and the "Not run" list.

   Consequences:
   - C4a-2's collected half is reachable in the boot scene (3e).
   - **C1b-3's LIMIT is reachable too.** With physics on, `Collision_GetType` runs every frame from
     `Player_LoopCrossover` and the player sensors, so it can be exercised at a non-zero
     `Cache_Origin_Row` by combining s7's up/down slide with a B press. **RUNTIME-TAG.**
2. **s7's EFX-4b "PARTIAL" most likely did not look at the path the padding is for.** "Frame 400
   after boot: 30 bytes of program ending 8AFF FFFF, then zeros through byte 128. First install
   only." At frame 400 the camera is in section 0, whose preset is `patched: OJZ_TwoChannel`
   (`OJZ_Preset_Sec0`; `act_descriptor.emp`'s `ojz_sec(sec: 0, …)`).
   - A patched install goes through `Raster_InstallPatched` (which sets `Raster_Program` =
     `Raster_Buf_B`) and `Raster_BuildSchedule`. It never reaches `.copy_program`'s fixed 128-byte
     copy.
   - The builder emits its own `$8AFF $FFFF` terminator. `OJZ_TwoChannel`'s body is 50 bytes in
     ROM, and a 30-byte recording fits one suppressed record, but that last point is inference.
   - The zeros past byte 30 are equally explained by boot-cleared RAM.

   **RUNTIME-TAG:** at frame 400, read `Raster_Patch_Tab` (non-zero means patched) and
   `Raster_Program` (a RAM address means patched; a ROM address means static). EFX-4b should be
   re-witnessed on a static pair (3c).
3. **The s7 note's reference listing is no longer the tree it names.** The file on disk has the
   post-fix `Draw_Sprite` layout, so it was rebuilt after `c5dd8c20`. Resolve symbols against the
   ROM you load, not against addresses copied from that note.
4. **"Input free-scrolls the camera"** (brief, s7): the input moves `Player_1` by
   `Player_DebugMove`, and `Camera_Update` follows him. The difference matters for any check that
   reads `Player_1` or the camera deadzone.
5. **"Nothing placed in OJZ act 1 exercises either" (Draw_Sprite)** is true of placed objects
   only. The null-mappings path runs on every ring-sparkle and dust retirement once physics is on
   (3g, derived). The multisprite parent is one mailbox write away in s4.debug (3f).
6. **Killed_MarkObject** (DEFERRED_WORK side finding (a), re-booked): confirmed, and strengthened
   (3h).

## Not checked

- `GameState_Demo`'s body.
- `DeleteObject`'s `.clear_slot` body (its header was relied on).
- What `AnimateSprite` does with null mappings.
- The boot value of `Debug_Lab_Index`.
- Whether channel 1 of `OJZ_TwoChannel` is suppressed at the boot camera.
- The collected-window park geometry for a 200-frame slide.
- How `object_test_state` / `test_parent` are excluded from release (only their absence from
  `s4.lst` was checked).
- Entering ObjectTest mid-run.
