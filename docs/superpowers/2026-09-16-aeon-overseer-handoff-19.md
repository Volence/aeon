# Aeon overseer handoff 19 (2026-09-16)

**The resume anchor for the next aeon session.** Read `docs/lane-status.json` first; this file says why.

## Landed today (all on master, all re-verified on the merged tree)
- **BG-PLANE-WINDOW**: the prime blits the window the scroll selects.
- **REGIONS-P2-STEP6**: the crossing wipe.
- **REGIONS-EMIT-BINDINGS**: act 1 reads its regions from the editor file, zero bytes.

## In progress: region background switching (part of regions, owner ruling)
- **Design:** `docs/superpowers/specs/2026-09-16-megaact-bg-streaming-design.md` v2. **Its correction banner overrides
  its body** — the body has not been rewritten after the Fable review.
- **Research:** `docs/research/megaact-bg-streaming/00`-`07` (07 is the Fable review).
- **Goal:** Sonic 4 regions that feel like different places; stress test = all of Sonic 2/3 as one act, zones as regions.

## Next, in this order (from the review)
1. **Put R5 back to the owner.** He ruled "warn, let it exist" believing an over-budget spot stutters. **It soft-locks
   in release.** He must decide again with the true consequence, and may want a release escape (a stall watchdog).
2. **M-B** — measure the 80×60 cache window's page set along a stitched real-zone seam and a three-zone junction.
   Tool-only. **Decides whether the stress test can exist.**
3. **M-E** — confirm the release soft-lock under the existing stress fixture.
4. **Choose the blank transport**, then **M-A** as the full blank + overwrite + repaint sequence under a worst-case fall.
5. **Rewrite the design body** against the review; do not implement from the uncorrected sections.

## Held (not blocked, deliberately)
- **REGIONS-P2-STEP7/8** (video-memory levers): wait for the foreground design, to avoid carving VRAM twice.
- **LS-13b** (boot bus hold): unblocked by sigil today; waiting for the owner's go.

## Still the owner's
- The spring sound A/B from 09-09.

## Standing lessons from today, in `docs/OVERSEER-REFERENCE.md` and memory
- A count is keyed to spelling, field, record shape, equivalence AND comparison set; name them.
- A caveat is not a measurement. "Found none" is not "there are none".
- Never upgrade a label: INFERRED in a note stays INFERRED in a design.
- Install the ROM built from the landed commit before asking anyone to fly it.
