# Effects P3 Parcel C2 — the declared delta list

**Written BEFORE the gate captures, on purpose.** Parcel C's gate is
"behaviour-identical against a declared delta list" (spec §8.1). A delta list written
after the captures is not a gate — it is a rationalisation of whatever was observed. So
this file is committed first, and anything the captures show that is NOT on this list is
a regression to explain, not a delta to append.

---

## The deltas this parcel intends

### D1. Frame-0 un-varianted water

**What changes:** `Variant_Water_Deep` is bound one frame later.

**Why:** today `games/sonic4/test/ojz_scroll_test.emp` binds variant slot 0 imperatively
during state INIT (`:276-278`), before the first frame renders. Under total binding, the
preset carries the variant and it is bound by the first `Parallax_CheckBoundary`, which
runs on frame 1 (`Parallax_Init` seeds `Prev_Sec_X/Y` to `$FF,$FF` sentinels precisely so
the first check always re-selects).

**Observable as:** frame 0 renders with the un-varianted palette; frame 1 onward is
identical to today.

**Must NOT be read as:** a failed install. In a press-frame or single-screenshot capture
this looks like the variant is missing entirely.

### D2. Water becomes per-section, and that IS the fix

**What changes:** the water raster template no longer survives arbitrarily far past the
section that installed it.

**Why:** this is EFX-1, the defect the parcel exists to kill. Today
`Raster_InstallSection` treats a NULL `sec_raster_table` as "keep current", so an install
persists until some later section happens to overwrite it — water renders at a stale
screen line forever, in sections that never asked for it. Total binding writes EVERY
channel on every crossing, so a section that does not name a patched template gets
`Raster_Program_None` and the water stops.

**Observable as:** in sections 4-8, where today's build may show a stale water boundary,
the new build shows none.

**Must NOT be read as:** water "disappearing". The old behaviour was the bug.

---

## What is explicitly NOT expected to change

These are the claims the captures have to support. Any movement here is a regression.

| | expectation |
|---|---|
| Section 0 | `OJZ_TestRamp` renders exactly as measured 2026-08-14: rows 0-112 unchanged, 113-223 differ, scroll advancing +1px per 2 rows, accumulator ending at exactly `$00300000` |
| Section 1 | `OJZ_TestRaster` sparse fire, unchanged |
| Section 2 | `OJZ_TestPal` palette snap + `OJZ_TestGradient`'s 8 monotonic bands on rows 96-191, boundaries on 96+12k, all three channel mixes in phase |
| Section 3 | `OJZ_ShimmerCycle` cycling, unchanged |
| Variant | `Variant_Water_Deep` live in ALL nine sections from frame 1 (matching today's live state, where init binds it once and nothing clears it) |
| Replay net | both fixtures PASS |
| `Pal_Active` | `$10` (variant-only) in steady state, as today |

---

## Deltas considered and deliberately NOT taken

- **Section-scoping the water variant.** Today `Variant_Water_Deep` is bound once at init
  and never cleared, so it is live in all nine sections. That is arguably wrong — a water
  tint in a cave section is not intentional design — but every preset carries it anyway,
  because this parcel CONVERTS, it does not re-author. Changing which sections are tinted
  is content work for Parcel D, and mixing it in here would make the frozen-table audit
  unattributable, which is the whole reason the parcel was split.

- **Dropping the four unreferenced starter variants.** `Variant_Water_Murky`,
  `Variant_Poison`, `Variant_CaveDark` and `Variant_Dusk` cost 32 emitted bytes and are
  read by nothing (measured Task 11). Kept: they are deliberate seeds, and the usage data
  is now recorded so a later parcel can decide with evidence.

- **`ep_transition` / cross-fade.** Present in the struct, used by no C2 fixture, so
  `Palette_ArmFade`/`Palette_DoFade` stay unreachable (EFX-2). Deliberate — it keeps this
  parcel's gate clean, and the arch doc's "cross-fading (planned)" line stays accurate.
