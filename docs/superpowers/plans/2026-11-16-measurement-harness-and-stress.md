---
kind: plan
status: awaiting-owner
description: "Empyrean v2 step 0 tasks B1-B4, C1-C4 and E1: pinned Oracle with provenance, tick-keyed closed-loop legs, per-DMA VBlank-end probe, the correction rule with BlastEm as second witness, object-heavy / sidekick / streaming stress shapes, and the v1 behaviour reference."
---
# Measurement Harness, Stress Content and v1 Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every engine number from here on comes from a pinned emulator, carries its provenance, and covers 8 fixed legs in both shapes (release and DEBUG). A missing result reads DID NOT RUN. A v1 behaviour reference is recorded that later work can diff against.

**Architecture:** The 2026-09-25 perf-survey harness (`docs/research/2026-09-25-perf-survey/leg_probe.py`, `run_survey.sh`) is a research instrument and stays where it is, frozen. Its replacement goes in `tools/` as small single-purpose modules. They sit on `tools/aether_instance.py`, which spawns a private headless `oracle-aether` and checks the cart. Inputs are poked at the `Input_Tick` seam, keyed to `Logic_Tick`, from a closed-loop policy. This is the drive the Oracle-fitness audit proved on Oracle and BlastEm (`…/audit-builds/oracle/blastem/drive_*.py`). The stress content is new off-canonical build shapes in the S2CLIP pattern: a throwaway in-place data re-bake under an EXIT trap, a distinct artifact name, release and DEBUG, no sigil edit, and canonical bytes identical by construction. The streaming act is the existing S2CLIP shape.

**Tech Stack:** Python 3 (pytest, asyncio, the Aether client from `empyrean/clients/python`), `oracle-aether` (Rust, release build), BlastEm 0.6.2 over its GDB-RSP stub under `xvfb-run`, `.emp` + `build.sh` (sigil) for the stress shapes.

**Spec:** `empyrean/docs/v2/Empyrean v2 architecture.md` (step 0 row, Continuity and second-witness rules); task notes `empyrean/docs/v2/tasks/{B1..B4,C1..C4,E1}*.md`. Evidence the plan argues from: `oracle/docs/audits/Oracle fitness.md` (minimum fixes 1-3 and 5, findings 1-5, plan items 1-3, 5, 6), `aeon/docs/audits/Audit process review.md` (change 1), `aeon/docs/audits/frame-architecture/2-measurements.md` (the leg table), `aeon/docs/audits/AUDIT_TEMPLATE.md:70-71` (the fixed legs).

**Branches:** `feat/v2-step0-harness` (aeon: Tasks 1-6 and 11), `feat/v2-step0-stress` (aeon: Tasks 7-10). Both branch off master and both use a worktree. **No oracle branch:** B1 builds an existing oracle commit and changes no oracle source.

**Independence:** Task 1 and Task 7 (C1) need nothing and can start on day 1 in parallel. Tasks 3 and 4 need only Task 2's `InputLog` and `TickState` types. Task 3's module half can be written alongside Task 2, and its integration step comes after. Task 5 (E1) needs Tasks 1 and 2 and must record **before Tasks 8-10 merge** (continuity rule). Tasks 8, 9 and 10 are independent of each other once Task 7's note exists. Task 11 needs everything.

## Global Constraints

- **Continuity:** v1 master stays green and is the behaviour reference. The canonical `s4.bin` / `s4.debug.bin` bytes must not change on either branch. Check this with `crc32` against a master build in every task that touches `build.sh`, `games/` or generated data.
- **No `mcp__oracle__*` tools, ever.** Headless harness scripts that start their own private `oracle-aether` through `tools/aether_instance.py` ARE sanctioned. Run them; do not skip them.
- **Pinned emulator only:** every result comes from the binary named in `tools/oracle_pin.toml`. `aether_instance.SERVER`'s default (`oracle/target/release/oracle-aether`) does not exist on this machine (Oracle fitness finding 1). Always pass `binary=`.
- **Provenance in every result file:** aeon commit plus dirty flag; oracle `serverBuild` (id, source, dirty); ROM name, crc32 and size; listing `DIGEST-SHAPE` and `DIGEST-ASSEMBLER revision`. A writer with any of these missing refuses to write.
- **A missing result is DID NOT RUN, never 0 or green.** A leg that ran but never met its coverage condition is DID NOT COVER. A leg whose progress stalled is STUCK. "Couldn't measure" is never a number.
- **Labels:** MEASURED / ESTIMATED / PUBLISHED on every figure in a doc or summary.
- **Frame constant:** 128,006 cycles (262 × 3,420 ÷ 7 = 128,005.7; measured mean 127,983-128,033). `FRAME_CYC = 127840` must not be copied forward.
- **Any gate or check added (invariant 8 of `dispatching-empyrean-agents`), all five:** (a) red-first, SHOWING the mutation on disk: quote the mutated line back, or `git diff --stat` naming the file; (b) commit the check first, then restore the mutation from that commit, on a tree whose `git status --porcelain` shows only the mutated file, never with `git checkout --` on other dirt; (c) actually red: applied and still green means a runner defect, to be fixed before the gate is claimed; (d) wired into a named runner, with expectations derived from source or constants, and loud on unmeasurable; (e) if the proof method changes, redo the earlier proofs and say so.
- **Runners:** pure tests run in `pytest tools -m "not needs_build"` (the pre-build lane of `tools/landing_build.sh`). Emulator-backed checks are `@pytest.mark.needs_build(...)` tests in the post-sigil `needs_build_lane.py` lane of `tools/landing_build.sh`.
- **Long runs:** run in the foreground with an explicit `timeout` of 600 s or less, one shape or leg chunk per invocation. Never background a run and wait on a notification. Completeness is proven by the survey manifest's leg count, never by a clean log.
- **Commits:** `git add` with exact paths only. Run `git branch --show-current` before every commit, because parallel sessions share the tree.
- **PAL is out of scope:** Oracle has no PAL mode (fitness finding 8). BlastEm `-r E` can boot PAL; that is listed as an option and not built here.
- **BlastEm is a black box:** use `oracle/tools/blastem-differential/rsp.py` over the RSP stub and never open its source (`blastem-differential/README.md:8-10`).

## Review Focus

1. **A stale or mismatched artifact.** A fresh `.bin` with an old `.lst`, a dirty aeon tree, or a pinned binary rebuilt at the same path must be refused or marked, never measured silently. Tested in Task 1: `test_refuses_stale_pair`, `test_refuses_binary_sha_mismatch`, `test_records_dirty_tree`.
2. **A leg that "finishes" by bouncing.** A leg that hits the tick cap while the camera moves every tick (the x ≈ 1046 loop) must read STUCK. Tested in Task 2: `test_loop_bounce_is_stuck_although_camera_moves`.
3. **Lag frames have no tick.** No input is applied on a lag frame, and lag is counted as `dFrame_Counter − dLogic_Tick`, never per row. Tested in Task 2: `test_lag_counted_from_frame_counter_delta`.
4. **A VBlank with no DMA versus a probe that cannot see.** "No DMA this VBlank" and "trigger sites unresolved or line calibration off" are different results, and the second is loud. Tested in Task 3: `test_no_sites_is_unmeasurable`, `test_entry_line_mismatch_is_unmeasurable`.
5. **A DEBUG leg that never leaves free flight.** If it stays in flight, every physics number is a flight number. Tested in Task 2: `test_debug_free_flight_not_left_refuses`.

---

### Task 1 (B1): Pinned Oracle build + provenance

**Files:**
- Create: `tools/oracle_pin.toml`, `tools/leg_provenance.py`, `tools/test_leg_provenance.py`
- Reads: `tools/aether_instance.py` (`AetherInstance(binary=…)`, `.handshake`), `tools/artifact_provenance.py` (`read_digest`, `check_pair`)
- Outside the repo: `<suite>/.oracle-bin-archive/<sha8>/oracle-aether` plus `BUILD_INFO.json` (the archive pattern already holds `549dc4f/`)

**Interfaces:**
- Produces:
  - `OraclePin(commit: str, binary: Path, sha256: str)`; `load_pin(path: Path = TOOLS / "oracle_pin.toml") -> OraclePin`
  - `verify_pin(pin: OraclePin, handshake: dict) -> None`, which raises `PinMismatch`
  - `rom_provenance(rom: Path, lst: Path) -> dict` with keys `rom, crc32, size, game, debug, target, extra_entries, sigil_revision, tree`
  - `aeon_provenance(root: Path) -> dict` with keys `commit, dirty, branch`
  - `provenance(pin, handshake, rom, lst) -> dict` with keys `oracle{commit, server_build_id, source, dirty, sha256}, aeon{…}, rom{…}, harness{tool_sha256}`
  - `require_provenance(result: dict) -> None`, which raises `MissingProvenance`
  - `spawn_pinned(rom, lst) -> AetherInstance`, the only spawn the harness uses

- [ ] **Step 1: Build the pin, outside every repo tree.** `git clone --local <suite>/oracle <scratch>/oracle-pin && git -C <scratch>/oracle-pin checkout --detach <oracle main HEAD>`, then `CARGO_TARGET_DIR=<scratch>/oracle-pin-target cargo build --release -p oracle-aether` with timeout 600 s. The clone is a real git checkout, so `build.rs` stamps `serverBuild.source = "vcs"` and `dirty = false`. Copy the binary to `<suite>/.oracle-bin-archive/<sha8>/` and write `BUILD_INFO.json` (commit, `rustc -V`, profile, UTC date, sha256). Record `tools/oracle_pin.toml`: `commit = "<40 hex>"`, `binary = ".oracle-bin-archive/<sha8>/oracle-aether"` (suite-root relative, resolved via `suite_paths.suite_path`), `sha256 = "<hex>"`. Expected: the binary starts and its handshake `serverBuild.id == "<commit>+profile=release"`.
- [ ] **Step 2: Write failing tests** in `tools/test_leg_provenance.py`:
  - `test_verify_pin_accepts_matching_handshake`: a handshake `{"implementation":"oracle-rs","serverBuild":{"id":C+"+profile=release","source":"vcs","dirty":False}}` passes.
  - `test_verify_pin_refuses_other_commit`, `test_verify_pin_refuses_dirty`, `test_verify_pin_refuses_declared_source`: each raises `PinMismatch` and names the field.
  - `test_refuses_binary_sha_mismatch`: a tmp binary whose sha256 is not the pin's raises `PinMismatch` before any spawn.
  - `test_rom_provenance_reads_digest_shape`: on a synthetic `.lst` with `DIGEST-SHAPE target=sonic4 game=sonic4 debug=1 extra-entries=none`, returns `debug == 1` and the revision.
  - `test_refuses_stale_pair`: a listing whose `DIGEST-ROM crc` differs from the `.bin` raises (it delegates to `artifact_provenance.check_pair`).
  - `test_records_dirty_tree`: in a tmp git repo with an untracked edit, `aeon_provenance(...)["dirty"] is True`.
  - `test_require_provenance_refuses_each_missing_key`, parametrised over the four top-level keys.
- [ ] **Step 3: Run** `pytest tools/test_leg_provenance.py -v`. Expected: FAIL (module missing).
- [ ] **Step 4: Implement `tools/leg_provenance.py`.** `spawn_pinned` calls `load_pin`, checks sha256, constructs `AetherInstance(rom, lst, binary=pin.binary)`, starts it, then runs `verify_pin(pin, inst.handshake)` and reaps on failure.
- [ ] **Step 5: Run the tests.** Expected: PASS.
- [ ] **Step 6: Invariant 8 proof (gate: pin refusal).** Commit. Mutate one hex digit of `commit` in `tools/oracle_pin.toml`. Show `git diff --stat` naming the file and quote the mutated line. Run `python3 -c "import leg_provenance as p; p.spawn_pinned('s4.bin','s4.lst')"` from `tools/`. Expected: RED, `PinMismatch` naming `serverBuild.id`. Restore from the commit with only that file dirty. Runner: `test_verify_pin_refuses_other_commit` in the pre-build pytest lane.
- [ ] **Step 7: Commit** `tools/oracle_pin.toml tools/leg_provenance.py tools/test_leg_provenance.py`, message `feat(harness): pinned oracle build + provenance in every result (v2 B1)`.

### Task 2 (B2): Tick-keyed closed-loop leg driver

**Files:**
- Create: `tools/leg_drive.py` (pure policies, stuck detector, field resolution, async drive loop), `tools/leg_run.py` (CLI: one leg, one shape, one phase, one JSON result), `tools/test_leg_drive.py`
- Reads: `engine/system/replay.emp:117-160` (the `Input_Tick` seam), `engine/ram.emp:346-376,1090` (`Frame_Counter`, `Logic_Tick`, `Ctrl_1_Held`, `Ctrl_1_Press`, `Camera_X_Max`), `engine/objects/sst.emp` (`name: Type @ $NN` field offsets), `games/sonic4/player/player_common.emp:95` (`ground_speed`)

**Interfaces:**
- Consumes: `spawn_pinned`, `provenance`, `require_provenance` (Task 1).
- Produces:
  - `TickState(tick: int, frame_counter: int, px: int, py: int, xvel: int, yvel: int, gspeed: int, airborne: bool, cx: int, cy: int, cx_max: int)`
  - `InputLog = {"t0": int, "held": list[int]}`, one held byte per tick from `t0`. This is also E1's replay format.
  - `Policy` protocol with `held(s: TickState) -> int`, and `POLICIES: dict[str, Callable[[Buttons], Policy]]` with keys `idle, run, topspeed, diagfall, spindash`
  - `Buttons(right, left, down, up, a, b, c)`, resolved from the listing's `BUTTON_*` equates
  - `ProgressStuck(window_ticks=300, min_progress_px=32)` with `.observe(s) -> bool`
  - `async drive_leg(client, syms, policy, t0: int, cap_ticks: int, on_tick=None) -> LegTrace(rows, input_log, status ∈ {"FINISHED","STUCK","CAP"}, lag_frames: int)`
  - `PHASE_OFFSETS = (0, 7, 19)` (ticks added to `T0 = 300`)
  - `leg_run.py --rom R --lst L --leg NAME --phase {0,1,2} --out DIR [--profile] [--dma-probe] [--cap N]` writes `DIR/<rom-stem>_<leg>_p<phase>.json` with keys `provenance, leg, phase, status, coverage{rule, got, need, met}, lag{frames, ticks}, rows, input_log, profile, dma`

**The drive (decisions the implementer cannot make alone):**
- Set one breakpoint at `Input_Tick`. On each hit: read the state, compute `held = policy.held(s)` and `press = held & ~prev`, then write `Ctrl_1_Held`/`Ctrl_1_Press` by symbol (never by literal address; the scratch drivers' `0xff8028` is stale by construction), and continue. Ticks are the only index. A lag frame produces no hit, so no input is applied and the next row's `dFrame_Counter` is 2.
- **Closed-loop rules:**
  - `run`: hold right; press C only when on ground and `|xvel| < $80` for 8 consecutive ticks (blocked), never on a period.
  - `spindash`: when on ground and `|gspeed| < PHYS_TOP_SPEED/2`, release right, hold down, tap C 4 times (2 ticks on, 4 off), release down, hold right.
  - `topspeed`: the run rule, plus a spindash when on ground and `|gspeed| < $200` for 30 ticks.
  - `diagfall`: the spindash rule, plus hold down while airborne.
  - `idle`: 0.
- **Stuck:** progress is the maximum `px` reached. The leg is STUCK when that maximum has not grown by `min_progress_px` within `window_ticks`. Camera motion is ignored, because it moves every tick inside a loop (fitness finding 2).
- **FINISHED** when `cx >= cx_max` (`Camera_X_Max`). **CAP** otherwise.
- **Coverage rules:** each takes its threshold from a listing equate.
  - `idle`: 600 ticks.
  - `run`: FINISHED.
  - `topspeed`: at least 60 ticks with `|gspeed| >= PHYS_TOP_SPEED` (equate, `$600`).
  - `diagfall`: at least 30 ticks with the camera moving on both axes and `yvel > 0`.
  - `spindash`: FINISHED and at least 1 spindash release.
  - The `objheavy`, `sidekick` and `stream` rules come from Tasks 8-10.
- **DEBUG shape:** after `t0`, if `py` is unchanged over 8 ticks, press B once. If `py` is still frozen 8 ticks later, refuse: `status = "FAILED"`, reason `free flight not left`.
- **Lag** over the leg is `Σ dFrame_Counter − Σ dLogic_Tick`. DEBUG also records the `Lag_Frame_Count` delta as a second witness.
- The profiler is armed over the drive window (`set_profiler {enabled, callers}`) exactly as `leg_probe.py:121-122,184-196` does, with its identity-remainder check. A non-zero remainder is recorded, never dropped.

- [ ] **Step 1: Write failing tests** in `tools/test_leg_drive.py`, all pure, using synthetic `TickState` series:
  - `test_loop_bounce_is_stuck_although_camera_moves`: `px` oscillates 1040-1075 for 400 ticks while `cx` changes every tick. `observe` is True by tick 300.
  - `test_steady_progress_is_not_stuck`: `px += 2` per tick for 1000 ticks. Never stuck.
  - `test_run_policy_jumps_only_when_blocked`: no C for 100 ticks at `xvel=$300` on ground; C on the 8th tick at `xvel=0`.
  - `test_spindash_sequence_shape`: the held bytes over the 30-tick sequence equal the rule above.
  - `test_press_is_edge_of_held`: held `[R, R|C, R|C, R]` gives press `[R, C, 0, 0]`.
  - `test_lag_counted_from_frame_counter_delta`: rows with `dFrame_Counter` `[1,2,1,3]` over 4 ticks give `lag_frames == 3`.
  - `test_debug_free_flight_not_left_refuses`: a frozen `py` after the B press gives FAILED.
  - `test_sst_offsets_parsed_from_source`: parsing `engine/objects/sst.emp` gives `x_pos == 0x02`, `x_vel == 0x0A`, `y_vel == 0x0C`, `status == 0x1E` (the values in the file's own `@ $NN` annotations).
  - `test_finished_at_camera_max`
- [ ] **Step 2: Run** `pytest tools/test_leg_drive.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `tools/leg_drive.py` and `tools/leg_run.py`.** Read the player through `Camera_Target` exactly as `lag_flythrough_probe.snap` does, with offsets from the source parse. `leg_run.py` calls `require_provenance` before writing.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Real-run check of the x ≈ 1046 stall.** Build master's canonical shapes in the worktree (`./build.sh`; `DEBUG=1 ./build.sh`). Run `python3 tools/leg_run.py --rom s4.bin --lst s4.lst --leg run --phase P --out <scratch>/b2` for P = 0, 1, 2, then the same on `s4.debug.bin`. Expected: 6 of 6 FINISHED at `cx == cx_max` (5824 at the time of the audit). Record per-phase lag frames as a range. Any STUCK is reported with its `(px, py)` and is not retried with a tuned rule without saying so.
- [ ] **Step 6: Invariant 8 proof (gate: stuck detector).** Commit. Mutate `ProgressStuck.observe` to the old rule (camera unchanged for 60 ticks) and quote the line from disk. Run `pytest tools/test_leg_drive.py::test_loop_bounce_is_stuck_although_camera_moves`. Expected: RED. Restore from the commit. Runner: the pre-build pytest lane.
- [ ] **Step 7: Commit** `tools/leg_drive.py tools/leg_run.py tools/test_leg_drive.py`, message `feat(harness): tick-keyed closed-loop legs with progress-based stuck check (v2 B2)`.

### Task 3 (B3): Per-DMA VBlank-end probe

**Files:**
- Create: `tools/vblank_dma_probe.py`, `tools/test_vblank_dma_probe.py`, `tools/test_leg_harness_smoke.py` (needs_build)
- Modify: `tools/leg_run.py` (the `--dma-probe` path)
- Reads: `engine/system/dma_queue.emp:303-321,359-474` (the drain groups: `move.w (a1)+,(a5)` and `move.w (a0)+,(a5)` are the command words that start each DMA), `engine/system/vblank.emp:206,270,282,456`

**Interfaces:**
- Consumes: `drive_leg(on_tick=…)` (Task 2); `DMA_END_LIMIT_LINE` and `MCLK_PER_LINE` from `leg_correction` (Task 4). Until Task 4 lands, define them in a stub `leg_correction.py` with the same names and values, and have Task 4 own the file.
- Produces:
  - `dma_trigger_sites(lst_text: str, symbols: dict) -> list[int]`, which raises `NoTriggerSites`
  - `DmaEvent(tick, vblank, site, start_line, start_off, end_line, end_off)`
  - `line_of(mclk: int) -> tuple[int, int]` (line, mclk into the line; frame of 896,040 mclk)
  - `class DmaProbe` with `async arm(client)` and `async on_break(client, pc, reply) -> bool`
  - `vblank_end(events) -> DmaEvent | None` and `overruns(events) -> list[DmaEvent]`
  - In the result JSON, `dma = {sites, events, worst_end{line, off, tick}, overruns, unmeasurable: str | None}`

**Method (harness version, per fitness plan item 3).** Sites come from the listing: every instruction that writes the last command word to `(a5)` inside `Process_DMA_Critical` and `Drain_Budgeted_Queue`, the two drain bodies, bounded by their symbols. Set a breakpoint on each site. On a hit, `start = reply.mclk`; then `emulator/step {count:1}` and `end = reply.mclk`. Oracle charges the DMA stall to the triggering instruction, so the step's return time is the DMA end on Oracle's model. Calibration: a breakpoint at `VBlank_Handler` must compute line 224 on every frame; any other value makes the probe unmeasurable. The check fails when an end is after `DMA_END_LIMIT_LINE` (260) + 0 mclk.

- [ ] **Step 1: Write failing tests** (pure):
  - `test_sites_found_in_both_drain_bodies`: on the real `s4.debug.lst`, sites is non-empty, every site lies inside one of the two procs' address ranges, and the count is at least the number of drain groups the listing shows for `Process_DMA_Critical`. Mark this test `needs_build("s4.debug.lst")`.
  - `test_no_sites_is_unmeasurable`: a listing with the drain lines removed raises `NoTriggerSites`.
  - `test_line_of`: `line_of(257*3420+2097) == (257, 2097)`. That is the reviewer's worst DEBUG frame (fitness finding 3).
  - `test_entry_line_mismatch_is_unmeasurable`
  - `test_overrun_flagged_past_limit`: `end = (260, 1)` is flagged and `(260, 0)` is not.
  - `test_vblank_end_is_last_event_not_rte`
- [ ] **Step 2: Write the needs_build smoke** `test_leg_harness_smoke.py::test_idle_legs_with_dma_probe`, marked `needs_build("s4.bin","s4.lst","s4.debug.bin","s4.debug.lst")`. It runs the idle leg with `--cap 120 --dma-probe` on both shapes and asserts: provenance present, `dma.unmeasurable is None`, at least one event per non-lag VBlank, no overruns, VBlank entry line 224. A missing pinned binary FAILS, naming the pin path; it does not skip.
- [ ] **Step 3: Run both tests.** Expected: FAIL.
- [ ] **Step 4: Implement** `tools/vblank_dma_probe.py` and wire `--dma-probe` into `leg_run.py`.
- [ ] **Step 5: Run.** Expected: PASS. Then reproduce the audit's figure as a cross-check: diagfall leg on `s4.debug.bin`, phase 0. Report the worst last-DMA end with its tick. The audit's 257 + 2,097 came from a different drive (free-flight diagonal, tick 603), so a different value is not a failure. Report both.
- [ ] **Step 6: Invariant 8 proof (gate: DMA-end limit).** Commit. Mutate `DMA_END_LIMIT_LINE` from 260 to 250 and quote it. Run the smoke test. Expected: RED, because the first DMA starts at line 243 and its end exceeds 250 (finding 3). Restore. Second mutation: make `dma_trigger_sites` return `[]`. Expected: RED via `unmeasurable`, never green. Runner: the `needs_build` lane of `tools/landing_build.sh`. Report the smoke's wall-clock time. If it is over 30 s, move it to `tools/nightly_instrument_keepalive.sh` and say so; that move is the owner's call.
- [ ] **Step 7: Commit** the three files and `tools/leg_run.py`, message `feat(harness): per-DMA VBlank-end probe with line-260 flag (v2 B3)`.

### Task 4 (B4): Correction rule + BlastEm second witness

**Files:**
- Create: `tools/leg_correction.py`, `tools/blastem_witness.py`, `tools/test_leg_correction.py`
- Modify: `docs/audits/Hardware limits.md` (a new section "Correcting Oracle's numbers")
- Reads: `oracle/tools/blastem-differential/rsp.py` (imported through `suite_paths.require_suite_path("oracle","tools","blastem-differential")`); BlastEm at `<suite>/emulators/blastem64-0.6.2/blastem`

**BlastEm headless: yes.** `rsp.py:40-43` launches `xvfb-run -a -s "-screen 0 640x480x24" blastem ROM -D -g` with `SDL_AUDIODRIVER=dummy`, and `/usr/bin/xvfb-run` exists. The fitness audit ran 4 tick-locked BlastEm legs this way (`…/audit-builds/oracle/blastem/b_*.json`). Limits: the stub has no cycle counter, so the witness is lag-level and path-level only. `P` for pc is unsupported (`README.md`). PAL option: `blastem -r E`, not built here.

**Interfaces:**
- Produces:
  - Constants: `FRAME_CYCLES = 128006`, `MCLK_PER_LINE = 3420`, `LINES_PER_FRAME = 262`, `BLANK_DMA_LINES = 37`, `DMA_END_LIMIT_LINE = 260`, `REFRESH_FRACTION = 2/128`, `Z80_STALL_MAX_FRACTION = 0.026`, `WITNESS_MARGIN_FRACTION = 0.03`
  - `corrected_margin(margin_cycles: int, elapsed_cycles: int, sound_playing: bool) -> int`, which subtracts `elapsed × REFRESH_FRACTION`, plus `elapsed × Z80_STALL_MAX_FRACTION` when sound is playing
  - `classify(margin_cycles: int, budget_cycles: int, elapsed_cycles: int, sound_playing: bool, witness: WitnessResult | None) -> str` returning one of `"FITS"`, `"OVER"`, `"NEEDS-WITNESS"`, `"WITNESS-DISAGREES"`
  - `run_blastem(rom: Path, lst: Path, input_log: InputLog, n_ticks: int) -> list[WitnessRow(tick, frame_counter, cx, cy, px, py)]`
  - `compare(oracle_rows, blastem_rows) -> WitnessResult(path_agree_ticks, first_divergent_tick, lag_oracle, lag_blastem, extra_lag_ticks)`
  - CLI: `blastem_witness.py --rom R --lst L --result <leg_run json>` replays that result's `input_log` open-loop, keyed to tick, and writes `<result>.blastem.json`

**The rule (copy into Hardware limits.md, values verbatim from Oracle fitness):**
1. Judge VBlank work by the **last DMA's end**, not by `rte`.
2. The blank-rate window is **37 lines**, not 38; on hardware it ends at about line 261 + 0, give or take a line. Use the threshold **"no DMA ends after line 260 + 0"**, one line of safety, which needs no disputed GPL-only constant (fitness decision 2).
3. Oracle omits the 68000 refresh (2 cycles in 128, 1.56%) and Z80 bank stalls (up to about 2.6% with sound). Correct by **2-4%** of the cycles elapsed since VInt: the low end for a silent leg, the high end with sound.
4. Frame budgets on Oracle are about **2% optimistic** (band 1.5-2.5%, ESTIMATED from one BlastEm lag frame).
5. **A "fits" call with a corrected margin under 3% of its budget (about 3.8k cycles of a frame) is not a verdict on Oracle alone.** It needs BlastEm agreement on lag and path for the same tick-keyed inputs, or it is reported NEEDS-WITNESS.
6. A DMA past the blank is **not measurable** on Oracle (flat cost, finding 4). Report the flag, not a cost.

- [ ] **Step 1: Write failing tests:**
  - `test_corrected_margin_silent_uses_refresh_only`: elapsed 16,418 cycles gives a correction of 256.
  - `test_corrected_margin_with_sound_adds_z80`
  - `test_under_three_percent_needs_witness`: `margin = 3800, budget = 128006` gives NEEDS-WITNESS with no witness.
  - `test_witness_agreement_upgrades_to_fits`
  - `test_witness_extra_lag_is_disagrees`
  - `test_compare_finds_first_divergent_tick`, on synthetic rows.
  - `test_constants_match_hardware_limits_doc`: parses the new section of `docs/audits/Hardware limits.md` and checks that 37, 260, 3% and 2/128 equal the module constants, so the doc and the code cannot drift.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement both modules and write the doc section.** The doc section links Oracle fitness and states that BlastEm is a second model, not hardware.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Witness smoke.** Run `blastem_witness.py` on Task 2's release run p0 result. Expected: `path_agree_ticks` equals all ticks, or `first_divergent_tick` is reported, and both lag counts are printed. The run is limited to 600 s. If BlastEm cannot start, record **COULD NOT RUN** with the stderr tail and leave the rule's NEEDS-WITNESS path as the outcome.
- [ ] **Step 6: Invariant 8 proof (gate: classify).** Commit. Mutate `WITNESS_MARGIN_FRACTION` to `0.0` and quote it. `test_under_three_percent_needs_witness` must go RED. Restore. Runner: the pre-build pytest lane.
- [ ] **Step 7: Commit** the three files and `docs/audits/Hardware limits.md`, message `feat(harness): Oracle correction rule + BlastEm second witness (v2 B4)`.

### Task 5 (E1): v1 behaviour reference

**Files:**
- Create: `tools/v1_reference.py`, `tools/test_v1_reference.py`, `docs/benchmarks/v1-reference/MANIFEST.json`, `docs/benchmarks/v1-reference/<shape>/<leg>.inputs.json`, `docs/benchmarks/v1-reference/<shape>/<leg>.frames.jsonl.gz`

**Interfaces:**
- Consumes: `drive_leg`, `InputLog` (Task 2); `provenance` (Task 1).
- Produces:
  - `record(rom, lst, leg: str, out: Path, inputs: InputLog | None = None) -> RecordStats`. With `inputs`, the drive is open-loop replay; without, it is the closed-loop policy and the produced `InputLog` is saved as the replay.
  - Frame row: `{tick, held, fb, vdp, obj_ram, game_ram, px, py, xvel, yvel, status, cx, cy, lag_before}`.
    - `fb` is `state_hash{includeFramebuffer:true}.framebuffer` and `vdp` is `.combined`.
    - `obj_ram` is `memory_hash{symbol:"Object_RAM", len: Object_RAM_End−Object_RAM}`.
    - `game_ram` is the hash of the game RAM block bounded by its symbols.
    - The semantic fields are plain values, so a rebuilt engine with a different RAM layout can still be diffed on behaviour; the raw hashes serve same-layout regression only.
  - `diff(ref_dir: Path, run_dir: Path, fields: tuple[str, ...] = ALL) -> DiffReport({(shape, leg): (first_tick, field) | None})`
  - CLI `v1_reference.py record|replay|diff`.
- Scope: the canonical shapes `s4.bin` and `s4.debug.bin`; legs idle, run, topspeed, diagfall, spindash; phase 0. That is 10 recordings. The stress shapes are not v1 canonical and are not recorded.

- [ ] **Step 1: Write failing tests** (pure, synthetic):
  - `test_diff_identical_is_none`
  - `test_diff_reports_first_divergent_tick_and_field`: mutating `px` at tick 40 gives `(40, "px")`.
  - `test_diff_semantic_only_ignores_ram_hashes`
  - `test_diff_missing_leg_is_did_not_run`, never equal.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** `tools/v1_reference.py`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Record against master.** Build both canonical shapes from master HEAD in the worktree. The harness branch changes no ROM bytes, so check that the crc32 values equal those of a plain master build. Record the 10 legs, then **replay each from its own `inputs.json` into a second directory and `diff`**. Expected: 10 of 10 report `None` (determinism). Also run oracle's `replay_runner` on `s4.debug.bin` and put its verdict in `MANIFEST.json`. Before commit, measure the compressed size; if it is over 5 MB, stop and ask the controller where it should live.
- [ ] **Step 6: Invariant 8 proof (gate: diff).** Commit. Flip one held byte at tick 100 in `run.inputs.json`, quote it, replay and diff. Expected: RED at the first tick at or after 100 where state differs. Restore. Runner: `test_diff_reports_first_divergent_tick_and_field` in the pre-build pytest lane.
- [ ] **Step 7: Commit** the tool, its test and the `docs/benchmarks/v1-reference/` paths, message `feat(reference): v1 behaviour reference, replays + per-frame hashes, both shapes (v2 E1)`.

### Task 6: Survey runner + completeness

**Files:**
- Create: `tools/leg_survey.py`, `tools/test_leg_survey.py`

**Interfaces:**
- Consumes: `leg_run.py` (Task 2), with `--dma-probe` (Task 3); `classify` (Task 4).
- Produces:
  - `LEGS = ("idle","run","topspeed","diagfall","spindash","objheavy","sidekick","stream")` and `SHAPES = ("release","debug")`
  - `LEG_ROM: dict[tuple[str,str], str]`: canonical legs map to `s4.bin` / `s4.debug.bin`; `objheavy` maps to `s4.stressobj[.debug].bin` (Task 8); `sidekick` maps to `s4.sidekick[.debug].bin` (Task 9); `stream` maps to `s4.s2clip[.debug].bin` built with the clip pinned in Task 10
  - `LEG_POLICY`: the stress legs use `run`
  - `expected_matrix() -> list[tuple[str,str,int]]` (8 × 2 × 3 = 48)
  - `run(out_dir, only: list[str] | None)`, one `leg_run` subprocess per cell, with `rc` appended to `out_dir/manifest.jsonl`
  - `summarise(out_dir) -> Summary(rows, counts)`, each row's status one of `OK`, `STUCK`, `DID NOT COVER`, `DID NOT RUN`, `FAILED`
  - Writes `out_dir/summary.md`: per leg and shape, lag min–max over the 3 phases, worst last-DMA end, the rule-4 verdict, and `ran N of 48`
  - Exit codes: 0 when all 48 are OK; 2 when any is DID NOT RUN; 1 otherwise

- [ ] **Step 1: Write failing tests:**
  - `test_matrix_is_48`
  - `test_missing_result_is_did_not_run`: an out_dir holding 47 synthetic results gives exit 2 and names the missing cell.
  - `test_result_without_provenance_is_failed`
  - `test_stuck_and_uncovered_are_not_ok`
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** `tools/leg_survey.py`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Invariant 8 proof (gate: completeness).** Commit. Mutate `summarise` to skip absent files and quote the line. `test_missing_result_is_did_not_run` must go RED. Restore. Runner: the pre-build pytest lane.
- [ ] **Step 6: Commit** both files, message `feat(harness): 48-cell leg survey with DID NOT RUN accounting`.

### Task 7 (C1): Size the stress content (estimate + design note)

**Files:**
- Create: `docs/superpowers/notes/2026-11-16-stress-content-sizing.md` (frontmatter `kind: note`)

**Decision this plan makes, and C1 may overturn only in writing.** The stress content is **off-canonical build shapes in the S2CLIP pattern** (`build.sh:186-240`): an in-place throwaway re-bake under an EXIT trap that restores the committed tree; a distinct artifact name spelled as a standalone `ROM_NAME="…"` literal (`gate_cut_shape.py` reads them); release and DEBUG; FAST refused; unfrozen, no golden. The alternatives were weighed and rejected:
- **DEBUG-only test states**, such as the `emulator/object_spawn` mailbox or `GameState_ObjectTest`. The mailbox cells exist only in DEBUG (`oracle-aether/src/objreq.rs:11-18`), so release legs cannot run, and the charter's gate is release legs with provenance. `GameState_ObjectTest` does not run the act's camera, streaming and physics, so it does not measure the frame we ship.
- **A runtime game state or cheat bit.** It ships code in canonical `s4.bin`, which moves sigil's goldens and the E1 reference.
- **The STRESS_EVICT pattern.** It needs a sigil CLI flag (`sigil-cli/src/main.rs:197,2794`), which is a Rust edit per shape: the coupling the charter names as a v1 defect.

**What C1 measures (each a number in the note, labelled):**
- [ ] **Step 1: Object-heavy.** Capacity: `NUM_DYNAMIC = 40` (`engine/system/constants.emp:92`). Find how many placements the entity window spawns at once (`ojz_entity_gen.py`, per-section type-table limits, window span). Work out the overlay density needed to hold at least 30 live dynamic objects (¾ × `NUM_DYNAMIC`) across the run leg's path. Check that `ojz_entity_gen.py` can take an overlay file, and how `clip_rom_bake.py` regenerates `entity_data.emp`.
- [ ] **Step 2: Sidekick.** No CPU follower exists anywhere (`git log --all -- games/sonic4/player/tails_cpu.emp` is empty; character-dispatch v2 plan Task 8 never landed). The real CPU Tails is product code and needs the owner's design approval under the charter, so the stress sidekick is a **mirror-input second player**: `Player_2` is spawned 32 px behind `Player_1` and runs the same `Player_Main` on the same `Ctrl_1_*` input. That gives the cost of a second body, DPLC, collision and appendage without the AI filter. Measure:
  - whether the per-slot player globals let two `Player_Main` instances run (character-dispatch C1 claimed `Camera_Target` + per-slot globals; `Camera_Target` exists);
  - **the VRAM shortfall:** a follower body needs up to 29 tiles (the cast's peak, `vram.toml:285`) plus an 8-tile appendage window if the follower is Tails (`vram.toml:587-588` warns that a sidekick undoes the insta-shield overlay). The free runs are 3 tiles at 989 and 12 at 1492. Find which region the shape can borrow in **both** shapes (candidate: one act-pool page frame, as character-dispatch Task 5 option (a) proposed);
  - how the shape's `const STRESS_SIDEKICK` reaches code without a sigil edit (candidate: emitted by the re-bake into a regenerated module, as `OJZ_CLIP_ACT` is in `clip_act.emp`).
- [ ] **Step 3: Streaming act.** Confirm the S2CLIP shape streams. The 2026-09-25 survey's clip had 17 pool pages against `PAGE_FRAMES = 12`, was not resident, and made `PageIn_Process`/`PageCache_Prefetch` calls (`perf-survey.md:42-44`). Pick the clip id (candidates `s2_ehz_cpz`, `s2_woven`) whose run leg can FINISH and whose decode routine makes at least 1 call. Record the decode routine's exact name from the listing.
- [ ] **Step 4: Write the note.** It gives the effort estimate per shape, the risks, the mechanism chosen for each, and the coverage rule each leg will use (the thresholds named from equates). Tasks 8-10 implement what the note says. **Starting estimate, to be confirmed or replaced by C1 (ESTIMATED):** C2 1 to 1.5 days; C3 2 to 4 days, dominated by the VRAM carve and the two-instance audit; C4 half a day. Total about 4 to 6 days.
- [ ] **Step 5: Commit** the note on `feat/v2-step0-stress`, message `docs(stress): size the step-0 stress content (v2 C1)`.

### Task 8 (C2): Object-heavy shape `STRESS_OBJECTS=1`

**Files:**
- Create: `tools/stress_objects_overlay.py`, `tools/test_stress_objects_overlay.py`, `games/sonic4/data/editor/ojz/act1/stress_objects.overlay.json` (generated, committed)
- Modify: `tools/ojz_entity_gen.py` (an `--overlay PATH` input), `build.sh` (the shape block, the re-bake block and its EXIT trap, the FAST refusal, the mutual exclusions with S2CLIP and STRESS_*), and any shape list that enumerates off-canonical shapes (`tools/gate_cut_shape.py`, `tools/test_landing_lane_shapes.py`; find each with `grep -n S2CLIP tools/*.py`)

**Interfaces:**
- Consumes: Task 7's note (density, types); the run leg's `rows` (Task 2) as the path to keep clear.
- Produces:
  - `place(path: list[tuple[int,int]], act_w: int, act_h: int, n_per_screen: int, clearance_px: int = 64) -> list[dict(x, y, typeId, subtype)]` using the registered types in `games/sonic4/data/editor/objects.json`
  - Artifacts `s4.stressobj.bin/.lst` and `s4.stressobj.debug.bin/.lst`
  - Leg coverage rule: at least 60 ticks with live dynamic objects ≥ ¾ × `NUM_DYNAMIC` (equate). Live count comes from `emulator/object_list`, or from the `Dynamic_Free_Stack` depth if `object_list` is DEBUG-only (C1 says which).

- [ ] **Step 1: Failing tests:**
  - `test_no_object_within_clearance_of_path`
  - `test_count_matches_density`
  - `test_overlay_is_deterministic`: same inputs give byte-identical JSON.
- [ ] **Step 2: Run, expect FAIL. Implement. Run, expect PASS.**
- [ ] **Step 3: Shape build.** `STRESS_OBJECTS=1 ./build.sh` and `STRESS_OBJECTS=1 DEBUG=1 ./build.sh`, each succeeding. Then `git status --porcelain` shows no change under `games/sonic4/data/generated/`, and the canonical `s4.bin`/`s4.debug.bin` built afterwards match master's crc32.
- [ ] **Step 4: Leg check.** Run `leg_run.py --leg objheavy` on both shapes, phase 0. Expected: FINISHED and coverage met. Also expected, because the objects sit off the player's path: `px, py` agree with the canonical run leg tick for tick until the first touch, and that tick is reported. The cost per object (MEASURED) is the regression slope of main-loop cycles per tick against live count.
- [ ] **Step 5: Commit** exact paths, message `feat(stress): object-heavy STRESS_OBJECTS shape, release + DEBUG (v2 C2)`.

### Task 9 (C3): Sidekick shape `STRESS_SIDEKICK=1`

**Files:** (as Task 7's note fixes them; default:)
- Create: `games/sonic4/test/stress_sidekick.emp` (the `Player_2` spawn and per-tick `Player_Main` call, all inside `if STRESS_SIDEKICK == 1 { }` so canonical shapes emit zero bytes)
- Modify: `games/sonic4/test/ojz_scroll_test.emp` (one gated call site), `games/sonic4/map.toml` (order entry), the regenerated module that carries `STRESS_SIDEKICK`, `games/sonic4/vram.toml` (the borrowed region, gated per the note), `build.sh` (the shape block, as in Task 8)

**Interfaces:**
- Consumes: Task 7's note (VRAM borrow, switch mechanism).
- Produces: `s4.sidekick.bin/.lst` and `s4.sidekick.debug.bin/.lst`. Leg coverage rule: `Player_2` live (its code word non-zero) on at least 90% of drive ticks, with its DPLC transfers present in the DMA events (the Task 3 probe sees them as extra Important entries).

- [ ] **Step 1: Failing check.** A `needs_build("s4.sidekick.debug.bin","s4.sidekick.debug.lst")` test `test_sidekick_slot_live`: boot, run 300 ticks, and assert `Player_2`'s first word is non-zero and its `x_pos` is within 256 px of `Player_1`. Run it against a canonical ROM copied to the sidekick name. Expected: FAIL.
- [ ] **Step 2: Implement** per the note. Canonical crc32 values are unchanged (checked as in Task 8 Step 3).
- [ ] **Step 3: Run the test.** Expected: PASS on both shapes. Then `leg_run.py --leg sidekick`, phase 0, both shapes. Expected: FINISHED and coverage met; a STUCK sidekick (`Player_2` left behind) is reported, not tuned away.
- [ ] **Step 4: Invariant 8 proof (gate: `test_sidekick_slot_live`).** Commit. Mutate the gated spawn call into a no-op, quote it from disk, rebuild the shape and run the test. Expected: RED. Restore from the commit and rebuild. Runner: the `needs_build` lane.
- [ ] **Step 5: Commit** exact paths, message `feat(stress): mirror-input sidekick STRESS_SIDEKICK shape (v2 C3)`.

### Task 10 (C4): Streaming act

**Files:**
- Modify: `tools/leg_survey.py` (`STREAM_CLIP = "<id from C1>"`, and the stream leg's coverage rule)

**Interfaces:**
- Produces: stream leg coverage rule. The decode routine named in C1 makes at least 1 call in the profile, and the page-cache eviction count is at least 1 (read from the RAM counter C1 names, else from the profiler's call count of the eviction routine).

- [ ] **Step 1: Failing test** `test_stream_leg_requires_decode_calls`: a synthetic result with 0 decode calls gives DID NOT COVER.
- [ ] **Step 2: Implement the rule. Run the test.** Expected: PASS.
- [ ] **Step 3: Real check.** `S2CLIP=<id> ./build.sh` and `DEBUG=1 S2CLIP=<id> ./build.sh`, then `leg_run.py --leg stream` on both shapes. Expected: coverage met, with the decode count reported (MEASURED). If the clip's run leg is STUCK on both rules, report it and try C1's second candidate; never tune the policy for one act.
- [ ] **Step 4: Commit** `tools/leg_survey.py tools/test_leg_survey.py`, message `feat(stress): pin the streaming act for the stream leg (v2 C4)`.

### Task 11: Full survey with provenance

**Files:**
- Create: `docs/benchmarks/legs/<YYYY-MM-DD>-<aeon sha8>/` (`manifest.jsonl`, 48 result JSONs gzipped, `*.blastem.json` where rule 5 asks, `summary.md`)

- [ ] **Step 1: Build all six artifacts** from one commit: canonical release and DEBUG, `STRESS_OBJECTS`, `STRESS_SIDEKICK`, and S2CLIP `<id>`, the last three each in release and DEBUG. Record their crc32 values.
- [ ] **Step 2: Run** `python3 tools/leg_survey.py run --out <dir> --only <leg>`, one leg per invocation (6 cells), in the foreground with timeout 600 s, for all 8 legs.
- [ ] **Step 3: For every verdict the summary marks NEEDS-WITNESS**, run `blastem_witness.py` on that result. Re-run `summarise`.
- [ ] **Step 4: Completeness.** `python3 tools/leg_survey.py summarise <dir>` prints `ran 48 of 48` and exits 0. Any other count is reported as it stands, cell by cell, with DID NOT RUN / STUCK / DID NOT COVER. Release must show 8 of 8 legs.
- [ ] **Step 5: Commit** the result directory, message `measure: step-0 leg survey, 48 cells with provenance`.

---

## Notes for the controller

- **Leg count versus the charter.** The step-0 gate says "release runs 7 of 7 legs"; the template (`AUDIT_TEMPLATE.md:70-71`) lists 9 legs, one of them PAL. This plan runs the 8 non-PAL legs per shape, which covers the 7. The owner should pick the wording.
- **Hand-offs outside aeon:** after Tasks 1-11 land, set the empyrean task notes (`B1…E1`) to status and branch. That is empyrean's edit, not this plan's.
- **Not in scope, from Oracle fitness:** core fixes (worst single call per routine, per-line DMA billing, refresh, PAL), the sound leg (N1), and the PAL boot leg (BlastEm `-r E`).

## Self-review

- **Spec coverage:**
  - B1 is Task 1. B2 is Task 2. B3 is Task 3. B4 is Task 4: the rule, BlastEm headless, and the PAL option noted. C1 is Task 7. C2, C3 and C4 are Tasks 8, 9 and 10. E1 is Task 5.
  - The 8 legs × 2 shapes, proven complete by count, are Tasks 6 and 11.
  - The fitness harness fixes are covered: stable path and build id (Task 1); closed loop, three phases and `FRAME_CYC` (Task 2); the line-260 flag (Task 3); the correction text (Task 4).
  - Invariant 8 appears in each task that adds a check: Tasks 1-6 and 9. Task 8 adds no gate, only a generator with unit tests. Task 10's rule is tested in Step 1.
- **Type consistency:** `InputLog`, `TickState`, `DMA_END_LIMIT_LINE` and the `leg_run` result keys are used with the same names in Tasks 2-6 and 11.
- **Blocked:** nothing hard. The C3 VRAM borrow (about 29-37 tiles needed against 15 free) is the one open design question; Task 7 resolves it, and it may need the owner if no page frame can be spared in both shapes.
