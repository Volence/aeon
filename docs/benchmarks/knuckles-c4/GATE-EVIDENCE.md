# Knuckles C4 — gate evidence (glide / slide / climb / ledge)

The durable `--ab` reference for the `knuckles-c4` freeze. Every observation below
was made by the controller on the **oracle** emulator against the lane build; the
static analysis that produced each fix is cited at the code.

## What the parcel changes

Knuckles' whole glide family, added behind ONE record field
(`CharDef_Knuckles.cd_ability` -> `Ability_KnuxGlide`) with **zero engine changes and
no `Character_ID` test anywhere in the player frame** — the acceptance proof for the
C1 dispatch seam. New modules `games/sonic4/player/player_glide.emp` (`PSTATE_GLIDE`,
`GLIDEFALL`, `SLIDE`) and `player_climb.emp` (`CLIMB`, `LEDGE`, the glide wall-catch),
registered as two new sigil sections. Plus two visual-defect fixes (dust palette
permute, dust priority band) and a DEBUG-only test scaffold.

## Oracle-verified behaviour

**Glide -> wall-catch -> climb -> ledge -> stand.** Verified at the user's real ledge
(left face x464). Ascent passes the former freeze point, **LEDGE fires at y=557**
(state 24), the clamber runs to completion, and the state ends **GROUND standing on
top at (464,528)** — no hop at the top-out, no wedge.

**Climb-up recess tolerance (user-ruled S3K divergence).** The predicted arithmetic
matched live: at y=561 the wall probe reads dist 2 (formerly a permanent freeze), the
climb now rises 1 px, the gap reads exactly 4 at y=560, and the ledge fires by S3K's
own unchanged threshold. Derived from the platform's top tile, shape 29
(heights `[9,9,10,10,...,16,16]`, rotated widths `254,252,250,248,246,244,242,16...`).

**Climb-down landing.** Lands on the walkable ground instead of shooting to the level
bottom (the pre-fix symptom was y~5920, falling through the map).

**Glide -> land -> slide.** Glide landing on flat terrain enters **SLIDE (state $14)
with x_vel preserved ($1004)**; the slide now integrates position — measured
**x=494 speed $1800 -> x=565 speed $17A0** on consecutive steps, with a DustPuff left
behind at x=494 as he moves past it (the trail). Full glide -> land -> slide -> get-up
travels **~440 px**.

**Solid-object tops are floors (user-ruled S3K divergence).** On the DEBUG test
platform: a glide contacting a solid-object top enters **SLIDE (state $14) with x_vel
preserved ($0FE4)**, and sliding off the edge takes the ledge-drop into **GLIDEFALL
(state $12)** — the ruled behaviour works on objects exactly as on terrain.

## Withdrawn / closed without code

Three reported defects closed as NOT-BUGS after the evidence was re-derived, recorded
so they are not re-opened:

- **Overhang top-out.** Every climb probe is `SOLID_LRB`, byte-identical to S3K's
  `lrb_solid_bit` contract; stock S3K refuses the same geometry. TOP-only lips are the
  authoring fix, not a code change.
- **Standstill slope drift.** `Player_SlopeResist` matches S3K clause for clause
  (standing gate `|factor| >= $D`, `PHYS_SLOPE_WALK $20`) and `engine/data/sine.bin` is
  **byte-identical** to `skdisasm/Levels/Misc/sine.bin`. The apparent asymmetry is
  `asr` flooring toward -inf and affects exactly four angles (`$90 $91 $EF $F0`).
  Authentic; a symmetry option is registered in DEFERRED_WORK.
- **BUG 10 (glide dead-stops on a solid).** Withdrawn. `width_pixels`/`height_pixels`
  are FULL box dimensions per `aabb_axis_test` (`2*|delta| < dim_a + dim_b`), so the
  16x16 test object spanned x795-811 / top y=200, not the 32x32 assumed; at the
  captured frames `|dy|` was 28-35 against a required `< 18.5`, i.e. **no contact had
  occurred**. Re-tested on a proper platform, the ruled behaviour passed first try.

## Byte-gate notes for this freeze

- The **Z80 sound blob is untouched** by this parcel: both shapes build clean with the
  `BLOB_LEN_*` tripwire **ARMED** (no `SIGIL_BLOB_LEN_DRIFT` override), so no
  `BLOB_LEN_*` / `Z80_SOUND_SIZE` / seam-1 re-pin was required.
- The **release shape is byte-identical across the DEBUG test scaffold**: the scaffold
  is gated as a single conditional array whose `DEBUG=0` branch is the original list
  verbatim. Verified in the built ROMs — the 8 platform records appear contiguously in
  `s4.debug.bin` and are **absent** from `s4.bin`.
- Replay fixtures are expected to be unaffected as Sonic: the parcel adds Knuckles-only
  states plus the dust changes, and touches no shared ground/air physics.
