# S2-COMPRESSED-ACT parcel 6 — the first bootable clip act

**Date:** 2026-09-17 · **Branch:** `parcel/s2-first-clip-act` (worktree `aeon-wt-s2boot`, base
`origin/master` `1d6117ec`)
**Design row:** §10 row 6 — *"★ FIRST THING ON SCREEN: a one-clip act. One 2-section Emerald
Hill clip as a whole act: art + collision + its palette, bootable."*
**Booking:** `docs/DEFERRED_WORK.md`, section `S2-COMPRESSED-ACT`.

Parcel 5 named exactly what this inherits: *"What is still missing is the BLOCK STREAM.
Nothing here exercises `ojz_block_gen` or S4LZ. `sec{N}_blocks.bin` is where the collision
planes and the art meet in the format the ROM reads, and it is the gap between this parcel's
output and a bootable act — with the `project.json` entry and the `act_descriptor.emp` with
matching GRID_W/GRID_H parcel 3 named."* All three exist now, and the act builds.

**One command:**

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
python3 tools/s2_zone_convert.py convert s2disasm@EHZ     # once, ~0.2 s
S2CLIP=s2_ehz_boot ./build.sh                             # -> s4.s2clip.bin
```

---

## 0. What happened, in four lines

* **`S2CLIP=s2_ehz_boot ./build.sh` exits 0** and writes `s4.s2clip.bin`, **821,211 bytes**,
  md5 `7f40876af03b35f03f0ef9d6bd527743`, DIGEST-ROM crc `76106cb9`. Every gate in `build.sh`
  runs against the clip tree and passes.
* **No canonical ROM byte moved.** Re-derived at landing, not copied: `s4.bin` 821,479 B
  `ae62156a66c9c3f13e93940e938c340e`, `s4.debug.bin` 848,075 B
  `b15ef259523f67ac963ef0cf4df003dc`, `demo.debug.bin` 104,707 B
  `f740c22498f6ad132ac9f8bd978c9350` — the three master booked.
* **The ground is where Emerald Hill's ground is**, by the engine's own lookup arithmetic
  re-implemented over the EMITTED ROM bytes, with a second witness from the donor game itself.
* **The palette is BLOCKED** on a ruling and is not worked around. The default shape shows
  Emerald Hill's geometry and art in Oracle Jungle's colours, loudly labelled. §5 below.

---

## 1. The rectangle, and why

`games/sonic4/data/clips/s2_ehz_boot/clips.json` (tracked):

```jsonc
"act":  { "grid_w": 3, "grid_h": 3 },
"clips": [{ "id": "ehz_opening", "donor": "s2disasm", "zone": "EHZ",
            "src_rect": { "x": 0, "y": 0, "w": 4096, "h": 1024 },
            "dst_rect": { "x": 0, "y": 0, "w": 4096, "h": 1024 } }]
```

**The opening stretch of Emerald Hill Zone act 1.** Five reasons, each of them a constraint
rather than a taste:

1. **Two sections wide**, which is what row 6 asks for. Its height is 1024 and not 2048
   because EHZ's whole crop is 128 tiles tall (`zone.json` `extent.crop_tiles` = `[0, 1372,
   0, 128]`) and R9 refuses a rect past it. A "2-section clip" of Emerald Hill cannot be two
   sections TALL; the zone is half a section high.
2. **`src` == `dst`, so the paste SHIFT is (0, 0).** R12 is satisfied by construction, and a
   collision misalignment — which moves ground 8 px and which no screenshot shows — cannot
   hide behind a nonzero shift on the first act anyone looks at.
3. **`dst` (0, 0) puts painted geometry in SECTION 0.** `games/sonic4/map.toml`'s order array
   names `OJZ_Sec0_Blocks` and `OJZ_Sec0_LocalMap` as section HEAD labels; an all-air section
   0 content-dedups into an `equ` alias of whichever section owns the air blob, and the
   placement rows would name a label that is not a section head.
4. **It is the most recognisable ground in Sonic 2** — flat ground under the whole spawn
   column, the first hill, the palm trees. The clearest possible answer to "is this our engine
   drawing Sonic 2".
5. **EHZ has ZERO cells on CRAM line 0** (`zone.json` `counts.cram_line0_painted_cells` = 0,
   verified rather than assumed — parcel 2 measured 698 in CPZ and 104 in WFZ). The palette
   defect parcel 2 found cannot appear here.

The owner picks the real rectangles later in the editor; this one exists to be looked at.

---

## 2. How a second act coexists with the shipped one

**It is a THROWAWAY re-bake of the ONE act slot**, in exactly the shape this repo already has
for this problem: `build.sh`'s `STRESS_ART`. An off-canonical DEV shape — unfrozen, no golden,
a distinct artifact — that re-bakes the act slot IN PLACE under an EXIT trap restoring the
committed tree from git.

**The canonical shapes are byte-identical BY CONSTRUCTION, not by promise.** They read the
committed tree; this writes over it; the trap puts it back; and no `.emp`, no `map.toml` row
and no engine constant is touched. `git status games/sonic4/data` is clean after the build.

**Why not a second act entry.** sigil places the generated `.emp` modules (`ojz_act_pool`,
`sec_block_blobs`, `sec_local_maps`, …) by a FIXED registry path, and `map.toml`'s order array
names their head labels. A second act's modules are not linked without a sigil registry
change, a `map.toml` change and a second `act_descriptor.emp` — all of which land bytes in the
canonical ROM, which is the thing this parcel may not do.

**Why not a separate game.** `games/demo` is the proof the engine is game-agnostic and has ZERO
Sonic code. "Sonic stands on its ground" needs the player, the character art, the mappings and
the DPLC: a fork of the whole `games/sonic4` game layer. That duplication is what CLAUDE.md's
"clean, not bolted-on" refuses.

**What the clip act inherits from the shipped act, stated rather than hidden** — these are the
parts of the picture that are NOT Emerald Hill:

| inherited | why | whose problem |
|---|---|---|
| the BACKGROUND | `ojz_strip_gen` Pass 6b builds Plane B from the sonic_hack donor unconditionally ("BG layout always uses sonic_hack data") | a per-clip background is the corridor work, §9.1 / row 7+; a second act's BG animation has nowhere to live (risk 5) |
| the OBJECTS and RINGS | Pass 8 (`ojz_entity_gen`) reads the shipped act's editor entities, at their OJZ world positions | objects are out of scope for the whole first cut (owner's scope) |
| the REGION TABLE and EFFECTS PRESETS | both live in the hand-written `act_descriptor.emp`, untouched | section 0's preset installs a VSRAM raster that bands Plane B below screen line 112; it still fires, over Emerald Hill |

---

## 3. ONE clip, and why that is a refusal

An editor nametable word's tile index is 11 bits into ONE act-wide tileset.
`ojz_strip_gen.generate()` reads exactly one (`project.json` `zones[0].tileset`) and hands
`place_pool` a uniform zone grid. **A one-clip act has exactly one donor zone and is therefore
an ORDINARY aeon act** — no per-cell tileset key is needed and nothing is faked. That is the
whole reason row 6 is reachable without the ROM-side stitching work.

A two-clip act is not, and `clip_rom_bake` refuses it by name (**R20**) rather than baking the
second clip's indices against the first clip's art: a tree every gate accepts and half a
picture that is the wrong zone. **Teaching the ROM path a per-cell key is row 7's work.**

---

## 4. What was built

| file | what |
|---|---|
| `tools/clip_rom_bake.py` | the driver: `bake` (clip → the generated tree the ROM links) and `ground` (the static half of row 6's check) |
| `tools/elect_pool_pages.py` | the act-art-pool ZX0/raw election, lifted out of `regenerate-level.sh`'s thirty lines of bash so BOTH acts elect through one emitter |
| `games/sonic4/data/clips/s2_ehz_boot/clips.json` | the fixture, tracked |
| `tools/test_clip_rom_bake.py` | 18 rows, donor-free and build-free |
| `build.sh` | the `S2CLIP` shape (+ `S2CLIP_PALETTE`) |

**What the bake runs**, all of it the shipped generators pointed at a second act rather than a
second copy of them:

1. `clip_act_bake.bake` — rows 3 + 5's composer. Writes the act's editor-shaped tree and runs
   R1-R12 / C1-C3 including the 255-entry attr cap.
2. a staged `project.json` beside that tree, naming the donor zone's `tileset.bin` and the act
   grid, `dataPath: "."`.
3. `ojz_strip_gen.generate()`, redirected through a new `configure()`, with the **Sonic 2**
   collision bank (row 4's `base_s2`) and the donor zone's `palette.bin`.
4. `tools/inject_editor_bg.py`, exactly as `regenerate-level.sh` runs it.
5. `elect_pool_pages.elect` — per-page form election + `ojz_act_pool.emp`.
6. `ojz_block_gen.generate_all()` — **THE BLOCK STREAM**.

**The first bake's numbers:**

```
286 pool tiles in 5 pages · 66 of 255 collision attr entries
sec0 12,220 B (K=1 dict, 128/256 non-empty blocks)
sec1 16,860 B (K=3 dict, 128/256 non-empty blocks)
sec2-8 air, content-deduped to one 1,024 B blob (6,144 ROM bytes saved)
fg_page_order check: 5 pages, pins [0], worst window 5 of 12 frames,
                     0 of 257,367 windows over budget
art_rom_report:      5 pages, raw 8.9 KB -> stored 4.8 KB (54.2%), soft 24 / hard 64 KB: ok
```

Two things worth reading in those numbers.

**THE DESIGN'S OWN MEASUREMENT REPRODUCES THE ROM BAKE EXACTLY, through a completely
different path.** §3.2's sweep of every section-aligned 2-section clip of Emerald Hill
reports `min=286 canonical tiles, min=5 pages`, and names the position:

```
$ python3 docs/research/s2-compressed-act/s2_clip_budget.py clipsweep EHZ --secw 2 --sech 1
# canonical tiles per clip: min=286 p50=470 max=480 | pages: min=5 p50=8 max=8
{"col0": 0, "row0": 0, "px": [0, 0], "src": 392, "canonical": 286, "pages": 5, ...}
```

**286 and 5, the two numbers the bake printed.** The two sides share nothing but the donor
bytes: the sweep reads the donor's own layout/chunk/block tables directly, while the bake
goes through a converted editor tree, `clips.json`, `clip_act_bake`'s composer and
`ojz_strip_gen.generate()`. They agree because the rectangle is the same rectangle, and they
could have disagreed for a dozen reasons.

**And it says something about the rectangle rather than only about the pipeline.** §3.2's
headline is "taking a third of Emerald Hill costs the same 480 tiles as taking all of it" —
true of the MAXIMUM and of the median (470). The MINIMUM, 286, is the zone's opening, because
a Sonic zone's opening stretch is the one part that has not yet introduced the rest of the
tileset. That is not a reason to pick openings for the showcase (the owner picks for the
picture, and §3.2's conclusion that zone COUNT sets the art cost is untouched), but it is why
this particular first act is cheap: 5 pages of 12, not 8.

**The collision is 66 of Emerald Hill's whole-zone 105** (parcel 5's per-zone figure), so an
opening stretch really is cheaper than a zone on the axis that actually binds — which is the
shape §3.5's clip-harder option needs.

---

## 5. BLOCKED: the palette

`--palette clip` is the right picture and **does not build**.

`games/sonic4/data/effects/ojz_effects.emp` carries **eight top-level comptime `ensure`s pinned
to statistics of the SHIPPED act's palette**: the night grade's lit-colour count (42), its
retention ceiling (76%), three blue-share permille figures (**337 / 341 / 406** — CORRECTED
2026-09-18; this sentence read "313 / 310 / 377", which are EHZ's MEASURED values, not the pinned
ones. Verified at `ojz_effects.emp:2268, 2270, 2272`), the distinct
colour count (39), the merge budget (36), and the showcase palette's agreement with
`OJZ_Palette` over CRAM lines 1-2.

**They are RIGHT and they fire correctly.** Their job is to catch the act art changing under a
hand-derived grade, and a clip act changes the act art: Emerald Hill's palette has **46** lit
colours where Oracle Jungle has 42, 37 distinct where OJZ has 39, and a blue share of **313**
permille against the pinned **337** (the swap above, same correction).

**AND THE DECISIVE NUMBER WAS MISSING FROM THIS LIST** (added 2026-09-18, from the hub's
adjudicating agent, which re-implemented all seven comptime functions and reproduced every OJZ pin
exactly as its positive control before running them on the donor's verbatim `EHZ.bin`; that agent's
measurement, not this lane's): **EHZ's night retention ceiling is 91% against the pinned 76%.**
That is precisely the *"straggler that will read as full daylight in the night region"* the pin's
own message names — and OJZ act 1's night region (x 3400..4799) sits INSIDE this clip's 4096-wide
rectangle. So re-pinning to EHZ's measurements would have banked a known-bad night picture as an
expectation. The list above named the figures that merely differ and omitted the one that means
something.

**"Every one of their messages says re-derive" is also too strong:** `:2257` says "Re-derive, do
not re-pin" and `:2268` says "re-derive the two rows below rather than nudging them"; `:2270`,
`:2272` and `:2279` carry no such language, and the eighth (`:2378`) asks for a generator re-run,
not a hand derivation. The distinction matters: "re-derive" forbids nudging a literal until green.
It does not forbid a person measuring a SECOND palette and pinning per palette.

**Three options, all of them the owner's:**

- **(a) scope the pins to the shipped act** — a top-level comptime conditional around a block
  of `ensure`s. **NO SUCH PATTERN EXISTS IN THIS CODEBASE**: the `if DEBUG == 1` sites are
  expressions inside initializers, not statement blocks around guards. Byte-neutral if it
  works, since an `ensure` emits nothing. Inventing it inside the shipped effects library is
  not a clip parcel's call.
- **(b) derive the pins per act** instead of pinning them. Their own messages forbid it.
- **(c) give a clip act its own effects library.** That is the per-region palette work §9.1
  describes — row 7 and beyond.

**What ships instead:** `S2CLIP_PALETTE=shipped` (the default). Emerald Hill's geometry and art
in Oracle Jungle's colours, announced in a loud banner at the bake and recorded in the bake's
own JSON. A wrong picture that says it is wrong, rather than a green one that lies. **The
geometry claim does not depend on the palette at all.**

---

## 6. The static evidence — as close as a static check reaches

Row 6's check as written is *"the clip renders and Sonic stands on its ground"*, which is a
RUNTIME claim. **No emulator was used anywhere in this parcel.** This is what a static check
can say, and the runtime confirmation is tagged in §8.

### 6.1 The act is what the converter emitted — `verify_level_bin`, all ten lanes

```
verify_level_bin: editor bake fidelity OK (9 sections, 589,824 nametable words)
verify_level_bin: editor collision fidelity OK (9 sections, 589,824 cells,
                                                7,840 authored non-air)
verify_level_bin: OK [act-pool+content+sidecar / local-maps+table / block-blobs /
                      block-decode / bininclude-targets / collision-interned /
                      editor-bake / editor-collision / section-set / orphans]
```

That is the whole claim "its tiles resolve, and its collision bytes are the ones the converter
emitted", measured over every cell of the act rather than sampled. **It needed two
parameterisations, because both fidelity lanes were silently act-specific:**

* `--project PATH` — the act's project file. `dataPath` now resolves against the PROJECT FILE
  rather than the repo root (identical for the shipped `project.json`, which sits at the root).
* `--bank DIR` — the base shape bank the editor cell words index. A Sonic 2 clip is indexed
  against `collision/base_s2`, and a shape index means a DIFFERENT shape in the S&K bank, so
  the wrong bank reports every authored cell as a mismatch.

Both default to today's values; a canonical run is unchanged and was re-verified OK. **Without
them the shape would have had to SKIP those two lanes, and a lane a shape never runs is a lane
that shape does not have.**

### 6.2 The ground is under the spawn — the engine's own arithmetic

`python3 tools/clip_rom_bake.py ground games/sonic4/data/clips/s2_ehz_boot/clips.json`:

```
ground: spawn re-derived from the engine = world (256, 256) px
ground: SOLID at world y=656 (cell row 41), attr byte 8, solidity $03,
        height 1 px in column 0, angle $F8; surface at world y=671,
        415 px below the spawn
```

Every step is the engine's, not a convenient restatement of it:

* **the spawn** is `Camera_Init`'s seed (`(start_sec << SECTION_SIZE_SHIFT) + start_local −
  half a screen`, CLAMPED) plus the boot state's `Camera + half a screen` — computed from the
  descriptor's own `start_*` fields and the engine's `CAM_*` constants, never typed. The halves
  cancel except where the clamp bites, which is why it is computed.
* **the cell** is picked the way `probe_core` picks it: the 8-px column from the world x, the
  16-px collision row from the tile row by one `lsr.w #1`
  (`engine/level/collision_lookup.emp:65`). A paste shifted 8 or 16 px reads a different byte.
* **the solidity CLASS gate** (`and.b d6, d0` against `SolidityTable`, `SOLID_TOP` for a floor
  sensor) is applied. Parcel 4's own check omitted it and answered solid for 158,442 probes
  Sonic 2 answers air.
* **the height byte** comes from the EMITTED `heightmaps.bin` at `attr × 16 + (x & $F)`,
  indexed by the attr byte the EMITTED `sec{N}_strips_a.bin` carries. Everything between the
  donor and the ROM is in the loop; nothing is read from the donor or from the plane files.
* **a negative height** is a hanging run (`bmi .cl_hanging`) and is reported, not counted as
  the landing.

### 6.3 THE SECOND WITNESS — Sonic 2's own start position

"Something solid is under the spawn" is a weak claim: air is the only thing it rules out, and a
clip pasted 16 px wrong still has ground under it. So the check asks a question with a number
in it.

Sonic 2 ships a start position per act. `s2disasm/startpos/EHZ_1.bin` is `$0060 $028F` = **(96,
655)**. At that same point in our act, the ROM's collision says the floor surface is at
**y = 676**; the player's feet, at `PLAYER_Y_RADIUS` 19 below 655, are at **y = 674**.

**2 pixels.** The window is DERIVED, not fitted: at or below the feet (above would spawn the
player inside the ground) and within one 16-px collision cell (further up is a fall, not a
stand). **A paste shifted by R12's 16-px block quantum, or by the 8 px that moves collision and
not art, lands outside it.**

The floor across the whole clip, for scale — a continuous surface, flat and sloped:

| world x | 96 | 128 | 256 | 512 | 1024 | 2048 | 3000 | 4000 |
|---|---|---|---|---|---|---|---|---|
| surface y | 676 | 672 | 671 | 644 | 576 | 608 | 672 | 532 |
| angle | $FF | $FF | $F8 | $FF | $08 | $FF | $FF | $08 |

---

## 7. What the existing gates caught — five, all five right

Recorded because the interesting half of a parcel is what refused it.

1. **`inject_editor_bg.py` was never run by the clip bake**, so `OJZ_Act1_BG_Layout` was emitted
   at 4,096 B against a declared 8,192 and the link died with `[emit.size-mismatch]`. The clip
   act keeps the shipped background, so it must keep the whole shipped BG path.
2. **`bganim_room` had no ruled ceiling for the new shape** and said so (COULD NOT RUN, with
   the fix in its own message). Two rows added, DERIVED and not copied: a clip act re-bakes only
   the FOREGROUND half and keeps the shipped BG authoring byte for byte, so the ruled number
   carries; the ROOM does not, which is why they are keyed by their own listings.
3. **`test_bg_emit` derived the off-canonical shapes with its own
   `ROM_NAME="(s4\.stress[a-z]*)"` regex and a `len == 2` tripwire** — a rule keyed to the two
   shapes that existed when it was written. The `S2CLIP` listings are off-canonical, are not
   spelled `stress`, and were invisible to it, so the population check had silently stopped
   covering the population. It asks `tools/gate_cut_shape.py` now, which already reads
   `build.sh` for exactly that set. One reader, one source.
4. **`test_cli_dispatch_refuses`**: `clip_rom_bake.py` and `verify_level_bin.py` joined the
   argv-dispatch population unrostered (21 → 23). `clip_rom_bake` is `_FIXED` with **NO**
   subprocess row — it OVERWRITES tracked build inputs, and that file's own rule is that on a
   regression such a row's failure IS the write.
5. **`test_page_size_constant` and `test_baker_refusals` stubbed the art-pool election**, which
   had just moved out of the bash into a real tool. Both harnesses drive the script end to end,
   so both get the REAL `elect_pool_pages.py`; stubbing it would have made
   `test_page_size_constant`'s three rows test nothing at all.

---

## 8. ★ THE RUNTIME CHECK — TAGGED FOR THE FOREGROUND

**No emulator was used in this parcel and none may be.** This is the confirmation somebody has
to do by hand, written so it can be executed and so it can FAIL.

**Boot:** `s4.s2clip.bin` (built by `S2CLIP=s2_ehz_boot ./build.sh`; add `DEBUG=1` for the
debugger twin, `s4.s2clip.debug.bin`).

**⚠ On the DEBUG shape, PRESS B FIRST.** The boot state starts the player in debug free flight,
so the harness's default state IS the condition under test and physics never runs. On the plain
shape there is nothing to press.

**What to look for, in order:**

1. **Emerald Hill's opening, on the ground.** Green chequered terrain with the flat opening
   stretch and the first rise, palm trunks, the signature EHZ ground edge. **In Oracle Jungle's
   COLOURS** — the palette is blocked (§5), so expect OJZ's greens/browns over EHZ's shapes,
   and expect the background to be Oracle Jungle's, because the clip act keeps it (§2).
2. **Sonic falls about 415 px and LANDS**, roughly half a second, and then stands still. He
   spawns at world (256, 256) and the floor's surface is at y = 671.
3. ~~**He runs right along a continuous floor for two sections** (4,096 px).~~ **FALSE, AND
   THIS SENTENCE IS WHAT TURNED A LEVEL FEATURE INTO A BUG REPORT** (corrected by parcel 7,
   2026-09-17). The floor is continuous in the sense that every one of the 512 columns has a
   landing surface somewhere — that is measured and it holds — but it is NOT a surface you
   can run along. **Emerald Hill act 1 has a jump at x 1,344..1,535**: its own layout puts
   the all-empty chunk `$0C` at chunk column 11 and empties chunk `$0B`'s right half, the
   ground drops from y 644 to y 872, and Sonic 2 puts a row of five rings over it at
   y 568, x 1,392..1,488 (24 px apart — `RingsMgr_NextRingInRow`'s `addi.w #$18,d2`). A clip act inherits OJZ's rings, so that cue is not on screen and the drop reads as
   the world ending. §6.3's table samples eight x values and steps straight over it. What to
   look for instead: **he runs right, and at x ≈ 1,344 the ground falls away into a pit with a
   floor 228 px down.** That is Emerald Hill, correctly converted.
4. **At x ≈ 4096 the world ends** — and parcel 7 found that this is the whole reported bug,
   not a footnote. Sections 2/5/8 are air (0 of 256 non-empty blocks, content-deduped to one
   1,024 B blob), so at x = 4,096 the art and BOTH collision planes stop dead, top to bottom,
   at a fixed world x. The camera's `EDGE_CLAMP` clamps the CAMERA to the act, not the player
   to the clip, so a player who keeps running right leaves the painted world and falls the
   act's full 6,144 px with nothing to land on. It IS correct for a one-clip act; what was
   wrong was that nothing but this sentence said so. It is now DECLARED in the manifest
   (`unpainted_remainder`) and CHECKED by `tools/clip_reachability.py` on every S2CLIP build.

**What would FALSIFY it, and what each failure would mean:**

| symptom | what it means |
|---|---|
| Sonic falls through the ground and keeps falling | ⚠ **PARCEL 7 RESOLVED THIS ONE AND IT WAS NOT THE COLLISION BYTES.** They reach the runtime intact: every block decodes to its strips, and all 512 painted columns carry a plane-A landing surface. It is the act's unpainted remainder past x = 4,096. If it recurs INSIDE x < 4,096, `clip_reachability.py` now fails the build before the ROM exists |
| Sonic stands but the ground is visibly 8 or 16 px out of line with the art he stands on | the paste shift (R12) — the failure §6.3's second witness is aimed at, and the one no screenshot of a STILL frame shows |
| the terrain is Oracle Jungle's, not Emerald Hill's | the clip's tile indices were resolved against the wrong tileset |
| the terrain is Emerald Hill's but scrambled / wrong tiles in the right places | the dedupe or the page placement, i.e. the pool, not the layout |
| a black screen or a red fault screen | a boot failure, not a data failure; discriminate by display-off vs planes-drawing |
| the ground is right but Sonic sinks into slopes or catches on flat ground | the S2 collision bank's angles or the height profiles, i.e. row 4's bank, not row 6 |

**A screenshot of a still frame is not enough for item 3** — verify DURING motion, because a
scroll artifact does not appear at rest.

---

## 9. What row 7 (two clips + a corridor) inherits

* **The ROM path is open, for ONE clip.** `clip_rom_bake bake` produces the whole generated
  tree the ROM links, and `S2CLIP=<id> ./build.sh` builds it green. Row 7's first job is
  **R20**: two clips need the per-cell tileset key on the ROM path, which `clip_act_bake`
  already computes (`clip_manifest.cell_grids`) and `ojz_strip_gen.generate()` does not read —
  it hands `place_pool` a `zone_grid` of zeros and loads ONE tileset.
* **The act grid is 3 × 3 and fixed by the descriptor** (R21). Two clips plus a corridor wider
  than the 640 px camera window fit in one 6,144 px row with room to spare; the corridor's own
  art has to come from somewhere, and today it would come from the one tileset.
* **The palette blocker of §5 is row 7's on the critical path**, not a nicety: two clips means
  two palettes and a cross-fade, and neither can reach the screen while the night-grade pins
  describe the shipped act's palette. **It wants the owner's ruling before row 7 starts.**
* **`fg_page_order.check` now reads the clip act.** Parcel 3's restatement of the row-3 check is
  CLOSED rather than permanently accepted: a clip act is baked into the shipped act's slot, so
  `_known_acts` and `fg_working_set.Model` see the act they already know. It ran on the clip
  tree at 5 of 12 frames.
* **The `$18` tripwire is still armed** and still costs nothing: no showcase zone references it.
* **A clip act's own effects, regions and background do not exist.** All three are inherited
  from the shipped act (§2). Row 7's corridor needs at least the region rows.

---

## 10. Reproducing every number here

```bash
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob

python3 tools/s2_zone_convert.py convert s2disasm@EHZ          # §1's zone.json
python3 tools/clip_rom_bake.py bake  games/sonic4/data/clips/s2_ehz_boot/clips.json
python3 tools/verify_level_bin.py --project games/sonic4/data/clips/s2_ehz_boot/baked/project.json \
                                  --bank    games/sonic4/data/collision/base_s2   # §6.1
python3 tools/fg_page_order.py check                            # §4
python3 tools/art_rom_report.py .                               # §4
python3 tools/clip_rom_bake.py ground games/sonic4/data/clips/s2_ehz_boot/clips.json  # §6.2, §6.3
git checkout -- games/sonic4/data/generated games/sonic4/data/collision   # put the tree back
git clean -fdq -- games/sonic4/data/generated

S2CLIP=s2_ehz_boot ./build.sh                                   # §0 — the ROM
python3 -m pytest tools/test_clip_rom_bake.py -q                # the 18 gate rows
./tools/landing_build.sh                                        # the canonical three
```

`bake` refuses to start over a dirty generated tree (**R22**), so the `git checkout` line is
not optional between runs; `build.sh`'s `S2CLIP` shape owns that restore itself through an EXIT
trap.
