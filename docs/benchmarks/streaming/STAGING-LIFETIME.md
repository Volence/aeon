# The staging-lifetime settling experiment — who serves a crossing, and why rows are free while columns burst

Measured 2026-08-21 by `tools/staging_lifetime_timeline.py` (rewritten for this question —
see §1.3 for its relationship to the F2-era instrument of the same name). This is the
settling experiment TICK-VARIANCE §3 booked for its one flagged inference: *why do the
block-ROW crossings cost nearly nothing while the block-COLUMN crossings burst 25.7-48.9k
cycles of `S4LZ_DecompressDict`?* The leading hypothesis there — "the column crossing
decompresses blocks that the row crossing three ticks later re-uses out of the staging
slots" — is **REFUTED by measurement** (§3). The burst-smoothing parcel's design inputs
are in §5.

| | |
|---|---|
| ROM | `s4.debug.bin` crc **`0dbaa80f`**, 715,010 B — the current canonical DEBUG image (matches the 2026-08-21 handoff's pinned CRC). **Not** TICK-VARIANCE's `5be03175`: master merged the P3 walker landings after the arc, so §3's pattern was RE-DERIVED here rather than assumed — and it reproduces exactly (§2's bursts are 48,882 / 40,986 / 25,736 cycles, the same values to the cycle) |
| instrument | `oracle/target/release/oracle-aether`. Main run: the binary TICK-VARIANCE used (built 2026-08-20 05:12, pre-CR-28). §6's caller addendum: rebuilt at oracle main `f476785` (post-CR-28, 3.3 s rebuild); the corpus control was re-run and PASSED under **both** binaries |
| ritual | `tick_variance_probe.py`'s, **imported not re-implemented**: maxdiag/right/down via the leader poke, settle 180 / lead 24 / 31-frame window, fresh server per boot, prefix ladder on the `cyclesSelf` basis, completeness identity at every rung |
| boots | **3 per state, fresh server each. Claim-ledger spread 0 (byte-identical JSON) across boots at all three states**; ticks `[28,28,28]` maxdiag, `[31,31,31]` right, `[31,31,31]` down |
| wall | control 1.0 s + 9 boots ≈ 15.6 s each = **141.5 s total**, `up 3 days 22:31 → 22:33`, load 1.98-4.16. Poison lanes 22:02 (`up 3 days 22:26`), caller addendum 2.1 s at 22:11 (`up 3 days 22:35`) |
| run | `python3 tools/staging_lifetime_timeline.py --rom s4.debug.bin --lst s4.debug.lst --states maxdiag,right,down --boots 3 --json …` · addendum `--callers` · red lanes `--poison claims|form|coverage` |

## 0. Controls — green quoted, and every check proven red first

The corpus A/B PHASE-0 REFERENCE ROW control (tick_variance_probe §0, reused verbatim)
PASSED before any number was taken, on the A/B's own ROM at both camera states:

```
PASS control idle    : $FFB452 1878.0 cyc/frame, 4.000 calls/frame, stall 0; sampleCycles 3968178; 30 ticks; …series EXACT vs A/B §12
PASS control maxdiag : $FFB452 1878.0 cyc/frame, 4.000 calls/frame, stall 0; sampleCycles 3968178; 15 ticks; …series EXACT vs A/B §12
```

Three identities cross-witness the ledger every frame, each with a `--poison` lane that
perturbs the SUBJECT and names its mismatch; all three ran red (exit 1) on 2026-08-21:

| poison | observed failure text (quoted from the run) |
|---|---|
| `claims` | `BLOCKED: CLAIMS identity: frame +1: Block_Stage_Gen advanced 1 but 0 slot keys changed — the ledger does not see every claim (a slot turned over twice inside one frame, or the gen witness moved without a key write)` |
| `form` | `BLOCKED: FORM identity: frame +5: 0 claims classified COMPRESSED (staged ptr == Block_Stage_Buffers slot base) but S4LZ_DecompressDict ran 4 times (profiler row) — the pointer classification does not describe the decode paths taken` |
| `coverage` | `BLOCKED: COVERAGE: crossing R at frame +2: needed block (1,7) [key 00000071] is neither pre-staged at the prior boundary nor claimed in frames +2..+3 — the needed-set derivation does not describe the fill's real walk; no serving verdict may be printed from it` |

Green, the identities say: per frame, `Block_Stage_Gen`'s delta == the number of slot keys
that changed == `TileCache_DecompressBlock`'s profiler calls; claims classified COMPRESSED
(staged pointer == `Block_Stage_Buffers` slot base) == `S4LZ_DecompressDict`'s profiler
calls; and every block a crossing needs is accounted as pre-staged-before or
claimed-at-the-crossing. Geometry (`BLOCK_TILE_SIZE`, `BLOCK_STAGE_SLOTS`,
`BLOCK_DECOMP_BUDGET`, `BLOCK_SPEC_LEAD_TICKS`, …) is parsed from
`engine/system/constants.emp` at run time; slot/symbol addresses come from the listing via
the server's resolver. Nothing is pinned from a prior document.

## 1. The instrument

### 1.1 The ledger

`Block_Stage_Keys[16]` and `Block_Stage_Ptrs[16]` are snapshotted at every prefix-ladder
frame boundary. Diffing adjacent snapshots is an **exact** per-frame claim ledger: eviction
is strict round-robin, so a slot cannot turn over twice inside one frame below 17
claims/frame — and that case is detected (gen delta > changed slots) and BLOCKED, not
assumed away. The staged pointer classifies each claim's decode form — RAM slot base =
**compressed** (S4LZ ran), `Block_Stage_ZeroPage` = **empty**, ROM address = **raw-direct**
— and the FORM identity ties the classification to the profiler's own S4LZ call counts.

### 1.2 Two instrument findings (both caught live by the checks)

* **The arm-frame lump.** `sample()`'s profiler window starts one frame after any state
  readable before it (`run_frames(N)` → `frameCount N-1`). Reading the start counters at
  `reach()`'s end lumps TWO physical frames into ledger interval 1. The `right` state
  caught it: `gen delta 2 != TileCache_DecompressBlock calls 1` at rung 1 — a claim inside
  the arm frame, invisible to the profiler by construction. Fix: the counted window's true
  start boundary is read in a dedicated deterministic pass (reach + 1 frame + read), with a
  repeat-pass reproducibility witness. maxdiag alone would never have caught this — its
  first frames carry no claims. The confound lane earned its seat.
* **Window-edge crossings are not adjudicable.** A crossing's claims land in frames
  `f..f+1` (the fill pass straddles the boundary; a budget-out resumes next frame). A
  crossing at the window's last frame is EDGE-EXCLUDED with a printed note, never
  adjudicated on a truncated view. Related: the printed `Cache_Fill_Budget` is a boundary
  SAMPLE — on claim frames it can show the NEXT pass's reset value, which is also why
  TICK-VARIANCE's "budget 6 → 1" reads oddly on row frames. Not load-bearing here.

### 1.3 Relationship to the F2-era tool of the same name

`tools/staging_lifetime_timeline.py` previously held the F2 parcel's watchpoint-based
dead-speculation grader (committed `e6a0dedd`, 2026-08-20; its measurements are quoted in
CHOKE-DIAGNOSIS §3's correction and §9(b)6). This rewrite answers the DIFFERENT question
TICK-VARIANCE §3 booked under this name — per-claim serving, filler, and form — on the
migrated profiler ritual. **The old instrument is not lost:** it is recoverable at
`e6a0dedd` byte-exactly, and CHOKE-DIAGNOSIS's tables remain reproducible from it. Nothing
in this document reuses its numbers.

## 2. (a) MEASURED — what served each crossing, per block

At **maxdiag** (28 ticks / 31 frames, the owner-felt state), the whole window contains
exactly 7 claim frames and **39 claims: 30 empty, 9 compressed, 0 raw-direct** (1.39
claims/tick). Every crossing's serving table, from the run (frames are ladder-window
relative; block = world block col,row):

| crossing | needed | pre-staged | claimed at crossing | forms of the claims | S4LZ in that frame |
|---|---|---|---|---|---|
| R +2 | 6 (rows: (1..6,6)) | **0** | 6, slots 10-15, via FillRow@bottom | 6× empty | 0 |
| C +5 | 5 (col: (7,2..6)) | **0** | 5, slots 0-4, via FillColumn@head | **4× compressed** + 1 empty | **48,882 cyc / 4 calls** |
| R +11 | 6 ((2..7,7)) | **0** | 6, slots 5-10, FillRow@bottom | 6× empty | 0 |
| C +14 | 5 ((8,3..7)) | **0** | 5, slots 11-15, FillColumn@head | **3× compressed** + 2 empty | **40,986 / 3** |
| R +20 | 6 ((3..8,8)) | **0** | 6, slots 0-5, FillRow@bottom | 6× empty | 0 |
| C +22 | 5 ((9,4..8)) | **0** | 5 (landed +23, the pass straddle), slots 6-10, FillColumn resume | **2× compressed** + 3 empty | **25,736 / 2** |
| R +29 | 6 ((4..9,9)) | **0** | 6, slots 11-15+0, FillRow@bottom | 6× empty | 0 |
| C +31 | — | — | WINDOW-EDGE EXCLUDED | — | — |

**"Who filled the slot that served the crossing" has a stark answer at maxdiag: nobody.
Not one crossing block, row OR column, was pre-staged — every crossing claims its own
blocks in its own tick.** The slots named above were each filled BY the crossing itself,
evicting six-crossings-old tenants (the eviction column in the tool's full ledger shows
round-robin order exactly).

Where staging DOES serve: **within an axis, between crossings.** Claims happen in 7 of 31
frames; the other 21 ticks' fills (2 rows + 2 columns per tick) run entirely on staged
hits — `TileCache_FindStagedBlock` 586 probes in the window (328 from FillRow, 258 from
FillColumn, CR-28 rows), zero decompresses outside the 7 claim frames. A block claimed at
a crossing serves the following ~7 ticks of fills through that block row/column. That is
the real carryover, and it is intra-axis, not the cross-axis reuse the hypothesis named.

Slot lifetime at maxdiag (claim → same-slot round-robin eviction): n=23, **min 9 / mean
12.9 / max 15 frames** (≈ 8.1-13.6 ticks at 1.107 frames/tick).

## 3. (b) MEASURED — the hypothesis is REFUTED; content form is the mechanism

The hypothesis said the column burst's output covers the later row crossing. The ledger
says the two crossings' block sets are **disjoint — zero overlap, every time** (a column
crossing stages `(head_col, rows 2..8)`; the next row crossing needs `(cols 1..9,
bottom_row)`; compare the tables above). Nothing the column burst stages is ever re-used
by a row crossing.

**What actually makes rows ~free and columns expensive is the DECODE FORM of the blocks
each crossing meets, i.e. a property of the content along this trajectory:**

* Every row-crossing block at maxdiag decoded **EMPTY** (24/24 adjudicated; 30 empty
  claims window-wide) — the zero-page arm of `TileCache_DecompressBlock`: two pointer
  publishes, no decompression, no copy. TICK-VARIANCE's ~864 cyc/call DecompressBlock
  figure on row frames is the cost of THIS arm. Its §3 wording "the block is already
  staged" was wrong in the mechanism (the blocks were NOT in the slots — `Block_Stage_Gen`
  +6 on those very frames says they were claimed); the cost story it fed into survives
  unchanged, the reason moves from "staged" to "empty-form".
* The column-crossing blocks that cost are **COMPRESSED** (9 window-wide, 12,220-13,662
  cyc/call, matching TICK-VARIANCE's per-call range on the older ROM to the cycle) — the
  head column's upper block rows carry real level content while the diagonal's lower rows
  have left it behind.

INFERRED (flagged): the empty row side is a property of THIS trajectory through OJZ act 1
(the maxdiag poke dives below the authored content). A trajectory whose below-row carries
compressed content would make ROW crossings burst by the same mechanism — the engine
draws no row/column distinction; the forms do. The `down` lane is consistent (19/19 claims
empty) but also un-suppressed (§4), so it cannot separate the two factors by itself.

## 4. (c) MEASURED — why the column crossing finds nothing staged

The only mechanism in the engine that ever pre-stages a column block is the cs col-scan
speculation inside `Tile_Cache_Fill` (with the pfx row scan and corner as siblings). At
maxdiag it is **suppressed by the F2a latch for the entire window**: `Cache_Spec_Blocked`
= 1 at all 31 boundaries, `Cache_Spec_Skips` +27 over 28 ticks, `Cache_Spec_Window` 11-16
(at/above the 16-slot trip line, never at/below the re-arm 8). CR-28 gives the same answer
from the call graph: `TileCache_DecompressBlock`'s callers at maxdiag are FillColumn 15 +
FillRow 24 and **zero from `Tile_Cache_Fill`** — not one speculative claim landed.

The `right` lane shows exactly what the suppressed mechanism does when allowed
(`Cache_Spec_Blocked` = 0 throughout): the cs scan stages the next head-side block column
**one block per tick** (9,442-15,332 cyc per compressed block, single call per frame,
inside the leftover budget), finishing **≥4 ticks before the crossing** — and all three
adjudicated column crossings found **4/4 pre-staged, zero claims, zero S4LZ at the
crossing**. `down` mirrors it for rows (5/5 pre-staged at all four R crossings, all empty
forms, `spec-row` filler named per slot). Lifetime at right: 25 frames (n=3) — pre-staged
blocks comfortably outlive their 8-tick lead.

## 5. Design INPUT for the burst-smoothing parcel (mechanism + budget — not a ship recommendation)

> **OUTCOME 2026-08-22 (`BURST-SMOOTHING.md`):** shape (a) was built and iterated five
> times, all measured. The two budgets below turned out to be a joint exclusion at
> whole-call granularity — every whole-call schedule (k=1 spread, drift-ordered,
> compressed-only, recovery-tick batches of 2 and 3) produced 5-8 spike ticks against
> the baseline's 3. Coverage itself is PROVEN to un-lag a crossing (a fully covered
> crossing ran spike-free, live), and the escalation this section names — slicing the
> decompress — is exactly what resolves both constraints at once. BLOCKED finding +
> substrate + booked slicing parcel in that doc; no engine bytes shipped.

* **The gap is precisely scoped:** at maxdiag the column crossing needs its **2-4
  compressed** blocks (the empties cost nothing) staged before the crossing tick. The
  cs-scan already computes the right target (`Cache_Pfx_Col_Target` was correct at every
  boundary); what stops it is the F2a latch, which is doing its OTHER job correctly
  (suppressing the churn class F2 measured). "Early staging for columns" therefore means:
  a claim class that the latch does NOT gate (demand-classified lookahead for the
  *imminent* head column), or an amended latch that admits k=1 col-scan claims while
  blocked — the mechanism choice is the parcel's, but the covering behaviour to reproduce
  is the measured `right` lane: k=1 per tick, ≥2-4 ticks of lead.
* **Residency budget (measured):** staged blocks at maxdiag's current 1.39 claims/tick
  survive 9-15 frames (mean 12.9) against an 8-tick crossing cadence — anything staged
  within the previous inter-crossing gap survives to its crossing. Early staging adds its
  own claims: at ~1.9 claims/tick total, worst-case round-robin survival is 16/1.9 ≈ 8.4
  ticks — still ≥ the cadence, but with ~0.4 ticks of margin. **Re-run this instrument
  after the parcel; the COVERAGE identity will say directly whether the pre-staged blocks
  survived.**
* **Cycle budget (measured):** one compressed block costs 9.4-15.3k cyc (singles, right)
  / 12.2-13.7k (bursts, maxdiag). Spread at k=1/tick that is one call per ordinary tick.
  TICK-VARIANCE's ordinary maxdiag ticks ran 106.9-116.7k of work — +15.3k on a 116.7k
  tick crosses 128,000, so a flat "always stage one" can trade a 3-per-window guaranteed
  double-frame for occasional marginal ones. The pass already has the H4 lag gate and the
  budget-leftover ordering for exactly this shaping; slicing the decompress (the ZX0R
  §9.7 precedent) is the escalation if whole calls prove too coarse. Numbers to design
  against, not a mechanism ruling.
* The parcel must not regress what the latch protects: `right`/`down` (latch never trips
  there — 0.48/0.61 claims/tick against 16 slots) and the F2-measured churn class. This
  instrument re-run at all three states is the regression harness.

## 6. CR-28 caller lens — first consumption, verdict for the oracle team

`--callers` (set_profiler `{callers:true}`, get_profiler_frames `{topCallers:8}`) on the
rebuilt binary (oracle main `f476785`): **works, exact, and closes the loop on
attribution.** Whole-window rows at maxdiag:

```
S4LZ_DecompressDict        calls  9  self 115,604   callers 1/1:  TileCache_DecompressBlock (callsTotal 9, cyclesSelfTotal 115,604)
TileCache_DecompressBlock  calls 39  self  33,774   callers 2/2:  TileCache_FillColumn (15) · TileCache_FillRow (24)
TileCache_FindStagedBlock  calls 586 self 112,128   callers 2/2:  TileCache_FillRow (328) · TileCache_FillColumn (258)
```

Every count reproduces the ledger independently (39 = 15 column-crossing + 24
row-crossing claims; S4LZ's 115,604 == the three bursts summed, to the cycle), and at
`right` the same rows show `TileCache_DecompressBlock <- Tile_Cache_Fill 15/15` — the
speculative claim site named directly, no geometry inference needed. The corpus control
PASSED unchanged under the rebuilt binary. One residual: the per-frame ledger still needs
the slot snapshots — callers say *which code path*, the keys say *which block, into which
slot, evicting what*.

## 7. What this does NOT establish

* **One act, one trajectory per state.** The §3 content-form finding is about OJZ act 1
  along these three pokes; other content shapes are unmeasured (and §3's INFERRED
  paragraph names the risk: content with compressed below-rows would move the burst to R
  crossings).
* **DEBUG shape only**, `s4.debug.bin` crc `0dbaa80f`.
* **The maxdiag serving verdicts cover 7 of 8 crossings** — the +31 column crossing is
  window-edge excluded by construction, not evidence either way.
* Per-tick work figures are quoted from TICK-VARIANCE (older ROM) where used in §5's
  cycle budget; this run did not re-take the work/tick table.
* The two-emulator tick divergence (F-TICK-BOUNDARY-DIVERGENCE) is untouched here, per
  scope.
