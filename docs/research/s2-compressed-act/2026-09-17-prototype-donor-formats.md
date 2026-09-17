# The Simon Wai prototype donor — what its formats actually are

**Date:** 2026-09-17 · **Branch:** `parcel/s2-donor-loader` (worktree `aeon-wt-s2donor`)
**Parcel:** S2-COMPRESSED-ACT staged plan row 1 (`../2026-09-17-s2-compressed-act-design.md` §10),
widened by the owner's answer to the Hidden Palace card.
**Donor:** `/home/volence/sonic_hacks/s2-simonwai-disasm`, read-only,
`https://github.com/Totally-Not-Filter/s2-8XX-disasm` at `0113ca4775115689edc87d4115ed9cb51f220e02`.

This is the note the design doc's §6 asked for and could not write, because at the time the
prototype was not on disk. **Everything below was re-derived from the prototype's own
`main.asm` and `constants.asm`, or measured off the files.** Where the design guessed, the
guess is quoted and marked right or wrong.

Nothing here was run in an emulator. Every figure is donor data pushed through aeon's
build-time functions.

---

## 1. Summary for someone who just wants the answer

Hidden Palace Zone is **real, complete, and loadable**. It has a layout, 16x16 and 128x128
mappings, tile art, both collision indices and a palette, all present, all decodable, and it
goes through aeon's page pipeline today:

```
HPZ  box 16384x2048 px (placeholder)   painted 9216x2048 px   4.5 sections
     700 blocks · 256 chunks · 725 art tiles · 561 canonical tiles · 9 pages
     collision: 152 attr-set entries whole, 87 for one section, 111 for two
     foreground palette: 97.0% CRAM line 2, 3.0% line 3
```

That last line is the happy surprise. **Hidden Palace is the most aeon-shaped foreground of
the six zones the owner named** — aeon's own foreground is entirely on line 2, Emerald Hill is
95% line 2, and Hidden Palace is 97%. Chemical Plant (90% line 3), Metropolis (98% line 3) and
Wing Fortress (83% line 3) are the ones that disagree.

The prototype's formats differ from the final game's in five places, and the one that matters
most is that **its level art is Nemesis, not Kosinski** — there is no `art/kosinski/` directory
in that tree at all.

---

## 2. Format by format: prototype vs final game

| Thing | Final game (`s2disasm`) | Prototype (`s2-simonwai-disasm`) | Same? |
|---|---|---|---|
| Level layout | `level/layout/<Z>_<act>.kos`, Kosinski, decodes to exactly $1000 B: 32 rows of 128, even rows FG and odd rows BG | `level/layout/<Z>_<act>.bin`, **uncompressed**, 2050 B: a two-byte (width-1, height-1) header then width*height chunk ids. FG and BG are **separate files** (`GHZ_1.bin` / `GHZ_BG.bin`) | **NO** |
| Layout row width | always 128 | `Interleave_Level_Layout` (main.asm:7930) **TILES** each row `$80 div width` times across the 128-byte RAM row. Every foreground layout happens to be 128x16 so the tiling is one copy; the background layouts are 4, 6 and 8 wide and genuinely repeat | **NO** |
| 16x16 blocks | `mappings/16x16/<SET>.kos`, Kosinski | `mappings/16x16/<SET>.bin`, **uncompressed**; main.asm:7816 copies it word for word into Block_Table | **NO** (content identical in shape: 4 words per block) |
| 128x128 chunks | `mappings/128x128/<SET>.kos`, Kosinski, 64 words per chunk | same, and `GHZ and HTZ.kos` is a shared set the way `EHZ_HTZ.kos` is | **YES** |
| Tile art | `art/kosinski/<SET>.kos`, Kosinski | `art/nemesis/<SET> primary.nem`, **Nemesis** | **NO** |
| Art VRAM base | tile 0 | tile 0 (`Hidden_Palace_Sprites_1` loads `ArtNem_HPZ` to `$0000`) | **YES** |
| Supplementary art | HTZ and WFZ overlay a second blob at a tile offset named by a constant in `s2.constants.asm` | HTZ overlays `HTZ secondary.nem` at the VRAM address its PLC list names (`$3F80` = tile 508). Same mechanism, different place to read the offset from | mechanism YES |
| HTZ block patch | `Block_Table+$980` from `BM16_HTZ` | identical spelling, identical offset | **YES** |
| Collision index | `collision/<SET> primary/secondary 16x16 collision index.kos`, Kosinski, 768 B | `collision/<SET> primary/secondary 16x16 collision index.bin`, **uncompressed**, 768 B. (It is expanded byte→word into a $600-byte RAM buffer at load time, main.asm:4174 — a RAM detail with no bearing on the file) | **NO** (file), YES (content) |
| Collision shape bank | `Collision array - Vertical.bin` / `- Horizontal.bin`, 4096 B each | `Collision array 1.bin` / `Collision array 2.bin`, 4096 B each. **MEASURED: 1 is byte-identical to Vertical, 2 to Horizontal** | **YES** (content) |
| Collision angles | `Curve and resistance mapping.bin`, 256 B | `Curve and resistance mappings.bin` (plural), 256 B, **byte-identical** | **YES** (content) |
| Chunk-entry word | bits 9:0 block id, 10 X-flip, 11 Y-flip, 13:12 path-A solidity, 15:14 path-B | identical — `andi.w #$3FF` (main.asm:7304), `btst #3`/`btst #2` on the high byte (:7534), and `constants.asm:70-71` spells the solidity bits out: top bit is "either $C or $E", lrb "either $D or $F" | **YES** |
| `LevelSize` | `zoneTableEntry.w xstart, xend, ystart, yend`, per zone AND act | 4 longs per zone, two per act, each long packing (min, max) as two words. Unpacks to the same four numbers (main.asm:4897-4906 reads it) | **NO** (shape), YES (meaning) |
| Palette | `art/palettes/<Z>.bin`, 96 B | `palettes/<Z>.bin`, 96 B | **YES** |

**The single most important line in that table is the collision one.** The two games share one
collision-shape vocabulary, byte for byte. A prototype zone's geometry therefore needs no
second shape bank, and staged-plan parcel 4 (the S2 base-bank import) covers both donors at
once instead of twice. `tools/test_s2_donor.py::test_the_two_donors_share_one_collision_shape_vocabulary`
is what stops that from quietly ceasing to be true.

### Nemesis

Aeon had no Nemesis decoder — the engine deliberately dropped Enigma/Nemesis/Kosinski/UFTC —
so `s2_donor.nem_decompress()` is new, and it is build-time only. The header word is bit 15 =
XOR/delta mode and bits 14:0 = a **TILE** count (the output is `tiles * 32` bytes, not
`rows * 4`; reading it as rows is an eight-fold undercount and was the first thing I got wrong).

It is verified against **clownnemesis v1.1.1** (`sonic_hack/tools/nemdec -d`), a third-party
decompressor, over **all 283 `.nem` files in the two donors** — 79 in the prototype, 204 in
`s2disasm` — byte for byte, **0 mismatches**. It is also verified with no external tool at all
against the one uncompressed twin `s2disasm` itself commits: `art/nemesis/Signpost.nem`
decodes to exactly `art/uncompressed/Signpost.bin`, 2,496 bytes.

---

## 3. The prototype's zones, measured

`python3 docs/research/s2-compressed-act/s2_clip_budget.py zones --donor s2-simonwai-disasm`

| Zone | Camera box (px) | Painted extent (px) | Sections | Source tiles | Canonical tiles | Pages | Collision (whole zone) |
|---|---|---|---|---|---|---|---|
| GHZ | 10976 x 1024 | 10976 x 1016 | 6 | 636 | 480 | 8 | 105 |
| WZ | 16384 x 2048 * | 2176 x 1920 | 8 | 788 | 788 | 13 | 66 |
| MTZ | 16384 x 2048 * | 8576 x 2048 | 8 | 422 | 422 | 7 | 65 |
| HTZ | 10560 x 2048 | 10560 x 2048 | 6 | 604 | 423 | 7 | 125 |
| **HPZ** | **16384 x 2048 \*** | **9216 x 2048** | **8** | **561** | **561** | **9** | **152** |
| OOZ | 12480 x 1888 | 12480 x 1840 | 7 | 485 | 485 | 8 | 55 |
| DHZ | 9408 x 1088 | 9408 x 1088 | 5 | 604 | 481 | 8 | 79 |
| CNZ | 16384 x 2048 * | 16384 x 2048 | 8 | 728 | 540 | 9 | 116 |
| CPZ | 10432 x 2048 | 10432 x 2048 | 6 | 622 | 622 | 10 | 160 |
| NGHZ | 10752 x 640 | 10752 x 640 | 6 | 600 | 600 | 10 | 141 |

`*` = the `LevelSize` row is the `$3FFF` placeholder, exactly as Wing Fortress's is in the
final game. **A clip of any starred zone must be taken from the painted bounding box, not the
camera box.** The loader records this in `Zone.box["camera_box_is_placeholder"]` and
deliberately does NOT trim, because trimming would move every figure measured off that box.

Five zones exist in both trees under the same name (CNZ, CPZ, HTZ, MTZ, OOZ) with different
data, which is why the loader has no default donor and no bare-name spelling for the
prototype.

---

## 4. The act the owner actually asked for, budgeted for the first time

The design's six-zone figures used Hill Top as a stand-in for Hidden Palace and said so at each
one. Here are the real six — Emerald Hill, Chemical Plant, Hidden Palace, Wing Fortress, Oil
Ocean, Metropolis — two sections each, through aeon's real Pass 4 placement:

```bash
python3 docs/research/s2-compressed-act/s2_clip_budget.py place \
    EHZ:1,0,2,1 CPZ:1,0,2,1 's2-simonwai-disasm@HPZ:0,0,2,1' \
    WFZ:2,0,2,1 OOZ:2,0,2,1 MTZ:1,0,2,1 --rowlen 12
```

| | Stand-in (HTZ for HPZ) | **Real six (HPZ from the prototype)** |
|---|---|---|
| Sections | 12 of 48 | 12 of 48 |
| Pool tiles | 2,965 | **2,959** |
| Pages | 50 | **50** |
| Worst camera window | 12 of 12 frames, 0 of 322,391 over | **12 of 12 frames, 0 of 322,391 over** |
| Collision, 2 sections each | 278 of 255 (over by 23) | **353 of 255 (over by 98)** |
| Collision, 1 section each | 131 of 255 (fits) | **199 of 255 (fits)** |

**The art budget is unchanged and still passes at exactly the limit.** The collision budget is
substantially worse: Hidden Palace is collision-rich (152 entries whole, against Hill Top's
125), so the real act overruns the 255-entry cap by 98 instead of 23 at two sections a clip,
and the one-section act that used to sit at 131 now sits at 199. The design's §9.3 owner card
on the collision cap is therefore **more** urgent, not less: at one section per clip there are
56 entries of headroom left for six zones, and nothing else in the act has been added yet.

A spec may now carry a `<donor>@` prefix, because the showcase act is five final-game zones
plus one prototype zone and no per-invocation donor flag can express that.

---

## 5. What a later parcel must NOT assume

1. **Do not assume `<zone>_BG.bin`.** The prototype's background layouts are per zone AND act
   and named by `Off_Level`'s table, not by a rule: `GHZ_BG.bin` serves both acts, but
   `HTZ_1_BG.bin` and `HTZ_2_BG.bin` are separate, and `CNZ_2_BG.bin` is 8 bytes where
   `CNZ_1_BG.bin` is 2048. `s2_donor.load_bg_grid()` is final-donor only and refuses by name.
2. **Do not assume a layout row is 128 wide.** It is for every foreground layout and for none
   of the small backgrounds. The expansion tiles; it does not pad.
3. **Do not assume the prototype needs its own collision base bank.** It does not — the banks
   are byte-identical. But do not assume the reverse either without re-running the test that
   says so.
4. **Do not clip a placeholder-box zone from its camera box.** WZ, MTZ, CNZ and HPZ in the
   prototype, WFZ in the final game.
5. **Do not read `$?` from `s2_clip_budget.py`.** `mode_collision` and `mode_place` compute a
   verdict and return 0/1 and `main()` has always discarded it, so both exit 0 whether they fit
   or refuse. Booked below rather than fixed inside a refactor whose whole check is that
   nothing moved.
6. **Two of the design's own side findings are still unverified**, and parcel 4 owns them: the
   "75 of 151 S2 shapes unreachable from the S&K bank" figure and the "211 of 256 rotated
   shapes disagree by sign" figure came from a separate, uncommitted measurement. Neither is
   reproducible from anything in the repo today.

---

## 6. Correction to a published figure — the collision counts moved by two

`s2_clip_budget.py collision` was handing `collision_pipeline.bake_cell` the **rotated**
array (`Collision array - Horizontal.bin`) as its per-column **height** profiles. The shipping
bake reads the other one: `collision_pipeline.load_donor_collision` takes sonic_hack's
`Collision array 1.bin`, which (measured, §2) is the Vertical array. So the design's §3.5
counts were interned off width profiles read as heights.

`--profiles` now defaults to `vertical`. The published figures and the corrected ones:

| Set | Published (`--profiles horizontal`) | Corrected (default) |
|---|---|---|
| EHZ CPZ OOZ MTZ WFZ, whole | 301, over by 46 | **299, over by 44** |
| the six, 1 section each | 131, FITS | **130, FITS** |
| the six, 2 sections each | 278, over by 23 | **276, over by 21** |

**No conclusion in §3.5 moves.** `--profiles horizontal` reproduces the published numbers
exactly, and that is how the loader promotion was proven faithful.

---

## 7. How the promotion was proven byte for byte

The design's falsifiable check for row 1 is: *"The new module reproduces, byte for byte, the
zone word grids the measurement tool produces for all 9 zones."*

Method: `git archive d234c084 | tar -x` into a scratch directory, so the PRE-promotion loader
ran from a pristine export of the commit this branch started at and could not see any new code.
Both loaders were then asked for all nine zones and the SHA-256 of `words.astype(">u2")
.tobytes()` and of the art blob were compared.

**Result: 9 of 9 identical, both the word grid and the art blob.** The `box` dictionary gained
exactly two additive keys (`donor` on every zone, `camera_box_is_placeholder` on WFZ) and no
existing key changed value. The nine hashes are frozen in
`tools/test_s2_donor.py::FINAL_GOLDEN`.

For the prototype there is no prior loader to compare against — nothing in this repo had ever
read that tree. The equivalent check is an **independent re-derivation**: each of the ten
prototype art blobs was recomposed from the same `art_sources()` list using clownnemesis
instead of `nem_decompress`, and all ten agreed. That is a real check rather than a
self-consistency tautology because the decompressor on the other side is somebody else's C.

Two further byte-level controls came free:

* `python3 tools/megaact_window_pageset.py control` still reproduces the committed OJZ bake:
  589,824 cells compared, **0 differing**, pool 612 tiles, 10 pages, same pinned set.
* `tools/test_gen_region_bg_showcase.py::test_committed_showcase_outputs_match_the_generator`
  passes, so the committed showcase blobs still regenerate byte-identically after that
  generator was rewired onto `s2_donor`.

And the §13 re-run: with `--profiles horizontal`, the entire section-13 command set produces
output identical to the pre-promotion tree apart from two elapsed-time readings and the run's
own timestamp. `zones`, `clipsweep`, both `place` runs (including the 870,231- and
322,391-window sweeps and their 12-of-12 worst windows), the whole `window` sweep, all three
`collision` counts, `collsweep` and `pallines` are unchanged.

---

*Wall clock: 2026-09-17, dev box up 1 day 19 h, load average 1.9-3.1 across the runs. No
emulator was used. `tools/landing_build.sh` exit 0, `finished=0`, three shapes built — this
parcel changes no `.emp` and no ROM byte, and the build was run to clear the unbuilt-tree
failures in `test_extern_guard_reachability`, not because anything here reaches the ROM.*
