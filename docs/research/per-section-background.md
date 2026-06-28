# §2 A.5 Research — Per-section background art

Settles four open questions for A.5 (per-section BG art) by surveying 7 reference disasms + online sources per CLAUDE.md research checklist.

## TL;DR — decisions

| Question | Decision | Justification |
|---|---|---|
| Q1 — Pre-clear Plane B before redraw? | **No, trust data.** | Both T2 and T3 layouts are full-coverage 64×32 nametables; no possible holes. Pre-clear would double the redraw cost for zero correctness benefit. |
| Q2 — T3 BG tile art shares A.3 art group concept? | **Yes, share.** | Thunder Force IV bundles nametable + tile art in one stage-init DMA batch; Alien Soldier ties BG to per-section unified mechanisms. Matches industry precedent and avoids parallel infrastructure. |
| Q3 — BG-tile dedupe scope? | **Per-section combined FG+BG dedupe in same pass.** | Same dedupe pass already runs in A.1/A.3; folding BG-referenced tiles in costs nothing extra and recovers aliasing wins. |
| Q4 — BG layout storage shape? | **Full 64×32 raw nametable per layout (4096 bytes uncompressed).** | All BG-redraw precedents (TF4, sonic_hack, S.C.E. init) use full nametables. ROM cost (4 KB/layout × ~9 sections = 36 KB) is trivial vs. our 4 MB ROM budget. Compression is a measurable optimization deferrable to later. |

---

## Sources surveyed

### Reference disassemblies (all 7)

#### 1. S.C.E. (Sonic Clean Engine)

- `Engine/Core/Level Setup.asm:38–45` — `VRAM_Plane_B_Name_Table = $E000` set in d7 before BG init
- `Engine/Core/Plane Map To VRAM.asm` — chunk-based layout transformation
- `Engine/Core/Draw Level.asm:679–693` — `Draw_BGAsYouMove` does incremental column/row redraw
- `Levels/DEZ/Events/DEZ1 - Events.asm:22–32` — per-act BG init (`DEZ1_BackgroundInit`)

**BG model:** Two-tier (layout array → 128×128 chunk → tile composition). BG draws at level load via `Refresh_PlaneFull`, then incrementally per camera scroll. Per-act layout swaps via `Level_layout_addr2_ROM`. No mid-act art swap.

**Takeaway for us:** S.C.E.'s incremental-redraw model is more complex than we need. We don't need column-by-column BG streaming because Plane B has independent scroll — section transitions happen rarely enough that one-shot full-redraw is fine.

#### 2. sonic_hack (our reference S2 disasm)

- `code/engines/level_init.asm:174–177` — level init calls `JmpTo_InitDrawBGFull`
- `code/engines/scroll_camera.asm:349–380, 978–1022` — `LoadTilesAsYouMove` and `InitDrawBGFull`
- `code/Levels/Layout List.asm:34` — `Level_OJZ1_BG` zone-wide BG pointer
- `S4.constants.asm:1066, 1578` — `Section_BG_Layout_Ptr` RAM, BG layout RAM addr

**BG model:** **Single zone-wide blob** (e.g., `Level_OJZ1_BG`), shared across all 8 OJZ sections. Per-section variation is **palette only**, not layout/geometry. BG drawn at level load, then per-frame incremental as camera scrolls. Plane B nametable at $6000 in sonic_hack (aeon uses $E000 — different VRAM split).

**Takeaway for us:** sonic_hack is the cleanest direct precedent for our T1 design. The "all sections share one BG" pattern is exactly what we ship for OJZ. Where sonic_hack and S.C.E. differ from us: they do per-frame incremental BG redraw because the BG scrolls and reveals content; we plan one-shot redraw at section transition because our T2/T3 BGs are 64×32 nametables that loop horizontally — no reveal needed.

#### 3. Batman & Robin

- `disasm/code/late/late_code.asm:1558–1700` — `sub_1E5F88` master stage graphics loader
- `disasm/code/engine/vdp.asm:1–300` — VDP layer setup
- Stage table at PC-relative `$1e50d6`

**BG model:** Static per-stage with **compressed** layout data, decompressed once at stage init via pointer-chain dereferencing. No mid-stage BG swap. Plane B at $E000.

**Takeaway for us:** Confirms that for one-shot stage-init BG redraw, compression is worthwhile when ROM is tight — but this game shipped on a 1 MB cartridge. We're at 4 MB and have ~36 KB of BG layouts in worst case, so compression's not load-bearing for A.5.

#### 4. Vectorman

- `vectorman_disasm/ANALYSIS.md:84–200`

**BG model:** Object-centric — backgrounds built entirely through per-object DMA command lists drained at VBlank. No "level layout data" per se; everything is procedurally assembled. Plane B at $E000.

**Takeaway for us:** Not directly applicable — Vectorman's model is for cinematic/cutscene-style scenes, not Sonic-style continuous platforming.

#### 5. Gunstar Heroes

- `gunstar_disasm/code/disasm.asm:1527–1544, 6944–6989`

**BG model:** Stage-loaded once at init, no per-section streaming, direct DMA from VBlank. Standard 32×32 plane size. Per-stage variation only.

**Takeaway for us:** Confirms "one-shot stage init load + no further changes" is a valid model for stage-based games. Our model is similar but with section transitions firing additional one-shot redraws.

#### 6. Alien Soldier (closest analog to T2/T3)

- `aliensoldier_disasm/code/disasm.asm:5278–5296` — VDP register $80D4 holds plane size bits (`andi.w #$e000`)
- `aliensoldier_disasm/code/disasm.asm:42148–42250` — per-section BG headers

**BG model:** **Per-section background management** with 6-byte section headers controlling Plane B VRAM address and tile setup. Runtime CPU writes patch Plane B layout dynamically per section, not DMA. Section data is in a 163 KB region (`$05A400-$0823FF`). Confirms 64×32 plane size support (VDP register $80D4 with $e000 mask).

**Takeaway for us:** Closest industry precedent for what A.5 T2/T3 builds. Alien Soldier patches Plane B per-section using section headers — directly analogous to our `sec_bg_layout` field. Alien Soldier uses CPU writes (not DMA); we'll start with VDP DATA-port writes for simplicity, can move to DMA in a later optimization (added to deferred work).

#### 7. Thunder Force IV (closest analog to T3 unified bundle)

- `thunderforce4_disasm/code/disasm.asm:9765–9815` — `sub_00C374` stage init
- `thunderforce4_disasm/code/disasm.asm:9925–9967` — `sub_00C9D8`/`sub_00CA12` plane nametable loaders
- `thunderforce4_disasm/code/disasm.asm:10077–10099` — DMA execution

**BG model:** Per-stage data-driven DMA. Each stage has a ROM table at `$14cbc/$14cfc` containing **8 DMA parameter triplets** (offset, VRAM address, length). Stage init loops through all 8, building DMA commands that swap **both nametable and tile art in one batch**.

**Takeaway for us:** Strongest precedent for our T3 design — bundling BG nametable + BG tile art in a single section transition. TF4 unifies the data ("8 DMA triplets per stage") rather than treating them as parallel systems. Confirms Q2 decision.

### Online sources

#### plutiedev — VDP Commands

- https://plutiedev.com/vdp-commands

DMA destination formula: `((addr AND $3FFF) << 16) OR ((addr AND $C000) >> 14) OR cmd`. VRAM write command = `$40000080`. Confirms standard hardware approach for nametable writes. No specific Plane B nametable swap pattern documented (it's just "write the bytes you want to the right VDP address").

#### md.railgun.works — VDP wiki

- VDP Plane A/B nametable base addresses configurable per-byte (`SA15-SA13`)
- DMA modes: ROM/RAM → VRAM (copy), VRAM → VRAM (fill), VRAM → VRAM (copy)
- DMA fastest in VBLANK; same speed as direct access during active scan

Confirms our plan to do DMA copy from ROM to VRAM for full Plane B blits (4096 bytes = 2048 word writes; in active scan via VDP DATA port, ~0.6 ms blocking).

#### segaretro — Sonic CD level format

- https://bghq.com/bgs.php?c=3g (Sonic CD background gallery)
- SonED2 format: layout plane sizes stored separately from layout data (`.bin` files)
- Plane A and Plane B have separate layout files

Confirms the precedent for separate FG/BG layout storage. Our `sec_strips_a` (FG) + `sec_bg_layout` (BG) split matches this pattern.

#### SGDK MAP system

- https://github.com/Stephane-D/SGDK/wiki/Tuto-background
- http://www.retropc.net/mm/md/doc/html/map_8h.html

Modern reference. `MAP_create(resource, plane, palette, tiles)` — creates a MAP attached to either BG_A or BG_B. `MAP_scrollTo(plane, x, y)` for scroll. **MAP doesn't support tile streaming** — would need free-scrolling coordination, deemed too complex.

Internal encoding: 128×128 pixel blocks, deduplicated globally, each block = 8×8 grid of 16×16 metatiles.

**Takeaway for us:** Validates two design choices: (a) deduplication is the right approach for BG content (matches our A.1 dedupe), (b) BG and FG can share a unified data model. SGDK doesn't do per-section streaming because it's a general-purpose engine — we can do it because we've designed sections from the start.

#### SpritesMind — community discussions

- http://gendev.spritesmind.net/forum/viewtopic.php?t=1364 — DMA basics
- https://gendev.spritesmind.net/forum/viewtopic.php?t=3244 — "Thousand tiles based maps - 'How to' using SGDK?"

Community consensus: large maps need either (a) decompression + DMA at load time, or (b) chunk-based metatile dedupe (SGDK approach). For per-section variation, chunk-based metatile is the dominant pattern.

#### Mega Cat Studios VDP Guide

- https://megacatstudios.medium.com/sega-genesis-mega-drive-vdp-graphics-guide-v1-2a-e14093f71a33

Confirms: nametable address = SA15-SA13 register × $2000. Plane B's base must align to $2000. Our $E000 satisfies this (= $7 × $2000).

---

## Decisions in detail

### Q1 — Pre-clear before redraw? **No, trust data.**

**Cost analysis:** Our T2/T3 layouts are full-coverage 64×32 nametables. Pre-clearing means 4096 zero-byte writes (~0.5 ms via VDP DATA port) followed by 4096 actual writes. That's 2× the redraw cost.

**Correctness:** Pre-clear protects against partial-coverage layouts (where the source data doesn't fill all 2048 nametable cells). We don't have that case — every BG layout we emit is full-size by design.

**Decision: trust the data.** If we ever introduce sparse/partial layouts (e.g. windowed mid-stage panels), revisit then.

### Q2 — T3 BG tile art shares A.3 art group concept? **Yes, share.**

**Evidence:**
- Thunder Force IV bundles nametable + tile art in one stage-init DMA batch (8 DMA triplets, mixed types).
- Alien Soldier ties per-section BG to a unified section-header mechanism (not separate BG vs FG paths).
- SGDK's MAP unifies FG and BG (`MAP_create(resource, BG_A_or_BG_B, ...)`) — same data, different plane.

**Mechanism for us:** When `--bg-fixture=t3` is set, the build tool walks the section's BG layout, collects referenced tile indices, and folds them into the section's existing A.3 tile-art group (`sec_tile_art_s4lz`). The section's S4LZ blob then contains BOTH FG-referenced and BG-referenced tiles. A.4's `Section_StreamArtGroup` already streams this blob — no engine change needed for T3 streaming.

**Decision: share.** No parallel system. T3 = T2 + extra tile refs added to section's existing art group.

### Q3 — BG-tile dedupe scope? **Per-section combined FG+BG dedupe.**

**Options considered:**
- (a) Separate BG dedupe pass with own pool — simpler, less aliasing
- (b) Global FG+BG dedupe across whole zone — most aliasing, but conflicts with A.3's per-section art-group model
- (c) **Per-section FG+BG combined dedupe** — folds BG refs into A.3's existing per-section dedupe pass

**Decision: (c) per-section combined.** A.1/A.3 already runs a dedupe pass per section. Adding BG-referenced tiles to that pass costs nothing extra at build time. Within a section, FG and BG often share tiles (e.g. a sky tile used in both upper FG and BG bands), so combined dedupe captures aliasing that separate passes would miss.

For T1 (no per-section BG): question doesn't apply — T1 BG references the act-wide FG VRAM space and uses the same tiles already loaded.

### Q4 — BG layout storage shape? **Full 64×32 raw nametable, uncompressed.**

**Options considered:**
- (a) Full 64×32 raw — 4096 B/layout
- (b) Full 64×32 S4LZ-compressed — likely ~2000 B (compression ratio ~0.5 for sky data)
- (c) Column-strip array (parallel to FG strips_a) — 32 cols × 96 B = 3072 B/section but requires column-by-column streaming engine
- (d) Partial 64×16 (top half only, BG pattern repeats vertically via tile reuse) — 2048 B

**Cost analysis (full ROM budget for OJZ):**
- T1 only (current ship target): one zone-wide BG = 4 KB ROM cost.
- T1 + T2/T3 fixtures: T1 + 1 fixture section = 8 KB total.
- Hypothetical zone with 16 sections all T2: 17 layouts × 4 KB = 68 KB — still trivial vs. 4 MB ROM.

**Compression deferrable:** S4LZ compression of BG layouts is straightforward to add as a build-tool optimization later. Until BG ROM cost matters, raw is simpler to author, debug, and reason about. No engine code change needed at compression-add time other than swapping `move.w (a1)+, (a2)` for an S4LZ-decompress preflight.

**Column-strip approach** (option c) was rejected because it forces a column-streaming engine for Plane B, identical to Plane A. That's significant new code for no benefit — Plane B has independent scroll, so the moment-to-moment "needed columns" don't follow camera as cleanly as Plane A does.

**Partial layout** (option d) was rejected because it requires runtime synthesis (loop the partial vertically) for marginal byte savings.

**Decision: (a) full 64×32 raw, 4096 bytes per layout.** Compression deferred. Column-strip approach explicitly rejected.

---

## Implications for the plan

These decisions confirm Tasks 2–10 of the plan as written:

- **Q4 confirms** the 4096-byte layout shape used in `emit_zone_bg_layout` and `emit_section_bg_layout` (Task 3, Task 7).
- **Q1 confirms** `BG_RedrawForSection` skips pre-clear (Task 5 already written this way).
- **Q2 confirms** T3's BG tiles fold into the section's existing A.3 art group (Task 9 design).
- **Q3 confirms** the `sec_tile_refs[sec_id] |= bg_tile_refs` union approach in Task 9 (combined per-section dedupe).

Compression of BG layouts gets added to the deferred-work list in Task 11.

## Q5 — Where do T1/T2 BG tiles live in VRAM? (surfaced during implementation)

**Question** (not foreseen in spec): A.3's per-section graph coloring means VRAM slots 0-1279 are owned by whichever sections are currently loaded. The BG nametable can't reference those slots — slot content shifts on every section transition. So T1's "shares FG tiles" claim isn't operational without a fix.

**Decision: reserve a shared BG tile region at slots 1280-1535 ($A000-$BFFF), 256 tiles capacity, loaded once at level init.**

**Justification:**
- Sonic CD precedent: BG art is loaded once per act, not streamed.
- Thunder Force IV: stage init bundles nametable + tile art in one DMA batch, then the art stays put.
- sonic_hack: ArtKos_OJZ loads zone tiles flat at level init (no per-section pools), so its BG can reference any tile.
- aeon's per-section A.3 model is a memory-efficiency win, but it forces the question of where BG tiles live. The cleanest answer is a separate fixed region.

**Sizing:** 256 tiles = 8 KB. Empirically the OJZ BG (cloud + grass band, sampled 64 cells × 32 cells from `OJZ_1.bin`'s BG section) deduplicates well below this — actual count populated in measurement doc by Task 6. Future zones with richer BG art may need to expand the region; if so, claim more slots from the (currently unused) middle of slots 226-1279.

**Trade-offs:**
- Fixed-size region wastes VRAM for zones with simpler BGs. Acceptable: 256 slots is small relative to 1536 total.
- Reserves slots that can't be used for FG growth. Acceptable: A.3 caps each color at ~700 tiles for OJZ-scale zones; future zones up to ~640 tiles per color stay clear of the BG region.
- Load cost at level init grows by 8 KB DMA. Acceptable: this happens once with display off.

**Implication for plan:** add Task 5b "shared BG tile region" between Tasks 5 and 6. Emits `bg_tiles.bin` from build tool, loads it via `BG_Init`. Without this, T1 ships with placeholder content (engine path proven, visuals incorrect). With it, T1 ships with image-9-quality cloud + grass BG.

## Deferred from A.5 (carried to a future milestone)

- **S4LZ compression of BG layouts.** Straightforward to add when ROM cost becomes meaningful. Engine cost: one S4LZ decompress before the blit; same blit afterward.
- **Plane B redraw via Deferrable DMA queue** (instead of blocking VDP DATA-port writes). Currently ~0.6 ms blocking on T2/T3 transition; could move to ~0 ms by routing through `Plane_Buffer` infrastructure or a dedicated streaming buffer. Defer until profiling shows the blocking redraw is observable.
- **Per-section BG palette swaps.** Already out of A.5 scope per spec; tracked under §7 palette system.
- **Animated BG tiles (palette cycling, tile cycling).** Out of A.5 scope; §7.
- **Per-section parallax variation.** Out of A.5 scope; §4.6 deferred work.
