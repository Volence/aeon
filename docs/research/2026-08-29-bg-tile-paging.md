# Can the 448-tile background region become a residency cache? (d-31 option 3, follow-on)

*2026-08-29. DESIGN ONLY. **No build was run** (a certification run was in flight against the
shared binaries) and **no emulator was used**. Every number below is read from source, from the
generated artifacts, or computed from the shipped editor data at the revisions cited. Runtime
questions are TAGs in §9.*

**Direct predecessor:** `docs/research/2026-08-29-tall-background-map.md`, branch
`design/bg-tall-map`, commit **`9555d96b`** (local branch; not on `origin/master` at the time of
writing). That doc priced *nametable* streaming and concluded BG tile paging was "a separate and
much larger project". This doc is the audit of that characterisation.

**The owner's question, verbatim:**

> *"so question on this, is there a way to get this more? Like mayybe having 448 be the ceiling
> for a region or something? Like if I want the bg height to be the 2.6k pixels there's probably
> more tiles than that, is there a way to have it dynamic like we have for forground, where at
> most loaded in there's x tiles"*

---

## 0. The verdict, first line first

**Yes. The working set does not kill it.** On the shipped OJZ background, the worst
screen-height window needs **268 distinct tiles of the 448**, and the mean window needs 167. The
448 stops being a limit on the authored picture and becomes a limit on **any 232-px-tall
horizontal slice of it** — which is exactly the "dynamic, at most X loaded" shape he described.

Size: **not one parcel, and not the "much larger project" the sibling doc called it either.**
It is roughly **320 bytes of genuinely new engine code** — because three quarters of the
machinery is already shipped and, by a real accident of the VRAM map, the existing
frame→VRAM arithmetic already addresses the BG region *exactly*. But it is **strictly
downstream of BG row streaming** and cannot be taken first, for a structural reason given in
§3. Call it **4-5 parcels behind the streamer**, on proven machinery.

The three headline numbers:

| | today | with paging |
|---|---|---|
| ceiling on authored BG tiles | **448** for the whole act | **ROM budget** (~2,000 before the next wall) |
| ceiling on *resident* BG tiles | 448 | **320** (448 − `band_reserve` 128) |
| what that ceiling now applies to | the entire picture | **any 29 map rows = 232 px** |

---

## 1. What is established — re-derived, with two corrections

### 1a. Confirmed

| claim | verdict | authority |
|---|---|---|
| `BG_TILE_REGION_BYTES = VRAM_SPRITE_TABLE − BG_TILE_BASE_VRAM = $B800 − $8000 = $3800` = 14,336 B = 448 tiles | **confirmed** | `engine/level/bg.emp` (the `const` and its comment); `VRAM_SPRITE_TABLE = $B800`, `BG_TILE_BASE_VRAM = $8000` at `engine/system/constants.emp:506-508` |
| the BG blob is loaded **once, in one shot**, at load time and nothing pages it | **confirmed** | `BG_Init` in `engine/level/bg.emp` — one `.tile_copy` `move.l`/`dbf` run into `vdp_comm(BG_TILE_BASE_VRAM, …)`, called from `Level_LoadArt` with display off. The only other Plane-B writer is `Section_RedrawPlanes`, at level init and cache recovery only |
| the shipped override reads **layout 4096 / tiles 320 / anims 1** | **confirmed exactly** | `games/sonic4/data/editor_bg_override.json`, parsed |
| the FG already runs a globally-deduped, spatially-ordered, paged residency cache | **confirmed** | ARCH §9.7 (`docs/ENGINE_ARCHITECTURE.md:4769`), status SHIPPED; `engine/level/page_cache.emp`, `engine/level/page_in.emp` |
| `band_reserve = 128`, so the static importer's budget is **320** | **confirmed** | `games/sonic4/vram.toml:122-132` (`bg_region`, base 1024, tiles 448) |
| generated artifacts: `bg_tiles.bin` = 10,242 B (2 B header + 320 × 32), `zone_bg.bin` = 8,192 B | **confirmed** | `stat` on `games/sonic4/data/generated/ojz/act1/` |

### 1b. CORRECTION TO THE BRIEF — the FG's local map is **not** an eviction shield

The brief states, as the thing "most likely to kill it":

> *"The foreground reaches its tiles through a per-section local map, so a page moving does not
> invalidate the nametable."*

**This is false, and it is the single most load-bearing correction in this document** — because
if it were true, plane B would be uniquely disadvantaged, and it is not.

`PageCache_PatchRun_Seq` / `_Col`'s own header block (`engine/level/page_cache.emp:474-530`)
states the pipeline verbatim:

> *"read the LOCAL word at (a0), local→global through the staged block's section map
> (`Cache_Cur_LocalMap` — F-3 merge-translation), **global→physical**, capture-old-BEFORE-write
> at (a1), ref the new frame / unref the overwritten one"*

and ARCH §9.7 confirms what lands: *"the 11-bit nametable field only ever carries the **physical**
index (≤ 959)"*.

So the local→global map is a **build-time index-space compression device** — it is what lets a
section address ≤2048 tiles through an 11-bit field without a global 2048-tile ceiling. It is
resolved *before* the physical index is computed, and the word written into
`Tile_Cache_Nametable` (and thence into plane A) is the **physical VRAM tile index**. A page
that moves invalidates every already-written cell exactly as it would on plane B.

**What actually protects the foreground is the refcount.** `PageCache_AllocFrame` scans only
`PF_EVICTABLE` frames, and `PF_EVICTABLE` is cleared on every ref 0→1 and set on every unref
1→0 — so a frame referenced by any cell in the resident window is structurally never a victim.
The constants file records the consequence in its own words
(`engine/system/constants.emp:360-370`):

> *"the refcount source is the whole 80×60 `Tile_Cache_Nametable` window … the AllocFrame assert
> correctly REFUSES to evict displayed art."*

That reframes question 2 completely, and §3 answers it on the corrected footing.

### 1c. CORRECTION TO THE SIBLING DOC — the two unlocked OJZ scenes are named wrong

`9555d96b` §2 names them *"(`OJZ_Depth`, `OJZ_Underwater`) at `v_factor 3`"*. There is no
`Scene_OJZ_Depth`. The two `v_factor: 3` scenes are:

- **`Scene_OJZ_Default`** — `games/sonic4/data/effects/ojz_scenes.emp:123`, `count: 4,
  v_factor: 3, v_center: 512, v_offset: 0` (line 137)
- **`Scene_OJZ_Underwater`** — same file line 152, same header at line 166

`OJZ_Depth` in this tree names *effects* objects — `OJZ_DepthVSplit`, `OJZ_Preset_Depth`
(`games/sonic4/data/effects/ojz_effects.emp:942,1024`). The nearest actual scene is the
editor-generated **`Scene_Editor_ojz_act1_depth`**
(`games/sonic4/data/generated/ojz/act1/effects_scenes.emp:40`), and its source
`games/sonic4/data/editor/effects/ojz_act1_depth.json` carries **`v_factor = 15`** — it is one
of the eighteen *locked* scenes, not one of the two unlocked ones. The sibling doc's *count*
(2 unlocked of 20) and its arithmetic are unaffected; only the name is wrong. §7 shows why the
distinction happens to matter a great deal.

### 1d. Stale comment, no consequence

`engine/system/constants.emp:272-274` says *"`POOL_TILE_CEILING(960)` / `ART_POOL_PAGE_TILES(64)`
= 15 frames"*. `POOL_TILE_CEILING` is **896** (`constants.emp:668`, `ensure`d against
`vram.toml` at `games/sonic4/config/constants.emp:398`), so `PAGE_FRAMES` is **14**, not 15. The
derivation and its `ensure` are correct; only the prose is stale. Noted because §5 raises this
constant and the next reader will trip on it.

---

## 2. The working set — measured, not guessed

**This is the question the whole thing turns on**, so it is answered from the shipped data
rather than from a model.

### 2a. Method

`games/sonic4/data/editor_bg_override.json` is row-major, `idx = row*64 + col` — confirmed at
`tools/inject_editor_bg.py:558,566` (*"the editor is ROW-MAJOR (idx = row\*64 + col), the engine
reads COLUMN-MAJOR"*). Each cell's low 11 bits (`NT_TILE_MASK = $07FF`) are the tile id; bits
11-15 are pal/pri/flip and are irrelevant to residency. All counts below are over distinct low-11
values, on the shipped 64 × 64 layout, run with `PYTHONDONTWRITEBYTECODE=1`.

### 2b. The numbers

```
whole map (64 rows, 4096 cells)                    320 distinct   (== len(tiles); closes exactly)
distinct tiles in ONE row (64 cells)               min 1   max 16   mean 12.8
distinct tiles in a 28-row window (224 px)         min 68  max 268  mean 162.7
distinct tiles in a 29-row window (232 px)         min 70  max 268  mean 166.7
distinct tiles in a 45-row window                  min 197 max 270  mean 255.3   (interpolated at 48)
distinct tiles in the full 64-row plane            320 (every window; the map IS 64 rows)
```

**The screen is 224 px = 28 rows; 29 covers a partial-scroll straddle.** So the answer to
"how many tiles must be resident at once" for *this* art is **268 worst, 167 mean, against a
320-tile static budget and a 448-tile region.**

### 2c. Why it comes out that way — the locality is real and strong

```
tile vertical span (last-use row − first-use row), over all 320 tiles:
    median 8 rows    mean 9.1    p90 24    max 61
    only 5 of 320 tiles are used across more than 32 rows
    25 of 320 are used in exactly one row
```

A median tile lives inside an 8-row (64-px) horizontal band. That is precisely the property a
residency cache needs, and it is not something anyone designed for — it falls out of drawing a
background where the sky is at the top and the ground is at the bottom.

### 2d. What a *tall* map costs, extrapolated from the same data

New distinct tiles introduced per row, scanning top to bottom (the warm-up rows 0-15 are
excluded because they are the cold-cache transient):

```
rows 16..63:   212 new tiles over 48 rows  =  4.42 / row
rows 32..63:   199 new tiles over 32 rows  =  6.22 / row
```

Extrapolating `total ≈ 320 + rate × (rows − 64)`:

| map | rows | distinct tiles authored | vs the 448 region |
|---|---|---|---|
| today (512 px) | 64 | **320** | fits, 128 spare (the band reserve) |
| OJZ at `v_factor 3` (744 px) | 93 | **448 – 500** | **exactly at, or just past, the wall** |
| Sky-Sanctuary class (2,816 px) | 352 | **1,592 – 2,111** | **3.6× – 4.7× the entire region** |

The 744-px figure is an **independent confirmation of the sibling doc**, which reached "you would
need 465 static tiles" from cells-per-tile density. Two different derivations — density there,
introduction rate here — landing on 448-500 and 465. His instinct in the question ("there's
probably more tiles than that") is right, and it is right by a factor of four for the height he
named.

### 2e. The multiplier paging buys

Resident requirement is a property of the **window**, not of the map, and the span statistics in
§2c say it stays put as the map grows:

| map | authored | resident (29-row worst) | **multiplier** |
|---|---|---|---|
| 744 px | 448 – 500 | 268 | **1.7× – 1.9×** |
| 2,816 px | 1,592 – 2,111 | 268 | **5.9× – 7.9×** |

**Paging buys `map_height / window_height`, capped by how much the art actually changes with
height.** For the height he asked about that is a factor of six to eight, and it is the
difference between "impossible" and "comfortable".

### 2f. The one thing paging does NOT buy — say this to him plainly

The per-row measurement is the important caveat: the shipped art uses **at most 16 distinct
tiles in a 64-cell row**, i.e. it is roughly 4× horizontally repetitive. If art were
*horizontally* unique too, a 29-row window would need 29 × 64 = **1,856 tiles** and no cache
of any size in this VRAM map would hold it.

> **Paging makes background HEIGHT free. It does nothing at all for horizontal variety inside
> one screen-height band.** The 448 (really 320) is now a budget on any 512 × 232 px slice.

The shipped art's worst slice spends 268 of that 320. That is a genuine 1.19× margin — real, but
not generous, and it is the number the art pass has to hold.

---

## 3. The indirection problem — the verdict, on the corrected footing

Given §1b, the question "is there an existing indirection that survives a page move" has the same
answer on both planes: **no, and the foreground does not have one either.** Both planes' cells
carry physical tile indices; both would be invalidated by a page moving. What the foreground has
is a **refcount that forbids the move while the cells are live**.

So the real question becomes: *can plane B maintain that refcount?* Three findings.

### 3a. Today it structurally cannot — and this is the dependency, not a defect

Plane B's 4,096 cells are written once by `BG_Init` and then never touched (`bg.emp`'s own
header: *"Both happen once at level load"*; `Section_RedrawPlanes` runs *"at level init / cache
recovery only"*; teleports were removed from that path on the position-independence argument).
Every cell therefore references its tile **permanently**. Under the FG's discipline every BG
frame's refcount would be permanently non-zero, nothing would ever be `PF_EVICTABLE`, and
`AllocFrame` would find no victim.

> **BG tile paging on a statically-blitted plane degenerates to exactly today's behaviour, with
> extra machinery.** Row streaming is not an optimisation you could add later — it is what
> *creates* the eviction opportunity. Paging cannot be taken first.

This is where the sibling doc is right about ordering, and it is the strongest reason its
"separate project" framing is defensible even though its *size* estimate is not.

### 3b. Plane B's refcount is far CHEAPER than plane A's, not more expensive

The foreground pays a 9,600-byte RAM shadow (`TILE_CACHE_NT_SIZE = 80 × 60 × 2`,
`constants.emp:240-243`) and a per-*cell* ref/unref inside the copy runs, because its content is
a two-dimensional function of the camera window and of per-section staged blocks.

**Plane B's content is a pure function of the map row.** Row `R` of the map always contains the
same 64 cells and therefore always references the same set of pages. So the build can emit **one
page-membership bitmask per map row** — a word per row — and the runtime refcount for page `p`
becomes "how many *resident rows* have bit `p` set", maintained by one OR/decrement pass as each
row enters and leaves. Costs:

| | foreground | background |
|---|---|---|
| refcount source | `Tile_Cache_Nametable`, **9,600 B RAM** | per-row page bitmask, **2 B/row in ROM** (352 B for a 2,816-px map) |
| refcount granularity | per cell | per row |
| refcount work | 2 frame-record updates per word patched | 1 pass over ≤16 bits, once per row transition (≈ once per 4 frames) |

Three orders of magnitude cheaper. This is the finding that most changes the cost picture.

### 3c. Stable allocation — possible for some pages, not provable for the rest

The brief asks whether allocation can be made stable enough never to move. Partly:

- **Pinned pages: yes, and the mechanism already exists.** `ART_PAGE_FLAG_PINNED` /
  `PF_PINNED` make a page a permanent non-victim; `PageCache_Publish` reads `pm_flags` and sets
  it. The `band_reserve` 128 tiles (two 64-tile frames) that `BgAnim` rotates art through are
  exactly this: build-pinned, never evicted, never moved. **`BgAnim` therefore needs no changes
  at all** — its `vram_dest` slot ranges stay fixed by construction.
- **A direct-mapped scheme (`page mod N`, so the layout could bake final physical indices at
  build time and skip the runtime translation entirely): attractive but not provable.**
  Spatial ordering by first-use row makes conflicts *unlikely* — a 29-row window spans ~3.7
  consecutive pages (§4) and consecutive pages never alias under `mod 5`. But "unlikely" is not
  an invariant, a conflict is a silent wrong-tile on screen rather than a loud stall, and the
  five long-span tiles in §2c are exactly the counterexample generators. **Take refcount + LRU,
  matching the foreground**, and keep the direct-mapped idea as the thing the `PageCache_Direct_Map`
  latch (§9.7's F1 fix) already does for the degenerate case.

**Verdict on question 2: not a blocker.** It is a hard sequencing dependency (§3a) and a cheap
implementation (§3b).

---

## 4. Can the foreground's machinery serve plane B?

Mostly yes, and one piece of it is better than "yes".

### 4a. THE LUCKY FACT — the dest arithmetic already addresses the BG region exactly

`PageIn_Process` derives a page's VRAM destination as
(`engine/level/page_in.emp:246-252`, `ART_POOL_PAGE_BYTES_SHIFT = 11`):

```
dest = frame << ART_POOL_PAGE_BYTES_SHIFT     // frame * 2048
```

Evaluate it past the foreground's 14 frames:

```
frame 16 * 2048 = $8000  ==  BG_TILE_BASE_VRAM      (constants.emp:506)
frame 22 * 2048 = $B000  ... + 2048 = $B800
frame 23 * 2048 = $B800  ==  VRAM_SPRITE_TABLE      (constants.emp:387)
448 tiles = 7 * 64 = frames 16..22, EXACTLY
```

**The BG region is exactly seven 64-tile frames, starting exactly on a frame boundary, ending
exactly at the SAT.** No new destination math, no base offset, no second formula — the shipped
expression already lands correctly on `$8000..$B7FF` for frame ids 16-22. That is worth a
sentence in the merge note when this ships, because it is the kind of coincidence that quietly
saves a parcel.

### 4b. Reusable unchanged — named by symbol

| symbol / mechanism | file | shared? |
|---|---|---|
| `ZX0R_Decompress` + the `@resumable` contract | (compression) | **as-is** |
| `PageIn_BankRegs`, `PageIn_Resume`, the VBlank bookmark hook | `page_in.emp:442,469` | **as-is** |
| `Art_Staging_Buffer` (2,048 B) + `PageIn_Staging_Busy` handshake | `constants.emp:581` | **as-is — but SINGLE-SLOT (see §4d)** |
| `PageIn_Enqueue` / `PageIn_Process` / `PageIn_EnqueueLanding` | `page_in.emp:554,104,503` | **as-is** |
| the 8-slot FIFO + `PGRQ_DEMAND` / `PGRQ_BULK` / `PGRQ_PREFETCH` disciplines | `constants.emp:344-352` | **as-is** |
| `PageManifest` {source, tiles, form, flags} + `ART_PAGE_FORM_ZX0` / `_RAW` + the 4-byte wrapper | `constants.emp:254-268` | **as-is** — BG pages are just more manifest entries |
| `dest = frame << ART_POOL_PAGE_BYTES_SHIFT` | `page_in.emp:246` | **as-is** (§4a) |
| `Page_Table` (256 entries), `PAGE_TABLE_MAX = 256` | `constants.emp:268` | **as-is** — OJZ FG uses 10; BG adds 7-25; nowhere near |
| `Page_Queued_Bits` + the claim-continuity invariant | `page_cache.emp:169-215` | **as-is** |
| `PageCache_Publish` + its duplicate-publish catcher | `page_cache.emp:370` | **as-is** |
| `PageCache_FreeFrame` (B&R rollback twin) | `page_cache.emp:333` | **as-is** |
| `ART_PAGE_FLAG_PINNED` / `PF_PINNED` for the `band_reserve` frames | `constants.emp:266`, `page_cache.emp:412` | **as-is** (§3c) |
| `PageCache_Audit` (bijectivity + orphan/refcount recount) | `page_cache.emp:983` | **as-is, plus one new check** (§8 G3) |
| `PageIn_Flush` NOT called at teleport rebases | `page_in.emp:600`, §9.7 "Cancel/flush" | **as-is and still correct** — BG page identity is position-independent too |

### 4c. Needs work — also named

| item | change | est. |
|---|---|---|
| `PAGE_FRAMES_MAX` 15 → 23 | sizes `Page_Frames` (8 B/record) and `Page_Audit_Scratch`. **`constants.emp:278-291` says in terms that raising this "IS a RAM-layout change and owes the full pin/goldens ritual"** — the note exists precisely so this is paid deliberately | **+64 B RAM**, plus the ritual |
| `PageCache_AllocFrame` → **arena-scoped** | a BG page must never land in an FG frame. Needs a second `Page_Free_Head` and an arena-restricted `.ev_scan` bound (the scan already walks `(PAGE_FRAMES-1)*sizeof(PageFrame)` downward — it becomes a per-arena base/limit pair). **This is the one genuine surgery in `page_cache.emp`** | ~60 B ROM, 1 B RAM |
| `PageCache_Prefetch` | FG-specific: it walks the tile-cache ahead-strip and merge-translates. BG needs its own, trivial: OR the next N map rows' bitmasks and Request the non-resident bits | ~60 B ROM, new |
| `PageCache_PatchRun_Seq` / `_Col` | **not reusable** — they patch `Tile_Cache_Nametable` from staged blocks. The BG's equivalent is a translate loop inside the row producer (read ROM layout word → page → `Page_Table` → frame → physical → OR attrs → store). Same three run hoists (`a2` map, `a3 Page_Table`, `a4 Page_Frames`) | ~120 B ROM, on top of the streamer's `Draw_BG_TileRow` |
| demand stall | `Cache_Art_Stall` and `STALL_WATCHDOG_FRAMES` belong to `Tile_Cache_Fill`. BG needs its own flag — but a BG stall is far more benign: the row is not visible yet, so the producer simply defers the row | ~40 B ROM, 2 B RAM |
| row scrub | §6b — write a departing row blank so its refcounts drop | ~40 B ROM, 2 B RAM |

**New engine code total: ~320 bytes**, on top of the sibling doc's ~350 B for the streamer
itself. That is the number that contradicts "much larger project".

### 4d. The one real contention — a single staging slot

`ART_STAGING_BUFFER_SIZE = ART_POOL_PAGE_BYTES` = one page, and §9.7 is explicit that *"a
suspended decode holds the single staging slot"* and *"No new decode starts while
`PageIn_Staging_Busy`"*. BG and FG page-ins therefore **serialize**. On OJZ this is free — §9.7
records that OJZ's FG cache *"correctly degenerates to fully resident"* (10 pages, 4 pinned), so
there is no FG page traffic during play at all. On a genuinely streaming act they compete, and
the BG's `PGRQ_PREFETCH` requests will be correctly starved behind FG demand by the existing
demand-first discipline. §7 is where that matters.

---

## 5. Timing — and the direction of the advantage

### 5a. At `v_factor 3` the advantage is enormous

`CAM_MAX_Y_STEP = 16` px/frame (`constants.emp:821`). At `v_factor 3` the BG scroll advances at
most 2 px/frame, so it crosses an 8-px map row **once per 4 frames**.

A 64-tile page covers `64 / rate` map rows, at the §2d introduction rates:

```
64 / 6.22 = 10.3 rows   ->   41 frames per page boundary   (pessimistic rate)
64 / 4.42 = 14.5 rows   ->   58 frames per page boundary   (measured rate)
```

**A new BG page is needed at most once every ~41 frames**, at *sustained maximum* camera speed —
which no real traversal holds.

**Prefetch lead.** The plane holds 64 rows; the view shows 28-29. The streamer writes a row when
it enters the plane's hidden margin, ~35 rows before it is visible → at 4 frames/row that is
**~140 frames of lead**. A 2 KB ZX0 page is ~45 K cycles (§9.7's own measurement) against
~42.5 K average idle, i.e. **1-2 frames of decode**. Lead-to-cost ratio ≈ **70-140×**. The
`PAGE_PREFETCH_MAX = 2` per-frame cap is never approached.

The sibling doc's §3f made the same observation about the *nametable* and it holds a fortiori
here: the foreground has *zero* catch-up headroom by construction (`CAM_MAX_Y_STEP <=
VFILL_ROWS_PER_FRAME * 8` at equality, 16 == 2×8); the background streamer has 140 frames.

### 5b. DMA, priced

| item | bytes/frame, amortized |
|---|---|
| plane-B content rows, 132 B once per 4 frames (sibling doc §3d) | 33 |
| plane-B **scrub** rows (§6b), same rate | 33 |
| page landings, 2,048 B once per 41-58 frames | 35 – 50 |
| **BG total** | **~100 B/frame = 1.6 % of `DMA_BUDGET_NTSC` (6,144)** |

PAL is 11,648 and strictly roomier; NTSC is the binding case.

### 5c. Where the advantage disappears — five cases

**(1) `v_factor 0` / 1:1 background — Sky Sanctuary's own case. This is the sharp one.**

At 1:1 the BG moves 16 px/frame = **2 map rows/frame**. Then:

```
map height required   = full act height = 6,144 px = 768 rows
authored tiles        ~ 320 + 4.42*(768-64)  =  3,431   (~54 pages)
page boundary every   = 10.3 rows / 2 rows-per-frame  =  ~5 frames
prefetch lead         = 35 rows / 2 rows-per-frame    =  ~17 frames   (was 140)
DMA: page landings    = 2048 / 5      =  410 B/frame
     content rows     = 2 * 132       =  264 B/frame
     scrub rows       = 2 * 132       =  264 B/frame
                                        ---------------
                                        ~940 B/frame  =  15 % of the NTSC budget
```

17 frames of lead against a 1-2 frame decode is still workable **in isolation**, but this is also
precisely the regime where the foreground is streaming hardest, and §4d's single staging slot
serializes them. **At `v_factor 0` the mechanism is no longer free**; it needs its own
conversation about page size, and possibly a second staging slot. It is not a blocker for what
he asked (OJZ at `v_factor 3`), but a design that quietly assumed `v_factor ≥ 3` would be a
design with a hole, so: **stated, bounded, and gated (§8 G2).**

**(2) Teleport — the one that decides parcel count.**

At `v_factor 3` a `$1000` (4,096 px) vertical shift is **512 px of background = 64 rows = exactly
one whole plane**. `bg.emp`'s closing comment is why teleports are free today:

> *"they are pure coordinate rebases — world coordinates, plane mapping (mod 64) and scroll
> (mod 512) are all invariant under the $1000px shift, so a redraw would write byte-identical
> content (`docs/research/teleport-rebase.md`)."*

Under a tall map the **scroll** stays invariant and the **content** does not — the sibling doc
already flagged this for streaming alone. Paging adds a second layer: the entire resident working
set turns over at once. Note carefully what does *not* break: **page identity remains
position-independent**, so §9.7's rule that `PageIn_Flush` is *"NOT [called] at pure teleport
rebases"* stays correct and needs no change. What changes is the miss storm:

```
without pre-arm:  8 KB plane repaint (the existing 3-4 frame Section_RedrawPlanes storm)
                + up to 5 demand page decodes at 1-2 frames each
                = 8-13 frames  ->  a visible ~0.2 s hitch
with pre-arm:     enqueue the destination window's pages as PGRQ_BULK when the teleport
                  is ARMED (destinations are static level data), so the repaint finds them
                  resident = 3-4 frames, i.e. today's cost
```

The pre-arm is ~40 bytes and reuses `PGRQ_BULK`, which exists for exactly this shape (the init
bulk load: *"non-speculative (D3-gate-exempt) but still evictable"*). **With it this stays one
parcel's worth of work; without it, it is two.**

**(3) Scene switch.** A scene change can move `v_factor` / `v_center` / `v_offset`, which
relocates the BG window arbitrarily. Same storm as (2) but **not pre-armable** — scene switches
are not scheduled ahead. Bound it at build time: an act declaring a tall BG map must have all
reachable scenes agree on the vertical mapping, or accept the storm. `SceneRegistry_CapsFolded`
already folds capabilities build-fatally across that seam, so the shape exists.

**(4) `v_factor 15` — the eighteen locked OJZ scenes.** The BG never scrolls, the window never
moves, pages land at level init and are never evicted. **Zero traffic, and no guard may fire on
them** — that is the negative control for every gate in §8.

**(5) NOT IN THE BRIEF'S LIST, and it is the subtle one: BG per-column V-scroll.**

`parallax.emp:679-915` sets VDP register `$0B` bit 2 — *"bit 2 = VScroll mode: 0 whole-plane,
1 per-column"* — whenever `pcfg_v_deform_table_bg` is non-null. `engine/structs.emp:214` types
that field as a *"ROM ptr to 256-byte signed BG V-column"*, and `parallax.emp:1650-1657` applies
`offset = sample >> pcfg_v_deform_shift_bg`.

The tables are `[i8; 256]` (`scene_registry.emp:700,705`), so the amplitude is up to **±127 px =
±16 rows** at the shipped `shift: 0`. With a BG v-deform live, **different 2-cell columns show
different map rows**, and the refcounted window widens from 29 rows to **~61** — nearly the whole
plane. The measured working set then goes from 268 tiles to 320, which is the entire dynamic
budget with nothing left for an in-flight page.

**The shipped art dodges this by coincidence, and the coincidence should be made an invariant.**
All six v-deform scenes are locked:

```
Scene_Rocking_Slow / Rocking / Rocking_Fast          v_factor: 15   (ojz_scenes.emp:355)
Scene_Perspective_Subtle / _ / _Dramatic             v_factor: 15   (ojz_scenes.emp:402)
```

and both `v_factor: 3` scenes (`Scene_OJZ_Default`, `Scene_OJZ_Underwater`) attach **no** BG
v-deform — they set only `deform_bg` (horizontal). Nothing structural forbids a scene with both.
Hence gate G2 in §8.

---

## 6. The design, in the shape it would actually be built

### 6a. Build side

1. `tools/png_to_bg_override.py` learns a per-act `MAP_H` (its `PLANE_H = 64` becomes the act's
   row count) and its *"unique flip-canonical tiles ≤ `BG_STATIC_TILE_BUDGET`"* gate moves from
   the whole image to **the worst window** (§8 G1).
2. `tools/inject_editor_bg.py` spatially-orders the BG pool by first-use row — the same
   `order_pool_spatially` idea the FG uses — splits it into 64-tile pages, and emits (a) the
   `PageManifest` entries, (b) the layout with **logical** tile ids, (c) the per-row page bitmask.
   It stops transposing to column-major: the sibling doc's §3d already argues row-major is a
   strict simplification for a row producer, and here it is required, because the translate loop
   wants a row's 64 words contiguous.
3. `BG_LAYOUT_SIZE` — today a `pub` contract typing `act_assets.emp`'s embed so a wrong-sized
   blob is a build error — becomes per-act. **The build-time catch must survive** (`bg.emp`'s
   own note: *"so a wrong-sized blob is an `array length mismatch` at build time rather than a
   transposed background at runtime"*).

### 6b. Runtime side — the one design move worth naming

The streamer writes a row when it enters the plane's hidden margin. But a row that has left the
*view* still sits in the plane for ~35 more rows, and its cells still reference its tiles — so
under a naive refcount the resident window is the whole 64-row plane (320 tiles, zero headroom).

**Fix: write each row twice — once with content just before it enters view, once blanked just
after it leaves.** Then:

- the refcounted window is the visible 29 rows (plus any v-deform margin, §5c-5), not 64;
- the working set is the measured 268 worst / 167 mean, not 320;
- the cost is one extra 132-byte plane row per transition — the 33 B/frame second line in §5b,
  taking BG DMA from ~67 to ~100 B/frame. **1.6 % of the NTSC budget.**
- direction reversal is handled by a ±4-row deadband so an oscillating camera cannot thrash the
  scrub; there are 35 rows of hidden plane to absorb it, so no artifact is reachable.

Every section map's entry 0 is generator-guaranteed blank (§9.7: *"the shared zero staged block
reads as blank through any map"*), so "blank" costs no tile.

---

## 7. Costs and what it buys

| axis | cost |
|---|---|
| **ROM, engine** | ~320 B new code (§4c), on top of the streamer's ~350 B |
| **ROM, data (2,816-px act)** | layout 64 × 352 × 2 = **45,056 B** (vs 8,192 today) — this is the *streamer's* cost, not paging's; tile art ~1,600-2,100 tiles × 32 = **51-67 KB raw**, ZX0'd to roughly 25-35 KB; manifest 8 B/page ≈ 200 B; per-row page bitmask 2 B/row = 704 B. **~75-85 KB/act** |
| **RAM** | +64 B (`Page_Frames` at `PAGE_FRAMES_MAX` 23) + ~11 B (second free head, BG edge/scrub trackers, stall flag). **~75 B — and it is a RAM-LAYOUT change owing the pin/goldens ritual** (`constants.emp:278-291` says so explicitly) |
| **VRAM** | **zero new.** The existing 448 tiles are re-read as frames 16-22 |
| **DMA/frame** | **~100 B, 1.6 % of NTSC**, at `v_factor 3`. ~940 B / 15 % at `v_factor 0` (§5c-1) |
| **Cycles** | the row translate loop is ~64 words × ~100 cyc (the F1-measured collapsed row-path cost) ≈ 6.4 K cycles, once per 4 frames = **~1.3 % of a frame amortized** |
| **What he'd see** | the background can be as tall as he wants. Sky-Sanctuary-class art becomes reachable at OJZ's full `v_factor 3` depth |

### Does this dissolve the 448 as a limit on *authored* background art? **Yes.**

The new binding limits, in the order they would bite:

1. **~320 distinct tiles in any 29-row (232 px) window** — the residency budget after
   `band_reserve`. Measured worst on the shipped art: **268**. This is the real new ceiling, and
   the important thing about it is that it is *local*: it does not care how tall the picture is.
2. **ROM** — ~75-85 KB per act for a 2,816-px background (§7 table). The layout blob dominates.
3. **The 11-bit nametable field (2,047).** §2d puts a 2,816-px map at 1,592-2,111 *logical*
   tiles, i.e. **brushing 2,047 at the loose end of the extrapolation.** Solved the FG's way
   (per-band local index spaces, exactly what `Cache_Cur_LocalMap` is for) or by capping the map.
   Worth flagging now because it is the wall *behind* the wall he is asking about.
4. `PAGE_TABLE_MAX = 256` pages — a 2,816-px map is ~25 BG pages against OJZ's 10 FG pages.
   Not binding, not close.

---

## 8. Gates this would owe

**G1 — `bg_window_budget`.** For each act with a declared BG map height: over all windows of
`W` consecutive map rows, `max |distinct tile ids|` ≤ `BG_TILE_CAPACITY − band_reserve` (= 320
today, both read from `tools/vram_map.py`, itself generated from `games/sonic4/vram.toml` — one
authority, no restated literal). `W` is **derived**, not pinned:
`W = 29 + 2*ceil(max_bg_vdeform_px / 8)` where the deform amplitude comes from the act's scenes.
*Runner:* `tools/test_bg_emit.py`, the build-fatal pytest lane, beside the existing
`TestBgAnimBandCeiling`; with a comptime `ensure` in the generated act descriptor as the ROM-side
backstop. *Red-first:* author one window with 350 unique tiles. *Loud, not green:* an act that
declares a tall map but emits no per-row bitmask must **FAIL**, not skip — this is the class of
gate that most often ends up measuring nothing. **Must run with `PYTHONDONTWRITEBYTECODE=1` and
a cleared `__pycache__`** (the recorded false-green defect: a same-length mutation in the same
second was served from cache).

**G2 — `bg_vdeform_vs_vfactor`.** A comptime `ensure`: no scene in an act with a tall BG map may
carry both `v_factor < 15` and a non-null `pcfg_v_deform_table_bg` unless its amplitude is
declared and folded into G1's `W`. *Red-first:* attach `DeformTable_Rocking` to
`Scene_OJZ_Default`. *Negative control:* must **not** fire on the six shipped deform scenes
(`Rocking` ×3, `Perspective` ×3), all of which are `v_factor: 15`, nor on the eighteen locked
OJZ scenes. *Runner:* the sigil build, the named runner for every other `ensure` in that file.

**G3 — `bg_frame_arena_disjoint`.** Extend `PageCache_Audit` (`page_cache.emp:983`) with one
check: every resident page's frame lies in that page's declared arena (FG 0-13, BG 16-22).
*Red-first:* hand-corrupt one `Page_Table` entry. *Loud:* it `raise_error`s like every other
audit invariant rather than returning a status. This is the check that catches the §4c
arena-scoped-`AllocFrame` surgery going wrong, and it is worth having because the failure mode
without it is a background tile appearing in the foreground.

---

## 9. TAGs for the controller — runtime confirmation this lane may not do

**T1 — working set.** Traverse OJZ act 1 top to bottom with a tall BG resident and sample
`Page_Frames[16..22].pf_refcount` + `Page_Table` each frame.
*Prediction:* at most **5** BG frames non-zero at any instant, and zero `AllocFrame` thrash
`raise_error`s. *Falsified* if a sixth is ever needed — which would mean §2b's 268-tile worst
window understates the real one, and the whole cost picture moves.

**T2 — the prefetch lead.** Sample `Dbg_PageCache_Demands` across the same traverse.
*Prediction:* BG **demand** misses == 0 at `v_factor 3` — every BG page-in should be prefetch.
*Falsified* by any non-zero count, which would falsify the 140-frame lead in §5a directly.

**T3 — teleport.** Fire a vertical `$1000` teleport with a tall BG resident, with and without
the `PGRQ_BULK` pre-arm, and sample the `Frame_Counter` delta and `Lag_Frame_Count` across it.
*Prediction:* **8-13 frames without pre-arm, ≤4 with.** Either result is decision-relevant: it
is exactly the measurement that settles one parcel vs two (§5c-2).

**T4 — the `v_factor 0` case.** Build the stress fixture at `v_factor 0` and sample
`DMA_Budget_Remaining` at end of frame. *Prediction:* ~940 B/frame of BG consumption (§5c-1).
*Falsified upward* — above ~1,200 — means the 64-tile page is the wrong granularity for 1:1
backgrounds and the design needs a second staging slot or 32-tile BG pages.

---

## 10. Recommendation, and honest sizing

**Recommend: yes, but strictly after the streamer, and declared as a project rather than a
parcel.**

The sibling doc's *ordering* is right and its *sizing* is not. Three specific reasons it is
smaller than "a separate and much larger project" implies:

1. the frame→VRAM arithmetic **already addresses the BG region exactly** — 448 = 7 × 64, frame
   16 = `$8000`, frame 23 = the SAT (§4a);
2. the decoder, bookmark, FIFO, manifest, staging, publish, pinning and audit are **100 %
   reused**, unchanged (§4b);
3. the BG's refcount source is a **per-row bitmask in ROM**, not a 9,600-byte RAM cache —
   three orders of magnitude cheaper than the foreground's (§3b).

**~320 bytes of new engine code.** And one reason it is *not* smaller than the sibling doc's
ordering claim: without row streaming nothing is ever evictable, so this can never be taken
first (§3a).

**Proposed shape — 4 aeon parcels + 1 tools parcel, behind the streamer:**

| | parcel |
|---|---|
| P0 | **the sibling doc's streamer** (`Draw_BG_TileRow` + scheduler) — prerequisite, already recommended there |
| P1 | arena-scoped frames: `PAGE_FRAMES_MAX` 15→23, second free head, arena-restricted `.ev_scan`, G3. **Owes the pin/goldens ritual** |
| P2 | the row producer's logical→physical translate + per-row bitmask refcounting + the row scrub (§6b) |
| P3 | BG prefetch + the teleport `PGRQ_BULK` pre-arm + G2 |
| T1 | `png_to_bg_override.py` / `inject_editor_bg.py`: per-act `MAP_H`, spatial ordering, paging, manifest + bitmask emission, row-major, G1 |

plus the aurora-side work the sibling doc already priced (canvas strip viewport, band coordinates
in map space, the live preview's moving-window model) and the art pass, which remains the
largest single item and is the owner's call.

**Sequencing note.** This does not conflict with `slower` (`v_factor 4`) or with the streamer;
each is a strictly weaker stopgap for the same want, and taking them in order costs nothing.

---

## 11. Open, with reasons

- **BLOCKED — no build was run.** A certification run was in flight against the shared binaries.
  Nothing above depends on one: every figure comes from source, generated artifacts, or the
  shipped editor JSON. A build would settle only the true byte delta of the ~320 B, which is not
  decision-relevant.
- **Not measurable here — the worst-case *page* count for a tall map.** §2b's distinct-tile
  window figures are clean, but the page-touch figures (mean 3.67 frames per 29-row window at
  64-tile pages, mean 7.00 at 32-tile) have a max pinned at the whole pool, **because the shipped
  map is only 64 rows tall — a 29-row window in a 64-row map necessarily touches everything.**
  The mean is the honest locality signal; the max is an artifact of the short map and is *not*
  evidence about a tall one. A real worst case needs real tall art, which does not exist yet.
  Recorded so nobody quotes "max 5 of 5" as a finding.
- **Unverified — the comptime path for G2.** Same open mechanism the sibling doc recorded for its
  own gate 1: `v_factor` lives in the scene tables, not the act descriptor.
  `SceneRegistry_CapsFolded` proves a *bitmask* travels that seam; a *value* has not been proven
  to. If it cannot, fold a `SceneRegistry_MinVFactor` / `SceneRegistry_MaxBgVDeform` the same way.
- **Not costed — the art.** "Draw a 512 × 2,816 background whose every 232-px slice fits in 320
  tiles" is the real work here and it is not an engineering estimate.
- **Not examined — a second staging slot.** §5c-1 and §4d both point at it for the `v_factor 0`
  case. It is a `+2,048 B` RAM question with a scheduler change behind it, and it is out of scope
  for the height the owner actually asked about.
