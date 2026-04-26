# Multi-region VRAM Packing Research (§2 A.2)

**Date:** 2026-04-26
**Driver:** §2 Phase 2 Layer A.2 needs to spill the deduped tile pool into a secondary VRAM region when region 1 ($0000-$BFFF, 1536 tiles) overflows. The candidate is Plane B's off-screen nametable rows.

## Sources reviewed

**Reference disassemblies (all 7 per CLAUDE.md):**
1. **S.C.E.** — `Engine/Constants.asm` defines `VRAM_Plane_A_Name_Table = $C000` (extends to $CFFF), `VRAM_Plane_B_Name_Table = $E000` ($E000-$EFFF). Uses **64×32 planes** (8KB each? no — actually 4KB each at this 32-row height; $C000-$CFFF is 4KB). Has `$D000-$DFFF` as a 4KB gap between plane A and plane B available for art. HScroll table at $F000, sprite attribute table at $F800. **Three free regions** ($D000-$DFFF = 128 tiles, $F380-$F7FF ≈ 36 tiles, $FA80-$FFFF ≈ 44 tiles).
2. **sonic_hack** — `VRAM_Layout.asm` defines `VRAM_ScrollPlane = $600-$67F` (tile slot units → byte $C000-$CFFF). Same 64×32 design as S.C.E.; sprite tiles live in $240-$5FF zone pools (tile slots), with the Plane A nametable bracketed by free art regions on either side.
3. **Batman & Robin** — `code/init/init.asm:` writes `$9001` to VDP register $90. **64×32 planes**, statically configured. No off-screen-art trick used; their architectural difference is "uncompressed art everywhere, procedural effects" (per `ART_AND_COMPRESSION.md`) rather than VRAM cleverness.
4. **Vectorman** — `code/disasm.asm` shows BOTH `move.w #$9001, $c00004.l` AND `move.w #$9011, $c00004.l` at different scenes. **The only commercial Genesis game that dynamically switches between 64×32 and 64×64 plane sizes.** Confirms our architecture doc's Vectorman reference. Their use case is presumably scene-specific: 64×32 for normal play (more art slots), 64×64 for cinematic / vertically-rich scenes.
5. **Thunder Force IV** — `ANALYSIS.md` covers VRAM-related code generically (DMA, mapping data) but no off-screen embedding pattern.
6. **Gunstar Heroes** — same as Thunder Force IV: ANALYSIS describes DMA mechanics but nothing on packing strategies.
7. **Alien Soldier** — symlinks to gunstar's ANALYSIS.md; no separate analysis. Alien Soldier is famously a Treasure tour-de-force but the relevant tricks are sprite-multiplexing-class, not VRAM-region embedding.

**Online & community sources:**
8. **SGDK `vdp.h`** — supports 32/64/128 plane sizes flexibly. Sprite attribute table + HScroll table have alignment constraints (multiples of $400 in H40, $200 in H32). $F800 (our region 2 base) is a multiple of $400 = valid for any of these tables if relocated. Confirms our region-2 base is alignment-clean.
9. **plutiedev `vdp-setup`** — mentions VDPREG_SIZE register $9000 and value $01 in setup code but doesn't expand on plane-size tradeoffs. **Not covered.**
10. **plutiedev `writing-video`** — focuses on VDP write mechanics; doesn't address VRAM layout strategies. **Not covered.**
11. **md.railgun.works `VRAM`** — covers VDP function and Mega Drive/32X implementations but **does not address layout strategies**, off-screen embedding, or character-DMA constraints.
12. **plutiedev `scrolling-the-screen`, `scrolling-other-techniques`, `foreground`** — all 404. Pages don't exist at the URLs implied by site index.
13. **segaretro `Memory_map`** — 403 forbidden.
14. **gendev.spritesmind.net** — 503 service unavailable for forum search.

The Genesis homebrew/dev community appears to **not** document the "embed art in off-screen nametable rows" technique because it's specific to the 64×64 plane case, which is rare. Most guidance assumes 64×32 (the dominant choice) and treats $D000-$DFFF (the inter-plane gap) as the free art region.

## Region-2 boundary decision

**Chosen: Option B — region 2 = $F800..$FFFF, 64 tiles (16 nametable rows × 128 bytes / 32 bytes per tile).**

The decision is grounded in three calculations against current OJZ act 1 setup:

1. **Camera-Y reach.** OJZ act descriptor sets `cam_max_y = 128` pixels. Bottom of the visible 224-px viewport = camera_y + 224 = max 352 px = nametable row **44** (352 / 8). Rows 45+ of Plane B are guaranteed off-screen for any camera position the act allows.
2. **Available rows.** Row 45-63 = 19 rows × 128 bytes = 2,432 bytes = 76 tiles (Option A — tight to the actual visible boundary).
3. **Safety margin.** Row 48-63 = 16 rows × 128 bytes = 2,048 bytes = 64 tiles (Option B — 3-row safety margin protecting against future cam_max_y bumps up to 152 px).

Option C (row 56+, 32 tiles, 8-row margin) is over-conservative; we'd lose half the available capacity to a margin we don't need yet. Option A is too tight; it leaves zero headroom for future level designs that bump cam_max_y to e.g. 144 px (to allow the camera-pan/lookahead system to extend a bit further down). Option B is the right balance: 64 tiles is meaningful capacity (12.5% of the deduped pool's typical size on small zones), and 24 px of cam_max_y headroom covers any reasonable future change without forcing a plan revisit.

If a future level needs cam_max_y > 152, the constants in `tools/ojz_strip_gen.py` and `constants.asm` get bumped to e.g. row 56 (Option C) and we lose 32 of the 64 region-2 tiles. Acceptable; it's a one-line constants change with no code path differences.

## Character-DMA conflict result

**No conflict.** Region 2 lives entirely inside Plane B's nametable region ($E000-$FFFF). Per ENGINE_ARCHITECTURE.md §2.3, character sprite tiles DMA into Plane A's off-screen rows — that's the $C000-$DFFF region, which contains:
- Sprite Attribute Table at $D800-$DA7F (640 bytes; constants.asm and the s4budget output both confirm)
- HScroll Table at $DC00-$DF7F (896 bytes)
- Free fragments: $DA80-$DBFF (384 bytes / 12 tiles), $DF80-$DFFF (128 bytes / 4 tiles)
- The fragmented free space (16 tiles total in 2 chunks) is what character DMA presumably targets when the character system lands.

Plane B's nametable region ($E000-$FFFF) is currently empty of any other VDP table (sprite, hscroll, or window). The whole $F800-$FFFF region (Option B) is clean. No interference with character DMA.

Important: A.2 reserves $F800-$FFFF specifically. If a future system wants to use Plane B's off-screen rows for something else (e.g., a second sprite attribute table for water reflections, per ENGINE_ARCHITECTURE.md §7.6 Castlevania-style cache-switching), it must use a different range or coordinate explicitly with A.2. Document that constraint in the future system's plan.

## Engine constants to add

`constants.asm` (§2 A.2 block):
```asm
REGION1_TILE_CAPACITY   = 1536              ; primary art pool $0000-$BFFF
REGION2_VRAM_BASE       = $F800             ; Plane B off-screen, row 48+
REGION2_TILE_CAPACITY   = 64                ; ($10000 - $F800) / 32 = 64 tiles
```

`tools/ojz_strip_gen.py` (matching, must stay in sync):
```python
REGION1_TILE_CAPACITY = 1536
REGION2_VRAM_BASE     = 0xF800
REGION2_TILE_CAPACITY = 64
```

## Anything that changes ENGINE_ARCHITECTURE.md

**One small clarification.** §2.3 of the architecture doc says "off-screen rows of Plane B: available for future use" — A.2 is now using them. Update §2.3's table to reflect the new state:

Find the row in the §2.3 VRAM-layout table:
```
│ $700-$7FF     │ PLANE B NAMETABLE (256 tiles = 8KB, 64×64)         │
│ (256 tiles)   │   Visible area: ~40×28 tiles                       │
│               │   Off-screen rows: available for future use         │
```

Change the third line to:
```
│               │   Off-screen rows: rows 48-63 used by §2 A.2 region 2 (64 tiles)  │
```

No other arch-doc changes. The `Off-screen rows: available for future use` line was forward-looking (the doc anticipated something like A.2); A.2 is the something.
