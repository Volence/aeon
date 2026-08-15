# Water off-screen state — design draft

**Status:** DRAFT, 2026-08-15, for adversarial sweep. No code.
**Premise audited by a Fable adviser** before drafting — verdicts folded in below.
**Requirements statement:** `games/sonic4/data/effects/ojz_effects.emp`, the note at the
`patchable(ch: 0, ...)` call, which named this fix and booked it as its own parcel.

## 1. The defect

`Raster_PatchAll` converts an anchor to a fire line and **clamps** it to the record's authored
band (`raster.emp:893-902`) rather than suppressing it. So when the true boundary falls outside
the band, the water line renders at a wrong on-screen position and stays there.

Measured on the debug shape, anchor = 224, band 3..120:

| Camera_Y | true boundary | rendered | error |
|---|---|---|---|
| 400 | −176 (above screen) | line 3 | 3 lines dry at top + the fire's mid-line spill |
| 32 | 192 | line 120 | **72 lines tinted that should be dry** |
| 160 | 64 | line 64 | correct — inside the band |

Both directions are visible in ordinary play. The 72-line case was observed by the owner at a
sustained camera position, not a frozen one.

**Severity, stated honestly** (the audit trimmed my first claim): Shadow/Highlight contributes
**nothing** here — all OJZ plane art is high-priority and S/H only dims low-priority pixels
(`ojz_effects.emp:194-205`). The visible effect is a 3-entry hue shift on palette line 2, entries
4-6, where entry 5 alone covers ~54% of lower-screen pixels. So: "the dominant ground colours tint
wet", not "the screen renders underwater".

**Why the clamp exists and must stay:** a sub-band fire line yields a negative inter-record gap,
which stores as `$FF` — the park word — killing every remaining fire in the frame
(`raster.emp:867-870`). The clamp is load-bearing. This parcel does not remove it.

## 2. Why the obvious suppressions do not work

The audit checked each; none composes per-channel:

- **The park word `$8AFF`** kills the whole tail, so parking channel 0 kills channel 1's fire too.
- **`Raster_Program_None` / `Raster_Install(0)`** uninstalls the entire program and fights C2's
  total binding.
- **`pal_dirty_mask`** is frame-top only.
- **A zero `op_count`** *is* already "skip this record" (`raster.emp:627-628`, `subq #1` / `bmi
  .advance` — the priming records use it). But patching a live record's count to 0 leaves its op
  words in the buffer with nothing to consume them, so `.advance` resumes inside them and the
  chain desynchronises. Rejected.
- **Rescheduling the fire past line 223** pushes every later record off with it, because gaps are
  relative.

## 3. The mechanism: choose what the two palette sources HOLD

The fire is `OP_PAL_REGION`, streaming 3 words from `Pal_Variant_Stage` at a comptime offset, over
the same 3 CRAM entries the base palette occupies. Above the fire the screen shows
`Palette_Buffer`; below it, the variant. So the boundary is *the difference between two buffers*,
and if they agree the fire is invisible.

**The offsets already coincide.** `pal_stage_off(0, 2, 4)` = `0*128 + 2*32 + 4*2` = **72**, which
is exactly `Palette_Buffer` + line 2 + entry 4. The two sources are the same 3 words at the same
offset in different buffers.

| state | above the fire | below the fire | fire is | result |
|---|---|---|---|---|
| **normal** (`0 < L < 224`) | base | water | a real boundary | today's behaviour, unchanged |
| **submerged** (`L <= 0`) | **water** | water | inert | whole screen wet |
| **dry** (`L >= 224`) | base | **base** | inert | whole screen dry |

Nothing touches the fire chain, the arm words, the record walk, or the op set. The fire runs in
all three states and costs what it always cost; in two of them it writes the values already on
screen.

**The state is computed once per frame from the UNCLAMPED `L`** — before the band clamp, which is
what today's code cannot see past.

## 4. The parallax side must read the same state

W's overlay clamps `L` through `Raster_GetChannelBand` and then splits. In the **dry** state it
must not split at all — today it splits at the clamped line, which is where the 72 wrongly-shimmering
lines come from. In the **submerged** state it already does the right thing (`L <= 0` clamps to 0,
split at index 0, every band overridden) and must keep doing it.

This is W's one-anchor-two-readers pattern extended from a raw anchor to a **derived state**. The
audit flagged the trap explicitly: if the two sides disagree about the state, the palette and
scroll boundaries separate again — the exact defect W exists to remove. They must read one value.

## 5. Open questions for the sweep

1. **Who owns the state, and when is it computed?** It must be one value read by both consumers in
   the same frame. `Raster_PatchAll` runs in VBlank; the parallax overlay runs in the main loop.
   Those are different points in the frame, so a naively recomputed state can disagree between them
   on a frame where the camera moved. Candidate: compute once in VBlank, store, both read it.
2. **How do the palette sources actually get swapped?** Options: (a) write the 3 words directly,
   (b) bind an identity variant so the derive fills the stage with base, (c) patch the DMA source.
   (b) costs a ~19,332-cycle re-derive (15.1% of a frame) and must not run per-frame. (a) is 3
   words and looks right, but needs an owner and a restore path.
3. **Does making `Palette_Buffer` hold water in the submerged state break anything downstream?**
   It is the authority the frame-top restore ships from, and Parcel R wants it to be the
   pre-effect base by construction. A submerged state that mutates it may foreclose that.
4. **Is `pal_dirty_mask` re-shipping the base every frame going to fight the submerged state?**
   `Raster_VBlank` ORs the program's mask into `Palette_Dirty` every frame, and
   `Enqueue_Dirty_Buffers` re-ships those CRAM lines from `Palette_Buffer`. If the submerged state
   writes water into `Palette_Buffer` this composes; if it writes CRAM directly it will be
   overwritten every frame.
5. **Hysteresis.** `L` crossing 0 or 224 while the camera jitters would flip state every frame,
   re-deriving or rewriting each time. Does this need a dead band?
6. **Is the third state even needed for channel 1?** Channel 1 is a vscroll split, not a palette
   effect. Does the state generalise per-channel, or is it water-specific and therefore mis-placed
   as a raster-level concept?
