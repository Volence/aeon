#!/usr/bin/env python3
"""data/sound/song_drumtest.py — DEBUG STREAM DAC-on drum-test song (Layer 5 Task 5.3).

Authors Song_DrumTest and emits data/sound/song_drumtest.asm via the song_packer.
Run from the repo root:
    python3 data/sound/song_drumtest.py

PURPOSE — the integrated proof for the DAC-drum phase's bank brackets (B1-B4) +
the FM6 dedicate gate + the SFX-mid-drum path (B3):

  * It is a STREAM song (SH_F_STREAM): its command streams + patch bank are read
    DIRECTLY through the banked $8000 window every sequencer frame. It is placed
    in the SAME bank as Moving Trucks ($0F) — the only bank that holds the
    co-located engine tables (FmPitchTableZ etc., read window-relative by the FM
    voice writer) — so it reuses the engine-default pitch table (pitchtable_ptr=0)
    and Moving Trucks' FM patch bank (SongPatchTable[id-1] = MovingTrucks_Patches).
    No second copy of the engine tables (those labels are global — re-including
    would collide), and no per-song pitch/patch data of its own.

  * FM6 = DAC (SH_F_FM6_FM CLEAR). When the DAC channel fires $E2, Snd_StartSample
    arms the DAC ($2B=$80, $B6=$C0) and SND_STAT_DAC_ACTIVE=1; the Layer-4 gate in
    Fm_NoteOnFreq then SUPPRESSES the ch6 $28 key-on for the duration of the
    sample (FM6 coasts), and the FM6 key-ons between hits fire normally. The
    FM6 channel below keys eighth notes continuously so this gate is exercised
    every drum (observe the $28 ch6 stream: absent during a sample, present
    between).

  * The DAC channel ($E2 kick/snare on the beat) drives the per-frame song<->sample
    bank swap (B1). The FM1/FM2/PSG1 music must stay correct AFTER each $E2 (a
    bank-swap failure would stream ROM garbage that looks audible) — that is the
    L3 gate. The drum payloads stay in the SEPARATE shared DAC bank ($0E), so the
    song bank ($0F) != the sample bank ($0E): the swap is real, not a no-op.

DEBUG-only (song id 2, registered under ifdef __DEBUG__ in song_table.asm).

Pitch index = MIDI note - 12 (semitone 0 = C0), indexing the engine-default
chromatic FmPitchTableZ. So C4(MIDI60)=48, A4(MIDI69)=57.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "tools")))

from song_packer import (  # noqa: E402
    SongDesc, ChannelDesc, write_asm,
    SetDur, Rest, Note, Vol, Patch, Dac, LoopPoint, Jump,
    CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM6, CHROUTE_PSG1, CHROUTE_DAC,
    SH_F_STREAM,
)

# --- pitch indices (index = MIDI - 12) ---
C3, G3 = 36, 43
C4, D4, E4, G4 = 48, 50, 52, 55
C5 = 60

# --- DacSampleTable ids (engine/z80_sound_driver.asm DacSampleTable) ---
KICK, SNARE = 2, 3              # 1=blip, 2=kick, 3=snare, 4=hat

# --- Moving Trucks' FM patch bank is reused (SongPatchTable[1] = MovingTrucks_Patches).
# Any 0..PATCH_COUNT_MT-1 index is a valid voice; the test gates on bank-swap
# correctness + the FM6 gate, not on a specific timbre.
PATCH_A, PATCH_B, PATCH_C = 0, 1, 2

# Phase 3 frame-model tempo: TEMPO_BASE=16 runs the per-channel clock at the full
# ~59.06 Hz frame rate (the max event-tick rate). Durations are in event ticks.
TEMPO_BASE = 16
E, Q, H = 15, 30, 60           # eighth / quarter / half (~0.25 / 0.5 / 1.0 s)


def build_song() -> SongDesc:
    return SongDesc(tempo=0x80, tempo_base=TEMPO_BASE, flags=SH_F_STREAM, channels=[
        # FM1 — LEAD melody. Proves the bank swap leaves the FM command stream +
        # patch + pitch reads correct AFTER each $E2 (loops a fixed 4-note motif).
        ChannelDesc(CHROUTE_FM1, [
            Patch(PATCH_B), Vol(95), SetDur(Q),
            LoopPoint(),
            Note(C4), Note(E4), Note(G4), Note(E4),
            Jump(),
        ]),
        # FM2 — BASS (half notes).
        ChannelDesc(CHROUTE_FM2, [
            Patch(PATCH_A), Vol(85), SetDur(H),
            LoopPoint(),
            Note(C3), Note(G3),
            Jump(),
        ]),
        # FM6 — the dedicated DAC slot's FM voice. Eighth notes so the Layer-4 ch6
        # key-on gate is exercised every drum: each $28 inside a DAC sample window
        # is suppressed; those between hits fire. (Inaudible — $2B is armed by
        # Snd_StartSample at the first $E2 — so the proof is the $28 ch6 stream.)
        ChannelDesc(CHROUTE_FM6, [
            Patch(PATCH_C), Vol(80), SetDur(E),
            LoopPoint(),
            Note(C5), Note(C5), Note(C5), Note(C5),
            Jump(),
        ]),
        # PSG1 — harmony. Proves the swap doesn't corrupt the PSG stream either.
        ChannelDesc(CHROUTE_PSG1, [
            Vol(48), SetDur(Q),
            LoopPoint(),
            Note(E4), Note(G4), Note(E4), Note(C4),
            Jump(),
        ]),
        # DAC — kick/snare on the beat. The first $E2 fires at tick 0; each $E2
        # arms the DAC and drives the per-frame song<->sample bank swap (B1). The
        # ~1.0 s rest after each hit gives the one-shot sample room to fully play
        # and DC-center-stop (DAC_ACTIVE 0->1->0) before the next trigger.
        ChannelDesc(CHROUTE_DAC, [
            SetDur(H),
            LoopPoint(),
            Dac(KICK), Rest(),
            Dac(SNARE), Rest(),
            Jump(),
        ]),
    ])


def main():
    out_path = os.path.join(_HERE, "song_drumtest.asm")
    write_asm(build_song(), "Song_DrumTest", out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
