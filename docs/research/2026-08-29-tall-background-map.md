# Background art taller than the plane — scope and price (d-31, option 3)

*2026-08-29. Design only. No build was run (the controller was relinking the shared sigil
binary); no emulator was used. Everything below is read from source, data files, generated
artifacts and reference trees at the revisions cited.*

**The owner's question, verbatim:** *"d-31 not level height, background art height is what I'm
talking about. like the background art for sky sanctuary zone is supposed to be 2.6k pixels or
something right? I had use investigate recently"*

He is asking for background ART taller than the 512-px plane — d-31's option 3. Options 1/2 of
`d-31-refiled` cope *inside* 512 px and are not what he asked for.

---

## 0. The answer in five lines

1. **His memory is right.** Sky Sanctuary 1's background is **2,816 px tall as authored**, of which
   **~2,530 px is scrolled through in one continuous run** — his "2.6k" lands on the second almost
   exactly. Re-derived three ways in §7.
2. **It is a genuinely tall streamed map, not a scroll trick, and SSZ does not even use a band
   table** — it calls plain `DrawBGAsYouMove`, the simple mechanism §8 recommends. The reframe
   that matters: **S3K's planes are 512x256, not 512x512.** S3K got 2,816 px of background out of
   a 256-px resident window. **Our plane already holds twice S3K's entire window** — and OJZ needs
   740 px, not 2,816, because our background runs at 1/8 where SSZ's runs at 1:1.
3. **The engine cost is small and mostly already built.** One new producer, one scheduler,
   **4 bytes of RAM, no new VRAM**, and ~33 bytes/frame of DMA — because the background crosses
   tile rows `2^v_factor` times more slowly than the foreground (8x at OJZ's factor 3).
4. **It does NOT dissolve the 448-tile ceiling. It makes it bite 45% harder.** 448 is a VRAM
   address-space limit, not a consequence of the once-blit design. Streaming the nametable
   allocates zero new tiles; it only spreads the same tiles over more area.
5. **The real cost is art, not code**: a 512x744 background drawn from the same 320 unique tiles.

---

## 1. Verification of the inputs this design was handed

### 1a. The aurora survey says what it was reported to say — confirmed

`aurora docs/reviews/2026-08-26-bg-capability-survey-s1-s2-s3k.md`, read via
`git show origin/master:…` at aurora **`93f78707b32864cf3f78adbea5cc4a9669f2fc3f`**; the file's
own last-touching commit is **`1611834f1da7021f9ac43141920ccedfb8d1e857`**. Both verified
**reachable at aurora `origin/master`** (`git merge-base --is-ancestor`), remote
`git@github.com:Volence/aurora.git`. Not local-only.

- **Row 19 exists** and reads *"BG plane redrawn per band from separate BG cameras (art wider/
  taller than one plane)"*, verdict **NO**, smallest fix **Engine L**, and names
  `bg.emp` / the zero-caller `Draw_BG_TileColumn` / the booked seam-streaming spec as the reason.
- **Summary point (2) exists** and states aeon blits Plane B once at load and never redraws it,
  that every background layer must therefore tile at 512 px, that the whole act's background
  lives in **448 tiles**, and that *"the seam-streaming spec that would fix (2) and (3) is
  already booked in aeon"*.

All four claims relayed by the hub are accurate. **One drift, in aurora's favour to know about:**
the survey's row 4 says the layer cap is 8 and calls raising it to 16 "a RAM + cycle question".
That landed the next day — `MAX_PARALLAX_BANDS = 16` since 2026-08-27
(`engine/system/constants.emp`, and `docs/DEFERRED_WORK.md` carries the closure). The survey is
three days stale on that one row only.

### 1b. CORRECTION TO THE BRIEF — the 448 ceiling is aurora **d-1**, not d-2

The brief asks whether this dissolves *"the 448-tile ceiling that stopped aurora's band editor
(their d-2)"*. **Aurora d-2 is not that decision.** Read at aurora `origin/master`
`docs/decisions.jsonl`:

- **d-2** (2026-08-24) is a *push-authorization* question — whether the lane may publish its own
  repo's work without asking. Superseded by **d-4**.
- **d-1** (2026-08-24) is the 448 card: *"The background picture in Oil Ocean fills the console's
  background picture memory completely, right up to a hardware wall, so the parallax editor
  cannot add a single new moving band to it."*

d-1's own detail is the best statement of the limit anywhere in the suite, and it is a
measurement:

> `aeon games/sonic4/data/editor_bg_override.json` is at 448/448 tiles. tileSlotsRemaining 0,
> bandsRemaining 4. **448 = (0xB800-0x8000)/32 exactly; the SAT at $B800 is the wall, tile 449
> sprays into it.** Measured against aeon pin `e087af9c`: 448 distinct bitmaps, 0 flip-redundant
> pairs over orig/H/V/HV, 0 uniform-colour, no H- or V-symmetric tiles, so dedup/blank/flip
> reclaim are all exhausted.

**And that stranding was already lifted, by a different mechanism than streaming:** aurora
**d-9/d-10** (2026-08-26) ruled the shipped background be regenerated from an auto-simplified
source. The shipped `editor_bg_override.json` today reads **layout 4096 cells / tiles 320 /
anims 1** — 320 static, 128 reserved for bands. So d-1 is closed by art simplification, not by
any engine feature. §5b says what this means for the question actually asked.

### 1c. The booked spec exists, is three weeks old, and is still accurate

`docs/research/2026-08-08-bg-seam-streaming.md` (253 lines), authored `e324d48d` 2026-08-08,
with a `000bb44e` addendum on 2026-08-26. Booked from `docs/DEFERRED_WORK.md`
§"SPEC: Per-section background grid with seam streaming".

It has **not** rotted, and it corrects itself where it did: its §1 opens by falsifying four
assumptions of the older DEFERRED_WORK sketch (layouts are 64x64/8192 B not 64x32; the transport
is `Plane_Buffer` not `QueueDMA_Deferrable`; there is no single *horizontal* BG camera; the tile
ceiling is 448 not 512). I re-checked all four against today's source and all four still hold.
Its §4 build order already names the work the owner is asking for as **step (2), "vertical seam
streaming"**, and its own §3 notes that the vertical BG camera Pattern A needs *already exists*.

**But note what it was booked FOR.** The spec is about **per-section background themes** — the
owner's "forest above, darker firefly below" — and vertical streaming is step 2 of 5 on the way
there. The owner is not asking for themes. He is asking for one tall picture. That is a strict
subset, and §6 recommends taking only the subset.

---

## 2. Geometry, re-derived

| quantity | value | authority |
|---|---|---|
| Plane geometry | `PLANE_H_CELLS = PLANE_V_CELLS = 64` -> **512 x 512 px** | `engine/system/constants.emp` |
| Screen | 320 x 224 | `SCREEN_WIDTH` / `SCREEN_HEIGHT`, same file |
| OJZ act 1 extent | `GRID_W 3`, `GRID_H 3`, `SECTION_SIZE_SHIFT 11` -> **6,144 x 6,144 px** | `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` (its own `ensure` binds `SCENE_ACT_SPAN_Y == GRID_H << SECTION_SIZE_SHIFT`) |
| BG vertical map | `Vscroll_BG = ((camY - v_center) >> v_factor) + v_offset` | `Parallax_Step5_Vscroll`, `engine/level/parallax.emp` |
| OJZ scenes | **20 total; 18 locked at `v_factor 15`; 2** (`OJZ_Depth`, `OJZ_Underwater`) **at `v_factor 3`, `v_center 512`, `v_offset 0`** | `games/sonic4/data/effects/ojz_scenes.emp` |
| BG tile region | tiles **1024-1471 = 448**, `band_reserve 128`, static budget **320** | `docs/generated/vram-map-sonic4.md` (generated from `games/sonic4/vram.toml`) |
| Free VRAM, whole map | **14 tiles across 4 runs** | same |

**The deficit, derived not copied:**

```
camera Y travel   = 6144 - 224            = 5,920 px
required BG span  = 5920 >> 3             =   740 px      (v_factor 3)
plane span                                =   512 px
                                            ---------
deficit                                     =   228 px    (map must be 1.45x the plane)

max act height at v_factor 3 = 512 << 3   = 4,096 px  -> OJZ is 2,048 px past it
max act height at v_factor 4 = 512 << 4   = 8,192 px  -> OJZ fits, with 142 px spare
                                                         (this is the `slower` ruling he reopened)
```

This matches `docs/DEFERRED_WORK.md` §"The 512-px background has a HEIGHT x DEPTH budget"
independently. Only the two unlocked scenes are affected; the eighteen `v_factor 15` scenes are
exempt by construction and any guard must not fire on them.

---

## 3. Cost 1 — ENGINE

### 3a. What already exists (this is most of it)

- **The drain is already generic.** `VInt_DrawLevel` (`engine/level/plane_buffer.emp`) dispatches
  on bit 15 of the entry header: clear = row mode, autoinc `$02`, longword drain, to an
  *arbitrary* VRAM address. **A Plane-B row entry needs zero drain changes.**
- **The loop shape exists.** `Section_UpdateColumns`' bottom/top row fill (`engine/level/
  section.emp`) is the exact template: an edge tracker pair
  (`Section_Top_Row_Written` / `Section_Bottom_Row_Written`, `engine/ram.emp`), a
  `world_row & 63` nametable map, a `PLANE_BUFFER_SIZE - 2 - (4 + PLANE_H_CELLS*2)` admission
  test, and a wrap clamp at +/-63.
- **A BG producer exists but is the wrong axis.** `Draw_BG_TileColumn` — I confirmed by grep
  across every `.emp`/`.asm`/`.toml` in the tree that it still has **zero callers** (only
  self-references in `bg.emp`'s comments). It is a *column* producer. The tall case needs rows.
- **The vertical BG camera already exists**: `Parallax_Current_Vscroll_BG`, one whole-plane value,
  wrapping mod 512. The booked spec says this and it is still true.

### 3b. The VSRAM math does not change at all

Worth stating because it is the property that makes this cheap. With streaming, plane row for
world BG row `R` is `R & 63`, so world row `R` lands at plane line `(R & 63) * 8`. A VSRAM scroll
of `S` puts screen line 0 at plane line `S & 511`. Both are already mod-512. So
`Parallax_Step5_Vscroll` is **untouched**, and so is every band-rotation consumer downstream of
`Parallax_Current_Vscroll_BG`. The feature is purely additive on the plane-content side.

### 3c. New code, RAM, VRAM

| item | size |
|---|---|
| `Draw_BG_TileRow` producer (sibling of `Draw_BG_TileColumn`) | ~150-200 B ROM |
| BG row-edge scheduler (mirror of the FG top/bottom fill) | ~120-150 B ROM |
| `BG_Top_Row_Written`, `BG_Bottom_Row_Written` | **4 bytes RAM** |
| per-act BG map height (Act descriptor field + blob type) | 2 B ROM/act |
| **new VRAM** | **zero** |

The 4 RAM bytes land at the engine RAM tail and ripple only `Engine_RAM_End` plus the game RAM
chained after it — `engine/ram.emp`'s own notes call that "a full game-side repin, routine".

### 3d. DMA and cycles — priced against the foreground, honestly

One Plane-B row entry = 4 B header + 64 cells x 2 B = **132 bytes**.

**Crossing rate.** `CAM_MAX_Y_STEP = 16` px/frame. At `v_factor 3` the BG scroll moves at most
2 px/frame, so it crosses an 8-px row boundary **at most once per 4 frames**. The foreground
fills up to `VFILL_ROWS_PER_FRAME = 2` rows/frame. So:

| | FG vertical | BG @ v_factor 3 | BG @ v_factor 4 |
|---|---|---|---|
| rows/frame, worst case | 2 | 0.25 | 0.125 |
| bytes/frame, peak | 264 | 132 (1 frame in 4) | 132 (1 frame in 8) |
| bytes/frame, amortized | 264 | **33** | **16.5** |
| % of `DMA_BUDGET_NTSC` (6144), amortized | 4.3% | **0.54%** | 0.27% |

**So yes — meaningfully smaller than the foreground's, by exactly `2^v_factor`: 8x at factor 3,
16x at factor 4.** This is the reference pattern's own prediction: the seam doc's §2 Pattern A
notes that in S.C.E./sonic_hack/SGDK "no ratio arithmetic exists in the drawer — fractional rates
just cross boundaries less often". It falls out for free here too.

Peak-frame headroom is fine: `PLANE_BUFFER_SIZE = 1536` with a documented "worst realistic frame
~800 B", so +132 B leaves ~604 B spare, and the producer's own admission test refuses rather than
overruns.

**Cycles, and a byte-order finding.** The shipped BG blob is **column-major**, stride 128
(`bg.emp` header). A *row's* 64 cells are therefore strided by 128 B, not contiguous:

- sequential (row-major source): 32 x `move.l (a1)+,(a2)+` ≈ **960 cycles**
- strided (column-major source): 64 x (`move.w (a1),(a2)+` + `adda.w #stride,a1` + `dbf`)
  ≈ **1,920 cycles**

An NTSC frame is ~127,840 cycles (7.67 MHz / 60 Hz), so even the strided gather is 1.5% of one
frame, once per four frames — **0.38% amortized**. Both are affordable.

**But the shipped byte order is optimised for the producer that has zero callers, and is pessimal
for the one this feature needs.** Recommend storing the tall blob **row-major**, because it is
strictly a simplification in three places at once:

1. the row gather becomes the 960-cycle sequential run;
2. `BG_Init`'s initial blit drops its `$8F80` autoincrement excursion *and* the `IPL >= 6` assert
   that exists only to make that excursion atomic against `Flush_VDP_Shadow`;
3. `tools/inject_editor_bg.py` currently *transposes* row-major editor data into column-major
   engine order — so the change is a **deletion**, not an addition.

`Draw_BG_TileColumn` (zero callers) inherits the stride, and horizontal streaming is out of scope
anyway (§6).

### 3e. What breaks — five things, one of them sharp

1. **`Section_RedrawPlanes` asserts the invariant this removes.** Its Plane-B pass is commented
   *"BG layout is act-wide, not position-dependent"* and blits rows 0..63 from the head of the
   blob. With a tall map it must blit the *current window* at the BG camera's offset. ~10
   instructions. Same for `BG_Init`.
2. **SHARP — teleports stop being free.** `bg.emp` records that teleports no longer redraw Plane B
   because they are pure coordinate rebases and would write byte-identical content
   (`docs/research/teleport-rebase.md`). That holds *only because the BG is position-independent*.
   With a tall map, a vertical teleport lands on different BG content. At `v_factor 3` a `$1000`
   (4,096 px) shift is 512 px of BG — exactly one plane wrap, so the **scroll** stays invariant
   while the **content** does not. Needs either a windowed repaint (8 KB, i.e. the existing 3-4
   frame `Section_RedrawPlanes` storm) or a build guard that teleport shifts are whole multiples
   of the BG map height. **This is the one item that could turn a parcel into two.**
3. **`BG_LAYOUT_SIZE` is a `pub` contract**, and `act_assets.emp` types its embed
   `[u8; BG_LAYOUT_SIZE]` precisely so a wrong-sized blob is a build error rather than a
   transposed background at runtime. It becomes per-act. The build-time catch must survive the
   change, not be traded away for flexibility.
4. **`Draw_BG_TileColumn`'s `lsl.w #7, d3`** (col * 128) hard-codes a 64-row map.
5. **The guard d-31 asks for changes shape rather than being written as specified.** Its proposed
   `ensure(... >> v_factor_bg <= PLANE_B_SPAN)` becomes `<= bg_map_span`. Note `PLANE_B_SPAN` is a
   name in that card, **not a constant that exists** in `constants.emp` today.

### 3f. One thing that is much better than the foreground's, and is worth banking

The plane holds 64 rows; the view is 28. So **36 rows = 288 px of the plane are always hidden**,
which at `v_factor 3` is `288 * 8 = 2,304 camera px` — about 144 frames at the camera cap — of
catch-up slack before a stale row could re-enter view. The **foreground has exactly zero**:
`constants.emp` binds `CAM_MAX_Y_STEP <= VFILL_ROWS_PER_FRAME * 8` at *equality* (16 == 2*8) and
its own comment says "zero catch-up headroom". The BG streamer is the comfortable one.

---

## 4. Cost 2 — AUTHORING (aurora side)

### What exists today

`tools/png_to_bg_override.py` converts a PNG to `games/sonic4/data/editor_bg_override.json`.
Its hard gates are *"image tile-aligned (8x8); width divides the 512px plane; unique
flip-canonical tiles <= BG_STATIC_TILE_BUDGET"*, with `PLANE_W = 64` and `PLANE_H = 64`. The
shipped override reads exactly **layout 4096 / tiles 320 / anims 1**.

### What changes

**The background stops being a picture and becomes a strip.** Concretely:

| surface | today | tall |
|---|---|---|
| source PNG | 512 x 512 | **512 x 744** (OJZ at factor 3) |
| `PLANE_H` in the importer | fixed 64 | per-act `MAP_H` (93 rows) |
| `layout` array | 4,096 cells | **5,952 cells** (~1.45x the JSON) |
| ROM per act | 8,192 B | **11,904 B** (+3,712 B, uncompressed) |
| band `y` coordinates | plane space, 0..511 | **map space, 0..MAP_H*8** |

**The two aurora-side items that are not just "a bigger number":**

1. **The map canvas and band editor draw the background as one 512x512 picture behind the
   level.** It becomes a strip with a vertical viewport, and band tops stop being plane-space
   (the survey's row 3 notes band tops are plane LINES 0..511 today, and `scene_dsl`'s guard
   binds a layer span to 512). A band can now sit outside the plane window.
2. **The live camera preview currently models Plane B as static content plus a scroll offset.**
   That model is exactly what this feature invalidates. If the preview is not taught the moving
   window, it will diverge from the ROM precisely where the new feature lives — i.e. it will look
   correct while being wrong, which is the failure mode this suite has recorded most often.

**Cross-lane: yes.** aeon engine + aeon importer + aurora canvas/band-editor/preview + the
empyrean schema doc. **Recommend the hub declare it as a project**; it is not a single-repo
parcel. The engine half alone is.

---

## 5. Cost 3 — ANIMATED BANDS and the ACT ART POOL

### 5a. Bands: the mechanism survives, the budget does not

**Mechanism — compatible.** BgAnim bands animate *tile art* in fixed VRAM slot ranges
(`vram_dest`), by rotating columns of tiles; the streamer rewrites *nametable cells*. They do not
touch each other. As the map scrolls, cells referencing band tiles travel with the art — which is
the behaviour you want. `BGANIM_MAX_BANDS = 4` (`engine/level/bg_anim.emp`, held build-fatally in
three directions by `tools/test_bg_emit.py::TestBgAnimBandCeiling`) is unaffected.

**Budget — this is the collision, and it is arithmetic:**

```
today:  320 static tiles cover 64 x 64 = 4,096 cells  -> 12.8 cells per unique tile
tall:   320 static tiles cover 64 x 93 = 5,952 cells  -> 18.6 cells per unique tile
                                                          +45% required repetition
to hold today's density over 740 px you would need 465 static tiles
   ... which exceeds the entire 448-tile region, let alone the 320-tile budget.
```

So a tall background **must** be authored with ~45% more repetition, or it eats into the 128-tile
`band_reserve` — which would re-strand the band editor, i.e. undo exactly what aurora d-9/d-10
achieved on 2026-08-26. **That is the real price of this feature and it is paid in art, not code.**

### 5b. Act art pool: no VRAM collision, two small time collisions

**No VRAM collision.** `fg_art_pool` is tiles 0-895; `bg_region` is 1024-1471. Separate arenas.
But there is also **no room to grow**: the generated VRAM map reports **14 free tiles across 4
runs** in the whole 2,048-tile space. Enlarging the BG region means taking tiles from the FG pool,
and `POOL_TILE_CEILING = 896` is not a free knob — its own comment records that it sizes
`PAGE_FRAMES` and two RAM arrays.

**Two time collisions, both small, both TAGs rather than blockers:**

- The plane-buffer drain and the art-pool page-ins share `DMA_Budget_Remaining` (6144 NTSC).
  +132 B on one frame in four, against `act_art_budget` 4096 B/frame of page-ins and
  `DMA_ENQ_BYTE_CAP` 12288.
- The ~960-1,920 cycle row gather competes with the resumable ZX0 page decoder's idle-time slices
  (ARCH §9.7). 0.4-1.5% of a frame, on 25% of frames.

---

## 6. What it buys — and the 448 verdict

### 6a. SSZ-class backgrounds: yes, and it is the only thing that gets them

It removes the `512 << v_factor` height x depth budget entirely, decoupling act height from
parallax depth. OJZ act 1 could keep `v_factor 3` — visible vertical depth — at its full 6,144 px,
instead of being pushed to `v_factor 4` where the background moves half as much. That trade is
exactly what the owner reopened d-31 to avoid.

### 6b. The 448-tile ceiling: **NO. Independent limit, and streaming makes it worse.**

This is the question with two very different answers, and the answer is the unwelcome one.

**448 is VRAM address space.** `BG_TILE_REGION_BYTES = VRAM_SPRITE_TABLE - BG_TILE_BASE_VRAM`
= `$B800 - $8000` = `$3800` = 14,336 B = 448 tiles (`engine/level/bg.emp`). Aurora measured the
same wall independently in d-1: *"448 = (0xB800-0x8000)/32 exactly; the SAT at $B800 is the wall,
tile 449 sprays into it"*, with dedup, blank-tile and flip reclaim all proven exhausted.

**Nametable streaming allocates zero new tiles.** It changes which *cells* you can reach, not how
many distinct *bitmaps* are resident. Per §5a it increases the area those 448 (really 320) tiles
must cover by `map_span / 512` — **1.45x for OJZ**. A tall background is strictly *harder* to fit
under 448 than a short one.

The thing that *would* dissolve 448 is **BG tile paging** — the act art pool's own mechanism
(64-tile frames, a page table, ZX0 pages decoded across idle time) applied to the BG region. That
is a different and much larger project, and it is not what the seam-streaming spec describes; the
spec's §4.3 proposes *halving* the 448 into two ~224 pools for theme crossfades, which makes the
per-theme ceiling lower still.

**And the band editor is already unstranded anyway**, by art simplification under aurora d-9/d-10
(320/320 static, 128 reserved). Nothing about this feature is needed to keep it that way — but
this feature does put pressure back on exactly that reserve.

---

## 7. S3K's Sky Sanctuary background, in pixels — and the reframe

**SSZ act 1's background is 2,816 px tall as authored, and ~2,530 px of it is scrolled through in
one continuous run.** The owner's "2.6k or something" is right, and lands almost exactly on the
second figure.

**Derivation, done three times.** `docs/research/2026-08-08-bg-seam-streaming.md`'s 2026-08-26
addendum (aeon `000bb44e`) parsed every `skdisasm/Levels/*/Layout/*.bin` header — words are FG
width, BG width, FG height, BG height, in 128-px chunks. I re-derived SSZ from the raw bytes, and
a second lane re-derived it from the format authority, at skdisasm
`2fcd861c208f342b6d14df694c6422c74f20a4be` (**verified an ancestor of `origin/master`**, remote
`git@github.com:sonicretro/skdisasm.git`):

- `skdisasm/Levels/SSZ/Layout/1.bin` opens `0036 003c 0020 0016` = FG 54 x 32, **BG 60 x 22**
  chunks; **22 x 128 px = 2,816 px**.
- The word order is confirmed by the file size closing exactly:
  `8 (header) + 128 (64 row pointers) + 32*54 (FG) + 22*60 (BG) = 3,184` = the bytes on disk.
- The 128-px chunk is measured, not assumed: `Get_LevelChunkColumn` does `lsl.w #7` on the chunk
  id and `asr.w #7` on X.
- Format authority: `Level_layout_header` / `Level_layout_main` in `sonic3k.constants.asm`.

**The mechanism is plain vertical streaming, and SSZ does NOT use a band table.** Grepping
`BGDrawArray` in `sonic3k.asm` yields seven acts and **`SSZ` is not among them** — the label at
the line the aurora survey cites is `SSZ1_BGDeformArray`, a *horizontal* per-line HScroll deform
array consumed by `ApplyDeformation`, which adds no height. SSZ1 instead calls plain
`DrawBGAsYouMove` every frame, which runs `Draw_TileColumn`/`Draw_TileRow` off
`Camera_{X,Y}_pos_BG_copy` and pushes a fresh 16-px row into plane B on each boundary crossing.
That is exactly the mechanism recommended in §8 — the simple one, not the band-table one.

**And the reason SSZ needed 2,816 px is the number that makes our ask small:** in its main castle
mode SSZ1's background runs at **1:1 with the foreground** (`BG_Y = FG_Y + $160`, no parallax
division at all — which is why `sonic3k.constants.asm` documents `Camera_Y_diff` as "used for
background collision in SSZ"). At 1:1, BG span *is* act span. Required map height scales as
`travel >> v_factor`, so **OJZ at `v_factor 3` needs 740 px — about a quarter of SSZ's — out of a
plane twice the size of SSZ's.**

**Caveat on the runner-up, worth knowing before anyone cites it:** LRZ1's 2,560 px is **not** one
tall image. `LRZ1_Deform` runs the BG at 1/8, and `sub_56DAC` jumps the BG camera to a wholly
different part of the map by player region — it is an *atlas* of separate background pictures.
**SSZ1 is the genuine article** among regular acts. (Only `Levels/Pachinko` is taller, at 4,096,
and it is a bonus stage.) S3K's own hard ceiling on any layout is 4,096 px — 32 rows, from
`Layout_row_index_mask = $7C`.

The addendum's full playable-act table, for scale: 256 px — ALZ, CGZ, DPZ, EMZ, DEZ1/2, MGZ1;
384 — BPZ, DDZ, LBZ1; 512 — DEZ3, LRZ2, LRZ3; 640 — CNZ2; 768 — ICZ2, MHZ1/2/3, HPZ; 896 — MGZ2,
SOZ1; 1024 — HCZ1, HCZ2, ICZ1; 1152 — CNZ1; 1280 — AIZ2; 1408 — AIZ1; 1536 — FBZ1, FBZ2, LBZ2;
2048 — SOZ2; 2560 — LRZ1; **2816 — SSZ1**.

### The part that should change how this question feels

The brief asked me to flag prominently if S3K achieves tall-looking backgrounds by something
other than a tall image. **It does not — it is a genuinely tall map.** But the reframe is better
than that, and it runs the other way:

> **S3K's scroll planes are 64x32 cells = 512 x 256 px** (`$9001`). *Every* S3K background taller
> than 256 px — 27 of the acts listed above — is streamed row-by-row into a **256-px** wrapping
> plane, exactly like its foreground.

So S3K produced 2,816 px of background from a resident window **half the size of ours**. We are
asking for 740 px out of 512. This is not an ambitious feature at the edge of the hardware; it is
the ordinary way the reference engine works, and we would be attempting it from a starting
position twice as favourable, with a foreground streamer that already does the identical job on
the identical buffer.

That also settles a design question the spec left open (its Q1, 512-px vs 256-px theme slices):
the S3K precedent argues for **streaming into a fixed window**, and says nothing in favour of a
particular chunk height.

---

## 8. Recommendation

**Do it. Vertical only. One engine parcel.**

It is already **step (2) of the booked build order** in `2026-08-08-bg-seam-streaming.md`, not new
work. Take *only* step 2 and explicitly decline steps (1) palette variants, (3) theme tile-pool
halving, (4) horizontal connects-to, (5) per-theme handoff. Those five together are the
*per-section-theme* feature; the owner asked for one tall picture, which is a strict subset, and
the subset is the cheap half. Horizontal is separately unattractive: the spec's own §1b.3
establishes there is **no single horizontal BG camera** (scroll is per-band), so vertical is the
only axis where "the BG seam" is even well-defined today.

**The cost, in a form he can picture:**

> One new routine, one scheduler, **four bytes of RAM, no new VRAM**, about 350 bytes of ROM, and
> **33 bytes of DMA per frame on average**. The background PNG becomes 512x744 instead of 512x512,
> and has to be drawn from the same 320 unique tiles — so about 45% more repetition in the art
> than today's. S3K did the same thing into a plane half our size, for 27 of its acts.

**One parcel or a programme?** The engine change is **one parcel** — with one caveat that could
make it two: the teleport-repaint regression (§3e.2). Everything else is additive. **The whole
thing is a small cross-lane project: 2 repos, 3 parcels** (aeon engine, aeon importer, aurora
canvas + preview + band-editor coordinates), plus an art pass that is the owner's call and is the
single largest item in the list.

**Sequencing note:** this makes `v_factor 4` (the hub's ruled-then-reopened `slower`) unnecessary
for OJZ but not wrong — shipping `slower` first is a zero-risk stopgap that this feature later
lets him take back. They do not conflict.

### Gates this would owe

1. **`bg_height_depth` — a comptime `ensure`, build-fatal.** In the act descriptor:
   `((GRID_H << SECTION_SIZE_SHIFT) - SCREEN_HEIGHT) >> v_factor_bg <= bg_map_span_px`, per
   non-locked scene. Every term derived from constants that already exist and are already
   `ensure`d in that file — **no pins**. Runner: the sigil build itself, which is the named runner
   for every other `ensure` there. Loud rather than green: names the act, the scene, the required
   span and the ceiling. **Red-first provable** by raising `GRID_H` or lowering the factor; the
   negative control is that it must *not* fire on the eighteen `v_factor 15` scenes.
   *Open mechanism:* the scene `v_factor` lives in the scene tables, not the descriptor, so this
   needs a comptime path from the scene registry into the act descriptor. `scene_registry.emp`
   already folds capabilities build-fatally across that seam (`SceneRegistry_CapsFolded`), so the
   shape exists — but I have **not** verified a value (as opposed to a bitmask) can travel it.
   If it cannot, fold a `SceneRegistry_MinVFactor` the same way.
2. **`test_bg_emit.py::TestBgMapSpanLockstep`** on the existing pytest lane (build-fatal since
   2026-08-16). Assert the emitted `zone_bg.bin` length `== 64 * map_h * 2`, and that `map_h`
   agrees across all three authors: the act descriptor, the importer, and the source PNG height/8
   — the same three-way shape as the existing `TestBgAnimBandCeiling`. Red-first by truncating the
   blob 2 bytes. **Must be run with `PYTHONDONTWRITEBYTECODE=1` and a cleared `__pycache__`** —
   see the recorded false-green defect where a same-length mutation in the same second was served
   from cache.

### TAGs for the controller (runtime confirmation, which this lane may not do)

- **T1 — window integrity.** Traverse OJZ act 1 top to bottom and sample
  `Parallax_Current_Vscroll_BG` with the Plane-B nametable row at `(bg_scroll >> 3) & 63`.
  *Falsifies the design* if any frame shows a row whose content belongs to a world BG row more
  than 63 rows from the current window — that would mean the wrap clamp is wrong.
- **T2 — budget.** Sample `Plane_Buffer_Ptr` at end of frame across the same traverse. *Falsifies
  the pricing* if it ever exceeds today's shipped worst case by more than 132 B; §3d predicts one
  entry per four frames and never two in one frame at `v_factor 3`.
- **T3 — teleport.** Fire a vertical teleport with a tall BG resident and screenshot the seam.
  §3e.2 predicts stale BG content unless a repaint is added; a clean seam would falsify that and
  make this a one-parcel job.

## 9. Open, with reasons

- **BLOCKED — no build was run** (the controller was relinking shared sigil). Nothing here depends
  on one: every number is from source, generated artifacts, or on-disk data. A build would settle
  only the actual ROM delta of the ~350 B, which is not decision-relevant.
- **Unverified — the comptime path for gate 1** (§8, gate 1's open mechanism). Reading
  `scene_registry.emp` establishes the seam exists for bitmasks; a value has not been proven to
  travel it.
- **Not costed — the art pass.** "Redraw OJZ's background 45% taller from 320 tiles" is the
  largest item on the list and it is the owner's call, not an engineering estimate.
- **Not examined — PAL.** All DMA figures are NTSC (`DMA_BUDGET_NTSC` 6144); PAL is 11,648 and
  strictly roomier, so NTSC is the binding case.
