# Visual Techniques Backlog

Catalog of Genesis VDP and 68000 visual tricks worth investigating for richer-looking zones. Not a commitment — a research backlog. Each entry: what it is, what it costs, what it buys, where to dig deeper.

When a technique graduates from "interesting" to "we'll use this," promote it to a focused research note in this directory and link it back here.

## Status legend

- `IDEA` — noted, not yet researched
- `RESEARCHING` — actively gathering reference + measurements
- `PROTOTYPING` — code experiment in progress
- `ADOPTED` — promoted to ENGINE_ARCHITECTURE.md, in use
- `REJECTED` — investigated, not worth it (note why)

---

## 1. Shadow/Highlight tier system as a level palette multiplier

**Status:** IDEA

The headline motivation for this whole doc. With STE on (VDP $0C bit 3), every CRAM color renders at three brightnesses depending on how it's drawn:
- Low-pri tile → shadowed
- High-pri tile → normal
- Under operator sprite (palette 3 / $E or $F) → highlighted

One CRAM green becomes three perceptual greens. A 16-color foliage palette becomes ~45 perceived foliage colors with no extra CRAM use.

**Cost:** Lose plane-priority as a depth-ordering tool (it becomes a brightness-tier tool instead). Reserve palette line 3 indices $E/$F for operators. Base palette must be designed to read meaningfully at all three brightnesses (mid-saturation, mid-value colors work best).

**Buys:** Roughly 3× perceived color count from the same 64-entry CRAM. Big mood win for forest, cave, underwater, twilight, industrial zones.

**Research:** Sonic 3D Blast (heavy use), Comix Zone (cel-shaded look), Vectorman, Castlevania Bloodlines stained glass, Mickey Mania, Ristar.

**Engine touchpoints (when adopted):** Per-chunk priority flag in section data, "operator sprite" type in mappings format, palette-design guidelines doc.

---

## 2. HInt palette regions (vertical color zones)

**Status:** IDEA

Horizontal interrupt fires every N+1 lines (VDP $0A) and rewrites part of CRAM. Used for waterlines, gradient skies, mood bands, bottom-of-screen tints.

**Cost:** ~80 useful 68K cycles per HInt fire after entry/exit overhead. Each HInt eaten every line ≈ 10% of NTSC frame budget just on entry/exit. CRAM rewrites must finish in HBlank or corrupt the next active line.

**Buys:** Hundreds of perceived colors per frame. Works orthogonally to S/H — you can stack both.

**Research:** Sonic 1 Labyrinth water, Sonic 2/3 Aquatic Ruin / Hydrocity (waterline palette swap, NOT shadow/highlight as is sometimes claimed), Toy Story / Vectorman gradient skies, Comix Zone backgrounds.

**Engine touchpoints:** Per-section "palette band" table `(scanline, palette_line, num_colors, src_addr)`, generic HInt dispatcher, build-time validator that sums per-line CRAM bandwidth and refuses to assemble over-budget zones.

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

**Status:** IDEA

Rotate a sequence of CRAM entries each frame instead of changing tile art. Classic for water shimmer, lava ripples, force fields, candle flames, glowing eyes, "selected" UI items.

**Cost:** Trivial — a few `move.w` per frame. Burns palette slots that have to participate in the cycle (so their tiles can't use those slots for static colors).

**Buys:** Apparent motion with zero VRAM bandwidth and zero sprite use. Stacks with everything.

**Research:** Sonic 1 GHZ water sparkle, Sonic 2 CPZ acid bubbles, basically every 16-bit RPG ever, Amiga demoscene (decades of palette-cycling tricks).

**Engine touchpoints:** Per-section "cycling slots" descriptor; ring buffer of CRAM offsets to advance per frame; designer convention for which palette slots are "cycling-reserved."

---

## 5. Backdrop register animation

**Status:** IDEA

VDP register $07 picks one CRAM entry as the "backdrop" — the color that shows wherever no plane/sprite pixel is opaque. You can animate just this one register for full-screen ambient changes (sunset fade, lightning flash, underwater bottom-tint, alarm strobe).

**Cost:** Literally one register write per frame.

**Buys:** Massive perceived mood shift for ~1 cycle of work. Lightning flashes, fade-to-black, ambient cycling.

**Research:** Many games use it for fades; Sonic 3 lightning in some zones; commonly used for cheap title screen pulsing.

**Engine touchpoints:** Per-section backdrop animation descriptor; reserve one or two CRAM slots as "ambient" colors that drive the backdrop.

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

**Status:** IDEA

The HScroll table can specify a horizontal offset per line, per 8-line tile, or per screen. Per-line opens up wave distortion, heat haze, water surface ripple, boss-attack screen wobble. Per-tile gives cheap multi-band parallax.

**Cost:** Per-line mode = HScroll table is 224 entries × 4 bytes = 896 bytes RAM, written every frame. Per-tile mode = 28 entries × 4 bytes = 112 bytes (much cheaper).

**Buys:** Mountains/clouds at multiple speeds, water reflections wobbling, mirage / heat-haze bands, boss "screen-shake-only-here" effects.

**Research:** Sonic 2 CPZ background bands (per-tile), Thunder Force IV (per-line everywhere), Sonic 3 Hydrocity surface ripple, Treasure games for boss effects.

**Engine touchpoints:** Per-section parallax descriptor; pre-built HScroll table generator for common patterns (sin-wave wobble, layered band scroll); HScroll DMA upload path in VBlank.

---

## 8. VScroll per-cell (vertical column scrolling)

**Status:** IDEA

VSRAM is 40 entries (one per 16-pixel column in H40 mode), letting each column scroll vertically independently. Great for fake-3D terrain where the floor "sinks" in the middle, screen-warping boss attacks, wavy ocean horizons.

**Cost:** 80 bytes of VSRAM updates per frame if every column changes. Cheaper if only a band changes.

**Buys:** Pseudo-3D depth that's hard to fake any other way. Can simulate hills, valleys, screen-melt transitions.

**Research:** Sonic 2 special stage (per-column V-scroll for the 3D effect), Sonic 3D Blast HUD area, Castlevania Bloodlines water column scrolling.

**Engine touchpoints:** Per-section "column-scroll mode" flag; pre-built column table generators (sine, sawtooth, melt).

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

**Status:** IDEA

A sprite at X=0 with the right link-list position acts as a mask — it hides any lower-priority sprite on the same scanlines. Useful for "object enters tunnel and disappears" effects without changing sprite art, or for column-wise occlusion in foreground areas.

**Cost:** One sprite slot per masking column. Link-list ordering complexity.

**Buys:** Clean object-disappear effects, column-based foreground occlusion that would otherwise need plane-priority gymnastics.

**Research:** Plutiedev sprite masking page; some shmups use this for foreground rocks.

**Engine touchpoints:** Sprite type flag for "mask," documented link-list ordering rules.

---

## 11. Mid-frame plane base address swap

**Status:** IDEA

VDP plane base addresses (registers $02 / $04) can be changed via HInt. Top half of the screen renders from one nametable, bottom half from another. Effectively gives you two plane As in one frame.

**Cost:** One HInt fire to do the swap; nametable data for both regions; design complexity in the section streamer.

**Buys:** Two visually distinct regions stacked vertically — sky + ground that scroll independently with completely different art and palettes; "split-screen 3D" effects; UI/gameplay separation richer than the window plane allows.

**Research:** Some Treasure games and shmups, Titan demos, Mode 7-style rotozoom hacks.

**Engine touchpoints:** Section-streaming awareness of dual-region zones; HInt handler that swaps base regs.

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

**Status:** IDEA (tier: demoscene)

Deliberately write CRAM during active display to produce raster bars — colored stripes that ride across the screen pixel-precise. Titan Overdrive uses this.

**Cost:** Cycle-counted CRAM writes timed to specific dots. Extremely fragile against any other CPU work in the same frame area.

**Buys:** Visual flair impossible by other means. Title screen / cutscene hero shots.

**Research:** Titan Overdrive 1 & 2 (videos + post-mortems), Mega Drive demoscene articles, Kabuto's hardware notes.

**Engine touchpoints:** Probably a one-off scene-script system for cutscenes rather than general engine support. Not worth complicating gameplay code.

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

**Status:** IDEA (subset of section streaming, but worth flagging the visual implications)

By DMA-uploading tiles ahead of the camera, you can have apparent unique art well beyond the 2048-tile VRAM cap. The section streamer in this engine already does the work — but the visual *opportunity* is using it aggressively for non-repeating environments.

**Cost:** DMA bandwidth, build-time tile dedupe, camera-ahead prediction.

**Buys:** Movie-like environments where every screen looks different. No tile reuse boredom.

**Research:** Comix Zone (every screen unique), Sonic CD bonus stages, Demons of Asteborg.

**Engine touchpoints:** Already in scope via section streaming (`docs/research/section-streaming.md`); this entry is a reminder that streaming enables visual uniqueness, not just memory savings.

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

**Status:** RESEARCHING (see `ristar-techniques.md`)

Instead of one global HInt handler that branches on the current section's effect type, each section *registers its own HInt routine pointer* at entry, and the IRQ dispatch jumps directly to it. Costs nothing per-frame and removes a branch tree that gets uglier as more raster effects are added.

**Cost:** One pointer per section in section data. Section streamer must update the IRQ vector (or a `HInt_CurrentHandler` hook) on transitions.

**Buys:** Each act can do completely different raster work — cell-scroll, per-line palette, sin-wave HSCROLL, mid-frame plane swap — without paying for runtime dispatch. Easier to author one-off "hero shot" effects per stage.

**Research:** Ristar uses this — per-act HInt scripts for the planet-exit zoom, underwater shimmer, boss pull-in. Thunder Force IV similar pattern. Sonic 1/2/3 do NOT — single shared raster routine with stage-id branches.

**Engine touchpoints:** `Section` struct gains `hint_handler` pointer (default = no-op). VBlank exit / section-load path stores it where the HInt vector reads from. Composes naturally with #2 (HInt palette regions), #7 (HScroll per-line), #8 (VScroll per-cell), #11 (mid-frame plane swap).

---

## 20. Sprite multiplexing (multi-band SAT reuse)

**Status:** IDEA (tier: specialty mode, not default sprite path)

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
