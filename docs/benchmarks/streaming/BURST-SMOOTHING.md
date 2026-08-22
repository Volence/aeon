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

> **§1 revision, discovered during implementation:** the corner probe was NOT put under
> the classifier — the toward-motion register does not survive `decompose_block` (it
> writes d1) into the corner section, and the cs walk covers the corner block one
> block-row later anyway once `Cache_Bottom_Row` advances at the preceding R crossing.
> The corner stayed fully latch-gated in every iteration.

## 2. Before — measured on this worktree's build (crc `0dbaa80f`, byte-identical to STAGING-LIFETIME's ROM)

Both instruments, unmodified, against the worktree's own baseline build (engine bytes ==
master `02bb74ad`; DEBUG crc reproduces STAGING-LIFETIME's `0dbaa80f` exactly).
`staging_lifetime_timeline.py --states maxdiag,right,down --boots 3`: wall 151.2 s,
`up 3 days 23:00 → 23:03`, load 5-17. `tick_variance_probe.py --state maxdiag --boots 3`:
wall 45.1 s, `up 3 days 23:04 → 23:05`. Controls PASSED (both quoted rows exact); every
figure spread 0 across 3 boots.

* **Serving/ledger (reproduces STAGING-LIFETIME §2 to the block):** maxdiag 28 ticks,
  39 claims (30 empty / 9 compressed, 1.39/tick); crossings R+2/R+11/R+20/R+29 each
  6 needed, 0 pre-staged, 6 claimed (all empty, S4LZ 0); C+5/C+14/C+22 each 5 needed,
  0 pre-staged, 5 claimed with **S4LZ 48,882/4 · 40,986/3 · 25,736/2** at the crossing.
  `right` 15 claims (crossings 4/4 pre-staged, zero S4LZ at crossing), `down` 19
  (5/5 pre-staged), lifetimes 25 frames.
* **Variance:** 29 ticks/31 frames, work/tick **112,838**; exactly **3 spike ticks**
  (the 3 C crossings), lowers 127,940-127,948, uppers 235,460-239,194; ordinary ticks
  106,740-116,574; recovery ticks 22,546/40,724/51,238.

## 3. After — five whole-call schedules, measured, none acceptance-green

Each iteration was built (`DEBUG=1 ./build.sh`, canonical, all lanes) and measured with
the same two instruments, 3 boots each, spread 0 on every figure quoted. Uptimes:
v1 slt `up 3d 23:08→23:10` (146 s) + tvp `23:11→23:12` (48 s); v2 slt `23:17→23:19`
(BLOCKED, see below) + tvp `23:20` (± 55 s); v3 slt `up 4d 1:35→1:38` + tvp `1:40`;
v4 tvp `1:45→1:46`; v5 tvp end `1:49` + right/down slt `1:50→1:51`.

| schedule (all: classifier-admitted k through the down latch) | crc | ticks/31f | work/tick | **spikes** | spike lowers |
|---|---|---|---|---|---|
| baseline (F2a latch, no lookahead) | `0dbaa80f` | 29 | 112,838 | **3** | all 127.9k |
| v1: k=1 every toward-motion tick, top-down walk | `afc1d960` | 25 | 126,760 | **5** | all 127.9k |
| v2: + drift-direction walk (bottom-up when falling) | `7bf2a7b2` | 26 | 122,133 | **5** | all 127.9k |
| v3: + compressed-only claims (`TileCache_BlockIsCompressed`) | `37f1a3fe` | 23 | 124,547 | **8** | all 127.9k |
| v4: recovery-tick-only admission, batch ≤ 3 | `053412d1` | 26 | 118,635 | **5** | all 127.9k |
| v5: recovery-tick-only, batch ≤ 2 | `946b4cd6` | 25 | 118,787 | **6** | all 127.9k |

What each measured, in one line:

* **v1** — coverage works (C crossings 3-4/5 pre-staged, crossing S4LZ 48.9k → 21.4/11.9/0k)
  but the k=1 call lands on ordinary 107-117k ticks: some fit (five singles measured at
  120.4-127.9k), some don't, and the extra claims (42 vs 39, 13 compressed vs 9) evict
  live strip blocks → mid-span compressed RE-claims stack a second call onto marginal
  ticks.
* **v2** — bottom-up claims the bottom EMPTIES first and reaches the compressed upper
  rows last; worse lumps (26.8k/36.9k off-crossing). Its slt run **BLOCKED itself
  honestly**: `CLAIMS identity: frame +22: gen delta 1 != TileCache_DecompressBlock
  calls 0` — a claim invocation straddling a lag boundary, i.e. the instrument refusing
  to adjudicate a regime this laggy.
* **v3** — compressed-only claims stop the slot waste (`right`/`down` ledgers
  byte-identical, checked) but now EVERY lookahead claim is a 12-15k call; the
  stage→lag→H4-skip→stage alternation locks in: 8 spikes.
* **v4** — admission restricted to recovery ticks (measured 87-105k spin) via the H4
  armed-skip becoming a col-scan-only entry; batch ≤3. **The existence proof landed:
  crossing 221, fully covered by the preceding batch, did NOT spike** — a covered
  maxdiag column crossing does not lag (the tick ran with S4LZ 0 and no lag frame). But
  a 3-batch + the crossing's own 5-6 claims out-claim the 16-slot round-robin locally:
  strip-carryover blocks evicted mid-walk, demand re-decompresses at the NEXT R
  crossing (25.7-38.6k lumps on R-crossing ticks).
* **v5** — batch ≤2 relieves the pool but under-covers (2/cadence vs 2-4 needed);
  residual crossing calls + the alternation: 6 spikes.

**Non-regression, verified on the final form (v5, the strictest gate stack):**
`right` and `down` claim ledgers, serving tables and lifetimes are **byte-identical**
to the baseline run's JSON (`right` 15 claims 4/4 pre-staged, `down` 19 claims 5/5,
lifetimes 25 — dict-compare True on ledger/serve/lifetimes). The latch machinery
(`Cache_Spec_*` thresholds, `Cache_Spec_Skips` frame-gate bookkeeping, row scan and
corner gating) is untouched in every iteration; the admitted class exists only while
`Cache_Spec_Blocked == 1`, which `right`/`down` never reach (windows 4-5 vs trip 16).

## 4. FINDING — BLOCKED at whole-call granularity; slicing is the escalation

**The two §5 constraints jointly exclude every whole-call schedule tried:**

1. **The cycle line.** An ordinary maxdiag tick (106.7-116.7k incl. the walk) plus ONE
   whole `S4LZ_DecompressDict` call (10.2-15.3k measured across the family) straddles
   128,000. Which tick stages does not matter — v1/v3 proved the ordinary-tick lottery
   (P(over) is high enough that 4-6 staged calls/window always produce more than 3
   lags), and H4's reactive skip converts each loss into the alternation.
2. **The residency pool.** The only tick class with guaranteed whole-call headroom
   (recovery ticks) forces BATCHED claims, and batches + the crossing's own 5-6 claims
   locally out-claim 16 round-robin slots — the strip-carryover blocks the fill needs
   for the next ~7 ticks get evicted and re-decompressed (v4/v5). That is the F2 churn
   mechanism re-created by schedule pressure, with the latch and classifier intact.

**What IS established, permanently:** coverage un-lags a crossing (v4's crossing 221,
live); the classifier + compressed-only filter deliver coverage without touching
`right`/`down` (byte-identical ledgers) or the latch's protection; and the correct
lookahead claim set is "the imminent head column's compressed blocks, arriving-rows
first" — every piece of which is committed in this branch's history
(`66cc7635` + `096d934d`) as the substrate for the escalation.

**The escalation — booked, not built here (§5 named it):** ZX0R-style slicing of the
lookahead decompress (the §9.7 resumable-decoder precedent). A sliced stage is ONE
claim whose 10-15k of decode spreads at ~4-6k/tick across the 6 quiet ticks of the
cadence: constraint 1 (112.8k mean + 5k ≪ 128k, p95 base + slice still < 128k) and
constraint 2 (claims/tick returns to the ~1.4-1.5 the pool sustains — no batches)
are satisfied SIMULTANEOUSLY, which no whole-call schedule can do. It needs a
resumable `S4LZ_DecompressDict` bookmark (src/dst/window state) — engine/compression
work, a separate parcel per this note's §1.

**Tip state of this branch:** the engine files are reverted to master `02bb74ad`
byte-identically (tip DEBUG crc `0dbaa80f` — verified by rebuild); the iterations live
in history, the evidence lives here. Nothing in this branch should be repinned or
refrozen — it moves no bytes at its tip. Do NOT cherry-pick an iteration onto master:
every one of them makes maxdiag strictly worse than the baseline it replaces.

## 5. What this does NOT establish

* One act, one trajectory per state (OJZ act 1, the three leader pokes), DEBUG shape
  only — the same scope limits as STAGING-LIFETIME §7.
* The recovery-tick headroom figures are from the CURRENT spike regime; a future
  regime with different lag anatomy re-prices v4's premise (but not the finding — the
  finding is that no whole-call schedule closes both constraints).
* No pixel evidence; cycle instruments only.
