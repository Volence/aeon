# Art-streaming P2b Task 7 — golden re-freeze evidence (chain 68)

**Parcel:** eviction live + trailing-lag-gated page prefetch + demand-page eviction
protection + the `STRESS_EVICT` forced-eviction dev fixture (completes P2b).

## What moved the goldens

All canonical/off-canonical sonic4 shapes carry engine `page_cache` / `page_in` /
`load_art` code, so the Task-7 code re-emits them. The `STRESS_EVICT` define was added
to every profile's `emp_defines` at value **0**, where `PAGE_FRAMES_CLAMP == PAGE_FRAMES`
— **byte-inert**: the profile-plumbing addition alone moves nothing; only the Task-7
code does.

## Build-level evidence (this session's ceiling — the behavioural soak is the controller's)

Three shapes built green against the chain-68 sigil binaries:

| shape          | ROM             | crc       | bytes  |
|----------------|-----------------|-----------|--------|
| release        | `s4.bin`        | ed57293f  | 414081 |
| DEBUG          | `s4.debug.bin`  | 61ceedbf  | 427336 |
| STRESS_EVICT   | `s4.stress.bin` | e8b34e9f  | 427336 |

**Fixture isolation.** `s4.debug.bin` vs `s4.stress.bin` differ in **exactly two bytes**:
the header checksum (`$18F`) and the single free-list-terminator displacement byte inside
`PageCache_Init` (`$76E4`). The clamp is `PAGE_FRAMES_CLAMP = 6` under STRESS_EVICT vs
`= PAGE_FRAMES (15)` otherwise — a lone immediate/displacement, no size change (both ROMs
are 427336 B, so the DEBUG frozen size table resolves the stress shape directly; the
`stress_evict` profile is **UNFROZEN** — no golden, not a refreeze/`shipped_shapes`
target).

**Listing sanity (s4.debug.lst):** `PageCache_Prefetch` @ 0x7A0C (`.scan_block` @ 0x7AAE);
`PageIn_Process` D3 gate at `.gate_reset`/`.start` (0x73F0/0x73F4). Soak counters:
`Dbg_PageCache_Prefetches` @ FFFF8A2C, `Dbg_PageIn_PfxSkips` @ FFFF8A2E; own-lag latch
`PageIn_Last_Frame` @ FFFFB4BE, `PageIn_Prev_Lagged` @ FFFFB4C0,
`PageIn_Pfx_Skip_Armed` @ FFFFB4C2, `Page_Pfx_Budget` @ FFFFB4C4.

## Behavioural gate (controller-owned, pending — Task 7 Step 6)

`STRESS_EVICT=1 ./build.sh` → `s4.stress.bin`, oracle: 3+ full max-scroll circuits both
directions + vertical + diagonal. Gates: zero wrong-tile frames during motion, audit
assert clean throughout, no deadlock in the demand-stall path, `Dbg_PageIn_Preempts`
climbing, lag bounded (clamp-frame counts recorded, not gated until Task 10's camera
gate). The demand-page eviction protection is designed in (a demand page stays out of
the LRU until its first `Ref`), not relied upon to surface in the soak.

## Chain 69 — soak-found prefetch defect + fix

**Symptom (controller soak, first seconds of gameplay):** DEBUG assert
`assert.b d2 eq #ART_VER_ZX0, Got 00` at the ZX0-form dispatch — a prefetch-requested
`page_id` strided off the 10-entry manifest (`pm_source` garbage → wrapper version 0).
Counters at halt: `Dbg_PageCache_Prefetches=22`, `Dbg_PageCache_Demands=0`.

**Root cause (candidate d, confirmed by data):** the OJZ per-section local→global maps
top out at global index 611 (page 9), so a valid translated pool word can only yield
page 0..9 — Task 6 rendering proves every *displayed* block is valid. `PageCache_Prefetch`
derives page ids from *speculatively-probed* staged-slot words (ahead-strip blocks, some
never displayed) **without validating them against the live pool**, so a word that is not
a real translated pool reference produced page ≥ `act_art_pool_pages`; `PageCache_Request`
then strided `page*sizeof(PageManifest)` past the table into adjacent ROM.

**Fix (both, page_cache.emp):**
1. `PageCache_Prefetch.scan_block` enforces the pool-bounds invariant — `page >=
   act_art_pool_pages` is a scan artifact and is **silently skipped** (`a3 =
   Current_Act_Ptr` carries the count across the loop). Speculation must never off-manifest.
2. `PageCache_Request` gains the loud backstop: a page id ≥ `act_art_pool_pages`
   **DEBUG-raises** (`raise_error`, a real bug for any non-speculative caller) and
   **release-skips** (silent no-op). A prefetch/demand can no longer walk off the manifest.

Rebuilt green: `s4.bin` crc=e3ed767b (414103 B), `s4.debug.bin` crc=81977270 (427376 B),
`s4.stress.bin` crc=1d76f638 (427376 B). Fixture isolation intact (debug↔stress differ
only in the clamp byte @0x76E3 + the checksum word). Re-soak pending.
