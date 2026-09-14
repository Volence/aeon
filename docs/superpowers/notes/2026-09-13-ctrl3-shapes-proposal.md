# Which of the four builds to keep: a priced proposal (CTRL-3, second half)

2026-09-13, `parcel/ctrl3-land-gate`. For the hub to pick from, unless it judges this a real
tradeoff for the owner. **Nothing here is implemented.** No build was dropped.

## What the four builds are

Before a change joins the main copy of the game, the check command builds the game four ways
and tests each one:

1. **Sonic 4, normal** (`s4.bin`). The game as players would get it.
2. **Sonic 4, debug** (`s4.debug.bin`). The same game with the developer tools switched on.
   This is the one your emulator opens by default, and the one the effects checks play.
3. **Demo, normal** (`demo.bin`). A tiny second "game" that only shows a white box on a blue
   screen. It exists to prove the engine is not secretly tied to Sonic.
4. **Demo, debug** (`demo.debug.bin`). The tiny game with the developer tools on.

Each takes three and a half to four minutes on your PC, so the whole check runs about
15 minutes (measured 15 min 18 s on 2026-09-13, with another job running).

## The recommendation

**Stop building "demo, normal" in the pre-merge check. Keep the other three.** That saves
about three and a half minutes per merge (3 min 35 s measured, below).

What you give up: a problem that shows up **only** in the normal build of the tiny demo game
would reach the main copy and be caught by the nightly check the next morning instead of
before the merge. That has happened once in the project's recorded history, and it was a size
change spotted by comparing checksums, not a breakage. The normal demo build is also the most
covered of the four already: every Sonic 4 build quietly assembles it to check it still fits
and links.

What stays: the Sonic 4 normal build is what would ship, and it caught two real problems no
other build showed (a blank screen and a failed link). Sonic 4 debug is what your emulator
runs and what the effects checks need. Demo debug carries the one test that compares the two
games and the demo's memory-layout checks, which nothing else does.

"Stop building it in the check" is not "delete it". The build script still builds it on
request, the nightly job still builds all four every night, and the assembler project's own
tests still build it from our source.

**A separate saving that drops nothing (option D below):** about a minute and a half of each
build is the same set of tests run again, identically, four times. Running it once would save
about four and a half more minutes per merge with no loss of checking. It needs a small change to the
build script and a ruling, because the build script currently refuses every non-standard
switch on purpose. It can be taken with any of the options.

## The options

| | What changes | Saved per merge | What would reach the main copy unseen (caught by the nightly next morning instead) |
|---|---|---|---|
| **A (recommended)** | drop demo normal from the check | about 3 min 35 s | a problem only demo's normal build shows: a debug-only change that shifts demo's normal ROM (2026-08-19, spotted by checksum); one test row (the symbol appendix in `demo.bin`) |
| B | drop both demo builds | about 7 min 14 s | the above, plus: the test comparing the two games' effects code, demo debug's memory-layout checks, and the effects checks' demo comparison (2026-09-03, demo paid 104 bytes where 30 were expected, found through the demo debug listing). "The engine works for other games" becomes a nightly-only fact |
| D (no drop) | keep all four, run the shared tests once | about 4 min 40 s (3 x the shared part) | nothing |

**Not offered: dropping either Sonic 4 build.** Sonic 4 normal is the only build that showed
two of the recorded problems (below), and it is what ships. Sonic 4 debug is what the owner's
emulator launcher, the effects checks, the nightly job and seven of the fourteen build-reading
tests use; dropping it from the check would mean the effects checks' ROM was never built
before a merge.

If A is picked, these move together (for whoever implements it): `tools/landing_build.sh`'s
`run_shape demo` line; its needs_build lane treats any deferral as COULD NOT RUN, and
`test_deb2_appendix[demo.bin]` would then defer, so the lane needs a declared exemption for
exactly that pair; the docs that say "four shapes" (`CLAUDE.md`, `docs/OVERSEER-REFERENCE.md`
Landing lane, `docs/EMP_PITFALLS.md` Trap C). `build.sh` and the nightly do not change.

## Measured detail

### Cost per build (from `tools/landing_build.sh` logs)

**Run 2 is the one to price from:** the verification run of this parcel's tip `09b6e8a9`,
2026-09-13 20:07:27-20:22:45 local, `finished=0`, the `secs=` each `EXIT_` line now carries.
Load average 4.2 rising to 9.9 during it (another agent was building), so the absolute seconds
are inflated; the proportions are what matter.

| build | seconds (run 2) | of which: the shared tool-suite tests | shared `emp_expect_fail` |
|---|---|---|---|
| Sonic 4 normal | 230 | 66 (2651 passed) | yes, 55/55 cases |
| Sonic 4 debug | 230 | 73 (2651 passed) | yes, 55/55 |
| demo normal | 215 | 68 (2651 passed) | yes, 55/55 |
| demo debug | 219 | 72 (2651 passed) | yes, 55/55 |
| needs_build lane (once) | 24 | 14 ran, 0 deferred | |
| **whole check** | **918** (15 min 18 s) | | |

Run 1 (19:23-19:35, `6a6b0baa`, load 5.0 to 7.6) agrees: 217, 215 and 197 s for the first three
(its demo debug build stopped early on a test failure this parcel caused and then fixed).

So, per merge at run 2's load: **A saves 215 s (3 min 35 s); B saves 434 s (7 min 14 s); D saves
about 3 x (70 s of tests + about 23 s of expect-fail, the figure in `build.sh`'s header table)
= about 4 min 40 s.** A and D together: about 8 min 15 s, a check of about 7 minutes.

**Why option D is real.** The pre-build tool-suite lane is `pytest tools -m "not needs_build"`.
It takes no shape input (no test reads `DEBUG`, `GAME` or `ROM_NAME` from the environment;
`build.sh` exports neither), and it ran the identical set in all four builds of each run
(2613 tests in run 1; 2651 in run 2, after this parcel's own tests joined). The expect-fail
lane builds sonic4 with `NATIVE_DEBUG=1` whatever the shape (`tools/emp_expect_fail.py`),
55/55 each time. So roughly 90 s of every build (66-73 s of tests plus about 23 s of
expect-fail) is the same work. Run once instead of four times: about 3 x 93 = 280 s saved.

### What each build uniquely catches

**Tests that read a build's output** (the `@pytest.mark.needs_build` markers, resolved per
test by pytest's own collection, 14 tests in all):

| build | tests needing its files | which |
|---|---|---|
| Sonic 4 normal | 5 | `test_bg_emit` (listing), `test_deb2_appendix[s4.bin]`, `test_system_pool_release_empty` (the release ROM never writes a system slot), `test_tool_selftests::dplc_straddle`, `test_zx0r_resume_net` (checks are in the release ROM) |
| Sonic 4 debug | 7 | `test_anim_frame_bound` x2, `test_deb2_appendix[s4.debug.bin]`, `test_demo_specialization_witness` (a real listing), `test_effects_gates_segments` x2, `test_system_pool_release_empty` (its debug control) |
| demo normal | 1 | `test_deb2_appendix[demo.bin]` |
| demo debug | 2 | `test_deb2_appendix[demo.debug.bin]`, and the segments parent, which needs `demo.debug.lst` together with the Sonic 4 debug pair |

**Checks that run only in some builds** (from `build.sh`):
- Sonic 4 only, in both of its builds: the sound emit, `collision_consistency`, the effects
  seam gate, the editor palette and band-drift goldens, the background-animation room gate,
  the DPLC straddle, DMA headroom, sprite tilt, insta-shield and loop crossover gates.
- Release only: `plane_base_swap_gate` and `reels_gate` assert their debug words emit **zero
  bytes** in the release ROM; only the release build checks that nothing debug-only leaks into
  what ships.
- Per build, every build: sigil's own checks (`ensure`s, the contract closure), placement and
  region budgets, `s4budget`, the post-build test lane, and for the demo the checks that
  Sonic-only content is absent.
- **Already done for other builds without building them:** every build runs `sigil build
  --check` over all four shapes plus `--config-a` in its test lane
  (`tools/test_extern_guard_reachability.py`), which checks their guards but not placement; and
  every Sonic 4 build assembles demo **normal** in full to check its placement, budget and
  image bounds (`build.sh`, "Evaluating the other game's link-time guards"). Nothing does the
  same for demo debug.

**History: problems only one build showed** (searched `docs/DEFERRED_WORK.md`,
`docs/OVERSEER-LOG.md`, `docs/lane-log.jsonl`, `docs/lens-findings.jsonl`, and `git log`):

| date | what | which build showed it | other builds | caught by |
|---|---|---|---|---|
| 2026-08-14 (`f2adf85c`) | boot table cursor read the alignment pad: blank screen, "in BOTH games" | both **normal** builds | debug builds rendered | no gate at all; "nothing in the gate set looks at a screen" |
| 2026-08-14 (`58d6ee43`) | listing symbols 4 bytes high in the sound-off shapes (a sigil listing bug) | **demo** | Sonic 4 fine | by hand |
| 2026-08-19 (DEFERRED_WORK, Fix F5) | a zero-byte debug-only label moved `demo.bin`'s checksum; "`s4.bin` did not move, so a release CRC check on sonic4 alone would have missed it" | **demo normal** | `s4.bin` unchanged | a checksum comparison, not a red build |
| 2026-09-03 (`16489e83`) | an unconditional role swap cost demo 104 bytes, not 30 | **demo** image, measured through `demo.debug.lst` | Sonic 4 unaffected | the effects gates' demo row |
| 2026-09-06 (DEFERRED_WORK, BAND-LIVE-BUILD) | a `use` resolved in every shape broke the **plain** link; "a `DEBUG=1`-only check would have missed the whole subject" | **Sonic 4 normal** | debug linked | a normal build |
| 2026-09-10 (DEFERRED_WORK, ITEM 0) | the demo build failed at a scene DSL line (a deliberate intermediate step) | **demo** | Sonic 4 has scenes | a demo build |

Per build: Sonic 4 normal 2, Sonic 4 debug **0**, demo normal 1 or 2, demo debug 1 (the demo
entries whose record does not say normal or debug are counted for neither). The "always build
all four" rule itself (`docs/EMP_PITFALLS.md` Trap C) was promoted from session memory
2026-08-18 with no incident recorded behind it.

### Who else uses each build

- **Sonic 4 debug:** the owner's launcher (`~/.local/bin/oracle-debug` defaults to
  `~/sonic_hacks/aeon/s4.debug.bin`, the main folder, which the landing lane rebuilds after
  every merge); the effects gates (`tools/effects_gates.py` default ROM); the nightly
  (`tools/nightly_effects_gates.sh` runs the effects gates and the preset lab witness on it).
- **Sonic 4 normal:** the configuration meant to ship (there is no release process, tag or CI
  in the repository); aurora's Build & Run defaults to `s4.bin`/`s4.lst`.
- **demo debug:** `tools/effects_gates.py` reads `demo.debug.lst` for the sonic4-versus-demo
  span comparison and the demo witness.
- **All four:** sigil's frozen goldens pin all six targets (`s4`, `s4_debug`, `demo`,
  `demo_debug`, `config_a`, `config_b`) in `crates/sigil-harness/golden/provenance.toml`,
  captured by running OUR `build.sh` in their own checkout, and their nightly builds the shipped
  shapes from our source. Neither reads our landing outputs, so none of the options changes
  them. oracle's replay tests read frozen copies (`fixtures/aeon/PIN.tsv`), not live builds;
  refreshing that pin needs both demo listings, which the build script still makes on request.
- **"The permanent proof the engine is game-agnostic" (`CLAUDE.md`):** under A the proof still
  runs before every merge (demo debug is built and tested, and demo normal is assembled by every
  Sonic 4 build). Under B it runs nightly only.

### Building, shipping, using

Every option above is about the **pre-merge check** (`tools/landing_build.sh`). None removes a
shape from `build.sh`, from the nightly job, from sigil's goldens, or from what the owner can
build and play.
