#!/usr/bin/env python3
"""Tests for s4budget — ROM/RAM/VRAM budget dashboard."""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4budget import parse_symbol_table


SAMPLE_SYMTAB = """\
  Symbol Table (* = unused):
  --------------------------

 ACCELERATION :                   C - | *ADDRESSERROR :               30408 C |
 ENTRYPOINT :                   200 C |  DECOMP_BUFFER :  FFFFFFFFFFFF0000 C |
 OBJECT_RAM :        FFFFFFFFFFFF88D4 C |  RAM_END :        FFFFFFFFFFFF9FF6 C |
 SYSTEM_STACK :            FFFFFF00 - |  VDP_DATA :             C00000 - |
 VRAM_PLANE_A :              C000 - |  PLANE_H_CELLS :             40 - |
*ADDRESSERROR.__STR :                                       "ADDRESS ERROR" - |
 ENDOFROM :                  312D6 C |  OBJCODEBASE :              10000 C |
"""


class TestParseSymbolTable(unittest.TestCase):

    def setUp(self):
        self.result = parse_symbol_table(SAMPLE_SYMTAB.splitlines())

    def test_rom_labels_found(self):
        self.assertIn("ENTRYPOINT", self.result.rom_labels)
        self.assertEqual(self.result.rom_labels["ENTRYPOINT"], 0x200)

    def test_rom_labels_exclude_high_addresses(self):
        self.assertNotIn("VDP_DATA", self.result.rom_labels)

    def test_ram_labels_found(self):
        self.assertIn("DECOMP_BUFFER", self.result.ram_labels)
        self.assertEqual(self.result.ram_labels["DECOMP_BUFFER"], 0xFFFF0000)

    def test_ram_labels_masked_to_32bit(self):
        self.assertEqual(self.result.ram_labels["OBJECT_RAM"], 0xFFFF88D4)

    def test_constants_found(self):
        self.assertIn("SYSTEM_STACK", self.result.constants)
        self.assertEqual(self.result.constants["SYSTEM_STACK"], 0xFFFFFF00)

    def test_constants_include_vram(self):
        self.assertIn("VRAM_PLANE_A", self.result.constants)
        self.assertEqual(self.result.constants["VRAM_PLANE_A"], 0xC000)

    def test_unused_symbols_flagged(self):
        self.assertIn("ADDRESSERROR", self.result.unused)

    def test_string_values_skipped(self):
        self.assertNotIn("ADDRESSERROR.__STR", self.result.rom_labels)
        self.assertNotIn("ADDRESSERROR.__STR", self.result.constants)

    def test_endofrom_is_rom_label(self):
        self.assertEqual(self.result.rom_labels["ENDOFROM"], 0x312D6)

    def test_unused_symbol_still_classified(self):
        self.assertIn("ADDRESSERROR", self.result.rom_labels)
        self.assertIn("ADDRESSERROR", self.result.unused)

    def test_page_break_skipped(self):
        lines = SAMPLE_SYMTAB.replace(
            " ENDOFROM",
            " AS V1.42 Beta [Bld 212] - Source File main.asm - Page 150 - 04/25/2026\n\n\n ENDOFROM"
        ).splitlines()
        result = parse_symbol_table(lines)
        self.assertIn("ENDOFROM", result.rom_labels)


if __name__ == "__main__":
    unittest.main()
