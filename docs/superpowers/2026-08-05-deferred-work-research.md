# §9.7 Deferred-Work Scheduler — Research Corpus (2026-08-05)

Five-track research fan-out (internal docs, Sonic-family disassemblies, six non-Sonic
commercial disassemblies, online sources, modern scheduling patterns) for the §9.7
design phase. Full agent reports live in the session transcript; this note is the
durable distillation. Status: **research COMPLETE, design decision pending user.**

## Verdict — all five tracks converge

**The mechanism is settled: supervisor-mode VBlank-checkpointed stackless task**
(the S3K/Ristar/S.C.E. "bookmark"), exactly what the banked Phase-2 art-streaming
spec (`specs/2026-07-02-art-streaming-phase2-design.md` §3) already chose. The
user-mode cooperative multitasking design still written in ARCH §9.7 was REJECTED
by that spec's header and §3; the rewrite never landed (drift flag, ARCH:3804).

Evidence summary:
- **Commercial precedent is unanimous**: zero of six examined engines (B&R,
  Vectorman, Gunstar, Alien Soldier, TFIV, Ristar) plus S3K/S.C.E./sonic_hack use
  user mode. Exhaustive greps: no SR write clears bit 13 anywhere; B&R even uses
  USP as a 16th *scratch register* in supervisor mode. The only preemption ever
  shipped is the supervisor bookmark — independently invented twice in 1994
  (Ristar `$FFE5BC` flag protocol; S3K `Set_Kos_Bookmark`).
- **Community consensus** (SpritesMind): "no point to be in UM" (Stef/SGDK author);
  user mode is the least-exercised path in emulators and silicon lore. SGDK did
  ship a Sik-derived user-mode task unit (v1.70, 2022) but its production use is
  MegaWiFi network polling, not decompression.
- **Modern-systems verdict**: run-to-completion beat preemption even in Destiny's
  engine; small-RAM systems converge on cooperative + single stack. The stackful
  cost that matters on 64 KB is a permanently reserved unguarded second stack +
  uninspectable reentrancy invariants — not the ~0.3%/frame switch cycles.
  Real-time GC's MMU metric formalizes "never steal a frame" and uses
  *trailing-window* accounting — independent validation of the trailing-lag-gate
  constraint (ARCH:2340, campaign-gap-ledger).

## The mechanism's three load-bearing invariants (from S3K/S.C.E. tracing)

1. **Stack-neutral preemptible region** — the decoder never pushes; abort = `rts`,
   and resume works from any stack depth. S3K rewrote Kosinski to keep its
   description field in RAM/registers for exactly this reason.
2. **One contiguous PC range** checkable from the interrupt (`[Start, Done)`
   against the stacked rte address). Our spec improves on S3K's magic `$42(sp)`
   with exported PC-range symbols.
3. **Bookmark is the V-int's final act**, after all frame-critical work; the lag
   path never bookmarks (decode can only be live between main-loop start and the
   vsync spin — structurally impossible on a lag frame in the S3K shape; verify
   the equivalent holds in Aeon's VInt_Lag).

**Negative example in our own tree**: legacy `sonic_hack/code/engines/kosplus.asm`
ported the bookmark and broke all three — processor called from *inside* V-int,
`Set_KosPlus_Bookmark` has zero call sites, decode body behind a `jsr` outside the
guarded range. Use as the review checklist for whatever we build.

## Refinements the references contribute (beyond the banked spec)

- **S.C.E. deltas worth stealing**: register-resident decoder state → 26-byte
  bookmark (vs S3K's 46), `rtr` resume (CCR only — legal because `move sr,<ea>` is
  unprivileged on 68000), DEBUG-build queue-overflow traps, int-guarded DMA enqueue.
- **Vectorman dual cap, instruction-verified**: 54 entries AND 2,880-**word**
  (5,760 B) running byte budget, with **atomic rollback** — an over-cap batch
  reverts wholesale and the producer retries next frame. (Confirms the
  unified-prefetch note's correction of the local ANALYSIS.md gloss.)
- **B&R budgeted continuation**: per-frame budget word (`$FF9916`) refilled from a
  per-state value, charge/refund allocator, **chunk size derived from remaining
  budget** (jobs `divu` the residual) — the per-act art budget word in spec §6 is
  this pattern; the charge/refund + budget-derived-chunk-size ideas are available
  if the arbiter needs them.
- **TFIV discipline**: producers retry-on-full (defer, never drop, never tear);
  V-int always publishes a *complete* frame from shadow state.
- **Lag-frame precedent is uniform**: a flag/index selects a short V-int path;
  audio never skipped, no partial commits — matches our VInt_Lag shape.
- **Ristar's spawn trick**: a background decode is started by *manufacturing* a
  bookmark (fake saved SR/PC pointing at the decoder entry) — spawn, resume, and
  preempt-resume are then one code path. Its consumer is an object state machine
  polling the flag; a cancel path just clears the flag.
- **Modern**: publication = one aligned word write at unit completion (atomic wrt
  interrupts on 68000 — no critical sections needed if producer state stays
  private until then). Foreground needs an explicit **cancel/invalidation path**
  for stale prefetch (Unity incremental-GC fallback lesson); spec §6 has
  demand-priority but no explicit flush — add one.

## Corrections to existing docs (apply during the §9.7 rewrite)

- ARCH §9.7's "~80-120 cycles total overhead" is unsupported — plutiedev publishes
  no numbers; real 68000 timings give ~300-400 cycles/frame for a full two-way
  switch (still negligible; the figure just shouldn't survive the rewrite).
- DEFERRED_WORK.md:746 still points readers at the rejected §9.7 as "the designed
  vehicle" for resumable decode.
- Stale measurements riding along: spec §5's lower-RAM slack (9,150 B → now
  6,078 B post-H5), spec §4 idle figures (2026-06-22 vintage; diagonal lag
  re-measured ~42% in prefetch A/B regime (e)), ARCH §1.5 stub still says
  "no bookmark systems" citing the dead design.
- The 2026-07-02 plan predates the Sigil port and engine/game split — every file
  path is `.asm`; re-anchor before executing.

## Open decision points (need user ruling at design time)

1. **Sequencing: pre-chunk-first vs bookmark-first.** The unified-prefetch note §7
   point 3 says run the page-size sweep FIRST and land the bookmark only if small
   pages miss the latency target; the banked plan builds the resumable decoder
   immediately (Task 2). Corpus lens: KosM itself is *both* — format-level 4 KB
   pre-chunking AND the bookmark under it. The bookmark's unique value is consuming
   ALL idle (no chunk-size tuning, zero overshoot); pre-chunking alone is simpler
   and may suffice at 2 KB pages ≈ <1 frame of idle.
2. **Arbiter execution site.** §7 point 1 wants one cost-denominated slack arbiter
   for all deferred work, but the block tier's budget is consumed inside VBlank
   (`Tile_Cache_Fill`) while page decode runs in the main-loop idle spin — one
   budget, two execution contexts, unresolved.
3. **Whether decode admission needs the trailing-lag skip** (start a new ~45K-cycle
   decode this frame after a lag?) and with what bound — unspecified; research
   suggests trailing-lag as *policy* gate (suppress new speculative starts during
   sustained lag), never as a per-chunk deadline.
4. **§9.7 rewrite naming** — the drift flag conflates "pre-chunked" and "bookmark";
   the rewrite must present them as the two layers they are (KosM precedent).
5. Re-measure the `VSync_Wait` idle distribution under the current main loop
   before sizing anything (open question 3 of the reconciliation dossier).

## Idle re-measurement (2026-08-05, answers open decision point 5)

Measured on current master (plain build, sound on, crc `c2d17ee3` — loaded-ROM
hash verified against the build), oracle profiler, OJZ scroll-test state, NTSC
128,000-cycle frames. Idle = cycles attributed to `VSync_Wait` (the `.wait`
spin), averaged over the stated window:

| Scenario | Idle cycles/frame | Idle % | Notes |
|---|---|---|---|
| At rest | 95,148 | 74.3% | 120-frame window |
| Sustained max-H (6 px/frame ground speed) | 86,717 | 67.8% | 120-frame window; `Tile_Cache_Fill` only 6.1% — prefetch campaign tamed pure-H streaming |
| Diagonal fall (6 px/frame H + up to 16 px/frame V) | 42,496 | 33.2% | 100-frame window incl. some pre-fall run-up; `Tile_Cache_Fill` 36.1% inclusive in these frames |

vs the 2026-06-22 vintage figures (62% max scroll / ~24% worst diagonal): both
improved, consistent with the prefetch campaign.

**Design consequence for decision point 1 (page size / bookmark):** a 64-tile
2 KB ZX0 page ≈ 45K cycles does NOT fit the measured worst-window *average*
frame (42.5K idle), and per-frame minima inside that window are necessarily
lower. So at 2 KB pages, pure pre-chunking either overruns into lag on
diagonal-heavy frames or must defer (latency) exactly when streaming demand is
highest. Live options: (a) 32-tile/1 KB pages (~22.5K cycles — fits the worst
window with ~2x margin; the spec's planned page-size sweep covers this), or
(b) the bookmark, whose value concentrates precisely in these frames.
Caveats: averages hide minima (instrument per-frame during implementation, per
the spec's DEBUG self-test); the OJZ test scene is object-light — real levels
with badniks will shave idle further; measurement is emulator (oracle), not
hardware, per project policy.

## Consumers and their actual needs (from the reconciliation dossier)

| Consumer | Need |
|---|---|
| ZX0 mid-game page decode (Phase-2) | multi-frame slicing; 64-tile/2 KB page ≈ 45K cyc ≈ <1 frame idle at max scroll, ~2.4 frames worst diagonal; latency hidden by ~10-column cache lookahead |
| S4LZ streaming (§2.1) | only for larger-than-block payloads, if any remain — block tier already solved by prefetch |
| Page prefetch queue | demand-before-prefetch FIFO, ≤1 decode in flight, per-act budget word, dual-cap DMA admission, camera soft-clamp |
| Ring/object pre-scan | effectively satisfied by shipped §4.9 entity window — non-requirement |
| Palette blend (~3,840 cyc/frame during transitions) | tiny periodic idle-time call slot — needs no preemption machinery |
