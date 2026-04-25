#!/usr/bin/env python3
"""Tests for s4budget — ROM/RAM/VRAM budget dashboard."""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4budget import parse_symbol_table, parse_source_listing, FileContribution, Region


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


SAMPLE_LISTING = """\
 AS V1.42 Beta [Bld 212] - Source File main.asm - Page 1 - 04/25/2026

       1/       0 :                     ; Sonic 4 Engine
      23/       0 :                         org 0
      28/       0 :                     __BUDGET_VECTORS:
      29/       0 : 00FF FF00               dc.l    $00FFFF00
      30/       4 : 0000 0200               dc.l    $00000200
      88/     200 :                     __BUDGET_ENGINE:
      92/     200 :                         include "engine/boot.asm"
(1)    1/     200 :                     ; Boot sequence
(1)    2/     200 : 4AB9 00A1 0008              tst.l   ($00A10008).l
(1)    3/     206 : 66FE                        bne.s   .skip
(1)    4/     208 : 4E75                        rts
      93/     20A :                         include "engine/vdp_init.asm"
(1)    1/     20A :                     ; VDP init
(1)    2/     20A : 41FA 0010                   lea.l   Data(pc), a0
(1)    3/     20E : 4E75                        rts
     114/     210 :                         org $10000
     115/   10000 :                     __BUDGET_OBJBANK:
     116/   10000 : 4E75                        rts
     118/   10002 :                         include "objects/test_obj.asm"
(1)    1/   10002 :                     TestObj:
(1)    2/   10002 : 7000                        moveq   #0, d0
(1)    3/   10004 : 4E75                        rts
     131/   10006 :                     __BUDGET_DATA:
     132/   10006 : 0001 0002                   dc.l    $00010002
     162/   1000A :                     EndOfRom:
"""


class TestParseSourceListing(unittest.TestCase):

    def setUp(self):
        self.result = parse_source_listing(SAMPLE_LISTING.splitlines())

    def test_regions_found(self):
        names = [r.name for r in self.result.regions]
        self.assertIn("Vectors", names)
        self.assertIn("Engine", names)
        self.assertIn("Object Bank", names)
        self.assertIn("Game Data", names)

    def test_vectors_region_range(self):
        r = next(r for r in self.result.regions if r.name == "Vectors")
        self.assertEqual(r.start, 0x0)
        self.assertEqual(r.end, 0x200)

    def test_engine_region_range(self):
        r = next(r for r in self.result.regions if r.name == "Engine")
        self.assertEqual(r.start, 0x200)
        self.assertEqual(r.end, 0x10000)

    def test_objbank_region_range(self):
        r = next(r for r in self.result.regions if r.name == "Object Bank")
        self.assertEqual(r.start, 0x10000)
        self.assertEqual(r.end, 0x10006)

    def test_data_region_range(self):
        r = next(r for r in self.result.regions if r.name == "Game Data")
        self.assertEqual(r.start, 0x10006)
        self.assertEqual(r.end, 0x1000A)

    def test_file_contributions_found(self):
        files = {fc.filename for fc in self.result.file_contributions}
        self.assertIn("engine/boot.asm", files)
        self.assertIn("engine/vdp_init.asm", files)
        self.assertIn("objects/test_obj.asm", files)

    def test_boot_asm_size(self):
        fc = next(f for f in self.result.file_contributions if f.filename == "engine/boot.asm")
        self.assertEqual(fc.size, 0x20A - 0x200)

    def test_vdp_init_size(self):
        fc = next(f for f in self.result.file_contributions if f.filename == "engine/vdp_init.asm")
        self.assertEqual(fc.size, 0x210 - 0x20A)

    def test_test_obj_size(self):
        fc = next(f for f in self.result.file_contributions if f.filename == "objects/test_obj.asm")
        self.assertEqual(fc.size, 0x10006 - 0x10002)

    def test_endofrom_value(self):
        self.assertEqual(self.result.endofrom, 0x1000A)

    def test_empty_input(self):
        result = parse_source_listing([])
        self.assertEqual(result.regions, [])
        self.assertEqual(result.file_contributions, [])
        self.assertEqual(result.endofrom, 0)


if __name__ == "__main__":
    unittest.main()
