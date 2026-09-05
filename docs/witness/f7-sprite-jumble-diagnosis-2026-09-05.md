# F7 — the sprite jumble: a diagnosis with numbers, and what is NOT yet established

His report: *"it does when playing, I got a lucky pause on it. here I paused exactly when it
happens, it's when a sprite is rotated slightly"* (capture: empyrean
`docs/captures/2026-09-04-owner-sprite-jumble.png`, PC in `DRAW_SPRITE.NO_PARENT`).

The capture shows Sonic assembled from the **right tiles in the wrong places** — a
mappings-versus-VRAM mismatch, not corrupt art.

## The mechanism, from `engine/objects/dplc.emp` — already documented in that file

`perform_dplc` (:214-262) does **not** commit `prev_frame` until every entry has enqueued:

```
jbsr    {queue}          // carry SET = dropped (queue full)
bcs     .done            // dropped — leave prev_frame stale so next frame RETRIES
```

That retry design is correct and deliberate. **But the SAT is still emitted this frame with
the NEW `mapping_frame`.** So on any frame where the enqueue is partially dropped, the
sprite is drawn from mappings whose tiles were never loaded — which is exactly the picture.

The file's own header states the consequence and even names the frames:

> At 12/12 the Important queue is 100% player and `PageIn_EnqueueLanding` is
> deterministically dropped — a streaming stall on exactly the frames the player holds
> (LookUp; **the walk-tilt frames, during ordinary running**).

**"the walk-tilt frames"** is his "rotated slightly".

## The measurement (mine, `tools/dplc_straddle.py --gate` on `s4.debug.bin`, exit 0)

| quantity | value |
|---|---|
| `DMA_IMPORTANT_SLOTS` | 12 |
| `DPLC_ENTRY_RESERVE` | 2 |
| the wall the ratchet aims at | 12 - 2 = **10** |
| peak player DPLC **entries** | **10**, frames `$1E $8B $90 $C2 $C7 $DF` |
| peak **slots** over REACHABLE frames | 10 at `$1E`, `$8B` |
| straddling entries | 1, across frame `$65` |

**10 + 2 = 12 = DMA_IMPORTANT_SLOTS.** On those six frames the Important queue is **exactly
full**. It is under the wall and therefore green — the gate is not lying — but there is
**zero headroom** on precisely the frames the header warns about.

## What this says, and how confident each part is

- **MEASURED:** peak 10 entries on six named frames; reserve 2; slots 12; the queue is
  exactly full there.
- **MEASURED (in-tree, prior work):** a dropped enqueue leaves `prev_frame` stale, and the
  object shows stale tiles until it retries.
- **INFERRED, not shown:** that in play, a competing Important enqueue on one of those six
  frames causes a partial drop and produces his picture. The pieces all exist; I have not
  caught the two happening together.
- **NOT ESTABLISHED:** that frames `$1E $8B $90 $C2 $C7 $DF` ARE the rotated/tilt frames.
  That is the single cheapest corroboration available and it has not been done.
- **REFUTED as the cause:** the historical 13-entries-against-12-slots breach, which the
  header describes as PERMANENT ("that entry's tiles never load"). Peak is 10 today, so
  that specific defect is fixed and is not what he is seeing.

## What I saw on the emulator, which is less than a reproduction

Drove the loop rightward at `$600` (rotation happens on the arc) and stepped the crest.
The SAT at frame 378: slots 0-3 form Sonic with a **terminated link chain**; slots 4, 5 and
6 hold **stale entries** — slot 5 reusing base tile 978, the same as slot 2 — which are
unlinked and therefore not drawn that frame. Suggestive of SAT slot reuse, **not** the
jumble. **I did not reproduce his picture.**

## The honest next step

Corroborate the frame IDs against the rotation set first — if `$1E $8B $90 $C2 $C7 $DF` are
not the tilt frames, this diagnosis is wrong and cheaply so.
