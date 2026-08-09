# Art-streaming P2c Tasks 8+9 — A/B evidence (chains 75/76/77/78)

Durable A/B evidence backing the combined golden refreeze of the P2c dual-cap +
per-act art-budget parcels. Byte-changing feature parcels (they add new governed
behavior), so the bar is "the shipping circuit is unaffected and the governors are
silent as gated" (the shipping gate), plus a structural characterization of the
STRESS fixture.

## Parcels covered (aeon `feat/art-streaming-p2`)

| chain | commit | change |
|---|---|---|
| 75 | `2666b77` | `feat(system)`: enqueue-side dual cap (entries + bytes) on the DMA queue |
| 76 | `615673f` | `feat(level)`: per-act art streaming budget word (B&R pattern) + T7 NIT-1 |
| 77 | `a4f65b5` | `fix(level)`: reload art budget in the PageIn per-frame tick, not VInt_Level |
| 78 | `025f525` | `fix(level)`: STRESS_EVICT_FRAMES 8->9 + structural finding (constants only) |

## Normal build — the SHIPPING gate (controller oracle A/B, collected)

Deterministic OJZ circuit, both directions + vertical + diagonal:

- Circuit CLEAN (no wrong/blank FG tiles during motion; renders as the pre-parcel baseline).
- `Lag_Frame_Count` = 0 throughout.
- **`Dbg_DMA_Enq_Capped` = 0** — the Vectorman byte cap (12288, above the drain-window
  budgets) never fires in normal play; the entry-count half is likewise never hit.
- **`Dbg_PageIn_Deferred` = 0** — the per-act art budget (4096 = 2 pages/frame) never
  defers; landing throughput is <=1 page/frame (single staging slot), structurally
  below the ceiling. Both governors present-but-silent, exactly as gated.

This is the shipping gate: the shipped ROM behaves identically to the pre-parcel
baseline; the new caps are inert admission governors that engage only under a runaway
enqueue storm / multi-page-per-frame burst that the current design cannot produce.

## Phase-fix note (chain 77)

The art budget is CHARGED in the main loop (`PageIn_EnqueueLanding`, every physical
frame) but was first RELOADED only in `VInt_Level`. `Frame_Counter` advances on BOTH
the `VInt_Level` and `VInt_Lag` (decode-straddle) paths, so any frame whose VBlank
dispatched `VInt_Lag` charged without reloading -> the budget depleted into a spurious
deferral, and a deferred landing parks its allocated frame (`pf_page=$FFFF`) across the
retry -> transient frame famine. Fix: reload in `PageIn_Process`'s own once-per-physical
-frame tick (gated on the same `Frame_Counter` delta, beside the `Page_Pfx_Budget`
reset), so reload and charge are always in-phase and the per-frame byte ceiling
accumulates correctly. Single owner. The `PageIn_EnqueueLanding` charge already commits
only on a successful `QueueDMA_Important` (verified in ROM bytes), so no charge-rollback
change was needed.

## Cap-reset-location note (chain 75)

The Task-8 DMA enqueue byte-cap total (`DMA_Enq_Bytes_Frame`) is reset in `VInt_Level`
(frame boundary, matching `DMA_Budget_Remaining`), NOT in the PageIn tick. It is charged
by many enqueuers with no single main-loop tick, and its 12288 ceiling is coarse enough
that a rare `VInt_Lag`-straddle accumulation is benign (worst case: a spurious reject
that retries next frame — no held frame, no thrash). Only the tight, held-frame-
amplified ART budget needed the in-phase PageIn-tick reload.

## STRESS fixture — structural characterization (not a shipping gate)

`STRESS_EVICT=1` clamps the residency cache below the pool to force eviction. Result on
the chain-74 soak matrix (boot -> right 700 -> left 700 -> down 400 -> diag right+down
500): the `PageCache_AllocFrame` thrash assert fires at the diagonal seam at every clamp
< PAGE_FRAMES (8 and 9 both).

STRUCTURAL finding (overseer, final): the refcount source is the whole 80x60
`Tile_Cache_Nametable` window (multi-screen); on OJZ's deduped 10-page pool any window
references ~every page, so **the cache-window working set == the pool**. Refcount-based
eviction cannot sustain churn at any clamp < PAGE_FRAMES on a small deduped act
(chain-74's clean run at clamp 8 was traversal luck). The refcount **audits stay clean
through every thrash run** (recount == stored): the refs are genuine window references,
not leaks, and the AllocFrame assert **correctly refuses to evict displayed art**. The
thrash is correct LOUD detection with ZERO silent corruption — the design being right.
Streaming exists for acts whose windows cannot span the pool; OJZ is not one.

Consequence: on OJZ the STRESS fixture is a loud thrash-CANARY, not a churn generator.
`STRESS_EVICT_FRAMES` is kept at 9 as the fixture floor with the full calibration
history documented in `engine/system/constants.emp` (6 livelock / 7 loud-thrash probe /
8 marginal / 9 floor + this structural finding). Real sustained-churn coverage is
Task 11's `--stress-uniquify` fixture (window << pool).

## Verdict

Normal-build A/B green is the shipping gate and is met. The STRESS fixture is a
structural-limitation canary whose loud thrash is correct behavior (audits clean, no
silent corruption). The combined 75/76/77/78 golden re-freeze is earned on this
evidence.
