# Visual Techniques Backlog

Catalog of Genesis VDP and 68000 visual tricks worth investigating for richer-looking zones. Not a commitment — a research backlog. Each entry: what it is, what it costs, what it buys, where to dig deeper.

When a technique graduates from "interesting" to "we'll use this," promote it to a focused research note in this directory and link it back here.

## Status legend

- `IDEA` — noted, not yet researched
- `RESEARCHING` — actively gathering reference + measurements
- `PROTOTYPING` — code experiment in progress
- `ADOPTED` — promoted to ENGINE_ARCHITECTURE.md, in use
- `REJECTED` — investigated, not worth it (note why)

## 2026-08-14 status sweep

The effects vocabulary review (`docs/superpowers/notes/2026-08-14-effects-vocabulary-review.md`)
flagged that this file's statuses had gone stale: several entries were still `IDEA` after the
engine shipped the capability. Every claim below was re-checked against the tree on
2026-08-14 and each changed status carries a `file:line` citation.

**Convention for the corrections.** The original entry text is left exactly as written — a
reader should be able to see what was believed when the entry was authored. Corrections are
appended as a dated block at the end of the entry, and the `**Status:**` line shows the
original status struck through followed by the corrected one. Some capabilities landed in
halves (the raster half of a technique ships while its content or authoring half does not);
those statuses name both halves rather than inventing a new legend value.

---

## 1. Shadow/Highlight tier system as a level palette multiplier

**Status:** ~~IDEA~~ → **ADOPTED** (hardware enable + measurement) — corrected 2026-08-14

The headline motivation for this whole doc. With STE on (VDP $0C bit 3), every CRAM color renders at three brightnesses depending on how it's drawn:
- Low-pri tile → shadowed
- High-pri tile → normal
- Under operator sprite (palette 3 / $E or $F) → highlighted

One CRAM green becomes three perceptual greens. A 16-color foliage palette becomes ~45 perceived foliage colors with no extra CRAM use.

**Cost:** Lose plane-priority as a depth-ordering tool (it becomes a brightness-tier tool instead). Reserve palette line 3 indices $E/$F for operators. Base palette must be designed to read meaningfully at all three brightnesses (mid-saturation, mid-value colors work best).

**Buys:** Roughly 3× perceived color count from the same 64-entry CRAM. Big mood win for forest, cave, underwater, twilight, industrial zones.

**Research:** Sonic 3D Blast (heavy use), Comix Zone (cel-shaded look), Vectorman, Castlevania Bloodlines stained glass, Mickey Mania, Ristar.

**Engine touchpoints (when adopted):** Per-chunk priority flag in section data, "operator sprite" type in mappings format, palette-design guidelines doc.

**2026-08-14 correction:** The hardware enable shipped with the effects raster tier.
`sh_on()` (`engine/effects/raster_dsl.emp:116`) emits `set_reg($8C89, $8C81)` — VDP $0C bit 3
on from the landing line, H40 base restored at frame top — and the shipped OJZ fixture uses it
(`games/sonic4/data/parallax/configs.emp:347`). The effect is gate-measured, not asserted: mean
row brightness steps **15.83 → 8.10 across the boundary, a 1.95x step**
(`docs/benchmarks/effects-p2/GATE-EVIDENCE.md:163`).
Still open from this entry's touchpoints: no per-chunk priority flag in section data and no
"operator sprite" type in the mappings format — i.e. what ships is the S/H *mode*, not yet the
authored tier system built on top of it.

---

## 2. HInt palette regions (vertical color zones)

**Status:** ~~IDEA~~ → **ADOPTED**, with the asked-for build-time validator only partly delivered — corrected 2026-08-14

Horizontal interrupt fires every N+1 lines (VDP $0A) and rewrites part of CRAM. Used for waterlines, gradient skies, mood bands, bottom-of-screen tints.

**Cost:** ~80 useful 68K cycles per HInt fire after entry/exit overhead. Each HInt eaten every line ≈ 10% of NTSC frame budget just on entry/exit. CRAM rewrites must finish in HBlank or corrupt the next active line.

**Buys:** Hundreds of perceived colors per frame. Works orthogonally to S/H — you can stack both.

**Research:** Sonic 1 Labyrinth water, Sonic 2/3 Aquatic Ruin / Hydrocity (waterline palette swap, NOT shadow/highlight as is sometimes claimed), Toy Story / Vectorman gradient skies, Comix Zone backgrounds.

**Engine touchpoints:** Per-section "palette band" table `(scanline, palette_line, num_colors, src_addr)`, generic HInt dispatcher, build-time validator that sums per-line CRAM bandwidth and refuses to assemble over-budget zones.

**2026-08-14 correction:** Shipped as the raster op set. Three opcodes cover this entry:
`OP_CRAM` (`engine/effects/raster.emp:88`, inline colour words), `OP_PAL_REGION`
(`engine/effects/raster.emp:116`, a scoped region streamed from a palette variant's staging
buffer) and `OP_RUN_GRADIENT` (`engine/effects/raster.emp:141`, the dense per-line tier).
Authoring is `cram` / `pal_region` / `region_boundary`
(`engine/effects/raster_dsl.emp:121`, `:141`, `:268`); the per-section table asked for above
is `Sec.sec_raster_table` (`engine/structs.emp:117`) consumed by `Raster_InstallSection`
(`engine/effects/raster.emp:545`).

**But the build-time validator this entry asked for is only half there, and the half that is
missing is the one the entry actually named.** `fire` (`engine/effects/raster_dsl.emp:203-250`)
sums stream words *within a single fire* against that fire's class ceiling (since 2026-08-19
a per-class pair, `RASTER_BURST_MAX_CRAM` and `RASTER_BURST_MAX_DEEP`, both 3 today) and
additionally
caps ops-per-fire at 4 and CRAM-class-ops-per-fire at 2. **Nothing sums bandwidth across fires
within a frame.** `raster_program` (`engine/effects/raster_dsl.emp:491`) bounds only the
program's total emitted byte length (128 bytes) and cross-checks its own length computation;
it does not model per-line or per-frame CRAM cost. A program of many fires that is
individually legal and collectively over-budget assembles cleanly. The `fire` guard's own
comment says as much — it documents the ceilings as "STRUCTURAL COUNTS … and NOT a cycle
model" (`engine/effects/raster_dsl.emp:208-209`).

---

## 3. Tile-level animation via DMA patching

**Status:** IDEA

Animate tiles in place by DMA-uploading new pixel data to the same VRAM tile slot every few frames. No sprites, no extra tile slots, just a small art rotation queue.

**Cost:** DMA bandwidth per frame (~7.5 KB total in NTSC VBlank — compete with sprite/section streaming). One ROM bank of frame variants per animated tile group.

**Buys:** Waterfalls, flowing lava, twinkling stars, animated gears, blinking lights, conveyor belts — all "free" in tile/sprite count. Looks alive without burning the SAT.

**Research:** Sonic 1/2/3 waterfalls and animated tiles, S.C.E. animated tile system, Treasure games (Gunstar level decoration).

**Engine touchpoints:** Animated tile descriptor table, DMA queue priority lane below section streaming, per-section animated tile activation list.

---

## 4. CRAM cycling (palette animation)

**Status:** ~~IDEA~~ → **ADOPTED** — corrected 2026-08-14

Rotate a sequence of CRAM entries each frame instead of changing tile art. Classic for water shimmer, lava ripples, force fields, candle flames, glowing eyes, "selected" UI items.

**Cost:** Trivial — a few `move.w` per frame. Burns palette slots that have to participate in the cycle (so their tiles can't use those slots for static colors).

**Buys:** Apparent motion with zero VRAM bandwidth and zero sprite use. Stacks with everything.

**Research:** Sonic 1 GHZ water sparkle, Sonic 2 CPZ acid bubbles, basically every 16-bit RPG ever, Amiga demoscene (decades of palette-cycling tricks).

**Engine touchpoints:** Per-section "cycling slots" descriptor; ring buffer of CRAM offsets to advance per frame; designer convention for which palette slots are "cycling-reserved."

**2026-08-14 correction:** Shipped as the palette cycling system. The per-section descriptor
this entry asked for is `Sec.sec_pal_cycle` (`engine/structs.emp:120`), pointing at a
`PalCycleScriptN` of `pal_cycle_channel` records (`engine/effects/palette.emp:146-159`,
4 channels max per script — `PAL_CYCLE_MAX_CHANNELS`, `:73`). Authoring is `cycle_channel`
(`engine/effects/palette_dsl.emp:87`), which bounds line, span, period and direction. Runtime
install and per-frame advance are in `engine/effects/palette.emp:294-338` and `:434-438`,
gated by `PAL_ACT_CYCLE` (`:94`). One script ships today: `OJZ_ShimmerCycle`
(`games/sonic4/data/parallax/configs.emp:402`), bound at
`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:198`.
Caveat carried forward from the review: the cadence has **never been measured** — no cycling
figure appears in `docs/benchmarks/effects-p2/GATE-EVIDENCE.md`, and a possible off-by-one in
the period reload is unadjudicated in either direction.

---

## 5. Backdrop register animation

**Status:** ~~IDEA~~ → **ADOPTED (per-line/raster half) / IDEA (frame-level animation half)** — corrected 2026-08-14

VDP register $07 picks one CRAM entry as the "backdrop" — the color that shows wherever no plane/sprite pixel is opaque. You can animate just this one register for full-screen ambient changes (sunset fade, lightning flash, underwater bottom-tint, alarm strobe).

**Cost:** Literally one register write per frame.

**Buys:** Massive perceived mood shift for ~1 cycle of work. Lightning flashes, fade-to-black, ambient cycling.

**Research:** Many games use it for fades; Sonic 3 lightning in some zones; commonly used for cheap title screen pulsing.

**Engine touchpoints:** Per-section backdrop animation descriptor; reserve one or two CRAM slots as "ambient" colors that drive the backdrop.

**2026-08-14 correction, in two halves.** The *raster* half is authorable today with zero new
code: reg $07 is `$87xx`, comfortably inside `set_reg`'s accepted `$8000..$97FF` range
(`engine/effects/raster_dsl.emp:89-91`), and `set_reg` forces the author to supply the paired
frame-top reset, so a backdrop change cannot latch past the frame it was made in. A raster
program can therefore change the backdrop at any scanline.

The *frame-level* half — "animate just this one register per frame" — has **no consumer**. No
per-section backdrop animation descriptor exists, and the only reg-$07 write in the tree
outside a raster program is the fault path (`engine/system/release_fault.emp:71`, which sets
the backdrop red before halting). A raster program is a frozen schedule; the per-frame
animation this entry describes would need either a staged word the program reads or a
frame-level animator, and neither is built.

**MEASURED 2026-08-14 — INERT ON OJZ, AND THE REASON IS THE ART. Do not re-run this.**
The backdrop is only visible where plane A, plane B **and** sprites are all transparent.
Measured directly, with raster taken out of the equation: the boot value at
`engine/system/boot_data.emp:135` was changed from `$00` (pal 0, entry 0) to `$16`
(pal 1, entry 6 = white) and the frame diffed against the unmodified build.

> **Zero pixels differed, out of 71,680.**

OJZ act 1 section 0 has **no transparent pixels on screen at all**. The 51% of the frame that
reads as pure black is opaque black *art*, not the backdrop showing through. A four-band raster
probe (white/yellow/blue/grey at lines 40/90/140/190) confirmed it from the other direction:
the blue and grey bands scored 0 pixels, and the only white/yellow hits in frame were the HUD.

**The consequence for planning.** This technique is **art-led, not engine-led**. Its payoff is
gated on a zone deliberately authoring transparent regions — open sky behind a broken
silhouette (ridge line, ruined skyline, a canopy with real gaps). OJZ is a dense foliage wall
with no sky, so it is precisely the wrong host. File as *available when a zone wants sky*
rather than sequencing engine work for it. Note also what it can do that painting cannot: the
backdrop shows through **every** hole at once, and per-line it shades each hole by its own
height — painting that needs a distinct tile per (hole shape x height), which explodes. That is
the only case where it beats simply painting the gradient into the background art.

Corpus note (2026-08-14 sweep): **no game in the nine-disassembly corpus animates reg $07
per line** — verified negative for Batman & Robin, Thunder Force IV, Vectorman, Ristar, S3K and
Alien Soldier; Gunstar only strobes it with the display off. The likely reason is the same one
measured above: period backgrounds are opaque, so there is no surface for the effect to appear
on. It is a genuine gap in the corpus rather than a technique anyone tried and rejected.

---

## 6. Operator sprites for lighting

**Status:** IDEA (subset of #1 but worth its own slot)

Beyond the static-region S/H tier system, operator sprites can be **dynamic**: a torch sprite that highlights an aura around it, a magnifying glass, a flashlight cone in a dark zone, a drop shadow beneath the player at all times.

**Cost:** Standard sprite budget (80 total / 20 per line). Operator pixels still consume sprite-line slots.

**Buys:** Real-time lighting on a 1990 console. Drop shadows give massive depth perception for free. Torch zones look unforgettable.

**Research:** Vectorman lighting, Castlevania Bloodlines torches, modern homebrew (Demons of Asteborg uses dynamic lighting).

**Engine touchpoints:** Sprite mappings format flag for "operator (highlight)" / "operator (shadow)" so editor can stamp them visually. Player drop-shadow as a built-in sprite type.

---

## 7. HScroll per-line and per-tile parallax

**Status:** ~~IDEA~~ → **ADOPTED** (both modes) — corrected 2026-08-14

The HScroll table can specify a horizontal offset per line, per 8-line tile, or per screen. Per-line opens up wave distortion, heat haze, water surface ripple, boss-attack screen wobble. Per-tile gives cheap multi-band parallax.

**Cost:** Per-line mode = HScroll table is 224 entries × 4 bytes = 896 bytes RAM, written every frame. Per-tile mode = 28 entries × 4 bytes = 112 bytes (much cheaper).

**Buys:** Mountains/clouds at multiple speeds, water reflections wobbling, mirage / heat-haze bands, boss "screen-shake-only-here" effects.

**Research:** Sonic 2 CPZ background bands (per-tile), Thunder Force IV (per-line everywhere), Sonic 3 Hydrocity surface ripple, Treasure games for boss effects.

**Engine touchpoints:** Per-section parallax descriptor; pre-built HScroll table generator for common patterns (sin-wave wobble, layered band scroll); HScroll DMA upload path in VBlank.

**2026-08-14 correction:** Both modes ship in the parallax system, and the mode is chosen for
the author rather than declared. `Parallax_Fill_PerCell` (`engine/level/parallax.emp:1072`)
emits the 28-longword per-cell table; `Parallax_Fill_PerLine`
(`engine/level/parallax.emp:880`) emits the 224-longword per-line table with FG/BG deform
sampling. The selection is derived from whether the active config carries H-deform tables, and
the same derivation drives the VDP $0B mode bits so register and buffer can never disagree
(`engine/level/parallax.emp:439-445`: `%10` per-cell, `%11` per-line). Per-section binding is
the parallax config on the `Sec` record.

---

## 8. VScroll per-cell (vertical column scrolling)

**Status:** ~~IDEA~~ → **ADOPTED** (per-column VBlank path; per-band raster path added 2026-08-14) — corrected 2026-08-14

VSRAM is 40 entries (one per 16-pixel column in H40 mode), letting each column scroll vertically independently. Great for fake-3D terrain where the floor "sinks" in the middle, screen-warping boss attacks, wavy ocean horizons.

**Cost:** 80 bytes of VSRAM updates per frame if every column changes. Cheaper if only a band changes.

**Buys:** Pseudo-3D depth that's hard to fake any other way. Can simulate hills, valleys, screen-melt transitions.

**Research:** Sonic 2 special stage (per-column V-scroll for the 3D effect), Sonic 3D Blast HUD area, Castlevania Bloodlines water column scrolling.

**Engine touchpoints:** Per-section "column-scroll mode" flag; pre-built column table generators (sine, sawtooth, melt).

**2026-08-14 correction, in two halves — both now shipped.**

*Per-column, whole-frame:* `Vscroll_Write` (`engine/level/parallax.emp:339`) branches on the
active config's `pcfg_v_deform_table_bg` and emits either the whole-plane `Vscroll_Factor` or
the 20-longword per-column buffer to VSRAM. The per-section mode flag this entry asked for is
that config field, and it is mirrored into the VDP $0B mode bit by the same derivation that
drives HScroll mode (`engine/level/parallax.emp:447-449`, bit 2 = per-column V-scroll).
A hardware quirk is documented at the branch: with non-zero Plane B HScroll, the leftmost
partial 16px column renders at V-scroll 0 regardless of VSRAM[0]
(`engine/level/parallax.emp:329-337`).

*Per-band, mid-frame (raster):* the `vsram()` constructor
(`engine/effects/raster_dsl.emp:186`) lets a raster program write VSRAM at a chosen scanline.
It needed **no runtime change** — `Raster_HInt`'s CRAM path issues whatever command longword
the program carries and never inspects the target bits, so the only thing that had made those
ops CRAM-only was the encoder hardcoding the target. Caveat recorded at the constructor and
worth repeating here (`engine/effects/raster_dsl.emp:172-181`): **which scanline a VSRAM write actually lands on is unmeasured.** CRAM
and reg $07 are unlatched and apply to line N+1; VSRAM may latch earlier and land on N+2.
Sources conflict, emulators differ, and nobody has run it on oracle. Content must not assume
the N+1 rule for `vsram`.

---

## 9. Window plane for HUD

**Status:** IDEA

The Window plane is a third "fake" plane locked to one or more screen edges, drawn from a separate nametable. Use it for a fixed HUD area — frees up the 80-sprite budget that HUD digits would otherwise consume.

**Cost:** Window steals nametable RAM and overlaps with plane A in its region (plane A becomes invisible there). Must be edge-anchored — no floating mid-screen window.

**Buys:** HUD that doesn't compete with gameplay sprites. Score, ring count, timer, boss health bar — all sprite-free.

**Research:** Sonic 1/2/3 didn't use it (uses sprites for HUD), but Streets of Rage, Strider, Castlevania Bloodlines, many shmups do. Plutiedev has good window plane docs.

**Engine touchpoints:** Window plane nametable region in VRAM layout, HUD renderer that writes to window nametable instead of SAT.

---

## 10. Sprite masking (column occlusion)

**Status:** ~~IDEA~~ → **ADOPTED** — corrected 2026-08-14

A sprite at X=0 with the right link-list position acts as a mask — it hides any lower-priority sprite on the same scanlines. Useful for "object enters tunnel and disappears" effects without changing sprite art, or for column-wise occlusion in foreground areas.

**Cost:** One sprite slot per masking column. Link-list ordering complexity.

**Buys:** Clean object-disappear effects, column-based foreground occlusion that would otherwise need plane-priority gymnastics.

**Research:** Plutiedev sprite masking page; some shmups use this for foreground rocks.

**Engine touchpoints:** Sprite type flag for "mask," documented link-list ordering rules.

**2026-08-14 correction:** Shipped as `InsertSpriteMasks`
(`engine/objects/sprites.emp:753`), called from the SAT build path at
`engine/objects/sprites.emp:441` so masks are written into the SAT buffer at the ordering
position the hardware needs. Listed in the architecture index as "sprite X=0 masking
(hardware clipping)" (`docs/ENGINE_ARCHITECTURE.md:18`).

---

## 11. Mid-frame plane base address swap

**Status:** ~~IDEA~~ → **ADOPTED (raster half) / IDEA (content half)** — corrected 2026-08-14

VDP plane base addresses (registers $02 / $04) can be changed via HInt. Top half of the screen renders from one nametable, bottom half from another. Effectively gives you two plane As in one frame.

**Cost:** One HInt fire to do the swap; nametable data for both regions; design complexity in the section streamer.

**Buys:** Two visually distinct regions stacked vertically — sky + ground that scroll independently with completely different art and palettes; "split-screen 3D" effects; UI/gameplay separation richer than the window plane allows.

**Research:** Some Treasure games and shmups, Titan demos, Mode 7-style rotozoom hacks.

**Engine touchpoints:** Section-streaming awareness of dual-region zones; HInt handler that swaps base regs.

**2026-08-14 correction:** The second touchpoint above — "HInt handler that swaps base regs" —
is listed as though one still needed writing. **`OP_SET_REG` is that handler**
(`engine/effects/raster.emp:87`, dispatched as the compare chain's fall-through at
`engine/effects/raster.emp:451-458`). Registers $02 and $04 are `$82xx` / `$84xx`, inside
`set_reg`'s accepted `$8000..$97FF` range (`engine/effects/raster_dsl.emp:89-91`), and
`set_reg`'s mandatory paired frame-top reset means the swap structurally cannot latch past the
frame. A two-fire program that repoints Plane B mid-screen and restores it is authorable today
with no new code.

What this entry still needs is the **content** side, and that half is untouched: a second
nametable in the VRAM map and a streamer that fills it, plus the section-streaming awareness
the first touchpoint names. Raster support was never the blocker.

---

## 12. Multi-sprite mega-objects

**Status:** IDEA (already implicitly in scope for bosses)

Build huge characters / bosses out of many linked sprites with shared logic. Treasure's specialty — Gunstar Heroes bosses, Alien Soldier, Dynamite Headdy puppet-bosses.

**Cost:** Sprite slot count balloons; need a "multi-sprite object" abstraction in the object system.

**Buys:** Bosses that fill the screen, articulated characters, anything bigger than the 32×32 single-sprite ceiling.

**Research:** Gunstar Heroes (boss dissection on YouTube + disasm), Alien Soldier, Vectorman.

**Engine touchpoints:** Object format extension for "multi-sprite link group," SAT writer that emits multiple slots per object, per-part offset tables.

---

## 13. Sprite-only parallax layer (third plane)

**Status:** IDEA

Wide low-priority sprites placed behind plane B can act as a third pseudo-plane — useful for far parallax or for foreground decoration that needs to scroll independently of A and B.

**Cost:** Sprite budget; sprites are 32×32 max so coverage costs many slots; per-line cap means horizontal density is capped.

**Buys:** A whole extra parallax layer. Lets plane A and B be more carefully designed without compromise.

**Research:** Strider has sprite-based foreground parallax; Thunder Force IV layered backgrounds.

**Engine touchpoints:** "Background sprite" object class; section-data hook for spawning them on entry; sprite-line budget validator.

---

## 14. Active-display CRAM dot crawl (raster bars)

**Status:** ~~IDEA (tier: demoscene)~~ → **ADOPTED (per-line band form) / IDEA (pixel-precise dot crawl)** — corrected 2026-08-14

Deliberately write CRAM during active display to produce raster bars — colored stripes that ride across the screen pixel-precise. Titan Overdrive uses this.

**Cost:** Cycle-counted CRAM writes timed to specific dots. Extremely fragile against any other CPU work in the same frame area.

**Buys:** Visual flair impossible by other means. Title screen / cutscene hero shots.

**Research:** Titan Overdrive 1 & 2 (videos + post-mortems), Mega Drive demoscene articles, Kabuto's hardware notes.

**Engine touchpoints:** Probably a one-off scene-script system for cutscenes rather than general engine support. Not worth complicating gameplay code.

**2026-08-14 correction:** The **per-line band** form of this is largely covered by the dense
raster tier and needs no scene-script system. `OP_RUN_GRADIENT`
(`engine/effects/raster.emp:141`) is a per-line CRAM writer: its `.dense_body`
(`engine/effects/raster.emp:510`) re-issues a constant CRAM command every line and advances a
cursor through a stream, which is exactly a moving colour band. The shipped gate is a 96-line
ramp (`OJZ_TestGradient`, `games/sonic4/data/parallax/configs.emp:536-541`), and the dense
tier's marginal cost is ~342 cyc/line — an upper bound that includes profiler
instrumentation and exception entry, not a clean marginal
(`docs/superpowers/2026-08-13-effects-p2-handoff.md:84`).

`rgp_stream` is typed `Label` (`engine/effects/raster.emp:255`, parameter at
`engine/effects/raster.emp:263`), so it is admissible to aim it at a **RAM** buffer and refill
that buffer each frame — the bars would then ride. **This is untested:** the only stream that
has ever shipped is ROM `data` (`games/sonic4/data/parallax/configs.emp:532`), and nobody has
run a RAM-backed stream. Treat it as a plausible path, not a demonstrated one.

What is genuinely *not* covered is the tier this entry was actually written about: the
**pixel-precise, dot-timed** Titan-class bar. Our granularity is one scanline, set by the HInt,
and the handler deliberately burns `EFX_BLANK_DELAY` to park writes offscreen rather than
timing them to a dot. Mid-scanline FIFO-slot precision remains an unbuilt item
(`docs/ENGINE_ARCHITECTURE.md:22`).

---

## 15. Dithering across S/H tiers

**Status:** IDEA

Combine S/H mode with checkerboard / ordered dither at the tile level to produce intermediate brightnesses (between shadow and normal, between normal and highlight). Pushes the perceived color count beyond 3× per palette entry.

**Cost:** Tile art design discipline (manual dithered tiles); risk of "screen door" pattern visibility on small TVs / emulators with sharp upscaling.

**Buys:** ~5–6 perceived brightness levels per palette entry instead of 3. Smoother gradients and softer mood transitions.

**Research:** Amiga demoscene dither patterns; modern emulator-friendly dither studies; PC engine art (used heavily in low-color-count workflows).

**Engine touchpoints:** Tile authoring guidelines doc; possible "dither tile pair" helper in the editor.

---

## 16. Streaming art bigger than VRAM

**Status:** ~~IDEA (subset of section streaming, but worth flagging the visual implications)~~ → **ADOPTED** — corrected 2026-08-14

By DMA-uploading tiles ahead of the camera, you can have apparent unique art well beyond the 2048-tile VRAM cap. The section streamer in this engine already does the work — but the visual *opportunity* is using it aggressively for non-repeating environments.

**Cost:** DMA bandwidth, build-time tile dedupe, camera-ahead prediction.

**Buys:** Movie-like environments where every screen looks different. No tile reuse boredom.

**Research:** Comix Zone (every screen unique), Sonic CD bonus stages, Demons of Asteborg.

**Engine touchpoints:** Already in scope via section streaming (`docs/research/section-streaming.md`); this entry is a reminder that streaming enables visual uniqueness, not just memory savings.

**2026-08-14 correction:** No longer aspirational — this is the shipped §9.7 VRAM residency
cache. The act's globally-deduped, spatially-ordered tile pool is split into 64-tile pages
streamed in on demand plus prefetch, decoded by a resumable ZX0 decoder sliced across idle time
by a VBlank supervisor bookmark, with stamp eviction of the oldest released unpinned pages
(`docs/ENGINE_ARCHITECTURE.md:24`, `:1516`, `:1592`, `:1678`). The consequence this entry cared
about is now literal: **the pool is capped by ROM budget, not by VRAM** — gated at build time by
`tools/art_rom_report.py` — and it degenerates to fully-resident for acts whose pool fits the
frame budget (`docs/ENGINE_ARCHITECTURE.md:1519`).

---

## 17. DMA fill / DMA copy

**Status:** IDEA

VDP DMA can fill VRAM with a single byte at high speed (DMA fill) or copy VRAM to VRAM one byte at a time (DMA copy). Useful for clearing nametables, painting solid background regions, scrolling tile content within VRAM, fast effects.

**Cost:** Mostly cycle-cheap; DMA copy is slow per byte (1 byte ~16 mclk) so suited to small ranges.

**Buys:** Fast clears for transitions; scrolling tile patterns by DMA-copying tile rows; possible "bigger-than-screen" parallax effects.

**Research:** Plutiedev DMA reference; many engines use DMA fill on level transitions.

**Engine touchpoints:** Section transition path uses DMA fill for nametable clears; tile-scroll effects could use DMA copy.

---

## 18. Beat-driven visual effects

**Status:** IDEA (tier: speculative, gameplay-feel)

Hook visual effects (palette pulse, backdrop tint, raster bars) to music kicks via the Z80 sound driver state. Title screens and boss intros benefit most.

**Cost:** Z80↔68K coordination; sound driver must expose beat / channel-state. The Flamedriver design probably needs a small "visual hook" port.

**Buys:** Title screens, boss reveals, end-of-act fanfares with synchronized visual punch. Modern feel on retro hardware.

**Research:** Demons of Asteborg synced cutscenes; modern Pico-8 / TIC-80 visual-music coupling for ideas; Flamedriver internals.

**Engine touchpoints:** Z80 driver shared-state byte for "beat tick"; 68K visual-effect dispatcher that polls it.

---

## 19. Per-section HInt handler dispatch

**Status:** ~~RESEARCHING (see `ristar-techniques.md`)~~ → **ADOPTED — mechanism shipped; the one-handler shape is POLICY, not a limit** — corrected 2026-08-14

Instead of one global HInt handler that branches on the current section's effect type, each section *registers its own HInt routine pointer* at entry, and the IRQ dispatch jumps directly to it. Costs nothing per-frame and removes a branch tree that gets uglier as more raster effects are added.

**Cost:** One pointer per section in section data. Section streamer must update the IRQ vector (or a `HInt_CurrentHandler` hook) on transitions.

**Buys:** Each act can do completely different raster work — cell-scroll, per-line palette, sin-wave HSCROLL, mid-frame plane swap — without paying for runtime dispatch. Easier to author one-off "hero shot" effects per stage.

**Research:** Ristar uses this — per-act HInt scripts for the planet-exit zoom, underwater shimmer, boss pull-in. Thunder Force IV similar pattern. Sonic 1/2/3 do NOT — single shared raster routine with stage-id branches.

**Engine touchpoints:** `Section` struct gains `hint_handler` pointer (default = no-op). VBlank exit / section-load path stores it where the HInt vector reads from. Composes naturally with #2 (HInt palette regions), #7 (HScroll per-line), #8 (VScroll per-cell), #11 (mid-frame plane swap).

**2026-08-14 correction — resolved, but differently from how this entry imagines it. Two
facts, and they are easy to conflate:**

**1. The mechanism ships, and it is more general than this entry asked for.** The IRQ4 vector
points *directly* at `HBlank_Vector_Slot` (`engine/system/vectors.emp:122`), a 6-byte RAM slot
(`engine/ram.emp:764`) holding either an idle `rte` or `jmp handler.l`
(`engine/system/hblank.emp:31`). The public `HBlank_Install(a0, d0)`
(`engine/system/hblank.emp:57-59`) patches the slot with an arbitrary handler address and
programs the line counter. There is no ROM dispatch stub and no indirect call — the interrupt
reaches the handler through one `jmp` (`engine/system/hblank.emp:3-7`). **So arbitrary
per-state HInt handlers ARE supported today**, and by any game state, not just a section
transition. That is a superset of the `Section.hint_handler` field this entry proposed.

**2. What we do by POLICY is install exactly one handler.** `Raster_HInt`
(`engine/effects/raster.emp:384`) is armed once (`engine/effects/raster.emp:369`) and walks
*per-section data* rather than dispatching to per-section code: `Sec.sec_raster_table`
(`engine/structs.emp:117`) is staged by `Raster_InstallSection` on a boundary crossing
(`engine/effects/raster.emp:545`, called from `engine/level/parallax.emp:186`). The expensive
per-line work that motivated this entry lives outside the interrupt entirely, in the parallax
system's frame-level HScroll/VSRAM buffers (#7, #8). So this entry's stated motivation —
"removes a branch tree that gets uglier as more raster effects are added" — is satisfied with
no branch tree at all, and by data rather than by code pointers.

**A bespoke handler remains available to any state that wants one** — that is what
`HBlank_Install` is. The one-handler-plus-data shape is a deliberate choice for level play,
not a ceiling. (A prior reading of this entry concluded the mechanism was absent and only the
policy existed; that is wrong, and the distinction matters — the next author to want a
one-off raster handler for a title screen or boss does not need new engine work.)

---

## 20. Sprite multiplexing (multi-band SAT reuse)

**Status:** ~~IDEA (tier: specialty mode, not default sprite path)~~ → **IDEA (HInt half covered; blocked on VRAM + SAT binning) — AND DISPUTED: a banked doc rejects this technique outright, see the correction below** — corrected 2026-08-14

The VDP scans the SAT top-to-bottom as the beam descends — by the time line 100 is rendering, all sprites with Y < 100 have been processed and their SAT entries are no longer in use. So if you swap to a different SAT mid-frame, the **same 80 hardware sprite slots** can render a fresh set of 80 sprites in each band. 4 bands → 320 effective sprites, 8 bands → 640, etc. Demos have hit 1000+. Pair with CRAM rewrites between bands and you also multiply visible color count (~440 colors in published demos).

**Per-line cap (20 sprites) still applies** within each band. Multiplexing does not let you stack 40 sprites on one row — only 80 sprites on different rows that each fit the 20-per-line cap.

**Cost:**
- **Approach A (DMA-rewrite SAT each band):** ~1900 cycles per DMA over many scanlines via active-display DMA, plus per-frame SAT-build cost in main RAM. Bandwidth-heavy.
- **Approach B (multiple SATs in VRAM, swap via VDP register $05):** ~30 cycles per HInt + ~110 cycles entry/exit. **4 bands ≈ 560 cycles/frame, less than 0.5% of NTSC budget.** This is the path worth investigating first.
- **VRAM cost (Approach B):** N × 640 bytes for N SATs (4 bands = 2.5 KB, 8 bands = 5 KB).
- **Authoring cost:** every sprite-spawning system needs to know which band a sprite ends up in, either via static binning (per-system band assignment) or dynamic binning (sweep all sprites by Y each frame, ~5–10 cyc per sprite).

**Buys:** Specialty visual moments that 80-sprite hardware can't normally do — ring-rush sections (hundreds of rings), bullet-hell bosses, snow/rain/firefly weather, crowd/audience scenes, opening logo with 200 floating particles. Color expansion is arguably the bigger Sonic-engine win: each band gets its own ~16-color palette, so a single zone can present multiple distinct color regions.

**Why not always-on:** Most Sonic gameplay never needs >80 sprites. Default-on multiplexing taxes every frame for binning and SAT rebuilds even when there's nothing extra to render. Best deployed as a per-state opt-in (boss arena flips it on, normal level uses standard sprite path).

**Research:** Mega Drive demoscene "Sprite Multiplex" demos, Titan Overdrive 2 (multiplexed sprites), modern homebrew (Demons of Asteborg uses it for some boss patterns), plutiedev sprite engine page, Kabuto's hardware notes for SAT timing.

**Engine touchpoints:** Per-state `multiplex_bands` config; SAT-build code that bins sprites into N bands by Y range; HInt handler that writes VDP register $05 to swap SAT base address; optional CRAM-rewrite hook to multiply colors band-by-band. Composes naturally with #19 (per-section HInt handler dispatch — multiplexer is just one more handler kind) and #2 (HInt palette regions — same HInt fire can do both).

**2026-08-14 correction, part 1 — the HInt half is covered; the blockers are elsewhere.**
"HInt handler that writes VDP register $05 to swap SAT base address" is one `set_reg` call:
reg $05 is `$85xx`, inside `set_reg`'s accepted `$8000..$97FF` range
(`engine/effects/raster_dsl.emp:89-91`), dispatched by `OP_SET_REG`
(`engine/effects/raster.emp:87`), and the band-by-band CRAM rewrite the entry wants alongside
it is `cram` in the same fire. Approach B's per-band cost is therefore already payable.
What actually blocks this entry is the other two touchpoints: **N x 640 bytes of VRAM for N
SATs** against a pool that is already carved to the tile
(`docs/ENGINE_ARCHITECTURE.md:1540`), and **SAT-build code that bins sprites by Y** — neither
exists. Status stays `IDEA` for that reason, not for want of raster support.

**2026-08-14 correction, part 2 — TWO BANKED DOCS DISAGREE ABOUT THIS TECHNIQUE. NOT
ADJUDICATED HERE.**

`docs/research/2026-06-23-genesis-technique-survey.md:105` lists sprite multiplexing among
techniques **rejected outright**, on the grounds of "no >80-sprite content, fixed priority
bands suffice for a platformer; each trades clarity/budget for granularity we don't need."

This entry argues the opposite: that the colour expansion (per-band palettes) is "arguably the
bigger Sonic-engine win", independent of sprite count, and that it should live as a per-state
opt-in rather than being rejected engine-wide.

Both readings are defensible and they cannot both stand as the project's position. The
disagreement is **recorded, not resolved** — it needs an owner ruling, and whichever way it
goes, the losing document should be amended rather than left to contradict the other.

---

## Cross-cutting considerations

When evaluating any of these for adoption, run them through these filters:

1. **VRAM cost** — does this consume tile slots? How many?
2. **CRAM cost** — does this lock palette slots? Compete with S/H reservations?
3. **DMA cost** — bytes per VBlank? Compatible with section-streaming bandwidth?
4. **Sprite cost** — slots used? Per-line risk?
5. **CPU cost** — cycles per frame? VBlank-only or active-display?
6. **Composability** — does it stack cleanly with already-adopted techniques?
7. **Authoring cost** — does it need editor / build-pipeline support?
8. **Failure mode** — when it goes wrong on hardware, is it loud (visible glitch) or silent (off-by-one drift)?

A technique passes adoption when its VRAM/CRAM/DMA/sprite/CPU costs fit alongside everything already in the budget, and the authoring path is clear enough that level designers can use it without reading 68K assembly.
