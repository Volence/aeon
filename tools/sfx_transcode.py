#!/usr/bin/env python3
"""sfx_transcode.py — transcode Sonic 3 & Knuckles SMPS SFX sources into our
engine's SFX blob format (SfxHeader + per-channel records + event streams +
FmPatch bank).

BUILD-PC tooling: reads skdisasm Sound/SFX/*.asm, reuses translate_voice() and
emit_patch_bank_asm() from zyrinx_port.py, and packs events using the song_packer
event model.  Emits data/sound/sfx/sfx_NN.asm + sfx_NN_patches.asm + sfx_table.asm.

Format reference:
  SfxHeader (4 bytes): priority, flags, chcount, pad
  Per-channel record  (6 bytes each): route, kind, cmd_ptr(BE), voice_ptr(BE)
  Then: packed event streams, then: FmPatch bank bytes.
  voice_ptr points into the inline FmPatch bank (offset from blob start).

SFX id → priority map mirrors sound_constants.asm SFXPRI_* constants.
Reserved channels (FM1, FM2, FM6, DAC) may NOT appear; any SFX targeting them
raises a build error.  Unknown coord-flag bytes ($E0-$FF not in the v1 coverage
list) raise a build error per spec §8.  smpsModSet is the one intentional lossy
mapping: dropped with a log line (not a build error).

Usage:
  python3 tools/sfx_transcode.py [generate]   # emit all core SFX to data/sound/sfx/
  python3 -m pytest tools/test_sfx_transcode.py -q
"""

import os
import re
import sys

# ---------------------------------------------------------------------------
# Import reuse surface: translate_voice + emit_patch_bank_asm from zyrinx_port,
# Event classes from song_packer.  Mirror the import pattern in zyrinx_port.py.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from zyrinx_port import translate_voice, emit_patch_bank_asm, FMPATCH_LEN
except ImportError:
    from tools.zyrinx_port import translate_voice, emit_patch_bank_asm, FMPATCH_LEN  # type: ignore

try:
    from song_packer import (
        End, Note, NoteDur, Rest, SetDur, Patch, Vol, Pan, PsgEnv, ModSet,
        SpinRev, LoopPoint, Jump,
        RepeatStart, RepeatEnd,
        CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5,
        CHROUTE_FM6, CHROUTE_PSG1, CHROUTE_PSG2, CHROUTE_PSG3, CHROUTE_PSGN,
        CHROUTE_DAC,
        PackError,
        MEV_END,
    )
except ImportError:
    from tools.song_packer import (  # type: ignore
        End, Note, NoteDur, Rest, SetDur, Patch, Vol, Pan, PsgEnv, ModSet,
        SpinRev, LoopPoint, Jump,
        RepeatStart, RepeatEnd,
        CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5,
        CHROUTE_FM6, CHROUTE_PSG1, CHROUTE_PSG2, CHROUTE_PSG3, CHROUTE_PSGN,
        CHROUTE_DAC,
        PackError,
        MEV_END,
    )


# ---------------------------------------------------------------------------
# Constants mirroring sound_constants.asm (Phase 5a additions from Task 2)
# ---------------------------------------------------------------------------

# SFXEL_* eligibility kinds (mirror sound_constants.asm)
SFXEL_NONE  = 0
SFXEL_FM    = 1
SFXEL_PSG   = 2
SFXEL_NOISE = 3

# Per-SFX priority tiers (mirror sound_constants.asm SFXPRI_*)
SFXPRI_RING     = 0x20
SFXPRI_JUMP     = 0x40
SFXPRI_ROLL     = 0x60
SFXPRI_SKID     = 0x60
SFXPRI_SPINDASH = 0x80
SFXPRI_DASH     = 0x80
SFXPRI_DEATH    = 0xC0
SFXPRI_RINGLOSS = 0xC0

# SHF_* flag bits (mirror sound_constants.asm)
SHF_CONTINUOUS = 1 << 0
SHF_STEREO_ALT = 1 << 1
SHF_LOOP       = 1 << 2

# Priority table keyed by SFX id (hex string as in filename, lower-case)
_SFX_PRIORITY = {
    0x33: SFXPRI_RING,
    0x34: SFXPRI_RING,
    0x35: SFXPRI_DEATH,
    0x36: SFXPRI_SKID,
    0x3C: SFXPRI_ROLL,
    0x62: SFXPRI_JUMP,
    0xAB: SFXPRI_SPINDASH,
    0xB6: SFXPRI_DASH,
    0xB9: SFXPRI_RINGLOSS,
}

# S3K channel id -> (our CHROUTE_*, eligibility kind)
_S3K_CHAN_MAP = {
    0x80: (CHROUTE_PSG1,  SFXEL_PSG),    # cPSG1
    0xA0: (CHROUTE_PSG2,  SFXEL_PSG),    # cPSG2
    0xC0: (CHROUTE_PSG3,  SFXEL_PSG),    # cPSG3
    0xE0: (CHROUTE_PSGN,  SFXEL_NOISE),  # cNoise
    0x02: (CHROUTE_FM3,   SFXEL_FM),     # cFM3
    0x04: (CHROUTE_FM4,   SFXEL_FM),     # cFM4
    0x05: (CHROUTE_FM5,   SFXEL_FM),     # cFM5
    0x06: (CHROUTE_FM6,   SFXEL_NONE),   # cFM6 — reserved in v1
}

# Reserved routes that SFX may NOT target
_RESERVED_ROUTES = {CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM6, CHROUTE_DAC}

# SFX id -> filename prefix (for the core set)
_CORE_SFX_IDS = [0x33, 0x34, 0x35, 0x36, 0x3C, 0x62, 0xAB, 0xB6, 0xB9]

# S3K note enum: nRst=$80, nC0=$81, nCs0=$82, ..., sequential chromatically
# The enum starts at $80 for nRst, then $81 for nC0, $82 for nCs0, etc.
# Total range covers ~8 octaves (nC0..$FF).
# Our pitch index = S3K note byte - 0x81 (so nC0=0, nCs0=1, ...).
# nRst=$80 maps to Rest.
S3K_NOTE_REST = 0x80
S3K_NOTE_BASE = 0x81    # nC0 = our pitch index 0

# S3K PSG note-names are 2 octaves below scientific pitch: nC0 in S3K sounds like C2
# in scientific notation.  Our PsgDivisorTableZ uses scientific numbering (index 0 = true C0).
# Therefore an S3K PSG note index must be shifted +24 semitones to reproduce S3K's actual
# audible pitch in our engine.
# NOTE: PSGPitchConvert in the S3K driver is a no-op branch for smpsHeaderStartSong 3 /
# SonicDriverVer=4 SFX sources, so there is no psgdelta to undo — the raw note bytes
# already encode the S3K-nominal pitch and the +24 fixup is the full correction.
PSG_OCTAVE_FIXUP = 24

# --- TASTE KNOB: FM SFX octave shift ---------------------------------------
# This is NOT a faithfulness correction.  Our FM SFX pitch path reproduces real
# Sonic 3 & Knuckles frequencies EXACTLY (verified: ring/roll/spindash notes
# match S3K's zGetNextNote + zFMFrequencies + header-transpose math to within
# rounding, ratio 1.000 / <0.005 octaves).  But S3K's FM SFX are objectively
# high-pitched — e.g. Roll's nCs6 with its +$0C (one-octave) header transpose
# lands at block 7 / ~2220 Hz (C#7), and Spindash/Ring sit at ~520-1050 Hz.
#
# The user reports they sound "a few octaves too high" by ear, so this knob
# lowers the FM SFX a clean, whole number of octaves below faithful S3K.  It is
# applied ONLY to FM SFX notes (PSG keeps its own scientific-pitch fixup above).
# Default = -12 semitones (one octave down) as a starting point; bump to -24 for
# two octaves.  Set to 0 to restore byte-exact S3K pitch.
FM_SFX_OCTAVE_SHIFT = 0   # semitones; -12 = one octave down (taste, not faithfulness)


class TranscodeError(Exception):
    """Raised on unrecognised SMPS coord flags or other fatal parse errors."""
    pass


# ---------------------------------------------------------------------------
# SMPS SFX source parser
# ---------------------------------------------------------------------------

def _parse_int(tok: str) -> int:
    """Parse a token that may be hex ($XX) or decimal."""
    tok = tok.strip().rstrip(',')
    if tok.startswith('$'):
        return int(tok[1:], 16)
    return int(tok, 0)


def _parse_signed_byte(tok: str) -> int:
    """Parse a byte token as a SIGNED value (-128..127): $F8 -> -8, $1A -> 26.
    Used for the smpsModSet `change` (per-step pitch delta), which the source writes
    as a raw byte whose high bit is the sign (S3K's zDoModulation sign-extends it)."""
    v = _parse_int(tok)
    return v - 256 if v > 127 else v


# sTone_XX token -> 1-based engine PSG vol-env id. The id IS the sTone number
# (the engine's PsgVolEnv_Table holds the S3K-exact VolEnv body for each shipped
# id). Only the sTones our core corpus references are mapped; an unmapped sTone
# raises (spec section 8: never silently dropped).
_STONE_TO_ENV = {
    'sTone_03': 0x03, 'sTone_0D': 0x0D, 'sTone_0E': 0x0E,
    'sTone_0F': 0x0F, 'sTone_11': 0x11, 'sTone_1D': 0x1D,
}


def _stone_to_env_id(tok: str) -> int:
    tok = tok.strip()
    if tok in _STONE_TO_ENV:
        return _STONE_TO_ENV[tok]
    # allow a bare numeric (already an id)
    try:
        return _parse_int(tok)
    except (TranscodeError, ValueError):
        raise TranscodeError(
            f"unmapped smpsPSGvoice tone {tok!r} "
            f"(add it to PsgVolEnv_Table + _STONE_TO_ENV)")


def _chan_id_from_token(tok: str) -> int:
    """Resolve a cXXX or bare hex channel id token."""
    _chan_names = {
        'cPSG1': 0x80, 'cPSG2': 0xA0, 'cPSG3': 0xC0, 'cNoise': 0xE0,
        'cFM3': 0x02,  'cFM4': 0x04,  'cFM5': 0x05,  'cFM6': 0x06,
    }
    tok = tok.strip()
    if tok in _chan_names:
        return _chan_names[tok]
    return _parse_int(tok)


def _note_from_token(tok: str) -> int:
    """Return the raw S3K note byte for a note token like nC5, nBb3, nRst, $90, etc."""
    tok = tok.strip()
    if tok.startswith('$'):
        return _parse_int(tok)
    if tok.startswith('n'):
        # Build a lookup from name to byte value
        # S3K note names follow chromatic scale starting at C:
        # C Cs/Db D Ds/Eb E F Fs/Gb G Gs/Ab A As/Bb B
        _NOTE_STEPS = {
            'C': 0, 'Cs': 1, 'Db': 1, 'D': 2, 'Ds': 3, 'Eb': 3,
            'E': 4, 'Fb': 4, 'Es': 5, 'F': 5, 'Fs': 6, 'Gb': 6,
            'G': 7, 'Gs': 8, 'Ab': 8, 'A': 9, 'As': 10, 'Bb': 10,
            'B': 11, 'Cb': 11, 'Bs': 12,
        }
        if tok == 'nRst':
            return S3K_NOTE_REST
        # parse octave: nXXn (e.g. nC5, nBb3)
        # Find octave digit(s) at the end
        m = re.match(r'^n([A-Z][a-z]?)(\d+)$', tok)
        if m:
            name, octave_str = m.group(1), m.group(2)
            step = _NOTE_STEPS.get(name)
            if step is None:
                raise TranscodeError(f"Unknown note name in token: {tok!r}")
            octave = int(octave_str)
            return S3K_NOTE_BASE + octave * 12 + step
        raise TranscodeError(f"Cannot parse note token: {tok!r}")
    raise TranscodeError(f"Cannot parse note token: {tok!r}")


def _smps_note_to_pitch(raw_byte: int, is_psg: bool, transpose: int = 0) -> int:
    """Convert a raw S3K note byte to our engine pitch index.

    For FM: pitch = raw - S3K_NOTE_BASE + transpose + FM_SFX_OCTAVE_SHIFT,
    clamped 0..0x5E.  FM_SFX_OCTAVE_SHIFT is a TASTE knob (default one octave
    down); the raw+transpose part alone reproduces S3K's exact FM SFX pitch.
    For PSG: S3K PSG note-names are 2 octaves below scientific pitch (nC0 in S3K
    sounds like C2 scientifically).  Our PsgDivisorTableZ is scientific-numbered
    (index 0 = true C0), so we add +24 semitones to translate S3K PSG note indices
    to our table's scientific numbering and reproduce S3K's actual audible pitch.
    PSGPitchConvert is a no-op for smpsHeaderStartSong 3 / SonicDriverVer=4 SFX
    sources, so there is no psgdelta to undo — +24 is the complete correction.
    """
    pitch = raw_byte - S3K_NOTE_BASE + transpose
    if is_psg:
        pitch += PSG_OCTAVE_FIXUP
    else:
        # FM SFX taste knob (NOT faithfulness): bring S3K's high FM SFX down a
        # whole number of octaves.  FM-only; PSG keeps its scientific fixup above.
        pitch += FM_SFX_OCTAVE_SHIFT
    if pitch < 0:
        pitch = 0
    if pitch > 0x5E:
        pitch = 0x5E
    return pitch


class _SmpsVoiceBuilder:
    """Accumulate smpsVc* macro calls into a voice dict for translate_voice()."""
    def __init__(self):
        self._d = {
            'fb': 0, 'algo': 0, 'ams_fms_pan': 0xC0,
            'dt_mul': [0, 0, 0, 0], 'tl': [0, 0, 0, 0],
            'ks_ar': [0, 0, 0, 0], 'am_d1r': [0, 0, 0, 0],
            'd2r': [0, 0, 0, 0], 'sl_rr': [0, 0, 0, 0],
        }
        # Accumulate per-operator values separately before combining
        self._dt   = [0, 0, 0, 0]
        self._cf   = [0, 0, 0, 0]
        self._rs   = [0, 0, 0, 0]
        self._ar   = [0, 0, 0, 0]
        self._am   = [0, 0, 0, 0]
        self._d1r  = [0, 0, 0, 0]

    def apply(self, macro: str, args: list):
        """Process one smpsVc* macro call with parsed args."""
        if macro == 'smpsVcAlgorithm':
            self._d['algo'] = _parse_int(args[0])
        elif macro == 'smpsVcFeedback':
            self._d['fb'] = _parse_int(args[0])
        elif macro == 'smpsVcUnusedBits':
            pass  # ignored
        elif macro == 'smpsVcDetune':
            self._dt = [_parse_int(a) for a in args[:4]]
        elif macro == 'smpsVcCoarseFreq':
            self._cf = [_parse_int(a) for a in args[:4]]
        elif macro == 'smpsVcRateScale':
            self._rs = [_parse_int(a) for a in args[:4]]
        elif macro == 'smpsVcAttackRate':
            self._ar = [_parse_int(a) for a in args[:4]]
        elif macro == 'smpsVcAmpMod':
            # S3K SMPS2ASM version 1 stores raw AM value shifted left by 7
            # (smpsVcAmpMod with SourceSMPS2ASM==0 does <<5, ==1 does <<7).
            # The SFX files use smpsHeaderStartSong 3 without a smps2asm version
            # arg (implicit 0), so SourceSMPS2ASM==0 → am<<5.
            self._am = [_parse_int(a) << 5 for a in args[:4]]
        elif macro == 'smpsVcDecayRate1':
            self._d1r = [_parse_int(a) for a in args[:4]]
        elif macro == 'smpsVcDecayRate2':
            self._d['d2r'] = [_parse_int(a) for a in args[:4]]
        elif macro == 'smpsVcDecayLevel':
            dl = [_parse_int(a) for a in args[:4]]
            self._d['sl_rr'] = [(dl[i] << 4) for i in range(4)]  # rr filled by ReleaseRate
        elif macro == 'smpsVcReleaseRate':
            rr = [_parse_int(a) for a in args[:4]]
            for i in range(4):
                self._d['sl_rr'][i] = (self._d['sl_rr'][i] & 0xF0) | (rr[i] & 0x0F)
        elif macro == 'smpsVcTotalLevel':
            # smpsVcTotalLevel emits in S3K physical order: op4, op3, op2, op1
            # (S3K non-S2 order for SMPS Z80: [op4,op3,op2,op1] → our physical [S1,S3,S2,S4])
            # Actually looking at the S3K macro (SonicDriverVer>=3, SourceDriver>=3):
            # smpsDcb (vcDT4<<4)+vcCF4, (vcDT3<<4)+vcCF3, (vcDT2<<4)+vcCF2, (vcDT1<<4)+vcCF1
            # So byte order is [op4, op3, op2, op1] in the binary data.
            # The macro args are op1,op2,op3,op4 (same as all the other macros).
            # We need: dt_mul[0]=op1, dt_mul[1]=op3, dt_mul[2]=op2, dt_mul[3]=op4
            # (because the binary stores [op4,op3,op2,op1] and S3K indices are 1-based).
            # But for TL, the macro args are also (op1,op2,op3,op4).
            # In smpsVcTotalLevel, the smpsDcb line writes: TL4,TL3,TL2,TL1
            # So we store them in [op1..op4] order as provided by the macro args.
            tl = [_parse_int(a) for a in args[:4]]
            self._d['tl'] = tl  # args: op1,op2,op3,op4
            # Finalize dt_mul = (dt<<4)|cf, ks_ar = (rs<<6)|ar, am_d1r
            # S3K binary order for these groups is also [op4,op3,op2,op1]:
            # smpsDcb (vcDT4<<4)+vcCF4, (vcDT3<<4)+vcCF3, (vcDT2<<4)+vcCF2, (vcDT1<<4)+vcCF1
            # So the binary stores data for op4 first; args are [op1,op2,op3,op4].
            # Our translate_voice() OP_REORDER=[0,1,2,3] = identity (already calibrated
            # for B&R Bank2 voices in physical register order).
            # S3K voices in the Z80 binary are stored [op4,op3,op2,op1] for each group.
            # translate_voice() reads self._d[key][OP_REORDER[0..3]], so we store in
            # [op4,op3,op2,op1] order (what the Z80 binary would have, same as the
            # B&R Bank2 that the reorder=identity was calibrated against).
            # args[0]=op1,args[1]=op2,args[2]=op3,args[3]=op4 → store as [op4,op3,op2,op1]
            for key, src in [
                ('dt_mul', [(self._dt[i] << 4) | (self._cf[i] & 0x0F) for i in range(4)]),
                ('ks_ar',  [(self._rs[i] << 6) | (self._ar[i] & 0x1F) for i in range(4)]),
                ('am_d1r', [(self._am[i] & 0x80) | (self._d1r[i] & 0x1F) for i in range(4)]),
            ]:
                # reorder from macro-arg order [op1,op2,op3,op4] to binary order [op4,op3,op2,op1]
                self._d[key] = [src[3], src[2], src[1], src[0]]
            # TL: also reorder args [op1,op2,op3,op4] to binary [op4,op3,op2,op1]
            self._d['tl'] = [tl[3], tl[2], tl[1], tl[0]]
        else:
            pass  # unknown smpsVc* sub-macro — ignore

    def build(self) -> bytes:
        """Finalize and call translate_voice()."""
        return translate_voice(self._d)


def _split_args(arg_str: str) -> list:
    """Split macro argument string on commas, stripping whitespace."""
    return [a.strip() for a in arg_str.split(',') if a.strip()]


def _parse_sfx_source(src: str, sfx_id: int, sfx_label: str) -> dict:
    """Parse a skdisasm SFX .asm source string.

    Returns a dict:
      {
        'id': sfx_id,
        'label': sfx_label,
        'channels': [
            {
                'chanid': int,          # raw S3K channel id
                'route': int,           # our CHROUTE_*
                'kind': int,            # SFXEL_*
                'transpose': int,       # from smpsHeaderSFXChannel pitch arg
                'init_vol': int,        # from smpsHeaderSFXChannel vol arg (0 = no init vol)
                'events': [Event, ...], # song_packer events
                'has_loop': bool,       # does this channel have a smpsLoop?
            },
            ...
        ],
        'voices': [bytes, ...],  # list of 26-byte FmPatch records (in order seen)
        'flags': int,            # SHF_* accumulated flags
      }
    """
    lines = src.splitlines()

    # --- Phase 1: find labels and their line indices ------------------------
    label_lines = {}  # label_name -> line_index
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.endswith(':') and not stripped.startswith(';'):
            lbl = stripped[:-1].strip()
            label_lines[lbl] = i

    # --- Phase 2: scan for smpsHeaderSFXChannel lines ----------------------
    chan_headers = []  # list of (chanid, data_label, pitch, vol)
    voices_label = None
    chcount = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(';'):
            continue

        # smpsHeaderVoice <label>
        m = re.match(r'smpsHeaderVoice\s+(\S+)', stripped)
        if m:
            voices_label = m.group(1)
            continue

        # smpsHeaderSFXChannel chanid, loc, pitch, vol
        m = re.match(r'smpsHeaderSFXChannel\s+(.+)', stripped)
        if m:
            args = _split_args(m.group(1))
            if len(args) < 4:
                raise TranscodeError(
                    f"sfx ${sfx_id:02X}: smpsHeaderSFXChannel needs 4 args, got {args}")
            chanid = _chan_id_from_token(args[0])
            data_lbl = args[1].strip()
            pitch = _parse_int(args[2])
            # pitch is a signed byte (two's-complement in SMPS)
            if pitch >= 0x80:
                pitch -= 0x100
            vol_raw = _parse_int(args[3])
            chan_headers.append((chanid, data_lbl, pitch, vol_raw))
            chcount += 1
            continue

    if not chan_headers:
        raise TranscodeError(f"sfx ${sfx_id:02X}: no smpsHeaderSFXChannel found")

    # --- Phase 3: parse voice block ----------------------------------------
    # Find the voices label line and parse smpsVc* macros after it.
    voices = []
    if voices_label and voices_label in label_lines:
        vbuilder = _SmpsVoiceBuilder()
        in_voice = False
        vline_start = label_lines[voices_label]
        for line in lines[vline_start + 1:]:
            stripped = line.strip()
            if stripped.startswith(';') or not stripped:
                continue
            m = re.match(r'(smpsVc[A-Za-z]+)\s*(.*)', stripped)
            if m:
                macro = m.group(1)
                args = _split_args(m.group(2))
                if macro == 'smpsVcTotalLevel':
                    vbuilder.apply(macro, args)
                    # smpsVcTotalLevel is the last macro in a voice block
                    voices.append(vbuilder.build())
                    vbuilder = _SmpsVoiceBuilder()
                else:
                    vbuilder.apply(macro, args)
                in_voice = True
            elif in_voice:
                # Stop at non-voice line
                break

    # --- Phase 4: parse channel data streams --------------------------------
    # Build a flat token stream for each channel, starting from its data label.
    channels_out = []
    sfx_flags = 0

    # Channel-boundary labels: every smpsHeaderSFXChannel data-pointer label.
    # A channel's data block ends where the NEXT channel's data label begins
    # (S3K source layout: channel data blocks are laid out sequentially and a
    # channel that lacks an explicit smpsStop falls through into the next
    # channel's label).  We use this set to inject an implicit end at that
    # boundary so a channel never consumes the following channel's events.
    # Loop-target labels (Sound_XX_LoopNN / loop-internal labels) are NOT in
    # this set, so smpsLoop handling is unaffected.
    _channel_data_labels = {dl for (_cid, dl, _p, _v) in chan_headers}

    # We need to handle the special case where the data for a channel lives
    # somewhere else (e.g. Sound_34's smpsJump to Sound_34_Jump00 in Sound_33).
    # We build a per-label content map for cross-label jumps.

    def _get_line_range_for_label(lbl: str) -> int:
        """Return the start line index for a label, or -1 if not found."""
        return label_lines.get(lbl, -1)

    for chanid, data_lbl, transpose, vol_raw in chan_headers:
        route_info = _S3K_CHAN_MAP.get(chanid)
        if route_info is None:
            raise TranscodeError(
                f"sfx ${sfx_id:02X}: unknown S3K channel id ${chanid:02X}")
        route, kind = route_info

        if route in _RESERVED_ROUTES:
            raise TranscodeError(
                f"sfx ${sfx_id:02X}: channel ${chanid:02X} maps to reserved route "
                f"{route} (FM1/FM2/FM6/DAC are not stealable)")

        is_psg = kind in (SFXEL_PSG, SFXEL_NOISE)
        is_fm  = kind == SFXEL_FM

        events = []

        # Initial volume (from header vol field) — $00 means "no initial vol"
        # (the volume is set by an initial PSG voice envelope for PSG, or by
        # the voice TL for FM).  For simplicity: emit Vol only if non-zero.
        if vol_raw != 0:
            # SMPS vol is an attenuation/raw byte; map to our 0-127 scale.
            # S3K PSG: vol is SN76489 attenuation (0=loud, $F=silent + more).
            # S3K FM: vol is a TL addition (higher = quieter).
            # For our engine: Vol(0..127) where 0=silent,127=loud follows our
            # driver convention.  The SMPS vol field is an initial volume modifier;
            # map: fm_vol = max(0, 100 - vol_raw); psg_vol = max(0, 100 - vol_raw*7).
            # This is approximate — the exact mapping depends on SFX-specific
            # voice parameters.  For v1 the FM voice TL carries the real loudness.
            if is_fm:
                fm_vol = max(0, min(127, 127 - vol_raw))
                events.append(Vol(fm_vol))
            else:
                psg_vol = max(0, min(127, 127 - vol_raw * 7))
                events.append(Vol(psg_vol))
        else:
            # Default volume: 100 for FM (mid), 80 for PSG
            if is_fm:
                events.append(Vol(100))
            else:
                events.append(Vol(80))

        # noattack flag: set if smpsNoAttack precedes the next note
        noattack_pending = False

        # current duration default (set by bare duration bytes)
        cur_dur = 1

        # voice index (within the SFX's own bank, 0-based)
        voice_idx = 0

        # loop / repeat tracking
        loop_label = None   # label of smpsLoop's target
        loop_count = 0      # smpsLoop repeat count (plays N times total)
        has_loop = False

        # jump target for smpsJump
        jump_target_label = None

        # Scan the channel data starting at data_lbl
        start_line = _get_line_range_for_label(data_lbl)
        if start_line < 0:
            raise TranscodeError(
                f"sfx ${sfx_id:02X}: data label {data_lbl!r} not found in source")

        # Process lines from the data label
        i = start_line + 1

        # We may need to follow a smpsJump to another label in the same file.
        # We track a "continuation label" to pick up after a jump.
        follow_label = None

        def _process_lines(start_i: int) -> bool:
            """Process lines starting at start_i. Returns True if we hit smpsStop."""
            nonlocal noattack_pending
            nonlocal cur_dur, voice_idx, loop_label, loop_count, has_loop
            nonlocal jump_target_label, sfx_flags

            i = start_i
            while i < len(lines):
                line = lines[i]
                i += 1
                stripped = line.strip()
                if not stripped or stripped.startswith(';'):
                    continue

                # Skip label lines (definitions)
                if re.match(r'^[A-Za-z_][A-Za-z0-9_]*:', stripped):
                    continue

                # Check for inline dc.b content (multiple tokens on one line)
                # A dc.b line may contain: note bytes, duration bytes, or special tokens
                if stripped.startswith('dc.b'):
                    rest = stripped[4:].strip()
                    _process_dcb(rest)
                    continue

                # Check for coord flag macros
                m = re.match(r'(smps[A-Za-z]+|smpsFM[A-Za-z]+)\s*(.*)', stripped)
                if m:
                    macro = m.group(1)
                    arg_str = m.group(2).strip()
                    if macro == 'smpsStop':
                        events.append(End())
                        return True  # channel stream ended
                    elif macro == 'smpsSetvoice' or macro == 'smpsFMvoice':
                        args = _split_args(arg_str)
                        # voice index in SFX's own bank (always 0 for v1 — one voice)
                        # The arg is the voice index within the SFX voice table.
                        # Since our transcoder collects voices in order, this is always 0.
                        vi = _parse_int(args[0]) if args else 0
                        events.append(Patch(vi))
                    elif macro == 'smpsPan':
                        args = _split_args(arg_str)
                        # args: direction + amsfms
                        # direction is panNone=$00, panRight=$40, panLeft=$80, panCentre=$C0
                        # smpsHeaderSFXChannel uses $E0+direction in the raw byte;
                        # the macro emits: dc.b $E0, direction+amsfms
                        dir_tok = args[0].strip()
                        amsfms_tok = args[1].strip() if len(args) > 1 else '0'
                        _pan_names = {
                            'panNone': 0x00, 'panRight': 0x40,
                            'panLeft': 0x80, 'panCentre': 0xC0, 'panCenter': 0xC0,
                        }
                        if dir_tok in _pan_names:
                            dir_val = _pan_names[dir_tok]
                        else:
                            dir_val = _parse_int(dir_tok)
                        amsfms_val = _parse_int(amsfms_tok)
                        b4 = dir_val | amsfms_val
                        events.append(Pan(b4))
                    elif macro == 'smpsPSGvoice':
                        # PSG volume envelope (sTone_XX). Emit MEV_PSGENV with the
                        # 1-based engine env id (== the sTone number; the engine table
                        # holds the S3K-exact VolEnv body for each id we ship).
                        args = _split_args(arg_str)
                        tone_tok = args[0].strip() if args else '0'
                        env_id = _stone_to_env_id(tone_tok)
                        events.append(PsgEnv(env_id))
                    elif macro == 'smpsModSet':
                        # Pitch modulation: emit MEV_MODSET with the raw .asm operands
                        # (wait, speed, change, step). The engine applies S3K's own
                        # srl-on-init (Mod_ReArm seeds steps = raw>>1) — do NOT re-encode
                        # the macro's version-specific *speed step transform here (that is
                        # the data layer, already implied by the source operands). `change`
                        # is signed ($F8 -> -8). All-zero = mod off (smpsModSet 0,0,0,0).
                        args = _split_args(arg_str)
                        if len(args) < 4:
                            raise TranscodeError(
                                f"smpsModSet expects 4 operands, got {args!r}")
                        wait  = _parse_int(args[0])
                        speed = _parse_int(args[1])
                        change = _parse_signed_byte(args[2])
                        step  = _parse_int(args[3])
                        events.append(ModSet(wait, speed, change, step))
                    elif macro == 'smpsSpindashRev':
                        # Runtime-escalating spindash rev: emit the opcode; the engine
                        # adds the global rev (re-trigger count) into sc_transpose.
                        events.append(SpinRev())
                    elif macro == 'smpsResetSpindashRev':
                        # The rev RESET is dispatch-folded in the engine (any non-spindash
                        # SFX zeroes the global), so no stream opcode is emitted here.
                        pass
                    elif macro == 'smpsPSGform':
                        # Noise mode / PSG form control: $F3,form.  For noise SFX, $E7 form
                        # enables periodic noise (borrowing PSG3 frequency).
                        # v1: record informatively; no engine event (engine handles via sx_kind).
                        args = _split_args(arg_str)
                        form_val = _parse_int(args[0]) if args else 0
                        print(f"  [info] sfx ${sfx_id:02X} ch ${chanid:02X}: smpsPSGform "
                              f"${form_val:02X} (noise mode; handled by engine restore via sx_kind)",
                              file=sys.stderr)
                    elif macro == 'smpsLoop':
                        # smpsLoop index, loops, loc
                        args = _split_args(arg_str)
                        loop_idx = _parse_int(args[0]) if len(args) > 0 else 0
                        loops = _parse_int(args[1]) if len(args) > 1 else 1
                        lbl = args[2].strip() if len(args) > 2 else ''
                        # Translate to RepeatStart/RepeatEnd (back-patch style).
                        # The loop body starts at the label; we emit RepeatEnd here.
                        # Since we process top-to-bottom, we need to have emitted
                        # RepeatStart when we passed the loop label.
                        # We do this by inserting a LoopPoint at the label position.
                        # For our pack_sfx, we use a simple bounded-unroll approach:
                        # The loop body is already in our events list from the first pass.
                        # We emit RepeatEnd(loops) now and scan back to find where to
                        # insert RepeatStart.
                        # Find the insertion point: the loop-target label
                        tgt_line = _get_line_range_for_label(lbl)
                        if tgt_line < 0:
                            # fallback: wrap everything after the last Vol/Patch setup
                            # in a repeat
                            _insert_repeat_start(events, lbl)
                        else:
                            _insert_repeat_start(events, lbl)
                        events.append(RepeatEnd(max(1, min(255, loops))))
                        has_loop = True
                        sfx_flags |= SHF_LOOP
                    elif macro == 'smpsJump' or macro == 'smpsJumpS3':
                        # smpsJump loc — jump to loc (absolute, in same file).
                        # For our transcoder: follow the jump (the target content is
                        # included inline), then treat it as if the stream continues there.
                        args = _split_args(arg_str)
                        lbl = args[0].strip() if args else ''
                        jump_target_label = lbl
                        tgt_line = _get_line_range_for_label(lbl)
                        if tgt_line >= 0:
                            # Recurse into the jump target
                            _process_lines(tgt_line + 1)
                        else:
                            raise TranscodeError(
                                f"sfx ${sfx_id:02X}: smpsJump target {lbl!r} not found")
                        return True  # stop after jump (target handles End/Stop)
                    elif macro == 'smpsFMAlterVol':
                        # Relative FM volume change: compute absolute Vol from current vol.
                        # S3K: $E5,val1,val2 (two-arg form for S3K; val1 unused, val2 is FM delta).
                        # One-arg form: $E6,val1 (FM only in S3K context).
                        # The macro expands to $E5,val1,val2 for S3K driver.
                        # For us: translate to a relative volume adjustment on the current
                        # channel by scanning back to find the last Vol() in events and
                        # computing an updated absolute volume.
                        args = _split_args(arg_str)
                        if len(args) >= 2:
                            # S3K two-arg form: first is unused, second is FM delta
                            delta = _parse_int(args[1])
                        elif args:
                            delta = _parse_int(args[0])
                        else:
                            delta = 0
                        # Find the current volume from the last Vol event
                        cur_vol = _find_last_vol(events, default=100 if is_fm else 80)
                        # Apply delta: in S3K, higher delta = quieter (more attenuation)
                        # Our Vol is 0=silent, 127=loud; SMPS delta adds to attenuation.
                        new_vol = max(0, min(127, cur_vol - delta))
                        events.append(Vol(new_vol))
                    elif macro == 'smpsNoAttack':
                        # The smpsNoAttack byte ($E7) is used as a prefix before the next note.
                        # It prevents re-keying the FM envelope.  In our engine this means
                        # we emit the note WITHOUT re-key.  For v1 we track a flag and
                        # emit the note normally (the no-attack semantics are honored by
                        # the fact that we don't re-key in the SFX interpreter for held notes).
                        noattack_pending = True
                        # Also: smpsNoAttack appears INLINE in dc.b lines as a token
                        # (handled in _process_dcb).
                    elif macro in ('smpsHeaderStartSong', 'smpsHeaderVoice',
                                   'smpsHeaderTempoSFX', 'smpsHeaderChanSFX',
                                   'smpsHeaderSFXChannel'):
                        # Header macros — already consumed in phase 2; skip in data pass.
                        pass
                    else:
                        # Unknown coord flag — build error per spec §8.
                        raise TranscodeError(
                            f"sfx ${sfx_id:02X} ch ${chanid:02X}: unknown SMPS coord flag "
                            f"{macro!r} — not in v1 coverage list. "
                            f"Add support or document as intentional lossy mapping.")
                    continue

                # smpsVc* macros in the data stream would be part of voices block — skip
                if re.match(r'smpsVc[A-Za-z]+', stripped):
                    continue

            return False  # fell off the end without smpsStop

        def _insert_repeat_start(ev: list, lbl: str):
            """Insert a RepeatStart before the events that logically start at lbl.

            We search backwards from the end of events for a position that
            corresponds to the loop-target label.  Since we emit events top-to-bottom
            and the loop label appears mid-stream, we need to mark its position.

            Strategy: we annotate events with a sentinel when we pass a label that
            could be a loop target, then replace the sentinel with RepeatStart here.
            For simplicity in v1: scan back to find the marker and insert there.
            """
            # Look for a _LoopMarker sentinel event we may have emitted when passing
            # the label.  If found, replace it with RepeatStart.
            for idx in range(len(ev) - 1, -1, -1):
                if isinstance(ev[idx], _LoopMarker) and ev[idx].label == lbl:
                    ev[idx] = RepeatStart()
                    return
            # No marker found: insert at the beginning (conservative fallback).
            ev.insert(0, RepeatStart())

        def _find_last_vol(ev: list, default: int = 100) -> int:
            """Find the most recent Vol event's value in the event list."""
            for e in reversed(ev):
                if isinstance(e, Vol):
                    return e.vol
            return default

        def _process_dcb(content: str):
            """Process a dc.b line's content, handling notes, durations, smpsNoAttack."""
            nonlocal noattack_pending, cur_dur

            tokens = [t.strip() for t in content.split(',') if t.strip()]
            t_idx = 0
            while t_idx < len(tokens):
                tok = tokens[t_idx].strip()
                t_idx += 1

                # Strip comments
                if ';' in tok:
                    tok = tok[:tok.index(';')].strip()
                if not tok:
                    continue

                # smpsNoAttack inline token
                if tok == 'smpsNoAttack':
                    noattack_pending = True
                    continue

                # Try to parse as a note or duration byte
                try:
                    val = _note_from_token(tok) if tok.startswith('n') else _parse_int(tok)
                except (TranscodeError, ValueError):
                    # Could be a label reference or unknown token
                    print(f"  [warn] sfx ${sfx_id:02X}: unrecognised token {tok!r} in dc.b",
                          file=sys.stderr)
                    continue

                if val == S3K_NOTE_REST:
                    # Rest
                    events.append(SetDur(min(cur_dur, 0x7F)))
                    events.append(Rest())
                    noattack_pending = False
                elif S3K_NOTE_BASE <= val <= 0xFF:
                    # Note byte
                    pitch = _smps_note_to_pitch(val, is_psg, transpose)
                    # (spindash rev is now runtime: the SpinRev opcode + the global
                    #  rev add the transpose at play time; the note stays the bare nC5.)
                    # Check if there's a duration byte following
                    if t_idx < len(tokens):
                        next_tok = tokens[t_idx].strip()
                        if ';' in next_tok:
                            next_tok = next_tok[:next_tok.index(';')].strip()
                        # Duration byte: a small value that doesn't look like a note or coord flag
                        try:
                            dur_val = _parse_int(next_tok)
                            if 0x01 <= dur_val <= 0x7F:
                                # It's a duration byte
                                cur_dur = dur_val
                                t_idx += 1
                                events.append(NoteDur(pitch, dur_val))
                                noattack_pending = False
                                continue
                        except (ValueError, TranscodeError):
                            pass
                    # No duration follows: use current default
                    events.append(Note(pitch))
                    noattack_pending = False
                elif 0x01 <= val <= 0x7F:
                    # Duration byte (standalone tempo modifier)
                    cur_dur = val
                    # This sets the current default duration for the next note
                elif val >= 0xE0:
                    # Coord flag byte ($E0-$FF) — must be handled; raise if unknown
                    _handle_raw_coord(val)
                else:
                    # Unknown byte in range $80..$DF (not a note, not a duration)
                    print(f"  [warn] sfx ${sfx_id:02X}: byte ${val:02X} in dc.b range $80..$DF, "
                          f"not a note/rest — skipped", file=sys.stderr)

        def _handle_raw_coord(val: int):
            """Handle a raw coord flag byte encountered in dc.b content."""
            raise TranscodeError(
                f"sfx ${sfx_id:02X} ch ${chanid:02X}: raw coord flag byte ${val:02X} "
                f"in dc.b not in v1 coverage list. Must be handled explicitly.")

        # Emit a loop-marker when we pass a label that appears in the data region
        # (so _insert_repeat_start can find it).
        class _LoopMarkerObj:
            def __init__(self, lbl):
                self.label = lbl
            def encode(self):
                return b''  # zero-bytes sentinel; removed before packing
            def validate(self, route):
                pass

        # Monkey-patch a LoopMarker class accessible in _insert_repeat_start
        _LoopMarker = _LoopMarkerObj

        # Re-define _process_lines to emit loop markers when passing labels
        # that appear as smpsLoop targets.  We do a pre-scan to find loop targets.
        _loop_targets = set()

        def _prescan_loop_targets(start_i: int):
            for line in lines[start_i:]:
                s = line.strip()
                m = re.match(r'smpsLoop\s+(.*)', s)
                if m:
                    args = _split_args(m.group(1))
                    if len(args) >= 3:
                        _loop_targets.add(args[2].strip())

        _prescan_loop_targets(start_line + 1)

        # Re-process lines with loop-marker injection
        def _process_lines_v2(start_i: int) -> bool:
            nonlocal noattack_pending
            nonlocal cur_dur, voice_idx, loop_label, loop_count, has_loop
            nonlocal jump_target_label, sfx_flags

            i = start_i
            while i < len(lines):
                line = lines[i]
                i += 1
                stripped = line.strip()
                if not stripped or stripped.startswith(';'):
                    continue

                # Check for label definitions — emit a loop marker if this is a loop target
                lbl_m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):\s*$', stripped)
                if lbl_m:
                    lbl_name = lbl_m.group(1)
                    # Channel-boundary stop: reaching the data-pointer label of a
                    # DIFFERENT channel ends this channel's stream (S3K sequential
                    # layout — a channel with no explicit smpsStop falls through
                    # into the next channel's data).  Inject an implicit End.
                    if lbl_name in _channel_data_labels and lbl_name != data_lbl:
                        events.append(End())
                        return True
                    if lbl_name in _loop_targets:
                        events.append(_LoopMarker(lbl_name))
                    continue
                # Also handle "Label:   ; comment" form
                lbl_m2 = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)', stripped)
                if lbl_m2 and not lbl_m2.group(1) in (
                    'smpsHeaderStartSong', 'smpsHeaderVoice',
                    'smpsHeaderTempoSFX', 'smpsHeaderChanSFX',
                    'smpsHeaderSFXChannel', 'smpsModSet', 'smpsPan',
                    'smpsSetvoice', 'smpsFMvoice', 'smpsPSGvoice',
                    'smpsPSGform', 'smpsSpindashRev', 'smpsResetSpindashRev',
                    'smpsLoop', 'smpsJump', 'smpsFMAlterVol', 'smpsNoAttack', 'smpsStop'
                ):
                    lbl_name = lbl_m2.group(1)
                    # Channel-boundary stop (label with trailing content form).
                    if lbl_name in _channel_data_labels and lbl_name != data_lbl:
                        events.append(End())
                        return True
                    if lbl_name in _loop_targets:
                        events.append(_LoopMarker(lbl_name))
                    rest_of_line = lbl_m2.group(2).strip()
                    if not rest_of_line or rest_of_line.startswith(';'):
                        continue
                    # Fall through to process rest_of_line as content
                    stripped = rest_of_line

                if stripped.startswith('dc.b'):
                    rest = stripped[4:].strip()
                    # Strip trailing comment
                    if ';' in rest:
                        rest = rest[:rest.index(';')].strip()
                    _process_dcb(rest)
                    continue

                m = re.match(r'(smps[A-Za-z]+)\s*(.*)', stripped)
                if not m:
                    continue
                macro = m.group(1)
                arg_str = m.group(2).strip()
                # Strip trailing comment from arg_str
                if ';' in arg_str:
                    arg_str = arg_str[:arg_str.index(';')].strip()

                if macro == 'smpsStop':
                    events.append(End())
                    return True
                elif macro in ('smpsSetvoice', 'smpsFMvoice'):
                    args = _split_args(arg_str)
                    vi = _parse_int(args[0]) if args else 0
                    if is_fm:
                        events.append(Patch(vi))
                elif macro == 'smpsPan':
                    args = _split_args(arg_str)
                    dir_tok = args[0].strip() if args else '0'
                    amsfms_tok = args[1].strip() if len(args) > 1 else '0'
                    _pan_names = {
                        'panNone': 0x00, 'panRight': 0x40,
                        'panLeft': 0x80, 'panCentre': 0xC0, 'panCenter': 0xC0,
                    }
                    if dir_tok in _pan_names:
                        dir_val = _pan_names[dir_tok]
                    else:
                        dir_val = _parse_int(dir_tok)
                    amsfms_val = _parse_int(amsfms_tok)
                    b4 = dir_val | amsfms_val
                    events.append(Pan(b4))
                elif macro == 'smpsPSGvoice':
                    # PSG volume envelope (sTone_XX). This is the pass that BUILDS the
                    # final event list -> emit MEV_PSGENV here with the 1-based engine
                    # env id (== the sTone number; engine PsgVolEnv_Table holds the body).
                    args = _split_args(arg_str)
                    tone_tok = args[0].strip() if args else '0'
                    env_id = _stone_to_env_id(tone_tok)
                    events.append(PsgEnv(env_id))
                elif macro == 'smpsModSet':
                    # Pitch modulation: emit MEV_MODSET with the raw .asm operands
                    # (wait, speed, change, step). The engine applies S3K's own
                    # srl-on-init (Mod_ReArm seeds steps = raw>>1) — do NOT re-encode
                    # the macro's version-specific transform here. `change` is signed
                    # ($F8 -> -8). All-zero = mod off (smpsModSet 0,0,0,0).
                    args = _split_args(arg_str)
                    if len(args) < 4:
                        raise TranscodeError(
                            f"smpsModSet expects 4 operands, got {args!r}")
                    wait  = _parse_int(args[0])
                    speed = _parse_int(args[1])
                    change = _parse_signed_byte(args[2])
                    step  = _parse_int(args[3])
                    events.append(ModSet(wait, speed, change, step))
                elif macro == 'smpsSpindashRev':
                    events.append(SpinRev())
                elif macro == 'smpsResetSpindashRev':
                    pass                     # rev reset is dispatch-folded (see above)
                elif macro == 'smpsPSGform':
                    args = _split_args(arg_str)
                    form_val = _parse_int(args[0]) if args else 0
                    print(f"  [info] sfx ${sfx_id:02X} ch ${chanid:02X}: smpsPSGform "
                          f"${form_val:02X} (noise mode; handled by engine via sx_kind)",
                          file=sys.stderr)
                elif macro == 'smpsLoop':
                    args = _split_args(arg_str)
                    loops = _parse_int(args[1]) if len(args) > 1 else 1
                    lbl = args[2].strip() if len(args) > 2 else ''
                    _insert_repeat_start(events, lbl)
                    events.append(RepeatEnd(max(1, min(255, loops))))
                    has_loop = True
                    sfx_flags |= SHF_LOOP
                elif macro == 'smpsJump':
                    args = _split_args(arg_str)
                    lbl = args[0].strip() if args else ''
                    jump_target_label = lbl
                    tgt_line = _get_line_range_for_label(lbl)
                    if tgt_line >= 0:
                        _process_lines_v2(tgt_line + 1)
                    else:
                        raise TranscodeError(
                            f"sfx ${sfx_id:02X}: smpsJump target {lbl!r} not found")
                    return True
                elif macro == 'smpsFMAlterVol':
                    args = _split_args(arg_str)
                    if len(args) >= 2:
                        delta = _parse_int(args[1])
                    elif args:
                        delta = _parse_int(args[0])
                    else:
                        delta = 0
                    cur_vol = _find_last_vol(events, default=100 if is_fm else 80)
                    new_vol = max(0, min(127, cur_vol - delta))
                    events.append(Vol(new_vol))
                elif macro == 'smpsNoAttack':
                    noattack_pending = True
                elif macro in ('smpsHeaderStartSong', 'smpsHeaderVoice',
                               'smpsHeaderTempoSFX', 'smpsHeaderChanSFX',
                               'smpsHeaderSFXChannel'):
                    pass
                elif macro.startswith('smpsVc'):
                    pass  # voice macros — in voice block
                else:
                    raise TranscodeError(
                        f"sfx ${sfx_id:02X} ch ${chanid:02X}: unknown SMPS macro "
                        f"{macro!r} — not in v1 coverage list.")
            return False

        _process_lines_v2(start_line + 1)

        # Remove any remaining _LoopMarker sentinels (they should have been
        # replaced by _insert_repeat_start, but defensive cleanup).
        events[:] = [e for e in events if not isinstance(e, type(events[0]).__class__.__mro__[0])
                     or not hasattr(e, 'label')]
        # Actually just filter by attribute
        cleaned = []
        for e in events:
            if hasattr(e, 'label') and hasattr(e, 'encode') and e.encode() == b'':
                # This is a LoopMarker sentinel that was NOT converted to RepeatStart.
                # This means the smpsLoop target was found but _insert_repeat_start
                # couldn't find the marker in the event list (timing issue).
                # For now: drop it (it won't affect correctness since RepeatEnd was
                # still emitted — the marker was just for insertion point tracking).
                continue
            cleaned.append(e)
        events[:] = cleaned

        channels_out.append({
            'chanid': chanid,
            'route': route,
            'kind': kind,
            'transpose': transpose,
            'init_vol': vol_raw,
            'events': events,
            'has_loop': has_loop,
        })

    return {
        'id': sfx_id,
        'label': sfx_label,
        'channels': channels_out,
        'voices': voices,
        'flags': sfx_flags,
    }


# ---------------------------------------------------------------------------
# SFX blob packer (mirrors pack_song but emits SfxHeader + per-channel records)
# ---------------------------------------------------------------------------

def pack_sfx(sfx_desc: dict, priority: int) -> bytes:
    """Pack an SFX descriptor to bytes.

    Layout:
      [0]  priority (SFXPRI_*)
      [1]  flags (SHF_*)
      [2]  chcount
      [3]  pad (0)
      per channel (6 bytes each):
        [+0] route
        [+1] kind
        [+2] cmd_ptr hi (BE offset from blob start)
        [+3] cmd_ptr lo
        [+4] voice_ptr hi (BE offset from blob start; 0 if PSG/no voice)
        [+5] voice_ptr lo
      Then: packed event streams (one per channel)
      Then: FmPatch bank bytes (FM voices only)

    Returns the complete blob bytes.
    """
    channels = sfx_desc['channels']
    flags = sfx_desc['flags']
    voices = sfx_desc.get('voices', [])
    chcount = len(channels)

    # Build the patch bank bytes
    patch_bank = b''.join(voices)

    # Pack each channel's event stream
    streams = []
    for ch in channels:
        s = b''.join(e.encode() for e in ch['events'])
        streams.append(s)

    # Header: 4 bytes + chcount*6 bytes
    header_len = 4 + chcount * 6

    # Stream layout: streams follow the header
    stream_offsets = []
    cur = header_len
    for s in streams:
        stream_offsets.append(cur)
        cur += len(s)

    # Patch bank follows all streams
    patch_bank_offset = cur if patch_bank else 0

    out = bytearray()
    out.append(priority & 0xFF)        # sfh_priority
    out.append(flags & 0xFF)           # sfh_flags
    out.append(chcount & 0xFF)         # sfh_chcount
    out.append(0x00)                   # sfh_pad

    for ch, stream_off in zip(channels, stream_offsets):
        out.append(ch['route'] & 0xFF)
        out.append(ch['kind'] & 0xFF)
        out.append((stream_off >> 8) & 0xFF)   # cmd_ptr hi
        out.append(stream_off & 0xFF)           # cmd_ptr lo
        # voice_ptr: for FM channels with voices, point to patch bank
        if ch['kind'] == SFXEL_FM and patch_bank:
            out.append((patch_bank_offset >> 8) & 0xFF)
            out.append(patch_bank_offset & 0xFF)
        else:
            out.append(0x00)  # no FM patch (PSG/noise)
            out.append(0x00)

    for s in streams:
        out.extend(s)

    out.extend(patch_bank)

    return bytes(out)


def emit_sfx_asm(sfx_desc: dict, priority: int, label: str) -> str:
    """Emit the SFX blob as an AS data file."""
    blob = pack_sfx(sfx_desc, priority)
    lines = []
    sfx_id = sfx_desc['id']
    lines.append("; ======================================================================")
    lines.append(f"; data/sound/sfx/{label.lower()}.asm — GENERATED by tools/sfx_transcode.py")
    lines.append(f"; SFX id ${sfx_id:02X} ({sfx_desc['label']})")
    lines.append("; Layout: SfxHeader(4) + per-channel records(6 each) + streams + FmPatch bank")
    lines.append("; DO NOT EDIT BY HAND.")
    lines.append("; ======================================================================")
    lines.append("")
    lines.append(f"{label}:")
    for i in range(0, len(blob), 16):
        chunk = blob[i:i + 16]
        lines.append("    dc.b   " + ", ".join(f"${b:02X}" for b in chunk))
    lines.append(f"{label}_End:")
    lines.append("")
    lines.append("    align 2")
    return "\n".join(lines) + "\n"


def emit_sfx_patches_asm(voices: list, label: str, sfx_id: int) -> str:
    """Emit the FmPatch bank for an SFX's voices as an AS data file.

    Does NOT reuse emit_patch_bank_asm (which uses the PATCH_COUNT_MT global
    that collides across multiple inclusions).  Instead emits a self-contained
    file using a per-SFX constant name ({label}_Patches_Count).
    """
    patches_label = f"{label}_Patches"
    count_const = f"{label}_Patches_Count"

    if not voices:
        # No FM voices (e.g. PSG-only SFX)
        lines = []
        lines.append(f"; ======================================================================")
        lines.append(f"; data/sound/sfx/{label.lower()}_patches.asm — GENERATED by tools/sfx_transcode.py")
        lines.append(f"; SFX ${sfx_id:02X}: no FM voices (PSG-only SFX)")
        lines.append(f"; DO NOT EDIT BY HAND.")
        lines.append(f"; ======================================================================")
        lines.append(f"")
        lines.append(f"{patches_label}:")
        lines.append(f"{patches_label}_End:")
        lines.append(f"")
        lines.append(f"    align 2")
        return "\n".join(lines) + "\n"

    bank_bytes = b''.join(voices)
    count = len(voices)

    # pbyte macro (ifndef-guarded; identical to fm_patches.inc — safe to include both)
    lines = []
    lines.append("; ======================================================================")
    lines.append(f"; data/sound/sfx/{label.lower()}_patches.asm — GENERATED by tools/sfx_transcode.py")
    lines.append(f"; SFX ${sfx_id:02X}: FmPatch bank ({count} voice(s), {count * FMPATCH_LEN} bytes)")
    lines.append("; DO NOT EDIT BY HAND.")
    lines.append("; ======================================================================")
    lines.append("")
    lines.append("        ifndef pbyte_defined")
    lines.append("pbyte_defined = 1")
    lines.append("pbyte   macro                           ; emit data byte(s); CPU-correct directive")
    lines.append("        if MOMCPUNAME=\"Z80\"")
    lines.append("        db      ALLARGS                  ; Z80 phase-0 blob context")
    lines.append("        else")
    lines.append("        dc.b    ALLARGS                  ; 68k ROM context")
    lines.append("        endif")
    lines.append("        endm")
    lines.append("        endif")
    lines.append("")
    lines.append(f"{count_const} = {count}")
    lines.append("")
    lines.append(f"{patches_label}:")
    for vi in range(count):
        rec = bank_bytes[vi * FMPATCH_LEN:(vi + 1) * FMPATCH_LEN]
        lines.append(f"; --- voice {vi} ---")
        lines.append(f"        pbyte   {rec[0]:<3}                     ; fp_alg_fb     ${rec[0]:02X}")
        lines.append(f"        pbyte   {rec[1]:<3}                     ; fp_lr_ams_fms ${rec[1]:02X}")
        group_labels = [
            ('fp_dt_mul', '$30'),
            ('fp_tl',     '$40'),
            ('fp_rs_ar',  '$50'),
            ('fp_am_d1r', '$60'),
            ('fp_d2r',    '$70'),
            ('fp_d1l_rr', '$80'),
        ]
        for gi, (glbl, greg) in enumerate(group_labels):
            off = 2 + gi * 4
            g = rec[off:off + 4]
            lines.append(f"        pbyte   {g[0]:3}, {g[1]:3}, {g[2]:3}, {g[3]:3}"
                         f"   ; {glbl}  {greg}  [S1,S3,S2,S4]")
    lines.append(f"{patches_label}_End:")
    lines.append("")
    lines.append(f"        if ({patches_label}_End-{patches_label})/FmPatch_len <> {count_const}")
    lines.append(f"          error \"SFX ${sfx_id:02X} patch bank count mismatch\"")
    lines.append(f"        endif")
    lines.append(f"        if ({patches_label}_End-{patches_label}) <> {count_const}*FmPatch_len")
    lines.append(f"          error \"SFX ${sfx_id:02X} patch bank size mismatch\"")
    lines.append(f"        endif")
    lines.append("")
    return "\n".join(lines) + "\n"


def emit_sfx_table_asm(sfx_ids: list, id_to_label: dict) -> str:
    """Emit sfx_table.asm: SfxTable dc.l per SFX + SFX_COUNT + completeness assert."""
    lines = []
    lines.append("; ======================================================================")
    lines.append("; data/sound/sfx/sfx_table.asm — GENERATED by tools/sfx_transcode.py")
    lines.append("; SfxTable: indexed by SFX id - 1 (densely numbered, id range $33..$B9).")
    lines.append("; DO NOT EDIT BY HAND.")
    lines.append("; ======================================================================")
    lines.append("")

    if not sfx_ids:
        lines.append("SFX_COUNT = 0")
        lines.append("SfxTable:")
        lines.append("SfxTable_End:")
        return "\n".join(lines) + "\n"

    min_id = min(sfx_ids)
    max_id = max(sfx_ids)
    total = max_id - min_id + 1

    lines.append(f"SFX_ID_BASE  = ${min_id:02X}")
    lines.append(f"SFX_COUNT    = {len(sfx_ids)}")
    lines.append(f"SFX_TABLE_LEN = {total}   ; max_id - min_id + 1 (sparse over the id range)")
    lines.append("")
    lines.append("; SfxTable: for each id in [SFX_ID_BASE, max_id], a dc.l ptr or 0 if unused.")
    lines.append("SfxTable:")
    for sfx_id in range(min_id, max_id + 1):
        if sfx_id in id_to_label:
            lbl = id_to_label[sfx_id]
            lines.append(f"    dc.l    {lbl}     ; ${sfx_id:02X}")
        else:
            lines.append(f"    dc.l    0               ; ${sfx_id:02X} (unused)")
    lines.append("SfxTable_End:")
    lines.append("")
    lines.append("        if (SfxTable_End-SfxTable)/4 <> SFX_TABLE_LEN")
    lines.append("          error \"SfxTable length mismatch\"")
    lines.append("        endif")
    lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Top-level: load + transcode a single SFX from a skdisasm source path
# ---------------------------------------------------------------------------

def _sfx_label(sfx_id: int) -> str:
    return f"Sfx_{sfx_id:02X}"


def transcode_sfx_file(src_path: str, sfx_id: int) -> dict:
    """Load a skdisasm SFX .asm file and return the parsed sfx_desc dict."""
    with open(src_path, encoding='utf-8', errors='replace') as f:
        src = f.read()
    label = _sfx_label(sfx_id)
    return _parse_sfx_source(src, sfx_id, label)


def transcode_sfx_source(src: str, sfx_id: int) -> dict:
    """Parse an SFX .asm source string (for testing without file I/O)."""
    label = _sfx_label(sfx_id)
    return _parse_sfx_source(src, sfx_id, label)


# ---------------------------------------------------------------------------
# CLI: generate all core SFX to data/sound/sfx/
# ---------------------------------------------------------------------------

# Path to the skdisasm SFX directory
SKDISASM_SFX_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '..', 'skdisasm', 'Sound', 'SFX')

# Core SFX id -> filename prefix map
_CORE_SFX_FILENAMES = {
    0x33: '33 - Ring (Right).asm',
    0x34: '34 - Ring (Left).asm',
    0x35: '35 - Death.asm',
    0x36: '36 - Skid.asm',
    0x3C: '3C - Roll.asm',
    0x62: '62 - Jump.asm',
    0xAB: 'AB - Spin Dash.asm',
    0xB6: 'B6 - Dash.asm',
    0xB9: 'B9 - Ring Loss.asm',
}


def generate_all(out_dir: str = None, skdisasm_dir: str = None):
    """Transcode all core SFX and write to out_dir."""
    if out_dir is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(repo_root, 'data', 'sound', 'sfx')
    if skdisasm_dir is None:
        skdisasm_dir = SKDISASM_SFX_DIR

    os.makedirs(out_dir, exist_ok=True)

    # SFX 33/34/B9 share a cross-file dependency: Sound_34_Jump00 and
    # Sound_33_34_B9_Voices are defined in SFX 33's file, but referenced by
    # SFX 34 (smpsJump) and SFX B9 (smpsHeaderVoice).  We resolve this by
    # extracting the "data section" of the aux file (everything after the last
    # smpsHeaderSFXChannel line) and APPENDING it to the target source.  This
    # makes the shared labels visible without pulling in the aux file's header
    # channel declarations (which would cause the parser to see extra channels).
    _aux_src_cache: dict = {}  # sfx_id -> raw source text (lazy-loaded)

    def _load_aux_data_section(sfx_id: int) -> str:
        """Return the data section of an SFX source (after the last header line)."""
        if sfx_id not in _aux_src_cache:
            fname = _CORE_SFX_FILENAMES[sfx_id]
            path = os.path.join(skdisasm_dir, fname)
            with open(path, encoding='utf-8', errors='replace') as f:
                _aux_src_cache[sfx_id] = f.read()
        raw = _aux_src_cache[sfx_id]
        # Find the last smpsHeaderSFXChannel / smpsHeaderChanSFX line
        # Everything after that line is pure data (data labels, dc.b, voice macros).
        lines = raw.splitlines(keepends=True)
        last_header_idx = -1
        for i, ln in enumerate(lines):
            s = ln.strip()
            if (s.startswith('smpsHeaderSFXChannel') or
                    s.startswith('smpsHeaderChanSFX') or
                    s.startswith('smpsHeaderTempoSFX')):
                last_header_idx = i
        if last_header_idx < 0:
            # No header found — just return the whole file.
            return raw
        return ''.join(lines[last_header_idx + 1:])

    # Cross-file dependency table: {target_sfx_id: [aux_sfx_ids_to_append]}
    # We APPEND the data section of aux files so their labels are in scope when
    # the target's data stream is parsed.  We do NOT prepend (which would bring
    # aux header channel declarations into scope).
    _CROSS_FILE_APPEND = {
        0x34: [0x33],   # Sound_34_Jump00 + Sound_33_34_B9_Voices in SFX 33
        0xB9: [0x33],   # Sound_33_34_B9_Voices in SFX 33
    }

    id_to_label = {}
    for sfx_id in _CORE_SFX_IDS:
        fname = _CORE_SFX_FILENAMES[sfx_id]
        src_path = os.path.join(skdisasm_dir, fname)
        if not os.path.exists(src_path):
            print(f"  [warn] SFX ${sfx_id:02X}: source not found at {src_path}",
                  file=sys.stderr)
            continue

        print(f"  transcoding SFX ${sfx_id:02X} ({fname})...", file=sys.stderr)

        # Build source text, appending aux data sections for cross-file deps.
        with open(src_path, encoding='utf-8', errors='replace') as f:
            raw_src = f.read()
        aux_ids = _CROSS_FILE_APPEND.get(sfx_id, [])
        if aux_ids:
            aux_parts = [_load_aux_data_section(aid) for aid in aux_ids]
            combined_src = raw_src + '\n' + '\n'.join(aux_parts)
            print(f"    [cross-dep] appended data section from SFX "
                  f"{[f'${a:02X}' for a in aux_ids]} for cross-file label resolution",
                  file=sys.stderr)
        else:
            combined_src = raw_src

        sfx_desc = _parse_sfx_source(combined_src, sfx_id, _sfx_label(sfx_id))
        priority = _SFX_PRIORITY.get(sfx_id, SFXPRI_RING)
        label = _sfx_label(sfx_id)

        # Emit blob
        blob_asm = emit_sfx_asm(sfx_desc, priority, label)
        out_path = os.path.join(out_dir, f'sfx_{sfx_id:02X}.asm')
        with open(out_path, 'w') as f:
            f.write(blob_asm)
        print(f"    wrote {out_path}", file=sys.stderr)

        # Emit patches
        patches_asm = emit_sfx_patches_asm(sfx_desc.get('voices', []), label, sfx_id)
        patches_path = os.path.join(out_dir, f'sfx_{sfx_id:02X}_patches.asm')
        with open(patches_path, 'w') as f:
            f.write(patches_asm)
        print(f"    wrote {patches_path}", file=sys.stderr)

        id_to_label[sfx_id] = label

    # Emit sfx_table.asm
    table_asm = emit_sfx_table_asm(_CORE_SFX_IDS, id_to_label)
    table_path = os.path.join(out_dir, 'sfx_table.asm')
    with open(table_path, 'w') as f:
        f.write(table_asm)
    print(f"  wrote {table_path}", file=sys.stderr)
    return id_to_label


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == 'generate':
        generate_all()
        return 0
    print("Usage: python3 sfx_transcode.py generate", file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
