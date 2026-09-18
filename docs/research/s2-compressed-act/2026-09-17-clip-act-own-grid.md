# A clip act declares its own grid — and the act holds five of Emerald Hill's 5.36 painted sections

S2-COMPRESSED-ACT parcel 9, 2026-09-17. Branch `parcel/s2-clip-act-extent`, base `8ee74c67`.
Subject: `s4.s2clip.bin`, rebuilt from `S2CLIP=s2_ehz_boot ./build.sh`.

---

## 1. What was asked, and the one thing in the ask that was wrong

The owner flew parcel 8's act to its right-hand edge and said:

> "Oh nice, I see as much as I can now but after our third section it stops because we only
> have 3 horizontally"

Correct. The act was 3 x 3 and the clip painted all of it; there was simply no more act. The
dispatch asked for the whole of Emerald Hill act 1 — **six sections, 12,288 px** — "if the
measurements allow it", and asked for the binding number if they did not.

**They do not, and the number that binds is the donor's own crop against the 2,048 px section
grid.** EHZ's converted tree declares `extent.crop_tiles` ending at tile **1372**, i.e. painted
content stops before x = **10,976 px**, and `clip_manifest` R9 refuses a `src_rect` past the crop.
**10,976 px is 5.36 sections.** Six sections need 12,288 and would leave 1,312 px of the act
unpaintable — the owner's exact complaint, one section further right. So the act is **five
sections, 10,240 px**, and the clip paints all 1,280 of its columns.

### ⚠ THAT IS A TRUNCATION, AND IT IS 736 px OF REAL EMERALD HILL

**Say the two things in one sentence or the second one does not get through:** the act paints
**every column it has**, and it **has fewer columns than the donor has content**. 5 x 2,048 =
10,240; the crop reaches 10,976; **736 px — 92 columns — of painted Emerald Hill is outside the
act and is not in the ROM.**

**It is not padding, and that was measured rather than assumed** (`zone.json` plus the donor's own
`section_5.*.bin`, counted directly). The band is x 10,240..10,975 — local columns 0..91 of
`section_5`, rows 0..127, 92 x 128 = **11,776 cells**:

| x 10,240..10,975 (92 columns, rows 0..127) | content cells | % of band | columns touched |
|---|---|---|---|
| art (`section_5.tiles.bin`), tile index != 0 | **7,745** | 65.8% | **92 of 92** |
| collision plane A (`.collattr.bin`), shape index != 0 | **3,036** | 25.8% | **92 of 92** |
| collision plane B (`.collattrb.bin`), shape index != 0 | **3,036** | 25.8% | **92 of 92** |
| **control** — x 10,976..12,287, past the crop | **0** | 0% | **0** |

So every one of those 92 columns is fully drawn and carries collision, and the zero-padding claim
is true only *past* 10,976, which is exactly where the crop says it starts. **The act holds 5 of
the zone's 5.36 painted sections and loses 736 px at the right.**

#### ⚠ THESE FIGURES SUPERSEDE THE ONES THIS PARCEL'S OWN COMMITS CARRY, AND THE CONCLUSION DOES NOT MOVE

Commit `60af29e8` and the first draft of this file measured the band as **11,776 non-zero art
cells** and **3,304 non-zero collision cells per plane**. Those counted *the cell word is
non-zero*; the question is *does the cell hold content*. They are superseded by the table above,
and a reader who meets the old numbers in the git log should land here.

**Why the old figure could not stand:** 11,776 of 11,776 is exactly 100.0000% — its own
denominator. It is real (the control past the crop returns 0 through the same path, so the counter
does discriminate) but near-vacuous: zone-wide, non-zero words cover 175,276 of 175,616 crop
cells, 99.8%. Row 0 of the band is 92 identical cells of word **0x4000** — tile index 0 with a
palette line, a blank sky cell that is non-zero only because of its attribute bits.

**The right instrument is derived, not chosen.** In a Genesis nametable word bits 0..10 are the
tile index. Counting tile index != 0 over rows 0..127 of all six sections gives **119,231**, which
is exactly `zone.json`'s own `counts/painted_cells` — the converter's definition of painted,
confirmed against an independent pin rather than picked for its answer. §11 gives the command.

**The collision planes had a smaller version of the same defect, and it is decided rather than
suspected.** 3,304 non-zero minus 3,036 with a shape = **268 cells, and all 268 are the single
word `0x0400`**: shape index 0, solidity bits (13:12) clear, X-flip (bit 10) set — the plane word
format `tools/s2_zone_convert.py` documents at its `bit_layout`. An X-flipped empty shape with no
solidity is not collision, so 3,036 is the honest figure.

**THE CONCLUSION DOES NOT MOVE.** Every one of the 92 columns still carries real art AND real
collision under the stricter definition, the control is still 0, and 65.8% in the band sits right
alongside the zone's own 67.9% (119,231 of 175,616) — a discriminating figure where 100.0% was
not. The band is fully drawn Emerald Hill; only the evidence for it got stronger.

**416 px of what is lost is playable level.** Sonic 2's own camera box for EHZ act 1 is
`x max 10656`, which is inside the truncated band: the act stops 416 px before the end of the
level the donor lets a player reach (where the signpost stands), and the remaining 320 px is
drawn scenery past the camera box.

**Why truncating is still the right call here, stated as a decision and not as an absence:** the
alternatives are a six-section act with 1,312 px of unpainted world at its right edge — the defect
being fixed, moved — or a non-section-aligned act extent, which nothing in the engine or the
bakers supports today. The truncation costs content the owner has never seen; the unpainted band
costs him the thing he reported twice.

## 2. The mechanism, and how much of parcel 8's pricing survived

Parcel 8 §7 priced this from reading and flagged itself as an estimate. Scored against what it
took:

| parcel 8 §7 said | verdict |
|---|---|
| `GRID_W`/`GRID_H` are hand-written `const`s in `act_descriptor.emp`, shared with the canonical ROM | **confirmed** |
| the available identity channel is the generated `.emp` the bake already emits | **confirmed** — it is now `games/sonic4/data/generated/ojz/act1/act_grid.emp`, lowered from `project.json` by `tools/act_grid.py emit`, inside the tree the S2CLIP trap restores |
| "that moves canonical bytes unless the generated symbol reproduces the shipped 3 x 3 exactly ... proving it is the parcel, not a footnote" | **confirmed as the right worry, and it was the cheap half.** §3 |
| R21 would be re-aimed rather than relaxed | **confirmed.** §5 |
| — | **MISSED: the grid is not the only thing sized by the grid.** §2.1 |
| — | **MISSED: an act's width is a whole number of SECTIONS and a donor's content is not.** §1 |

### 2.1 What §7 did not price, and it was most of the work

Three tables are sized by the act grid and only one of them is the grid itself.

* **The section table.** `pub data OJZ_Act1_Sections: [Sec; 9]`, nine hand-written `ojz_sec(...)`
  rows with a page of prose each about what that section is for. `Section_GetSecPtrXY` indexes it
  by flat id over `GRID_W x GRID_H`, so a 15-section grid over a 9-row table reads whatever the
  linker put next. It is now **nine hand-written rows ++ a generated remainder**
  (`sec_grid_extra.emp`, EMPTY for the shipped act), and the total is `ensure`d equal to
  `GRID_W * GRID_H`. The nine rows and their prose are untouched.
* **The region table.** Exact coverage is a whole-table `ensure` — the rows' areas must sum to
  `ACT_W * ACT_H`, because a place with no row has no identity. `regions.emp` is lowered from the
  editor by `effects_gen.py`, **which the S2CLIP throwaway does not run**, so a wider clip act
  gets the shipped act's 6,144-wide document over a 10,240-wide act. §4.
* **The per-section artifacts** — strips, local maps, block blobs, block dictionaries, entity
  tables. `ojz_strip_gen` was already fully grid-parametrised; `ojz_block_gen` and
  `ojz_entity_gen` were not, and both read the SHIPPED `project.json` no matter what was being
  baked. §6.

Neither of the last two is visible from the file §7 was reading.

## 3. No canonical byte moved, and here is how that was proved

Two controls, not one.

**The release shape.** `./build.sh` before the change and after it:
`s4.bin` md5 **`ae62156a66c9c3f13e93940e938c340e`**, **821,479 B**, both times — the same md5 the
baseline `tools/landing_build.sh` produced on this worktree at `8ee74c67`. `s4.debug.bin`
848,075 B `b15ef259…` and `demo.debug.bin` 104,707 B `f740c224…` likewise; the final
`landing_build.sh` numbers are in §8.

**The clip shape, which is the stronger one.** With the grid mechanism in and nothing else,
`S2CLIP=s2_ehz_boot ./build.sh` reproduced **parcel 8's own clip ROM byte for byte**:
`c869deafd12a2ad7fab9a59602caa891`, 821,305 B — the md5 printed in parcel 8's report. So the
mechanism moved neither ROM at the shipped grid, and the widening in §1 is the only thing that
moved the clip ROM.

**That control caught a real defect.** The first attempt at §6's redirect pointed
`ojz_entity_gen` at the clip's own staged project. The clip ROM's **size did not change** and its
**md5 did** — and the cause was that every entity table had been emptied (27 lines of OJZ objects
and rings replaced by terminators), because the clip's baked tree carries no objects/rings JSON.
A clip act inherits the shipped act's entities on purpose; ending that silently is not this
parcel's business. A size-only check would have passed it.

## 4. The region document and the act stopped being the same width

Every `6143` in `act_descriptor.emp`, and every `ACT_W - 1` that meant "the right edge of the
authored document", now says `OJZ_AUTHORED_ACT_W - 1` — derived from the generated rows' own
maximum `rg_x1`, not typed. Two `ensure`s pin it: the document may not reach past the act, and it
must end on a section line.

`OJZ_WIDE_FILL_ROWS` is then **one** region covering `[authored width, ACT_W)` over the act's full
height, binding `OJZ_Preset_Plain` — the plainest look three shipped rows already bind, so nothing
new reaches the ROM for it. It is `[]` unless `ACT_W` exceeds the authored width, so **on an act
whose document does tile it, the exact-coverage ensure is still doing its whole job** and this row
emits zero bytes.

Said out loud rather than discovered later: this admits any future act whose grid outgrows its
region document, not only a clip act. The guard is the emptiness condition above.

## 5. R21, re-aimed — what it still catches and what is given up

`check_act_grid_matches_engine` used to read `const GRID_W` out of the hand-written descriptor and
refuse any clip declaring anything else. It could not do otherwise: the grid lived where a
throwaway bake cannot write.

**Now** the bake emits the grid from the manifest and R21 runs immediately after, reading the
value back out of the emitted module.

* **Still caught:** a module that is STALE or was never written — a previous bake's grid left on
  disk, which is the 2026-09-12 F2 staleness one file over, and the failure a bake is likeliest to
  produce by accident. And a descriptor that stopped taking its grid from that module at all:
  `act_grid.descriptor_grid` RAISES on a module that declares no `pub const OJZ_ACT_GRID_W`, so an
  unreadable grid is Unmeasurable, never a pass. That case is now a test row of its own.
* **No longer caught, named rather than implied:** a clip act declaring a grid different from the
  shipped act's. **That refusal WAS the cap this parcel removed**, so it is deliberately given up.
* **Who took over the guarantee it actually claimed** ("a local-map table shorter than the grid the
  engine indexes by flat id"): a comptime `ensure` in the descriptor,
  `OJZ_SEC_ROWS_TOTAL == GRID_W * GRID_H`, which no bake can skip because it is the build; plus
  `verify_level_bin`'s existing local-map arity lane against `act_grid.section_count`. A short
  table now fails the BUILD instead of being refused at the manifest — strictly earlier and
  strictly harder to skip.
* **`section_grid()`'s cross-check looks tautological now and is not.** It compares `project.json`
  (what the bake is about to bake) with `act_grid.emp` (what the engine last compiled). They
  disagree exactly when one was edited without re-emitting, which is the F2 hazard in its new
  location. What genuinely died is "somebody hand-typed a different grid into the descriptor" —
  there is no longer a number there to type.

A stale-literal guard went with it: `ensure(GRID_W * GRID_H == 9, "the [Sec; 9] table must match
grid_w*grid_h")` was in the descriptor, superseded by the derived ensure above. Deleted rather
than left beside it.

## 6. Two generators were reading the wrong project, and one of them still is on purpose

* `ojz_block_gen.generate_all` took its section count from `act_grid.section_count()` — the
  SHIPPED `project.json`. `clip_rom_bake`'s own comment asserted this was safe "by construction
  (this bakes into its slot at its grid, R21)". **Parcel 9 made that sentence false** and it is
  corrected in place rather than deleted. It now takes `project_json=`.
* `ojz_entity_gen` took the grid AND the editor `dataPath` from the same shipped file. It now
  takes `sections=` — **a count override and deliberately not a project redirect**, for the
  measured reason in §3. It refuses a count BELOW the editor's own, because that direction drops
  authored data.

## 7. ★ A SIGIL FINDING, measured with a discriminator

**A `pub const` reached ONLY through a generated module's own `use` does not resolve to an
integer.** sigil hands it back as a link-time LABEL and the consumer refuses the field:

```
[Error] [emit.type] expected an integer for u16, got label,
        in `OJZ_Act1_Sections[9].sec_block_dict_len`
```

The obvious hypothesis — "the value is 0 and 0 is ambiguous" — is **wrong**, and the
discriminator says so: one row taking `OJZ_SEC5_BLOCK_DICT_LEN` (value 0, a name
`act_descriptor.emp` ALSO imports) resolved cleanly, beside a row taking
`OJZ_SEC10_BLOCK_DICT_LEN` (also value 0, imported only by the generated module) that did not.
The distinguishing property is who else imports the name, not what it holds. Same shape as
`docs/EMP_PITFALLS.md` section 2 — a free name resolving against the CONSUMER's scope rather than
the declaring module's.

So `sec_grid_extra.emp` writes the dictionary length as a **literal** and imports nothing for it.
It cannot drift from `sec_block_dicts.emp`: both files are written from one `dict_lens` list in
one call of one function. **The label-typed fields (`*u8` pointers) are unaffected** — being
resolved as labels is exactly right for those, which is why only the one `u16` field failed.

This is reported from aeon's side as a symptom. It has not been raised with sigil and no claim is
made here about sigil's internals.

## 8. Every budget, before and after

Three sections is parcel 8's measurement, re-run here and reproduced. Five sections is this
parcel's, off the same instruments.

| | 3 sections (6,144 px) | **5 sections (10,240 px)** | ceiling |
|---|---|---|---|
| act art pool | 472 tiles | **480 tiles** | 768 |
| pool pages | 8 | **8** | 256 (`PAGE_TABLE_MAX`) |
| **worst camera window** | 8 frames | **8 frames** | **12** (`PAGE_FRAMES`) |
| — where | tile left 529, cam x≈4,392 | **the SAME window** (5,059 windows at that count, was 2,703) | |
| camera windows evaluated | 257,367 | **443,223** | — |
| collision attr entries | 105 | **105** | 255 |
| sections | 9 | **15** | 48 (`MAX_ACT_SECTIONS`) |
| non-empty blocks | 384 of 2,304 | **640 of 3,840** | — |
| painted columns | 768 | **1,280** | 1,280 = the whole act |
| local maps | 9 sections | **15 sections, 6 distinct** | — |
| `s4.s2clip.bin` | 821,305 B (`c869deaf…`) | **821,708 B** (`45268bc1…`) | 4 MB |

**The tightest budget's CEILING did not move. Its EXPOSURE nearly doubled, and that is not the
same thing.** The worst window is still 8 of 12 frames, still the same 80 x 60-tile window over
the same busy art at camera x ≈ 4,392 that parcel 8 found — the dispatch flagged this measure as
LOCAL and that is exactly why the peak held. But the number of camera positions sitting AT that
peak went **2,703 -> 5,059**, out of 257,367 -> 443,223 windows evaluated. As a share of all
camera positions that is 1.05% -> 1.14%.

**A reader who sees "8 of 12, unchanged" will conclude the widening was free and that is wrong.**
Four frames of headroom is a static fact about the worst case; how often the player stands in a
worst case is a different fact, and it grew by 87%. Nothing in the static proof bounds what
happens at the ceiling — the fill-throughput lag in §10's table is the runtime finding this makes
more likely to be seen, not less.

**The pool grew by eight tiles for 4,096 px of new ground.** EHZ reuses its art that heavily: the
whole zone's tileset is 914 tiles and only 633 are referenced anywhere in it.

**105 attr entries is the whole zone's requirement**, not the clip's — `zone.json` records the
same 105 for all six donor sections. It cannot rise however wide this act gets.

**No budget refused.** The thing that refused was the donor's crop (§1), and that is a content
fact, not a budget.

## 9. The clip ROM

`S2CLIP=s2_ehz_boot ./build.sh` produces **`s4.s2clip.bin`, 821,708 bytes, md5
`45268bc176e92956941c4217c8fa6bbb`** — reproduced byte for byte across two consecutive builds at
the landing. That is **+403 B** over parcel 8's three-section clip ROM (821,305 B, `c869deaf…`),
which is what two more sections of block/strip/local-map/entity tables cost; the act art pool grew
by only 8 tiles (§8), so almost none of it is art.

The bake announces the new grid on the way past, and these two lines are the ones §10 tells a
reader to check if they suspect a stale ROM:

```
clip_rom_bake: engine grid 5x3 -> games/sonic4/data/generated/ojz/act1/act_grid.emp (15 sections)
clip_rom_bake: DONE — s2_ehz_boot is in games/sonic4/data/generated/ojz/act1; 480 pool tiles in 8 pages, 105 of 255 attr entries
```

§11 carries the full landing evidence, including the two build md5s and the canonical shapes.

## 10. ★ THE RUNTIME CHECK — TAGGED FOR THE FOREGROUND

**No emulator was used in this parcel and none may be.** Somebody has to do this by hand.

**Boot:** `s4.s2clip.bin` from `S2CLIP=s2_ehz_boot ./build.sh`. On the `DEBUG=1` twin **press B
first** or the harness's free flight is the condition under test.

**The thing the owner asked about — how far right it goes:**

1. **Hold RIGHT from the spawn and keep going.** The ground should be continuous all the way to
   **x = 10,240**, which is the end of the act. That is 5 sections, not 3 — he should pass the old
   stopping point at 6,144 without anything happening there at all.
2. **At the far right the camera should STOP** with painted ground under the player and painted
   art to the screen edge. **There should be no vertical line of background, anywhere.**

| what you see | what it means |
|---|---|
| the camera stops at the right with ground under him and art to the edge | **fixed.** What the static proof says: all 1,280 columns measure painted |
| a hard vertical line at **x = 6,144** still | the ROM is the old one — check the build re-baked (`clip_rom_bake: engine grid 5x3 ... (15 sections)` and `DONE ... 480 pool tiles in 8 pages`) |
| a hard vertical line at any **other** fixed world x | **the static account is wrong.** Report the x |
| art that **lags behind the camera and fills in when you stop** | not a bound — a fill-throughput lag. Still the plausible new finding, and now over twice the distance: the worst window is 8 of 12 frames and there are 5,059 windows at that count instead of 2,703 |
| the camera stopping SHORT of 10,240 with painted ground continuing past the screen edge | a camera-clamp finding, not a paint one. Report where it stopped |

**Expected, not a bug — tell him before he finds it:**

3. **At x ≈ 1,344 the ground falls away** (EHZ's own jump; floor 228 px below at y ≈ 872). He
   should land.
4. **TWO pits with no floor at all, at x 4,672..4,863 and x 9,472..9,663.** Both are Emerald
   Hill's own. In Sonic 2, falling in kills you at y = 800 and you restart; **here he will just
   keep falling**, because this engine has no death. The second one is new only in the sense that
   the act now reaches it. Declared in `clips.json`, count AND runs, and the build checks both.
5. **Any fall that gets under the terrain never ends** — 1,232 of 1,280 columns, up from 744 of
   768. Arithmetic, not a regression.
6. **The level does NOT end where Sonic 2's does, and he will notice.** The act stops at
   x = 10,240; Emerald Hill act 1's own end — the stretch where the signpost stands — is at
   x 10,240..10,656 and is **not in this ROM**. 736 px of fully drawn Emerald Hill is truncated
   (§1), because an act's width is a whole number of 2,048 px sections and the zone is 5.36 of
   them. The camera stopping there with ground under him is CORRECT; it is just not the end of the
   level.

**Verify DURING motion.** Row 1 versus row 4 of that table is only distinguishable while moving
and while stopping.

## 11. Evidence

**The landing ran on 2026-09-18**, in worktree `land/0918` off `origin/master` `2395d575`. Every
figure below was produced on that tree; none is carried forward from the parcel's own worktree.

### 11.1 The landing check

`tools/landing_build.sh` (no `FAST=1`, no `NO_LINT=1` — it refuses both), on the merge plus the
§1 correction, commit `ff852186`:

```
exit code      0
finished=0                       (the stamp that separates a completed run from a killed one)
land-gate      STAMP WRITTEN key=58fd606e4d66b8ff head=ff8521869adf
```

Aggregate totals, not a tail excerpt:

| lane | result |
|---|---|
| pre-build tool suite (`pytest tools -m "not needs_build"`, runs once, in the `s4` shape) | **3,150 passed, 2 skipped, 28 deselected, 143 subtests passed** (87.19 s) |
| `emp_expect_fail` | **56/56 cases** (54 comptime + 2 link) |
| `needs_build` lane, `s4` | 10 passed, 18 skipped, 40 subtests |
| `needs_build` lane, `s4.debug` | 15 passed, 13 skipped |
| `needs_build` lane, `demo.debug` | 1 passed, 27 skipped |
| `needs_build_lane.py` aggregation over the three shapes | **27 ran, 0 deferred, 0 failed, 1 exempted** — `EXIT_needs_build=0` |

The one exemption is `test_deb2_appendix[demo.bin]`, which needs `demo.bin` — a shape
`LANDING_SHAPES` deliberately omits. **Exempted is not passed**; it is graded by `./build.sh demo`
and the nightly.

### 11.2 The shapes it built

| file | bytes | md5 |
|---|---|---|
| `s4.bin` | 821,479 | `ae62156a66c9c3f13e93940e938c340e` |
| `s4.debug.bin` | 848,075 | `b15ef259523f67ac963ef0cf4df003dc` |
| `demo.debug.bin` | 104,707 | `f740c22498f6ad132ac9f8bd978c9350` |

**These are the same three md5s §3 reports from before the parcel**, reproduced here by a different
worktree on a different day: no canonical byte moved, and §3's claim survives the landing rather
than merely being repeated by it.

### 11.3 The clip ROM

`S2CLIP=s2_ehz_boot ./build.sh` → **`s4.s2clip.bin`, 821,708 bytes, md5
`45268bc176e92956941c4217c8fa6bbb`.**

**Reproduced across three builds**, and the three were not interchangeable — one ran *before* the
§1 correction touched `clips.json` and two *after*:

| build | when | bytes | md5 |
|---|---|---|---|
| 1 | before the `clips.json` note was corrected | 821,708 | `45268bc176e92956941c4217c8fa6bbb` |
| 2 | after | 821,708 | `45268bc176e92956941c4217c8fa6bbb` |
| 3 | after | 821,708 | `45268bc176e92956941c4217c8fa6bbb` |

So the ROM is reproducible **and** the corrected prose in the clip manifest reaches no byte of it —
which is the control that says the correction was documentation, not a content change. The bake
printed `engine grid 5x3 ... (15 sections)` and `480 pool tiles in 8 pages, 105 of 255 attr
entries` on each run (§9).

The landing worktree had no donor tree (it is gitignored, so a fresh worktree lacks it);
`python3 tools/s2_zone_convert.py convert s2disasm@EHZ` regenerated it, reporting `6x1 = 6
sections, 914 tiles, 119231 painted cells` and `175616 cells round-tripped, 0 differing`, and the
result is **md5-identical, file for file, to the main checkout's donor tree**. So §1's band
measurements and this ROM were taken over the same donor bytes.

### 11.4 The instrument behind §1, as a command a reader can re-run

§1's counts use *tile index != 0* (nametable bits 0..10), not *word != 0*. That choice is validated
by reproducing the converter's own published total:

```python
# zone-wide: rows 0..127 of sections 0..5, columns to the crop edge at tile 1372
import struct
D = "games/sonic4/data/donors/s2disasm/EHZ"
tot = 0
for sec in range(6):
    w = struct.unpack(">65536H", open(f"{D}/section_{sec}.tiles.bin", "rb").read())
    for r in range(128):                       # crop height
        for v in w[r*256 : r*256 + (256 if sec < 5 else 92)]:
            if v & 0x7FF:                      # bits 0..10 = tile index
                tot += 1
print(tot)          # 119231  ==  zone.json counts/painted_cells
```

**119,231 is `zone.json`'s own `counts/painted_cells`.** The same script with `if v:` instead gives
175,276 of 175,616 crop cells (99.8%) — the near-vacuous figure §1 discarded. For the collision
planes, swap the file for `section_5.collattr.bin` / `.collattrb.bin` and the mask for `0x3FF`
(bits 0..9 = shape index).

### 11.5 What is NOT evidenced here

**§10's runtime check has not been run.** No emulator was used anywhere in this parcel or its
landing; §10 is tagged for a foreground session with the owner and is still open. Everything above
is static: assembler, generators, gates and file bytes. **A green landing says the ROM builds and
reproduces; it does not say the act looks right when Sonic runs east.**

## 12. What the next act needs from this

* **`OJZ_WIDE_FILL_ROWS` is a floor, not a design.** A clip act wider than its region document
  shows one flat preset over everything past 6,144 px. The right answer is for the region document
  to be per-act data the bake can produce, which is `effects_gen` work and is not booked here
  beyond this sentence.
* **736 px of painted Emerald Hill — 92 fully drawn columns, 416 px of them playable — is
  truncated** while an act's width must be a whole number of 2,048 px sections. A clip act owning
  a NON-section-aligned extent is the parcel-7 idea in its last surviving form, and it is the only
  thing that recovers them. This parcel did not need it; the next reader of this file might.
* **Six sections becomes available the moment an act can hold two clips** — the padding at the end
  of EHZ is exactly where a corridor or a second zone would go, which is row 7.
