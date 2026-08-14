# Effects P3 — `vsram()` gate evidence

**Date:** 2026-08-14 · **Emulator:** oracle (Exodus-derived) · **Shape:** `DEBUG=1`
**Fixture:** `OJZ_TestVsram`, bound to OJZ act 1 **section 0** so it is on screen at spawn.

## What was being proved

`vsram(addr, values)` was added on the finding that `Raster_HInt`'s CRAM op is **target-agnostic** —
it issues whatever VDP command longword the program carries, so only the *constructors* were ever
locked to CRAM. If that reading was right, per-band vertical scroll needed **no runtime change at
all**. This is the first program to exercise it, and Aeon had no vertical scroll banding before it.

## Method

Two builds differing **only** in `OJZ_VSRAM_OFFSET`:

| build | offset | ROM |
|---|---|---|
| effect | `$0040` (64 px) | `crc=2769cf38 len=711314` |
| control | `$0000` | `crc=ba4b15c0 len=711314` |

Identical program, identical fire line, identical timing — so any pixel difference is the scroll and
nothing else. Both captured deterministically: `reload_rom` (power-cycle reset) → `press start ×150`
→ screenshot. Captures in this directory.

## Result 1 — it works

A 64 px vertical discontinuity appears across plane A at the authored line, repeating a vine band that
belongs higher up the level. Visible without instrumentation (`vsram-on-planeA.png` vs
`vsram-control-offset0.png`).

## Result 2 — it lands on N+1, not N+2

Row-by-row pixel diff of the two captures, ignoring `y <= 24` (the HUD ring counter, which differs
run to run):

```
   y=108      0 differing px
   y=109      0 differing px
   y=110      0 differing px
   y=111      0 differing px
   y=112    150 differing px   <-- SPLIT
   y=113    156 differing px
   ...
   112 of 199 body rows differ
```

**The authored line is 112 and the split is on 112**, with zero rows of slop. So a VSRAM write from
HInt takes effect on the line *after* the fire, exactly like a CRAM write, and the DSL's existing
`-1` fire-line arithmetic is correct for VSRAM with no separate rule. This closes the
N+1-vs-N+2 question `docs/DEFERRED_WORK.md` booked when the constructor was added.

## Caveats, recorded rather than glossed

- **Emulator, not hardware.** Emulators disagree on mid-frame VSRAM: GensKMod latches at HBlank
  start; Exodus/BizHawk consult continuously. Oracle is Exodus-derived, so this measurement reflects
  continuous reading. This project verifies on oracle by policy and has no real hardware, so N+1 is
  the best evidence available — not a hardware fact.
- **Plane B is unexplained.** The same program targeting byte 2 (VSRAM entry 1, plane B) produced
  **no** visible change in this scene against the same control. The write should have been identical
  in kind. Occlusion is the obvious guess; a layer-toggle probe was inconclusive. **Not established —
  do not assume plane B works here until someone measures it.**
- **Transience is inferred, not instrumented.** `Vscroll_Write` rewrites VSRAM every VBlank, and the
  image is stable frame to frame rather than drifting, which is consistent with the base being
  restored at frame top. Not separately measured.
- The VDP shadow was read live to confirm the mode this rests on: reg `$0B` = `$03`, i.e. HScroll
  mode `%11` (per-line) and vscroll bit 2 = 0 (**full-screen**), so entry 0 is plane A for every
  column.

## Incidental

The build-time pin caught a real authoring error before the first run: the hand-written VSRAM command
words were wrong (`$4000 $0002` instead of `$4002 $0010` — the address belongs in the high word and
the type bits leave `$10` in the low). `first_mismatch` reported index 9 and named the word.
