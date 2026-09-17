# S2-COMPRESSED-ACT parcel 4 — the Sonic 2 collision base bank

**Date:** 2026-09-17 · **Branch:** `parcel/s2-collision-bank` (worktree `aeon-wt-s2coll`, base
`9b25b9b5`) · **Staged plan:** `docs/research/2026-09-17-s2-compressed-act-design.md` §10 row 4.
**Scope:** the shape bank and its five tables. No per-cell collision emission (that is row 5), no
engine code, no `.emp`, no ROM change. The shipping act's tables under
`games/sonic4/data/collision/` and the S&K bank under `.../collision/base/` are untouched, and so
is `games/sonic4/data/editor/ojz/act1`. Both donor trees were read-only throughout. No emulator.

## What shipped

| File | What it is |
|---|---|
| `tools/import_s2_collision.py` | the importer (`build`), the four falsifiable checks (`check`), and a line-for-line transcription of S2's own `FindFloor` |
| `games/sonic4/data/collision/base_s2/*.bin` | the bank: `heightmaps` 4,096 B · `heightmaps_rot` 4,096 B · `angles` 256 B · `solidity` 256 B · `crossover` 256 B |
| `tools/test_import_s2_collision.py` | 18 rows in the pre-build `pytest tools -m "not needs_build"` lane |
| `tools/test_cli_dispatch_refuses.py` | the new CLI registered in `_FIXED` + `_ROSTER`; census 20 → 21 |

The bank is a SECOND bank beside S&K's, in a sibling directory. Nothing in the build reads it yet.

## The two measurements the design told this parcel to re-derive

§13 named them as not reproducible from `s2_clip_budget.py` and said parcel 4 should re-derive
both "rather than inherit them". Both were re-derived from the donor trees and the S&K bank.

### 1. Reachability — the design says 75, it is **68**

| Figure | Design | Re-derived |
|---|---|---|
| distinct shapes the six showcase zones reference | 151 | **151** ✓ |
| of those, unreachable from the S&K bank under all four flips | 75 | **68** ✗ |

The 151 reproduces exactly, and it is the six-zone union with the REAL prototype Hidden Palace
(EHZ 55, CPZ 68, OOZ 36, MTZ 38, WFZ 61, HPZ 69 distinct non-zero ids in their own collision
indices). 75 does not reproduce under any scope or array pairing tried:

| Scope / pairing | Unreachable |
|---|---|
| six-zone union, S2 vertical vs S&K vertical (the stated question) | **68** |
| five final zones only (the pre-prototype scope) | 64 |
| all nine final-donor zones | 76 |
| every non-empty S2 slot (224) | 120 |
| six-zone union, S2 horizontal vs S&K vertical (the §3.5 confound) | 84 |
| six-zone union, matching on (profile, angle) rather than profile | 107 |
| counting distinct profiles instead of ids | 68 |

The design's illustration is also false in both halves: *"including a shape as plain as a 6-px
flat floor"* — a 6-px flat floor IS in the S&K flip closure, and **no S2 slot is a 6-px flat
floor at all.**

**The conclusion is untouched and this parcel is still necessary.** 68 of 151 is 45% of the
shapes the act needs, and the S&K bank cannot express them. A true illustration, for whoever
wants one: S2's vertical array contains no hanging (negative) bytes at all, where S&K's contains
362 — the two banks are not near-misses of one vocabulary.

### 2. The rotated-heightmap sign disagreement — the design's **211 is right**, and it is a whole-convention inversion

| Figure | Design | Re-derived |
|---|---|---|
| shapes where `rotate_profile` disagrees with S2's shipped horizontal array | 211 of 256 | **211 of the 255 it can answer** ✓ |
| of those, pure sign disagreements | all 211 | **all 211** ✓ |
| shapes where `rotate_profile` raises | 1 (`$18`) | **1 (`$18`)** ✓ |

212 of 256 once the now-RULED `$18` is counted, which is what `check sign` reports. 44 agree
exactly, and they are precisely the shapes whose rows are only 0 and 16 — the values that carry
no sign.

The design describes this as a sign disagreement. It is more than that, and the sharper statement
matters for row 5: **the two conventions are exact opposites, and it is confirmed from both
sides' code, not inferred from the byte diff.**

```
S2    s2.asm:43282 FindWall2, loc_1EA78 / loc_1EAE0
      +w  -> d1 = $F - ((x&$F) + w)      the wall's face is at column 16-w   RIGHT-anchored
      -w  -> embedded iff (x&$F) < w      the run is columns 0..w-1           LEFT-anchored

aeon  games/sonic4/player/player_sensors.emp, probe_core + Collision_ProbeLeft/Right
      +w  -> partial for a LEFT probe, dist = 16 - w - (15-s) = s+1-w         LEFT-anchored
      -w  -> negated by ProbeRight's pnegate into +w                          RIGHT-anchored
```

1,533 rows are S2-positive where aeon wants negative and 139 are the other way — both directions,
which is what an inverted convention looks like and what a one-sided bug would not.

**Constructively**: decode each row of both arrays to a SET OF SOLID COLUMNS under its own
convention, and compare each against the vertical array's own coverage. On all **3,584 of 3,584**
non-air rows the two decodings agree with each other AND with the vertical array. The vertical
array is a third, independent witness, so this cannot pass by agreeing with the wrong reference.
Regenerating is therefore a pure transcription and loses nothing; copying would mirror the solid
side of every partial wall row, and a wall solid on the left of a cell would push from the right.

### 3. The donors share one vocabulary — re-checked, and it holds

Parcel 1's claim, re-measured because this bank must serve Hidden Palace too: the prototype's
`Collision array 1.bin` is byte-identical to the final game's `Collision array - Vertical.bin`
(sha1 `9cc4c24e980f`), `2.bin` to `- Horizontal.bin` (`a3d9d599dae5`), and the angle tables are
identical (`35bf06c2ab64`). One bank serves both donors. A gate row also asserts the consequence
directly: every shape HPZ's collision indices name is non-air in this bank.

## The `$18` ruling

`$18` is a symmetric 45-degree **peak**, `[2,4,6,8,10,12,14,16,16,14,12,10,8,6,4,2]`:

```
r 0 .......##.......      r 8 ...##########...
r 2 ......####......      r10 ..############..
r 4 .....######.....      r12 .##############.
r 6 ....########....      r14 ################
```

Its upper 14 rows have a solid run touching NEITHER edge. Aeon's rotated table stores one signed
byte per row and can name a run only by an edge anchor plus a width, so a centred run is not
representable at all. It is the only such shape in the S2 bank, and the S&K bank has none.

**RULED: keep the run's width, anchor it at the RIGHT edge** — `(256 - w) & 0xFF`.

- **It is what Sonic 2 itself shipped.** S2's own row for `$18` is
  `[2,2,4,4,6,6,8,8,10,10,12,12,14,14,16,16]` — the run's width at each row, positive, which in
  S2's convention means right-anchored. Transcribed into aeon's inverted convention that is
  exactly what the rule produces, and the gate asserts that equality rather than a hand-typed
  pin. It is the only evidence of intent that exists.
- **It preserves an invariant both donors satisfy with zero exceptions.** Measured across both
  banks: **0 rows are vertically covered but zero in the shipped rotated array.**
- **`$18` is referenced by NO showcase zone**, so the ruling is a completeness question, not a
  gameplay one. A gate row fails if that ever stops being true.

**Emitting 0 (air for the horizontal probe) was considered first and rejected**, on the third
measurement above: it would make aeon's the only bank of the three where a wall probe sees air
through solid geometry. The initial instinct was 0 — "never invent solid where there is none" —
and the invariant measurement, taken as a control, pointed the other way. The cost of the chosen
rule is bounded: the run keeps its width and only its anchor moves, by 7 columns at the tip and 1
at the base.

**A row with MULTIPLE solid runs still raises.** There is no defensible single byte for one, the
S2 bank contains none, and a silent answer there would be a fabrication. A gate row keeps that
refusal alive with a synthetic two-run profile, since no real shape exercises it.

## The design's own check, both halves

### Half one — every shape round-trips, no raise

`256/256`, no raise, **1** via the centred-run ruling. The check reads `heightmaps.bin` off disk
and re-derives every rotated row from it, so it measures the committed artifact rather than an
in-memory value.

`rotate_profile_ruled` is deliberately NOT a fork of the shared convention: when no row needed
the ruling it asserts its result equals `collision_pipeline.rotate_profile` exactly. The two can
only differ where the shared one refuses to answer at all.

### Half two — against the donor's own lookup, re-implemented

The design asks that "a hand-picked slope's height and angle match `FindFloor`'s result for the
same block in the donor". Hand-picked was widened to **exhaustive**, and `FindFloor` was
re-implemented in Python from `s2.asm:42942`/`43030` rather than run in an emulator:

> **3,612,672 probes** — every distinct chunk-entry word of all six zones × 16 x-sub × 16 y-sub ×
> both sensor classes. **0 exit-kind mismatches, 0 angle mismatches, 0 distance mismatches.**
>
> Population (S2's own exit, so the sweep is not agreeing about air): top sensor 145,392 surface /
> 520,425 full-back / 1,140,519 air; L/R/B sensor 124,544 / 605,463 / 1,076,329.

The two implementations turn out to match structurally, exit for exit, which is why the check can
be this sharp:

| S2 `FindFloor` | aeon `probe_core` |
|---|---|
| `loc_1E7E2` — air, evaluate the cell one step forward | `.empty_fwd` |
| `loc_1E86A` — solid through, evaluate one step back | `.full_back` |
| fallthrough — surface here, `d1 = $F - (sub + h)` | `dist = 16 - h - sub` |
| X flip: `not.w d1` on the column, `neg.b` on the angle | `flip_profile_x` (reverse), `flip_angle_x` (`-a`) |
| Y flip: `+$40 ; neg ; -$40` on the angle | `flip_angle_y` (`-a-$80`) |

Two differences exist and both are accounted for, not waved past:

1. **The distance is off by exactly one, always.** S2 measures to the last empty pixel, aeon to
   the first solid one. The check asserts `aeon == S2 + 1` on every one of the 269,936 surface
   probes rather than ignoring the field, so a future divergence in the arithmetic is caught.
2. **Y-flipping a full column (`h = 16`) diverges, and the divergence cancels.** S2 negates to
   `-16`; aeon's `flip_profile_y` keeps `16`. S2's `-16` then always satisfies `sub + h < 0`, so
   it falls to `loc_1E86A` — the same back-probe aeon reaches from `16` via `.full_back`. The
   two are equivalent at the exit, and the sweep proves it across every y-flipped word in the
   donor rather than leaving it as an argument.

**A defect was found in the CHECK while writing it**, and it is the reason both sensor classes
are now swept. The aeon side originally omitted `probe_core`'s `and.b d6,d0 / beq .cl_air`
solidity-class gate, and answered full-back for **158,442 of 1,806,336** probes where S2 answers
air — every one of them an L/R/B-only cell read by a floor sensor. `bake_cell` interns a cell
whose solidity is non-zero for EITHER class, because the runtime decides which sensor is asking.
The bank was never wrong; the check was. An anti-vacuity row now proves the donor actually
contains class-asymmetric cells, so the gate that broke once cannot go untested.

## The row 4 / row 5 boundary — one finding, no silent absorption

The boundary is drawn in the right place, and two things row 5 inherits are worth stating before
someone hits them.

1. **`ojz_strip_gen.load_base_bank()` still hard-codes `games/sonic4/data/collision/base/`.**
   Teaching the bake to select a bank is row 5's first move. It was deliberately NOT done here:
   an unused parameter added a parcel early is a dormant scaffold, and the bank is the only thing
   row 4 owed.
2. **`collision_pipeline.emit_tables()` calls the UNRULED `rotate_profile` on the interned
   heights** (`:348-354`), so if a row-5 clip ever interns `$18` or a flip of it, the bake raises
   at emit time and the importer's local ruling does not help. It is safe today — `$18` is in no
   showcase zone, and the raise condition is a property of the height profile that all four flips
   preserve, so a shape safe unflipped is safe flipped. Row 5 must decide whether `emit_tables`
   gets `rotate_profile_ruled` or keeps the loud refusal. Leaving `rotate_profile` raising is the
   deliberate choice here: it is a live tripwire for the shipping act, and turning a refusal into
   a silent value is not row 4's call to make on the shipping path.

## Evidence

**Pre-build tool lane** `python3 -m pytest tools -m "not needs_build" -q`, `__pycache__` cleared,
**no converted donor trees present — the state a fresh checkout is in** (this worktree has never
run `s2_zone_convert.py`; `games/sonic4/data/donors/` does not exist):

> **4 failed, 2986 passed, 2 skipped, 28 deselected, 55 errors, 143 subtests passed in 69.32 s**

The 4-failed / 55-error artifact-freshness family was established by an **in-place control taken
before this parcel touched anything** — the same worktree at base `9b25b9b5`, same conditions:
**4 failed, 2965 passed, 2 skipped, 28 deselected, 55 errors in 65.19 s**, and the four FAILED
node ids are byte-identical between the two runs. Delta **+21 passed** = 18 gate rows + 2 CLI
refusal rows + 1 mode-table row. No row of this parcel is among the failures or errors.

**The checks**, `python3 tools/import_s2_collision.py check`, exit 0, 3.0 s.

**Red-first**, eight mutations, each applied on disk, the diff shown, run red, then restored from
a COMMITTED baseline (`git show HEAD:` into the scratchpad, restored by copy, verified with
`cmp`):

| # | Mutation | Red |
|---|---|---|
| M1 | `$18` ruled LEFT instead of RIGHT | ruling row |
| M2 | `$18` ruled to 0 — the rejected alternative | ruling row |
| M3 | a multi-run row fabricates an answer | refusal row |
| M4 | `probe_core`'s class gate removed | FindFloor row (the real defect) |
| M5 | `default_out` bound at import time | call-time row |
| M6 | Y-flip angle uses the X formula | FindFloor row |
| M7 | the rotated table COPIED from the donor | 3 rows, incl. the central one |
| M8 | CLI dispatch falls through to the writing `build` | both refusal rows; the tripwire fired, proving the real `build` never ran |

**Another gate caught this parcel and was right.** `test_cli_dispatch_refuses`'s census flagged
the new tool as an argv dispatch with no recorded verdict (20 → 21). Because `build` OVERWRITES a
tracked bank — the `ojz_strip_gen` shape of the LS-15d incident — the CLI was converted to a
MODES table whose dispatch runs before any handler, `main()` now raises `SystemExit(1)` rather
than returning, and the tool is registered in `_FIXED` with its writing handlers blinded. It is
deliberately given NO subprocess row: that file's own rule is that a writing tool must never have
one, because on a regression the row's failure IS the write.

Nothing here is build-adjacent — no `.emp`, no generator the build runs, no committed input the
ROM embeds — so no ROM byte moves. `tools/landing_build.sh` was run anyway, as the parcel's
pre-merge check; its result is in the `S2-COMPRESSED-ACT` booking.

Wall clock at measurement: 2026-09-17, dev box up 1 day 21 h, load average 3.4-4.8 across the
runs. No emulator was used.
