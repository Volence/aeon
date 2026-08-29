# Triage: the six deform scenes, the left-edge strip, and Rocking Slow's stillness

**2026-08-28, branch `diag/left-edge-deform-scenes`. DIAGNOSIS ONLY — no engine behaviour changed,
no scene data changed.** This lane has no emulator; every claim below is derived from source or
quoted from a prior measured run, and each is labelled which.

## The report

The owner played all twenty entries of the DEBUG scene cycle and reported, transcribed:

> "Rocking Slow does nothing but draw the fg incorrectly on the left. 12 rocking works but it also
> messes up the fg, same with rocking fast. Same with perspective subtle, perspective, perspective
> dramatic."

Six scenes. Against `~/.config/oracle/player.conf`'s `symbol_watch` roster that is indices
**10, 11, 12, 13, 14, 15** — `Rocking_Slow`, `Rocking`, `Rocking_Fast`, `Perspective_Subtle`,
`Perspective`, `Perspective_Dramatic`. Those are exactly, and only, the six scenes that raise
`CAP_PER_COL_VSRAM`.

## Verdict in one line

**Two separate defects, and the strip is neither a plain engine bug nor a plain authoring bug: the
engine is provably faithful, the trigger is authored, and the policy that authorised the trigger
adjudicated the WRONG PLANE.** The no-motion is unrelated and is one authored `speed: 0`.

---

## Defect 1 — the left-edge strip. DESIGN-SHAPED, with a real policy hole underneath.

### The engine side is correct, and it is checkable from source

`Parallax_Update` Step 5b (`engine/level/parallax.emp:1611-1651`) fills the 20-entry column buffer.
The plane-A half of every entry is:

```
        move.w  d1, (a2)+                   // FG word = camY (constant per column)
```

`d1` is the camera Y, identical for all twenty columns. `Vscroll_Write`
(`engine/level/parallax.emp:802-825`) emits all twenty longwords with no skipped entry and no index
arithmetic. **There is no expression on this path that could single out a column.** Whatever the
owner sees at screen x < 16 is not produced by engine arithmetic.

### The artifact is silicon, and it was measured, not inferred

With VDP reg `$0B` bit 2 set (per-column V-scroll), the leftmost partial 16-px column — the sliver
before HScroll's first 16-px boundary — renders at **V-scroll = 0 regardless of VSRAM[0]**. There is
no register that fixes it. `Vscroll_Write`'s own banner (`parallax.emp:768-782`) documents this.

Measured 2026-08-27 (controller run, `docs/research/2026-08-27-fg-left-edge-reproduction.md`,
`s4.debug` crc `9f9c0126`): reg `$0B` bit 2 is **0 at boot** and **1 on scenes 10-15**. Correlating a
total ground wipe of the two leftmost columns across all twenty scenes at one camera position: the
signature appears on **5 of 5 sampled bit-2 scenes and 0 of 14 bit-2-clear scenes** (scene 11 was
sampled at a wobble phase through zero and missed by a single sample). The owner's twenty-scene
playthrough is now an independent second confirmation of that same correlation, from a human eye
rather than a probe.

### The trigger is authored

`games/sonic4/data/effects/ojz_scenes.emp`, `rocking_scene` (`:334-349`) and `perspective_scene`
(`:377-391`), both:

```
        v_deform: SceneVDeform.Columns(DeformTable_<...>, speed, shift),
        left_column_mask: SceneLeftColMask.Accept)
```

`Accept` is the authored spelling of "ship the artifact". The scenes ask for per-column V-scroll and
explicitly accept its cost. So far this reads as hypothesis 2 — the engine is doing what the scenes
asked.

### But the `Accept` was reasoned about plane B, and the owner is looking at plane A

**This is the finding.** Every guard in the `left_column_mask` family tests plane-B factors and
plane-B deform only — `engine/level/scene_dsl.emp:1322-1376`: `Factor0Lock` is verified against
"a real layer's `fb` is not FACTOR_0" and against "a layer or anchor `dsb` is not 15". Neither
`fa` nor `dsa` is ever consulted. **Plane A is never adjudicated by the policy layer at all.**

Both scene banners inherit that blind spot. Rocking's, at `ojz_scenes.emp:322-327`, states:

> at runtime the artifact genuinely cannot occur: `fb` is `FACTOR_0` and the only plane-B H-deform
> source is `DeformTable_Zero`, whose every sample is 0, so plane-B HScroll is identically zero.

That claim is **true** (`deform_zero()` at `engine/level/parallax_dsl.emp:60-62` returns 256 zeros)
and **irrelevant to what is on screen**. On plane A the same scene authors `fa: FACTOR_1`, and
`Decode_Factor_A` with `s1 = 0` returns `-camX`. Plane A's HScroll is therefore a multiple of 16 in
**one camera position out of sixteen**; the partial column exists at the other fifteen. Plane A's
correct V-scroll is `camY` (non-zero everywhere in this act), so the strip renders the foreground at
V-scroll 0 — different world rows — which is precisely the measured signature: content in the upper
rows, ground band absent, screen-pinned across 32 px of camera travel (d-32's cell table and
four-position sweep).

**So `Accept` is a real decision for plane B and an unexamined consequence for plane A.** Nobody
ruled on the thing the owner is reporting. That is d-32's own conclusion, restated: d-27 authorised
"eight pixels on the background"; what ships is sixteen pixels on the foreground with the ground
wiped out, and a ruling taken on a materially understated description does not carry over.

### Where this leaves hypothesis 1 vs hypothesis 2

- **Not (1) in the sense of an engine arithmetic bug.** The column fill and the VSRAM emit are
  correct and there is no candidate expression.
- **Partly (2):** the scenes turn the mode on and declare Accept.
- **But there IS an engine-side hole, and it is in the policy layer, not the renderer:**
  `SceneLeftColMask` cannot see plane A. A future scene could truthfully declare `Factor0Lock`,
  pass the build, and still lose the foreground strip — the guard would certify a claim about the
  plane nobody is looking at. That is worth booking whichever way the owner rules on the pixels.

---

## Defect 2 — Rocking Slow's stillness. PURE AUTHORING, and unrelated to defect 1.

`Scene_Rocking_Slow = rocking_scene(speed: 0, shift: 0)` (`ojz_scenes.emp:351`).

`speed` is the per-frame phase advance for the per-column V-deform. Step 5b does
`add.w d3, Parallax_V_Deform_Phase_BG` with `d3 = pcfg_v_deform_speed_bg = 0`. **The phase never
moves.**

Its only other animating input is `deform_bg: SceneDeform.Shared(DeformTable_Zero, 1)` — advancing a
256-entry all-zero table at speed 1 produces the same zeros every frame.

**`Rocking_Slow` is the only one of the twenty scenes with zero time-varying input on every axis.**
Standing still, nothing on screen can change. Compare the rest of the family conventions:

| family | slow | mid | fast |
|---|---|---|---|
| Shimmer | 1 | 3 | 6 |
| Haze | 1 | 2 | 4 |
| Perspective (`v_speed`) | 0 | 1 | 2 |
| **Rocking (`speed`)** | **0** | 1 | 3 |

`Perspective_Subtle` also takes `v_speed: 0` but still animates, because its `h_speed: 1` shimmer is
live. `Rocking_Slow` has no such second axis.

It is not *nothing*: the `.col` loop increments `d4` per column, so twenty consecutive table samples
still apply and the scene is a **static per-column tilt** on plane B. That is documented as
deliberate — `scene_registry.emp:372` and `ojz_scenes.emp:328` both call it "a STATIC tilt with the
table attached, not an absent attachment", and the entry exists partly to keep `CAP_PER_COL_VSRAM`
raised for a static attachment. So the intent is on the record.

**The bug is the promise, not the value.** An entry the debug cycle labels "Rocking Slow" cannot
rock. Either it should be `speed: 1` (with `Rocking`/`Fast` moving to 2/4 to keep the family
cadence) or it should be labelled "Rocking Static" in the roster.

**One defect or two: TWO.** The strip is silicon plus an unruled policy on all six scenes; the
stillness is one authored integer on one scene. They coincide only in that `Rocking_Slow` exhibits
both, which is what made the owner's sentence read as a single symptom.

---

## Does it reach the shipped default scene? NO.

`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:157` installs `ParallaxConfig_OJZ_Default`,
which is `lower4(SCENES[0])` = `Scene_OJZ_Default` (`scene_registry.emp:307, :683`).
`Scene_OJZ_Default` attaches no `SceneVDeform.Columns`.

Three independent gates keep bit 2 clear on that config: the per-frame reg `$0B` assertion
(`parallax.emp:879-911`) ORs bit 2 only from the active config; Step 5b's fill and `Vscroll_Write`'s
emit both `beq` out on a NULL `pcfg_v_deform_table_bg`. Measured confirmation: bit 2 read **0 at
boot** on 2026-08-27.

**Urgency: DEBUG effects-lab only.** A normal boot and normal play of OJZ act 1 never enters the
mode. It is highly visible to *this* owner because he plays the DEBUG shape and cycles scenes — but
it is not a shipping-path defect, and it should not preempt the two byte-moving parcels queued
ahead of it.

---

## Where I contradict the report

The relayed screenshot description says **~60 px**. **No measurement supports 60.** The measured
band is **16 px — two 8-px columns** (d-32's cell table at `Camera_X = 195`: x=0 and x=8 transparent
across every ground row, x=16 onward carrying the band; and the four-camera screen-pin sweep showing
x=0/x=8 empty at all four positions while x=16/24/32 change). 16 px is one VSRAM column-pair, which
is *the* grain of this silicon quirk. **There is no mechanism in this class that widens to 60 px.**
Most likely the relay over-read a scaled screenshot.

**The sharper contradiction is on the working scenes.** The report says the ground stops ~60 px short
of the left edge on the *working* scenes too, exposing a full-height BG strip. That **contradicts the
measured control**: the 2026-08-27 run found the two leftmost columns *clean* at the same camera Y
with bit 2 clear, and the twelve-position sweep on the boot scene found no left-edge deficit at all.
If the owner genuinely sees a full-height strip on the fourteen non-deform scenes, **that is a third
phenomenon and nothing on file explains it.** It is the one item I would not let pass on description.

---

## Owed correction, independent of any ruling (comment-only, byte-neutral)

`engine/level/parallax.emp` still carries two comments that are **stale and wrong for this game**:

- `:670-672` — "No config attaches a column table, so VDP reg `$0B` bit 2 is never set and the test
  is dead."
- `:793-795` — "No scene attaches a v-deform column table, so `pcfg_v_deform_table_bg` is NULL for
  every config this game can install and the emitter is unreachable."

Six scenes attach one and the emitter runs. d-32 flagged these on 2026-08-27; they are still
present. A reader chasing this bug hits them first and is told the mechanism cannot occur.

---

## Proposed fixes — DESCRIBED, NOT APPLIED

1. **The strip, properly:** the `SpriteMask` arm, currently refused by `scene_dsl.emp:1375` pending
   the strip emitter (aeon+sigil port-flip pair, plus a game-owned opaque mask tile). **It must be
   specified for plane A, not plane B** — an emitter that covers only the plane-B case would land,
   pass its gate, and leave the owner's symptom untouched.
2. **The policy hole, cheaply and separately:** extend the `left_column_mask` guard family to test
   `fa`/`dsa`, so `Factor0Lock` cannot be certified while plane A can H-scroll. Comptime-only, zero
   ROM bytes. Worth doing even if the owner rules "ship the artifact", because today the guard
   certifies a claim about a plane that is not the one at risk.
3. **Considered and rejected:** quantising plane A's HScroll to a multiple of 16 while bit 2 is set
   would remove the plane-A half outright, since plane A's V-scroll is already uniform across all
   twenty entries. It costs sub-tile-smooth foreground scrolling on those scenes, which is a worse
   artifact than the one it fixes. Recorded so the next reader does not re-derive it.
4. **Rocking Slow:** `rocking_scene(speed: 0, ...)` -> `speed: 1`, optionally moving `Rocking` and
   `Rocking_Fast` to 2 and 4 for family cadence — or rename the roster entry to "Rocking Static".
   This changes `pcfg_v_deform_speed_bg`, a shipped record byte, so it is a byte-mover needing the
   freeze ritual, and the speed values are owner taste.

---

## Runtime TAGs — what the controller should capture

This lane cannot run the emulator. `tools/fg_left_edge_probe.py` is the ready instrument (plane-A
`opaque` per cell across the left edge) but it has **no scene selection**, so as written it samples
the boot scene with bit 2 clear.

**TAG 1 — settle the 60-vs-16 width.** Scene **12** (`Rocking Fast`, the loudest of the six and not
phase-dependent like scene 11). Sample plane-A opacity at screen **x = 0, 8, 16, 24, 32, 40, 48, 56,
64** across ground rows **y = 168, 176, 184**. Prediction if the mechanism is the booked one: x=0 and
x=8 transparent, **x=16 onward opaque**. If the deficit extends past x=16 the booked mechanism is
incomplete and the width is a new finding.

**TAG 2 — the working-scene strip, the highest-value capture.** Same columns and rows, on scene
**0** (`OJZ Default`) at the *same camera position*. Prediction from the measured control: **all
columns opaque, no strip.** If the owner's full-height BG strip appears here, it is a third defect
and everything above is only half the story.

**TAG 3 — read bit 2 at the sample point, every time.** `VDP` reg `$0B` (or
`VDP_Shadow_Table + VDP_MODE3_OFF`). Two instruments manufacture a false negative here and both did
on 2026-08-27: the DEBUG warp clears bit 2, and travelling re-applies the section's own scene, so
`Debug_Scene_Index` can read 10 while bit 2 has gone back to 0. **Never trust the scene cursor.**

**TAG 4 — Rocking Slow's stillness, if a pixel confirmation is wanted.** Scene **10**, player
stationary, `state_hash` or a framebuffer hash over ~120 frames. Prediction: **identical every
frame**. Scene 11 under the same conditions must differ. That converts "does nothing" from a report
into a measurement, and it distinguishes "authored static" from "the table is not being sampled".
