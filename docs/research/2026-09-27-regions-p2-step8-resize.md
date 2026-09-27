# REGIONS-P2-STEP8 re-sized: halving the scroll plane under the stay-at-12 ruling

**Date:** 2026-09-27. **Branch:** `design/regions-p2-step8`, based on aeon `8c62c915`.
**Nature:** design research only. No engine file, tool or ROM byte changed. No emulator was run.
**Scripts:** `docs/research/2026-09-27-regions-p2-step8/vram_step8.py` and `bg_plane_budget.py`.
Both only read files, and every MEASURED figure below comes from one of them unless another
command is named.

Labels: **MEASURED** means computed in this session from a committed file or a donor tree, with
the command given. **DERIVED** means arithmetic on measured or declared values, with no runtime
assumption. **INFERRED** means it depends on runtime behaviour or intent that I did not observe.
**QUOTED** means taken from a named earlier document and not re-derived here.

---

## 0. Short answer

1. **Step 8 frees 256 tiles, not 384 and not 128. The window plane costs nothing.**
   - At 64x32 the planes free two 128-tile runs, `$D000-$DFFF` and `$F000-$FFFF`.
   - The window is disabled at boot (`reg $11 = $00`, `reg $12 = $00`, MEASURED) and no
     engine or game code ever writes those registers (MEASURED by grep). So the VDP never
     reads any byte of the window's nametable. Its base can stay at `$F000` pointing into
     object art at zero cost.
   - S3K does the same thing, pointing its disabled window at `$8000`, which is art. S.C.E.
     points its window at Plane A's base `$C000`.
   - The "384" was 128 from the cache plus these 256 planes. It never included the window.
     With the cache held at 12 pages, **step 8 can promise objects +256 tiles.**
   - One tool change is part of this: `vram.toml` has to stop charging the window a full
     128-tile run once it no longer overlays Plane B (§2.3).
2. **Object room under stay-at-12:**
   - **142 tiles today → 398 after step 8.** Counting the 12 test-art tiles, as the
     2026-09-17 audit does, it is 154 → 410. The card's own cut gives 152 → 408.
   - The plan the owner originally picked promised about 536. This is **128 tiles short of
     that**, which is exactly the retired cache cut.
   - The audit's free "Tier 1" savings (62 tiles, all still valid on today's map) add on top:
     **460 / 472**.
3. **Halving the plane costs real background capability, and the woven mega-act uses it.**
   - The 32 spare Plane B rows are the background streamer's slack. At 32 rows the streamer
     keeps **1 row** above the screen and **2 below**. At 64 rows it keeps 17 and 18 (DERIVED
     from `bg.emp`'s own formula).
   - A sudden jump in the background scroll is invisible today up to 17 rows (136 px). At 32
     rows anything over 1 row (8 px) shows.
   - A streamed background can carry per-column wobble from **-8 to +17 px** only. Today the
     range is ±136. The shipped rocking effect needs ±20 px, and the perspective floor needs up
     to +31 px.
   - Only EHZ and CNZ among the Sonic 2 backgrounds would still fit in one plane. MCZ, OOZ and
     Metropolis (which repeats every 512 px) fit in one plane at 64 rows but not at 32. That
     removes the proposed "one-plane" exemption the woven layout's 384-px tunnels are waiting on.
4. **Size: L.** It is six steps, three of which (the guards, map-space band tops, windowing the
   act-default background) are worth doing at 64 rows too. The flip itself is M and moves
   canonical bytes.
5. **My pick:**
   - Take the audit's Tier 1 now (S, +62).
   - Build the three prerequisites that pay off at either plane size.
   - **Flip the plane when the first real object set is measured to need more than about 200
     tiles.** Today no act places a real badnik, so there is nothing to measure yet.
   - The owner asked for this tonight, so §6 puts it to him as a card rather than deciding it
     here.

---

## 1. Today's VRAM map, read from source

**Command:** `python3 docs/research/2026-09-27-regions-p2-step8/vram_step8.py`. It parses
`games/sonic4/vram.toml`, which is the placement contract that `tools/gen_vram_map.py` checks and
the build consumes.

**Check that the map is the live one:**
`python3 tools/gen_vram_map.py --game sonic4 --emp <scratch copy> --map-doc <scratch> --py <scratch>`
printed `sonic4 OK — 23 regions, 1 free tiles` and exited 0. All three regenerated files were
byte-identical to `docs/generated/vram-map-sonic4.md`, `tools/vram_map.py` and
`games/sonic4/config/constants.emp`. **MEASURED.**

| tiles | bytes | n | region | category |
|---|---|---|---|---|
| 0-767 | $0000-$5FFF | 768 | `fg_art_pool` | FG art cache (12 pages x 64) |
| 768-895 | $6000-$6FFF | 128 | `spare_nametable` | reserved nametable (no register points here) |
| 896-911 | $7000-$71FF | 16 | `dust_puff` | object |
| 912-923 | $7200-$737F | 12 | `dust_spindash` | object |
| 924-927 | $7380-$73FF | 4 | `ring_sparkle` | object |
| 928-956 | $7400-$779F | 29 | `insta_shield` | object |
| 957-958 | $77A0-$77DF | 2 | `debug_preset_readout` | debug tag |
| 959 | $77E0-$77FF | 1 | [free] | the only free tile |
| 960-991 | $7800-$7BFF | 32 | `character_window` | character |
| 992-999 | $7C00-$7CFF | 8 | `test_obj` | test art |
| 1000-1015 | $7D00-$7EFF | 16 | `ring_placeholder` | object |
| 1016-1019 | $7F00-$7F7F | 4 | `test_marker` | test art |
| 1020-1023 | $7F80-$7FFF | 4 | `debug_lab_name` | debug tag |
| 1024-1399 | $8000-$AEFF | 376 | `bg_region` | BG arena (band_reserve 56 inside) |
| 1400-1447 | $AF00-$B4FF | 48 | `waterline_strips` | BG effect art |
| 1448-1471 | $B500-$B7FF | 24 | `spring` | object |
| 1472-1491 | $B800-$BA7F | 20 | `sprite_table` | VDP table (reg $05) |
| 1492-1500 | $BA80-$BB9F | 9 | `tails_appendage` | character |
| 1501-1503 | $BBA0-$BBFF | 3 | `debug_bganim_tag` | debug tag |
| 1504-1531 | $BC00-$BF7F | 28 | `hscroll_table` | VDP table (reg $0D) |
| 1532-1535 | $BF80-$BFFF | 4 | `debug_raster_tag` | debug tag |
| 1536-1791 | $C000-$DFFF | 256 | `plane_a` | nametable (reg $02) |
| 1792-2047 | $E000-$FFFF | 256 | `plane_b` | nametable (reg $04) |
| (1920-2047) | $F000-$FFFF | (128) | `window_plane` | overlay on `plane_b` (reg $03), disabled |

- **Coverage:** 2048 tiles are covered exactly once, none uncovered, none double-counted
  (overlays excluded). MEASURED.
- **By category (sums to 2048, MEASURED):**
  - FG cache 768
  - nametables 512
  - BG arena 376
  - object and character art **142**
  - reserved nametable 128
  - BG effect art 48
  - VDP tables 48
  - debug tags 13
  - test art 12
  - free 1
- **The object figure depends on the cut, and three cuts are in circulation:**
  - **142** = object and character regions only. This is the cut used in this document.
  - **154** = 142 plus the 12 test-art tiles (the 2026-09-17 audit's cut).
  - **152** = the 128-tile 896..1023 neighbourhood plus the spring 24 (the owner's card's cut).
  - All three describe the same map. When a number goes to the owner, name the cut beside it.
- **The engine agrees with the map.** Read from `engine/system/constants.emp`:
  - `PLANE_H_CELLS 64`, `PLANE_V_CELLS 64`
  - `VRAM_PLANE_A $C000`, `VRAM_PLANE_B $E000`, `VRAM_WINDOW $F000`
  - The register byte for the plane size (`VDP_REG_PLANE_SIZE = $11`) is now pinned to those
    constants by an `ensure` (`constants.emp:1286`).
  - The 2026-09-09 plane-size doc's worry that `boot_data.emp`'s `$11` was hand-typed is
    **closed**: `boot_data.emp:190` now writes `VDP_REG_PLANE_SIZE`.

**Where docs disagree with source (checked):**

- `DEFERRED_WORK.md` VRAM-NEIGHBOURHOOD says `bg_region` is 388 and objects are "~128". Source
  says 376 and 142/154. The audit had already corrected both.
- `docs/research/2026-09-09-plane-size-lever.md` §3.3 counts `spare_nametable` in a "384 from the
  planes". **Wrong.** At 64x32 the freed tails are `$1000`-aligned, not `$2000`-aligned (next
  table), so they cannot host the Plane Z that `spare_nametable` is held for. The audit (§3.1)
  already recorded this. I confirm it from the alignment arithmetic.
- `docs/superpowers/designs/2026-09-03-vram-replan-item0-design.md` Option C, point 3, says the
  bob amplitude ladder "goes **empty**" at 64x32. **Wrong.** Using the engine's own
  `bob_shift_min` and `bob_shift_max`:
  - At 288 origins the smallest legal shift is 1. At 32 origins it is 4.
  - The largest legal shift stays 8, so the ladder shrinks from 1..8 to 4..8. It does not
    empty.
  - At shift 4 the peak excursion is 256 >> 4 = 16 px.
  - No shipped scene uses the bob. `grep -rn bob games/sonic4/data` finds nothing, and only
    poison fixtures and the equivalence proof name `bob_shift`. DERIVED + MEASURED.
- Option C's other two points (`PLANE_B_SPAN == 512` pinned, `VSCROLL_BG_MAX` collapsing to 32)
  were true when written. Since regions part 2 steps 4 and 5, **the background scroll ceiling
  comes from each region's map height** (`rg_bg_span`, `structs.emp:124-131`), and
  `VSCROLL_BG_MAX` is only the fallback for a region that sets no height.
  - That moves the cost out of "the background cannot scroll" and into the streamer's slack
    (§3).

---

## 2. What step 8 frees, and the window question settled

### 2.1 The arithmetic (DERIVED from source constants, MEASURED by `vram_step8.py`)

- At 64x32 each plane is 64 x 32 x 2 = 4096 B = 128 tiles. The bases stay at `$C000` and
  `$E000`, which are the only `$2000` slots the planes can use without moving art.
- The freed runs:

| run | tiles | size | legal base for (granules from `engine/vdp.emp` `VdpBase`) |
|---|---|---|---|
| `$D000-$DFFF` | 1664-1791 | 128 | Window, SAT, HScroll (not Plane A/B: they need `$2000`) |
| `$F000-$FFFF` | 1920-2047 | 128 | Window, SAT, HScroll |
| **total** | | **256** | |

- The H40 window granule of `$1000` is confirmed online. md.railgun.works (VDP page, fetched
  2026-09-27) says "WD11 is ignored if the display resolution is 320px wide (H40), which limits
  the Window nametable address to multiples of $1000". `engine/vdp.emp` encodes the same value.

### 2.2 The window: why it costs 0 today and what it would cost enabled

- **What the VDP reads.** It fetches window nametable cells only for screen cells the window
  covers.
  - In H40 each window row is 64 cells, a 128-byte stride, which is 4 tiles of VRAM per row
    (INFERRED from the standard VDP spec, consistent with the `$1000` granule).
  - With `reg $11 = $00` and `reg $12 = $00` the window covers no cell, so it reads **0 bytes**.
    MEASURED: `boot_data.emp:191-192`.
  - A grep over `engine/` and `games/` for `$91xx`/`$92xx`/`$83xx` writes, `VRAM_WINDOW` and
    `Window` finds only the boot table, the constant and the `VdpBase` enum. The debugger's
    register dump in `error_handler.emp` is data. So nothing turns the window on at runtime.
    MEASURED.
- **What that means for step 8.** Today the window base `$F000` sits inside Plane B's tail. At
  64x32 it sits in the freed `$F000` run.
  - It can stay there, disabled, while object art occupies the same bytes. Cost: **0 tiles**.
  - The reference games do the same, MEASURED from their register tables:
    - **S3K** in-game: window `$8320` = `$8000`, which is art (`sonic3k.asm:1347`).
    - **S.C.E.**: window = `$C000`, Plane A's base (`Engine/Core/VDP.asm`).
    - **S2**: window `$F000` in its boot table (`s2.asm:291`), with both window registers
      written `$00` in-game (`s2.asm:1452-1453`). What S2 keeps at `$F000` was not
      re-verified here.
    - None of the three reserves VRAM for a window it does not use.
- **If a future effect enables the window**, its footprint is the rows it covers x 4 tiles,
  starting at those rows' own offset from the base:

| window rows enabled | VRAM read |
|---|---|
| 4 (a HUD strip) | 16 tiles |
| 16 (effects item 10c's top band) | 64 tiles |
| 28 (full screen) | 112 tiles |

  - It would come out of whichever freed run it points at, so a 16-row band would leave step 8
    at +192 for objects.
  - That is an owner decision for whenever the window gets a consumer. It does not change what
    step 8 can promise today.
- **So the booked 128-tile disagreement resolves like this.** The replan design's "the window
  keeps its `$F000` base" is right. The card's "384" never counted the window (it was cache 128
  plus planes 256). **Step 8's promise is +256**, with the window disabled and parked on a freed
  run.

### 2.3 The one piece of accounting that must change with it

- `vram.toml` declares `window_plane` as `tiles = 128, overlay_with = ["plane_b"]`.
- At 64x32, Plane B ends at tile 1919. The overlay stops overlapping anything, and
  `gen_vram_map.py` would then charge the window a full 128-tile run. That silently eats half of
  what step 8 frees.
- **The fix.** Declare the window's footprint from its register fold:
  - tiles = (rows enabled from `$11`/`$12`) x 4, which is 0 today.
  - Or let a disabled window overlay any region.
  - Either way `gen_vram_map.py` needs a small change: it has no concept of a zero-footprint
    base today.
- Booked as part of step 8a below. Without it, the obvious toml edit reproduces the 128-tile
  disagreement in the map itself.

### 2.4 What objects can be promised (MEASURED base, DERIVED sums)

| scenario | objects+characters (142 cut) | 154 cut | card's 152 cut |
|---|---|---|---|
| today | 142 | 154 | 152 |
| + step 8, window disabled (the promise) | **398** | 410 | 408 |
| + audit Tier 1 (C12 D16 F13 A9 I9 G3 = 62) | **460** | 472 | 470 |
| card's original plan (cache 10 + planes) | — | — | ~536 |
| + step 8 with a 16-row window band later | 334 | 346 | 344 |

- **Tier 1 is still valid.** `vram.toml`'s last change is `67458e39` (the spring side sheet),
  which is before the audit. `WATERLINE_H` is still `ROW_REMAP_H16` and `RING_ANIM_SPEED` is
  still 8 (MEASURED by grep). So the audit's 62 is still the number.
- **The freed tiles do not form one contiguous run.**
  - Two separate 128-tile runs is plenty: sprite tile indices are 11-bit, so any tile 0..2047
    is addressable.
  - `character_window` must not move: its base is baked into the replay hash.
- **The freed runs cannot become FG cache pages.**
  - A page frame's id is `tile >> PAGE_FRAME_TILE_SHIFT` (`constants.emp:464`), so frames are
    contiguous from tile 0. A 13th frame would be tiles 768-831, which is `spare_nametable`,
    not a freed plane tail.
  - The woven act's "13 in 108 windows" therefore cannot be paid from step 8. It can only be
    paid from `spare_nametable`, which the owner declined on 2026-09-10, or by trimming the
    tunnel art (woven doc §A.5). DERIVED.

---

## 3. What halving the scroll plane costs

`PLANE_V_CELLS` and `reg $10` are shared by both planes. There is no Plane-B-only halving.

### 3.1 Plane A (foreground): cheap, and it gets cheaper

- The plane-size doc's Part 1 still holds against today's source. Re-checked:
  - `ensure(SECTION_V_REACH_ROWS_MAX <= PLANE_V_CELLS - 1)` at `constants.emp:1001` reads
    29 <= 31 at 32 rows.
  - The vertical streamer's stop target is the viewport.
- The FG column entry (`Draw_TileColumn`, `8 + PLANE_V_CELLS*2`) drops from **136 B to 72 B**.
  At 2 columns a frame that gives back 128 B/frame of the VBlank DMA budget (DERIVED). That
  matters for any object-art streaming alternative (§4).

### 3.2 Plane B (background): the streamer loses its slack

**Command:** `python3 docs/research/2026-09-27-regions-p2-step8/bg_plane_budget.py`. It reads
`SCREEN_HEIGHT`, `BG_VSCROLL_MAX_STEP_ROWS` and `BG_WIPE_ROWS_PER_FRAME` from source and applies
`bg.emp`'s own formulas: `BG_SCREEN_ROWS = 224/8 + 1`, `SPARE = P - BG_SCREEN_ROWS`,
`LEAD = SPARE/2`, `want_top = (vscroll>>3) - LEAD`.

| plane rows P | span | spare | lead above | below | streamed per-column VSRAM offset range | one-plane wrap budget | crossing wipe frames | FG column entry |
|---|---|---|---|---|---|---|---|---|
| 64 (today) | 512 | 35 | 17 | 18 | **-136 .. +145 px** | 288 | 16 | 136 B |
| 32 (step 8) | 256 | 3 | 1 | 2 | **-8 .. +17 px** | 32 | 8 | 72 B |

**Deriving the offset range.** A column shows lines `[v+o, v+o+223]`. The streamer holds rows
`[top, top+P-1]`. Taking the worst case over `v mod 8`:
- `o >= -8*LEAD`
- `o <= 8*(P-LEAD) - 231`

This assumes the tracker is exactly on target, which is guaranteed at steady state by the rate
clamp.

**Consequences, each DERIVED unless marked:**

1. **Scroll jumps.**
   - Today a background scroll discontinuity of up to 17 rows (136 px) lands inside rows the
     plane already holds. The tracker then catches up invisibly at 2 rows a frame.
   - At 32 rows the tolerance is **1 row (8 px)**.
   - The woven act's Metropolis/Chemical Plant seam puts the two background scrolls **112 px
     apart** (QUOTED, `DEFERRED_WORK.md` SHORT-TUNNEL-VSCROLL-RATCHET, 2026-09-27). That is 14
     rows: absorbable at 64 rows, a visible tear at 32 on any streamed map.
2. **The ratchet lever gets weaker.**
   - The booked fix for the woven act's 384-px seams is "skip the rate clamp when the region's
     map is one plane tall" (the same entry).
   - Sonic 2 background content heights (MEASURED, `bg_plane_budget.py` S2 section, chunk-level
     rule):

     | zone | content | repeat |
     |---|---|---|
     | EHZ | 256 px | — |
     | CNZ | 256 px | — |
     | MCZ | 512 px | — |
     | OOZ | 512 px | — |
     | CPZ | 896 px | — |
     | ARZ | 1536 px | — |
     | HTZ | 1664 px | — |
     | MTZ | 1920 px | repeats every 512 px |
     | WFZ | 1920 px | — |

   - **At 64 rows, EHZ, CNZ, MCZ and OOZ are one plane, and MTZ wraps exactly. At 32 rows only
     EHZ and CNZ are.** So the exemption covers fewer of the woven act's zones, and the seams
     need the crossing wipe instead.
3. **Vertical wobble effects.**
   - Rocking (`deform_sine(20, 64)`, offsets -20..+20) and the perspective floor (0..+31,
     QUOTED from the plane-size doc §2.3) both exceed -8..+17. **Neither can run on a streamed
     background at 32 rows.**
   - Rocking's full swing is 40 px, which needs (224+40+7)/8 + 1 = 34 held rows. A 32-row plane
     cannot hold that at any lead.
   - On a background that is exactly one plane (≤256 px) they still fit the 32-px wrap budget,
     with 1 px to spare. That is the plane-size doc's warning, unchanged.
   - **Recommendation regardless of step 8:** an `ensure` that caps authored vertical wobble
     against the envelope in the table.
4. **OJZ's own background becomes a streamed map.**
   - `zone_bg.bin` is 8192 B.
   - Rows 0-31 use 2048/2048 cells and 121 distinct tile indices.
   - Rows 32-63 use 2048/2048 cells and 248 distinct indices, and are not a copy of the top
     half. MEASURED.
   - So the act-default background is 64 rows of real art, and at 32 rows it has to be a tall
     map with `rg_bg_span = 512`.
   - Its perspective floor (rows 48-63) then shares the -8..+17 envelope (item 3). The floor's
     screen-anchored wobble needs up to +31, so **the OJZ floor scene breaks at 32 rows** unless
     its wobble is re-authored within +17. INFERRED from the envelope and the quoted figure;
     no emulator was run.
5. **Map-space band tops become mandatory.**
   - Step 4a masks `Parallax_Current_Vscroll_BG & (PLANE_B_SPAN-1)` (`parallax.emp:2180`), and
     band tops are plane lines 0..511. That is BG-BAND-PLANE-ANCHOR, open.
   - At 32 rows OJZ_Default's tops `[0, 64, 320, 384]` exceed the 256-line plane. The act
     default would alias on the plain release shape, not only in the DEBUG tall region.
   - `scene_dsl.emp` also inlines 512 at `:94`, `:1013-1019` (vsplit range), `:1063-1070`
     (rowRemap plane_y), `:2557` and `:3401-3405` (`scene_plane_line`).
6. **The act-default blit.**
   - `bg.emp:87` sets `BG_LAYOUT_SIZE = 64*64*2`, and its `ensure` pins that to exactly one
     plane.
   - `BG_Init` runs before `Camera_Init` (BG-BOOT-REGION-BLIT, ruled "route 1 stands").
   - At 32 rows either the act default is limited to 256 px, or `BG_Init` blits rows 0..31 and
     the windowed `Section_RedrawPlanes` (which already exists) corrects it before display-on.
   - The second option fits the standing ruling: `BG_Init` still writes a picture, just a
     windowed one. It needs the act blob format to become "taller than a plane" in the
     generators (`inject_editor_bg.py`, `ojz_strip_gen.py`, `perspective_floor_gen.py`).
7. **Absolute VSRAM values in the lab.**
   - `fx_vscroll_split` writes an absolute plane line: `$0043` at line 112, 222 and 170
     (`ojz_effects.emp:1086`, `:2465`, `:2693`).
   - Those values change meaning with the plane height. They are lab content, but each one needs
     re-checking by eye (tag **[RUNTIME-SPLIT]**).
8. **Gains.**
   - The crossing wipe halves: 16 → 8 frames at 4 rows/frame.
   - FG columns cost 64 B less each.
   - Tall backgrounds (CPZ's 896 px, which is cropped to 512 today and marked as an
     approximation in `clip_bg_lower.py`) become faithful as part of the same work, since every
     clip background becomes a streamed map anyway.

### 3.3 The hand-written sites

- **Pinned, so they fail loudly (MEASURED by reading the `ensure` messages):**
  - 17 sites in `engine/level/section.emp` (`:1522-1524`)
  - 10 sites in `engine/level/plane_buffer.emp` (`:842-849`)
  - the layout-size pin in `engine/level/bg.emp:98`
  - the reg `$10` pin (`constants.emp:1286`)
- **Silent. These are the dangerous ones:**
  - **`parallax.emp:715` `PLANE_B_CELL_ROWS = 64`** is still an independent literal. Its
    `ensure(PLANE_B_SPAN == 512)` passes after a `PLANE_V_CELLS` edit. It feeds
    `PLANE_B_SPAN`, `VSCROLL_BG_MAX`, `BG_VSCROLL_ROW_PX`, the bob ladder, and through
    `section.emp:33` the BG window blit. MEASURED by grep: no `ensure` ties it to
    `PLANE_V_CELLS`. The plane-size doc flagged this on 2026-09-09 and it is **still open**.
  - **`scene_dsl.emp`'s inlined 512s** (item 5). Its pin compares against `PLANE_B_SPAN`, so it
    inherits the silent literal above.
  - **Tools with a hard-coded 64-row or 8192-byte plane** (MEASURED,
    `grep -n 'PLANE_ROWS\s*=\|8192' tools/*.py`):
    - `bg_nt_gate.py:42`
    - `clip_bg_lower.py:61`
    - `crossing_witness.py:73`
    - `depth_onset_probe.py:478-479`
    - `boot_override_gate.py:314`
    - `perspective_floor_gen.py:188`
    - `gen_region_bg_showcase.py`
    - `inject_editor_bg.py:1059`
    - `bganim_vprobe_gen.py`
    - `clip_rom_bake.py:2070`
    - `clip_*` belongs to another lane tonight and was not touched.
- **`engine/system/buffers.emp`: unaffected.** Its only plane-geometry input is `PLANE_H_CELLS`
  (`:211`), which does not change. HScroll stays per-line at 896 B.
- **`engine/effects/*`: no plane-height literal** (MEASURED grep for 512/`$1FF`/63/`PLANE_`).
  The raster vocabulary reaches the plane only through `fx_vscroll_split`'s absolute value
  (item 7).
- **`engine/level/bg_anim.emp`: no plane-height dependency.** It touches no VSRAM (QUOTED from
  the plane-size doc, re-checked by grep).

---

## 4. Alternatives that free object VRAM without cutting the cache

Ranked against the woven act. The woven act has no objects in scope yet (QUOTED:
`clip_rom_bake.py` header, "Objects are out of scope for the whole first cut"). It does need BG
arena room (EHZ+HPZ+OOZ = 403 > 376, woven doc) and seam crossings that do not tear.

| rank | lever | tiles | cost | woven-act conflict | size |
|---|---|---|---|---|---|
| 1 | **Audit Tier 1**: ring 4-tile frame window (C 12), unreachable waterline tail (D 16), debug tags borrow `spare_nametable` in DEBUG (F 13), Tails appendage shares the insta-shield window (A 9), solid test art as 1 tile per colour (I 9), character window 32→29 (G 3) | **62** | 16 B/frame of DMA for C; a small `gen_vram_map.py` overlay rule for F; A breaks when a sidekick is on screen | none | S |
| 2 | **Step 8, the plane halving** | **256** | §3: 1-row BG slack, wobble envelope -8..+17, map-space bands, act-default windowing, 9 tools | **yes**: seam tears and weaker ratchet exemption (§3.2 items 1-2) | L |
| 3 | **Per-type DPLC for badniks** (stream each type's current frame into a peak-frame window, as the character and insta-shield already do) | sheet minus peak, per type | each animated type costs DMA every frame it changes; instances of one type on different frames need separate windows (the `dust_puff` reason); DMA headroom is 2,944 B/frame residual and the worst frame is already 32 B over (QUOTED, object-art-tier §1.5). Step 8's 128 B/frame FG saving is what would fund it | none | M per type |
| 4 | **Object-art residency tier** (per-section pool, demand loader; the Batman & Robin shape) | 0 today, largest future lever | L; needs palette-line work; BLOCKED on a real badnik set (QUOTED, object-art-tier, audit N) | none | L |
| 5 | **BG band reserve 56 → 0** (audit E) | 56 | owner dial; Aurora vendors `BG_TILE_CAPACITY` | **yes**: the woven act wants a *bigger* BG arena, not a smaller one | S |
| 6 | **Drop Plane Z, release `spare_nametable`** | 128 (or 2 FG pages) | owner declined 2026-09-10 | if reopened, the woven act's 13th page is the better use | S |
| — | Cache 12 → 10 | 128 | ruled out, `stay-at-12` | the woven act is at 12/12 | — |

**How the references budget object VRAM** (first-hand register reads above; the rest QUOTED
from `docs/research/2026-09-09-object-art-tier.md` §4 and the 2026-08-11 reference survey):

- **S2, S3K and S.C.E. all run 64x32 planes.** S3K keeps characters, rings, shields and dash
  dust in exactly the two plane tails step 8 would free:
  - `ArtTile_Player_1 $680`, `Player_2 $6A0`, `Ring $6BC` are in `$D000-$DFFF`.
  - `Shield $79C`, `DashDust $7E0` are in `$F000-$FFFF`, between HScroll `$F000` and the SAT
    `$F800` (`sonic3k.constants.asm:1090-1097`, `sonic3k.asm:1347-1357`). MEASURED.
  - So step 8's placement is the S3K placement.
- **Object art is budgeted per zone or act, by hand.** S2 has 147 zone-banded `ArtTile_*`
  constants, and address sharing is unenforced; tile `$0500` carries six meanings. S3K splits
  art into primary and secondary sets.
- **DPLC in the Sonic games covers players, Tails' tails and a few bosses.** Badniks are
  resident.
- **Batman & Robin** is the only one of nine trees with a refcounted, evicting object-art cache.
- **Treasure games (TF4, Gunstar, Alien Soldier)** fit Plane A, the window and Plane B together
  in `$C000-$EFFF` by using 64x32.
- **None of them keeps 64x64 planes.** Aeon's 64x64 is the outlier, and what it buys now
  (§3.2) is background streaming slack, which none of the references needed because none of
  them streamed a background taller than its plane under a per-column wobble.

---

## 5. Recommendation, sized per step

| step | what | size | changes canonical bytes? | useful at 64 rows too? |
|---|---|---|---|---|
| **8-T1** | Audit Tier 1 recut (62 tiles), one parcel | S | yes (C, D, I, G move art) | yes |
| **8a** | Guards first: tie `PLANE_B_CELL_ROWS` to `PLANE_V_CELLS`; derive `scene_dsl.emp`'s 512s; `gen_vram_map.py` window footprint from the `$11`/`$12` fold (0 today) plus a base-granule check (already booked as a rider); the 9 tools read plane geometry from `constants.emp` | S | no (zero-byte) | yes |
| **8b** | BG-BAND-PLANE-ANCHOR: band tops in map space | M | yes | yes (every tall map, CPZ 896) |
| **8c** | Act-default and clip backgrounds as tall streamed maps: `BG_Init` blits a window; the generators emit `rg_bg_span`; CPZ becomes faithful | M | yes | yes |
| **8d** | Wobble envelope: an `ensure` capping authored vertical wobble at the streamed envelope; re-author or retire Rocking and the floor's +31 | S-M | yes | the `ensure` yes |
| **8e** | The flip: reg `$10`, `PLANE_V_CELLS 32`, the 37 pinned sites, `vram.toml` re-cut with objects in `$D000`/`$F000`, effects-gate ritual, the crossing witness on the woven seams | M | yes | — |

**Total to +256: L.**

**Order:** 8-T1 and 8a now; 8b and 8c when the woven act needs faithful tall backgrounds (it
does, for CPZ and MTZ); 8d and 8e last, **triggered by a measured object need.** The trigger:
the first real badnik set's art (OBJ-ART step 1's per-envelope figure) exceeds what 8-T1 leaves,
roughly 62 tiles of new room.

**Why not flip tonight:** the object need is still unmeasured, while the flip's costs land on
the act currently being built (seam tears, the weaker ratchet exemption, the OJZ floor scene).
Everything the flip needs except the flip itself pays off at 64 rows, so building 8a-8c first
loses nothing and makes 8e an M.

---

## 6. Question for the owner

**STEP8-RESIZE.** *"With the art cache staying at 12, halving the scroll plane gives objects
256 more tiles, not 384. How do you want to get object room?"*

- **(a) Free savings now, plane later (MY PICK).**
  - Take the 62 free tiles now, which gives objects about 204 of 2048.
  - Build the plane-halving groundwork, which also makes tall backgrounds like Chemical Plant's
    faithful.
  - Flip the plane the day real badniks need more room. That day objects go to about 460.
  - *Cost:* one S parcel now, two M parcels of groundwork. Object room stays modest until
    badniks exist.
- **(b) Halve the plane now.**
  - Objects go to about 398, or about 460 with the free savings.
  - *Cost:* L of work before it lands.
  - In the woven act, a background can only absorb a 1-row (8 px) scroll jump instead of 17
    rows, so the Metropolis/Chemical Plant tunnels need the full crossing wipe.
  - Rocking backgrounds and the OJZ perspective floor must be toned down to about half their
    current wobble.
- **(c) Free savings only; keep the big plane.**
  - Objects get about 204, and nothing else changes.
  - *Cost:* the least work, and the least room. Fine for a showcase with few enemy types, not
    for a full zone's badnik set.

## 7. Runtime tags (for the controller; no emulator was run here)

- **[RUNTIME-SEAM]** After 8e, run `crossing_witness` on the woven seams at P=32 and count the
  glitch ticks against today's figures.
- **[RUNTIME-FLOOR]** The OJZ perspective floor and Rocking scenes at P=32: whether the
  -8..+17 envelope shows as garbage rows. It should, per §3.2 item 3.
- **[RUNTIME-SPLIT]** The three `fx_vscroll_split` lab entries' absolute `$0043` at a 256-line
  plane.

## 8. Found in passing (not fixed; files owned by other lanes or docs-only scope)

- `tools/clip_bg_lower.py`: `lower()`'s `info["painted_rows_px"]` reads **2048** for EHZ.
  - Its own docstring says EHZ paints 256 px.
  - The counting rule treats the tail's non-blank chunk as paint.
  - The chunk-level rule in `bg_plane_budget.py` reproduces the docstring's 256 (EHZ) and
    896 (CPZ).
  - MEASURED: `python3 -c "…clip_bg_lower.lower('s2disasm','EHZ')…"`.
- The replan design's "bob ladder goes empty" (§1) is wrong: the ladder shrinks from 1..8 to
  4..8. Not edited, because it is a historical design document; recorded here.
