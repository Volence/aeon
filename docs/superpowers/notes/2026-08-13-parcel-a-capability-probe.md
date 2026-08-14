# Effects P3 Parcel A, Task 1 — capability probe

Date: 2026-08-13 · branch `feat/effects-p3-parcel-a` · worktree `aeon/.worktrees/p3a`

**Compiler under test** (a capability result means nothing without one — this tree has documented
traps for stale sigil binaries and for aeon/sigil pairing):

| | |
|---|---|
| sigil | `476a5bd9` ("Merge parcel/lens-sweep-refreeze"), worktree `sigil/.worktrees/p3a`, tree clean |
| sigil binaries | `target/release/{sigil,emit_sound_blob}`, built 2026-08-13 20:31, i.e. **after** that commit's 18:55 timestamp — not stale |
| aeon base | `ffe05158` ("docs(plan): Effects P3 Parcel A") |

Purpose: before Task 6 builds a raster/palette authoring vocabulary on top of them, establish
**with negative controls** that the `.emp` constructs the vocabulary needs actually work on this
tree. Payload-carrying `comptime enum`s in particular had **zero existing usage anywhere in the
codebase** before this probe. Also pays the two toolchain debts the design spec left owed: the
**§5.2** `Label != 0` "is it bound?" witness (the sentence recording the debt lives at the end of
§6.1, but the witness is §5.2's), and **§6.1**'s `const`-vs-`data` length-guard asymmetry.

The probe was temporary. It has been stripped; `engine/effects/raster_dsl.emp` now holds its
module header plus one placeholder export for Task 6 to fill (deviation 2 below).
`games/sonic4/data/parallax/configs.emp` keeps `use engine.effects.raster_dsl.*` so the module
stays reachable.

Baseline and every green build: **`crc=fedcf197 len=696836`** — the probe emitted zero ROM bytes.
That is `s4.bin`, the **plain/release** shape. The debug shape was not built; nothing here is
shape-sensitive (no bytes were emitted), but no debug-shape coverage is claimed.

## Results

Rows are marked by how the build behaved, because "PASS" otherwise means two different things:
**green** = the build succeeded with the `ensure` holding; **fired** = the build FAILED exactly as
the probe designed it to, which is the pass condition for a negative control.

| # | Construct probed | Result |
|---|---|---|
| 1 | `comptime var` accumulation across a `for` + `++` inside a `comptime fn`, reaching the fn-level var | PASS (green) |
| 2 / 2b | Flattened value correct element-by-element (payload destructuring order preserved) | PASS (green) |
| 3 | An INDEPENDENT size path (`match` arms returning counts) agrees with the concatenation path | PASS (green) |
| 4 | A `Label` param defaulted to `0` compares EQUAL to `0` (the "unbound" half of the idiom) | PASS (green) |
| 5 | Negative half: a **bound** `Label` compares NOT-equal to `0` | PASS (**fired** — build failed as designed) |
| 6 | Declared array length on a `const` is **vacuous**; on a `pub data` it is **enforced** | PASS (green const half + **fired** data half) |

Payload-carrying `comptime enum` + `match` destructuring works, including the zero-payload arm
returning `[]` and one mixed case: `ProbeOp.B(3, [4, 5, 6])` bound an **array** to a payload slot
declared `int` and the `match` arm destructured it, with `ys.len == 3` — so that particular
declared payload type was not enforced. That is one observation, not a general survey of payload
type-checking.

**Measured vs read.** Every row above, and every message quoted below, came from an actual build
on the compiler named in the header. The mechanism explanations (`Type::Refined`, `values_equal`,
`check_arg_class`) are **source reads**, cited to `file:line` where they appear.

## Negative controls — exact message text

Every one of these was produced by an actually-failing build. An `ensure` that cannot fail is the
precise failure mode this task was written about, so each is quoted verbatim.

**Step 4** — PROBE 1 flipped to `PROBE_OUT.len == 8`:

```
  [Error] PROBE 1: expected 7 words, got 7 @ Span { source: SourceId(9), start: 1220, end: 1296 }
```

This also proves the module is genuinely **walked and evaluated**, and that `{...}` interpolation
in the message is live. The distinction matters and is worth stating precisely: an `ensure` in an
unimported pure-comptime module does not *pass* — it is **never evaluated at all**. There is no
diagnostic, no row, nothing; the build is simply green. See I4 under "Reachability" below.

**Step 5** — `probe_label_bound(sym: <a real bound label>)`:

```
  [Error] PROBE 5 NEGATIVE: a BOUND Label must NOT equal 0 @ Span { source: SourceId(9), start: 2489, end: 2597 }
```

So `Label != 0` really does discriminate bound from unbound; PROBE 4 is not a tautology. **The
witness §5.2 owed is paid.** Standing caveat unchanged, and this half is a *source read*, not a
measurement: it rests on `Value::Label` vs `Value::Int` falling into `values_equal`'s catch-all
`_ => a == b` arm (`sigil-frontend-emp/src/eval/expr.rs:1232-1239`) as a variant mismatch, not on
a designed predicate. If sigil ever diagnoses cross-class comparison, PROBE 4 inverts silently to
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

   **What a parameter annotation does and does not buy** (source read — do not generalize past
   this; an earlier draft of this note said "any name parses and means nothing", which is FALSE
   and would invite someone to strip a `Label` annotation as decorative, destroying the exact
   idiom probes 4 and 5 established):

   - **No bind-time range or length check** outside `where LO..HI`. Only `ast::Type::Refined`
     carries one, at `eval/call.rs:309-318`; a bare `int`/`u8`/`[T; N]`/`array` param binds
     whatever it is given. This is why `[int; 3]` accepted a 4-element list above.
   - **`Reg` and `Label` ARE class-checked**, by *exact spelling*: `check_arg_class`
     (`eval/call.rs:446-480`) rejects a register into a non-`Reg` param and a non-register into a
     `Reg` param, and symmetrically for labels. The predicates `param_type_is_reg`
     (`eval/call.rs:829`) and `param_type_is_label` (`eval/call.rs:838`) each match a
     single-segment `Named` path spelled exactly `Reg` / `Label` — no alias, no path prefix.
   - **The class check runs on explicitly supplied args only** (its two call sites are the
     positional and named arms of `bind_args`, `eval/call.rs:545` and `:563`). A parameter left to
     its **default** never reaches it. That asymmetry is not incidental — it is precisely why
     PROBE 4 works and why `probe_label_bound(sym: 0)` is instead a hard error
     (`expected a label (a Label argument), got int`).

   The probe used `xs: array` as the honest generic spelling for a list. **Task 6 should adopt one
   spelling as a convention** (`array` recommended) and must not mistake `[T; N]` on a parameter
   for a checked length — it is not one. Conversely, a `Label` annotation on a pointer-taking
   constructor param is load-bearing and must be kept.

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
   literal `0` for a `Label` param is a hard error; only the *default* path skips the class check
   (mechanism cited under deviation 1).

## Reachability — the one line that can silently switch every `ensure` off

`use engine.effects.raster_dsl.*` in `games/sonic4/data/parallax/configs.emp` is **load-bearing**.
`engine.effects.raster_dsl` is not in `COMPTIME_HELPERS` (`sigil-harness/src/native.rs:1733-1748`,
which is what auto-publicizes and auto-imports the twelve listed helper modules), and nothing else
in `configs.emp` names a `raster_dsl` symbol. That single glob is the only thing making the module
reachable. Prune it and every module-level `ensure` in `raster_dsl.emp` stops being evaluated:
**green build, zero diagnostics, no signal that the checks are gone** — the same hazard class
`configs.emp:28-33` already spends six lines guarding against for late-bound struct-literal
constants. The line therefore carries a WHY comment; it must keep one.

If Task 6 ever adds `engine.effects.raster_dsl` to `COMPTIME_HELPERS`, that glob's job changes
(the module becomes reachable and its items force-`pub` regardless) and the line should be
re-justified or removed deliberately, not left as cargo.
