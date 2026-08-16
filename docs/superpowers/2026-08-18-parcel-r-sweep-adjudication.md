# PARCEL R — lens sweep adjudication. **STOP. My recommendation was wrong.**

**Date:** 2026-08-18
**Supersedes** `2026-08-18-parcel-r-recommendation.md` (which said the decision had collapsed and (A)
was now a small parcel) and stops the draft `specs/2026-08-18-parcel-r-mid-screen-restore-design.md`.

Three seats: hardware/timing (Fable), correctness/state (Opus), gate vacuity (Sonnet).

---

## The correction, stated first

I recommended (A) on the grounds that `Palette_Buffer` is already a maintained pre-effect staging
buffer, so R needed **no new RAM, no new owner, and no new mid-frame writer**. Two seats independently
falsified the third claim, and it takes the other two with it.

**`Palette_Buffer` is one compose-generation AHEAD of the CRAM it is supposed to match.**

- `Enqueue_Dirty_Buffers` samples `Palette_Buffer` in VBlank and `Process_DMA_Critical` drains it in
  the same VBlank, so CRAM during frame N's active display is `Palette_Buffer` **as it stood at
  VBlank N**.
- `Palette_Compose` runs from the **main loop**, after the game-state `jsr`, at the tail of the loop
  body (`engine/system/game_loop.emp:43-49`) — that is, **during frame N's active display** — and it
  writes `Palette_Buffer` **in place**.
- A restore fire at line N therefore streams generation k+1 while every row above the band still
  shows generation k. Where compose lands relative to the fire varies with frame logic load, so the
  skew **flickers frame to frame**, and an HInt landing inside `Palette_RotateSpan`'s in-place shift
  streams a **torn** span — garbage, not merely stale.

**What I got wrong, precisely:** I checked who writes `Palette_Buffer` and when, saw "once per frame
from the main loop", and concluded "stable during active display". Once per frame from the main loop
**is** during active display. The handler reads it at a scanline that may be before or after that
frame's compose.

**Why the precedent I leaned on does not transfer.** `OP_PAL_REGION` reads `Pal_Variant_Stage`, which
is written from the main loop too and carries the identical one-generation skew — but nothing claims
a variant matches CRAM, so the skew is invisible. **A restore's entire specification is byte-identity
with the frame-top ship.** R does not inherit a benign relationship; it inherits a benign
relationship and then asserts the one property that relationship never had.

This bites exactly the cases §5.1 named as safe: cross-fade (every step of a 16-frame window), cycling
(every `pc_period` tick), a section crossing (new palette below the band, old above), and both flash
operators.

---

## The other blockers, which the snapshot does NOT fix

**A restore does not compose, and the reason is the one the draft itself cites for deleting `init[]`.**
Two regions compose because each writes its own value; a restore writes the *absence* of a value,
which cannot lose a race — it is a destructive reset of those entries.

- Band A `[100,140]` and band B `[120,160]` over the same entries: at 140 A's restore kills B's tint
  for 140-160 while B is nominally on. No guard can see it — `op_mask`, `check_intervals`,
  `check_density`, `check_mixed_fire` all reason about lines and word counts, never about which
  entries an op owns.
- A restore colliding with another effect on the same line: `compose` merges them into one fire and
  emits CRAM-class ops in **`progs` argument order**, so which one wins is decided by the order the
  author passed lists to `compose()`.
- Worse on the register side: a band restoring reg `$0C` from the shadow silently cancels an
  unrelated `sh_on()` from an earlier effect, from the restore line down.

R reintroduces **mid-frame** exactly the per-program restore semantics the blanket frame-top flush
was created to delete. That is a direction-level change, not a detail.

**A patchable band is unrepresentable today**, so §5.4's question was mis-framed. `patchable`
hard-refuses a two-fire list (`raster_dsl.emp:331-332`), and marking the two fires separately on one
channel is refused by GUARD 11. Two channels builds, but then one visual boundary has two anchors and
`Raster_GetChannelBand` has two answers. The open question is not "should `patchable` refuse one fire
of a band" — it already refuses both spellings — it is **"what is the representation of a moving band
at all"**, and that is unanswered.

**The band budget halves.** Bands double the record count, and `RASTER_MAX_PATCH`'s own constraint is
`sum(hi_i - lo_i + 1) + (N-1) <= 221`. OJZ ships channel 0 banded `3..220` with channel 1 pinned at
222, so expressing the water as a band leaves lines 221-223 for its restore, one of which is taken —
**the flagship use case is essentially unbuildable at today's banding.**

**Blast radius I missed entirely:** mark a restore fire `offscreen_ship: 1` and `Raster_BuildShipEntry`
builds a frame-top DMA from `Pal_Variant_Stage + <bit-15 offset>` — arbitrary memory blasted into CRAM
every frame the anchor is off-screen. `patchable`'s ship guard only counts `pal_region` ops; it cannot
tell a base-sourced restore from a staging-sourced region.

---

## Where the draft's two self-flagged choices actually land

**The source bit was the wrong call, and my cost argument was backwards.** A fifth opcode inserted
last in the compare chain costs OP_CRAM / OP_PAL_REGION / the two dense ops **zero** extra cycles —
only the `OP_SET_REG` fall-through pays. Meanwhile the "one `btst`" is really a 3-4 instruction
restructure of the shipped region path with no free register (`d0` = op count, `d1` = count-1, `a1` =
cursor, `a2` = base; a wider `movem` costs ~40 of the budget), and `adda.w` **sign-extends**, so bit 15
set lands the source pointer ~32 KB below the base unless masked.

The decisive criterion is one neither the draft nor I considered: **which design leaves the
oracle-calibrated `EFX_BLANK_DELAY` path byte-identical.** Touching `.op_region` de-calibrates the
CRAM write landing for **every existing `pal_region` user**, and the delay's own comment says to
recalibrate on oracle when the prologue changes. A fifth opcode leaves that path untouched and gives
the restore its own independently tunable body. **The opcode wins on the criterion that matters.**

**The register case is not cheap and not symmetric.** `OP_SET_REG`'s wire body is one `$8xxx` word
with no spare bit, so a shadow-sourced variant needs a new opcode, a new length, or an in-band range
test — i.e. it forces the very opcode-format reopening §4.1 argued against. And `VDP_Shadow_Table`
has **nine writers, two of them main-loop** (`parallax.emp:298`, `:496-497`), so "one owner, read-only
during active display" is a property the draft would have to create, not one it can assume.

---

## What R actually costs now

1. A **VBlank-latched 128-byte snapshot** taken where the DMA samples the buffer — which is precisely
   "a staging buffer holding the pre-effect values, maintained by somebody", the finding that stopped
   R in the first place, resurrected. New RAM, new owner, but at least the owner is obvious and the
   snapshot is byte-identical to CRAM by construction. (The alternative, moving `Palette_Compose`
   into VBlank ahead of `Enqueue_Dirty_Buffers`, reverses a standing ruling and puts the whole
   compose inside the DMA window.)
2. A **composition ruling**: what happens when two effects own the same entries and one of them ends.
   This is the deep one and it is unanswered.
3. A **fifth opcode**, not a source bit — plus an oracle recalibration if the shared path is touched
   at all.
4. A **representation for a moving band**, since `patchable` refuses every current spelling.
5. Either drop the register case or re-cost it as the new-opcode change it is.
6. A **runtime instrument that observes the handler**, because every gate proposed so far asserts the
   program's own words — a build that encodes the source correctly and never reads it passes all of
   them.

That is not the small parcel I described. It is a design parcel with an unanswered ownership question
at its centre, which is where R started.

---

## Recommendation

**Do not proceed to a plan.** The direction — a restore streaming from an in-phase base — can still be
right, but the parcel must first name a buffer genuinely in phase with CRAM, and must answer
composition before any wire-format decision is spent.

Given that D's most interesting content (moving boundaries, world-anchored gradients) is already
unlocked by P and W and needs nothing from R, **the honest sequencing is D first**. R is not blocking
anything; it was queued ahead of D because it looked small, and it is not.

**One gate finding worth keeping regardless of what happens to R:** every gate in the tree that
asserts a raster program asserts the PROGRAM'S WORDS. Nothing observes the handler that interprets
them. A breakpoint inside the op path reading the source pointer the handler actually computed would
close that, and it is worth building the next time any op changes.
