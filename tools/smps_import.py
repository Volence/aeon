# tools/smps_import.py  — SMPS (S3K) -> music-format-v0 converter.
import os, sys, re
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

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
