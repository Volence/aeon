#!/usr/bin/env python3
"""Do the four remaining zones' Sonic 2 songs go through the SHIPPED S2 importer, and how big are they?

A PROBE for docs/research/2026-09-27-mega-act-woven.md (the owner: "import the four zones'
Sonic 2 songs, via the existing region music"). It calls the same `_convert` the committed
EHZ/CPZ import uses (games/sonic4/data/sound/song_s2_ehz_cpz.py: tools/smps_import.py's S2
mode with its DECLARED fTone and drum tables) on 90 HPZ, 8F WFZ, 84 OOZ, 85 MTZ, and prints
each song's packed size or the converter's refusal. It writes NOTHING (the blobs are measured
in memory). EHZ and CPZ are re-converted as the control: they must match the committed .bin
sizes.

    python3 music_probe.py
"""
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "games/sonic4/data/sound"))
sys.path.insert(0, str(REPO / "tools"))
import song_s2_ehz_cpz as S                     # noqa: E402
from smps_import import S2Refusal, S2_DAC_MAP, S2_FTONE_MAP   # noqa: E402

# SIZE-ONLY placeholders: every name the declared tables lack, pointed at an id the
# declared tables already use, so the song can be PACKED and measured. Not a proposal
# for what these drums should sound like; that is the owner's call (the report's §D).
SIZE_ONLY_DAC = dict(S2_DAC_MAP, dLowTom=10, dMidTimpani=8, dVLowTimpani=10, dClap=6,
                     dScratch=6)
SIZE_ONLY_FTONE = dict(S2_FTONE_MAP, **{str(0x0C): 0x4B})
SIZE_ONLY_FTONE = {int(k) if isinstance(k, str) else k: v for k, v in SIZE_ONLY_FTONE.items()}

SONGS = (("ehz", "82 - EHZ.asm"), ("cpz", "8E - CPZ.asm"),
         ("hpz", "90 - HPZ.asm"), ("wfz", "8F - WFZ.asm"),
         ("ooz", "84 - OOZ.asm"), ("mtz", "85 - MTZ.asm"))


def main():
    total_new = 0
    for stem, fname in SONGS:
        try:
            song, patches = S._convert(stem, fname, None, None)
        except S2Refusal as e:
            print(f"{stem.upper()}  REFUSED: {e}")
            try:
                song, patches = S._convert(stem, fname, SIZE_ONLY_FTONE, SIZE_ONLY_DAC)
            except Exception as e2:                  # the packer's own refusal, past the tables
                print(f"{stem.upper()}  with SIZE-ONLY placeholder mappings: REFUSED "
                      f"further on: {type(e2).__name__}: {e2}")
                continue
            total_new += len(song) + len(patches)
            print(f"{stem.upper()}  with SIZE-ONLY placeholder mappings: song {len(song):5d} B  "
                  f"patches {len(patches):4d} B")
            continue
        committed = REPO / f"games/sonic4/data/sound/song_s2_{stem}.bin"
        ctl = ""
        if committed.exists():
            ctl = (f"  control: committed {committed.stat().st_size} B "
                   f"{'MATCH' if committed.read_bytes() == song else 'DIFFERS'}")
        else:
            total_new += len(song) + len(patches)
        print(f"{stem.upper()}  song {len(song):5d} B  patches {len(patches):4d} B{ctl}")
    print(f"new songs that packed, together: {total_new} B")


if __name__ == "__main__":
    main()
