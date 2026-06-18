#!/usr/bin/env python3
"""Tests for gen_sound_tables — build-time FM/PSG pitch + volume + carrier tables.

TDD: these are written before the implementation. Run via:
    python3 -m pytest tools/test_gen_sound_tables.py -q
"""

import unittest
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_sound_tables import (
    fnum_block,
    fm_pitch_table,
    psg_divisor,
    psg_divisor_table,
    log_volume_lut,
    carrier_mask_table,
    emit_asm,
    emit_asm_z80,
    NUM_PITCHES,
    A4_PITCH_INDEX,
)


class TestFnumBlock(unittest.TestCase):

    def test_a4_reference(self):
        # A4 = 440 Hz -> fnum 0x43B, block 4 (research-pinned, within ±1-2 LSB).
        fnum, block = fnum_block(A4_PITCH_INDEX)
        self.assertEqual(block, 4)
        self.assertIn(fnum, (0x43A, 0x43B))

    def test_fnum_in_range(self):
        for i in range(NUM_PITCHES):
            fnum, block = fnum_block(i)
            self.assertTrue(0 <= fnum <= 0x7FF, f"fnum {fnum:#x} out of range at {i}")
            self.assertTrue(0 <= block <= 7, f"block {block} out of range at {i}")

    def test_equal_temperament_ratio(self):
        # Adjacent semitones within the same block: fnum ratio ~ 2^(1/12).
        ratio = 2 ** (1 / 12)
        for i in range(NUM_PITCHES - 1):
            f0, b0 = fnum_block(i)
            f1, b1 = fnum_block(i + 1)
            if b0 == b1:
                got = f1 / f0
                self.assertAlmostEqual(got, ratio, delta=0.01,
                                       msg=f"semitone {i}->{i+1} ratio {got}")

    def test_block_increments_at_octave_boundary(self):
        # Block is non-decreasing across the table.
        blocks = [fnum_block(i)[1] for i in range(NUM_PITCHES)]
        self.assertTrue(all(blocks[i] <= blocks[i + 1] for i in range(NUM_PITCHES - 1)))
        # Once the fnum has reached its per-octave plateau (block >= 1), every
        # +12 semitones is exactly +1 block with the SAME fnum (standard YM
        # octave construction). The bottom octave (block 0) instead doubles
        # fnum, since nothing forces a block split that low.
        for i in range(NUM_PITCHES - 12):
            f0, b0 = fnum_block(i)
            f1, b1 = fnum_block(i + 12)
            if b0 >= 1:
                self.assertEqual(b1, b0 + 1, f"octave boundary block at {i}")
                self.assertEqual(f1, f0, f"octave boundary fnum at {i}")
            else:
                # bottom octave: fnum doubles, block holds (or just crosses to 1)
                self.assertIn(b1, (0, 1), f"low octave block at {i}")


class TestFmPitchTable(unittest.TestCase):

    def test_length(self):
        # MEV_NOTE_MAX - MEV_NOTE_BASE + 1 = 0xDF - 0x81 + 1 = 95.
        self.assertEqual(len(fm_pitch_table()), 95)
        self.assertEqual(NUM_PITCHES, 95)

    def test_entry_word_pack(self):
        # Each entry is (word, fnum, block); word high byte = $A4 value
        # ((block<<3)|(fnum>>8)), low byte = $A0 value (fnum & 0xFF).
        for i, (word, fnum, block) in enumerate(fm_pitch_table()):
            a4 = ((block << 3) | (fnum >> 8)) & 0xFF
            a0 = fnum & 0xFF
            self.assertEqual(word, (a4 << 8) | a0, f"pitch {i}")
            self.assertTrue(0 <= word <= 0xFFFF)


class TestPsgDivisor(unittest.TestCase):

    def test_a4_reference(self):
        # A4 = 440 Hz -> divisor 0xFE (254).
        self.assertEqual(psg_divisor(A4_PITCH_INDEX), 0xFE)

    def test_clamp_range(self):
        for d in psg_divisor_table():
            self.assertTrue(1 <= d <= 0x3FF)

    def test_monotonic_decreasing(self):
        tbl = psg_divisor_table()
        self.assertEqual(len(tbl), 95)
        self.assertTrue(all(tbl[i] >= tbl[i + 1] for i in range(len(tbl) - 1)))


class TestLogVolumeLut(unittest.TestCase):

    def setUp(self):
        self.lut = log_volume_lut()

    def test_length(self):
        self.assertEqual(len(self.lut), 256)

    def test_endpoints(self):
        self.assertEqual(self.lut[127], 0)       # loudest = no attenuation
        self.assertEqual(self.lut[0], 0x7F)      # silence = max attenuation

    def test_monotonic_nonincreasing(self):
        # Rising linear volume -> falling TL delta (less attenuation).
        for i in range(255):
            self.assertGreaterEqual(self.lut[i], self.lut[i + 1])

    def test_all_in_tl_range(self):
        for v in self.lut:
            self.assertTrue(0 <= v <= 0x7F)


class TestCarrierMaskTable(unittest.TestCase):

    def test_table(self):
        t = carrier_mask_table()
        self.assertEqual(len(t), 8)
        self.assertEqual(t[0], 0b1000)   # algo 0 -> S4 only
        self.assertEqual(t[7], 0b1111)   # algo 7 -> all four carriers
        self.assertEqual(t, [0x8, 0x8, 0x8, 0x8, 0xC, 0xE, 0xE, 0xF])


class TestEmitAsm(unittest.TestCase):

    def setUp(self):
        self.asm = emit_asm()

    def test_contains_size_asserts(self):
        self.assertIn("FM pitch table wrong length", self.asm)
        self.assertIn("log volume LUT must be 256 bytes", self.asm)
        self.assertIn("carrier mask table must be 8 bytes", self.asm)

    def test_labels_present(self):
        for lbl in ("FmPitchTable", "FmPitchTable_End", "PsgDivisorTable",
                    "LogVolumeLut", "LogVolumeLut_End",
                    "CarrierMaskTable", "CarrierMaskTable_End"):
            self.assertIn(lbl + ":", self.asm)

    def _parse_dc(self, label, width):
        # Extract dc.b / dc.w values between `label:` and `label_End:`.
        # width = 'b' or 'w'.
        lines = self.asm.splitlines()
        start = next(i for i, l in enumerate(lines) if l.strip().startswith(label + ":"))
        vals = []
        for l in lines[start + 1:]:
            s = l.strip()
            if s.startswith(label + "_End:"):
                break
            m = re.match(r"dc\.[bw]\s+(.*)", s)
            if m:
                for tok in m.group(1).split(","):
                    tok = tok.strip()
                    if tok:
                        # AS hex literals use a `$` prefix.
                        if tok.startswith("$"):
                            vals.append(int(tok[1:], 16))
                        else:
                            vals.append(int(tok, 0))
        return vals

    def test_pitch_table_roundtrip(self):
        words = self._parse_dc("FmPitchTable", "w")
        self.assertEqual(len(words), 95)
        for i, (word, _f, _b) in enumerate(fm_pitch_table()):
            self.assertEqual(words[i], word)

    def test_volume_lut_roundtrip(self):
        vals = self._parse_dc("LogVolumeLut", "b")
        self.assertEqual(vals, log_volume_lut())

    def test_carrier_mask_roundtrip(self):
        vals = self._parse_dc("CarrierMaskTable", "b")
        self.assertEqual(vals, carrier_mask_table())


class TestEmitAsmZ80Matches68k(unittest.TestCase):
    """Drift guard: the Z80 inline emit (emit_asm_z80) must carry the SAME
    numeric table values as the 68k ROM emit (emit_asm). They share the source
    functions, so this is structurally unlikely to drift, but the codebase
    values build-time validation — a cheap guard is worth it."""

    def setUp(self):
        self.asm68k = emit_asm()
        self.asmz80 = emit_asm_z80()

    def _parse_68k(self, label):
        # dc.b/dc.w with AS `$` hex literals, between `label:` and `label_End:`.
        lines = self.asm68k.splitlines()
        start = next(i for i, l in enumerate(lines) if l.strip().startswith(label + ":"))
        vals = []
        for l in lines[start + 1:]:
            s = l.strip()
            if s.startswith(label + "_End:"):
                break
            m = re.match(r"dc\.[bw]\s+(.*)", s)
            if m:
                for tok in m.group(1).split(","):
                    tok = tok.strip()
                    if tok:
                        vals.append(int(tok[1:], 16) if tok.startswith("$") else int(tok, 0))
        return vals

    def _parse_z80(self, label):
        # db/dw with Intel-hex literals (e.g. 01Eh, 0A0Bh) between label/label_End.
        lines = self.asmz80.splitlines()
        start = next(i for i, l in enumerate(lines) if l.strip().startswith(label + ":"))
        vals = []
        for l in lines[start + 1:]:
            s = l.strip()
            if s.startswith(label + "_End:"):
                break
            m = re.match(r"d[bw]\s+(.*)", s)
            if m:
                for tok in m.group(1).split(","):
                    tok = tok.strip()
                    if tok.endswith("h") or tok.endswith("H"):
                        vals.append(int(tok[:-1], 16))
                    elif tok:
                        vals.append(int(tok, 0))
        return vals

    def test_pitch_table_values_match(self):
        self.assertEqual(self._parse_z80("FmPitchTableZ"),
                         self._parse_68k("FmPitchTable"))

    def test_log_volume_lut_values_match(self):
        self.assertEqual(self._parse_z80("LogVolumeLutZ"),
                         self._parse_68k("LogVolumeLut"))

    def test_carrier_mask_values_match(self):
        self.assertEqual(self._parse_z80("CarrierMaskTableZ"),
                         self._parse_68k("CarrierMaskTable"))


if __name__ == "__main__":
    unittest.main()
