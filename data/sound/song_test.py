#!/usr/bin/env python3
"""data/sound/song_test.py — minimal representative test song (Music format v0).

Authors a SongDesc and emits data/sound/song_test.asm (label Song_Test) via the
song_packer. Run from the repo root:
    python3 data/sound/song_test.py

The song just has to pack and build in Task 1 — it exercises every channel kind
and the loop opcodes. Pitch index 57 = A4 (440 Hz) per the FM pitch table.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "tools")))

from song_packer import (  # noqa: E402
    SongDesc, ChannelDesc, write_asm,
    SetDur, Rest, Note, Vol, Patch, Dac, NoteDur, LoopPoint, Jump,
    CHROUTE_FM1, CHROUTE_FM2, CHROUTE_PSG1, CHROUTE_PSGN, CHROUTE_DAC,
)

# A4 = pitch index 57; a small A-minor-ish set of indices for variety.
A4, C5, E5, A5 = 57, 60, 64, 69


def build_song() -> SongDesc:
    # tempo byte = N>>2 (N = tempo<<2). Bigger = faster (period = 18.773us*(1024-N)).
    # 0xC0 -> N=768 -> period (1024-768)*18.773us = 4806us -> ~208 ticks/sec, a
    # musically reasonable rate for this bring-up song (durations 0x08..0x20 ticks).
    return SongDesc(tempo=0xC0, channels=[
        # FM1 — patch 0, melody loop.
        ChannelDesc(CHROUTE_FM1, [
            Patch(0), Vol(100), SetDur(0x10),
            LoopPoint(),
            Note(A4), Note(C5), Note(E5), Rest(),
            Note(A5), Rest(),
            Jump(),
        ]),
        # FM2 — patch 1, slower harmony with an explicit-duration note.
        ChannelDesc(CHROUTE_FM2, [
            Patch(1), Vol(80), SetDur(0x20),
            LoopPoint(),
            Note(A4), Rest(),
            NoteDur(E5, 0x18), Rest(),
            Jump(),
        ]),
        # PSG1 — tone arpeggio.
        ChannelDesc(CHROUTE_PSG1, [
            Vol(90), SetDur(0x08),
            LoopPoint(),
            Note(A5), Note(E5), Note(C5), Note(A4),
            Jump(),
        ]),
        # PSG noise — periodic hit.
        ChannelDesc(CHROUTE_PSGN, [
            Vol(70), SetDur(0x20),
            LoopPoint(),
            Note(0), Rest(),
            Jump(),
        ]),
        # DAC — a couple of sample triggers, looping.
        ChannelDesc(CHROUTE_DAC, [
            SetDur(0x20),
            LoopPoint(),
            Dac(1), Rest(),
            Dac(1), Rest(),
            Jump(),
        ]),
    ])


def main():
    out_path = os.path.join(_HERE, "song_test.asm")
    write_asm(build_song(), "Song_Test", out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
