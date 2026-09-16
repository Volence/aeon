# Background streaming across zones — design DRAFT for owner review (2026-09-16)

**Status: DRAFT. Nothing here is ruled or built.** The owner asked for research across every reference,
tech demos and modern techniques, then a design, **brought to him before anything is built**. This is
that design. It has not been through the lens audit this repo runs on design drafts before planning.

**The goal, in the owner's words:** *"our first like showcase of this will be sonic 2 or sonic 3 in 1
act, so we have to figure out what to do for things like this!"* Several classic zones back to back, no
act card, no fade, no load screen. Each zone brings its own foreground art, background art, palettes
and parallax.

## 000. UNDER DISCUSSION 2026-09-16T20:01:10Z — the owner's direction, NOT yet ruled; do not implement from this

**Why regions matter (his words):** *"eventually when we start sonic 4 this means that one act can have like a
cave region, a tree top region, a deep jungle region, and they can feel like completelyy different areas all
within the same act ... That's why the extremes of zones as regions for our test comes into playy."* **So
the Sonic 2/3 act is the STRESS TEST, not the product.** The product is varied regions inside Sonic 4 acts.

**His proposals, verbatim, pending his confirmation of direction:**
1. Densest spot over budget: *"it should warn us in aurora and then if we ignore it I guess nothing right?"*
2. *"how long would it take to, when we cross regions, just completely overwrite the bg tiles in vram?
   Instead of splitting it up ... if we have to go split it should bve the one you're in and the one you're
   *closest to*, not necessarily headed too"*
3. *"Corridor might be fine anyway for bg to save the jarring 'all of a sudden different bg'. That's on the
   artist/level designer to just cover up"*
4. Junctions: *"This might be solved by whatever you're closer to right? ... the bg should be covered up by
   designer so whenever yyou get past that part it should have the correct bg in."*

**A HARD LIMIT this raises, verified in code, that none of his proposals can design away:** the engine writes
CRAM **lines 1-3 only** for level art; line 0 belongs to the character (`engine/effects/palette.emp` header,
LINE-0 INVARIANT). **So all level art on screen, foreground and background, shares 45 colours.** Two zones
whose foregrounds need different palettes **cannot both show correct colours on the same scanlines.**
**Stacked vertically they can:** aeon's raster system writes CRAM per screen band (`raster_dsl.emp`,
`stream_cram`, `band(top, bot, ...)`), so a zone above and a zone below can each keep their colours on their
own lines. **Side by side on the same lines, they must share 45 colours.** This bites the Sonic 2/3 stress
test with real art; Sonic 4's authored regions can be designed to share palettes and avoid it.

---

## 00. ⚠ THE GOAL WAS REFINED BY THE OWNER, 2026-09-16T19:54:03Z — READ THIS BEFORE THE DESIGN BELOW

**Several sections below were written for the WRONG model** (zones in a row, linked by corridors). They are
kept, not deleted, so the reasoning that changed is visible. **Every section marked REOPENED below is not
to be implemented as written.**

**His words, verbatim:** *"bg change within a zone for us too. So think about it this way, we have 1 act, 1
continuous gameplay, and I should be able to get all of sonic 3 into it without stopping to switch zones or go
to a new zone loading screen or anything. Backgroudns can switch when we go from say emerald hill to chemical
plant, you can see chemical plant tiles on the ground while heading towards them in emerald hill, etc... Think
of those zones just as how regions would function. If we wanted to stitch things interestingly, we could have
chemical plant next to oil ocean and mystic cave below, so all 3 can potentiallyy be seen on fg but the bg is
whichever region you're in currently. Make sense? We still want the region shapes however we want"*

**The model, restated:**
- **One act, continuous play, a whole game in it.** No zone switch and no loading screen, ever.
- **A zone IS a region.** There is no separate zone concept for the engine to manage.
- **Zones abut directly, with no corridor.** The foreground of a neighbouring zone is visible across the
  boundary before you reach it, and at a junction **several zones' foreground can be on screen at once.**
- **The background is whichever region the camera is in.** One background at a time.
- **Region shapes are arbitrary.** A 2D patchwork, not a chain.
- **A single zone can hold several background regions.**

**What that reopens, and why:**

- **D2 (build-time graph colouring) — REOPENED.** Its two-colour argument depended on the zones forming a
  PATH. Arbitrary region shapes on a 2D map form a **planar** adjacency graph, which can need **up to four
  colours** (four-colour theorem), i.e. about **94 tiles per slot**, below every measured S3K act background
  (104-174). **The likely replacement (INFERRED, to design properly):** only **two** background themes are ever
  resident at once (the current one and the one being loaded), so **two slots suffice for ANY topology** if a
  theme's slot is chosen at RUNTIME. That needs a per-word **base offset** added at row-draw time. That is one
  constant `add`, far cheaper than the foreground's page lookup plus refcount. It is Alien Soldier's load-time
  rebasing, **which §6 rejected under the chain assumption.** That rejection is withdrawn pending the redesign.
- **D4 (derived corridor length) — REOPENED.** There is no corridor; zones meet at a region boundary. The
  preload must land before the camera centre crosses the boundary, triggered by approaching the edge.
- **NEW OPEN PROBLEM — the next region is AMBIGUOUS at a junction.** From one region the camera may be heading
  into any of several neighbours, and two slots can preload only **one** guess. Candidates: preload the region
  whose edge is nearest in the direction of travel, re-preload when that changes, and fall back to the camera
  hold (D3) on a wrong guess; or reserve a third slot at junctions. **This needs its own design and measurement.**
- **D6 (foreground) — SHARPENED, not reopened.** The foreground never needs a zone concept. It is already one
  globally deduplicated, spatially paged tile set streamed by camera position (the repo's own architecture
  says so). **The budget question becomes: the working set at the DENSEST point on the whole map**, the worst
  junction where several zones' foreground is visible at once. That is M-2, restated. At whole-game scale the
  foreground **pinning policy** (pin a page used by 75% or more of sections) stops making sense, because nothing
  is used by 75% of a game.
- **D1 (per-theme residency), D3 (THE GATE) and D5a (position-driven fade) STAND.** None of them depended on
  the chain. The gate matters more at a junction, not less.
- **OC-2 (what the corridor looks like) — DISSOLVED.** No corridor.

---

## 0. What this is, and a correction to how it was framed

**This is not a new design. It is step (3) of `docs/research/2026-08-08-bg-seam-streaming.md` §4 —
"theme tile-pool halving + paged theme swap" — re-derived against what has landed since and what the
2026-09-16 research found.**

That needs saying because the owner was told, earlier the same day, that background streaming *"was
never designed"*. **That was false**: the claim came from one spec file that doesn't mention
backgrounds, and it missed this 289-line design, which does. Everything below starts from 08-08 and
names where it keeps, sharpens or departs from it.

**Evidence base.** Six research slices plus a controller reconciliation, all committed verbatim under
`docs/research/megaact-bg-streaming/`:

| File | Slice |
|---|---|
| `00-controller-reconciliation.md` | Where two slices disagreed, settled by reading the source firsthand |
| `01-s3k-and-s2.md` | Sonic 3 & Knuckles and Sonic 2 |
| `02-sce-and-sonic-hack.md` | S.C.E. and sonic_hack |
| `03-vectorman-gunstar-aliensoldier.md` | Treasure and Vectorman |
| `04-batman-tf4-ristar.md` | Batman & Robin, Thunder Force IV, Ristar |
| `05-online-and-tech-demos.md` | Hardware bounds, homebrew, tech demos |
| `06-aeon-baseline-and-modern-techniques.md` | What aeon already has, and modern techniques mapped onto it |

**Citations below name the note; the note carries the `file:line`.** Every research claim is labelled
MEASURED or INFERRED in its note. Where this draft infers beyond a note, it says so.

---

## 1. What has landed since 08-08

08-08's build order, against the tree as of 2026-09-16:

| 08-08 step | State |
|---|---|
| (1) palette variants per section | Palette per region exists (`palette.emp`, region presets) |
| (2) vertical seam streaming — `Draw_BG_TileRow` + BG row trackers | **LANDED** as regions part 2 step 5 (`BG_Stream_Update`, `BG_Plane_Top`) |
| (3) theme tile-pool halving + paged theme swap | **NOT LANDED. This design.** |
| (4) horizontal connects-to | Not landed |
| (5) per-theme anim-band + parallax handoff | Not landed |

**Also landed since, and not in 08-08:** regions part 2 **step 6**, the crossing wipe. When the camera
crosses into a region whose background layout differs, `BG_Stream_Update` repaints all 64 plane rows at
`BG_WIPE_ROWS_PER_FRAME` = 4 a frame, starting at the top **visible** row. **That is a deliberate
departure from 08-08 §4 item 3(c), which said "rows repainted through the streamer while
off-screen".** Step 6's agent rejected hidden-first because the palette snaps on frame 0, so hidden-first
leaves new palette over old art for all 16 frames instead of 8. This design keeps step 6's order.

**08-08's hard dependency is satisfied.** It made step (3) depend on the art-streaming phase 2 page-in
machinery. That machinery exists: `engine/level/page_cache.emp`, `engine/level/page_in.emp`, raw-direct
page form, prefetch (slice 06).

---

## 2. What the research established

Only the conclusions this design rests on:

**R-1. Transfer bandwidth is not the constraint. Decompression time and co-residency are.** A full Sonic
2 zone's art (604-965 tiles) uploads in 5-8 frames at aeon's 4096 B/frame art budget. (Slice 05.)

**R-2. The one shipped scrolling corridor lags because it gates on the wrong thing.** S3K's Icecap Zone
triggers its act 1→2 swap on camera X during live scrolling. It gates the act switch on
`Kos_decomp_queue_count`, which covers chunks and blocks, **not** on `Kos_modules_left`, which covers the
8×8 tiles. Hydrocity gates on the tiles. Icecap's art visibly lags at speed. **MEASURED** for the trigger
and the counters; **INFERRED** that the gating causes the lag. (Reconciliation R1, read firsthand.)

**R-3. Two more games independently use the ordering Icecap skips.** Batman & Robin swaps a 78-tile
backdrop during live play: idle decompress, wait; budgeted upload, wait; only then a budgeted row
repaint. Its new tiles are fully in VRAM before the first nametable word references them (slice 04).
Alien Soldier and Gunstar Heroes stream **376-711-tile** loads during live scrolling, and stage code
waits on a "load finished" flag before repainting (slice 03).

**R-4. Zone-scale live streaming has shipped.** Alien Soldier's 711-tile and Gunstar's 708-tile loads
are Sonic-zone scale. In both, the corridor is a stage script — hold progress until loaded — not a
runtime mechanism. (Slice 03.)

**R-5. S3K never swaps between ZONES seamlessly.** Its mid-level swaps are same-zone act changes, mostly
with the camera locked in a boss arena behind a mask (AIZ's fire, HCZ's fully covering arena). Zone to
zone, both S3K and S2 fade to black. (Slice 01; Icecap is the one scrolling exception, R-2.)

**R-6. A background on its own is small; the foreground is the budget problem.** Background-only unique
tiles per S3K act: AIZ1 137, AIZ2 104 (174 with the fire), HCZ1 159, HCZ2 168. Every one fits in 188.
A whole zone's art is 604-965 tiles (S2) or 698-2536 (S3K), against the 768-tile foreground pool.
(Slice 01; reconciliation R2.)
**Caveat carried: Sonic 2's background-only counts were NOT measured.** Slice 06 could not split S2 tile
sets between planes.

**R-7. Real zones share almost no tiles, so deduplication won't make them fit.** Sonic 2 zones share
0.2-0.3% of tiles and S3K zones 0.1-0.2%, counting flips. (Slice 06.)

**R-8. The foreground and background keep indices valid differently.** The foreground translates every
word into a RAM shadow and refcounts frames. The background copies layout words straight from ROM, with
no translation and no refcount. So "put background tiles in the foreground page pool" is a real engine
change, not reuse. (Slice 06.)

**R-9. The step-6 wipe makes per-layout residency safe.** The wipe rewrites every plane row. Once it
finishes, no word from the previous layout remains on the plane, so background residency can be tracked
per **layout** instead of per word, with no RAM shadow. (Slice 06.)

---

## 3. The design

### D1. The residency unit is a background THEME, tracked per layout

A **theme** is a background layout plus the tile set it references. A theme's tiles must be resident
from the moment the wipe that paints it **arms** until the wipe that replaces it **completes** (R-9).

Rejected alternative: per-word refcounting as the foreground does (R-8). It needs a RAM shadow of
Plane B, which 08-08 already ruled out at 8192 B, plus a translation pass on every wipe row.

### D2. Theme VRAM slots are assigned at BUILD time, by graph colouring

**This generalises 08-08's "halve the BG pool".**

- **Nodes** are themes. **An edge** joins two themes that can be resident together, i.e. whose regions
  meet across one crossing.
- Colour the graph so neighbouring themes never share a colour. **Each colour is a fixed VRAM sub-range
  of the background block.**
- A theme's layout words are baked against its colour's range, so **`Draw_BG_TileRow` doesn't change
  and there is no runtime translation.**
- **The build proves capacity**: every theme must fit its colour's range, or the build refuses and names
  the theme.

**A straight chain of zones is a path graph, and two colours cover any path.** Two colours over the
376-tile block is exactly 08-08's half-pool plan, at **188 tiles per half, not 08-08's 224** (08-08
used the stale 448 figure). S3K's measured background-only acts, 104-174 tiles, all fit (R-6).

A branching or looping act can need more colours. The tool handles that; the capacity per colour shrinks
accordingly, and the build says so.

Technique source: register allocation, linear scan (slice 06 §3, 12a).

### D3. THE GATE: never arm the wipe until the incoming theme's tiles are resident

**This is the rule Icecap Zone breaks (R-2), and the one Batman & Robin and Alien Soldier follow (R-3).**
08-08 §4 item 5 already had the principle (*"art rows of theme N+1 may not enter view before both have
fired"*). This makes it an explicit gate on the wipe, since step 6 now exists and assumes its tiles are
already resident (slice 06, Q5).

The crossing sequence:

1. **Preload.** When the camera enters a preload trigger ahead of the crossing, queue the incoming
   theme's tile pages into its colour's range through the existing page-in queue. A trigger placed from
   the region graph ahead of the edge beats a velocity model here, because themes change only at
   discrete region edges (slice 06 §3, item 10).
2. **Resident.** All of the theme's pages have landed. **A single "theme resident" flag**, the aeon
   counterpart of Hydrocity's `Kos_modules_left` (which Icecap didn't check) and Alien Soldier's
   load-finished gate.
3. **Arm only if resident.** The step-6 wipe arms on the crossing **only** when the incoming theme is
   resident.
4. **If it isn't resident yet, hold the camera.** Aeon already does this for the foreground:
   `Cache_Art_Stall` plus `CLAMP_MARGIN_TILES` hold the camera back when a foreground page is missing
   (slice 06, Q1). **Reuse that behaviour rather than inventing a second one.** A properly sized corridor
   (D4) makes the hold rare.
5. **Wipe.** 64 rows, 4 a frame, 16 frames.
6. **Release.** When the wipe completes, the outgoing theme's colour range is free for the next preload.

### D4. The corridor's length is derived, not authored

From slice 05 and R-2: **corridor length ≥ top speed × (decode frames + upload frames).**

- **Store theme pages raw, not ZX0, so decode frames are zero.** Raw pages skip decoding and go straight
  from ROM by DMA (slice 06, `page_in.emp:288`). That removes the exact bottleneck Icecap hit. The cost
  is ROM size.
- **Upload frames** follow from the theme's size and the art budget. A 168-tile background is 5376 B,
  about 2 frames at 4096 B/frame. (INFERRED; the art budget is shared with the foreground.)
- **The build computes the minimum corridor for each crossing and refuses a layout whose corridor is too
  short**, naming the crossing.

This corridor is a **space constraint, not a mechanism**. Treasure and Batman & Robin both treat it that
way: the corridor is level design the engine checks (R-4).

### D5. Palette handover (open, see OC-1)

The foreground and background **share CRAM lines 1-3**, so a zone's palette change hits both planes at
once (slice 06, Q4). The step-6 wipe **snaps the palette on frame 0**, so old art is visible under the
new palette until its rows are repainted (slice 06, Q5). Across a zone boundary the whole foreground is
affected too, not just the background, so this will look worse than it does within a zone today.

Candidates, not chosen: snap at wipe arm (today's behaviour); fade over 16 frames in lockstep with the
16-frame wipe (the fade machinery exists: `PAL_FADE_FRAMES` = 16); or make the corridor's own art use
only colours shared by both zones. **This is a look call.** See OC-1.

### D6. The foreground is a separate track, and the bigger one

This design covers the **background**. The showcase also needs the **foreground** to stream across a
zone seam, and that's where the budget pressure is (R-6):

- One Sonic 2 zone's art (604-965 tiles) is about the size of the whole 768-tile foreground pool.
- **OJZ act 1 has never actually streamed.** It's fully resident, and eviction only happens under the
  `STRESS_EVICT` fixture (slice 06, Q1).
- Whether both zones' pages fit the foreground cache's 80×60 window around a seam was not modelled.

**So foreground seam streaming is its own design item, and the held video-memory levers (regions part 2
steps 7 and 8) are its likely prerequisites.** Those stay held until this and the foreground design say
how video memory should be divided. Dividing it now for a single zone risks doing it twice.

---

## 4. Measurements owed before sizing, not guesses

**M-1. Background-only tile counts for the actual showcase zones. This blocks D2's sizing.**
Measured for four S3K acts only (R-6). **Not measured for any Sonic 2 zone**, and the showcase may be
Sonic 2. **D2 works only if each showcase theme is ≤ 188 tiles.** Measuring it needs S2's tile sets split
between planes, which needs layout and chunk parsing. This is the real-level test the owner asked for.

**M-2. Foreground seam fit.** Whether both zones' foreground pages fit the cache window at a seam (D6).

**M-3. Whether Icecap's wrong gate really causes its lag.** INFERRED today. It needs a running emulator.
It doesn't block the design, which gates on tiles either way, but it is the strongest cited precedent,
so it should be confirmed rather than assumed.

---

## 5. Owner calls

> **ANSWERED 2026-09-16T19:35:12Z by the owner, in session.** His words are quoted verbatim under each call; the
> original options are kept below them so the reasoning survives.

**OC-1 answered.** *"Maybe we can have an option to choose? I was thinking previously if we had sections have
different palettes, as you got half way through one it would start fading to the next. Maybe we should have a
fade to option or snap when switching option?"*
- **The snap-or-fade option already exists, per region**, verified in code: `ep_transition` on presets
  (`engine/effects/preset.emp:67`) and `pcfg_transition` on parallax configs (`engine/structs.emp:355`, *"0 =
  smooth lerp (default), 1 = instant snap"*). So a zone crossing chooses snap or fade the same way a region
  crossing does today. **No new option is needed for that part.**
- **NEW, and it is the better idea: a POSITION-driven fade.** Today's fade runs on a timer, `PAL_FADE_FRAMES` =
  16 (`engine/effects/palette.emp:307`). His idea ties fade progress to **how far through the crossing the
  camera is**, starting partway through the outgoing section. This fits a seamless showcase better than the
  timer, for two reasons (INFERRED, to test):
  1. **It reverses.** A timed fade finishes even if the player walks back out, leaving the wrong palette. A
     position-driven fade un-fades as you retreat.
  2. **It makes the corridor and the fade the same distance**, which answers much of OC-2 at the same time.
  **Booked as design item D5a** (below). Not designed yet.

**OC-2 answered.** *"Idk that shoul dddepend no?"* — **the corridor is authored per crossing, not fixed by
the engine.** The engine's part stays D4: it computes and **enforces the minimum length**, and refuses a
corridor that is too short. What it looks like is content, decided zone by zone.

**OC-3 answered, conditionally.** *"Maybe hold, I guess we should see how long it is."* — **hold the camera
if the art is late, pending a measurement of how long the hold actually is.** Booked as **M-4** below. If
it turns out long enough to feel bad, this reopens.

**OC-4 answered.** *"Part of regions."* — **this is part of the regions project, not its own.** The hub has
been told, so it can update the project record.

---

### D5a. Position-driven palette fade across a crossing (the owner's idea, booked, not designed)

Blend the outgoing and incoming palettes by the camera's progress through a crossing span, instead of over a
fixed number of frames. **Open questions for its own design:** which axis drives progress when a crossing can
be entered from the side or from above (the same entry-side problem step 6 had to solve for the wipe); how
it composes with the existing cycle, operator and variant stages of `Palette_Compose`; and how it lines up
with the 16-frame wipe when the camera stops mid-crossing. **The existing per-region snap/fade option should
stay alongside it**, as a third choice rather than a replacement.

### M-4. How long the camera hold actually lasts (from OC-3)

Measure the frames between reaching a crossing and the incoming theme becoming resident, at top speed, with
raw-form theme pages and the foreground's own art traffic competing for the same budget. An emulator
measurement, not a derivation. It decides whether OC-3's hold stands.

---

*The calls as originally put, kept for the reasoning:*

**OC-1. Palette at a zone crossing.** Snap, 16-frame fade in lockstep with the wipe, or a corridor
authored in colours both zones share? A look call. **Leaning: the lockstep fade**, because it reuses
existing machinery and matches the wipe's duration. It still needs his eye on a running ROM.

**OC-2. What the corridor looks like.** Every shipped precedent hides the swap behind something: the
AIZ fire, a fully covering arena, the Icecap tunnel, a Batman & Robin blank plane. A seamless showcase
needs a **designed** stretch between zones. That's content and level design, not engine work.

**OC-3. If the preload hasn't landed by the crossing.** Hold the camera (reusing the foreground stall,
D3 step 4), or let it cross and show the old theme briefly. A feel call. **Leaning: hold**, because it is
the existing behaviour and never shows wrong art. A well-sized corridor should make the hold rare.

**OC-4. Its own project, or part of regions?** Nothing is blocked on this. The hub flagged the draft as
the natural moment to ask.

---

## 6. Explicitly not taken

- **Per-word background translation and refcounting (the foreground's method).** It needs an 8192 B
  Plane B RAM shadow that 08-08 already ruled out, plus a per-word patch on every wipe row (R-8).
- **Runtime tile rebasing (Alien Soldier's technique).** Alien Soldier rebases block tables at load time.
  Aeon's backgrounds are baked nametables, not block tables, so rebasing would mean a translation pass
  at the same cost as the item above (slice 03, T3).
- **Build-time dedup as the fix.** Real zones share 0.1-0.3% of tiles (R-7).
- **Locking the camera at every crossing (S3K's same-zone method).** That defeats "seamless". Allowed
  only as the fallback hold when a preload is late (D3 step 4).
- **Display-off or letterbox for extra bandwidth.** Bandwidth isn't the constraint (R-1), and it's
  visible.
- **Hidden-first wipe order (08-08 §4 item 3(c)).** Superseded by step 6's measured reason (§1).

---

## 7. Proposed order, for after owner review and the lens audit

1. **M-1.** Measure background-only tile counts for the candidate showcase zones. If any exceeds 188,
   D2's two-colour sizing fails and this design changes before anything is built.
2. **D2 tool half.** The colouring and capacity proof in the build, no engine change. It can land and
   refuse bad layouts before the runtime exists.
3. **D3 and D4 engine half.** Theme preload, the resident flag, gating the wipe arm, the camera hold, raw
   theme pages, and the corridor check.
4. **D5**, once OC-1 is ruled.
5. **D6**, the foreground seam, as its own design, with steps 7 and 8 re-evaluated there.

**Folded in:** the hub's `AEON-VRAM-RESIDENCY-AUDIT` (what is resident and what streams, D1 and D6) and
`AEON-REAL-LEVEL-TEST` (M-1 on real zones). Both are the owner's existing requests, answered inside this
design rather than as separate items.

---

## 8. Doc corrections this work surfaced (booked, not yet made)

- **`docs/ENGINE_ARCHITECTURE.md` ~1738** says the background block is 448 tiles, OJZ uses ~340, and
  cites `constants.asm`. The constant is **376** (`constants.emp:648`), the shipped background is **320**
  tiles, and the file is `constants.emp`. It also says the engine doesn't read the constant, but
  `bg.emp:157` clamps on it. (Slices 02, 06.)
- **08-08 itself** uses 448 throughout, so its half-pool is 224 instead of 188.
- Further doc/code disagreements are listed in slice 06 §6.
