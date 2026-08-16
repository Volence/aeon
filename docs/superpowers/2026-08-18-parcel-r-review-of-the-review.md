# PARCEL R — audit of the adjudication. What survived, what did not, and two live bugs.

**Date:** 2026-08-18
**Why this exists:** the owner observed that two drafts had been killed for wrong assumptions and
asked whether the SURVIVING claims were any better. Three reviewers (Fable reasoning audit, Opus
attacking the palette claim, Sonnet attacking the proposed fixes). The answer is mixed, and the most
valuable output is not about R at all.

---

## 1. TWO LIVE BUGS IN SHIPPED CODE — fix these regardless of R's fate

### BUG A — `Effects_Offscreen_Entry` is published before the DMA entry it names is built

`Raster_InstallPatched` stores the pointer at `raster.emp:862` and only builds `Static_Pal_Ship` at
`:887`, with no `ints_off` bracket between. `Enqueue_Dirty_Buffers` tests only that pointer, bit 2 of
`Palette_Dirty` and the latched `Effects_Screen_L` (`buffers.emp:279-315`).

**A VBlank landing in that window queues a well-formed DMA carrying the PREVIOUS patched program's
source offset, colour count and CRAM address** — wrong colours into CRAM for that frame. This window
is not theoretical: `Effects_InstallPreset`'s own comment says of the same region *"this proc runs
from the MAIN LOOP … so a VBlank lands inside this window routinely"* (`preset.emp:209-211`), and the
ship's gate is typically OPEN there because `Effects_LatchWorldLines` has already re-latched the
incoming section's screen line while `Palette_Compose` has not yet run.

Same window, second symptom: `Raster_Patch_Tab` goes live at `:834` while `Raster_Active_Buf` and
`Raster_Program` still belong to the outgoing program, so a VBlank there brings the incoming schedule
live one frame early against the outgoing palette base.

**Fix:** build the entry before publishing the pointer, or bracket the pair.

### BUG B — `Raster_Dense_Lines` is never reset per frame

It is written only by the two dense ENTER ops (`raster.emp:705`, `:717`) and cleared only in
`Raster_InstallPatched` (`:870`). **Nothing clears it per frame.** A dense run authored to overrun
line 223 leaves the counter non-zero, so the NEXT frame's first HInt takes `.dense_body`
(`:631-632`) and streams from the stale `Raster_Dense_Cursor` across the top of the display,
ignoring the rewound `Raster_Cursor` until the count expires — and on a crossing into a static
program it never stops.

**Fix:** frame-scope the counter in `Raster_VBlank`.

### Confirms a known bug

`Raster_VBlank`'s explicit-clear arm is **unreachable dead code**: `beq.s .no_install` at `:493`
guarantees `d0 != 0`, so `bne.s .copy_program` at `:496` is always taken. `HBlank_Uninstall` has no
live caller and IE1 is never dropped once armed. This is EFX-7 in `docs/BUGS.md`, independently
re-derived — and `ram.emp:362-368` reasons about that path as if it were merely latent. It is dead.

---

## 2. The palette mechanism: TRUE-WITH-CAVEATS, and now genuinely verified

The seat attacking it strengthened the trace with four checks the original did not run:

- **The lag path holds**, for a reason nobody had written down: `VInt_Lag` runs the same four steps in
  the same order (`vblank.emp:291-337`), and a lag VBlank can land **mid-`Palette_Compose`**, shipping
  a half-composed buffer — but the snapshot spliced at the `bclr` reads the same frozen buffer the
  DMA reads later in that IRQ, so **snapshot == CRAM even on a torn frame**.
- **The Critical drain is genuinely unbudgeted** — `Process_DMA_Critical` has no budget test and no
  drop path; the budget flows the other way, subtracting Critical's bytes so Important/Deferrable see
  the remainder. No palette transfer can be deferred past the VBlank.
- **Palette enqueues cannot be byte-capped** — `queue_static_dma`'s only rejection is a slot check; it
  never touches the frame byte cap, so that second, independent drop mechanism cannot reach a line.
- **The CRAM-writer census is exhaustive** and there are no independent fade/flash writers —
  `Palette_DoOperator` works through `Palette_Buffer`, so the dirty mask covers it.

**But the headline sentence was still overclaimed**, for a reason I should have caught: the invariant
is stated as "byte-identical to what CRAM received AT FRAME TOP", and `VInt_DrawLevel` sits between
the enqueue and the drain, so on a heavy frame the drain lands after line 0. The mechanism is fine;
the CLAIM is wrong. Correct form: **"the snapshot equals this frame's base-DMA payload"** — which is
exactly what the `bclr` splice pins, and it makes the drop-safety argument exact rather than
incidental.

---

## 3. Three of my seven fixes were wrong or unspecified

- **The ship guard is unwritable as ruled.** "Refuse a band on a channel that declares
  `offscreen_ship`" — a static band never carries a channel (`fire_channel` returns -1 for a
  non-patchable fire), so the condition is unreachable. It would have shipped as a guard that can
  never fire. Worse, it is keyed on the wrong quantity: the ship's destination is a raw CRAM address
  and count, so a band on a DIFFERENT channel covering those entries breaks identically. **Both
  reviewers and the audit converged on this independently.**
- **The VSRAM fix repairs the wrong layer.** Mirroring `Vscroll_Write`'s mode branch makes the
  restore's VALUE right, but the OP ITSELF changes meaning across modes: `vsram(2, …)` is "all of
  plane B" in whole-plane and "column 0's plane B only" in per-column. The author's band is already
  wrong before any restore happens.
- **"Book the oracle recalibration" covers only the path with a knob.** `EFX_BLANK_DELAY` is a
  CRAM-path spin; `OP_SET_REG` burns no delay, so recalibration has no mechanism to move a
  set_reg-only write — and the already-measured, deliberately-unfixed ~45% mode-register seam gets
  wider from the same dispatch tax.
- **The pairing predicate is unspecified.** "A restore must have a matching effect op with the same
  target and count" is an EXISTENCE check, but two legitimate bands can share target and count (a
  mist band and a water band tinting the same accent entries at different depths — exactly this
  parcel's motivating content). Existence-checking both misses real authoring bugs and over-exempts
  real conflicts.

Only the "banded line is dirty every frame" invariant came back sound, and it falls out for free
provided the new op's `op_mask` arm follows the established derivation (a missing arm is a build
error, since the match is exhaustive).

---

## 4. The structural finding, which outlives this parcel

**The engine has no single frame-top commit seam.** Frame-top state is the emergent tail of an
ordered pipeline — flush, raster install, palette enqueue, ship register replay (deliberately
POST-flush), ship DMA (deliberately POST-base-lines), queue drain — with mode-dependent emitters and
an intentional post-commit writer. "Snapshot at the commit point" was never one mechanism three
times; it is N mechanisms, each re-deriving that pipeline's tail, and **any future frame-top writer
silently invalidates every snapshot** unless something structural forces it to declare itself.

The mitigation, if bands ever ship: a comptime registry of frame-top committers, so adding one
without declaring its band interaction is a build error — the contract-closure idiom this codebase
already uses elsewhere.

## 5. The process leak

**Adjudications mint fixes, and those fixes enter the next draft unswept.** Sweep 1 minted "snapshot
at the commit point"; v2 adopted it as its central mechanism; sweep 2 killed two thirds of it. Sweep
2 minted four more fixes; this audit holed three. Under the current process a sweep 3 should be
EXPECTED to kill something in the fix list.

Two corrections to how these run, both cheap:
1. **Positive claims need more redundancy than kills, not less.** v1's kill had two independent
   seats; the surviving "verified sound" claim had one. That is backwards — a kill needs one witness,
   soundness has to survive all of them.
2. **Treat adjudication-minted fixes as claims to be swept, not rulings to build on**, and require
   the draft to carry per-source derivations with file:line evidence rather than a table.

---

## 6. Recommendation

**Fix the two live bugs first, as their own small parcel.** They are independent of R, they are in
shipped code, and BUG A corrupts CRAM on a section crossing — which is ordinary play.

**Then, if R proceeds, narrow it until the guards become trivial:**

- **ONE band per program** — at most one restore op in the whole composed program. This collapses the
  pairing predicate (one band, one restore, no ambiguity), the cross-band overlap guard (nothing to
  overlap with), and the merged-fire ordering problem, all at once.
- **Program-keyed ship refusal**, not channel-keyed: refuse a band in any program carrying a ship
  trailer entry. Strictly safer than the entry-overlap guard and far simpler to prove.
- **Palette only.** Scroll is its own parcel with its own derivation and its own sweep, and the op's
  cross-mode meaning must be settled before any of it.
- The invariant restated as "the frame's base-DMA payload".

That is enough for a fog layer, a top-half glow, or a tinted slab — the content that motivated R —
and every guard in it is a condition with nothing to get wrong. The owner's "if the format moves, it
moves once" premise was priced on byte-identity, which is now falsified, so it deserves
re-ratification rather than silent carriage.
