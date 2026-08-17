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

3. **Evaluated only by `emp_expect_fail.py`.** These modules are entry points for the
   negative-build lane exclusively — invoked directly (`sigil emp <path> --root
   <aeon-root>`) so their own top-level `ensure`s run regardless of reachability from
   any other entry. They are otherwise inert data as far as `sigil build` is
   concerned.

## The lane cannot run these yet — EFX-10

Property 3 above holds only for a **self-contained** poison, one whose `ensure` names
nothing outside itself. Every poison here reaches a guard in
`engine/effects/raster_dsl.emp`, and `sigil emp --root` cannot elaborate those: it skips
the `publicize_helper_comptime` / `normalize_helper_imports` rewrites that `sigil build`
applies, so the helper vocabulary is not in scope and raster_dsl's private helpers are
not importable at any spelling. Full derivation in `docs/BUGS.md` (EFX-10) and in
`tools/emp_expect_fail.py`'s docstring.

Consequences for anyone writing a module here:

- **Write it in the ambient spelling**, with no `use` lines, exactly as an author's
  module is written. That is the shape the lane will need once EFX-10 closes, and
  adding imports to chase the current invocation makes the poison resolve names
  differently from the build it is supposed to be modelling.
- **Verify it by splicing**, until the lane runs. Append the poison's body (everything
  after its `module` line) to a module that IS in the real build's `use` closure —
  `games/sonic4/data/effects/ojz_effects.emp` is the natural victim for effects work —
  run `sigil build --aeon . --native` (sub-second), read the diagnostic, restore the
  file. Red-first still means red-first: confirm the splice builds CLEAN *before* the
  guard exists.
- **Register the row in `BLOCKED_CASES`**, not `CASES`, and give the module the exact
  `EXPECTED FRAGMENT` header comment the row quotes.
