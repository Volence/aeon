# Aeon Engine Roadmap

*Created 2026-08-08. This is the engine-level counterpart to
`empyrean/docs/ROADMAP.md` (the suite roadmap). It answers one question: **what is
the engine working on now, and what comes next, in what order and why.** Statuses
are dated; update them when reality moves — this doc follows the same
keep-in-sync-with-reality rule as `ENGINE_ARCHITECTURE.md`. Fine-grained truth
stays where it lives (`DEFERRED_WORK.md`, the banked plans/specs, the research
docs); this doc only sequences it.*

---

## Now (updated 2026-08-09)

1. **Art-streaming Phase 2 — MERGED** (2f047e3 + lens saga through the
   wave/final-panel closings + patch-run batching, all on master 2026-08-09).
   The replay regression net is re-recorded and live; the eviction-liveness
   witness (`tools/evict_witness.py`) closed panel debt V-3. Open from this
   lane: the STRESS_EVICT sustained-scroll famine root-cause session (ledgered
   in the adjudication note — feeds the C4-3 famine-handling design) and the
   FillColumn/Draw_TileColumn hoist (measured 2026-08-09, scoped in
   DEFERRED_WORK, next perf parcel).
2. **Character dispatch v2** — staged S3K Tails/Knuckles assets + the
   re-anchored plan; next in the level-code lane.

## Next (ranked, post-P2-merge)

3. **BG per-section seam streaming** — research + design proposal banked
   2026-08-08 (`docs/research/2026-08-08-bg-seam-streaming.md`; corrects the
   DEFERRED_WORK spec sketch). Vertical-first, Plane_Buffer transport, S3K-style
   off-screen theme swaps riding P2's page-in queue. Three design rulings queued
   for the user (slice height, horizontal ambition, start-before-merge). This is
   the main engine gap the 2026-07-15 alignment audit named, and the hard
   dependency of the mega-act goal.
4. **Sound driver completion** — two tracks, one queue:
   - the banked packages, order **3 → 4 → 5 → 6** (package 2 shipped
     2026-07-07; **package 1 shipped 2026-08-09** with R4 + the TimerA-DMA
     ruling — debug blob headroom is now 3 B, reclaim before any resident
     addition);
   - the 2026-08-08 MDSDRV triage (`docs/research/2026-08-08-sound-study-triage.md`):
     R1 (drain underrun guard) + R5-trace ride package 4's session, R4 rides
     package 1, R2 (observability cluster) rides package 6; **R3 log-domain pitch**
     and **R6 format revision v1** are the two new scoped plans (R6 after
     package 4). Four user rulings queued (TimerA-DMA first among them).
5. **Player-facing polish debts** — the confirmed trio **shipped 2026-08-09**
   (roll anim S3K-exact, camera curl compensation per skdisasm MoveCameraY,
   layer-anchored deform phase — evidence note 2026-08-09-player-polish-trio-ab).
   Remaining: the structural takes (capability flags, post-dispatch condition
   block, shield descriptor record) as the player matures.
6. **Game-shell gaps** (also Harmony-exposed, confirmed): no fade of any kind, no
   title card, no act transition, no screen shake / look-up-down / camera limits;
   `HBlank_Install` has zero consumers (§7.2 raster table unbuilt). These block
   the mega-act *presentation* even once streaming works. Not yet specced —
   candidate for the next design week.

## The destination

7. **Mega-act tech demo** — the standing showcase goal: one seamless multi-zone
   act. Assembles: P2 streaming (3), theme swaps (3), transition corridors +
   floating-origin (banked designs), the Harmony "marker-relative rebase" idea for
   parallax residue across corridor seams, and the shell polish (6).

## Open but not scheduled

- **Collision**: object-vs-object (`DEFERRED_WORK` §3 — deliberately blocked until
  a gameplay object needs it); build-time collision validation; editor collision
  authoring (spec exists). Core level + player collision is **done** — sensors,
  Path A/B, per-section maps all shipped and verified.
- **Parallax fill jump-table unroll** — the one remaining §4.6 perf lever,
  unblocked, banked.
- **ComfyUI art pipeline M1** (spec approved 2026-07-12) — awaits its writing-plans
  pass; tooling lane, independent of the engine queue.
- **Fonts** (HUD leaning Emerald; title font undecided) — content decisions,
  user's call.
- The 3 conditional review rows from the 2026-08-05 backlog reconciliation.

## Standing constraints (why the order is what it is)

- One engine-code lane at a time while sigil pins couple a binary to a branch.
- Data/doc/tooling lanes may run parallel to a code lane (this doc is proof).
- Sound (Z80 + `engine/sound/`) is disjoint from level-streaming files — it is
  the safe second code lane once a session's build-gate logistics allow two.
- Emulator-only verification (no real hardware); anything hardware-only needs an
  explicit user ruling (see the TimerA-DMA item).
