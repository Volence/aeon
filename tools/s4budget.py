#!/usr/bin/env python3
"""
s4budget — Sonic 4 Engine ROM/RAM/VRAM budget dashboard.

Parses the AS Macro Assembler listing file to report space usage
by region, file, and buffer.

Usage:
    python3 tools/s4budget.py s4.lst s4.bin              # full report
    python3 tools/s4budget.py s4.lst s4.bin --summary    # build one-liner
"""

from __future__ import annotations

import re
from typing import Dict, List, NamedTuple, Set


class SymbolTable(NamedTuple):
    rom_labels: Dict[str, int]
    ram_labels: Dict[str, int]
    constants: Dict[str, int]
    unused: Set[str]

_MAX_ROM_ADDR = 0x400000

_SYM_ENTRY_RE = re.compile(
    r'(\*?)'
    r'([\w.]+)'
    r'\s*:\s*'
    r'([0-9A-Fa-f]+|"[^"]*")'
    r'\s+([C\-])'
    r'\s*\|'
)

_PAGE_BREAK_RE = re.compile(r'^\s*AS V\d+\.\d+')


def parse_symbol_table(lines: List[str]) -> SymbolTable:
    """Parse the AS Macro Assembler symbol table section from listing lines.

    Buckets:
      rom_labels  — type C, address < $400000, not RAM-prefixed.
                    These are code/data labels assembled into the ROM.
      ram_labels  — type C, FFFFFFFFFFFF prefix (AS sign-extends negative
                    equates to 48 bits).  Values are masked to 32-bit so
                    callers get the real Genesis RAM address (e.g. $FFFF8000).
      constants   — type -, all values.  Covers hardware register addresses
                    ($C00000-$C0001F), VRAM tile constants, numeric equates,
                    and any other AS "absolute" symbol.
      unused      — names whose entry is prefixed with '*' in the listing.
                    A symbol in this set also appears in its value bucket
                    (rom_labels / ram_labels / constants) — membership is
                    not exclusive.
    """
    rom_labels: Dict[str, int] = {}
    ram_labels: Dict[str, int] = {}
    constants: Dict[str, int] = {}
    unused: Set[str] = set()

    in_symtab = False

    for line in lines:
        if _PAGE_BREAK_RE.match(line):
            continue

        if "Symbol Table" in line and "unused" in line:
            in_symtab = True
            continue
        if line.strip().startswith("---") and in_symtab:
            continue
        if in_symtab and line.strip() == "":
            continue

        if in_symtab and re.match(r'\s+\d+ symbols', line):
            break
        if in_symtab and line.strip().startswith("Defined"):
            break

        if not in_symtab:
            continue

        for m in _SYM_ENTRY_RE.finditer(line):
            star, name, raw_val, typ = m.groups()

            if raw_val.startswith('"'):
                continue

            val = int(raw_val, 16)

            if star == "*":
                unused.add(name)

            if typ == "C":
                if raw_val.upper().startswith("FFFFFFFFFFFF"):
                    ram_labels[name] = val & 0xFFFFFFFF
                elif val < _MAX_ROM_ADDR:
                    rom_labels[name] = val
            else:
                constants[name] = val

    return SymbolTable(rom_labels, ram_labels, constants, unused)
