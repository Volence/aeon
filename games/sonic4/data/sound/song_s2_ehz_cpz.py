#!/usr/bin/env python3
"""data/sound/song_s2_ehz_cpz.py — Sonic 2 Emerald Hill + Chemical Plant import
(S2CLIP-REGION-MUSIC: the converter's S2 mode + its declared tables).

Converts the two Sonic 2 songs straight from s2disasm's smps2asm source through
tools/smps_import.py, whose S2 mode (SourceDriver 2, read from each song's own
`smpsHeaderStartSong 2`) applies the S2 -> S3K rules s2disasm's _smps2asm_inc.asm
defines and parses each song's own voice bank:

  * games/sonic4/data/sound/song_s2_ehz.bin + s2_ehz_patches.bin
  * games/sonic4/data/sound/song_s2_cpz.bin + s2_cpz_patches.bin

Run from the repo root:
    python3 games/sonic4/data/sound/song_s2_ehz_cpz.py

THE OUTPUT IS COMMITTED AND THE BUILD EMBEDS IT (S2CLIP-REGION-MUSIC step 4), the HCZ2
convention: games/sonic4/data/sound/mt_bank.emp embeds the four .bin files as
SONG_S2_EHZ / SONG_S2_CPZ (games/sonic4/config/sound_ids.emp) in every sound-on shape,
and the build never re-runs this script. A regeneration therefore MOVES ROM BYTES;
tools/test_smps_import.py holds the committed files equal to a fresh run, so an edit
to the converter or its tables that changes either song fails there until the files
are regenerated and committed. (Until step 4 this wrote to tools/generated/s2_music/,
which no build input named.)

Both songs reference S2 PSG envelopes (fTone_NN) and S2 drum notes (dKick,
dSnare, and for EHZ dMidTom/dFloorTom). Neither resolves by number: S2's envelope
bodies are not the engine's same-numbered S3K ones, and the engine has no S2 drum
samples. So the converter resolves them ONLY through its declared tables
(smps_import.S2_FTONE_MAP / S2_DAC_MAP) and refuses any reference they do not
name; on a refusal this script prints every missing name and exits 1, writing
nothing. Steps 2 and 3 of the plan (docs/DEFERRED_WORK.md, S2CLIP-REGION-MUSIC)
filled the tables: the fTones point at Sonic 2's own envelopes, imported as engine
ids $41..$4B (tools/gen_sound_tables.py), and the drums at the S3K kick, snare and
toms (owner ruling S2CLIP-MUSIC-DRUMS = s3k-drums). NOTHING HAS BEEN LISTENED TO.

`generate(out_dir, ftone_map=..., dac_map=...)` takes explicit tables, which is
how tools/test_smps_import.py exercises the writing path.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "tools"))

from suite_paths import require_suite_path                      # noqa: E402
from song_packer import pack_song                               # noqa: E402
from smps_import import (                                       # noqa: E402
    S2Refusal, build_patch_remap, convert_song, pack_song_patch_table,
    song_used_voice_ids,
)

# (output stem, s2disasm source file)
SONGS = (
    ("ehz", "82 - EHZ.asm"),
    ("cpz", "8E - CPZ.asm"),
)

OUT_DIR = _HERE


def _convert(stem, fname, ftone_map, dac_map):
    path = require_suite_path("s2disasm", "sound", "music", fname,
                              what="the Sonic 2 %s song source" % stem.upper())
    with open(path) as f:
        src = f.readlines()
    used = song_used_voice_ids(src)
    song = convert_song(src, None, build_patch_remap(used),
                        dac_map=dac_map, ftone_map=ftone_map)
    return pack_song(song), pack_song_patch_table(src, used)


def generate(out_dir=OUT_DIR, ftone_map=None, dac_map=None):
    """Convert both songs, then write them. Returns [(path, nbytes), ...].
    ftone_map / dac_map None = the converter's declared tables. Every song
    is converted BEFORE any file is written, so a refusal leaves out_dir untouched."""
    blobs = []
    refusals = []
    for stem, fname in SONGS:
        try:
            blobs.append((stem,) + _convert(stem, fname, ftone_map, dac_map))
        except S2Refusal as e:
            refusals.append("%s (%s): %s" % (stem.upper(), fname, e))
    if refusals:
        raise S2Refusal("\n".join(refusals))
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for stem, song_blob, patch_blob in blobs:
        for name, blob in (("song_s2_%s.bin" % stem, song_blob),
                           ("s2_%s_patches.bin" % stem, patch_blob)):
            p = os.path.join(out_dir, name)
            with open(p, "wb") as f:
                f.write(blob)
            written.append((p, len(blob)))
    return written


def main():
    try:
        written = generate()
    except S2Refusal as e:
        print("song_s2_ehz_cpz: REFUSED, nothing written:\n%s" % e, file=sys.stderr)
        return 1
    for p, n in written:
        print("wrote %s (%d bytes)" % (p, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
