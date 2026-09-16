# NIGHT-REGION-LOOK: the night palette becomes a grade, and the ruling's night numbers do not survive re-derivation

Parcel `parcel/night-palette-tone`, 2026-09-16, based on aeon `277ddcdd`.
Companion to `2026-09-16-night-palette-mechanism.md`, which found the mechanism.
Hub ruling: empyrean `290815e` (direction upheld; two of its figures corrected below).

---

## 1. THE HEADLINE, AND IT IS A CORRECTION TO THE RULING I WAS TOLD TO TEST

I was told the ruling's channel means came off `t5-f272-settled.png`, a frame named
*settled* by hand that is in fact mid-fade, and asked to test that claim rather than inherit
it. **It is true, it is sharper than "mid-fade", and it does not contaminate everything the
ruling said — only half of it.**

`t5-f272-settled.png` is the **penultimate fade frame, and it is one step short in RED and in
red alone.** Every one of its seven unaccounted colours (45.9% of the frame, which the
mechanism note could not explain and honestly said so) is the settled night colour with the
red channel exactly one rung high:

| unaccounted colour | = night entry | + red |
|---|---|---|
| `(3,1,1)` | idx 21 `(2,1,1)` | +1 |
| `(2,0,1)` | idx 20 `(1,0,1)` | +1 |
| `(4,2,2)` | idx 22 `(3,2,2)` | +1 |
| `(5,3,3)` | idx 23 `(4,3,3)` | +1 |
| `(1,4,1)` | idx 30 `(0,4,1)` | +1 |
| `(5,5,0)` | idx 12 `(4,5,0)` | +1 |
| `(3,5,3)` | idx 31 `(2,5,3)` | +1 |

**Seven specific colours out of 512 — 1.4% of the colour space.** The mechanism note killed
an earlier explanation of this residue because it accepted 145 of 512 colours (28%) and
therefore distinguished nothing. This one is not that: green and blue have arrived at their
night values everywhere and red has one rung left, which is a single, falsifiable statement
about the fade's state, and every affected entry is named. It also agrees with the v2 set's
own measured step model (`Palette_DoFade` steps on odd counts; max channel distance 3).

### What that does to the ruling's numbers

I re-derived every figure from the certified set, `docs/captures/2026-09-16-night-settled-v2/`.
Method: take a certified DAY frame and recolour it through the night map, so the **art is held
fixed and only the palette varies**. (The camera moves 112 px between the last certified day
frame and the first certified night one, so measuring day and night frames directly against
each other confounds palette with scenery. The map is well defined on colours — see that
directory's sibling README in `2026-09-16-night-grade-options/` — and all seven certified
frames decode 100.0% to their own palette with zero residue.)

| quantity | ruling | re-derived | verdict |
|---|---|---|---|
| day dirt mean RGB | 165 / 104 / 42 (`t5-f267-cross`) | **176 / 103 / 42** | **agrees** (G and B exact; R 7% low) |
| day canopy+trunk mean value | ~29 (`t5-f185-before`) | **28.8** | **agrees, exactly** |
| night dirt mean RGB | 91 / 29 / 39 (`t5-f272-settled`) | **66 / 31 / 42** | **red inflated 38%** |
| night canopy V | ~14 | **15.2** | agrees |
| night trunk V | ~17 | **9.7** | **inflated 75%** |
| night dirt saturation | "as high as the day colour" (0.70 measured) | **0.54** vs day 0.76 | **overstated** |
| night dirt hue | (not quoted) | **336 deg** vs day 27 deg | ruling's *description* understates it |

**So: the ruling's DAY figures are sound and its NIGHT figures are inflated in the warm
channels, always in the direction of "less night" — exactly the mid-fade signature, and
exactly the channel (red) the frame is short in.** I measured `t5-f272-settled`'s own dirt
band at **92.8 / 27.8 / 38.7**, which is the ruling's 91/29/39 to within a rounding, so the
provenance is confirmed as well as the defect.

**And the direction survives intact — in one place it survives MORE than intact.** The dirt's
true night hue is 336 deg against day's 27 deg: a 51-degree rotation across the red boundary
into magenta. The canopy/trunk band is blacker than the ruling thought, not less black. The
one clause that was inflated in the ruling's favour is "saturation as high as the day colour",
which is 0.54 against 0.76 — still a bad number, not the identical one the ruling claimed.

**What would have made me disagree with the ruling:** a day-side figure off by more than a
few per cent, or a night dirt red at or below 66 in `t5-f272` (which would have meant the
frame was not inflated and the difference lay in my method). Neither happened.

### Two corrections to my own brief

* The `DEFECT.md` is beside **`docs/captures/2026-09-16-night-settled/`** — the first,
  superseded run of the settle tool — not beside the 09-13 set, and it documents a different
  defect (zero day controls certified).
* **`06-night-landed.png` is in `docs/captures/2026-09-15-regions-p2-e2/`**, not in the 09-13
  set. See §5.

---

## 2. THE FIX: half the light, three quarters of the blue

`OJZ_Palette_Night` is no longer 48 literals. It is `night_palette(OJZ_Palette)` — a
**per-channel multiplicative scale in eighths**, round half up, with a floor that keeps any
lit channel lit:

```
const NIGHT_LIGHT_8 = 4     // red and green
const NIGHT_BLUE_8  = 6     // blue — the blue lean, and the transform's ONLY asymmetry
n = (v * s8 + 4) / 8,  floored at 1 for v > 0,  capped at 7
```

**Red and green share one scale on purpose.** Equal scales preserve the red:green ratio
exactly on every colour, so a warm colour cannot rotate toward magenta however dark it is
taken. The wine-red is not reduced here; it is structurally unreachable. Blue leaning is then
one number rather than an accident of which channel had the smallest subtrahend.

The rounding rungs, which every property below follows from and nothing else:

```
s8 = 4 (R,G):  v 1..7 -> 1 1 2 2 3 3 4    ratios 1.00 .50 .67 .50 .60 .50 .57
s8 = 6 (B):    v 1..7 -> 1 2 2 3 4 5 5    ratios 1.00 1.00 .67 .75 .80 .83 .71
```

Every rung is ≤ 1.00, so nothing brightens. Every rung is ≥ 1 for v ≥ 1, so nothing dies.

### Measured, art held fixed

| | day | subtraction (was) | grade 4/6 (is) |
|---|---|---|---|
| canopy+trunk black-pixel fraction | .636 | **.751** | **.636** |
| canopy+trunk mean value | 28.8 | 12.9 | 17.3 |
| dirt hue / saturation | 27 deg / .76 | **336 deg** / .55 | 21 deg / .57 |
| area-weighted blue share | .146 | .339 | .222 |
| luminance retention, 42 lit entries | — | **0-100%, span 100** | **50-100%, span 50** |
| distinct colours surviving | 39/39 | 33/39 | 36/39 |

The black-fraction row is the sharpest number in the parcel and it is the one the ruling was
describing when it said the canopy "merges foreground pillars with the gaps between them":
the subtraction turns **11.5 percentage points** of the canopy/trunk band black, i.e. it
deletes 18% of everything that had been visible there. The grade leaves it at the day value
exactly, because no colour crosses the black line at all.

### The stragglers, answered in both directions at once

The ruling asked for the two full-daylight elements to be brought into the night set. What
was actually wrong was the retention **spread**, and both ends of it moved:

| idx | day | area | OLD ret | NEW ret | what it is |
|---|---|---|---|---|---|
| 17 | `$0002` | 721 | **0%** | 100% | trunk dark — was DELETED, is now kept |
| 25 | `$0020` | 4483 | **0%** | 100% | canopy dark — was DELETED, is now kept |
| 31 | `$06EA` | 518 | 65% | 58% | the bright vine/grass highlight, brought down |
| 12 | `$00EE` | 256 | 66% | 57% | (the 16x16 free-flight cursor, not content) |
| 21 | `$026A` | 17692 | 38% | 64% | the dominant dirt tone |

The 100% class has exactly four members — `$0002` (1,0,0), `$0020` (0,1,0) at two indices, and
`$0202` (1,0,1) — and every one of them is a colour whose lit channels are already at the dimmest
non-black step their scale allows. They keep 100% **by arithmetic necessity**, not by escaping the
grade, and they are precisely the canopy and trunk darks the ruling wanted lifted out of black. A
pin asserts the class contains nothing else, and the pytest lane asserts it entry by entry.

**Also worth recording: part of the "full daylight" impression was the mid-fade frame.** The
grass patch in `t5-f272` renders as `(3,5,3)` and `(1,4,1)` — one red rung above the settled
`(2,5,3)` and `(0,4,1)` — so it looked paler and warmer in that capture than it ever was on
a settled frame.

### The three collapsed pairs, named

The merge budget is 3 (39 distinct day colours -> 36 distinct night ones). It is a budget rather
than a zero because 39 distinct colours cannot all stay distinct inside a darker box of a 3-bit
cube. Which three, with their area in the certified day frame:

| night colour | day colours that collapse into it | areas |
|---|---|---|
| `(36,36,72)` | `$0624` idx 38, `$0444` idx 9 | 0 px, 0 px |
| `(0,72,72)` | `$0460` idx 27/35, `$0680` idx 36 | **1166 px**, 0 px |
| `(72,36,109)` | `$0828` idx 39, `$0848` idx 40 | 0 px, 0 px |

Two pairs are invisible in every frame of the v2 set; the third pairs a drawn colour with an
undrawn one. So no art edge that is actually drawn in these captures stops being an edge. **That
is evidence about these frames and not about the act** — a section this run never entered could
draw `$0680` beside `$0460`, and nothing offline can see it. The pin is a canary for exactly that.

**And the property that makes this structural rather than a touch-up:** retention over
darkenable colours is capped at **76%**. No element can stay at daylight, because no element
is allowed to keep more than three quarters of its light.

### The one thing the ruling asked for that I did not deliver

The ruling asks for canopy+trunk mean value **20-22**; the grade gives **17.3**. This is not
a choice I made, it is a ceiling I hit: reaching 20 on a 3-bit palette requires
`NIGHT_LIGHT_8 ≥ 6`, which leaves the whole world at about 80% of daylight and is no longer a
night. The scan behind that is in `docs/captures/2026-09-16-night-grade-options/`. The ruling's
20-22 was itself derived as "roughly halfway back" from a contaminated 14-17; re-derived,
halfway between the true 12.9 and day's 28.8 is 20.9, so its arithmetic was right and its
input was not, and the target it implies is still out of reach. Fixing the crush alone buys
12.9 → 17.3 and returns every silhouette, which was the *purpose* the 20-22 was serving.

---

## 3. THE PINS, AND THE RED-FIRST SWEEP THAT PROVED EACH ONE BITES

Fourteen module-level `ensure`s in `games/sonic4/data/effects/ojz_effects.emp`, zero bytes,
evaluated in every build of every shape because the module is reachable from
`OJZ_Preset_Night`. **The runner is `./build.sh` and therefore `./tools/landing_build.sh`.**

Eleven mutations, each applied to the working tree on disk (diff captured), built with
`sigil build --aeon . --native --game sonic4`, then restored with `git checkout --` from the
**committed** baseline and re-verified clean. Baseline before and after: `rc=0`, 0 errors.

| # | mutation applied on disk | rc | pins fired |
|---|---|---|---|
| M1 | `NIGHT_BLUE_8 6 -> 4` (lean removed) | 1 | lean_ineq, blue_night, distinct_night |
| M2 | `NIGHT_LIGHT_8 4 -> 3` | 1 | ret_min, blue_night, distinct_night |
| M3 | floor `if v > 0 && n < 1 { n = 1 }` deleted | **0** | **NONE — see below** |
| M4 | `NIGHT_BLUE_8 6 -> 9` | 1 | range_ineq, brighter, ret_max_lit, ret_100_class, blue_night, distinct_night |
| M5 | `night_src_word` poisoned to return 0 | 1 | **lit_entries**, ret_min, ret_max_lit, ret_100_class, distinct_day, distinct_night |
| M6 | round-half-up -> round-half-down (`+4` dropped) | 1 | ret_min, blue_night, distinct_night |
| M7 | floor deleted **and** `NIGHT_LIGHT_8 -> 3` | 1 | **black_set (3), dead_channels (9)**, ret_min, ret_max_lit, ret_100_class, blue_night, distinct_night |
| M8 | scale replaced by a subtraction (R,G -2, B -1) | 1 | black_set, dead_channels, + 5 |
| M9 | `night_blue_permille` sums the GREEN channel | 1 | **blue_day**, blue_night |
| M10 | the embed points at a 32-byte file | 1 | **embed_len**, lit_entries, distinct_day, distinct_night, ret_max_lit |
| **M11** | **`night_word` replaced by the recipe that ACTUALLY SHIPPED** (r-3, g-2, b-0, clamped) | 1 | black_set (**4**), dead_channels (**26**), ret_min (**0%**), ret_max_lit (**100%**), blue_night (547), distinct_night (33) |

M11 is the one that matters: **the guard set refuses, by name and with the right counts, the
palette this parcel replaced.** Four entries cross the black line — the four the mechanism
note identified independently, from CRAM read off a booted ROM.

M5 is the anti-vacuity demonstration. Poison the reader so the palette reads as 48 black
words and six pins report "no faults" — they count faults, and a palette with nothing in it
has none. The `lit_entries == 42` pin is the only thing standing between that and a green
build, which is why it is first.

### M3 IS A FINDING, NOT A GAP: the floor is redundant at the shipped scale

Deleting the non-zero floor alone left the build **green**, and invariant 8(c) says an applied
mutation that stays green is a runner defect to fix rather than a pass. It is not one here,
and the reason is arithmetic: at `s8 = 4`, round half up already carries `v = 1` to
`(4 + 4) / 8 = 1`, so the floor never executes. It becomes load-bearing the moment the knob
goes **down** — the same deletion at `s8 = 3` (M7) reports 3 new blacks and 9 dead channels.
The proof that the runner IS executing the patched line is M7 itself, which differs from M3
only by the constant. This is now written at the function, because a reader who deletes a
guard rail "since nothing fires on it" would remove it from exactly the direction the look is
most likely to be tuned.

### The method changed partway, and what that cost (invariant 8(e))

**I credited rounding to the design, and my own new test caught it.** The blue-lean pin first
compared the graded palette (406 permille) against the DAY palette (337) and read the
69-permille gap as the lean. It is not. Scale blue by *exactly* the light factor — no lean
whatsoever — and the share still rises to **341**, because round-half-up and the non-zero
floor act hardest on the smallest channel value, and in this art blue is usually the smallest.

The correct control is the **even scale**, not the day palette. `night_blue_permille` now
takes both scales and the pins are three rows — day 337 (via the identity scale 8/8), no-lean
control 341, shipped 406 — with the middle row's only job being to be the thing the third is
compared against. Every earlier claim in this note that quotes a blue figure has been
re-derived under that control; the retention, black-fraction, hue and distinct-colour figures
never used the day palette as a control and are unchanged.

### The second lane

`tools/test_night_palette_grade.py`, 16 rows, run by the pre-build `pytest tools` lane
(14 rows) and the post-build `needs_build` lane (2 rows, declaring `s4.bin` + `s4.lst`). It
does the two things a comptime `ensure` structurally cannot:

1. **reads the EMITTED words** out of `s4.bin` at the address `s4.lst` gives, and compares
   them against an independent Python derivation from the same `.bin` and the same two
   constants. The old palette was a literal; this one is a fold, and a fold that is right in
   the compiler and wrong in the image is a class this tree has had no check for.
2. **requires every mirrored predicate to be falsifiable**, by feeding it a palette built to
   violate it — including the shipped subtraction, which it must report as exactly 4 crushed
   colours and a 0-100% retention range.

It does **not** prove the `.emp` ensures run. Only the sweep above does, and only at the
revision it was run at.

### How much of the colour space the checks accept (invariant 8(d))

Stated because a colour check that quietly accepts a wide swathe of the space is the failure
this lane hit last week. These guards are not colour-membership tests — they are relations
between a day entry and its night image, so the question is what fraction of candidate
TRANSFORMS they admit, not what fraction of colours:

* **`black_set`, `dead_channels`, `brighter`** are exact and their acceptance is derived, not
  estimated. For a day channel of value `v`, the admitted images are exactly `1..v` — `v` of
  the 8 possible values, so **1 of 8** at `v = 1` and **7 of 8** at `v = 7`. Over this
  palette's 42 lit entries and their **107** lit channels (histogram 1:16 2:17 3:16 4:21 5:11
  6:7 7:19), the mean admitted fraction is **48.1%** of per-channel outcomes. Taken as whole
  colours, the admitted image of an average lit entry is **11.5% of the 512-colour cube**.
  That is a real constraint and it is not a tight one on its own — which is why the retention
  band and the distinct-colour budget sit beside it and not instead of it.
* **`ret_min >= 50` with `ret_max_lit == 76`** is the narrow one: it admits a band 26 points
  wide out of the 0-100 the subtraction occupied, i.e. **26%** of the retention range, and the
  `== 76` form admits exactly one value of the ceiling.
* **`lit_entries == 42`, `embed_len == 96`, `distinct == 39/36`, the three blue rows** are
  single-value pins: one accepted value each.
* Weakest row, named so it is not mistaken for a strong one: **`blue_permille` cannot
  distinguish WHICH entries carry the blue.** A grade that put all its blue into one entry and
  none into the rest would read the same 406. Nothing here covers that; the contact sheet does,
  by eye.

---

### The landing evidence

`./tools/landing_build.sh` — the ruled pre-merge check — **exit 0, `finished=0`**, 2026-09-16,
`head=b49d1e973608`, land-gate stamp `key=544d20cb4c2d2717`. (Wall clock: launched 06:23:56,
`uptime` load average 2.97 at launch.)

| lane | result |
|---|---|
| shapes built (`LANDING_SHAPES`) | `s4` crc `bc7d8b85` len 820606 · `s4.debug` crc `a70d90f6` len 846986 · `demo.debug` crc `915cfd0f` len 103742 |
| pre-build `pytest tools -m "not needs_build"` | **2840 passed, 2 skipped**, 25 deselected, 143 subtests passed, 86.19 s |
| `emp_expect_fail` | **56/56** cases (54 comptime + 2 link) |
| post-build `needs_build_lane` | **24 ran, 0 deferred, 0 failed, 1 EXEMPTED** (`test_deb2_appendix[demo.bin]`, a shape this caller does not build) |

Both new `needs_build` rows RAN rather than deferred:
`test_night_palette_grade.TestRomCarriesTheGrade::test_rom_words_are_the_derived_grade` and
`...::test_rom_words_are_not_the_day_palette`.

**One shape is not in that list and it is the script's own declared choice, not an omission**:
`demo` plain. The hub's 2026-09-14 CTRL-3 pick A drops it from the pre-merge check because every
Sonic 4 build assembles it for placement; `./build.sh demo` and the nightly still build it. Said
here because the parcel brief asked for four shapes and this check runs three by design.

**The effects-gate ritual does not bind this parcel** (`tools/effects_gates.py` is required for
`engine/effects/*`, `engine/level/bg_anim.emp`, `engine/system/buffers.emp`; the change is in
`games/sonic4/data/effects/` and moves 48 data words, no engine code). It also boots a headless
emulator, which this lane may not do. If the controller wants it belt-and-braces it is a
foreground run.

---

## 4. WHAT I CONSIDERED AND DID NOT SHIP

Options rendered, measured, and committed as `docs/captures/2026-09-16-night-grade-options/`
(synthesized, not captured — the README there says so in its first line and says why the
synthesis is exact).

* **`4/8` — blue untouched** is the real alternative: bluer (471 permille vs 406), loses one
  art edge instead of three, identical darkness and dirt hue. Its cost is that leaving blue at
  full scale lets a pure-blue entry keep 100% of its luminance, so the **76% ceiling becomes
  no ceiling**, and that ceiling is what makes "nothing stays at daylight" enforceable rather
  than hoped for. One word switches it.
* **a blue FLOOR on the shadows** (`4/6` + `max(b, 1)`) reads most like moonlight of anything
  I rendered, and the shipped guard set refuses it on purpose: its retention reaches **136%**,
  i.e. some colours are brighter at night than by day. That may well be the right look — film
  night grades do exactly this — but it is a different design and it needs the owner's word,
  not a quiet relaxation of the "nothing brightens" pin.
* **a lerp toward a dark-blue tint** — the textbook night grade. Scanned across tint and
  amount; every position that is genuinely blue either brightens the near-blacks or pushes the
  dirt back into magenta, for the reason below.
* **going darker** (`NIGHT_LIGHT_8 = 3` or less) turns the dirt to dusty rose at hue 0 deg and
  collapses eight more art edges.

**The structural finding under all of those: on this palette, a strong blue cast and "nothing
gets brighter" are incompatible.** The dirt's day colour is `(5,3,1)` — blue is already its
smallest channel — so any lean strong enough to be obvious either lifts blue above green
(magenta, the original bug) or adds blue as an offset (brightening). `4/6` is the corner of
that trade-off where the hue stays brown and nothing brightens.

---

## 5. THE `06-night-landed.png` QUESTION, ANSWERED OFFLINE — AND IT WAS ALREADY ANSWERED

The hub asked whether that frame's canopy is a different scene or a mid-load capture, i.e.
"a streaming defect in a capture's clothes".

**It is a different scene, it is correct behaviour, and it is not a streaming defect.** Two
independent lines:

1. **Already banked in this repo.** `docs/captures/2026-09-15-regions-p2-e2/README.md` carries
   a 2026-09-16 correction raised by the hub's own reader and measured on the running ROM:
   landing drops the camera to y 3034, the night region is y 0..2047 by construction, so the
   resolved region becomes section 5's row (x 4096..6143, y 2048..4095) binding a different
   preset. The caption was wrong; the behaviour was not. (The brief's claim that this frame
   lives in the 09-13 set is also off — it is in the E2 set.)
2. **My own offline check, which did not use that README.** `06-night-landed.png` decodes
   **98.0% to the DAY palette** and only 67.1% to the night one, and all 67.1% is the two
   palettes' shared colours. It is not a night-region frame at all. A mid-load capture would
   show the NIGHT palette over stale art; this shows a different palette entirely.

For the same reason, `07-walking-back-across.png` (95.3% day) is not night evidence either.
**No emulator was used for this answer and none is needed.** Nothing to route onward.

---

## 6. WHAT IS STILL OPEN

* **The look itself is not settled by anything here.** Every figure in this note is a still or
  a derivation; whether 4/6 reads as "the forest after dark" at 60 Hz is the owner's call on a
  running ROM. My own read of the contact sheet: it reads more *overcast dusk* than *moonlit*,
  and `4/8` or the shadow-lift variant would read more like night at the costs named in §4.
* **The fade's midway frames are not re-judged.** They were the ugliest pictures in the E2 run
  under the subtraction; under a grade that preserves ratios they should be strictly better,
  because every intermediate now lies on a line between two colours of the same hue. Not
  measured — it needs the running fade.
* **`PALETTE-LINE0` is untouched and still separate.** Sonic keeps his day colours in the night
  region. The mechanism note refuted the idea that the act's stragglers were line 0 (0.0% of
  `t5-f272` is line 0), and this parcel changes nothing about the character line.
* **The knob positions have not been built.** Only `4/6` is in a ROM. Any other position needs
  its pins re-derived, which is deliberate.
