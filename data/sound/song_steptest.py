#!/usr/bin/env python3
"""data/sound/song_steptest.py — Phase 3 Task 5 SCRATCH voice-stepping verification.

Authors a one-FM-channel song that exercises MEV_REGDELTA ($EA) — the mid-note
minimal-register-delta voice-stepping primitive — and the RE-KEY RULE, so both can
be runtime-verified in BlastEm/Exodus.

THE VOICE-STEP (the Moving-Trucks signature)
--------------------------------------------
A single held note whose TIMBRE is swept by writing only the register(s) that change
between voice steps. Verified against the real Zyrinx lead voice-step ($9C->$A0):
it differs by EXACTLY ONE byte — operator S1's TL (the $40 group, op0) — so a rapid
step is ONE MEV_REGDELTA with a single (reg_sel(RD_GROUP_TL, 0), tl) pair. We do NOT
do a full ~26-register patch reload per step (untenable per frame; see
tools/cycle_budget_phase3.md). The lead's voice numbers $9C..$A0 map to monotonically
brighter S1-TL values; we mimic that with the TL sweep below.

PATCH_LEAD is algorithm 0: operator 0 (array index 0 = reg offset +0 = S1) is a
MODULATOR (its patch TL = $38); the carrier is S4 (op array index 3, TL 0). Sweeping
op0's TL down (brighter modulator = more FM = brighter timbre) and back is an audible
continuous timbre sweep of the held note — exactly the Zyrinx voice-step effect.

THE PHRASE (looping)
--------------------
  Patch(PATCH_LEAD), Vol, SetDur(WAIT=1):
  LoopPoint:
    PitchEnv([NOTE_IDX])   ; key the note ONCE (first time); the engine re-key rule
                           ; makes every SUBSEQUENT same-index PitchEnv a HELD no-attack
                           ; (no key-off->on, no fresh EG attack) — so the whole sweep
                           ; below is ONE key-on, no re-attacks.
    for tl in TL_SWEEP:    ; [$38, $30, $28, $20, $28, $30]  (S1-TL, op0)
        RegDelta.tl(0, tl) ; write reg $40 (FM1 op0) = tl IMMEDIATELY (mid-note, no key)
        PitchEnv([NOTE_IDX]) ; WAIT 1 event-tick while HELD (same idx -> no re-attack)
    Jump  -> LoopPoint

Each `PitchEnv([NOTE_IDX])` after the first is the engine's faithful "WAIT 1 while
keyed" (the Zyrinx `PITCH_1 $40 ; VOICE ; WAIT 1` voice-step idiom): it advances one
event-tick (paced by SetDur(WAIT)) and, because the pitch index is UNCHANGED, the
re-key rule renders it as a held note with NO new key-on. The RegDelta executes
zero-tick just before each hold, so reg $40 steps once per event-tick.

EXPECTED RUNTIME BEHAVIOR (what the controller verifies via VGM + emulator_z80_read)
------------------------------------------------------------------------------------
  * reg $40 (FM1, op0 = S1, part I ch0) sweeps through, in order, per event-tick:
        $38 -> $30 -> $28 -> $20 -> $28 -> $30  (then loops)
    These are the exact MEV_REGDELTA values; a continuous timbre sweep on the held note.
  * EXACTLY ONE key-on ($28 = $F0) for the held note across the WHOLE sweep — NO extra
    key-ons / re-attacks while the TL sweeps (the re-key rule: re-articulate ONLY on a
    PITCH change; same-index PitchEnv = held). The first loop iteration keys once
    (sc_note was the $FF init sentinel, so the opening PitchEnv differs and attacks);
    on loop-back the index is still NOTE_IDX, so NO new attack — it just keeps holding.
    So after warm-up the sweep produces ZERO key-ons; the channel sustains.
  * sc_note (emulator_z80_read of the SeqChannel) holds NOTE_IDX throughout; SCF_KEYED
    stays set; sc_patch stays PATCH_LEAD (MEV_PATCH is NOT re-issued during the sweep,
    so there is NO full patch reload — only the single $40 byte changes per step).

NOTE_IDX $30 = C (block1) in the engine-default Zyrinx Moving-Trucks 132-entry fnum
table (pitchtable_ptr=0) -> $A4 = $0C, $A0 = $00. sc_transpose = 0.

This is a TASK-5 scratch/verification asset (not a real song): the DEBUG boot is
temporarily pointed at SONG_STEPTEST. Revert the boot to SONG_TEST after verification.

Run from the repo root:
    python3 data/sound/song_steptest.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "tools")))

from song_packer import (  # noqa: E402
    SongDesc, ChannelDesc, write_asm,
    SetDur, Vol, Patch, PitchEnv, RegDelta, LoopPoint, Jump,
    CHROUTE_FM1,
)

PATCH_LEAD = 1   # enum in data/sound/fm_patches.inc (audible alg-0 voice)

# Per-frame frame clock is ~59.06 Hz; with TEMPO_BASE=16 the event-tick rate IS the
# frame rate, so WAIT=1 event-tick = 1 frame (~17 ms) per voice-step. The sweep is
# rapid (one TL write per frame), mimicking the Zyrinx lead's per-tick voice swaps.
TEMPO_BASE = 16
WAIT = 1         # hold ONE event-tick between sweep steps (the Zyrinx "WAIT 1")

# A clear mid-register held note. idx $30 = C (block1): $A4 = $0C, $A0 = $00.
NOTE_IDX = 0x30

# Operator S1's TL sweep (op0, the $40 group). $38 = PATCH_LEAD's S1 patch TL
# (the natural starting point); brighten down to $20, then back. Mimics the lead
# voice-step $9C->$A0 (monotonically brighter), as a single $40-byte delta per step.
TL_SWEEP = [0x38, 0x30, 0x28, 0x20, 0x28, 0x30]


def build_song() -> SongDesc:
    events = [Patch(PATCH_LEAD), Vol(110), SetDur(WAIT), LoopPoint(),
              # Key the held note ONCE (the first PitchEnv attacks; same-index
              # re-arms below are held no-attacks per the re-key rule).
              PitchEnv(NOTE_IDX)]
    for tl in TL_SWEEP:
        events.append(RegDelta.tl(0, tl))    # reg $40 (op0) = tl, mid-note, no re-key
        events.append(PitchEnv(NOTE_IDX))    # WAIT 1 tick, HELD (same idx -> no attack)
    events.append(Jump())
    return SongDesc(tempo=0x80, tempo_base=TEMPO_BASE, channels=[
        ChannelDesc(CHROUTE_FM1, events),
    ])


def main():
    out_path = os.path.join(_HERE, "song_steptest.asm")
    write_asm(build_song(), "Song_StepTest", out_path)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
