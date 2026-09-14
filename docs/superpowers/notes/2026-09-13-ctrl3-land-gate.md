# CTRL-3: the landing gate (record)

2026-09-13, branch `parcel/ctrl3-land-gate` from `6a6b0baa`. The owner chose `gate` at
2026-09-13T22:06:54Z: *"ctrl-3 do what's recommended as long as it doesn't hamper too much.
also I don't need all 4 versions, what are they again? let's get rid of some."* This file is
the first half. The second half (which builds to drop) is
`docs/superpowers/notes/2026-09-13-ctrl3-shapes-proposal.md`.

## What shipped

- `tools/landing_build.sh` calls `tools/land_gate.py begin` before its four builds and
  `finish` just above `finished=`. `finish` writes a **stamp** only for `finished=0` over a
  tree whose code paths were clean at the start and still are, with HEAD unmoved. A moved HEAD
  or code path makes the run `finished=2` (COULD NOT RUN). Every `EXIT_` line gained `secs=`.
- The stamp is keyed by **content**: sha256 over the `(mode, object, path)` of every code path
  in the commit's tree (`content_key`). It lives in
  `$(git rev-parse --git-common-dir)/aeon-land-gate/<key>.json`, shared by every worktree and
  by no commit.
- `tools/hooks/pre-push` (tracked, **not installed by this parcel**) passes every ref except
  `refs/heads/master` through untouched, and for master runs the pushing checkout's
  `tools/land_gate.py pre-push`, which refuses unless the pushed code has a stamp or is
  identical to the remote master's code, and runs the tests that read any changed docs file.
- `tools/land_gate_audit.py`, registered by `tools/conftest.py`, fails any pytest session in
  which a test opens a docs file the classifier does not declare that test as reading.
- Tests: `tools/test_land_gate.py` (19 rows, real `git push` into a scratch bare remote),
  `tools/test_landing_build_stamp.py` (7 rows, the real script beside stub builds),
  `tools/test_land_gate_classifier.py` (9 rows: plugin armed, verdicts, an end-to-end sandbox
  session, the static scan, constraint 2, rule shape). All in build.sh's pre-build lane.

## The form, and why

**Chosen: a pre-push hook that checks a stamp `landing_build.sh` writes** (the brief's option
(ii) with the stamp; no `tools/land.sh`). Against the alternatives:

- A `land.sh` that merges, builds and pushes (oracle's `tools/land.sh`, aurora's
  `scripts/land.mjs`, both read at their committed revisions) is the literal wording of the
  recommended option. It would not satisfy constraint 6: aeon's landing has hand-run steps
  between the build and the push (the effects gates, sigil's Z80 clobbers gate, per-parcel
  witnesses) and a ledger commit AFTER verification, so a script that merges and pushes would
  either absorb those steps or push before them. And a command is still skippable: a bare
  `git push origin HEAD:master` bypasses it by forgetting, which is the failure CTRL-3 exists
  for. Aurora's own header records that its lane-log commit lands after its suite "by
  construction", and it re-ordered its flow to fit its command.
- The hook sits at the one point every route to master crosses, and the stamp carries the
  recommended option's property ("refuses if any check failed or the code changed during the
  run") to that point. The merge, witnesses and ledger steps stay exactly where they are.
- Both (iii) would add a `land.sh` nobody needs once the push is gated; it can be added later
  as a convenience with no change to the gate.

## The six constraints

1. **A docs-only push does not pay the build.** It changes no code path, so it needs no stamp.
   But "docs-only" could not mean "skip" (next section): every docs file is read by a test, so
   the hook runs those tests, in a temporary checkout of the pushed commit. Measured about
   0.75 s (below). No build.
2. **The ledger commit after a verified merge needs no rebuild.** The key covers code paths
   only, so `docs/lens-findings.jsonl` and `docs/lane-log.jsonl` rows on top of the verified
   commit keep its key. Proven by `test_the_ledger_commit_after_a_verified_merge_needs_no_rebuild`
   and measured (case E below); held by `test_the_landing_ledger_files_never_need_a_rebuild`.
3. **Refusals.** No stamp for this content (keyed by content: a stamp for other content does
   not count); a stamp that is not a complete `finished: 0` record; a run under which HEAD or a
   code path moved (no stamp, and `finished=2`); code dirty at the start (no stamp); a killed
   run (no stamp: `finish` runs only after the builds and the lane). Red-first, below.
4. **Other refs untouched.** The hook's shell prefilter exits 0 without running Python when no
   line targets `refs/heads/master` (measured 1 ms), and the Python side filters again.
5. **A loud bypass.** `AEON_LAND_GATE=skip git push ...` prints a GATE SKIPPED ... UNVERIFIED
   banner. `git push --no-verify` also works and prints nothing, because a hook that does not
   run cannot print; the docs say so and prefer the variable.
6. **The flow is unchanged** apart from the gate at the push: merge, assert, `landing_build.sh`
   (which now also stamps), hand-run gates, ledger commit, push, fast-forward the owner's folder.

## Deriving which paths are code

**The brief's assumption was wrong, and so was mine.** It said at least
`tools/test_overseer_bound.py` reads `docs/OVERSEER.md` and wondered whether anything else did.
Measured three ways:

1. **An inotify trace** of this worktree's `docs/` tree across a full `landing_build.sh` run
   (every process: build.sh, sigil, the gates, both pytest lanes; ctypes inotify, 58 watches,
   no queue overflow). **830 of the 832 tracked docs files were opened, at least 4 times each**
   (once per build). The other two have a non-ASCII `§` in their names (booked in
   `docs/DEFERRED_WORK.md`: `test_citation_form` quotes and then fails to open them).
2. **Per-test attribution** with `tools/land_gate_audit.py`'s record mode over both lanes
   (with the assembler variables set; without them the provenance tests fail early and hide
   their reads, which the first record run did):
   - `test_citation_form`: opens every tracked docs file (its anchor row looks for a
     `CITATIONS-ANCHORED-AT` declaration in all of them; its live row opens the LIVE ones);
   - `test_decisions_ledger` (`docs/decisions.jsonl`), `test_lane_log_shape`
     (`docs/lane-log.jsonl`), `test_overseer_bound` (`docs/OVERSEER.md`),
     `test_object_mailbox_contract` (`docs/ENGINE_ARCHITECTURE.md`), `test_effects_gen`
     (`docs/EDITOR_RASTER_PRESETS.md`), `test_lab_index_lint` (`docs/EFFECTS_LAB.md`),
     `test_gen_vram_map` and `test_fg_working_set` (`docs/generated/vram-map-*.md`);
   - LISTINGS of every docs directory by `test_emp_helper_closure`, `test_artifact_provenance`,
     `test_bg_emit` and `tools/conftest.py`: each is a walk for `*.emp` modules only (read at
     source: `emp_helper_closure.py`'s `if not fn.endswith(".emp")`; `artifact_provenance.
     scan_members`, sigil's module walk reproduced);
   - the needs_build lane opens no docs file; nothing in the pre-build lane opened a docs
     file from a child process (every inotify open in a lane-only trace was attributed).
3. **The build reads no docs file.** The three listings' Source Digests (`DIGEST-` rows: every
   file the build read) name no `docs/` path, and there are 0 `*.emp` files under `docs/`.
   sigil's module walk would take one if it appeared, so `docs/**/*.emp` is code.

So: **every docs path is `checked`** (a push that changes it runs `test_citation_form` plus the
file's own readers), `docs/**/*.emp` is `code`, and nothing outside `docs/` is anything but
code. The table is `RULES` in `tools/land_gate.py`; the listers are `LISTERS`.

**Caveat on the first trace, re-established by the final run.** The first full-run trace was
contaminated: a research subagent of this session was grepping `docs/` in the same worktree
during it, which explains its residual opens (+17 on `DEFERRED_WORK.md`, +1 on every file under
`docs/superpowers/notes/` including PNGs, which no build stage would open). The verification run
at the end of this parcel repeats the trace with nothing else in the tree; see "Final
verification run".

**Validation runs in a sibling worktree, measured necessary.** In a fresh checkout under
`/tmp`, `test_emp_helper_closure` failed 4 rows: it finds the paired sigil checkout BESIDE the
aeon root. So the hook's temporary checkout is `<parent of the pushing checkout>/.aeon-land-
gate-<pid>-<time>`, removed in a `finally`. `git worktree add --detach` of this tree took 82 ms.

**How it stays true.** `land_gate_audit.py` watches every `open()`, `os.listdir()` and
`os.scandir()` the test process makes and fails the session on an undeclared docs read, with
the rule to add. What it cannot see (a child process, a relative `os.open()` whose base is a
directory fd) is covered by the static scan of docs paths named in tracked code
(`test_every_docs_path_named_in_code_is_covered`, 9 known references each with a verdict) and
booked as open. Two things this parcel got wrong on the way and fixed: stdlib `rmtree` opens
children by bare name relative to a directory fd, which the first version resolved against the
cwd and misattributed (19 false rows); and the static scan enumerates with `git ls-files`, so
the gate's own untracked files were invisible to it until committed, which the red-first
control run caught.

## Red-first proofs

`scratchpad/mutate.py` (not committed; its output is quoted here): each mutation is an exact,
unique string replacement on disk, the mutated line is read back from disk or its file named by
`git diff --stat`, the targeted rows run, and the file is restored with `git restore
--source=bdbb1542` (the committed baseline), after which the tree is checked clean. Control
first: **26 passed, rc=0** with no mutation.

| # | mutation (file) | red rows |
|---|---|---|
| M1 | a missing stamp passes (`land_gate.py`) | code push without a stamp; stamp for other content; docs path the build reads |
| M2 | a stamp need not record `finished: 0` | incomplete or non-green stamp |
| M3 | HEAD moving is ignored | finish after HEAD moved; landing run with a commit during it |
| M4 | a tree changing is ignored | finish after an edit; landing run with an edit during it |
| M5 | a dirty start is ignored | dirty code at start (both files) |
| M6 | any `finished` stamps | a run that was not green; a failed shape |
| M7 | non-master lines treated as master (hook + `land_gate.py`) | other refs untouched and silent |
| M8 | deleting master allowed | deleting master is refused |
| M9 | checked paths not validated | a ledger line that breaks its reader |
| M10 | validation run in the pushing tree | validated in the pushed commit, not the working tree |
| M11 | `docsx/` counted as docs | nothing outside docs is anything but code |
| M12 | an old checkout exits 0 (hook) | a checkout that predates the gate |
| M13 | bypass banner removed | the bypasses |
| M14 | audit never sets exit 1 (`land_gate_audit.py`) | end-to-end undeclared read fails a green session |
| M15 | conftest does not register the audit | the audit plugin is armed in this session |
| M16 | a KNOWN static reference unlisted | every docs path named in code is covered |
| M17 | the `*.emp` rule disabled | an emp file under docs is code; the verdicts |
| M18 | `docs/lane-log.jsonl` made CODE | the landing ledger files never need a rebuild |
| M19 | a moved tree is not `finished=2` (`landing_build.sh`) | landing run with a commit during it |
| M20 | the stamp written before the builds (`landing_build.sh`) | a killed run writes no stamp |

**20 of 20 went red on every targeted row**, each restored clean. Two rows that went red for a
wrong reason were caught before this table: the hermetic tests first redirected `HOME`, so the
hook's `python3 -m pytest` found no pytest and "refused" (a green for the wrong reason); the rows
now assert the reader's own `JSONDecodeError`.

## Measured cost of the hook

In a scratch `--shared` clone of this repository at the branch tip (real tree, real tests; the
shared repository was not touched). Each case three times; load average 4.9 to 5.1 throughout
(another agent was building).

| case | ms (3 runs) | what ran |
|---|---|---|
| A. a `parcel/*` push | 1, 1, 1 | the shell prefilter only |
| B. docs-only push, a note | 742, 753, 757 | `test_citation_form` in a temporary checkout: "3 passed" |
| C. a booking plus a lane-log row | 792, 783, 779 | plus `test_lane_log_shape`: "19 passed" |
| D. a code push with a stamp | 27, 27, 27 | key + stamp lookup |
| E. stamped code plus the ledger commit on top | 795, 811, 784 | D plus C's validation |
| F. a code push with no stamp | 27, 26, 25 | refused |

No validation worktree was left behind. The brief expected "well under a second" for a docs
push on the assumption that docs are unread; they are read, so a docs push costs the tests that
read it, about three quarters of a second.

## Install, uninstall, bypass

```sh
install -m 0755 tools/hooks/pre-push "$(git rev-parse --git-common-dir)/hooks/pre-push"   # once
rm "$(git rev-parse --git-common-dir)/hooks/pre-push"                                    # undo
AEON_LAND_GATE=skip git push origin HEAD:master     # deliberate, printed bypass
tools/land_gate.py stamps                           # what has been proven on this machine
```

A copy, not `core.hooksPath`: a relative hooksPath resolves in each worktree's own checkout and
git runs nothing where the file is missing, so an older worktree would push master ungated. The
copy always runs and dispatches to the pushing checkout's `tools/land_gate.py`; where that is
missing it refuses master and passes everything else. No git config was changed and no hook was
installed by this parcel.

## For the controller at landing

- Install the hook (above), then push the landing itself through it: the landing run's stamp
  covers this branch's code, so the push is the gate's first live test.
- Ledger rows to append (`docs/lens-findings.jsonl`), after the install:
  - `CTRL-3` -> fixed: "answered `gate` (owner 2026-09-13T22:06:54Z): a local pre-push gate on a
    content-keyed landing_build.sh stamp, no hosted CI; installed <date> by <install line>".
  - `V-8` -> fixed: "the four-shape rule is automatic: a master push without a green
    landing_build.sh stamp for its code is refused (tools/hooks/pre-push); the rule's other half,
    which shapes, is the CTRL-3 shapes proposal".
- `docs/DEFERRED_WORK.md` carries what stays open (the section at the top).
