# `Palette_DeriveVariant` gate — A/B evidence (2026-08-13)

Parcel: `fix/palette-variant-derive` (aeon + sigil).
Claim: the variant derive cost 15.1% of every frame recomputing a constant; gating it
on "did the source move?" recovers that entirely, with a byte-identical result.

## Builds

| shape | before (master `78205620`) | after |
|---|---|---|
| `s4.bin` | `2e932149` / 696788 | `601fc11b` / 696788 |
| `s4.debug.bin` | `f9b3d140` / 711252 | `d792e8d6` / 711252 |

Lengths unchanged in both shapes — the +0x30 of code is org-anchor absorbed. Same
oracle instance, ROM swapped between legs, symbols reloaded each time.

## Root cause, measured BEFORE any code change

Not a broken early-out. `tst.b Pal_Active` did exactly what it says; the problem is that
`Pal_Active` answers *"is a slot bound?"* while the derive needs *"did this layer's input
change?"*. Read live on `OJZ_ScrollTest`:

```
Pal_Variant_Ptr[0] = 0x00007C84   (Variant_Water_Deep, bound)
Pal_Variant_Ptr[1] = 0x00000000
Pal_Cycle_Script   = 0x00000000
Pal_Fade_Frames    = 0x00
Pal_Op             = 0x00
Pal_Base_Dirty     = 0x00
Pal_Active         = 0x10          <- ONLY PAL_ACT_VARIANT
```

So every frame skipped base, cycling, fade and operators and ran **only** the derive —
whose inputs never moved: `Palette_Buffer` (source, 128 B) and `Pal_Variant_Stage`
(output, 128 B) both read **bit-identical** across frames many apart.

Transform verified correct by hand, so this was waste and not a math bug: buffer line 1
word 2 = `0x0E62` -> R=1 G=3 B=7; `variant(shift_r: 1, shift_g: 1)` -> R=0 G=1 B=7 ->
repacks `0x0E20`, which is what the stage held.

`variant()` defaults `lines` to `%1110`, so the cost is 3 lines x 16 entries = **48
entries at ~403 cyc**.

Why it read identical in every section: there is exactly ONE `Palette_SetVariant` call
site in the tree (`ojz_scroll_test.emp:280`, scene init) and nothing ever unbinds it.

## The A/B — same scene, same 30 profiled frames, profiler on both legs

| routine | before | after |
|---|---|---|
| `Palette_DeriveVariant` | 19332 (**15.1%**) | **absent from top-14** (floor 1095) |
| `Palette_DoVariants` | 19428 (15.2%) | absent |
| `Palette_Compose` | 19568 (15.3%) | absent |
| `VSync_Wait` (idle) | 80267 (**62.7%**) | 99688 (**77.9%**) |

Idle rose **+15.2 points**, matching the 15.3% compose cost almost exactly — the whole
cost came back as headroom rather than moving somewhere else.

**Controls, unchanged across the legs** (this is what makes it a controlled A/B rather
than two readings): `GameState_OJZScroll_Update` 20593 / 20593 · `Parallax_Update` 7388 /
7388 · `Parallax_Fill_PerLine` 3908 / 3908 · `Render_Sprites` 3653 / 3653 ·
`Process_DMA_Critical` 2696 / 2696 · `RunObjects` 2278 / 2278 · HInt 8503 / 8500 ·
`total_cycles` 128005 / 128005.

## Correctness

1. **`Pal_Variant_Stage` is BYTE-IDENTICAL after the fix** — all 128 bytes, against the
   pre-change capture. Same image, ~19.5k fewer cycles. This is the load-bearing check:
   the staging image is exactly what `OP_PAL_REGION` streams mid-frame.
2. **Render matches** — the section-1 water band and the darkened lower region are
   visually identical between legs (the only pixel delta is the animating ring frame).
3. **Zero RAM movement** — `Palette_Buffer` `$FFFF821A`, `Pal_Variant_Stage` `$FFFF8B78`,
   `Pal_Active` `$FFFF8C8C` all at their pre-change addresses, because the flag took a
   free bit in `Pal_Active` rather than a new cell.
4. `Pal_Active` reads `$10` in the steady state after the fix — the stale bit is clear,
   i.e. the gate is genuinely skipping rather than the flag being stuck set.

## What this does NOT claim

A frame whose source actually moved still pays the full ~19332. Lever A removes the
*redundant* derives, not the derive. Real content running continuous cycling or a fade
will pay it every frame, and the answer there is the bind-time per-channel LUT (lever C),
banked in DEFERRED_WORK with this number. Measuring that today would mean measuring a
garish test fixture, which is the same caveat that qualifies the dense-tier
reserved-register ruling.
