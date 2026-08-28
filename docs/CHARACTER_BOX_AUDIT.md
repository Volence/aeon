# Character collision box / sprite alignment audit

**Date:** 2026-08-28 · **Scope:** Sonic, Tails, Knuckles × every state · **Verdict: no engine
defect found. The one real symptom is an art fact inherited from stock S3K.**

Prompted by: *"Tails when rolling is like a pixel above ground. We should make sure all sizes
for the characters are correct."*

Re-measure any time with `python3 tools/measure_character_boxes.py` (reads every radius from
source, so it re-measures rather than repeating this file).

---

## 1. The answer in one line

Rolling Tails floats exactly **1 px**. His collision box is correct, the curl arithmetic is
correct, the sensors are correct, and the render path adds no offset. **His ball ART is 28 px
tall where the shared ball collision box is 29 px**, drawn concentric on `y_pos`, so its
bottom row lands one pixel short of the collision floor. That art is stock Sonic 3 & Knuckles
and stock S3K has the same gap.

It reads as a bug *here* and not in S3K because **our Sonic's art is not S3K's**. Sonic's
mappings come from S2 / `sonic_hack`; Tails' and Knuckles' come from skdisasm. The S2 Sonic
ball happens to sit flush, so Tails is being compared against a neighbour that stock S3K never
had.

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
**29 of the 36 reachable grounded states land on exactly `delta = 0`** — every walk, run,
push, idle, look-up, duck, skid and spindash frame for all three. That is what makes the seven
nonzero rows below meaningful rather than noise. (Counting only states a character can enter:
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

`delta` per state. Every row with `delta = 0` is omitted; **24 of 28 grounded states are 0.**

| Character | State | box | y_rad | art rows | delta | reading |
|---|---|---|---|---|---|---|
| **Tails** | **Roll** | roll | 14 | [−14,+13] | **−1** | **THE REPORTED SYMPTOM.** Ball art 28 px in a 29 px box. |
| Knuckles | Roll | roll | 14 | [−15,+16] | +2 | ball art 32 px in a 29 px box — overlaps the ground |
| Sonic | Roll | roll | 14 | [−15,+14] | 0 | flush — **because his art is S2, not S3K** |
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

| ball art | height | bottom row | vs. 14 | source |
|---|---|---|---|---|
| our Sonic | 30 px | +14 | **flush** | S2 / `sonic_hack` (`tools/convert_s2_mappings.py` over `sonic_hack/mappings/sprite/Sonic.bin` reproduces our blob byte-for-byte) |
| **our Tails** | **28 px** | **+13** | **floats 1** | stock S3K |
| our Knuckles | 32 px | +16 | overlaps 2 | stock S3K |
| **stock S3K Sonic** | **32 px** | **+15** | **overlaps 1** | measured directly from skdisasm `Map - Sonic.asm` + `Art/Sonic.bin`, frames `$96-$9A` — S3K's own `AniSonic02` roll list |

**Stock S3K does not hold a `delta = 0` invariant for balls at all.** Its three characters give
−1, +1 and +2 against the same shared 14 px radius. Tails is the only one on the floating side,
which is why he is the one that reads wrong — and our Sonic being flush (an S2 accident) gives
him a neighbour that looks planted, which stock S3K never did.

Verified at the byte level, because this is the load-bearing claim. **Every ball frame in all
four sets is a single 32×32 piece with tile 0 and no flip** — the mappings are effectively
identical, so nothing about the difference lives in the mapping:

| set | piece `y_off` | opaque rows within the 32 px cell |
|---|---|---|
| our Sonic (S2) | −16 | 1‥30 — a 30 px ball, centred, 1 px inset top and bottom |
| our Tails (S3K) | −16 | 2‥29 — a 28 px ball, centred, 2 px inset |
| our Knuckles (S3K) | **−15** | 0‥31 — fills the cell, and the cell itself sits 1 px lower |
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
- **Not the asset conversion.** Neither `gen_characters.py` (:381-405) nor
  `convert_s2_mappings.py` (:113, :137) applies any geometric transform — the S3K signed byte Y
  is sign-extended to a word and written verbatim. The only content transform is a palette
  index permutation of Tails' *pixels*, which cannot move anything.

---

## 8. Recommendation — no fix landed, and why

**Nothing was changed.** The cause is proven and it is art, not code, and the fix is an
aesthetic ruling that belongs to the owner:

- **Option A — leave it.** Current state is faithful to stock S3K for the two S3K-sourced
  characters. Sonic is the odd one out, and only because his art is S2.
- **Option B — seat all three balls flush.** Shift Tails' three ball frames (`$96-$98`) `+1`
  and Knuckles' five (`$96-$9A`) `−2` in their mapping `y_off`. This is a *consistency* choice,
  not a correctness one: it makes the roster uniform and deliberately diverges from S3K for all
  three characters. It must be done in `gen_characters.py` (which ships the blobs) so a
  regenerate cannot silently revert it.
- **Option C — match stock S3K exactly.** Re-source Sonic's art from S3K, at which point all
  three balls overlap or float as Sega drew them, and Tails stops looking singular.

Option B is a one-line change per character in the generator and is the only one that removes
the symptom. It was **not** landed here because picking `+1` to make a symptom disappear is
indistinguishable from tuning a magic number unless the "all balls flush" rule is adopted as a
deliberate project convention — and that is a content decision, not an engine one.

No gate was added either. The honest invariant would be `delta = 0` for grounded poses, and it
is **false by design** for get-up crouches, flight and glide, and false in stock S3K for two of
three balls. A gate asserting today's measured deltas would be a snapshot that cannot tell a
regression from an intentional re-export. `tools/measure_character_boxes.py` prints instead.

---

## 9. Needs runtime confirmation

Static analysis cannot see the screen. To confirm on the emulator:

1. **Tails, rolling, flat ground.** Expect his ball's bottom row exactly **1 px** above the
   ground surface; standing Tails touches it. Compare with Sonic rolling on the same tile —
   Sonic's ball should be flush.
2. **Knuckles, rolling, flat ground.** Expect his ball to sink **2 px** into the ground.
   (Predicted from the art, never observed.)
3. **Knuckles, glide → release → land** and **climb → jump off.** These are the two deliberate
   divergences from S3K (§6.2, §6.3). Expect a smooth landing with no vertical pop; a visible
   pop means the derived shift is wrong for a path I could only read statically.
4. **Tails, debug mode enter/exit while rolling.** Expect the standing box restored and no
   vertical jump. The 16×16 debug box is the only even-sized box in the game; `Player_DebugExit`
   is supposed to set the standing box before any hook can see it.
