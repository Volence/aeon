# §9.7 — Decision memo for the four open points (2026-08-06, overnight prep)

**Status: options + evidence + recommendation per point. NO ruling made — all
four are reserved for Volence.** Sources: the research corpus
(`2026-08-05-deferred-work-research.md`, incl. the fresh idle table), the
Phase-2 spec (`specs/2026-07-02-art-streaming-phase2-design.md`), the
unified-prefetch note (sigil `7199792a`, §7 + §10), and the read-only code
survey in the companion bookmark sketch
(`2026-08-06-bookmark-implementation-sketch.md`).

**Coupling note up front:** D1 is the master decision. D2 and D3 change shape
depending on it — each is written with a "under bookmark-first" and "under
pre-chunk-only" branch so one ruling on D1 mostly settles them.

---

## D1 — Sequencing: bookmark-first (plan Task 2) vs page-size-sweep-first (unified-prefetch §7.3)

**The question.** The banked plan builds the resumable decoder + bookmark
immediately (Tasks 2–4) and cuts the format over after (Task 5). The
unified-prefetch note's Phase-2 contract (§7.3) says: run the page-size sweep
FIRST, land the bookmark only if small pages miss the latency target.
Note both agree pages exist regardless — they are the residency granule and the
format (Task 5 happens either way). The only question is whether the decoder
under them is resumable or blocking-with-small-chunks.

**Option A — bookmark-first (keep plan order).**
- The 2026-08-05 idle re-measurement already answers the question the sweep was
  going to ask: a 64-tile/2 KB page ≈ 45 K cycles does NOT fit the measured
  worst-window *average* (42.5 K idle, diagonal fall), and per-frame minima
  inside that window are necessarily lower. 2 KB pages without the bookmark
  overrun or defer exactly when streaming demand peaks.
- The 1 KB fallback (~22.5 K cyc, ~2× average margin) rests on two unmeasured
  softeners: per-frame *minima* (averages hide them) and the fact that the OJZ
  test scene is object-light — real levels with badniks shave idle further.
  Choosing pre-chunk-only means re-running this decision every time a level
  gets heavier; the bookmark consumes all idle with zero overshoot and makes
  page size a pure density/manifest knob, closed forever.
- P2a is standalone-provable on the *existing* 256-tile/8 KB pages (~620 K cyc
  — heavy forced preemption, a brutal self-test) before any format work. The
  plan's Task-2 decoder listing is already written and verified against the
  live `zx0.emp` control flow (sketch §1).
- Pre-chunk-first ships an interim blocking decoder into the streaming runtime
  that a later bookmark must replace — a dormant scaffold of exactly the kind
  the clean-not-bolted-on rule exists to prevent.
- KosM precedent: the corpus lens on this ("pre-chunk vs bookmark is a false
  fork — KosM is both layers") favors building both, and A is the order that
  ends with both.

**Option B — sweep-first (§7.3 as written).**
- Honest case for it: the bookmark is the single most contract-hostile
  mechanism in the engine's history (stacked-PC rewrite, rte from non-handler
  context, stackless region) and needs Sigil support that does not exist yet
  (sketch §6). Small pages need zero new Sigil machinery. If 1 KB pages pass
  the P2c stress, the bookmark's remaining value is marginal (~latency
  smoothing) against real complexity.
- Against it: the sweep's decisive scenario (worst diagonal, real-level object
  load) doesn't exist yet to measure — the sweep would pass on OJZ and the
  premise re-opens later; and §7.3 predates the 2026-08-05 idle numbers, which
  were measured precisely to inform this and came back adverse for 2 KB.

**Recommendation: A — bookmark-first, keeping the banked plan's order; demote
the page-size sweep to the P2c tuning knob it already is (the stress fixture
makes it a 10-minute experiment).** File the Sigil asks (sketch §6) at ruling
time regardless of D1's outcome — items 1–2 gate Task 2 and have sigil-side
lead time.

---

## D2 — Arbiter execution site (unified-prefetch §7.1's one-arbiter contract vs the two execution contexts)

**The question.** §7.1 wants one cost-denominated slack arbiter for all
deferred work. But the block tier's budget is consumed early in the frame
(`Tile_Cache_Fill`, main-loop context during the VBlank lines, V≈240 — the H4
correction) while page decode runs at the *end* of the frame (the `VSync_Wait`
idle spin). One budget, two temporally disjoint sites.

**Key fact from the code survey (sketch §2):** under the bookmark, page decode
*cannot* cause lag or steal main-loop time — it runs only in the idle spin and
is suspended at the VBlank boundary. Its CPU cost is structurally free; the
only shared, contended resources left are DMA bytes (already governed: per-act
art budget word + Vectorman dual cap + `DMA_Budget_Remaining`) and the staging
buffer (≤1 decode in flight). A CPU-slack arbiter for the page tier has
nothing to arbitrate.

**Option A — one arbiter routine, one call site.** Rejected by geometry: there
is no single point in the frame where both consumers' demand is known and both
can still act.
**Option B — one shared ledger word:** reset in `VInt_Level` beside
`DMA_Budget_Remaining`, charged by the fill early and read by decode admission
late. Temporal order gives demand-fill priority for free. This is the right
shape *if* decode admission needs CPU gating at all — i.e. under pre-chunk-only,
where a blocking chunk really does steal from the next frame.
**Option C — no unified arbiter now.** Each tier keeps its own governor at its
own seam: block tier = count budget + trailing-lag gate (shipped, H4); page
tier = bookmark + DMA budgets + single-flight staging. The §7.2 adoption seam
(~10 lines in `Tile_Cache_Fill`) stays named and documented for the day a third
consumer with real non-preemptible cost arrives. Palette blend (~3.8 K
cyc/frame) is far below arbitration threshold — a fixed idle-slot call.

**Recommendation: C under bookmark-first (the arbiter's problem dissolves;
don't build machinery without a consumer — same reasoning that killed
graph-coloring). B under pre-chunk-only, where admission is load-bearing.**
Either way the §7 contract text survives as the seam definition, not as a
build item.

---

## D3 — Trailing-lag admission policy for decode starts

**The question.** Should starting a new ~45 K-cycle decode be gated after a lag
frame, and with what bound? Research verdict (corpus + real-time-GC MMU
parallel): trailing-lag as a *policy* gate on new speculative starts, never a
per-chunk deadline. The H4 beam-gate autopsy adds the hard constraint: any
deferred-work gate must use a trailing indicator, not beam position.

**Under bookmark-first (recommended frame):**
- **Demand decodes: never gated.** A stalled fill is the highest-priority
  deferred work in the engine; gating it converts one lag frame into a visible
  stall. (Uniform with "demand fill is never gated" in the shipped H4.)
- **Speculative (prefetch) decode starts: adopt the shipped H4 pattern
  verbatim** — a self-contained `Frame_Counter`-delta latch inside `page_in`
  (own latch, not a reuse of `Cache_Pfx_Lag_Flag`, which is fill-owned and only
  as fresh as the last `Tile_Cache_Fill` call), skip-if-last-frame-lagged,
  armed to **≤1 consecutive skip** so sustained lag can't starve prefetch into
  a cold-page cascade. Rationale: decode CPU is free under the bookmark, but a
  completing speculative page still adds DMA-window pressure and occupies the
  single staging slot during exactly the frames that are already tight.
- Explicitly rejected: per-chunk deadlines, beam reads, and gating *resumes*
  (a suspended decode holds the staging slot — finishing it is always better
  than freezing it).

**Under pre-chunk-only:** the gate becomes load-bearing and applies to ALL
starts (a chunk overrun steals the next frame's main-loop budget). Same
trailing latch + the Option-B ledger from D2 as the admission test.

**Recommendation: the H4-pattern gate on speculative starts only, ≤1
consecutive skip, demand never gated.** It is one compare on a path that runs
once per frame, keeps every deferred-work gate in the engine the same shape,
and its bound is already field-proven (unified-prefetch §10, regime (e)).

---

## D4 — §9.7 rewrite naming and structure

**The question.** The drift flag conflates "pre-chunked" and "bookmark"; the
rewrite must present them as the two layers they are (KosM precedent), and the
section title should stop describing a rejected mechanism ("Cooperative
Multitasking").

**Candidates:**
- **A. "§9.7 Idle-Time Deferred Work — Pre-Chunked Pages + Supervisor
  Bookmark"** — names both layers in the title; sub-structure 9.7.1 granularity
  layer (pages), 9.7.2 preemption layer (bookmark), 9.7.3 admission & gating
  (trailing-lag), 9.7.4 rejected: user-mode multitasking.
- **B. "§9.7 The Idle-Time Work Scheduler"** — shorter, but "scheduler"
  oversells (there is no scheduler; there is a FIFO, a gate, and a bookmark)
  and under-names the two-layer structure the ruling asked to surface.
- **C. "§9.7 Background Decode — the Supervisor Bookmark"** — accurate about
  the marquee mechanism but demotes the pre-chunking layer to a footnote,
  recreating the conflation in mirror image.

**Recommendation: A.** The full proposed replacement text (already structured
this way, with corrected cycle figures, the trailing-lag constraint, the
cancel/flush path, and the consumers table) is drafted in
`2026-08-06-arch-97-rewrite-proposal.md` — reviewing that draft is effectively
ruling on D4. Cross-reference sweep (§1.5 stub, §2.1, §9.8, §9.12,
DEFERRED_WORK rows) is enumerated there too; it lands with implementation, per
the standing reconciliation rule.
