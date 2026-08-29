# Character collision box / sprite alignment audit

**Date:** 2026-08-28 · **Scope:** Sonic, Tails, Knuckles × every state · **Verdict: no engine
defect found. The one real symptom was an art fact inherited from stock S3K — since fixed.**

Prompted by: *"Tails when rolling is like a pixel above ground. We should make sure all sizes
for the characters are correct."*

Re-measure any time with `python3 tools/measure_character_boxes.py` (reads every radius from
source, so it re-measures rather than repeating this file). **Where this file and that tool
disagree, the tool is right** — it measures, this file records.

> ### RESOLVED 2026-08-29 (`parcel/ball-seating`)
>
> The owner ruled **d-36 = flush** (*"theyy should all be flush"*): all three rolling balls
> seat on the collision floor. §8's **Option B is what shipped**, in
> `games/sonic4/data/characters_staging/gen_characters.py` as ruled — but with the shift
> **derived** (`BALL_Y_RADIUS − max(lowest opaque art row over the ball frames)`) rather than
> typed, so a radius change, an animation-table edit or an art re-export re-derives it. The
> derivation reproduced the audited numbers exactly: **Tails `$96-$98` `+1`, Knuckles
> `$96-$9A` `−2`**, Sonic untouched.
>
> §8's *"no gate was added either"* is superseded for one row only:
> `tools/test_ball_seating.py` now asserts `delta == 0` for the three `Roll` rows, run
> build-fatally by `build.sh`'s tool-suite lane. Every other row stays a report, for exactly
> the reasons §8 gives.
>
> The measured numbers below are **pre-fix** except where marked. §5's ball rows and the two
> tables under them carry both.

---

## 1. The answer in one line

Rolling Tails floated exactly **1 px**. His collision box was correct, the curl arithmetic was
correct, the sensors were correct, and the render path added no offset. **His ball ART was
28 px tall where the shared ball collision box is 29 px**, drawn concentric on `y_pos`, so its
bottom row landed one pixel short of the collision floor. That art is stock Sonic 3 & Knuckles
and stock S3K has the same gap.

It read as a bug *here* and not in S3K because **our Sonic's art is not S3K's**. Sonic's
mappings come from S2 / `sonic_hack`; Tails' and Knuckles' come from skdisasm. The S2 Sonic
ball happens to sit flush, so Tails was being compared against a neighbour that stock S3K
never had.

Both S3K balls are now shifted onto the floor in the generator (see the banner above); the
28 px art is unchanged, it is the mapping piece that moved.

---

## 2. How the two subsystems meet

The only quantity that connects a collision box to a drawn sprite:

```
delta = (lowest opaque art pixel row, relative to y_pos)  -  y_radius
```

`delta = 0` means the sprite's bottom row is exactly the collision floor. The engine computes
the on-screen Y as

```
SAT_Y = y_pos.int - Camera_Y + 128 + piece.y_off
```

(`engine/objects/sprites.emp:250-255, 341-358, 602-621`) — **no per-state, per-character or
per-animation term exists anywhere.** The SST has no render-Y field. Verified by reading the
whole sprite path plus every `y_pos` reference in `games/sonic4/player/*.emp`. So a vertical
discrepancy is either baked into a mapping frame's `y_off` or is a real `y_pos`/box difference.
There is no third channel.

**The `delta = 0` reading is empirically anchored, not assumed.** Across the three characters,
**29 of the 36 reachable grounded states landed on exactly `delta = 0`** (31 after the ball
fix) — every walk, run, push, idle, look-up, duck, skid and spindash frame for all three. That
is what makes the nonzero rows below meaningful rather than noise. (Counting only states a
character can enter:
11 grounded states each for Sonic and Tails, 14 for Knuckles. The glide/slide/climb rows in
Sonic's and Tails' animation tables are unreachable placeholders that reuse their walk frames.)

---

## 3. The boxes, as installed

All boxes are stored as **full dimensions (2r+1)**, packed `W<<8|H`, in each `CharacterDef`
(`engine/structs.emp:256-289`). The sensors halve them with `lsr`
(`games/sonic4/player/player_sensors.emp:348-352`), so 39→19, 31→15, 29→14, 21→10 — exact,
because 2r+1 is always odd.

| | Sonic | Tails | Knuckles | S3K reference |
|---|---|---|---|---|
| standing | 9 × 19 | 9 × **15** | 9 × 19 | `Sonic_Init` `$13`/`9`, `Tails_Init` `$F`/`9`, `Knuckles_Init` `$13`/`9` (sonic3k.asm:21908, 26107, 30355) — **exact match** |
| rolling | 7 × 14 | 7 × 14 | 7 × 14 | `#$E`/`#7` shared by all three (sonic3k.asm:23265) — **exact match** |
| ability | none (`0`) | none (`0`) | 10 × 10 | `Knux_Test_For_Glide` `#$A`/`#$A` (sonic3k.asm:32566) — **exact match** |
| debug-fly | 16 × 16 | 16 × 16 | 16 × 16 | S3K's debug never touches the radii; its **exit** hardcodes `#$13`/`#9` regardless of character (sonic3k.asm:200105) — **we are better than S3K here**, see §6 |

Sources: `engine/system/constants.emp:128-131` (`PLAYER_X_RADIUS 9`, `PLAYER_Y_RADIUS 19`,
`BALL_X_RADIUS 7`, `BALL_Y_RADIUS 14`), `games/sonic4/player/tails.emp:46`
(`TAILS_Y_RADIUS 15`), `games/sonic4/player/knuckles.emp:64` (`KNUX_ABILITY_RADIUS 10`),
`games/sonic4/player/player_common.emp:1494-1496` (debug).

## 4. The y-position adjustments, as applied

The engine derives every shift from the two boxes involved rather than hardcoding it
(`PHook_EnsureStanding` / `PHook_EnsureBall` / `PHook_EnsureAbility`,
`games/sonic4/player/player_common.emp:1260-1292`):

```
to standing:  shift = (cd_stand_h - current_h) >> 1     applied as y_pos -= shift
to ball:      shift = (current_h  - roll_h)    >> 1     applied as y_pos += shift   (signed)
to ability:   no shift
```

Both operands are odd, so the difference is even and the `>>1` is exact — no truncation, no
half-pixel drift. Feet stay planted across every transition, by construction.

| transition | Sonic | Tails | Knuckles | S3K |
|---|---|---|---|---|
| stand → ball | +5 | **+1** | +5 | `Player_DoRoll` hardcodes `addq.w #5` (:23268); **`Tails_Roll` has its own hardcoded `addq.w #1`** (:28503). Both equal our derived values. **Match.** |
| jump (stand → ball) | +5 | +1 | +5 | derived as `y_radius - default_y_radius` (:23347-23355, :28573-28580, :32489-32496). **Match.** |
| ball → stand | −5 | −1 | −5 | derived, same idiom (:22986-22999, :28230-28243, :32258-32271, and all three `*_TouchFloor`). **Match.** |
| stand → ability | — | — | 0 | S3K applies none (:32565-32567). **Match.** |
| ability → stand | — | — | −9 | S3K's slide get-up derives −9 (:30978-30986). **Match.** Two *other* S3K exits (glide button-release :30730, `LetGoOfWall` :31461) apply **no** shift — see §6. |
| ability → ball (wall jump) | — | — | −4 | S3K applies **no** shift (:31430). **Deliberate divergence** — see §6. |

Everything the dispatching session stated about the constants and the derivation checked out
against source. Nothing in §3 or §4 is wrong.

---

## 5. Where art and box disagree

`delta` per state, as measured on **2026-08-28, before the ball fix**. Every row with
`delta = 0` is omitted. For today's numbers run the tool — this table is a record of what was
found, not a live reading, and only the tool re-measures.

| Character | State | box | y_rad | art rows | delta | reading |
|---|---|---|---|---|---|---|
| **Tails** | **Roll** | roll | 14 | [−14,+13] | **−1** | **THE REPORTED SYMPTOM.** Ball art 28 px in a 29 px box. **FIXED 2026-08-29 → [−13,+14], delta 0.** |
| Knuckles | Roll | roll | 14 | [−15,+16] | +2 | ball art 32 px in a 29 px box — overlaps the ground. **FIXED 2026-08-29 → [−17,+14], delta 0.** |
| Sonic | Roll | roll | 14 | [−15,+14] | 0 | flush — **because his art is S2, not S3K.** Untouched by the fix. |
| Sonic | GetUp | stand | 19 | [−15,+15] | −4 | crouched get-up pose; by design |
| Tails | GetUp | stand | 15 | [−17,+13] | −2 | crouched get-up pose; by design |
| Knuckles | GetUp | stand | 19 | [−13,+13] | −6 | crouched get-up pose; by design |
| Knuckles | Balance | stand | 19 | [−28,+22] | +3 | teeter pose leans past the box; by design |
| Tails | Fly / FlyTired | stand | 15 | [−16,+11] | −4 | legs tucked; airborne, no floor to touch |
| Knuckles | Glide 0/1/3/4 | ability | 10 | [−12,+11] | +1 | horizontal pose, airborne |
| Knuckles | GlideFall | ability | 10 | [−24,+22] | +12 | tumble pose, airborne |
| Knuckles | SlideGetUp | ability | 10 | [−9,+19] | +9 | standing up *out of* the 10×10 box; S3K restores the box in the same frame |
| Knuckles | Climb / Ledge | ability | 10 | [−18,+18] | +8 / +3 | attached to a wall — the vertical box is not the ground contact |

Only the first three rows are ground-contact geometry. **The rest are poses that are not
touching the floor, and their deltas are correct art.**

### The three balls, side by side

Bottom row is the union over each set's ball frames — the same statistic the tool prints and
`tools/test_ball_seating.py` asserts.

| ball art | height | bottom row (before → after) | vs. 14 | source |
|---|---|---|---|---|
| our Sonic | 30 px | +14 → +14 (untouched) | **flush** | S2 / `sonic_hack` (`tools/convert_s2_mappings.py` over `sonic_hack/mappings/sprite/Sonic.bin` reproduces our blob byte-for-byte) |
| **our Tails** | **28 px** | **+13 → +14** | floated 1, now **flush** | stock S3K, shifted `+1` by `gen_characters.py` |
| our Knuckles | 32 px | +16 → +14 | overlapped 2, now **flush** | stock S3K, shifted `−2` by `gen_characters.py` |
| **stock S3K Sonic** | **32 px** | **+15** | **overlaps 1** | measured directly from skdisasm `Map - Sonic.asm` + `Art/Sonic.bin`, frames `$96-$9A` — S3K's own `AniSonic02` roll list. Donor, not ours; unchanged. |

**Stock S3K does not hold a `delta = 0` invariant for balls at all.** Its three characters give
−1, +1 and +2 against the same shared 14 px radius. Tails was the only one on the floating
side, which is why he was the one that read wrong — and our Sonic being flush (an S2 accident)
gave him a neighbour that looked planted, which stock S3K never did. Ruling d-36 adopts the
invariant S3K lacks, for the balls only.

### The ball frames are not uniform *within* a character (found 2026-08-29)

The row above is a union, and the union hides this. Per ball frame, lowest opaque row:

| set | `$96` | `$97` | `$98` | `$99` | `$9A` | frames in its `Roll` row |
|---|---|---|---|---|---|---|
| our Sonic (before = after) | 14 | 14 | 14 | 14 | **13** | `$96-$9A` |
| our Tails (before) | 13 | 13 | 13 | — | — | `$96-$98` |
| our Tails (after `+1`) | 14 | 14 | 14 | — | — | |
| our Knuckles (before) | **16** | 15 | 15 | 15 | 15 | `$96-$9A` |
| our Knuckles (after `−2`) | 14 | 13 | 13 | 13 | 13 | |

So **"flush" cannot mean per-frame flush for a rigid shift**: Knuckles' `$96` reaches 1 px
lower than his other four, and Sonic's `$9A` — untouched, and already accepted — stops 1 px
short of his other four. That variation is inside the drawn pixels. The shipped rule is the
one our reference character already satisfies: **the deepest ball pixel rests on the floor and
none sinks past it**, i.e. `max == BALL_Y_RADIUS`.

**Open, for the owner's eye rather than a measurement** (§9): Knuckles at `−2` has 1 frame
flush and 4 floating 1 px, where `−1` would give 4 flush and 1 overlapping 1 px. `−2` is what
the rule derives and what d-36 named; `−1` may read better in motion. Flipping it is a
one-line change of the statistic in `derive_ball_shift`, not a magic number.

Verified at the byte level, because this is the load-bearing claim. **Every ball frame in all
four sets is a single 32×32 piece with tile 0 and no flip** — the mappings are structurally
identical, so nothing about the *art* difference lives in the mapping; the fix moves the one
field that does:

| set | piece `y_off` before → after | opaque rows within the 32 px cell (union) |
|---|---|---|
| our Sonic (S2) | −16 → −16 | 1‥30 — a 30 px ball, centred, 1 px inset top and bottom |
| our Tails (S3K) | −16 → **−15** | 2‥29 — a 28 px ball, centred, 2 px inset |
| our Knuckles (S3K) | −15 → **−17** | 0‥31 — fills the cell |
| stock S3K Sonic | −16 | 0‥31 — fills the cell |

(S3K Sonic's frame `$96` reads `dc.w 1` / `dc.b $F0,$F,0,0,$FF,$F0` in
`skdisasm/General/Sprites/Sonic/Map - Sonic.asm:1091-1092` — `y=−16`, size `$F` = 4×4 cells,
tile 0, `x=−16` — the same shape as ours.)

---

## 6. Divergences from S3K, all deliberate, all in our favour

1. **Tails' debug-mode exit.** S3K's `sub_92AD4` hardcodes `#$13`/`#9` with no character test
   (sonic3k.asm:200105-200106) and never rewrites `default_y_radius`, so **S3K's Tails leaves
   debug mode with a 4 px oversized box** until his next jump/roll/landing. Ours reads the
   record (`Player_DebugExit` → `set_standing_size`,
   `games/sonic4/player/player_common.emp:1507-1512`) and is correct for every character.

2. **Knuckles' wall-jump.** S3K sets the ball radii with no y compensation (:31430), dropping
   his box bottom 4 px instantly. `PHook_EnsureBall` derives −4 and keeps the feet planted.

3. **Knuckles' glide release / let-go-of-wall.** S3K restores `$13`/`9` with no y compensation
   (:30730-30731, :31461-31462) — 9 px of sudden box growth downward — while its *other* two
   exits from the same box derive the −9. Ours derives −9 uniformly.

4. **Curl shift derivation.** S3K hardcodes the constant per routine (`#5` for Sonic/Knuckles,
   `#1` for Tails) and re-derives it in others. Ours derives it once from the record. Same
   numbers, one source.

In S3K, cases 2 and 3 are absorbed by `Player_AnglePos`'s floor re-snap on the next *grounded*
frame — which does not run while airborne, and which is bounded (penetration corrected only up
to 14 px; a gap larger than `min(|x_vel| + 4, 14)` makes the player fall instead). Our derived
shifts mean nothing has to be absorbed.

---

## 7. What was ruled out, with the arithmetic

- **Not the collision box.** Standing 9×15 and rolling 7×14 for Tails are byte-exact against
  `Tails_Init` and the shared `#$E`/`#7`.
- **Not the curl shift.** `(31 − 29) >> 1 = 1`. Standing Tails rests at `y_pos = G − 15`;
  curled he goes to `G − 14`; feet at `(G − 14) + 14 = G`. Exact, no re-snap needed. (S3K's own
  `Tails_Roll` hardcodes the same `+1`.)
- **Not the sensors.** `player_sensors.emp:348-352` halves whatever is in
  `width_pixels`/`height_pixels`; 29 → 14 for both Sonic and Tails, so the two characters rest
  at the *identical* `y_pos` while rolling. Whatever differs must be art.
- **Not the render path.** No render-only Y term exists (§2). The camera's
  `Camera_Curl_Offset` (`engine/level/camera.emp:344-346`) moves the whole screen, not the
  player within it.
- **Not the asset conversion.** *(True as audited; deliberately no longer true, see below.)*
  Neither `gen_characters.py`'s `emit_mappings` nor `convert_s2_mappings.py` applied any
  geometric transform — the S3K signed byte Y was sign-extended to a word and written verbatim.
  The only content transform was a palette index permutation of Tails' *pixels*, which cannot
  move anything. **Since 2026-08-29 `gen_characters.py` DOES apply one geometric transform, and
  only one**: `derive_ball_shift`/`apply_ball_shift` move the ball frames' piece `y_off` by a
  shift derived from `BALL_Y_RADIUS`. Every other frame of every set is still verbatim.

---

## 8. Recommendation — Option B, ruled and shipped

*Written 2026-08-28 while the ruling was still open; kept because its reasoning is why the
shipped fix has the shape it has. **The owner ruled Option B on 2026-08-28 and it landed on
2026-08-29** — see the banner at the top of this file.*

The cause is proven and it is art, not code, and the fix was an aesthetic ruling that belonged
to the owner:

- **Option A — leave it.** Current state is faithful to stock S3K for the two S3K-sourced
  characters. Sonic is the odd one out, and only because his art is S2.
- **Option B — seat all three balls flush.** Shift Tails' three ball frames (`$96-$98`) `+1`
  and Knuckles' five (`$96-$9A`) `−2` in their mapping `y_off`. This is a *consistency* choice,
  not a correctness one: it makes the roster uniform and deliberately diverges from S3K for all
  three characters. It must be done in `gen_characters.py` (which ships the blobs) so a
  regenerate cannot silently revert it.
- **Option C — match stock S3K exactly.** Re-source Sonic's art from S3K, at which point all
  three balls overlap or float as Sega drew them, and Tails stops looking singular.

Option B is the only one that removes the symptom. It was not landed *in this audit* because
picking `+1` to make a symptom disappear is indistinguishable from tuning a magic number unless
the "all balls flush" rule is adopted as a deliberate project convention — and that is a
content decision, not an engine one.

**The owner adopted it (d-36), so it is now a rule and not a tuned number** — and it is
implemented as a rule: `derive_ball_shift` in `gen_characters.py` computes
`BALL_Y_RADIUS − max(lowest opaque art row over the ball frames)` from source on every run.
There is no `+1` or `−2` typed anywhere; those are outputs.

**The gate is narrow, for the reason this section gave.** `delta = 0` for *grounded poses* is
still **false by design** — get-up crouches, flight, glide — and a gate over today's whole
measured table would still be a snapshot that cannot tell a regression from an intentional
re-export. `tools/measure_character_boxes.py` still prints that table and nothing asserts it.
What the ruling promoted from observation to convention is exactly the three `Roll` rows, and
`tools/test_ball_seating.py` asserts exactly those, with the radius and the frame set read from
source rather than pinned. Run build-fatally by `build.sh`'s tool-suite lane.

---

## 9. Needs runtime confirmation

Static analysis cannot see the screen. To confirm on the emulator:

1. **Tails, rolling, flat ground.** ~~Expect his ball's bottom row exactly 1 px above the
   ground surface~~ — **superseded by the fix.** Now expect his ball flush against the ground,
   indistinguishable from Sonic rolling on the same tile. Also check the twin-tails appendage,
   which was deliberately NOT shifted (its roll frames are drawn at one of four runtime
   orientations, half of them with both axes flipped, so a uniform mapping shift would move
   half of them the wrong way on screen): the tails now sit 1 px higher relative to the ball
   than before. Expected to be invisible on a spinning blur; nobody has looked.
2. **Knuckles, rolling, flat ground.** ~~Expect his ball to sink 2 px into the ground~~ —
   **superseded by the fix.** Now expect his deepest ball frame flush and the other four
   floating **1 px** (see §5's per-frame table). If that 1 px reads wrong, `−1` instead of
   `−2` is the alternative, and it is a change of statistic in `derive_ball_shift`, not a
   magic number. **This is the one open aesthetic question left by the fix.**
3. **Knuckles, glide → release → land** and **climb → jump off.** These are the two deliberate
   divergences from S3K (§6.2, §6.3). Expect a smooth landing with no vertical pop; a visible
   pop means the derived shift is wrong for a path I could only read statically.
4. **Tails, debug mode enter/exit while rolling.** Expect the standing box restored and no
   vertical jump. The 16×16 debug box is the only even-sized box in the game; `Player_DebugExit`
   is supposed to set the standing box before any hook can see it.
