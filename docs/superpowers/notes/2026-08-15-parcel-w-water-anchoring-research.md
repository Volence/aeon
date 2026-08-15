# Parcel W research — how the references anchor a water surface

Gathered 2026-08-15 for the Parcel W design draft
(`docs/superpowers/specs/2026-08-15-effects-p3-parcel-w-design.md`). Sonic-family seat complete;
the Treasure/Sega non-Sonic seat is recorded separately below when it lands.

## The Sonic baseline (skdisasm, S.C.E., s2disasm, sonic_hack)

**1. The water line is an absolute world Y, never a screen value.** S3K loads it per act from
`StartingWaterHeights` into `Water_level` / `Mean_water_level` / `Target_water_level`
(`skdisasm/sonic3k.asm:8802-8806`).

**2. It becomes a screen line in exactly one instruction, once per frame.**

| codebase | conversion |
|---|---|
| S3K | `sonic3k.asm:8494-8495` — `move.w (Water_level).w,d0` / `sub.w (Camera_Y_pos).w,d0` |
| S.C.E. | `Engine/Core/Water Effects.asm:25` — `sub.w (Camera_Y_pos).w,d0` |
| S2 | `s2.asm:5277-5281` — same shape |
| sonic_hack | `code/engines/water.asm:14-15` — `move.w #$130,d2` / `sub.w (Camera_Y_pos).w,d2` |

Aeon's raster patch channel already does exactly this, once per record
(`engine/effects/raster.emp:892-894`). **W2 proposes the same single conversion for the band top,
which is the reference-standard spelling, not an invention.**

**3. "Surface above the camera top" is a distinct STATE, not a negative line.** S3K sets
`Water_full_screen_flag` and `H_int_counter = -1`, swapping a whole-screen CRAM DMA in VBlank and
disabling the HInt entirely (`sonic3k.asm:8496-8505`). S.C.E. mirrors it
(`Water Effects.asm:30-33`). The draft's `L <= 0` branch — the anchored band takes the whole screen,
count 1 — is the same idea in the band pipeline's terms.

**4. The underwater region is TERMINAL by construction in every one of them.** The HInt handler
blits the water palette and immediately reprograms VDP reg `$0A` so it cannot fire again this frame:
`sonic3k.asm:1238` (`move.w #$8A00+224-1,…`), `:1015` (`$8AFF`), S.C.E.
`Engine/Core/Interrupt Handler.asm:390`. There is no bottom edge and no structure below the surface.
**This is the strongest single piece of support for the draft's terminal-band rule** (§3.2): no
reference codebase has ever needed structure below a water line, and the mechanism they all use makes
it unrepresentable rather than merely unused.

**5. Bands and water are two orthogonal systems in the references.** Band tops are walked from the BG
camera copy — `sonic3k.asm:103665` `move.w (Camera_Y_pos_BG_copy).w,d0` inside `ApplyDeformation`,
S.C.E. `Deformation Script.asm:150-155` — i.e. **art-anchored, exactly like Aeon's plane-space band
tops**. Water is a screen-space HBlank CRAM swap. They never interact: water changes no scroll value,
deformation changes no palette line.

**Aeon is deliberately past this point.** Parcel W exists precisely because we want the two to share
a boundary, which no reference does. That is not a warning sign by itself — the standing rule here is
*decide by best overall, not precedent* — but it does mean **the references supply no proof for the
seam, only for the anchor space and for terminality.**

## Where Aeon already exceeds the references, and must not regress

**The ripple/deform phase.** S3K has **no per-line HScroll water ripple at all**; HCZ's waterline is
DMA'd tile animation keyed on a level-event value (`sonic3k.asm:53970`, `:54000`), and the S1 ripple
table is a dead leftover the disassembly comments on directly (`:33449-33450`). The S1/S2 ripple that
does exist is **screen-anchored**: its index is the frame counter alone —
`s2.asm:15285-15302`, `move.b (Vint_runcount+3).w,d1 / andi.w #7,d1 … andi.w #$1F,d1` — with camera Y
entering only through the band walker, never through the ripple index. S2's ARZ, the actual water
zone, has no ripple whatsoever (`SwScrl_ARZ`, `s2.asm:17644`).

That screen-anchored index **is** the defect the Harmony study logged as #2 and that
`parallax.emp:937-944` fixes by folding `Camera_Y` into the sample index. So:

- The work order's citation ("S3K anchors ripple phase to world quantities in three separate
  places") is **not supported by the tree it cites** — S3K has no ripple to anchor. The fix Aeon
  shipped is ours, and it is ahead of all four references.
- Any W design that touches the phase fold is giving up the one place Aeon is already better. The
  draft does not touch it, and §5.1 of the draft is the gate that proves it did not.

## Bearing on the draft's open choices

| draft choice | reference support |
|---|---|
| act-space world Y is authoritative (§2 Q1) | **strong** — unanimous across four codebases |
| one `sub Camera_Y` conversion at read time (§3.2) | **strong** — the exact instruction, in all four |
| `L <= 0` is a whole-screen state (§3.2) | **strong** — S3K/S.C.E. `Water_full_screen_flag` |
| the anchored band is terminal (§3.2) | **strong** — structurally terminal in all four |
| plane-anchored bands stay art-anchored (§2) | **strong** — `Camera_Y_pos_BG_copy` in S3K and S.C.E. |
| a boundary SHARED between palette and scroll (all of W) | **none** — no reference attempts it |
| camera-folded deform phase (existing, untouched) | **none** — Aeon is ahead; protect it |
