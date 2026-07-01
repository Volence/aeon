<!--
Research artifact. Produced 2026-06-23 by a 9-agent parallax research workflow
(TF4 / Ristar / Batman&Robin / Sonic2 disasm readers + plutiedev/demoscene/Sonic-BG
online + a fresh read of our engine/level/parallax.asm). Disasm claims carry
file:routine:line citations read from actual code, not inferred.
Verified against our codebase before saving:
  - parallax.asm:268,287 Plane A hard-locked / Decode_Factor_B Plane B  CONFIRMED
  - DEFERRED_WORK.md:467 FG left-edge draw-lookahead (the FG-parallax blocker)  CONFIRMED
  - DEFERRED_WORK.md:871 column-scroll left-edge VSRAM bug + sprite-mask fix  CONFIRMED (already ours)
Framing: educational survey + honest gap analysis. Locked decisions respected
(Plane A camera-locked, Plane B lerp/deform, per-line HScroll mandatory, no mulu).
-->

# How One Background Becomes Six Layers: Genesis Parallax for the s4_engine

You drew an arrow over the pillars and said "these move at a different speed than the cliffs behind them, and there's even a separate foreground." That's the right thing to be suspicious of, because the Genesis has **exactly two scroll planes and one sprite layer** — and the image reads as six. This explains how that trick works, why your specific observation (two things at a *similar height* moving at *different speeds*) is the genuinely hard case, and exactly where our engine already stands against it.

---

## 1. The core mechanism: line-scroll turns one plane into N layers

The single most important fact: **a "layer" in a Genesis background is not a plane. It is a contiguous range of scanlines on the *same* plane, given its own horizontal scroll offset.**

### The hardware feature

VDP register `$0B` (mode register 3) controls scroll granularity:
- bits 0-1 (HSCR): `00` = whole screen (1 H-scroll value), `10` = per-cell (every 8px row), `11` = **per-line** (one value per scanline).
- bit 2 (VSCR): `0` = whole screen vertical, `1` = **per-2-cell column** (every 16px-wide column has its own vertical scroll).

Classic Sonic and our engine set `$8B03` (per-line H, whole-screen V) or `$8B07` (per-line H + per-column V). Sources: `sonic_hack/code/engines/level_init.asm:85`, `s2disasm/s2.asm:4106`, and the hardware reference at rasterscroll.com/mdgraphics/vdp-inner-workings/ and plutiedev.com/mirror/kabuto-hardware-notes.

### The HScroll table — exact structure

In per-line mode, VRAM holds a **HScroll table**: one **longword per scanline**, where:

```
  bits 31..16 = Plane B (background) horizontal scroll   ← high word
  bits 15..0  = Plane A (foreground/playfield) scroll    ← low word
```

(A/B word ordering confirmed in `sonic_hack/code/engines/dma_plc.asm:172` and huguesjohnson.com / Kabuto notes. *Note the convention: low word = Plane A. Our engine writes FG word + BG word per entry — same layout.*)

- 224 NTSC lines × 2 planes × 2 bytes = **896 bytes** for the full table.
- Scroll value is 10-bit signed (−512..+511); positive shifts the plane right. The VDP value is the **negative** of camera position (you move the *world*, so the plane offset is `-camera_x`).
- Base address set via VDP register `$0D`. In S2 it lives at VRAM `$FC00`.
- **No interrupt is required.** The VDP walks the table automatically as it rasterizes each line. HInt is only needed for things the table can't express (palette swaps, register changes, mid-line splits) — see §2 and §4.

### How you get the layers

You divide the 224 lines into **bands**. Every line in a band gets the same Plane B scroll value; between bands, the value changes. The value is `camera_x >> N`, negated — larger shift = slower = farther away:

```
 line   band         Plane B value     apparent layer
 ───────────────────────────────────────────────────────
  0..21  SKY          0  (static)       sky gradient (locked)
 22..79  CLIFFS       camX >> 6  (1/64) distant cliffs — crawl
 80..127 PILLARS      camX >> 3  (1/8)  midground pillars — faster
128..175 GRASS        camX >> 1  (1/2)  near grass — fast
176..223 FG STRIP     camX >> 0  (1/1)  ground, camera-locked
```

That is the whole illusion. One Plane B tilemap — sky tiles painted at top, cliff tiles below, grass tiles at the bottom — sliced by scanline so each painted region scrolls at its own rate. Stock Sonic does this in `s2disasm/s2.asm:15253` (`SwScrl_EHZ`) and `:15779` (`SwScrl_HTZ`); our OJZ build does it in `sonic_hack/code/engines/level_load.asm:316` (`DeformOJZ_BG_X1..X8`, literally `camX >> 6,5,4,3,2,1` down the near-ground stack). S3K generalized it into a data table (`skdisasm/sonic3k.asm:103662 ApplyDeformation`, walking a `*_BGDeformArray` of band-length words). Thunder Force IV drives all four of its bands from **one shared 512-byte wave table** read at different phase accumulators and `asr` depths (`thunderforce4_disasm/.../disasm.asm` `loc_004CE8`, table at ROM `$17a00`).

### Per-frame cost

- **Compute:** build 224 longwords into a RAM shadow buffer. Pure `asr`/`neg`/`add` and tight `dbf` runs — **no multiply**. S2's `SwScrl_OJZ` is ~9 dbf loops; the only expensive variant is the graduated ground band (a `divs.w` + 16.16 fixed-point accumulator per line, `s2.asm:15330`).
- **DMA:** the 896-byte table is transferred to VRAM every VBlank. *This is the dominant cost, not the compute.* On our engine it's a measured ~20% flat tax (more in §5).
- **VSRAM:** 80 bytes total = 40 longwords = 20 columns × 2 planes. Either one whole-plane longword (cheap) or all 20 columns. DMA-Fill **cannot** touch VSRAM, so it's a CPU loop / queued transfer — still trivial in bytes.

---

## 2. The hard part you spotted: two things at a similar height, different speeds

Your arrow is on the **pillars** (midground) vs the **cliffs** (back) — and they overlap vertically. Here is the honest answer:

**Within a single band, pure plane scroll cannot make two objects at the same scanline scroll at different speeds.** A band is *one* scroll value applied to *one* plane across that line range. Everything painted on those lines moves together, full stop. If the cliff bases and the pillar tops occupy the same scanlines, banding alone makes them one layer.

This is the real 2-plane wall. The cheat is that in most Hill-Top-style art **the layers don't actually overlap vertically as much as they appear to** — the artist stacks them so each gets its own clean scanline range, and the eye reads depth from the *speed difference between adjacent bands*, not from true occlusion. But when they genuinely must overlap (a pillar standing in front of a cliff that continues behind it), you need one of four real techniques:

### (a) Plane A vs Plane B separation — the one true "two layers at the same height"
The only way to get two tilemaps occupying the same scanlines at different speeds **for free** is to put one on Plane A and one on Plane B. That's your real second layer. But Sonic spends Plane A on the **playfield the character stands on** (camera-locked) and Plane B on the banded background — so both planes are already committed. You can't hand the pillars their own plane without giving up either the playfield or the background.

### (b) Sprite-based scenery layers
Anything that must move independently *and* overlap another layer at the same height becomes **hardware sprites**. Pillars rendered as sprite columns can scroll at any rate, in front of or behind the player via the priority bit, completely decoupled from the band underneath. Cost: sprite budget (80/frame, 20/line in H40) and pixel-fill. Thunder Force IV does exactly this — its "in-front" depth is sprites from type-segregated pools with priority round-robin on overflow (`thunderforce4_disasm` foreground note). Stone Protectors multiplexes one sprite slot down the screen for 118 effective sprites across 3 depth layers (rasterscroll.com/.../sprite-raster-effects/). This is the workhorse for genuine same-height overlap.

### (c) Clever art / band placement
The cheapest fix, and what real Hill-Top does: **author the art so cliffs and pillars occupy disjoint scanline ranges.** Cliff bases sit *above* the line where pillars start. Then "different speed at similar height" becomes "different speed at adjacent bands," which banding handles trivially. The red arrow's effect is sold by the *seam* between two bands moving apart, not by true overlap.

### (d) Mid-band raster splits (HInt)
If you need the split line to **track a world feature** (a horizon that bobs, a foreground floor whose top edge follows the camera), you arm an HInt at a computed scanline and reprogram scroll/registers mid-frame. Ristar computes `splitLine = worldFeatureY − cameraY` each frame and writes it to VDP reg `$8A` (the HInt line counter): `ristar_disasm/.../disasm.asm:16180` (`$D3BA`: `move.w $e580,d0 ; sub.w $f024,d0 ; addi.w #$8a00,d0 ; move.w d0,$c00004`). At that line the HInt bursts a fresh VSRAM table or flips reg `$0B` mode. This is how you get a band whose *boundary* is camera-tracked rather than a fixed scanline.

### Concrete build: how I'd actually layer YOUR image

```
  ┌────────────────────────────────────────────┐
  │ (1) SKY GRADIENT          lines  0.. 23     │  Plane B, scroll = 0 (static)
  │                                             │   — or a palette gradient via HInt
  ├────────────────────────────────────────────┤
  │ (2) CLOUD BAND            lines 24.. 47     │  Plane B, scroll = camX>>4 PLUS an
  │     ~~~~~~~~~~~~~~~~~~~~~~~~                 │   animated additive offset table so
  │                                             │   clouds drift even when player is still
  ├────────────────────────────────────────────┤
  │ (3) BROWN STRIPED CLIFFS  lines 48..111     │  Plane B, scroll = camX>>5 (1/32, far)
  │     ║║║║  ║║║║  ║║║║                         │   striped art = on the SAME plane
  ├────────────────────────────────────────────┤
  │ (4) ROCK PILLARS + grass  lines 96..143     │  ── THE HARD ONE ──
  │     ▲     ▲      ▲   (red arrows)            │   If pillars sit BELOW cliffs:
  │     ███   ███    ███                         │   next Plane B band, scroll = camX>>2.
  │                                             │   If pillars OVERLAP cliffs at same Y:
  │                                             │   pillars become SPRITES (option b)
  ├────────────────────────────────────────────┤
  │ (5) GREEN GRASS BAND      lines 144..199    │  Plane B, scroll = camX>>1 (1/2, near)
  │     ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒                   │
  ├────────────────────────────────────────────┤
  │ (6) CHECKERED FG STRIP    lines 200..223    │  Plane A, high-priority tiles, scroll
  │     ▣▢▣▢▣▢▣▢▣▢▣▢▣▢▣▢                         │   = camX (1/1) or slightly faster band
  └────────────────────────────────────────────┘
```

- **Bands 1, 2, 3, 5** are pure Plane B line-scroll bands. Free.
- **Band 4 (pillars)** is the crux. If the art lets pillars live on their own scanlines below the cliffs → another Plane B band, free (your red-arrow speed difference is just `>>2` vs `>>5`). If pillars must stand *in front of* cliffs that continue behind them at the same height → they become **sprites**, because no amount of banding splits one scanline into two speeds.
- **Band 6 (checkered FG)** is the "separate foreground." It is *not* a third plane — it's either the bottom rows of **Plane A** with the high-priority bit set (renders over a low-priority player), or sprites. See §3.

The takeaway for the arrow: **the cliffs and pillars almost certainly do not truly overlap in the source art.** They're adjacent bands. If they did overlap, one of them would be a sprite layer. There is no third plane.

---

## 3. The separate foreground

"In front of the player and/or scrolling faster than the player" has exactly three implementations on real silicon. The hardware layer order is fixed:

```
 backdrop < low-pri B < low-pri A < low-pri sprites < high-pri B < high-pri A < high-pri sprites
```

### (a) High-priority Plane A tiles over a low-priority player — the classic Sonic FG
Set the priority bit on the foreground tiles' mappings. A high-priority Plane A tile renders **above** a low-priority player sprite — this is the "run behind the pillar/tunnel" look. **Free** (just the per-tile bit). The catch: the FG scrolls with Plane A. To make it scroll *faster* than the player you dedicate scanline-bands of Plane A to it via per-line HScroll — but then those bands can't simultaneously be the player's mid-ground. On a 2-plane machine that's a real tension. (rasterscroll.com sprite-raster-effects; SpritesMind t=2865.)

### (b) High-priority sprites
High-pri sprites beat *everything*, including high-pri Plane A — they always pass in front. Positioned/scrolled fully independently → true independent-speed FG. **Cost:** sprite budget (80/frame, 20/line) and pixel-fill; large transparent FG shapes waste sprite cells. This is what TF4 and Ristar use for in-front motion (`ristar_disasm` SAT shadow `$FFEC00`, per-piece priority bit OR'd at `$50FE`).

### (c) Window plane
A rectangular region of Plane A that **does not scroll** — good for HUD, letterbox, static frames. **Useless for a moving foreground** (can't scroll, axis-aligned rectangle only).

**Honest verdict:** a faster-than-player, in-front foreground that isn't a priority-tile band is almost always sprites. There is no third tile plane to give it. The tradeoff is sprite-budget vs. spending one of your two planes' scanline bands.

---

## 4. The advanced / demoscene tier

Same two primitives (per-line HScroll + per-column VSRAM), driven much harder.

- **Pseudo-rotation / tilt floors** — cross a per-line HScroll *ramp* (shear horizontally, 1px/line) with a per-column VSRAM *ramp* (shear vertically per column). Linear on both axes ≈ a small rotation. **Set-piece only**, narrow angle range, shearing artifacts. Castlevania Bloodlines' tower/statue, Gunstar Heroes stage-3 boss (rasterscroll.com/.../tilting-rotation/). B&R's dual-accumulator generator is the exact primitive: two 16.16 accumulators, one to the HScroll buffer, one to the VSRAM buffer (`disasm/engine/engine_data_1.asm:6150`). **Gameplay-viable** as a gentle tilt; **not** as free rotation.

- **Perspective (1/z) floors** — per-line scroll step via `divu` against a horizon parameter, so line spacing compresses toward the horizon. B&R's pseudo-3D Batmobile surfaces: `disasm/effects/effects.asm:8317` (`$C000 / d7`, then `asl.l #6`). True perspective-correct, but needs a divide (a reciprocal LUT for our no-`mulu`/no-`divu` rule). **Set-piece**, bandwidth-bound.

- **Water / reflection line-scroll** — water ripple is *free* because HScroll is already per-line: add a tiny animated 0-3px offset table to the water band's lines (`s2disasm/s2.asm:15398 SwScrl_RippleData`, advanced every 8 frames). Bloodlines' sprite reflections exploit the SAT half-entry cache: two sprite tables, flip the SAT base register at the water line, the VDP keeps cached Y/size/link while reading the new live half → free mirrored sprites, zero duplication (rasterscroll.com sprite-raster-effects). **Gameplay-viable.**

- **Sprite-multiplexed extra layers** — rewrite a sprite's SAT entry every N scanlines to reuse one slot down the screen (Stone Protectors, 118 effective sprites). Sprite groups scrolled at their own rate = extra parallax layers beyond the 2 planes. **Gameplay-viable** within sprite budget.

- **Animated cloud/wave offset tables** — an additive per-line table summed onto a band's base scroll, indexed by a free-running phase accumulator. HTZ clouds drift even when Sonic stands still (`s2.asm:15779`). TF4's shared wave table + per-band phase (`$f2a4..$f2ac` step accumulators). **Gameplay-viable, near-free.** This is what our deform path already is.

- **The genuinely crazy stuff (Titan Overdrive)** — rewrite VSRAM **every scanline** plus change the Plane A nametable-base register mid-line (the nametable register is *not* latched — it applies immediately, unlike VScroll which latches at HInt) to fake 3D spheres/tunnels. HInt is too late (~10-16px + ~44 CPU cyc to enter the handler), so Titan **polls the H-counter to mid-line and bursts writes**; VSRAM/CRAM pop in 1 FIFO slot vs 2 for VRAM. (jsgroth.dev/blog/posts/titan-overdrive via snippets; Kabuto notes; SpritesMind t=2604.) **Demo-only** — costs CPU spin-waiting every scanline, no room for game logic.

- **The live hardware bug you must respect:** whenever per-column VSRAM is active **and** the plane has nonzero horizontal scroll, the **leftmost 16px column shows garbage tiles.** Hardware-mandated, not a coding error. Real games hide it with a sprite strip over column 0 (Battle Mania 2) or avoid H-scroll on column-scroll stages (M.U.S.H.A.); Gynoug shipped it visible. (rasterscroll.com row-column-scrolling.) **This is a live risk for us** — see §5.

---

## 5. Where OUR engine stands

This is the honest assessment against the image, respecting locked decisions (Plane A camera-locked, Plane B lerp/deform, per-line HScroll mandatory, per-cell rejected, no `mulu`).

### What we already do (shipped, `engine/level/parallax.asm`)
- **Multi-band per-line HScroll** — up to `MAX_PARALLAX_BANDS = 8` (`constants.asm:322`); shipped OJZ runs 4 bands. Each band carries independent Plane-A and Plane-B factors as **multiply-free shift-add** `{shift1, shift2, op}` decoded by `Decode_Factor_A/B` (`parallax.asm:543`). This is the exact band model from §1.
- **Per-line FG/BG H-deform** — animated cloud/wind/heat-shimmer via a 256-byte signed table sampled at a free-running phase accumulator (`parallax.asm:626`, phases at `ram.asm:145`). OJZ ships it zeroed (`DeformTable_Zero`) purely to force per-line mode for 1px band-boundary precision.
- **Per-column VSRAM deform** — 20 column-pairs, animated, for rocking/pseudo-perspective (`parallax.asm:497`, `Parallax_Vscroll_Column_Buf` 80 bytes). **We already do the vertical axis TF4 never needed.**
- **Whole-plane vertical parallax + per-frame band rotation** — Plane B scrolls vertically and the authored plane-space band tops are rotated into screen rows each frame (`Step4a`, `parallax.asm:333`) so a vertical Hill-Top-style stack holds its depth ordering while scrolling up/down. This is the non-obvious load-bearing piece.
- **Section-boundary config switch with Plane-B-only lerp** (`parallax.asm:61`). Plane A is **never** lerped — hard-locked to `−camX` every frame.

### Could we render THAT image's parallax today?

**The background, YES. The separate foreground, NO — and that's the whole delta.**

- **Bands 1, 2, 3, 5 (sky, clouds, cliffs, grass)** — directly. That is precisely our band model; OJZ Deep-Forest already ships monotonic depth bands (1/16, 1/8, 1/2, 5/8). Cloud drift = our deform path (currently zeroed, but the machinery exists). **Renderable today.**
- **Band 4 (pillars at a different speed than cliffs)** — **YES, if they're on disjoint scanlines** (another Plane B band with its own factor — exactly the red-arrow effect). **NO, if they must truly overlap the cliffs at the same height**, because that needs either a sprite layer (we have **no sprite-foreground system**) or a second mid-ground tilemap (mid-frame Plane-B nametable swap, designed in ARCH §7.2 but **unbuilt**).
- **Band 6 (separate checkered foreground)** — **this is the real gap.** We have:
  1. **No parallaxing foreground.** Plane A is hard-locked `−camX` in every shipped band. Giving it a different factor or H-deform is *possible in code* (the `factor_a` fields and FG deform loop exist) but **deliberately off-limits**: any Plane-A offset from the camera **drags the 64-column plane-wrap streaming seam onto screen**. Unblocking it needs the **left-edge draw-lookahead** that is in `DEFERRED_WORK` (lines 466-477) and **not built**.
  2. **No FG-over-player path.** No high-priority Plane A tile rendering over the player, and **no sprite system at all** for foreground props. So even a static-but-in-front checkered strip has no code path today.

### The honest delta

Our **background parallax foundation fully reproduces the image's BG layer stack today** — bands, graduated depth, vertical parallax with band rotation, animated drift. What's missing is small in concept but real in code:

1. **A separate foreground that passes in front of the player.** Two unbuilt routes, both already *designed*: high-priority Plane A tile bands (needs the left-edge draw-lookahead to let Plane A scroll off-camera without seam tearing — `DEFERRED_WORK:466`), or a sprite-foreground system (doesn't exist yet). For the checkered strip specifically, the cheapest path is a **camera-tracked HInt split** (Ristar's `worldY − cameraY` → reg `$8A`, `ristar_disasm:16180`) giving the bottom band its own VSRAM sub-range on Plane A — designed as ARCH §7's unified raster command table, unbuilt.
2. **A true mid-ground that overlaps the back layer at the same height.** Either accept it as more Plane B bands (free, works as long as the art keeps them on separate scanlines — which Hill-Top art does) or build the **mid-frame Plane-B nametable swap** (ARCH §7.2, unbuilt) for a genuine second BG tilemap.

**Two things to fix regardless:**
- **The column-scroll left-edge bug** (§4) — we run per-column VSRAM on Plane B *and* Plane B has nonzero HScroll. The 16px leftmost-column garbage is documented in our own code comments (`parallax.asm:497` region) but worth verifying on hardware/Exodus that the band ranges actually hit it; if so, a column-0 sprite cover or zero-HScroll-where-deform-active is the standard mitigation.
- **TF4's shared-wave-table steal** — collapsing any per-band deform curves into one 512-byte sine read at per-band `{phase-step, shift}` (`thunderforce4_disasm` `$17a00`) is a strict RAM + cycle win over per-band tables, and lets us animate every band's drift for near-zero extra cost.

**Bottom line:** we could render the *backgrounds* of that Hill-Top image today with the bands we ship; the cliffs-vs-pillars speed split works as adjacent bands; the **only genuine gap is the separate foreground** (and true same-height overlap), which is two already-designed-but-unbuilt features — a parallaxing/over-player FG (blocked on the left-edge draw-lookahead and a sprite-FG system) and an optional mid-frame nametable swap. No architecture change is needed; the foundation is correct. The delta is implementation of cleanly-designed `§7` raster features, not a redesign.