# Parcel R1 — gate evidence

All measurements on oracle (the only verification instrument — no real hardware exists for
this project). ROM identified by CRC per section.

---

## CLAIM 9 — the restore's `op_work_cyc` — RE-DERIVED AND RE-CLOSED (2026-08-28, parcel P2a)

> **⚠ READ THIS BEFORE THE 2026-08-17 SECTION BELOW. That closure EXPIRED, silently, and the
> way it expired is the transferable lesson.** Nothing about it was wrong when it was
> written; it was anchored to an artifact — `s4.debug.bin` crc `04882b94`, a 712,732-byte
> ROM on a since-merged feature branch — and five substrate parcels then rebuilt the very
> handler it measured. The document kept saying CLOSED while every number in it went stale,
> because a benchmark file has no way to notice that its subject moved. **An
> artifact-anchored closure needs the artifact's identity in its own headline, and a
> re-check whenever that identity changes.** The 08-17 numbers below are kept verbatim as
> history; **not one of them may be subtracted from a present-day total.**

**What was owed, and it was not a measurement.** The eight F-series fixtures were
re-measured on 2026-08-28 against `s4.debug.bin` crc `fee02557` (3 boots, 30-frame samples,
load 4.69). Four of them had moved a long way from 08-17 — F0 572→588, F1 412→**320**, F5
628→**646**, F8 556→**674** — and **not in the same direction**, so the components had moved
relative to one another and no arithmetic could bridge the two revisions. What P2a owed was
therefore a **re-derivation of the constant from today's total against today's
decomposition**, which needs no emulator because the measurement was already taken.

**Today's eight measurements, and the shipped model against them.** Every component below is
read out of `engine/effects/raster_dsl.emp` at this revision. **No 2026-08-17 component
(302 fire base / 8 fetch / 82 dispatch / 90 stream / 10 tail) appears anywhere in it** — those
were derived at `RUNGS=5` on a ROM 22 KB shorter, and three of the five have since moved
(the fire base to 280, the dispatch to 90 via the zero pre-test).

| fixture | shape | measured 2026-08-28 | model | residual |
|---|---|---:|---:|---:|
| F0 | two priming records | 588 (absolute) | 588 | 0 |
| F1 | `reg_set` | 320.0 | 320 | 0 |
| F2 | `stream_cram` 1w | 624.0 | 624 | 0 |
| F3 | `stream_cram` 3w | 646.0 | 646 | 0 |
| F4 | `stream_pal_region` 3w | 666.0 | 666 | 0 |
| F5 | `reg_set` + `stream_cram` 3w | 646.0 | 646 | 0 |
| F6 | two 1-word crams, one fire | 688.0 | 688 | 0 |
| F7 | `stream_vsram` 1w | 624.0 | 624 | 0 |
| F8 | `pal_restore` 3w | **674.0** | **674** | **0** |

**The derivation, from F8 = 674 alone.** `op_cost_cycles` is
`RASTER_OP_FETCH_CYC + op_dispatch_cyc + op_work_cyc + op_stream_word_cyc × words +
RASTER_OP_TAIL_CYC`, and `fire_cost_cycles` adds `RASTER_FIRE_BASE_CYC` once:

```
674 = 280 (RASTER_FIRE_BASE_CYC)
    +   8 (RASTER_OP_FETCH_CYC)
    +  90 (dispatch: ZERO_MISS 8 + RUNG 16 × RASTER_DEPTH_RESTORE 4 + HIT 18)
    + WORK
    +  90 (RASTER_STREAM_WORD_DEEP_CYC 30 × 3 words)
    +  10 (RASTER_OP_TAIL_CYC)

WORK = 674 − 478 = 196
     = RASTER_WORK_RESTORE_BASE_CYC + spin_cyc(11)      spin_cyc(n) = 10n + 14
     = base + 124
base = 196 − 124 = 72
```

**`op_work_cyc(PalRestore, spin) = 72 + 10·spin + 14`; spinless base 72; 196 at the shipped
solved spin of 11.** That is the value in the tree — `RASTER_WORK_RESTORE_BASE_CYC = 72` —
so **the shipped model was already current and today's measurement confirms it with zero
residual on all eight fixtures.** The F-series `ensure`s pin model-against-literal on every
build; what they cannot do is pin model-against-hardware, and that is exactly what this run
supplies.

**Where each input to that arithmetic comes from, so none of it is borrowed:**

- `RASTER_FIRE_BASE_CYC = 280` — from **today's F0**: `(588 − 2×30)/2 + 16`, the two priming
  records less the frame-rewind interlock only they pay, plus the 16 a record with ops pays
  over a no-op one. That identity is a module-level `ensure` and is checked every build.
- `FETCH 8 + ZERO_HIT 10 + WORK_REG 12 + TAIL 10 = 40` — from **today's F1**: 320 − 280.
  F1 carries no delay site, so it is the one fixture with no spin term and no free parameter.
- dispatch 90 and the deep word 30 — instruction-level, from `Raster_HInt`'s own compare
  chain and `.restore_loop`, transcribed beside the constants in `raster_dsl.emp`.
- spin 11 — the **solver's** answer for this shape, and it is emitted DATA (the `SPIN` word
  in the op's wire body), not a fitted parameter.

**An independent cross-check that never names the restore's constant at all.** F8 and F4 are
the same shape — one leading op, three deep-stream words — differing only in dispatch depth
and work base:

```
F8 − F4 = 674 − 666 = 8
        = 3 × RUNG(16) + (W_RESTORE − W_REGION) + 10 × (11 − 15)
        = 48 + (W_RESTORE − W_REGION) − 40
  ⇒  W_RESTORE − W_REGION = 0
```

The restore's spinless work base **equals** the region's, exactly — which is what
`raster_dsl.emp` asserts in prose ("the restore body: region's shape, spinless base") and
what the two 72s say. Two of today's measurements, and not one borrowed constant.

**What could NOT be separated, stated rather than papered over.** Today's eight fixtures are
eight equations in roughly thirteen constants plus seven solved spins; the system is
underdetermined and **the F-series cannot split dispatch depth from work base on its own**
(the F8 − F4 identity above pins their *sum*, which is why it yields a difference and not two
values). That split is instruction-level evidence, not fixture evidence, and it is recorded
as such at each constant. Anyone re-deriving after a change to `Raster_HInt`'s prologue must
go back to the instruction list, not to this table.

**And a trap for the next person who reaches for the "obvious" slope.** The fixtures' raw
differences are **contaminated by the solver**, because each shape's spin is re-centred for
that shape:

| naive reading | value | what it actually is |
|---|---:|---|
| F3 − F2 as "per streamed word" | 22 / 2 = **11** | `2 × 26 − 10 × (22 − 19)` = 22. The true word is **26**; the spin fell 3 iterations. |
| F6 − F2 as "per extra op" | **64** | a whole 1-word cram op at spin 0 (124) less the first op's 6-iteration spin drop (60). |

Neither raw slope is a component of anything. Use the model and the solved spins, or use
F1/F0, which are the only two fixtures with no spin term in them.

**Status: CLOSED at `s4.debug.bin` crc `fee02557`.** Re-open it the next time a substrate
parcel touches `Raster_HInt`'s prologue, its dispatch chain, or `RASTER_HBLANK_END_CYC` — the
five edits since 08-17 each moved a fixture, and each one is documented in `raster_dsl.emp`'s
re-derivation chain.

**What P2a actually needed from this number — and it is less than the design claimed.**
Design §7.3 says "every band-height minimum in `band()` is cost-keyed to it (`:669, :704`)".
**That is wrong, and the source at those two lines is the refutation:** both minima call
`fire_cost_cycles` on the **ON** fire (`f_on`, `f_on_sh`), whose op is a `stream_cram` or
`stream_pal_region`. `op_work_cyc(PalRestore, …)` appears in neither. The restore's cost
enters `check_density` and `check_hint_total` instead — and both consume the **whole fire
total**, which today's F8 measures **directly at 674**. So the quantity N bands multiplies is
a measured fire total, not a decomposed constant, and the decomposition above is
corroboration rather than the load-bearing step.

---

## CLAIM 9 — the restore's `op_work_cyc` — MEASURED, CLOSED (2026-08-17) — **SUPERSEDED, see above**

**ROM:** `s4.debug.bin` crc=`04882b94` len=712732 (branch `feature/parcel-r1-palette-bands`
@ `25bad462` — encoder + constructor landed, guards not yet). **This ROM no longer exists in
any shipped shape; every figure in this section describes it and not the tree.**

**Command:**
```
python3 tools/raster_cost_probe.py --rom s4.debug.bin --lst s4.debug.lst \
  --only F0,F1,F5,F8 --repeat 3
```

**Result — 3 independent boots, spread 0 on every fixture:**

| fixture | n | marginal cyc/fire | model (RUNGS=5) | verdict |
|---|---|---:|---:|---|
| F0 (floor) | 0 | 572 (absolute) | 572 | exact |
| F1 (reg_set) | 6 | **412.0** | 412 | exact — the +16 rung tax is real |
| F5 (reg_set + cram3) | 5 | **628.0** | 628 | exact — mixed fire additive at 5 rungs |
| F8 (pal_restore 3w) | 6 | **556.0** | 556 | exact — **claim 9 closed** |

**Derivation check:** 556 − 302 (fire base) − 8 (fetch) − 82 (dispatch, depth 4) − 90
(3×30 stream) − 10 (tail) = **64** = the derived `RASTER_WORK_REGION_CYC(122) − delay
site(58)`. The derived constant IS the measured one; the sweep-5 correction (64, not v5's
68) is hardware-confirmed.

**Consequences applied:**
- `RASTER_WORK_RESTORE_CYC = 64` re-labelled MEASURED in `raster_dsl.emp`.
- F1/F5 measured-equality ensures re-labelled `measured 412` / `measured 628` (they were
  honest-DERIVED from Task 4 until this run).
- New F8 pin ensure added (556) — the pin that keeps the `band()` minima honest.
- `effects_gates.py` cost_model gate now runs `--only F0,F1,F3,F5,F8` with computed
  expectations (F5 = f0 + 5×fire_mixed — five fires, buffer cap; F8 = f0 + 6×fire_rest).
- **The §6.2 minima may now freeze** (the spec's ordering rule is satisfied): restore fire
  1w = 496 / 3w = 556; downstream gap ≥ 2 at every count stands on measured ground.

**Pin-provenance correction from Task 1 (recorded so it is not repeated):** the +0x100
game-RAM pin shifts were `@align(256)` padding on the leader-only ring, NOT "two-player
width" — pin rationales must state the mechanical source only.

---

## CLAIM 8 — snapshot VBlank cost — MEASURED, CLOSED (2026-08-17)

`Enqueue_Dirty_Buffers` IS a distinct per-routine profiler row (confirmed via `--dump`).
Same scene (OJZ, camera frozen at settle 180), branch ROM (`04882b94`, splices) vs a
baseline ROM built in a temporary worktree at `d0710868` (RAM added, splices absent).

| condition | baseline | branch | splice delta |
|---|---:|---:|---:|
| steady state (mask %0101, 2 dirty lines/frame) | 971 | 1318 | **+347** (~173.5/line) |
| forced worst case (`Palette_Dirty = $0F`, single frame) | 1400 | 2104 | **+704 — the derived figure EXACTLY** |

- The estimate (~176/line, ~704 worst) is confirmed: 704/4 = 176.0/line on the clean
  4-line measurement; the steady-state 347 vs 352 sits inside per-path `lea`-form variance.
- Window headroom: the worst forced frame's `VBlank_Handler` row reads 10,028 cyc against
  the ≈18,565-cyc NTSC blanking window — the +704 is 3.8% of the window and end-of-window
  overrun is nowhere near (≈8.5k cyc of slack on the heaviest frame measured).
- `VInt_Level`'s self-time row is identical (5328) on both ROMs — the cost lives entirely
  in the `Enqueue_Dirty_Buffers` row, as placed.
- **Z80 DRAIN scope (Task 2 review I3): derivation only, booked.** 704 cyc ≈ 92 µs at
  7.67 MHz of additional ring-only DAC coverage (sound-ON) / held bus (sound-OFF) inside
  the `SND_CTRL_DMA_ACTIVE` bracket. No automated Z80-side instrument exists; an audible
  soak on the sound-ON shape is booked with the Task 13 capture session's notes.

## §7.3 measurement 1 — the restore's landing — CLEAN, CALIBRATED (2026-08-17)

The first datum at this fire shape, ever. Fixture: `band`-shaped program poked into
`Raster_Buf_A` on the GUI oracle (pokes must happen PAUSED — a running emulator's
per-VBlank schedule re-record races the pokes and rewrites the buffer; one capture was
lost to this before the pause discipline was adopted). Camera frozen at spawn
(Camera_Y=144), tint `$0E0E`×3 on line 2 entries 4-6 ($48 — entries the trunk art
heavily uses; line 1 entries 1-3 were tried first and are nearly unused at those rows,
the P1-CORRECTION trap in the flesh). Per-row magenta-pixel analysis of the PNG.

**Zero delay (the bracket start):** the burst completed at **x≈180 of row 139** — the row
ABOVE the authored OFF edge (140): row 139's tint cut off at x=180, rows 140+ fully base.
The bare single-op cram ON fire spilled identically (row 99 tinted from x≈170) —
**sweep 4's anchor finding confirmed comprehensively: every single-op fire lands
mid-previous-row; the calibrated evidence only ever covered the mixed shape.** The
measured restore-vs-cram offset (~10 px ≈ 8 cyc) matched the pinned model's +6 within
2 cyc — the dispatch/delay model is pixel-accurate.

**The jump:** the clean mixed shape carries ~152 cyc of pre-burst delay (SetReg 94 +
spin 58); `EFX_RESTORE_DELAY = 13` gives 4+130+14 = 148. **Verified clean in one step:**
row 139 fully tinted to x=311 (same extent as 137/138), rows 140+ fully base. The OFF
edge sits exactly on the authored line.

**Model consequence applied:** the calibrated body's work = 64 + 148 = **212**
(`RASTER_WORK_RESTORE_CYC` updated; F8 expectation 556 → **704**; TOML mirror synced;
re-measure confirmation in the post-calibration gate run below). The restore fire at
704 cyc still needs downstream gap ≥ 2 (704 ≤ 976) — the §6.2 tables hold.

Captures: `band_capture3.png` (zero delay), `band_capture4.png` (calibrated), scratchpad;
per-row tables in this file's history.

## §7.3 measurement 2 — the +16 mixed-fire landing — ATTEMPTED: METHOD-CONFOUNDED, **NO VERDICT** (2026-08-17, Fable-ruled)

**What IS hardware-confirmed: the tax itself.** F5 measures 628.0/fire (3 boots, spread
0) — exactly the 5-rung model. Only the pixel-landing CONSEQUENCE is unmeasured.

**Why no verdict exists:**
- The P2 baseline rows (118-120) are camera-stale — at the current spawn the ch-0
  boundary latches at screen row 80 (`Effects_Screen_L` = $50); no recorded row
  corresponds.
- The cross-ROM differential (pre-tax `82b10ffa` ROM vs current, both at the frozen
  spawn) **failed its own negative control**: 116 differing rows INCLUDING rows 5-20,
  which carry no raster ops — the boots sit at different `Logic_Tick` phases and
  BgAnim/HUD animation dominates. Boundary-region diffs (11-59 px/row, rows 79-86) are
  inside that noise band; the sought ~14-15 px seam drift is unresolvable. **This is the
  FOURTH capture protocol to fail its own control** — preserved here as the
  control-failure record for the next protocol designer.
- `Logic_Tick` phase alignment is infeasible unthrottled: the emulator ran at 86-220
  ticks/s of wall time across sleeps; exact-tick landing needs ~200 MCP round-trip
  frame-steps per ROM against a press-wedge-prone socket.

**The bound (what tonight DOES exclude):** the catastrophic failure form only. The S/H
seam exists at row 80 on the current ROM, the arm-word scene gates pass, and no gross
artifact (a visibly dry row below the boundary) appears in any capture. **Resolution of
this bound: the 11-59 px/row animation noise floor — the ≤15 px precision question is
fully open.**

**Disposition (Fable ruling, 2026-08-17, owner-delegated):** spec §7.3 classifies the
captures as "evidence, not gates"; the §3.3 fallback slot activates only on a MEASURED
failure and none is evidenced — the instrument failed, not the parcel. Merge proceeds;
`EFX_BLANK_DELAY` untouched; the fallback slot stays VACANT; the precision re-measure is
booked concretely in `docs/DEFERRED_WORK.md` against the render-anchoring parcel (framediff
at pinned camera, Logic_Tick controlled or anchored out, boundary re-derived at the
capture camera — the P2 rows must not be reused). Sweep 5's corrected arithmetic (last
word ~90 of ~97 window-cycles) is context, NOT a conclusion.

## Boot evidence log

- Task 1 ROM (`f1a8d28d`): boots to OJZ on oracle, frame 928, PC in `VInt_Level`. 2026-08-16.
- Task 2 ROM (`f9e38b9f`): boots; `Palette_Ship_Snap` read live == `Palette_Buffer`
  byte-identical across all 128 bytes at frame ~101835 (splices live). 2026-08-16.
- Task 3-5 ROM (`04882b94`): boots; OJZ scene + HUD render normally with the live raster
  program; opcode body dead as designed. 2026-08-17.
