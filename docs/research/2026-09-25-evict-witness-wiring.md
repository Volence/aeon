# EVICT-WITNESS-WIRING: the nightly now grades the STRESS_EVICT artifact (2026-09-25)

Branch `parcel/evict-witness-wiring`, base `40c891f5`. The row is closed in `docs/DEFERRED_WORK.md` under `EVICT-WITNESS-WIRING`.

## What the witness measures

`tools/evict_witness.py` boots the `STRESS_EVICT=1 ./build.sh` ROM (`s4.stress.bin` / `s4.stress.lst`) in a headless `oracle-aether` that it spawns itself. It stops at `GameState_OJZScroll_Init` and watches `Page_Table` while the OJZ act loads.

The fixture clamps the residency cache to fewer frames than the act's art pool has pages, so the load itself has to evict. The verdict is a pigeonhole: more distinct pages are seen resident than the clamp has frames. Both sides of that comparison are derived on every run:

- the pool page count comes from the act descriptor on the running machine;
- the clamp comes from the emitted `cmpi.w #imm,d6` in `Level_LoadArt`.

Phase 2 is a single 90-frame scroll burst. It reports the known AllocFrame famine as open debt and does not fail the witness.

Exit codes:

- 0: PASS.
- 1: FAIL.
- 2: UNMEASURABLE. The ROM cannot force an eviction, or the cart the server loaded is not the file on disk.

## Verdict on today's stress build

`STRESS_EVICT=1 ./build.sh` exited 0 after 440 s (load average 27 to 35). `s4.stress.bin` is crc32 `cd308561`, 848,075 bytes.

**The witness as it stood could not be wired.** I ran it 16 times back to back on that ROM. It exited 1 in 11 of the 16 runs, reporting "no eviction proven" with distinct pages `[0,1,3..9]` = 9; page 2 was never seen. Runs 1 to 3, 10 and 16 passed.

Stepping the machine one frame at a time from the init breakpoint shows why:

- pages 0 to 8 stream in every 2 frames from +35;
- page 2 is resident for exactly 12 frames, +39 to +50;
- at +51 page 2 is evicted to admit page 8;
- the table is settled by +52.

The old sampler let the machine run free and read the table every 50 ms of wall time. Whether a 12-frame window fell between two reads was therefore up to the host. I did not measure how the miss rate depends on host speed.

**The repair:** Phase 1 now keeps the machine stopped and advances it with `run_frames 1` for each sample. The budget is 900 frames, about 17 times the measured settle point, and takes about 4 s of wall time. After the repair the witness passed 12 of 12 runs, all identical:

```
PAGE_FRAMES_CLAMP(emitted) = 9, read off `cmpi.w #$0009,d6` at $0093B6 in Level_LoadArt
  !! DISAGREEMENT: the listing publishes PAGE_FRAMES_CLAMP = 12, the ROM compares against 9. ...
act descriptor $018A38 (frame +34): act_art_pool_pages=10 vs PAGE_FRAMES_CLAMP=9
PHASE 1: eviction proven — 10 distinct pages > 9 frames; directly observed evictions: [2]; first at frame +51: evicted [2] admitting [8] [867 per-frame samples over 900 frames]
PHASE 2: known AllocFrame famine on scroll burst (OPEN DEBT ...); witness PASS stands on Phase 1
PASS (with known famine)
```

On canonical `s4.debug.bin` (crc32 `62238a15`) the repaired witness still exits 2, UNMEASURABLE: the 10-page pool fits the 12-frame clamp.

Red-first evidence for the repair. Each mutation was shown on disk before its run, then restored with `git checkout HEAD --` and re-run green.

| | mutation | result |
|---|---|---|
| pre | the committed wall-clock sampler | exit 1 in 11 of 16 runs |
| M1 | `run_frames 13` | **SURVIVED, exit 0.** 13 x 3 = 39 lands inside +39..+50, so this stride sees page 2 by phase. The mutation was a poor choice; the check is not weak. |
| M1b | `run_frames 17` (samples at +34 and +51, none inside the window) | **exit 1**, with the same signature as the flaky failure: `[0, 1, 3, 4, 5, 6, 7, 8, 9] (= 9)` |

Phase 2 hit the known famine on every run today, both before and after the repair. It does not change the exit code.

## What the nightly now does

In `tools/nightly_effects_gates.sh`, the new leg comes straight after the `STRESS_EVICT=1 ./build.sh` leg:

- **Only after a green build.** The witness runs only when the build exited 0. On a failed build the leg writes `evict_witness NOT RUN ...` into its log, so that log is never left over from a previous night, and sets `rc_ew=1`. The build leg's FAILED note already carries the verdict for that night.
- **Its own log.** The command is spelled out literally: `python3 tools/evict_witness.py --rom s4.stress.bin --lst s4.stress.lst`. Output goes to `$STATE/stress_evict_witness.log`, with begin and end stamps that carry `uptime`.
- **Exit mapping.** The exit code is mapped the same way as the gates and the lab witness, not like a build leg. The witness's own exit 2 means UNMEASURABLE, and "could not ask" is not "the answer is no":
  - 0 writes an OK line.
  - 1 writes a `STRESS_EVICT EVICTION WITNESS FAILED` note.
  - Any other code is COULD NOT RUN (2).
- **Worst-wins.** `rc_ew` is part of the same worst-wins fold as the other legs.
- **Tree check unaffected.** The witness writes nothing into the tree, so the tree check after the stress legs does not change.

I ran the leg's own lines, extracted from the script unchanged, in the worktree. `STATE` and `LOG` pointed at a scratch directory.

| input | rc_ew | nightly.log |
|---|---|---|
| build rc 0, real artifact | 0 | `OK at ... (STRESS_EVICT eviction witness)`, witness exit 0 in 6 s |
| build rc 1 | 1 | nothing (the witness log says NOT RUN) |
| build rc 0, listing moved aside | 2 | `COULD NOT RUN: STRESS_EVICT eviction witness (exit 2)` |
| build rc 0, witness mutated (M1b) | 1 | `STRESS_EVICT EVICTION WITNESS FAILED` |

I did not run the whole nightly script. It fetches origin and builds in a checkout of its own.

**The guarding test** is `tools/test_landing_lane_shapes.py::test_the_nightly_grades_the_stress_evict_artifact`, in build.sh's pre-build pytest lane. It parses the real script and requires all of the following:

1. exactly one witness invocation on `s4.stress.*`;
2. that invocation comes after the STRESS_EVICT build and before STRESS_ART;
3. it sits in the THEN branch of `if [ "$rc_se" = 0 ]`;
4. `rc_ew=$?` is captured right after it;
5. `rc_ew` is in the worst-wins fold;
6. nothing sets `rc_ew=0` by hand.

Seven parametrized controls each break exactly one of these clauses, and the parser reports every one of them.

Red-first on the real script:

- Deleting the leg on disk (20 lines) gave 1 failed, 13 passed, with the message "found 1 build(s), 0 invocation(s)".
- Dropping `"$rc_ew"` from the real fold gave 1 failed, 13 passed.
- Restoring from the commit gave 14 passed.

## The keepalive manifest: why the witness is not `[wired]`

The booking said to move the witness from `[not_wired]` to `[wired]` with a baseline. **That would turn the keepalive lane red every night, so I did not do it.**

`tools/keepalive_lane.py` gives every wired row a single artifact, `{rom}` = `s4.debug.bin`. That is the only ROM `tools/nightly_instrument_keepalive.sh` builds. On that ROM the witness prints a line-leading `UNMEASURABLE:`.

Measured: I ran the real lane with a scratch manifest that wires the witness at `expect = 2` (with matching `baseline_args`) and `--only evict_witness`. The row came back **COULD NOT RUN ("the instrument itself refused: UNMEASURABLE ...")** and the lane exited 2. The refusal marker is checked before the baseline, so no `expect` value can make that row pass. Pointing the row at `s4.stress.*` does not help either, because that lane never builds that artifact.

The witness therefore keeps the disposition `preset_lab_witness.py` already has: `[not_wired]`, with the reason "reachable: tools/nightly_effects_gates.sh runs it every night".

Census effect: `keepalive_population.unreachable()` goes from 44 to 43, and `evict_witness.py` leaves the unreachable set. I measured this on the same tree with only the two changed files swapped back to their base versions. The accounting is unchanged otherwise: 85 bus instruments, 35 wired tools / 36 rows, 50 not wired.

⚠ **The census credits the witness twice, and only one of the two actually runs it.** The nightly runs it, but the new test also names it inside a regex literal. Each reference is enough on its own to make the witness "reachable". If the leg were deleted, the census would still say reachable, through the test. The test would be red at that point, so this is not a silent hole. It is the known `CENSUS-CRITERION-TOO-NARROW` pattern, recorded here and not booked.

## The listing EQU wrinkle

With the installed sigil binary (built 2026-09-17), `s4.stress.lst` publishes `EQU PAGE_FRAMES_CLAMP = $0000000C` (12), while the ROM compares against 9.

Sigil fixed this in `df055bd1`, which is an ancestor of `74914fa8`. Sigil's landing record `dd20a3ec` states two things about the fix:

- the ROMs are identical in all five shapes;
- the only listing change is that EQU, from 12 to 9.

The witness verdict reads the clamp only from the emitted `cmpi.w`. The EQU is read for just one purpose: printing the informational `!! DISAGREEMENT` line.

**Control:** I gave the repaired witness today's listing with that single line edited to `$00000009`, which is what the fixed sigil publishes. The result was `PAGE_FRAMES_CLAMP(EQU)=9`, no disagreement line, the same Phase 1 result, and **exit 0**.

The nightly's expected outcome is therefore exit 0 on today's binary, and still exit 0 after sigil is rebuilt with the fix. The only visible difference will be that the DISAGREEMENT line disappears. Nothing grades that line.
