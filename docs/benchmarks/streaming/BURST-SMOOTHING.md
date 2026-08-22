# Burst smoothing — giving maxdiag's column crossings the `right` lane's coverage

Parcel of the approved streaming lane (owner ruling 2026-08-21). Mechanism pinned by
`STAGING-LIFETIME.md` (§4): at maxdiag the F2a latch (`Cache_Spec_Blocked` = 1 for the
whole window) suppresses the cs col-scan — the ONE mechanism that pre-stages column
blocks — so every block-column crossing pays a 25.7-48.9k cyc `S4LZ_DecompressDict`
burst (2-4 compressed blocks) in one tick, guaranteeing 3 double-frames per 8-tick
cadence (`TICK-VARIANCE.md` §2/§3). At `right` (latch up) the same col-scan covers
crossings 4/4 with zero S4LZ at the crossing: k=1 block/tick, 9.4-15.3k cyc each,
≥4 ticks of lead.

## 1. Design decision — shape (a): a demand-classified lookahead claim class

§5 of STAGING-LIFETIME offers two mechanism shapes:

* **(a)** a demand-classified lookahead claim class the latch does NOT gate — imminent
  head column only;
* **(b)** an amended latch admitting k=1 col-scan claims while blocked.

**Chosen: (a).** Concretely: the cs col-scan's F2a gate (`tst.w Cache_Spec_Blocked` after
the target publish) becomes a classifier. Latch up: unchanged — the scan runs as today.
Latch down: the scan's k=1 stage is admitted ONLY when the camera moved toward the
latched side THIS tick (delta px x latched direction > 0, both already live in registers
at the classification point). The corner (H2) probe — whose block IS the imminent head
column's bottom block at maxdiag (compare STAGING-LIFETIME §2: C +22 needs (9,4..8),
row 8 x col 9 is the corner) — is admitted under the same classification, additionally
requiring both axis targets active, which the existing corner preconditions already
enforce. The pfx row scan stays fully latch-gated.

### Why (a) over (b)

(b) is two deleted instructions — while blocked, let the col scan run k=1 always. At
maxdiag the two shapes behave identically, because the toward-motion test passes every
tick there. Where they part is the case the latch exists for: **a stale H3 direction
latch with no horizontal motion** (e.g. a vertical fall after rightward running — the
H3 hysteresis latch holds `Cache_H_Pfx_Dir` until H_PFX_HYST px of NET opposite motion,
which pure-vertical motion never supplies). Under (b) the col scan would keep claiming
right-side blocks that no crossing will consume, from the same 16 round-robin slots the
demand fill needs — exactly the F2-measured churn class (CHOKE-DIAGNOSIS §3 correction:
the bigger cost of churn was demand blocks evicted mid-walk and re-decompressed, 2.20
demand claims/tick at pre-guard maxdiag). Under (a) those claims are refused: no
toward-motion, no claim. The classification makes the admitted claim *demand pulled
forward* — the camera is measurably advancing on the target column — rather than
speculation, which is the §5 distinction between the two shapes, bought for two
instructions (a sign-fold and a `tst.w`).

### The measured constraints, argued

* **Residency (~0.4 ticks of margin at ~1.9 claims/tick worst case).** The admitted
  class moves the crossing's 5 claims earlier; it does not add claims (a pre-staged
  block is a staged hit at the crossing, not a second claim). Steady-state claims/tick
  stays ≈1.39; the §5 worst case (~1.9, survival 16/1.9 ≈ 8.4 ticks vs the 8-tick
  cadence) already prices transient overlap. Our claims are staged inside the previous
  inter-crossing gap, so their lead is ≤7 ticks < 8.4-tick worst-case survival. Dead
  claims are possible only on a camera reversal after staging (bounded: ≤ the blocks of
  one column per reversal, and the H3 hysteresis makes reversals rare at speed). The
  COVERAGE identity of `staging_lifetime_timeline.py` verifies survival directly — §3
  below carries the after-tables.
* **Cycle budget (+15.3k on a 116.7k tick crosses 128,000).** No new pacing mechanism
  is invented; the admitted class rides the two that exist, per §5's own pointer:
  * **budget-leftover ordering** — the scan runs only when the demand fill left
    `Cache_Fill_Budget` > 0. Row-crossing ticks claim 6 blocks against
    BLOCK_DECOMP_BUDGET = 6, so the scan self-excludes from exactly the ticks that
    already carry 6 claims; the k=1 stage lands on the quiet ticks between crossings
    (6 of every 8 at maxdiag).
  * **the H4 lag gate** — the tick after any lag frame skips speculation (never two
    running), so a marginal tick that does lag cannot compound.
  The residual risk is real and stated: a k=1 compressed stage (12.2-13.7k at maxdiag
  content) landing on a 115-116.7k quiet tick crosses the line. Whether that happens
  depends on which ticks are expensive after the phase changes — a measurement, not a
  model. The acceptance gate is TICK-VARIANCE's own instrument re-run: if new frames
  cross 128,000, whole calls are too coarse and the booked escalation is ZX0R-style
  slicing of `S4LZ_DecompressDict` (§9.7 precedent) — a separate parcel, not a silent
  loosening of this one.
* **What the latch protects stays protected.** While down, the row scan and the
  un-classified col/corner claims remain suppressed; `Cache_Spec_Skips` bookkeeping
  (frame-gate section) is untouched; trip/re-arm thresholds are untouched. At `right`/
  `down` the latch never trips (windows 4-5 claims per 8 ticks vs trip 16), so the only
  delta there is the classifier's ~3 instructions on the always-armed path — claim
  ledgers must come back byte-identical, and §3's before/after tables check exactly
  that.

### What is deliberately NOT done

* No latch threshold changes (BLOCK_SPEC_LEAD_TICKS / BLOCK_STAGE_SLOTS trip /
  BLOCK_SPEC_REARM untouched).
* No row-scan admission: on THIS content row crossings are free (24/24 empty-form).
  STAGING-LIFETIME §3's INFERRED paragraph names the symmetric risk (compressed
  below-row content would burst R crossings by the same mechanism); that is booked as
  deferred work, not smuggled in here.
* No new pacing state, no cycle estimator, no slicing — escalation criteria above.

## 2. Before — measured on this worktree's build (crc `0dbaa80f`, byte-identical to STAGING-LIFETIME's ROM)

(filled by the measurement step)

## 3. After — same instruments, same ritual

(filled by the measurement step)
