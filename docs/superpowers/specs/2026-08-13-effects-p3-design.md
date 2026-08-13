# Effects Phase 3 — Authoring Vocabulary, Preset Binding, Starter Pack

**Date:** 2026-08-13
**Status:** Design approved by the user after a three-lens adversarial audit; ready for
per-parcel implementation plans
**Parent spec:** `docs/superpowers/2026-08-11-effects-suite-design.md` §10, row "Phase 3"
**Predecessors:** Effects P1 (merged `21130909`), Effects P2 (merged `78205620`),
palette-variant gate fix (merged `ff0720ff`)

---

## 0. What Phase 3 is

P1 built the raster core, P2 built the palette engine and the dense tier. Both were
authored by hand: a raster program today is a raw `[u16; N]` literal with a hand-counted
length, hand-computed arm words, CRAM commands split into two literal hex words, `count-1`
encodings, and op boundaries marked only by indentation
(`games/sonic4/data/parallax/configs.emp:310-329`, `:389-403`).

Phase 3 makes effects **authorable**: a comptime vocabulary that computes the encodings
and validates them, a preset that binds a section's whole visual identity by name, and a
starter pack that proves the vocabulary against real content. It ships no Aurora, no JSON,
and no new runtime capability.

**The one-line test of success:** an author adds a water section without typing a single
VDP register word, arm word, or CRAM command, and the build refuses the mistakes P1 and
P2 had to discover on hardware.

---

## 1. Rulings that bind this design

Made by the user during brainstorming (1-8) and after the audit (9-12).

1. **Scope: DSL + `.emp` presets only.** The portable `.preset.json` format and
   `tools/effects_gen.py` move to Phase 4/5, where Aurora is their actual producer and
   consumer. Phase 3 defines no serialization format.
2. **Binding: one `sec_effects` preset pointer.** An `EffectsPreset` bundles a section's
   parallax config, raster program, variant set, and cycle script. The imperative water
   install is deleted.
3. **Starter pack: full pack (6 spec'd + 2 range demos), tiered verification.** Oracle-verify
   one preset per distinct mechanism mid-motion; the rest are gated by build-time `ensure`s
   plus a byte-compare against the mechanism they reuse.
4. **Dead data: module-granularity reachability, no compiler pass.** Superseded ruling 4 of
   the brainstorm (which said "build the pruning pass") once the audit established that
   sigil already prunes unreferenced *modules*. See §7.
5. **P2 riders folded in:** constructor-guaranteed correctness ops; world-anchor the
   gradient; give `tools/effects_budget_model.toml` a reader; retire the garish test
   fixtures once the gates they anchor are re-pointed at equivalent coverage.
6. **Showcase: OJZ act1 sections, real content.** No separate showcase act.
7. **Raster representation: computed-length arrays.** `[u16; raster_words(PROGRAM)]`.
   Fixed-max padding was the fallback and is no longer needed (§6.1).
8. **Reserved dense-tier register: stays parked.** Amended by ruling 12.
9. **Mixed-fire policy: allow with explicit acknowledgment.** A fire mixing `OP_SET_REG`
   with a CRAM op is legal, but the author must pass a named acknowledgment param. See §5.3.
10. **Budget model: a checker, not a generator.** See §4.3.
11. **Parcel split: four parcels, replay-net debt first.** See §2.
12. **Drop the reserved-register re-measurement.** Effect dressing does not populate a
    level; the measurement could not support the ruling. See §9.

---

## 2. Parcel structure

Two audits independently concluded this cannot land as one merge: two independent layout
movers in a single delta make the frozen-table audit unattributable, and a smaller parcel
of this class went **139 failures -> 14 -> 0** at its merge gate, with the last blocker
consuming the rest of the session (`docs/superpowers/2026-08-13-effects-p2-handoff.md:107-137`).

| Parcel | Delivers | Repos | Gate |
|---|---|---|---|
| **0** | Re-stamp the replay net on master | aeon | Both fixtures green |
| **A** | `raster_dsl` + `palette_dsl` + budget checker | aeon + sigil | **Byte-compare**: DSL output == today's hand-typed words |
| **C** | `EffectsPreset`, `sec_effects`, `Effects_InstallPreset` | aeon | P1/P2 gates pass unchanged through the new path |
| **D** | Starter pack, world-anchored gradient, section rebinding, gate re-pointing | aeon | Four mid-motion oracle captures + coverage-preserving fixture retirement |

Parcel **B** (a general item-level pruning pass) is **deleted** by ruling 4.

### 2.0 Parcel 0 — pay the replay-net debt first

Master's replay net is **red right now**: both master and the P2 branch desync
byte-identically at tick 1282, inherited from the Knuckles C4 merge whose re-stamp was
never done (`docs/superpowers/notes/2026-08-13-replay-net-attribution.md`). The cause is
attributed: the standing fixture's input at tick 1212 is a spindash charge, and C4 changed
spindash dust, line-0 palette, and `EnsureStanding` — shared player code, intended change,
stale fixture.

Parcels C and D want that net as regression evidence for "behaviour-identical through the
preset path". Against a red baseline that evidence does not exist and any new desync is
unattributable. Re-stamp per
`docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md`, using the probe-ROM logger
route rather than interactive MCP recording (which was measured as unable to produce a
trustworthy fixture: `emulator_hold` fails ~50% of the time and adds rather than replaces).

**This is pre-existing debt, not Phase 3 work.** It is listed first because it gates the
value of everything after it.

### 2.1 Why Parcel A is nearly free at the gate

Parcel A re-expresses the **existing** fixtures and water through the new constructors and
asserts the output is byte-identical to the hand-typed words already in the tree. If that
holds there is no repin, no golden rebaseline, and minimal port-flip. It is also where the
mixed-fire question (§5.3) gets settled against a ground truth instead of an opinion.

Caveat to verify rather than assume: comptime-only module moves *should* be byte-identical,
but sigil module-registration side effects must be checked before the plan promises it.

---

## 3. Architecture

### 3.1 Module layout

```
engine/effects/raster_dsl.emp     NEW — pure comptime, emits zero bytes.
engine/effects/palette_dsl.emp    NEW — pure comptime, emits zero bytes.
engine/effects/preset.emp         NEW — runtime module: the EffectsPreset struct,
                                  its preset() constructor, Effects_InstallPreset.
engine/effects/raster.emp         Sheds constructors + validation. KEEPS its wire-format
                                  structs and documentation.
engine/effects/palette.emp        Sheds constructors + validation. KEEPS its wire-format
                                  structs. Also sheds the five starter variants
                                  (:824-830) — those are Sonic content in an engine module.
games/sonic4/data/effects/        NEW — one module per preset family (§7).
games/sonic4/data/parallax/       Sheds :278-453, becoming what its name says.
```

**Structs stay with the runtime.** Only constructors and validation move. `pal_variant`
(`palette.emp:115-121`), `pal_cycle_channel` (`:186-193`), and `RasterGradientProgram`
(`raster.emp:244-256`) are read by runtime code (`Palette_DeriveVariant` at `:760`,
`:780-807`; `Palette_DoCycle` at `:490-496`); moving them into the DSLs would make the
runtime import the DSL, inverting the dependency the split exists to establish.

**The raster authoring surface is three disjoint spans**, not the one block the runtime
module labels as such: `{112-117 (pal_stage_off), 188-286 (the labelled block),
584-597 (water_arm0 and its bounds consts)}`. A plan that moves only `:188-286` leaves two
helpers behind.

**`preset.emp` is a runtime module**, not a third DSL. Its constructor sits beside its
runtime the way `raster_gradient_program` sits in `raster.emp` today. It is justified by
owning a genuinely new install path and a new wire struct, not by symmetry.

**Concrete win of the seam:** `raster.emp:106-111` currently inlines `128/32/2` to avoid a
`raster -> palette` module edge. A comptime-only `raster_dsl` can import palette constants
freely (no code coupling), retiring that hand-sync note.

### 3.2 The dependency rule

The DSL owns the encoding arithmetic and its validation; the runtime owns only decoding.
Today this is violated in both directions: arm words are hand-computed at call sites while
correctness `ensure`s sit *beside* the data (`configs.emp:295-296`, `:386-387`, `:423-424`)
instead of inside a constructor that could guarantee them.

---

## 4. Authoring surface

### 4.1 Raster programs

The general constructor covers the **sparse tier only**. A `[u16; N]` array cannot hold a
link-time symbol — the only producers of a symbol reference in data position are `*T`-typed
fields and cells sized to the declared width — so a program carrying the gradient's stream
pointer is not expressible as a word array at any spelling. The **dense tier keeps its
struct constructor** (`raster_gradient_program`). One universal constructor would be a
wire-format redesign, not a DSL task, and is explicitly out of scope.

The authoring shape is two declarations, not one. A variable-length value cannot be a
struct field, and existing pointer-taking constructors declare `Label` params, so the
program is its own `pub data` and the preset references it by label:

```
const WATER_PROG = [ region_boundary(line: WATER_LINE, variant: 0, sh: true,
                                     mid_line_switch: true) ]

pub data Water_Prog: [u16; raster_words(WATER_PROG)] = raster_program(WATER_PROG)

pub data Preset_Water_Deep: EffectsPreset = preset(
    parallax:       ParallaxConfig_OJZ_Windy,
    water_template: Water_Prog,
    water_world_y:  OJZ_WATER_WORLD_Y,
    variants:       [Variant_Water_Deep],
    cycle:          OJZ_ShimmerCycle,
)
```

The length annotation is a real guard: `data X: [u16; n] = <array>` hard-checks element
count, so the type proves the constructor and the length agree. This is the doctrine
already stated at `engine/sound/sound_sfx.emp:1611` ("THE LENGTH GUARD IS THE TYPE
ANNOTATION").

`raster_program` computes the arm schedule (including the `T-1` ENTER cost P2 discovered on
hardware), splits CRAM commands into their two words, encodes `count-1`, and emits the
terminator.

### 4.2 Palette

`variant()` and `cycle_channel()` move essentially unchanged — they are already good, with
`ensure` validation and a comptime model of the runtime derive whose proof `ensure`s
build-time-verify known colours through known variants (`palette.emp:147-172`). That
model-plus-proof pattern is the standard the raster DSL should meet.

The `PalCycleScriptN` wart is fixed: today the channel count is spelled three times for one
number (`pcs_count`, the array length, and the wrapper struct name).

### 4.3 The budget model becomes a checker

`tools/effects_budget_model.toml` has zero consumers today; its header's claim that "the
generator enforces and Aurora displays" is aspirational.

The originally-drafted generator (emit `.emp` constants, `ensure` against them, fail on
unmeasured rows) is **unsound and is not built**. The measured rows are upper bounds that
include profiler instrumentation and exception entry — the sparse tier is 8358 cyc/frame
over ~4 fires, roughly 2090 cyc/fire against a `usable_cycles_after_entry` of 60. Any
constructor `ensure` comparing those would fail programs that demonstrably run today. The
predicate would be either false or vacuous.

**What gets built instead:** a checker that walks the `code-derived` rows, resolves each
named `.emp` symbol, and fails if the TOML disagrees with the code. That closes the real
gap — nothing enforces the link today, and the linkage is comment-only — without inventing
a predicate the measurements cannot support.

The two `NEEDS-MEASUREMENT` rows (`raster.op_pal_region.handler_extra_cycles`,
`palette.compose_fade_step_cycles`) are still worth measuring, as **evidence**, not as a
build gate.

### 4.4 Import hygiene is solved structurally

A comptime fn's free names resolve at the **call site**, and in struct-literal position a
missing import degrades **silently** to a label reference rather than erroring. This has
already bitten the tree: `configs.emp:28-33` imports two names nothing in that file spells,
solely because a constructor's struct literal names them.

Hiding `OP_*`, `RASTER_ARM_*`, and the CRAM splitter behind a DSL makes the blind import
list at each call site *longer*, so the failure mode grows with the abstraction.

**Fix:** add `engine.effects.raster_dsl` and `engine.effects.palette_dsl` to sigil's
`COMPTIME_HELPERS` (`sigil/crates/sigil-harness/src/native.rs:1733-1746`), which
force-injects `use <id>.*` into every module. `engine.level.parallax_dsl` is already on that
list for exactly this reason. This makes the whole error class unreachable rather than
documented, and it is why **Parcel A is a paired aeon+sigil parcel**.

Belt and braces: constructors should still prefer parameters and numeric literals in
returned struct literals, pinning any inlined number with a co-located `ensure` — the
pattern `raster.emp:587-597` already established for `water_arm0`.

---

## 5. The preset contract

### 5.1 Binding

`sec_effects` **reuses the reserved `sec_collision_s4lz` pointer at `$34`**
(`engine/structs.emp:124`), which has zero engine consumers. Renaming it keeps
`sizeof(Sec)` at exactly 66.

This matters more than it sounds. `Sec` is full, and 66 is pinned by two `ensure`s and
hardcoded as a literal in two runtime multiplies (`engine/level/section.emp:27,151`,
`engine/level/tile_cache.emp:31,302`), plus a third guard at `act_descriptor.emp:87`. A new
4-byte field would take `Sec` to 70, trip all three guards, change both literals, widen the
shift/add expansion in the section-lookup path, grow every section record, and move the
frozen placement tables. Reusing `$34` costs none of that. Collision-S4LZ has no design
behind it yet and can claim a pad later.

### 5.2 Preset and legacy fields are mutually exclusive

The four existing fields (`sec_parallax_config`, `sec_pal`, `sec_raster_table`,
`sec_pal_cycle`) remain for sections without a preset. A section may name a preset **or**
the legacy fields, never both, enforced in `ojz_sec` at build time.

Layering them was the original draft and it was wrong. `sec_parallax_config`'s 0 does not
mean "keep current" — it falls back to `Act.act_parallax_config` (`parallax.emp:189-193`) —
while the other three do (`palette.emp:260`, `:369`; `raster.emp:537`). A uniform override
rule would have silently redefined one of the four and given parallax config three possible
sources with unstated precedence. It also worsens a known trap: a 0 field already has two
meanings ("keep previous" or "install failed"), and a preset layer adds a third.

`sec_pal` is the exception to work out in the plan: it is currently a *required* argument,
so either the preset carries the palette too or `sec_pal` is exempted from exclusivity.

### 5.3 Water is a separate channel

Water is not a normal raster program. `Raster_InstallWater` (`raster.emp:607-623`) copies
the template into **`Raster_Buf_B`**, points both `Raster_Active_Buf` and `Raster_Program`
at Buf_B, and **clears `Raster_Pending`**, explicitly bypassing the ROM-program Buf_A path
(`:604-605`). `Raster_PatchWaterLine` then writes into Buf_B unconditionally (`:656`,
`:665`, `:668`).

If a preset carried water as an ordinary `raster:` field, install would route through
`Raster_Pending` -> Buf_A, while `Raster_PatchWaterWorldY` kept writing Buf_B every frame.
The water would still render, at a wrong line, forever, never tracking the camera. Silent,
and exactly the "dynamic thing made static" failure mode.

So `EffectsPreset` carries `ep_water_template` + `ep_water_world_y` as a channel distinct
from `ep_raster`, and `Effects_InstallPreset` routes it through `Raster_InstallWater`, which
survives as a runtime entry point.

### 5.4 The mixed-fire acknowledgment (ruling 9)

A fire mixing `OP_SET_REG` with a CRAM op still switches its mode register roughly 45%
across the line; P2 measured that extending the delay costs ~40 cycles of a ~60-cycle
budget and deliberately did not take it (`raster.emp:164-167`).

The shipped water **is** that mix (`configs.emp:396-400`), so a constructor that refused it
could not re-express water byte-for-byte, which would kill Parcel A's gate. The DSL
therefore **allows** the mix but requires a named acknowledgment parameter, and documents
the artifact as an invariant of that shape. The footgun stays visible at the authoring
surface instead of silent.

### 5.5 Buffer topology: at most one patched effect per section

`Raster_Buf_B` is a single buffer and water owns it (§5.3). The P2 handoff's recipe for
world-anchoring the gradient is "install it into `Raster_Buf_B` the way water is" — which
means **a section may carry at most one world-anchored (runtime-patched) effect**. A
world-anchored water and a world-anchored gradient in the same section contend for the same
buffer.

This is a constraint, not a defect, and it must be enforced at build time: `preset()`
`ensure`s that at most one patched channel is populated. Supporting two would mean a second
patch buffer plus a merge step at flip, which is a Phase-6-scale change and is out of scope.

Note this does **not** limit stacking in the sparse tier: treeline **and** water as two
region boundaries inside one program is a single static program, which is exactly the
stacked-regions case §8.1 gates on. The constraint is specifically about two independently
*patched* effects.

### 5.6 Install correctness

- `Effects_InstallPreset` writes **every** variant slot unconditionally. `Palette_SetVariant`
  treats a null pointer as "clear the slot" (`palette.emp:317-337`), so a preset with one
  variant writes `[Variant_X, 0]`. Skipping the write would leave a stale slot bound when
  crossing from a 2-variant preset to a 1-variant one, and a bound variant derives every
  frame — the exact 15.1%-of-frame cost the P2 gate fix just recovered.
- **No count or version field.** `Palette_SetVariant`'s null-clears semantics make a count
  redundant, and the struct is compile-time-linked rather than serialized, so a version byte
  is dead ROM in every preset.
- **`PAL_MAX_VARIANTS` cannot be raised past 2 without a fix first.** `palette.emp:323` uses
  `andi.w #(PAL_MAX_VARIANTS - 1), d0`, a power-of-two mask; a value of 3 would silently
  fold slot 2 onto slot 0. Any change to that constant must convert the mask to a bounds
  check.
- **Layout:** sigil does not auto-4-align (`RasterGradientProgram.rgp_stream` sits at byte
  offset 26). Even alignment is all the 68000 needs, so `EffectsPreset` must simply avoid an
  odd count of `u8` fields before any pointer.
- **`Preset_None` is required**, and it is not merely `Raster_Program_None`. Turning a preset
  off must clear four channels at once, which needs a `Pal_Cycle_None` (an empty count-0
  script) that does not exist in the tree today.
- **Install site:** `Parallax_CheckBoundary` (`parallax.emp:179-186`) is the single
  crossing-detection point and all consumers already take and preserve `a0 = Sec*`.
- **Install order:** the palette engine's `base -> cycling -> cross-fade -> operators ->
  variants` order is a per-frame *compose* order, and imposes nothing on install. The one
  real install-order constraint is that `Palette_ArmFade` is a one-shot consumed by
  `Palette_LoadSection` (`palette.emp:269`, `:281`, `:300-303`), so a preset wanting a
  cross-fade must arm **before** the base load.
- **First section is not a hole:** `Parallax_Init` seeds `Prev_Sec_X/Y` to `$FF`
  (`parallax.emp:121-122`), so section 0 gets a full install. But note that deleting the
  imperative water install moves variant binding from *init* to *update frame 1*, so the
  first displayed frame shows un-varianted water. Expected, and must not be mistaken for a
  failed install in a press-frame capture.

---

## 6. Verified toolchain facts this design depends on

### 6.1 Computed-length arrays work

Sigil parses the array-size position with the full expression parser
(`sigil-frontend-emp/src/parser.rs:823-830`), resolves it through `eval_const_index` ->
`eval_expr` -> `eval_call` into the user `comptime fn` table (`layout.rs:249-252, 327-352`;
`eval/expr.rs:60`; `eval/call.rs:235-256`). Two doc comments state the intent explicitly
(`layout.rs:1535-1537`, `eval/mod.rs:1812-1813`). Only the provisional forms (`bankid`,
`extern`, `here()`) are refused in that position.

**Not yet witnessed end-to-end from aeon.** Step 1 of Parcel A's plan is a single-file probe
(`comptime fn n() -> int { return 4 }` / `data T: [u16; n()] = [0,0,0,0]`, run `sigil emp` on
that file alone). Two riders to write into the plan: the size expression is re-evaluated on
every `resolve_type`, so `ensure`s inside a length-computing fn can double-report; and a
comptime fn's return-type annotation is never enforced, so it is documentation only.

### 6.2 List-taking constructors work

Array-typed params bind (params are loosely typed at bind; only refined params are checked),
`for e in <array>` iterates, `Array ++ Array` plus `comptime var` reassignment accumulates,
and payload-carrying comptime enums exist for heterogeneous descriptors.

### 6.3 Module registration is a real cost

Byte-emitting `.emp` modules live in a hardcoded Rust registry
(`sigil-harness/src/native.rs:216-255ff`) with a pins Region each. So `engine/effects/preset.emp`
and each `games/sonic4/data/effects/*` module needs a registry entry, a `repin.toml` region,
a `map.toml` order slot, and rows in all seven frozen tables. Pure-comptime modules need no
registry entry (precedent: `engine/debug/generated/compression_vectors.emp`), though
`COMPTIME_HELPERS` membership is separate and required per §4.4.

Note also that moving the five starter variants out of `palette.emp:824-830` shrinks
`pins::PALETTE.plain_len` by 40 bytes — a frozen-table change with no behaviour change
behind it. There is a loud guard, not a silent failure, if a byte-emitting module lands
unregistered (`native.rs:1820-1828`).

### 6.4 ROM cost is negligible

Roughly: `EffectsPreset` ~20-24 B, eight presets ~200 B, eight raster programs ~320 B
(largely *replacing* retired fixtures), `sec_effects` 0 B (reused field). Under 1 KB against
a 696,788-byte ROM. The real spatial constraint is the data region's headroom before the
`$48000` org anchor, not total ROM. (The often-quoted "31.8 KB free" figure is **RAM**, not
ROM, and presets do not touch it.)

---

## 7. The dead-data property

**Sigil already prunes at module granularity.** A BFS over `use` edges
(`sigil-frontend-emp/src/resolve/mod.rs:793-839`, called at `:432`) means an unreferenced
*module* contributes nothing. There is no item-level pass, and building one was dropped
(ruling 4): it would need a whole-program reference graph whose root set includes
`extern("...")` **string** references (`act_descriptor.emp:168` resolves data by string),
AS-residual references, and map.toml anchors — a naive symbol-graph pass would prune live
data and ship a broken ROM. It would also fight the port tests, which compile one module in
isolation where nearly everything is unreferenced.

**So the library property is a file-layout decision:** one module per preset family.
Referenced family -> bytes; unreferenced family -> zero.

**Gate method:** compare **`data`-item spans in the `.lst`**, never ROM length. A length
comparison measures the placer's own fill, which is a recorded failure mode in this
codebase.

**Bonus this unlocks:** after the property holds, retiring a test fixture from `Sec`
references makes it cost zero ROM **without deleting it**. The P1/P2 fixtures can survive as
source, bound only in an off-canonical test profile — which is how ruling 5's
"equivalent coverage first" condition gets satisfied at zero release cost.

---

## 8. Testing and gates

### 8.1 Per-parcel gates

- **A — byte-compare.** DSL output must equal the existing hand-typed words for
  `OJZ_TestRaster`, `OJZ_WaterRaster`, `OJZ_TestGradient`, and the five variants. This is the
  parcel's whole justification: it forces §5.4 against a ground truth and keeps the merge
  surface near zero.
- **C — behaviour-identical.** The P1 and P2 gates run unchanged through the new preset path,
  with the existing fixtures wrapped as presets. Replay net (green after Parcel 0) plus
  oracle evidence.
- **D — four mid-motion oracle captures**, one per distinct mechanism: variant region + S/H;
  world-anchored dense gradient (verified to move with camera Y); cycle; and **stacked
  regions** (treeline and water in one section), which is the composability proof. Remaining
  pack members are gated by build-time `ensure`s plus byte-compare against the mechanism they
  reuse.

Verification doctrine throughout: captures **during motion**, never at rest. And
`emulator_read_cram` is frame-latched — it cannot see a mid-frame CRAM write and returns the
base palette at every scanline, so per-scanline CRAM sampling is not a valid instrument for
raster work. Measure the framebuffer. (`configs.emp:409-410` still carries a stale comment
claiming the `run_to_scanline` + `read_cram` method; the re-pointed gate must inherit the
framebuffer method and that comment should be corrected.)

### 8.2 Fixture retirement must preserve coverage

Each retired fixture anchors specific coverage:

- **`OJZ_TestRaster`** — sparse multi-op fire, the plain **`OP_CRAM`** path, `pal_dirty_mask`
  transience. Its discriminator CRAM entry was chosen *after* the first choice proved
  unfalsifiable under art (`configs.emp:288-296`). A water preset covers SET_REG +
  PAL_REGION but **not plain `OP_CRAM`** — so either one pack member uses `OP_CRAM`, or the
  coverage narrowing is recorded explicitly.
- **`OJZ_TestPal`** — its value is that a *subtle* real palette makes "consumer never ran"
  look like success. Real content cannot carry this discriminator unless adjacent sections'
  palettes are provably far apart. Replace with a CRAM read of 2-3 entries, pinned by a
  build-time `ensure` proving the neighbouring sections' authored palettes differ, so art
  edits cannot quietly erode the gate.
- **`OJZ_TestGradient`** — seven measured ramp boundaries plus three deliberately different
  channel words at the same level, so a one-word stream desync is distinguishable from a
  one-line shift. This caught the real `T-1`/`T-2` off-by-one. Real sky gradients co-vary
  their channels, destroying that discriminator — a sunset **can** be authored with
  deliberately distinct per-entry ramps plus `ensure`-pinned boundaries, but a sky chosen for
  looks alone cannot.
- **`OJZ_ShimmerCycle`** — period/span check survives on real content provided entries and
  period stay known constants.

Per §7, retirement means unbinding from `Sec`, not deletion.

---

## 9. Explicitly out of scope

- **`.preset.json`, `tools/effects_gen.py`, and all Aurora work** — Phase 4/5 (ruling 1).
- **`SAT_SWITCH` reflections and `RUN_VSRAM`.** The parent spec's §4 command table and its §5
  water definition include both, but the **shipped runtime op set is SET_REG / CRAM /
  PAL_REGION / RUN_GRADIENT only** (`raster.emp:87-129`). Every pack member — including the
  two range demos — must stay inside the shipped op set, or a starter preset silently drags
  runtime scope into Phase 3.
- **One universal raster constructor spanning both tiers** — a wire-format redesign (§4.1).
- **Item-level dead-data pruning** — ruling 4 and §7.
- **Proving S/H on real content.** It needs low-priority water tiles, which means
  regenerating block data through `tools/ojz_strip_gen.py` and `games/sonic4/data/editor/ojz`
  — auto-commit-daemon territory, with uncommitted changes already in the working tree. The
  S/H proof from P2 stands on its own evidence (a measured 1.95x brightness step across the
  boundary).
- **The reserved dense-tier register re-measurement (ruling 12).** The parked question's
  caveat is that a *populated* level has less idle to absorb a dense run. Binding effect
  dressing to OJZ sections does not populate it, so the measurement would re-measure the
  near-empty scroll test with prettier colours and could not support the ruling. It stays
  parked until there is real content to measure in.
- **Two independently patched effects in one section** — single-buffer contention, §5.5.
- **A seamless fully-submerged view.** A fully-submerged screen keeps a 3-line un-effected
  sliver at the top, because screen lines 0-2 belong to the priming records. Closing it means
  authoring the program's frame-top init words, which the DSL *does* expose (they are already
  part of the program header) — but the fully-submerged content state itself is not a Phase 3
  deliverable, and no pack member depends on it.
- **`sec_anim_blocks`** — a separate DEFERRED_WORK entry, called out here only because Parcel
  C touches the struct it lives in.
- **The residual streaming-lag hunt** (~14% of frames on a diagonal stress traverse, post
  palette-variant fix) — its own task, with the instrument already identified (break on the
  `Lag_Frame_Count` increment; averaged profiling cannot find a spike).

---

## 10. Pre-existing defects surfaced by the audit

Neither is Phase 3's to fix, both should be recorded in `docs/BUGS.md`:

1. **Water survives exactly one section crossing.** Crossing from section 0 into section 1
   stages `OJZ_TestRaster` into Buf_A and destroys the water install permanently, because
   section 0's `sec_raster_table` is 0 = "keep current" (`raster.emp:544-554`), so crossing
   back never restores it. Parcel C's per-section preset install is the natural fix.
2. **The cross-fade layer is unreachable.** `Palette_ArmFade` and `Palette_LoadCycle` have
   **zero callers** — 60-plus lines of `Palette_DoFade`, `Pal_Target`, and `PAL_FADE_FRAMES`
   are dead in the shipped ROM. A preset carrying a transition is their natural first caller;
   Parcel C should claim them rather than leave the machinery dead.

Also noted: `games/sonic4/data/editor/ojz/act1/export/act_descriptor.asm` (untracked, another
session's in-flight work, under the auto-commit daemon) emits a **stale** `Sec` layout with
fields that no longer exist. `engine/structs.emp` is the authority, but whoever touches `Sec`
should expect a collision there.

---

## 11. Documentation obligations

- `docs/ENGINE_ARCHITECTURE.md` §7 must be updated as each parcel lands — it is the source of
  truth, and CLAUDE.md makes keeping it current law.
- `docs/DEFERRED_WORK.md` entry 3 (water/underwater hooks) and entry 6 (the reserved
  dense-tier register) both need status updates.
- `tools/effects_budget_model.toml`'s header claim about generator enforcement must be
  corrected to match §4.3.

---

## 12. Audit provenance

This design was revised after a three-lens adversarial audit of the first draft, run because
the parcel is large and its merge ritual expensive. The lenses were architecture/contract
correctness, toolchain feasibility, and scope/sequencing risk. Findings that changed the
design rather than confirming it:

- `Sec` is full; the naive field addition trips three guards and two hardcoded strides (§5.1).
- Routing water through an ordinary raster field breaks the Buf_A/Buf_B contract silently
  (§5.3).
- The drafted mixed-fire refusal made the flagship preset inexpressible (§5.4).
- The drafted one-call-site ergonomic does not type-check (§4.1).
- A word array cannot carry the gradient's stream pointer at any spelling (§4.1).
- Sigil already prunes at module granularity, deleting a whole parcel (§7).
- The drafted budget-model gate was an unsound predicate (§4.3).
- The import-hygiene problem has a structural fix in sigil rather than a discipline rule
  (§4.4).
- One merge had to become four parcels (§2).
