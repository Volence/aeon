# DPLC-STRADDLE-REACHABLE: the six straddles are Sonic's frames $29 and $2B, and dplc_straddle already said they were reachable (2026-09-25)

Branch `parcel/dplc-straddle-reachable`, base `1efd5fb3`. Files changed:
`tools/dma_straddle_exercise.py`, `tools/test_dma_straddle_exercise.py` (new), this report,
`docs/DEFERRED_WORK.md`, and dated correction notes in three older records
(`docs/witness/f7-straddle-instrument-read-2026-09-05.md`,
`docs/witness/f7-sprite-jumble-diagnosis-2026-09-05.md`,
`docs/measurements/2026-09-03-dma-split-reserve-reading.md`). No `.emp`, no map, no build
script, no clip manifest or bake tool, and not `tools/bganim_room.py`.

## Short answer

The straddles are Sonic's own DPLC loading run-tilt frames **$29** (four times) and **$2B**
(twice). Each one is Perform_DPLC's entry loop enqueueing `Art_Sonic+$5960` (0x7FFC2, 512 B or
224 B), which crosses the 0x80000 boundary. `tools/dplc_straddle.py`, run on the ROM the
observation was made on, lists **$29 and $2B as straddling and REACHABLE**. The static tool's
reachability analysis was right, and every straddle came from a DPLC frame. So neither reading
(a) nor reading (b) holds. What was wrong is a third thing:
**`dma_straddle_exercise.py` carried dplc_straddle's 2026-09-05 output as prose and as a
literal control ladder, and never re-read it after the art moved.** The stale literal also
made control B unable to fire on today's ROM. That is fixed, with a test proven red first.

No engine defect was found. Peak 1 against a reserve of 2 and zero rejects both stand.

## 1. dplc_straddle on today's master, and a correction to the brief

`python3 tools/dplc_straddle.py --lst s4.debug.lst` on `1efd5fb3`'s `s4.debug.bin`
(crc32 `62238a15`, 848,075 B), exit 0:

| subject | art base | straddling frames | REACHABLE | unreachable |
|---|---|---|---|---|
| sonic | `Art_Sonic` 0x7A662, spans 0x80000 | `$29`, `$2B` | **`$29`, `$2B`** | none |
| tails | `Art_Tails` 0x34A64, spans 0x40000 | `$63` | none | `$63` |
| tails_tail | `Art_TailsAppendage` 0x51498 | none | none | none |
| knuckles | `Art_Knuckles` 0x55E60, spans 0x60000 | `$4C` | none | `$4C` |

It prints "worst REACHABLE frame split: 1 extra entry(ies) against a 2-slot
DPLC_ENTRY_RESERVE" and "CONCURRENT ... worst case sonic 1 + knuckles 0 + tails 0 = 1
split(s)". It also prints its existing MARGIN WARNING: Sonic's art can move 5,151 B up before
VERDICT A fires, which is less than the 49,152 B `DATA_GROWTH_RESERVE`. That warning was
already there before this parcel, and nothing here changes it.

**The brief said `Art_Sonic` had moved since 09-19. In the canonical shape it has not.**
Today's `s4.debug.bin` is byte-identical to the one the 09-19 campaign measured (crc32
`62238a15`, which the booking commit `8c83475a` and its lane-log entry both record). I also
rebuilt the 09-19 tree (`8c83475a`, `FAST=1 DEBUG=1`, today's sigil). It gives crc32
`62238a15` again, and **the 09-19 revision of `dplc_straddle.py` on that ROM already printed
`straddling REACHABLE: 2: $29, $2B`**. So the booking's premise was false for the ROM the
observation was made on: dplc_straddle did not claim that every straddling frame was
unreachable. The one place `Art_Sonic` has moved is the off-canonical Sonic 2 clip shape
(0x80D0E, per `docs/research/2026-09-25-s2clip-bank-room-gate.md`). See "Open / TAGGED".

## 2. The frames that straddle in real play, attributed

**Method.** I did not write a new campaign. I ran `tools/dma_straddle_exercise.py`'s own
`main()` with a wrapper around one method, `Driver.call`. The wrapper arms an execution
breakpoint on `$engine.dma_queue$QueueDMA_Deferrable$split` (0x1ECC). It checks that this
address holds `addq.w #1,Dbg_DMA_Straddle_All`, so the breakpoint fires exactly where the
counter is incremented. It then replays the campaign's `play_input` rows one frame at a time,
using `hold` plus `run_frames 1`. When the run halts on the breakpoint, the wrapper reads the
registers, the return address and both player SSTs, steps one instruction and finishes the
frame. The wrapper is a scratch harness and is not committed. The reason is under "What was
not done".

Two things surprised me, and both are measured.

* **`play_input` does not end on a breakpoint halt.** It keeps going, and every halt uses up one
  row-frame. Probe: a breakpoint on a main-loop PC, `play_input` of 30 frames. The reply said
  `frames: 30`, the frame counter moved by 3, and `hits` was 28. My first wrapper trusted
  `play_input` to stop. It recorded 0 hits while the counter reached 6, and the input timing
  drifted (first hit at (1082,490) `$2B` instead of (1082,497) `$2C`). That run is thrown away.
  The per-frame replay above is the fix.
* A `run_frames 1` issued from the middle of a frame runs to the next frame boundary, not a
  whole frame further. So the wrapper keeps the campaign's frame count exactly.

**Fidelity check.** The per-frame replay reproduces the booking exactly: `*** FIRST NON-ZERO
Dbg_DMA_Straddle_Peak=1 at frame 13005 (P4-anchored) player=(1082,497) in_air=False
mapping_frame=$2C`. The final cells match too: All 6, Peak 1, Reject 0, Overflow 0, Capped 0,
over 36,638 frames. That run was `uptime` 04:10 to about 04:14, load average about 21.

**The six hits.** Every hit has these values: caller `$engine.objects.dplc$asm1$entry_loop+0x20`
(return 0x2FFA, which is inside `Perform_DPLC`), `a0` = 0xFFFF901E (`Player_1`), `a3` =
0x7A662 (`Art_Sonic`), `d4` = 0x8162 (`DMA_Important_End`, so the Important queue), VRAM dest
0x7800, `Character_ID` 0 (Sonic), `Player_1` anim 1 (`ANIM_RUN`), status $00 (grounded), and
`Player_2` empty.

| poll | P1 frame (prev) | angle | P1 (x,y) | source .. end | bytes | cells before |
|---|---|---|---|---|---|---|
| 12975 | `$29` (`$25`) | $4C | (1086,459) | 0x7FFC2 .. 0x801C1 | 512 | 0/0/0/0 |
| 12975 | `$2B` (`$2A`) | $40 | (1082,484) | 0x7FFC2 .. 0x800A1 | 224 | 1/0/1/0 |
| 13005 | `$29` (`$2C`) | $34 | (1085,511) | 0x7FFC2 .. 0x801C1 | 512 | 2/0/1/0 |
| 13582 | `$29` (`$25`) | $4C | (1086,461) | 0x7FFC2 .. 0x801C1 | 512 | 3/0/1/0 |
| 13582 | `$2B` (`$2A`) | $40 | (1082,486) | 0x7FFC2 .. 0x800A1 | 224 | 4/0/1/0 |
| 13612 | `$29` (`$2C`) | $34 | (1085,513) | 0x7FFC2 .. 0x801C1 | 512 | 5/0/1/0 |

("poll" is the campaign's `frames_driven` when the hit was recorded, which only advances at
chunk boundaries. "cells" is All/Frame/Peak/Reject.)

This is the run-tilt mechanism. `Player_ApplyTilt` takes the ground angle (biased by one,
mirrored when facing right), adds `TILT_BIAS` ($10), shifts right by 5 and masks with 3 to get
an orientation block. Here it picked block 2, and run block 2 is frames $29 to $2C. The place is a steep wall or curve at x ≈ 1082-1086, y ≈ 459-513, run up and down
twice. `$2C`, the frame the booking quotes, **does not straddle**. It was the frame at the poll
boundary: two of the six hits have `prev_frame = $2C`, because the DPLC was leaving `$2C` for
`$29`.

## 3. Which reading is true

**(a) "The static tool's reachability analysis is wrong": REJECTED.** On this exact ROM the
tool reports `$29` and `$2B` as straddling and REACHABLE, and it derives them from the tilt
expansion (`derived: sonic: tilt: ids 0/1, 4 blocks, strides 1<<3/1<<2`). As a wider check, I
compared every mapping frame the campaign saw at its 735 polls (37 distinct frames) with the
tool's reachable set for Sonic (95 of 224). None of the 37 falls outside it. No path into a
straddling frame was missed.

**(b) "The straddle is not a DPLC transfer": REJECTED.** All six breakpoint hits return into
Perform_DPLC's entry loop, with source inside `Art_Sonic` and `a0` = `Player_1`. The static page
survey prints `ANY page-in landing in this act can straddle a 128 KB boundary: False` (11 pages,
0x015B2C to 0x018BBD). No other enqueuer reached `.split`.

**What was actually wrong: the argument quoted a frame list from an older build.** On
2026-09-05 dplc_straddle named Sonic `$65`, Tails `$9F` and Knuckles `$85`, all unreachable.
Before that, on 09-03 and 09-04, it named Knuckles `$8B` and then `$88` as the reachable
straddlers. The list moves every time the data above the character art changes size.
`dma_straddle_exercise.py` copied the 09-05 list into three places: the module docstring,
`static_straddle_survey()`'s docstring and the control-B ladder default. Its "empty by
construction" argument, and the two 09-05 witness records, quoted that copy. **The tool that
owns the answer was re-run on every build and was right. The copy was never re-read.**

**It also cost a control.** On `62238a15` none of `$65`, `$9F` or `$85` straddles for any
character, so control B could never fire. Both of today's full campaigns on this ROM print
"the instrument did NOT fire on any forced mapping frame of $65, $9F, $85". Nobody had noticed,
because control A fires in a full campaign. It matters when control A does not fire. I measured that case with the same short
campaign (`--survey-x1 400 --p1-frames 60 ...`, where control A stays silent):

* literal ladder (`--control-frame 0x65 0x9F 0x85`): `did NOT fire` ... `VERDICT: UNMEASURABLE`, **exit 2**
* derived ladder (the new default, `$29 $2B $63 $4C`): `the instrument FIRES: forcing mapping_frame $29 moved Dbg_DMA_Straddle_All 0 -> 1 ... Dbg_DMA_Straddle_Frame moved 0 -> 1`, first attempt, **exit 0**

That is the LOSSY failure mode `KEEPALIVE-IS-BLIND-TO-LOSSY` describes, in a second instrument.
A short run on a live instrument would have reported it as unmeasurable.

## 4. What changed

1. **`default_control_ladder(lst, rom)`** (`tools/dma_straddle_exercise.py`). It returns every
   straddling DPLC frame of each player subject in this build, Sonic first. It computes them
   with dplc_straddle's own primitives: the labelled art bases, the DPLC tables, `TILE_SIZE`,
   and the boundary decoded from `dma_queue.emp`, with the extents checked against the ROM.
   Reachability is ignored on purpose, because the control writes the frame itself.
   `--control-frame` still overrides it. A derivation failure raises `SetupError` (exit 2). An
   empty ladder is returned as empty, and the verdict then rests on control A alone.
2. **`tools/test_dma_straddle_exercise.py`** (new, `needs_build("s4.debug.bin",
   "s4.debug.lst")`). It checks that every frame in the default ladder straddles for some player
   subject in the built ROM, and that each player subject with a straddler has at least one in
   the ladder. The expectation is derived, and no frame number appears in the test. If no player
   straddles at all, the test fails loudly instead of passing without checking anything.
   * **Red first, no mutation needed.** The baseline itself was wrong. On `70c3f3f0` (the
     committed baseline, where the refactor kept the literal): `AssertionError: control B would
     force ['$65', '$9F', '$85'], which straddle for NO player subject in s4.debug.bin; the
     straddling frames are sonic: $29 $2B, tails: $63, knuckles: $4C`, 1 failed.
   * Green after the fix (`5ea40912`): 1 passed.
   * **Mutations on the committed fix, each shown on disk before its run and each restored with
     `git checkout` from the commit.** M1 appended `0x65` to the returned ladder:
     `control B would force ['$65'] ...`, 1 failed. M2 inserted `break` after the first player
     subject: `the ladder has no straddling frame for ['tails', 'knuckles']`, 1 failed. After
     the restore, `git status` was clean and the test passed.
3. **Prose.** The module docstring, `static_straddle_survey()`'s docstring and
   `control_body()`'s 09-19 correction paragraph are corrected. The printed NOTE that read a
   silent control A as "the straddle population reachable by this act is empty" now says
   "THIS campaign never enqueued a straddling transfer, NOT 'none is reachable'" and points at
   dplc_straddle's REACHABLE line. The old wording is false on `62238a15`: a short run prints
   zeros while `$29` and `$2B` are reachable.
4. **Older records.** The two 09-05 witness docs and the 09-03 measurement quote the
   "unreachable" argument. Each gets a dated note beside the sentence. The historical text is
   left as it was, because it was true of the ROM it described.
5. **`docs/DEFERRED_WORK.md`.** The booking is closed with this finding.

## 5. Engine risk (none found, and here is how big the margin is)

* All six straddles got both slots. `DMA_Split_Reject_Count` stayed 0 and `.full` and the byte
  cap stayed 0, so the queue handled every split correctly.
* Per-window demand: `Dbg_DMA_Straddle_Peak` = 1. The breakpoint trace confirms it: the two hits
  at poll 12975 fall in different VBlank windows (Peak stayed 1 while All went 0 to 2).
* Static bound: dplc_straddle's reachable split ceiling for this placement is 1 per character,
  and the concurrent worst case is 1 (Tails' and Knuckles' straddlers are unreachable). The
  reserve is 2.
* The standing risk is dplc_straddle's existing MARGIN WARNING, not anything found here. A
  5,151 B upward move of `Art_Sonic` reaches VERDICT A. That tool gates every sonic4 build, so
  the first bad placement turns a build red. I changed no engine code and no engine change is
  proposed.

## What was not done, and why

* **The attribution harness is not committed.** It is a wrapper around the campaign, and it
  depends on a server behaviour (`play_input` does not stop on a breakpoint) that I measured once
  today and did not pin. Committing it as a tool means a keepalive-manifest row and a test of
  that server behaviour, which is a bigger job than this booking. Its method and full output are
  above. If someone wants it kept, it is about 150 lines. **TAGGED: decide whether per-hit
  straddle attribution becomes an `--attribute` flag on `dma_straddle_exercise.py`.**
* **The 09-05 frame list could not be re-measured.** Today's sigil cannot build `667b9604`:
  `emit_sound_blob ... plain blob is 6163 bytes, expected 6176`. The 09-05 list is quoted from
  the 09-05 records.

## Open / TAGGED

* **TAGGED (for the S2-clip lane, not touched here):** in the S2 clip shape `Art_Sonic` sits at
  0x80D0E, which is +26,284 B from canonical. `dplc_straddle.py --sweep Art_Sonic --range
  26284:26286` on the canonical listing reports 0 straddling entries for Sonic at that shift.
  That sweep moves only `Art_Sonic`. The clip shape's other character bases were not measured,
  so it says nothing about Tails or Knuckles there.
* `docs/lane-status.json` still lists `DPLC-STRADDLE-REACHABLE` as `next`. I left that shared
  file for the lander, because a parallel parcel is also writing it.
