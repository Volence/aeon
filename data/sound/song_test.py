#!/usr/bin/env python3
"""data/sound/song_test.py — demo song (Music format v0).

Authors a SongDesc and emits data/sound/song_test.asm (label Song_Test) via the
song_packer. Run from the repo root:
    python3 data/sound/song_test.py

This is a *demo* (replacing the original atonal bring-up test pattern): a short,
recognizable, in-tune tune — the "Ode to Joy" A-theme — arranged for three voices
(FM lead melody + FM bass + PSG parallel-thirds harmony) so the engine can be
heard playing actual music. The DAC and PSG-noise channels are intentionally
OMITTED here: the placeholder DAC sample (the 1B test "blip") LOOPS forever once
triggered, so it drones rather than plays a drum, and the noise channel just
buzzes — both are proven working in the 1C verification but are left out for a
pleasant demo. Real drum samples + percussion are deferred content.

Pitch index = MIDI note - 12 (semitone 0 = C0). So C4(MIDI60)=48, A4(MIDI69)=57.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "tools")))

from song_packer import (  # noqa: E402
    SongDesc, ChannelDesc, write_asm,
    SetDur, Rest, Note, Vol, Patch, NoteDur, LoopPoint, Jump,
    CHROUTE_FM1, CHROUTE_FM2, CHROUTE_PSG1,
)

# --- pitch indices (index = MIDI - 12) ---
C4, D4, E4, F4, G4 = 48, 50, 52, 53, 55
A3, B3 = 45, 47
C2, G2 = 24, 31

PATCH_BASS, PATCH_LEAD = 0, 1   # enum in data/sound/fm_patches.inc

# Note lengths in ticks. tempo $80 -> N=512 -> period 18.773us*(1024-512) =
# 9611us -> ~104 ticks/sec, so a quarter note = 52 ticks = 0.5s = 120 BPM.
Q, H = 52, 104   # quarter, half (both <= 127, the SetDur/NoteDur max)

# Ode to Joy A-theme (16 notes): E E F G | G F E D | C C D E | E D D(half).
MELODY = [E4, E4, F4, G4, G4, F4, E4, D4, C4, C4, D4, E4, E4, D4]   # 14 quarters
# ...then E(q) D(q) D(half) closes the phrase (the last D held).

# Parallel diatonic thirds below the melody (C major), same rhythm — a sweet,
# consonant harmony: E->C, F->D, G->E, D->B3, C->A3.
THIRDS = [C4, C4, D4, E4, E4, D4, C4, B3, A3, A3, B3, C4, C4, B3]   # 14 quarters
# ...closing C(q) B3(q) B3(half) under the melody's E D D.


def build_song() -> SongDesc:
    return SongDesc(tempo=0x80, channels=[
        # FM1 — LEAD, the melody.
        ChannelDesc(CHROUTE_FM1, [
            Patch(PATCH_LEAD), Vol(95), SetDur(Q),
            LoopPoint(),
            *[Note(n) for n in MELODY],
            Note(E4), Note(D4), NoteDur(D4, H),   # E D D(held)
            Jump(),
        ]),
        # FM2 — BASS, root notes (half notes): I-I-I-V-I-I-V-I under the theme.
        ChannelDesc(CHROUTE_FM2, [
            Patch(PATCH_BASS), Vol(85), SetDur(H),
            LoopPoint(),
            Note(C2), Note(C2),     # bar 1
            Note(C2), Note(G2),     # bar 2
            Note(C2), Note(C2),     # bar 3
            Note(G2), Note(C2),     # bar 4 (V -> I cadence)
            Jump(),
        ]),
        # PSG1 — soft parallel-thirds harmony under the melody.
        ChannelDesc(CHROUTE_PSG1, [
            Vol(48), SetDur(Q),
            LoopPoint(),
            *[Note(n) for n in THIRDS],
            Note(C4), Note(B3), NoteDur(B3, H),    # under E D D
            Jump(),
        ]),
    ])


def main():
    out_path = os.path.join(_HERE, "song_test.asm")
    write_asm(build_song(), "Song_Test", out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
