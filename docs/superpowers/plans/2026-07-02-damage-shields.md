# Damage / Shields / Loss-Rings / Death Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make damage real: hurt/i-frames, 32-ring scatter (dedicated pool), death→respawn with star posts, the full S3K shield kit, and monitors.

**Architecture:** D1 (Tasks 2-4): PSTATE_HURT + i-frame/flicker/gate + the loss-ring pool + spikes + a test hazard. D2 (Tasks 5-6): PSTATE_DEAD + level-reload restore contract + star posts. D3 (Tasks 7-8): shield state/display/immunity + the four active abilities + ring magnet. D4 (Tasks 9-10): monitors + integration soak + docs/merge. Spec: `docs/superpowers/specs/2026-07-02-damage-shields-design.md` (APPROVED). All S3K constants in the spec §2-§6 — the plan repeats the load-bearing ones inline.

**Dependencies:** design #3's C1 (`cd_ability` hook + child API usage patterns) should land first for D3; D1/D2 only need current master + the `Touch_Hurt` seam. If #3 hasn't landed, D3's ability entry point is a temporary direct call from the air state, tagged for the hook.

**Tech Stack:** 68000 (AS), oracle MCP. Standing rules: research step first per task (anchors drift); DEBUG build; runtime-boot after ram.asm changes; exact-path commits; branch `feat/damage-shields`; merge at Task 10; verify during MOTION.

---

### Task 1: Branch + baseline + test hazard

- [ ] **Step 1: Research.** Read `engine/objects/collision.asm` in full (the dispatch, handler register contract d0-d3/a2/a3, the post-handler position reload at :79-81), `engine/objects/rings.asm` (RingCollision + buffer format), `games/sonic4/player/player_common.asm` PlayerV + `Player_Death_Pending` set site (~:689), `engine/objects/core.asm` Alloc*/DeleteObject + ObjectMove, `games/sonic4/objects/test_particle.asm` (the effect template), `docs/superpowers/specs/2026-07-02-damage-shields-design.md` end to end.
- [ ] **Step 2: Branch + test hazard.** `git checkout -b feat/damage-shields`. A minimal `test_hazard.asm` object (static, `COLLISION_HURT`, placeholder art) placed via the test objdef list — the D1 verification target. Build green, hazard visible, currently harmless (stub still `rts`). Commit.

### Task 2: D1a — PSTATE_HURT + i-frames + flicker + gates

**Files:**
- Create: `games/sonic4/player/player_hurt.asm` (PSTATE_HURT + PSTATE_DEAD shell)
- Modify: `engine/objects/collision.asm` (`Touch_Hurt`), `player_common.asm` (states table, `Player_Display` flicker, ANIM classifier ANIM_HURT), `constants.asm`, `engine/objects/rings.asm` (the recollect gate)

- [ ] **Step 1: Research.** The exact handler calling convention (a2=player a3=target, and note TouchResponse reloads player pos AFTER the handler — knockback-safe); how `Player_Display` decides to draw; where ANIM_HURT fits the classifier; whether ANIM_HURT exists (contract grows if not — re-assert all character tables per design #3 if it landed).
- [ ] **Step 2: Implement.** `Touch_Hurt`: gates in spec §2 order (`invuln_time` → shield/immunity (bits exist but shields land in D3 — the mask check is written now, reads zeros) → hurt). `Player_Hurt` entry: shield-bit branch (clear + no rings, D3 fills the bits), rings==0 → `Player_Kill` (Task 5 shell now: set Death_Pending), else scatter call (Task 3 stub: just zero the counter for now, tagged) + knockback `x=∓$200,y=−$400` (halved when `ST_UNDERWATER`), `Player_SetState PSTATE_HURT`. State body: gravity `$30` (−`$20` water), no input read, land → zero x_vel, `invuln_time=120`, getup arm, → ground state; **timeout 120 airborne frames** → force-exit (spec §7.1, comment cites SPG). Flicker in `Player_Display`: skip draw unless `invuln_time & 4` when nonzero, decrement per frame. Recollect gate in `RingCollision`: `cmpi.b #90,_pl_invuln(a2); bhs skip` — SAME field (spec §7 pitfall).
- [ ] **Step 3: Verify + commit.** Oracle vs the test hazard: knockback vector + magnitudes (RAM-watch), control locked until landing, 120-frame flicker at 4-on/4-off (frame-step), can't be re-hurt during i-frames, can't collect a placed ring until timer < 90, timeout fires when landing is denied (hazard over a pit edge). `feat(player): PSTATE_HURT — knockback, i-frames, flicker, recollect gate (D1)`

### Task 3: D1b — the loss-ring pool

**Files:**
- Create: `engine/objects/loss_rings.asm` (pool + burst + update + render), velocity tables
- Modify: `ram.asm` (pool RAM), `constants.asm`, `player_hurt.asm` (real scatter call), `games/sonic4/main.asm`

- [ ] **Step 1: Research.** S.C.E.'s `Rings_Velocity`/`Rings_WaterVelocity` tables (`Objects/Main/Rings/Rings.asm:404-462`) — transcribe as our ROM tables (32 entries × x.w,y.w each, outer 16 then inner 16, mirrored pairs baked). Our collision lookup for a point (the tile-cache collision path the player sensors use — find the cheap "floor distance at x,y" entry point) for the bounce check. The ring sprite render path (`DrawRings`) for render integration + `VRAM_RING_PLACEHOLDER`.
- [ ] **Step 2: Implement.**

```asm
; ram.asm
Loss_Ring_Pool:    ds.b LOSS_RING_MAX*LossRing_len   ; 32 * 12 = 384
Loss_Ring_Count:   ds.w 1
; structs.asm
        struct LossRing
lr_x        ds.w 1     ; world px
lr_y        ds.w 1
lr_xvel     ds.w 1     ; 8.8
lr_yvel     ds.w 1
lr_life     ds.b 1     ; 255 -> 0
lr_flags    ds.b 1     ; bit0 magnetized (D3)
        endstruct
```

  `LossRings_Burst(d0=count, a-player)`: min(count,32), fill from the table (water table + gravity select per entry when below waterline — identity today, tagged), life=255. `LossRings_Update` (per frame from the level loop): gravity `$18`, integrate, **floor check when `frame_ctr+index & 3 == 0` AND y_vel>0** (spec §7.2 — every 4 staggered): embedded → reposition + `y_vel = −(y_vel − y_vel>>2)`; kill-plane delete; life decrement, **fade flag last 16 frames** (render skips alternate frames); collect when player AABB overlaps AND `_pl_invuln < 90` → counter++, sparkle via `CreateEffect_Simple`, swap-remove. `LossRings_Render`: emit sprites via the ring path, behind player, fade-flicker honored. Wire burst into `Player_Hurt`; counter zeroed after burst regardless of pool fill (classic).
- [ ] **Step 3: Verify + commit.** Take a hit with 40 rings: exactly 32 scatter, mirrored spiral shape (screenshot during burst), outer/inner speeds probed, bounce damping ≈75%, regather works after the gate, expiry fade visible, no tunneling on flat ground across 20 bursts (count failures — expect ~0 at 4-frame cadence), burst-frame `Lag_Frame_Count` clean. `feat(engine): loss-ring pool — 32-ring scatter, bounce, regather, fade (D1)`

### Task 4: D1c — spikes

**Files:**
- Create: `games/sonic4/objects/spikes.asm` + objdef entry
- Modify: `engine/objects/collision.asm` (`Touch_SolidHurt`)

- [ ] **Step 1: Research.** ARCH's `objoff_3A` face-byte commitment (§1573-1585); how `Touch_Solid` computes the contact face (the min-penetration axis logic — reuse it); SFX id for spike hit (exists in our SFX set? else the normal hurt SFX with a TODO tag).
- [ ] **Step 2: Implement.** `Touch_SolidHurt`: run the solid push-out, THEN if the contact face matches the object's face byte → `Player_Hurt` path with the spike SFX select (by collision type, cleaner than S3K's address-range hack — S.C.E. precedent). Spikes object: static solid, face=TOP default, S3K sizes. I-frames respected by construction (the Task-2 gate).
- [ ] **Step 3: Verify + commit.** Stand-on-top hurt, side-walk-into-solid-not-hurt (face mismatch), land-during-flicker not re-hurt (the S1 bug's regression test). `feat(objects): spikes — solid+hurt with face select (D1 complete)`

### Task 5: D2a — death + respawn restore

**Files:**
- Modify: `player_hurt.asm` (PSTATE_DEAD real), the level game state (restart path), `ram.asm` (`Lives_Count`, `Saved_*` block), `engine/level/entity_window.asm` or rings.asm (the reset entry points)

- [ ] **Step 1: Research.** The level game-state init flow (what re-runs on a fresh level entry — `GameState_OJZScroll_Init` today; identify the re-enterable subset = the restore contract's vehicle); the §4.9 reset surfaces: `RingBuffer_Clear` (rings.asm:100), the collected-window/park init (`Collected_*` init path), `Ring_Counter`; camera/player seeding (`camera.asm:20-36`, Act start fields).
- [ ] **Step 2: Implement.** `Player_Kill`: PSTATE_DEAD (y=−$700, x=0, no collision, high-priority draw, camera lock flag). Past `Camera_Y+$100` → 60-frame wait → `Level_Restart`: re-seed player+camera from star-post save if active else act start; **explicit reset list** (comment block = the contract): ring buffer, ring counter, collected window + parks, loss-ring pool, invuln/shield bits, timer := saved timer (posts) else 0; `Lives_Count` decrement (word, RAM only); 0 → freeze-stub state tagged §9.13. Consume `Player_Death_Pending` in the level loop (EDGE_KILL finally works).
- [ ] **Step 3: Verify + commit.** 0-ring hit → full death → respawn at start; collected rings respawned; EDGE_KILL bottom edge kills; timer behavior; lives decrements. `feat(player,level): death plunge + level restart — the restore contract (D2)`

### Task 6: D2b — star posts

**Files:**
- Create: `games/sonic4/objects/starpost.asm` + objdef
- Modify: `ram.asm` (`Last_Star_Post`, saved block), `player_hurt.asm`/restart path (post restore)

- [ ] **Step 1: Research.** Objdef/subtype plumbing (how test objects declare subtypes); respawn-memory gating pattern (the killed/collected bitmask APIs — posts persist activation like killed badniks); child API for the spinning head.
- [ ] **Step 2: Implement.** Activation: player X crosses post with `subtype > Last_Star_Post`, box $10×$68; save id/x/y/timer; head-spin child anim; SFX; respawn-memory bit so re-entry shows activated. Restart path (Task 5) reads it. Special-stage gate = comment hook.
- [ ] **Step 3: Verify + commit.** Activate two posts in order (out-of-order ignored), die after #2 → respawn at #2 with its timer; park/window reset still correct; post stays activated across death. `feat(objects): star posts — activation, save, respawn restore (D2 complete)`

### Task 7: D3a — shield state, display child, immunity typing

**Files:**
- Create: `games/sonic4/objects/shield.asm`, shield art/anim data (S3K-sourced via the design-#3 converter if landed; else placeholder tagged)
- Modify: `constants.asm` (`SSEC_*` status_secondary bits, `SST_immunity` objdef byte), `engine/objects/collision.asm` (immunity mask in the hurt gate), objdef macro (immunity param), `player_common.asm` (pickup API `Player_GiveShield`)

- [ ] **Step 1: Research.** Design-#3 child API contracts (or children.asm directly); priority-band runtime-change rule (clear RF_PRIORITY_MASK first, constants.asm:180); where objdef bytes live (the 26-byte archetype image — a free byte for immunity? else the spare template field); VRAM region for shield art (coordinate with design-#3 Task-5's character VRAM map if landed; else carve a tagged slot).
- [ ] **Step 2: Implement.** `status_secondary` bits real (`SSEC_SHIELD/FIRE/LTNG/BUBBLE/INVINC/SPEEDSHOES`, exclusive-elemental setter in `Player_GiveShield`); `SST_immunity` byte in the objdef image (fire/lightning/bubble/bounce bits); hurt gate ANDs player bits vs object immunity (S3K masking). Shield child: spawned/killed by `Player_GiveShield`/hit-absorb; per frame copies player x/y/flip; anim per type; front/behind by anim frame via priority band; hidden while invincible.
- [ ] **Step 3: Verify + commit.** Debug-grant each shield: display tracks/flips/layers; absorbing a hit clears it without ring loss; fire-immune test object ignored with fire shield. `feat(player,objects): shield state + display child + immunity typing (D3)`

### Task 8: D3b — the four abilities + ring magnet

**Files:**
- Create: `games/sonic4/player/player_shield_moves.asm`
- Modify: `characters.asm` (Sonic's cd_ability → shield-move dispatch) or the air state direct call (pre-#3 fallback), `engine/objects/loss_rings.asm` (magnet), `engine/objects/rings.asm` (buffer-ring conversion)

- [ ] **Step 1: Research.** The air-state jump-press entry (design #3's hook if landed); `GetSineCosine` equivalent for the bubble ground-normal rebound; once-per-airtime latch precedent (`double_jump`-style flag — a PlayerV bit).
- [ ] **Step 2: Implement.** Dispatch by shield bits (fire→dash, ltng→jump, bubble→slam, none→insta): fire `x_vel=gsp=±$800,y=0`, end-on-land, camera-pan kick tag; lightning `y=−$580` + 4 sparks (`±$200` pairs, gravity `$18`, effect pool); bubble `x=0,y=+$800`, landing rebound `$780` ($400 water) along `angle−$40` normal, forces roll; insta 14-frame attack with 24px-radius expanded hitbox (spec §7.4) + brief immunity. **Magnet** (lightning passive, in LossRings_Update + a RingCollision pre-pass): 64px box; loss rings: per-axis accel `$30` toward player, ×4 when receding, `lr_flags` magnetized (no terrain bounce once magnetized — S3K); buffer rings inside the box convert to magnetized pool entries (spawn into the pool, remove from buffer WITHOUT marking collected — collected only on touch).
- [ ] **Step 3: Verify + commit.** Each ability's velocities probed; once-per-airtime; bubble rebound on a slope along the normal; magnet gathers a scatter + pulls placed rings; water-loss paths flag-stubbed with tags. `feat(player): shield abilities + lightning ring magnet (D3 complete)`

### Task 9: D4a — monitors

**Files:**
- Create: `games/sonic4/objects/monitor.asm` + objdef entries, monitor art (S3K-sourced/placeholder tagged)
- Modify: `engine/objects/collision.asm` (`Touch_Monitor`)

- [ ] **Step 1: Research.** The respawn-memory killed-bitmask API (gating BEFORE allocation — the ghost-bug rule); `Touch_Solid`'s standing mechanics (a monitor is solid + breakable — the break check runs in `Touch_Monitor` before/instead of solid per S3K's order: y_vel sign → rolling/airborne posture → break); award targets (`Player_GiveShield`, ring counter + 100/200 life checks, `SSEC_INVINC` timer, speedshoes phys-swap hook, `Lives_Count`).
- [ ] **Step 2: Implement.** S3K rules incl. from-below break; break = forced-airborne for a standing player, atomic {collision clear + solidity clear + broken frame}, respawn bit set, icon-float child (y=−$300, gravity $18, award at apex) + explosion effect. Spawn gate: bit checked in the entity-window spawn path before allocation → spawns pre-broken frame, no collision.
- [ ] **Step 3: Verify + commit.** Break matrix (roll into, jump onto, hit from below, walk into = pushed not broken); each award; broken persists across window eviction + death; **ghost regression**: evict + return + break attempt on the broken one does nothing. `feat(objects): monitors — S3K break rules + awards, ghost-bug-proof (D4)`

### Task 10: D4b — integration soak + docs + merge

- [ ] **Step 1: The soak.** Full loop on OJZ: collect rings → hit (scatter) → regather → shield pickup → each ability → hit-with-shield (absorb) → 0-ring death → respawn at post → broken monitors stayed broken → repeat ×3. Burst-frame + magnet-frame `Lag_Frame_Count` vs baseline; frame-step the hit frame (knockback + burst same frame).
- [ ] **Step 2: Docs.** ARCH: TouchResponse handler table statuses updated; the damage/shield/monitor sections written as-designed; DEFERRED_WORK: close §5 "Shields+damage+loss-rings", §4.9 "Bouncing Loss Rings", the EDGE_KILL/death hook, ANIM_GETUP arming; register follow-ups (Ring Attraction entry → subsumed note, water interactions, invincibility stars visual, speedshoes phys-swap completion, §9.13 lives/game-over, badnik rebound consumers). Queue-doc log.
- [ ] **Step 3: Final gates + merge.** DEBUG + plain builds, pytest, one clean baseline circuit, merge `feat/damage-shields` → master.

---

## Self-review (done at write time)

- **Spec coverage:** §2→T2 (+T4 spikes); §2.1 rebound→T2's enemy-touch path is D4-adjacent — rebound implemented in T2's Touch_Enemy gate stub and exercised fully when badniks exist (noted in T10 docs as follow-up consumer); §3→T3; §4→T5-6; §5→T7-8; §6→T9; §7 fixes→T2 (timeout, gate), T3 (cadence, fade), T8 (insta hitbox); §8 phases→task order + T10.
- **Placeholders:** none — art placeholders are explicit tagged decisions pending the #3 converter, not TBDs.
- **Consistency:** `PSTATE_HURT/DEAD`, `_pl_invuln` (=invuln_time), `SSEC_*`, `SST_immunity`, `LossRing`/`Loss_Ring_Pool`/`LossRings_Burst/Update/Render`, `Player_GiveShield`, `Player_Kill`, `Level_Restart`, `Last_Star_Post`, `Lives_Count` uniform.
