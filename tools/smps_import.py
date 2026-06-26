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
