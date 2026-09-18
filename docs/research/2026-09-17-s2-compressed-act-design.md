# S2-COMPRESSED-ACT — the aeon half of the design

**Date:** 2026-09-17 · **Branch:** `research/s2-compressed-act` (worktree `aeon-wt-s2conv`)
**Booking:** `docs/DEFERRED_WORK.md`, section `S2-COMPRESSED-ACT` (OPEN, owner direction
2026-09-17T16:00:34Z, part of REGIONS).
**Measurement script:** `docs/research/s2-compressed-act/s2_clip_budget.py` (committed beside
this file).

**What the owner asked for, verbatim:** *"maybe we can start with sonic 2, but like I'd like
it so we can make like "compressed" version of the game in one act as a test? Like we convert
the levels to our format, but then I load them on a page and can marquee parts of it, copy it
over to our layout, and paste it in as a region or something. This way we can showcase
multiple paarts of the game in the same aact without someone having to play through the whole
thing."* Scope he set: inside REGIONS, not a new project; first cut is **level art +
collision only**, objects later; **six** Sonic 2 zones — Emerald Hill, Chemical Plant, Hidden
Palace, Wing Fortress, Oil Ocean, Metropolis.

> **UPDATE 2026-09-17, after this document landed — parcel 1 is DONE and two things below
> are now WRONG.** Read
> [`s2-compressed-act/2026-09-17-prototype-donor-formats.md`](s2-compressed-act/2026-09-17-prototype-donor-formats.md)
> beside this file. In short: **Hidden Palace is no longer blocked** — the owner ruled
> `prototype-donor`, the Simon Wai disassembly is cloned, and HPZ loads, clips and budgets
> today (§6 and §9.2 below are superseded); and **the §3.5 collision counts move by two**,
> because this document's measurement handed `bake_cell` the rotated collision array instead
> of the per-column height array (301/131/278 become 299/130/276; no conclusion changes; the
> old figures are reproducible with `--profiles horizontal`). The S2 donor loader now lives in
> `tools/s2_donor.py` and reads both donor trees.

**Scope of this document:** the aeon half only — converting a whole Sonic 2 zone into aeon's
level format, and pasting an arbitrary clipped rectangle of it into an act. The aurora half
(the page that loads a converted level, marquees a rectangle and pastes it) is another lane's;
§8 states only the interface aeon must offer it.

---

## 0. Read this first — the five things that decide the design

Every figure below names the file it came from. Figures tagged MEASURED were produced by a
command printed in this document; figures tagged INFERRED are arithmetic on measured numbers
and are labelled as such in the sentence.

1. ~~**Hidden Palace Zone cannot be built from this donor. At all.**~~ **SUPERSEDED
   2026-09-17.** True of `s2disasm`, and no longer the situation: the owner ruled
   `prototype-donor`, `s2-simonwai-disasm` is cloned read-only, and Hidden Palace loads
   completely from it — layout, mappings, art, both collision indices, palette. See §6's
   update and the prototype-formats note.
2. **Clipping saves world space, not tile art.** A 2-section clip of Emerald Hill already
   needs 480 of the whole zone's 480 unique tiles (MEASURED). What costs VRAM pages is the
   NUMBER of zones, not how much of each you take. A 6-zone act clipped to 2 sections each
   needs a *bigger* art pool (2,965 tiles) than a 5-zone act taking the zones WHOLE (2,830).
3. **Clipping is nevertheless mandatory — for collision.** Aeon's collision attribute set is
   capped at 255 entries for a whole act. Five whole Sonic 2 zones need 301 (MEASURED,
   46 over). The same six zones clipped to one section each need 131. The clip is what makes
   collision fit. *(2026-09-17: corrected to 299 and 130 — see §3.5's note. And with the REAL
   Hidden Palace instead of the Hill Top stand-in, the one-section-per-clip act is **199**, not
   130: still fitting, with 56 entries of headroom instead of 125.)*
4. **The foreground art budget already passes.** Aeon's real page-placement pass
   (`fg_page_order.place_pool`, the one the bake calls) ACCEPTS a five-whole-zone Sonic 2 act:
   worst camera window needs 12 of 12 page frames, 0 of 870,231 windows over budget (MEASURED).
   It passes at exactly the limit, with no headroom, and the count does not include object art,
   background, or in-flight decodes.
5. **The seam is the real problem, and it is the palette.** Aeon's foreground uses exactly ONE
   CRAM palette line (line 2, all 46,211 painted cells of OJZ act 1 — MEASURED). Every Sonic 2
   zone's foreground uses two to four lines, and they disagree about which (MEASURED, §5.3).
   Two zones cannot be correct on screen at the same time. Clips therefore cannot simply butt
   together; each one needs a transition the camera passes through. **This is the finding that
   changes the shape of what the owner described** — see §9.1.

---

## 1. Format gap, measured from source on both sides

### 1.1 What Sonic 2 has

Donor: `/home/volence/sonic_hacks/s2disasm` (read-only; nothing in it was modified).

| Thing | Where | Shape (MEASURED) |
|---|---|---|
| Level layout | `level/layout/<ZONE>_<act>.kos` | Kosinski; decodes to exactly $1000 = 4096 bytes. 32 rows × 128 bytes; even rows are the foreground plane, odd rows the background. Each byte is a 128×128-px chunk id. (`tools/megaact_window_pageset.py:344-355`) |
| 128×128 chunks | `mappings/128x128/<SET>.kos` | 64 words per chunk (8×8 blocks). Word: bits 9:0 block id, bit 10 X-flip, bit 11 Y-flip, bits 13:12 path-A solidity, bits 15:14 path-B solidity. (`tools/ojz_common.py:338-369`, `tools/collision_pipeline.py:46-61`) |
| 16×16 blocks | `mappings/16x16/<SET>.kos` | 4 VDP nametable words per block (TL, TR, BL, BR). (`tools/ojz_common.py:317-336`) |
| Tile art | `art/kosinski/<SET>.kos` | Kosinski; 32 bytes/tile. EHZ_HTZ decodes to 914 tiles, WFZ_SCZ to 889, MTZ to 792 (MEASURED). Two zones (HTZ, WFZ) overlay a supplementary blob at a fixed tile offset. |
| Collision index | `collision/<SET> primary/secondary 16x16 collision index.kos` | 13 files, every one decodes to exactly **768 bytes** — one byte per 16×16 block, naming a collision-tile id. (MEASURED) |
| Collision shapes | `collision/Collision array - Horizontal.bin`, `... Vertical.bin` | 4096 bytes each = 256 shapes × 16 column heights. (MEASURED) |
| Collision angles | `collision/Curve and resistance mapping.bin` | 256 bytes, one angle per shape; bit 0 = "no usable angle". (MEASURED; semantics `s2.asm:43609-43613`) |
| Palette | `art/palettes/<ZONE>.bin` | 96 bytes = 48 colours = 3 CRAM lines. (MEASURED) |
| Camera extent | `s2.asm:14698-14750` `LevelSize:` | Per zone+act (xstart, xend, ystart, yend). |

### 1.2 What aeon has

| Thing | Where | Shape |
|---|---|---|
| Act | `engine/structs.emp:41-69` | 46-byte `Act` record: section-grid pointer, `grid_w`/`grid_h`, start position, act-wide BG layout + tiles, parallax config, art-pool table + page count, edge mode, per-section local-map table, art budget, region table + count. |
| Section | `engine/structs.emp:285-292` | 22-byte `Sec`: block index, objects, rings, type table, block dictionary + length. **Nothing else.** Palette, music, BG layout and tileset were all deleted from `Sec` between 2026-09-04 and 2026-09-16 (`engine/structs.emp:322-350`). |
| Section size | `engine/system/constants.emp:357-358` | `SECTION_SIZE = $0800` (2048 px), `SECTION_SIZE_SHIFT = 11`. A section is 256×256 tiles. |
| Act grid cap | `engine/system/constants.emp:875` | `MAX_ACT_SECTIONS = 48` (grid_w × grid_h). |
| Region | `engine/structs.emp:132-156` | 26-byte `Region`: an **arbitrary world-pixel rectangle** naming an effects preset (mandatory; the preset carries the palette), an optional parallax override, and optional BG layout / span / tiles. **Presentation and identity only — storage stays per section** (`engine/structs.emp:74-77`). |
| Editor section geometry | `tools/ojz_strip_gen.py:468-489, 522-529` | `section_N.tiles.bin` = 256×256 big-endian VDP nametable words (131,072 B). Tile indices point into one act-wide tileset named by `project.json` `zones[0].tileset`. |
| Editor collision | `tools/ojz_strip_gen.py:1805-1937` | `section_N.collattr.bin` / `.collattrb.bin` = 256×256 big-endian 16-bit cell words (131,072 B each), planes A and B. Word: bits 9:0 shape index into the base bank, 10 X-flip, 11 Y-flip, 13:12 this plane's solidity, 15:14 loop-crossover mark. |
| Runtime collision | `tools/collision_pipeline.py:199-231, 339-365` | One byte per 8×16-px cell, indexing five parallel 256-entry ROM tables (heightmaps, rotated heightmaps, angles, solidity, crossover). The interning table is capped at **255 solid combinations for the whole act** (`:224-228`). |
| Art pool | `engine/system/constants.emp:380, 394, 405, 874` | One flat act-wide pool: 64-tile pages (`ART_POOL_PAGE_TILES`), at most 256 pages (`PAGE_TABLE_MAX`), 768 VRAM tiles resident (`POOL_TILE_CEILING`) = 12 page frames (`PAGE_FRAMES`). |
| Palette | `engine/effects/palette.emp:48-50, 285-311` | 96 bytes = CRAM lines 1, 2, 3. Line 0 is the character's and the engine never writes it. Installed per **region** via the effects preset (`engine/effects/preset.emp:420-422`, `engine/level/parallax.emp:1263`). |

### 1.3 The gap, item by item

**Maps 1:1, no transformation:**

- Two-path (primary/secondary) collision. Aeon's `LAYER_PATH_A/B` with two collision planes is
  Sonic 2's, and aeon's `PATH_A_SOL_SHIFT = 12` / `PATH_B_SOL_SHIFT = 14`
  (`tools/collision_pipeline.py:53-54`) are literally S2's chunk-word bit pairs.
- Solidity encoding (0 none / 1 top / 2 left-right-bottom / 3 all).
- Height-byte encoding (positive = up from the bottom, negative = hanging from the top,
  16 = full block). Verified: **no byte** in S2's vertical array falls outside the range aeon's
  validator accepts (`tools/collision_pipeline.py:426-435`).
- Angle bytes: 256 units per turn, 0 = flat, bit 0 = unusable. Aeon's flip formulas
  (`tools/collision_pipeline.py:127-134`) are transcriptions of `s2.asm:42968-42978`.
- Block and chunk geometry: 16×16-px blocks, 8×8 blocks per 128-px chunk, chunk words with
  flip bits at 10 and 11.
- Palette file size: 96 bytes, 3 lines, both sides.
- VDP nametable words: identical (they are hardware).

**Needs transformation (all of it mechanical, and most of it already written):**

- **Layout → sections.** S2 is a 128×16 grid of 128-px chunks (16,384 × 2,048 px max). Aeon is
  a grid of 2048-px sections each stored as one 256×256-word file. A re-tiling, no more.
- **Collision indirection collapse.** S2 resolves `block id → per-zone index → collision-tile
  id → {height column, angle}` at runtime on every probe. Aeon resolves the whole chain at bake
  time into one interned byte. `tools/collision_pipeline.py:234-270` `bake_cell()` **already
  does exactly this transformation**, including per-path solidity and flip resolution, because
  it was written for the sonic_hack donor, which is S2-format data. This is the single biggest
  head start in the parcel.
- **Flips become identities.** S2 flips at runtime; aeon bakes each `(shape, xflip, yflip,
  solidity)` into its own attr-set entry. This is what makes §3's 255 cap bite.
- **Collision X resolution doubles.** S2 stores collision per 16-px block; aeon per 8-px column
  (`COLL_CELL_W = 8`, `engine/system/constants.emp:1043`). Each S2 block becomes two adjacent
  cells with the same byte — `tools/ojz_strip_gen.py:1757-1758` already does this.

**No counterpart in aeon today — this is the real work list:**

1. **A per-cell tileset key.** Aeon's generator reads ONE tileset per act
   (`project.json` `zones[0].tileset`) and hands the page placer a uniform zone grid. The
   placer's multi-zone rungs already exist and are exercised by fixtures, but
   `tools/fg_page_order.py:51-55` states the gap outright: *"a stitched act's loader must
   supply the per-cell tileset key."* No such loader exists. **This is parcel 1.**
2. **A collision base bank that is not S&K's.** ~~`load_base_bank()`
   (`tools/ojz_strip_gen.py:1795-1802`) hard-codes `games/sonic4/data/collision/base/`. Of the
   151 distinct collision shapes Sonic 2 actually uses, **75 are unreachable from the S&K
   bank's 236 shapes even allowing all four flips** — including a shape as plain as a 6-px flat
   floor (MEASURED, second measurement).~~ **DONE 2026-09-17 (parcel 4), and the figure was
   WRONG: it is 68, not 75.** The 151 reproduces exactly (the six-zone union with the real
   prototype HPZ); 75 reproduces under no scope or array pairing tried — five final zones 64,
   all nine 76, every non-empty S2 slot 120, the rotated-array confound 84, (profile, angle)
   matching 107. The 6-px-flat-floor illustration is false twice: it IS in the S&K flip closure,
   and no S2 slot is one. The CONCLUSION stands — 68 of 151 is 45% of the shapes the act needs,
   S2's vertical array has no hanging bytes at all where S&K's has 362, and the two banks are
   not near-misses of one vocabulary. `tools/import_s2_collision.py` imports S2's own
   `Collision array - Vertical.bin` as a second bank at
   `games/sonic4/data/collision/base_s2/`; the two are NOT merged. ~~`load_base_bank()` still
   hard-codes `base/` — selecting a bank is row 5's first move.~~ **DONE 2026-09-17 (row
   5):** `ojz_strip_gen.load_base_bank(bank_dir=None)` takes the directory, a converted
   donor tree's `zone.json` NAMES its bank and pins its sha256, and
   `clip_manifest.collision_banks` resolves an act's bank and REFUSES an act whose clips
   disagree (one act has one attr set, and one index inside it must mean one shape).
   `generate()` still calls it with no argument and still reads `base/`, so no ROM byte
   moved. See
   `docs/research/s2-compressed-act/2026-09-17-s2-collision-bank.md`.
3. **A rotated-heightmap regeneration, not a copy.** S2 and S&K store right-anchored runs as
   *positive* widths; aeon stores them as *negative* (`256-w`) and the player sensors are
   written to that convention. For **211 of 256** S2 shapes, aeon's `rotate_profile` disagrees
   with S2's shipped horizontal array, and every one of the 211 is a pure sign disagreement
   (MEASURED). The converter must regenerate from the vertical array and never copy S2's
   horizontal array in. One S2 shape (`$18`) makes `rotate_profile` **raise** (its row 0 solid
   span touches neither edge) and needs a hand ruling.
   **DONE 2026-09-17 (parcel 4), figures CONFIRMED and sharpened.** 211 of the 255
   `rotate_profile` can answer, all pure sign, exactly one raise (`$18`) — all three reproduce.
   212 of 256 once `$18` is ruled. It is not merely a sign disagreement but a WHOLE-CONVENTION
   INVERSION, confirmed from both sides' code rather than inferred from the byte diff: S2
   (`s2.asm:43282 FindWall2`, `loc_1EA78`/`loc_1EAE0`) reads `+w` as a RIGHT-anchored run, aeon
   (`probe_core`/`Collision_ProbeLeft`) as a LEFT-anchored one, and the disagreement runs both
   ways (1,533 rows / 139 rows). Decoded to solid-column sets the two describe the SAME geometry
   on 3,584 of 3,584 non-air rows, each also agreeing with the vertical array's own coverage —
   so regenerating loses nothing. `$18` RULED: it is a symmetric peak whose upper 14 rows have a
   centred run; keep the run's width and anchor it RIGHT, which is what S2 itself shipped for it
   once transcribed, and which preserves an invariant both donors satisfy with zero exceptions
   (no row is vertically covered but zero in the rotated array). Emitting 0 was considered and
   rejected on that measurement. `$18` is referenced by NO showcase zone.
   *Side finding, pre-existing and unrelated to this parcel:* the same sign confusion is live
   in `tools/import_sk_collision.py:80,87-88`, which copies S&K's rotated table verbatim into
   `base/`. It does not reach the ROM today only because `load_base_bank` never reads that
   file. Worth booking separately.
4. **More than one foreground palette on screen at once.** §5.3. Nothing today.
5. **Runtime collision-layer switching by table swap.** S2 path-swapper objects rewrite
   `Collision_addr`. Aeon's only layer-change mechanism is the per-cell loop-crossover mark.
   Out of scope for an art+collision first cut, but it is why some S2 loops will not behave.
6. **A second act's BG animation.** Already booked: `docs/DEFERRED_WORK.md:3841-3880` — two
   acts of one zone emit the same section and the same `BgAnim_Table` symbols. Needs an owner
   ruling on ROM layout.

**Existing partial converters, and what they are actually worth:**

- `tools/convert_s2_mappings.py` — converts S2 **sprite** mappings, not level data. Precedent
  for "we convert S2 formats", nothing reusable here.
- `tools/import_sk_collision.py` (95 lines) — the template for an S2 collision-bank importer.
  Reads three fixed-size files, writes five ROM tables to `data/collision/` and
  `data/collision/base/`. An `import_s2_collision.py` is a near-copy.
- ~~`tools/donor_provenance.py` — knows exactly two donors.~~ **DONE 2026-09-17:** it knows
  four. Both S2 trees are registered with `contributes_to_rebake=false`, because no committed
  byte comes from either yet and recording them without that flag would read as a claim that a
  re-bake used them.
- ~~**`tools/megaact_window_pageset.py` is the real prize.**~~ **DONE 2026-09-17 (parcel 1).**
  Its `_load_s2` was promoted into `tools/s2_donor.py`, which is now THE Sonic 2 donor loader,
  reads BOTH donor trees with the donor named explicitly per call, and covers nine final-game
  zones (WFZ added) plus the prototype's ten. `megaact_window_pageset` imports it; its `control`
  mode still reproduces the committed OJZ bake cell-for-cell (589,824 cells, 0 differing). All
  nine final-game grids reproduce byte for byte — see the prototype-formats note §7 for the
  method.

---

## 2. The clip operation

### 2.1 What a clip has to carry

A clip is a rectangle of one zone. To be pasteable it must carry, per cell:

- the **nametable word** (tile index within the source zone's tileset, plus flip bits, palette
  line, priority bit);
- the **source tileset identity** — which zone's art blob that tile index means. This is the
  "per-cell tileset key" of §1.3 item 1. Without it, two zones' tile index spaces collide
  silently;
- the **collision cell word** for plane A and plane B (shape, flips, solidity, crossover mark);
- and per clip rather than per cell: the **source zone's palette** and a **background
  reference**.

### 2.2 Alignment: what the grids force

- Sonic 2's native quantum is the **128-px chunk**. A layout byte is a chunk.
- Aeon's storage quantum is the **2048-px section** (256×256 tiles), and a section is one file.
- Aeon's streaming quantum is the **128-px block** (16×16 tiles) — `TileCache_DecompressBlock`
  resolves the section and its dictionary per block (`engine/level/tile_cache.emp:466-513`).
- Aeon's **region** quantum is one world pixel: regions are arbitrary rectangles, proven by
  OJZ act 1's night region at x 3400..4799, deliberately straddling the section line at 4096
  (`games/sonic4/data/levels/ojz/act1/act_descriptor.emp:606-607`).

**Recommendation: snap clips to 128 px on both axes (the chunk/block grid), and snap each
clip's PLACEMENT in the act to a 2048-px section boundary.**

- 128-px snapping is free: it is both games' natural quantum, and it means no clip edge ever
  cuts a chunk in half, so collision and art stay coherent cell-for-cell.
- Section-boundary placement is not free but is worth it: aeon interns a **per-section local
  tile map** of at most 2047 entries (`tools/ojz_strip_gen.py:815-843`), and ~~the page placer's
  multi-zone rung builds **pages that never mix two zones**
  (`tools/fg_page_order.py:526-554`). A clip straddling a section boundary puts two zones'
  tiles into one section's local map and defeats that.~~ It also means each clip's world
  rectangle is exactly the region rectangle you want for its palette (§5).
- Finer placement than a section is *possible* (regions are pixel-granular) and should be left
  available — but it should be the exception, not the default.

> **CORRECTED 2026-09-17 by parcel 3, which MEASURED both halves of that bullet.**
> `python3 tools/clip_act_bake.py measure-alignment` — two 1024×1024 clips, EHZ and CPZ, in a
> 2×1-section act, three placements of the same cells:
>
> | placement | sections used | local maps | pool | pages | worst window |
> |---|---|---|---|---|---|
> | separated, one zone per section | 2 | 394 / 224 | 617 | 10 | 7 of 12 |
> | adjacent, one zone per section | 2 | 394 / 224 | 617 | 10 | **9 of 12** |
> | adjacent, both inside section 0 | 1 | 617 / 1 | 617 | 10 | **9 of 12** |
>
> Row 2 is the control for row 3: the clips touch in both, so "a camera window can hold two
> zones" is held fixed and the only thing that varies is whether the section boundary falls
> between them. **The page budget is the same either way.** The struck sentence is wrong on
> both counts: `perzone_pages` groups by the per-CELL zone key, not by section, so a
> straddling clip does not defeat it; and the page-budget difference in the table is
> ADJACENCY (row 1 → row 2), which is §9.1's corridor argument, not an alignment argument.
>
> What section alignment does buy is the local-map column, and that part stands: a section
> carries ONE 11-bit local tile map capped at 2047 entries, and a section holding two zones
> needs the sum of both. So the recommendation survives as the DEFAULT — `clip_manifest`'s
> R11 refuses an unaligned `dst_rect` unless the clip carries an `unaligned_dst_reason`
> string — while "two zones in one section" is a WARNING (W3) rather than a refusal, because
> the exact limit is downstream and precise and this one is a cost, not an error.
>
> The 128-px bullet also survives only as a warning at parcel 3 (W1): on the ART path a
> nametable word is per cell and nothing cares. Its evidence is collision-side, so promoting
> it to a refusal is row 5's call. The one alignment rule that is HARD and that this section
> did not state is **8 px**: an editor section file is a grid of 8-px cells and has no
> sub-tile addressing at all (R6).

> **RULED 2026-09-17 by row 5, and the 128-px premise was FALSE.** "128-px snapping is free
> ... no clip edge ever cuts a chunk in half, so collision and art stay coherent" reads as
> if a chunk were the unit collision is authored in. It is not. **A chunk is 8×8 independent
> BLOCK PLACEMENTS and every placement carries its own entry word** — its own block id, its
> own flips, its own two solidity nibbles — so a cut between two blocks inside a chunk
> severs nothing, and a cut at a chunk boundary is not special. W1 is RETIRED (its tag kept
> reserved in `tools/clip_manifest.py`'s header with the false premise recorded).
>
> **The quantum that does bind is the BLOCK, 16 px, and it binds on the paste SHIFT rather
> than on the src origin.** DERIVED from the runtime, not from either file format: a
> collision cell's height profile is 16 bytes covering a 16-px block and `probe_core`
> selects the column with `andi.w #$F, d0` on the **world** x
> (`games/sonic4/player/player_sensors.emp`), while the collision ROW is the world tile row
> halved (`engine/level/collision_lookup.emp` `lsr.w #1`). The geometry a cell describes is
> therefore anchored to its own world position mod 16. Move it 8 px and every probe reads
> the wrong half of a profile — **silently**, because the art, one word per 8-px cell, moves
> correctly: the failure is ground 8 px out of place, which no screenshot shows.
>
> So **R12** replaces W1: `dst origin - src origin` is a multiple of 16 px in both axes, a
> refusal with NO opt-out, because unlike R11 there is no argument to be made. Note it is a
> rule about the shift: a 16-px-aligned src pasted to a 16-px-aligned dst is correct, and so
> is an 8-px-aligned src pasted 2048 px away.

### 2.3 What happens at the cut edges

**Collision continuity.** Because collision is stored per 8×16-px cell and resolved by absolute
world position (`engine/level/collision_lookup.emp:27-85`), a cut edge has no special meaning to
the engine — the cells simply stop. The player walking off the right edge of a clip walks into
whatever the next cell says. So the cut itself is safe; **what is unsafe is what the author
leaves next to it.** Two concrete cases:

- A clip cut mid-slope leaves a vertical wall of whatever height the last column had. Fine if
  intended, a soft-lock if not.
- A clip cut across a loop or an overpass severs the path-A/path-B pairing. Aeon's crossover
  encoding is per-cell and paired (`docs/LOOP_CROSSOVER_ENCODING.md` §3.3), and
  `apply_editor_collision_overlay` REFUSES a self-mark (`tools/ojz_strip_gen.py:1821-1834`).
  ~~**A clip whose marquee cuts a loop in half will fail the bake**, loudly.~~
  **WRONG, and row 5 built the refusal that makes it true (2026-09-17).** R2 refuses a
  SELF-MARK — a plane-A cell carrying `XOVER_TO_A`. Cutting a loop in half produces a
  perfectly well-formed mark whose PARTNER is simply absent, which R2 cannot see and
  which nothing else saw either: `collision_xover_census.py` reports pairing but is a
  census, not a gate. Nor is the thing a rectangle cuts the per-cell pair — that is one
  cell on two planes and a rectangle clips both identically. What a cut really removes is
  the loop's OTHER crossing (act 1's eight paired indices are two BANDS of one column,
  §3.3's bottom-centre and top-centre). **`tools/clip_act_bake.py` C1 is the refusal**, and
  it is conservative by necessity: the encoding records which PLANE a mark points at and
  never which LOOP it belongs to, so "the clip takes some of this zone's marks and leaves
  others" is the sharpest rule available, with an in-file `severed_xover_reason` opt-out
  in R11's style.

**Half-chunks.** With 128-px snapping there are none. Without it, a clip edge that lands
mid-chunk splits a 16-block group whose flip and solidity bits were authored as a unit; the
tile side survives (words are per cell) but the collision side needs the block re-baked from a
partial chunk. Not impossible, just a reason the snap is a good default.

**Air gutters between clips.** In the measurement of five whole zones laid out on section
boundaries, the natural padding (each zone is narrower than its section allocation) left gaps
of 164 tiles or more — wider than the 80-column camera window, so **no camera position ever
showed two zones at once**. That is accidental, and it is also, as §9.1 argues, the shape the
design should adopt on purpose.

---

## 3. Budgets, derived from the real pipeline

All numbers in this section are MEASURED by pushing donor data through aeon's own functions,
with the exact command lines given. They are measurements over **donor data through the
build-time pipeline**, not observations of a running engine.

Constants read from source at measurement time
(`engine/system/constants.emp:357, 380, 394, 405, 874, 875`):
`SECTION_SIZE = 2048 px`, `MAX_ACT_SECTIONS = 48`, `ART_POOL_PAGE_TILES = 64`,
`PAGE_FRAMES = 12`, `POOL_TILE_CEILING = 768`, `PAGE_TABLE_MAX = 256`.

### 3.1 Per-zone facts

```
python3 docs/research/s2-compressed-act/s2_clip_budget.py zones
```

| Zone | Camera box (px) | Painted extent (px) | Sections at 2048 px | Source tiles | Unique (deduped) tiles | Pages at 64 |
|---|---|---|---|---|---|---|
| EHZ | 10976 × 1024 | 10976 × 1016 | 6 × 1 = 6 | 634 | **480** | 8 |
| CPZ | 10432 × 2048 | 10432 × 2048 | 6 × 1 = 6 | 619 | **619** | 10 |
| OOZ | 12480 × 1888 | 12480 × 1840 | 7 × 1 = 7 | 483 | **483** | 8 |
| MTZ | 9152 × 2048 | 9152 × 2048 | 5 × 1 = 5 | 420 | **420** | 7 |
| WFZ | 16384 × 2048 | 12544 × 1408 | 8 × 1 = 8 | 846 | **832** | 13 |
| HTZ | 10560 × 2048 | 10560 × 2048 | 6 × 1 = 6 | 602 | 422 | 7 |
| CNZ | 10464 × 2048 | 10464 × 2048 | 6 × 1 = 6 | 698 | 512 | 8 |
| MCZ | 9408 × 1088 | 9408 × 1088 | 5 × 1 = 5 | 600 | 481 | 8 |
| ARZ | 10752 × 1248 | 10752 × 1248 | 6 × 1 = 6 | 605 | 605 | 10 |

Every zone fits in ONE section row (2048 px tall). WFZ's camera box is the full 16,384 px
because its `LevelSize` entry is the placeholder `$3FFF` (`s2.asm:14718`) — its real painted
extent is 12,544 × 1,408 px, so **WFZ's clip must be taken from the painted bounding box, not
the camera box.**

~~**WFZ is not in aeon's existing S2 registry.**~~ **DONE 2026-09-17 (parcel 1).** It is now a
registry row in `tools/s2_donor.py`, built the same way HTZ's supplement is: base art
`WFZ_SCZ.kos` with `WFZ_Supp.kos` overlaid at `ArtTile_ArtKos_NumTiles_WFZ_Main` = $0307
(`s2disasm/s2.asm:6492-6495`, `s2.constants.asm:2305`). The monkey patch that used to carry it
is deleted.

### 3.2 Clipping saves sections, not art

```
python3 docs/research/s2-compressed-act/s2_clip_budget.py clipsweep EHZ --secw 2 --sech 1
```

Unique tiles in a 2-section (4096 × 2048 px) clip, over every section-aligned position:

| Zone | min | median | max | whole zone (for comparison) |
|---|---|---|---|---|
| EHZ | 286 | 470 | **480** | 480 |
| CPZ | 549 | 569 | **591** | 619 |
| OOZ | 377 | 462 | **478** | 483 |
| MTZ | 407 | 418 | **420** | 420 |
| WFZ | 114 | 490 | **592** | 832 |
| HTZ | 375 | 384 | **419** | 422 |

Read the right-hand two columns together. **Taking a third of Emerald Hill costs you the same
480 tiles as taking all of it.** Classic Sonic zone art is heavily reused along the whole zone,
so a clip anywhere in the middle pulls in essentially the entire tileset. At 1 section
(2048 × 2048) the medians fall — EHZ 339, HTZ 276, WFZ 244 — but even then the *maximum* is
near the whole-zone figure.

**Consequence:** the VRAM art cost of this act is set by how many ZONES it contains, not by how
much of each you paste. Making the clips smaller to "fit more in" does not work for art.

### 3.3 Does the foreground art budget pass? Yes, at exactly the limit

This runs aeon's REAL Pass 4 placement (`fg_page_order.place_pool`, the function
`tools/ojz_strip_gen.py:2177` calls) and its real refusal.

> **2026-09-17, parcel 3: the tool had a pin-rule defect, and this table is UNAFFECTED — which
> was measured, not assumed.** `s2_clip_budget.mode_place` handed `place_pool` the raw
> `ojz_strip_gen.mark_pinned_pages`, which returns a `list[bool]`; `place_pool` wants page
> INDICES and `generate()` wraps it. The candidate set became `{False, True} - {0}` = `{True}` =
> page 1, so any act with a pinned page pinned page 1 and could pin nothing else. **No page on
> any of the four acts below reaches the pin rule's 75%-of-sections threshold**, so the
> candidate set is empty either way and every row re-measured identically (5 whole zones:
> pins `[0]`, worst 12, 707 positions of 870,231 windows, both ways). On a SMALL act it does
> move: `place EHZ:1,0,1,1 CPZ:1,0,1,1` is worst **11** with the defect and **10** without.
> Fixed, with `--pins raw` reproducing the old behaviour the way `--profiles horizontal`
> reproduces the pre-parcel-1 collision figures.

```
python3 docs/research/s2-compressed-act/s2_clip_budget.py place \
    EHZ:0,0,6,1 CPZ:0,0,6,1 OOZ:0,0,7,1 MTZ:0,0,5,1 WFZ:0,0,8,1 --rowlen 32
```

| Act | Sections | Pool tiles | Pages | Shipped order's worst window | Searched order's worst | Windows over budget | Verdict |
|---|---|---|---|---|---|---|---|
| 5 whole named zones, section-aligned | 32 of 48 | 2,830 | 46 | 18 of 12 | **12 of 12** | 0 of 870,231 | **PASSES** |
| same, tight-packed (real seams) | 30 of 48 | 2,830 | 46 | 18 of 12 | **12 of 12** | 0 of 815,447 | **PASSES** |
| 6 zones (HTZ standing in for HPZ), 2 sections each | 12 of 48 | 2,965 | 50 | 16 of 12 | **12 of 12** | 0 of 322,391 | **PASSES** |
| all 9 zones with a layout, 2 sections each | 18 of 48 | 4,502 | 75 | 16 of 12 | **12 of 12** | 0 of 486,743 | **PASSES** |

Four things to take from this table:

1. **The default page order fails every one of these acts** (worst 16-18 against a budget of
   12). Only the "searched" rung — per-zone dedupe, per-zone pages, Hilbert first-use order,
   then a swap search — fits them. That rung exists and is wired into the bake, and there is a
   hard refusal if it cannot fit (`tools/fg_page_order.py:632-646`). This is the machinery
   `STITCHED-ACT-PAGE-ORDER` delivered on 2026-09-17; report 09 measured S2 junctions going
   from worst 17 / 10,296 windows over to **12 / 0** with it
   (`docs/research/megaact-bg-streaming/09-page-order-candidates.md:33`).
2. **Every act lands at exactly 12 of 12, never below.** 707 window positions sit at 12 in the
   five-zone act, 4,762 in the six-clip act. There is no headroom, and the count explicitly
   excludes object art, the background plane, animated tiles, in-flight decodes and eviction
   order under motion (`tools/fg_page_order.py:75-78`). A static pass at the budget is
   necessary for no camera soft-lock, not sufficient. **This wants a runtime confirmation and
   is TAGGED for foreground follow-up.**
3. `PAGE_TABLE_MAX` is 256, so 46-75 pages is comfortable.
4. Section count is not the binding constraint. Even the whole-zone act uses 32 of 48.

### 3.4 ROM cost

The committed OJZ pool compresses 19,584 raw bytes to 11,964 ZX0 bytes, a ratio of 0.611
(MEASURED). Scaling by that ratio (INFERRED — the real ratio depends on the actual tiles):

| Act | Pool tiles | Raw pool | ZX0 pool (inferred) | Against `art_rom_report.py` budget |
|---|---|---|---|---|
| 5 whole zones | 2,830 | 90,560 B | ~55,300 B (54 KB) | soft 24 KB **exceeded**, hard 64 KB ok |
| 6 clips × 2 sections | 2,965 | 94,880 B | ~58,000 B (57 KB) | soft **exceeded**, hard ok |
| 9 clips × 2 sections | 4,502 | 144,064 B | ~88,000 B (86 KB) | **hard 64 KB EXCEEDED** |

Budget defaults are `ART_ROM_SOFT_KB = 24.0` / `ART_ROM_HARD_KB = 64.0`
(`tools/art_rom_report.py:38-39`), overridable per act by env var (`:122-123`) and described in
the file as "generous now, tightened when real acts exist" (`:27`). So the six-zone act needs
the soft budget raised and clears the hard one; a nine-zone act needs the hard budget raised
too, which is an owner call, not a tool flag someone sets quietly.

Separately, the section block stream: OJZ's 9 sections total 52,934 bytes of block blobs, a
mean of 5,881 B per section. At that mean (INFERRED, linear scaling): 12 sections ≈ 69 KB,
30 sections ≈ 172 KB, 48 sections ≈ 276 KB. That is the larger ROM item and it scales with
sections, so it is the other reason to clip.

### 3.5 The collision budget — the one that actually fails

> **CORRECTED 2026-09-17.** Every count in this section was interned off
> `Collision array - Horizontal.bin` — the ROTATED array — where `bake_cell`'s `profiles`
> argument means the per-column HEIGHT array (`Collision array - Vertical.bin`, which is what
> `collision_pipeline.load_donor_collision` reads for the shipping bake). Corrected, the
> headline figures are **299 (over by 44)**, **130 (FITS)** and **276 (over by 21)** where this
> section says 301, 131 and 278. No conclusion here changes. `s2_clip_budget.py` now defaults
> to `--profiles vertical`; pass `--profiles horizontal` to reproduce the numbers as printed
> below. And with the REAL Hidden Palace rather than the Hill Top stand-in, the six-zone
> figures are **worse**: 353 (over by 98) at two sections a clip and 199 (fits) at one — see
> the prototype-formats note §4.

Aeon interns every distinct `(height profile, angle, solidity, crossover)` into a **single
attr set shared by the whole act**, capped at **255** entries
(`tools/collision_pipeline.py:224-228`, one set per act at `tools/ojz_strip_gen.py:2107`).
Today's shipped act uses 63 of 255.

Baking Sonic 2's own chunk words through aeon's own `bake_cell`, over every chunk each act-1
layout references (MEASURED):

| Scope | Attr-set entries needed | Against the 255 cap |
|---|---|---|
| EHZ alone | 105 | fits |
| CPZ alone | ~~162~~ **160** | fits |
| OOZ alone | 67 | fits |
| MTZ alone | 62 | fits |
| WFZ alone | 108 | fits |
| HTZ alone | 122 | fits |
| **5 whole named zones** | **301** | **over by 46** |
| **6 whole zones (HTZ for HPZ)** | **329** | **over by 74** |
| all 9 whole zones | 427 | over by 172 |
| 6 zones clipped to the first 2 sections each | 278 | over by 23 |
| **6 zones clipped to the first 1 section each** | **131** | **fits** |
| 5 zones clipped to the first 2 sections each | 242 | fits |

And over clip POSITION (2-section clips, every section-aligned position):

| Zone | entries needed by the clip alone: min / median / max |
|---|---|
| EHZ | 24 / 86 / 104 |
| CPZ | 2 / 143 / 158 |
| OOZ | 5 / 49 / 67 |
| MTZ | 9 / 43 / 62 |
| WFZ | 8 / 67 / 96 |
| HTZ | 7 / 103 / 116 |

Union of one 2-section clip per zone, picking the cheapest / median / most expensive clip of
each: **6 zones → 37 / 283 / 322** entries. So a six-zone act at 2 sections per zone fits or
fails **depending on which rectangles the author marquees**, which is the strongest argument in
this document for putting the number in front of the author in the editor (§8).

*Method note, stated so it can be checked:* the counts walk every cell of every chunk the
layout references, deduped by chunk word, through `collision_pipeline.bake_cell` with S2's own
shape and angle tables. A second, independently written measurement over the same data landed
within about 10% per zone and reached the same verdict at every scope. The "clipped to the
first N sections" rows use the leftmost N sections as a representative clip, not a bound.

> **2026-09-17, row 5 — this table's per-zone row for CPZ was stale, and the six zones
> now have measured emitted counts.** The correction note at the top of this section moved
> the three headline figures from the horizontal array to the vertical one but left the
> per-zone table alone; CPZ is **160** on the vertical array, not 162. EHZ 105, OOZ 67,
> MTZ 62, WFZ 108 and HTZ 122 all reproduce unchanged. And the counts are no longer only a
> prediction: `tools/s2_zone_convert.py` emits both collision planes per zone and
> `zone.json` carries the attr-set cost, and all six EMITTED counts equal the predictor's
> through two code paths that share nothing but the shape bank — EHZ 105, CPZ 160, HPZ
> 152, WFZ 108, OOZ 67, MTZ 62.
>
> **One caveat on using `collision <ZONE>:<s0>,<n>` as a per-CLIP predictor: that spec has
> no vertical extent.** It counts every chunk its COLUMN range references, over every row
> of the layout grid, where a clip is a rectangle. It happens to agree for the tracked
> fixtures because those clips are full-height, and it agrees at whole-zone scope even for
> the two zones whose grids reach below their camera-box crop (EHZ's below-crop chunks are
> chunk 0 = air; OOZ's are real chunks, 180-186 among them, and both cropped and uncropped
> counts are 105/105 and 67/67 — the below-crop chunks reuse shapes the crop already
> needs). A clip shorter than its zone's grid is a different rectangle and
> `tools/clip_act_bake.py`'s per-clip number is the one about the bytes.

**Ways out, for the owner to choose between (§9.3):** clip harder; widen the attr field from
one byte to two (a per-cell storage change touching the block format and the runtime lookup);
merge near-identical shapes with a tolerance; or give each region its own 255-entry bank
(a real engine change — the bank is act-wide today).

---

## 4. What the act would actually look like

Two candidate shapes, both measured above.

**Shape A — "the guided tour", 6 clips of 1-2 sections each.**
12-18 sections of 48. Each clip is one recognisable set-piece: Emerald Hill's first hill and
loop; Chemical Plant's tube drop; Oil Ocean's fans; Metropolis's screws; Wing Fortress's
platforms; and a sixth (see §6 on Hidden Palace — no longer blocked). Art pool ~2,965 tiles /
50 pages, passing at 12 of 12 *(the real six, with prototype HPZ: 2,959 tiles / 50 pages, still
12 of 12)*. Collision fits at 1 section each (131 entries; **199** with the real HPZ) and is
position-dependent at 2 sections
each (37-322 entries). ROM ~57 KB pool + ~70-105 KB block stream (inferred).
**This is the recommended shape.**

**Shape B — "five whole zones".**
30-32 sections of 48, and measurably legal for ART (0 of 870,231 windows over budget). But
collision needs 301 entries against a cap of 255, so it cannot be built today without one of
§3.5's four changes. Worth knowing it is this close, because it means "compressed Sonic 2"
could later mean *most of* Sonic 2, not just six postcards.

In both shapes the natural layout is a single horizontal section ROW — every zone is at most
2048 px tall, and a 1-row act keeps the camera's vertical behaviour trivial. A vertical stack
is the alternative and has one real advantage (§9.1).

---

## 5. Palette, background, and the seam

### 5.1 The good news: per-region palettes already ship

A region names an effects preset; the preset carries the palette; crossing a region boundary
installs it, with a snap or a 16-frame cross-fade
(`engine/structs.emp:136`, `engine/effects/preset.emp:58, 420-422`,
`engine/effects/palette.emp:285-311`, `engine/level/parallax.emp:1263`). The shipped proof is
OJZ act 1's night region (row 9, x 3400..4799), whose palette is a comptime grade of all 48
entries. A DEBUG region already carries **Oil Ocean Zone's background** with its own layout and
its own tiles (`act_descriptor.emp:752-758`). So "six zones, six palettes, six backgrounds" is
not new engine work — it is authoring plus per-region BG tile budget
(`BG_REGION_STATIC_TILE_BUDGET` = 320 tiles, `act_assets.emp:77`).

### 5.2 The catch: regions carry palettes, but the editor cannot author them

`regions.json` has no palette key; `project.json` gives one palette per zone; the authored
`palette.bin` is a single 96-byte file per act. Six palettes today means six hand-written
`pub data` blobs plus six presets in `games/sonic4/data/effects/ojz_effects.emp`. That is a
tractable authoring parcel, not an engine one.

### 5.3 The real blocker: Sonic 2 zones do not agree on which palette line the ground is

Measured directly, over every non-blank foreground cell:

| Zone | Palette lines used by the foreground |
|---|---|
| **aeon OJZ act 1** | **line 2 only** (all 46,211 painted cells) |
| EHZ | line 1 (4.3%), line 2 (95.1%), line 3 (0.5%) |
| CPZ | line 0 (0.6%), line 1 (9.7%), **line 3 (89.7%)** |
| OOZ | line 2 (59.9%), line 3 (40.1%) |
| MTZ | line 1 (1.8%), line 2 (0.3%), **line 3 (98.0%)** |
| WFZ | line 0 (0.1%), line 1 (15.8%), line 2 (1.5%), **line 3 (82.6%)** |
| HTZ | line 1 (4.2%), line 2 (95.6%), line 3 (0.2%) |
| CNZ | line 2 (48.3%), line 3 (51.7%) |

Three facts fall out:

1. Aeon's engine has **three** writable palette lines (1, 2, 3 — line 0 is the character's and
   the engine never writes it, `engine/effects/palette.emp:48-50`).
2. Each Sonic 2 zone's foreground spans **two to four** of them, and they disagree about which
   is the main one. CPZ and MTZ put ~90-98% of the ground on line 3; EHZ and HTZ put ~95% on
   line 2.
3. CPZ (0.6%) and WFZ (0.1%) reference **line 0**, which aeon never writes, so those cells will
   render in the character's colours. Small, but visible, and it needs a decision.
   **Independently reproduced and made exact by parcel 2 (2026-09-17):** CPZ **698** painted
   cells of 112,906 (0.62%) in the final donor and **680** of 112,136 (0.61%) in the prototype;
   WFZ **104** of 101,812 (0.10%). Every other zone of both donors is **zero** — the whole
   defect in the six-zone act is 802 cells. The converter does NOT remap them (it would be the
   palette-bit rewrite §9.1(b) is rejected for, and it would pre-empt this decision); it counts
   them per zone and per section into `zone.json` and warns. **The decision is still open**, and
   it is now a small one: 802 cells to repaint by hand, to hide behind geometry, or to accept.

**Therefore two Sonic 2 zones cannot be correct on screen simultaneously.** A region crossing
installs one 96-byte palette covering all three lines; the moment the camera window straddles
two clips, one of them is wrong. The camera window is 80 tiles wide (640 px), so "straddling"
means a 640-px zone of wrongness at every seam.

**What cannot fix it:** the raster palette machinery. `OP_PAL_REGION` streams at most 3 colour
words per interrupt fire (`engine/effects/raster.emp:128-137`), so one full 16-colour line takes
6 consecutive scanlines and all three lines take about 16. That is usable for a *horizontal*
band boundary and useless for a *vertical* seam, since raster changes are per-scanline. And it
would consume the whole 2-slot variant staging (`engine/effects/palette.emp:339`).

**What can fix it** — three options, priced in §9.1.

---

## 6. Hidden Palace Zone — ~~BLOCKED~~ UNBLOCKED 2026-09-17

> **SUPERSEDED.** The owner ruled `prototype-donor` the same day
> (*"look for simon wai beta disassembly"*). `/home/volence/sonic_hacks/s2-simonwai-disasm` is
> cloned read-only at `0113ca47`, and Hidden Palace loads completely through
> `tools/s2_donor.py`: 700 blocks, 256 chunks, 725 art tiles, 561 canonical tiles, 9 pages,
> 152 collision attr-set entries, painted 9216 x 2048 px, and a foreground that is **97% on
> CRAM line 2** — the most aeon-shaped of the six zones the owner named. Option (c) below was
> taken and it cost one parcel, not a project. The rest of this section is kept because its
> account of what `s2disasm` does and does not hold is still exactly right, and it is the
> reason the second donor exists.

I re-derived this rather than take it on trust, and the conclusion is stronger than "probably".

**What `s2disasm` has for HPZ:** palettes (`art/palettes/HPZ.bin`, underwater, and two cycles),
music (`sound/music/90 - HPZ.asm`), object layout (`level/objects/HPZ_1.bin`, `HPZ_2.bin`), ring
layout, start position, and a lot of live code — palette cycling (`s2.asm:2826`), camera init
(`:14967`), scroll (`:16107`), level events (`:21281`).

**What it does not have:**

- No entry in `level/layout/` — the directory holds 20 files and none is HPZ (MEASURED).
- No `mappings/16x16/HPZ.*`, no `mappings/128x128/HPZ.*`, no `art/kosinski/HPZ.*`.
- **No collision.** `s2.asm:89589-89591`:
  `ColP_HPZ:  ;BINCLUDE "collision/HPZ primary 16x16 collision index.kos"` — the include is
  **commented out**, and the file does not exist. `ColP_HPZ` and `ColS_HPZ` therefore resolve
  onto the next label's address.
- `SonED2 Projects/hpz1.sep` exists but is a stub pointing at Oil Ocean's mapping files.

~~**And there is no beta disassembly anywhere under the suite root**~~ — true when written; the
owner cloned one the same evening. Acquiring donor material was his call, not a subagent's,
which is why this paragraph stopped at reporting the absence.

**What HPZ would need, if the owner wants it:**

1. A Simon Wai (or Nick Arcade) prototype disassembly added as a fourth donor project, with the
   owner's say-so on provenance. **DONE:** `s2-simonwai-disasm`, owner-ruled 2026-09-17.
2. From it: the HPZ layout, its 16×16 and 128×128 mappings, its Kosinski tile art, and its
   collision index. The final ROM's `HPZ.bin` palette can be reused as-is.
3. Tooling changes: a beta-specific registry row (the prototype's layout is a different size —
   the Simon Wai build predates the final layout format), and `suite_paths` / `donor_provenance`
   entries for the new donor.

**Options for the owner, in plain terms:**

- **(a) Substitute a zone.** Aquatic Ruin, Casino Night, Mystic Cave and Hill Top all have
  complete data here and all fit the budgets (§3.1, §3.5). Casino Night in particular is
  visually distinct from the other five. Cost: zero. This is the recommendation for the first
  cut.
- **(b) Use HPZ's palette and music over someone else's geometry** — a "Hidden Palace tribute"
  clip. Cheap, dishonest, probably not what he wants.
- **(c) Add the prototype donor.** Real work (a new donor project, a second layout format, a
  provenance decision) and it blocks the first playable act on an acquisition. Better as a
  follow-up parcel once the pipeline exists and HPZ is the only thing missing.

---

## 7. Where "region" means two different things

The owner said *"paste it in as a region or something."* In aeon today, **a Region is
presentation and identity only** — a world rectangle naming an effects preset (and so a
palette), an optional parallax override, and an optional background. Storage — tiles, blocks,
collision, objects, rings — stays on the section grid and a region never touches it
(`engine/structs.emp:74-77`).

So "paste as a region" splits into two operations that happen together:

- **Paste the geometry** into the section files (`section_N.tiles.bin`, `.collattr.bin`,
  `.collattrb.bin`) at the target world rectangle. This is an editor write.
- **Declare a region** over the same rectangle, naming the clip's preset (its palette) and its
  background. This is a `regions.json` row.

Both exist. Neither is the other. Calling the pair a "paste" is fine for the author; the design
just has to keep them distinct, because the first has a 255-entry collision cap and a
per-section local map behind it and the second has a whole-act coverage invariant behind it
(the region rows must not overlap and must sum to the act's area,
`act_descriptor.emp:938-945`).

---

## 8. The interface aeon must offer aurora

This is the contract, not a UI design.

**What aurora reads to show a converted Sonic 2 zone on a page:**

A converted zone should land as a normal aeon editor act tree, because then aurora already
knows how to render it. **Built by parcel 2 (2026-09-17), and the sketch below is corrected in
place** — it named a donor directory `s2/<zone>`, which cannot work now that two S2 donors are
registered and five zone names exist in both; and it claimed the shape mirrors aeon's own act
directory, which it does not:

```
games/sonic4/data/donors/<donor>/<ZONE>/     # <donor> = s2disasm | s2-simonwai-disasm
    tileset.bin                              # decompressed S2 art, 32 B/tile          [parcel 2]
    palette.bin                              # 96 B, the zone's 3 CRAM lines, verbatim  [parcel 2]
    section_<N>.tiles.bin                    # 256x256 big-endian nametable words       [parcel 2]
    section_<N>.collattr.bin                 # 256x256 big-endian collision cell words, plane A  [row 5]
    section_<N>.collattrb.bin                # plane B                                            [row 5]
    zone.json                                # grid w/h, extents, painted bbox, provenance, per-section counts  [parcel 2]
```

~~`zone.json` carries attr-set cost per section~~ — ~~it cannot until parcel 4 rules on the S2
shape bank, so parcel 2's `zone.json` carries the art-side counts (painted cells, distinct
tiles, CRAM-line-0 cells, per-file SHA-256) and not that one.~~ **DONE 2026-09-17 (row 5):
it does, per section and per zone**, plus the base bank it is indexed against and that
bank's sha256. The plane files carry AURORA's per-plane cell word — shape, flips, this
plane's solidity, crossover — and never the baked attr byte, because an attr byte is an
index into an ACT-wide 255-entry set and a donor zone is not an act. The transcode is
`collision_pipeline.chunk_entry_to_plane_words` and it is exactly equivalent to `bake_cell`
(measured over every distinct chunk-entry word of the six showcase zones).

**Where this differs from aeon's OWN act tree, transcribed from
`games/sonic4/data/editor/ojz/act1` and `project.json` rather than from this table:**

- ~~mirrors `games/<game>/data/editor/<zone>/<act>/`~~ — **there is no `tileset.bin` in an act
  directory.** The zone tile blob is whatever `project.json`'s `zones[].tileset` names, and it
  lives OUTSIDE the act dir (`games/sonic4/data/editor/ojz_tiles.bin`). `tileset.bin` is a name
  parcel 2 chose so a donor tree is self-contained; a project that wants to use one points
  `zones[].tileset` at it.
- `palette.bin` IS in the act dir, but because `zones[].palette` names it, not by convention.
- A real act dir also carries `regions.json`, `section_N.meta.json`, `section_N.objects.json`,
  `section_N.rings.json` and a vestigial `section_N.coll.bin`. A converted donor tree has none
  of them, and `validate_editor_inputs` does not want them.

Every one of those formats is already what `ojz_strip_gen` reads
(`tools/ojz_strip_gen.py:468-489`, `:1838-1841`), so aurora needs no new loader for the donor
page — only a way to open a tree that is not the project's own act. Parcel 2 confirmed that
end: `validate_editor_inputs(data_path, tileset_path, num_sections)` takes all three paths
explicitly, so a converted tree validates without touching `project.json` or the committed act.

**What aurora writes when the author marquees and pastes:**

1. **Into the target act's section files** — the clip's nametable words and both collision
   planes, at the target world rectangle. Straight writes to existing formats.
2. **Into `regions.json`** — one row for the pasted rectangle:
   `{id, name, rect:{x,y,w,h}, preset, bg:{layoutRef, span}}`. The `preset` names an `.emp`
   record; aurora validates it against the game's effects library
   (`tools/effects_gen.py:3686-3691`).
3. **Into a new clip manifest** — the one genuinely new file, and the answer to §1.3 item 1.
   **Built by parcel 3 (2026-09-17): `tools/clip_manifest.py`, and the sketch below is
   corrected in place.**

```jsonc
// games/sonic4/data/clips/<act id>/clips.json          [parcel 3]
{ "schema": 1,
  "id": "s2_two_clip",                      // names the act and its bake output dir
  "name": "free text",                      // optional
  "act": { "grid_w": 2, "grid_h": 1 },      // the act's SECTION grid, DECLARED not inferred
  "clips": [
    { "id": "ehz_loop",
      "donor": "s2disasm", "zone": "EHZ",   // ~~"donor": "s2/EHZ"~~ — two donor trees exist
      "src_rect":  { "x": 4096, "y": 0, "w": 2048, "h": 1024 },   // donor world px
      "dst_rect":  { "x": 0,    "y": 0, "w": 2048, "h": 1024 },   // act world px, same w/h
      "palette":   "OJZ_Palette_EHZ",       // optional, pass-through (rows 6/7)
      "region_id": "ehz_loop",              // optional, cross-ref into regions.json
      "unaligned_dst_reason": null } ] }    // optional R11 opt-out, see §2.2's correction
```

Four corrections, each with its reason:

- ~~`"donor": "s2/EHZ"`~~ — donor and zone are separate, separately validated fields. Two
  donor trees are registered and five zone names exist in **both**, meaning different levels.
- **`act.grid_w`/`grid_h` are declared, not inferred** from the clips' bounding box. An act
  with a trailing empty section is a different act: the camera-window sweep the art budget is
  counted over is a function of the grid (`fg_page_order.camera_windows`), so inferring it
  would make the budget depend on where the last clip happened to end.
- **`dst_rect` keeps `w`/`h` and they must equal `src_rect`'s.** A clip is a paste, never a
  scale.
- **There is no `tileset` field.** The tileset is `donors/<donor>/<zone>/tileset.bin` from
  parcel 2's tree, and the zone key is DERIVED: distinct `(donor, zone)` pairs in
  first-appearance order. Two clips of the same zone share a key, or the pool would carry
  that zone's art twice.

The bake (`tools/clip_act_bake.py`) reads `clips.json`, maps every cell of the act to its
donor zone, and hands `fg_page_order.place_pool` the per-cell tileset key it has been asking
for (`tools/fg_page_order.py:51-55`). Without this file there is no way to tell the placer
that two identical tile indices in two sections mean different art — **and there is no way to
represent the act at all**, because an editor word's index field is 11 bits, so one act-wide
tileset tops out at 2048 tiles against §0 item 2's 2,965 for six clipped zones. Multiple
tilesets are forced by the format, not chosen.

Aurora should validate, before writing: the donor is registered and the zone belongs to
**that** donor; every rect coordinate is a multiple of 8; `dst` w/h equal `src` w/h; the
`src_rect` is inside that zone's `crop_tiles` (NOT merely inside its padded section grid —
outside the crop there is only the converter's zero padding); no two `dst_rect`s overlap; and
the act grid contains every `dst_rect`. An unaligned `dst_rect` needs an
`unaligned_dst_reason`. `clip_manifest.load` refuses all of these by name (R1-R11) and warns
on three more (W1-W3), so the page can call it rather than reimplement it.

**What aeon must show back to aurora, per clip, so the author is not flying blind:**

- unique tiles and pages this clip adds to the act pool;
- **attr-set entries this clip adds** — the number from §3.5 that decides whether the bake
  refuses;
- the worst camera-window page count in the clip's neighbourhood;
- whether the marquee cuts a loop-crossover pair (which will fail the bake).

~~The first three are one function call each against code that already exists. The fourth is a
scan of the crossover marks in the source rectangle.~~

**ALL FOUR SHIP 2026-09-17.** Parcel 3 put tiles, pages and worst window in the bake's
`clipact.json`; row 5 adds the other two, and the attr-set item turned out to be row 5's and
not row 4's — it is a property of a baked CLIP, not of the shape bank. Per clip,
`clipact.json` `collision.per_clip` now carries `attr_entries_alone` (what this rectangle
needs on its own — the number to compare between two candidate marquees),
`attr_entries_added` (what it adds to the clips before it — the number that matters for the
act's 255), `solid_cells`, and the crossover census `marks_inside_src` /
`marks_outside_src`. The fourth item is a refusal and not only a readout (C1, §2.3), and the
cap is one too (C2): an act over 255 is refused with the per-clip breakdown attached, which
is the form the author needs — "you need 278, and `cpz_s2` alone is 148" rather than "it
overflowed".

---

## 9. What I think the owner should decide

### 9.1 The clips should not touch — and that is a feature

**The evidence:** §5.3. A region crossing swaps all three palette lines at once, and no two
Sonic 2 zones agree on which line the ground is. Any seam where two clips are visible at once
shows one of them in the wrong colours for the ~640 px the camera window spans.

**Three ways to live with it:**

- **(a) Put a transition between every pair of clips** — a corridor, a door, a tunnel, a short
  neutral stretch wider than the 640-px camera window. The camera never holds two zones. The
  palette cross-fade (16 frames, already shipped) plays *inside* the corridor and reads as
  intentional. Cost: about 1 section of filler per seam, ~5 sections for six clips, and some
  neutral art. **This is what I would do**, and it is also a better showcase — "compressed
  Sonic 2" as a hub of six doorways is a stronger demo than six zones butted together, and it
  makes the region machinery the star rather than a workaround.
- **(b) Re-quantise the art.** Remap each zone's tiles onto one palette line so all six share
  lines 1 and 3 and differ only on line 2. This is a lossy recolour of six zones' art and it
  also trips `verify_level_bin.py`'s bake-fidelity lane, which asserts the bake never rewrote a
  nametable word's palette bits (`tools/verify_level_bin.py:793-794, 967`). Expensive, and it
  makes the zones look wrong in a way people who know Sonic 2 will notice immediately.
- **(c) Stack the clips vertically and swap the palette per scanline band.** A horizontal seam
  *can* be raster-split. But `OP_PAL_REGION` moves 3 colours per fire, so all three lines take
  ~16 scanlines to change over, the 2-slot variant staging is fully consumed, and nothing like
  it has been built. Genuinely interesting, genuinely novel, and not where a first playable act
  should spend its risk.

**Flag for the owner:** (a) changes what he described — the clips would be connected by short
corridors rather than pasted edge to edge. I think it is a better version of his idea and the
evidence for it is in §5.3, but it is his call.

### 9.2 ~~Hidden Palace: substitute now, add the prototype later~~ — ANSWERED: prototype, now

§6. Recommend Casino Night or Aquatic Ruin for the first cut, and book the prototype donor as a
separate parcel that does not block anything.

### 9.3 The collision cap needs a ruling before parcel 4

§3.5. The four options, in ascending cost:

| Option | What it costs | What it buys |
|---|---|---|
| Clip harder (1 section per zone) | Less of each zone on screen | Fits today: 130 of 255 with the Hill Top stand-in, **199 of 255 with the real Hidden Palace** (2026-09-17). No code change, but only 56 entries of headroom. |
| Raise the soft/hard art ROM budget | A number in an env var, and the owner's agreement that the act is allowed to be big | Only fixes §3.4, not the collision cap |
| Merge near-identical shapes with a tolerance | A bake pass and a fidelity argument | Maybe 20-30% fewer entries (INFERRED, unmeasured); collision becomes approximate |
| Widen the attr byte to a word | Block format, runtime lookup, five ROM tables, every gate that reads them | 65,535 entries; whole zones become possible (Shape B) |

**Recommendation:** clip harder for the first cut, and measure the merge-tolerance option before
anyone proposes widening the field.

### 9.4 One-row or vertical-stack act

A single 2048-px-tall section row keeps camera behaviour simple and every zone fits it. Only
adopt a vertical stack if §9.1(c) is ever pursued.

---

## 10. Staged plan

Each parcel has one falsifiable check. Sizes are S (a day or less), M, L.

| # | Parcel | Size | Falsifiable check |
|---|---|---|---|
| 1 | ~~**Promote the S2 donor loader.**~~ **DONE 2026-09-17** — `tools/s2_donor.py`, BOTH donor trees, WFZ row added, both S2 donors registered in `donor_provenance`. | S | **PASSED: 9 of 9 zones byte-identical** (word grid and art blob), measured against a `git archive d234c084` export of the pre-promotion loader. |
| 2 | ~~**Whole-zone converter → editor tree.**~~ **DONE 2026-09-17** — `tools/s2_zone_convert.py`, both donors, all 19 zone/donor pairs. Art and layout only. Output `games/sonic4/data/donors/<donor>/<ZONE>/` (see the corrected §8 tree). | M | **PASSED, all 19 pairs: 6,317,248 cells round-tripped, 0 differing; 0 nonzero pad cells; 0 tile indices past any tileset; `validate_editor_inputs` accepted all 19 trees.** The reference side of the round trip is a second implementation of the chunk/block expansion, not the loader's, and its three branches are mutation-proven load-bearing. |
| 3 | ~~**`clips.json` + the per-cell tileset key.**~~ **DONE 2026-09-17** — `tools/clip_manifest.py` (schema 1, R1-R11 + W1-W3) and `tools/clip_act_bake.py` (compose → real `place_pool` with a real zone grid → emit → re-count off disk). Art and layout only. | M | **PASSED, with the check restated — see below.** Two tracked two-clip fixtures bake; placement verdict, recount-off-disk and `s2_clip_budget.py place` all agree, and 1,182 (zone, tile) pairs verify against their own zone's art. |

> **The row-3 check as written could not be run, and why.** It named `fg_page_order.check`,
> which reads **exactly one act**: `_known_acts` RAISES on any act whose generated dir is not
> `fg_working_set.GEN_DIR`, and `fg_working_set.Model` takes GRID_W/GRID_H from OJZ act 1's
> `act_descriptor.emp` (⚠ since parcel 9, 2026-09-17, it folds them THROUGH that file out of the
> generated `act_grid.emp`, which is where the numbers themselves now live; the one-act limit is
> unchanged). Pointing it at a second act needs a `project.json` entry and a
> matching `.emp` descriptor — a ROM change, which is rows 4-6, not row 3. So the count is
> run in `clip_act_bake` instead, importing the two functions `check` itself calls
> (`window_needed`, `budget_verdict`): the arithmetic is shared and only the decoding
> differs (`check` S4LZ-decodes `sec{N}_blocks.bin`; the bake reads `section_N.local.bin`,
> because a block file carries the collision planes and inventing collision bytes to reach a
> count is row 5's work, not filler for row 3). **Three numbers, not two:** the placement
> verdict, the recount off disk, and `s2_clip_budget.py place`. On `s2_two_clip` all three
> are 12 of 12 over 48,471 windows, 682 positions at the peak. On `s2_two_clip_pins` all
> three are 10 — **and that fixture exists because the first one cannot discriminate:** its
> answer is 12 whether the pin rule is wired correctly or not (see §3.3's note).
| 4 | ~~**Collision: the S2 base bank.**~~ **DONE 2026-09-17** (`parcel/s2-collision-bank`). `tools/import_s2_collision.py` writes the bank to `games/sonic4/data/collision/base_s2/`, regenerating the rotated table. `$18` ruled: keep the run's width, anchor RIGHT. | M | **PASSED, both halves.** 256/256 round-trip, no raise, 1 via the ruling. The second half was widened from a hand-picked slope to **3,612,672 probes** — every distinct chunk word of all six zones x 16 x-sub x 16 y-sub x both sensor classes — against a line-for-line transcription of `s2.asm:42942`/`43030`: 0 exit-kind, 0 angle, 0 distance mismatches. No emulator; the donor's lookup is re-implemented. |
| 5 | ~~**Collision: clip → `collattr.bin`.**~~ **DONE 2026-09-17** (`parcel/s2-clip-collision`). `collision_pipeline.chunk_entry_to_plane_words` + `tools/s2_zone_convert.py` (both plane files per donor zone, crop-masked like the art, attr cost in `zone.json`) + `tools/clip_act_bake.py` (clip → both act plane files, per-clip §8 readout, C1/C2/C3). Bank selection done: `load_base_bank(bank_dir)`. W1 RULED and retired; R12 replaces it. | M | **PASSED, both halves.** Six counts, six exact matches — `s2_two_clip` ehz_s2 95 / cpz_s2 148 / act 207, `s2_two_clip_pins` ehz_s1 62 / cpz_s1 148 / act 191, each equal to `s2_clip_budget.py collision` on the same rectangle, and each act re-counted off the emitted bytes. C1 refuses a clip that takes some of a zone's crossover marks and leaves others — a refusal that **did not exist**, because the §2.3 mechanism named for it (R2) catches self-marks, not severed ones. |
| 6 | ~~**★ FIRST THING ON SCREEN: a one-clip act.**~~ **DONE 2026-09-17** (`parcel/s2-first-clip-act`). `tools/clip_rom_bake.py` + `tools/elect_pool_pages.py` + build.sh's `S2CLIP` shape. The block stream exists: `sec{N}_blocks.bin` via `ojz_block_gen`, S4LZ v3, per-section dictionaries. **The palette half is BLOCKED** — see below. | M | **PASSED as far as a static check reaches, and the runtime half is TAGGED rather than claimed.** `S2CLIP=s2_ehz_boot ./build.sh` exit 0 -> `s4.s2clip.bin` 821,211 B (every build.sh gate green on the clip tree); `tools/landing_build.sh` exit 0 with the three canonical ROMs byte-identical. `verify_level_bin` all ten lanes on the clip tree: 589,824 nametable words and 589,824 collision cells carry what the converter emitted. The ground: spawn (256,256) DERIVED from `Camera_Init`, solid at y=656 by `probe_core`'s own arithmetic over the EMITTED ROM tables, surface y=671 — and Sonic 2's own `startpos/EHZ_1.bin` (96, 655) puts the player's feet at y=674 where our floor is at y=676, **2 px**, inside a derived 0..16 window a 16- or 8-px paste shift would miss. **No emulator was used**; "it renders" is a runtime claim and is tagged in the parcel report's §8. |
| 7 | **Two clips + a corridor.** Two zones, a neutral transition between them (§9.1a), two regions, two palettes, a cross-fade at the crossing. | M | No camera position holds cells from both clips (a static check over the placed act); the palette cross-fade fires exactly once per crossing. |
| 8 | **Three clips, and the budget gates.** Add the per-clip readout of §8 so the author sees tiles/pages/attr-entries before pasting. | M | `fg_page_order.check` green; `art_rom_report` within whatever budget the owner ruled in §9.3; attr set under 255. |
| 9 | **Six clips — the showcase act.** | L | The whole act passes `tools/landing_build.sh`, and a runtime pass confirms no camera hold at the worst window §3.3 identified. |

~~**First visible result: parcel 6.**~~ **THERE IS A ROM, 2026-09-17.** Parcels 1-5 were
pipeline with no picture, which was a real morale cost and was worth saying out loud; parcel 6
built `s4.s2clip.bin`. The suggestion below — pulling it earlier by hand-authoring the collision
in aurora — was not needed and would have cost the work twice, exactly as it warned.

**And the way it coexists with the shipped act is not what this document assumed.** §10 row 6
read as though a clip act would be a SECOND act. It is not, and cannot cheaply be: sigil places
the generated `.emp` modules by a FIXED registry path and `games/sonic4/map.toml` names their
head labels, so a second act needs a sigil registry change, a map.toml change and a second
`act_descriptor.emp` — all of which land bytes in the canonical ROM. A clip act is a THROWAWAY
in-place re-bake of the ONE act slot under an EXIT trap (build.sh's `STRESS_ART` shape,
generalised), which makes the canonical shapes byte-identical BY CONSTRUCTION. **The consequence
for the plan: a clip act inherits the shipped act's background, objects, rings, region table and
effects presets**, because all of those live outside the generated tree. Rows 7-9 own the first
three of those the moment a corridor needs its own.

**THAT LIST WAS INCOMPLETE, AND THE MISSING ITEM IS THE ONE THAT BIT** (parcel 7, 2026-09-17 —
`docs/research/s2-compressed-act/2026-09-17-clip-act-reachability.md`). A clip act also inherits
the shipped act's **EXTENT**: `clip_rom_bake`'s R21 forces the manifest to declare the
descriptor's grid, because `GRID_W`/`GRID_H` are hand-written in `act_descriptor.emp` and shared
with the canonical ROM. So `s2_ehz_boot` paints 4,096 × 1,024 px of a 6,144 × 6,144 px act, the
remaining sections are baked as air, and **at x = 4,096 the art and both collision planes stop
dead at a fixed world x** — the tile cache carries all three in the same block, so it is one
bound consumed twice. `EDGE_CLAMP` clamps the CAMERA to the act, not the player to the clip, so
the player walks off the painted world and falls its full height. ~~Widening the rectangle does
not fix it (EHZ act 1 has its own bottomless pit at x 4,672..4,863).~~ **WIDENING IS EXACTLY WHAT
FIXED IT — parcel 8, 2026-09-17** (`s2-compressed-act/2026-09-17-clip-act-full-width.md`), on the
owner's ruling: *"yeah just finish painting emerald hill out"*. `s2_ehz_boot` now paints
6,144 × 1,024 — the act's own width, three sections of three — so the painted world runs to the
camera's own clamp and there is no remainder to walk into. It cost pool 286 → 472 tiles of 768,
pages 5 → 8, worst camera window 5 → 8 of 12 frames, attr entries 66 → 105 of 255: everything
still fits, the window being the tightest. The pit at x 4,672..4,863 is real and did arrive with
the third section — 24 columns, art fully drawn, collision present and every cell an LRB-only
wall — and it is ACCEPTED rather than avoided, because Sonic 2 survives it with a level bottom
boundary at y = 800 and this engine has no death at all, which the owner already knew and set
aside. Avoiding it would have put the hard edge at x = 4,672 instead of 4,096: the same defect,
576 px right. `clip_reachability.py` gained a `floorless_columns` declaration (per plane, exact on
the count AND the runs) so the pit is checked rather than refused. ~~**A clip act should still OWN
its act extent** — the remainder is declared in `clips.json` (`unpainted_remainder`) and checked
on every S2CLIP build, and "fill the act" stops being available the moment an act is wider than
its donor, which row 7's corridor will be. Row 7+ owns that.~~ **DONE ON 2026-09-17 BY PARCEL 9**
(`s2-compressed-act/2026-09-17-clip-act-own-grid.md`), and not as row 7 work. `GRID_W`/`GRID_H`
are no longer hand-written in `act_descriptor.emp`: they are GENERATED from `project.json` into
`games/sonic4/data/generated/ojz/act1/act_grid.emp`, which is inside the tree the S2CLIP trap
restores, so **a clip act declares its own grid in its own manifest** and R21 is re-aimed to hold
the manifest to the grid the engine will compile rather than to the shipped act's. No canonical
byte moved (`s4.bin` md5 unchanged), and at the shipped 3 × 3 the clip ROM is byte-identical to
parcel 8's. The act is now **5 × 3 = 10,240 × 6,144 px** and the clip paints all 1,280 of its
columns. **The act paints every column it HAS and has fewer columns than the donor has
content — both halves.** EHZ's `extent.crop_tiles` ends at tile 1,372 (x < 10,976 px = **5.36
sections**) and R9 refuses a rect past it, so "EHZ is six sections wide" describes its PADDED grid,
not its painted content; six sections would leave 1,312 px UNPAINTED, which is the defect being
fixed, moved right. Five sections therefore **TRUNCATES 736 px (92 columns) of fully drawn Emerald
Hill** — measured on the donor's own `section_5.*.bin` (**7,745** art cells with a non-zero tile
index in 92 of 92 columns, 65.8% of the band; **3,036** collision cells with a non-zero shape index
per plane; 0 past the crop), 416 px of it inside Sonic 2's own camera box for the level. (Those
figures replace an earlier 11,776/3,304 that counted non-zero WORDS and so counted blank sky and
X-flipped empty collision as content; the conclusion is unchanged and the instrument is pinned to
`zone.json counts/painted_cells` — clip-act-own-grid §1.) A NON-section-aligned act extent is the only thing that recovers them. A SECOND Emerald Hill pit
came with the new ground, at x 9,472..9,663. **Owning the extent and filling the act turned out not
to be alternatives** — parcel 9 owns the grid and then fills it, which is both. What is still open
is a NON-section-aligned extent: the last 416 px of EHZ act 1 (Sonic 2's camera box reaches
x 10,656) is inside the crop but not inside a whole fifth section. **The act's HEIGHT is untouched:
nothing is painted below y = 1,024, 744 of the 768 columns have air below their last landing
surface, and there is no bottom boundary.**

---

## 11. Risks, stated plainly

1. **The palette seam (§5.3) is the one that could reshape the whole thing.** MEASURED, not
   suspected. If the owner insists on clips butting directly together, the answer is a lossy
   art recolour of six zones, and that is a much bigger and less pleasant parcel than the
   corridor.
2. **The art budget passes at exactly 12 of 12 with nothing in reserve** (§3.3), and the count
   omits object art, background, animated tiles and in-flight decodes. Object art is explicitly
   out of scope for the first cut, which conveniently postpones the problem — and guarantees it
   arrives later. **TAGGED for a foreground runtime check** once parcel 7 exists: no static pass
   proves the camera never holds.
3. **The collision cap (§3.5) fails for anything ambitious.** Six *whole* zones need 329 of 255.
   The fix is clipping, and clipping is position-dependent (a median-clip act needs 283, a
   cheapest-clip act 37), so the author can build something that refuses to bake and not
   understand why. §8's readout is not a nicety.
4. ~~**Nothing stitched has ever run.**~~ **PARTLY SPENT 2026-09-17.** A ONE-CLIP act is now a
   ROM (`s4.s2clip.bin`, parcel 6) and every number in §3 that it touches was reproduced through
   the ROM bake rather than the donor-side tool — including §3.2's own `min=286 canonical, 5
   pages` for a 2-section Emerald Hill clip, which the bake printed independently. **What is
   still true is the part that matters: nothing has RUN.** Parcel 6 used no emulator; its
   rendering claim is tagged for a foreground check, not asserted. And nothing STITCHED has been
   built at all — a one-clip act is an ordinary aeon act with one tileset, which is precisely why
   it was reachable. The stitched case starts at row 7.
5. **A second act's background animation has nowhere to live** —
   `docs/DEFERRED_WORK.md:3841-3880`, already booked, needs an owner ruling on ROM layout. It
   bites the moment the showcase is a second act rather than a replacement for OJZ act 1.
6. **A lot of tooling says "ojz".** 3,682 hits across 228 files; most is prose, but the real
   work is concentrated: `verify_level_bin.py:28` hard-codes the generated directory,
   `regenerate-level.sh:176` hard-codes the pool directory, nine files hard-code
   `zones[0]`/`acts[0]`, 16 tools name `OJZ_Act1_Descriptor` directly, `map.toml:133` lists
   seven OJZ head labels, and the boot path types the descriptor address five times in one game
   state. `tools/effects_gen.py` already takes `zone`/`act` parameters and derives every symbol
   name from the project ids — that is the pattern to copy.
7. **`verify_level_bin.py` asserts the bake never rewrites a nametable word's palette bits**
   (`:793-794, 967`). Any palette-line remap (§9.1b) trips exactly that lane. Good — it is the
   guard working — but it means option (b) is a lane change, not a data change.
8. **Two pieces of stale documentation found in passing**, both worth a one-line fix and neither
   part of this parcel: `docs/ENGINE_ARCHITECTURE.md:19`'s summary row still says "per-section
   full palette copies (128 bytes)" when the shipped mechanism is per-region, 96 bytes, 3 lines;
   and `docs/LEVEL_EDITOR_SPEC.md:9,64` says the `Act` struct is 34 bytes and `Sec` is 34 bytes
   when `engine/structs.emp:41,285` say 46 and 22.

---

## 12. Where I disagree with how the task was framed

The brief asked me to treat its framings as hypotheses. Three came out differently:

- **"Clips share the 48 sections, so budget the sections carefully."** Sections are not the
  binding constraint — even five *whole* zones use 32 of 48 (§3.3). The binding constraints are
  the 255-entry collision attr set (§3.5) and the palette seam (§5.3). Budget those.
- **"Clip small pieces so the showcase fits."** For ART, clipping buys almost nothing (§3.2):
  a third of Emerald Hill costs the same 480 tiles as all of it, and a 6-zone clipped act needs
  a *bigger* pool than a 5-zone whole act. Clipping is still right, but for the collision and
  ROM reasons, not the VRAM one. Worth telling the owner, because the intuition is natural and
  wrong.
- **"Paste it in as a region."** In aeon a Region carries no geometry (§7). The paste is two
  operations that must happen together, and conflating them would hide the coverage invariant
  the region table has to satisfy.

One instruction I could not carry out as written: the brief named six zones including Hidden
Palace, and Hidden Palace has no level data in this donor (§6). I measured five and used Hill
Top as a stand-in for the sixth wherever a six-zone figure was needed, and said so at each
figure. **Resolved 2026-09-17:** the owner added the prototype donor, and the real six-zone
act is measured in the prototype-formats note §4 — the art budget is unchanged (2,959 tiles,
50 pages, 12 of 12) and the collision budget is materially worse (353 over 255 at two sections
a clip, against the stand-in's 278).

---

## 13. Reproducing every number in this document

> **2026-09-17:** the worktree named below is gone (the design landed); run these from any aeon
> checkout. The `collision` and `collsweep` lines need **`--profiles horizontal`** to print the
> figures as published — the tool's default is now the correct `vertical` array, which prints
> 299 / 130 / 276. Every other line reproduces unchanged. Add `--donor s2-simonwai-disasm` for
> the prototype's zones.
>
> **2026-09-17, parcel 3:** `place` gained `--pins wrapped|raw` (default `wrapped`, the
> correct one). The §3.3 table reproduces unchanged under BOTH — see §3.3's note. Parcel 3's
> own commands, which need the converted donor trees
> (`python3 tools/s2_zone_convert.py convert --all-six`, ~0.5 s):
>
> ```bash
> python3 tools/clip_manifest.py validate games/sonic4/data/clips/s2_two_clip/clips.json
> python3 tools/clip_act_bake.py bake     games/sonic4/data/clips/s2_two_clip/clips.json
> python3 tools/clip_act_bake.py bake     games/sonic4/data/clips/s2_two_clip_pins/clips.json
> python3 tools/clip_act_bake.py measure-alignment          # the §2.2 correction, ~0.3 s
> python3 $S place EHZ:2,0,1,1 CPZ:2,0,1,1                  # N3 for s2_two_clip -> 12
> python3 $S place EHZ:1,0,1,1 CPZ:1,0,1,1                  # N3 for the pins fixture -> 10
> python3 $S place EHZ:1,0,1,1 CPZ:1,0,1,1 --pins raw       # the old wiring -> 11
> ```

> **2026-09-17, parcel 6 — the first bootable clip act.** Needs the converted EHZ tree and the
> two sigil env vars. The bake OVERWRITES the committed generated tree as a THROWAWAY and
> REFUSES to start over a dirty one (R22), so the `git checkout` line between runs is not
> optional; `build.sh`'s `S2CLIP` shape owns that restore itself through an EXIT trap.
>
> ```bash
> export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
> export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
> python3 tools/s2_zone_convert.py convert s2disasm@EHZ
> python3 tools/clip_rom_bake.py bake games/sonic4/data/clips/s2_ehz_boot/clips.json
> python3 tools/verify_level_bin.py \
>     --project games/sonic4/data/clips/s2_ehz_boot/baked/project.json \
>     --bank    games/sonic4/data/collision/base_s2        # the ten lanes, on the clip tree
> python3 tools/clip_rom_bake.py ground games/sonic4/data/clips/s2_ehz_boot/clips.json
> git checkout -- games/sonic4/data/generated games/sonic4/data/collision
> git clean -fdq -- games/sonic4/data/generated
> S2CLIP=s2_ehz_boot ./build.sh                            # -> s4.s2clip.bin
> ```
>
> `$S clipsweep EHZ --secw 2 --sech 1` above is the CROSS-CHECK for the bake: its
> `min=286 canonical, 5 pages` at `px [0,0]` are the two numbers `clip_rom_bake` prints, reached
> without going through a converted tree or a `clips.json` at all.

```bash
cd <your aeon checkout>
export PYTHONDONTWRITEBYTECODE=1
S=docs/research/s2-compressed-act/s2_clip_budget.py

python3 $S zones                                          # 3.1   ~0.4 s
python3 $S clipsweep EHZ --secw 2 --sech 1                # 3.2   ~1 s per zone
python3 $S place EHZ:0,0,6,1 CPZ:0,0,6,1 OOZ:0,0,7,1 \
                 MTZ:0,0,5,1 WFZ:0,0,8,1 --rowlen 32      # 3.3   ~1.1 s
python3 $S place EHZ:1,0,2,1 CPZ:1,0,2,1 OOZ:2,0,2,1 \
                 MTZ:1,0,2,1 WFZ:2,0,2,1 HTZ:1,0,2,1 \
                 --rowlen 12                              # 3.3   ~1 s
python3 $S window EHZ:0,0,6,1 ... --rowlen 32             # 3.3 shipped-order sweep, ~2.5 s

# 3.5 collision budget, through collision_pipeline.bake_cell and a cap-free AttrSet.
# "ZONE" means the whole zone; "ZONE:s0,n" means n sections starting at section s0.
python3 $S collision EHZ CPZ OOZ MTZ WFZ                  # -> 301, OVERFLOWS by 46
python3 $S collision EHZ:0,1 CPZ:0,1 OOZ:0,1 \
                     MTZ:0,1 WFZ:0,1 HTZ:0,1              # -> 131, FITS
python3 $S collision EHZ:0,2 CPZ:0,2 OOZ:0,2 \
                     MTZ:0,2 WFZ:0,2 HTZ:0,2              # -> 278, OVERFLOWS by 23
python3 $S collsweep EHZ CPZ OOZ MTZ WFZ HTZ --secw 2     # 3.5 per-position table, ~0.3 s

python3 $S pallines EHZ CPZ OOZ MTZ WFZ HTZ               # 5.3, ~1 s
```

Two figures in this document are NOT produced by that script and are named here so nobody
mistakes them for reproducible output. **The S&K-vs-S2 shape comparison of §1.3 item 2** (75 of
151 S2 shapes unreachable from the S&K flip closure) and **the rotated-heightmap sign
disagreement of §1.3 item 3** (211 of 256 shapes, all pure sign) came from a second, separately
written measurement over `collision_pipeline.rotate_profile` and the two banks. They are
directionally load-bearing — they are why parcel 4 exists — so parcel 4 should re-derive both
as its own first step rather than inherit them.

> **2026-09-17, parcel 4: both re-derived, and they are now reproducible.** The sign figures all
> hold; the reachability figure was **68, not 75**, and its illustration was false. See §1.3
> items 2 and 3 above, and `docs/research/s2-compressed-act/2026-09-17-s2-collision-bank.md`.
> Both are now a committed check with a gate behind it:
>
> ```bash
> python3 tools/import_s2_collision.py check          # reach + sign + roundtrip + findfloor, ~3 s
> python3 tools/import_s2_collision.py check reach    # 151 used, 68 unreachable
> python3 tools/import_s2_collision.py check sign     # 44 identical, 212 differ, all pure sign
> ```

>**2026-09-17, parcel 5 (row 5).** Collision now converts with the zones; these need the
> donor trees (`python3 tools/s2_zone_convert.py convert --all-six`, which also writes both
> collision planes and the attr cost into each `zone.json`):
>
> ```bash
> python3 tools/s2_zone_convert.py convert --all-six       # emits + verifies both planes
> python3 tools/clip_act_bake.py bake games/sonic4/data/clips/s2_two_clip/clips.json
> python3 tools/clip_act_bake.py bake games/sonic4/data/clips/s2_two_clip_pins/clips.json
> python3 $S collision EHZ:2,1        # -> 95,  the bake's ehz_s2 alone
> python3 $S collision CPZ:2,1        # -> 148, the bake's cpz_s2 alone
> python3 $S collision EHZ:2,1 CPZ:2,1   # -> 207, the act
> python3 $S collision EHZ:1,1 CPZ:1,1   # -> 191, the pins act
> python3 -m pytest tools/test_s2_clip_collision.py -q     # 33 rows, incl. the C1 refusal
> ```
>
> The whole-zone counts the converter emits are EHZ 105, CPZ 160, HPZ 152, WFZ 108, OOZ 67,
> MTZ 62, and `python3 $S collision <ZONE>` prints the same six. §3.5's per-zone table said
> 162 for CPZ; that was the horizontal-array figure and is corrected there.

Aeon's own foreground palette-line figure in §5.3 (all 46,211 painted cells of OJZ act 1 on
line 2) is a one-liner over the committed editor sections:

```bash
python3 -c "
import glob, numpy as np
h={}
for p in sorted(glob.glob('games/sonic4/data/editor/ojz/act1/section_*.tiles.bin')):
    w=np.frombuffer(open(p,'rb').read(),dtype='>u2'); nz=(w&0x7FF)!=0
    for a,b in zip(*np.unique(((w>>13)&3)[nz],return_counts=True)): h[int(a)]=h.get(int(a),0)+int(b)
print(h)"
```

Wall clock at measurement: 2026-09-17, dev box up 1 day 18 h, load average 1.3-5.8 across the
runs. No emulator was used and nothing was built.

---

*This report and its measurement tool were committed on `research/s2-compressed-act` as
`2b6a104` (the tool) and `07c7e10` (the report + the `S2-COMPRESSED-ACT` booking update).
No engine code, no `.emp`, no build change, and no emulator was used.*
