# A shorter EHZ -> CPZ connector: what sets its length, and a 640-px feasibility clip

> **UPDATE, same day (the limit test, §8).** The owner then asked for *"slightly longer than a
> screen"*, then *"slightly above screen width and that's it ... it can be our new full cpz"*.
> One engine change (the one-plane background is now repainted by DMA from ROM, 0 B RAM) plus
> a Z1 screen override takes the connector to **384 px, the shortest MEASURED glitch-free**
> (0 glitch frames in 12 runs, 0 frames of slack at the camera cap); **336 px was built and shows
> 2 glitch frames arriving EHZ at every speed and 1 arriving CPZ at the cap** (§8). `s2_ehz_cpz_short` is now the real act (full 2528-px CPZ) with a
> 384-px tunnel; the 640-px version below is commit 5e720fe1. The hysteresis lever costed in §3
> turned out to need a DIRECTIONAL region, not a sticky one, and was not built (§8.3).
> **§2-§4's frame counts were taken with a one-frame alignment error in the witness** (§8.1):
> the landed act re-measured is palette +12 / background +12 into CPZ, +12-13 / +10-11 into EHZ,
> slack 4 at the cap; the 640-px clip's slack is 3 / 4 as stated.

2026-09-25, branch `research/shorter-connector`. The owner, verbatim: *"I'd like the make the
connector quite a bit shorter if possible, I just want to test the feesibility."*

**Answer in one paragraph.** The landed tunnel is 832 px. Two clip-tool rules were said to set
that length: Z2 (palette crossing) and Z1 (tile-cache separation). They do not bind the way
the previous parcel read them. Measured on the running ROM, the thing that actually has to fit
inside the tunnel is the **background switch** (the BG tile overwrite and then the plane
repaint). It takes 12 frames into CPZ and 10-11 into EHZ at the camera cap, which is as long as
the palette fade really takes (11-12 frames, not the 16 Z2 assumes). No clip rule modelled the
background. With **no engine code** (two clip-tool overrides that apply only to the new clip) the
connector goes to **640 px (-23%)**. `s2_ehz_cpz_short` is that clip, and it measures 0 glitch
frames at every speed. Going past about 600 px needs engine work. The cheapest engine change is
region hysteresis, which gives about 480 px (-42%). All of it is costed below.

Tools and files: `tools/crossing_witness.py` (new, a witness), `tools/clip_rom_bake.py` (Z2's
background term, `crossing_overrides`), `tools/test_clip_crossing_overrides.py` (new),
`games/sonic4/data/clips/s2_ehz_cpz_short/clips.json` (new), `tools/keepalive_manifest.toml`
(one line). `s2_ehz_cpz` and its outputs are not touched.

## 1. The rules as the source states them (re-derived, not carried)

| Rule | Where | Formula | Today |
|---|---|---|---|
| Z2 | `clip_rom_bake.check_palette_crossings` | crossing at the gap's middle rounded down to 16; each side needs `CAM_SCREEN_HALF_W` 160 + `PAL_FADE_FRAMES` 16 x `CAM_MAX_X_STEP` 16 = **416 px** | 416 / 416: binds at 832 |
| Z1 | `clip_act_bake.zone_separation`, enforced by `clip_rom_bake.check_zone_separation` | no `TILE_CACHE_COLS` x `TILE_CACHE_ROWS` (80 x 60 cells) window a camera can produce holds cells of two donor zones, so gap >= 79 cells = **632 px** | gap 104 cells |

Both readings in the brief are correct: 160 comes from `engine/system/constants.emp`, 16 frames
from `engine/effects/palette.emp`, 16 px from `engine/level/camera.emp` (file-local), and 80 from
`constants.emp:366` ("viewport 40 + margin 20x2").

## 2. What goes wrong if each is violated, traced through the engine

### 2.1 The crossing pipeline (one tick)

`GameState_OJZScroll_Update` (games/sonic4/test/ojz_scroll_test.emp) runs `Camera_Update`, then
`Parallax_CheckBoundary` (region by camera CENTRE, `Camera_X + 160`), which on a change calls
`Effects_InstallPreset`. That call either arms a fade (`ep_transition != 0`: `Palette_LoadPal`
loads `Pal_Target`, `Pal_Fade_Frames = 16`) or snaps (`Pal_Base`, one-shot copy). Then
`Parallax_Update` runs, then `BG_Stream_Update` (engine/level/bg.emp), which reads the
region's `rg_bg_tiles`/`rg_bg_layout`. After the state, `GameLoop` runs `Palette_Compose`. The
next VBlank ships CRAM (`Enqueue_Dirty_Buffers`; a refused line stays dirty and retries next
VBlank), HScroll and the plane buffer together.

### 2.2 Z2's subject: the palette

Lines 1-3 are the zone's, and one set is installed at a time. If the screen shows zone cells
while the wrong set, or a half-faded set, is in CRAM, **those cells are drawn in the wrong
colours** until the fade lands. That is a colour error, not torn tiles and not a crash.

- **The fade's real length is palette-dependent.** `Palette_DoFade` moves every channel +/-1
  every second compose and closes early when all arrive: `2*max(d)-1` composes
  (tools/region_fade_witness.py's header, from the instructions). 16 is the backstop. EHZ<->CPZ
  measured **+11 / +12 frames** (crossing_witness, landed ROM). Z2's 16 over-reserves 4-5
  frames (64-80 px) per side.
- **What is on lines 1-3 inside the tunnel: nothing visible.** Tested with
  `crossing_witness.py --scan` (full-screen `emulator/pixel_attribution`, counting pixels whose
  winning CRAM index is on lines 1-3). On the landed ROM, cap speed, rightward: **0 such pixels
  on every frame from 3 before the crossing until the screen reached CPZ** (rows 50-68). The
  first appear exactly on the frame the geometry says CPZ enters the screen. The reasons: the
  tunnel is recoloured onto line 0; Sonic is on line 0 (`player_common`'s resolve); the HUD is
  line 0 (`BGND_Palette`); the tunnel rect has 0 transparent pixels, so neither plane B nor the
  backdrop (`OJZ_CLIP_BACKDROP` $20 = line 2 entry 0) shows through; and no OJZ ring (line 1,
  `ring_sparkle.emp`) lands in the tunnel's window. So **hypothesis (b) holds**: a lines-1-3
  swap inside the tunnel is invisible, and a snap is as good as a fade there.

### 2.3 The term nobody modelled: the background switch

The region also names each zone's background (B-1, 2026-09-25). In `BG_Stream_Update`, if the
arena does not hold the region's tile blob, it queues one `BG_OVERWRITE_CHUNK_BYTES` (1824 B)
chunk per frame and **returns before the wipe and the streamer**. So for the whole overwrite
the plane keeps the old layout over tiles that are being replaced. **If it were on screen, that
is garbage BG tiles.** After that, the wipe repaints 4 rows a frame (`BG_WIPE_ROWS_PER_FRAME`)
from the top visible row down, so the 29 visible rows (`BG_SCREEN_ROWS`) take 8 frames.

| Switch into | Blob | Chunks | Model (chunks + 8) | Measured (cap speed) |
|---|---|---|---|---|
| CPZ | 237 tiles, 7584 B | 5 | 13 | **12** |
| EHZ | 141 tiles, 4512 B | 3 | 11 | **10-11** |

On the landed act at 16 px/frame, the screen first reaches CPZ **16 frames** after the crossing
(**17** for EHZ). **Slack: 4 and 5 frames.** The 832-px tunnel was safe, but with **the
background, not the fade, as the tighter term**. Any shortening that trimmed only the fade
margin would have shown garbage/old BG through CPZ's transparent pixels at the tunnel mouth.

### 2.4 Z1's subject: the palette again, through a conservative window

Z1's own docstring says it guards the palette ("a screen showing two zones shows one of them in
the other's colours"). It counts the 80-column **tile cache** window, which is 20 columns wider
than the screen on each side. It does not guard art residency: two zones' art sharing a window
is legal (one act-wide pool; the page budget is N1/N2's, and at 640 px the worst window is still
9 of 12 pages). It does not guard the section local maps either (W3 and the bake's 2047 cap).
**Violating Z1 while Z2 holds shows nothing wrong on screen**, because the cache margins are
never displayed. Z1 is a stronger proxy for Z2's screen walk. It binds at 632 px only once the
palette and BG terms are below about 290 px a side.

## 3. Levers, costed

Corridor = `320 + 16 x (T_left + T_right)` in px at the camera cap, where `T_side` is the frames
the switch INTO that side's zone takes: max(palette, background). The crossing sits at the
middle, so both sides get the larger term. The result is rounded to the 16-px grid and floored
by Z1.

| # | Lever | Palette T | BG T (CPZ / EHZ) | Shortest | Engine code? |
|---|---|---|---|---|---|
| 0 | today's rule | 16 (fade) | 13 / 11 (unmodelled) | **832** | - |
| a1 | Z2 uses the fade's true arrival (2*max(d)-1 = 11) plus the BG term | 11-12 | 13 / 11 | **~736** (-12%) | no (tool: derive d from the two palettes) |
| a2 | shorter `PAL_FADE_FRAMES` globally | - | - | nothing below a1 | yes, and it changes every fade in the game (the step rule is +/-1 per 2 composes, so a shorter window just ends in a snap). Not recommended |
| b | palette SNAP (transition 0) | 1 | 13 / 11 | **~736** (-12%) | no (per-clip override) |
| d1 | **snap + CO-RESIDENT backgrounds** (both BGs in one 376-tile blob, only the wipe) | 1 | 8 / 8 | **640** (-23%), Z1-bound (576 without Z1) | **no**: per-clip overrides, built |
| c | d1 + Z1 counted on the SCREEN window, not the cache | 1 | 8 / 8 | **~608** (-27%) with 1 frame slack | no (tool: a per-clip Z1 window override). Buys 32 px; not built |
| e | d1 + c + **region hysteresis** (install when the screen's trailing edge clears the zone left behind, so each direction switches once and early) | 1 | 8 | **~480** (-42%): 320 + 16 x 8 + slack | **yes, small and isolated**: a per-row HOLD flag in `Region_Resolve`/`Parallax_CheckBoundary` (keep `Region_Current` while the centre is inside a marked band), ~20-40 lines of 68k + a Region flag + a gate. Clip tool emits the band |
| f | faster wipe (`BG_WIPE_ROWS_PER_FRAME` 4 -> 8) | - | 4 | with d1 still 640 (Z1); with d1 + c ~480; with e ~400 | yes: `PLANE_BUFFER_SIZE` (1536 B) must grow by 4 rows x 132 B = 528 B of RAM, and RAM is at 93.8%. The plane-buffer ensure in bg.emp names it. Expensive |
| g | both BGs in ONE plane (stacked), switch = VSRAM base | 1 | ~1 | e at ~352 | yes, and content: both lowered BGs are full 512-row planes (EHZ paints 2048 px, CPZ 896), so each would have to be cropped to 256 px of height. Speculative, not recommended |

**Why d1 is tool-only.** `BG_Stream_Update` compares the region's EFFECTIVE tile blob with
`BG_Tiles_Current` by pointer. With `rg_bg_tiles = 0` on CPZ's rows, the effective blob is the
act default's, which is already resident, so no overwrite runs and only the layout's wipe does.
The two zones' tiles share 2 (by clip_bg_lower's canonical flip form): 141 + 237 - 2 =
**376 = `BG_TILE_CAPACITY` exactly, 0 spare**. That is 56 tiles into the band reserve
(`BG_STATIC_TILE_BUDGET` 320), which a clip act can spend because it has no BgAnim band (the
bake reads back the injector's zero-band stub before allowing it). A zone pair whose union
exceeds 376 cannot use this lever. The bake refuses it by name.

## 4. The feasibility clip: `s2_ehz_cpz_short`

**Connector 640 px** (x 10976..11615; landed 832). CPZ at x 11616, crossing x 11296, 320 px
from each zone. Z2 re-derived: 160 + 16 x max(SNAP_FRAMES 1, BG 8) = 288 each side, so 2
frames of slack at the camera cap. Z1: gap 80 cells >= 79. Everything else is as in
`s2_ehz_cpz`. The act is 672 px of unpainted remainder past CPZ's 2048 px, declared
two-sided. The overrides are one named manifest key with a `why`, and the bake prints them in
a `!!!` banner. An act without the key is held to exactly what it was:
`test_the_landed_act_is_held_to_what_it_was` pins 416/416 and transition 1 on `s2_ehz_cpz`.

### Measured (headless, `S2CLIP=s2_ehz_cpz_short DEBUG=1`, crc 2f641ad0)

`crossing_witness.py`, 6 runs (right/left x walk from rest / PHYS_TOP_SPEED / PHYS_GSP_CAP):
**0 glitch frames, 0 faults.**

| Run | Palette on screen | BG settled (visible rows) | Screen reaches far zone | Slack |
|---|---|---|---|---|
| right, walk | +0 | +7 | +27 | 20 |
| right, top | +0 | +7 | +26 | 19 |
| right, cap | +0 | +7 | +10 | **3** |
| left, walk | +0 | +7 | +27 | 20 |
| left, top | +0 | +7 | +27 | 20 |
| left, cap | +0 | +11 frames (7 camera moves; 8 lag frames at the exit) | +15 | **4** |

`--scan` at cap speed, both directions: **0 line 1-3 pixels on every frame from before the
crossing until the screen reaches the far zone** (right rows 44-56, left rows 50-68). When CPZ or
EHZ enters, the palette is already the right one and the visible BG rows are already repainted.

`tunnel_run_witness.py`: 6 of 6 crossed, 0 airborne frames inside, 0 faults, 11 stall frames
(the landed 832-px tunnel measured 23 after the lag fix; stalls are harness pacing, see its
header), |gsp| steady through both seams, y 748..750.

### What an honest viewer should expect to see

- **Nothing** at the crossing itself: no fade, and no colour change is visible, because nothing on
  screen uses the lines being swapped. The screen is all tunnel for 320 px (20 frames at a run,
  about 2 at the camera cap) before the far zone appears.
- The tunnel is 192 px shorter. At the camera cap the far zone appears **10 frames** after
  the crossing, against 16 in the landed act.
- **Residual risks, not seen in any run:** (1) the BG wipe finishes its off-screen rows up to 5
  frames after the far zone appears (rows below/above the screen). A camera moving sharply
  vertically right at the mouth could reveal a not-yet-repainted row for a frame. The tunnel
  floor is flat, so this needs a jump at the exact exit frame. (2) At the camera cap the slack
  is 2-3 frames. A DMA refusal of a CRAM line (+1 frame) is inside it; a run of lag frames only
  delays the camera too.
- The overrides change the LOOK in one respect the owner should judge: **the crossing is now a
  cut, not a fade.** It is hidden inside the tunnel either way.

## 5. Red-first evidence for the new checks (mutations on disk, restored from HEAD)

| Mutation (tools/clip_rom_bake.py) | Red rows |
|---|---|
| `fr_l = pal_frames` / `fr_r = pal_frames` (drop the BG term) | `test_z2_background_term_refuses_a_crossing_only_the_fade_fits`, `test_snap_override_emits_transition_0_and_holds_the_snap_margin` |
| `want_trans = 1` (ignore the snap override) | `test_snap_override_emits_...`, `test_snap_override_refuses_a_preset_that_still_fades`, `test_the_short_clip_is_the_shortest_its_overrides_allow` |
| `if True:` for `if t not in index:` (no dedupe in the union) | `test_co_resident_blob_draws_every_zones_own_tiles`, `test_the_short_clip_...` (bake refuses: "need 519 tiles ... BG_TILE_CAPACITY = 376") |
| `if z["bg"].get("co_resident") and False:` (BG1 skips the re-lowering) | `test_bg1_refuses_a_co_resident_cell_that_draws_another_tile` |

Each was restored with `git show HEAD:tools/clip_rom_bake.py > tools/clip_rom_bake.py` and the
file then diffed clean.

## 6. Builds and landing evidence

| Build | sigil pair | Result |
|---|---|---|
| `S2CLIP=s2_ehz_cpz DEBUG=1` (baseline, landed act) | shared `sigil/target/release` | crc e4ce79c9, 849,389 B (matches the landed record) |
| `S2CLIP=s2_ehz_cpz_short FAST=1 DEBUG=1` | shared | crc 2f641ad0, 849,371 B |
| `S2CLIP=s2_ehz_cpz_short DEBUG=1` | candidate `.sigil-pin-1d19e60b` | exit 0, crc **2f641ad0**, 849,371 B; bganim room 49,798 B (+646 over the reserve; landed +348) |
| `S2CLIP=s2_ehz_cpz_short` | candidate | exit 0, crc **cb417c49**, 822,889 B; room 52,638 B (+3,486) |
| `tools/landing_build.sh` (HEAD 270ecf1c) | candidate | **exit 0, `finished=0`**; s4 e4f3f8fd, s4.debug 762fa8db, demo.debug 72b0a8d1, which are the canonical CRCs, so byte-identical; pre-build lane 3388 passed / 3 skipped; emp_expect_fail 56/56; needs-build lane 32 ran, 0 failed, 1 exempted. The land-gate printed NO STAMP only because the run-unique copy of the script was an untracked file in the tree |

The first short DEBUG build failed on `test_every_bus_instrument_in_the_tree_is_declared`
(crossing_witness.py had no keepalive disposition). The fix is one `not_wired` line.

## 7. Recommendation

- If the owner likes 640 px on screen, the two overrides can be promoted into `s2_ehz_cpz`
  (a clips.json edit that the parallel CPZ-extension parcel owns). Nothing in the engine changes.
- If he wants about half the length, **(e) region hysteresis** is the one engine change worth
  making. It is small, isolated in the region resolver, and also helps any future two-zone act.
  (f) and (g) cost RAM or content and are not recommended.
- Z2's background term now applies to every clip act. It passed the landed act unchanged, and it
  would have refused a fade-only trim that showed garbage BG at the mouth.

## 8. The limit test: "slightly above screen width" (same day, second round)

The owner, verbatim, in order: *"let's make the tunnel slightly longer than a screen, I want to
limit test."*, *"we can make this connector test even shorter I think for clip-short."*, and
*"the shorter tunnel itself I want to test as even shorter, like slightly above screen width and
that's it, Idc what's on the other side it can be our new full cpz."* So `s2_ehz_cpz_short` is
now `s2_ehz_cpz`'s own content (origin/master 18e96e47, Chemical Plant 2528 px) with ONLY the
tunnel changed, and its own `anchors.toml` (`tools/clip_anchors.py --derive`, rule 0xB8000 in
both shapes).

### 8.1 The witness had a one-frame alignment error (found and fixed first)

`crossing_witness` paired tick i's camera with the CRAM and VRAM read at sample i+1, on the
belief that a sample precedes its tick's VBlank. Measured on the 336-px clip, it does not: the
tick-710 install is already in CRAM at the sample whose `Logic_Tick` reads 710, and the pixel
scan's first line 1-3 pixels land on the same row where the camera geometry says the zone enters.
`run_frames` stops after the VBlank that follows tick i. The witness now pairs the same sample
(commit "crossing_witness: same-sample alignment"). It also now reads the background ON SCREEN
from VRAM: every visible Plane B row is compared, whole, with the zone's layout row in ROM, where
it used to trust the wipe cursor. `--jump` presses jump at the tunnel mouth, which gives the
vertical camera move asked for.

### 8.2 The engine change: a one-plane background is repainted by DMA from ROM

With palette SNAP (0 frames, measured) and co-resident tiles (no overwrite), the only thing
left inside the tunnel is the wipe: 29 visible rows at 4 rows a frame through `Plane_Buffer` =
8 frames. A map no taller than the plane (every clip background) has plane row p = map row p,
and a run of rows is one contiguous span in the ROM layout AND in the Plane B nametable. So
`BG_Stream_Update` now queues ONE Deferrable DMA a frame of up to `BG_WIPE_DMA_ROWS` = 14 rows
(`engine/level/bg.emp`, `.wipe_dma`; the CPU path stays for taller maps).

| Cost | Value |
|---|---|
| RAM | **0 B** (no new variable; no `Plane_Buffer` bytes) |
| Code | +66 B in the canonical DEBUG ROM; ~40 lines of `.emp` in one proc, 1 constant + 1 `ensure` |
| Cycles | on a wipe frame only: one `QueueDMA_Deferrable` call plus ~20 instructions (a few hundred cycles), replacing the CPU path's 4 x 32 `move.l` row copies + their VBlank drain (~3k cycles each side). 0 on every other frame (`tst.b BG_Wipe_Cursor` as before) |
| VBlank DMA | up to 1792 B per wipe frame on the Deferrable queue: the size `BG_OVERWRITE_CHUNK_BYTES` was already derived to fit (the overwrite and the sweep never share a frame) |

Measured: the visible rows are right from frame +2 (14 + 14 rows by +1; the 29th row,
visible when BG vscroll is not 8-aligned, lands at +2).

### 8.3 Hysteresis: built? No, and why

A STICKY region (overlapping rows, which the engine's fast path already honours: the centre
stays in the live row until it leaves it) switches LATE, at the far edge, which is the opposite
of what we want. The lever needs a DIRECTIONAL middle region that installs the zone you are
heading into as soon as the screen has cleared the one you left: rightward at centre >= a_right
+ 160, leftward at centre <= b_left - 160. Its gain, measured against the rule above, is
`G >= 319 + 16k` instead of `G >= 2 x (160 + 16k)`. With k = 2 that is 352 against 384: **32
px**. At 336 it would still show 1 glitch frame. Its costs:

- **a glitch on reversal**: turn back inside the middle band near its entry edge and the old
  zone comes back on screen with the new zone's background for up to k frames. The fixed
  crossing has no such case.
- **a Region flag** (the struct has no spare field: `size: 26`) or a new sentinel, which moves
  every region table and every tool that strides it.

Not built. It is small in cycles but not small in surface, and it buys 32 px while trading
a glitch the fixed crossing does not have.

### 8.4 The shortest connector, measured

Every probe is a FAST debug clip build of this act at that width, driven by `crossing_witness`
at walk, top speed and the camera cap, both directions, plain and with a jump at the mouth
(12 runs), all with the same-sample alignment:

| Connector | Crossing (left/right margin) | Glitch frames | Worst slack at the cap | ROM crc |
|---|---|---|---|---|
| 416 | 208 / 208 | 0 | 1 | 6b4c36d8 (older CPZ) |
| **384** | 192 / 192 | **0** | **0** | 95db1392 |
| 368 | 176 / 192 | 2 | -2 | 21ec1051 |
| 336 | 160 / 176 | 7 over 6 runs (plain and jump identical) | -2 | c112cec1 |

**Binding rule at 384: the background repaint.** Each side needs 160 + 16 x k with k = 2
frames of not-yet-repainted visible rows: 192, and the crossing sits at the middle. Z2's static
model keeps a third frame as the allowance for a DMA that slips a frame (`ceil(29/14)` = 3), so
it asks for 208 a side (416). The clip carries `crossing_margin = report`, and the bake prints
the 16-px-a-side shortfall instead of refusing. Z1 counted on the screen (40 cells) has 8
cells to spare (gap 48 cells). The palette never binds: it is on screen in the crossing frame.

**What 336 looks like** (built, both shapes, and measured; commit `s2_ehz_cpz_short: the limit
test, 336 px`):
- **arriving EHZ (leftward), every speed: 2 frames.** On the crossing frame the leftmost
  2-16 px of the screen already show Emerald Hill, and in that strip the lower 15 of the 29
  background rows are still Chemical Plant's picture (the pixel scan counts at most 616 background
  pixels in the whole strip at the cap). On the next frame only the bottom background row (8 px
  tall, 16-32 px wide) is still wrong.
- **arriving CPZ (rightward): 0 frames at walk and top speed, 1 at the camera cap.** The first
  ~13 px of Chemical Plant, bottom background row only.
- It is the other zone's REAL background, in the right palette line, not garbage tiles (both
  zones' tiles are resident). The palette is never wrong.

### 8.5 What the owner should expect in `s2_ehz_cpz_short` (384 px)

- A tunnel 1.2 screens long (landed: 2.6). Walk through at any speed, either way, jump at the
  mouth: the colours and background change instantly while only tunnel is on screen, and
  nothing wrong was measured on the frame the far zone appears.
- It has **no margin at the camera cap**: the background is finished exactly as the far zone
  scrolls in. One slipped DMA there (a Deferrable queue refusal on that frame) would show the
  bottom background row of the far zone's first 16 px for one frame. None was seen in 12 runs.
- Past Chemical Plant's 2528 px there is a 448-px unpainted void (the act stays 7 sections), which the owner said
  does not matter.
