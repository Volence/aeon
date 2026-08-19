# Instrument parity — Phase 0's reference row

**Parcel:** Scanline Services P2, Phase 0, Task 1.
**Instrument:** oracle (old), headless harness, per-routine profiler row.
**ROM:** `s4.debug.bin`, crc `d22dda85`, len 713295, built from `18af84f3` on branch
`measure/scanline-p2-phase0`.
**Run:** `python3 tools/raster_cost_probe.py --rom s4.debug.bin --lst s4.debug.lst --repeat 3`
**Wall clock:** started 2026-08-19T14:19:43-04:00 (`up 1 day, 14:43`, load 2.16), finished
14:21:36 (`up 1 day, 14:45`, load 6.04) — **113 s** for 3 boots x 11 fixtures. That figure is
the probe, not the panel: the build is a separate command and is not inside it.

---

## What this task actually is, today

The plan (Task 1) frames this as a check against a 2026-08-18 reference row: F1 412, F2 462,
F3 522, F4 570, F5 632, F6 622, F7 462, F8 708, F0 572.

**That row is historically true and superseded.** Seven byte-moving parcels landed on the
raster path between it and this run, and every one of them moved fixture costs by design. A
"divergence" against those numbers would be the parcels working, not the instrument drifting
— so comparing against them would be the copied-expectation defect this tree keeps getting
bitten by, wearing a regression check's clothes.

The check that IS meaningful today has three parts, and all three had to hold:

1. **Reproducibility.** 3 independent boots per fixture, spread 0 on every row.
2. **Model parity.** Measured marginal cost equals what the SHIPPED constants derive — the
   live `ensure` pins in `engine/effects/raster_dsl.emp`, which are the cost gate's own
   expectations. Derived here from source, not copied from any table.
3. **Provenance.** The parcel chain that separates this row from the 2026-08-18 one is named
   below, so a later reader can tell a superseded row from a broken one.

A gap between measured and model-derived would have been a STOP-and-report. There was none.

## The parcel provenance chain — why the 2026-08-18 row does not apply

Each of these moved the fixture costs, in commit order on `engine/effects/raster*.emp`:

| # | Parcel | Commit | Effect on the fixtures |
|---|---|---|---|
| 1 | the blanking spin becomes per-op program data (substrate item 1a) | `638c58c3` | every STREAM op +4 (a `move.w` read replacing a `moveq`); reg-only unmoved |
| 2 | the CRAM burst word is 26, not 30 (`-4(a2)` vs the absolute long) | `c44c80ad` | cram/vsram words -4 each; region/restore words held at 30 (F4/F8 are its controls) |
| 3 | item 1c — the spin is SOLVED FROM POSITION, not fitted per op class | `dfb5a6ad` | every stream fixture's spin re-solved; F5's spin overtook F3's for the identical op |
| 4 | Tier-3 item 2 — the op fetch's own Z flag IS the `OP_SET_REG` test | `0b1ad989` | a register write's dispatch 80 -> 10, so F1 -70; every other op +8 for the not-taken pre-test |
| 5 | the two `Raster_VBlank` tail calls (Tier 3 #5, raster half) | `74043ec9` | VBlank-side; matters here because it is on the same path the probe pokes |
| 6 | the frame-rewind interlock + `RASTER_PRIMING_GUARD_CYC` — charged to no-op records only | `aa139c75`, `c0fc195c`, `8d29797c` | F0 is two priming records, so the interlock lands on F0 and on nothing else |
| 7 | Tier-3 item 6 — the handler's SR save was work for `rte` to undo | `3c82c0b3` | -22 per fire on the base; `RASTER_HBLANK_END_CYC` 351 -> 371, so every burst waits +2 iterations (+20), netting -2 on stream shapes and the full -22 on reg-only and dense |
| 8 | re-derive the window anchor to 366, HOLD the cram ceiling at 3 | `faa8a35c` | no hardware change; the SOLVER's answer moved, re-rounding five of seven spins and holding two (F6, F8) |

Parcels 7 and 8 are why `RASTER_HBLANK_END_CYC` reads **366** here and why the fixture pins
were re-derived twice inside one day. Parcel 8 in particular changed no instruction: it moved
what the model aims at, which is exactly the class of change a measured-vs-model check has to
be able to see.

---

## THE PHASE-0 REFERENCE ROW (this is the one later tasks cite)

Per-routine row for the **HBlank trampoline `$FFB452`**, matched on the low 24 bits (oracle
prints `$FFFFB452`, the raw sign-extended 68000 PC; the listing spells it `$FFB452`, and the
row carries no symbol name, so neither the printed string nor the name matches).

30-frame sample per boot, 3 boots, **spread 0 on every fixture and every call count**.

### Raw totals — cycles/frame for the HInt row

| Fixture | n fires | calls | cycles/frame (3 boots) | spread |
|---|---|---|---|---|
| F0  | 0  | 2  | 588   | 0 |
| F1  | 6  | 8  | 2508  | 0 |
| F2  | 6  | 8  | 4332  | 0 |
| F3  | 5  | 7  | 3818  | 0 |
| F4  | 6  | 8  | 4584  | 0 |
| F5  | 4  | 6  | 3172  | 0 |
| F6  | 4  | 6  | 3340  | 0 |
| F7  | 6  | 8  | 4332  | 0 |
| F8  | 6  | 8  | 4632  | 0 |
| FD1 | 8 lines  | 13 | 4136  | 0 |
| FD2 | 40 lines | 45 | 14632 | 0 |

`calls` is a free correctness check, not decoration: a fixture that failed to install cannot
be silently measured. The dense pair's counts are DERIVED (`lines + 5`, the arm pipeline) and
both matched — 13 and 45.

### Marginal cost of one fire, `(fixture - F0) / n`, F0 = 588

| Fixture | shape | measured | model-derived | verdict |
|---|---|---|---|---|
| F1 | `reg_set` | **320.0** | 320 | match |
| F2 | `stream_cram` 1w | **624.0** | 624 | match |
| F3 | `stream_cram` 3w | **646.0** | 646 | match |
| F4 | `stream_pal_region` 3w | **666.0** | 666 | match |
| F5 | `reg_set` + `stream_cram` 3w | **646.0** | 646 | match |
| F6 | two `stream_cram` 1w in ONE fire | **688.0** | 688 | match |
| F7 | `stream_vsram` 1w | **624.0** | 624 | match |
| F8 | `pal_restore` 3w | **674.0** | 674 | match |

### The dense tier — a SLOPE, never a difference against F0

`(FD2 - FD1) / (40 - 8)` = `(14632 - 4136) / 32` = **328.0 cyc** per gradient line.
Model: `RASTER_DENSE_LINE_GRAD_CYC` = **328**. Match.

Read only as a pair. Neither leg alone is a dense cost — each carries the same
priming/setup/LEAVE overhead and the same fire base, and both use the same `top` so those
terms cancel exactly in the slope. Subtracting F0 (a sparse schedule) would fold the
setup difference into the per-line figure.

### F0 itself

F0 is the per-fire base's own anchor and cannot be spelled as a `fire` (a fire with no ops is
refused). Its pin is arithmetic on the measurement rather than an equality with it:

    RASTER_FIRE_BASE_CYC == (588 - 2 * RASTER_PRIMING_GUARD_CYC) / 2 + 16
                         == (588 - 60) / 2 + 16  ==  264 + 16  ==  280        ✓

Measured F0 = 588. Match.

---

## Where the model-derived column comes from

Not from any table in the plan and not from this file's own numbers. Each figure is the
value a LIVE `ensure` in `engine/effects/raster_dsl.emp` asserts about
`fire_cost_cycles(...)` for that exact fixture shape — the arithmetic that a build-time guard
divides by, so a drift here fails the build rather than this document:

```
ensure(fire_cost_cycles(fire(3, [reg_set($8C81)])) == 320, ...)                       F1
ensure(fire_cost_cycles(fire(3, [stream_cram($22, [0])])) == 624, ...)                F2
ensure(fire_cost_cycles(fire(3, [stream_cram($22, [0, 0, 0])])) == 646, ...)          F3
ensure(fire_cost_cycles(fire(3, [stream_pal_region($22, 0, 1, 1, 3)])) == 666, ...)   F4
ensure(fire_cost_cycles(fire(3, [reg_set($8C81), stream_cram($22, [0,0,0])])) == 646) F5
ensure(fire_cost_cycles(fire(3, [stream_cram($22,[0]), stream_cram($26,[0])])) == 688) F6
ensure(fire_cost_cycles(fire(3, [stream_vsram(2, [0])])) == 624, ...)                 F7
ensure(fire_cost_cycles(fire(3, [pal_restore($22, 3)])) == 674, ...)                  F8
pub const RASTER_DENSE_LINE_GRAD_CYC = 328                                            dense
pub const RASTER_FIRE_BASE_CYC       = 280                                            F0
```

## VERDICT

**All ten rows match, spread 0 across 3 boots.** This is the plan's first outcome ("the
instrument is stable"), restated against the current model rather than the superseded
2026-08-18 row: the instrument reproduces exactly, and the cost model the shipped `ensure`s
encode predicts every fixture to the cycle. **Phase 0 proceeds.**

Nine ROM-byte-moving parcels sit between the 2026-08-18 row and this one, and the model
tracked every one of them without a single re-fit. That is a stronger statement than the
plan asked for: it is not just that the instrument did not drift, it is that the model
follows the code.

---

## STANDING CAVEATS — carried into EVERY Phase-0 row

**1. `interrupts.hint` is HBlank PLUS VBlank on this ROM. It is NEVER a valid source.**

Oracle classifies an interrupt by the handler address the vector points at:

```
if (vec == 0x78 || (vec >= 0x70078 && vec <= 0x7FFFF)) vint += dur; else hint += dur;
        -- oracle linux-port/gui/ControlSocket.cpp, OpGetProfilerFrames
```

Aeon's `VBlank_Handler` is a ROM address that never matches, so BOTH handlers fall into the
`else` and `interrupts.hint` reads as neither. This is a silent wrong number, not a missing
one, which is why "per-routine rows keyed by entry address ONLY" is a rule and not a
preference. Address matching compares the **low 24 bits** — the sign-extension trap above.

**2. Absolute cycle claims keep ORACLE as the reference.**

oracle-next has no profiler instrument at all (confirmed with the oracle-next session
2026-08-18: none of its 31 bus methods is profiler-shaped). So every row this parcel
produces carries old-oracle provenance and will migrate when a profiler surface lands there.
**No row in this parcel may assert oracle-next cycle parity** while oracle-next's
instruction-granularity slop is open.

When that surface does land, its design is already pinned on their side: HInt and VInt as
separate buckets keyed by interrupt **cause**, never by handler-entry-PC matching, with
Aeon's finding cited as the measured counterexample. Task 1 becomes a genuine cross-instrument
parity check at that point. Until then it is oracle against itself, which is what this run is.
