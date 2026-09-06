# The shipped section-4 showcase, driven — its background IS destroyed by its own curve

**Date** 2026-09-06 · **Branch** `parcel/depth-showcase-onset` ·
**Instrument** `tools/depth_onset_probe.py` (added here), oracle-aether headless.
**Raw data** `docs/witness/depth-onset-2026-09-06.json` (4 play + 4 attribution + 17 sweep +
14 A/B samples). **Pictures** `docs/witness/depth-onset-*-2026-09-06.png`.
**Predecessor** `docs/witness/curve-desc-2026-09-06.md`, whose open items 2 and 0 this
answers and partly corrects.

---

## 1. The answer, first

**Yes. At a play-reachable position the d-15 showcase's background is destroyed, and the
curve is what destroys it.**

Warping through the ordinary DEBUG mailbox to player (3000, 3000) — nothing poked, nothing
pinned — lands Camera (2840, 2888) with `Parallax_Current_Config` on the section-4 binding.
There:

| band | span | `fb` → `curve: To(..)` | excursion | vs 192 px margin | rate | Plane B wins |
|---|---|---|---|---|---|---|
| 112..159 | 48 | `FACTOR_1_4` → `FACTOR_3_8` | 348 px | 1.81 x | 7.40 px/line | **99%** of pixels |
| 160..223 | 64 | `FACTOR_1_2` → `FACTOR_1` | 1398 px | 7.28 x | 22.19 px/line | **100%** of pixels |

`docs/witness/depth-onset-ab-2840-band160-2026-09-06.png` is the proof it is the curve and
not the art: the shipped render (top) against a **control ROM built from the same scene with
its two `curve:` keys deleted and nothing else touched** (bottom), at the same camera, same
warp, same frame counts. The control shows recognisable vertical foliage; the shipped build
shows fine horizontal noise with no structure. The Plane-B nametable is **hashed on both
ROMs and is identical** (`sha256[:16] c4d7e2cb3db35fbe`), so the two frames are the same
background art and the only difference is the per-line scroll.

`depth-onset-play-exposed-2026-09-06.png` is the whole frame at that position.

**This is an owner-facing look call and I am not proposing a fix.** What to do about
authored content is his.

---

## 2. Why it is not visible everywhere, measured rather than guessed

At the other three play positions the same scene looks fine. That is **occlusion**, and
`emulator/pixel_attribution` (on the real frame; nothing masked, nothing re-rendered) says
so directly:

| warp | Camera | band 112 | band 160 |
|---|---|---|---|
| (2200, 2300) | (2040, 2188) | planeA 78%, planeB 21% | **planeA 100%** |
| (3000, 2300) | (2840, 2188) | planeA 78%, planeB 21% | **planeA 100%** |
| (4000, 2300) | (3840, 2188) | planeA 78%, planeB 22% | **planeA 100%** |
| (3000, 3000) | (2840, 2888) | **planeB 99%** | **planeB 100%** |

`Vscroll_BG` is 0 at all four, so Plane B's contribution at a given Camera_X is *identical*
between Camera_Y 2188 and 2888 — the difference is entirely how much foreground covers it.
`depth-onset-play-occluded-2026-09-06.png` (Camera_Y 2188) and
`depth-onset-play-exposed-2026-09-06.png` (2888) are the same background, once hidden and
once shown.

**This wrecked my first pass and is the methodological finding of the parcel.** The first
camera sweep was run at Camera_Y 2188 and its band-160 crops are pictures of **Plane A** —
which is `FACTOR_1`, locked to the camera, and shears by nothing. Any onset read off them
would have been read off the wrong layer. The probe now measures Plane-B exposure at every
sample and prints it beside every band, and no visual claim here rests on a band below 99%.

---

## 3. The reachable camera range, measured

Section 4 is col 1, row 1 of the 3x3 grid at `SECTION_SIZE $0800`
(`act_descriptor.emp`:111-112), so its world x is 2048..4095 — **the same column as section
7**. Measured Camera_X from warps to player x 2200 / 3000 / 4000: **2040, 2840, 3840**.

Both derived onsets (`camX = 192/|Δf|` → 1536 for band 112 and 384 for band 160) are far
below that. So **both curve bands are past the wrap margin at every play-reachable camera
x**: band 112 by 1.30..2.45 x, band 160 by 5.23..9.84 x. The arithmetic booked in the
previous parcel holds, and it is now a run.

---

## 4. The walker is exact, on shipped content, at 21 camera positions

Derived-vs-measured on `Hscroll_Buffer`: **0 of 224 lines differ, max |delta| 0**, at 4 play
positions, 17 swept positions and every A/B sample. The expectation comes from the scene's
authored factors plus live state; `bc_step` / `bc_rem` / `bc_span` — the walker's own output
for the ramp — are never read.

**The ±1 that arrived first, and what it was.** The swept samples initially showed 134..160
lines differing by exactly 1. It is **band drift**: `Parallax_Update` adds
`Parallax_Drift_Acc`'s pixel part to each band's Plane-B word
(`parallax.emp` `.cap_band_drift_accum`). Read, not reasoned:

* **exactly zero on every band at every play position**, held across 120+ extra frames, and
  every shipped band record carries drift rate 0 (read out of the binding's ROM image) —
  which is why `play` was exact from the first run;
* `(-1, -1, -1, -1, 0)` in the sweep, seeded by the camera poke plus config re-pin.

It is **not** a constant offset in the buffer: a drifted base changes the hoist's spread, so
the Bresenham pair moves and the ramp *shape* differs too (16..26 lines per sample). Folding
the accumulator in makes all 17 exact. The probe prints both columns so the correction
cannot hide behind a green number.

**Not established:** why a camera poke seeds a non-zero accumulator when every shipped rate
is 0. Booked, not guessed.

---

## 5. The excursion-vs-rate discriminator does NOT close, and the reason is not the one I was given

The dispatch's hope was that two curves on one scene at onsets 1536 and 384 would separate
"excursion crosses 192 px" from "per-line rate crosses ~1 px/line". **It does not, and the
obstacle is arithmetic rather than the spans.**

`excursion = rate x span`, and this scene's curve bands are 48 and 64 lines — a ratio of
4/3. So across the whole scene the two quantities stay nearly proportional, exactly as they
did on sec7's single 224-line band. Worse, band 160 dominates band 112 on **both** metrics
at every camera x (4 x the excursion, 3 x the rate), so no single frame separates them.

The one accessible matched pair is cross-camera, and against a per-camera control it is
sound — but it lands where duplication is weakest:

| pair | span | excursion | vs margin | rate | duplicates | look vs its own control |
|---|---|---|---|---|---|---|
| band 160 @ camX 512 | 64 | 252 px | 1.31 x | **4.0** | **YES** | a diagonal shear |
| band 112 @ camX 1536 | 48 | 188 px | 0.98 x | **4.0** | **no** | a diagonal shear |

(`depth-onset-ab-rate4-dup-2026-09-06.png` and `...-rate4-nodup-...png`.) **At matched rate
they are indistinguishable.** At 1.31 x the margin only 60 px of the band's travel is past
it, so the duplicated column occupies under a fifth of the screen against a busy texture —
this is a weak test of duplication, not a clean refutation of it.

What the same-band ladder does show, art and control held fixed, is that severity is
**monotone in rate**: 1.97 px/line is a mild slant (`...-ab-rate2-...png`), 4.0 is a
stronger slant, 16.0 and 22.2 are destroyed (`...-ab-2840-band160-...png`).

### 5.1 What this does to the previous parcel's reading

`docs/witness/curve-desc-2026-09-06.md` §5 argued the excursion-vs-192 reading was the
better-argued of the two live models. **That still stands as geometry — above 192 px a plane
column really is shown twice, and that is derived, not fitted — but this parcel weakens it
as an account of the VISIBLE break**, because the first matched-rate comparison ever run
finds duplication at 1.31 x the margin visually undetectable. Both documents now say so.

### 5.2 The fixture that would close it, named precisely

Matched rate with a large excursion ratio needs a large **span** ratio, which neither scene
has. A scene with one curve band of span 64 and another of span 192, both authored to the
same rate, gives `E = 192` (no duplication) against `E = 576` (3 x past it) **at identical
per-line rate** — one build, and it is the experiment. `curve-desc`'s §5.1 asked for "vary
the span at fixed excursion"; this is the same request, stated as something authorable.

---

## 6. Left open

1. **The discriminator** (§5.2). Until that fixture runs, "excursion past 192" and
   "per-line rate" both survive, and the rate reading has gained ground.
2. **The drift accumulator's seeding under a camera poke** (§4).
3. **Whether the showcase is played anywhere near Camera_Y 2888** is not established. I
   reached it by warping. Whether ordinary play puts the camera where the foreground stops
   covering band 160 is a level-traversal question I did not answer, and it decides whether
   §1 is a defect the player meets or one only a debug warp can reach.
4. **`ojz_act1_floor`'s curve is untested** (`FACTOR_0` → `FACTOR_1_32`, `|Δf|` = 1/32,
   derived onset camX 6144). It is the one shipped curve whose onset is plausibly outside
   its section, and it was not driven here.
