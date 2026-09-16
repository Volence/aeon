# Aeon's baseline and modern techniques for background streaming

> **Research slice for MEGAACT-BG-STREAMING (2026-09-16).** This is the research agent's final report,
> extracted programmatically from its transcript and committed VERBATIM, never retyped: a report
> whose value is its `file:line` citations cannot be summarised without becoming the
> summary-of-a-summary this project was bitten by twice today. It is a LEAD for the design, not a
> finding the design may assume: every MEASURED claim is re-checkable at its citation.

---

# Background streaming in Aeon: what the engine already has, and which modern techniques fit

## 1. Verdict

The foreground doesn't solve the "nametable addresses VRAM by position" problem by keeping tiles still. It translates every word as it copies it into a RAM shadow of the plane, and it counts references. The background has neither: no RAM shadow of Plane B, and no translation step. So "put background tiles in the same page pool" is a real engine change, not reuse.

The crossing wipe (your step 6) gives the background something the foreground doesn't have, though. A wipe rewrites every one of the 64 plane rows, so once it finishes, no word from the old background can be left on the plane. That lets background residency be tracked **per layout instead of per word**. Load the new layout's page set before arming the wipe, and release the old set when the wipe finishes. This is exactly how S3K does its seamless Hydrocity act 1 to 2 change (sonic3k.asm:105719-105745): it queues act 2's art and doesn't change act until `Kos_modules_left` is zero.

**The most promising technique** is build-time slot assignment, done like register allocation. Treat each background theme's tiles as a variable whose "lifetime" is the set of regions where it can be on screen. Treat VRAM slots as registers. Colour the region-adjacency graph so neighbouring themes never share a slot. Layouts can then keep baked VRAM positions, `Draw_BG_TileRow` doesn't change, and the build proves the capacity. For a straight chain of zones this needs two colours, which is exactly the "two half-pools" plan already in `docs/research/2026-08-08-bg-seam-streaming.md`.

**Cross-zone tile deduplication does not change the budget.** Real Sonic 2 and S3K zones share 0.1-0.3% of tiles even when flips are allowed (section 4).

## 2. Aeon baseline (master `60a94111`)

### Q1. How the foreground page cache works (all MEASURED)

**Pages and frames**
- A page is 64 tiles (`constants.emp:380`).
- `PAGE_FRAMES = POOL_TILE_CEILING / 64`, and `POOL_TILE_CEILING = 768` (`constants.emp:405`, `:871`). That is **12 frames**. The capacity constant `PAGE_FRAMES_MAX` is 15 (`:421`).
- OJZ act 1 has 10 pages (`generated/ojz/act1/ojz_act_pool_manifest.emp:7`). So the shipped act is **fully resident, and nothing ever evicts in normal play**:
  - `Level_LoadArt` sets `PageIn_Fully_Resident` and the direct-map mode (`load_art.emp:90-93`, `:175-189`).
  - Eviction only happens under the `STRESS_EVICT` fixture. Its own comment says OJZ's working set equals the whole pool (`constants.emp:474-503`).

**How indices stay valid**
- Staged block words hold section-local indices. `PageCache_PatchRun_Seq` / `_Col` map each word local → global → physical as `frame<<6 | global&63` while copying into the RAM `Tile_Cache_Nametable`, 80×60 cells (`page_cache.emp:449-586`).
- On each write it increments the new frame's refcount and decrements the overwritten word's frame. A frame whose count reaches 0 is stamped and flagged `PF_EVICTABLE`.
- Only refcount-0, unpinned frames can be evicted (`page_cache.emp:12-17`, `:246-336`).
- Plane cells outside the cache window can still hold stale physical words. The code accepts them because they're never visible (`plane_buffer.emp:405-410`, `:480-483`).
- If a page isn't resident, the copy site requests it, sets `Cache_Art_Stall`, and leaves the cell alone. The camera then holds back (`CLAMP_MARGIN_TILES`, `constants.emp:545-560`).

**Eviction choice:** the oldest frame by `Frame_Counter - pf_stamp`, found by scanning all frames (`page_cache.emp:258-296`). Pages the build marks as used by at least 75% of sections are pinned (`tools/ojz_strip_gen.py:142`, `:826`). Demand pages are protected until their first reference (`:422-441`).

**Decoder budget:** there isn't a fixed cycle budget.
- ZX0 pages decode in `VSync_Wait` idle time and are paused at VBlank by the "bookmark" (`page_in.emp:1-57`).
- One page decodes at a time, because there is a single staging buffer.
- Raw-form pages skip decoding and go straight from ROM by DMA (`page_in.emp:288-320`).
- ARCH §9.7 quotes "2 KB page ≈ 45 K cycles vs ~42.5 K average idle". That comes from the doc; I did not re-measure it.

**Transfer budgets**
- Each landing is charged against `Art_Budget_Remaining`, reloaded from the act's budget every frame. OJZ's budget is 4096 B, i.e. 2 pages (`page_in.emp:131`; `act_descriptor.emp:172`).
- The VBlank DMA window is `DMA_BUDGET_NTSC` 6144 / `DMA_BUDGET_PAL` 11648 (`constants.emp:708-709`). The plane buffer drain is charged against the same window.
- The enqueue cap is 12288 B (`:723`), and the queue has 8+12+12 slots (`:373-376`).

### Q2. Can background tiles join the same pool?

**Not as-is** (MEASURED, with my reasoning on top). Every piece of code that assumes the background block is fixed:
- **`tools/inject_editor_bg.py:1347`** bakes `idx + BG_TILE_BASE_SLOT` into the layout words. `tools/ojz_strip_gen.py:414` does the same.
- **`Draw_BG_TileRow`** copies layout words straight from ROM into the plane buffer with `move.l`. There is no translation and no refcount (`plane_buffer.emp:639-700`).
- **`Section_RedrawPlanes`' Plane B half** is a raw window blit (`section.emp:645-672`).
- **`BG_Init`** copies the tile blob to `BG_TILE_BASE_VRAM` and blits the layout once (`bg.emp:128-296`).
- **`BgAnim` bands** carry absolute `vram_dest` values (`bg_anim.emp:62`; `inject_editor_bg.py:1196`).
- **`Region` has no tiles field**, only `rg_bg_layout` and `rg_bg_span` (`structs.emp:132-149`).

What would break if background words were treated like foreground words:
1. **No refcount source.** There's no RAM shadow of Plane B. The 2026-08-08 doc rules out an 8192 B shadow for the DEBUG build.
2. **Translation cost on the wipe.** Patching each word costs 89-136 cycles in the ARCH F1 measurements (doc figure, not re-measured). A row is 64 words and the wipe does 4 rows per frame.
3. **Frame ids only cover tiles 0-767.** The Page_Frames arrays are sized by `PAGE_FRAMES_MAX`. The background arena at tile 1024 would need frame ids 16-21, and 1400/64 isn't a whole number.

The workable shape is refcounting at **layout granularity**, which the wipe's full coverage makes safe (`bg.emp:549-552`: "covering all PLANE_V_CELLS plane rows exactly once"). Whether pages sit at fixed slots or in shared frames is the decision in section 3.

### Q3. The full VRAM map (`games/sonic4/vram.toml`, MEASURED)

| Tiles | Region | Size (tiles) |
|---|---|---|
| 0-767 | `fg_art_pool` | 768 |
| 768-895 | `spare_nametable` (reserved at $6000 as a possible plane base) | 128 |
| 896-911 | dust puff | 16 |
| 912-923 | spindash dust | 12 |
| 924-927 | ring sparkle | 4 |
| 928-956 | insta-shield | 29 |
| 957-958 | debug preset readout | 2 |
| 959 | **free** | 1 |
| 960-991 | character window | 32 |
| 992-999 | test object | 8 |
| 1000-1015 | ring placeholder | 16 |
| 1016-1019 | test marker | 4 |
| 1020-1023 | debug lab name | 4 |
| 1024-1399 | `bg_region` (of which `band_reserve` 56) | 376 |
| 1400-1447 | waterline strips | 48 |
| 1448-1471 | spring | 24 |
| 1472-1491 | sprite table | 20 |
| 1492-1500 | tails appendage | 9 |
| 1501-1503 | debug BG-anim tag | 3 |
| 1504-1531 | hscroll table | 28 |
| 1532-1535 | debug raster tag | 4 |
| 1536-1791 | Plane A | 256 |
| 1792-2047 | Plane B | 256 |
| 1920-2047 | window plane (overlaps Plane B, feature disabled) | 128 |

Where background streaming space could come from:
- **The pool's idle frames.** OJZ uses 10 of 12, so 2 frames (128 tiles) are idle today. They're only available if the mega-act's foreground working set leaves them.
- **The unused `band_reserve`:** 56 tiles.
- **`spare_nametable`:** 128 tiles, but those are the scarce aligned address run.
- **The plane-size lever (64×32):** halves both nametables and frees 256 tiles. It's priced in `docs/research/2026-09-09-plane-size-lever.md`.
- **Nothing else.** The map has 1 free tile.

### Q4. Palettes (MEASURED)
- A region crossing runs `Parallax_CheckBoundary` → `Effects_InstallPreset` → `Parallax_StartTransition` (`parallax.emp:1261-1262`).
- `ep_pal` → `Palette_LoadPal` loads 96 bytes, which is CRAM lines 1-3. Line 0 belongs to the character (`palette.emp:48-55`).
- It either snaps into `Pal_Base` or, if `ep_transition` armed `Palette_ArmFade` first, starts a `PAL_FADE_FRAMES` = 16-frame lerp toward `Pal_Target`. A snap cancels a fade already running (`palette.emp:285-321`; `preset.emp:282-398`).
- Order per frame: base → cycling → cross-fade → operators (fade to black/white, flash) → variants, all in `Palette_Compose`.
- **Foreground and background share lines 1-3.** There's no background-only palette line, so a zone's palette change hits both planes at once.

### Q5. What the crossing wipe guarantees, and what it doesn't (MEASURED)

**It guarantees:**
- It arms, level-triggered, on the frame the effective layout pointer differs from `BG_Plane_Layout`.
- It snaps `BG_Plane_Top` to the destination window.
- It rewrites all 64 plane rows, 4 per frame (16 frames), starting at the top visible row and walking down.
- Its cursor only advances when a row is admitted to the plane buffer.
- Plane-buffer headroom is pinned by an `ensure` (`bg.emp:527-615`, `:478-496`).

**It does not:**
- **Load any tiles.** It assumes every tile the new layout references is already resident. `gen_tall_bg_test.py` says so outright: "every cell in the map names a tile the act's BG tile blob actually loads".
- **Delay the palette.** The palette snaps on frame 0, so old art shows under the new palette until its rows are repainted (`bg.emp:326-335`).
- **Swap `BgAnim` tables.**

## 3. Techniques

| # | Technique · source | Label | Fit to Aeon | Cost | Worth it? |
|---|---|---|---|---|---|
| 6 | Virtual texturing ([van Waveren, *Software Virtual Textures*, 2012](https://mrelusive.com/publications/papers/Software-Virtual-Textures.pdf)) | Code MEASURED; fit INFERRED | The foreground cache already is this. `page_cache.emp:10` cites van Waveren's free/evictable/locked states. The key difference, from his §1: "with a texture it is possible to fall back to slightly blurrier data without stalling". The VDP has no coarser fallback, and a miss shows garbage, which is why Aeon holds the camera back instead. The background is the missing application, but only at layout granularity (Q2). | Page-set table per layout in ROM; preload gate on the wipe arm | **Yes**, as layout-level residency. Not as per-word translation. |
| 7 | Clipmaps ([Tanner et al. 1998](https://dl.acm.org/doi/10.1145/280814.280855); [Wikipedia](https://en.wikipedia.org/wiki/Clipmap)) | INFERRED | Van Waveren §2 says the clipmap's single focus point suits data with natural spatial correlation. A side-scroller has that, and Aeon's wrapping 64×64 plane plus the 80×60 cache already are a one-level clip region. There's no resolution-by-distance equivalent on a tile VDP. "Detail tiers" can only mean authoring simpler far layers, which is what the aurora art simplification already did (448 → 320). | None at runtime | **No** as a mechanism; already present in the form that matters. |
| 8 | Build-time cross-zone deduplication | **MEASURED** (section 4) | The VDP gets H/V flip for free; the foreground build already uses it (`tools/tile_dedupe.py`, lex-smallest of 4 orientations). Palette-line remapping doesn't create sharing: identical pixel indices are already exact matches, and matching a colour permutation needs a CRAM line holding those permuted colours, which isn't free. | Build time only | **No** for real zones (0.1-0.3%). Yes within one zone's iterations. |
| 9 | Build-time residency planning ([Belady offline optimum](https://www.cs.jhu.edu/~huang/cs318/fall18/lectures/lec11_replacement.pdf)) | INFERRED | Belady needs the future request sequence, and the player's path isn't known. What the build does know is the region graph. So the plan should be per-region required sets plus per-edge preload sets, with a build-time proof that every adjacent pair's union fits the capacity. The foreground already has a small version of this in pinning (`ojz_strip_gen.py:142`). | Tool work; a few ROM bytes per region | **Yes**, as graph constraints, not a replayed script. |
| 10 | Predictive prefetch | Code MEASURED; background INFERRED | Already exists for the foreground: `PageCache_Prefetch`, 2 enqueues per frame from the leading edge (`constants.emp:465`). Background themes change at discrete region edges, so a trigger rectangle placed ahead beats a velocity model. At a maximum of 16 px/frame (`CAM_MAX_Y_STEP`, per the plane-size doc), ~12 frames of preload needs roughly 192 px of lead. | Near zero | **Yes, cheap**: region-graph lookahead, not velocity. |
| 11 | Content-addressed tiles ([Git internals](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects)) | MEASURED | The foreground global dedupe already is this. A game-wide store saves almost nothing (section 4). Its value is as the stable tile ID the slot allocator in #12a works on. | Build time | Only as IDs; no ROM or VRAM win. |
| 12a | **Build-time slot colouring** ([Poletto & Sarkar, linear scan](http://web.cs.ucla.edu/~palsberg/course/cs132/linearscan.pdf)) | INFERRED | Themes are "variables", region-graph lifetimes are "live intervals", background VRAM slots are "registers". Layouts stay baked-physical, so there's zero runtime translation. A zone chain is a path, so 2 colours suffice, which is the 2026-08-08 half-pool plan generalised. | 376/2 = 188 tiles per theme today, or more if the plane-size lever frees 256 | **Best fit.** Capacity is the open question. |
| 12b | S3K primary/secondary split (sonic3k.asm:105719-105745, levartptrs :199306) | MEASURED | Shared "primary" art stays resident at fixed VRAM. "Secondary" art is queued into VRAM at a transition while only primary art is on screen, and the act switch waits for the queue to empty. Hydrocity primary is 283 tiles; act 1 secondary 571; act 2 secondary 549 (from my decompression). This is the corridor precedent, in shipped code. | — | **Yes**, as the design pattern. |
| 12c | Raw-form background pages | MEASURED mechanism; timing INFERRED | Raw pages skip decoding and the single staging slot (`page_in.emp:288`). At OJZ's 2 pages/frame budget, 376 tiles (6 pages) could land in about 3 frames instead of serial ZX0 decodes. | ROM (uncompressed) | **Yes** for theme preloads. |

## 4. The tile-sharing measurement (item 8)

**Method.** Throwaway Python in the scratchpad; nothing in the repo was touched.
- Editor exports: a 2-byte big-endian length header, then 32-byte 4bpp tiles.
- Keys compared:
  - exact bytes
  - flip: lowest of the 4 H/V orientations
  - flip+perm: that plus colours renumbered in first-seen order with 0 kept fixed. This is an upper bound, since it isn't free on the VDP.
- Solid single-colour tiles were excluded for the pair tests.
- Real zones: I wrote my own Kosinski and Kosinski-Moduled decoders, because `sonic_hack/tools/kosdec` crashes with an assertion. EHZ_HTZ decodes to 914 tiles, which looks right.

**Aeon's 18 editor backdrops.** Your "zero shared across any pair" is **wrong**:

| Measure | Result |
|---|---|
| Pairs sharing at least one non-solid tile, exact | 116 of 153 |
| Most shared, exact | deep-forest v12 / v13: **390**; v10 / v11: 386 |
| Sum of per-backdrop uniques → union, exact | 7624 → 3917 |
| Sum → union, flip+perm | 7202 → 3726 |
| `ojz_act1_bg` and `ingame-forest-v15` shared with any other export | **0**, even under flip+perm |

- The 16 deep-forest files are versions of one generator, so their overlap says nothing about different zones.
- Exports are **not** deduplicated even exactly: v15 has 216 tiles but 182 exact-unique, and v10 goes 503 → 487 with flips.
- The **shipped** blob is `generated/ojz/act1/bg_tiles.bin` = **320 tiles**, not 218. It's already flip-deduplicated (2340 flipped words in `zone_bg.bin`), and it shares 199 tiles with `ingame-forest-v15`, which it was derived from.

**Real zones, foreground and background art combined, non-solid:**

| Set | Exact saved | Flip saved | Flip+perm saved |
|---|---|---|---|
| Sonic 2 (8 zone sets, 6587 tiles summed) | 14 (0.2%) | 22 (0.3%) | 158 (2.5%) |
| S3K (7 zones, primary + all secondaries, 9646 tiles) | 9 (0.1%) | 20 (0.2%) | 213 (2.4%) |

The largest single pair is 30 tiles (CPZ and WFZ, flip+perm only).

Per-zone unique counts after flip dedup: Sonic 2 is 604-965; S3K is 698-2536.

**So different zones really do share almost nothing.** The budget is each zone's working set, and one Sonic 2 zone's whole art set (604-965 flip-deduplicated tiles) is already about the size of the 768-tile pool on its own.

## 5. What I couldn't determine
- **Background-only tile counts for Sonic 2 / S3K zones.** Their tile sets mix foreground and background. Splitting them needs layout and chunk parsing I didn't do, and that's the number that decides whether 188 tiles per colour is enough.
- **Runtime cycle costs** of per-word background translation or a layout-level pin. I didn't use an emulator, per the constraints, so the patch costs quoted above are the doc's F1 figures.
- **Whether a foreground seam between two zones fits 12 frames.** The 80×60 window around a seam would reference both zones' pages; I didn't model it.
- **Four S3K zones** (MHZ, SOZ, LRZ, plus the `.kos` special stage) weren't decoded. The script only covered 7 zones.

## 6. Things in the brief that are wrong
1. **"Zero tiles shared across any pair."** False for 116 of 153 pairs. True only for `act1_bg` and `ingame-forest` (section 4).
2. **"OJZ act 1 default background = 218 unique tiles."** That's the editor file. The shipped blob is 320 tiles. So "218 + 182 = 400 > 376" understates the problem: 320 + 180 = 500.
3. **"The background was never designed to stream / the corridor plan lived only in notes."** The phase 2 spec really has zero matches (I checked; the phase 2 plan mentions the background blob once, at line 285). But a dedicated design exists:
   - `docs/research/2026-08-08-bg-seam-streaming.md` §4 step 3: "incoming theme's tile blob paged into the inactive half of the 448-tile BG pool via the P2 page-in queue".
   - `docs/DEFERRED_WORK.md:7713` "SPEC: Per-section background grid with seam streaming".
   - Both use the stale 448-tile figure.
4. **"The foreground page cache is capped by ROM, not VRAM."** Only true for the working set within one window. It needs working set ≤ 12 frames minus pinned pages, and OJZ has never actually streamed outside the stress fixture.
5. **Doc vs code disagreements:**
   - **`ENGINE_ARCHITECTURE.md:1738`:**
     - It says 448 tiles; the code says 376.
     - It cites "constants.asm"; the constants live in `constants.emp`.
     - It says "~340" in use; the shipped blob is 320.
     - "The engine doesn't read this constant" is false: `bg.emp:157` clamps on it.
     - It claims "the same residency guarantee the FG act pool relies on", but the foreground relies on translation plus refcounts, not fixed slots.
   - **ARCH:17, :1666, :1689** say the pool is "1,472 tiles"; `POOL_TILE_CEILING` is 768.
   - **ARCH §9.7** says "≤ 959" and "41 pages vs 15 frames"; there are now 12 frames.
   - **ARCH:1768** says Tier 3 background tiles are "already resident before play begins". That's false for streaming acts, and background words have no translation path at all.
   - **The `constants.emp` comment** above `ART_POOL_PAGE_BYTES_SHIFT` says the destination is `page_id << shift`; the code uses `frame << shift` (`page_in.emp:246-253`).
   - **`tools/perspective_floor_gen.py:191`** mirrors 400 and asserts equality with 376 at `:473`, so that check fails if run.
   - **`tools/gen_tall_bg_test.py:65`** uses 448.
   - **`ojz_strip_gen.py:396`** docstring says "64×32" (layouts are 64×64).

Scratch scripts are in `/tmp/claude-1000/-home-volence-sonic-hacks-aeon/24471b62-cac3-45bf-af06-17ff8b6994b6/scratchpad/` (`m.py`, `kos.py`, decoded `s2/` and `s3/`).
