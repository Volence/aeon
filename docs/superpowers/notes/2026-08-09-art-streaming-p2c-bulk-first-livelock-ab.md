# A/B — P2c bulk-first prefetch discipline (init livelock fix, chain 78)

## Parcel

`art-streaming-p2c-t11-bulk-first-livelock` — fixes a black-screen init LIVELOCK found on
the 41-page stress-art fixture's acceptance run (controller, 2026-08-09).

## Symptom (ground truth from the acceptance run)

Init never completes on the 41-page fixture: `Dbg_PageIn_Preempts`/`Resumes` climb linearly
forever (~1/frame, every preempt resumed), `Dbg_PageCache_Demands` stays 0, no red screen (no
thrash, no watchdog — no demand stall exists), the display never enables.

## Root cause

`Level_LoadArt` bulk-loads the whole pool and spins a drain-wait on queue-empty + idle. But
`PageCache_Prefetch` runs every `PageIn_Process` tick (from `VSync_Wait`) during that spin, and
with the pool (41 pages) > `PAGE_FRAMES` (15) each prefetch landing evicts an LRU page whose
ahead-strip references then get re-scanned and re-requested — a prefetch<->evict cycle that
never drains. The chain-74 demand-first yield only engages on `Cache_Art_Stall`; the init drain
has no stall, so prefetch free-runs. (OJZ never hit this: all pages fit, prefetch found
everything resident.)

## Fix (bulk-first discipline — mirror of demand-first)

1. **`PageIn_Bulk_Drain` flag** (engine/ram.emp — consumes the former word-align pad byte, so
   the RAM layout is unchanged): `Level_LoadArt` sets it around its bulk enqueue + drain-wait
   and clears it once the drain reaches quiescence (before the display comes on);
   `PageCache_Init` clears it defensively across an act reset. `PageCache_Prefetch` returns
   early while it is set — the exact mirror of the existing `Cache_Art_Stall` demand-first
   early-return, one flag spanning the whole bulk load (so act-transition reloads are covered
   too).
2. **Prefetch ahead-target baseline** (engine/level/tile_cache.emp): the per-frame
   `Tile_Cache_Fill` scan sets `Cache_Pfx_Row/Col_Target`, but `PageCache_Prefetch` (frame-top,
   from `VSync_Wait`) can fire on the FIRST gameplay frame before that scan runs this act.
   Seed the `$FFFF` "axis-inactive" sentinel in `FillAll`'s section reset (before display-on),
   so a pre-first-fill prefetch reads "no target" and skips instead of scanning a RAM-init 0 as
   a live block coordinate. (Second latent issue the controller flagged; verified: the scan
   guards on `== $FFFF`, and the sentinel was previously only written by the per-frame scan.)

## Byte impact (streaming-path code — present in every shape)

| shape | before (chain 77) | after (chain 78) | Δ |
|---|---|---|---|
| `s4.bin` | d9e6a30a / 414325 | f8561c7c / 414341 | +16 |
| `s4.debug.bin` | 8e98b4b4 / 427910 | 2afa70a9 / 427926 | +16 |

`PageIn_Bulk_Drain` reuses the existing pad byte, so `Engine_RAM_End` and all RAM addresses are
unchanged; only the four code sites move ROM bytes (both shapes, +16 B).

## Verification

- Both canonical shapes rebuild green.
- Acceptance re-run (controller) confirms init completes on the 41-page fixture — the drain now
  reaches quiescence (`PageIn_Bulk_Drain` suppresses the prefetch refill), display enables.
- refreeze chain 78; full-rom + repin-staleness gates green.
