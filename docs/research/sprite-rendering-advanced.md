# Advanced Sprite Rendering Research — §3.5

Date: 2026-04-25
Task: 19 (Phase 7 research)

## VDP Sprite Limits (H40 / 320px mode)

| Limit | Value |
|---|---|
| Max sprites per frame | 80 |
| Max sprites per scanline | 20 |
| Max sprite pixels per scanline | 320 (40 tiles × 8px) |
| Sprite overflow flag | Status register bit 6 (latched, cleared on read) |

Both per-scanline limits are enforced simultaneously — whichever is hit first causes dropout. With small sprites (8×8, 8×16), the 20-sprite count limit triggers first. With large sprites (32×32), the 320-pixel dot limit triggers with only 10 sprites. Transparent pixels within a sprite tile count toward the dot limit. Partially off-screen sprites also count.

## VDP Sprite Cache Behavior (from Kabuto hardware notes)

The VDP processes sprites in 4 phases per scanline:

**Phase 1 — Visibility Scanning:** Scans the internal Y/size/link cache (not VRAM) to find sprites on the upcoming scanline. Follows the link chain, processing one sprite per pixel (two per VDP cycle) for exactly 40 cycles. Results go into a 20-slot shift register. Link value 0 terminates scanning.

**Phase 2 — Attribute Fetching:** For each visible sprite from Phase 1, fetches the "second half" of the SAT entry from VRAM: X position (9 bits), tile/flags, palette, priority, horizontal mirror. These are re-read from VRAM every frame — not cached.

**Phase 3 — Tile Rendering:** Iterates through Phase 2 results, fetching 1-4 tiles per sprite from VRAM and rendering into a 320-pixel line buffer. A sprite with X=0 following one with X≠0 disables further sprite output (masking).

**Phase 4 — Display:** Line buffer output as a priority layer alongside Planes A and B.

**Key implications:**
- Y/size/link are cached via write-through — any CPU write to SAT VRAM addresses immediately updates the cache
- X/tile data is fetched fresh from VRAM each frame (Phase 2) — these can be changed mid-frame
- Changing the SAT base register (VDP reg 5) without rewriting data: cache retains old Y/size/link, but X/tile is read from new location (Castlevania: Bloodlines exploits this for water reflections)
- DMA to the SAT region updates the cache incrementally as each byte is written

---

## 1. Link-Order Cycling

### Technique

When >20 sprites land on one scanline, the VDP drops everything past the 20th in link-chain order. Rotating the link chain starting point each frame distributes dropout as flicker rather than permanent disappearance of the same sprites.

### Reference Findings

| Source | Implemented? | Details |
|---|---|---|
| Thunder Force IV | **YES** | Round-robin rotation via `add.w $F29A.w` — cycles which sprites get priority every 4 frames |
| S.C.E. | No | Fixed link chain 0→1→2→...→79→0, set at init, never rotated |
| sonic_hack (Sonic 2) | No | Simple incrementing counter d5 (0-79), no rotation |
| Batman & Robin | No | sprite_link_count tracks total, no cycling |
| Gunstar Heroes | No | No rotation mechanism found |
| Alien Soldier | No | No cycling found |
| Vectorman | No | Pre-computed DMA queue, no link rotation |

**Only Thunder Force IV implements this.** No Sonic engine (stock or modded) has ever used it.

### Online Findings

- CPU cost is minimal: one `addq` + `andi` to the starting link index per frame
- Since the SAT is rebuilt in RAM each frame anyway, the cost is a few extra instructions during SAT construction
- Global cycling is crude — it flickers ALL sprites, not just overflowing ones. Smarter approaches cycle only within scanline bands where overflow actually occurs
- A link value of 0 terminates the list — sprite 0 cannot be at the end of the chain

### Verdict: IMPLEMENT

Cheap (one add + mask per frame), high visual quality improvement under overflow. Our priority-band Render_Sprites already processes objects in band order — we can rotate the starting offset within the SAT output. Combined with scanline budgeting, this handles the visual degradation case gracefully.

**Implementation approach:** Add a `Sprite_Cycle_Offset` RAM variable. Each frame, `Render_Sprites` starts writing SAT entries at `Sprite_Cycle_Offset` instead of always index 0, wrapping at 80. Increment by 1 each frame. The link chain is rebuilt each frame anyway, so this just shifts which physical SAT slot each logical sprite occupies.

---

## 2. Scanline-Aware Sprite Budgeting

### Technique

During sprite rendering, maintain counters of how many sprites (and/or sprite pixels) overlap on each scanline. When a scanline's budget is exhausted, skip or deprioritize remaining sprites proactively rather than letting the VDP silently drop them.

### Reference Findings

| Source | Implemented? | Details |
|---|---|---|
| Thunder Force IV | Partial | Type-segregated pools (bullets, enemies, FX) with dedicated fast-path loops — implicit budget via pool size limits |
| Alien Soldier | Partial | Split dispatch: two-stage filtering by type flags, then routine index — objects checked against bounds before rendering |
| S.C.E. | No | Global 80-sprite hard limit only |
| sonic_hack (Sonic 2) | No | `cmpi.b #80,d5` — global limit, no per-scanline tracking |
| Batman & Robin | No | Global sprite_link_count threshold checks |
| Gunstar Heroes | No | No per-scanline tracking |
| Vectorman | No | Per-entry byte budget (2880 bytes/frame max), not per-scanline |

**No commercial Genesis game does full per-scanline sprite budgeting.** TF4 and Alien Soldier approximate it via pool segregation and type-based filtering.

### Online Findings

- Full per-scanline histogram for 224 scanlines × 80 sprites is expensive — a simplified approach with 8-16 scanline bands is much cheaper
- Most commercial games relied on careful art design (keeping sprites small, avoiding dense overlap) rather than software budgeting
- SGDK provides `SPR_enableVDPSpriteChecking()` — global count check only, not per-scanline
- Space Harrier II converts large foreground sprites to Plane A tilemap data to avoid sprite limits entirely
- The VDP's dot overflow flag (status register bit 6) detects overflow but doesn't indicate which scanline or sprites were affected
- Must account for sprite width, not just count — 10 sprites of 32px = 320 pixels = entire scanline budget used with only half the slot count

### Verdict: IMPLEMENT (simplified band-based approach)

Full per-scanline tracking is too expensive for the benefit. Instead, use a band-based approach:
- Divide the screen into 8 vertical bands (28 scanlines each)
- During Render_Sprites Phase 2, count sprites per band based on Y position + height
- When a band hits a threshold (e.g., 16 sprites), skip lowest-priority remaining sprites for that band
- Combined with link-order cycling, overflow degrades as even flicker rather than permanent dropout

**Rejected alternative:** Per-scanline pixel counting. Too expensive — requires iterating sprite width × height coverage for every piece. The 20-sprite count limit triggers first in typical Sonic gameplay (small sprites), making pixel counting unnecessary.

---

## 3. Sprite X=0 Masking

### Technique

A sprite at X position 0 in the SAT stops the VDP from rendering all subsequent sprites (in link order) on the scanlines that sprite covers. Zero CPU cost — just place a sprite entry with X=0 at the right position in the link chain.

### Two Modes (from Charles MacDonald / Sonic 3 Unlocked blog)

**Mode 1 (simple):** A sprite with X=0 masks all lower-priority sprites on its scanlines. Straightforward.

**Mode 2 (X=1 trigger):** Requires both X=0 AND X=1 sprites on the same scanline. Enabled when the VDP encounters X=1, persists until frame end. Only Galaxy Force II is known to use this mode.

### Reference Findings

| Source | Implemented? | Details |
|---|---|---|
| S.C.E. | **YES** | Dedicated `Obj_SpriteMask` object — sets `Spritemask_flag`, post-processing in Render_Sprites finds sprite with Y=$7C0 and sets its X=0, link=0 |
| Sonic 2 | Avoids it | `bne.s +; addq.w #1,d0` — bumps X=0 to X=1 to prevent accidental masking |
| Alien Soldier | Likely | Known for X=0 masking, bounds checking code consistent with it |
| Others | No | Not found in Batman & Robin, Gunstar, Vectorman, TF4 |

### Online Findings

- Used in: Sonic 2 title screen (masking behind wing emblem), Sonic 3 bonus stage, Castlevania: Bloodlines, Raiden Trad, Alien Soldier
- Sonic 1 title screen does NOT use X=0 masking — instead floods with garbage sprites to hit the 20-sprite limit
- The masking sprite consumes one of the 20 per-scanline slots and counts against the 320-pixel budget
- Many emulators historically implemented this incorrectly (Sega's own docs were inaccurate)
- The masking sprite's height determines which scanlines are affected

### Verdict: IMPLEMENT

Zero CPU cost, useful for HUD/status bar clipping without needing the Window plane. Our engine already avoids X=0 (bumps to 1) in the piece loops — we just need a mechanism to intentionally place masking sprites when needed.

**Implementation approach:** Add a `SpriteMask_Insert` routine that places a tall (4-cell) sprite at X=0 at a specific position in the link chain. Used during status bar / HUD rendering to prevent gameplay sprites from bleeding into the HUD area. Link chain ordering ensures masking sprite appears after HUD sprites but before gameplay sprites.

---

## 4. Sprite Multiplexing

### Technique

Rewrite SAT entries mid-frame via HBlank to display more than 80 visual sprites from fewer physical SAT entries. Since the VDP caches Y/size/link but re-reads X/tile each frame, mid-frame writes to X/tile take effect immediately.

### Reference Findings

| Source | Implemented? | Details |
|---|---|---|
| Vectorman | **YES** | Double-buffered pre-computed DMA queue — main loop builds VDP register write sequences, VBlank drains them. Max 54 DMA entries/frame |
| Thunder Force IV | **YES** | Direct VBlank DMA construction + round-robin rotation |
| Alien Soldier | **YES** | Pre-built display lists at $BE00, VBlank writes without computation |
| Gunstar Heroes | Partial | Direct VBlank DMA, similar to TF4 |
| S.C.E., Sonic 2 | No | Single SAT DMA per frame |

### Online Findings

- **Stone Protectors** uses it for falling snow — 3 physical sprites rewritten every 8 scanlines
- **Castlevania: Bloodlines** switches SAT base register mid-frame for water reflections (exploits cache/VRAM split)
- VRAM bandwidth during active display (H40): only 18 bytes per scanline — approximately 2 full SAT entry updates per scanline
- HBlank handler must execute within ~92 68000 cycles per scanline
- Constraint: multiplexed sprites cannot share scanlines
- CPU cost competes directly with gameplay logic

### Verdict: DEFER

Too complex and constrained for a Sonic game. The technique works best for simple, repetitive effects (rain, snow, starfields) where sprites are small and never share scanlines. A Sonic game has diverse objects at varying positions — the no-shared-scanline constraint is too restrictive. The CPU cost of per-scanline HBlank handlers competing with gameplay logic is also problematic.

**If needed in the future:** Particle weather effects (rain/snow) could use 3-5 multiplexed sprites rewritten every N scanlines. Add to DEFERRED_WORK.md.

---

## 5. Sprite LOD (Level of Detail)

### Technique

Use simplified mappings (fewer sprite pieces) for objects far from the camera center. Reduces per-scanline sprite consumption for distant/unimportant objects.

### Reference Findings

**No commercial Genesis game implements explicit sprite LOD.** Related techniques:
- Space Harrier II: pre-drawn sprites at multiple sizes, converts large foreground sprites to Plane A tilemap
- Dynamite Headdy: 6 pre-drawn size variants for scaling illusion
- Yu Yu Hakusho: shifts component sprites closer together for shrinking effect

### Verdict: REJECT

The Genesis screen is 320×224 pixels. Objects are never far enough away for reduced detail to be unnoticeable. The complexity of maintaining multiple mapping sets per object is not justified by the small sprite piece savings. Sonic sprites are typically 4-6 pieces, enemies 1-4 — reducing by 1-2 pieces is marginal.

Removed from ENGINE_ARCHITECTURE.md §3.5.

---

## 6. Pre-Formatted SAT Entries

### Technique

Store VDP-ready sprite data in object RAM or a staging buffer to avoid field reordering during rendering. Instead of converting mapping format → SAT format each frame, keep data in SAT format and just copy it.

### Reference Findings

| Source | Implemented? | Details |
|---|---|---|
| Alien Soldier | **YES** | Pre-built SAT entries at RAM $BE00 — 64 entries written during main loop, VBlank copies to VRAM without computation |
| Vectorman | **YES** | Pre-computed complete VDP register write sequences — 5 VDP register writes per DMA entry, stored in RAM buffer at $FFFFE49E |
| All others | No | All rebuild SAT from object mappings each frame |

### Analysis

Our engine already gets most of the benefit through **VDP-order mappings** — our mapping format matches the SAT entry layout (Y offset, size, pad/link, tile attrs, X offset = 8 bytes, same order as VDP SAT). The only per-piece work in Render_Sprites is:
1. Add screen position to Y/X offsets
2. Add VDP offset (128) to Y/X
3. Add art_tile base to tile attributes
4. Set link field (incrementing counter)
5. Handle flip variants (negate offsets, toggle bits)

Items 1-4 are unavoidable — even pre-formatted entries need position updates every frame (objects move). Item 5 is already handled by our 4 specialized piece loops. The marginal benefit of further pre-formatting is small.

### Verdict: NO ACTION NEEDED

Our VDP-order mapping format already eliminates the field reordering that makes other engines' BuildSprites expensive. The remaining per-piece work (position add, VDP offset, art_tile add, link counter) cannot be pre-computed because it changes every frame. No further optimization needed here.

---

## Summary: Implementation Plan

| Technique | Decision | Task | Priority |
|---|---|---|---|
| Link-order cycling | **IMPLEMENT** | Task 20 | High — cheap, high visual quality |
| Scanline-aware budgeting | **IMPLEMENT** (simplified) | Task 21 | Medium — band-based approach |
| Sprite X=0 masking | **IMPLEMENT** | Add to Task 20 or new task | Medium — zero cost, HUD clipping |
| Sprite multiplexing | **DEFER** | Add to DEFERRED_WORK.md | Low — complex, constrained |
| Sprite LOD | **REJECT** | Remove from architecture doc | N/A — not worthwhile |
| Pre-formatted SAT | **NO ACTION** | Already achieved via VDP-order mappings | N/A |

### Architecture Doc Updates (Task 23)

- Remove Sprite LOD from §3.5 (evaluated and rejected)
- Add note that pre-formatted SAT is achieved via VDP-order mapping format
- Move sprite multiplexing to DEFERRED_WORK.md with weather/particle use case
- Add VDP sprite cache behavior section (Phase 1-4 pipeline)
- Add VDP per-scanline limits (20 sprites AND 320 pixels, whichever first)

---

## Sources

### Disassembly References
- S.C.E.: `Engine/Objects/Render Sprites.asm`, `Engine/Objects/Draw Sprite.asm`, `Objects/Main/Sprite Mask/Sprite Mask.asm`
- Batman & Robin: `disasm/code/engine/core.asm` (sprite_link_count), `disasm/OBJECT_SYSTEM.md`
- Thunder Force IV: `ANALYSIS.md` line 159 (round-robin $F29A.w), lines 116-122 (type-segregated pools)
- Alien Soldier: `code/disasm.asm` lines 1152-1280 (SAT pre-building at $BE00), lines 1254-1269 (bounds checking)
- Vectorman: `ANALYSIS.md` lines 114-133 (DMA queue), $FFFFE49E (pre-built buffer)
- Gunstar Heroes: `code/disasm.asm` (link field $58 for multi-part bosses)
- sonic_hack: `code/engines/build_sprites.asm` (X=0 avoidance at lines 192-196)

### Online Sources
- Kabuto hardware notes (via plutiedev.com) — VDP sprite cache 4-phase pipeline
- plutiedev.com/sprites — SAT format, limits, cache behavior
- Charles MacDonald VDP Documentation v1.5f — sprite masking modes
- Sonic 3 Unlocked blog — X=0 masking modes 1 and 2
- SpritesMind forum — H32/H40 limits, VRAM HBlank bandwidth (18 bytes/scanline)
- Raster Scroll (rasterscroll.com) — Stone Protectors multiplexing, Castlevania SAT switch
- Blast Processing Retrospectives — multiplexing demo, VRAM write constraints
- SGDK sprite_eng.h — modern homebrew sprite management approach
