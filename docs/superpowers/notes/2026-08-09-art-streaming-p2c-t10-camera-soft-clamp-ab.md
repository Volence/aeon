# Art-streaming P2c Task 10 — camera soft-clamp — A/B evidence (chain 76)

Durable A/B evidence backing the golden refreeze of the P2c camera soft-clamp
degradation parcel. A byte-changing feature parcel (new governed behavior: a demand
-stalled fill near the visible edge holds the offending camera axis), so the bar is
"the shipping circuit is unaffected and the governor is silent as gated" (the
shipping gate), plus a structural characterization of the STRESS fixture. The
clamp's ENGAGEMENT (counter > 0, art held instead of shown blank) is deferred to
the Task-11 fixture — recorded explicitly below.

## Parcel covered (aeon `feat/art-streaming-p2`)

| chain | commit | change |
|---|---|---|
| 76 | `80082bb` | `feat(level)`: camera soft-clamp on art demand-miss (honorable degradation) + RIDER sub-page-budget deadlock ensure |

Mechanism: a demand-stalled `Tile_Cache_Fill` whose stalled cell sits within
`CLAMP_MARGIN_TILES` (4) of the visible screen edge sets the axis bit in
`Camera_Art_Hold` (X at `.fc_budget_out`, Y at `.fr_budget_out`, each re-tested
against `Cache_Art_Stall` so a plain budget-out never holds). `Camera_Update` treats
a held axis' max step as 0 (the existing `.x_done` / `.clamp_y` no-apply paths —
player logic untouched). The word is re-derived from scratch every fill pass
(`clr.b` beside the `Cache_Art_Stall` clear), so it clears the frame the stall
resolves. DEBUG counter `Dbg_Cam_Clamp_Frames`.

## Normal build — the SHIPPING gate (controller oracle A/B, collected)

`s4.debug.bin` md5 `d21abd9a7cc20ad4cb666a86699af9eb`:

- Boot CLEAN.
- 600-frame max-scroll circuit CLEAN (renders as the established pre-parcel baseline;
  mid-scroll frame == the baseline capture).
- `Lag_Frame_Count` = 0.
- **`Dbg_Cam_Clamp_Frames` = 0 throughout** — the mechanism is present and SILENT.
  On OJZ the cache-window working set == the pool (deduped 10-page pool; see the
  structural finding), so demand stalls do not occur in normal play and the camera
  never holds. This is exactly the gated state: the shipped ROM behaves identically
  to the baseline, and the soft-clamp is an inert degradation governor.

This is the shipping gate: the shipped ROM behaves identically to the pre-parcel
baseline; the soft-clamp engages only when a demand miss leaves unfetched art near
the visible edge, which the current OJZ design cannot produce in normal play.

## STRESS fixture — structural characterization (not a shipping gate)

`s4.stress.bin` md5 `5a6d62e5ab5c4b228c5daaf358b0624c` (`STRESS_EVICT=1`, cache
clamped below the pool to force eviction):

- Boot CLEAN.
- The `PageCache_AllocFrame` thrash assert fired **mid-HORIZONTAL leg** this run.

This h-leg datapoint is noteworthy: horizontal legs were CLEAN on prior chains
(chain-74/T8-T9 saw the thrash only at the diagonal seam). It is further confirmation
of the established structural finding, now shown to be traversal-order-independent:
the refcount source is the whole 80x60 `Tile_Cache_Nametable` window (multi-screen);
on OJZ's deduped 10-page pool any window references ~every page, so the cache-window
working set == the pool. Refcount-based eviction therefore cannot sustain churn at
ANY clamp < `PAGE_FRAMES` on a small deduped act — and the leg on which the thrash
surfaces (h vs diagonal on prior chains) is just window-content luck, not a property
of the axis. The refcount audits stay CLEAN through the thrash (recount == stored):
the refs are genuine window references, not leaks, and the AllocFrame assert
correctly REFUSES to evict displayed art. Loud detection, zero silent corruption —
the design being right. Real sustained-churn coverage (window << pool) is Task 11's
`--stress-uniquify` fixture.

## Deferred proof — clamp ENGAGEMENT (Task-11 fixture territory)

The positive half of the clamp's contract — `Dbg_Cam_Clamp_Frames > 0` at a genuine
near-edge demand stall, WITH no unfetched/blank FG tile ever visible while the axis
is held — cannot be exercised on OJZ (the working set == the pool, so no sustained
near-edge stall occurs; the STRESS thrash is the AllocFrame refusal, upstream of a
fill demand miss). Per the plan (Task 10 Step 3 / Task 11 acceptance matrix), the
engagement verification is Task-11-fixture territory: the `--stress-uniquify` pool
(window << pool) is the shape where demand stalls actually fire and the camera holds
instead of showing pop-in. This chain-76 refreeze is earned on the SHIPPING-gate
evidence (present-and-silent) + the mechanism's compile-time/listing sanity; the
engagement proof is explicitly deferred to Task 11 and is NOT claimed here.

## Verdict

Normal-build A/B green is the shipping gate and is met (mechanism present, silent,
counter 0, circuit == baseline). The STRESS fixture is the same structural-limitation
canary as prior chains, this run adding a horizontal-leg datapoint that confirms the
finding is traversal-order-independent (audits clean, no silent corruption). Clamp
engagement is deferred to Task 11. The chain-76 golden re-freeze is earned on this
evidence.
