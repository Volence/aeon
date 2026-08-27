# World-Y re-glue — what changed, what it cost, and what it does not do

**Parcel:** Scanline P3, Phase 1, Task 7 (`docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`)
**Branch:** `p3/t7-worldy-reglue`
**Acceptance harness:** Task 3's instrument, `tools/parallax_cost_probe.py --sweep` — see
`REGLUE-INSTRUMENT.md` beside this file. `ab_runner` cannot substitute: its four committed
scenes poke `Debug_Scene_Freeze = 1`, so a re-glue that is wrong under motion is invisible
to them by construction.

---

## 1. The defect, stated as a number

Before this parcel, Step 4a computed

```
vshift = (Vscroll_BG mod 512) >> 3          // PLANE CELLS
screen_cell = band_top_cell - vshift
band_top_line = screen_cell << 3
```

`Vscroll_BG & 7` was discarded. Every band top therefore landed on an 8-px cell edge, and
as the BG scrolled a top **sat still for eight lines and then jumped eight**, while the art
under it moved one line at a time. A layer boundary is supposed to be glued to that art.

The poison run below measures the correction directly, at `Camera_Y = 112` on
`ParallaxConfig_OJZ_Underwater`, where `Vscroll_BG = 65486` → `& $1FF` = 462:

| | shadow tops read out of the machine |
|---|---|
| before (`REGLUE-INSTRUMENT.md` §4.3) | `[0, 56, 112, 120, 224]` |
| after (this parcel) | `[0, 50, 112, 114, 224]` |

`462 >> 3 = 57`, `57 * 8 = 456`, and `462 - 456 = 6`. **The two tops that are not pinned by
the anchor moved by exactly 6 lines** — the discarded remainder, now carried. 50 and 114
are not multiples of 8, which is the whole point: those positions were previously
unreachable.

## 2. What the references actually do (Task 7 Step 3)

Three sources, three questions, no ritual sweep.

**S.C.E. `ApplyDeformation`** — `Sonic-Clean-Engine-S.C.E.-/Engine/Core/Deformation Script.asm:150-267`.
Seeds `d0` from `Camera_Y_pos_BG_copy` read `.w` (the integer-pixel high word of a `.l`),
then walks a table of **band HEIGHTS in scanlines** (`sub.w d2,d0 / bmi.s .block_visible`).
It carries the partial offset **twice, from the same register**:

```
add.w   d0,d2            ; d2 = height + (negative remainder) = lines consumed INTO this band
add.w   d2,d2            ; -> per-line scroll-word index for a "linear" band
...
neg.w   d0               ; d0 = lines of this band still on screen = the first run's length
```

Dropping either is the classic one-line-off port defect. The shipped table
(`Levels/DEZ/Events/DEZ1 - Events.asm:77`) is `dcb.w 15, 16` + `$7FFF` — pixels, not cells.

**S2 MCZ** — `s2disasm/s2.asm:16411` (`SwScrl_MCZ`), heights at `:16585`
(`SwScrl_MCZ_RowHeights`, 24 `dc.b` entries, **units scanlines**, summing to exactly 512 =
the Plane-B span the BG wraps in — the same modulus this engine uses). Seeds from
`Camera_BG_Y_pos` directly (`:16548`), walks `sub.w d0,d1 / bcc.s .segmentLoop`, and carries
the partial offset as `neg.w d1` — one place rather than two, because MCZ has one scroll
value per row instead of per line.

**So both Sonic-lineage references walk in SCANLINES. The 8-px cell quantisation was ours
alone**, and removing it is a return to the reference behaviour, not a novelty.

**Thunder Force IV** — checked for the arithmetic alternative and it does **not** supply one.
Its bands are **screen-anchored, not world-anchored**: `$FFFF9718` holds 64 per-band scroll
accumulators, cleared once at init (`thunderforce4_disasm/code/disasm.asm:484-513`), and each
builder emits a fixed number of unrolled `move.l d0,(a0)+` per band (e.g. `$004F52`,
`disasm.asm:4970-4986`: 64 flat lines then 32 bands of 4 lines each, with the per-band rate
ramped arithmetically as `add.w d3,d2` — no table, no search, no remainder). Band *k* owns
the same scanlines forever, so "which band is at the top of the screen" is a compile-time
constant and the seek never exists. That is not portable to a walker whose bands are glued to
a scrolling world.

The even-spacing collapse (`band = camY >> log2(spacing)`, `partial = camY & (spacing-1)`)
is available in principle and **is not taken here**, for a reason that is measurable rather
than stylistic: OJZ's bands are not evenly spaced. `ParallaxConfig_OJZ_Default`'s plane lines
are 0 / 64 / 320 / 384 — gaps of 64, 256, 64, 128. A comptime "evenly spaced" predicate would
select a second code path that **no shipped scene satisfies**, which is the vacuous-
specialisation shape this suite keeps rediscovering. The search is at most 7 word compares,
once per frame.

*(TF4 caveat, carried from the research: the bundled `ANALYSIS.md` mis-addresses in places —
its layer table is at `$FFFF8198`, not `$8000`, and its "factor = -(layer*2-7), range -7..+7"
omits a `subq.w #2` / `addq.w #1` pair, so the real factors are -8,-6,-4,-2,+2,+4,+6,+8.
Everything cited above was re-verified against the raw disassembly.)*

## 3. What actually changed

### 3.1 The record — RESHAPED, NOT RESIZED

`band_entry` is still **10 bytes**, so `BAND_ENTRY_LEN`, `Parallax_Shadow_Bands` (80 B) and
the axis-6 RAM row **do not move**. The arithmetic:

```
band_top      u8 -> u16   (+1)   a PLANE LINE is 0..511 and does not fit a byte
band_factor_a_op + band_factor_b_op -> band_factor_ops   (-1)   two 1-bit flags, one byte
```

The op packing is not a tidy-up riding along — it is what pays for the wider top.
`Decode_Factor_A/B` read it with `btst #0` / `btst #1`, the same cost as the two `tst.b`s.

Keeping the size fixed also keeps **Task 8's blast radius intact**: correction C5 assigns the
`BAND_ENTRY_LEN` move, the `extern("band_entry_len")` pin (EMP_PITFALLS §5) and the axis-6
RAM row to the extended-record parcel. None of them are touched here.

### 3.2 The authored coordinate — ACT SPACE

`layer(world_y:)` is an **act** Y now. `scene_plane_line()` (engine/level/scene_dsl.emp) maps
it to a plane line at **comptime**, through the scene's own vertical mapping — the same one
`Parallax_Step5_Vscroll` applies to the camera:

```
plane_line = ((world_y - v_center) >> v_factor) + v_offset       // v_factor < 15
plane_line = world_y                                             // v_factor == 15, locked
```

Folding it at comptime is deliberate: `v_factor`/`v_center`/`v_offset` are scene constants, so
a runtime mapping would recompute an invariant up to eight times a frame to reach the same
number.

**The locked arm carries the shipped registry, not a corner.** Eighteen of the twenty shipped
scenes are `v_factor: 15` — a locked BG plane ignores the camera, `Vscroll_BG` is pinned at
`v_offset`, and there is no act→plane relation to invert (`(wy - v_center) >> 15` is 0 or −1
for every `wy`, which would collapse every layer onto one line). For a locked plane the
authoring space *is* the plane, so the mapping is the identity and those eighteen scenes'
tops (0/32/80/112/160) are unchanged numbers meaning unchanged rows.

The two unlocked scenes (`OJZ_Default`, `OJZ_Underwater`: `v_factor 3 / v_center 512 /
v_offset 0`) changed their authored numbers and **not their bands**: plane lines
0/64/320/384 are the images of act Y **512/1024/3072/3584**.

**A coordinate-space caveat that is easy to get wrong.** `Effects_LatchWorldLines` maps the
anchor bank's act Y to a screen line as `world_y - Camera_Y`, 1:1, because a patch anchor is a
LEVEL feature at the camera's own depth. A static layer top is a feature of the BG ART, at the
BG plane's depth. **Two things authored in the same space land on different screen lines, and
that is parallax, not an inconsistency.** They coincide only at `v_factor 0 / v_center 0 /
v_offset 0`.

### 3.3 The two guards — RELAXED, NOT REMOVED

| was | is | where |
|---|---|---|
| `ensure(world_y % 8 == 0)` | gone — an off-grid top is representable, and `scene_forces_per_line()` **arm 5** forces the per-line pipeline instead | `scene_dsl.emp`, arm 5 |
| `ensure(world_y >= 0 && world_y < 512)` (the BG PLANE's span) | `world_y < $8000` in `layer()` (the engine act-axis ceiling every act descriptor asserts) **plus** `world_y < act_span` at the registry fold | `layer()` + `assert_act_relative_tagged(scenes, act_span)` |

The act span is **derived, not typed**: `scene_registry.emp` declares `SCENE_ACT_SPAN_Y` and
`act_descriptor.emp` pins it to `GRID_H << SECTION_SIZE_SHIFT` (6144). The mirror direction is
forced — `act_descriptor` already imports `scene_registry`, so importing back would be a cycle
— and it is the same two-species-of-pin discipline as `PARALLAX_STATE_LONGS`.

**The off-grid ↔ forcer coupling is proven red, not asserted.** `poison_scene_grid.emp` changed
subject with the guard it used to target: it is now a two-fixture differential (`world_y 4` vs
`world_y 8`, both `v_factor 15` so the plane image is the authored value) whose on-grid control
must stay green and whose off-grid half must fail with *"forced the per-line pipeline"*.
`tools/emp_expect_fail.py` case count stays 1.

**Arm 5 asks the PLANE image, not the act value**, and that is a correction Task 7 forced. The
fill quantises plane lines; with `v_factor 3` a 64-px act step is one plane cell, so testing the
act value would both over-force (a top dead on a cell edge) and under-force (an act value that
is a multiple of 8 whose plane image is not, e.g. `v_offset 4`).

### 3.4 Ordering — UNCHANGED, and re-derived rather than assumed

`Parallax_Update` still tail-jumps `Parallax_Step5_Vscroll`, which still tail-jumps
`Parallax_Step4_Fill`. **Step 5 before Step 4.** Re-glue changed what Step 4a computes, not
what it needs: its first instruction is still `move.w Parallax_Current_Vscroll_BG, d0` and
Step 5 is still that word's sole writer. The `--poison-vscroll` control below is the runtime
evidence that the dependency is real — poisoning `Vscroll_BG` reddens all 18 positions, which
it could not do if Step 4a had stopped consuming it. **No ordering change was made, so none
had to be argued.**

### 3.5 Capacity — UNCHANGED *by this parcel* (superseded 2026-08-27)

`MAX_PARALLAX_BANDS` stays **8** (≤7 authored when anchored). Step 4a stays **copy-all**.
World-Y bought anchoring and vertical gluing, not layer count. Windowed re-glue over >8
declared layers remains a §9 future with its own re-derivation.

> **AMENDMENT 2026-08-27.** The ceiling is **16** now, raised by
> `parcel/band-ceiling-16-impl` — `pcfg_layer_mask` widened to a `u16` and
> `parallax_config` to 30 bytes. This section's "stays 8" was a statement about what THIS
> parcel changed, and it remains true of this parcel; it is no longer true of the tree.
> The live numbers and the full derivation are in `docs/DEFERRED_WORK.md`'s
> "`MAX_PARALLAX_BANDS` 8 -> 16 — LANDED" row and `docs/ENGINE_ARCHITECTURE.md`'s "Band
> ceiling" paragraph. Step 4a is still copy-all, and "copy-all" still means all LIVE
> bands — which is why the raise cost an unchanged scene zero per-frame cycles.

---

## 4. Evidence

### 4.1 The sweep — 18 positions × 3 boots, all exact

`python3 tools/parallax_cost_probe.py --sweep --repeat 3` · 39 s wall
(uptime 09:08:21 → 09:09:00, load 1.53 → 3.76) · **exit 0**

```
ALL POSITIONS AGREE with the derived Step-4a rotation.
distinct (k, vshift) rotation states exercised: 16
  [(0,0) (0,4) (1,8) (1,12) (1,20) (1,28) (1,36) (2,40) (2,44)
   (3,48) (3,52) (3,56) (3,57) (3,58) (3,59) (3,60)]
distinct overlay split lines exercised: 4  [0, 64, 112, 160]
```

Both anti-vacuity checks are live: fewer than two rotation states, or every anchored position
resolving `L = 0`, fails the run. Two configs are exercised without being asked for — the
camera crosses a section boundary and `Parallax_CheckBoundary` swaps
`ParallaxConfig_OJZ_Underwater` ($01230C, anchored) for `ParallaxConfig_OJZ_Default` ($0122C8).

### 4.2 The poison, run against this build

`python3 tools/parallax_cost_probe.py --sweep --repeat 1 --poison-vscroll 64` · 13 s wall
(uptime 09:09:25 → 09:09:38) · **exit 5**, **18 of 18 positions red**, each naming the first
disagreeing band index. Its control is §4.1: same 18 positions, same ROM, exit 0.

### 4.3 The derivation's own unit test, proven red first

`tools/test_parallax_hscroll_probe.py::test_the_partial_offset_survives_p3_re_glue` asserts
that three `Vscroll_BG` values one line apart give three tops one line apart:

```
re-glue (line precision):      [48, 47, 46]
pre-re-glue (cell quantised):  [48, 48, 48]   -> the test FAILS against the old form
```

The control was run by re-invoking the same `derive_shadow` with `vs` rounded down to a cell
edge, which is exactly what the removed `>> 3` did.

### 4.4 Byte accounting — all four shapes

| shape | before | after | len |
|---|---|---|---|
| `s4.bin` | `fa881cad` | `445092a7` | 699108 (unchanged) |
| `s4.debug.bin` | `58b5cfde` | `d7b36f90` | 715010 (unchanged) |
| `demo.bin` | `44289321` | `9320c210` | 96336 (unchanged) |
| `demo.debug.bin` | `5f075958` | `2ef6bf83` | 101044 (unchanged) |

All four move — expected, and demo moves for a real reason rather than the deb2-label one:
Step 4a and `Decode_Factor_A/B` are not capability-gated, so demo carries the same edits.
Lengths are unchanged because the placer fill absorbed the deltas, which is precisely why
`demo_specialization_witness.py` asserts per-proc pins and never a region byte count.

**The witness pin moved and was RE-DERIVED, not edited to match.** One proc:
`Parallax_Step4_Fill`, demo 176 → **170** (−6), sonic4 536 → **528** (−8). Derived instruction
by instruction before the number was touched (the full ledger is in the tool's re-derivation
log): Step 4a contributes −2 `lsr.w #3`, −2 and −2 for two `moveq #0` zero-extends the widened
`move.w` reads no longer need, +2 for `moveq #28` → `move.w #224`, −2 `lsl.w #3` = **−6**; the
anchored overlay adds −2 for a third `moveq #0` = **−8** on sonic4. The four field accesses
that changed width (`move.b` ↔ `move.w` at offsets 0 and −10) are the same size and contribute
nothing. The other seven pinned rows are unchanged.

### 4.5 The cost model — re-fit, and `multiband` re-measured rather than retired

`python3 tools/parallax_cost_probe.py --repeat 1` · 26 fixtures · **spread 0 on every
fixture, exit 0** · run alone, ~2 min wall on a machine at load 7–9 (uptime 09:27:56 →
09:29:5x — **not an idle-machine figure**; a concurrent session was busy). Every window is
verified preemption-free (frames/ticks 31/31, lag 0 on all 26), so the cycle rows are
unaffected by that load even though the wall clock is.

**The baseline is `postunroll_*`, not the older committed rows** — those are stale by the
fill-unroll parcel, as `REGLUE-INSTRUMENT.md` §8 records. Booked under `reglue_*` in
`tools/effects_budget_model.toml`.

**The un-anchored subset residual is still EXACTLY 0.00 over the same 18 fixtures.** Four
columns moved and every one derives to the instruction:

| column | postunroll | reglue | Δ | derivation |
|---|---|---|---|---|
| `base` | 3144.00 | **3116.00** | −28 | Step 4a per call: `lsr.w #3, d0` deleted (−12) + the single copy-loop iteration's `moveq #0, d3` (−4) and `lsl.w #3, d3` (−12). W0 *is* `base` (1 band, per-cell). |
| `band_percell` | 772.00 | **752.00** | −20 | copy-loop −16, plus `Parallax_Fill_PerCell`'s `.next_band` `moveq #0, d4` (−4) — the widened `move.w` needs no zero-extend |
| `band_perline` | 874.00 | **854.00** | −20 | copy-loop −16, plus `Parallax_Fill_PerLine`'s `.have_end` `moveq #0, d5` (−4) |
| `multiband` | 24.00 | **20.00** | −4 | `.find_k`'s body `moveq #0, d3` |
| `anchor` | 985.6 | 981.4 | −4.2 | Step 4b's `.anchor_find_k` `moveq #0, d2`, once per call — inside the term's own residual band, so consistent rather than a second measurement |
| `anchor_ops` | 61.65 | 60.77 | −0.88 | ditto |
| `line_mode`, `line_fg_only`, `line_bg_only`, `line_both`, `shift_lines`, `band_sampling`, `vdeform` | — | unchanged | 0 | all seven |

**`multiband` is RE-MEASURED at 20.00, not retired.** The plan asked for that verdict
explicitly ("if the new form has no once-at-two-bands cost, REMOVE the indicator column").
It has one: the new Step 4a still seeks, because the even-spacing arithmetic collapse was
declined (§2). Every fixture has `k = 0`, so `.find_k`'s body runs **exactly once** — the
column *is* that one `moveq`, and the −4 is its cost. The indicator keeps its subject.

| residual | postunroll | reglue |
|---|---|---|
| un-anchored subset (18) | 0.00 | **0.00** |
| all 26 fixtures | 43.2 | 43.6 |
| overlay term (8) | 58.3 | 58.9 |
| out of sample | model 13646.4 / measured 13798 / **+1.10%** | model 13542.7 / measured 13834 / **+2.11%** |

**The out-of-sample gap grew and the measured value rose by 36 cycles while every column
got cheaper — say why rather than let it read as a regression.** The shipped config's
**band geometry moved**: its shadow tops are now `0/46/80/110/224` where they were
`0/48/80/112/224`. That is the partial offset, which is the point of the parcel, so the
band spans — and therefore the per-line work composition — are not the same work as before.
Same walker, different bands. The gap is also dominated by the anchored overlay term, whose
own residual is ±58.9 over 8 fixtures, and the shipped config is anchored.

**One instrument defect was found by this run and fixed before the rows were taken**, which
is worth recording because all three of its faces looked like an engine bug or a pass:
three readers of the band top were still byte-wide against a now-16-bit field
(`parallax_cost_probe.py`'s fixture-arm hex parse, the same parse in
`parallax_hscroll_identity.py`, and `parallax_hscroll_probe.py`'s `stage_a` comparing the
top against `want & 0xFF`). The first made every shadow top read as its always-zero high
byte, so anchored fixtures reported "shadow tops IDENTICAL — no split" and un-anchored ones
reported "slot band_count was WRITTEN": twelve fixtures refused for a defect in the reader.
The `--sweep` arm was already correct because it goes through `be_top`, which is why §4.1
and §4.2 were green before this surfaced.

### 4.6 Lanes

* `python3 -m pytest tools/ -q` → **1180 passed, 3 skipped, 0 failed** (with
  `AEON_SKDISASM_DIR` exported; without it 9 tests fail on a missing donor tree, which is an
  environment fault and not a code one).
* `tools/emp_expect_fail.py` → **20/20**, via `./build.sh` (the lane is part of the canonical
  build). `poison_scene_proof.emp`'s fixture top moved `0` → `512` for the same act-space
  reason as the shipped scenes; a `world_y: 0` against its `v_center: 512` now sits above the
  plane's reach and would have added two diagnostics the lane's count check cannot separate
  from the planted one.
* `tools/demo_specialization_witness.py` → **OK** after the re-derivation.
* `python3 tools/effects_gates.py --rom s4.debug.bin --lst s4.debug.lst` → **24 of 25 gates
  PASS**, exit 1, 12 segments (11 emulator-backed), 09:32:54 → 09:36:58 on a machine at load
  6–8. The one FAIL is `cost_model vs hardware`, and it is an **emulator stop-race, not an
  assertion**: `aether.BusError: [-32010] reset: timeout waiting for main-thread drain`, with
  no measured value reported. Re-run alone —
  `--only cost_model`, 26 s wall (09:37:27 → 09:37:53), **exit 0, 2 gates PASS**:
  `F0=588 F1=2508 F3=3818 F4=4584 F5=3172 F8=4632` all matching, and the dense row at
  316.0 cyc/line. That segment is the raster cost model (`raster_cost_probe`), which this
  parcel does not touch — it boots six fixtures and carries the lane's widest timeout for
  exactly this reason.

### 4.7 Re-verified on the final committed tree

Every figure above was taken against `s4.debug.bin crc=d7b36f90`. After the last two
commits (comment corrections plus removing the registry fold's redundant
`scene_plane_line` call) all four shapes were rebuilt canonically and **all four CRCs are
identical to the ones the sweep and the fit measured** — so those later commits are
byte-neutral and the evidence stands against the tree as committed. The sweep was re-run
once more on that build (`--sweep --repeat 1`, 13 s, 09:41:06 → 09:41:19): **exit 0, 16
rotation states, 4 split lines, all positions agree.** `emp_expect_fail: OK — 20/20`,
`s4lint: no issues`, `effects_budget_check: OK — 31 code-derived rows agree`, pytest
**1180 passed / 3 skipped**.
