# Effects Phase 3, Parcel A — gate evidence

**Date:** 2026-08-13
**Branch:** `feat/effects-p3-parcel-a` (aeon, 27 commits) + `feat/effects-p3-parcel-a` (sigil, 1 commit)
**Plan:** `docs/superpowers/plans/2026-08-13-effects-p3-parcel-a.md`
**Spec:** `docs/superpowers/specs/2026-08-13-effects-p3-design.md`

Parcel A delivers `engine/effects/raster_dsl.emp`, `engine/effects/palette_dsl.emp` and a budget-model
checker, and re-expresses the two shipped sparse raster fixtures through the DSL **in place**. It is
comptime-only: **zero ROM bytes moved.**

---

## 1. The gate: seven golden ROMs, no rebaseline

Captured before any work (Task 0) and again after the last commit (Task 11), both by fresh full
rebuild through `crates/sigil-harness/golden/capture_goldens.sh` with no `--write`.

| target | before (`ffe05158`) | after (`c1f36d28`) |
|---|---|---|
| `s4` | `fedcf197 / 696836`, anchor `202f705f / 659952` | **identical** |
| `s4_debug` | `3dc20e2c / 711298`, anchor `b748bed7 / 667824` | **identical** |
| `demo` | `d5ea5776 / 95615`, anchor `7cd0cdfb / 70180` | **identical** |
| `demo_debug` | `321ad9c6 / 99783`, anchor `fc49dec9 / 70180` | **identical** |
| `config_a` | `8cb75de6 / 711666`, anchor `68a44fb7 / 667824` | **identical** |
| `config_b` | `b860aab0 / 598846`, anchor `9f7b223d / 562640` | **identical** |
| `lean` | `1602cde3 / 655726`, anchor `2737f366 / 655726` | **identical** |

**No `refreeze --freeze` was run.** `refreeze --check` reports
`OK (tip \`character-lens-sweep-postmerge\`, chain len 111)` — the same tip and the same chain length
as before the parcel. Nothing was frozen; the goldens were never the moving part.

The in-suite byte gates (`native_full_rom`, `native_offcanonical_full`, `native_offcanonical_rom`,
`native_rom`, run with `SIGIL_STRICT_GATE=1` so a missing aeon tree cannot make them skip green)
returned 3 + 9 + 5 + 2 tests, **0 failed**.

---

## 2. The two toolchain witnesses the spec left owed

Both paid in Task 1, recorded in full at
`docs/superpowers/notes/2026-08-13-parcel-a-capability-probe.md`, each with a negative control.

- **`Label != 0` (spec §5.2).** An unbound `sym: Label = 0` default compares EQUAL to 0; a *bound*
  label does not. The negative half fired: `PROBE 5 NEGATIVE: a BOUND Label must NOT equal 0`. The
  mechanism is a variant mismatch in `values_equal`'s `_ => a == b` arm
  (`sigil-frontend-emp/src/eval/expr.rs:1232-1239`), **not a designed predicate** — recorded as a
  standing caveat, because if sigil ever diagnoses cross-class comparison the idiom inverts silently.
- **`const` vs `data` length guards (spec §6.1).** Confirmed on this tree: the identical annotation on
  a `const` compiles a wrong-length value green, while on a `data` it fails with
  `array length mismatch: expected 2 element(s), got 3`. **Every length guard in this parcel therefore
  sits on a `data` declaration or on an explicit `.len` `ensure`.**

Compiler under test: sigil `476a5bd9` + this parcel's `36093f0d`; aeon base `ffe05158`.

---

## 3. Negative controls on every shipped guard

A guard nobody has watched fail is a guard on trust. Each of these was deliberately broken, the
message captured verbatim, and the change reverted (via scratchpad copies — `git checkout --` reverts
to last-*committed* state and tripped one task early on).

| guard | control | message |
|---|---|---|
| word-value pin, `OJZ_TestRaster` | colour `$000E`→`$000C` | `OJZ_TestRaster: DSL output diverges from the hand-authored words at index 15` |
| length annotation | second colour added | `OJZ_TestRaster: DSL counts 19 words, the hand program is 18` |
| word-value pin (reviewer's own, different) | `fire(120)`→`fire(121)` | `... diverges ... at index 3` (the arm word) — predicted from `arm_at` before running |
| word-value pin (reviewer's own, different) | `count: 3`→`count: 2` | `... diverges ... at index 14` (the `count-1` word) — predicted before running |
| **patch-offset invariant** (new) | second distinct init word | `OJZ_WaterRaster: word 3 is not the priming arm word — Raster_PatchWaterLine patches byte offset 6 (WATER_TEMPLATE_ARM0_OFF) unconditionally, which is word 3 only when init_count == 1` |
| mixed-fire ordering (ruling 14) | ops reversed | `raster fire at screen line 120: OP_SET_REG must be the FIRST op in a mixed fire (it is at index 1). A mixed fire already switches its mode register ~45% across the line ...` |
| region address/source cross-check (new) | `entry: 4`→`entry: 5` | `pal_region: destination CRAM address 72 is entry 4 but the staging source is entry 5` |
| `raster_dsl` literal pins (4 of 7 broken) | e.g. `OP_CRAM == 3` | `raster_dsl's inlined opcodes drifted from engine.effects.raster` |
| `cycle_script1` | two channels | `cycle_script1: 2 channels — cycle_script1 takes exactly 1. ...` |
| `PAL_MAX_VARIANTS` pin | `== 99` | `PAL_MAX_VARIANTS is 2 — the power-of-two mask in Palette_SetVariant must be fixed first` |

The `index 15` result is corroborated **three independent ways**: derived on paper in Task 6, obtained
by a reviewer who built a throwaway harness and executed the constructors, and observed for real in
Task 7.

**One pin was found broken by its own control.** `"drifted from RASTER_{MIN,MAX}_FIRE_LINE"` had its
braces parsed as an *interpolation*, so breaking that pin produced `unknown name MIN` instead of the
diagnostic — latent while the pin passed, broken exactly when needed. Repaired and re-broken to
confirm: `raster_dsl's inlined screen-line bounds drifted from RASTER_MIN_FIRE_LINE / RASTER_MAX_FIRE_LINE`,
one error, both names intact. The module was then swept for the same latent class; no other instance.

---

## 4. The two new checkers

**`tools/emp_helper_closure.py`** — gates `COMPTIME_HELPERS` for pairwise name disjointness, reading
the helper list out of sigil's `native.rs` rather than duplicating it. Readings across the parcel:

| point | reading |
|---|---|
| before (12 helpers) | `OK — 394 names, no collisions` |
| after `palette_dsl` + `raster_dsl` joined (14) | `OK — 402 names` |
| after the raster vocabulary landed | `OK — 424 names` |
| final | `OK — 425 names across 14 helpers, no collisions` |

`clamp07` was the flagged rename risk — a generic private name that force-publicization made globally
injected. It does not collide, so no rename was needed. Two defects in the drafted tool were caught
during construction: a module-id→path mapping that failed for 2 of 12 helpers (returning rc=2 without
checking anything), and a missing `pub context` item kind that made `engine/irq.emp` and
`engine/z80_bus.emp` report the **empty set**. Mutation-tested; the item-position gate initially had
no failing test and now does.

**`tools/effects_budget_check.py`** — resolves each `[symbols]`-declared `.emp` constant and fails on
disagreement. It earned its keep on its first run:

```
1 budget row(s) disagree with the shipped code:
  ram.raster_state_bytes: model says 286, engine/effects/raster.emp:RASTER_STATE_SIZE is 288
```

Post-fix: `effects_budget_check: OK — 8 code-derived rows agree`.

---

## 5. Suite totals

| suite | before | after |
|---|---|---|
| sigil workspace (`--no-fail-fast`, `SIGIL_STRICT_GATE=1`) | 3672 passed / 0 failed / 4 ignored | **identical** |
| aeon `python3 -m pytest -q` | 944 passed, 2 skipped | **983 passed, 2 skipped** (+22 closure, +17 budget) |

The 4 ignored are the standing set. Totals were read from aggregated `test result:` lines, never from
a tail — a tail once hid 16 failures in this tree.

---

## 6. What this parcel did NOT prove

Stated plainly, because the temptation is to read a green gate as broader than it is.

- **The length annotation does not catch a wrong word value.** `raster_program`'s own internal
  `ensure(out.len == raster_words(fires))` is what catches framing drift, and it runs on every call.
  The `data` annotation adds one narrower thing: it catches `[u16; raster_words(A)] = raster_program(B)`
  — an annotation naming a *different* program, a realistic copy-paste between two adjacent fixtures —
  and pins the declared ROM footprint at the linker seam. Word-value drift is the hand-word twins'
  job, with the goldens behind them.
- **The DSL has produced exactly two programs**, both of which already existed and both of which it
  was built to reproduce. Its generality is unproven until Parcel D authors new content. Reproducing
  a known answer is a much weaker claim than producing a new one.
- **The patch-offset invariant is redundant today.** Word index 1 *is* `init_count`, so any program
  with `init_count != 1` diverges from the hand twin at index ≤ 1 unconditionally — a reviewer
  constructed the specific case that was claimed to evade the twin and got two errors, not one. The
  ensure is retained because `OJZ_WATER_HAND` retires in Parcel D, at which point it becomes the only
  build-time guard on `init_count == 1`, and because it is the co-located half of `region_boundary`'s
  required `sh`. **A Parcel D reader must not delete it as dead weight during exactly the change that
  makes it load-bearing.**
- **Nothing runs the two new python checkers automatically.** No CI, no hook, not `test.sh`. They gate
  only when someone runs `pytest`. Pre-existing gap, already booked in `docs/DEFERRED_WORK.md` §5;
  this parcel adds to the pile rather than fixing it.
- **No runtime or emulator verification was performed, and none was warranted** — the parcel moves
  zero bytes, so the shipped program is bit-for-bit the one P1 and P2 validated on hardware.
- **The replay net was not exercised.** Its state is pre-existing debt owed by the character lens-sweep
  merge (`dbbb6afc`), and it is Parcel C's gate, not A's.

---

## 7. Defects found and fixed *in the plan* during execution

Recorded because the rate is the interesting datum: every task found something.

| task | defect in the plan |
|---|---|
| 1 | seven `comptime fn` params written untyped — a parse error; and annotations are mandatory but mostly unenforced, so `[T; N]` on a param is not a length check |
| 2 | `module_path()` mapped module ids to paths by string substitution (wrong for 2 of 12); `pub context` missing from the item set |
| 3 | five wrong citations, one inside the Task 6 code block where it would have shipped into source |
| 3 (review) | `RASTER_CRAM_MAX` checked per-op though it is a per-**fire** cycle budget; `region_boundary`'s `sh: int = 0` made the *corrupt* case the default |
| 4 | a comment claiming an import was "redundant" when it was load-bearing; a guard message naming a function that does not exist |
| 6 (review) | a pin whose failure message was itself broken; `fire_line_of` returning a screen line; a guard claim crediting the wrong `ensure` |
| 9 (review) | **the controller's own error** — an unverified claim that a pointer-field name degradation is caught only by the goldens. It is caught by the linker (`unresolved symbol … for fixup`); silent-green requires a collision with a defined symbol. Propagated into three files before being corrected |
| 10 | a const regex that would silently skip `pub const NAME : Type = value`, a form the tree uses |

Two spec claims also failed verification against the code: `Palette_DoFade` **is** called (it is
unreachable, a different mechanism), and `act_sec_field_equs()` is not a hypothetical rename risk — it
is **already** two fields and 6 bytes stale, and nothing fails. That matters for Parcel C, which
renames a field in that same blob.

---

## 8. Verified pair

| repo | branch head |
|---|---|
| aeon | `c1f36d28` |
| sigil | `36093f0d` |

Merge SHAs appended below after the merge.
