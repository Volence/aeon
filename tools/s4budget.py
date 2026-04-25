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

import argparse
import json
import os
import re
import sys
from typing import Dict, List, NamedTuple, Optional, Set, Tuple


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


# ---------------------------------------------------------------------------
# RAM layout computation
# ---------------------------------------------------------------------------

class RAMEntry(NamedTuple):
    name: str
    address: int
    size: int


class RAMLayout(NamedTuple):
    lower: List[RAMEntry]
    upper: List[RAMEntry]
    total_used: int
    free_before_stack: int
    stack_addr: int


_DEFAULT_STACK = 0xFFFFFF00
_LOWER_RAM_START = 0xFFFF0000
_UPPER_RAM_START = 0xFFFF8000


def _entries_from_sorted(syms: List[Tuple[str, int]],
                         boundary: int) -> List[RAMEntry]:
    """Build RAMEntry list from address-sorted symbols.

    Each entry's size is the gap to the next symbol (or *boundary* for the
    last one).  Zero-size entries (two symbols at the same address) are
    dropped.
    """
    entries: List[RAMEntry] = []
    for i, (name, addr) in enumerate(syms):
        if i + 1 < len(syms):
            size = syms[i + 1][1] - addr
        else:
            size = boundary - addr
        if size > 0:
            entries.append(RAMEntry(name, addr, size))
    return entries


def compute_ram_layout(ram_labels: Dict[str, int],
                       constants: Dict[str, int]) -> RAMLayout:
    """Compute per-buffer RAM breakdown from symbol addresses.

    Splits symbols into Lower RAM ($FFFF0000-$FFFF7FFF) and Upper RAM
    ($FFFF8000+).  Free space is measured from the highest symbol to
    SYSTEM_STACK.
    """
    stack_addr = constants.get("SYSTEM_STACK", _DEFAULT_STACK)

    lower_syms = sorted(
        [(n, a) for n, a in ram_labels.items() if a < _UPPER_RAM_START],
        key=lambda x: x[1],
    )
    upper_syms = sorted(
        [(n, a) for n, a in ram_labels.items() if a >= _UPPER_RAM_START],
        key=lambda x: x[1],
    )

    lower = _entries_from_sorted(lower_syms, _UPPER_RAM_START)
    # Don't extend the last upper entry to the stack — its actual size is
    # unknowable from labels alone.  free_before_stack owns that gap.
    highest = upper_syms[-1][1] if upper_syms else _UPPER_RAM_START
    upper = _entries_from_sorted(upper_syms, highest)

    total_used = sum(e.size for e in lower) + sum(e.size for e in upper)
    free = stack_addr - highest

    return RAMLayout(lower, upper, total_used, free, stack_addr)


# ---------------------------------------------------------------------------
# VRAM layout computation
# ---------------------------------------------------------------------------

class VRAMLayout(NamedTuple):
    total_bytes: int         # 65536
    total_tiles: int         # 2048
    plane_a_addr: int
    plane_a_size: int
    plane_b_addr: int
    plane_b_size: int
    sprite_table_addr: int
    sprite_table_size: int
    hscroll_table_addr: int
    hscroll_table_size: int
    window_addr: int
    window_size: int
    art_tiles_available: int


_SPRITE_TABLE_SIZE = 640   # 80 entries x 8 bytes
_HSCROLL_SIZE = 896        # 224 lines x 4 bytes (per-line hscroll)
_TILE_SIZE = 32            # 8x8 tile, 4bpp = 32 bytes


def compute_vram_layout(constants: Dict[str, int]) -> Optional[VRAMLayout]:
    """Compute static VRAM layout from VDP configuration constants.

    Returns None when required constants (VRAM_PLANE_A, VRAM_PLANE_B,
    PLANE_H_CELLS, PLANE_V_CELLS) are missing.
    """
    required = ["VRAM_PLANE_A", "VRAM_PLANE_B", "PLANE_H_CELLS", "PLANE_V_CELLS"]
    if not all(k in constants for k in required):
        return None

    h_cells = constants["PLANE_H_CELLS"]
    v_cells = constants["PLANE_V_CELLS"]
    plane_size = h_cells * v_cells * 2

    sprite_addr = constants.get("VRAM_SPRITE_TABLE", 0xD800)
    hscroll_addr = constants.get("VRAM_HSCROLL_TABLE", 0xDC00)
    window_addr = constants.get("VRAM_WINDOW", 0xF000)
    window_size = plane_size

    vdp_tables_start = min(
        constants["VRAM_PLANE_A"],
        constants["VRAM_PLANE_B"],
        sprite_addr,
        hscroll_addr,
        window_addr,
    )
    art_bytes = vdp_tables_start
    art_tiles = art_bytes // _TILE_SIZE

    return VRAMLayout(
        total_bytes=65536,
        total_tiles=2048,
        plane_a_addr=constants["VRAM_PLANE_A"],
        plane_a_size=plane_size,
        plane_b_addr=constants["VRAM_PLANE_B"],
        plane_b_size=plane_size,
        sprite_table_addr=sprite_addr,
        sprite_table_size=_SPRITE_TABLE_SIZE,
        hscroll_table_addr=hscroll_addr,
        hscroll_table_size=_HSCROLL_SIZE,
        window_addr=window_addr,
        window_size=window_size,
        art_tiles_available=art_tiles,
    )


# ---------------------------------------------------------------------------
# Report formatters
# ---------------------------------------------------------------------------

_ROM_MAX = 4 * 1024 * 1024  # 4MB
_OBJBANK_LIMIT = 64 * 1024  # 64KB


def _fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024*1024):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n:,} B"


def _fmt_size_aligned(n: int, width: int = 10) -> str:
    return _fmt_size(n).rjust(width)


def format_rom_report(regions: List[Region],
                      file_contributions: List[FileContribution],
                      endofrom: int,
                      rom_file_size: Optional[int] = None) -> str:
    lines = []
    actual_size = rom_file_size if rom_file_size is not None else endofrom
    pct = actual_size / _ROM_MAX * 100

    lines.append("=== ROM Budget ===")
    lines.append(f"ROM: {actual_size:,} / {_ROM_MAX:,} bytes ({pct:.1f}%)")
    lines.append("")

    for r in regions:
        extra = ""
        if r.name == "Object Bank":
            ob_pct = r.size / _OBJBANK_LIMIT * 100
            extra = f"  (of 64 KB limit: {ob_pct:.1f}%)"
        lines.append(f"  {r.name:<14} ${r.start:06X}-${r.end:06X}  {_fmt_size_aligned(r.size)}{extra}")

    free = _ROM_MAX - actual_size
    lines.append(f"  {'Free':<14} {'':>15} {_fmt_size_aligned(free)}")

    for r in regions:
        region_files = [
            fc for fc in file_contributions
            if fc.start >= r.start and fc.start < r.end
        ]
        if not region_files:
            continue
        region_files.sort(key=lambda f: f.start)
        lines.append("")
        lines.append(f"  {r.name} ({_fmt_size(r.size)}):")
        for fc in region_files:
            lines.append(f"    {fc.filename:<40} {_fmt_size_aligned(fc.size)}")

    return "\n".join(lines)


def format_ram_report(layout: RAMLayout) -> str:
    lines = []
    lines.append("=== RAM Budget ===")
    lines.append(
        f"RAM: {layout.total_used:,} bytes  "
        f"[{layout.free_before_stack:,} free before stack]"
    )
    lines.append("")

    if layout.lower:
        lines.append(f"  Lower RAM (${_LOWER_RAM_START:08X}-${_UPPER_RAM_START - 1:08X}):")
        for e in layout.lower:
            lines.append(f"    {e.name:<30} {e.size:>10,} B")
        if layout.upper:
            lines.append("")

    if layout.upper:
        lines.append(f"  Upper RAM (${_UPPER_RAM_START:08X}+):")
        for e in layout.upper:
            lines.append(f"    {e.name:<30} {e.size:>10,} B")
        lines.append(f"    {'[Free]':<30} {layout.free_before_stack:>10,} B  -> ${layout.stack_addr:08X} (stack)")

    return "\n".join(lines)


def format_vram_report(layout: VRAMLayout) -> str:
    lines = []
    lines.append("=== VRAM Budget ===")
    lines.append(f"VRAM: {layout.total_bytes:,} bytes ({layout.total_tiles:,} tiles)")
    lines.append("")

    entries = [
        ("Plane A", layout.plane_a_addr, layout.plane_a_size, layout.plane_a_size // _TILE_SIZE),
        ("Plane B", layout.plane_b_addr, layout.plane_b_size, layout.plane_b_size // _TILE_SIZE),
        ("Sprite Table", layout.sprite_table_addr, layout.sprite_table_size, None),
        ("Hscroll Table", layout.hscroll_table_addr, layout.hscroll_table_size, None),
        ("Window Plane", layout.window_addr, layout.window_size, layout.window_size // _TILE_SIZE),
    ]
    for name, addr, size, tiles in entries:
        tile_str = f"  ({tiles:,} tiles)" if tiles is not None else ""
        end_addr = addr + size - 1
        lines.append(f"  {name:<16} ${addr:04X}-${end_addr:04X}  {size:>6,} B{tile_str}")

    art_bytes = layout.art_tiles_available * _TILE_SIZE
    if art_bytes > 0:
        lines.append(f"  {'Art Tiles':<16} $0000-${art_bytes - 1:04X}  {art_bytes:>6,} B  ({layout.art_tiles_available:,} tiles available)")
    else:
        lines.append(f"  {'Art Tiles':<16} {'':>11}      0 B  (0 tiles available)")

    return "\n".join(lines)


def format_summary(regions: List[Region], rom_file_size: int,
                   ram: RAMLayout) -> str:
    rom_kb = rom_file_size // 1024
    rom_pct = int(rom_file_size / _ROM_MAX * 100)

    objbank = next((r for r in regions if r.name == "Object Bank"), None)
    ob_str = ""
    if objbank:
        ob_kb = objbank.size // 1024
        ob_pct = int(objbank.size / _OBJBANK_LIMIT * 100)
        ob_str = f" | ObjBank: {ob_kb}KB/64KB ({ob_pct}%)"

    ram_kb = ram.total_used // 1024
    ram_total_kb = 32
    ram_pct = int(ram.total_used / (32 * 1024) * 100)
    free_kb = ram.free_before_stack / 1024

    return (
        f"ROM: {rom_kb}KB/4MB ({rom_pct}%)"
        f"{ob_str}"
        f" | RAM: {ram_kb}KB/{ram_total_kb}KB ({ram_pct}%)"
        f" | Free: {free_kb:.1f}KB before stack"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="s4budget",
        description="ROM/RAM/VRAM budget dashboard for the Sonic 4 Engine.",
    )
    p.add_argument("listing", help="Path to AS listing file (s4.lst)")
    p.add_argument("rom", help="Path to ROM binary (s4.bin)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--summary", action="store_true",
                      help="Print compact one-liner to stderr (for build integration)")
    mode.add_argument("--json", action="store_true",
                      help="Output as JSON to stdout")
    p.add_argument("--rom-only", action="store_true",
                   help="Show only ROM budget (full report mode)")
    p.add_argument("--ram-only", action="store_true",
                   help="Show only RAM budget (full report mode)")
    p.add_argument("--vram-only", action="store_true",
                   help="Show only VRAM budget (full report mode)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not os.path.isfile(args.listing):
        print(f"s4budget: error: listing file not found: {args.listing}", file=sys.stderr)
        return 1

    with open(args.listing, "r", encoding="utf-8", errors="replace") as f:
        listing_lines = f.readlines()

    symbols = parse_symbol_table(listing_lines)
    source = parse_source_listing(listing_lines)

    rom_file_size: Optional[int] = None
    if os.path.isfile(args.rom):
        rom_file_size = os.path.getsize(args.rom)

    ram = compute_ram_layout(symbols.ram_labels, symbols.constants)
    vram = compute_vram_layout(symbols.constants)

    if args.json:
        data = {
            "rom": {
                "size": rom_file_size if rom_file_size is not None else source.endofrom,
                "max": _ROM_MAX,
                "percent": round((rom_file_size if rom_file_size is not None else source.endofrom) / _ROM_MAX * 100, 1),
                "regions": [
                    {"name": r.name, "start": r.start, "end": r.end, "size": r.size}
                    for r in source.regions
                ],
                "files": [
                    {"filename": f.filename, "start": f.start, "end": f.end, "size": f.size}
                    for f in source.file_contributions
                ],
            },
            "ram": {
                "total_used": ram.total_used,
                "free_before_stack": ram.free_before_stack,
                "lower": [{"name": e.name, "address": e.address, "size": e.size} for e in ram.lower],
                "upper": [{"name": e.name, "address": e.address, "size": e.size} for e in ram.upper],
            },
            "vram": {
                "total_tiles": vram.total_tiles if vram else 0,
                "art_tiles_available": vram.art_tiles_available if vram else 0,
            } if vram else None,
        }
        print(json.dumps(data, indent=2))
        return 0

    if args.summary:
        actual_rom = rom_file_size if rom_file_size is not None else source.endofrom
        print(format_summary(source.regions, actual_rom, ram), file=sys.stderr)
        return 0

    show_all = not (args.rom_only or args.ram_only or args.vram_only)

    sections = []
    if show_all or args.rom_only:
        sections.append(format_rom_report(
            source.regions, source.file_contributions,
            source.endofrom, rom_file_size
        ))
    if show_all or args.ram_only:
        sections.append(format_ram_report(ram))
    if (show_all or args.vram_only) and vram:
        sections.append(format_vram_report(vram))
    elif args.vram_only and not vram:
        print("s4budget: VRAM constants not found in listing", file=sys.stderr)
        return 1

    print("\n\n".join(sections))
    return 0


if __name__ == "__main__":
    sys.exit(main())
