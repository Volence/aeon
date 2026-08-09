# Art-Streaming Phase 2 — lens panel adjudication packet

**Panel (2026-08-09):** ratified 2026-08-01 composition over the P2 merge diff
(merge-base `97417bcf` → merge `2f047e3`, + follow-up `1aaf7bc`, reviewed at master
`73f2bde`): A (ceremony) · A2 (comment truth) · B1 (construct reuse) · B2
(cross-file dup, code-first) · C1 (instruction perf, reverse walk) · C2
(gate-blind hazards, forward) · C3 (hardware timing, handler-first) · C4
(algorithmic altitude) · C5 (space/footprint) · +vacuity/gate-coverage (the
standing bar minted after the 08-01 sweep, seated tenth). Single seats with
walk-order variation encoded across the C tier (merge-scale scope, not the
118-file corpus). Overseer own-verified every Section-1 load-bearing citation
before this packet: MRU tail-pop + tail-append, the `$07FF` global mask vs the
generator's explicit >2047 contract, the raw-path frame leak + ZX0-path frame
retention asymmetry, the size-0 tripwire ordering, the one-slot 128KB-split
carry-clear exit, `run_tests()` omitting the five stress-uniquify tests with no
pytest config anywhere, and the `Art_Decompress` caller census.

**Headline verdict.** The §9.7 core is genuinely sound: the VBlank bookmark
protocol survived five adversarially-chosen interrupt interleavings (C3, C2
independently), the ZX0R resumable decoder is instruction-level-faithful to the
golden blocking decoder with complete banked state, admission disciplines and
the DMA budget integration traced clean, comment arithmetic verified ~95/95
claims (A2), and the merge is unusually disciplined about house constructs (B1:
zero transliteration fossils). The actionable set clusters in four places: an
inverted eviction policy, a representational ceiling that contradicts the
design's own scaling premise, a raw-form-path correctness cluster, and a
tooling-gate layer thinner than the acceptance record claims.

**Seat conflict resolved:** A's A12 ("`Art_Decompress`/blocking `ZX0_Decompress`
have no release-shape caller") CONFIRMED by caller census; C5-10's contrary
"live via BG path" claim REFUTED (no such call site exists — the retention note
in the header was misread as a caller).

---

## SECTION 1 — fix parcels (byte-changing unless noted)

- **F-1 · Eviction end inversion (CONFIRMED ×2 seats + overseer; S).**
  `PageCache_AllocFrame` `.from_lru` pops `Page_LRU_Tail` (`page_cache.emp:237`)
  while `LruLinkTail` appends newly-evictable frames at tail — MRU/LIFO
  eviction, the recency-inverted policy, contradicting the file's own van
  Waveren LRU citation. A just-published prefetch frame is the *next* victim
  before its fill ever refs it; camera reversal faults on the page evicted
  seconds ago. Consistent with (and a plausible driver of) the chain-74/77/78
  churn bugs that were each mitigated downstream with gating flags. Dormant on
  shipped OJZ (everything pins). Minimal fix: pop `Page_LRU_Head` (one
  instruction + comments; the demand-protection invariant is end-agnostic).
  Preferred end-state (C4-3, M-size follow-up): replace the doubly-linked list
  wholesale with a `pf_unref_stamp` + O(15) min-scan at eviction — deletes
  LruUnlink/LruLinkTail/PF_IN_LRU/audit-arm and fixes the policy by
  construction (wraparound via unsigned delta compare). RULING WANTED on
  one-line-now vs stamp-rework-now; recommend one-line now, stamp rework as its
  own parcel.

- **F-2 · Raw-form correctness cluster (CONFIRMED; S-M).** Four defects, one
  parcel, all raw-path (OJZ ships zero raw pages today; STRESS_ART and any
  future act elect them):
  (a) *Frame leak on landing rejection* (`page_in.emp` `.raw` carry path):
  re-enqueues the request and `rts` without freeing/retaining the allocated
  frame — detached (pf_page $FFFF), invisible to the orphan audit by design,
  unrecoverable until PageCache_Init; a handful of occurrences starves
  AllocFrame into `.thrash` → in release, permanent camera hold + stale art.
  Fix: mirror the ZX0 `.land_full` shape — retain `PageIn_Cur_Frame` across the
  retry (or free the frame on rollback).
  (b) *Half-landed page published resident* (128KB split, `dma_queue.emp`
  `.split` one-slot path → `.finish_entry` → carry CLEAR; the dma_queue header
  ledgers this edge as this plan's unfinished rollback work): a raw blob
  straddling a 128KB ROM boundary with one free slot lands only its first half
  and publishes. Fix: generator-side straddle avoidance + `ensure` (cheapest),
  and/or reject-both-halves when only one slot is free (compute-then-commit
  idiom already present for the byte cap).
  (c) *Size-0 tripwire mis-wired* (`page_in.emp:226-227`, pre-Task-6 leftover):
  fires after AllocFrame → leaks the frame + strands the queued-bit claim.
  Re-point it before allocation (or delete: `verify_level_bin.py` enforces
  nonzero tiles).
  (d) *DEBUG evenness assert on raw `pm_source`* (the `lsr.l #1` silently drops
  bit 0) + extend `Level_LoadArt` `.drain_wait` to cover queued raw landings
  (C2-C9/C3-5).

- **F-3 · The 2048-tile representational ceiling (CONFIRMED; RULING REQUIRED —
  this is a design-direction bet).** The staged-word path carries GLOBAL tile
  indices in 11-bit nametable fields: `.translate_slot` masks the u16 global
  with `$07FF` (`tile_cache.emp:339`), and PatchWord/Prefetch/audit all decode
  `page = word11 >> 6 ≤ 31`. The generator's contract states the opposite
  ("the GLOBAL pool may exceed 2047 tiles", `ojz_strip_gen.py:627`), §9.7
  claims "capped by ROM not VRAM", and the 2600-tile stress fixture was chosen
  *because* it crosses the 2048 line — so ~550 clone references alias into
  pages 0-8 and pages ≥32 are unrepresentable/never-requestable. Silent in
  every shape. Two rulable shapes:
  (i) **Merge-translation** (C4-2 strong form): delete `.translate_slot`;
  translate local→global inside PatchWord (section map ptr is already threaded
  to the copy sites); global lives only in registers at full u16 width;
  physical (≤959) always fits the field. Lifts the ceiling entirely (mega-act
  premise preserved), deletes a 256-word pass per staged block. M-L parcel,
  touches the "staged words are GLOBAL" invariant everywhere it's documented.
  (ii) **Scope-and-guard**: loud generator failure + engine `ensure` at 2048;
  §9.7 claim re-scoped to "capped at 2048 deduped tiles/act"; stress fixture
  shrunk below 2048 (voiding the >32-page acceptance axis). S parcel, caps the
  mega-act.
  Either way: **the acceptance evidence needs a re-run** — the recorded
  "zero wrong tiles" soaks used the pre-1aaf7bc fixture AND the >2048 fixture
  the engine provably truncates; 1aaf7bc's fix is generator-only and cannot
  have fixed the engine half (its verification was a data-level audit, not an
  on-screen retest). See M-5.

- **F-4 · Gate hardening (CONFIRMED; M).** The tooling-gate layer, per the
  vacuity seat + convergent B2/B1/C5 findings:
  (a) `verify_level_bin.py` is content-blind — ZX0 pages checked 4-byte-wrapper
  deep, raw pages length-only (always 2048 for full pages = zero discriminating
  power). Add decode-and-compare (or content hash) of every elected artifact
  against its `.bin`; byte-equality for raw. This is THE drift gate for a tree
  the build cannot re-derive.
  (b) `art_rom_report.py` exits 0 on zero pools found and reports "0 pages ok"
  on regex drift — the budget watchdog dies silently on exactly the likely
  change class. Fail on pool-file-exists-but-zero-parsed and on zero pools;
  implement (or delete the docstring claim of) the JSON-sidecar cross-check
  (dead `import json`); fold the 3.3 KB of local maps + manifest into the
  gated number (C5-9a).
  (c) The five `test_stress_uniquify_*` tests are dead under every automated
  invocation (`run_tests()` omits them; pytest can't collect the file). Wire
  them into `run_tests()`. The T11 AB note's recorded "pytest tools/ -q green"
  verification could not have executed them — annotate the note.
  (d) `regenerate-level.sh` prints the verifier's name but never runs it — run
  it (the one moment the tree actually changes).
  (e) ZX0R equivalence-walk liveness: count pages actually equivalence-tested,
  raise/report on zero (a raw-election shift silently zeroes ZX0R coverage).
  (f) Pinned-bit cross-check: `verify_level_bin.py` captures `pm_flags` and
  discards it; nothing ties .emp pinned bits to the sidecar's `pinned`.
  (g) Sec local maps: add size/content pinning + a nametable-index-range vs
  map-entry-count consistency check (a re-bake committing `blocks.bin` without
  its `local_map.bin` currently renders garbage with all gates green).

- **F-5 · Build-time tripwire parcel (CONFIRMED ×2-3 seats; S, byte-neutral).**
  `ensure(sizeof(PageManifest)==8)` + `ensure(sizeof(PageInReq)==4)` beside the
  literal-shift stride sites (house pattern, done for PageFrame, missed for
  both new structs); derive `PageIn_Flush`'s hand-unrolled eight `clr.l`s from
  `PAGE_TABLE_MAX` (or `ensure` the unroll); derive/`ensure`
  `Page_Audit_Snapshot`'s 52 and the writer's bare 16 from `PAGE_FRAMES`
  (silently truncating already on the 41-page fixture); blank-word/frame-0
  assumption gets a DEBUG assert or an Init-ordering `ensure` (C2-C8).
  Ride-alongs: use `NT_TILE_MASK`/`NT_ATTR_MASK` in `.translate_slot` (if it
  survives F-3), `PGRQ_DEMAND_BIT`/new `ART_PAGE_FLAG_PINNED_BIT` at the two
  `btst #0` sites, `BLOCKS_PER_SECTION_SHIFT` naming in `PageCache_Prefetch`.

- **F-6 · Dead code (CONFIRMED; S).** Delete `PageCache_Lookup` (zero callers
  repo-wide). RULING WANTED on `Art_Decompress` + blocking `ZX0_Decompress`:
  sole callers are the DEBUG selftest; either DEBUG-gate the pair with their
  consumer or record a ruling that release ships them (the header documents
  retention as deliberate — but §1.7 says release carries none of the
  equipment).

- **F-7 · Comment-truth + doc sweep (S-M, byte-neutral).** The A/A2 catalog,
  worst first: the `AllocFrame` call-site comment asserting a d3/a4 clobber
  that would sanction breaking the path's own a4-live contract
  (`page_in.emp:196`); the pre-chain-77 "VInt_Level reloads the budget" claim
  in two files (`structs.emp:45`, `page_in.emp:458`) contradicting vblank's
  correct "NOT here"; the retired `POOL_TILE_CEILING` guard cited as live
  protection (`ojz_strip_gen.py:1743,1870`); three mutually inconsistent
  `Level_LoadArt` liveness sets (real set: a4/d5-d7); the stale "raw ROM
  block" staged-pointer option that breaks the translated-GLOBAL invariant
  narrative (`tile_cache.emp:178`); load_art's pre-P2 "fully resident for the
  life of the act" header; the repin span comment predating page_cache's
  insertion (`page_in.emp:63`); the movem-to-absolute "no assembler support /
  needs scratch register" hardware falsehood (`ram.emp` bookmark block) —
  rewrite as a sigil gap and FILE THE SIGIL ASK (C1-3: ~92 cycles/preempt
  recoverable if sigil gains the encoding); STRESS_EVICT "4 dynamic" vs the
  shipped 9-frame/5-dynamic config; `PageCache_Lookup` "~10 cyc" (real ~42);
  DEFERRED_WORK's four stale "merge pending" rows; ARCH §2.2/§2.5/§2-graph
  prose still describing the deleted init-time pipeline (8 KB staging /
  Critical DMA / `page<<13` fixed slots / REGION1 build-time cap) — reconcile
  with the shipped §9.7 reality; §9.7's phantom `ZX0R_Start` symbol and the
  pin-vs-refcount conflation; chain-narration curation per the house
  present-tense rule (keep the invariant *why*, drop the incident log).

## SECTION 2 — measure first (oracle, foreground; lag counter is ground truth)

- **M-1 · PatchWord per-word cost (C1-4/C1-7 ≡ C4-4, independently derived
  ×2).** Estimated ~400-500 cycles/word in the steady-state fill loops
  (~50-80K cycles/frame at 16 px/frame — over half the frame), vs the recorded
  `Lag_Frame_Count = 0` soaks. The estimates and the soak record cannot both
  describe the same regime — construct a sustained max-speed scroll (and the
  diagonal), read the lag counter + profiler, and only then decide on the
  site-specialized inline-patch rework (which removes calls; both seats agree
  on the fix shape if real). Do NOT retune blind.
- **M-2 · Prefetch residency scan (C1-9 ≡ C4-5).** Up to 256 words × ~100
  cycles per staged ahead-strip block per moving frame, no memo, no
  fully-resident early-out. The Tier-1 fix (latch
  `pool_pages <= PAGE_FRAMES` at load, early-out Prefetch) is cheap and
  deletes the whole cost on all shipped content — take it as a fix parcel
  ride-along; the bitset/memo rework for streaming acts is measure-first.
- **M-3 · ZX0R copy unroll (C1-10).** 2× unroll ≈ −10K cycles/page,
  contract-safe per the seat's banking analysis; measure decode-slice/fault
  latency before and after.
- **M-4 · Form election by residency class (C4-6).** Split the ZX0/raw
  threshold on the `pinned` bit the sidecar already carries (pinned: keep 10%;
  evictable: much higher bar or raw). Needs the demand-fault-per-page
  histogram (`Dbg_PageCache_Demands`) from a real streaming act first.
- **M-5 · Stress-fixture visual re-verification (feeds F-3).** Run STRESS_ART
  at master, oracle-inspect cells referencing clone slots ≥2048: truncated
  cross-texture tiles confirm C4-2/C2-C1 on-screen and formally void the
  >32-page acceptance axis until F-3 lands; also re-run the visual matrix legs
  post-1aaf7bc (the recorded runs predate it — B9).
- **M-6 · Byte-cap down-counter (C1-2).** ~24 cycles/enqueue on the hot admit
  path; small enough to fold into F-2/F-5 if desired.

## SECTION 3 — recorded-evidence corrections (no code)

- The T11 note's pytest citation (F-4c) and the pre-1aaf7bc visual-matrix
  caveat (M-5) get annotations in their AB notes.
- The plan's "idle-minima floor via DEBUG state counters" acceptance row was
  never built and never measured (no such counter exists) — either build it
  (one Dbg word + VSync_Wait stamp) or strike the row with a note (B8).
- `characters_staging/` (~515 KB Tails/Knuckles data + generator) rode this
  merge with zero ROM effect — provenance-note it in the P2 execution memory
  (C5-10).

## Clean-by-panel (for the record)

Bookmark protocol interleavings (×2 seats); ZX0R state completeness + stack
discipline; Z80/VDP bracket discipline (zero new touchpoints outside existing
brackets); VBlank budget arithmetic incl. the closed last-entry-overshoot
class; RAM/struct layout + alignment (compiler-checked, one wrong comment);
teleport-rebase interaction (no flush needed, correct); camera hold bounds
outrun by construction (worst case = hitch, never wrong art — modulo C2-C4's
narrow publish-before-land transient under budget pressure, filed in F-2's
neighborhood as a watch item); comment arithmetic (~95 claims recomputed, A2);
no mulu/divu; no branch-sizing debt (sigil auto-sizes); Z80 footprint zero
(verified by diff sweep); dead-ROM sweep clean; generator dedup/ordering
right-sized; `art_rom_report` measures the right quantity at the right place
(its liveness holes notwithstanding).

## FIXUP ROUND (2026-08-09, branch fix/p2-lens-fixup)

Shipped same-day, four commits, all shapes green (sonic4 debug+plain, demo,
STRESS_EVICT):

- **F-1** — evictor pops `Page_LRU_Head` (was tail = MRU). One-line shape;
  the C4-3 stamp rework stays open as its own parcel.
- **F-2** — raw cluster: `PageCache_FreeFrame` B&R rollback on the raw carry
  path; dma_queue `.split_reject` (a one-slot 128KB split now rejects BOTH
  halves, carry set, byte charge rolled back); dispatch resolves the manifest
  BEFORE AllocFrame (size-0 drop holds no frame, releases its queued-bit
  claim; corrupt-id drop releases too, bounds-guarded); DEBUG evenness assert
  on raw `pm_source`.
- **F-4** — verify_level_bin decodes every ZX0 page (salvador -d) and
  byte-compares vs .bin, raw pages byte-compare, pinned bit cross-checked vs
  the JSON sidecar, per-section local-map/dict-block consistency check; both
  new checks MUTATION-TESTED (page5.zx0 byte-100 XOR → FAIL; sec1 map
  truncated → FAIL; both restored). art_rom_report fails on zero
  pools/zero-parsed pages, cross-checks the sidecar page count, counts local
  maps + manifest into the budget (OJZ 11.8 → 15.0 KB), errors on malformed
  env. ojz_strip_gen run_tests() now calls ALL 22 tests (12 were dead — more
  than the panel found); regenerate-level.sh runs the verifier.
- **F-5** — `sizeof` ensures for PageManifest (×2 sites) + PageInReq; flush
  unroll pinned to PAGE_TABLE_MAX; audit snapshot geometry ensured vs
  PAGE_FRAMES; named-constant swaps (NT masks, PGRQ_DEMAND_BIT, new
  ART_PAGE_FLAG_PINNED_BIT).
- **F-6** — `PageCache_Lookup` deleted. (Art_Decompress retention still open
  for ruling.)
- **F-7** — full comment/doc truth sweep applied, byte-neutral (debug crc
  a93785aa unchanged before/after).
- **M-2 Tier-1** — `PageIn_Fully_Resident` latch + Prefetch early-out
  (verified live on hardware state: latch = $FF on OJZ, streaming clean).

Oracle verification (fresh instance, ROM CRC-matched to the build each time):
DEBUG boot selftest passes; at-rest + mid-motion renders clean across ~180
frames of scroll into new terrain; `Lag_Frame_Count = 0`;
`Dbg_PageCache_Demands = 0` on the canonical shape. STRESS_EVICT fixture
boots + streams under the flipped evictor.

**NEW FINDING P-1 (pre-existing, found by the fixup's A/B): STRESS_EVICT
reference famine on reversal.** Input right×180 → left×120 from spawn drives
the fixture into `AllocFrame .thrash` ("no free/evictable frame") — all 5
dynamic frames simultaneously referenced/held at the reversal point. The
IDENTICAL input thrashes the PRE-fix master build the same way (A/B verified,
same raise, same call path) — a reachable famine state the recorded soaks
never hit, NOT a fixup regression. In release this path degrades to
requeue + camera hold; whether the hold can deadlock against refs the frozen
fill never releases is exactly the C4-3/streaming-act question. Feeds the
F-3/mega-act work: real streaming acts need a frames-vs-max-simultaneous-
referenced-pages bound, or famine handling beyond the hold.

Still open: F-3 (2048 ceiling — RULING), F-6 retention (RULING), F-1 stamp
rework, F-4(e) ZX0R-walk liveness cross-gate, M-1/M-3/M-4 measurements, M-5
stress visual re-verification.

## Recommended order

F-1 (one-line flip) → F-2 (raw cluster) → F-5 (tripwires) → F-6 (dead code) →
F-4 (gates) → M-5/M-1/M-2 measurement session (one oracle sitting) → F-3 per
ruling (+ C4-3 stamp rework if ruled) → F-7 (comment/doc sweep) → M-3/M-4/M-6
as measured.

## RULINGS (closed 2026-08-09)

- **F-3: option (i), merge-translation** — user-ruled ("let the mega-act
  live"). The against-case is sequencing, not design: +1 u16 read per patched
  word in the hot loop (more than repaid by deleting the 256-word per-block
  translate pass), invariant-comment churn, and the loop being M-1's
  measurement target. INTERIM (landed same day): ojz_strip_gen refuses to bake
  a non-stress act past 2048 deduped tiles; the stress fixture bakes with a
  loud known-invalid warning on its >32-page axis.
- **F-6: DEBUG-gate the pair** (overseer-ruled per §1.7). Implementation
  reality: Art_Decompress is load_art's SECTION HEAD-LABEL in the map's union
  order, so the clean gate is a byte-shifting parcel with the sigil
  repin/refreeze ritual — folded into the wave below rather than paid alone.
- **F-1: stamp rework YES** (overseer-ruled, clean-not-bolted-on) — replace
  the linked LRU with pf_unref_stamp + O(PAGE_FRAMES) eviction scan; deletes
  LruUnlink/LruLinkTail/PF_IN_LRU/audit-arm and makes the policy structural.

**Execution shape: ONE parcel wave** — M-1/M-5 measurement session first (one
oracle sitting, constructed worst frames + stress visual), then
F-3 merge-translation + F-1 stamp rework + F-6 gating together (same files,
one byte-shifting repin/refreeze ritual, one stress re-verification), then
M-3/M-4/M-6 as the measurements direct.


## WAVE + FINAL PANEL (2026-08-09, second sitting)

**Wave executed and merged** (aeon `3e7a1c7`, sigil `75c6f979`): F-3
merge-translation (2048-tile ceiling GONE — 2600-tile STRESS_ART fixture
oracle-verified rendering correct art under churn: 2 demands / 18 prefetches /
evictions live / lag 0 / audits silent), F-1 stamp eviction (list machinery
deleted, policy structural), F-6 (blocking decompressors live with their DEBUG
consumer; release: real code −144 B, deb2 appendix −436 B). M-1 MEASURED with
the oracle profiler: PatchWord ~162 self / ~235 inclusive cycles per word —
the review's ~500 estimate was 2x pessimistic; max-diagonal fill ≈ half a
frame, consistent with recorded lag=0. Cross-repo ritual end-to-end (roster,
repin.toml, seed tables, repin, refreeze entries `wave-f3-f1-f6` +
`wave-panel-closing`); full sigil suite 318 suites / 3,667 tests green.

**Pre-existing discoveries en route (A/B-proven, not wave regressions):**
- **P-2** — the standing replay fixture DESYNCS on post-P2 master (identical
  hash/tick on pre-wave build). The regression net needs re-recording.
- **P-3** — sigil port-test seam-rot family: the P2c Task-8 byte-cap cell was
  never seamed into ANY dma_queue/vblank-lowering composition, and
  load_art_port's chain-71/P2c rows were missing — masked by the tests'
  ROM-presence skip (baseline preS+preA FAILED). Remediated (rows + repin
  symbols + two stale baselines); the STRUCTURAL hole remains: 57 skip sites
  across 45 port tests, and CI runs without an aeon checkout so every strict
  gate skips there by design.

**Final nine-seat panel over the wave diff — verdict: sound, one convergent
latent defect, closed same sitting.** Six seats (A/A2/B/C2/C3/C4)
independently found the out-of-grid `.empty_block` map-publish gap +
uninitialized map cells (NULL map -> ROM addr 0 read -> global $FFFF -> OOB
Page_Table/refcount). CLOSED in `4b2110c`: Blank_Local_Map constant published
unconditionally on the empty arm + parked into every map cell at
InvalidateStaging — the invariant is total by construction. Also closed:
PatchWord DEBUG pool-bounds assert (the 11-bit structural cap F-3 removed had
no replacement on the patch path), verify_level_bin map-VALUE bounds
(mutation-tested), C1-2 blank early-outs (~34 cyc/blank word, endorsed by two
seats), the zx0_resume zlib attribution (dangled at the deleted file for a
release-shipped decoder), and ~20 stale comments/doc sites. Panel
endorsements: merge-translation is amortized CHEAPER than the deleted pass
(crossover 1.52x re-patch), stamp eviction repays in <10 transitions,
probe->copy adjacency airtight at every fill site, footprint reconciles
(+66 B RAM net, VRAM/Z80 untouched; before-sizes recorded here: pre-fixup
414,341/427,926 golden; pre-wave f54b1ce local 414,473/428,134; post-wave
413,905/427,844; post-closing 413,953/427,926).

**Named open debts (ranked):**
1. **Eviction liveness witness** (panel V-3) — CLOSED 2026-08-09:
   `tools/evict_witness.py` (aether-bus harness vs live oracle, STRESS_EVICT
   shape). Phase 1 proves eviction famine-free during the init load itself
   (10 pages through 9 frames; pigeonhole via distinct-resident sampling +
   the page-2 eviction directly observed); Phase 2 scroll-burst is
   famine-triaged. Repeatable PASS ×2. Runbook: `STRESS_EVICT=1 ./build.sh`
   then `python3 tools/evict_witness.py`.
   **NEW FAMINE INTEL (P-1 class, WORSE than ledgered):** on 2026-08-09
   master the AllocFrame famine fires on SUSTAINED RIGHT scroll alone —
   full-speed right×900 from settle, burst-paced right×90×5, and even a
   single first right×90 burst have all raised it (knife-edge race; camera
   in this scene is input-driven at ~8 px/frame). Counters at raise: 2
   demands / 8 prefetches / stall-watchdog 6 — famine hits EARLY, not after
   runaway thrash. An A/B against pre-batching 517bf4 was CONFOUNDED: on
   that build the same scene never progresses under input (camera parked at
   96px, zero streaming counters, player suspended) — cause unknown; the
   batching-regression question is OPEN, not answered. Needs its own
   root-cause session (scene drive semantics first), folded into the C4-3 /
   famine-handling design (debt 6 below).
2. **P-2 fixture re-record** — CLOSED 2026-08-09 (merge 0aac1c2, sigil chain
   81): both fixtures re-recorded, determinism ×2 each, all four slide
   crossings re-proven, release pass. En route: the patchrun-batch parcel's
   skipped sigil ritual (stale roster/pins/port seams) was found and paid.
   Evidence: `2026-08-09-replay-net-rerecord-ab.md`.
3. **CI strict-gate hole** (V-4): give sigil CI an aeon checkout or a
   fail-not-skip mode for the 57 ROM-presence sites.
4. **C4-4** PF_PROTECTED inversion (derive candidacy, flag only the
   demand-protection window) — makes the flag/rc disagreement class
   unwritable.
5. **B-2** shared comptime template for the two local->global read sites.
6. **C2-6 / first-panel C5** stall-strand frame leak (pre-existing, DEBUG
   audit catches it; release leaks one frame until act reset) — fold into the
   streaming-act hardening pass.
7. **Frame_Counter hoist in the eviction scan** (C3-2/C1-5c — 1-frame age
   skew, safety-neutral; needs a register the license doesn't have).
8. M-3 ZX0R copy unroll, M-4 pinned-class election split, C1-3 prefetch
   page-set bitmask — measure-first when the first streaming act ships.
