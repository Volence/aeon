# The whole-zone converter — one Sonic 2 zone becomes an aeon editor tree

**Date:** 2026-09-17 · **Branch:** `parcel/s2-zone-converter` (worktree `aeon-wt-s2conv2`)
**Parcel:** S2-COMPRESSED-ACT staged plan row 2 (`../2026-09-17-s2-compressed-act-design.md` §10).
**Base:** `757c0c58` (master at parcel 1's landing).
**Donors:** `/home/volence/sonic_hacks/s2disasm` and `/home/volence/sonic_hacks/s2-simonwai-disasm`,
both read-only. No git was run in either.

Nothing here was run in an emulator, and no `.emp` and no ROM byte changed.

---

## 1. Summary for someone who just wants the answer

`tools/s2_zone_convert.py` turns one Sonic 2 zone — from either donor — into a directory
`ojz_strip_gen` can already read. All nineteen zone/donor pairs convert, and the conversion is
lossless:

```
19 zone/donor pairs · 1.3 s wall clock · 17 MB
6,317,248 cells round-tripped · 0 differing
0 nonzero pad cells · 0 tile indices past any tileset
validate_editor_inputs accepted all 19 trees
```

```
games/sonic4/data/donors/<donor>/<ZONE>/
    tileset.bin            the decompressed level art, 32 B/tile, tile 0 at offset 0
    palette.bin            the donor's 96-byte zone palette, verbatim (CRAM lines 1-3)
    section_<N>.tiles.bin  256x256 big-endian VDP nametable words, N = sy*grid_w + sx
    zone.json              grid, extents, painted bbox, provenance, per-section counts
```

Art and layout only. Collision, objects, regions, background and the clip manifest are rows
3, 4 and 5.

---

## 2. The design doc's §8 file set was wrong about aeon's own act tree

The design proposed a donor tree "mirroring `games/<game>/data/editor/<zone>/<act>/`". It does
not mirror it, and the difference matters to whoever wires a converted tree into a project.
Transcribed from `games/sonic4/data/editor/ojz/act1` and `project.json`:

| Design §8 said | The tree actually holds |
|---|---|
| `tileset.bin` in the act directory | **There is no tileset in an act directory.** `project.json`'s `zones[].tileset` names the blob, and today it is `games/sonic4/data/editor/ojz_tiles.bin` — outside the act dir |
| `palette.bin` in the act directory | True, but because `zones[].palette` names it, not by convention |
| (not mentioned) | A real act dir also carries `regions.json`, `section_N.meta.json`, `.objects.json`, `.rings.json` and a vestigial `.coll.bin` |
| `zone.json` carries attr-set cost per section | Not computable before row 4 rules on the S2 shape bank. Parcel 2's `zone.json` carries the art-side counts instead |

`tileset.bin` is therefore a name **this converter chooses** so a donor tree is self-contained.
A project that wants to open one points `zones[].tileset` at it.

The good news is the one the design cared about:
`ojz_strip_gen.validate_editor_inputs(data_path, tileset_path, num_sections)` takes all three
paths explicitly, so a converted tree validates without touching `project.json` and without any
risk to the committed OJZ act. The design doc has been patched in place at §8, §5.3 and §10.

---

## 3. The three rules this parcel had to decide

### 3.1 Section alignment: PAD, never crop, never refuse

The converted grid is anchored at **donor world tile (0, 0)** and covers
`ceil(crop_x1 / 256) x ceil(crop_y1 / 256)` sections. Everything inside the grid and outside the
camera-box crop is a zero word.

*Why pad rather than crop or refuse.* Measured over both donors: **not one of the nineteen
zone/donor pairs has a camera-box crop that is a whole number of 256-tile sections on its long
axis.** A refusing converter would convert nothing. A cropping one would silently drop
camera-reachable cells, which is the class of defect this whole pipeline is built to prevent.

*Why anchor at world (0, 0) rather than at the crop origin.* Four zones have a `LevelSize`
ystart above zero — ARZ y0=64, MCZ and DHZ y0=120, NGHZ y0=64 (tiles). Anchoring at world zero
costs them nothing, because every zone's crop ends at or before tile row 256 and the grid is one
section tall either way. What it buys is that **a donor pixel and a converted-tree pixel are the
same number**: row 3's `clips.json` names `src_rect` in donor coordinates, and an origin shift
here would put a silent constant offset under every clip in the showcase act.

*Placeholder-box zones are NOT trimmed here.* WFZ (final) and CNZ/HPZ/MTZ/WZ (prototype) have
the `$3FFF` camera-box placeholder, and the prototype-formats report's rule is that a CLIP of
one must come from the painted bbox. That is a rule about clipping, which is row 3's job. This
converter materialises the whole camera box (8 sections for those zones, mostly blank) because
that is the lossless choice, and writes `painted_bbox_tiles` into `zone.json` so row 3 can obey
the rule.

### 3.2 Palette: copy verbatim, and DERIVE the CRAM line from each donor

Both donors' 96-byte zone palettes load to **CRAM lines 1, 2 and 3** — exactly the three lines
aeon writes (line 0 is the character's; `engine/effects/palette.emp`). That is not assumed. It
is read out of each donor's own palette-pointer table, which the two games spell differently:

* **Final game:** `PalPtr_EHZ: palptr Pal_EHZ, 1`, and the macro is
  `dc.w (Normal_palette+lineno*palette_line_size)&$FFFF` / `dc.w bytesToLcnt(ptr_End-ptr)` —
  so the macro's second argument IS the CRAM line and the payload is the file's own length.
* **Prototype:** the table is open-coded, `dc.l Pal_HPZ` / `dc.w $FB20,$17` — a RAM destination
  and a `dbf` count of longs minus one. `Normal_palette` is a `ds.b` inside a struct in
  `constants.asm` and is not resolvable from a regex, so the line is derived **from the table
  itself**: the one entry with a four-line (128-byte) payload can only be a whole-CRAM load, so
  its destination pins line 0, and every other entry's line is the offset from it. A second
  four-line entry, or one at a different destination, breaks the derivation loudly instead of
  shifting every zone's palette by a line.

All nineteen pairs derive to `(line 1, 96 bytes)`. A zone that derived to anything else is
refused by name — a palette on the wrong three lines is a ruling, not a copy.

### 3.3 CRAM line 0 cells: convert faithfully, count, surface — never remap

Some zones paint cells on palette line 0, which aeon never writes, so they would render in the
character's colours. Exact counts, over painted (non-blank) cells:

| Zone | Donor | Line-0 painted cells | of painted | % |
|---|---|---:|---:|---:|
| CPZ | s2disasm | **698** | 112,906 | 0.62% |
| CPZ | s2-simonwai-disasm | **680** | 112,136 | 0.61% |
| WFZ | s2disasm | **104** | 101,812 | 0.10% |
| every other zone of both donors | | **0** | | 0.00% |

This independently reproduces the design's §5.3 figures (CPZ 0.6%, WFZ 0.1%) and makes them
exact. **The whole defect in the owner's six-zone act is 802 cells.**

The converter does not rewrite them. Three reasons, in order of how much they bind:

1. It would break this parcel's own identity bar. The round trip would no longer be identity,
   and there would be nothing left proving the conversion is lossless.
2. Rewriting a nametable word's palette bits is exactly what `tools/verify_level_bin.py`'s
   bake-fidelity lane asserts the bake never does — the same reason §9.1(b)'s recolour option
   was priced as expensive.
3. It is not this parcel's decision. §9.1 prices three whole-act answers to the palette problem
   and the owner ruled only on corridors. A quiet remap here would close options he has not been
   asked about.

So it counts them per zone and per section into `zone.json` and prints a warning. **The
decision stays open, and it is now a small one:** 802 cells to repaint by hand, hide behind
geometry, or accept.

---

## 4. Every zone, measured

`python3 tools/s2_zone_convert.py convert --all-zones --out <dir>`

| Donor | Zone | Sections | Crop (tiles) | Tileset tiles | Painted cells | Cells round-tripped | Differing | Line-0 |
|---|---|---:|---|---:|---:|---:|---:|---:|
| s2disasm | ARZ | 6x1 | 1344 x 156 @ y64 | 1013 | 110,208 | 209,664 | 0 | 0 |
| s2disasm | CNZ | 6x1 | 1308 x 256 | 816 | 259,887 | 334,848 | 0 | 0 |
| s2disasm | CPZ | 6x1 | 1304 x 256 | 867 | 112,906 | 333,824 | 0 | **698** |
| s2disasm | EHZ | 6x1 | 1372 x 128 | 914 | 119,231 | 175,616 | 0 | 0 |
| s2disasm | HTZ | 6x1 | 1320 x 256 | 914 | 247,224 | 337,920 | 0 | 0 |
| s2disasm | MCZ | 5x1 | 1176 x 136 @ y120 | 936 | 125,560 | 159,936 | 0 | 0 |
| s2disasm | MTZ | 5x1 | 1144 x 256 | 792 | 203,818 | 292,864 | 0 | 0 |
| s2disasm | OOZ | 7x1 | 1560 x 236 | 681 | 94,047 | 368,160 | 0 | 0 |
| s2disasm | WFZ * | 8x1 | 2048 x 256 | 889 | 101,812 | 524,288 | 0 | **104** |
| s2-simonwai-disasm | CNZ * | 8x1 | 2048 x 256 | 850 | 312,408 | 524,288 | 0 | 0 |
| s2-simonwai-disasm | CPZ | 6x1 | 1304 x 256 | 858 | 112,136 | 333,824 | 0 | **680** |
| s2-simonwai-disasm | DHZ | 5x1 | 1176 x 136 @ y120 | 936 | 125,465 | 159,936 | 0 | 0 |
| s2-simonwai-disasm | GHZ | 6x1 | 1372 x 128 | 912 | 119,045 | 175,616 | 0 | 0 |
| s2-simonwai-disasm | **HPZ** * | 8x1 | 2048 x 256 | 725 | 166,680 | 524,288 | 0 | 0 |
| s2-simonwai-disasm | HTZ | 6x1 | 1320 x 256 | 912 | 247,814 | 337,920 | 0 | 0 |
| s2-simonwai-disasm | MTZ * | 8x1 | 2048 x 256 | 783 | 161,375 | 524,288 | 0 | 0 |
| s2-simonwai-disasm | NGHZ | 6x1 | 1344 x 80 @ y64 | 1002 | 58,085 | 107,520 | 0 | 0 |
| s2-simonwai-disasm | OOZ | 7x1 | 1560 x 236 | 693 | 82,060 | 368,160 | 0 | 0 |
| s2-simonwai-disasm | WZ * | 8x1 | 2048 x 256 | 798 | 49,947 | 524,288 | 0 | 0 |
| | **total** | **123** | | | **2,809,708** | **6,317,248** | **0** | **1,482** |

`*` = `LevelSize` xend is the `$3FFF` placeholder, so the grid is the full camera box and most of
it is blank. `@ yN` = the camera box starts at tile row N; those rows are written as pad.

---

## 5. How the round trip avoids being a tautology

A round trip is the easiest check in the world to write vacuously — compare an array to itself
and report zero differing. Two things stop that here.

**The reference side is a second implementation.** `s2_donor.load_zone` builds its word grid
through `ojz_strip_gen.chunk_get_tile_word`, and that grid is what the writer wrote. So the
verifier does not call it. `s2_zone_convert.expand_chunk_words` re-derives the same words
straight from the two file formats — chunk entry bits 9:0 block id, 10 X-flip, 11 Y-flip; block
= four nametable words top-left/top-right/bottom-left/bottom-right; a chunk-level flip both
swaps the sub-tile within the block and toggles that tile word's own H/V bit; an out-of-range
block id resolves to word 0, not to a wrapped index.

Those three branches are all exercised by real data rather than merely present. Measured over
the 16,384 chunk entries of each zone's chunk table: every zone of both donors carries X-flipped
and Y-flipped entries (EHZ 2842/363, HPZ 1778/584, CNZ-proto 2182/2500), and fourteen of the
nineteen carry out-of-range block ids (WZ 1356, CNZ-proto 792, OOZ 763).

**And the branches are mutation-proven load-bearing.**
`test_the_reference_expander_is_load_bearing` breaks one branch of the reference at a time,
against bytes already fixed on disk, and requires the round trip to go red. If it stayed green,
the two sides would not be independent and "0 cells differing" would prove nothing.

**The pad is verified, not asserted.** Rule 1 says everything outside the crop rectangle is
zero. `verify_tree` counts it. That is what makes "padded, never cropped" a measurement rather
than a statement of intent: nothing was dropped, because everything outside the identity
rectangle is provably blank.

---

## 6. The gate's own fixture was vacuous once, and that is worth recording

The red-first proof found a defect in the gate before it found anything in the converter.

Mutation M2, applied on disk: change the writer from "anchor the section grid at donor world
tile (0, 0)" to "anchor it at the crop origin" — the alternative rule 3.1 rejects. **All fifteen
rows stayed green.** The fixture was EHZ and HPZ, and both crop from tile row 0
(`crop_tiles` `[0, 1372, 0, 128]` and `[0, 2048, 0, 256]`), so for them the two rules are the
same arithmetic and the mutation is a no-op.

A green mutation is a defect in the gate, not a pass for the code. ARZ joined `CASES` — its
camera box starts at tile row 64 — and `test_the_grid_is_anchored_at_donor_world_zero` now
asserts the rule directly. Re-run with mutation M2b (a well-formed crop-origin-anchored tree
rather than the shape error M2's one-line form produced): **2 failed, 16 passed**, and the two
failures are exactly the ARZ round trip and the anchoring row, with EHZ and HPZ still green —
the correct discrimination. Restored from the committed baseline `d3848ceb`: 18 passed.

The other mutation, M1 (the writer drops the priority bit): **2 failed, 13 passed**, with the
HPZ round trip reporting 160,521 of 524,288 cells differing.

---

## 7. What row 3 inherits

- **`zone.json` is the interface.** It carries `grid` (w/h/sections and the flat row-major index
  rule), `extent` (camera box, `camera_box_is_placeholder`, `crop_tiles`, `painted_bbox_tiles`,
  the pad rule), `tileset` (bytes, tiles, per-source paths and offsets, SHA-256), `palette`
  (CRAM lines, SHA-256, source path) and per-section counts including `distinct_tiles`. A clip
  manifest needs none of it re-measured.
- **Donor and tree coordinates are the same number.** `src_rect` in donor pixels indexes the
  converted tree directly. That is rule 3.1 and it is asserted by a test, not a convention.
- **Tile indices are NOT remapped.** A converted word's 11-bit index means the same tile in
  `tileset.bin` it meant in the donor, so the per-cell tileset key row 3 owes
  `fg_page_order.place_pool` is just `(donor, zone)` per clip, with no index translation.
- **A clip of a placeholder-box zone must come from `painted_bbox_tiles`,** not from the grid
  extent. Parcel 1's rule, unchanged; parcel 2 records the bbox and deliberately does not apply
  it.
- **The converted trees are gitignored** (`games/sonic4/data/donors/`) — derived, regenerable in
  1.3 s, read by nothing in the build. **That flips at row 6.** The moment a clip out of one of
  these trees reaches a committed byte, the tracked-bytes argument that keeps
  `games/sonic4/data/generated/` in git applies word for word here, or the ROM will be built
  from bytes nobody can reproduce. The `.gitignore` comment says so at the line.
- **`donor_provenance` still records both S2 donors with `contributes_to_rebake=false`, and that
  is still correct** — nothing this parcel produces reaches a committed byte. Row 6 is what
  flips it.
- **No background.** `load_bg_grid` is final-donor only and refuses the prototype by name; the
  `Off_Level` registry parcel 1 described is still unwritten and still has no consumer.

---

## 8. Evidence

- **Pre-build tool lane**, `python3 -m pytest tools -m "not needs_build" -q`, `__pycache__`
  cleared first: **4 failed, 2924 passed, 2 skipped, 28 deselected, 55 errors, 143 subtests
  passed in 62.74 s**.
- **The failures are pre-existing and were established as such by a control, not assumed.** The
  same worktree with this parcel's two files moved aside and `.gitignore` reverted to `757c0c58`:
  **4 failed, 2906 passed, 2 skipped, 28 deselected, 55 errors in 60.63 s** — and the 59
  FAILED/ERROR node ids are an **identical set**. The delta is exactly +18 passed, this parcel's
  18 new rows. The family is `test_artifact_provenance.py` (17), `test_provenance_consumers.py`
  (34), `test_extern_guard_reachability.py` (5), `test_bg_emit.py` (1) and
  `test_needs_build_lane.py` (1): the artifact-freshness family that fails on a tree with no
  freshly built ROM, which is why parcel 1's evidence line reports no failures — it ran
  `tools/landing_build.sh` first.
  (A `git archive 757c0c58` export at `/tmp` was tried as the control FIRST and rejected: it
  reports 42 failed, because an export carries no gitignored working-tree state and is a
  different environment, not a different commit.)
- **`tools/test_s2_zone_convert.py`**: 18 rows, all green, red-proven by three on-disk mutations
  (M1 priority bit, M2/M2b anchoring) each restored from a committed baseline.
- **No emulator.** No `.emp` touched, no ROM byte changed, the committed
  `games/sonic4/data/editor/ojz/act1` tree untouched (`git status` clean at every commit).

*Wall clock: 2026-09-17, dev box up 1 day 19 h, load average 1.2-2.9 across the runs.*
