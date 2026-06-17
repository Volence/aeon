# DAC Output Jitter — Objective VGM Analysis (2026-06-17)

## Method (new capability)

The Exodus MCP can capture **VGM** (`emulator_vgm_start/stop`), which logs every YM2612
register write — including each DAC sample written to reg `$2A` — with sample-accurate
timing. Parsing the `$2A` inter-write intervals gives an **objective** measure of the DAC
output rate and its jitter, replacing ear-based guessing. Parser: `/tmp/vgm_analyze.py`
(walks VGM commands, accumulates the 44.1 kHz wait clock, histograms `$2A` intervals).

This is the right tool for all future audio-timing work — measure, don't guess.

## What we measured (TEMP blip, idle harness, ~2 s captures each)

| Config | Rate | Jitter (stdev/mean) | Notes |
|---|---|---|---|
| Timer-paced, N=1020 (75 µs period) | 6.0 kHz | **23%** | loop overruns the short period, misses a variable # of ticks |
| Timer-paced, N=1009 (282 µs) | 3.5 kHz | 10% | more slack → fewer missed ticks |
| Timer-paced, N=1003 (400 µs) | 2.5 kHz | 6.6% | jitter shrinks with slack → bounded loop-overrun, not unbounded |
| Free-run, 2:1 fill + guard | 6.5 kHz | 20% | bimodal: 130 µs / 150 µs clusters |
| Free-run, 1 fill, **guard on, mode-branch on** | 8 kHz | 24% | 113 µs (66%) / 130 µs (26%) |
| Free-run, **pure fixed** (1 fill, no guard, no mode-branch) | 8.8 kHz | core **unimodal** | **91.6% of samples at exactly 113 µs** |

## Conclusions

1. **The jitter is per-sample CODE-PATH variation in the Z80 loop — not the timer, not bus
   contention.** Proof: stripping the loop to a single fixed instruction sequence (pure
   fixed) collapses the distribution to one value (91.6% @ 113 µs). Re-adding the
   ring-full **guard** (no-op vs real-fill paths differ ~20 µs) and the **PLAY_MODE
   fill/drain branch** each re-introduce a cluster.
2. **The timer-paced architecture is a dead end for quality.** Output cadence = the loop's
   trip time only if the loop fits inside the timer period; the variable fill makes it
   overrun and miss a variable number of ticks. Widening the period reduces jitter only by
   crushing the rate (2.5 kHz @ 6.6% is still not clean). Drop the timer.
3. **The ROM read is NOT the problem.** Its latency is consistent (constant code path →
   constant timing). Earlier hypothesis (bus-contention variance forcing an architecture
   pivot) was **disproven** by the controlled fixed-loop test. No 68k-fed-buffer pivot
   needed.

## The fix (validated direction, not yet landed)

A **free-running constant-cost loop** (MegaPCM model), no timer: every sample executes the
same cycle count, so the cadence — and thus pitch — is constant. Requires:
- **Constant-cost `FillOne`**: the ring-full no-op path padded to equal the real-fill path.
- **Balanced drain path**: the DMA-window DRAIN path padded to equal the FILL path (the ROM
  read being constant-latency makes a fixed NOP pad viable — now justified).
- **Minimal / compensated VBlank ISR**: it fires once/frame and lengthens one sample (~the
  tail spikes); keep it short or fold its cost in.
- Expected result: a **constant ~5–7 kHz** (with 2:1 recovery) — low but clean. Raising the
  rate later means trimming the per-sample fill cost.

## Open issue blocking a clean land tonight

Blind pad-tuning of the no-op path did **not** converge: across pad = 0/18/32 NOPs the
two clusters stayed ~20–30 µs apart instead of merging, and the majority cluster just
shifted with the pad. Two unknowns to resolve next, methodically:
1. **What are the two clusters, exactly?** Hypotheses: (a) steady "1 fill + 1 no-op" vs
   catch-up "2 fills"; (b) a capture artifact — the two `run_to_scanline` calls per capture
   land the 68k in different bus states → two contention populations. Resolve by capturing
   one continuous run and by stepping the loop to count actual per-path cycles
   (`emulator_step` + cycle counters), instead of inferring from the histogram.
2. **The once-per-frame ISR spike** (the 1–2% tail at 220–560 µs) needs its own handling.

Next session: count the FillOne fill vs no-op path cycles exactly (emulator step), set the
pad from that, verify the `$2A` histogram is unimodal, then balance the drain path. Use a
single continuous capture to remove the suspected two-run artifact.
