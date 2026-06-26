# tools/smps_import.py  — SMPS (S3K) -> music-format-v0 converter.
import os, sys, re
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from song_packer import (
    Note, Rest, SetDur, NoteDur, MEV_NOTE_BASE, MAX_DUR,
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
    raise KeyError("unknown SMPS constant: %r" % tok)

class ChannelHdr:
    def __init__(self, kind, label, transpose=0, voice=None):
        self.kind = kind          # "FM" | "PSG" | "DAC"
        self.label = label
        self.transpose = transpose
        self.voice = voice

class SongConfig:
    def __init__(self):
        self.divider = 1; self.tempo_mod = 0; self.channels = []
    @property
    def tempo_base(self):
        return max(16, min(255, 256 - self.tempo_mod))

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
            cfg.channels.append(ChannelHdr("DAC", args[0]))
        elif mnem == "smpsHeaderFM":
            if len(args) < 3:
                raise ValueError("smpsHeaderFM needs loc,pitch,vol: %r" % args)
            cfg.channels.append(ChannelHdr("FM", args[0],
                transpose=_signed8(resolve_const(args[1])), voice=resolve_const(args[2])))
        elif mnem == "smpsHeaderPSG":
            if len(args) < 3:
                raise ValueError("smpsHeaderPSG needs loc,pitch,vol: %r" % args)
            cfg.channels.append(ChannelHdr("PSG", args[0],
                transpose=_signed8(resolve_const(args[1]))))
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

# Coordination-flag macro mnemonics this converter recognizes as line-leading
# tokens. Membership here decides ('flag',...) vs warn-skip in the flattener.
# Task 2.1 only walks notes/rests/durations — every flag is warn-skipped in the
# walk; Task 2.2 maps them to MEV events. (Header/voice macros are NOT here —
# they are handled before channel conversion.)
_FLAG_MNEMONICS = frozenset((
    "smpsPan", "smpsSetvoice", "smpsFMvoice", "smpsModSet", "smpsModOff",
    "smpsPSGvoice", "smpsNoteFill", "smpsStop", "smpsSetVol",
    "smpsAlterVol", "smpsPSGAlterVol", "smpsDetune", "smpsAlterNote",
    "smpsAlterPitch", "smpsCall", "smpsReturn", "smpsLoop", "smpsJump",
    "smpsSetNote", "smpsChangeTransposition", "smpsNoAttack", "smpsPSGform",
))


def warn(msg):
    sys.stderr.write("smps_import: WARN: %s\n" % msg)


class ConvState:
    """Mutable per-channel conversion state carried across the byte walk.

    transpose : signed semitone displacement folded into every note pitch
                (the channel header's transpose; Task 2.4 may also fold
                smpsChangeTransposition into this).
    volume    : current folded channel volume (Task 2.3 delta folding); None
                until the first explicit volume.
    cur_dur   : the current DEFAULT duration already emitted (the v0 stream's
                running SetDur value), in v0 ticks. None until first set, so the
                first note always emits a SetDur.
    tie       : True after an inline smpsNoAttack ($E7) — the next note should be
                tied / no-attack (Task 2.4 consumes this; recorded here so the
                walk does not misinterpret the $E7 byte as a note).
    """
    def __init__(self, transpose=0, volume=None):
        self.transpose = transpose
        self.volume = volume
        self.cur_dur = None
        self.tie = False


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


def _emit_with_dur(out, st, ev_factory, ticks, pitch=None):
    """Emit a note/rest with the given v0 tick duration, choosing SetDur+Note
    vs NoteDur (overflow) per the format-v0 default-duration model.

    ev_factory(pitch) -> Note (when pitch is not None) or Rest (pitch None).
    """
    if ticks > MAX_DUR:
        # Duration overflows the 7-bit SetDur range. NoteDur carries a full
        # 8-bit duration and does NOT change the running default.
        if pitch is None:
            # A rest cannot exceed $7F in v0 (no NoteDur form). Clamp + warn;
            # real HCZ2 rests never overflow (divider is $01).
            warn("rest duration %d > %d, clamped" % (ticks, MAX_DUR))
            if st.cur_dur != MAX_DUR:
                out.append(SetDur(MAX_DUR)); st.cur_dur = MAX_DUR
            out.append(Rest())
        else:
            out.append(NoteDur(pitch, ticks))
        return
    if st.cur_dur != ticks:
        out.append(SetDur(ticks)); st.cur_dur = ticks
    out.append(Rest() if pitch is None else Note(pitch))


def convert_channel(kind, lines, blocks, cfg, st):
    """Convert one channel's SMPS source lines into a list of music-format-v0
    events. `kind` is "FM" | "PSG" | "DAC"; `st` is a ConvState; `cfg` supplies
    .divider. `blocks` (the label->lines map) is accepted for Task 2.4 call/loop
    resolution; unused here.

    Task 2.1 implements the note/rest/duration walk only. Coordination flags are
    warn-skipped (Task 2.2 maps them to MEV events)."""
    toks = _flatten_tokens(lines)
    out = []
    i = 0
    n = len(toks)
    while i < n:
        tok = toks[i]
        if tok[0] == "flag":
            warn("skip flag %s" % tok[1])            # Task 2.2 dispatches these
            i += 1
            continue

        # ('byte', b)
        b = tok[1]
        if b >= FIRST_COORD_FLAG:                    # inline coordination flag
            warn("skip inline flag byte $%02X" % b)  # Task 2.2 handles these
            i += 1
            continue

        # FM / PSG / DAC note-bearing route (DAC sample classification is 2.2).
        if b >= MEV_NOTE_BASE:                        # $81..$DF -> note
            pitch = (b - MEV_NOTE_BASE) + st.transpose
            ticks, consumed = _peek_dur(toks, i + 1, cfg, st)
            _emit_with_dur(out, st, Note, ticks, pitch=pitch)
            i += 1 + consumed
        elif b == SMPS_REST:                          # $80 -> rest
            ticks, consumed = _peek_dur(toks, i + 1, cfg, st)
            _emit_with_dur(out, st, None, ticks, pitch=None)
            i += 1 + consumed
        else:                                         # $00..$7F bare duration
            st.cur_dur = b * cfg.divider
            i += 1
    return out


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


def _peek_dur(toks, j, cfg, st):
    """Trailing-duration peek (zGetNoteDuration). Look at token index j; if it is
    a ('byte', b) with b < $80, it is this note/rest's duration: consume it,
    update the saved default (st.cur_dur is updated by _emit_with_dur, but the
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
