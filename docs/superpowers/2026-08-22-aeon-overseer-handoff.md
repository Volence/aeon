# Aeon overseer handoff — 2026-08-22 (post-P3-completion rotation)

You are the aeon overseer. Boot: `docs/OVERSEER.md`, then `../empyrean/docs/OVERSEER-PROTOCOL.md`.
This file is the STATE the previous incarnation left you, verified and pushed. Read
`docs/DEFERRED_WORK.md`'s top block after this.

## Where things stand

**Scanline P3 is COMPLETE — T1-T16 all landed** (plan:
`docs/superpowers/plans/2026-08-20-scanline-p3-walker-mechanisms.md`, every task carries a
DONE block). T12-T16 landed tonight as five zero-byte parcels (merges `25ef878c`, `c17d73b7`,
`ff0653bd`, `d3a805cf`, `fefb3a65`), each verified from a clean checkout, all four CRCs
unchanged throughout: s4 `060401e4`, s4.debug `0dbaa80f`, demo `c708b114`, demo.debug
`dec88cc1`. Lane bars now: pytest tools **1192/3** (fresh worktree's FIRST sonic4 build
shows 1191/4 — benign artifact-presence skip in `test_effects_gates_segments.py`),
expect-fail **29/29** + sentinel, effects_budget_check **39 rows**, effects_gates
**27 gates / 13 segments, exit 0**. What P3 left open: the `sprite_mask` ENGINE EMISSION
(aeon+sigil pair, mechanism ruling recorded in DEFERRED_WORK: opaque strip at X=0, the VDP
X=0 masking feature CANNOT serve) and the plan's **7 PARKs** (owner).

**The streaming/burst lane is measured to a decision point** (`docs/benchmarks/streaming/`:
`STAGING-LIFETIME.md`, `BURST-SMOOTHING.md`):
- The settling experiment REFUTED the staged-carryover hypothesis: rows are ~free because
  their blocks decode EMPTY on this trajectory; columns burst because theirs are COMPRESSED
  and the F2a latch suppresses the one mechanism (cs col-scan) that pre-stages columns —
  measured covering crossings 4/4 at `right`.
- The smoothing parcel then measured FIVE whole-call lookahead schedules — ALL worse than
  baseline's 3 spikes (5/5/8/5/6): a whole S4LZ call (10-15k) + an ordinary maxdiag tick
  (106.7-116.7k) straddles 128k wherever it lands, and recovery-tick batching out-claims the
  16-slot pool. Engine reverted byte-identically; mechanism substrate (classifier +
  compressed-only filter, proven non-regressing byte-identically at right/down) lives in the
  merged branch history (`66cc7635`, `096d934d`). DO NOT re-try whole-call schedules.
- **PARKED FOR OWNER: the escalation** — resumable `S4LZ_DecompressDict` slicing (~4-6k/tick
  over the 6 quiet ticks; ZX0R §9.7 precedent). Recommendation given: approve. A covered
  crossing provably does not lag (v4 crossing 221, live).

## OWNER RULING 2026-08-22 morning — the arc order is SET

> "I wanna do the aurora parallax/raster view/worker next, are we able to do that? Then 1,
> 2, then 3." — i.e.: **(A) Aurora parallax/raster effects authoring view (Parcel D's
> Aurora half) FIRST → (B) S4LZ slicing parcel → (C) sigil game-defines adoption check →
> (D) booked engine work (sprite_mask emission pair, P1 §8 differential).**

Arc A state: assessment agent dispatched (read-only over aurora at their master `4cffe45`,
deliverable = `docs/research/2026-08-22-aurora-effects-authoring-assessment.md` on branch
`research/aurora-effects-assessment`). **Lane split agreed with aurora-86** (their message,
morning 08-22): THEY dispatch and land all Aurora parcels; aeon ships committed
briefs/contracts with SHAs (empyrean for cross-tool contract material); they transcribe
what Aurora consumes. Their intel, already folded into the survey brief: yesterday's aurora
line `5b58f68..4cffe45` reworked the exact surfaces this view rides (ClassicLevelViewport
overlay scaffolding, classic-overlays, viewStore/ViewMenu, shared rAF play-clock ~0.2-0.7
ms/pass, per-pixel priority occlusion); required reading = aurora docs/OVERSEER.md, ROADMAP
§2.6/§5.1, docs/reviews/2026-08-21-s1-viewport-lenses-audit.md; and the aeon ProjectAdapter
in aurora is a ROUTING MARKER (real loader deferred, ROADMAP §2.5) — a load-bearing gap the
assessment must name. Flow: assessment → owner design review → design/contract docs
committed → ping aurora-86 with SHAs.

## Still owner-pending beyond the ruling

The P3 plan's 7 PARKs; F6 proper; wiki stable-sections; seraph S0.

## Cross-suite state

- **sigil-83**: has the GO for `feat/game-defines` (sent 08-21 ~22:00); NOT yet merged as of
  ~03:30 08-22 (their branch exists, master tip `a32fee7f`). When their ship notice arrives
  we owe the T8 adoption check: re-run T8's three contexts with a capability-derived define
  (recipe: EXTENDED-RECORD.md), exercise the struct-offset harvest explicitly. T15 added a
  second consumer for that parcel: sigil doesn't enforce array-length on comptime `const`
  bindings (booked in DEFERRED_WORK with unlocks).
- **oracle-next-f3**: CR-28 CLOSED both sides — shipped (oracle `a621e4c`), consumed
  firsthand (STAGING-LIFETIME §6, callers reproduce the slot ledger to the cycle), verdict
  banked their side (`a27e4d2`). depthCap unreachable = booked caveat, no ask.
  F-TICK-BOUNDARY-DIVERGENCE still open on the joint ledger (single-tick trace at frames
  7-8; whoever reaches it first pings).
- **aurora-86**: idle, no blocking pressure; sprite-export consumer still booked.

## Rules that bit THIS session (beyond OVERSEER.md)

- **Account session limits killed three agents mid-task** (resets were 7pm/1am ET).
  Recovery that worked: `SendMessage` to the dead agent's id resumes it with context intact —
  but first re-check its worktree state yourself and tell it exactly what's committed vs
  dirty (one agent had uncommitted engine edits at death).
- **A detached verification lane can strand an agent**: T16 detached effects_gates and
  idled forever — the harness only re-invokes on TRACKED background children. Watch the
  done-marker yourself and SendMessage the agent when it lands.
- Landing rhythm that worked for zero-byte parcels: merge → clean worktree at merge SHA →
  four shapes → CRC identity vs the pins above → push. ~4 min each.
- `tools/staging_lifetime_timeline.py` was REWRITTEN (slot-ledger instrument on the new
  oracle profiler); the F2 watchpoint tool it replaced is byte-exact at `e6a0dedd`
  (provenance notes in CHOKE-DIAGNOSIS + STAGING-LIFETIME §1.3).
- The shared `oracle-aether` binary is now post-CR-28 (oracle main `f476785`); corpus
  control passes under it (checked both binaries).

## Next work, in recommended order

1. Owner rulings above (slicing first — it's the felt-lag fix; then Parcel D).
2. If slicing approved: design+implement the resumable S4LZ bookmark
   (engine/compression), acceptance = STAGING-LIFETIME §5's regression harness (this
   instrument at 3 states + tick_variance at maxdiag; COVERAGE identity says directly
   whether pre-staged blocks survive). Byte-mover: full pair landing ritual.
3. sigil adoption check on their ship notice.
4. P1 §8's deferred runtime differential (booked in DEFERRED_WORK, due at the next
   deliberate image-divergence parcel).
