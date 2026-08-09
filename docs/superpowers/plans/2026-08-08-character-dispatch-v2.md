# Character Dispatch + Tails & Knuckles Implementation Plan — v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **v2 provenance (2026-08-08).** This re-anchors the banked 12-task plan (`2026-07-02-character-dispatch.md`, now SUPERSEDED) against the live tree, which predates neither the Sigil flip nor the engine/game split when the original was written. Every `.asm` path, `main.asm` include, `struct`/`ram.asm` reference, and build command has been translated to the `.emp`/Sigil/`map.toml` world and every file:line the original cited has been re-verified against the working tree (branch `feat/art-streaming-p2`, the pre-merge state — see the branch/merge note below). A cold session needs ONLY this file plus the spec `docs/superpowers/specs/2026-07-02-character-dispatch-design.md` (APPROVED; asset sourcing = skdisasm). Where a cited mechanism has since changed, the drift is corrected inline and called out with **DRIFT:**; four spec claims no longer hold against the live tree and are flagged **SPEC-STALE:** for controller attention (collected in the self-review).

**Goal:** One shared movement core driving a three-character roster — a `CharacterDef` data record + one ability-hook vector; Tails (flight, appendage child, CPU follower), Knuckles (glide/slide/climb/ledge); stock S3K assets converted from skdisasm.

**Architecture:** C1 (Tasks 2-4): `CharacterDef` + per-slot globals + `Camera_Target` + P2-correctness audit, gated by a recorded-input regression (the existing replay net) proving Sonic byte-identical. C2 (Tasks 5-7): S3K asset conversion, `tails.emp`, `PSTATE_FLY`, the appendage child. C3 (Task 8): CPU input filter with AIR quality fixes. C4 (Tasks 9-11): Knuckles assets + glide/slide/climb/ledge. Task 12: docs + merge. Spec: `docs/superpowers/specs/2026-07-02-character-dispatch-design.md`.

**Branch / merge context (READ FIRST):**
- **This plan executes AFTER `feat/art-streaming-p2` merges to master.** Art-streaming P2 inserts engine RAM (page-frame cache + staging), so `Engine_RAM_End` (engine/ram.emp:617) moves and the game RAM chained after it (`game_ram @ after(upper_ram)`, config/ram.emp:21) rebases. **Every RAM anchor in this plan must be re-pinned against post-merge master** — the line numbers below are pre-merge (`feat/art-streaming-p2`) and Task 1's research step re-reads them fresh.
- Art-streaming P2's residency cache also changes the **VRAM art budget** that Task 5 draws the follower/appendage DPLC regions from (see Task 5 Step 3): if P2 residency has landed, take page frames; otherwise carve static slots below the 960 FG ceiling.
- **Branch name: `feat/character-dispatch`** (off a clean post-merge master; the original's `feat/character-roster` is retired).
- **Parallel asset-prep lane:** a separate agent is extracting the S3K Tails/Knuckles assets + regenerating DPLCs through the fixed 16-tile-split path, staging the reproducible output (plus its generation script) at **`games/sonic4/data/characters_staging/`** (does not exist yet on this branch). This plan's asset tasks (5, 9) **consume + verify + integrate** that staged output as the primary path, with the from-scratch conversion kept as an explicit fallback.

**Tech Stack:** 68000 assembly in the `.emp` tree (Sigil — `DEBUG=1 ./build.sh` drives the Sigil build; there are no `.asm` twins). Python asset converters in `tools/` (`convert_s2_mappings.py`, `dplc_layout.py` exist; `convert_s3k_char.py` is new). skdisasm asset source (`/home/volence/sonic_hacks/skdisasm/General/Sprites/{Tails,Knuckles}/`). oracle emulator MCP (controller-only).

---

## Standing rules for every task

**The `.emp` world (this is not the pre-Sigil tree the original plan assumed):**
- All player code is `.emp` under `games/sonic4/player/` — `player_common.emp`, `sonic.emp`, `player_ground.emp`, `player_air.emp`, `player_spindash.emp`, `player_sensors.emp`. There is NO `player_common.asm` and NO `games/sonic4/main.asm`. `player_common.emp` OWNS the player frame outright (the PlayerV overlay, `Player_Main`, `Player_SetState`, the state/hook tables). Character data (`sonic.emp`) contributes asset/physics data only, never forks inside shared routines.
- **ROM placement is `games/sonic4/map.toml`, not `main.asm` includes.** Every new byte-emitting section (each `proc`/`data` head-label in a new `.emp` module — `characters.emp`, `tails.emp`, `knuckles.emp`, `player_fly.emp`, `player_glide.emp`, `player_climb.emp`, `tails_cpu.emp`, `tails_appendage.emp`, and the new character data modules) must be added to `map.toml`'s `order` list (map.toml:43-66) in its correct union position — near the existing player entries (`Player_Init`, `PState_Ground`, `PState_Air`, `PState_Spindash`, `Sonic_InitAssets`) for code, near `Ani_Sonic`/`Map_TestObj` for data. The registry/pins/golden side is sigil-owned — coordinate with the sigil session.
- **Character asset DATA is `pub data` from `embed(...)`, not `BINCLUDE`.** Precedent: `Map_Sonic`/`DPLC_Sonic`/`Art_Sonic` are declared in `games/sonic4/data/collision/collision_data.emp:24-26` from embedded `.bin`s (with signed-word-offset `ensure` guards). Animation tables are `offsets` blocks with ordinal-drift `ensure`s: `Ani_Sonic` is in `games/sonic4/data/animations/sonic_anims.emp:33`. New character data modules mirror these forms.
- **RAM:** game RAM lives in `games/sonic4/config/ram.emp` (`pub vars game_ram @ after(upper_ram) .. SYSTEM_STACK, w_addressable`); it chains from `Engine_RAM_End`. New player globals (`Character_ID`, per-slot `Player_Phys`/quadrant/jump-buffer, `Camera_Target`, `Player_Inputs`, CPU-AI globals) go here as typed `vars`. DEBUG-only counters go in the `if DEBUG == 1 @shape_divergent { }` group (config/ram.emp:26). `pad(1)` after any odd `u8` run to keep the following words even. Alignment/overlap/`w_addressable` are compiler checks now.
- **Structs:** `CharacterDef` and the `PageFrame`-style records go in `engine/structs.emp` (engine-owned type twins) OR a game struct module if character-specific — `sizeof` is compiler truth, no manual `_len` constants. The SST overlay `PlayerV` lives in `player_common.emp` (`pub vars PlayerV: Sst.sst_custom { ... }`, player_common.emp:72). Field access is by name (`PlayerV.field(a0)`).

**SST budget — the sequencing rule is RESOLVED (do not re-derive it):**
- **SPEC-STALE / DRIFT:** the spec §4 + original standing rules say "check `structs.asm` FIRST — 16 free at `sst_custom=$30` if floating-origin F2 landed, else 18 at `$2E`." **This is already resolved by the sst-fold (2026-08-05).** The live `Sst` (engine/objects/sst.emp:26) is `(size: $50)` with `frame_off @ $2E` and `sst_custom: [u8; 32] @ $30` (window `$30-$4F`); the tail word `$4E-$4F` is engine-owned `SST_interact` → **30 game-usable custom bytes.** `PlayerV` (player_common.emp:72-90) currently uses **18 bytes** (the "18 of 34" comment at :65 is itself stale on the "34" — it is 18 of 30 usable now), so there are **12 free bytes.** The floating-origin-F2 metadata relayout the spec worried about **has already happened** (frame_off moved $50→$2E in the fold). There is no pending `section_id` relayout to sequence against. Re-verify the current `PlayerV` size against post-merge `player_common.emp` at Task 1 and record the real free count; every PlayerV growth below asserts headroom against it.

**Build shapes:**
- Plain `./build.sh` → `s4.bin` with **sound ON** (default since the engine/game split). `DEBUG=1 ./build.sh` → **suffixed** `s4.debug.bin` / `s4.debug.lst`. DEBUG carries asserts/self-tests; a plain build proves nothing about them. **Character hotkey testing additionally needs `SOUND_DEBUG_HOTKEYS=1`** if you drive the sound-test hotkeys too — but the character-select hotkey is a DEBUG-only addition to the game debug hook (see Task 6 Step 4), independent of the sound axis. Oracle symbol cross-checks use `s4.debug.lst`. Never plain-`./build.sh` in a shared hot tree mid-session without byte-verifying the loaded ROM afterward.

**The byte-changing-parcel ritual (rides EVERY aeon byte-emitting change):**
- `SIGIL_BLOB_LEN_DRIFT=warn`, rebuild BOTH sigil binaries, repin → refreeze `--ab`. `pins.rs` is a gate, not an input. **THREE test gates on every byte-changing task:** (1) hand-type the `repin_pins.rs` baseline (historically the missed step), (2) `native_full_rom` + any touched port-test anchors green, (3) `pins_rs_is_current` + `refreeze --check`. Sigil commits land on sigil master. Coordinate the registry/golden side with the sigil session. Do NOT invent waiver hacks — if a gate cannot be made green, pause for controller coordination.

**Verification & emulator:**
- **Every oracle/emulator step is CONTROLLER-ONLY (⚠ controller).** The emulator MCP from a subagent deadlocks the arbiter; the foreground controller session does ALL oracle work. Subagents build, edit, and reason — they never touch oracle.
- Verification is oracle-observed behavior, never build-success alone. **Verify player behavior DURING motion** (at-rest screenshots hide scroll/animation artifacts): drive circuits, watch RAM live. Oracle gotchas current 2026-08-05: absolute-path `reload_rom` + crc-verify, `press` not `hold`, `pgrep -a`; oracle symbols go stale after `reload_rom` — cross-check against fresh `s4.debug.lst`.

**The regression net — use the SHIPPED replay system, not a hand-written press script:**
- **DRIFT:** the original Task 1 built a scratchpad `emulator_press` capture script. The tree now has a deterministic input-replay net: `Input_Tick` (the `GameLoop` replay seam, game_loop.emp:31), `Input_Source` = `INPUT_LIVE`/`INPUT_PLAYBACK`/`INPUT_RECORD` (engine/ram.emp:167), the replay engine `engine/system/replay.emp`, packer `tools/replay_pack.py`, and two fixtures: `Replay_OJZ_Fixture` (standing) + `Replay_OJZ_Slide_Fixture` (section-crossing + vertical fly), both in `games/sonic4/test/replay_fixture.emp` from `games/sonic4/data/replays/*.bin`. The C1 regression uses `INPUT_PLAYBACK` of these fixtures — deterministic by construction — and captures the player SST + camera at checkpoints via oracle memory reads. This is stronger than a fresh press script and already built.

**Daemon-watched files — NOT touched by this plan:**
- The auto-commit daemon watches `tools/ojz_strip_gen.py` and `games/sonic4/data/editor/ojz/`. **No task in this plan edits either.** The new converter `tools/convert_s3k_char.py` and the staged `games/sonic4/data/characters_staging/` are NOT in the daemon's watch set. If any task turns out to need an edit under those two watched paths, STOP and ask the user first; never `--amend` near them.

**Git:**
- `git add` exact paths only (never `-A`/globs). Commit per green task. Branch `feat/character-dispatch` off a clean post-merge master; merge to master ONLY at Task 12 (merge commit, repo habit). **Verify `git branch --show-current` before EVERY commit** (parallel sessions share the tree).

**Law:** `CODING_CONVENTIONS.md` is the law of the codebase — read it before writing any `.emp`. `.s`/`.w`/`.l` on every branch/jump; `function`/comptime for all build-time math; typed struct literals; PascalCase routines/globals, ALL_CAPS constants, `.lowercase` locals; no `mulu`/`divu`.

---

### Task 1: Branch + the input-replay regression baseline

**Files:** none created (scratchpad numbers only).

- [ ] **Step 1: Research.** Read the spec end-to-end. Read the live player surfaces fresh (re-pin every anchor — these are `feat/art-streaming-p2` lines; re-read on post-merge master):
  - `games/sonic4/player/player_common.emp` in full — the PlayerV overlay (:72-90), `Player_Init` (:192), `Player_RefreshPhysics` (:233), `Player_Main` (:255), `Player_Display` (:377), `Player_Animate` (:398, the ball test :420-421), `Player_SetState` (:553) + the enter/exit hook tables (`PState_EnterHooks` :570, `PState_ExitHooks` :585) and hooks (:601-682), `Player_LevelBound` (:784), the debug-fly trio (:851-909). **The four hardwired Sonic sites** (see DRIFT below).
  - `games/sonic4/player/sonic.emp` — `Sonic_InitAssets` (:24), `Sonic_LoadArt` (:39), `PhysTable_Sonic` (:58, with the `extern("Player_Phys_End") - extern("Player_Phys")` size ensure :68).
  - `games/sonic4/player/player_air.emp` — `PState_Air`/`PState_AirBall`/`PState_RollJump`/`PState_Jump` (:58-68), `PState_AirShared` (:76), the variable-jump-height HELD block (:99-125). This is where the ability hook lands (Task 3).
  - `games/sonic4/player/player_ground.emp` (jump init sets `PSTATE_JUMP` at :838), `player_spindash.emp`, `player_sensors.emp` headers.
  - `games/sonic4/config/constants.emp` — `PSTATE_*` (:56-65, the ordering `ensure` :64), `ANIM_*` (:71-82, `ANIM_COUNT` :82), `CHEAT_*` (:38), VRAM allocation (`VRAM_TEST_SONIC = $3C0` :130, `VRAM_TEST_OBJ` :117, `VRAM_TEST_MARKER` :126).
  - `games/sonic4/config/ram.emp` — `game_ram` region (:21), `Player_Phys` block (:50-59), `Player_Quadrant`/`Player_JumpBuffer` (:61-62), the rings (:80-83), `Game_RAM_End` (:84), the `@shape_divergent` DEBUG group (:26).
  - `engine/ram.emp` — `Engine_RAM_End` (:617), `Player_1`/`Player_2` SST slots (:305-306), `Object_RAM` (:303), `Camera_X`/`Camera_Y` (:347-348), the replay state block (`Input_Source` :167, `Replay_Ptr` :173).
  - `engine/objects/sst.emp` — `Sst (size: $50)` (:26), `frame_off @ $2E` (:73), `sst_custom @ $30` (:82), `interact_off()` (:96), `set_priority_band` (:168).
  - `engine/level/camera.emp` — `Camera_Update` (:199), the two `lea Player_1` follow sites (:228 x, :292 y), the `PL_STATE_ADDR` state probe (:70 def, :329 use), the `CAM_MAX_X_STEP` file-local const (:21) and the `pstate_jump_mirror_ok` mirror (:47-57).
  - `games/sonic4/objects/path_swap.emp` — `lea Player_1` at :84 (`PathSwap_Init`) and :101 (`PathSwap_Main`).
  - `engine/objects/collision.emp` — `TouchResponse` player loop (:112, `.player_loop` :120), the per-player `bclr #ST_ON_OBJECT` (:133), `Touch_Solid`'s `bset #ST_ON_OBJECT` (:289). **See SPEC-STALE on the P2 bit below.**
  - `engine/objects/dplc.emp` — `Perform_DPLC` (:97, `proc (a0: *Sst, a2: *u8, a3: *u8, d1: u16) clobbers(d0-d4/a1-a2)`).
  - `engine/objects/children.emp` — `CreateChild_Normal` (:148, the live creator), `CreateChild_FlipAware` (:341, **`@scaffolding` — zero call sites**), `DeleteChildren` (:555), `PopulateSpawnedPieceCount` (:114).
  - `engine/system/replay.emp` + `games/sonic4/test/replay_fixture.emp` + `tools/replay_pack.py` — the regression net.
  - `games/sonic4/debug/game_debug.emp` — `Debug_MusicToggle` (:67) is the game's `debug_tick` impl; buttons A/B/C/UP/START are already claimed (for the character-cycle hotkey in Task 6, pick a free combo).

  **DRIFT — the four hardwired Sonic dispatch sites** (the spec's cited `player_common.asm:119/154/259/405` no longer exist; the live sites are):
  1. `Player_Init` → `jbsr Sonic_InitAssets` (player_common.emp:193)
  2. `Player_RefreshPhysics` → `lea PhysTable_Sonic, a1` (player_common.emp:234)
  3. `Player_Display` tail → `jbra Sonic_LoadArt` (player_common.emp:380)
  4. `Player_DebugExit` → `jbsr Sonic_InitAssets` (player_common.emp:869)
  plus the character immediates inside `Sonic_InitAssets` (`Map_Sonic`, `VRAM_TEST_SONIC`, `Ani_Sonic` — sonic.emp:25-27) and `Sonic_LoadArt` (`DPLC_Sonic`, `Art_Sonic`, `VRAM_TEST_SONIC` — sonic.emp:40-42).

- [ ] **Step 2: Branch.** `git checkout -b feat/character-dispatch` from a clean post-merge master (verify `git branch --show-current` = master first; confirm `feat/art-streaming-p2` has already merged — if not, STOP and coordinate).
- [ ] **Step 3: Baseline. ⚠ controller.** Build `DEBUG=1 ./build.sh`; load `s4.debug.bin` in oracle (absolute path + crc-verify). Drive the regression via the replay net: set `Input_Source = INPUT_PLAYBACK`, `Replay_Ptr = Replay_OJZ_Fixture + REPLAY_HEADER_LEN` (the poke recipe is in replay_fixture.emp's header note), run to `Replay_Done`. At fixed checkpoints (every 30 ticks, and at each fixture checkpoint) capture to scratchpad `baseline_trajectory.tsv`: `Player_1` `x_pos`/`y_pos`/`ground_speed`/`player_state`/`status`, and `Camera_X`/`Camera_Y`. Repeat with `Replay_OJZ_Slide_Fixture` → `baseline_slide.tsv`. Also record `Lag_Frame_Count` over each run. **These are the C1 gate oracle** — Task 4 re-runs and diffs (must be byte-identical). Record the current `PlayerV` byte count + free bytes (the SST-budget rule).

### Task 2: C1a — CharacterDef + Character_ID + the four dispatch sites

**Files:**
- Create: `games/sonic4/player/characters.emp` (the `CharacterDefs` index table + `CharDef_Sonic`) + its head-labels (`CharacterDefs`, `CharDef_Sonic`) into `games/sonic4/map.toml` `order` (near `Sonic_InitAssets`).
- Modify: `games/sonic4/player/sonic.emp`, `games/sonic4/player/player_common.emp` (the four sites + `PlayerV`), `engine/structs.emp` (the `CharacterDef` struct), `games/sonic4/config/constants.emp` (`CHAR_*`), `games/sonic4/config/ram.emp` (`Character_ID`).
- Parcel ritual on all byte-emitting changes.

- [ ] **Step 1: Research.** Re-verify the four sites (DRIFT list in Task 1) and the exact `Player_RefreshPhysics` copy loop (player_common.emp:234-240 — four `move.l` copies of the 8-word row). Read `Perform_DPLC`'s register contract (dplc.emp:97). Read how the `PlayerV` overlay's window-overflow check subsumes the old `objvarsCheck` (player_common.emp:65-71). Read `Sst.mappings`/`art_tile`/`anim_table` field types (sst.emp:43-49) so the def's pointer fields carry matching `engine.types` annotations.
- [ ] **Step 2: The struct + Sonic's def.** In `engine/structs.emp` (typed literal; `sizeof` is truth):

```
// engine/structs.emp
pub struct CharacterDef {
    cd_phys:      u32,          // -> 8-word physics row (PhysTable shape)
    cd_mappings:  u32,
    cd_dplc:      u32,
    cd_artbase:   u32,
    cd_animtable: u32,
    cd_ability:   u32,          // jump-press hook, called from the air state
    cd_vrambase:  u16,          // tile index (vram_bytes applied at use)
    cd_stand_wh:  u16,          // W<<8|H stand radii
    cd_roll_wh:   u16,          // W<<8|H roll radii
    cd_flags:     u16,          // reserved capability bits
}
```

  ```
  // games/sonic4/config/constants.emp
  pub const CHAR_SONIC    = 0
  pub const CHAR_TAILS    = 1
  pub const CHAR_KNUCKLES = 2
  // games/sonic4/config/ram.emp  (game_ram vars; word for clean index math)
  Character_ID:  u16,
  ```

  `characters.emp`: `pub data CharacterDefs` = an index table `[CharDef_Sonic, CharDef_Tails, CharDef_Knuckles]` (the latter two point at `CharDef_Sonic` until C2/C4, each tagged `// TEMP roster stub`). `CharDef_Sonic` is a typed `CharacterDef` literal filled from today's Sonic immediates: `PhysTable_Sonic`, `Map_Sonic`, `DPLC_Sonic`, `Art_Sonic`, `Ani_Sonic`, `Ability_None` (an `rts`), `VRAM_TEST_SONIC`, `(PLAYER_X_RADIUS*2+1)<<8 | (PLAYER_Y_RADIUS*2+1)` for stand (= 19<<8|39 in full-size bytes — but keep the classic convention the code uses: the def carries the SAME width/height bytes `set_standing_size` writes, so read those constants, do not hardcode), roll `(BALL_X_RADIUS*2+1)<<8|(BALL_Y_RADIUS*2+1)`, flags 0.
- [ ] **Step 3: Cache the def per slot + convert the four sites.** Add a `PlayerV` long field `chardef: u32` (grows PlayerV 18→22 — **assert headroom** against the Task-1 free count; 12 free → 8 remain). `Player_Init` resolves `Character_ID` → `CharacterDefs[id]`, stores the pointer in `PlayerV.chardef(a0)`, then:
  - `Sonic_InitAssets` becomes a shared `Player_InitAssets` reading `cd_mappings`/`cd_vrambase`/`cd_animtable` from the def (a1 = def ptr).
  - `Player_RefreshPhysics` loads the source row from `cd_phys` via the def instead of the hardwired `lea PhysTable_Sonic` (it must obtain the def — either a param or re-resolve from `Character_ID`; pick and comment, favor the def ptr since `Player_Init` cached it).
  - `Player_Display`'s tail becomes a shared `Player_LoadArt` reading `cd_dplc`/`cd_artbase`/`cd_vrambase` (replaces the hardwired `jbra Sonic_LoadArt`).
  - `Player_DebugExit`'s `Sonic_InitAssets` call routes through the shared `Player_InitAssets`.
  - The `PState_Spindash` row stays shared (roster-shared — only the header comment updates).
  - `sonic.emp` shrinks toward data: `PhysTable_Sonic` + the def-referenced labels stay; the two procs fold into the shared loaders (keep thin Sonic-named wrappers only if a caller still needs the symbol — grep first).
  **Keep the enter-hook radii mechanism intact** (`set_standing_size`/`set_ball_size` are comptime splices, player_common.emp:129-141); the def's `cd_stand_wh`/`cd_roll_wh` are consumed later (Task 6/9 for per-character sizes) — this task Sonic's def values equal what the splices write, so behavior is unchanged.
- [ ] **Step 4: Build + boot + quick circuit. ⚠ controller.** `DEBUG=1 ./build.sh` green (parcel ritual done); Sonic plays normally by hand-feel and via a quick replay-fixture spot-run. The formal gate is Task 4. Commit: verify branch. `feat(player): CharacterDef data dispatch — Sonic through the roster path (C1)`.

### Task 3: C1b — per-slot globals, ability hook, Camera_Target, P2 audit

**Files:**
- Modify: `games/sonic4/player/player_common.emp`, `games/sonic4/player/player_air.emp`, `games/sonic4/player/player_ground.emp`, `games/sonic4/player/player_spindash.emp`, `games/sonic4/config/ram.emp`, `games/sonic4/config/constants.emp`, `engine/level/camera.emp`, `games/sonic4/objects/path_swap.emp`, `engine/objects/collision.emp` (audit only — see SPEC-STALE).
- Parcel ritual.

- [ ] **Step 1: Research.** Grep every reader of `Player_Phys`/`Player_Quadrant`/`Player_JumpBuffer` (the physics table is read via `lea Player_Phys, a4` at player_common.emp:290 and `a4`-relative `PPHYS_*` in the state code; quadrant at player_common.emp:298 write + player_sensors reads; jump-buffer written player_common.emp:330-335, consumed in player_ground). Grep every `lea Player_1` outside player files (found: camera.emp:228/292, path_swap.emp:84/101, rings.emp:267, core.emp:475/620, collision.emp:116 — classify each as leader-follow vs whole-roster-loop). Enumerate all `PSTATE_JUMP` ball-test compares (player_common.emp:420-421; camera's mirror at :330 is a landing-lock test on JUMP/ROLLJUMP specifically, NOT the curled set — unaffected by the rework, but note it).
- [ ] **Step 2: Per-slot globals.** In `config/ram.emp`, `Player_Phys` becomes `Player_Phys_Slots: [u16; 8*NUM_PLAYERS]` (keep the `mark Player_Phys`/`mark Player_Phys_End` pair pointing at slot 0 so `PhysTable_Sonic`'s size `ensure` still resolves — or update the ensure). `Player_Main` computes the slot's physics base into a4: derive the slot index from `(a0 - Object_RAM)/sizeof(Sst)` OR cache a `PlayerV.slot: u8` set at init (pick the cheaper; a cached byte avoids a divide — comment why). `Player_Quadrant`/`Player_JumpBuffer` become per-slot `PlayerV` bytes (2 bytes; PlayerV 22→24, re-assert headroom). Ring recording (player_common.emp:357-368) gates on leader: `tst.b PlayerV.slot(a0); bne .skip_record` (slot 0 = leader).
- [ ] **Step 3: Ability hook.** In `player_air.emp` `PState_AirShared`, after the on-object early exit (:97) and the variable-jump-height block (:99-125), add a **fresh-press** ability dispatch: read `Ctrl_1_Press`, mask with `BUTTON_JUMP_MASK` under the same `CHEAT_DEBUG_FLY` gate idiom the HELD check uses (player_air.emp:117-123), and on a fresh airborne jump press call the def's ability: `movea.l PlayerV.chardef(a0), a1; movea.l CharacterDef.cd_ability(a1), a1; jsr (a1) as <AbilityHook type>`. Define `Ability_None` (an `rts`) in `characters.emp` or `sonic.emp`. The hook type is a new `type AbilityHook = proc (a0: *Sst) preserves(a0) clobbers(...)` — declare it and give `Ability_None` that shape. Note: the press must not double-fire the SAME press that started the jump — the jump starts on the ground frame (player_ground.emp:838 sets PSTATE_JUMP), so a fresh air-state press on a LATER frame is the ability trigger; verify the press-edge timing (the jump-buffer was consumed on the ground frame).
- [ ] **Step 4: PSTATE curled-set rework.** **SPEC:** replace the `>= PSTATE_JUMP` ball test (player_common.emp:421) with an explicit curled test so C2/C4 states (FLY/GLIDE/SLIDE/CLIMB/LEDGE) can append without the "curled states last" ordering constraint. Add `PSTATE_CURLED_MASK` (a bit-per-state constant, or a small `dc.b` classification table) in `config/constants.emp`, with a build `ensure` it covers ROLL/JUMP/ROLLJUMP/AIRBALL (the currently-curled set — note ROLL is grounded-curled, handled separately in `Player_Animate` at :423, so scope the mask to the states the ball-anim test actually needs). Update the ordering `ensure` at constants.emp:64: it can relax (states no longer must be last) OR stay as a documented invariant for the current set — pick, and comment. Glide/slide are attacking-but-NOT-curled (spec §3), so they are NOT in the curled mask.
- [ ] **Step 5: Camera_Target + path-swap.** Add `Camera_Target: u32` to `config/ram.emp` (game RAM), seeded to `Player_1` at level init. Replace camera's two hardwired `lea Player_1` follow reads (camera.emp:228, :292) and the `PL_STATE_ADDR` state probe (camera.emp:70/:329) with reads through `Camera_Target`. **The `_pl_state` offset stays** — the target is a leader SST pointer; `PL_STATE_ADDR` becomes `Camera_Target + _pl_state`. Replace path_swap's two `lea Player_1` (path_swap.emp:84, :101) with `Camera_Target` (path-swap follows the leader). Leave `rings.emp:267` and the `core.emp`/`collision.emp` whole-roster loops alone (they iterate all players, not follow the leader).
- [ ] **Step 6: P2 correctness — AUDIT, not a fix.** **SPEC-STALE:** the spec §4 + original Task 3 Step 5 claim `collision.asm:205` hardcodes P1 standing/pushing bits (`ST_P1_STANDING`/`ST_P2_STANDING` globals). **This bug does not exist in the from-scratch engine.** Status is a per-SST byte: `TouchResponse`'s `.player_loop` (collision.emp:120) iterates both players with `a2` = current player and sets `ST_ON_OBJECT`/`ST_PUSHING` on `status(a2)` — inherently per-player (bclr :133, bset :289). There are no `ST_P1_*`/`ST_P2_*` global constants (only `ST_PUSHING = 6`, `ST_ON_OBJECT`). **This step is: audit + confirm** the standing/pushing/on-object bits are already per-player across the loop, add a one-line comment recording that the sonic_hack-lineage P1-hardcode bug is structurally absent, and REMOVE this from the behavior-change surface. Do not manufacture a fix. If the audit finds any genuinely P1-hardwired per-player bit, THEN fix it and note the delta — but the expectation is zero changes here.
- [ ] **Step 7: Build + boot + commit. ⚠ controller.** Green; boot; Sonic hand-feel unchanged; quick replay spot-run clean. Verify branch. `feat(player): per-slot physics/quadrant/jump-buffer, ability hook, Camera_Target, curled-set rework (C1)`.

### Task 4: C1 gate — recorded-input regression

**Files:** none (verification only).

- [ ] **Step 1: Re-run the replay net. ⚠ controller.** On the refactored build, replay `Replay_OJZ_Fixture` and `Replay_OJZ_Slide_Fixture` under `INPUT_PLAYBACK`, capturing the same checkpoint columns as Task 1. Diff against `baseline_trajectory.tsv` + `baseline_slide.tsv`: **byte-identical required.** Any divergence = a refactor behavior change — fix before proceeding (usual suspects: physics-copy timing across the per-slot indirection, jump-buffer consumption order once per-slot, quadrant read timing, the ability-hook press edge firing when it should not). Confirm `Lag_Frame_Count` ≤ baseline. Record the diff-clean result + commit hash. Commit: verify branch. `test(player): C1 regression gate passed — roster path is behavior-identical`.

### Task 5: C2a — S3K Tails + appendage assets (consume staged output; convert as fallback)

**Files:**
- Create: `tools/convert_s3k_char.py` (fallback path + pytest), converted outputs staged under `games/sonic4/data/characters/` (mappings/dplc/art/anim bins), new character data module `games/sonic4/data/characters/tails_data.emp` (`embed(...)` → `pub data Map_Tails`/`DPLC_Tails`/`Art_Tails` + the appendage set) + `games/sonic4/data/animations/tails_anims.emp` (`Ani_Tails`/`Ani_TailsAppendage` `offsets` tables).
- Modify: `games/sonic4/map.toml` (`order` entries for the new data head-labels, near `Ani_Sonic`/`Map_TestObj`), `games/sonic4/config/constants.emp` (VRAM placement — Step 3).
- Parcel ritual on byte-emitting changes.

- [ ] **Step 1: Research + locate the staged output.** Check `games/sonic4/data/characters_staging/` for the parallel lane's output + its generation script + a manifest. **If present:** this task is *verify + integrate*, not *extract from scratch*. **If absent:** fall back to the from-scratch converter (Step 2b). Read `tools/convert_s2_mappings.py` (S2→VDP-order mapping format, the piece-format doc in its header) and `tools/dplc_layout.py` (our DPLC format + `split_contiguous_entries` / `MAX_TILES_PER_ENTRY = 16` — the >16-tile entry-split fix, dplc_layout.py:24-32). Read the S3K sources: `skdisasm/General/Sprites/Tails/{Map - Tails.asm, DPLC - Tails.asm, Anim - Tails.asm, Art/}` and the appendage set `{Map - Tails tails.asm, DPLC - Tails tails.asm, Anim - Tails Tail.asm}`. Read `collision_data.emp:24-26` (the `embed` data-module form) and `sonic_anims.emp:33` (the `offsets` anim-table form with ordinal `ensure`s) as the shapes to mirror.
- [ ] **Step 2a: Verify + integrate staged output (primary).** Re-run the lane's generation script into a scratchpad dir; byte-compare against the committed `characters_staging/` bins (reproducibility gate — mismatch = STOP, coordinate with the lane). **Assert no DPLC entry exceeds 16 tiles** (the known overflow trap — memory: DPLC 16-tile overflow fix): parse each `DPLC_Tails`/appendage frame and check every entry's count field ≤ 16; a violation means the data was NOT generated through the fixed split path — reject it. Copy the verified bins into `games/sonic4/data/characters/`, wire them into `tails_data.emp` via `embed(...)`, add signed-word-offset `ensure`s (mirror collision_data.emp:17-18).
- [ ] **Step 2b: Converter (fallback + regression cover).** `tools/convert_s3k_char.py <char>`: parses S3K map/DPLC asm → our VDP-order mappings bin + our DPLC bin (through `dplc_layout` conventions, entry-split for >16-tile frames). Deterministic, pytest-covered (golden frame count + a spot-checked frame + the ≤16-tile assertion as a test). Even when Step 2a succeeds, land this converter so the pipeline is reproducible in-repo.
- [ ] **Step 3: Anim tables (hand-authored).** Anim scripts are NOT machine-converted: author `Ani_Tails` + `Ani_TailsAppendage` in `tails_anims.emp` by hand against our ANIM contract, using S3K's `Anim - Tails.asm` / `Anim - Tails Tail.asm` frame sequences as the source of truth. `Ani_Tails` must have one entry per `ANIM_*` id with ordinal `ensure`s (mirror sonic_anims.emp:59+) — including the FLY/FLY_TIRED ids added in Task 6 (leave placeholders/fallbacks now or add in Task 6; sequence so ANIM_COUNT stays asserted).
- [ ] **Step 4: VRAM placement (resolve before wiring — the one measured decision).** Sonic's DPLC region is `VRAM_TEST_SONIC = $3C0` (tile 960, up to 25 tiles → BG at 1024; constants.emp:127-130). Two simultaneous characters (leader + follower) + the appendage need distinct regions. Measure real needs: max tiles/frame from the converted DPLCs (Sonic ~48, Tails ~40, appendage ~12 — confirm from the actual data). Options in preference order: **(a)** if art-streaming P2 residency has landed, carve the follower + appendage regions from freed page frames; **(b)** if not, carve static slots below the 960 FG ceiling / tighten all char regions. Document the chosen map in `config/constants.emp` with the audit trail (new `VRAM_TAILS`/`VRAM_TAILS_APPENDAGE` consts, each with a clear-of comment like `VRAM_TEST_SONIC`'s). This is the one place the plan defers to measured data.
- [ ] **Step 5: pytest + build (data assembles, nothing consumes yet) + commit. ⚠ controller for the oracle boot check.** `python3 -m pytest tools/ -q` green; `DEBUG=1 ./build.sh` green (new data sections in map.toml `order`); oracle boot still reaches gameplay as Sonic (data present, unreferenced). Verify branch. `feat(tools,data): S3K Tails + appendage assets converted to engine formats (C2)`.

### Task 6: C2b — Tails playable: def + PSTATE_FLY

**Files:**
- Create: `games/sonic4/player/tails.emp`, `games/sonic4/player/player_fly.emp` (PSTATE_FLY) + head-labels into `map.toml` `order`.
- Modify: `games/sonic4/player/characters.emp` (`CharDef_Tails` real; index table entry), `games/sonic4/player/player_air.emp` (the ability entry `Ability_TailsFlight`), `games/sonic4/config/constants.emp` (`ANIM_FLY`/`ANIM_FLY_TIRED` + `PSTATE_FLY`), `games/sonic4/player/player_common.emp` (`Player_States` + enter/exit hook tables + curled-mask), `games/sonic4/data/animations/*` (all character anim tables grow), the game debug hook `games/sonic4/debug/game_debug.emp` (DEBUG character hotkey).
- Parcel ritual.

- [ ] **Step 1: Research.** Re-read spec §5. Read `Player_Animate`'s classifier (player_common.emp:398) to see where flight anims slot (they are airborne, uncurled → they'd hit `.walk_or_run` today; FLY needs its own branch). Check `ANIM_COUNT` asserts across every character anim table (sonic_anims.emp `ensure`s, tails_anims). Read the `PState_EnterHooks`/`PState_ExitHooks`/`Player_States` `offsets` tables (player_common.emp:534/570/585) and the `.count == PSTATE_COUNT` `ensure`s — appending a state means adding a row to all three tables + bumping `PSTATE_COUNT`.
- [ ] **Step 2: `tails.emp`.** `PhysTable_Tails` = Sonic's row verbatim (comment: SPG — Tails ground physics identical; only sizes + ability differ). `CharDef_Tails` (typed `CharacterDef` literal): `cd_phys = PhysTable_Tails`, mappings/dplc/art/vrambase from Task 5's Tails assets + `VRAM_TAILS`, `cd_animtable = Ani_Tails`, `cd_ability = Ability_TailsFlight`, `cd_stand_wh = 9<<8|15`-shaped bytes (match the classic full-size convention the sizing splices use), `cd_roll_wh` per S3K. Point `CharacterDefs[CHAR_TAILS]` at it (remove the TEMP stub).
- [ ] **Step 3: `PSTATE_FLY` in `player_fly.emp`,** S3K-exact per spec §5. Add `PSTATE_FLY` to `config/constants.emp` (append BEFORE the curled states if the ordering `ensure` still constrains — but Task 3's curled-mask rework should have freed that; place per the rework's rule and bump `PSTATE_COUNT`), add its rows to `Player_States` + enter/exit hooks. Body:
  - entry (`Ability_TailsFlight`, the air-state hook): only if airborne-and-not-curled; seed fuel 240, set thrust flag; `Player_SetState` to PSTATE_FLY.
  - thrust: `y_vel -= $20`/frame while `y_vel >= -$100`, 32-frame ramp cap/flap.
  - coast: gravity `y_vel += 8`/frame.
  - fuel: decrement every other frame (`Frame_Counter` parity), ≈8 s; tired = flap disabled ONLY (physics unchanged) + tired anim/sfx cadence (16-frame).
  - **ceiling fix (SPG-documented S3K trap):** on ceiling contact reset thrust→coast gravity (do NOT strand the gravity flip — cite SPG in the comment).
  - top clamp: camera-min + $10.
  - land → ground state via `Player_SetState`.
  - X control: air accel from the phys row (a4), same drag rule as the air state (share/factor the air-X code rather than duplicate).
  - **PlayerV fields:** flight ramp counter + fuel byte — union into the free PlayerV region (per-character overlay; one character per slot). Re-assert headroom.
- [ ] **Step 4: Anims + hotkey.** Append `ANIM_FLY`/`ANIM_FLY_TIRED` to the ANIM contract (constants.emp, bump `ANIM_COUNT`); **every character anim table grows** — Sonic's `Ani_Sonic` gets `Fly`/`FlyTired` rows pointing at safe fallbacks (commented), re-asserted; `Ani_Tails` gets the real rows. DEBUG character-select hotkey: add to the game's `debug_tick` hook (game_debug.emp). Buttons A/B/C/UP/START are taken by the sound test (game_debug.emp:82-155) — use a free combo (e.g. DOWN+START, or a Cheat_Flags-style bit) that does not collide; it cycles `Character_ID` and re-runs `Player_Init` on `Player_1`. Gate behind `DEBUG == 1` (and note it only lives in shapes that bind the game debug hook). Comment the button-collision reasoning like the existing hotkeys do.
- [ ] **Step 5: Oracle flight matrix. ⚠ controller.** Select Tails via the hotkey. RAM-watch `y_vel` at the exact thrust/coast transition velocities; 8 s fuel wall-clock; tired behavior; ceiling fix (fly into an OJZ terrain overhang — no strand); top clamp; land cleanly. Verify DURING motion. Commit: verify branch. `feat(player): Tails playable — CharacterDef + PSTATE_FLY (C2)`.

### Task 7: C2c — the appendage child

**Files:**
- Create: `games/sonic4/objects/tails_appendage.emp` + head-label into `map.toml` `order`.
- Modify: `games/sonic4/player/tails.emp` (spawn at init), `engine/objects/children.emp` (un-`@scaffolding` the chosen creator — see Step 1).
- Parcel ritual.

- [ ] **Step 1: Research.** **DRIFT:** the spec cites `CreateChild_FlipAware (:187)` / `DeleteChildren (:354)`; live anchors are `CreateChild_FlipAware` at children.emp:341 and `DeleteChildren` at :555 — AND `CreateChild_FlipAware` (like `Complex`/`Linked`) carries a `@scaffolding("engine API awaiting its consumer — zero call sites today")` tag (children.emp:340). The appendage is its FIRST consumer, so this task must REMOVE that scaffolding tag from the creator it uses (and only that one). **Decide the creator:** `CreateChild_FlipAware` (spec's choice, gives parent-X-flip mirroring — un-scaffold it) vs `CreateChild_Normal` (:148, already live, no flip mirror). The appendage needs facing-flip tracking, so `CreateChild_FlipAware` is the spec-intended path; confirm its contract (children.emp:341, `clobbers(d0-d4/a1-a2)`) and un-scaffold it. Read `DeleteChildren` (:555) and `parent_ptr` invariant (sst.emp:60-63 — every child writer must link into the parent's sibling chain; the `CreateChild_*` do). Read S3K's `Obj_Tails_Tail_AniSelection` (sonic3k.asm:~30080) for the parent-anim→tail-anim pairs. Pick the object pool: children must never cull while the player lives — read `core.emp`'s pool culling (System/Effect pools are fixed-swept, not window-culled; the entity window culls Dynamic). System pool is the safe choice — confirm children can spawn there.
- [ ] **Step 2: The object.** Spawned by Tails' `Player_InitAssets` path (via `CreateChild_FlipAware` into the non-cullable pool). Per frame: read parent via `parent_ptr` (x/y/angle/status/render_flags/priority); map parent `anim` (SST field :47) through a `TailsApp_AnimMap` `dc.b` table (mirroring S3K's pairs for OUR anim ids); own DPLC via the converted appendage set + `VRAM_TAILS_APPENDAGE`; copy x/y/angle/priority/flip each frame. Deleted with the player (parent-death hook via `DeleteChildren`, or explicit on character switch). Add its head-label to `map.toml` `order`.
- [ ] **Step 3: Oracle. ⚠ controller.** Appendage tracks through run/roll/jump/fly/tired; flips with facing; no orphan on character switch (hotkey away from Tails → appendage deletes); DPLC watch shows the appendage VRAM region updating. Commit: verify branch. `feat(objects): Tails appendage child — parent-state-mapped anims (C2 complete)`.

### Task 8: C3 — CPU Tails input filter

**Files:**
- Create: `games/sonic4/player/tails_cpu.emp` + head-label into `map.toml` `order`.
- Modify: `games/sonic4/player/player_common.emp` (input-source indirection), `games/sonic4/config/ram.emp` (`Player_Inputs` slots + AI globals), the game's follower-spawn path (level/test state init).
- Parcel ritual.

- [ ] **Step 1: Research.** Read how `Player_Main` reads input: it reads `Ctrl_1_Press` (player_common.emp:259) and `Ctrl_1_Held` directly in several places (player_common.emp:364 rings, :439/:495/:501 in `Player_Animate`, player_air.emp:117). Design the indirection: a slot-indexed `Player_Inputs` (held/press words per slot) filled by `Player_Main`'s caller — leader from `Ctrl_1`, follower from the AI — with the movement core reading `Player_Inputs[slot]` instead of `Ctrl_1_*` directly. Read the ring format (config/ram.emp:80-83, `Player_Pos_Ring`/`Player_Stat_Ring`, 64-deep, stride 4, 256-aligned) and spec §6's machine + AIR fixes. **Floating-origin note:** the position ring holds WORLD coords; the spec says it joins the rebase shift-list (design #2). Check whether floating-origin/rebase has landed and whether the ring is registered on its shift-list — if rebases exist and the ring is NOT registered, the follower will teleport on a rebase; flag it.
- [ ] **Step 2: Input indirection + spawn.** Add `Player_Inputs: [u16; 2*NUM_PLAYERS]` (held/press per slot) to game RAM. Leader copies `Ctrl_1_Held`/`Ctrl_1_Press` into slot 0's pair each frame; the movement core reads only `Player_Inputs[slot]`. `Player_2` spawns as `CHAR_TAILS` follower (DEBUG toggle to enable/disable). Migrate the direct `Ctrl_1_*` reads in the player frame to `Player_Inputs[slot]` — do this carefully so the leader's behavior stays byte-identical (re-run the Task-4 regression after this migration as a sub-gate).
- [ ] **Step 3: The AI.** `TailsCPU_Update` runs before the follower's `Player_Main`; writes slot 1's `Player_Inputs` pair. AI globals (follower-singleton, game RAM): `CPU_Routine`/`CPU_Idle_Timer`/`CPU_Flight_Timer`/`CPU_Target_X`/`CPU_Target_Y`. Routines (S3K machine + AIR fixes, all constants named in `config/constants.emp` with S3K/AIR provenance comments):
  - **FLYIN:** target leader-x, leader-y − 192; approach `min(12, |dx|>>4) + |leader_xvel| + 1` px/frame X, 1 px/frame Y; **land when |dx|≤4 AND |dy|≤4 AND leader grounded, OR leader jump-press** (the AIR tolerance — kills the orbit-forever bug).
  - **FOLLOW:** read the ring 17 frames back (index − $44); `target_x += leader_xvel>>7` keep-up feed-forward; walk threshold 48; stand-behind −32 when leader slow; auto-jump on the 64-frame global timer only if stuck-pushing OR leader >32 above AND |dx| ≥ $30 (no auto-jump when |dx| < $30).
  - **ROLL-FOLLOW:** leader rolling → hold-down variant.
  - **DESPAWN:** off-screen 300 frames → FLYIN.
  - **Idle takeover:** any real P2 input → `CPU_Idle_Timer = 600`, AI early-outs while nonzero.
  - Cosmetic sync at rest (facing + spindash-charge mimic).
- [ ] **Step 4: Oracle soak. ⚠ controller.** Leader circuits at max scroll: follower keeps up through OJZ's fastest stretch (the keep-up fix observable); park — no orbit (lands within tolerance); despawn/fly-in cycle; idle takeover timing; manual P2 control. If floating-origin/rebase has landed: force a rebase mid-follow and verify no follower teleport (ring on the shift-list). `Lag_Frame_Count` delta ≤ ~1-2%. Commit: verify branch. `feat(player): CPU Tails — input-filter AI with AIR quality fixes (C3)`.

### Task 9: C4a — Knuckles assets + def

**Files:**
- Create: converted Knuckles assets under `games/sonic4/data/characters/`, `games/sonic4/data/characters/knuckles_data.emp`, `games/sonic4/data/animations/knuckles_anims.emp`, `games/sonic4/player/knuckles.emp` + head-labels into `map.toml` `order`.
- Modify: `games/sonic4/player/characters.emp` (`CharDef_Knuckles` real), `tools/convert_s3k_char.py` (Knuckles param), `games/sonic4/config/constants.emp` (`VRAM_KNUCKLES` + anim ids grow).
- Parcel ritual.

- [ ] **Step 1: Research.** Check `games/sonic4/data/characters_staging/` for the lane's Knuckles output (consume-and-verify as in Task 5). skdisasm `General/Sprites/Knuckles/{Map - Knuckles.asm, DPLC - Knuckles.asm, Anim - Knuckles.asm, Art/}` (same shapes as Tails — confirm; note Knuckles has no separate appendage). VRAM placement per the Task-5 map.
- [ ] **Step 2: Convert + def.** Integrate staged (or convert via `convert_s3k_char.py knuckles`), **assert no DPLC entry > 16 tiles**. `PhysTable_Knuckles` = Sonic's row with jump force `$680 → $600` (the ONLY delta — comment cites SPG/S3K; the jump-force field is `PHYS_JUMP_FORCE`, the 6th row entry, sonic.emp:64). `CharDef_Knuckles` (stand 9×19-shaped bytes, `cd_ability = Ability_KnuxGlide`). `Ani_Knuckles` full table + the `ANIM_GLIDE`/`ANIM_SLIDE`/`ANIM_CLIMB`/`ANIM_LEDGE` contract growth (bump `ANIM_COUNT`; re-assert every character table incl. Sonic/Tails fallbacks). Point `CharacterDefs[CHAR_KNUCKLES]` at it. Commit: verify branch. `feat(player): Knuckles def + converted S3K assets (C4)`.

### Task 10: C4b — glide + slide

**Files:**
- Create: `games/sonic4/player/player_glide.emp` (PSTATE_GLIDE + PSTATE_SLIDE) + head-labels into `map.toml` `order`.
- Modify: `games/sonic4/config/constants.emp` (states + consts), `games/sonic4/player/player_common.emp` (`Player_States` + hooks + curled-mask), `games/sonic4/player/characters.emp` / `knuckles.emp` (`Ability_KnuxGlide`).
- Parcel ritual.

- [ ] **Step 1: Research.** Spec §7 constants. Our sine/cos: `GetSineCosine` (engine/system/math.emp:21, `proc (d0: Angle) clobbers() out(d0: fixed<8,8>, d1: fixed<8,8>)`). The enter-hook radii mechanism for the 10×10 ability size (glide/slide/climb use 10×10 — the def's `cd_stand_wh` is the standing size; the ability enter hook sets the 10×10 like `set_ball_size` sets ball radii — add a `set_ability_size`-style splice or write the bytes in the glide enter hook). Dust-effect spawning precedent (spindash dust in player_spindash / `CreateEffect_Normal` children.emp:594).
- [ ] **Step 2: Glide (`PSTATE_GLIDE`).** Add the state (constants + `Player_States` + enter/exit hooks; NOT in the curled mask — glide is attacking-not-curled). Entry (`Ability_KnuxGlide`, the air-state hook): `y_vel += $200` clamp ≥0, gsp=$400, angle=0/−$80 by facing, radii 10×10 via the enter hook. Per frame: accel +8 below $400 / +4 above (not while turning), cap $1800; angle ±2/frame toward held direction (64-frame reversal); `x_vel = cos·gsp >> 8` (via `GetSineCosine`); parachute `y_vel ±$20` toward terminal $80; release → fall sub-state with `x_vel asr 2`, radii restored via exit hook. Land: slope-angled → normal land with `x_vel = gsp`; flat → PSTATE_SLIDE.
- [ ] **Step 3: Slide (`PSTATE_SLIDE`).** Friction $20/frame toward 0 → get-up (move_lock $F, ANIM via classifier); ledge-drop (floor dist ≥14 → fall); dust cadence 8; button-release zeroes x_vel (S3K).
- [ ] **Step 4: Oracle matrix. ⚠ controller.** RAM-watch: turn takes 64 frames end-to-end with |velocity| preserved; cap honored; parachute terminal $80; slide stop distance vs hand-computed friction; drop = quarter speed. Verify DURING motion. Commit: verify branch. `feat(player): Knuckles glide + slide (C4)`.

### Task 11: C4c — climb + ledge

**Files:**
- Create: `games/sonic4/player/player_climb.emp` (PSTATE_CLIMB + PSTATE_LEDGE) + head-labels into `map.toml` `order`.
- Modify: `games/sonic4/player/player_glide.emp` (wall-catch handoff), `games/sonic4/config/constants.emp`.
- Parcel ritual.

- [ ] **Step 1: Research (the hard part — write it in the file header before coding).** Map S3K's wall detection (`GetDistanceFromWall` casting from y−11, push-flag gate, 12px floor window — sonic3k.asm:~30776-30855, ~31518-31531) onto OUR sensor layer (`games/sonic4/player/player_sensors.emp` — identify which sensor calls give wall distance at an arbitrary Y; read its wall-probe entry points, e.g. the ones `player_air.emp` `Air_WallProbeRight`/`Air_WallProbeLeft` (:512/:530) call). This equivalence is the task's crux — document it in the module header.
- [ ] **Step 2: Wall-catch from glide.** Push-contact during glide + wall-verify + floor-clearance (12px) → PSTATE_CLIMB: zero velocities, latch X, anim-pacing var (union into PlayerV free region).
- [ ] **Step 3: Climb (`PSTATE_CLIMB`).** 1px/frame up/down; detach on latch-X drift or wall-loss below; ledge detect above (wall distance ≥4 at head sensor) → PSTATE_LEDGE; floor within ~19px below on climb-down → land; jump-off away $400/up −$380 into normal air; top camera clamp.
- [ ] **Step 4: Ledge pull-up (`PSTATE_LEDGE`).** The 4-step script `{frame,dx,dy,6}` table (our frame ids from the converted Knuckles mappings — find the 4 clamber frames), ends standing via `Player_SetState`.
- [ ] **Step 5: Oracle matrix on OJZ walls. ⚠ controller.** Glide→catch at various approach angles; climb both directions; ledge pull-up lands on top; detach cases; jump-off arc. Verify DURING motion. Commit: verify branch. `feat(player): Knuckles climb + ledge pull-up (C4 complete)`.

### Task 12: Docs + merge

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (player-system section), `docs/DEFERRED_WORK.md`, `docs/superpowers/2026-07-02-design-week-queue.md` (log). Any residual engine byte change rides the parcel ritual.

- [ ] **Step 1: ARCH.** Rewrite the player-system section around `CharacterDef` + the ability hook (reads as designed-this-way, not bolted-on). **Fix the stale PlayerV figure:** the doc + player_common.emp:65 comment say "18 of 34 bytes" — state the real number (18 used of 30 usable custom bytes post-sst-fold, then the post-Task-11 number once all ability fields union in). Record that the P2 standing-bit hardcode the spec anticipated is structurally absent in the from-scratch engine (per-SST status). Sweep for stale "PlayerV 16"/"34-byte" claims.
- [ ] **Step 2: DEFERRED_WORK.** Close the per-character-dispatch / Tails / Knuckles items (point here). Register follow-ups: Sonic-carry hook → design #4; water physics rows; Super forms; character-select UI → §9.13. Note the SST-sequencing-vs-floating-origin item is RESOLVED (the sst-fold already relaid the metadata; no relayout pending).
- [ ] **Step 3: Final gates + merge. ⚠ controller.** Full `DEBUG=1 ./build.sh` + plain `./build.sh` both green; `python3 -m pytest tools/ -q` green; the Task-4 regression re-run one final time as Sonic (still byte-identical); all three characters hand-verified via the hotkey + a fly/glide/climb spot-check DURING motion; then merge `feat/character-dispatch` → master (merge commit per repo habit — verify branch at each commit) and update the design-week queue log.

---

## Self-review (done at write time, v2)

- **Spec coverage:** §2 (CharacterDef)→T2; §3 (shared machine + ability + curled rework)→T3 + T6/T10/T11 states; §4 (per-slot globals + P2)→T3 + T1/T4 gate; §5 (Tails+appendage)→T5-7; §6 (CPU)→T8; §7 (Knuckles)→T9-11; §8 phasing→task order; §9 verification→T4/T6/T8/T10/T11 matrices; §10 risks→T3 curled rework, T7 pool choice, T5 VRAM measured decision, T11 sensor mapping; §11 provenance→carried.
- **Sigil-flip translation (global + inline):** every `.asm` path → `.emp` under `games/sonic4/player/`; `main.asm` BINCLUDEs → `map.toml` `order` entries + `embed(...)` data modules (the collision_data.emp precedent); `struct` → `engine/structs.emp` typed literal + `sizeof`; RAM via `games/sonic4/config/ram.emp` chaining from `Engine_RAM_End`; anim tables → `offsets` blocks with ordinal `ensure`s (sonic_anims.emp precedent); build = `DEBUG=1 ./build.sh` → suffixed `s4.debug.bin/.lst`; the parcel ritual (SIGIL_BLOB_LEN_DRIFT=warn, rebuild both sigil binaries, repin→refreeze --ab, THREE test gates) rides every byte-changing task; sigil commits on sigil master.
- **Standing-rules markers:** ⚠ controller on every oracle step; parcel ritual on every byte-emitting change; verify-branch-before-commit throughout; merge only at Task 12; daemon-watched paths (`tools/ojz_strip_gen.py`, `games/sonic4/data/editor/ojz/`) confirmed NOT touched by any task (new converter + staging dir are outside the watch set) — ask-user-first only if that ever changes.
- **Anchors re-verified against `feat/art-streaming-p2`** (drift fixed inline): the four dispatch sites `player_common.asm:119/154/259/405` → live `Player_Init:193` / `Player_RefreshPhysics:234` / `Player_Display:380` / `Player_DebugExit:869` (+ sonic.emp immediates); `Perform_DPLC :21` → dplc.emp:97 (new signature); `CreateChild_FlipAware :187` → children.emp:341 (**+ `@scaffolding`, must un-tag**); `DeleteChildren :354` → :555; `collision.asm:205` P1-hardcode → **absent** (per-SST status); camera Player_1 sites → camera.emp:228/292 + `PL_STATE_ADDR` :70/:329; path_swap → :84/:101; `GetSineCosine` → math.emp:21; PSTATE ball test → player_common.emp:420-421 + ordering `ensure` constants.emp:64; `Engine_RAM_End` → engine/ram.emp:617.
- **SPEC-STALE claims flagged for controller attention (do NOT trust the spec verbatim on these):**
  1. **SST sequencing rule is resolved** — the sst-fold (2026-08-05) already relaid the metadata (frame_off $50→$2E, custom window $30-$4F); PlayerV is 18 of 30 usable bytes = 12 free; there is no floating-origin-F2 relayout to sequence against. (spec §4 + original standing rules)
  2. **The P2 standing/pushing-bit hardcode does not exist** — the from-scratch engine uses per-SST status bytes iterated over both players in `TouchResponse`; `ST_P1_STANDING`/`ST_P2_STANDING` globals were never created. Task 3 Step 6 is an audit, not a fix. (spec §4)
  3. **The regression harness is the shipped replay net**, not a fresh `emulator_press` script — `Input_Source=INPUT_PLAYBACK` over `Replay_OJZ_Fixture`/`Replay_OJZ_Slide_Fixture`. (original Task 1)
  4. **The child creator is `@scaffolding` (zero call sites)** — the appendage is its first consumer and must remove the tag; the spec assumed a live API. (spec §5)
- **Post-merge re-pin rule:** every RAM/line anchor is pre-merge (`feat/art-streaming-p2`); art-streaming P2 moves `Engine_RAM_End` and the VRAM budget — Task 1 re-reads on post-merge master and Task 5 draws the follower/appendage VRAM from P2's freed frames.
- **Asset gotchas:** DPLC 16-tile-overflow assertion is an explicit step in T5/T9 (data must pass through `dplc_layout.split_contiguous_entries`); asset tasks consume+verify the parallel lane's `characters_staging/` output with from-scratch conversion as fallback.
- **Placeholders:** none — T5's VRAM placement is an explicit measured decision with ranked options; every code step has an exact anchor + expected observable.
- **Consistency:** `CharacterDef`/`cd_*`, `PlayerV.chardef`, `Character_ID`, `CHAR_*`, `Ability_None`/`Ability_TailsFlight`/`Ability_KnuxGlide`, `PSTATE_FLY`/`GLIDE`/`SLIDE`/`CLIMB`/`LEDGE`, `PSTATE_CURLED_MASK`, `Player_Inputs`, `Camera_Target`, `VRAM_TAILS`/`VRAM_TAILS_APPENDAGE`/`VRAM_KNUCKLES` uniform across tasks.
