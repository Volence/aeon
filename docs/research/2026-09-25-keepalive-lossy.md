# KEEPALIVE-IS-BLIND-TO-LOSSY: survey of the wired instruments, and what is still uncovered (2026-09-25)

Booking: `docs/DEFERRED_WORK.md`, `## KEEPALIVE-IS-BLIND-TO-LOSSY`. Branch `parcel/keepalive-lossy`,
base `b2820dc3`. Measured against this branch's own `DEBUG=1 ./build.sh` output, `s4.debug.bin`.

The booking said not to treat it as a demand for a mechanism. No mechanism was added to the lane.
Five instruments were changed so that each one stops discarding something it had already measured.
Everything else found is written down below, with what it would take to fix.

## 1. Where this started: the fingerprint that was priced and not bought

The 09-19 per-arm baseline parcel (`fd7e5dc6`, record in `docs/DEFERRED_WORK.md` under
`## A BASELINE DESCRIBES AN INVOCATION ...`, its "ALTERNATIVES REJECTED" table and "WHAT IS STILL
OPEN" item 2) priced this option and rejected it: forbid non-zero `expect` and match a quoted
fingerprint of the instrument's output instead. Its reasoning: the option is strictly stronger,
because it separates two runs that exit the same way for different reasons; it is a much bigger
schema change; and it breaks on every wording change in a tool's prose.

This survey adds two things to that reasoning.

- **A fingerprint does not catch a tool that was already lossy when its baseline was recorded.**
  A fingerprint pins whatever the tool printed at that time. If the tool was discarding a
  measurement then (as `dma_straddle_exercise` did from 09-05 to 09-19), the fingerprint pins
  the discarding output. It catches changes to the output, not a baseline that was wrong from
  the start. The booking's third failure mode is therefore not closed by a fingerprint either.
- **Most of what a fingerprint would add is concentrated on the three declared-red rows.** Its
  one real advantage over an exit code is telling "red as usual" apart from "red for a new
  reason". That only matters on a row whose baseline is red: `loop_step_over_witness.py`,
  `sprite_owner_probe.py` and `waterline_art_witness.py`, all `expect = 1`. Each of those tools
  can get the same separation without the lane changing, by giving its vacuous or setup result
  an exit code its real failures do not share (section 4, 3c). That change lives in one
  tool, and it does not break when the prose is reworded.

## 2. What the lane can see, derived from its predicate

The lane's predicate is `keepalive_lane.classify` (`tools/keepalive_lane.py:217-236`):

- a timeout is COULD NOT RUN;
- a traceback is COULD NOT RUN;
- an argparse usage error with exit 2 is COULD NOT RUN;
- a non-zero exit whose output has a LINE-LEADING refusal marker (`REFUSAL_MARKERS`, `:191-198`)
  is COULD NOT RUN;
- an exit equal to `expect` is PASSED;
- anything else is FAILED.

So a tool that discards a measurement is invisible to the lane only when the discarding leaves
the exit code equal to the declared baseline. That splits LOSSY into three shapes, and the lane
does something different with each:

| shape | what the tool does | the lane on an `expect = 0` row | the lane on an `expect = 1` row |
|---|---|---|---|
| **3a lossy-to-refusal** (the `dma_straddle_exercise` shape) | measures, then exits "could not measure" | **sees it, but blames the wrong thing.** The exit changes, so the row reads FAILED, or COULD NOT RUN if the refusal line starts with a marker. It looks like a stale instrument, not a failure the tool measured. | blind if the refusal also exits 1 |
| **3b lossy-to-green** | measures a failure or fault, then exits 0 | **structurally blind** | not applicable |
| **3c lossy-by-collision** | a vacuous or setup red shares its exit code with real failures | not applicable | **structurally blind**: every new real failure exits the declared code and grades PASSED |

Across all three shapes, a baseline recorded while the tool was already lossy makes the loss
permanent: the lane's reference point is the lossy exit itself. `dma_straddle_exercise` is not
wired (`tools/keepalive_manifest.toml`, `[not_wired]`, the cost reason), so the lane never ran
its lossy period. If it had been wired, its verdict line `  VERDICT: UNMEASURABLE.` does not
start with a marker, because the line starts with `VERDICT:`. The row would have read FAILED
against `expect = 0`, or PASSED if someone had baselined it at 2.

## 3. The survey: 35 wired tools, 36 rows

"file:line" refers to base `b2820dc3` unless a row says otherwise. Every row was read against its
exit paths, and each YES was re-read at the cited lines before any action.

| tool | lossy shape? | evidence | action |
|---|---|---|---|
| spring_launch_witness.py | **YES, 3a** | `fails` was a local of `run()` (`:2265`). `main()`'s `except Unmeasurable` (`:2555-2558`) returned 2 without it. C1 raised at `pushed is None` (`:1534`) after the launch and anim findings had been appended (`:1489`, `:1507`), which breaks the file's own rule at `:1476-1485` | **FIXED** (`a492a9ff`) |
| glide_ceiling_witness.py | **YES, 3a** | legs combined only after all three returned (`:778`). `except (Unmeasurable, …)` returned 2 (`:770-773`), losing A's or B's fails | **FIXED** across legs (`5d0f3b5d`). NOT fixed inside leg C: the floor-model raise (`:713`) after the dead-stop fail (`:710`) |
| transition_window_probe.py | **YES, 3b** | `rc = e.code if isinstance(e.code, int) else 0` (`:149`): a subject's `sys.exit("msg")`, which is exit 1, became 0 | **FIXED** (`adc66d9f`). The wired subject exits with an int, so the row did not move |
| loop_step_over_witness.py `#no-assert-grounded` | **YES, 3b** | fault row recorded (`:219-222`) and printed (`:253-254`); `main` returned 0 (`:369`). `--phase-sweep` quiet path dropped fault rows (`:273-277`), return 0 (`:348`) | **FIXED** (`1def2145`) |
| loop_step_over_witness.py (default row) | **YES, 3c** | the not-landed refusal (`:196-208`) and a ROM fault at boot or placement (`check_alive`, `:135-138`) both exit 1; `expect = 1` | not fixed: moves the row's baseline (section 4, 3c) |
| dplc_coherence_witness.py | **YES, 3b** | fault or wedge rows recorded (`:718`, `:727`, `:733`); `main` returned 0 on every path (`:1258`); `report`'s return value ignored (`:1256`) | **FIXED for the fault only** (`086f8992`). The ART/SAT/VACUOUS results are still printed and not graded. **The row prints its own tilt control VACUOUS today and exits 0** (measured in this parcel's control run) |
| waterline_art_witness.py | **YES, 3c** | FAIL, an unpopulated guard (`:325-332`) and INCONCLUSIVE (`:334`) all `return 1` (`:342`); `expect = 1`. INCONCLUSIVE also overwrites a FAIL label | not fixed (section 4, 3c) |
| sprite_owner_probe.py | **YES, 3c** | THIN is appended to `failures` (`:174-179`); any entry returns 1 (`:192`); `expect = 1` | not fixed (section 4, 3c) |
| lens_residue_raster_witness.py `efx4b` (the lane's selector) | borderline, 3a | control-dead exit (`:478-481`) returns COULD NOT RUN after `check()` and the `ctl_image` fail (`:470-477`). The pre-check `:386` means `ctl_nonzero == 0` implies `ctl_image` is false, so `fails` is never empty there | **not fixed: a judgement call.** A dead control is equally consistent with an engine copy failure and with the instrument reading the wrong buffer, so "fails outranks the refusal" is not clearly right here |
| lens_residue_raster_witness.py `c3b2` / `c3b2s7` (not on the lane) | YES, 3a | `missed` checked before `hits` (`:1042` before `:1046`; `:1413` before `:1419`), so tear hits observed directly are reported as COULD NOT RUN | not fixed: off-lane, and `c3b2s7` needs a tab tag on hits so that off-section hits keep priority |
| ramp_authored_witness.py | no (exit code); prose borderline | `run_arm5`'s `ok` only moves to False (`:763-1095`). Arm 3 always prints "differ in FOUR BYTES" (`:1281`), even when nothing differed | not fixed: the exit is sound; the print is cosmetic |
| parallax_scratch_probe.py | **YES, 3b** | STEP 4's null result is printed "Reported, not excused" (`:364-365`), then PASS, return 0 (`:367-369`), while STEP 3's matching null result returns 1 (`:344-347`) | not fixed: whether mask = 0 is guaranteed to change the output from this fixture has not been measured |
| raster_frame_epoch_probe.py | **YES, 3b** | exit reads only `image_intact` (`:426`, `:430`). A wedged fixture sets `image_intact: True` (`:410`). STALLED, VARIES, zero complete frames and the control fixture are never graded | not fixed: stall and wedge are sometimes the mechanism under study; which fixture is the control is not declared |
| streaming_choke_probe.py | borderline, 3b | `frames_recorded` read (`:219`) and never checked; always returns 0 (`:424`) | not fixed: it has no pass/fail contract |
| poke_storm_sound_cost_witness.py | YES, 3b on `--poison` (not wired); borderline on the default arm | `--poison` returns 0 before `pairs_sub` or `fails` is looked at (`:355-358`). Default arm: C2 never adds to `fails` (`:321-330`), `dropped` never consulted (`:239`) | not fixed: poison is off-lane; the C2 and `dropped` semantics are unverified |
| spring_sfx_witness.py | borderline (dormant) | L1/L2 fails would be lost if C1's re-boot raised (`:438`, caught `:484-487`) | not fixed: the re-boot repeats one that just passed |
| plane_buffer_headroom_probe.py | no verdict; prose borderline | `hits == 0` still prints "PEAK 0 B" and exits 0 | not fixed: no verdict contract |
| sh_probe.py | no verdict | per-pixel `BusError` swallowed; exits 0 | not fixed |
| band_capture.py | no verdict | exits 0 whatever the coverage (an empty band crashes at `:123`) | not fixed |
| pcc_identity_probe.py | no verdict | prints `VERDICT:` with a count, always returns 0 (`:73-76`) | not fixed |
| parallax_hscroll_identity.py | no | every check feeds `bad` (`:566-646`), and `bad` decides the exit (`:648-652`) | none |
| bganim_vprobe_witness.py | no | every arm reaches `fails` (`:391`) | none |
| spring_line0_gate.py | no | `bad` covers every used index (`:218`, `:231`) | none |
| role_swap_witness.py | no (refusals exit 1, see below) | all arms reach `fails` (`:270-274`) | none |
| perspective_floor_witness.py | no | every FAIL clears `ok` | none |
| zx0r_net_boot_witness.py | no | gate reads both `resident` and `preempts` | none |
| staging_index_poison.py | no | `ok &=` over all four cases | none |
| pagecache_audit_poison.py | no | `ok &=` over all four cases | none |
| band_witness.py | no | every exit path is 1 either way | none |
| plane_buffer_peak_probe.py | no | a partial route failure is printed COULD NOT RUN by design; all routes failing exits 2 (`:341`) | none |
| left_edge_vsram_probe.py | no verdict | always 0 (`:526`), "never the verdict" per its docstring | none |
| spring_clip_ab.py | no verdict | "NOT A GATE"; 0 or 2 | none |
| fg_left_edge_probe.py / fg_left_edge_capture.py / floor_capture.py / floor_hscroll_dump.py / pcc_lab_probe.py | no verdict | capture or dump; 0 (or 2 on a witness error) | none |

A separate, non-lossy pattern turned up in five tools: `role_swap_witness`, `ramp_authored_witness`,
`parallax_scratch_probe`, `left_edge_vsram_probe` and `bganim_vprobe_witness` all refuse with
`raise SystemExit("…")`, which exits **1**, the same code as a measured failure. The lane
separates the two only when the message starts with a refusal marker. This is recorded here and
nothing was changed for it.

### What each fix is proven by

Every fix has a test file that drives the SHIPPED entry point (`main()`, or the leg function)
with only the machine faked, so the tests run in the pre-build lane and boot nothing. Each was
committed first, then shown RED under a mutation that restores the old behaviour. The mutation
was quoted with `git diff -U0` before each red run, and the file was restored from the commit
with `git checkout --`.

| commit | test file | mutation shown on disk | red |
|---|---|---|---|
| spring_launch | `tools/test_spring_launch_witness.py` | `if fails:` -> `if fails and not stopped:` (M1); `if pushed is None and fails:` -> `… and False:` (M2) | 2 failed (the two subject rows), 2 controls passed |
| glide_ceiling | `tools/test_glide_ceiling_witness.py` | `if fails:` -> `if fails and not stopped:` (G1) | 1 failed (the subject row), 2 passed |
| transition_window | `tools/test_transition_window_probe.py` | message branch `rc = 1` -> `rc = 0` (T1, the old mapping) | 2 failed (both message exits), 5 passed |
| loop_step_over | `tools/test_loop_step_over_witness.py` | `faulted = […]` -> `faulted = []` (L1); quiet path `"faulted": False` (L2) | L1: 3 failed (every argv); L2: 1 failed (exactly `--phase-sweep`) |
| dplc_coherence | `tools/test_dplc_coherence_witness.py` | `drive_verdict`'s `faults = […]` -> `[]` (D1) | 2 failed (ErrorHandler, wedge), 1 control passed |

**Baselines did not move.** The keepalive lane was run with `--only` over the five tools (6 rows)
on this branch's `s4.debug.bin`, before and after the changes. Both runs: 6 PASSED, 0 FAILED,
0 COULD NOT RUN. The before run: `dplc_coherence` exit 0, 3.3 s; `glide_ceiling` exit 0, 2.3 s;
`loop_step_over` exit 1, 1.6 s; its arm exit 0, 6.2 s; `spring_launch` exit 0, 25.3 s;
`transition_window` exit 0, 45.1 s; load average about 28. The after run: the same six exits,
in 2.0 / 1.4 / 0.9 / 3.7 / 17.0 / 32.2 s at load average about 14 to 20. `glide_ceiling` and
`spring_launch` both printed `RESULT: PASS`, and neither the `dplc_coherence` log nor the
`no-assert-grounded` log has a `FAULTED` line in either run.

## 4. The coverage statement

Read this section as a list of what is covered, and no wider. Anything not named in it is not
covered.

**(1) SILENT: covered by the keepalive, for the one declared argv of each of the 36 wired rows
(35 tools).** Not covered: the 50 `[not_wired]` tools; the unreached surface of the wired tools
(`tools/keepalive_surface.py`: 38 options gate 241 lines). A tool that "runs" but has no verdict
contract (the no-verdict rows above) is kept alive only in the sense that it produced no
traceback.

**(2) FALSE-POSITIVE: nothing covers it.** A declared-red baseline absorbs it by construction.

**(3) LOSSY: now covered in exactly these places and no others.**

- **3a lossy-to-refusal.** The tool itself now refuses to report "could not measure" when it has
  a measured failure in hand, in:
  - `spring_launch_witness` (across all eleven legs, and inside C1);
  - `glide_ceiling_witness` (across legs A, B and C; **not** inside leg C).

  Known instances still open: `lens_residue_raster_witness` efx4b (a judgement call), c3b2 and
  c3b2s7 (off-lane); `glide_ceiling` leg C in-leg; `spring_sfx_witness` (dormant);
  `spring_launch`'s L5-vs-L7 reading (L5 calls "entered the face, no hook" unmeasurable, L7
  calls the same observation a FAIL: a semantic ruling, not a code change). On an `expect = 0`
  row the lane does see a 3a loss, but reports it as a stale instrument. It cannot tell 3a
  apart from an honest refusal.
- **3b lossy-to-green.** A fault or subject exit the tool had observed is now graded, in:
  - `loop_step_over_witness` (all arms);
  - `dplc_coherence_witness` (fault and wedge only);
  - `transition_window_probe` (the subject's exit status).

  The lane is **structurally blind** to 3b and nothing else covers it. Known open instances:
  - `dplc_coherence`'s ART/SAT/VACUOUS results (printed, never graded, VACUOUS on the wired row
    today);
  - `raster_frame_epoch_probe`: wedged, stalled, zero-frame and control results;
  - `parallax_scratch_probe`: STEP 4;
  - `streaming_choke_probe`: `frames_recorded`;
  - `poke_storm_sound_cost_witness`: `--poison`, C2 and `dropped`;
  - `plane_buffer_headroom_probe`: `hits == 0`.
- **3c lossy-by-collision.** **Nothing covers it**, and it hides a real regression today, not
  only in principle. On `loop_step_over_witness` (default row), `sprite_owner_probe` and
  `waterline_art_witness`, a vacuous or setup red and a real failure share exit 1, the baseline
  is 1, and so any new real failure on those rows grades PASSED. The fix for each row: give the
  vacuous or setup outcome its own exit code, then re-measure and rebaseline through the lane,
  with `baseline_args`. That was **not done in this parcel**, for two reasons. It moves three
  declared baselines, which is a lane re-measurement rather than a tool fix. And for
  `sprite_owner_probe`, whose docstring reserves 2 for setup/spawn, it needs a ruling on what
  THIN's exit code means. It is the cheapest remaining step that is worth taking, and it buys
  most of what the rejected fingerprint would have bought (section 1).

**A baseline recorded while a tool was already lossy (any of 3a/3b/3c): nothing covers it.**
The lane's reference point is the lossy exit itself, and a fingerprint would pin the lossy
output too. Only reading the tool against its own measurements catches it. This survey was one
such reading. It does not repeat itself.

## 5. What this parcel did NOT do

- It added no lane mechanism and no manifest change; every baseline is untouched.
- It did not touch `tools/dma_straddle_exercise.py` (read as the reference pattern only), the
  clip tooling, `bganim_room.py`, or any `.emp` file.
- It opened no new booking row. Everything that would have been one is listed in section 4 and
  in the DEFERRED_WORK section, which this note narrows in place.
