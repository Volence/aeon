# Sonic Animations + Shared Spindash — Design

**Date:** 2026-06-15
**Status:** Approved (design), pending implementation plan
**Scope:** Author Sonic's full normal-play animation set, add speed-scaled
animation timing, relocate spindash into shared (all-character) player code, and
build a debug anim-viewer for visual verification.

## Baseline philosophy

Design decisions track **S3K as the floor**, plus our own modern choices — not
S2. The migrated Sonic art (`art/optimized/characters/sonic.bin`) comes from a
S2 disassembly, so S2 frame-index tables are useful only as an **art-frame map**.
S2 is data; S3K (and beyond) is behavior.

## Goal

Today `data/animations/sonic_anims.asm` defines only walk, idle (reusing walk
frame 5), and roll. The migrated `sonic.bin` mappings + DPLC already contain the
full Sonic frame set; the scripts were never authored. Sonic also lacks
speed-scaled timing, so walk/run/roll do not animate faster at speed. Spindash
lives in `sonic.asm` (`PState_Spindash`) and is character-specific, but every
character will share spindash.

This pass makes Sonic "look normal" in every normal-play animation, drives them
from a clean character-agnostic selection routine, and makes spindash shared.

## Out of scope (deferred, tracked in DEFERRED_WORK.md §5)

- S3K signature abilities: dropdash, insta-shield.
- Super Sonic, hurt/death/drown, spring, hang, slide, shield animations — all
  depend on unbuilt systems (damage, water, shields, super).
- Per-character dispatch-table indirection refactor (Tails/Knux state/physics
  tables). This pass only makes **spindash** shared; it does not build the full
  roster indirection.
- Camera pan on duck/look-up (a camera-system concern; left as a wired-but-zero
  hook, see Section 2).

---

## Architecture overview

```
Player_Main (per frame)
  ├─ ... physics / state machine / collision (UNCHANGED) ...
  └─ Player_Display
       ├─ Player_Animate        ← NEW: read-only classifier, writes one ANIM_* id
       ├─ AnimateSprite         ← EXTENDED: speed-scaled duration sentinels
       └─ Sonic_LoadArt → Perform_DPLC → Draw_Sprite   (UNCHANGED)
```

`Player_Animate` is pure read-only classification: it reads state, status bits,
input, and (only when at rest) one ledge sensor, and writes exactly one
`ANIM_*` id into `SST_anim`. It performs no physics and mutates no game state
except the skid latch and get-up one-shot (both display-only transients).
Physics, the state machine, and collision are untouched.

---

## Section 1 — Shared `ANIM_*` id contract

`ANIM_*` ids are a **shared contract** across all characters, defined once in
`constants.asm`. `Player_Animate` only ever writes ids; it never knows which
character it animates. Each character's `Ani_<char>` table is ordered by these
ids, so the same id resolves to that character's own frames.

```
ANIM_WALK      = 0
ANIM_RUN       = 1
ANIM_ROLL      = 2        ; also the air ball (jump/airball) — alias ANIM_BALL
ANIM_SPINDASH  = 3
ANIM_PUSH      = 4
ANIM_IDLE      = 5        ; wait/idle (neutral hold → foot-tap tail)
ANIM_BALANCE   = 6
ANIM_LOOKUP    = 7
ANIM_DUCK      = 8
ANIM_SKID      = 9
ANIM_GETUP     = 10
ANIM_BALL      = ANIM_ROLL ; explicit alias for air states
```

A build-time assert keeps `Ani_Sonic`'s entry count in sync with the id count.

---

## Section 2 — `Player_Animate` (selection) + new signals

Replaces the inline if/else currently in `Player_Display` (`player_common.asm`
~249-276). Selection is by priority, highest first:

| Pri | Condition | Anim | Engine status |
|----|-----------|------|----------------|
| 1 | `PSTATE_SPINDASH` | `ANIM_SPINDASH` | state exists |
| 2 | ball states (roll / jump / rolljump / airball) | `ANIM_ROLL` | exists |
| 3 | grounded, input opposes inertia, `\|gsp\| ≥ PHYS_SKID_MIN` | `ANIM_SKID` | NEW (compute in-select + latch) |
| 4 | grounded, `ST_PUSHING` | `ANIM_PUSH` | signal wired |
| 5 | grounded ~rest, DOWN held | `ANIM_DUCK` | NEW (input read in-select) |
| 6 | grounded ~rest, UP held | `ANIM_LOOKUP` | NEW (input read in-select) |
| 7 | grounded, `\|gsp\| ≥ ANIM_RUN_THRESHOLD` | `ANIM_RUN` | NEW threshold |
| 8 | grounded, moving | `ANIM_WALK` | exists |
| 9 | grounded, rest, support at ledge edge | `ANIM_BALANCE` | NEW (edge sensor) |
| 10 | grounded, rest | `ANIM_IDLE` (→ wait) | exists |

Air uncurled (`PSTATE_AIR`) keeps the walk/run cycle from carried `gsp`, as
today. The existing ball-state ordering assert in `constants.asm` is preserved.

**Skid, duck, look-up are display conditions, not new `PSTATE`s.** They are
classified read-only inside `Player_Animate` from input + inertia. No
state-machine changes, no new persistent status bits. Duck continues to feed the
existing spindash trigger in `PState_Ground` exactly as today (this routine does
not consume or alter the down-press).

**Skid latch (refinement).** Without a latch the skid pose flickers as
input/inertia cross the threshold each frame. A single transient byte
(`skid_latch` in the player overlay) holds the skid pose through the brake; it is
cleared when the player stops (`gsp == 0`) or inertia reverses sign to match
input. This is what makes the brake read as "normal."

**Get-up one-shot (refinement).** Leaving duck or spindash back to rest plays
`ANIM_GETUP` once, then falls through to idle. Implemented as a one-shot
transient in select (e.g. a small countdown), not a `PSTATE`.

**Look/duck camera pan — explicit deferred hook.** S3K pans the camera after a
hold delay while ducking/looking up. That is a camera-system concern, out of
scope here, but is left as a **named, wired, zero-valued** seam
(`Player_LookOffset`) so it is a deliberate future hook, not a forgotten one.

**Balance (the one new sensor).** Only computed when grounded-at-rest (so it is
cheap — gated behind the rest condition). A small helper checks whether the
support sensor sits at/over a ledge edge; if so, select `ANIM_BALANCE`. Faces
the player toward the drop, per S3K. This is the highest-effort new signal and
gets a dedicated implementation task with its own research step.

---

## Section 3 — Speed-scaled animation timing (generalized)

S3K plays walk/run/roll faster as the character accelerates. Rather than
hardcoding the formula in player code, generalize it in the **animation format**.

Byte 0 of an animation script is normally a literal frame-hold. We reserve two
sentinel values **for byte 0 only** (the frame bytes own `$F7–$FF`; byte 0 is a
separate namespace, so there is no collision):

```
DUR_SPEED       ; walk/run cycle: hold = f(|speed|)
DUR_SPEED_ROLL  ; roll: faster curve
```

`AnimateSprite`, when it loads/reloads the per-animation duration and sees a
sentinel, takes the hold from a small caller-populated field
(`SST_anim_dyn_dur`) instead of the script byte. The **player** computes that
value once per frame from `_pl_gsp` (e.g. an S3K-style
`hold = max(0, BASE - (|gsp| >> N))`; exact constants chosen in the
implementation task after research) and writes it before calling
`AnimateSprite`. Generic objects never use sentinels, so they never read the
field and pay only one compare. This keeps the mechanism reusable (anything that
spins faster as it moves) and out of the player-specific code path.

The walk↔run split (Section 2 priority 7) is independent of timing: it selects
which animation plays; speed-scaling sets how fast it cycles.

---

## Section 4 — Shared spindash

Relocate `PState_Spindash` and its enter/exit hooks
(`PHook_SpindashEnter` / `PHook_SpindashExit`) out of `sonic.asm` into shared
player code (new `engine/player/player_spindash.asm`). `Player_States` and the
hook tables already reference the labels — this is a move, not a rewrite, and the
cross-file reference becomes a same-tier shared reference.

The spindash **animation** resolves through `ANIM_SPINDASH` in each character's
own `SST_anim_table`, so Tails/Knux automatically get their own spindash frames
when those characters exist. After this move, `sonic.asm` holds only
genuinely Sonic-specific items: `Sonic_InitAssets`, `Sonic_LoadArt`, and the
Sonic physics table.

Spindash physics, charge curve, release formula, and camera freeze are
unchanged. Dust object remains deferred (DEFERRED_WORK.md §5).

---

## Section 5 — Animation data

Rewrite `data/animations/sonic_anims.asm` as the full normal-play set, ordered by
the `ANIM_*` ids, using frames already present in the migrated `sonic.bin`:

- **Walk / Run / Roll** — `DUR_SPEED` / `DUR_SPEED_ROLL` sentinel durations.
- **Spindash** — fast rev cycle (existing `$86–$8B` frames).
- **Push** — `$B6–$B9` cycle.
- **Idle/Wait** — neutral hold that transitions to a foot-tap tail after a long
  delay (S3K-style), replacing the current "borrow walk frame 5" stopgap.
- **Balance** — teeter frames (`$A4–$A6`).
- **Look-up** (`$C3–$C4`), **Duck** (`$9B–$9C`), **Skid/Stop** (`$9D–$A0`),
  **Get-up** (`$8F`).

Exact frame lists are confirmed against the mapping/DPLC binary during
implementation (the indices above are the S2 art map and are expected to hold,
but are verified, not assumed).

---

## Section 6 — DPLC / VRAM verification (no code change, must verify)

The art + DPLC pipeline already maps frame → DMA and needs no code change. **But**
the character VRAM reservation `VRAM_TEST_SONIC` is documented as "up to 25
tiles." Some newly-used frames (push, balance, spindash) may need more tiles than
the current walk/idle/roll worst case. If any frame's DPLC tile total exceeds the
reservation, its DMA overflows into neighboring VRAM.

Before authoring data, compute the **real worst-case per-frame tile count** from
`data/dplc/optimized/sonic.bin` across all frames the new scripts reference, and
size `VRAM_TEST_SONIC` accordingly. Add a build-time assert
(`worst_case_tiles ≤ reservation`) so this can never regress silently.

---

## Section 7 — Verification harness (debug anim viewer)

A `DEBUG`-gated anim-viewer mode for visual verification:

- An input combo toggles viewer mode; in viewer mode the player is **frozen**
  (position held, physics/state dispatch skipped, reusing the existing debug-fly
  suspend path) and `Player_Animate`'s output is **overridden** with a
  manually-selected `ANIM_*` id.
- An input steps the forced id forward/back through the full `ANIM_*` set.
- For the speed-scaled ids (walk/run/roll) the viewer injects a fixed `_pl_gsp`
  so the cycle actually animates and timing can be eyeballed.
- Build once, step through every animation, capture a screenshot per id via the
  Exodus MCP, and confirm: frames are clean (no torn/garbage tiles → DPLC/VRAM
  correct), and each animation reads as expected.

The viewer lives behind the `DEBUG` switch and never ships in a release build.

**Verification loop per animation:** rebuild ROM → `emulator_reload_rom` →
step to the id → `emulator_screenshot` → inspect. Note the Exodus MCP socket was
unavailable at design time; reconnect before the verification task.

---

## Files touched

| File | Change |
|------|--------|
| `constants.asm` | `ANIM_*` ids, `ANIM_RUN_THRESHOLD`, `DUR_SPEED*` sentinels, skid-latch/look-offset overlay fields, VRAM reservation + assert |
| `engine/player/player_common.asm` | `Player_Animate` (new), `Player_Display` calls it; viewer override hook |
| `engine/player/player_spindash.asm` | NEW — relocated `PState_Spindash` + hooks |
| `engine/player/sonic.asm` | remove spindash state/hooks (now shared) |
| `engine/player/player_ground.asm` | balance edge-sensor helper (new); duck trigger unchanged |
| `engine/objects/animate.asm` | speed-scaled duration sentinel handling |
| `data/animations/sonic_anims.asm` | full animation set |
| `main.asm` | include `player_spindash.asm` |
| `docs/ENGINE_ARCHITECTURE.md` §5 | document anim selection, speed-scaling, shared spindash |
| `docs/DEFERRED_WORK.md` | mark spindash-shared done; note dropdash/insta-shield, look/duck camera pan |

## Verification / done criteria

- Build clean; all build-time asserts pass (ANIM id sync, ball-state order,
  VRAM worst-case ≤ reservation).
- Debug anim viewer: every `ANIM_*` id renders clean, correct frames; speed-scaled
  ids visibly animate.
- In normal play (viewer off): walk→run splits at speed and cycles faster with
  velocity; roll spins with speed; push/skid/duck/look-up/balance/wait each
  trigger in their real situations and read correctly.
- Spindash behaves identically to before the relocation (charge, release,
  camera freeze), now from shared code.
- `sonic.asm` contains no spindash state logic.
```
