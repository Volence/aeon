# Harmony Framework — rendering / camera / effects / transitions research

Source: `aeon/docs/research/external/harmony/` (UltraRing Harmony Framework, GameMaker Studio 2 / GML).
Scope: rendering, camera, backgrounds, effects, transitions, special stage.
Framing: nothing transfers as code. Every item is classified as (a) emulating a real VDP
technique, (b) achievable on VDP by a different route, or (c) impossible / wrong on Genesis.

Paths below are relative to `aeon/` unless prefixed `harmony/`.

---

## 0. Executive summary

Harmony is unusually *un*-modern in its visual vocabulary: almost every effect it ships is a
GPU re-creation of a specific Genesis technique, because the authors were chasing S3K/Mania
fidelity rather than modern flash. That makes it a good mirror. Concretely:

- `shd_line_scroll` **is** the VDP per-line HScroll table, with one feature we do not have:
  a **linear scroll-factor ramp across a strip** (not a flat factor per band).
- `shd_line_dist` **is** our deform table — same 256-entry signed table, same
  `(line + time + offset) mod N` sampling. We have the machinery; they have better authored
  tables and a **camera-anchored phase** we lack.
- `shd_color_replacer` is CRAM palette-line swapping done the hard way (GameMaker has no
  indexed color). We get it for free; their *authoring form* (palette strip: column 0 = source,
  columns 1..N = variants) is worth stealing.
- `shd_color_grading` (3D LUT) is a full RGB remap — pointless on a 64-color machine, but it
  independently validates our §7.1 "computed water palette" instinct: they too wanted a
  *transform* of the base palette, not a hand-authored second palette.
- `shd_alpha_dither` is the classic Genesis 4x4 ordered dither, computed instead of baked.
- The **act transition** is the single best idea in the repo and has nothing to do with shaders:
  everything (player, camera, camera bounds, signpost, monitors, **and every parallax layer's
  scroll offset**) is stored *relative to a marker object* and rebased onto the next act's
  marker, so there is zero visual discontinuity across an act boundary. That is directly the
  mechanism our mega-act tech demo needs.

- The **Blue Sphere** stage is a verbatim port of Mania's tables, which are transitively S3K's.
  Its `palette_page` / `palette_line` variables are vestigial Genesis names that now index a
  sprite flipbook — 2 pages x 16 cycle steps = 32 frames exactly — which is direct evidence that
  **S3K's special-stage floor moved entirely by CRAM cycling on a static plane**, and that the
  projected sprites had to share that same phase counter. The geometry (four integer LUTs indexed
  by a depth row 0..111) would port to 68000 almost line-for-line; only the pre-rendered art
  would not.

**Top 4 to take:** per-band scroll ramp (#1), camera-anchored deform phase (#2), marker-relative
transition rebase (#3), moving camera boundaries + deterministic shake (#4/#5).

---

## 1. PARALLAX — how Harmony models and authors it

### The model

Backgrounds are a **parent object with parallel arrays**, one entry per layer
(`harmony/objects/par_background/Create_0.gml:3-22`). Per-frame, `Draw_0.gml:2-6` loops every
layer and calls `background_position_layer(i)` then `background_draw_layer(i)`.

Two layer kinds:

**(a) Flat layer** — `background_add(sprite, frame, scroll_x, scroll_y, spd_x, spd_y, off_x, off_y, vertical_loop)`
(`harmony/scripts/background_util/background_util.gml:13-32`). Position is
`pos_x = camX*factor_x + offset_x` (`background_util.gml:149-150`), drawn as a camera-clipped
tiled sprite (`harmony/scripts/render_util/render_util.gml:12-58`). `spd_x/spd_y` are auto-scroll
velocities added to the offset every frame when `global.process_objects`
(`background_util.gml:165-170`) — that is the classic "clouds drift independently of camera" layer.

**(b) Line-scroll layer** — `background_add_line(..., gaps, steps)`
(`background_util.gml:47-69`), drawn through `shd_line_scroll` (`background_util.gml:86-116`).
This is the interesting one; see §2.

**Authoring is code-per-background**, not data. A background is an object whose Create event is
a list of `background_add` calls (`harmony/objects/obj_aaz_bg_inside/Create_0.gml`,
`obj_aaz_bg_outside/Create_0.gml`, `obj_bg_base/Create_0.gml`). Layers are ordered by call order.
Backgrounds are swapped in/out by `obj_bg_switch` (`Step_0.gml:16-35`), which tests **the camera
centre** against a trigger rectangle and toggles `visible` on named background objects. Its
comment (`obj_bg_switch/Step_0.gml:12-14`) states the rationale explicitly: camera not player,
"in case of the player going faster than the camera". Per-layer runtime hiding is via a
`visibility[]` array documented at `obj_aaz_bg_inside/Draw_0.gml:3-12`.

### The revealing detail: they fake gradients with discrete strips

`obj_aaz_bg_inside/Create_0.gml:18-25` adds **eight** layers of the same sprite whose only
difference is an inline-interpolated factor:

```
background_add(spr_bg_aaz_ruins, 6,  0.8-((0.8-0.5)*(24/104)), 2/3, ...);
background_add(spr_bg_aaz_ruins, 7,  0.8-((0.8-0.5)*(32/104)), 2/3, ...);
...
background_add(spr_bg_aaz_ruins, 14, 1/2,                      2/3, ...);
```

i.e. "this strip sits 24 px into a 104 px band that ramps from factor 0.8 to 0.5". They are
hand-discretising a **continuous vertical scroll-factor gradient** — the thing S3K's HCZ water
does natively with a per-line HScroll ramp. Where the gradient must be smooth (the water), they
switch to the line-scroll layer instead.

### What we do today

Data-driven, comptime-generated records: `engine/level/parallax_dsl.emp` (factor encoding +
deform-table generators), `games/sonic4/data/parallax/configs.emp` (the 20 shipped configs),
`engine/level/parallax.emp` (1093 lines: `Parallax_Init` / `Parallax_CheckBoundary` /
`Parallax_StartTransition` / `Parallax_Update` / `Vscroll_Write`).

- Bands, not layers: a config is a 28-byte header + N x 10-byte `band_entry`, each band owning a
  **flat** FG factor and BG factor over a range of cell-rows (`configs.emp:38-51`).
- Factors are shift-add encoded — 14 canned fractions only (`parallax_dsl.emp:25-40`),
  deliberately multiply-free.
- Section-boundary config switch keys off the **camera centre** section index
  (`parallax.emp:133-152`) — same rationale Harmony documents.
- Layer enable mask + band inheritance (`configs.emp:257-265`, arch §4.6).

---

## 2. `shd_line_scroll` and `shd_line_dist`

### `shd_line_scroll` = the VDP per-line HScroll table, with a ramp

`harmony/shaders/shd_line_scroll/shd_line_scroll.fsh:22-29`:

```glsl
Diff     = (v_vPosition - Position);
LineCalc = 1. + ceil(Diff.y / LineGaps / YScale) * YSteps;
Result   = mod(floor(OffsetX * LineCalc) + Diff.x, Width) - Diff.x;
gl_FragColor = v_vColour * texture2D(gm_BaseTexture, vec2(v_vTexcoord.x + Result*TexelWidth, v_vTexcoord.y));
```

Read it as a scroll table: for screen row `y` within the strip, horizontal scroll is
`OffsetX * (1 + floor(y/LineGaps)*YSteps)`, `floor`ed to whole pixels, wrapped mod sprite width.
So:

- **`OffsetX`** is the layer's base scroll (`background_util.gml:158`: `camX*(1-factor_x) - off_x`).
- **`YSteps`** is a **per-line increment of the scroll factor** — a *linear ramp down the strip*.
- **`LineGaps`** groups N scanlines to one scroll value (quantises the ramp).
- **`YScale`** stretches the ramp (see §5, water).

Category **(a)**: this is exactly the VDP per-line HScroll table. `floor(...)` inside the mod
even reproduces the VDP's integer-pixel HScroll entries.

The authoring form is the payoff. `obj_aaz_bg_inside/Create_0.gml:29` plus its comment at 31-35:

```
background_add_line(spr_bg_aaz_water, 1, 2/3, 2/3, 0,0,0, 930, 1, (2/3)/96); // ID 17
/* 2/3 is the X factor of the TOP of the water, 96 is the height. This makes the top of the
   water parallax the same speed as the horizon and the bottom the same speed as the
   foreground ... now it can be done with a single division! */
```

That is: **a strip is authored by its two endpoint factors and its height**, and the runtime
walks the ramp. `obj_aaz_bg_outside/Create_0.gml:15` does the same for the outdoor water
(`gaps: 2, steps: 0.006`) — a coarser, gentler ramp.

**We do not have this.** Our bands are flat: `band(cell, fa, fb, dsa, dsb, phase)`
(`configs.emp:38-51`) gives one factor for the whole band, which is why our
"perspective"/"caves" configs stack 5 discrete bands to approximate a gradient
(`configs.emp:190-204`, `241-249`) — the same discretisation Harmony resorts to for its
non-line layers.

### `shd_line_dist` = our deform table, verbatim

`harmony/shaders/shd_line_dist/shd_line_dist.fsh:15-24`:

```glsl
float pixel  = v_vTexcoord.y * size.y;                       // screen scanline
float offset = dist[int(mod(pixel + time + offset, array_size))];
float dist_result = offset * (1.0 / size.x);
```

A signed offset table (max 512 entries), indexed by `(scanline + time + offset) mod N`, applied
as an X displacement (`mode 0`) or a Y displacement (`mode 1`), row-wise or column-wise
(`direction`). Driven by `effect_surface_deform(width, height, deform_data, offset, mode, dir)`
(`render_util.gml:285-314`).

Ours: `Parallax_Fill_PerLine` samples `deform_table[(phase + band_phase + line) & $FF]`,
downscaled by the band's `dsa`/`dsb` shift (`engine/level/parallax.emp:850-1016`,
arch §4.6). `mode 1` (Y displacement, column-indexed) is our per-column VSRAM path
(`pcfg_v_deform_table_bg`). Category **(a)**, and **[ALREADY HAVE]**.

Two things in their *use* of it that we lack:

**Camera-anchored phase.** `harmony/objects/obj_aaz2_water_effect/Create_0.gml:36` passes
`offset = cy + FRAME_TIMER/3` for the foreground, and line 62 passes
`offset = cy*(1 - 2/3) + FRAME_TIMER/3` for the background — i.e. the sample index is anchored in
the *layer's own* space (camera Y scaled by the layer's parallax residue), not in screen space.
Our phase is `phase += deform_speed` per frame, screen-anchored only
(`configs.emp:110`, arch §4.6) — so when the camera scrolls vertically our wave **slides against
the art it is deforming**. Fix is one add of `(Camera_Y >> k)` into the sample index.

**Table shapes.** Their FG ripple table (`obj_aaz2_water_effect/Create_0.gml:31-34`) is not a sine:
it is `1,1,2,2,3,3,3,3,2,2,1,1` then ~26 zeros, then the mirrored negative crest, then ~64 zeros
— **a pair of travelling ripple crests on a flat surface**, period 112. Their BG table
(`Create_0.gml:57-60`) *is* a sine, `8*sin(360/128*i)`. So: sharp localised ripples near the
camera, smooth swell far away. All our tables are pure sine/triangle/ramp
(`parallax_dsl.emp:51-99`). Adding a `deform_crest(amplitude, crest_width, period)` generator is
a 10-line comptime function.

Distortion patterns present in the repo: horizontal water wobble (above), a heat-haze-shaped
travelling ripple, the splash-screen logo warp (`obj_harmony_splash/Draw_0.gml:27,35` — an X warp
composed on top of a Y warp, two passes), and the stage-select background warp
(`obj_stage_select/Draw_0.gml:2`, mode 1 = vertical). We already ship shimmer/haze/rocking/
perspective variants (`configs.emp:119-204`); the only genuinely new pattern is the
**two-pass X-then-Y warp**, which on Genesis is per-line HScroll + per-column VSRAM applied
simultaneously — we already support both simultaneously.

---

## 3. `shd_color_replacer` / `shd_color_grading` — palette work

### `shd_color_replacer` = CRAM palette swapping

`harmony/shaders/shd_color_replacer/shd_color_replacer.fsh:9-20`: for each pixel, scan column 0
of a "palette sprite" for a colour within `u_fTolerance`; if found, output the colour at the
same row of column `u_fIndex`. Set up by `effect_set_palette(texture, index)`
(`render_util.gml:216-251`).

This is a **workaround for GameMaker having no indexed colour**. It is category (a): it emulates
exactly what the VDP does natively — swap the 16 CRAM words a tile references. We get it for
free via `Palette_Buffer` + `Palette_Dirty` DMA (`engine/system/buffers.emp:13-16, 106-137,
213-237`; `engine/ram.emp:201-202`).

Where they use it is the useful part — the full inventory of "palette transitions" in the repo:

| Site | Effect | Genesis equivalent |
|---|---|---|
| `obj_player/Draw_0.gml:4` `effect_set_palette(super_palettes[character], super_color)` | Super form palette cycling | CRAM line rewrite per frame — S3K does exactly this |
| `obj_aaz2_boss/Draw_0.gml:16,23` (`..._palette`, `..._palette_hit`) | Boss damage flash + per-frame palette animation | CRAM line rewrite for 1-2 frames |
| `obj_aaz1_boss/Draw_0.gml:2` | Hit flash | same |
| `obj_title_screen/Draw_0.gml:66` `index = FRAME_TIMER/4` | Logo shine — index cycles a strip | Classic palette cycling (our `sec_pal_cycle`) |
| `obj_bss_controller/Draw_0.gml:4` `palette_index` | Special-stage stage-number palette | CRAM |
| `obj_stage_select/Draw_0.gml:35,52,64` | Menu selection highlight | CRAM / different palette line per text row |
| `stage_bss_engine.gml:490` | Recolour to the awarded emerald's row | CRAM |

**Authoring form worth taking:** a palette is a 2D image strip, **column 0 = the source colours,
columns 1..N = variants, and a single byte index selects the variant**. On our side that is an
`N x 32`-byte table indexed by a byte, with entry 0 being the base — one comptime generator, and
it covers super forms, boss flash, and cycling with one mechanism.

**Genesis caveat to record:** the shader model implies **per-object arbitrary palettes**, which
do not exist. CRAM is 64 entries = 4 lines x 16, and a sprite/tile picks a line, not a colour set.
So "boss flash" on Genesis means either dedicating a palette line to the boss or rewriting that
line's 16 words for the flash frames. Any Harmony effect that recolours two objects that share a
palette line *differently in the same frame* is category (c).

### `shd_color_grading` = 3D LUT, i.e. an arbitrary RGB->RGB transform

`harmony/shaders/shd_color_grading/shd_color_grading.fsh:8-19`: standard unrolled-3D-LUT lookup
(`cell = floor(b*(size-1))`, x/y offsets from r/g). Applied by
`effect_set_color_grading(texture, size)` (`render_util.gml:257-275`).

Its intended use is spelled out in the **underwater** code path, present but commented out in
both `harmony/objects/obj_water/Draw_0.gml:31-50` and `obj_water_pool/Draw_0.gml:21-40`:

```
//IMPORTANT NOTE!! Enable this code if you wanna use shaders for color replacing instead of
//blend modes. You can either use palette_swap or set_color_grading
    surface_copy(surf, 0, 0, application_surface);
    effect_set_color_grading(yourlut, 17);
    draw_surface_part(surf, 0, y-cy, 426, cy, cx+64, y);   // only the region below the water line
```

So: **their underwater palette is a LUT transform of whatever is on screen, clipped to the region
below the water line.** With only 64 on-screen colours a 17^3 LUT is absurd for us — but the
*intent* is our §7.1 "Computed water palette (NOVEL)": derive the underwater palette from the
current palette by a transform, so it survives cycling and cross-fading. Harmony reaching for the
same shape from the opposite direction is decent corroboration that the idea is right.

### Transitions actually supported by Harmony

- **Fade to black / fade to white** — `harmony/scripts/fade_util/fade_util.gml:48-88`. One scalar
  timer `fade.timer` in 0..512; the three channels are read off it at staggered offsets
  `r = t-256, g = t-128, b = t`, clamped 0..255, XOR $FF, then drawn as a full-screen rect with
  `bm_subtract` (black) or `bm_add` (white) (`fade_util.gml:79-87`). The stagger means **blue
  drains first and red last** — that is the classic Sonic staggered per-component palette fade,
  not a uniform dim. Category (a); our §7.1 22-frame component-stepping fade is the same thing.
  The **single-scalar formulation** (one 0..512 number drives in, out, and colour, and the title
  card reuses it verbatim at `obj_titlecard/Draw_0.gml:11-31`) is a nice simplification.
- **Fade + scene change as one declarative call** — `fade_to_room(room, speed, colour, buffer)`
  / `fade_to_room_next` / `fade_in_room` / `fade_change` (`fade_util.gml:96-182`), with
  `fade.buffer` a hold-at-black delay before the switch (`fade_util.gml:21-43`).
- **Cross-fade between two palettes: NOT SUPPORTED.** There is no palette-to-palette lerp
  anywhere in the repo. Their equivalent is a hard background swap (`obj_bg_switch`).
- **Per-region tint:** yes, but as a blend rect (see §5), not as palette work.
- **Underwater palette:** the LUT path above, shipped-but-commented-out; the live path is a
  subtract-blend rect.

Our side: only the **dirty-line CRAM DMA** is implemented. Arch §7.1 states this outright:
cross-fading, computed water palette, per-section cycling, fades, flashes and per-scanline
gradients are all PLANNED, `sec_pal`/`sec_pal_cycle` (`engine/structs.emp:63,68`) have **no
runtime consumer**. Confirmed by grep: no fade/palette-blend/water code exists in `engine/` or
`games/sonic4/`. So Harmony is ahead of us on transitions purely because we have not built ours.

---

## 4. `shd_alpha_dither`

`harmony/shaders/shd_alpha_dither/shd_alpha_dither.fsh:14-56` builds a 4x4 ordered-dither
threshold matrix procedurally from a 0..1 opacity (`dPatlvl = int(opacity*16)`, then a 16-step
scatter that fills the matrix in dispersed order), then at line 66-71 sets
`gl_FragColor.a = dPattern[x mod 4][y mod 4] * sign(alpha)`.

Yes — this **is** the classic Genesis dithered-transparency look (ordered dither, screen-space
4x4, 17 discrete opacity levels). The shader header even says "read up on Ordered dithering".

**Where it is applied: exactly one place** — the framework splash logo dissolve,
`harmony/objects/obj_harmony_splash/Draw_0.gml:41` (`effect_set_alpha_dither(dither_timer)` on the
final composited logo surface). It is *not* used for water, shields, or any gameplay
transparency. Notably the water and shields use blend modes instead, i.e. they chose *not* to
use the authentic Genesis look where a modern one was available.

Genesis verdict: on real hardware the dither pattern is **baked into tile art**, not computed. A
17-step animated dissolve of the whole screen would mean re-uploading every tile per step —
impossible. But a **bounded** region is fine: an 8x8-tile logo is 64 tiles = 2 KB, so 16
pre-dithered levels cost 32 KB ROM and one 2 KB DMA per step. See ranked item #8.

---

## 5. WATER

Three cooperating pieces.

**(1) The tint.** `harmony/objects/obj_water/Draw_0.gml:14-18`: a `bm_subtract` rectangle of
colour `$5b301e` covering the full screen width from the water line downward. `obj_water_pool` does
the same over a **bounded rectangle** (`obj_water_pool/Draw_0.gml:4-8`) — local pools, not just a
global water line. Optional white flash on electric-shield loss
(`obj_water/Draw_0.gml:20-25`, gated by `WATER_FLASH` / `WATER_FLASH_COLOR` in
`harmony/scripts/game_config/game_config.gml:23-27`).

**(2) The surface.** `obj_water/Draw_0.gml:52-53`: an animated sprite tiled across the screen at
`y`, snapped to a sprite-width grid (`round(cx/spr_width)*spr_width`) so the surface tiles never
sub-pixel-crawl.

**(3) The water level itself.** `par_water/Step_0.gml:5`:
`y = math_approach(y, level_target, rise_speed)` — a smoothly-approaching level, driven by the
public `change_water_level(level, rise_speed, water_obj)`
(`harmony/scripts/level_util/level_util.gml:1-15`), which converts a target Y into a y-scale for
bounded pools. LBZ-style rising water for free.

**(4) `obj_aaz2_water_effect` — the underwater refraction.** This is the only place Harmony does a
real post-process. `Draw_0.gml:5-12` attaches begin/end scripts to three named tile layers
(`"BackgroundObject"`, `"PlaneFront"`, `"PlaneBack"`); `aaz2_water_dist_start`
(`Create_0.gml:5-18`) redirects that layer's rendering into a full-screen surface, and
`aaz2_water_dist_end` / `aaz2_water_dist_bg_end` (`Create_0.gml:20-68`) then draw the surface back
in **two pieces**:

```gml
effect_surface_deform(WINDOW_WIDTH, WINDOW_HEIGHT, distort_data, cy + FRAME_TIMER/3)
draw_surface_part(global.pal_surf, -8, obj_water.y-cy, W+32, cy, cx-8, obj_water.y); // below: warped
shader_reset();
draw_surface_part(global.pal_surf,  0, 0,             W+32, obj_water.y-cy, cx, cy); // above: clean
```

i.e. **the region below the water line is redrawn through the line-distortion shader; the region
above is untouched.** The BG variant uses the smooth 128-entry sine and the parallax-corrected
phase `cy*(1-2/3)`; the FG variant uses the sharp ripple-crest table and the plain `cy`. Note the
`-8` / `W+32` overscan margins — they widen the source so the horizontal warp never exposes an
empty edge.

**Genesis mapping:**
- The **split at the water line** is category (a): it is precisely an HInt raster event — swap
  palette (and optionally S/H mode) at scanline `water_y - camY`. This is already designed as
  arch §7.2's unified raster command table (`sec_raster_table` at `engine/structs.emp:65`), and
  `HBlank_Install` exists (`engine/system/hblank.emp:46-67`) with **zero consumers** today.
- The **below-line horizontal warp** is category (a): per-line HScroll on both planes for lines
  below the water line only. Our band + deform machinery already expresses this — a 2-band config
  whose lower band carries a deform table (exactly the shape of `ParallaxConfig_SkyHaze`,
  `configs.emp:227-233`).
- The **tint as a subtract blend** is category (c) as a blend — no alpha on Genesis. Achieve it as
  a second palette (what S3K does) or, for a *bounded* pool, via shadow/highlight on low-priority
  tiles (arch §7.3) — which gives half-brightness, not a blue shift.
- **`obj_water_pool` (bounded rectangular water) via a palette split is impossible** — a raster
  palette swap is full-width by construction. A bounded pool needs S/H + priority-tagged tiles,
  or a palette line dedicated to pool tiles.
- **The sprites warping too** (their surface capture warps the player) is category (c) for a true
  shear. Cheap approximation available: offset each underwater sprite's X by the deform table
  sampled at that sprite's Y — one lookup + one add per sprite. It jiggles the sprite as a rigid
  body rather than shearing it, but it sells the effect and costs nothing.

---

## 6. CAMERA

`harmony/objects/obj_camera/` + `harmony/scripts/camera_util/camera_util.gml`.

- **State machine:** `mode` dispatches to user events (`Step_2.gml:10` `event_user(mode)`):
  `CAM_NORMAL` (`Other_10.gml`), `CAM_RETURN` (`Other_11.gml`), `CAM_RETURN_KNUCKLES`
  (`Other_12.gml`). `camera_set_mode()` / `camera_return()` are the public API
  (`camera_util.gml:26-44`).
- **Two selectable follow profiles** via `global.camera_type` (`Other_10.gml:32`):
  - *type 0, "Mega drive games camera"* (`Other_10.gml:34-73`): grounded Y speed
    `2 + max(abs(gsp*sin(angle)), 4)`; airborne a +/-32 px deadzone at full `y_speed`.
  - *type 1, "Sonic mania camera"* (`Other_10.gml:76-118`): a `ground_offset` that is 32 while
    airborne and decays `ground_offset -= ground_offset/8` on landing (line 100) — a smooth
    re-centre instead of a hard deadzone snap. Pure shift-subtract; trivially 68000-able.
- **X deadzone:** asymmetric 16 px hold on the left, hard follow on the right
  (`Other_10.gml:17-26`) — identical to ours (`engine/level/camera.emp:230-251`,
  `CAM_X_DEADZONE_INIT = $10`).
- **Camera lag:** `h_lag` / `v_lag` frame counters that suppress follow entirely, decremented in
  `Step_2.gml:39-40`, set via `camera_set_lag()` (`camera_util.gml:5-21`). Ours is the narrower
  `Camera_Hold_Frames` spindash freeze (`camera.emp:206-227`) — same idea, less general.
- **Look up / look down:** a 120-frame hold then `math_approach(look_shift, -104 | +88, 2)`
  (`Other_10.gml:122-154`) — the classic S3K values, and note the asymmetry (104 up, 88 down).
  We have **nothing**: `DEFERRED_WORK.md:520-525` records the duck/look-up camera pan as
  explicitly not implemented.
- **Lookahead pan:** `global.camera_pan_type` (`Other_10.gml:157-193`) — type 1 is Sonic CD
  (approach +/-64 px when `|gsp| >= 6` or spindash/peelout, else return to 0); type 2 is a
  velocity-proportional lerp `lerp(shift_x, gsp*4*cos(angle), 0.1)`. Ours: `Camera_Pan_Offset`
  exists but is **write-only scaffolding** (`camera.emp:159-164`) and `sec_camera_lookahead`
  (`engine/structs.emp:76`) has no consumer.
- **Screen shake — two mechanisms, both in `Step_2.gml:16-32`:**
  - `camera_shake`: `random_range(-camera_shake, camera_shake)` with exponential decay
    `camera_shake *= 0.9`, cut to 0 below 1.
  - `shake_x` / `shake_y`: **deterministic** — the sign alternates on frame parity
    (`FRAME_TIMER % 2 == 0 ? shake_x : -shake_x`) and the magnitude decays linearly by
    `shake_speed`. Zero table, zero RNG.
  We have neither; arch §7.5 plans table-driven shake.
- **Animated camera boundaries** (`camera_util.gml:52-126`): each of the four limits creeps
  toward its target at 2 px/frame, with escape clauses that snap when the limit is already
  off-screen (`if(limit_bottom > cy + sh + 16) limit_bottom = target_bottom;`, line 77, and the
  three analogues). `obj_camera_boundary/Step_0.gml:7-21` sets `target_bottom` from a trigger
  volume, and disarms on the player's death (line 4). This is the generic S3K boss-arena /
  bottomless-floor lock. Ours: a static world-space clamp only (arch §4.5, `camera.emp:278-281`).

**Beyond classic Sonic:** the two selectable follow profiles and two selectable pan profiles
(runtime-switchable), the generic animated boundary system, and the deterministic shake. Nothing
here requires anything the 68000 cannot do — it is all compares, adds and shifts.

---

## 7. TRANSITIONS — title cards, act transitions, fades

### Title card (`harmony/objects/obj_titlecard/`)

Motion is authored as **GameMaker animation curves**: `curve_titlecard` with four named channels,
evaluated at normalised time (`Step_0.gml:27-36`, `Draw_0.gml:49-53`). Each moving element gets its
own channel *and its own duration*, which is how the stagger is authored:

```gml
offset[0] = animcurve_channel_evaluate(c_channel_1, min(timer/80, 1))  * global.window_width;  // bar sweep
offset[1] = animcurve_channel_evaluate(c_channel_2, min(timer/80, 1))  * (58+48);              // lower bar Y
offset[2] = animcurve_channel_evaluate(c_channel_2, min(timer/80, 1))  * 58;                   // upper bar Y
offset[4] = -w(zone) - 24 + animcurve_channel_evaluate(c_channel_3, min(timer/100,1)) * (w(zone)+71+24);
offset[6] = -w(act)  - 24 + animcurve_channel_evaluate(c_channel_4, min(timer/100,1)) * (w(act) +71+24);
```

Three curve assets exist: `curve_titlecard`, `curve_titlecard_leave`, `curve_titlecard_bonus`
(`harmony/animcurves/`). There is also a **counter-scrolling ribbon**
(`Draw_0.gml:70-73`): the same 5 sprite pieces drawn twice, one column moving down at `timer` and
an 8 px strip moving up at `timer/2`.

`harmony/scripts/ease_util/ease_util.gml` supplies 30 named easing functions (sine/quad/cubic/
quart/quint/expo/circ/back/elastic/bounce, in/out/inout) as the code-side alternative to curves.

The card also reuses the fade formula inline for its own screen darkening (`Draw_0.gml:11-31`),
and drives `obj_player.input_disable` / `obj_level.disable_timer` (`Create_0.gml:15-16`) and
`obj_hud.slide_in` (`Step_0.gml:17`).

### Act transition (`harmony/objects/obj_act_transition/`) — the best idea in the repo

An `obj_act_trans_marker` is placed in **both** the outgoing and incoming rooms. On transition,
`Create_0.gml:9-65` stores **everything relative to that marker**:

```gml
player_pos[0] = player.x - marker.x;             camera_pos[0] = obj_camera.camera_x - marker.x;
cam_bound[0..3] = obj_camera.limit_* - marker.*; sign_pos[0..1] = obj_signpost.* - marker.*;
for each background object, for each of its layers:
    array_push(data.list_x, bg.diff_x[n]);       // stored parallax residue, see below
    array_push(data.list_y, bg.diff_y[n]);
for each monitor: monitor_x[i] = ... - marker.x; (plus type, destroyed, depth)
```

then `room_goto(next_level)`. `Other_4.gml:9-75` re-applies all of it against the **new** room's
marker. The parallax half (`Other_4.gml:38-58`) writes each layer's stored residue into
`offset_x/offset_y` and sets `trigger[n] = true`; `background_util.gml:129-143` consumes that
trigger once, re-solving the offset so the layer lands **exactly where it was on screen**:

```gml
if(trigger[bg]) {
    var reposition_x = camX*factor_x[bg] + offset_x[bg];
    diff_x[bg] = reposition_x - camX;
    offset_x[bg] += offset_x[bg] - diff_x[bg];
    trigger[bg] = false;
}
```

`diff_x/diff_y` are maintained every frame as "layer position minus camera position"
(`background_util.gml:152-153, 161-162`) precisely so this rebase is possible. **Result: crossing
an act boundary produces zero visual discontinuity in any parallax layer.**

This is structurally the same trick as our teleport rebase / floating-origin rebase
(memory: "Teleports are pure rebases"; arch §4.11), applied to *presentation* state rather than
world coordinates. It is exactly the mechanism the mega-act tech demo needs at a corridor seam.

### Fades

Covered in §3. Note the presentation vocabulary is small and entirely classic: staggered
component fade to black or white, title card, act transition, background switch. No wipes, no
irises, no cross-fades.

---

## 8. BLUE SPHERE special stage

`harmony/scripts/stage_bss_engine/stage_bss_engine.gml:1` states the provenance outright:

```gml
// Blue Spheres engine, accurate port of Sonic Mania's code.
```

— i.e. a port of Mania's RSDKv5 `BSS_Setup`/`BSS_Collectable`, which are themselves a
reimplementation of S3K. Every function carries its original RSDK symbol as a comment
(`// BSS_Setup_State_GlobeTurnLeft`, `// BSS_Setup_CollectRing`, `//== Mania's tile & 0x3FF`, …),
and the lookup tables are annotated `// Lookup tables copied verbatim from Mania's
BSS_Setup.h / BSS_Collectable.h` (`stage_bss_engine.gml:162`). **This is a transitive copy of the
S3K ROM's own tables**, which makes it unusually informative about the original.

### Data model

Flat 1-D array, **column-major**, torus-wrapped on both axes
(`stage_bss_engine.gml:66-83`: `bss_idx(x,y) = wrap_x(x)*BSS_H + wrap_y(y)`). Default 32x32,
runtime-variable with a 16 minimum (`:108-152`). Cell types are an enum 0..19
(`:8-30`) with **bit 7 = "player is standing on it"** (`GREEN_STOOD=0x81`, `BLUE_STOOD=0x82`,
`PINK_STOOD=0x86`) and `& 0x7F` masking everywhere — a straight S3K-ism.

Authoring is a **GameMaker tile layer named `"Playfield"` where tile index == cell value**
(`:140-141`), backed by a 12-tile 16x16 editor-only tileset
(`tilesets/tile_bss_playfield/tile_bss_playfield.yy:36-42`), hidden at load (`:148`). Two arrays:
`pf_stage` (immutable template) and `pf` (live working copy, re-copied per attempt at `:945-946`).

### Rendering: (c) sprite-per-cell with an integer LUT projection, over a pre-rendered floor

No tilemap+line-scroll, no matrix, no mesh, no vertex buffer, no shader except the palette swap
(`obj_bss_controller/Draw_0.gml:4`).

**The floor** is a **32-frame pre-rendered 512x240 flipbook** (`spr_bss_globe_roll`), indexed
`bf = ((palette_page & 1)*16 + palette_line) mod 32` (`Draw_0.gml:21`), plus two 15-frame turn
flipbooks. That is the one wholly non-hardware piece: ~5.9 MB of raw pixels.

**The spheres/rings** are projected per-cell (`Draw_0.gml:52-105`). Quoted core:

```gml
var sx  = ((ox * cs + oy * sn) >> 4);          // 2x2 integer rotation, cs/sn are 8.8
var sy  = ((oy * cs - ox * sn) >> 4);
var dep = -(sy + palette_line - 16);           // integer DEPTH ROW, 0..111
if (dep < 0 || dep >= 112) continue;
var f     = global.bss.frameTable[dep] - (abs(sx) >> 5);      // discrete scale frame
var fxv   = global.bss.xMultiplierTable[dep] * sx;            // 1/z horizontal fan
var dist  = (fxv * fxv) div 65536;
var worldX= (((fxv <= 0) ? fxv + dist : fxv - dist) >> 4);    // barrel/arc correction
var dx = worldX + center_x;
var dy = global.bss.screenYTable[dep] + (worldX*worldX) div global.bss.divisorTable[dep];
```

Four parallel LUTs indexed by the integer depth row: `screenYTable` (280→38, the perspective Y
curve), `xMultiplierTable` (134→36, the 1/z fan), `divisorTable` (4096→802, the globe's curved
horizon term), `frameTable` (31→0, sprite scale). **There is no Z, no near/far plane, no
divide-by-w.** Visible cells come from two **hand-authored** offset lists — `frustum1` (59
entries, axis-aligned) and `frustum2` (81, mid-turn) — ordered back-to-front, so painter's-order
depth sorting is free with no sort step (`:1012-1013` records that Mania authored these as tile
layers and baked them). Scaling is **16 discrete pre-drawn sprite frames**, not continuous
(`:455-502`, `_f div 2` into 16-frame sprites).

### Rotation and horizon

Discrete 90 degrees, animated over 16 frames at 4 binary-degrees each (256 units/turn), queued at
cell boundaries and never mid-cell (`obj_bss_controller/Step_0.gml:145-223`). Position on the
board stays integer; `globe_timer` (0..255) is the sub-cell fraction, and
`sin256(angle) >> 8` collapses the 8.8 sine to an exact -1/0/+1 cardinal step (`:170-172`).

The turn's floor animation is **15 frames that are only 8 unique images, mirrored**
(`stage_bss_engine.gml:195-197`):

```gml
globeFrameTable = [0,1,2,3,4,5,6,7,6,5,4,3,2,1,0];
globeDirTableL  = [0,0,0,0,0,0,0,0,1,1,1,1,1,1,1];   // horizontal flip flag
```

Sky is a tiled 512x256 starfield whose horizontal scroll is a **direct function of facing angle**:
`bg_scroll_x = (angle & 255) * 4` (`Step_0.gml:483`) — two wraps of the 512-wide sky per full
turn, which is what sells the rotation. Mania's additive horizon glow is present but deliberately
commented out (`Draw_0.gml:27-33`, "Uncomment this if you like Sonic Mania!").

### Per-frame cost and 68000 plausibility

All integer. Not one `sin`/`cos`/`sqrt`/`matrix_*`/float-divide in the draw path; `sin256`/`cos256`
are a 256-entry 8.8 table (`scripts/math_util/math_util.gml:94-129`). Worst case per frame: 81
frustum iterations, ~6 `MULU` and **1 `DIVU`** per surviving cell. At 7.67 MHz / 127,800 cycles
per NTSC frame: 81 `DIVU.W` ~ 11,300 cycles (~9 %); ~500 `MULU.W` ~ 35,000 (~27 %), but most
frustum cells are `NONE` and bail before any multiply (`Draw_0.gml:71`), and depth-culling kills
more (`:81`) — real occupancy is ~20-40 cells. **The geometry math would port to 68000 almost
line-for-line.** Everything else is `>> 4 / >> 5 / >> 8 / & 255 / & 0x3F`.

The one heavy off-frame routine is `bss_process_chain` (`:388-452`), O(W·H) with an O(W+H) inner
4-ray enclosure test — worst case ~130 k inner steps on a blue-sphere pickup, i.e. several frames
of 68000 time. That is consistent with the original's known brief hitch when a large enclosure
converts.

### What it reveals about the S3K original

The decisive fossil is the **vestigial palette machinery**. `palette_page` and `palette_line` are
named for the Genesis mechanism — S3K animated the checkerboard by **cycling CRAM entries** and
flipping between two palette pages at every cell crossing. In this port they touch no palette at
all; they index the sprite flipbook. `palette_line = (globe_timer >> 4) & 15` (`Step_0.gml:197`)
gives 16 cycle steps; `palette_page ^= 1` fires at each cell crossing (`:173, :186, :346, …`).
**2 pages x 16 steps = 32 = exactly the flipbook length.** The 32-frame sprite is a 1:1 bake of
the original's palette-animation state space.

And decisively, `Draw_0.gml:78`:

```gml
var dep = -(sy + palette_line - 16);   //Depth row, blending in the roll scroll
```

**The sphere depth row is offset by the palette cycle step.** On hardware the floor's apparent
forward motion *was* the palette phase, so the sprites had to be indexed off the same counter to
stay glued to it. That is a hardware constraint leaking through two ports, and it tells you
exactly how S3K's Blue Sphere floor worked: a **static warped-checkerboard plane whose motion is
100 % palette cycling**, with sprites projected through integer depth-row LUTs sharing the same
phase counter.

### Game logic worth noting

- **Collision is grid-cell, evaluated twice per traversal**: the *current* cell in the first half
  of the roll and the *cell ahead* in the second half, with per-type `globe_timer` windows
  (`stage_bss_engine.gml:571-813`) — BLUE `<128`/`>128`, RED `<32`/`>224`, BUMPER `<112`/`>144`
  with nested sub-cases, PINK `<64`, etc. Hand-tuned originals.
- **Blue→red conversion is deferred** through a `collected` event queue (`:816-891`): a stepped
  blue becomes `BLUE_STOOD` and only flips to `RED` once the player has rolled clear
  (`globe_timer > 32 && < 224`). Green does the inverse with a 10-frame countdown — which is
  why greens feel "sticky".
- **Ring enclosure** is a 4-way flood-walk with a **dead-end unwind** (`:243-341`: a tail that
  never branched is retracted), closed-loop detection by return-to-start, then a 4-ray
  inside/outside test (`:344-384`) and a "hell pit" trim (`:418-439`) whose comment preserves the
  community nickname for a known S3K quirk rather than fixing it.
- **"Perfect" is a countdown, not a comparison**: `ring_count` starts at 64 and decrements; zero
  fires the message (`:529-546`). `rings_collected` (score) is tracked separately.
- **Speed ramps +4 every 30 s, capped at 32** (`Step_0.gml:130-134`), and the same block is
  duplicated verbatim inside both turn states so the timer does not stall during a turn — a
  faithful quirk. It drives gravity, roll rate, tail rate, and **music pitch**
  `power(1.05, (max(speedup,16)-16)/4)` (`:504`).

---

## 9. RANKED CANDIDATES

### 1. Per-band **linear scroll-factor ramp** in the HScroll fill — [WORTH TAKING — VDP-feasible]

**Harmony:** `shd_line_scroll.fsh:24-27` (`LineCalc = 1 + ceil(Diff.y/LineGaps/YScale)*YSteps`),
authored as two endpoint factors + a height at `obj_aaz_bg_inside/Create_0.gml:29` and
`obj_aaz_bg_outside/Create_0.gml:15`.

**Genesis equivalent:** the VDP per-line HScroll table already accepts an arbitrary value per
scanline (reg $0B mode %11, 224 x 4 bytes at `VRAM_HSCROLL_TABLE`). A ramp is simply a different
fill pattern — an accumulator add per line instead of a constant store. **Zero extra DMA**
(still 896 B, `engine/system/buffers.emp:151-155`), and roughly the same cycle count as the
current per-line loop.

**Ours today:** flat factor per band (`configs.emp:38-51`; fill at
`engine/level/parallax.emp:850-1016`). We fake gradients with 5 stacked bands
(`configs.emp:190-204`, `241-249`) and cap out at 8 bands.

**Why it matters:** this is the one *capability* Harmony has that we do not. It is the S3K HCZ
water/floor look. It also sidesteps a real limitation of our factor encoding: the shift-add set
has only 14 representable fractions (`parallax_dsl.emp:25-40`), so a stacked-band gradient snaps
to coarse steps, whereas a per-line accumulator ramp is smooth by construction (the ramp delta is
a fixed-point increment, not a canned fraction). Suggested shape: two extra `band_entry` bytes,
`band_ramp_a` / `band_ramp_b` (signed 8.8 delta per line, 0 = current flat behaviour), consumed
as one `add.w` per line in `Parallax_Fill_PerLine`.

**Verdict: [WORTH TAKING — VDP-feasible].** Highest value in this report.

### 2. Camera-anchored deform phase — [WORTH TAKING — VDP-feasible]

**Harmony:** `obj_aaz2_water_effect/Create_0.gml:36` (`offset = cy + FRAME_TIMER/3`) and `:62`
(`offset = cy*(1 - 2/3) + FRAME_TIMER/3`) — the deform sample index is anchored in the deformed
layer's own space, scaled by that layer's parallax residue.

**Genesis equivalent:** add `(Camera_Y * (1 - factor)) >> k` into the sample index. With our
shift-add factors, `(1 - factor)` is itself a shift-add, so this is 2-3 instructions per frame,
computed once outside the fill loop.

**Ours today:** `Parallax_Fill_PerLine` samples at `(phase + band_phase + line) & $FF`, where
`phase` only advances by `deform_speed` per frame (arch §4.6; `configs.emp:110`). The wave is
pinned to the screen, so it slides across the artwork whenever the camera moves vertically.

**Verdict: [WORTH TAKING — VDP-feasible].** Near-free correctness fix to a shipped system.

### 3. Marker-relative rebase of ALL presentation state across a transition — [WORTH TAKING — authoring/tooling idea]

**Harmony:** `obj_act_transition/Create_0.gml:9-65` + `Other_4.gml:9-75` +
`background_util.gml:129-143` (the `trigger[]` re-solve) + `background_util.gml:152-153,161-162`
(`diff_x/diff_y` maintained every frame for exactly this purpose).

**Genesis equivalent:** nothing hardware-specific; it is a data-model discipline. Store the
*residue* (layer scroll minus camera scroll) rather than the absolute scroll, and re-solve the
offset against the new anchor so the on-screen position is invariant.

**Ours today:** `Parallax_StartTransition` (`engine/level/parallax.emp:190-199`) does a 16-frame
per-band lerp toward the new config's targets, or an instant snap when `pcfg_transition = 1`
(`configs.emp:243`). Both are *approximations of continuity*; neither preserves the layer's exact
on-screen position. Plane A is never lerped at all (arch §4.6), for good reasons.

**Why it matters:** memory records the mega-act tech demo goal — several zones as one seamless
act with corridor seams. At a corridor the parallax config *must* change (different zone art)
without the sky jumping. A residue rebase gives exactly that, and composes with our existing
lerp: rebase the offset for continuity, then lerp the *factors*.

**Verdict: [WORTH TAKING — authoring/tooling idea]**, with direct engine consequences.

### 4. Animated camera boundaries + boundary trigger volumes — [WORTH TAKING — VDP-feasible]

**Harmony:** `camera_util.gml:52-126` (four limits creeping at 2 px/frame toward targets, with
off-screen snap escapes at lines 77, 93, 109, 125), driven by `obj_camera_boundary/Step_0.gml:7-21`.

**Genesis equivalent:** pure integer arithmetic on four RAM words. Zero VDP cost.

**Ours today:** static world-space clamp computed from grid dimensions
(`engine/level/camera.emp:278-281`, arch §4.5). No moving limits, no trigger volumes.

**Why it matters:** boss arenas, bottomless-pit floors, and act-end lockups all need this, and it
is a prerequisite for any boss encounter. The "snap if already off-screen" escapes are the
non-obvious part — without them a limit that moves *toward* the camera can shove the view.

**Verdict: [WORTH TAKING — VDP-feasible].**

### 5. Deterministic parity screen shake — [WORTH TAKING — VDP-feasible]

**Harmony:** `obj_camera/Step_2.gml:16-22`:
`shake_x_result = (FRAME_TIMER % 2 == 0 ? shake_x : -shake_x)`, magnitude decremented linearly.
(They also ship a random variant with `*= 0.9` decay, lines 25-32.)

**Genesis equivalent:** `btst #0, frame_counter` + `neg.w`. No table, no RNG, ~6 instructions.

**Ours today:** none shipped; arch §7.5 plans two precomputed offset tables.

**Why it matters:** it is *deterministic*, which matters directly for our input-replay fixtures
(memory: "Oracle screenshots aren't deterministic — use the input-replay net"). An RNG-driven
shake would desync replays; a parity shake cannot. It is also strictly cheaper than the planned
tables.

**Verdict: [WORTH TAKING — VDP-feasible]**, and prefer it over the planned §7.5 tables for the
timed-impact case.

### 6. Palette-variant strip: column 0 = source, columns 1..N = variants, byte index selects — [WORTH TAKING — authoring/tooling idea]

**Harmony:** `render_util.gml:216-251` + `shd_color_replacer.fsh:9-20`; consumed at
`obj_player/Draw_0.gml:4` (super forms), `obj_aaz2_boss/Draw_0.gml:16,23` (damage flash + anim),
`obj_title_screen/Draw_0.gml:66` (logo shine via `FRAME_TIMER/4`), `obj_bss_controller/Draw_0.gml:4`,
`stage_bss_engine.gml:490`.

**Genesis equivalent:** an `N x 32`-byte table indexed by a byte, DMA'd into one CRAM line via
`Palette_Buffer` + `Palette_Dirty` (`engine/system/buffers.emp:106-137`). Free.

**Ours today:** `sec_pal` and `sec_pal_cycle` fields exist (`engine/structs.emp:63,68`) with **no
runtime consumer** — arch §7.1 says so explicitly.

**Why it matters:** one uniform data shape covers super forms, boss hit flash, logo shine,
per-section cycling, and menu highlight. That is the whole §7.1 palette backlog behind a single
comptime generator and one `Pal_SetVariant(line, table, index)` routine.

**Caveat to record in the design:** CRAM is 4 lines x 16. Two objects sharing a palette line
cannot be recoloured differently in the same frame; the shader model silently assumes they can.

**Verdict: [WORTH TAKING — authoring/tooling idea].**

### 7. Water line as a raster split + region-limited deform — [WORTH TAKING — VDP-feasible] (validates a design we already have but have not built)

**Harmony:** `obj_aaz2_water_effect/Draw_0.gml:5-12` + `Create_0.gml:20-68` — the frame is split
at the water line and only the lower part is warped; `obj_water/Draw_0.gml:14-18` tints the lower
region; `par_water/Step_0.gml:5` + `level_util.gml:1-15` animate the water level smoothly.

**Genesis equivalent:** an HInt raster command at scanline `water_y - camY` doing a palette-line
swap (and optionally an S/H toggle), plus a 2-band parallax config whose lower band carries a
deform table. Both halves are already designed: arch §7.2 raster command table with
`sec_raster_table` (`engine/structs.emp:65`), and `SkyHaze` (`configs.emp:227-233`) is already the
exact 2-band regional-deform shape.

**Ours today:** `HBlank_Install` exists (`engine/system/hblank.emp:46-67`) and has **zero
consumers**. `DEFERRED_WORK.md:206-208` records water as port-gate-cleared but wanting its own
design pass. No water code exists.

**Verdict: [WORTH TAKING — VDP-feasible].** Harmony confirms the decomposition (split line +
regional warp + smooth level animation + surface strip) and hands us the two distortion tables to
start from. Take the *decomposition*, not the surface-capture mechanism.

### 8. Ordered-dither dissolve for a bounded region — [WORTH TAKING — VDP-feasible, bounded only]

**Harmony:** `shd_alpha_dither.fsh:14-71`, applied only at `obj_harmony_splash/Draw_0.gml:41`.

**Genesis equivalent:** pre-dithered art levels DMA'd per step. A logo of 64 tiles = 2 KB per
level; 16 levels = 32 KB ROM and one 2 KB DMA per dissolve step — comfortably inside the VBlank
budget. Full-screen is category (c): re-uploading the whole tile pool per step is impossible.

**Ours today:** nothing; not planned.

**Verdict: [WORTH TAKING — VDP-feasible] for logos/title-card elements; [REJECT] for
full-screen.** Also record that the *classic* Genesis look is the 50 % checkerboard specifically,
which composite video blurs into real translucency — the 17-level ramp is a modern liberty.

### 9. Two selectable camera follow profiles + two pan profiles — [WORTH TAKING — VDP-feasible, taste-gated]

**Harmony:** `obj_camera/Other_10.gml:32-118` (`global.camera_type` 0 = Mega Drive, 1 = Mania
smooth focus with `ground_offset -= ground_offset/8`) and `:157-193` (`global.camera_pan_type`
1 = Sonic CD, 2 = velocity lerp).

**Genesis equivalent:** all shift/add/compare. Trivial.

**Ours today:** classic S3K fixed deadzones only (`engine/level/camera.emp:230-251`, `:300`);
`Camera_Pan_Offset` is write-only scaffolding (`camera.emp:159-164`); `sec_camera_lookahead`
(`engine/structs.emp:76`) has no consumer; look-up/duck pan explicitly deferred
(`DEFERRED_WORK.md:520-525`).

**Verdict: [WORTH TAKING — VDP-feasible]**, but the *choice* of profile is a design call, and
memory records an S3K-baseline ruling. Recommendation: take the **CD-style pan** to finally give
`Camera_Pan_Offset` / `sec_camera_lookahead` their consumer, and the **look-up/look-down shift**
(the 120-frame hold and the asymmetric -104 / +88 targets are the authentic classic values). Skip
the Mania follow profile unless the user asks for it.

### 10. Asymmetric ripple-crest deform tables (not just sines) — [WORTH TAKING — authoring/tooling idea]

**Harmony:** `obj_aaz2_water_effect/Create_0.gml:31-34` — a hand-authored 112-entry table that is
two short travelling crests separated by long flat runs, used for the near-field warp, paired with
a smooth `8*sin` table for the far field (`Create_0.gml:57-60`).

**Genesis equivalent:** identical — a 256-byte signed table, which is exactly what
`engine/level/parallax_dsl.emp:51-99` emits.

**Ours today:** `deform_sine`, `deform_triangle`, `deform_zero`, `v_column_perspective`,
`v_column_floor` — all continuous, all symmetric.

**Verdict: [WORTH TAKING — authoring/tooling idea].** A `deform_crest(amplitude, crest_width,
period)` comptime generator is ~10 lines and gives water a visibly different character from heat
haze, which today share a wave shape.

### 11. Line grouping (`LineGaps`) as a fill-loop optimisation — [WORTH TAKING — VDP-feasible, small]

**Harmony:** `background_add_line(..., gaps, ...)`; `shd_line_scroll.fsh:24`
(`ceil(Diff.y / LineGaps / YScale)`) — N consecutive scanlines share one scroll value.

**Genesis equivalent:** the **DMA cannot shrink** — per-line mode is 896 B whatever the content
(`engine/system/buffers.emp:151-155`), and `DEFERRED_WORK.md:571` measures that DMA at ~20 % of
frame as a flat tax. But the **fill** can: compute one value and store it 4x with an unrolled
`move.l` run instead of sampling and computing per line. `DEFERRED_WORK.md:583-588` already banks
a "computed-jump-table unroll" for the same loop (~7.4 % of frame, ~2200 cycles of `dbf`
overhead); line-grouping composes with it.

**Verdict: [WORTH TAKING — VDP-feasible]**, but modest, and it *conflicts* with candidate #1 (a
smooth ramp wants per-line resolution). Treat as a per-band opt-in for bands with no ramp and no
deform.

### 12. Bounded water pools (`obj_water_pool`) — [REJECT — impossible via palette split; partial via S/H]

**Harmony:** `obj_water_pool/Draw_0.gml:4-8` tints an arbitrary rectangle, and
`level_util.gml:5-8` animates its height via `image_yscale`.

**Genesis:** a raster palette swap is inherently **full-width** — the CRAM change applies to the
entire scanline. There is no way to tint a horizontal sub-range of a scanline via palette. The
achievable substitutes are: (a) shadow/highlight on low-priority tiles (arch §7.3), which gives
half-brightness rather than a blue shift and is bounded per-pixel; (b) a palette line dedicated to
pool-region tiles, which costs one of only four lines and cannot cover sprites entering the pool.

**Verdict: [REJECT — impossible as designed].** Record the S/H substitute as the fallback if a
level ever wants a local pool.

### 13. `shd_color_grading` LUT for the underwater transform — [REJECT — wrong tool, right idea]

**Harmony:** `shd_color_grading.fsh:8-19`, wired to the water at `obj_water/Draw_0.gml:41`
(commented out in favour of blend modes).

**Genesis:** with 64 on-screen colours a 17^3 LUT is meaningless — the transform *is* just a
second 128-byte palette, or better, a computed one. Their reaching for a transform rather than a
hand-authored second palette does corroborate our §7.1 "computed water palette" plan; on 9-bit
RGB the equivalent is `(c >> 1) + bias` per 3-bit component with clamping, which is a handful of
instructions per colour over 64 colours.

**Verdict: [REJECT — the mechanism]; the intent is already ours (arch §7.1) and remains
unimplemented.**

### 14. Full-frame surface capture and re-warp — [REJECT — impossible]

**Harmony:** `obj_aaz2_water_effect/Create_0.gml:5-18` + `Draw_0.gml:5-12` — render tile layers to
an off-screen surface, then draw that surface back through a distortion shader.

**Genesis:** there is no framebuffer to read back. The VDP composites planes and sprites at scan
time; nothing renders to memory you can re-sample. What *is* reachable is the same visual outcome
for **planes** via per-line HScroll (which is what S3K actually does), so the effect survives even
though the mechanism does not.

**Verdict: [REJECT — impossible].** Consequence to record: their warp also warps **sprites**
(the player ripples underwater); per-line HScroll does not touch sprites. A cheap partial: offset
each underwater sprite's X by the deform table sampled at its own Y — rigid jiggle, not shear, but
one lookup and one add per sprite.

### 15. Per-object arbitrary palettes — [REJECT — impossible]

Implicit throughout `effect_set_palette` usage. CRAM is 64 entries = 4 lines x 16; a sprite selects
a line, not a colour set. Any Harmony frame that recolours two objects sharing a line differently
is unreachable. Not a feature request — a constraint to keep visible when porting any of their
palette effects.

### 16. Confirmations (no action)

- **Camera-centre-driven background/config switching** — `obj_bg_switch/Step_0.gml:12-19` states
  the rationale (player can outrun the camera); we already key `Parallax_CheckBoundary` off the
  camera centre (`engine/level/parallax.emp:133-152`). **[ALREADY HAVE]**, independently confirmed.
- **Per-layer visibility toggling** — `background_util.gml:76-77`, `obj_aaz_bg_inside/Draw_0.gml:3-12`
  vs our `pcfg_layer_mask` with band inheritance (`configs.emp:257-265`). **[ALREADY HAVE]**, and
  ours is strictly better (inheritance semantics, no per-frame conditional).
- **Camera-clipped tiled background draw** — `render_util.gml:12-58` computes exactly the tile
  range overlapping the view. The VDP does this for free via 64x64 plane wrap; our BG plane is
  512 px tall for precisely this (`engine/level/bg.emp:16-22`). **[ALREADY HAVE — in hardware]**.
- **Render-state push/pop stack** — `render_util.gml:85-158`. Our VDP shadow table (arch §0.4) is
  the same idea, RAM-resident. **[ALREADY HAVE]**.
- **Auto-scroll layers** (`speed_x/speed_y`, `background_util.gml:165-170`; used for drifting
  clouds at `obj_aaz_bg_outside/Create_0.gml:10-14` with per-layer speeds -0.2 .. 0). We express
  the same thing through the deform phase for waves, but **we have no plain constant-velocity
  layer drift**: every band's scroll is a pure function of `Camera_X`. Worth a one-word
  `band_autoscroll` accumulator — cheap, and it is how cloud layers have looked since Sonic 1.
  Flag as a small **[WORTH TAKING — VDP-feasible]** addition folded into candidate #1's band-entry
  extension.
- **Fade-then-change-scene as one declarative call** (`fade_util.gml:96-137`) maps onto our §9.13
  game-state machine as a transition helper. Small **[WORTH TAKING — authoring/tooling idea]**.
- **Easing curves as authored data** (`harmony/animcurves/curve_titlecard*`, `ease_util.gml`'s 30
  functions) map to precomputed 64-128 byte tables sampled by frame index — exactly arch §7.4's
  "effect sequencer". The concrete lesson is **one channel per moving element, each with its own
  duration**, which is how the stagger is authored rather than hand-tuned. Small
  **[WORTH TAKING — authoring/tooling idea]**.
- **Counter-scrolling title-card ribbon** (`obj_titlecard/Draw_0.gml:70-73`: one column down at
  `t`, an 8 px strip up at `t/2`) is per-line HScroll on the title-card rows — machinery we
  already have and which is otherwise idle during a title card.
  **[WORTH TAKING — VDP-feasible]**, trivial.

### 17. Integer depth-row LUT projection (the Blue Sphere geometry) — [WORTH TAKING — VDP-feasible]

**Harmony:** `obj_bss_controller/Draw_0.gml:52-105`; tables at `stage_bss_engine.gml:165-193`,
annotated `// copied verbatim from Mania's BSS_Setup.h` (`:162`) and therefore transitively the
S3K ROM's own.

**Genesis equivalent:** it already *is* the Genesis shape — four LUTs indexed by an integer depth
row 0..111, an 8.8 sin/cos table, and shift-based scaling. Nothing needs redesigning. Two places
we could beat the original:
- the one `DIVU` per cell (`worldX*worldX div divisorTable[dep]`) becomes a `MULU` by storing the
  **reciprocal** in the table (`DIVU.W` ~140 cycles vs `MULU.W` ~70) — the divisor is already
  table-indexed, so this is a build-time change only;
- our `function`/comptime rule (CODING_CONVENTIONS) makes all four tables comptime-generated
  rather than transcribed.

**Constraint to design around (the real limit, not the math):** H40 allows **80 sprites total,
20 sprites per scanline, and 320 sprite pixels per scanline**. A near row of large spheres can
exhaust the per-line pixel budget before it exhausts the sprite count. The 59/81-entry frustum
plus depth culling is what keeps it inside those caps — treat the frustum list as a *budget*, not
just a visibility set.

**Ours today:** `GS_SPECIAL` is a declared game state (arch §9.13, ID 6) with no implementation.

**Verdict: [WORTH TAKING — VDP-feasible].** This is a ready-made blueprint if a Blue-Sphere-style
special stage is ever wanted, and its LUT-per-depth-row structure generalises to any pseudo-3D
floor.

### 18. Floor motion entirely by palette cycling on a static plane — [ALREADY HAVE as a listed technique; unimplemented]

**Harmony:** the fossil evidence — `palette_page` / `palette_line` (2 x 16 = 32 states) surviving
as the flipbook index (`obj_bss_controller/Draw_0.gml:21`, `Step_0.gml:197`), and
`Draw_0.gml:78` offsetting the sphere depth row by `palette_line`.

**Genesis equivalent:** this **is** the hardware technique — a static warped-checkerboard plane
whose entire apparent forward motion is CRAM cycling, at essentially zero CPU and zero DMA
(16 CRAM words per step). Arch §7.9 already lists it ("Palette Cycling Animation Trick, from
Jon Burton / Sonic 3D Blast"); this is independent confirmation that S3K used it at full-screen
scale for the special stage.

**Ours today:** listed in arch §7.9, and `sec_pal_cycle` (`engine/structs.emp:68`) exists with no
runtime consumer. Folds naturally into candidate #6's palette-variant mechanism.

**Verdict: [ALREADY HAVE — as a technique]**; worth recording the S3K precedent and the
"projected sprites must share the cycle phase counter" consequence, which is the non-obvious part.

### 19. Mirrored animation frames — half the art for free — [WORTH TAKING — authoring/tooling idea]

**Harmony:** `stage_bss_engine.gml:195-197` — a 15-frame turn animation stored as **8 unique
images plus a per-frame horizontal-flip flag** (`globeFrameTable` ramps 0→7→0 while
`globeDirTableL` inverts at the midpoint). Clearly a ROM-budget trick carried over from the
original.

**Genesis equivalent:** *cheaper than in GameMaker* — horizontal and vertical flip are bits in the
nametable word and in the sprite attribute word, so a mirrored frame costs **zero** extra VRAM,
zero DMA, and zero cycles.

**Ours today:** level-art tile dedupe already canonicalises H/V flips
(`tools/ojz_strip_gen.py:387` via `tile_dedupe.remap_nametable_word(word, slot, flip_bits)`), so
this is **[ALREADY HAVE]** for level art. It is *not* expressed at the **animation/mappings**
level: there is no way to author "frames 9-15 are frames 7-1 mirrored". That is a mappings-format
+ animation-script idea, and it halves the art for any symmetric animation (turns, wobbles,
pendulums, ping-pong cycles).

**Verdict: [WORTH TAKING — authoring/tooling idea]**, scoped to the animation/mappings layer.

### 20. Back-to-front authored draw list = free depth sort — [WORTH TAKING — authoring/tooling idea]

**Harmony:** `frustum1X/Y` (59 entries) and `frustum2X/Y` (81) are **hand-authored offset lists,
pre-ordered back-to-front**, so painter's-algorithm depth ordering needs no sort at runtime.
`stage_bss_engine.gml:1012-1013` records that Mania authored them as tile layers and baked them
to offsets.

**Genesis equivalent:** sprite priority is purely **SAT link order**, so emitting objects in a
pre-sorted list order gives correct depth with literally zero sort cost. Applies to any
fixed-camera-relative object set — pseudo-3D floors, isometric scenes, layered boss parts.

**Ours today:** sprite build is `engine/objects/sprites.emp` walking the object list; ordering
comes from slot order, not from an authored depth list.

**Verdict: [WORTH TAKING — authoring/tooling idea]**, low priority (no current consumer), but the
right pattern to remember before anyone writes a runtime sprite sort.

### 21. Pre-rendered full-screen flipbook floor — [REJECT — impossible]

**Harmony:** `spr_bss_globe_roll` = 32 frames of 512x240, plus 2 x 15 turn frames
(`obj_bss_controller/Draw_0.gml:11-23`) — roughly 5.9 MB of raw pixels.

**Genesis:** beyond both cart storage and per-frame DMA bandwidth by orders of magnitude. The
original achieved the same visual with a static plane + palette cycling (candidate #18) and a
nametable/art swap for the turn. **The flipbook is the modern shortcut; the palette cycling is the
technique.** Related: 16 *discrete* pre-drawn sprite scale frames (`stage_bss_engine.gml:455-502`)
are not a stylistic choice — the VDP has no sprite scaling at all, so discrete frames are
mandatory; both S3K and Mania judged 16 steps sufficient, which is a useful budget datum.

**Verdict: [REJECT — impossible]** for the mechanism; the effect survives via #18.

---

## 10. Gaps this exposed on our side (not Harmony's ideas — ours, unbuilt)

Verified by reading the code, not the doc:

- **No fade of any kind.** No palette fade, flash, or cross-fade in `engine/` or `games/sonic4/`.
  Arch §7.1 marks all of it PLANNED and says so explicitly.
- **No title card, no act transition, no signpost sequencing.** Grep for `titlecard|act_trans`
  across `engine/` and `games/` returns nothing.
- **`HBlank_Install` has zero consumers** (`engine/system/hblank.emp:46-67`; it appears only in
  the two `map.toml` export lists). The entire arch §7.2 raster command table — water line,
  nametable splits, S/H toggles, per-scanline gradients — is unbuilt, and `sec_raster_table`
  (`engine/structs.emp:65`) has no reader.
- **`sec_pal` / `sec_pal_cycle` have no runtime consumer** (`engine/structs.emp:63,68`).
- **`Camera_Pan_Offset` is write-only scaffolding** (`engine/level/camera.emp:159-164`) and
  `sec_camera_lookahead` (`engine/structs.emp:76`) has no reader.
- **No screen shake, no look-up/look-down pan, no moving camera limits.**

Harmony is "ahead" on transitions and camera polish only because it built them; nothing there
required a GPU.
