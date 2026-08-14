# Effects P3 Parcel A, Task 1 — capability probe

Date: 2026-08-13 · branch `feat/effects-p3-parcel-a` · worktree `aeon/.worktrees/p3a`
sigil: `sigil/.worktrees/p3a/target/release/sigil`

Purpose: before Task 6 builds a raster/palette authoring vocabulary on top of them, establish
**with negative controls** that the `.emp` constructs the vocabulary needs actually work on this
tree. Payload-carrying `comptime enum`s in particular had **zero existing usage anywhere in the
codebase** before this probe. Also pays the two toolchain debts the design spec left owed
(spec 6.1 / 5.2): the `Label != 0` "is it bound?" witness, and the `const`-vs-`data` length-guard
asymmetry.

The probe was temporary. It has been stripped; `engine/effects/raster_dsl.emp` now holds only its
module header for Task 6 to fill. `games/sonic4/data/parallax/configs.emp` keeps
`use engine.effects.raster_dsl.*` so the module stays reachable.

Baseline and every green build: **`crc=fedcf197 len=696836`** — the probe emitted zero ROM bytes.

## Results

| # | Construct probed | Result |
|---|---|---|
| 1 | `comptime var` accumulation across a `for` + `++` inside a `comptime fn`, reaching the fn-level var | PASS |
| 2 / 2b | Flattened value correct element-by-element (payload destructuring order preserved) | PASS |
| 3 | An INDEPENDENT size path (`match` arms returning counts) agrees with the concatenation path | PASS |
| 4 | A `Label` param defaulted to `0` compares EQUAL to `0` (the "unbound" half of the idiom) | PASS |
| 5 | Negative half: a **bound** `Label` compares NOT-equal to `0` | PASS (negative control fired) |
| 6 | Declared array length on a `const` is **vacuous**; on a `pub data` it is **enforced** | PASS (both halves) |

Payload-carrying `comptime enum` + `match` destructuring works, including the mixed case
(`ProbeOp.B(3, [4, 5, 6])` — an *array* passed through a payload slot declared `int`; payload
types are not enforced) and the zero-payload arm returning `[]`.

## Negative controls — exact message text

Every one of these was produced by an actually-failing build. An `ensure` that cannot fail is the
precise failure mode this task was written about, so each is quoted verbatim.

**Step 4** — PROBE 1 flipped to `PROBE_OUT.len == 8`:

```
  [Error] PROBE 1: expected 7 words, got 7 @ Span { source: SourceId(9), start: 1220, end: 1296 }
```

This also proves the module is genuinely **walked and evaluated** (a pure-comptime module that
nothing imports would let every `ensure` pass silently), and that `{...}` interpolation in the
message is live.

**Step 5** — `probe_label_bound(sym: <a real bound label>)`:

```
  [Error] PROBE 5 NEGATIVE: a BOUND Label must NOT equal 0 @ Span { source: SourceId(9), start: 2489, end: 2597 }
```

So `Label != 0` really does discriminate bound from unbound; PROBE 4 is not a tautology. **The
witness spec 6.1 owed is paid.** Standing caveat unchanged: this rests on `Value::Label` vs
`Value::Int` being a *variant mismatch* in `values_equal`'s `_ => a == b` arm, not on a designed
predicate. If sigil ever diagnoses cross-class comparison, PROBE 4 inverts silently to
always-pass — any future re-probe must keep the negative half.

**Step 6** — the same `[u16; probe_guard_len(2)]` annotation on a `pub data` carrying 3 elements:

```
  [Error] array length mismatch: expected 2 element(s), got 3 @ Span { source: SourceId(9), start: 2798, end: 2858 }
```

while the identical annotation on a `const` built green and `PROBE_GUARD.len == 3` held. The
spec's inherited claim is **verified on this tree**: a length guard is real only on `data`.
Consequence for Task 6 — a declared length on a `const` buys nothing; put the guard on the
emitted `data`, or assert with `ensure`.

## Deviations from the task text (and why)

Three, all forced by the grammar/loader; none replaces a probed construct.

1. **Untyped `comptime fn` params are not expressible.** `comptime fn probe_build(ops) { … }`
   fails to parse — the annotation is mandatory (`parser.rs::comptime_fn_decl` does
   `expect_ident` then `expect(Colon)`):

   ```
   ./engine/effects/raster_dsl.emp:22:28: error: expected `:`, found RParen
   ./engine/effects/raster_dsl.emp:22:28: error: expected name, found RParen
   ```

   A syntax survey of list-parameter spellings, each fed a **four**-element array:

   | Spelling | Parses | Enforced at bind |
   |---|---|---|
   | `xs: [int; 3]` | yes | **no** — a 4-element list binds and `xs.len == 4` |
   | `xs: [int]` (slice) | **no** — `error: expected `;` in array type, found RBracket` | n/a |
   | `xs: array` | yes | no |
   | `xs: list` | yes | no |
   | `xs: Data` | yes | no |

   Only `Type::Refined` (`where LO..HI`) params are checked at bind; everything else is loosely
   typed, so any name parses and means nothing. The probe used `xs: array` as the honest generic
   spelling. **Task 6 should adopt one spelling as a convention** (`array` recommended) and not
   mistake `[T; N]` on a parameter for a checked length — it is not one.

2. **A glob-imported module must export at least one `pub` name.** With every probe item private,
   the build failed with:

   ```
     [Error] glob `use engine.effects.raster_dsl.*` matches no module with `pub` names
   ```

   The probe fns were marked `pub`. Task 6's `raster_dsl.emp` will have `pub` names anyway, but
   the interim state must not be all-private or the glob import in `configs.emp` hard-errors.

   This makes the two halves of the task's Step 7 mutually exclusive: "leave only the module
   header" and "leave the `use … .*` line in `configs.emp`" cannot both hold, because the stripped
   module then exports nothing. Resolved in favour of the green build (the parcel's hard
   constraint) plus reachability: the stripped module carries a single documented
   `pub const RASTER_DSL_PLACEHOLDER = 0`, which emits no bytes. **Task 6 deletes it** as soon as
   real vocabulary is exported.

3. **Step 5 used `Raster_Program_None` (a `pub data` in `engine.effects.raster`) rather than
   `OJZ_TestPal`.** `OJZ_TestPal` lives in `configs.emp`, which glob-imports `raster_dsl` —
   naming it from inside `raster_dsl` would be a circular import. `Raster_Program_None` is an
   equally real bound label reachable without a cycle. As the task noted, an explicitly-supplied
   literal `0` for a `Label` param is a hard error; only the *default* path skips the class check.
