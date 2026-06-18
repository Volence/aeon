#!/usr/bin/env python3
"""data/sound/song_pantest.py — Phase 3 Task 6 SCRATCH pan + op-bias verification.

Authors a one-FM-channel song that exercises MEV_PAN ($E4) and MEV_OPBIAS ($E9) so
the ModUpdate write-on-change pan render and the Fm_PatchLoad per-operator TL bias
can be runtime-verified. The phrase loops:

  PHASE 1 — hard-LEFT (~1 s): Pan($80) then a held note. ModUpdate sees sc_pan
    change 0 -> $80 and writes $B4+ch = $80 (bit7 = Left output enable only). The
    note plays only out the LEFT speaker.
        Expected $B4 (FM1, part I ch0) = $80.

  PHASE 2 — hard-RIGHT (~1 s): Pan($40) then the SAME note. ModUpdate sees sc_pan
    change $80 -> $40 and writes $B4 = $40 (bit6 = Right output enable only). The
    note plays only out the RIGHT speaker.
        Expected $B4 = $40.

  PHASE 3 — op-bias timbre shift (~1 s): Pan($C0) (recenter, both speakers) then
    OpBias(op=0, val=$30) then Patch(PATCH_LEAD) (re-load so the bias latches) then
    a held note. OpBias adds $30 attenuation to operator 0 (S1, a MODULATOR of the
    alg-0 voice), so the $40-group TL for S1 becomes patch_TL[S1] + $30. PATCH_LEAD
    S1 TL = $38, so the biased S1 TL = $38 + $30 = $68. A quieter modulator = less
    FM modulation = an audibly DARKER / mellower timbre (and the carrier loudness is
    unchanged because Fm_SetVolume re-applies only the carrier TL after the load).
        Expected $B4 = $C0 (recentered).
        Expected reg $40 (FM1, op 0 = reg offset +0 = S1) = $68 after the biased
        patch load (= PATCH_LEAD S1 TL $38 + bias $30), vs $38 with no bias.

PAN / $B4 NOTES
---------------
YM2612 $B4: bit7 = LEFT-output enable, bit6 = RIGHT-output enable, bits5-4 = AMS,
bits2-0 = FMS. So $80 = LEFT only, $40 = RIGHT only, $C0 = both/center. PATCH_LEAD's
own $B4 is $C0 (both); the per-frame pan render OVERRIDES it write-on-change. A held
pan (sc_pan == sc_last_pan) writes nothing — so $B4 is written exactly ONCE per phase
(on the frame sc_pan changes), NOT every frame.

OP-BIAS NOTES
-------------
Per /tmp/zyrinx_re_modulation.md §6 the op-mod is a per-note additive TL bias LATCHED
at key-on / patch load and re-asserted as a CONSTANT (not a swept envelope). So
MEV_OPBIAS only changes sc_opbias[op]; the bias is APPLIED when Fm_PatchLoad uploads
the $40-group (next Patch / note). This song therefore re-issues Patch(PATCH_LEAD)
after the OpBias so the bias takes effect immediately. Biasing a MODULATOR (op 0/1/2
of the alg-0 voice) changes timbre; biasing the carrier (op 3) would be overwritten by
the volume re-apply, so we bias a modulator for an audible, persistent effect.

This is a TASK-6 scratch/verification asset (not a real song): the DEBUG boot is
temporarily pointed at SONG_PANTEST. Revert the boot to SONG_TEST after verification.

Run from the repo root:
    python3 data/sound/song_pantest.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "tools")))

from song_packer import (  # noqa: E402
    SongDesc, ChannelDesc, write_asm,
    SetDur, Vol, Patch, PitchEnv, Pan, OpBias, LoopPoint, Jump,
    CHROUTE_FM1,
)

PATCH_LEAD = 1   # enum in data/sound/fm_patches.inc (audible alg-0 voice)

# Per-frame frame clock is ~59.06 Hz; with TEMPO_BASE=16 the event-tick rate IS the
# frame rate, so ~59 ticks ~= 1 s per held note.
TEMPO_BASE = 16
HOLD = 59        # ~1 s at 59.06 Hz

# A clear mid-register note to hear the pan/timbre on. idx $30 = C (block1) in the
# engine-default Zyrinx Moving-Trucks 132-entry fnum table -> $A4 = $0C, $A0 = $00.
NOTE_IDX = 0x30

# Op-bias: add $30 attenuation to operator 0 (S1, a modulator of the alg-0 voice).
OPBIAS_OP = 0
OPBIAS_VAL = 0x30


def build_song() -> SongDesc:
    return SongDesc(tempo=0x80, tempo_base=TEMPO_BASE, channels=[
        # FM1 — the only voice. Patch + Vol first (packer requires it before the
        # first note), then a looping LEFT / RIGHT / op-bias phrase.
        ChannelDesc(CHROUTE_FM1, [
            Patch(PATCH_LEAD), Vol(110), SetDur(HOLD),
            LoopPoint(),
            # PHASE 1 — hard-LEFT
            Pan(Pan.PAN_LEFT),                 # $B4 -> $80 (write-on-change)
            PitchEnv(NOTE_IDX),
            # PHASE 2 — hard-RIGHT
            Pan(Pan.PAN_RIGHT),                # $B4 -> $40
            PitchEnv(NOTE_IDX),
            # PHASE 3 — recenter + op-bias timbre shift
            Pan(Pan.PAN_CENTER),               # $B4 -> $C0
            OpBias(OPBIAS_OP, OPBIAS_VAL),     # sc_opbias[0] = $30 (latches at next load)
            Patch(PATCH_LEAD),                 # re-load patch -> applies the bias ($40 = $68)
            PitchEnv(NOTE_IDX),
            Jump(),
        ]),
    ])


def main():
    out_path = os.path.join(_HERE, "song_pantest.asm")
    write_asm(build_song(), "Song_PanTest", out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
