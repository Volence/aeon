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
