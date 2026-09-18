# A clip act declares its own grid — and Emerald Hill is five sections wide, not six

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

**They do not, and the number that binds is the donor's own crop.** EHZ's converted tree
declares `extent.crop_tiles` ending at tile **1372**, i.e. painted content stops before
x = **10,976 px**, and `clip_manifest` R9 refuses a `src_rect` past the crop because outside it
there is only the converter's zero padding — "a clip that reads smaller than it looks". Six
sections need 12,288. So the sentence this lane has been repeating since parcel 6 —
*"EHZ itself is six sections wide (12288 px)"*, written into `clips.json` as fact — is true of
the donor's **padded section grid** and false of its **painted content**: the last 1,312 px of
that sixth section is padding.

**Five sections — 10,240 px — is the widest act every column of which the donor can paint**, and
painting every column is the whole point, because the defect the owner has reported twice is a
hard vertical edge where the painted world stops. So the act is 5 x 3 and the clip is
10,240 x 1,024.

**The cost of keeping the act a whole number of sections is 416 px.** Sonic 2's own camera box
for EHZ act 1 is `x max 10656`; the act stops at 10,240, so the very end of the level — where the
signpost stands — is inside the donor's crop but not inside a whole fifth section.

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
| `s4.s2clip.bin` | 821,305 B (`c869deaf…`) | **§9** | 4 MB |

**The tightest budget did not move.** The dispatch flagged the page window as the one to watch
because it is a LOCAL measure — and that is exactly why it held: the worst window is the same
80 x 60-tile window over the same busy art at camera x ≈ 4,392 that parcel 8 found. Five sections
put 185,856 more windows under the instrument and none of them beat it. Four frames of headroom,
unchanged.

**The pool grew by eight tiles for 4,096 px of new ground.** EHZ reuses its art that heavily: the
whole zone's tileset is 914 tiles and only 633 are referenced anywhere in it.

**105 attr entries is the whole zone's requirement**, not the clip's — `zone.json` records the
same 105 for all six donor sections. It cannot rise however wide this act gets.

**No budget refused.** The thing that refused was the donor's crop (§1), and that is a content
fact, not a budget.

## 9. The clip ROM

See §11 for the reproduced figures; they are written there and not here so that the number and the
evidence that it reproduces sit together.

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

**Verify DURING motion.** Row 1 versus row 4 of that table is only distinguishable while moving
and while stopping.

## 11. Evidence

Filled in at §12 with the landing-build and clip-build figures, each reproduced twice.

## 12. What the next act needs from this

* **`OJZ_WIDE_FILL_ROWS` is a floor, not a design.** A clip act wider than its region document
  shows one flat preset over everything past 6,144 px. The right answer is for the region document
  to be per-act data the bake can produce, which is `effects_gen` work and is not booked here
  beyond this sentence.
* **The 416 px tail of EHZ act 1 is unreachable** while an act's width must be a whole number of
  sections. A clip act owning a NON-section-aligned extent is the parcel-7 idea in its last
  surviving form, and this parcel did not need it.
* **Six sections becomes available the moment an act can hold two clips** — the padding at the end
  of EHZ is exactly where a corridor or a second zone would go, which is row 7.
