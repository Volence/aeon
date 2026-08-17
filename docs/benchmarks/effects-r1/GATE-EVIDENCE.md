# Parcel R1 — gate evidence

All measurements on oracle (the only verification instrument — no real hardware exists for
this project). ROM identified by CRC per section.

---

## CLAIM 9 — the restore's `op_work_cyc` — MEASURED, CLOSED (2026-08-17)

**ROM:** `s4.debug.bin` crc=`04882b94` len=712732 (branch `feature/parcel-r1-palette-bands`
@ `25bad462` — encoder + constructor landed, guards not yet).

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
