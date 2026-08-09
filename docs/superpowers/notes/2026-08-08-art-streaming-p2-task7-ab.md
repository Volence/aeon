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
only in the clamp byte @0x76E3 + the checksum word).

## Chain 70 — soak crash #2: corrupt manifest base at the gameplay dequeue

**Re-soak (chain 69):** crash reproduced identically — a valid page id (< 10, passed both
bounds guards) resolved to a garbage `pm_source` (wrapper version 0). Falsifies the
scan-artifact theory: the defect is the RESOLUTION CONTEXT, not the id.

**Analysis (static, via capstone disasm of the whole residency cache):** every routine
(dequeue, AllocFrame, LRU link/unlink, Ref/Unref, Publish, Prefetch) is individually
correct. The act descriptor is intact (`act_art_pool_table`=0x14FAC, `pages`=10); the
manifest ends exactly where the descriptor begins. The crashed `pm_tiles`=476 (from
`d1=0x3B80=476<<5`) is NOT anywhere in the ROM manifest region for any small page —
so `PageIn_Pool_Table` (the cached manifest base) was corrupted to a RAM value at
gameplay. **Init works because init dispatch runs BEFORE `Current_Act_Ptr` is set and
uses the freshly-written cache; gameplay is the first dispatch after a stray write
corrupts the cache.** Task 6 never ran the gameplay dequeue at all (pool fully resident,
no page-in), so the latent corruption was invisible until STRESS_EVICT forced eviction.

**Fix (robust, chain 70):** the dispatch (page_in resolve) and `PageCache_Publish` now
derive the manifest base from the IMMUTABLE act descriptor (`Current_Act_Ptr ->
act_art_pool_table`), NOT the corruptible cached `PageIn_Pool_Table`. The init bulk load
(when `Current_Act_Ptr` is still null) falls back to the freshly-set cache. Added: a
DEBUG resolve guard `PageIn_Cur_Page < act_art_pool_pages` (raise + release-skip), and a
DEBUG counter `Dbg_PageIn_BaseCorrupt` (@FFFF8A30) that increments when the cached base
disagrees with the descriptor — confirms whether the cache is being corrupted (root-cause
locator for the stray-writer hunt) while the soak runs on the robust base.

**CAVEAT for the controller:** this eliminates the cached-base corruption VECTOR (the
evidence-consistent cause), but the stray WRITER itself was not pinned statically (no
live-RAM access here). On the re-soak, read `Dbg_PageIn_BaseCorrupt` (@FFFF8A30): if >0,
the cache IS being corrupted (confirmed) and the writer still needs hunting — read
`PageIn_Pool_Table` (@FFFFB4BA) vs the descriptor base (0x14FAC) at that point. If the
`PageIn_Cur_Page >= pages` DEBUG assert fires instead, the corrupt target is the id, not
the base. Rebuilt green: `s4.bin` crc=6eca5ade (414219 B), `s4.debug.bin` crc=6fb633ff
(427549 B), `s4.stress.bin` crc=8c9e791f (427549 B).

## Chain 71 — CASE CLOSED by the controller's live reads: two plain bugs, no corruption

Live reads on the halted machine debunked ALL three "corruption" theories:
1. **`Current_Act_Ptr` = 0 during gameplay.** My assumption that `Section_Init` sets it
   for the dispatch was false in this scene (it read null), so the chain-70 descriptor
   path never ran (`Dbg_PageIn_BaseCorrupt`=0) — the fallback was taken every dispatch.
2. **`PageIn_Pool_Table` = 0x14FAC — CORRECT, uncorrupted.** The garbage base came from a
   resolve reading off the wrong context (null act ptr → fallback), not a stray write.
   `d1=0x3B80`/`pm_tiles`=476 etc. were fields read from the wrong base — noise.

**Fix (chain 71) — remove the whole flaky vector:**
- **`Level_LoadArt` binds the act context at the START of level init:** sets
  `Current_Act_Ptr` (before any page-in, not deferred to `Section_Init`) AND stores the
  pool page count in a new RAM word `PageIn_Pool_Pages` (@FFFFB4C0).
- **The entire streaming hot path now reads the STORED, correct values** —
  `PageIn_Pool_Table` (base) + `PageIn_Pool_Pages` (id bound) — with **zero
  `Current_Act_Ptr` dependency**: the page-in resolve, its page-id guard, the page
  prefetch's pool-bounds skip, and `PageCache_Request`'s backstop all switched from
  `Act.act_art_pool_pages(Current_Act_Ptr)` to `PageIn_Pool_Pages`. The chain-70
  descriptor-derivation + fallback in the resolve/Publish is deleted; both read
  `PageIn_Pool_Table` straight through the symbol (verified in the binary: resolve reads
  `$b4bc`, guard `$b4c0`, prefetch/Request `$b4c0`).
- The dispatch page-id guard now runs BEFORE `AllocFrame` (no frame leak on a bad id);
  DEBUG raises, release drops. `Dbg_PageIn_BaseCorrupt` kept as a DEBUG integrity monitor
  (Pool_Table vs the now-bound Current_Act_Ptr base) — should stay 0.

Rebuilt green: `s4.bin` crc=0b8fa9ec (414138 B), `s4.debug.bin` crc=ca9bbd3f (427468 B),
`s4.stress.bin` crc=c8493cbf (427468 B). Third soak expected to run.
