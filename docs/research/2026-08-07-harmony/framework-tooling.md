# Harmony Framework — architecture & developer-tooling study

Source: `github.com/UltraRing/Harmony-Framework`, cloned at
`/home/volence/sonic_hacks/aeon/docs/research/external/harmony/`
GameMaker Studio 2 / GML. Whole `scripts/` + `objects/` GML corpus is **19,468 lines** —
small. Stated goal (README): *"adapt the accuracy of the MEGA Drive Sonic titles … create
an essential, user friendly framework for beginner developers."* MIT for original games.

Scope of this study: framework architecture + developer tooling. Player physics and
rendering/shaders are covered by sibling agents and are deliberately not analysed here.

**Bias warning up front.** Harmony is a *beginner-facing* framework on a platform with
garbage collection, structs, dynamic arrays, `instance_deactivate_object`, a room editor,
and a JIT'd scripting language. Nearly everything it does that we do not do is a thing it
can afford because of those. The valuable extraction is almost entirely at the level of
**which affordances a Sonic developer expects to have**, not how they are built.

---

## (a) DEV-TOOLING REQUIREMENTS INVENTORY

Everything Harmony ships as an in-game developer affordance, with our-side status.
"Ours" spans Aeon (in-ROM), Oracle (emulator/debugger + MCP) and Aurora (editor) — the
comparison is against the *suite*, since on our platform a lot of this correctly lives
outside the ROM.

### A1. Gating and lifecycle

| # | Affordance | Harmony | Ours |
|---|---|---|---|
| 1 | Dev mode is a **build configuration**, not a runtime bool: `#macro DEVMODE (os_get_config() == "Dev")` → `global.dev_mode` | `game_macros.gml:5`, `game_init_global_variables.gml:5` | HAVE — `DEBUG` / `CRASH_REPORT` / `SOUND_DEBUG_HOTKEYS` build axes, three build shapes (ARCH §8.2) |
| 2 | Dev objects instantiated only in dev mode | `obj_global/Other_2.gml:35-39` | HAVE — whole-file gating of `games/sonic4/debug/game_debug.emp`, `compression_selftest` |
| 3 | Dev tools survive the global "suspend everything" pass via an explicit allowlist | `obj_global/Step_1.gml` (`ignore_objects = [obj_dev, obj_shell, obj_pause, obj_dev_menu]`) | N/A shape — we have no global pause; see idea #7 |

### A2. In-game debug menu / navigation

| # | Affordance | Harmony | Ours |
|---|---|---|---|
| 4 | ESC opens a modal **dev menu** that suspends the game (`global.process_objects = false`) | `obj_dev/Step_1.gml:4-7`, `obj_dev_menu/Create_0.gml:11` | NOT PRESENT in-ROM |
| 5 | Dev menu is **declaratively registered**: `dev_menu_add_category` / `dev_menu_add_entry` / `dev_menu_add_option_number` / `dev_menu_add_option_flag` | `dev_util.gml:13-59`, populated at `obj_dev_menu/Create_0.gml:59-99` | NOT PRESENT |
| 6 | Character select as a dev-menu stage before level select | `obj_dev_menu/Step_0.gml:86-116` | NOT PRESENT (single character shipped) |
| 7 | Categorised level select: hand-curated categories ("PRESENTATION", "REGULAR STAGES") **plus** an auto-enumerated "EVERY SCENE" category built by walking `room_first`→`room_last` | `obj_dev_menu/Create_0.gml:77-99` | NOT PRESENT — the auto-enumeration trick is the interesting half |
| 8 | Tunable-options page bound to **global variables by name string**, with min/max/step or flag toggle, edited live | `dev_util.gml:38-59`, `obj_dev_menu/Step_0.gml:225-250` | NOT PRESENT |
| 9 | Player-facing stage select (separate from dev menu) with zone/act grid + sound test | `obj_stage_select/Step_0.gml` | NOT PRESENT |
| 10 | `M` key jump straight to stage select from anywhere | `obj_dev/Step_1.gml:14-18` | NOT PRESENT |

### A3. Hotkey surface (the full map, `obj_dev/Step_1.gml`)

| Key | Function | line | Ours |
|---|---|---|---|
| ESC | open dev menu | 4 | — |
| F5 | toggle the command shell | 21 | — |
| TAB | toggle "debug mode" (object placement + noclip player) | 25 | PARTIAL — B toggles debug-fly (`player_common.emp:260`) |
| B | toggle HUD render | 26 | — (Oracle: `emulator_set_layer_enabled`) |
| T | toggle title cards | 27 | — |
| F9 | show collision layers (plane-aware: only shows the plane the player is on) | 28, `obj_dev/Step_2.gml` | — |
| F8 | show hitboxes | 29 | — (unimplemented in Harmony too: `Draw_0.gml:13-16` is a TODO) |
| F3 | FPS + instance-count overlay | 30, `Draw_0.gml:24-37` | PARTIAL — Oracle profiler; no in-ROM overlay (ARCH §8.5 profiler NOT built, per DEFERRED_WORK) |
| F7 | player state panel | 32 | — (Harmony's is also a TODO; Oracle has `emulator_player_state`) |
| F12 | draw every registered culling rectangle, colour-coded by flag | 33, `Draw_0.gml:39-63` | — |
| F4 | cycle window scale | 34-39 | N/A |
| F2 | soft-restart current room with fade | 41-45 | PARTIAL — Oracle `emulator_reset` |
| F1 | full `game_restart()` | 46 | PARTIAL — Oracle |
| F10 | hot-swap character, re-binding animation list + animator | 47-57 | N/A |
| F6 (hold) | **slow motion** — `game_set_speed(5)` | 59 | — |
| BACKSPACE (hold) | **fast forward** — `game_set_speed(240)` | 60 | — |
| N | mute/unmute BGM | 31 | PARTIAL — Oracle `emulator_set_channel_enabled` |
| V | force act-clear sequence | 65-68 | — |
| 1 (hold) | add rings | 71 | — |
| 2 | add life | 78 | — |
| 3 | cycle shield type | 85 | — |
| 4 | invincibility 1200f | 96 | — |
| 5 | speed shoes 1200f | 103 | — |
| 6 | combine ring | 110 | — |
| 7 | hurt player | 117 | — |
| 8 | kill player | 123 | — |
| SPACE | **cycle through `obj_debug_teleport` markers placed in the room** — moves player *and* camera, and resets all camera limits | 129-149 | — (we have debug-fly, which is a different, freer tool) |

### A4. Free-move / noclip

| # | Affordance | Harmony | Ours |
|---|---|---|---|
| 11 | Debug player: acceleration-based free flight with friction, `collision_allow=false`, `hitbox_allow=false`, `underwater=false`, shift = 2× speed | `player_debug.gml:1-57` | HAVE — debug-fly (`games/sonic4/player/player_common.emp:845+`), bounds deliberately skipped, art swap to a marker |
| 12 | Debug mode **resurrects** a dead/drowned player (restores state, fade, camera mode, depth) | `player_debug.gml:60-70` | Not present; small, worth having |

### A5. Object placement (the in-game editor)

| # | Affordance | Harmony | Ours |
|---|---|---|---|
| 13 | Mouse-wheel scroll through a curated `object_list`, ghost-preview the selected object's sprite at the cursor at 0.75 alpha, name label above cursor | `obj_dev/Create_0.gml:3`, `Step_1.gml:170-175`, `Draw_0.gml:68-93` | Aurora does this offline, not in-ROM |
| 14 | Left click = place instance on the "Objects" layer; right click = delete the instance under the cursor | `obj_dev/Step_1.gml:178-195` | Aurora (offline) |
| 15 | Placement is **not persisted** — it is a live scratch tool, not an editor | (implicit; nothing writes back) | — |

### A6. Command shell (`obj_shell`)

`obj_shell` is a vendored copy of the third-party GameMaker **rt-shell** console
(`Create_0.gml:57,76,380` reference `rt-shell` by name; upstream issue numbers `#18`/`#32`
survive in comments). Harmony's own contribution is `game_shell_functions.gml` — four
commands. The library's mechanics are the interesting part:

| # | Affordance | Harmony | Ours |
|---|---|---|---|
| 16 | Commands are **discovered by naming convention** at boot: every global named `sh_*` becomes a command; every global named `meta_*` returns its help/argument metadata struct | `obj_shell/Create_0.gml:117-151` | N/A (no reflection in asm) — but the *pattern* maps to a build-time generated table |
| 17 | Per-argument autocomplete: metadata declares a suggestion array **or a function returning one** (dynamic), per argument index | `Create_0.gml:178-208` | Oracle CLI/MCP has no argument completion |
| 18 | **Mouse-picked arguments** — a suggestion slot can be typed `mouseArgumentType.worldX/worldY/guiX/guiY/instanceId/objectId`; the shell then live-reads the cursor's world position or the instance under the cursor and fills the argument | `Create_0.gml:62-70`, `Step_0.gml:284-305`, used at `game_shell_functions.gml:12` | NOT PRESENT anywhere in the suite. This is the single best idea in the repo |
| 19 | Deferred command queue — commands that must run while the game is *not* paused are queued and flushed on shell close | `Create_0.gml:53,100-103`, `Step_0.gml:171` | Oracle: no equivalent; MCP calls run against a paused core |
| 20 | Command execution wrapped in try/catch; exception message + longMessage + script + stacktrace dumped, console shows a short error | `Create_0.gml:376-386` | N/A |
| 21 | Persistent command history to disk, truncated to `savedHistoryMaxSize`, restored next launch | `Create_0.gml:411-440` | Oracle: not present |
| 22 | Full readline ergonomics: bash kill/yank (Ctrl-K/Ctrl-Y), Ctrl-A/Ctrl-E, key-repeat with initial-delay then repeat-delay, common-prefix tab completion | `Create_0.gml:216-285`, `Step_0.gml:39-60` | — |
| 23 | Shipped commands: `help`, `clear`, `instance_create`, `room_goto`, `suicide`, `music_play`, plus shell-geometry setters | `Other_10.gml`, `game_shell_functions.gml` | Oracle MCP is far richer at the *machine* level (breakpoints, VRAM, registers), poorer at the *game* level |

### A7. Build/version provenance on screen

| # | Affordance | Harmony | Ours |
|---|---|---|---|
| 24 | Debug overlay prints window caption + `GM_version`, `GM_build_date` date and time, player X/Y, camera X/Y, room dimensions | `obj_dev/Draw_0.gml:79-88` | NOT PRESENT in-ROM |
| 25 | `fps` vs `fps_real` distinction — displayed rate vs true achievable rate, `fps_real` sampled on a 10-frame alarm to keep it readable | `obj_dev/Create_0.gml:13`, `Alarm_0.gml`, `Draw_0.gml:32` | Analogue = `Lag_Frame_Count`; the "sample slowly so a human can read it" trick is not applied anywhere |

### A8. What Harmony does **not** ship (honest gaps)

- No hitbox display (F8 is a TODO stub, `obj_dev/Draw_0.gml:13-16`).
- No player state inspector (F7 is a TODO stub, `Draw_0.gml:19-22`; a commented-out
  version at `Draw_64.gml:10-33` shows the intent: total step time + culling-pool size).
- No frame stepping / single-step. Slow-mo and fast-forward only.
- No breakpoints, watchpoints, memory inspection, save states, or rewind.
- No logging framework — `show_debug_message` calls are ad hoc.
- No profiler beyond `get_timer()` around the step (`obj_global/Step_1.gml`,
  `Step_2.gml`), and its only consumer is commented out.
- No instance recorder consumer: `instance_recorder_*` (`instance_util.gml:285-345`) is a
  complete circular value-history recorder with zero callers in the repo.
- `file_bin_util.gml` (all 95 lines) has **zero callers** — dead helper library.

**Net:** on raw debugger capability Oracle vastly exceeds Harmony. On *game-level* dev
affordances — level select, cheats, live tunables, in-world markers, on-screen provenance,
time control — Harmony is meaningfully ahead of us, and those are cheap on 68000.

---

## ANSWERS TO THE EIGHT QUESTIONS

### 1. Object / instance management

`instance_util.gml` (713 lines) is a **grab-bag utility module**, not an object manager. It
is roughly four unrelated things:

1. **Solid-object collision** (`instance_act_solid` :8, `instance_act_semi_solid` :109,
   `instance_collide` :183) — AABB push-out returning a collision side, with a
   hard-coded `if (o.object_index == obj_player)` branch to a player-specific reaction
   (:88-96). Sibling-agent territory, but architecturally note the **result struct is a
   preallocated global** (`global.collision_result_struct`, :78-83) reused every call to
   avoid per-call allocation. That is a GC-avoidance pattern with an exact 68000 analogue
   (a fixed scratch block) — and it is what we already do implicitly.
2. **Culling registration** (`instance_register_culling` :239).
3. **A value recorder** (:285-345) — register `(instance, variable_name)` pairs, ring-buffer
   the last N frames of each, query with a frame offset. Zero callers. Intended for
   trailing-effect/afterimage work and for post-hoc debugging.
4. **Spawn helpers** — bullets (:358), particles (:427), debris (:466), score popups
   (:486), ring loss (:521).

**Culling / activation.** The real system is in `obj_level`:

- Objects opt in via `instance_register_culling(region, on_culling, flags)`
  (`instance_util.gml:239-268`), which pushes a struct
  `{inst_id, region, type, cull_flag, culled, flag}` onto `obj_level.instance_list`.
- `obj_level/Step_2.gml` walks that list **every frame, linearly, all of it**, against a
  camera rect expanded by `CULL_REGION_W/H = 128` (`game_macros.gml:12-13`). Dead entries
  are spliced out during the walk (:20-24).
- Two check modes as a bitfield (`CULL_FLAG.CHECK_ENTITY_POS` / `CHECK_ENTITY_START`,
  `game_enums.gml:64-68`): current position and/or **spawn** position. Moving platforms
  register START only (`par_moving_platform/Create_0.gml:14`) so a platform that has
  wandered offscreen still deactivates by its origin; badniks register both
  (`obj_badnik_wheeltank/Create_0.gml:22`).
- Two policies (`CULL_TYPE`, `game_enums.gml:57-61`): `DEACTIVATE` (default) or `DISABLE`
  (never cull). Scattered rings from a hit set `culling_struct.type = CULL_TYPE.DISABLE`
  so they cannot vanish mid-flight (`instance_util.gml:536`).
- **On-cull callback**: `on_reset` is invoked at the moment of deactivation, so badniks
  snap back to `xstart/ystart` (`obj_badnik_ribbot/Create_0.gml:29-33`).

**Respawn / persistence semantics.** Split in two:

- *Reversible* (badniks, moving parts): reset-on-cull callback. State is the object's own
  spawn transform. Classic Sonic behaviour, same as ours.
- *Irreversible* (collected rings, broken monitors, killed badniks): a global list keyed by
  **instance id**, `global.store_object_state[| id] = true`
  (`obj_ring/Step_0.gml:24`, `obj_monitor/Step_2.gml:80`, `par_badnik/Step_0.gml:29`).
  On room start / create, the object checks the list and self-destroys
  (`obj_ring/Create_0.gml:12-15`, `obj_badnik_ribbot/Other_4.gml`). The list is cleared on
  death (`player_state_knockout.gml:66,83,134,151`) and on `level_reset_data()`
  (`level_util.gml:12`) — i.e. it is *checkpoint-scoped* persistence.

**Pooling: none.** Every spawn is `instance_create_depth` (GC-backed). No free list.

**Priority / update order: none explicit.** Order is GameMaker's, sorted by `depth`, which
doubles as the draw order. Controllers force themselves to the front with
`depth = -1000` (`obj_global/Other_2.gml:3`, `obj_dev/Create_0.gml:22`). The only ordering
discipline is the Step-0 / Step-1 / Step-2 (begin/step/end) event split, used as a crude
three-phase frame: input+suspend in Step-1, gameplay in Step-0, culling+music+fade in
Step-2 (`obj_global/Step_1.gml`, `Step_2.gml`; `obj_level/Step_2.gml`).

**Versus the classic "object slot" model, and versus ours.** Harmony abandons the slot
model entirely — no fixed pool, no 64-byte SST, no slot ceiling, and therefore no
allocation strategy at all. Its culling walk is O(all registered objects) per frame with no
spatial ordering and no early exit; ours (`ARCH §4.9`) is an X-sorted ROM list per section
with per-section ratchet pointers, 2×2 quadrant tracking, Y banding with load/despawn
hysteresis, idempotent-spawn bitmasks, mask migration on slide, and a 3×3 rolling
collected/killed bitmask window. **They solved nothing we did not.** Three details are
nonetheless worth naming:

- The **spawn-position vs current-position culling flag** is a real distinction we express
  differently (`OEF_ANY_Y` + section-lifetime) but less generally.
- The **on-cull callback** is a hook we do not have: our despawn is `DeleteObject`, and an
  object cannot run cleanup at despawn time. Cheap to add, occasionally load-bearing
  (releasing a rider, clearing a trigger flag, decrementing a shared counter).
- The **never-cull escape hatch per instance** (`CULL_TYPE.DISABLE` on scattered rings) is
  something we handle by keeping scattered rings out of the ROM-list system entirely; worth
  confirming that invariant holds when scattered rings are implemented.

### 2. The "shell" concept

`obj_shell` is **not a Harmony abstraction** — it is a vendored third-party in-game
command console (rt-shell). The problem it solves: *let a developer invoke arbitrary
engine functions at runtime without a rebuild, with discoverability*. It is a REPL bolted
to the game.

Is the abstraction worth having? **The REPL, no. The three mechanisms inside it, yes:**

- Command registry built by **convention-based discovery** with a parallel metadata
  namespace (`sh_foo` + `meta_foo`) — on our platform this becomes a build-time generated
  command table, which is strictly better (no reflection cost, build-time validated).
- **Per-argument dynamic suggestions** (a function that returns the valid values *now*).
- **Mouse-picked arguments** — see idea #1 below.

The console *itself* is the wrong shape for us. Text entry on a 6-button pad is miserable,
and everything the console does at the game level, Oracle can do better from the host side
with a real keyboard — provided Oracle grows game-level commands, not just machine-level
ones.

### 3. Config / macros / enums — build-time vs run-time

Three tiers, cleanly separated, and the separation is the good part:

1. **`game_config.gml`** — the *documented user-editable file*. Literally headed
   `// This is where you configure Harmony Framework`. Ten `#macro`s: resolution,
   `ANGLE_GRID_SIZE`, `PLAYER_ALT_COLLISION_MODE`, `PLAYER_MAX_STEPS`,
   `PLAYER_STEPS_AMOUNT`, `INSTA_SHIELD_BOX_SIZE`, `WATER_FLASH_COLOR`, `WATER_FLASH`,
   `KNUCKLES_S3_GLIDE_TURN`. Every one carries a prose comment explaining the tradeoff,
   and one carries an external reference URL (`game_config.gml:11`). **Compile-time,
   one file, curated, documented.**
2. **`game_macros.gml`** — internal derived macros: `DEVMODE`, camera-view accessors,
   cull region sizes, global aliases. Not user-facing.
3. **`game_init_global_variables.gml`** — ~25 *runtime* feature flags with the same
   comment discipline: `use_peelout`, `use_dropdash`, `use_airroll`, `use_spindash`,
   `use_insta_shield`, `camera_pan_type`, `camera_type`, `chaotix_dust_effect`,
   `chaotix_monitors`, `no_skid_state`, `water_running_effect`, `rotation_type`,
   `knux_camera_smooth`, `super_button`. These are the "which Sonic game do you want to
   feel like" dials, and several are exposed live in the dev menu
   (`obj_dev_menu/Create_0.gml:70-74`).

**Compile-time validation: none.** No asserts, no `ensure`, no contract checks, no build-time
range checking. GML cannot express it and Harmony does not try.

**Engine-vs-game separation: essentially none, and this is Harmony's weakest axis.**
There is no engine/game wall. `instance_util.gml:88` hard-codes `obj_player`;
`instance_util.gml:492-514` hard-codes badnik score chaining into a generic spawn helper;
`obj_level`'s "default stage setup" block hard-codes `MUSIC.TECHDEMO_TOWER` and
`"Empty Level"` (`obj_level/Create_0.gml:9-32`); enums for shields, monitors and emeralds
live in the shared `game_enums.gml`. The one genuinely good separation mechanism is
**room creation code as a per-level manifest**: `rooms/rm_arboreal_agate1/RoomCreationCode.gml`
is a `with(obj_level){ … }` block setting `stage_music`, `stage_name`, `act`,
`act_transition`, `animal[]`, `next_level`, overriding the defaults `obj_level/Create_0.gml`
established. That is exactly our `implement Game` manifest idea in a much weaker form — no
types, no required-member checking, no build failure if a level forgets a field (it silently
inherits "Empty Level").

Our `interface Game` / `implement Game` with `ensure(extern(...) == ...)` walls and
whole-ROM link resolution (ARCH "Engine/game contract") is strictly ahead. The one thing
Harmony has that we should copy is the **single curated, prose-commented, user-facing config
file** — `games/<game>/config/constants.emp` is close but it is an engineering file, not a
"here is your dashboard" file.

### 4. Dev tooling

See inventory (a) above — that is the full answer, 25 numbered affordances plus the eight
honest gaps.

### 5. Level / act structure

- **A level is a GameMaker room.** `obj_level` is the per-room controller singleton and
  holds the level's identity (`stage_music`, `stage_name`, `act`, `act_transition`,
  `animal[]`, `next_level`); `RoomCreationCode.gml` per room overrides those.
- **Layer structure is convention, enforced by string names.** From
  `rooms/rm_arboreal_agate1/rm_arboreal_agate1.yy`, depth-ordered:
  `Utilities` (0) → `Collision` group (100) containing `CollisionTriggers` (200),
  `CollisionA` (300), `CollisionB` (400), `CollisionMain` (500), `CollisionSemi` (600) →
  `PlaneFront` (700) → `Objects` (800) → `PlaneBack` (1000) → `ObjectsBack` (1100) →
  `BackgroundObject` (1200). The names are hard-coded in
  `game_init_global_variables.gml:50` (`global.col_tile`) and toggled by name in
  `obj_level/Step_0.gml:10-14`. `rm_template` is the starter room a new level copies.
- **Plane A/B layer switching** is an object: `obj_layer_switch` reads a
  `layer_type` string property ("Layer A", "Layer B", "From A to B", "From B to A") and
  sets `obj_player.plane`, direction-sensitive on `ground_speed`, with an optional
  `ground_only` gate (`obj_layer_switch/Step_0.gml:1-23`).
- **Camera bounds are objects**: `obj_bounds_marker_h` sets `obj_camera.target_top` or
  `target_bottom` while the player's X is inside its bbox (`Step_0.gml:7-16`), and the
  camera lerps `limit_*` toward `target_*`. `obj_camera_boundary` complements it.
- **Act transition** is a snapshot/restore across a room change (`obj_act_transition`).
  `Create_0.gml` records *everything relative to a marker object* `obj_act_trans_marker`:
  player XY delta, shield, camera XY delta, all four camera limit deltas, signpost delta,
  every background object's per-layer scroll offsets, background visibility, and the full
  state of every monitor the signpost bumped (position delta, type, destroyed flag, depth).
  Then `global.act_transition = true`, `level_reset_data()`, `room_goto(next_level)`. The
  marker object is the coordinate origin that makes act 1 and act 2 stitchable even though
  they are separate rooms. **This is a coordinate-rebase across a level boundary, and it is
  conceptually the same trick as our floating-origin rebase (ARCH §4.11)** applied to a
  seam instead of to overflow.
- **`obj_script_trigger`** is a 15-line object with two editor-exposed properties:
  `script_to_execute` (a function-typed object property, default `function() { }`) and
  `trigger_once` (bool). Step: if the player overlaps and not yet triggered, `script_execute`
  it; if `!trigger_once`, re-arm on exit (`obj_script_trigger/Step_0.gml`). The scripts it
  calls live in per-zone script files — `stage_script_aaz.gml` is 14 lines and defines
  exactly one, `change_water_level(level, rise_speed, water_obj)`.

**Is scripted-event authoring a good pattern?** Yes, and it is one of the two ideas here
worth real investment. The value is not the mechanism (a callback) — it is the
**authoring model**: the designer drops a box in the editor, picks a function from a
dropdown, sets its arguments, and gets a level event with no new object type, no new
object ID, no engine code. Every zone-specific set piece — water rise, camera lock,
boss arena entry, music change, cutscene start, layer forcing — collapses into one
placeable primitive. On 68000 the callback is a ROM pointer, which is the cheapest thing
there is. See idea #2.

### 6. Animator

`animator_util.gml` (378 lines). A per-instance `animator` struct (`animator_create` :3)
plus a per-object **animation list** built with `animation_add(id, sprite, speed,
loop_frame, loop_flag, use_duration)` (:125) — e.g. `player_animation_list.gml` (159 lines,
rebuilt on character swap: `obj_dev/Step_1.gml:52`).

Two timing modes:
- **speed mode** — fractional frame accumulator, `animation_frame += animation_speed` (:34).
- **duration mode** — integer sub-image counter against a duration, where the duration may
  be a **scalar or a per-frame array** (:40-53). Per-frame durations clamp to the last
  array entry (`min(frame, len-1)`), so a short duration array covers a long sprite.

Other features: `loop_frame` (loop target ≠ 0, i.e. intro-then-loop), a `finished` flag
(set even on looping animations, :76), `animator_reset` as a **deferred** flag consumed at
the next update (:24, :90) rather than an immediate mutation, a listless
`animation_play_no_list` for one-off effects (:144), `dont_reset_frame` for
animation changes that should preserve phase (:153), and a full getter/setter surface
(`animation_get_sprite/frame/speed/frame_count/loop_index/duration`,
`animation_set_speed/duration/loop_index/frame`).

**Anything better than a classic frame/duration table? No.** It *is* a frame/duration
table with a decent API. It has no events, no callbacks, no branching, no
speed-linked timing (Sonic's speed→animation coupling is done by the caller poking
`animation_set_speed`). Our animation system (ARCH §3.6) is a bytecode **behavior
sequencer** with `AF_CALLBACK` / `AF_SOUND` / `AF_COLLISION` / `AF_SET_FIELD` events,
loop/jump/branch control codes, speed-scaled timing built in, and multi-sprite child
driving — strictly a superset. Three small things Harmony has that are worth checking
against ours:

- **Per-frame duration arrays that clamp short** — a 3-entry duration array driving a
  12-frame sprite. Ours has per-frame durations in PerFrame mode; the clamp-short
  convenience is not obviously present.
- **`loop_frame` ≠ 0** — intro-then-loop in one animation. We have `$FE = jump back`,
  which covers it.
- **`dont_reset_frame`** — change animation without resetting phase. Genuinely useful for
  e.g. walk↔run at matched cadence. Worth confirming we can express it (we have
  `prev_anim`/`prev_frame` change detection, which implies a reset on change).

### 7. File / data

`file_bin_util.gml` defines **no formats**. It is 95 lines of big-endian fixed-width integer
read/write over GameMaker's binary-file API: `int8`/`uint8`/`int16`/`uint16`/`int32`/`uint32`
(`file_bin_util.gml:5,15,24,36,46,63,75,85`). Explicitly big-endian
(`<< 8 * (1 - i)` :52, `<< 8 * (3 - i)` :91) — i.e. **Mega Drive byte order**, which is the
tell: it was written to read/write Genesis-native data blobs.

It has **zero callers in the repo**. Its `int16` sign-extension is also wrong
(`result - 65535` at :39, should be `65536`), which confirms it was never exercised. The
only binary persistence actually in use is elsewhere: a commented-out
`game_tile_file_save()` in `game_init_collision.gml` (the collision height-map cache) and
rt-shell's JSON history file.

The intent is legible and worth naming: they wanted **precomputed collision height maps
cached to a binary file rather than recomputed at boot**. Today `game_init_collision.gml`
bakes 16×16 tile height maps at startup by mask-sampling sprites, and it
`show_debug_message`s the bake time — i.e. it is slow enough to have been measured
(`game_init_collision.gml:70`). We do this correctly already: collision is embedded in the
block strips at build time (ARCH §4.7, §8.1 step 5) and there is no runtime bake. **Nothing
to take.**

### 8. Ease / math

**`ease_util.gml`** — the complete Robert Penner / easings.net set, 30 functions,
in/out/inOut × sine, quad, cubic, quart, quint, expo, circ, back, elastic, bounce
(`ease_util.gml:5-296`). Pure `float → float` on `[0,1]`, no duration/time handling — the
caller owns the timeline.

68000 feasibility, honestly:

| Family | Feasible? | Note |
|---|---|---|
| quad/cubic/quart/quint | **Yes, as tables** | 64- or 128-entry `dc.w` LUT per curve, ~128-256 B each. Runtime is `move.w tbl(pc,d0.w),d1`. Computing them is build-time Python. |
| sine | **Yes** | we already need sine tables; ease-in/out-sine is a re-indexing of one |
| back / elastic / bounce | **Yes, as tables** | the shapes overshoot outside [0,1]; store signed 8.8 |
| expo / circ | **Yes, as tables** | same |
| Any of them *computed* at runtime | **No** | needs `mulu`/`divu`/`pow`/`sqrt`; conventions forbid `mulu`/`divu` |

The correct 68000 shape is: **one 128-entry 8.8 fixed-point LUT per curve you actually
use**, generated at build time, plus a single `Ease(curve_id, t)` lookup. Do not port 30
curves; ship the 4-6 that appear in real motion (out-quad, in-out-quad, out-back,
out-bounce, out-expo). Harmony itself uses easing sparingly.

**`math_util.gml`** (129 lines) — six helpers, and the interesting half is the last two:

- `math_uangle(a)` (:5) — mirror an angle about 180°. Trivial.
- `math_approach(val, target, step)` (:19) — the single most-used helper in the framework.
  Ours is `move toward`, expressed inline everywhere. Worth having as a macro.
  **68000: trivial** (compare + add/sub + clamp).
- `math_wrap(val, min, max)` (:34) — note this is *snap-to-other-end*, not modulo; it wraps
  by exactly one step, which is what menu selection needs. Used everywhere in the dev menu
  and pause menu. **68000: trivial.**
- `math_lerp_angle(value, angle, amount)` (:55) — shortest-arc angle interpolation via
  `((target - value + 540) mod 360) - 180`. **68000: feasible if angles are 0-255**
  (`(target - value + 128) & 255) - 128`, all AND/ADD, no divide) — and that is the right
  representation anyway.
- `math_pinhole_scale(px, py, pz)` (:73) — perspective projection, `1/(1+z)`. **68000: no**
  as written; a reciprocal LUT over z would make it feasible, but nothing in a
  Sonic engine needs it.
- **`sin256` / `cos256`** (:94-129) — and this is the real find. They compute the
  **Mega Drive's exact sine table**: 256-entry, amplitude 256, built as
  `sin(i/128 * pi) * 512`, truncated toward zero, then `>> 1`, with four cardinal entries
  hard-corrected (`0, 64, 128, 192` forced to `0, 256, 0, -256`) — `__trig256_build` :118-129.
  A modern high-level framework deliberately reproducing the 68000 table's exact rounding
  and its four hand-fixed entries is a strong independent confirmation that
  **256-unit angles + a 256-entry `dc.w` amplitude-256 table is the right primitive**, and
  the four corrections are the ones to bake into our generator. **68000: this IS the
  68000 approach** — Harmony back-ported it.

---

## (b) RANKED IDEAS, WITH VERDICTS

Ranked by expected value to us, highest first.

---

### 1. Mouse-picked command arguments — click the world to fill in a parameter
**Harmony:** `objects/obj_shell/Create_0.gml:62-70` (the `mouseArgumentType` enum),
`objects/obj_shell/Step_0.gml:284-305` (live resolution of worldX/worldY/instanceId/objectId),
`scripts/game_shell_functions/game_shell_functions.gml:12`
(`suggestions: [mouseArgumentType.worldX, mouseArgumentType.worldY, [], []]`).

A command declares that argument N is "a world X coordinate" or "the instance under the
cursor"; the console then watches the mouse and offers the live value, which the user
commits with a keypress. Typing `instance_create ` and then clicking where you want the
spring is a categorically better interaction than typing coordinates.

**Ours:** Oracle's MCP surface is entirely address- and value-typed
(`emulator_write_memory`, `emulator_breakpoint_add`, `emulator_object_slot`). Nothing in
the suite resolves a *screen click* to a *game-space value*. Oracle already renders the
framebuffer and already knows camera position (it exposes `emulator_player_state` and VDP
registers), so the transform is available.

**Verdict: [WORTH TAKING — Oracle].** Concretely: click-to-world-coordinate readout in the
Oracle GUI, click-to-object-slot (hit-test the click against the live SST list Oracle
already enumerates via `emulator_object_list`), and both surfaced as MCP results so an
agent can say "what object is at this screen position". This is the highest-leverage
single idea in the repo and it costs zero ROM bytes.

**68000 feasibility:** N/A — host-side.

---

### 2. `obj_script_trigger` — the placeable scripted-event primitive
**Harmony:** `objects/obj_script_trigger/Step_0.gml` (15 lines),
`objects/obj_script_trigger/obj_script_trigger.yy` properties
(`script_to_execute`, function-typed, editor-exposed; `trigger_once`, bool),
consumer example `scripts/stage_script_aaz/stage_script_aaz.gml`.

One object type. Editor-picked callback. Editor-set re-arm policy. Every zone-specific
set piece becomes data.

**Ours:** we have `obj_script_trigger`'s *ingredients* and none of its *shape*. Our object
spawn is archetype-template driven (ARCH §3.7, 26-byte ObjDef) with a 5-bit per-section
type index and an 8-bit subtype; a per-section ROM type table already maps type index →
ObjDef pointer (ARCH §4.9.2). We have a level trigger flag array for button↔door coupling
(ARCH §9.2). What we do *not* have is a generic "run this ROM routine when the player
enters this box" placeable, and we do not have an editor affordance for choosing the
routine.

**Verdict: [WORTH TAKING — Aeon + Aurora].** The Aeon half is small: an ObjDef whose
`sst_custom` holds a ROM routine pointer + a trigger-once bit, and whose code does an AABB
test against the player and `jsr`s. The subtype byte can index a per-section
*script table* exactly parallel to the existing per-section type table — which keeps the
"32 types, 256 subtypes, no global ID space" property. The Aurora half is the real work: a
dropdown of the current act's script table entries and per-trigger argument fields, exported
into the objentry stream.

Design caution consistent with ARCH §3.7's object-authoring rule: the trigger's stored state
must be a ROM pointer and flags, never an absolute world coordinate, so a future
floating-origin rebase (§4.11) does not strand it.

**68000 feasibility:** trivially cheap — a bbox compare plus an indirect `jsr` through a
bounds-checked table index (and ARCH §8.4 already specifies `cmpa.l #ROM_End,a0` before any
indirect call, plus `chk` for the table index).

---

### 3. In-ROM dev menu with declarative registration and live-tunable globals
**Harmony:** `scripts/dev_util/dev_util.gml:13-59` (the four `dev_menu_add_*` registrars),
`objects/obj_dev_menu/Create_0.gml:59-99` (the whole menu declared in 40 lines),
`objects/obj_dev_menu/Step_0.gml:225-250` (live edit of a named global with min/max/step,
or flag toggle).

The menu is *data*: categories, entries, and tunables are registered by calls, not by a
hand-written UI. Adding a level to the level select is one line. Exposing a physics
constant as a live dial is one line.

**Ours:** we have no in-ROM menu of any kind. Level entry is `Game.ENTRY_ID` / `Game.entry`
fixed at build time (ARCH "Engine/game contract"); changing which level boots is a rebuild.
Physics constants are comptime.

**Verdict: [WORTH TAKING — Aeon, DEBUG shape only].** Two independently valuable halves:

- **Level/state select.** A DEBUG-shape menu over the game-state table would remove a
  rebuild from every "look at act 2" loop. This is the higher-value half and it is
  small — a table of `(name string, GameState proc, state id)` and a 20-line
  up/down/confirm loop.
- **Live tunables.** Harmony edits globals *by name string* via `variable_instance_set`.
  On 68000 the equivalent is a ROM table of `(name, RAM address, size, min, max, step)`
  and a generic editor — perfectly feasible, but it only works for values that live in RAM.
  Most of our tuning constants are comptime immediates baked into instructions, so this
  half requires deciding which constants get promoted to RAM in the DEBUG shape. That is a
  real cost and it should be scoped to a short, deliberate list (camera lag, camera
  look-ahead, parallax rates) rather than done wholesale.

**68000 feasibility:** menu = trivial. Tunables = feasible, but constrained to
RAM-resident values; do not promote comptime constants wholesale.

---

### 4. Time control: slow-motion and fast-forward hotkeys
**Harmony:** `objects/obj_dev/Step_1.gml:59-60` — hold F6 → 5 fps, hold BACKSPACE → 240 fps,
via `game_set_speed`.

Two lines of code for the single most useful "see what is actually happening" tool in the
list. Slow-mo makes one-frame visual bugs (our teleport edge flash, mid-scroll artifacts,
DMA races) directly observable by eye; fast-forward makes "walk to the far end of the act"
instant.

**Ours:** Oracle has `emulator_step` / `emulator_step_over` / `emulator_run_to` /
`emulator_run_to_scanline` — instruction- and scanline-granular, which is *finer* than
slow-mo but not the same tool. What is missing is **continuous playback at a controlled
rate with input still live**, i.e. playing the game in slow motion while holding right.
Memory note "[Verify render/scroll DURING motion]" says at-rest captures hide scroll
artifacts — this is exactly the tool for that.

**Verdict: [WORTH TAKING — Oracle].** A host-side frame-rate throttle/turbo is the right
home (no ROM cost, works on every build shape including release, and composes with the
existing input-replay net). An in-ROM version (skip N frames of game logic / run the loop
N times) is possible but changes timing semantics and would falsify anything
timing-sensitive; prefer the emulator.

**68000 feasibility:** N/A — host-side, and it should stay host-side.

---

### 5. On-cull callback: let an object run cleanup at despawn
**Harmony:** `scripts/instance_util/instance_util.gml:239-268` (the `on_culling` parameter
stored as `culled`), `objects/obj_level/Step_2.gml:47-49` (`if(is_method(inst.culled)) inst.culled();`),
usage `objects/obj_badnik_ribbot/Create_0.gml:29-33` (reset to `xstart/ystart`).

**Ours:** ARCH §4.9.3 despawn calls `DeleteObject` directly (which pushes the slot and
zeroes the SST). There is no per-archetype despawn hook. Most objects do not need one —
our respawn is ROM-driven, so "reset to spawn position" is implicit. But objects holding
*external* state do: a platform with a rider, an object that incremented a shared counter,
an object holding a trigger-array bit, a parent whose children live in the effect pool.

**Verdict: [WORTH TAKING — Aeon], small and conditional.** Add an optional `on_despawn`
routine pointer to the ObjDef archetype (the 26-byte layout has no spare field, so this
costs 2-4 bytes per ObjDef and a null test per despawn). Do not build it speculatively —
build it the first time an object needs it, and note that Harmony's primary use of the hook
(position reset) is one we do not need.

**68000 feasibility:** `tst.l`/`beq` + `jsr` on the despawn path only. Negligible.

---

### 6. Single curated, prose-commented, user-facing config file
**Harmony:** `scripts/game_config/game_config.gml` — 30 lines, 10 macros, every one with a
comment explaining what it does and what the tradeoff is, one with an external reference
URL (`:11`). Headed `// This is where you configure Harmony Framework`.
Its runtime sibling `scripts/game_init_global_variables/game_init_global_variables.gml:64-78`
does the same for the ~14 "which Sonic feel do you want" flags.

**Ours:** `games/sonic4/config/constants.emp` is the nearest thing, but it is an engineering
file — the mix of tunables, layout facts, and derived values means a new game author cannot
tell which lines are theirs to change. The engine/game *contract* is superbly documented
(ARCH "Engine/game contract"); the engine/game *dials* are not.

**Verdict: [WORTH TAKING — Aeon], cheap and purely organisational.** Split a
`games/<game>/config/tuning.emp` (or a clearly-fenced section of `constants.emp`) that
contains only author-facing dials, each with a one-line prose comment and its valid range,
and reference it from `games/demo/`'s "start here" story. Zero bytes. This is squarely on
Harmony's stated goal ("user friendly framework for beginner developers") and it is the axis
where a beginner-facing framework legitimately beats us.

**68000 feasibility:** N/A.

---

### 7. Placed teleport markers, cycled with one key
**Harmony:** `objects/obj_dev/Step_1.gml:129-149` — SPACE cycles through every
`obj_debug_teleport` instance in the room, moving player *and* camera and resetting all
camera limits to room bounds; `teleport_id` wraps modulo the instance count and resets on
room start (`obj_dev/Other_4.gml`).

The point is that the *level designer* places the interesting spots in the editor, and the
tester just taps one key. Much better than "fly there" for repeatable testing of a specific
set piece.

**Ours:** debug-fly (`games/sonic4/player/player_common.emp:845+`) is more powerful but
requires manual navigation every time. Oracle can `emulator_write_memory` the camera and
player position, but that requires knowing the coordinates.

**Verdict: [WORTH TAKING — Aurora + Oracle], not Aeon.** The right split for us: Aurora
already knows the act's named locations (it places objects and rings on a canvas), so it
should export a small named-waypoint list; Oracle consumes it and offers "warp to waypoint"
by writing camera + player position + re-running the entity-window rebuild. Putting the
markers in the ROM as spawned objects (Harmony's approach) would cost object slots and ROM
in a shape we do not want to ship.

Note the fiddly part Harmony gets right and we would have to replicate: after teleporting,
it resets *every* camera limit (`Step_1.gml:140-145`), because the boundary-marker objects
that set those limits will not have run for the new position. Our equivalent is the entity
window anchor + `BuildEntries` — a warp is a rebase-shaped operation, not a position poke.

**68000 feasibility:** N/A if host-side. If ever in-ROM, the "reset the derived camera
state" step is the whole difficulty, and ARCH §4.9.3 already documents that shape.

---

### 8. Culling visualiser (draw every registered cull region, colour-coded by flag)
**Harmony:** `objects/obj_dev/Draw_0.gml:39-63` — F12 draws each registered culling struct's
rectangle at 0.5 alpha, maroon for `CHECK_ENTITY_POS`, teal for `CHECK_ENTITY_START`, so
both boxes are visible when an object registers both.

**Ours:** we have far more to visualise (2×2 entity window, X ratchet position, Y band,
load vs despawn hysteresis boundaries, the 3×3 collected window, section grid). We
currently visualise none of it — the entity window is verified by reading RAM through
Oracle and reasoning.

**Verdict: [WORTH TAKING — Oracle].** An overlay that draws, on top of the emulator's
framebuffer: the section grid with ids, the 2×2 window entries with their `SEC_VOID`
status, the X load/despawn edges, the Y band edges, and every buffered ring's world
position. Oracle already reads all of this (`Entity_Window_Anchor`, `Entity_Scan_State`,
`Ring_Buffer` are all named RAM). This turns "read 1,448 bytes of RAM and reason" into
"look at it", and it is the natural companion to the memory-note lesson about verifying
during motion.

**68000 feasibility:** N/A — pure host-side overlay, which is also why it beats an in-ROM
version (no VRAM, no sprites, no ROM, works in release builds).

---

### 9. Build provenance + readable-rate FPS on the debug overlay
**Harmony:** `objects/obj_dev/Draw_0.gml:79-88` (caption, `GM_version`, `GM_build_date`
date and time, player XY, camera XY, room dimensions);
`objects/obj_dev/Create_0.gml:13` + `Alarm_0.gml` + `Draw_0.gml:32`
(`fps` vs `fps_real`, the latter resampled every 10 frames so it is readable).

**Ours:** nothing on screen. This is genuinely a recurring cost for us — memory notes
record "daemon plain-rebuilds mid-session (byte-verify ROM-vs-lst!)" and "stale sigil
binaries" as gate traps. A build stamp burned into the ROM and displayed on the DEBUG boot
screen would have caught both classes directly.

**Verdict: [WORTH TAKING — Aeon (build stamp), Oracle (display)].** Split it:
- **Aeon:** emit a build-identity blob (git short SHA, build epoch, shape flags) into a
  fixed ROM location in every shape including release. A dozen bytes. This is the part that
  actually solves "am I running the ROM I just built".
- **Oracle:** read and display it in the title bar, and expose it via MCP so an agent can
  assert freshness before believing a test result.
- The **slow-sampled counter** trick (resample a jittery number every N frames so a human
  can read it) applies directly to any lag/frame-time readout Oracle shows.

**68000 feasibility:** the stamp is `dc.b` data. Free.

---

### 10. `math_approach` / `math_wrap` / `sin256` as named primitives
**Harmony:** `scripts/math_util/math_util.gml:19` (`math_approach`), `:34` (`math_wrap`),
`:94-129` (`sin256`/`cos256` + `__trig256_build`).

**Ours:** `engine/system/` has math routines; move-toward and menu-wrap are expressed
inline. Our sine tables are build-time generated.

**Verdict: [MOSTLY ALREADY HAVE], one confirmation worth banking.** `math_approach` and
`math_wrap` are one-macro conveniences — take them if the inline sites are numerous,
otherwise ignore. The genuinely useful artifact is `__trig256_build`
(`math_util.gml:118-129`): an independent, modern re-derivation of the Mega Drive's
256-entry amplitude-256 sine table *including* the `*512` → truncate-toward-zero → `>>1`
rounding and the four hard-corrected cardinal entries (indices 0/64/128/192 forced to
0/256/0/-256). Worth diffing against our generator's output — if ours differs at those four
entries or in rounding direction, one of us is wrong, and Harmony's version is the one
that was checked against real hardware behaviour.

**68000 feasibility:** this is *already* the 68000 approach; Harmony back-ported it.

---

### 11. Easing curve set
**Harmony:** `scripts/ease_util/ease_util.gml:5-296` — 30 Penner curves.

**Verdict: [WORTH TAKING — Aeon, heavily reduced].** Do not port 30 curves. Ship 4-6
build-time-generated 128-entry 8.8 LUTs (out-quad, in-out-quad, out-back, out-bounce,
out-expo, in-out-sine) behind a single `Ease(curve_id, t)` indexed lookup. Total cost
~1.5 KB ROM. Uses: title card slides, HUD entry, camera transitions, menu highlights,
signpost, act-clear — everything with a scripted motion curve.

**68000 feasibility:** LUT lookup only. Runtime evaluation is impossible under our no-`mulu`
/no-`divu`/no-float rules; the table is the only correct shape. Generation is build-time
Python, which is the pattern we already use for sine and parallax tables.

---

### 12. Convention-discovered command/metadata registry
**Harmony:** `objects/obj_shell/Create_0.gml:117-151` — scan all globals, `sh_*` becomes a
command, `meta_*` supplies its help and per-argument suggestions; hidden flag in the
metadata suppresses a command from autocomplete (`:136-143`).

**Verdict: [WORTH TAKING — Oracle, as build-time generation].** The runtime reflection is
impossible for us and unnecessary. The transferable idea is **one declaration site per
command that carries both the implementation and its help/argument metadata**, with the
registry generated rather than hand-maintained — Oracle's MCP tool surface is large enough
(90+ tools in the deferred registry) that a single-source-of-truth declaration with
generated schemas is worth it if it is not already the case. Low priority; likely already
solved.

---

### 13. Suspend-the-world with an explicit exemption allowlist
**Harmony:** `objects/obj_global/Step_1.gml` — when `global.process_objects` is false,
snapshot every instance, `instance_deactivate_all(true)`, then re-activate only
`[obj_dev, obj_shell, obj_pause, obj_dev_menu]`; `Step_2.gml` re-activates everything for
the draw pass and clears the list.

**Verdict: [REJECT — wrong shape for us].** Our frame is a fixed sequence of subsystem
calls, not a bag of self-scheduling instances, so "pause everything except these four
objects" has no analogue and no cost we need to avoid: a pause is a game-state change plus
skipping the object-run and physics phases. The allowlist exists because GameMaker's
deactivation is all-or-nothing; ours does not need one. The one transferable sliver is that
a pause must **not** stop the sound driver, the DMA queue drain, or the debug hooks — which
our architecture gets for free by structure. Noted, not taken.

---

### 14. Global "collected/destroyed" list keyed by instance id
**Harmony:** `objects/obj_ring/Step_0.gml:24`, `objects/obj_monitor/Step_2.gml:80`,
`objects/par_badnik/Step_0.gml:29` write `global.store_object_state[| id] = true`; creates
and room-starts check it (`obj_ring/Create_0.gml:12`, `obj_badnik_ribbot/Other_4.gml`);
cleared on death (`player_state_knockout.gml:66,83,134,151`) and on `level_reset_data()`.

**Verdict: [ALREADY HAVE — and ours is better].** Ours is the 3×3 rolling collected/killed
bitmask window (ARCH §4.9.5): 9 slots × 34 bytes, keyed by `(section_id, list_index)`, with
explicit eviction semantics and a documented, deliberate persistence depth of one section of
backtrack. Harmony's is an unbounded list keyed by a runtime instance id, which cannot
survive a room reload and whose memory grows with play. The one thing Harmony makes explicit
that we should keep explicit: **the scope at which this memory is cleared is a design
decision** (theirs = death or checkpoint reset). Ours is spatial (3×3 eviction) rather than
event-based; both are defensible, but the interaction of the two (does dying clear the
collected window?) is worth confirming is decided, not incidental.

---

### 15. Culling by spawn position vs current position, as separate opt-in flags
**Harmony:** `scripts/game_enums/game_enums.gml:64-68` (`CULL_FLAG.CHECK_ENTITY_POS` /
`CHECK_ENTITY_START`), evaluated at `objects/obj_level/Step_2.gml:27-38`;
`objects/par_moving_platform/Create_0.gml:14` registers START-only,
`objects/obj_badnik_wheeltank/Create_0.gml:22` registers both.

**Verdict: [ALREADY HAVE — different expression].** Our `OEF_ANY_Y` (ARCH §4.9.2) plus
section-lifetime governance covers the same need: an object whose behavior takes it far from
its spawn point does not despawn merely because it wandered. Harmony's version is more
general (independent X and Y, both axes, per-instance) but also costs a per-frame double
rectangle test for every registered object. Ours is a single ROM flag bit mirrored into
`SST_slot_tag` bit 7 and tested with one `btst`. No change warranted — but if a future object
needs "despawn by origin, not by current position" on the **X** axis, note that our design
currently only has the Y exemption.

---

### 16. Animator conveniences: `dont_reset_frame`, clamp-short duration arrays, `loop_frame`
**Harmony:** `scripts/animator_util/animator_util.gml:153,168` (`dont_reset_frame`),
`:40-53` (per-frame duration array with `min(frame, len-1)` clamp), `:75`
(`animation_loop_frame` as the loop target).

**Verdict: [ALREADY HAVE — 2 of 3; 1 worth checking].** `loop_frame` ≈ our `$FE` jump-back
control code. Per-frame durations exist in `AnimateSprite_PerFrame`. **`dont_reset_frame`
is the one to check**: changing animation without resetting the frame counter matters for
matched-cadence transitions (walk↔run, idle↔breathe). Our `prev_anim`/`prev_frame = $FF`
change-detection convention (ARCH §3.7 step 3) implies a reset on every animation change; if
so, a "preserve phase" variant is a small, real addition. Everything else in
`animator_util.gml` is a subset of our behavior sequencer (§3.6).

---

### 17. Room-creation-code as a per-level manifest
**Harmony:** `rooms/rm_arboreal_agate1/RoomCreationCode.gml` — a `with(obj_level){ … }`
block setting `stage_music`, `stage_name`, `act`, `act_transition`, `animal[]`,
`next_level`, overriding the defaults in `objects/obj_level/Create_0.gml:9-32`;
`rooms/rm_template/` is the copy-me starter.

**Verdict: [ALREADY HAVE — ours is strictly better].** Our `implement Game` manifest is
typed, its members are checked at bind time, unbound hooks cost zero bytes, and
`ensure(extern("NAME") == NAME, ...)` walls catch mismatched game-side constants at build
time (ARCH "Engine/game contract"). Harmony's has no types and no required-member checking —
a level that forgets `stage_name` silently inherits `"Empty Level"`. The two things Harmony
does that we should confirm we match: (a) a **`rm_template` copy-me starter** — our
`games/demo/` plays this role and plays it better, since it is also a CI-enforced
agnosticism regression; (b) a **documented default for every field**, so a partially-filled
manifest is legible rather than mysterious.

---

### 18. `file_bin_util` binary I/O helpers
**Harmony:** `scripts/file_bin_util/file_bin_util.gml` — 95 lines of big-endian int8/16/32
read/write. Zero callers. `int16` sign-extension bug at `:39` (`- 65535`).

**Verdict: [REJECT — dead code, and the problem it was for is already solved better].**
Its evident purpose (cache the baked collision height maps to a binary file rather than
recomputing at boot, cf. the commented-out `game_tile_file_save()` in
`scripts/game_init_collision/game_init_collision.gml`) is a problem we do not have: our
collision is embedded in the block strips at build time (ARCH §4.7, §8.1 step 5). Nothing to
take.

---

### 19. `instance_recorder` — circular per-variable value history
**Harmony:** `scripts/instance_util/instance_util.gml:285-345` — register
`(instance, variable_name)` pairs, ring-buffer N frames of each, read back with a frame
offset. Zero callers.

**Verdict: [REJECT for Aeon — WORTH NOTING for Oracle].** In-ROM it is a solution looking
for a problem (its intended use, trailing afterimages, we would do with a sprite cache).
But the *debugging* form — "record the last N frames of these named RAM addresses and let
me scrub back" — is a real emulator feature, adjacent to Oracle's existing watchpoints and
input-replay net, and would directly serve the recurring "verify during motion" problem.
Low priority; listed for completeness rather than recommended.

---

### 20. `math_pinhole_scale` — perspective projection helper
**Harmony:** `scripts/math_util/math_util.gml:73-88` — `1/(1+z)` pinhole projection.

**Verdict: [REJECT].** Requires a divide; nothing in a section-streaming Sonic engine needs
perspective projection; a reciprocal LUT would make it possible but there is no consumer.

---

## SUMMARY TABLE

| # | Idea | Verdict | Cost |
|---|---|---|---|
| 1 | Mouse-picked command arguments (click → world coord / object) | WORTH TAKING — Oracle | host-side, medium |
| 2 | Placeable scripted-event trigger primitive | WORTH TAKING — Aeon + Aurora | small ROM, real editor work |
| 3 | In-ROM dev menu: level select + live tunables | WORTH TAKING — Aeon (DEBUG) | small (select) / medium (tunables) |
| 4 | Slow-motion + fast-forward playback | WORTH TAKING — Oracle | host-side, small |
| 5 | On-despawn callback per archetype | WORTH TAKING — Aeon, on demand | 2-4 B/ObjDef |
| 6 | Curated prose-commented user config file | WORTH TAKING — Aeon | zero bytes |
| 7 | Named waypoints + warp-to-waypoint | WORTH TAKING — Aurora + Oracle | host-side |
| 8 | Entity-window / culling visual overlay | WORTH TAKING — Oracle | host-side, medium |
| 9 | Build-identity stamp in ROM, displayed by Oracle | WORTH TAKING — Aeon + Oracle | ~12 B |
| 10 | `math_approach`/`math_wrap`; verify `sin256` rounding | MOSTLY ALREADY HAVE | trivial |
| 11 | Easing curves as build-time LUTs (4-6, not 30) | WORTH TAKING — Aeon | ~1.5 KB ROM |
| 12 | Single-declaration command+metadata registry | WORTH TAKING — Oracle, low prio | — |
| 13 | Suspend-world with exemption allowlist | REJECT — wrong shape | — |
| 14 | Global collected/destroyed list | ALREADY HAVE (ours better) | — |
| 15 | Cull by spawn-pos vs current-pos flags | ALREADY HAVE (different) | — |
| 16 | Animator: `dont_reset_frame` (check ours) | ALREADY HAVE ×2, check ×1 | small |
| 17 | Per-level manifest via room creation code | ALREADY HAVE (ours better) | — |
| 18 | `file_bin_util` binary helpers | REJECT — dead + solved better | — |
| 19 | Value recorder | REJECT (Aeon) / note (Oracle) | — |
| 20 | Pinhole projection | REJECT | — |
