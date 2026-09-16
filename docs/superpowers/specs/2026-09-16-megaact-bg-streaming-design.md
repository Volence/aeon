# Region background switching — design v2 (2026-09-16)

**Status: DIRECTION RULED by the owner, in session, 2026-09-16. Nothing built.** Under review by a
Fable agent at the owner's request, before any implementation planning.

**This is v2, a clean rewrite.** v1 was drafted, then layered with corrections as the owner refined the
goal over one afternoon. Its superseded designs are summarised in §8 with the reason each was dropped, and
remain readable in git (`aea08ce6`, `9532dd30`, `a7247ecb`, `c0a75d0a`). **Read §8 before proposing any
of them again.**

---

## ⚠ CORRECTIONS FROM THE FABLE REVIEW (2026-09-16T20:25:05Z) — READ BEFORE ANY SECTION BELOW

Full review: `docs/research/megaact-bg-streaming/07-fable-design-review.md`. **Verdict: on the right track for the
background, but the plan must be reordered.** The sections below are NOT yet rewritten; these corrections override them.

**False in this design:**
- **§3.6 "an over-budget spot STUTTERS" — FALSE. In release it SOFT-LOCKS.** No evictable frame → release returns
  `PAGE_NOT_RESIDENT`, the page is re-enqueued forever, the stall watchdog exists only under DEBUG, and the camera hold
  never releases while the player can walk off screen. **And the budget is the 80×60 cache window's page set, not the
  visible screen.** The owner's ruling R5 (warn, let it exist) was made on the false "stutters" account and must be
  put back to him.
- **§3.2 and §4 overclaim Icecap as "verified firsthand".** The trigger and the two counters are MEASURED; that the
  gate CAUSES the lag is INFERRED, as the reconciliation itself says. The upgrade was this design's error. The review
  also found a second mechanism: ICZ2's secondary art lands at `$122`, where ICZ1's visible art already sits, so it is
  overwritten in place whatever the gate does. Only a blank or a mask prevents that, which argues MORE strongly for §3.1.
- **§5 M-A "about a sixth of a second" — covers two of three steps.** The blank has no transport and no cost anywhere
  in this design. A full-plane blank is 8,192 B, more than the NTSC window. **Realistic: 13-27 frames.**
- **§3.1 "every region gets the whole 376-tile block" — it is 320 static plus a 56-tile band reserve** under today's
  importer contract.
- **§2 dropped the owner's OC-3 ruling without record.** He said *"Maybe hold, I guess we should see how long it is"*.
  Restored here: under full overwrite its analogue is holding the camera when the authored cover is shorter than the
  sequence, using the existing `Camera_Art_Hold`.

**Undesigned, and blocking:**
- **Cover at speed is about two screens of opaque foreground per crossing** (~720 px at 16 px/frame for a 25-frame
  sequence). The corridor did not go away; only its check did. **v1 D4's CHECK should return as a build warning.**
- **The blank colour is CRAM line 0 entry 0 — the character's colour**, which the designer does not own. Needs an
  authored fill word per crossing.
- **Two existing Plane B writers** (the steady-state streamer and `Section_RedrawPlanes`) will paint garbage
  mid-sequence unless gated.
- **Boot, respawn and warp into a non-default region are wrong by construction:** `Region` has no tiles field.
- **Hysteresis belongs at the crossing** (where palette and parallax also swap), not at the background alone.
- **BgAnim has no table selector in release.**

**OWNER, 2026-09-16T20:44:58Z, on the blank step — challenged, and the controller agrees; it is dropped by default:** *"is there a
reason to go blank screen first? If it's blank it looks messed up anyway and is that just taking extra steps/time?"*
The blank's ONLY purpose is what shows if the background is VISIBLE during the switch (flat colour instead of the old
layout scrambled across half-overwritten tiles). **R3 already makes the switch covered by foreground, and behind cover
neither is seen, so the blank is pure cost** — and it was the expensive, undesigned part (2-16 of the review's 13-27
frames, no transport, and an uncovered blank shows the character's colour 0). **§3.1 becomes: overwrite, then repaint,
behind authored cover.** What survives unchanged, and is the actual Icecap fix: **the repaint must not start until the
overwrite completes.** The blank may return only as an opt-in for a crossing deliberately left uncovered.
**FG-OVERBUDGET-SOFTLOCK answered: warn and let the game recover** (*"probably 1"* — a lean, recorded as said).

**Reordered next steps:** M-B FIRST (the 80×60 window's page set along a stitched real-zone seam and at a three-zone
junction — tool-only, and it decides whether the stress test can exist at all), M-E (confirm the release soft-lock),
choose the blank transport, THEN M-A as the full three-step sequence under a worst-case fall.

---

## 1. The goal

**The product (owner's words):** *"eventually when we start sonic 4 this means that one act can have like
a cave region, a tree top region, a deep jungle region, and they can feel like completelyy different areas
all within the same act."*

**The stress test that proves it:** all of Sonic 2 or Sonic 3 as **one continuous act**. *"I should be
able to get all of sonic 3 into it without stopping to switch zones or go to a new zone loading screen or
anything ... Think of those zones just as how regions would function."*

**The model:**
- **A zone IS a region.** The engine has no separate zone concept.
- **One act, continuous play.** No zone switch and no loading screen, ever.
- **Zones abut directly.** A neighbour's foreground is visible across the boundary before you reach it;
  *"you can see chemical plant tiles on the ground while heading towards them in emerald hill"*.
- **At a junction, several zones' foreground can be on screen at once.** *"chemical plant next to oil
  ocean and mystic cave below, so all 3 can potentiallyy be seen on fg"*
- **The background is whichever region the camera is in.** One background at a time.
- **Region shapes are arbitrary.** *"We still want the region shapes however we want"* — a 2D patchwork.
- **A single zone can hold several background regions.** *"bg change within a zone for us too"*

**The Sonic 2/3 act is the extreme case, not the product.** If whole classic zones work as regions of one
act, varied regions inside a Sonic 4 act are the easy case.

---

## 2. Owner rulings (2026-09-16, verbatim)

| # | Question | His answer | What it means |
|---|---|---|---|
| **R1** | Is this its own project? | *"Part of regions."* | Scoped inside the regions project. |
| **R2** | How does the background change at a crossing? | *"just completely overwrite the bg tiles in vram ... Ok cool glad we agree"* | **Full overwrite** (§3.1). No slot splitting. |
| **R3** | What hides the swap? | *"That's on the artist/level designer to just cover up"*; *"either way we'll cover it with fg most likely"* | **Authored cover**, usually foreground. The engine doesn't enforce it. |
| **R4** | Junction with several neighbours? | *"This might be solved by whatever you're closer to right? ... the bg should be covered up by designer"* | Moot under full overwrite: nothing is predicted (§3.4). |
| **R5** | Densest foreground spot over budget? | *"it should warn us in aurora and then if we ignore it I guess nothing right?"* | **Warn, don't refuse.** Consequence clarified in §3.6. |
| **R6** | Palette at a crossing? | *"Palette's fine the way we have it, if you get close andd we set it to start blending that should work like that too but it's still up to use to determine fg coverage and ddwith that we'll know how palette shoul dwork."* | **Existing per-region snap/fade stands.** A position-driven blend is booked (§3.5). Foreground coverage decides palette handling, per case. |
| **R7** | Snap or fade option? | *"Maybe we can have an option to choose? ... as you got half way through one it would start fading to the next."* | Snap/fade **already exists per region**. The halfway blend is new (§3.5). |

---

## 3. The design

### 3.1 A background switch is a full overwrite, in three ordered steps

When the camera centre enters a region whose background layout differs from the one Plane B currently
holds:

1. **Blank.** Fill Plane B with an empty tile, so nothing on screen references the tiles about to change.
2. **Overwrite.** Replace the background tile block with the new region's tiles, raw from ROM, spread over
   frames against the art budget.
3. **Repaint.** Draw the new layout through the existing step-6 crossing wipe.

**Each step waits for the previous one to finish.**

**Why this order.** The old background is on screen while its tiles are overwritten. Overwrite first, and
for those frames the old layout is drawn with new art, which is garbage. Blanking first removes every
reference, so the overwrite is invisible. **Batman & Robin does exactly this in shipped code:** it fills a
plane with a blank tile before reusing that plane's tile range (`docs/research/megaact-bg-streaming/04-batman-tf4-ristar.md`,
"blank before reusing a plane's tiles").

**What it buys:**
- **Every region gets the whole 376-tile background block.** No splitting into halves or quarters.
- **No preload and no prediction**, so junctions need no special handling (§3.4).
- **Much simpler than any slot scheme** (§8).

**What it costs:**
- **A brief blank background at each crossing.** R3 makes hiding it the designer's job.

### 3.2 The gate is structural now

**S3K's Icecap Zone shows new art before it has loaded**, because it gates its act switch on the layout
data (`Kos_decomp_queue_count`) rather than the tiles (`Kos_modules_left`). Verified firsthand:
`docs/research/megaact-bg-streaming/00-controller-reconciliation.md` R1.

**§3.1's ordering makes that failure impossible by construction:** the repaint (step 3) cannot start until
the overwrite (step 2) completes, so the new layout never references a tile before it is uploaded. This must
be enforced by the sequence itself, not by timing, and a gate should be able to prove it red.

### 3.3 Hysteresis at a boundary

A player hovering on a region boundary would trigger a full overwrite on every step back and forth, making
the background flicker. **Switching back requires the camera centre to pass a margin beyond the boundary.**
The margin size is a feel call, to measure (§5, M-C).

### 3.4 Junctions need nothing special

Under a slot scheme, a junction was hard: the next region is ambiguous, and two slots can preload only one
guess. **Under full overwrite nothing is preloaded**, so there is no guess. The background switches when the
camera centre actually enters a region, and the designer's cover hides the swap (R3, R4).

### 3.5 Palette

**Hard hardware fact, verified in code:** the engine writes CRAM **lines 1-3 only** for level art; line 0
belongs to the character (`engine/effects/palette.emp` header, LINE-0 INVARIANT). **So all level art on
screen, foreground and background, shares 45 colours.**

- **Zones stacked vertically** can keep separate colours: the raster system writes CRAM per screen band
  (`engine/effects/raster_dsl.emp`, `stream_cram`, `band(top, bot, ...)`).
- **Zones side by side on the same lines must share those 45 colours.**

**Ruled (R6): the existing machinery stands.** Per-region snap or fade exists today: `ep_transition`
(`engine/effects/preset.emp:67`) and `pcfg_transition` (`engine/structs.emp:355`, *"0 = smooth lerp
(default), 1 = instant snap"*). **Foreground coverage, decided by the designer per case, determines how
palettes should blend** at a given boundary.

**Booked, not designed — a position-driven blend (R7).** Today's fade runs on a timer (`PAL_FADE_FRAMES` = 16,
`engine/effects/palette.emp:86`). The owner's idea ties blend progress to how far the camera is through a
crossing. Two properties worth keeping (INFERRED): **it reverses** if the player walks back, which a timed
fade cannot, and **it tracks the camera** rather than a stopwatch. Open for its own design: which axis
drives progress when a crossing can be entered from the side or from above, and how it composes with
`Palette_Compose`'s cycle, operator and variant stages.

### 3.6 The foreground: zone-agnostic, budgeted at the densest spot

**The foreground never needs a zone concept.** It is already one globally deduplicated, spatially paged tile
set, streamed by camera position (`engine/level/page_cache.emp`, `page_in.emp`; the repo's architecture
describes the act tileset as "globally-deduped, spatially-ordered, paged"). Two zones' foreground on screen
at once is just two sets of pages near the camera.

**The budget question is the working set at the DENSEST point on the whole map**: the worst junction, where
several zones' foreground is visible together.

**Ruled (R5): warn, don't refuse.** Aurora warns while authoring. The aeon build should also compute and
report the offending spot, so a layout that didn't come through Aurora is still caught.

**What "ignore the warning" actually does, stated so it is an informed choice:** the spot does not show
garbage. The foreground cache holds the camera until the art it needs is resident (`Cache_Art_Stall` plus
`CLAMP_MARGIN_TILES` = 4, `engine/system/constants.emp:557`). **So an over-budget spot STUTTERS.** If the
visible screen alone references more art than the pool holds, it can never settle.

**Two things that change at game scale:**
- **The pinning policy** pins a page used by 75% or more of sections (`tools/ojz_strip_gen.py:142`). Nothing
  is used by 75% of a whole game, so the rule stops meaning anything.
- **OJZ act 1 has never actually streamed.** It is fully resident; eviction runs only under the
  `STRESS_EVICT` fixture (`docs/research/megaact-bg-streaming/06-aeon-baseline-and-modern-techniques.md` Q1).
  **The mechanism the whole foreground plan depends on has not run under real load.**

---

## 4. What the research established (the load-bearing parts)

Full notes: `docs/research/megaact-bg-streaming/00` to `06`. Each claim there is labelled MEASURED or INFERRED
and carries its `file:line`.

- **Transfer bandwidth is not the constraint.** A whole Sonic 2 zone's art uploads in 5-8 frames at aeon's
  4096 B art budget. The real limits are decompression time and co-residency (05).
- **No shipped Sonic game changes zones seamlessly.** S3K's mid-level art swaps are act changes within a
  zone, almost all with the camera locked. Zone to zone, S3K and S2 fade to black (01).
- **Icecap Zone is the one act change S3K triggers while scrolling**, and it shows art before it has loaded
  (reconciliation R1, verified firsthand). Sandopolis's countdown trigger was not traced.
- **Zone-scale live streaming has shipped:** Alien Soldier and Gunstar Heroes stream 376-711-tile loads
  during live scrolling, holding stage progress until each finishes (03).
- **Batman & Robin blanks a plane before reusing its tile range** — the ordering §3.1 adopts (04).
- **S3K Launch Base swaps foreground LAYOUT, not art**, when you enter a building: it rewrites chunk IDs in
  the RAM layout on player position, redraws the screen, and restores on exit. Both looks use resident tiles.
  A cheaper, different problem from zone art; a candidate regions feature in its own right.
- **Real zones share almost no tiles**: 0.1-0.3% even allowing flips (06). Deduplication won't help.
- **Backgrounds alone are small; a whole zone is not.** S3K act backgrounds measure 104-174 tiles, which fit
  376 with room to spare. A whole zone's art is 604-965 tiles (S2) or 698-2536 (S3K) (01, 06).

---

## 5. Measurements owed before implementation

| | What | Why it matters |
|---|---|---|
| **M-A** | The real time of blank + overwrite + visible repaint, in an emulator | §3.1's cost. **Derived estimate: ~3 frames to upload 376 tiles (12,032 B at 4,096 B/frame) plus ~7 frames to repaint the ~28 visible rows at 4 rows/frame — about a sixth of a second. Not measured.** The art budget is shared with foreground streaming, so a crossing during heavy foreground load could take longer. |
| **M-B** | The foreground working set at the densest junction of a stitched Sonic 2/3 map | §3.6's budget question. |
| **M-C** | The hysteresis margin that stops flicker without feeling sticky | §3.3. A feel measurement. |

**No longer blocking:** Sonic 2's background-only tile count. Under full overwrite a region needs at most
376 tiles, not 188; S3K's measured backgrounds fit easily. Worth measuring for completeness, not as a gate.

---

## 6. Open risks, for the review to press on

1. **The blank is visible wherever the designer does not cover the crossing.** R3 makes cover authored;
   nothing tells the designer a crossing is uncovered.
2. **Background animation bands.** `BgAnim` bands carry absolute VRAM destinations inside the background
   block, and the step-6 wipe does not swap `BgAnim` tables (06 Q5). A full overwrite clobbers band tiles, so
   the new region's blob must carry its own band tiles and band table. **Not designed.**
3. **The overwrite competes with foreground streaming for the same art budget.** A crossing at a dense
   foreground spot may be slower than M-A's calm-frame figure.
4. **The foreground plan rests on a mechanism that has never streamed under real load** (§3.6).
5. **The PAL DMA budget is too small** (booked `DMA-BUDGET-PAL-LINE-COUNT`): conservative, so safe, but it
   understates PAL throughput.

---

## 7. Proposed order, after review

1. **M-A** — measure the overwrite and repaint cost on a running ROM.
2. **The switch**: blank, overwrite, repaint, strictly ordered, with a gate that goes red if the repaint can
   start before the overwrite completes.
3. **Hysteresis** (M-C).
4. **`BgAnim` handover** (risk 2).
5. **The foreground at game scale**: M-B, the densest-spot warning in the build, and the pinning policy.
6. **Position-driven palette blend** (§3.5), as its own design.

---

## 8. Superseded, and why — read before proposing any of these

| Superseded | Why it was dropped |
|---|---|
| **Build-time slot colouring** (v1 D2), generalising 08-08's half-pool plan | Assumed zones form a **chain**: a path graph, two colours, 188 tiles each. The owner's **2D patchwork** makes a planar graph needing **up to four colours**, about 94 tiles each, under every measured S3K act background. Full overwrite gives every region all 376. |
| **Runtime two-slot A/B with a per-word base offset** (Alien Soldier's rebasing) | Proposed to fix the four-colour problem. Unneeded once full overwrite removed slots entirely. |
| **Preload plus junction prediction** ("closer to" vs "headed to") | Needed only because slots preload. Full overwrite preloads nothing. |
| **Derived corridor length** (v1 D4) | There is no corridor. Zones abut, and the designer covers the swap (R3). |
| **Theme preload gate on the wipe arm** (v1 D3) | Replaced by §3.2's structural ordering: blank, overwrite, repaint. |
| **08-08 step 3, "theme tile-pool halving + paged theme swap"** | Superseded by full overwrite for the same reasons as the first row. 08-08's safe-swap principle survives as §3.2. |

**One correction carried from v1, because it was said to the owner:** background streaming *was* designed
before today, in `docs/research/2026-08-08-bg-seam-streaming.md`. The owner was told otherwise; that was
false. This design supersedes 08-08's step 3; it does not replace work that never existed.
