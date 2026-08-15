# Water off-screen state — REJECTED DRAFT + the sweep that replaced it

**Status: THE MECHANISM BELOW WAS REJECTED.** Kept because the reasoning is load-bearing for
whoever builds this next, and because knowing *why* a design was believed is worth more here than
a clean page. Read §0 first; the draft body follows unedited beneath it.

## 0. Outcome of the three-lens sweep, 2026-08-15

**Verdict: DO SOMETHING ELSE.** Three lenses (two Opus, one Fable) plus a Fable premise audit.

**The draft did not fix its own headline measurement.** Its worst case was Camera_Y 32, boundary
rendered 72 lines too high. But `L = 224 - 32 = 192`, which is `< 224`, so by the draft's own rule
that is the NORMAL state — "unchanged". The 72-line error is a **band** defect, not an off-screen
one. The draft would have shipped without touching the thing that motivated it, and would have
added a discontinuity: at Camera_Y 0 the dry state renders correctly, at Camera_Y 1 the normal
state clamps to 120 and 103 lines snap wet — a full-lower-screen pop on one pixel of movement.

**What actually fixed it: RE-BANDING** (aeon `8fcf4d2b`). ch0 3..214 / ch1 216..223. Worst dry-side
error 72 -> 10 lines, zero new mechanism. The band was narrow only because a gate fixture sat
mid-screen.

**Three further defects in the draft's mechanism:**
1. **"The fire becomes inert" is false.** Channel 0's record carries TWO ops; the `OP_SET_REG
   $8C89` S/H write fires in every state regardless of what the palette buffers hold. Invisible
   only while all OJZ art is high-priority — a content gap the fixture plans to close.
2. **Writing water into `Palette_Buffer` is a compounding feedback loop.** `Palette_DeriveVariant`
   READS that buffer (`palette.emp:688`), so the next stale frame derives `f(water)` and
   `Variant_Water_Deep` halves R/G again — base R=6 -> 3 -> 1 -> 0 within three stale frames. And
   nothing restores those words on exit; `Palette_Buffer` lines 1-3 are only rewritten from
   `Pal_Base` on `Pal_Base_Dirty`. Also: the "offsets coincide" elegance does NOT extend to
   `Pal_Base` — `Palette_Buffer + $20` maps to `Pal_Base + 0`, so the base twin of offset 72 is
   `Pal_Base + 40`.
3. **The abstraction is misplaced.** "Submerged" is meaningless for channel 1's vscroll split, so
   water vocabulary would be installed at the raster level, constraining every future patched
   effect. The *geometry* (unclamped L above/within/below screen, per channel) is generic and
   belongs beside `Raster_GetChannelBand`; the *response* is per-effect and belongs in the
   vocabulary/preset.

## 1. WHAT TO BUILD INSTEAD — steal S3K's, which costs nothing

`Handle_Onscreen_Water_Height` (`skdisasm/sonic3k.asm:8473-8519`) computes
`Water_level - Camera_Y` and, when `<= 0`, sets `Water_full_screen_flag` and
`H_int_counter = -1`. The flag's ONLY job is to pick a DMA source at frame top — four identical
readers (`sonic3k.asm:595-603`, `:726`, `:800`, `:928`):

```
tst.b   (Water_full_screen_flag).w
bne.s   VInt_0_FullyUnderwater
dma68kToVDP Normal_palette,$0000,$80,CRAM
VInt_0_FullyUnderwater:
dma68kToVDP Water_palette,$0000,$80,CRAM
```

**Same DMA either way. Cost is one `tst.b`/`bne.s` (~16 cycles) per frame** plus a duplicated DMA
macro in ROM. No transition machinery, no hysteresis, no re-derive, no buffer mutation — which
sidesteps defect 2 entirely.

**Aeon's form:** a second pre-built `DMAEntry` (`Static_Pal_Line2_Water`) sourcing
`Pal_Variant_Stage + $40`, and `Enqueue_Dirty_Buffers` picking between it and `Static_Pal_Line2`
on the flag. Ships all 16 entries of line 2 rather than the fire's 3, which is *more* correct for
"fully submerged". This is the only option with an exact, side-effect-free restore.

**Where the flag is computed (this one is subtle and Lens A caught it).** NOT in VBlank. Verified
ordering: `Camera_Update` (`ojz_scroll_test.emp:310`) -> `Parallax_Update` (`:481`, overlay reads
`Camera_Y` at `parallax.emp:747`) -> VBlank -> `Raster_PatchAll` (`raster.emp:886` reads
`Camera_Y`). Both consumers already see the same tick's camera. A state computed in VBlank and
stored would reach the parallax overlay one `Camera_Update` LATER — palette whole-screen wet while
the shimmer still splits mid-screen, a guaranteed one-frame pop at every transition. **Latch in
the main loop after `Camera_Update`, before `Parallax_Update`; `Raster_PatchAll` consumes the
latch.** Latch L itself, not just the state, or a lag frame derives the fire line and the state
from different cameras (`VInt_Lag` also calls `Raster_VBlank`, `vblank.emp:291`).

**Register reality:** `Raster_PatchAll` has no free register (`clobbers(d0-d4/a0-a2)`, all live;
`VInt_Lag` omits a3), so the latch must be a RAM cell written at `raster.emp:894` where the
unclamped L briefly exists — which is the same conclusion the latch argument reaches.

## 2. THE BIGGER PRIZE — Ristar dissolves the "cannot park one record" blocker

§2 of the draft rejects genuine suppression because gaps are relative, so parking one record kills
every later one. **That is an artifact of Aeon's array-of-gaps encoding, not of raster programs.**
Ristar's HBlank is a self-rewriting linked list: each node writes its own gap AND its own successor
(`ristar_disasm/code/disasm.asm:14556-14595`), so removing a node is a local edit. It runs two
independently armed effects off one chain with separate thresholds, and a disarmed effect costs
interrupt entry + `tst`/`beq`/`rte` (~40 cycles) instead of its payload
(`disasm.asm:16184-16199`, and the arm tests at `$00E142`/`$00E250`/`$00E2A0`/`$00E30E`).

Also worth knowing: **Sonic 2 clamps exactly as Aeon did** (`s2.asm:5280-5292`, clamping to 223),
and S3K/S.C.E. deliberately changed it to disarm. Aeon independently reproduced S2's design and its
bug. And `HInt5` (`sonic3k.asm:1060-1108`) is Sega's own byte-for-byte water handler with the base
and water palettes swapped, shipped disabled — the draft's "invert which buffer holds water" idea,
built and abandoned by its originators.

---

*The rejected draft follows unedited.*

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
