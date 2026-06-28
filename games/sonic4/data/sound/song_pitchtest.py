#!/usr/bin/env python3
"""data/sound/song_pitchtest.py — Phase 3 SCRATCH pitch-verification song.

Authors a one-FM-channel song that emits a handful of MEV_PITCHENV count=1 notes
at KNOWN absolute indices into the per-song fnum table (the Zyrinx Moving-Trucks
132-entry table, the engine default — pitchtable_ptr=0). Each note is held ~0.5s
and the phrase loops, so a runtime check can confirm the engine keys the EXACT
$A4/$A0 frequency the table says for each index.

This is a TASK-3 scratch/verification asset (not a real song): the DEBUG boot is
temporarily pointed at SONG_PITCHTEST so the controller can compare the
BlastEm-rendered FM1 frequency to the table below. Revert the boot to SONG_TEST
after verification.

Run from the repo root:
    python3 data/sound/song_pitchtest.py

--- INDEX -> EXPECTED ($A4, $A0) (from /tmp/zyrinx_re_timing_pitch.md §2.4) ------
The notes span a couple octaves of C-major-ish anchors so the pitch climb is
audible AND each register write is checkable:

    idx $24  C  (block0, fnum1024)  -> $A4 = $04, $A0 = $00
    idx $28  E  (block0, fnum1290)  -> $A4 = $05, $A0 = $0A
    idx $2B  G  (block0, fnum1534)  -> $A4 = $05, $A0 = $FE
    idx $30  C  (block1, fnum1024)  -> $A4 = $0C, $A0 = $00
    idx $3C  C  (block2, fnum1024)  -> $A4 = $14, $A0 = $00
    idx $48  C  (block3, fnum1024)  -> $A4 = $1C, $A0 = $00

(block = (idx-$24)/12, fnum index = (idx-$24)%12; verify A4=(block<<3)|(fnum>>8),
A0 = fnum & $FF.) sc_transpose is 0 for this channel (loader inits it to 0 via the
seq clear), so the rendered index equals the operand index exactly.
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
# the frame rate, so ~30 ticks ~= 0.5 s per held note.
TEMPO_BASE = 16
HOLD = 30        # ~0.5 s at 59.06 Hz

# Absolute fnum-table indices to verify (see the index->($A4,$A0) map above).
PITCH_INDICES = [0x24, 0x28, 0x2B, 0x30, 0x3C, 0x48]


def build_song() -> SongDesc:
    return SongDesc(tempo=0x80, tempo_base=TEMPO_BASE, channels=[
        # FM1 — the only voice: a climbing run of single-point pitch-envelope
        # notes at the known indices, each held HOLD ticks, looping.
        ChannelDesc(CHROUTE_FM1, [
            Patch(PATCH_LEAD), Vol(110), SetDur(HOLD),
            LoopPoint(),
            *[PitchEnv(idx) for idx in PITCH_INDICES],
            Jump(),
        ]),
    ])


def main():
    out_path = os.path.join(_HERE, "song_pitchtest.asm")
    write_asm(build_song(), "Song_PitchTest", out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
