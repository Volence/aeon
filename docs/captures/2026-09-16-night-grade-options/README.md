# ⚠ THESE ARE NOT CAPTURES. They are DERIVED images, and the derivation is exact.

Every panel in `options.png` except the first is one certified DAY capture —
`docs/captures/2026-09-16-night-settled-v2/in-k-001-t00202-cx3392-r01-pf00-settled.png` —
with each pixel's colour put through a candidate day-to-night palette map. No emulator ran.

**Why that is legitimate here, and where it stops being legitimate.** The frame decodes
**100.0%** to `OJZ_Palette`, with nothing left over (all four certified day frames do, and
all three certified night frames decode 100.0% to the night palette). And the day-to-night
map is well defined on COLOURS, not merely on indices: every group of day entries sharing a
colour maps to one night colour under every candidate here, so no pixel is ambiguous. The
result is therefore the exact image the VDP would draw from that scene with that palette
installed.

**What it holds fixed is the point.** The camera moves 112 px between the last certified day
frame and the first certified night one, so a day frame and a night frame do not show the
same scenery and any colour difference between them is part palette and part art. Recolouring
ONE frame holds the art at zero and varies only the palette.

**What it cannot show:** the fade between the two palettes (a motion percept — see the v2
set's README), anything about streaming, and anything about how this reads at 60 Hz on a CRT.
The look is judged on the running ROM; this sheet exists so the knob can be chosen before
somebody spends a build on each position.

## The panels

`options.png`, reading left to right, top to bottom.

| option | new blacks | retention | distinct | canopy+trunk V | dirt hue/sat | blue permille |
|---|---|---|---|---|---|---|
| DAY (certified capture, unaltered) | 0 | 100% | 39/39 | 28.8 | 27 deg / 0.76 | 337 |
| **WAS**: subtraction r-3 g-2 b-0 | **4** | **0-100%** | 33/39 | 12.9 | **336 deg** / 0.55 | 547 |
| **SHIPPED**: grade 4/6 | 0 | 50-100% | 36/39 | 17.3 | 21 deg / 0.57 | 406 |
| darker: 3/6 | 0 | 34-100% | 31/39 | 15.8 | 0 deg / 0.43 | 469 |
| lighter: 5/7 | 0 | 50-100% | 35/39 | 18.2 | 19 deg / 0.62 | 415 |
| bluer: 4/8 (blue untouched) | 0 | 50-100% | **38/39** | 17.3 | 21 deg / 0.56 | **471** |
| shadow-lift: 4/6 + blue floor 1 | 0 | 52-**136%** | 33/39 | 17.3 | 21 deg / 0.57 | 420 |
| no lean (control): 4/4 | 0 | 50-100% | 35/39 | 17.3 | 24 deg / 0.61 | 341 |

Retention is luminance kept, over every lit entry; `distinct` is how many of the day
palette's 39 distinct colours survive as distinct colours (a collapse is an art edge that
stops being an edge); canopy+trunk V is the mean of max(R,G,B) over screen rows 0..111;
dirt hue/sat is the area-weighted HSV of the five-entry dirt ramp; blue permille is blue's
share of the palette's total channel sum.

**Read the rows against the control, not against DAY.** The bottom-right panel is the same
grade with blue scaled exactly like red and green — no lean at all — and its blue share is
**341**, not 337. Rounding half up and the non-zero floor act hardest on the smallest channel
value, and in this art blue is usually the smallest, so about 4 permille of every "blue lean"
below is arithmetic rather than design. The shipped grade's lean is 406 against 341.

## What each row is there to say

* **`WAS`** is the whole complaint in one picture: the dirt at hue 336 deg (magenta, the
  wine-red) with its saturation almost intact, and a canopy where four colours have become
  literal `$0000`. Its retention range of 0% to 100% is why it reads as a different zone
  rather than as the forest at night — the transform kept a different fraction of each
  colour depending on the colour's hue.
* **`darker: 3/6`** is why the knob does not simply go down. At `NIGHT_LIGHT_8 = 3` the dirt
  lands at hue 0 deg and saturation 0.43 — a dusty rose — and eight more art edges collapse.
  A 3-bit palette runs out of room before it runs out of darkness.
* **`bluer: 4/8`** is the real alternative and its one cost is worth stating: it is bluer
  (471 vs 406) and it loses only ONE art edge instead of three, but leaving blue untouched
  means a pure-blue entry keeps 100% of its luminance, so the shipped retention ceiling of
  76% over darkenable colours becomes no ceiling at all. That ceiling is what makes "nothing
  stays at full daylight" an enforceable property rather than a hope, which is why 4/6 ships.
  `$0800` draws zero pixels in every frame of the v2 set today, so the difference is a
  property question, not a picture question.
* **`shadow-lift`** is the variant that makes the picture read most like moonlight, by giving
  every non-black colour a blue floor. It is refused by the shipped guard set on purpose:
  its retention goes to **136%**, i.e. some colours are BRIGHTER at night than by day. That
  may be the right look — film night grades do exactly this — but it is a different design
  and it needs the owner's word, not a quiet relaxation of the "nothing brightens" pin.

## Turning the knob

`NIGHT_LIGHT_8` and `NIGHT_BLUE_8` in `games/sonic4/data/effects/ojz_effects.emp`. Moving
either one will make several of the fourteen pins beside them go red with the measured
figure in the message — that is intended. **Re-derive the pins from the new scale; do not
re-type them from what the build reports**, or the pins become a transcript of whatever the
last edit did.
