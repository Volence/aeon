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

# --- Phase 3 frame-model tempo_base + note durations ----------------------
# Phase 3 replaces the per-song Timer-A tempo with a FIXED frame clock
# (SND_FRAME_HZ = 59 -> Timer-A N = 122 -> period 16.93ms -> ~59.06 frames/sec)
# plus a per-channel tempo accumulator: each frame `tempo_accum -= 16`, and on a
# BORROW `tempo_accum += tempo_base` and ONE event-tick runs (single tick per
# frame — the engine does not catch up multiple ticks in one frame). For the
# accumulator to stay BOUNDED, ticks/frame = 16/tempo_base must be <= 1, i.e.
# tempo_base >= 16; tempo_base < 16 would demand >1 tick/frame and drift. So:
#   EVENT-TICK rate = frame_rate * 16 / tempo_base,   with tempo_base >= 16,
#   and the MAXIMUM event rate is the frame rate itself (tempo_base = 16).
#
# The 1C song ran at ~104 event-ticks/sec (Timer-A tempo $80) — ABOVE the 59.06 Hz
# frame cap, so it cannot be reproduced tick-for-tick. We instead preserve the
# WALL-CLOCK musical tempo by running the per-channel clock at the FULL frame rate
# (TEMPO_BASE = 16 -> 59.06 event-ticks/sec, the max) and RESCALING the note
# durations by the rate ratio 59.06/104.05 = 0.5676:
#   1C quarter = 52 ticks @ 104.05 Hz = 0.500 s (120 BPM)
#   P3 quarter = round(52 * 0.5676) = 30 ticks @ 59.06 Hz = 0.508 s (118 BPM)
#   1C half    = 104 ticks                -> P3 half = 60 ticks @ 59.06 = 1.016 s
# So the tune plays at the same pitch/rhythm and ~118 BPM (within ~1.5% of the
# original 120 BPM). Q/H stay <= 127 (the SetDur/NoteDur max).
TEMPO_BASE = 16
Q, H = 30, 60   # quarter, half (rescaled for the 59.06 Hz frame clock)

# Ode to Joy A-theme (16 notes): E E F G | G F E D | C C D E | E D D(half).
MELODY = [E4, E4, F4, G4, G4, F4, E4, D4, C4, C4, D4, E4, E4, D4]   # 14 quarters
# ...then E(q) D(q) D(half) closes the phrase (the last D held).

# Parallel diatonic thirds below the melody (C major), same rhythm — a sweet,
# consonant harmony: E->C, F->D, G->E, D->B3, C->A3.
THIRDS = [C4, C4, D4, E4, E4, D4, C4, B3, A3, A3, B3, C4, C4, B3]   # 14 quarters
# ...closing C(q) B3(q) B3(half) under the melody's E D D.


def build_song() -> SongDesc:
    return SongDesc(tempo=0x80, tempo_base=TEMPO_BASE, channels=[
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
