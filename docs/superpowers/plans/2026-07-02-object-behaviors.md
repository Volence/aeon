# Reusable Object Behaviors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A two-track per-object byte-opcode behavior sequencer (skeleton + three example badniks) with Aurora-attached per-placement params via subtype bundles, plus the badnik-side Touch_Enemy kill/score/explosion chain.

**Architecture:** M (Task 1): 256-angle math module. B (Tasks 2-3): sequencer core + flow ops, then movement/combat ops. K (Task 4): Touch_Enemy + death chain. G (Task 5): `behavior_gen.py` + param bundles. E (Task 6): the three example badniks (Patroller/Shooter/Orbiter; `test_enemy` deleted). A (Task 7): Aurora properties panel + MCP tools. Task 8: dense-fixture profiler checkpoint + soak + ARCH docs + merge. Spec: `docs/superpowers/specs/2026-07-02-object-behaviors-design.md` (APPROVED) — op semantics, event enum, bundle mechanism, boss seams all specified there.

**Dependencies:** design #4's player-side `Touch_Enemy` rebound is separate (this plan implements the badnik side; the two halves meet at the `Touch_Enemy` handler — if #4 executed first, extend its handler; if not, own the handler and leave the rebound branch tagged for #4). Score BCD helpers arrive with #7 — until it lands, award raw BCD adds with a tagged helper. Aurora task in the sibling repo (separate git).

**Tech Stack:** 68000 (AS), Python 3 + pytest, oracle MCP (foreground only), Aurora Electron/React/TS. Standing rules: research first per task; `DEBUG=1`; runtime-boot after ram.asm/structs changes; exact-path commits; branch `feat/object-behaviors`; object code lives inside the 64KB object bank (`code_addr` routines) — engine sequencer/angle code does NOT (it's engine block, called via `jsr`); verify DURING MOTION; behaviors store NO absolute coords (floating-origin rule — review every op for it).

---

### Task 1: 256-angle math module

**Files:**
- Create: `engine/system/angles.asm` (sin/cos + atan2 + velocity-from-angle), `tools/gen_angle_tables.py` (emits the two tables as asm includes), `tools/tests/test_gen_angle_tables.py`
- Modify: `games/sonic4/main.asm` (engine include), `build.sh`

- [ ] **Step 1: Research.** Spec §3.5; skdisasm `GetSineCosine:3020`/`GetArcTan:3042` + `ArcTanTable:3099` (semantics reference, code fresh); plutiedev angle-math + Coranac octant folding (cited in spec §2); our existing math helpers (grep `Sine\|CalcAngle` in engine/ — confirm none exist); CODING_CONVENTIONS on lookup tables + `function` build-time math.
- [ ] **Step 2: Failing test.** `test_gen_angle_tables.py`: generator emits 256-entry word sine table (Q8.8, sin[0]=0, sin[$40]=$100, sin[$80]=0, sin[$C0]=-$100) and a 32×32 octant atan2 byte table with spot values (atan2(1,1)=$20 region). FAIL first.
- [ ] **Step 3: Implement.** Generator → `data/generated/tables/angle_tables.asm`. Engine API:

```asm
; d0.b angle -> d1.w sin, d2.w cos (Q8.8). cos = sin[(angle+$40)&$FF]
Angle_SinCos:
; d0.w dx, d1.w dy -> d0.b angle (0=right, $40=down; screen-y positive down)
Angle_Atan2:        ; octant fold: swap/negate to octant 0, asr both until <32, table, unfold
; d0.b angle, d1.w speed (Q8.8-scalar) -> d0.w x_vel, d1.w y_vel (8.8)
Angle_Velocity:     ; sin/cos * speed via shifts+adds on table values (no mulu)
```

- [ ] **Step 4: Verify + commit.** `git checkout -b feat/object-behaviors`. DEBUG boot self-check (like compression golden): assert `Angle_Atan2` octant-boundary cases (dx=dy, dx=0, negatives) against expected bytes, `Angle_Velocity` magnitudes within 1/256 tolerance at 8 angles; oracle boot shows PASS. `feat(engine): 256-angle math — sin/cos, octant atan2, velocity (no divide)`

### Task 2: Sequencer core + flow ops

**Files:**
- Create: `engine/objects/behavior.asm` (BehaviorV struct over sst_custom, Behavior_Tick, flow ops, event system)
- Modify: `constants.asm` (`BOP_*` opcodes, `EV_*` enum), `structs.asm` (BehaviorV), `games/sonic4/main.asm`, a temporary `games/sonic4/objects/test_behavior.asm` fixture in the object bank

- [ ] **Step 1: Research.** Spec §3.1-3.4 in full; `engine/objects/core.asm:159-249` (loop contract: preserve a0/d7; dispatch shape); `macros.asm:59-63` `objvarsCheck`; the culling thresholds (`CULL_DISTANCE_X/Y`) for the EV_ONSCREEN semantics; `animate.asm:161-163` AF_ROUTINE convention + `AF_CALLBACK` contract (:25-27) for the EV_ANIM bridge; design #8's landed-or-planned sequencer for idiom alignment (separate machinery — do NOT share code).
- [ ] **Step 2: Implement.**

```asm
; structs.asm — over sst_custom (objvarsCheck'd)
        struct BehaviorV
bv_move_pc      ds.w 1   ; offset into BehaviorBank, 0 = idle
bv_move_wait    ds.w 1
bv_move_loop    ds.b 1
bv_act_pc       ds.w 1
bv_act_wait     ds.w 1
bv_act_loop     ds.b 1
bv_resume_pc    ds.w 1   ; depth-1 interrupt slot (shared)
bv_facing       ds.b 1   ; bit0 dir; bits1-7 last-fire angle store (sequence mode)
bv_params       ds.w 1   ; bundle ptr low word (bank-relative)
        endstruct        ; 14 bytes; locals live after this in sst_custom
```

  `Behavior_Tick(a0)`: per track — wait nonzero → `subq.w`, done; else fetch loop: `moveq #0,d0; move.b (a2)+,d0; add.w d0,d0; move.w BopTable(pc,d0.w),d1; jsr BopTable(pc,d1.w)` until an op yields (sets wait / clears pc / ends frame). Flow ops: `BOP_END` (pc=0) · `BOP_WAIT n.w` · `BOP_WAIT_EVENT ev.b[,params]` (stores armed event in a track local; the event scanner satisfies it) · `BOP_BRANCH rel.w` · `BOP_LOOP n.b`/`BOP_ENDLOOP` · `BOP_ON_EVENT ev.b,rel.w` · `BOP_RESUME` · `BOP_NATIVE idx.b` (per-game table, `jsr`). Event scanner (runs once per tick before tracks): armed-only checks — `EV_ONSCREEN/OFFSCREEN` (render flag), `EV_PLAYER_NEAR` (box compare vs `Player_1` — abs-delta, params from bundle/inline), `EV_LANDED/EV_WALL/EV_EDGE` (flags set by movement ops, §Task 3), `EV_ANIM` (flag set by an AF_CALLBACK shim `Behavior_AnimEvent`). Fixture object: hand-assembled byte stream in ROM (`dc.b BOP_WAIT,>60,<60, BOP_BRANCH,...`) toggling its anim; verifies wait timing + loop + on_event/resume via a debug-key-forced event.
- [ ] **Step 3: Verify + commit.** Oracle frame-step: wait counts exact; loop iterates N; on_event fires once, resume returns to saved PC; a0/d7 preserved (DEBUG assert passes); idle objects cost the subq path only (spot-check via step-over). `feat(engine): behavior sequencer core — two tracks, flow ops, armed events, depth-1 interrupt`

### Task 3: Movement + combat ops

**Files:**
- Modify: `engine/objects/behavior.asm` (ops), `constants.asm`
- Uses: `engine/objects/children.asm` (CreateChild_Normal), `engine/system/angles.asm`

- [ ] **Step 1: Research.** Spec §3.4; `core.asm:293-329` ObjectMove/X/Y; `children.asm:43,390,450` descriptors + effect spawn; `MAX_SPAWNS_PER_FRAME` guard site; how `test_enemy.asm` senses edges today (it doesn't — counter only) → implement EV_EDGE/EV_WALL via the collision lookup the player sensors use (find the cheap floor-distance entry point; if none exists for objects, a minimal `Behavior_FloorProbe` using the tile-cache collision read is in-scope here); design #3 spec's `Camera_Target` (aim reads `Player_1` behind a `BEHAVIOR_AIM_TARGET` alias so #3's pointer lands cleanly).
- [ ] **Step 2: Implement.** `BOP_SET_VEL mode.b,angle.b,speed.w`: mode 0 absolute (angle as given) · 1 **aim** (`Angle_Atan2` of target−self delta, +angle as offset) · 2 relative (facing-adjusted) · 3 **sequence** (last-fire angle + delta; store back). → `Angle_Velocity` → x_vel/y_vel. `BOP_MOVE_UNTIL ev.b`: sets a per-track "moving" flag; each tick runs `ObjectMoveX` (or full move if y_vel), probes per the armed event (edge: floor probe ahead-below misses → EV_EDGE; wall: probe ahead at mid-height hits → EV_WALL; probe every 4th frame staggered by slot index — the loss-ring cadence precedent), event → next op. `BOP_TURN`: `neg.w x_vel` + flip facing + RF_XFLIP toggle. `BOP_HOME speed.w,rate.b`: every `rate` frames re-run aim (steering clamp ±4 angle units/step). `BOP_FIRE arch.b,mode.b,angle.b,speed.w`: resolve child descriptor index → `CreateChild_Normal`, then aim math applied to the CHILD's velocity; honors spawn cap (fail = skip silently, classic). `BOP_SPAWN arch.b,dx.b,dy.b`. `BOP_SET_ANIM id.b`. `BOP_SET_COLLISION type.b`. `BOP_DIE style.b` → Task 4's `Badnik_Die`. **Floating-origin review:** every op audited — no absolute coords stored anywhere (facing/angles/counters only).
- [ ] **Step 3: Verify + commit.** Fixture streams on oracle: aim fires point at the player from 8 approach octants (probe child x_vel/y_vel signs+ratios in RAM); sequence mode emits an evenly-spaced fan; move_until+turn patrols a platform edge-to-edge indefinitely (DURING MOTION, across a section boundary); spawn cap respected under a pathological fire loop. `feat(engine): behavior movement/combat ops — 4-mode aim, patrol probes, fire/spawn/die`

### Task 4: Touch_Enemy + the death chain

**Files:**
- Modify: `engine/objects/collision.asm` (`Touch_Enemy` real), `engine/objects/behavior.asm` (`Badnik_Die`), `ram.asm` (`Chain_Bonus_Count.b` + pad), `constants.asm` (score ladder)
- Create: explosion effect anim data if none fits (`games/sonic4/data/animations/` TEMP)

- [ ] **Step 1: Research.** Damage spec §2/§2.1 (the split: attacking-posture test + kill here; rebound is player-side #4 — check whether #4 landed; integrate accordingly); s2 `Touch_KillEnemy:84817` + `Enemy_Points` ladder semantics (reference); our `TouchResponse` handler contract (`collision.asm:11-17`); §4.9 killed-bit API (`entity_window.asm` — find the "mark killed" entry the despawn path uses); #7's BCD add helper if landed (else tagged local `abcd` chain).
- [ ] **Step 2: Implement.** `Touch_Enemy`: player attacking posture (rolling/jumping status bits per damage spec §2 gate order) → `Badnik_Die(a3)`, rebound branch tagged for #4 (or call #4's if present) ; not attacking → the hurt path (#4's `Touch_Hurt` entry or its stub). `Badnik_Die`: chain ladder (`Chain_Bonus_Count`: 0-3→100/200/500, ≥4→1000; reset on landing — player-side flag read, or timer fallback tagged), BCD score add, `CreateEffect_Simple` explosion (anim ends `AF_DELETE`), killed-bit via the §4.9 entry, animal hook = tagged `rts` stub, `DeleteObject`. Chain count reset wired where the damage spec's landing code lives (or the timer fallback if #4 absent).
- [ ] **Step 3: Verify + commit.** Oracle with the Task-2 fixture given `COLLISION_ENEMY`: jump on it → explosion + score += 100 (BCD probe) + object gone + killed-bit set (scroll away and back — no respawn); chain: 2 kills in one jump → 100+200. `feat(engine): Touch_Enemy badnik side — kill, chain score, explosion, killed-bit`

### Task 5: behavior_gen.py + param bundles

**Files:**
- Create: `tools/behavior_gen.py`, `tools/tests/test_behavior_gen.py` (+ fixtures incl. golden), `games/sonic4/data/editor/behaviors/` (patrol.behavior.json, shooter.behavior.json, orbiter.behavior.json authored here even though badniks land in Task 6)
- Modify: `games/sonic4/data/editor/objects.json` (behaviors + param schemas), `build.sh` (run BEFORE ojz_entity_gen.py), `tools/ojz_entity_gen.py` (consume rewritten subtypes — read the bundle map file, not the raw placement subtype)

- [ ] **Step 1: Research.** Spec §6/§7 in full; `ojz_entity_gen.py` end to end (validation, emit, where subtype flows); the exact op encodings as landed in Tasks 2-3 (the contract — transcribe the byte layouts into the generator's assembler); `SST_CUSTOM_SIZE` and BehaviorV size for the fit gate.
- [ ] **Step 2: Failing tests.** Gate fixtures: unknown op/event/archetype, param out of declared range, dangling jump label, loop depth >1, >256 bundles for one type, BehaviorV+locals overflow, die-chain spawn count > MAX_SPAWNS_PER_FRAME. Golden: patrol.behavior.json → exact byte stream. Bundle test: 3 placements with 2 distinct param sets → 2 bundles, subtypes rewritten 0/1/0, bundle table bytes exact. FAIL first.
- [ ] **Step 3: Implement.** Compile scripts (symbolic steps → bytes, labels resolved), emit `data/generated/behaviors/behavior_bank.asm` (streams + per-archetype bundle tables + native-table externs) + `behavior_bundles.json` (placement→bundle map for ojz_entity_gen). `ojz_entity_gen.py` change: when a placement's typeId has a param schema, take subtype from the bundle map (hand-set subtypes remain valid for schema-less types). Wire build.sh ordering. All tests PASS; build green.
- [ ] **Step 4: Commit.** `feat(tools): behavior_gen — script compiler, param bundles, subtype rewriting`

### Task 6: The three example badniks

**Files:**
- Create: `games/sonic4/objects/badnik_patroller.asm`, `badnik_shooter.asm`, `badnik_orbiter.asm` (thin: objdef + BehaviorV locals + `jsr Behavior_Tick` + `jmp Draw_Sprite`), TEMP art/mappings/anims under `games/sonic4/data/` (sonic_hack donor art where it fits, else placeholder)
- Modify: `games/sonic4/data/objdefs/test_objects.asm` (add three, DELETE ObjDef_Enemy), delete `games/sonic4/objects/test_enemy.asm`, `games/sonic4/data/editor/objects.json` (three entries + schemas: patroller {speed, range}, shooter {trigger_box, fire_rate, proj_speed}, orbiter {orbit_radius, fan_count}), place all three in OJZ act 1 sections via the placement JSONs (respect daemon rules: coordinate with user if the watched tree must change — placements live in `data/editor/ojz/act1/section_N.objects.json` which IS daemon-watched; do this step with the user aware)
- Note: placements in the daemon-watched tree — make these edits in one sitting and let the daemon commit them as usual; do not fight it.

- [ ] **Step 1: Research.** The behavior documents authored in Task 5 (they are the source); `test_emitter.asm`/`test_particle.asm` (projectile/effect pattern); DPLC/mappings pipeline for the TEMP art; damage spec monitor pattern NOT in scope.
- [ ] **Step 2: Implement.** Patroller: MOVE = `loop{ move_until EV_EDGE; turn }`, params speed/range → bundle. Shooter: ACT = `wait_event EV_ONSCREEN; loop{ wait_event EV_PLAYER_NEAR; set_anim ATTACK; fire proj,aim,0,$0300; wait fire_rate }`; projectile = effect-pool child, COLLISION_HURT. Orbiter: init native op spawns 2 linked orbit children; ACT fires a 3-shot `sequence` fan on player-near. All three: COLLISION_ENEMY, death chain live. Build green incl. generators.
- [ ] **Step 3: Verify + commit (DURING MOTION).** Oracle circuit: patroller turns at real ledges incl. section-boundary platforms; shooter fires player-ward from all approach angles, resumes idle; orbiter children track parent, fan is even, killing parent cleans children (sibling walk); all three die correctly with chain bonus; respawn semantics (killed → gone until reload). `feat(game): three example badniks on the behavior sequencer; test_enemy retired`

### Task 7: Aurora properties panel + MCP tools

**Files (aurora repo — separate git):**
- Modify: `src/core/model/s4-types.ts` (ObjectPlacement + `params?: Record<string,number>`; ObjectDef.properties schema type), `src/core/editing/commands.ts` (`set-object-props`), `src/renderer/components/PropertiesPanel.tsx` (editable form), `src/renderer/hooks/useProject.ts` (params round-trip — free via JSON), `src/main/editor-methods.ts` + `src/renderer/agent/agent-handler.ts` (`get_object_props`, `set_object_props`, `list_behaviors`, `assign_behavior`)
- Delete: the stale TS entity asm exporter path (`core/export/entity-data.ts` emission from saveProject — Python is sole authority per spec §8)

- [ ] **Step 1: Research.** The D9 Aurora research findings hold (PropertiesPanel read-only at :44-52, commands whole-object, properties field dead) — re-verify lines; Task 5's schema format (the contract); design #6/#7 tool descriptor conventions.
- [ ] **Step 2: Failing tests.** Vitest: schema-driven form model (defaults + overrides resolve; out-of-range rejected); `set-object-props` undo restores prior params; save/load round-trips params. FAIL first.
- [ ] **Step 3: Implement.** Schema type `{name, type:'int'|'enum', min, max, default, options?}` read from objects.json properties; PropertiesPanel form (typed inputs, reset-to-default, dirty indicator); command routes through history; retire the TS asm export (save writes JSON only); MCP handlers per convention. Tests PASS.
- [ ] **Step 4: Verify + commit (aurora).** Edit a shooter's fire_rate in Aurora → save → aeon rebuild → behavior visibly changes in oracle; MCP `set_object_props` round-trip + one-step undo. `feat(objects): per-placement param editing + behavior tools; TS entity export retired`

### Task 8: Profiler checkpoint + soak + docs + merge

**Files:**
- Modify: `docs/ENGINE_ARCHITECTURE.md` (§3.6 extended: behavior sequencer as-built alongside anim events; §3.4 Touch_Enemy no longer stub; §3.7 params-via-bundles; angle math section), `docs/DEFERRED_WORK.md` (badnik-workload profiler entry updated with measured result; visual behavior editor + rand op + boss pass as deferred entries), `docs/superpowers/2026-07-02-design-week-queue.md` (log — week complete)

- [ ] **Step 1: Profiler checkpoint.** Dense fixture: 12+ live behavior objects (mix of all three) + max scroll — `Lag_Frame_Count` must hold baseline over a 5-minute soak; if it lags, STOP and build the §8.5 cycle profiler before optimizing (the spec's named trigger). Record the measurement in DEFERRED_WORK.
- [ ] **Step 2: Determinism check.** Scripted input run twice from reset → `emulator_state_hash` equal at frames 600/1200/1800.
- [ ] **Step 3: Docs + merge.** ARCH rewritten as-built (clean-not-bolted-on); queue log marks design week EXECUTION-READY across #7-9; `git checkout master && git merge --ff-only feat/object-behaviors`; build green on master. Aurora merged separately.

---

## Self-review (done at write time)

- **Spec coverage:** §3 core/ops→T2/T3 (angles §3.5→T1); §4 badnik contract→T4; §5 boss seams = format decisions in T2 (events reserved, resume slot) — no build task by design; §6/§7 generator+bundles→T5; §8 Aurora→T7; §9 examples→T6; §10 tagging enforced per task; §11 testing→distributed + T8 checkpoints; §12 order followed (M→B→K→G→E→A).
- **Placeholders:** none; TEMP art/animal-hook/rebound-branch tags are intentional spec'd seams with owners named (#4, content=user).
- **Type consistency:** `BehaviorV` fields (bv_*) uniform T2-T6; `BOP_*`/`EV_*` names uniform T2/T3/T5 (generator transcribes T2-T3 encodings); `Badnik_Die` defined T4, called T3 (`BOP_DIE`); bundle map filename `behavior_bundles.json` consistent T5/T6; `Behavior_Tick` contract (preserve a0/d7) stated T2, relied on T6.
