# T10 verification — portamento resident (2026-07-02)

Code: `0205df1` (B1 resident) + `f0825f1` (B2 MEV_PORTA) + `e878469` (B3 packer) +
`f60cc8a` (docs). Budget $310 → $18E free (386 B — the T2-T4 recovery paying out as
planned). pytest 813+2 (two new packer tests).

## Soak (the original failure mode was a Z80 self-reinit from banked code fetches)

3,000+ frames HCZ2 + SFX presses on the T10 build:
- Z80 PC sampled every 500 frames: always resident ($00D5-$012C hot-loop region),
  never $8xxx/$Cxxx (no banked-window code fetches), never $0000-0002.
- `$0000` reset-vector trap (F3 18 FE) installed for the whole soak: NEVER fired.
- SND_SEQ_ACTIVE=1 throughout; SND_STAT_TICK advancing (wrapping normally).

## Rendered glide (canonical-table linearity)

Live-armed `sc_porta_incr`=$0008 on FM1 during HCZ2 (post-T4 addresses: route 0
incr at $1A2A, route 1 at $1A66): the fnum stream shows an unbroken 163-step sweep
of EXACTLY +8 per frame (548 total +8 steps in 15s) — Porta_Apply running resident
per-frame with uniform stepping, composing cleanly with T6 vibrato (±6 deltas
interleave correctly via the shared sc_last_freq shadow). Uniform fnum steps on the
T7 canonical band = uniform cents within a block; Fm_FnumApplyDelta block-corrects
at band edges (code-verified by the implementer, same routine as detune/vibrato).
The second poked channel's incr was overwritten at its next note-on — correct:
the note-on porta block re-derives incr from the channel porta rate.

## Notes

- T0.3 (banked-code hazard) was already closed by T2/T3's relocations —
  sound_banked_z80.asm and its include were gone before this task; recorded in the
  final commit message.
- No shipped song emits MEV_PORTA yet; the packer + opcode + engine paths are
  fully wired and tested. Authored content lands whenever a song wants it.
