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

**Comptime consumers that GATE CODE EMISSION** (`if (Game.SCANLINE_CAPS & CAP_*) != 0`).
Counted mechanically, comment lines excluded — **29 live sites**:

| File | Live sites |
|---|---|
| `engine/level/parallax.emp` | 24 |
| `engine/effects/raster.emp` | 4 |
| `engine/level/bg_anim.emp` | 1 (`:440`, `ROW_REMAP`) |
| `engine/level/scene_dsl.emp` | 0 (its one occurrence is inside a comment) |

Per bit, across `engine/` (30 occurrences including the one commented
`CAP_ANCHORS` in `scene_dsl.emp:206`):

`ROLE_SWAP` 5 · `ROW_REMAP` 4 · `TRANSITIONS` 3 · `PER_COL_VSRAM` 3 ·
`FACTOR_CURVE` 3 · `BAND_DRIFT` 3 · `ANCHORS` 3 · `MULTI_DEFORM_TABLE` 2 ·
`DEFORM` 2 · `ANCHOR_MOTION` 2 · `DENSE_TIER` 1.

The `ROLE_SWAP` count of 5 independently matches `game.emp`'s own claim of "five sites",
which is a small check that the counting method agrees with the tree's own record.

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

## F. B5 — THE TRILEMMA: no spelling transports the fold's value into the binding

B1 says the fold is the wrong *value*. This says it cannot be *delivered* either. Since
`$0700 | $08DE = $0FDE` exactly, a hybrid that declares only the non-foldable bits and
imports the rest would reproduce the shipped mask byte for byte — so it is worth knowing
that it is unreachable for an independent reason. All three spellings were built.

| # | Spelling in `games/sonic4/config/game.emp` | sigil result |
|---|---|---|
| **E1** | `use games.sonic4.scene_registry.{SCENES}` + `fold_caps(SCENES)` | 30 errors. `unknown name Scene_OJZ_Default` x21 **blamed on `scene_registry.emp:345-368`**; mask silently folds to `$0010` |
| **E2** | `use ...scene_registry.{SceneRegistry_CapsFolded}` + `$0700 \| SceneRegistry_CapsFolded` | `./games/sonic4/data/effects/scene_registry.emp:494:38: [Error] unknown function `fold_caps`` |
| **E3** | `use games.sonic4.scene_registry` (whole path), same expression | `./games/sonic4/config/game.emp:147:35: [Error] unknown name `SceneRegistry_CapsFolded`` |

All three are `EMP_PITFALLS.md` §2 — free names resolve at the **call site** — wearing
three different hats:

- **E1**: the array travels, its **element barewords do not**.
- **E2**: a selective `use` of a `const` **clones its initializer, not its value**, and
  re-evaluates the clone in the consumer's scope, where `fold_caps` is not in scope.
- **E3**: a whole-path `use` **elaborates** the module but **injects no names**.

E2 is not a new discovery — **`scene_registry.emp:17-21` already documents it verbatim**,
predicting the exact error string this experiment produced:

> The name-list form alone is a trap for the CLOSURE: a selective
> `use ...{SceneRegistry_CapsFolded}` injects a CLONE of the const whose initializer
> re-evaluates in the CONSUMER's scope, so it reports `unknown function fold_caps` at a
> span inside THIS file while never elaborating this module at all.

E2 and E3 are the two halves of a vice: the form that injects the name cannot carry the
value, and the form that elaborates the value cannot inject the name.

**This is the genuine comptime constraint the brief hypothesised** — just not the
mechanism it guessed. It is not "the engine sizes RAM from caps, and the registry depends
on engine types, therefore a cycle". It is that a `.emp` `const` is not a transportable
value across a module boundary at all: it is an expression re-elaborated wherever it is
named. Note also that **all three diagnostics point at the wrong file or the wrong
symbol** — none says "cycle", none says "game.emp asked for this".

## G. Not reachable — so, the fallback, priced honestly

### G1. The brief's own fallback is the one already refused

*"Deriving only the engine-side sizing constants from the fold while the cap mask stays
declared"* is B2. It was written, built, and rejected — `unknown name Game.SCANLINE_CAPS`,
twenty times, one per emitted config record (`EMP_PITFALLS.md` §9;
`parallax.emp:150`'s banner; `docs/benchmarks/scanline-p3/EXTENDED-RECORD.md`). Nor can it
read `SceneRegistry_CapsFolded` instead: `parallax.emp` is engine and the engine/game wall
forbids importing game data, and by F the const would not transport anyway.

### G2. The smallest change that genuinely shortens the retreat — and it is not a derivation

The coupling that costs the owner his edits is **not** cap-mask-to-scene. It is
**cap-bit ↔ `BAND_*_N` ↔ `BAND_*_BYTES`**: three numbers in three files that must move in
one commit and that **cannot see each other**, purely because §9 blinds the layout and
harvest contexts to contract members.

The fix for that is already identified, already booked, and is a **sigil** change, not an
aeon one: expose each game's declared caps as an **`emp_defines` row**, the way
`MAX_RING_BUFFER` already is. `parallax.emp:157-161` states the evidence that makes it
concrete rather than speculative — *"A build DEFINE **is** visible there: driving
`BAND_EXT_N` off `DEBUG` sized the record and built byte-identically."*

With that in place `BAND_REMAP_N` and `BAND_REMAP_BYTES` derive from the define and stop
being hand-edited. It also buys the thing the pinned literals cannot do today at all:
**two games that disagree about a bit** (today `demo` pays every widened band record for
capabilities it will never use).

**Recommend: do not attempt the derivation. Push the `emp_defines` row.** It is the only
change measured to work in the contexts that matter.

## H. The owner's actual case, counted

The waterline is `rowRemap: SceneRemap.Ladder(RowRemapLadder_Waterline16, 101, 4)` at
**`games/sonic4/data/effects/ojz_scenes.emp:347`**, on `Scene_OJZ_Underwater`'s layer 1.
Note that file is a **fifth** file the `:489` message does not name.

**Today, to turn it off — 5 files, 7 edits:**

| # | File | Edit |
|---|---|---|
| 1 | `games/sonic4/data/effects/ojz_scenes.emp:347` | delete the `rowRemap:` ← **the edit he wanted** |
| 2 | `games/sonic4/config/game.emp:145` | `$0FDE` -> `$07DE` |
| 3 | `engine/level/parallax.emp` | `BAND_REMAP_N = 1` -> `0` |
| 4 | `engine/ram.emp` | `BAND_REMAP_BYTES` -> `0` |
| 5 | `games/sonic4/data/effects/scene_registry.emp` | flip the `:488` arm to `== 0`; drop the 272-byte `RowRemapLadder_Waterline16` at `:841`; correct the `CapsExpected` prose |

**With a derived cap mask, had it been reachable: 4 files, 6 edits.** Only row 2 goes
away. Rows 3-5 are exactly the ones §9 forbids deriving.

**This is the part of the proposal that does not survive.** The derivation was supposed to
collapse the three-file retreat to a one-file edit. Measured against the real case, it
removes **one** edit of seven — and costs the `CAP_DENSE_TIER` construction gate to do it.

**With the `emp_defines` row (G2): 3 files, 4 edits** — rows 3 and 4 vanish entirely.
Still not one edit, because clearing the bit (row 2) and retiring the now-unreferenced
272-byte table (row 5) are real, deliberate consequences that a human should see.

**The one-sentence answer:** with the proposed derivation in place the owner would still
have had to touch **four files and make six edits** to turn that waterline off — one fewer
than today — whereas the already-booked `emp_defines` change gets him to **three files and
four edits**, which is why the sizing constants, not the cap mask, are the thing to fix.

## I. The strongest argument against this conclusion

**B1 is contingent, not fundamental — and I have stated it too much like a theorem.**

`scene_caps()` has no arm for `$0700` because nobody wrote one, not because scenes are
incapable of expressing those capabilities. `CAP_ROLE_SWAP` is a plausible scene field.
`CAP_ANCHOR_MOTION` is a property of raster programs, and raster programs *are* registered
game data — a fold over that population is conceivable. Extend the fold's domain and
`$0700` folds; B1 evaporates. So B1 is a statement about **today's `scene_caps()`**, and a
determined implementer could dissolve it.

**And B3 is narrower than I wrote it.** Deriving the *whole* mask inverts the
`CAP_DENSE_TIER` gate — that holds. But it says nothing against a **hybrid** that leaves
the intent-declaring bits declared and derives only the foldable ones. B3 is an argument
against the pure derivation the brief proposed, not against every derivation. What
actually kills the hybrid is F (the trilemma), not B3 — and F is a property of **sigil
`af35fa561663`**, which is under active development in a repo that has already changed
comptime semantics twice this month (`EMP_PITFALLS.md` §12, §13). A sigil that let a
`const` export its *value* would reopen this.

So the honest scope of the answer is: **not reachable on sigil `af35fa561663` with today's
`scene_caps()` domain** — not "impossible in principle". The durable finding is not the
"no"; it is **H**: even granting the derivation everything it wants, it removes one edit of
seven, and the edits that actually hurt are blocked by §9, which a derivation does not
touch.

**Where the brief's reasoning holds up, and it is the main point.** The claim that these
guards prevent a genuinely inconsistent state rather than merely policing waste is
**correct, and E1 is evidence for it**: a single half-done retreat was caught in nine
independent places, each naming a different concrete consequence (bytes per band, RAM that
nothing advances, a gated pass reading a record base as a ROM pointer). A
"decline and announce" softening would let all nine through. `effects_seam_gate`'s own
refusal states the principle better than I can: *"a check that cannot run must not pass."*
