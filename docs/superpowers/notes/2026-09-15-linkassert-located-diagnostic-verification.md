# Link-assert failure: located diagnostic, no panic — aeon-side verification

**Date:** 2026-09-15 · **Branch:** `throwaway/linkassert-fixture` (worktree
`/home/volence/sonic_hacks/.aeon-linkassert`, based on master `70c302ed`) · **Throwaway.**
Nothing here lands in the engine; this note is the durable record.

## What was asked

Sigil's commit `82838687` ("merge: link-assert failures render located, all of them,
through one renderer, never as a panic", 2026-09-07) claims a `.emp` `ensure` that can only
be decided at LINK time now fails as a located diagnostic and never panics. Aeon owed an
independent run against a real fixture in a real aeon tree.

**VERDICT: the claim holds on this binary. Located diagnostic, exit 1, no panic** — on both
the `--check` path and the full build path, with `RUST_BACKTRACE=1` set and no panic text of
any kind emitted. No partial ROM was written.

## Binary identity (a claim about assembler behaviour is meaningless without this)

```
path   /home/volence/sonic_hacks/sigil/target/release/sigil
md5    324d85d6ad5267a99bd57f118871ed1f
size   8764656
mtime  2026-09-15 19:51:04 -0400
self-reported:  sigil 0.1.0 (700177b1)
                revision 700177b1da3a1c4a46f39909fdec10c524ae0800
                committed 2026-09-13T21:20:48-04:00, tree clean at capture
```

`git merge-base --is-ancestor 82838687 700177b1` → rc 0, so **the binary under test does
contain the commit whose claim is being tested**. (Checked against the BINARY's own
self-reported revision, not against the sigil repo's working HEAD `2e4761c7` — the repo tree
has moved on six commits past the binary and an ancestry check against HEAD would have been
the wrong question.)

`SIGIL_EMIT` = `emit_sound_blob`, md5 `8c874ce1f50d57f4841c5324329c2216`.


## THE MULTI-FAILURE LEG — run 2026-09-16 at sigil's ask, and it was the leg that mattered

The scope caveat below ("one failing LinkAssert per run") drew a real hole and sigil named it
precisely: **their** harness proves the renderer emits every failing guard *when handed both*;
**this note's** first run proves the real build path delivers *one*. Neither proved the real build
path delivers **BOTH** — and that is exactly where the original defect lived. The old behaviour
printed `first Some(Diagnostic{..})`, so **short-circuit-after-the-first is this fix's specific
regression class**, and a single-failure run cannot see it: with one failure, a renderer that
prints ALL and one that prints THE FIRST produce byte-identical output.

Fixture: `games/sonic4/test/linkassert_probe/probe_multi.emp`, throwaway branch
`throwaway/linkassert-fixture` `fe38648d`. Three link-time guards, two drifting, **distinct symbol
pairs and distinct message tags** so two `[Error]` lines cannot be one line counted twice. Same
binary, md5 `324d85d6ad5267a99bd57f118871ed1f`.

| failing guards | `[Error]` lines | exit | header |
|---|---|---|---|
| 2 | **2** | 1 | `declared-chain drift guard FIRED: 2 error(s)` |
| 1 (guard B made true) | **1** | 1 | `… 1 error(s)` |
| 0 (both made true) | **0** | 0 | `checked: … 671 LinkAssert(s) decided at link` |

Both drifting guards render, each located at its own line, each interpolating its own resolved
number (5280 for the Object_RAM pair, 472 for the Palette_State pair). Zero `panicked at`. No ROM
written. **`--check` and the full `-o` build path produced identical diagnostics**, so this is the
real build path and not only the check path.

**THE CONTROL THAT CAME FREE — AND THE OVERCLAIM IT CARRIED, CORRECTED 2026-09-16 ON SIGIL'S
READING OF THEIR OWN SOURCE. Read the correction, not the struck sentence.** Guard C is a passing
link-time guard, and it never appears in the failing runs. On its own that is ambiguous between two
very different worlds: the renderer filters on FAILURE, or guard C was never evaluated at all.

~~The all-pass run settles it without a further experiment — its tally reads **671** LinkAsserts
against the **668** baseline, i.e. **+3**, so all three guards reached the link bucket, the passing
one included.~~ **THAT SENTENCE CLAIMS AN OBSERVATION THE TALLY IS NOT.** `GuardCensus::from_verdict`
(sigil `crates/sigil-harness/src/native.rs:3811`) computes `link_asserts_decided` as
`conditions - inapplicable.len()` over the COLLECTED IR list; `check_link_asserts` returns only a
`Vec<Diagnostic>`, so nothing reports which asserts actually folded. **The number is a subtraction,
not an observation.** What the +3 does prove: three more Condition-kind LinkAsserts were COLLECTED
and none landed in the inapplicable bucket. That they were DECIDED follows only through an
invariant sigil states at `native.rs:3809` — *"Every assert not inapplicable was decided"* — which
is well argued for the ordinary link path and is precisely what an `--extra-entry` module's
distinct load path would be testing. Booked by sigil as `GUARD-CENSUS-DERIVED-NOT-OBSERVED`; the
fix is to have the fold path report what it decided. **Until then this tally is not a liveness
proof, here or in sigil's `--extra-entry` row.**

**WHAT SURVIVES, AND IT IS THE POINT OF THE WHOLE EXCHANGE:** *absence-from-the-output and
never-having-run are the same artifact until something counts them* — and then the counter turned
out to be a subtraction, which is the same shape one level down. A single failing guard could not
distinguish print-all from print-first; a derived tally cannot distinguish decided from merely
collected. **Each instrument was blind in exactly the way the thing it was measuring was blind.**
Sigil's own `check_only_census.rs` cannot catch it either, because it asserts the derived number
against the same derivation — a check that computes its expectation the way the subject computes
it is not a check.

**A NARROWING THIS LANE OFFERS, AS REASONING AND NOT AS A MEASUREMENT.** The residual worry is that
`--extra-entry`'s load path might collect asserts without folding them. But guards A and B are in
that same module, loaded the same way, and were OBSERVED to fold — they rendered real resolved
numbers (5280, 472) that only `resolve_layout` can supply. So "this load path collects without
folding" is refuted for that path outright. What stays unobserved is narrower: whether folding is
per-assert complete WITHIN such a module, since a passing assert that silently failed to fold and
one that folded to true are the same artifact. Offered to sigil to judge against their source;
this lane has not measured it and does not claim it.

**Still not tested, and deliberately, at sigil's own direction:** DEBUG and demo shapes. Same
renderer, same code path, and the shape does not vary what a diagnostic looks like — sigil asked
for the run to be spent on the multi-failure case instead of a sweep. That is their call on their
own subject and it is recorded as theirs.

## RE-RUNNING THIS — added by the overseer at landing, because the note as written had no command in it

**The note originally recorded a verdict nobody could re-run.** That is the defect this lane has a
standing rule about: hand the receiver something they can EVALUATE, not something they must
BELIEVE. Two commands, and they answer different questions.

**1. The live standing check, which works on master forever and is what actually guards this:**

```sh
python3 tools/emp_expect_fail.py        # ~23 s, 20 real sigil builds
```

Its `poison_extern_span.emp` row is the same two-label-VMA road (`Parallax_State`), registered at
`tools/emp_expect_fail.py:693`. **This is the regression net. Nobody needs to rebuild one.**

**2. The independent fixture this verification actually used, which is NOT in the tree.** It was
deliberately independent of the registered row — testing the row that is already asserted green
tests the assertion, not the mechanism — and it is not landed because a fixture no runner executes
is a dormant scaffold. It lived at `throwaway/linkassert-fixture` `b2ea57b2`. To recreate it,
`games/sonic4/test/linkassert_probe/probe_linktime.emp` is the module named below, and:

```sh
export SIGIL_BUILD=/home/volence/sonic_hacks/sigil/target/release/sigil
export SIGIL_EMIT=/home/volence/sonic_hacks/sigil/target/release/emit_sound_blob
"$SIGIL_BUILD" build --aeon . --game sonic4 --check \
    --extra-entry games.sonic4.test.linkassert_probe.probe_linktime
```

**The flag spelling is `build --aeon <dir> --check`, not `check`** — `sigil check <map.toml>` is
not a command and exits 2 on the usage banner, which is easy to mistake for a result. The overseer
hit that twice before finding the form; it is written here so the next reader does not.

**INDEPENDENTLY REPRODUCED BY THE OVERSEER at landing**, in the agent's worktree, against the same
binary (md5 `324d85d6ad5267a99bd57f118871ed1f`, self-reporting `700177b1`, confirmed by
`git merge-base --is-ancestor 82838687 700177b1` rc 0): **exit 1**, zero `panicked at`, and

```
error: native check (sonic4 plain): declared-chain drift guard FIRED: 1 error(s):
  ./games/sonic4/test/linkassert_probe/probe_linktime.emp:24:1: [Error] LINKPROBE_LINKTIME: this probe claims the Object_RAM reservation spans 1 byte; the link says 5280
```

So the verdict below is not a single agent's run. The `:24` here against the note's `:23` for the
same check is the comment edit the note explains, and it is the evidence that the location is
computed rather than canned.

## The fixture

`games/sonic4/test/linkassert_probe/probe_linktime.emp` — zero bytes, ensures-only, reached
via `--extra-entry`. The two lines that make it link-time rather than comptime:

```
const LINKPROBE_IMPOSSIBLE_SPAN = 1

ensure(extern("Object_RAM_End") - extern("Object_RAM") == LINKPROBE_IMPOSSIBLE_SPAN, "...")
```

The condition is a **difference of two label VMAs**. `extern()` poisons comptime-ness
(`docs/EMP_PITFALLS.md` §5), so neither operand has a value until `resolve_layout` has placed
both symbols and the whole condition defers to the LinkAssert bucket. Shape copied from the
working model at `engine/debug/sound_debug.emp:98`
(`extern("Dynamic_Live") - extern("Sound_Dbg_Mirror")`) — **that model is as described; the
handoff's account of it was correct.** The symbol pair is deliberately NOT the one the
already-registered `games/sonic4/test/poison/poison_extern_span.emp` uses (`Parallax_State`),
so this run is independent of that row.

`Object_RAM`/`_End` bracket a `mark`ed region of whole `Sst`s (stride `$50` = 80,
`engine/ram.emp:870-876`), so a 1-byte span is structurally unreachable. Measured span this
tree: **5280 = 66 × 80**.

## Evidence the check actually reached the LINK-TIME path

`--check` prints its own bucket tally, which is the discriminator. Three runs, identical
except for the `--extra-entry` module, each probe written in a TRUE variant so the run goes
green and the counters print:

| run | comptime verdicts | LinkAsserts decided at link |
|---|---|---|
| baseline, no `--extra-entry` | 90199 | 668 |
| `probe_linktime_green` (subject, true) | 90199 — **unchanged** | **669 (+1)** |
| `probe_comptime_green` (control, true) | **90200 (+1)** | 668 — **unchanged** |

The subject's `ensure` moves the LinkAssert counter and leaves the comptime counter alone;
the control does the exact opposite. The control was established BEFORE the subject was
believed. Corroborating: the failing subject's message interpolates the real resolved span
**5280**, a number that can only come from resolved layout, and the two buckets even fail
through different phases (`build_program` for comptime vs `declared-chain drift guard FIRED`
for link).

## Verbatim output

**Subject, `--check`** (exit **1**):
```
check: sonic4 plain: deciding every ensure and LinkAssert against final post-relaxation placement, then stopping before the link: a green check proves nothing about region budget or overlap, image bounds, the checksum or the contract closure gate, and is not a statement that the game builds
check: sonic4 plain: emit_generated writes the sound artifacts into . (a precondition of the .emp build), the one write this run makes
error: native check (sonic4 plain): declared-chain drift guard FIRED: 1 error(s):
  ./games/sonic4/test/linkassert_probe/probe_linktime.emp:23:1: [Error] LINKPROBE_LINKTIME: this probe claims the Object_RAM reservation spans 1 byte; the link says 5280
```

**Subject, full build** `-o <scratch>.bin`, `RUST_BACKTRACE=1` (exit **1**):
```
warning: 14 warnings, module.path-mismatch 14; SIGIL_WARNINGS=full to list
error: native build (sonic4 plain): declared-chain drift guard FIRED: 1 error(s):
  ./games/sonic4/test/linkassert_probe/probe_linktime.emp:24:1: [Error] LINKPROBE_LINKTIME: this probe claims the Object_RAM reservation spans 1 byte; the link says 5280
```
No ROM file was created. `grep -c 'panicked at'` = **0** on every captured run.

(The `:23:` → `:24:` shift between the two is a comment edit made between the runs, not an
inconsistency — and it is incidental evidence that the location is genuinely computed from
the source position rather than canned.)

**Comptime control, `--check`** (exit **1**) — the bucket a naive false `ensure` lands in,
recorded so nobody mistakes it for the answer:
```
error: native check (sonic4 plain): build_program: 1 error(s);
  ./games/sonic4/test/linkassert_probe/probe_comptime.emp:14:1: [Error] LINKPROBE_COMPTIME: this control claims 1 == 2
```

## Adjacent probe, reported as adjacent — NOT part of the tested claim

`probe_undef.emp`: an `extern()` in a link-time `ensure` naming a symbol no module defines.
Also located, also no panic, exit **1**, and it carries a **column** as well as a line:
```
error: native check (sonic4 plain): extern() names a symbol no module in this link defines: 1 error(s):
  ./games/sonic4/test/linkassert_probe/probe_undef.emp:2:8: [Error] [extern.unknown] `extern("LinkProbe_No_Such_Symbol_XYZZY")` names a symbol not defined in this link: no label, equ or supplied stub is called `LinkProbe_No_Such_Symbol_XYZZY`
```

## Scope — what this run does NOT establish

Sonic 4 `plain` shape only, one `--extra-entry` module at a time, one failing LinkAssert per
run. It says nothing about DEBUG or demo shapes, about multiple simultaneous link-assert
failures, or about link-assert failures reached without `--extra-entry`. The
`82838687` claim is "all of them, through one renderer"; this run confirms the renderer is
located and panic-free for **three** expression shapes (label-VMA difference, comptime
literal comparison, undefined extern), not for the whole family.

## Corrections to the dispatch brief

None needed. `engine/debug/sound_debug.emp:98` is the model it was described as; `--check` is
the right flag and self-documents as "decides every ensure and LinkAssert against final
post-relaxation placement"; the comptime/link-time split works as described. The brief's
warning that a plain false `ensure` lands in the wrong bucket is **confirmed empirically** by
the control row above.

The one thing worth adding for a future session: the tree ALREADY carries a registered
link-assert poison family at `games/sonic4/test/poison/poison_extern_*.emp`, driven by
`tools/emp_expect_fail.py` via the same `--extra-entry` mechanism. An independent fixture was
still the right call here, but that family is the standing regression net.
