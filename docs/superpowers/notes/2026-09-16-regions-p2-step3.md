# Regions part 2, step 3 — the background belongs to the region, and `Sec` becomes pure storage

Parcel `parcel/regions-p2-step3`, based on aeon `origin/master` `c2c90854`.
Spec: empyrean `origin/main:docs/superpowers/specs/2026-09-14-regions-part-2-design.md`
§4.1 / §4.5 / §4.6 and step-table row 3, read at empyrean `e4057d58`.
**No emulator was used.** The step's gate, BG-NT-IDENTICAL, needs one; what I expect it to
show, and the way it could pass for the wrong reason, are stated below and not claimed.

## What landed

| what | where |
|---|---|
| `Section_RedrawPlanes`' Plane B half resolves the REGION under the camera CENTRE, through `Region_Resolve` | `engine/level/section.emp` |
| `Sec.sec_bg_layout` DELETED; `Sec` 26 → 22 B; `Region.rg_bg_layout` gains its first reader | `engine/structs.emp`, `games/sonic4/data/levels/ojz/act1/act_descriptor.emp` |
| the 8-byte BG plane tracker, seeded by BOTH synchronous blits | `engine/ram.emp`, `engine/level/bg.emp`, `engine/level/section.emp` |
| `ensure(sizeof(Region) == 22)` and `ensure(sizeof(Sec) == 22)` beside the declarations | `engine/structs.emp` |
| the build-red guard: a poison whose whole content is "this name must not resolve" | `games/sonic4/test/poison/poison_sec_bg_layout.emp`, `tools/emp_expect_fail.py` |
| the readable half of the same guard | `tools/test_sec_bg_layout_is_deleted.py` |
| the two `sizeof(Sec)` stride pins, 26 → 22, with the sigil oracle note | `engine/level/section.emp`, `engine/level/tile_cache.emp` |
| doc sync, three stale record tables, a new `.emp` pitfall, three bookings | `docs/ENGINE_ARCHITECTURE.md`, `docs/LEVEL_EDITOR_SPEC.md`, `docs/ART_PIPELINE_CONTRACT{,_ADDENDUM}.md`, `docs/EMP_PITFALLS.md`, `docs/DEFERRED_WORK.md`, `tools/ojz_strip_gen.py` |

**One query, three callers.** `Section_RedrawPlanes` now asks `Region_Resolve` the same
question, at the same point (`Camera_X + CAM_SCREEN_HALF_W`, `Camera_Y + CAM_SCREEN_HALF_H`),
that `Parallax_CheckBoundary`'s crossing and the init ladder's parallax boot select already
ask. That is the point of the deletion: the 2026-08-26 precedence bug is what two private
answers to one question look like when they drift, and a third — the section grid — was still
standing. `Section_GetSecPtrXY` leaves this routine; the entity window keeps it alive.

This is the **first cross-module call from `engine/level/section.emp` into
`engine/level/parallax.emp`** (measured: `grep` for `jbsr Parallax*/Region*/Effects*` in
`section.emp` returned nothing before this parcel). It is in the shape `Region_Resolve`'s own
header asks for — that header already names two callers, one of them across the engine/game
seam — but it is a new edge and worth an overrule if the layering is meant to be one-way.

## Findings, in the order they matter

### 1. §4.5's boot premise is false at the pin, and `BG_Init` cannot be region-aware

The spec asks `BG_Init` to "resolve the boot region first (`Region_Resolve` on the start camera
centre; **`Camera_Init` precedes the boot select**)". That parenthesis is true of the PARALLAX
boot select and false of `BG_Init`. Measured at the one shipped init ladder,
`games/sonic4/test/ojz_scroll_test.emp`:

| line | call |
|---|---|
| 629 | `jbsr Level_LoadArt` — which tail-calls `BG_Init` (`engine/level/load_art.emp:199`, `jbra BG_Init`) |
| 677 | `jbsr Camera_Init` |
| 826 | `jbsr Section_Init` |
| 854 | `jbsr Section_UpdateColumns` — the synchronous `Section_RedrawPlanes` |
| 894 | `jbsr Parallax_Init` |

`Camera_Init` is the only writer of `Camera_X`/`Camera_Y` before the plane fill, and it runs
48 lines BELOW the routine that is supposed to query it. `Current_Act_Ptr` **is** live inside
`BG_Init` (`load_art.emp:59` sets it at the top of the same proc), so a `Region_Resolve` there
would not crash — it would answer, and answer about a camera that does not exist: `(0,0)` plus
half a screen after boot's RAM clear, or the PREVIOUS act's position on a re-entry. And today
it would answer wrongly *invisibly*, because all ten of act 1's region rows (eleven in DEBUG —
`OJZ_E2_SNAP_ROWS` adds one) leave `rg_bg_layout` at 0. That is step 2's finding-2 shape again:
an instrument that cannot produce the answer it claims to look for.

**Shipped instead:** `BG_Init` blits `Act.act_bg_layout` as before and seeds the tracker with
what it actually blitted. `Section_RedrawPlanes` — later in the SAME init, after `Camera_Init`
and after the DEBUG boot-position override, still before display-on — does the region-aware
blit and re-seeds. The first VISIBLE frame is the region's picture on every path, and "the
tracker names the blob the plane holds" is true at every instant rather than from the second
writer onwards. Cost: one wasted 8192-byte blit at load on any act that ever authors a
non-default layout under its start point, with the display off.

Booked as **BG-BOOT-REGION-BLIT** with three costed ways out. **This is my call and it is the
one I most want contradicted** — option 2 there (make `BG_Init` the BG *tile* loader only and
let `Section_RedrawPlanes` be the sole nametable writer) is cleaner by the one-authority rule
and deletes a whole blit; I did not take it because it makes the picture depend on
`Section_Plane_Dirty` being set on every boot path, and I did not enumerate those paths.

### 2. No window arithmetic, for the same reason, one step later

§4.5 asks the blits to write "a WINDOW of `PLANE_V_CELLS` rows starting at the row the initial
scroll selects". The scroll it means is `Parallax_Current_Vscroll_BG`, and **`Parallax_Init`
runs after both blits** on both ladders (boot: 854 then 894; warp: the `Section_UpdateColumns`
of step 6 then the `Parallax_CheckBoundary` of step 7). A window start row computed at either
blit today could only read 0.

It costs nothing here because the map height IS the plane height (`rg_bg_span` 0 =
`PLANE_B_SPAN` = 512 = `PLANE_V_CELLS * 8`), so the window is rows 0..63 and the whole-image
blit **is** the window. Booked; step 5 supplies `BG_Plane_Top` and step 8 makes it mandatory.

### 3. A deleted field read as `Struct.field(aN)` raises NO field diagnostic

The step asks for "build red if any `.emp` still names `sec_bg_layout`". It IS red, in every
spelling I could construct — but one of them is red for a reason that never mentions the field.
Measured against the release sigil that builds this tree, **control run last**:

| probe | result |
|---|---|
| `offsetof(Sec, sec_bg_layout)` in a poison, reachable via `--extra-entry` | **RED**: `[Error] offsetof: struct Sec has no field sec_bg_layout`, 1 error |
| `movea.l Sec.sec_bg_layout(a0), a1` in a REACHABLE module (`section.emp`, at the real site) | **RED**, `error: the contract closure DROPPED 1 instruction(s)` — no field diagnostic anywhere |
| the same line in an UNREACHABLE module | **RED**, same message |
| **CONTROL**: the same unreachable module reading `Sec.sec_objects(a0)` | **GREEN**, exit 0, no drop |

The displacement form does not resolve the field name at all; it survives elaboration and is
stopped downstream by the contract-closure analysis noticing an instruction it cannot read.
`sigil build` itself refuses and writes no ROM, so this is not a silent miscompile. `CONTRACTS=0`
was **not** measured — `build.sh` refuses to pair it with `FAST=1` ("leaves the build checked by
nothing at all"), and a canonical run to answer it was not worth four minutes; if anyone wants
that answer it is one build.

Generalised into `docs/EMP_PITFALLS.md` §14. Two artifacts, deliberately unequal:

* **`poison_sec_bg_layout.emp`** — the strong half. Registered in `tools/emp_expect_fail.py`
  (fragment transcribed from the measured run, count 1), so it is graded on every canonical
  build and before every merge, in the compiler's own words. **Red-proven**: with the field
  restored to `Sec` (and the two stride pins moved to 26, and `ojz_sec()` given the argument
  back — a defaulted field must still be spelled at the constructor, `[struct.missing-field]`,
  which is its own layer of the guard), that poison builds **CLEAN, exit 0, 0 errors**, which is
  exactly the FAILED the lane reports.
* **`tools/test_sec_bg_layout_is_deleted.py`** — the readable half, and **labelled weaker**. It
  names the file, the line and the field. It is blind to a rename, and deliberately blind to
  comments and to `ensure` message strings, because a history note saying where the field went
  is exactly what a reader grepping the old name should find. Red-proven with the mutation
  quoted from disk; restored from the committed baseline.

⚠ **A process note against myself.** My first red-proof of the `sizeof` ensures restored
`engine/structs.emp` from `HEAD` — and `HEAD` did not yet contain the ensures, so the restore
silently deleted the artifact I had just proven. Commit the artifact BEFORE red-proving it;
"restore from a committed baseline" is only a restore if the baseline contains the work.

### 4. Where the bytes went, MEASURED — and the spec's ROM figure is wrong in an interesting way

The step table estimates **ROM −36 (9 sections × 4 B)** and **RAM +8**. RAM is exactly +8.
ROM is **+55 / +56**, and the −36 is real but never reaches the file.

**Four canonical shapes, both revisions, all exit 0.** Base `c2c90854`, after `282935dc`.
Wall clock across the runs: `up 6:10` to `up 6:38`, load average 2.9–6.7 (parallel sessions on
this box), so the elapsed times are inflated and are context, not a benchmark.

| shape | base size | base md5 | after size | after md5 | Δ |
|---|---|---|---|---|---|
| `s4.bin` | 820477 | `46f2e4e5390c4627b84a298a2dc4a311` | 820532 | `9a3bdf176246b8c95d6360dcb7e153a3` | **+55** |
| `s4.debug.bin` | 846856 | `317e18245cb1ed9eaf9ffd40dab7fe98` | 846912 | `63980e7ef62c80ce7928b1b13da3629c` | **+56** |
| `demo.bin` | 97173 | `f8d51cb8a4308c6af53a5dc102e70fa8` | 97229 | `4876455d3fa63cc8455079999601c22a` | **+56** |
| `demo.debug.bin` | 103606 | `623c01672e168f7ac94e71474c5c8fa7` | 103662 | `9f5d490cbef277e186e015dd80c98524` | **+56** |

The four base figures are my own rebuild of `c2c90854` in this worktree and they are
**byte-identical to step 2's landed figures**, which is the check on the claim that the
BG-NT-IDENTICAL docs commit between them moved no bytes.

**By symbol span (release shape; the debug and demo shapes agree on every row that exists in
them):**

| site | base | after | Δ |
|---|---|---|---|
| `BG_Init` | 176 | 188 | **+12** (the three tracker stores) |
| `Section_RedrawPlanes` | 480 | 498 | **+18** (the region resolve replacing the section walk, plus three tracker stores) |
| `OJZ_Act1_Sections` | 234 | 198 | **−36** (9 × 26 → 9 × 22) |
| code + data, 68000 image | | | **−6** |

**And `EndOfRom` is at `$BDA02` in BOTH listings** (demo debug: `$1121A` in both). The 68000
image is exactly the same length. The address shifts say where each piece went:

| from | shift |
|---|---|
| `Section_UpdateColumns` `$00605A` | **+18** |
| `BgAnim_Init` `$0082CA` | **+30** (cumulative) |
| `OJZ_Act1_Regions` `$018098` | **−36** — so the +30 was absorbed by alignment padding at a fixed bank base between those two points, the same mechanism steps 1 and 2 both measured |

and the −36 is absorbed in turn somewhere past `$018098`, since `EndOfRom` does not move.

**So the entire file growth is the deb2 symbol appendix**: 820477 − `$BDA02` = 43771 appendix
bytes before, 43826 after, **+55**; demo debug 33436 → 33492, **+56**. Four new RAM symbol
names (`BG_Plane_Layout`, `BG_Plane_Top`, `BG_Wipe_Cursor`, `BG_Wipe_Dir`) cost that, in every
shape including `demo`, which has no `Sec` table, no act and no caller for either blit — its
+56 is appendix and nothing else, which is the cleanest proof of the decomposition.

**Read the two figures in the right direction.** "ROM −36" as an estimate of the TABLE was
exactly right. As an estimate of the ROM it was wrong by construction, because a fixed bank base
absorbs sub-alignment changes and the symbol appendix ships in both canonical shapes
(crash-report ruling 2026-08-04). A parcel that adds RAM symbols grows the release ROM whatever
it does to the code.

**Why the ROMs differ in 389,506 bytes for a net-zero image:** the 8 new RAM bytes sit before
`Raster_Program`, so **212 RAM symbols shift by +8** — measured, and +8 is the only shift value
in the whole RAM map — and every `abs.w` reference to them re-encodes. Plus the three shifted
ROM runs above. Nothing moved that was not supposed to.

### 5. `sizeof(Sec)` and the two `mul_const` sites, for the sigil lane

**`sizeof(Sec)` = 22** at this parcel, 26 at the base. Read from the declaration
(`engine/structs.emp`, six fields: three `*u8` + `*u8` + `*u8` + `u16`) and **confirmed against
the listing** by the emitted table: `OJZ_Act1_Sections` spans 198 bytes for 9 rows = 22.

**Both `mul_const.w #sizeof(Sec)` sites changed their ENCODING and neither changed SIZE.** The
multiply did **not** disappear — 22 is not a power of two, so it is still a shift/add chain, now
by a constant outside sigil's oracle multiplier set. That is the hazard direction, not the safe
one.

| site | address (identical in both) | base ×26 | after ×22 |
|---|---|---|---|
| `Section_GetSecPtrXY` | `$5E40`, span 58 in both | `3801 d241 d244 e549 d244 d241` | `3801 e549 d244 d241 d244 d241` |
| `TileCache_DecompressBlock` | `$4B4A`, span 314 in both | `3803 d643 d644 e54b d644 d643` | `3803 e54b d644 d643 d644 d643` |

Both chains are 6 words / 12 bytes. ×26 is `x → 2x → 3x → 12x → 13x → 26x`; ×22 is
`x → 4x → 5x → 10x → 11x → 22x`. So the two sites sigil's multiplier work found uncovered are
these, they are still multiplies, and they are now multiplies by 22.

### 6. The replay hash is untouched, and the reason is structural rather than careful

§4.6 warns that a pointer folded raw silently re-poisons every recorded fixture.
`BG_Plane_Layout` is a pointer. **Nothing was added to `Replay_Hash`**, and nothing could have
been added by accident: the hashed set is a NAMED enumeration — the `.hash_table` `(addr, len)`
rows plus the word tail — so a new RAM cell joins it only if somebody writes its name there.
What placement CAN break is a named span's contiguity (`Camera_X, 2` folds `Camera_X` and
`Camera_Y` as one long; `Section_Top_Row_Written, 1` folds Top+Bottom), so the eight bytes went
after `Region_Current`, which no hashed row touches — and the +8 shift measured above starts at
`Raster_Program`, past every hashed cell's span except through the normalisations the fold
already performs (the free-stack cursors and `interact` are folded as offsets from their bases
precisely so an address move cannot change the hash).

**`BG_Plane_Top` and the wipe cells MAY be folded and were not**, because at this pin they are
always 0: folding a constant is coverage that cannot fail. They become worth folding at step 5
and step 6, when they vary. `BG_Plane_Layout` stays out permanently, or goes in normalised as a
row index into `Act.act_regions` — never the address.

**What I could NOT do: run a fixture.** `tools/test_replay_fixture.py` is structural only and
says so in its own header — *"This does NOT run the replay net. Running it needs the emulator
and a human"* — and the net has no automated runner at all. It passes (both fixtures, in the
2755-test lane). **That is not the check §4.6 asks for**, and I am not reporting it as one.
TAGGED below.

### 7. The tracker RAM is outside `Parallax_State`, and that is load-bearing

`Parallax_Init`'s `PARALLAX_STATE_LONGS` zero loop runs AFTER the plane blit on the boot ladder
(854 then 894). A tracker cell inside that span would be seeded by the blit and erased a few
calls later. It sits with `Region_Cur_*` and `Parallax_Roles_Swapped`, which are out there for
the same family of reason.

The cursor and the direction byte clear as one `clr.w BG_Wipe_Cursor` at both writers, pinned by
an `extern()` adjacency `ensure` at the foot of `engine/level/bg.emp` — a field inserted between
them would not fail to build, it would leave `BG_Wipe_Dir` holding a stale byte that nothing
reads until step 6 arms a sweep.

### 8. `Draw_BG_TileRow` still has no caller, and step 3 is not the step that gives it one

§4.5 is about the two SYNCHRONOUS blits: direct VDP poke storms, IRQ-masked, display off or
mid-recovery. `Draw_BG_TileRow` appends to `Plane_Buffer`, which `VInt_DrawLevel` drains at
VBlank. Using it from either blit is a category error, and there is a number that settles it:
`PLANE_BUFFER_SIZE` is **1536 bytes** and a row entry is `4 + PLANE_H_CELLS*2` = **132**, so the
buffer holds **11 rows**, against the 64 a prime needs (8448 bytes). The callers are the tracker
(step 5) and the wipe (step 6), exactly as step 2's note said.

## Guard and lane totals

| lane | base | after |
|---|---|---|
| `pytest tools -m "not needs_build"` | 2750 passed, 2 skipped, 16 deselected, 143 subtests | **2753 passed, 2 skipped, 16 deselected, 143 subtests, exit 0** |
| `emp_expect_fail` | OK — 55/55 (53 comptime + 2 link) | **OK — 56/56 (54 comptime + 2 link)** |
| sigil warnings, all four shapes | — | **exactly +1 `module.unreachable`** in every shape, which is the new poison module. Every other category identical: s4 166→167, s4.debug 153→154, demo 188→189, demo.debug 184→185 |

The pre-build lane found one real defect on the way: a live citation of `engine/structs.emp:104`
in `ART_PIPELINE_CONTRACT.md` that my own `structs.emp` edit pushed onto a bare delimiter.
Re-cited by name, which is what that gate's message prescribes — the same failure step 2 hit,
from the same cause.

Both `sizeof` ensures were **proven red** by widening one field of each record and moving the
`(size:)` declaration to match, so the declaration check PASSED and the `ensure` was the only
thing left to fail: `[Error] engine/structs.emp: sizeof(Region) is 24, and the record is 22
bytes`, and `sizeof(Sec) is 24, not 22` in an isolated second run. They cost **zero ROM bytes**
— the debug ROM was byte-identical (`crc=9f3d8328 len=846912`) across adding them.

## Three documents were already wrong before this parcel touched them

All three are RECORD LAYOUTS, and this repo has no gate that looks at one. That sentence was
already written in `ART_PIPELINE_CONTRACT.md`'s own ⚠, about itself, and was then proven right
by a second independent drift.

* **`docs/LEVEL_EDITOR_SPEC.md`** was THREE deletions behind: its `Sec` table still listed
  `sec_parallax_config` and `sec_effects`, which left `Sec` on **2026-09-13**, so every offset
  from `$0C` down was wrong *before* step 3 moved them again. Its `ojz_sec()` example carried
  two arguments the constructor does not take. An editor writing section rows from that table
  wrote garbage. Now the real 22-byte record, with both deletion events named and a line telling
  an editor to read `engine/structs.emp` rather than the table.
* **`docs/ART_PIPELINE_CONTRACT_ADDENDUM.md`** named "two consumers" of the field, one of which
  (`Draw_BG_TileColumn`) was deleted in step 2, at a line number that had moved. The count of two
  was right by accident: step 2 removed one consumer and added another.
* **`docs/ART_PIPELINE_CONTRACT.md`** needed the same ⚠ a second time, for the same reason.

## GATE BG-NT-IDENTICAL — TAGGED, and it can pass for the wrong reason

**Claim to test:** the Plane B nametable in VRAM is byte-identical before and after this parcel,
after boot and again after one warp.

| | |
|---|---|
| shape | `s4.debug.bin` |
| BEFORE | the coordinator's frozen `/home/volence/sonic_hacks/.aeon-bgnt-baseline/before-s4.debug.bin` |
| AFTER | this parcel's `s4.debug.bin`, 846912 B, md5 `63980e7ef62c80ce7928b1b13da3629c` |
| addresses | `$E000`..`$FFFF`, 8192 bytes |
| third leg | AFTER must also equal `games/sonic4/data/generated/ojz/act1/zone_bg.bin` byte for byte |

**I expect all legs EQUAL, and the derivation is short:** every region row of act 1 — ten in
release, eleven in DEBUG (`OJZ_E2_SNAP_ROWS` adds one) — omits `bg_layout:`, so `rg_bg_layout`
is 0 on every row, so `Section_RedrawPlanes` takes `.plb_use_act_layout` and blits
`Act.act_bg_layout` — the identical pointer the `Sec.sec_bg_layout == 0` fallback reached
before. The blit itself is byte-identical code. Even the degenerate case agrees: if
`Region_Resolve` returned 0 the routine takes the *same* fallback branch.

⚠ **AND THAT LAST SENTENCE IS THE PROBLEM WITH THIS GATE, SO I AM NAMING IT RATHER THAN
COLLECTING THE GREEN.** A PASS is consistent with the region path never running at all —
`Region_Resolve` returning 0 on every call, or the new code being skipped entirely — because
every path ends at the same blob. BG-NT-IDENTICAL cannot distinguish "the region seam works"
from "the act fallback did all the work", and neither can any static reading, and neither can
`BG_Plane_Layout`, which both branches set to the same value.

**The discriminator is one breakpoint, and it is cheap:** stop at the `jbsr Region_Resolve`
inside `Section_RedrawPlanes` (the call immediately after the Plane A `.pla_fill` loop), step
over it, and read `a0`. It must be an address **inside `OJZ_Act1_Regions`**, not 0. If you can
read `d2`/`d3` on the way in, they should be the camera centre. That single observation is the
difference between "the picture did not change" and "the picture did not change *and* the new
code is what produced it".

## Also TAGGED for the foreground

* **The warp leg matters MORE now than it did in step 2.** Step 3 changes the recovery blit,
  which is exactly the path a warp takes. Step 2's note records that the warp leg was **never
  run** — the `Warp_Req_Flag` byte stayed `$01`, unconsumed — and warns that a warp that never
  happened and a warp that changed nothing produce identical bytes. **Assert `Warp_Req_Flag`
  cleared before believing any nametable read.**
* **`tools/test_replay_fixture.py` passing is NOT the §4.6 check.** The replay net has no
  automated runner; a real fixture replay needs the emulator and a human. The structural
  argument for why nothing can have been poisoned is in finding 6; it is an argument, not a run.
* **`CONTRACTS=0` with a deleted-field reference** was not measured (finding 3). One canonical
  build answers it.

## Open / not done here

* **BG-NT-IDENTICAL is UNMEASURED.** Nothing here claims the picture is unchanged on hardware.
* **`rg_bg_span` still has no reader.** The clamp that reads it is step 4. `ojz_region()`'s span
  `ensure`s from step 1 are unchanged and still hold.
* **No window arithmetic** (finding 2), **no caller for `Draw_BG_TileRow`** (finding 8), **no
  wipe** — all step boundaries, all booked or named.
* **PAIRED HALF NOT DONE.** This parcel moves ROM bytes in all four shapes, so sigil's goldens
  no longer match. Nothing here touches sigil and sigil's suite was not run.
* **`SpawnDesc`'s unenforced `(size: 4)`** is real and is booked, not fixed — a different engine
  file is not this parcel's subject. Its booking carries sigil's measurement and the trap that
  `engine/effects/preset.emp:114`'s prescribed `[module.unreachable]` census cannot find it from
  either end. **That note in `preset.emp` was not edited by this parcel.**
* **Not cross-seam by NAME.** `sec_bg_layout` appeared in `.emp`, `tools/` and docs only —
  neither `map.toml`, nor either `game_root.asm`, nor `debugger.asm` named it. Re-derived
  firsthand rather than taken from the brief; my sweep agreed with the coordinator's. The byte
  change is the sigil pairing obligation, not a name.
