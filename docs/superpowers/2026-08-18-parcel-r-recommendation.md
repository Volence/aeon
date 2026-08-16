# PARCEL R — re-read against what shipped since. **The decision has collapsed.**

> **SUPERSEDED 2026-08-18 — THIS RECOMMENDATION IS WRONG.** Its central claim, that `Palette_Buffer`
> needs no new owner and is safe to read mid-frame, is false: `Palette_Compose` runs from the MAIN
> LOOP during active display (`game_loop.emp:43-49`), so the buffer is one compose-generation AHEAD
> of the CRAM a restore must match. Two lens seats found it independently. See
> `2026-08-18-parcel-r-sweep-adjudication.md`. The ground truth below about WHERE the values live is
> still correct; the conclusion drawn from it is not.

**Date:** 2026-08-18
**Supersedes the recommendation in** `2026-08-16-overnight-work-order.md` ("Parcel R (queue item 6)"),
whose ground truth is all still correct. Only its conclusion is overtaken.

---

## The question R was stopped on

> Does "restore" become a first-class op with its own storage, or does the band become an authoring
> pattern over the ops that already exist?
>
> - **(A)** a restore op — "needs a new RAM region plus an owner who keeps it truthful across
>   cycling/variant/cross-fade. **That owner question is the real cost.**"
> - **(B)** two fires and no new mechanism — "degrades badly the moment the base palette is itself
>   animated."
> - **(C)** defer until after W — RECOMMENDED at the time, on the grounds that W was about to decide
>   who owns shared per-effect state, and "if W's answer generalises, R may get its staging buffer
>   for free and the question collapses."

**(C) has expired: W shipped 2026-08-15.** This is the promised re-read.

## The finding: the staging buffer already exists, and already has an owner

R's blocker was never the op. It was the sentence *"it needs a staging buffer holding the pre-effect
values, maintained by somebody."* **Somebody already maintains one, and it predates the question.**

`Palette_Buffer` (`engine/ram.emp:225`, 128 bytes = 4 lines x 32) holds **the live composed base
palette**. From `engine/effects/palette.emp:67-68`:

> "Pal_Composed is ELIDED: the compose writes straight into `Palette_Buffer` and the variant derive
> reads `Palette_Buffer` as 'the live composed palette'"

and `:104`: `Palette_DeriveVariant` is "a pure function of (descriptor, `Palette_Buffer` lines ...)".

So the composition pipeline — `base -> cycling -> cross-fade -> global operators -> variants` — lands
in `Palette_Buffer` at the *pre-variant* stage, with the VARIANT going to the separate
`Pal_Variant_Stage` that `OP_PAL_REGION` already streams from. Three consequences, all of which
dissolve (A)'s stated cost:

1. **No new RAM region.** `Palette_Buffer` is exactly the pre-effect image a restore wants.
2. **No new owner.** `Palette_Compose` is already "one owner, one deterministic order, composed once
   per frame" (`palette.emp:31`), and it is kept truthful across cycling, cross-fade and variants
   **because the frame-top restore already depends on it being so** — `Enqueue_Dirty_Buffers`
   re-ships those CRAM lines from it every frame. A restore op inherits that correctness rather than
   needing its own.
3. **No mid-frame writer.** `Palette_Compose` runs from **GameLoop, not VBlank**
   (`engine/system/game_loop.emp:49`), and `Enqueue_Dirty_Buffers` reads it in VBlank. During active
   display the buffer is stable, so the handler only ever READS it — the identical read-only
   relationship `OP_PAL_REGION` has with `Pal_Variant_Stage` today. The P-b-in-spirit worry about a
   new mid-frame writer of engine state does not arise, because there is no new writer.

## What the op actually is

Structurally the same op as `OP_PAL_REGION` with a different source base:

```
OP_PAL_REGION   lea Pal_Variant_Stage, a2   adda.w <comptime offset>, a2   stream count words
OP_PAL_RESTORE  lea Palette_Buffer, a2      adda.w <comptime offset>, a2   stream count words
```

Same wire body, same cycle cost, same `EFX_BLANK_DELAY` treatment, same `RASTER_CRAM_MAX` ceiling,
and the comptime offset is the same arithmetic one line simpler (`line * 32 + entry * 2`, with no
variant slot). The handler's compare chain gains one opcode.

**It is arguably not even a new op.** `OP_PAL_REGION`'s source base could become a wire field —
staging vs base — making "restore" a *parameter* of the existing op rather than a sibling. That is a
design-draft question, not a decision-to-stop question, and it is the kind of thing the lens sweep
should adjudicate.

## Recommendation: **(A), and it is now a small parcel**

(B) was only ever attractive because (A) was priced at "a new RAM region plus an owner". That price
is already paid, by a pipeline that shipped for other reasons. (B)'s stated weakness is real and
unchanged — baking base colours into a program breaks the moment cycling, a variant or a cross-fade
moves them, "i.e. exactly when the engine is doing something interesting" — and there is no longer
any saving to buy it with.

## What is still genuinely open — the design draft's job, not a blocker

1. **Op or parameter?** A distinct `OP_PAL_RESTORE`, or a source-select field on `OP_PAL_REGION`.
2. **Density is the real constraint on band height.** A restore fire is an ordinary fire: a 3-word
   CRAM fire measured **526 cycles against a 488-cycle line**, so a band costs TWO fires and
   `check_density` adjudicates the minimum gap between them. A very short band may be refused at
   build time. That is correct behaviour, but it must be stated so an author is not surprised.
3. **>3 entries needs consecutive fires**, exactly as setting them does (`RASTER_CRAM_MAX`).
4. **The symmetric register case.** R's brief is about palette, but "turn S/H off at line 140" has
   the same shape and the same answer available: `VDP_Shadow_Table` is the register analogue of
   `Palette_Buffer` — the frame-top restore's own source, maintained by one owner, read-only during
   active display. Whether R takes that too, or books it, is a scope call for the draft. It should
   at least not be designed out.

## Process from here

R is a new op class touching the raster wire format, so: research -> design draft -> **three
mixed-model adversarial lenses** -> owner sign-off -> plan -> execute. The same sequence that caught
two load-bearing defects in the local-removal draft.

Its gate is already built: `aeon/tools/scenes/` + `aeon/tools/effects_scene_assert.py` assert a
raster program's shape from a deterministic harness capture, so R's evidence can be a committed
scene rather than a hand-run ritual — the first parcel that gets to start that way.
