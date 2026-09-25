# S2 clip act: a longer Chemical Plant, and each zone's own Sonic 2 background (scoping)

2026-09-25. Branch `research/s2clip-cpz-bgs`, base **`e9edfef3`** (origin/master after a fresh
`git fetch origin`). **Research only: no ROM-changing code.** Measurement scripts are committed
beside this file in `docs/research/2026-09-25-s2clip-cpz-bgs/`; section 7 lists the commands.

The owner flew row 7 (`481ac02e`, `s4.s2clip.bin`) and said, verbatim: *"We get to chemical
plant but it's very short, we should add more sections to see more of the level please. Also
the bgs should be from the games and such"*. That is two asks:

- **(A)** a longer Chemical Plant clip;
- **(B)** each zone shows its original Sonic 2 background.

Hub constraint for today: sigil card **d-35-revised** (the clip shape's own bank anchors) is
unanswered. Anything that needs it, or that grows past the room gate, is **filed here, not
built.**

No emulator was used. Every figure is a build, a listing, or donor data run through aeon's own
loaders. Anything visual is **TAGGED** for the owner's look.

---

## 0. The answer in five lines

1. **(A) cannot land today, in any size.** One more CPZ section adds **28,434 B** to both
   shapes. The plain shape then misses its reserve by **19,460 B**; it has 8,974 B to spare
   today. Two or more extra sections do not even LINK in either shape: the data run crosses
   the fixed `dac_banks` anchor at 0xA8000. So (A) is **d-35 work**, filed in §6.
   **Recommendation once d-35 lands:** extend CPZ to zone x 6143, its second checkpoint (A2).
2. **(B) can land today in the PLAIN shape, with one condition.** The clip act has to stop
   carrying Oracle Jungle's background, which it no longer shows. The OJZ background tiles
   get replaced by Emerald Hill's, and the OJZ animation bank goes. Estimated plain margin
   afterwards is **about 6.4 to 7.1 KB above the reserve**. Without dropping that bank it
   misses by about 1.0-1.8 KB. **The DEBUG shape stays exit 1**; it is already failing and
   accepted (S2CLIP-DEBUG-ROOM). B would make it fail by about 1.8-2.6 KB more. That growth is filed for
   the hub (§6).
3. **The brief is wrong on one point.** The clip act's background is **not** Oil Ocean.
   It is Oracle Jungle's own editor-authored background (`editor_bg_override.json`; Aurora's
   vendored copy is the `ojz_forest_flowers` source), drawn in Sonic 2 palettes. Oil Ocean's
   background exists only on one DEBUG region row of the canonical act. The clip act's region
   table replaces that row, so Oil Ocean never shows in the clip act. Its bytes do, though:
   see item 5.
4. **Faithful static backgrounds need no engine change.** EHZ's background is exactly one
   512-px period, 142 tiles, on its own palette lines. CPZ's is 215-238 tiles. Both fit the
   320-tile budget. **EHZ's parallax is expressible as data today:** 7 bands, a curve band
   and a ripple deform table. **CPZ's is only partly expressible.** Faithful CPZ needs two
   engine items that aurora's 2026-08-26 survey already named: backgrounds taller than 512 px
   with BG-space bands, and backgrounds wider than 64 cells. Both are larger, separate items.
5. **New lever, filed for the hub.** The clip DEBUG ROM carries **24,258 B** of the canonical
   act's DEBUG-only test backgrounds: the tall map, and the Oil Ocean showcase layout and
   tiles. The clip act never references them. Gating them off in clip shapes would put the
   DEBUG clip shape about +6.0 KB **above** its reserve before B, with no d-35. That is not
   mine to choose over the hub's ruling (B) = own anchors. §6.

---

## 1. Baseline, re-derived here (the control)

`FAST=1 S2CLIP=s2_ehz_cpz ./build.sh` at base `e9edfef3`, sigil at `$SIGIL_BUILD`:
- exit 0; ROM crc32 **`9a3533f1`**, 822,334 B. This is identical to the row-7 figure, so the
  base is the ROM the owner flew.
- FAST skips `bganim_room`, so I ran it by hand:
  `python3 tools/bganim_room.py --lst s4.s2clip.lst --rom s4.s2clip.bin --gate` gave exit 0.
- Packed end **0x99CF2**. Room under `dac_banks` 0xA8000 is **58,126 B**, which is
  **8,974 B** above `DATA_GROWTH_RESERVE` 49,152 B.

DEBUG baseline: not re-built here. The S2CLIP-DEBUG-ROOM row gives it as packed end 0xA074C,
**−18,252 B**, crc `441f1db0`. I read the installed `s4.s2clip.debug.bin` in the main checkout
and it is still crc `441f1db0`, 848,912 B, so its `.lst` is the one I read symbols from in
§4.5 and §6. My own A1 DEBUG build (§3) moved by exactly the same +28,434 B as plain, which
agrees with row 7's "the act adds the same bytes in both shapes".

**Units and the rule used below.** "Room" means the bytes under `dac_banks` beyond the
49,152-B reserve. The bank rule the gate prints is
`dac_banks >= align_up(packed_end + RESERVE 0xC000 + GRACE 0x8000, 0x8000)`. Check: at base,
0x99CF2 + 0x14000 = 0xADCF2, which aligns up to 0xB0000, and that is what the gate printed.

---

## 2. What the donor has

### 2.1 Chemical Plant act 1

**Extent.** Camera box x 0..10431 (`LevelSize` CPZ act 1 = `$0,$2780,$0,$720`,
`s2disasm/s2.asm:14739`). That is 5.09 aeon sections wide, with camera y up to 1,824.

**Painted foreground by 2048-px column** (`cpzextent.py`):

| zone x | painted y (px) |
|---|---|
| 0..2047 (**the clip today**) | 448..1727 |
| 2048..4095 | 0..1727 |
| 4096..6143 | 0..2047 |
| 6144..8191 | 128..2047 |
| 8192..10239 | 128..2047 |
| 10240..10431 | 1088..1279 (the act-end stub) |

So **4.09 sections of CPZ act 1 are not shown**: x 2048..10431, 8,384 px.

**Natural stretch ends.** The donor's own starposts (checkpoints) come from
`level/objects/CPZ_1.bin`, object id `$79` (`cpzobj.py`):

| starpost | x | y |
|---|---|---|
| 1 | 4272 | 1512 |
| 2 | 6104 | 1512 |
| 3 | 7936 | 744 |

The act has 153 objects. By 2048-px column they number 20 / 32 / 51 / 33 / 16 / 1. None of
them is in the clip act, which has no objects yet.

### 2.2 Backgrounds

**Where the data is.** Sonic 2 keeps each zone's background in the same `$1000`-byte layout
as the foreground: odd rows, 128 chunks wide. It uses the same chunk and block tables and the
same tile art (`tools/s2_donor.py:740` `load_bg_grid`, FINAL donor only). **The converter
does NOT extract it**: `tools/s2_zone_convert.py:45` says "no background". The one tool that
already lowers an S2 background is `tools/gen_region_bg_showcase.py` (`--donor s2-ooz`). It
re-quantises everything onto CRAM line 3 because the OJZ act's foreground owns line 2. **The
clip act does not need that step.** Each clip region already installs its donor zone's
complete lines 1-3 (row 7), so a background can keep its native palette bits.

Measured with `bgmeasure.py`, `bgcrop.py`, `bgtrans.py` and `fgentries.py`:

| | EHZ | CPZ |
|---|---|---|
| painted BG height | 2 chunk rows = **256 px** (rows 2+ are chunk 0) | 7 chunk rows = **896 px** |
| horizontal period | 4 chunks = **512 px = exactly 64 cells** (no invented seam) | 6 chunks = 768 px = **96 cells** (does not divide 64) |
| tiles, one plane's worth | 180 by index, **142** after flip-aware pixel dedupe | 64-col crop, 512 px tall: **215-238** depending on crop start (pixel dedupe saves nothing) |
| palette lines (cells) | line 2: 8,866 · line 3: 154 · line 1: 135 | line 2: 6,015 · line 3: 2,045 · line 1: 111 · **line 0: 2** |
| priority-bit cells | 0 | about 1,000-1,120 of 4,096 in a 64x64 crop (26%) |
| backdrop (`move.w #$8720` in `Level:`, `s2.asm` = line 2 entry 0) | **$C20** (sky blue) | $002 (near black) |
| colour-0 (transparent) pixels in the visible BG | **12.6%** of 224 x 512 px | 33.4% of 688 x 512 px |

The consequence of the last two rows: aeon's backdrop register is `$00`
(`engine/system/boot_data.emp:181`), which shows CRAM[0] = $000, black. EHZ's transparent sky
pixels would therefore show **black where Sonic 2 shows blue**. CPZ's would show $000 where
S2 shows $002, which nobody will see.

### 2.3 How Sonic 2 scrolls them

**`SwScrl_EHZ`** (`s2.asm:15253`). The background's vertical position is fixed
(`InitCam_EHZ` clears `Camera_BG_Y_pos`, and nothing moves it), so each screen line is a
background line. The horizontal scroll, screen line by line:

| lines | horizontal scroll | what it is |
|---|---|---|
| 0-21 | 0 | still sky |
| 22-79 | camX/64 | |
| 80-100 | camX/64 + ripple | 0-3 px from `SwScrl_RippleData`, a 32-entry cycle that advances 1 step every 8 frames |
| 101-111 | 0 | |
| 112-127 | camX/16 | |
| 128-143 | 3·camX/32 | |
| 144-221 | linear ramp from camX/8 to about 0.43·camX | 39 steps; lines 222-223 are unwritten in the original, a known bug |

**`SwScrl_CPZ`** (`s2.asm:17244`, `InitCam_CPZ` :15031):
- The background moves vertically at camY/4.
- Its horizontal bands are keyed by **background row** (16-px "line blocks"), not screen line:

| background rows | horizontal scroll |
|---|---|
| 0-287 | camX/8 |
| 288-303 (block 18) | camX/8 + the same ripple |
| 304 and below | camX/2 |

- The camera reaches y 1,824, so background Y reaches 456. The visible background rows
  therefore run to about 680, which is past 512.

**Palette cycles.** `PalCycle_EHZ` and `PalCycle_CPZ` exist and are not considered here (§5).

---

## 3. (A) A longer Chemical Plant

### 3.1 What changes

- **One file:** `games/sonic4/data/clips/s2_ehz_cpz/clips.json`.
  - `cpz_act1`'s `src_rect.w` and `dst_rect.w` get wider.
  - `act.grid_w` goes up.
  - `unpainted_remainder.x_from` moves.
  - The reachability declarations (`unbounded_fall.columns`, `floorless_columns`) are
    re-derived by `clip_reachability.py`.
- No tool and no engine code changes. Everything else is the existing bake.

### 3.2 Measured, per candidate

Method:
1. Write scratch manifests with `mkcand.py`: the row-7 manifest with only the CPZ width and
   the grid changed. They are **uncommitted and deleted afterwards**.
2. Run `FAST=1 S2CLIP=<id> ./build.sh` in both shapes, then `bganim_room.py --gate` on each
   listing (`runcands.sh`).
3. Load average during the runs was about 8-10, so no timings are quoted.

`clip_reachability` did not run. It is skipped under FAST, and the scratch declarations were
not re-derived. That changes no byte and no room figure.

| | CPZ zone x | ends | act grid (sections) | pool tiles / pages / ZX0 B | worst camera window | attr entries | plain: packed end → vs reserve | DEBUG |
|---|---|---|---|---|---|---|---|---|
| today | 0..2047 | | 7x3 (21) | 872 / 14 / 11,764 | 8 of 12 | 163 | 0x99CF2 → **+8,974** | −18,252 |
| **A1** | 0..4095 | 176 px before starpost 1 | 8x3 (24) | 1,030 / 17 / 13,994 | 11 of 12 | 217 | 0xA0C04 → **−19,460** | 0xA765E → **−46,686** |
| **A2** | 0..6143 | 40 px past starpost 2 | 9x3 (27) | 1,089 / 18 / 14,782 | 11 of 12 | 220 | **does not link**: `collision_data` run [0x8AB6E, 0xA8050) overlaps `dac_banks` at 0xA8000 | does not link |
| A3 | 0..8191 | past starpost 3 | 10x3 (30) | 1,100 / 18 / 14,958 | **12 of 12** (2,022 windows at the peak) | 220 | does not link (run ends 0xAE824) | does not link |
| A4 | 0..10239 | the act end | 11x3 (33) | 1,100 / 18 / 14,958 | **12 of 12** (4,002 windows) | 220 | does not link (run ends 0xB323A) | does not link |

Every other gate the bake runs had margin in every candidate:
- **Sections:** 24-33 of `MAX_ACT_SECTIONS` 48.
- **Attr set:** 217-220 of 255.
- **Pages:** 17-18 of `PAGE_TABLE_MAX` 256.
- **Art pool:** ZX0 ≤ 14,958 B, against `art_rom_report`'s 64 KB hard limit.
- **Z1** (zone separation) passed in every bake.
- **The page budget has 0 windows over.** But A3 and A4 sit at 12 of 12, which is the
  design's §3.3 "no headroom, static pass only" condition. **The binding budget is ROM room,
  as row 7 found.**

**Incremental ROM.** Each extra 2048-px CPZ section costs **19.5 to 28.4 KB**:
- A1 adds 28,434 B of packed data in both shapes.
- Between the failing links, the `collision_data` run end moved +26,580 B (A2 to A3) and
  +19,478 B (A3 to A4).

This is larger than row 7's "13-25 KB" because a CPZ section is 2,048 px tall and fully
painted.

### 3.3 Can it land today, without d-35?

**No, not at any width.** Every lever I found that does not need d-35 is smaller than A1's
19,460-B plain shortfall:
- **Drop OJZ's dead background-animation bank (about 8.2 KB).** That still leaves A1 11.3 KB
  short.
- **Gate the dead DEBUG blobs.** They are DEBUG-only, so they do nothing for plain.
- **Carve CPZ vertically.** A 2048-px-tall clip could be cut to the band the player actually
  traverses. The size of that band is unknown without a look, and I did not guess it. It is
  an owner option (§6).
- **Trade Emerald Hill length for Chemical Plant.** This is unmeasured, and it contradicts
  the owner's own S2CLIP-TRUNCATION ask ("didn't quite get to the end"). Owner option (§6).

### 3.4 What d-35 must provide, per candidate (rule arithmetic on the measured ends)

| candidate | plain `dac_banks` ≥ | DEBUG `dac_banks` ≥ |
|---|---|---|
| A1 | 0xB8000 (0xA0C04 + 0x14000 = 0xB4C04) | **0xC0000** (0xA765E + 0x14000 = 0xBB65E) |
| A2 | ≥ 0xC0000 (lower bound from the run end 0xA8050) | about one bank higher |
| A3 | ≥ 0xC8000 (lower bound) | about one bank higher |
| A4 | ≥ 0xC8000 (lower bound) | about one bank higher |

`sound_bank` = `dac_banks` + 0x10000 in every row.

For A2-A4 the value is a lower bound. Those builds did not link, so their packed end was
never measured. The DEBUG shape runs about 27 KB further along (A1: 0xA765E − 0xA0C04 =
27,226 B, the same as today).

**This corrects a number in the (B) pricing note.**
`docs/research/2026-09-25-clip-own-anchor-pricing.md` says the rule gives the clip pair
0xB8000/0xC8000 "today". That is right for today's act and **does not cover even A1's DEBUG
shape**, which needs 0xC0000/0xD0000. This is the argument for that note's M3 (a per-clip
`anchors.toml` overlay, re-derived per row) over any single fixed value.

### 3.5 Recommendation for (A)

**A2: extend CPZ to zone x 0..6143,** so the act runs to CPZ's second starpost:
- three sections of Chemical Plant instead of one;
- worst window 11 of 12;
- 220 of 255 attr entries;
- 27 of 48 sections.

Do it as the first zone row after d-35-revised lands both halves.
- **Anchors to derive for it:** plain at least 0xC0000; DEBUG higher, taken from its own
  built listing.
- **Fallback if the owner wants anchors kept low:** A1, ending 176 px short of starpost 1.
- **Avoid for now:** A3 and A4, until the 12-of-12 window has had a runtime confirmation
  (design §3.3, TAGGED foreground follow-up).

### 3.6 Parcel (dispatch after d-35-revised, both halves)

**A-1 (S).** Widen `s2_ehz_cpz` to A2:
1. Re-derive the `unbounded_fall` and `floorless_columns` declarations with
   `clip_reachability`.
2. Commit the clip's `anchors.toml` (d-35's aeon half) with values read from BOTH shapes'
   built listings.
3. Run `S2CLIP=s2_ehz_cpz ./build.sh` and the DEBUG shape. **Both must exit 0.**
4. Run `tools/landing_build.sh`; the canonical ROMs must be byte-identical.
5. **Tell the aurora lane** in the same turn (§5): its currency pin on this manifest goes red
   by design.

It is TAGGED for runtime because the new CPZ ground arrives without CPZ's tubes, platforms
and springs. Some of its geometry assumes objects that are not there. The owner should know
before he flies it.

---

## 4. (B) Each zone's own Sonic 2 background

### 4.1 What the engine can already express

**Per-region backgrounds are built** (`engine/structs.emp:132` `Region`):
- `rg_bg_layout`, `rg_bg_tiles` and `rg_bg_span`;
- the crossing overwrite and repaint (`engine/level/bg.emp` `BG_Stream_Update`, live in both
  shapes);
- the 16-frame palette cross-fade at the same crossing, already emitted by the clip bake.

**Parallax is data** (`engine/structs.emp:366` `parallax_config`,
`engine/level/parallax.emp:109-423`):
- up to 16 bands keyed by **plane line** 0..511;
- a per-band factor that is a shift pair (2^-a ± 2^-b), with 15 meaning a locked zero;
- per-band deform tables (256-byte signed, `CAP_MULTI_DEFORM_TABLE`, declared in sonic4:
  `GAME_SCANLINE_CAPS = 0x0FDE`);
- curve bands that ramp from one factor to another (`CAP_FACTOR_CURVE`, declared);
- `v_factor_bg` = 15 to lock the background vertically.

**A preset binds all of it.** `preset(pal:, parallax:, cycle:, ...)`
(`engine/effects/preset.emp:161`) takes the parallax config. Today the clip bake emits
`parallax: 0`.

Mapping Sonic 2 onto that:

| Sonic 2 behaviour | aeon, today | fidelity |
|---|---|---|
| EHZ BG locked vertically | `v_factor_bg = 15`, `v_offset = 0` | exact |
| EHZ lines 0-21 / 101-111 still | band factor s1=15 | exact |
| EHZ camX/64, camX/16 | s1 = 6, s1 = 4 | exact |
| EHZ 3·camX/32 | s1 = 4, s2 = 5, ADD | exact |
| EHZ ramp camX/8 → about 0.43·camX over lines 144-221 | curve band from 1/8 to 7/16 (s1 1, s2 4, SUB) | S2 steps every 1, 2 or 3 lines; the curve is per-line Bresenham. Near-exact |
| EHZ / CPZ ripple | a band deform table holding the 32-entry pattern repeated | **the SHAPE is exact; the SPEED is not.** Phase advances ≥ 1 step per frame, and S2 advances 1 step per 8 frames. Aurora's survey lists "deform phase speeds below 1 step/frame" as an S engine gap. Default to a static ripple and TAG it |
| CPZ camY/4 | `v_factor_bg = 2`, `v_center_y = 256` (CPZ is pasted 256 px lower) | exact while background Y ≤ 288 |
| CPZ bands by BG row (1/8, ripple, 1/2) | bands keyed on plane line | exact for background rows < 512 only |
| CPZ background taller than 512 px (rows to about 680 are visible in S2) | `rg_bg_span` streams a tall map, **but bands key on plane line** (map row mod 512), so rows 512+ would take the 1/8 band instead of 1/2 | **NOT expressible.** Aurora survey gap 2 ("BG plane redrawn per band from separate BG cameras: CPZ"), L |
| CPZ 96-cell horizontal period | the plane is 64 cells and wraps | **NOT expressible.** Crop 64 of 96 cells with one invented seam every 512 px, as the OOZ showcase does. Wide maps are booked as "BG row streamer: wide-map stride and wrap", L |
| backdrop = line 2 entry 0 | the backdrop register is `$00` for every act | needs a clip-only register-7 write (§4.3) |

### 4.2 Design: make the bytes the clip act no longer shows pay for the ones it now does

The clip act inherits the shipped act's background path, which costs this much in the plain
listing:
- `OJZ_Act1_BG_Layout` 8,192 B;
- `OJZ_Act1_BG_Tiles` 10,242 B;
- `BgAnim_Banks` 8,192 B plus band headers.

The clip bake rewrites this path every build (`clip_rom_bake.py:942-962` re-runs
`inject_editor_bg.py`). **Under (B) the clip act never shows any of it.** The design:

1. **The start region's zone becomes the act default background.** Today that is EHZ. The
   clip bake writes the generated `zone_bg.bin` (typed at 8,192 B, full plane) and
   `bg_tiles.bin` from EHZ's background instead of running the OJZ injector. Those files are
   in the generated tree the S2CLIP EXIT trap already restores.
   - **Why EHZ is the default and not a region override:** `BG_Init` blits the act default
     before the camera exists (**BG-BOOT-REGION-BLIT**), so the boot picture is correct only
     if the start zone's background IS the act default.
   - `bg_span` stays 0.
2. **Every other zone gets a region override.** Today that is CPZ: the clip bake appends a
   typed layout and tile blob to its CLIP ACT DATA block and names them in CPZ's region rows
   (`rg_bg_layout`, `rg_bg_tiles`, `rg_bg_span = 0`). The EHZ rows keep 0, which means
   "the act's". The crossing is the existing one at x = 11632, mid-corridor.
   - The wipe takes `BG_WIPE_FRAMES`, 64 rows at 4 per frame = 16 frames.
   - The corridor gives at least 41 frames at 16 px per frame (656 px each side).
3. **The generated `bg_anim.emp` is written with zero bands and no bank.** The shipped band
   is `default_off` (`BgAnim_Table` = 0, "the act boots with BG animation OFF"). Nothing in a
   clip act can turn it on except the DEBUG effects lab, and that lab would animate OJZ art
   over a Sonic 2 background.
4. **Lowering keeps native palette bits.** No re-quantisation: each zone's region installs its
   own donor lines 1-3. It keeps flip bits, pixel-dedupes flipped tiles, and rebases through
   `inject_editor_bg.rebase_layout`, reused read-only.
   - **Refused:** more than `BG_STATIC_TILE_BUDGET` 320 tiles; a word past the blob.
   - **Warned:** line-0 words. CPZ has **2** such cells; they are the same class of decision
     as the 76 foreground cells row 7 tagged.
   - **Priority bits are kept, which is faithful.** CPZ's 26% priority background cells draw
     over low-priority foreground exactly as they do in Sonic 2. TAGGED.
5. **Per-zone parallax configs** go in the same data block, bound through
   `preset(parallax: ...)`. Two configs: EHZ with 7 bands, CPZ with 3.
6. **Backdrop register 7 = `$20`** (line 2 entry 0, Sonic 2's own `$8720`), in clip shapes
   only.
   - A comptime-gated store into `VDP_Shadow_Table` + 7 in the game's level init
     (`GameState_OJZScroll_Init`, `games/sonic4/test/ojz_scroll_test.emp:585`), keyed on
     `OJZ_CLIP_ACT`. That flag is 0 in the committed neutral module, so the store emits
     **zero bytes** in canonical shapes. `Flush_VDP_Shadow` re-blits registers $00-$12 every
     VBlank, so it holds.
   - Effect: EHZ's transparent sky shows $C20 and CPZ's shows $002, as in Sonic 2.
   - The corridor's blank cells show whichever zone's line-2 entry 0 is live, fading at the
     crossing. That is what a Sonic 2 transition would show; TAGGED.

### 4.3 Cost against every gate

**ROM, plain shape.**

| item | bytes | basis |
|---|---|---|
| OJZ tiles out, EHZ tiles in (the 8,192-B layout is the same size) | −10,242 + 4,546 = **−5,696** | exact blob sizes; EHZ 142 tiles x 32 + 2 |
| OJZ animation bank out (8,238 B in the plain listing, 0x3616C..0x3819A; `BgAnim_Table` stays) | **about −8,190** | listing |
| CPZ region: layout 8,192 + tiles ≤ 238 x 32 + 2 | **+15,074 to +15,810** | exact by crop |
| two parallax configs (30 + 7x32, 30 + 3x32) + one 256-B deform table | **about +636** | `ParallaxConfig_OJZ_Default` measures 158 B = 30 + 4 x 32 in the listing |
| register-7 store | about +6 | |
| **net** | **about +1.8 to +2.6 KB** | |

Against today's plain room of +8,974 B, that leaves **about +6.4 to +7.1 KB, so it FITS.**
Two caveats:
- **Without step 3 it misses:** net about +10.0 to +10.8 KB, **short by about 1.0 to 1.8 KB.**
- These figures are arithmetic on measured blob sizes, not a build. The B-1 parcel must
  measure the room with `bganim_room` and quote it.

**ROM, DEBUG shape.** The same net, about +1.8 to +2.6 KB. The known −18,252 B becomes about
**−20.1 to −20.8 KB**: still exit 1, still for the reason S2CLIP-DEBUG-ROOM accepts, and **larger**.
Filed (§6).

**Everything else B touches:**
- **VRAM:** the background arena is `BG_TILE_CAPACITY` 376, of which the static budget is 320
  (`band_reserve` 56, carved first; `games/sonic4/vram.toml:223-228`). EHZ uses 142 of 320
  (178 spare) and CPZ 215-238 of 320 (82-105 spare). With no animation band, the band reserve
  goes unused. The foreground pool, page frames and cache windows are **unchanged**:
  background tiles live in their own arena.
- **Sections, collision attr set, foreground page budget:** unchanged, since no foreground byte
  moves.
- **`MAX_PARALLAX_BANDS`:** 16; EHZ needs 7.

### 4.4 Can it land today without d-35?

**The plain shape: yes, if step 3 goes with it (estimated +6.4 KB margin; must be measured).
The DEBUG shape: no.** It is already exit 1 and accepted, and B makes the known overrun about
1.8-2.6 KB larger. The hub said anything that "grows past the room gate is FILED". The gate is
already failing in that shape, but B still grows the failure. So I am **filing** the DEBUG
half rather than assuming the growth is covered by the existing acceptance.

### 4.5 Recommendation for (B)

Ship B in two parcels:
- **B-1:** static backgrounds, backdrop register 7, and the dead OJZ animation bank removed.
- **B-2:** EHZ's faithful parallax, and CPZ's parallax within the 512-row and 64-cell limits.

CPZ's lower background rows and its 96-cell period are **approximated and TAGGED**:
- the background stops following the camera vertically below zone y ≈ 1,408 (background Y
  clamps at 288);
- there is one invented seam per 512 px.

Book faithful CPZ as the two larger engine items aurora already surveyed; do not build them
for a test act.

### 4.6 Parcels

**B-1 (M): each zone's own background, static.**
- **Files:**
  - a new `tools/clip_bg_lower.py`: the native-palette S2 background lowering, reading
    through `s2_donor`, with refusals and warnings as in §4.2;
  - `tools/clip_rom_bake.py`: the act-default BG write replaces the injector call; the
    zero-band `bg_anim.emp`; CPZ blobs and region-row fields in `clip_data_block`;
  - the Z2 parse (`clip_rom_bake.py:665` matches `preset(pal: X,` and must accept the new
    kwargs);
  - `tools/test_clip_two_zone.py` and a new `test_clip_bg_lower.py`, red-first;
  - `games/sonic4/test/ojz_scroll_test.emp` (the register-7 store, comptime-gated);
  - the neutral `clip_act.emp` if the flag needs a second constant.
- **Must not touch:**
  - `inject_editor_bg.py`, whose `validate_band_coherence` aurora runs as a gate;
  - `editor_bg_override.json`, `act_descriptor.emp` and `ojz_effects.emp`, all vendored by
    aurora with currency tests;
  - `clip_act_bake.py` and `clip_manifest.py`, which aurora invokes and pins by tool blob.
- **Checks:**
  1. `S2CLIP=s2_ehz_cpz ./build.sh` exit 0, with `bganim_room`'s margin quoted.
  2. A `tools/landing_build.sh` run with canonical ROMs byte-identical (`s4` `6d1af7a3`,
     `s4.debug` `62238a15`, `demo.debug` `ce922bf7`, unless master moved), which also proves
     the register-7 gate emits nothing.
  3. A red-first mutation per new refusal.
- **Expected DEBUG result:** exit 1 at `bganim_room`, short by about 20.1-20.8 KB, unless §6
  item 2 is taken.
- **TAGGED:** the picture, the crossing (background wipe plus palette fade together), CPZ's
  priority cells, the corridor backdrop.

**B-2 (S-M): parallax.**
- **Files:** two parallax configs and one ripple deform table, emitted by the bake; presets
  bound with `parallax:`.
- **Built through the scene DSL constructors** (`engine/level/scene_dsl.emp`), not hand-typed
  bytes. **Risk:** helper imports resolve at the call site
  (`reference_emp_helper_imports_dont_travel`), and the data block lives in the
  `entity_data.emp` vehicle. If the constructors cannot be reached from there, this is where
  row 7's booked "clip act data needs a section of its own" (a map.toml row plus a sigil
  `section_align` row) becomes a requirement. **That half is sigil's: STOP and report, do not
  work around it.**
- **Checks:** the existing parallax gates that read a config (`parallax_crossing_gate`
  struct offsets) on the clip tree. The band tables are derived from `s2.asm` by script, not
  typed.
- **TAGGED:** motion, and ripple speed (static, per §4.1).

**Not proposed (larger, separate, needs a hub id if anyone wants them):**
- tall background with BG-space bands (aurora gap 2, L);
- wide background (booked, L);
- phase speed below 1 step per frame (S);
- `PalCycle_EHZ` / `PalCycle_CPZ` through `preset(cycle:)`: probably data, **unmeasured**.

---

## 5. Consumers (aurora origin/master `44ba3d7f`, read through git objects)

- **(A)** edits `games/sonic4/data/clips/s2_ehz_cpz/clips.json`. Aurora vendors it verbatim
  (`test/fixtures/clips/s2_ehz_cpz.clips.json` + provenance, pinned at blob `d891f2d1`), and
  `test/formats/aeon-fixture-currency.test.ts` **goes red by design** when the aeon path moves
  on origin/master. It needs a re-vendor and a message to the aurora lane in the same turn.
  - The alternative is a new manifest id, which leaves aurora untouched but changes the act
    the owner flies. Not recommended.
  - Aurora's `s2_ehz_cpz.clipact.json` output fixture is keyed to `clip_act_bake.py`'s blob,
    not the manifest, but its `per_clip` numbers become stale for the widened act. Say so in
    the message.
- **(B)** as scoped touches none of the aurora-read files:
  - `clip_act_bake.py` and `clip_manifest.py` are invoked by aurora's `src/main/clip-tool.ts`;
  - `inject_editor_bg.py` is run by aurora's injector-gate test;
  - `editor_bg_override.json`, `act_descriptor.emp` and `ojz_effects.emp` are vendored;
  - `clipact.json`'s shape is read by `clipact-pool.ts`.

  If B-1 ever adds a background readout to `clipact.json`, that is a `clip_act_bake.py` change
  and aurora's tool-blob pin re-measures: message them. **No manifest key is needed for B.**
  The background is derived from each clip's `(donor, zone)`, so aurora's paste format does
  not change.

---

## 6. Filed: for d-35, for the hub, for the owner

**For d-35-revised (hub-gated; nothing below dispatches until it is answered and both halves
land):**
1. **(A), all of it.** A1 misses the plain reserve by 19,460 B; A2-A4 do not link. Its anchors
   must be derived per act from both shapes' listings (§3.4). **The pricing note's fixed
   0xB8000/0xC8000 does not cover A1's DEBUG shape**, which needs 0xC0000/0xD0000. M3's
   per-clip overlay is the mechanism that absorbs this.

**For the hub:**

2. **A lever that makes the DEBUG clip shape pass without d-35.**
   - `OJZ_Act1_BG_Layout_Tall` (12,288 B), `OJZ_Act1_BG_Showcase_Layout` (8,192 B) and
     `OJZ_Act1_BG_Showcase_Tiles` (3,778 B) are DEBUG-only test blobs.
   - They total **24,258 B** in the clip DEBUG ROM (`s4.s2clip.debug.lst`, crc `441f1db0`,
     0x36C72..0x3CB34), and the clip act never references them, because its region table
     replaces the rows that name them.
   - Gating those embeds and their two DEBUG region rows on `OJZ_CLIP_ACT == 0` would move
     the DEBUG clip shape from −18,252 B to about **+6.0 KB**, or about +3.4 KB after B.
     Canonical stays byte-identical by construction (the flag is 0 there).
   - Size S. It edits `act_descriptor.emp`, which aurora vendors, so it needs a message.
   - **This is an alternative to the hub's ruled (B) for today's act, not a replacement for
     d-35.** It buys 24 KB once, and (A) needs more than that. Hub's call.
   - The same listing also answers the pricing note's open question: why `Art_Sonic` sits
     27,226 B further along in DEBUG than in plain. These blobs are 24,258 B of that; they
     landed on 2026-09-16, after the 09-04 re-layout that measured 2,402 B.
3. **B's DEBUG shape grows the accepted overrun by about 1.8-2.6 KB** (§4.4). Accept that as
   covered by S2CLIP-DEBUG-ROOM, or pair B-1 with item 2.

**For the owner (his calls, none guessed):**

4. **How much more Chemical Plant:** A2 (to the second checkpoint, recommended) or A1 (to just
   before the first). A3 and A4 sit at 12 of 12 frames in the tile cache's worst camera
   window.
5. **A CPZ vertical carve or an EHZ trade**, only if he wants more CPZ before d-35. Neither is
   measured. The EHZ trade undoes his own "didn't quite get to the end" fix.
6. **The CPZ background's two approximations** (vertical clamp below zone y ≈ 1,408; one seam
   per 512 px), versus funding the two engine items.
7. **The ripple**: static, or animated 8x too fast, until a sub-frame phase exists.

---

## 7. Reproduce

Run from the repo root with the two `SIGIL_*` exports. Donor trees:
`python3 tools/s2_zone_convert.py convert s2disasm@EHZ s2disasm@CPZ`.

```bash
python3 docs/research/2026-09-25-s2clip-cpz-bgs/bgmeasure.py EHZ CPZ OOZ   # BG geometry, periods, lines
python3 docs/research/2026-09-25-s2clip-cpz-bgs/bgcrop.py                  # native-palette tile counts per crop/span
python3 docs/research/2026-09-25-s2clip-cpz-bgs/bgtrans.py                 # transparency and backdrop colours
python3 docs/research/2026-09-25-s2clip-cpz-bgs/fgentries.py               # palette entries the FG uses
python3 docs/research/2026-09-25-s2clip-cpz-bgs/cpzextent.py               # CPZ painted y per 2048-px column
python3 docs/research/2026-09-25-s2clip-cpz-bgs/cpzobj.py                  # CPZ act 1 starposts
FAST=1 S2CLIP=s2_ehz_cpz ./build.sh && python3 tools/bganim_room.py --lst s4.s2clip.lst --rom s4.s2clip.bin --gate
python3 docs/research/2026-09-25-s2clip-cpz-bgs/mkcand.py 4096 6144 8192 10240   # SCRATCH manifests, never commit
OUT=<scratch> nohup docs/research/2026-09-25-s2clip-cpz-bgs/runcands.sh s2x_cpz4096 s2x_cpz6144 s2x_cpz8192 s2x_cpz10240 &
# poll <scratch>/runcands.status for finished=8, then: rm -rf games/sonic4/data/clips/s2x_cpz*
```
