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
from typing import Dict, List, NamedTuple, Set, Tuple


class FileContribution(NamedTuple):
    filename: str
    start: int
    end: int
    size: int


class Region(NamedTuple):
    name: str
    start: int
    end: int
    size: int


class SourceListingResult(NamedTuple):
    regions: List[Region]
    file_contributions: List[FileContribution]
    endofrom: int


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


# ---------------------------------------------------------------------------
# Source listing parser
# ---------------------------------------------------------------------------

_SOURCE_LINE_RE = re.compile(
    r'^(?:\((\d+)\))?\s*(\d+)\s*/\s*([0-9A-Fa-f]+)\s*:'
)
_INCLUDE_RE = re.compile(r'include\s+"([^"]+)"', re.IGNORECASE)
_SENTINEL_RE = re.compile(r'(__BUDGET_\w+):')
_ENDOFROM_RE = re.compile(r'EndOfRom:', re.IGNORECASE)

_SENTINEL_NAMES: Dict[str, str] = {
    "__BUDGET_VECTORS": "Vectors",
    "__BUDGET_ENGINE": "Engine",
    "__BUDGET_OBJBANK": "Object Bank",
    "__BUDGET_DATA": "Game Data",
}


def _is_ram_addr_str(addr_str: str) -> bool:
    """Return True if the address string represents a RAM phase block."""
    return len(addr_str) > 6 and addr_str.upper().startswith("FFFFFFFFFFFF")


def _build_regions(
    sentinels: List[Tuple[str, int]], endofrom: int
) -> List[Region]:
    """Build region list from ordered sentinel addresses and EndOfRom."""
    regions: List[Region] = []
    for i, (name, start) in enumerate(sentinels):
        if i + 1 < len(sentinels):
            end = sentinels[i + 1][1]
        else:
            end = endofrom
        regions.append(Region(name=name, start=start, end=end, size=end - start))
    return regions


def parse_source_listing(lines: List[str]) -> SourceListingResult:
    """Parse the source listing section of an AS listing file.

    Tracks which include file contributes how many ROM bytes and detects
    ``__BUDGET_*`` sentinel labels for region boundaries.
    """
    include_stack: List[Tuple[str, int]] = []
    file_contributions: List[FileContribution] = []
    sentinel_map: Dict[str, int] = {}
    sentinel_order: List[str] = []
    endofrom: int = 0
    prev_depth: int = 0
    last_addr: int = 0

    for line in lines:
        if _PAGE_BREAK_RE.match(line):
            continue

        m = _SOURCE_LINE_RE.match(line)
        if m is None:
            continue

        depth = int(m.group(1)) if m.group(1) else 0
        addr_str = m.group(3)

        # Skip RAM phase blocks for ROM accounting
        if _is_ram_addr_str(addr_str):
            continue

        addr = int(addr_str, 16)

        # Depth decreased — pop include entries that have ended.
        # The current line's address marks where the parent resumes,
        # which is the byte right after the included file's last opcode.
        while prev_depth > depth and include_stack:
            fname, first = include_stack.pop()
            file_contributions.append(FileContribution(
                filename=fname, start=first, end=addr, size=addr - first
            ))
            prev_depth -= 1

        # Check for sentinel labels
        ms = _SENTINEL_RE.search(line)
        if ms:
            label = ms.group(1)
            if label in _SENTINEL_NAMES:
                sentinel_map[label] = addr
                if label not in sentinel_order:
                    sentinel_order.append(label)

        # Check for EndOfRom
        if _ENDOFROM_RE.search(line):
            endofrom = addr

        # Check for include directive
        mi = _INCLUDE_RE.search(line)
        if mi:
            include_stack.append((mi.group(1), addr))
            prev_depth = depth + 1
            last_addr = addr
            continue

        last_addr = addr
        prev_depth = depth

    # Flush any remaining include stack entries (EOF before depth returned)
    while include_stack:
        fname, first = include_stack.pop()
        file_contributions.append(FileContribution(
            filename=fname, start=first, end=last_addr, size=last_addr - first
        ))

    # Build regions from sentinels
    sentinels: List[Tuple[str, int]] = [
        (_SENTINEL_NAMES[key], sentinel_map[key]) for key in sentinel_order
    ]
    regions = _build_regions(sentinels, endofrom)

    return SourceListingResult(
        regions=regions,
        file_contributions=file_contributions,
        endofrom=endofrom,
    )
