# Per-Character Dispatch + Tails & Knuckles — design spec

**Date:** 2026-07-02
**Status:** Approved by user (design dialogue 2026-07-02); pending spec review
**Extends:** the §5 player system (`2026-06-12-player-system-design.md`) — the deferred
"per-character dispatch-table indirection" + Tails + Knuckles items
**Design-week queue:** #3 of 5

---

## 1. Goal & decisions

Make the player system a **roster**: Sonic unchanged, Tails (playable + flight +
appendage + CPU follower), Knuckles (glide/slide/climb/ledge), all through one
shared movement core. User-ratified decisions:
1. **Ability-hook architecture** (Mania's shape), NOT per-character state tables:
   one shared `Player_States` machine containing all states; the only per-character
   code switch is a `CharacterDef` with constants + one ability-hook vector.
   Evidence: S3K duplicates its entire movement pipeline 3× differing only by
   constants + one ability each; S.C.E. never solved it (dropped the characters);
   Mania/MoonCast/AIR all converged on hook-plus-data.
2. **CPU Tails = classic + AIR fixes** (classic-faithful ≠ bug-faithful): S3K's
   machine and timings, with Sonic 3 AIR's proven quality fixes designed in.

**Non-goals:** Sonic-carry (needs object_control/damage plumbing — design #4 hook),
Super forms, water physics rows (water spec later; glide/climb ignore water by S3K
design — kept), character-select UI (§9.13; DEBUG hotkey until then), Tails/Knuckles
final art (engine uses clearly-tagged placeholders; asset sourcing is the user's —
Tails art/DPLC staged in-repo but mappings MISSING; no Knuckles assets exist).

## 2. CharacterDef — a character is data

ROM struct, one per character, in `games/sonic4/player/<name>.asm`:
- `cd_phys` → physics row (existing 8-word PhysTable shape; Tails' ground row =
  Sonic's verbatim, Knuckles differs ONLY in jump force $680→$600 per SPG/S3K),
- `cd_sizes` → stand/roll W×H radii (Tails stands 9×15; Knuckles 9×19) + ability
  overrides (Knuckles glide/slide/climb 10×10),
- `cd_mappings`, `cd_dplc`, `cd_artbase`, `cd_vrambase`, `cd_animtable` (the ANIM_*
  contract is already per-slot via `SST_anim_table` — 11 universal ids, per-character
  tables like `Ani_Sonic`),
- `cd_ability` → the ability-hook vector (called from the air state on jump-press:
  Sonic → `rts` today, dropdash/insta-shield slot in later; Tails → flight entry;
  Knuckles → glide entry),
- `cd_flags` → capability bits (reserved).

`Character_ID` (new RAM byte) + a `CharacterDefs` index table; `Player_Init` caches
the def pointer per slot. The four hardwired Sonic sites
(`player_common.asm:119/154/259/405` as of audit) become def reads;
`Sonic_InitAssets`/`Sonic_LoadArt` shrink into data + a tiny shared loader
parameterized by the def. `tails.asm`/`knuckles.asm` parallel `sonic.asm`.

## 3. Shared machine gains the ability states

`PSTATE_FLY`, `PSTATE_GLIDE`, `PSTATE_SLIDE`, `PSTATE_CLIMB`, `PSTATE_LEDGE` join
`Player_States` with normal enter/exit hooks (enter hooks own radii/status bits, as
today). The "curled states last" ordering assert is reworked to an explicit
curled-set test (glide/slide are attacking-but-not-curled; the ball test at
`Player_Display` generalizes). States are reachable only via the owning character's
ability hook — no per-character table needed.

## 4. Per-slot globals + two-player correctness

- `Player_Phys` (16 B), `Player_Quadrant`, `Player_JumpBuffer` become per-slot
  blocks indexed by slot (a4 already abstracts the physics base — consumers
  unchanged).
- The position ring (`Player_Pos_Ring`/`Stat_Ring`, already recorded 64-deep every
  frame) stays SINGLE-instance by design: it records the leader; it is the AI's
  oracle. Recording moves behind "am I the leader" (slot 0 today).
- Camera gains `Camera_Target` (pointer, default `Player_1`) replacing the three
  hardcoded `lea (Player_1)` sites; path-swap likewise.
- Touch-response standing/pushing-bit fix: select `ST_P1_*`/`ST_P2_*` by loop index
  (constants exist; `collision.asm:205` hardcodes P1 — audit-confirmed bug).
- `Player_2` slot + all three engine loops are already two-player-ready (audit).

**SST budget:** PlayerV uses 16 bytes; Tails needs ~2 (flight ramp + reuse of the
fuel byte in `air_left`-style reserve), Knuckles ~4 (glide angle, glide speed word,
climb pacing) — per-character fields UNION over the free region (one character per
slot). Fits current 18-free and post-floating-origin-F2 16-free.
**Sequencing rule:** this design and floating-origin F2 both relayout the SST
metadata block — whichever executes first carries the section_id relayout; the other
rebases onto it. (Cross-referenced in both specs.)

## 5. Tails

**Flight (`PSTATE_FLY`)** — S3K-exact: entry from the ability hook (airborne
jump-press); thrust `y_vel -= $20`/frame while `y_vel >= -$100`, ramp capped 32
frames/flap; coast gravity `+8`/frame; fuel 240 decremented every other frame
(≈8 s), tired = flap disabled ONLY (physics unchanged) + tired anim/sfx cadence
(16-frame); screen-top clamp (camera min + $10). **One deliberate fix (SPG-documented
S3K trap):** ceiling hit while thrust-gravity active zeroes y_vel and strands the
gravity flip — reset to coast gravity on ceiling contact. Flight ignores water
constants (S3K design — kept; revisit in the water spec).
**Anims:** ANIM contract gains `ANIM_FLY`/`ANIM_FLY_TIRED` (universal ids; Sonic's
table points them at safe fallbacks — table stays ANIM_COUNT-asserted).

**The appendage** — a child object (`CreateChild_FlipAware`): reads the parent via
`parent_ptr` (state/gsp/status), maps parent anim → tail anim via a lookup table
(S3K's `Obj_Tails_Tail_AniSelection` pattern), copies x/y/angle/priority/flip each
frame, own DPLC. Spawned at Tails init into a slot that cannot be culled while the
player lives (plan resolves pool choice; parent-death deletes it via the child API).

## 6. CPU Tails — an input filter

Runs before `Player_Main` for the follower slot; writes a virtual controller word
the movement core consumes exactly like real input (the core never knows the AI
exists — Mania's `stateInput` swap, S3K's `Ctrl_2_logical` injection). Global RAM
state (follower-singleton like every reference): routine, idle timer, flight timer,
target. S3K machine + timings: fly-in at leader-x / leader-y − 192; follow reading
the ring **17 frames behind**; auto-jump every 64 frames when stuck/leader above;
despawn after 300 frames off-screen → fly-in respawn; any P2 input = manual control
for 600 frames. **AIR fixes baked in:** ±4 px landing tolerance (or leader
jump-press) instead of exact-pixel equality (kills the orbit-forever bug); keep-up
feed-forward `target_x += leader_x_vel >> 7` (survives chase sequences); no
auto-jump when |dx| < $30; facing + spindash-charge cosmetic sync at rest. Respawn
must handle floating-origin rebases (positions shift under it — it reads live
leader coords, and design #2's shift-list note covers the ring buffer: the ring
holds world coords and **joins the rebase shift-list** — registered there).

## 7. Knuckles

- **Glide (`PSTATE_GLIDE`)**: entry via ability hook (kills upward momentum:
  `y_vel += $200`, clamp ≥0); start `gsp = $400` toward facing; accel +8/frame
  below $400, +4/frame above, cap $1800; turn angle steps ±2/frame (64-frame
  reversal), `x_vel = cos(angle)·gsp` — speed preserved through turns; parachute
  gravity ±$20 toward terminal $80; offensive hitbox (design-#4 hook tag); release
  → fall with `x_vel /= 4`.
- **Slide (`PSTATE_SLIDE`)**: glide-into-flat-ground; friction $20/frame to stop →
  get-up (move_lock $F); ledge-drop check (floor dist ≥ 14 → fall); dust + sfx
  cadence 8.
- **Climb (`PSTATE_CLIMB`)**: wall-catch from glide via push-flag + wall/floor
  verify (12 px window); latch-X detach guard; 1 px/frame up/down through the
  existing sensor layer (`GetDistanceFromWall` equivalent on our sensors); top
  camera clamp; climb-down floor-stop (~19 px); jump-off = away $400 / up −$380.
- **Ledge (`PSTATE_LEDGE`)**: the 4-step scripted pull-up
  `{frame,dx,dy,6-frames}×4` (S3K table), ends standing.
- Water: glide/climb constants unaffected (S3K design — kept, documented).

## 8. Phasing

- **C1 — Dispatch refactor.** CharacterDef + Character_ID + per-slot globals +
  Camera_Target + P2-bit fix + ability hook (Sonic → rts). GATE: Sonic plays
  pixel-identically (input-script regression vs master).
- **C2 — Tails playable + appendage.** tails.asm def, flight state, anims
  (placeholder mappings, tagged), appendage child. DEBUG hotkey selects character
  at init.
- **C3 — CPU Tails.** Input filter + fly-in/follow/respawn machine + AIR fixes;
  P2 slot spawns as follower.
- **C4 — Knuckles.** knuckles.asm def (placeholder art), glide/slide/climb/ledge.
All engine except the per-character data files (design-#5 tagging).

## 9. Verification

- C1: recorded-input regression — same inputs, byte-compare player SST trajectory
  vs pre-refactor master over a full OJZ circuit (the refactor must be invisible).
- C2: flight matrix in oracle (thrust/coast/tired/ceiling-fix/top-clamp), appendage
  anim mapping spot-checks per state, DPLC watch.
- C3: follower soak — leader circuits at max scroll: no orbit at rest (the ±4 px
  fix observable), keep-up through the fastest OJZ stretch, despawn/fly-in cycle,
  idle takeover after 600 frames, manual override; across a forced floating-origin
  rebase if #2 has landed (ring registered in its shift-list).
- C4: glide arc/turn/cap numbers probed via RAM watch; slide friction stop; climb
  latch/detach; ledge script frames; 10×10 size swap asserts.
- Throughout: `Lag_Frame_Count` vs baseline (the AI filter + appendage are the new
  per-frame costs; budget ~1-2% frame).

## 10. Risks & open parameters

- **PSTATE ordering asserts** — the curled-set rework touches `Player_Display`'s
  ball test; enumerate all `>= PSTATE_JUMP` compares during C1 research.
- **Appendage pool choice** — must never cull while player lives (plan resolves).
- **Anim id growth** — ANIM_COUNT grows (FLY, FLY_TIRED, GLIDE, SLIDE, CLIMB,
  LEDGE, GETUP reuse); every character table re-asserted; Sonic fallbacks defined.
- **Knuckles wall sensing** — S3K uses dedicated wall casts; ours must come from
  the §5 sensor layer — C4's research step maps the equivalence before coding.
- **SST collision with floating-origin F2** — sequencing rule in §4.

## 11. Research provenance

Three-agent pass 2026-07-02: aeon audit (4 hardwired sites + 6 singletons, PlayerV
16/34 — header + ARCH figures stale, pos-ring recorded & unconsumed, child API
sufficient, P2 loops ready, camera/path-swap/standing-bit P1-hardcoded); S3K/S.C.E.
(all constants above with sonic3k.asm cites; S3K = 3× duplicated pipelines,
Character_Speeds table used in competition only; S.C.E. = Sonic-only with latent
hooks); web (SPG values incl. per-character table, AIR tails_ai.lemon fixes, Mania
decomp stateAbility/stateInput architecture, MoonCast/SWN/Orbinaut survey; one
prompt-injection page encountered and discarded during TCRF fetch).
