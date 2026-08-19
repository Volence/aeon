# Engine reservation baselines — idle and max-diagonal

**Parcel:** Scanline Services P2, Phase 0, Tasks 2 and 3.
**Instrument:** oracle (old), headless harness, per-routine profiler rows.
**Tool:** `tools/engine_baseline_probe.py`
**ROM:** `s4.debug.bin`, crc `d22dda85`, len 713295, branch `measure/scanline-p2-phase0` off
master `18af84f3`.
**Sample:** 31 video frames per state, **5 independent boots per state**, spread **0** on every
row of both states.
**Wall clock:** run started 2026-08-19T14:39:36-04:00 (`up 1 day, 15:03`, load 1.57), finished
by 14:45:54 (`up 1 day, 15:09`, load 2.93) — about **6 minutes** for 10 boots. That is the
probe; the build is a separate command and is not inside it.

Read this file alongside `INSTRUMENT-PARITY.md`, whose three standing caveats apply to every
row here — in particular **caveat 0: every cycle figure is an IDEAL CYCLE count.** Oracle's
clock adds only `cyclesExecuted` to `_currentCycle` (`M68000.cpp:1029-1031`) while bus, VDP and
DMA stall accumulate in `additionalTime` and land in `_currentTime`. Nothing below includes a
stall.

---

## 1. The two camera states, defined

The plan's Step 1 requires these written down first, because "a baseline whose state is not
reproducible is not a baseline" — the effects-p3 baseline rows went camera-stale exactly this
way (R1 evidence §7.3, "NO VERDICT").

### `idle`

| property | value |
|---|---|
| how it is reached | boot, `run_frames 180`. **Nothing is poked at all.** |
| game state | `GameState_OJZScroll_Update` |
| act / section | OJZ act 1, section 0 |
| camera | `Camera_X` = 96, `Camera_Y` = 144, stationary for the whole sample |
| player | at level-init start position, at rest, on the ground |
| streaming | quiescent — `Tile_Cache_Fill` 4629 cyc/frame, the residual per-frame tick |
| raster program | OJZ section-0 sparse preset, 4 records (see §4) |
| on screen | the OJZ section-0 scene: water boundary (shadow/highlight region fire) plus the VSRAM scroll fire |
| `Camera_Art_Hold` | 0 throughout |
| `Dbg_Cam_Clamp_Frames` | 0 throughout |

This is the most reproducible state available, because it is simply what the ROM does. There is
no poke to go stale.

### `max-diagonal`

| property | value |
|---|---|
| how it is reached | boot, `run_frames 180`, then **ONE poke**: the leader's `Sst.x_pos` += 2000 px and `Sst.y_pos` += 1400 px (16.16, pixels in the high word), then `run_frames 24` to reach steady state, then sample |
| what drives the camera | `Camera_Update` — the engine's own follow path, NOT a poked camera |
| camera | (320,368) -> (560,608) across the sample, **16 px per LOGIC TICK on both axes** = `CAM_MAX_X_STEP` = `CAM_MAX_Y_STEP`, the engine's own per-axis ceilings, both saturated |
| player | teleported far down-right and left there; physics continue, the gap never closes inside the window |
| act / section | OJZ act 1, section 0 for the whole window — the camera does not cross a boundary |
| streaming | fully loaded — `Tile_Cache_Fill` 51369 cyc/frame (40.1%), `Section_UpdateColumns` 3621 |
| raster program | **the same** OJZ section-0 sparse preset, 4 records, byte-identical to idle |
| `Camera_Art_Hold` | 0 throughout |
| `Dbg_Cam_Clamp_Frames` | 0 throughout |

**Why the engine's own follow path rather than `Debug_Scene_Freeze` + a poked camera.** The
freeze is the right tool for a PINNED scene (`tools/scenes/README.md`) and the wrong one here:
it skips `Camera_Update` AND `EntityWindow_Scan`, so a "main loop" total taken under it would
be missing two of the routines a reservation has to reserve for. Poking the camera each frame
would also interleave bus writes with the profiled window.

---

## 2. THE FINDING: sustained max-diagonal does not run at 60 Hz

This was not looked for. It was found because the derived check failed: the camera advanced
**8 px per video frame** where 16 was expected, and the plan's rule is that a state you cannot
re-enter as specified is not a baseline. Chasing it produced the result.

**It is not the art soft-clamp.** That was the first hypothesis and it is refuted twice over:
`Camera_Art_Hold` reads 0 at both ends of every sample, and DEBUG's own
`Dbg_Cam_Clamp_Frames` counter — which `Camera_Update` increments on any frame the clamp holds
an axis — stays at **0** for the entire run. A 40-frame per-frame trace shows the pattern
plainly: 16 px, then 0, then 16, then 0.

**It is lag.** The main loop overruns one video frame, `VInt_Lag` services the spare VBlanks,
and the logic ticks at roughly 30 Hz. Measured on the engine's own counters — `Frame_Counter`
counts VBlanks, `Logic_Tick` counts game-loop iterations and is documented in `engine/ram.emp`
as *"lag-immune, unlike Frame_Counter"*:

| state | video frames | logic ticks | frames per tick | `Lag_Frame_Count` delta | spread over 5 boots |
|---|---|---|---|---|---|
| idle | 31 | 30 | **1.033** | +1 | 0.000 |
| max-diagonal | 31 | 15 | **2.067** | +16 | 0.000 |

**Two independent instruments agree.** The camera advances `CAM_MAX_STEP` per logic tick, so
`camera_dx / 16` is a second, unrelated derivation of the tick count. It reads 15.00 against
`Logic_Tick`'s 15, exactly, on every boot. The probe asserts this agreement rather than
assuming either.

### The consequence for every row below

Every max-diagonal figure has **two honest denominators** and both are published:

- **cycles per VIDEO FRAME** — what the 128000-cycle frame budget divides. This is the profiler's
  native unit.
- **cycles per LOGIC TICK** — what one invocation of the work actually costs, = per-video-frame
  x frames-per-tick.

Quoting only the first understates every max-diagonal routine by 2.07x, and worse, makes some
of them appear to get *cheaper* under load. `Parallax_Update` is the clean example: 19511
cyc/video-frame at idle against 12189 at max-diagonal, which reads as a 37% saving and is
nothing of the sort — per tick it goes 20161 -> 25191, a 25% rise, which is the true direction.

**`HBlank_Vector_Slot` is the deliberate exception and has no per-tick column at all.** HInt is
a DISPLAY-time cost: the schedule is armed in VBlank and the handler fires on every video frame
whether or not the main loop ticked. Multiplying it by the lag factor would invent HBlank work
that does not happen. The probe prints `n/a (display)` there rather than a number.

---

## 3. The rows

31-frame sample, 5 boots, **spread 0 everywhere**. Per-routine rows matched on the low 24 bits
of the entry address; `interrupts.hint` is never read.

### idle — 1.033 video frames per logic tick

| routine | calls | cyc/video-frame | %frame | cyc/logic-tick |
|---|---|---|---|---|
| `HBlank_Vector_Slot` (HInt total) | 4 | **1878** | 1.5% | n/a (display) |
| `GameState_OJZScroll_Update` (main loop) | 1 | **35125** | 27.4% | 36296 |
| `VInt_Level` (VBlank bracket) | 1 | **8280** | 6.5% | 8556 |
| `VInt_Lag` | 1 | 166 | 0.1% | 172 |
| `VSync_Wait` (idle headroom) | 1 | 79595 | 62.2% | 82248 |
| `Parallax_Update` | 1 | **19511** | 15.2% | 20161 |
| `Raster_VBlank` | 1 | **1482** | 1.2% | 1531 |
| `Palette_Compose` | 1 | **145** | 0.1% | 150 |
| `Enqueue_Dirty_Buffers` | 1 | **1356** | 1.1% | 1401 |
| `BgAnim_Update` | 1 | **181** | 0.1% | 187 |
| `Camera_Update` | 1 | 565 | 0.4% | 584 |
| `EntityWindow_Scan` | 1 | 1796 | 1.4% | 1856 |
| `Tile_Cache_Fill` | 1 | 4629 | 3.6% | 4783 |
| `Section_UpdateColumns` | 1 | 847 | 0.7% | 875 |

### max-diagonal — 2.067 video frames per logic tick

| routine | calls | cyc/video-frame | %frame | cyc/logic-tick |
|---|---|---|---|---|
| `HBlank_Vector_Slot` (HInt total) | 4 | **1878** | 1.5% | n/a (display) |
| `GameState_OJZScroll_Update` (main loop) | 1 | **55144** | 43.1% | **113964** |
| `VInt_Level` (VBlank bracket) | 1 | **6117** | 4.8% | 12642 |
| `VInt_Lag` | 1 | 2904 | 2.3% | 6002 |
| `VSync_Wait` (idle headroom) | 1 | 34371 | 26.9% | 71033 |
| `Parallax_Update` | 1 | **12189** | 9.5% | 25191 |
| `Raster_VBlank` | 1 | **1488** | 1.2% | 3075 |
| `Palette_Compose` | 1 | **67** | 0.1% | 138 |
| `Enqueue_Dirty_Buffers` | 1 | **1236** | 1.0% | 2554 |
| `BgAnim_Update` | 1 | **74** | 0.1% | 153 |
| `Camera_Update` | 1 | 319 | 0.2% | 659 |
| `EntityWindow_Scan` | 1 | 953 | 0.7% | 1970 |
| `Tile_Cache_Fill` | 1 | **51369** | 40.1% | **106163** |
| `Section_UpdateColumns` | 1 | 3621 | 2.8% | 7483 |

`calls` is per-video-frame and integer. At max-diagonal `VInt_Level` and `VInt_Lag` both read
1 because a two-frame tick carries exactly one of each — which is the lag showing up in a
third place.

### What actually spends the max-diagonal frame

| | idle | max-diagonal |
|---|---|---|
| the five effects routines, per video frame | 22675 (17.7%) | 15054 (11.8%) |
| the five effects routines, per logic tick | 23430 | **31111** |
| `Tile_Cache_Fill` alone, per video frame | 4629 (3.6%) | **51369 (40.1%)** |
| `Tile_Cache_Fill` alone, per logic tick | 4783 | **106163** |

**Art streaming, not effects, is what spends the max-diagonal frame** — by better than 3x, and
the gap widens per tick. Worth stating plainly in a budget parcel: the reservation the scene
budgets are subtracted from is dominated by a cost the scene model does not control.

The main loop costs 113964 cycles per tick against a 128000-cycle frame — 89% — with the VBlank
bracket and the lag handler on top. That is the mechanism behind the 30 Hz.

---

## 4. Budget axis 4b — the per-frame HInt total (Task 3)

Design §5 axis 4 splits into (4a) per-fire spacing, which `check_density` already owns, and
(4b) a per-frame TOTAL, which is genuinely new. **Every absolute HInt row this tree has ever
carried came off `interrupts.hint`, which is HBlank plus VBlank in this ROM. This is the first
one that did not.** It is the HBlank trampoline's own per-routine row, `$FFB452`.

### Measured

| state | HInt cyc/video-frame | fires | %frame | spread over 5 boots |
|---|---|---|---|---|
| idle | **1878** | 4 | 1.5% | 0 |
| max-diagonal | **1878** | 4 | 1.5% | 0 |

**Identical at both states, and that is a fact about this content rather than a general one.**
The OJZ section-0 sparse schedule's records are position-clamped and the max-diagonal window
never leaves section 0, so the same 4-record program is live in both. The probe captures the
live buffer at the start AND end of every sample and asserts it did not change mid-sample, and
that it is the same across all five boots; both held. Do not read 1878 as "the HInt total" —
read it as "the OJZ section-0 sparse program's HInt total". The dense figure below is 17x it.

### The model cross-check — EXACT, gap 0

The plan's Step 2 requires summing the model's fire costs over the frame's **live records** and
investigating any gap before recording either number. There is no gap.

The live program is read through `Raster_Active_Buf` — never from a fixed buffer address,
because `Raster_BuildSchedule` re-records into the inactive buffer and swaps every frame. Its
wire image at both states:

```
0004                                     header: pal_dirty_mask
8A4D 0000                                record 0 — priming, 0 ops
8A8D 0000                                record 1 — priming, 0 ops
8AFF 0002                                record 2 — 2 ops
     0000 8C89                             OP_SET_REG  $8C89   (shadow/highlight ON)
     0004 C0480000 000B 0002 0048          OP_PAL_REGION  3 words, spin 11
8AFF 0001                                record 3 — 1 op
     0002 40020010 0016 0000 0043          OP_CRAM (a VSRAM write) 1 word, spin 22
8AFF FFFF                                terminator
```

| record | model | derivation |
|---|---|---|
| 0 (priming) | 294 | `RASTER_FIRE_BASE_CYC` 280 − 16 + `RASTER_PRIMING_GUARD_CYC` 30. The 30 is the frame-rewind interlock, which ONLY a no-op record pays; the −16 is what a record WITH ops pays over a no-op one |
| 1 (priming) | 294 | as above |
| 2 (the water fire) | 666 | 280 + reg_set 40 + region(3 words, spin 11) 346 |
| 3 (the vsram fire) | 624 | 280 + cram(1 word, spin 22) 344 |
| **total** | **1878** | **measured 1878, gap 0** |

Fire count is checked too: 4 live records against `calls` = 4.

**The two constants come from the shipped `.emp`, not from a mirror.** `RASTER_FIRE_BASE_CYC`
and `RASTER_PRIMING_GUARD_CYC` are read out of `engine/effects/raster_dsl.emp` at run time by
the probe, so a drift fails rather than silently re-baselining.

**The decoder is the only new transcription in the probe, and it is pinned hard.** It is the
inverse of `raster_cost_probe`'s encoder, and `selftest_decoder()` runs all NINE measured
fixture programs (F0..F8) through encode -> decode -> cost-sum, requiring every total to match
what the hardware reported in Task 1 — 588 / 2508 / 4332 / 3818 / 4584 / 3172 / 3340 / 4332 /
4632. It passes. A decoder that mis-parsed an op, dropped a record or mis-costed a class cannot
survive nine of those. The self-test runs on every invocation and the tool exits non-zero if it
fails, so it cannot go quietly vacuous.

### A stale row this closed

`sparse_fire_water_cycles` read **680**, tagged `modelled`. Decoding the actual live water fire
prices it at **666**, and it is now one of the two authored records inside a sum that matches
the hardware exactly, so the row is measurement-backed rather than modelled. 680 is retained as
`sparse_fire_water_cycles_SUPERSEDED3` per this file's convention.

Worth naming so it is not read as an error: **666 is also fixture F4's figure, and the two get
there differently.** F4's lone region op solves to spin 15; the water fire's solves to 11, which
is 40 cycles cheaper, and the water fire spends exactly that 40 on the `reg_set` F4 does not
have. A coincidence, not a check.

### The dense tier — measured, and its model DISAGREES

Axis 4b's real worst case on shipped content is not the sparse program. It is the dense tier,
and it is 17x larger. Measured at a third state (`Debug_Scene_Freeze` = 1, `Camera_Y` = 144,
`Camera_X` = 4960 — `tools/scenes/effects_raster_dense.json`'s state, which reaches OJZ section
2 where `OJZ_TestGradient` lives, 96 lines):

| | fires | HInt cyc/video-frame | %frame |
|---|---|---|---|
| shipped `OJZ_TestGradient`, 96 lines | **100** | **32758** | 25.7% |
| model (`FD1`/`FD2` fixture pair): 1512 + 96 x 328 | 101 | 33000 | 25.8% |
| a POKED fixture at the SAME top(96) and lines(96) | **101** | **33000** | 25.8% |

**The model is right and the shipped program is 242 cycles and one fire short of it.** The
model's intercept 1512 is derived from the measured pair (`FD1` 4136 at 8 lines, `FD2` 14632 at
40 lines, both giving 1512 exactly), and a sweep at 8 / 40 / 80 / 96 / 120 lines confirms
`lines + 5` fires and `1512 + 328 x lines` hold at every count including 96. So the
discrepancy is not in the model and not in the line count — it is between the shipped program
and a **byte-identical** poked wire image.

Three hypotheses tested, all three refused:

1. **A sample-window artifact.** Re-measured at a 60-frame window: 100 fires, 32758 cycles.
   Unchanged.
2. **The frame-top offscreen ship.** The poked fixtures set `Effects_Offscreen_Entry` = 0 and
   the shipped state has it live. Poking it to 0 in the shipped state changed nothing.
3. **The patch-table re-record.** Likewise `Raster_Patch_Tab` = 0. Changed nothing.

`Raster_Dense_Lines` reads **1** at the frame boundary in the shipped state where 0 is
expected, so the run is finishing one line short — consistent with the missing fire, though 242
is not one dense line's 328 either.

**UNEXPLAINED, and recorded rather than smoothed.** It does not touch the two rows Task 3
asked for, which are the sparse totals at the two Task-2 camera states, and those are exact.
Booked in the toml as `hint_total_dense_model_gap = -242` with
`hint_total_dense_status = "measured, model DISAGREES"`.

---

## 5. What these rows do NOT cover

Stated so Phase 2 does not read more into them than they say.

- **One act, one section.** Everything here is OJZ act 1 section 0 (plus section 2 for the dense
  row). A different section's preset is a different program and a different reservation.
- **A near-empty game state.** `GameState_OJZScroll` is a scroll test. A populated level has
  more objects, so `RunObjects`, `TouchResponse` and `Render_Sprites` all grow and the idle
  headroom shrinks. The 62.2% idle at rest is an upper bound on headroom, not a promise.
- **No sound-driver contention beyond what the shape carries.** These are the canonical
  `DEBUG=1` sound-ON builds; nothing was measured with sound off for comparison.
- **Ideal cycles.** See caveat 0 — no bus, VDP or DMA stall is in any figure here.
- **No transition frame.** Design §5's ledger evaluates the TRANSITION frame (outgoing and
  incoming configs both partially live, the reg `$0B` mode change, the larger HScroll DMA).
  Neither state above crosses a section boundary, so no transition frame is measured. That is
  Task 12's subject and it will need its own state.
