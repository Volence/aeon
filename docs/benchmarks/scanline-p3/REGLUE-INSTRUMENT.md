# The re-glue instrument — shadow tops under a vertical sweep, and the transition frame

**Parcel:** Scanline P3, Phase 0, Task 3 (`docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`)
**Tool:** `tools/parallax_cost_probe.py --sweep` and `--transition N`
**Engine bytes changed:** none. This parcel is instrument + rows only.
**ROM under test:** `s4.debug.bin`, `crc=5be03175 len=715084` (`DEBUG=1 ./build.sh`, 34.8 s wall,
uptime 05:04:10, load 2.74).

---

## 1. Why this exists, and what it does NOT close

Two reasons, both load-bearing, and the second one comes with a boundary that must not be
blurred.

1. **World-Y re-glue's claim is "layer tops stay glued to the background during vertical
   scroll", and nothing measured that.** `parallax_cost_probe`'s fit sweep reads
   `Parallax_Shadow_Bands` at ONE frozen camera position, as a fixture sanity check.
   `parallax_hscroll_probe`'s frozen arm (P3 Task 2) does derive and check the shadow view —
   but at `Camera_Y` 144, 320 and 96, **all three of which land the same rotation state**
   (`k = 3`). Task 7 rewrites the code that computes `k`. A mechanism whose only witness never
   varied its input is the F2/dense shape.

2. **P2 Task 12 is BLOCKED on two things and this closes ONE of them.** Blocker (b) was "there
   is no measured transition-frame reservation — neither Phase-0 camera state crosses a
   section boundary". A frozen camera plus `Parallax_Current_Config = A`,
   `Parallax_Target_Config = B`, `Parallax_Transition_Frames = N` written straight into RAM is
   a live transition frame with both configs routed, and it is measurable per-routine. §5
   below is that measurement.

**Blocker (a) is UNCHANGED and still blocks Task 12.** The section→scene join is a `Label`
end to end — `Sec.sec_parallax_config` → `EffectsPreset.ep_parallax` →
`preset(parallax: Label = 0)` — so there is no comptime path from a config back to its scene
value, and an `ensure` comparing a Label to an int is silently unevaluable and always passes.
P3 does not touch that. **Task 12 is not unblocked.**

---

## 2. Two arms, deliberately not one run

| | `--sweep` | `--transition N` |
|---|---|---|
| checks | VALUES (shadow band tops, deform shifts, the split) | COST (per-routine cycles, DMA queue bytes) |
| camera | MOVED — 18 written `Camera_Y` positions | FROZEN at the boot state |
| what is poked | `Camera_Y` and the overlay's arm word, nothing else | the three transition RAM fields |
| exit code | 5 on any derived-check failure | 5 on any derived-check failure |

They cannot be the same run. A cycle figure needs a frozen camera to mean one call — under
sustained motion one logic tick spans two video frames and a per-frame average stops being one
call (`WALKER-MODEL.md` §0(a), `ENGINE-BASELINE.md` §2). A re-glue check needs the camera to
move or it tests nothing. Keeping them apart is the only way to have both, and it is the same
split `parallax_hscroll_probe` draws between its frozen and sweep arms.

---

## 3. The derivation — ONE copy in the tree

The sweep does **not** carry its own transcription of Step 4a. It imports
`derive_shadow` and `resolve_anchor_line` from `tools/parallax_hscroll_probe.py`, which
already transcribe the rotation (`parallax.emp:687-770`) and the anchored split
(`:887-993`). A second copy would be a second thing to keep in sync with the walker, and the
first one to go stale would still print "ok".

What the sweep supplies per position, all read out of the running machine, never chained from
the previous position:

| input | source | why not derived |
|---|---|---|
| the config | `Parallax_Current_Config` → header + `band_count` entries | whichever one `Parallax_CheckBoundary` installed at this camera Y; naming a symbol would test a config the engine may not have chosen |
| `Vscroll_BG` | `Parallax_Current_Vscroll_BG`, read AFTER the frame | deriving it from `Camera_Y` would make the check agree with Step 5 by construction and stop testing Step 4a |
| `Parallax_Current_Scroll_A/B` | RAM | the pre-rotation scroll words `derive_shadow` reorders |
| the latched L | `Effects_Screen_L[ch]` | camera-dependent, latched by `Effects_LatchWorldLines` between `Camera_Update` and `Parallax_Update` |
| the patch record | `Raster_Patch_Tab` → count + entries | `Raster_GetChannelBand` clamps L into the channel's authored band; without it the split lands in the wrong place |

**The expectation is derived from the authored world-Y tops and the frame's own `Vscroll_BG`.
It is never chained from the previous position's readback** — a chained expectation drifts
with the thing it is checking.

### 3.1 The two-sided arm word

Shadow slot `band_count` is poisoned with `$FF` before the measured frame. Step 4a writes
exactly `band_count` entries; slot `band_count` is written by Step 4b's split and by nothing
else. So "the machine split this frame" is **read**, not inferred from the tops, and it must
agree with "the derivation resolved an anchor line". A disagreement in either direction is a
failure — which matters because the degenerate `L <= 0` split leaves the leading tops looking
untouched, so field equality alone cannot see it.

---

## 4. The sweep, and its red-first poison

### 4.1 Camera positions, derived not picked

Two groups.

* **Rotation coverage** — `camY = 512 + v*64` for `v` in `{0,4,8,12,20,28,36,40,44,48,52,56,60}`.
  `Vscroll_BG = ((camY - v_center) >> v_factor) + v_offset`, and the shipped OJZ configs use
  `v_center 512 / v_factor 3 / v_offset 0`, so this lands `vshift` exactly on plane cell row
  `v`. The OJZ tops are cells 0/8/40/48, so `k` takes all four of its values.
* **Overlay coverage** — `camY` in `{0, 64, 112, 160, 224}`. `Effects_World_Y[0]` is 224 in
  this act and the split line is `world_y - Camera_Y`, so these walk L across the whole screen.
  Without them every anchored row is the degenerate `L <= 0 -> split at line 0` case and the
  sweep never checks a mid-screen split at all.

Neither group is assumed: the vscroll and the latched L used by the expectation are read back,
so a different act still gets a correct expectation — it just gets less interesting coverage,
which the run's distinct-states tally reports.

### 4.2 Result — 18 positions x 3 boots, all exact

`python3 tools/parallax_cost_probe.py --sweep --repeat 3` · 40.0 s wall
(uptime 05:33:21 → 05:34:01, load 5.72 → 7.05) · **exit 0**

```
  camY      cfg  n  vscroll vshift  k  tf split  verdict
     0 $01230C  4    65472     56  3   0 False  ok — 4 bands exact
    64 $01230C  4    65480     57  3   0  True  ok — 5 bands exact, split at line 160
   112 $01230C  4    65486     57  3   0  True  ok — 5 bands exact, split at line 112
   160 $01230C  4    65492     58  3   0  True  ok — 5 bands exact, split at line 64
   224 $01230C  4    65500     59  3   0  True  ok — 5 bands exact, split at line 0
   512 $01230C  4        0      0  0   0  True  ok — 5 bands exact, split at line 0
   768 $01230C  4       32      4  0   0  True  ok — 5 bands exact, split at line 0
  1024 $01230C  4       64      8  1   0  True  ok — 5 bands exact, split at line 0
  1280 $01230C  4       96     12  1   0  True  ok — 5 bands exact, split at line 0
  1792 $01230C  4      160     20  1   0  True  ok — 5 bands exact, split at line 0
  2304 $0122C8  4      224     28  1   0 False  ok — 4 bands exact
  2816 $0122C8  4      288     36  1   0 False  ok — 4 bands exact
  3072 $0122C8  4      320     40  2   0 False  ok — 4 bands exact
  3328 $0122C8  4      352     44  2   0 False  ok — 4 bands exact
  3584 $0122C8  4      384     48  3   0 False  ok — 4 bands exact
  3840 $0122C8  4      416     52  3   0 False  ok — 4 bands exact
  4096 $0122C8  4      448     56  3   0 False  ok — 4 bands exact
  4352 $0122C8  4      480     60  3   0 False  ok — 4 bands exact

distinct (k, vshift) rotation states exercised: 16
distinct overlay split lines exercised: 4  [0, 64, 112, 160]
```

Two configs are exercised without being asked for — the camera crosses a section boundary and
`Parallax_CheckBoundary` swaps `ParallaxConfig_OJZ_Underwater` ($01230C, anchored) for
`ParallaxConfig_OJZ_Default` ($0122C8, not). The run waits 32 frames per position and REFUSES
any position where `Parallax_Transition_Frames` has not reached 0, because mid-transition the
ACTIVE config is `Target` and the one it read would be the wrong subject.

Two anti-vacuity checks are wired into the exit code, because every assertion above is
conditional on the sweep actually sweeping:

* fewer than two distinct `(k, vshift)` states = "an at-rest capture wearing a sweep's name";
* every anchored position resolving `L = 0` = the overlay's clamp-to-top early-out checked, and
  the mid-screen split — the part Task 7 moves — never checked.

### 4.3 The poison, run red-first

`--poison-vscroll 64` perturbs the `Vscroll_BG` fed to the EXPECTATION (one cell row less than
a full band step) between the read and the derivation. Today's Step 4a rebases plane-cell rows
to screen lines from `Vscroll_BG`, so if the checker is not really consuming it, this passes.

`python3 tools/parallax_cost_probe.py --sweep --repeat 1 --poison-vscroll 64` · **exit 5**,
**18 of 18 positions red**, each naming the first disagreeing band index:

```
  r0@0:    band 2 top: machine (128, 15, 15) != derived (224, 15, 15)  (tops machine [0, 64, 128, 224] vs derived [0, 64, 224, 224])
  r0@64:   band 2 top: machine (120, 15, 15) != derived (160, 15, 2)   (tops machine [0, 56, 120, 160, 224] vs derived [0, 56, 160, 224, 224])
  r0@112:  band 3 top: machine (120, 15, 2)  != derived (224, 15, 2)   (tops machine [0, 56, 112, 120, 224] vs derived [0, 56, 112, 224, 224])
  r0@160:  band 3 top: machine (112, 15, 2)  != derived (224, 15, 2)   (tops machine [0, 48, 64, 112, 224] vs derived [0, 48, 64, 224, 224])
  r0@224:  band 3 top: machine (104, 15, 2)  != derived (224, 15, 2)   (tops machine [0, 0, 40, 104, 224] vs derived [0, 0, 40, 224, 224])
  r0@512:  band 2 top: machine (64, 15, 2)   != derived (224, 15, 2)   (tops machine [0, 0, 64, 224, 224] vs derived [0, 0, 224, 224, 224])
  r0@1024: band 2 top: machine (224, 15, 2)  != derived (192, 15, 2)   (tops machine [0, 0, 224, 224, 224] vs derived [0, 0, 192, 224, 224])
  r0@2304: band 1 top: machine (96, 15, 15)  != derived (32, 15, 15)   (tops machine [0, 96, 160, 224] vs derived [0, 32, 96, 224])
  r0@3584: band 1 top: machine (128, 15, 15) != derived (64, 15, 15)   (tops machine [0, 128, 192, 224] vs derived [0, 64, 128, 224])
  … 18 rows, all red
```

The run's own control is the unpoisoned run above: same 18 positions, same ROM, exit 0. The
poison perturbs the SUBJECT'S INPUT and names a specific mismatch — it is not a gate asserting
that "something failed".

---

## 5. The transition frame

### 5.1 Method, and the spec correction it forced

The plan asks for "the two shipped configs that differ most in mode — one per-cell, one
per-line". **The tree cannot supply that pair.** All 20 shipped scenes attach at least one
H-deform table — several attach `DeformTable_Zero` precisely to force the flat-pathed per-line
pipeline — so the H bits of the reg `$0B` mode are `%11` for every config the game can install
and **no shipped pair differs in HScroll mode at all**. The mode axis that does vary is the
VScroll bit: `v_deform: Columns(...)` raises bit 2.

So the maximal shipped mode difference is `$3` vs `$7`, and that is the pair taken. The probe
derives both configs' mode bytes with `mode3()` (transcribed from `Parallax_Update`'s own
`.mode3_h_done`/`.mode3_shadow` arms) and **REFUSES a pair whose modes match**, so the claim
is checked at run time rather than trusted from prose.

| | config | addr | bands | anchor | mode |
|---|---|---|---|---|---|
| A | `ParallaxConfig_OJZ_Underwater` | $01230C | 4 | ch 0 | `%011` |
| B | `ParallaxConfig_Perspective_Dramatic` | $012B2E | 5 | none | `%111` |

Four cases per boot, each ONE field apart from its neighbour:

```
A stable      Current = A, Target = 0, Transition_Frames = 0      active A
B stable      Current = B, Target = 0, Transition_Frames = 0      active B
A->B trans    Current = A, Target = B, Transition_Frames = N      active B  (.use_target)
B->A trans    Current = B, Target = A, Transition_Frames = N      active A  (.use_target)
```

Every window is verified preemption-free (`Frame_Counter` == `Logic_Tick`, `Lag_Frame_Count`
delta 0) and re-taken until it is, and the state is read back afterwards: the config pointers
must not have moved, the counter must not have reached 0 inside the window, and the reg `$0B`
shadow byte must equal the ACTIVE config's derived mode.

### 5.2 Rows — N = 250, sample 31 frames, 5 boots

`python3 tools/parallax_cost_probe.py --transition 250 --repeat 5` · 87.7 s wall
(uptime 05:18:02 → 05:19:29, load 8.29 → 5.19) · **exit 0, no failed checks**

| case | active | `Parallax_Update` | spread | `Enqueue_Dirty_Buffers` | spread | reg $0B | queue @220 |
|---|---|---|---|---|---|---|---|
| A stable | $01230C | **13791** | 0 | 1374 | 0 | $3 | 3056 B |
| B stable | $012B2E | **13184** | 0 | 1374 | 0 | $7 | 3056 B |
| A→B trans | $012B2E | **14258** | 0 | 1376 | 0 | $7 | 3056 B |
| B→A trans | $01230C | **14685** | 0 | 1376 | 0 | $3 | 3056 B |

**Spread 0 across all five boots on every row.** Frames/ticks 31/31, lag 0, everywhere.

**The row is a DIFFERENCE, not a level.** "A transition frame costs 14258" is unfalsifiable on
its own — most of it is the walker doing what it always does. The surcharge is the transition
frame against the stable frame on the SAME active config, one field apart:

| surcharge | `Parallax_Update` | `Enqueue_Dirty_Buffers` |
|---|---|---|
| A→B trans − B stable (active B, 5 bands) | **+1074** | +2 |
| B→A trans − A stable (active A, 4 bands) | **+894** | +2 |

Both directions are reported because A and B differ in band count (4 vs 5) and in `v_factor`
(3 vs locked 15), so a single number would average two different mechanisms. The surcharge is
the `.use_target` routing plus the per-band Plane-B scroll lerp — a `divs.w` per enabled band
(`parallax.emp:640-651`) — plus, on A, the `Parallax_Step5_Vscroll` lerp its unlocked
`v_factor` enables.

### 5.3 Axes 2 and 3 — the DMA queue at scanline 220

Scanned with `engine_baseline_probe`'s own `_scan_dma` (imported, not re-typed): inside active
display, past every main-loop enqueue, before VBlank drains it.

**The queue is byte-for-byte identical in all four cases**, transition or not:

| slot | words | bytes | cmd |
|---|---|---|---|
| 0 | 16 | 32 | `C0000080` |
| 1 | 16 | 32 | `C0400080` |
| 2 | 12 | 24 | `78000082` |
| 3 | 448 | **896** | `7C000082` |
| 4 | 12 | 24 | `78000082` |
| 5 | 448 | **896** | `7C000082` |
| 8 | 576 | 1152 | `48000081` |

total **3056 B**, largest single DMA **1152 B**, slot cursors `[$804A, $80BA, $8162]`.

**So the transition frame's axis-2 and axis-3 cost is ZERO on this pair**, and the reason is
structural rather than lucky: both configs are per-line, so the "larger of the pair" HScroll
length is the same length, and `Enqueue_Dirty_Buffers` moves by +2 cycles. A pair that
differed in HScroll mode would move this row — and, per §5.1, **no such pair exists in the
shipped registry**, so a mode-differing HScroll length is unmeasurable in this tree today.
That is a boundary on the row, not a value for it.

**Observation for P3 Task 6, explicitly NOT a ruling here.** The scan reproduces correction
C1's discrepancy exactly: `buffers.emp:156-162` declares ONE `Static_Hscroll_Line` at
`dma_length(896)`, and the live queue holds **two** 448-word entries with the SAME command
word `7C000082` — plus a matching duplicated pair of 24-byte `78000082` entries. Task 6 Step 1
owns reconciling that; this is the raw evidence, taken on a different day and a different
build from the P2 scan that first saw it.

### 5.4 Controls run against this arm

| control | result |
|---|---|
| **N is not a confound.** `--transition 15 --sample 1` (real-transition divisors ~10, sample window one frame) | surcharge **+1074 / +894** — identical to N = 250 / sample 31. The synthesized N does not distort the row. |
| **A too-small N is caught, not averaged.** `--transition 60 --sample 31` | 4 settle + 31 burn + 31 window = 66 > 60, so the counter promoted mid-window. The readback check fired: *"the transition counter reached 0 inside the window — the row is part transition, part stable"* plus *"the config pointers moved (target $000000)"*, **exit 5**. A CLI guard now refuses `N <= 4 + 2*sample + 8` up front; the readback stays as the backstop for a retried window. |
| **A missing row is not a zero.** `--sample 1` | `Enqueue_Dirty_Buffers` does not appear in a 1-frame window. Reported as *"NOT measured, and not 0"* and it fails the run, rather than rendering as a 0 in a budget row. |

### 5.5 What a synthesized transition does NOT exercise

Stated so the row is not over-read:

* **`Parallax_StartTransition` and `Parallax_CheckBoundary` do not run.** A frozen camera
  suppresses them by construction. The staging cost (the `pcfg_transition` test, the mode
  shadow update, the same-config short-circuit) is not in any row here.
* **The reg `$0B` write is not in the window either.** `Parallax_Update` compares the derived
  mode against its shadow byte and writes the register only when they differ, so the mode
  change is paid ONCE — on the first frame after the install, four frames before the burn
  window starts. The shadow byte IS read back and checked against the ACTIVE config's derived
  mode, so the change is *witnessed* even though its cost is not measured.
* **The promote frame** (the one where the counter hits 0, `Target` moves into `Current` and
  `Target` is cleared) is deliberately outside every window — it is a different, one-off frame.
* **Every figure is an IDEAL-CYCLE figure.** The oracle 68000 core adds only `cyclesExecuted`
  to `_currentCycle` while bus/VDP/DMA stall lands in `_currentTime` (`WALKER-MODEL.md` §7).
  P3 does not fix that and this row does not claim to.

---

## 6. The ordering contract — recorded here so Task 7 does not rediscover it

**`Parallax_Update` tail-jumps `Parallax_Step5_Vscroll`, which tail-jumps
`Parallax_Step4_Fill`. Step 5 runs BEFORE Step 4.**

```
engine/level/parallax.emp:677-679          (tail of Parallax_Update)
        // NOTE: Step 5 (Vscroll) runs BEFORE Step 4 (HScroll fill) — the
        // band rotation in Step 4a needs this frame's Vscroll_BG.
        jbra    Parallax_Step5_Vscroll

engine/level/parallax.emp:1148-1149        (tail of Parallax_Step5_Vscroll)
    .v_done:
        jbra    Parallax_Step4_Fill         // Step 4 runs after Vscroll is final
```

The reason is the first instruction of Step 4a (`:698`): `move.w Parallax_Current_Vscroll_BG,
d0`, which is the rotation's whole input. Step 5 is the sole writer of that word (`.v_pack`).

**This instrument depends on the ordering too**, which is why it is recorded here rather than
only in the code: the sweep reads `Parallax_Current_Vscroll_BG` after the frame and uses it as
the expectation's input. That is the value Step 4a consumed *in the same frame* only because
Step 5 already ran. If Task 7's re-glue ever moves Step 4 ahead of Step 5, the sweep's
expectation silently becomes one frame stale — it would still be derived, and it would still
be wrong.

**Task 7 must preserve or re-derive this.** Re-glue changes what Step 4a computes, not what it
needs. If the new form genuinely does not need `Vscroll_BG` first, simplifying the ordering is
a separate, stated change with its own evidence — never a side effect — and this instrument
has to change with it.

---

## 7. Findings this task produced, beyond its own rows

1. **No shipped config is HScroll per-cell.** All 20 attach an H-deform table, so
   `mode3()`'s H bits are `%11` throughout. Any plan step that says "one per-cell, one
   per-line shipped config" cannot be executed as written. (§5.1)
2. **`parallax_hscroll_probe`'s frozen positions all land `k = 3`.** `Camera_Y` 144, 320 and
   96 give `vshift` 58, 61 and 57 against OJZ tops at cells 0/8/40/48 — one rotation state,
   three times. That tool's Stage A is a correct shadow-view check; it is not rotation
   coverage, and Task 7 needs rotation coverage. (§1)
3. **The C1 queue discrepancy reproduces.** Two 896-byte HScroll entries with the same command
   word, from one declared static. Task 6 Step 1's subject, re-observed on this build. (§5.3)
4. **The transition frame costs nothing in DMA bytes on the shipped registry** — and cannot be
   made to, because finding 1 removes the pair that would. (§5.3)
5. **`[parallax.cost_model]`'s per-line rows are STALE against master** — measured, not
   suspected. §8.

---

## 8. The model rows are stale against master — the clean-constant confound, arrived

This parcel touched no `Parallax_*` routine, so the standing rule's re-fit does not apply. The
default fit mode was re-run anyway, as a **regression check on the edited tool**:

`python3 tools/parallax_cost_probe.py --repeat 1` · 26 fixtures · spread 0 on every fixture ·
**zero failed derived checks, exit 0** · ~65 s wall on an otherwise-idle machine.

The tool is fine. The **rows it is compared against are not**. `[parallax.cost_model]`'s
`loop_shape` field says outright that its rows are a property of the PRE-UNROLL per-line filler
at master `08e87cbc`, and that the fill-unroll parcel re-measures rather than carries them.
**That parcel has landed** — `afccb141 perf(parallax): pointer-walk + unroll the single-channel
sampling loops` is in master's history since. The warning came true.

**The model's structure survived the unroll intact.** The un-anchored subset residual is still
**exactly 0.00** over the same 18 fixtures, and 7 of 11 un-anchored columns did not move at all.
What moved is exactly what the unroll was predicted to move — work out of the per-line body and
into the per-band prologue:

| column | pre-unroll `08e87cbc` | post-unroll `aab012a7` | |
|---|---|---|---|
| `base` / `band_percell` / `line_mode` / `band_perline` / `multiband` / `shift_lines` / `vdeform` | — | identical | no move |
| `line_fg_only` | 72.75 | **26.00** | −64% |
| `line_bg_only` | 72.81 | **26.90** | −63% |
| `line_both` | 125.21 | 124.53 | ~no move |
| `band_sampling` | 0.00 | **154.00** | 0 → the predicted class |
| `anchor` / `anchor_ops` | 982.2 / 59.27 | 985.6 / 61.65 | ~no move |

`band_sampling` going 0 → 154 is the clearest confirmation available: `WALKER-MODEL.md` §5(d)
predicted "a ~149-cycle class once the sampled loops are unrolled", from a different parcel, and
this is that number measured. A column that reads zero on one loop shape and 154 on another is a
real parameter with two regimes, and the regime is the loop shape.

| | pre-unroll | post-unroll |
|---|---|---|
| residual, un-anchored (18) | 0.00 | **0.00** |
| residual, all 26 | 13.3 | 43.2 |
| residual, overlay term (8) | 27.6 | 58.3 |
| out of sample | model 19915.3 / measured **20162** / +1.22% | model 13646.4 / measured **13798** / +1.10% |

**Why this matters here and not only to Task 13.** The shipped config now costs 13798, not
20162 — 31.6% cheaper. Without this recorded, §5's transition rows (13791 / 13184 / 14258 /
14685) read as if something were broken, because they would be compared against a model
measured on different code. They are not: this arm's `A stable` row (active
`ParallaxConfig_OJZ_Underwater`, **13791**) and the fit sweep's *untouched* out-of-sample row
for the same config (**13798**) agree to **7 cycles, 0.05%**, both spread 0, on the same ROM.
The 7 cycles are a frame-offset difference between the two runs' 31-frame windows, not a
disagreement.

**Booked, not promoted.** The post-unroll values are in `tools/effects_budget_model.toml` under
`postunroll_*`, beside a block naming the staleness. Task 1's rows are left intact — they are
the pre-unroll record that `loop_shape` exists to name, and overwriting them from an instrument
parcel would destroy it. **P3 Task 7's standing-rule re-fit and Task 13's re-take own the
promotion.** Until then, nothing should divide by the pre-unroll per-line columns: they
over-charge a sampled line by ~2.8x and would refuse a scene that demonstrably runs.

---

## 9. Reproducing

```bash
DEBUG=1 ./build.sh                                                   # s4.debug.bin + .lst

python3 tools/parallax_cost_probe.py --sweep --repeat 3              # exit 0
python3 tools/parallax_cost_probe.py --sweep --poison-vscroll 64     # exit 5, 18/18 red
python3 tools/parallax_cost_probe.py --transition 250 --repeat 5     # exit 0
python3 tools/parallax_cost_probe.py --transition 15 --sample 1      # the N control
```

The runner is the probe invoked by hand, as it is for the fit sweep; there is no CI lane for
it, because both arms boot a headless emulator per run and cannot live in `build.sh`. Rows are
booked in `tools/effects_budget_model.toml` under `[parallax.cost_model]`, marked SYNTHESIZED.
