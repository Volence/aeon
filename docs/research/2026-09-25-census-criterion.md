# CENSUS-CRITERION-TOO-NARROW: the census counts drivers by what they do, and credits only executions (2026-09-25)

Branch `parcel/census-criterion`, base `db0d0f23`. The booking is closed in place in
`docs/DEFERRED_WORK.md`, in the section "⚠ EVERY INSTRUMENT-POPULATION FIGURE IN THIS FILE IS OVER A
NARROW CRITERION". Dated corrections sit next to each old figure, and the old figures are still there.

## Which census

The booking points at the census behind the keepalive accounting: `tools/keepalive_population.py`.
`keepalive_lane.py` and `tools/keepalive_manifest.toml` consume it. `tools/cart_coverage_census.py`
is a different census. It counts cart-check coverage over its own import-defined population, and
this parcel does not change it. It enters here only because its CANARIES table was the
string that credited `evict_witness` and then `sfx_audition` as "reachable".

## The predicates, old and new

### Population

| | predicate |
|---|---|
| **old** | a `tools/*.py` (not `test_*`, not the lane's two files) whose text contains `BusClient` |
| **new** | the same files, admitted by what their code DOES (`drives()`, read from the AST) through any of five arms |

The five arms:

| arm | admits a file that ... | why it is an arm |
|---|---|---|
| `import` | imports anything from `aether`, `aether_instance` or `launcher` | every emulator connection in the tree comes from one of these three modules (the bus client, the spawner, and the legacy headless launcher) |
| `protocol` | has a code string that is exactly an Aether method name (`^emulator/[a-z_]+$`), outside docstrings and prose statements | it speaks the bus protocol on a client it was handed; this is the arm that admits `cart_identity` |
| `socket` | uses `socket.AF_UNIX` itself | the shape `evict_witness` had before 2026-09-19; no file needs this arm today (see "Arm contribution") |
| `borrow` | uses a sibling member's DRIVER CALLABLE: a top-level def or class whose body reaches a connection, taken to a fixpoint across modules | admits `base_swap_witness` (`ramp_authored_witness.run` spawns) and `depth_onset_probe` (`curve_desc_probe.Server`). Importing a sibling's arithmetic, such as `raster_cost_probe.parse_lst`, does not count |
| `child` | runs a member, or oracle-old's `ab_runner.py`, from an argv display that contains an interpreter | admits `effects_gates`. `ab_runner.py:91` is `from launcher import headless_emulator`, read on 2026-09-25 |

**Why this contains the four booked tools, plus two more:**

- `effects_gates`: `child` only. It runs 16 member gates and `ab_runner.py` as subprocesses.
- `cart_identity`: `protocol` and `borrow`. It calls `emulator/read_memory` on the client it is passed.
- `depth_onset_probe`: `import` (`assert_rust_server`), `borrow` (`curve_desc_probe.Server`) and `protocol`.
- `cart_verify_spawn_proof`: `import` (`AetherInstance`) and `borrow`.
- `base_swap_witness`: `borrow` only, through `ramp_authored_witness.run`.
- `staging_lifetime_timeline`: `borrow` (`tick_variance_probe.Server`) and `protocol`.

The last two are **new findings**. The booking did not list them.

`cart_coverage_census.py` **leaves** the population. It names `BusClient` only in strings (an arm
description and a canary note) and drives nothing.

**Where the booking was wrong:**

- The gap was six tools, not four.
- `cart_identity` and `effects_gates` do not drive "through `aether_instance`". The first is a
  helper that is handed a client. The second drives only through child processes.
- The 09-19 table claims `landing_build.sh` runs `effects_gates`. It does not. Its only python
  invocations are `land_gate.py` and `needs_build_lane.py`.
- The same table claims `depth_onset_probe` is "imported by `cart_coverage_census.py`". It is not.
  It is named in a CANARIES string.

### Reachability

| | predicate |
|---|---|
| **old** | transitive over a tool's NAME, matched with word boundaries, anywhere in the code of any tracked `.py`/`.sh`. Comments and docstrings were stripped from `.py` files only, and short string literals were kept |
| **new** | transitive from the same entry points (`build.sh`, `tools/landing_build.sh`, `tools/nightly_effects_gates.sh`, every `tools/test_*.py` not in `LANE_BOOKKEEPING`), over EXECUTING edges only (`exec_edges()`) |

The executing edges:

- in a `.sh` file: a `python3 … x.py` command, or `x.sh` in command position. Comment lines and
  `echo`/`printf` segments are removed first.
- in a `.py` file:
  - an argv display that contains an interpreter (`python3`, `sys.executable`, `bash`), following
    `NAME = …` bindings up to two hops;
  - the argv list or shell string of a `subprocess.*`/`os.system` call;
  - `x.main(...)` on an imported module, or `main` imported from `x`;
  - `runpy.run_path` or `run_module`;
  - a dynamic `importlib.import_module(<non-literal>)` together with a `.main(` call in the same
    file. This credits the module stems that file names in code strings. The table counts here
    only because the same file contains the mechanism that runs it
    (`test_cli_dispatch_refuses`).

A file is read only after something reachable executes it. The first version read every tracked
`.py`. The land-gate audit flagged 42 `docs/` reads from the new test, and the lazy read also
states the truth: nothing that runs has looked at an unreached file.

Things that do **not** credit a tool any more:

- a name in a data table (`cart_coverage_census.CANARIES`, `test_land_gate_classifier`'s path table);
- a regex (`test_landing_lane_shapes`);
- a printed command line (`tile_cache_fill_gate` prints `python3 tools/canopy_record.py`);
- a tuple of script names (`RUNNERS = ("landing_build.sh", ...)`);
- an import of a tool's arithmetic;
- a read of its source text.

## Before and after

Measured on this branch at load average 7 to 20.

| | old criterion (base `db0d0f23`) | new |
|---|---|---|
| population | 85 | **90** (+6 drivers, −`cart_coverage_census`) |
| executed from a real entry point | 42 | **25** |
| unreachable | 43 | **65** |
| manifest `[wired]` | 35 tools / 36 rows | 35 / 36 (unchanged) |
| manifest `[not_wired]` | 50 | **55** |
| `[not_wired]` reasons beginning "reachable" | 33 | **20** (every one verified by test) |
| wired tools executed by something else | 5 | 5 |
| unexecuted AND not wired | 13 | **35** |
| `keepalive_lane.py --list` | exit 0 | exit 0 (90 declared) |

The historical figures from `DEFERRED_WORK.md` that were corrected in place:

| figure | when | corrected to |
|---|---|---|
| 85 / 84 | 09-18 | 90 drivers. 84 is still the count of files that construct a `BusClient`, which is a different criterion |
| 35 reachable / 50 unreachable | 09-19 | 25 / 65 |
| 44 → 43 | 09-25 | 65 of 90 |
| 47 hold / 3 rotted | 09-19 audit | re-graded to 34 hold / 16 not: the 3 rotted, plus 13 "reachable" reasons that are false under the executing rule |

`python3 tools/keepalive_population.py -v` prints every figure above, each driver's arms, and the
parent and edge kind that executes each reachable driver.

### Arm contribution

Files admitted by one arm alone, on this tree:

| arm | files | load-bearing? |
|---|---|---|
| `protocol` | `aether_bytes` | yes |
| `child` | `effects_gates` | yes |
| `borrow` | `base_swap_witness` | yes |
| `import` | none | redundant today |
| `socket` | none | redundant today |

The accounting test cannot see a break in `import` or `socket`, so each has its own synthetic
fixture.

## Per-tool changes

### Population and disposition

| tool | change | disposition (all `[not_wired]`) |
|---|---|---|
| `effects_gates.py` | joined (`child`) | **reachable**: the effects nightly runs it, the merge ritual runs it by hand, and `test_effects_gates_segments` runs it. It is the runner of 16 gates, not one instrument with one verdict |
| `cart_identity.py` | joined (`protocol`, `borrow`) | not an instrument: a helper with no `__main__` |
| `depth_onset_probe.py` | joined | **UNEXECUTED**: nothing imports it or runs it; never measured |
| `base_swap_witness.py` | joined (`borrow`) | **UNEXECUTED as a program**: the wired `role_swap_witness` imports only its `read_const`; never measured |
| `staging_lifetime_timeline.py` | joined | **UNEXECUTED**: zero references anywhere; may inherit `tick_variance_probe`'s refusal (not measured) |
| `cart_verify_spawn_proof.py` | joined (`import`, `borrow`) | **DEAD**: nothing executes it and nothing imports it (see below) |
| `cart_coverage_census.py` | **left** the population (drives nothing) | manifest line removed |

### Reachability credit that changed

Every member whose executed/unexecuted status moved, with its new disposition:

| tool | old credit came from | new credit | new disposition |
|---|---|---|---|
| `aether_bytes.py` | name chain through `aether_instance` | UNEXECUTED (a library) | unchanged: "not an instrument" |
| `aether_instance.py` | name chain through `row_remap_witness`, `row_remap_gate` | UNEXECUTED as a program; its `--smoke` main runs nowhere | unchanged: "not an instrument" |
| `canopy_record.py` | `tile_cache_fill_gate` PRINTS its command line | UNEXECUTED; `test_canopy_record` imports its functions | rewritten |
| `curve_desc_probe.py` | `depth_onset_probe`, via the CANARIES string | UNEXECUTED; only `depth_onset_probe` imports it | rewritten |
| `curve_probe.py` | `test_perspective_floor` imports its arithmetic | UNEXECUTED as a program | rewritten |
| `dma_straddle_exercise.py` | `test_dma_straddle_exercise` imports it | UNEXECUTED as a program | unchanged: the cost reason never claimed reachability |
| `e2_snap_capture.py` | named in `night_settle_capture`'s strings | UNEXECUTED | rewritten; keeps the overwrite-hazard clause |
| `engine_baseline_probe.py` | imported by `parallax_cost_probe` | UNEXECUTED as a program | rewritten |
| `fg_left_edge_gate.py` | CANARIES string | UNEXECUTED as a program; 4 WIRED tools import its functions | rewritten |
| `hblank_window_sweep.py` | `test_hblank_subline` imports its arithmetic | UNEXECUTED as a program | rewritten |
| `night_settle_capture.py` | its test imports it | UNEXECUTED as a program | rewritten |
| `parallax_cost_probe.py` | imported by `curve_probe` | UNEXECUTED as a program; imported by the WIRED `parallax_hscroll_identity` | rewritten |
| `parallax_hscroll_probe.py` | imported by `curve_probe` | UNEXECUTED as a program | reason now opens "UNEXECUTED"; the rest is kept |
| `ramp_boundary_probe.py` | `test_land_gate_classifier` path table | UNEXECUTED | rewritten |
| `reels_witness.py` | `test_reels_witness` imports it and reads its source | UNEXECUTED as a program | rewritten |
| `row_remap_witness.py` | prose and a printed message in `row_remap_gate` | UNEXECUTED | rewritten |
| `sfx_audition.py` | CANARIES string | UNEXECUTED | unchanged: "needs a live emulator a human is listening to" |

### Credit that held, with a corrected source

| tool | what executes it now |
|---|---|
| `evict_witness.py` | only the nightly's `python3 tools/evict_witness.py ...` line. The regex in `test_landing_lane_shapes` no longer counts, which settles the double-credit caveat in today's evict-witness record |
| `cache_hold_probe.py` | `test_cli_dispatch_refuses` drives its `main()` to the usage refusal. It is kept "reachable, but THINLY": the dispatch ladder runs and no emulator ever does. **The 09-19 audit graded it D ("nothing runs it"), and that grade was wrong on that day too** |
| the 16 effects gates (incl. `raster_cost_probe`) | `effects_gates.py`. Each reason now names that runner instead of "reachable in code" |
| `preset_lab_witness.py` | the nightly (unchanged) |

### Wired tools executed by something else

`dplc_coherence_witness`, `glide_ceiling_witness`, `loop_step_over_witness`,
`spring_launch_witness` and `transition_window_probe` are executed by their own tests (`main()`,
or argv through `PROBE`). This was already true under the old rule. It is listed because it
falsifies the 09-19 sentence "all 35 are in the census's nothing-else-runs-this set", which is now
corrected in place.

## `cart_verify_spawn_proof.py`: dead, in the census's sense

Nothing executes it and nothing imports it. Its only mention elsewhere is a comment in
`tools/test_aether_instance.py`, which keeps it out of pytest because it boots a server. It was
run once by hand, on 2026-09-12 (`5d9e0990`), as the five-leg proof of the spawn-time cart check.

The manifest's rule for a tool the lane does not run is a `[not_wired]` entry with a reason, and
it has that entry now, reading "DEAD, by the census's definition". It was **not deleted**, and it
was **not re-run**, so whether it still passes is unmeasured.

## Checks added, and their red evidence

All the checks are in `tools/test_keepalive_lane.py`, which runs in build.sh's pre-build pytest
lane.

| check | red evidence |
|---|---|
| `test_a_reachable_reason_is_true` | **red on the real shipped manifest** at commit 2 of this branch, naming the 13 rows. Green after the manifest commit |
| `test_every_bus_instrument_in_the_tree_is_declared` (existing) | red at commits 1 and 2: 6 UNDECLARED, 1 MISSING |
| `test_each_arm_admits_a_file_that_only_it_reaches` (8 fixtures) | M1, M6, M7, M8 and M9 below |
| `test_a_file_that_only_names_the_bus_is_not_a_driver` (6 fixtures) | M2, M4, M4b and M5 below |
| `test_the_real_population_contains_the_drivers_the_old_criterion_missed` | red under M1 and M8 |
| `test_only_an_executing_reference_makes_a_tool_reachable` | red under M2 and M3 |

Each mutation was quoted with `git diff -U0` before its run. `__pycache__` was cleared before each
run, and the file was restored with `git checkout HEAD --`:

| mutation | result |
|---|---|
| M1 `borrow` arm off | 3 failed (both borrow fixtures and the real-population pin) |
| M2 argv display without an interpreter accepted | 2 failed (the table fixture and the executing-reference test) |
| M3 `echo` stripping off | 1 failed (executing-reference) |
| M4 prose exclusion off for `protocol` | **SURVIVED at first**: the only docstring fixture was also held off by the whole-string match. A second fixture was added, one per guard, and committed. **Rerun: 1 failed** (`bare_doc.py`) |
| M4b method regex unanchored | 1 failed (`helpstr.py`) |
| M5 every def a driver | 1 failed (`arith.py`) |
| M6 `import` arm off | 3 failed |
| M7 `socket` arm off | 1 failed |
| M8 `child` arm off | 3 failed |
| M9 module-form borrow off | 1 failed |

M1, M2 and M3 were run again after the fixture change and again after the lazy-read change. They
were still red each time.

## What is still uncovered

These are stated here and not booked, as the parcel's brief required.

1. **Under-credit from spelling through a variable.** An argv display that spells a tool through
   a parametrized variable (`[sys.executable, tool]` with `tool` coming from a list) is not
   credited. `NAME = "…"` bindings are followed; loop and parametrize variables are not. This
   errs toward "dead", which is the safe side for a list of things that need wiring.
2. **Drivers outside `tools/`.** `docs/superpowers/notes/2026-09-13-f3-runtime-tag/f3rt_run.py`
   and `f3rt_watch.py` import `aether_instance`. The population is `tools/*.py` by scope.
3. **Arms that no file needs.** `import` and `socket` admit no file on their own. Only their
   synthetic fixtures guard them.
4. **Six drivers never measured by any lane parcel.** `depth_onset_probe`, `base_swap_witness`,
   `staging_lifetime_timeline` and `cart_verify_spawn_proof` have never been run by a keepalive
   parcel. Their dispositions are read from source and imports.
5. **"UNEXECUTED" is not "broken".** Of the 65 unreachable drivers, 30 are wired, so the lane runs
   them. The other 35 are the honest gap. The earlier finding still stands: only a run finds a
   tool that imports cleanly and dies on its first bus call.
6. **Unchanged labels.** The lane's output keeps the label "bus instruments in tools/", because
   `tools/nightly_instrument_keepalive.sh` greps for that exact text. The label now counts
   emulator drivers.
