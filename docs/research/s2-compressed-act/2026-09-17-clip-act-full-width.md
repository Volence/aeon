# The act is painted to its edge now — and Emerald Hill's own pit came with it

S2-COMPRESSED-ACT parcel 8, 2026-09-17. Branch `parcel/s2-clip-extent` (the branch is named
for the fix that was planned; the owner chose the other one mid-parcel — see §1).
Subject: `s4.s2clip.bin`, rebuilt from `S2CLIP=s2_ehz_boot ./build.sh`.

---

## 1. What was asked, and the reversal in the middle of it

The owner booted the clip act and said, in his own words:

> "No it's just literally missing parts of the right side of the edge, I'm not talking about
> below or anything, I understand there's no death pits here (there's no death at all in our
> engine currently). The forground just randomly ends at that 409x spot"

Parcel 7 had already found the mechanism (`2026-09-17-clip-act-reachability.md` §2): a clip act
is baked into the SHIPPED act's slot at the SHIPPED act's grid, so a 4,096 × 1,024 clip lived
inside a 6,144 × 6,144 act and at x = 4,096 the art and both collision planes stopped dead.

Two fixes were on the table. **Shrink the act to fit the clip** — a clip act owning its own
extent, which is what this branch is named after — or **widen the clip to fill the act.** This
parcel started on the first and was redirected to the second by the owner, in these words:

> "yeah just finish painting emerald hill out, add more sections if need be (but we have another
> so it should be fine?)"

He is right that there was room, and **the extent work was not done**: `GRID_W`/`GRID_H`,
`act_descriptor.emp` and R21 are untouched, and no canonical byte moved. §7 prices the extent
option anyway, because it is still the right answer for a clip that is *smaller* than an act.

## 2. The change, in one line

`games/sonic4/data/clips/s2_ehz_boot/clips.json`: the one clip's `src_rect` and `dst_rect` go
from `w: 4096` to `w: 6144`. That is the whole fix. Everything else in this parcel is the
consequence of it.

6,144 is `grid_w` 3 × `SECTION_SIZE` 2,048 — **the act's own width.** The painted foreground now
runs to the last column the camera can reach, and `EDGE_CLAMP` stops the camera exactly there.
There is no unpainted remainder left to walk into.

Height stays 1,024: EHZ's whole crop is 128 tiles tall (`zone.json` `extent.crop_tiles`) and R9
refuses a rect past it. **The act's lower two section rows are still air** — see §5.

## 3. What it cost, measured on the bake

Baseline is the parcel-7 ROM, rebuilt here and its md5 reproduced
(`7f40876af03b35f03f0ef9d6bd527743`), so these are two measurements of the same instrument.

| | before (4,096 wide) | after (6,144 wide) | ceiling |
|---|---|---|---|
| act art pool | 286 tiles | **472 tiles** | 768 (`POOL_TILE_CEILING`) |
| pool pages | 5 | **8** | 256 (`PAGE_TABLE_MAX`) |
| worst camera window | 5 pages | **8 pages** | **12** (`PAGE_FRAMES`) |
| collision attr entries | 66 | **105** | 255 |
| non-empty blocks | 256 of 2,304 | **384 of 2,304** | — |
| painted columns | 512 | **768** | 768 = the whole act |
| `s4.s2clip.bin` | 821,211 B (md5 `7f40876a…`) | **821,305 B** (md5 `c869deaf…`) | — |

**The tightest of those is the camera window at 8 of 12 frames**, and it is the one to watch: it
is a *local* measure (the worst 80 × 60-tile window, at tile left 529 / camera x ≈ 4,392), so it
grows with how busy the art is under the camera rather than with how much act there is. Four
frames of headroom. Everything else is comfortable.

## 4. ★ EMERALD HILL ACT 1'S OWN BOTTOMLESS PIT, AT x 4,672..4,863

Parcel 7 predicted this by name and used it as the argument *against* widening: *"a 3-section
clip trades this edge for a worse one."* It was right that the pit is there. It was wrong that
the trade is worse, and the owner's instruction settles which edge he cares about.

**Measured, on the emitted bytes:** 24 columns of 8 px. The **art is fully drawn** — all 128
cells of every one of those columns carry a tile, so you *see* a pit, not a void. The
**collision cells are present too** (12-18 non-zero cells per column) — they are the pit's walls,
and every one of them is LRB-only, so **no column in the run has a `SOLID_TOP` surface at any
height, on either plane.** There is nothing to land on.

**This is faithful Sonic 2 level design, not a conversion defect.** Sonic 2 ships that pit and
survives it the way it survives every pit: **EHZ act 1 declares a level bottom boundary at
y = 800** (`s2_donor.level_size` → `(0, 10656, 0, 800)`), and a player who falls past it dies and
restarts. **This engine has no death of any kind**, which the owner said himself and had already
set aside. So here, the same pit is an endless fall.

**The alternative was worse.** Stopping the clip at x = 4,672 to avoid the pit just moves the
hard edge he reported from 4,096 to 4,672 — the same defect, 576 px to the right.

### What that did to the gate, and what it gives up

`tools/clip_reachability.py` check (2) — "a landing surface on every reachable plane" — would
refuse this act. It now takes a **`floorless_columns` declaration**, per plane, inside
`unpainted_remainder`, beside the `unbounded_fall` one parcel 7 added:

```json
"floorless_columns": {
  "why": "<why this act ships with it>",
  "planes": { "A": { "columns": 24, "x_runs": [[4672, 4864]] } }
}
```

**It is stricter than the declaration next to it.** `unbounded_fall` compares a count;
this compares the count **and the runs**, exactly. Mutation B in §6 is a pit that MOVED with the
count unchanged — a count-only check passes that and this does not.

**What it still catches**, written down because a declaration channel is a weakening unless the
boundary is:

* a reachable plane with floorless columns and **no declaration for that plane** — the original
  failure, character for character, including the whole of plane B the moment a crossover marks
  one (parcel 7 §4's latent defect stays armed — proved by
  `test_a_floorless_declaration_on_plane_b_does_not_cover_plane_a`, a unit row rather than one
  of §6's real-tree mutations, because plane B is unreachable in this act so there is no real
  tree on which it fails);
* a declared run that **moved, grew or shrank by a single 8-px column**;
* a declaration that has gone **stale** because the columns gained a floor.

**What it no longer catches, named rather than implied:** this act shipping with a pit a player
can fall into forever. That is now a fact in `clips.json` with the donor's own bottom boundary
written next to it. **The case deliberately given up is "the build refuses an act with an
unsurvivable hole in it."** It comes back the day this engine has a death plane: give the act a
bottom boundary, the runs go empty, and the stale half of this same check turns red until the
declaration is deleted.

## 5. What is still unpainted, precisely

**Nothing on the x axis.** `x_from` is 6,144, which is the act's extent, and the gate checks it
two-sided: if a future re-bake loses a section, the build says so.

**The y axis is unchanged and is not fixed by this.** The clip paints down to y = 1,024 of a
6,144 px act; 5,120 px below that is air. That is the parcel-7 finding the owner explicitly set
aside, and its numbers moved with the widening:

| | before | after |
|---|---|---|
| unbounded-fall columns (air below the LAST landing surface) | 512 of 512 | **744 of 768** |
| floorless columns (no landing surface at all, plane A) | 0 | **24** |

744 + 24 = 768. **The rise from 512 to 744 is arithmetic, not a regression**: more painted ground
means more column interiors a body can get under. Sonic 2's terrain interiors are LRB-only
(`$2000`) and stop nothing falling; the donor game survives that with the y = 800 boundary.

## 6. The gate change, red-first, on the real baked tree

Three mutations, each on a **copy** of the real baked tree with the real tree untouched, each
with the changed bytes printed **on disk before** the red run, each restored by discarding the
copy. The unmutated copy of the same tree exits 0 — the control that says the mutations are what
turned it red.

| mutation | on disk | result |
|---|---|---|
| **A** — give ONE declared pit column a floor (x = 4,672) | `sec2_strips_a.bin` byte 56446: `0 → 1` | exit **1** — "declares 24 … bytes have 23 at [(4680, 4864)] … **FEWER**" |
| **B** — SHIFT the pit: floor into x = 4,672 **and** clear x = 4,864 | byte 56446 `0 → 1`; plane-A column at 75008, nonzero `6 → 0` | exit **1** — "24 at [(4680, 4872)] … **The COUNT agrees and the RUNS do not**". *A count-only declaration passes this.* |
| **C** — clear one column's plane-A collision far from the pit (x = 1,600) | `sec0_strips_a.bin` plane-A column at 155712, nonzero `3 → 0` | exit **1** — "25 at [(1600, 1608), (4672, 4864)] … **MORE**" |
| control — the same baked tree, unmutated | — | exit **0** |

Plus **16 new rows** in `tools/test_clip_reachability.py` (38 total in the file, up from 22),
donor-free and build-free — including the one that matters most,
`test_the_undeclared_case_is_untouched_and_still_fails`, and an 8-case parametrization proving a
**malformed declaration is Unmeasurable (exit 2), never a pass**.

Runner, named: `build.sh`'s `S2CLIP` shape, `gate strict "clip_reachability.py"`, immediately
after the ten `verify_level_bin` lanes. Unchanged wiring; the gate it runs is the one that
changed. Expectations are derived as before — `SOLID_TOP`, `COLL_CELL_W/H` from
`engine/system/constants.emp`, the strip layout from `ojz_strip_gen`'s source, the grid from the
descriptor, the rectangle from the manifest.

## 7. The extent option, priced but NOT built

The owner reversed onto widening before this was written, so it is an estimate from the reading
done first, not a measurement — **flagged as such.** It still matters, because widening only
works while the donor has content to reach with, and row 7's corridor will not.

A clip act cannot declare `GRID_W`/`GRID_H` today: they are hand-written in
`act_descriptor.emp`, shared with the canonical ROM, and R21 exists to force the manifest to
agree with them. **The available identity channel is the generated `.emp` module the bake emits**
(parcel 6's finding: no `-D` reaches `sigil build`, and the S2CLIP shape forbids touching
`map.toml`) — so a clip act would have to get `grid_w`/`grid_h` out of a generated module the
descriptor reads, which means the shipped descriptor takes them from a generated symbol instead
of two `const` lines. **That moves canonical bytes unless the generated symbol reproduces the
shipped 3 × 3 exactly**, which it would for the shipped act — but proving it is the parcel, not
a footnote. R21 would then be re-aimed rather than relaxed: it would hold the manifest to the
**generated** grid instead of the hand-written one, which is the same guarantee against a
short local-map table.

**And it would not have solved the reported bug better.** Shrinking the act to 4,096 wide moves
the camera clamp onto the painted edge, which is the same end state widening reaches — except
the player sees two sections of Emerald Hill instead of three.

## 8. ★ THE RUNTIME CHECK — TAGGED FOR THE FOREGROUND

**No emulator was used in this parcel and none may be.** Somebody has to do this by hand.

**Boot:** `s4.s2clip.bin` from `S2CLIP=s2_ehz_boot ./build.sh`. On the `DEBUG=1` twin **press B
first** or the harness's free flight is the condition under test.

**The one thing the owner asked about — the right-hand edge:**

1. **Hold RIGHT from the spawn and keep going.** The ground should be continuous all the way to
   **x = 6,144**, which is the end of the act.
2. **At the far right, the camera should STOP** with painted ground under the player and painted
   art to the screen edge. **There should be no vertical line of background, anywhere.**

| what you see | what it means |
|---|---|
| the camera stops at the right with ground under him and art to the edge | **fixed.** What the static proof says |
| a hard vertical line at **x = 4,096** still | the ROM is the old one — check the build actually re-baked (`clip_rom_bake: DONE … 472 pool tiles in 8 pages`) |
| a hard vertical line at any **other** fixed world x | **the static account is wrong.** Every one of the 768 columns measures painted. Report the x |
| art that **lags behind the camera and fills in when you stop** | not a bound — a fill-throughput lag. Would be a NEW finding, and the plausible one now: the worst camera window went from 5 pages to 8 of 12 |

**Expected, not a bug — tell him before he finds it:**

3. **At x ≈ 1,344 the ground falls away** (EHZ's own jump; floor 228 px below at y ≈ 872). He
   should land.
4. **At x 4,672..4,863 there is a pit with no floor at all.** That is Emerald Hill's own. In
   Sonic 2 falling in kills you at y = 800 and you restart; **here he will just keep falling**,
   because this engine has no death. Not a conversion defect and not something this parcel
   broke — it arrived with the third section, it is declared in `clips.json`, and the build
   checks it.
5. **Any fall that gets under the terrain never ends** — parcel 7 §3a, unchanged, 744 of 768
   columns.

**Verify DURING motion.** Row 1 versus row 4 of that table is only distinguishable while moving
and while stopping.

## 9. What a multi-clip act needs on top of this

Widening is the one-clip answer and **does not generalise**:

* **R20 still refuses two clips.** `ojz_strip_gen` reads exactly one tileset
  (`project.json` zones[0]), so a one-clip act is an ordinary aeon act. A per-cell tileset key
  is row 7's work and nothing here touched it.
* **"Fill the act" stops being available** the moment the act is not one donor zone wide. Row 7
  is two clips plus a corridor; the corridor is *authored*, not donor content, and there is no
  Emerald Hill to keep painting. That is when the extent work in §7 becomes the answer rather
  than an alternative to it — and §7 is why the clip rectangle should not be the thing an act's
  bounds are keyed to.
* **`floorless_columns` is already per-plane and per-run**, so a second clip's pits declare
  alongside the first's without the schema moving. `unpainted_remainder`'s `x_from` is **one
  trailing edge on one axis** and is the part that will not survive a multi-clip act with a hole
  between the clips — the gate already distinguishes a hole from an edge ("that is a hole, not an
  edge"), so the hole case fails loudly rather than silently, which is the right failure to
  inherit.
* **The pit problem gets worse with every zone added**, and the real answer is not a declaration
  channel — it is a bottom boundary and a death. That is booked, not designed.
