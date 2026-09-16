# The night region's FADE edge at x = 3400, captured until it settled

`s4.debug.bin` md5 `63980e7e`, symbols `s4.debug.lst`. Cold boot, one held RIGHT in DEBUG free flight (16 px/tick). "Centre" is `Camera_X` + `CAM_SCREEN_HALF_W`, the point `Region_Resolve` tests. The night region is row 9, x 3400..4799.

**Every filename here was derived from the state read on that tick, by `tools/capture_settle.py`. A frame is called `settled` only where that predicate said so from a live read; otherwise the name carries the first clause that refused.** This set exists because `docs/captures/2026-09-13-regions-p2-night/t5-f272-settled.png` was named by hand and is mid-fade.

## What `settled` was required to mean

Seven clauses, all of them, from a live read, with CRAM lines 1-3 identical across **3** consecutive samples:

| clause | what it reads |
|---|---|
| `fading` | `Pal_Fade_Frames == 0` |
| `armed` | `Pal_Fade_Request == 0` |
| `layer` | `Pal_Base_Dirty`, `PAL_ACT_CYCLE`, `Pal_Op` — the three gates `Palette_Compose` branches on for the layers that move lines 1-3 |
| `buf` | all 48 words of `Palette_Buffer` lines 1-3 == `Pal_Target` under `$0EEE` — ARRIVED, not merely stopped |
| `cram` | CRAM lines 1-3 == the buffer (the DMA runs in the next VBlank) |
| `lag` | the window took no lag frame |
| `hold` | CRAM identical across 3 samples |

N = 3 is derived: 1 tick compose -> CRAM + 1 tick CRAM -> the completed video frame a paused screenshot returns + 1, because N samples span N-1 intervals. Full derivation and its citations are in `report.json` under `settle.derivation`.

## The run

Crossing at Logic_Tick 203, camera centre x 3408. `k` counts ticks from there.

| k | tick | centre x | row | `Pal_Fade_Frames` | CRAM stable run | state | file |
|---:|---:|---:|---:|---:|---:|---|---|
| -4 | 199 | 3344 | 1 | 0 | 194 | `buf` | `in-k-004-t00199-cx3344-r01-pf00-buf.png` |
| -3 | 200 | 3360 | 1 | 0 | 195 | `buf` | `in-k-003-t00200-cx3360-r01-pf00-buf.png` |
| -2 | 201 | 3376 | 1 | 0 | 196 | `buf` | `in-k-002-t00201-cx3376-r01-pf00-buf.png` |
| -1 | 202 | 3392 | 1 | 0 | 197 | `buf` | `in-k-001-t00202-cx3392-r01-pf00-buf.png` |
| +0 | 203 | 3408 | 9 | 15 | 1 | `fading` | `in-k+000-t00203-cx3408-r09-pf15-fading.png` |
| +1 | 204 | 3424 | 9 | 14 | 2 | `fading` | `in-k+001-t00204-cx3424-r09-pf14-fading.png` |
| +2 | 205 | 3440 | 9 | 13 | 1 | `fading` | `in-k+002-t00205-cx3440-r09-pf13-fading.png` |
| +3 | 206 | 3456 | 9 | 12 | 2 | `fading` | `in-k+003-t00206-cx3456-r09-pf12-fading.png` |
| +4 | 207 | 3472 | 9 | 0 | 1 | `hold` | `in-k+004-t00207-cx3472-r09-pf00-hold.png` |
| +5 | 208 | 3488 | 9 | 0 | 2 | `hold` | `in-k+005-t00208-cx3488-r09-pf00-hold.png` |
| +6 | 209 | 3504 | 9 | 0 | 3 | `settled` | `in-k+006-t00209-cx3504-r09-pf00-settled.png` |
| +7 | 210 | 3520 | 9 | 0 | 4 | `settled` | `in-k+007-t00210-cx3520-r09-pf00-settled.png` |
| +8 | 211 | 3536 | 9 | 0 | 5 | `settled` | `in-k+008-t00211-cx3536-r09-pf00-settled.png` |

**3 frame(s) INSIDE THE NIGHT REGION are named `settled`** and they are the only ones any night colour measurement may be taken from: `in-k+006-t00209-cx3504-r09-pf00-settled.png`, `in-k+007-t00210-cx3520-r09-pf00-settled.png`, `in-k+008-t00211-cx3536-r09-pf00-settled.png`.

The 0 approach frame(s) before the crossing are also named `settled` — correctly, on the DAY palette. They are the control that the predicate is not vacuously false, and they are NOT night evidence. The region row in each name (`r` field) is what tells the two apart.

## The step model, as a cross-check and never as a source

`Palette_DoFade` steps on ODD decremented counts and closes early on arrival, so a channel distance `d` from the LIVE buffer predicts arrival at `2d - 1` composes. Measured here from the buffer as it stood at the arm, not assumed:

* max channel distance `d` = **3**
* predicted arrival k = **5**
* measured arrival k = **5**
* `Pal_Fade_Frames` on the arming tick = **15**

They agree.

## What these stills cannot settle

Whether the fade READS as a transition or as a fault is a motion percept at 60 Hz; a contact sheet cannot produce it for anyone. Use these to measure colour and to see which frame is which, and the running ROM to judge the look.
