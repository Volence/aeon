#!/usr/bin/env python3
"""hcz2_s3k_balance — per-channel loudness of our HCZ2 import against real Sonic 3 & Knuckles,
on RENDERED AUDIO (parcel/psg-env-noteon, 2026-09-26).

WHY. The PSG envelope attack fix (PsgEnvAttack: byte 0 on the note-on tick, as S2 and S3K do)
moves every song with a PSG envelope, and HCZ2 is the one S3K song this engine ships. This asks
what tools/s2_music_balance.py asks for the Sonic 2 songs: per channel, how loud is ours next to
the same channel of the same song in the real game.

THE INSTRUMENT is s2_music_balance's: Genesis Plus GX (libretro) headless through ctypes, the
MAME YM2612 core (the only one whose per-channel mixer volumes work), one process per render,
a MIX render, one SOLO per channel, and a MUTED control that must be silent. Its Core,
options, RMS and spectrum functions are imported, not copied.

HOW EACH ROM IS BROUGHT TO THE SONG:
  * real S3K (an skdisasm S3&K build, --s3k-rom; symbols from --s3k-lst, the build's
    sonic3k.lst): START is pulsed until Game_mode reads $0C (a level). Then
    Current_zone_and_act is set to HCZ act 2 ($0101) and Restart_level_flag to 1, so the level
    reloads as HCZ2 and its own loader plays LevelMusic_Playlist's entry (mus_HCZ2) with
    Play_Music. The capture starts on the first frame Current_music reads mus_HCZ2 (written
    immediately before Play_Music), so the song's first tick is within a frame of it.
    mus_HCZ2 is read from sonic3k.constants.asm's own enumeration, never typed.
  * ours (a DEBUG sound-on ROM, whose song table carries HCZ2; --rom/--lst): after BOOT
    frames Music_Want is poked to SONG_HCZ2 (read from games/sonic4/config/sound_ids.emp);
    Music_Service posts it from the top on the next frame. The capture starts on the poke.

CHANNEL CORRESPONDENCE. GPGX's mixer is per YM channel / per PSG channel. S3K's zFMDACInitBytes
and our CHROUTE_FM1..5 put FM1..FM5 on YM channels 1,2,3,5,6... as s2_music_balance states for
S2; the HCZ2 import keeps each S3K track on its own route (tools/song_hcz2.py), so the solos
compare the same track. The DAC is YM channel 6 in both. This is a like-for-like comparison of
BALANCE between channels on one emulator, not of the owner's chip model.

No threshold, no runner: a measurement read by a person. Exit 0 measured, 2 could not measure.

Usage:
    python3 tools/hcz2_s3k_balance.py --s3k-rom ../skdisasm/skbuilt.bin \\
        --s3k-lst ../skdisasm/sonic3k.lst --rom s4.debug.bin --lst s4.debug.lst [--seconds 60]
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s2_music_balance as smb  # noqa: E402
from suite_paths import suite_path  # noqa: E402

S3K_LEVEL_MODE = 0x0C
S3K_HCZ2 = 0x0101
S3K_LEVEL_TIMEOUT = 3000
S3K_RELOAD_TIMEOUT = 900


def _s3k_sym(lst, name):
    """A RAM symbol from sonic3k.lst's symbol table (`Name : FFFF...FE10 C |`)."""
    pat = re.compile(r"\b%s :\s+([0-9A-Fa-f]+) " % re.escape(name))
    for line in open(lst, errors="replace"):
        m = pat.search(line)
        if m:
            return int(m.group(1), 16) & 0xFFFFFF
    raise KeyError("%s not in %s" % (name, lst))


def _s3k_mus_hcz2():
    """mus_HCZ2's value from sonic3k.constants.asm's enumeration (ds.b 1 per id, each line
    carrying its value as a comment); the comment is cross-checked against the count."""
    path = suite_path("skdisasm", "sonic3k.constants.asm")
    lines = open(path, errors="replace").read().splitlines()
    start = next(i for i, l in enumerate(lines) if re.match(r"^mus__First\b", l))
    n = None
    for l in lines[start:]:
        m = re.match(r"^(mus_\w+)\s+ds\.b\s+1\s*;\s*\$([0-9A-Fa-f]+)", l)
        if m:
            n = int(m.group(2), 16)
            if m.group(1) == "mus_HCZ2":
                return n
    raise KeyError("mus_HCZ2 not found in %s" % path)


def render(job):
    kind, rom, lst, seconds, solo, extra = job
    core = smb.Core(smb._options(solo))
    core.load(rom)
    if core.unknown_keys:
        raise RuntimeError("core never asked for options %s" % sorted(core.unknown_keys))
    if kind == "s3k":
        gm, za, rl, cm = extra["Game_mode"], extra["Current_zone_and_act"], \
            extra["Restart_level_flag"], extra["Current_music"]
        frame = 0
        while core.rd(gm) != S3K_LEVEL_MODE:
            core.buttons = (1 << smb.JOYPAD_START) if (frame % 40) < 4 else 0
            core.run()
            frame += 1
            if frame > S3K_LEVEL_TIMEOUT:
                raise RuntimeError("S3K never reached a level (Game_mode $%02X)" % core.rd(gm))
        core.buttons = 0
        core.run(smb.SETTLE)
        core.wr(za, S3K_HCZ2 >> 8)
        core.wr(za + 1, S3K_HCZ2 & 0xFF)
        core.wr(rl, 0)
        core.wr(rl + 1, 1)
        for i in range(S3K_RELOAD_TIMEOUT):
            core.run()
            if core.rd(cm + 1) == extra["mus"] and core.rd(za) == 1 and core.rd(za + 1) == 1:
                break
        else:
            raise RuntimeError("S3K: Current_music never read mus_HCZ2 ($%02X) after the HCZ2 "
                               "reload (zone/act %02X%02X)" % (extra["mus"], core.rd(za),
                                                              core.rd(za + 1)))
        core.audio = bytearray()
    else:
        want = smb._lst_symbol(lst, "Music_Want")
        core.run(smb.BOOT_FRAMES)
        core.audio = bytearray()
        core.wr(want, smb._song_id("SONG_HCZ2"))
    need = int(seconds * core.rate) * 4
    while len(core.audio) < need:
        core.run()
    pcm = bytes(core.audio[:need])
    return smb.rms_dbfs(pcm), smb.log_spectrum(pcm), core.rate


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--s3k-rom", required=True)
    ap.add_argument("--s3k-lst", required=True)
    ap.add_argument("--rom", required=True, help="our DEBUG sound-on ROM (HCZ2 in its table)")
    ap.add_argument("--lst", required=True)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    a = ap.parse_args(argv)
    for p in (smb.CORE, a.s3k_rom, a.s3k_lst, a.rom, a.lst):
        if not os.path.isfile(p):
            print("COULD NOT RUN: %s is missing" % p)
            return 2
    extra = {n: _s3k_sym(a.s3k_lst, n) for n in
             ("Game_mode", "Current_zone_and_act", "Restart_level_flag", "Current_music")}
    extra["mus"] = _s3k_mus_hcz2()
    solos = [None] + [c[0] for c in smb.CHANNELS] + ["MUTED"]
    jobs, keys = [], []
    for kind, rom, lst in (("s3k", a.s3k_rom, None), ("ours", a.rom, a.lst)):
        for solo in solos:
            jobs.append((kind, rom, lst, a.seconds, solo, extra))
            keys.append((kind, solo))
    ctx = mp.get_context("spawn")
    try:
        with ctx.Pool(a.jobs, maxtasksperchild=1) as pool:
            results = pool.map(render, jobs, chunksize=1)
    except RuntimeError as e:
        print("COULD NOT RUN: %s" % e)
        return 2
    got = dict(zip(keys, results))
    status = 0
    print("== HCZ2  (%.0f s from the song's start; dBFS RMS, both sides pooled; mus_HCZ2 $%02X) =="
          % (a.seconds, extra["mus"]))
    print("  %-6s %9s %9s %8s" % ("chan", "real S3K", "ours", "ours-S3K"))
    for kind in ("s3k", "ours"):
        m = got[(kind, "MUTED")][0]
        if m is not None and m > -90.0:
            print("COULD NOT RUN: the %s render with every channel muted is %.2f dBFS, not "
                  "silent" % (kind, m))
            status = 2
    for solo in solos[:-1]:
        r, o = got[("s3k", solo)][0], got[("ours", solo)][0]
        if solo is None and (r is None or o is None):
            print("COULD NOT RUN: the mix rendered silent (real %s, ours %s)" % (r, o))
            status = 2
        fmt = lambda v: "%9.2f" % v if v is not None else "%9s" % "-"
        d = "%8.2f" % (o - r) if (r is not None and o is not None) else "%8s" % "-"
        print("  %-6s %s %s %s" % (solo or "MIX", fmt(r), fmt(o), d))
    sr, so = got[("s3k", None)][1], got[("ours", None)][1]
    if sr is not None and so is not None:
        print("  mix log-spectrum correlation: %.4f" % float(np.corrcoef(sr, so)[0, 1]))
    return status


if __name__ == "__main__":
    sys.exit(main())
