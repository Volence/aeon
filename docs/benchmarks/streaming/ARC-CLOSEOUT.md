# The streaming choke arc — CLOSE-OUT (2026-08-20)

Opened by owner ruling 2026-08-19 evening ("if we're getting choked this fast with
little to no parallax, little to no objects... worth looking into next"). Closed
2026-08-20 morning, six parcels later, every one measured, every one landed as an
aeon+sigil pair (chains 150-155).

## The verdict

| | at diagnosis | at close | mechanism |
|---|---|---|---|
| sustained max-diagonal | **2.067 frames/tick** (~30 Hz) | **1.192** | see ladder |
| work/tick (maxdiag, DEBUG) | 190,931 cyc | **123,016** (−35.6%) | |
| vs the 128,000 60-fps line | +49% over | **4,984 UNDER, on the mean** | |
| sustained right / down | 1.000 | 1.000, both cheaper | |

**The criterion itself was corrected at the close:** `frames_per_tick = ceil(work/128k)`
is a floor on a MEAN — a mean under the line is necessary, not sufficient. 5 of 31
frames still spike past 128k and double up; the residual 0.192 frames/tick is
**tick-to-tick VARIANCE, which nothing has yet measured**. That is the arc's named
successor question, not a footnote (see "What remains").
**Both halves are now MEASURED — see `TICK-VARIANCE.md` and the addendum below.**

## The ladder (all measured, several bookings corrected)

| parcel | chain | what it did | measured |
|---|---|---|---|
| F5 audit-off-fill | 150 | de-noised the instrument | fill −3,854 idle (100.4% of the audit) |
| F1 resident identity | 151 | the ruled premise was FALSE (maps are ROM); shipped VERIFY-then-latch instead — Page_Table provably identity under resident load order | Col 183→103, Seq 136→88 cyc/word |
| F4 staging side index | 153 | zero-hash bucket over untouched eviction | probe 402-440→~200 cyc |
| F2 prefetch lands | 154 | Schmitt-guarded speculation + memo re-key; the timeline instrument corrected the diagnosis (59% dead, not 100%; demand-churn was the larger cost); latent cross-tier prefetch-aiming bug found and fixed | 2.067→1.240 f/t |
| coda: parallax unroll | 155 | the booking was stale twice; the real lever was Parcel W's sampled lines (90→43.25 cyc) | 1.240→**1.192**, mean under the line |
| (T1, P3) | — | retroactively: P2's walker coefficients were 30/31 of truth — the instrument, not the walker | model residual 195.9→13.3 |

Corrections the arc forced on its own inputs: the famine hypothesis (none — the page
tier is inert on shipped content); "~600 cyc trailing fires" (232, one fire);
"~2,300 dense re-test" (4 — VDP bus-hold absorbs operand accesses, not fetches);
"prefetch 100% dead" (59%, and the churn mattered more); the ceil model itself.

## What remains (booked, none blocking)

1. ~~**The variance question**~~ — **CLOSED 2026-08-20, `TICK-VARIANCE.md`.** The suspect
   named here was right in half: it is a fill burst on the **column** crossing
   (`S4LZ_DecompressDict`, 25.7-48.9k cyc, one per 128 px = every 8 ticks), and the ROW
   crossings cost nothing like it because their blocks are already staged. What remains
   open from that measurement: *why* the row side is covered (hypothesis only), and the
   two emulators' tick-count divergence (§1.2).
2. **F6 margins** — owner-parked; with the mean under the line its urgency dropped
   further. Revisit only if the variance work wants headroom.
3. The arm-rewrite raster rider (~1,152 cyc/frame, off this path), the declined
   micro-levers, and the deferred capacity re-derivation — all in DEFERRED_WORK.
4. Instrument migration: this arc ran on old oracle's ideal-cycle rows with three
   documented defects (20.6% preemption loss; 30/31 window lag; per-frame division).
   The corpus A/B retires it. **First leg landed 2026-08-20:
   `tools/tick_variance_probe.py` is on the new profiler and took this arc's retake;
   `streaming_choke_probe.py`, `engine_baseline_probe.py`, `parallax_cost_probe.py` and
   `raster_cost_probe.py` are still on `oracle-old` — see DEFERRED_WORK, PROBE MIGRATION.**

## Addendum 2026-08-20, hours after close: the corpus A/B landed — and revises the margin

The profiler corpus A/B (oracle `docs/2026-08-20-profiler-corpus-ab.md`, oracle main
`8d10cc5`) PASSED — the migration condition is met. But its completeness finding bears on
this close-out directly: **on the corpus-era ROM, the five published top-level rows account
for only 78.45% of a max-diagonal frame.** The missing 21.55 points are real work the old
instrument dropped (mostly `GameState_OJZScroll_Update`, +60%/tick honest vs old, and
`Tile_Cache_Fill`, +18.6%).

What that means for the verdict above, stated precisely:
- **The frames/tick figures stand** (2.067 → 1.192): they are direct tick-over-frame counts,
  not profiler sums.
- **The work/tick figures and the "4,984 under the line" margin are OLD-INSTRUMENT numbers.**
  Both endpoints carry the same loss class, so the −35.6% relative improvement is credible —
  but the absolute margin against 128,000 is NOT established and may not survive an honest
  retake. "Mean under the line" is hereby downgraded from a finding to a hypothesis.
- The retake merges into the variance workload: same instrument, same window, one run answers
  both. One gift from the A/B for that run: `vintCycles` partitions tick-frames from
  lag-frames EXACTLY (15 high frames == 15 logic ticks at maxdiag), so the per-tick
  distribution is two interleaved series — averaging across them finds nothing.

## Addendum 2026-08-20, same day: the retake RAN — hypothesis to measured verdict

`docs/benchmarks/streaming/TICK-VARIANCE.md`, `tools/tick_variance_probe.py` on the new
oracle's profiler, ROM crc `5be03175` (byte-identical to sigil `af2a4429`'s frozen golden,
i.e. this close-out's own image), 3 boots, spread 0, control PASSED against the A/B's
pinned reference row on the A/B's own ROM.

- **THE MEAN IS UNDER THE LINE, and by more than the old instrument said.** Honest
  work/tick = `(sampleCycles − VSync_Wait incl) / ticks` = **112,897 cyc, 15,103 UNDER
  128,000 (88.2% of a frame)** — against the hypothesised 123,016 / 4,984. **The verdict
  row above stands; its number is superseded.** The 21.55-point attribution hole never
  entered it: the close-out's formula built on the frame TOTAL, not on a sum of rows, so
  only `VSync_Wait`'s own row was exposed. The two instruments agree on the window's
  total work to **2.4%**.
- **`frames/tick` reads 1.069 here, not 1.192** (29 ticks in 31 frames, camera 464 px not
  416) — on byte-identical ROM bytes, so it is the two emulators disagreeing about how
  much work fits in a frame near the line, not the engine. Reported, NOT resolved; §1.2 of
  TICK-VARIANCE.
- **The variance question is ANSWERED.** 3 of 26 whole ticks fail to fit in a frame; all
  three carry **25.7-48.9k cycles of `S4LZ_DecompressDict`** that no other tick in the
  window carries, and `S4LZ_DecompressDict` runs in **exactly those 3 frames of 31**. The
  cause is the block-column crossing: one per `BLOCK_TILE_SIZE` = 128 px of camera travel
  = every 8 ticks at the follow ceiling. The four ROW-edge crossings claim the same 6
  blocks and cost ~864 cyc/call because those blocks are already staged. The three
  saturated frames run at **99.9 / 100.0 / 100.0%** of the 128,000-cycle frame with the
  vsync spin collapsed to 70 cycles.
- **stall at maxdiag: 2,216.3 cyc/frame, all of it the VBlank DMA drain** — flat across
  the window, including the burst frames, so it is not part of the variance story.
- The A/B's `vintCycles` partition **does not reproduce at this state** and must not be
  used as a method: `Logic_Tick` read at every frame boundary is the ground truth
  (TICK-VARIANCE §5.1).

## The method note

Six parcels; five materially corrected their own briefs or the packet that ordered
them, through instruments built BEFORE fixes. The arc's real export is the pattern:
diagnosis packet → instrument-first parcels → measured verdicts → honest residuals.
