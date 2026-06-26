#!/usr/bin/env python3
"""data/sound/song_hcz2.py — HCZ2 (S3K Hydrocity Zone Act 2) import (Phase 7).

Generates BOTH the song stream and its FM patch bank from the original S3K SMPS
source via the verified SMPS converter (tools/smps_import.py):

  * data/sound/song_hcz2.asm    — Song_HCZ2 (the packed music-format-v0 blob).
  * data/sound/hcz2_patches.asm — HCZ2_Patches (4x26-byte FmPatch records).

Run from the repo root:
    python3 data/sound/song_hcz2.py

WHAT IT IS — a real, faithful sequencer playback of HCZ2 (NOT a register replay):
  * STREAM song (SH_F_STREAM): the command streams + the patch bank are read
    DIRECTLY through the banked $8000 window every sequencer frame, exactly like
    Moving Trucks. So Song_HCZ2 + HCZ2_Patches MUST live in the SAME 32KB bank
    (asserted in main.asm) — one SetBank covers all of HCZ2's ROM reads.
  * 9 channels: DAC + FM1..FM5 + PSG1..PSG3 (HCZ2 uses 5 FM + 3 PSG; FM6 is free).
  * DAC drums use the S3K drum-sample remap (HCZ2_DAC_REMAP): the in-body
    1-based S3K DAC ids are rewritten to our DacSampleTable ids 5..10
    (s3k_kick/snare/toms/floortom), whose payloads ship in dac_samples.asm.
  * FM voices: HCZ2 plays four S3K Universal Voice Bank voices ($03,$06,$0E,$15).
    emit_patch_table() converts them through the SAME verified SFX voice converter
    used everywhere else, and patch_remap rewrites each in-body smpsSetvoice id to
    the dense 0-based HCZ2_Patches index ({$03:0,$06:1,$0E:2,$15:3}).
  * Engine-default pitch table (pitchtable=None -> pitchtable_ptr=0). A per-song
    HCZ2 pitch table is a later conditional phase; for now the engine-default
    chromatic FmPitchTableZ is used for note frequency lookup.

DEBUG-only (registered under ifdef __DEBUG__ in song_table.asm).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "..", "tools")))

from song_packer import write_asm                              # noqa: E402
from smps_import import (                                       # noqa: E402
    convert_song, emit_patch_table,
    HCZ2_DAC_REMAP, S3K_Z80_DRIVER,
)

# The S3K source for HCZ2 (Hydrocity Zone Act 2), straight from the skdisasm.
HCZ2_SRC = "/home/volence/sonic_hacks/skdisasm/Sound/Music/HCZ2.asm"

# HCZ2's four in-body smpsSetvoice ids -> dense 0-based HCZ2_Patches indices.
# (Same mapping build_patch_remap([0x03,0x06,0x0E,0x15]) yields; spelled out for
# clarity at the call site.)
HCZ2_PATCH_REMAP = {0x03: 0, 0x06: 1, 0x0E: 2, 0x15: 3}
HCZ2_USED_VOICE_IDS = [0x03, 0x06, 0x0E, 0x15]


def main():
    with open(HCZ2_SRC) as f:
        src_lines = f.readlines()

    # Engine-default pitch table for now (pitchtable=None / offset 0).
    song = convert_song(src_lines,
                        dac_remap=HCZ2_DAC_REMAP,
                        patch_remap=HCZ2_PATCH_REMAP)

    song_path = os.path.join(_HERE, "song_hcz2.asm")
    write_asm(song, "Song_HCZ2", song_path)
    print("wrote", song_path)

    patch_asm, remap = emit_patch_table(S3K_Z80_DRIVER,
                                        HCZ2_USED_VOICE_IDS,
                                        "HCZ2_Patches")
    patch_path = os.path.join(_HERE, "hcz2_patches.asm")
    with open(patch_path, "w") as f:
        f.write(patch_asm)
    print("wrote", patch_path)
    print("patch_remap:", remap)


if __name__ == "__main__":
    main()
