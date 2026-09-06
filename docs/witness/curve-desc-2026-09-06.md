# CURVE-DESC — reproduced, and the variable the record named is not the one that moves

**Date** 2026-09-06 · **Branch** `parcel/curve-desc` · **Instrument**
`tools/curve_desc_probe.py` (added by this parcel), oracle-aether headless via
`tools/aether_instance.assert_rust_server`.
**Raw data** `docs/witness/curve-desc-2026-09-06.json` (all four arms, 224 BG words each).
**Pictures** `docs/witness/curve-desc-{flat,descsmall,desc,asc}-2026-09-06.png`.

---

## 1. The record, and what it does not contain

The queue row (`docs/lane-status.json`, id `CURVE-DESC`) reads:

> ENGINE DEFECT: descending parallax curve garbles the BG; mechanism unestablished

Its entire origin is the body of **`df3b8810`** ("scene(sec7): the curve-free scene —
descending curves were the garbage"), whose eight-arm bisect at player (3000, 4400) and
frame 540 ended:

> no scene -> correct; original fa -> garbage; fa corrected -> garbage; world_y 3->40 ->
> mostly, residual band; + v_offset 288 -> garbage plus magenta; vsplit removed ->
> byte-identical ROM; CURVES REMOVED -> CORRECT; upward curve -> CORRECT.
> So a DESCENDING parallax curve garbles the background and an ascending one does not.

`05b8ad10` is the follow-up look. `docs/DEFERRED_WORK.md` has **no** entry, `docs/witness/`
had **no** artifact, and `docs/OVERSEER-LOG.md` in this repo does not mention it — the
empyrean hub log does (`OVERSEER-LOG.md` 2026-09-05T14:43 and 14:51). Aurora reached the
same conclusion about the record independently and wrote it down
(`aurora/docs/reviews/2026-09-05-rowremap-author.md` §9.3): *"The record for that defect
lives only in commit prose and the hub log … There is no witness doc, no DEFERRED_WORK
entry and no queue row, **and no record of which ascending pair the bisect used as its
control**."* That last clause is the load-bearing gap, and §4 below is why.

Aurora also shipped a `curveDescendingAdvisory` in the editor on the strength of the
correlation, deliberately as advice and not prevention, and asked (§9.2) for the sentence
to be **re-pointed** rather than deleted if the cause turned out to be direction-independent
or bounded. It is both. See §6.

---

## 2. Method

`tools/curve_desc_probe.py`, one ROM per arm, each arm ONE authored variable apart in
`games/sonic4/data/editor/effects/ojz_act1_sec7_worldwater.json` (canonical
`DEBUG=1 ./build.sh` after `tools/regenerate-level.sh`; no `FAST=1` anywhere).

* Boot 180 frames, warp through the DEBUG mailbox to df3b8810's own coordinates
  (`Warp_Req_X` 3000, `Warp_Req_Y` 4400, flag last), poll the ack, settle 30.
  **All four arms: ack in 18 frames, `Camera_X` 2840, `Camera_Y` 4288,
  `Parallax_Current_Vscroll_BG` 288.** A bare camera poke is not used — it faults
  EntityWindow's single-axis slide invariant.
* **Value domain:** `Hscroll_Buffer` read out of RAM, 224 lines x 4 bytes, compared line by
  line against an expectation DERIVED from the scene's own authored factors plus the live
  `Camera_X` (`curve_probe.derive_curve_buffer`). Nothing is read back off the band records
  the walker wrote — that would be checking the walker against itself. A single read is
  valid here because the buffer is DMA'd whole in VBlank and the raster interpreter touches
  only CRAM and VSRAM.
* **Pixel domain:** real raster scanlines, `source == "raster"` asserted on every call, all
  224 rows, written to PNG. A post-hoc render cannot witness a per-line effect and fails by
  showing a clean picture.

---

## 3. The four arms

| arm | live band's `fb` -> `curve: To(..)` | direction | measured BG excursion down the screen | picture |
|---|---|---|---|---|
| `flat` | `FACTOR_1_2`, no curve (master today) | — | **0 px** (one run of -1420 over 224 lines) | **CLEAN** |
| `descsmall` | `FACTOR_1_2` -> `FACTOR_7_16` | descending | **176 px** (-1420 .. -1244) | **CLEAN** |
| `desc` | `FACTOR_1_2` -> `FACTOR_1_8` (df3b8810's own) | descending | **1060 px** (-1420 .. -360) | **GARBLED** |
| `asc` | `FACTOR_1_8` -> `FACTOR_1_2` (the mirror) | ascending | **1061 px** (-1416 .. -355) | **GARBLED** |

`asc` is the deliberate mirror of `desc`: `fb` and the far end swapped, so the span (224
lines) and `|spread|` are the same to within one pixel of Bresenham rounding and **only the
direction reverses**.

### 3.1 The walker's arithmetic is exact, in both directions

**Derived-vs-measured: 0 of 224 lines differ, max |delta| 0 — on ALL FOUR ARMS**, plane B
and plane A alike. The curve hoist's `divs.w` + negative-remainder floor normalisation and
the fill's per-line Bresenham accumulate emit exactly the authored ramp from the layer's
base to its far end across the layer's span. Spot-checked by hand against
`base + 4n + floor(169n/224)` on the `desc` arm at n = 0/39/100/161/162/223: -1420, -1235,
-945, -655, -650, -360, every one matching.

**There is no value defect, and no sign defect.** df3b8810 already suspected as much
("the positive-spread path already takes correct floor division, so the correlation
survives and its cause does not"); this measures it on both signs rather than reasoning
about one.

---

## 4. The direction claim is refuted, from both sides

Named before the runs, so a predicted result could not be read as a refutation:

* the direction hypothesis is falsified by **an ascending arm of the same |spread| and
  span that garbles**, or by **a descending arm that is clean**;
* the excursion hypothesis is falsified by **a clean arm whose excursion is well over
  192 px**, or **a garbled arm well under it**.

`asc` garbles. `descsmall` is clean. **"A descending parallax curve garbles the background
and an ascending one does not" is refuted as stated.** The correlation df3b8810 recorded is
real — its two curve arms both garbled and removing them fixed it — but the variable it
named is not the one that moves. Its "upward curve -> CORRECT" arm is the one whose
parameters were never written down; a small-`|Δf|` upward curve would have been clean for
the reason below, and nothing distinguishes that from the direction reading any more.

---

## 5. What does move: the per-band excursion against the plane's wrap margin

Plane B is a **64 x 64** nametable (VDP reg `$10` = `$11`, `engine/system/boot_data.emp`
:186) — 512 px wide, wrapping. The screen is 320 px. So a band may shear its Plane-B
HScroll by at most

```
PLANE_W - SCREEN_W = 512 - 320 = 192 px
```

before the wrap seam enters the visible window and rows of the same band start showing
plane columns 512 px apart — the art repeats and smears down the screen, which is the
"streaky green/black noise" the owner reported.

The excursion is **camera-proportional**: `E = camX * |f_from - f_to|`, so the onset is at
`camX = 192 / |Δf|`. The measured arms straddle it by a factor of six (176 clean, 1060/1061
garbled), and this is **not a new law** — the perspective-floor lane derived and measured
it independently for its own curve (`tools/perspective_floor_predict.py`:60-63,
`tools/perspective_floor_gen.py`:70-95, with a measured onset table 195 / 389 / 778 / 1557
for `To(FACTOR_1 / 1_2 / 1_4 / 1_8)` against a predicted `192/F` of 192 / 384 / 768 / 1536).
**That lane's curve is ASCENDING** (`fb: FACTOR_0` -> `To(FACTOR_1_8)`) and garbles past its
own onset, which is a second, independent reason the sign cannot be the variable.

**NOT ESTABLISHED HERE: the exact onset in this scene.** Two points either side of a
threshold derived from `PLANE_W - SCREEN_W` is not a bisect. The floor lane's table shows
the transition is gradual (8-20% baseline noise at onset), so "176 clean, 1060 garbled" is
consistent with 192 and does not measure it. A bisect over `|Δf|` at fixed `camX` would.

---

## 6. A second finding, unrelated to curves, that the record did not have

**At these coordinates this scene renders as ONE band covering the whole screen, not three.**

`scene_plane_line()` is the **identity** on a vertically locked plane — it returns the
authored `world_y` and does **not** add `v_offset` (`engine/level/scene_dsl.emp`:3313-3332;
`scene_vsplit_line`'s banner states the consequence, `screen = plane_line - v_offset`, and
notes that every other locked scene in the tree has `v_offset: 0`, which is why "the
authored top IS the screen line" reads as a law). The sec7 scene is the first locked scene
with a non-zero `v_offset`. Its authored tops 0 / 40 / 162 are therefore **plane** lines
while `Vscroll_BG` is pinned at 288, so Step 4a's rotation (`.find_k`) picks
**k = 2** — the last band whose plane top <= 288 — forces it to screen line 0, and the other
two rotate to `top - 288 + 512` >= 224 where the clamp zeroes their length.

Measured, not inferred:

* `flat`: **one** run, -1420 (= `FACTOR_1_2`, the third layer's `fb`) across all 224 lines.
  The first layer's `FACTOR_1_8` (-355) appears nowhere.
* `desc`: **one** Bresenham ramp across all 224 lines with **no discontinuity at line 40 or
  162** — the two boundaries the JSON declares.
* `Parallax_Current_Vscroll_BG` reads 288, matching the modelled rotation.

This is the engine doing exactly what the data says (bands are plane-anchored; plane rows
288..511 all belong to the last band), so it is not an engine defect. It does mean the
scene's three authored layers have no effect at this camera position, which is almost
certainly not what the author intended, and it is why the curve's span is the full 224
lines rather than 62 — i.e. it is upstream of the excursion above.

The probe's first expectation model assumed `top == world_y` and was wrong on every line of
the `flat` arm; its own layer-boundary self-control is what caught it, and the model now
carries the rotation.

---

## 7. Left open

1. **The onset is not bisected** (§5). Two points either side of a derived threshold.
2. **`ojz_act1_depth` — a SHIPPED scene — carries `fb: FACTOR_1_2, curve: To(FACTOR_1)` at
   `world_y: 160`.** `|Δf|` = 1/2 gives a **derived** onset at `camX` 384. **NOT MEASURED**
   — this is arithmetic on the authored factors, not a run, and the band's span and the
   camera range reachable in section (1,1) are both unchecked. If it holds, the d-15
   showcase scene garbles past camera x 384, and its curve is ascending. Worth a drive.
   The other two shipped curves are far out: `ojz_act1_depth` `world_y: 112`
   (`FACTOR_1_4` -> `FACTOR_3_8`, `|Δf|` = 1/8, onset 1536) and `ojz_act1_floor`
   `world_y: 440` (`FACTOR_0` -> `FACTOR_1_32`, `|Δf|` = 1/32, onset 6144).
3. **The one-band collapse in §6 is not ruled.** Whether sec7 should author its tops at
   288/328/450 (to sit inside the visible plane window), or drop `v_offset`, is a content
   call for the scene's author and the owner. Nothing here refuses it, and no guard in
   `layer()` or `scene()` relates an authored top to the visible window `[v_offset,
   v_offset + 224)`.
4. **df3b8810's other seven arms were not re-run.** All four arms here sit on the CURRENT
   scene geometry (`fa: FACTOR_1`, tops 0/40/162, `v_offset: 288`); the original `fa`,
   `world_y: 3` and no-`v_offset` arms are untouched, and this parcel says nothing about
   them. The `fa != FACTOR_1` finding of `7ee97fe1` is a separate, real defect and remains
   where it was — note that `7ee97fe1` itself is **not an ancestor of master** and the
   `tools/fg_hscroll_witness.py` it added never landed.
5. **Aurora's `curveDescendingAdvisory` needs re-pointing, not deleting** — their own §9.2
   asks for exactly that if the cause turned out bounded or direction-independent. The
   sentence that fits the measurement is about `camX * |Δf|` against 192 px, and it applies
   to both directions.
