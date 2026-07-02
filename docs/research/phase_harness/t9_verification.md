# T9 outcome — D.2 attempted, measured, REVERTED; D.3 measured, toggling REJECTED (2026-07-02)

## D.2 (Timer-B-paced seam drains): implemented faithfully, measured net-negative, reverted

Commits: `8a43fd3` (implementation; the implementer also corrected the plan's Timer-B
unit — the plan claimed ~150.2us/unit but unit_B = 16 x unit_A(18773ns) = 300.4us, so
N=252 gives the ~1.2ms target period), `1e1f2cc` (Timer-A-not-due gate amendment),
`d6c11dd` + follow-up (reverts). Budget returned to $310 free; pytest 811+2 throughout.

**Round 1 (as-planned):** holds 24.1% -> 48.9% (ref 21.4%), 5-10ms gaps 441 -> 2091,
tempo -20% (key-ons/s 23.0 -> 18.3). Root cause: a pitch-correct 22-sample burst costs
exactly one Timer-B period (4290 cyc), so repayment is 1:1 with accrual — draining ticks
stretch ~2x; stretched ticks cross the 16.7ms Timer-A period and each crossing eats one
music tick (the latched A-flag fires one tick regardless of overflow count).

**Round 2 (drain only while Timer-A not yet due):** tempo restored (22.1/s) but holds
51.1%, 5-10ms gaps 2579. The stretching still starves the engine's own recovery
machinery.

**Why no variant can win (the architectural accounting, verified against the driver's
design comments):** the hot loop is a 195-cycle/sample metronome whose balance proof
already allocates 100% of streaming real-time; the ring lead (SND_RING_LEAD_TARGET=200)
exists to absorb DMA-induced FILL stalls, not tick holds — during a tick nothing
consumes the ring, so no lead depth covers a tick hold; and any in-tick emitter
necessarily spends real time 1:1 that must come out of the tick budget (tempo) or the
hot loop's slack (which does not exist). S3K's own reference behaves the same way:
21.4% hold airtime measured on the identical script — the tick-hold class is inherent
to single-Z80 drivers with in-tick work.

**Where this leaves the D-group numbers (current = T8 state, the measured best):**
holds 24.1% vs ref 21.4% (delta 2.7pp); 5-10ms gaps ~4.6/s vs ref ~1.0/s; 10-17ms
~0.5/s vs ref ~0.02/s. The honest remaining lever is SHORTENING THE WORST TICKS
(the 5-10ms ticks themselves: profile what dominates them — patch-load YM busy-waits,
bulk-refill length, event clusters), NOT in-tick draining and NOT ring depth. Recorded
as a follow-up investigation for DEFERRED_WORK at T12; needs its own profiling round.

## D.3 (hit-scoped $2B/FM6 duty): measured, REJECTED per the spec's expected outcome

Inter-hit noise floor on isolated DAC+FM6 renders (63 ref / 80 ours windows >150ms):
both drivers are DIGITAL SILENCE (below -180 dBFS rel peak) between hits. Our
always-armed DAC parked at $80 DC is exactly as silent as ref's key-off+$2B-toggle
(42-72% duty) approach. Hit-scoped toggling adds complexity for zero measurable
benefit: REJECTED. (Spec §D.3 one-line amendment lands with T12's doc sync.)
