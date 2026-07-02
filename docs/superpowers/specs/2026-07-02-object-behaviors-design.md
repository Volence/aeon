# Reusable Object Behaviors — design spec

**Date:** 2026-07-02
**Status:** Approved by user (design dialogue 2026-07-02)
**Extends:** the object system (SST v2, `sst_custom` 34 B, objdef archetypes,
`Load_Object`, §4.9 entity window + killed bits), the children/effects API
(`CreateChild_*`, `CreateEffect_*`), the animation event-tag system (§3.6 —
`AF_CALLBACK`/`AF_COLLISION`/`AF_SET_FIELD`/`AF_DELETE`), the collision
dispatch (`TouchResponse`, handler stubs), and design #8's sequencer idiom
(its §5 note reserved the control-flow shape for this design).
**Depends on:** design #4 (player-side `Touch_Enemy` rebound is #4's; the
badnik-side kill/award/explosion is OURS — #4's spec says so verbatim);
design #3's `Camera_Target` convention (aim ops target it, `Player_1` until
then); designs #6/#7/#8's Aurora document/generator/MCP conventions.
**Design-week queue:** #9 (last).

---

## 1. Goal & user-ratified scope

Delete the classic-Sonic duplication where every badnik hand-rolls
wait-onscreen → patrol → trigger → fire → death (S2 does this inline ~40
times): behaviors become **composable data** — a lightweight two-track
per-object byte-opcode sequencer, primitives as opcodes, params attached per
placement in Aurora.

**V1 (user decision: skeleton + examples, not full features):** the sequencer
core built for the end-state, a small honest op vocabulary, and **three
example badniks** proving composition — Patroller (patrol/turn-at-edge),
Shooter (onscreen + player-near trigger + aimed fire), Orbiter (child chain +
sequence-mode fan; the multi-part smoke test) — plus the shared death chain.
**Boss seams designed, not built** (user decision): phase = ACT-script swap,
multi-part = existing parent/sibling links, health/threshold/hit events
reserved in the enum, conductor = bodiless object on an ACT script; the
record format assumes nothing single-part or phase-free.

**Architecture (user decision: approach B).** Rejected: A (native subroutine
library only — halves duplication, nothing Aurora-authorable); B-single-track
(movement and firing interleave — composition suffers); C (Batman full
direct-threaded — 2-4× denser but undebuggable scripts, fragile SP-restore
unwinding; density is not our constraint).

**Non-goals:** bosses themselves (a later boss pass on these seams), a visual
behavior-step editor in Aurora (JSON-first v1, same interim posture as #7's
screens), a `rand` op (reserved; per-object LFSR seeded from spawn X/Y when
it lands), platform/gimmick migration to behaviors (candidates later; solids
stay native), water/badnik-specific art (TEMP placeholders; animal spawn is a
TEMP-flagged hook — content is the user's).

## 2. Research grounding (checklist discharged)

All 8 disassemblies + online + modern, 5 subagents, 2026-07-02:

- **Batman & Robin (verified in disassembly):** two-level threaded interpreter
  — the `$0820` yield saves the script PC into the SST and returns: **the PC
  is the state**, no routine counters. Adopted as the core idea. Its FORM is
  rejected: word-per-opcode handler addresses defeat disassembly/debugging;
  SP-restore mid-update unwinding is brittle (our research notes independently
  recommend against both). Dispatch cost benchmark: ~16 cyc/op threaded; our
  byte-opcode table costs ~8-24 more — irrelevant at 20-30 objects.
- **Sonic family:** every badnik = permutations of wait-onscreen / patrol /
  proximity / timed-fire / shared-death. The `wait_timer`+`wait_addr` idiom
  (S3K/S.C.E. `Obj_Wait`, `ObjCheckFloorDist_DoRoutine` edge callbacks) is the
  embryonic sequencer; S3K `ChildObjDat_*` blocks already embed a movement
  routine pointer as data; s2/sonic_hack bosses run a mini animation-script
  bytecode with an advance-phase command. Shared-death precedent:
  `Touch_KillEnemy` + `Enemy_Points` (10/20/50/100 ladder) + explosion+animal
  object. Subtype = the universal per-instance param (832 uses in S3K).
- **Treasure:** multi-part bosses are entirely link-fields ($58/$5C — our
  `parent_ptr`/`sibling_ptr`); no bytecode. Vectorman's split-stub model
  rejected (hardcoded data blocks don't scale to interchangeable archetypes).
  Ristar's $C01E is input-injection (cutscene lever, wrong for per-object AI);
  its event-tagged frames are already ours (§3.6).
- **Modern (converged):** FSM/coroutine is the industry verdict for this enemy
  class (Game AI Pro; BTs re-evaluate from the root — wasted cycles);
  **two parallel tracks** (movement ‖ action) is what shipped authoring tools
  converged on (Danmakufu tasks, NESmaker movement‖action, GB Studio);
  depth-1 interrupt beats a stack for fixed-memory (Galaga/S3K precedent:
  swap the pointer, save one resume slot); **BulletML's four angle modes**
  (absolute/aim/relative/sequence) cover essentially all shipped 2D projectile
  patterns; LDtk's typed param schema + per-placement overrides is the editor
  pattern; GBVM proves editor-events→bytecode on 8-bit. Aim without divide:
  256-angle system, octant-folded atan2 table (~528 B) + shifts (plutiedev/
  Coranac). Determinism: frame counts only, per-object PRNG seeds, all
  interpreter state in the object block.
- **Aeon substrate (verified):** anim event tags shipped (`AF_*` incl.
  callback/collision/field-poke/delete); `CreateEffect_*`+`AF_DELETE` IS
  death-into-explosion; `test_enemy` is the hand-coded patrol; dynamic pool
  culls at 768/512 px (wait-onscreen interacts with culling — §4.3); the
  **entity word is full** (3 flags + 5 type + 8 subtype; 6-byte stride baked
  into the entity-window walkers) — the param problem, solved in §7 without
  a format break; behavior state must be **relative/re-derivable** (ARCH
  §3.7 floating-origin contract).

## 3. Sequencer core (engine — `engine/objects/behavior.asm`)

### 3.1 Per-object state (in `sst_custom`, via `BehaviorV` + `objvarsCheck`)
Two tracks — MOVE and ACT — each `{pc.w (offset into the behavior bank,
0 = idle), wait.w, loop.b}`; one shared `resume_pc.w` (depth-1 interrupt);
`facing/angle.b`; `params.w` (bundle pointer, §7); ≈14 bytes, leaving ~20 for
op locals and per-behavior vars. Objects run the sequencer by calling
`Behavior_Tick` from their (thin) objroutine; non-behavior objects are
untouched.

### 3.2 Execution
`Behavior_Tick(a0=SST)`: for MOVE then ACT — if waiting, `subq` + return
path (the dominant per-frame cost); else fetch byte opcodes off a jump table
until the track yields (wait/wait-event/end). The saved PC is the state.
Contract: preserves a0/d7 (object-loop rule); ops may use the documented
scratch set.

### 3.3 Events & interrupts
Event enum: `EV_ONSCREEN`, `EV_OFFSCREEN`, `EV_PLAYER_NEAR` (box params),
`EV_LANDED`, `EV_WALL`, `EV_EDGE`, `EV_ANIM` (pulsed by `AF_CALLBACK` — the
animation bridge), `EV_HIT` + `EV_HEALTH_LOW` (reserved boss seams).
`on_event(ev, label)` arms a per-track vector; fire → PC saved to
`resume_pc` → handler; `resume` restores. Depth 1 by design.
**Culling note:** beyond the 768/512 px cull the object doesn't tick at all;
`wait_event EV_ONSCREEN` therefore means "on-screen per render flag," and
spawn-time init runs on entity-window load — the classic semantics.

### 3.4 Op vocabulary (v1)
Flow: `end · wait N · wait_event ev[,params] · branch rel · loop N/endloop ·
on_event ev,label · resume · native idx` (per-game objroutine table — the
boss/oddball escape hatch; scripts stay thin over 68k).
Movement: `set_vel mode,angle,speed` (modes: **absolute / aim / relative /
sequence** — aim = atan2 to `Player_1`→`Camera_Target`; sequence = relative
to previous fire, fans/spirals free) · `move_until ev` · `turn` (neg x_vel +
flip) · `home speed,turn_rate` (re-aim every N frames).
Lifecycle: `fire archetype,mode,angle,speed` (children API;
`MAX_SPAWNS_PER_FRAME` honored) · `spawn archetype,dx,dy` · `set_anim id` ·
`set_collision type` · `die style`.
Reserved: `rand`, boss phase-swap op. Opcode space is byte-wide; ≥ $80
reserved for future game-registered ops (the #7/#8 handler-table convention).

### 3.5 Angle math (engine — `engine/system/angles.asm`)
256-angle circle: sin/cos word table (cos = sin + $40 offset), octant-folded
atan2 table (~528 B, shift-normalized inputs, no division), velocity =
speed × sin/cos via table + shifts. Serves behaviors, future bosses, and any
engine consumer.

### 3.6 Rules baked in
**Floating-origin:** no op stores absolute world coords; patrol is
counter/edge-driven, aim computes deltas at fire time (ARCH §3.7 contract
holds by construction). **Determinism:** frame counts only; all interpreter
state in the SST (resumable; replay/rollback-ready); no globals.

## 4. The badnik contract (owned here)

`Touch_Enemy` implemented (engine): attacking-posture test → kill; else the
player-hurt path (#4's machinery). Kill →
- chain-bonus score ladder (classic 100/200/500/1000 as BCD, #7's helpers),
- explosion via `CreateEffect_*` (anim ends in `AF_DELETE`),
- killed-bit set through the §4.9 entity window (respawn semantics unchanged),
- animal spawn hook — TEMP-flagged, content pending.
`COLLISION_BOSS` remains a stub with its seam documented (health byte in
`BehaviorV`, hit-flash, `EV_HIT`/`EV_HEALTH_LOW`).

## 5. Boss seams (designed, not built)

Phase transition = ACT-PC swap (op or native — the S3K pointer-swap pattern
as data); multi-part = `parent_ptr`/`sibling_ptr` + `CreateChild_Complex`/
`_Linked` (strategies already mapped in ARCH §3.3); conductor = bodiless
object running an ACT script (S3K event-control precedent); health/threshold
via the reserved events. A later boss design composes these; nothing here
needs reshaping.

## 6. Behavior documents & generator

### 6.1 Documents (`games/sonic4/data/editor/behaviors/*.behavior.json`)
Named behaviors: move/act scripts as symbolic step lists
(`{"op":"wait_event","event":"player_near","box":[96,64]}`), param
declarations (name, type, range, default — LDtk pattern), event bindings.
`objects.json` entries gain `behaviors: {move, act, events}` + the param
schema (the dead `properties` field gets its job). Placements keep
human-readable `params` maps.

### 6.2 `tools/behavior_gen.py`
Validate → compile → `data/generated/behaviors/` (byte streams + label
offsets + per-archetype **param bundle tables**), nonzero exit on violation.
**Param bundles (§7):** collect distinct param sets per archetype across all
placements, dedup, emit bundle tables, **rewrite each placement's subtype to
its bundle index** before `ojz_entity_gen.py` runs (>256 bundles/type =
error). Gates: unknown op/event/archetype/behavior, param range, jump
targets, loop depth, `BehaviorV` fit vs `SST_CUSTOM_SIZE`, die-chain spawn
count vs `MAX_SPAWNS_PER_FRAME`. Pytest fixtures per gate + golden
round-trip.

## 7. Per-placement params without a format break

The 16-bit entity word is full and the 6-byte stride is baked into the
entity-window walkers — widening it touches five components. Instead:
**subtype-as-param-bundle-index.** Aurora edits typed params per placement;
the generator dedups identical sets into per-archetype bundles and assigns
indices; `Load_Object`'s existing subtype copy is untouched; behavior init
resolves `subtype → bundle table → params.w` pointer. Unlimited param width,
zero entity-format change, ≤256 distinct bundles per archetype (ample), and
the killed-bit/`MAX_LIST_ENTRIES` machinery is untouched. Human-readable
params never leave the JSON; packing is a compiler concern.

## 8. Aurora (map mode — no new mode)

- PropertiesPanel becomes an editable form: archetype schema → typed fields
  (dropdowns/ranges), instance overrides over defaults, reset-to-default;
  subtype/variant readout. New `set-object-props` command (one undo step).
- Behavior picker on library entries (assign move/act/events refs).
- The stale TS entity asm exporter is **retired**; the Python generator path
  is sole authority (closes the known TS/Python flag-emission divergence).
- MCP/Aether tools per convention: `get_object_props`, `set_object_props`,
  `list_behaviors`, `assign_behavior`.
- Behavior scripts stay JSON-in-your-editor for v1; a visual step editor is
  a natural later pass once the schema is proven.

## 9. V1 examples (the deliverable's proof)

Three badniks in OJZ act 1, placed via Aurora with distinct param bundles:
- **Patroller** — MOVE: `loop{ move_until EV_EDGE; turn }`; die-on-touch.
  (Replaces hand-coded `test_enemy` — which is deleted, clean-not-bolted-on.)
- **Shooter** — ACT: `wait_event EV_ONSCREEN; loop{ wait_event
  EV_PLAYER_NEAR; set_anim ATTACK; fire proj,aim,0,speed; wait N }`.
- **Orbiter** — spawn-time child chain + `sequence`-mode 3-shot fan; the
  multi-part/boss-seam smoke test.
All three exercise the shared death chain. Projectile + explosion art = TEMP
placeholders where sonic_hack donor art doesn't fit.

## 10. Engine/game tagging (design-#5 inputs)

**Engine:** sequencer core + op handlers + event system, angle math,
`Touch_Enemy` machinery, bundle-table reader, `BehaviorV` layout. Zero game
symbols (grep gate). **Game:** behavior documents + compiled bank, the
native-routine table, object library + schemas, the three badniks
(objdefs/art/anims), score values, animal hook.

## 11. Testing

Build: generator gates + golden. Runtime (foreground oracle): each badnik
verified **during motion** (patrol across section boundaries + at ledges;
aim accuracy at octant boundaries via RAM-probed velocities; killed-bit
respawn semantics across entity-window reload; death chain under
spawn-cap pressure); determinism (identical input script twice →
`emulator_state_hash` equal); the **profiler checkpoint** — a dense fixture
(12+ live behavior objects) must hold `Lag_Frame_Count` at baseline; this is
DEFERRED_WORK's named trigger workload, so if it lags, build the §8.5 cycle
profiler before optimizing blind.

## 12. Sequencing & risks

**Plan order:** angle math → sequencer core + flow ops → movement/combat ops
+ Touch_Enemy/death chain → generator + bundles → three badniks (+ delete
test_enemy) → Aurora panel + tools → soak/docs/merge.

**Risks:** `sst_custom` pressure (14 B sequencer + params pointer leaves ~18
for op locals; `objvarsCheck` catches overflow per archetype — complex
archetypes fall back to `native`); event-check cost (player-near boxes are
per-frame compares — keep the event set armed-only, not polled-always);
subtype-bundle rewriting must run before `ojz_entity_gen.py` and after any
hand-edit of placements (build.sh ordering, documented); anim-event ↔
behavior-event double-firing (single bridge: `AF_CALLBACK` pulses `EV_ANIM`,
nothing else crosses); the #8 sequencer stays separate machinery per its
spec note — op sets did NOT converge (visual/palette sinks vs object verbs),
merging is explicitly declined.
