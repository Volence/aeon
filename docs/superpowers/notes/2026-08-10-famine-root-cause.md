# STRESS_EVICT famine — root cause (2026-08-10)

Workstream 3 of the 2026-08-09 handoff: confound resolution → clean A/B →
root cause. NO fix shipped (per ruling: fix design folds into C4-3).

## 1. The prebatch "unresponsive scene" confound: methodology, not build

On prebatch `517bff40` (STRESS_EVICT, chain-80 sigil binaries — the current
binaries refuse that tree: blob 5933 vs expected 6255, the stale-binary gate
trap), the stress scene responds to LIVE input perfectly: camera 96 → 752 px
over right×90 (~7.3 px/f), demands/prefetches counting. The 2026-08-09 session's
"camera parked at 96px, zero counters, player suspended" is exactly what an
armed `Input_Source=1` playback produces: `Input_Tick` OVERWRITES the live pad
from the stream, and a foreign/desynced fixture on DEBUG raises
`REPLAY DESYNC`/`REPLAY BAD OPCODE` → the game's own error screen (frozen
`Logic_Tick`, `running=true`) — the known triage trap. Lesson re-confirmed:
after arming playback for the replay net, RESET/clear `Input_Source` before any
live-input experiment, and check `status.symbol_at_pc` before concluding
"unresponsive".

## 2. Clean A/B: the famine PREDATES patch-run batching

Same drive (single live right×90 from settle) on both builds → same raise:
`PageCache_AllocFrame: no free/evictable frame (thrash bug)`, caller
`PageIn_Process.no_base_check+22`.
- prebatch 517bff40: 2 demands / 6 prefetches at raise
- master (2026-08-09 intel): 2 demands / 8 prefetches, stall-watchdog 6
Patch-run batching neither caused nor meaningfully changed it. The
"batching-regression" question is CLOSED.

## 3. Root cause: pinned+transient concurrent need exceeds the stress clamp

Frozen-trap frame table (prebatch, identical shape expected on master):

| frame | page | refcount | flags |
|---|---|---|---|
| F0 | 0 | $9E | PINNED |
| F1 | 1 | $3F | PINNED |
| F2 | 9 | 0 | PINNED |
| F3 | 3 | $0E | — |
| F4 | 4 | $38 | — |
| F5 | 2 | $0D | — |
| F6 | 5 | $3A | — |
| F7 | 6 | $0B | — |
| F8 | 8 | 0 | PINNED |

PageIn queue head at raise: **page 7, demand class**.

- Pinning is BUILD-TIME (`ojz_strip_gen.py::mark_pinned_pages`: page 0 always +
  any page referenced by ≥ 75% of sections → OJZ act1 pins 4 of its 10 pages).
- Pinned frames are never eviction candidates, even at refcount 0 (pages 8/9
  arrived via right-direction prefetch and permanently seized 2 frames).
- Every non-pinned frame holds a transient page (2-6) with a LIVE refcount —
  the visible cache window genuinely spans 5 transient pages in the dense
  strip. No refcount leak, no eviction bug: eviction correctly finds zero
  candidates.
- Concurrent need at the famine window = 4 pinned + 6 transients (2..7) = 10
  frames vs STRESS_EVICT_FRAMES = 9. **The famine is deterministic capacity
  arithmetic**, which is why it fires EARLY (single burst) with tiny counters,
  not after runaway thrash. Release PAGE_FRAMES = 15 → 11 transient frames ≥ 6
  — ample margin; release also degrades to camera-hold instead of raising.

## 4. Where the fix design goes (C4-3 — queued for design, not built here)

The C4-3 famine-handling question now has its concrete bound: the fixture (and
any future act) must respect `frames >= pinned_pages + max_simultaneously_
referenced_transients (+1 for the in-flight demand)`. Options for the design
pass, in the order they look attractive from here:
1. **Build-time bound emission:** the strip generator already knows per-window
   page spans — emit `MAX_CONCURRENT_PAGES` per act and `ensure` the clamp
   (and release PAGE_FRAMES) against it. Turns famine into a build error.
2. **Prefetch admission control:** don't page-in far-ahead PINNED pages while
   free+evictable ≤ demand-window need (pages 8/9 seized frames early here).
3. **Famine handling beyond camera-hold** for the mega-act goal (the original
   C4-3 question) — demand-time degrade instead of DEV raise.
`tools/evict_witness.py` Phase 2 keeps reporting the famine as a known open
debt until the C4-3 design lands; STRESS_EVICT_FRAMES=9 stays as-is (it is
doing its job: it found a real bound).

## Repro crib

`STRESS_EVICT=1 ./build.sh` → s4.stress.bin; boot, wait out OJZ init (~12 s),
single `press right ×90` from settle → raise. Prebatch needs chain-80 sigil
binaries (worktree build of sigil `bb500005`).
