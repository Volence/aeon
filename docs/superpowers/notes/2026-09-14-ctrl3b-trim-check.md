# CTRL-3b: the pre-merge check, trimmed (A plus D)

2026-09-14, `parcel/ctrl3b-trim-check`, base `d4d7977d`. The record of what was built,
why each design call was made, and the evidence. `.runlogs/` is gitignored, so the
load-bearing output is quoted here.

## The ruling

empyrean `cf430f7` docs/OVERSEER.md:215, "HUB PICK on aeon CTRL-3's build-shapes proposal":
**A plus D** of `docs/superpowers/notes/2026-09-13-ctrl3-shapes-proposal.md`. A: the
pre-merge check stops building demo normal. D: the shape-independent lanes run once per
check, not once per shape. **B (drop both demos) stays the owner's**, one word away.
It is the pre-merge check only: `./build.sh` in every shape, the nightly and sigil's
goldens are unchanged.

## A: what changed

`tools/landing_build.sh` builds one declared list:

```sh
# >>> LANDING_SHAPES
LANDING_SHAPES="s4 s4.debug demo.debug"
# <<< LANDING_SHAPES
```

Everything else derives from it: the build loop (game and DEBUG are read back out of each
ROM name by build.sh's rule, and each name must round-trip before anything is built), the
md5 line, the list handed to the needs_build lane (`--shapes-built`), and which shape
carries the shared lanes.

**Demo normal is still assembled before every merge**, verified on the base, `build.sh`
lines 1101-1112 at `d4d7977d`:

```sh
if [[ "${GAME}" == "sonic4" && "${FAST:-0}" != "1" ]]; then
    _xg_out="$(mktemp -d)"
    echo "Evaluating the other game's link-time guards (assemble only, scratch output)..."
    if ! "${SIGIL_BUILD}" build --aeon . --native --game demo \
            -o "${_xg_out}/demo.bin" --emit-lst "${_xg_out}/demo.lst" >"${_xg_out}/log" 2>&1; then
```

The comment above it says what that does and does not cover: placement, region budget and
image bounds, not demo's own lanes.

### The exemption, derived from the list

`tools/needs_build_lane.py --shapes-built S...` computes EXEMPT = `tools/conftest.py`
BUILD_ARTIFACTS minus each listed shape's `.bin`/`.lst`. For A that is `demo.bin, demo.lst`;
for B it would be all four demo artifacts, with no other change. An unknown shape is COULD
NOT RUN (a typo would otherwise exempt the shape it misspelt).

`tools/conftest.py` now records each marked case's declared artifacts and, when deferred,
the ones that deferred it, as JUnit properties (`needs_build_declared`,
`needs_build_unusable`; inert without `--junit-xml`, skip text unchanged). A deferral is
EXEMPTED only when that record exists and every artifact in it is exempt. It is printed as
`EXEMPTED` by name (with any built artifact the case also declares) and counted on the
summary line, which now reads `N ran, N deferred, N failed, N exempted`. Every other
deferral is still exit 2, and so is a run where everything was exempted. Without
`--shapes-built` (the nightly, a hand run) nothing is exempt.

**Design call: "every unusable artifact exempt", not "every declared artifact exempt".**
The stricter rule would make B more than one line: under B the segments parent declares
`s4.debug.bin`, `s4.debug.lst` (built) and `demo.debug.lst` (not), and would be COULD NOT
RUN. B's proposal already gives that test up to the nightly, so under B it is EXEMPTED, and
the EXEMPTED line names the s4.debug artifacts it also declares so the loss is visible.
Under A no case straddles (below).

### Every needs_build case under A

(from the source markers, and named RAN/EXEMPTED by the tip run's lane, below)

| case | declares | under A |
|---|---|---|
| test_anim_frame_bound::test_gate_is_green_on_the_built_rom | s4.debug.lst, s4.debug.bin | runs |
| test_anim_frame_bound::test_every_pair_proved_red_first_in_both_directions | s4.debug.lst, s4.debug.bin | runs |
| test_bg_emit…::test_the_live_tree_growth_path_is_sound_and_its_pads_are_real | s4.lst | runs |
| test_deb2_appendix[s4.bin] | s4.bin, s4.lst | runs |
| test_deb2_appendix[s4.debug.bin] | s4.debug.bin, s4.debug.lst | runs |
| test_deb2_appendix[demo.bin] | demo.bin, demo.lst | **EXEMPTED** |
| test_deb2_appendix[demo.debug.bin] | demo.debug.bin, demo.debug.lst | runs |
| test_demo_specialization_witness…::test_raster_hint_no_longer_equals_the_gap_to_sfxblobwintab | s4.debug.lst | runs |
| test_effects_gates_segments::test_segmented_parent_checks_the_row_set_it_aggregated | s4.debug.bin, s4.debug.lst, demo.debug.lst | **runs** (all three built) |
| test_effects_gates_segments::test_segment_child_writes_its_rows_as_json | s4.debug.bin, s4.debug.lst | runs |
| test_system_pool_release_empty::test_release_rom_never_loads_a_system_slot_address | s4.bin, s4.lst | runs |
| test_system_pool_release_empty::test_debug_rom_still_contains_the_writers_the_release_rom_lacks | s4.debug.bin, s4.debug.lst | runs |
| test_tool_selftests::test_dplc_straddle_selftest_proves_its_gate_red | s4.lst, s4.bin | runs |
| test_zx0r_resume_net::test_the_checks_are_in_the_release_rom | s4.lst, s4.bin | runs |

13 run, 1 exempted. The multi-artifact tests (the segments parent above all) run.

### The planted second deferral, on the real artifacts

Hermetically, `test_a_second_deferral_is_still_could_not_run` (and red-first row R6, below).
Then for real, over the tip run's own artifacts and threshold (T0 `1789349608`), the lane
exactly as landing_build.sh called it, control first:

```
md5 s4.lst before: e589eba24ea8b4b3a33aea551e156aba
control  rc=0  pytest exit 0 — 14 case(s) in the report: 13 ran, 0 deferred, 0 failed, 1 exempted
  (s4.lst moved aside: an artifact of a shape the check DOES build)
planted  rc=2  pytest exit 0 — 14 case(s) in the report: 8 ran, 5 deferred, 0 failed, 1 exempted
  DEFERRED  tools.test_bg_emit…::test_the_live_tree_growth_path_is_sound_and_its_pads_are_real  — … s4.lst (absent)
  DEFERRED  tools.test_deb2_appendix::…[s4.bin]  — … s4.bin (stale — …/s4.lst does not exist) …
  DEFERRED  tools.test_system_pool_release_empty::test_release_rom_never_loads_a_system_slot_address  — …
  DEFERRED  tools.test_tool_selftests::test_dplc_straddle_selftest_proves_its_gate_red  — … s4.lst (absent) …
  DEFERRED  tools.test_zx0r_resume_net::test_the_checks_are_in_the_release_rom  — … s4.lst (absent) …
  EXEMPTED  tools.test_deb2_appendix::…[demo.bin]  — deferred only on demo.bin, demo.lst, …
COULD NOT RUN: 5 marked test(s) DEFERRED.
md5 s4.lst after: e589eba24ea8b4b3a33aea551e156aba   (moved back, not rebuilt)
restored rc=0  pytest exit 0 — 14 case(s) in the report: 13 ran, 0 deferred, 0 failed, 1 exempted
```

**A first attempt at this is void, and is recorded as such:** its script did not export
SIGIL_BUILD, so the provenance primitive called every pair stale and the CONTROL was already
red (`0 ran, 13 deferred`). A red control makes the planted run meaningless either way. Re-run
with the variable exported, above.

## D: the two lanes are shape-independent, re-established on the base

**From source** (base `d4d7977d`):
- No Python file under `tools/` reads `DEBUG`, `GAME`, `ROM_NAME`, `SOUND_*`, `STRESS_*`,
  `CONTRACTS`, `FAST` or `NO_LINT` from the environment (a grep of every
  `environ.get(`/`environ[`/`getenv(` name: none of these appears).
- `build.sh` exports only `SIGIL_REV` (the same value in every shape) and, under
  `CONTRACTS=0` only, `SIGIL_CONTRACTS`; there is no `set -a`. `GAME` and `ROM_NAME` are
  unexported shell variables; demo's `build.conf` assigns `SOUND_DRIVER_ENABLED` with `:=`,
  unexported. So between shapes the lanes' environment differs by `DEBUG=1` alone (it is in
  the environment because the caller runs `env DEBUG=1 ./build.sh`).
- `tools/emp_expect_fail.py` hard-codes `--game sonic4`, writes to a tempdir, and sets only
  `NATIVE_DEBUG=1` itself (for its link rows); it reads source files, no artifact.
- The pre-build lane deselects `needs_build`; `tools/conftest.py` fails any unmarked test
  that skips for a build artifact. The shell scripts that name DEBUG
  (`landing_build.sh`, `nightly_effects_gates.sh`, `seed-worktree.sh`) either unset it, set
  it for their own builds (the nightly, whose only test-run path is `--checkout-only`,
  which exits before any build), or print it in a message.

**The one thing source cannot show is what the sigil binary reads.** So both lanes were run
on the base with DEBUG unset and with DEBUG=1, under an LD_PRELOAD shim that logs every
`getenv()` name any dynamically linked process looks up (sigil imports `getenv` and
`environ`; Rust's `std::env::var` calls libc `getenv`). Results (`.runlogs/envprobe/`):

```
sigil[unset]  rc=0 md5=0de120e31f1b94318fedac5a0780661f
sigil[debug1] rc=0 md5=0de120e31f1b94318fedac5a0780661f
sigil ROM: IDENTICAL
listing diff lines (paths normalised): 0
expect_fail[unset]  rc=0 secs=176 emp_expect_fail: OK — 55/55 cases (53 comptime + 2 link)
expect_fail[debug1] rc=0 secs=136 emp_expect_fail: OK — 55/55 cases (53 comptime + 2 link)
expect-fail output: identical once per-case timings are removed (58 lines each)
pytest[unset]  rc=0 2672 passed, 2 skipped, 14 deselected, 5 warnings, 140 subtests passed
pytest[debug1] rc=0 2672 passed, 2 skipped, 14 deselected, 5 warnings, 140 subtests passed
pytest per-test outcome diff lines: 0 (outcome rows: 2674)
distinct names sigil looks up (union): AEON_DIR GLIBCXX_TUNABLES NATIVE_DEBUG
  SIGIL_BLOB_LEN_DRIFT SIGIL_CENSUS_BUDGET SIGIL_CENSUS_EXPLABEL SIGIL_CENSUS_INCLUDE
  SIGIL_CENSUS_LAYOUT SIGIL_CONTRACTS SIGIL_WARNINGS TMPDIR
```

No process in any lane looked up DEBUG, GAME or ROM_NAME (also searched as substrings, since
two processes' concurrent writes can glue names together: the only DEBUG-bearing names are
NATIVE_DEBUG, PYTHONDEBUG, PYTHON_DISABLE_REMOTE_DEBUG, PYTHONNODEBUGRANGES and EXPAT_*).
NATIVE_DEBUG is set by `emp_expect_fail.py` itself, never by build.sh. SIGIL_CONTRACTS is the
same in every shape. **No shape dependence found; D proceeds.** (The getenv trace cannot see a
program that iterates `environ` for a prefix; the byte-identical ROM and listing and the
identical outcomes are what cover that.)

## D: how the lanes run once, and how the caller is proven

**Design call: the lanes run inside the first shape's build.sh, not in landing_build.sh.**
The brief asked landing_build.sh to run them itself "with the SAME selection and flags
build.sh would have used", derived and not retyped. Letting build.sh run them in exactly one
shape is the strongest form of that: selection, flags, the `gate strict` wrapper AND the
pre-state (the sound emit, compression vectors, the budget check that precede them) are
byte-for-byte a person's `./build.sh`, and nothing is copied. Running them from
landing_build.sh before any build would have run them before `emit_sound_blob` and
`gen_compression_vectors`, i.e. on a different pre-state than any build uses.

- A lane failure fails that build.sh, so `EXIT_s4=FAILED`, `finished=1`.
- Inability: `python3` without pytest is now COULD NOT RUN (exit 2) in landing_build.sh before
  any build, because build.sh's pytest lane only WARNS then and the receipt would otherwise
  claim lanes that never ran. `FAST`/`NO_LINT` were already refused; no `-nl` is passed.
- If the carrier fails, the next shape runs the lanes itself: they are never skipped on a
  build that did not pass. `finished=` is still the last line.

**The knob: `AEON_LANDING_LANES_RECEIPT`** (build.sh block `LANDING_LANES_RECEIPT`, right after
`NO_LINT_KNOB`). landing_build.sh writes a receipt (`landing_pid`, `carrier`, `lanes=passed`)
into a `mktemp -d` outside the tree (removed on exit; an untracked file in the tree would read
as a CHANGED tree to the land gate) only after the carrier exited 0, and passes its path to
every later shape. build.sh honours it only when ALL hold, and otherwise REFUSES (exit 1):

1. the receipt exists, says `lanes=passed` for a named carrier, and names a pid > 1;
2. that pid is an **ancestor of this build.sh**, walked through `/proc/<pid>/stat`;
3. that ancestor's command line runs a script named `landing_build.sh`;
4. that ancestor's working directory is this build's directory.

**Why it holds, and why it is not a second FAST=1.** A marker alone ("landing sets X") is
satisfied by `X=1 ./build.sh` in any shell, which is FAST=1 with a different name. Requiring a
LIVE `landing_build.sh` process ABOVE the build, in the same directory, means an exported
value, one left in a shell profile, or one inherited from a finished landing run (its pid is
gone, its receipt dir deleted) all refuse, loudly. What it does not stop is deliberate forgery
(a process renamed `landing_build.sh`); nothing in a file anyone can edit can. It stops the
shortcut. An unreadable `/proc` finds no ancestor and refuses (unmeasurable is not honoured).

**The refusal, by hand, at `278c9ac5`** (exit 1, and the refusal is the FIRST line of output,
before any build work):

```
$ AEON_LANDING_LANES_RECEIPT=/tmp/no-such-receipt ./build.sh
exit=1
ERROR: AEON_LANDING_LANES_RECEIPT is set, and only tools/landing_build.sh may set it.
  It skips the shape-independent lanes (the pre-build `pytest tools -m "not needs_build"`
  and emp_expect_fail) in a shape AFTER tools/landing_build.sh ran them green in an
  earlier shape of the SAME run. It is not a speed knob. Refused because
  there is no readable receipt at /tmp/no-such-receipt.
  Unset it. A hand build that skips lanes is NO_LINT=1, which says so.

$ AEON_LANDING_LANES_RECEIPT=.runlogs/fake-receipt ./build.sh
  (a well-formed receipt naming the calling shell: a LIVE ancestor, not landing_build.sh)
exit=1
ERROR: AEON_LANDING_LANES_RECEIPT is set, and only tools/landing_build.sh may set it.
  ... Refused because
  its ancestor 1347354 is running '/usr/bin/zsh -c source ...', not tools/landing_build.sh.
```

(The second message quoted the ancestor's whole multi-line command; `504a70d0` shortens it to
120 characters on one line.)

## The A→B swap

The one line:

```diff
-LANDING_SHAPES="s4 s4.debug demo.debug"
+LANDING_SHAPES="s4 s4.debug"
```

`tools/test_landing_build_trim.py::test_the_A_to_B_swap_is_one_line_and_derives_everything_else`
makes it in a sandbox copy (asserting the diff is exactly one line), runs the real script over
a stub build.sh, and checks: only s4 and s4.debug build, the lanes run once, the md5 block
hashes exactly those two ROMs, the lane receives exactly `--shapes-built s4 s4.debug`, and the
REAL lane's exemption equals the artifacts of the shapes the sandbox did not write (observed on
disk, not typed): the four demo artifacts. B is not shipped.

## The land gate

`tools/land_gate.py`, `tools/test_land_gate.py`, `tools/test_land_gate_classifier.py` and
`tools/test_landing_build_stamp.py` were read for four-shape assumptions. The gate's logic
(`cmd_finish`) keys on HEAD, the content key, the clean flag and rc only, so nothing in it
counted shapes; its docstrings said "four-shape" and now describe the LANDING_SHAPES check.
`test_landing_build_stamp.py` DID assume four: its failed-shape row and its three during-the-run
rows (commit, edit, kill) were keyed to the stub shape `demo`, which A no longer builds, so under
A they would never have fired. They now act on the LAST shape of the list, read from the script.
The stamp is still written only on `finished=0` over a tree clean at the start and unmoved
(those rows are green again under A). A stamp now means "the TRIMMED check finished 0 over this
code", as intended.

## Every check added or changed, proven red first

Driver: scratch `redfirst.py`, run at `c61740c9` (retroactively, after the step-5 test fix).
Each row: the committed file clean; one exact-string mutation, shown on disk; the named test RED;
restored from `git show HEAD:<path>`; `git diff --exit-code` clean; the test GREEN again.

| row | check | mutation (on disk) | test(s) mutated → restored |
|---|---|---|---|
| R1 | receipt: ancestor | `"${_lr_found}" != 1` → `== 2` | test_build_env_knobs::test_a_hand_set_receipt_is_refused_naming_landing_build: 1 failed → 1 passed |
| R2 | receipt: name | `*"/landing_build.sh "*\|*" landing_build.sh "*) ;;` → `*) ;;` | …ancestor_must_be_named_landing_build_and_work_in_this_directory + the hand-set row: 2 failed → 2 passed |
| R3 | receipt: directory | `"${_lr_cwd}" != "$(pwd -P)"` → `== "/nowhere"` | …ancestor_must_be_named…: 1 failed → 1 passed |
| R4 | expect-fail call site honours the receipt | `LANDING_LANES_SKIP == "1"` → `"x"` (expect-fail) | test_with_a_receipt_neither_shared_lane_runs_and_both_say_so: 1 failed → 1 passed |
| R5 | pytest call site honours the receipt | the same, at the pytest site | same test: 1 failed → 1 passed |
| R6 | exemption narrow (the planted second deferral) | exempt ANY deferral once an exemption exists | test_needs_build_lane::test_a_second_deferral_is_still_could_not_run: 1 failed → 1 passed |
| R7 | exemption needs EVERY unusable artifact exempt | `<= exempt` → `& exempt` | test_a_case_that_also_misses_a_built_shape_is_not_exempted: 1 failed → 1 passed |
| R8 | no record, no exemption | `d[2] is None` counts as exempt | test_a_deferred_case_without_the_conftest_record_is_not_exempted: 1 failed → 1 passed |
| R9 | unknown shape refused | `if not pair <= arts:` → `if False:` | test_an_unknown_shape_is_could_not_run: 1 failed → 1 passed |
| R10 | exemption never covers a built shape | `return sorted(arts - built)` → `sorted(arts)` | lane derivation + test_landing_lane_shapes runner row + the swap test: 3 failed, 1 passed → 4 passed |
| R11 | lanes once: receipt handed on | the `cmd+=("AEON_LANDING_LANES_RECEIPT=…")` line removed | test_landing_build_trim::test_the_check_builds_exactly_its_shapes_and_runs_the_shared_lanes_once: 1 failed → 1 passed |
| R12 | lanes never skipped on a failed carrier | receipt written whether or not the carrier passed | test_a_failed_carrier_hands_the_lanes_to_the_next_shape: 1 failed → 1 passed |
| R13 | A→B: lane list derived | `--shapes-built "${SHAPES[@]}"` → typed `s4 s4.debug demo.debug` | test_the_A_to_B_swap_is_one_line_and_derives_everything_else: 1 failed → 1 passed |
| R14 | A→B: md5 line derived | `md5sum "${SHAPES[@]/%/.bin}"` → typed three names | same swap test: 1 failed → 1 passed |
| R15 | conftest records the deferral | the `needs_build_unusable` append → `pass` | test_a_deferral_on_a_shape_the_caller_does_not_build_is_exempted_and_named: 1 failed → 1 passed |

`rows not proven: 0`; the tree was clean after every restore and after the run.

The first run, at `278c9ac5`, proved 13 of 15: R13 (a typed `--shapes-built` list) and R14 (a
typed md5 line) stayed GREEN, because the swap test compared a prefix of the lane's argv and did
not read the md5 block at all. Fixed in `504a70d0`; every row was then re-run.

All the new and changed tests run in build.sh's pre-build tool-suite lane
(`pytest tools -m "not needs_build"`, build-fatal): in every hand `./build.sh`, and once per
landing check (in its carrier shape).

## Control against tip

Both runs: `SIGIL_BUILD` = `sigil 0.1.0 (1532b72f)`, md5(SIGIL_BUILD)
`739016647ad1ab92f4d072e3013b8818`. **Another agent was building on this machine throughout**,
so the load is noisy: compare proportions as well as seconds.

### Control: untouched base `d4d7977d`, `.runlogs/control-0913.log`

Start 20:58:00 (load 3.94, 5.42, 7.26), end 21:12:53 (load 4.69, 5.57, 6.43 at the next
reading): **893 s (14 min 53 s)**. `finished=0`, STAMP WRITTEN for key `606d8288…`.

| step | secs | pre-build pytest lane | expect-fail |
|---|---|---|---|
| s4 | 221 | 2672 passed, 2 skipped, 14 deselected, 140 subtests (70.04 s) | 55/55 |
| s4.debug | 227 | 2672 passed, 2 skipped, 14 deselected, 140 subtests (67.31 s) | 55/55 |
| demo | 215 | 2672 passed, 2 skipped, 14 deselected, 140 subtests (69.69 s) | 55/55 |
| demo.debug | 211 | 2672 passed, 2 skipped, 14 deselected, 140 subtests (70.27 s) | 55/55 |
| needs_build lane | ~18 (pytest's own line) | `14 case(s) in the report: 14 ran, 0 deferred, 0 failed` | |

md5: `0de120e31f1b94318fedac5a0780661f  s4.bin`, `45ddcada0a5af458e386116b1c95813d  s4.debug.bin`,
`e3e7190e8ada7f72c7d258a18d3c2fb5  demo.bin`, `6bd0ecd351e7b526608a616a38b79945  demo.debug.bin`.
The shared pytest lane ran 4 x 2672; expect-fail ran 4 x 55.

### Tip: `c61740c9`, `.runlogs/tip-0913.log`

Start 21:33:28 (load 4.57, 5.28, 6.14), end 21:37:45 (load 2.97, 4.45, 5.63 at the next
reading): **257 s (4 min 17 s)**. `finished=0`, STAMP WRITTEN for key `efdd2a38…`.

| step | secs | shared pytest lane | expect-fail |
|---|---|---|---|
| s4 (carrier) | 218 | 2688 passed, 2 skipped, 14 deselected, 140 subtests (69.44 s) | 55/55 |
| (receipt) | | `--- shared lanes: ran ONCE, green, inside the s4 build; the shapes after it skip them on a receipt ---` | |
| s4.debug | 19 | NOT RUN in this shape (banner + receipt from pid 1512902) | NOT RUN |
| demo.debug | 3 | NOT RUN in this shape | NOT RUN |
| needs_build lane | ~16 (pytest's own line) | `14 case(s) in the report: 13 ran, 0 deferred, 0 failed, 1 exempted` | |

The lane's own lines: `shapes this caller builds: s4 s4.debug demo.debug; does NOT build: demo`,
`exempt: demo.bin, demo.lst`, the 13 `RAN` rows (the table above, the segments parent among
them), `EXEMPTED  tools.test_deb2_appendix::…[demo.bin]  — deferred only on demo.bin, demo.lst,
written only by a shape this caller does not build`, and `OK — all 13 marked test(s) this
caller's shapes can reach ran and passed; 1 EXEMPTED above.`

md5: `0de120e31f1b94318fedac5a0780661f  s4.bin`, `45ddcada0a5af458e386116b1c95813d  s4.debug.bin`,
`6bd0ecd351e7b526608a616a38b79945  demo.debug.bin`: **all three identical to the control's**.

**The later shapes ran everything but the two lanes.** Their step lines (Running/Checking/
Evaluating/Building/Build complete/gate totals/the post-sigil lane) were diffed against the
control's same shapes: the only differences are the banner, the two `NOT RUN` lines in place of
the two lanes, the `--artifacts-built-after` instant, and the post-sigil lane's deselected count
(2690 vs 2674, the same 16 new tests). The post-sigil lanes are identical: s4.debug 6 passed,
8 skipped; demo.debug 1 passed, 13 skipped. So 19 s and 3 s are real.

**Proportions (the load was similar: s4, the same work in both runs, took 218 s vs 221 s).**
Whole check 257 s against 893 s: **29%**, a saving of 636 s (10 min 36 s). Demo normal's
215 s is gone (A). Each later shape lost about 210 s (s4.debug 227 → 19, demo.debug 211 → 3):
that is the true per-shape cost of the two shared lanes at this load, **not** the proposal's
~93 s. The pre-build pytest lane is ~70 s as priced, but emp_expect_fail cost ~138 s here,
against the ~23 s in build.sh's header table (the base-tree probe measured 136 s and 176 s for
it standalone under the same load). So D alone is worth more than the proposal priced.

**The shared-lane count.** The tip's pre-build lane ran once, with **2688** passed against the
control's 2672 per shape. The difference is exactly this parcel's own new rows, accounted from
the diff rather than assumed: `git diff d4d7977d..HEAD -- 'tools/test_*.py'` adds 18 `def test_`
lines and removes none, and two of those (`test_built`, `test_demo_normal`) are fixture TEXT
inside the `ONE_BUILT_ONE_DEMO` string in `tools/test_needs_build_lane.py`, never collected. The
16 collected ones: 6 in `test_build_env_knobs.py` (the receipt and SHARED_LANES rows), 4 in
`test_landing_build_trim.py`, 6 in `test_needs_build_lane.py`. 2672 + 16 = 2688. So the tip ran
ONE suite's worth (2688 once) where the control ran four (4 x 2672 = 10688). Skipped (2) and
deselected (14) are unchanged.

## What is still open

- **B** is the owner's: one line. Under it the segments parent is EXEMPTED before merge and
  graded nightly only, and demo debug's memory-layout checks likewise.
- The getenv trace is a one-off measurement, not a gate: a future tool that starts reading
  DEBUG would make a shared lane shape-dependent with nothing to notice. Candidate: a pytest
  row that fails if any `tools/*.py` reads `DEBUG`/`GAME`/`ROM_NAME` from the environment.
