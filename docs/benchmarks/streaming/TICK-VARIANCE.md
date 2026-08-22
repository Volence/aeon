# The tick-variance measurement — which ticks spike, why, and the honest work/tick retake

Measured 2026-08-20 by `tools/tick_variance_probe.py`, the first probe to run on the NEW
oracle's exact per-invocation profiler (`oracle` main, Rust). It answers the two questions
the streaming arc left open in one run: **the close-out's "mean under the line" hypothesis**
(`ARC-CLOSEOUT.md`, Addendum 2026-08-20) and **the variance question** — the arc's named
successor item.

| | |
|---|---|
| ROM | `s4.debug.bin`, **crc `5be03175`**, 715,084 B — **byte-identical to sigil `af2a4429`'s frozen golden**, i.e. exactly the arc-close-era image (`git show af2a4429:crates/sigil-harness/golden/s4.debug.bin`) |
| engine bytes | unchanged since the arc's coda `afccb141` — every commit after it is docs/measure/plan, so this IS the close-out's ROM |
| instrument | `oracle/target/release/oracle-aether`, oracle main `8236559` (binary built 05:12, last crate-touching commit `ccff237`/`018612a`; the three commits after it are docs) |
| state | `maxdiag`, settle 180 / lead 24 / 31-frame window — byte-identical ritual to `engine_baseline_probe.py` and `streaming_choke_probe.py` |
| boots | **3**, fresh server process each. **Spread 0 on every figure below**: ticks `[29,29,29]`, `sampleCycles` `[3968176,3968176,3968176]`, work/tick `[112,897 ×3]` |
| wall | control 1.0 s + 3 boots × 14.7 s = **45.3 s total**, `up 2 days, 7:28`, load average 4.74 |

**Row basis, and it is repeated beside every figure in the tool's own output.**
`cyclesSelf` is the additive basis (callees excluded; rows + both interrupt buckets sum to
the window with remainder 0, checked at every sample). `cycles` is inclusive of callees and
excludes preemption, and is labelled `incl` wherever it appears. **`stallCycles` is reported
separately and never absorbed into a cycle figure.** The old instrument's three caveats — the
30/31 window division, `max(1, …)` on `calls`, `interrupts.hint` conflating HBlank with
VBlank — do not exist here and are deleted, not carried.

---

## 0. The control — the arc stops if this misses, and it did not

Before any new number, the corpus A/B's own designated **PHASE-0 REFERENCE ROW** was
re-measured **on the A/B's own ROM**: `s4.debug.bin` crc `d22dda85` / 713,295 B, recovered
byte-identically from sigil `7b46f075`'s committed golden (no rebuild), at both camera states.

| check (pinned from `oracle/docs/2026-08-20-profiler-corpus-ab.md`) | idle | maxdiag |
|---|---|---|
| `$FFB452` cyc/video-frame | **1878.0** ✓ | **1878.0** ✓ |
| `$FFB452` calls/frame | **4.000** ✓ | **4.000** ✓ |
| `$FFB452` `stallCycles` | **0** ✓ | **0** ✓ |
| `sampleCycles` | **3968178** ✓ | **3968178** ✓ |
| `Logic_Tick` delta | **30** ✓ | **15** ✓ |
| camera transit | (96,144) → (96,144) ✓ | (320,368) → **(560,608)** ✓ |
| whole 31-row `perFrame[].vintCycles` series (§12) | **exact** ✓ | **exact** ✓ |
| whole 31-row `perFrame[].stallCycles` series (§12) | **exact** ✓ | **exact** ✓ |
| completeness identity remainder | **0** ✓ | **0** ✓ |

The corpus ROM ships no listing, so the symbol addresses are borrowed from the current
build's and **validated on it** by three witnesses the A/B publishes independently:
`Camera_X` 96, `Camera_Y` 144, and `Camera_Target` resolving to leader **`$FF8DB0`** — the
A/B's exact value. A borrowed address that described a different ROM would fail all three.

**And the same reference row reads 1878.0 / 4.000 / stall 0 on the CURRENT ROM too**, at both
states — so the migration did not silently change what the row means.

**Red-first, all three exit 1** (`--poison`, transcripts run 2026-08-20):

| poison | what it breaks | observed |
|---|---|---|
| `identity` | adds 1 cycle to the completeness remainder | `BLOCKED: completeness identity does not close: sampleCycles 3968176 - (self 3968176 + unattributed 0) = 1` |
| `prefix` | drops rung 15 from the ladder | `BLOCKED: prefix ladder is not contiguous 1..31: 30 rungs, missing [15] — every difference across a gap would be booked as one frame's work and read as a spike` |
| `control-rom` | runs the corpus expectations against the CURRENT ROM | `BLOCKED: [control idle] sampleCycles 3968180 != 3968178; ticks 31 != 30; perFrame vintCycles series differs from A/B §12 …` |

---

## 1. THE HEADLINE — the honest work/tick retake, and the hypothesis SURVIVES

The close-out downgraded *"work/tick 123,016, mean 4,984 UNDER the 128,000 line"* to a
hypothesis because it was an old-instrument number with a 21.55-point attribution hole
behind it. Retaken with no attribution gap to hide in:

```
work over the window = sampleCycles - VSync_Wait(inclusive)
                     = 3,968,176   - 694,156                = 3,274,020
work per tick        = 3,274,020 / 29 ticks                 =   112,897 cyc
```

> ### **112,897 cyc/tick — UNDER the 128,000 line by 15,103 (88.2 % of a video frame).**
> Spread **0** across three boots. The mean was under the line, and it is under by **three
> times the margin** the old instrument claimed.

`sampleCycles` is the machine's own undivided cycle count for the window, so the only
modelling in that expression is *"the vsync spin is not work"*. Interrupt time is work and is
inside it — the same convention the 128,000 line uses. (`VSync_Wait` self is 685,556; the
8,600 difference is a callee reached from inside the wait and is counted as spin here.)

### 1.1 Why the number moved, itemised — and it is NOT the attribution hole

| | old instrument (close-out coda) | new instrument (here) |
|---|---:|---:|
| frames/tick | 1.192 (26 ticks / 31 frames) | **1.069 (29 ticks / 31 frames)** |
| `VSync_Wait` per frame | 24,409 | **22,392** |
| work/tick | 123,016 | **112,897** |
| implied total work over the 31-frame window | 123,016 × 26 = **3,198,416** | **3,274,020** |

**The two instruments agree on the window's total work to 2.4 %.** The per-tick difference is
almost entirely the *tick count*, not the cycles. That is the honest answer to the addendum's
worry: the close-out's formula was `(frame total − VSync_Wait) × frames/tick`, built on the
frame TOTAL rather than on a sum of rows, so the 21.55-point row-attribution loss never
entered it — only `VSync_Wait`'s own row did.

### 1.2 The tick-count divergence, stated and NOT resolved here

On **byte-identical ROM bytes** the old emulator ran 26 logic ticks in 31 frames where this
one runs 29 (camera 416 px vs **464 px**). At idle the same gap is one tick (old 1.033 / 30
ticks, new **1.000** / 31 ticks) and the work/tick figures nearly agree (old 43,726, new
**44,455**, +1.7 %). At the corpus-era state the two agree exactly (both 15 ticks / 2.067
frames per tick).

So the divergence is not a constant instrument offset — it appears **where the tick sits
close to the frame boundary**, which is where `frames/tick` is a threshold function of
per-tick work and a 1-2 % timing difference flips whole frames. This measurement does not
settle which machine's timing is right, and does not need to: both say the mean is under the
line, and both say the residual is variance. **Booked as an open item, not smoothed.**

> **Prior art, added 2026-08-20 after the oracle team registered this as
> F-TICK-BOUNDARY-DIVERGENCE (oracle `9003a79`):** this clock-honesty class has been settled
> once before, in their favor. The 2026-07-23 RT-3 A/B (VGM register streams, both emulators,
> same ROM) root-caused a bounded ~8-tick offset to **oracle-old over-dropping ticks** via
> `ClampHandshakeTimeDeterministic`'s over-conservative bus-arbitration clamp, corroborated at
> the time by the sound driver's own N=136→137 retune note; the new core was ruled
> tick-accurate with steady-state 60.000 Hz byte-exact on both. Different window, same class:
> oracle-old's clock historically loses ticks at arbitration-heavy boundaries. Still not a
> ruling for THIS window — the settling experiment (single-tick trace at the first divergent
> boundary, frames 7-8) remains the test, whoever reaches it first pings the other.

---

## 2. THE DISTRIBUTION — two populations, and the ceiling is real

Per-frame per-routine rows are not in `perFrame[]` (whole-frame totals only, by spec), so
they are recovered by **prefix differencing**: 31 samples of length 1..31 from the same start
state, differenced. Exact because the machine is deterministic and the server attributes open
invocations as they go (`unattributedCycles == 0` at every rung). Controlled two ways:
contiguity, and the top rung reproducing the direct 31-frame sample cell for cell.

`work` = frame cycles − that frame's `VSync_Wait` span. `fillsub` and `S4LZ` are **sums of
self** over declared rows (see §5 for why inclusive diffs are not per-frame quantities); the
fill subtree's 15 rows close against `Tile_Cache_Fill`'s inclusive window total to −0.06 %.

```
 frame tick     work  %128k    spin  stall   vint  fillsub    S4LZ  n  dec  headcol  botrow  blk c/r
   205    T   111654  87.2%   16352   2220  13920    58922       0  0    0      105      95     6/5
   206    T   115942  90.6%   12062   2220  13908    63274       0  0    6      107      97    6/6 R
   207    T   113936  89.0%   14064   2220  13920    61256       0  0    0      109      99     6/6
   208    T   111264  86.9%   16748   2220  13908    58678       0  0    0      111     101     6/6
   209    .   127930  99.9%      70   2220  13920   107934   48882  4    5      113     103    7/6 C
   210    T    51290  40.1%   76718   2182   7840     8712       0  0    0      113     103     7/6
   211    T   116678  91.2%   11326   2220  13920    62618       0  0    0      115     105     7/6
   212    T   115740  90.4%   12270   2220  13908    62708       0  0    0      117     107     7/6
   213    T   111066  86.8%   16936   2220  13920    60116       0  0    0      119     109     7/6
   214    T   111214  86.9%   16792   2220  13908    59900       0  0    0      121     111     7/6
   215    T   114814  89.7%   13194   2220  13920    64556       0  0    6      123     113    7/7 R
   216    T   112534  87.9%   15472   2220  13908    62288       0  0    0      125     115     7/7
   217    T   109418  85.5%   18586   2220  13920    59242       0  0    0      127     117     7/7
   218    .   127948 100.0%      70   2220  13908   107542   40986  3    5      129     119    8/7 C
   219    T    40740  31.8%   87256   2182   7852       38       0  0    0      129     119     8/7
   220    T   112330  87.8%   15670   2220  13908    61448       0  0    0      132     121     8/7
   221    T   111682  87.3%   16330   2220  13920    60908       0  0    0      134     123     8/7
   222    T   107408  83.9%   20598   2220  13604    58976       0  0    0      136     125     8/7
   223    T   107674  84.1%   20334   2220  13920    58796       0  0    0      138     127     8/7
   224    T   112366  87.8%   15638   2220  13908    63272       0  0    6      140     129    8/8 R
   225    T   110302  86.2%   17704   2220  13920    61184       0  0    0      142     131     8/8
   226    T   107522  84.0%   20478   2220  13908    58606       0  0    0      144     133    9/8 C
   227    .   127938 100.0%      70   2220  13920    91070   25736  2    5      145     135     9/8
   228    T    22634  17.7%  105374   2220   8304       38       0  0    0      146     135     9/8
   229    T   108852  85.0%   19156   2182  13400    60242       0  0    0      148     137     9/8
   230    T   111664  87.2%   16342   2220  13908    60440       0  0    0      150     139     9/8
   231    T   106888  83.5%   21114   2220  13920    57740       0  0    0      152     141     9/8
   232    T   106930  83.5%   21072   2220  13908    57740       0  0    0      154     143     9/8
   233    T   111474  87.1%   16538   2220  13920    62326       0  0    6      156     145    9/9 R
   234    T   109438  85.5%   18564   2220  13908    60308       0  0    0      158     147     9/9
   235    T   106750  83.4%   21258   2220  13920    57826       0  0    0      160     149   10/9 C
```

**The frame budget is a hard ceiling and three frames sit ON it.** Frames 209, 218 and 227
read 127,930 / 127,948 / 127,938 cycles of work against a 128,000-cycle frame — **99.9 %,
100.0 %, 100.0 %**, with the vsync spin collapsed to **70 cycles**. Those are exactly the
three frames that carried no logic tick. Everything else lives between 83.4 % and 91.2 % of the frame.

### 2.1 Per-tick, with the frame-granularity bound stated rather than hidden

A tick begins part way into the frame its `Logic_Tick` lands in and the ladder can only cut
at frame boundaries, so each tick is a **range**: lower = the frames strictly after its start
frame, upper = every frame in its group. Both bounds are exact measurements.

| population | n | work |
|---|---:|---|
| ordinary ticks (one frame each) | 20 | 106,888 – 116,678 (83.5 – 91.2 % of a frame) |
| **spike ticks** (two frames each) | **3** | lower **127,930 – 127,948**, upper **235,460 – 239,194** (1.84×) |
| recovery ticks (the tick after a spike) | 3 | **22,634 / 40,740 / 51,290** (17.7 – 40.1 %) |

Whole ticks in the window (the two partial ends dropped): n = 26, min 22,634, **mean
117,524**, max 239,194.

**Averaging across these populations finds nothing** — the A/B's warning, confirmed on a
different partition than the one it named (§5.1).

---

## 3. THE SPIKE TICKS — named, with one common cause

| tick | frames | work (lower..upper) | `S4LZ_DecompressDict` self | calls | cyc/call |
|---:|---|---|---:|---:|---:|
| 3 | 208, 209 | 127,930 .. 239,194 | **48,882** | 4 | 12,220 |
| 11 | 217, 218 | 127,948 .. 237,366 | **40,986** | 3 | 13,662 |
| 19 | 226, 227 | 127,938 .. 235,460 | **25,736** | 2 | 12,868 |

> ### The cause: **S4LZ dictionary decompression, in a burst, on the block-column crossing.**
> `S4LZ_DecompressDict` ran in **exactly 3 of 31 frames — 209, 218, 227 — and they are the
> three spike frames.** It runs nowhere else in the window. Each call costs ~12.2-13.7 k
> cycles and the tick takes 2-4 of them at once.

**And the burst is on the block grid, derived from the engine's own constant** (`BLOCK_TILE_SIZE
= 16` tiles = 128 px, read from `engine/system/constants.emp` by the probe, not pinned):

- Block-grid crossings in the window: `(206 R) (209 C) (215 R) (218 C) (224 R) (226 C) (233 R)
  (235 C)` — where **C** = `Cache_Head_Col` crossed a 16-tile block edge, **R** =
  `Cache_Bottom_Row` did.
- **3 of 3** S4LZ frames are within one frame of a **column**-edge crossing.
- **The four ROW-edge crossings cost nothing like it.** Frames 206, 215, 224 and 233 each
  claim 6 blocks (`Block_Stage_Gen` +6) and `S4LZ_DecompressDict` **never runs**:
  `TileCache_DecompressBlock` costs ~864 cyc/call there because the block is **already
  staged**. Row demand is served from staging; column demand is not.
- The cadence follows from the camera, not from a fit: 16 px/tick at the follow ceiling,
  128 px per block ⇒ **one column crossing every 8 ticks**, and the window shows exactly that
  (ticks 3, 11, 19).
- On the burst frame the fill's budget is **exhausted**: `Cache_Fill_Budget` 6 → 1 and
  `Cache_Fill_Rows_Left` 2 → 0 on frames 209 / 218 / 227 and nowhere else. That is why the
  next tick is nearly free (fill subtree 38 cycles) — the work was pulled forward, not
  avoided.

**What is measured vs what is inferred.** Measured: the burst, its size, its calls, its
frames, the block-edge coincidence, the budget exhaustion, and that row crossings find their
blocks staged while column crossings do not. **Inferred, and flagged as such:** *why* the row
side is covered. It is **not** the F2a speculation guard — `Cache_Spec_Skips` advances on 27
of the window's 28 ticks, i.e. speculation is suppressed almost throughout, exactly as
`BLOCK_SPEC_LEAD_TICKS`'s own comment predicts for sustained max-diagonal. The leading
hypothesis is that the column crossing decompresses blocks that the row crossing three ticks
later re-uses out of the staging slots. What would settle it is
`tools/staging_lifetime_timeline.py` — which slot served each row-crossing claim, and who
filled it. **Not taken here.**

> **SETTLED 2026-08-21 — hypothesis REFUTED** (`STAGING-LIFETIME.md`, on the then-current
> ROM `0dbaa80f`; the bursts reproduce to the cycle). No crossing block, row or column, is
> ever pre-staged at maxdiag: the row crossings claim their own six blocks fresh — the
> `Block_Stage_Gen` +6 above IS those claims, so "find their blocks staged" two paragraphs
> up is corrected too — and they are cheap because every one decodes as the EMPTY form
> (the zero-page arm; that is what the ~864 cyc/call DecompressBlock figure was, not
> "already staged"), while the column blocks are COMPRESSED. The staging carryover that
> does exist is intra-axis, between crossings. The column side finds nothing staged
> because the F2a latch suppresses the one mechanism that pre-stages columns — measured
> covering the crossings completely at `right`/`down` when the latch is up.

---

## 4. stallCycles at max-diagonal — the first honest stall row for this state

| | cyc/frame | where |
|---|---:|---|
| whole machine (`perFrame[].stallCycles`) | **2,216.3** | min/max per frame 2,182 / 2,220 |
| `VBlank_Handler` | 2,216.3 | 100 % of it |
| `Process_DMA_Critical` | 2,216.3 | all of the above, one level down |
| `VInt_Level` | 2,003.9 | inside the same bracket |
| `VInt_Lag` | 212.4 | inside the same bracket |
| `interrupts.vint` bucket | 2,216.3 | the same cycles, keyed by cause |

**Every stalled cycle on this ROM at this state is the VBlank DMA drain** — the rows nest, so
that list is a *location*, not a second total. Nothing outside `Process_DMA_Critical` stalls
measurably. This reproduces the A/B §9.4 shape (2,200.4 cyc/frame at its maxdiag) on a ROM
nine parcels newer, and it is the row `ENGINE-BASELINE.md` §4b booked as
`"UNMEASURABLE-ON-THIS-INSTRUMENT"`.

Stall is **1.7 % of a frame** — smaller than the spike ticks' overrun by an order of
magnitude, and it is flat across the window (the burst frames stall the same 2,220 as their
neighbours). It is not part of the variance story, and this is the measurement that says so
rather than assuming it.

---

## 5. Two instrument findings the next migrated probe will need

### 5.1 The A/B's `vintCycles` partition is a property of ITS state, not a method

A/B §12 shows `vintCycles` partitioning tick-frames from lag-frames *exactly* at the
corpus-era max-diagonal (15 high == 15 ticks). **It does not generalise, and this probe
checks it against ground truth rather than using it.** On the current ROM at max-diagonal:

- ground truth (`Logic_Tick` read at every frame boundary): 28 of 31 frames carried a tick;
- `vintCycles` on tick frames spans 7,840 – 13,920; on the three lag frames it is 13,908 /
  13,920 / 13,920 — i.e. the lag frames are at the **top** of the range, and the low-vint
  frames (210, 219, 228) are ticks.
- **No threshold separates them.** The probe prints `VERDICT: NO vintCycles threshold
  separates tick frames from lag frames at this state`.

The mechanism is visible in the table: the cheap *recovery* ticks are the low-vint frames.
A partition that reads as a clean law at one state is a coincidence of that state's phase —
the standing "clean constant = suspect confound" caution, caught by carrying the engine
counter instead of trusting the derived one.

### 5.2 Differencing INCLUSIVE `cyclesTotal` does not give per-frame cost

Measured while building this probe, and the reason every per-frame figure above is on the
self basis: an invocation that straddles a frame boundary has its inclusive cost credited in
a lump. `GameState_OJZScroll_Update` reads **3,836** in frame 209 and **149,104** in frame 210
— more than a whole 128,000-cycle frame — while its own child `Tile_Cache_Fill` reads 97,878
in frame 209. `cyclesSelf` has no such problem: it is additive by construction and the
server's identity closes on it at every rung, which the probe checks. **Subtree costs are
therefore built by summing self over a declared subtree and checking the sum against the
parent's inclusive window total** (fill: −0.06 % at maxdiag, −3.49 % at idle, both disclosed
by the tool).

---

## 6. What this means for the parked F6 question — context only

**No recommendation is made here and none is implied. F6 stays owner-parked.**

The arithmetic, for whoever eventually rules on it:

- The mean is **112,897 (88.2 %)** and 20 of 26 whole ticks sit between 83.5 % and 91.2 % of
  a frame. **A mean lever has ~15 k cyc/tick of headroom to give and no frame to win with
  it** — none of those ticks is anywhere near the ceiling.
- The whole residual `frames/tick` cost is **3 ticks in 26**, each needing between 127,930
  and 239,194 cycles, and each carrying **25.7 - 48.9 k cycles of `S4LZ_DecompressDict` that
  no other tick in the window carries**. The burst is 23 - 38 % of the spike tick's lower
  bound.
- Those three ticks are **predictable**: one per block-column crossing, i.e. one per 128 px
  of horizontal camera travel at the follow ceiling, every 8 ticks.
- The tick after each spike costs **17.7 - 40.1 %** of a frame.

So the shape of the remaining problem is *scheduling a known, periodic, ~2-4 block burst*,
not shaving means. Which lever — if any — is owner's call.

---

## 7. What this does NOT establish

- **One state, one act, one section.** OJZ act 1, sustained max-diagonal at the follow
  ceiling (dx = dy = 29 × 16 px, `Camera_Art_Hold` 0, `Dbg_Cam_Clamp_Frames` 0,
  `PageIn_Fully_Resident` set). `right`, `down` and every other content shape are unmeasured
  here.
- **DEBUG shape only.** `s4.debug.bin`. The release shape carries different asserts and its
  own baselines (the F1 packet measured the two shapes disagreeing by more than their fix).
- **The tick-count divergence between the two emulators is reported, not resolved** (§1.2).
  Nothing here says which machine's timing is right.
- **Why the row-side block demand is covered is a hypothesis** (§3), not a measurement.
  *(Settled 2026-08-21: refuted — see §3's addendum and `STAGING-LIFETIME.md`.)*
- **The per-tick figures are ranges, not points** — the ladder cuts at frame boundaries and a
  tick does not start at one. Both bounds are exact; the truth is between them.
- **No pixel evidence.** This is a cycle instrument; nothing here observes the picture.
