# Aeon Engine Roadmap

*Created 2026-08-08. This is the engine-level counterpart to
`empyrean/docs/ROADMAP.md` (the suite roadmap). It answers one question: **what is
the engine working on now, and what comes next, in what order and why.** Statuses
are dated; update them when reality moves — this doc follows the same
keep-in-sync-with-reality rule as `ENGINE_ARCHITECTURE.md`. Fine-grained truth
stays where it lives (`DEFERRED_WORK.md`, the banked plans/specs, the research
docs); this doc only sequences it.*

---

## Now (updated 2026-08-26)

*The previous stamp on this section was 2026-08-09. **1,110 commits landed between
that stamp and this one**, including the whole scanline/effects arc, the streaming
root-cause arc, the background-band ceiling ruling and the insta-shield. Everything
below was re-derived from the tree on 2026-08-26, not carried forward.*

1. **Scanline services / effects (Scanline P1 through P5) — SHIPPED.** The arc that
   dominated the period. Raster DSL with a solved spin schedule, per-layer vertical
   depth, curves, deform, capability-selected record shapes, palette variants, and
   the P5 binding seam that made an Aurora-authored scene reach a ROM
   (`parcel/p5-binding-seam`, 2026-08-22). **This closed the old item 6 blocker
   verbatim**: `HBlank_Install` no longer has zero consumers, `engine/effects/raster.emp`
   tail-calls it, so the §7.2 raster table is built rather than unbuilt.
2. **EFFECTS-W1 (suite project, aeon + aurora + sigil) — ACTIVE, and the only thing
   in flight here.** An effect an author builds in Aurora reaches a ROM. Landed since:
   the one-resolver parallax precedence fix, the boot-select witness, the background
   band placement freed from the frozen section table, and the effects gate lane moved
   wholesale onto the Rust emulator core. **Open in this lane:** the section-crossing
   witness (the boot witness samples deliberately before any crossing, so the crossing
   itself is still unmeasured).
3. **Streaming root-cause arc — F1, F2, F4, F5 CLOSED; F6 PARKED on a ruling.**
   Max-diagonal went from 2.067 to 1.192 frames per tick. F6 (margins, roughly 13,000
   cycles per tick estimated) must not be started before the owner rules on it. The
   whole-call lookahead escalation was measured and **refuted**: five schedules, all
   worse than baseline.

## Next (ranked, 2026-08-26)

*Re-ranked against the tree as it stands. The old ranking was written when Phase 2
streaming had just merged and the raster table did not exist; both premises have moved.*

4. **Game shell and presentation.** No fade of any kind, no title card, no act
   transition, no screen shake, no look-up-down, no camera limits. **Promoted from
   sixth to first in the ranking**, for two reasons: the effects arc just built the
   raster machinery this work was previously waiting on, and it is the largest gap
   between what the engine can do and what a person watching a screen would call a
   game. Blocks the mega-act *presentation* independently of whether streaming works.
   Not yet specced. This is the strongest candidate for the next design week.
5. **BG per-section seam streaming.** Research and design banked 2026-08-08
   (`docs/research/2026-08-08-bg-seam-streaming.md`). Still the largest undesigned
   engine surface and still the hard dependency of the mega-act. Three design rulings
   were queued for the owner; **one of the three ("start before Phase 2 merges") has
   expired**, since Phase 2 merged on 2026-08-09. The other two (slice height,
   horizontal ambition) are live and are being filed as decision cards.
6. **Sound driver completion.** Packages in order 3, 4, 5, 6 (package 2 shipped
   2026-07-07, package 1 shipped 2026-08-09), plus the 2026-08-08 MDSDRV triage riders.
   **Ranked here rather than higher because it is the safe parallel lane**, not because
   it matters less: sound is disjoint from the level-streaming files, so it is the one
   track that can run beside a code lane rather than behind it.
7. **Characters: Tails and Knuckles.** Dispatch v2 with the staged S3K assets and the
   re-anchored plan. No dispatch work merged in this period, so the 2026-08-09 entry
   calling it "next in the level-code lane" did not survive contact; it is genuinely
   still open and now sits behind the shell.

## The destination

8. **Mega-act tech demo** — the standing showcase goal: one seamless multi-zone
   act. Assembles: Phase 2 streaming (shipped), BG seam streaming and its theme
   swaps (5), transition corridors + floating-origin (banked designs), the Harmony
   "marker-relative rebase" idea for parallax residue across corridor seams, and the
   shell polish (4). *Cross-references re-pointed 2026-08-26: they addressed the
   pre-2026-08-26 numbering and named the wrong items after the re-rank.*

## Open but not scheduled

- **Collision**: object-vs-object (`DEFERRED_WORK` §3 — deliberately blocked until
  a gameplay object needs it); build-time collision validation; editor collision
  authoring (**closed 2026-08-08** — the authoring half landed in Aurora and the
  engine needed no changes). Core level + player collision is **done** — sensors,
  Path A/B, per-section maps all shipped and verified.
- **SRAM save** — mechanically ready and the port gate cleared 2026-08-05, but it
  retains a live external dependency: the emulator must persist SRAM before any of it
  can be verified. A later ruling made SRAM the *only* persistence mechanism the engine
  has, which raises the stakes on that dependency rather than lowering them.
- **ComfyUI art pipeline M1** (spec approved 2026-07-12) — awaits its writing-plans
  pass; tooling lane, independent of the engine queue.
- **Fonts** (HUD leaning Emerald; title font undecided) — content decisions,
  user's call.
- ~~The 3 conditional review rows from the 2026-08-05 backlog reconciliation.~~
  **CLOSED** — all three fixed 2026-08-05 by `parcel/defect-batch-8`; the
  2026-07-16 review records every item closed.
- **Full open-work inventory (sound + engine), 2026-08-10:**
  `docs/superpowers/2026-08-10-open-work-inventory.md` — the authoritative
  "what's left" record, including the nine unplanned sound riders that this
  roadmap and the sound queue doc both predate.

## Standing constraints (why the order is what it is)

- One engine-code lane at a time while sigil pins couple a binary to a branch.
- Data/doc/tooling lanes may run parallel to a code lane (this doc is proof).
- Sound (Z80 + `engine/sound/`) is disjoint from level-streaming files — it is
  the safe second code lane once a session's build-gate logistics allow two.
- Emulator-only verification (no real hardware); anything hardware-only needs an
  explicit user ruling (see the TimerA-DMA item).
