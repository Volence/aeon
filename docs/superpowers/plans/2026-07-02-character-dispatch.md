# Character Dispatch + Tails & Knuckles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One shared movement core driving a three-character roster — CharacterDef data + one ability hook; Tails (flight, appendage, CPU follower), Knuckles (glide/slide/climb/ledge); stock S3K assets converted from skdisasm.

**Architecture:** C1 (Tasks 2-4): CharacterDef + per-slot globals + Camera_Target + P2-bit fix, gated by a recorded-input regression proving Sonic unchanged. C2 (Tasks 5-7): S3K asset conversion, tails.asm, PSTATE_FLY, the appendage child. C3 (Task 8): CPU input filter with AIR fixes. C4 (Tasks 9-11): Knuckles assets + glide/slide/climb/ledge. Task 12: docs + merge. Spec: `docs/superpowers/specs/2026-07-02-character-dispatch-design.md` (APPROVED; asset sourcing = skdisasm per `da7e699`).

**Tech Stack:** 68000 assembly (AS), Python asset converters (`tools/`), oracle MCP, skdisasm asset source (`/home/volence/sonic_hacks/skdisasm/General/Sprites/{Tails,Knuckles}/`).

**Standing rules:** Step 1 of every task is research; line anchors are as of `da7e699` and WILL drift. Build `SOUND_DRIVER_ENABLED=1 DEBUG=1 ./build.sh`; runtime-boot after ram.asm/structs.asm changes; `git add` exact paths; commit per green task; branch `feat/character-roster` off master; merge at Task 12. **SST sequencing rule (spec §4):** if floating-origin F2 has landed, PlayerV free space is 16 bytes at `sst_custom=$30`; if not, 18 at `$2E` — check `structs.asm` FIRST and record which world you're in. Verify during MOTION.

---

### Task 1: Branch + the input-script regression harness

**Files:**
- Create: scratchpad capture script (not committed)

- [ ] **Step 1: Research.** Read `games/sonic4/player/player_common.asm` in full (the state machine, `Player_Main`, `Player_SetState`, hooks), `sonic.asm`, `player_ground.asm`/`player_air.asm`/`player_spindash.asm` headers, `constants.asm:141-144,178,195-201,271-297`, `structs.asm:60-115`, `ram.asm:217-223,282-295,423-428`, `engine/level/camera.asm:40-80,140-185`, `engine/objects/collision.asm:20-30,200-210`, `engine/objects/children.asm` API headers, `engine/level/path_swap.asm:70-95`.
- [ ] **Step 2: Branch.** `git checkout -b feat/character-roster`.
- [ ] **Step 3: Harness.** Scripted oracle run: reset → spawn on OJZ → a fixed ~1200-frame input script exercising run/skid/roll/jump/spindash/slope/loop (drive via `emulator_press`/`emulator_run_frames` — deterministic because input timing is frame-exact). Sample every 30 frames: `Player_1` x_pos/y_pos/ground_speed/_pl_state/SST_status + `Camera_X/Y`. Save the table to scratchpad as `baseline_trajectory.tsv`. This is the C1 gate oracle — rerun after Task 3 and diff (must be byte-identical).

### Task 2: C1a — CharacterDef + Character_ID + the four dispatch sites

**Files:**
- Create: `games/sonic4/player/characters.asm` (def struct + index table)
- Modify: `games/sonic4/player/sonic.asm`, `games/sonic4/player/player_common.asm` (sites :119, :154, :259, :405 as audited), `structs.asm`, `constants.asm`, `ram.asm`, `games/sonic4/main.asm`

- [ ] **Step 1: Research.** Re-verify the four hardwired sites and the exact `Player_RefreshPhysics` copy loop; read `Perform_DPLC`'s register contract (`engine/objects/dplc.asm:21`); read how `objvarsCheck` guards PlayerV.
- [ ] **Step 2: The struct + Sonic's def.**

```asm
; structs.asm
        struct CharacterDef
cd_phys         ds.l 1          ; -> 8-word physics row (PhysTable shape)
cd_mappings     ds.l 1
cd_dplc         ds.l 1
cd_artbase     ds.l 1
cd_animtable    ds.l 1
cd_ability      ds.l 1          ; jump-press hook, called from the air state
cd_vrambase     ds.w 1          ; tile index (vram_bytes applied at use)
cd_stand_wh     ds.w 1          ; W<<8|H stand radii
cd_roll_wh      ds.w 1
cd_flags        ds.w 1          ; reserved capability bits
        endstruct
; constants.asm
CHAR_SONIC = 0
CHAR_TAILS = 1
CHAR_KNUCKLES = 2
; ram.asm
Character_ID:   ds.w 1          ; word for clean index math
```

  `characters.asm`: `CharacterDefs:` index table (`dc.l CharDef_Sonic, CharDef_Tails, CharDef_Knuckles` — the latter two point at Sonic's until C2/C4, tagged `; TEMP roster stub`). `CharDef_Sonic` filled from today's immediates (`PhysTable_Sonic`, `Map_Sonic`, `DPLC_Sonic`, `Art_Sonic`, `Ani_Sonic`, `Ability_None` (an `rts`), `VRAM_TEST_SONIC`, 9<<8|19, 7<<8|14).
- [ ] **Step 3: Cache the def per slot + convert the four sites.** New PlayerV long `_pl_chardef` (grows PlayerV 16→20 — assert headroom per the SST sequencing rule). `Player_Init` resolves `Character_ID` → def, stores it, and: InitAssets becomes a shared `Player_InitAssets` reading cd_mappings/cd_vrambase/cd_animtable; `Player_RefreshPhysics` loads `cd_phys` via the def; `Player_Display`'s tail becomes a shared `Player_LoadArt` reading cd_dplc/cd_artbase/cd_vrambase; the `PState_Spindash` row stays shared (it is roster-shared — only the header comment updates). `sonic.asm` shrinks to data (`PhysTable_Sonic` + the def).
- [ ] **Step 4: Build + boot + quick circuit.** Sonic must play normally by hand-feel; the formal gate is Task 4. Commit: `feat(player): CharacterDef data dispatch — Sonic through the roster path (C1)`

### Task 3: C1b — per-slot globals, ability hook, Camera_Target, P2-bit fix

**Files:**
- Modify: `player_common.asm`, `player_air.asm`, `player_ground.asm`, `player_spindash.asm`, `ram.asm`, `engine/level/camera.asm`, `engine/level/path_swap.asm`, `engine/objects/collision.asm`

- [ ] **Step 1: Research.** Enumerate every reader of `Player_Phys`/`Player_Quadrant`/`Player_JumpBuffer` (grep); every `lea (Player_1)` outside player files; all `>= PSTATE_JUMP` ball-test compares (the curled-set rework's blast radius).
- [ ] **Step 2: Per-slot globals.** `Player_Phys` becomes `Player_Phys_Slots: ds.w 8*NUM_PLAYERS`; `Player_Main` computes the slot's base into a4 (slot index from `(a0 - Object_RAM)/SST_len`, or a cached `_pl_slot` byte set at init — pick the cheaper, comment why). `Player_Quadrant`/`Player_JumpBuffer` become per-slot bytes in PlayerV (quadrant + jumpbuffer = 2 bytes; PlayerV 20→22). Ring recording gated on leader: `tst.b _pl_slot; bne .skip_record`.
- [ ] **Step 3: Ability hook.** In the air state's jump-press handling (`player_air.asm` — find the double-jump-shaped input check; if none exists, add the press check where jump-release cap is handled): `movea.l _pl_chardef(a0),a1; movea.l cd_ability(a1),a1; jsr (a1)`. `Ability_None: rts`.
- [ ] **Step 4: PSTATE curled-set rework.** Replace `>= PSTATE_JUMP` ball tests with an explicit curled mask/table so C2/C4 states can append without ordering constraints; delete the ordering assert, add a `PSTATE_CURLED_MASK` (bit per state) with a build assert it covers JUMP/ROLLJUMP/AIRBALL/ROLL.
- [ ] **Step 5: Camera_Target + path-swap + P2 bit.** `Camera_Target: ds.l 1` seeded to `Player_1`; the three `lea (Player_1)` camera sites + path-swap read it. `collision.asm:205`: select `ST_P1_STANDING`/`ST_P2_STANDING` (and pushing) by the loop index (the loop counter is live — derive bit number, `bset d6,...`).
- [ ] **Step 6: Build + boot + commit.** `feat(player): per-slot physics/quadrant/jump-buffer, ability hook, Camera_Target, P2 status bits (C1)`

### Task 4: C1 gate — recorded-input regression

- [ ] **Step 1:** Re-run the Task-1 harness script on the refactored build. Diff `trajectory.tsv` against baseline: **byte-identical required.** Any divergence = a refactor behavior change — fix before proceeding (the usual suspects: physics-copy timing, jump-buffer consumption order, quadrant read timing). Record the diff-clean result + commit hash in the commit message: `test(player): C1 regression gate passed — roster path is behavior-identical`

### Task 5: C2a — S3K asset conversion (Tails + tails appendage)

**Files:**
- Create: `tools/convert_s3k_char.py`, converted outputs under `games/sonic4/data/{mappings,dplc,animations}/` + `art/`
- Modify: `games/sonic4/main.asm` (BINCLUDEs)

- [ ] **Step 1: Research.** Read `tools/convert_s2_mappings.py` (the existing converter — S2 format in, our VDP-order format out) and `tools/dplc_layout.py` (our DPLC format + the >16-tile entry-splitting fix). Read the S3K source formats: `skdisasm/General/Sprites/Tails/Map - Tails.asm`, `DPLC - Tails.asm`, `Anim - Tails.asm`, `Art` dir (uncompressed?
  check for .bin vs compressed), and the appendage set (`Map - Tails tails.asm`, `DPLC - Tails tails.asm`, `Anim - Tails Tail.asm`). S3K mappings/DPLC are the S3K player format (word-offset tables, art in uncompressed .bin for players). Diff our staged `art/optimized/characters/tails.bin` + `data/dplc/tails.bin` (sonic_hack lineage) against the skdisasm source — if identical lineage, reuse; else convert fresh per the spec decision.
- [ ] **Step 2: Converter.** `convert_s3k_char.py <char>`: parses S3K map/DPLC asm → emits our mappings bin (VDP field order) + our DPLC bin (via dplc_layout conventions, entry-split for >16-tile frames — the known overflow trap). Deterministic, pytest-covered (golden frame-count + a spot-checked frame). Anim scripts are NOT machine-converted: author `Ani_Tails`/`Ani_TailsAppendage` by hand against our ANIM contract (11+ ids), using S3K's `Anim - Tails.asm` frame sequences as the source of truth.
- [ ] **Step 3: VRAM placement research (resolve before wiring).** Sonic's DPLC region is `VRAM_TEST_SONIC = $3C0` (64 tiles to BG at 1024). Two simultaneous characters (leader + follower) + the appendage need distinct regions. Measure real needs: max tiles per frame from the converted DPLCs (Sonic ~48? Tails ~40? appendage ~12?). Options in preference order: (a) carve the follower + appendage regions from the FG pool budget (interacts with art-streaming P2's ~700-850 effective budget — if P2 residency has landed, take frames; else static slots below 960), (b) tighten all char regions. Document the chosen map in `constants.asm` with the audit trail; this is the one place the plan defers to measured data.
- [ ] **Step 4: pytest + build (data assembles, nothing consumes yet) + commit.** `feat(tools,data): S3K Tails + appendage assets converted to engine formats (C2)`

### Task 6: C2b — Tails playable: def + PSTATE_FLY

**Files:**
- Create: `games/sonic4/player/tails.asm`, `games/sonic4/data/animations/tails_anims.asm`
- Modify: `characters.asm`, `player_air.asm` (ability entry), new `games/sonic4/player/player_fly.asm`, `constants.asm` (ANIM_FLY/ANIM_FLY_TIRED + PSTATE_FLY), `player_common.asm` (states table + hooks), `game_loop.asm` (DEBUG character hotkey)

- [ ] **Step 1: Research.** Re-read spec §5 constants; read our `Player_Animate` classifier to see where flight anims slot; check `ANIM_COUNT` asserts across all character tables.
- [ ] **Step 2: `tails.asm`:** `PhysTable_Tails` = Sonic's row verbatim (comment: SPG — Tails ground physics identical; ONLY sizes + ability differ); `CharDef_Tails` (stand 9×15, roll 7×14, `Ability_TailsFlight`).
- [ ] **Step 3: `PSTATE_FLY` in `player_fly.asm`,** S3K-exact per spec §5: entry (from `Ability_TailsFlight`: only if airborne-not-curled-check passes; seed fuel 240, thrust flag); thrust `subi.w #$20` while `y_vel >= -$100`, 32-frame ramp cap; coast `addi.w #8`; fuel decrement every other frame (`Frame_Counter` parity); tired blocks re-flap only; **ceiling fix**: on ceiling contact reset thrust→coast (the S3K strand trap — comment cites SPG); top clamp at camera-min+$10; land → ground state via `Player_SetState`. X control: air accel from the phys row (a4), drag rule as the air state (share the code — flight X is the air state's X, factored if not already).
- [ ] **Step 4: Anims + hotkey.** `ANIM_FLY`/`ANIM_FLY_TIRED` appended to the contract; ALL character tables grow (Sonic's rows point at ANIM_SPRING-style fallbacks, commented); `Ani_Tails` full table. DEBUG: SELECT-equivalent hotkey (pick a free button/combo — check `Debug_MusicToggle`'s claimed buttons A/B/C/UP/START; use DOWN+START or similar) cycles `Character_ID` and re-runs `Player_Init`.
- [ ] **Step 5: Oracle flight matrix.** Thrust/coast transitions at the exact velocities (RAM-watch y_vel); 8s fuel wall-clock; tired behavior; ceiling fix (fly into OJZ terrain overhang — no strand); top clamp; land cleanly. Commit: `feat(player): Tails playable — CharacterDef + PSTATE_FLY (C2)`

### Task 7: C2c — the appendage child

**Files:**
- Create: `games/sonic4/objects/tails_appendage.asm`
- Modify: `tails.asm` (spawn at init), `characters.asm`

- [ ] **Step 1: Research.** Read `engine/objects/children.asm` `CreateChild_FlipAware` (:187) + `DeleteChildren` (:354) contracts; the S3K anim-mapping table (`Obj_Tails_Tail_AniSelection`, sonic3k.asm:30080) for the parent-anim→tail-anim pairs; our object pool culling rules (`core.asm:180-181`) to pick the pool (System pool if children can spawn there — research; the appendage must never cull while the player lives).
- [ ] **Step 2: The object.** Spawned by Tails' `Player_InitAssets` path; per frame: read parent (`parent_ptr`) x/y/angle/status/priority; map parent `SST_anim` through `TailsApp_AnimMap` (dc.b table mirroring S3K's pairs for OUR anim ids); own DPLC via the converted appendage set; deleted with the player (parent-death hook or explicit on character switch).
- [ ] **Step 3: Oracle.** Appendage tracks through run/roll/jump/fly/tired; flips with facing; no orphan on character switch; DPLC watch shows appendage region updates. Commit: `feat(objects): Tails appendage child — parent-state-mapped anims (C2 complete)`

### Task 8: C3 — CPU Tails input filter

**Files:**
- Create: `games/sonic4/player/tails_cpu.asm`
- Modify: `player_common.asm` (input source indirection), `ram.asm` (AI globals), test harness state (spawn follower)

- [ ] **Step 1: Research.** Read how `Player_Main` reads input (`Ctrl_1_Held/Press` direct? — find the read sites); design the input indirection: each slot reads `_pl_input_*` fields (or a per-slot input pair in RAM) that `Player_Main`'s caller fills — leader from Ctrl_1, follower from the AI. Read the ring format (`ram.asm:423-428`, stride 4, 64 deep) and spec §6's machine + AIR fixes.
- [ ] **Step 2: Input indirection + spawn.** Slot-indexed `Player_Inputs` (held/press words ×2); leader copies Ctrl_1; `Player_2` spawned as `CHAR_TAILS` follower (DEBUG toggle to enable/disable). Movement core reads only `Player_Inputs[slot]`.
- [ ] **Step 3: The AI.** `TailsCPU_Update` (runs before the follower's `Player_Main`): globals `CPU_Routine/CPU_Idle_Timer/CPU_Flight_Timer/CPU_Target_X/Y`. Routines: FLYIN (target leader-x, leader-y−192; approach `min(12, |dx|>>4)+|leader_xvel|+1` px/frame X, 1 px/frame Y; **land when |dx|≤4 AND |dy|≤4 AND leader grounded, or leader jump-press** — the AIR tolerance); FOLLOW (read ring 17 frames back = index−$44; `target_x += leader_xvel>>7` keep-up; walk threshold 48; stand-behind −32 when leader slow; auto-jump on 64-frame global timer only if stuck-pushing or leader >32 above AND |dx| ≥ $30); ROLL-FOLLOW (leader rolling → hold down variant); DESPAWN (off-screen 300 frames → FLYIN). Idle takeover: any real P2 input → `CPU_Idle_Timer = 600`, AI early-outs while nonzero. Cosmetic sync at rest (facing + spindash-charge mimic). All constants named in `constants.asm` with S3K/AIR provenance comments.
- [ ] **Step 4: Oracle soak.** Leader circuits at max scroll: follower keeps up through OJZ's fastest stretch (the keep-up fix observable); park — no orbit (lands within tolerance); despawn/fly-in cycle (trap the follower); idle takeover timing; manual P2 control. If floating-origin has landed: force a rebase mid-follow (ring is on its shift-list — verify no follower teleport). `Lag_Frame_Count` delta ≤ ~1%. Commit: `feat(player): CPU Tails — input-filter AI with AIR quality fixes (C3)`

### Task 9: C4a — Knuckles assets + def

**Files:**
- Create: converted Knuckles assets, `games/sonic4/player/knuckles.asm`, `games/sonic4/data/animations/knuckles_anims.asm`
- Modify: `characters.asm`, `tools/convert_s3k_char.py` (char param), `main.asm`

- [ ] **Step 1: Research.** skdisasm `General/Sprites/Knuckles/` formats (same shapes as Tails — confirm); VRAM placement per the Task-5 map.
- [ ] **Step 2:** Convert; `PhysTable_Knuckles` = Sonic's row with jump force `$680→$600` (the ONLY delta, comment cites SPG/S3K); `CharDef_Knuckles` (stand 9×19, `Ability_KnuxGlide`); `Ani_Knuckles` full table + `ANIM_GLIDE/ANIM_SLIDE/ANIM_CLIMB/ANIM_LEDGE` contract growth (all tables re-asserted). Commit: `feat(player): Knuckles def + converted S3K assets (C4)`

### Task 10: C4b — glide + slide

**Files:**
- Create: `games/sonic4/player/player_glide.asm` (PSTATE_GLIDE + PSTATE_SLIDE)
- Modify: `constants.asm`, `player_common.asm` (table + hooks + curled-mask), `characters.asm`

- [ ] **Step 1: Research.** Spec §7 constants; our sine table access (`GetSineCosine` equivalent — find the engine's sin/cos, `engine/system/math.asm`?); the enter-hook radii mechanism for the 10×10 ability size; dust-effect spawning precedent (spindash dust).
- [ ] **Step 2: Glide.** Entry (`Ability_KnuxGlide`): `y_vel += $200` clamp ≥0, gsp=$400, angle=0/−$80 by facing, radii 10×10 via enter hook. Per frame: accel +8 below $400 / +4 above (not while turning), cap $1800; angle ±2 toward held direction; `x_vel = cos·gsp>>8`; parachute `y_vel ±$20` toward $80; release → fall sub-state with `x_vel asr 2`, radii restore. Land: slope-angled → normal land with `x_vel=gsp`; flat → PSTATE_SLIDE.
- [ ] **Step 3: Slide.** Friction $20/frame toward 0 → get-up (move_lock $F, ANIM via classifier); ledge-drop (floor ≥14 → fall); dust cadence; button-release zeroes x_vel (S3K).
- [ ] **Step 4: Oracle matrix.** RAM-watch: turn takes 64 frames end-to-end with |velocity| preserved; cap honored; parachute terminal $80; slide stop distance vs hand-computed friction; drop = quarter speed. Commit: `feat(player): Knuckles glide + slide (C4)`

### Task 11: C4c — climb + ledge

**Files:**
- Create: `games/sonic4/player/player_climb.asm` (PSTATE_CLIMB + PSTATE_LEDGE)
- Modify: `player_glide.asm` (wall-catch handoff), `constants.asm`

- [ ] **Step 1: Research.** Map S3K's wall detection (`GetDistanceFromWall` casting from y−11, push-flag gate, 12px floor window — sonic3k.asm:30776-30855, 31518-31531) onto OUR sensor layer (`games/sonic4/player/player_sensors.asm` — which sensor calls give wall distance at an arbitrary Y; the §5 sensor doc). This mapping is the task's hard part — write it down in the file header before coding.
- [ ] **Step 2: Wall-catch from glide:** push-contact during glide + wall-verify + floor-clearance (12px) → PSTATE_CLIMB: zero velocities, latch X, anim pacing var.
- [ ] **Step 3: Climb:** 1px/frame up/down; detach on latch-X drift or wall-loss below; ledge detect above (wall distance ≥4 at head sensor) → PSTATE_LEDGE; floor within ~19px below on climb-down → land; jump-off away $400/up −$380 into normal air; top camera clamp.
- [ ] **Step 4: Ledge pull-up:** the 4-step script `{frame,dx,dy,6}` table (our frame ids from the converted mappings — find the 4 clamber frames), ends standing via `Player_SetState`.
- [ ] **Step 5: Oracle matrix on OJZ walls:** glide→catch at various approach angles; climb both directions; ledge pull-up lands on top; detach cases; jump-off arc. Commit: `feat(player): Knuckles climb + ledge pull-up (C4 complete)`

### Task 12: Docs + merge

- [ ] **Step 1:** ARCH: player system section rewritten around CharacterDef + ability hook (reads as designed-this-way); fix the stale "PlayerV 13 of 34" figure (audit: was 16, now larger — state the real number); DEFERRED_WORK: close the per-character-dispatch/Tails/Knuckles items, register follow-ups (Sonic-carry hook → design #4; water rows; Super forms; character-select UI → §9.13); spec §9 cross-references updated in the floating-origin spec if its F2 ordering resolved here.
- [ ] **Step 2:** Full gates: DEBUG + plain builds; pytest; the Task-4 regression re-run one final time as Sonic (still identical); all three characters hand-verified via the hotkey; merge `feat/character-roster` → master; queue-doc log updated.

---

## Self-review (done at write time)

- **Spec coverage:** §2→T2; §3→T3(hook,curled)+T6/T10/T11(states); §4→T3+T1/T4(gate); §5→T5-7; §6→T8; §7→T9-11; §8 phasing→task order; §9→T4/T6/T8/T10/T11 matrices; §10 risks→T3 curled rework, T7 pool choice, T5 VRAM research, T11 sensor mapping, sequencing rule in standing rules.
- **Placeholders:** none — T5's VRAM placement is an explicit measured decision with options ranked, not a TBD.
- **Consistency:** `CharacterDef`/`cd_*`, `_pl_chardef`, `Character_ID`, `CHAR_*`, `Ability_None/TailsFlight/KnuxGlide`, `PSTATE_FLY/GLIDE/SLIDE/CLIMB/LEDGE`, `PSTATE_CURLED_MASK`, `Player_Inputs`, `Camera_Target` uniform across tasks.
