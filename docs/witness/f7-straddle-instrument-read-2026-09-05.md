# F7 — the four straddle cells, read at last: the numbers, and what they are worth

Companion to `f7-sprite-jumble-diagnosis-2026-09-05.md`, which ends by asking for exactly
this run. Driver: `tools/dma_straddle_exercise.py`. Full per-poll record:
`docs/witness/f7-straddle-campaign-2026-09-05.json`.

ROM `s4.debug.bin`, 845944 bytes, crc32 `8bb835d7`, built from this branch's base
(`1f2aab07`). Campaign wall clock 124.4 s, machine uptime 11 days 48 min at the end of it.

## The four numbers, and the two beside them

**36829 frames** of driven play (614 s of game time), 735 polls, **62.7 % grounded**
(429 of 684 polls in the grounded phases), 16 free-fall rescue warps.

| cell | at boot | final | max over 735 polls |
|---|---|---|---|
| `Dbg_DMA_Straddle_All` (control) | 0 | 0 | **0** |
| `Dbg_DMA_Straddle_Frame` | 0 | 0 | **0** |
| `Dbg_DMA_Straddle_Peak` | 0 | 0 | **0** |
| `DMA_Split_Reject_Count` | 0 | 0 | **0** |
| `DMA_Overflow_Count` (adjacent) | 0 | 0 | **0** |
| `Dbg_DMA_Enq_Capped` (adjacent) | 0 | 0 | **0** |

The last two are not the parcel's subject and are here on purpose. The F7 mechanism starts
with a **dropped Important enqueue**, and `QueueDMATransfer` returns carry-set from three
places, not one: `.split_reject` (the subject), `.full` (an ordinary full queue, charged to
`DMA_Overflow_Count`) and `.byte_capped` (`Dbg_DMA_Enq_Capped`). Measuring only the first
would have answered a narrower question than the one asked. **All three are zero.**

## What the player was doing

Grounded, animating, and in the frames the owner's report points at. Across the campaign
the player passed through **44 distinct mapping frames**, of which **28 are in the walk/run
tilt block `$01-$30`** — the "rotated slightly" frames — including all of
`$01 $02 $03 $04 $05 $06 $07 $08 $09 $0A $0D $0F $12 $18 $1F $20 $21 $22 $23 $24 $27 $29
$2A $2B $2C $2E $2F $30`. Every one of the nine OJZ sections `(0,0)` through `(2,2)` was
visited. Phases: long right run with jumps, long left run, reversal whiplash at both
internal X seams, anchored play at all ten surveyed ground spots, a direction-flip shuttle,
a debug-fly sweep of the grid, and a final grounded right run.

## Did the control move? No — and that is the finding, not a hole

`ram.emp`'s own reading rule: a zero in the Important cells means "Important never
straddled" **only** while `Dbg_DMA_Straddle_All` is non-zero; otherwise it means "nothing
straddled at all, which is also what a broken instrument reads like."

The control did **not** move in play. Three independent pieces of evidence say that is the
correct reading rather than a dead instrument:

1. **The counter writes are in the ROM image**, located by opcode:
   `$1EB2` / `$1EBC` / `$1F10` `addq.w #1,(xxx).w` in `dma_queue.emp`'s `.split` and
   `.split_reject`; `$2402` `clr.w` + `$240C` `move.w d0,(xxx).w` in `vblank.emp`'s
   `VInt_Level` fold; `$1E9A` / `$1EA6` for the two adjacent counters. The `if DEBUG == 1`
   blocks compiled in.

2. **Nothing in this act can straddle.** The act's page manifest, read out of the ROM:
   `OJZ_Act_Pool_PageTable` @ `0x17C74`, 11 pages, sources `0x014DB8` … `0x017D4B`. The
   whole pool sits inside **one** 128 KB block, so **no page-in landing in this act can
   cross a DMA-source boundary** — and page-in landings are the largest non-player
   Important consumer, DMAing direct from ROM on the RAW form (`page_in.emp:272-287`). The
   ZX0 form cannot straddle at all: it DMAs from `Art_Staging_Buffer` in work RAM, and
   `$FF0000-$FFFFFF` lies wholly inside one 128 KB block. Meanwhile `tools/dplc_straddle.py`
   reports on every build that the cast's only three straddling DPLC frames — Sonic `$65`,
   Tails `$9F`, Knuckles `$85` — are all **unreachable** through their anim tables.
   The straddle population in ordinary play is therefore **empty by construction**.

3. **A forced control fires.** Writing Sonic's straddling frame `$65` into the player's
   `mapping_frame` and running ONE frame moved `Dbg_DMA_Straddle_All` 0 → 1 **and** the
   Important-only `Dbg_DMA_Straddle_Frame` 0 → 1, with `prev_frame` committing to `$65` —
   and `perform_dplc` commits only after every entry has enqueued (`dplc.emp:214-262`), so
   the whole entry list went in, straddling entry included. This uses the ROM's own data
   and no source change, and runs on a **separate emulator instance** so it cannot touch
   the campaign it vouches for.

## The verdict, and its confidence

**The DPLC starvation path is not what the owner is seeing.** Across representative
grounded play covering the tilt frames, no Important enqueue was dropped by any of the
three drop paths, and `Dbg_DMA_Straddle_Peak` never left 0 against a reserve of 2. A drop
is the *necessary first step* of the stale-`prev_frame` mechanism, so the mechanism did not
fire. `DRAW_SPRITE.NO_PARENT` — the PC in the owner's capture — points at the **sprite
emit**, not the load.

Confidence, split honestly:

- **HIGH** that no drop occurred in this campaign: three counters, 735 polls, 36829 frames,
  and the instrument proven live on the same ROM.
- **HIGH** that no straddle-driven reject is *possible* in OJZ act 1 as built: it is a
  static property of where the art landed, and it is derived from the ROM image itself.
- **MEDIUM** as a statement about the owner's session. He was playing this act, but I drove
  it headlessly with warps and rescue teleports; a human session is not this session.
- **NOT ESTABLISHED**: anything about the sprite emit. This parcel exonerates one candidate;
  it does not name the replacement.

## What could not be exercised, and why

- **Tails and Knuckles.** Their DPLC art is loaded only when they are the active character,
  and nothing in this campaign cycles the roster (`Debug_CharacterHotkey` needs an A press
  *in debug fly*, which the grounded phases never make). Sigil's report that
  `DPLC_Knuckles`' ceiling equals its bar exactly is **untested here**. Note the static
  half is not silent about it: `dplc_straddle` puts Knuckles' peak at **5** slots over
  reachable frames against a bar of 10, and its one straddling frame `$85` unreachable.
- **The 100 % grounded run.** OJZ act 1's built floor is a narrow strip: the live ground
  survey found footing at ten anchors over x 200-2100 and **no floor at all** from x 2200
  to x 5800 at probe height. Held directions run off the world in about two seconds. 62.7 %
  is what the level data allows; the remaining 37 % is jumps and the falls between rescues.
- **A human-shaped input trace.** This is machine play: held directions, periodic jumps,
  seam whiplash, warps.

## Three things measured on the way that are worth more than the parcel

**1. The canonical DEBUG shape boots ALREADY IN DEBUG FLY**, and nothing said so.
`GameState_OJZScroll_Init` arms `CHEAT_DEBUG_FLY` *and* engages free flight, so out of the
box `Player_1` is a camera puck: flat ~15.6 px/frame, `x_vel`/`y_vel` both **zero**, status
pinned at `$08`, and **`mapping_frame` pinned at `$00` with `prev_frame` `$FF` — the player
never animates.** `Perform_DPLC`'s `mapping_frame == prev_frame` early-out then fires every
frame and the player enqueues **nothing**. Any campaign driven from boot without pressing B
measures a machine with the subject system switched off. This is a *second, independent*
defect in the 600-frame RIGHT-hold attempt, on top of the free-fall one already recorded.
One B press hands the player to real physics — measured at spawn: falls 256 → 573, lands,
idles through `$BA-$C0`, then runs right through `$21-$23` with `x_vel` 1536.

**It also means `tools/canopy_gap_exercise.py`'s phases 1-3 and 5-6 drove a non-animating
player.** Harmless for its own subject (the canopy shadow), and recorded here because the
next person to copy that harness for a player-side question will inherit it silently.

**2. Forcing an out-of-range mapping frame stops the machine.** The enqueue completes and
`prev_frame` commits, and then the machine lands in the MD Debugger island (PC `$000C13CC`)
with `Logic_Tick` frozen — something downstream of the queue guards the frame. Which guard
was **not** determined here. Practical consequence: a forced control gets exactly ONE
attempt per machine.

**3. Whether the force is seen is deterministic in the stop frame, not random.**
`reset → 180f → B(2f) → release → 120f → force` fired on six resets out of six; the same
sequence with two extra frames in it missed on six out of six. Combined with (2), this is
how **three full campaigns in a row** reported UNMEASURABLE while the instrument was
perfectly fine — one attempt, wrong offset, machine dead, no second chance. The driver now
gives the control its own instance and steps the settle by one frame per attempt.

An earlier version of the control swept all 256 mapping frames looking for the straddling
set. It started at `$00`, that first force stopped the machine, and it then reported that
**nothing straddles** — a confident wrong answer manufactured entirely by the control's own
side effect. That sweep is deleted, and the reason is written where it was.
