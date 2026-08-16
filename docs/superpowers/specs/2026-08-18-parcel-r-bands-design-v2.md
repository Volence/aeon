# DESIGN DRAFT v2 — Parcel R: bands

**Date:** 2026-08-18
**Status:** DRAFT, pre-sweep. **v1 of this draft was WRONG** and was stopped by a three-seat lens
sweep; see `2026-08-18-parcel-r-sweep-adjudication.md`. Everything below is written against that
adjudication, and the places it answers a specific finding are marked.
**Owner rulings folded in:** do R before D; cover colour AND scroll rather than serially (owner:
"if the format is going to move, it should move once").

---

## 1. What this is, in one sentence

Today a raster effect starts at a line and runs to the bottom of the screen. **R gives an effect an
end**, so a band of the screen can differ from the parts above *and* below it.

Concretely it unlocks the top-half and middle-band cases that are currently inexpressible: a mist
layer, a fire-lit glow on the upper screen, the shimmer strip at a waterline, a slab of the
background at a different vertical offset.

## 2. The mechanism, and why it is one mechanism three times

Every op class that can be banded already has a **frame-top source**: a RAM buffer whose contents
are committed to hardware once per frame. "Restore" means "write back what the frame top wrote".

| op class | frame-top source | committed by | size |
|---|---|---|---|
| colour (CRAM) | `Palette_Buffer` lines 1-3 | `Enqueue_Dirty_Buffers` -> DMA | 96 B |
| vertical scroll (VSRAM) | `Parallax_Vscroll_Column_Buf` | `Vscroll_Write` (direct, VBlank) | 80 B |
| mode registers | `VDP_Shadow_Table` | `Flush_VDP_Shadow` (unconditional) | ~19 B |

So the parcel is ONE concept — *a band is an effect with an end* — and not three bolted-on ops.

### 2.1 The trap that killed v1, and the fix

**v1 proposed streaming a restore directly from `Palette_Buffer`. That is wrong.** `Palette_Compose`
runs from the MAIN LOOP, after the game-state `jsr` (`engine/system/game_loop.emp:43-49`), i.e.
*during active display*. So the buffer is one compose-generation ahead of the CRAM a restore must
match: rows above the band show generation k, the restore would write k+1, and where compose lands
varies with frame load so the skew flickers. Mid-`Palette_RotateSpan` it is a torn span, not merely a
stale one.

**Every one of the three sources has this property** — `Parallax_Vscroll_Column_Buf` is written by
`Parallax_Update` from the main loop, and `VDP_Shadow_Table` has nine writers, two of them main-loop
(`parallax.emp:298`, `:496-497`).

**The fix: SNAPSHOT at the commit point.** A restore never reads a live buffer; it reads a snapshot
taken in VBlank at the moment that source is handed to hardware. The snapshot is then by construction
exactly what the hardware received, and it is untouched for the whole frame because nothing but the
VBlank pass writes it.

### 2.2 The palette snapshot is PER LINE, and that is not an optimisation

`Enqueue_Dirty_Buffers` tolerates a dropped DMA: each line's dirty bit is cleared **only** when its
enqueue succeeds, so the next VBlank retries (`engine/system/buffers.emp:236-262`). On a drop, CRAM
keeps the PREVIOUS frame's colours for that line.

A whole-buffer snapshot would therefore hold values CRAM never received, and the band would render
**inverted** — effect above, base below — which the sweep found as a live failure mode.

So line N's 32 bytes are snapshotted **exactly where that line's `bclr` runs**, in lockstep with the
enqueue that makes them true. Drop-safe by construction rather than by a test.

VSRAM and registers have no drop path (both are direct writes), so their snapshots are taken
immediately after `Vscroll_Write` and `Flush_VDP_Shadow` respectively.

## 3. The wire format: TWO NEW opcodes, and nothing existing moves

v1 proposed a source-select BIT on `OP_PAL_REGION`'s offset word. **The sweep rejected it on a
criterion v1 never considered**, and the criterion is decisive:

- Touching `.op_region` displaces the CRAM write's landing position, which `EFX_BLANK_DELAY` was
  measured on oracle to fix. That de-calibrates **every shipped `pal_region` effect** and books an
  oracle recalibration.
- `adda.w` sign-extends, so a bit-15 flag lands the source pointer ~32 KB below the base unless
  masked — and there is no free register in the handler to mask with.
- The dispatch-cost argument for the bit was backwards: a compare inserted LAST in the chain costs
  every other op **zero**; only the `OP_SET_REG` fall-through pays.

So: **new opcodes, existing paths byte-identical.**

```
OP_RESTORE_STREAM            colour and vertical scroll
  dc.l <VDP write command>   CRAM or VSRAM write, exactly as OP_CRAM carries
  dc.w count-1               <= RASTER_CRAM_MAX
  dc.w src_off               snapshot selector in the high nibble, byte offset in the low 12 bits

OP_RESTORE_REG               mode registers
  dc.w reg_index             which shadowed register; the handler assembles $8xxx from the snapshot byte
```

`OP_RESTORE_REG` is a separate opcode rather than a mode of `OP_SET_REG` because `OP_SET_REG`'s wire
body is a single `$8xxx` word with no spare bit (`set_reg` admits `$8000-$97FF`), and because its
inner action differs: a stream op writes words to `VDP_DATA` after a command, a register op writes
`$8xxx` to `VDP_CTRL`.

**Open for the sweep:** whether `OP_RESTORE_REG` earns its place in v1 at all. It is the least
motivated of the three (no content asks for it), and it needs runtime word assembly the other two do
not. Dropping it costs nothing structural — the snapshot pass would still take the register bytes.

## 4. Authoring

```emp
pub comptime fn pal_band(top, bottom, addr, slot, pal_line, entry, count) -> array
pub comptime fn vscroll_band(top, bottom, addr, values) -> array
```

Each returns a two-fire list — the effect at `top`, the restore at `bottom` — so it composes with
`compose()` like every other preset and both fires inherit every per-fire ceiling through `fire()`.
The restore's target and count are the effect's, so "restore exactly what was written" is a property
of the constructor rather than an author obligation.

## 5. Scope boundaries, stated so they are not discovered later

- **Static bands only.** A MOVING band (both edges following a world anchor) is out of scope:
  `patchable` hard-refuses a two-fire list (`raster_dsl.emp:331-332`) and GUARD 11 refuses two
  patchable records on one channel, so a moving band has no representation today. Inventing one is
  its own parcel — the sweep was right that this is an unanswered representation question, not a
  detail.
- **Plane A vertical scroll is not bandable.** The rows around the camera window are the streamer's
  working margin; shifting them mid-frame displays half-written tiles (learned on the P2 gate
  fixture). `vscroll_band` should refuse plane A's whole-screen entry at build time rather than
  document the hazard.
- **No geometry, no art.** A band changes how already-drawn pixels are coloured and where planes
  sit.
- **Horizontal scroll is already banded** by the parallax shadow-band system. This adds VERTICAL
  scroll bands; it does not touch HScroll.

## 6. The composition rule — THE decision this draft needs ruled

A restore is not a value that can lose a race; it is a **destructive reset** of the entries it names.
So two bands over the same entries interact in a way two regions do not: band A `[100,140]` and band
B `[120,160]` means A's restore at 140 kills B's effect for 140-160 while B is nominally still on.
Nothing existing can see it — `op_mask`, `check_intervals`, `check_density` and `check_mixed_fire`
all reason about lines and word counts, never about which entries an op owns.

**Recommendation: refuse at build time.** A comptime guard rejects a program in which any CRAM-class
op's entry range overlaps a band's entry range on a line the band spans. Rationale: it makes the bad
state unrepresentable rather than detectable, which is this codebase's standing idiom; and the
alternative resolves collisions by the order lists were passed to `compose()`, which is invisible at
the call site and cannot be walked back once content depends on it.

Cost of refusing: layered bands over shared entries become a build error. No shipped content does
this, and the guard can be relaxed later if content demands it — the reverse is not true.

## 7. Correctness arguments

1. **A restore reproduces what is above the band, exactly.** The snapshot is taken where the source
   is committed to hardware, per line for palette, so it is byte-identical to what CRAM/VSRAM/the
   registers received — including mid-fade, mid-cycle, across a section crossing, and on a dropped
   DMA frame. This is the claim v1 got wrong, and the snapshot is what makes it true rather than
   asserted.
2. **No new mid-frame writer.** The snapshot pass runs in VBlank; the handler only reads. Unlike v1,
   this is now true of the buffer actually being read.
3. **Existing effects are bit-for-bit unaffected.** No existing op path changes, so the
   `EFX_BLANK_DELAY` calibration and the density model's measured constants stand.
4. **Band height is bounded by `check_density`**, which already refuses fires too close together. A
   3-word band's second fire needs ~2 scanlines of separation. Note the density model's per-fire
   constant was fitted to `OP_CRAM`-path measurements; a restore's body is region-shaped and costs
   more, so **the model under-charges it exactly as it already under-charges `OP_PAL_REGION`**. That
   is pre-existing, and this draft does not fix it — but it must be stated, and a re-measurement is
   the honest follow-up.
5. **A dropped restore fire degrades loudly, not inertly.** If a band's ON fire survives and its OFF
   fire is dropped, the effect runs to the frame bottom — rows the author declared clean render
   treated. Static bands cannot be dropped (only patchable records are), which is a second reason
   v1's moving bands are out of scope.

## 8. Gates

**The finding that must shape this section:** every gate in this tree asserts the raster program's
own WORDS. Nothing observes the handler that interprets them, so a build that encodes a restore
correctly and never reads the snapshot passes all of them.

- **Handler-observing gate (new, and the important one).** A breakpoint inside the restore op path,
  reading back the source pointer the handler computed. That directly observes which buffer was
  chosen — the property the word-gates structurally cannot see. This instrument is worth building
  regardless of R's fate.
- **Snapshot-fidelity gate.** After a frame, the snapshot must equal the source it was taken from —
  and on a forced drop (fill the Critical queue) the snapshot for that line must equal the PREVIOUS
  frame's value, not the current one. That is the drop-inversion case, tested directly.
- **Comptime:** hand twins for a two-fire band program; `first_mismatch` over the whole image; and a
  guard that indexes the EMITTED image, not the constructor's arithmetic — the distinction that
  GUARD 10 had to be hardened for once already.
- **Scene-harness gate:** a band scene asserting both records and their op words, with a poison
  control, using the committed `tools/scenes/` + `effects_scene_assert.py` machinery.
- **Vacuity note:** the byte-identity claim in §7.1 is checkable at the RAM level (snapshot vs
  source) but NOT at the pixel level, because oracle's framebuffer is nondeterministic by
  construction. The gate asserts the RAM property and says so; it does not claim to have verified
  pixels.

## 9. Open questions for the sweep

1. Does `OP_RESTORE_REG` earn its place in v1? (§3)
2. Is refusing overlapping bands right, or too strict? (§6)
3. Is the per-line palette snapshot placement correct, and does it cost anything measurable in
   VBlank? (§2.2)
4. Does the density model's under-charge of region-shaped fires (§7.4) bite a band badly enough to
   need re-measuring in this parcel rather than after it?
5. Is there a fourth bandable source this draft has missed?
