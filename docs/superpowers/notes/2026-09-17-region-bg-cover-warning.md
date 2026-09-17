# REGION-BG-COVER-WARNING, phase 1: required cover, authored cover, and whether "opaque cover" is defined

Parcel `parcel/region-bg-cover-warning`, base aeon `origin/master` `2d206f08`. Booking:
`docs/DEFERRED_WORK.md`, "REGION-BG-COVER-WARNING". Measurement script (re-runnable, committed
beside this note): `docs/superpowers/notes/2026-09-17-region-bg-cover-measure.py`.

**Outcome: BLOCKED on the definition of "opaque cover". Phase 2 was not started.** The rulings fix
WHAT has to be hidden and for HOW LONG, but not what counts as hiding it. Reasonable readings give
different warning sets on OJZ act 1's real crossings, measured below. Options and a recommendation
are at the end.

---

## 1. Required cover, from source

### 1.1 The crossing and the clock

- The crossing is a point test on the camera CENTRE, `Camera_X + CAM_SCREEN_HALF_W`,
  `Camera_Y + CAM_SCREEN_HALF_H` (`engine/level/parallax.emp:1211-1226`). It fires on the first tick
  the centre is inside the new rectangle, so the screen already reaches `CAM_SCREEN_HALF_W` (160) or
  `CAM_SCREEN_HALF_H` (112) px back into the OLD region. `SCREEN_WIDTH` 320, `SCREEN_HEIGHT` 224,
  halves 160 and 112 (`engine/system/constants.emp:538-544`).
- `BG_Stream_Update` runs after `Parallax_Update` in the same tick (`engine/level/bg.emp:610`; call
  sites `games/sonic4/test/ojz_scroll_test.emp:1405/1411` and `:1825/1837`), so the overwrite arms on
  the crossing tick itself.

### 1.2 Overwrite ticks `n`

`BG_Stream_Update` (`engine/level/bg.emp:642-739`):
- the target is the region's `rg_bg_tiles`, or the act's `act_bg_tiles` when null (`:642-647`). So
  LEAVING a tile-owning region is also an overwrite, back to the act's blob;
- length = the blob's 2-byte header, clamped to `BG_TILE_CAPACITY_BYTES` and `andi #$FFFC` (`:673-678`);
- one chunk of at most `BG_OVERWRITE_CHUNK_BYTES` = 1824 (`:583`) is enqueued per tick, and only when
  `DMA_Deferrable_DestPending` finds no arena write still queued (`:686-712`);
- completion is observed on the tick after the last chunk was sent (`:691`, `.ow_complete` `:721`),
  and falls through into the wipe arm on that same tick (`:736`).

So, uncontended, **n = ceil(len / BG_OVERWRITE_CHUNK_BYTES)** ticks from the crossing to
`BG_Tiles_Current` set. Contended (act art page landings on the Important queue during a streaming
fall), n is longer by an amount nothing measures (the cost report's "Contended half: COULD NOT RUN").

### 1.3 Visible repaint

The wipe arms with the cursor at the top VISIBLE plane row (`:869-870`) and walks down,
`BG_WIPE_ROWS_PER_FRAME` = 4 rows a tick (`:530`, `:876`, `:905`), over all `PLANE_V_CELLS` = 64
plane rows. `BG_SCREEN_ROWS` = `SCREEN_HEIGHT / 8 + 1` = 29 (`:514`); `BG_WIPE_FRAMES` = 16 (`:535`).

- **BG window not moving vertically:** the last visible row is sent on tick
  **T_vis = n + ceil(BG_SCREEN_ROWS / BG_WIPE_ROWS_PER_FRAME) - 1 = n + 7**.
- **BG window moving vertically** (the entered region's parallax lets the BG V-scroll move, up to
  `BG_VSCROLL_MAX_STEP` = 2 rows a tick, `parallax.emp:744-745`): T_vis is NOT an upper bound. On a
  descent, rows enter at the bottom faster than the sweep's head reaches them for a while; on an
  ascent, the rows entering at the top are the `BG_STREAM_LEAD_ROWS` = 17 hidden rows above the screen
  (`bg.emp:519`), which the sweep reaches LAST (the order is visible, then below, then above, bg.emp's
  own header ~:455-461), and the streamer paints only the row entering the WINDOW, not the row
  entering the screen (`:915-944`). The only bound valid for any motion is the full sweep:
  **T_sweep = n + BG_WIPE_FRAMES - 1 = n + 15**.

The cost report agrees with both, and its vertical figure is the evidence that T_vis is not enough
on that axis: horizontal measured 10 ticks for the 3-chunk Oil Ocean blob (T_vis = 3 + 7 = 10) and 11
for the 4-chunk colonnade (4 + 7 = 11); VERTICAL measured 11 and 12, one tick past T_vis, and the
sweep retired at 18 and 19 (T_sweep = 18, 19). The report itself called the extra tick "the window
catching up".

### 1.4 Camera caps

- `CAM_MAX_X_STEP` = 16, **file-local** to `engine/level/camera.emp:26` (applied `:287-294`). A tool
  must read it from that file; it is not in `constants.emp`.
- `CAM_MAX_Y_STEP` = 16, `engine/system/constants.emp:1101` (applied `camera.emp:414-420`).
- Other `Camera_X/Y` writers are `Camera_Init` (`camera.emp:153-175`) and the DEBUG boot/warp
  mailbox (`ojz_scroll_test.emp:315-340`), which are teleports that take the synchronous
  `Section_RedrawPlanes` path, not the crossing.

### 1.5 The formula

**required = screen_axis + T x cap_axis**, where screen_axis is 320 (horizontal crossing) or 224
(vertical), measured from the screen's trailing edge at the crossing tick (edge - half screen). T is
T_vis horizontally and, vertically, T_vis if the entered region's BG cannot V-scroll and T_sweep if it
can. The booking's "about one screen plus (overwrite + visible repaint ticks) x cap" is this with T_vis
on both axes. It is short vertically when the BG moves.

For OJZ act 1 (blob headers: act default `bg_tiles.bin` 0x2800 = 10240 B = 6 chunks; showcase
`bg_tiles_showcase_debug.bin` 0x0EC0 = 3776 B = 3 chunks):

| crossing | n | T_vis | T_sweep | required (T_vis) | required (T_sweep) |
|---|---|---|---|---|---|
| horizontal INTO showcase | 3 | 10 | 18 | 480 px | (not used horizontally) |
| horizontal OUT of showcase | 6 | 13 | 21 | 528 px | |
| vertical INTO showcase | 3 | 10 | 18 | 384 px | 512 px |
| vertical OUT of showcase | 6 | 13 | 21 | 432 px | 560 px |

Cross-check against the cost report: its addendum's horizontal "~10 ticks" gives 160 + 320 = 480.
**Agrees.** Its original "496 / 416" is the retired 216-tile blob: T_vis 11, which also agrees. The
report never gives the OUT direction's larger figure (the act's 320-tile blob, 13 ticks), although
it mentions a 320-tile blob would take "about 13" ticks.

---

## 2. Authored cover: what data exists, which crossings, where it would run

### 2.1 What "foreground" is in data

- Plane A per section: `games/sonic4/data/editor/ojz/act1/section_N.tiles.bin`, 256 x 256 big-endian
  VDP nametable words, flat id row x gridWidth + col (`tools/ojz_strip_gen.py:469-487`, `project.json`
  `gridWidth`/`gridHeight`).
- Pixels: `project.json` `zones[0].tileset` = `games/sonic4/data/editor/ojz_tiles.bin`, raw 4bpp,
  32 B/tile (`ojz_strip_gen.py:103-117`). Colour 0 is transparent on a plane.
- Both are committed and donor-free. The generated tree re-indexes the same words into the act pool
  without changing pixels, so the editor tree is the authored truth.
- Priority: bit 15 of each word. See 3.2.
- **Nothing in the data marks "this is cover".** There is no authored cover field and no crossing
  lane. "Authored cover" has to be computed from Plane A pixels.

### 2.2 Which crossings exist

- **Release: none switch tiles.** Every row in `games/sonic4/data/editor/ojz/act1/regions.json` takes the
  act's tiles (the schema has no tiles key; booking REGION-BG-TILES-AUTHORING), so in release the
  overwrite never arms.
- **DEBUG: one tile-owning row**, the showcase (`act_descriptor.emp:752-756`, x 1024..2047,
  y 2048..4095, `rg_bg_tiles: OJZ_Act1_BG_Showcase_Tiles`). Its neighbours are all act-default: sec3
  on the left (edge x = 1024), sec4 on the right (x = 2048), sec0 above (y = 2048), sec6 below
  (y = 4096). That is **8 directed crossings**, and all of them overwrite (in with 3 chunks, out with 6).
- The DEBUG tall row (`OJZ_TALL_BG_ROWS`, `:720`) changes only the layout. That gives a step-6 wipe
  with valid tiles on both sides, with no overwrite and no garbage. I read it as outside this
  booking, whose subject is "old background over partly overwritten tiles".
- A corner entry (both axes at once) is a real case on a 2D patchwork and is not an axis case.

### 2.3 Where the computation would live

- **Not the re-bake.** `tools/regenerate-level.sh:6-15` is manual and needs two out-of-repo donors,
  and "the build never runs these generators". A warning that only fires when someone re-bakes by hand
  would miss every edit that did not go through it.
- **A build lane.** The pure function (blob bytes, axis, BG-can-V-scroll, constants -> required px;
  Plane A pixels + crossing geometry -> authored px) belongs in `tools/` with its unit test in the
  pre-build `pytest tools -m "not needs_build"` lane. The report over real data has a catch: the only
  tile-owning rows are DEBUG-shape comptime deltas in `act_descriptor.emp`, not rows in `regions.json`.
  So the lane either parses that `.emp` (brittle) or runs after sigil and reads `OJZ_Act1_Regions` and
  each `rg_bg_tiles` header out of `s4.debug.bin` + `s4.debug.lst` (the `needs_build` pattern
  `build.sh:1276-1340` already runs). I would pick the latter.

---

## 3. Is "opaque cover" determined? No.

### 3.1 What IS determined

- **What must be hidden, and for how long:** the whole Plane B shows garbage (old words over new
  tiles, then a mid-wipe mix) from the crossing tick to T (§1). The garbage is not confined to a
  band, so hiding it all needs Plane A over the WHOLE screen for every camera position in that span.
  That follows from the mechanism.
- **Pixel, not tile:** the VDP shows Plane B through any colour-0 Plane A pixel. A tile with one
  transparent pixel leaks.

### 3.2 Priority: determined for today's data, not by construction

At equal priority Plane A is drawn over Plane B, so a low-priority FG pixel covers a low-priority BG
pixel. It does NOT cover a HIGH-priority BG pixel. The BG blobs are low priority by the importers'
choice, not by a rule: `ojz_strip_gen.py:434` clears the bit ("BG always low-priority") and
`gen_region_bg_showcase.py:61` clears it, but `inject_editor_bg.py:1051` `rebase_layout` keeps
priority bits. Measured on the committed blobs: `zone_bg.bin` and `zone_bg_showcase_debug.bin` each
hold **0** high-priority words. So today the FG priority bit changes nothing, and a future
high-priority BG word would make low-priority FG stop counting as cover over it.

### 3.3 What the rulings and the booking leave open

- **R3** (spec §2): *"That's on the artist/level designer to just cover up"*, *"either way we'll cover
  it with fg most likely"*, "The engine doesn't enforce it". No extent and no threshold.
- **R5**: warn, don't refuse. Shape only.
- **Review 07 finding 3**: "~720 px of fully opaque Plane A on the new side of every boundary". This is a
  1D length on the entry axis. It says nothing about the perpendicular, and it says "new side" where
  the screen also covers 160 px of the old side.
- **The booking**: "the opaque-foreground extent per crossing", again a 1D length.
- **Plan row 3** (`2026-09-16-region-bg-switch.md:79`): "needs the opaque-FG extent per crossing".

Left open:
1. **Perpendicular extent.** A crossing is an edge up to 2048 px long, and the camera centre can cross
   anywhere along it. Is cover judged at the WORST reachable position (the whole edge must be walled
   off), at the BEST one (some lane exists), or only on the path the player can actually take? The
   last needs collision reachability, which no tool computes.
2. **Whole screen, or a line.** The mechanism says whole screen (3.1). The rulings' "extent" and the
   review's "720 px" read naturally as a length along a corridor, which a designer checks on the path
   line.
3. **Partial cover.** "Cover it with fg most likely" does not say whether 90% opaque with gaps is
   cover. Foliage-style art is rarely 100% opaque.
4. **Vertical T.** T_vis or T_sweep (§1.3). This is engine-side and I would decide it myself
   (T_sweep when the entered region's BG can V-scroll), but it moves the vertical requirement by 128 px.
5. **Corner entries**, and camera drift on the other axis during T (a diagonal fall).

### 3.4 Measured: what each reading warns on for OJZ act 1 today

Script output, DEBUG showcase crossings (required uses T_vis; the vertical T_sweep figure changes no
verdict below). "Worst" = min over every reachable camera centre along the edge (8 px steps, clipped
to the camera-centre band); "best" = max.

| reading | sec3->show x1024 | show->sec3 x1024 | show->sec4 x2048 | sec4->show x2048 | sec0->show y2048 | show->sec0 y2048 | show->sec6 y4096 | sec6->show y4096 |
|---|---|---|---|---|---|---|---|---|
| required (px) | 480 | 528 | 528 | 480 | 384 (512) | 432 (560) | 432 (560) | 384 (512) |
| A pixel, whole screen: worst / best authored | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 111 | 0 / 0 | 0 / 0 |
| B tile fully opaque, whole screen | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 111 | 0 / 0 | 0 / 0 |
| C tile any-pixel, whole screen | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 111 | 0 / 0 | 0 / 0 |
| D pixel, centre line: worst / best | 0 / **672** | 0 / **1183** | 0 / 160 | 0 / 287 | 0 / 0 | 111 / 111 | 0 / 0 | 0 / 0 |
| E tile any-pixel, centre line | 0 / **672** | 0 / **1183** | 0 / 160 | 0 / 287 | 0 / 0 | 111 / 111 | 0 / 0 | 0 / 0 |
| F opaque fraction of the swept screen: min / max | 0% / 57% | 0% / 54% | 0% / 54% | 0% / 38% | 21% / 38% | 14% / 26% | 13% / 13% | 0% / 0% |

What each reading WARNS ON:

| reading | warns on |
|---|---|
| A, B or C (whole screen), worst OR best | **all 8** |
| D or E (centre line), worst | all 8 |
| D or E (centre line), best ("a lane exists") | **6**: every crossing except sec3 <-> showcase at x = 1024 (672 and 1183 px of opaque centre line clear 480 and 528) |
| F at >= 50% opaque, best | **5**: every crossing except sec3 <-> showcase and showcase -> sec4 (31, 15 and 14 centres reach 50%) |
| F at >= 75% or >= 90%, either | all 8 |

So the readings disagree on real crossings: x = 1024 both ways, and showcase -> sec4. Today the
disagreement is confined to how lenient the reading is. Whole-screen readings warn everywhere,
because the showcase was placed for gate geometry, not behind authored cover.

**Unmeasured, and would move numbers:** Plane A per-line H-scroll raster (sec5 and sec6 bind raster
programs, and a line-scrolled Plane A does not sit where its nametable does), and sprites or HUD,
which are not authored static cover.

---

## 4. Options, and my recommendation

| option | definition | OJZ act 1 today | cost / risk |
|---|---|---|---|
| **1. Strict** | pixel-exact, whole screen, worst reachable centre along the edge, T_sweep vertically when the BG can V-scroll | warns on all 8 | Faithful to the mechanism: it warns exactly when garbage can be seen. In practice it demands a wall of opaque FG along the whole boundary, which most levels will never author, so it may warn on every crossing forever and get ignored |
| **2. Lane** | pixel-exact, whole screen, but only at camera centres the author marks as the crossing lane (a new authored input, e.g. a `coverLane` span on the region edge in regions.json) | cannot be evaluated: no lane data exists. With the lane = the full edge it equals option 1 (8) | Needs a schema key, which is cross-repo (empyrean contract + Aurora), like REGION-BG-TILES-AUTHORING |
| **3. Centre line, best** | the booking's 1D "extent" on the centre line, some position along the edge | warns on 6 | Matches the booking's words. Silent while most of the screen shows garbage: a 1-px opaque line counts |
| **4. Threshold** | opaque fraction of the swept screen >= X% | X = 50: warns on 5; X = 75 or 90: all 8 | X is a look call and the owner's |

**Recommendation: option 1 as the build warning's definition, reported with option 4's fraction as
context in the message** (for example "authored 0 px fully opaque; best lane 57% opaque"). R5 asks to be
TOLD, and a warning that is honest about what can be seen is worth more than one that stays quiet
while garbage shows. If the owner rules that a partly covered crossing is acceptable, that is option 4
with his X. Option 2 is the right end state once Aurora can author a lane, and Aurora computes cover
too, so it would read the same field.

**The owner's call is the definition itself (1, 3 or 4, and X for 4).** The vertical T choice (§1.3)
and the priority caveat (§3.2) are engine-side, and I would settle them as stated above without
asking.

## 5. What phase 2 would build once the definition is ruled

- `tools/region_bg_cover.py`: `required_cover_px(blob_bytes, axis, bg_v_scrolls, consts)` and
  `authored_cover_px(plane_a_opaque, crossing, consts)` as pure functions, with every constant read from
  `constants.emp`, `camera.emp` (the file-local `CAM_MAX_X_STEP`) and `bg.emp`. The measurement script
  here is the prototype of the second function.
- A unit test in the pre-build pytest lane with fixture crossings one pixel short (warns) and one
  pixel long (quiet), both boundaries derived from the constants.
- A post-sigil `needs_build` report over `s4.debug.bin`'s region table that prints WARNING lines and
  exits 0.
