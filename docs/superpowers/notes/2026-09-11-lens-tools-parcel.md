# 2026-09-11 lens tools parcel: V-5, C5-7, C2b-4 and two side findings

Branch `parcel/lens-tools-0911`, base `3492ce3a` (= origin/master at dispatch; contains
`3492ce3a` as required). Zero bytes: tools, fixtures, build.sh prose and docs only.
No emulator was used. No cargo was run. `docs/DEFERRED_WORK.md` and
`docs/lens-findings.jsonl` are untouched: the proposed lines are at the bottom.

## Base (before the first edit)

`./tools/landing_build.sh` at `3492ce3a`, detached, `finished=0`, `REAL_EXIT=0`.

| ROM | cksum | size | md5 |
|---|---|---|---|
| s4.bin | 3697579482 | 821103 | 5cbafe417ad3fd7e440562dd690c78b3 |
| s4.debug.bin | 394963879 | 847367 | 50981e597809db4730c5032403a813f8 |
| demo.bin | 755353563 | 97051 | 0540d930d18eb9f489cef7a057595b6e |
| demo.debug.bin | 4271321717 | 103335 | 908dc94ac6171a2dbafd3f008cdd24aa |

Assembler: `SIGIL_BUILD` = sigil `target/release/sigil` (mtime 2026-09-07 19:47).
Base pytest totals, all four shapes: pre-build `2428 passed, 2 skipped, 14 deselected, 5
warnings, 112 subtests passed`; post-sigil 5/6/1/1 passed with 9/8/13/13 deferred;
needs_build lane `14 passed` (its verdict line: all 14 marked tests ran and passed), `EXIT_needs_build=0`.

## Items

### 1. V-5: the pytest lane's extent (commit `61c88d76`)

- `build.sh` said "18 files, ~984 assertions, no pytest.ini, no conftest" (a 2026-08-16
  count; `tools/conftest.py` exists since LS-1) and printed `sweeping N test file(s)` from
  `find tools -maxdepth 1 -name 'test_*.py'`, beside prose claiming "the same rule pytest
  collects by".
- Now `tools/conftest.py` counts files from the items pytest actually collected
  (`pytest_report_collectionfinish`, plus `pytest_deselected` so a wholly deselected file
  still counts as swept), and pytest prints it in every lane over `tools/`. `build.sh`'s
  echo names the source and computes nothing. `build.sh` is line-neutral (8 out, 8 in).
- Before: `sweeping 109 test file(s) under tools` (base run, x4). pytest's own collection
  at base: 109 files, 2430 items, all 109 contributing. The numbers AGREED at base; the
  rules did not.
- After (with this parcel's two new test files): `pytest swept 111 test file(s) under tools
  by its own collection rule; 111 of them contribute the 2438 test(s) left after deselection`.
- The rules disagree on a real case: a probe `tools/test_zz_v5_probe_no_tests.py` defining
  no test gives find(1) 112 and pytest 111 (probe removed).
- A report line, not a gate: nothing asserts a count.

### 2. C5-7: the listing fixtures (commit `a4fec63b`)

- **Regenerated, not retired.** `tools/test_s4budget.py` asserts real behaviour of a tool
  `build.sh` runs strictly on every build: the parser's refusals (AS-era, truncated,
  contradictory, disagreeing listings), RAM sizing by successor gap, the object-bank cursor
  against the real `map.toml`, ROM-tail accounting, RAM-into-stack. The excerpt's
  addresses are only self-consistent inputs to those checks. Retiring the fixture would
  have removed the unit coverage of a build-fatal gate to fix a labelling problem.
- Cut with the tool's own documented command from the plain `s4.lst` / `demo.lst` of the
  base run. Drift of the old cut (a4ebf2d1, 2026-08-18) against this build:
  Game_RAM_End FFFFBC02 -> FFFFBF02; EndOfRom A11C0 -> BDDA0; DeformTable_Zero 11984 ->
  12B1A; Page_Table FFFF6842 -> FFFF699C; Cheat_Flags == Engine_RAM_End FFFFB836 -> FFFFBB8C.
  The demo cut had drifted the same way (it was not named by C5-7; re-cut for one provenance).
- The re-cut failed at least 11 tests before the literal update (e.g. `76570 != 72068`,
  the cursor; `12634 != 12288`, the Block_Stage_Buffers gap). Literals re-pointed by a patch
  that asserted each old spelling's count first and that no old literal survived; after,
  `52 passed`. Six CLI rows now size their ROM by `FIXTURE_ENDOFROM` instead of a seventh
  copy of EndOfRom.
- `make_listing_excerpt.py` and `test_s4budget.py` now say the cuts are FORMAT SAMPLES of a
  named build, never today's layout. The fixture will drift again with the next RAM move.
  That is by design; the prohibition is what stops it being read as the layout.
- Other consumers of the two excerpts: none (`grep` over tools/, docs/*.md, build.sh).

### 3. landing_build.sh `[logfile]` (commit `b7dc81fa`)

- With one argument the script re-runs itself with none and tees that whole output
  (stdout and stderr) to the file; `finished=<n>` is the last line of both; exit is the
  child's (`PIPESTATUS[0]`). A relative path is resolved against the caller's directory
  before the script `cd`s. An unwritable log, two arguments, or an option-looking argument
  is COULD NOT RUN (exit 2, `finished=2`) before anything builds. What it runs is unchanged.
- `tools/test_landing_build_logfile.py`: red first against the committed script, 6 failed /
  1 passed (the no-logfile control), 0.49 s; after the fix 7 passed, 0.10 s. It covers the
  green path (`finished=0`), a failed shape (`finished=1`), a lane that could not run
  (`finished=2`), both refusals, relative paths, the unwritable log, and the control.
- Exit codes on non-building paths, committed vs fixed (sandbox copies): unset SIGIL_BUILD
  1 / 1; FAST=1 2 / 2; NO_LINT=1 2 / 2. Unchanged.
- The final landing run below used the new argument, so it is also a live witness.

### 4. C2b-4: sigil's Z80 clobbers gate as a landing step (commit `bcc607af`)

- Found at sigil `crates/sigil-cli/tests/z80_clobbers_incomplete.rs` (5 `#[test]`, last
  touched `2188f19a`, 2026-09-02). Its header gives the strict command; `reference_tree`
  in `crates/sigil-harness/src/test_support.rs` skips green on a missing reference unless
  `SIGIL_STRICT_GATE` is set. Read with `git grep` / `git show` only.
- `docs/OVERSEER-REFERENCE.md`, landing lane: a conditional step (when one of the seven
  `sound_tree()` inputs moved), with the command, flag inside the span:
  `CARGO_TARGET_DIR=<suite>/.aeon-landing-sigil-target SIGIL_STRICT_GATE=1 AEON_DIR=<absolute path of the merged aeon tree> cargo test --release --locked -p sigil-cli --test z80_clobbers_incomplete -- --nocapture`
  plus derived pass criteria and the sequence line updated. The private `CARGO_TARGET_DIR`
  is required because `sigil-cli`'s `[[bin]]` is `sigil`: a `--release` run in sigil's own
  `target/` would re-link the `SIGIL_BUILD` binary. `Cargo.lock` is tracked, so `--locked`.
- Cost: test body 0.06 s and warm incremental release compile 9.12 s (sigil's nightly log,
  2026-09-11); a cold first run in a fresh private target is unmeasured. Not put in
  `landing_build.sh` (cargo in another repo's tree).
- **Correction to the finding:** the gate is not only reachable by hand. sigil's
  `scripts/nightly_source_gates.sh` runs it with `SIGIL_STRICT_GATE=1` against a detached aeon
  master every morning (2026-09-11 05:19: OK at aeon 8d99deeb, 5 passed). The gap was
  pre-merge only. It is still a remembered step; CTRL-1 is the enforced form and stays open.

### 5. ojz_entity_gen MAX_LIST_ENTRIES (commit `2637d402`)

- `tools/test_ojz_entity_list_cap.py` reads `pub const MAX_LIST_ENTRIES` off
  `engine/system/constants.emp` (never retyped), requires it to be the only declaration
  under engine/ and games/, imports the generator, and requires equality. Missing,
  duplicated or non-literal is UNMEASURABLE and FAILS, never skips. Runner: the pre-build
  pytest lane. The generator's self-test `* 129` is now `* (MAX_LIST_ENTRIES + 1)`.
- Red first, three mutations, each shown on disk before the run and restored from the
  committed file after the check was committed:
  - `constants.emp:1172 ... = 256` -> FAILED, "generator 128 ... declares 256" (1 failed, 0.04 s);
  - `ojz_entity_gen.py:55 MAX_LIST_ENTRIES = 64` (different length, so no stale .pyc) ->
    FAILED, "generator 64 ... declares 128";
  - `constants.emp:1172 ... = 64 * 2` -> FAILED, "UNMEASURABLE ... not an integer literal".
- The sibling copies in the same header block (SECTION_SIZE, MAX_TYPES_PER_SECTION,
  MAX_SUBTYPE, OEF_TYPE_SHIFT, OEF_* bits) agree with constants.emp today and remain
  unchecked; named in the test's WHAT THIS DOES NOT COVER.

## Incident during item 3 (recorded because it is a hazard class, not only a slip)

The first draft of `test_landing_build_logfile.py` ran the REAL script against the REAL
repo and relied on FAST=1 to refuse before any build. One row omitted FAST. On the unfixed
script that row went on to `./build.sh`; its pre-build pytest lane collected the new test,
which launched `landing_build.sh` again: a recursion, one generation per ~60 s (the
subprocess timeout killed only the bash parent, orphaning each build). Found from the red
run's 60 s wall time. Stopped by quarantining the test file out of `tools/` and killing by
PID, each PID confirmed by cwd = this worktree or by a command line naming it (two other
sessions' builds were running and were not touched). Verified afterwards: `git status`
clean, all four ROM CRCs equal to base, no stray files. The shipped test runs a COPY of
the script in a sandbox beside stub `build.sh` / `needs_build_lane.py`, in its own session,
killed as a group on timeout. **General hazard: any test in the `tools/` lane that invokes
`build.sh` or `landing_build.sh` against the real repo recurses through that lane.**

## What in the brief (or the sources) was wrong or weaker than stated

- C2b-4 "SKIPS green unless run with `SIGIL_STRICT_GATE=1 AEON_DIR=...`": true of a bare run,
  but sigil's nightly runs it strictly every morning. Not unrun, only post-merge.
- C5-7's "512 B" could not be re-derived: the old fixture had Game_RAM_End $FFFFBC02 and
  Player_Ring_Index $FFFFBC00, so a $FFFFBC00 model value is 2 B from one and equal to the
  other. The measured drift today is ROM-wide, not a RAM-only 512 B.
- V-5 "same rule pytest collects by": at base the counts agreed (109 = 109) by layout, not
  by rule. The sift's "108 test files" was 109 at base.
- `test_citation_form.py` checks `X.emp:N` citations only; build.sh line-neutrality was kept
  as a courtesy to the several `build.sh:N` citations in tools/ (most already stale).

## Found, not fixed (for the controller to book)

- `engine/objects/entity_window.emp`, the `COLLECTED_MASK_BYTES * 8 == MAX_LIST_ENTRIES`
  ensure message (line 101 at base), now says a false thing: "tools/ojz_entity_gen.py's own
  MAX_LIST_ENTRIES = 128, which no build step compares with this constant". Zero-byte string,
  but an engine file, which this parcel was told not to edit. Suggested respelling: "...its own
  MAX_LIST_ENTRIES copy, which tools/test_ojz_entity_list_cap.py compares with this constant in
  build.sh's pre-build pytest lane (not under FAST=1 or NO_LINT=1)".
- `tools/landing_build.sh` exits 1 with no `finished=` stamp when SIGIL_BUILD or SIGIL_EMIT is
  unset (bash `${VAR:?}`): a COULD NOT RUN reported as a failure, and the one path whose log
  has no stamp. Pre-existing; left alone because the brief fixed the exit codes.
- `tools/test_landing_lane_shapes.py:declared_artifacts` enumerates `test_*.py` with
  `os.listdir(TOOLS)`, the same maxdepth-1 rule V-5 replaced; harmless while tools/ has no
  test subdirectory.

## Proposed ledger lines (append at landing; `fixedAt` = the merge SHA)

```json
{"id": "V-5", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "V", "severity": "low", "title": "The build script's own description of its test lane is stale by several times, and its self-check does not measure what it claims", "state": "fixed", "fixedAt": "<merge>", "detail": "FIXED by parcel/lens-tools-0911 (branch commit 61c88d76), evidence docs/superpowers/notes/2026-09-11-lens-tools-parcel.md. build.sh's prose now dates the 18-file / ~984-assertion count to 2026-08-16 and drops 'no conftest'; the extent line is printed by pytest itself from the items it collected (tools/conftest.py pytest_report_collectionfinish + pytest_deselected), replacing find tools -maxdepth 1 -name 'test_*.py'. At base 3492ce3a the two counts agreed (109 = 109) by layout, not by rule; a probe test_*.py defining no test gives find 112 against pytest 111. build.sh line-neutral (8 out, 8 in). A report line, not a gate: nothing asserts a count."}
{"id": "C5-7", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C5", "severity": "low", "title": "A committed listing fixture disagrees with a real listing by five hundred and twelve bytes, and a model validated against it passed by luck", "state": "fixed", "fixedAt": "<merge>", "where": {"path": "tools/fixtures/s4_listing_excerpt.lst"}, "detail": "FIXED by parcel/lens-tools-0911 (branch commit a4fec63b). REGENERATED, not retired: tools/test_s4budget.py asserts the parser and the build-fatal budget gate, which is real behaviour; only the excerpt's addresses were stale. Both excerpts re-cut with make_listing_excerpt.py from the plain s4.lst / demo.lst of 3492ce3a (landing_build finished=0). Measured drift of the old cut: Game_RAM_End FFFFBC02 -> FFFFBF02, EndOfRom A11C0 -> BDDA0, DeformTable_Zero 11984 -> 12B1A, Page_Table FFFF6842 -> FFFF699C. The 512 B in this row's title was NOT re-derived (a $FFFFBC00 model value is 2 B from the old Game_RAM_End). Test literals re-pointed by an asserted patch, 52 passed. make_listing_excerpt.py and test_s4budget.py now say the cuts are format samples of one named build, never today's layout; the fixture will drift again by design, and the prohibition is what stops it being read as the layout.", "batch": "Tier 3"}
{"id": "C2b-4", "at": "<stamp at append>", "sweep": {"date": "2026-09-06", "packet": "docs/superpowers/notes/2026-09-06-aeon-lens-sweep.md", "sha": "9cfebb72", "pin": "61f22403"}, "seat": "C2b", "severity": "high", "title": "An edit to the sound driver's register contracts builds green here and is caught only in another repo, under an environment variable", "state": "fixed", "fixedAt": "<merge>", "detail": "FIXED as the row's own stated fix (name it as a landing step) by parcel/lens-tools-0911 (branch commit bcc607af). docs/OVERSEER-REFERENCE.md's landing lane names sigil's crates/sigil-cli/tests/z80_clobbers_incomplete.rs as a conditional step (when one of the seven files its sound_tree() reads moved), with SIGIL_STRICT_GATE=1 inside the command span, a private CARGO_TARGET_DIR (sigil-cli's [[bin]] is sigil, so a --release run in sigil's own target/ would re-link the SIGIL_BUILD binary), --locked, and pass criteria derived at the time. Correction to this row's framing: sigil's scripts/nightly_source_gates.sh already runs the gate with SIGIL_STRICT_GATE=1 against a detached aeon master every morning (2026-09-11 05:19: OK at aeon 8d99deeb, 5 passed in 0.06 s), so the gap was pre-merge only. Still a remembered step, not an enforced one: CTRL-1 (an aeon build-fatal Z80 under-declare census) is the enforced form and stays open. The command itself was not run by the parcel (no cargo); a cold first-run compile is unmeasured.", "batch": "LS-2"}
```

Proposed DEFERRED_WORK note for the two side findings: "Side findings (a) of the contracts
parcel (`92a17978`) and (b) of the lens-pins parcel (`f1b3fae6`) are FIXED by
parcel/lens-tools-0911: landing_build.sh tees to `$1` (`b7dc81fa`), and
tools/test_ojz_entity_list_cap.py pins ojz_entity_gen.py's MAX_LIST_ENTRIES to constants.emp
(`2637d402`). Evidence: docs/superpowers/notes/2026-09-11-lens-tools-parcel.md."

## Final landing run (tip)

PENDING: filled in by the commit after the run.
