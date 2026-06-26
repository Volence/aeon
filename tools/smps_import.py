# tools/smps_import.py  — SMPS (S3K) -> music-format-v0 converter.
import os, sys, re
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from song_packer import (
    Note, Rest, SetDur, NoteDur, Vol, Patch, Pan, ModSet, PsgEnv, NoteFill,
    Dac, End, LoopPoint, Jump, MEV_NOTE_BASE, MAX_DUR,
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
    # PSG tone/envelope names: sTone_NN -> the hex number NN. The numeric id is
    # the S3K PSG-envelope index; v1 does not import those envelopes (see
    # _dispatch_flag smpsPSGvoice), but resolving the constant lets the header
    # parser and any inline use succeed instead of KeyError-ing.
    m = re.fullmatch(r"sTone_([0-9A-Fa-f]{1,2})", tok)
    if m:
        return int(m.group(1), 16)
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
                        _ticks, consumed = _peek_dur(toks, i + 1, cfg, st)
                        emit(Dac(b & 0x7F))
                        i += 1 + consumed
                    elif b == SMPS_REST:             # $80 -> rest
                        ticks, consumed = _peek_dur(toks, i + 1, cfg, st)
                        _emit_with_dur_g(emit, st, ticks, None)
                        i += 1 + consumed
                    else:                            # $00..$7F bare duration
                        st.cur_dur = b * cfg.divider
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
                    st.cur_dur = b * cfg.divider
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
    """_emit_with_dur but driven through the bounded `emit` callback (so the
    runaway cap counts every event). Mirrors _emit_with_dur's overflow logic."""
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
