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

They sit in the level-init block, display off, immediately after `Level_LoadArt`. Adding
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
