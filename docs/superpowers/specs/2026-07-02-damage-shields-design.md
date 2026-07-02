# Damage, Shields, Loss-Rings, Death & Star Posts — design spec

**Date:** 2026-07-02
**Status:** Approved by user (design dialogue 2026-07-02)
**Extends:** the §5 player system + §4.9 entity/ring system; consumes the pre-built
seams: `Touch_Hurt` (collision.asm:137), `invuln_time`/`status_secondary` (PlayerV),
`Player_Death_Pending` (set by EDGE_KILL, consumed by nothing — until now)
**Depends on:** design #3 (`cd_ability` hook hosts Sonic's shield moves; the shield
display child uses the child API). Executable after #3's C1; D3 needs C1 only.
**Design-week queue:** #4 of 5

---

## 1. Goal & user-ratified scope

Everything that makes damage real: hurt/i-frames, the 32-ring scatter, the
death→respawn loop, star posts, the **full S3K shield kit** (fire/lightning/bubble
+ insta-shield), and monitors. Fidelity baseline = S3K exact constants
(cross-verified S3K/S.C.E./SPG, §8); classic-faithful ≠ bug-faithful — four adopted
fixes are listed in §7. Loss rings use a **dedicated compact pool**, not SST slots.

**Non-goals:** game-over/lives UI + results (§9.13; lives = RAM counter only),
special stages (star-post ring-gating recorded as a hook), Super forms,
water-physics rows (bubble's air-refill is a hook for the water spec), badniks
themselves (COLLISION_ENEMY's award/explosion comes with the badnik design — but
`Touch_Enemy`'s rebound lands here since it is player-side).

## 2. Hurt (`PSTATE_HURT`)

Entry via `Touch_Hurt`/`Touch_SolidHurt` (and `Touch_Enemy` when not attacking):
- Immunity gates, in order: `invuln_time != 0` → ignore; shield/invincible bit +
  per-object immunity byte (§5) → negate; attacking posture (rolling/glide/insta)
  vs COLLISION_ENEMY → rebound instead (§2.1).
- On hit with a shield: clear shield bits (one mask, S3K `$8E` semantics), NO ring
  loss. Without: rings>0 → scatter (§3) + hurt; rings==0 → death (§4).
- Knockback: `x_vel = ∓$200` (away from hazard; positive if x equal),
  `y_vel = −$400`; underwater halved (`∓$100/−$200`). `ground_vel = 0`, airborne.
- `PSTATE_HURT`: no input; gravity `$30` (net `$10` underwater); no air drag;
  exits on landing (zero x_vel, re-arm `invuln_time = 120`, ANIM_GETUP arms the
  existing getup_timer) — **or on the adopted timeout** (§7.1).
- Flicker: draw when `invuln_time & 4` (4-on/4-off); ring collection (both pools)
  gated on `invuln_time < 90` — the gate keys off THE SAME timer (§7 pitfall).
- Spikes: `COLLISION_SOLID_HURT` + face byte (`objoff_3A` per ARCH §1573-1585),
  S3K rules (i-frames respected), distinct spike SFX selected by object identity.

### 2.1 Rebound (player-side, lands here)
Badnik: falling & above → `y_vel = −y_vel`; else `y_vel -= sign(y_vel)`.
Monitor: always reverse. Applied after gravity; x untouched; variable-jump clamp
applies only to jumped bounces. (SPG:Rebound, verified.)

## 3. Loss rings — dedicated compact pool

- `Loss_Ring_Pool`: 32 entries × {x.w, y.w, x_vel.w, y_vel.w, life.b, flags.b}
  (12 B ⇒ 384 B RAM) + count. NOT SSTs — zero effect-pool contention; own update
  + render loop (renders through the ring sprite path, behind the player).
- Burst: `min(rings, 32)`; velocities from **precomputed tables** (S.C.E.'s
  decoded spiral: outer 16 ≈ `$400`, inner 16 ≈ `$200`, mirrored pairs; separate
  water table) — water table + gravity `$A` selected per ring at spawn when below
  the waterline (S.C.E. refinement; identity until water exists). Ring counter →
  0, HUD dirty flag, extra-life flags cleared.
- Physics: gravity `$18`/frame; floor-only bounce `y_vel = −(y_vel − y_vel>>2)`
  (−75%); checks the tile-cache collision path **every 4 frames staggered** (§7.2);
  no wall/ceiling sensing (classic); delete below kill plane.
- Lifetime 256 frames; **fade/flicker warning in the last 16** (§7.3); collectible
  via the normal gate (§2) — collection = counter++, sparkle effect, entry freed.
- Exhaustion: burst stops when the pool is full; counter still zeroed (classic
  degradation). The 32-at-once spawn respects `MAX_SPAWNS_PER_FRAME`? No — pool
  entries are not object spawns; the guard is the pool size itself.

## 4. Death & star posts

- **Death** consumes `Player_Death_Pending` + the 0-ring hit path:
  `PSTATE_DEAD` — `y_vel = −$700`, x 0, normal gravity, no collision, drawn
  high-priority; camera locked. Past `Camera_Y + $100` → 60-frame wait →
  **level reload**: at the active star post else level start.
- **Restore contract:** position + camera consistent; **timer resumes** from the
  post's saved value; rings = 0; shields/invuln cleared; **respawn-memory parks +
  `Ring_Collected_Window` + ring buffer explicitly reset** (our section-keyed
  memory would otherwise persist collected state across death — decided: it
  resets, matching classic "rings respawn on death"); killed badniks revive.
  Lives: RAM word decrement; 0 → stub state (freeze + flag) until §9.13 owns
  game-over.
- **Star posts** (game object): activation when passed with subtype >
  `Last_Star_Post` (S3K ordering), proximity box; saves post id + position +
  timer; spinning-head child anim; respawn-memory-gated like monitors. Special-
  stage gating = deferred hook comment.

## 5. Shields — full S3K kit

- **State:** `status_secondary` bits (shield, fire, lightning, bubble, invincible,
  speedshoes — the reserved byte becomes real); elemental bits exclusive.
  **Immunity typing:** per-object byte `SST_immunity` (objdef-supplied) with
  fire/lightning/bubble/bounce bits — S3K's `shield_reaction` masking verbatim.
- **Display:** ONE shield child object (design-#3 child API), anim per shield
  type, **priority-band switching** for front/behind frames (bands exist;
  runtime change clears RF_PRIORITY_MASK first). Hidden while invincible. Art =
  properly allocated VRAM region — S3K's one-slot shield/stars/sparks exclusivity
  is explicitly NOT inherited.
- **Active abilities** (Sonic's `cd_ability` hook; once per airtime, reset on
  landing; shield move only when no double-jump action pending):
  - **Fire dash:** `x_vel = ground_vel = ±$800` (facing), `y_vel = 0`; ends on
    landing; camera lookahead kick (hook to the existing pan). Lost on water
    entry (dissipate puff).
  - **Lightning jump:** `y_vel = −$580`; 4 sparks (±$200 pairs, gravity $18,
    effect pool); **ring magnet**: 64px box, accel `$30` per axis toward the
    player, ×4 when receding — applies to loss-pool rings AND buffer rings in
    radius (buffer ring converts to a magnetized loss-pool entry on attraction).
    Lost on water entry (flash).
  - **Bubble bounce:** `x_vel = 0`, `y_vel = +$800`; on landing rebound `$780`
    (`$400` underwater) along the ground normal, forces roll. Survives water;
    air-refill hook noted for the water spec.
  - **Insta-shield** (no-shield default): 14-frame attack, **expanded 24px-radius
    hitbox** (generous per Mania's v1.04 lesson), brief hazard immunity while
    active.
- Passive: any shield absorbs one hit (§2); elemental immunities via the typing
  byte (fire objects, lightning objects, bubble-negated objects).

## 6. Monitors

Game object, S3K rules: solid 14×16; breaks when hit rolling/airborne from
side/above, **and from below** (S&K behavior — the monitor does not topple);
standing player forced airborne on break. Award dispatch by subtype: rings+10
(with 100/200 life checks vs the lives counter), fire/lightning/bubble shield,
invincibility (timer + stars deferred visual), speed shoes (`status_secondary`
bit + phys-row swap hook), 1-up, broken frame persists. **Ghost-bug rules (from
the legacy repo's documented failure):** respawn-memory bit gates spawn BEFORE
allocation; break clears collision + solidity atomically with the frame change.
Icon float (`y_vel −$300`, gravity `$18`) + explosion via the effect pool.

## 7. Adopted fixes (classic defaults, deviations documented at the site)

1. **Hurt-state timeout** (~120 frames airborne cap) — SPG's own recommendation;
   a ledge knockback can't strand control indefinitely.
2. **Loss-ring floor checks every 4 frames staggered** (stock is 8) — halves the
   tunnel-through-floor rate; measured headroom covers it.
3. **Mania-style scatter expiry fade** (last 16 frames) — telegraphs the timer.
4. **Generous insta-shield hitbox** — Mania shipped tight and patched to generous.
Everything else is constant-exact S3K, including the feel-critical ones: 120-frame
re-armed-at-landing i-frames, ≥90 recollect gate, −75% bounce, halved underwater
knockback, monitor break rules.

## 8. Phasing & verification

- **D1 — Hurt + scatter.** PSTATE_HURT, i-frames/flicker/gate, loss-ring pool,
  spikes; a test hazard object. Verify: RAM-watch constants vs §2/§3 numbers;
  scatter filmed during motion; regather after 30 frames; tunnel-rate spot check.
- **D2 — Death + star posts.** PSTATE_DEAD, reload path, restore contract
  (explicit reset list), star-post object. Verify: death→respawn at post; timer
  resumes; parks/buffer reset (collected rings respawn); kill-edge path finally
  consumes its flag.
- **D3 — Shields.** Status bits, display child, immunity typing, the four
  abilities, magnet. Verify: each ability's velocities probed; magnet radius/force
  behavior; shield-absorbs-hit; water-entry losses (flag-stubbed until water).
- **D4 — Monitors + soak.** Monitor object + awards; the full integration soak:
  hit→scatter→regather→shield pickup→ability→death→respawn→broken-monitor-stays-
  broken; `Lag_Frame_Count` on the burst frame; ghost-bug regression (respawn
  memory + atomic break).
Engine/game tags: §2/§3/§4 machinery + rebound = **engine**; shields/monitors/
star-posts/test-hazard = **game objects** on engine seams (design-#5 input).

## 9. Research provenance

Three-agent pass 2026-07-02: aeon audit (Touch_* stubs, reserved fields,
Player_Death_Pending orphan, effect-pool budget tension → the dedicated pool
decision, no game-state restart path — this design creates the first one, ghost-
monitor commitments); S3K/S.C.E. mechanics (all constants w/ sonic3k.asm cites;
S.C.E. byte-identical + two adopted refinements: precomputed velocity tables,
water-aware spawn); web/SPG (version deltas: S3K monitors break from below,
spikes respect i-frames post-S1, scatter checks are 8-frame staggered not SPG's
4; the one-VRAM-slot shield exclusivity; Mania scatter fade + insta-shield
hitbox lesson; the same-timer recollect-gate pitfall).
