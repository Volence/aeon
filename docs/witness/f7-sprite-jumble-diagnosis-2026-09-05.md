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

---

## ANSWERED — see `f7-straddle-instrument-read-2026-09-05.md` (same day)

The parcel this section asks for has been run. 36829 frames of grounded play, 735 polls,
62.7% grounded, 28 of the walk/run tilt frames `$01-$30` exercised across all nine
sections. **All four cells stayed at 0, and so did the two other drop paths
(`DMA_Overflow_Count`, `Dbg_DMA_Enq_Capped`).** The control did not move in play — and the
act's page manifest says it *cannot*: OJZ's whole art pool sits inside one 128 KB block, so
no page-in landing can straddle, and `dplc_straddle` already had every straddling DPLC
frame in the cast unreachable. A forced control (Sonic's `$65`, on a separate machine)
moved both `Dbg_DMA_Straddle_All` and the Important-only `Dbg_DMA_Straddle_Frame` 0 → 1,
proving the instrument live.

**So the DPLC starvation path is exonerated and `DRAW_SPRITE.NO_PARENT` points at the
sprite emit.** Two corrections to what is written above:

- The "600 frames of RIGHT" run had a **second** defect beyond the free fall: the canonical
  DEBUG shape boots **already in debug fly**, where `mapping_frame` is pinned at `$00`,
  `prev_frame` at `$FF`, and the player never animates — so `Perform_DPLC` early-outs every
  frame and the player enqueues nothing at all. That window measured the subject system
  switched off. A B press is what turns it on.
- The "2 at boot, 2 at the end" control reading above does not reproduce: on
  `s4.debug.bin` crc32 `8bb835d7` built from `1f2aab07`, `Dbg_DMA_Straddle_All` reads **0**
  at boot and 0 after 36829 frames, which the static survey says is the correct value.

---

## THE OTHER WALL: the drain defers, and nothing counts a deferral (2026-09-05)

**Three corrections to this document first, all found while checking its references.**

1. **`DRAW_SPRITE.NO_PARENT` is real, and this doc's spelling is the third of three.**
   `s4.debug.lst:3355` carries `$engine.objects.sprites$Draw_Sprite$no_parent : 370A`.
   Oracle demangles a mangled name to its **last two `$` components joined with a dot**
   (`oracle/crates/oracle-core/src/symbols.rs:1295`), which is exactly
   `Draw_Sprite.no_parent`; this doc then upper-cased it. **A recursive `grep` for it in an
   agent shell finds nothing**, and the mechanism is READ, not inferred: the harness shell
   snapshot defines `grep` as a function running the claude binary as **`ugrep
   --ignore-files ... -I`**, so it honours `.gitignore` (and `*.lst` is ignored at
   `.gitignore:20`) and skips binaries. Measured from the repo root: shell `grep -rl` over
   `*.lst` returns **0** files, `command grep` and `/usr/bin/grep` return **343**. Use
   `command grep`, `git grep` or `/usr/bin/grep` for anything that must see build outputs.

   **⚠ Two control designs make this hazard look refuted, and both were run today.**
   (a) A canary that starts its walk BELOW the `.gitignore` never reads it -- put marker
   files in `<repo>/x/` and search `x` and both greps agree, search `.` and they diverge.
   (b) A canary run through `subprocess.run(..., executable='/bin/bash')` resolves `grep`
   to `/usr/bin/grep`, so it compares the tool with ITSELF and agrees perfectly. A test
   that bypasses its own subject cannot fail, and its passing is indistinguishable from a
   clean refutation. Compare two greps only in the shell whose `grep` is under test.
2. **`.no_parent` is not the child-skip guard, it is the CULL BLOCK.** It spans
   `$370A-$3765` (the next symbol, `.screen_coords`, is at `$3766`), so a PC there means
   only "inside `Draw_Sprite`'s culling, mid-`RunObjects`" -- it says nothing about
   multisprite parents. And `Render_Sprites` has not run yet at that PC, so the buffer read
   at it is the LAST COMPLETE emit plus an uncleared tail, which is by design: `H3` ships
   `Sprites_Rendered * 4` words, so entries past the live count are never sent.
3. **`Dbg_DMA_Straddle_All` is at `$FFE912`, not `$FFE91A`** as the cell table above says.
   `$FFE91A` is `BgAnim_Table_Ptr`. The campaign tools resolve the symbol from the listing
   and were never wrong; only this table is.

**The mechanism this doc's exoneration does not cover.** Every instrument read so far
counts a DROP. The Important queue has a second wall that is not a drop:
`Drain_Budgeted_Queue` (`engine/system/dma_queue.emp`) hits `.out_of_budget`, **compacts
the survivors to the base and leaves them for next frame**. The enqueue already returned
**carry clear**, so `perform_dplc` has ALREADY committed `prev_frame`; no counter moves.
Meanwhile `VInt_Level` ships the SAT on **Critical, which is unbudgeted and always fully
drains** (`vblank.emp:200`), before it ever calls the budgeted `Process_DMA_Important`
(`:264`). Nothing interlocks the two. So the VDP is handed the new frame's mappings over
partly-old art, for exactly one frame, silently.

**Order decides who loses.** One `GameLoop` pass runs `VSync_Wait` -- where
`PageIn_Process` enqueues a 2048 B page landing on Important -- **before** the state
dispatch where `perform_dplc` enqueues the player's art. The queue is FIFO and the drain
walks from the base, so the page landing spends the budget first and the player's art is
what gets deferred.

**The arithmetic, derived in `tools/dma_defer_headroom.py` (gated in build.sh).**
NTSC budget 6144 - plane drain 1536 - Critical (128 palette + 640 SAT + 896 HScroll)
= **residual 2944 B**. Worst-case demand = 2048 page landing + 928 peak Sonic DPLC frame
= **2976 B**. **Deficit +32 B, one tile.** PAL's residual is 8448 B and has 5472 B spare.
Sonic's two peak-byte frames are `$0E` and `$1E` -- both walk-tilt frames, which is his
"rotated slightly". Every charge is that rider's MAXIMUM, so this is an ENVELOPE and not
an observed frame: it says the window is open and how wide, never that play enters it.

## THE FOREGROUND RECIPE -- run this at the machine, it needs no rebuild

The whole hypothesis has a **cause-side knob in RAM**: `DMA_Budget_Default` at
**`$FFFF8210`**, re-read into `DMA_Budget_Remaining` at the top of every `VInt_Level`
(`vblank.emp:136`). Turning it down makes the deficit permanent; turning it up switches the
mechanism off. That is a control on the proposed cause, not a correlation with a symptom.

**Addresses, all from `s4.debug.lst` on this branch.**

| what | address | reading |
|---|---|---|
| `DMA_Budget_Default` | `$FFFF8210` | the knob (word) |
| `DMA_Important_Slot` | `$FFFF820C` | post-drain occupancy (word) |
| `DMA_Important` (base) | `$FFFF80BA` | slot == base means fully drained |
| `DMA_Peak_Important` | `$FFFF8F74` | BYTES from base; one entry = 14 |
| `DMA_Overflow_Count` | `$FFFF8F78` | drops. Must stay 0 |
| `Dbg_DMA_Enq_Capped` | `$FFFF8F7A` | byte-cap rejects. Must stay 0 |

**The breakpoint: `$002414`.** Decoded from this build's own bytes, it is the
`tst.b PageIn_Staging_Busy` immediately after `bsr.w Process_DMA_Important` at `$002410`,
reached unconditionally every `VInt_Level` frame before anything else touches the queue.
`(DMA_Important_Slot - $80BA) / 14` = entries the drain **deferred**.

**STEP 0, and skipping it voids everything after it.** `DEBUG=1` boots in debug fly, where
`mapping_frame` is pinned `$00`, `prev_frame` `$FF`, and `Perform_DPLC` early-outs every
frame. **Press B** to leave it, then run 300 frames of movement and read
`DMA_Peak_Important`. **If it is <= 14 (one entry), the DPLC never ran, the subject was
switched OFF, and the run must be discarded -- not reported as a zero.** A prior 600-frame
run measured exactly this and read clean. Also compare `romBytes` against the ROM on disk
before any measurement.

**ARM 1 -- does it happen on its own.** Break at `$002414`, play a grounded run through the
loop (warp with `Warp_Req_X` `$FFEE02`, `Warp_Req_Y` `$FFEE04`, `Warp_Req_Flag` `$FFEE06`
u8; ack is the flag clearing and `Camera_Y` moving). CONFIRMED = `DMA_Important_Slot` reads
above `$80BA` on at least one frame while `DMA_Overflow_Count` and `Dbg_DMA_Enq_Capped`
both stay `0`. That combination -- **survivors without drops** -- belongs to this mechanism
and to no other: the booked stale-`prev_frame` hazard requires a drop and predicts the
opposite sign on the same two cells.

**ARM 2 -- the decisive one, because it is two-sided.**
Write `DMA_Budget_Default` = `$0400` mid-level (after `Level_LoadArt`, which sets it
itself). The Important queue can then never drain while the SAT keeps shipping.
**Predicted: a continuous, severe jumble while running, worst on the loop.**
Then write `$7FFF` and repeat the heaviest play you can. **Predicted: it never appears.**
For his intermittent picture rather than a constant one, try `$0BB8` (3000).

**WHAT REFUTES IT, and this outcome is reachable and cheap.** If `$0400` -- outright
starvation of the Important queue with the player animating -- does **not** make Sonic
jumble, then deferred art is not the mechanism and this whole line is dead, whatever
arm 1 says. Run `$0400` FIRST: it is the arm that can kill the hypothesis, and running it
first stops arm 1's result from being read in its light.

**A third prediction the other candidates do not make.** The NTSC residual is 2944 B
against a 2976 B demand; PAL's is 8448 B with 5472 B spare. **This mechanism should be
NTSC-only.** A mapping-table or emit defect would not care about the region.

**Still BLOCKED, and not by anything at the machine.** Whether the owner's picture is THIS
and not the mid-rebuild transient already booked cannot be settled here: his capture was
never committed, `git log --all` over that path is empty, and no reading of it can be
checked by anyone. The narrowest question that would settle it is his, not the debugger's:
**does he see it while PLAYING, or only after pausing?** A mid-rebuild RAM transient cannot
reach the screen during play. This one can, because the SAT was shipped and its art was not.

---

## 2026-09-05, later: the eliminating drive did not contain the subject

**The measurement that eliminated the deferred-Important-DMA path reported
`DMA_Peak_Important = $0070` = 8 entries, FLAT across a 1900-frame RIGHT-held drive.**
Derived here from the shipped `dplc/optimized/sonic.bin` and this build's own `Ani_Sonic`
(walked with `tools/dplc_straddle.py`'s machinery, so the strides come from
`Player_ApplyTilt`'s own constants, not from prose):

| block | walk frames | peak ENTRIES | peak BYTES | run frames | peak ENTRIES |
|---|---|---|---|---|---|
| 0 (upright) | `$01-$08` | **8** (`$05`) | 704 | `$21-$24` | **8** |
| 1 | `$09-$10` | 9 (`$0F`) | 928 (`$0E`) | `$25-$28` | 8 |
| 2 | `$11-$18` | 5 | 736 | `$29-$2C` | 2 |
| 3 | `$19-$20` | **10** (`$1E`) | 928 (`$1E`) | `$2D-$30` | 7 |

**8 is exactly the block-0 ceiling.** A flat peak of 8 over 1900 frames is what a player who
never leaves the upright block produces; it also proves no 9- or 10-entry frame (`$0F`,
`$19`, `$1E`) was ever enqueued, i.e. the top two rungs of the slot budget -- and both
928-byte frames -- were never exercised. The drive did not contain the population the
symptom is reported on. That does not resurrect the mechanism; it withdraws the elimination.

**The corollary IS sound, and now checked against source.** All three carry-set exits of
`QueueDMA` bump a counter (`.full` -> `DMA_Overflow_Count`, `.byte_capped` ->
`Dbg_DMA_Enq_Capped`, `.split_reject` -> `DMA_Split_Reject_Count`, all `if DEBUG == 1`,
`dma_queue.emp:168/178/250`). With all three at 0 in a DEBUG shape, `perform_dplc`'s
`bcs .done` never ran, so `prev_frame` was never left stale -- **for those runs**.

**A silent path with no counter at all**: `Drain_Budgeted_Queue.out_of_budget`
(`dma_queue.emp:459`) leaves entries queued and compacts them to the next frame. It is not a
drop, bumps nothing, and the SAT for that frame has already shipped above it. Read it as
`DMA_Important_Slot > DMA_Important` at the post-drain breakpoint.

**Statically refuted, so stop re-proposing it:** every one of Sonic's 224 frames has
`max mapping tile index + cells <= DPLC tile count` (both tables are indexed `frame*2`, so
they cannot disagree by construction), and `tools/dplc_straddle.py --gate` is green with 0
straddling REACHABLE frames. A per-frame mapping/DPLC index mismatch is not the cause.

**The instrument now refuses a vacuous drive.** `tools/dplc_coherence_witness.py` gained a
TILT POPULATION control that censuses the sampled `mapping_frame`s per orientation block and
prints a loud VACUOUS banner when none were tilted, plus a `DEFERRAL` line reading
`imp_left`, plus `--start X,Y` / `--cam X,Y` so the drive can be placed on a slope. Run it
with `--start` on the loop and check the census line **before** reading any verdict.
