# Exodus: Z80 cartridge-ROM read timing during DAC playback (possible over-stall)

**Context:** Custom from-scratch Genesis/Mega Drive engine with a Z80-autonomous sample
(DAC) sound driver. We test primarily in **Exodus** (the MCP integration + VRAM viewer are
excellent) but ran into a DAC audio-quality discrepancy and would appreciate your read on
whether it's accurate behavior or a timing-model issue.

## Summary

Our Z80 DAC streaming loop plays an 8-bit PCM sample by reading bytes from cartridge ROM
(through the `$8000` bank window) and writing them to YM2612 reg `$2A`. In **Exodus** the
output has audible "static"/crackle; the **identical ROM** in **BlastEm** is clean, even under
maximum 68k/DMA load. We traced it to the **Z80's cartridge-ROM read cost**: in Exodus a Z80
read of cart ROM during active 68k execution appears to stall much more than on real hardware /
BlastEm, which adds variable per-sample delay and shows up as timing jitter ("FM-style" noise).

## The mechanism

The DAC loop is cycle-balanced: every output path is the same length **except** that the
sample-fetch path does two `ld r,(hl)` reads from the `$8000` ROM window, while the other paths
(ring-buffer drain / idle) read only Z80 RAM. So any extra cost on the ROM read shows up
directly as a per-sample timing difference between "fetched a ROM byte this sample" and "didn't".

## Objective measurement (same ROM, same driver, both emulators)

We captured the YM2612 `$2A` (DAC data) write stream as VGM and measured the inter-write
interval (= the realized DAC sample period).

| Emulator | DAC sample timing | Spectral noise floor |
|---|---|---|
| **Exodus** | bimodal **~90 µs vs ~110 µs** (≈19% jitter); the ~110 µs samples are exactly the ones that read ROM | audible static |
| **BlastEm** (accurate) | uniform | **−52 to −54 dB off-harmonic noise, 98% energy in the fundamental, 0.05% sub-fundamental noise** — clean, *even under forced continuous scrolling (max DMA)* |

The ~20 µs gap per ROM-reading sample ≈ **~70 Z80 cycles for two reads ≈ ~35 cycles of stall
per cart-ROM read**. For reference, Kabuto's hardware notes (via plutiedev) put the Z80→68k-bus
ROM access penalty at roughly **~3.3 cycles**. So the observed Exodus cost is ~10× that.

## Why we believe the small figure is correct (not Exodus)

- **BlastEm** (widely regarded as cycle-accurate, ~1–2% off real silicon) renders it clean
  under max load.
- **Real Genesis games stream DAC samples from ROM during gameplay and sound clean.** If the
  Z80 cart-bus stall were as large as Exodus models it during sample playback, essentially all
  Genesis PCM (Sonic drums, voices, etc.) would exhibit this same static — and it does not.

That said, we have **not** measured real silicon directly; BlastEm + Kabuto's notes are our
accuracy reference. It's possible we're hitting a config/version edge case or misreading
Exodus's model — hence this report rather than a bug assertion.

## What we'd love help with

Could you advise whether, in Exodus, a **Z80 read of cartridge ROM while the 68k is actively
running** is expected to cost on the order of ~35 Z80 cycles, vs a few cycles? If that's a
model artifact (e.g., the Z80↔68k bus-arbitration / wait-state path for Z80 cart accesses),
correcting it would make Exodus's DAC audio match BlastEm/hardware — and let us do all our
audio testing in Exodus, which we'd much prefer.

## Reproduction

1. Z80 driver streams 8-bit PCM from a banked ROM sample to YM2612 `$2A` in a tight loop, with
   the 68k running normal game code (active display).
2. Log the `$2A` write stream (VGM) and histogram the inter-write intervals.
3. Exodus: bimodal, ROM-reading samples ~20 µs slower. BlastEm: uniform.
4. We can provide the exact ROM, the driver source, and our VGM-analysis script on request.

— Reported from a custom Genesis homebrew engine project; happy to provide any additional data
or run targeted experiments in Exodus.
