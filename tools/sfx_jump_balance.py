#!/usr/bin/env python3
"""sfx_jump_balance — how loud the JUMP sound is, alone and against Emerald Hill's music, in our
S2 clip ROM next to real Sonic 2, measured on RENDERED AUDIO (jump-SFX level parcel, 2026-09-27).

THE QUESTION. After the S2 music was brought to real Sonic 2's levels the owner said the jump
sounded "a little quiet", while the other SFX sounded normal. The jump is a PSG sound (PSG1) in
every donor; the ring, spring, spindash and skid-less rest are FM. This tool answers "how loud is
our jump, in isolation and in the mix, next to Sonic 2's own jump over Sonic 2's own EHZ music".

THE INSTRUMENT. The same Genesis Plus GX libretro frontend `s2_music_balance` uses (its `Core`,
MAME YM2612 so the per-channel mixer volumes work, a MUTED control that must render silent).

BOTH ROMS ARE PLAYED THE SAME WAY, through the game's own jump path (a button press, not a poked
SFX request):
  * real Sonic 2 (a REV01 build of s2disasm; --s2-rom): START is pulsed until Game_Mode reads
    $0C (EHZ act 1), SETTLE frames pass, MusID_EHZ is written to Sound_Queue.Music0.
  * our clip ROM (a PLAIN s4.s2clip.bin + .lst; DEBUG's B is free flight): after BOOT frames
    Music_Current is poked to 0 so the region service restarts EHZ from the top.
  Then, in both, a jump button (A, B and C held together: every one of them jumps in both games)
  is held for HOLD frames at each of --at frames after the song request. Sonic is standing at the
  act start in both, and the presses are far enough apart that he has landed.

RENDERS, per ROM: MIX with jumps, MIX without jumps (the music the jump sits against), PSG1 solo
with jumps (the jump alone: both drivers give PSG1 to the SFX and silence the music's PSG1 under
it), PSG1 solo without jumps (what the music's PSG1 contributes in the window: the proof the PSG1
solo window is the jump, not the song), and MUTED.

WHAT IS PRINTED, per press and averaged: over the WINDOW frames from the press, the jump's RMS and
peak (PSG1 solo), the music mix's RMS (no-jump render, same window), jump - music in dB, and the
mix-with-jump minus mix-without-jump in dB (how much the jump adds to what is heard); then ours -
real for each. Exit 0 = measured; 2 = could not measure (a ROM missing, no level, a muted control
not silent, or a press that produced no jump: the PSG1 window with the press is not at least
10 dB above the same window without it).

Usage:
    python3 tools/sfx_jump_balance.py --s2-rom PATH/s2built.bin --rom s4.s2clip.bin \\
        --lst s4.s2clip.lst [--at 300,600,900,1200] [--window 30] [--wav-dir DIR]
"""
from __future__ import annotations

import argparse
import math
import multiprocessing as mp
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s2_music_balance as smb  # noqa: E402

JOY_B, JOY_A, JOY_Y = 0, 8, 1          # libretro ids; GPGX maps them to Genesis A/B/C
JUMP_BUTTONS = (1 << JOY_B) | (1 << JOY_A) | (1 << JOY_Y)
HOLD = 4
S2_SFX0 = 0xFFFFE1          # s2.constants.asm SoundQueue: Music0 $FFE0, SFX0 $FFE1
MAX_DIFF_SHORTFALL_DB = 3.0


def render(job):
    """job = (kind, rom, lst, solo, trig, at, total, boot, settle, wav). trig is None (no
    trigger: the bed), "press" (hold the jump buttons) or an SFX id to REQUEST at each frame of
    `at` (real S2: Sound_Queue.SFX0; ours: an enqueue into Sfx_Ring_Buf, exactly what
    Sound_PlaySFX does). Returns (pcm bytes, [sample offset of each frame start], rate)."""
    kind, rom, lst, solo, trig, at, total, boot, settle, wav = job
    core = smb.Core(smb._options(solo))
    core.load(rom)
    if core.unknown_keys:
        raise RuntimeError("core never asked for options %s" % sorted(core.unknown_keys))
    if kind == "s2":
        frame = 0
        while core.rd(smb.S2_GAME_MODE) != smb.S2_GAME_MODE_LEVEL:
            core.buttons = (1 << smb.JOYPAD_START) if (frame % 40) < 4 else 0
            core.run()
            frame += 1
            if frame > smb.S2_LEVEL_TIMEOUT:
                raise RuntimeError("real S2 never reached a level")
        core.buttons = 0
        core.run(settle)
        core.audio = bytearray()
        core.wr(smb.S2_MUSIC0, smb.S2_SONG["ehz"])
    else:
        cur = smb._lst_symbol(lst, "Music_Current")
        core.run(boot)
        ehz = smb._song_id(smb.OUR_SONG_NAME["ehz"])
        if core.rd(cur) != ehz:
            raise RuntimeError("clip ROM: Music_Current is %d after %d frames, expected %d"
                               % (core.rd(cur), boot, ehz))
        core.audio = bytearray()
        core.wr(cur, 0)
    if kind == "ours":
        ring = smb._lst_symbol(lst, "Sfx_Ring_Buf")
        ring_wr = smb._lst_symbol(lst, "Sfx_Ring_Wr")
        ring_rd = smb._lst_symbol(lst, "Sfx_Ring_Rd")
        depth = ring_wr - ring                  # the buffer ends where the write cursor starts
        if depth <= 0 or depth & (depth - 1) or ring_rd != ring_wr + 1:
            raise RuntimeError("clip ROM: Sfx_Ring_Buf/Wr/Rd layout is not buf[2^n], Wr, Rd")
    starts = []
    for f in range(total):
        starts.append(len(core.audio) // 4)
        held = trig == "press" and any(a <= f < a + HOLD for a in at)
        core.buttons = JUMP_BUTTONS if held else 0
        if isinstance(trig, int) and f in at:
            if kind == "s2":
                core.wr(S2_SFX0, trig)
            else:
                wr = core.rd(ring_wr)
                if ((wr + 1) & (depth - 1)) == core.rd(ring_rd):
                    raise RuntimeError("clip ROM: Sfx_Ring_Buf full at frame %d" % f)
                core.wr(ring + wr, trig)
                core.wr(ring_wr, (wr + 1) & (depth - 1))
        core.run()
    starts.append(len(core.audio) // 4)
    pcm = bytes(core.audio)
    if wav:
        with wave.open(wav, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(core.rate)
            w.writeframes(pcm)
    return pcm, starts, core.rate


def _win(pcm, starts, f0, n):
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    a, b = starts[f0] * 2, starts[min(f0 + n, len(starts) - 1)] * 2
    return x[a:b]


def db_rms(x):
    s = float(np.mean(x * x)) if x.size else 0.0
    return None if s == 0 else 10 * math.log10(s / 32768.0 ** 2)


def db_peak(x):
    p = float(np.max(np.abs(x))) if x.size else 0.0
    return None if p == 0 else 20 * math.log10(p / 32768.0)


def _parse_sfx(spec):
    """'OURS_ID:OURS_CHAN:S2_ID:S2_CHAN' (ids hex, channels from s2_music_balance.CHANNELS)."""
    names = {c[0] for c in smb.CHANNELS}
    try:
        oid, och, sid, sch = spec.split(":")
        oid, sid = int(oid, 16), int(sid, 16)
    except ValueError:
        raise argparse.ArgumentTypeError("--sfx wants OURS_ID:OURS_CHAN:S2_ID:S2_CHAN")
    if och not in names or sch not in names:
        raise argparse.ArgumentTypeError("channels are %s" % sorted(names))
    return {"ours": (oid, och), "s2": (sid, sch)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--s2-rom", required=True)
    ap.add_argument("--rom", required=True, help="our PLAIN S2CLIP ROM (s4.s2clip.bin)")
    ap.add_argument("--lst", required=True)
    ap.add_argument("--at", default="300,600,900,1200",
                    help="frames after the song request at which the SFX is triggered")
    ap.add_argument("--window", type=int, default=30, help="frames measured from each trigger")
    ap.add_argument("--sfx", type=_parse_sfx,
                    help="REQUEST this SFX instead of pressing jump: OURS_ID:OURS_CHAN:S2_ID:S2_CHAN"
                         " (e.g. 33:FM4:B5:FM5, the ring; 62:PSG1:A0:PSG1, the jump by request)")
    ap.add_argument("--boot-frames", type=int, default=smb.BOOT_FRAMES)
    ap.add_argument("--settle", type=int, default=smb.SETTLE)
    ap.add_argument("--wav-dir")
    a = ap.parse_args(argv)
    for p in (smb.CORE, a.s2_rom, a.rom, a.lst):
        if not os.path.isfile(p):
            print("COULD NOT RUN: %s is missing" % p)
            return 2
    at = [int(v) for v in a.at.split(",")]
    total = max(at) + a.window + 10
    spec = a.sfx or {"ours": ("press", "PSG1"), "s2": ("press", "PSG1")}
    label = "jump (button)" if a.sfx is None else "SFX ours $%02X / S2 $%02X" % (
        spec["ours"][0], spec["s2"][0])
    jobs, keys = [], []
    for kind, rom, lst in (("s2", a.s2_rom, None), ("ours", a.rom, a.lst)):
        trig, chan = spec[kind]
        for name, solo, t in (("MIX", None, trig), ("BED", None, None), ("SFX", chan, trig),
                              ("CHBED", chan, None), ("MUTED", "MUTED", trig)):
            wav = None
            if a.wav_dir:
                os.makedirs(a.wav_dir, exist_ok=True)
                wav = os.path.join(a.wav_dir, "sfx_%s_%s.wav" % (kind, name))
            jobs.append((kind, rom, lst, solo, t, at, total, a.boot_frames, a.settle, wav))
            keys.append((kind, name))
    try:
        with mp.get_context("spawn").Pool(len(jobs), maxtasksperchild=1) as pool:
            res = dict(zip(keys, pool.map(render, jobs, chunksize=1)))
    except RuntimeError as e:
        print("COULD NOT RUN: %s" % e)
        return 2
    table = {}
    for kind in ("s2", "ours"):
        m = db_rms(np.frombuffer(res[(kind, "MUTED")][0], dtype="<i2").astype(np.float64))
        if m is not None and m > -90.0:
            print("COULD NOT RUN: %s MUTED render is %.2f dBFS, not silent" % (kind, m))
            return 2
        rows = []
        for f0 in at:
            w = {n: _win(res[(kind, n)][0], res[(kind, n)][1], f0, a.window)
                 for n in ("MIX", "BED", "SFX", "CHBED")}
            j, jp, bed = db_rms(w["SFX"]), db_peak(w["SFX"]), db_rms(w["BED"])
            mix, cbed = db_rms(w["MIX"]), db_rms(w["CHBED"])
            if j is None or bed is None or mix is None:
                print("COULD NOT RUN: %s trigger at %d: a window rendered silent" % (kind, f0))
                return 2
            # Did the trigger sound anything? The renders are deterministic, so the channel's
            # window with the trigger minus the same window without it is exactly what the
            # trigger changed. It must carry most of the window's energy, or the level below
            # would be the song's, not the SFX's.
            n = min(w["SFX"].size, w["CHBED"].size)
            diff = db_rms(w["SFX"][:n] - w["CHBED"][:n])
            if diff is None or diff < j - MAX_DIFF_SHORTFALL_DB:
                print("COULD NOT RUN: %s trigger at %d: the %s window changed by %s dBFS against "
                      "%.2f with the trigger: no SFX sounded there" % (
                          kind, f0, spec[kind][1], "%.2f" % diff if diff is not None else "-inf",
                          j))
                return 2
            rows.append((f0, j, jp, bed, j - bed, mix - bed, cbed))
        table[kind] = rows
    print("== %s vs EHZ music, %d-frame window from each trigger (dBFS; both sides pooled) =="
          % (label, a.window))
    print("  channel: ours %s, S2 %s" % (spec["ours"][1], spec["s2"][1]))
    print("  %-5s %5s %9s %9s %9s %9s %9s %9s" % ("rom", "frame", "sfxRMS", "sfxPeak",
                                                "musicRMS", "sfx-mus", "mix+sfx", "chan bed"))
    for kind in ("s2", "ours"):
        for f0, j, jp, bed, d, lift, cbed in table[kind]:
            print("  %-5s %5d %9.2f %9.2f %9.2f %9.2f %9.2f %9s"
                  % (kind, f0, j, jp, bed, d, lift, "%.2f" % cbed if cbed is not None else "-"))
    avg = {k: [float(np.mean([r[i] for r in table[k]])) for i in (1, 2, 3, 4, 5)]
           for k in table}
    print("  %-11s %9s %9s %9s %9s %9s" % ("mean", "sfxRMS", "sfxPeak", "musicRMS", "sfx-mus",
                                         "mix+sfx"))
    for k in ("s2", "ours"):
        print("  %-11s %9.2f %9.2f %9.2f %9.2f %9.2f" % ((k,) + tuple(avg[k])))
    print("  %-11s %9.2f %9.2f %9.2f %9.2f %9.2f"
          % (("ours-s2",) + tuple(o - r for o, r in zip(avg["ours"], avg["s2"]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
