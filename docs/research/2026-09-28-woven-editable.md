# How far is the woven Sonic 2 act from being editable in aurora?

**Date:** 2026-09-28 (session clock 2026-09-27). **Branch:** `research/woven-editable`, base
aeon `origin/master` `9bff4c9a`. **Aurora read:** `origin/master` `6f13cd23`, through git
objects only (`git -C ../aurora show origin/master:<path>`). Aurora's own survey, relayed by
the controller, was at aurora `40ac2af9` (a descendant of `6f13cd23`); it is folded in as
**QUOTED (aurora survey)**.
**Status:** research only. No engine, tool, data, sigil or aurora file was changed. No
emulator was used.

**The owner's question:** *"how far off is this from being editable in aurora?"*, about
`games/sonic4/data/clips/s2_woven/clips.json` (8 clips, 6 Sonic 2 zones, 5 x 4 sections).

Tags: **READ** (file:line), **MEASURED** (a command in §7 printed it), **INFERRED**
(reasoning on read or measured facts; the sentence says which), **QUOTED** (someone else
measured it; named).

---

## 0. The answer in one screen

- **Placement is editable today; cells are not.** Aurora's Donors page already edits the
  act's *placement*, but only by appending clips to `clips.json`. It has no move, resize or
  delete. Aurora previews the bake and throws it away (**READ** aurora
  `src/core/formats/donors/clip-manifest-doc.ts:208`, `withClip`; **QUOTED** aurora survey).
- **Touching up the layout cell by cell (tiles, both collision planes) is a real project.**
  The aeon side is **M**, if the act stays in the one OJZ act slot. The aurora side is **L to
  XL** (QUOTED aurora survey). The aurora number is the long pole.
- **A premise to correct: the clip act does have an editor-shaped source.** It is not
  committed and it is not the format aurora's level editor reads. Every clip bake composes
  one first: `section_N.tiles.bin`, `.collattr.bin`, `.collattrb.bin` and a per-cell
  `section_N.zonekey.bin`, plus a staged `project.json` (**READ** `tools/clip_rom_bake.py:72-78`,
  `:2753-2820`). It then feeds that tree to the same `ojz_strip_gen.generate()` that bakes
  OJZ. It lands in the gitignored `clips/<id>/baked/` (**READ** `.gitignore:216`).
  - It is a **keyed** act: each cell names which zone's tileset it indexes. The generator
    already reads that form (**READ** `tools/ojz_strip_gen.py:142-164`). Aurora's *level
    editor* does not.
  - Aurora's *donor target pane* already draws it read-only, each cell through its zone's
    tileset and palette (**READ** aurora `src/renderer/components/donors/DonorTargetPane.tsx:9-12`).
- **There is one act slot, and adding a second one is L.** Everything is the OJZ act 1 slot.
  The recommended path keeps the woven act in that slot as a throwaway re-bake, as `S2CLIP`
  does today. The only change is that its cells come from a committed, editable tree
  instead of from Sonic 2 on every build.
- **Where hand edits live (aurora's question back): freeze the cells and keep the manifest
  for everything else (option iii, refined).** Reasons in §5.
- **Can we make it look like a one-zone act to aurora? Only partly.** Collision already has
  one bank for the whole act. Tiles and palettes cannot be flattened:
  - the pool has **2,877 distinct 8x8 tiles, more than the 2,048 an 11-bit index can
    address** (MEASURED);
  - the six palettes hold **119 distinct colours, and one act palette has 45 slots**
    (MEASURED).

  So the editor format should carry the **per-cell zone key, which already exists**. It
  should not carry a flat tileset or section-local maps (§6).
- **First useful step:** add `clip_rom_bake.py promote`, which writes one frozen snapshot of
  the composed woven act as a committed editor act tree with a provenance stamp. Then open it
  **read-only** through aurora's existing keyed renderer, the donor target pane (§4).

---

## 1. What "promote the woven act to an editable level" takes on aeon's side

### 1.1 What exists

| Piece | State | Tag |
|---|---|---|
| Composer that turns `clips.json` into an editor-shaped cell tree | Exists: `clip_act_bake.bake`. For s2_woven it writes 20 x (`tiles`, `zonekey`, `collattr`, `collattrb`, `local`) plus `corridor_sheet.bin` and `clipact.json` | READ `tools/clip_rom_bake.py:72-78`; MEASURED (§7, run into scratch) |
| Generator that reads a KEYED act (`tilesets: [...]` plus `section_N.zonekey.bin`) | Exists, in `ojz_strip_gen`, including validation of keyed inputs | READ `tools/ojz_strip_gen.py:142-164`, `:727-760` |
| Staged `project.json` that points the OJZ generators at such a tree | Exists; written on every clip bake | READ `tools/clip_rom_bake.py:2753-2820` |
| Throwaway re-bake into the OJZ slot, with the restore trap | Exists: `S2CLIP=<id> ./build.sh` | READ `build.sh:1072-1118` |
| Region rows, per-zone palettes and presets, BG lowering, BG blobs, layer lines, start | Exist, **derived from the manifest** by `clip_rom_bake` into `clip_act.emp` | READ `tools/clip_rom_bake.py:526-960`; `act_descriptor.emp:94-117` |

**INFERRED:** most of what "promote" needs is already built. What is missing is to *commit*
the composed tree and have the bake *read* it instead of recomposing it.

### 1.2 Is the editor format expressive enough? Piece by piece

| Donor content | Fits the editor format today? | Where it does not fit |
|---|---|---|
| **Two collision planes** | **Yes.** `section_N.collattr.bin` / `.collattrb.bin` are the same per-plane cell-word files OJZ uses (OJZ commits both, READ `games/sonic4/data/editor/ojz/act1/`). | The **bank** differs. Sonic 2 shapes index `collision/base_s2/`, and OJZ indexes S&K's `base/`. 68 of the 151 Sonic 2 shapes the six zones use cannot be expressed in S&K's bank (READ `tools/import_s2_collision.py:9-13`). The act uses **250 of 255** attr entries (MEASURED). The project file must name the bank per act. Today aurora assumes `base/` (QUOTED aurora survey). |
| **Art from 6 zones** | **Only in the KEYED form** (per-cell `zonekey` plus a `tilesets[]` list). The generator supports it (READ `ojz_strip_gen.py:142-164`). The level-editor format aurora reads has one `tileset` per zone (READ aurora `src/core/project/aeon/load.ts:531-534`). | A flat act tileset is impossible (§6). The Sonic 2 tilesets live in the **gitignored** donor trees (READ `.gitignore:205`), so a committed act has to commit copies of them. That is 6 sheets of 681 to 914 tiles plus the 37-tile neutral sheet (MEASURED). |
| **Per-zone palettes** | **Not as an editor file.** An editor act has one `palette.bin` (READ `project.json`, aurora `load.ts:547`). The clip path emits one palette per zone into `clip_act.emp` and installs it per region (READ `clip_rom_bake.py:868-936`). | The palette cannot be merged into one (§6). **INFERRED:** the palette key per cell is the zone key, so one sidecar solves both tiles and palette. |
| **Layer lines** | **Yes in shape.** `layer_lines.json` (`tools/layer_lines.py`) and the clip's rows are both `LayerLine` rows. | The clip derives them from Sonic 2's layer-switch objects in donor coordinates (READ `clip_rom_bake.py:719-775`). A frozen act can keep deriving them while the loops stay where they are, or commit them once as `layer_lines.json`. |
| **Region table** | **Almost.** `regions.json` rows are one rect plus a required `preset` plus an optional `bg`/`sceneRef` (READ `editor/ojz/act1/regions.json`, `tools/region_flatten.py` header, `tools/effects_gen.py:3671`). | The clip rows (`OJZ_CLIP_REGION_ROWS`) name **generated** per-zone presets and per-zone lowered BGs, which live in `clip_act.emp` and not in the bglib or effects tree that `regions.json` refs resolve through. **INFERRED:** the region rows stay manifest-derived (§5). They are a function of the zone key grid and the crossing rules, not a hand-painted document. |
| **Tall backgrounds and BG blobs** | **No.** An editor act has one `bgLayout`/`bgTiles` (READ `project.json`). BG per region comes through `regions.json` `bg.layoutRef` into OJZ's `ojz_bglib.json`. | The woven act's BGs are six lowered Sonic 2 backgrounds with tall-map chains, grouped into three blobs, all derived from the donor (READ `clip_rom_bake.py:1150-1300`). They stay manifest-derived. |
| **Objects and rings** | Not applicable: the clip act has `entities: none` (READ `clip_rom_bake.py:2805-2811`). | An editor act would carry empty `objects.json` / `rings.json` files. That is harmless. |
| **The act slot** | **One slot.** See §2. | |

---

## 2. A second act beside OJZ act 1?

**Not today. Everything is the OJZ act 1 slot** (the premise is right):

- **One `Act` instance:** `pub data OJZ_Act1_Descriptor: Act` (READ
  `games/sonic4/data/levels/ojz/act1/act_descriptor.emp:240`). No act table and no level
  select.
- **The boot hard-codes it.** `Game.entry = GameState_OJZScroll_Init` (READ
  `games/sonic4/config/game.emp:156`), which does `lea OJZ_Act1_Descriptor, a0` before
  `Level_LoadArt` and `Section_Init` (READ `games/sonic4/test/ojz_scroll_test.emp:642`, `:853`).
- **The placement names OJZ's heads** (`OJZ_Act1_Descriptor`, `OJZ_Sec0_Blocks`, ...), and
  the generated modules sit at fixed registry paths (READ `games/sonic4/map.toml:133`,
  `tools/clip_rom_bake.py:20-27`).
- **Collision tables are global, and there is one interned set per ROM.** The player's
  probes take `#HeightMaps` absolute (READ `games/sonic4/player/player_sensors.emp:215`,
  `:250`), and `struct Act` has no collision pointer (READ `engine/structs.emp:44-67`). OJZ
  uses the S&K bank and the woven act uses the S2 bank at 250 of 255 entries, so **one
  shared table cannot hold both** (INFERRED from MEASURED 250 plus any OJZ entries).
- **The generators are wired to one act:** `ojz_strip_gen` `OUTPUT_DIR`, `PROJECT_JSON`,
  `COLLISION_DIR` and `fg_page_order._known_acts` (READ `tools/ojz_strip_gen.py:85-102`,
  `tools/fg_page_order.py:782`; `clip_act_bake.py` header).

**What a real second act slot costs: L to XL, byte-moving, and cross-repo:**

- a per-act collision-table pointer in `Act`, and sensor code that reads it (engine plus
  player);
- a second set of generated modules and sigil registry and `map.toml` rows (ask sigil; do
  not assume);
- a second `act_descriptor.emp`;
- act selection (an act table or a level select);
- every per-act generator and gate parameterised by act (`ojz_strip_gen`, `fg_page_order`,
  `verify_level_bin`, staleness);
- about 313 KB more ROM for the woven act's level data (QUOTED woven report, v2.1 budget
  table).

**The woven act does not need this in order to be edited.** It can keep being baked into
the OJZ slot as a throwaway, exactly as `S2CLIP` does, with its cells read from a committed
editor tree (§4). The second slot belongs to the mega-act tech demo milestone, not to "let me
touch it up".

---

## 3. What promoting loses and what keeps working

**Lost, or changed in meaning, once cells are frozen:**

- **Re-derivation of cells from Sonic 2 on every bake.** A converter fix or a donor change no
  longer flows in by itself; a re-promote has to merge it.
- **"Collision == Sonic 2" as a guarantee.** `collision_baseline.json` lists the faithful
  Sonic 2 violations, keyed section-local, placed only inside donor clips (READ
  `clips/s2_woven/collision_baseline.json` `_comment`, `why`). After a hand edit that
  baseline describes the donor, not the act. The lane keeps running, but a hand-edited cell
  needs its own carve-out, and a new violation is an edit to review, not donor fidelity.
- **Moving a rectangle and having its content follow.** After a freeze, a rectangle edit in
  `clips.json` would silently do nothing to the cells, so it must be refused (§5).
- **The composer's independent cross-checks on the act cells:** N3 (the donor-side
  predictor), the per-clip collision rows, and `verify_art_fidelity` of (zone, tile) against
  the donor (READ `tools/clip_act_bake.py` header).
- **Aurora's donor-page paste into this act.** It writes `clips.json`, which no longer owns
  the cells.

**Keeps working, because it reads the cell tree or the manifest's per-zone facts and not the
composition** (INFERRED from READ `clip_rom_bake.py` steps 2-5 and the derivations listed
in §1.1):

- ROM bake steps 2-5: strips, local maps, pool pages, election, block stream;
- `verify_level_bin` aimed at the act's project (READ `build.sh:1162-1170`);
- the FG page budget N1/N2 (the 12-frame window, measured today at **12 of 12, 0 over**);
- the 255 attr cap;
- Z1 zone separation (it reads `zonekey`);
- the region plan (it walks zone labels);
- per-zone palettes and presets;
- BG lowering and blobs, and the crossing timings Z2;
- layer lines (while the loops stay put), the start, music and the anchor overlay.

---

## 4. Sizes, the recommended path, and the first step

### Aeon side

| # | Piece | Size | Notes |
|---|---|---|---|
| A1 | `clip_rom_bake.py promote <clips.json> --to games/sonic4/data/editor/s2woven/act1/`. Writes the composed cell tree (20 x `tiles` / `zonekey` / `collattr` / `collattrb`), copies of the 6 zone sheets, the neutral sheet and the 6 palettes, and a keyed act project entry that names its collision bank. Stamps what it froze: the `clips.json` sha, the donor HEADs and the converter blob | **S-M** | About **9.2 MB** of section files for the one act, against OJZ's 4.1 MB (MEASURED). It commits Sonic 2-derived art into aeon for the first time outside a throwaway. **That is an owner call.** |
| A2 | The bake reads the cells from the frozen tree and skips the composition. Everything else stays manifest-derived. Either an `S2CLIP` mode or a sibling shape name | **M** | Same slot, same restore trap, so the canonical shapes stay byte-identical by construction |
| A3 | Refusals: once the stamp exists, a manifest whose rectangles changed is refused, and a plain `S2CLIP=s2_woven` recompose is refused. Aurora's donor page must refuse a paste into a frozen act | **S** | Closes aurora's "edits silently overwritten" blocker (QUOTED aurora survey) |
| A4 | Collision-baseline carve-out for hand-edited cells, and `DONOR_PROVENANCE`-style stamping | **S-M** | |
| A5 | A second real act slot (§2) | **L-XL** | Not recommended for this goal |

### Aurora side (QUOTED, aurora survey at `40ac2af9`, re-shaped by §6)

| Piece | Size |
|---|---|
| Per-cell zone key: tiles and palette from one sidecar | L. The renderer half already exists in `DonorTargetPane` (READ) |
| Collision bank per act | M |
| Chunks record their source tileset (CHUNK-STAMP-ACROSS-ZONES) | M |
| A generated/read-only act flag | S-M |
| Act wiring | S |
| Reading `collision_baseline.json` | S-M |
| A second fixture set | S |
| **Total** | **L to XL** |

### Recommended path

1. **A1, then open the result read-only in aurora** (step 0, below).
2. **A2 plus A3**, so an S2CLIP-style build of the frozen tree is green and a stale manifest
   is refused.
3. **Aurora's keyed act in the level editor:** zone key, bank per act, frozen flag.
4. **A4.**

Aeon total is about **M**. Aurora total is L to XL. Skip A5.

### The first useful step

- Run `promote` once on s2_woven and commit the snapshot plus its stamp.
- Point aurora's **existing** keyed renderer at it read-only. The donor target pane already
  draws `tiles` / `zonekey` / `collattr` / `collattrb` through each zone's tileset and palette.
- The owner then sees the exact cells he would be editing, with no editor-format work in
  aurora yet.
- **INFERRED, not driven:** the pane has been exercised on 1-D, 2-clip acts only. A 5 x 4
  act with shafts and a fill has not been opened in it.

---

## 5. Aurora's question back: where do hand edits live?

The options: **(i)** override files the bake applies over the donor, **(ii)** edit the
donor trees, **(iii)** freeze the act out of re-bake once it is hand-edited.

**Recommendation: (iii), refined.** Freeze the **cells** (tiles, zone key, both collision
planes) into a committed editor act tree. Keep `clips.json` as the authority for everything
that is a per-zone fact and not a cell: palettes, presets, the region plan, BGs and blobs,
crossings, layer lines, the start and music. The stamp (A1) plus the refusals (A3) make the
freeze explicit, so nothing is overwritten silently.

**Reasons:**

- **(ii) is rejected.**
  - The donor trees are gitignored, so edits are unversioned and unreviewable (READ
    `.gitignore:205`).
  - They are regenerated by `tools/s2_zone_convert.py`, so a re-convert erases the edits.
  - They are shared by every clip act that uses the zone: 10 clip acts exist.
  - They are in donor coordinates.
  - Worst: every "equals Sonic 2" check would then compare the edited donor against itself
    and stay green. That is a vacuous gate dressed as a fidelity check.
- **(i) costs the most for a benefit nobody has asked for yet.**
  - It needs an override format and keying that survives a moved rectangle (clip-local, not
    act coordinates).
  - It needs a separate layer for connector and fill cells, and conflict rules when a
    rectangle moves under an override.
  - It cannot add new art without an act-owned tile sheet anyway.
  - Aurora would need diff-on-save semantics.
  - All of that exists to let the owner keep re-placing rectangles *after* touching cells.
- **(iii) is the OJZ model.** One committed editor tree is the source of truth, so aurora
  gains no second editing model ("clean, not bolted-on").
- **(iii) does not close the door on (i).** The frozen tree minus a fresh composition of the
  same manifest *is* the override set. If re-placing after touch-ups is ever wanted, (i) is
  derived from (iii) by a diff tool, not migrated to.
- **Timing.** Placement edits keep going through the donor page (and `clips.json`) until the
  owner is happy with the rectangles. Then freeze once and touch up cells after that.

---

## 6. Can aeon re-express the act as "one tileset / one palette / one bank"?

- **Collision: it already is one bank.** The woven act is a single S2-bank act at 250 of
  255 entries (MEASURED). Aeon can remove the aurora item's guesswork by naming the bank in
  the act's project entry (for example `collisionBank`) in A1. Mapping into S&K's bank is
  impossible: 68 of 151 shapes are unreachable (READ `import_s2_collision.py:13`).
- **Tiles: no flat per-act tileset fits 11 bits.**
  - Deduped pool: **2,877** distinct 8x8 tiles, byte-exact. Deduping modulo H/V flips gives
    the same **2,877**, so the pool is already flip-canonical. The bake's own count is
    **2,894** (zone, tile) pairs, because it keys by zone and counts the blank slot, in
    **49** pages. The 11-bit field holds **2,048** (READ `ojz_strip_gen.py:269`; aurora
    `src/core/model/s4-types.ts:51`). All MEASURED.
  - So a flat act tileset would need a 12-bit index in both the engine-side editor word and
    aurora.
- **Tile-map form the editor format should carry: the per-cell zone key**
  (`section_N.zonekey.bin` plus `tilesets[]`).
  - Each zone sheet is at most **914** tiles (MEASURED), so the 11-bit index stays valid
    per sheet.
  - Aeon's generator already bakes this form.
  - Aurora's target pane already renders it.
  - The same key selects the palette, which is why the tile L and the palette M collapse
    into one mechanism.
- **Why not section-local maps?** They are the ROM form: worst **801** of 2,047 entries,
  sum 6,104 across 20 sections (MEASURED). As an *editor* form they make one painted tile
  change a section's map, and they make cross-section copy and paste a remap. They also
  exist only after placement, so every save would need a bake to be valid. Keep them a
  build product.
- **Palette: cannot be one.** The six zones' palettes hold **119** distinct opaque colours
  (HPZ 38, CPZ 29, EHZ 36, MTZ 37, OOZ 40, WFZ 37), and lines 1 to 3 hold 45 (MEASURED).
  The engine already swaps palette per region. The editor needs the zone key to pick the
  cell's palette, and nothing more.
- **Other layouts that were measured:**
  - A section can hold up to **4 zones** (sections 6 and 12), so a per-section key cannot
    replace a per-cell key (MEASURED, `clipact.json` `sections[].zone_keys`).
  - **13** of the 20 sections carry more than one sheet key (neutral connector sheet included); the other 7 carry one (MEASURED, same field).

---

## 7. Commands (what the MEASURED rows came from)

```
# The composer only, into scratch. The repo tree is untouched: no clip_rom_bake, no generated
# tree written. Donor root = the main checkout's gitignored trees.
python3 -c "import sys; sys.path.insert(0,'tools'); import clip_act_bake as b; \
  b.bake('games/sonic4/data/clips/s2_woven/clips.json', out_dir=SCRATCH, \
  donor_root='/home/volence/sonic_hacks/aeon/games/sonic4/data/donors')"
#  -> collision 250 of 255 (bank base_s2); N1 = N2 = worst 12 of 12, 0 over; 20 sections
# clipact.json: pool.tiles 2894, pool.pages 49; zone_table tiles WFZ 889, EHZ 914, MTZ 792,
#   CPZ 867, HPZ 725, OOZ 681, neutral 37; sections[].local_map_entries max 801, sum 6104
# pool.bin (3136 slots, page-padded): 2877 distinct exact, 2877 distinct modulo H/V flip
# du -cb of section_*.{tiles,zonekey,collattr,collattrb}.bin: 9,175,040 B
#   (OJZ editor section_*: 4,132,227 B)
# donor palette.bin x6: opaque distinct per zone 38/29/36/37/40/37, union 119
```

Numbers that moved since the woven report (v2.1): collision was 245 there and is **250**
now; the pool was 2,659 tiles / 45 pages there and is **2,894 / 49** now; the worst local
map was 773 there and is **801** now. These are later connector and fill changes on master.
The report's numbers were right when it was written. This note quotes today's.
