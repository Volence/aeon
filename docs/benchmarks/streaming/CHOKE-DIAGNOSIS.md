# The streaming choke — root-cause packet

**Parcel:** Streaming root-cause arc, diagnosis parcel (owner-ruled 2026-08-19). Branch
`diag/streaming-choke` off master `6a9ba181`. **This parcel changes NO engine code** — the
delivered branch rebuilds to `crc=06af0010` (debug, 713863 B) and `crc=e111dff7` (release,
698411 B), the pre-parcel identities.

**Instruments.** oracle (old), headless harness, per-routine profiler rows —
`tools/streaming_choke_probe.py`, added by this parcel. Plus four THROWAWAY
measurement-only builds (§6), none of which touched the delivered branch: each edit was
made, built, measured, and reverted with `git checkout` before the next.

**Wall clock.** All measurement 2026-08-19 20:13–20:38 −04:00, `up 1 day, 20:37` → `20:59`,
load average 5.0–17.4 throughout (three other agents building in parallel). Load does not
enter any figure below: every number is an EMULATED IDEAL CYCLE count, deterministic across
boots — **spread 0 on every routine row of every state, across 3 boots**, and the exact
decompress counts (§2) are identical across boots too.

Read alongside `docs/benchmarks/scanline-p2/ENGINE-BASELINE.md` (the top-level measurement
this decomposes) and `INSTRUMENT-PARITY.md`, whose **caveat 0 applies to every figure
here: these are IDEAL cycles.** Oracle's clock adds only `cyclesExecuted` to `_currentCycle`;
bus, VDP and DMA stall land in `_currentTime` and reach no row. The two components this
packet indicts hardest — the S4LZ decode and the per-word patch loop — are both
memory-traffic-heavy, so their REAL cost is bounded below by what is printed here.

---

## 0. The answer in six lines

Sustained max-diagonal costs **190,931 cycles of work per logic tick** against a
128,000-cycle frame, so a tick takes 2 frames and the game runs at 30 Hz. Of that,
`Tile_Cache_Fill` is 106,138.

Two independent mechanisms, both in the BLOCK tier, account for essentially all of the
excess:

1. **The per-word residency patch** (`PageCache_PatchRun_Seq`/`_Col`) costs 46,234 cyc/tick
   — 24% of the whole tick — translating and refcounting every nametable word, for a page
   residency cache that is **provably dormant on all shipped content** (§4).
2. **The block prefetch performs 3.06 speculative decompresses per tick that are ALL dead**
   — every one is round-robin-evicted from the 16-slot staging cache before the frame that
   needs it arrives. Proved by removing the prefetch: total decompresses fall 4.53 → 1.47
   per tick and demand does **not** rise to compensate (§3).

With both neutralised in a throwaway build, max-diagonal runs at **1.107 frames per tick**
— the choke is gone (§6). Neither lever alone crosses the line; together they do.

---

## 1. The camera states, defined

`idle` and `maxdiag` are **byte-identical in setup** to `engine_baseline_probe`'s, so every
row here is directly comparable with ENGINE-BASELINE.md. Two new single-axis states isolate
the scaling axes.

| state | how it is reached | camera over the sample |
|---|---|---|
| `idle` | boot, `run_frames 180`. Nothing poked at all. | stationary at (96,144) |
| `maxdiag` | boot, `run_frames 180`, ONE poke: leader `Sst.x_pos += 2000`, `Sst.y_pos += 1400` (16.16, px in the high word), `run_frames 24`, then sample | (320,368) → (560,608); 16 px per LOGIC TICK on both axes = `CAM_MAX_X_STEP` = `CAM_MAX_Y_STEP`, both saturated |
| `right` **(new)** | as `maxdiag` but the **x poke only** | dx 496, dy 0 over 31 frames; 16 px/tick, X axis only |
| `down` **(new)** | as `maxdiag` but the **y poke only** | dx 0, dy 496; 16 px/tick, Y axis only |

All four: OJZ act 1 section 0 throughout, `Camera_Art_Hold` 0, `Dbg_Cam_Clamp_Frames` 0,
`Cache_Art_Stall` 0, `PageIn_Fully_Resident` true. Sample 31 video frames, 3 independent
boots, settle 180, lead 24.

The single-axis states matter because **`right` and `down` do not lag** (1.000 frames/tick,
exactly). That makes them the only states on this instrument where the profiler's own
accounting closes (§7) — so the trustworthy decomposition is anchored there and the
max-diagonal table is cross-checked against it.

Reproducing any row: `python3 tools/streaming_choke_probe.py --rom s4.debug.bin
--lst s4.debug.lst --repeat 3`.

---

## 2. Question 1 — the 106k, decomposed

Every callee of `Tile_Cache_Fill` has its own per-routine row, so the tree reconstructs by
subtraction. The subtraction is only honest if each callee has ONE live parent; that was
established by grepping every `jbsr` in `engine/` and `games/`:

    Tile_Cache_Fill
      +- TileCache_FillColumn -> TileCache_CopyBlockColumn -> PageCache_PatchRun_Col
      +- TileCache_FillRow    -> PageCache_PatchRun_Seq
      +- TileCache_DecompressBlock -> S4LZ_DecompressDict
      +- TileCache_FindStagedBlock          (THREE live parents: col fill, row fill, prefetch)
      +- TileCache_HSlide / VSlide / VSlideUp
      +- PageCache_Audit                    (DEBUG only, one pass in 128)
                                            ^^ AS MEASURED HERE. Fix F5 (§8) has since
                                            moved this gate OUT of the fill and into the
                                            level state's tick; on master today it is a
                                            SIBLING of Tile_Cache_Fill, not a child.

`DecompressBlock`, `CopyBlockColumn`, both `PatchRun`s, `S4LZ_DecompressDict` and the slides
have exactly one live parent. `TileCache_FindStagedBlock` has three inside the fill plus a
fourth in `PageCache_Prefetch` — which early-outs on `PageIn_Fully_Resident` and contributes
**zero** here (measured: 14 cyc/frame, and `PageCache_Request` never called). The probe reads
`PageIn_Fully_Resident` and prints a warning if it is ever false, so this can never go
silently stale.

### The exclusive (own-cost) table — `maxdiag`, per LOGIC TICK

Frame → tick conversion is ×2.067. The rows sum to the parent **exactly**:
45,693 + 5,664 residual = 51,357 = the measured `Tile_Cache_Fill` row.

| component | cyc/frame | **cyc/tick** | % of fill | % of the 190,931-cyc tick |
|---|---|---|---|---|
| `PageCache_PatchRun_Col` (leaf) | 12,534 | **25,904** | 24.4% | 13.6% |
| `PageCache_PatchRun_Seq` (leaf) | 9,837 | **20,330** | 19.2% | 10.6% |
| `S4LZ_DecompressDict` (leaf) | 9,458 | **19,547** | 18.4% | 10.2% |
| inline residual — `Fill` + `FillColumn` + `FillRow` own code, incl. the collision copies | 5,664 | **11,707** | 11.0% | 6.1% |
| `TileCache_FindStagedBlock` (leaf) | 4,993 | **10,319** | 9.7% | 5.4% |
| `TileCache_CopyBlockColumn` own | 3,740 | **7,729** | 7.3% | 4.0% |
| `PageCache_Audit` (DEBUG one-shot, see below) | 3,548 | **7,333** | 6.9% | 3.8% |
| `TileCache_DecompressBlock` own | 1,392 | **2,877** | 2.7% | 1.5% |
| `TileCache_HSlide` + `VSlide` | 191 | **395** | 0.4% | 0.2% |
| **total** | **51,357** | **106,138** | 100% | 55.6% |

**The two patch runs together are 46,234 cyc/tick — 43.6% of the fill and 24.2% of the whole
logic tick.** They are the single largest thing in the streaming path, larger than all
decompression.

> **Superseded by fix F5 (§8), shipped 2026-08-19.** The `PageCache_Audit` row above is the
> LAST measurement taken with the audit inside the fill. Its gate now lives in the level
> state's tick, so on master that row is gone from this table and the fill's total at `idle`
> falls 4,780 → 926 cyc/tick. Everything else in the table is unchanged (proved at `right`,
> `down` and two non-firing `maxdiag` phases) — which is what makes the rest of this
> decomposition trustworthy. The paragraph below still describes the mechanism.

`PageCache_Audit` is a **DEBUG-only one-shot, not a steady-state cost**: it walks all 4,800
nametable words every 128 fill passes and costs ~110,000 cycles when it fires. It fired
inside the `maxdiag` and `idle` windows (`Page_Audit_Ticks` 123 → 10) and **did not** fire
inside `right` or `down` (3 → 34). The probe reports which, so the row is never read as
recurring. Its release cost is zero; its measurement cost is that it contaminates one DEBUG
window in four.

### The uncontaminated single-axis tables

These are the ones to trust for the per-component cost model (§7 explains why).

**`right`** — 1.000 frames/tick, fill 43,437 cyc/tick:

| component | cyc/tick | % of fill |
|---|---|---|
| `PageCache_PatchRun_Col` | **21,981** | 50.6% |
| `TileCache_CopyBlockColumn` own (incl. the collision column copy) | 7,078 | 16.3% |
| inline residual (`Fill` + `FillColumn` own) | 5,766 | 13.3% |
| `S4LZ_DecompressDict` | 4,377 | 10.1% |
| `TileCache_FindStagedBlock` | 3,725 | 8.6% |
| `TileCache_DecompressBlock` own | 326 | 0.8% |
| `TileCache_HSlide` | 184 | 0.4% |

**`down`** — 1.000 frames/tick, fill 41,109 cyc/tick:

| component | cyc/tick | % of fill |
|---|---|---|
| `PageCache_PatchRun_Seq` | **21,835** | 53.1% |
| inline residual (`Fill` + `FillRow` own — dominated by FillRow's `ic_lo`/`ic_hi` run derivation and the phase-2 collision byte copies, neither of which is a callable routine) | 13,986 | 34.0% |
| `TileCache_FindStagedBlock` | 4,798 | 11.7% |
| `TileCache_DecompressBlock` own | 402 | 1.0% |
| `S4LZ_DecompressDict` | **0 (never called)** | 0% |
| `TileCache_VSlide` | 88 | 0.2% |

**`down` calls S4LZ zero times.** All 20 of its decompresses take the `.empty_block` or
`.raw_direct` path — the blocks below the start position are blank or stored raw. This is a
CONTENT fact about OJZ section 0, not an engine property, and it is why `down` is not a valid
proxy for decode cost.

### Cost per unit of work — derived from the geometry, not from a call count

The camera advances 2 tiles per tick on a saturated axis, so per tick the fill writes
exactly `2 × TILE_CACHE_ROWS` = 120 nametable words on the column path and
`2 × TILE_CACHE_COLS` = 160 on the row path. (The profiler's `calls` field is an
integer-ROUNDED per-frame average and cannot be used for this — see instrument ask C2.)

| | words/tick | cyc/tick | **cyc per patched word** |
|---|---|---|---|
| `PageCache_PatchRun_Col` @ `right` | 120 | 21,981 | **183** |
| `PageCache_PatchRun_Seq` @ `down` | 160 | 21,835 | **136** |

Both figures INCLUDE the per-run `movem.l d1-d5/a2-a4` bank and the three run hoists
(~180 cyc over ~8–10 runs per tick), so the loop body itself is ~160 / ~118 cycles per word.
That is what a ~30-instruction body with two indexed table reads, two 6-bit shifts, a
read-modify-write refcount increment and a second read-modify-write decrement costs on a
68000. The loop is not pathological — **it is simply being run 280 times per tick to do
work that is dormant** (§4).

`TileCache_FindStagedBlock` costs 416 cyc per probe (4,993 cyc / 12 probes per frame at
`maxdiag`). It is a **linear scan of all `BLOCK_STAGE_SLOTS` = 16 keys** via `cmp.l (a1)+ /
dbeq`, so its cost is linear in the slot count — confirmed by the 20-slot throwaway, where
the same `right` state raised it from 3,725 to 3,949 cyc/tick.

---

## 3. Question 3 (taken first, because it is the root cause) — the famine verdict, and what
   the prefetch is actually doing

### There is no famine. The page tier is not engaged at all.

Every page-tier counter reads zero for the whole of every sustained-motion sample:

| counter | `maxdiag` | `right` | `down` |
|---|---|---|---|
| `PageIn_Fully_Resident` | true (255) | true | true |
| `Dbg_PageCache_Demands` delta | 0 | 0 | 0 |
| `Dbg_PageCache_Prefetches` delta | 0 | 0 | 0 |
| `Dbg_PageIn_Preempts` / `Resumes` / `Flushes` / `PfxSkips` / `Deferred` deltas | 0 | 0 | 0 |
| `PageCache_Request` calls | 0 (routine absent from the profile) | 0 | 0 |
| `Cache_Art_Stall` / `Camera_Art_Hold` / `Cache_Stall_Watchdog` | 0 | 0 | 0 |
| `PageCache_Prefetch` cost | 14 cyc/frame (the `tst.b` early-out) | 32 | 32 |

OJZ act 1's art pool is **10 pages against `PAGE_FRAMES` = 15**, so `Level_LoadArt` latches
`PageIn_Fully_Resident` and the whole §9.7 residency machinery — eviction, refcount-driven
candidacy, demand requests, the ZX0R resumable decoder, the VBlank supervisor bookmark —
is inert. **The known `STRESS_EVICT` famine is a fixture-only phenomenon (`PAGE_FRAMES_CLAMP`
= 9 forced below the pool) and is NOT this choke; it is not even adjacent to it.** Nothing in
the streaming choke is a page-tier problem.

The choke is entirely in the BLOCK tier: the 16-slot S4LZ block staging cache and the
nametable patch that runs off it.

### The block prefetch's speculation is 100% dead under sustained diagonal

`Block_Stage_Gen` is bumped in exactly two places — `TileCache_InvalidateStaging`
(act-init only, never inside a sample) and the `TileCache_DecompressBlock` slot claim. Its
delta is therefore an **EXACT** decompress count, unlike the profiler's rounded `calls`.

| state | decompresses over the sample | **per tick** | geometric minimum (derived) |
|---|---|---|---|
| `right` | 15 / 31 ticks | **0.48** | 4–5 blocks per 8 ticks = 0.50–0.63 |
| `down` | 20 / 31 ticks | **0.65** | 5–6 blocks per 8 ticks = 0.63–0.75 |
| `maxdiag` | 68 / 15 ticks | **4.53** | 1.13–1.38 (the two axes plus a corner) |

The geometric minimum: a block is 16 tiles across, the camera advances 2 tiles/tick, so an
axis enters a new block strip every 8 ticks and must stage that strip's
`ceil(cache_extent / 16)` blocks. Each single-axis state sits **at** its minimum. The
diagonal sits at **4× its minimum**.

**Proof that the excess is dead speculation, not extra demand.** Throwaway build with the
three speculative stage sites bypassed (one `jbra .fill_return` at `.v_top_done`), same
camera state, same distance travelled (dx 240, dy 240, identical):

| | baseline | prefetch OFF |
|---|---|---|
| decompresses/tick @ `maxdiag` | 4.53 | **1.47** |
| `Tile_Cache_Fill` cyc/tick | 106,138 | 87,401 |
| WORK per tick | 190,931 | **169,351** |

Demand did **not** rise to fill the gap — it landed on 1.47, the geometric minimum. So the
3.06 decompresses/tick the prefetch performs in the baseline produce **zero** reduction in
demand decompresses. Every one of them is staged and then evicted before the frame that
needs it arrives.

### Why they die — the residency-vs-lead arithmetic

* **Prefetch lead.** Each scan targets the block strip one block beyond the cache edge. The
  edge advances 2 tiles/tick, so that strip is consumed **8 ticks** later.
* **Staging residency.** Eviction is strict round-robin over `BLOCK_STAGE_SLOTS` = 16
  (`Block_Stage_Next` increments and wraps). A staged block therefore survives exactly 16
  claims, i.e. `16 / claim_rate` ticks. At the measured 4.53 claims/tick that is
  **3.53 ticks**.

3.53 < 8, so **nothing survives to its use**. And the loop is self-reinforcing: each dead
speculation is itself a claim, which shortens residency, which kills more speculation.

The system is **bistable**. At the single-axis rate of 0.48–0.65 claims/tick, residency is
25–33 ticks, comfortably beyond the 8-tick lead, and the prefetch works — which is exactly
what the measurements show. Sustained diagonal knocks it into the bad basin and it stays
there.

A second, independent consequence of the same rate: the prefetch scans carry a memo keyed on
`Block_Stage_Gen` (`Pfx_Memo_Gen` / `Cs_Memo_Gen`) whose entire purpose is to skip the
`FindStagedBlock` walk when nothing has changed. Because the generation is bumped by every
staging claim — **including the claims the scans themselves make** — the memo can never hit
at 4.53 claims/tick. And the memo is only ever RECORDED on the all-hits exit
(`.pfx_record` / `.cs_record`); a scan that stages a block jumps straight to `.row_done` and
records nothing. So under sustained diagonal the memo is armed on no frame at all, and the
full scans run every tick. That is a design-level self-defeat, not a tuning miss.

### Capacity is NOT the lever — a measured negative

The obvious reading of "residency 3.53 < lead 8" is "add slots". Measured, and it does not
work. `BLOCK_STAGE_SLOTS` 16 → 24 does not build at all (`region.overflow`: `lower_ram`
overflows by 2,522 B — each slot is `BLOCK_RAW_SIZE` = 768 B and only ~6.5 KB is free).
16 → 20, which does build:

| | 16 slots (baseline) | 20 slots |
|---|---|---|
| decompresses/tick | 4.53 | 3.87 (−15%) |
| `Tile_Cache_Fill` cyc/tick | 106,138 | 103,470 (−2.5%) |
| **WORK per tick** | **190,931** | **191,024 (+0.05%)** |
| frames/tick | 2.067 | **2.067 (unchanged)** |

Nothing moved, because the fewer decompresses were paid for by a longer linear key scan in
`FindStagedBlock` (§2). To reach residency > lead at the baseline claim rate you would need
`16 × 8 / 3.53` ≈ **36 slots = 27 KB of RAM**, which does not exist. **The lever is the
policy, not the capacity.**

---

## 4. Question 4 — what scales with what

| component | scales with | evidence |
|---|---|---|
| `PageCache_PatchRun_Col` | camera X speed × `TILE_CACHE_ROWS`. Content-independent, ~183 cyc/word flat. | `right`: 120 words/tick, 21,981 cyc; identical per-word figure at `maxdiag` |
| `PageCache_PatchRun_Seq` | camera Y speed × `TILE_CACHE_COLS`. Content-independent, ~136 cyc/word flat. | `down`: 160 words/tick, 21,835 cyc |
| `S4LZ_DecompressDict` | decompress RATE × per-block stream cost. Rate = geometric minimum **+ dead speculation** (§3). Per-block cost is CONTENT-dependent: ~9,100 cyc for a compressed block, **0** for raw-direct or empty. | `down` never calls it at all; `right` 4,377 cyc/tick; `maxdiag` 19,547 |
| `TileCache_FindStagedBlock` | (blocks visited by the fill + blocks walked by the prefetch scans) × `BLOCK_STAGE_SLOTS`. Linear in the slot count. | 416 cyc/probe; 3,725 → 3,949 cyc/tick at `right` when slots went 16 → 20 |
| inline residual (collision copies + run derivation) | same axis geometry as the patch runs | `down` 13,986 vs `right` 5,766 — the row path's collision phase 2 is a byte loop over 80 cells × 2 planes |
| `PageCache_Audit` | per-tick CONSTANT of 0 in release; in DEBUG, ~110,000 cyc once per 128 ticks. **No longer part of the fill at all since F5 (§8)** — it is a sibling of `Tile_Cache_Fill` in the level state's tick. | fired in the `maxdiag`/`idle` windows, not in `right`/`down` |
| `HSlide` / `VSlide` / `VSlideUp` | O(1) origin arithmetic, per axis crossing | ≤ 395 cyc/tick everywhere |

**Nothing here scales with the level's content in the way the §9.7 design anticipates.**
Page count, dictionary size and pool pressure are all irrelevant on shipped content because
the pool is fully resident (§3). The choke scales with **camera speed and cache geometry
only** — which is why it appears, as the owner framed it, with little parallax, few objects
and minimal content. It is a property of the foundation.

Two geometry constants set the fill's whole scale and are worth naming: the tile cache is
80 × 60 for a 40 × 28 viewport (`TILE_CACHE_MARGIN_H` = 20, `TILE_CACHE_MARGIN_V` = 16), so
every column fill patches 60 words and every row fill 80 — 2.1× and 2.0× the visible extent.

---

## 5. Question 2 — the tick-rate reconciliation

**It closes exactly, and the mechanism is INTEGER QUANTISATION.**

The profiler reports `total_cycles`, the ideal cycles it accounted for in one video frame
(against `budget_cycles` = 128,000). `VSync_Wait` is the idle spin inside that. The
difference, scaled to the tick, is what a logic tick actually costs:

    work_per_tick = (total_cycles − VSync_Wait) × frames_per_tick

| state | total_cycles/frame | VSync_Wait/frame | **work/tick** | work ÷ 128,000 | **ceil** | **measured frames/tick** |
|---|---|---|---|---|---|---|
| `idle` | 127,789 | 79,548 | 49,849 | 0.39 | 1 | 1.033 ✓ |
| `right` | 127,765 | 35,796 | **91,969** | 0.72 | 1 | **1.000** ✓ |
| `down` | 127,769 | 37,310 | **90,459** | 0.71 | 1 | **1.000** ✓ |
| `maxdiag` | 126,734 | 34,348 | **190,931** | **1.49** | **2** | **2.067** ✓ |

**`frames_per_tick = ceil(work_per_tick / 128,000)` predicts every state.** The ratio is 2.067
rather than 1.3 because *there is no 1.3*. A logic tick either fits inside one video frame or
it does not; when it does not, `VInt_Lag` services the spare VBlank and the tick costs two
frames whole. At 1.49 frames of work the engine pays for 2 and throws away the remaining 0.51
— the measured 70,986 cyc/tick that `VSync_Wait` spends idle at `maxdiag` while the game runs
at 30 Hz.

This also sets the target precisely: **work/tick must fall below 128,000, i.e. by 62,931
cycles (33%)**, for max-diagonal to return to 60 Hz. `Tile_Cache_Fill` is 106,138 of the
190,931, so the fill has to come down to roughly what a single axis already costs.

> **UPDATED after fix F1 shipped (2026-08-19, §8).** The collapsed patch loop moves
> `maxdiag` work/tick **190,941 → 174,437 (−16,504)**, `right` 91,964 → 82,569 and `down`
> 90,460 → 83,607. `frames_per_tick = ceil(work/tick ÷ 128,000)` still predicts every state:
> `right`/`down` stay at 1.000 (0.65 frames of work each) and **`maxdiag` stays at 2.067**
> — 174,437 is 1.36 frames, so it still pays 2. **That is the predicted result, not a
> disappointment:** §5's own arithmetic said neither lever alone crosses the line, and §6's
> ladder measured it (C alone, the throwaway floor for this fix, landed at 154,262 and still
> read 1.938 frames/tick). The remaining **46,437 cycles** to the line are F2's; throwaway D
> (F1 + F2) is the row that reads 1.107.
>
> The superadditivity DIAGNOSIS below survives F1 intact. Re-derived on the post-F1 numbers
> (with `idle` taken at a non-audit-firing settle, 42,845): axes 39,724 + 40,762 over the
> shared baseline give an additive prediction of **123,331** against **174,437** measured —
> an excess of **+51,106 (+41%)**, versus +58,352 (+44%) before. F1 removed ~12% of the
> excess as a side effect of making both axes cheaper and touched none of its mechanism: the
> exact `Block_Stage_Gen` decompress counts are identical before and after at all four states
> (0 / 4.53 / 0.48 / 0.65 per tick, spread 0 across three boots). The excess is still the
> dead-speculation loop of §3, and it is still F2's.

### Is the diagonal merely the sum of its axes? No — it is superadditive

Taking `idle`'s 49,849 cyc/tick as the shared non-streaming baseline:

| | work/tick | marginal streaming cost |
|---|---|---|
| `idle` | 49,849 | — |
| `right` | 91,969 | 42,120 |
| `down` | 90,459 | 40,610 |
| **additive prediction** for the diagonal | **132,579** | 82,730 |
| **`maxdiag`, measured** | **190,931** | **141,082** |
| **excess** | **+58,352 (+44%)** | **+70.6%** |

The whole of that excess is the dead-speculation loop of §3. Two things follow, and the
second is easy to miss:

* Even the additive prediction, 132,579, is **3.6% over 128,000** — so a perfectly
  non-interacting diagonal would still just barely take 2 frames. Killing the superadditivity
  alone gets you to the line, not past it; that is exactly what the single-lever throwaways
  show in §6.
* Therefore the fix must be **both** a policy fix (kill the dead speculation) **and** a
  cost fix (make the per-word patch cheaper). Neither is optional.

---

## 6. The lever ladder — measured, not modelled

Four throwaway measurement-only builds. Each was made, built, measured, and reverted with
`git checkout` before the next; the delivered branch rebuilds to `crc=06af0010` /
`crc=e111dff7`, verified after the last revert (§0).

| # | build | what was changed | decompresses/tick | fill cyc/tick | **work/tick** | **frames/tick** |
|---|---|---|---|---|---|---|
| — | **baseline** `06af0010` | — | 4.53 | 106,138 | **190,931** | **2.067** |
| A | `bb84f5e5` | `BLOCK_STAGE_SLOTS` 16 → 20 | 3.87 | 103,470 | 191,024 | 2.067 |
| B | `875cfa32` | prefetch bypassed (`jbra .fill_return` at `.v_top_done`) | **1.47** | 87,401 | 169,351 | 2.067 |
| C | `77608d4f` | patch loop reduced to map-read + attr-merge + store (page→frame indirection and both refcount RMWs dropped); `PageCache_Audit` disabled with it | 4.50 | 86,610 | 154,262 | 1.938 |
| D | `1610a7f4` | **B + C together** | **1.18** | **61,734** | **121,598** | **1.107** |

**Build D is the result.** 121,598 < 128,000: the tick fits a frame and max-diagonal runs at
28 logic ticks per 31 video frames — an **87% increase in logic rate**, essentially 60 Hz.
Its decompress rate, 1.18/tick, is the geometric minimum.

Read the ladder carefully, because the single levers are the instructive part:

* **A is a clean negative.** Capacity does not move the tick rate at all (§3).
* **B alone does not cross the line** (169,351) even though it removes three quarters of all
  decompression. Nor does **C alone** (154,262), even though it halves the largest component.
  Only together do they clear 128,000 — the arithmetic of §5 predicted exactly this.
* **B is a REGRESSION on a single axis.** With the prefetch off, `right` goes from
  **1.000 to 1.069 frames/tick** (29 ticks in 31 frames) while its mean fill cost FALLS
  (43,437 → 41,981 cyc/tick). Lower mean, worse frame rate: the prefetch is smoothing the
  block-crossing spikes, and every eighth tick now pays 4–5 synchronous decompresses at once
  and overruns. **So "delete the prefetch" is the wrong fix even though it produces the right
  number at max-diagonal.** The fix has to make speculation LAND, not remove it.

**C's output is wrong** (the map still holds globals, so the tiles are garbage) — it is a
cost floor, not a shippable shape. It bounds the saving available to a correct
implementation of fix F1; a real one lands at or slightly above it. `PageCache_Audit` had to
be disabled in the same build because it `raise_error`s on the refcounts C stops maintaining
— which is itself worth noting as evidence that the audit is a genuine machine check.

---

## 7. INSTRUMENT DEFECT FOUND — old oracle's rows are wrong when the frame lags

This was not looked for. It surfaced because `GameState_OJZScroll_Update`'s row (55,145
cyc/frame at `maxdiag`) is **smaller than the sum of its own children** — `Tile_Cache_Fill`
51,357 + `Parallax_Update` 12,188 = 63,545 — which is impossible for an inclusive row.

Summing the true top-level entries against `total_cycles`:

| state | frames/tick | state handler + `VSync_Wait` + `VBlank_Handler` + HInt | `total_cycles` | **gap** |
|---|---|---|---|---|
| `idle` | 1.033 | 125,230 | 127,789 | −2,559 (−2.0%) |
| `right` | 1.000 | 129,054 | 127,765 | +1,289 (+1.0%) |
| `down` | 1.000 | 129,053 | 127,769 | +1,284 (+1.0%) |
| `maxdiag` | 2.067 | 100,571 | 126,734 | **−26,163 (−20.6%)** |

(The ±1–2% at the three healthy states is the expected residue: HInt is double-counted, since
the trampoline fires inside whichever routine was executing.)

**The accounting closes at 1.000 frames/tick and loses a fifth of the frame at 2.067.** The
common factor is preemption: when a logic tick spans a VBlank, the profiled routine that was
executing across the boundary loses cycles. The same signature shows in throwaway B, where
the probe's own inclusive-row check fires outright — `Tile_Cache_Fill` row 42,291 against
44,681 of children, a **negative** own cost.

Consequences for this packet, stated so nothing here is over-read:

* The `maxdiag` decomposition table in §2 is **indicative, not exact**. Its internal
  arithmetic closes (the exclusive rows sum to the parent to the cycle), and its shape agrees
  with the `right`/`down` tables where those are trustworthy, but its absolute figures carry
  the preemption loss.
* Everything the packet actually CONCLUDES from is preemption-free: the exact
  `Block_Stage_Gen` decompress counts, the `right`/`down` decompositions at 1.000 frames/tick,
  and `work_per_tick`, which is built from `total_cycles` and `VSync_Wait` alone and predicts
  the measured tick rate at all four states plus all four throwaways (§5, §6).
* It is why the two single-axis states were built at all.

---

## 8. Question 5 — the ranked fix list

Every saving below is MEASURED on a throwaway build or derived from a measured exclusive
cost — none is booked from a nominal instruction count. The discipline is the one tonight's
operand-vs-fetch bus finding earned: a nominal figure for this loop would have predicted
~40 cyc/word where the hardware reports 136–183.

**Nothing here is started. F1 and F2 need rulings before anyone writes code.**

### F1 — collapse the per-word residency patch on identity-mapped acts — ✅ SHIPPED 2026-08-19 (`perf/resident-patch-collapse`)
* **Mechanism, as ruled.** `PageIn_Fully_Resident` is already latched at act load and is true
  for all shipped content. When it holds, no page can ever be evicted, so per-word
  `page → frame` indirection and the ref/unref refcount pair are pure overhead: the physical
  index is a fixed function of the global index for the act's lifetime. Bake
  `local → PHYSICAL` into the section local maps at act load, and the loop collapses to
  read / mask / one table read / merge attrs / store.
* **THE CONTRADICTION THE RULING ANTICIPATED — the section local maps are ROM.** They are
  `embed()`ed blobs (`games/sonic4/data/generated/ojz/act1/sec*_local_map.bin`, reached
  through `Act.act_sec_local_maps`), read directly by the patch runs via
  `Cache_Cur_LocalMap`. Nothing copies them to RAM, so there is no in-place rewrite to
  perform. A RAM copy was priced and rejected: OJZ act 1's nine maps are 3,230 B against
  **3,622 B free in `lower_ram`** — it fits *this* act with 392 B to spare and puts a hard,
  invisible content ceiling on the next one.
* **What shipped instead — the same collapsed loop, composed at build time by being the
  IDENTITY.** Under the latch, `PageCache_Init`'s free list (threaded `0→1→…→N-1`) plus
  `Level_LoadArt`'s in-order bulk enqueue plus page-in's single-slot in-order completion make
  `Page_Table` the identity: `Page_Table[p] == p` for every `p < PageIn_Pool_Pages` (measured
  live: `00 01 02 … 09` over the 10-page pool). Then
  `frame<<6 | (global&63) == (global>>6)<<6 | (global&63) == global`, so **the section map's
  GLOBAL value already IS the physical index** and no composition pass is needed at all.
  `Level_LoadArt` **verifies** the identity once the pool has landed — it is checked, never
  assumed — and latches `PageCache_Direct_Map` (which consumes an existing word-align pad
  byte, so **RAM layout is unchanged**). The runs then dispatch per RUN, not per word:
  `tst.b PageCache_Direct_Map` selects the collapsed variant, and the fallback arm is the
  pre-F1 loop **byte-for-byte**, over the pristine ROM maps.
* **The F-3 merge-translation contract is satisfied identically.** Staged words stay LOCAL,
  the section map is applied per word, the full-width global lives only in a register, and
  the 11-bit nametable field carries only the physical index (≤ 959 = `POOL_TILE_CEILING`).
* **`PageCache_Audit` neither reddens nor goes vacuous.** Throwaway C had to disable it
  because it `raise_error`s on refcounts a collapsed loop stops maintaining. Here the
  refcount-vs-nametable comparison is REPLACED under the latch by the three invariants that
  are live in that regime: (a) every `pf_refcount` is zero — a nonzero one means a general-loop
  run executed under the latch, i.e. the two variants got mixed, which is exactly the
  divergence the comparison used to catch; (b) every frame the nametable references is
  assigned (`pf_page != $FFFF`) — the no-dangling-physical-index property the refcounts
  existed to protect, re-derived from the nametable walk itself; (c) `Page_Table` is STILL
  the identity, the premise the whole collapsed loop rests on. Bijectivity, the
  candidate-flag invariant and the orphan check are untouched and stay live.
* **Measured saving** (`--repeat 3`, spread 0.000 on `frames/tick` at every state, 3 boots;
  baseline `s4.debug.bin` crc `2191bfdc` at master `76afd279`, F1 crc `47111ae9`):

  | state | fill cyc/tick | patch run cyc/tick | cyc per patched word |
  |---|---|---|---|
  | `right` | 43,395 → **33,646** (−9,749, **−22.5%**) | `_Col` 21,971 → **12,394** (−43.6%) | 183.1 → **103.3** |
  | `down` | 41,067 → **34,218** (−6,849, **−16.7%**) | `_Seq` 21,794 → **14,160** (−35.0%) | 136.2 → **88.5** |
  | `maxdiag` | 105,231 → 89,842 | `_Col` 25,904 → 13,003, `_Seq` 20,332 → 14,624 | — |

  `work/tick`: `right` 91,964 → **82,569**; `down` 90,460 → **83,607**; `maxdiag`
  190,941 → **174,437 (−16,504)**.
* **Why the saving is ~84% / ~78% of throwaway C's floor, not 100%.** C dropped the DEBUG
  pool-bounds assert with the page derivation it rode on. The shipped loop keeps it, in a
  STRICTER and cheaper form — it bounds the GLOBAL directly against `pool_pages<<6` (hoisted
  once per run into d4) instead of deriving the page per word, so it catches every
  out-of-pool map entry the page-level check caught **and the sub-page ones it did not**.
  That cost is **DEBUG-only**; the release shape runs at C's floor. The residual also
  carries the per-run `tst.b`+`bcc` variant select (~200 cyc/tick against ~95 cyc/word over
  280 words/tick).
* **`maxdiag`'s −16,504 vs C's −36,669 is the §7 instrument, not a shortfall.** F1's own
  per-word deltas predict (183.1−103.3)×120 + (136.2−88.5)×160 = **17,208 cyc/tick**, and the
  measured `work/tick` fell 16,504 — **closing to 4%**. C's −36,669 exceeds its OWN per-word
  arithmetic ((183−88)×120 + (136−77)×160 = 20,840) by 76%, and it disabled `PageCache_Audit`
  in the same build. Read F1 off `right`/`down`, where the instrument closes (§7).
* **Tick rate.** `right` and `down` stay at 1.000 frames/tick; `maxdiag` stays at **2.067** —
  exactly as §5 predicts, since 174,437 is still above 128,000. **F2 is the other half.**
* **The `idle` null, and one honest artifact.** At every settle where the DEBUG audit does
  NOT fire in the window (120 / 150 / 210 / 240) base and F1 are identical: 1.000 frames/tick
  and `work/tick` 42,840–42,851 vs 42,841–42,847 — a spread smaller than the baseline's own
  across settles. At the canonical settle 180, where the audit DOES fire, F1 reads 1.069
  frames/tick against the baseline's 1.033. Nothing got slower: every routine row is equal or
  lower, `PageCache_Audit` is 3,688 cyc/frame in BOTH, and `Page_Audit_Ticks` enters the
  window at 110 instead of 109 — F1 has completed one MORE logic tick by frame 180, so the
  ~114,000-cycle DEBUG one-shot lands at a different tick/frame phase and straddles one more
  frame. It is a phase artifact of a DEBUG-only one-shot with zero release cost; the
  non-firing settles are the null.
* **Value identity — the hard gate. ALL EQUAL.** Full byte compare (not a hash alone) of
  `Tile_Cache_Nametable` (9,600 B) *and* `Tile_Cache_Collision` (4,800 B) against the
  pre-parcel ROM at all four pinned camera states, reached by identical setup, with
  `Camera_X`/`Camera_Y` verified equal at the sample point. Exact `Block_Stage_Gen`
  decompress counts are unchanged at every state (0 / 4.53 / 0.48 / 0.65 per tick) — F1
  changes no scheduling.
* **Cost.** `s4.debug.bin` 713,905 → 714,234 B (+329); `s4.bin` 698,411 → 698,517 B (+106).
  RAM: **unchanged** — the latch consumes an existing word-align pad byte at `$FFB833`, and
  every RAM symbol keeps its address (`Tile_Cache_Nametable`, `Page_Table`, `Page_Frames`,
  `Camera_*`, … all verified equal between the two `.lst`s). Changed procs:
  `PageCache_PatchRun_Seq` and `_Col` (+174 B each — the direct variant + the dispatch),
  `PageCache_Audit` (+376 B, the direct-regime arm, DEBUG-only), `Level_LoadArt` (+40 B, the
  latch), `PageCache_Init` (+4 B, clearing it). No other proc's span changed except by
  inter-symbol padding.

### F2 — make the block prefetch's speculation land instead of dying
* **Mechanism.** Three sub-options, in increasing order of ambition:
  * **F2a (guard).** Skip speculation while `BLOCK_STAGE_SLOTS / claim_rate` is below the
    8-tick lead. Both terms are already cheaply available (the claim rate is a per-pass
    count; `Block_Stage_Gen` already exists). This removes the dead work without removing
    the prefetch on the axes where it earns its keep.
  * **F2b (batch).** Stage the ahead strip as a UNIT rather than `k = 1` per frame, so it
    arrives coherently instead of dribbling in and being evicted piecemeal.
  * **F2c (policy).** Replace round-robin eviction with camera-distance or
    time-to-consumption ordering, so a speculative block is not the first thing evicted.
    §3's negative result on capacity is what points at policy.
  * Independently: **the memo generation key is self-defeating** — `Block_Stage_Gen` is
    bumped by the very claims the scans make, so the memo cannot hit at any interesting claim
    rate, and it is only ever recorded on the all-hits exit. Key the memo on something the
    scan does not itself invalidate.
* **Measured saving.** Throwaway B (the crude version — prefetch removed entirely):
  decompresses 4.53 → 1.47/tick, work/tick 190,931 → 169,351 (−21,580). A landing prefetch
  should reach that saving **without** B's `right` regression.
* **Risk class: schedule-changing.** It changes when decode work happens, which changes the
  per-frame spike distribution — and §6 shows that distribution, not the mean, is what
  decides whether a tick overruns.
* **Verification.** Exact decompress rate via `Block_Stage_Gen` at all four camera states
  (the `right` state is the regression guard, and it must stay at 1.000 frames/tick), plus
  work/tick.
* **⚑ PARK for a ruling** — F2b and F2c are §4.7/§9.7 design changes.

### F3 — F1 + F2 together
* **Measured.** Throwaway D: work/tick 121,598, **frames/tick 1.107**. The choke is gone.
  Recorded here as the joint result, because §5's arithmetic says neither half suffices.

### F4 — direct-map the staging probe
* **Mechanism.** `TileCache_FindStagedBlock` linear-scans all 16 keys (`cmp.l (a1)+ / dbeq`).
  A small hash or a direct-mapped index on the (sec_x, sec_y, block) key makes it O(1).
* **Measured saving ceiling.** 10,319 cyc/tick at `maxdiag` (9.7% of the fill), 3,725–4,798
  at the single axes; 416 cyc per probe. A realistic direct map recovers most of it.
* **Risk class: value-identical.** Self-contained inside one proc plus the key table's shape.
* **Note.** This is also what makes any future slot-count increase affordable — the 20-slot
  negative in §3 was partly self-inflicted by this scan.
* **Verification.** The probe's `FindStagedBlock` row at `right`/`down`.

### F5 — move `PageCache_Audit` off the fill path — ✅ SHIPPED 2026-08-19 (`perf/audit-off-fill-path`)
* **Mechanism.** It is DEBUG-only and correct, but it ran INSIDE `Tile_Cache_Fill` and
  spends ~110,000 cycles in a single pass every 128, which lands as a 7,333 cyc/tick
  contamination on one DEBUG measurement window in four.
* **Measured cost.** 3,548 cyc/frame amortised at `maxdiag`; zero in release.
* **Risk class: value-identical, DEBUG-only.** Cheap and worth doing first purely to
  de-noise every subsequent measurement in this arc.
* **What shipped.** The interval gate moved out of `Tile_Cache_Fill` and into the LEVEL
  STATE's tick (`games/sonic4/test/ojz_scroll_test.emp`), one call after the fill returns —
  a sibling of the fill, not a child. Cadence is UNCHANGED: the fill's own
  once-per-physical-frame gate already advanced the counter once per LOGIC TICK (idle:
  `Page_Audit_Ticks` 109 → 11 over 30 ticks / 31 frames), so the audit still fires every
  `PAGECACHE_AUDIT_INTERVAL` = 128 ticks and its blind window is still one interval. The
  witness is preserved because the corruption class is MONOTONE — nothing re-derives
  `pf_refcount` from the nametable, so a periodic audit never MISSES a drift, only reports
  it late. It is spelled inline rather than as an engine proc because a new zero-byte
  DEBUG-only label lands in the release deb2 appendix and moved `demo.bin` (aae04929 →
  6710c1ac; `s4.bin` did not move, so sonic4 alone would not have caught it).
* **De-noise, measured at `idle`** (the audit fires; the instrument closes there):
  `Tile_Cache_Fill` 4,780 → **926 cyc/tick** (−3,854, = 100.4% of the audit's own
  3,837 cyc/tick row, which survives intact at 3,811).
* **The null — the parcel's real product.** At `right`, `down` and at non-firing `maxdiag`
  phases (settle 160 / 186), nothing else moves: the fill loses only the removed gate
  (−42 cyc/frame at `right`/`down`, −14 at `maxdiag`/160), and every leaf row, every
  bracket, `work/tick`, `frames/tick` and the exact `Block_Stage_Gen` decompress counts are
  unchanged. **§2's other rows are therefore proven audit-free** — F1/F2/F4's savings were
  never contaminated.
* **A second, independent demonstration of §7.** At the canonical `maxdiag` (settle 180) the
  fill row moves only 106,138 → 105,231 cyc/tick while the `PageCache_Audit` row collapses
  7,333 → 872: old oracle stops ATTRIBUTING the pass rather than moving it. Its rows already
  fail to close in that state — the `GameState_OJZScroll_Update` bracket (55,145 cyc/frame)
  is smaller than the sum of the children the probe measures under it (56,219), both before
  and after. Read the F5 de-noise off `idle`/`right`/`down`, never off `maxdiag`.
* **Probe change.** `tools/streaming_choke_probe.py` no longer tables `PageCache_Audit`
  under `Tile_Cache_Fill`: it is out of the child map (so the inclusive check stays honest)
  and prints flush-left with no "%fill" — it read 411.6% of the fill at `idle` in the first
  post-move run, which is what a percentage of a routine you are not inside looks like.

### F6 — reconsider the tile-cache margins
* **Mechanism.** The cache is 80 × 60 for a 40 × 28 viewport. Column-fill cost is linear in
  `TILE_CACHE_ROWS` and row-fill cost linear in `TILE_CACHE_COLS`, so `TILE_CACHE_MARGIN_H`
  20 → 8 and `MARGIN_V` 16 → 8 would cut patched words per tick from 280 to 200 (−29%).
* **Estimated saving.** ~13,000 cyc/tick at `maxdiag` on the patch runs alone, pro rata from
  the measured per-word costs — and it compounds with F1 rather than overlapping it.
* **Risk class: DESIGN-CHANGING.** Margin is lookahead; less of it means less slack for the
  demand fill and a tighter coupling to camera speed. It also interacts with F2's lead
  arithmetic (a smaller cache means a shorter prefetch lead, which HELPS §3's inequality).
* **⚑ PARK — owner ruling required.** Recorded because the interaction with F2 is real, not
  because it is recommended.

### Explicitly NOT a fix — raising `BLOCK_STAGE_SLOTS`
Measured null (§3, throwaway A). Recorded so the arc does not re-derive it: 20 slots moves
work/tick by +0.05% and the frame rate not at all, and 24 slots does not fit in RAM.

---

## 9. Question 6 — instrument asks for oracle-next

*This section goes verbatim to the oracle-next session.*

Sorted against oracle-next's in-flight profiler v1 (per-routine `cyclesSelf` + `stallCycles`
with a completeness identity, and opt-in `perFrame[]`), per the coordinator's 2026-08-19
note. Only category (c) generates work.

### (a) Already satisfied by v1 on arrival — no ask, just confirmation that these land

1. **`cyclesSelf` per routine.** Every exclusive figure in §2 was hand-derived by subtracting
   child rows from parent rows, which first required proving sole-parenthood for each callee
   by grepping every `jbsr` in the tree. `cyclesSelf` deletes both the subtraction and the
   proof burden.
2. **The completeness identity (Σ self + unattributed == sample, exact).** This is the one
   that matters most here. Old oracle silently lost **26,163 cyc/frame — 20.6% of the frame**
   at max-diagonal while closing to within 1–2% at the three non-lagging states (§7). I found
   it only because a
   parent row came out smaller than its children. An exact identity would have surfaced it on
   the first run, and it directly revises how much of this packet's max-diagonal table can be
   quoted as exact.
3. **`stallCycles` per routine.** Everything in this packet is ideal cycles. The two
   components it indicts — the S4LZ decode and the 280-word/tick patch loop — are both
   memory-traffic-bound, so their true share is understated by an unknown amount and the
   ranking in §8 could in principle change under real stall accounting.
4. **`perFrame[]` `{frame, cycles, stallCycles, hintCycles, vintCycles}`.** The fill's cost
   is BURSTY: block-crossing ticks pay 4–5 synchronous decompresses, interior ticks pay
   none. 31-frame averages hide that entirely, and §6's most instructive result — throwaway B
   LOWERING the mean fill cost at `right` while RAISING the lag — is a fact about the spike
   distribution that only a per-frame series explains. Burst analysis is exactly the
   anticipated customer; this arc is one.

### (b) Composable TODAY on oracle-aether via mclk-stamped watch hits — booked as method, not as gaps

Noted for the record and for whoever runs the next parcel; these would have shortened this
one materially.

5. **Staging-claim timeline** — watch writes to `Block_Stage_Next` / `Block_Stage_Gen`. Gives
   exact decompress instants with mclk, i.e. the rate AND its burst structure. I got the rate
   only because `Block_Stage_Gen` happens to be a monotone counter bumped once per claim; on
   a component without such an accident I would have had nothing.
6. **Residency-lifetime timeline** — watch `Block_Stage_Keys` slot writes (stage instant) and
   the `FindStagedBlock` hit path (use instant). The difference IS the
   "staged-but-evicted-before-use" waste. **This is the single instrument that would have
   turned §3's central claim from an inference — residency 3.53 ticks < lead 8 ticks, derived
   from slots ÷ rate — into a direct measurement of dead speculations.** Worth building
   before the fix parcel, so F2's success criterion is a measured lifetime rather than a
   proxy.
7. **Budget timeline** — watch `Cache_Fill_Budget` writes for the per-pass consumption
   profile, which is what would show whether a pass is budget-bound or geometry-bound.

### (c) GENUINELY NEW — these are the asks

**C1. Attribution correctness across an interrupt / frame boundary.**
The measured defect is §7: when a profiled routine is preempted by VBlank, its cycles go
missing — 20.6% of the frame at 2.067 frames/tick, ~1% at 1.000. **Ask:** define and
document what the profiler does when an interrupt preempts a profiled routine, and make
`cycles` / `cyclesSelf` exact under preemption — credit the preempted routine's pre- and
post-interrupt segments to it, and the handler to the handler. If an exact split is not free,
a `preemptedCycles` (or `resumedSegments`) diagnostic per routine would at least make the
loss visible and bounded. **Replaces:** my workaround of building two extra single-axis camera
states purely to obtain a non-lagging measurement, which still leaves the actual subject of
the parcel — sustained max-diagonal — decomposable only indicatively. **Note:** the v1
completeness identity will REVEAL this defect, but does not by itself FIX the attribution;
these are two different asks and this is the second one.

**C2. Exact total call counts, not integer-rounded per-frame averages.**
`calls` is a per-frame average truncated to an integer. For a routine invoked 4.53 times per
logic tick it reports `2`; `TileCache_DecompressBlock` and `S4LZ_DecompressDict` are called
1:1 and report `2` and `1`. Every rate in this packet therefore had to come from an engine-side
monotone counter that happened to exist (`Block_Stage_Gen`) or from cache geometry. **Ask:**
a `callsTotal` integer alongside the per-frame average, over the sampled window. **Replaces:**
hunting the engine's RAM for an accidental counter — which worked here only by luck.

**C3. Per-routine CALLER breakdown, even just top-N.**
`TileCache_FindStagedBlock` has three live call sites inside a single routine (column fill,
row fill, prefetch scan) plus a fourth elsewhere. No amount of parent/child subtraction can
split a row across call sites that share a parent, so I built two additional camera states
(`right`, `down`) whose sole purpose was to make one call site active at a time. **Ask:**
`callers: [{addr, calls, cycles}]` per routine row, top-N is plenty. **Replaces:** constructing
one bespoke camera state per call site — which does not generalise, since not every call site
has a camera axis that isolates it. Of the three asks this is the one that most changes the
shape of a decomposition parcel.

---

## 10. What this packet does NOT cover

* **One act, one section.** Everything is OJZ act 1 section 0, whose art pool is fully
  resident. An act whose pool exceeds `PAGE_FRAMES` would engage the page tier and could show
  a genuinely different choke — the one §9.7 was designed for. **No such act exists in the
  tree today**, so the page-tier machinery has never been measured under its design load.
* **No section crossing.** No sample crosses a section boundary; the transition frame is
  unmeasured.
* **A near-empty game state.** `GameState_OJZScroll` is a scroll test. `RunObjects` (1,270
  cyc/frame), `Render_Sprites` (703) and `TouchResponse` are near-idle here and will grow.
  The 33% cut §5 asks for is therefore a floor on what the fix has to deliver, not a ceiling.
* **Ideal cycles only.** See caveat 0 and instrument ask (a)3.
* **Left / up motion.** Only rightward and downward axes were measured. The leftward fill
  path (`.h_left_fill`) and the paired upward fill (`.v_top_fill`, which fills rows two at a
  time) are structurally different code and are unmeasured.
* **Throwaway C's correctness.** It measures a cost floor with wrong output; F1's real
  saving is bounded by it, not equal to it.
