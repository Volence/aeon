# rowRemap route (c): the gate is over-strict, and its stated reason is FALSE for a curve

Aurora found by building — not reading — that a scene with a **curve** links and writes
`s4.bin`, then is refused by the post-sigil `tools/row_remap_gate.py` for a NULL
`pcfg_deform_table_bg`, **while citing a comptime guard that accepts exactly that case.**
They declined to guess which side was wrong and handed me the call. This is the ruling.

## What the gate says (`row_remap_gate.py:494-499`, the visibility arm, added 2026-09-03)

> `pcfg_deform_table_bg` is NULL, so **the per-line sample loop is flat-pathed and every
> line of this band gets the same plane-B scroll word. Remapping that is the identity.**
> `scene()`'s comptime guard requires a table alongside a live shift; a NULL here means the
> lowering dropped it.

## Why it is over-strict

The cited authority requires a table **"alongside a live shift"**. A curve layer
**structurally cannot have a live shift**: `layer()` refuses `curve` together with any live
deform amplitude (`dsa`/`dsb != 15`) for a measured register reason — the curve loop already
spends all seven usable data registers (`ojz_scenes.emp`, the perspective-floor banner).

So a curve band has `dsb = 15`, no live shift, and the comptime guard **correctly** does not
require a table. The gate applies the requirement unconditionally. **The guard is not
under-strict; the gate is checking a condition its own quoted authority conditions away.**

## And its REASON is factually wrong for this case, which matters more

The gate's premise is that a NULL table means *"every line of this band gets the same
plane-B scroll word"*. **That is false when a curve is present.** The curve hoist
(`engine/level/parallax.emp`, `.cap_factor_curve_hoist`) decodes the far-end factor to a real
scroll value, takes `spread = far_end - base`, and Bresenhams `spread/span` **per line**. The
whole point of a curve is that every line's scroll word differs.

So the remap is **not** the identity on a curve band. The gate refuses a case that works, for
a reason that does not hold in that case.

## Ruling

**The gate is wrong. The comptime guard stays as it is.** The visibility arm must treat a
band as varying if EITHER a deform table is present OR the band carries an active curve —
the band record already has `CURVE_FLAG_ACTIVE_BIT`, so the gate can read it without new
plumbing.

**Not fixed in this session** (at a boundary); booked so the next parcel has the ruling
rather than the question.

## The generalisable half

**A gate that quotes an authority should be tested against that authority.** This one cites a
comptime guard as its justification and then enforces something stricter — and the citation
is what made it look correct. Aurora read the quoted guard and found it said something else.
Same shape as the consumer-contract line found this morning: **a rule and its stated reason
drifting apart, with the reason still reading as authoritative.**
