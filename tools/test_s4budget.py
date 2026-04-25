#!/usr/bin/env python3
"""Tests for s4budget — ROM/RAM/VRAM budget dashboard."""

import unittest
import os
import sys
import tempfile
import io
import contextlib
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4budget import (
    parse_symbol_table, parse_source_listing, FileContribution, Region,
    compute_ram_layout, compute_vram_layout, RAMLayout, RAMEntry, VRAMLayout,
    format_rom_report, format_ram_report, format_vram_report, format_summary,
    main as s4budget_main,
)


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


class TestComputeRAMLayout(unittest.TestCase):

    def test_basic_layout(self):
        ram_labels = {
            "DECOMP_BUFFER": 0xFFFF0000,
            "DECOMP_BUFFER_END": 0xFFFF8000,
            "RAM_START": 0xFFFF8000,
            "VBLANK_FLAG": 0xFFFF8000,
            "FRAME_COUNTER": 0xFFFF8002,
            "OBJECT_RAM": 0xFFFF8010,
            "RAM_END": 0xFFFF9000,
        }
        constants = {"SYSTEM_STACK": 0xFFFFFF00}
        result = compute_ram_layout(ram_labels, constants)

        self.assertEqual(len(result.lower), 1)
        self.assertEqual(result.lower[0].name, "DECOMP_BUFFER")
        self.assertEqual(result.lower[0].size, 0x8000)

        self.assertGreater(len(result.upper), 0)
        self.assertEqual(result.free_before_stack, 0xFFFFFF00 - 0xFFFF9000)
        # total_used + free must not double-count
        self.assertEqual(
            result.total_used + result.free_before_stack,
            0x8000 + (0xFFFFFF00 - 0xFFFF8000),
        )

    def test_upper_ram_sorted_by_address(self):
        ram_labels = {
            "B_SECOND": 0xFFFF8010,
            "A_FIRST": 0xFFFF8000,
            "C_THIRD": 0xFFFF8020,
        }
        constants = {"SYSTEM_STACK": 0xFFFFFF00}
        result = compute_ram_layout(ram_labels, constants)
        names = [e.name for e in result.upper]
        self.assertEqual(names, ["A_FIRST", "B_SECOND"])

    def test_missing_stack_uses_default(self):
        ram_labels = {"RAM_END": 0xFFFF9000}
        result = compute_ram_layout(ram_labels, {})
        self.assertEqual(result.free_before_stack, 0xFFFFFF00 - 0xFFFF9000)


class TestComputeVRAMLayout(unittest.TestCase):

    def test_basic_layout(self):
        constants = {
            "VRAM_PLANE_A": 0xC000,
            "VRAM_PLANE_B": 0xE000,
            "VRAM_SPRITE_TABLE": 0xD800,
            "VRAM_HSCROLL_TABLE": 0xDC00,
            "VRAM_WINDOW": 0xF000,
            "PLANE_H_CELLS": 64,
            "PLANE_V_CELLS": 64,
        }
        result = compute_vram_layout(constants)
        self.assertEqual(result.total_bytes, 65536)
        self.assertEqual(result.total_tiles, 2048)
        self.assertEqual(result.plane_a_size, 64 * 64 * 2)
        self.assertEqual(result.plane_b_size, 64 * 64 * 2)
        self.assertGreater(result.art_tiles_available, 0)

    def test_missing_constants_returns_none(self):
        result = compute_vram_layout({})
        self.assertIsNone(result)


class TestFormatROMReport(unittest.TestCase):

    def test_contains_header(self):
        regions = [Region("Engine", 0x200, 0x1000, 0xE00)]
        files = [FileContribution("engine/boot.asm", 0x200, 0x600, 0x400)]
        output = format_rom_report(regions, files, 0x1000, 0x1000)
        self.assertIn("=== ROM Budget ===", output)
        self.assertIn("Engine", output)

    def test_objbank_shows_limit_with_percentage(self):
        regions = [Region("Object Bank", 0x10000, 0x18000, 0x8000)]
        output = format_rom_report(regions, [], 0x18000, 0x18000)
        self.assertIn("64 KB limit", output)
        self.assertIn("50.0%", output)

    def test_per_file_breakdown(self):
        regions = [Region("Engine", 0x200, 0x600, 0x400)]
        files = [
            FileContribution("engine/boot.asm", 0x200, 0x400, 0x200),
            FileContribution("engine/vdp_init.asm", 0x400, 0x600, 0x200),
        ]
        output = format_rom_report(regions, files, 0x600, 0x600)
        self.assertIn("engine/boot.asm", output)
        self.assertIn("engine/vdp_init.asm", output)


class TestFormatRAMReport(unittest.TestCase):

    def test_contains_header(self):
        layout = RAMLayout(
            lower=[RAMEntry("DECOMP_BUFFER", 0xFFFF0000, 0x8000)],
            upper=[RAMEntry("VBLANK_FLAG", 0xFFFF8000, 1)],
            total_used=0x8001,
            free_before_stack=0x6FFF,
            stack_addr=0xFFFFFF00,
        )
        output = format_ram_report(layout)
        self.assertIn("=== RAM Budget ===", output)
        self.assertIn("DECOMP_BUFFER", output)
        self.assertIn("free before stack", output)

    def test_lower_only_no_trailing_blank(self):
        layout = RAMLayout(
            lower=[RAMEntry("DECOMP_BUFFER", 0xFFFF0000, 0x8000)],
            upper=[],
            total_used=0x8000,
            free_before_stack=0x7F00,
            stack_addr=0xFFFFFF00,
        )
        output = format_ram_report(layout)
        self.assertFalse(output.endswith("\n"))
        self.assertIn("DECOMP_BUFFER", output)


class TestFormatVRAMReport(unittest.TestCase):

    def test_contains_header(self):
        layout = VRAMLayout(
            total_bytes=65536, total_tiles=2048,
            plane_a_addr=0xC000, plane_a_size=8192,
            plane_b_addr=0xE000, plane_b_size=8192,
            sprite_table_addr=0xD800, sprite_table_size=640,
            hscroll_table_addr=0xDC00, hscroll_table_size=896,
            window_addr=0xF000, window_size=8192,
            art_tiles_available=1536,
        )
        output = format_vram_report(layout)
        self.assertIn("=== VRAM Budget ===", output)
        self.assertIn("Plane A", output)
        self.assertIn("1,536 tiles", output)


class TestFormatSummary(unittest.TestCase):

    def test_oneliner_format(self):
        regions = [
            Region("Engine", 0x200, 0x1000, 0xE00),
            Region("Object Bank", 0x10000, 0x18000, 0x8000),
        ]
        ram = RAMLayout(
            lower=[], upper=[],
            total_used=26624,
            free_before_stack=5888,
            stack_addr=0xFFFFFF00,
        )
        output = format_summary(regions, 209408, ram)
        self.assertIn("ROM:", output)
        self.assertIn("ObjBank:", output)
        self.assertIn("RAM:", output)
        self.assertIn("Free:", output)
        # Should be a single line
        self.assertEqual(output.count("\n"), 0)


class TestCLI(unittest.TestCase):

    def _make_listing(self):
        return """\
 AS V1.42 Beta [Bld 212] - Source File main.asm - Page 1 - 04/25/2026

       1/       0 :                     ; Sonic 4 Engine
      23/       0 :                         org 0
      28/       0 :                     __BUDGET_VECTORS:
      29/       0 : 00FF FF00               dc.l    $00FFFF00
      88/     200 :                     __BUDGET_ENGINE:
      92/     200 : 4E75                        rts
     114/     202 :                         org $10000
     115/   10000 :                     __BUDGET_OBJBANK:
     116/   10000 : 4E75                        rts
     131/   10002 :                     __BUDGET_DATA:
     132/   10002 : 0001                        dc.w    1
     162/   10004 :                     EndOfRom:

  Symbol Table (* = unused):
  --------------------------

 DECOMP_BUFFER :             FFFFFFFFFFFF0000 C |  RAM_END :  FFFFFFFFFFFF9000 C |
 SYSTEM_STACK :            FFFFFF00 - |  VRAM_PLANE_A :            C000 - |
 VRAM_PLANE_B :            E000 - |  VRAM_SPRITE_TABLE :       D800 - |
 VRAM_HSCROLL_TABLE :      DC00 - |  VRAM_WINDOW :             F000 - |
 PLANE_H_CELLS :             40 - |  PLANE_V_CELLS :            40 - |

    10 symbols
"""

    def _run(self, listing_content, extra_args=None):
        lst_file = tempfile.NamedTemporaryFile(mode="w", suffix=".lst", delete=False)
        lst_file.write(listing_content)
        lst_file.flush()
        lst_file.close()

        bin_file = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        bin_file.write(b"\x00" * 0x10004)
        bin_file.close()

        try:
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                code = s4budget_main([lst_file.name, bin_file.name] + (extra_args or []))
            return code, buf.getvalue()
        finally:
            os.unlink(lst_file.name)
            os.unlink(bin_file.name)

    def test_full_report_exits_zero(self):
        code, output = self._run(self._make_listing())
        self.assertEqual(code, 0)
        self.assertIn("ROM Budget", output)
        self.assertIn("RAM Budget", output)
        self.assertIn("VRAM Budget", output)

    def test_summary_mode(self):
        code, output = self._run(self._make_listing(), ["--summary"])
        self.assertEqual(code, 0)
        self.assertIn("ROM:", output)
        self.assertNotIn("=== ROM Budget ===", output)

    def test_rom_only(self):
        code, output = self._run(self._make_listing(), ["--rom-only"])
        self.assertEqual(code, 0)
        self.assertIn("ROM Budget", output)
        self.assertNotIn("RAM Budget", output)

    def test_ram_only(self):
        code, output = self._run(self._make_listing(), ["--ram-only"])
        self.assertEqual(code, 0)
        self.assertNotIn("ROM Budget", output)
        self.assertIn("RAM Budget", output)

    def test_json_output(self):
        code, output = self._run(self._make_listing(), ["--json"])
        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertIn("rom", data)
        self.assertIn("ram", data)

    def test_missing_listing_exits_one(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = s4budget_main(["/nonexistent.lst", "/nonexistent.bin"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
