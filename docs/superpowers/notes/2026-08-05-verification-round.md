# Emulator verification round — BUG-005 band-cap probe + A2 two-SFX — 2026-08-05

Foreground oracle session on the post-objtest-gate DEBUG ROM (crc F44EAAF7,
loaded-ROM byte-verified before every probe). Third leg of the overnight
backlog run (after the defect batch and the objtest gate).

## BUG-005 — the `.band_limit_pop` probe (the named first-look site)

The band-cap path fires only past MAX_VDP_SPRITES (80) emitted pieces, which no
current scene reaches (~45 under the object-test soak). Probed by FORCING it:
a file-level probe ROM (never committed) patched the `.object_loop` cap compare
`cmpi.w #80,d5` (ROM offset 0x3460, verified against the .lst) to #12.

- Breakpoint at `.band_limit_pop` (0x36D6): **fires** under the object-test
  scene — the path is genuinely exercised, not skipped.
- 25 s soak with the cap firing EVERY frame: `Sprites_Rendered` pinned at 12,
  the chain-walk assert net (link-path length == emitted count, in-frame at
  `.done`) **silent throughout**, frame shows exactly 12 coherent sprites —
  no ghost, no stray pieces.

**Verdict: the a4/d5-skew class BUG-005 named at this path does NOT reproduce**
under thousands of cap events with the net armed. The suspect is downgraded;
BUG-005 stays OPEN-INSTRUMENTED (the original one-frame artifact remains
unexplained and unreproduced).

## BUG-005 — replay screenshot burst (pose transitions + ring emission)

The OJZ fixture replay (jumps, rolls, ring collection — the ring shows
jump/roll SFX ids enqueued during the run) executed with the net armed;
7 screenshots sampled through the motion phase. Every frame carries a single
coherent Sonic; no duplicate head, no stray piece. `Replay_Done = $FF`, no
desync, no trap. (Screenshots are press-frame nondeterministic per the
capture-drift note — a burst is evidence of absence-at-sampled-frames, not
proof; the standing DEBUG net remains the real trap.)

## A2 — two SFX in one frame (live delivery re-check)

DEFERRED_WORK already records A2 as DISCHARGED; this is extra live evidence on
the current build. With the emulator paused, two DISTINCT ids ($36 skid + $B6
dash) were enqueued into `Sfx_Ring_Buf[4..5]` and `Sfx_Ring_Wr` bumped 4→6 in
the same frame. After resume: `Rd == Wr == 6`. `Sound_DrainSfxRing` advances
`Rd` only after the Z80 clears the previous request, so both ids were posted
AND consumed — the exact frame shape the 1-byte mailbox used to lose is
lossless through the 8-deep ring.

## Round verdict

All three targets green: the band-cap path holds its invariants under forced
fire, the replay pose-transition sweep is ghost-free, and two-in-one-frame SFX
delivery is lossless. No new defects found; no code changed.
