# Effects P3 Parcel P-b — Gate Evidence

**The runtime patcher: N world-anchored raster boundaries, moved every VBlank.**

Build under test: `s4.debug.bin` crc `2318eef6`, aeon branch `parcel/effects-p3-p-b`.
Emulator: oracle, one instance, foreground. Measured 2026-08-15.

---

## 0. The claim, stated so it can fail

> Each patchable boundary lands on **its predicted absolute screen row**, derived as
> `world_y - Camera_Y` and clamped into the record's authored band; two channels in one
> program are placed **independently**; and when the camera moves, every boundary moves by
> **exactly the camera delta**.

The last clause is the one that matters and the one that is easy to get wrong. It is
deliberately **not** phrased as "the separation between the two channels changes" — two
world-anchored channels hold a **constant** separation, so that predicate would pass a broken
single-anchor implementation and fail a correct one. The falsifiable form is the opposite:
**channel 1's arm word must be *invariant* under camera motion**, because its gap is measured
from channel 0 and both move together. A screen-anchored channel would be forced to change it.

---

## 1. The instrument, and why it is not CRAM

`emulator_read_cram` cannot see a mid-scanline CRAM write during active display: it returns
the re-asserted base palette and reads as "the effect did nothing". Two instruments are used
instead, and they are independent of each other:

**(a) The arm words in `Raster_Buf_B`.** The patcher's whole output is one byte per record.
Reading `Raster_Buf_B[0..7]` gives channel 0's and channel 1's arm words directly, and the
predicted value is computable by hand from `Camera_Y`, the anchor and the band. This measures
the arithmetic exactly, with no pixel involved.

**(b) A framebuffer row diff between two anchor settings.** Capture the same scene twice with
one channel's anchor at two different values; every row between the two resulting boundaries
differs and every row outside them is identical. This measures where the fire *actually lands*
on the display, which (a) cannot.

**Drift control.** Two captures at the *same* anchor, 9 frames apart, differ in rows 8-23 (the
ring HUD) and rows 69-119 (the OJZ background animation, peak 209/320 px). That is not noise to
wave away — an early hi-clamp measurement was contaminated by exactly this and had to be redone.
**Every framebuffer result below uses adjacent captures 3 frames apart**, where the same control
measures ≤24/320 px of residue, and each result is stated together with the rows that are
*identically zero*, which drift cannot fake.

---

## 2. Predicted vs measured — arm words

Fire lines are screen minus 1 (Ruling 1a). Priming record 1 sits at fire line 1, so
`gap_0 = fire_0 - 1 - 1` and `gap_k = fire_k - fire_{k-1} - 1`. The arm word is `$8A00 | gap`.

Bands: channel 0 screen 40..120, channel 1 screen 130..200.

| # | `Camera_Y` | anchors (ch0, ch1) | ch0 screen | ch1 screen | predicted | **measured** |
|---|---|---|---|---|---|---|
| 1 | 144 | 224, 314 | 80 | 170 | `$8A4D` `$8A59` | **`$8A4D` `$8A59`** |
| 2 | 144 | 204, 314 | 60 | 170 | `$8A39` `$8A6D` | **`$8A39` `$8A6D`** |
| 3 | 96  | 140, 314 | 44 | 218 → **clamp hi 200** | `$8A29` `$8A9B` | **`$8A29` `$8A9B`** |
| 4 | 80  | 224, 314 | 144 → **clamp hi 120** | 234 → **clamp hi 200** | `$8A75` `$8A4F` | **`$8A75` `$8A4F`** |
| 5 | 80  | 100, 314 | 20 → **clamp lo 40** | 234 → **clamp hi 200** | `$8A25` `$8A9F` | **`$8A25` `$8A9F`** |
| 6 | 80  | 185, 275 | 105 | 195 | `$8A66` `$8A59` | **`$8A66` `$8A59`** |
| 7 | 112 | 185, 275 | 73 | 163 | `$8A46` `$8A59` | **`$8A46` `$8A59`** |

Seven for seven, including **both clamp directions** and a case where one channel is free while
the other clamps (#3).

Row 2 is also the **chain-relink** case: moving channel 0 alone changed *channel 1's* arm word
(`$8A59` → `$8A6D`), because every gap is relative to the previous record. That is precisely why
a single-word patcher cannot be generalised by writing more single words, and why the routine
walks the whole table.

### The world-anchor claim (rows 6 and 7)

Camera 80 → 112 is a delta of **+32**.

- Channel 0's screen row went 105 → 73: **exactly −32**.
- Channel 1's arm word was **`$8A59` at both cameras — bit-identical**.

Channel 1's separation from channel 0 is 90 screen rows at both positions, which is exactly
`275 − 185`. **This is the negative control for screen-anchoring**, and it needs no code change
to run: had channel 1 been anchored to a fixed screen row, its gap would have had to absorb the
whole 32-line camera delta, giving `$8A79` or `$8A39`. It did not move by one bit.

---

## 3. Predicted vs measured — absolute framebuffer rows

Each row below is a diff of two adjacent captures. "Band" is the set of rows where exactly one
of the two has the effect, so **the band's edges are the two boundaries**.

| test | `Camera_Y` | A: anchor → row | B: anchor → row | predicted band | **measured** |
|---|---|---|---|---|---|
| in-band placement | 144 | 204 → **60** | 244 → **100** | 60..99 | **59\*..99**, zero at 100+ |
| **hi clamp** | 80 (held) | 224 → clamp **120** | 140 → **60** | 60..119 | **59\*..119**, zero at 120..223 **and** at 24..58 |
| **lo clamp** | 80 (held) | 100 → clamp **40** | 140 → **60** | 40..59 | **39\*..59**, zero at 60+ |

\* The leading row is a **partial** row, and it is the documented mid-line CRAM landing, not an
off-by-one. On the in-band test, row 59 differs only from x ≥ 127 and row 99 only up to x ≤ 255:
the fire for screen line M runs during line M−1 and its CRAM writes land part-way across that
line, so line M−1 carries a fragment and line M is the first fully-affected row. This matches the
P2 density evidence, which measured the same artifact at x = 232/248/294 of 320.

The clamp rows are the load-bearing numbers. At `Camera_Y` = 80 an anchor of 224 derives screen
row **144**, well outside the band — and the boundary is measured at **120**, the band's `hi`
edge, with **zero differing pixels at rows 120..223**. An anchor of 100 derives screen row **20**
and is measured at **40**, the band's `lo` edge. Neither is where the unclamped arithmetic points.

**A stable camera needed an instrument of its own.** OJZ's spawn area is flat and `Camera_Y` is
spring-loaded back to 144 at `CAM_MAX_Y_STEP` = 16 px/frame, so writing `Camera_Y` and stepping
gives a *moving* camera, not a held one — an early attempt read arms for a camera 16 px away from
the one written and looked like a defect until the lerp was accounted for. The camera is instead
held by lowering `Camera_Y_Max`, so the engine's **own** clamp pins it: no per-frame poking, and
the value is stable across the 3-frame gap between captures.

---

## 4. Negative controls

**(a) Overlapping bands must fail the BUILD.** Widening channel 0's band to `hi: 135` against
channel 1's `lo: 130` fails with guard 2 (`check_intervals`):

> raster program: … Records must occupy STRICTLY ASCENDING, DISJOINT fire-line intervals …
> two records on one fire line make the gap −1, whose byte is $FF — the PARK word.

**(b) Disjoint but too close still fails, on a different guard.** `hi: 129` leaves the bands
disjoint (guard 2 passes) and is caught instead by guard 8 (`check_density`):

> the fire at screen line 100 models at 526 cycles but only 1 scanline(s) = 488 cycles remain …

This is the worst-case band-edge measurement P-a shipped, doing exactly what it was built for.

**(c) The adjacent legal case.** The unchanged fixture (`hi: 120`) builds green, with a margin of
10 fire lines. It is worth recording that `hi: 128` — the widest band the density model would
accept — *also* fails, but on neither semantic guard: it trips the hand twin,
`OJZ_TwoChannel: the emitted patched image diverges from the hand twin at index 68`. Index 68 is
the table's `band_hi_fl` word. The fixture's patch table is pinned word-for-word, so a band edit
cannot go unnoticed.

**(d) Teardown, verified live rather than by inspection.** Walking right out of section 0 into
section 1 (whose preset binds a *static* raster program) left
`Raster_Patch_Tab = 0` and `Raster_Active_Buf = $FFFF89A2` (= `Raster_Buf_A`). The
`.copy_program` clear fires. This was found by accident — a 200-frame camera experiment crossed
a section boundary and the arms stopped tracking — which is a better test than a deliberate one.

---

## 5. What is NOT proved

- **`Effects_SetWorldY` is exercised, but only from test scaffolding** — see §6. What is *not*
  proved is that any real content wants the surface; that is Parcel D's question.
- **Channels 2 and 3 are never non-zero.** `RASTER_MAX_PATCH` is 4; the fixture uses 2. The seed
  loop copies all four, but only two are ever walked by a table.
- **Only one program shape is measured.** `OJZ_TwoChannel` is `[patchable, patchable]`. A table
  mixing static and patchable records exercises the `.static` branch, which no runtime test here
  reaches — it is covered only by the build-time table pin.
- **The below-viewport delta is real and is not a defect.** A boundary whose derived row falls
  below its band now renders at the band's `hi` edge instead of vanishing. The deleted
  `Raster_PatchWaterLine` had two *semantic* off-screen branches (above viewport → fire as early
  as possible, "fully submerged"; below viewport → park, "not visible"). `Raster_PatchAll` clamps
  in both directions instead. This is a **declared delta**, stated in the plan before it was
  measured, and section 4's clamp rows are what it looks like: at `Camera_Y` = 80 the water line
  sits at row 120 rather than off-screen at 144.
- **No S/H transparency is demonstrated.** OJZ's plane art is high-priority, so the `$8C89`
  Shadow/Highlight write below the boundary has nothing to dim. The op provably *executes* (it
  precedes the region op in the same fire, and a mis-parse would desync the CRAM command into
  garbage), but proving S/H needs low-priority water content. Pre-existing, carried from P2.
- **Frame cost is not measured.** `Raster_PatchAll` walks the table every VBlank; nothing here
  bounds what that costs. The budget model is Parcel B's subject.

---

## 6. `Effects_SetWorldY` — the main-loop-write → VBlank-conversion seam

Sections 2-4 were measured before this call site existed, by writing `Effects_World_Y` RAM
directly from the emulator — which does not execute `Effects_SetWorldY` at all. The proc had
**no call site anywhere in the tree**, and the gate was silent about it.

**Decided by Fable adviser, 2026-08-15: add the call site, DEBUG-gated and controller-driven,
and extend the gate — not weakly.** The ruling also corrected the reasoning, and the correction
is what changed the assertions:

> "You're treating it as one failure class when it's two. `fx_tint_band` was a **comptime DSL
> helper** — its body is only elaborated at a call site, so with zero call sites it was never
> even compiled in the meaningful sense. `Effects_SetWorldY` is a **`pub proc`** — its four
> instructions are assembled, encoded and byte-pinned in every build regardless of callers. The
> 'shipped broken, nobody could know' form of the lesson does not apply here.
>
> What *does* apply is the lesson's second form: **rot and contract drift**. What you cannot read
> off the listing is the contract — that `d1` is WORLD-space not camera-relative, that a
> main-loop-time write is legal and gets picked up by the next VBlank's `Raster_PatchAll` (this
> is the entire load-bearing claim of the P-b redesign), and that the proc and the preset seed
> loop agree on `Effects_World_Y`'s element size and base."

It ruled against deleting the setter on three grounds: the plan's ruling 4 names it explicitly,
so removing it re-litigates a settled term rather than sitting adjacent to it; deferring to
Parcel D does not remove the verification obligation, it re-creates it with the fixture cold and
a content deadline attached; and seeded-only anchors leave nothing to *use* — the parcel's own
comment names the alternative as "poking RAM at an index the author has to guess".

**The call site** (`games/sonic4/test/ojz_scroll_test.emp`, `GameState_OJZScroll_Update`):
C+UP / C+DOWN nudge channel 0's world anchor by ∓1 per held frame. **Input-gated, not a frame
counter** — a free-running counter would perturb every frame of every build of this scene,
moving the visual baseline and risking a replay-fixture desync for no benefit, whereas a replay
that never presses the chord is bit-identical. C is unclaimed (A is the character-cycle hotkey,
B the debug toggle).

**Measured**, `s4.debug.bin` crc `df9d0015`:

| step | expected | **measured** |
|---|---|---|
| seed on section entry | `Effects_World_Y` = 224, 314 | **224, 314** |
| hold C+DOWN, 20 frames | ch0 224 → **244**, ch1 unchanged | **244**, ch1 **314** |
| hold C+UP, 10 frames | ch0 244 → **234**, ch1 unchanged | **234**, ch1 **314** |
| arms after the nudge, `Camera_Y` = 432 | ch0 244−432 = −188 → clamp lo 40 → `$8A25`; ch1 → clamp lo 130 → `$8A59` | **`$8A25` `$8A59`** |

Both directions, exact per-frame step, channel 1 untouched (so the `RASTER_MAX_PATCH-1` index
mask works), and the resulting arm words predicted exactly. **The last row is the seam the rest
of this document never crossed**: an anchor written from the MAIN LOOP, converted to arm bytes by
`Raster_PatchAll` at the next VBlank. That write is safe from the main loop for the precise
reason a *patch* is not — it lands in RAM, and every arm byte is still derived in one pass
inside VBlank, so the relative-gap chain is never observed half-updated.

**Residue, stated rather than implied:** this is a *test-scaffold* call site. It proves the
surface works; it does not prove content wants it.

---

## 7. Instrument note for whoever measures raster next

`ojz_scroll_test.emp` already has **`Debug_Scene_Freeze`**, a DEBUG-shape flag that skips
`Camera_Update` so a `write_memory` to `Camera_X/Y` stays put. That is the right tool for a
pinned-camera raster capture and it was found only *after* §3 had been measured the hard way
(lowering `Camera_Y_Max` to make the engine's own clamp hold the camera). Both work; the freeze
is one write instead of two and does not perturb the act's clamp. Use it.
