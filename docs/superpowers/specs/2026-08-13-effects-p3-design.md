# Effects Phase 3 — Authoring Vocabulary, Preset Binding, Starter Pack

**Date:** 2026-08-13
**Status:** Approved after TWO adversarial audit rounds (six agents, six lenses). Ready for
per-parcel implementation plans, subject to the one pre-planning probe in §6.1.
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

Phase 3 makes effects **authorable**: a comptime vocabulary that computes the encodings and
validates them, a preset that binds a section's whole visual identity by name, and a
starter pack that proves the vocabulary on real content. It ships no Aurora, no JSON, and no
new runtime capability.

**The one-line test of success:** an author adds a water section without typing a single VDP
register word, arm word, or CRAM command, and the build refuses the mistakes P1 and P2 had
to discover on hardware.

---

## 1. Rulings that bind this design

Made by the user during brainstorming (1-8), after audit round 1 (9-12), and after audit
round 2 (13-15). Where a later ruling supersedes an earlier one, both are shown, because the
superseded premise explains why the spec is shaped the way it is.

1. **Scope: DSL + `.emp` presets only.** `.preset.json` and `tools/effects_gen.py` move to
   Phase 4/5, where Aurora is their producer and consumer.
2. **Binding: one `sec_effects` preset pointer.** The imperative water install is deleted.
3. **Starter pack: full pack (6 spec'd + 2 range demos), tiered verification.** Oracle-verify
   one preset per distinct mechanism mid-motion; the rest gated by build-time `ensure`s plus
   byte-compare against the mechanism they reuse.
4. **~~Build the sigil pruning pass~~ -> ~~module-granularity reachability~~ -> DROP THE
   DEAD-DATA PROPERTY.** Twice superseded, both times by evidence. See §7 — the property is
   not achievable for registered modules at all. The pack ships as **one module**.
5. **P2 riders folded in:** constructor-guaranteed correctness ops; world-anchor the
   gradient; give `tools/effects_budget_model.toml` a reader; retire the garish fixtures once
   the gates they anchor are re-pointed at equivalent coverage.
6. **Showcase: OJZ act1 sections, real content.**
7. **Raster representation: computed-length arrays.** `[u16; raster_words(PROGRAM)]`.
8. **Reserved dense-tier register: parked** (amended by ruling 12).
9. **~~Mixed-fire acknowledgment param~~ -> `SET_REG`-must-be-first `ensure`.** Superseded:
   the boolean was ritual, and could not see the strictly-worse ordering. See §5.4.
10. **Budget model: a checker, not a generator.** §4.3.
11. **Parcel split: four parcels, replay-net debt first.** §2.
12. **Drop the reserved-register re-measurement.** §9.
13. **Dead data: one pack module, property dropped** (ruling 4's final form). Fixture
    retirement at zero release cost is achieved by **conditional `ModuleSpec` push in an
    off-canonical profile**, not by unbinding from `Sec`. §7.
14. **Mixed fire: `ensure` that `OP_SET_REG` is the first op in any mixed fire**, with the
    measured 45% figure in the message. §5.4.
15. **The stacked-regions gate is treeline + a second static region, no water.** §8.1.

Decided by the controller where the audits converged on a single answer, and recorded here
so the plan does not re-open them:

- **The preset carries the palette** (`ep_pal`), and `ojz_sec`'s `pal` becomes
  `Label = 0`. §5.2.
- **Parcel A is comptime-only.** All data relocation moves to C. §2.1, §3.1.
- **All four parcels are paired aeon+sigil.** §2.

---

## 2. Parcel structure

Two round-1 audits independently concluded this cannot land as one merge: two independent
layout movers in a single delta make the frozen-table audit unattributable, and a smaller
parcel of this class went **139 failures -> 14 -> 0** at its merge gate
(`docs/superpowers/2026-08-13-effects-p2-handoff.md:107-137`).

| Parcel | Delivers | Repos | Gate |
|---|---|---|---|
| **0** | Re-stamp the replay net on master | aeon | Divergence disappears **for the attributed reason** (§2.0) |
| **A** | `raster_dsl` + `palette_dsl` + budget checker. **Comptime-only; zero bytes moved.** | aeon + sigil | **All seven golden ROMs green with no rebaseline** (§8.1) |
| **C** | `EffectsPreset`, `sec_effects`, `Effects_InstallPreset`, `Preset_None`/`Pal_Cycle_None`, **all data relocation**, delete the imperative install | aeon + sigil | P1/P2 gates pass through the new path; replay net green; declared delta list |
| **D** | Starter pack (one module), world-anchored gradient, section rebinding, gate re-pointing | aeon + sigil | Four mid-motion oracle captures + coverage-preserving retirement |

**Every parcel is paired.** The sigil-side registry, `pins.rs`, `repin.toml`, and the frozen
tables are what make C and D paired; A is paired because of `COMPTIME_HELPERS` (§4.4). Merge
the two repos **as a pair** and record the verified pair — this tree has a recorded failure
where sigil master was coupled to an unmerged aeon branch and aeon master became
unbuildable. Rebuild **both** sigil binaries before gating; a stale binary produces a green
run against the wrong compiler.

**One layout mover per parcel** is the principle. A moves nothing, C moves data, D adds
content.

### 2.0 Parcel 0 — pay the replay-net debt first

Master's replay net is red: both master and the P2 branch desync byte-identically at tick
1282, inherited from the Knuckles C4 merge whose re-stamp was never done
(`docs/superpowers/notes/2026-08-13-replay-net-attribution.md`). The cause is attributed —
the fixture's input at tick 1212 is a spindash charge, and C4 changed spindash dust, line-0
palette, and `EnsureStanding`.

Re-stamp per `docs/superpowers/notes/2026-08-09-replay-net-rerecord-ab.md`, using the
probe-ROM logger route (interactive MCP recording was measured as unable to produce a
trustworthy fixture: `emulator_hold` fails ~50% of the time and adds rather than replaces).

**The gate must not be "both fixtures green."** A re-recorded fixture always replays green
against the ROM it was recorded on, so that observation is true by construction and tests
nothing. The falsifiable version: record that the tick-1282 divergence disappears **for the
attributed reason** — i.e. the pre-re-stamp fixture's divergence is demonstrated to originate
in the spindash-charge input at tick 1212, and the new fixture is verified to replay against
an unrelated already-merged commit as well.

This is pre-existing debt, not Phase 3 work. It is first because it is what makes C's and D's
regression evidence mean anything.

### 2.1 Parcel A is comptime-only, and that is what makes it cheap

Round 2 settled the contradiction the controller flagged. The comptime constructor moves and
the `COMPTIME_HELPERS` additions **are** byte-neutral. Moving the five starter variants out
of `engine/effects/palette.emp:824-830` is **not** — it relocates 40 bytes of `pub data`,
shifting every downstream section and invalidating all seven golden ROMs.

**Therefore Parcel A re-expresses the existing fixtures IN PLACE** in `configs.emp` and
creates only the two pure-comptime DSL modules. Every data relocation — the five variants,
and `configs.emp:278-453` moving to `games/sonic4/data/effects/` — lands in **Parcel C**,
where a repin is being paid anyway.

If A were allowed to move data, its byte-compare would also self-rebaseline into vacuity
("my new output equals my new output") — the recorded gate-measures-the-placer failure mode,
one layer up.

---

## 3. Architecture

### 3.1 Module layout, with the parcel that performs each move

```
engine/effects/raster_dsl.emp    NEW, pure comptime, zero bytes.          [Parcel A]
engine/effects/palette_dsl.emp   NEW, pure comptime, zero bytes.          [Parcel A]
engine/effects/preset.emp        NEW runtime module: EffectsPreset,
                                 preset(), Effects_InstallPreset.         [Parcel C]
engine/effects/raster.emp        Sheds constructors + validation.         [A: comptime only]
engine/effects/palette.emp       Sheds constructors + validation;
                                 later sheds the five starter variants.   [A: comptime; C: data]
games/sonic4/data/effects/       NEW — ONE module for the whole pack.     [C creates; D fills]
games/sonic4/data/parallax/      Sheds :278-453.                          [Parcel C]
```

**Structs stay with the runtime.** Only constructors and validation move. `pal_variant`
(`palette.emp:115-121`), `pal_cycle_channel` (`:186-193`), and `RasterGradientProgram`
(`raster.emp:244-256`) are read by runtime code, so moving them into the DSLs would invert
the dependency. See §4.4 for the consequence this has for import hygiene, which the first
draft got wrong.

**The raster authoring surface is three disjoint spans**, not the one block the runtime
module labels as such: `{112-117 (pal_stage_off), 188-286 (the labelled block), 584-597
(water_arm0 and its bounds consts)}`. A plan that moves only `:188-286` leaves two helpers
behind.

**`preset.emp` is a runtime module**, not a third DSL; its constructor sits beside its
runtime the way `raster_gradient_program` sits in `raster.emp` today.

**Concrete win of the seam:** `raster.emp:106-111` inlines `128/32/2` to avoid a
`raster -> palette` module edge; a comptime-only `raster_dsl` can import palette constants
freely, retiring that hand-sync note.

### 3.2 The dependency rule

The DSL owns the encoding arithmetic and its validation; the runtime owns only decoding.
Today this is violated in both directions: arm words are hand-computed at call sites while
correctness `ensure`s sit *beside* the data (`configs.emp:295-296`, `:386-387`, `:423-424`).

---

## 4. Authoring surface

### 4.1 Raster programs

The general constructor covers the **sparse tier only**. A `[u16; N]` array cannot hold a
link-time symbol, so a program carrying the gradient's stream pointer is not expressible as a
word array at any spelling. The **dense tier keeps `raster_gradient_program`**.

**Scope exclusion the audit forced (new):** the wire format *permits* sparse events before and
after a dense run — `Raster_HInt`'s `.op_run_gradient` falls through to `.advance`
(`raster.emp:495-508`), and the LEAVE schedule at `:419-425` explicitly discusses "the first
post-gradient sparse event". Neither constructor can author that combination.
**A program mixing sparse events with a dense run is not authorable in Phase 3**; a section
takes one or the other. No pack member may require the mix (§9).

The authoring shape is two declarations. A variable-length value cannot be a struct field,
and pointer-taking constructors declare `Label` params, so the program is its own `pub data`:

```
const WATER_PROG = [ region_boundary(line: WATER_LINE, variant: 0, sh: true) ]

pub data Water_Prog: [u16; raster_words(WATER_PROG)] = raster_program(WATER_PROG)

pub data Preset_Water_Deep: EffectsPreset = preset(
    pal:            OJZ_Palette,
    parallax:       ParallaxConfig_OJZ_Windy,
    patched:        Water_Prog,
    patch_world_y:  OJZ_WATER_WORLD_Y,
    variants:       [Variant_Water_Deep],
    cycle:          OJZ_ShimmerCycle,
)
```

The length annotation is a real guard: `data X: [u16; n] = <array>` hard-checks element
count, so the type proves constructor and length agree — the doctrine already stated at
`engine/sound/sound_sfx.emp:1611`.

`raster_program` computes the sparse arm schedule, splits CRAM commands into their two words,
encodes `count-1`, and emits the terminator.

> **Correction the audit caught in the first draft:** the `T-1` ENTER cost is a **dense**-tier
> fact (`raster.emp:236-243`). The sparse authorities are `raster_arm` / `raster_fire_line` /
> `water_arm0` (`:197-213`, `:592-595`). Applying the dense off-by-one to sparse arithmetic
> fails the byte-compare in the most confusing possible direction.

**The plan must open Parcel A with a vocabulary table** — the descriptor set, each one's
parameters, what `raster_words()` counts (header + priming + records + terminator), and how
`pal_dirty_mask` and the init words derive from the descriptors. The byte-compare gate is only
winnable if the vocabulary can express every word already in the tree, and the gate targets
include cases the single shown constructor does not cover: `OJZ_TestRaster`'s plain `OP_CRAM`
with an inline colour at a different CRAM address (`configs.emp:310-329`), the region op's
address/entry/count triple, and the mask and init words.

### 4.2 Palette

`variant()` and `cycle_channel()` move essentially unchanged — they already carry `ensure`
validation and a comptime model of the runtime derive whose proof `ensure`s build-time-verify
known colours through known variants (`palette.emp:147-172`). That model-plus-proof pattern is
the standard the raster DSL should meet.

The `PalCycleScriptN` wart is fixed: the channel count is currently spelled three times for
one number.

### 4.3 The budget model becomes a checker

The originally-drafted generator (emit `.emp` constants, `ensure` against them, fail on
unmeasured rows) is **unsound and is not built**: the measured rows are upper bounds including
profiler instrumentation and exception entry (~2090 cyc/fire against a
`usable_cycles_after_entry` of 60), so any such `ensure` would fail programs that demonstrably
run today.

**What gets built:** a checker over the `code-derived` rows that resolves each named `.emp`
symbol and fails on disagreement.

Sized honestly by the audit: **7 rows over 6 distinct constants** are mechanically resolvable
(`RASTER_CRAM_MAX` twice, `PAL_MAX_VARIANTS`, `PAL_CYCLE_MAX_CHANNELS`, `PAL_FADE_FRAMES`,
`PALETTE_STATE_SIZE`, `RASTER_STATE_SIZE`), plus `variant_stage_bytes` if the checker
evaluates expressions. Not resolvable: `save_set_registers` (a `movem` operand),
`program_overhead_fires` (no symbol), `full_line_fire_cost` (`ceil(16/3)`),
`compose_static_frame` (prose).

**It is not vacuous — it already has a catch.** `RASTER_STATE_SIZE` is 288
(`raster.emp:184`); the TOML says `raster_state_bytes = 286` (`:99`). `PALETTE_STATE_SIZE`
agrees at 472, so this is a real one-row drift rather than a systematic offset.

**Parcel A must also edit the TOML** to add an explicit symbol key per row — today the linkage
is comment-only prose, which no checker can consume.

The two `NEEDS-MEASUREMENT` rows stay unmeasured for now and are recorded as evidence gaps,
not build gates.

### 4.4 Import hygiene: structural for values, discipline for types

A comptime fn's free names resolve at the **call site**, and in struct-literal position a
missing import degrades **silently** to a label reference. This has already bitten the tree
(`configs.emp:28-33`).

**The structural half:** add `engine.effects.raster_dsl` and `engine.effects.palette_dsl` to
sigil's `COMPTIME_HELPERS` (`sigil/crates/sigil-harness/src/native.rs:1733-1746`), which
force-injects `use <id>.*` into every module. `engine.level.parallax_dsl` is already there for
this reason. **This is why Parcel A is paired.**

**The half the first draft got wrong:** `collect_pub_comptime` injects a helper's **own** items
only — it does not transitively inject what the helper imports. The wire-format **struct type
names** (`pal_variant`, `PalCycleScript1`, `EffectsPreset`, `RasterGradientProgram`) stay in
byte-emitting modules, which can never be `COMPTIME_HELPERS` members. So type imports remain a
**discipline rule**, and the "belt and braces" practice below is the actual mitigation for
them, not a nicety:

> A constructor's returned struct literal should contain only its own parameters and numeric
> literals. Where a named constant is wanted, inline the number and pin it with a co-located
> `ensure` — the pattern `raster.emp:587-597` established for `water_arm0`.

**Two hazards `COMPTIME_HELPERS` membership carries, which the plan must handle:**

1. `normalize_helper_imports` (`native.rs:1077-1126`) drops existing helper `use`s and
   prepends one glob per helper **in list order**, so between two helpers the later wins
   silently.
2. `publicize_helper_comptime` (`native.rs:1134-1155`) force-publicizes every **private**
   comptime item of a helper. The moment `palette_dsl` joins the list, `palette.emp`'s private
   `clamp07` and friends become globally injected names.

The one way either changes bytes: a name currently **unresolved and degrading to a label
reference** in some module would start resolving to an injected const. **Parcel A step:**
enumerate the two DSL modules' post-publicize exported closure and diff it against the union
of the existing eleven helpers' closures; fail on any duplicate. Do this **before** the golden
run, so a green golden is not mistaken for absence of collision.

---

## 5. The preset contract

### 5.1 Binding

`sec_effects` **reuses the reserved `sec_collision_s4lz` pointer at `$34`**
(`engine/structs.emp:124`), verified to have zero engine consumers. Renaming keeps
`sizeof(Sec)` at exactly 66.

This matters: `Sec` is full, and 66 is pinned by two `ensure`s plus hardcoded literals in two
runtime multiplies (`engine/level/section.emp:27,151`, `engine/level/tile_cache.emp:31,302`)
and a third guard at `act_descriptor.emp:87`. A new 4-byte field would trip all three, change
both literals, widen the shift/add expansion in the section-lookup path, grow every section
record, and move the frozen tables.

The rename moves no bytes: `harvest_engine_struct_offsets` (`native.rs:1315-1331`) derives
`Sec_<field>` mechanically, and field names never reach the image or the deb2 table. `ojz_sec`
names every field explicitly, so the rename fails loud rather than silently.

`*u8` is the correct type — every `Sec` pointer is `*u8` including ones that point at structs.
A `*EffectsPreset` would force `engine.structs` (itself a `COMPTIME_HELPERS` member) to depend
on `engine.effects.preset`, the wrong direction.

**Rider:** `sigil/crates/sigil-harness/src/test_support.rs:142` carries
`("Sec_sec_collision_s4lz", "$34")` as a supply-only blob for standalone port oracles, and
**nothing cross-checks it against the harvest** — a stale name silently supplies a dead equ.
Rename it in the same commit, and add the cheap hardening that asserts the two name sets match.

### 5.2 Preset and legacy fields are mutually exclusive; the preset carries the palette

A section may name a preset **or** the legacy fields, never both, enforced by an `ensure` in
`ojz_sec` (with a twin in `preset()` so other games inherit it).

Layering them was the first draft and it was wrong: `sec_parallax_config`'s 0 does not mean
"keep current" — it falls back to the act default (`parallax.emp:189-193`) — while the other
three do. A uniform override rule would have silently redefined one of the four and given
parallax config three sources with unstated precedence.

**`sec_pal` is resolved, not deferred: the preset carries the palette** (`ep_pal`), and
`ojz_sec`'s `pal` becomes `Label = 0`. The audit confirmed `pal` was only required because a
link-time extern cannot be a comptime *default* — which is exactly why `raster: Label = 0`
already works. Exclusivity then requires exactly one of `{pal, effects}`.

Two implementation costs the plan must carry:
- `Palette_LoadSection` reads `Sec.sec_pal(a0)` directly (`palette.emp:265`), so a
  preset-carried palette needs a pointer-taking core with the Sec-reading wrapper over it.
- `Palette_LoadSection` is deliberately the **section head** of the `palette` pins region
  (`palette.emp:250-252`), so adding a proc above it moves the region boundary — a
  frozen-table change with no behaviour behind it, on top of the 40-byte variant move.

**Consequence to state plainly:** because turning a preset off requires `Preset_None`, a legacy
neighbour of a preset section cannot clear the preset without itself becoming a preset section.
Conversion is all-or-nothing per neighbourhood. Fine for OJZ act 1 (all nine convert).

**The comptime exclusivity `ensure` is enforceable, on a mechanism worth pinning.** An unbound
`Label = 0` param binds `Value::Int(0)`; `check_arg_class` only runs on supplied args; and
`raster != 0` on a `Value::Label` reaches `values_equal`, whose cross-variant arm returns
false, so `!= 0` is true. That is a *variant mismatch*, not a designed predicate, and there is
no precedent in the tree for comparing a `Label` param to an int. **Parcel A's probe must
include a two-line comptime witness for this**, and the intent belongs in a comment at the
`ensure` — if sigil ever diagnoses cross-class comparison, the `ensure` inverts silently to
always-pass.

### 5.3 One patched channel, generically named

Water is not a normal raster program. `Raster_InstallWater` (`raster.emp:607-623`) copies the
template into **`Raster_Buf_B`**, points both `Raster_Active_Buf` and `Raster_Program` at
Buf_B, and **clears `Raster_Pending`**, deliberately bypassing the ROM-program Buf_A path.
`Raster_PatchWaterLine` then writes into Buf_B unconditionally.

Routing water through an ordinary `raster:` field would put the live buffer on Buf_A while the
patch kept writing Buf_B: the water would render, at a wrong line, forever, never tracking the
camera.

**So the preset carries one generically-named patched channel** — `ep_patched` +
`ep_patch_world_y` — distinct from the static `ep_raster`.

**Why generic rather than water-specific (round 2):** `RasterGradientProgram`'s `rgp_arm0`
sits at byte offset **6**, identical to `WATER_TEMPLATE_ARM0_OFF`, and
`rgp_arm0 = raster_arm(1, top-1) = $8A00|(top-3)` is the *same formula* as
`water_arm0(M) = $8A00|(M-3)`; `rgp_arm1` is the constant `EVERY_LINE`, independent of `top`.
**`Raster_PatchWaterLine` therefore moves a dense gradient correctly with zero changes.** One
channel serves both, world-anchoring the gradient becomes nearly free, and the
"at most one patched effect" constraint becomes **structurally unrepresentable** rather than
checked. (The first draft's `ensure` for it was vacuous anyway — it quantified over a single
field.)

`Raster_Buf_B` is single (`RASTER_STATE_SIZE`, `raster.emp:184`), so one patched channel per
section is the true limit, and the struct now expresses exactly that.

**Three defects in the first draft's routing, all fixed here:**

1. **World-Y corruption.** `Raster_InstallWater` takes `d0 = water **screen** line` and
   *derives* world Y from the camera (`raster.emp:616-621`). Feeding it an authored
   `ep_patch_world_y` yields `world_y + Camera_Y`, so the boundary lands wrong on install and
   re-anchors differently on every re-entry. `Effects_InstallPreset` must instead copy the
   template, `move.w ep_patch_world_y, Raster_Water_World_Y`, and `jbsr
   Raster_PatchWaterWorldY` — i.e. `Raster_InstallWater` needs a world-Y entry point, or its
   screen-line seed must be split off.
2. **`ep_raster == 0` inside a present preset means `Raster_Program_None`, not "keep."**
   Inheriting `Raster_InstallSection`'s keep-current semantics would leave a previous
   section's water rendering forever — the mirror of §10 defect 1.
3. **Populating both `ep_raster` and `ep_patched` is forbidden by `ensure`.** Whichever runs
   last wins destructively: `Raster_InstallWater` clears `Raster_Pending`, killing a staged
   static program; the reverse order lets VBlank re-point `Active_Buf` to Buf_A while the
   patch keeps writing Buf_B.

**Teardown needs nothing explicit:** `Raster_VBlank`'s `.copy_program` re-points
`Raster_Active_Buf` at Buf_A whenever a `Pending` install is consumed (`raster.emp:331-338`),
so patched -> static is consistent.

**Rider:** `Raster_PatchWaterWorldY` is currently called every frame from the test loop only
(`games/sonic4/test/ojz_scroll_test.emp:379`). Promoting it to the engine loop requires gating
on "a patched channel is live."

**Pre-existing rider:** `Raster_InstallWater` copies a fixed `RASTER_BUF_SIZE` = 128 bytes from
templates that are 34-36 bytes, over-reading ~94 bytes of adjacent ROM into Buf_B. Harmless
today (never walked), but the DSL is about to make template lengths author-controlled, so the
constructor gets a `RASTER_BUF_SIZE` bound `ensure`.

### 5.4 Mixed fires: `SET_REG` must be first (ruling 14)

A fire mixing `OP_SET_REG` with a CRAM op switches its mode register roughly 45% across the
line; P2 measured that extending the delay costs ~40 cycles of a ~60-cycle budget and
deliberately did not take it (`raster.emp:164-167`). The shipped water **is** that mix
(`configs.emp:396-400`), so refusing it would break Parcel A's byte-compare.

The first draft's acknowledgment boolean is **replaced**. It was ritual by the second water
preset and could not see the worse case: `OP_SET_REG` writes with no delay
(`raster.emp:456-457`) while CRAM ops each burn `EFX_BLANK_DELAY` first (`:462-466`,
`:482-485`), so a `SET_REG` placed **after** a CRAM op executes strictly later in the line — a
worse artifact than the measured 45%, invisible to a boolean.

**The invariant:** in any mixed fire, `ensure` that `OP_SET_REG` is the **first** op, with the
measured 45% figure in the message. Checkable, actionable, and `OJZ_WaterRaster` already
satisfies it.

### 5.5 `EffectsPreset` field inventory

The first draft never declared one, and three sections silently disagreed about it. The
complete list, with **total-binding semantics** — every channel is written on install, `_None`
sentinels are used for "off", and 0 is illegal inside a preset except where noted:

| Field | Type | Notes |
|---|---|---|
| `ep_pal` | `*u8` | Required (§5.2) |
| `ep_parallax` | `*u8` | 0 = act default (the one legal 0, matching `parallax.emp:189-193`) |
| `ep_raster` | `*u8` | Static program; 0 illegal, use `Raster_Program_None` |
| `ep_patched` | `*u8` | Patched template (water or world-anchored gradient); 0 = none |
| `ep_patch_world_y` | `u16` | Meaningful only when `ep_patched != 0` |
| `ep_variants` | `[*u8; PAL_MAX_VARIANTS]` | Unused slots are 0 (clears) |
| `ep_cycle` | `*u8` | 0 illegal, use `Pal_Cycle_None` |
| `ep_transition` | `u16` | Cross-fade arm; **present but unused by any Parcel-C fixture**, so C's gate stays clean |

Roughly 36 bytes, not the ~20-24 the first draft estimated. No version field: the struct is
compile-time-linked rather than serialized. Layout must avoid an odd count of `u8` fields
before any pointer — sigil does not auto-align (`RasterGradientProgram.rgp_stream` sits at
offset 26), and even alignment is all the 68000 needs. Give it a `(size: N)` assertion.

Total-binding is what makes §10 defect 1 (water surviving one crossing) actually fixed;
keep-current semantics would not.

### 5.6 Install correctness

- **Write every variant slot**, but **skip the write when the pointer already matches.**
  `Palette_SetVariant` recomputes the `PAL_ACT_VARIANT` summary from both slots
  (`palette.emp:330-331`), so order is irrelevant and `[Variant_X, 0]` clears slot 1 properly.
  But every call also sets `PAL_ACT_VARIANT_STALE` (`:335`) even when re-binding an identical
  pointer, forcing a full re-derive (~19,332 cyc) at **every** crossing — including between
  two sections sharing a preset, on the frame already under streaming pressure. Both sibling
  installers already guard on "already live?" (`raster.emp:547`, `palette.emp:377`); match them.
- **`PAL_MAX_VARIANTS` cannot be raised past 2 without a fix first.** `palette.emp:323` uses
  `andi.w #(PAL_MAX_VARIANTS - 1), d0`, a power-of-two mask; 3 would silently fold slot 2 onto
  slot 0.
- **Install site:** `Parallax_CheckBoundary` (`parallax.emp:179-186`) is the single
  crossing-detection point and all consumers already take and preserve `a0 = Sec*`.
  `sec_effects != 0` routes to `Effects_InstallPreset` **instead of** the three legacy
  consumers, not in addition.
- **Spawn:** `Parallax_Init` picks its config before the first `CheckBoundary`, so a section-0
  preset with non-default parallax would lerp in over 16 frames at spawn unless init resolves
  the preset too. The first draft's "first section is not a hole" note covered variants only.
- **Install order:** the palette engine's compose order imposes nothing on install. The one
  real constraint is that `Palette_ArmFade` is a one-shot consumed by `Palette_LoadSection`
  (`palette.emp:269`, `:281`, `:300-303`), so a preset wanting a cross-fade must arm **before**
  the base load.
- **Frame-1 delta:** deleting the imperative install moves variant binding from init to update
  frame 1, so the first displayed frame shows un-varianted water. Expected; must not be read as
  a failed install in a press-frame capture.

---

## 6. Verified toolchain facts this design depends on

### 6.1 Computed-length arrays — PROBED AND CONFIRMED (2026-08-13)

> **RESULT: option C works end-to-end, verified on the real build path with a negative
> probe.** Ruling 7 stands; the padding fallback stays retired.
>
> | probe | result |
> |---|---|
> | `pub data Probe_Table: [u16; probe_words(2)] = [1, 2, 3, 4]` | **builds** (`len` 711252 -> 711264) |
> | same type, **3** elements | **fails**: `array length mismatch: expected 4 element(s), got 3` |
> | probe reverted | `crc=d792e8d6 len=711252`, byte-identical to the pre-probe build |
>
> The negative probe is what makes this meaningful: the comptime fn call was evaluated to
> 4 and **enforced**, so `[u16; raster_words(PROGRAM)]` is a real guard, not decoration.
>
> **New finding, and a trap for the plan: `const` does NOT enforce its declared array
> length — only `data` does.** The first attempt used a zero-byte
> `const PROBE: [u16; probe_words(2)] = [1, 2, 3]` to avoid changing the ROM; it compiled
> the 3-element value and only failed later, at an out-of-bounds index in a separate
> `ensure`. So a length guard written on a `const` is **vacuous**. Note this makes
> `engine/sound/sound_sfx.emp:1611`'s "THE LENGTH GUARD IS THE TYPE ANNOTATION" comment
> misattributed: the guard there holds because of the `pub data SfxEligTable: [u8;
> CHROUTE_COUNT] = SFX_ELIG` line beneath it, not the `const`'s own annotation. Every
> Phase-3 length guard must therefore sit on the `data` declaration. Worth a dedicated
> check in Parcel A, since it is exactly the vacuous-probe failure mode this codebase has
> been bitten by before.

### 6.1.1 Original reasoning (retained for the plan's benefit)

Sigil parses the array-size position with the full expression parser
(`sigil-frontend-emp/src/parser.rs:823-830`) and resolves it through `eval_const_index` ->
`eval_expr` -> `eval_call` into the user `comptime fn` table (`layout.rs:249-252, 327-352`;
`eval/call.rs:235-256`). Two doc comments state the intent (`layout.rs:1535-1537`,
`eval/mod.rs:1812-1813`). Only provisional forms (`bankid`, `extern`, `here()`) are refused.

This was the static reasoning; §6.1's table above is the measured confirmation.

**Method note for anyone re-running it:** there is no standalone `sigil emp` entry point —
the `sigil` binary takes an `.asm`, and `emp_census` / `emp_contracts` only inspect procs, so
neither exercises layout. The probe must go into an already-registered module and run through
`./build.sh`. The §5.2 `Label != 0` witness is still owed and belongs in Parcel A alongside
the `const`-vs-`data` guard check.

Two riders: the size expression is re-evaluated on every `resolve_type`, so `ensure`s inside a
length fn can double-report; and a comptime fn's return-type annotation is never enforced.

### 6.2 List-taking constructors work

Array-typed params bind (only refined params are class-checked), `for e in <array>` iterates,
`Array ++ Array` plus `comptime var` accumulates, and payload-carrying comptime enums exist for
heterogeneous descriptors.

### 6.3 Per-module registration cost, corrected

Byte-emitting modules live in a hardcoded Rust registry (`native.rs:217-255ff`). Per added
module, corrected by round 2:

- **A real pins `Region` is mandatory, not optional.** `DUMMY_REGION` collapses the section
  onto base 0 where it collides with `vectors` under the pinned-profile bootstrap — documented
  four times as failure chain 89 (`native.rs:400-441, 473-495`).
- **A `repin.toml` region with a `tests = [...]` entry**, which implies a **port test** (the
  `palette` region declares `tests = ["palette_port"]` at `:363-367`). The port-flip ritual
  (`--no-fail-fast`, full green) belongs in the gates and was missing.
- **A `map.toml` order slot** — note it is a section **head-label**, not a module name.
- **Rows in five frozen tables, not seven.** A sonic4-only module touches `s4`, `s4_debug`,
  `config_a`, `config_b`, `lean`; `demo`/`demo_debug` do not link it. The tables re-derive
  mechanically (`golden/derive_offcanonical_sizes.sh`), so the cost is running the ritual.

This corrected cost is what makes the one-module pack decision (§7) obviously right.

### 6.4 ROM cost

`EffectsPreset` ~36 B, eight presets ~290 B, eight raster programs ~320 B (largely replacing
retired fixtures), `sec_effects` 0 B. Roughly 700 B against a 696,788-byte ROM. The real
spatial constraint is the data region's headroom before the `$48000` org anchor. (The
often-quoted "31.8 KB free" is **RAM**; presets do not touch it.)

---

## 7. Dead data: the property is dropped (ruling 13)

**The property does not exist, and both round-2 auditors verified why independently.**
`synthetic_entry_src` (`native.rs:1606-1632`) emits `use <module_id>` for **every** registry
spec, so the BFS the earlier plan relied on (`resolve/mod.rs:793-839`) reaches every registered
module unconditionally. Since sigil has no item-level DCE, **a registered module always emits
all its bytes**, referenced by a `Sec` or not.

So "referenced family -> bytes, unreferenced -> zero" was false for exactly the modules it was
written about, and one-module-per-family would have bought eight registry entries, eight pins
regions, eight `map.toml` slots and eight sets of frozen-table rows for zero benefit.

**Decision: the starter pack ships as ONE module** (`games/sonic4/data/effects/`), one registry
entry, one pins region. The dead-data gate is deleted from Phase 3. At ~700 B the pack does not
need the property.

**The bonus survives, by a different mechanism.** `registry()` already varies its spec list by
build shape (`COMPRESSION_SELFTEST` is debug-only, `native.rs:240-242`). Retiring the P1/P2
fixtures at zero release cost is therefore done by **conditionally pushing a `ModuleSpec` in an
off-canonical profile** — not by unbinding from `Sec`, which achieves nothing. Ruling 5's
"equivalent coverage first" condition is satisfied that way.

**Falsifiable observation for the profile gating:** an unlowered module's labels never reach
`emit_listing`, so the gate is **symbol absence from `s4.lst`** — `grep`-checkable. The first
draft's "compare `data`-item spans in the `.lst`" is **mechanically impossible**: sigil's
listing carries a name and a 24-bit address per symbol and nothing else
(`sigil-link/src/listing.rs:63-93`). Spans could only be synthesized by differencing adjacent
addresses, which folds in alignment fill — measuring the placer, the very failure the rule
was invoked to avoid.

---

## 8. Testing and gates

### 8.1 Per-parcel gates

- **0 — attributed disappearance**, not "fixtures green" (§2.0).
- **A — all seven golden ROM comparisons stay green with no rebaseline.** That is the named,
  falsifiable reference (`sigil/crates/sigil-harness/golden/*.bin` plus `golden_crc32` per
  target), and it is only meaningful because A moves no data (§2.1). During development, the
  working instrument is a per-fixture comptime `ensure(dsl_output[i] == hand_words[i])`. Plus
  the helper-closure collision diff (§4.4) **before** the golden run, and the port-flip ritual.
- **C — behaviour-identical against a declared delta list.** The deltas are known in advance:
  frame-1 un-varianted water (§5.6), and water becoming per-section (which *is* §10 defect 1's
  fix). Artifacts: replay net green + the GATE-EVIDENCE captures re-run + the delta list.
- **D — four mid-motion oracle captures**, one per mechanism: variant region + S/H;
  world-anchored dense gradient (verified to move with camera Y); cycle; and **stacked regions
  — treeline plus a second static region, no water** (ruling 15). Captures must be
  replay-driven; press-frame screenshots are non-deterministic here.

Why ruling 15: the first draft called the stacked case "a single static program", but a static
water boundary is precisely the dynamic-made-static failure §5.3 exists to prevent — and routed
through the patched buffer instead, the single offset-6 arm word would move both boundaries
together. Removing water from that capture makes each gate test one thing.

**On the frame-latch, stated precisely** so the correction is not over-applied:
`emulator_read_cram` is frame-latched and cannot see a mid-frame CRAM write, so it is invalid
for `OP_CRAM` / `OP_PAL_REGION` / `OP_RUN_GRADIENT` sampling — measure the framebuffer there.
It **is** a valid instrument for a whole-frame `sec_pal` base palette DMA'd at VBlank.
(`configs.emp:409-410` still carries a stale comment claiming `run_to_scanline` + `read_cram`
for the *gradient* gate; that one must be corrected.)

### 8.2 Fixture retirement must preserve coverage

Coverage each fixture anchors:

- **`OJZ_TestRaster`** — sparse multi-op fire, the plain **`OP_CRAM`** path, `pal_dirty_mask`
  transience, with a discriminator entry chosen only after the first proved unfalsifiable under
  art (`configs.emp:288-296`). A water preset covers SET_REG + PAL_REGION but not plain
  `OP_CRAM` — so either one pack member uses `OP_CRAM`, or the narrowing is recorded explicitly.
- **`OJZ_TestPal`** — **cannot be replaced by real content, and the audit settled why.** The
  proposed build-time `ensure` that neighbouring palettes differ is unwritable: real section
  palettes are `embed()`ed blobs (`act_assets.emp:10`) and `embed` has no evaluator handling, so
  its bytes are lowering-time only. And there are no differing neighbours to prove — every OJZ
  section except section 2 passes the same `OJZ_Palette`. **Resolution: the `sec_pal` crossing
  gate keeps its comptime-authored palettes** (which is exactly what makes the `ensure`
  writable), retained via §7's profile gating rather than replaced.
- **`OJZ_TestGradient`** — seven measured ramp boundaries plus three deliberately different
  channel words at the same level, so a one-word stream desync is distinguishable from a
  one-line shift. This caught the real `T-1`/`T-2` off-by-one. A sunset **can** carry it with
  deliberately distinct per-entry ramps plus `ensure`-pinned boundaries; a sky chosen for looks
  alone cannot.
- **`OJZ_ShimmerCycle`** — survives on real content if entries and period stay known constants.

---

## 9. Explicitly out of scope

- **`.preset.json`, `tools/effects_gen.py`, all Aurora work** — Phase 4/5.
- **`SAT_SWITCH` reflections and `RUN_VSRAM`.** The shipped runtime op set is SET_REG / CRAM /
  PAL_REGION / RUN_GRADIENT only (`raster.emp:87-129`), though the parent spec's water
  definition names `SAT_SWITCH`. Every pack member, including the two range demos, stays inside
  the shipped op set.
- **Programs mixing sparse events with a dense run** — the wire format permits it, neither
  constructor can author it, and no pack member may need it (§4.1).
- **One universal raster constructor spanning both tiers** — a wire-format redesign.
- **Item-level dead-data pruning** — ruling 13 and §7.
- **Two independently patched effects in one section** — `Raster_Buf_B` is single; §5.3 makes
  the limit structural.
- **A seamless fully-submerged view** — the 3-line sliver at screen top belongs to the priming
  records. The DSL exposes frame-top init words, but no pack member depends on closing it.
- **Proving S/H on real content** — needs low-priority water tiles, i.e. regenerating block data
  through the editor pipeline (auto-commit-daemon territory, with uncommitted changes already in
  the tree). P2's measured 1.95x brightness step stands as the S/H evidence.
- **The reserved dense-tier register re-measurement** (ruling 12) — effect dressing does not
  populate a level, so the measurement could not support the ruling.
- **`sec_anim_blocks`** — separate DEFERRED_WORK entry.
- **The residual streaming-lag hunt** (~14% of frames on a diagonal stress traverse) — its own
  task; the instrument is a break on the `Lag_Frame_Count` increment, since averaged profiling
  cannot find a spike.

---

## 10. Pre-existing defects surfaced by the audits

To be recorded in `docs/BUGS.md`. Items 1-3 are real bugs; 4-6 are riders.

1. **Water survives exactly one section crossing.** Crossing from section 0 into section 1
   stages `OJZ_TestRaster` into Buf_A and destroys the water install permanently, because
   section 0's `sec_raster_table` is 0 = "keep current" (`raster.emp:544-554`). Parcel C's
   total-binding preset install is the fix.
2. **The cross-fade layer is unreachable.** `Palette_ArmFade` and `Palette_LoadCycle` have zero
   callers; `Palette_DoFade`, `Pal_Target`, and `PAL_FADE_FRAMES` are dead in the shipped ROM.
   `ep_transition` exists to claim them, but deliberately goes unused by any Parcel-C fixture so
   C's gate stays clean.
3. **A count-0 cycle script leaves cycling ACTIVE — and Parcel C would activate it.** In
   `Palette_InstallCycleSection` (`palette.emp:374-395`) the `ori.b #PAL_ACT_CYCLE` happens
   **before** the `channel_count == 0` test, so a non-NULL empty script ends with `PAL_ACT_CYCLE`
   set. `Palette_Compose` then takes `.cycling` and unconditionally sets
   `PAL_ACT_VARIANT_STALE` (`:432-434`) every frame, re-arming the exact 15.1%-of-frame derive
   the `ff0720ff` gate fix recovered. `Palette_LoadCycle` has the identical shape. Latent today
   because the empty-script path is documented (`:369`) but never exercised — **`Pal_Cycle_None`
   would exercise it**, so C must move the flag set after the count test.
4. `Raster_InstallWater` copies a fixed 128 bytes from 34-36 byte templates, over-reading
   adjacent ROM into Buf_B (§5.3).
5. `tools/effects_budget_model.toml:99` says `raster_state_bytes = 286`; `RASTER_STATE_SIZE` is
   288.
6. `act_sec_field_equs()` is un-gated against `harvest_engine_struct_offsets`, so any `Sec`/`Act`
   field rename silently leaves a dead equ (§5.1).

Also: `games/sonic4/data/editor/ojz/act1/export/act_descriptor.asm` (untracked, another
session's in-flight work, under the auto-commit daemon) emits a stale `Sec` layout.
`engine/structs.emp` is the authority, but expect a collision there.

---

## 11. Documentation obligations

- **`docs/ENGINE_ARCHITECTURE.md` §7** (`:3341`) — correctly targeted, but **already
  self-contradictory before Phase 3 touches it**: the banner (`:3343-3380`) says P2 shipped
  cycling, cross-fade and gradients, while §7.1's body (`:3392-3396`) still calls them PLANNED
  with "no shipped code", and §7.2 (`:3417-3419`) still attributes the sparse tier to
  `engine/system/hblank.emp`. **Reconciling that P2 drift is an explicit Parcel-C obligation**,
  not an incidental edit.
- **`docs/DEFERRED_WORK.md`** — the water/underwater hooks entry at `:229` and the dense-tier
  reserved-register entry at `:273`. Cite by line or heading: the file has two independently
  numbered lists and "entry 3 / entry 6" is ambiguous.
- **`docs/BUGS.md`** — the six items in §10.
- **`tools/effects_budget_model.toml`** — correct the header's generator-enforcement claim to
  match §4.3, and add the per-row symbol keys.
- **`configs.emp:409-410`** — the stale `run_to_scanline` + `read_cram` comment.
- **`repin.toml` / `native.rs` doc comments** — this codebase treats those as the placement
  rationale of record (see the failure-chain-89 comments).

---

## 12. Audit provenance

Two rounds, six agents, six lenses, because the parcel is large and its merge ritual expensive.

**Round 1** (architecture / feasibility / scope, against the first draft) changed: the `Sec`
field strategy, water's buffer routing, the mixed-fire rule, the one-call-site ergonomic, the
sparse/dense split, the pruning approach, the budget-model gate, the import-hygiene fix, and the
parcel count.

**Round 2** (fix verification / unaudited sections / plan readiness, against the committed spec)
changed: the dead-data property (deleted — the mechanism does not exist), the `.lst` gate method
(impossible), Parcel A's contents (comptime-only) and its named reference (the seven goldens),
the mixed-fire invariant (`SET_REG`-first), the patched channel (generic, which makes gradient
world-anchoring nearly free), the stacked-regions gate (no water), `sec_pal` (resolved, not
deferred), the `EffectsPreset` field inventory (created), the Repos column (all four paired),
the T-1 tier conflation, and three previously-unknown defects (§10.1-3).

Round 2 also found that a fix can be worse than the defect it closes — the acknowledgment
boolean — and that a gate can be true by construction — Parcel 0's original "fixtures green".
Both are recorded here rather than in a transcript so the next design does not repeat them.
