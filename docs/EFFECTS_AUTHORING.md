# Effects Authoring — the Phase-3 raster and palette vocabulary

**Status: specification.** This document is written *before* the code it describes, on purpose: spec
§4.1 requires Parcel A to open with a vocabulary table, because "the byte-compare gate is only
winnable if the vocabulary can express every word already in the tree." `engine/effects/raster_dsl.emp`
and `engine/effects/palette_dsl.emp` (Parcel A Tasks 4-8) are written to satisfy this document, and the
two shipped fixtures are re-expressed against it **byte-for-byte**. After Parcel A lands, this is the
standing authoring reference.

Source of truth for the runtime side is `engine/effects/raster.emp` — the decoder. This document owns
the **encoding**; that module owns only the decoding. Where the two disagree, the ROM is the arbiter and
one of them is wrong.

Line citations are as of the commit that introduced this file. Cited symbols are named alongside their
lines so a citation that drifts is still followable.

---

## What the DSL is for

Today a raster program is a hand-laid `[u16; N]` with a hand-counted length, a hand-computed VDP timer
arm word, a CRAM command hand-split into two literal hex words, a hand-written `count-1`, and a
`pal_dirty_mask` the author had to know to type — see `games/sonic4/data/parallax/configs.emp:316-335`
(`OJZ_TestRaster`) and `:395-409` (`OJZ_WaterRaster`). Every one of those is a place where a correct
program and a silently wrong program look the same on the page; the `%0001`-instead-of-`%0100` mask bug
that made P1's red cover the whole ground instead of just the region below the split
(`configs.emp:317-322`) is the recorded instance. The vocabulary's goal is that an author adds a water
section by naming a screen line, a palette region and a variant slot — **without typing a VDP register
word, an arm word, a CRAM command, a `count-1`, a dirty mask, or a word count** — and that the classes
of mistake listed under "New correctness the constructors guarantee" become unrepresentable rather than
merely discouraged.

---

## Scope — what is and is not authorable in Phase 3

**Sparse tier only.** The general constructors (`raster_words` / `raster_program`) cover the sparse tier:
a schedule of per-scanline VDP work in which HInt fires only on event lines.

**The dense tier keeps `raster_gradient_program`** (`raster.emp:258-286`) and is not folded into the
general constructor. The reason is structural, not stylistic: a dense run carries a **link-time ROM
stream pointer** (`rgp_stream: *u8`, `raster.emp:254`) and a `[u16; N]` literal array cannot hold a
symbol address at any spelling. So the dense tier stays a `struct` built by its own constructor, and
`OJZ_TestGradient` (`configs.emp:454-459`) keeps using it.

**A program mixing sparse events with a dense run is NOT authorable in Phase 3** (spec §4.1). The wire
format *permits* it — `Raster_HInt`'s `.op_run_gradient` falls through to `.advance`
(`raster.emp:495-508`), and the LEAVE schedule (`raster.emp:419-425`) explicitly discusses "the first
post-gradient sparse event". Neither constructor can author that combination, and neither is being
extended to. **A section takes one tier or the other.** If a future pack member needs the mix, that is a
design change to raise, not something to assemble by hand-editing a program array.

---

## ⚠ The T-1 trap: a dense fact that must never touch sparse arithmetic

The dense tier's setup record sits at screen line **T-1** for a run whose first stream line lands on T.
That number is **measured, not derived** — `raster.emp:236-243` records the measurement: the naive
derivation puts the setup at T-2, and on hardware that authored the whole run one line high (with
`top=96` the level boundaries came out at 107/119/131/143/155/167/179 instead of 108/120/.../180, a
uniform -1 across all seven). The dense path does not inherit the sparse -1 because entering the run
costs its own pipelined arm, which absorbs exactly one line.

The sparse tier's rule is different, and it rests on different evidence: an effect authored to land on
screen line M fires at **M-1** because a register write in the handler for fire line L affects line L+1
at the earliest. That is a **documented hardware rule** — the Sega manual's "the CPU can control the
display of the next line but not the line on which the interrupt occurs", plus hardware-verified sources
and the one corroborating disassembly (survey `:29-40`, Ruling 1a) — not a measurement taken against our
own code. The sparse authorities in the tree are `raster_arm` and `raster_fire_line`
(`raster.emp:197-213`) and `water_arm0` (`raster.emp:592-595`).

**Applying the dense off-by-one to sparse arithmetic fails the byte-compare in the most confusing
possible direction** — every word is plausible, the program assembles, the length matches, and the
effect is silently one line off. Two different facts, two different tiers. Do not carry one into the
other.

---

## Sparse program wire format

```
word 0            pal_dirty_mask          DERIVED — OR of (1 << (cram_addr >> 5)) over every CRAM-class op
word 1            init_count N            DERIVED — count of distinct frame-top reset words
words 2..2+N-1    init words              DERIVED — each set_reg op's reset word, first-appearance
                                          order, deduped
                  ---- records ----
record 0          arm, 0                  priming, fires on line 0
record 1          arm, 0                  priming, fires on line 1
record 2..k+1     arm, op_count, <ops>    one per authored fire, in ascending screen-line order
record k+2        arm, RASTER_OPS_END     terminator
```

This is the layout `Raster_VBlank` walks (header: `raster.emp:344-355`) and `Raster_HInt` dispatches
(`raster.emp:434-508`). `pal_dirty_mask` is OR'd into `Palette_Dirty` **every frame**
(`raster.emp:345-346`), which is what makes a mid-frame CRAM write transient: the base palette is
restored at frame top, so above the fire line you see the base and below it you see the effect. A mask
naming the wrong line leaves the write latched forever.

### The record / arm schedule

Record `i` carries the arm word for `gap(L[i+1] -> L[i+2])`, where

```
L = [0, 1, M_1 - 1, …, M_k - 1]
```

and `M_j` is the authored **screen line** the effect lands on. The fire line is `M - 1` (Ruling 1a) and

```
arm = $8A00 | (L[i+2] - L[i+1] - 1)      (the -1 is Ruling 1a's bias; the i+2 is Ruling 1b's lag)
```

Past the end of `L` the arm parks at `$8AFF` (`RASTER_ARM_PARK`, `raster.emp:137`) — the next fire would
be 256 lines away, i.e. never within active display.

The `i+2` is not an off-by-one; it is the hardware. The VDP reloads its line counter from reg `$0A` *at
the instant of underflow*, before the 68000 executes a single handler instruction, so a write to `$8Axx`
from inside handler `i` is not consumed by the gap it is sitting in — it is consumed at fire `i+1` and
therefore schedules `gap(i+1 -> i+2)`. The full argument is at `raster.emp:24-40`.

**For a single-event program at screen line M this reduces to `$8A00 | (M - 3)`** — exactly what
`water_arm0(M)` produces (`raster.emp:592-595`), which is what lets `OJZ_WaterRaster` come out
byte-identical.

### Worked check against both shipped fixtures

Both fixtures are one event at screen line 120, so `L = [0, 1, 119]` for both.

| | `OJZ_TestRaster` (`configs.emp:316-335`) | `OJZ_WaterRaster` (`configs.emp:395-409`) |
|---|---|---|
| record 0 arm | `$8A00 \| (119 - 1 - 1)` = `$8A00 \| 117` = **`$8A75`** ✓ shipped `$8A75` | same = **`$8A75`** ✓ shipped `water_arm0(120)` |
| single-event form | `$8A00 \| (120 - 3)` = `$8A00 \| 117` = `$8A75` ✓ | `120 - 3 = 117` ✓ |
| record 1 arm | `i+2 = 3 = L.len` → park **`$8AFF`** ✓ | ✓ |
| record 2 arm | `i+2 = 4 > L.len` → park **`$8AFF`** ✓ | ✓ |
| word count | `2 + 1 + 4 + (2 + 2 + 5) + 2` = **18** ✓ declared `[u16; 18]` | `2 + 1 + 4 + (2 + 2 + 5) + 2` = **18** ✓ |
| `pal_dirty_mask` | CRAM `$4A` → `1 << ($4A >> 5)` = `1 << 2` = **`%0100`** ✓ | CRAM `$48` → `1 << 2` = **`%0100`** ✓ |
| CRAM addr decode | `$4A` → line `2`, entry `5` | `$48` → line `2`, entry `4`; the staging source `pal_stage_off(0, 2, 4)` separately evaluates to 72 |

Word-count breakdown, identical for both: 2 header words (`pal_dirty_mask`, `init_count`) + 1 init word
(`$8C81`) + 4 for the two priming records + 9 for the event record (2 for `arm`/`op_count`, 2 for the
`set_reg`, 5 for the CRAM-class op) + 2 for the terminator = 18.

**A coincidence to not read as a rule:** in `OJZ_WaterRaster` the staging offset and the destination
CRAM address are both 72 (`$48`). They are different quantities in different address spaces — a
`Pal_Variant_Stage` RAM offset and a CRAM byte address — and they agree here *only because the slot is
0*. For slot 1 the same region would stage from offset `1*128 + 2*32 + 4*2` = 200 while the CRAM address
stayed `$48`. `pal_region` checks that the two name the same *line and entry*, not that they are the
same number.

Verified against the shipped words, not asserted from the plan.

---

## Descriptor set

| Constructor | Parameters | Emits | `op_size` |
|---|---|---|---|
| `set_reg(word, reset)` | `word` = mid-frame `$8xxx` VDP register write; `reset` = the frame-top word restoring the **same** register | `OP_SET_REG, word` | 2 |
| `sh_on()` | none | `set_reg($8C89, $8C81)` — Shadow/Highlight on below the fire, H40 base restored at frame top (`engine/system/boot_data.emp:140`) | 2 |
| `cram(addr, colours)` | `addr` = CRAM **byte** address; `colours` = 1..3 colour words, inline | `OP_CRAM, cmd>>16, cmd&$FFFF, colours.len-1, <colours>` | `4 + colours.len` |
| `pal_region(addr, slot, pal_line, entry, count)` | `addr` = destination CRAM byte address; `slot`/`pal_line`/`entry` = the `Pal_Variant_Stage` source; `count` = 1..3 | `OP_PAL_REGION, cmd>>16, cmd&$FFFF, count-1, slot*128 + pal_line*32 + entry*2` | 5 |
| `fire(line, ops)` | `line` = screen line 3..223 the effect lands on; `ops` = descriptor array | one record: `arm, ops.len, <bodies>` | `2 + Σ op_size` |
| `region_boundary(line, addr, slot, pal_line, entry, count, sh)` | thin composite. **`sh` is required — deliberately no default**, see "Why `sh` has no default" below | `fire(line, [sh_on(), pal_region(…)])` when `sh == 1`, else the region alone | as above |
| `raster_words(fires)` | descriptor array | the word count, computed from `op_size` — **independently of** `raster_program`'s concatenation | — |
| `raster_program(fires)` | descriptor array | the flat `[u16]` | — |

`cmd` is `vdp_comm(addr, VdpTarget.Cram, VdpOp.Write)`. `vdp_comm` is a `COMPTIME_HELPERS` member and is
therefore glob-injected at every call site, so naming it inside a constructor body is safe.

The opcode values themselves (`OP_SET_REG = 0`, `OP_CRAM = 2`, `OP_PAL_REGION = 4`,
`OP_RUN_GRADIENT = 6`) live at `raster.emp:87-129`; `RASTER_CRAM_MAX = 3` at `:143`;
`RASTER_BUF_SIZE = 128` at `:178`. `raster_dsl` inlines them as literals and pins each with a
module-level `ensure` — see "The discipline rule" below for why.

### Four per-op quantities, deliberately distinct

The encoding asks four different questions of one op, and the answers are **not** interchangeable. This
is where a plausible-looking simplification does real damage: a `pal_region` occupies 5 wire words but
writes `count` colours, and a `set_reg` occupies 2 wire words but writes no CRAM at all — so counting
either one with the other's function silently mis-sizes a program or mis-budgets a fire.

| Helper | Answers | `SetReg(w, reset)` | `Cram(a, cols)` | `PalRegion(a, slot, pl, e, n)` |
|---|---|---|---|---|
| `op_size` | wire words the op occupies | 2 | `4 + cols.len` | 5 |
| `op_cram_words` | **CRAM words the handler writes** — what `fire` sums against the per-fire ceiling | 0 | `cols.len` | `n` |
| `op_mask` | the `pal_dirty_mask` bit the op needs re-asserted at frame top | 0 | `1 << (a >> 5)` | `1 << (a >> 5)` |
| `op_init` | frame-top reset words the op contributes | `[reset]` | `[]` | `[]` |

`op_size` feeds `raster_words`; `op_cram_words` feeds `fire`'s per-fire budget check; `op_mask` and
`op_init` feed the header, OR'd and deduped-in-first-appearance-order respectively. All four are private
to `raster_dsl` — an author never calls them — but knowing they are distinct is what makes the guarantee
list below readable.

### The authoring shape

Two declarations. A variable-length value cannot be a struct field, so the program is its own `pub data`:

```
const WATER_PROG = [ region_boundary(line: 120, addr: $48, slot: 0, pal_line: 2,
                                     entry: 4, count: 3, sh: 1) ]

pub data Water_Prog: [u16; raster_words(WATER_PROG)] = raster_program(WATER_PROG)
```

The length annotation must sit on the `data`. **`const` does not enforce its declared array length; only
`data` does** — probed and measured on this tree, `docs/superpowers/notes/2026-08-13-parcel-a-capability-probe.md`
(the "Step 6" negative control).

### Why `sh` has no default

`region_boundary`'s `sh` is a **required** parameter. A `= 0` default would be the ordinary, friendly
choice and it is the wrong one here, because `sh: 0` is the *dangerous* value:

`sh: 0` produces a program with **zero** init words (nothing contributes a frame-top reset), which moves
the priming arm word from word 3 to word 2. But `Raster_PatchWaterLine` writes
`WATER_TEMPLATE_ARM0_OFF = 6` — byte offset 6, i.e. **word 3** — unconditionally, at all three of its
exit paths (`raster.emp:656`, `:665`, `:668`). On a patched template that write lands on a priming
record's `op_count` instead of its arm word, and `Raster_HInt` then does `subq #1` on a value that was
never a count and walks tens of thousands of words of garbage as ops.

A default would have made that the outcome an author gets by *not thinking about Shadow/Highlight at
all* — the failure would be reached by omission. Requiring the parameter forces the thought. It is not
a complete guard on its own; see the init-count pairing under the guarantees below.

### Deviation from the spec's sketch, recorded so it is not silent

Spec §4.1 sketches `region_boundary(line:, variant:, sh:)`. That signature presumes a **preset binding
that does not exist until Parcel C** — there is no `variant:` handle to name yet. Parcel A therefore
ships the primitives (`fire`, `set_reg` / `sh_on`, `cram`, `pal_region`) plus a `region_boundary` whose
parameters are the ones `OJZ_WaterRaster` actually needs. Parcel D re-shapes the signature once it knows
the pack. This is a deviation from a spec *sketch*, not from a ruling.

---

## Reaching the ROM: what to import, and how a program gets installed

**Imports.** After Parcel A, `engine.effects.raster_dsl` and `engine.effects.palette_dsl` are members of
sigil's `COMPTIME_HELPERS` (`native.rs:1733-1746`, twelve members before this parcel, fourteen after),
so every `pub` item in them — `fire`, `cram`, `set_reg`, `sh_on`, `pal_region`, `region_boundary`,
`raster_words`, `raster_program`, `variant`, `cycle_channel`, … — is **ambient in every module**. No
`use` is required to call them, and `normalize_helper_imports` strips an explicit helper `use` at build
time anyway. Writing one regardless is the house convention where it documents a seam worth naming
(`raster.emp:14`'s `use engine.structs.{Sec}` is exactly such a line: `engine.structs` is itself a
helper). What you **must** still import by hand are the wire-format **struct type names** from
byte-emitting modules — `RasterGradientProgram`, `pal_variant`, `PalCycleScriptN` — because those
modules emit bytes and therefore can never be helpers.

**Install.** A compiled program is inert data; something has to point the runtime at it. Three routes:

1. **Per-section (the normal one).** Point the section's `Sec.sec_raster_table` at your `pub data`.
   `Raster_InstallSection` (`raster.emp:544-554`) consumes it on a boundary crossing. NULL means "keep
   the current program", *not* "no effects" — a section that must turn a neighbour's effect **off**
   points at `Raster_Program_None` (`:559`), an explicit empty program. Raster programs snap; they are
   never lerped across a boundary.
2. **Imperative.** `Raster_Install` with `a0` = the program (`raster.emp:294-297`); `Raster_Clear` to
   remove one (`:302-306`). The install is *staged* and consumed at the next `Raster_VBlank`, so it can
   never tear a frame mid-walk. Main-loop context only.
3. **Runtime-patched (the water route).** `Raster_InstallWater` with `a0` = the template and `d0.w` =
   the screen line (`raster.emp:607-623`) copies the program into `Raster_Buf_B` and makes it live; then
   call `Raster_PatchWaterWorldY` once per frame (`:682-687`) to keep the boundary anchored to a **world
   Y** as the camera moves, which is what makes the effect stay on a place in the level rather than at a
   fixed height on the display. `Raster_PatchWaterLine` (`:648-670`) does the actual one-word arm
   rewrite and owns the two off-screen semantics (above the viewport = fully submerged, fire as early as
   possible; below it = park). **This is the route carrying the `init_count == 1` invariant** described
   under the guarantees.

Route 3's call sites are what Parcel C replaces: the imperative water install is deleted in favour of a
single `sec_effects` preset pointer (spec ruling 2). The program format and this vocabulary are
unaffected by that change — only who calls the installer.

---

## What each guard actually proves

This table matters more than the descriptor table. This codebase has shipped guards that measured the
placer instead of the subject and guards that could not fail; be precise about what is and is not
covered.

| Guard | Catches | Does **not** catch |
|---|---|---|
| `ensure(out.len == raster_words(fires))` **inside** `raster_program` | header/record **framing** drift between the two independent computations (`op_size` path vs `op_words` concatenation path) — this is the instance that fires first on genuine framing drift | a wrong word *value* inside a correctly-sized body |
| `data X: [u16; raster_words(P)] = raster_program(P)` | that the declared length was computed by the size path over **the same** descriptor list the body was built from — i.e. an annotation naming a different program, or a hand-typed literal length going stale. `data` hard-checks element count (probe-measured) | a wrong word value; and note it re-checks a fact `raster_program` already asserted internally, so it is a second lock on the same door rather than a wholly independent one |
| The same annotation on a `const` | **nothing** — measured vacuous on this tree (probe note, Step 6). Put length guards on `data`, or assert with an explicit `ensure` on `.len` | everything |
| The retained hand-word twin + its `first_mismatch` ensure | any word-value drift in the two shipped fixtures, reported as "DSL output diverges at index *n*" rather than "golden ROM differs" | a fixture the twin does not cover; and it pins the DSL to the *hand words*, so a shared misunderstanding of the hardware would satisfy it |
| Seven golden ROMs | every emitted byte, everywhere | nothing — **this is the parcel's real bar** |

Writing `data X: [u16; P.len] = P` instead would be **tautological** and is forbidden: the annotation
and the value would be two readings of one computation, so it cannot fail for any reason that matters.
It is the `gate-measures-the-placer` failure one layer up.

### What the vocabulary does NOT check (know these before authoring)

Stated plainly rather than left for someone to discover on hardware:

- **The patched-water template's `init_count == 1` requirement — not by the vocabulary.**
  `WATER_TEMPLATE_ARM0_OFF = 6` (`raster.emp:572`) is a byte offset that is only correct when the header
  carries exactly one init word: with `N = 1` the layout is `[mask 0][init_count 2][init[0] 4][arm0 6]`,
  but with `N = 0` offset 6 lands on `op_count` and with `N = 2` `arm0` moves to offset 8 (so the patch
  would rewrite an *init word* every frame instead of the boundary). Because `raster_program` **derives**
  the init words from the ops, a patched template's init count is a consequence of how many *distinct*
  `set_reg` reset words the program happens to use. Two things mitigate it and neither is a general
  guard: `region_boundary`'s `sh` is required, so the zero-init case cannot be reached by omission; and
  the water fixture carries a **co-located** `ensure` that word 3 of its own compiled program is the
  expected priming arm word. **If you author any other program destined for the water patch slot, write
  that assertion yourself** — nothing in `raster_dsl` knows a program is going to be patched.
- **Parameter type annotations.** They are mandatory to parse but mostly not enforced: `[T; N]` on a
  parameter is *not* a checked length (a 4-element list binds to an `[int; 3]` param), which is why
  loose list params are spelled `array` and length checking is done with explicit `ensure`s on `.len`.
  `Reg` and `Label` **are** class-checked by exact spelling, on explicitly supplied args only — do not
  strip a `Label` annotation as decorative. All measured; see the probe note.
- **Reachability of a non-helper comptime module.** A pure-comptime module's `ensure`s do not *pass*
  when nothing imports it — they are **never evaluated at all**, with no diagnostic and a green build.
  That hazard applied to `raster_dsl` before it joined `COMPTIME_HELPERS`, which is why
  `configs.emp:40` carries a `use engine.effects.raster_dsl.*` glob with a do-not-prune comment
  (`:35-39`). Membership in the helper list removes the hazard for these two modules; it remains live
  for any *new* pure-comptime module that is not a helper.

---

## New correctness the constructors guarantee (ruling 5)

- **`set_reg`**: the mid-frame word and its frame-top reset must target the **same** VDP register — so a
  mode change can never latch past the frame. The reset is not optional and is not typed separately into
  a header; `raster_program` derives the program's init words from these resets, so an author cannot
  write the mid-frame half alone.
- **`pal_region`**: the destination CRAM address must name the **same line and entry** as the staging
  source (`(addr >> 5) == pal_line` and `((addr >> 1) & 15) == entry`). Hand authoring had no such check
  — the two were independent literals.
- **`pal_dirty_mask` is derived** from the CRAM addresses rather than typed. A mask naming the wrong
  line is the observed P1 bug (`configs.emp:317-322`); it is now unrepresentable.
- **Palette line 0 is refused.** `cram` rejects an address on CRAM line 0 and `pal_region` bounds
  `pal_line` to 1..3. Line 0 is the character's (`CharacterDef.cd_palette`); a raster write there
  repaints the active character.
- **`raster_program`**: `words * 2 <= RASTER_BUF_SIZE` (spec §10 rider 4). `Raster_VBlank`
  (`raster.emp:335`) and `Raster_InstallWater` (`:612`) both copy a **fixed 128 bytes**, so a longer
  program would be truncated live. (The converse over-read of a short template is pre-existing and
  harmless — the walker never reaches past the terminator. It is spec §10 rider 4, *awaiting* a
  `docs/BUGS.md` entry: checked at this commit, `BUGS.md` does not yet carry it.)
- **The per-fire CRAM budget**: `fire` sums `op_cram_words` across all of its ops and requires the total
  to be `<= RASTER_CRAM_MAX` (3). `RASTER_CRAM_MAX` is a **per-fire cycle** budget, not a per-op one —
  `raster.emp:72-76` derives it from the ~60 usable cycles between HINT-pending and the next line's
  active display, and that ceiling applies to the whole handler entry. The per-op bounds inside `cram`
  and `pal_region` are therefore *necessary but not sufficient*: three 3-colour ops in one fire satisfy
  every per-op check and blow the budget threefold, painting visible CRAM dots (single-ported CRAM,
  Ruling 2b). The legitimate way to write more colours is **consecutive fires on successive lines** — a
  full 16-colour line takes `ceil(16/3) = 6` of them, which is S3K's actual technique and precisely why
  it pushes the dots offscreen. (Note the per-op `<= 3` bound is now *subsumed* by the per-fire sum for
  any op that reaches the wire; it survives for the better error message, not for extra coverage.)
- **Fire ordering**: fires must be in strictly ascending screen-line order and no two events may share a
  fire line; the schedule *is* the program order, since the runtime never compares a line number.
- **Mixed fires**: `OP_SET_REG` must be the **first** op (ruling 14, spec §5.4). Not a style rule.
  `OP_SET_REG` writes with no delay (`raster.emp:456-457`) while every CRAM-class op first burns
  `EFX_BLANK_DELAY` (`:462-466`, `:482-485`), so a `SET_REG` placed *after* a CRAM op executes strictly
  later in the line — worse than the measured ~45%-across-line-119 mode switch a mixed fire already
  costs (`raster.emp:163-168`), and invisible to an author. A pixel-clean mode change must be scheduled
  a line earlier instead.

---

## The discipline rule for anyone adding a constructor

> **A constructor's returned value may name only its own parameters, numeric literals, its own module's
> items, and `COMPTIME_HELPERS` items. Anything else must be inlined as a literal and pinned with a
> module-level `ensure`.**

This is not stylistic. A comptime fn's free names resolve at the **call site**, and in struct-literal
position a missing import degrades **silently to a label reference** — the value compiles, the build is
green, and the emitted word is an address. If a constructor body spelled `OP_CRAM`, then every author's
module would have to import `engine.effects.raster`'s constants or get `unknown name` (or worse, the
silent degradation). Inlining the number and pinning it with a co-located `ensure` keeps a single source
of truth without imposing that on callers.

The established pattern is `water_arm0` (`raster.emp:587-597`): the body spells `3` and `223`, and the
`ensure` immediately below asserts `RASTER_MIN_FIRE_LINE == 3 && RASTER_MAX_FIRE_LINE == 223`. The pin
is what makes the inlining safe; an inline without its pin is just a magic number.

Two corollaries:

- `vdp_comm` / `VdpTarget` / `VdpOp` **are** safe to name in a body, because `engine.vdp` is itself a
  `COMPTIME_HELPERS` member and is glob-injected at every call site.
- Wire-format **struct type names** (`pal_variant`, `PalCycleScriptN`, `RasterGradientProgram`) live in
  byte-emitting modules, which can never be `COMPTIME_HELPERS` members. So for those, the import at the
  *emission* site remains a discipline rule that no mechanism enforces.

Adding a module to `COMPTIME_HELPERS` also force-publicizes its **private** comptime items and injects
one glob per helper in list order, where the later helper silently wins a duplicate name. Run
`python3 tools/emp_helper_closure.py` before and after any such change; it fails on any name exported by
two helpers.

---

## References

- `engine/effects/raster.emp` — the runtime decoder, the timing model (`:24-45`), the opcode set
  (`:87-143`), `pal_stage_off` (`:112-117`), the P1 sparse authoring helpers (`:197-213`), the dense tier
  (`:244-286`), the water patch slot (`:572-597`).
- `games/sonic4/data/parallax/configs.emp:284-459` — the shipped fixtures this vocabulary must reproduce.
- `docs/superpowers/specs/2026-08-13-effects-p3-design.md` §4.1, §4.4, §5.4, §6.1, §8.1 — and §1,
  where rulings 5 (constructor-guaranteed correctness) and 14 (`SET_REG` first) are stated. Those two
  are *design rulings*, not survey findings.
- `docs/superpowers/notes/2026-08-13-parcel-a-capability-probe.md` — what the `.emp` comptime layer can
  and cannot do, measured with negative controls.
- `docs/research/2026-08-12-raster-hint-survey.md` — Ruling 1a (`:34-40`), Ruling 1b (`:41-61`),
  Rulings 2a/2b (`:83-89`), and the manual's fire-line-vs-affected-line statement (`:29-33`). The origin
  of the arm schedule and of the cycle budget.
