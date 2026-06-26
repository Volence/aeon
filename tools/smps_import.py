# tools/smps_import.py  — SMPS (S3K) -> music-format-v0 converter.
import os, sys, re
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from song_packer import (
    Note, Rest, SetDur, NoteDur, Vol, Patch, Pan, ModSet, PsgEnv, NoteFill,
    Dac, End, LoopPoint, Jump, MEV_NOTE_BASE, MAX_DUR,
    SongDesc, ChannelDesc, SH_F_STREAM,
    CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5,
    CHROUTE_PSG1, CHROUTE_PSG2, CHROUTE_PSG3, CHROUTE_DAC,
)

# ---------------------------------------------------------------------------
# Note bytes — _smps2asm_inc.asm lines 31-47
#
# The enum starts at nRst=$80, then nC0=$81 and increments by 1 per step.
# Canonical note names per semitone within an octave (12 semitones):
#   C Cs D Ds E F Fs G Gs A As B
# Flat / enharmonic aliases (from the enum, e.g. nEb0=nDs0):
#   Db=Cs, Eb=Ds, Fb=E,  Gb=Fs, Ab=Gs, Bb=As
#   Es=F   (nEs0 is the next counter value after nE0; nF0=nEs0)
#   Cb(N) = B(N-1)        (cross-octave alias, nCb1=nB0)
#   Bs(N) = C(N+1)        (cross-octave alias, nBs0=nC1)
#
# For PSG channels (SonicDriverVer>=3, _smps2asm_inc.asm lines 58-59):
#   nMaxPSG1 = nBb6 = $D3
#   nMaxPSG2 = nB6  = $D4
_NOTE_NAMES = ["C", "Cs", "D", "Ds", "E", "F", "Fs", "G", "Gs", "A", "As", "B"]
NOTE_BYTES: dict[str, int] = {}

# nRst — _smps2asm_inc.asm line 31
NOTE_BYTES["nRst"] = 0x80

for _oct in range(8):
    for _i, _n in enumerate(_NOTE_NAMES):
        NOTE_BYTES["n%s%d" % (_n, _oct)] = 0x81 + _oct * 12 + _i

# Flat aliases: Db=Cs, Eb=Ds, Fb=E, Gb=Fs, Ab=Gs, Bb=As  (per octave)
_FLAT_ALIASES = [("Db", "Cs"), ("Eb", "Ds"), ("Fb", "E"),
                 ("Gb", "Fs"), ("Ab", "Gs"), ("Bb", "As")]
for _oct in range(8):
    for _flat, _sharp in _FLAT_ALIASES:
        NOTE_BYTES["n%s%d" % (_flat, _oct)] = NOTE_BYTES["n%s%d" % (_sharp, _oct)]

# Sharp-above aliases: Es(N)=F(N) (same octave)
for _oct in range(8):
    NOTE_BYTES["nEs%d" % _oct] = NOTE_BYTES["nF%d" % _oct]

# Cross-octave aliases: Bs(N)=C(N+1), Cb(N)=B(N-1)
for _oct in range(7):
    NOTE_BYTES["nBs%d" % _oct] = NOTE_BYTES["nC%d" % (_oct + 1)]
for _oct in range(1, 8):
    NOTE_BYTES["nCb%d" % _oct] = NOTE_BYTES["nB%d" % (_oct - 1)]

# PSG max-note constants (SonicDriverVer>=3) — _smps2asm_inc.asm lines 58-59
# nMaxPSG1 = nBb6 = nAs6 = 0x81 + 6*12 + 10 = 0xD3
# nMaxPSG2 = nB6          = 0x81 + 6*12 + 11 = 0xD4
NOTE_BYTES["nMaxPSG1"] = NOTE_BYTES["nAs6"]   # nBb6 = nAs6 = 0xD3
NOTE_BYTES["nMaxPSG2"] = NOTE_BYTES["nB6"]    # 0xD4

# ---------------------------------------------------------------------------
# Pan bytes — used as args to smpsPan macro
PAN_BYTES = {"panLeft": 0x80, "panRight": 0x40, "panCenter": 0xC0, "panNone": 0x00}

# ---------------------------------------------------------------------------
# Driver-v3 DAC enum (_smps2asm_inc.asm lines 96-113, case 3).
# Only the HCZ2 set is required; extend as needed.
DAC_IDS = {
    "dSnareS3": 0x81, "dHighTom": 0x82, "dMidTomS3": 0x83, "dLowTomS3": 0x84,
    "dFloorTomS3": 0x85, "dKickS3": 0x86,
}

# ---------------------------------------------------------------------------
# HCZ2 DAC remap: raw S3K 1-based DAC id (dXxx & 0x7F) -> v0 DacSampleTable id.
# Dac() carries the 1-based id (smps_import emits `Dac(b & 0x7F)`); convert_song's
# dac_remap rewrites it to the engine's DacSampleTable id. The v0 ids are the 6
# S3K HCZ2 drums appended in Phase 5 (engine/z80_sound_driver.asm DacSampleTable,
# data/sound/dac_samples.asm): kick=5 snare=6 hitom=7 midtom=8 lowtom=9 floortom=10.
#   dSnareS3   $81  -> 1-based 1  -> v0 id 6
#   dHighTom   $82  -> 1-based 2  -> v0 id 7
#   dMidTomS3  $83  -> 1-based 3  -> v0 id 8
#   dLowTomS3  $84  -> 1-based 4  -> v0 id 9
#   dFloorTomS3 $85 -> 1-based 5  -> v0 id 10
#   dKickS3    $86  -> 1-based 6  -> v0 id 5
HCZ2_DAC_REMAP = {
    1: 6,   # dSnareS3   -> s3k_snare
    2: 7,   # dHighTom   -> s3k_hitom
    3: 8,   # dMidTomS3  -> s3k_midtom
    4: 9,   # dLowTomS3  -> s3k_lowtom
    5: 10,  # dFloorTomS3-> s3k_floortom
    6: 5,   # dKickS3    -> s3k_kick
}

# ---------------------------------------------------------------------------
# Coordination-flag byte values — _smps2asm_inc.asm
#
# These constants appear INLINE as dc.b args (e.g. "dc.b nMaxPSG1, $06, smpsNoAttack, $06").
# Phase 2 handles them as leading mnemonics via tokenize_line dispatch (not changed here).
# Only scalar EQU values are listed; multi-byte macros (smpsStop=$F2, etc.) cannot
# appear as raw dc.b args and are NOT included.
#
# smpsNoAttack EQU $E7  — _smps2asm_inc.asm line 457
FLAG_BYTES: dict[str, int] = {
    "smpsNoAttack": 0xE7,   # line 457: prevent attack on next note (scalar EQU)
}

# ---------------------------------------------------------------------------

def resolve_const(tok: str) -> int:
    tok = tok.strip()
    if tok.startswith("$"):
        return int(tok[1:], 16)
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    for table in (NOTE_BYTES, PAN_BYTES, DAC_IDS, FLAG_BYTES):
        if tok in table:
            return table[tok]
    # PSG tone/envelope names: sTone_NN -> the hex number NN. The numeric id is
    # the S3K PSG-envelope index; v1 does not import those envelopes (see
    # _dispatch_flag smpsPSGvoice), but resolving the constant lets the header
    # parser and any inline use succeed instead of KeyError-ing.
    m = re.fullmatch(r"sTone_([0-9A-Fa-f]{1,2})", tok)
    if m:
        return int(m.group(1), 16)
    raise KeyError("unknown SMPS constant: %r" % tok)

class ChannelHdr:
    def __init__(self, kind, label, transpose=0, volume=None, psg_voice=None):
        self.kind = kind          # "FM" | "PSG" | "DAC"
        self.label = label
        self.transpose = transpose
        # `volume` is the channel VOLUME (attenuation) — the 3rd smpsHeader* arg.
        # VERIFIED against skdisasm/Sound/_smps2asm_inc.asm:332
        # (smpsHeaderFM macro loc,pitch,vol): the 3rd arg is the channel volume,
        # NOT a voice index. The FM voice comes from an in-body smpsSetvoice.
        self.volume = volume
        # PSG only: the header's 5th arg (smpsHeaderPSG loc,pitch,vol,mod,voice,
        # _smps2asm_inc.asm:338) is the INITIAL PSG volume-envelope id (sTone).
        # Captured here for completeness; v1 import does not replay header PSG
        # envelopes (in-body smpsPSGvoice drives the melody timbre).
        self.psg_voice = psg_voice

class SongConfig:
    def __init__(self):
        self.divider = 1; self.tempo_mod = 0; self.channels = []
    @property
    def tempo_base(self):
        # Engine tempo model: accumulator -= 16/frame; on borrow it re-adds
        # tempo_base and fires one event-tick.  ticks/frame = 16 / tempo_base.
        # SMPS model: accumulator += mod/frame; overflow SKIPS a tick.
        # ticks/frame = (256 - mod) / 256.
        # Match: 16 / tempo_base = (256 - mod) / 256
        #  -> tempo_base = 16 * 256 / (256 - mod) = 4096 / (256 - mod).
        denom = 256 - self.tempo_mod
        if denom <= 0:
            denom = 1
        return max(16, min(255, round(4096 / denom)))

def _signed8(v):
    return v - 256 if v >= 128 else v

def parse_header(lines):
    """Parse SMPS2ASM header lines into a SongConfig.

    smpsHeaderTempo macro signature: div, mod
      args[0] = div  (TempoDivider — per-note duration multiplier, small value e.g. $01)
      args[1] = mod  (tempo accumulator addend, e.g. $25 -> zCurrentTempo)
    """
    cfg = SongConfig()
    for ln in lines:
        mnem, args, _ = tokenize_line(ln)
        if mnem == "smpsHeaderTempo":
            if len(args) < 2:
                raise ValueError("smpsHeaderTempo needs div,mod: %r" % args)
            cfg.divider = resolve_const(args[0])
            cfg.tempo_mod = resolve_const(args[1])
        elif mnem == "smpsHeaderDAC":
            # smpsHeaderDAC macro loc,pitch,vol — volume present but unused for DAC
            # (the DAC route only triggers samples; it has no melodic volume op).
            dac_vol = resolve_const(args[2]) if len(args) >= 3 else None
            cfg.channels.append(ChannelHdr("DAC", args[0], volume=dac_vol))
        elif mnem == "smpsHeaderFM":
            # smpsHeaderFM macro loc,pitch,vol — _smps2asm_inc.asm:332.
            # args[2] is the channel VOLUME (attenuation), not a voice index.
            if len(args) < 3:
                raise ValueError("smpsHeaderFM needs loc,pitch,vol: %r" % args)
            cfg.channels.append(ChannelHdr("FM", args[0],
                transpose=_signed8(resolve_const(args[1])),
                volume=resolve_const(args[2])))
        elif mnem == "smpsHeaderPSG":
            # smpsHeaderPSG macro loc,pitch,vol,mod,voice — _smps2asm_inc.asm:338.
            # args[2] = volume; args[4] (if present) = initial PSG envelope (sTone).
            if len(args) < 3:
                raise ValueError("smpsHeaderPSG needs loc,pitch,vol: %r" % args)
            psg_voice = resolve_const(args[4]) if len(args) >= 5 else None
            cfg.channels.append(ChannelHdr("PSG", args[0],
                transpose=_signed8(resolve_const(args[1])),
                volume=resolve_const(args[2]), psg_voice=psg_voice))
    return cfg

def split_blocks(lines):
    """Return an ordered dict mapping each label to its body lines.

    Lines before the first label are ignored (the header section is handled
    separately by parse_header). Blank/comment-only lines within a block are
    also dropped so callers get only actionable content.

    Style assumption (skdisasm convention): labels occupy their own line
    (e.g. "Snd_HCZ2_FM1:"), never sharing a line with code ("Label: dc.b ...").
    Constant definitions ("EQU"/"=") do not appear inside channel blocks in
    HCZ2-style sources. Both constraints hold for all skdisasm songs.
    """
    blocks, cur = {}, None
    for ln in lines:
        _, _, label = tokenize_line(ln)
        if label is not None:
            cur = label; blocks[cur] = []
        elif cur is not None and ln.split(";", 1)[0].strip():
            blocks[cur].append(ln)
    return blocks

# ---------------------------------------------------------------------------
# Channel conversion: SMPS byte stream -> music-format-v0 events.
#
# The SMPS duration model (verified vs skdisasm "Sound/Z80 Sound Driver.asm"
# zGetNextNote / zGetNoteDuration, ~lines 907-1060):
#
# Per-channel the byte stream is walked. A byte is classified by value:
#   >= $E0 ($E0..$FF) : coordination flag.
#   $81..$DF          : a NOTE. pitch_index = (byte - $81) + transpose.
#   $80               : a REST.
#   $00..$7F          : a bare DURATION byte (sets the saved/default duration).
#
# After a note OR a rest, the driver PEEKS the next byte (zGetNoteDuration):
#   - if it is < $80, that byte is THIS note/rest's duration; consume it AND
#     store it as the channel's SavedDuration (the new default).
#   - otherwise reuse SavedDuration (do NOT consume the next byte).
# Final ticks for the note/rest = raw_dur * cfg.divider (zComputeNoteDuration).
#
# Format-v0 emit: track the last-emitted default duration (st.cur_dur). When a
# computed dur differs from the default and fits in $00..$7F, emit SetDur(dur)
# (updating the default) before the Note/Rest. When dur > $7F (divider overflow),
# emit NoteDur(pitch, dur) instead and DON'T touch the default. Rests likewise
# get a preceding SetDur on change (a Rest carries no inline duration in v0).
#
# Coordination flags reach the walk two ways:
#   (a) line-leading macros  -> ('flag', mnem, args) tokens.
#   (b) INLINE inside dc.b    -> ('byte', b) tokens with b >= $E0 (HCZ2 only ever
#       has smpsNoAttack/$E7 inline; it is operand-less).

# Coordination-flag macro mnemonics this converter understands as line-leading
# tokens. Membership here decides ('flag',...) vs warn-skip in the flattener;
# the actual mapping is in _dispatch_flag. (Header/voice macros are NOT here —
# they are handled before channel conversion.)
_FLAG_MNEMONICS = frozenset((
    # Direct coordination flags -> MEV events (_dispatch_flag).
    "smpsPan", "smpsSetvoice", "smpsFMvoice", "smpsModSet", "smpsModOff",
    "smpsPSGvoice", "smpsNoteFill", "smpsStop", "smpsSetVol",
    # Per-channel state (Task 2.3): transpose + volume folding, all in
    # _dispatch_flag.
    "smpsAlterVol", "smpsPSGAlterVol", "smpsSetNote", "smpsChangeTransposition",
    "smpsAlterPitch",
    # Structural control flow (Task 2.3): intercepted by the convert_channel
    # walker BEFORE _dispatch_flag (call-inline / loop-unroll / jump-loopback /
    # return).
    "smpsCall", "smpsReturn", "smpsLoop", "smpsJump",
    # Recognized so the walk never breaks; dropped/approximated v1 fidelity gaps
    # (warned once in _dispatch_flag): fine pitch detune, PSG waveform select.
    "smpsDetune", "smpsAlterNote", "smpsNoAttack", "smpsPSGform",
))


def warn(msg):
    sys.stderr.write("smps_import: WARN: %s\n" % msg)


class ConvState:
    """Mutable per-channel conversion state carried across the byte walk.

    transpose : signed semitone displacement folded into every note pitch (the
                channel header transpose, plus smpsSetNote / smpsChangeTransposition
                folding — Task 2.3).
    volume    : legacy folded-volume slot (kept for back-compat); the live
                running volume is fm_vol_raw / psg_vol_raw below.
    cur_dur   : the current DEFAULT duration already emitted (the v0 stream's
                running SetDur value), in v0 ticks. None until first set, so the
                first note always emits a SetDur.
    tie       : True after an inline smpsNoAttack ($E7) — the next note should be
                tied / no-attack (recorded here so the walk does not misinterpret
                the $E7 byte as a note; the no-attack articulation itself is a v1
                fidelity gap, the note still sounds).
    """
    def __init__(self, transpose=0, volume=None):
        self.transpose = transpose
        self.volume = volume
        self.cur_dur = None
        self.tie = False
        # Running SMPS-domain volume (attenuation): seeded by smpsSetVol, mutated
        # by smpsAlterVol/smpsPSGAlterVol. None until first touched. Kept in the
        # SMPS domain so deltas compose correctly; mapped to the v0 0..127
        # loudness only at emit time. FM and PSG track separately because their
        # SMPS volume domains differ (FM TL-ish attenuation vs PSG 4-bit attn).
        self.fm_vol_raw = None
        self.psg_vol_raw = None
        # Tie-merge tracking (Task 2.4 — smpsNoAttack same-pitch merge).
        # _prev_note_idx : index in `out` of the most recently emitted note event
        #                  (the Note or NoteDur), or None. Used to replace it in-
        #                  place when a same-pitch tie arrives.
        # _prev_pitch    : SMPS pitch index of that note.
        # _prev_note_dur : the tick duration that note was emitted with.
        self._prev_note_idx = None
        self._prev_pitch = None
        self._prev_note_dur = None


def _flatten_tokens(lines):
    """Flatten a channel's source lines into an ordered token list, preserving
    source order. Each token is one of:
        ('byte', int)          — a dc.b/dc.w arg (incl. inline flag bytes >=$E0)
        ('flag', mnem, [args]) — a coordination-flag macro line
    Non-channel mnemonics (smpsHeader*, unknown) are warn-skipped."""
    toks = []
    for ln in lines:
        mnem, args, label = tokenize_line(ln)
        if mnem is None:
            continue                     # blank / comment / stray label
        if mnem in ("dc.b", "dc.w"):
            for a in args:
                toks.append(("byte", resolve_const(a)))
        elif mnem in _FLAG_MNEMONICS:
            toks.append(("flag", mnem, args))
        else:
            warn("skip non-channel mnemonic %s" % mnem)
    return toks


def _smps_vol_to_v0(kind, val):
    """Map an SMPS absolute volume operand to a v0 0..127 volume.
    FM  : SMPS FM volume IS a TL-ish attenuation but the v0 Vol op takes the
          value directly (clamped to 127); the engine handles FM scaling.
    PSG : SMPS PSG volume low nibble is 0..15 attenuation (0=loud, 15=silent);
          v0 wants 0..127 LOUDNESS, so invert + scale."""
    if kind == "FM":
        return min(127, val)
    # PSG / DAC-noise: low nibble is the SN76489 attenuation.
    return int(round((15 - (val & 0x0F)) / 15 * 127))


# Default SMPS-domain volume seeds for a channel that emits a volume delta before
# any absolute set. FM attenuation 0 = full; PSG attenuation 0 = loudest.
_DEFAULT_FM_VOL = 0
_DEFAULT_PSG_VOL = 0


def _alter_vol(kind, want, delta, st, out):
    """Fold a volume delta (smpsAlterVol / smpsPSGAlterVol). `want` is the
    channel-kind the flag legitimately applies to ("FM"/"PSG"); on a mismatched
    channel the flag is a no-op (the driver guards likewise — cfChangePSGVolume
    returns on non-PSG). The running SMPS-domain volume is clamped to its native
    attenuation range, then mapped to a v0 0..127 Vol on emit."""
    if kind != want:
        return                              # flag inapplicable on this channel
    if want == "FM":
        cur = st.fm_vol_raw if st.fm_vol_raw is not None else _DEFAULT_FM_VOL
        cur = max(0, min(127, cur + delta))   # FM attenuation 0..127
        st.fm_vol_raw = cur
        out.append(Vol(_smps_vol_to_v0("FM", cur)))
    else:
        cur = st.psg_vol_raw if st.psg_vol_raw is not None else _DEFAULT_PSG_VOL
        cur = max(0, min(0x0F, cur + delta))  # PSG attenuation 0..15
        st.psg_vol_raw = cur
        out.append(Vol(_smps_vol_to_v0("PSG", cur)))


_psg_env_warned = False
_detune_warned = False


def _warn_psg_env_once():
    global _psg_env_warned
    if not _psg_env_warned:
        warn("PSG-envelope timbre approximated (v1 maps every sTone -> PsgEnv(0);"
             " PSG melody preserved, S3K envelope shape not imported)")
        _psg_env_warned = True


def _warn_detune_once():
    global _detune_warned
    if not _detune_warned:
        warn("smpsDetune/smpsAlterNote (fine pitch detune) dropped in v1")
        _detune_warned = True


def _dispatch_flag(kind, mnem, args, st, out, cfg):
    """Handle one NON-structural ('flag', mnem, args) coordination-flag token.
    Appends 0+ events to `out` and/or mutates per-channel state (transpose,
    running volume). Structural flags (smpsCall/Return/Loop/Jump) are handled by
    the convert_channel walker and never reach here. Unmodeled flags are
    warn-skipped so the walk never breaks (a documented v1 fidelity gap)."""
    if mnem == "smpsPan":
        if kind == "DAC":
            return                                   # pan is meaningless on DAC
        out.append(Pan(resolve_const(args[0])))
    elif mnem in ("smpsSetvoice", "smpsFMvoice"):
        out.append(Patch(resolve_const(args[0])))    # FM patch
    elif mnem == "smpsModSet":
        out.append(ModSet(resolve_const(args[0]), resolve_const(args[1]),
                          _signed8(resolve_const(args[2])), resolve_const(args[3])))
    elif mnem == "smpsModOff":
        out.append(ModSet(0, 0, 0, 0))
    elif mnem == "smpsPSGvoice":
        # PSG voice = an S3K PSG volume-envelope index (sTone_NN). v1 does NOT
        # import those envelope contours, so map every tone to PsgEnv(0) (no
        # envelope = flat PSG tone). The PSG NOTES/melody are preserved; only the
        # S3K envelope SHAPE is approximated — a documented v1 fidelity gap.
        # MEV_PSGENV is 1-based with 0 = none, so 0 is the safe "no env" id; do
        # NOT index a nonexistent envelope.
        _warn_psg_env_once()
        out.append(PsgEnv(0))
    elif mnem == "smpsNoteFill":
        out.append(NoteFill(resolve_const(args[0]) * cfg.divider))
    elif mnem == "smpsStop":
        out.append(End())
    elif mnem == "smpsSetVol":
        # Seed the running SMPS-domain volume so later deltas compose, and emit.
        raw = resolve_const(args[0])
        if kind == "FM":
            st.fm_vol_raw = raw
        else:
            st.psg_vol_raw = raw
        out.append(Vol(_smps_vol_to_v0(kind, raw)))
    elif mnem == "smpsSetNote":
        # cfSetKey ($ED): transpose = val - $40 (signed result).
        st.transpose = _signed8(resolve_const(args[0])) - 0x40
    elif mnem in ("smpsChangeTransposition", "smpsAlterPitch"):
        # cfChangeTransposition ($FB): transpose += signed(val).
        st.transpose += _signed8(resolve_const(args[0]))
    elif mnem == "smpsAlterVol":
        # cfChangeVolume ($E6): add signed delta to the running FM attenuation.
        _alter_vol(kind, "FM", _signed8(resolve_const(args[0])), st, out)
    elif mnem == "smpsPSGAlterVol":
        # cfChangePSGVolume ($EC): add signed delta to the running PSG attn.
        _alter_vol(kind, "PSG", _signed8(resolve_const(args[0])), st, out)
    elif mnem in ("smpsDetune", "smpsAlterNote"):
        # cfDetune ($E1): a fine FREQUENCY detune, not a transpose. v1 does not
        # model sub-semitone detune; drop it (the note pitch is unaffected).
        # Warned once so the fidelity gap is visible without log spam.
        _warn_detune_once()
    elif mnem == "smpsNoAttack":
        # cfNoAttack ($E7): tie the next note to the previous (no re-attack).
        # Same-pitch -> merge durations (Task 2.4). Different-pitch -> re-attack
        # (accepted v1 fidelity gap, warned once below). Setting st.tie here
        # handles the line-leading macro form; the inline byte form ($E7 inside
        # a dc.b) is handled directly in the walk (sets st.tie = True there too).
        st.tie = True
    else:
        # Remaining unmodeled coordination mnemonics (e.g. smpsPSGform — the PSG
        # noise/waveform select, a v1 fidelity gap). Structural flags
        # (smpsCall/Return/Loop/Jump) never reach here: the walker intercepts
        # them before _dispatch_flag.
        warn("skip flag %s" % mnem)


MAX_CALL_DEPTH = 8          # guard against recursive/cyclic smpsCall
MAX_CHANNEL_EVENTS = 20000  # runaway-unroll cap (loop counts blow up)


class _UnrollLimit(Exception):
    """Raised when a channel exceeds MAX_CHANNEL_EVENTS (runaway unroll)."""


def convert_channel(kind, lines, blocks, cfg, st, start_label=None):
    """Convert one channel's SMPS data into a list of music-format-v0 events.

    `kind` is "FM" | "PSG" | "DAC"; `st` is a ConvState; `cfg` supplies .divider.
    `blocks` is the label->lines map from split_blocks (channel headers AND
    internal sub-labels). A channel's data spans MULTIPLE blocks: when a block's
    tokens run out, execution FALLS THROUGH to the next block in source order
    (this is how HCZ2's DAC chains DAC -> Loop00 -> Loop01 -> ...).

    Two entry modes:
      * start_label given  -> the structural walker follows blocks (call-inline,
        loop-unroll, jump-loopback, fall-through). This is the real path.
      * start_label None   -> a single ad-hoc block of `lines` (used by the unit
        tests that pass inline source with no surrounding block map); structural
        flags whose targets live in `blocks` still resolve.

    Returns a flat event list, terminated by Jump (channel loop-back) or End
    (smpsStop) when one is reached."""
    out = []

    if start_label is None and lines:
        # Ad-hoc single-block mode: make the inline `lines` a synthetic block so
        # the same walker handles it (and any structural flag it contains).
        blocks = dict(blocks)
        blocks["__inline__"] = list(lines)
        start_label = "__inline__"
    elif start_label is None:
        return out

    # Ordered label list for fall-through ("the next block in source order").
    order = list(blocks.keys())
    order_index = {lbl: idx for idx, lbl in enumerate(order)}
    # Per-block flattened token lists (cached; flatten is pure).
    tok_cache = {}

    def toks_for(label):
        if label not in tok_cache:
            tok_cache[label] = _flatten_tokens(blocks.get(label, []))
        return tok_cache[label]

    # label -> output index where that label's events begin (for jump-loopback
    # LoopPoint insertion). Recorded the first time the walker enters a block.
    label_out_pos = {}

    def emit(ev):
        out.append(ev)
        if len(out) > MAX_CHANNEL_EVENTS:
            raise _UnrollLimit(
                "channel %r exceeded %d events (runaway unroll?)"
                % (start_label, MAX_CHANNEL_EVENTS))

    def walk(label, depth, stop_at):
        """Walk blocks starting at `label`, following fall-through, until a
        terminator (smpsJump/smpsStop), running off the last block, or reaching
        the `stop_at` loop position (label, token_index) that bounds an unroll
        body. Returns one of: 'fell_off', 'returned', 'terminated', 'stopped'.

        depth      : smpsCall nesting (guarded by MAX_CALL_DEPTH).
        stop_at    : (label, idx) of the smpsLoop flag whose body this is, or
                     None at top level. The replay must NOT re-trigger that exact
                     loop flag (that would recurse forever); it stops there."""
        cur = label
        while True:
            if cur not in order_index:
                # Unknown target (e.g. a forward jump out of the known map) —
                # cannot continue safely.
                warn("walk: unknown label %r" % cur)
                return "fell_off"
            # Record where this label's events start (first entry only).
            if cur not in label_out_pos:
                label_out_pos[cur] = len(out)
            toks = toks_for(cur)
            i = 0
            n = len(toks)
            while i < n:
                tok = toks[i]

                # --- structural flags (intercepted before _dispatch_flag) ---
                if tok[0] == "flag":
                    mnem, args = tok[1], tok[2]

                    if mnem == "smpsCall":
                        if depth + 1 > MAX_CALL_DEPTH:
                            raise RecursionError(
                                "smpsCall depth > %d at %r (cycle?)"
                                % (MAX_CALL_DEPTH, args[0]))
                        walk(args[0], depth + 1, None)  # inline; returns at smpsReturn
                        i += 1
                        continue

                    if mnem == "smpsReturn":
                        return "returned"

                    if mnem == "smpsStop":
                        emit(End())
                        return "terminated"

                    if mnem == "smpsLoop":
                        # If this is the loop flag that bounds the current unroll
                        # body, stop here (do NOT recurse).
                        if stop_at == (cur, i):
                            return "stopped"
                        # smpsLoop index, loops, loc  -> args = [index, loops, loc]
                        count = resolve_const(args[1])
                        target = args[2]
                        # The in-line pass already played the body ONCE (the
                        # tokens from `target` up to here). Replay it count-1 more
                        # times, each bounded by THIS loop's position so it does
                        # not re-loop.
                        for _ in range(max(0, count - 1)):
                            walk(target, depth, (cur, i))
                        i += 1
                        continue

                    if mnem == "smpsJump":
                        target = args[0]
                        if target in label_out_pos:
                            # Backward jump: a channel loop-back. Insert a
                            # LoopPoint at the target's recorded position and a
                            # terminal Jump, then stop converting this channel.
                            _insert_loop_point(out, label_out_pos, target)
                            out.append(Jump())
                            return "terminated"
                        # Forward jump (rare): continue inline at the target.
                        cur = target
                        break  # restart outer while with new block
                    # Non-structural flag -> normal MEV dispatch.
                    _dispatch_flag(kind, mnem, args, st, out, cfg)
                    i += 1
                    continue

                # --- data byte (note / rest / sample / bare dur) ---
                b = tok[1]
                if b >= FIRST_COORD_FLAG:            # inline coordination flag
                    name = _flag_name_for_byte(b)
                    if name == "smpsNoAttack":
                        st.tie = True
                    else:
                        warn("skip inline flag byte $%02X" % b)
                    i += 1
                    continue

                if kind == "DAC":
                    if b >= MEV_NOTE_BASE:           # $81..$DF -> sample
                        ticks, consumed = _peek_dur(toks, i + 1, cfg, st)
                        # Dac() carries the RAW S3K 1-based sample id (b & $7F,
                        # e.g. dKickS3=$86 -> $06). convert_song's dac_remap MUST
                        # map this S3K id -> the v0 DacSampleTable id (Phase 5
                        # lays out that table); the raw id is NOT a v0 table index.
                        emit(Dac(b & 0x7F))
                        # The engine's $E2 MEV_DAC is ZERO-TICK (sound_sequencer
                        # Seq_Op_Dac: "the DAC channel's note IS the trigger; a
                        # following SetDur/Rest paces it"). So pace the sample with
                        # a timed Rest carrying its duration — exactly the
                        # `$E2 ss $80` shape song_drumtest uses. Without this the
                        # whole DAC stream would fire in one frame and the loop
                        # would have no time-advancing event.
                        _emit_with_dur_g(emit, st, ticks, None)
                        i += 1 + consumed
                    elif b == SMPS_REST:             # $80 -> rest
                        ticks, consumed = _peek_dur(toks, i + 1, cfg, st)
                        _emit_with_dur_g(emit, st, ticks, None)
                        i += 1 + consumed
                    else:                            # $00..$7F bare duration
                        _set_default_dur(st, b * cfg.divider)
                        i += 1
                    continue

                # FM / PSG route.
                if b >= MEV_NOTE_BASE:               # $81..$DF -> note
                    pitch = (b - MEV_NOTE_BASE) + st.transpose
                    ticks, consumed = _peek_dur(toks, i + 1, cfg, st)
                    if st.tie:
                        st.tie = False
                        if (st._prev_note_idx is not None
                                and pitch == st._prev_pitch):
                            # Same pitch: merge by replacing the previous note
                            # event with a NoteDur carrying the combined duration.
                            # Do NOT update st.cur_dur (the merged NoteDur is self-
                            # contained; the running default must stay undisturbed
                            # so subsequent bare-Note events keep their duration).
                            merged = min(0xFF, st._prev_note_dur + ticks)
                            if st._prev_note_dur + ticks > 0xFF:
                                warn("tie-merge duration overflow, clamped to $FF")
                            out[st._prev_note_idx] = NoteDur(pitch, merged)
                            st._prev_note_dur = merged
                            # _prev_note_idx stays: another tie could extend again
                        else:
                            # Different pitch or no previous note: re-attack
                            # (accepted v1 fidelity gap — no same-pitch merge).
                            _emit_with_dur_g(emit, st, ticks, pitch)
                            st._prev_note_idx = len(out) - 1
                            st._prev_pitch = pitch
                            st._prev_note_dur = ticks
                    else:
                        _emit_with_dur_g(emit, st, ticks, pitch)
                        st._prev_note_idx = len(out) - 1
                        st._prev_pitch = pitch
                        st._prev_note_dur = ticks
                    i += 1 + consumed
                elif b == SMPS_REST:                 # $80 -> rest
                    ticks, consumed = _peek_dur(toks, i + 1, cfg, st)
                    st.tie = False          # a rest breaks any pending tie
                    st._prev_note_idx = None
                    _emit_with_dur_g(emit, st, ticks, None)
                    i += 1 + consumed
                else:                                # $00..$7F bare duration
                    _set_default_dur(st, b * cfg.divider)
                    i += 1
            else:
                # Ran off the end of this block's tokens: fall through to the
                # next block in source order (or stop if this is the last).
                nxt = order_index[cur] + 1
                if nxt >= len(order):
                    return "fell_off"
                cur = order[nxt]
                continue
            # (broke out of inner loop via a forward smpsJump: `cur` updated)
            continue

    try:
        walk(start_label, 0, None)
    except _UnrollLimit as e:
        warn(str(e))
        raise
    return out


def _insert_loop_point(out, label_out_pos, target):
    """Insert a LoopPoint marker at the recorded output position of `target` and
    fix up every recorded position at or after it. Idempotent-ish: if a LoopPoint
    already sits there, do not add another (a channel jumps back to one place)."""
    pos = label_out_pos[target]
    if pos < len(out) and isinstance(out[pos], LoopPoint):
        return
    out.insert(pos, LoopPoint())
    for lbl in label_out_pos:
        if label_out_pos[lbl] >= pos:
            label_out_pos[lbl] += 1


def _emit_with_dur_g(emit, st, ticks, pitch):
    """Emit a note/rest with the given v0 tick duration through the bounded
    `emit` callback (so the runaway cap counts every event), choosing SetDur+Note
    vs NoteDur (overflow) per the format-v0 default-duration model. `pitch` None
    emits a Rest; otherwise a Note (or NoteDur on duration overflow)."""
    if ticks > MAX_DUR:
        if pitch is None:
            warn("rest duration %d > %d, clamped" % (ticks, MAX_DUR))
            if st.cur_dur != MAX_DUR:
                emit(SetDur(MAX_DUR)); st.cur_dur = MAX_DUR
            emit(Rest())
        else:
            emit(NoteDur(pitch, ticks))
        return
    if st.cur_dur != ticks:
        emit(SetDur(ticks)); st.cur_dur = ticks
    emit(Rest() if pitch is None else Note(pitch))


# SMPS byte-class boundaries (mirror of the driver: FirstCoordFlag = $E0, the
# note range $81..$DF, rest = $80, durations $00..$7F).
FIRST_COORD_FLAG = 0xE0
SMPS_REST = 0x80


def _flag_name_for_byte(b):
    """Reverse-lookup an inline flag byte (>= $E0) to its FLAG_BYTES mnemonic,
    or None if unknown."""
    for name, val in FLAG_BYTES.items():
        if val == b:
            return name
    return None


def _set_default_dur(st, ticks):
    """Standalone bare-duration byte ($00..$7F not consumed as a trailing dur):
    the driver's zStoreDuration writes it into SavedDuration, which subsequent
    bare notes reuse (zGetNoteDuration). So it MUST update st._saved_dur — the
    field _peek_dur reads — not just a display copy. (FIX 1: the old code wrote
    only st.cur_dur, leaving _saved_dur stale at 0, so a leading "set default
    duration" byte produced dur-0 notes.)

    st.cur_dur (the running EMITTED-SetDur tracker) is deliberately NOT set here:
    no note has been emitted yet, so no SetDur is in the stream. Leaving cur_dur
    alone lets the NEXT note emit the SetDur that actually carries this duration
    into the v0 stream (setting cur_dur here would suppress that SetDur and the
    note would play at an undefined duration on the engine)."""
    st._saved_dur = ticks


def _peek_dur(toks, j, cfg, st):
    """Trailing-duration peek (zGetNoteDuration). Look at token index j; if it is
    a ('byte', b) with b < $80, it is this note/rest's duration: consume it,
    update the saved default (st.cur_dur is updated by _emit_with_dur_g, but the
    SMPS SavedDuration is the RAW value*divider here). Returns
    (ticks, consumed) where consumed is 0 or 1.

    When no trailing duration is present, reuse the channel's saved duration.
    The saved duration is tracked as raw*divider in st via a private field so a
    bare note reuses the exact same tick count without re-emitting SetDur."""
    if j < len(toks) and toks[j][0] == "byte" and toks[j][1] < SMPS_REST:
        raw = toks[j][1]
        ticks = raw * cfg.divider
        st._saved_dur = ticks
        return ticks, 1
    # reuse the saved duration (default to 0 only if a note ever precedes any
    # duration — real data always sets one first).
    return getattr(st, "_saved_dur", 0), 0


def tokenize_line(line):
    """Return (mnemonic_or_None, [args], label_or_None) for one SMPS2ASM source line.

    Strips ';' comments. A line like 'Foo:' yields a label; '\tmacro a, b' yields
    (macro, [a, b], None).

    Style assumption (skdisasm convention): labels are alone on their own line
    with no trailing code — 'Label: dc.b ...' is not handled and will be parsed
    as a mnemonic, not a label.
    """
    code = line.split(";", 1)[0].rstrip()
    if not code.strip():
        return (None, [], None)
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", code.strip())
    if m and code.strip().endswith(":"):
        return (None, [], m.group(1))
    parts = code.strip().split(None, 1)
    mnem = parts[0]
    args = [a.strip() for a in parts[1].split(",")] if len(parts) > 1 else []
    return (mnem, args, None)


# ---------------------------------------------------------------------------
# Task 3.1 — convert_song: a whole SMPS song -> a packable SongDesc.
#
# Route assignment (by kind, in source order): DAC -> CHROUTE_DAC; the FM
# channels -> FM1..FM5; the PSG channels -> PSG1..3 (mirror of the v0 route enum
# in song_packer). HCZ2 has exactly one DAC, five FM, three PSG, so the order
# tables below are sufficient; a song with more channels of a kind than there are
# v0 routes raises (the song does not fit the format).
_FM_ROUTE_ORDER = (CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5)
_PSG_ROUTE_ORDER = (CHROUTE_PSG1, CHROUTE_PSG2, CHROUTE_PSG3)

# Song-level playback constants. tempo is the LEGACY Timer-A selector field —
# unused by the per-frame Phase-3 engine but kept in the header; 0x80 is the
# conventional mid value used by the streaming songs. The real per-frame pace is
# tempo_base (= cfg.tempo_base, the 256 - tempo_mod accumulator base).
_SONG_TEMPO = 0x80


def _assign_routes(channels):
    """Assign a v0 route to each ChannelHdr by kind, in source order. Returns a
    list of (ChannelHdr, route) pairs. Raises if a kind has more channels than
    the format has routes for it."""
    fm_i = psg_i = 0
    out = []
    for ch in channels:
        if ch.kind == "DAC":
            out.append((ch, CHROUTE_DAC))
        elif ch.kind == "FM":
            if fm_i >= len(_FM_ROUTE_ORDER):
                raise ValueError("too many FM channels for the v0 route set "
                                 "(max %d)" % len(_FM_ROUTE_ORDER))
            out.append((ch, _FM_ROUTE_ORDER[fm_i])); fm_i += 1
        elif ch.kind == "PSG":
            if psg_i >= len(_PSG_ROUTE_ORDER):
                raise ValueError("too many PSG channels for the v0 route set "
                                 "(max %d)" % len(_PSG_ROUTE_ORDER))
            out.append((ch, _PSG_ROUTE_ORDER[psg_i])); psg_i += 1
        else:
            raise ValueError("unknown channel kind %r" % ch.kind)
    return out


def _first_timing_index(events):
    """Index of the first time-advancing event (Note/Rest/NoteDur) — the point
    the chip is first keyed and so the point the packer's setup-run check fires.
    len(events) if the channel never keys (e.g. a pure smpsStop stub)."""
    for i, ev in enumerate(events):
        if isinstance(ev, (Note, Rest, NoteDur)):
            return i
    return len(events)


def _apply_remaps(events, dac_remap, patch_remap):
    """Rewrite every Dac.sample_id through dac_remap (raw S3K 1-based id -> v0
    DacSampleTable id) and every Patch.patch through patch_remap (in-body
    smpsSetvoice id -> v0 patch-table index), IN PLACE. A missing key raises a
    clear error naming the unmapped id so the caller can extend the remap."""
    for ev in events:
        if isinstance(ev, Dac):
            if ev.sample_id not in dac_remap:
                raise KeyError("DAC sample id %d (raw S3K id $%02X) not in "
                               "dac_remap" % (ev.sample_id, ev.sample_id))
            ev.sample_id = dac_remap[ev.sample_id]
        elif isinstance(ev, Patch):
            if ev.patch not in patch_remap:
                raise KeyError("FM voice id $%02X (in-body smpsSetvoice) not in "
                               "patch_remap" % ev.patch)
            ev.patch = patch_remap[ev.patch]


def _make_packable(ch, route, events):
    """Make one converted channel satisfy song_packer._validate_channel's setup
    requirements (Vol before first note; FM also Patch before first note) and
    ensure it terminates. Returns the finalized event list.

      * PREPEND a Vol(v0 volume from the header) when no Vol precedes the first
        time-advancing event. The header volume (ch.volume) maps via
        _smps_vol_to_v0; default to 0 (full FM / loudest PSG) if the header
        omitted it.
      * FM only: PREPEND a Patch(0) when no Patch precedes the first
        time-advancing event (e.g. HCZ2's FM3 rests $07 ticks BEFORE its first
        smpsSetvoice, so the first keyed event has no patch yet). 0 is the
        post-remap default voice index (patch_remap already applied upstream).
        DAC/PSG never get a Patch ($E1 is rejected on non-FM routes).
      * APPEND End() when the channel does not already terminate in Jump/End.
        (HCZ2 channels all terminate in a smpsJump loop-back -> Jump, but a
        truncated stub may not.)
    """
    out = list(events)
    fti = _first_timing_index(out)

    if route in (CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5):
        # FM: ensure a Patch precedes the first keyed event.
        if not any(isinstance(e, Patch) for e in out[:fti]):
            out.insert(0, Patch(0))
            fti += 1
    if route != CHROUTE_DAC:
        # FM + PSG: ensure a Vol precedes the first keyed event. DAC has no Vol
        # op and is exempt from the packer's first-note check.
        if not any(isinstance(e, Vol) for e in out[:fti]):
            kind = "FM" if route in (CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3,
                                     CHROUTE_FM4, CHROUTE_FM5) else "PSG"
            raw = ch.volume if ch.volume is not None else 0
            out.insert(0, Vol(_smps_vol_to_v0(kind, raw)))

    if not out or not isinstance(out[-1], (Jump, End)):
        out.append(End())
    return out


def convert_song(src_lines, dac_remap, patch_remap, pitchtable=None):
    """Convert a whole SMPS (S3K) song source into a packable SongDesc.

    src_lines    : the song's .asm lines (header + all channel blocks).
    dac_remap    : {raw S3K 1-based DAC id -> v0 DacSampleTable id}. Every Dac
                   event's sample id is rewritten through this; a missing id
                   raises.
    patch_remap  : {in-body smpsSetvoice id -> v0 FM patch-table index}. Every
                   Patch event is rewritten through this; a missing id raises.
    pitchtable   : optional per-song pitch table reference, stored on the SongDesc
                   for the loader (None = engine default).

    Returns a SongDesc(tempo=0x80, tempo_base=cfg.tempo_base, flags=SH_F_STREAM,
    channels=[...]) ready for pack_song. Each channel is route-assigned by kind,
    converted via convert_channel, remapped, made packable (Vol/Patch prologue +
    terminator), and validated by pack_song's _validate_channel at pack time."""
    cfg = parse_header(src_lines)
    blocks = split_blocks(src_lines)

    channels = []
    for ch, route in _assign_routes(cfg.channels):
        st = ConvState(transpose=ch.transpose)
        ev = convert_channel(ch.kind, blocks.get(ch.label, []), blocks, cfg, st,
                             start_label=ch.label)
        _apply_remaps(ev, dac_remap, patch_remap)
        ev = _make_packable(ch, route, ev)
        channels.append(ChannelDesc(route, ev))

    return SongDesc(tempo=_SONG_TEMPO, channels=channels,
                    flags=SH_F_STREAM, tempo_base=cfg.tempo_base,
                    pitchtable=pitchtable)


# ===========================================================================
# Phase 4 — UVB voice import (S3K Universal Voice Bank -> our FmPatch)
#
# Task 4.1: smps_voice_to_fmpatch — thin wrapper over the VERIFIED SFX voice
#           converter. We REUSE sfx_transcode's _SmpsVoiceBuilder (the smpsVc*
#           accumulator) and translate_voice() unchanged; the battle-tested
#           _s3k_op_reorder ([op1,op2,op3,op4] -> [op4,op2,op3,op1]) and the
#           tl_is_level=False (smpsVcTotalLevel is already YM attenuation)
#           decisions come for free. Crucially we DO NOT call _bake_channel_volume
#           here: that bake exists only because S&K folds the SFX channel-volume
#           into the carrier TL at key-on. For HCZ2 MUSIC the sequencer applies
#           channel volume itself (sc_volume -> carrier TL via the MEV_VOL the
#           converter emits), so the patch must stay BASE and let the engine layer
#           volume on top. _SmpsVoiceBuilder.build() already produces the base
#           patch (it never calls _bake_channel_volume), so this is correct by
#           construction.
#
# Task 4.2: parse_uvb_voices / emit_patch_table — locate the UVB in the S3K Z80
#           driver, parse its sequential smpsVc* voice blocks (voice id = 0-based
#           index, confirmed by the per-voice "; Voice NNh" comments), convert
#           each used voice, and emit the HCZ2_Patches table + the patch_remap.
# ===========================================================================

# Import the SFX voice-conversion core directly (cleanly importable: module-level
# class + helper, no import-time CLI side effects). Keeping a single source means
# the UVB voices go through the EXACT same operator reorder + translate_voice path
# as the verified SFX voices.
from sfx_transcode import _SmpsVoiceBuilder, TranscodeError  # noqa: E402
from zyrinx_port import FMPATCH_LEN                          # noqa: E402

# HCZ2's real in-body smpsSetvoice ids (the 4 distinct UVB voices it plays).
HCZ2_USED_VOICE_IDS = (0x03, 0x06, 0x0E, 0x15)

# Path to the S3K Z80 driver holding the FM Universal Voice Bank.
S3K_Z80_DRIVER = "/home/volence/sonic_hacks/skdisasm/Sound/Z80 Sound Driver.asm"

# The UVB label in the S3K Z80 driver (z80_UniVoiceBank:). HCZ2's header is
# smpsHeaderVoiceUVB, which points the song at this bank.
_UVB_LABEL = "z80_UniVoiceBank"

# All smpsVc* sub-macros, in the order a voice block emits them. A voice block
# starts at smpsVcAlgorithm and ends at smpsVcTotalLevel (the last sub-macro).
_SMPS_VC_MACROS = frozenset((
    "smpsVcAlgorithm", "smpsVcFeedback", "smpsVcUnusedBits", "smpsVcDetune",
    "smpsVcCoarseFreq", "smpsVcRateScale", "smpsVcAttackRate", "smpsVcAmpMod",
    "smpsVcDecayRate1", "smpsVcDecayRate2", "smpsVcDecayLevel",
    "smpsVcReleaseRate", "smpsVcTotalLevel",
))


def _normalize_vc_token(tok: str) -> str:
    """Normalize a Z80-driver hex token to the $XX form the SFX parser expects.

    The S3K Z80 driver writes voice bytes as suffix-hex (`04h`, `0FFh`, `1Fh`)
    while the SFX .asm sources (and sfx_transcode._parse_int) use prefix-hex
    (`$04`). Convert `NNh` -> `$NN`; pass `$XX` / decimal through untouched."""
    tok = tok.strip().rstrip(",")
    m = re.fullmatch(r"([0-9A-Fa-f]+)[hH]", tok)
    if m:
        return "$" + m.group(1)
    return tok


def smps_voice_to_fmpatch(voice_macros) -> bytes:
    """Convert one parsed UVB voice into our 26-byte FmPatch (BASE patch).

    `voice_macros` is a list of (macro_name, [arg_tokens]) pairs covering one
    voice block (smpsVcAlgorithm .. smpsVcTotalLevel), with arg tokens in either
    `$XX`, `NNh`, or decimal form. Reuses sfx_transcode's _SmpsVoiceBuilder, so
    the result is op-reordered (_s3k_op_reorder) and TL-verbatim (tl_is_level=
    False) identically to the verified SFX path. Channel volume is NOT baked in
    (music applies volume via the sequencer).

    Returns exactly FMPATCH_LEN (26) bytes laid out per sound_constants.asm
    FmPatch: fp_alg_fb, fp_lr_ams_fms, fp_dt_mul[4], fp_tl[4], fp_rs_ar[4],
    fp_am_d1r[4], fp_d2r[4], fp_d1l_rr[4]."""
    b = _SmpsVoiceBuilder()
    saw_total_level = False
    for macro, args in voice_macros:
        if macro not in _SMPS_VC_MACROS:
            continue
        b.apply(macro, [_normalize_vc_token(a) for a in args])
        if macro == "smpsVcTotalLevel":
            saw_total_level = True
    if not saw_total_level:
        raise TranscodeError(
            "smps_voice_to_fmpatch: voice block missing smpsVcTotalLevel "
            "(no terminating TL group)")
    patch = b.build()
    assert len(patch) == FMPATCH_LEN, \
        "FmPatch must be %d bytes, got %d" % (FMPATCH_LEN, len(patch))
    return patch


def _parse_vc_blocks(lines, start_i: int):
    """Parse sequential smpsVc* voice blocks starting just after the UVB label.

    Returns a list of voices, each a list of (macro, [args]) pairs. A block runs
    from smpsVcAlgorithm to smpsVcTotalLevel inclusive; the bank ends at the
    first non-comment, non-blank line that is not a smpsVc* macro (the next data
    label / directive after the bank)."""
    voices = []
    cur = None
    for line in lines[start_i:]:
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        m = re.match(r"(smpsVc[A-Za-z0-9]+)\s*(.*)", stripped)
        if not m:
            # First non-voice line after the bank body ends the bank.
            if cur is not None:
                break
            # A label line (e.g. the UVB label itself) before any voice -> skip.
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", stripped):
                continue
            break
        macro = m.group(1)
        args = [a.strip() for a in m.group(2).split(",") if a.strip()]
        # strip trailing comments from the last arg
        if args and ";" in args[-1]:
            args[-1] = args[-1][:args[-1].index(";")].strip()
            args = [a for a in args if a]
        if macro == "smpsVcAlgorithm":
            cur = []
            voices.append(cur)
        if cur is None:
            continue
        cur.append((macro, args))
    return voices


def parse_uvb_voices(driver_asm_path: str = S3K_Z80_DRIVER,
                     used_ids=HCZ2_USED_VOICE_IDS) -> dict:
    """Parse the S3K Universal Voice Bank, returning {voice_id: 26-byte FmPatch}.

    voice_id is the 0-based sequential index of the voice in the bank (voice $00
    = the first smpsVc* block). Confirmed by the driver's per-voice "; Voice NNh"
    comments. Only the requested `used_ids` are converted/returned. Raises if an
    id is out of range for the bank."""
    with open(driver_asm_path) as f:
        lines = f.read().splitlines()

    label_i = None
    for i, line in enumerate(lines):
        if line.strip() == _UVB_LABEL + ":":
            label_i = i
            break
    if label_i is None:
        raise TranscodeError(
            "UVB label %r not found in %s" % (_UVB_LABEL, driver_asm_path))

    blocks = _parse_vc_blocks(lines, label_i + 1)
    out = {}
    for vid in used_ids:
        if vid >= len(blocks):
            raise TranscodeError(
                "UVB voice $%02X out of range (bank has %d voices)"
                % (vid, len(blocks)))
        out[vid] = smps_voice_to_fmpatch(blocks[vid])
    return out


def build_patch_remap(used_ids=HCZ2_USED_VOICE_IDS) -> dict:
    """{in-body smpsSetvoice id -> 0-based v0 FM patch-table index}, sorted/stable
    (sorted by S3K id so the table order is deterministic)."""
    return {vid: i for i, vid in enumerate(sorted(used_ids))}


def emit_patch_table(driver_asm_path: str = S3K_Z80_DRIVER,
                     used_ids=HCZ2_USED_VOICE_IDS,
                     label: str = "HCZ2_Patches"):
    """Emit the HCZ2 FmPatch table + the patch_remap.

    Returns (asm_text, patch_remap):
      - patch_remap = {S3K id -> 0-based index} (e.g. {3:0, 6:1, 14:2, 21:3}).
      - asm_text = `HCZ2_Patches:` + one 26-byte dc.b row per used voice, in
        remap-index order, each commented with its S3K id, plus a per-row size
        assert (26 bytes) and a total-size assert (count * 26)."""
    voices = parse_uvb_voices(driver_asm_path, used_ids)
    remap = build_patch_remap(used_ids)
    count = len(remap)

    L = []
    L.append("; ======================================================================")
    L.append("; data/sound/%s.asm — GENERATED by tools/smps_import.py — DO NOT EDIT." % label.lower())
    L.append(";")
    L.append("; HCZ2 FmPatch table: the %d S3K Universal Voice Bank voices HCZ2 plays" % count)
    L.append("; (in-body smpsSetvoice ids %s), translated to our 26-byte FmPatch via the"
             % ", ".join("$%02X" % v for v in sorted(used_ids)))
    L.append("; verified SFX voice converter (smps_voice_to_fmpatch). The song's Patch")
    L.append("; events were remapped to dense 0-based indices via patch_remap.")
    L.append(";")
    L.append("; Record: fp_alg_fb=$B0, fp_lr_ams_fms=$B4, then 6 four-byte per-op arrays")
    L.append("; for regs $30/$40/$50/$60/$70/$80, array index 0..3 = PHYSICAL operators")
    L.append("; S1,S3,S2,S4 (S3K binary order reordered via _s3k_op_reorder).")
    L.append("; ======================================================================")
    L.append("")
    L.append("%s:" % label)
    # Inverse remap: dense index -> S3K id, so rows emit in remap-index order.
    idx_to_id = {i: vid for vid, i in remap.items()}
    for i in range(count):
        vid = idx_to_id[i]
        rec = voices[vid]
        byte_str = ", ".join("$%02X" % x for x in rec)
        L.append("        dc.b    %s  ; [%d] S3K voice $%02X" % (byte_str, i, vid))
    L.append("%s_End:" % label)
    L.append("")
    L.append("        if (%s_End-%s) <> %d*FmPatch_len" % (label, label, count))
    L.append("          error \"%s size mismatch (expected %d voices * 26 bytes)\""
             % (label, count))
    L.append("        endif")
    L.append("")
    return "\n".join(L) + "\n", remap
