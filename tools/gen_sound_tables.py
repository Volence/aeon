#!/usr/bin/env python3
"""gen_sound_tables — build-time FM/PSG pitch, volume, and carrier-mask tables.

Emits data/sound/sound_tables.asm (68k ROM data, read by the Z80 sequencer
through its $8000 window in later tasks). Everything here is pure build-PC math;
the contracts (opcode/struct/header) live in sound_constants.asm.

Run as a module-less script to regenerate the .asm:
    python3 tools/gen_sound_tables.py            # -> data/sound/sound_tables.asm
Tests: python3 -m pytest tools/test_gen_sound_tables.py -q

--- DECISIONS (documented per task DECISIONS-TO-MAKE) ---

1. Pitch-table word pack: high byte = the YM $A4 register value
   ((block<<3)|(fnum>>8)), low byte = the YM $A0 register value (fnum & 0xFF).
   Emitted as dc.w = (a4 << 8) | a0. A Task-3 writer splits the word: write the
   high byte to $A4+ch, then the low byte to $A0+ch (hardware requires $A4
   first — it latches the block/fnum-high, $A0 commits). This matches the
   on-hardware fnum/block register split exactly.

2. semitone-0 reference = MIDI note 12 (C0, 16.3516 Hz at A4=440 equal
   temperament). With this base, pitch index = MIDI - 12, A4 (MIDI 69) lands on
   pitch index 57 -> fnum 0x43B, block 4 (research target 0x43A/block4, +1 LSB
   from round-half-up — within the documented ±1-2 LSB tolerance). The top
   index 94 (MIDI 106) stays inside block 7, so the 3-bit block field never
   overflows.

3. log_volume_lut formula: tl_delta = round(-log2(linear/127) * SCALE), clamped
   to 0..0x7F, with SCALE chosen so index 0 saturates at 0x7F. Index 0 (silence)
   is forced to 0x7F and index 127 (loudest) to 0 (exact endpoints). Indices
   128..255 EXTEND the table by clamping to 0 (already-loudest) — a linear
   volume above 127 cannot get louder than 0 attenuation, so the curve flatlines
   at 0. This keeps the LUT a full 256 bytes (single-byte index, no bounds check
   on the Z80 side) while the meaningful domain is 0..127.
"""

import math
import os

# --- Hardware clocks (NTSC) ---
MASTER_CLOCK = 53693175           # Hz
FM_SAMPLE_RATE = MASTER_CLOCK / 7 / 144     # = 53267.039 Hz
Z80_CLOCK = 3579545               # Hz (master/15)
PSG_SAMPLE_RATE = Z80_CLOCK / 16  # = 223721.56 Hz

# --- Pitch table geometry ---
# Pitch index range = MEV_NOTE_BASE..MEV_NOTE_MAX = $81..$DF -> 0..94 (95 entries).
NUM_PITCHES = 0xDF - 0x81 + 1     # = 95
SEMITONE0_MIDI = 12               # C0 (decision 2)
A4_MIDI = 69
A4_PITCH_INDEX = A4_MIDI - SEMITONE0_MIDI   # = 57
A4_FREQ = 440.0


def _round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def _pitch_freq(pitch_index: int) -> float:
    """Equal-temperament frequency for a pitch index (A4=440)."""
    midi = SEMITONE0_MIDI + pitch_index
    return A4_FREQ * 2 ** ((midi - A4_MIDI) / 12)


def fnum_block(semitone: int) -> tuple[int, int]:
    """Return (fnum 11-bit, block 3-bit) for a pitch index.

    fnum_raw = round(freq * 2^21 / FM_SAMPLE_RATE); normalize into the 11-bit
    fnum window (< 0x800) by halving and incrementing block.
    """
    freq = _pitch_freq(semitone)
    fnum = freq * 2 ** 21 / FM_SAMPLE_RATE
    block = 0
    while fnum >= 0x800:
        fnum /= 2
        block += 1
    return _round_half_up(fnum), block


def fm_pitch_table() -> list[tuple[int, int]]:
    """One entry per pitch index 0..94: (packed_word, fnum, block).

    packed_word = ($A4 value << 8) | $A0 value (decision 1).
    """
    out = []
    for i in range(NUM_PITCHES):
        fnum, block = fnum_block(i)
        a4 = ((block << 3) | (fnum >> 8)) & 0xFF
        a0 = fnum & 0xFF
        out.append(((a4 << 8) | a0, fnum, block))
    return out


def psg_divisor(semitone: int) -> int:
    """10-bit PSG tone divisor for a pitch index. = round(clock/(32*freq)).

    The divisor is clamped to the 10-bit ceiling ($03FF), so low PSG pitches
    saturate: the bottom ~2.5 octaves are not chromatic (correct hardware
    behavior — the SN76489 has no lower divisor resolution there).
    """
    freq = _pitch_freq(semitone)
    d = _round_half_up(PSG_SAMPLE_RATE / (freq * 2))
    return max(1, min(0x3FF, d))


def psg_divisor_table() -> list[int]:
    return [psg_divisor(i) for i in range(NUM_PITCHES)]


def log_volume_lut() -> list[int]:
    """256 entries mapping linear volume -> YM TL delta (log attenuation).

    lut[127] = 0 (loudest), lut[0] = 0x7F (silence), monotonic non-increasing.
    Indices 128..255 clamp to 0 (can't be louder than 0 attenuation).
    """
    # SCALE so that the smallest nonzero linear (1) maps near 0x7F.
    # -log2(1/127) = 6.989; scale to span up to 0x7F across 1..127.
    SCALE = 0x7F / -math.log2(1 / 127)
    lut = []
    for i in range(256):
        if i >= 127:
            lut.append(0)
        elif i == 0:
            lut.append(0x7F)
        else:
            delta = _round_half_up(-math.log2(i / 127) * SCALE)
            lut.append(max(0, min(0x7F, delta)))
    return lut


def carrier_mask_table() -> list[int]:
    """8 entries, algorithm 0..7 -> 4-bit carrier-operator mask.

    Bit i (i=0..3) = operator at register offset +i*4 = physical order
    S1,S3,S2,S4. Carrier set per YM2612 algorithm:
      algo 0-3 -> S4 only        = 0b1000
      algo 4   -> S2,S4          = 0b1100
      algo 5,6 -> S2,S3,S4       = 0b1110
      algo 7   -> all four       = 0b1111
    """
    return [0x8, 0x8, 0x8, 0x8, 0xC, 0xE, 0xE, 0xF]


def _emit_dc(width: str, values, per_line: int) -> list[str]:
    """Emit dc.b/dc.w lines, `per_line` values each, as hex literals."""
    fmt = "${:02X}" if width == "b" else "${:04X}"
    lines = []
    for i in range(0, len(values), per_line):
        chunk = values[i:i + per_line]
        lines.append("    dc.%s   %s" % (width, ", ".join(fmt.format(v) for v in chunk)))
    return lines


def emit_asm() -> str:
    pitch = fm_pitch_table()
    psg = psg_divisor_table()
    vol = log_volume_lut()
    masks = carrier_mask_table()

    out = []
    out.append("; ======================================================================")
    out.append("; data/sound/sound_tables.asm — GENERATED by tools/gen_sound_tables.py")
    out.append("; DO NOT EDIT BY HAND. Regenerate: python3 tools/gen_sound_tables.py")
    out.append(";")
    out.append("; FM pitch table : per pitch index, dc.w = ($A4 value << 8) | $A0 value")
    out.append(";                  ($A4 = (block<<3)|(fnum>>8), $A0 = fnum&$FF).")
    out.append("; PSG divisor    : per pitch index, dc.w = 10-bit tone divisor.")
    out.append(";                  Low pitches saturate at the 10-bit ceiling ($03FF),")
    out.append(";                  so the bottom ~2.5 octaves of PSG are not chromatic")
    out.append(";                  (correct SN76489 hardware behavior).")
    out.append("; Log volume LUT : 256 bytes, linear vol 0..127 -> YM TL delta (log).")
    out.append("; Carrier mask   : 8 bytes, algo 0..7 -> 4-bit carrier-op mask")
    out.append(";                  (bit i = operator at reg offset +i*4 = S1,S3,S2,S4).")
    out.append("; A4=440Hz -> FM fnum $%03X/block %d (pitch idx %d); PSG divisor $%03X."
               % (pitch[A4_PITCH_INDEX][1], pitch[A4_PITCH_INDEX][2],
                  A4_PITCH_INDEX, psg[A4_PITCH_INDEX]))
    out.append("; ======================================================================")
    out.append("")
    out.append("FmPitchTable:")
    out.extend(_emit_dc("w", [w for (w, _f, _b) in pitch], 8))
    out.append("FmPitchTable_End:")
    out.append("")
    out.append("        if (FmPitchTable_End-FmPitchTable)/2 <> 95")
    out.append('          error "FM pitch table wrong length"')
    out.append("        endif")
    out.append("")
    out.append("PsgDivisorTable:")
    out.extend(_emit_dc("w", psg, 8))
    out.append("PsgDivisorTable_End:")
    out.append("")
    out.append("        if (PsgDivisorTable_End-PsgDivisorTable)/2 <> 95")
    out.append('          error "PSG divisor table wrong length"')
    out.append("        endif")
    out.append("")
    out.append("LogVolumeLut:")
    out.extend(_emit_dc("b", vol, 16))
    out.append("LogVolumeLut_End:")
    out.append("")
    out.append("        if (LogVolumeLut_End-LogVolumeLut) <> 256")
    out.append('          error "log volume LUT must be 256 bytes"')
    out.append("        endif")
    out.append("")
    out.append("CarrierMaskTable:")
    out.extend(_emit_dc("b", masks, 8))
    out.append("CarrierMaskTable_End:")
    out.append("")
    out.append("        if (CarrierMaskTable_End-CarrierMaskTable) <> 8")
    out.append('          error "carrier mask table must be 8 bytes"')
    out.append("        endif")
    out.append("")
    out.append("        align 2")
    out.append("")
    return "\n".join(out)


def _emit_dc_z80(width: str, values, per_line: int) -> list[str]:
    """Emit Z80-syntax db/dw lines (Intel-hex literals, e.g. 0A0Bh)."""
    def lit(v):
        h = ("%0*X" % (4 if width == "w" else 2, v))
        # Intel-hex needs a leading digit; AS requires 0-prefix if it starts A-F.
        return (h + "h") if h[0].isdigit() else ("0" + h + "h")
    kw = "dw" if width == "w" else "db"
    lines = []
    for i in range(0, len(values), per_line):
        chunk = values[i:i + per_line]
        lines.append("        %s      %s" % (kw, ", ".join(lit(v) for v in chunk)))
    return lines


def emit_asm_z80() -> str:
    """Z80-syntax inline copies of the FM tables for the phase-0 sound blob.

    Task 3 (FM voice writer) reads these with DIRECT Z80 addressing — they live
    INSIDE the z80_sound_driver.asm `phase 0` blob (loaded into Z80 RAM at boot),
    so no $8000-window banking is needed. The values are identical to the 68k
    ROM tables in sound_tables.asm; only the syntax (db/dw, Intel-hex literals)
    and the labels (…Z suffix) differ. (Task 6 may switch the writers to the
    banked ROM tables; for 1C these static tables are inline + directly read.)
    PSG divisor table is NOT emitted here — the PSG writer (Task 4) can add it
    if/when it needs an inline copy.
    """
    pitch = fm_pitch_table()
    vol = log_volume_lut()
    masks = carrier_mask_table()

    out = []
    out.append("; ======================================================================")
    out.append("; engine/sound_tables_z80.asm — GENERATED by tools/gen_sound_tables.py")
    out.append("; DO NOT EDIT BY HAND. Regenerate: python3 tools/gen_sound_tables.py")
    out.append(";")
    out.append("; Z80-SYNTAX INLINE copies of the FM tables, included INSIDE the phase-0")
    out.append("; Z80 blob so the FM voice writer (engine/sound_fm.asm) reads them with")
    out.append("; direct Z80 addressing (no $8000-window banking). Identical VALUES to the")
    out.append("; 68k ROM tables in data/sound/sound_tables.asm.")
    out.append("; ======================================================================")
    out.append("")
    out.append("FmPitchTableZ:")
    out.extend(_emit_dc_z80("w", [w for (w, _f, _b) in pitch], 8))
    out.append("FmPitchTableZ_End:")
    out.append("")
    out.append("LogVolumeLutZ:")
    out.extend(_emit_dc_z80("b", vol, 16))
    out.append("LogVolumeLutZ_End:")
    out.append("")
    out.append("CarrierMaskTableZ:")
    out.extend(_emit_dc_z80("b", masks, 8))
    out.append("CarrierMaskTableZ_End:")
    out.append("")
    return "\n".join(out)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(here, "..", "data", "sound", "sound_tables.asm")
    out_path = os.path.normpath(out_path)
    with open(out_path, "w") as f:
        f.write(emit_asm())
    print("wrote", out_path)

    z80_path = os.path.join(here, "..", "engine", "sound_tables_z80.asm")
    z80_path = os.path.normpath(z80_path)
    with open(z80_path, "w") as f:
        f.write(emit_asm_z80())
    print("wrote", z80_path)


if __name__ == "__main__":
    main()
