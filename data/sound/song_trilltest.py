#!/usr/bin/env python3
"""data/sound/song_trilltest.py — Phase 3 Task 4 SCRATCH trill/arp-verification song.

Authors a one-FM-channel song that emits MULTI-POINT MEV_PITCHENV notes so the
ModUpdate `.multipoint` path can be runtime-verified. A multi-point note cycles
its pitch points ONCE PER ~59 Hz frame (the built-in trill/arp), so the FM1
frequency alternates frame-by-frame between the points while the note is held.

Two phrases, looping:
  * count=2 whole-step TRILL: indices [$30, $32] (C<->D, block1), held ~1 s. The
    cursor alternates 0,1,0,1,... so the rendered pitch toggles every frame:
        idx $30 = C (block1) -> $A4 = $0C, $A0 = $00
        idx $32 = D (block1) -> $A4 = $0C, $A0 = $7D
    First frame sounds $30 (cursor 0 on the arm frame), then $32, $30, $32, ...
  * count=3 major-triad ARP: indices [$24, $28, $2B] (C-E-G, block0), held ~1 s.
    The cursor cycles 0,1,2,0,1,2,... so the rendered pitch steps every frame:
        idx $24 = C (block0) -> $A4 = $04, $A0 = $00
        idx $28 = E (block0) -> $A4 = $05, $A0 = $0A
        idx $2B = G (block0) -> $A4 = $05, $A0 = $FE
    First frame sounds $24 (cursor 0 on the arm frame), then $28, $2B, $24, ...

All A4/A0 values above are from the engine-default Zyrinx Moving-Trucks 132-entry
fnum table (data/sound/movingtrucks_pitchtable.asm; pitchtable_ptr=0). sc_transpose
is 0 (loader inits it via the seq clear), so the rendered index equals the operand
index exactly. The note is HELD for ~1 s via the channel default duration, but the
HOLD only paces how long before the NEXT MEV_PITCHENV fetches — the trill cycling
is driven by ModUpdate at the frame rate, NOT by event-ticks.

This is a TASK-4 scratch/verification asset (not a real song): the DEBUG boot is
temporarily pointed at SONG_TRILLTEST so the controller can confirm the per-frame
pitch alternation in BlastEm. Revert the boot to SONG_TEST after verification.

Run from the repo root:
    python3 data/sound/song_trilltest.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "tools")))

from song_packer import (  # noqa: E402
    SongDesc, ChannelDesc, write_asm,
    SetDur, Vol, Patch, PitchEnv, LoopPoint, Jump,
    CHROUTE_FM1,
)

PATCH_LEAD = 1   # enum in data/sound/fm_patches.inc (audible voice)

# Per-frame frame clock is ~59.06 Hz; with TEMPO_BASE=16 the event-tick rate IS
# the frame rate, so ~59 ticks ~= 1 s of hold per multi-point note. The hold sets
# how long the SAME multi-point note keeps trilling before the next PitchEnv.
TEMPO_BASE = 16
HOLD = 59        # ~1 s at 59.06 Hz

# count=2 whole-step trill (C<->D, block1) and count=3 major-triad arp (C-E-G).
TRILL_POINTS = [0x30, 0x32]
ARP_POINTS = [0x24, 0x28, 0x2B]


def build_song() -> SongDesc:
    return SongDesc(tempo=0x80, tempo_base=TEMPO_BASE, channels=[
        # FM1 — the only voice: a held count=2 trill, then a held count=3 arp,
        # looping. Each multi-point note re-articulates its points per FRAME.
        ChannelDesc(CHROUTE_FM1, [
            Patch(PATCH_LEAD), Vol(110), SetDur(HOLD),
            LoopPoint(),
            PitchEnv(TRILL_POINTS),
            PitchEnv(ARP_POINTS),
            Jump(),
        ]),
    ])


def main():
    out_path = os.path.join(_HERE, "song_trilltest.asm")
    write_asm(build_song(), "Song_TrillTest", out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
