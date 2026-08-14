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
