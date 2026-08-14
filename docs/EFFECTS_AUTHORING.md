# Effects Authoring — the Phase-3 raster and palette vocabulary

**This is the standing authoring reference** for the sparse raster tier (`engine/effects/raster_dsl.emp`)
and the palette variant system it reaches into (`engine/effects/palette.emp`,
`engine/effects/palette_dsl.emp`). Read it before writing a raster program.

**Provenance.** This document was written *before* the code it describes, deliberately. Spec §4.1
required Parcel A to open with a vocabulary table, because "the byte-compare gate is only winnable if
the vocabulary can express every word already in the tree" — a vocabulary specified against words that
already existed can be proved by byte-compare instead of by taste. Parcel A then shipped
(`f406d50b`), the two shipped raster programs were re-expressed through the vocabulary **byte-for-byte
in place**, and all **seven golden ROMs came out identical with no rebaseline**
(`docs/superpowers/notes/2026-08-13-effects-p3-parcel-a-evidence.md` §1). The spec-first order is
recorded because it is the method to hold anything built on top to, not because the doc is still ahead
of the code — it is not.

Source of truth for the runtime side is `engine/effects/raster.emp` — the decoder. This document owns
the **encoding**; that module owns only the decoding. Where the two disagree, the ROM is the arbiter and
one of them is wrong.

**Line citations were re-derived against commit `2dd5e35c`** ("fix(effects): close four review defects
in the raster DSL and add vsram()") by opening every cited file at that commit. Cited symbols are named
alongside their lines so a citation that drifts is still followable. Citations have drifted twice in
this parcel's lifetime; if you edit a cited file, re-measure the citations *after* your last edit to it.

**Three words this document uses precisely.**

- **Fire line** vs **screen line.** A *fire line* is where HInt fires; a *screen line* is where the
  author wants the effect to appear. For the sparse tier they differ by one: `fire line = screen line - 1`.
  Every constructor takes screen lines. Nothing here is ever called an "event line".
- **Fixture.** One of the two shipped sparse programs, `OJZ_TestRaster`
  (`games/sonic4/data/parallax/configs.emp:375`) and `OJZ_WaterRaster` (`:491`). They are shipped
  content *and* the parcel's test artifact at once — that double role is why the word turns up in both
  senses, and both are meant.
- **Template.** A program that is copied into `Raster_Buf_B` and then has one of its words rewritten at
  runtime (the water route below). A template is an ordinary program; the word only marks that
  something patches it live.

---

## What the DSL is for

Before Parcel A a raster program was a hand-laid `[u16; N]` with a hand-counted length, a hand-computed
VDP timer arm word, a CRAM command hand-split into two literal hex words, a hand-written `count-1`, and
a `pal_dirty_mask` the author had to know to type. The retained hand-word twins still show exactly that
shape — `OJZ_TEST_HAND` (`configs.emp:359-369`) and `OJZ_WATER_HAND` (`:474-485`). Every one of those is
a place where a correct program and a silently wrong program look the same on the page; the
`%0001`-instead-of-`%0100` mask bug that made P1's red cover the whole ground instead of just the region
below the split (recorded at `configs.emp:343-345`) is the observed instance.

The vocabulary's goal is that an author adds a water section by naming a screen line, a palette region
and a variant slot — **without typing a VDP register word, an arm word, a CRAM command, a `count-1`, a
dirty mask, or a word count** — and that the classes of mistake listed under "New correctness the
constructors guarantee" become unrepresentable rather than merely discouraged.

---

## The authoring shape

Two declarations. A variable-length value cannot be a struct field, so the program is its own `pub data`:

```
const WATER_PROG = [ region_boundary(line: 120, addr: $48, slot: 0, pal_line: 2,
                                     entry: 4, count: 3, sh: 1) ]

pub data Water_Prog: [u16; raster_words(WATER_PROG)] = raster_program(WATER_PROG)
```

The length annotation must sit on the `data`. **`const` does not enforce its declared array length; only
`data` does** — probed and measured on this tree, `docs/superpowers/notes/2026-08-13-parcel-a-capability-probe.md`
(the "Step 6" negative control).

That is the whole recipe. Everything below is either the descriptor set you fill it with, the model the
descriptors encode, or the guards that catch you.

---

## Descriptor set

Signatures and bounds below are read from `engine/effects/raster_dsl.emp` at `2dd5e35c`, not inferred.

| Constructor | Parameters | Emits | `op_size` |
|---|---|---|---|
| `set_reg(word, reset)` (`:88-111`) | `word` = mid-frame `$8xxx` VDP register write, `$8000..$97FF`; `reset` = the frame-top word restoring the **same** register. Reg `$0A` is refused — it is the schedule's | `OP_SET_REG, word` | 2 |
| `sh_on()` (`:116-118`) | none | `set_reg($8C89, $8C81)` — Shadow/Highlight ON **starting at the landing line M** (the fire is at M-1, so the register write takes effect from M), H40 base restored at frame top (`engine/system/boot_data.emp:140`) | 2 |
| `cram(addr, colours)` (`:121-131`) | `addr` = CRAM **byte** address 0..126, even, not on line 0; `colours` = 1..3 colour words, inline; `entry + colours.len <= 16` | `OP_CRAM, cmd>>16, cmd&$FFFF, colours.len-1, <colours>` | `4 + colours.len` |
| `pal_region(addr, slot, pal_line, entry, count)` (`:136-152`) | `addr` = destination CRAM byte address; `slot` 0..1, `pal_line` 1..3, `entry` 0..15 = the `Pal_Variant_Stage` source; `count` = 1..3. `addr` must agree with `pal_line`/`entry` | `OP_PAL_REGION, cmd>>16, cmd&$FFFF, count-1, slot*128 + pal_line*32 + entry*2` | 5 |
| `vsram(addr, values)` (`:186-195`) | `addr` = VSRAM **byte** address 0..78, even; `values` = 1..3 scroll words, inline; `addr + 2*values.len <= 80` | `OP_CRAM, cmd>>16, cmd&$FFFF, values.len-1, <values>` — the same opcode with a **VSRAM** command longword | `4 + values.len` |
| `fire(line, ops)` (`:203-249`) | `line` = screen line 3..223 the effect lands on; `ops` = 1..4 descriptors, at most 2 of them CRAM-class, at most 3 CRAM-class words total | one record: `arm, ops.len, <bodies>` | `2 + Σ op_size` |
| `region_boundary(line, addr, slot, pal_line, entry, count, sh)` (`:264-271`) | thin composite. **`sh` is required — deliberately no default**, see below | `fire(line, [sh_on(), pal_region(…)])` when `sh == 1`, else the region alone | as above |
| `raster_words(fires)` (`:477-487`) | descriptor array | the word count, computed from `op_size` — **independently of** `raster_program`'s concatenation | — |
| `raster_program(fires)` (`:491-519`) | descriptor array | the flat `[u16]` | — |

`cmd` is `vdp_comm(addr, VdpTarget.Cram, VdpOp.Write)` — or `VdpTarget.Vsram` for `vsram`. `vdp_comm` is
a `COMPTIME_HELPERS` member and is therefore glob-injected at every call site, so naming it inside a
constructor body is safe.

The opcode values themselves (`OP_SET_REG = 0` at `raster.emp:87`, `OP_CRAM = 2` at `:88`,
`OP_PAL_REGION = 4` at `:116`, `OP_RUN_GRADIENT = 6` at `:141`); `RASTER_OPS_END = $FFFF` at `:145`,
`RASTER_ARM_PARK = $8AFF` at `:149`, `RASTER_CRAM_MAX = 3` at `:155`, `RASTER_BUF_SIZE = 128` at `:190`,
`RASTER_MIN_FIRE_LINE = 3` / `RASTER_MAX_FIRE_LINE = 223` at `:586-587`. `raster_dsl` inlines them all as
literals and pins each with a module-level `ensure` (`raster_dsl.emp:33-48`) — see "The discipline rule"
for why.

### `vsram` — per-band vertical scroll, and what is not yet known about it

`vsram` is the newest constructor and the only one that reaches a capability the engine did not
otherwise have: Aeon has **one vertical scroll factor for the whole BG plane and no vertical banding at
all** without it.

It needed **zero runtime change**, and that is a fact about the decoder rather than luck.
`Raster_HInt`'s `.op_cram` path (`raster.emp:461-473`) does `move.l (a1)+, (a2)` with *whatever command
longword the program carries* and then streams `count` words to `VDP_DATA`; it never inspects the target
bits. The only thing that ever made those ops CRAM ops was `cram`/`pal_region` hardcoding
`VdpTarget.Cram` in the encoder. So `vsram` emits `OP_CRAM` with a VSRAM command instead.

VSRAM is 80 bytes = 40 word entries. In per-column vertical scroll mode entry `2n` is plane A and
`2n+1` is plane B for the n-th 16-pixel column; in full-screen mode only entries 0 and 1 are read.

> **UNMEASURED — content must not rely on the exact landing line.** Whether a VSRAM write issued from
> the HInt handler first takes effect on line **N+1** or **N+2** has never been run. The VDP latches the
> next line's render state ~36 cycles after HInt asserts while the 68000 needs ~44 cycles just to reach
> the handler; CRAM and reg `$07` are unlatched and apply to N+1, which is what the whole
> screen-line = fire-line + 1 rule encodes — but VSRAM may be latched. **Sources conflict and emulators
> differ.** The constructor therefore ships with the same screen-line semantics as `cram` and says so at
> `raster_dsl.emp:171-185`. Booked in `docs/DEFERRED_WORK.md:1899-1902`; it wants an oracle measurement
> (author a `vsram` fire at a known line, screenshot, read where the scroll discontinuity actually
> falls). If it measures as N+2 **the fix belongs in this constructor's line arithmetic** — schedule the
> fire a line earlier, or carry a per-op line bias into `fire_lines` — never in the handler.
> Target-agnosticism is the property that made the op free and it must stay.

`op_mask` returns **0** for a VSRAM op, and that is deliberate rather than an omission: a VSRAM op
writes no palette, so there is no CRAM line to re-assert at frame top. Deriving `1 << (addr >> 5)` from
a scroll offset is nonsense in general, and at VSRAM offset 0 it would yield bit 0 — the *character's*
CRAM line — forcing a spurious full re-assert of the character palette every single frame, silently
(`raster_dsl.emp:349-354`).

### Why `sh` has no default

`region_boundary`'s `sh` is a **required** parameter. A `= 0` default would be the ordinary, friendly
choice and it is the wrong one here, because `sh: 0` is the *dangerous* value:

`sh: 0` produces a program with **zero** init words (nothing contributes a frame-top reset), which moves
the priming arm word from word 3 to word 2. But `Raster_PatchWaterLine` writes
`WATER_TEMPLATE_ARM0_OFF = 6` (`raster.emp:573`) — byte offset 6, i.e. **word 3** — unconditionally, at
all three of its exit paths (`raster.emp:647`, `:656`, `:659`). On a patched template that write lands on
a priming record's `op_count` instead of its arm word, and `Raster_HInt` then does `subq.w #1` on a value
that was never a count (`raster.emp:440`).

That number is exactly computable rather than a vague "tens of thousands". **Derived** for the shipped
water template: the patched word is the arm word `$8A75`, `subq.w #1` leaves `$8A74`, and `dbf` runs the
op loop `$8A74 + 1` = **35,445 times**, walking 35,445 words of adjacent ROM as opcodes inside a raw
interrupt handler.

A default would have made that the outcome an author gets by *not thinking about Shadow/Highlight at
all* — the failure would be reached by omission. Requiring the parameter forces the thought. It is not
a complete guard on its own; see the `init_count` pairing under "What the vocabulary does NOT check".

### Deviation from the spec's sketch, recorded so it is not silent

Spec §4.1 sketches `region_boundary(line:, variant:, sh:)`. That signature presumes a **preset binding
that does not exist until Parcel C** — there is no `variant:` handle to name yet. Parcel A therefore
shipped the primitives (`fire`, `set_reg` / `sh_on`, `cram`, `pal_region`, `vsram`) plus a
`region_boundary` whose parameters are the ones `OJZ_WaterRaster` actually needs. Parcel D re-shapes the
signature once it knows the pack. This is a deviation from a spec *sketch*, not from a ruling.

---

## Walking a new effect end to end

Every worked example elsewhere in this document re-derives a fixture that already existed. This one does
not: it is the path every future program takes. The effect is a "dusk band" — below screen line 96, swap
CRAM line 1 entries 8-10 to a dusk-tinted variant, with no Shadow/Highlight.

**1. Pick the palette entries, and derive the CRAM byte address.** CRAM line 1 starts at byte
`1 * 32 = 32`; entry 8 is `+ 8 * 2 = 16`. So `addr = 48 = $30`. (You supply this *and* the
`pal_line`/`entry` pair; `pal_region` checks your arithmetic rather than doing it. That is the
vocabulary's largest remaining friction and it is named as such in the 2026-08-14 review §6.)

**2. Write the program.** In the game-side effects library, `games/sonic4/data/parallax/configs.emp`:

```
const DUSK_PROG = [
    fire(96, [ pal_region(addr: $30, slot: 1, pal_line: 1, entry: 8, count: 3) ]),
]

pub data OJZ_DuskBand: [u16; raster_words(DUSK_PROG)] = raster_program(DUSK_PROG)
```

No `use` line is needed — `raster_dsl` is ambient (see "Reaching the ROM"). Nothing else is typed: the
arm word, the CRAM command, the `count-1`, the staging offset, the `pal_dirty_mask` and the length are
all derived. Self-check if you want one: 2 header words + 0 init words + 4 priming + (2 + 5) + 2
terminator = **15 words**, and the single event at screen line 96 gives arm `$8A00 | (96 - 3)` = `$8A5D`.

**3. Bind a variant to the slot the program names.** A `pal_region` streams from
`Pal_Variant_Stage[slot]`, which is empty until something binds a descriptor to that slot. At level init:

```
moveq   #1, d0                  // slot 1 — the slot DUSK_PROG names
lea     Variant_Dusk, a0        // one of the five starters, palette.emp:780
jbsr    Palette_SetVariant
```

`Variant_Dusk` is `variant(shift_b: 1, bias_r: 1)` and its `lines` defaults to `%1110`, so it covers
line 1. **If it did not, nothing would catch you** — see the uncovered-line hole under the variant
section.

**4. Point a section at it.** In `games/sonic4/data/levels/ojz/act1/act_descriptor.emp`, the `ojz_sec`
wrapper (`:137`) takes a `raster:` argument that lands in `Sec.sec_raster_table` (`engine/structs.emp:117`),
exactly as section 1 already does for `OJZ_TestRaster` (`act_descriptor.emp:176`):

```
    ojz_sec(blocks: OJZ_Sec4_Blocks,
            …
            raster: OJZ_DuskBand),
```

**5. See it.** On a boundary crossing `Parallax_CheckBoundary` (`engine/level/parallax.emp:154`, calls at
`:185-186`) invokes `Raster_InstallSection` (`raster.emp:545-555`), which stages the pointer; the next
`Raster_VBlank` (`:323-372`) copies 128 bytes into `Raster_Buf_A`, applies the init words, and leaves
reg `$0A` = 0 so the pipeline primes on lines 0 and 1. Screen lines 0-95 show the base palette; from 96
down, entries 8-10 of line 1 carry the dusk-derived colours, and the base is restored at the next frame
top because `pal_dirty_mask` re-asserts line 1 every frame.

Confirm it the way the dense gate did, not by eyeballing a screenshot: oracle `run_to_scanline` +
`read_cram` above and below line 96 answers "did the handler write the authored word on the authored
line" directly, and cannot be confounded by art coverage.

**6. Turning it off.** Crossing into a section whose `sec_raster_table` is 0 **keeps the program** —
NULL means "keep current", not "no effects". A section that must kill a neighbour's effect points at
`Raster_Program_None` (`raster.emp:560`), an explicit empty program.

---

## Scope — what is and is not authorable in Phase 3

**Sparse tier only.** The general constructors (`raster_words` / `raster_program`) cover the sparse tier:
a schedule of per-scanline VDP work in which HInt fires only on the scheduled fire lines.

**The dense tier keeps `raster_gradient_program`** (`raster.emp:262-287`) and is not folded into the
general constructor. The reason is structural, not stylistic: a dense run carries a **link-time ROM
stream pointer** (`rgp_stream: *u8`, `raster.emp:255`) and a `[u16; N]` literal array cannot hold a
symbol address at any spelling. So the dense tier stays a `struct` built by its own constructor, and
`OJZ_TestGradient` (`configs.emp:536-541`) keeps using it.

**A program mixing sparse events with a dense run is NOT authorable in Phase 3** (spec §4.1). The wire
format *permits* it — `Raster_HInt`'s `.op_run_gradient` falls through to `.advance`
(`raster.emp:496-509`), and the LEAVE schedule (`raster.emp:420-426`) explicitly discusses "the first
post-gradient sparse event". Neither constructor can author that combination, and neither is being
extended to. **A section takes one tier or the other.** If a future pack member needs the mix, that is a
design change to raise, not something to assemble by hand-editing a program array.

---

## Palette variants — what `pal_region` reaches into

`pal_region`'s `slot` / `pal_line` / `entry` are not raster concepts; they are coordinates into the
palette system's staging buffer. You cannot author a *new* variant effect without this model.

**A variant is a cheap per-channel transform of the live composed palette.** Per channel:
`clamp((c >> shift) + bias, 0, 7)`. A Genesis colour word is `0000 BBB0 GGG0 RRR0`, three bits per
channel, so `shift` is 0..3 and `bias` is -7..+7 — both validated at build time
(`palette_dsl.emp:32-49`). The descriptor is the 8-byte `pal_variant` struct (`palette.emp:126-132`) and
`lines` is a bitmask of CRAM lines 1-3; line 0 is refused, because it is the character's
(`CharacterDef.cd_palette`). Five starters ship at `palette.emp:776-780`.

**It transforms the LIVE palette, which is why it never goes stale.** `Palette_Compose` runs one
deterministic order per frame — base → cycling → cross-fade → global operators → **variants**
(`palette.emp:33`) — so a variant derived at the end sees whatever the layers above it produced. There
is no snapshot to invalidate.

**A slot is one of `PAL_MAX_VARIANTS` = 2 staging images.** `Palette_SetVariant`
(`palette.emp:272-288`) binds a `pal_variant*` to slot 0 or 1 (or clears it with `a0 = 0`). While a slot
is bound, `Palette_DoVariants` (`palette.emp:681-697`) calls `Palette_DeriveVariant` (`:709-771`) once
per frame, writing the transformed colours into `Pal_Variant_Stage` — **128 bytes per slot, a 4-line
image, each line at its natural `line * 32` offset.** Only lines named in `v_lines` are written.

`PAL_MAX_VARIANTS` cannot be raised past 2 without a fix first: `Palette_SetVariant`'s
`andi.w #(PAL_MAX_VARIANTS - 1), d0` (`palette.emp:273`) is a power-of-two mask, so 3 would silently fold
slot 2 onto slot 0. `palette_dsl.emp:125-126` pins that.

**The derive is gated, and the gate is a measured win.** It runs only when `PAL_ACT_VARIANT_STALE`
(`palette.emp:115`) is set — that is, when a bound slot's *source* actually moved (`:411-413`). The
derive is a pure function of (descriptor, `Palette_Buffer[v_lines]`), so skipping it on an unchanged
frame yields the *same answer*, not an approximation. Measured before the gate on `OJZ_ScrollTest`:
19332 cyc/frame = **15.1% of every frame**, larger than the whole sparse raster tier, entirely spent
recomputing a constant.

**`pal_region` is the raster side of that buffer.** It carries a comptime *offset* —
`slot*128 + pal_line*32 + entry*2`, the arithmetic `raster.emp:124-129`'s `pal_stage_off` owns and
`raster_dsl.emp:47-48` pins itself against — and the handler (`raster.emp:474-495`) streams `count`
words from `Pal_Variant_Stage + offset` to CRAM. An offset rather than a pointer is what keeps a sparse
program a flat `[u16]` of comptime literals with no link-time symbol in it.

So the three-part model is: **`variant()` describes the transform, `Palette_SetVariant` binds it to a
slot and the compose derives it each frame, and `pal_region` scopes it to a screen band.** Nothing about
the variant itself knows about scanlines; nothing about the raster program knows about colour maths.

**The hole to know about:** nothing cross-checks `pal_region`'s `pal_line` against the bound variant's
`v_lines`. If the variant does not cover that line, `Palette_DeriveVariant` never writes those staging
bytes and `OP_PAL_REGION` streams **uninitialised RAM straight to CRAM mid-frame**. Safe today only
because `variant()`'s `lines` defaults to `%1110`. (2026-08-14 review §5, ARGUED — reasoned from the
code, not reproduced.)

**Cycling is a different mechanism on the same palette.** `cycle_channel` / `cycle_script1` /
`cycle_script2` (`palette_dsl.emp:87-118`) rotate spans of CRAM entries *in place* each period, installed
per section through `Sec.sec_pal_cycle` (`engine/structs.emp:120`) by `Palette_InstallCycleSection`
(`palette.emp:324`). Cycling needs no raster program at all — it is a whole-screen effect. It composes
*before* variants, so a variant derived afterwards sees the rotated colours. Variants transform, cycling
permutes; the raster tier is how either one becomes scoped to a band.

---

## Reaching the ROM: what to import, and how a program gets installed

**Imports — there are none, and that has a cost.** `engine.effects.raster_dsl` and
`engine.effects.palette_dsl` are members of sigil's `COMPTIME_HELPERS`, so every `pub` item in them —
`fire`, `cram`, `set_reg`, `sh_on`, `vsram`, `pal_region`, `region_boundary`, `raster_words`,
`raster_program`, `variant`, `cycle_channel`, … — is **ambient in every module**. No `use` is required
to call them, and `normalize_helper_imports` strips an explicit helper `use` at build time anyway.
Writing one regardless is the house convention where it documents a seam worth naming
(`raster.emp:14`'s `use engine.structs.{Sec}` is exactly such a line: `engine.structs` is itself a
helper; `configs.emp:64`'s glob with its do-not-prune comment at `:52-63` is another).

What you **must** still import by hand are the wire-format **struct type names** from byte-emitting
modules — `RasterGradientProgram`, `pal_variant`, `PalCycleScriptN` — because those modules emit bytes
and therefore can never be helpers.

**Helper membership also force-publicises a module's PRIVATE comptime items.** That is a real
consequence, not a footnote, and it is why the four internal helpers below are described as *internal by
convention* and not as private: `op_size`, `op_cram_words`, `op_mask`, `op_init`, `op_words`,
`op_is_set_reg`, `prog_mask`, `prog_init`, `fire_lines`, `arm_at` and `check_mixed_fire` are all
**ambient names in every module in the tree**, whatever their declared visibility. An author never calls
them; nothing stops one.

The practical consequence for *you*: this parcel injected roughly twenty short generic names — `fire`,
`cram`, `set_reg`, `vsram`, `variant`, `op_size`, `op_mask`, `op_init`, `op_words`, … — into every
module. **Do not shadow them with a module-local name.** `python3 tools/emp_helper_closure.py` catches
helper-vs-helper collisions and fails on any name exported by two helpers; it does **not** catch a
collision against a module-local name. Run it before and after any change to the helper list; it also
prints the current set's size, which is the honest way to enumerate the helpers rather than a count
copied into prose (it reported 426 names across 14 helpers at `2dd5e35c`).

**Install.** A compiled program is inert data; something has to point the runtime at it. Three routes:

1. **Per-section (the normal one).** Point the section's `Sec.sec_raster_table` (`engine/structs.emp:117`)
   at your `pub data`. `Raster_InstallSection` (`raster.emp:545-555`) consumes it on a boundary
   crossing, from `Parallax_CheckBoundary` (`engine/level/parallax.emp:186`). NULL means "keep the
   current program", *not* "no effects" — a section that must turn a neighbour's effect **off** points
   at `Raster_Program_None` (`raster.emp:560`), an explicit empty program. Raster programs snap; they
   are never lerped across a boundary.
2. **Imperative.** `Raster_Install` with `a0` = the program (`raster.emp:295-298`). The install is
   *staged* and consumed at the next `Raster_VBlank`, so it can never tear a frame mid-walk. Main-loop
   context only.
   **`Raster_Clear` (`raster.emp:303-307`) does not work and this document previously claimed it did.**
   It stores 0 into `Raster_Pending`, which `Raster_VBlank`'s `beq.s .no_install` (`:325`) reads as
   "nothing pending" — so `Raster_Install`'s documented "0 = clear/uninstall" convention is
   **unreachable**, HInt is never disarmed, and `HBlank_Uninstall`'s only reference in the tree is the
   dead branch at `:330`. Verified in the 2026-08-14 review §1.3 and **unfixed at this commit**; both
   procs have zero callers, so it is latent. Use `Raster_Program_None` to turn effects off.
3. **Runtime-patched (the water route).** `Raster_InstallWater` with `a0` = the template and `d0.w` =
   the screen line (`raster.emp:597-613`) copies the program into `Raster_Buf_B` and makes it live; then
   call `Raster_PatchWaterWorldY` once per frame (`:673-678`) to keep the boundary anchored to a **world
   Y** as the camera moves, which is what makes the effect stay on a place in the level rather than at a
   fixed height on the display. `Raster_PatchWaterLine` (`:639-661`) does the actual one-word arm
   rewrite and owns the two off-screen semantics (above the viewport = fully submerged, fire as early as
   possible; below it = park). **This is the route carrying the `init_count == 1` invariant** described
   under "What the vocabulary does NOT check".

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
| `ensure(out.len == raster_words(fires))` **inside** `raster_program` (`raster_dsl.emp:516-517`) | header/record **framing** drift between the two independent computations (`op_size` path vs `op_words` concatenation path) — this is the instance that fires first on genuine framing drift | a wrong word *value* inside a correctly-sized body |
| `data X: [u16; raster_words(P)] = raster_program(P)` | that the declared length was computed by the size path over **the same** descriptor list the body was built from — i.e. an annotation naming a different program, or a hand-typed literal length going stale. `data` hard-checks element count (probe-measured) | a wrong word value; and note it re-checks a fact `raster_program` already asserted internally, so it is a second lock on the same door rather than a wholly independent one |
| The same annotation on a `const` | **nothing** — measured vacuous on this tree (probe note, Step 6). Put length guards on `data`, or assert with an explicit `ensure` on `.len` | everything |
| The retained hand-word twin + its `first_mismatch` ensure (`configs.emp:370-373`, `:486-489`) | any word-value drift in the two shipped fixtures, reported as "DSL output diverges at index *n*" rather than "golden ROM differs" | a fixture the twin does not cover; a **length** difference unless the paired `.len` ensure is also present (see below); and it pins the DSL to the *hand words*, so a shared misunderstanding of the hardware would satisfy it |
| Seven golden ROMs | every emitted byte, everywhere | nothing — **this is the parcel's real bar** |

Writing `data X: [u16; P.len] = P` instead would be **tautological** and is forbidden: the annotation
and the value would be two readings of one computation, so it cannot fail for any reason that matters.
It is the `gate-measures-the-placer` failure one layer up.

### What the vocabulary does NOT check (know these before authoring)

Stated plainly rather than left for someone to discover on hardware:

- **`first_mismatch` returns -1 when `a` is a PREFIX of `b`, so it MUST be paired with a `.len` ensure.**
  Its precondition is documented at `raster_dsl.emp:527-534` and was previously absent from this page.
  It walks only `a`'s indices and skips any index past the end of `b` — so a DSL program that is **short
  by a trailing record compares EQUAL to its hand-word twin**. Nothing inside the function can see that;
  only a length check can. Both shipped fixtures pair it correctly (`configs.emp:370-373`, `:486-489`);
  copy that pairing, do not copy only the `first_mismatch` line. (The chain happens to hold one rung
  deeper here, because `raster_program` asserts `out.len == raster_words(fires)` on every call — but that
  is a fact about `raster_program`, not about `first_mismatch`, and a caller must not rely on it.)
- **The patched-water template's `init_count == 1` requirement — not by the vocabulary.**
  `WATER_TEMPLATE_ARM0_OFF = 6` (`raster.emp:573`) is a byte offset that is only correct when the header
  carries exactly one init word: with `N = 1` the layout is `[mask 0][init_count 2][init[0] 4][arm0 6]`,
  but with `N = 0` offset 6 lands on `op_count` and with `N = 2` `arm0` moves to offset 8 (so the patch
  would rewrite an *init word* every frame instead of the boundary). Because `raster_program` **derives**
  the init words from the ops, a patched template's init count is a consequence of how many *distinct*
  `set_reg` reset words the program happens to use. Two things mitigate it and neither is a general
  guard: `region_boundary`'s `sh` is required, so the zero-init case cannot be reached by omission; and
  the water fixture carries a **co-located** `ensure` (`configs.emp:466-468`) that word 3 of its own
  compiled program is the expected priming arm word. **If you author any other program destined for the
  water patch slot, write that assertion yourself** — nothing in `raster_dsl` knows a program is going
  to be patched. Note also that a `sh: 0` region boundary needs *some* `set_reg` to manufacture the init
  word at all; a no-op pairing such as `set_reg($8C81, $8C81)` is the escape hatch.
- **Nothing checks a `pal_region` against the bound variant's covered lines.** See the palette variant
  section: an uncovered line streams uninitialised staging RAM to CRAM.
- **Parameter type annotations.** They are mandatory to parse but mostly not enforced: `[T; N]` on a
  parameter is *not* a checked length (a 4-element list binds to an `[int; 3]` param), which is why
  loose list params are spelled `array` and length checking is done with explicit `ensure`s on `.len`.
  The same applies inside the descriptor enum: `RasterOp.Cram(addr, 5)` binds an int to the `array`
  slot without complaint, and the build only fails downstream at the first `.len` or `++`
  (`raster_dsl.emp:50-60`). `Reg` and `Label` **are** class-checked by exact spelling, on explicitly
  supplied args only — do not strip a `Label` annotation as decorative. All measured; see the probe note.
- **Reachability of a non-helper comptime module.** A pure-comptime module's `ensure`s do not *pass*
  when nothing imports it — they are **never evaluated at all**, with no diagnostic and a green build.
  That hazard applied to `raster_dsl` before it joined `COMPTIME_HELPERS`, which is why
  `configs.emp:64` carries a `use engine.effects.raster_dsl.*` glob with a do-not-prune comment
  (`:52-63`). Membership in the helper list removes the hazard for these two modules; it remains live
  for any *new* pure-comptime module that is not a helper.

---

## New correctness the constructors guarantee (ruling 5)

- **`set_reg`**: the mid-frame word and its frame-top reset must target the **same** VDP register — so a
  mode change can never latch past the frame. The reset is not optional and is not typed separately into
  a header; `raster_program` derives the program's init words from these resets, so an author cannot
  write the mid-frame half alone.
- **`set_reg` refuses reg `$0A`.** That register is the *schedule's*. `Raster_HInt` writes the record's
  arm word to reg `$0A` **first** and only then runs the record's ops (`raster.emp:436` before `:442`),
  so an op writing `$8Axx` would overwrite the arm the encoder just scheduled; the counter then reloads
  with the author's value at the next HInt and every remaining fire in the frame lands on the wrong line
  — silently, and only from that fire onward. Reg `$0F` (autoincrement) was considered and **deliberately
  not** banned: Gunstar Heroes and Alien Soldier both change autoincrement mid-frame as ordinary
  technique, and the mandatory frame-top reset already bounds the change to the frame that made it
  (`raster_dsl.emp:95-109`).
- **`pal_region`**: the destination CRAM address must name the **same line and entry** as the staging
  source (`(addr >> 5) == pal_line` and `((addr >> 1) & 15) == entry`). Hand authoring had no such check
  — the two were independent literals.
- **`pal_dirty_mask` is derived** from the CRAM addresses rather than typed. A mask naming the wrong
  line is the observed P1 bug (`configs.emp:343-345`); it is now unrepresentable.
- **Palette line 0 is refused.** `cram` rejects an address on CRAM line 0 and `pal_region` bounds
  `pal_line` to 1..3. Line 0 is the character's (`CharacterDef.cd_palette`); a raster write there
  repaints the active character.
- **`raster_program`**: `words * 2 <= RASTER_BUF_SIZE` (spec §10 rider 4, `raster_dsl.emp:514-515`).
  `Raster_VBlank` (`raster.emp:336`) and `Raster_InstallWater` (`:602`) both copy a **fixed 128 bytes**,
  so a longer program would be truncated live. The converse over-read of a *short* template is
  pre-existing and harmless — the walker never reaches past the terminator — and is booked as **EFX-4**
  in `docs/BUGS.md:79`, where Parcel A is recorded as closing the overflow half and the over-read half
  stays open.
- **Three per-fire ceilings, and they are counts rather than cycles.** `fire` (`raster_dsl.emp:207-247`)
  enforces exactly three things:

  | Ceiling | Value | Why that quantity |
  |---|---|---|
  | ops per fire | 4 | every op walks `Raster_HInt`'s compare chain before doing any work, and `OP_SET_REG` — the op with no other cost — is that chain's **fall-through** (`raster.emp:451-459`), so it is the most expensive op to *dispatch* |
  | CRAM-class ops per fire | 2 | each of `cram` / `pal_region` / `vsram` issues its own command longword **and** burns its own `EFX_BLANK_DELAY` spin (`raster.emp:465-467`, `:484-486`), and that spin is the entire mechanism that parks a write in HBlank. Only the **first** op's writes are measured to land there (row 119, 1px → 0px, `docs/benchmarks/effects-p2/GATE-EVIDENCE.md`) |
  | CRAM-class words per fire | `RASTER_CRAM_MAX` = 3 | the writes themselves; `op_cram_words` sums `cram`/`pal_region`/`vsram` alike, because a VSRAM word costs the same as a colour |

  The per-op bounds inside `cram` / `pal_region` / `vsram` are *necessary but not sufficient*: three
  3-word ops satisfy every per-op check.

  **What is still NOT enforced — read no cycle guarantee into the above.** These are **structural
  counts, not a cycle model**, and a cycle model was considered and rejected as unsound: the only
  measured figures in the tree (`docs/benchmarks/effects-p2/GATE-EVIDENCE.md`) are per-frame upper bounds
  that include profiler instrumentation and exception entry, so a per-op cycle table derived from them
  would be authoritative-looking fiction. The *cost* of a fire is not modelled at all — a 4-op fire of
  `set_reg`s and a 1-op fire of one `cram` both pass, and the first is certainly slower. Whether even
  the permitted maxima finish before active display is **unmeasured**: nothing in this tree has ever run
  more than two ops or more than one CRAM-class op in a single fire, and adjacent-fire density is
  unmeasured too. These ceilings bound the *damage* of a mistake; they do not certify the shapes they
  admit. (This paragraph replaces an earlier one that claimed a fire blowing the ~60-cycle budget had
  been made impossible. It had not: the guard then counted only CRAM words and scored `set_reg` as free,
  so a twenty-`set_reg` fire passed everything. 2026-08-14 review §1.2, VERIFIED.)

  The legitimate way to write more colours than the ceiling is **consecutive fires on successive
  lines** — a full 16-colour line takes `ceil(16/3) = 6` of them. **That six-fire idiom is OURS, not a
  reference's.** S3K's `HInt3` swaps a whole water palette in **one** interrupt: park the counter, stop
  the Z80, then repeat {fresh CRAM command, 3 colours, a cycle-counted ~370-cycle `dbf` spin} — the
  spacing that pushes the dots offscreen comes from the *spin*, not from multiple interrupts. S3K's
  `HInt2`, Sonic 2's `PalToCRAM` and S.C.E.'s `HInt` each write **64 CRAM words in a single fire with no
  delay at all**. Ours is dot-free by construction (single-ported CRAM, Ruling 2b) and pays six
  exception entries for that. An earlier revision of this document and of `fire`'s error message
  attributed the six-fire idiom to S3K; that was checked against the disassembly and is false.
  *(Density caveat: nothing has ever run **adjacent** fires on hardware. The only measured sparse figure
  is 8358 cyc/frame at ~4 fires/frame, non-adjacent. Six back-to-back fires wants an oracle measurement
  before content relies on it — 2026-08-14 review §9.)*
- **Fire ordering**: fires must be in strictly ascending screen-line order and no two events may share a
  fire line (`raster_dsl.emp:418-419`); the schedule *is* the program order, since the runtime never
  compares a line number.
- **Mixed fires**: every `OP_SET_REG` must precede every CRAM-class op (ruling 14, spec §5.4). Not a
  style rule. `OP_SET_REG` writes with no delay (`raster.emp:457-459`) while every CRAM-class op first
  burns `EFX_BLANK_DELAY` (`:465-467`, `:484-486`), so a `SET_REG` placed *after* a CRAM op executes
  strictly later in the line — worse than the measured ~45%-across-line-119 mode switch a mixed fire
  already costs (`raster.emp:175-180`), and invisible to an author. A pixel-clean mode change must be
  scheduled a line earlier instead. The guard is a **prefix test** (`last_set < first_cram`,
  `raster_dsl.emp:465`); an earlier spelling tested only that *a* `SetReg` was first, which passed
  `[sh_on(), pal_region(…), set_reg(…)]` — the exact ordering the rule forbids — and then reported "it
  is at index 0", pointing at the one op that was fine.

---

## The program-size ceiling: how many events fit

`RASTER_BUF_SIZE` is **128 bytes = 64 words** (`raster.emp:190`), and both `Raster_VBlank` (`:336`) and
`Raster_InstallWater` (`:602`) copy exactly that many bytes. A program that does not fit is refused at
build time (`raster_dsl.emp:514-515`), but the message speaks bytes rather than "drop two fires", so
here is the arithmetic up front instead of discovered by overflowing.

```
total words = 2                    header: pal_dirty_mask + init_count
            + I                    one word per DISTINCT set_reg reset value
            + 4                    the two priming records
            + Σ over fires (2 + Σ op_size)
            + 2                    terminator
            <= 64
```

Fixed overhead is therefore `8 + I` — **9 words** for the ordinary case of one init word. What that
leaves, by fire shape:

| Fire shape | words per fire | init words | max fires |
|---|---|---|---|
| `region_boundary(…, sh: 1)` — the water shape | 9 | 1 | **6** |
| `fire(M, [cram(a, [c1, c2, c3])])` | 9 | 0 | **6** |
| `fire(M, [pal_region(…)])` | 7 | 0 | **8** (exactly 64 words) |
| `fire(M, [vsram(a, [v])])` | 7 | 0 | **8** |
| `fire(M, [set_reg(w, r)])`, resets all distinct | 4 | 1 each | 11 |
| `fire(M, [set_reg(w, r)])`, one shared reset | 4 | 1 total | 13 |

So **roughly 6-8 events for anything that writes colour**, and the ceiling is on the *program*, not on
the frame. Plan for six if your fires carry a mode change; if you need more bands than that, the answer
today is a different program per section, not a bigger buffer — `RASTER_BUF_SIZE` sizes two RAM buffers
and the `RASTER_STATE_SIZE` span guard (`raster.emp:196-198`) is its twin.

`docs/ENGINE_ARCHITECTURE.md:3493` claims "no limit on how many effects stack in a single frame". That
is false as stated; the limit is this one. Noted here rather than edited there.

---

## Encoding reference

Everything below is the model the constructors encode. An author who only writes programs can stop at
the previous section; read on when you are debugging emitted words, adding a constructor, or reviewing
someone else's arithmetic.

### Sparse program wire format

```
word 0            pal_dirty_mask          DERIVED — OR of (1 << (cram_addr >> 5)) over every CRAM-class
                                          op; 0 for a vsram op
word 1            init_count N            DERIVED — count of distinct frame-top reset words
words 2..2+N-1    init words              DERIVED — each set_reg op's reset word, first-appearance
                                          order, deduped
                  ---- records ----
record 0          arm, 0                  priming, fires on line 0
record 1          arm, 0                  priming, fires on line 1
record 2..k+1     arm, op_count, <ops>    one per authored fire, in ascending screen-line order
record k+2        arm, RASTER_OPS_END     terminator
```

This is the layout `Raster_VBlank` walks (header at `raster.emp:344-356`) and `Raster_HInt` dispatches
(`raster.emp:442-509`). `pal_dirty_mask` is OR'd into `Palette_Dirty` **every frame**
(`raster.emp:346-347`), which is what makes a mid-frame CRAM write transient: the base palette is
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

Past the end of `L` the arm parks at `$8AFF` (`RASTER_ARM_PARK`, `raster.emp:149`) — the next fire would
be 256 lines away, i.e. never within active display.

The `i+2` is not an off-by-one; it is the hardware. The VDP reloads its line counter from reg `$0A` *at
the instant of underflow*, before the 68000 executes a single handler instruction, so a write to `$8Axx`
from inside handler `i` is not consumed by the gap it is sitting in — it is consumed at fire `i+1` and
therefore schedules `gap(i+1 -> i+2)`. The full argument is at `raster.emp:24-40`.

**For a single-event program at screen line M this reduces to `$8A00 | (M - 3)`** — exactly what
`arm_at` produces for that case (`raster_dsl.emp:429-435`), which is what lets `OJZ_WaterRaster` come
out byte-identical and what `Raster_PatchWaterLine` (`raster.emp:645-646`) is the runtime twin of. Both
spell `RASTER_MIN_FIRE_LINE` (`raster.emp:586`) rather than a hand-synced 3.

The sparse authorities in the tree are `raster_dsl`'s `fire` (`raster_dsl.emp:203-249`), which enforces
the 3..223 screen-line range, and `fire_lines` / `arm_at` (`:413-424`, `:429-435`), which own the `-1`
and the arm schedule. `raster_arm` (`raster.emp:210-216`) survives in `raster.emp` for the **dense**
tier's schedule only — see the T-1 subsection below before borrowing anything from it.

### Worked check against both shipped fixtures

Both fixtures are one event at screen line 120, so `L = [0, 1, 119]` for both.

| | `OJZ_TestRaster` (`configs.emp:346-375`) | `OJZ_WaterRaster` (`configs.emp:438-491`) |
|---|---|---|
| record 0 arm | `$8A00 \| (119 - 1 - 1)` = `$8A00 \| 117` = **`$8A75`** ✓ shipped `$8A75` | same = **`$8A75`** ✓ derived by `region_boundary(line: 120, …)` |
| single-event form | `$8A00 \| (120 - 3)` = `$8A00 \| 117` = `$8A75` ✓ | `120 - 3 = 117` ✓ |
| record 1 arm | `i+2 = 3 = L.len` → park **`$8AFF`** ✓ | ✓ |
| record 2 arm | `i+2 = 4 > L.len` → park **`$8AFF`** ✓ | ✓ |
| word count | `2 + 1 + 4 + (2 + 2 + 5) + 2` = **18** ✓ declared `[u16; 18]` | `2 + 1 + 4 + (2 + 2 + 5) + 2` = **18** ✓ |
| `pal_dirty_mask` | CRAM `$4A` → `1 << ($4A >> 5)` = `1 << 2` = **`%0100`** ✓ | CRAM `$48` → `1 << 2` = **`%0100`** ✓ |
| CRAM addr decode | `$4A` → line `2`, entry `5` | `$48` → line `2`, entry `4`; the staging source `pal_stage_off(0, 2, 4)` separately evaluates to 72 |

Word-count breakdown, identical for both: 2 header words (`pal_dirty_mask`, `init_count`) + 1 init word
(`$8C81`) + 4 for the two priming records + 9 for the event record (2 for `arm`/`op_count`, 2 for the
`set_reg`, 5 for the CRAM-class op) + 2 for the terminator = 18.

**A coincidence to not read as a rule.** In `OJZ_WaterRaster` two different numbers are both 72
(`$48` — see the note at `configs.emp:473`). They are *not* the same quantity and they are not even in
the same address space:

- **72 decimal** is the `Pal_Variant_Stage` **RAM byte offset**, `pal_stage_off(0, 2, 4)` =
  `0*128 + 2*32 + 4*2`. It is the fifth word of staging line 2 in slot 0.
- **`$48` = 72** is the destination **CRAM byte address**, `2*32 + 4*2` — line 2, entry 4.

They agree here *only because the slot is 0*, which makes the `slot*128` term vanish. For slot 1 the
same region would stage from offset `1*128 + 2*32 + 4*2` = **200** while the CRAM address stayed `$48`.
`pal_region` checks that the two name the same *line and entry*, not that they are the same number.

**The verification method behind this table**, named rather than asserted: both fixtures carry a
`raster_words(PROG) == HAND.len` ensure and a `first_mismatch(raster_program(PROG), HAND) == -1` ensure
against literal hand-word twins (`configs.emp:370-373`, `:486-489`), so **every build re-proves the
words**; and Parcel A's seven golden ROMs came out byte-identical with no rebaseline. The table above is
that comparison written out, not a re-derivation from the plan.

### Dense tier only — the T-1 setup line (sparse authors can skip this section)

Nothing here applies to `fire` / `raster_program`. It is recorded so that no one carries it across.

The dense tier's setup record sits at screen line **T-1** for a run whose first stream line lands on T.
That number is **measured, not derived** — `raster.emp:237-244` records the measurement: the naive
derivation puts the setup at T-2, and on hardware that authored the whole run one line high (with
`top=96` the level boundaries came out at 107/119/131/143/155/167/179 instead of 108/120/.../180, a
uniform -1 across all seven). The dense path does not inherit the sparse -1 because entering the run
costs its own pipelined arm, which absorbs exactly one line.

The sparse tier's rule is different, and it rests on different evidence: an effect authored to land on
screen line M fires at **M-1** because a register write in the handler for fire line L affects line L+1
at the earliest. That is a **documented hardware rule** — the Sega manual's "the CPU can control the
display of the next line but not the line on which the interrupt occurs", plus hardware-verified sources
and the one corroborating disassembly (survey `:29-40`, Ruling 1a) — not a measurement taken against our
own code.

**Applying the dense off-by-one to sparse arithmetic fails the byte-compare in the most confusing
possible direction** — every word is plausible, the program assembles, the length matches, and the
effect is silently one line off. Two different facts, two different tiers. Do not carry one into the
other.

*(Known stale text, flagged not fixed: `raster.emp:418-419`'s ENTER comment still instructs "author the
`OP_RUN_GRADIENT` fire at `gradient_top - 2`", which is the rejected naive derivation. The shipped
constructor authors it at `top - 1` (`raster.emp:276`). 2026-08-14 review §1.4, VERIFIED.)*

### Four per-op quantities, deliberately distinct

The encoding asks four different questions of one op, and the answers are **not** interchangeable. This
is where a plausible-looking simplification does real damage: a `pal_region` occupies 5 wire words but
writes `count` colours, and a `set_reg` occupies 2 wire words but writes no CRAM at all — so counting
either one with the other's function silently mis-sizes a program or mis-budgets a fire.

| Helper | Answers | `SetReg(w, reset)` | `Cram(a, cols)` | `PalRegion(a, slot, pl, e, n)` | `Vsram(a, vals)` |
|---|---|---|---|---|---|
| `op_size` (`:316-323`) | wire words the op occupies | 2 | `4 + cols.len` | 5 | `4 + vals.len` |
| `op_cram_words` (`:330-337`) | **data words streamed to the VDP** — what `fire` sums against the per-fire ceiling | 0 | `cols.len` | `n` | `vals.len` |
| `op_mask` (`:344-356`) | the `pal_dirty_mask` bit the op needs re-asserted at frame top | 0 | `1 << (a >> 5)` | `1 << (a >> 5)` | **0** — deliberately; see the `vsram` note above |
| `op_init` (`:359-366`) | frame-top reset words the op contributes | `[reset]` | `[]` | `[]` | `[]` |

`op_size` feeds `raster_words`; `op_cram_words` feeds `fire`'s per-fire budget; `op_mask` and `op_init`
feed the header, OR'd and deduped-in-first-appearance-order respectively. A fifth,
`op_is_set_reg` (`:372-379`), feeds both the mixed-fire ordering guard and the CRAM-class op ceiling —
that split is the runtime's, not a taxonomy: `OP_SET_REG` is the one op that writes with no blanking
delay.

These are **internal by convention, not private** — helper membership makes them ambient names in every
module (see "Reaching the ROM"). An author never calls them; knowing they are distinct is what makes the
guarantee list readable.

---

## The discipline rule for anyone adding a constructor

> **A constructor's returned value may name only its own parameters, numeric literals, its own module's
> items, and `COMPTIME_HELPERS` items. Anything else must be inlined as a literal and pinned with a
> module-level `ensure`.**

This is not stylistic. A comptime fn's free names resolve at the **call site**, and in struct-literal
position a missing import does not error there — the bare name **degrades to a label reference**. What
catches it depends on the destination field's type, and the difference is worth knowing:

- **Integer-typed field** — caught at emit, by name: `[emit.type] expected an integer for u16, got
  label` (measured 2026-08-13 by pruning `RASTER_ARM_PARK` + `RASTER_OPS_END` from `configs.emp`; the
  measurement is recorded in that file's import block, `configs.emp:39-48`).
- **Pointer-typed field** — a label reference is well-typed, so emit accepts it and the reference
  becomes a data fixup. The catch is **deferred to link**, where it surfaces positionally rather than
  by name: `unresolved symbol … for fixup in section … at offset …`. Comptime constants lower to zero
  link symbols, so a degraded constant name has no definition to find. (The nicer frontend check,
  `resolve::report_unresolved`, does **not** run here — it is gated on `closed`, and aeon's mixed
  AS + `.emp` build goes through `build_program_open_embed`.)

So it is not silent — it is *deferred and de-named*. It is silent-green only in the one case where the
degraded name happens to collide with an actually-defined label or `equ`. If a constructor body spelled
`OP_CRAM`, every author's module would have to import `engine.effects.raster`'s constants or hit one of
those two failures. Inlining the number and pinning it with a co-located `ensure` keeps a single source
of truth without imposing that on callers.

The reference example is `raster_dsl`'s own pin block (`raster_dsl.emp:33-48`): `fire`'s body spells
`3` and `223`, and a module-level `ensure` asserts `RASTER_MIN_FIRE_LINE == 3 && RASTER_MAX_FIRE_LINE
== 223`; the opcodes, terminator, park word, buffer bound and staging arithmetic are pinned the same
way. The pin is what makes the inlining safe; an inline without its pin is just a magic number. Note the
comment at `raster_dsl.emp:40-42`: those pin messages spell both constant names out longhand on purpose,
because `RASTER_{MIN,MAX}_FIRE_LINE` would parse as a message **interpolation** and emit `unknown name
MIN` instead of the diagnostic — latent while the pin passes, broken exactly when it fires.

Two corollaries:

- `vdp_comm` / `VdpTarget` / `VdpOp` **are** safe to name in a body, because `engine.vdp` is itself a
  `COMPTIME_HELPERS` member and is glob-injected at every call site.
- Wire-format **struct type names** (`pal_variant`, `PalCycleScriptN`, `RasterGradientProgram`) live in
  byte-emitting modules, which can never be `COMPTIME_HELPERS` members. So for those, the import at the
  *emission* site remains a discipline rule that no mechanism enforces.

Adding a module to `COMPTIME_HELPERS` also force-publicises its **private** comptime items and injects
one glob per helper in list order, where the later helper silently wins a duplicate name. Run
`python3 tools/emp_helper_closure.py` before and after any such change; it fails on any name exported by
two helpers, and it is also the way to enumerate the current helper set. It does **not** see a collision
against a module-local name — that risk is described under "Reaching the ROM".

---

## References

- `engine/effects/raster.emp` — the runtime decoder: the timing model (`:24-45`), the cycle budget
  (`:71-75`), the opcode set (`:85-155`), `pal_stage_off` (`:118-129`), the row-119 blanking-delay
  measurement (`:157-186`), `raster_arm` (`:210-216`, dense tier only), the dense tier (`:218-287`),
  `Raster_VBlank` (`:323-372`), `Raster_HInt` (`:384-531`), `Raster_InstallSection` (`:545-555`),
  `Raster_Program_None` (`:560`), the water patch slot (`:562-587`) and its three procs (`:597-678`).
- `engine/effects/raster_dsl.emp` — the sparse authoring vocabulary: the inlined-literal pins (`:33-48`),
  the descriptor enums (`:71-80`), the op constructors (`:88-195`), the fire constructors (`:203-271`),
  the encoder internals (`:277-468`), the two public entry points (`:477-519`), `first_mismatch` and its
  prefix precondition (`:527-542`).
- `engine/effects/palette.emp` — the composition pipeline (`:25-68`), `pal_variant` (`:126-132`),
  `Palette_SetVariant` (`:272-288`), the stale gate (`:115`, `:403-414`), `Palette_DoVariants`
  (`:681-697`), `Palette_DeriveVariant` (`:709-771`), the five starter variants (`:776-780`).
- `engine/effects/palette_dsl.emp` — `variant` (`:32-49`) and its build-time packing proofs (`:51-81`),
  `cycle_channel` (`:87-95`), the script wrappers (`:107-120`).
- `games/sonic4/data/parallax/configs.emp:308-541` — the shipped fixtures this vocabulary must reproduce,
  and their hand-word twins.
- `docs/BUGS.md` — **EFX-4** (`:79`), the `Raster_InstallWater` over-read, partially closed by Parcel A.
- `docs/DEFERRED_WORK.md:1899-1902` — the unmeasured VSRAM landing line.
- `docs/superpowers/specs/2026-08-13-effects-p3-design.md` §4.1, §4.4, §5.4, §6.1, §8.1 — and §1,
  where rulings 5 (constructor-guaranteed correctness) and 14 (`SET_REG` first) are stated. Those two
  are *design rulings*, not survey findings.
- `docs/superpowers/notes/2026-08-13-parcel-a-capability-probe.md` — what the `.emp` comptime layer can
  and cannot do, measured with negative controls.
- `docs/superpowers/notes/2026-08-13-effects-p3-parcel-a-evidence.md` — Parcel A's gate: seven golden
  ROMs, no rebaseline (§1).
- `docs/superpowers/notes/2026-08-14-effects-vocabulary-review.md` — the five-lens review this revision
  answers; the open items it raises that are *not* fixed here are flagged inline above.
- `docs/research/2026-08-12-raster-hint-survey.md` — Ruling 1a (`:34-39`), Ruling 1b (`:41-70`),
  Rulings 2a/2b (`:83-92`), and the manual's fire-line-vs-affected-line statement (`:29-32`). The origin
  of the arm schedule and of the cycle budget.
