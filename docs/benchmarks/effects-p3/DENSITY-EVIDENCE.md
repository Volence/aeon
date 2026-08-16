# DENSITY EVIDENCE — what a raster fire costs

**Rig:** `tools/raster_cost_probe.py` · **ROM:** `s4.debug.bin` · **Emulator:** oracle (headless,
`ORACLE_DETERMINISTIC=1`) · **Date:** 2026-08-16

This file was cited by `engine/effects/raster_dsl.emp`, `docs/EFFECTS_AUTHORING.md`,
`tools/effects_budget_model.toml` and the crown roadmap for two parcels before it existed. It exists
now, and the numbers in it are not the ones those citations were carrying.

---

## The instrument, and the one thing you must not do with it

Oracle's profiler reports `interrupts.hint`. **In this ROM that figure is HBlank plus VBlank
summed.** `OpGetProfilerFrames` classifies an interrupt by its handler's entry address:

```c
if (vec == 0x78 || (vec >= 0x70078 && vec <= 0x7FFFF)) vintCycles += dur;
else                                                   hintCycles += dur;
```

Aeon's `VBlank_Handler` sits at `$2310` and the HBlank trampoline at `$FFB452`. Neither matches, so
both land in the `else`. Arithmetic proof from one live sample, F3, 30-frame average:

| row | cycles/frame |
|---|---|
| `VBlank_Handler` `$002310` | 5,690 |
| HBlank trampoline `$FFFFB452` | 3,680 |
| **sum** | **9,370** |
| reported `interrupts.hint` | **9,370** |
| reported `interrupts.vint` | 0 |

Exact, and `vint` reads zero in every sample ever taken here. So:

- **Never read `interrupts.hint` as HBlank cost.** It is two handlers.
- **Never difference two configs on it when they differ in VBlank work** — and a config that adds or
  removes a schedule RECORD differs in VBlank work, because `Raster_BuildSchedule` copies records.
- **Read the per-routine row instead.** `routines[]` is keyed by that same entry address, so the two
  handlers are separate rows with their own `cycles` and `calls`. That is what this file uses.

`calls` is a free correctness check: it reports how many fires the hardware actually took, so a
fixture that failed to install cannot be silently measured. Every row below reads `2 + n`.

### Noise floor: ZERO

Five independent boots per fixture, eight fixtures, 30-frame samples, forty runs:

```
F0 [572,572,572,572,572]   F1 [2948]x5   F2 [3320]x5   F3 [3680]x5
F4 [3968]x5                F5 [3632]x5   F6 [3028]x5   F7 [3320]x5
```

Spread 0 on all eight, and the `calls` counts identical too. The scene is pinned
(`Debug_Scene_Freeze = 1`), the anchor is a reset, and `cycles`/`calls` are divided by the frame
count inside the emulator, so a multi-frame sample is exact rather than averaged-with-noise. **No
difference reported here is inside a noise floor, because there isn't one.**

This supersedes the "+/- 35 cycles" figure recorded on 2026-08-18. That was the spread of
`interrupts.hint` on live content with the camera running — an instrument three ways noisier than
this one and measuring a different quantity.

---

## The fixtures

Each varies ONE thing. Fires repeat inside a fixture so the reported figure is a marginal cost
divided by the repeat count; the repeat count is capped by `RASTER_BUF_SIZE` (128 bytes), not by
choice. Fires are spaced 20 lines apart, far outside any density boundary. Fire POSITION was
separately shown to have no effect (line 2 vs line 99, 2026-08-18).

| fixture | shape | calls | cycles/frame | marginal per fire |
|---|---|---:|---:|---:|
| F0 | no fires — priming records only | 2 | 572 | (286 per no-op record) |
| F1 | one `reg_set` | 8 | 2,948 | **396** |
| F2 | `stream_cram`, 1 word | 8 | 3,320 | **458** |
| F3 | `stream_cram`, 3 words | 8 | 3,680 | **518** |
| F4 | `stream_pal_region`, 3 words | 8 | 3,968 | **566** |
| F5 | `reg_set` + `stream_cram` 3 | 7 | 3,632 | **612** |
| F6 | two 1-word `stream_cram` ops in ONE fire | 6 | 3,028 | **614** |
| F7 | `stream_vsram`, 1 word | 8 | 3,320 | **458** |

Marginal = (fixture - F0) / n.

---

## The model, and why it is not a curve fitted to its own anchors

```
fire_cost = FIRE_BASE + sum over ops of ( FETCH + dispatch(depth) + class_work + WORD x words + TAIL )
```

| constant | value | what it is |
|---|---:|---|
| `RASTER_FIRE_BASE_CYC` | 302 | everything not an op: prologue, arm write, record decode, loop entry/exit, epilogue, `rte` |
| `RASTER_OP_FETCH_CYC` | 8 | `move.w (a1)+, d1` |
| `RASTER_DISPATCH_RUNG_CYC` | 16 | a FAILED rung: `cmpi.w #imm,d1` + `beq.s` not taken |
| `RASTER_DISPATCH_HIT_CYC` | 18 | the matching rung: `cmpi.w` + `beq.s` taken |
| `RASTER_OP_TAIL_CYC` | 10 | `dbf d0, .op_loop`, taken |
| `RASTER_STREAM_WORD_CYC` | 30 | one streamed word: `move.w` to `VDP_DATA` + `dbf` |
| `RASTER_WORK_REG_CYC` | 12 | `move.w (a1)+, (a2)` |
| `RASTER_WORK_CRAM_CYC` | 90 | command `move.l` 20 + `moveq` 4 + `EFX_BLANK_DELAY` spin 54 + count read 8 + final not-taken `dbf` 4 |
| `RASTER_WORK_REGION_CYC` | 122 | the above + `lea Pal_Variant_Stage` 8 (short form) + `adda.w` 8 + `lea VDP_CTRL` restore 12 |

Dispatch depth comes from the opcode: `Raster_HInt` tests `OP_CRAM`, `OP_PAL_REGION`,
`OP_RUN_GRADIENT`, `OP_RUN_RAMP` in ascending order with `OP_SET_REG` as the fall-through, so
`depth = (opcode - OP_CRAM) / 2` and the fall-through pays all four rungs. **Inserting an opcode
re-prices every op behind it automatically** — that is the property the review asked for, and the
derivation is pinned to the opcode constants rather than restated.

### Eight measurements, four free parameters, zero residual

| fixture | model | measured |
|---|---:|---:|
| F1 | 302 + (8+64+12+10) = **396** | 396 |
| F2 | 302 + (8+18+90+30+10) = **458** | 458 |
| F3 | 302 + (8+18+90+90+10) = **518** | 518 |
| F4 | 302 + (8+34+122+90+10) = **566** | 566 |
| F5 | 302 + 94 + 216 = **612** | 612 |
| F6 | 302 + 156 + 156 = **614** | 614 |
| F7 | = F2 = **458** | 458 |

Every op term is confirmed a SECOND way, by hand-counting the emitted 68000 stream at
`s4.debug.bin $79CC..$7A5C`. All four dispatch branches are `beq.s` (`671A 672E 674E 675A`), which
is where 16 and 18 come from. Only `RASTER_FIRE_BASE_CYC` is measurement-only: the hand count lands
~10 cycles off, inside this emulator's exception-entry / `movem` / `rte` timings, and this project
has no silicon to arbitrate.

The pins live in `raster_dsl.emp` beside the constants, so the model is held to all seven shapes at
build time. Perturbing `RASTER_STREAM_WORD_CYC` by ONE cycle fails five of them by name.

---

## The correction to the record

The 2026-08-18 brief recorded that `check_density` charged **roughly half** what a fire costs, on
these figures:

| fire | modelled then | "measured" then | measured NOW |
|---|---:|---:|---:|
| `reg_sh_on` + 3-word `stream_pal_region` | 526 | ~1,002 | **660** |
| 1-word `stream_vsram` | 454 | ~665 | **458** |

**The ~1,002 and ~665 were `interrupts.hint` differentials, i.e. HBlank + VBlank.** Suppressing a
patch channel removes the record from `Raster_BuildSchedule`'s per-record copy as well as removing
the fire, so each figure carried a few hundred cycles of VBlank. The residuals are the right size
for that: 1,002 - 660 = 342 and 665 - 458 = 207, against records of 9 and 7 words copied at ~22
cycles a word plus the entry's own decode.

So the old `418 + 36 x words` was accurate to **1.5%** on the two shapes it was fitted to. It was
not under-charging. It was mis-STRUCTURED, in four ways:

1. `reg` ops charged **zero** — a fire of four register writes modelled at 0 and could never be
   refused. It costs 678.
2. every stream op charged alike — `stream_pal_region` costs **48 more** than `stream_cram` at equal
   word count.
3. dispatch depth invisible — **16 cycles per rung**, and adding an opcode moved existing ops with
   nothing able to see it.
4. the per-fire base charged **once per stream op** instead of once per fire, so a two-stream-op fire
   was over-charged by a whole base. Two errors in opposite directions is precisely why the one shape
   it was fitted to came out right.

`RASTER_CRAM_MAX`'s and `fire`'s existing per-fire ceilings are unaffected: they are structural
counts, and this is the cycle model they always disclaimed.

## VSRAM costs what CRAM costs

F7 and F2 read **identically**, to the cycle. That is not a coincidence to be explained away — a
`stream_vsram` op EMITS `OP_CRAM` with a different command longword, so it is the same instruction
path. The open op-class split is about `EFX_BLANK_DELAY` and the `RASTER_CRAM_MAX` ceiling, i.e.
whether a VSRAM write needs parking in HBlank at all. That would REMOVE work, so nothing this model
admits today becomes illegal under it.

## The guard, both directions

Demonstrated by building, not by argument:

| program | verdict |
|---|---|
| two 3-colour `stream_cram` fires on lines 120 and 121 | **REFUSED** — "models at 518 cycles but only 1 scanline(s) = 488 cycles remain" |
| the same two on lines 120 and 122 | **ADMITTED** — ROM builds, crc unchanged |
| four `reg_set`s on 120, a fire on 121 | **REFUSED** at 678 — the old model scored this **0** |
| every program shipped in the tree | **ADMITTED**, all four CRCs unchanged |

Nothing shipped had to move. `OJZ_TwoChannel`'s two bands are 2 fire lines apart (976 cycles) and its
heaviest fire is 660.
