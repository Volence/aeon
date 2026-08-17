# games/sonic4/test/poison

Poison `.emp` modules for `tools/emp_expect_fail.py`, the tree's negative-build lane
(Parcel R1 §10.4). Each module here is deliberately broken — it exists to trip one
specific guard (an `ensure`, a lowering error, a contract check) and prove the guard
still fires.

Three properties every module in this directory must hold:

1. **Parsed by every build's manifest scan.** `sigil build` scans the WHOLE `--aeon` tree
   to build the module manifest, so every file under here is parsed on every ordinary
   build and every `emp_expect_fail` run. That means each poison module must stay
   **syntactically valid** `.emp` — a parse error here is indistinguishable from every
   other module's parse error and would make the `module.unreachable` scan noisy for
   everyone, not just this lane. The module fails on its *content* (a false `ensure`, a
   bad lowering), never on syntax.

2. **Never imported by any real entry.** Nothing under `games/sonic4/` or `engine/`
   may `use` a module from this directory. A poison module that ends up in a real
   build's `use` closure would fail THAT build, not just this lane. Unreachability is
   also what keeps these guards quiet: a module the real build's synthetic entry cannot
   reach is skipped, so its module-level `ensure`s are never evaluated.

3. **Evaluated only by the lane, as a named extra entry.** `sigil` never runs these as
   an ordinary entry — `emp_expect_fail.py` names each one on a real build invocation and
   reads the diagnostic.

## How the lane runs these — `sigil build --extra-entry`

One real build per case, with the poison named as an extra entry:

```
sigil build --aeon . --native --game sonic4 -o <scratch>.bin --extra-entry <poison>
```

`--extra-entry` evaluates the named module inside the **real build profile** — the same
manifest rewrites (`publicize_helper_comptime`, `normalize_helper_imports`) and the same
`-D` interface values the ordinary build uses — so a poison whose guard lives in
`engine/effects/raster_dsl.emp` resolves that helper vocabulary exactly as an author's
module does. The poison's module-level `ensure`s run because the flag names the module,
not because anything imports it: no file's body is rewritten, and no state has to be
restored after a case. A missing or unresolvable module, or one that would contribute
bytes, is a loud nonzero error rather than a silent skip.

**The sentinel (case 0, permanent, first).** `poison_sentinel.emp` in this directory holds
a single self-contained `ensure(false, "EMP_EXPECT_FAIL_SENTINEL — ...")`. The lane runs it
before any real poison and requires it to fail with that message. If it builds clean,
`--extra-entry` is not evaluating the module it names and every case after it would pass
for the wrong reason — the lane fails loudly right there instead of reporting false greens.

Consequences for anyone writing a module here:

- **Write it in the ambient spelling**, with no `use` lines, exactly as an author's
  module is written. That is the shape `--extra-entry` reproduces, and adding imports to
  chase a different invocation makes the poison resolve names differently from the build
  it is supposed to be modelling.
- **Verify a new poison directly**: `sigil build --aeon . --native --game sonic4
  -o <scratch>.bin --extra-entry games/sonic4/test/poison/<new>.emp` (a few seconds), read
  the diagnostic. Red-first still means red-first: confirm the module builds CLEAN
  *before* the guard exists.
- **Register the row in `CASES`** in `tools/emp_expect_fail.py` — path, entry id, expected
  message fragment, expected `[Error]` count — and give the module the exact
  `EXPECTED FRAGMENT` header comment the row quotes.
