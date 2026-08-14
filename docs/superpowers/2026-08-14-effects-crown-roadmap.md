# Effects — the road to the crown

**Date:** 2026-08-14 · **Master:** `85fa0a0b`, green, both shapes byte-verified
**Owner ruling this rests on (2026-08-14):** *bands eventually — do not freeze the shape now.*
Parcel C keeps the preset a program **reference** with a seam for parameters, so a future band
compiler can emit into it without re-cutting the binding.

---

## Where the lane actually stands

| | state |
|---|---|
| Effects P1 (sparse HInt raster, per-section palettes) | shipped |
| Effects P2 (dense tier, palette variants) | shipped |
| P3 Parcel 0 (replay net) | shipped |
| P3 Parcel A (`raster_dsl` + `palette_dsl` + budget checker) | shipped `f406d50b` |
| Vocabulary review §1 defects | closed `49c7ca9a` (also shipped `vsram()`) |
| Plane B VSRAM banding | merged, aeon `cb86e130` / sigil `84d4676c` |
| Review §5 wrong-pixel holes | closed `85fa0a0b`, zero bytes |
| **Adjacent-fire density** | **MEASURED — `docs/benchmarks/effects-p3/DENSITY-EVIDENCE.md`** |
| P3 Parcel C (presets) | spec'd, **plan not written — next** |
| P3 Parcel D (starter pack + content) | spec'd |

## The two facts that should drive everything after this

**1. The vocabulary is excellent at STATIC effects and cannot express VARYING ones.**
A raster program is a frozen schedule in ROM. Everything that moves, moves by mutating staged data
or **one blessed patched word** — and that word is hardcoded three ways (`WATER_TEMPLATE_ARM0_OFF =
6`, valid only at `init_count == 1`, only for the first fire). Consequences already in the field:
`region_boundary`'s `sh: 1` is secretly load-bearing (a lava line must write a no-op
`set_reg($8C81,$8C81)` purely to manufacture the init word the offset needs), and there is exactly
one `Buf_B` and one world anchor, so **a section can have at most one moving boundary of any kind**.
Nearly everything left on the backlog's raster shelf varies at runtime.

**2. Density has a hard, measured edge at one scanline (~489 cyc).**
`vsram` at 454 fits; `cram`-of-3 at 526 does not. Overrun does not drop fires — it pushes writes
into active display and produces visible dots. S3K gets 3 colours/line at 484 by staying **inside
one interrupt** with a tuned spin; Aeon pays a separate exception entry per line. So:

> **Per-line colour work belongs in the dense tier. The sparse tier's adjacent fires are for ops
> under a scanline.**

Also worth internalising: **S3K, S2 and S.C.E. each run exactly ONE raster event per frame.** Aeon's
multi-event scheduler is not a port of anything — which is why no density number could be inherited,
and why this is a genuine differentiator rather than catch-up.

---

## Parcel sequence

### C — presets (next, byte-changing, paired)
As spec'd in `specs/2026-08-13-effects-p3-design.md`, plus:
- the preset's raster field stays a **program reference**, with one declared seam for parameters
  (the owner's bands-eventually ruling);
- fix **EFX-3 before shipping `Pal_Cycle_None`** — a count-0 script sets `PAL_ACT_CYCLE` before
  reading the count and would re-arm the 15.1%-of-frame variant derive that `ff0720ff` recovered;
- EFX-1, EFX-2, EFX-6 ride along.

### P — the patch generalisation *(the crown unlock; do this before D)*
Let a fire be declared **patchable** at authoring time and have the DSL emit its offset as a named
constant. `raster_program` already computes the exact layout and throws it away. This deletes the
magic offset, the `init_count == 1` trap, the co-located-assertion ritual, the `sh:1` hack and the
one-moving-boundary limit **in a single move**, and it is what every runtime-varying effect needs:
lava, rising flood, lightning, beat-driven pulses, a gradient that survives vertical camera motion.

Steal from S3K while here: `H_int_counter = H_int_counter_command + 1` — the arm word is a prebuilt
VDP command whose **low byte is the counter**, so re-arming is a single byte store with no OR or
masking.

### W — the world anchor gets an owner
Raster owns `Raster_Water_World_Y`; the parallax deformation system owns per-line HScroll wave and
ripple; they share no seam, so a complete underwater section (palette boundary **plus** shimmer at
the same line) cannot be expressed. S3K anchors ripple **phase** to world quantities in three
separate places precisely because a wave keyed to a frame counter slides when the camera moves.
Settle this before `sec_effects` freezes as the composition point.

### R — mid-screen restore
There is a derived mechanism for restoring at frame top and **nothing** for restoring at a lower
line, so a tint over lines 100-140 is not expressible. This is the concrete form of the bands
question and the natural first thing a band compiler would need.

### B — budget honesty, from the measurement
Correct `effects_budget_model.toml` (`full_line_fire_cost = 6` is a LINE count, not a cost;
`sparse_tier_cycles_per_frame = 8358` was VBlank+HInt under the instrument bug), add the measured
rows, and put a **density guard in `raster_program`** — density is a property of the schedule, not
of one fire — with a negative probe so it cannot go vacuous.

### D — starter pack + content
Unchanged in intent, but it should be written **after** P and W, because its most interesting
content (moving boundaries, a world-anchored gradient) is exactly what those unlock.

---

## What the corpus sweep changed (2026-08-14, nine disassemblies + web)

Three items outrank most of the sequence above and are new:

**RR — blanket register restore.** Gunstar re-blits regs `$01`-`$12` from a RAM shadow every
VBlank in ~290 cycles (`gunstar_disasm/code/disasm.asm:636-655`); Alien Soldier does it
selectively. That is *why* both Treasure engines clobber registers mid-frame with no per-effect
cleanup. Aeon instead makes each author supply a frame-top `reset` per op, which means two presets
touching one register must **agree** — composition as negotiation. Adopting the blanket restore
deletes the `reset` parameter from the vocabulary. **This is the single biggest structural item for
the SMPS-shaped goal** and it is byte-changing.

**RAMP — an accumulator op.** Five engines independently converged on per-line values computed by a
16.16 accumulator rather than streamed from a table: Ristar's perspective floor (one `divu` per
frame, then `add.l step,acc / asr.l #8` per line, ROM `$061ACE`), Gunstar's `sec θ` fan, Alien
Soldier's mirrored `$8000/amplitude`, Vectorman's centre-anchored DDA with **no table at all**, and
Thunder Force IV's Bresenham DDA in reserved registers. Aeon's `OP_RUN_GRADIENT` streams fixed words
from a baked pointer and has no accumulator and no runtime parameter. Adding `OP_RUN_RAMP` — roughly
six instructions in `.dense_body`, with `(start, step)` as runtime words in `Raster_State` — buys
vertical zoom, perspective floor, screen-melt, sweeping wave and hit-stop squash **as parameterised
presets**. Highest capability-per-line-of-code found.

**Only CRAM glitches.** A CRAM write during rasterisation recolours the pixel being drawn; VRAM,
VSRAM and register writes produce no mid-line artifact (Nemesis, SpritesMind t=291). So `vsram()`
inheriting `EFX_BLANK_DELAY` and the `RASTER_CRAM_MAX = 3` ceiling is pure loss — the hardware
ceiling is ~6 VSRAM words/line and Ristar writes **42 in one fire**. Splitting the op class is a
free capability increase.

Also worth knowing: the corpus runs handlers at **84-230 cycles/line** against our 454, via three
transferable levers — a globally reserved stream register, a VDP port pre-armed in VBlank with
autoinc 0, and pre-fetching the next line's value inside this line's handler. That 3-5x is the
difference between a few bands and a preset per band.

### Cheapest genuinely-new effect on the machine
**Per-line backdrop (reg `$07`).** Verified negative across the whole corpus — nobody does it
per-line — yet register writes are not slot-bound and do not glitch. One 12-cycle write per line is
the cheapest true raster bar available, and Aeon can author it **today** via `set_reg`; it simply
has no consumer.

### Traps recorded
Mid-frame H32/H40 switching is supported by **Exodus only** — and oracle is Exodus-derived, so it is
the one technique that would look fine here and be wrong everywhere else. The VDP debug register
stays rejected (bus-conflict based, ~30% of Model 1 units glitch). Vertical border opening is
incompatible with our per-frame arm-schedule rewind (HIRQ is not reset per frame). And re-arming
reg `$0A` inside the handler can double-fire — Tanglewood ships a `btst.b #0` filter for it and
**Aeon re-arms on every fire**, which is worth a look.

### Corrections owed to our own docs
- `docs/research/ristar-techniques.md` claim #4 is **false**: Ristar does not use cell-scroll as its
  workhorse — reg `$0B` is only ever `$8B03`/`$8B07`, both per-line, and it DMAs a full 1024-byte
  256-line HScroll table every frame. Claim #3 is correct and better than stated: the per-stage
  table pairs each HInt handler with a matching VBlank setup hook, and the pairing is the part to copy.
- The checked-in `ANALYSIS.md` raster sections for Thunder Force IV, Vectorman and Gunstar are wrong,
  and those linear disassembly sweeps are desynced exactly where the handlers live.
- `EFFECTS_AUTHORING.md` still calls the VSRAM landing line UNMEASURED while `DEFERRED_WORK.md`
  records it MEASURED N+1. Reconcile — and note the mode may decide it, so pin it per reg-`$0B`
  mode rather than globally.

## Technique worth taking from the corpus

**HCZ's permutation-profile distortion.** `HCZ_WaterlineScroll_Data` is 9312 bytes = **97 × 96
exactly** (verified by file size): 97 authored profiles, one per waterline pixel offset, each 96
byte-indices selecting *which existing ramp value a scanline shows*. It is a line stretch/compress
remap rather than a delta table — cheaper and more expressive — and the same authored bytes drive a
second subsystem (tile art re-staging). That is the shape to reach for when we want authored,
art-directed distortion rather than a sine.

## Open, and deliberately not swept into a zero-byte parcel

- `period: N` yields an **N+1** frame cadence (documented on the fixture; the real fix moves bytes).
- `pal_region` is never cross-checked against the bound variant's `v_lines` — a narrow variant leaves
  a staging line unwritten and streams zeros, or stale colours after a rebind. **The fix cannot be a
  constructor check** (binding is a runtime call); it belongs in `Palette_SetVariant` or in
  `Palette_DeriveVariant` writing all of lines 1-3.
- EFX-7 (`Raster_Clear` is a no-op, `HBlank_Uninstall` unreachable) — byte-changing.
- Spacing sweep 2/4/8 lines, to find where the adjacent-`cram` dot disappears.
