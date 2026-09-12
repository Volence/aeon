# Aeon overseer handoff, 2026-09-12 eighth session (booted ~13:46Z after the owner's clear)

**Read this, then `docs/lane-status.json`, then `docs/DEFERRED_WORK.md`.** Supersedes "Next, in order" of
`docs/superpowers/2026-09-12-aeon-overseer-handoff-7.md`. Every SHA below is on aeon origin/master unless marked.
Stopped by the owner's clear rule (see "Why it stopped").

## The finding that changes the queue

**The boot scene HAS player physics.** The debug build boots the player in the fly cheat
(`GameState_OJZScroll_Init` arms `CHEAT_DEBUG_FLY` in the DEBUG shape only), and one B press hands him to
`Player_Main`'s real state machine. `GameState_OJZScroll_Update` calls `RunObjects` every tick. Controller-verified at
runtime: boot plus 400 frames, then B held for frames 400-402, and by frame 440 `Player_1` y went 256 → 426 with Sonic's
sprite drawn (it is mid-fall; the floor there is y 573, reached around frame 457, per the raster witness). **Every
booking that said "the scroll test has no physics, so X cannot be witnessed" was wrong**, and the survey plus the
booking parcel correct them. In release there is no cheat, so he is in physics from frame 1. **B must be HELD, not tapped:**
the boot+400 frame boundary falls mid-tick, and once physics is on the scene lags, so one tick can span two frames.

## Landed this session

**One landing, `land/0912-s8` in `.aeon-ls8-land`**, merges `5130ebbe` (survey), `a9e81094` + `5d938b78` (object
witnesses + path fix), `c631c011` + `329187ee` (blank priority + path fix), `12508b64` (gap sweep packet),
`dce1e8b1` + `39f96557` (raster witnesses + extent fix), `a51f8352` (booking corrections), `93c6d6d0` (baker refusals),
all on `9fe9ee91`. **First four-shape run FAILED** (`.runlogs/landing-0912-s8.log`, `finished=1`): one test in every shape,
`test_routine_extent_phased`'s next-symbol census catching `lens_residue_raster_witness.py`; no ROMs were written.
Nothing was pushed. After the fix, the **second run** (`tools/landing_build.sh .runlogs/landing-0912-s8b.log`, started
15:04:55Z detached) ended `finished=0`: every EXIT 0, pre-build lane 2553 passed / 0 failed / 2 skipped per shape,
needs_build 14 ran / 0 deferred / 0 failed. ROMs written 15:08Z..15:18Z, after the start: s4 `9cdeb9b1` / 821155,
s4.debug `9ce1c2ff` / 847533, demo `3170d31e` / 97109, demo.debug `3cf4f104` / 103501. **Byte-identical to
`9fe9ee91`, so the landing moved zero bytes**, as a tools + docs landing must. Assembler md5 `2e7c2592…` (sigil
`6884bfba`). No engine, effects or sound source moved, so neither the effects gates nor the Z80 clobbers gate applied.
`verify_level_bin` was also run by hand on the merged tree before the build: OK on every stage, including the new
`block-decode` and `editor-collision` checks (2080 authored non-air cells). The land commit and the push verification follow
this file in the log.

| what | branch | evidence |
|---|---|---|
| Physics-scene survey: how a state is chosen, which states run physics, a recipe per owed check | `survey/physics-scene-0912` | note `docs/superpowers/notes/2026-09-12-physics-scene-survey.md` |
| Object witnesses: C2a-6, Draw_Sprite multisprite parent + null mappings (natural path), C4a-2 collected half, C4a-3 full buffer (keep-all 15,224 c, remove-all 65,400 c), all WITNESSED with controls | `witness/objects-0912` | `tools/lens_residue_object_witness.py all` exit 0 on `9ce1c2ff`; note `2026-09-12-object-witnesses.md` |
| Raster/collision witnesses: EFX-4b longer→shorter re-install WITNESSED; C1b-3 with physics at origin 34 WITNESSED (12/12 cells, 6 would differ without the origin); C3b-2 NOT OBSERVED 0/3,000, structurally (section 0 has no motion, so it cannot show it) | `witness/raster-collision-0912` | `tools/lens_residue_raster_witness.py all` exit 0; note `2026-09-12-raster-collision-witnesses.md` |
| F4 measured: a blank cell's priority bit changes shadowing, 19 of 116 words visible, all in section 1 (the P1 test fixture); F4 was wrong about section 7 | `measure/blank-priority-0912` | `tools/blank_priority_probe.py`; note `2026-09-12-blank-priority-measurement.md` |
| Gap lens sweep: the Z80 comment surface (A2) and the OJZ bakers (T1), the two holes the 09-06 panels left | `review/gap-lens-sweep-0912` | packet `docs/superpowers/notes/2026-09-12-aeon-gap-lens-sweep.md` + fixtures |
| Baker refusals: T1's F1/F2/F3/F5/F6 FIXED (F4 left open: it needs the authoring call), zero bytes; `validate_editor_inputs` refuses bad editor input before the first write, and a failed re-bake restores what it wrote | `fix/baker-refusals-0912` | per-fix pre-fix-green / post-fix-red evidence in each commit body; `tools/test_baker_refusals.py`; DEFERRED row `GAP-SWEEP-0912 BAKERS F1-F6` |
| Booking corrections: DEFERRED_WORK updated in place, 7 lens-ledger rows appended (C2a-6, C3b-2, B2a-2, C4a-2, C4a-3, EFX-4b, C1b-3), s7 marked superseded in part | `docs/booking-corrections-0912` | the agent's per-item report; the ledger rows use its "latest line wins" rule |

## Next, in order

1. **The A2 comment parcel** (queue `LENS-SWEEP-COVERAGE`, now `next`): six load-bearing wrong Z80 comments (A2-1/2/3/5/6/9), the
   wrong-but-inert list, and the stale-count tail. The packet's A2 "Triage" says which are comment edits, which is a
   zero-byte guard with red-first proof (A2-6's `MEV_EXT` pin), and which need the emulator first (A2-9's drum cut at
   a song load, A2-11's stuck `FADE_BUSY`, the section.emp poke-storm). Zero bytes: prove it with `landing_build.sh`.
   **It touches Z80 sound sources, so the landing runs the Z80 clobbers gate** (`OVERSEER-REFERENCE.md`, landing lane).
2. **Still owed at runtime (controller or a headless witness):** C3b-2 in SECTION 7 (channels 2 and 3 are the two
   live moving ones); the C4a-3 and C4a-2 before/after cycle counts on the pre-merge ROMs (parents of `f64f26b3` and
   `62fb300f`); T1's F2 in-game consequence (a NULL local map); the engine-vs-Python decoder agreement.
3. **Owner cards unchanged:** `WORKING-COPY-CATCHUP` (his copy is now further behind), `SECTION-EFFECTS-VISUAL` (if he
   takes the recommendation, F4's only visible consequence goes with it), `VRAM-FOR-OBJECTS`, `CTRL-3`, `EFX-2`,
   `CHAR-10`, `SP6-MODULATION-DIVERGENCE`. None answered as of this session.
4. **Book or propose:** B2a-2's debug-only harness object (survey §4a) is an owner call; the section-0 `sh: 1` record that
   never fires on screen (an agent's reading, not a measurement).

## Found this session (read the bookings, not this summary)

- **`LENS-SWEEP-COVERAGE` was stale:** the 09-06 engine panel covered sound and engine/system. Only the two named holes
  were real, and both are now swept.
- **New tools that spell a home path fail the build lane** (`tools/test_no_baked_home_paths.py`): two helpers did it, and
  both were fixed before landing. Put it in every brief that writes a tool.
- **The worktree isolation checker refuses `PYTHONPYCACHEPREFIX=$(mktemp -d) python3 …`.** The helpers used
  `python3 -X pycache_prefix=<fresh dir>`. Brief it that way.
- **The session scratchpad is SHARED with helpers**, and one overwrote another's scratch file (second occurrence;
  handoff-7 had the first). Tell helpers to use `mktemp -d` under the scratchpad, never a fixed name.
- **zsh does not word-split an unquoted `$VAR`**, so a `$TS` holding four test paths reached pytest as ONE path (rc 4).
  Spell lists out, or use an array.
- **A fresh checkout is not a clean control for `test_bg_emit.py`**: it errors at collection without build artifacts.
- **A new tool that finds a routine's extent from "the next symbol" fails the build lane**
  (`tools/test_routine_extent_phased.py`, `TestNoSIXTHConsumerSlipsIn`). It failed this landing's first four-shape run
  (`finished=1`, one failure in each shape, no ROMs written) on `lens_residue_raster_witness.py`. The fix routes the lookup
  through `scene_spans.lst_proc_sizes`, and every witness re-ran identical. **Brief any listing-reading tool to use that
  helper.** Together with the home-path test, that is two build-lane tests a new tool meets which no helper
  anticipated. Brief a tool-writing helper to run `python3 -m pytest tools -q` on its own branch before it reports.
- **The isolation checker also refuses `-X pycache_prefix="$D"` when `$D` is computed in the same command.** Make the
  directory first, then pass its literal path. (Memory `reference_pycache_false_green_poison` now says so.)
- **The lens ledger's ids collide:** `docs/lens-findings.jsonl` already has A2-1..A2-6 from the 09-06 sweep. When the
  next session books the gap sweep's A2 findings there, give them a distinct prefix. DEFERRED_WORK's gap-sweep row
  names them in prose only.
- **Unmeasured cost, booked here and nowhere else yet:** F5's restore-on-failure trap snapshots
  `games/sonic4/data/{generated,collision}` on EVERY re-bake, including `build.sh`'s FAST auto-re-bake. Measure the
  FAST loop before and after. The owner feels that loop directly.
- **Commit message not matching its diff:** raster branch commit `4fa6c339` says the C3b-2 re-run is "recorded in the
  note", and it is not. The agent flagged this itself. The correction is in merge `39f96557`'s message; the note's
  figures still hold.
- **The owner's working copy passes the new baker refusals.** `validate_editor_inputs` was run read-only on his
  `editor/ojz/act1` and `ojz_tiles.bin` at about 14:58Z: no refusal.

## Housekeeping

After the push, removed only where the tip was an ancestor of origin/master and nothing held the tree (by PID, cmdline and cwd):
the seven helper worktrees and their feature branches (`survey/physics-scene-0912`, `witness/objects-0912`,
`witness/raster-collision-0912`, `measure/blank-priority-0912`, `fix/baker-refusals-0912`,
`docs/booking-corrections-0912`, `review/gap-lens-sweep-0912` with `.aeon-review-gaps`), plus this session's eight
`worktree-agent-*` harness branches, all at `9fe9ee91`. **The ~300 other `worktree-agent-*` branches predate this session
and were NOT touched.**
- KEEP: `.aeon-ls8-land` (landing tree), `.sigil-pin-6884bfba`, `.aeon-landing-sigil-target`.
- `.aeon-review-gaps` (the packet's worktree) and the agent worktrees are removed after the landing.
- The oracle MCP own-instance (pid 510366) holds `.aeon-ls8-land/s4.debug.bin` `9ce1c2ff` with this session's checkpoint.

## Why it stopped

Owner rule (2026-09-11T23:19:31Z / 23:20:23Z). MEASURED from this session's transcript usage records (input + cache_read
+ cache_creation): 296,881 tokens at 2026-09-12T14:17:37Z, already past the ~200k line. So no new wave went out after that point: the
A2 comment parcel was booked for the next session instead of dispatched, and the session stopped once the in-flight wave had landed.
