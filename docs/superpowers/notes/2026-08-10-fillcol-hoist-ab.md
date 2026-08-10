# fillcol-hoist A/B — VERDICT (2026-08-10, controller)

Candidate: `perf/fillcol-hoist` tip `118c184a` (T1-T5 all landed), s4.debug.bin
428520 / crc 5c9bd63a. Baseline: master `4a411dc2`, 428014 / bbcb1b50. Method +
baseline numbers: `notes/2026-08-10-fillcol-hoist-baseline.md` (identical script
both sides).

## Correctness: PASS (all four gates)

- **Replay net — both fixtures HOLD, no desync.** This is the parcel's defining
  gate: a pure-perf parcel must NOT desync, and neither did. Standing fixture
  and slide fixture each played to clean end-of-stream (`Replay_Done` = $FF via
  the `.end` path, `Input_Source` reverted to live, `Replay_Ptr` landed inside
  its span), so every embedded checkpoint hash of the curated state block
  matched tick-for-tick. Visible state is bit-identical through T3's inlined
  copy body, T4's collision unroll, and T5's resolve memo.
- **DEBUG refcount audit: green** through 270 frames of dense-region diagonal
  (periodic `PageCache_Audit` ran ~2×; zero raises, no fault handler).
- **No semantic leak into the untouched patch runs:** `PatchRun_Seq`
  16,942→16,685 (6 calls both), `PatchRun_Col` 9,571→9,647 (5 calls both) —
  unchanged within noise, exactly the plan's leak detector.
- `CopyBlockColumn` (13,624, 4 calls) vanished from the profile — inlined into
  `FillColumn` as designed; the proc survives for `FillAll`.

## Performance: NO MEASURABLE WIN — the parcel does not pay for itself

Lag counter (ground truth), 3×90-frame diagonal windows:

| | logic ticks /270f | LAG /270 | camera travel | lag per 100 ticks |
|---|---|---|---|---|
| baseline | 209 | **61** | 96→3424 (3328 px) | 29.2 |
| candidate | 207 | **63** | 96→3392 (3296 px) | 30.4 |

The predicted ~5.5-8k cycles/frame did not appear as lag reduction. Both sides
cover the same ground at the same 15.9 px/tick, and the candidate is marginally
*worse* — inside noise, but nowhere near a win.

**Attributable per-routine wins are real but small** (~1k/frame combined):
- `Draw_TileColumn` 2,750 → 2,361 = **−389 (−14%)** — T1's gather unroll,
  measured at the SAME address ($005280) with the symbol resolved on both
  sides, so this one is unambiguous.
- `TileCache_FindStagedBlock` 13 → **11 calls**, 5,099 → 4,501 = −598 — T5's
  memo is working exactly as designed (the call count is its direct witness).

**Why the profiler comparison can't settle the rest:** the two window-2
profiles hit different content — the candidate ran more cold decompression
(`TileCache_DecompressBlock` 14,636→17,780, `S4LZ_DecompressDict`
13,277→16,168, ≈ +3.1k) because window boundaries drift with tick count
(baseline w2 spans camera 1152→2144, candidate 1200→2176). That content
variance is ~3× the attributable savings, so the fill-side deltas
(`FillRow` 30,860→31,581, `FillColumn` 20,155→21,111 — the latter now
*containing* the inlined body) cannot be read as regressions or wins. A
verdict on the copy chain needs a position-matched harness (drive to a fixed
camera X, not a fixed frame count).

## Cost

ROM **+430 B** plain vs the merged base; RAM **+138 B** (the trace block).

## Recommendation: DO NOT MERGE on this evidence — owner ruling wanted

The branch is correct, safe, and gated green; it just has no demonstrated
benefit against a real cost. Three defensible options:

1. **Take T1 only** — `Draw_TileColumn`'s unroll is the one clean, isolated,
   *measured* win (−14% on that routine, +42 B, zero RAM, no refcount
   surface). Cherry-pick `903bfde`, drop the rest.
2. **Merge whole** — accept +430 B/+138 B on the argument that T3/T4/T5's
   savings are real but currently below this measurement's noise floor, and
   will matter once a denser act ships.
3. **Re-measure first** — build the position-matched harness (fixed camera-X
   target, count frames) and re-run before deciding. Highest confidence,
   costs another oracle session.

The 2026-08-09 DEFERRED_WORK entry named this the "top lever" on the diagonal
line item at ~100% budget. This measurement says the top lever is NOT the copy
chain's call/hoist overhead — it is the flat decompress + patch-run + HInt
taxes, which the parcel deliberately did not touch. That reframing is the most
valuable output of the parcel regardless of which option is chosen.
