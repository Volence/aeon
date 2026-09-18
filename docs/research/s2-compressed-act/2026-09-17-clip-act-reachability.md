# The world ends at x = 4,096, and it is the act the clip does not paint

S2-COMPRESSED-ACT parcel 7, 2026-09-17. Branch `parcel/s2-clip-gap`.
Subject: `s4.s2clip.bin` md5 `7f40876af03b35f03f0ef9d6bd527743` — rebuilt here and the md5
reproduced, so this is the same artifact the owner booted, not a lookalike.

---

## 1. What was reported, and what was actually true

Two observations, both firsthand, both real:

* Running right, the player falls through and never stops, reaching y = 5,920 (the camera's
  own maximum) in an act that is 6,144 px tall.
* A **hard vertical line** in the drawing: terrain to the left of one column, pure background
  to the right of it, top of screen to bottom — **with the debug build in free flight, so
  player physics was entirely out of the picture.**

Three hypotheses were on the table: an inherited camera clamp, a truncated art pool, and a
mis-derived clip height. The answer is the first one, in mechanism, at a different place than
anyone was looking.

**Nothing in the pipeline is truncated. The level data is complete and faithful.** Measured on
the emitted bytes, over the whole clip rectangle:

| what | measured |
|---|---|
| columns of the 4,096 × 1,024 clip rect with no art | **0 of 512** |
| columns with no plane-A landing surface | **0 of 512** |
| local-map coverage | sec0 uses indices 0..252 of 253 entries; sec1 0..279 of 280. No index past either map |
| local-map targets | every entry points inside the 286-tile pool; none past it |
| block stream | `verify_level_bin.py`'s block-decode lane green: every block decodes to the block its strips define |
| donor fidelity | the converted tree matches s2disasm's own EHZ chunk grid, chunk for chunk |

## 2. The cause

A clip act is baked into the **shipped act's slot at the shipped act's grid**. `clip_rom_bake`'s
R21 (`check_act_grid_matches_engine`) forces the manifest to declare that grid, and it forces it
for a good reason: `GRID_W`/`GRID_H` are hand-written in `act_descriptor.emp` and shared with the
canonical ROM, so a clip act cannot declare its own without moving canonical bytes.

So `s2_ehz_boot` paints **4,096 × 1,024 px of a 6,144 × 6,144 px act.** Sections 2, 5 and 8 are
baked as air — 0 of 256 non-empty blocks each, content-deduped into one 1,024-byte blob. At
x = 4,096 the art and **both** collision planes stop dead:

```
ART, x 3968..4224 (16 px cells)     COLLISION, same range
  596 ++++++++........               596 =..=............
  612 ++++++++........               612 ====............
  628 ..++++++........               628 ..==............
  644 ....++++........               644 ....=...........
                ^ x = 4096                        ^ x = 4096
```

That is the hard vertical line: **a fixed world x, not a streaming artifact.** And it is
**one bound consumed twice** — the tile cache carries the nametable *and* both collision planes
in the same block, so a section that is all air is blank art and air collision at the same x, in
the same bytes. The two symptoms are not two causes that coincide; they are one boundary seen
from the renderer and from the sensors.

The player is not stopped at it. `edge_mode: EDGE_CLAMP` clamps the **camera** to the act, not
the player to the clip, so running right walks off the painted world into 2,048 px of void and
falls the act's full height with nothing to land on.

### What a clip act should OWN versus INHERIT

It should own its **act extent**. It cannot today, and the fix is not a wider rectangle:
Emerald Hill act 1 has its own bottomless pit at x 4,672..4,863, so a 3-section clip trades this
edge for a worse one. Owning the extent means a clip act with its own descriptor, which is row
7+ work. **What this parcel does instead is make the inheritance explicit and build-checked**
rather than implicit: the manifest declares `unpainted_remainder`, with the reason written next
to it, and the build refuses if the painted world ends anywhere but exactly there.

## 3. Two things the owner's evidence got right, and one it got wrong

**Right: the hypothesis.** "The clip act inherits the shipped act's descriptor, including its
act extent" is exactly the mechanism. The boundary is at x = 4,096, not at x ≈ 1,500.

**Right: the clip height.** `crop_tiles [0, 1372, 0, 128]` is correct and consistent. The
converter measured 217,600 pad cells outside the crop with **0 non-zero** — there is genuinely
nothing in EHZ outside 10,976 × 1,024 px. The design's "the whole zone is only 1024 tall" stands.

**Wrong: "the data DOES contain that ground" at x 1,400..1,528.** It does not, and the reading
that said so counted *non-zero donor words* as solid. A Sonic 2 chunk word packs the block index
in bits 0-9 and the solidity in bits 12-15; `0x00ff` is block 255 with **no solidity on either
path** — a non-collidable filler tile. Every word quoted in that range is `0x00ff` or `0x20ff`
(left/right/bottom only, not standable from above).

What is actually at x 1,344..1,535 is **a genuine Emerald Hill jump.** EHZ's own layout puts the
all-empty chunk `$0C` at chunk column 11 and empties chunk `$0B`'s right half; the ground drops
from y 644 to a floor at y 872; and **Sonic 2's ring layout puts a horizontal row of five rings over it** — layout entry
`x=1392, y=568, count=5`, and `RingsMgr_NextRingInRow` steps `addi.w #$18,d2`, so they sit at
x 1,392 / 1,416 / 1,440 / 1,464 / 1,488, spanning the pit 76 px above its lip. (Decode verified
against s2disasm's own expander, not assumed: `rol.w #4` + `andi.w #7` is count-1 in bits 12-14,
`andi.w #$FFF` is Y, `bmi` on the second word is a column. An earlier draft of this report called
it an *arc*; it is a level row, and the spacing is 24 px, not 16.) A clip act inherits OJZ's rings, so that cue is not on screen. The
parcel-6 report's runtime item 3 promised "a continuous floor for two sections", which is what
turned a level feature into a bug report; it is corrected in place.

## 4. Found on the way — the only thing inside the rectangle that CAN swallow a player

**Plane B has no landing surface at all in x 1,344..1,407** — 8 columns, bottomless.

It is harmless today and was invisible before today, for two independent reasons:

* Nothing writes the player's layer byte. `player_common.emp` clears it at init
  (`clr.b layer(a0)`) and the only writer is `Player_LoopCrossover`, which fires off the
  interned CrossoverTable — and this act's table marks **zero** attr bytes.
* **Every act that has ever run on this engine had plane B as a byte-for-byte copy of plane A.**
  `tools/ojz_block_gen.py`'s `test_extract_block` asserts it in terms: *"OJZ: plane B must be a
  copy of plane A"*. A Sonic 2 clip is the **first** content where the two planes differ, because
  Sonic 2's chunk words carry two independent solidity nibbles and the converter splits them.

So the clip act is also the first content on which a wrong `layer` byte is fatal rather than a
no-op. The gate prints these columns as INFORMATIONAL and **turns them red the moment one
crossover attr byte is marked** — which is a row in `tools/test_clip_reachability.py`, not a
promise.

## 5. The gate — `tools/clip_reachability.py`

Wired into `build.sh`'s S2CLIP shape as `gate strict`, immediately after the ten
`verify_level_bin` lanes.

**Why the ten lanes could not see this.** They ask whether the bytes are *self-consistent*:
every block decodes to its strips, every `.zx0` round-trips, the spawn has a floor under it.
All ten were green on this ROM. None of them asks whether the act is *playable* — and checking
the clip's own rectangle would have been green too, because inside the rectangle everything is
perfect. **The rectangle was the wrong subject; the gate scans the whole act.**

Per 8-px world column of the act:

1. **art** — some tile in the column is non-zero;
2. **a landing surface on every REACHABLE collision plane** — a SOLID_TOP attr with a positive
   height in the sensor's own column of the 16-byte profile, the arithmetic `probe_core` uses.
   Reachability is **read** from the crossover table, never assumed.

The unpainted remainder is declared in the manifest and the check is **two-sided**: a void
starting *earlier* than declared is missing content; *later* (or absent) is a stale declaration
that has stopped asking anything. A clip act with no declaration and a real void fails by name,
with the numbers — that is the state `s2_ehz_boot` shipped in.

Derived, never typed: the strip layout from `ojz_strip_gen`'s source; `SOLID_TOP`,
`COLL_CELL_W`/`COLL_CELL_H` from `engine/system/constants.emp`; the grid from the descriptor;
the rectangle from the manifest. Exit 2 (COULD NOT MEASURE) on a missing or short strip, an
unreadable crossover table, a constant that moved, or a tree that is not this clip act's.

**Red-first, mutations shown on disk before the red run** (all three on a copy of the real baked
tree, the real tree untouched):

| mutation | on disk | result |
|---|---|---|
| mark one crossover attr byte | `crossover.bin[9]` 0 → 1, nonzero entries 0 → 1 | exit **1**, names plane B's 8 columns |
| zero one tile column's plane-A collision | tile col 200's 128 plane-A bytes, nonzero 3 → 0 | exit **1**, names x run (1600, 1608) |
| remove a strip file | `sec1_strips_a.bin` moved away | exit **2**, COULD NOT MEASURE |

Plus 19 donor-free, build-free rows in `tools/test_clip_reachability.py`, proven to pass with
`games/sonic4/data/donors` moved away.

## 6. The bare-bake defect, and the stale-tree trap

Parcel 6 left `clip_rom_bake.py bake` dirtying the shipped tree when run by hand: R22 refused to
*start* over uncommitted work, but nothing put the tree back, and `build.sh`'s exit trap only
covers `build.sh`. The next person to `git commit -a` commits the clip act into the shipped act's
slot.

**A bare `bake` now restores on exit, win or lose.** It is exact rather than best-effort
precisely because R22 has already proven the pre-state clean — a restore is only safe when
something guaranteed what it restores *to*. "Write elsewhere" was not available: sigil places the
generated `.emp` modules by a fixed registry path and `map.toml` names their head labels, so the
bake must land in the shipped slot.

`--keep` opts out for the callers that need the tree to survive — `build.sh` (which owns its own
trap) and the two gates — and writes an **untracked** `clip_bake_stamp.json` naming the act.
`ground` and `clip_reachability` refuse on a missing or mismatched stamp, *before measuring
anything*.

That closes the second trap the owner hit: a `ground` run against a stale tree refused, but with
`donor_corroboration`'s message, which says *"a difference that is a multiple of 8 or 16 is a
PASTE SHIFT"*. It was not a paste shift. It was the wrong act, and a reader acting on that
message would go and audit R12 and the clip rectangle, which are innocent. It now says
**"STALE TREE, not a geometry problem"** and names the act it actually found.

## 7. ★ THE RUNTIME CHECK — TAGGED FOR THE FOREGROUND

**No emulator was used in this parcel and none may be.** This is the confirmation somebody has to
do by hand. It is written to be executable and to be able to FAIL.

**Boot:** `s4.s2clip.bin` — `S2CLIP=s2_ehz_boot ./build.sh`. Use the **plain** shape for
anything about the ground; on the DEBUG twin **press B first**, or the harness's free flight is
the condition under test.

**Inputs and what to look for, in order:**

1. **Hold RIGHT from the spawn.** He lands (415 px, ~0.5 s) and runs right over Emerald Hill's
   opening — in Oracle Jungle's colours, over Oracle Jungle's background, both inherited.
2. **At x ≈ 1,344 the ground falls away.** *This is expected.* It is EHZ's own jump; the floor is
   228 px below, at y ≈ 872. Sonic 2 puts five rings in an arc over it, and this act has no
   rings, so there is no cue. **He should land, not keep falling.**
3. **Keep going right to x ≈ 4,096.** The art and the ground stop at a hard vertical line and he
   falls with nothing to land on. **This is the reported bug and it is EXPECTED for a one-clip
   act** — it is now declared in the manifest and checked by the build.
4. **THE DISCRIMINATOR THIS PARCEL NEEDS — free flight, plain lateral movement.**
   Fly right along y ≈ 640 and watch the right-hand edge of the terrain.

| what you see | what it means |
|---|---|
| the only hard vertical line is at x = 4,096, and terrain is continuous everywhere left of it | **the static account is confirmed.** One boundary, the one in the bytes |
| a hard line at some *other* fixed world x, left of 4,096 | **the static account is WRONG** and there is a second cause the emitted bytes do not carry. Report the x — every column below 4,096 measures complete, so a line there is a runtime bound, not data |
| a line that **moves with you** and **fills in within a second when you stop** | a fill-throughput lag, not a bound: the camera outran `BLOCK_DECOMP_BUDGET` (6 blocks/frame). Would be a *new* finding — it is not what the bytes say and not what parcel 7 claims |
| the ground at x ≈ 1,344 does **not** catch him at y ≈ 872 | the collision planes are not reaching the sensors after all, and §1's table is wrong somewhere. This is the one result that would falsify the central claim |
| he ends up on plane B (anything that changes `layer`) | impossible per §4 unless something new writes it — and §4's 8 bottomless columns become live. Say so loudly |

**Verify DURING motion, not from a still frame.** The distinction between item 4's first and
third rows is *only* visible while moving and while stopping.

## 8. What is still open

* **The owner's x samples (1,472 / 1,901) are not reconciled.** Every column at those x measures
  complete — art, plane-A floor, block decode — so either the sampled quantity was not the
  player's world x, or there is a runtime bound the bytes cannot show. §7 item 4 is the
  discriminator, and this is flagged rather than explained away.
* **Plane B's 8 bottomless columns** are informational until something marks a crossover.
* **A clip act owning its own extent** is row 7+ and is the real fix for §2.
