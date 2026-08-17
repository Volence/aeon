# games/sonic4/test/poison

Poison `.emp` modules for `tools/emp_expect_fail.py`, the tree's negative-build lane
(Parcel R1 §10.4). Each module here is deliberately broken — it exists to trip one
specific guard (an `ensure`, a lowering error, a contract check) and prove the guard
still fires.

Three properties every module in this directory must hold:

1. **Parsed by every build's manifest scan.** `sigil emp <entry> --root .` (and
   `sigil build`) scan the WHOLE `--root` tree to build the module manifest, so every
   file under here is parsed on every ordinary build and every `emp_expect_fail` run.
   That means each poison module must stay **syntactically valid** `.emp` — a parse
   error here is indistinguishable from every other module's parse error and would
   make the `module.unreachable` scan noisy for everyone, not just this lane. The
   module fails on its *content* (a false `ensure`, a bad lowering), never on syntax.

2. **Never imported by any real entry.** Nothing under `games/sonic4/` or `engine/`
   may `use` a module from this directory. A poison module that ends up in a real
   build's `use` closure would fail THAT build, not just this lane.

3. **Evaluated only through the carrier.** These modules are never run directly by
   `sigil` — `emp_expect_fail.py` reads each one and copies its body (everything after
   its own `module` line) into `games/sonic4/test/poison_carrier.emp`, a real module
   that IS in the build's `use` closure, then runs the real `sigil build --native`
   invocation. The poison's `ensure`s run because the carrier's module identity is
   reachable, not because the poison file itself was ever an entry.

## How the lane runs these — the carrier backend (EFX-10 interim)

A **self-contained** poison, one whose `ensure` names nothing outside itself, could in
principle run directly via `sigil emp <path> --root <aeon-root>` (its own top-level
`ensure`s fire regardless of reachability, since an entry module is exempt from the
`module.unreachable` skip). Every poison here reaches a guard in
`engine/effects/raster_dsl.emp` instead, and `sigil emp --root` cannot elaborate that:
it skips the `publicize_helper_comptime` / `normalize_helper_imports` rewrites that
`sigil build` applies, so raster_dsl's helper vocabulary is not in scope at that
invocation. Full derivation in `docs/BUGS.md` (EFX-10) and in
`tools/emp_expect_fail.py`'s docstring.

**The carrier backend** (Fable-ruled 2026-08-17, temporary, aeon-side) works around
this without touching sigil: `games/sonic4/test/poison_carrier.emp` lives OUTSIDE this
directory, specifically so it can be the thing property 2 forbids a poison module from
being — a module a real entry (`games/sonic4/data/effects/ojz_effects.emp`) legally
`use`s. Its canonical resting state is a bare module line plus a header comment: zero
bytes, ensures-only, inert to every ordinary build. `emp_expect_fail.py` rewrites its
body to a poison's body, runs the real `sigil build --native` invocation against the
whole tree, reads the diagnostic, and restores the canonical body before moving to the
next case. Two safeguards ride along:

- **The sentinel (case 0, permanent, first).** A self-contained
  `ensure(false, "POISON_CARRIER_SENTINEL — ...")` body run before any real poison. If
  it builds clean, the carrier has fallen out of the build's `use` closure and every
  case after it would be vacuous — the lane fails loudly right there instead of
  reporting false greens.
- **Self-heal against crash residue.** If a previous run died mid-case (Ctrl-C, a
  sigil crash) the carrier can be left on disk holding a poison's body instead of its
  canonical one. Every run checks the on-disk carrier against the embedded canonical
  string first and, if it differs, restores it and prints a loud
  `CRASH RESIDUE — carrier was left poisoned by a previous run; self-healed` warning
  before doing anything else.

Consequences for anyone writing a module here:

- **Write it in the ambient spelling**, with no `use` lines, exactly as an author's
  module is written. That is the shape the carrier needs, and adding imports to chase
  a particular invocation makes the poison resolve names differently from the build it
  is supposed to be modelling.
- **Verify a new poison by splicing** before wiring it into `CASES`: append its body
  (everything after its `module` line) to `games/sonic4/data/effects/ojz_effects.emp`
  (or run it straight through the carrier the way `emp_expect_fail.py` does), run
  `sigil build --aeon . --native --game sonic4 -o <scratch>.bin` (sub-second), read the
  diagnostic, restore the file. Red-first still means red-first: confirm the splice
  builds CLEAN *before* the guard exists.
- **Register the row in `CASES`** in `tools/emp_expect_fail.py`, and give the module
  the exact `EXPECTED FRAGMENT` header comment the row quotes.

**Removal condition.** The carrier, the `use` edge in `ojz_effects.emp`, and this
section all retire together the day `--extra-entry <module>` lands on `sigil build`
(docs/BUGS.md EFX-10) — the properly-scoped fix, which elaborates a poison inside the
real profile without any file's body being rewritten out from under it.
