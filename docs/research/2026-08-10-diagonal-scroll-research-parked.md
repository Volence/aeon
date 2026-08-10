# Diagonal-scroll research — what was tried, what it cost, what's left

Owner ruling 2026-08-10: **take the clean win (T1), park the rest for a
research day.** This note is the parked state, so nobody has to re-derive it.

Evidence: `../superpowers/notes/2026-08-10-fillcol-hoist-ab.md` (verdict) and
`-baseline.md` (method + baseline numbers). Plan:
`../superpowers/plans/2026-08-10-fillcolumn-hoist.md`.

## Shipped: T1, the gather unroll

`Draw_TileColumn`'s two column-gather runs now read four cells per iteration
via 16-bit displacements plus one `lea`, with the old body as the 0-3 cell
remainder. 30 cycles/cell → 19.5. Measured **2,750 → 2,361 cycles (-14%)** at
the same address with the symbol resolved on both sides — the one unambiguous
win in the parcel. +42 B, no RAM, no refcount surface. On master as `e1367aee`
(cherry-picked from `903bfde`), sigil chain 87.

## Parked: T2-T5, on branch `perf/fillcol-hoist` (tip `118c184a`) — DO NOT DELETE

All four are **built, green, and correctness-gated** (both replay fixtures
hold with every checkpoint hash matching, refcount audit clean, patch runs
unchanged within noise). They simply did not move the lag counter.

| task | what it does | measured | cost |
|---|---|---|---|
| T2 | `FillRow` phase 2 reuses phase-1 run bounds instead of re-deriving | not separable | −66 B |
| T3 | `FillColumn` banks per column; `CopyBlockColumn` inlined for the hot path (proc retained for `FillAll`) | not separable | +268 B |
| T4 | collision copy count-8 full unroll, displaced two-plane pairs | not separable | +24 B |
| T5 | gen-guarded per-walk memo of `FindStagedBlock` resolves | 13 → **11 calls/frame** | +162 B, +138 B RAM |

Whole parcel: 61 → 63 lag per 270 frames (no win), +430 B ROM, +138 B RAM.

## The reframing — this is the real result

The 2026-08-09 DEFERRED_WORK entry called the copy chain the "top lever" on
the diagonal budget. **That is now falsified by measurement.** Every lever in
that scope shipped and the lag counter did not move. The residual at ~100%
budget is the flat taxes the parcel deliberately did not touch: cold
decompression, the already-batched patch runs, and HBlank. DEFERRED_WORK's
diagonal entry carries this correction.

## If someone picks this up again, start here

1. **Fix the measurement first.** Fixed-FRAME windows drift in content — the
   candidate hit ~3.1k more cold-decompress cycles than the baseline purely
   from landing at a different camera position, which is ~3× the savings being
   hunted. Drive to a **fixed camera-X** and count frames instead. Without
   this, nothing in this area is measurable.
2. **Re-target at the flat taxes**, not the copy chain. In the window-2
   profile they are: cold decompress (`DecompressBlock` + `S4LZ_DecompressDict`
   ≈ 28k when a page misses), `PatchRun_Seq`/`_Col` ≈ 26k (already batched and
   M-1-endorsed — needs a different idea, not more batching), HInt 5.9k,
   `Section_UpdateColumns` 4.8k, `Parallax_Update` + `Parallax_Fill_PerLine`
   5.9k.
3. **T5's memo does work** (13 → 11 probes) — it is just too small to see. If
   the probe count ever grows (denser acts, more blocks per walk), it becomes
   worth more; the branch has it written and gated.
4. **Merging the branch later needs one sigil row**:
   `("TileCache_FillColumn", "TileCache_FindStagedBlock", "a1")` in
   `D1C_BASELINE` — the same documented edge-blind false positive already
   baselined for `FillRow`. It must land **in the merge lockstep**, never
   ahead of it (adding it to sigil master early makes the multiset GONE-fire
   on master and blocks every other lane — that happened on 2026-08-10 and was
   reverted as `3004aef9`).
5. Rejected in-scope alternative, recorded so it isn't re-invented: pairing
   sibling row fills so they share one walk. Bigger theoretical win, but the
   resume topology (budget-out mid-walk) makes it risky.
