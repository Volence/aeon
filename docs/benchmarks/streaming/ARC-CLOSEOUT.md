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

1. **The variance question** — which ticks spike and why (fill bursts on row/column
   crossings are the suspect). Needs per-tick distribution measurement; oracle's
   perFrame[] profiler rows (shipped, awaiting corpus A/B) are the purpose-built
   instrument. THE successor item.
2. **F6 margins** — owner-parked; with the mean under the line its urgency dropped
   further. Revisit only if the variance work wants headroom.
3. The arm-rewrite raster rider (~1,152 cyc/frame, off this path), the declined
   micro-levers, and the deferred capacity re-derivation — all in DEFERRED_WORK.
4. Instrument migration: this arc ran on old oracle's ideal-cycle rows with three
   documented defects (20.6% preemption loss; 30/31 window lag; per-frame division).
   The corpus A/B retires it.

## The method note

Six parcels; five materially corrected their own briefs or the packet that ordered
them, through instruments built BEFORE fixes. The arc's real export is the pattern:
diagnosis packet → instrument-first parcels → measured verdicts → honest residuals.
