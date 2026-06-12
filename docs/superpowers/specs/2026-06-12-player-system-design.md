# §5 Player/Character System — Design (APPROVED)

**Date:** 2026-06-12
**Status:** APPROVED — brainstormed with user 2026-06-12; supersedes the open
points in `2026-06-12-player-system-design-brief.md`. Research basis:
`docs/research/player-physics-classics.md`, `player-sensors-sce.md`,
`player-feel-modern.md`, `player-structure-refs.md`.

## 1. Scope

**In this plan:** Sonic only, physics-first, placeholder art (the existing
test-player sprite, no animation/DPLC work). Movement kit: ground movement,
jumping, rolling, spindash. Real OJZ collision data through the generator.
Sensor layer. Camera landing lock. Minimal path-swap line object (needed to
verify the loop). Debug-fly coexistence.

**Deferred to follow-up plans:** Sonic art/animation/DPLC, dropdash,
instashield, Super, Tails (AI + flight), Knuckles (glide/climb),
shields/damage/loss-rings, 6-button extras, per-section physics *system*
(plumbing lands now — §5.4), Lerp at section physics boundaries, water.

## 2. The feel contract

**S3K behavior is the reference throughout** — verified against the actual
`sonic3k.asm` disassembly, not SPG folklore; S2 is cited only where the two
are identical (base constants are). Tie-breaker rule for anything that comes
up during implementation: **S3K wins.**

User decisions (2026-06-12, all resolved):

| Decision | Call |
|---|---|
| Coyote time | REJECTED — classic ledge behavior (the ~10px spatial overhang forgiveness is already classic) |
| Jump input buffer | ADOPTED — 2 frames, press edges OR-accumulate across lag frames |
| Roll-jump air control | CLASSIC LOCKOUT KEPT — roll-jumps commit you to your trajectory |
| Extended camera | REJECTED — classic camera numbers only |
| Roster | SONIC FIRST |
| Landing speed conversion | CLASSIC AXIS-SELECT BANDING (motion quadrant + angle band). Vector projection rejected — it is a myth that S3K does it, and it would diverge from the contract |
| Physics source | S3K over S2 wherever they differ |
| Per-section physics | Plumbing only (effective-table-in-RAM, identity modifier) |
| Non-jump airborne up-cap (−$FC0) | **REMOVED** — see §2.1 |
| Mania taller jump | OFF — strict Genesis arc |
| Jump-delay fix | ADOPTED — player moves on the press frame (documented classic bug; Mania fixed it) |
| Classic bug fixes | #1–#10 of the research table fixed **unconditionally** (no "keep glitches" build flag); #11 (angle-range asymmetries) kept as tuned feel |

### 2.1 FEEL DEVIATION NOTE — removed up-velocity cap

The classic non-jump airborne up-cap (`y_vel` clamped to −$FC0 on ramp/slope
launches) is **removed**. Rationale: under our ground-speed cap of $1000
(adopted as the tunneling guard, SPG-recommended placement on GSp rather than
x_vel) the fastest launch already converts to ≤ $1000 upward, so the −$FC0
clamp would shave only the top 1.6% of a max launch while adding a clamp that
classic players dislike (it truncates earned ramp launches).

**If launches ever feel truncated, the knob is the $1000 GSp cap** — raising
it is a coupled change: `CAM_MAX_Y_STEP`, `VFILL_ROWS_PER_FRAME`, and swept
sensor checks must rise together (16px/frame is the verified streaming
contract; sensor reach is 32px). This note is duplicated as a `; FEEL
DEVIATION:` comment at the clamp site in code and in `DEFERRED_WORK.md`.

Drawing keeps up by construction: the engine draws at *camera* speed
(`CAM_MAX_Y_STEP = 16` px/frame, matched to `VFILL_ROWS_PER_FRAME = 2`), never
at player speed. A monster launch means the player briefly outruns the camera
— exactly what the classics do.

## 3. Architecture

### 3.1 Files & ownership

- `engine/player/player_common.asm` — frame skeleton, state dispatch, ALL
  shared movement code. Owns the player frame; characters contribute state
  handlers + tables. (Inverts sonic_hack's failed split, which shared 603
  lines of helpers while duplicating ~8,000 lines of control flow 3×.)
- `engine/player/player_sensors.asm` — the 6-sensor layer wrapping
  `collision_lookup.asm` per its documented register convention (d3.b layer on
  every entry, X/Y saved in d4/d5).
- `engine/player/sonic.asm` — Sonic's state table, physics base table,
  spindash. Tails/Knuckles later add sibling files with zero changes to
  common.
- `objects/test_player.asm` — debug-fly demoted to a debug toggle that
  suspends the state dispatch (the `obj_control` escape hatch every classic
  keeps).

### 3.2 Player as object

The player is a standard SST object in the `Player_1` slot — camera and entity
window already assume this. All state lives in the 34-byte `sst_custom`
overlay ($2E–$4F); the research fit table (player-structure-refs §2.2) is the
field budget: ~24 bytes used, ~10 spare. **DPLC table/art base are per-character
code immediates, not SST fields** (the 9-byte test_player pattern is not
carried over). This closes the deferred §3 audit question: fits, no per-pool
stride, no SST growth.

Universal SST fields used as-is: `x_pos`/`y_pos` (16.16), `x_vel`/`y_vel`
(8.8), `status` ($1E, ST_* condition bits), `angle` ($1F), `layer` ($2D),
`width_pixels`/`height_pixels`, anim block, `parent_ptr` (future Tails
leader link).

### 3.3 State machine

Flat explicit state index + jump table. **Mutually-exclusive movement modes
get states; concurrent conditions stay flag bits** (facing, pushing,
underwater, on-object — the line S2 never drew). Initial state set:

| State | Notes |
|---|---|
| `PSTATE_GROUND` | standing/running |
| `PSTATE_ROLL` | grounded, curled |
| `PSTATE_SPINDASH` | charging |
| `PSTATE_AIR` | airborne, uncurled (ledge walk-off, springs) — no release cap |
| `PSTATE_JUMP` | airborne, curled, from jump — variable-height release cap active |
| `PSTATE_ROLLJUMP` | as JUMP but air control locked (classic lockout) |
| `PSTATE_AIRBALL` | airborne, curled, not from jump (rolled off ledge) — no release cap |

Every state gets `Enter`/`Exit` hooks; all transitions route through a single
`Player_SetState` (old exit → new enter → write state byte). Height/width
changes, the ±5px y-shift on curl/uncurl, collision-mode resets, and anim
selects happen ONLY in hooks — one auditable writer. This resolves the
architecture doc's "hierarchical state machine (evaluate)" → **rejected** in
favor of flat states + condition flags (survey verdict: explicit index beats
flag-derived dispatch; hierarchy unneeded at 7 states).

The classic `status3` pseudo-states (jumping, spindash) dissolve into the
state index; genuine conditions remain `ST_*` bits.

### 3.4 Physics plumbing (per-section ready, identity now)

Movement code NEVER reads character constants directly — it reads an
**effective physics table in RAM** (accel, decel, friction, top speed,
gravity, jump force, air-drag params) through the proven a4-register
convention (S2/S3K/sonic_hack all do this). `Player_RefreshPhysics`
recomputes the RAM table from `character base table × section modifier` —
called on section change and on future water/speed-shoes events, NEVER
per-frame. Day one the modifier is identity, so behavior is pure classic;
a future terrain type is one `dc.w` table + a section reference, zero code.
Lerp-at-boundary slots inside RefreshPhysics later without touching movement
code (every classic snaps; nobody noticed for 30 years).

### 3.5 Frame skeleton (order is the contract)

1. **Input** — polled once per frame in VBlank (already exists); press edges
   OR-accumulate across lag frames; opposing D-pad directions masked (bug
   #10); 2-frame jump buffer latched on press edge, decremented here.
2. **State dispatch** — jump table on `player_state`; handlers read the
   effective physics table. Order within grounded states preserved from the
   classics: spindash check → jump check (jump-delay fix: the press frame
   completes its movement) → slope factor → input accel/decel/friction →
   inertia→velocity projection → ground wall probe (velocity-projected,
   facing-aware push) → roll check.
3. **Integration** — position += velocity, single `add.l` per axis (16.16
   SWAP convention).
4. **Sensors** — per current mode quadrant (`(angle+$20)>>6`, computed once
   per frame as a first-class value): floor pair grounded; motion-quadrant
   sensor activation airborne. Adaptive snap-down `min(|vel|+4, 14)`; −14
   fixed snap-up.
5. **Angle/landing resolution** — closer sensor wins, ≥$20 divergence or
   odd-flag → cardinal snap; landing = classic banding; angle continuity
   guard (reject >$20 jumps — loop fallthrough prevention).
6. **Position history ring push** — 64×4B position ring + parallel stat ring
   (input word + status), 256-aligned via `phase` so the low-byte-increment
   wrap is free. Recorded unconditionally (branch costs more than the
   writes). Feeds future Tails AI input-replay and invincibility trails.
7. **Camera update** — existing system + landing lock (no downward scroll
   while airborne from a jump until landing or bottom-deadzone exit).

## 4. Collision data pipeline (generator-only; first plan task)

No engine format change — the cache, layer model, lookup math, and ROM table
slots are in place and verified by the priority-bit placeholder. Work is in
`tools/ojz_strip_gen.py` + `tools/gen_collision_data.py`:

1. Kosinski-decompress OJZ primary/secondary 16×16 collision index files
   (374 bytes each, measured; 46 blocks differ = real path-B loop data) with
   the existing `kos_decompress`.
2. Per cell, per path, resolve `(profile, xflip, yflip, solidity)` — path A
   from primary index + chunk-word bits 12-13, path B from secondary + bits
   14-15. Stop dropping chunk-word bits 15..10.
3. **Bake placement into the byte**: each unique combo becomes a synthesized
   profile in a build-generated, deduplicated attribute set (91 unique combos
   measured for OJZ). xflip ⇒ reverse height bytes + negate angle; yflip ⇒
   flip height semantics + reflect angle `−(angle+$40)−$40`; rotated profiles
   REGENERATED from the flipped vertical profile (never trust the source
   rotated array for flips).
4. **Encoding: full 8-bit attr-set index + parallel 256-byte `SolidityTable`
   ROM table** (solidity values: 0 air, 1 top-only, 2 lrb-only, 3 all).
   Chosen over 2-bit-solidity-in-byte for 256-slot headroom and a simpler
   generator; cost is one indexed load per probe (~14 cycles — noise).
5. Regenerate `data/collision/*.bin` (heights, rotated, angles) from the
   sonic_hack source arrays through the attr-set remap, preserving the
   odd-angle-flag convention ($FF/odd = "no usable angle, snap to cardinal").
6. Emit per 8-px cell (both tile columns of a block carry the same byte);
   plane A and plane B bytes now genuinely differ.

Also: sync `ENGINE_ARCHITECTURE.md` §4.7 (says 16-px collision columns; code
is 8-px).

## 5. Sensor layer (`player_sensors.asm`)

Four directional probe cores — `Collision_ProbeDown/Up/Left/Right` — stamped
from **one AS macro** (specialization without runtime eor-mask plumbing; zero
runtime cost, conventions §1). Each fixes the full gap list from the sensor
research:

- **Two-block extension**: empty → +16px re-probe, full → −16px re-probe;
  result range −16..+31; distances ≥16 = "nothing found".
- **Negative-height accept rule**: `(probe & $F) + h < 0` for hanging
  geometry (required — OJZ rotated array contains $F1–$FF).
- **Solidity gate per sensor class**: floor sensors accept top+all;
  wall/ceiling accept lrb+all (via `SolidityTable`).
- **Odd-angle flag** → substitute the probe quadrant's cardinal.

On top of the cores:

- Pair wrappers: floor pair (exists, extend), ceiling pair, closer-wins +
  angle resolution policy.
- Single wall probe at the constant **±10px** (not x_radius); grounded push
  probes at next-frame position (velocity-projected entry that skips the SST
  fetch), at `y+8` on exactly-flat ground, raised 5px when rolling; on hit,
  distance is added into velocity (not position) grounded, position airborne.
- Push sensors disabled outside −90°..90° ground angle; re-enabled at exact
  cardinal multiples (S3K rule).
- Radii: standing 9/19, ball 7/14, symmetric ±5px y-shift on curl/uncurl
  (properly fixes the roll-jump 5px size bug, #5 — always ball radii while
  curled).
- DEBUG-build assert on out-of-cache probes (silent air = falling through the
  world during streaming bugs).

All entries follow the d3-layer register contract documented in
`collision_lookup.asm`.

## 6. Physics specification

Canonical values (8.8 fixed point), from the verified quick-reference card:

| Quantity | Value |
|---|---|
| accel / decel / friction | $C / $80 / $C |
| top speed | $600 |
| gravity | $38 (applied AFTER position add) |
| jump force | $680, perpendicular launch ADDS to velocity (ramp jumps) |
| jump release cap | −$400, only in JUMP/ROLLJUMP states |
| jump headroom check | ≥6px via ceiling probe at angle+$80 |
| air accel | 2×accel = $18; no air friction/decel distinction |
| air drag | `x_vel -= x_vel >> 5`, only while −$400 ≤ y_vel < 0, before gravity |
| airborne angle decay | toward 0 by 2/frame |
| slope factor walk | $20·sin; S3K standing gate: applied at GSp==0 only if ≥$D |
| slope factor roll | $50·sin downhill / $14·sin uphill (quartered) |
| roll friction / brake | $6 (accel/2) / $20 fixed; no input accel while rolling |
| roll start / unroll | ≥$100 with down, L/R not held / <$80 (S3K thresholds) |
| forced-roll floor | GSp = ±$400 when unroll forbidden; $200 if rolled at 0 |
| ground speed cap | **±$1000 on GSp** (tunneling guard, SPG placement) |
| fall speed cap | $1000 |
| up speed cap | **none** (FEEL DEVIATION — §2.1) |
| turnaround kick | crossing 0 under decel sets ∓$80 |
| top-speed back-out | input accel never clamps speed already above top — ground AND air (S3K) |
| skid threshold | ≥$400 on flat quadrant — implement with the d1 fix (the stock compare tests a clobbered register; both disassemblies carry the `fixBugs` correction) |
| slip (S3K rework) | angle ≥$18 and |GSp|<$280 → GSp ±= $80 downhill nudge; detach only at angle ≥$30; move_lock 30 frames (input-only freeze; friction + slope factor still run) |
| spindash | release $800 + charge·$80 capped $C00; +$200/tap capped $800; decay `counter -= counter>>5`/frame; table-form data |
| landing | motion quadrant (CalcAngle −$20, &$C0) then angle band: flat ⇒ GSp=x_vel; mid band ⇒ y_vel>>1, GSp=±y_vel; steep ⇒ GSp=±y_vel, x_vel=0; horizontal motion ⇒ GSp=x_vel on floor hits, GSp=y_vel on wall hits (wall-run engage) |
| landing eligibility | dist ≥ −(y_vel/256 + 8) — embed tolerance scales with fall speed |

Bug-fix ledger (research table, all unconditional): #1 ground speed-cap
curtail (S2 fix), #2 air speed-cap (S3K fix), #3 tunneling caps (GSp $1000 +
fall $1000), #4 jump delay, #5 roll-jump size, #6 two-sensor ledge quirks
(prefer motion-side sensor on near-ties), #7 wall-zip guards (clamp eject
per frame, never invert sign, clamp to section bounds), #8 MoDule S3 fixes
where applicable, #9 slope-glitch (force airborne re-eval when stood-on
object vanishes — hook for future solid objects), #10 L+R masking. #11
angle-range asymmetries KEPT.

Named constants for every value (conventions §; sonic_hack's constant naming
is the model). Underwater/super/speed-shoes table rows: NOT in this plan
(no water in OJZ) — the RefreshPhysics plumbing is their landing site.

## 7. Camera integration

Classic numbers stay. Additions:

- **Landing lock**: while airborne from a jump, the camera does not scroll
  down until landing or the player exits the bottom dead-zone (kills
  per-jump camera bounce).
- Debug-fly bypass keeps working (suspends state dispatch, camera follows as
  today).

## 8. Path-swap line object

Minimal invisible line object (entity-window v2 object): when the player
crosses the armed line, write the SST `layer` byte (0/1). Replaces S.C.E.'s
global solid-bit pair with our per-object layer model (multi-actor safe).
Needed to verify the OJZ loop. Subtype encodes orientation/direction/size,
matching the v2 6-byte entity format.

## 9. Verification matrix (final plan task)

On OJZ, via build + Exodus MCP bridge (live RAM/VRAM inspection):

1. Flat ground: accel to top speed, friction stop, turnaround kick, skid.
2. Each slope band: walk/roll up/down, slope factor signs, slip + 30-frame
   lock, detach at ≥$30.
3. The loop: full traversal both directions at roll speed (path swappers),
   angle continuity through all four quadrants, no fallthrough.
4. Jumps: variable height (tap vs hold), ramp launch adds perpendicular,
   release cap only in jump states, headroom rejection, jump buffer (press
   2 frames early), roll-jump lockout.
5. Rolling: thresholds, unroll, forced-roll, $1000 caps.
6. Spindash: charge/decay/release values, camera behavior.
7. Edges: ledge walk-off → AIR uncurled; roll-off → AIRBALL; balance NOT in
   scope (no balance anim with placeholder art).
8. Tunneling: spindash-jump into thin floors/ceilings at max speeds.
9. Debug-fly toggle round-trip mid-air and mid-roll.
10. Frame budget: player frame must fit comfortably alongside streaming
    worst case. The §8.5 profiler is not built yet — measure with a CRAM
    raster strip (border-color timing) or VBlank-overrun flag instead.

## 10. Documentation updates bundled with implementation

- `ENGINE_ARCHITECTURE.md` §5: myth corrections (already partially done),
  state-machine resolution (flat, not hierarchical evaluate), landing =
  banding (cascade line correction), −$FC0 removal note, §4.7 8-px column
  sync.
- `DEFERRED_WORK.md`: close the §3 SST-fit audit question (fits, DPLC as
  immediates); add the launch-cap coupling note (§2.1); list deferred items
  (§1).
- `docs/research/player-movement.md` is superseded by the four §5 research
  docs where they conflict.
