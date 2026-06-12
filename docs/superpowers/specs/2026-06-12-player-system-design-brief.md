# §5 Player/Character System — Design Brief (for user review)

**Date:** 2026-06-12 (overnight groundwork)
**Status:** BRIEF — research synthesis + decision points. NOT a locked spec; the
§5 brainstorm happens with the user. Research: `docs/research/player-physics-classics.md`,
`player-sensors-sce.md`, `player-feel-modern.md`, `player-structure-refs.md` (all committed).

## What the research settled (recommendations, evidence in the docs)

1. **Physics baseline = S2 values + the five verified S3K refinements** (standing
   slope-factor gate, $18-angle slip with nudge, air-speed preservation above top
   speed, roll start/unroll thresholds, facing-aware push). Two popular claims are
   MYTHS, verified against real code: S3K does NOT do vector projection at landing
   (same axis-select as S2), and apex-only air drag is in S2/S1 too. Our §5
   architecture-doc text citing both needs correcting before implementation.
2. **Sensor system per the SPG spec** (6 sensors, mode quadrants, 9/19 radii,
   adaptive snap `min(|xsp|+4,14)`), running against our tile cache. The
   `collision_lookup.asm` heightmap+angle math already exists against stub
   tables; runtime gaps are enumerated (2-block probe extension, 4 probe
   directions, solidity gating, negative heights, odd-angle flag).
3. **The collision-data prerequisite is generator-only work**: OJZ's primary +
   secondary index files decode (Kosinski, 374 blocks; 46 differ = real loop
   data), and baking (profile, flips, solidity) per placement measures only 91
   unique combos for OJZ — fits the existing one-byte cell format. No engine
   format change needed. This is the first §5 plan task.
4. **SST fits the player** — full S3K-feature set needs 24-32 of the 34
   `sst_custom` bytes (per-character DPLC immediates recommended). Closes the
   deferred §3 audit question: no per-pool stride, no growth.
5. **Structure**: explicit state-index + jump table (the clean pattern across
   every reference); concurrent conditions (facing/water/pushing) stay as flag
   bits, only mutually-exclusive modes get states. `Player_Common` should own
   the frame skeleton with characters contributing states + tables (sonic_hack
   shares only helpers and duplicates ~8,000 control-flow lines 3× — the
   cautionary tale). State entry/exit hooks: keep. Physics tables via the
   proven register-pointer convention: keep. Position-history ring (64×4B +
   stat ring, input replay): adopt unchanged, 256-aligned.
6. **Input**: poll once per frame in VBlank; OR-accumulate press edges across
   lag frames; full moveset must work on 3 buttons.
7. **Known classic bugs — fix list** (community-canon-positive): speed-cap bugs
   (preserve legit downhill over-top), tunneling guards ($1000 caps),
   roll-jump 5px size bug, wall zips. Keep: angle-range asymmetries (feel).

## Decisions that are YOURS (each is reversible, but sets the feel)

A. **Coyote time** (a few frames of jump grace after leaving a ledge): modern
   QoL, not in any classic; S3AIR ships similar as opt-in. Adopt / reject /
   build-flag?
B. **Jump input buffer** (2-frame): research recommends adopt (imperceptible,
   pure responsiveness); confirm.
C. **Roll-jump control**: classic S2/S3K locks air control after a roll-jump;
   CD/Mania unlock it. Research recommends CD/Mania behavior (and the §5
   architecture doc already says "no special-case lockout"). Confirm.
D. **Extended/lead camera** (CD-style look-ahead at speed): ties into our
   camera system, not just the player. Adopt now / defer to a camera pass?
E. **Character roster order**: implement Sonic first (plan assumption), with
   Tails/Knuckles as follow-up plans?

## Proposed plan shape (5-7 tasks, pending the brainstorm)

1. Collision data pipeline: real OJZ indices + height/angle tables through
   `ojz_strip_gen.py` → both cache planes (kills the priority-bit placeholder;
   path-B becomes real). Editor splitting of collision authoring comes later.
2. Sensor core: probe routines against the tile cache (extend the
   `collision_lookup.asm` API per the gap list), mode quadrants.
3. Ground movement state (accel/decel/friction/slope factor/slip) + the input
   skeleton in Player_Common.
4. Air + jumping (variable jump, air drag window, landing conversion).
5. Rolling + spindash.
6. Camera integration (deadzone behavior vs the §4 camera; landing lock) +
   debug-fly coexistence.
7. Verification matrix on OJZ (slopes, the loop once path-B swappers exist).

Tails AI, Knuckles abilities, shields/damage (loss rings — §4.9's deferred
items), and super forms are separate follow-up plans.
