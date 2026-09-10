# Can `Game.SCANLINE_CAPS` be derived from the scene registry's fold?

**Answer: NO — and the blocker is not the one that was hypothesised.**

The hypothesis under test was a comptime ORDERING/CIRCULARITY constraint between the
engine/game interface binding and the game-data registry that supplies the fold. That
constraint is real in one narrow place (B4), but it is **not** what forbids the
derivation. The derivation is forbidden first and fatally by a **domain gap**: three of
the ten declared bits are raised by things that are not scenes, and `fold_caps()` cannot
emit them at all. No ordering fix reaches this.

---

## A. Verified coordinates

Every coordinate in the brief was checked by symbol and content. All four are **exact**.

| Claim | Verified |
|---|---|
| `games/sonic4/config/game.emp:145` — `const SCANLINE_CAPS = $0FDE`, hand-written literal | EXACT |
| `games/demo/config/game.emp:20` — `const SCANLINE_CAPS = 0` | EXACT |
| `games/sonic4/data/effects/scene_registry.emp:494` — `pub const SceneRegistry_CapsFolded = fold_caps(SCENES)` | EXACT |
| guards around `:459-:492` and `:596-:613`; `CAP_ROW_REMAP` arm at `:488` | EXACT (`:488` is the `ensure`, `:489` its message) |

Two corrections to the surrounding prose, both doc-rot:

1. **`scene_registry.emp:428-431` is STALE.** Its hand-derived expectation block concludes
   `$0002|$0004|$0008|$0010 = $001E, which is EXACTLY the declared Game.SCANLINE_CAPS —
   the subset test below passes with zero slack.` The declared mask is now **`$0FDE`**,
   and the fold is a strict subset with substantial slack. The "zero slack" sentence has
   been false since at least the item-3 drift adoption (2026-09-02).
2. **The `:489` message says "THREE-file retreat" and then enumerates six steps across
   four files** (`game.emp`, `parallax.emp`, `engine/ram.emp`, `scene_registry.emp`) plus
   a data emission. The count in the message under-reports its own instructions.

## B. Why the derivation is impossible — four independent blockers

### B1. THE FATAL ONE: the declared mask's domain is strictly larger than `fold_caps`' codomain

`scene_caps()` (`engine/level/scene_dsl.emp`) has exactly seven accumulator arms, and
they can raise only:

```
$0002 CAP_PER_COL_VSRAM   $0004 CAP_DEFORM   $0008 CAP_ANCHORS
$0020 CAP_MULTI_DEFORM_TABLE   $0040 CAP_FACTOR_CURVE
$0080 CAP_BAND_DRIFT   $0800 CAP_ROW_REMAP
```

`fold_caps()` ORs those over the registry and adds `$0010 CAP_TRANSITIONS` on
`scenes.len > 1`. So the **entire codomain** of `fold_caps` is `$08FE`.

```
fold_caps codomain (max) : $08FE
declared                 : $0FDE
declared NOT foldable    : $0700
```

`$0700` is three real, load-bearing, currently-declared bits:

- **`$0100 CAP_ANCHOR_MOTION`** — gates spans in `engine/effects/raster.emp`
  (`:2205`, `:2317`). Motion is a property of a raster program's anchor, not of a
  scene; `scene_caps()` never inspects one.
- **`$0200 CAP_DENSE_TIER`** — gates **construction** of a dense-tier ramp program. Its
  subject is `OJZ_TestRamp`, which `game.emp`'s own comment calls "a gate fixture that
  never renders". It is in **no** scene registry. Worse, three live `ensure`s *require*
  the bit — `games/sonic4/data/effects/ojz_effects.emp:1252` and
  `games/sonic4/data/generated/ojz/act1/effects_scenes.emp:232` and `:265` — so a fold
  that omitted it would **fail the build**, not merely under-declare.
- **`$0400 CAP_ROLE_SWAP`** — gates five sites in `engine/level/parallax.emp`
  (`:1125`, `:1643`, `:1801`, `:2702`, `:3179`). A plane-role swap is a runtime
  arrangement, not a scene field.

A derived mask would clear all three. That is not a tautology; it is a regression that
turns three shipped features off and breaks the build on the fourth.

### B2. The engine sizing constants CANNOT read the caps — this kills the fallback too

This is `docs/EMP_PITFALLS.md` §9, and `engine/level/parallax.emp:150` carries its own
banner titled *"WHY BAND_EXT_N IS A PINNED LITERAL AND NOT A FOLD OF Game.SCANLINE_CAPS"*.
The spelling was **written, built, and rejected twenty times over** — `unknown name
Game.SCANLINE_CAPS`, once per emitted config record. Three contexts bind no contract
member: an emitted `data` binding's record-type layout, `harvest_engine_struct_offsets`,
and `harvest_engine_ram_addresses`.

So `BAND_EXT_N` / `BAND_CURVE_N` / `BAND_DRIFT_N` / `BAND_REMAP_N` and their
`engine/ram.emp` `*_BYTES` mirrors are pinned literals **by compiler refusal, already
measured**. Substituting `SceneRegistry_CapsFolded` for `Game.SCANLINE_CAPS` does not
help: `parallax.emp` is engine and may not import game data (the engine/game wall), and
the harvest contexts are one file plus `types.emp`.

**This is the brief's own proposed fallback — "derive only the engine-side sizing
constants from the fold while the cap mask stays declared" — and it has already been
tried and refused.**

### B3. Derivation would INVERT the guard it is meant to make tautological

The verify is one-sided **on purpose** (`scene_registry.emp:496-500`, and
`engine/system/game_contract.emp:30-33`): a declared SUPERSET only forgoes a
specialisation; a declared SUBSET is a wrong picture on hardware.

`CAP_DENSE_TIER`'s gate is the clearest case. Its message reads: *"a game must declare
intent to spend the dense tier's ramp axis before it may author one."* The declaration is
a **precondition on authoring**. Deriving the declaration *from* the authoring makes the
gate unfalsifiable — authoring would auto-grant the permission the gate exists to
withhold. The guards would not become tautological; they would become **vacuous**, which
is this tree's most expensive recurring failure (`EMP_PITFALLS.md` §10, §12).

### B4. The circularity is REAL, but it is at the TOOL level, not the comptime level

There are **two** independent scene populations folded against the same declared mask:

- `SceneRegistry_CapsFolded = fold_caps(SCENES)` — `scene_registry.emp:494` (hand-authored)
- `EditorScenes_OJZ_Act1_CapsFolded = fold_caps(EditorScenes_OJZ_Act1)` — `effects_scenes.emp:161` (**generated**)

The generated one is emitted by `tools/effects_gen.py`, which reads the declared mask
**textually, by regex demanding a literal**:

```python
# tools/effects_gen.py:1994
m = re.search(r"^\s*const SCANLINE_CAPS\s*=\s*(\$?[0-9A-Fa-f]+)\s*(?://.*)?$", ...)
# :1997 -> _refuse("no `const SCANLINE_CAPS = <literal>` declaration ...")
```

So the generator that produces half the folded population consumes the value that would
be folded from it. Replacing the literal with `fold_caps(...)` makes `effects_gen.py`
**refuse outright**, by design and with its own message. Three further tools parse the
same literal with the same shape: `tools/row_remap_gate.py:122`, `tools/scene_spans.py:43`,
`tools/waterline_art_gate.py`. Two more derive span expectations from it
(`tools/demo_specialization_witness.py:521/541`, `tools/effects_gates.py:1222`).

**None of these can evaluate a comptime fold.** This is the blocker an identifier grep
finds and reasoning does not.

## C. The stated historical reason has EXPIRED, and it is not the current one

`games/sonic4/config/game.emp:22-26` explains itself:

> DECLARED as a literal rather than computed because the registry it would fold
> (`SceneRegistry_CapsFolded`) does not exist until Task 5, while adding the interface
> member obliges BOTH games to bind it immediately or contract closure fails.

Task 5 has landed; `SceneRegistry_CapsFolded` exists. **That reason is dead.** Anyone
reading only this comment would conclude the derivation is now unblocked. It is not — it
is blocked by B1-B4, none of which this comment mentions. The comment should be corrected
whether or not anything else here is acted on.

## D. Consumer enumeration, and how it was built

Built by **what touches the value**, not by identifier grep alone — the two are different
questions and neither is a superset (this tree's standing finding).

**Comptime consumers that GATE CODE EMISSION** (`if (Game.SCANLINE_CAPS & CAP_*) != 0`),
22 sites:

| File | Sites | Bits |
|---|---|---|
| `engine/level/parallax.emp` | 17 | `ROLE_SWAP`x5, `TRANSITIONS`x3, `PER_COL_VSRAM`x3, `BAND_DRIFT`x3, `FACTOR_CURVE`x3, `ROW_REMAP`x3, `DEFORM`x2, `ANCHORS`, `MULTI_DEFORM_TABLE` |
| `engine/effects/raster.emp` | 4 | `DENSE_TIER`, `ANCHORS`, `ANCHOR_MOTION`x2 |
| `engine/level/bg_anim.emp` | 1 | `ROW_REMAP` (`:440`) |

**Comptime consumers that SIZE something — the critical class.** These do **not** read
`Game.SCANLINE_CAPS` (they cannot, per B2); they are **pinned literal mirrors** held to it
by two-directional `ensure`s in `scene_registry.emp`:

| Constant | Site | Value | Pinned by |
|---|---|---|---|
| `BAND_EXT_N` | `parallax.emp` | 0 | `scene_registry.emp:459` + `:461` |
| `BAND_CURVE_N` | `parallax.emp` | 1 | `:468` + `:470` |
| `BAND_DRIFT_N` | `parallax.emp` | 1 | `:476` + `:491` |
| `BAND_REMAP_N` | `parallax.emp` | 1 | `:482` + `:484` |
| `BAND_*_BYTES` | `engine/ram.emp` | mirrors | same commit, per each banner |

**Comptime guards** (`ensure`): `scene_registry.emp:459,461,468,470,476,482,484,488,491,596,611,613`;
`effects_scenes.emp:162,232,265`; `ojz_effects.emp:1252`; `scene_equiv_proof.emp:355`;
`poison_scene_mask.emp`, `poison_scene_own_caps.emp` (fixtures).

**Contract surface**: `engine/system/game_contract.emp:43` — `const SCANLINE_CAPS: u16`.
Note `:37` — the width is **documentary only**; sigil range-checks no const member, so
the registry's `ensure` is the whole guard on that word.

**Non-comptime (build-tool) consumers** — the class reasoning misses:
`tools/effects_gen.py` (regex, `_refuse`s a non-literal), `tools/scene_spans.py`,
`tools/row_remap_gate.py`, `tools/waterline_art_gate.py`,
`tools/demo_specialization_witness.py`, `tools/effects_gates.py`,
`tools/test_effects_gen.py`, `tools/test_scene_span_labels.py`.

## E. THE EXPERIMENT — the derivation was made, and it was refused twice

Not settled by reasoning. A throwaway edit put the derivation in and built it. Tree
restored from the committed baseline afterwards (`git checkout -- games/sonic4/config/game.emp`,
verified clean, `:145` back to `$0FDE`).

**Control, established first:** `FAST=1 DEBUG=1 ./build.sh` on the unmodified branch —
**EXIT=0**.

**The edit (E1):**

```emp
use engine.level.scene_dsl.*
use games.sonic4.scene_registry.{SCENES}
...
    const SCANLINE_CAPS = fold_caps(SCENES)      // was $0FDE
```

### E1a — refused at the TOOL layer, before sigil ever ran

`FAST=1 DEBUG=1 ./build.sh` — **EXIT=1**, and the build never reached the assembler:

```
effects_seam_gate: FAIL — a preset document does not load, so this gate cannot tell which
chooser each bound section owes — the arm is the document's own property:
.../games/sonic4/config/game.emp: no `const SCANLINE_CAPS = <literal>` declaration. Every
game declares the scanline services it wants lowered; without it the capability check on
`patch_motion` cannot run, and a check that cannot run must not pass.

ERROR: the editor-scene binding seam is broken in the SOURCE — see above.
```

That is B4 firing first, with its own message. Note its last clause — *"a check that
cannot run must not pass"* — which is precisely the disposition the audit's
"decline and announce" would reverse.

### E1b — sigil's own refusal, obtained by invoking it directly

Bypassing the gate (`sigil build --aeon . --native --game sonic4`) gave **EXIT=1, 30
errors**. Two distinct failures, and the first is a `.emp` pitfall:

**(i) `EMP_PITFALLS.md` §2 — a comptime fn's free names resolve at the CALL SITE.**
Twenty-one of the thirty errors:

```
./games/sonic4/data/effects/scene_registry.emp:345:5: [Error] unknown name `Scene_OJZ_Default`
./games/sonic4/data/effects/scene_registry.emp:346:5: [Error] unknown name `Scene_OJZ_Underwater`
... 21 of these, one per scene ...
```

`SCENES`' elements are barewords for `Scene_*` consts that `scene_registry.emp` pulls in
with `use games.sonic4.ojz_scenes.*` (`:332`). Importing `SCENES` moves the array; **the
element names do not travel.** The fold therefore evaluated over twenty-one unresolved
names. Note the blame site: `scene_registry.emp:345-368` — the **innocent file**. The
author of `game.emp` supplied none of those lines. This is §2 and §8's signature.

**(ii) The mask silently collapsed to `$0010`.** Every downstream message reports
`Game.SCANLINE_CAPS = 16` — only `CAP_TRANSITIONS`, the one bit `fold_caps` adds from
`scenes.len > 1` regardless of content. The remaining nine errors are the whole guard
lattice firing at once, each with its own text:

```
scene_registry.emp:470  BAND_CURVE_N is 1 but this game does NOT declare CAP_FACTOR_CURVE (Game.SCANLINE_CAPS = 16)
scene_registry.emp:484  BAND_REMAP_N is 1 but this game does NOT declare CAP_ROW_REMAP (= 16)
scene_registry.emp:491  BAND_DRIFT_N is 1 but this game does NOT declare CAP_BAND_DRIFT (= 16)
scene_registry.emp:613  the folded capability mask 2270 is NOT a subset of Game.SCANLINE_CAPS 16
ojz_effects.emp:1252    OJZ_TestRamp: ... does not declare CAP_DENSE_TIER
effects_scenes.emp:162  editor scenes: the folded capability mask 88 is NOT a subset of ... 16
effects_scenes.emp:232  EditorRaster_OJZ_Act1_aurora_ramp_witness: ... does not declare CAP_DENSE_TIER
effects_scenes.emp:265  EditorRaster_OJZ_Act1_ramp_probe: ... does not declare CAP_DENSE_TIER
scene_equiv_proof.emp:355  ... the lowered band record is 32 bytes against the legacy entry's 10
```

### E1c — the compiler independently confirmed B1's arithmetic

`:613` and `:162` print the folds computed **where the names do resolve**:

| quantity | measured | hex |
|---|---|---|
| `SceneRegistry_CapsFolded` | 2270 | **`$08DE`** |
| `EditorScenes_OJZ_Act1_CapsFolded` | 88 | **`$0058`** |
| declared `SCANLINE_CAPS` | 4062 | **`$0FDE`** |

`declared & ~(registry fold) = $0700`; `(registry fold) & ~declared = $0`.

So the true union of every folded population is `$08DE`, the declared mask is `$0FDE`,
and the difference is **exactly** the `$0700` predicted in B1 from reading `scene_caps()`
— `CAP_ANCHOR_MOTION | CAP_DENSE_TIER | CAP_ROLE_SWAP`. This is the compiler's own
number, not my reading of the source. **B1 is measured, not argued.**
