# tools/smps_import.py  — SMPS (S3K) -> music-format-v0 converter.
import os, sys, re
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_NOTE_NAMES = ["C","Cs","D","Ds","E","F","Fs","G","Gs","A","As","B"]
NOTE_BYTES = {}
for _oct in range(8):
    for _i, _n in enumerate(_NOTE_NAMES):
        NOTE_BYTES["n%s%d" % (_n, _oct)] = 0x81 + _oct*12 + _i

PAN_BYTES = {"panLeft": 0x80, "panRight": 0x40, "panCenter": 0xC0, "panNone": 0x00}

# Driver-v3 DAC enum (_smps2asm_inc.asm lines 96-113, case 3).
# Only the HCZ2 set is required; extend as needed.
DAC_IDS = {
    "dSnareS3": 0x81, "dHighTom": 0x82, "dMidTomS3": 0x83, "dLowTomS3": 0x84,
    "dFloorTomS3": 0x85, "dKickS3": 0x86,
}

def resolve_const(tok):
    tok = tok.strip()
    if tok.startswith("$"):
        return int(tok[1:], 16)
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    for table in (NOTE_BYTES, PAN_BYTES, DAC_IDS):
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
            cfg.divider = resolve_const(args[0])
            cfg.tempo_mod = resolve_const(args[1])
        elif mnem == "smpsHeaderDAC":
            cfg.channels.append(ChannelHdr("DAC", args[0]))
        elif mnem == "smpsHeaderFM":
            cfg.channels.append(ChannelHdr("FM", args[0],
                transpose=_signed8(resolve_const(args[1])), voice=resolve_const(args[2])))
        elif mnem == "smpsHeaderPSG":
            cfg.channels.append(ChannelHdr("PSG", args[0],
                transpose=_signed8(resolve_const(args[1]))))
    return cfg

def split_blocks(lines):
    """Return an ordered dict mapping each label to its body lines.

    Lines before the first label are ignored (the header section is handled
    separately by parse_header). Blank/comment-only lines within a block are
    also dropped so callers get only actionable content.
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
    (macro, [a, b], None)."""
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
