# The DMA split reserve: the reading, and why the zero is a result

Taken 2026-09-03 against `s4.debug.bin` built from `origin/master` at `81b2a719`
(last byte-moving commit `094496ca`; the two commits after it move no bytes).
Emulator reset before each run, so every peak below is a high-water mark over
that run alone.

The booking (`BUG-DMA-SPLIT-RESERVE`) asked whether the two-slot reserve that
holds the queue open for a 128 KB-boundary straddle is big enough. The first
attempt, on 2026-09-02, was **uninterpretable and was not called clean**: the
control counter read 0 after 4,200 frames, and the instrument's own pre-stated
rule says a zero control means the run never exercised a straddle at all.

This one is interpretable, in both halves: the control is still zero, and the
zero is now **predicted** rather than unexplained.

## What was measured

`sizeof(DMAEntry) = 14` and `12 slots = 168 bytes is the wall`, both from the
comment at `engine/system/vblank.emp:246-248` that computes the peak — not from
a nearby pin.

| Run state | `DMA_Peak_Important` | Entries | Of 12 |
|---|---|---|---|
| debug free-flight, 300 frames | `$0E` = 14 B | 1 | 1 |
| dropped into physics, idle | `$38` = 56 B | 4 | 4 |
| + one spindash charge | `$8C` = 140 B | **10** | 10 |

`Dbg_DMA_Straddle_All` = 0, `Dbg_DMA_Straddle_Frame` = 0,
`Dbg_DMA_Straddle_Peak` = 0, on every run.

The reserve is 2 slots = 28 bytes, and it was untouched: 140 + 28 = 168 = the
wall exactly.

**The ladder 1 → 4 → 10 is the control.** It is what makes the zero straddle
count weigh anything: a counter that never moves is indistinguishable from a
counter that cannot move, and this one demonstrably moves under drive. The
spindash step was run in isolation from a fresh reset, so the 10 is attributable
to it rather than to boot or level load — and Spindash is one of the six
animations the static gate names as costing the full 10 slots (its `$8B` frame).

That also explains the earlier attempt's stray "14 bytes = one entry" reading:
14 B is the debug-free-flight figure, so that 4,200-frame run never left debug
fly at all. It was measuring a state with no animation in it.

## Why zero straddles is the predicted result

`tools/dplc_straddle.py` reports exactly one straddling frame per character:
Sonic `$6A`, Tails `$A4`, Knuckles `$8B`. For the only character the game can
actually play, **`$6A` cannot be displayed**:

1. No Sonic animation script names it. The scripts reach `$C4` at most, and
   `$6A` appears in none of them.
2. The only non-script writer of Sonic's `mapping_frame` is `Player_ApplyTilt`
   (`games/sonic4/player/player_common.emp:1108`), which adds a tilt-bank offset
   to the script's frame. It is gated to WALK and RUN alone
   (`cmpi.b #ANIM_RUN` / `bhi .done`) and masks its bank with
   `andi.w #TILT_SETS - 1` to 0..3. So it produces walk `1..8 + 8·d2` (max `$20`)
   and run `$21..$24 + 4·d2` (max `$30`). `$6A` is above both.

So a zero straddle count is what the machine is supposed to produce, and the
reserve is simply never exercised by Sonic.

### The falsification this claim invites, and the result of taking it

The enumeration forbids something specific: **any observed Sonic
`mapping_frame` outside {script frames} ∪ {tilt expansion}**. Every frame
observed under drive fell inside it — `$C4` (LookUp, its held last frame),
`$9C` (Duck, its held last frame), `$86` (Spindash), `$04` and `$02` (Walk).
A frame in the forbidden zone (`$31`-`$85`, where `$6A` lives) would have
refuted the whole argument. None appeared.

## What this does not say

- **It does not clear the reserve for the roster.** Tails' straddling frame
  `$A4` *is* scripted (FlyTired) and Knuckles' `$8B` *is* scripted (Spindash).
  Both become reachable the moment those characters ship. Knuckles cannot be
  reached at all today for an unrelated reason: the debug hotkey's
  `CHAR_KNUCKLES` row is still the Sonic record
  (`games/sonic4/test/ojz_scroll_test.emp`), so Knuckles art never loads.
- **The enumeration is over source scripts, matched by pattern, not over the
  built table.** A ROM-derived enumeration is the stronger form, and is what the
  gate should carry rather than this document.
- **Sampling was one read per action**, not per frame — a watchpoint halts the
  run, so continuous capture was not available. A transient frame could have
  been missed. This is a falsification opportunity taken, not exhaustive
  coverage.

## The consequence worth acting on

`tools/dplc_straddle.py` computes its straddle set over all 224 frames of the
art, **including frames the game cannot display**. Today that overstates. The
sharper problem is the other direction: it cannot tell you when a straddle lands
on a frame that *is* reachable, because it never asks the question.

`BLOCK-STREAM-DEDUP` is booked to move art bases by about 21 KB — four times the
margin the DPLC fix depends on. Moving a base moves which frames straddle. That
is precisely the case that has to be loud, and right now it would be silent.
