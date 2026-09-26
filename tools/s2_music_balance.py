#!/usr/bin/env python3
"""s2_music_balance — per-channel loudness of the Sonic 2 clip songs, measured on RENDERED
AUDIO against real Sonic 2 (S2CLIP-REGION-MUSIC volume parcel, 2026-09-26).

THE QUESTION. The owner heard the clip build's Emerald Hill and Chemical Plant songs and said the
per-channel volumes and the drums were off, more in EHZ than CPZ. This tool answers "how loud is
each channel of OUR song, next to the same channel of the same song in REAL Sonic 2", from audio
an emulator actually produced, not from register streams.

THE INSTRUMENT. Genesis Plus GX (the system's libretro core, /usr/lib/libretro/
genesis_plus_gx_libretro.so) driven through a minimal ctypes libretro frontend, headless, one
process per render. GPGX exposes per-channel mixer volumes as core options
(genesis_plus_gx_md_channel_N_volume, N = YM2612 channel 1..6 as 0..5, channel 5 is FM6 = the DAC;
genesis_plus_gx_psg_channel_N_volume, 0..2 tone, 3 noise). A SOLO render sets every other channel
to 0. The YM core is GPGX's MAME YM2612 for both ROMs: its per-channel volume options are
IGNORED under the Nuked cores (measured: all six md channels at 0 still rendered -24.8 dBFS under
'nuked (ym2612)', -47.9 under 'mame (ym2612)'), so every run also renders a MUTED control (every
channel 0) and refuses to report unless it is silent. Nothing here uses the aether bus or MCP.

BOTH ROMS ARE PLAYED THE SAME WAY: in gameplay, idle, with the song REQUESTED at a known frame and
the capture starting on that frame.
  * real Sonic 2 (a REV01 build of s2disasm; pass --s2-rom): START is pulsed until Game_Mode
    ($FFF600) reads $0C (level: Emerald Hill act 1), SETTLE frames pass, then the song's playlist
    id (MusID_EHZ $82 / MusID_CPZ $8E, s2.constants.asm) is written to Sound_Queue.Music0
    ($FFFFE0), which the 68k passes to the Z80 driver on the next V-int (a restart from the top).
  * our clip ROM (s4.s2clip.bin + its .lst): after BOOT frames the act-load request has played
    EHZ; the region service's own two bytes are then poked: Music_Current = 0 (EHZ: the service
    reposts Music_Want = SONG_S2_EHZ from the top) or Music_Want = SONG_S2_CPZ (CPZ).
Both drivers restart the song on a request, so both captures start at the song's first tick,
within a frame or two.

WHAT IS PRINTED, per song: for each channel, the RMS level of its solo render over the capture
window in dBFS (both stereo sides pooled), and the same for the full mix; then per channel
ours - real in dB. Plus, for the mix, the correlation of the two average log-magnitude spectra.
A channel silent in both (e.g. an unused one) is shown as '-'. Exit 0 = measured; 2 = could not
measure (a ROM missing, the game never reached a level, a render came back empty). There is no
pass/fail threshold: this is a measurement, read by a person.

Usage:
    python3 tools/s2_music_balance.py --s2-rom PATH/s2built.bin \\
        --rom s4.s2clip.bin --lst s4.s2clip.lst [--seconds 60] [--song ehz|cpz|both]
        [--wav-dir DIR]   # also write every render as a WAV (listen to them)
"""
from __future__ import annotations

import argparse
import ctypes as C
import math
import multiprocessing as mp
import os
import re
import struct
import sys
import wave

import numpy as np

CORE = "/usr/lib/libretro/genesis_plus_gx_libretro.so"

S2_GAME_MODE = 0xFFF600
S2_GAME_MODE_LEVEL = 0x0C
S2_MUSIC0 = 0xFFFFE0
S2_SONG = {"ehz": 0x82, "cpz": 0x8E}           # s2.constants.asm MusID_EHZ / MusID_CPZ
OUR_SONG_NAME = {"ehz": "SONG_S2_EHZ", "cpz": "SONG_S2_CPZ"}

RETRO_DEVICE_JOYPAD = 1
JOYPAD_START = 3
BOOT_FRAMES = 150      # ours: the act-load request lands at frame 45 plain / 88 debug (measured)
SETTLE = 120           # real S2: frames in the level before the request
S2_LEVEL_TIMEOUT = 2400

CHANNELS = ([("FM%d" % (i + 1), "md", i) for i in range(5)] + [("DAC", "md", 5)]
            + [("PSG%d" % (i + 1), "psg", i) for i in range(3)] + [("NOISE", "psg", 3)])


# --------------------------------------------------------------------------- libretro
class _Var(C.Structure):
    _fields_ = [("key", C.c_char_p), ("value", C.c_char_p)]


class _GameInfo(C.Structure):
    _fields_ = [("path", C.c_char_p), ("data", C.c_void_p), ("size", C.c_size_t),
                ("meta", C.c_char_p)]


class _Geom(C.Structure):
    _fields_ = [("bw", C.c_uint), ("bh", C.c_uint), ("mw", C.c_uint), ("mh", C.c_uint),
                ("ar", C.c_float)]


class _Timing(C.Structure):
    _fields_ = [("fps", C.c_double), ("sample_rate", C.c_double)]


class _AV(C.Structure):
    _fields_ = [("geometry", _Geom), ("timing", _Timing)]


_ENV = C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p)
_VIDEO = C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t)
_AUDIO1 = C.CFUNCTYPE(None, C.c_int16, C.c_int16)
_AUDIOB = C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
_POLL = C.CFUNCTYPE(None)
_STATE = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)


class Core:
    """One GPGX instance. Load the core ONCE per process: its state is global."""

    def __init__(self, options: dict):
        self.lib = C.CDLL(CORE)
        self.options = {k.encode(): v.encode() for k, v in options.items()}
        self.unknown_keys = set()
        self.asked = set()
        self._keep = []
        self.audio = bytearray()
        self.buttons = 0
        self._cbs = [_ENV(self._env), _VIDEO(lambda *a: None), _AUDIO1(self._audio1),
                     _AUDIOB(self._audiob), _POLL(lambda: None), _STATE(self._state)]
        L = self.lib
        L.retro_set_environment(self._cbs[0])
        L.retro_set_video_refresh(self._cbs[1])
        L.retro_set_audio_sample(self._cbs[2])
        L.retro_set_audio_sample_batch(self._cbs[3])
        L.retro_set_input_poll(self._cbs[4])
        L.retro_set_input_state(self._cbs[5])
        L.retro_init()

    def _env(self, cmd, data):
        cmd &= 0xFFFF
        if cmd == 15:                                   # GET_VARIABLE
            v = C.cast(data, C.POINTER(_Var)).contents
            self.asked.add(v.key)
            if v.key in self.options:
                buf = C.c_char_p(self.options[v.key])
                self._keep.append(buf)
                v.value = buf.value
                return True
            return False
        if cmd == 10:                                   # SET_PIXEL_FORMAT
            return True
        if cmd in (9, 31):                              # system / save directory
            p = C.c_char_p(b"/tmp")
            self._keep.append(p)
            C.cast(data, C.POINTER(C.c_char_p))[0] = p.value
            return True
        if cmd == 17:                                   # GET_VARIABLE_UPDATE
            C.cast(data, C.POINTER(C.c_bool))[0] = False
            return True
        if cmd == 52:                                   # GET_CORE_OPTIONS_VERSION -> legacy
            C.cast(data, C.POINTER(C.c_uint))[0] = 0
            return True
        return False

    def _audio1(self, left, right):
        self.audio += struct.pack("<hh", left, right)

    def _audiob(self, data, frames):
        self.audio += C.string_at(data, frames * 4)
        return frames

    def _state(self, port, device, index, id_):
        if port == 0 and device == RETRO_DEVICE_JOYPAD:
            return 1 if (self.buttons >> id_) & 1 else 0
        return 0

    def load(self, path):
        rom = open(path, "rb").read()
        self._rom = C.create_string_buffer(rom, len(rom))
        info = _GameInfo(path.encode(), C.cast(self._rom, C.c_void_p), len(rom), None)
        self.lib.retro_load_game.restype = C.c_bool
        if not self.lib.retro_load_game(C.byref(info)):
            raise RuntimeError("GPGX refused to load %s" % path)
        av = _AV()
        self.lib.retro_get_system_av_info(C.byref(av))
        self.rate = int(round(av.timing.sample_rate))
        self.lib.retro_get_memory_data.restype = C.c_void_p
        self.lib.retro_get_memory_size.restype = C.c_size_t
        if self.lib.retro_get_memory_size(2) != 0x10000:
            raise RuntimeError("GPGX system RAM is not 64 KB")
        self._ram = C.cast(self.lib.retro_get_memory_data(2), C.POINTER(C.c_uint8))
        for k in self.options:
            if k not in self.asked:
                self.unknown_keys.add(k)

    def run(self, n=1):
        for _ in range(n):
            self.lib.retro_run()

    # GPGX keeps 68k work RAM as 16-bit words in host order: byte address a lives at a ^ 1
    # (measured: S2's Game_Mode reads 4 = title at $F600 ^ 1, 0 at $F600).
    def rd(self, addr):
        return self._ram[(addr & 0xFFFF) ^ 1]

    def wr(self, addr, val):
        self._ram[(addr & 0xFFFF) ^ 1] = val & 0xFF


# --------------------------------------------------------------------------- one render
def _options(solo):
    opts = {"genesis_plus_gx_ym2612": "mame (ym2612)",
            "genesis_plus_gx_audio_filter": "disabled",
            "genesis_plus_gx_show_advanced_audio_settings": "enabled"}
    for name, bank, idx in CHANNELS:
        opts["genesis_plus_gx_%s_channel_%d_volume" % (bank, idx)] = (
            "100" if solo is None or solo == name else "0")   # solo "MUTED" -> all 0
    return opts


def _lst_symbol(lst, name):
    pat = re.compile(r"^\s*%s\s*:\s*([0-9A-Fa-f]+)\b" % re.escape(name))
    for line in open(lst, errors="replace"):
        m = pat.match(line)
        if m:
            return int(m.group(1), 16)
    raise KeyError("%s not in %s" % (name, lst))


def _song_id(name):
    """The id from the game's authority (games/sonic4/config/sound_ids.emp), read the way
    clip_rom_bake reads it; never typed here."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import clip_rom_bake
    return clip_rom_bake.song_ids()[name]


def render(job):
    """job = (kind, rom, lst, song, seconds, solo, wav_path, boot, settle). Returns
    (samples:list, rate) or raises. Runs in its own process (the core's state is global)."""
    kind, rom, lst, song, seconds, solo, wav_path, boot, settle = job
    core = Core(_options(solo))
    core.load(rom)
    if core.unknown_keys:
        raise RuntimeError("core never asked for options %s" % sorted(core.unknown_keys))
    if kind == "s2":
        frame = 0
        while core.rd(S2_GAME_MODE) != S2_GAME_MODE_LEVEL:
            core.buttons = (1 << JOYPAD_START) if (frame % 40) < 4 else 0
            core.run()
            frame += 1
            if frame > S2_LEVEL_TIMEOUT:
                raise RuntimeError("real S2 never reached a level (Game_Mode $%02X)"
                                   % core.rd(S2_GAME_MODE))
        core.buttons = 0
        core.run(settle)
        core.audio = bytearray()
        core.wr(S2_MUSIC0, S2_SONG[song])
    else:
        want = _lst_symbol(lst, "Music_Want")
        cur = _lst_symbol(lst, "Music_Current")
        core.run(boot)
        ehz = _song_id(OUR_SONG_NAME["ehz"])
        if core.rd(cur) != ehz:
            raise RuntimeError("clip ROM: Music_Current is %d after %d frames, expected the "
                               "act-load EHZ request (%d)" % (core.rd(cur), boot, ehz))
        core.audio = bytearray()
        if song == "ehz":
            core.wr(cur, 0)                     # the service reposts Music_Want (EHZ)
        else:
            core.wr(want, _song_id(OUR_SONG_NAME["cpz"]))
    need = int(seconds * core.rate) * 4
    while len(core.audio) < need:
        core.run()
    pcm = bytes(core.audio[:need])
    if wav_path:
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(core.rate)
            w.writeframes(pcm)
    return rms_dbfs(pcm), log_spectrum(pcm), core.rate


# --------------------------------------------------------------------------- measures
def rms_dbfs(pcm):
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
    if x.size == 0:
        return None
    s = float(np.mean(x * x))
    return None if s == 0 else 10 * math.log10(s / (32768.0 ** 2))


def log_spectrum(pcm, n=4096):
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float64).reshape(-1, 2).mean(axis=1)
    frames = len(x) // n
    if frames == 0:
        return None
    x = x[:frames * n].reshape(frames, n) * np.hanning(n)
    mag = np.abs(np.fft.rfft(x, axis=1)).mean(axis=0)
    return np.log10(mag + 1e-9)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--s2-rom", required=True)
    ap.add_argument("--rom", required=True, help="our S2CLIP ROM (s4.s2clip*.bin)")
    ap.add_argument("--lst", required=True)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--song", choices=("ehz", "cpz", "both"), default="both")
    ap.add_argument("--wav-dir")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    # How long EHZ plays before the request. The defaults request the song while EHZ has not
    # yet sounded a PSG note (its first PSG1/PSG2 note is ~230 frames after the act-load
    # request), so every PSG tone latch still holds 0: that is a request FROM IDLE. A request
    # after EHZ's PSG has played (e.g. --boot-frames 900 --settle 900) is the region switch
    # the owner hears, which the idle request cannot see (S2CLIP CPZ drone, 2026-09-27).
    ap.add_argument("--boot-frames", type=int, default=BOOT_FRAMES,
                    help="ours: frames from reset to the request (default %(default)s)")
    ap.add_argument("--settle", type=int, default=SETTLE,
                    help="real S2: frames in the level before the request (default %(default)s)")
    a = ap.parse_args(argv)
    for p in (CORE, a.s2_rom, a.rom, a.lst):
        if not os.path.isfile(p):
            print("COULD NOT RUN: %s is missing" % p)
            return 2
    songs = ("ehz", "cpz") if a.song == "both" else (a.song,)
    solos = [None] + [c[0] for c in CHANNELS] + ["MUTED"]
    jobs, keys = [], []
    for song in songs:
        for kind, rom, lst in (("s2", a.s2_rom, None), ("ours", a.rom, a.lst)):
            for solo in solos:
                wav = None
                if a.wav_dir:
                    os.makedirs(a.wav_dir, exist_ok=True)
                    wav = os.path.join(a.wav_dir, "%s_%s_%s.wav" % (song, kind, solo or "MIX"))
                jobs.append((kind, rom, lst, song, a.seconds, solo, wav, a.boot_frames,
                             a.settle))
                keys.append((song, kind, solo))
    ctx = mp.get_context("spawn")
    try:
        with ctx.Pool(a.jobs, maxtasksperchild=1) as pool:
            results = pool.map(render, jobs, chunksize=1)
    except RuntimeError as e:
        print("COULD NOT RUN: %s" % e)
        return 2
    got = dict(zip(keys, results))   # (rms dBFS or None, log spectrum, rate)
    status = 0
    for song in songs:
        print("== %s  (%.0f s from the request; dBFS RMS, both sides pooled) ==" % (song.upper(), a.seconds))
        print("  %-6s %9s %9s %8s" % ("chan", "real S2", "ours", "ours-S2"))
        for kind in ("s2", "ours"):
            m = got[(song, kind, "MUTED")][0]
            if m is not None and m > -90.0:
                print("COULD NOT RUN: the %s %s render with every channel muted is %.2f dBFS, "
                      "not silent: the solo renders do not isolate a channel" % (song, kind, m))
                status = 2
        for solo in solos[:-1]:
            r = got[(song, "s2", solo)][0]
            o = got[(song, "ours", solo)][0]
            if solo is None and (r is None or o is None):
                print("COULD NOT RUN: the %s mix rendered silent (real %s, ours %s)" % (song, r, o))
                status = 2
            fmt = lambda v: "%9.2f" % v if v is not None else "%9s" % "-"
            d = "%8.2f" % (o - r) if (r is not None and o is not None) else "%8s" % "-"
            print("  %-6s %s %s %s" % (solo or "MIX", fmt(r), fmt(o), d))
        sr = got[(song, "s2", None)][1]
        so = got[(song, "ours", None)][1]
        if sr is not None and so is not None:
            print("  mix log-spectrum correlation: %.4f" % float(np.corrcoef(sr, so)[0, 1]))
    return status


if __name__ == "__main__":
    sys.exit(main())
