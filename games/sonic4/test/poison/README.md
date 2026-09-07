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

## A poison whose guard contains `extern(` goes in `LINK_CASES`, not `CASES`

An `ensure` whose condition mentions `extern(...)` is **not a comptime guard**. sigil
lowers it to a `LinkAssert` and evaluates it after `resolve_layout`, in
`check_link_asserts` — a later phase with its own report format:

```
error: native build (sonic4 plain): declared-chain drift guard FIRED: N error(s); first Some(Diagnostic { .. })
```

There is **no `[Error]` token anywhere in it**. A row registered in `CASES` for such a
poison therefore fails on `got 0 [Error] diagnostic(s), expected 1` however correct the
guard is, which is why this directory held zero fixtures containing `extern(` until
2026-09-06 (LS-16). Those rows live in **`LINK_CASES`**, run by `run_one_link`, which
reads the phase's own `FIRED: N error(s)` count instead — and sets `NATIVE_DEBUG=1` so
sigil prints EVERY failing assert as a `REAL DRIFT: <message>` line rather than only the
first, without which a fragment match is luck whenever more than one fires.

`LINK_SENTINEL` (`poison_extern_equate.emp`) is that phase's case 0 and runs right after
this file's case 0, for the same reason: **case 0 says nothing about the link phase**, so
without it `check_link_asserts` could stop evaluating anything and all 135 of the tree's
`extern()`-bearing guards would go unenforced with every build still green.

Three modules, one per expression shape the family actually uses, because they are three
different roads through the resolver:

| module | shape | models |
|---|---|---|
| `poison_extern_equate.emp` | `extern("EQU") == n` | the ~120 cross-namespace constant mirrors (anims, `vdp.emp`, sound banks, `ram.emp`) |
| `poison_extern_span.emp` | `extern("X_End") - extern("X") == n` | the eleven RAM-reservation spans (`palette`, `raster`, `bg_anim`, `parallax`, `core`) |
| `poison_extern_addr.emp` | `(extern("Label") & m) == n` | the alignment/window guards (`epilogue`, `player_common`, `core`) |

**What these three do NOT prove**, said plainly because it is easy to misread as coverage:
they prove the *phase* is live, not that any individual engine guard is. A poison
contributes zero bytes by construction, so it cannot move a reservation or an equate —
there is no argument a poison can pass that makes `engine/level/parallax.emp:480` false.
Per-guard proof for all 135 is `tools/extern_guard_census.py`, which negates each guard's
own condition and reads the diagnostics back. That lane REWRITES engine sources, so it is
deliberately not in `build.sh`; run it by hand after touching the family.

## Why every scene poison globs

Every `poison_scene_*` module spells `use engine.level.scene_dsl.*` and
`use engine.level.parallax_dsl.*`, and that is the author's own spelling, not a shortcut.
`engine.level.scene_dsl` is NOT a member of sigil's COMPTIME_HELPERS set
(`crates/sigil-harness/src/native.rs`), so unlike `raster_dsl` nothing it defines is
glob-injected into a module by the build. Every scene author writes this exact pair of
globs (see `games/sonic4/data/effects/ojz_scenes.emp`), and a selective `use ...{layer}`
is silent on the constant axis (`docs/EMP_PITFALLS.md` §2) — so the glob is what makes a
poison model an author's module rather than a special case. (This paragraph lived in
`poison_scene_grid.emp`'s header until that poison was deleted with the per-line forcer
it targeted, 2026-08-26.)
