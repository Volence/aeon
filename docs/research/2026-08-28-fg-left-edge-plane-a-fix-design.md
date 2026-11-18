# The foreground left-edge strip: the width, the option set, and the parcel

> **⚠ SUPERSEDED — read this first (correction added 2026-11-17).** The recommendation here (a 16-px sprite strip, the six scenes flipping to `SpriteMask`) never shipped. The owner was offered the bar under d-40 and rejected it. Master instead shipped the column-19 VSRAM borrow, the option §2.9 rejects as "not a fix" (d-41, `def98ee5`), and later made it per scene (d-50, `9de3c757`). See `docs/research/2026-08-29-vsram-column19-borrow.md` and the closed booking in `DEFERRED_WORK.md`. Don't read §0 ("nothing cheaper covers it") or §2.9 as current. §5.2 step 1's plane-A guard already landed (`67e2c51a`). What still holds: the width is `HScroll & 15`, so any future cover must be 16 px, not 8. The "Sonic 3 Hydrocity" precedent is false (checked in skdisasm; it still appears at `engine/level/scene_dsl.emp:665`). Caveat on §1.5 and TAG 1: the 2026-08-27 measurement ran on Oracle, which always draws the partial column 16 px wide (divergence P4). It cannot confirm the 13-px reading, and TAG 1 run on Oracle would show a constant 16 that does not disprove §1.2.

**2026-08-28, branch `design/fg-left-edge-planea`. DESIGN ONLY — no engine code, no scene
data, no byte moved by this parcel.** Every line number below was re-derived from the tree at
this branch's base; every sigil claim names the revision it was read at. This lane has no
emulator, so nothing here is a runtime measurement — the runtime questions are TAGs in §7.

Predecessors, superseded by neither:
- `docs/research/2026-08-27-fg-left-edge-reproduction.md` — the measured reproduction.
- `docs/research/2026-08-28-deform-scene-left-edge-triage.md` — the triage that found the
  policy adjudicates the wrong plane.

---

## 0. Summary for the owner

The foreground left edge breaks on the six per-column scenes because the VDP renders a sliver
at the left of the screen at a vertical scroll the program never wrote. The engine's arithmetic
is right; the hardware is doing this; six scenes turn the mode on and declare "ship it".

**Recommendation: cover it with an opaque sprite strip, 16 pixels wide, full screen height —
and the strip's specification in the tree today is wrong in three ways, each of which would
have shipped the bug.** It says 8 px (**half** the width the hardware documentation gives). The
policy that authorises it never looks at the plane the owner is looking at. And one of the two
precedents it cites for the mechanism turns out not to exist.

**What the owner will see:** an opaque 16-pixel bar down the left edge — 5% of the screen
width, static, at the very edge — and *only* while one of the six scenes is live. That is what
Battle Mania 2 did, and it is what every sourced precedent does. Nothing cheaper covers it: the
two register tricks (left-column blank, Window plane) are each ruled out below on hardware and
VRAM grounds, from sources, not from taste.

**The build cost is small, and smaller than the tree says.** One aeon parcel plus a one-file
sigil test change — the "sigil port flip" blocker is **stale**, because the harness helper that
unblocks it already exists at sigil `b73bf420`. 4 tiles of VRAM, which fit an existing
`[[free]]` run without re-planning the VRAM map. 14 of 77 spare sprite-table entries. **Zero
extra cost on the ceiling the sprite budget actually gates on.**

---

## 1. The width, derived

### 1.1 The two things that set it

**Hardware grain.** With VDP reg `$0B` bit 2 set, vertical scroll is per *column pair* — one
VSRAM entry per 16 screen pixels. In H40 that is 320/16 = **20 entries**, which is exactly the
20 longwords `Vscroll_Write` emits (`engine/level/parallax.emp:806-825`) and the 20 column-pairs
Step 5b fills (`parallax.emp:1640`, `moveq #20-1, d6`). The engine's own loop bounds witness
the grain.

**The scroll expression.** Both per-column families author `fa: FACTOR_1` on every real layer
(`games/sonic4/data/effects/ojz_scenes.emp:334` for Rocking; `:378-382` for Perspective — five
layers, all `fa: FACTOR_1`). `FACTOR_1 = packed(s1: 0, s2: 15, op: 0)`
(`engine/level/parallax_dsl.emp:27`). `Decode_Factor_A` (`parallax.emp:1665-1694`) with `s1 = 0`
computes `d2 = camX >> 0`, sees `s2 == 15`, branches straight to `.negate`, and returns
**`-camX`**. Plane A's HScroll register value is `-camX` at every camera position.

### 1.2 The derivation

Let `H` be the HScroll value written for a plane. A HScroll value `v` shifts the plane right by
`v`, so screen pixel `x` shows plane pixel `x - v`. With `v = -camX`, screen `x` shows plane
pixel `x + camX`.

The VDP fetches and V-scrolls plane data in whole 16-px column units aligned to the *plane*.
The first plane-aligned 16-px boundary at or after screen `x = 0` sits at

```
    x + camX ≡ 0  (mod 16)      →      x ≡ -camX  (mod 16)
```

so the first fully-aligned column starts at screen `x = (-camX) mod 16`. Everything left of it
is the **partial column** — the sliver the hardware cannot give a correct V-scroll to.

```
    w(camX)  =  (-camX) mod 16   =   H & 15      ∈  { 0, 1, 2, …, 15 }
```

**Range: 0 to 15 pixels, sweeping every value as the camera crosses 16 pixels.** `w = 0`
exactly once in every 16 camera positions — the one position where nothing is wrong. `w = 15`
one position later.

### 1.3 The derivation is confirmed by hardware documentation, not just by this doc

The `H & 15` form is exactly what plutiedev's hardware-issues page states, and it names the
width in words:

> "The behavior of column -1's vertical scroll (**the up to 15px to the left that you're
> supposed to hide**) has also changed, being garbage in earlier hardware and a copy of column 0
> in later hardware."
> — <https://plutiedev.com/hardware-issues>

Independently, the Genesis Plus GX renderer draws the partial column into its line buffer at
offset `0x10 + shift` while the visible area begins at `0x20`, so exactly `shift = xscroll & $0F`
pixels of it are visible (`core/vdp_render.c`, `render_bg_m5_vs` family). The mechanism behind
it, from Mask of Destiny on SpritesMind (thread 1341):

> "The VDP renders 2 extra columns before the first column of the display. If the low 4-bits of
> the horizontal scroll value are zero, these extra columns are completely unused."

**So `w = H & 15`, 0..15, is sourced twice over and matches the engine's own banner's prose**
(`parallax.emp:770-774`: "the screen sliver before HScroll's first 16-px boundary"). It is not a
model this lane invented.

### 1.4 What that means for a cover

A sprite is positioned in pixels but sized in whole 8-px cells. The affected pixel set is
always a subset of `x ∈ [0, 14]`, so:

| cover width | camera positions it is CORRECT at (of 16) | worst uncovered |
|---|---|---|
| 8 px (1 cell) — **the spec in the tree today** | 9 (`w = 0…8`) | 7 px |
| **16 px (2 cells)** | **16 — all of them** | 0 px |

**An 8-px strip is wrong at 7 of every 16 camera columns.** `camX` advances continuously during
play, so "7 of every 16" is not a residual — it is the owner's exact symptom, flickering on and
off several times a second at a walking pace and faster at speed. A gate built against the 8-px
spec would have measured a covered strip at one camera position and passed.

16 px is the smallest cover that is correct everywhere, and — usefully — it is also plutiedev's
independent "safe margins" figure for the sides of an MD screen, so it costs nothing that a
careful layout was not already conceding.

### 1.5 The derivation reproduces the measurement, and corrects how it was read

The 2026-08-27 A/B was taken at `Camera_X = 195`. `195 mod 16 = 3`, so `w = (-195) mod 16 = 13`:
pixels `x ∈ [0,12]` are wrong. The probe samples cell-left pixels `x = 0, 8, 16, …`.
`x = 0` ∈ [0,12] — wrong. `x = 8` ∈ [0,12] — wrong. `x = 16` ∉ [0,12] — correct. **That is
exactly the measured table** (x=0 and x=8 transparent across every ground row, x=16 onward
carrying the band).

The triage read that table as "the artifact is 16 px". **It is not: at that camera position it
is 13 px, and it merely rounds up to two sampled cells.** The distinction is the whole point of
this section — the triage's 16 is a coincidence of one camera position and an 8-px sampling
grid; the derived 16 is a bound over all camera positions. Same number today, and only one of
them is still true tomorrow.

### 1.6 A value claim in the engine banner that the research contradicts

`Vscroll_Write`'s banner (`parallax.emp:770-773`) and the `SceneLeftColMask` banner
(`scene_dsl.emp:360-364`) both say the partial column "renders at V-scroll = 0 regardless of
VSRAM[0]". **No source supports the specific value 0, and the best-sourced model disagrees.**
Genesis Plus GX, hardware-verified on a PAL MD2 by its author, models the H40 case as

```c
/* Left-most column vertical scrolling when partially shown horizontally (verified on PAL MD2) */
if (reg[12] & 1) { yscroll = vs[19] & (vs[19] >> 16); }
```

— the **bitwise AND of the last VSRAM entry's plane-A and plane-B words**, applied to *both*
planes; and in H32 the partial column's vertical scroll is disabled outright. plutiedev's
account differs again ("garbage in earlier hardware and a copy of column 0 in later hardware"),
and both sources agree the behaviour is **revision-dependent**.

This changes nothing about the fix — an opaque cover covers whatever was fetched, which
`DEFERRED_WORK`'s mechanism ruling already says. It matters for two other reasons: the banner
states an unsourced specific value as fact, and **nothing in the design may depend on the
value** — only on the fact that the region is wrong and at most 15 px wide. Both banners should
be corrected to say "a V-scroll the program never wrote (revision-dependent; do not depend on
the value)" rather than "0".

### 1.7 Why plane A, and why the policy could not see it

Both planes suffer this independently, each by its own HScroll. For these six scenes:

- **Plane B**: every layer is `fb: FACTOR_0` (`ojz_scenes.emp:334`, `:378-382`), so base HScroll
  is 0 and `w_B = 0`. Perspective's live `dsb` shimmer re-adds per-line plane-B HScroll on the
  hills/ground rows, so `w_B` is non-zero *there* — the Accept its banner spells honestly at
  `ojz_scenes.emp:365-371`.
- **Plane A**: `fa: FACTOR_1` → HScroll `-camX` → `w_A = (-camX) mod 16`, non-zero at 15 of
  every 16 camera positions.

The `left_column_mask` guard family in `engine/level/scene_dsl.emp` scans `l.ly_fb` (`:1325`),
`l.ly_dsb` (`:1344`) and the anchor's `dsb` (`:1349`). **`ly_fa` and `ly_dsa` appear nowhere in
the guard block** (`:1296-1377`, read in full). The brief's claim is confirmed: the policy
adjudicates plane B; the owner is watching plane A.

That is worse than a stale comment. `Factor0Lock` is presented as a *verified* claim that "the
artifact CANNOT OCCUR" (`scene_dsl.emp:398`). A scene authored `fa: FACTOR_1, fb: FACTOR_0,
dsb: 15` would pass both halves of the verification, ship a foreground artifact, and carry a
build-checked declaration saying it cannot exist. **The guard is not conservative in the wrong
direction; it is unsound.**

---

## 2. The option set

Research checklist run in full — the reference disassemblies, plutiedev / md.railgun.works /
Kabuto's notes / SpritesMind / Charles MacDonald's genvdp.txt / Genesis Plus GX source /
rasterscroll, and the repo's own constraints. Where a source could not settle a question it says
so rather than guessing.

### 2.0 A precedent in the repo's own banners is WRONG, and it should not survive this parcel

`scene_dsl.emp:371-372`, `parallax.emp`'s banner and the `DEFERRED_WORK` booking all cite
**"Battle Mania 2, Sonic 3's Hydrocity boss arena"** as the two games that covered this with a
sprite strip.

- **Battle Mania 2 — VERIFIED.** rasterscroll's row/column-scrolling page, on the Trouble
  Shooter Vintage capture: *"This is a layer of sprites hiding the first column due to the VDP's
  column scrolling bug."*
- **Sonic 3's Hydrocity — REFUTED, checked in `skdisasm` directly by two independent research
  lanes that did not see each other's work.** S3K writes VDP register `$0B` with exactly three
  values — `$8B00`, `$8B03`, `$8B07` — and only `$8B07` sets bit 2. Its enable sites are the
  **AIZ1→AIZ2 transition (`sonic3k.asm:104639`), the MGZ2 collapse (`:106513`), an LBZ1 event
  (`:110986`), SSZ1 (`:115959`), SSZ2 (`:117774`) and `:119524`** — all set-pieces. Hydrocity is
  not among them; it runs `$8B03`, full-screen vscroll, and the only HCZ arena code in the tree
  is the camera-bounds/palette `HCZ1_Resize`/`HCZ2_Resize` handlers, which touch nothing near the
  left column. Separately, S3K writes register `$00` only as `$8004` / `$8014` — **bit 5 is never
  set anywhere in the game.** So S3K neither uses 2-cell vscroll in Hydrocity nor uses the
  left-column-blank bit at all.
- **Gynoug — VERIFIED as the ship-it precedent** (rasterscroll's caption; and Eke-Eke's
  Everdrive hardware test on SpritesMind t=737 confirms Gynoug's left column is dismissed).

A citation that does not survive a check is worse than no citation, because it is what a reader
reaches for when deciding whether the mechanism is real. **The Hydrocity claim must be deleted
from all three places, not quietly left.** The mechanism is still well-precedented — rasterscroll
states the general practice flatly: *"When column scrolling is combined with most forms of
horizontal scrolling, the first column will show garbage tiles, so developers typically hid it
using sprites."*

### 2.1 Opaque sprite strip, plane A, 16 px — **RECOMMENDED**

The mechanism `SceneLeftColMask.SpriteMask` names, with the width corrected. Opaque sprites at
SAT X = 128 (screen X 0), priority bit set, first in the SAT link chain. It is the only option
that covers the derived width without taking something else away, and it is the sourced
precedent (§2.0). Pricing in §3.

### 2.2 VDP register `#0` bit 5 — the left-column-blank bit — **DIES TWICE**

Bit 5 of VDP reg `$00` blanks the leftmost **8 pixels** to the backdrop colour (plutiedev's
register reference: *"1 to blank the leftmost column (8px wide)"*). Aeon boots with
reg `$00 = $04` (`engine/system/boot_data.emp:137`) — bit 5 clear.

**Death 1 — the width.** It blanks 8 px; §1 needs up to 15. It is wrong at the same 7 of every
16 camera positions the 8-px sprite strip is wrong at, and unlike the sprite strip it *cannot*
be widened: the width is fixed in silicon. It fails on exactly the derivation that kills the
8-px spec. No source claims it is used for this; every sourced precedent uses sprites, and this
arithmetic is why.

**Death 2 — it blanks sprites too, so it cannot be combined with the strip.** Genesis Plus GX
applies the blank *after* both `render_bg` and `render_obj`, overwriting sprite pixels; and
Charles MacDonald's hardware account of the line-buffer erase (SpritesMind p=17583) only makes
sense if LCB suppresses the sprite readout. **LCB would eat the left 8 px of the masking sprite
strip.** The two mitigations do not compose.

**The one combination that would work, and why it is still rejected.** Quantise plane A's
HScroll to a multiple of 8 while bit 2 is set. Then `w ∈ {0, 8}` — the artifact is either absent
or exactly the 8 px LCB blanks. That is a *complete* fix costing zero sprites, zero VRAM and
zero per-frame CPU (one shadowed register bit toggled with the scene). Its price is
8-px-quantised foreground horizontal scrolling on those six scenes. **Rejected: on a Sonic
foreground that is visible judder at any speed below a run** — the same class of cost §2.4
rejects, only halved. Recorded because it is the cheapest complete fix in the set, and a future
*non-scrolling* per-column scene should reach for it rather than buy a sprite strip.

**One caveat on bit 5 itself, recorded because it is the weakest link in the research.**
Charles MacDonald's *genvdp.txt v1.5f* lists reg `$00` bit 5 as **"No effect"** on the Genesis.
That is a 2000-era pre-hardware-testing document; plutiedev and Genesis Plus GX both treat the
bit as functional. Since neither option here depends on bit 5, nothing in this design rests on
resolving it — but anything that later does must verify it first.

### 2.3 Window plane over the leftmost columns — **DIES ON VRAM, and carries its own bug**

Geometrically it looks near-perfect, and two of the three properties check out:

- **Granularity is exactly 16 px.** plutiedev's register reference on `$91xx`: *"X coordinate of
  split (in 16px steps)"*; genvdp.txt: *"The WHP field defines the horizontal range of the
  window, in units of two cells. (16 pixels)."* Exactly the derived width.
- **The window does not scroll** (genvdp.txt: it is *"a 'replacement' for plane A"*; rasterscroll
  states it flatly), and it is **immune to this artifact** — in Genesis Plus GX's `render_bg_m5_vs`
  the window branch has no `yscroll` term and no partial-column path at all, and its destination
  is cell-aligned to the visible origin.
- A 16 px × 28 row window is 56 nametable entries all pointing at one solid tile: **1 tile of
  VRAM, zero sprites, zero per-frame CPU.** On paper it beats the sprite strip on every axis.

**It is dead anyway, and the reason is written in the engine's own boot table**
(`engine/system/boot_data.emp:138-145`, verbatim):

> `$03`: Window nametable at `$F000`. CONSTRAINT, not a free choice: with 64x64 planes
> (reg `$10` = `$11`) Plane B at `$E000` spans `$E000-$FFFF`, so `$F000` lies INSIDE Plane B.
> Harmless today — the window is disabled (regs `$11`/`$12` = 0), so the VDP never fetches from
> it — but there is **NO free window space anywhere in this VRAM map**. Enabling the window
> means first re-planning the VRAM layout, not just writing `$11`/`$12`.

Enabling the window means finding a window nametable's worth of contiguous VRAM in a map that
declares full coverage of tiles 0..2047 and whose largest `[[free]]` run is **4 tiles = 128
bytes** (`games/sonic4/vram.toml`). The 64×64 planes are what the engine's vertical-transition
and VSRAM design rests on. **Trading the plane geometry for a left-edge cover inverts the cost
of the thing being fixed.**

**And the window carries a second, sourced left-edge bug of its own** — which would have killed
it even with free VRAM. md.railgun.works' VDP page:

> "There is a bug that causes incorrect tiles to be fetched if RGHT=0 and the horizontal scroll
> offset is not a multiple of 16"

`RGHT=0` is precisely a left-aligned window, and "hscroll not a multiple of 16" is precisely
this scene's condition. Genesis Plus GX carries a distinct `/* Window bug */` branch for it. So
a 16-px left window would replace a ≤15-px artifact at `x ∈ [0,14]` with a plane-A tile-fetch
artifact immediately to its right. **A strictly worse trade, on top of a VRAM cost that is not
payable.**

### 2.4 Quantise plane A's HScroll to a multiple of 16 — **RE-DERIVED, and the rejection HOLDS**

The triage rejected this. Re-derived here rather than inherited, because the triage's reasoning
was about plane B's V-scroll uniformity and the real argument is simpler.

From §1.2, `w = 0` exactly when `camX ≡ 0 (mod 16)`. Forcing the HScroll write to `-(camX & ~15)`
makes `w = 0` at every camera position, so the artifact vanishes completely, at zero cost in
sprites, VRAM, SAT slots or bandwidth. **It is a real, complete, free fix — and its price is the
foreground scrolling in 16-px jumps.**

**Rejected, and not because it costs something: because it is a worse bug.** A foreground that
advances in 16-px steps while the player moves smoothly is more prominent than a 16-px strip at
the screen edge — it is in the centre of the frame, it is in motion, and it desynchronises the
foreground from the player sprite (which still moves per pixel), which reads as the player
sliding. The artifact being fixed is static, peripheral, and 5% of the width. **The rejection
holds, now on a stated comparison rather than an assertion.**

One variant, named so nobody re-derives it: quantising and compensating elsewhere is not
available. The residual `camX & 15` is exactly what creates the partial column, and there is no
second knob to absorb it. The per-line HScroll table the engine does have (224 longwords) varies
HScroll *per line*, while the partial column is a *per-column* geometry — using it would make `w`
vary per line, turning a clean 13-px bar into a ragged edge.

### 2.5 Swap the planes — FG on B, BG on A — **RECORDED, NOT PROPOSED**

The artifact hurts because it lands on the plane carrying the ground band. `d-27` authorised
"eight pixels on the background", which is the same silicon on the plane where nobody looks. If
the foreground were on plane B (HScroll locked to 0 by these scenes) and the background on plane
A, the artifact would move to the background and `d-27` would apply unchanged.

**Not proposed.** Plane A is the foreground in every plane buffer, section stream, tile-cache
target, VRAM constant and collision contract in the engine. This is recorded because it answers
"why does this hurt so much more than the card said" — the card was written about the other
plane — not because it is a candidate.

### 2.6 Lock plane A's HScroll too (`fa: FACTOR_0`) — **RECORDED for static scenes**

With `fa: FACTOR_0` the artifact cannot occur on either plane, `Factor0Lock` becomes truthful
once the guard learns to check plane A (§6), and the cost is zero. The price is that the
foreground does not scroll horizontally at all. Useless for a playable scene; **correct for a
static one** — the M.U.S.H.A. answer (rasterscroll: *"does not have a black bar on the left
column because there is no horizontal scrolling on that stage, so the bug does not appear"*).
Worth naming in the guard's error message so a future author of a non-scrolling per-column scene
finds the free answer instead of buying a sprite strip.

### 2.7 Delete the effect — **the honest floor**

Per-column V-scroll is the only way to get a per-column vertical wobble; there is no cheaper
spelling of Rocking/Perspective. Recorded so "just don't do it" is a weighed option rather than
an unspoken one. The owner asked for the artifact fixed, not the effect removed, so this is the
floor and not the answer.

### 2.8 What the eight reference disassemblies ACTUALLY do — swept, and it reframes the menu

The full sweep (S.C.E., Batman & Robin, Vectorman, Gunstar Heroes, Alien Soldier, Thunder Force
IV, Ristar, sonic_hack, plus stock S2 and S3K) returns a blunt headline:

**None of the ten trees sets VDP reg `$00` bit 5. None parks a sprite strip at screen X 0. None
enables a left-aligned window.** Every reg-`$00` write in every tree is `$8004`/`$8014`; every
reg `$11` write is `$9100` (window disabled) except S.C.E.'s debug raster aid, which is
*right*-aligned, and S3K's LBZ2 Death Egg platform, which uses the window **vertically**
(`$9285`). Vectorman's and Thunder Force IV's generic window-H setters actively *reject*
left-aligned values above `$1F`, and TF4's has no caller at all.

So the sprite strip's precedent rests entirely on Battle Mania 2 (rasterscroll, §2.0) and on
rasterscroll's general statement of the practice — **it is not corroborated anywhere in this
repo's own reference corpus.** That does not make it wrong; it makes the citation thin, and the
banner should stop implying two games when it has one.

**What the corpus does instead, and both are worth knowing:**

- **S3K locks the camera.** Every one of its six per-column-vscroll events sets `Scroll_lock`
  immediately before enabling the mode — `sonic3k.asm:115957` (`st (Scroll_lock).w`) before
  `:115959` for SSZ1, `:117735` before `:117774` for SSZ2, `:111479`/`:111555` for LBZ2,
  `:104905` for the AIZ transition. **S3K does not fix the artifact; it stops it moving.** With
  `camX` frozen, `w` is a constant, and a static 13-px oddity at the screen edge during a
  collapse set-piece is invisible. Its arenas are 10 columns wide at a hardcoded X
  (`:106460-106513`, `:111000-111040`). **This is unavailable to us**: our six scenes are live
  during ordinary play with the player driving the camera, which is exactly why the artifact is
  a flicker here and was never one in S3K.
- **S.C.E. rounds the camera X *up* to the next 16-px boundary** before the column walk
  (`Engine/Core/Deformation Script.asm:713-724`: `andi.w #16-1,d2 / beq.s .check_column /
  addi.w #16,d0 / lsr.w #4,d0`). This looked like the deliberate left-edge fix in the corpus, so
  it was chased down. **It is not one, and it is not applicable.** It changes which *deform
  sample* each VSRAM entry receives so the columns align to the world grid; it does not touch
  HScroll and cannot affect the partial column, which ignores `VSRAM[0]` regardless. It is also
  dead code — `Apply_FGVScroll`/`Apply_BGVScroll` have no callers in that tree. Recorded so the
  next reader who finds it does not mistake it for the answer.

### 2.9 Feed the entry the partial column actually reads — **REJECTED on revision-dependence,
but it is the one that will tempt the next reader**

Two shipped games write **21** column pairs into a 40-word (20-pair) VSRAM:

- **Ristar**, in its H-int chain (`ristar_disasm/code/disasm.asm:14580-14592`): `move.w #$14,d1`
  driving a `dbra`, i.e. 21 iterations of two words = 42 words, into `$40000010` (VSRAM 0). Its
  VBlank path by contrast DMAs exactly `$0028` = 40 words (`:16453-16456`).
- **Batman & Robin** (`disasm/code/effects/effects.asm:8283-8284`): `move.w #$14, d7` over the
  same shape.

That is one entry past the last, on the exact hardware feature under discussion, in two
independent 1994 codebases. Put beside Genesis Plus GX's model that the H40 partial column reads
**`VSRAM[19]`** (§1.6), it suggests a free fix: **plane A's V-scroll is uniform (`camY` in all
twenty entries, `parallax.emp:1645`), so `VSRAM[19]`'s plane-A word is already the value the
sliver needs** — and if the entry the partial column samples could be steered, plane A's sliver
would simply be correct, at zero sprites, zero VRAM and zero pixels.

**Rejected, and the reason is the one this document sets for itself in §1.6: nothing may depend
on the fill value.** Under GPGX's PAL-MD2 model the sampled value is
`VSRAM[19].planeA & VSRAM[19].planeB` — an AND of the two planes' words, applied to *both*
planes, so making it right for plane A means bending plane B's column-19 wobble to match. Under
plutiedev's account of other revisions it is "garbage in earlier hardware and a copy of column 0
in later hardware" — a different mechanism entirely, on which the trick does nothing. **A fix
that is correct on one silicon revision and silently wrong on another is not a fix**, and this
one would fail *invisibly* rather than loudly.

Recorded in full because it is clever, because two shipped games gesture at it, and because a
future reader who finds those `#$14`s will otherwise re-derive it from scratch and not know why
it was passed over. If anyone ever does want it, TAG 4 is the measurement it needs first.

### 2.10 What the brief's option set was missing

The brief's list (sprite strip / bit 5 / window / quantise) is **complete on the mechanisms it
names**, but the research added five things it did not have, all above:

1. the **bit-5-plus-8-px-quantise combination** (§2.2) — the cheapest *complete* fix in the set,
   rejected only on scroll smoothness;
2. **LCB and a sprite strip cannot be combined at all** (§2.2, death 2) — a tempting
   belt-and-braces move that is in fact self-defeating, since LCB blanks sprites too;
3. the **`fa: FACTOR_0` free answer for static scenes** (§2.6);
4. **camera lock**, S3K's actual shipped answer (§2.8) — unavailable to us, and the reason this
   artifact is a flicker here and was never one in S3K;
5. **feeding `VSRAM[19]`** (§2.9) — the clever one, rejected on revision-dependence.

Plus three corrections to the tree's own record: the refuted Hydrocity precedent (§2.0), the
unsourced "V-scroll = 0" value claim (§1.6), and the 8-px width (§1.4).

---

## 3. The real price of the recommended option

### 3.1 The geometry is NOT the one in the tree, and the reason is VRAM

`tools/effects_budget_model.toml:167-176` prices the strip off `InsertSpriteMasks`' shipped
geometry — `SPRITE_MASK_SIZE = %00000011` (1×4 cells = 8×32 px) and `SPRITE_MASK_HEIGHT = 32`
(`engine/objects/sprites.emp:26-27`) — giving `ceil(224/32) = 7` slots and 8 px/line.

**Two problems, and the first is a live gate defect.**

**(a) `SPRITE_MASK_*` belongs to a different mechanism, and the gate that prices the strip is
measuring that mechanism instead.** `InsertSpriteMasks` (`sprites.emp:827-901`) writes
**transparent tile 0 at SAT X = 0** — the VDP's X=0 sprite-*masking* feature, which suppresses
later sprites and repaints no plane pixel. `DEFERRED_WORK`'s ruling and `scene_dsl.emp:1376`
both say explicitly that this feature *cannot* serve the left-column job. So the budget model
prices the left-column strip using the constants of the one mechanism that provably cannot be
it, and `check_axis5_mask_pricing()` (`tools/effects_budget_check.py:255-280`) re-derives the
toml rows from those same constants. **That gate would stay green while the strip is 16 px,
because it is not measuring the strip.**

Verified dormant: `grep SpriteMask_Y` over `engine/`, `games/` and `tools/` returns only its
declaration (`engine/ram.emp:647`) and its reader (`sprites.emp:854`) — **no writer anywhere**,
and `sprites.emp:490` skips the call when it is 0. The X=0 mask is shipped, byte-costing and
dead, and its geometry is free to disagree with the strip's. **The strip needs its own
constants, not a reuse.**

**(b) A 2-cell-wide × 4-cell-tall sprite needs 8 consecutive VRAM tiles, and there is no free
run of 8.** Sprite tiles are consecutive from the base, so a 16×32 strip sprite is 8 tiles =
256 B. `games/sonic4/vram.toml`'s `[[free]]` runs are **3, 4, 3, 4 tiles** (bases 957, 1020,
1501, 1532). Nothing fits. Widening a region would move `POOL_TILE_CEILING`, which moves RAM.

### 3.2 The geometry that fits: **2×2 cells (16×16 px), 14 stacked**

```
    size byte    = %00000101 = $05     (bits 2-3 = width-1  = 1 → 2 cells
                                        bits 0-1 = height-1 = 1 → 2 cells)
    VRAM         = 2 × 2 = 4 consecutive opaque tiles = 128 B
    SAT slots    = ceil(SB_SCREEN_LINES / 16) = ceil(224/16) = 14
    sprites/line = 1     (a vertically stacked non-overlapping strip intersects any
                          scanline exactly once — geometric, independent of height)
    pixels/line  = 16    (the derived width, §1.4)
```

**4 tiles fits the existing `[[free]] base = 1020, tiles = 4` run exactly.** No VRAM re-plan, no
`POOL_TILE_CEILING` move, no RAM churn.

The whole family of stackings costs the same on the binding ceiling and only trades slots
against VRAM, which is why 2×2 is the pick:

| geometry | VRAM tiles | SAT slots | sprites/line | pixels/line | fits a free run? |
|---|---|---|---|---|---|
| 2×4 (16×32) | 8 | 7 | 1 | 16 | **no** — largest free run is 4 |
| **2×2 (16×16)** | **4** | **14** | **1** | **16** | **yes** (base 1020) |
| 2×1 (16×8) | 2 | 28 | 1 | 16 | yes |
| two 1×4 columns sharing one tile base | 4 | 14 | **2** | 16 | yes, but doubles the binding cost |

### 3.3 Against the axis-5 reservation

Budgets from `tools/effects_budget_model.toml [engine_reservation]`, transcribed into
`engine/level/scene_dsl.emp:1901-1906`. Sprite limits confirmed against plutiedev's sprites page
(H40: 20 sprites/line, 320 sprite pixels/line, max sprite 4×4 cells) and genvdp.txt (80 total).

| sub-ceiling | pool | reserved | budget | strip today (8 px) | **strip at 16 px** | headroom used |
|---|---|---|---|---|---|---|
| per-line sprites — **the BINDING ceiling** | 20 | 2 | 18 | 1 | **1** | 5.6% — **unchanged** |
| per-line sprite pixels | 320 | 32 | 288 | 8 | **16** | 5.6% (was 2.8%) |
| SAT table slots | 80 | 3 | 77 | 7 | **14** | 18.2% (was 9.1%) |

**Widening the strip from 8 px to 16 px does not move the ceiling the axis gates on.** The
toml's own ruling (`axis5_binding_ceiling`, `axis5_task12_resolution`) is that the axis gates on
the per-line sprite count, "where the column strip costs exactly 1 sprite … REGARDLESS of how
many table entries build it". That reasoning is unchanged at 16 px: a vertically stacked strip
still intersects any scanline exactly once.

Two rows move, both stay well inside budget. The toml's 4-cell note (`:1201-1202`) prices the
unlock condition at "a strip wider than 288 px … is unreachable" — a 2-cell strip is 16 px
against a 288-px budget, nowhere near it. The 14-slot row is the one needing an open ruling:
**ACCEPT 14, openly**, the same shape as `axis5_task12_resolution`'s ACCEPT-7 — 18.2% of the
measured table headroom, on the sub-ceiling the axis explicitly does not gate on, in exchange
for the artifact actually being covered. Bounding the height buys nothing on the binding ceiling
and turns a policy into a partial cover, exactly as the ACCEPT-7 ruling said.

**The reservation is an upper bound on headroom** (`axis5_caveat`): measured on
`GameState_OJZScroll`, a near-empty scroll test. A populated level grows every row. At 1
sprite/line and 16 px/line the strip is robust to that; at 14 of 80 table slots it is worth
re-checking when a populated level is measured. Recorded, not hand-waved.

**One hardware detail that argues for the strip being FIRST in the chain, beyond priority.**
genvdp.txt: *"Sprites that are outside of the physical display area are still taken into
account"* — an off-screen sprite still burns a per-line slot, so the 20/line limit is reached
by object count, not by what is visible. First-in-chain is what exempts the strip from being
dropped on a busy line. That is TAG 3.

### 3.4 Everything else

- **DMA / VRAM bandwidth:** 4 tiles = 128 B uploaded once when the act loads (resident, like
  `ring_sparkle`). Not a per-frame cost.
- **Per-frame CPU:** 14 SAT entries × 8 bytes = 112 bytes into the SAT buffer per frame while a
  per-column scene is live, in a loop shaped like `InsertSpriteMasks` (`sprites.emp:857-899`).
  Order tens of microseconds. Zero when no per-column scene is installed (capability-gated).
- **RAM:** none new if the strip reuses the shape of the existing `SpriteMask_*` cells; a handful
  of bytes if it takes its own. Parcel call, not a blocker.
- **ROM:** the emitter, capability-gated, elided entirely in a game that does not raise the bit.

---

## 4. The blockers, re-verified

### 4.1 Blocker 1 — the sigil port flip — **STALE. A one-file test change, not a feature.**

The refusal at `scene_dsl.emp:1376` and the `DEFERRED_WORK` booking both say the emission is
"blocked on an aeon+sigil pair (the strip emitter needs `engine/objects/sprites.emp`'s FIRST
`Game.*`/`CAP_*` reference, a sigil port-flip)".

**The aeon half is confirmed:** `grep -c 'Game\.\|CAP_' engine/objects/sprites.emp` returns
**0**. A capability gate would be the module's first cross-seam reference.

**The sigil half no longer requires new machinery.** Read at **sigil `origin/master` =
`b73bf420e90ceade6e1c314502156828d8052c0e`** (2026-08-28), via `git -C ../sigil show
origin/master:<path>` — never through the sibling working tree:

- `crates/sigil-harness/src/test_support.rs:947` defines **`pub fn scanline_caps_contract_env(
  aeon: &Path) -> InterfaceEnv`**, which binds sonic4's *whole* `implement Game` contract at the
  canonical shape. Its own doc comment: the env "carries every other member too, so a second
  member one of them starts reading resolves instead of aborting the lower."
- It is **already used by four port tests**: `parallax_port.rs:353`, `buffers_port.rs:232`,
  `raster_port.rs:274`, `raster_negative_probes.rs:225`.
- `test_support.rs:900-908` also provides **`scene_dsl_cap_consts_src(aeon)`**, which synthesizes
  the `CAP_*` integer constants for a single-module oracle that cannot follow a
  `use engine.level.scene_dsl.{CAP_…}` edge.
- `crates/sigil-cli/tests/sprites_port.rs` lowers via single-module `lower_module`; the change is
  to route it through `lower_module_with_contracts` with those two helpers — exactly what
  `parallax_port.rs:344-358` already does.

**Revised assessment: still an aeon+sigil PAIR** (the sigil test must change in the same landing
or `sprites_port` goes red the moment sprites.emp names `Game.SCANLINE_CAPS`), **but the sigil
side is a few lines against two existing public helpers, not a port-flip needing new sigil
capability.** The booking's framing is what is stale, not the pairing.

Caveat this lane cannot discharge: `sprites_port.rs` is a **byte gate** against pinned reference
windows. A capability-gated block moves bytes in the `sprites` region, so the parcel is a
**byte-changing parcel** and owes the repin→refreeze `--ab` ritual in both shapes. A known cost,
not a surprise; named here so it is in the estimate.

### 4.2 Blocker 2 — the game-owned opaque tile — **STILL HOLDS, and now has a home**

Confirmed as stated: the engine cannot know a game's VRAM layout, so the opaque tile is a game
hook. What §3.2 adds is that the hook is now fully specified and free: **4 consecutive tiles of a
solid non-zero palette index, at `games/sonic4/vram.toml`'s existing `[[free]] base = 1020,
tiles = 4` run**, resident for the act. The natural shape is the one `DEFERRED_WORK` predicted —
`SceneLeftColMask.SpriteMask` grows an `art_tile`-word payload — with the tile generated at build
time rather than authored as art (32 bytes of a repeated nibble; a generator line, not an art
pass).

Deliberately left open to the parcel: **which palette line and which colour.** Black matches the
Battle Mania 2 precedent and is the obvious default, but it is visible on screen and therefore
the owner's call, not the engine's. Not a blocker — a default with a knob.

### 4.3 The capability bit — no blocker, but it needs a number

`scene_dsl.emp:186-194` rules that `SpriteMask` **will** need a bit, that the bit "arrives WITH
its gated block in the emission parcel, never ahead of it", and that `CAP_FG_SPRITE_STRIPS`
($0080) is **not** it. Declared and reserved bits run `$0002`…`$0800` (`:178-184`), with `$0001`
a deliberate retired hole. **The first genuinely free bit is `$1000`.** Derived from the block,
not chosen.

### 4.4 The dormant twin — an opportunity, not a blocker

`InsertSpriteMasks` has no caller that ever does anything (§3.1a). The strip emitter's loop is
structurally the same walk: stack sprites down the screen, respect `MAX_VDP_SPRITES`, thread
`a4`/`d5`. **Whether to generalise one emitter or add a second is a parcel-shape call**, but it
should be made deliberately rather than by default — two near-identical emitters, one of them
dead, sharing one set of constants is how the 8-px/16-px confusion happened in the first place.

---

## 5. Recommendation, cost, and the shape of the parcel

**Cover the artifact with a 16-px-wide, full-height opaque sprite strip on plane A, built from
14 stacked 2×2 (16×16) sprites over 4 shared VRAM tiles.**

**What the owner sees:** while one of the six per-column scenes is live, an opaque 16-pixel bar
down the left edge — 5% of the width, static, at the very edge. The wobble and perspective
effects are untouched. Under any other scene the bar is not there.

**What it costs the machine:** 4 VRAM tiles (an existing free run), 14 of 77 spare sprite-table
entries, 1 of 18 spare sprites per scanline, 16 of 288 spare sprite pixels per scanline, ~112
bytes of SAT writes per frame while the scene is live, and zero of all of it otherwise.

### 5.1 One parcel or a pair — **a PAIR, and it is byte-changing**

| lands in | what |
|---|---|
| **aeon** | the strip emitter in `engine/objects/sprites.emp`, capability-gated on a new `CAP_LEFT_COL_STRIP = $1000`; the strip's own geometry constants (NOT a reuse of `SPRITE_MASK_*`); the `art_tile` payload on `SceneLeftColMask.SpriteMask`; deleting the refusal `ensure` at `scene_dsl.emp:1375`; the corrected width in the `SceneLeftColMask` banner (`:379`) and the `Vscroll_Write` banner; the §1.6 value-claim correction and the §2.0 Hydrocity deletion in both banners; the axis-5 repricing (`SB_AXIS5_MASK_LINE_PIXELS` 8→16, `SB_AXIS5_MASK_TABLE_SLOTS` 7→14) and the matching toml rows; `check_axis5_mask_pricing()` re-pointed at the strip's constants; the mask tile + `vram.toml` region at base 1020; `left_col_mask_probe.py --mask` grown into a real arm |
| **sigil** | `crates/sigil-cli/tests/sprites_port.rs` routed through `lower_module_with_contracts` + `scanline_caps_contract_env` + `scene_dsl_cap_consts_src`; the `SPRITES` pins repinned for the new region length in both shapes |

**It is a byte-changing parcel** — sprites.emp grows a gated block, so the `sprites` region
length moves in both shapes and the repin→refreeze `--ab` ritual applies with prose.

### 5.2 Suggested sequencing — the correctness fixes are separable and should go first

1. **Zero-byte, immediately, no dependencies:** extend the guard family to scan `ly_fa` / `ly_dsa`
   (§6); correct the width in `scene_dsl.emp:379`; correct the §1.6 value claim in both banners;
   delete the §2.0 Hydrocity citation from `scene_dsl.emp:371`, the `Vscroll_Write` banner and
   `DEFERRED_WORK`; and fix the two stale comments the triage flagged
   (`parallax.emp:670-672` and `:793-795`, both of which still say no scene attaches a column
   table). Comptime and comment only. **Worth landing on its own even if the owner later rules
   "ship it"** — today `Factor0Lock` is unsound (§1.7) and a scene can pass a build-checked claim
   that its foreground artifact cannot exist.
2. **The pair:** the emission, as above.
3. **After:** flip the six scenes' declarations (§6).

### 5.3 The gate the parcel owes

Per the gate bar: **`check_axis5_mask_pricing()` re-pointed at the strip's own constants**,
deriving `pixels/line` from the strip's size byte (`(((size >> 2) & 3) + 1) * 8` — the arithmetic
already at `effects_budget_check.py:271`) and `slots` from `ceil(SB_SCREEN_LINES / strip_height)`
— **not** from `SPRITE_MASK_*`, which measure the dormant X=0 mechanism (§3.1a). Runner:
`tools/effects_budget_check.py`, already executed build-fatally by every canonical `./build.sh`.
Red-first, both arms: (i) shrink the strip's size byte to 1 cell and the derivation must name 8
against the toml's 16; (ii) perturb the toml reservation so 14 slots overruns and the comptime
`scene_dsl.emp:2260` ensure must fire. Loud when it cannot measure: the existing
`return ([...], "")` paths on a missing constant already do this and the re-point must keep them.

**The gate that does NOT exist and must.** Nothing in the tree can see that the strip is *wide
enough*. The pricing gate checks the strip against the *budget*; it never checks it against the
*artifact*. That is the gap this whole design exists because of. The derivable half is a comptime
`ensure` beside the strip's constants:

```
    ensure(LEFT_COL_STRIP_WIDTH_PX >= VDP_COLUMN_VSCROLL_GRAIN,
           "the left-column strip must cover a whole VSRAM column-pair: the partial column
            is (HScroll & (GRAIN-1)) px wide and reaches GRAIN-1, so a narrower strip is
            correct only at some camera positions — see docs/research/2026-08-28-…")
```

Zero bytes, fails at build time on any future narrowing, expectation derived from the grain
(itself derivable from `Vscroll_Write`'s 20-entry emit against `SCREEN_WIDTH`), never copied
from a nearby pin. The other half is runtime and is TAG 2.

---

## 6. Should the six scenes' `Accept` change?

**Yes — to `SpriteMask`, all six, but only at step 3 of §5.2 and not before.**

- **Rocking**'s `Accept` (`ojz_scenes.emp:321-330`) is argued entirely on plane B and is *true
  about plane B*. Under a guard that also scans plane A it becomes an unexamined claim about the
  plane that actually breaks. Its banner needs rewriting whatever the owner rules.
- **Perspective**'s `Accept` (`:365-372`) is a genuine artifact decision — again for plane B's
  shimmer rows. Its own "if the sliver ever matters visually, the upgrade path is SpriteMask" is
  exactly the path being taken.
- All six are **registry-only**: `act_descriptor.emp:157` installs `ParallaxConfig_OJZ_Default`
  (`Scene_OJZ_Default`), which attaches no per-column table. Flipping them changes no
  shipping-path pixel; it changes the DEBUG effects-lab, which is where the owner saw this.

**Sequencing is not cosmetic.** `scene()` refuses `SpriteMask` today (`scene_dsl.emp:1375`), so
flipping before the emission lands fails the build. Flipping *before the width is corrected*
would ship an 8-px cover under a declaration claiming coverage — the precise
gate-cannot-see-the-unbuilt-half failure that refusal `ensure` was written to prevent.

**A booked side note that a plane-A-aware guard SUPERSEDES.** `DEFERRED_WORK` records that
re-authoring Rocking's `dsb: 4` to `15` would unlock the verified `Factor0Lock` spelling at the
cost of one shipped record byte per Rocking config. **Under a plane-A-aware guard that stops
being true**: Rocking's `fa: FACTOR_1` fails the new plane-A half regardless of `dsb`. That note
should be marked superseded rather than left live, and the only route by which Rocking reaches
`Factor0Lock` is §2.6 — locking `fa` too, which stops the foreground scrolling. Recorded as a
correction to a booked item, not smuggled into the recommendation.

---

## 7. TAGs — runtime work for the controller's foreground lane

This lane has no emulator. Each TAG states the scene, what to sample, and **the prediction that
would falsify the design if it came back wrong**.

**TAG 1 — the width is a function of camera X, not a constant. THE LOAD-BEARING ONE.**
Scene **12** (`Rocking_Fast`; loudest of the six, and not phase-dependent like scene 11). Read
`Camera_X` **and** VDP reg `$0B` at the sample point — never trust the scene cursor
(`2026-08-27-…-reproduction.md` records two instruments that manufacture a false negative).
Sample plane-A `opaque` at screen `x = 0, 4, 8, 12, 16` across ground rows `y = 168, 176, 184`,
at **sixteen consecutive camera X positions**.
*Prediction (§1.2, and plutiedev's "up to 15px"):* the artifact's right edge sits at
`x = (-camX) mod 16`, sweeping the full 0…15 range across the sixteen positions — including
**exactly one position, `camX ≡ 0 (mod 16)`, with no artifact at all**.
**Falsifies:** a width constant at 16 across all sixteen positions (the recommendation survives,
but §1.2's formula and §5.3's `ensure` must be re-derived), or any width exceeding 15 px (the
whole 16-px premise is wrong and §3 must be re-priced).

**TAG 2 — the strip actually covers it. AFTER the emission lands; the gate §5.3 cannot build
statically.** Same scene, same rows, with a per-column scene declaring `SpriteMask`, sampled at
**all sixteen camera phases** — not one.
*Prediction:* plane-A pixels at `x ∈ [0,15]` are the strip's colour at every one of the sixteen
phases, and `x = 16` is unaffected.
**Falsifies:** any phase where a ground-row pixel in `[0,15]` is neither strip nor correct
content. Sampling one phase would pass against an 8-px strip — the exact hole this design is
about.

**TAG 3 — the strip survives the per-line sprite limit.** Same instrument, SAT walked from the
VRAM link chain (pattern: `tools/engine_baseline_probe.py --sat`). Motivated by genvdp.txt's
"sprites outside the physical display area are still taken into account" (§3.3) — the 20/line
limit is reached by object count, not by visibility.
*Prediction:* the 14 strip entries are **first** in the link chain, SAT `X = 128`, priority bit
set, Y coverage 0..223 with no gap at the 16-line seams.
**Falsifies:** the strip appearing after object sprites in the chain — it would be droppable at
the 20-sprite line limit, i.e. the cover would vanish exactly when the screen is busy.

**TAG 4 — the partial column's VALUE. NOT needed for this design; needed by anyone who reopens
§2.9.** An opaque cover covers whatever was fetched, and **nothing in the recommendation depends
on the value** — the sources disagree and the behaviour is revision-dependent (§1.6). But §2.9's
free fix stands or falls on it, and two shipped games gesture at it, so the measurement is
specified rather than left as folklore. On scene 12 with bit 2 confirmed set: sample plane-A and
plane-B `VSRAM[19]` (VSRAM word offsets `$26`/`$27`) and the rendered sliver's apparent V-scroll
in the same frame.
*Prediction if Genesis Plus GX's model holds on this emulator:* the sliver's V-scroll equals
`VSRAM[19].planeA & VSRAM[19].planeB` on **both** planes.
**Whatever it returns, §2.9 stays rejected on a single-emulator result** — the objection is
revision-dependence across real silicon, which no emulator run can retire. A green TAG 4 would
justify only a *further* investigation, never the fix.

---

## 8. What this lane could not settle

- **The partial column's fill value** (§1.6). Sources disagree; behaviour is revision-dependent.
  Immaterial to the fix, material to the banners, which currently state "0" as fact.
- **Whether VDP reg `$00` bit 5 works at all** (§2.2 caveat). genvdp.txt says "No effect";
  plutiedev and Genesis Plus GX say 8-px left blank. Nothing in this design depends on it.
- **The strip's colour and palette line** (§4.2). Visible on screen, therefore the owner's.
- **Whether to generalise `InsertSpriteMasks` or add a second emitter** (§4.4). A parcel-shape
  call that wants the code in front of it.
- **Nothing here is measured.** No emulator ran. Every number is derived from source, from a
  cited hardware reference, or quoted from a prior measured run — and each says which.
