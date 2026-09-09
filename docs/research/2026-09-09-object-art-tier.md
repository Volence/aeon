# The object-art tier — the third tier of aeon's VRAM story

**Status: DESIGN ONLY. No engine code, no constants moved.** Building this is a later
owner ruling.

**Date:** 2026-09-09 · **Branch:** `design/object-art-tier` · **No emulator was used.**
Anything wanting a runtime check is TAGGED `[RUNTIME]` for the controller.

**The ask, in the owner's words (2026-09-07/08):**

> "I'm just trying to think of how we can get massive dynamic levels still while having
> space for objects within our system"

> "can we add something to the region project to talk about and figure out vram space,
> and what we can do to get more of it for objects since it's all eaten by level pretty
> much"

---

## 0. The one-paragraph answer

**Build a per-section object-art residency pool with a demand loader, and do NOT build it
out of the foreground page cache.** Object art in this engine is *uncompressed ROM*, so a
load is one ROM→VRAM DMA and needs no decompressor, no staging buffer and no resumable
decode — the three most expensive things the FG cache owns. The FG cache's refcount is
defined over *nametable words*, which objects do not have, and its VRAM addressing is
hard-wired to base 0 with a 64-tile quantum, which a 4-tile sparkle cannot use. Reuse its
*shape* (frame table, refcount, age eviction, demand + prefetch) and none of its *code*.
The authoring question is nearly answered already: `sec_type_table` is a generated,
placement-derived enumeration of exactly the `ObjDef`s a section can spawn, and it is the
manifest. The binding constraint is not VRAM, it is the **DMA window**: NTSC residual
after the mandatory riders is 2,944 bytes/frame and the current worst frame is already
32 bytes over it.

**The precedent to build against is Batman & Robin, not any Sonic game.** Of the nine trees
surveyed (§4), B&R is the only one that ships the exact mechanism this needs — a refcounted,
evicting cache over 64 fixed 16-tile slots with lazy reclaim and a four-way rollback guard —
and **none of the nine solved aeon's actual problem**, because every one of them kept its
loading unit and its spawning unit identical. That is the thing this design changes, and it
is why the classics constrain it less than they appear to.

---

## 1. What is actually true in this tree today

Every claim in this section was re-derived on 2026-09-09 at this branch's base. Where a
command's output is the evidence, the command is named.

### 1.1 The map, and the one free tile

`python3 tools/gen_vram_map.py --game sonic4` → `gen_vram_map: sonic4 OK — 23 regions, 1
free tiles`, exit 0, and `git status --short` clean afterwards — so the committed
`docs/generated/vram-map-sonic4.md` **is** current and the table below is not a memory
quote. Full coverage of tiles 0..2047 is enforced by that tool, so "full" means fully
*accounted for*.

The object-and-character regions, read off the generated table:

| tiles | region | lifetime | what it is |
|---|---|---|---|
| 896-911 | `dust_puff` | act | 16 — all four puff frames live at once |
| 912-923 | `dust_spindash` | act | 12 — the charge-dust DPLC target |
| 924-927 | `ring_sparkle` | act | 4 — one 2×2 piece, four flip orientations |
| 928-956 | `insta_shield` | act | 29 — Sonic's flash, DPLC-streamed into a fixed window |
| 957-958 | `debug_preset_readout` | mode | 2 — reserved in every shape |
| **959** | **FREE** | — | **the whole map's only free tile** |
| 960-991 | `character_window` | act | 32 — THE character DPLC window (one character resident) |
| 992-999 | `test_obj` | mode | 8 — test squares |
| 1000-1015 | `ring_placeholder` | act | 16 — ring art |
| 1016-1019 | `test_marker` | mode | 4 |
| 1020-1023 | `debug_lab_name` | mode | 4 |
| 1448-1471 | `spring` | act | 24 — **scavenged from `bg_region`'s reserve** |
| 1492-1500 | `tails_appendage` | act | 9 |
| 1501-1503 | `debug_bganim_tag` | mode | 3 |
| 1532-1535 | `debug_raster_tag` | mode | 4 |

The 896..1023 neighbourhood is 128 tiles and is fully spent. `spring` is not in it because
it did not fit: it took 24 tiles out of `bg_region`'s unwritten `band_reserve` (400 → 388 →
376, reserve 80 → 56), which is what `docs/DEFERRED_WORK.md` "VRAM-NEIGHBOURHOOD — objects
have no room" was booked for. **56 reserve tiles remain and they are the cheapest scavenge
for the next object.** That trick has two more objects in it, maybe three.

### 1.2 Object art residency: verified, and worse than "no region concept"

There is **no engine object-art loader at all.** Object art reaches VRAM from a
hand-written stanza in the *game's test-scene init routine*.

`grep -rn "jbsr *QueueDMA\|jbra *QueueDMA\|bsr.*QueueDMA" --include='*.emp' engine games`
returns 17 sites, complete. Four of them are the object-art loads, consecutive, in
`games/sonic4/test/ojz_scroll_test.emp:637,647,658,668`:

```
        move.l  #Art_Spring, d1
        move.w  #vram_bytes(VRAM_SPRING), d2
        move.w  #SPRING_ART_LEN, d3
        jbsr    QueueDMA_Critical @discards(dropped)
```

They sit in the level-init block, **display off**, immediately after `Level_LoadArt` — which
is itself display-blanked and *raises* the window budget to
`DMA_BUDGET_BLANKED_INIT = ART_STAGING_BUFFER_SIZE + DMA_BUDGET_NTSC` = 8,192 for the bulk
load, restoring the active-display budget before it returns
(`engine/level/load_art.emp:46-50,105-109`). **So the always-resident floor set is loaded
under an 8 KB window with the display off and is never a bandwidth problem** — only the
streamed set in §5.3 is. Adding
an object type today means **hand-adding a fifth stanza to a test scene**. That is not a
"resident policy" — it is the absence of one. Every "RESIDENT for the whole act" comment
in `vram.toml`, `dust_data.emp` and `test_solid.emp` is describing this block.

Three consequences worth stating separately, because they change the design:

1. **Object art is stored RAW in ROM.** `test_solid.emp:860` is
   `const _art_spring = embed(".../art_spring.bin")` and the DMA source is `#Art_Spring`
   directly. Same for `Art_Dust`, `Art_RingSparkle`, `TestArt`. **A load is one
   ROM→VRAM DMA.** No ZX0, no S4LZ, no staging buffer, no resumable decode. This is the
   single biggest difference from the FG tier and it makes the object tier *much* cheaper
   to build than the thing next door to it.
2. **The `art_tile` word is baked at compile time.** `objdef(... art: vram_art(VRAM_SPRING))`
   is a `comptime fn` result stored in the `ObjDef` at `+$0C`, and `Load_Object`
   (`engine/objects/load_object.emp:44-50`) burst-copies the template's `$0A-$21` image
   into the SST, which carries `art_tile` at Sst `+$14` (`engine/objects/sst.emp:44`,
   correspondence `ensure`d at `:166`). A dynamic tier must **patch that word after the
   burst copy** from a runtime residency table. That is one extra write on the spawn path
   and it is the whole runtime integration.
3. **DPLC is the only streaming path objects have, and it streams into a fixed window.**
   `perform_dplc` (`engine/objects/dplc.emp:373,388`) enqueues per-frame entries at
   Important/Deferrable into a per-object `cd_vrambase` that is a compile-time constant.
   DPLC solves "which frames of *this* object are live"; it does not solve "which objects
   are live".

### 1.3 The region identity layer is not built — but the section one is, and it is enough

`grep -rn "Region_Cur\|rg_plc\|region_rect\|RegionRect\|struct Region" --include='*.emp'
--include='*.py' engine games tools` returns **nothing** (plain grep, no `2>/dev/null`; it
would have printed a `path:line:` row for any hit). Painted regions are a design
(`empyrean/docs/research/2026-08-29-painted-regions-study/`), not a runtime key. **A design
that requires regions to exist cannot be built today.**

It does not have to. The engine already ships a per-section object identity layer, and it
is *exactly* the manifest this tier needs:

- `Sec.sec_type_table` (`engine/structs.emp:152`) — `dc.b count, pad; dc.l ObjDef × N`.
- Generated from placement by `tools/ojz_entity_gen.py:290-301`. Nine live tables in
  `games/sonic4/data/generated/ojz/act1/entity_data.emp:36-76`, e.g.
  `OJZ_Sec0_TypeTable: ObjTypeTable2 = { count: 2, t0: ObjDef_Spring, t1: ObjDef_Solid }`.
- Read at runtime: cached per tracked section at `entity_window.emp:653`, then indexed at
  `:1263` by the placement word's 5-bit type field (`OEF_TYPE_SHIFT = 8`,
  `OEF_TYPE_MASK = $1F`) to produce the `ObjDef` pointer `Load_Object` is called with.
- Ceiling: **32 distinct types per section**, enforced at generation
  (`ojz_entity_gen.py:191-194`).

So "which objects belong to which area" is already **derived from what is actually placed
there**, already generated, already resident in ROM, and already loaded into the scan
state one section at a time. The authoring question in §4.5 is therefore not open in the
way it looks.

### 1.4 The spatial and temporal budget the loader gets

- `SECTION_SIZE = $0800` = 2048 px (`constants.emp:319`).
- `MAX_TRACKED_SECTIONS = 4` — a 2×2 camera envelope (`:1119`). **Up to four sections'
  entity lists are live simultaneously**, which is the edge problem in §4.2.
- `ENTITY_LOAD_BUFFER = $180` = 384 px horizontally, `ENTITY_LOAD_BUFFER_Y = $100` = 256 px
  vertically (`:1120,1122`); despawn hysteresis 512 / 384 px (`:1121,1123`).
- `CAM_MAX_X_STEP = 16` px/frame (`engine/level/camera.emp:26`), `CAM_MAX_Y_STEP = 16`
  (`constants.emp:1049`).

**Derived lead time between "an object spawns" and "it can be on screen":**
384 / 16 = **24 frames** horizontally, 256 / 16 = **16 frames** vertically. Sixteen frames
is the worst case and it is the latency budget for a demand load. It is generous — the
spring is 768 bytes, one DMA.

The *section crossing* hook (`Parallax_CheckBoundary`, `engine/level/parallax.emp:1165`,
called every frame from `ojz_scroll_test.emp:1224`) is **not** usable as the load trigger:
it is edge-triggered on the camera *centre* crossing an edge, by which time the new
section occupies half the screen. The entity window's 384/256 px envelope is the earlier
signal and the correct one.

Concurrency ceiling: `NUM_DYNAMIC = 40` object slots (`constants.emp:92`). At most 40 live
dynamic objects, so at most 40 distinct live types — in practice far fewer.

### 1.5 The DMA window, priced against the *remaining* headroom

`ENGINE_ARCHITECTURE.md:1187` and `engine/system/vblank.emp:169-205` agree, and the code is
the authority: `VInt_Level` seeds `DMA_Budget_Remaining` from `DMA_Budget_Default`, then
**charges** it twice before `Process_DMA_Important`/`_Deferrable` ever run —
`sub.w Plane_Buffer_Ptr, DMA_Budget_Remaining` for the plane drain (`:175-176`), then a walk
of the Critical queue summing entry lengths and subtracting them (`:181-200`), floored at 0.

`tools/dma_defer_headroom_baseline.json`, committed, derives every input from source and
cross-checks it against the assembled listing (route 1 = declared, route 2 = assembled;
disagreement is `Unmeasurable`, not a silent preference). NTSC:

| quantity | bytes | where it comes from |
|---|---|---|
| `DMA_BUDGET_NTSC` | 6,144 | `constants.emp:670` |
| − plane drain charge (max) | 1,536 | `PLANE_BUFFER_SIZE` |
| − Critical charge (max) | 1,664 | hscroll 896 + SAT 640 + 4×32 palette |
| **= residual for Important + Deferrable** | **2,944** | |
| current demand, solo character | 2,976 | page landing 2,048 + Sonic peak DPLC 928 |
| current demand, Sonic + Tails | 4,032 | + Tails 768 + tail 288 |
| **deficit today, solo** | **+32** | already over |
| **deficit today, duo** | **+1,088** | already over |

**This is the finding that constrains the whole design.** On NTSC the worst frame is
*already* 32 bytes over the window with one character, and 1,088 over with two. There is no
spare bandwidth to hand an object loader in the worst frame. PAL residual is 8,448 and has
5.4 KB to spare, so this is an NTSC-only constraint — which means it is the binding one.

What that does *not* mean: the worst frame is not the typical frame. The 2,048-byte page
landing only occurs on frames where `PageIn_Process` completes a page, and OJZ act 1 is
fully resident after init (§1.6), so on the shipped act that term is **zero in steady
state**. The honest statement: **object-art DMA must be Deferrable, must be sized so it
never needs to complete in a specific frame, and must be measured on an act where the FG
cache is actually streaming, not on OJZ act 1.**

### 1.6 Where the tiles would come from

The `VRAM-NEIGHBOURHOOD` booking names four levers. Two of them are now measurable:

- **`fg_art_pool` = 768 tiles = 12 frames of 64** (`POOL_TILE_CEILING = 768`,
  `PAGE_FRAMES = POOL_TILE_CEILING / ART_POOL_PAGE_TILES`). The shipped act needs
  **`OJZ_ACT_POOL_PAGES = 10`**
  (`games/sonic4/data/generated/ojz/act1/ojz_act_pool_manifest.emp:7`) — so 640 of 768
  tiles are used and the act is fully resident (the §9.7 degenerate path). **Cutting the
  pool 768 → 640 frees exactly 128 tiles and keeps OJZ act 1 fully resident.** It also
  leaves that act *zero* eviction headroom, and `vram.toml` already records 640/10 as the
  floor "until C4-3 (the famine capacity fix) lands". So: 128 tiles are available at the
  price of the streaming margin, and the price is a known-open defect, not a theoretical
  one. **This is the largest honest lever and it is not free.**
- **`spare_nametable` = 128 tiles.** Reserved because it is the map's only $2000-aligned
  run and therefore the only address a plane/window base register could still be pointed
  at. Spending it on objects spends an *address*, not tiles, and tiles are not the scarce
  thing there. Recommend leaving it.
- **13 tiles of debug tags**, reserved in every shape including release. Real, small.
- **`test_obj` 8 + `test_marker` 4 = 12 tiles** of test scaffolding, which retire with the
  scene.
- **`bg_region`'s remaining 56 reserve tiles** — the scavenge route, and the one the
  booking says to stop using.

**The always-resident floor** (§4.4), read off the same table: `character_window` 32 +
`ring_placeholder` 16 + `ring_sparkle` 4 + `dust_puff` 16 + `dust_spindash` 12 +
`insta_shield` 29 = **109 tiles**, plus `tails_appendage` 9 = **118** with Tails in the
roster. There is **no HUD** in this engine — the object listings under `engine/objects/`
and `games/sonic4/objects/` contain no HUD module and the only `HUD` string in `.emp`
source is a comment on `Ring_Counter` (`engine/ram.emp:1063`) — so the floor above is
missing a real cost that a shipped game will add.

⚠ **Documentation drift found while measuring, not fixed here (design-only lane):**
`games/sonic4/objects/test_solid.emp:781` and `ojz_scroll_test.emp:660` both say the spring
is "12 tiles"; `SPRING_ART_LEN = 24 * TILE_SIZE` and `vram.toml` says 24. The DMA uses the
constant, so behaviour is right and the comments are stale by one sheet.

---

## 2. The reuse verdict on the foreground page cache

**Verdict: reuse the SHAPE, reuse none of the CODE. The object tier is a second, much
smaller mechanism — not a second instance of the page cache, and not a client of the same
pool.**

The brief is right that the FG cache solves a strictly harder problem. That is exactly why
it is the wrong body of code: nearly everything that makes it hard is a cost the object
tier does not have to pay, and three of its load-bearing assumptions are false for objects.

### 2.1 What the FG cache actually is (read, not assumed)

`engine/level/page_cache.emp` + `engine/level/page_in.emp`, 1,815 lines together:

- `PageCache_Request` / `AllocFrame` / `FreeFrame` / `Publish` / `Prefetch` /
  `ResetRefcounts` / `Audit`, over `Page_Table` (page id → frame) and
  `Page_Frames[]` (`PageFrame` = 8 B: `pf_page`, `pf_refcount`, `pf_stamp`, `pf_next`,
  `pf_flags`).
- `AllocFrame` (`:231`): free list first; else **the oldest `PF_EVICTABLE` frame by an
  O(PAGE_FRAMES) `pf_stamp` age scan**; else THRASH (DEBUG `raise_error`, release returns
  `PAGE_NOT_RESIDENT` and the caller re-queues).
- `Prefetch` (`:743`): reads the *tile-cache* leading-edge signals
  `Cache_Pfx_Row_Target` / `Cache_Pfx_Col_Target`, probes staged **blocks**, translates
  their **local nametable words** through the section map, and requests the pages those
  words reference.
- `page_in.emp`: a resumable ZX0 decode sliced across VBlank idle time into a **singleton
  2,048-byte `Art_Staging_Buffer`** (`engine/ram.emp:307`), then a landing DMA at
  Important priority (`:519`).

### 2.2 The three assumptions that are false for objects

1. **The refcount is defined over nametable words.** The module header states the safety
   invariant in as many words: *"`pf_refcount` counts nametable words currently in the tile
   cache that reference the frame"*, and `PageCache_Audit` proves it by recomputing every
   refcount from the whole nametable. **Objects have no nametable words.** Their tile
   references live in `Sst.art_tile` and are re-emitted into the SAT every frame by the
   sprite builder. An object refcount is a count of *live SST slots* — a different quantity,
   computed from a different structure, at a different time. Nothing in `page_cache.emp` can
   compute it, and `PageCache_Audit` — the machine check that makes the FG invariant
   trustworthy — would have to be replaced wholesale.

2. **The VRAM address is hard-wired to base 0 with a 64-tile quantum.** `page_in.emp:253`
   computes the landing destination as `frame << ART_POOL_PAGE_BYTES_SHIFT` (frame × 2048),
   and `page_cache.emp:526` patches physical tiles as `frame << PAGE_FRAME_TILE_SHIFT`
   (frame × 64). Both are *shifts*, chosen deliberately over a multiply. There is no base
   term. Pointing this machinery at a pool that does not start at tile 0 means adding a base
   to two hot paths and giving up the shift on at least one. And the quantum is wrong by an
   order of magnitude: `ring_sparkle` is **4** tiles, `tails_appendage` 9, `dust_spindash`
   12, `dust_puff` 16, `spring` 24, `insta_shield` 29. A 64-tile frame holding a 4-tile
   sparkle wastes 94% of itself. **This is the argument that kills "a client of the same
   pool" outright**, not just "a second instance": sharing the pool means sharing the
   quantum.

3. **The expensive half of `page_in` is decompression, and object art is not compressed.**
   The resumable ZX0 decoder, the supervisor bookmark, the staging buffer, the two-stage
   staging→VRAM landing — all of it exists because a page arrives as ZX0 and cannot be
   decoded in one VBlank. An object load is `move.l #Art_Spring, d1` + `QueueDMA`. The
   staging buffer is a *singleton*, so routing object art through `page_in` would also make
   objects and level art contend for it. **The tier that would be reused is ~80% machinery
   for a problem the object tier does not have.**

### 2.3 What the object tier *does* get for free, and it is a lot

- **Relocation is a single word write.** Every sprite piece's tile attribute is added to
  `Sst.art_tile` at emit time — `move.w (a3)+, d0` / `add.w d6, d0`
  (`engine/objects/sprites.emp:654,661,669,675`; d6 is loaded from `Sst.art_tile` at
  `:361`/`:460`). Mappings are fully position-independent. Moving an object's art base costs
  **one `move.w`**.
- **The spawn hook already exists and is one instruction wide.** `Load_Object` already
  burst-copies then patches per-placement fields; the residency patch is another line in the
  same block.
- **The manifest already exists** (§1.3).
- **The trigger already exists** — the entity window's 384/256 px envelope, with 16-24
  frames of lead.

### 2.4 So what should be copied

The *design*, at a fraction of the size: a small slot table with a refcount, an age stamp
and a free list; demand-first with bounded speculative prefetch; a DEBUG audit that
recomputes the refcount from the authoritative structure (here: a walk of the live object
slots, which `Dynamic_Live` already maintains). Approximately `PageCache_Request` +
`AllocFrame` + `FreeFrame` + a refcount pair — with `Publish`, `Prefetch`, the ZX0 path,
the staging buffer and the nametable patch runs all absent. **Call it 150-250 lines against
the FG tier's 1,815.**

A design that reinvented the cache next door would be worse. A design that forced 4-tile
sparkles through a 64-tile-quantised, base-0, nametable-refcounted, ZX0-staged pipeline
would be worse than both.

---

## 3. The hard problems

### 3.1 An object spawns and its art is not resident

**The only genuinely new failure mode, and the answer has to be a policy, not a mechanism.**
Four options, and the classics do not agree (§5):

| policy | what happens | cost |
|---|---|---|
| **(a) Refuse the spawn** | `Load_Object` returns failure; the `EntityLoaded` bit is not set, so the **re-scan retries next frame** — this path already exists at `entity_window.emp:1270` (`bne .gated` on alloc failure, "no bit, re-scan retries") | an object can be late by the load latency; at 16-24 frames of lead it should never be visibly late |
| **(b) Spawn invisible** | object exists and runs logic, rendering suppressed until art lands | correct physics, popping art; needs a per-object "art pending" state |
| **(c) Spawn with garbage art** | what happens today if a stanza is forgotten | unacceptable |
| **(d) Prevent it structurally** | the loader guarantees a section's whole set is resident before the entity window ever scans that section | needs the set to *fit*, which §3.3 says it may not |

**Recommendation: (a), because the mechanism is already built.** The retry path is the same
one that handles a full object pool, it is proven, and it converts "art missing" into
"object appears a few frames later" — at 16 frames of lead, invisible. Keep (d) as the
*goal* (prefetch should make (a) never fire) and add a DEBUG counter so a fired retry is a
measurable defect rather than a silent stutter.

**⚠ REVISED after §4.4 — there are TWO paths here, not one, and I originally saw only one.**
Batman & Robin and Vectorman both handle this case, and both handle a case (a) does not
cover: an object **already alive** whose *animation* advances to a frame whose art is not
resident. There is no "refuse the spawn" available there — the object exists and is on
screen. Their answer:

- **B&R reverts to the previously-resident art ID** (`move.w d7, $20(a6)`) and re-renders the
  old frame, retrying next frame (`objects.asm:4167-4180`).
- **Vectorman rolls the whole queue-entry list back and returns 0**; the caller commits
  nothing and renders from still-resident art (`:6326-6332`, `:7438-7445`).

Both are the same idea: **never partially commit, and always have something valid to draw.**
So the policy is a pair —

| case | policy |
|---|---|
| **spawn**, no art resident, nothing previously drawn | **(a) refuse + retry**, via `entity_window`'s existing path |
| **live object**, animation advances past resident art | **revert to the last resident art and retry** — B&R's answer |

**And the guard should be four-way with rollback, not the two-state I proposed in
§3.6(iii).** B&R checks *all* of: per-frame DMA budget, free queue slots, free VRAM slots,
free cache records — and **restores every counter** on any failure. Adopt that shape; it is
the difference between "usually correct" and "cannot be wrong".

### 3.2 Objects near an edge — up to four sections live at once

`MAX_TRACKED_SECTIONS = 4` is a 2×2 camera envelope, so **a pool holding "one section's
set" is wrong at every edge by construction**, exactly as the brief says. Not a corner case:
the camera is inside a 2×2 envelope most of the time.

**The resolution is that the pool is not keyed by section at all.** It is keyed by **art
blob**, and section membership is only an input to *pinning*:

- The pool holds N art blobs, each with **two independent counters**: a **refcount** =
  live SST slots whose `art_tile` points into it, and a **pin count** = tracked sections
  whose type table names it.
- Entering a section increments pins for its blobs; leaving decrements. Up to four sections
  pin simultaneously, and that is *correct*, not a bug — those are exactly the objects that
  can spawn.
- A blob is evictable only when refcount 0 **and** pin count 0 — the same two-condition rule
  the FG cache uses (`refcount == 0 && !PF_PINNED`), which is why the shape is worth copying.

**The number this makes concrete:** the working set is the **union of up to four adjacent
sections' blob sets**, not one section's. §4 prices it.

### 3.3 Fragmentation

Fixed windows do not fragment; a variable-size pool does. Blob sizes measured above run
4, 9, 12, 16, 24, 29 — no common factor, and a free-run allocator over them will fragment.

**Recommendation: fixed-size slots, sized by a build-time histogram, with a comptime
`ensure` on every blob.** Two or three slot classes at most (e.g. small = 16 tiles, large =
32), with class sizes derived from the actual art by the same generator that writes the type
tables. This trades bounded internal waste for zero external fragmentation and an O(1)
allocator, and it matches how the FG tier already solves the same problem (fixed 64-tile
frames). The waste is *known at build time*, which is the property a free-run allocator
cannot offer.

**⚠ REVISED after §4.4 — treat "two classes" as one arm of a fork, not as settled.** Batman &
Robin uses **a single 16-tile class** across 64 slots and allocates **multi-slot runs** for
larger art, absorbing the resulting fragmentation with a forced-eviction walk down its reclaim
list (`main_loop.asm:1407-1500`). On aeon's measured histogram a 16-tile class is a good fit —
4, 9, 12 and 16 all take one slot; 24 and 29 take two — and one class means one free list, one
size, and no "which class does this blob belong to" question at either build or run time.
**Against it:** a multi-slot run needs *contiguous* free slots, which is external fragmentation
by another name, and B&R pays for that with the forced-eviction walk (an eviction that can
displace still-referenced entries — a complication a two-class scheme does not have).

**Decide it with the histogram, in the build step of §6.1 step 1**, which computes exactly the
inputs both arms need. Do not settle it here: it is a measurement, and the measurement is
already being taken for another reason.

**When a section's set does not fit the pool: that is a BUILD ERROR, not a runtime policy.**
The generator knows every section's type table and every blob's size; the union over each
2×2 envelope is computable at build time.
`ensure(worst_envelope_slots <= OBJ_POOL_SLOTS, "envelope (sx,sy) needs N slots ...")` names
the offending envelope and the author moves an object or the owner raises the pool. This is
the tree's standing preference (`CODING_CONVENTIONS.md` §1.6, §7.1) and it removes the
hardest runtime case entirely.

**One thing a fixed-slot pool must NOT do: relocate a resident blob to compact.** A live
object's `art_tile` was patched at spawn; moving its art means finding and re-patching every
live SST that points at it. `Dynamic_Live` makes that walk possible, but it is a whole
second mechanism for a case fixed slots make unreachable. Rule it out in the design.

### 3.4 The always-resident floor

Measured in §1.6: **109 tiles** (`character_window` 32, `ring_placeholder` 16,
`ring_sparkle` 4, `dust_puff` 16, `dust_spindash` 12, `insta_shield` 29), **118 with
Tails**. Four notes, because this number bounds everything else:

- **`insta_shield`'s 29 tiles are character-conditional, not global.** It is Sonic's
  ability. Under the merged character dispatch, a Tails-only or Knuckles-only act does not
  need it resident — which makes it a *per-character* window, not a floor item. Nobody has
  claimed those 29 tiles back.
- **`ring_placeholder` is a placeholder.** Real ring art may not be 16 tiles.
- **There is no HUD.** A rings/score/time HUD with digits and labels is a real cost this
  floor does not contain.
- **`character_window` at 32 is already the peak DPLC frame's requirement** for all three
  characters (guarded three times: `collision_data.emp:105`, `tails_data.emp:141`,
  `knuckles_data.emp:172`). It cannot shrink.

**So the honest floor for a shipped game is ~110 tiles plus a HUD, and the pool is whatever
is left after it.**

### 3.5 Authoring: derived, and it is already built

The brief frames this as derived-vs-authored. **In this tree it is already derived**, by
`tools/ojz_entity_gen.py`, into `Sec.sec_type_table` (§1.3), from exactly what is painted.
Extend that generator rather than introduce a parallel authored list:

- Each `ObjDef` names an **art blob id** plus that blob's tile count (a new field, or
  derived from its existing `art:` word).
- The generator already knows each section's distinct `ObjDef` set. It emits, per section,
  the *blob* set — the union over that section's types, **deduped** (two spring directions
  share `Art_Spring`; the two dust objects share `Art_Dust`).
- It computes every 2×2 envelope union and emits the worst case as a constant for the
  `ensure` in §3.3.

**The brief's objection to derived — "can be wrong at an edge" — is answered by computing
the envelope union at build time instead of the section set.** The generator has the
adjacency; nothing about "derived" forces a per-section answer.

**Where authoring is still needed, and it is one bit: pinning.** Some art must be resident
regardless of placement (§3.4), and some art belongs to an object *spawned by another
object* rather than placed — a projectile, a monitor's contents, an explosion, a boss's
second phase. Placement-derivation cannot see those. **Recommendation: an authored `pins:`
list per act, plus a `spawns:` declaration on each `ObjDef` naming the types it can create
at runtime, so the generator can take the transitive closure.** That closure is the piece
that makes derivation *correct* rather than merely cheap, and its absence is the most likely
way this design fails silently.

### 3.6 The problems the brief did not list

**(i) The DMA window is already over-subscribed (§1.5), and this is the real blocker.**
NTSC residual 2,944 B; today's worst frame wants 2,976 solo and 4,032 duo. An object loader
adds demand to a window already in deficit. Consequences: object-art DMA is **Deferrable**,
never Important, and must tolerate being dropped for many consecutive frames — which is
exactly what policy (a) in §3.1 provides. **Any measurement of this tier taken on OJZ act 1
is worthless**, because that act is fully resident and contributes zero page-landing bytes
in steady state; the honest test needs a streaming act. `[RUNTIME]`

**(ii) Palette, not just tiles.** CRAM is four lines of sixteen and all four are spoken for:
`ojz_scroll_test.emp:598-627` loads `BGND_Palette` into line 0 (character + backdrop +
debug) and `OJZ_Palette` into lines 1-3 (level). The spring only fits because its donor's
pixel indices `{0,1,6,7,8,9,C,D}` happen to read correctly against line 0 —
`test_solid.emp:783-793` says so at length, and says skdisasm's sheet would have rendered
wrong. **A per-section object set needs a palette line as well as tiles, and there is no
free line.** Either every object draws on line 0 (constraining object art to the character
palette forever), or the design needs a per-region palette story — which is the *other* half
of the painted-regions project. A genuine unresolved coupling, not solvable inside the
object-art tier.

**(iii) A dropped Deferrable DMA makes residency a lie.** `QueueDMA_*` returns carry-set
when the queue is full, and every current call site spells `@discards(dropped)`. If a slot
is marked "resident" at *enqueue* time and the enqueue is dropped, every object spawned that
frame gets a correct-looking `art_tile` pointing at uninitialised VRAM. **The table must be
marked resident on the DMA's completion, not its enqueue** — a two-state (`pending` /
`resident`) per slot, with the §3.1 spawn gate testing `resident`, not `allocated`. This is
the same class of bug the FG tier's "published but not yet ref'd" demand-protection
invariant exists to prevent (`page_cache.emp:243-249`); the lesson transfers even though
none of the code does.

**Good news, read out of the queue rather than assumed: once an entry is ACCEPTED, delivery
is guaranteed.** `Drain_Budgeted_Queue` (`engine/system/dma_queue.emp:461-492`) tests each
entry against `DMA_Budget_Remaining` and, on a miss, **leaves it and everything after it
queued, compacting the survivors to the queue base for the next frame's fresh budget** — the
comment says so at `:468` ("entry does not fit — leave it (+ the rest) queued for next
frame's fresh budget; no overshoot"). So the loader enqueues **once**; the only failure is
carry-set at *enqueue* time (queue full), which is a synchronous, testable result.

**And that gives a cheap completion signal with no new mechanism:** an entry is delivered
once the Deferrable slot pointer has returned to the queue base (`.loop` exit writes
`move.w a3, (a2)` with `a3` = base only on a full drain). A loader that flips its `pending`
slots to `resident` on any frame where the Deferrable queue drained empty is correct,
conservative, and costs one `cmp` per frame. **This is the mechanism to use — do not invent
a per-entry completion callback the queue does not have.**

**(iv) An object can leave the area that pinned its art.** A badnik launched by a spring, a
projectile, a follower. The refcount handles it correctly (a live SST holds a reference
wherever it is) and `ENTITY_DESPAWN_BUFFER` removes it by distance, releasing the reference.
What must not happen is releasing a *pin* while a live object still holds a *refcount* —
which is why §3.2 keeps them as two separate counters rather than one.

**(v) Determinism and the replay fixture.** Residency affects `art_tile`, which affects the
SAT, which the replay net covers. A residency table driven by a *droppable* Deferrable DMA
is frame-timing-dependent. Either residency is made deterministic (fixed enqueue order,
budget that cannot vary), or the replay hash must be shown not to cover it. **Unresolved —
flag for the owner.** `[RUNTIME]`

**(vi) Shape independence.** `vram.toml` is one map for every build shape by deliberate
policy ("a VRAM reservation is not a ROM byte"). The object pool's size and base must
therefore be shape-independent, so the 13 tiles of debug tags and 12 tiles of test windows
stay reserved in release. Recovering them is a separate decision about whether `vram.toml`
may become shape-conditional, and its own comments argue firmly against it.

**(vii) Blob sharing and dedup.** `Art_Spring` already holds two sheets (vertical plus a
separate 12-tile horizontal one) in one blob; `Art_Dust` holds the spindash DPLC source and
the puff block. **The unit of residency is the blob, not the object type**, and the
generator must dedup by blob so a section with four spring directions loads one blob.
Straightforward, but it must be stated: getting it wrong makes §4's arithmetic wrong by a
large factor.

---

## 4. How the originals actually did it

Read out of the disassemblies by a research lane, with file:line for every claim. **I
spot-checked the two most decision-relevant findings myself** — S2's PLC drain rate
(`s2disasm/s2.asm:2202-2221`, confirmed verbatim: 6 patterns/frame in `ProcessDPLC`, 3 in
`ProcessDPLC2`) and S3K's mid-level act transition (`skdisasm/sonic3k.asm:105716-105736`,
confirmed verbatim including the comment "Load secondary HCZ2 art, blocks, and chunks so as
to not compromise current position"). The rest is relayed with its citations. Two questions
were flagged as needing an emulator and were **not** attempted: whether S2's second PLC is
genuinely still decompressing after gameplay begins, and what a missing-art object actually
renders.

### 4.1 Sonic 2 — per-ZONE list, title-card cover, 3 tiles/frame, no guard at all

- **Unit:** a named `PlrList_*` — 83 of them — of 6-byte `plreq` entries
  (`dc.l romsrc / dc.w vramdest`), indexed out of one 67-entry `ArtLoadCues` offset table
  (`s2.asm:88614-88697`). The per-zone binding is the 12-byte level-art pointer block
  indexed by **`Current_Zone` × 12** (`s2.asm:4770-4780`) — so **EHZ1 and EHZ2 share a
  list**. The unit is the zone, not the act, not the object.
- **When:** `ClearPLC` then PLC1 at level init with the display cleared
  (`s2.asm:4760-4787`); PLC2 later, from `loadZoneBlockMaps` (`s2.asm:20076-20078`).
- **Cover:** the title card. `Level_TtlCard` (`s2.asm:4910-4920`) spins on VBlank and
  refuses to proceed while the queue is non-empty —
  `tst.l (Plc_Buffer).w / bne.s Level_TtlCard`. The *second* title-card loop
  (`:5056-5062`) has **no such gate**.
- **Incremental:** yes, in VBlank, at two rates — **6 tiles/frame during the title card**
  (`ProcessDPLC`), **3 tiles/frame during gameplay** (`ProcessDPLC2`, reached via
  `Vint_Level` → `Do_Updates`). Both verified.
- **Mid-gameplay loads, covered by nothing but distance:** the signpost
  (`CheckLoadSignpostArt`, `s2.asm:6150-6168` — fires at `Camera_Max_X_pos - $100` and
  simultaneously pins `Camera_Min_X_pos` so the player cannot walk back into the load), the
  boss capsule (`Boss_Defeat`, `:60768`, with a 179-frame `Boss_Countdown` before the
  capsule appears), and the animals+explosion set every boss requests (`:21861-21868`).
- **VRAM allocation:** 299 hand-written `ArtTile_*` constants, 147 of them zone-banded with
  literal `; EHZ` / `; MTZ` section comments (`s2.constants.asm:2310-2495`). **Reuse across
  zones is by hand-picked address overlap with nothing enforcing it** — tile `$0500` alone
  carries six different meanings across six zones.
- **Missing art:** **no guard.** `ChkLoadObj` (`s2.asm:33376-33406`) moves the layout byte
  straight into `id(a1)`; `Obj_Index` (`:29686`) is a single global table with no
  zone-dependent indirection. The only failure reported is a full object slot. **Prevention
  is level-design convention: the object is simply not placed in a zone whose PLC lacks its
  art.**

### 4.2 Sonic 3 & Knuckles — per-ACT, primary/secondary art split, and one genuinely streamed act change

- **Unit:** per-**act**, two PLCs each, out of a 24-byte load block
  (`sonic3k.asm:199302-199354`); `Offs_PLC` has 124 entries, two per act (`:199357-199481`).
- **The structural difference that matters:** the 8×8 tileset is split
  **primary (shared between the zone's acts) / secondary (per-act)** —
  `HCZ_8x8_Primary_KosM` for both, `HCZ1_8x8_Secondary_KosM` vs `HCZ2_8x8_Secondary_KosM`
  (`:199305-199306`). This split is what makes 4.2's streamed transition affordable.
- **Cover:** fade to black → `Clear_DisplayData` → a title-card spin gated on **both** the
  title-card object and the queue (`:7736-7747`). `Act3_flag` (`:7732`) skips the title card
  entirely for the LRZ→HPZ and HPZ→DEZ handoffs.
- **Two independent incremental decompressors:**
  - Nemesis PLC at the same 6/3 tiles-per-frame rates as S2 (`:2159-2180`).
  - **Kosinski-moduled level art, resumable across VBlank via a stack bookmark**
    (`Set_Kos_Bookmark`, `:2818-2830`): the VBlank handler's return address is examined,
    saved into `Kos_decomp_bookmark`, and replaced so the interrupt resumes the decoder.
    **This is the direct ancestor of aeon ARCH §9.7's "VBlank supervisor-bookmark idle-time
    decoder"** — the technique aeon already uses for the FG tier came from here.
- **The one real mid-level art stream, and it is worth studying** — HCZ1→HCZ2, MGZ1→MGZ2,
  CNZ1→CNZ2 change acts **without leaving `LevelLoop`**, two-stage:
  1. A placed screen-event trigger sets `Events_fg_5`; `HCZ1BGE_Normal`
     (`:105716-105736`) queues the **secondary** chunks/blocks/tiles and the two new PLCs
     **while the player is still running**. Only the act-specific half is restreamed.
  2. `HCZ1BGE_DoTransition` (`:105750-105783`) waits on `Kos_modules_left`, flips
     `Current_zone_and_act`, reloads the layout, and **rebases every coordinate**
     (`move.w #$3600,d0`, subtracted from both players, the camera and its bounds, plus
     `Offset_ObjectsDuringTransition`). MGZ is the same on two axes.
  **The shape — stream a delta while playing, then rebase — is exactly aeon's
  teleports-are-pure-rebases finding, arrived at independently.**
- **VRAM allocation:** worse than S2 — only ~12 object `ArtTile*` constants
  (`sonic3k.constants.asm:1067-1097`); every PLC entry writes a bare hex number
  (`plreq $41B, ArtNem_AIZSwingVine`).
- **Missing art: no guard, and the thing that looks like one is not one.** S3K picks one of
  **two** 256-entry object-pointer sets by zone (`:37414-37428`,
  `Sprite_Listing3` / `Sprite_ListingK`), so ID `$03` is `Obj_AIZHollowTree` in one and
  `Obj_MHZTwistedVine` in the other. **Classified by call site, this is an ID-space doubler,
  not an art-residency check**: it is consulted at level init and per frame, and never
  consults residency. The spawn itself (`:37885-37889`) takes the routine pointer straight
  from the layout byte.

### 4.3 S.C.E. — the one SONIC tree with a runtime VRAM allocator, and it has one caller

**S.C.E. does not merely inherit S3K's PLC design; it replaces most of it.**

- **Nemesis is gone entirely.** `grep -rli "nemesis|Nem_Decomp|NemDec"` over the repo root
  printed nothing; `Engine/Decompression/` holds only Enigma and the three Kosinski+ forms.
  All PLC art is Kosinski+Moduled.
- **Per-ACT lists addressed by direct label pointer**, no offset-table index
  (`Levels/DEZ/Pointers/DEZ1 - Pointers.asm:58-61` — `PLC1`, `PLC2`, `PLCAnimals`).
- **The decompression moved OUT of VBlank** into the main loop
  (`Screens/Level/Level.asm:187-188, 204`), with the S3K stack bookmark retained and called
  from the interrupt handler (`Engine/Core/Interrupt Handler.asm:148,159,316,320`).
- **Queue overflow raises in DEBUG** (`Kosinski Plus Moduled Decompression.asm:160-163`) —
  the only tree that treats it as a defect rather than silence.
- **A runtime VRAM slot allocator exists.** `SetUp_ObjAttributesSlotted`
  (`Engine/Objects/Misc.asm:31-77`) scans an 8-byte bitmap `Slotted_object_bits`
  (`Engine/Variables.asm:226`), finds a clear bit, sets it, and **writes the computed VRAM
  offset into `art_tile(a0)`** — so `art_tile` is a *variable* for slotted objects, and
  `Perform_DPLC` (`Misc.asm:85-119`) reads its destination from that field at runtime.
  Release is `Remove_From_TrackingSlot` (`Remember State.asm:237-241`).
- **⚠ Name vs behaviour: the allocator has exactly ONE call site in the shipped tree** —
  the signpost (`Signpost.asm:81`, with `subObjSlotData 1-1, $494, …`, i.e. one slot). It is
  infrastructure that is barely exercised, which is worth knowing before treating it as a
  proven design.
- **Missing art: the only refusal anywhere in the three trees, and it is a VRAM-availability
  refusal, not an art-residency one.** If no slot is free, the object clears its own
  `code_addr`, zeroes `status`, **unwinds its caller's stack frame (`addq.w #4*2,sp`) and
  returns** (`Misc.asm:48-57`). Only slotted objects get it. Everything else spawns straight
  from the layout (`Load Objects.asm:305-308`), with unused IDs pointed at
  `Delete_Current_Object` — which catches an *unimplemented* ID, not a *missing-art* one.
- **No mid-level act transition**, and only DEZ ships, so there is no S.C.E. counterpart to
  S3K's HCZ stream to compare.

### 4.4 The Treasure / Sega / BlueSky set — and one of them has already built this design

Read by a second research lane across six trees. **I did not verify these myself**; they are
relayed with the lane's citations and with its own coverage caveats, which are severe enough
to matter and are reproduced at the end of this section. Nothing here was checked against a
running ROM.

**These six sit at four distinct points on a spectrum, and only two have anything resembling
a VRAM allocator.**

| game | loading unit | cover | VRAM management | per-frame object-art DMA |
|---|---|---|---|---|
| **Ristar** | per-STAGE (21 art sets) | **display OFF** | fixed windows; per-stage tile offsets in a data table | player DPLC + animated-tile cycler |
| **Gunstar Heroes** | per scene-segment / boss-phase | camera clamp + multi-frame spin | fixed windows (2 × 32-tile player + one re-pointed "big object") | **3 fixed slots only** |
| **Alien Soldier** | per scene-script step | **none — game live** | fixed hand-authored windows | **1 slot; all enemies static** |
| **Vectorman** | per ANIMATION FRAME, continuous | **none** | allocator exists; **its body is in an undisassembled gap** | bounded 5,760 B/frame, global FCFS |
| **Thunder Force IV** | per-STAGE | intro cutscene, then amortised over ~128 frames | fixed windows | none (background only) |
| **Batman & Robin** | per ANIMATION FRAME, demand-loaded | **none** | **refcounted, evicting cache over 64 × 16-tile slots** | bounded, per-level-tuned budget |

#### 4.4.1 Batman & Robin has already built the design in §6, and it is worth copying twice

`disasm/code/engine/objects.asm` and `.../main_loop.asm`:

- **A refcounted, evicting cache over 64 fixed 16-tile (512 B) slots = 32 KB, VRAM
  `$0BE0–$89DF`** — exactly half of VRAM given to object art. Destination table at `$80B5`,
  stride `$10`, VRAM step `$0200`.
- **Slot count and per-frame DMA budget are per-LEVEL constants supplied by the level setup
  script** (`main_loop.asm:3597,3604`).
- Allocator `$0085F8` (`main_loop.asm:1407-1500`), three paths: pop a free slot; **reclaim**
  the oldest unreferenced record and steal its slots; **forced eviction** walking the reclaim
  list past still-referenced entries.
- **Release does not free the VRAM.** `$0086AA` decrements the refcount and pushes onto a
  reclaim list; the art stays resident and re-hittable until something evicts it. **That is
  precisely the "Refcount-based Art Caching / Lazy Reclaim" entry in `DEFERRED_WORK.md`,
  shipped in a 1995 commercial game.**
- A cache hit does no DMA at all (`objects.asm:4200`).
- Objects leaving a `$170 × $110` camera window **release their art handle**
  (`objects.asm:2090-2091`) — the same camera-envelope-drives-residency shape as §3.2.

**Three things this changes in my design:**

1. **§3.3's slot classes are probably wrong, or at least not obviously right.** B&R uses **one
   class** — 16 tiles — and allocates *multi-slot runs* for larger art, handling the resulting
   fragmentation with the forced-eviction walk. A single class is simpler than my two, and 16
   tiles happens to fit aeon's blob histogram well (4→1, 9→1, 12→1, 16→1, 24→2, 29→2 slots).
   **Recommend evaluating single-class-with-runs against my two-class proposal as an explicit
   fork in the build step**; the histogram is already computable, so the answer is cheap.
2. **§3.1 gains a better answer for the frame-swap case, though not for the spawn case.** On
   any failure B&R does `move.w d7, $20(a6)` — it **reverts to the previously-resident art ID**
   and re-renders the old frame, retrying next frame (`objects.asm:4167-4180`). There is no
   garbage-tile case and no hard failure. That is strictly better than "refuse" *where a
   previous frame exists*; at a **spawn** there is no previous art, so §3.1(a) still stands
   for the spawn path. **Both are needed and they are different paths.**
3. **The guard should be four-way, not one-way.** B&R checks, before committing:
   per-frame DMA budget, free queue slots, free VRAM tile slots, and free cache records — and
   **restores the counters** on any failure. My §3.6(iii) only proposed a resident/pending
   two-state. Adopt the four-way pre-check and the rollback.

#### 4.4.2 Vectorman — atomic rollback, and a bandwidth figure worth comparing against

- Art is **uncompressed and DMA'd straight from ROM** (the `$95/$96/$97` source-register
  bytes are copied verbatim out of the descriptor), which is why the ROM is 2 MB with
  ~1.6 MB of data. **The same choice aeon has already made for object art** (§1.2).
- **Budget: ≤54 queue entries and ≤`$B40` = 5,760 bytes per frame, globally shared FCFS**,
  reset once per frame (`:6252`). Objects late in the render list are denied and repeat last
  frame's art.
- **The best guard found in any of the six:** if the DMA queue is full, the producer **rolls
  the entire entry list back and returns 0** (`:6326-6332`); the caller commits nothing and
  renders from the still-resident art (`:7438-7445`). Atomic per object, retried next frame —
  *structurally impossible* to draw non-resident art. Plus an unallocated-window skip, an
  80-sprite clamp, and a 73-site assert framework.
- **The comparison that matters:** Vectorman spends **5,760 B/frame on object art alone**
  against aeon's **2,944 B total residual** — nearly 2× aeon's entire remaining window. It can,
  because Vectorman streams *no level art*: its planes are fixed and the whole budget is
  sprites. **aeon is buying a foreground streaming tier that Vectorman does not have, and the
  object tier is paying for it.** That is the honest framing of §1.5's deficit, and it is a
  design tension, not a defect.

#### 4.4.3 Ristar, Gunstar, Alien Soldier — and the finding that lowers expectations

- **Ristar:** per-stage, **display blanked** (`andi.b #$bf` on the reg-1 shadow at `$014080`,
  restored `ori.b #$40` at `$0141FE`), VBlank handler set to a bare `rts` during the load, and
  the loader **manually pumps the SFX queue mid-load** — which is what you do when you know
  you are blocking for many frames. Placement is *data*: a 22-entry per-stage tile-offset
  table added to a base tile. **No allocator, no free list, no refcount, no eviction, and no
  PLC queue at all.** A chunked streamer object does exist (`$05D3BE`, 100 tiles = 3,200 B per
  frame) but it sits beside a palette fade and a global mutex and reads as a *transition*, not
  mid-combat — the lane flags "does it run while the player has control" as unproven.
  `[RUNTIME]`
- **Gunstar Heroes:** a real PLC (`{flags.w, src.l, dest.w}`, `$FFFF`-terminated), triggered by
  a camera-X threshold or by an object's own routine. Cover is a **scroll lock plus hiding the
  boss plus a multi-frame busy-wait** (`btst #$7,$a958.w` → `tst.w $f720.w` → `clr.w $2(a5)` →
  `jsr $2478`), one frame per `$200`/`$400` chunk — "the screen stops scrolling, then the boss
  is there." All nine writes to the per-object VRAM base are immediate constants.
- **Alien Soldier:** the architecture *inverts* — gameplay runs inside the VBlank interrupt and
  the foreground main loop does nothing but stream art (`$000554`: `move #$2300,sr / jsr $294E
  / bra`). Loads are **uncovered**, budgeted at 512 or 1,024 B/frame. Exactly **one** write to
  the per-object VRAM base exists in the entire 2 MB ROM.

**The finding, and it is the one that should temper §5.1's expectations:** **Treasure did not
stream enemy art either.** Gunstar streams three slots (two players + one big object); Alien
Soldier streams **one**. Every ordinary enemy and every boss part in both games draws from
*static* VRAM tile indices. Two of the most sprite-dense games on the platform solved object
variety by **authoring within a fixed resident set**, exactly as the Sonic trees did. Only the
two *animation-frame*-driven engines (B&R, Vectorman) built caches — and they built them to
stream **frames of a few large characters**, not **art of many different objects**, which is
aeon's actual problem. **Nobody in this set has solved aeon's problem; two of them have built
the machinery that would.**

#### 4.4.4 Corrections to our own repo that fell out of this

Booked separately in `DEFERRED_WORK.md`; recorded here because they were found in service of
this design and a reader of §4.4.3 needs to know the Ristar doc is not reliable.

**The first two below I re-derived MYSELF** — they contradict a claim of ours marked DONE and
an analysis file we cite, so relaying them second-hand was not good enough.

- **`docs/research/ristar-techniques.md` claim #4 is REFUTED — VERIFIED HERE.** It is marked
  **DONE / already adopted** and says Ristar uses cell-scroll (~28 entries) as the workhorse
  with per-line reserved for hero shots. `grep -in '#\$8b0' ristar_disasm/code/disasm.asm`
  returns **exactly seven VDP register writes** — `$8b03` ×4 (`$00BBE6`, `$00BDD4`, `$00D806`)
  and `$8b07` ×4 (`$00BE4A`, `$00D836`, `$00DF18`, `$00E0DC`) — plus one `ori.l #$8b0000b2, d2`
  that is not a VDP write at all. **`$02` never appears.** Reg `$0B` bits 1:0 select HScroll
  mode; `$03` is `%11` = per-line, and `$07` is `%11` plus the 2-cell vscroll bit — also
  per-line. **Ristar is per-line HScroll always.**
  ⚠ **Method note, because it nearly went the other way:** a raw hex grep for `8b0[0-9a-f]`
  over the same file returns ~290 hits and would have "confirmed" `$8b02` — it matches the byte
  pattern in unrelated data and addresses. The instrument has to select **instructions**
  (`#\$8b0` with the immediate marker), not bytes.
- **`aliensoldier_disasm/ANALYSIS.md` is a SYMLINK to `../gunstar_disasm/ANALYSIS.md` —
  VERIFIED HERE** (`/usr/bin/ls -l`, `lrwxrwxrwx … -> ../gunstar_disasm/ANALYSIS.md`). There is
  no Alien-Soldier-specific analysis in the tree, and anyone reading "Alien Soldier's analysis"
  is reading Gunstar's. Its "Direct DMA (No Queue) / art is pre-rendered, not streamed" line is
  false for Alien Soldier, which has both a queue and streaming.
- **Claim #3 (per-stage HInt dispatch) is CONFIRMED and larger than stated** — `$05612C` is
  table-driven and installs per-stage **VBlank** handlers too.
- **Claim #1 (event-tagged animation frames) is PARTIAL** — the `{frame_no, action_byte}`
  table shape exists, but the action vocabulary is `{none, clear flip bits, set flip bits}`,
  not the SFX/hitbox/callback set the doc claims.
- **The "stage script interpreter at `$C01E`" is a misidentification** — it is the attract-mode
  **demo player**, replaying canned controller input. It loads no art.

#### 4.4.5 ⚠ How much to trust §4.4 — the coverage holes, reproduced

The lane reported these unprompted and they are load-bearing limits on everything above:

- **Vectorman: 79.1% of the ROM is not disassembled** (1,658,880 B across 42 markers). **The
  VRAM allocator's body, the VBlank DMA drain, and the covered-install path are all inside
  gaps**, and the art-descriptor byte layout is *inferred from access patterns and did not
  parse when hexdumped*. So "Vectorman has an allocator" is a call-site inference, not a read
  design.
- **Gunstar: ~175 KB of code omitted inside the CODE ranges** across 152 label gaps. The
  DMA-queue primitive, the PLC walker's caller, the VDP register init and the per-scene load
  lists are all in holes. The stall length is unproven. `[RUNTIME]`
- **Alien Soldier: the disassembly is LOSSY, not merely truncated** — the main loop and the
  entire VBlank entry are absent and were recovered by hexdumping the ROM. Its `ANALYSIS.md`
  is **a symlink to Gunstar's**, so there is no Alien-Soldier-specific analysis, and that
  file's "no queue, art is pre-rendered not streamed" claim is **false** for Alien Soldier.
- **Thunder Force IV:** the VBlank dispatch and object-slot allocator are in holes; the plane
  and SAT assignments are inferred from usage, not read from register writes.
- **Batman & Robin:** the per-frame reset of the queue counters could not be located — only
  mode-init writers exist, and the queue would exhaust after 40 total entries without one.
  **So the "bounded, per-level-tuned budget" in the table is partly inferred.** `[RUNTIME]`

**Reading rule for §4.4: treat the two cache designs (B&R, Vectorman) as strong evidence that
the shape works and weak evidence about its details.** The details are what the gaps ate.

### 4.5 What the Sonic trees agree and disagree on

**Agree:**
1. **The unit of loading is a batch — a zone's or an act's list. An object is never the
   thing that triggers a load**, with a handful of named exceptions (S2's signpost, capsule
   and boss animals; S3K's bosses; S.C.E.'s egg capsule).
2. **Everything is incremental across frames**, at a *very* low rate: 3 tiles/frame during
   gameplay in both S2 and S3K.
3. **Cover is a title card or a fade.** Where there is no cover, the load is hidden by
   *distance* plus a one-way camera lock (S2's signpost) or a long timer (S2's boss).
4. **VRAM allocation is hand-assigned.** 147 zone-banded constants → 12 constants plus raw
   hex → 13 constants plus raw hex plus a barely-used bitmap. **Nobody has a build-time VRAM
   linker; aeon's `vram.toml` is already ahead of all three.**
5. **Nobody gates spawning on art residency.** The design space's answer to "what happens
   when art is missing" is, in every case, *make it structurally impossible by authoring*.

**Disagree, and these are the choices aeon has to make:**
- **Where the incremental work runs.** S2/S3K: VBlank. S.C.E.: the main loop. aeon's FG tier
  already chose the VBlank-idle bookmark; the object tier needs neither, because its art is
  uncompressed.
- **Whether `art_tile` is a constant or a variable.** S2/S3K: constant. S.C.E.: variable for
  slotted objects. **aeon must make it a variable, and S.C.E. is the precedent that it
  works.**
- **Whether exhaustion is silent.** S.C.E. raises in DEBUG; the others do not. **Follow
  S.C.E.**

### 4.6 Across all nine trees — what actually generalises

**The single most useful thing the whole survey produced:** the nine games split cleanly on
one axis, and it is **not** "did they stream art".

| | streams no object art | streams a FEW LARGE characters' frames | streams MANY DIFFERENT objects' art |
|---|---|---|---|
| games | S2, S3K, S.C.E., Ristar, Thunder Force IV | Gunstar (3 slots), Alien Soldier (1), Vectorman, **Batman & Robin** | **nobody** |

**Nobody in the reference set solved aeon's problem.** Every one of these games got object
variety by **authoring within a fixed resident set**, and the four that built streaming
machinery built it to page *animation frames of a small cast*, not *art of many distinct
object types*. Even Treasure — Gunstar and Alien Soldier, two of the most sprite-dense games
on the hardware — stream three slots and one slot respectively and draw every ordinary enemy
from static VRAM.

Three consequences, and they are the ones that should survive into whatever gets built:

1. **The classics constrain us less than they look like they do.** "Nobody gates spawning on
   art residency" (§4.5) is not nine independent votes against a residency gate; it is nine
   games that never needed one because their loading unit and their spawning unit were the
   same thing. aeon is proposing to separate those two, which is genuinely novel here, and
   §3.1's policy is therefore a **design decision to be argued on its merits**, not a
   departure from precedent to be justified.
2. **But the machinery is proven, twice, in shipped commercial games.** Batman & Robin's
   refcounted evicting cache with lazy reclaim (§4.4.1) and Vectorman's atomic
   rollback-on-full (§4.4.2) are exactly the two mechanisms §3 needs, running at 60 Hz on this
   hardware in 1995. **The risk in this design is in the manifest and the palette, not in the
   cache.**
3. **The cover story is the one thing that does NOT generalise.** Display-off (Ristar, S2/S3K
   init), a title card (S2/S3K), a camera clamp plus a visible stall (Gunstar), a cutscene
   (TFIV), or nothing at all (Alien Soldier, Vectorman, B&R) — every option in the space is
   represented, and the choice tracks the *engine*, not the era. aeon's answer is already
   fixed by its own architecture: the entity window gives 16-24 frames of lead (§1.4), so the
   cover is **distance**, the same answer S2's signpost reached.

**One number worth carrying:** Batman & Robin gave **half of VRAM — 32 KB, 1,024 tiles — to
the object art cache.** aeon's proposed pool is 256 tiles, a quarter of that, on a machine
that is also streaming a foreground tileset B&R did not have. If §6.3's measurement comes
back saying 256 is not enough, **B&R is the existence proof that a much larger object pool is
a legitimate shape for a Genesis game** — and the tiles would have to come from the planes or
the FG pool, which is the conversation `VRAM-NEIGHBOURHOOD` already asks for.

---

## 5. The cost, in the three currencies

The shape being priced is the one §6 recommends: **a slot-table object pool, fixed slot
classes, blob-keyed, section-pinned, ROM→VRAM DMA at Deferrable priority.**

### 5.1 VRAM tiles

**The pool does not have to be contiguous.** A slot table stores a VRAM base per slot, so
the pool can be assembled from the disjoint runs the map can actually spare. That matters,
because the two biggest sources are on opposite sides of `spare_nametable`.

A worked 256-tile pool, sourced only from levers already named in the
`VRAM-NEIGHBOURHOOD` booking:

| source | tiles | price |
|---|---|---|
| the existing object neighbourhood 896-1023, re-cut as pool slots | 128 | none — it is already object art |
| `fg_art_pool` 768 → 640 (12 → 10 page frames) | 128 | OJZ act 1 stays fully resident (needs 10) but has **zero** eviction headroom; `vram.toml` names 640/10 as the floor until C4-3 lands |
| **pool total** | **256** | |
| *not taken:* `bg_region` reserve | 56 | the scavenge route the booking says to stop using |
| *not taken:* `spare_nametable` | 128 | spends an *address* (the map's only $2000-aligned run), not tiles |

Slot classes, sized from the measured blob histogram (4, 9, 12, 16, 24, 29):
**8 × 16-tile slots + 4 × 32-tile slots = 256 tiles, 12 slots.**

What the floor consumes of it (§3.4): character 32 → 1 large; `insta_shield` 29 → 1 large;
`ring_placeholder` 16, `dust_puff` 16, `dust_spindash` 12, `tails_appendage` 9,
`ring_sparkle` 4 → 5 small. **Floor = 2 large + 5 small = 144 tiles.**

**What is left for the streamed set: 2 large + 3 small = 112 tiles, 5 concurrent blobs.**

**This is the number that answers the owner's question, and it should be read carefully.**
It does **not** say "five badniks per act". It says: *object variety costs ROM, and only
CONCURRENCY costs VRAM.* An act may contain twenty distinct badniks so long as no 2×2
section envelope needs more than five of them resident at once — and that is a condition the
generator can compute and `ensure` at build time (§3.3). Under today's design, twenty
badniks would cost twenty windows and is flatly impossible. That is the whole change.

Two honest caveats on the 5:
- **A HUD is not in the floor and this engine does not have one.** S3K's uncompressed HUD
  digit sheet is 768 B = 24 tiles (`skdisasm General/Sprites/HUD Icon/HUD Digits.bin`,
  `binclude`d at `sonic3k.asm:18210`) plus a compressed label sheet. Budget ≥ 24 tiles,
  realistically 32-40 — **one to two more large slots off the streamed set**, taking 5 down
  to 3 or 4.
- **The floor is soft in the other direction.** `insta_shield`'s 29 tiles are Sonic's
  ability, not a global cost, and `ring_placeholder` is a placeholder. Reclaiming
  `insta_shield` as a per-character slot returns a large slot immediately.

### 5.2 ROM

Object art is raw, so ROM cost is exactly `tiles × 32` with no compression win and no
decoder cost. Measured blobs: `Art_Spring` 768 B (24 tiles), `Art_RingSparkle` 128 B,
`dust_puff` block 512 B.

A twenty-badnik act at ~24 tiles each ≈ **15.4 KB**. Against the ROM margin measured at the
2026-09-04 re-layout — room 114,658 B on the binding DEBUG shape, of which **65,506 B sits
above `DATA_GROWTH_RESERVE`** (`docs/superpowers/2026-09-04-rom-relayout-more-room-report.md`,
quoted in `vram.toml`) — that is ~23% of the available margin. **Comfortable, and it is the
currency the design deliberately spends.** ⚠ Re-derive that margin before quoting it; it
moves, and `tools/bganim_room.py` is the instrument.

Tables: a per-section blob set is a count byte plus one slot-id byte per blob — on the order
of **10-40 bytes per section**, negligible beside the art. If object art is later compressed
(ZX0 would roughly halve it), the tier gains a decoder and loses the "one DMA" property that
makes it cheap; **do not do this until ROM is actually tight.**

### 5.3 Bandwidth and latency, against the *remaining* window

The unit is the DMA-byte-equivalent the engine actually charges (§1.5). NTSC residual after
the plane drain and the Critical queue: **2,944 B/frame.**

| frame kind | already spoken for | left for object art |
|---|---|---|
| steady state, fully-resident act, solo character | Sonic DPLC peak 928 | **2,016 B** |
| steady state, duo | 928 + 768 + 288 = 1,984 | **960 B** |
| a frame where a page landing completes, solo | 2,048 + 928 = 2,976 | **0** (already 32 B over) |
| a frame where a page landing completes, duo | 4,032 | **0** (1,088 B over) |

One 24-tile blob is **768 B = 38% of the 2,016 B solo steady-state headroom, one frame**
(26% of the 2,944 B residual before DPLC is charged — the smaller figure is the wrong
denominator and an earlier draft of this line used it). A full
five-blob envelope changeover is ~3.8 KB — **two frames solo, four duo**, against
**16 frames** of vertical lead and **24** of horizontal (§1.4). Even if half the frames in
that window are page-landing frames and yield zero, the margin is roughly 4× .

**So bandwidth is not the constraint on a normal crossing. It is the constraint on the
worst frame, and the design's answer is to never need a specific frame:** Deferrable
priority, drop-tolerant, resident-on-completion (§3.6 iii), spawn-retry on miss (§3.1).

PAL is not the binding case: residual 8,448 B, 5.4 KB spare even in the worst frame.

**Two things this pricing does not cover, and both are `[RUNTIME]`:**
- The *slot count* cost of the DMA queue, not the byte cost. `DMA_DEFERRABLE_SLOTS = 12`
  and DPLC already spends Important slots per frame. Five blobs is five Deferrable entries,
  and **a blob crossing a $20000 ROM boundary costs TWO slots — and is rejected outright if
  only one is free**, not split partially (`engine/system/dma_queue.emp:80-81,199-204`:
  "A 128KB split needs TWO free slots: with only one, the whole transfer is rejected"). So
  worst case is ten of twelve. **The cheap fix is build-time: keep every object blob inside
  one 128 KB span, which the placer can do for free and which removes the straddle case from
  this tier entirely.** Watch this number before the byte budget.
- The measurement must be taken on a **streaming** act. OJZ act 1 is fully resident, so its
  page-landing term is zero in steady state and it will make this tier look free.

---

## 6. Recommendation, and the measurement that would refute it

### 6.1 What I would build

**Build the object-art tier as a small blob-keyed slot pool, keyed on SECTIONS today and
regions later, and build it in this order:**

1. **First, a build-time step and nothing else.** Extend `tools/ojz_entity_gen.py` to emit,
   per section, the deduped set of art blobs its type table implies, plus the 2×2 envelope
   unions and an `ensure`-able worst case. **This produces a number — "the worst envelope in
   this act needs N tiles of object art" — with zero engine risk**, and that number is what
   the owner should see before anyone writes a loader. If it comes back small, the whole
   tier can be deferred and the map merely re-cut.
2. **Then the re-cut**, as the `VRAM-NEIGHBOURHOOD` booking asks: object windows become pool
   slots in `vram.toml`, `fg_art_pool` drops to 640 if step 1 says the tiles are needed, and
   `gen_vram_map.py` gains a `kind = "pool"` that the slot table is generated from. Aurora
   gets the notice the booking commits us to, *before* it lands.
2b. **Also from step 1: settle the slot-class fork** (§3.3) — one 16-tile class with multi-slot
   runs, B&R's shape, versus two classes. The histogram step 1 computes is the whole input.

3. **Then the loader**, and **model it on Batman & Robin rather than on anything in the Sonic
   trees** (§4.4.1), because B&R is the only reference that actually built this: slot table,
   refcount + pin as two counters, age-stamp eviction, **release that does NOT free the VRAM**
   (lazy reclaim — art stays re-hittable until evicted, which is free cache-hit performance and
   is the `DEFERRED_WORK.md` "Refcount-based Art Caching / Lazy Reclaim" entry), a **four-way
   pre-check with full rollback** (DMA budget, queue slots, VRAM slots, records), the
   **revert-to-last-resident-art** path for live objects (§3.1), one
   ROM→VRAM Deferrable DMA per load, resident-on-completion, spawn-retry on miss, and a
   DEBUG audit that recomputes refcounts from `Dynamic_Live`.
4. **Regions arrive as a re-key, not a redesign.** When the painted-region layer exists,
   the pin source changes from "the four tracked sections' type tables" to "the live
   regions' blob sets". Nothing else in the tier moves. **Designing for sections now costs
   nothing later** — and designing for regions now is unbuildable (§1.3).

### 6.2 What I would NOT build

- **Not a second page cache, and not a client of the first** (§2). The quantum and the
  refcount source both disagree.
- **Not a free-run allocator** (§3.3). Fixed slot classes turn the hard case into a build
  error.
- **Not compression** on object art, yet (§5.2). It buys ROM this engine has and costs the
  one property that makes the tier cheap.
- **Not relocation/compaction** of a resident blob (§3.3).

### 6.3 The falsifier

**The claim: object-art residency is CONCURRENCY-bounded, not variety-bounded, and the
concurrency in real content is small enough that a ~256-tile pool with ~5 free slots is
enough.**

**The measurement that would refute it, and it is step 1 above, so it is cheap:** run the
generator over an act authored with real content variety — not OJZ act 1, whose type tables
are `{Spring, Solid}`, `{Solid}`, `{Solid, Static}` and six empties
(`entity_data.emp:36-76`) — and print, for every 2×2 section envelope, the number of
distinct art blobs and their total tiles.

- **If the worst envelope needs more than the pool's free slots, the recommendation is
  wrong** and the answer is a different axis entirely: fewer object types per area (an
  authoring constraint the owner may not accept), or shared/atlased object art, or DPLC for
  ordinary objects rather than only characters.
- **If the worst envelope is comfortably under, the loader may not even be needed** — a
  per-act resident set in a re-cut pool would do, and the honest recommendation shrinks to
  step 2.

Either way the experiment is a Python script over data that already exists, it runs before
any engine code is written, and it decides the question. **That is the reason step 1 is
step 1.**

Three secondary refutations, all `[RUNTIME]` and all for the controller:

- **Bandwidth.** Instrument object-art DMA bytes per frame on a *streaming* act and compare
  against `DMA_Budget_Remaining` at the Deferrable drain. If object loads are being dropped
  for more than ~8 consecutive frames at a crossing, the 16-frame lead is not enough and the
  entity window's buffers must grow (they are constants; growing them is cheap).
- **Queue slots, not bytes** (§5.3). If a five-blob changeover plus DPLC exceeds
  `DMA_DEFERRABLE_SLOTS = 12`, the byte budget was never the binding constraint.
- **Determinism.** If the replay hash diverges across runs after the tier lands, residency
  is frame-timing-dependent and §3.6(v) is a real defect, not a caution.

---

## 7. Open holes, stated as holes

These are named rather than answered. An invented answer here would be worse than the gap.

1. **Palette (§3.6 ii).** All four CRAM lines are spent. A per-region object art set needs a
   palette line and there is none. This is a coupling to the painted-regions palette work
   and it is **not solvable inside the object-art tier.** It is also the most likely thing
   to make the whole idea moot: if every object must draw on the character palette line
   forever, "the cave's badniks" cannot look like the cave's badniks.
2. **Determinism / the replay fixture (§3.6 v).** Unresolved. Needs the owner's call on
   whether residency joins the hash ledger or is made structurally deterministic. `[RUNTIME]`
3. **The `spawns:` closure (§3.5).** Placement-derived manifests cannot see objects created
   by other objects. The mechanism proposed (a per-`ObjDef` declaration + transitive closure)
   is sound but unbuilt anywhere, and it is where a derived manifest silently goes wrong.
4. **Whether `fg_art_pool` can actually give up 128 tiles.** It keeps OJZ act 1 fully
   resident at 640/10, but that leaves zero eviction headroom and `vram.toml` records an
   open defect (the `STRESS_EVICT` famine, C4-3) below that line. **This is a real
   dependency, not a formality.**
5. **The DMA-queue *slot* budget** (§5.3) has not been costed against a realistic
   changeover. Bytes were; slots were not.
6. **Not examined: the demo game.** Everything here is measured against `games/sonic4`.
   `games/demo` has no `Sec` array and no type tables, so an engine-side pool must degrade
   to "no pool" cleanly for it, and that has not been designed.
