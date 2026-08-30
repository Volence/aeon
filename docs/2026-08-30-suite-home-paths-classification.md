# SUITE-HOME-PATHS — the suite half, classified (2026-08-30)

**Scope: the CLASSIFICATION only. Nothing was swept, converted or fixed.** The question is
which baked-absolute-path tests would *pass having checked nothing*, because a gate that
lies corrupts the evidence for every other item on both tiers.

## Population, docs excluded by construction

`git grep -l '/home/volence'` restricted to `tools/ engine/ games/ build.sh` — a path
filter, not a post-hoc exclusion — gives **52 files**. Split by whether pytest collects
them (`def test_`): **6 suite files, 46 harness/probe/generator files.** Only the suite half
runs build-fatally under `build.sh`, so only it can lie to a landing. **The 46 are a separate
population and are NOT classified here.**

## Result: 188 rows gated, 5 of 6 files fail loudly, ONE ROW SKIPS SILENTLY

Baseline collection over the six is **188 rows** — and the per-file gated counts below sum to
exactly 188, so **every pytest row in these files is gated by a baked path.**

| file | rows | absent | present-but-empty | verdict |
|---|---|---|---|---|
| `test_smps_import.py` | 106 | error | error | LOUD |
| `test_zyrinx_port.py` | 40 | collection error | collection error | LOUD |
| `test_effects_gates_segments.py` | 30 | error | error | LOUD |
| `test_aether_instance.py` | 8 | collection error | collection error | LOUD |
| `test_wait_for_break_spelling.py` | 3 | 1 fail · 1 pass · **1 skip** | same | **GUARDED, one silent row** |
| `tools/palette_variant_gate.py` | 1 | collection error | collection error | LOUD |

**Sized by rows gated, not literals, and the difference is the point:** `test_zyrinx_port.py`
carries **2** path literals and gates **40** rows; `test_smps_import.py` carries 8 and gates 106.
A count of occurrences would have ranked this work backwards.

## The one row that is not loud, and why the file is still the best of the six

`test_wait_for_break_spelling.py` survives collection and then, poisoned, reports **1 failed,
1 passed, 1 skipped** against a clean **3 passed**. The failure is
`test_send_sites_are_found_at_all` — **a completeness guard whose subject IS the tree being
present**, exactly the class that is *supposed* to fail under this poison and must not be
"fixed". It is why this file is not a silent-pass.

**But one row leaves the totals as a SKIP.** That is aurora's collection-death class arriving
one level down: not a file vanishing from the run, a *row* vanishing from it, and a skip reads
as deliberate. **A reader seeing `1 failed, 1 passed, 1 skipped` learns nothing about whether
the skip was chosen or caused.** That is the finding, and it is small and real.

## A negative result worth recording: the two scenarios did NOT differ here

Aurora measured **0** misdirected with the tree absent and **43** with it present-but-empty,
and warned that deleting the input finds the least. **In aeon the two scenarios produced
identical verdicts on all six files.** That does not refute their advice — running both cost
one extra command and I would not have known otherwise — but the asymmetry is a property of
their tree, not a law. **Report per scenario; do not assume another lane's ratio transfers.**

## What was NOT measured

The **46 harness files**, which are not pytest-collected and so cannot silently shrink a
build-fatal total — a different risk (a probe that misleads a human) needing a different assay.
And walk-up path finders: none of the six uses one, so that class had no subject here and
remains untested rather than absent.

## Method note against myself

While running this I read a real `exit 1` as `REAL_EXIT=0` — again — because `$?` after a pipe
is the *last stage's* status. I had banked that trap two hours earlier and repeated it inside
the audit written to catch instruments that lie. The pytest summary lines are what the verdicts
above rest on, not those exit codes.
