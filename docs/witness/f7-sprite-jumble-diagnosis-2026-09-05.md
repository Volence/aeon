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

---

## CORRECTION, same session, before anyone acted on the above

**I overstated "zero headroom" as if it were a defect. It is the design.**

`DPLC_ENTRY_RESERVE = 2` is not slack that the player is eating — it is the allowance
**reserved for everyone else**. Player peak 10 + reserve 2 = 12 = `DMA_IMPORTANT_SLOTS` is
the budget being spent exactly as intended, and the gate is green because it *is* correct.
A drop needs non-player consumers to want **more than 2** Important slots on a peak player
frame. I did not check whether they can.

**And the frame-ID corroboration I called the cheapest next check has now been done, and it
mostly fails.** From `player_common.emp:224-244`, the tilt frames are walk `$01-$20` and run
`$21-$30`:

| peak frame | is it a tilt frame? |
|---|---|
| `$1E` | **yes** — walk tilt block 3 |
| `$8B` `$90` `$C2` `$C7` `$DF` | **no** — outside `$01-$30` |

**One of six.** So "the peak frames are the rotated frames" is not true as stated.

**The historical breach is also confirmed CLOSED rather than merely superseded**
(`collision_data.emp:65-78`): `$C4` (LookUp) and `$0E` (walk tilt block 1) each sat at 12,
the whole queue, and were re-cut by `tools/dedup_art.py` trading entries for bytes on
exactly the six frames that were over the wall. That is the fix that already shipped.

## So what F7 actually needs next

The mechanism (drop → stale `prev_frame` → SAT drawn against unloaded tiles) is real and is
still the only candidate that produces his picture. What is missing is a reason the drop
happens **today**, and the specific question is now:

**can non-player Important-queue consumers want more than `DPLC_ENTRY_RESERVE = 2` slots on
a frame where the player wants 10?** Enumerate every `QueueDMA`-Important caller and its
worst-case per-frame demand. If the answer is no, the DPLC path is exonerated and the
jumble is something else — and `DRAW_SPRITE.NO_PARENT` in his capture points at the sprite
emit rather than the load.

**What I got wrong and why it is worth recording:** I had a mechanism, a matching symptom,
and numbers that summed to exactly the budget, and I read "exactly full" as "over". The
arithmetic was right and the conclusion did not follow from it. The corroboration I myself
called cheapest is what caught it — one frame in six, not six in six.

---

## THE INSTRUMENT ALREADY EXISTS, and it is aimed at exactly this question

`engine/ram.emp:1424-1460` documents four DEBUG cells built for the d-47 booking
*"DMA SPLIT-REJECT NEEDS TWO FREE IMPORTANT SLOTS, AND NOTHING COUNTS PER-FRAME
STRADDLES"*:

| cell | addr | what it is |
|---|---|---|
| `Dbg_DMA_Straddle_Frame` | `$FFE914` | this window's straddling IMPORTANT enqueues |
| `Dbg_DMA_Straddle_Peak` | `$FFE916` | high-water mark — **the number the booking asks for** |
| `DMA_Split_Reject_Count` | `$FFE918` | **"Any non-zero value here is the defect, observed directly"** |
| `Dbg_DMA_Straddle_All` | `$FFE91A` | free-running, EVERY queue — **the positive control** |

And `ram.emp` states the gap my corrected diagnosis was groping for, in its own words:

> That reserve was sized from total art VOLUME — ~354 KB across the cast — which bounds how
> many straddling entries EXIST IN THE ROM and **says nothing about how many can want slots
> in ONE FRAME**. … the per-frame count of straddling ENQUEUES is a run-time property … and
> **NOTHING measured it. These four cells are that measurement.**

So the F7 question — can non-player Important consumers want more than the reserved 2 — is
precisely the question these cells were added to answer, and the answer has never been read.

## What I measured, and why it is weak

Boot, then `RIGHT` held for 600 frames on `s4.debug.bin` (845944):

| | at boot | after 600 frames |
|---|---|---|
| `Straddle_Frame` | 0 | 0 |
| `Straddle_Peak` | 0 | 0 |
| `Split_Reject_Count` | **0** | **0** |
| `Straddle_All` (control) | 2 | 2 |

**No split rejects. But this run is NOT representative and I am not going to present it as
one.** The player ended at x3401, **y5587** — he ran off the built ground early and spent
most of those 600 frames in free fall. Free fall streams nothing and animates almost
nothing, so the zero is close to uninformative.

**And the control did not move either** (2 at boot, 2 after), which by `ram.emp`'s own
reading rule makes the Important zeros uninterpretable for THIS window: a zero means
"Important never straddled" only while the control is moving.

## The parcel this needs

Long, varied, **grounded** play driven headlessly through `tools/aether_instance.py` — the
harness `tools/canopy_gap_exercise.py` already uses to drive 21,439 frames across all nine
sections — polling the four cells throughout, with the control asserted non-zero-and-moving
before any Important zero is read as meaning anything.

If `DMA_Split_Reject_Count` goes non-zero during play, F7's cause is found and the engine
said so itself. If it stays zero across representative play **with a moving control**, the
DPLC starvation path is exonerated and `DRAW_SPRITE.NO_PARENT` points at the sprite emit.
