# Effects P3 — `vsram()` gate evidence

**Date:** 2026-08-14 · **Emulator:** oracle (Exodus-derived) · **Shape:** `DEBUG=1`
**Fixture:** `OJZ_TestVsram`, bound to OJZ act 1 **section 0** so it is on screen at spawn.
**Shipped form:** VSRAM byte 2 (entry 1 = **plane B**), offset `$0043` (67 px), screen line 112.

## What was being proved

`vsram(addr, values)` was added on the finding that `Raster_HInt`'s CRAM op is **target-agnostic** —
it issues whatever VDP command longword the program carries, so only the *constructors* were ever
locked to CRAM. If that reading was right, per-band vertical scroll needed **no runtime change at
all**. This is the first program to exercise it, and Aeon had no vertical scroll banding before it.

## Method

Builds differing **only** in one constant each, all targeting byte 2 (plane B):

| build | offset | ROM |
|---|---|---|
| control | `$0000` | `crc=ba4b15c0 len=711314` |
| 64 px | `$0040` | `crc=827ad896 len=711314` |
| 67 px | `$0043` | `crc=eb607681 len=711314` |

Identical program, identical fire line, identical timing — so any pixel difference is the scroll and
nothing else. Captured deterministically: `reload_rom` (power-cycle reset) → `press start ×150` →
screenshot; row-by-row pixel diff ignoring `y <= 24` (the HUD ring counter differs run to run).
Each pair was captured twice: with plane A composited normally, and with plane A muted
(`set_layer_enabled` **before** the run — the framebuffer does not re-composite while paused).
Captures in this directory (`vsram-planeB-*.png`).

## Result 1 — plane B works, and lands on N+1

67 px build vs control, plane A **on**:

```
   y=108..111    0 differing px
   y=112       118 differing px   <-- SPLIT, exactly the authored line
   ...
   every row 112..223 differs — 16,630 px total
```

With plane A **off**: the identical result, 16,630 differing px from y=112. So a VSRAM write from
HInt takes effect on the line *after* the fire, exactly like a CRAM write, and the DSL's existing
`-1` fire-line arithmetic is correct for VSRAM with no separate rule. This matches the earlier
plane A (byte 0) measurement bit-for-bit on the split line, and closes the N+1-vs-N+2 question
`docs/DEFERRED_WORK.md` booked when the constructor was added — now measured on **both** entries.

## Result 2 — the "plane B shows nothing" mystery, resolved

The prior session's `$0040` (64 px) plane B write produced no visible change and was left
explicitly unexplained. Root cause, established today:

- **64 px build vs control: 0 differing pixels** — with plane A on *and* off. Reproduced cleanly.
- **67 px build vs control: 16,630 differing pixels** from exactly y=112. Same program, same byte,
  same line; only the value differs. **The write lands and displays.**
- **The OJZ BG nametable is vertically periodic with period 64 px.** Read off VRAM `$E000` on
  oracle: the trunk band cycles every 8 tile rows (`$60,$70,$80,$90,$A0,$B0,$C0,$D0` repeating —
  exactly 64 px), the canopy every 4 rows (32 px), and every row repeats every 16 tiles
  horizontally. A 64 px vertical scroll maps plane B onto itself pixel-for-pixel.
- Corroborated in image space: below the split, screen rows 64 px apart in the control differ by
  only 112 px total across 47 rows (sprite pixels), vs 16,630 for a true 67 px shift.

So of the five candidate explanations in the 2026-08-14 handoff, the first was correct
(**self-similar art**); occlusion is disproven (the effect is fully visible with plane A on — and
plane B dominates this scene anyway), and the write/clobber theories are disproven both empirically
and statically (`Vscroll_Write` is `requires(vblank)` and is the only other VSRAM writer).

**The shipped fixture therefore uses `$0043`.** Any offset ≡ 0 (mod 64) is invisible against this
art; pick banding offsets against the BG's repeat period, not round numbers.

## Result 3 — plane A must not be scrolled mid-frame (engine constraint)

The first cut of this fixture targeted byte 0 (plane A). It measures the same clean y=112 split
(`vsram-on-planeA.png`, kept as the byte-0 N+1 evidence) but the revealed content is **streamer
scratch**: `TILE_CACHE_ROWS = 60` means the rows around the camera window are the streamer's
working margin, not display-ready content, so a large mid-frame plane A vscroll displays
stale/half-written tiles. This is a real engine constraint, recorded in the `vsram()` constructor
docs — band **plane B**, which is also what the reference corpus does.

## Caveats, recorded rather than glossed

- **Emulator, not hardware.** Emulators disagree on mid-frame VSRAM: GensKMod latches at HBlank
  start; Exodus/BizHawk consult continuously. Oracle is Exodus-derived, so this measurement reflects
  continuous reading. This project verifies on oracle by policy and has no real hardware, so N+1 is
  the best evidence available — not a hardware fact.
- **Transience is inferred, statically supported, not instrumented.** `Vscroll_Write` rewrites
  VSRAM every VBlank (`requires(vblank)`, called only from the VBlank path), and the image is
  stable frame to frame, consistent with the base being restored at frame top. Not separately
  measured at runtime.
- The VDP shadow was read live to confirm the mode this rests on: reg `$0B` = `$03`, i.e. HScroll
  mode `%11` (per-line) and vscroll bit 2 = 0 (**full-screen**), so entry 0 is plane A and entry 1
  is plane B for every column.

## Incidental

The build-time pin caught a real authoring error before the first run: the hand-written VSRAM command
words were wrong (`$4000 $0002` instead of `$4002 $0010` — the address belongs in the high word and
the type bits leave `$10` in the low). `first_mismatch` reported index 9 and named the word.
