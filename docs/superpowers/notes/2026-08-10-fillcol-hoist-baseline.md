# fillcol-hoist A/B — BASELINE side (2026-08-10, controller capture)

Baseline for the perf/fillcol-hoist parcel's Task 6 A/B, captured on post-pkg3
master `4a411dc2` (s4.debug.bin crc bbcb1b50, md5 f3e0525b, hash-verified at
load). The candidate side must use the IDENTICAL script below.

## Method (deterministic, replayable)

Oracle, canonical DEBUG. Reload ROM → wait OJZ init (~16 s wall) → PAUSE →
read {Frame_Counter(u16), Logic_Tick(u32), Camera_X/Y} → three consecutive
`press [right,down] ×90` (each leaves the emulator paused; reads between are
exact-window) → lag per window = 90 − ΔLogic_Tick. Profiler enabled just
before window 2; decomposition = `get_profiler_frames(frames=60, top=30)`
taken at window-2 end. Debug-fly drive ≈ 16 px/tick diagonal. Determinism
check: camera endpoints reproduce exactly across runs (verified twice:
(1152,1168) after w1).

## Lag (ground truth)

| window | camera X span | logic ticks | LAG /90 |
|---|---|---|---|
| w1 (spawn) | 96 → 1152 | 67 | **23** |
| w2 | 1152 → 2144 | 62 | **28** |
| w3 | 2144 → 3424 | 80 | **10** |
| total | 96 → 3424 | 209 | **61/270 (22.6%)** |

## Profiler decomposition (window-2, 60-frame avg, budget 128,000)

total 128,005 (saturated). Incl-cycle costs:
- `Tile_Cache_Fill` 57,112 (44.6%) — `TileCache_FillRow` 30,860 /
  `TileCache_FillColumn` 20,155
- `TileCache_CopyBlockColumn` 13,624 (4 calls) · `PageCache_PatchRun_Seq`
  16,942 (6) · `PageCache_PatchRun_Col` 9,571 (5) — PatchRuns must be
  UNCHANGED within noise in the candidate
- `TileCache_FindStagedBlock` 5,099 (13 calls) — call count is the T5 memo's
  direct witness
- `TileCache_DecompressBlock` 14,636 (2 calls; `S4LZ_DecompressDict` 13,277)
  — demand decompresses landed in this window; expect window-to-window
  variance on this line, compare across all three windows if it confounds
- `Draw_TileColumn` 2,750 · `Draw_TileRow_FromCache` 1,838 (must be unchanged)
- Flat taxes: HInt 5,855 (4.6%) · `Parallax_Update` 3,814 +
  `Parallax_Fill_PerLine` 2,023 · `Section_UpdateColumns` 4,813 ·
  `VInt_Level` 4,633
- `VSync_Wait` 42,342 = the non-lag frames' idle in the 60-frame average
  (window not 100% saturated every frame)

Note vs the 2026-08-09 from-spawn numbers in DEFERRED_WORK: different window
position ⇒ different absolutes (e.g. FillRow 30.9k vs 35.9k). The A/B verdict
uses THIS note's method on both sides, not cross-session comparisons.
