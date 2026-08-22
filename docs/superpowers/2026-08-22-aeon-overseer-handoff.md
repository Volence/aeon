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

Arc A state: **assessment LANDED** (merge `f85cbd16`,
`docs/research/2026-08-22-aurora-effects-authoring-assessment.md` — surveyed aeon `77cbf7c0`
/ aurora `4cffe456` clean). Recommendation: **Option B** — Aurora authors neutral JSON in
`games/sonic4/data/editor/effects/` (+ the existing `editor_bg_override.json` `anims`
contract for BgAnim); the booked-unbuilt `tools/effects_gen.py` (scanline-services P5) emits
generated `.emp` through the same constructors so every ensure/budget still fires. Matches
three prior rulings (effects-suite §8, scanline design §7, the 08-20 format-boundary
ruling). Phasing: BgAnim bands FIRST (contract+bake exist; only UI/preview/first-authored-
act missing — also discharges inject_editor_bg's byte-unproven animated arm), then scene
editing + section assignment, then raster preset composition. Preview verdict: BOTH (oracle
loop ≈ free via P2 playtest plumbing; in-Aurora canvas per-line preview effort M). **The §(f) six questions are ADJUDICATED**
(merge `cc518baa`, provenance-flagged assistant-authored under owner delegation — the owner
answered the assessment agent's task view directly with "do what's best for best-in-class
tools + engine", leaning "the section one" on Q2; **OWNER CONFIRMED ALL SIX IN THE MAIN
CONVERSATION 2026-08-22, banked `08f01b73` — that gate is CLOSED, doc work is cleared**):
two waves (BgAnim+scenes+assignment, then raster presets); per-section `sceneRef` in the
`section_N.meta.json` sidecars; generated per-act binding module (descriptor stays
hand-authored; label-vs-const import trap flagged); re-point `project.json` parallax at a
scene id in the schema parcel; schema→empyrean + consumer field list→aeon, Aurora goldens
pin both SHAs; labeled-approximate preview v1 with the oracle loop as truth. **NEXT STEP:
write the schema/contract docs (empyrean + aeon halves) and the wave-1 design doc, then
ping aurora-86 with the SHAs.** **Lane split agreed with aurora-86** (their message,
morning 08-22): THEY dispatch and land all Aurora parcels; aeon ships committed
briefs/contracts with SHAs (empyrean for cross-tool contract material); they transcribe
what Aurora consumes. Their intel, already folded into the survey brief: yesterday's aurora
line `5b58f68..4cffe45` reworked the exact surfaces this view rides (ClassicLevelViewport
overlay scaffolding, classic-overlays, viewStore/ViewMenu, shared rAF play-clock ~0.2-0.7
ms/pass, per-pixel priority occlusion); required reading = aurora docs/OVERSEER.md, ROADMAP
§2.6/§5.1, docs/reviews/2026-08-21-s1-viewport-lenses-audit.md. **[SUPERSEDED — this brief
also carried "the aeon ProjectAdapter is a ROUTING MARKER (real loader deferred, ROADMAP
§2.5)", which was REFUTED the same night; see the overnight addendum below. The rAF
play-clock intel is ALSO scoped narrower than written: it is ClassicLevelViewport-only,
and the OJZ showcase runs MapViewport.]** Flow: assessment → owner design review → design/contract docs
committed → ping aurora-86 with SHAs.

## Overnight delegation standing rule (owner, 2026-08-22 bedtime)

> "if you need any decisions made just whip up a fable agent"

Design calls arising overnight are delegated: dispatch a Fable-model adjudication agent
(`model: "fable"`) with the competing options and the evidence rather than blocking or waking
the owner. **Every such call is PROVENANCE-FLAGGED assistant-authored-under-owner-delegation**,
carries its reasoning, and is listed for morning review — same treatment as the §(f) six. The
delegation covers open calls with defensible answers; it does NOT cover irreversible or
design-changing bets, which still PARK. Also ruled tonight: S4LZ slicing is STOPPED/parked for
usage reasons (nothing was committed; re-dispatch from the brief when a cheaper session runs).

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

---

## OVERNIGHT ADDENDUM — 2026-08-22 night (Aurora arc)

**LANDED + PUSHED, aeon master `00607dd5`.** The Aurora contract/design docs merged as
`db11f59d`, verified byte-identical from a CLEAN CHECKOUT across all four shapes: s4
`060401e4`, s4.debug `0dbaa80f`, demo `c708b114`, demo.debug `dec88cc1` — all matching the
pinned values. (Trap relived: the MAIN tree builds `c7b9d10d` because it carries ~43
uncommitted content files. Always verify identity from a clean checkout, never the live tree.)

Artifacts: `tools/EFFECTS_CONSUMER_CONTRACT.md` (consumer field list — the first of its kind;
the sprite-export contract it was told to mirror turns out never to have landed, only booked),
`docs/superpowers/specs/2026-08-22-aurora-effects-wave1-design.md`, DEFERRED_WORK booking
"AURORA EFFECTS-AUTHORING WAVE 1" (+32 insertions, effects-tail entry untouched).

**The empyrean schema half** (`docs/AURORA_EFFECTS_SCHEMA.md` +
`contract/schema/aurora-effects-scene.schema.json`) is on empyrean branch
`docs/aurora-effects-schema` head `2a0b0c8`, handed to empyrean-73 who lands it in their own
lane. **We owe aurora-86 a three-SHA ping once their empyrean SHA comes back** — that ping is
aurora-86's start signal for cutting Aurora parcels.

### The peer-verification exchange (the night's real value)

aurora-86 ran an independent verification of the assessment's claims about their repo; every
finding below was **re-verified firsthand on this side** before folding. Four found defects that
would otherwise have shipped:

1. **A LIVE DATA-LOSS BUG in Aurora** (ERRATUM 2): the meta sidecar's bare silent catch +
   cleared-overwrite turned a corrupt sidecar into a well-formed empty one. FIXED their side,
   `a88db05`, merged-tree-verified. The atomic-write obligation became SHARED as a result.
2. **Ruling Q4 targeted a DEAD FIELD.** Two `parallaxRef` fields exist; the assessment cited
   `Section` (`s4-types.ts:121`, never written by save), the live one is `Act.parallaxRef`
   (`:227`, populated `load.ts:373`). Implementing from the old citation would silently do nothing.
3. **The "ProjectAdapter is a routing marker / loader deferred" caveat is REFUTED** — a real
   `loadAeonProject` runs at `index.ts:115`, `useProject.loadFromPath` doesn't exist. Closed in
   aurora `4782e86`, an ANCESTOR of our own survey pin. Conclusion survives (model names no
   scenes/budgets) but the cost does not: **model extension, not loader build. Never price this
   arc as "needs the deferred loader first."**
4. **Band drivers pick the SCALAR, never the axis** — all band motion is horizontal
   (`engine/level/bg_anim.emp:5-6`, whole-column rotation). An editor presenting `camera_y` as
   vertical motion is wrong, and it's the natural misreading.

### Still open on the Aurora lane (their work, tracked here)

- **`.collattr.bin` silent overwrite — a SECOND live data-loss defect, still open** (fix on
  their `fix/collattr-unreadable-guard`; SHA owed). Parse-level: `parseCollAttr` never throws on
  truncation, so no `understood()` gate can see it. So the error-handling asymmetry is "safe on
  aeon; FIXED for the sidecar on Aurora; STILL OPEN for collision planes" — do not freeze a
  settled-Aurora claim.
- **MapViewport has no rAF loop** — the preview machinery §(b) credited is
  `ClassicLevelViewport`-only, and the OJZ showcase runs MapViewport. No aeon-viewport perf datum
  exists. aurora-86 owes a foreground CDP measurement; if MapViewport needs its own animation
  loop that is a wave-1 prerequisite on their lane. **Preview posture is PROVISIONAL until then.**
- **Aurora is a NEW WRITER of `editor_bg_override.json`** (0 refs in their `src/`) — wave 1 must
  answer per-key ownership vs `png_to_bg_override.py`.
- RULED (delegated, mine): the agent-handler `BG_TILES_HIGH=32`/`BG_MAX_TILES=512` blocker is
  **NOT in wave-1 scope** — agent parity on bands is a separate parcel. Re-rule if agent-authored
  content becomes how the first act gets made.

### Delegated rulings made this night (all provenance-flagged, cheap to overturn)

`sceneRef` is normatively a **string id, never a numeric index** (the parser's failure mode for a
wrong-typed value is a silent null, not a loud reject); the atomic-write obligation is **shared**;
wave-1 `sceneRef` was **gated on Aurora's meta fix** (now discharged at `a88db05`); the
agent-handler parcel is out of wave-1 scope.
